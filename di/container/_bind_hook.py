import inspect
import sys
from typing import Any, Optional

if sys.version_info < (3, 8):
    from typing_extensions import Protocol
else:
    from typing import Protocol


from di.api.dependencies import DependantBase


class BindHook(Protocol):
    def __call__(
        self, param: Optional[inspect.Parameter], dependant: DependantBase[Any]
    ) -> Optional[DependantBase[Any]]:
        ...
