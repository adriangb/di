import sys
from typing import Callable, cast

vesion: Callable[[str], str]
if sys.version_info < (3, 8):
    from importlib_metadata import PackageNotFoundError, version

    version = cast(Callable[[str], str], version)
else:
    from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("di")
except PackageNotFoundError:
    __version__ = "0.0.0"


from di.container import Container  # noqa: E402
from di.dependant import Dependant  # noqa: E402
from di.params import Depends  # noqa: E402

__all__ = ("Container", "Dependant", "Depends")
