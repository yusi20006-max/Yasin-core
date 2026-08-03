from typing import Dict, Any, List, Optional

class APIRequest:
    """
    Standard API Request model for the Yasin-Core public API gateway layer.
    """
    def __init__(
        self,
        method: str,
        path: str,
        headers: Optional[Dict[str, str]] = None,
        query_params: Optional[Dict[str, Any]] = None,
        body: Optional[Any] = None,
    ):
        self.method = method.upper()
        self.path = path
        if isinstance(headers, dict):
            self.headers = {k.lower(): v for k, v in headers.items()}
        else:
            self.headers = headers if headers is not None else {}
        self.query_params = query_params or {}
        self.body = body

    def validate(self) -> None:
        """
        Validate the request structure.
        Raises ValueError if basic requirements are not met.
        """
        if not self.method:
            raise ValueError("Request method is required.")
        if not self.path:
            raise ValueError("Request path is required.")
        if not isinstance(self.headers, dict):
            raise ValueError("Headers must be a dictionary.")
        if not isinstance(self.query_params, dict):
            raise ValueError("Query parameters must be a dictionary.")


class APIResponse:
    """
    Standard API Response model for the Yasin-Core public API gateway layer.
    """
    def __init__(
        self,
        status_code: int,
        data: Optional[Any] = None,
        errors: Optional[List[Dict[str, Any]]] = None,
        version: str = "v1",
    ):
        self.status_code = status_code
        self.data = data
        self.errors = errors or []
        self.version = version

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize response to standard JSON-compatible dictionary.
        """
        return {
            "status_code": self.status_code,
            "data": self.data,
            "errors": self.errors,
            "version": self.version,
        }
