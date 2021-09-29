class DependencyInjectionException(Exception):
    pass


class WiringError(DependencyInjectionException):
    pass


class UnknownScopeError(DependencyInjectionException):
    pass


class DuplicateScopeError(DependencyInjectionException):
    pass


class DuplicatedDependencyError(DependencyInjectionException):
    pass


class CircularDependencyError(DependencyInjectionException):
    pass


class ScopeConflictError(DependencyInjectionException):
    pass


class ScopeViolationError(DependencyInjectionException):
    pass


class DependencyRegistryError(DependencyInjectionException):
    pass


class IncompatibleDependencyError(DependencyInjectionException):
    pass
