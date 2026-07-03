"""Compatibility facade for the RSI backtest CLI and public helpers.

Implementation currently lives in :mod:`crypto_rsi_scanner.backtest_parts.legacy`
while shared backtest ownership is split into focused package surfaces.
"""

from __future__ import annotations

from .backtest_parts import legacy as _legacy

for _name in dir(_legacy):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_legacy, _name)

_WRAPPED_CALLS = {}


def _sync_legacy_overrides() -> None:
    for _name, _value in tuple(globals().items()):
        if _name in {"_legacy", "_sync_legacy_overrides", "main"} or _name.startswith("__"):
            continue
        if _WRAPPED_CALLS.get(_name) is _value:
            continue
        if hasattr(_legacy, _name):
            setattr(_legacy, _name, _value)


def _wrap_legacy_call(name: str):
    def _wrapped(*args, **kwargs):
        _sync_legacy_overrides()
        return getattr(_legacy, name)(*args, **kwargs)

    _wrapped.__name__ = name
    _wrapped.__doc__ = getattr(getattr(_legacy, name), "__doc__", None)
    _WRAPPED_CALLS[name] = _wrapped
    return _wrapped


_fetch_volume_pit_frames = _wrap_legacy_call("_fetch_volume_pit_frames")


def main(argv=None) -> None:
    _sync_legacy_overrides()
    return _legacy.main(argv)


__all__ = tuple(_name for _name in globals() if not _name.startswith("_"))


if __name__ == "__main__":
    main()
