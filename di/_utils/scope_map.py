from __future__ import annotations

from typing import Dict, Hashable, List, Mapping, TypeVar, Union

from di.api.scopes import Scope
from di.exceptions import DuplicateScopeError, UnknownScopeError

KT = TypeVar("KT", bound=Hashable)
VT = TypeVar("VT")
T = TypeVar("T")


UNSET = object()


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

    def get_from_scope(self, key: KT, *, scope: Scope, default: T) -> Union[VT, T]:
        try:
            return self[scope].get(key, default)
        except KeyError:
            raise UnknownScopeError(str(scope)) from None

    def set(self, key: KT, value: VT, *, scope: Scope) -> None:
        self[scope][key] = value

    def add_scope(self, scope: Scope) -> None:
        if scope in self:
            raise DuplicateScopeError(f"The scope {scope} already exists!")
        self[scope] = {}  # type: ignore

    def __repr__(self) -> str:  # pragma: no cover, used only for debugging
        values: List[str] = []
        for scope, mapping in self.items():
            for k, v in mapping.items():
                values.append(f'{repr(k)}: {repr(v)} @ scope="{scope}"')
        return "{" + ", ".join(values) + "}"
