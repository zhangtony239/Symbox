"""Application ports for resolving persistent callable references."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from symbox.domain.models import BindingRef

BoundCallable = Callable[..., Any]


@dataclass(frozen=True, slots=True)
class LoadedBinding:
    """A verified runtime callable and its persistence-safe reference."""

    reference: BindingRef
    callable: BoundCallable
    signature: inspect.Signature


class BindingLoader(Protocol):
    """Resolve a trusted project-local callable behind an infrastructure adapter."""

    def load(
        self,
        project_root: Path,
        source_path: str,
        qualified_name: str,
        *,
        is_verb: bool = False,
    ) -> LoadedBinding:
        """Load, verify, and digest one persistent callable reference."""
        ...
