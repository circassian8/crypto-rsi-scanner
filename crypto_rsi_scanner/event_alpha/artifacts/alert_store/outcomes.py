"""Split implementation for `crypto_rsi_scanner/event_alpha/artifacts/alert_store.py` (outcomes)."""

from __future__ import annotations

import json
import math
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
import crypto_rsi_scanner.event_alpha.outcomes.outcome_artifacts as event_alpha_outcomes
import crypto_rsi_scanner.event_alpha.outcomes.quality_fields as event_alpha_quality_fields
import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
import crypto_rsi_scanner.event_alpha.radar.core_opportunities as event_core_opportunities
import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards
import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
import crypto_rsi_scanner.event_alpha.radar.graph as event_graph
import crypto_rsi_scanner.event_alpha.radar.playbooks as event_playbooks
from ....event_alpha.notifications import delivery as event_alpha_notification_delivery
from .models import *  # noqa: F403

def fill_alert_outcomes(
    rows: Iterable[Mapping[str, Any]],
    price_fixture_path: str | Path,
    out_path: str | Path,
    *,
    source_path: str | Path | None = None,
) -> EventAlphaOutcomeFillResult:
    """Fill forward returns and MFE/MAE from a local OHLCV price fixture."""
    source_rows = [dict(row) for row in rows]
    price_payload = _load_price_fixture(price_fixture_path)
    prices = _prices_by_symbol(price_payload.get("prices") or [])
    interval = _optional_str(price_payload.get("interval"))
    price_source = _optional_str(price_payload.get("source"))
    out_rows: list[dict[str, Any]] = []
    with_outcomes = 0
    missing = 0
    for row in source_rows:
        filled = dict(row)
        symbol = str(row.get("asset_symbol") or row.get("symbol") or "").upper()
        price_rows = prices.get(symbol, ())
        filled.setdefault("outcome_source", price_source)
        if not symbol:
            filled["outcome_status"] = "skipped_no_asset"
            missing += 1
        elif price_rows:
            outcome = _outcome_for_row(row, price_rows)
            if outcome:
                filled.update(outcome)
                filled["outcome_price_interval"] = interval
                filled["outcome_price_source"] = price_source
                filled["outcome_source"] = price_source
                filled["outcome_status"] = "filled"
                with_outcomes += 1
            else:
                filled["outcome_status"] = "stale_market_data"
                missing += 1
        else:
            filled["outcome_status"] = "insufficient_market_data"
            missing += 1
        out_rows.append(filled)
    out = Path(out_path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for row in out_rows:
            fh.write(json.dumps(_json_ready(row), sort_keys=True, separators=(",", ":")))
            fh.write("\n")
    return EventAlphaOutcomeFillResult(
        source_path=Path(source_path).expanduser() if source_path else Path(""),
        price_path=Path(price_fixture_path).expanduser(),
        out_path=out,
        rows_read=len(source_rows),
        rows_written=len(out_rows),
        rows_with_outcomes=with_outcomes,
        missing_price_rows=missing,
        interval=interval,
        price_source=price_source,
    )
def _outcome_for_row(row: Mapping[str, Any], price_rows: tuple[dict[str, Any], ...]) -> dict[str, Any] | None:
    observed = _dt(row.get("observed_at"))
    if observed is None:
        return None
    entry = _num(row.get("entry_reference_price")) or _num(row.get("market_price"))
    sorted_rows = sorted(price_rows, key=lambda item: _dt(item.get("timestamp")) or datetime.max.replace(tzinfo=timezone.utc))
    if entry is None or entry <= 0:
        first = _first_after(sorted_rows, observed)
        entry = _num(first.get("close")) if first else None
    if entry is None or entry <= 0:
        return None
    horizons = {
        "return_1h": observed + timedelta(hours=1),
        "return_4h": observed + timedelta(hours=4),
        "return_24h": observed + timedelta(hours=24),
        "return_72h": observed + timedelta(hours=72),
        "return_7d": observed + timedelta(days=7),
    }
    out: dict[str, Any] = {}
    for field, ts in horizons.items():
        price = _close_at_or_after(sorted_rows, ts)
        out[field] = None if price is None else (price - entry) / entry
    window = [
        item for item in sorted_rows
        if (dt := _dt(item.get("timestamp"))) is not None and observed <= dt <= observed + timedelta(days=7)
    ]
    expected_direction = str(row.get("expected_direction") or "")
    short_like = expected_direction == "down" or str(row.get("playbook_type") or "") == event_playbooks.EventPlaybookType.PROXY_FADE.value
    highs = [_num(item.get("high")) or _num(item.get("close")) for item in window]
    lows = [_num(item.get("low")) or _num(item.get("close")) for item in window]
    highs = [value for value in highs if value is not None]
    lows = [value for value in lows if value is not None]
    if highs and lows:
        if short_like:
            out["max_favorable_excursion"] = (entry - min(lows)) / entry
            out["max_adverse_excursion"] = (max(highs) - entry) / entry
        else:
            out["max_favorable_excursion"] = (max(highs) - entry) / entry
            out["max_adverse_excursion"] = (entry - min(lows)) / entry
    primary = str(row.get("primary_horizon") or "").strip().lower()
    primary_field = {
        "1h": "return_1h",
        "4h": "return_4h",
        "24h": "return_24h",
        "72h": "return_72h",
        "7d": "return_7d",
    }.get(primary)
    primary_return = out.get(primary_field) if primary_field else None
    out["primary_horizon_return"] = primary_return
    if expected_direction == "up" and primary_return is not None:
        out["direction_hit"] = primary_return > 0
    elif expected_direction == "down" and primary_return is not None:
        out["direction_hit"] = primary_return < 0
    else:
        out["direction_hit"] = None
    out.update(event_alpha_outcomes.compute_playbook_outcome_metrics(
        row,
        sorted_rows,
        entry_price=entry,
        observed_at=observed,
        returns=out,
    ))
    return out
def _load_price_fixture(path: str | Path) -> dict[str, Any]:
    try:
        raw = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    except Exception:
        return {"prices": []}
    return raw if isinstance(raw, dict) else {"prices": []}
def _prices_by_symbol(rows: Iterable[Mapping[str, Any]]) -> dict[str, tuple[dict[str, Any], ...]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        symbol = str(row.get("asset_symbol") or row.get("symbol") or "").upper()
        if not symbol:
            continue
        grouped.setdefault(symbol, []).append(dict(row))
    return {symbol: tuple(items) for symbol, items in grouped.items()}
def _mfe_mae_by_playbook(rows: Iterable[Mapping[str, Any]]) -> str:
    grouped: dict[str, list[tuple[float, float]]] = {}
    for row in rows:
        mfe = _num(row.get("max_favorable_excursion"))
        mae = _num(row.get("max_adverse_excursion"))
        if mfe is None or mae is None:
            continue
        grouped.setdefault(str(row.get("playbook_type") or "unknown"), []).append((mfe, mae))
    if not grouped:
        return ""
    parts = []
    for playbook, values in sorted(grouped.items()):
        avg_mfe = sum(item[0] for item in values) / len(values)
        avg_mae = sum(item[1] for item in values) / len(values)
        parts.append(f"{playbook}: MFE={avg_mfe * 100:+.1f}% MAE={avg_mae * 100:+.1f}% n={len(values)}")
    return "MFE/MAE by playbook: " + "; ".join(parts)
def _feedback_by_key(rows: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in rows:
        label = str(row.get("label") or "")
        if not label:
            continue
        for field in ("key", "target", "alert_id", "event_id", "coin_id", "symbol", "card_id"):
            key = str(row.get(field) or "").strip()
            if not key:
                continue
            out[key] = label
            if key.startswith("ea:"):
                out[key[3:]] = label
            else:
                out[f"ea:{key}"] = label
    return out
def _with_feedback(row: Mapping[str, Any], feedback_by_key: Mapping[str, str]) -> dict[str, Any]:
    out = dict(row)
    label = (
        feedback_by_key.get(str(row.get("alert_id") or ""))
        or feedback_by_key.get(str(row.get("alert_key") or ""))
        or feedback_by_key.get(str(row.get("event_id") or ""))
        or out.get("feedback_label")
    )
    out["feedback_label"] = label
    out["feedback_status"] = "reviewed" if label else out.get("feedback_status") or "pending"
    return out
def _market_anomaly_bucket(score: object) -> str:
    value = _num(score) or 0.0
    if value >= 80:
        return "extreme"
    if value >= 60:
        return "high"
    if value >= 40:
        return "medium"
    return "low"
def _btc_regime(candidate: Any) -> str:
    fade_candidate = candidate.fade_candidate
    if fade_candidate is not None and fade_candidate.rsi is not None:
        score = fade_candidate.rsi.btc_risk_on_score
        if score is not None:
            return "risk_on" if score >= 65 else "risk_off" if score <= 35 else "neutral"
    return "unknown"
