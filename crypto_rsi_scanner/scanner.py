"""Compatibility facade for the historical scanner CLI and helpers.

The implementation body now lives in
``crypto_rsi_scanner.cli.services.scanner_api`` while the public root module
keeps historical public imports and monkeypatch-heavy tests working.
"""

from __future__ import annotations

import functools
import inspect
from typing import Any

from .cli.services import scanner_api as _api

_WRAPPED_CALLS: dict[str, Any] = {}
_ORIGINAL_API_FUNCTIONS: dict[str, Any] = {}


def _sync_api_overrides() -> None:
    for _name, _value in tuple(globals().items()):
        if _name in {
            "_api",
            "_WRAPPED_CALLS",
            "_ORIGINAL_API_FUNCTIONS",
            "_sync_api_overrides",
            "_wrap_api_call",
            "_install_api_exports",
        } or _name.startswith("__"):
            continue
        if _WRAPPED_CALLS.get(_name) is _value:
            if _name in _ORIGINAL_API_FUNCTIONS:
                setattr(_api, _name, _ORIGINAL_API_FUNCTIONS[_name])
            continue
        if hasattr(_api, _name):
            setattr(_api, _name, _value)


def _wrap_api_call(name: str, func: Any) -> Any:
    if inspect.iscoroutinefunction(func):

        @functools.wraps(func)
        async def _async_wrapped(*args: Any, **kwargs: Any) -> Any:
            _sync_api_overrides()
            return await getattr(_api, name)(*args, **kwargs)

        _WRAPPED_CALLS[name] = _async_wrapped
        return _async_wrapped

    @functools.wraps(func)
    def _wrapped(*args: Any, **kwargs: Any) -> Any:
        _sync_api_overrides()
        return getattr(_api, name)(*args, **kwargs)

    _WRAPPED_CALLS[name] = _wrapped
    return _wrapped


def _install_api_exports() -> None:
    wrapped_api_names = set(getattr(_api, "_WRAPPED_API_CALLS", {}))
    for _name in dir(_api):
        if _name.startswith("__"):
            continue
        if _name in {
            "_API_MODULES",
            "_API_MODULE_EXPORTS",
            "_ORIGINAL_API_MODULE_VALUES",
            "_WRAPPED_API_CALLS",
            "_sync_api_module_globals",
            "_wrap_api_call",
            "_install_api_modules",
        }:
            continue
        _value = getattr(_api, _name)
        if inspect.isfunction(_value) and (
            _name in wrapped_api_names or getattr(_value, "__module__", None) == _api.__name__
        ):
            _ORIGINAL_API_FUNCTIONS[_name] = _value
            globals()[_name] = _wrap_api_call(_name, _value)
        else:
            globals()[_name] = _value


_install_api_exports()

__all__ = tuple(_name for _name in globals() if not _name.startswith("_"))


if __name__ == "__main__":
    main()
