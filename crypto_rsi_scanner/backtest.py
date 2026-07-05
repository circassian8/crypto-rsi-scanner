"""Compatibility facade for the RSI backtest CLI and public helpers.

Implementation currently lives in :mod:`crypto_rsi_scanner.backtest_parts.api`
while shared backtest ownership is split into focused package surfaces.
"""

from __future__ import annotations

from .backtest_parts import api as _api

for _name in dir(_api):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_api, _name)

_WRAPPED_CALLS = {}


def _sync_api_overrides() -> None:
    for _name, _value in tuple(globals().items()):
        if _name in {"_api", "_sync_api_overrides", "main"} or _name.startswith("__"):
            continue
        if _WRAPPED_CALLS.get(_name) is _value:
            continue
        if hasattr(_api, _name):
            setattr(_api, _name, _value)


def _wrap_api_call(name: str):
    def _wrapped(*args, **kwargs):
        _sync_api_overrides()
        return getattr(_api, name)(*args, **kwargs)

    _wrapped.__name__ = name
    _wrapped.__doc__ = getattr(getattr(_api, name), "__doc__", None)
    _WRAPPED_CALLS[name] = _wrapped
    return _wrapped


_fetch_volume_pit_frames = _wrap_api_call("_fetch_volume_pit_frames")


def main(argv=None) -> None:
    _sync_api_overrides()
    return _api.main(argv)


__all__ = tuple(_name for _name in globals() if not _name.startswith("_"))


if __name__ == "__main__":
    main()
