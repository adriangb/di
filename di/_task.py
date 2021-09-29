from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Generic, List, cast

from di._inspect import DependencyParameter
from di.dependency import Dependency, DependencyType

_UNSET = object()


class Task(Generic[DependencyType]):
    def __init__(
        self,
        dependencies: Dict[str, DependencyParameter[Task[Dependency]]],
    ) -> None:
        self.dependencies = dependencies
        self._result: Any = _UNSET

    def get_result(self) -> DependencyType:
        if self._result is _UNSET:
            raise ValueError(
                "`compute()` must be called before `get_result()`; this is likely a bug!"
            )
        return cast(DependencyType, self._result)


class AsyncTask(Task[DependencyType]):
    def __init__(
        self,
        call: Callable[..., Awaitable[DependencyType]],
        dependencies: Dict[str, DependencyParameter[Task[Dependency]]],
    ) -> None:
        self.call = call
        super().__init__(dependencies)

    async def compute(self) -> None:
        positional: List[Task[Dependency]] = []
        keyword: Dict[str, Task[Dependency]] = {}
        for param_name, dep in self.dependencies.items():
            if dep.parameter.kind is dep.parameter.kind.POSITIONAL_ONLY:
                positional.append(dep.dependency.get_result())
            else:
                keyword[param_name] = dep.dependency.get_result()
        self._result = await self.call(*positional, **keyword)


class SyncTask(Task[DependencyType]):
    def __init__(
        self,
        call: Callable[..., DependencyType],
        dependencies: Dict[str, DependencyParameter[Task[Dependency]]],
    ) -> None:
        self.call = call
        super().__init__(dependencies)

    def compute(self) -> None:
        positional: List[Task[Dependency]] = []
        keyword: Dict[str, Task[Dependency]] = {}
        for param_name, dep in self.dependencies.items():
            if dep.parameter.kind is dep.parameter.kind.POSITIONAL_ONLY:
                positional.append(dep.dependency.get_result())
            else:
                keyword[param_name] = dep.dependency.get_result()
        self._result = self.call(*positional, **keyword)
