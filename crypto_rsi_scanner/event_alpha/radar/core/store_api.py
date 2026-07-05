"""Compatibility surface for canonical core opportunity store helpers.

Implementation lives in focused sibling modules. This module keeps the old import
path working without retaining the historical monolith here.
"""

from __future__ import annotations

from types import ModuleType

from . import models as _models
from . import store as _store
from . import serialization as _serialization
from . import merge as _merge
from . import evidence_fields as _evidence_fields
from . import path_fields as _path_fields

_SPLIT_MODULES = (
    _models,
    _store,
    _serialization,
    _merge,
    _evidence_fields,
    _path_fields,
)


def _export_module_symbols(module: ModuleType) -> None:
    for name, value in vars(module).items():
        if name.startswith("__") and name.endswith("__"):
            continue
        globals()[name] = value


for _module in _SPLIT_MODULES:
    _export_module_symbols(_module)

for _module in _SPLIT_MODULES:
    _module.__dict__.update(globals())

__all__ = tuple(
    sorted(
        name
        for name in globals()
        if not (name.startswith("__") and name.endswith("__"))
        and name not in {"ModuleType", "_module", "_export_module_symbols", "_SPLIT_MODULES"}
    )
)

del ModuleType, _module, _export_module_symbols, _SPLIT_MODULES
