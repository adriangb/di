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
    Callable[..., Generator[DependencyType, None, None]],
    Callable[..., AsyncGenerator[DependencyType, None]],
]

Scope = Hashable

Dependency = Any

DependencyProvider = DependencyProviderType[Dependency]


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
    positional_arguments: List["Task[DependencyProvider]"] = field(default_factory=list, repr=False)
    keyword_arguments: Dict[str, "Task[DependencyProvider]"] = field(default_factory=dict, repr=False)
    dependencies: List[Set["Task[DependencyProvider]"]] = field(default_factory=list, repr=False)

    def __hash__(self) -> int:
        return id(self)
