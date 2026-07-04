"""Compatibility package for `crypto_rsi_scanner/cli/services/event_alpha_notifications.py`.

Implementation is split into focused submodules; this package preserves the historical import path.
"""

from __future__ import annotations

from importlib import import_module as _import_module

_MODULE_NAMES = ('bindings', 'preview', 'fixture_smoke', 'go_no_go', 'pack_export', 'send_readiness', 'final_check', 'delivery_reports')
_MODULES = tuple(_import_module(f"{__name__}.{_name}") for _name in _MODULE_NAMES)
_EXPORTS = {}
for _module in _MODULES:
    for _name, _value in vars(_module).items():
        if not _name.startswith("__"):
            _EXPORTS[_name] = _value
_BINDINGS = _MODULES[0]
_BIND_SCANNER_GLOBALS_IMPL = _BINDINGS.bind_scanner_globals


def bind_scanner_globals(target, scanner_module=None):
    scanner_module = _BIND_SCANNER_GLOBALS_IMPL(target, scanner_module)
    for _module in _MODULES:
        _BIND_SCANNER_GLOBALS_IMPL(_module.__dict__, scanner_module)
    return scanner_module


def _refresh_scanner_globals():
    return bind_scanner_globals(globals())


_EXPORTS["bind_scanner_globals"] = bind_scanner_globals
_EXPORTS["_refresh_scanner_globals"] = _refresh_scanner_globals
globals().update(_EXPORTS)
for _module in _MODULES:
    _module.__dict__.update(_EXPORTS)
__all__ = tuple(_name for _name in _EXPORTS if not _name.startswith("_"))
