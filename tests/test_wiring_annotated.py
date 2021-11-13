import sys

if sys.version_info < (3, 9):
    from typing_extensions import Annotated
else:
    from typing import Annotated

from di import Dependant, Depends


def test_wiring_based_from_annotation() -> None:
    def g() -> int:
        return 1

    def f(a: Annotated[int, Depends(g)]) -> None:
        pass

    dep = Dependant(f)
    subdeps = dep.get_dependencies()
    assert [d.dependency.call for d in subdeps] == [g]
