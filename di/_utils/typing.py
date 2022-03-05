import sys

if sys.version_info < (3, 8):  # pragma: no cover
    from typing_extensions import Protocol
else:  # pragma: no cover
    from typing import Protocol

__all__ = [
    "Protocol",
]
