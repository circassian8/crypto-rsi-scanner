"""Compatibility surface for Event Alpha evidence acquisition.

Implementation lives in focused sibling modules. This module keeps the old import
path working without retaining the historical monolith here.
"""

from __future__ import annotations

from types import ModuleType

from . import models as _models
from . import executor as _executor
from . import serialization as _serialization
from . import scoring as _scoring
from . import providers as _providers
from . import verdicts as _verdicts

_SPLIT_MODULES = (
    _models,
    _executor,
    _serialization,
    _scoring,
    _providers,
    _verdicts,
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
