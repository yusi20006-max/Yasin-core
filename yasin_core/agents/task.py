import uuid
from typing import Any, Dict, Optional


class Task:


    def __init__(
        self,
        name: str,
        input_data: Optional[Dict[str, Any]] = None,
        task_id: Optional[str] = None
    ):

        self.id = task_id or str(uuid.uuid4())

        self.name = name

        self.input_data = input_data or {}

        self.status = "pending"

        self.result = None

        self.error = None
