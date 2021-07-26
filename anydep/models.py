from typing import (
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Dict,
    Generator,
    Generic,
    List,
    Optional,
    Set,
    TypeVar,
    Union,
)

Dependency = TypeVar("Dependency")

DependencyProvider = Union[
    Callable[..., Dependency],
    Callable[..., Awaitable[Dependency]],
    Generator[Dependency, None, None],
    AsyncGenerator[Dependency, None],
]


class Dependant(Generic[Dependency]):

    def __init__(
        self,
        call: Optional[DependencyProvider] = None,
        *,
        lifespan_policy: Optional[Any] = None,
        cache_policy: Optional[Any] = None,
    ) -> None:
        self.call = call
        self.lifespan_policy = lifespan_policy
        self.cache_policy = cache_policy
        self.wired: bool = False
        self.positional_arguments: List[Dependant] = []
        self.keyword_arguments: Dict[str, Dependant] = {}

    @property
    def dependencies(self) -> List["Dependant"]:
        return [*self.positional_arguments, *self.keyword_arguments.values()]

    def __repr__(self) -> str:
        call = f"call={self.call}"
        lifespan_policy = "" if self.lifespan_policy is None else f", lifespan_policy={self.lifespan_policy}"
        cache_policy = "" if self.cache_policy is None else f", cache_policy={self.cache_policy}"
        return f"{self.__class__.__name__}({call}{lifespan_policy}{cache_policy})"


class Task(Generic[Dependency]):

    def __init__(
        self,
        call: Optional[DependencyProvider] = None,
        *,
        lifespan_policy: Optional[Any] = None,
    ) -> None:
        self.call = call
        self.lifespan_policy = lifespan_policy
        self.wired: bool = False
        self.positional_arguments: List[Task] = []
        self.keyword_arguments: Dict[str, Task] = {}
        self.dependencies: List[Set[Task]] = []

    def __repr__(self) -> str:
        call = f"call={self.call}"
        lifespan_policy = "" if self.lifespan_policy is None else f", lifespan_policy={self.lifespan_policy}"
        return f"{self.__class__.__name__}({call}{lifespan_policy})"
