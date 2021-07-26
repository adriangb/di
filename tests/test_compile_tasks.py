from typing import Any, List

import pytest

from anydep.cache import CachePolicy
from anydep.container import Container
from anydep.models import Dependant
from anydep.params import Depends
from tests.cache_policies import CacheByCall, CacheByDepId, NoCache


def call1():
    ...


def call2(c1: None = Depends(call1)):
    ...


def call3():
    ...


def call4(c2: None = Depends(call2), /, *, c3: None = Depends(call3)):
    ...


def call5(*, c4: None = Depends(call4)):
    ...


def call6(c4: None = Depends(call4)):
    ...


def call7(c5: None = Depends(call5), c6: None = Depends(call6)):
    ...


def sort_by_call_id(calls: List[List[Any]]) -> List[List[Any]]:
    return [list(sorted(cs, key=lambda c: id(c))) for cs in calls]


d1 = Dependant(call1)
d2 = Dependant(call2)
d3 = Dependant(call3)
d4 = Dependant(call4)
d5 = Dependant(call5)
d6 = Dependant(call6)
d7 = Dependant(call7)


container = Container()
container.wire_dependant(d7)


@pytest.mark.parametrize(
    "cache_policy,expected",
    [
        (CacheByDepId(), ([d1.call, d3.call], [d2.call], [d4.call, d4.call], [d5.call, d6.call], [d7.call])),
        (CacheByCall(), ([d1.call, d3.call], [d2.call], [d4.call], [d5.call, d6.call], [d7.call])),
        (
            NoCache(),
            (
                [d1.call, d1.call, d3.call, d3.call],
                [d2.call, d2.call],
                [d4.call, d4.call],
                [d5.call, d6.call],
                [d7.call],
            ),
        ),
    ],
    ids=["cache-by-dependant-id", "cache-by-dependant-call-id", "no-cache"],
)
def test_grouping(cache_policy: CachePolicy, expected: List[List[Any]]):

    expected = sort_by_call_id(expected)

    task = container.compile_task(dependant=d7, cache_policy=cache_policy)
    got = sort_by_call_id([[t.call for t in tasks] for tasks in task.dependencies])

    assert tuple(got) == tuple(expected)
