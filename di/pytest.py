import functools
import inspect
from typing import Any, AsyncGenerator, Callable, Coroutine, Union

try:
    import pytest
except ImportError:
    raise ImportError(
        'The "pytest" extra is required to use di.pytest.'
        "\nYou can instal it with `pip install di[pytest]`"
    )

from di import Container, Dependant
from di.api.dependencies import DependantBase
from di.executors import SimpleAsyncExecutor

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


class TestFunctionDependant(Dependant[None]):
    def create_sub_dependant(self, param: inspect.Parameter) -> DependantBase[Any]:
        return Dependant(
            None,
            scope=self.scope,
            share=True,
            wire=True,
            autowire=True,
        )


def inject(
    func: Union[Callable[..., None], Callable[..., Coroutine[None, None, None]]]
) -> Union[Callable[..., None], Callable[..., Coroutine[None, None, None]]]:
    sig = inspect.signature(func)
    sig = sig.replace(
        parameters=[
            param
            for param in sig.parameters.values()
            if not isinstance(
                param.default, DependantBase
            )  # TODO: expand this to handle Annotated
        ]
    )

    if inspect.iscoroutinefunction(func):

        @functools.wraps(func)
        async def inner(**kwargs) -> None:
            f = functools.partial(func, **kwargs)
            dep = TestFunctionDependant(
                f, scope="function", share=False, wire=True, autowire=False
            )
            solved = _container.solve(dep)
            await _container.execute_async(solved, values=kwargs)

    else:

        @functools.wraps(func)
        def inner(**kwargs) -> None:
            f = functools.partial(func, **kwargs)
            dep = TestFunctionDependant(
                f, scope="function", share=False, wire=True, autowire=False
            )
            solved = _container.solve(dep)
            _container.execute_sync(solved)

    inner.__signature__ = sig

    return inner
