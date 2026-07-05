"""Behavior-compatible aggregator for the Event Alpha artifact doctor."""

from __future__ import annotations

import functools
import inspect
from types import ModuleType
from typing import Any

from .artifact_doctor_parts.runtime import *
from .artifact_doctor_parts import context_loading as _context_loading
from .artifact_doctor_parts import integrated_radar_checks as _integrated_radar_checks
from .artifact_doctor_parts import namespace_checks as _namespace_checks
from .artifact_doctor_parts import notification_checks as _notification_checks
from .artifact_doctor_parts import notification_delivery_checks as _notification_delivery_checks
from .artifact_doctor_parts import outcome_checks as _outcome_checks
from .artifact_doctor_parts import provider_readiness_checks as _provider_readiness_checks
from .artifact_doctor_parts import reporting as _reporting
from .artifact_doctor_parts import result_models as _result_models
from .artifact_doctor_parts import source_coverage_checks as _source_coverage_checks

_LEGACY_MODULES: tuple[ModuleType, ...] = (
    _context_loading,
    _integrated_radar_checks,
    _namespace_checks,
    _notification_checks,
    _notification_delivery_checks,
    _outcome_checks,
    _provider_readiness_checks,
    _reporting,
    _result_models,
    _source_coverage_checks,
)
_LEGACY_MODULE_EXPORTS: dict[ModuleType, set[str]] = {
    _context_loading: set(getattr(_context_loading, "__all__", ())),
    _integrated_radar_checks: set(getattr(_integrated_radar_checks, "__all__", ())),
    _namespace_checks: set(getattr(_namespace_checks, "__all__", ())),
    _notification_checks: set(getattr(_notification_checks, "__all__", ())),
    _notification_delivery_checks: set(getattr(_notification_delivery_checks, "__all__", ())),
    _outcome_checks: set(getattr(_outcome_checks, "__all__", ())),
    _provider_readiness_checks: set(getattr(_provider_readiness_checks, "__all__", ())),
    _reporting: set(getattr(_reporting, "__all__", ())),
    _result_models: set(getattr(_result_models, "__all__", ())),
    _source_coverage_checks: set(getattr(_source_coverage_checks, "__all__", ())),
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
