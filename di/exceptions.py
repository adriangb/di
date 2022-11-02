from typing import Any, List

from di.api.dependencies import DependentBase


class DependencyInjectionException(Exception):
    """Base exception for this library"""

    pass


class WiringError(DependencyInjectionException):
    """Raised when wiring (introspection into types) failed"""

    def __init__(self, msg: str, path: List[DependentBase[Any]]) -> None:
        super().__init__(msg)
        self.path = path


class UnknownScopeError(DependencyInjectionException):
    """Raised when a dependency to be executed has an unknown Scope"""


class DuplicateScopeError(DependencyInjectionException):
    """Raised when enter_scope() is called with an existing scope"""


class DependencyCycleError(DependencyInjectionException):
    """Raised when a dependency cycle is detected"""

    def __init__(self, msg: str, path: List[DependentBase[Any]]) -> None:
        super().__init__(msg)
        self.path = path


class ScopeViolationError(DependencyInjectionException):
    """Raised when Scope layering is violated.
    Using pytests' Scopes as an example, if A has "session" Scope and B has "function" Scope,
    A cannot depend on B (in fact, pytest will also throw an error).
    """


class SolvingError(DependencyInjectionException):
    """Raised when there is an issue solving, for example if a dependency appears twice with different scopes"""

    def __init__(self, msg: str, path: List[DependentBase[Any]]) -> None:
        super().__init__(msg)
        self.path = path


class IncompatibleDependencyError(DependencyInjectionException):
    """Raised when an async context manager dependency is executed in a sync Scope"""
