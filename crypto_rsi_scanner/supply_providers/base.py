"""Provider protocols for event-discovery supply/on-chain enrichment."""

from __future__ import annotations

from typing import Any, Protocol


class SupplyProvider(Protocol):
    name: str

    def fetch_snapshots(self) -> dict[str, dict[str, Any]]:
        """Return supply-pressure snapshots keyed by coin id and/or symbol."""
