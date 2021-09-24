from __future__ import annotations

import typing

_T = typing.TypeVar("_T")
_KT = typing.TypeVar("_KT")
_VT = typing.TypeVar("_VT")


class IdentityMapping(typing.Generic[_KT, _VT]):
    def __init__(self) -> None:
        self._items: typing.Dict[int, typing.Tuple[_KT, _VT]] = {}

    def __setitem__(self, key: _KT, value: _VT) -> None:
        self._items[id(key)] = (key, value)

    def __getitem__(self, key: _KT) -> _VT:
        key_id = id(key)
        if key_id in self._items:
            return self._items[key_id][1]
        raise KeyError(key)

    def __contains__(self, key: _KT) -> bool:
        key_id = id(key)
        if key_id in self._items:
            return True
        return False

    def copy(self) -> IdentityMapping[_KT, _VT]:
        new = IdentityMapping[_KT, _VT]()
        new._items = self._items.copy()
        return new

    def __repr__(self) -> str:
        values = ", ".join([f"{repr(k)}: {repr(v)}" for k, v in self._items.values()])
        return "{" + values + "}"


class IdentitySet(typing.Generic[_T], typing.Iterable[_T]):
    """A set-like datastructure that compares items by their id instead of their hash

    This is useful for storing Dependants while ignoring their comparator semantics
    """

    def __init__(self) -> None:
        self._items: typing.Dict[int, _T] = {}

    def add(self, value: _T) -> None:
        self._items[id(value)] = value

    def __iter__(self) -> typing.Iterator[_T]:
        return iter(self._items.values())

    def __repr__(self) -> str:
        values = ", ".join([repr(v) for v in self._items.values()])
        return "{" + values + "}"
