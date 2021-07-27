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
from typing import Any, AsyncGenerator, Callable, Dict, List, Set, Tuple, Union

import anyio

from anydep.concurrency import contextmanager_in_threadpool, run_in_threadpool
from anydep.exceptions import DuplicateScopeError, UnknownScopError, WiringError
from anydep.inspect import (
    Parameter,
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
        self._bound_providers: Dict[DependencyProvider, DependencyProvider] = {}
        self._bound_dependants: Dict[Dependant[DependencyProvider], Dependant[DependencyProvider]] = {}
        self._cached_values: Dict[DependencyProvider, Dependency] = {}
        self._stacks: Dict[Scope, AsyncExitStack] = {}
        self._scopes: List[Scope] = []
        self._infered_dependants: Dict[Tuple[DependencyProvider, str], Dependant[DependencyProvider]] = {}

    @asynccontextmanager
    async def enter_scope(self, scope: Scope) -> AsyncGenerator[None, None]:
        if scope in self._stacks:
            raise DuplicateScopeError(f"Scope {scope} has already been entered!")
        async with AsyncExitStack() as stack:
            self._scopes.append(scope)
            self._stacks[scope] = stack
            bound_providers = self._bound_providers
            bound_dependants = self._bound_dependants
            cached_values = self._cached_values
            self._bound_providers = bound_providers.copy()
            self._bound_dependants = bound_dependants.copy()
            self._cached_values = cached_values.copy()
            try:
                yield
            finally:
                self._stacks.pop(scope)
                self._bound_providers = bound_providers
                self._bound_dependants = bound_dependants
                self._cached_values = cached_values
                self._scopes.pop()

    def _get_scope_index(self, scope: Scope) -> int:
        self._check_scope(scope)
        return self._scopes.index(scope)

    def _retrieve_cached_value(
        self, dependant: Dependant[DependencyProviderType]
    ) -> Task[Callable[[], DependencyType]]:
        def retrieve():
            return self._cached_values[dependant.call]

        new_dependant: Dependant[DependencyProviderType] = Dependant(call=retrieve, parameters=[])
        return Task(dependant=new_dependant, positional_arguments=[], keyword_arguments={}, dependencies=[])

    def _build_task(
        self,
        dependant: Dependant[DependencyProviderType],
        *,
        seen: Set[Dependant],
        cache: Dict[DependencyProvider, Dict[Scope, Task]],
    ) -> Task[DependencyProviderType]:
        if dependant in seen:
            raise WiringError("Circular dependencies detected")
        seen = seen | set([dependant])
        if dependant.parameters is None:
            dependant.parameters = get_parameters(dependant.call)  # type: ignore
            assert dependant.parameters is not None
        task: Task[DependencyProviderType] = Task(dependant=dependant)
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
            if sub_dependant in self._bound_dependants:
                sub_dependant = self._bound_dependants[sub_dependant]
                subtask = self._build_task(sub_dependant, seen=seen, cache=cache)  # always rebuild
            else:
                if sub_dependant.call in self._bound_providers and sub_dependant.scope is not False:
                    sub_dependant = self._bound_providers[sub_dependant.call]
                subtask: Union[None, Task[DependencyProvider]] = None
                scope: Scope
                if sub_dependant.scope is False:
                    scope = False
                elif sub_dependant.scope is None:
                    scope = self._scopes[-1]  # current scope
                else:
                    scope = sub_dependant.scope
                if scope is not False and sub_dependant.call in self._cached_values:
                    subtask = self._retrieve_cached_value(sub_dependant)
                else:
                    if scope is not False and sub_dependant.call in cache:
                        for cache_scope, cached in cache[sub_dependant.call].items():
                            if self._get_scope_index(cache_scope) <= self._get_scope_index(scope):
                                # e.g. cache_scope == "app" and scope == "request"
                                subtask = cached
                                break
                if subtask is None:
                    subtask = self._build_task(sub_dependant, seen=seen, cache=cache)
                    if scope is not False:
                        cache[sub_dependant.call][scope] = subtask
            if parameter.positional:
                task.positional_arguments.append(subtask)
            else:
                task.keyword_arguments[parameter.name] = subtask
        return task

    def compile_task_graph(self, dependant: Dependant[DependencyProviderType]) -> Task[DependencyProviderType]:
        if dependant.call is None:
            raise WiringError("Top level dependant must have a `call`")

        task = self._build_task(dependant, seen=set(), cache=defaultdict(dict))

        graph: Dict[Task, Set[Task]] = {}

        def build_graph(tsk: Task) -> None:
            if tsk in graph:
                return
            graph[tsk] = set()
            for sub_tsk in chain(tsk.positional_arguments, tsk.keyword_arguments.values()):
                graph[tsk].add(sub_tsk)
                build_graph(sub_tsk)

        build_graph(task)

        tasks = []
        for group in topsort(graph):
            subtasks = tasks.copy()
            for task in group:
                task.dependencies = subtasks
            tasks.append(group)
        task.dependencies = tasks

        return task

    def _check_scope(self, scope: Scope):
        if scope not in self._stacks:  # self._stacks is just an O(1) lookup of current scopes
            raise UnknownScopError(
                f"Scope {scope} is not known. Did you forget to enter it? Known scopes: {self._scopes}"
            )

    async def _run_task(
        self, task: Task[DependencyProviderType], solved: Dict[Task[DependencyProviderType], DependencyType]
    ) -> None:
        scope = task.dependant.scope if task.dependant.scope is not None else self._scopes[-1]
        self._check_scope(scope)
        args = (solved[subdep] for subdep in task.positional_arguments)
        kwargs = {keyword: solved[subdep] for keyword, subdep in task.keyword_arguments.items()}
        if is_async_gen_callable(task.dependant.call):  # type: ignore
            call = asynccontextmanager(partial(task.dependant.call, *args, **kwargs))  # type: ignore
        elif is_gen_callable(task.dependant.call):  # type: ignore
            call = contextmanager(partial(task.dependant.call, *args, **kwargs))  # type: ignore
        elif not is_coroutine_callable(task.dependant.call):  # type: ignore
            call = partial(run_in_threadpool, partial(task.dependant.call, *args, **kwargs))  # type: ignore
        else:
            call = partial(task.dependant.call, *args, **kwargs)  # type: ignore
        called = call()
        if isinstance(called, AbstractContextManager):
            called = contextmanager_in_threadpool(called)
        if isinstance(called, AbstractAsyncContextManager):
            res = await self._stacks[scope].enter_async_context(called)
        else:
            res = await called
        solved[task] = res

    async def resolve(self, call: DependencyProvider) -> DependencyType:
        task = self.compile_task_graph(self.get_dependant(call))
        solved: Dict[Task[DependencyProvider], Dependency] = {}
        for taskgroup in task.dependencies:
            async with anyio.create_task_group() as tg:
                for task in taskgroup:
                    tg.start_soon(self._run_task, task, solved)
        for task, value in solved.items():
            self._cached_values[task.dependant.call] = value
        return solved[task]

    def get_dependant(self, call: DependencyProvider) -> Dependant[DependencyProvider]:
        return Dependant(call=call)

    def get_flat_dependencies(self, call: DependencyProvider) -> Set[Dependant[Any]]:
        task = self.compile_task_graph(self.get_dependant(call))
        res = set()
        assert task.dependencies is not None  # for mypy
        for tasks in task.dependencies:
            for tsk in tasks:
                res.add(tsk.dependant)
        return res - set([task.dependant])
