from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Any, AsyncGenerator, ContextManager, Dict, List, Tuple, cast

from anyio import create_task_group

from anydep._concurrency import wrap_call
from anydep._state import ContainerState
from anydep._task import Task
from anydep.dependency import (
    DependantProtocol,
    DependencyProvider,
    DependencyProviderType,
    DependencyType,
    Scope,
)
from anydep.exceptions import DuplicateScopeError, ScopeConflictError, UnknownScopeError
from anydep.topsort import topsort


class Container:
    def __init__(self) -> None:
        self._context = ContextVar[ContainerState]("context")
        state = ContainerState()
        # bind ourself so that dependencies can request the container
        self._context.set(state)

    @property
    def state(self) -> ContainerState:
        return self._context.get()

    @asynccontextmanager
    async def enter_global_scope(self, scope: Scope) -> AsyncGenerator[None, None]:
        async with self.state.enter_scope(scope):
            # bind ourself so that dependencies can request the container
            try:
                self.state.cached_values.get(Container)
            except KeyError:
                self.state.cached_values.set(Container, self, scope=scope)
            yield

    @asynccontextmanager
    async def enter_local_scope(self, scope: Scope) -> AsyncGenerator[None, None]:
        if scope in self.state.stacks:
            raise DuplicateScopeError(f"Scope {scope} has already been entered!")
        current = self.state
        new = current.copy()
        token = self._context.set(new)
        try:
            async with self.state.enter_scope(scope):
                # bind ourself so that dependencies can request the container
                try:
                    self.state.cached_values.get(Container)
                except KeyError:
                    self.state.cached_values.set(Container, self, scope=scope)
                yield
        finally:
            self._context.reset(token)

    def bind(
        self, provider: DependencyProvider, dependency: DependencyProvider, scope: Scope
    ) -> ContextManager[None]:
        return self.state.bind(provider=provider, dependency=dependency, scope=scope)

    def resolve_dependency(
        self, dependency: DependantProtocol[Any]
    ) -> List[List[DependantProtocol[Any]]]:
        if dependency.solved_dependencies is None:
            # use id() as a hash, NOT the hash defined by DependantProtocol
            # so that we can build a static graph based on code alone
            dependency.solved_dependencies = topsort(
                dependency, lambda dep: set(dep.dependencies.values()), hash=id
            )
        return dependency.solved_dependencies

    def get_flat_dependencies(
        self, dependency: DependantProtocol[Any]
    ) -> List[DependantProtocol[Any]]:
        return [dep for group in self.resolve_dependency(dependency) for dep in group]

    def _build_task(
        self,
        dependency: DependantProtocol[DependencyType],
        tasks: Dict[DependantProtocol[Any], Tuple[DependantProtocol[Any], Task[Any]]],
        state: ContainerState,
    ) -> Task[DependencyType]:

        try:
            stack = state.stacks[dependency.scope]
        except KeyError:
            raise UnknownScopeError(
                f"The dependency {dependency} declares scope {dependency.scope}"
                f" which is not amongst the known scopes {self.state.stacks.keys()}"
            )

        async def call(**kwargs: Any) -> DependencyType:
            assert dependency.call is not None
            call = dependency.call
            if dependency.scope is not False and state.cached_values.contains(call):
                # use cached value
                res = state.cached_values.get(call)
            else:
                if state.binds.contains(call):
                    # use bind
                    call = cast(
                        DependencyProviderType[DependencyType], state.binds.get(call)
                    )
                res = await wrap_call(call, stack=stack)(**kwargs)
                state.cached_values.set(call, res, scope=dependency.scope)

            return cast(DependencyType, res)

        return Task(
            call=call,
            dependencies={
                k: tasks[dep][1] for k, dep in dependency.dependencies.items()
            },
        )

    async def execute(
        self, dependency: DependantProtocol[DependencyType]
    ) -> DependencyType:
        self.resolve_dependency(dependency)
        assert dependency.solved_dependencies is not None
        tasks: Dict[
            DependantProtocol[Any], Tuple[DependantProtocol[Any], Task[Any]]
        ] = {}  # here we use the hash semantics defined by DependantProtocol
        async with self.enter_local_scope(None):
            for group in reversed(dependency.solved_dependencies):
                for dep in group:
                    if dep in tasks:
                        task_dep, task = tasks[dep]
                        if (
                            dep.scope is not False
                            and task_dep.scope is not False
                            and dep.scope != task_dep.scope
                        ):
                            raise ScopeConflictError(
                                f"The dependency {dep.call} is declared with two different scopes:"
                                f" {dep.scope} and {task_dep.scope}"
                            )
                        continue
                    tasks[dep] = (dep, self._build_task(dep, tasks, self.state))
            ordered_tasks = [
                [tasks[dep][1] for dep in group]
                for group in dependency.solved_dependencies
            ]
            for task_group in reversed(ordered_tasks):
                async with create_task_group() as tg:
                    for task in task_group:
                        tg.start_soon(task.compute)  # type: ignore

        return tasks[dependency][1].get_result()
