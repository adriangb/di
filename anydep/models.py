import inspect as stdlib_inspect
from dataclasses import dataclass, field
from typing import (
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Dict,
    Generator,
    Generic,
    Hashable,
    List,
    Optional,
    Set,
    TypeVar,
    Union,
)

DependencyType = TypeVar("DependencyType")

DependencyProviderType = Union[
    Callable[..., DependencyType],
    Callable[..., Awaitable[DependencyType]],
    Generator[DependencyType, None, None],
    AsyncGenerator[DependencyType, None],
]

Scope = Hashable

DependencyProvider = Union[
    Callable[..., Any],
    Callable[..., Awaitable[Any]],
    Generator[Any, None, None],
    AsyncGenerator[Any, None],
]

Dependency = Any


@dataclass
class Parameter:
    positional: bool
    name: str
    annotation: Any
    default: Any
    empty: Any = stdlib_inspect.Parameter.empty


@dataclass
class Dependant(Generic[DependencyType]):
    call: Optional[DependencyProviderType] = None
    scope: Optional[Scope] = None
    parameters: Union[List[Parameter], None] = None

    def __hash__(self) -> int:
        return id(self)


@dataclass
class Task(Generic[DependencyType]):
    dependant: Dependant[DependencyProviderType]
    positional_arguments: List["Task[DependencyProvider]"] = field(default_factory=list, repr=False)  # type: ignore
    keyword_arguments: Dict[str, "Task[DependencyProvider]"] = field(default_factory=dict, repr=False)  # type: ignore
    dependencies: List[Set["Task[DependencyProvider]"]] = field(default_factory=list, repr=False)  # type: ignore

    def __hash__(self) -> int:
        return id(self)
