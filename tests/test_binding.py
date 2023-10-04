import sys
from abc import abstractmethod
from typing import List, TypeVar

import pytest

from di import Container, bind_by_type
from di.dependent import Dependent, Marker
from di.executors import SyncExecutor
from di.typing import Annotated

if sys.version_info < (3, 8):  # pragma: no cover
    from typing_extensions import Protocol
else:  # pragma: no cover
    from typing import Protocol


class Request:
    def __init__(self, value: int = 0) -> None:
        self.value = value


def endpoint(r: Request) -> int:
    return r.value


def test_bind():
    container = Container()

    class Test:
        def __init__(self, v: int = 1) -> None:
            self.v = v

    dependent = Dependent(Test)

    with container.enter_scope(None) as state:
        res = container.solve(dependent, scopes=[None]).execute_sync(
            executor=SyncExecutor(),
            state=state,
        )
        assert res.v == 1
    with container.bind(bind_by_type(Dependent(lambda: Test(2)), Test)):
        with container.enter_scope(None) as state:
            res = container.solve(dependent, scopes=[None]).execute_sync(
                executor=SyncExecutor(),
                state=state,
            )
            assert res.v == 2
    with container.enter_scope(None) as state:
        res = container.solve(dependent, scopes=[None]).execute_sync(
            executor=SyncExecutor(),
            state=state,
        )
        assert res.v == 1


T_co = TypeVar("T_co", covariant=True)


def test_bind_generic():
    container = Container()
    executor = SyncExecutor()
    expected = 100

    class GetterInterface(Protocol[T_co]):
        @abstractmethod
        def get(self) -> T_co:
            ...

    class GetterIntImpl(GetterInterface[int]):
        def __init__(self, v: int) -> None:
            self.v = v

        def get(self) -> int:
            return self.v

    def factory() -> GetterIntImpl:
        return GetterIntImpl(expected)

    hook = bind_by_type(
        Dependent(factory),
        GetterInterface[int],
    )
    container.bind(hook)

    # ===========================================
    # clean `_tp_cache`
    from typing import _cleanups as cache_cleanups  # type: ignore[attr-defined]

    for cache_cleanup in cache_cleanups:
        cache_cleanup()
    # ===========================================

    class IntService:
        """Declared after binding and cache clearing."""

        def __init__(self, getter: GetterInterface[int]) -> None:
            self.getter = getter

    scopes = [None]
    flat_dependent = Dependent(GetterInterface[int])
    wired_dependent = Dependent(IntService)
    with container.enter_scope(None) as state:
        flat_solved = container.solve(flat_dependent, scopes)
        wired_solved = container.solve(wired_dependent, scopes)
        flat = flat_solved.execute_sync(executor, state)
        wired = wired_solved.execute_sync(executor, state)

        assert flat.get() == wired.getter.get() == expected


def test_bind_transitive_dependency_results_skips_subdpendencies():
    """If we bind a transitive dependency none of it's sub-dependencies should be executed
    since they are no longer required.
    """

    def raises_exception() -> None:
        raise ValueError

    class Transitive:
        def __init__(self, _: Annotated[None, Marker(raises_exception)]) -> None:
            ...

    def dep(t: Annotated[None, Marker(Transitive)]) -> None:
        ...

    container = Container()
    with container.enter_scope(None) as state:
        # we get an error from raises_exception
        with pytest.raises(ValueError):
            container.solve(Dependent(dep), scopes=[None]).execute_sync(
                executor=SyncExecutor(),
                state=state,
            )

    # we bind a non-error provider and re-execute, now raises_exception
    # should not execute at all

    def not_error() -> None:
        ...

    with container.bind(bind_by_type(Dependent(not_error), Transitive)):
        with container.enter_scope(None) as state:
            container.solve(Dependent(dep), scopes=[None]).execute_sync(
                executor=SyncExecutor(),
                state=state,
            )
    # and this reverts when the bind exits
    with container.enter_scope(None) as state:
        with pytest.raises(ValueError):
            container.solve(Dependent(dep), scopes=[None]).execute_sync(
                executor=SyncExecutor(),
                state=state,
            )


def test_bind_with_dependencies():
    """When we bind a new dependent, we resolve it's dependencies as well"""

    def return_one() -> int:
        return 1

    def return_two(one: Annotated[int, Marker(return_one)]) -> int:
        return one + 1

    def return_three(one: Annotated[int, Marker(return_one)]) -> int:
        return one + 2

    def return_four(two: Annotated[int, Marker(return_two)]) -> int:
        return two + 2

    container = Container()
    with container.enter_scope(None) as state:
        assert (
            container.solve(Dependent(return_four), scopes=[None]).execute_sync(
                executor=SyncExecutor(),
                state=state,
            )
        ) == 4
    container.bind(
        lambda param, dependent: None
        if dependent.call is not return_two
        else Dependent(return_three)
    )
    with container.enter_scope(None) as state:
        val = container.solve(Dependent(return_four), scopes=[None]).execute_sync(
            executor=SyncExecutor(),
            state=state,
        )
    assert val == 5


def test_bind_covariant() -> None:
    class Animal:
        pass

    class Dog(Animal):
        pass

    container = Container()
    container.bind(
        bind_by_type(
            Dependent(lambda: Dog()),
            Animal,
            covariant=True,
        )
    )

    # include a generic to make sure we are safe with
    # isisntance checks and MRO checks
    def dep(animal: Animal, generic: Annotated[List[int], Marker(list)]) -> Animal:
        return animal

    solved = container.solve(Dependent(dep), scopes=[None])

    with container.enter_scope(None) as state:
        instance = solved.execute_sync(executor=SyncExecutor(), state=state)

    assert isinstance(instance, Dog)
