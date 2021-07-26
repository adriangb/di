from typing import Dict, Optional, TypeVar, Union

from anydep.cache import CachePolicy
from anydep.models import Dependant, Task

T = TypeVar("T")


class CacheByDepId(Dict[Dependant, Task], CachePolicy):
    pass


class CacheByCall(dict, CachePolicy):
    def get(self, key: Dependant, default: Optional[T] = None) -> Union[Task, T]:
        return super().get(key.call, default)

    def __setitem__(self, key: Dependant, value: Dependant) -> None:
        super().__setitem__(key.call, value)


class NoCache(CachePolicy):
    def get(self, key: Dependant, default: Optional[T] = None) -> Union[Task, T]:
        return default

    def __setitem__(self, key: Dependant, value: Dependant) -> None:
        return
