"""Research-only Event Alpha alert snapshot and outcome artifacts."""

from __future__ import annotations

import json
import math
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import (
    event_alerts,
    event_alpha_notification_delivery,
    event_alpha_outcomes,
    event_alpha_quality_fields,
    event_alpha_router,
    event_core_opportunities,
    event_research_cards,
    event_watchlist,
    event_graph,
    event_playbooks,
)

ALERT_STORE_SCHEMA_VERSION = "event_alpha_alert_snapshot_v1"

SNAPSHOT_CURRENT_CLEAN = "current_clean"
SNAPSHOT_QUALITY_GATED_LOCAL = "quality_gated_local"
SNAPSHOT_LEGACY_CONFLICT = "legacy_conflict"
SNAPSHOT_MISSING_FINAL_ROUTE = "missing_final_route"
SNAPSHOT_STALE_PRE_QUALITY_GATE = "stale_pre_quality_gate"
SNAPSHOT_CORE_RECONCILED = "core_reconciled"
SNAPSHOT_MISSING_CORE = "missing_core"

LEGACY_CONFLICT_CLASSIFICATIONS = {
    SNAPSHOT_LEGACY_CONFLICT,
    SNAPSHOT_MISSING_FINAL_ROUTE,
    SNAPSHOT_STALE_PRE_QUALITY_GATE,
}


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
    attempted: bool = True
    success: bool = True
    block_reason: str | None = None


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


def reconcile_alert_snapshots_with_core_store(
    snapshots: Iterable[Mapping[str, Any]],
    core_store_rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Apply canonical core final state to alert snapshots when possible."""
    core_rows = [dict(row) for row in core_store_rows if isinstance(row, Mapping)]
    if not core_rows:
        return [dict(row) for row in snapshots if isinstance(row, Mapping)]
    return [_with_core_resolution(dict(row), core_rows) for row in snapshots if isinstance(row, Mapping)]


def reconcile_alert_snapshot_with_core_store(
    snapshot: Mapping[str, Any],
    core_store_row: Mapping[str, Any],
) -> dict[str, Any]:
    """Mirror final operator-facing fields from a canonical CoreOpportunity row."""
    out = dict(snapshot)
    core = dict(core_store_row)
    requested_route = str(out.get("final_route_after_quality_gate") or out.get("route") or "")
    requested_level = str(out.get("final_opportunity_level") or out.get("opportunity_level") or "")
    requested_state = str(out.get("final_state_after_quality_gate") or out.get("state") or "")
    out.setdefault("requested_route_before_core_reconciliation", requested_route)
    out.setdefault("requested_opportunity_level_before_core_reconciliation", requested_level)
    out.setdefault("requested_state_before_core_reconciliation", requested_state)

    final_level = str(core.get("final_opportunity_level") or core.get("opportunity_level") or requested_level or "")
    final_score = _first_present(core, ("final_opportunity_score", "opportunity_score_final"))
    final_route = str(core.get("final_route_after_quality_gate") or core.get("route") or requested_route or "")
    final_state = str(core.get("final_state_after_quality_gate") or core.get("state") or requested_state or "")
    final_tier = _tier_for_final_route(final_route, out.get("requested_tier_before_quality_gate") or out.get("tier"), core)

    mirror_fields = {
        "symbol": core.get("symbol") or core.get("validated_symbol") or out.get("symbol"),
        "coin_id": core.get("coin_id") or core.get("validated_coin_id") or out.get("coin_id"),
        "asset_symbol": core.get("symbol") or core.get("validated_symbol") or out.get("asset_symbol"),
        "asset_coin_id": core.get("coin_id") or core.get("validated_coin_id") or out.get("asset_coin_id"),
        "validated_symbol": core.get("validated_symbol") or core.get("symbol") or out.get("validated_symbol"),
        "validated_coin_id": core.get("validated_coin_id") or core.get("coin_id") or out.get("validated_coin_id"),
        "final_opportunity_level": final_level,
        "opportunity_level": final_level,
        "final_opportunity_score": final_score,
        "opportunity_score_final": final_score,
        "opportunity_score": final_score if final_score is not None else out.get("opportunity_score"),
        "final_route_after_quality_gate": final_route,
        "route": final_route,
        "lane": event_alpha_router.lane_value_for_route_value(final_route),
        "final_state_after_quality_gate": final_state,
        "state": final_state,
        "final_tier_after_quality_gate": final_tier,
        "tier": final_tier,
        "final_verdict_source": core.get("final_verdict_source") or out.get("final_verdict_source"),
        "final_verdict_reason": core.get("final_verdict_reason") or out.get("final_verdict_reason"),
        "evidence_acquisition_status": core.get("evidence_acquisition_status") or out.get("evidence_acquisition_status"),
        "acquisition_confirmation_status": core.get("acquisition_confirmation_status") or out.get("acquisition_confirmation_status"),
        "acquisition_confirms_candidate": core.get("acquisition_confirms_candidate", out.get("acquisition_confirms_candidate")),
        "acquisition_confirms_impact_path": core.get("acquisition_confirms_impact_path", out.get("acquisition_confirms_impact_path")),
        "source_pack_confirmation_status": core.get("source_pack_confirmation_status") or out.get("source_pack_confirmation_status"),
        "live_confirmation_required": core.get("live_confirmation_required", out.get("live_confirmation_required")),
        "live_confirmation_passed": core.get("live_confirmation_passed", out.get("live_confirmation_passed")),
        "live_confirmation_status": core.get("live_confirmation_status") or out.get("live_confirmation_status"),
        "live_confirmation_reason": core.get("live_confirmation_reason") or out.get("live_confirmation_reason"),
        "live_confirmation_capped": core.get("live_confirmation_capped", out.get("live_confirmation_capped")),
        "live_confirmation_missing_requirements": core.get("live_confirmation_missing_requirements") or out.get("live_confirmation_missing_requirements"),
        "quality_gate_block_reason": (
            core.get("quality_gate_block_reason")
            or core.get("canonical_route_adjustment_reason")
            or out.get("quality_gate_block_reason")
        ),
        "feedback_target": core.get("feedback_target") or core.get("core_opportunity_id") or out.get("feedback_target"),
        "feedback_target_type": core.get("feedback_target_type") or "core_opportunity_id",
        "core_opportunity_id": core.get("core_opportunity_id") or out.get("core_opportunity_id"),
    }
    for key, value in mirror_fields.items():
        if value is not None:
            out[key] = value

    out["alertable_after_quality_gate"] = event_alpha_router.route_value_is_alertable(final_route)
    out["route_alertable"] = out["alertable_after_quality_gate"]
    changed = any(
        str(out.get(key) or "") != str(snapshot.get(key) or "")
        for key in ("final_route_after_quality_gate", "route", "opportunity_level", "final_state_after_quality_gate")
    )
    out["snapshot_core_reconciled"] = True
    out["snapshot_core_reconciliation_reason"] = (
        "canonical_core_final_state_applied" if changed else "canonical_core_aligned"
    )
    out.setdefault("core_resolution_status", "canonical")
    out["snapshot_core_resolution_status"] = SNAPSHOT_CORE_RECONCILED
    return _with_snapshot_quality_classification(out)


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
    quality = event_alpha_quality_fields.ensure_quality_fields({}, components=alert.score_components)
    requested_route = _route_for_tier_value(alert.tier.value)
    row = {
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
        "coin_id": candidate.asset.coin_id,
        "symbol": candidate.asset.symbol,
        "asset_coin_id": candidate.asset.coin_id,
        "asset_symbol": candidate.asset.symbol,
        "asset_name": candidate.asset.name,
        "relationship_type": candidate.classification.relationship_type,
        "asset_role": candidate.classification.asset_role,
        "source": candidate.event.source,
        "source_count": len(candidate.event.raw_ids),
        "tier": alert.tier.value,
        "requested_tier_before_quality_gate": alert.tier.value,
        "requested_state_before_quality_gate": None,
        "final_state_after_quality_gate": None,
        "quality_state_block_reason": None,
        "state_quality_capped": False,
        "requested_route_before_quality_gate": requested_route,
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
        "incident_id": alert.score_components.get("incident_id"),
        "hypothesis_id": alert.score_components.get("hypothesis_id"),
        "incident_link_status": "linked" if alert.score_components.get("incident_id") else "no_incident",
        "incident_link_reason": (
            None
            if alert.score_components.get("incident_id")
            else alert.score_components.get("incident_link_reason")
            or "no_canonical_incident_for_event_evidence"
        ),
        "incident_relevance_status": alert.score_components.get("incident_relevance_status"),
        "incident_relevance_score": alert.score_components.get("incident_relevance_score"),
        "incident_relevance_reasons": alert.score_components.get("incident_relevance_reasons") or (),
        "incident_relevance_warnings": alert.score_components.get("incident_relevance_warnings") or (),
        "canonical_persistence_reason": alert.score_components.get("canonical_persistence_reason"),
        "incident_canonical_name": alert.score_components.get("incident_canonical_name") or alert.score_components.get("canonical_incident_name"),
        "canonical_incident_name": alert.score_components.get("canonical_incident_name"),
        "incident_event_archetype": alert.score_components.get("incident_event_archetype") or alert.score_components.get("event_archetype"),
        "event_archetype": alert.score_components.get("event_archetype"),
        "incident_primary_subject": alert.score_components.get("incident_primary_subject") or alert.score_components.get("primary_subject"),
        "primary_subject": alert.score_components.get("primary_subject"),
        "incident_affected_ecosystem": alert.score_components.get("incident_affected_ecosystem") or alert.score_components.get("affected_ecosystem"),
        "affected_ecosystem": alert.score_components.get("affected_ecosystem"),
        "incident_cause_status": alert.score_components.get("incident_cause_status") or alert.score_components.get("cause_status"),
        "cause_status": alert.score_components.get("cause_status"),
        "claim_polarities": alert.score_components.get("claim_polarities") or (),
        "claim_history": alert.score_components.get("claim_history") or (),
        "role_confidence": alert.score_components.get("role_confidence"),
        "role_evidence": alert.score_components.get("role_evidence") or (),
        "market_context_source": alert.score_components.get("market_context_source"),
        "market_context_observed_at": alert.score_components.get("market_context_observed_at"),
        "market_context_age_seconds": alert.score_components.get("market_context_age_seconds"),
        "market_context_age_hours": alert.score_components.get("market_context_age_hours"),
        "market_context_stale": alert.score_components.get("market_context_stale"),
        "market_context_freshness_status": alert.score_components.get("market_context_freshness_status"),
        "market_context_freshness_cap_applied": alert.score_components.get("market_context_freshness_cap_applied"),
        "market_context_data_quality": alert.score_components.get("market_context_data_quality"),
        "incident_market_reaction_observed": alert.score_components.get("incident_market_reaction_observed") or alert.score_components.get("market_reaction_observed"),
        "market_reaction_observed": alert.score_components.get("market_reaction_observed") or alert.score_components.get("incident_market_reaction_observed"),
        "market_reaction_confirmed": alert.score_components.get("market_reaction_confirmed"),
        "incident_causal_mechanism_confirmed": alert.score_components.get("incident_causal_mechanism_confirmed") or alert.score_components.get("causal_mechanism_confirmed"),
        "causal_mechanism_confirmed": alert.score_components.get("causal_mechanism_confirmed"),
        "incident_confidence": alert.score_components.get("incident_confidence"),
        **quality,
        "route": requested_route,
        "lane": event_alpha_router.lane_value_for_route_value(requested_route),
        "btc_regime": _btc_regime(candidate),
        "signal_type": signal.signal_type.value if signal else None,
        "fade_state": signal.state.value if signal else None,
        "reason": alert.reason,
        "verify": list(alert.verify),
        "rejected_reason": alert.rejected_reason,
        "delivered_status": None,
        "feedback_status": "pending",
    }
    core_id = alert.score_components.get("core_opportunity_id") or event_core_opportunities.core_opportunity_id_for_row(row)
    row["core_opportunity_id"] = core_id
    row["feedback_target"] = core_id or row["alert_key"]
    row["feedback_target_type"] = "core_opportunity_id" if core_id else "alert_key"
    return _with_canonical_quality_route(row)


def _snapshot_from_route_decision(
    decision: event_alpha_router.EventAlphaRouteDecision,
    observed: datetime,
) -> dict[str, Any]:
    entry = decision.entry
    components = dict(entry.latest_score_components or {})
    alert_key = str(entry.key)
    observed_iso = observed.isoformat()
    playbook = entry.latest_effective_playbook_type or entry.latest_playbook_type or "unknown"
    validated_asset = components.get("validated_asset") if isinstance(components.get("validated_asset"), Mapping) else {}
    validated_symbol = components.get("validated_symbol") or validated_asset.get("symbol") or entry.symbol
    validated_coin_id = components.get("validated_coin_id") or validated_asset.get("coin_id") or entry.coin_id
    symbol = entry.symbol or validated_symbol
    coin_id = entry.coin_id or validated_coin_id
    warnings = list(entry.warnings)
    if not symbol and not validated_symbol:
        warnings.append("validated_hypothesis_snapshot_missing_identity")
    entry_quality = {
        key: getattr(entry, key, None)
        for key in event_alpha_quality_fields.REQUIRED_QUALITY_FIELDS
        if getattr(entry, key, None) not in (None, "", [], {}, ())
    }
    quality = event_alpha_quality_fields.ensure_quality_fields(entry_quality, components=components)
    final_route = event_alpha_router.final_route_value(decision)
    final_lane = event_alpha_router.final_lane_value(decision)
    alertable_after_quality = event_alpha_router.alertable_after_quality_gate(decision)
    tier = entry.latest_tier if alertable_after_quality else event_alerts.EventAlertTier.STORE_ONLY.value
    core_id = (
        components.get("core_opportunity_id")
        or components.get("aggregated_candidate_id")
        or event_core_opportunities.core_opportunity_id_for_row(entry)
    )
    feedback_target = str(core_id or decision.alert_id or alert_key)
    feedback_target_type = "core_opportunity_id" if core_id else "alert_id"
    row = {
        "schema_version": ALERT_STORE_SCHEMA_VERSION,
        "row_type": "event_alpha_alert_snapshot",
        "snapshot_id": f"{observed_iso}|{alert_key}",
        "alert_key": alert_key,
        "cluster_id": entry.cluster_id,
        "observed_at": observed_iso,
        "event_id": entry.event_id,
        "event_name": entry.latest_event_name,
        "event_type": components.get("event_type") or "impact_hypothesis",
        "event_time": entry.event_time,
        "external_asset": entry.external_asset,
        "coin_id": coin_id,
        "symbol": symbol,
        "asset_coin_id": coin_id,
        "asset_symbol": symbol,
        "asset_name": validated_asset.get("name") if isinstance(validated_asset, Mapping) else None,
        "relationship_type": entry.relationship_type,
        "asset_role": components.get("asset_role"),
        "source": entry.latest_source,
        "source_count": entry.source_count,
        "tier": tier,
        "requested_tier_before_quality_gate": entry.latest_tier,
        "opportunity_score": entry.latest_score,
        "opportunity_score_v2": components.get("opportunity_score_v2"),
        "opportunity_score_components": components.get("opportunity_score_components") or {},
        "score_components": components,
        "playbook_type": playbook,
        "rule_playbook_type": entry.latest_rule_playbook_type,
        "effective_playbook_type": playbook,
        "llm_adjusted_playbook_type": entry.latest_llm_adjusted_playbook_type,
        "playbook_score": entry.latest_playbook_score,
        "playbook_action": entry.latest_playbook_action,
        "llm_asset_role": entry.latest_llm_asset_role,
        "llm_confidence": entry.latest_llm_confidence,
        "expected_direction": components.get("direction_hint") or components.get("expected_direction") or "unknown",
        "primary_horizon": components.get("primary_horizon") or "manual",
        "success_metric": components.get("success_metric") or "manual",
        "market_anomaly_bucket": _market_anomaly_bucket(components.get("market_move_volume", 0)),
        "btc_regime": components.get("btc_regime") or "unknown",
        "signal_type": components.get("signal_type"),
        "fade_state": components.get("fade_state"),
        "state": event_watchlist.final_state_value(entry),
        **_state_cap_context(entry),
        "route": final_route,
        "lane": final_lane,
        "requested_route_before_quality_gate": decision.requested_route_before_quality_gate or decision.route.value,
        "final_route_after_quality_gate": final_route,
        "final_tier_after_quality_gate": _tier_for_final_route(final_route, entry.latest_tier, quality),
        "quality_gate_block_reason": decision.quality_gate_block_reason,
        "alert_id": decision.alert_id,
        "card_id": decision.card_id,
        "core_opportunity_id": core_id,
        "feedback_target": feedback_target,
        "feedback_target_type": feedback_target_type,
        "route_alertable": alertable_after_quality,
        "alertable_after_quality_gate": alertable_after_quality,
        "route_reason": decision.reason,
        "impact_category": components.get("impact_category") or playbook,
        "incident_id": components.get("incident_id"),
        "hypothesis_id": components.get("hypothesis_id") or entry.hypothesis_id or entry.event_id,
        "incident_link_status": components.get("incident_link_status") or entry.incident_link_status or (
            "linked" if components.get("incident_id") or entry.incident_id else "no_incident"
        ),
        "incident_link_reason": (
            components.get("incident_link_reason")
            or entry.incident_link_reason
            or (None if components.get("incident_id") or entry.incident_id else "no_canonical_incident_for_event_evidence")
        ),
        "incident_relevance_status": components.get("incident_relevance_status"),
        "incident_relevance_score": components.get("incident_relevance_score"),
        "incident_relevance_reasons": components.get("incident_relevance_reasons") or (),
        "incident_relevance_warnings": components.get("incident_relevance_warnings") or (),
        "canonical_persistence_reason": components.get("canonical_persistence_reason"),
        "incident_canonical_name": components.get("incident_canonical_name") or components.get("canonical_incident_name") or entry.incident_canonical_name,
        "canonical_incident_name": components.get("canonical_incident_name") or components.get("incident_canonical_name") or entry.incident_canonical_name,
        "incident_event_archetype": components.get("incident_event_archetype") or components.get("event_archetype"),
        "event_archetype": components.get("event_archetype") or components.get("incident_event_archetype"),
        "incident_primary_subject": components.get("incident_primary_subject") or components.get("primary_subject") or entry.incident_primary_subject,
        "primary_subject": components.get("primary_subject") or components.get("incident_primary_subject") or entry.incident_primary_subject,
        "incident_affected_ecosystem": components.get("incident_affected_ecosystem") or components.get("affected_ecosystem") or entry.incident_affected_ecosystem,
        "affected_ecosystem": components.get("affected_ecosystem") or components.get("incident_affected_ecosystem") or entry.incident_affected_ecosystem,
        "incident_cause_status": components.get("incident_cause_status") or components.get("cause_status") or entry.incident_cause_status,
        "cause_status": components.get("cause_status") or components.get("incident_cause_status") or entry.incident_cause_status,
        "claim_polarities": components.get("claim_polarities") or (),
        "claim_history": components.get("claim_history") or (),
        "role_confidence": components.get("role_confidence"),
        "role_evidence": components.get("role_evidence") or (),
        "market_context_source": components.get("market_context_source"),
        "market_context_observed_at": components.get("market_context_observed_at"),
        "market_context_age_seconds": components.get("market_context_age_seconds"),
        "market_context_age_hours": components.get("market_context_age_hours"),
        "market_context_stale": components.get("market_context_stale"),
        "market_context_freshness_status": components.get("market_context_freshness_status"),
        "market_context_freshness_cap_applied": components.get("market_context_freshness_cap_applied"),
        "market_context_data_quality": components.get("market_context_data_quality"),
        "incident_market_reaction_observed": components.get("incident_market_reaction_observed") or components.get("market_reaction_observed") or entry.incident_market_reaction_observed,
        "market_reaction_observed": components.get("market_reaction_observed") or components.get("incident_market_reaction_observed") or entry.incident_market_reaction_observed,
        "market_reaction_confirmed": components.get("market_reaction_confirmed"),
        "incident_causal_mechanism_confirmed": components.get("incident_causal_mechanism_confirmed") or components.get("causal_mechanism_confirmed") or entry.incident_causal_mechanism_confirmed,
        "causal_mechanism_confirmed": components.get("causal_mechanism_confirmed") or components.get("incident_causal_mechanism_confirmed") or entry.incident_causal_mechanism_confirmed,
        "incident_confidence": components.get("incident_confidence"),
        "validation_stage": components.get("validation_stage"),
        "impact_path_reason": components.get("impact_path_reason"),
        "impact_path_type": components.get("impact_path_type"),
        "impact_path_strength": components.get("impact_path_strength"),
        "candidate_role": components.get("candidate_role"),
        "evidence_specificity_score": components.get("evidence_specificity_score"),
        "digest_eligible_by_impact_path": components.get("digest_eligible_by_impact_path"),
        "why_digest_ineligible": components.get("why_digest_ineligible"),
        "evidence_quality_score": components.get("evidence_quality_score"),
        "source_class": components.get("source_class"),
        "evidence_specificity": components.get("evidence_specificity"),
        "market_confirmation_score": components.get("market_confirmation_score"),
        "market_confirmation_level": components.get("market_confirmation_level"),
        "opportunity_score_final": components.get("opportunity_score_final"),
        "opportunity_level": components.get("opportunity_level"),
        "opportunity_verdict_reasons": components.get("opportunity_verdict_reasons") or (),
        "why_local_only": components.get("why_local_only"),
        "why_not_watchlist": components.get("why_not_watchlist"),
        "manual_verification_items": components.get("manual_verification_items") or (),
        **quality,
        "hypothesis_score": components.get("hypothesis_score") or entry.latest_score,
        "validated_symbol": validated_symbol,
        "validated_coin_id": validated_coin_id,
        "quality_warnings": tuple(dict.fromkeys(warnings)),
        "research_card_path": None,
        "delivered_status": None,
        "feedback_status": "pending",
        "reason": decision.reason,
        "verify": components.get("what_to_verify") or [],
        "rejected_reason": None,
    }
    return _with_snapshot_quality_classification(row)


def _with_artifact_context(
    row: dict[str, Any],
    *,
    run_id: str | None,
    profile: str | None,
    run_mode: str | None,
    artifact_namespace: str | None,
) -> dict[str, Any]:
    out = dict(row)
    if run_id:
        out["run_id"] = run_id
    if profile:
        out["profile"] = profile
    if run_mode:
        out["run_mode"] = run_mode
    if artifact_namespace:
        out["artifact_namespace"] = artifact_namespace
    return out


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
        final_route = event_alpha_router.final_route_value(decision)
        final_lane = event_alpha_router.final_lane_value(decision)
        alertable_after_quality = event_alpha_router.alertable_after_quality_gate(decision)
        components = getattr(entry, "latest_score_components", None)
        if not isinstance(components, Mapping):
            components = {}
        entry_quality = {
            quality_key: getattr(entry, quality_key, None)
            for quality_key in event_alpha_quality_fields.REQUIRED_QUALITY_FIELDS
            if getattr(entry, quality_key, None) not in (None, "", [], {}, ())
        }
        quality = event_alpha_quality_fields.ensure_quality_fields(entry_quality, components=components)
        core_id = (
            components.get("core_opportunity_id")
            or components.get("aggregated_candidate_id")
            or event_core_opportunities.core_opportunity_id_for_row(entry)
        )
        out[key] = {
            "alert_id": getattr(decision, "alert_id", f"ea:{key}"),
            "card_id": getattr(decision, "card_id", ""),
            "core_opportunity_id": core_id,
            "feedback_target": core_id or getattr(decision, "alert_id", f"ea:{key}"),
            "feedback_target_type": "core_opportunity_id" if core_id else "alert_id",
            "route": final_route,
            "lane": final_lane,
            "requested_route_before_quality_gate": getattr(decision, "requested_route_before_quality_gate", None)
            or getattr(route, "value", str(route)),
            "final_route_after_quality_gate": final_route,
            "final_tier_after_quality_gate": _tier_for_final_route(
                final_route,
                getattr(entry, "latest_tier", None),
                quality,
            ),
            "quality_gate_block_reason": getattr(decision, "quality_gate_block_reason", None),
            "opportunity_level": getattr(decision, "opportunity_level", None) or quality.get("opportunity_level"),
            "opportunity_score_final": getattr(decision, "opportunity_score_final", None)
            if getattr(decision, "opportunity_score_final", None) is not None
            else quality.get("opportunity_score_final"),
            "route_alertable": alertable_after_quality,
            "alertable_after_quality_gate": alertable_after_quality,
            "route_reason": str(getattr(decision, "reason", "") or ""),
            **_state_cap_context(entry),
        }
    return out


def _route_decisions_for_snapshots(router_result: Any | None) -> tuple[event_alpha_router.EventAlphaRouteDecision, ...]:
    if router_result is None:
        return ()
    out: list[event_alpha_router.EventAlphaRouteDecision] = []
    for decision in getattr(router_result, "decisions", ()) or ():
        requested = getattr(decision, "requested_route_before_quality_gate", None)
        final = getattr(decision, "final_route_after_quality_gate", None)
        if (
            bool(getattr(decision, "alertable", False))
            or bool(getattr(decision, "quality_gate_block_reason", None))
            or (requested and final and requested != final)
        ):
            out.append(decision)
    return tuple(out)


def _state_cap_context(entry: event_watchlist.EventWatchlistEntry) -> dict[str, Any]:
    requested = event_watchlist.requested_state_value(entry)
    final = event_watchlist.final_state_value(entry)
    quality = {
        key: getattr(entry, key, None)
        for key in event_alpha_quality_fields.REQUIRED_QUALITY_FIELDS
        if getattr(entry, key, None) not in (None, "", [], {}, ())
    }
    if not quality:
        quality = dict(entry.latest_score_components or {})
    _, computed_block = event_watchlist.quality_cap_watchlist_state(requested, quality)
    capped = event_watchlist.state_is_quality_capped(entry)
    return {
        "state": final,
        "requested_state_before_quality_gate": requested,
        "final_state_after_quality_gate": final,
        "quality_state_block_reason": entry.quality_state_block_reason or computed_block,
        "state_quality_capped": capped,
    }


def _with_route_context(row: dict[str, Any], route_context: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    context = route_context.get(str(row.get("alert_key") or ""))
    if not context:
        return _with_snapshot_quality_classification(row)
    out = dict(row)
    if "requested_tier_before_quality_gate" not in out:
        out["requested_tier_before_quality_gate"] = out.get("tier")
    out.update(context)
    if context.get("state") is not None:
        out["state"] = context.get("state")
    if not bool(out.get("alertable_after_quality_gate", out.get("route_alertable"))):
        out["tier"] = event_alerts.EventAlertTier.STORE_ONLY.value
    elif out.get("final_tier_after_quality_gate"):
        out["tier"] = out["final_tier_after_quality_gate"]
    return _with_snapshot_quality_classification(out)


def classify_alert_snapshot(row: Mapping[str, Any]) -> str:
    """Classify snapshot route/quality consistency for reports and migrations."""
    components = row.get("score_components") if isinstance(row.get("score_components"), Mapping) else {}
    has_quality = event_alpha_quality_fields.has_any_quality_field(row, components_key="score_components")
    final_present = bool(row.get("final_route_after_quality_gate"))
    final_route, block = event_alpha_router.quality_gate_route_for_row(
        row,
        components=components,
        require_quality=has_quality,
    )
    persisted_final = str(row.get("final_route_after_quality_gate") or "")
    persisted_route = str(row.get("route") or "")
    persisted_alertable = bool(row.get("route_alertable")) or event_alpha_router.route_value_is_alertable(persisted_route)
    final_alertable = event_alpha_router.route_value_is_alertable(final_route)
    persisted_final_alertable = event_alpha_router.route_value_is_alertable(persisted_final)
    if not final_present:
        if persisted_alertable and not final_alertable:
            return SNAPSHOT_LEGACY_CONFLICT
        return SNAPSHOT_STALE_PRE_QUALITY_GATE if has_quality else SNAPSHOT_MISSING_FINAL_ROUTE
    if (persisted_alertable or persisted_final_alertable) and not final_alertable:
        return SNAPSHOT_LEGACY_CONFLICT
    if persisted_final and persisted_final != final_route and persisted_final_alertable:
        return SNAPSHOT_LEGACY_CONFLICT
    if bool(row.get("state_quality_capped")):
        return SNAPSHOT_QUALITY_GATED_LOCAL
    if block and not final_alertable:
        return SNAPSHOT_QUALITY_GATED_LOCAL
    return SNAPSHOT_CURRENT_CLEAN


def _with_snapshot_quality_classification(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out["snapshot_quality_classification"] = classify_alert_snapshot(out)
    return out


def _with_canonical_quality_route(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    components = out.get("score_components") if isinstance(out.get("score_components"), Mapping) else {}
    requested_route = str(
        out.get("requested_route_before_quality_gate")
        or out.get("route")
        or _route_for_tier_value(out.get("requested_tier_before_quality_gate") or out.get("tier"))
    )
    out["requested_route_before_quality_gate"] = requested_route
    out.setdefault("requested_tier_before_quality_gate", out.get("tier"))
    has_quality = event_alpha_quality_fields.has_any_quality_field(out, components_key="score_components")
    final_route, block = event_alpha_router.quality_gate_route_for_row(
        out,
        components=components,
        requested_route=requested_route,
        require_quality=has_quality,
    )
    final_tier = _tier_for_final_route(final_route, out.get("requested_tier_before_quality_gate") or out.get("tier"), out)
    out["final_route_after_quality_gate"] = final_route
    out["final_tier_after_quality_gate"] = final_tier
    out["quality_gate_block_reason"] = block or out.get("quality_gate_block_reason")
    out["alertable_after_quality_gate"] = event_alpha_router.route_value_is_alertable(final_route)
    out["route_alertable"] = out["alertable_after_quality_gate"]
    out["route"] = final_route
    out["lane"] = event_alpha_router.lane_value_for_route_value(final_route)
    out["tier"] = final_tier
    return _with_snapshot_quality_classification(out)


def _route_for_tier_value(tier: object) -> str:
    value = str(getattr(tier, "value", tier) or "").upper()
    if value == event_alerts.EventAlertTier.TRIGGERED_FADE.value:
        return event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH.value
    if value == event_alerts.EventAlertTier.HIGH_PRIORITY_WATCH.value:
        return event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value
    if value in {event_alerts.EventAlertTier.WATCHLIST.value, event_alerts.EventAlertTier.RADAR_DIGEST.value}:
        return event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value
    return event_alpha_router.EventAlphaRoute.STORE_ONLY.value


def _tier_for_final_route(
    final_route: object,
    requested_tier: object,
    quality: Mapping[str, Any] | None = None,
) -> str:
    route = str(getattr(final_route, "value", final_route) or "").upper()
    requested = str(getattr(requested_tier, "value", requested_tier) or "").upper()
    if route == event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH.value:
        return event_alerts.EventAlertTier.TRIGGERED_FADE.value
    if route == event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value:
        return event_alerts.EventAlertTier.HIGH_PRIORITY_WATCH.value
    if route == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value:
        if requested in {event_alerts.EventAlertTier.WATCHLIST.value, event_alerts.EventAlertTier.RADAR_DIGEST.value}:
            return requested
        level = str((quality or {}).get("opportunity_level") or "").strip()
        if level == "watchlist":
            return event_alerts.EventAlertTier.WATCHLIST.value
        return event_alerts.EventAlertTier.RADAR_DIGEST.value
    return event_alerts.EventAlertTier.STORE_ONLY.value


def _delivery_context_by_alert_id(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in event_alpha_notification_delivery.latest_rows_by_delivery(rows):
        state = str(row.get("state") or "")
        alert_ids = [part.strip() for part in str(row.get("alert_id") or "").split(",") if part.strip()]
        if not alert_ids:
            continue
        context = {
            "delivered_status": state,
            "delivery_state": state,
            "delivery_id": row.get("delivery_id"),
            "delivery_lane": row.get("lane"),
            "delivery_delivered_at": row.get("delivered_at"),
            "delivery_delivered_count": row.get("delivered_count"),
            "delivery_failed_count": row.get("failed_count"),
        }
        for alert_id in alert_ids:
            out[alert_id] = context
            if alert_id.startswith("ea:"):
                out[alert_id[3:]] = context
            else:
                out[f"ea:{alert_id}"] = context
    return out


def _with_delivery_context(row: dict[str, Any], context: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    ids = [
        str(row.get("alert_id") or ""),
        str(row.get("alert_key") or ""),
        str(row.get("card_id") or ""),
    ]
    for value in ids:
        if value and value in context:
            out = dict(row)
            out.update(context[value])
            return out
    return row


def _card_context_by_card_id(paths: Iterable[str | Path]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for raw in paths:
        path = Path(raw).expanduser()
        if path.name == "index.md":
            continue
        context = {
            "research_card_path": str(path),
        }
        core_id = event_research_cards.card_core_opportunity_id(path)
        feedback_target = event_research_cards.card_feedback_target(path)
        if core_id:
            context["core_opportunity_id"] = core_id
            context.setdefault("feedback_target", core_id)
            context.setdefault("feedback_target_type", "core_opportunity_id")
        if feedback_target:
            context["feedback_target"] = feedback_target
            context.setdefault(
                "feedback_target_type",
                "core_opportunity_id" if feedback_target.startswith("core_") else "card_feedback_target",
            )
        stem = path.stem
        identifiers = {stem, core_id or "", feedback_target or ""}
        if stem.startswith("card_"):
            identifiers.add(stem[5:])
        for identifier in identifiers:
            if identifier:
                out[identifier] = dict(context)
    return out


def _with_card_context(row: dict[str, Any], context: Mapping[str, Mapping[str, str]]) -> dict[str, Any]:
    for value in (
        str(row.get("card_id") or ""),
        str(row.get("alert_id") or "").replace("ea:", "card_"),
        str(row.get("core_opportunity_id") or ""),
        str(row.get("feedback_target") or ""),
    ):
        if value and value in context:
            out = dict(row)
            card = context[value]
            out["research_card_path"] = card.get("research_card_path")
            if card.get("core_opportunity_id") and not out.get("core_opportunity_id"):
                out["core_opportunity_id"] = card.get("core_opportunity_id")
            if card.get("feedback_target") and not out.get("feedback_target"):
                out["feedback_target"] = card.get("feedback_target")
                out["feedback_target_type"] = card.get("feedback_target_type")
            return out
    return row


def _with_core_resolution(row: dict[str, Any], core_rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    core_rows_tuple = tuple(dict(item) for item in core_rows if isinstance(item, Mapping))
    core_by_id = {
        str(item.get("core_opportunity_id") or "").strip(): item
        for item in core_rows_tuple
        if str(item.get("core_opportunity_id") or "").strip()
    }
    resolution = event_core_opportunities.resolve_canonical_core_opportunity_id(row, core_rows_tuple)
    out = dict(row)
    out["core_opportunity_id_status"] = resolution.resolution_status
    out["core_resolution_status"] = resolution.resolution_status
    out["canonical_core_resolution_warnings"] = resolution.warnings
    if resolution.resolution_status == "canonical":
        out["core_opportunity_id"] = resolution.canonical_core_opportunity_id
        out["is_diagnostic_snapshot"] = False
        out.pop("diagnostic_support_for_core_opportunity_id", None)
        out.setdefault("feedback_target", resolution.canonical_core_opportunity_id)
        out.setdefault("feedback_target_type", "core_opportunity_id")
        core_row = core_by_id.get(str(resolution.canonical_core_opportunity_id or ""))
        if core_row:
            out = reconcile_alert_snapshot_with_core_store(out, core_row)
    elif resolution.resolution_status == "diagnostic_support":
        out["core_opportunity_id"] = resolution.canonical_core_opportunity_id
        out["diagnostic_support_for_core_opportunity_id"] = resolution.diagnostic_support_for_core_opportunity_id
        out["diagnostic_row_id"] = _diagnostic_row_id(out)
        out["is_diagnostic_snapshot"] = True
        core_row = core_by_id.get(str(resolution.canonical_core_opportunity_id or ""))
        if core_row:
            out = reconcile_alert_snapshot_with_core_store(out, core_row)
        out["feedback_target"] = resolution.diagnostic_support_for_core_opportunity_id or out.get("feedback_target") or out.get("alert_key")
        out["feedback_target_type"] = "diagnostic_support_for_core_opportunity_id"
    elif event_core_opportunities.row_is_diagnostic(out):
        out["diagnostic_row_id"] = _diagnostic_row_id(out)
        out["is_diagnostic_snapshot"] = True
        out["diagnostic_support_for_core_opportunity_id"] = None
        out["core_opportunity_id"] = None
        if out.get("feedback_target_type") == "core_opportunity_id":
            out["feedback_target"] = out.get("alert_id") or out.get("alert_key") or out["diagnostic_row_id"]
            out["feedback_target_type"] = "diagnostic_row_id"
    else:
        out["is_diagnostic_snapshot"] = False
        if resolution.canonical_core_opportunity_id:
            out["core_opportunity_id"] = resolution.canonical_core_opportunity_id
            out.setdefault("feedback_target", resolution.canonical_core_opportunity_id)
            out.setdefault("feedback_target_type", "core_opportunity_id")
            out["core_resolution_status"] = SNAPSHOT_MISSING_CORE
            out["snapshot_core_reconciled"] = False
            out["snapshot_core_reconciliation_reason"] = "missing_canonical_core_store_row"
            out["alertable_after_quality_gate"] = False
            out["route_alertable"] = False
            out["requested_route_before_core_reconciliation"] = out.get("final_route_after_quality_gate") or out.get("route")
            out["requested_opportunity_level_before_core_reconciliation"] = out.get("final_opportunity_level") or out.get("opportunity_level")
            out["final_route_after_quality_gate"] = event_alpha_router.EventAlphaRoute.STORE_ONLY.value
            out["route"] = event_alpha_router.EventAlphaRoute.STORE_ONLY.value
            out["lane"] = event_alpha_router.EventAlphaRouteLane.LOCAL_ONLY.value
            out["final_tier_after_quality_gate"] = event_alerts.EventAlertTier.STORE_ONLY.value
            out["tier"] = event_alerts.EventAlertTier.STORE_ONLY.value
            out["quality_gate_block_reason"] = out.get("quality_gate_block_reason") or "missing_core_opportunity_store_row"
    return _with_snapshot_quality_classification(out)


def _sibling_core_store_rows(alert_path: Path) -> list[dict[str, Any]]:
    core_path = alert_path.expanduser().parent / "event_core_opportunities.jsonl"
    if not core_path.exists():
        return []
    return [
        row for row in _read_jsonl(core_path)
        if row.get("row_type") == "event_core_opportunity"
    ]


def _first_present(row: Mapping[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if row.get(key) not in (None, ""):
            return row.get(key)
    return None


def _diagnostic_row_id(row: Mapping[str, Any]) -> str:
    for key in ("diagnostic_row_id", "snapshot_id", "alert_id", "alert_key", "event_id", "hypothesis_id"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    payload = json.dumps(_json_ready(dict(row)), sort_keys=True, separators=(",", ":"))
    return "diagnostic:" + hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


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
            return [
                row for row in rows
                if bool(row.get("alertable_after_quality_gate", row.get("route_alertable")))
                and event_alpha_router.route_value_is_alertable(row.get("final_route_after_quality_gate") or row.get("route"))
            ]
        return [
            row for row in rows
            if bool(
                row.get(
                    "alertable_after_quality_gate",
                    route_context.get(str(row.get("alert_key") or ""), {}).get(
                        "alertable_after_quality_gate",
                        route_context.get(str(row.get("alert_key") or ""), {}).get("route_alertable"),
                    ),
                )
            )
            and event_alpha_router.route_value_is_alertable(row.get("final_route_after_quality_gate") or row.get("route"))
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
