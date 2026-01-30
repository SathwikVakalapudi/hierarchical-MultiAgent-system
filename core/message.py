from dataclasses import dataclass
from typing import Dict, Any

@dataclass(frozen=True)
class Message:
    type: str
    payload: Dict[str, Any]
