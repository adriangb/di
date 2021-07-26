from typing import Optional, Protocol, TypeVar, Union

from anydep.models import Dependant

_T = TypeVar("_T")


class CachePolicy(Protocol):
    def get(self, dependant: Dependant, default: Optional[_T] = None) -> Union[Dependant, _T]:
        raise NotImplementedError  # pragma: no cover

    def __setitem__(self, key: Dependant, value: Dependant) -> None:
        raise NotImplementedError  # pragma: no cover
