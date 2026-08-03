from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from .models import APIRequest
from .errors import APIError, APIErrorCode


class BaseAuthenticator(ABC):
    """
    Abstract Base Class for API Gateway Authenticators.
    """
    @abstractmethod
    def authenticate(self, request: APIRequest) -> Optional[Dict[str, Any]]:
        """
        Authenticate the given APIRequest.
        Should return a dict of identity/credential details on success,
        or raise an APIError if authentication fails.
        """
        pass


class APIKeyAuthenticator(BaseAuthenticator):
    """
    Default API Key/Token based authenticator.
    Checks headers for 'authorization' or 'x-api-key'.
    """
    def __init__(
        self,
        allowed_keys: Optional[List[str]] = None,
        required: bool = False,
    ):
        self.allowed_keys = allowed_keys or []
        self.required = required

    def authenticate(self, request: APIRequest) -> Optional[Dict[str, Any]]:
        if not self.required and not self.allowed_keys:
            # Not required and no keys configured -> allow all
            return {"identity": "anonymous", "authenticated": False}

        # Look up key/token in headers
        auth_header = request.headers.get("authorization", "")
        api_key = request.headers.get("x-api-key", "")

        token = ""
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()
        elif auth_header:
            token = auth_header.strip()
        else:
            token = api_key.strip()

        if not token:
            if self.required:
                raise APIError(
                    message="Authentication token is missing.",
                    code=APIErrorCode.UNAUTHORIZED,
                    status_code=401,
                )
            return {"identity": "anonymous", "authenticated": False}

        if self.allowed_keys and token not in self.allowed_keys:
            raise APIError(
                message="Invalid authentication token.",
                code=APIErrorCode.FORBIDDEN,
                status_code=403,
            )

        return {"identity": "authenticated_client", "token": token, "authenticated": True}
