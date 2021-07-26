from typing import Optional, Protocol, TypeVar, Union

from anydep.models import Dependant, Task

_T = TypeVar("_T")


class CachePolicy(Protocol):
    def get(self, key: Dependant, default: Optional[_T] = None, /) -> Union[Task, _T]:
        raise NotImplementedError  # pragma: no cover

    def __setitem__(self, key: Dependant, value: Dependant) -> None:
        raise NotImplementedError  # pragma: no cover
