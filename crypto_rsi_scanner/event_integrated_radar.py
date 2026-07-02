"""Integrated Event Alpha radar cycle.

This module orchestrates existing research-only Event Alpha sidecars into one
fixture-friendly radar run. It writes local artifacts only: no Telegram sends,
paper trades, normal RSI signal rows, order logic, or event-fade triggers.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Iterable, Mapping

from . import (
    event_artifact_paths,
    event_alpha_artifacts,
    event_alpha_run_ledger,
    event_alpha_router,
    event_alpha_source_coverage,
    event_live_provider_readiness,
    event_core_opportunity_store,
    event_derivatives_crowding,
    event_market_anomaly_scanner,
    event_market_reaction,
    event_official_exchange,
    event_research_cards,
    event_scheduled_catalysts,
    event_watchlist,
)


INTEGRATED_CANDIDATES_FILENAME = "event_integrated_radar_candidates.jsonl"
INTEGRATED_REPORT_FILENAME = "event_integrated_radar_report.md"
INTEGRATED_DELIVERIES_FILENAME = "event_integrated_radar_notification_deliveries.jsonl"
INTEGRATED_OUTCOMES_FILENAME = "event_integrated_radar_outcomes.jsonl"
INTEGRATED_OUTCOME_REPORT_FILENAME = "event_integrated_radar_outcome_report.md"
INTEGRATED_CALIBRATION_REPORT_FILENAME = "event_integrated_radar_calibration_report.md"
INTEGRATED_CALIBRATION_PRIORS_FILENAME = "event_integrated_radar_calibration_priors.json"
NOTIFICATION_PREVIEW_FILENAME = "event_alpha_notification_preview.md"
DAILY_BRIEF_FILENAME = "event_alpha_daily_brief.md"
SOURCE_COVERAGE_FILENAME = "event_alpha_source_coverage.md"
SOURCE_COVERAGE_JSON_FILENAME = "event_alpha_source_coverage.json"
INPUT_MANIFEST_FILENAME = "event_integrated_radar_input_manifest.json"
RESEARCH_DISCLAIMER = "Research-only. Not a trade signal, paper trade, live RSI signal, or execution."
INPUT_MODE_AUTO = "auto"
INPUT_MODE_RUN_SIDECARS = "run_sidecars"
INPUT_MODE_LOAD_EXISTING = "load_existing"
INPUT_MODES = {INPUT_MODE_AUTO, INPUT_MODE_RUN_SIDECARS, INPUT_MODE_LOAD_EXISTING}


@dataclass(frozen=True)
class EventIntegratedRadarResult:
    namespace_dir: Path
    run_id: str
    profile: str
    run_mode: str
    artifact_namespace: str
    started_at: datetime
    finished_at: datetime
    raw_events: int
    candidates: int
    core_opportunity_rows_written: int
    core_opportunity_write_attempted: bool
    core_opportunity_write_success: bool
    core_opportunity_write_block_reason: str | None
    research_card_paths: tuple[Path, ...]
    research_cards_dir: str
    integrated_candidates_path: Path
    integrated_report_path: Path
    daily_brief_path: Path
    notification_preview_path: Path
    integrated_delivery_path: Path | None
    run_ledger_path: str
    core_opportunity_store_path: str
    input_manifest_path: Path | None = None
    source_coverage_json_path: Path | None = None
    source_coverage_path: Path | None = None
    research_observed_at: datetime | None = None
    wall_started_at: datetime | None = None
    wall_finished_at: datetime | None = None
    market_anomalies: int = 0
    market_state_snapshots: int = 0
    official_exchange_events: int = 0
    official_listing_candidates: int = 0
    scheduled_catalysts: int = 0
    unlock_candidates: int = 0
    derivatives_state_rows: int = 0
    derivatives_crowding_candidates: int = 0
    fade_review_candidates: int = 0
    integrated_candidates: int = 0
    alerts: tuple[Mapping[str, Any], ...] = ()
    routed: int = 0
    alertable: int = 0
    send_requested: bool = False
    send_attempted: bool = False
    send_success: bool = False
    send_items_attempted: int = 0
    send_items_delivered: int = 0
    send_would_send_items: int = 0
    send_lane_items_attempted: Mapping[str, int] | None = None
    send_lane_items_delivered: Mapping[str, int] | None = None
    send_heartbeat_due: bool = True
    send_heartbeat_sent: bool = False
    send_block_reason: str | None = "no_send_guard_enabled"
    research_review_digest_enabled: bool = False
    research_review_digest_candidates: int = 0
    research_review_digest_would_send: int = 0
    research_review_digest_sent: int = 0
    research_review_digest_block_reason: str | None = "no_send_guard_enabled"
    snapshot_write_attempted: bool = True
    snapshot_write_success: bool = True
    snapshot_rows_written: int = 0
    strict_alerts: int = 0
    alertable_decisions: int = 0
    research_candidates: int = 0
    raw_source_candidates: int = 0
    cards_written: int = 0
    research_cards_written: int = 0
    preview_rendered_items: int = 0
    preview_eligible_items: int = 0
    preview_skipped_items: int = 0
    preview_skip_reason_counts: Mapping[str, int] | None = None
    integrated_delivery_rows: int = 0
    integrated_lanes_rendered: Mapping[str, int] | None = None
    integrated_lanes_empty: Mapping[str, int] | None = None
    operator_absolute_path_count: int = 0
    artifact_doctor_status: str | None = None
    source_coverage_json_path_rel: str | None = None
    source_coverage_md_path_rel: str | None = None
    warnings: tuple[str, ...] = ()
    cycle_completed: bool = True


def run_integrated_radar_cycle(
    *,
    context: event_alpha_artifacts.EventAlphaArtifactContext,
    fixture: bool = False,
    observed_at: datetime | str | None = None,
    input_mode: str = INPUT_MODE_AUTO,
) -> EventIntegratedRadarResult:
    """Run one integrated research-only radar cycle and write artifacts."""
    wall_started = datetime.now(timezone.utc)
    research_observed_at = _as_utc(_parse_time(observed_at) or wall_started)
    mode = _normalize_input_mode(input_mode)
    namespace_dir = Path(context.namespace_dir)
    namespace_dir.mkdir(parents=True, exist_ok=True)
    if fixture:
        _clear_namespace(namespace_dir)
        namespace_dir.mkdir(parents=True, exist_ok=True)
    run_id = event_alpha_run_ledger.run_id_for(research_observed_at, context.profile)
    sidecars, input_manifest = _run_or_load_sidecars(
        namespace_dir=namespace_dir,
        fixture=fixture,
        observed_at=research_observed_at,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        run_mode=context.run_mode,
        run_id=run_id,
        input_mode=mode,
    )
    manifest_path = namespace_dir / INPUT_MANIFEST_FILENAME
    _write_json(manifest_path, _input_manifest_document(
        input_manifest,
        run_id=run_id,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        run_mode=context.run_mode,
        input_mode=mode,
        wall_started_at=wall_started,
        research_observed_at=research_observed_at,
    ))
    candidates = build_integrated_candidates(
        sidecar_rows=sidecars,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        run_mode=context.run_mode,
        run_id=run_id,
        observed_at=research_observed_at,
    )
    candidates_path = namespace_dir / INTEGRATED_CANDIDATES_FILENAME
    _write_jsonl(candidates_path, candidates)
    report_path = namespace_dir / INTEGRATED_REPORT_FILENAME
    report_path.write_text(
        format_integrated_radar_report(candidates, context=context, input_manifest=input_manifest),
        encoding="utf-8",
    )
    core_result = event_core_opportunity_store.write_core_opportunities(
        candidates,
        cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=context.core_opportunity_store_path),
        now=research_observed_at,
        run_id=run_id,
        profile=context.profile,
        run_mode=context.run_mode,
        artifact_namespace=context.artifact_namespace,
    )
    core_rows = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
        include_legacy=True,
    ).rows
    card_result = event_research_cards.write_research_cards(
        context.research_cards_dir,
        watchlist_entries=(),
        alert_rows=core_rows,
        include_all_alertable=True,
        limit=25,
        now=research_observed_at,
        lineage_context={
            "run_id": run_id,
            "profile": context.profile,
            "artifact_namespace": context.artifact_namespace,
            "run_mode": context.run_mode,
        },
    )
    event_core_opportunity_store.update_core_opportunity_card_links(
        context.core_opportunity_store_path,
        card_result.card_paths,
        run_id=run_id,
    )
    core_rows = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
        include_legacy=True,
    ).rows
    readiness_report = event_live_provider_readiness.build_readiness_report(
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        smoke_mode=fixture,
        now=research_observed_at,
    )
    readiness_json_path, readiness_md_path = event_live_provider_readiness.write_readiness_artifacts(
        readiness_report,
        namespace_dir,
    )
    source_coverage_path = namespace_dir / SOURCE_COVERAGE_FILENAME
    source_coverage_path.write_text(
        format_integrated_source_coverage(
            candidates,
            readiness_json_path=readiness_json_path,
            readiness_md_path=readiness_md_path,
        ),
        encoding="utf-8",
    )
    source_coverage_json_path = namespace_dir / SOURCE_COVERAGE_JSON_FILENAME
    _write_json(
        source_coverage_json_path,
        format_integrated_source_coverage_json(
            candidates,
            input_manifest=input_manifest,
            readiness_json_path=readiness_json_path,
            readiness_md_path=readiness_md_path,
        ),
    )
    delivery_path = namespace_dir / INTEGRATED_DELIVERIES_FILENAME
    delivery_rows = build_integrated_notification_delivery_rows(
        candidates,
        core_rows=core_rows,
        context=context,
        run_id=run_id,
        generated_at=research_observed_at,
        send_guard_enabled=False,
    )
    _write_jsonl(delivery_path, delivery_rows)
    daily_brief_path = namespace_dir / DAILY_BRIEF_FILENAME
    daily_brief_path.write_text(
        format_integrated_daily_brief(
            candidates,
            core_rows=core_rows,
            context=context,
            input_manifest=input_manifest,
            delivery_rows=delivery_rows,
            source_coverage_path=source_coverage_path,
        ),
        encoding="utf-8",
    )
    preview_path = namespace_dir / NOTIFICATION_PREVIEW_FILENAME
    preview_path.write_text(
        format_integrated_notification_preview_from_deliveries(
            delivery_rows,
            candidates=candidates,
            core_rows=core_rows,
            context=context,
        ),
        encoding="utf-8",
    )
    finished = datetime.now(timezone.utc)
    lane_due = Counter(str(row.get("lane") or "unknown") for row in delivery_rows if row.get("would_send"))
    lane_empty = Counter(str(row.get("lane") or "unknown") for row in delivery_rows if not row.get("would_send"))
    rendered_items = sum(_int(row.get("rendered_item_count")) for row in delivery_rows)
    eligible_items = sum(_int(row.get("eligible_item_count")) for row in delivery_rows)
    skipped_items = sum(_int(row.get("skipped_item_count")) for row in delivery_rows)
    skip_reasons: Counter[str] = Counter()
    for row in delivery_rows:
        for item in row.get("skipped_items") or ():
            if isinstance(item, Mapping):
                skip_reasons[str(item.get("reason") or "unknown")] += 1
    sidecar_counts = _sidecar_count_summary(sidecars)
    operator_absolute_paths = sum(
        1
        for path in (report_path, daily_brief_path, preview_path, source_coverage_path, *card_result.card_paths)
        if _artifact_has_absolute_operator_path(path)
    )
    result = EventIntegratedRadarResult(
        namespace_dir=namespace_dir,
        run_id=run_id,
        profile=context.profile,
        run_mode=context.run_mode,
        artifact_namespace=context.artifact_namespace,
        started_at=wall_started,
        finished_at=finished,
        research_observed_at=research_observed_at,
        wall_started_at=wall_started,
        wall_finished_at=finished,
        raw_events=sum(len(rows) for rows in sidecars.values()),
        market_anomalies=sidecar_counts["market_anomalies"],
        market_state_snapshots=sidecar_counts["market_state_snapshots"],
        official_exchange_events=sidecar_counts["official_exchange_events"],
        official_listing_candidates=sidecar_counts["official_listing_candidates"],
        scheduled_catalysts=sidecar_counts["scheduled_catalysts"],
        unlock_candidates=sidecar_counts["unlock_candidates"],
        derivatives_state_rows=sidecar_counts["derivatives_state_rows"],
        derivatives_crowding_candidates=sidecar_counts["derivatives_crowding_candidates"],
        fade_review_candidates=sidecar_counts["fade_review_candidates"],
        integrated_candidates=len(candidates),
        candidates=len(candidates),
        core_opportunity_rows_written=core_result.rows_written,
        core_opportunity_write_attempted=core_result.attempted,
        core_opportunity_write_success=core_result.success,
        core_opportunity_write_block_reason=core_result.block_reason,
        research_card_paths=card_result.card_paths,
        research_cards_dir=str(context.research_cards_dir),
        integrated_candidates_path=candidates_path,
        integrated_report_path=report_path,
        daily_brief_path=daily_brief_path,
        notification_preview_path=preview_path,
        integrated_delivery_path=delivery_path,
        run_ledger_path=str(context.run_ledger_path),
        core_opportunity_store_path=str(context.core_opportunity_store_path),
        input_manifest_path=manifest_path,
        source_coverage_json_path=source_coverage_json_path,
        source_coverage_path=source_coverage_path,
        send_lane_items_attempted=dict(lane_due),
        send_lane_items_delivered={lane: 0 for lane in lane_due},
        send_would_send_items=sum(lane_due.values()),
        research_review_digest_enabled=False,
        research_review_digest_candidates=0,
        research_review_digest_would_send=0,
        snapshot_rows_written=len(candidates),
        strict_alerts=0,
        alertable_decisions=0,
        research_candidates=len(candidates),
        raw_source_candidates=len(candidates),
        cards_written=card_result.cards_written,
        research_cards_written=card_result.cards_written,
        preview_rendered_items=rendered_items,
        preview_eligible_items=eligible_items,
        preview_skipped_items=skipped_items,
        preview_skip_reason_counts=dict(skip_reasons),
        integrated_delivery_rows=len(delivery_rows),
        integrated_lanes_rendered=dict(lane_due),
        integrated_lanes_empty=dict(lane_empty),
        operator_absolute_path_count=operator_absolute_paths,
        source_coverage_json_path_rel=event_artifact_paths.artifact_relpath(source_coverage_json_path),
        source_coverage_md_path_rel=event_artifact_paths.artifact_relpath(source_coverage_path),
        warnings=tuple(_integrated_warnings(candidates)),
    )
    event_alpha_run_ledger.append_run_record(
        result,
        cfg=event_alpha_run_ledger.EventAlphaRunLedgerConfig(path=context.run_ledger_path),
        profile=context.profile,
        started_at=wall_started,
        finished_at=finished,
        with_llm=False,
        send_requested=False,
        notification_burn_in=context.run_mode == "notification_burn_in",
        success=True,
    )
    return result


def build_integrated_candidates(
    *,
    sidecar_rows: Mapping[str, Iterable[Mapping[str, Any]]],
    profile: str | None,
    artifact_namespace: str | None,
    run_mode: str | None,
    run_id: str | None,
    observed_at: datetime | str | None = None,
) -> tuple[dict[str, Any], ...]:
    """Merge sidecar rows into one candidate per canonical family."""
    observed = _as_utc(_parse_time(observed_at) or datetime.now(timezone.utc)).isoformat()
    grouped: dict[str, list[dict[str, Any]]] = {}
    for origin, rows in sidecar_rows.items():
        for raw in rows:
            if not isinstance(raw, Mapping):
                continue
            row = dict(raw)
            row["_source_origin"] = origin
            key = _candidate_family_key(row)
            grouped.setdefault(key, []).append(row)
    merged = [
        _merge_family(
            key,
            rows,
            profile=profile,
            artifact_namespace=artifact_namespace,
            run_mode=run_mode,
            run_id=run_id,
            observed_at=observed,
        )
        for key, rows in grouped.items()
    ]
    return tuple(sorted(merged, key=_candidate_sort_key, reverse=True))


def format_integrated_radar_report(
    candidates: Iterable[Mapping[str, Any]],
    *,
    context: event_alpha_artifacts.EventAlphaArtifactContext | None = None,
    input_manifest: Iterable[Mapping[str, Any]] = (),
) -> str:
    rows = [dict(row) for row in candidates if isinstance(row, Mapping)]
    lane_counts = Counter(str(row.get("opportunity_type") or "unknown") for row in rows)
    lines = [
        "# Event Alpha Integrated Radar Report",
        "",
        RESEARCH_DISCLAIMER,
        f"Profile: {context.profile if context else 'unknown'}",
        f"Artifact namespace: {context.artifact_namespace if context else 'unknown'}",
        f"Integrated candidates: {len(rows)}",
        "Lanes: " + _format_counts(lane_counts),
        "",
        "## Input Manifest",
    ]
    lines.extend(_input_manifest_lines(input_manifest))
    lines.extend([
        "",
        "## Unified Candidate Stream",
    ])
    for row in rows:
        lines.extend(_candidate_summary_lines(row))
    lines.extend([
        "",
        "No live Telegram sends, paper trades, normal RSI rows, execution, or Event Alpha TRIGGERED_FADE were created.",
    ])
    return "\n".join(lines).rstrip() + "\n"


def format_integrated_daily_brief(
    candidates: Iterable[Mapping[str, Any]],
    *,
    core_rows: Iterable[Mapping[str, Any]] = (),
    context: event_alpha_artifacts.EventAlphaArtifactContext | None = None,
    input_manifest: Iterable[Mapping[str, Any]] = (),
    delivery_rows: Iterable[Mapping[str, Any]] = (),
    outcome_rows: Iterable[Mapping[str, Any]] = (),
    source_coverage_path: str | Path | None = None,
) -> str:
    rows = [dict(row) for row in candidates if isinstance(row, Mapping)]
    deliveries = [dict(row) for row in delivery_rows if isinstance(row, Mapping)]
    outcomes = [dict(row) for row in outcome_rows if isinstance(row, Mapping)]
    manifest_rows = _manifest_rows(input_manifest, context=context)
    core_count = len([row for row in core_rows if isinstance(row, Mapping)])
    would_send = sum(1 for row in deliveries if row.get("would_send"))
    rendered = sum(_int(row.get("rendered_item_count")) for row in deliveries)
    skipped = sum(_int(row.get("skipped_item_count")) for row in deliveries)
    lines = [
        "# Event Alpha Daily Brief",
        "",
        RESEARCH_DISCLAIMER,
        "",
        "## Executive Summary",
        f"Selected run profile: {context.profile if context else 'unknown'}",
        f"Selected run namespace: {context.artifact_namespace if context else 'unknown'}",
        f"- Integrated candidates: {len(rows)}",
        f"- Canonical core opportunities: {core_count}",
        f"- Core opportunities: {core_count}",
        f"- Strict alerts: 0",
        f"- Alertable decisions: 0",
        "- Telegram: no-send guard enabled for this integrated smoke.",
        f"- Source coverage report: {event_artifact_paths.artifact_display_path(source_coverage_path or SOURCE_COVERAGE_FILENAME)}",
        "",
        "### Input Manifest",
    ]
    lines.extend(_input_manifest_lines(manifest_rows, compact=True))
    lines.extend([
        "",
        "### Research Review Digest",
        f"- Lane count sent/due: 0/{would_send}",
        f"- Eligible candidates: {len(_review_candidates(rows))}",
        f"- Preview rendered/skipped: {rendered}/{skipped}",
        "- Delivery: no-send preview only; structured integrated delivery ledger was written.",
        "",
        "## Opportunity Lanes",
    ])
    lane_order = (
        event_market_reaction.EventOpportunityType.EARLY_LONG_RESEARCH.value,
        event_market_reaction.EventOpportunityType.CONFIRMED_LONG_RESEARCH.value,
        event_market_reaction.EventOpportunityType.FADE_SHORT_REVIEW.value,
        event_market_reaction.EventOpportunityType.RISK_ONLY.value,
        event_market_reaction.EventOpportunityType.UNCONFIRMED_RESEARCH.value,
        event_market_reaction.EventOpportunityType.DIAGNOSTIC.value,
    )
    counts = Counter(str(row.get("opportunity_type") or "unknown") for row in rows)
    for lane in lane_order:
        lines.append(f"- {lane}: {counts.get(lane, 0)}")
    sections = (
        ("Early Long Research", event_market_reaction.EventOpportunityType.EARLY_LONG_RESEARCH.value),
        ("Confirmed Long Research", event_market_reaction.EventOpportunityType.CONFIRMED_LONG_RESEARCH.value),
        ("Fade / Short-Review", event_market_reaction.EventOpportunityType.FADE_SHORT_REVIEW.value),
        ("Risk Only", event_market_reaction.EventOpportunityType.RISK_ONLY.value),
        ("Unconfirmed Research", event_market_reaction.EventOpportunityType.UNCONFIRMED_RESEARCH.value),
    )
    for title, lane in sections:
        lines.extend(["", f"## {title}"])
        lane_rows = [row for row in rows if row.get("opportunity_type") == lane]
        if not lane_rows:
            lines.append("- None.")
        for row in lane_rows[:10]:
            lines.extend(_candidate_summary_lines(row, compact=True))
    lines.extend(["", "## Market Anomalies Without Confirmed Catalyst"])
    _append_filtered(lines, rows, lambda row: row.get("source_origin") == "market_anomaly")
    lines.extend(["", "## Fresh Official Exchange Catalysts"])
    _append_filtered(lines, rows, lambda row: "official_exchange" in (row.get("source_origins") or ()))
    lines.extend(["", "## Upcoming Scheduled Catalysts"])
    _append_filtered(lines, rows, lambda row: "scheduled_catalyst" in (row.get("source_origins") or ()))
    lines.extend(["", "## Unlock / Supply Risk"])
    _append_filtered(lines, rows, lambda row: row.get("unlock_event"))
    lines.extend(["", "## Derivatives Crowding / Fade-Review Research"])
    _append_filtered(lines, rows, lambda row: row.get("derivatives_state_snapshot"))
    lines.extend(["", "## Source Coverage"])
    lines.extend(_source_coverage_lines(rows))
    lines.extend(["", "## Outcome Tracker Status"])
    if outcomes:
        matured = sum(1 for row in outcomes if str(row.get("outcome_status") or "") == "filled")
        partial = sum(1 for row in outcomes if str(row.get("outcome_status") or "") != "filled")
        performance_rows = [row for row in outcomes if _truthy(row.get("include_in_performance"))]
        diagnostics = [row for row in outcomes if not _truthy(row.get("include_in_performance"))]
        lines.append(f"- Outcome rows: {len(outcomes)}")
        lines.append(f"- Filled: {matured}")
        lines.append(f"- Partial/missing data: {partial}")
        lines.append(f"- Performance rows: {len(performance_rows)}")
        lines.append(f"- Diagnostics excluded: {len(diagnostics)}")
        for lane, count in Counter(str(row.get("opportunity_type") or "unknown") for row in performance_rows).most_common():
            lines.append(f"- {lane}: {count}")
        lines.extend(["", "## Recently Matured Integrated Radar Outcomes"])
        for row in sorted(performance_rows, key=lambda item: str(item.get("preview_time") or item.get("observed_at") or ""), reverse=True)[:10]:
            lines.append(
                f"- {row.get('symbol')}/{row.get('coin_id')} {row.get('opportunity_type')} "
                f"label={row.get('outcome_label')} primary={_pct(row.get('primary_horizon_return'))} "
                f"vs BTC={_pct(_by_horizon(row.get('relative_return_vs_btc_by_horizon'), row.get('primary_horizon')))} "
                f"status={row.get('outcome_status')}"
            )
        if diagnostics:
            lines.append(f"- Diagnostics excluded from performance: {len(diagnostics)}")
        lines.extend(["", "## Calibration Snapshot"])
        for lane, lane_rows in sorted(_group_by(performance_rows, "opportunity_type").items()):
            validated = sum(1 for row in lane_rows if _outcome_truth(row) == "validated")
            invalidated = sum(1 for row in lane_rows if _outcome_truth(row) == "invalidated/noise")
            inconclusive = sum(1 for row in lane_rows if _outcome_truth(row) == "inconclusive")
            rate = validated / max(1, validated + invalidated)
            lines.append(
                f"- {lane}: rows={len(lane_rows)} validated={validated} "
                f"invalidated/noise={invalidated} inconclusive={inconclusive} "
                f"validation_rate={rate:.2f}"
            )
        lines.append("- Small-sample warning: recommendations only; no automatic threshold or routing changes were applied.")
    else:
        lines.append("- No integrated radar outcomes filled yet.")
    lines.extend(["", "## Diagnostics Appendix"])
    diagnostics = [row for row in rows if row.get("opportunity_type") == event_market_reaction.EventOpportunityType.DIAGNOSTIC.value]
    if not diagnostics:
        lines.append("- None.")
    for row in diagnostics[:10]:
        lines.extend(_candidate_summary_lines(row, compact=True))
    return "\n".join(lines).rstrip() + "\n"


def build_integrated_notification_delivery_rows(
    candidates: Iterable[Mapping[str, Any]],
    *,
    core_rows: Iterable[Mapping[str, Any]] = (),
    context: event_alpha_artifacts.EventAlphaArtifactContext | None = None,
    run_id: str | None = None,
    generated_at: datetime | str | None = None,
    send_guard_enabled: bool = False,
) -> tuple[dict[str, Any], ...]:
    rows = [dict(row) for row in candidates if isinstance(row, Mapping)]
    core_by_id = {str(row.get("core_opportunity_id") or ""): dict(row) for row in core_rows if isinstance(row, Mapping)}
    observed = _as_utc(_parse_time(generated_at) or datetime.now(timezone.utc)).isoformat()
    lane_specs = (
        ("early_long_research", "Early Long Research", event_market_reaction.EventOpportunityType.EARLY_LONG_RESEARCH.value),
        ("confirmed_long_research", "Confirmed Long Research", event_market_reaction.EventOpportunityType.CONFIRMED_LONG_RESEARCH.value),
        ("fade_short_review", "Fade / Short-Review", event_market_reaction.EventOpportunityType.FADE_SHORT_REVIEW.value),
        ("risk_only", "Risk Only", event_market_reaction.EventOpportunityType.RISK_ONLY.value),
        ("unconfirmed_research", "Unconfirmed Research", event_market_reaction.EventOpportunityType.UNCONFIRMED_RESEARCH.value),
    )
    out: list[dict[str, Any]] = []
    for lane, title, opportunity_type in lane_specs:
        lane_rows = [row for row in rows if row.get("opportunity_type") == opportunity_type]
        message = _integrated_lane_message(
            lane_rows,
            lane_title=title,
            context=context,
            lane=lane,
            core_by_id=core_by_id,
        )
        out.append(_integrated_delivery_row(
            lane=lane,
            lane_title=title,
            message_text=message,
            rendered_rows=lane_rows,
            skipped_rows=(),
            core_by_id=core_by_id,
            context=context,
            run_id=run_id,
            observed=observed,
            send_guard_enabled=send_guard_enabled,
        ))
    diagnostics = [row for row in rows if row.get("opportunity_type") == event_market_reaction.EventOpportunityType.DIAGNOSTIC.value]
    health_message = _integrated_lane_message(
        (),
        lane_title="Source / Provider Health",
        context=context,
        lane="source_provider_health",
        extra_lines=(
            "Lane-critical source priority: official exchange, derivatives/OI/funding, structured unlock/calendar, DEX/on-chain, protocol fundamentals, CryptoPanic tagged news, RSS/GDELT context.",
            f"Diagnostic rows hidden from candidate lanes: {len(diagnostics)}",
        ),
    )
    out.append(_integrated_delivery_row(
        lane="source_provider_health",
        lane_title="Source / Provider Health",
        message_text=health_message,
        rendered_rows=(),
        skipped_rows=diagnostics,
        core_by_id=core_by_id,
        context=context,
        run_id=run_id,
        observed=observed,
        send_guard_enabled=send_guard_enabled,
    ))
    return tuple(out)


def format_integrated_notification_preview_from_deliveries(
    delivery_rows: Iterable[Mapping[str, Any]],
    *,
    candidates: Iterable[Mapping[str, Any]] = (),
    core_rows: Iterable[Mapping[str, Any]] = (),
    context: event_alpha_artifacts.EventAlphaArtifactContext | None = None,
) -> str:
    deliveries = [dict(row) for row in delivery_rows if isinstance(row, Mapping)]
    rows = [dict(row) for row in candidates if isinstance(row, Mapping)]
    due = sum(1 for row in deliveries if row.get("would_send"))
    rendered = sum(_int(row.get("rendered_item_count")) for row in deliveries)
    eligible = sum(_int(row.get("eligible_item_count")) for row in deliveries)
    skipped = sum(_int(row.get("skipped_item_count")) for row in deliveries)
    skip_reasons: Counter[str] = Counter()
    for row in deliveries:
        for item in row.get("skipped_items") or ():
            if isinstance(item, Mapping):
                skip_reasons[str(item.get("reason") or "unknown")] += 1
    lines = [
        "🧭 Event Alpha Integrated Radar Preview",
        "Research-only / unvalidated. Not a trade signal.",
        f"Profile: {context.profile if context else 'unknown'}",
        f"Namespace: {context.artifact_namespace if context else 'unknown'}",
        "No-send rehearsal: would send, but send guard is disabled.",
        "This is expected in rehearsal mode. No Telegram delivery attempted.",
        "",
        "Summary:",
        f"- Strict alerts: 0",
        f"- Alertable decisions: 0",
        f"- Research candidates: {len(rows)}",
        f"- Raw source candidates: {len(rows)}",
        f"- Canonical core opportunities: {len([row for row in core_rows if isinstance(row, Mapping)])}",
        f"- Preview rendered items: {rendered}",
        f"- Preview eligible items: {eligible}",
        f"- Preview skipped items: {skipped}",
        f"- Delivery lanes due/sent/blocked: {due}/0/{due}",
        f"- Skip reasons: {_format_counts(skip_reasons) if skip_reasons else 'none'}",
        "",
    ]
    for row in deliveries:
        lines.append(f"## Lane: {row.get('lane_title') or row.get('lane')}")
        lines.append(f"- status: {row.get('status')}")
        lines.append(f"- would_send: {str(bool(row.get('would_send'))).lower()}")
        lines.append(f"- rendered_items: {row.get('rendered_item_count')}")
        lines.append(f"- skipped_items: {row.get('skipped_item_count')}")
        if row.get("skipped_items"):
            reasons = Counter(str(item.get("reason") or "unknown") for item in row.get("skipped_items") or () if isinstance(item, Mapping))
            lines.append(f"- skip_reasons: {_format_counts(reasons)}")
        lines.append("")
        body = str(row.get("message_text") or "").strip()
        if body:
            lines.append(body)
            lines.append("")
    lines.append("This preview avoids the ambiguous raw 'Alerts' count; raw rows are shown as research candidates.")
    return event_artifact_paths.scrub_absolute_paths_from_markdown("\n".join(lines).rstrip() + "\n")


def format_integrated_notification_preview(
    candidates: Iterable[Mapping[str, Any]],
    *,
    core_rows: Iterable[Mapping[str, Any]] = (),
    context: event_alpha_artifacts.EventAlphaArtifactContext | None = None,
    max_review_items: int = 10,
) -> str:
    del max_review_items
    delivery_rows = build_integrated_notification_delivery_rows(
        candidates,
        core_rows=core_rows,
        context=context,
        run_id=None,
        generated_at=datetime.now(timezone.utc),
        send_guard_enabled=False,
    )
    return format_integrated_notification_preview_from_deliveries(
        delivery_rows,
        candidates=candidates,
        core_rows=core_rows,
        context=context,
    )


def _integrated_lane_message(
    rows: Iterable[Mapping[str, Any]],
    *,
    lane_title: str,
    context: event_alpha_artifacts.EventAlphaArtifactContext | None,
    lane: str,
    core_by_id: Mapping[str, Mapping[str, Any]] | None = None,
    extra_lines: Iterable[str] = (),
) -> str:
    materialized = [dict(row) for row in rows if isinstance(row, Mapping)]
    lines = [
        f"🧭 Event Alpha {lane_title}",
        "Research-only / unvalidated. Not a trade signal.",
        f"Profile: {context.profile if context else 'unknown'}",
        f"Lane: {lane}",
        f"Items: {len(materialized)}",
        "",
    ]
    if not materialized:
        lines.append("- No candidate items in this lane.")
    for index, row in enumerate(materialized, start=1):
        card_path = _row_card_path(row, core_by_id=core_by_id)
        lines.extend([
            f"{index}. {row.get('symbol')}/{row.get('coin_id')}",
            f"   Opportunity: {row.get('opportunity_type') or 'unknown'}",
            f"   Why now: {row.get('why_now') or 'unknown'}",
            f"   Evidence: {row.get('source_pack') or 'unknown'}; source={row.get('source_class') or 'unknown'}",
            f"   Market state: {row.get('market_state_class') or 'unknown'}",
            f"   What confirms: {_list_label(row.get('what_confirms') or ())}",
            f"   What invalidates: {_list_label(row.get('what_invalidates') or ())}",
            f"   Why not alertable: {_list_label(row.get('why_not_alertable') or ())}",
            f"   Card: {card_path or 'not generated'}",
            "",
        ])
    for extra in extra_lines:
        text = str(extra or "").strip()
        if text:
            lines.append(f"- {text}")
    return event_artifact_paths.scrub_absolute_paths_from_markdown("\n".join(lines).rstrip())


def _integrated_delivery_row(
    *,
    lane: str,
    lane_title: str,
    message_text: str,
    rendered_rows: Iterable[Mapping[str, Any]],
    skipped_rows: Iterable[Mapping[str, Any]],
    core_by_id: Mapping[str, Mapping[str, Any]],
    context: event_alpha_artifacts.EventAlphaArtifactContext | None,
    run_id: str | None,
    observed: str,
    send_guard_enabled: bool,
) -> dict[str, Any]:
    rendered = [dict(row) for row in rendered_rows if isinstance(row, Mapping)]
    skipped = [dict(row) for row in skipped_rows if isinstance(row, Mapping)]
    would_send = bool(rendered or lane == "source_provider_health")
    status = (
        "would_send_but_guard_disabled"
        if would_send and not send_guard_enabled
        else ("sent" if would_send and send_guard_enabled else "not_due")
    )
    card_paths = tuple(dict.fromkeys(path for row in rendered for path in (_row_card_path(row, core_by_id=core_by_id),) if path))
    skipped_items = tuple(
        {
            "candidate_id": row.get("candidate_id"),
            "core_opportunity_id": row.get("core_opportunity_id"),
            "symbol": row.get("symbol"),
            "coin_id": row.get("coin_id"),
            "reason": "diagnostic_only_hidden_from_research_lanes",
        }
        for row in skipped
    )
    safe_text = event_artifact_paths.scrub_absolute_paths_from_markdown(message_text)
    return {
        "schema_version": 1,
        "row_type": "event_integrated_radar_notification_delivery",
        "run_id": run_id,
        "profile": context.profile if context else "unknown",
        "artifact_namespace": context.artifact_namespace if context else "unknown",
        "run_mode": context.run_mode if context else "unknown",
        "lane": lane,
        "lane_title": lane_title,
        "route": "INTEGRATED_RADAR_RESEARCH_PREVIEW",
        "status": status,
        "would_send": would_send,
        "sent": False,
        "send_guard_enabled": bool(send_guard_enabled),
        "no_send_rehearsal": not send_guard_enabled,
        "rendered_item_count": len(rendered),
        "eligible_item_count": len(rendered),
        "skipped_item_count": len(skipped),
        "skipped_items": skipped_items,
        "candidate_ids": tuple(str(row.get("candidate_id") or "") for row in rendered if row.get("candidate_id")),
        "core_opportunity_ids": tuple(str(row.get("core_opportunity_id") or "") for row in rendered if row.get("core_opportunity_id")),
        "canonical_symbols": tuple(str(row.get("symbol") or "") for row in rendered if row.get("symbol")),
        "card_paths": card_paths,
        "content_hash": hashlib.sha256(safe_text.encode("utf-8")).hexdigest(),
        "message_text": safe_text,
        "message_html": None,
        "generated_at": observed,
        "research_only": True,
        "created_alert": False,
        "normal_rsi_signal_written": False,
        "triggered_fade_created": False,
        "paper_trade_created": False,
        "notification_send_attempted": False,
        "telegram_send_attempted": False,
    }


def _row_card_path(
    row: Mapping[str, Any],
    *,
    core_by_id: Mapping[str, Mapping[str, Any]] | None = None,
) -> str:
    for key in ("research_card_path", "card_path"):
        value = row.get(key)
        if value:
            return event_artifact_paths.artifact_display_path(value)
    if core_by_id:
        core = core_by_id.get(str(row.get("core_opportunity_id") or ""))
        if core:
            for key in ("research_card_path", "card_path"):
                value = core.get(key)
                if value:
                    return event_artifact_paths.artifact_display_path(value)
    return ""


def format_integrated_source_coverage(
    candidates: Iterable[Mapping[str, Any]],
    *,
    readiness_json_path: str | Path | None = None,
    readiness_md_path: str | Path | None = None,
) -> str:
    rows = [dict(row) for row in candidates if isinstance(row, Mapping)]
    source_counts = Counter(
        source for row in rows for source in (row.get("source_packs") or [row.get("source_pack") or "unknown"])
    )
    lines = [
        "# Event Alpha Source Coverage",
        "",
        RESEARCH_DISCLAIMER,
        "",
        "## Lane-Critical Source Priority",
        "1. official exchange announcements",
        "2. derivatives/OI/funding",
        "3. structured unlock/calendar data",
        "4. DEX/on-chain liquidity",
        "5. protocol fundamentals",
        "6. CryptoPanic tagged news",
        "7. RSS/GDELT broad context only",
        "",
        "## Observed Source Packs",
    ]
    for pack, count in source_counts.most_common():
        lines.append(f"- {pack}: {count}")
    lines.extend(["", "Most useful next data source categories:"])
    for idx, category in enumerate(event_alpha_source_coverage.SOURCE_COVERAGE_CATEGORY_PRIORITIES, start=1):
        providers = ", ".join(str(item) for item in category.get("providers") or ()) or "none"
        lanes = ", ".join(str(item) for item in category.get("enabled_lanes") or ()) or "none"
        lines.extend(
            [
                f"{idx}. {category.get('category')}",
                f"   providers: {providers}",
                f"   enables: {lanes}",
                f"   reason: {category.get('reason') or 'none'}",
            ]
        )
    if readiness_md_path or readiness_json_path:
        lines.extend([
            "",
            "Live-provider activation readiness:",
            f"- readiness report: {event_artifact_paths.artifact_display_path(readiness_md_path or event_live_provider_readiness.READINESS_MD)}",
            f"- readiness JSON: {event_artifact_paths.artifact_display_path(readiness_json_path or event_live_provider_readiness.READINESS_JSON)}",
            "- command: make event-alpha-live-provider-readiness PROFILE=fixture ARTIFACT_NAMESPACE=integrated_radar_smoke",
            "- next activation plan: use no-send/readiness commands only; no live calls were made by this smoke.",
        ])
    else:
        lines.extend([
            "",
            "Live-provider activation readiness:",
            "- readiness: not generated; run make event-alpha-live-provider-readiness PROFILE=fixture ARTIFACT_NAMESPACE=integrated_radar_smoke",
        ])
    return "\n".join(lines).rstrip() + "\n"


def format_integrated_source_coverage_json(
    candidates: Iterable[Mapping[str, Any]],
    *,
    input_manifest: Iterable[Mapping[str, Any]] = (),
    readiness_json_path: str | Path | None = None,
    readiness_md_path: str | Path | None = None,
) -> dict[str, Any]:
    rows = [dict(row) for row in candidates if isinstance(row, Mapping)]
    source_counts = Counter(
        source for row in rows for source in (row.get("source_packs") or [row.get("source_pack") or "unknown"])
    )
    lane_counts = Counter(str(row.get("opportunity_type") or "unknown") for row in rows)
    return {
        "schema_version": 1,
        "row_type": "event_alpha_source_coverage",
        "source": "integrated_radar",
        "candidate_count": len(rows),
        "lane_counts": dict(sorted(lane_counts.items())),
        "source_pack_counts": dict(source_counts.most_common()),
        "live_provider_readiness_report_path": event_artifact_paths.artifact_display_path(readiness_md_path)
        if readiness_md_path
        else None,
        "live_provider_readiness_json_path": event_artifact_paths.artifact_display_path(readiness_json_path)
        if readiness_json_path
        else None,
        "category_priorities": [
            {
                "category_priority_rank": idx + 1,
                "category": item.get("category"),
                "providers": list(item.get("providers") or ()),
                "enabled_lanes": list(item.get("enabled_lanes") or ()),
                "reason": item.get("reason"),
            }
            for idx, item in enumerate(event_alpha_source_coverage.SOURCE_COVERAGE_CATEGORY_PRIORITIES)
        ],
        "lane_critical_priority": [
            "official_exchange_announcements",
            "derivatives_oi_funding",
            "structured_unlock_calendar",
            "dex_onchain_liquidity",
            "protocol_fundamentals",
            "cryptopanic_tagged_news",
            "rss_gdelt_context",
        ],
        "input_manifest": [dict(item) for item in input_manifest if isinstance(item, Mapping)],
    }


def load_integrated_candidates(namespace_dir: str | Path) -> tuple[dict[str, Any], ...]:
    return tuple(_read_jsonl(Path(namespace_dir) / INTEGRATED_CANDIDATES_FILENAME))


def load_integrated_notification_deliveries(namespace_dir: str | Path) -> tuple[dict[str, Any], ...]:
    return tuple(_read_jsonl(Path(namespace_dir) / INTEGRATED_DELIVERIES_FILENAME))


def _run_or_load_sidecars(
    *,
    namespace_dir: Path,
    fixture: bool,
    observed_at: datetime,
    profile: str,
    artifact_namespace: str,
    run_mode: str,
    run_id: str,
    input_mode: str,
) -> tuple[dict[str, tuple[dict[str, Any], ...]], tuple[dict[str, Any], ...]]:
    if fixture:
        rows = _run_fixture_sidecars(
            namespace_dir=namespace_dir,
            observed_at=observed_at,
            profile=profile,
            artifact_namespace=artifact_namespace,
            run_mode=run_mode,
            run_id=run_id,
        )
        return rows, tuple(
            _manifest_item(
                sidecar_name=name,
                mode="ran_fixture",
                namespace_dir=namespace_dir,
                rows=value,
                configured=True,
                sidecar_research_observed_at=observed_at,
                wall_started_at=datetime.now(timezone.utc),
                wall_finished_at=datetime.now(timezone.utc),
            )
            for name, value in rows.items()
        )
    if input_mode == INPUT_MODE_RUN_SIDECARS:
        rows = {
            "market_anomaly": (),
            "official_exchange": (),
            "scheduled_catalyst": (),
            "unlock": (),
            "derivatives": (),
        }
        manifest = tuple(
            _manifest_item(
                sidecar_name=name,
                mode="skipped_provider_unavailable",
                namespace_dir=namespace_dir,
                rows=value,
                configured=False,
                sidecar_research_observed_at=observed_at,
                wall_started_at=datetime.now(timezone.utc),
                wall_finished_at=datetime.now(timezone.utc),
                warnings=("configured sidecar execution is not enabled in this research-only integrated path",),
            )
            for name, value in rows.items()
        )
        return rows, manifest
    derivatives_rows = tuple(event_derivatives_crowding.load_derivatives_candidates(namespace_dir))
    derivatives_mode, derivatives_configured, derivatives_warnings = _derivatives_manifest_mode(namespace_dir, derivatives_rows)
    rows = {
        "market_anomaly": tuple(event_market_anomaly_scanner.load_market_anomaly_rows(namespace_dir)),
        "official_exchange": _official_exchange_integration_rows(
            event_official_exchange.load_official_exchange_events(namespace_dir),
            event_official_exchange.load_official_listing_candidates(namespace_dir),
        ),
        "scheduled_catalyst": tuple(event_scheduled_catalysts.load_scheduled_catalysts(namespace_dir)),
        "unlock": tuple(event_scheduled_catalysts.load_unlock_candidates(namespace_dir)),
        "derivatives": derivatives_rows,
    }
    manifest = tuple(
        _manifest_item(
            sidecar_name=name,
            mode=derivatives_mode if name == "derivatives" else "loaded_existing" if value else "skipped_missing_config",
            namespace_dir=namespace_dir,
            rows=value,
            configured=derivatives_configured if name == "derivatives" else bool(value),
            sidecar_research_observed_at=observed_at,
            wall_started_at=datetime.now(timezone.utc),
            wall_finished_at=datetime.now(timezone.utc),
            warnings=derivatives_warnings if name == "derivatives" else () if value else (f"{name} sidecar artifact missing or empty",),
        )
        for name, value in rows.items()
    )
    return rows, manifest


def _derivatives_manifest_mode(namespace_dir: Path, derivatives_rows: tuple[dict[str, Any], ...]) -> tuple[str, bool, tuple[str, ...]]:
    from . import event_coinalyze_preflight

    rehearsal_path = namespace_dir / event_coinalyze_preflight.REHEARSAL_JSON
    state_path = namespace_dir / event_derivatives_crowding.DERIVATIVES_STATE_FILENAME
    if derivatives_rows:
        return "loaded_existing", True, ()
    if not rehearsal_path.exists():
        return "skipped_missing_config", False, ("derivatives sidecar artifact missing or empty",)
    try:
        payload = json.loads(rehearsal_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    status = str(payload.get("status") or "unknown") if isinstance(payload, Mapping) else "unknown"
    if status == "missing_config":
        return "skipped_missing_config", False, ("coinalyze rehearsal missing_config",)
    if status == "live_call_blocked_by_default":
        return "live_blocked_by_default", True, ("coinalyze live call blocked by default",)
    if state_path.exists():
        return "loaded_existing", True, (f"coinalyze rehearsal status={status}",)
    return "skipped_missing_config", False, (f"coinalyze rehearsal status={status} without derivatives state",)


def _run_fixture_sidecars(
    *,
    namespace_dir: Path,
    observed_at: datetime,
    profile: str,
    artifact_namespace: str,
    run_mode: str,
    run_id: str,
) -> dict[str, tuple[dict[str, Any], ...]]:
    market = event_market_anomaly_scanner.run_market_anomaly_scan(
        market_rows=_fixture_market_rows(),
        namespace_dir=namespace_dir,
        observed_at=observed_at,
        profile=profile,
        artifact_namespace=artifact_namespace,
        run_mode=run_mode,
        run_id=run_id,
    )
    with TemporaryDirectory(prefix="event-alpha-integrated-", dir=str(namespace_dir)) as tmpdir:
        tmp = Path(tmpdir)
        binance_path = tmp / "binance.json"
        bybit_path = tmp / "bybit.json"
        tokenomist_path = tmp / "tokenomist.json"
        coinmarketcal_path = tmp / "coinmarketcal.json"
        derivatives_path = tmp / "derivatives.json"
        _write_json(binance_path, {"items": _fixture_binance_announcements()})
        _write_json(bybit_path, {"items": _fixture_bybit_announcements()})
        _write_json(tokenomist_path, {"items": _fixture_unlocks()})
        _write_json(coinmarketcal_path, {"items": _fixture_calendar_events()})
        _write_json(derivatives_path, _fixture_derivatives_payload())
        official = event_official_exchange.run_official_exchange_scan(
            namespace_dir=namespace_dir,
            provider_paths={"binance": binance_path, "bybit": bybit_path},
            profile=profile,
            artifact_namespace=artifact_namespace,
            run_mode=run_mode,
            run_id=run_id,
            observed_at=observed_at,
        )
        scheduled = event_scheduled_catalysts.run_scheduled_catalyst_scan(
            namespace_dir=namespace_dir,
            provider_paths={"tokenomist": tokenomist_path, "coinmarketcal": coinmarketcal_path},
            profile=profile,
            artifact_namespace=artifact_namespace,
            run_mode=run_mode,
            run_id=run_id,
            observed_at=observed_at,
        )
        derivatives = event_derivatives_crowding.run_derivatives_crowding_scan(
            namespace_dir=namespace_dir,
            derivatives_path=derivatives_path,
            profile=profile,
            artifact_namespace=artifact_namespace,
            run_mode=run_mode,
            run_id=run_id,
            observed_at=observed_at,
        )
    return {
        "market_anomaly": market.anomalies,
        "official_exchange": _official_exchange_integration_rows(official.events, official.candidates),
        "scheduled_catalyst": scheduled.scheduled_events,
        "unlock": scheduled.unlock_candidates,
        "derivatives": derivatives.candidate_rows,
    }


def _official_exchange_integration_rows(
    events: Iterable[Mapping[str, Any]],
    candidates: Iterable[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    """Return official listing candidates plus capped event rows filtered out by the sidecar."""
    rows = [_normalize_official_integration_row(row) for row in candidates if isinstance(row, Mapping)]
    represented: set[tuple[str, str]] = set()
    for row in rows:
        event_id = _text(row.get("official_exchange_event_id") or row.get("source_event_id") or row.get("event_id"))
        symbol = _text(row.get("symbol") or row.get("validated_symbol")).upper()
        if event_id and symbol:
            represented.add((event_id, symbol))
    for event in events:
        if not isinstance(event, Mapping):
            continue
        event_id = _text(event.get("official_exchange_event_id") or event.get("event_id"))
        symbols = [str(item).upper() for item in event.get("symbols") or () if str(item).strip()]
        coin_ids = [str(item) for item in event.get("coin_ids") or () if str(item).strip()]
        if not symbols:
            continue
        for index, symbol in enumerate(symbols):
            if event_id and (event_id, symbol) in represented:
                continue
            coin_id = coin_ids[index] if index < len(coin_ids) else symbol.casefold()
            row = dict(event)
            row.update({
                "row_type": "official_exchange_event_candidate",
                "symbol": symbol,
                "validated_symbol": symbol,
                "coin_id": coin_id,
                "validated_coin_id": coin_id,
                "accepted_evidence_count": 1,
                "rejected_evidence_count": 0,
                "evidence_acquisition_status": "accepted_evidence_found",
                "reason_codes": list(dict.fromkeys([
                    *(str(item) for item in event.get("reason_codes") or () if str(item)),
                    "official_exchange_event_observed",
                ])),
            })
            rows.append(row)
    return tuple(rows)


def _normalize_official_integration_row(row: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    symbol = _text(normalized.get("symbol") or normalized.get("validated_symbol"))
    coin_id = _text(normalized.get("coin_id") or normalized.get("validated_coin_id"))
    if not symbol:
        symbol = _symbol_for_coin_id(coin_id)
        if symbol:
            normalized["symbol"] = symbol
            normalized["validated_symbol"] = symbol
    event_type = str(normalized.get("event_type") or "").casefold()
    if (
        (symbol.upper() in {"BTC", "ETH", "USDT", "USDC", "FDUSD"} or coin_id in {"bitcoin", "ethereum", "tether", "usd-coin", "first-digital-usd"})
        and event_type in {"new_trading_pair", "spot_listing"}
    ):
        normalized["major_pair_simple_announcement"] = True
        reason_codes = [str(item) for item in normalized.get("reason_codes") or () if str(item)]
        normalized["reason_codes"] = list(dict.fromkeys((*reason_codes, "major_pair_simple_announcement_capped")))
    return normalized


def _symbol_for_coin_id(coin_id: str) -> str:
    return {
        "bitcoin": "BTC",
        "ethereum": "ETH",
        "tether": "USDT",
        "usd-coin": "USDC",
        "first-digital-usd": "FDUSD",
    }.get(str(coin_id or "").casefold(), "")


def _merge_family(
    key: str,
    rows: list[dict[str, Any]],
    *,
    profile: str | None,
    artifact_namespace: str | None,
    run_mode: str | None,
    run_id: str | None,
    observed_at: str,
) -> dict[str, Any]:
    origins = tuple(dict.fromkeys(str(row.get("_source_origin") or "unknown") for row in rows))
    source_packs = tuple(dict.fromkeys(str(row.get("source_pack") or "unknown") for row in rows if row.get("source_pack")))
    primary = _select_primary(rows)
    symbol = _text(_first_value(rows, "symbol", "validated_symbol")) or "UNKNOWN"
    coin_id = _text(_first_value(rows, "coin_id", "validated_coin_id")) or symbol.casefold()
    market_snapshot = _best_market_snapshot(rows)
    derivatives_row = _best_derivatives_row(rows)
    official_row = _best_row(
        rows,
        lambda row: str(row.get("row_type")) in {
            "official_listing_candidate",
            "official_exchange_event_candidate",
        },
    )
    scheduled_row = _best_row(rows, lambda row: str(row.get("row_type")) == "scheduled_catalyst_event")
    unlock_row = _best_row(rows, lambda row: str(row.get("row_type")) in {"unlock_event", "unlock_candidate"})
    source_strength = _best_source_strength(rows)
    source_class = _best_text(rows, "source_class") or "unknown"
    source_pack = _best_source_pack(rows, source_packs)
    impact_path = _best_impact_path(rows, source_pack)
    accepted_evidence_count = max(_int(row.get("accepted_evidence_count")) for row in rows)
    evidence_status = _best_text(rows, "evidence_acquisition_status") or ("accepted_evidence_found" if accepted_evidence_count else "not_executed")
    raw_reaction = event_market_reaction.evaluate_market_reaction({
        "symbol": symbol,
        "coin_id": coin_id,
        "source_class": source_class,
        "source_pack": source_pack,
        "impact_path_type": impact_path,
        "evidence_quality_score": _evidence_score(source_strength, accepted_evidence_count),
        "accepted_evidence_count": accepted_evidence_count or (1 if source_strength == "official_structured" else 0),
        "accepted_evidence_reason_codes": _merged_list(rows, "reason_codes"),
        "evidence_acquisition_status": evidence_status,
        "market_snapshot": market_snapshot,
        "derivatives_snapshot": dict(derivatives_row.get("derivatives_state_snapshot") or {}) if derivatives_row else {},
        "event_age_hours": _first_value(rows, "event_age_hours"),
        "catalyst_fresh": True,
        "negative_catalyst": _negative_candidate(rows, impact_path, source_pack),
    })
    opportunity = _policy_opportunity_type(raw_reaction, rows, origins, official_row=official_row)
    score = _score_for(opportunity, raw_reaction, rows, source_strength)
    level, route, state = _level_route_state(opportunity)
    reason_codes = tuple(dict.fromkeys((*_merged_list(rows, "reason_codes"), *raw_reaction.reason_codes)))
    warnings = tuple(dict.fromkeys((*_merged_list(rows, "warnings"), *_policy_warnings(opportunity, rows, raw_reaction))))
    candidate_id = f"iar:{_digest(key)}"
    derivatives_metadata = _derivatives_metadata(derivatives_row)
    integrated_market = _integrated_market_confirmation(opportunity, raw_reaction)
    candidate = {
        "schema_version": 1,
        "row_type": "event_integrated_radar_candidate",
        "candidate_id": candidate_id,
        "candidate_family_id": key,
        "core_opportunity_id": f"agg:{_digest(key)}",
        "run_id": run_id,
        "profile": profile,
        "run_mode": run_mode,
        "artifact_namespace": artifact_namespace,
        "symbol": symbol,
        "validated_symbol": symbol,
        "coin_id": coin_id,
        "validated_coin_id": coin_id,
        "canonical_asset_id": coin_id or symbol,
        "source_origin": "merged" if len(origins) > 1 else origins[0],
        "source_origins": list(origins),
        "source_pack": source_pack,
        "source_packs": list(source_packs or (source_pack,)),
        "source_class": source_class,
        "source_strength": source_strength,
        "opportunity_type": opportunity,
        "market_state_class": raw_reaction.market_state,
        "market_state": raw_reaction.market_state,
        "final_opportunity_level": level,
        "opportunity_level": level,
        "opportunity_score_final": score,
        "final_opportunity_score": score,
        "route": route,
        "tier": route,
        "final_route_after_quality_gate": route,
        "alertable_after_quality_gate": False,
        "state": state,
        "final_state_after_quality_gate": state,
        "score": score,
        "source_requirements_met": _source_requirements_met(opportunity, rows, source_strength),
        "market_requirements_met": _market_requirements_met(opportunity, raw_reaction),
        "fade_requirements_met": _fade_requirements_met(opportunity, rows),
        "risk_requirements_met": _risk_requirements_met(opportunity, rows),
        "integrated_market_confirmation_level": integrated_market["level"],
        "integrated_market_confirmation_score": integrated_market["score"],
        "integrated_market_reaction_confirmation": integrated_market["reaction"],
        "integrated_market_context_source": integrated_market["source"],
        "integrated_market_freshness_status": integrated_market["freshness"],
        "market_state_snapshot": raw_reaction.market_state_snapshot.to_dict(),
        "latest_market_snapshot": market_snapshot,
        "market_snapshot": market_snapshot,
        "derivatives_state_snapshot": dict(derivatives_row.get("derivatives_state_snapshot") or {}) if derivatives_row else None,
        "derivatives_snapshot": dict(derivatives_row.get("derivatives_state_snapshot") or {}) if derivatives_row else None,
        "crowding_class": derivatives_metadata.get("crowding_class"),
        "fade_readiness": derivatives_metadata.get("fade_readiness"),
        "crowding_exhaustion_evidence": derivatives_metadata.get("crowding_exhaustion_evidence") or [],
        "what_confirms_fade_review": derivatives_metadata.get("what_confirms_fade_review") or [],
        "what_invalidates_fade_review": derivatives_metadata.get("what_invalidates_fade_review") or [],
        "derivatives_warning_codes": derivatives_metadata.get("derivatives_warning_codes") or [],
        "official_exchange_event": _compact_event(official_row) if official_row else None,
        "scheduled_catalyst_event": _compact_event(scheduled_row) if scheduled_row else None,
        "unlock_event": _compact_event(unlock_row) if unlock_row else None,
        "evidence_acquisition_status": evidence_status,
        "accepted_evidence_count": accepted_evidence_count,
        "rejected_evidence_count": max(_int(row.get("rejected_evidence_count")) for row in rows),
        "why_now": _why_now_for(opportunity, raw_reaction, rows),
        "what_confirms": list(raw_reaction.what_confirms),
        "what_invalidates": list(raw_reaction.what_invalidates),
        "why_not_alertable": list(dict.fromkeys((*raw_reaction.why_not_alertable, *_lane_why_not(opportunity, rows)))),
        "reason_codes": list(reason_codes),
        "warnings": list(warnings),
        "research_only": True,
        "created_alert": False,
        "normal_rsi_signal_written": False,
        "triggered_fade_created": False,
        "paper_trade_created": False,
        "notification_send_enabled": False,
        "candidate_role": _candidate_role_for(opportunity),
        "primary_impact_path": impact_path,
        "impact_path_type": impact_path,
        "effective_playbook_type": impact_path,
        "playbook_type": impact_path,
        "impact_category": impact_path,
        "canonical_incident_name": _canonical_incident_name(rows, symbol, opportunity),
        "incident_id": f"incident:{_digest(key)}",
        "event_name": _best_text(rows, "event_name", "title") or _canonical_incident_name(rows, symbol, opportunity),
        "latest_event_name": _best_text(rows, "event_name", "title") or _canonical_incident_name(rows, symbol, opportunity),
        "source_url": _best_text(rows, "source_url", "url"),
        "supporting_evidence_quotes": _supporting_quotes(rows),
        "supporting_categories": list(dict.fromkeys(_merged_list(rows, "impact_path_type") or [impact_path])),
        "supporting_impact_paths": list(dict.fromkeys(_merged_list(rows, "impact_path_type") or [impact_path])),
        "source_count": len(origins),
        "latest_score": score,
        "latest_tier": route,
        "observed_at": observed_at,
        "created_at": observed_at,
    }
    if opportunity == event_market_reaction.EventOpportunityType.DIAGNOSTIC.value:
        candidate["diagnostic_row_count"] = max(1, len(rows))
    return candidate


def _fixture_market_rows() -> tuple[dict[str, Any], ...]:
    return (
        {"symbol": "BTC", "coin_id": "bitcoin", "price": 65000, "return_unit": "fraction", "return_1h": 0.0, "return_4h": 0.0, "return_24h": 0.0, "volume_zscore_24h": 0.0, "liquidity_usd": 5_000_000_000},
        {"symbol": "ETH", "coin_id": "ethereum", "price": 3200, "return_unit": "fraction", "return_1h": 0.001, "return_4h": 0.002, "return_24h": 0.004, "volume_zscore_24h": 0.2, "liquidity_usd": 2_000_000_000},
        {"symbol": "TESTPERP", "coin_id": "test-perp", "price": 2.4, "return_unit": "fraction", "return_1h": 0.035, "return_4h": 0.11, "return_24h": 0.18, "relative_return_vs_btc_4h": 10.0, "volume_zscore_24h": 3.4, "volume_to_market_cap": 0.32, "liquidity_usd": 18_000_000, "spread_bps": 18},
        {"symbol": "TESTFADE", "coin_id": "test-fade", "price": 5.2, "return_unit": "fraction", "return_1h": 0.06, "return_4h": 0.21, "return_24h": 0.42, "volume_zscore_24h": 4.8, "volume_to_market_cap": 0.45, "liquidity_usd": 3_500_000, "spread_bps": 42, "event_age_hours": 3},
        {"symbol": "TESTRUMOR", "coin_id": "test-rumor", "price": 0.5, "return_unit": "fraction", "return_1h": 0.002, "return_4h": 0.004, "return_24h": 0.01, "volume_zscore_24h": 0.4, "liquidity_usd": 1_200_000, "spread_bps": 55},
    )


def _fixture_binance_announcements() -> tuple[dict[str, Any], ...]:
    return (
        {
            "id": "binance-testlist",
            "title": "Binance Will List TestList (TESTLIST)",
            "body": "Binance will open spot trading for TESTLIST/USDT.",
            "symbols": ["TESTLIST"],
            "coin_ids": ["test-list"],
            "source_url": "https://www.binance.com/en/support/announcement/testlist",
            "published_at": "2026-06-15T13:00:00Z",
            "effective_time": "2026-06-15T19:00:00Z",
            "market_snapshot": {"return_unit": "fraction", "return_24h": 0.01, "volume_zscore_24h": 0.2, "event_age_hours": -3},
        },
        {
            "id": "binance-testfade",
            "title": "Binance Lists TestFade (TESTFADE)",
            "body": "Binance opened spot trading for TESTFADE/USDT.",
            "symbols": ["TESTFADE"],
            "coin_ids": ["test-fade"],
            "source_url": "https://www.binance.com/en/support/announcement/testfade",
            "published_at": "2026-06-14T12:00:00Z",
            "effective_time": "2026-06-15T13:00:00Z",
            "market_snapshot": {"return_unit": "fraction", "return_4h": 0.21, "return_24h": 0.42, "volume_zscore_24h": 4.8, "event_age_hours": 3, "liquidity_usd": 3_500_000, "spread_bps": 42},
        },
        {
            "id": "binance-btc-pair",
            "title": "Binance Adds BTC/USDT as a New Trading Pair",
            "body": "Binance adds a simple BTC/USDT trading pair.",
            "symbols": ["BTC"],
            "coin_ids": ["bitcoin"],
            "source_url": "https://www.binance.com/en/support/announcement/btcusdt",
            "published_at": "2026-06-15T13:10:00Z",
            "market_snapshot": {"return_unit": "fraction", "return_24h": 0.002, "volume_zscore_24h": 0.1},
        },
    )


def _fixture_bybit_announcements() -> tuple[dict[str, Any], ...]:
    return (
        {
            "id": "bybit-testperp",
            "title": "Bybit Lists TESTPERPUSDT Perpetual Contract",
            "body": "Bybit will launch TESTPERPUSDT perpetual futures.",
            "symbols": ["TESTPERP"],
            "coin_ids": ["test-perp"],
            "source_url": "https://announcements.bybit.com/article/testperp",
            "published_at": "2026-06-15T14:00:00Z",
            "effective_time": "2026-06-15T16:30:00Z",
            "market_snapshot": {"return_unit": "fraction", "return_4h": 0.11, "return_24h": 0.18, "volume_zscore_24h": 3.4, "relative_return_vs_btc": 10.0, "liquidity_usd": 18_000_000, "spread_bps": 18},
        },
    )


def _fixture_unlocks() -> tuple[dict[str, Any], ...]:
    return (
        {
            "id": "tokenomist-testunlock",
            "title": "TESTUNLOCK cliff unlock",
            "symbol": "TESTUNLOCK",
            "coin_id": "test-unlock",
            "source_url": "https://tokenomist.ai/testunlock",
            "unlock_time": "2026-06-16T08:00:00Z",
            "unlock_pct_circulating_supply": 14.0,
            "unlock_vs_30d_adv": 2.6,
            "unlock_usd": 12_000_000,
            "market_snapshot": {"return_unit": "fraction", "return_24h": -0.01, "volume_zscore_24h": 0.4, "event_age_hours": -16, "liquidity_usd": 650_000, "spread_bps": 80},
        },
    )


def _fixture_calendar_events() -> tuple[dict[str, Any], ...]:
    return (
        {
            "id": "coinmarketcal-rumor",
            "title": "TESTRUMOR rumored partnership AMA",
            "description": "Social rumor and calendar mention without official confirmation.",
            "symbol": "TESTRUMOR",
            "coin_id": "test-rumor",
            "source_class": "cryptopanic_tagged",
            "source_url": "https://cryptopanic.com/news/test-rumor",
            "event_time": "2026-06-17T12:00:00Z",
            "market_snapshot": {"return_unit": "fraction", "return_24h": 0.01, "volume_zscore_24h": 0.4, "event_age_hours": -44},
        },
        {
            "id": "sector-ai-theme",
            "title": "AI sector narrative heats up",
            "description": "Broad theme row for diagnostics only.",
            "symbol": "SECTOR",
            "coin_id": "ai_theme",
            "source_class": "broad_news",
            "source_url": "https://example.com/ai-sector",
            "event_time": "2026-06-17T12:00:00Z",
        },
    )


def _fixture_derivatives_payload() -> dict[str, Any]:
    return {
        "derivatives": [
            {"symbol": "TESTFADEUSDT", "coin_id": "test-fade", "open_interest_delta_24h": 0.52, "funding_rate": 0.12, "funding_zscore": 3.2, "liquidation_long_usd": 2_800_000, "liquidation_short_usd": 500_000, "perp_volume": 90_000_000, "spot_volume": 30_000_000, "freshness_status": "fresh"},
            {"symbol": "TESTPERPUSDT", "coin_id": "test-perp", "open_interest_delta_24h": 0.06, "funding_rate": 0.01, "funding_zscore": 0.2, "liquidation_long_usd": 120_000, "liquidation_short_usd": 90_000, "perp_volume": 12_000_000, "spot_volume": 10_000_000, "freshness_status": "fresh"},
        ],
        "candidates": [
            {"symbol": "TESTFADE", "coin_id": "test-fade", "event_name": "TESTFADE listing blowoff", "source_class": "official_exchange", "source_pack": "listing_liquidity_pack", "impact_path_type": "listing_liquidity_event", "evidence_quality_score": 92, "accepted_evidence_count": 1, "market_snapshot": {"return_unit": "fraction", "return_4h": 0.21, "return_24h": 0.42, "volume_zscore_24h": 4.8, "volume_to_market_cap": 0.45, "liquidity_usd": 3_500_000, "spread_bps": 42, "event_age_hours": 3}},
            {"symbol": "TESTPERP", "coin_id": "test-perp", "event_name": "TESTPERP perp breakout", "source_class": "official_exchange", "source_pack": "perp_listing_squeeze_pack", "impact_path_type": "listing_liquidity_event", "evidence_quality_score": 92, "accepted_evidence_count": 1, "market_snapshot": {"return_unit": "fraction", "return_4h": 0.11, "return_24h": 0.18, "volume_zscore_24h": 3.4, "relative_return_vs_btc": 10.0, "liquidity_usd": 18_000_000, "spread_bps": 18, "event_age_hours": -1}},
        ],
    }


def _clear_namespace(namespace_dir: Path) -> None:
    if namespace_dir.exists():
        shutil.rmtree(namespace_dir)


def _candidate_family_key(row: Mapping[str, Any]) -> str:
    asset = _text(row.get("coin_id") or row.get("validated_coin_id") or row.get("symbol") or row.get("validated_symbol") or "unknown").casefold()
    family = _impact_family(row)
    return "|".join(part for part in (asset, family) if part)


def _impact_family(row: Mapping[str, Any]) -> str:
    text = " ".join(str(row.get(key) or "") for key in ("source_pack", "impact_path_type", "event_type", "row_type")).casefold()
    if "unlock" in text:
        return "unlock_supply"
    if str(row.get("row_type") or "") == "event_market_anomaly":
        return "listing_liquidity"
    if (
        "perp" in text
        or "listing" in text
        or "exchange" in text
        or "trading_pair" in text
        or "derivatives" in text
        or "fade_short_review" in text
    ):
        return "listing_liquidity"
    if "sector" in text or str(row.get("symbol") or "").upper() == "SECTOR":
        return "sector_diagnostic"
    return "market_anomaly"


def _select_primary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return sorted(rows, key=lambda row: _opportunity_rank(str(row.get("opportunity_type") or "")), reverse=True)[0]


def _policy_opportunity_type(
    reaction: event_market_reaction.MarketReactionResult,
    rows: list[dict[str, Any]],
    origins: Iterable[str],
    *,
    official_row: Mapping[str, Any] | None,
) -> str:
    if any(str(row.get("symbol") or "").upper() == "SECTOR" for row in rows):
        return event_market_reaction.EventOpportunityType.DIAGNOSTIC.value
    if official_row and bool(official_row.get("major_pair_simple_announcement")):
        return event_market_reaction.EventOpportunityType.UNCONFIRMED_RESEARCH.value
    if _fade_requirements_met(event_market_reaction.EventOpportunityType.FADE_SHORT_REVIEW.value, rows):
        return event_market_reaction.EventOpportunityType.FADE_SHORT_REVIEW.value
    if _risk_requirements_met(event_market_reaction.EventOpportunityType.RISK_ONLY.value, rows):
        return event_market_reaction.EventOpportunityType.RISK_ONLY.value
    origin_set = set(origins)
    has_official = official_row is not None and str(official_row.get("source_class")) == "official_exchange"
    market_confirmed = reaction.market_state in {"confirmed_breakout", "stealth_accumulation"}
    if has_official and market_confirmed:
        return event_market_reaction.EventOpportunityType.CONFIRMED_LONG_RESEARCH.value
    if has_official and reaction.market_state == "no_reaction":
        return event_market_reaction.EventOpportunityType.EARLY_LONG_RESEARCH.value
    if origin_set == {"market_anomaly"}:
        return event_market_reaction.EventOpportunityType.UNCONFIRMED_RESEARCH.value
    return reaction.opportunity_type


def _level_route_state(opportunity: str) -> tuple[str, str, str]:
    if opportunity == event_market_reaction.EventOpportunityType.CONFIRMED_LONG_RESEARCH.value:
        return "exploratory", event_alpha_router.EventAlphaRoute.LOCAL_REPORT.value, event_watchlist.EventWatchlistState.RADAR.value
    if opportunity == event_market_reaction.EventOpportunityType.EARLY_LONG_RESEARCH.value:
        return "exploratory", event_alpha_router.EventAlphaRoute.LOCAL_REPORT.value, event_watchlist.EventWatchlistState.RADAR.value
    if opportunity == event_market_reaction.EventOpportunityType.FADE_SHORT_REVIEW.value:
        return "exploratory", event_alpha_router.EventAlphaRoute.LOCAL_REPORT.value, event_watchlist.EventWatchlistState.RADAR.value
    if opportunity == event_market_reaction.EventOpportunityType.RISK_ONLY.value:
        return "local_only", event_alpha_router.EventAlphaRoute.STORE_ONLY.value, event_watchlist.EventWatchlistState.RAW_EVIDENCE.value
    if opportunity == event_market_reaction.EventOpportunityType.DIAGNOSTIC.value:
        return "local_only", event_alpha_router.EventAlphaRoute.STORE_ONLY.value, event_watchlist.EventWatchlistState.RAW_EVIDENCE.value
    return "local_only", event_alpha_router.EventAlphaRoute.STORE_ONLY.value, event_watchlist.EventWatchlistState.RAW_EVIDENCE.value


def _opportunity_rank(opportunity: str) -> int:
    return {
        event_market_reaction.EventOpportunityType.FADE_SHORT_REVIEW.value: 6,
        event_market_reaction.EventOpportunityType.CONFIRMED_LONG_RESEARCH.value: 5,
        event_market_reaction.EventOpportunityType.EARLY_LONG_RESEARCH.value: 4,
        event_market_reaction.EventOpportunityType.RISK_ONLY.value: 3,
        event_market_reaction.EventOpportunityType.UNCONFIRMED_RESEARCH.value: 2,
        event_market_reaction.EventOpportunityType.DIAGNOSTIC.value: 1,
    }.get(opportunity, 0)


def _candidate_sort_key(row: Mapping[str, Any]) -> tuple[int, float, str]:
    return (_opportunity_rank(str(row.get("opportunity_type") or "")), float(row.get("score") or 0), str(row.get("symbol") or ""))


def _score_for(
    opportunity: str,
    reaction: event_market_reaction.MarketReactionResult,
    rows: list[dict[str, Any]],
    source_strength: str,
) -> float:
    base = {
        event_market_reaction.EventOpportunityType.CONFIRMED_LONG_RESEARCH.value: 78.0,
        event_market_reaction.EventOpportunityType.EARLY_LONG_RESEARCH.value: 66.0,
        event_market_reaction.EventOpportunityType.FADE_SHORT_REVIEW.value: 74.0,
        event_market_reaction.EventOpportunityType.RISK_ONLY.value: 58.0,
        event_market_reaction.EventOpportunityType.UNCONFIRMED_RESEARCH.value: 42.0,
        event_market_reaction.EventOpportunityType.DIAGNOSTIC.value: 10.0,
    }.get(opportunity, 25.0)
    if source_strength == "official_structured":
        base += 4.0
    if reaction.market_requirements_met:
        base += 4.0
    if any(row.get("accepted_evidence_count") for row in rows):
        base += 2.0
    return min(95.0, base)


def _source_requirements_met(opportunity: str, rows: list[dict[str, Any]], source_strength: str) -> bool:
    if opportunity in {
        event_market_reaction.EventOpportunityType.EARLY_LONG_RESEARCH.value,
        event_market_reaction.EventOpportunityType.CONFIRMED_LONG_RESEARCH.value,
        event_market_reaction.EventOpportunityType.RISK_ONLY.value,
        event_market_reaction.EventOpportunityType.FADE_SHORT_REVIEW.value,
    }:
        return source_strength == "official_structured" or any(row.get("accepted_evidence_count") for row in rows)
    return False


def _market_requirements_met(opportunity: str, reaction: event_market_reaction.MarketReactionResult) -> bool:
    if opportunity == event_market_reaction.EventOpportunityType.CONFIRMED_LONG_RESEARCH.value:
        return reaction.market_state in {"confirmed_breakout", "stealth_accumulation"} or reaction.market_requirements_met
    if opportunity == event_market_reaction.EventOpportunityType.FADE_SHORT_REVIEW.value:
        return reaction.market_state in {"post_event_fade_setup", "blowoff_crowded", "late_momentum"}
    return False


def _fade_requirements_met(opportunity: str, rows: list[dict[str, Any]]) -> bool:
    return any(bool(row.get("fade_requirements_met")) for row in rows) or any(
        str(row.get("opportunity_type")) == event_market_reaction.EventOpportunityType.FADE_SHORT_REVIEW.value
        for row in rows
    )


def _risk_requirements_met(opportunity: str, rows: list[dict[str, Any]]) -> bool:
    return any(str(row.get("opportunity_type")) == event_market_reaction.EventOpportunityType.RISK_ONLY.value for row in rows)


def _best_market_snapshot(rows: list[dict[str, Any]]) -> dict[str, Any]:
    snapshots: list[dict[str, Any]] = []
    for row in rows:
        for key in ("market_state_snapshot", "market_snapshot", "latest_market_snapshot"):
            value = row.get(key)
            if isinstance(value, Mapping):
                snapshots.append(dict(value))
    if not snapshots:
        return {}
    return sorted(snapshots, key=lambda snap: len([v for v in snap.values() if v not in (None, "", [], {})]), reverse=True)[0]


def _best_row(rows: list[dict[str, Any]], predicate: Any) -> dict[str, Any] | None:
    for row in rows:
        if predicate(row):
            return row
    return None


def _best_derivatives_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    classified = [
        row for row in rows
        if isinstance(row.get("derivatives_state_snapshot"), Mapping)
        and (
            row.get("crowding_class")
            or row.get("fade_readiness")
            or row.get("crowding_exhaustion_evidence")
            or row.get("derivatives_warning_codes")
            or row.get("what_confirms_fade_review")
        )
    ]
    if classified:
        return sorted(
            classified,
            key=lambda row: _opportunity_rank(str(row.get("opportunity_type") or "")),
            reverse=True,
        )[0]
    return _best_row(rows, lambda row: bool(row.get("derivatives_state_snapshot")))


def _derivatives_metadata(row: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(row, Mapping):
        return {}
    warnings = list(dict.fromkeys((*_list_values(row.get("derivatives_warning_codes")), *_list_values(row.get("warnings")))))
    return {
        "crowding_class": row.get("crowding_class"),
        "fade_readiness": row.get("fade_readiness"),
        "crowding_exhaustion_evidence": _list_values(row.get("crowding_exhaustion_evidence")),
        "what_confirms_fade_review": _list_values(row.get("what_confirms_fade_review")),
        "what_invalidates_fade_review": _list_values(row.get("what_invalidates_fade_review")),
        "derivatives_warning_codes": warnings,
    }


def _integrated_market_confirmation(
    opportunity: str,
    reaction: event_market_reaction.MarketReactionResult,
) -> dict[str, Any]:
    market_state = str(reaction.market_state or "")
    if opportunity == event_market_reaction.EventOpportunityType.CONFIRMED_LONG_RESEARCH.value:
        return {
            "level": market_state or "confirmed",
            "score": 80.0 if reaction.market_requirements_met else 0.0,
            "reaction": market_state or "confirmed_breakout",
            "source": "integrated_market_state",
            "freshness": reaction.market_state_snapshot.freshness_status or "fresh",
        }
    if opportunity == event_market_reaction.EventOpportunityType.FADE_SHORT_REVIEW.value:
        return {
            "level": market_state or "fade_review_market_state",
            "score": 75.0 if reaction.fade_requirements_met else 0.0,
            "reaction": market_state or "post_event_fade_setup",
            "source": "integrated_market_state",
            "freshness": reaction.market_state_snapshot.freshness_status or "fresh",
        }
    if opportunity == event_market_reaction.EventOpportunityType.RISK_ONLY.value and market_state:
        return {
            "level": market_state,
            "score": 55.0,
            "reaction": market_state,
            "source": "integrated_market_state",
            "freshness": reaction.market_state_snapshot.freshness_status or "fresh",
        }
    return {
        "level": None,
        "score": None,
        "reaction": market_state or None,
        "source": "integrated_market_state" if market_state else None,
        "freshness": reaction.market_state_snapshot.freshness_status if reaction.market_state_snapshot else None,
    }


def _list_values(value: Any) -> list[str]:
    if value in (None, "", [], (), {}):
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(";") if item.strip()]
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, Mapping)):
        return [str(item) for item in value if str(item or "")]
    return [str(value)]


def _best_source_strength(rows: list[dict[str, Any]]) -> str:
    values = [str(row.get("source_strength") or "") for row in rows]
    if "official_structured" in values:
        return "official_structured"
    if "strong" in values:
        return "strong"
    if "tagged_context" in values:
        return "tagged_context"
    return "weak"


def _best_source_pack(rows: list[dict[str, Any]], source_packs: Iterable[str]) -> str:
    packs = list(source_packs)
    priority = (
        "perp_listing_squeeze_pack",
        "official_exchange_listing_pack",
        "listing_liquidity_pack",
        "unlock_supply_pack",
        "official_exchange_risk_pack",
        "market_anomaly_pack",
    )
    for wanted in priority:
        if wanted in packs:
            return wanted
    return packs[0] if packs else "integrated_radar_pack"


def _best_impact_path(rows: list[dict[str, Any]], source_pack: str) -> str:
    for row in rows:
        value = _text(row.get("impact_path_type") or row.get("playbook_type"))
        if value:
            return value
    if "unlock" in source_pack:
        return "unlock_supply_event"
    if "listing" in source_pack or "exchange" in source_pack or "perp" in source_pack:
        return "listing_liquidity_event"
    return "market_anomaly_unknown"


def _evidence_score(source_strength: str, accepted: int) -> float:
    if source_strength == "official_structured":
        return 92.0
    if accepted:
        return 75.0
    return 45.0


def _negative_candidate(rows: list[dict[str, Any]], impact_path: str, source_pack: str) -> bool:
    text = f"{impact_path} {source_pack}".casefold()
    return "unlock" in text or "delist" in text or any(bool(row.get("negative_catalyst")) for row in rows)


def _policy_warnings(
    opportunity: str,
    rows: list[dict[str, Any]],
    reaction: event_market_reaction.MarketReactionResult,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if any(row.get("major_pair_simple_announcement") for row in rows):
        warnings.append("major_pair_simple_announcement_capped")
    if opportunity == event_market_reaction.EventOpportunityType.CONFIRMED_LONG_RESEARCH.value and not reaction.market_requirements_met:
        warnings.append("confirmed_long_requires_market_confirmation")
    return tuple(warnings)


def _lane_why_not(opportunity: str, rows: list[dict[str, Any]]) -> tuple[str, ...]:
    out: list[str] = []
    if any(row.get("major_pair_simple_announcement") for row in rows):
        out.append("major_pair_simple_announcement_not_alpha")
    if opportunity == event_market_reaction.EventOpportunityType.UNCONFIRMED_RESEARCH.value:
        out.append("strict_lane_requirements_not_met")
    if opportunity == event_market_reaction.EventOpportunityType.DIAGNOSTIC.value:
        out.append("diagnostic_context_hidden_from_default_operator_sections")
    return tuple(out)


def _why_now_for(
    opportunity: str,
    reaction: event_market_reaction.MarketReactionResult,
    rows: list[dict[str, Any]],
) -> str:
    if opportunity == event_market_reaction.EventOpportunityType.CONFIRMED_LONG_RESEARCH.value:
        return "official/structured source plus fresh market confirmation"
    if opportunity == event_market_reaction.EventOpportunityType.EARLY_LONG_RESEARCH.value:
        return "fresh official/structured catalyst with little market reaction yet"
    if opportunity == event_market_reaction.EventOpportunityType.FADE_SHORT_REVIEW.value:
        return "completed move with derivatives crowding/exhaustion evidence"
    if opportunity == event_market_reaction.EventOpportunityType.RISK_ONLY.value:
        return "credible downside/risk catalyst for research monitoring"
    if any(row.get("major_pair_simple_announcement") for row in rows):
        return "simple major-pair announcement capped as unconfirmed research"
    return reaction.why_now


def _candidate_role_for(opportunity: str) -> str:
    if opportunity == event_market_reaction.EventOpportunityType.DIAGNOSTIC.value:
        return "source_noise_control"
    return "direct_beneficiary"


def _canonical_incident_name(rows: list[dict[str, Any]], symbol: str, opportunity: str) -> str:
    title = _best_text(rows, "event_name", "title")
    return title or f"{symbol} {opportunity}"


def _compact_event(row: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    keys = (
        "row_type",
        "event_type",
        "exchange",
        "provider",
        "title",
        "event_name",
        "published_at",
        "effective_time",
        "event_start_time",
        "source_url",
        "reason_codes",
    )
    return {key: row.get(key) for key in keys if row.get(key) not in (None, "", [], {})}


def _supporting_quotes(rows: list[dict[str, Any]]) -> list[str]:
    quotes = []
    for row in rows:
        for key in ("title", "event_name", "description_summary"):
            value = _text(row.get(key))
            if value:
                quotes.append(value)
                break
    return list(dict.fromkeys(quotes))


def _candidate_summary_lines(row: Mapping[str, Any], *, compact: bool = False) -> list[str]:
    line = (
        f"- {row.get('symbol')}/{row.get('coin_id')} "
        f"{row.get('opportunity_type')} score={row.get('score')} "
        f"market={row.get('market_state_class')} source={row.get('source_pack')}"
    )
    lines = [line]
    if not compact:
        lines.append(f"  - Why now: {row.get('why_now') or 'unknown'}")
        if row.get("why_not_alertable"):
            lines.append("  - Why not alertable: " + "; ".join(str(item) for item in row.get("why_not_alertable") or ()))
    return lines


def _append_filtered(
    lines: list[str],
    rows: list[dict[str, Any]],
    predicate: Any,
    *,
    include_diagnostics: bool = False,
) -> None:
    selected = [
        row for row in rows
        if predicate(row)
        and (
            include_diagnostics
            or row.get("opportunity_type") != event_market_reaction.EventOpportunityType.DIAGNOSTIC.value
        )
    ]
    if not selected:
        lines.append("- None.")
        return
    for row in selected[:10]:
        lines.extend(_candidate_summary_lines(row, compact=True))


def _source_coverage_lines(rows: list[dict[str, Any]]) -> list[str]:
    counts = Counter(pack for row in rows for pack in (row.get("source_packs") or [row.get("source_pack") or "unknown"]))
    lines = [f"- {pack}: {count}" for pack, count in counts.most_common()]
    lines.append("- Most useful next source is lane-critical: official exchange, derivatives/OI/funding, structured unlock/calendar, then broader news context.")
    return lines


def _input_manifest_lines(
    manifest: Iterable[Mapping[str, Any]],
    *,
    compact: bool = False,
) -> list[str]:
    rows = [dict(item) for item in manifest if isinstance(item, Mapping)]
    if not rows:
        return ["- Input manifest: not available."]
    lines: list[str] = []
    for item in rows:
        name = item.get("sidecar_name") or "unknown"
        mode = item.get("mode") or "unknown"
        count = int((item.get("row_counts") or {}).get("rows") or 0)
        freshness = item.get("freshness_status") or "unknown"
        warnings = item.get("warnings") or ()
        line = f"- {name}: {mode}, rows={count}, freshness={freshness}"
        if warnings and not compact:
            line += " warnings=" + "; ".join(str(warning) for warning in warnings[:3])
        lines.append(line)
    return lines


def _manifest_rows(
    manifest: Iterable[Mapping[str, Any]],
    *,
    context: event_alpha_artifacts.EventAlphaArtifactContext | None = None,
) -> list[dict[str, Any]]:
    rows = [dict(item) for item in manifest if isinstance(item, Mapping)]
    if rows or context is None:
        return rows
    path = context.namespace_dir / INPUT_MANIFEST_FILENAME
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    sidecars = payload.get("sidecars") if isinstance(payload, Mapping) else None
    if not isinstance(sidecars, Iterable) or isinstance(sidecars, (str, bytes, Mapping)):
        return []
    return [dict(item) for item in sidecars if isinstance(item, Mapping)]


def _by_horizon(value: Any, horizon: Any) -> Any:
    if isinstance(value, Mapping):
        return value.get(str(horizon or "24h")) or value.get("24h")
    return value


def _pct(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "n/a"
    return f"{number * 100:+.2f}%"


def _group_by(rows: Iterable[Mapping[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get(key) or "unknown"), []).append(dict(row))
    return grouped


def _outcome_truth(row: Mapping[str, Any]) -> str:
    label = str(row.get("outcome_label") or "")
    if label in {"useful", "early_good", "continuation_good", "fade_review_good", "risk_validated", "watch"}:
        return "validated"
    if label in {"junk", "remained_noise"}:
        return "invalidated/noise"
    return "inconclusive"


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().casefold() in {"1", "true", "yes", "y", "on"}


def _review_candidates(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    excluded = {event_market_reaction.EventOpportunityType.DIAGNOSTIC.value}
    return sorted(
        [dict(row) for row in rows if str(row.get("opportunity_type") or "") not in excluded],
        key=_candidate_sort_key,
        reverse=True,
    )


def _integrated_warnings(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    warnings: list[str] = []
    for row in rows:
        if not row.get("opportunity_type"):
            warnings.append(f"{row.get('candidate_id')}:missing_opportunity_type")
        if row.get("opportunity_type") == event_market_reaction.EventOpportunityType.CONFIRMED_LONG_RESEARCH.value:
            if not (row.get("source_requirements_met") and row.get("market_requirements_met")):
                warnings.append(f"{row.get('candidate_id')}:confirmed_long_requirements_missing")
    return warnings


def _normalize_input_mode(value: str | None) -> str:
    text = str(value or INPUT_MODE_AUTO).strip().casefold().replace("-", "_")
    return text if text in INPUT_MODES else INPUT_MODE_AUTO


def _manifest_item(
    *,
    sidecar_name: str,
    mode: str,
    namespace_dir: Path,
    rows: Iterable[Mapping[str, Any]],
    configured: bool,
    sidecar_research_observed_at: datetime,
    wall_started_at: datetime,
    wall_finished_at: datetime,
    warnings: Iterable[str] = (),
    errors: Iterable[str] = (),
) -> dict[str, Any]:
    materialized = [dict(row) for row in rows if isinstance(row, Mapping)]
    artifact_paths = _sidecar_artifact_paths(namespace_dir, sidecar_name)
    missing = [event_artifact_paths.artifact_display_path(path) for path in artifact_paths if not path.exists()]
    freshness = "fresh" if materialized else "missing"
    item_warnings = [str(warning) for warning in warnings if str(warning)]
    if missing and not materialized:
        item_warnings.append("missing_sidecar_artifact")
    return {
        "sidecar_name": sidecar_name,
        "mode": mode,
        "artifact_paths": [event_artifact_paths.artifact_display_path(path) for path in artifact_paths],
        "artifact_relpaths": [event_artifact_paths.artifact_relpath(path) for path in artifact_paths],
        "row_counts": {"rows": len(materialized)},
        "provider_status": "configured" if configured else "not_configured",
        "configured": bool(configured),
        "freshness_status": freshness,
        "warnings": tuple(dict.fromkeys(item_warnings)),
        "errors": tuple(str(error) for error in errors if str(error)),
        "sidecar_research_observed_at": sidecar_research_observed_at,
        "sidecar_wall_started_at": wall_started_at,
        "sidecar_wall_finished_at": wall_finished_at,
        "started_at": wall_started_at,
        "finished_at": wall_finished_at,
        "wall_started_at": wall_started_at,
        "wall_finished_at": wall_finished_at,
        "research_observed_at": sidecar_research_observed_at,
    }


def _input_manifest_document(
    manifest: Iterable[Mapping[str, Any]],
    *,
    run_id: str,
    profile: str,
    artifact_namespace: str,
    run_mode: str,
    input_mode: str,
    wall_started_at: datetime,
    research_observed_at: datetime,
) -> dict[str, Any]:
    rows = [dict(item) for item in manifest if isinstance(item, Mapping)]
    return {
        "schema_version": 1,
        "row_type": "event_integrated_radar_input_manifest",
        "run_id": run_id,
        "profile": profile,
        "artifact_namespace": artifact_namespace,
        "run_mode": run_mode,
        "input_mode": input_mode,
        "sidecars": rows,
        "row_counts": {str(item.get("sidecar_name") or "unknown"): int((item.get("row_counts") or {}).get("rows") or 0) for item in rows},
        "warnings": [warning for item in rows for warning in item.get("warnings", ())],
        "errors": [error for item in rows for error in item.get("errors", ())],
        "started_at": wall_started_at,
        "finished_at": datetime.now(timezone.utc),
        "wall_started_at": wall_started_at,
        "wall_finished_at": datetime.now(timezone.utc),
        "research_observed_at": research_observed_at,
        "generated_at": datetime.now(timezone.utc),
    }


def _sidecar_artifact_paths(namespace_dir: Path, sidecar_name: str) -> tuple[Path, ...]:
    mapping = {
        "market_anomaly": ("event_market_state_snapshots.jsonl", "event_market_anomalies.jsonl"),
        "official_exchange": ("event_official_exchange_events.jsonl", "event_official_listing_candidates.jsonl"),
        "scheduled_catalyst": ("event_scheduled_catalysts.jsonl",),
        "unlock": ("event_unlock_candidates.jsonl",),
        "derivatives": ("event_derivatives_state.jsonl", "event_derivatives_crowding_candidates.jsonl", "event_fade_short_review_candidates.jsonl"),
    }
    return tuple(namespace_dir / name for name in mapping.get(sidecar_name, ()))


def _sidecar_count_summary(sidecars: Mapping[str, Iterable[Mapping[str, Any]]]) -> dict[str, int]:
    market_rows = list(sidecars.get("market_anomaly", ()))
    official_rows = list(sidecars.get("official_exchange", ()))
    derivatives_rows = list(sidecars.get("derivatives", ()))
    return {
        "market_anomalies": len(market_rows),
        "market_state_snapshots": len(market_rows),
        "official_exchange_events": sum(
            1 for row in official_rows
            if str(row.get("row_type") or "") in {"official_exchange_event", "official_exchange_event_candidate"}
            or isinstance(row.get("official_exchange_event"), Mapping)
            or row.get("official_exchange_event_id")
            or row.get("source_event_id")
            or row.get("event_id")
        ),
        "official_listing_candidates": sum(1 for row in official_rows if str(row.get("row_type") or "") in {"official_listing_candidate", "official_exchange_event_candidate"}),
        "scheduled_catalysts": len(tuple(sidecars.get("scheduled_catalyst", ()))),
        "unlock_candidates": len(tuple(sidecars.get("unlock", ()))),
        "derivatives_state_rows": sum(
            1 for row in derivatives_rows
            if str(row.get("row_type") or "") == "derivatives_state_snapshot"
            or isinstance(row.get("derivatives_state_snapshot"), Mapping)
        ),
        "derivatives_crowding_candidates": len(derivatives_rows),
        "fade_review_candidates": sum(1 for row in derivatives_rows if str(row.get("opportunity_type") or "") == event_market_reaction.EventOpportunityType.FADE_SHORT_REVIEW.value),
    }


def _first_value(rows: list[Mapping[str, Any]], *keys: str) -> Any:
    for row in rows:
        for key in keys:
            value = row.get(key)
            if value not in (None, "", [], {}):
                return value
    return None


def _best_text(rows: list[Mapping[str, Any]], *keys: str) -> str | None:
    value = _first_value(rows, *keys)
    text = _text(value)
    return text or None


def _merged_list(rows: list[Mapping[str, Any]], key: str) -> tuple[str, ...]:
    values: list[str] = []
    for row in rows:
        raw = row.get(key)
        if isinstance(raw, (list, tuple, set)):
            values.extend(str(item) for item in raw if str(item))
        elif raw not in (None, ""):
            values.append(str(raw))
    return tuple(dict.fromkeys(values))


def _format_counts(values: Mapping[str, int] | Counter[Any]) -> str:
    items = [(str(key), int(value)) for key, value in dict(values).items() if int(value)]
    if not items:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(items))


def _list_label(values: Any, *, limit: int = 3) -> str:
    if values in (None, "", [], (), {}):
        return "none"
    if isinstance(values, str):
        return values
    if isinstance(values, Mapping):
        return ", ".join(f"{key}={value}" for key, value in list(values.items())[:limit]) or "none"
    if isinstance(values, Iterable):
        items = [str(item) for item in values if str(item)]
        if not items:
            return "none"
        suffix = f"; +{len(items) - limit} more" if len(items) > limit else ""
        return "; ".join(items[:limit]) + suffix
    return str(values)


def _artifact_has_absolute_operator_path(path: str | Path) -> bool:
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return event_artifact_paths.has_operator_absolute_path(text)


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(_json_ready(dict(row)), sort_keys=True, separators=(",", ":")) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, Mapping):
                rows.append(dict(value))
    return rows


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_ready(dict(payload)), sort_keys=True), encoding="utf-8")


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return value


def _parse_time(value: datetime | str | None) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
