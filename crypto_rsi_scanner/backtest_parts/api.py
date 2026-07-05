"""Compatibility binder for `crypto_rsi_scanner/backtest_parts/api.py`.

Implementation is split under `implementation`; this module preserves the historical import path.
"""

from __future__ import annotations

from importlib import import_module as _import_module

_MODULE_NAMES = ('data', 'walk', 'results', 'costs', 'risk', 'reports', 'cli')
_MODULES = tuple(_import_module(f"{__package__}.implementation.{_name}") for _name in _MODULE_NAMES)
_EXPORTS = {}
for _module in _MODULES:
    for _name, _value in vars(_module).items():
        if not _name.startswith("__"):
            _EXPORTS[_name] = _value
globals().update(_EXPORTS)
for _module in _MODULES:
    _module.__dict__.update(_EXPORTS)
__all__ = tuple(_name for _name in _EXPORTS if not _name.startswith("_"))


def _sync_split_globals() -> None:
    for _module in _MODULES:
        for _name, _value in globals().items():
            if not _name.startswith("__"):
                _module.__dict__[_name] = _value


_ORIGINAL_MAIN = globals()["main"]
_ORIGINAL_FETCH_VOLUME_PIT_FRAMES = globals()["_fetch_volume_pit_frames"]


def main(*args, **kwargs):
    _sync_split_globals()
    return _ORIGINAL_MAIN(*args, **kwargs)


def _fetch_volume_pit_frames(*args, **kwargs):
    _sync_split_globals()
    return _ORIGINAL_FETCH_VOLUME_PIT_FRAMES(*args, **kwargs)

if __name__ == "__main__":
    raise SystemExit(main())
