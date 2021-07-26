import pytest

from anydep.container import Container
from anydep.exceptions import WiringError
from anydep.models import Dependant
from anydep.params import Depends


def dep() -> None:
    return


class Class:
    def __init__(self, dep: None = Depends(dep)) -> None:
        pass


def sub_dep(v0: Class, v1: "Class", v2: Class = Depends(), v3: "Class" = Depends(), v4: None = Depends(dep)) -> None:
    return


def parent(v1: None = Depends(sub_dep), /, v2: None = Depends(sub_dep), v3: None = Depends(dep)):
    return


class Cycle1:
    def __init__(self, other: "Cycle2" = Depends()) -> None:
        pass


class Cycle2:
    def __init__(self, other: "Cycle1" = Depends()) -> None:
        pass


def test_wiring_dep():
    dependant = Dependant(call=dep)
    container = Container()
    container.wire_dependant(dependant)
    assert len(dependant.positional_arguments) == 0
    assert len(dependant.keyword_arguments) == 0


def test_wiring_parent():
    dependant = Dependant(call=parent)
    container = Container()
    container.wire_dependant(dependant)
    pos = [d.call for d in dependant.positional_arguments]
    assert pos == [sub_dep]
    kws = {k: d.call for k, d in dependant.keyword_arguments.items()}
    assert kws == dict(v2=sub_dep, v3=dep)
    assert dependant.keyword_arguments["v2"] is not dependant.positional_arguments[0]


def test_wiring_sub_dep():
    dependant = Dependant(call=sub_dep)
    container = Container()
    container.wire_dependant(dependant)
    pos = [d.call for d in dependant.positional_arguments]
    assert pos == []
    kws = {k: d.call for k, d in dependant.keyword_arguments.items()}
    assert kws == dict(v0=Class, v1=Class, v2=Class, v3=Class, v4=dep)
    assert len(set(dependant.keyword_arguments.values())) == len(dependant.keyword_arguments.keys())


def test_wiring_Class():
    dependant = Dependant(call=Class)
    container = Container()
    container.wire_dependant(dependant)

    pos = [d.call for d in dependant.positional_arguments]
    assert pos == []
    kws = {k: d.call for k, d in dependant.keyword_arguments.items()}
    assert kws == dict(dep=dep)


def test_cycle_detection():
    dependant = Dependant(call=Cycle1)
    container = Container()
    with pytest.raises(WiringError):
        container.wire_dependant(dependant)
