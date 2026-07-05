"""Compatibility surface for Event Alpha impact hypotheses.

Implementation lives in focused sibling modules. This module keeps the old
``crypto_rsi_scanner.event_alpha.radar.impact_hypotheses.api`` import path
working without retaining the historical monolith here.
"""

from __future__ import annotations

from types import ModuleType

from . import assets as _assets
from . import builder as _builder
from . import candidates as _candidates
from . import family as _family
from . import generation as _generation
from . import models as _models
from . import report as _report
from . import rules as _rules
from . import scoring as _scoring
from . import validation as _validation

_SPLIT_MODULES = (
    _models,
    _rules,
    _assets,
    _validation,
    _scoring,
    _family,
    _candidates,
    _report,
    _builder,
    _generation,
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
