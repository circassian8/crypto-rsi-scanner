"""Event Alpha CLI service aggregator.

Implementation bodies live in focused ``event_alpha_*`` service modules. This
module re-exports the historical service surface while scanner wrappers and
older imports migrate incrementally.
"""

from __future__ import annotations

from . import (
    event_alpha_research,
    event_alpha_notifications,
    event_alpha_outcomes,
    event_alpha_reports,
    event_alpha_provider_preflights,
    event_alpha_namespace,
    event_alpha_integrated,
    event_alpha_fade_review,
)

_MODULES = (
    event_alpha_research,
    event_alpha_notifications,
    event_alpha_outcomes,
    event_alpha_reports,
    event_alpha_provider_preflights,
    event_alpha_namespace,
    event_alpha_integrated,
    event_alpha_fade_review,
)

for _module in _MODULES:
    globals().update(
        {
            name: getattr(_module, name)
            for name in dir(_module)
            if not (name.startswith("__") and name.endswith("__"))
        }
    )

__all__ = tuple(
    name
    for _module in _MODULES
    for name in dir(_module)
    if not (name.startswith("__") and name.endswith("__"))
)
