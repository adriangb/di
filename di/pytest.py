from typing import AsyncGenerator, Callable, Coroutine, Optional, Union, overload

try:
    import pytest
except ImportError:
    raise ImportError(
        'The "pytest" extra is required to use di.pytest.'
        "\nYou can instal it with `pip install di[pytest]`"
    )

from di import Container, Dependant
from di._utils.inspect import is_async_gen_callable, is_coroutine_callable
from di.api.providers import (
    AsyncGeneratorProvider,
    CallableProvider,
    CoroutineProvider,
    DependencyProviderType,
    DependencyType,
    GeneratorProvider,
)
from di.api.scopes import Scope
from di.executors import SimpleAsyncExecutor


@overload
def Depends(
    call: Optional[AsyncGeneratorProvider[DependencyType]] = None,
    *,
    scope: Scope = "function",
    share: bool = True,
    wire: bool = True,
    autowire: bool = True,
    sync_to_thread: bool = False,
) -> DependencyType:
    ...


@overload
def Depends(
    call: Optional[CoroutineProvider[DependencyType]] = None,
    *,
    scope: Scope = "function",
    share: bool = True,
    wire: bool = True,
    autowire: bool = True,
    sync_to_thread: bool = False,
) -> DependencyType:
    ...


@overload
def Depends(
    call: Optional[GeneratorProvider[DependencyType]] = None,
    *,
    scope: Scope = "function",
    share: bool = True,
    wire: bool = True,
    autowire: bool = True,
    sync_to_thread: bool = False,
) -> DependencyType:
    ...


@overload
def Depends(
    call: Optional[CallableProvider[DependencyType]] = None,
    *,
    scope: Scope = "function",
    share: bool = True,
    wire: bool = True,
    autowire: bool = True,
    sync_to_thread: bool = False,
) -> DependencyType:
    ...


def Depends(
    call: Optional[DependencyProviderType[DependencyType]] = None,
    *,
    scope: Scope = "function",
    share: bool = True,
    wire: bool = True,
    autowire: bool = True,
    sync_to_thread: bool = False,
) -> DependencyType:
    return Dependant(  # type: ignore[return-value]
        call=call,
        scope=scope,
        share=share,
        wire=wire,
        autowire=autowire,
        sync_to_thread=sync_to_thread,
    )


_container = Container(execution_scope="function", executor=SimpleAsyncExecutor())
_container.bind(
    Dependant(
        lambda: _container,
        scope="session",
        autowire=False,
        wire=False,
    ),
    Container,
)


@pytest.fixture(scope="session")
def container() -> Container:
    return _container


@pytest.fixture(scope="session", autouse=True)
async def enter_session_scope(container: Container) -> AsyncGenerator[None, None]:
    async with container.enter_scope("session"):
        yield


@pytest.fixture(scope="module", autouse=True)
async def enter_module_scope(container: Container) -> AsyncGenerator[None, None]:
    async with container.enter_scope("module"):
        yield


@pytest.fixture(scope="function", autouse=True)
async def enter_function_scope(container: Container) -> AsyncGenerator[None, None]:
    async with container.enter_scope("function"):
        yield


def inject(
    func: Union[Callable[..., None], Callable[..., Coroutine[None, None, None]]]
) -> Union[Callable[..., None], Callable[..., Coroutine[None, None, None]]]:
    dep = Dependant(
        func,
        share=False,
        scope="function",
        wire=True,
        autowire=True,
    )

    # TODO: manipulate signature to preserve compatibility w/ Pytest fixtures?
    # This would entail removing parameters that di will inject from the signature
    # while preserving those that it doesn't recognize

    if is_async_gen_callable(func) or is_coroutine_callable(func):

        async def inner_async() -> None:
            await _container.execute_async(_container.solve(dep))

        return inner_async
    else:

        def inner_sync() -> None:
            _container.execute_sync(_container.solve(dep))

        return inner_sync
