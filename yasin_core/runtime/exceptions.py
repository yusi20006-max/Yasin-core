class ServiceError(Exception):
    """Base exception for all service-related errors."""
    pass

class DuplicateServiceError(ServiceError):
    """Raised when registering a service name that is already registered."""
    pass

class ServiceNotFoundError(ServiceError):
    """Raised when looking up or removing a service that does not exist."""
    pass

class DependencyError(ServiceError):
    """Base exception for dependency-related errors."""
    pass

class MissingDependencyError(DependencyError):
    """Raised when a service is registered or initialized but is missing its dependencies."""
    pass

class CircularDependencyError(DependencyError):
    """Raised when a circular dependency is detected among services."""
    pass
