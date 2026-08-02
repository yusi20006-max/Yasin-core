from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

class ServiceState(Enum):
    UNINITIALIZED = "UNINITIALIZED"
    INITIALIZING = "INITIALIZING"
    ACTIVE = "ACTIVE"
    FAILED = "FAILED"
    STOPPED = "STOPPED"


@dataclass
class ServiceMetadata:
    name: str
    version: str = "1.0.0"
    description: str = ""
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
