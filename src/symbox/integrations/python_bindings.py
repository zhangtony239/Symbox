"""Trusted project-local Python callable loading and signature validation."""

from __future__ import annotations

import importlib.util
import inspect
import sys
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from types import ModuleType
from typing import Any

from symbox.domain.models import BindingRef, DomainInvariantError

BoundCallable = Callable[..., Any]


class BindingLoadError(DomainInvariantError):
    """Raised when a persistent callable reference cannot be safely resolved."""


@dataclass(frozen=True, slots=True)
class LoadedBinding:
    """A verified runtime callable and its persistence-safe reference."""

    reference: BindingRef
    callable: BoundCallable
    signature: inspect.Signature


def load_binding(
    project_root: Path,
    source_path: str,
    qualified_name: str,
    *,
    is_verb: bool = False,
) -> LoadedBinding:
    """Load and validate one trusted callable from a regular project-local source file."""
    root = project_root.resolve()
    if not root.is_dir():
        raise BindingLoadError(f"project root is not a directory: {root}")
    placeholder = BindingRef(source_path, qualified_name, "0" * 64, is_verb=is_verb)
    candidate_path = root / placeholder.source_path
    if candidate_path.is_symlink():
        raise BindingLoadError("binding source must be a regular non-symlink Python file")
    resolved = candidate_path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise BindingLoadError("binding source resolves outside the project root") from error
    if not resolved.is_file() or resolved.is_symlink():
        raise BindingLoadError("binding source must be a regular non-symlink Python file")

    try:
        content = resolved.read_bytes()
    except OSError as error:
        message = f"unable to read binding source: {placeholder.source_path}"
        raise BindingLoadError(message) from error
    digest = sha256(content).hexdigest()
    reference = BindingRef(
        placeholder.source_path,
        placeholder.qualified_name,
        digest,
        is_verb=is_verb,
    )
    module = _load_module(resolved, digest)
    target: Any = module
    for component in reference.qualified_name.split("."):
        try:
            target = getattr(target, component)
        except AttributeError as error:
            raise BindingLoadError(
                f"binding name not found: {reference.qualified_name}"
            ) from error
    if not callable(target):
        raise BindingLoadError(f"binding target is not callable: {reference.qualified_name}")
    signature = _validate_signature(target, reference.qualified_name)
    return LoadedBinding(reference, target, signature)


def _load_module(path: Path, digest: str) -> ModuleType:
    module_name = f"_symbox_binding_{digest}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise BindingLoadError(f"unable to create module spec for binding source: {path.name}")
    module = importlib.util.module_from_spec(spec)
    previous = sys.modules.get(module_name)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as error:
        raise BindingLoadError(f"binding module execution failed: {path.name}: {error}") from error
    finally:
        if previous is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous
    return module


def _validate_signature(target: BoundCallable, qualified_name: str) -> inspect.Signature:
    try:
        signature = inspect.signature(target)
    except (TypeError, ValueError) as error:
        raise BindingLoadError(f"binding has no inspectable signature: {qualified_name}") from error
    parameters = tuple(signature.parameters.values())
    if not parameters:
        raise BindingLoadError("binding must accept Subject as its explicit first parameter")
    first = parameters[0]
    if first.kind not in {
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    }:
        raise BindingLoadError("binding first parameter must accept Subject positionally")
    try:
        signature.bind(object())
    except TypeError:
        # More required arguments are allowed and supplied by now/Worry invocation.
        try:
            signature.bind_partial(object())
        except TypeError as error:
            raise BindingLoadError("binding cannot accept Subject as first parameter") from error
    return signature
