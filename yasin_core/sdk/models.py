from typing import Dict, Any, Optional

class SDKRequest:
    """Standardized SDK Request model."""
    def __init__(self, payload: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None):
        self.payload = payload
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "payload": self.payload,
            "metadata": self.metadata,
        }


class SDKResponse:
    """Standardized SDK Response model."""
    def __init__(
        self,
        success: bool,
        data: Optional[Any] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.success = success
        self.data = data
        self.error = error
        self.metadata = metadata or {}

    def is_success(self) -> bool:
        return self.success

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
        }
