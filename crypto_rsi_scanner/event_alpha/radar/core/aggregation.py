"""Core opportunity aggregation helpers."""

from __future__ import annotations

from .legacy_store import core_opportunities_from_rows
from .models import *  # noqa: F403 - split modules share legacy model names

__all__ = ("core_opportunities_from_rows",)
