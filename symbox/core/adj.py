from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class Adj:
    """Adjective patch stored in Subject (e.g. laptop.adj['Broken'])."""

    def __init__(
        self,
        name: str,
        value: Any = True,
        since: Optional[str] = None,
        justification: Optional[List[str]] = None,
        implies_tags: Optional[List[str]] = None,
    ):
        self.name = name
        self.value = value
        self.since = since if since is not None else datetime.now(timezone.utc).isoformat()
        self.justification = justification or []
        self.implies_tags = implies_tags or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "since": self.since,
            "justification": self.justification,
            "implies_tags": self.implies_tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Adj":
        return cls(
            name=data["name"],
            value=data.get("value", True),
            since=data.get("since"),
            justification=data.get("justification", []),
            implies_tags=data.get("implies_tags", []),
        )

    def __repr__(self) -> str:
        return f"<Adj {self.name}={self.value}>"
