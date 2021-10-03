from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import mutmut


def pre_mutation(context: mutmut.Context):
    context.config.test_command = "bash mutmut.sh"
