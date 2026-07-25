from typing import Any, Callable, Dict, List, Optional, Set


class Verb:
    """Verb predicate (V) in Symbox."""

    def __init__(
        self,
        name: str,
        domain: Optional[Set[str]] = None,
        range_: Optional[Set[str]] = None,
        check_func: Optional[Callable[[Dict[str, Any], Dict[str, Any]], bool]] = None,
        func_name: Optional[str] = None,
        module_path: Optional[str] = None,
        is_verb: bool = True,
        veto_rules: Optional[List[str]] = None,
        modify_rules: Optional[Dict[str, str]] = None,
    ):
        self.name = name
        self.domain: Set[str] = domain if domain is not None else set()
        self.range: Set[str] = range_ if range_ is not None else set()
        self.check_func = check_func
        self.func_name = func_name
        self.module_path = module_path
        self.is_verb = is_verb
        self.veto_rules: List[str] = veto_rules or []
        self.modify_rules: Dict[str, str] = modify_rules or {}

    def validate_kinds(self, subject_kind: str, object_kind: str) -> tuple[bool, str]:
        """Validate domain/range kinds to prevent meaningless combinations."""
        if self.domain and subject_kind not in self.domain:
            return False, f"Subject kind '{subject_kind}' not in Verb '{self.name}' domain {self.domain}"
        if self.range and object_kind not in self.range:
            return False, f"Object kind '{object_kind}' not in Verb '{self.name}' range {self.range}"
        return True, ""

    def check(self, subject_attrs: Dict[str, Any], object_attrs: Dict[str, Any]) -> bool:
        if self.check_func is not None:
            return self.check_func(subject_attrs, object_attrs)
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "domain": list(self.domain),
            "range": list(self.range),
            "func_name": self.func_name,
            "module_path": self.module_path,
            "is_verb": self.is_verb,
            "veto_rules": self.veto_rules,
            "modify_rules": self.modify_rules,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Verb":
        return cls(
            name=data["name"],
            domain=set(data.get("domain", [])),
            range_=set(data.get("range", [])),
            func_name=data.get("func_name"),
            module_path=data.get("module_path"),
            is_verb=data.get("is_verb", True),
            veto_rules=data.get("veto_rules", []),
            modify_rules=data.get("modify_rules", {}),
        )

    def __repr__(self) -> str:
        return f"<Verb {self.name}>"
