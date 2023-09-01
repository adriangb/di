from typing import Dict, Hashable, List, TypeVar, Union

from di.api.scopes import Scope
from di.exceptions import DuplicateScopeError, UnknownScopeError

KT = TypeVar("KT", bound=Hashable)
VT = TypeVar("VT")
T = TypeVar("T")


class ScopeMap(Dict[Scope, Dict[KT, VT]]):
    """Mapping-like structure to hold cached values.

    The important aspect of this is that we may have thousands of dependencies, but generally only a couple (<10) scopes.
    So this is designed to operate in ~ O(S) time, where S is the number of scopes.
    Imporantly, when we enter or exit a scope (which can happen very frequently, e.g. requests in a web framework),
    no iteration is required: we can simply pop all keys in that scope.
    """

    def get_key(self, key: KT, *, scope: Scope, default: T) -> Union[VT, T]:
        for current_scope, scopemap in self.items():
            if key in scopemap:
                return scopemap[key]
            if current_scope == scope:
                break
        return default

    def set(self, key: KT, value: VT, *, scope: Scope) -> None:
        try:
            self[scope][key] = value
        except KeyError:
            raise UnknownScopeError(
                f"The scope {scope} was not found. Did you forget to enter it?"
            )

    def add_scope(self, scope: Scope) -> None:
        if scope in self:
            raise DuplicateScopeError(f"The scope {scope} already exists!")
        self[scope] = {}  # type: ignore

    def __repr__(self) -> str:  # pragma: no cover, used only for debugging
        values: List[str] = []
        for scope, mapping in self.items():
            for k, v in mapping.items():
                values.append(f'{k!r}: {v!r} @ scope="{scope}"')
        return "{" + ", ".join(values) + "}"
