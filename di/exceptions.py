class WiringError(Exception):
    pass


class UnknownScopeError(Exception):
    pass


class DuplicateScopeError(Exception):
    pass


class DuplicatedDependencyError(Exception):
    pass


class CircularDependencyError(Exception):
    pass


class ScopeConflictError(Exception):
    pass


class ScopeViolationError(Exception):
    pass


class DependencyRegistryError(Exception):
    pass
