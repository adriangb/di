from collections import defaultdict
from contextlib import (
    AbstractAsyncContextManager,
    AbstractContextManager,
    AsyncExitStack,
    asynccontextmanager,
    contextmanager,
)
from functools import partial
from itertools import chain
from typing import AsyncGenerator, Callable, Dict, Hashable, List, Set, Tuple, Union

import anyio

from anydep.concurrency import contextmanager_in_threadpool, run_in_threadpool
from anydep.exceptions import DuplicateScopeError, UnknownScopError, WiringError
from anydep.inspect import (
    call_from_annotation,
    get_parameters,
    is_async_gen_callable,
    is_coroutine_callable,
    is_gen_callable,
)
from anydep.models import (
    Dependant,
    Dependency,
    DependencyProvider,
    DependencyProviderType,
    DependencyType,
    Scope,
    Task,
)
from anydep.topsort import topsort


class Container:
    def __init__(self) -> None:
        self._bound_providers: Dict[DependencyProvider, Dependant[DependencyProvider]] = {}
        self._bound_dependants: Dict[Dependant[DependencyProvider], Dependant[DependencyProvider]] = {}
        self._cached_values: Dict[Hashable, Dict[DependencyProvider, Dependency]] = {}
        self._stacks: Dict[Scope, AsyncExitStack] = {}
        self._scopes: List[Scope] = []
        self._infered_dependants: Dict[Tuple[DependencyProvider, str], Dependant[DependencyProvider]] = {}

    def bind(
        self,
        target: Union[Dependant[DependencyProviderType[DependencyType]], DependencyProviderType[Dependency]],
        dependant: Dependant[DependencyProviderType[DependencyType]],
    ) -> None:
        if isinstance(target, Dependant):
            self._bound_dependants[target] = dependant
        else:
            self._bound_providers[target] = dependant

    @asynccontextmanager
    async def enter_scope(self, scope: Scope) -> AsyncGenerator[None, None]:
        if scope in self._stacks:
            raise DuplicateScopeError(f"Scope {scope} has already been entered!")
        async with AsyncExitStack() as stack:
            self._scopes.append(scope)
            self._stacks[scope] = stack
            bound_providers = self._bound_providers
            bound_dependants = self._bound_dependants
            self._bound_providers = bound_providers.copy()
            self._bound_dependants = bound_dependants.copy()
            self._cached_values[scope] = {}
            try:
                yield
            finally:
                self._stacks.pop(scope)
                self._bound_providers = bound_providers
                self._bound_dependants = bound_dependants
                self._cached_values.pop(scope)
                self._scopes.pop()

    def _get_scope_index(self, scope: Scope) -> int:
        self._check_scope(scope)
        return self._scopes.index(scope)

    def _resolve_scope(self, dependant_scope: Scope) -> Hashable:
        if dependant_scope is False:
            return False
        elif dependant_scope is None:
            return self._scopes[-1]  # current scope
        else:
            return dependant_scope

    def _task_from_cached_value(self, value: DependencyType) -> Task[Callable[[], DependencyType]]:
        def retrieve():
            return value

        new_dependant: Dependant[DependencyProviderType[DependencyType]] = Dependant(call=retrieve, parameters=[])
        return Task(dependant=new_dependant, positional_arguments=[], keyword_arguments={}, dependencies=[])

    def _wire_task(
        self,
        dependant: Dependant[DependencyProviderType[DependencyType]],
        *,
        seen: Set[Dependant],
        cache: Dict[DependencyProvider, Dict[Scope, Task]],
    ) -> Task[DependencyProviderType[DependencyType]]:
        assert dependant.call is not None  # for mypy
        if dependant in seen:
            raise WiringError("Circular dependencies detected")
        seen = seen | set([dependant])
        if dependant.parameters is None:
            dependant.parameters = get_parameters(dependant.call)
            assert dependant.parameters is not None
        task: Task[DependencyProviderType[DependencyType]] = Task(dependant=dependant)
        for parameter in dependant.parameters:
            sub_dependant: Dependant[DependencyProvider]
            if isinstance(parameter.default, Dependant):
                sub_dependant = parameter.default
                if sub_dependant.call is None:
                    sub_dependant.call = call_from_annotation(parameter)
            elif parameter.default is parameter.empty:
                key = (dependant.call, parameter.name)
                if key not in self._infered_dependants:
                    self._infered_dependants[key] = Dependant(call=call_from_annotation(parameter))
                sub_dependant = self._infered_dependants[key]
            else:
                continue  # parameter has default value, use that
            assert sub_dependant.call is not None  # for mypy
            subtask: Union[None, Task[DependencyProvider]] = None
            if sub_dependant in self._bound_dependants:
                sub_dependant = self._bound_dependants[sub_dependant]
                subtask = self._wire_task(sub_dependant, seen=seen, cache=cache)  # always rebuild
            else:
                if sub_dependant.call in self._bound_providers and sub_dependant.scope is not False:
                    sub_dependant = self._bound_providers[sub_dependant.call]
                scope = self._resolve_scope(sub_dependant.scope)
                self._check_scope(scope)
                if scope is not False:
                    for cache_scope in self._scopes:
                        cached_values = self._cached_values[cache_scope]
                        if sub_dependant.call in cached_values:
                            value = cached_values[sub_dependant.call]
                            subtask = self._task_from_cached_value(value)
                            break
                    if sub_dependant.call in cache:
                        for cache_scope, cached in cache[sub_dependant.call].items():
                            if self._get_scope_index(cache_scope) <= self._get_scope_index(scope):
                                # e.g. cache_scope == "app" and scope == "request"
                                subtask = cached
                                break
                if subtask is None:
                    subtask = self._wire_task(sub_dependant, seen=seen, cache=cache)
                    if scope is not False:
                        assert sub_dependant.call is not None  # _wire_task allways returns with an assigned .call
                        cache[sub_dependant.call][scope] = subtask
            if parameter.positional:
                task.positional_arguments.append(subtask)
            else:
                task.keyword_arguments[parameter.name] = subtask
        return task

    def _build_task_dag(
        self, dependant: Dependant[DependencyProviderType[DependencyType]]
    ) -> Task[DependencyProviderType[DependencyType]]:
        if dependant.call is None:
            raise WiringError("Top level dependant must have a `call`")

        task = self._wire_task(dependant, seen=set(), cache=defaultdict(dict))

        graph: Dict[Task, Set[Task]] = {}

        def build_graph(tsk: Task) -> None:
            if tsk in graph:
                return
            graph[tsk] = set()
            for sub_tsk in chain(tsk.positional_arguments, tsk.keyword_arguments.values()):
                graph[tsk].add(sub_tsk)
                build_graph(sub_tsk)

        build_graph(task)

        tasks: List[Set[Task[DependencyProvider]]] = []
        for group in topsort(graph):
            subtasks = tasks.copy()
            for task in group:
                task.dependencies = subtasks
            tasks.append(group)
        task.dependencies = tasks

        return task

    def _check_scope(self, scope: Scope):
        if scope is False:
            return
        if scope not in self._stacks:  # self._stacks is just an O(1) lookup of current scopes
            raise UnknownScopError(
                f"Scope {scope} is not known. Did you forget to enter it? Known scopes: {self._scopes}"
            )

    async def _run_task(
        self, task: Task[DependencyProviderType[DependencyType]], solved: Dict[Task[DependencyProvider], Dependency]
    ) -> None:
        scope = task.dependant.scope if task.dependant.scope is not None else self._scopes[-1]
        self._check_scope(scope)
        args = (solved[subdep] for subdep in task.positional_arguments)
        kwargs = {keyword: solved[subdep] for keyword, subdep in task.keyword_arguments.items()}
        assert task.dependant.call is not None, "Cannot run task without a call! Is the Dependant unwired?"
        call: DependencyProvider
        if is_async_gen_callable(task.dependant.call):
            call = asynccontextmanager(partial(task.dependant.call, *args, **kwargs))
        elif is_gen_callable(task.dependant.call):
            call = contextmanager(partial(task.dependant.call, *args, **kwargs))
        elif not is_coroutine_callable(task.dependant.call):
            call = partial(run_in_threadpool, partial(task.dependant.call, *args, **kwargs))
        else:
            call = partial(task.dependant.call, *args, **kwargs)
        called = call()
        if isinstance(called, AbstractContextManager):
            called = contextmanager_in_threadpool(called)
        if isinstance(called, AbstractAsyncContextManager):
            res = await self._stacks[scope].enter_async_context(called)
        else:
            res = await called
        solved[task] = res

    async def resolve(self, call: DependencyProviderType[DependencyType]) -> DependencyType:
        task = self._build_task_dag(self.get_dependant(call))
        solved: Dict[Task[DependencyProvider], Dependency] = {}
        for taskgroup in task.dependencies:
            async with anyio.create_task_group() as tg:
                for task in taskgroup:
                    tg.start_soon(self._run_task, task, solved)
        for task, value in solved.items():
            assert task.dependant.call is not None  # assigned above
            if task.dependant.scope is not False:
                scope = self._resolve_scope(task.dependant.scope)
                self._cached_values[scope][task.dependant.call] = value
        return solved[task]

    def get_dependant(
        self, call: DependencyProviderType[DependencyType]
    ) -> Dependant[DependencyProviderType[DependencyType]]:
        return Dependant(call=call)

    def get_flat_dependencies(self, call: DependencyProvider) -> Set[Dependant[DependencyProvider]]:
        task = self._build_task_dag(self.get_dependant(call))
        res = set()
        for tasks in task.dependencies:
            for tsk in tasks:
                res.add(tsk.dependant)
        return res - set([task.dependant])
