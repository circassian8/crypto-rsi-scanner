"""Split implementation for `crypto_rsi_scanner/event_alpha/artifacts/alert_store.py` (store)."""

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

def write_alert_snapshots(
    alerts: Iterable[event_alerts.EventAlertCandidate],
    *,
    cfg: EventAlphaAlertStoreConfig,
    now: datetime | None = None,
    router_result: Any | None = None,
    run_id: str | None = None,
    profile: str | None = None,
    run_mode: str | None = None,
    artifact_namespace: str | None = None,
    delivery_rows: Iterable[Mapping[str, Any]] = (),
    research_card_paths: Iterable[str | Path] = (),
    core_opportunity_rows: Iterable[Mapping[str, Any]] = (),
) -> EventAlphaAlertStoreWriteResult:
    """Append research-only alert snapshots to JSONL."""
    observed = _as_utc(now or datetime.now(timezone.utc))
    rows = [_snapshot_from_alert(alert, observed) for alert in alerts]
    existing_keys = {str(row.get("alert_key") or "") for row in rows}
    route_rows = [
        _snapshot_from_route_decision(decision, observed)
        for decision in _route_decisions_for_snapshots(router_result)
        if str(getattr(decision.entry, "key", "") or "") not in existing_keys
    ]
    rows.extend(route_rows)
    rows = [
        _with_artifact_context(
            row,
            run_id=run_id,
            profile=profile,
            run_mode=run_mode,
            artifact_namespace=artifact_namespace,
        )
        for row in rows
    ]
    core_rows = [dict(row) for row in core_opportunity_rows if isinstance(row, Mapping)]
    route_context = _route_context_by_key(router_result)
    rows = [_with_route_context(row, route_context) for row in rows]
    delivery_context = _delivery_context_by_alert_id(delivery_rows)
    card_context = _card_context_by_card_id(research_card_paths)
    rows = [_with_delivery_context(row, delivery_context) for row in rows]
    rows = [_with_card_context(row, card_context) for row in rows]
    if core_rows:
        rows = [_with_core_resolution(row, core_rows) for row in rows]
    rows = _dedupe_canonical_alertable_snapshot_rows(rows)
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
        attempted=True,
        success=True,
    )
def blocked_alert_snapshot_write(
    *,
    cfg: EventAlphaAlertStoreConfig,
    now: datetime | None = None,
    reason: str,
) -> EventAlphaAlertStoreWriteResult:
    """Return a no-write result for intentionally blocked artifact writes."""
    observed = _as_utc(now or datetime.now(timezone.utc))
    return EventAlphaAlertStoreWriteResult(
        path=cfg.path.expanduser(),
        observed_at=observed.isoformat(),
        rows_written=0,
        attempted=False,
        success=False,
        block_reason=reason,
    )
def load_alert_snapshots(path: str | Path, *, latest_only: bool = False) -> EventAlphaAlertStoreReadResult:
    p = Path(path).expanduser()
    rows = [
        row for row in _read_jsonl(p)
        if row.get("row_type") == "event_alpha_alert_snapshot"
    ]
    rows = reconcile_alert_snapshots_with_core_store(rows, _sibling_core_store_rows(p))
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
def format_alert_store_write_result(result: EventAlphaAlertStoreWriteResult) -> str:
    return "\n".join([
        "=" * 76,
        "EVENT ALPHA ALERT SNAPSHOTS WRITTEN (research artifact only)",
        "=" * 76,
        f"path: {result.path}",
        f"observed_at: {result.observed_at}",
        f"rows_written: {result.rows_written}",
        f"attempted: {str(bool(result.attempted)).lower()}",
        f"success: {str(bool(result.success)).lower()}",
        *([f"block_reason: {result.block_reason}"] if result.block_reason else []),
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
        ("by final route", "final_route_after_quality_gate"),
        ("by legacy route", "route"),
        ("by snapshot quality classification", "snapshot_quality_classification"),
        ("by delivered status", "delivered_status"),
        ("by feedback status", "feedback_status"),
        ("by impact path type", "impact_path_type"),
        ("by impact path strength", "impact_path_strength"),
        ("by candidate role", "candidate_role"),
        ("by opportunity level", "opportunity_level"),
        ("by market confirmation", "market_confirmation_level"),
        ("by evidence source class", "source_class"),
        ("by evidence specificity", "evidence_specificity"),
        ("by LLM role", "llm_asset_role"),
        ("by source", "source"),
        ("by BTC regime", "btc_regime"),
        ("by market anomaly score", "market_anomaly_bucket"),
        ("by thesis origin", "thesis_origin"),
        ("by catalyst status", "catalyst_status"),
        ("by confidence band", "confidence_band"),
        ("by actionability score cohort", "actionability_score_cohort"),
        ("by anomaly type", "anomaly_type"),
        ("by radar route", "radar_route"),
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
            f"{row.get('final_tier_after_quality_gate') or row.get('tier', 'UNKNOWN'):<20} "
            f"score={int(row.get('opportunity_score') or 0):>3} "
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
        if row.get("route") or row.get("delivered_status") or row.get("research_card_path"):
            out.append(
                f"  route: final={row.get('final_route_after_quality_gate') or row.get('route') or 'none'} "
                f"legacy={row.get('route') or 'none'} lane={row.get('lane') or 'none'} "
                f"class={row.get('snapshot_quality_classification') or classify_alert_snapshot(row)} "
                f"delivered={row.get('delivered_status') or 'unknown'} feedback={row.get('feedback_status') or 'pending'}"
            )
            if row.get("research_card_path"):
                out.append(f"  card: {row.get('research_card_path')}")
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
