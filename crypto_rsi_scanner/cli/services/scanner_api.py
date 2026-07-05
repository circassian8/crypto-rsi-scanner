"""Compatibility aggregator for the historical scanner CLI service.

The implementation is split across focused modules under ``cli.services.scanner_parts``.
This module preserves old imports, monkeypatch-heavy tests, and scanner facade
compatibility behind a stable public API bridge.
"""

from __future__ import annotations

import functools
import inspect
from types import ModuleType
from typing import Any

from .scanner_parts.runtime import *
from .scanner_parts import alerts as _alerts
from .scanner_parts import config_reports as _config_reports
from .scanner_parts import event_research as _event_research
from .scanner_parts import fade_review as _fade_review
from .scanner_parts import provider_preflights as _provider_preflights
from .scanner_parts import reports as _reports
from .scanner_parts import rsi_scan as _rsi_scan
from .scanner_parts import utility_commands as _utility_commands

_API_MODULES: tuple[ModuleType, ...] = (
    _alerts,
    _config_reports,
    _event_research,
    _fade_review,
    _provider_preflights,
    _reports,
    _rsi_scan,
    _utility_commands,
)
_API_MODULE_EXPORTS: dict[ModuleType, set[str]] = {
    _alerts: set(getattr(_alerts, "__all__", ())),
    _config_reports: set(getattr(_config_reports, "__all__", ())),
    _event_research: set(getattr(_event_research, "__all__", ())),
    _fade_review: set(getattr(_fade_review, "__all__", ())),
    _provider_preflights: set(getattr(_provider_preflights, "__all__", ())),
    _reports: set(getattr(_reports, "__all__", ())),
    _rsi_scan: set(getattr(_rsi_scan, "__all__", ())),
    _utility_commands: set(getattr(_utility_commands, "__all__", ())),
}
_ORIGINAL_API_MODULE_VALUES: dict[tuple[ModuleType, str], Any] = {}
_WRAPPED_API_CALLS: dict[str, Any] = {}


def _sync_api_module_globals() -> None:
    source = {
        name: value
        for name, value in globals().items()
        if not name.startswith("__")
        and name not in {
            "ModuleType", "Any", "functools", "inspect",
            "_API_MODULES", "_API_MODULE_EXPORTS", "_ORIGINAL_API_MODULE_VALUES", "_WRAPPED_API_CALLS",
            "_sync_api_module_globals", "_wrap_api_call", "_install_api_modules",
        }
    }
    for module in _API_MODULES:
        local_exports = _API_MODULE_EXPORTS[module]
        for name, value in source.items():
            if name in local_exports:
                original = _ORIGINAL_API_MODULE_VALUES.get((module, name))
                if value is _WRAPPED_API_CALLS.get(name):
                    if original is not None and getattr(module, name) is not original:
                        setattr(module, name, original)
                    continue
            setattr(module, name, value)


def _wrap_api_call(module: ModuleType, name: str, func: Any) -> Any:
    if inspect.iscoroutinefunction(func):

        @functools.wraps(func)
        async def _async_wrapped(*args: Any, **kwargs: Any) -> Any:
            _sync_api_module_globals()
            return await getattr(module, name)(*args, **kwargs)

        _WRAPPED_API_CALLS[name] = _async_wrapped
        return _async_wrapped

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
            _ORIGINAL_API_MODULE_VALUES[(module, name)] = value
            if inspect.isfunction(value) and getattr(value, "__module__", "") == module.__name__:
                globals()[name] = _wrap_api_call(module, name, value)
            else:
                globals()[name] = value


_install_api_modules()
_sync_api_module_globals()


def cli(argv: list[str] | None = None) -> None:
    from ..dispatch import dispatch_args
    from ..parser import build_parser

    parser = build_parser()
    args = parser.parse_args(argv)
    dispatch_args(args)


def main() -> None:
    cli()


__all__ = tuple(sorted({*(name for module in _API_MODULES for name in _API_MODULE_EXPORTS[module]), "cli", "main"}))
