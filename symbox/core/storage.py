import json
import os
from typing import Any, Dict


class StorageManager:
    """JSON storage manager for Symbox engine state."""

    def __init__(self, state_file: str = "./.sbox/state.json"):
        self.state_file = os.path.abspath(state_file)

    def save(self, data: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load(self) -> Dict[str, Any]:
        if not os.path.exists(self.state_file):
            return {"subjects": {}, "verbs": {}, "worries": {}, "svo": []}
        with open(self.state_file, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return {"subjects": {}, "verbs": {}, "worries": {}, "svo": []}
