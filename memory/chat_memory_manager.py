# memory/chat_memory_manager.py

from pathlib import Path
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
import uuid


class ChatMemoryManager:
    def __init__(self, base_dir: str = "memory/chat_history", session_id: Optional[str] = None):
        self.base_dir = Path(base_dir).expanduser().resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # Either use provided session_id or create a new one
        self.session_id = session_id or str(uuid.uuid4())
        self.file_path = self.base_dir / f"chat_{self.session_id}.json"

    def _now(self) -> str:
        return datetime.utcnow().isoformat() + "Z"

    def _load(self) -> Dict:
        if not self.file_path.exists():
            initial = {
                "session_id": self.session_id,
                "created_at": self._now(),
                "last_updated": self._now(),
                "turns": []
            }
            self._save(initial)
            return initial

        try:
            return json.loads(self.file_path.read_text(encoding="utf-8"))
        except Exception:
            initial = {
                "session_id": self.session_id,
                "created_at": self._now(),
                "last_updated": self._now(),
                "turns": []
            }
            self._save(initial)
            return initial

    def _save(self, data: Dict):
        self.file_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def add_turn(
        self,
        user_query: str,
        main_planner: Dict[str, Any],
        planner: Dict[str, Any],
        perception_summary: Optional[str] = None,
        plan_summary: Optional[str] = None,
        action_results: Optional[str] = None,
        final_response: str = "",
        status: str = "success",
        duration_seconds: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        data = self._load()

        turn = {
            "timestamp": self._now(),
            "user_query": user_query.strip(),
            "main_planner": main_planner.copy(),
            "planner": planner.copy(),
            "perception_summary": perception_summary.strip() if perception_summary else None,
            "plan_summary": plan_summary.strip() if plan_summary else None,
            "action_results": action_results.strip() if action_results else None,
            "final_response": final_response.strip(),
            "status": status,
            "duration_seconds": round(duration_seconds, 2) if duration_seconds is not None else None,
            "metadata": metadata or {}
        }

        data["turns"].append(turn)
        data["last_updated"] = self._now()
        self._save(data)

    def get_full_history(self) -> Dict:
        return self._load()

    def get_recent_turns(self, limit: int = 10) -> List[Dict]:
        data = self._load()
        return data.get("turns", [])[-limit:]

    def clear(self):
        """Delete this session's memory file"""
        if self.file_path.exists():
            self.file_path.unlink()

    # Optional: useful for debugging / admin
    def delete_all_sessions(self):
        for f in self.base_dir.glob("chat_*.json"):
            f.unlink()