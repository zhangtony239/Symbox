"""Stable SHA-256 identities and collision protection for SVK facts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from hashlib import sha256

from symbox.domain.models import SVK, DomainInvariantError
from symbox.domain.node_keys import NodeKey
from symbox.domain.value_codec import canonical_json_bytes

DigestFunction = Callable[[bytes], str]


def _sha256(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def svk_payload(relation: SVK) -> bytes:
    """Build the complete canonical identity payload, normalizing keyword order."""
    return canonical_json_bytes(
        {
            "subject": relation.subject,
            "verb": relation.verb,
            "args": relation.args,
            "kwargs": {name: value for name, value in relation.kwargs},
        }
    )


@dataclass(frozen=True, slots=True)
class SVKIdentity:
    """A full persistence key plus the payload used to prove its identity."""

    key: NodeKey
    digest: str
    payload: bytes = field(repr=False)


class SVKIdentityRegistry:
    """Detect impossible-but-dangerous digest collisions instead of merging facts."""

    def __init__(self, digest_function: DigestFunction = _sha256) -> None:
        self._digest_function = digest_function
        self._payloads: dict[str, bytes] = {}

    def identify(self, relation: SVK) -> SVKIdentity:
        """Create and register an identity, rejecting a conflicting prior payload."""
        payload = svk_payload(relation)
        digest = self._digest_function(payload)
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise DomainInvariantError("SVK digest function must return lowercase SHA-256 hex")
        key = NodeKey.svk(relation.subject, relation.verb, digest)
        encoded_key = key.encode()
        existing = self._payloads.get(encoded_key)
        if existing is not None and existing != payload:
            raise DomainInvariantError(f"SVK identity collision detected for {encoded_key}")
        self._payloads[encoded_key] = payload
        return SVKIdentity(key, digest, payload)


def identify_svk(relation: SVK) -> SVKIdentity:
    """Generate an identity for a standalone relation."""
    return SVKIdentityRegistry().identify(relation)
