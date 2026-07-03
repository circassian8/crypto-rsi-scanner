"""Provider health wrapper package."""

from __future__ import annotations

from .base import *  # noqa: F401,F403
from .derivatives_provider import *  # noqa: F401,F403
from .event_provider import *  # noqa: F401,F403
from .universe_provider import *  # noqa: F401,F403
from .. import provider_health_legacy as _legacy

for _name in dir(_legacy):
    if not _name.startswith("__"):
        globals().setdefault(_name, getattr(_legacy, _name))

__all__ = tuple(_name for _name in globals() if not _name.startswith("_"))

