"""Core opportunity validation helpers."""

from __future__ import annotations

from .store_api import normalize_core_opportunity_rows
from .models import *  # noqa: F403 - split modules share legacy model names

__all__ = ("normalize_core_opportunity_rows",)
