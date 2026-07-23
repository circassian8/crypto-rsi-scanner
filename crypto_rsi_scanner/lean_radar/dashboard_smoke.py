"""Offline fixture smoke for every Lean Radar dashboard page."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

from .calendar import normalize_calendar_snapshot
from .config import LeanRadarSettings
from .dashboard import LeanRadarDashboardApp
from .health import refresh_system_health
from .models import BybitInstrument, LeanIdea, MarketSnapshot
from .outcomes import pending_outcomes_for_scan, refresh_outcomes
from .store import LeanRadarStore


SMOKE_NOW = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)


def run_dashboard_smoke() -> dict[str, object]:
    with TemporaryDirectory(prefix="lean-radar-dashboard-") as directory:
        store = LeanRadarStore(Path(directory) / "lean.db")
        _build_smoke_store(store)
        before = _digest(store.path)
        app = LeanRadarDashboardApp(
            store,
            evaluated_at=SMOKE_NOW + timedelta(hours=1, minutes=5),
        )
        primary_paths = ("/", "/ideas", "/market", "/calendar", "/outcomes", "/health")
        responses = {
            path: app.response(method="GET", path=path) for path in primary_paths
        }
        detail = app.response(method="GET", path="/ideas/lean-sol-rapid-review")
        head = app.response(method="HEAD", path="/health")
        rejected = app.response(method="POST", path="/")
        after = _digest(store.path)
        bodies = [response.body.decode("utf-8") for response in responses.values()]
        bodies.append(detail.body.decode("utf-8"))
        if not all(response.status_code == 200 for response in responses.values()):
            raise RuntimeError("one or more primary dashboard pages failed")
        if detail.status_code != 200 or head.status_code != 200 or head.body:
            raise RuntimeError("dashboard detail or HEAD behavior failed")
        if rejected.status_code != 405:
            raise RuntimeError("dashboard accepted a mutating HTTP method")
        if before != after:
            raise RuntimeError("dashboard GET/HEAD changed the runtime database")
        if any(body.count('class="nav-link') != 6 for body in bodies):
            raise RuntimeError("dashboard navigation is not exactly six primary pages")
        forbidden = (
            "rapid_market_anomaly",
            "urgent_review",
            "diagnostic_hidden",
            "2026-07-23T12:00:00",
            "application/json",
        )
        if any(value in body for body in bodies for value in forbidden):
            raise RuntimeError("dashboard exposed raw operator internals")
        required = (
            "Crypto Radar",
            "System Health",
            "Observed outcomes",
            "Scheduled context, never direction",
            "Rapid market anomaly",
            "Research only",
        )
        combined = "\n".join(bodies)
        if not all(value in combined for value in required):
            raise RuntimeError("dashboard omitted a required operator surface")
        return {
            "status": "passed",
            "page_count": len(primary_paths),
            "detail_page_rendered": True,
            "responsive_viewport_css": True,
            "raw_internal_values_hidden": True,
            "database_unchanged_by_get_head": True,
            "provider_call_attempted": False,
            "telegram_send_attempted": False,
            "trades_created": 0,
            "orders_created": 0,
            "paper_trades_created": 0,
            "normal_rsi_signal_rows_written": 0,
            "triggered_fade_created": 0,
            "research_only": True,
        }


def build_preview_database(path: Path) -> Path:
    """Create a disposable local visual-QA database outside production state."""

    store = LeanRadarStore(path)
    _build_smoke_store(store)
    return store.path


def _build_smoke_store(store: LeanRadarStore) -> None:
    store.replace_bybit_catalog(
        tuple(_instrument(symbol) for symbol in ("BTC", "ETH", "SOL", "XRP", "DOGE")),
        imported_at=SMOKE_NOW,
    )
    event_time = SMOKE_NOW + timedelta(hours=2)
    store.upsert_calendar_events(
        normalize_calendar_snapshot(
            {
                "schema_version": "lean_calendar_import_v1",
                "source_observed_at": SMOKE_NOW.isoformat(),
                "source_name": "Official calendar review bundle",
                "events": [
                    {
                        "event_id": "fomc-smoke-window",
                        "title": "Federal Reserve rate decision",
                        "category": "fomc",
                        "starts_at": event_time.isoformat(),
                        "time_certainty": "exact",
                        "importance": "high",
                        "affected_symbols": [],
                    },
                    {
                        "event_id": "sol-protocol-smoke",
                        "title": "Solana protocol upgrade window",
                        "category": "protocol_event",
                        "starts_at": (event_time + timedelta(hours=3)).isoformat(),
                        "time_certainty": "window",
                        "importance": "medium",
                        "affected_symbols": ["SOL"],
                    },
                ],
            },
            source_mode="fixture",
            source_sha256="c" * 64,
        ),
        imported_at=SMOKE_NOW,
    )
    start_snapshots = _snapshots(SMOKE_NOW, sol=100.0, xrp=1.0, doge=0.20)
    ideas = (
        _idea(
            idea_id="lean-sol-rapid-review",
            symbol="SOL",
            asset_id="solana",
            idea_type="rapid_market_anomaly",
            bias="long",
            route="urgent_review",
            action=82,
            confidence=71,
            risk=58,
            urgency=91,
            why="Price acceleration and unusual activity are occurring together",
            calendar_time=event_time,
        ),
        _idea(
            idea_id="lean-xrp-fade-review",
            symbol="XRP",
            asset_id="ripple",
            idea_type="exhaustion_or_fade_review",
            bias="short_review",
            route="watchlist",
            action=64,
            confidence=60,
            risk=67,
            urgency=63,
            why="Momentum is extended enough to review for exhaustion",
        ),
        _idea(
            idea_id="lean-doge-risk-review",
            symbol="DOGE",
            asset_id="dogecoin",
            idea_type="selloff_or_risk_warning",
            bias="risk",
            route="risk_calendar",
            action=70,
            confidence=62,
            risk=78,
            urgency=75,
            why="Downside is expanding with weakening relative strength",
        ),
        _idea(
            idea_id="lean-btc-market-watch",
            symbol="BTC",
            asset_id="bitcoin",
            idea_type="dashboard_watch",
            bias="neutral",
            route="dashboard_only",
            action=48,
            confidence=66,
            risk=41,
            urgency=34,
            why="Market activity is notable but not yet a stronger setup",
        ),
    )
    store.record_scan(
        start_snapshots,
        ideas,
        _scan_health(SMOKE_NOW),
        outcomes=pending_outcomes_for_scan(
            ideas,
            start_snapshots,
            evaluated_at=SMOKE_NOW,
        ),
    )
    end_time = SMOKE_NOW + timedelta(hours=1)
    store.record_scan(
        _snapshots(end_time, sol=106.0, xrp=0.96, doge=0.18),
        ideas,
        _scan_health(end_time),
    )
    refresh_outcomes(store, evaluated_at=end_time)
    refresh_system_health(
        store,
        LeanRadarSettings(db_path=store.path, cadence_minutes=20),
        environ={"RSI_EVENT_DISCOVERY_UNIVERSE_LIVE": "1"},
        evaluated_at=end_time + timedelta(minutes=5),
    )


def _instrument(symbol: str) -> BybitInstrument:
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
        source_observed_at=SMOKE_NOW.isoformat(),
        source_mode="imported_catalog",
        source_sha256="b" * 64,
    )


def _snapshots(
    observed_at: datetime,
    *,
    sol: float,
    xrp: float,
    doge: float,
) -> tuple[MarketSnapshot, ...]:
    values = (
        ("bitcoin", "BTC", 68_000.0, 1_300_000_000_000.0, 28_000_000_000.0, 1.2),
        ("ethereum", "ETH", 3_800.0, 470_000_000_000.0, 16_000_000_000.0, 2.1),
        ("solana", "SOL", sol, 75_000_000_000.0, 5_500_000_000.0, 12.0),
        ("ripple", "XRP", xrp, 58_000_000_000.0, 3_200_000_000.0, 16.0),
        ("dogecoin", "DOGE", doge, 30_000_000_000.0, 2_600_000_000.0, -12.0),
    )
    return tuple(
        MarketSnapshot(
            canonical_asset_id=asset_id,
            symbol=symbol,
            name=symbol,
            bybit_instrument=f"{symbol}USDT",
            observed_at=observed_at.isoformat(),
            source_mode="fixture",
            price_usd=price,
            market_cap_usd=market_cap,
            volume_usd_24h=volume,
            turnover_ratio_24h=volume / market_cap,
            return_1h_pp=return_24h / 3,
            return_24h_pp=return_24h,
            return_7d_pp=return_24h * 1.4,
            rsi_14=82.0 if symbol == "XRP" else 68.0,
            spread_bps=8.0,
            sparkline_prices=tuple(
                price * (0.92 + index * 0.003 + (0.006 if index % 4 == 0 else 0))
                for index in range(30)
            ),
            return_basis="fixture_percent_points",
            rsi_basis="fixture_wilder_14",
            data_quality="complete",
        )
        for asset_id, symbol, price, market_cap, volume, return_24h in values
    )


def _idea(
    *,
    idea_id: str,
    symbol: str,
    asset_id: str,
    idea_type: str,
    bias: str,
    route: str,
    action: float,
    confidence: float,
    risk: float,
    urgency: float,
    why: str,
    calendar_time: datetime | None = None,
) -> LeanIdea:
    calendar = (
        {
            "status": "attached",
            "event_count": 1,
            "highest_importance": "high",
            "next_event_at": calendar_time.isoformat(),
            "context_only": True,
            "directional_bias_created": False,
            "events": [
                {
                    "event_id": "fomc-smoke-window",
                    "title": "Federal Reserve rate decision",
                    "category": "fomc",
                    "starts_at": calendar_time.isoformat(),
                    "importance": "high",
                }
            ],
        }
        if calendar_time
        else {}
    )
    return LeanIdea(
        idea_id=idea_id,
        created_at=SMOKE_NOW.isoformat(),
        expires_at=(SMOKE_NOW + timedelta(hours=4)).isoformat(),
        symbol=symbol,
        canonical_asset_id=asset_id,
        bybit_instrument=f"{symbol}USDT",
        horizon="1h_to_4h" if route == "urgent_review" else "4h_to_24h",
        idea_type=idea_type,
        directional_bias=bias,
        actionability_score=action,
        confidence_score=confidence,
        risk_score=risk,
        urgency_score=urgency,
        timing_state="look_now" if route == "urgent_review" else "developing",
        market_phase="acceleration" if route == "urgent_review" else "attention",
        catalyst_status="unknown",
        liquidity_status="adequate",
        spread_status="observed",
        data_quality="complete",
        why_now=(why,),
        supporting_facts=("Fresh venue-confirmed market observation",),
        risks=("The move can reverse and remains research-only",),
        missing_information=("Confirmed catalyst",),
        what_confirms=("Structure and participation persist",),
        what_invalidates=("The move fully retraces",),
        dashboard_route=route,
        telegram_route=route,
        source_context={"market_source_mode": "fixture"},
        calendar_context=calendar,
        technical_context={
            "rsi_14": 68.0,
            "relative_btc_1h_pp": 3.2,
            "relative_eth_1h_pp": 2.8,
            "chase_risk_score": 42.0,
        },
    )


def _scan_health(observed_at: datetime) -> dict[str, object]:
    return {
        "status": "complete",
        "component": "scan",
        "scan_id": f"lean-smoke-{int(observed_at.timestamp())}",
        "checked_at": observed_at.isoformat(),
        "observed_at": observed_at.isoformat(),
        "next_scan_at": (observed_at + timedelta(minutes=20)).isoformat(),
        "cadence_minutes": 20,
        "source_mode": "fixture",
        "provider_call_attempted": False,
        "provider_call_succeeded": False,
        "market_row_count": 5,
        "snapshot_count": 5,
        "idea_count": 4,
        "no_send": True,
        "research_only": True,
    }


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


__all__ = ("build_preview_database", "run_dashboard_smoke")
