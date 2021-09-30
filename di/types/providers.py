from typing import Any, AsyncGenerator, Callable, Coroutine, Generator, TypeVar, Union

DependencyType = TypeVar("DependencyType")

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


Dependency = Any

DependencyProvider = Union[
    AsyncGeneratorProvider[Dependency],
    CoroutineProvider[Dependency],
    GeneratorProvider[Dependency],
    CallableProvider[Dependency],
]
