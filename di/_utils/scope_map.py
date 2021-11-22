from __future__ import annotations

from typing import Dict, Hashable, List, Mapping, TypeVar

from di.api.scopes import Scope
from di.exceptions import DuplicateScopeError

KT = TypeVar("KT", bound=Hashable)
VT = TypeVar("VT")


class ScopeMap(Dict[Scope, Dict[KT, VT]]):
    """Mapping-like structure to hold cached values.

    The important aspect of this is that we may have thousands of dependencies, but generally only a couple (<10) scopes.
    So this is designed to operate in ~ O(S) time, where S is the number of scopes.
    Imporantly, when we enter or exit a scope (which can happen very frequently, e.g. requests in a web framework),
    no iteration is required: we can simply pop all keys in that scope.
    """

    def to_mapping(self) -> Mapping[KT, VT]:
        ms = iter(self.values())
        res = next(ms).copy()
        for m in ms:
            res.update(m)
        return res

    def set(self, key: KT, value: VT, *, scope: Scope) -> None:
        self[scope][key] = value

    def add_scope(self, scope: Scope) -> None:
        if scope in self:
            raise DuplicateScopeError(f"The scope {scope} already exists!")
        self[scope] = {}

    def __repr__(self) -> str:  # pragma: no cover, used only for debugging
        values: List[str] = []
        for scope, mapping in self.items():
            for k, v in mapping.items():
                values.append(f'{repr(k)}: {repr(v)} @ scope="{scope}"')
        return "{" + ", ".join(values) + "}"
