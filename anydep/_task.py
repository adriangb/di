from typing import Any, Awaitable, Callable, Dict, Generic

from anydep.dependency import Dependency, DependencyType

_UNSET = object()


class Task(Generic[DependencyType]):
    def __init__(
        self,
        call: Callable[..., Awaitable[DependencyType]],
        dependencies: Dict[str, "Task[Dependency]"],
    ) -> None:
        self.call = call
        self.dependencies = dependencies
        self._result: Any = _UNSET

    async def compute(self):
        self._result = await self.call(
            **{k: v.get_result() for k, v in self.dependencies.items()}
        )

    def get_result(self):
        if self._result is _UNSET:
            raise ValueError(
                "`compute()` must be called before `get_result()`; this is likely a bug!"
            )
        return self._result
