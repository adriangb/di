import inspect
from contextlib import (
    AbstractAsyncContextManager,
    AbstractContextManager,
    asynccontextmanager,
    contextmanager,
)
from functools import partial
from typing import Dict, Optional, Set, get_type_hints

import anyio

from anydep.cache import CachePolicy
from anydep.concurrency import contextmanager_in_threadpool, run_in_threadpool
from anydep.exceptions import WiringError
from anydep.inspect import is_async_gen_callable, is_coroutine_callable, is_gen_callable
from anydep.lifespan import LifespanPolicy
from anydep.models import Dependant, Dependency, DependencyProvider, Task
from anydep.topsort import topsort
from anydep.utils import call_from_annotation

SolvedDependant = Dict[Dependant, Set[Dependant]]


async def execute_task(*, solved: Dict[Task, Dependency], task: Task, lifespan: LifespanPolicy) -> Dependency:
    args = (solved[subtask] for subtask in task.positional_arguments)
    kwargs = {keyword: solved[subtask] for keyword, subtask in task.keyword_arguments.items()}
    if is_async_gen_callable(task.call):  # type: ignore
        call = asynccontextmanager(partial(task.call, *args, **kwargs))  # type: ignore
    elif is_gen_callable(task.call):  # type: ignore
        call = contextmanager(partial(task.call, *args, **kwargs))  # type: ignore
    elif not is_coroutine_callable(task.call):  # type: ignore
        call = partial(run_in_threadpool, partial(task.call, *args, **kwargs))  # type: ignore
    else:
        call = partial(task.call, *args, **kwargs)  # type: ignore
    called = call()
    if isinstance(called, AbstractContextManager):
        called = contextmanager_in_threadpool(called)
    if isinstance(called, AbstractAsyncContextManager):
        res = await lifespan.bind_context(policy=task.lifespan_policy, context_manager=called)  # type: ignore
    else:
        res = await called
    solved[task] = res
    return res


class Container:
    def _wire_dependant(self, dependant: Dependant, *, seen: Set[Dependant]):
        if dependant.wired:
            return
        if dependant in seen:
            raise WiringError("Circular dependencies detected")
        params = inspect.signature(dependant.call).parameters  # type: ignore
        if inspect.isclass(dependant.call):
            types_from = dependant.call.__init__   # type: ignore
        else:
            types_from = dependant.call
        annotations = get_type_hints(types_from)  # type: ignore
        for param_name, parameter in params.items():
            annotation = annotations.get(param_name, None)
            if isinstance(parameter.default, Dependant):
                sub_dependant = parameter.default
                if sub_dependant.call is None:
                    sub_dependant.call = call_from_annotation(parameter, annotation)
            elif parameter.default is parameter.empty:
                sub_dependant = Dependant(call=call_from_annotation(parameter, annotation))
            else:
                continue  # use default value
            self._wire_dependant(
                sub_dependant,
                seen=seen
                | {
                    dependant,
                },
            )
            if parameter.kind == parameter.POSITIONAL_ONLY:
                dependant.positional_arguments.append(sub_dependant)
            else:
                dependant.keyword_arguments[param_name] = sub_dependant
        dependant.wired = True

    def wire_dependant(self, dependant: Dependant) -> None:
        if dependant.call is None:
            raise WiringError("Top level dependant must have a `call`")
        return self._wire_dependant(dependant, seen=set())

    def compile_task(self, dependant: Dependant[DependencyProvider], *, cache_policy: CachePolicy) -> Task[DependencyProvider]:
        self.wire_dependant(dependant)

        graph: Dict[Task, Set[Task]] = {}

        def build_graph(dep: Dependant) -> Task:
            cached = cache_policy.get(dep, None)
            if cached is None:
                task = Task(call=dep.call)
                cache_policy[dep] = task
            else:
                task = cached
            graph[task] = set()
            for pos_dep in dep.positional_arguments:
                parent_task = build_graph(pos_dep)
                graph[task].add(parent_task)
                task.positional_arguments.append(parent_task)
            for kw, kw_dep in dep.keyword_arguments.items():
                parent_task = build_graph(kw_dep)
                graph[task].add(parent_task)
                task.keyword_arguments[kw] = parent_task
            return task

        root = build_graph(dependant)

        seen = []
        for group in topsort(graph):
            seen.append(group)
            for task in group:
                task.dependencies.extend(seen)
        root.dependencies = seen

        return root

    def get_flat_dependencies(self, dependant: Dependant) -> Set[Dependant]:
        self.wire_dependant(dependant)

        seen = set()

        def recurse(dep: Dependant):
            if dep in seen:
                return
            seen.add(dep)
            for subdep in dep.dependencies:
                recurse(subdep)

        recurse(dependant)

        return seen - {
            dependant,
        }

    async def execute(
        self, *, task: Task[DependencyProvider], solved: Optional[Dict[Task, Dependency]] = None, lifespan: Optional[LifespanPolicy] = None
    ) -> Dependency:
        solved = solved or {}
        for subtask_group in task.dependencies:
            async with anyio.create_task_group() as tg:
                for subtask in subtask_group:
                    if subtask in solved:
                        continue
                    target = partial(execute_task, solved=solved, lifespan=lifespan, task=subtask)
                    tg.start_soon(target)
        return solved[task]
