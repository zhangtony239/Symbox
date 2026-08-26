"""Keep the hexagonal dependency direction explicit and testable."""

from __future__ import annotations

import ast
from pathlib import Path

PACKAGE_ROOT = Path(__file__).parents[2] / "src" / "symbox"

# A layer may import itself and any layer listed here.  In particular, domain is
# pure and no inner layer may depend on the CLI adapter.
ALLOWED_DEPENDENCIES = {
    "domain": {"domain"},
    "kernel": {"domain", "kernel"},
    "application": {"application", "domain", "kernel"},
    "persistence": {"domain", "kernel", "persistence"},
    "integrations": {"domain", "kernel", "integrations"},
    "cli": {"application", "cli", "domain"},
}


def _symbox_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            parts = name.split(".")
            if len(parts) >= 2 and parts[0] == "symbox":
                imports.add(parts[1])
    return imports


def test_layers_exist_and_only_import_allowed_dependencies() -> None:
    for layer, allowed in ALLOWED_DEPENDENCIES.items():
        layer_root = PACKAGE_ROOT / layer
        assert layer_root.is_dir(), f"missing architecture layer: {layer}"
        for module in layer_root.rglob("*.py"):
            disallowed = _symbox_imports(module) - allowed
            assert not disallowed, f"{module} imports forbidden layers: {sorted(disallowed)}"
