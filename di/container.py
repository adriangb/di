from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import (
    Any,
    AsyncGenerator,
    ContextManager,
    Dict,
    List,
    NamedTuple,
    Tuple,
    cast,
)

from anyio import create_task_group

from di._concurrency import wrap_call
from di._inspect import DependencyParameter
from di._state import ContainerState
from di._task import Task
from di._topsort import topsort
from di.dependency import (
    DependantProtocol,
    Dependency,
    DependencyProvider,
    DependencyProviderType,
    DependencyType,
    Scope,
)
from di.exceptions import (
    DependencyRegistryError,
    DuplicateScopeError,
    ScopeConflictError,
    ScopeViolationError,
    UnknownScopeError,
)


class SolvedDependency(NamedTuple):
    """Representation of a fully solved dependency.

    A fully solved dependency consists of:
    - A DAG of sub-dependency paramters.
    - A topologically sorted order of execution, where each sublist represents a
    group of dependencies that can be executed in parallel.
    """

    dependency: DependantProtocol[Any]
    dag: Dict[
        DependantProtocol[Any], Dict[str, DependencyParameter[DependantProtocol[Any]]]
    ]
    topsort: List[List[DependantProtocol[Any]]]


class Container:
    def __init__(self) -> None:
        self._context = ContextVar[ContainerState]("context")
        state = ContainerState()
        # bind ourself so that dependencies can request the container
        self._context.set(state)

    @property
    def _state(self) -> ContainerState:
        return self._context.get()

    @asynccontextmanager
    async def enter_global_scope(self, scope: Scope) -> AsyncGenerator[None, None]:
        """Enter a global scope that is shared amongst threads and coroutines.

        If you enter a global scope in one thread / coroutine, it will propagate to others.
        """
        async with self._state.enter_scope(scope):
            # bind ourself so that dependencies can request the container
            if not self._state.cached_values.contains(Container):
                self._state.cached_values.set(Container, self, scope=scope)
            yield

    @asynccontextmanager
    async def enter_local_scope(self, scope: Scope) -> AsyncGenerator[None, None]:
        """Enter a local scope that is localized to the current thread or coroutine.

        If you enter a global scope in one thread / coroutine, it will NOT propagate to others.
        """
        if scope in self._state.stacks:
            raise DuplicateScopeError(f"Scope {scope} has already been entered!")
        current = self._state
        new = current.copy()
        token = self._context.set(new)
        try:
            async with new.enter_scope(scope):
                # bind ourself so that dependencies can request the container
                if not new.cached_values.contains(Container):
                    new.cached_values.set(Container, self, scope=scope)
                yield
        finally:
            self._context.reset(token)

    def bind(
        self,
        provider: DependantProtocol[DependencyType],
        dependency: DependencyProviderType[DependencyType],
        scope: Scope,
    ) -> ContextManager[None]:
        """Bind a new dependency provider for a given dependency.

        This can be used as a function (for a permanent bind, cleared when `scope` is exited)
        or as a context manager (the bind will be cleared when the context manager exits).

        Binds are only identified by the identity of the callable and do not take into account
        the scope or any other data from the dependency they are replacing.

        The `scope` parameter determines the scope for the bind itself.
        The bind will be automatically cleared when that scope is exited.
        """
        return self._state.bind(provider=provider, dependency=dependency, scope=scope)

    def solve(self, dependency: DependantProtocol[Any]) -> SolvedDependency:
        """Solve a dependency.

        This is done automatically when calling `execute`, but you can store the returned value
        from this function and call `execute_solved` instead if you know that your binds
        will not be changing between calls.
        """

        scopes: Dict[Scope, int] = {
            scope: idx
            for idx, scope in enumerate(reversed(self._state.scopes + [None]))
        }

        dag: Dict[
            DependantProtocol[Any],
            Dict[str, DependencyParameter[DependantProtocol[Any]]],
        ] = {}

        dep_registry: Dict[DependantProtocol[Any], DependantProtocol[Any]] = {}

        def check_is_inner(
            dep: DependantProtocol[Any], subdep: DependantProtocol[Any]
        ) -> None:
            if scopes[dep.scope] > scopes[subdep.scope]:
                raise ScopeViolationError(
                    f"{dep} cannot depend on {subdep} because {subdep}'s"
                    f" scope ({subdep.scope}) is narrower than {dep}'s scope ({dep.scope})"
                )

        def check_scope(dep: DependantProtocol[Any]) -> None:
            if dep.scope not in scopes:
                raise UnknownScopeError(
                    f"Dependency{dep} has an unknown scope {dep.scope}."
                    f" Did you forget to enter the {dep.scope} scope?"
                )

        def get_sub_dependencies(
            dep: DependantProtocol[Any],
        ) -> List[DependantProtocol[Any]]:
            if dep not in dag:
                check_scope(dep)
                params = dep.get_dependencies().copy()
                for keyword, param in params.items():
                    assert param.dependency.call is not None
                    check_scope(param.dependency)
                    if self._state.binds.contains(param.dependency.call):
                        params[keyword] = DependencyParameter[Any](
                            dependency=self._state.binds.get(param.dependency.call),
                            kind=param.kind,
                        )
                    check_is_inner(dep, params[keyword].dependency)
                dag[dep] = params
                dep_registry[dep] = dep
            else:
                if dep in dep_registry and dep_registry[dep] != dep:
                    raise DependencyRegistryError(
                        f"The dependencies {dep} and {dep_registry[dep]}"
                        " have the same hash but are not equal."
                        " This can be cause by using the same callable / class as a dependency in"
                        " two different scopes, which is usually a mistake"
                        " To work around this, you can subclass or wrap the function so that it"
                        " does not have the same hash/id."
                        " Alternatively, you may provide an implementation of DependencyProtocol"
                        " that uses custom __hash__ and __eq__ semantics."
                    )
            return [d.dependency for d in dag[dep].values()]

        ordered = topsort(dependency, get_sub_dependencies, hash=id)

        return SolvedDependency(dependency=dependency, dag=dag, topsort=ordered)

    def get_flat_subdependants(
        self, dependency: DependantProtocol[Any]
    ) -> List[DependantProtocol[Any]]:
        """Get an exhaustive list of all of the dependencies of this dependency,
        in no particular order.
        """
        return [
            dep
            for group in self.solve(dependency).topsort
            for dep in group
            if dependency not in group
        ]

    def _build_task(
        self,
        dependency: DependantProtocol[DependencyType],
        tasks: Dict[DependantProtocol[Any], Tuple[DependantProtocol[Any], Task[Any]]],
        state: ContainerState,
        dag: Dict[
            DependantProtocol[Any],
            Dict[str, DependencyParameter[DependantProtocol[Any]]],
        ],
    ) -> Task[DependencyType]:
        if dependency.scope is False:
            stack = state.stacks[None]
        else:
            try:
                stack = state.stacks[dependency.scope]
            except KeyError:
                raise UnknownScopeError(
                    f"The dependency {dependency} declares scope {dependency.scope}"
                    f" which is not amongst the known scopes {self._state.scopes}."
                    f" Did you forget to enter the scope {dependency.scope}?"
                )

        async def bound_call(*args: Any, **kwargs: Any) -> DependencyType:
            assert dependency.call is not None
            if dependency.shared and state.cached_values.contains(dependency.call):
                # use cached value
                res = state.cached_values.get(dependency.call)
            else:
                res = await wrap_call(dependency.call, stack=stack)(*args, **kwargs)
                if dependency.shared:
                    # caching is allowed, now that we have a value we can save it and start using the cache
                    state.cached_values.set(
                        dependency.call, res, scope=dependency.scope
                    )

            return cast(DependencyType, res)

        task_dependencies: Dict[str, DependencyParameter[Task[DependencyProvider]]] = {}

        for keyword, param in dag[dependency].items():
            task_dependencies[keyword] = DependencyParameter(
                dependency=tasks[param.dependency][1], kind=param.kind
            )

        return Task(call=bound_call, dependencies=task_dependencies)

    async def execute_solved(self, solved: SolvedDependency) -> Dependency:
        """Execute an already solved dependency."""
        # this mapping uses the hash semantics defined by the implementation of DependantProtocol
        tasks: Dict[
            DependantProtocol[Any], Tuple[DependantProtocol[Any], Task[Any]]
        ] = {}
        async with self.enter_local_scope(None):
            for group in reversed(solved.topsort):
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
                    else:
                        tasks[dep] = (
                            dep,
                            self._build_task(dep, tasks, self._state, solved.dag),
                        )
            ordered_tasks = [
                [tasks[dep][1] for dep in group] for group in solved.topsort
            ]
            tg = create_task_group()
            for task_group in reversed(ordered_tasks):
                async with tg:
                    for task in task_group:
                        tg.start_soon(task.compute)  # type: ignore

        return tasks[solved.dependency][1].get_result()

    async def execute(
        self, dependency: DependantProtocol[DependencyType]
    ) -> DependencyType:
        """Solve and execute a dependency"""
        return await self.execute_solved(self.solve(dependency))
