from enum import Enum
from typing import Dict, Any, Optional

class APIErrorCode(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


class APIError(Exception):
    """
    Standard Exception representing an API error that can be caught and
    formatted into an APIResponse.
    """
    def __init__(
        self,
        message: str,
        code: APIErrorCode = APIErrorCode.INTERNAL_SERVER_ERROR,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """
        Return structured representation of the error.
        """
        err = {
            "code": self.code.value if hasattr(self.code, "value") else str(self.code),
            "message": self.message,
        }
        if self.details:
            err["details"] = self.details
        return err
