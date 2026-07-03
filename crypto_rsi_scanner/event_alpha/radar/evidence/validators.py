"""Evidence acquisition validators."""

from __future__ import annotations

from .legacy_acquisition import reconcile_acquisition_core_ids
from .models import *  # noqa: F403 - split modules share legacy model names

__all__ = ("reconcile_acquisition_core_ids",)
