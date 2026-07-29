from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import plistlib
from typing import Mapping, Sequence

import pytest

from crypto_rsi_scanner.lean_radar import maintenance, market_data
from crypto_rsi_scanner.lean_radar.config import LeanRadarSettings
from crypto_rsi_scanner.lean_radar.cli import run
from crypto_rsi_scanner.lean_radar.maintenance import (
    LeanMaintenanceError,
    install_maintenance,
    maintenance_status,
    service_plist_bytes,
    uninstall_maintenance,
)
from crypto_rsi_scanner.lean_radar.market_data import (
    MarketDataError,
    fetch_live_market_rows,
)
from crypto_rsi_scanner.lean_radar.models import BybitInstrument, MarketSnapshot
from crypto_rsi_scanner.lean_radar.scan import scan_readiness
from crypto_rsi_scanner.lean_radar.store import (
    MAX_CYCLE_RECEIPTS,
    LeanRadarStore,
)
from crypto_rsi_scanner.lean_radar.universe import build_universe


NOW = datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc)


def _instrument(symbol: str, *, observed_at: datetime = NOW) -> BybitInstrument:
    return BybitInstrument(
        instrument_id=f"{symbol}USDT",
        base_coin=symbol,
        quote_coin="USDT",
        settle_coin="USDT",
        contract_type="LinearPerpetual",
        status="Trading",
        tick_size="0.001",
        quantity_step="0.1",
        minimum_quantity="0.1",
        maximum_limit_quantity="100000",
        maximum_market_quantity="10000",
        minimum_notional_usdt="5",
        source_observed_at=observed_at.isoformat(),
        source_mode="imported_catalog",
        source_sha256="a" * 64,
    )


def _market_row(
    index: int,
    symbol: str,
    *,
    canonical_id: str | None = None,
) -> dict[str, object]:
    return {
        "id": canonical_id or f"asset-{index:04d}",
        "symbol": symbol.casefold(),
        "name": f"Asset {index}",
        "current_price": 10.0 + index,
        "market_cap": 1_000_000_000.0 + index,
        "market_cap_rank": index + 1,
        "total_volume": 10_000_000_000.0 - index,
        "price_change_percentage_1h_in_currency": 0.2,
        "price_change_percentage_24h_in_currency": 1.0,
        "price_change_percentage_7d_in_currency": 2.0,
        "sparkline_in_7d": {"price": [10.0 + step * 0.01 for step in range(30)]},
    }


class _FakeCoinGecko:
    pages: Mapping[int, Sequence[Mapping[str, object]]] = {}
    targeted: Mapping[str, Mapping[str, object]] = {}
    calls: list[dict[str, object]] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        self.last_request_telemetry: dict[str, object] | None = None

    async def __aenter__(self) -> _FakeCoinGecko:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def _get(
        self,
        path: str,
        params: dict[str, object],
    ) -> list[Mapping[str, object]]:
        assert path == "/coins/markets"
        self.calls.append(dict(params))
        if "ids" in params:
            requested = str(params["ids"]).split(",")
            rows = [self.targeted[value] for value in requested if value in self.targeted]
        else:
            rows = list(self.pages.get(int(params["page"]), ()))
        self.last_request_telemetry = {
            "endpoint_path": path,
            "http_status": 200,
            "retry_count": 0,
            "duration_ms": 2,
            "error_class": None,
        }
        return rows


def test_live_collection_paginates_to_200_eligible_and_targets_watchlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_symbols = [f"E{index:03d}" for index in range(150)]
    second_symbols = [f"E{index:03d}" for index in range(150, 210)]
    instruments = tuple(
        _instrument(symbol) for symbol in (*first_symbols, *second_symbols, "WATCH")
    )
    first = [
        _market_row(index, symbol)
        for index, symbol in enumerate(first_symbols)
    ] + [
        _market_row(10_000 + index, f"NO{index:03d}")
        for index in range(100)
    ]
    second = [
        _market_row(20_000 + index, symbol)
        for index, symbol in enumerate(second_symbols)
    ]
    watch = _market_row(
        30_000,
        "WATCH",
        canonical_id="watchlist-only",
    )
    _FakeCoinGecko.pages = {1: first, 2: second}
    _FakeCoinGecko.targeted = {"watchlist-only": watch}
    _FakeCoinGecko.calls = []
    monkeypatch.setattr(market_data, "CoinGeckoClient", _FakeCoinGecko)
    monkeypatch.setattr("crypto_rsi_scanner.config.FIXTURE_DIR", None)

    rows, telemetry = fetch_live_market_rows(
        instruments=instruments,
        manual_watchlist=(
            {"canonical_asset_id": "watchlist-only", "symbol": "WATCH"},
        ),
        environ={"RSI_EVENT_DISCOVERY_UNIVERSE_LIVE": "1"},
    )
    universe = build_universe(
        rows,
        instruments,
        ({"canonical_asset_id": "watchlist-only", "symbol": "WATCH"},),
        ranked_source_exhausted=telemetry["ranked_source_exhausted"],  # type: ignore[arg-type]
        ranked_page_budget_reached=bool(
            telemetry["ranked_page_budget_reached"]
        ),
    )

    assert telemetry["target_reached"] is True
    assert telemetry["eligible_ranked_count"] == 200
    assert telemetry["ranked_page_count"] == 2
    assert telemetry["provider_call_count"] == 3
    assert telemetry["watchlist_targeted_requested_count"] == 1
    assert "requested_ids_sha256" in telemetry["request_ledger"][-1]  # type: ignore[index]
    assert "ids" not in _FakeCoinGecko.calls[0]
    assert _FakeCoinGecko.calls[-1]["ids"] == "watchlist-only"
    assert universe.ranked_completion_status == "target_reached"
    assert universe.eligible_ranked_count == 200
    assert len(universe.active_assets) == 201
    watch_asset = next(
        row for row in universe.active_assets if row.canonical_asset_id == "watchlist-only"
    )
    assert watch_asset.liquidity_rank is None
    assert watch_asset.origins == ("manual_watchlist",)


def test_live_collection_reports_true_provider_exhaustion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instruments = (_instrument("A1"), _instrument("A2"))
    _FakeCoinGecko.pages = {
        1: [_market_row(1, "A1"), _market_row(2, "A2")]
    }
    _FakeCoinGecko.targeted = {}
    _FakeCoinGecko.calls = []
    monkeypatch.setattr(market_data, "CoinGeckoClient", _FakeCoinGecko)
    monkeypatch.setattr("crypto_rsi_scanner.config.FIXTURE_DIR", None)

    rows, telemetry = fetch_live_market_rows(
        instruments=instruments,
        environ={"RSI_EVENT_DISCOVERY_UNIVERSE_LIVE": "1"},
    )
    universe = build_universe(
        rows,
        instruments,
        ranked_source_exhausted=True,
    )

    assert telemetry["ranked_source_exhausted"] is True
    assert telemetry["ranked_page_budget_reached"] is False
    assert telemetry["eligible_ranked_count"] == 2
    assert universe.ranked_completion_status == "provider_exhausted_shortfall"


def test_live_collection_failure_retains_only_sanitized_bounded_telemetry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_page = [_market_row(index, f"X{index:03d}") for index in range(250)]

    class FailingCoinGecko(_FakeCoinGecko):
        async def _get(
            self,
            path: str,
            params: dict[str, object],
        ) -> list[Mapping[str, object]]:
            page = int(params["page"])
            if page == 1:
                self.last_request_telemetry = {
                    "endpoint_path": path,
                    "http_status": 200,
                    "retry_count": 0,
                    "duration_ms": 2,
                    "error_class": None,
                }
                return first_page
            self.last_request_telemetry = {
                "endpoint_path": path,
                "http_status": 403,
                "retry_count": 0,
                "duration_ms": 3,
                "error_class": "http_error",
            }
            raise RuntimeError("untrusted response body with token=do-not-persist")

    monkeypatch.setattr(market_data, "CoinGeckoClient", FailingCoinGecko)
    monkeypatch.setattr("crypto_rsi_scanner.config.FIXTURE_DIR", None)

    with pytest.raises(MarketDataError) as caught:
        fetch_live_market_rows(
            instruments=(_instrument("X000"),),
            environ={"RSI_EVENT_DISCOVERY_UNIVERSE_LIVE": "1"},
        )

    telemetry = caught.value.telemetry
    assert telemetry["failure_class"] == "provider_request_failed"
    assert telemetry["failure_stage"] == "ranked_page"
    assert telemetry["failure_ordinal"] == 2
    assert telemetry["provider_call_count"] == 2
    assert telemetry["completed_request_count"] == 1
    assert telemetry["last_request"] == {
        "endpoint_path": "/coins/markets",
        "http_status": 403,
        "retry_count": 0,
        "duration_ms": 3,
        "error_class": "http_error",
    }
    assert "do-not-persist" not in str(telemetry)


def test_catalog_freshness_warns_then_blocks_without_calling_provider(
    tmp_path: Path,
) -> None:
    store = LeanRadarStore(tmp_path / "lean.db")
    store.replace_bybit_catalog((_instrument("BTC"),), imported_at=NOW)
    settings = LeanRadarSettings(db_path=store.path, cadence_minutes=20)

    fresh = store.catalog_status(evaluated_at=NOW + timedelta(hours=11))
    refresh = store.catalog_status(evaluated_at=NOW + timedelta(hours=13))
    stale = store.catalog_status(evaluated_at=NOW + timedelta(hours=25))
    readiness = scan_readiness(
        store,
        settings,
        source_mode="live_no_send",
        environ={"RSI_EVENT_DISCOVERY_UNIVERSE_LIVE": "1"},
        evaluated_at=NOW + timedelta(hours=25),
    )

    assert fresh["status"] == "ready"
    assert fresh["freshness_status"] == "fresh"
    assert refresh["status"] == "ready"
    assert refresh["freshness_status"] == "refresh_recommended"
    assert stale["status"] == "stale"
    assert stale["usable_for_scan"] is False
    assert readiness["status"] == "blocked"
    assert readiness["provider_call_attempted"] is False


def _snapshot(observed_at: datetime) -> MarketSnapshot:
    return MarketSnapshot(
        canonical_asset_id="bitcoin",
        symbol="BTC",
        name="Bitcoin",
        bybit_instrument="BTCUSDT",
        observed_at=observed_at.isoformat(),
        source_mode="fixture",
        price_usd=100.0,
        market_cap_usd=1_000_000_000.0,
        volume_usd_24h=100_000_000.0,
        turnover_ratio_24h=0.1,
        return_1h_pp=0.0,
        return_24h_pp=0.0,
        return_7d_pp=0.0,
        rsi_14=50.0,
        spread_bps=10.0,
        sparkline_prices=tuple(100.0 for _ in range(30)),
        return_basis="fixture_percent_points",
        rsi_basis="fixture_wilder_14",
        data_quality="complete",
    )


def test_database_retention_dry_run_is_read_only_then_compacts_and_deletes(
    tmp_path: Path,
) -> None:
    store = LeanRadarStore(tmp_path / "lean.db")
    store.replace_bybit_catalog((_instrument("BTC"),), imported_at=NOW)
    snapshots = (
        _snapshot(NOW - timedelta(days=2)),
        _snapshot(NOW - timedelta(days=5)),
        _snapshot(NOW - timedelta(days=15)),
    )
    with store.connect(write=True) as connection:
        connection.executemany(
            """
            INSERT INTO market_snapshots (
                canonical_asset_id, observed_at, source_mode, payload_json
            ) VALUES (?, ?, ?, ?)
            """,
            [
                (
                    f"{row.canonical_asset_id}-{index}",
                    row.observed_at,
                    row.source_mode,
                    json.dumps(
                        {
                            **row.to_dict(),
                            "canonical_asset_id": f"{row.canonical_asset_id}-{index}",
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                )
                for index, row in enumerate(snapshots)
            ],
        )
        connection.commit()
    before = hashlib.sha256(store.path.read_bytes()).hexdigest()

    preview = store.maintain_database(evaluated_at=NOW)
    after_preview = hashlib.sha256(store.path.read_bytes()).hexdigest()
    applied = store.maintain_database(evaluated_at=NOW, apply=True)

    assert preview["status"] == "dry_run"
    assert preview["maintenance_candidates"]["snapshots_to_compact"] == 1
    assert preview["maintenance_candidates"]["snapshots_to_delete"] == 1
    assert before == after_preview
    assert applied["changes"]["snapshots_compacted"] == 1
    assert applied["changes"]["snapshots_deleted"] == 1
    with store.connect() as connection:
        rows = connection.execute(
            "SELECT observed_at, payload_json FROM market_snapshots ORDER BY observed_at"
        ).fetchall()
    assert len(rows) == 2
    compacted = json.loads(rows[0]["payload_json"])
    current = json.loads(rows[1]["payload_json"])
    assert compacted["sparkline_prices"] == []
    assert len(current["sparkline_prices"]) == 30


def test_cycle_receipts_are_bounded(tmp_path: Path) -> None:
    store = LeanRadarStore(tmp_path / "lean.db")
    store.replace_bybit_catalog((_instrument("BTC"),), imported_at=NOW)
    with store.connect(write=True) as connection:
        connection.executemany(
            """
            INSERT INTO cycle_receipts (
                cycle_id, attempted_at, completed_at,
                trigger, status, payload_json
            ) VALUES (?, ?, ?, 'scheduled', 'waiting', ?)
            """,
            [
                (
                    f"lean-cycle-{index:04d}",
                    (NOW + timedelta(minutes=index)).isoformat(),
                    (NOW + timedelta(minutes=index, seconds=1)).isoformat(),
                    json.dumps(
                        {
                            "schema_version": "lean_cycle_receipt_v1",
                            "cycle_id": f"lean-cycle-{index:04d}",
                            "attempted_at": (
                                NOW + timedelta(minutes=index)
                            ).isoformat(),
                            "completed_at": (
                                NOW + timedelta(minutes=index, seconds=1)
                            ).isoformat(),
                            "trigger": "scheduled",
                            "status": "waiting",
                            "no_send": True,
                            "research_only": True,
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                )
                for index in range(MAX_CYCLE_RECEIPTS + 9)
            ],
        )
        connection.commit()

    report = store.maintain_database(evaluated_at=NOW, apply=True)

    assert report["changes"]["cycle_receipts_deleted"] == 9
    assert len(store.list_cycle_receipts(limit=MAX_CYCLE_RECEIPTS)) == MAX_CYCLE_RECEIPTS


def test_scheduled_cycle_without_authorization_makes_no_call_and_records_skip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RSI_EVENT_DISCOVERY_UNIVERSE_LIVE", raising=False)
    store = LeanRadarStore(tmp_path / "lean.db")
    now = datetime.now(timezone.utc)
    store.replace_bybit_catalog(
        (_instrument("BTC", observed_at=now),),
        imported_at=now,
    )

    code, payload = run(("--db", str(store.path), "scheduled-cycle"))
    receipt = store.list_cycle_receipts(limit=1)[0]

    assert code == 2
    assert payload["status"] == "blocked"
    assert payload["provider_call_attempted"] is False
    assert payload["telegram_send_attempted"] is False
    assert payload["cycle_receipt_status"] == "recorded"
    assert receipt["trigger"] == "scheduled"
    assert receipt["status"] == "blocked"
    assert "RSI_EVENT_DISCOVERY_UNIVERSE_LIVE=1 is absent" in receipt["skip_reason"]
    assert receipt["no_send"] is True


def test_maintenance_plist_is_no_send_and_confirmation_gated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(maintenance.sys, "platform", "darwin")
    settings = LeanRadarSettings(
        db_path=tmp_path / "lean.db",
        cadence_minutes=20,
    )
    plist_path = tmp_path / "lean.plist"
    payload = service_plist_bytes(settings)
    parsed = plistlib.loads(payload)

    assert parsed["StartInterval"] == 1_200
    assert parsed["ProgramArguments"][-1] == "scheduled-cycle"
    assert "EnvironmentVariables" not in parsed
    assert b"TELEGRAM" not in payload.upper()
    assert b"AUTH" not in payload.upper()

    blocked = install_maintenance(
        settings,
        confirm=False,
        plist_path=plist_path,
    )
    assert blocked["status"] == "confirmation_required"
    assert not plist_path.exists()


def test_owned_maintenance_install_and_uninstall_are_exact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(maintenance.sys, "platform", "darwin")
    settings = LeanRadarSettings(
        db_path=tmp_path / "lean.db",
        cadence_minutes=20,
    )
    now = datetime.now(timezone.utc)
    LeanRadarStore(settings.db_path).replace_bybit_catalog(
        (_instrument("BTC", observed_at=now),),
        imported_at=now,
    )
    plist_path = tmp_path / "lean.plist"
    loaded = False

    def runner(command: Sequence[str]) -> int:
        nonlocal loaded
        if command[1] == "print":
            return 0 if loaded else 1
        if command[1] == "bootstrap":
            loaded = True
            return 0
        if command[1] == "bootout":
            loaded = False
            return 0
        return 2

    installed = install_maintenance(
        settings,
        confirm=True,
        plist_path=plist_path,
        runner=runner,
    )
    assert installed["status"] == "installed"
    assert installed["installed_owned"] is True
    assert plist_path.stat().st_mode & 0o777 == 0o600

    disabled = uninstall_maintenance(
        settings,
        confirm=True,
        plist_path=plist_path,
        runner=runner,
    )
    assert disabled["status"] == "disabled"
    assert not plist_path.exists()


def test_maintenance_refuses_an_unowned_plist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(maintenance.sys, "platform", "darwin")
    settings = LeanRadarSettings(
        db_path=tmp_path / "lean.db",
        cadence_minutes=20,
    )
    plist_path = tmp_path / "lean.plist"
    plist_path.write_text("unowned", encoding="utf-8")

    status = maintenance_status(settings, plist_path=plist_path)
    with pytest.raises(LeanMaintenanceError, match="unowned"):
        install_maintenance(
            settings,
            confirm=True,
            plist_path=plist_path,
            runner=lambda _command: 0,
        )

    assert status["status"] == "unowned_conflict"
    assert plist_path.read_text(encoding="utf-8") == "unowned"


def test_maintenance_refuses_a_symlinked_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(maintenance.sys, "platform", "darwin")
    settings = LeanRadarSettings(
        db_path=tmp_path / "lean.db",
        cadence_minutes=20,
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    redirected = tmp_path / "LaunchAgents"
    redirected.symlink_to(outside, target_is_directory=True)
    plist_path = redirected / "lean.plist"

    status = maintenance_status(settings, plist_path=plist_path)
    with pytest.raises(LeanMaintenanceError, match="path is unsafe"):
        install_maintenance(
            settings,
            confirm=True,
            plist_path=plist_path,
            runner=lambda _command: 0,
        )

    assert status["status"] == "unsafe_path"
    assert not (outside / "lean.plist").exists()


def test_maintenance_install_requires_an_initialized_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(maintenance.sys, "platform", "darwin")
    settings = LeanRadarSettings(
        db_path=tmp_path / "missing.db",
        cadence_minutes=20,
    )
    plist_path = tmp_path / "lean.plist"

    status = maintenance_status(settings, plist_path=plist_path)
    with pytest.raises(LeanMaintenanceError, match="must be initialized"):
        install_maintenance(
            settings,
            confirm=True,
            plist_path=plist_path,
            runner=lambda _command: 0,
        )

    assert status["status"] == "setup_required"
    assert status["runtime_available"] is False
    assert not plist_path.exists()


def test_cli_maintenance_readiness_uses_the_selected_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(maintenance.sys, "platform", "darwin")
    store = LeanRadarStore(tmp_path / "selected.db")
    now = datetime.now(timezone.utc)
    store.replace_bybit_catalog(
        (_instrument("BTC", observed_at=now),),
        imported_at=now,
    )

    code, payload = run(
        ("--db", str(store.path), "maintenance-readiness")
    )

    assert code == 0
    assert payload["status"] == "ready"
    assert payload["runtime_available"] is True
    assert payload["service_state"] == "prepared_disabled"
