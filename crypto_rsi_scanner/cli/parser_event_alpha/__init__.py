"""Compatibility package for `crypto_rsi_scanner/cli/parser_event_alpha.py`.

Implementation is split into focused submodules; this package preserves the historical import path.
"""

from __future__ import annotations

from importlib import import_module as _import_module

_MODULE_NAMES = ('event_alpha_args',)
_MODULES = tuple(_import_module(f"{__name__}.{_name}") for _name in _MODULE_NAMES)
_EXPORTS = {}
for _module in _MODULES:
    for _name, _value in vars(_module).items():
        if not _name.startswith("__"):
            _EXPORTS[_name] = _value
globals().update(_EXPORTS)
for _module in _MODULES:
    _module.__dict__.update(_EXPORTS)
__all__ = tuple(_name for _name in _EXPORTS if not _name.startswith("_"))
