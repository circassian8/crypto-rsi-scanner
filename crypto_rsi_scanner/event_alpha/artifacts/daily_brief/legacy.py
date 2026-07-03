"""Daily Markdown brief for Event Alpha research artifacts.

Compatibility aggregator over focused legacy daily-brief modules.
"""

from __future__ import annotations

import functools
import inspect
from types import ModuleType
from typing import Any

from .legacy_parts.runtime import *
from .legacy_parts import builder as _builder
from .legacy_parts import diagnostics as _diagnostics
from .legacy_parts import market_anomalies as _market_anomalies
from .legacy_parts import models as _models
from .legacy_parts import opportunity_lanes as _opportunity_lanes
from .legacy_parts import research_review as _research_review
from .legacy_parts import source_coverage as _source_coverage

_LEGACY_MODULES: tuple[ModuleType, ...] = (
    _builder,
    _diagnostics,
    _market_anomalies,
    _models,
    _opportunity_lanes,
    _research_review,
    _source_coverage,
)
_LEGACY_MODULE_EXPORTS: dict[ModuleType, set[str]] = {
    _builder: set(getattr(_builder, "__all__", ())),
    _diagnostics: set(getattr(_diagnostics, "__all__", ())),
    _market_anomalies: set(getattr(_market_anomalies, "__all__", ())),
    _models: set(getattr(_models, "__all__", ())),
    _opportunity_lanes: set(getattr(_opportunity_lanes, "__all__", ())),
    _research_review: set(getattr(_research_review, "__all__", ())),
    _source_coverage: set(getattr(_source_coverage, "__all__", ())),
}
_WRAPPED_LEGACY_CALLS: dict[str, Any] = {}


def _sync_legacy_module_globals() -> None:
    source = {
        name: value
        for name, value in globals().items()
        if not name.startswith("__")
        and name not in {
            "ModuleType", "Any", "functools", "inspect",
            "_LEGACY_MODULES", "_LEGACY_MODULE_EXPORTS", "_WRAPPED_LEGACY_CALLS",
            "_sync_legacy_module_globals", "_wrap_legacy_call", "_install_legacy_modules",
        }
    }
    for module in _LEGACY_MODULES:
        local_exports = _LEGACY_MODULE_EXPORTS[module]
        for name, value in source.items():
            if name in local_exports:
                continue
            setattr(module, name, value)


def _wrap_legacy_call(module: ModuleType, name: str, func: Any) -> Any:
    @functools.wraps(func)
    def _wrapped(*args: Any, **kwargs: Any) -> Any:
        _sync_legacy_module_globals()
        return getattr(module, name)(*args, **kwargs)

    _WRAPPED_LEGACY_CALLS[name] = _wrapped
    return _wrapped


def _install_legacy_modules() -> None:
    for module in _LEGACY_MODULES:
        for name in _LEGACY_MODULE_EXPORTS[module]:
            value = getattr(module, name)
            if inspect.isfunction(value) and getattr(value, "__module__", "") == module.__name__:
                globals()[name] = _wrap_legacy_call(module, name, value)
            else:
                globals()[name] = value


_install_legacy_modules()
_sync_legacy_module_globals()

__all__ = tuple(sorted(name for module in _LEGACY_MODULES for name in _LEGACY_MODULE_EXPORTS[module]))
