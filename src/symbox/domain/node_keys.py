"""Canonical, reversible truth-node identifiers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import quote, unquote_to_bytes

from symbox.domain.models import DomainInvariantError


class NodeNamespace(StrEnum):
    """Namespaces that prevent facts of different kinds from colliding."""

    SUBJECT = "Subject"
    ADJ = "Adj"
    SVK = "SVK"
    WORRY = "Worry"
    TAG = "Tag"


_ARITY = {
    NodeNamespace.SUBJECT: 1,
    NodeNamespace.ADJ: 2,
    NodeNamespace.SVK: 3,
    NodeNamespace.WORRY: 1,
    NodeNamespace.TAG: 2,
}


def _encode_component(component: str) -> str:
    if not component:
        raise DomainInvariantError("node key components must not be empty")
    return quote(component, safe="-._~", encoding="utf-8", errors="strict")


def _decode_component(encoded: str) -> str:
    if not encoded:
        raise DomainInvariantError("node key components must not be empty")
    try:
        decoded = unquote_to_bytes(encoded).decode("utf-8", errors="strict")
    except UnicodeError as error:
        raise DomainInvariantError("node key contains invalid UTF-8 escaping") from error
    if _encode_component(decoded) != encoded:
        raise DomainInvariantError("node key component is not canonically escaped")
    return decoded


@dataclass(frozen=True, slots=True)
class NodeKey:
    """A parsed node namespace and its unescaped identity components."""

    namespace: NodeNamespace
    components: tuple[str, ...]

    def __post_init__(self) -> None:
        expected = _ARITY[self.namespace]
        if len(self.components) != expected:
            raise DomainInvariantError(
                f"{self.namespace.value} node key requires {expected} components"
            )
        for component in self.components:
            _encode_component(component)

    def encode(self) -> str:
        """Encode the key into its canonical persistence form."""
        encoded = (_encode_component(component) for component in self.components)
        return ":".join((self.namespace.value, *encoded))

    @classmethod
    def parse(cls, value: str) -> NodeKey:
        """Parse and validate a canonical persistence key."""
        parts = value.split(":")
        try:
            namespace = NodeNamespace(parts[0])
        except (ValueError, IndexError) as error:
            raise DomainInvariantError("unknown node key namespace") from error
        expected = _ARITY[namespace]
        if len(parts) != expected + 1:
            raise DomainInvariantError(
                f"{namespace.value} node key requires {expected} components"
            )
        return cls(namespace, tuple(_decode_component(part) for part in parts[1:]))

    @classmethod
    def subject(cls, subject: str) -> NodeKey:
        return cls(NodeNamespace.SUBJECT, (subject,))

    @classmethod
    def adj(cls, subject: str, key: str) -> NodeKey:
        return cls(NodeNamespace.ADJ, (subject, key))

    @classmethod
    def svk(cls, subject: str, verb: str, digest: str) -> NodeKey:
        return cls(NodeNamespace.SVK, (subject, verb, digest))

    @classmethod
    def worry(cls, worry: str) -> NodeKey:
        return cls(NodeNamespace.WORRY, (worry,))

    @classmethod
    def tag(cls, subject: str, tag: str) -> NodeKey:
        return cls(NodeNamespace.TAG, (subject, tag))
