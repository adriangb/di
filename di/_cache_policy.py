import typing
from collections import deque
from enum import Enum, auto

from di._identity_containers import IdentityMapping
from di.dependency import DependantProtocol


class CachePolicy(Enum):
    """Value cache policies:
    - use: this dependency and all of it's subdependencies are cached, use the cached value for this dependency
    - clear: this dependency or one of it's subdependencies were re-computed, this and all parents must be re-computed and then set their policy back to use
    - forbid: this dependency or one of it's subdependencies do not allow caching (e.g. scope=False), all parents MUST also forbid caching
    """

    use = auto()
    invalidate = auto()
    forbid = auto()


def invalidate_caches(
    dependency: DependantProtocol[typing.Any],
    policies: IdentityMapping[DependantProtocol[typing.Any], CachePolicy],
) -> None:
    """BFS propagation of CachePolicy.ignore up to parents"""
    q: typing.Deque[DependantProtocol[typing.Any]] = deque([dependency])
    while q:
        cur = q.popleft()
        if cur not in policies:
            if cur.scope is False:
                policies[cur] = CachePolicy.forbid
            else:
                policies[cur] = CachePolicy.invalidate
        else:
            if policies[cur] in (CachePolicy.forbid, CachePolicy.invalidate):
                return
        policies[cur] = CachePolicy.invalidate
        q.extend(cur.parents)


def forbid_caching(
    dependency: DependantProtocol[typing.Any],
    policies: IdentityMapping[DependantProtocol[typing.Any], CachePolicy],
) -> None:
    """BFS propagation of CachePolicy.forbid up to parents"""
    q: typing.Deque[DependantProtocol[typing.Any]] = deque([dependency])
    while q:
        cur = q.popleft()
        if cur not in policies:
            if cur.scope is False:
                policies[cur] = CachePolicy.forbid
            else:
                policies[cur] = CachePolicy.invalidate
        else:
            if policies[cur] == CachePolicy.forbid:
                return
        policies[cur] = CachePolicy.forbid
        q.extend(cur.parents)
