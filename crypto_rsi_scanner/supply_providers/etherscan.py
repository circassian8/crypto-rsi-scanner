"""Fixture-backed Etherscan transfer-flow supply provider."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ._fixture_common import fetch_supply_snapshots


class EtherscanSupplyProvider:
    name = "etherscan_supply"

    def __init__(self, path: str | Path | None, *, required: bool = False) -> None:
        self.path = path
        self.required = required

    def fetch_snapshots(self) -> dict[str, dict[str, Any]]:
        return fetch_supply_snapshots(self.path, provider=self.name, required=self.required)
