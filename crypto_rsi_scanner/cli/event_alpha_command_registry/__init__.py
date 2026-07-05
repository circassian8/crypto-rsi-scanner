"""Compatibility package for `crypto_rsi_scanner/cli/event_alpha_command_registry.py`.

Implementation is split into focused submodules; this package preserves the historical import path.
"""

from __future__ import annotations

from importlib import import_module as _import_module

_MODULE_NAMES = ('models', 'metadata', 'dispatch')
_MODULES = tuple(_import_module(f"{__name__}.{_name}") for _name in _MODULE_NAMES)
_EXPORTS = {}
for _module in _MODULES:
    for _name, _value in vars(_module).items():
        if not _name.startswith("__"):
            _EXPORTS[_name] = _value
globals().update(_EXPORTS)
for _module in _MODULES:
    _module.__dict__.update(_EXPORTS)


def _bind_api_scanner_globals() -> None:
    """Preserve the old single-module scanner-global binding across split parts."""
    bind_scanner_globals(globals())
    for _module in _MODULES:
        bind_scanner_globals(_module.__dict__)


globals()["_bind_api_scanner_globals"] = _bind_api_scanner_globals
for _module in _MODULES:
    _module.__dict__["_bind_api_scanner_globals"] = _bind_api_scanner_globals
__all__ = tuple(_name for _name in _EXPORTS if not _name.startswith("_"))
