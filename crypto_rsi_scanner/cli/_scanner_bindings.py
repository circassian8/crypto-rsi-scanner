"""Lazy bindings to scanner helpers used by extracted CLI dispatch modules."""

from __future__ import annotations

from types import ModuleType
from typing import MutableMapping


def bind_scanner_globals(target: MutableMapping[str, object], scanner_module: ModuleType | None = None) -> ModuleType:
    if scanner_module is None:
        from .. import scanner as scanner_module
    for name, value in vars(scanner_module).items():
        if not name.startswith("__"):
            target[name] = value
    return scanner_module
