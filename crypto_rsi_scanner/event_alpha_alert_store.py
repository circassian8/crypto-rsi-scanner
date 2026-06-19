"""Research-only Event Alpha alert snapshot and outcome artifacts."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import event_alerts, event_alpha_outcomes, event_graph, event_playbooks

ALERT_STORE_SCHEMA_VERSION = "event_alpha_alert_snapshot_v1"


@dataclass(frozen=True)
class EventAlphaAlertStoreConfig:
    path: Path
    snapshot_policy: str = "all"
    sampled_controls_limit: int = 25


@dataclass(frozen=True)
class EventAlphaAlertStoreWriteResult:
    path: Path
    observed_at: str
    rows_written: int


@dataclass(frozen=True)
class EventAlphaAlertStoreReadResult:
    path: Path
    rows_read: int
    rows: list[dict[str, Any]]


@dataclass(frozen=True)
class EventAlphaOutcomeFillResult:
    source_path: Path
    price_path: Path
    out_path: Path
    rows_read: int
    rows_written: int
    rows_with_outcomes: int
    missing_price_rows: int
    interval: str | None
    price_source: str | None


def write_alert_snapshots(
    alerts: Iterable[event_alerts.EventAlertCandidate],
    *,
    cfg: EventAlphaAlertStoreConfig,
    now: datetime | None = None,
    router_result: Any | None = None,
) -> EventAlphaAlertStoreWriteResult:
    """Append research-only alert snapshots to JSONL."""
    observed = _as_utc(now or datetime.now(timezone.utc))
    rows = [_snapshot_from_alert(alert, observed) for alert in alerts]
    route_context = _route_context_by_key(router_result)
    rows = [_with_route_context(row, route_context) for row in rows]
    rows = _filter_snapshot_rows(
        rows,
        policy=cfg.snapshot_policy,
        sampled_controls_limit=cfg.sampled_controls_limit,
        route_context=route_context,
    )
    cfg.path.expanduser().parent.mkdir(parents=True, exist_ok=True)
    with cfg.path.expanduser().open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(_json_ready(row), sort_keys=True, separators=(",", ":")))
            fh.write("\n")
    return EventAlphaAlertStoreWriteResult(
        path=cfg.path.expanduser(),
        observed_at=observed.isoformat(),
        rows_written=len(rows),
    )


def load_alert_snapshots(path: str | Path, *, latest_only: bool = False) -> EventAlphaAlertStoreReadResult:
    p = Path(path).expanduser()
    rows = [
        row for row in _read_jsonl(p)
        if row.get("row_type") == "event_alpha_alert_snapshot"
    ]
    if latest_only:
        latest: dict[str, tuple[str, int, dict[str, Any]]] = {}
        for idx, row in enumerate(rows):
            key = str(row.get("alert_key") or row.get("snapshot_id") or idx)
            observed = str(row.get("observed_at") or "")
            current = latest.get(key)
            if current is None or (observed, idx) >= (current[0], current[1]):
                latest[key] = (observed, idx, row)
        rows = [item[2] for item in latest.values()]
    return EventAlphaAlertStoreReadResult(path=p, rows_read=len(rows), rows=rows)


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
        if price_rows:
            outcome = _outcome_for_row(row, price_rows)
            if outcome:
                filled.update(outcome)
                filled["outcome_price_interval"] = interval
                filled["outcome_price_source"] = price_source
                with_outcomes += 1
            else:
                missing += 1
        else:
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


def format_alert_store_write_result(result: EventAlphaAlertStoreWriteResult) -> str:
    return "\n".join([
        "=" * 76,
        "EVENT ALPHA ALERT SNAPSHOTS WRITTEN (research artifact only)",
        "=" * 76,
        f"path: {result.path}",
        f"observed_at: {result.observed_at}",
        f"rows_written: {result.rows_written}",
        "No live RSI alerts, paper trades, live DB rows, or execution were changed.",
    ])


def format_alert_snapshot_report(
    result: EventAlphaAlertStoreReadResult,
    *,
    feedback_rows: Iterable[Mapping[str, Any]] = (),
) -> str:
    rows = list(result.rows)
    feedback_by_key = _feedback_by_key(feedback_rows)
    rows = [_with_feedback(row, feedback_by_key) for row in rows]
    out = [
        "=" * 76,
        "EVENT ALPHA ALERT SNAPSHOT REPORT (research artifact only)",
        "=" * 76,
        f"path: {result.path}",
        f"rows_read: {result.rows_read}",
    ]
    if not rows:
        out.append("")
        out.append("No alert snapshots found.")
        return "\n".join(out)
    for label, field in (
        ("by playbook", "playbook_type"),
        ("by expected direction", "expected_direction"),
        ("by tier", "tier"),
        ("by LLM role", "llm_asset_role"),
        ("by source", "source"),
        ("by BTC regime", "btc_regime"),
        ("by market anomaly score", "market_anomaly_bucket"),
        ("by feedback label", "feedback_label"),
    ):
        out.append(_cohort_line(label, rows, field))
    mfe_mae = _mfe_mae_by_playbook(rows)
    if mfe_mae:
        out.append(mfe_mae)
    outcome_metrics = event_alpha_outcomes.summarize_outcome_metrics(rows)
    if outcome_metrics:
        out.append(outcome_metrics)
    out.append("")
    for row in sorted(rows, key=lambda item: str(item.get("observed_at") or ""), reverse=True)[:20]:
        out.append(
            f"{row.get('tier', 'UNKNOWN'):<20} score={int(row.get('opportunity_score') or 0):>3} "
            f"{row.get('asset_symbol', 'UNKNOWN')}/{row.get('asset_coin_id', 'unknown')} "
            f"playbook={row.get('playbook_type') or 'unknown'}"
        )
        out.append(f"  event: {row.get('event_name') or 'unknown'}")
        if row.get("return_24h") is not None:
            out.append(
                "  outcomes: "
                f"primary={_fmt_pct(row.get('primary_horizon_return'))} "
                f"hit={_fmt_bool(row.get('direction_hit'))} "
                f"1h={_fmt_pct(row.get('return_1h'))} "
                f"4h={_fmt_pct(row.get('return_4h'))} "
                f"24h={_fmt_pct(row.get('return_24h'))} "
                f"72h={_fmt_pct(row.get('return_72h'))} "
                f"7d={_fmt_pct(row.get('return_7d'))} "
                f"MFE={_fmt_pct(row.get('max_favorable_excursion'))} "
                f"MAE={_fmt_pct(row.get('max_adverse_excursion'))} "
                f"vol={_fmt_bool(row.get('volatility_hit'))} "
                f"up_fade={_fmt_bool(row.get('up_then_fade_hit'))}"
            )
    return "\n".join(out).rstrip()


def format_outcome_fill_result(result: EventAlphaOutcomeFillResult) -> str:
    return "\n".join([
        "=" * 76,
        "EVENT ALPHA ALERT OUTCOMES FILLED (research artifact only)",
        "=" * 76,
        f"price_path: {result.price_path}",
        f"out_path: {result.out_path}",
        f"rows_read: {result.rows_read} · rows_written: {result.rows_written}",
        f"rows_with_outcomes: {result.rows_with_outcomes} · missing_price_rows: {result.missing_price_rows}",
        f"price_source: {result.price_source or 'unknown'} · interval: {result.interval or 'unknown'}",
        "No live RSI alerts, paper trades, live DB rows, or execution were changed.",
    ])


def _snapshot_from_alert(alert: event_alerts.EventAlertCandidate, observed: datetime) -> dict[str, Any]:
    candidate = alert.discovery_candidate
    fade_candidate = candidate.fade_candidate
    signal = candidate.fade_signal
    market = fade_candidate.market if fade_candidate is not None else None
    entry = None
    if signal is not None:
        entry = signal.entry_reference_price
    if entry is None and market is not None:
        entry = market.price
    cluster_id = event_graph.cluster_id_for_event(candidate.event)
    effective_playbook = alert.effective_playbook_type or alert.playbook_type or candidate.classification.relationship_type
    alert_key = f"{cluster_id}|{candidate.asset.coin_id}|{effective_playbook}"
    observed_iso = observed.isoformat()
    return {
        "schema_version": ALERT_STORE_SCHEMA_VERSION,
        "row_type": "event_alpha_alert_snapshot",
        "snapshot_id": f"{observed_iso}|{alert_key}",
        "alert_key": alert_key,
        "cluster_id": cluster_id,
        "observed_at": observed_iso,
        "event_id": candidate.event.event_id,
        "event_name": candidate.event.event_name,
        "event_type": candidate.event.event_type,
        "event_time": candidate.event.event_time.isoformat() if candidate.event.event_time else None,
        "external_asset": candidate.event.external_asset,
        "asset_coin_id": candidate.asset.coin_id,
        "asset_symbol": candidate.asset.symbol,
        "asset_name": candidate.asset.name,
        "relationship_type": candidate.classification.relationship_type,
        "asset_role": candidate.classification.asset_role,
        "source": candidate.event.source,
        "source_count": len(candidate.event.raw_ids),
        "tier": alert.tier.value,
        "opportunity_score": alert.opportunity_score,
        "score_before_priors": alert.score_before_priors,
        "score_after_priors": alert.score_after_priors,
        "prior_file": alert.prior_file,
        "prior_version": alert.prior_version,
        "prior_generated_at": alert.prior_generated_at,
        "prior_multipliers_applied": dict(alert.prior_multipliers_applied),
        "score_components": dict(alert.score_components),
        "playbook_type": effective_playbook,
        "rule_playbook_type": alert.rule_playbook_type,
        "effective_playbook_type": effective_playbook,
        "llm_adjusted_playbook_type": alert.llm_adjusted_playbook_type,
        "playbook_score": alert.playbook_score,
        "playbook_action": alert.playbook_action,
        "playbook_hypothesis": alert.playbook_hypothesis,
        "playbook_what_to_verify": list(alert.playbook_what_to_verify),
        "playbook_timing_window": alert.playbook_timing_window,
        "playbook_invalidation": alert.playbook_invalidation,
        "llm_asset_role": alert.llm_asset_role,
        "llm_relationship_type": alert.llm_relationship_type,
        "llm_confidence": alert.llm_confidence,
        "expected_direction": alert.expected_direction,
        "primary_horizon": alert.primary_horizon,
        "success_metric": alert.success_metric,
        "entry_reference_price": entry,
        "market_price": market.price if market else None,
        "return_24h_at_alert": market.return_24h if market else None,
        "return_72h_at_alert": market.return_72h if market else None,
        "return_7d_at_alert": market.return_7d if market else None,
        "volume_zscore_24h": market.volume_zscore_24h if market else None,
        "market_anomaly_bucket": _market_anomaly_bucket(alert.score_components.get("market_move_volume", 0)),
        "btc_regime": _btc_regime(candidate),
        "signal_type": signal.signal_type.value if signal else None,
        "fade_state": signal.state.value if signal else None,
        "reason": alert.reason,
        "verify": list(alert.verify),
        "rejected_reason": alert.rejected_reason,
    }


def _route_context_by_key(router_result: Any | None) -> dict[str, dict[str, Any]]:
    if router_result is None:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for decision in getattr(router_result, "decisions", ()) or ():
        entry = getattr(decision, "entry", None)
        key = str(getattr(entry, "key", "") or "")
        if not key:
            continue
        route = getattr(decision, "route", "")
        out[key] = {
            "alert_id": getattr(decision, "alert_id", f"ea:{key}"),
            "card_id": getattr(decision, "card_id", ""),
            "route": getattr(route, "value", str(route)),
            "route_alertable": bool(getattr(decision, "alertable", False)),
            "route_reason": str(getattr(decision, "reason", "") or ""),
        }
    return out


def _with_route_context(row: dict[str, Any], route_context: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    context = route_context.get(str(row.get("alert_key") or ""))
    if not context:
        return row
    out = dict(row)
    out.update(context)
    return out


def _filter_snapshot_rows(
    rows: list[dict[str, Any]],
    *,
    policy: str,
    sampled_controls_limit: int,
    route_context: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    mode = (policy or "all").strip().lower()
    if mode == "all":
        return rows
    if mode == "non_store":
        return [row for row in rows if row.get("tier") != event_alerts.EventAlertTier.STORE_ONLY.value]
    if mode == "routed":
        if not route_context:
            return rows
        return [row for row in rows if str(row.get("alert_key") or "") in route_context]
    if mode == "alertable":
        if not route_context:
            return []
        return [
            row for row in rows
            if bool(route_context.get(str(row.get("alert_key") or ""), {}).get("route_alertable"))
        ]
    if mode == "sampled_controls":
        limit = max(0, int(sampled_controls_limit))
        kept: list[dict[str, Any]] = []
        controls = 0
        for row in rows:
            if row.get("tier") != event_alerts.EventAlertTier.STORE_ONLY.value:
                kept.append(row)
            elif controls < limit:
                kept.append(row)
                controls += 1
        return kept
    return rows


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


def _first_after(rows: Iterable[Mapping[str, Any]], ts: datetime) -> Mapping[str, Any] | None:
    for row in rows:
        row_ts = _dt(row.get("timestamp"))
        if row_ts is not None and row_ts >= ts:
            return row
    return None


def _close_at_or_after(rows: Iterable[Mapping[str, Any]], ts: datetime) -> float | None:
    row = _first_after(rows, ts)
    return _num(row.get("close")) if row else None


def _cohort_line(label: str, rows: Iterable[Mapping[str, Any]], field: str) -> str:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get(field) or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return f"{label}: " + ", ".join(f"{key}={count}" for key, count in sorted(counts.items()))


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
        key = str(row.get("key") or "")
        label = str(row.get("label") or "")
        if key and label:
            out[key] = label
    return out


def _with_feedback(row: Mapping[str, Any], feedback_by_key: Mapping[str, str]) -> dict[str, Any]:
    out = dict(row)
    out["feedback_label"] = feedback_by_key.get(str(row.get("alert_key") or "")) or out.get("feedback_label")
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


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _optional_str(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _dt(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return _as_utc(value)
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return _as_utc(parsed)


def _num(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _fmt_pct(value: object) -> str:
    num = _num(value)
    return "n/a" if num is None else f"{num * 100:+.1f}%"


def _fmt_bool(value: object) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "n/a"


def _json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return _as_utc(value).isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_ready(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(child) for child in value]
    return value


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
