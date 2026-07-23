from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from crypto_rsi_scanner.lean_radar.config import LeanRadarSettings
from crypto_rsi_scanner.lean_radar.health import refresh_system_health
from crypto_rsi_scanner.lean_radar.models import (
    BybitInstrument,
    LeanIdea,
    MarketSnapshot,
)
from crypto_rsi_scanner.lean_radar.outcomes import (
    pending_outcomes_for_scan,
    refresh_outcomes,
)
from crypto_rsi_scanner.lean_radar.store import LeanRadarStore


NOW = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)


def _snapshot(
    asset_id: str,
    symbol: str,
    price: float,
    observed_at: datetime,
) -> MarketSnapshot:
    return MarketSnapshot(
        canonical_asset_id=asset_id,
        symbol=symbol,
        name=symbol,
        bybit_instrument=f"{symbol}USDT",
        observed_at=observed_at.isoformat(),
        source_mode="fixture",
        price_usd=price,
        market_cap_usd=1_000_000_000.0,
        volume_usd_24h=100_000_000.0,
        turnover_ratio_24h=0.1,
        return_1h_pp=0.0,
        return_24h_pp=0.0,
        return_7d_pp=0.0,
        rsi_14=50.0,
        spread_bps=10.0,
        sparkline_prices=tuple(100.0 for _ in range(20)),
        return_basis="fixture_percent_points",
        rsi_basis="fixture_wilder_14",
        data_quality="complete",
    )


def _idea(
    *,
    idea_id: str = "lean-sol-outcome",
    directional_bias: str = "long",
    idea_type: str = "market_breakout_long",
    expires_at: datetime | None = None,
) -> LeanIdea:
    return LeanIdea(
        idea_id=idea_id,
        created_at=NOW.isoformat(),
        expires_at=(expires_at or NOW + timedelta(hours=4)).isoformat(),
        symbol="SOL",
        canonical_asset_id="solana",
        bybit_instrument="SOLUSDT",
        horizon="4h",
        idea_type=idea_type,
        directional_bias=directional_bias,
        actionability_score=70.0,
        confidence_score=60.0,
        risk_score=45.0,
        urgency_score=65.0,
        timing_state="active",
        market_phase="breakout",
        catalyst_status="unknown",
        liquidity_status="adequate",
        spread_status="observed",
        data_quality="complete",
        why_now=("Point-in-time move",),
        supporting_facts=("Fixture fact",),
        risks=("Research uncertainty",),
        missing_information=("Catalyst",),
        what_confirms=("Follow-through",),
        what_invalidates=("Full reversal",),
        dashboard_route="watchlist",
        telegram_route="watchlist",
    )


def _health(observed_at: datetime, *, provider: bool = False) -> dict[str, object]:
    return {
        "status": "complete",
        "component": "scan",
        "scan_id": f"scan-{int(observed_at.timestamp())}",
        "checked_at": observed_at.isoformat(),
        "observed_at": observed_at.isoformat(),
        "next_scan_at": (observed_at + timedelta(minutes=20)).isoformat(),
        "source_mode": "fixture",
        "provider_call_attempted": provider,
        "provider_call_succeeded": provider,
        "provider_attempted_at": observed_at.isoformat() if provider else None,
        "research_only": True,
    }


def _record_start(store: LeanRadarStore, idea: LeanIdea) -> None:
    snapshots = (
        _snapshot("bitcoin", "BTC", 100.0, NOW),
        _snapshot("ethereum", "ETH", 100.0, NOW),
        _snapshot("solana", "SOL", 100.0, NOW),
    )
    store.record_scan(
        snapshots,
        (idea,),
        _health(NOW),
        outcomes=pending_outcomes_for_scan((idea,), snapshots, evaluated_at=NOW),
    )


def _record_prices(
    store: LeanRadarStore,
    offset: timedelta,
    *,
    btc: float,
    eth: float,
    sol: float,
) -> None:
    observed = NOW + offset
    store.record_scan(
        (
            _snapshot("bitcoin", "BTC", btc, observed),
            _snapshot("ethereum", "ETH", eth, observed),
            _snapshot("solana", "SOL", sol, observed),
        ),
        (),
        _health(observed),
    )


def test_outcomes_mature_from_exact_retained_path_without_provider_call(
    tmp_path: Path,
) -> None:
    store = LeanRadarStore(tmp_path / "lean.db")
    idea = _idea()
    _record_start(store, idea)
    _record_prices(store, timedelta(minutes=20), btc=100.5, eth=100.2, sol=99.0)
    _record_prices(store, timedelta(minutes=40), btc=101.0, eth=100.5, sol=103.0)
    _record_prices(store, timedelta(hours=1), btc=102.0, eth=101.0, sol=105.0)

    report = refresh_outcomes(store, evaluated_at=NOW + timedelta(hours=1))
    one_hour = next(
        row
        for row in store.list_outcomes()
        if row["idea_id"] == idea.idea_id and row["horizon"] == "1h"
    )

    assert report["matured_count"] == 1
    assert report["pending_count"] == 3
    assert report["provider_call_attempted"] is False
    assert report["automatic_threshold_changes"] == 0
    assert report["human_labels_required"] is False
    assert one_hour["status"] == "matured"
    assert one_hour["result"] == "continued"
    assert one_hour["return_pp"] == pytest.approx(5.0)
    assert one_hour["relative_btc_pp"] == pytest.approx(3.0)
    assert one_hour["relative_eth_pp"] == pytest.approx(4.0)
    assert one_hour["mfe_pp"] == pytest.approx(5.0)
    assert one_hour["mae_pp"] == pytest.approx(-1.0)
    assert one_hour["path_snapshot_count"] == 4
    stored_idea = next(row for row in store.list_ideas() if row["idea_id"] == idea.idea_id)
    assert stored_idea["outcome_status"] == "partial"


def test_missing_endpoint_becomes_unresolved_without_backfill(
    tmp_path: Path,
) -> None:
    store = LeanRadarStore(tmp_path / "lean.db")
    idea = _idea(expires_at=NOW + timedelta(hours=1))
    _record_start(store, idea)
    _record_prices(store, timedelta(hours=2), btc=102.0, eth=103.0, sol=110.0)

    report = refresh_outcomes(
        store,
        evaluated_at=NOW + timedelta(hours=2),
    )
    one_hour = next(row for row in store.list_outcomes() if row["horizon"] == "1h")

    assert report["unresolved_count"] == 1
    assert one_hour["status"] == "unresolved"
    assert one_hour["result"] == "unresolved"
    assert one_hour["return_pp"] is None
    assert one_hour["expired"] is True
    assert "No endpoint snapshot" in one_hour["missing_information"][-1]


def test_risk_warning_is_validated_only_by_observed_downside(tmp_path: Path) -> None:
    store = LeanRadarStore(tmp_path / "lean.db")
    idea = _idea(
        idea_id="lean-sol-risk",
        directional_bias="risk",
        idea_type="selloff_or_risk_warning",
    )
    _record_start(store, idea)
    _record_prices(store, timedelta(hours=1), btc=99.0, eth=98.0, sol=95.0)

    refresh_outcomes(store, evaluated_at=NOW + timedelta(hours=1))
    one_hour = next(row for row in store.list_outcomes() if row["horizon"] == "1h")

    assert one_hour["result"] == "risk_warning_validated"
    assert one_hour["return_pp"] == pytest.approx(-5.0)
    assert one_hour["mfe_pp"] == pytest.approx(5.0)
    assert one_hour["mae_pp"] == pytest.approx(0.0)


def test_neutral_idea_does_not_invent_directional_excursions(tmp_path: Path) -> None:
    store = LeanRadarStore(tmp_path / "lean.db")
    idea = _idea(
        idea_id="lean-sol-neutral",
        directional_bias="neutral",
        idea_type="dashboard_watch",
    )
    _record_start(store, idea)
    _record_prices(store, timedelta(hours=1), btc=101.0, eth=101.0, sol=105.0)

    refresh_outcomes(store, evaluated_at=NOW + timedelta(hours=1))
    one_hour = next(row for row in store.list_outcomes() if row["horizon"] == "1h")

    assert one_hour["result"] == "inconclusive"
    assert one_hour["mfe_pp"] is None
    assert one_hour["mae_pp"] is None
    assert "neutral idea" in one_hour["missing_information"][0]


def test_system_health_separates_current_authorization_from_last_call(
    tmp_path: Path,
) -> None:
    store = LeanRadarStore(tmp_path / "lean.db")
    store.replace_bybit_catalog(
        (
            BybitInstrument(
                instrument_id="SOLUSDT",
                base_coin="SOL",
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
                source_observed_at=NOW.isoformat(),
                source_mode="imported_catalog",
                source_sha256="a" * 64,
            ),
        ),
        imported_at=NOW,
    )
    store.record_health("scan", _health(NOW, provider=True))

    report = refresh_system_health(
        store,
        LeanRadarSettings(db_path=store.path, cadence_minutes=20),
        environ={},
        evaluated_at=NOW + timedelta(minutes=5),
    )

    assert report["current_authorization_status"] == "absent"
    assert report["current_provider_call_eligibility"] == "authorization_absent"
    assert report["last_provider_call_attempted"] is True
    assert report["last_provider_call_succeeded"] is True
    assert report["data_freshness"] == "fresh"
    assert report["provider_call_attempted"] is False
    assert report["telegram_mode"] == "preview_only"
    assert report["telegram"]["preview_ready"] is True
    assert report["telegram"]["current_send_eligibility"] == "blocked"
    assert store.health_status("operator") == report


def test_outcomes_and_health_missing_store_are_safe_and_no_write(tmp_path: Path) -> None:
    store = LeanRadarStore(tmp_path / "missing.db")
    outcome_report = refresh_outcomes(store, evaluated_at=NOW)
    health_report = refresh_system_health(
        store,
        LeanRadarSettings(db_path=store.path, cadence_minutes=20),
        environ={},
        evaluated_at=NOW,
    )

    assert outcome_report["status"] == "setup_required"
    assert health_report["status"] == "setup_required"
    assert outcome_report["provider_call_attempted"] is False
    assert health_report["provider_call_attempted"] is False
    assert not store.path.exists()
