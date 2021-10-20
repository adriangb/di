from typing import Any, AsyncGenerator, Callable, Coroutine, Generator, TypeVar, Union

DependencyType = TypeVar("DependencyType", covariant=True)

CallableProvider = Callable[..., DependencyType]
CoroutineProvider = Callable[..., Coroutine[Any, Any, DependencyType]]
GeneratorProvider = Callable[..., Generator[DependencyType, None, None]]
AsyncGeneratorProvider = Callable[..., AsyncGenerator[DependencyType, None]]

DependencyProviderType = Union[
    CallableProvider[DependencyType],
    CoroutineProvider[DependencyType],
    GeneratorProvider[DependencyType],
    AsyncGeneratorProvider[DependencyType],
]


DependencyProvider = Union[
    AsyncGeneratorProvider[Any],
    CoroutineProvider[Any],
    GeneratorProvider[Any],
    CallableProvider[Any],
]
