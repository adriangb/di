import sys
from typing import Optional

if sys.version_info < (3, 9):
    from typing_extensions import Annotated
else:
    from typing import Annotated

from di import Dependant, Depends


def test_wiring_based_from_annotation() -> None:
    def g() -> int:
        return 1

    class G:
        pass

    def f(
        a: Annotated[int, Depends(g)],
        b: Annotated[G, "foo bar baz!"],
        c: Annotated[Optional[int], Depends(g)] = None,
    ) -> None:
        pass

    dep = Dependant(f)
    subdeps = dep.get_dependencies()
    assert [d.dependency.call for d in subdeps] == [g, G, g]
