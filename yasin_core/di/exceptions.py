class DIError(Exception):
    """Base exception for all Dependency Injection (DI) errors."""
    pass


class DependencyResolutionError(DIError):
    """Raised when dependency resolution fails (e.g. missing or unresolvable dependencies)."""
    pass


class CircularDependencyError(DependencyResolutionError):
    """Raised when a circular dependency loop is detected during resolution."""
    pass
