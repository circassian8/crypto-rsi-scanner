from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from crypto_rsi_scanner.lean_radar.bybit_universe import (
    BybitUniverseError,
    load_catalog,
    normalize_catalog,
)
from crypto_rsi_scanner.lean_radar.store import LeanRadarStore


ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "fixtures/bybit_execution_quality/instruments_info.json"


def test_catalog_keeps_only_confirmed_active_usdt_perpetuals() -> None:
    payload = json.loads(CATALOG.read_text(encoding="utf-8"))
    rows = normalize_catalog(
        payload,
        source_mode="fixture",
        source_sha256="a" * 64,
    )

    assert [row.instrument_id for row in rows] == ["BTCUSDT", "ETHUSDT"]
    assert rows[0].tick_size == "0.1"
    assert rows[1].maximum_limit_quantity == "10000"
    assert rows[1].maximum_market_quantity == "5000"
    assert all(row.quote_coin == row.settle_coin == "USDT" for row in rows)
    assert all(row.contract_type == "LinearPerpetual" for row in rows)


def test_genuine_import_rejects_checked_in_fixture_path() -> None:
    with pytest.raises(BybitUniverseError, match="fixture/test/mock/replay"):
        load_catalog(CATALOG, source_mode="imported_catalog")


def test_genuine_local_copy_imports_into_one_small_store(tmp_path: Path) -> None:
    catalog = tmp_path / "bybit_catalog.json"
    catalog.write_bytes(CATALOG.read_bytes())
    rows = load_catalog(catalog, source_mode="imported_catalog")
    database = tmp_path / "lean.db"
    store = LeanRadarStore(database)

    store.replace_bybit_catalog(rows)

    assert store.catalog_status()["instrument_count"] == 2
    assert store.catalog_status()["source_mode"] == "imported_catalog"
    assert [row.instrument_id for row in store.list_bybit_instruments()] == [
        "BTCUSDT",
        "ETHUSDT",
    ]
    assert os.stat(database).st_mode & 0o777 == 0o600


def test_incomplete_catalog_fails_closed() -> None:
    payload = json.loads(CATALOG.read_text(encoding="utf-8"))
    payload["result"]["nextPageCursor"] = "more"

    with pytest.raises(BybitUniverseError, match="incomplete"):
        normalize_catalog(payload, source_mode="fixture", source_sha256="b" * 64)
