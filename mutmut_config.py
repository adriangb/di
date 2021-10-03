from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import mutmut


excludes = (
    "@join_docstring_from",
    "@lru_cache",
)


def pre_mutation(context: mutmut.Context):
    context.config.test_command = "bash mutmut.sh"
    line: str = context.current_source_line.strip()
    if any(line.startswith(ex) for ex in excludes):
        context.skip = True
