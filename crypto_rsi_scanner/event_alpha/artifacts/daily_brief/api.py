"""Daily Markdown brief for Event Alpha research artifacts."""

from __future__ import annotations

import functools
import inspect
from types import ModuleType
from typing import Any

from .components.runtime import *
from .components import builder as _builder
from .components import diagnostics as _diagnostics
from .components import market_anomalies as _market_anomalies
from .components import models as _models
from .components import opportunity_lanes as _opportunity_lanes
from .components import research_review as _research_review
from .components import source_coverage as _source_coverage

_API_MODULES: tuple[ModuleType, ...] = (
    _builder,
    _diagnostics,
    _market_anomalies,
    _models,
    _opportunity_lanes,
    _research_review,
    _source_coverage,
)
_API_MODULE_EXPORTS: dict[ModuleType, set[str]] = {
    _builder: set(getattr(_builder, "__all__", ())),
    _diagnostics: set(getattr(_diagnostics, "__all__", ())),
    _market_anomalies: set(getattr(_market_anomalies, "__all__", ())),
    _models: set(getattr(_models, "__all__", ())),
    _opportunity_lanes: set(getattr(_opportunity_lanes, "__all__", ())),
    _research_review: set(getattr(_research_review, "__all__", ())),
    _source_coverage: set(getattr(_source_coverage, "__all__", ())),
}
_WRAPPED_API_CALLS: dict[str, Any] = {}


def _sync_api_module_globals() -> None:
    source = {
        name: value
        for name, value in globals().items()
        if not name.startswith("__")
        and name not in {
            "ModuleType", "Any", "functools", "inspect",
            "_API_MODULES", "_API_MODULE_EXPORTS", "_WRAPPED_API_CALLS",
            "_sync_api_module_globals", "_wrap_api_call", "_install_api_modules",
        }
    }
    for module in _API_MODULES:
        local_exports = _API_MODULE_EXPORTS[module]
        for name, value in source.items():
            if name in local_exports:
                continue
            setattr(module, name, value)


def _wrap_api_call(module: ModuleType, name: str, func: Any) -> Any:
    @functools.wraps(func)
    def _wrapped(*args: Any, **kwargs: Any) -> Any:
        _sync_api_module_globals()
        return getattr(module, name)(*args, **kwargs)

    _WRAPPED_API_CALLS[name] = _wrapped
    return _wrapped


def _install_api_modules() -> None:
    for module in _API_MODULES:
        for name in _API_MODULE_EXPORTS[module]:
            value = getattr(module, name)
            if inspect.isfunction(value) and getattr(value, "__module__", "") == module.__name__:
                globals()[name] = _wrap_api_call(module, name, value)
            else:
                globals()[name] = value


_install_api_modules()
_sync_api_module_globals()

__all__ = tuple(sorted(name for module in _API_MODULES for name in _API_MODULE_EXPORTS[module]))
