from __future__ import annotations

import importlib.util
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any, cast


class TargetLoadError(RuntimeError):
    pass


def load_module(path: Path) -> ModuleType:
    module_name = f"_bizproof_target_{abs(hash(path))}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise TargetLoadError(f"cannot load module from {path}")

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise TargetLoadError(f"module import failed with {type(exc).__name__}: {exc}") from exc
    return module


def load_function(path: Path, function_name: str) -> Callable[..., Any]:
    module = load_module(path)
    target = getattr(module, function_name, None)
    if target is None or not callable(target):
        raise TargetLoadError(f"function {function_name!r} not found in {path}")
    return cast(Callable[..., Any], target)
