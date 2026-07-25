from typing import Any, Dict, List, Optional, Set
from symbox.core.adj import Adj


class Subject:
    """Subject/Object entity (S/O) in Symbox."""

    def __init__(
        self,
        name: str,
        kind: str = "physical",
        attributes: Optional[Dict[str, Any]] = None,
        adj: Optional[Dict[str, Adj]] = None,
        tags: Optional[Set[str]] = None,
    ):
        self.name = name
        self.kind = kind  # "physical", "abstract", "meta"
        self._attributes: Dict[str, Any] = attributes or {}
        self.adj: Dict[str, Adj] = adj or {}
        self.tags: Set[str] = tags or set()
        self.worry_observers: List[Any] = []

        # Auto-derive tags from initial adjs
        for a in self.adj.values():
            if a.implies_tags:
                self.tags.update(a.implies_tags)

    @property
    def attributes(self) -> Dict[str, Any]:
        return self._attributes

    def set_attribute(self, key: str, value: Any) -> None:
        """Set attribute value and trigger Worry observer hooks (Section 4.4 Choice A)."""
        self._attributes[key] = value
        self.notify_worry_observers()

    def set_attributes(self, kv_pairs: Dict[str, Any]) -> None:
        """Set multiple attributes and trigger Worry observer hooks."""
        for k, v in kv_pairs.items():
            self._attributes[k] = v
        self.notify_worry_observers()

    def unset_attribute(self, key: str) -> None:
        """Unset an attribute and trigger Worry observers."""
        if key in self._attributes:
            del self._attributes[key]
            self.notify_worry_observers()

    def set_adj(self, adj_obj: Adj) -> None:
        """Set an Adjective patch and derive implied tags (Section 4.3)."""
        self.adj[adj_obj.name] = adj_obj
        if adj_obj.implies_tags:
            self.tags.update(adj_obj.implies_tags)

    def unset_adj(self, adj_name: str) -> None:
        if adj_name in self.adj:
            del self.adj[adj_name]

    def register_worry_observer(self, worry_instance: Any) -> None:
        if worry_instance not in self.worry_observers:
            self.worry_observers.append(worry_instance)

    def unregister_worry_observer(self, worry_instance: Any) -> None:
        if worry_instance in self.worry_observers:
            self.worry_observers.remove(worry_instance)

    def notify_worry_observers(self) -> None:
        for worry in self.worry_observers:
            if hasattr(worry, "evaluate_and_trigger"):
                worry.evaluate_and_trigger(self)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "attributes": self._attributes,
            "adj": {k: v.to_dict() for k, v in self.adj.items()},
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Subject":
        adjs = {k: Adj.from_dict(v) for k, v in data.get("adj", {}).items()}
        return cls(
            name=data["name"],
            kind=data.get("kind", "physical"),
            attributes=data.get("attributes", {}),
            adj=adjs,
            tags=set(data.get("tags", [])),
        )

    def __repr__(self) -> str:
        return f"<Subject {self.name} ({self.kind})>"
