"""Compatibility facade for the historical scanner CLI and helpers.

The implementation body now lives in
``crypto_rsi_scanner.cli.services.scanner_legacy`` while the public root module
keeps old imports and monkeypatch-heavy tests working during the v1/v2 refactor.
"""

from __future__ import annotations

import functools
import inspect
from typing import Any

from .cli.services import scanner_legacy as _legacy

_WRAPPED_CALLS: dict[str, Any] = {}
_ORIGINAL_LEGACY_FUNCTIONS: dict[str, Any] = {}


def _sync_legacy_overrides() -> None:
    for _name, _value in tuple(globals().items()):
        if _name in {
            "_legacy",
            "_WRAPPED_CALLS",
            "_ORIGINAL_LEGACY_FUNCTIONS",
            "_sync_legacy_overrides",
            "_wrap_legacy_call",
            "_install_legacy_exports",
        } or _name.startswith("__"):
            continue
        if _WRAPPED_CALLS.get(_name) is _value:
            if _name in _ORIGINAL_LEGACY_FUNCTIONS:
                setattr(_legacy, _name, _ORIGINAL_LEGACY_FUNCTIONS[_name])
            continue
        if hasattr(_legacy, _name):
            setattr(_legacy, _name, _value)


def _wrap_legacy_call(name: str, func: Any) -> Any:
    if inspect.iscoroutinefunction(func):

        @functools.wraps(func)
        async def _async_wrapped(*args: Any, **kwargs: Any) -> Any:
            _sync_legacy_overrides()
            return await getattr(_legacy, name)(*args, **kwargs)

        _WRAPPED_CALLS[name] = _async_wrapped
        return _async_wrapped

    @functools.wraps(func)
    def _wrapped(*args: Any, **kwargs: Any) -> Any:
        _sync_legacy_overrides()
        return getattr(_legacy, name)(*args, **kwargs)

    _WRAPPED_CALLS[name] = _wrapped
    return _wrapped


def _install_legacy_exports() -> None:
    legacy_wrapped_names = set(getattr(_legacy, "_WRAPPED_LEGACY_CALLS", {}))
    for _name in dir(_legacy):
        if _name.startswith("__"):
            continue
        if _name in {
            "_LEGACY_MODULES",
            "_LEGACY_MODULE_EXPORTS",
            "_ORIGINAL_LEGACY_MODULE_VALUES",
            "_WRAPPED_LEGACY_CALLS",
            "_sync_legacy_module_globals",
            "_wrap_legacy_call",
            "_install_legacy_modules",
        }:
            continue
        _value = getattr(_legacy, _name)
        if inspect.isfunction(_value) and (
            _name in legacy_wrapped_names or getattr(_value, "__module__", None) == _legacy.__name__
        ):
            _ORIGINAL_LEGACY_FUNCTIONS[_name] = _value
            globals()[_name] = _wrap_legacy_call(_name, _value)
        else:
            globals()[_name] = _value


_install_legacy_exports()

__all__ = tuple(_name for _name in globals() if not _name.startswith("_"))


if __name__ == "__main__":
    main()
