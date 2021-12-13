from typing import Any, AsyncGenerator, Callable, Coroutine, Generator, TypeVar, Union

T = TypeVar("T")

CallableProvider = Callable[..., T]
CoroutineProvider = Callable[..., Coroutine[Any, Any, T]]
GeneratorProvider = Callable[..., Generator[T, None, None]]
AsyncGeneratorProvider = Callable[..., AsyncGenerator[T, None]]

DependencyProviderType = Union[
    CallableProvider[T],
    CoroutineProvider[T],
    GeneratorProvider[T],
    AsyncGeneratorProvider[T],
]


DependencyProvider = Union[
    AsyncGeneratorProvider[Any],
    CoroutineProvider[Any],
    GeneratorProvider[Any],
    CallableProvider[Any],
]
