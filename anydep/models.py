from typing import (
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Dict,
    Generator,
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


class Dependant:
    def __init__(
        self,
        call: Optional[DependencyProvider] = None,
        *,
        lifespan_policy: Optional[Any] = None,
        cache_policy: Optional[Any] = None
    ) -> None:
        self.call = call
        self.lifespan_policy = lifespan_policy
        self.cache_policy = cache_policy
        self.wired: bool = False
        self.positional_arguments: List[Dependant] = []
        self.keyword_arguments: Dict[str, Dependant] = {}

    @property
    def dependencies(self) -> Set["Dependant"]:
        return set((*self.positional_arguments, *self.keyword_arguments.values()))

    def __hash__(self) -> int:
        return id(self.call)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Dependant):
            return False
        return self.call == other.call
