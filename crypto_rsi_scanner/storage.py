"""SQLite storage facade.

The public import path remains stable:
``from crypto_rsi_scanner.storage import Storage``.
"""

from __future__ import annotations

from .storage_parts import (
    ConnectionMixin,
    MaintenanceMixin,
    MigrationsMixin,
    PapersMixin,
    SignalsMixin,
    WatchlistMixin,
    _SCHEMA,
    _clean,
    _now_iso,
    _parse_iso,
)


class Storage(
    ConnectionMixin,
    MigrationsMixin,
    SignalsMixin,
    WatchlistMixin,
    PapersMixin,
    MaintenanceMixin,
):
    """Compatibility facade composed from storage mixins."""


__all__ = ("Storage", "_SCHEMA", "_clean", "_now_iso", "_parse_iso")
