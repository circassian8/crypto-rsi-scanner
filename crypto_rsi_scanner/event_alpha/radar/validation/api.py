"""Compatibility surface for Event Alpha validation reviews.

Implementation lives in focused sibling modules. This module keeps the old import
path working without retaining the historical monolith here.
"""

from __future__ import annotations

from types import ModuleType

from . import models as _models
from . import outcomes as _outcomes
from . import templates as _templates
from . import sample as _sample
from . import review as _review
from . import report as _report
from . import queue as _queue
from . import utils as _utils

_SPLIT_MODULES = (
    _models,
    _outcomes,
    _templates,
    _sample,
    _review,
    _report,
    _queue,
    _utils,
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
