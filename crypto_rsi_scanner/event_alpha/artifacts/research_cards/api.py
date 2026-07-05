"""Markdown research cards for routed Event Alpha candidates."""

from __future__ import annotations

import functools
import inspect
from types import ModuleType
from typing import Any

from .components.runtime import *
from .components import diagnostics as _diagnostics
from .components import evidence as _evidence
from .components import index as _index
from .components import market_state as _market_state
from .components import models as _models
from .components import outcomes as _outcomes
from .components import renderer as _renderer
from .components import source_coverage as _source_coverage

_API_MODULES: tuple[ModuleType, ...] = (
    _diagnostics,
    _evidence,
    _index,
    _market_state,
    _models,
    _outcomes,
    _renderer,
    _source_coverage,
)
_API_MODULE_EXPORTS: dict[ModuleType, set[str]] = {
    _diagnostics: set(getattr(_diagnostics, "__all__", ())),
    _evidence: set(getattr(_evidence, "__all__", ())),
    _index: set(getattr(_index, "__all__", ())),
    _market_state: set(getattr(_market_state, "__all__", ())),
    _models: set(getattr(_models, "__all__", ())),
    _outcomes: set(getattr(_outcomes, "__all__", ())),
    _renderer: set(getattr(_renderer, "__all__", ())),
    _source_coverage: set(getattr(_source_coverage, "__all__", ())),
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
