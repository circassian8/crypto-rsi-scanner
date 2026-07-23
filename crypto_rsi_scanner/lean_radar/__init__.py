"""Lean Crypto Radar: the small default operator product path.

The package is deliberately independent of the Event Alpha pipeline.  It may
reuse small pure helpers, but market-led ideas do not require catalyst evidence.
"""

from .models import (
    IDEA_TYPES,
    ROUTES,
    BybitInstrument,
    LeanIdea,
    UniverseAsset,
)

__all__ = (
    "IDEA_TYPES",
    "ROUTES",
    "BybitInstrument",
    "LeanIdea",
    "UniverseAsset",
)
