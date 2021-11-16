from typing import Any, Callable, TypeVar

T = TypeVar("T")


def join_docstring_from(original: Any) -> Callable[[T], T]:
    def wrapper(target: T) -> T:
        target.__doc__ = (getattr(original, "__doc__", None) or "") + (
            getattr(target, "__doc__", None) or ""
        )
        return target

    return wrapper
