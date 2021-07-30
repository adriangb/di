class WiringError(Exception):
    pass


class UnknownScopeError(Exception):
    pass


class DuplicateScopeError(ValueError):
    pass


class DuplicatedDependencyError(RuntimeError):
    pass
