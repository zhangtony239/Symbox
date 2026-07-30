from typing import Any, Callable, Dict, Optional
from symbox.core.subject import Subject


class Worry(Subject):
    """Worry object (Meta Subject) bridging value-domain to symbol-domain.

    Mechanically an ECA rule (spec v0.4 §3.1): attribute set = Event,
    check() = Condition, node flip triggering propagation = Action.

    Polarity convention (v0.4 §3.1): check()/condition returns
    **True = state normal / validation passed**, **False = triggers
    contradiction propagation**. The LTMS node mirrors this:
    True = healthy, False = contradiction.
    """

    def __init__(
        self,
        name: str,
        watch_subject_name: Optional[str] = None,
        condition_func: Optional[Callable[[Subject], bool]] = None,
        func_name: Optional[str] = None,
        module_path: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(name=name, kind="meta", attributes=attributes)
        self.watch_subject_name = watch_subject_name
        self.condition_func = condition_func
        self.func_name = func_name
        self.module_path = module_path
        self.is_active: bool = False
        self.engine_callback: Optional[Callable[["Worry", bool], None]] = None

    def check(self, subject_attrs: Dict[str, Any], object_attrs: Dict[str, Any]) -> bool:
        """Convention check signature def check(self, s, o) -> bool.

        v0.4 polarity (spec §3.1): returns True if the state is normal /
        validation passes, False if the health condition is violated
        (triggers contradiction propagation).
        """
        if self.condition_func is not None:
            # Create transient subject wrapper if needed
            transient_s = Subject(name=self.watch_subject_name or "s", attributes=subject_attrs)
            return bool(self.condition_func(transient_s))
        return True

    def evaluate(self, target_subject: Subject) -> bool:
        """Evaluate health condition on target subject.

        Returns True if the worry is triggered (active), i.e. the health
        condition is NOT met (check()/condition returned False, spec §3.1).
        Supports both plain condition_func and bound Worry subclasses
        overriding check(s, o) (spec §2.5).
        """
        try:
            if self.condition_func is not None:
                healthy = bool(self.condition_func(target_subject))
            else:
                healthy = bool(self.check(target_subject.attributes, {}))
            # v0.4 polarity: True = normal, False = triggered
            return not healthy
        except Exception:
            return False

    def evaluate_and_trigger(self, target_subject: Subject) -> None:
        """Observer hook invoked on target subject attribute modification (Section 4.4 Choice A)."""
        triggered = self.evaluate(target_subject)
        if triggered != self.is_active:
            self.is_active = triggered
            if self.engine_callback is not None:
                self.engine_callback(self, triggered)

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "watch_subject_name": self.watch_subject_name,
            "func_name": self.func_name,
            "module_path": self.module_path,
            "is_active": self.is_active,
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Worry":
        obj = cls(
            name=data["name"],
            watch_subject_name=data.get("watch_subject_name"),
            func_name=data.get("func_name"),
            module_path=data.get("module_path"),
            attributes=data.get("attributes", {}),
        )
        obj.is_active = data.get("is_active", False)
        return obj


class Attention(Subject):
    """Attention object (Meta Subject) modeling metacognitive context focus."""

    def __init__(
        self,
        name: str = "main_attention",
        focus_target: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        attrs = attributes or {}
        if focus_target:
            attrs["focus_target"] = focus_target
        super().__init__(name=name, kind="meta", attributes=attrs)

    @property
    def focus_target(self) -> Optional[str]:
        return self._attributes.get("focus_target")

    @focus_target.setter
    def focus_target(self, target_name: Optional[str]) -> None:
        self.set_attribute("focus_target", target_name)
