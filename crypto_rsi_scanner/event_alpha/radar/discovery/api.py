"""Compatibility surface for Event Alpha discovery helpers.

Implementation lives in focused sibling modules. This module keeps the old import
path working without retaining the historical monolith here.
"""

from __future__ import annotations

from types import ModuleType

from . import models as _models
from . import loader as _loader
from . import manual as _manual
from . import providers as _providers
from . import report as _report
from . import sample as _sample
from . import snapshots as _snapshots

_SPLIT_MODULES = (
    _models,
    _loader,
    _manual,
    _providers,
    _report,
    _sample,
    _snapshots,
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
