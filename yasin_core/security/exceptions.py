class SecurityError(Exception):
    """Base exception for all security-related errors in the Yasin ecosystem."""
    pass


class AccessDeniedError(SecurityError):
    """Raised when a subject does not have the required permissions or roles to perform an action."""
    pass


class AuthenticationError(SecurityError):
    """Raised when authentication (e.g., API Key, token, or credentials) fails or is invalid."""
    pass


class PermissionValidationError(SecurityError):
    """Raised when a permission structure or role definition is malformed or invalid."""
    pass
