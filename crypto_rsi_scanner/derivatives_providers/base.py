"""Provider protocols for event-discovery derivatives enrichment."""

from __future__ import annotations

from typing import Any, Protocol


class DerivativesProvider(Protocol):
    name: str

    def fetch_snapshots(self) -> dict[str, dict[str, Any]]:
        """Return derivatives snapshots keyed by coin id and/or symbol."""
