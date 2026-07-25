import importlib.util
import os
import sys
from typing import Any, Callable, Optional


def load_func_from_file(file_path: str, func_name: str) -> Callable[..., Any]:
    """Dynamically load function or class `func_name` from file path `file_path`."""
    abs_path = os.path.abspath(file_path)
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"Source file not found: {file_path}")

    module_name = f"symbox_dynamic_{os.path.splitext(os.path.basename(file_path))[0]}"
    spec = importlib.util.spec_from_file_location(module_name, abs_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load spec from {file_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    if not hasattr(module, func_name):
        raise AttributeError(f"Function/Class '{func_name}' not found in '{file_path}'")

    return getattr(module, func_name)
