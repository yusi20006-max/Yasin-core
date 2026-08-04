class CompatibilityError(Exception):
    """Base exception for all compatibility and migration issues."""
    pass


class VersionMismatchError(CompatibilityError):
    """Raised when there is an incompatible version mismatch or negotiation fails."""
    pass


class APICompatibilityError(CompatibilityError):
    """Raised when an API compatibility check fails."""
    pass


class MigrationError(CompatibilityError):
    """Raised when data or schema migration fails."""
    pass


class EcosystemValidationError(CompatibilityError):
    """Raised when ecosystem compatibility validation fails."""
    pass
