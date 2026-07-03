"""Compatibility aggregator for the historical scanner CLI service.

The implementation is split across focused modules under ``cli.services.legacy``.
This module preserves old imports, monkeypatch-heavy tests, and scanner facade
compatibility while command families continue to move into explicit services.
"""

from __future__ import annotations

import functools
import inspect
from types import ModuleType
from typing import Any

from .legacy.runtime import *
from .legacy import alerts as _alerts
from .legacy import config_reports as _config_reports
from .legacy import event_research as _event_research
from .legacy import fade_review as _fade_review
from .legacy import provider_preflights as _provider_preflights
from .legacy import reports as _reports
from .legacy import rsi_scan as _rsi_scan
from .legacy import utility_commands as _utility_commands

_LEGACY_MODULES: tuple[ModuleType, ...] = (
    _alerts,
    _config_reports,
    _event_research,
    _fade_review,
    _provider_preflights,
    _reports,
    _rsi_scan,
    _utility_commands,
)
_LEGACY_MODULE_EXPORTS: dict[ModuleType, set[str]] = {
    _alerts: set(getattr(_alerts, "__all__", ())),
    _config_reports: set(getattr(_config_reports, "__all__", ())),
    _event_research: set(getattr(_event_research, "__all__", ())),
    _fade_review: set(getattr(_fade_review, "__all__", ())),
    _provider_preflights: set(getattr(_provider_preflights, "__all__", ())),
    _reports: set(getattr(_reports, "__all__", ())),
    _rsi_scan: set(getattr(_rsi_scan, "__all__", ())),
    _utility_commands: set(getattr(_utility_commands, "__all__", ())),
}
_ORIGINAL_LEGACY_MODULE_VALUES: dict[tuple[ModuleType, str], Any] = {}
_WRAPPED_LEGACY_CALLS: dict[str, Any] = {}


def _sync_legacy_module_globals() -> None:
    source = {
        name: value
        for name, value in globals().items()
        if not name.startswith("__")
        and name not in {
            "ModuleType", "Any", "functools", "inspect",
            "_LEGACY_MODULES", "_LEGACY_MODULE_EXPORTS", "_ORIGINAL_LEGACY_MODULE_VALUES", "_WRAPPED_LEGACY_CALLS",
            "_sync_legacy_module_globals", "_wrap_legacy_call", "_install_legacy_modules",
        }
    }
    for module in _LEGACY_MODULES:
        local_exports = _LEGACY_MODULE_EXPORTS[module]
        for name, value in source.items():
            if name in local_exports:
                original = _ORIGINAL_LEGACY_MODULE_VALUES.get((module, name))
                if value is _WRAPPED_LEGACY_CALLS.get(name):
                    if original is not None and getattr(module, name) is not original:
                        setattr(module, name, original)
                    continue
            setattr(module, name, value)


def _wrap_legacy_call(module: ModuleType, name: str, func: Any) -> Any:
    if inspect.iscoroutinefunction(func):

        @functools.wraps(func)
        async def _async_wrapped(*args: Any, **kwargs: Any) -> Any:
            _sync_legacy_module_globals()
            return await getattr(module, name)(*args, **kwargs)

        _WRAPPED_LEGACY_CALLS[name] = _async_wrapped
        return _async_wrapped

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
            _ORIGINAL_LEGACY_MODULE_VALUES[(module, name)] = value
            if inspect.isfunction(value) and getattr(value, "__module__", "") == module.__name__:
                globals()[name] = _wrap_legacy_call(module, name, value)
            else:
                globals()[name] = value


_install_legacy_modules()
_sync_legacy_module_globals()


def cli(argv: list[str] | None = None) -> None:
    from ..dispatch import dispatch_args
    from ..parser import build_parser

    parser = build_parser()
    args = parser.parse_args(argv)
    dispatch_args(args)


def main() -> None:
    cli()


__all__ = tuple(sorted({*(name for module in _LEGACY_MODULES for name in _LEGACY_MODULE_EXPORTS[module]), "cli", "main"}))
