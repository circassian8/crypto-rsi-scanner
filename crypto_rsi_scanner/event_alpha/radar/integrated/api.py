"""Integrated Event Alpha radar cycle.

Compatibility aggregator over focused integrated-radar modules.
It writes local artifacts only: no Telegram sends, paper trades, normal RSI signal rows, order logic, or event-fade triggers.
"""

from __future__ import annotations

import functools
import inspect
from types import ModuleType
from typing import Any

from .pipeline_parts.runtime import *
from .pipeline_parts import cycle as _cycle
from .pipeline_parts import merge as _merge
from .pipeline_parts import models as _models
from .pipeline_parts import report as _report
from .pipeline_parts import sidecars as _sidecars
from .pipeline_parts import utilities as _utilities

_LEGACY_MODULES: tuple[ModuleType, ...] = (
    _cycle,
    _merge,
    _models,
    _report,
    _sidecars,
    _utilities,
)
_LEGACY_MODULE_EXPORTS: dict[ModuleType, set[str]] = {
    _cycle: set(getattr(_cycle, "__all__", ())),
    _merge: set(getattr(_merge, "__all__", ())),
    _models: set(getattr(_models, "__all__", ())),
    _report: set(getattr(_report, "__all__", ())),
    _sidecars: set(getattr(_sidecars, "__all__", ())),
    _utilities: set(getattr(_utilities, "__all__", ())),
}
_WRAPPED_LEGACY_CALLS: dict[str, Any] = {}


def _sync_api_module_globals() -> None:
    source = {
        name: value
        for name, value in globals().items()
        if not name.startswith("__")
        and name not in {
            "ModuleType", "Any", "functools", "inspect",
            "_LEGACY_MODULES", "_LEGACY_MODULE_EXPORTS", "_WRAPPED_LEGACY_CALLS",
            "_sync_api_module_globals", "_wrap_api_call", "_install_api_modules",
        }
    }
    for module in _LEGACY_MODULES:
        local_exports = _LEGACY_MODULE_EXPORTS[module]
        for name, value in source.items():
            if name in local_exports:
                continue
            setattr(module, name, value)


def _wrap_api_call(module: ModuleType, name: str, func: Any) -> Any:
    @functools.wraps(func)
    def _wrapped(*args: Any, **kwargs: Any) -> Any:
        _sync_api_module_globals()
        return getattr(module, name)(*args, **kwargs)

    _WRAPPED_LEGACY_CALLS[name] = _wrapped
    return _wrapped


def _install_api_modules() -> None:
    for module in _LEGACY_MODULES:
        for name in _LEGACY_MODULE_EXPORTS[module]:
            value = getattr(module, name)
            if inspect.isfunction(value) and getattr(value, "__module__", "") == module.__name__:
                globals()[name] = _wrap_api_call(module, name, value)
            else:
                globals()[name] = value


_install_api_modules()
_sync_api_module_globals()

__all__ = tuple(sorted(name for module in _LEGACY_MODULES for name in _LEGACY_MODULE_EXPORTS[module]))
