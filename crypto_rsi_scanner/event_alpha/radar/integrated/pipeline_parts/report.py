"""Report helpers for integrated radar."""

from __future__ import annotations

from .runtime import *
from ...decision_model_surfaces import (
    PREVIEW_LANE_ORDER,
    PREVIEW_LANE_TITLES,
    decision_model_markdown_lines,
    decision_model_values,
    group_decision_rows,
)

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
        lines.extend(_report_candidate_summary_lines(row))
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
    performance_snapshot: Mapping[str, Any] | None = None,
    source_coverage_path: str | Path | None = None,
    run_id: str | None = None,
    raw_events: int | None = None,
    cumulative_store_rows: int | None = None,
) -> str:
    rows = [dict(row) for row in candidates if isinstance(row, Mapping)]
    deliveries = [dict(row) for row in delivery_rows if isinstance(row, Mapping)]
    outcomes = [dict(row) for row in outcome_rows if isinstance(row, Mapping)]
    manifest_rows = _manifest_rows(input_manifest, context=context)
    materialized_core_rows = [dict(row) for row in core_rows if isinstance(row, Mapping)]
    visible_core = event_core_opportunities.visible_core_opportunities(materialized_core_rows)
    visible_core_rows = [item.primary_row for item in visible_core]
    support_rows = [
        row
        for item in visible_core
        for row in item.supporting_rows
        if row is not item.primary_row and dict(row) != dict(item.primary_row)
    ]
    core_count = len(materialized_core_rows)
    visible_core_count = len(visible_core_rows)
    resolved_run_id = _integrated_run_id(
        run_id,
        deliveries,
        materialized_core_rows,
        rows,
    )
    raw_event_count = (
        int(raw_events)
        if raw_events is not None
        else sum(int((item.get("row_counts") or {}).get("rows") or 0) for item in manifest_rows)
    )
    if raw_events is None and not manifest_rows:
        raw_event_count = len(rows)
    cumulative_core_count = int(cumulative_store_rows) if cumulative_store_rows is not None else core_count
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
        f"run_id: {resolved_run_id or 'unknown'}",
        (
            f"- raw_events={raw_event_count}; candidate_events={len(rows)}; "
            f"research_candidates={len(rows)}; source_alert_snapshots=0"
        ),
        (
            f"- current_generation_core_rows={core_count}; "
            f"current_generation_visible_core_rows={visible_core_count}; "
            f"cumulative_store_rows={cumulative_core_count}"
        ),
        (
            f"- alertable_decisions=0; strict_alerts=0; "
            f"preview_rendered_items={rendered}"
        ),
        "- burn_in_mode=no_send_notification_burn_in; send_guard_status=disabled_by_send_guard; "
        "send_requested=false; send_attempted=false; no_send_rehearsal=true; delivered=false",
        _freshness_scope_line("current_core_market_freshness", materialized_core_rows),
        _freshness_scope_line("current_generation_visible_core_freshness", visible_core_rows),
        _freshness_scope_line("support_row_market_freshness", support_rows),
        _freshness_scope_line("quality_row_market_freshness", rows),
        f"- Source coverage report: {event_artifact_paths.artifact_display_path(source_coverage_path or SOURCE_COVERAGE_FILENAME)}",
        "",
        "### Input Manifest",
    ]
    lines.extend(_input_manifest_lines(manifest_rows, compact=True))
    lines.extend([
        "",
        "### Derivatives/OI/funding status",
    ])
    lines.extend(_coinalyze_status_lines(manifest_rows))
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
    decision_groups = (
        group_decision_rows(rows, include_diagnostics=True)
        if config.EVENT_ALPHA_DECISION_MODEL_V2_PREVIEW_ENABLED
        else {lane: [] for lane in PREVIEW_LANE_ORDER}
    )
    decision_row_count = sum(len(items) for items in decision_groups.values())
    if decision_row_count:
        lines.extend([
            "",
            "## Crypto Radar v2 Preview Lanes",
            "- These research lanes are presentation-only and do not change legacy opportunity types or Telegram routing.",
        ])
        for lane in PREVIEW_LANE_ORDER:
            lines.append(f"- {PREVIEW_LANE_TITLES[lane]}: {len(decision_groups[lane])}")
        for lane in PREVIEW_LANE_ORDER:
            if lane == "decision_diagnostic" and not config.EVENT_ALPHA_DECISION_MODEL_V2_SHOW_DIAGNOSTICS:
                continue
            lines.extend(["", f"## {PREVIEW_LANE_TITLES[lane]}"])
            lane_rows = decision_groups[lane]
            if not lane_rows:
                lines.append("- None.")
            for row in lane_rows[:10]:
                lines.extend(_report_candidate_summary_lines(row, compact=False))
    _append_daily_brief_sections(
        lines,
        rows,
        outcomes=outcomes,
        performance_snapshot=performance_snapshot,
    )
    return "\n".join(lines).rstrip() + "\n"


def _append_daily_brief_sections(
    lines: list[str],
    rows: list[dict[str, Any]],
    *,
    outcomes: list[dict[str, Any]],
    performance_snapshot: Mapping[str, Any] | None,
) -> None:
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
            lines.extend(_report_candidate_summary_lines(row, compact=True))
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
    lines.extend(["", "## DEX / On-Chain Liquidity"])
    _append_filtered(lines, rows, lambda row: row.get("dex_liquidity_snapshot"))
    lines.extend(["", "## Protocol Fundamentals"])
    _append_filtered(lines, rows, lambda row: row.get("protocol_metrics_snapshot"))
    lines.extend(["", "## Source Coverage"])
    lines.extend(_source_coverage_lines(rows))
    lines.extend(["", "## Radar Learning Snapshot"])
    _append_radar_learning_snapshot(lines, performance_snapshot)
    lines.extend(["", "## Outcome Tracker Status"])
    _append_outcome_tracker_status(lines, outcomes)
    lines.extend(["", "## Diagnostics Appendix"])
    diagnostics = [row for row in rows if row.get("opportunity_type") == event_market_reaction.EventOpportunityType.DIAGNOSTIC.value]
    if not diagnostics:
        lines.append("- None.")
    for row in diagnostics[:10]:
        lines.extend(_report_candidate_summary_lines(row, compact=True))

def _report_candidate_summary_lines(row: Mapping[str, Any], *, compact: bool = False) -> list[str]:
    lines = list(_candidate_summary_lines(row, compact=compact))
    decision = decision_model_values(row)
    if not decision:
        return lines
    score_line = (
        "  - Crypto Radar v2: "
        f"route={decision.get('radar_route') or 'diagnostic'} "
        f"actionability={decision.get('actionability_score') if decision.get('actionability_score') is not None else 'n/a'} "
        f"evidence={decision.get('evidence_confidence_score') if decision.get('evidence_confidence_score') is not None else 'n/a'} "
        f"risk={decision.get('risk_score') if decision.get('risk_score') is not None else 'n/a'}"
    )
    lines.append(score_line)
    if not compact:
        lines.extend(f"  {item}" for item in decision_model_markdown_lines(decision))
    return lines

def _append_radar_learning_snapshot(lines: list[str], performance_snapshot: Mapping[str, Any] | None) -> None:
    if not isinstance(performance_snapshot, Mapping):
        lines.append("- Dashboard not available yet.")
        return
    maturation = performance_snapshot.get("maturation_counts") if isinstance(performance_snapshot.get("maturation_counts"), Mapping) else {}
    views = performance_snapshot.get("performance_views") if isinstance(performance_snapshot.get("performance_views"), Mapping) else {}
    early = views.get("early_long_conversion_rate") if isinstance(views, Mapping) else {}
    fade = views.get("fade_review_exhaustion_rate") if isinstance(views, Mapping) else {}
    lines.append(f"- Dashboard: {RADAR_PERFORMANCE_DASHBOARD_FILENAME}")
    lines.append(f"- Evaluated rows: {_int(performance_snapshot.get('rows_evaluated'))}")
    lines.append(f"- Maturation: {_format_counts(Counter({str(k): _int(v) for k, v in dict(maturation).items()}))}")
    if isinstance(early, Mapping):
        lines.append(f"- Early-long conversion rate: {_rate_text(early.get('rate'))}")
    if isinstance(fade, Mapping):
        lines.append(f"- Fade-review exhaustion rate: {_rate_text(fade.get('rate'))}")
    lines.append("- Recommendations only; no automatic threshold changes were applied.")

def _append_outcome_tracker_status(lines: list[str], outcomes: list[dict[str, Any]]) -> None:
    if not outcomes:
        lines.append("- No integrated radar outcomes filled yet.")
        return
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

def build_integrated_notification_delivery_rows(
    candidates: Iterable[Mapping[str, Any]],
    *,
    core_rows: Iterable[Mapping[str, Any]] = (),
    context: event_alpha_artifacts.EventAlphaArtifactContext | None = None,
    run_id: str | None = None,
    generated_at: datetime | str | None = None,
    send_guard_enabled: bool = False,
    preview_path: str | Path | None = None,
    decision_preview_enabled: bool | None = None,
) -> tuple[dict[str, Any], ...]:
    rows = [dict(row) for row in candidates if isinstance(row, Mapping)]
    core_by_id = {str(row.get("core_opportunity_id") or ""): dict(row) for row in core_rows if isinstance(row, Mapping)}
    observed = _as_utc(_parse_time(generated_at) or datetime.now(timezone.utc)).isoformat()
    zero_candidate_preview = not rows
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
            preview_path=preview_path,
            zero_candidate_preview=zero_candidate_preview,
        ))
    decision_groups = group_decision_rows(rows, include_diagnostics=True)
    v2_preview_enabled = (
        bool(config.EVENT_ALPHA_DECISION_MODEL_V2_PREVIEW_ENABLED)
        if decision_preview_enabled is None
        else bool(decision_preview_enabled)
    )
    if v2_preview_enabled and sum(len(items) for items in decision_groups.values()):
        for lane in PREVIEW_LANE_ORDER:
            if lane == "decision_diagnostic" and not config.EVENT_ALPHA_DECISION_MODEL_V2_SHOW_DIAGNOSTICS:
                continue
            lane_rows = decision_groups[lane]
            title = PREVIEW_LANE_TITLES[lane]
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
                preview_path=preview_path,
                zero_candidate_preview=zero_candidate_preview,
            ))
    diagnostics = [row for row in rows if row.get("opportunity_type") == event_market_reaction.EventOpportunityType.DIAGNOSTIC.value]
    if v2_preview_enabled:
        diagnostics.extend(
            row for row in decision_groups["decision_diagnostic"]
            if row not in diagnostics
        )
    health_message = _integrated_lane_message(
        (),
        lane_title="Source / Provider Health",
        context=context,
        lane="source_provider_health",
        extra_lines=(
            f"Lane-critical source priority: {_canonical_source_priority_summary()}.",
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
        preview_path=preview_path,
        zero_candidate_preview=zero_candidate_preview,
    ))
    return tuple(out)

def format_integrated_notification_preview_from_deliveries(
    delivery_rows: Iterable[Mapping[str, Any]],
    *,
    candidates: Iterable[Mapping[str, Any]] = (),
    core_rows: Iterable[Mapping[str, Any]] = (),
    context: event_alpha_artifacts.EventAlphaArtifactContext | None = None,
    run_id: str | None = None,
    raw_events: int | None = None,
    cumulative_store_rows: int | None = None,
) -> str:
    deliveries = [dict(row) for row in delivery_rows if isinstance(row, Mapping)]
    rows = [dict(row) for row in candidates if isinstance(row, Mapping)]
    materialized_core_rows = [dict(row) for row in core_rows if isinstance(row, Mapping)]
    visible_core_count = len(event_core_opportunities.visible_core_opportunities(materialized_core_rows))
    resolved_run_id = _integrated_run_id(run_id, deliveries, materialized_core_rows, rows)
    raw_event_count = int(raw_events) if raw_events is not None else len(rows)
    cumulative_core_count = (
        int(cumulative_store_rows)
        if cumulative_store_rows is not None
        else len(materialized_core_rows)
    )
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
        f"run_id: {resolved_run_id or 'unknown'}",
        "burn_in_mode: no_send_notification_burn_in",
        "send_guard_status: disabled_by_send_guard",
        "send_requested: false",
        "send_attempted: false",
        "no_send_rehearsal: true",
        "delivered: false",
        "Send guard: disabled (no-send rehearsal)",
        "No-send rehearsal: would send, but send guard is disabled.",
        "This is expected in rehearsal mode. No Telegram delivery attempted.",
        "",
        "Summary:",
        f"Raw events: {raw_event_count} · Candidate events: {len(rows)} · Research candidates: {len(rows)}",
        (
            "Source alert snapshots: 0 · "
            f"Current-generation core rows: {len(materialized_core_rows)} · "
            f"Current-generation visible core rows: {visible_core_count} · "
            f"Cumulative store rows: {cumulative_core_count}"
        ),
        f"Alertable decisions: 0 · Strict alerts: 0 · Preview-rendered items: {rendered}",
        f"- Preview eligible items: {eligible}",
        f"- Preview skipped items: {skipped}",
        f"- Delivery lanes due/sent/blocked: {due}/0/{due}",
        f"- Skip reasons: {_format_counts(skip_reasons) if skip_reasons else 'none'}",
    ]
    if not rows:
        lines.append("- Zero candidate lanes: candidate lanes are not_due / skipped_empty.")
    lines.append("")
    for row in deliveries:
        lines.append(f"## Lane: {row.get('lane_title') or row.get('lane')}")
        lines.append(f"- status: {row.get('status')}")
        if row.get("status_detail"):
            lines.append(f"- status_detail: {row.get('status_detail')}")
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
    lines.append("Canonical counter scopes are explicit; no legacy raw Alerts or raw-source-candidate aliases are rendered.")
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
        preview_path=context.namespace_dir / "event_integrated_radar_notification_preview.md" if context else None,
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
        "Research idea, not a trade instruction.",
        f"Profile: {context.profile if context else 'unknown'}",
        f"Lane: {lane}",
        f"Items: {len(materialized)}",
        "",
    ]
    if not materialized:
        lines.append("- No candidate items in this lane.")
    for index, row in enumerate(materialized, start=1):
        card_path = _row_card_path(row, core_by_id=core_by_id)
        decision_lines = decision_model_markdown_lines(decision_model_values(row))
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
        ])
        if decision_lines:
            lines.append("   Crypto Radar decision:")
            lines.extend(f"   {line}" for line in decision_lines)
        lines.append("")
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
    preview_path: str | Path | None,
    zero_candidate_preview: bool,
) -> dict[str, Any]:
    rendered = [dict(row) for row in rendered_rows if isinstance(row, Mapping)]
    skipped = [dict(row) for row in skipped_rows if isinstance(row, Mapping)]
    would_send = bool(rendered or lane == "source_provider_health")
    status = (
        "would_send_but_guard_disabled"
        if would_send and not send_guard_enabled
        else ("sent" if would_send and send_guard_enabled else "not_due")
    )
    status_detail = "skipped_empty" if not rendered and not skipped and lane != "source_provider_health" else None
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
    preview_label = event_artifact_paths.artifact_display_path(preview_path) if preview_path else None
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
        "status_detail": status_detail,
        "preview_path": preview_label,
        "preview_kind": "integrated_radar",
        "zero_candidate_preview": bool(zero_candidate_preview),
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
    run_id: str | None = None,
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
        f"- run_id: {run_id or 'none'}",
        "",
        "## Lane-Critical Source Priority",
    ]
    lines.extend(
        f"{idx}. {category}"
        for idx, category in enumerate(_canonical_source_priority_labels(), start=1)
    )
    lines.extend(["", "## Observed Source Packs"])
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
    run_id: str | None = None,
    input_manifest: Iterable[Mapping[str, Any]] = (),
    readiness_json_path: str | Path | None = None,
    readiness_md_path: str | Path | None = None,
) -> dict[str, Any]:
    rows = [dict(row) for row in candidates if isinstance(row, Mapping)]
    source_counts = Counter(
        source for row in rows for source in (row.get("source_packs") or [row.get("source_pack") or "unknown"])
    )
    lane_counts = Counter(str(row.get("opportunity_type") or "unknown") for row in rows)
    manifest_rows = [dict(item) for item in input_manifest if isinstance(item, Mapping)]
    manifest_counts = {
        str(item.get("sidecar_name") or "unknown"): int((item.get("row_counts") or {}).get("rows") or 0)
        for item in manifest_rows
    }
    coinalyze = _coinalyze_manifest_summary(input_manifest)
    return {
        "schema_version": 1,
        "row_type": "event_alpha_source_coverage",
        "run_id": str(run_id or "") or None,
        "source": "integrated_radar",
        "candidate_count": len(rows),
        "lane_counts": dict(sorted(lane_counts.items())),
        "source_pack_counts": dict(source_counts.most_common()),
        "coinalyze_artifact_namespace": coinalyze.get("coinalyze_artifact_namespace"),
        "coinalyze_derivatives_state_rows_loaded": coinalyze.get("coinalyze_derivatives_state_rows_loaded", 0),
        "coinalyze_crowding_candidates_loaded": coinalyze.get("coinalyze_crowding_candidates_loaded", 0),
        "coinalyze_fade_review_candidates_loaded": coinalyze.get("coinalyze_fade_review_candidates_loaded", 0),
        "coinalyze_provider_health_status": coinalyze.get("coinalyze_provider_health_status", "not_observed"),
        "coinalyze_freshness_status": coinalyze.get("coinalyze_freshness_status", "missing"),
        "coinalyze_skip_reason": coinalyze.get("coinalyze_skip_reason"),
        "dex_pool_state_rows": manifest_counts.get("dex_pool_state", 0),
        "dex_pool_anomaly_rows": manifest_counts.get("dex_pool_anomaly", 0),
        "protocol_fundamental_rows": manifest_counts.get("protocol_fundamentals", 0),
        "dex_onchain_readiness_status": "fixture_ready"
        if (
            manifest_counts.get("dex_pool_state", 0)
            or manifest_counts.get("dex_pool_anomaly", 0)
            or manifest_counts.get("protocol_fundamentals", 0)
        )
        else "not_loaded",
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
        "lane_critical_priority": list(_canonical_source_priority_slugs()),
        "input_manifest": manifest_rows,
    }

def load_integrated_candidates(namespace_dir: str | Path) -> tuple[dict[str, Any], ...]:
    return tuple(_read_jsonl(Path(namespace_dir) / INTEGRATED_CANDIDATES_FILENAME))

def load_integrated_notification_deliveries(namespace_dir: str | Path) -> tuple[dict[str, Any], ...]:
    return tuple(_read_jsonl(Path(namespace_dir) / INTEGRATED_DELIVERIES_FILENAME))

def _source_coverage_lines(rows: list[dict[str, Any]]) -> list[str]:
    counts = Counter(pack for row in rows for pack in (row.get("source_packs") or [row.get("source_pack") or "unknown"]))
    lines = [f"- {pack}: {count}" for pack, count in counts.most_common()]
    lines.append(f"- Most useful next source is lane-critical: {_canonical_source_priority_summary()}.")
    return lines


def _integrated_run_id(explicit: str | None, *row_groups: Iterable[Mapping[str, Any]]) -> str | None:
    if str(explicit or "").strip():
        return str(explicit).strip()
    run_ids = {
        str(row.get("run_id") or "").strip()
        for rows in row_groups
        for row in rows
        if str(row.get("run_id") or "").strip()
    }
    return next(iter(run_ids)) if len(run_ids) == 1 else None


def _freshness_scope_line(scope: str, rows: Iterable[Mapping[str, Any]]) -> str:
    materialized = [row for row in rows if isinstance(row, Mapping)]
    statuses = Counter(_integrated_market_freshness(row) for row in materialized)
    return f"- {scope}: total={len(materialized)}; statuses={_format_counts(statuses) if statuses else 'none'}"


def _integrated_market_freshness(row: Mapping[str, Any]) -> str:
    latest = row.get("latest_market_snapshot") if isinstance(row.get("latest_market_snapshot"), Mapping) else {}
    return str(
        row.get("market_context_freshness_status")
        or row.get("integrated_market_freshness_status")
        or row.get("market_data_freshness")
        or latest.get("market_context_freshness_status")
        or latest.get("freshness_status")
        or "missing"
    )

def _canonical_source_priority_labels() -> tuple[str, ...]:
    return tuple(
        str(item.get("category") or "unknown")
        for item in event_alpha_source_coverage.SOURCE_COVERAGE_CATEGORY_PRIORITIES
    )

def _canonical_source_priority_summary() -> str:
    return ", ".join(_canonical_source_priority_labels())

def _canonical_source_priority_slugs() -> tuple[str, ...]:
    compatibility_slugs = {
        "DEX/on-chain liquidity": ("dex_onchain_liquidity",),
    }
    return tuple(
        slug
        for label in _canonical_source_priority_labels()
        for slug in compatibility_slugs.get(label, (_source_priority_slug(label),))
    )

def _source_priority_slug(value: str) -> str:
    slug = "".join(character.lower() if character.isalnum() else "_" for character in value)
    return "_".join(part for part in slug.split("_") if part)

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

def _coinalyze_status_lines(manifest: Iterable[Mapping[str, Any]]) -> list[str]:
    summary = _coinalyze_manifest_summary(manifest)
    namespace = summary.get("coinalyze_artifact_namespace")
    skip_reason = summary.get("coinalyze_skip_reason")
    if not namespace and skip_reason:
        return [f"- Coinalyze: skipped ({skip_reason})."]
    if not namespace:
        return ["- Coinalyze: not loaded."]
    state_path = summary.get("coinalyze_derivatives_state_path")
    freshness = summary.get("coinalyze_freshness_status") or "missing"
    health = summary.get("coinalyze_provider_health_status") or "not_observed"
    state_rows = int(summary.get("coinalyze_derivatives_state_rows_loaded") or 0)
    crowding_rows = int(summary.get("coinalyze_crowding_candidates_loaded") or 0)
    fade_rows = int(summary.get("coinalyze_fade_review_candidates_loaded") or 0)
    status = "loaded" if state_rows or crowding_rows or fade_rows else "skipped"
    line = (
        f"- Coinalyze: {status} namespace={namespace} "
        f"state_rows={state_rows} crowding_candidates={crowding_rows} "
        f"fade_review_candidates={fade_rows} freshness={freshness} provider_health={health}"
    )
    if state_path:
        line += f" path={event_artifact_paths.artifact_display_path(state_path)}"
    if skip_reason:
        line += f" skip_reason={skip_reason}"
    return [line]

def _coinalyze_manifest_summary(manifest: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    for item in manifest:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("sidecar_name") or "") == "coinalyze":
            return dict(item)
    return {}

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
    coinalyze = _coinalyze_manifest_summary(rows)
    row_counts = {str(item.get("sidecar_name") or "unknown"): int((item.get("row_counts") or {}).get("rows") or 0) for item in rows}
    return {
        "schema_version": 1,
        "row_type": "event_integrated_radar_input_manifest",
        "run_id": run_id,
        "profile": profile,
        "artifact_namespace": artifact_namespace,
        "run_mode": run_mode,
        "input_mode": input_mode,
        "sidecars": rows,
        "row_counts": row_counts,
        "dex_pool_state_rows_loaded": row_counts.get("dex_pool_state", 0),
        "dex_pool_anomaly_rows_loaded": row_counts.get("dex_pool_anomaly", 0),
        "protocol_fundamental_rows_loaded": row_counts.get("protocol_fundamentals", 0),
        "coinalyze_artifact_namespace": coinalyze.get("coinalyze_artifact_namespace"),
        "coinalyze_derivatives_state_rows_loaded": coinalyze.get("coinalyze_derivatives_state_rows_loaded", 0),
        "coinalyze_crowding_candidates_loaded": coinalyze.get("coinalyze_crowding_candidates_loaded", 0),
        "coinalyze_fade_review_candidates_loaded": coinalyze.get("coinalyze_fade_review_candidates_loaded", 0),
        "coinalyze_provider_health_status": coinalyze.get("coinalyze_provider_health_status", "not_observed"),
        "coinalyze_freshness_status": coinalyze.get("coinalyze_freshness_status", "missing"),
        "coinalyze_skip_reason": coinalyze.get("coinalyze_skip_reason"),
        "warnings": [warning for item in rows for warning in item.get("warnings", ())],
        "errors": [error for item in rows for error in item.get("errors", ())],
        "started_at": wall_started_at,
        "finished_at": datetime.now(timezone.utc),
        "wall_started_at": wall_started_at,
        "wall_finished_at": datetime.now(timezone.utc),
        "research_observed_at": research_observed_at,
        "generated_at": datetime.now(timezone.utc),
    }

__all__ = (
    'format_integrated_radar_report',
    'format_integrated_daily_brief',
    'build_integrated_notification_delivery_rows',
    'format_integrated_notification_preview_from_deliveries',
    'format_integrated_notification_preview',
    '_integrated_lane_message',
    '_integrated_delivery_row',
    '_row_card_path',
    'format_integrated_source_coverage',
    'format_integrated_source_coverage_json',
    'load_integrated_candidates',
    'load_integrated_notification_deliveries',
    '_source_coverage_lines',
    '_input_manifest_lines',
    '_coinalyze_status_lines',
    '_coinalyze_manifest_summary',
    '_manifest_rows',
    '_by_horizon',
    '_pct',
    '_group_by',
    '_outcome_truth',
    '_truthy',
    '_review_candidates',
    '_integrated_warnings',
    '_normalize_input_mode',
    '_manifest_item',
    '_input_manifest_document',
)
