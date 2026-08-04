import functools
from typing import Dict, Any, Optional

class SDKError(Exception):
    """Base exception for all Yasin-Core SDK operations."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class SDKValidationError(SDKError, ValueError):
    """Raised when request arguments or configurations fail validation."""
    pass


class SDKAuthenticationError(SDKError, PermissionError):
    """Raised when authentication fails."""
    pass


class SDKConnectionError(SDKError, ConnectionError):
    """Raised when connecting to core services/gateway fails."""
    pass


class SDKExecutionError(SDKError, RuntimeError):
    """Raised when agent or task execution fails."""
    pass


class SDKDeprecationWarning(DeprecationWarning):
    """Warning category for deprecated SDK features."""
    pass


def translate_core_errors(func):
    """Decorator to translate core internal errors into standardized SDK errors."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        from yasin_core.security import SecurityError, AccessDeniedError
        from yasin_core.security.manager import AuthenticationError as CoreAuthError
        from yasin_core.storage import StorageError
        from yasin_core.config import ConfigurationValidationError

        try:
            return func(*args, **kwargs)
        except (SecurityError, AccessDeniedError, CoreAuthError) as e:
            raise SDKAuthenticationError(f"Security/Authentication failure: {str(e)}") from e
        except ConfigurationValidationError as e:
            raise SDKValidationError(f"Configuration validation failure: {str(e)}") from e
        except StorageError as e:
            raise SDKConnectionError(f"Storage backend failure: {str(e)}") from e
        except ValueError as e:
            raise SDKValidationError(str(e)) from e
        except Exception as e:
            if "not found" in str(e).lower() or "missing" in str(e).lower():
                raise SDKValidationError(str(e)) from e
            raise SDKExecutionError(f"SDK execution failed: {str(e)}") from e
    return wrapper
