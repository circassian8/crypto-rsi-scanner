"""Core opportunity store operations."""

from __future__ import annotations

from .legacy_store import (
    load_core_opportunities,
    normalize_core_opportunity_store,
    write_core_opportunities,
)

__all__ = ("load_core_opportunities", "normalize_core_opportunity_store", "write_core_opportunities")
