"""Day-1 notification helpers for Event Alpha research alerts.

This module re-exports the notification pipeline API while the implementation
lives in focused modules under ``notifications.pipeline_parts``.
It owns delivery state only. It does not rank alerts, mutate watchlist state,
create trades, paper trade, or write normal RSI signal rows.
"""

from __future__ import annotations

import functools
import inspect
from types import ModuleType
from typing import Any

from .pipeline_parts.runtime import *
from .pipeline_parts import delivery_models as _delivery_models
from .pipeline_parts import delivery_writer as _delivery_writer
from .pipeline_parts import heartbeat as _heartbeat
from .pipeline_parts import message_renderer as _message_renderer
from .pipeline_parts import plan_builder as _plan_builder
from .pipeline_parts import preview_writer as _preview_writer
from .pipeline_parts import research_review_selection as _research_review_selection
from .pipeline_parts import send_plan as _send_plan
from .pipeline_parts import utilities as _utilities

_API_MODULES: tuple[ModuleType, ...] = (
    _delivery_models,
    _delivery_writer,
    _heartbeat,
    _message_renderer,
    _plan_builder,
    _preview_writer,
    _research_review_selection,
    _send_plan,
    _utilities,
)
_API_MODULE_EXPORTS: dict[ModuleType, set[str]] = {
    _delivery_models: set(getattr(_delivery_models, "__all__", ())),
    _delivery_writer: set(getattr(_delivery_writer, "__all__", ())),
    _heartbeat: set(getattr(_heartbeat, "__all__", ())),
    _message_renderer: set(getattr(_message_renderer, "__all__", ())),
    _plan_builder: set(getattr(_plan_builder, "__all__", ())),
    _preview_writer: set(getattr(_preview_writer, "__all__", ())),
    _research_review_selection: set(getattr(_research_review_selection, "__all__", ())),
    _send_plan: set(getattr(_send_plan, "__all__", ())),
    _utilities: set(getattr(_utilities, "__all__", ())),
}
_WRAPPED_API_CALLS: dict[str, Any] = {}


def _sync_api_module_globals() -> None:
    source = {
        name: value
        for name, value in globals().items()
        if not name.startswith("__")
        and name not in {
            "ModuleType", "Any", "functools", "inspect",
            "_API_MODULES", "_API_MODULE_EXPORTS", "_WRAPPED_API_CALLS",
            "_sync_api_module_globals", "_wrap_api_call", "_install_api_modules",
        }
    }
    for module in _API_MODULES:
        local_exports = _API_MODULE_EXPORTS[module]
        for name, value in source.items():
            if name in local_exports:
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
            if inspect.isfunction(value) and getattr(value, "__module__", "") == module.__name__:
                globals()[name] = _wrap_api_call(module, name, value)
            else:
                globals()[name] = value


_install_api_modules()
_sync_api_module_globals()

__all__ = tuple(sorted(name for module in _API_MODULES for name in _API_MODULE_EXPORTS[module]))
