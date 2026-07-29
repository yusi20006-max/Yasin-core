from typing import Any, Dict, Optional


class Task:
    def __init__(
        self,
        id: str,
        name: str,
        input_data: Dict[str, Any] = None,
        status: str = "pending",
        result: Optional[Any] = None,
        error: Optional[str] = None
    ):
        self.id = id
        self.name = name
        self.input_data = input_data if input_data is not None else {}
        self.status = status
        self.result = result
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "input_data": self.input_data,
            "status": self.status,
            "result": self.result,
            "error": self.error
        }
