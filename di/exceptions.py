class DependencyInjectionException(Exception):
    """Base exception for this library"""

    pass


class WiringError(DependencyInjectionException):
    """Raised when wiring (introspection into types) failed"""

    pass


class UnknownScopeError(DependencyInjectionException):
    """Raised when a dependency to be executed has an unknown Scope"""

    pass


class DuplicateScopeError(DependencyInjectionException):
    """Raised when enter_scope() is called with an existing scope"""

    pass


class DependencyCycleError(DependencyInjectionException):
    """Raised when a dependency cycle is detected"""

    pass


class ScopeViolationError(DependencyInjectionException):
    """Raised when Scope layering is violated.
    Using pytests' Scopes as an example, if A has "session" Scope and B has "function" Scope,
    A cannot depend on B (in fact, pytest will also throw an error).
    """

    pass


class SolvingError(DependencyInjectionException):
    """Raised when there is an issue solving, for example if a dependency appears twice with different scopes"""

    pass


class IncompatibleDependencyError(DependencyInjectionException):
    """Raised when an async context manager dependency is executed in a sync Scope"""

    pass
