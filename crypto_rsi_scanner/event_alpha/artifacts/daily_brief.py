"""Daily Markdown brief for Event Alpha research artifacts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from ... import (
    event_alpha_alert_store,
    event_alpha_artifacts,
    event_alpha_explain,
    event_artifact_paths,
    event_coinalyze_preflight,
    event_core_opportunities,
    event_core_opportunity_store,
    event_evidence_acquisition,
    event_near_miss,
    event_alpha_run_ledger,
    event_alpha_router,
    event_alpha_source_coverage,
    event_opportunity_verdict,
    event_alpha_reason_text,
    event_market_units,
    event_market_anomaly_scanner,
    event_official_exchange,
    event_source_packs,
    event_source_registry,
    event_source_reliability,
    event_watchlist,
)
from . import research_cards as event_research_cards
from ..outcomes import calibration as event_alpha_calibration
from ..notifications import pipeline as event_alpha_notifications
from ..notifications import runs as event_alpha_notification_runs
from ..radar import derivatives_crowding as event_derivatives_crowding
from ..radar import scheduled_catalysts as event_scheduled_catalysts


@dataclass(frozen=True)
class EventAlphaDailyBriefResult:
    path: Path
    markdown: str
    cards: tuple[Path, ...] = ()


def build_daily_brief(
    *,
    run_rows: Iterable[Mapping[str, Any]] = (),
    alert_rows: Iterable[Mapping[str, Any]] = (),
    feedback_rows: Iterable[Mapping[str, Any]] = (),
    missed_rows: Iterable[Mapping[str, Any]] = (),
    core_opportunity_rows: Iterable[Mapping[str, Any]] = (),
    notification_runs: Iterable[Mapping[str, Any]] = (),
    hypothesis_rows: Iterable[Mapping[str, Any]] = (),
    incident_rows: Iterable[Mapping[str, Any]] = (),
    evidence_acquisition_rows: Iterable[Mapping[str, Any]] = (),
    market_anomaly_rows: Iterable[Mapping[str, Any]] | None = None,
    official_exchange_candidate_rows: Iterable[Mapping[str, Any]] | None = None,
    scheduled_catalyst_rows: Iterable[Mapping[str, Any]] | None = None,
    unlock_candidate_rows: Iterable[Mapping[str, Any]] | None = None,
    derivatives_state_rows: Iterable[Mapping[str, Any]] | None = None,
    fade_review_candidate_rows: Iterable[Mapping[str, Any]] | None = None,
    watchlist_entries: Iterable[event_watchlist.EventWatchlistEntry] = (),
    router_result: event_alpha_router.EventAlphaRouterResult | None = None,
    provider_health_rows: Mapping[str, Mapping[str, Any]] | None = None,
    card_paths: Iterable[Path] = (),
    requested_profile: str | None = None,
    artifact_namespace: str | None = None,
    run_mode: str | None = None,
    run_ledger_path: str | Path | None = None,
    alert_store_path: str | Path | None = None,
    include_test_artifacts: bool = False,
    include_legacy_artifacts: bool = False,
    include_diagnostics: bool = False,
    clock_status: Mapping[str, Any] | None = None,
    generated_at: datetime | None = None,
) -> str:
    generated = (generated_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    raw_runs = [dict(row) for row in run_rows if isinstance(row, Mapping)]
    legacy_available = any(event_alpha_artifacts.is_legacy_row(row) for row in raw_runs)
    runs = event_alpha_artifacts.filter_artifact_rows(
        raw_runs,
        profile=requested_profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    alerts = event_alpha_artifacts.filter_artifact_rows(
        alert_rows,
        profile=requested_profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    feedback = event_alpha_artifacts.filter_artifact_rows(
        feedback_rows,
        profile=requested_profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    missed = event_alpha_artifacts.filter_artifact_rows(
        missed_rows,
        profile=requested_profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    stored_core_rows = event_alpha_artifacts.filter_artifact_rows(
        [dict(row) for row in core_opportunity_rows if isinstance(row, Mapping)],
        profile=requested_profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    hypotheses = event_alpha_artifacts.filter_artifact_rows(
        [dict(row) for row in hypothesis_rows if isinstance(row, Mapping)],
        profile=requested_profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    incidents = event_alpha_artifacts.filter_artifact_rows(
        [dict(row) for row in incident_rows if isinstance(row, Mapping)],
        profile=requested_profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    acquisition_rows = event_alpha_artifacts.filter_artifact_rows(
        [dict(row) for row in evidence_acquisition_rows if isinstance(row, Mapping)],
        profile=requested_profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    raw_market_anomalies = (
        [dict(row) for row in market_anomaly_rows if isinstance(row, Mapping)]
        if market_anomaly_rows is not None
        else list(event_market_anomaly_scanner.load_market_anomaly_rows(Path(run_ledger_path).parent if run_ledger_path else None))
    )
    market_anomalies = event_alpha_artifacts.filter_artifact_rows(
        raw_market_anomalies,
        profile=requested_profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    raw_official_exchange_candidates = (
        [dict(row) for row in official_exchange_candidate_rows if isinstance(row, Mapping)]
        if official_exchange_candidate_rows is not None
        else list(event_official_exchange.load_official_listing_candidates(Path(run_ledger_path).parent if run_ledger_path else None))
    )
    official_exchange_candidates = event_alpha_artifacts.filter_artifact_rows(
        raw_official_exchange_candidates,
        profile=requested_profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    raw_scheduled_catalysts = (
        [dict(row) for row in scheduled_catalyst_rows if isinstance(row, Mapping)]
        if scheduled_catalyst_rows is not None
        else list(event_scheduled_catalysts.load_scheduled_catalysts(Path(run_ledger_path).parent if run_ledger_path else None))
    )
    scheduled_catalysts = event_alpha_artifacts.filter_artifact_rows(
        raw_scheduled_catalysts,
        profile=requested_profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    raw_unlock_candidates = (
        [dict(row) for row in unlock_candidate_rows if isinstance(row, Mapping)]
        if unlock_candidate_rows is not None
        else list(event_scheduled_catalysts.load_unlock_candidates(Path(run_ledger_path).parent if run_ledger_path else None))
    )
    unlock_candidates = event_alpha_artifacts.filter_artifact_rows(
        raw_unlock_candidates,
        profile=requested_profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    raw_derivatives_state = (
        [dict(row) for row in derivatives_state_rows if isinstance(row, Mapping)]
        if derivatives_state_rows is not None
        else list(event_derivatives_crowding.load_derivatives_state(Path(run_ledger_path).parent if run_ledger_path else None))
    )
    derivatives_state = event_alpha_artifacts.filter_artifact_rows(
        raw_derivatives_state,
        profile=requested_profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    raw_fade_review_candidates = (
        [dict(row) for row in fade_review_candidate_rows if isinstance(row, Mapping)]
        if fade_review_candidate_rows is not None
        else list(event_derivatives_crowding.load_fade_review_candidates(Path(run_ledger_path).parent if run_ledger_path else None))
    )
    fade_review_candidates = event_alpha_artifacts.filter_artifact_rows(
        raw_fade_review_candidates,
        profile=requested_profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    entries = list(watchlist_entries)
    decisions = list(router_result.decisions if router_result else ())
    alertable = [decision for decision in list(router_result.alertable_decisions if router_result else ()) if event_alpha_router.alertable_after_quality_gate(decision)]
    if stored_core_rows:
        core_opportunities = event_core_opportunity_store.core_opportunities_from_rows(stored_core_rows)
        core_source_rows: list[Any] = stored_core_rows
    else:
        core_opportunities = event_core_opportunities.aggregate_core_opportunities([*decisions, *hypotheses])
        core_source_rows = [*(decision.entry for decision in decisions), *hypotheses]
    core_sections = _core_opportunity_sections(core_opportunities)
    lane_sections = _core_opportunity_lane_sections(core_opportunities)
    source_coverage_report_path = (
        Path(run_ledger_path).parent / "event_alpha_source_coverage.md"
        if run_ledger_path
        else None
    )
    core_alertable_count = _core_alertable_count(core_opportunities)
    diagnostic_core_rows = sum(item.diagnostic_row_count for item in core_opportunities)
    diagnostic_control_rows = sum(item.source_noise_control_count for item in core_opportunities)
    diagnostic_capped_rows = sum(item.quality_capped_supporting_rows for item in core_opportunities)
    promoted_core_asset_keys = {
        event_core_opportunities.incident_asset_key_for_opportunity(item)
        for item in core_opportunities
        if item.alertable or item.is_high_priority or item.is_watchlist or item.is_validated_digest
    }
    promoted_core_assets = {
        event_core_opportunities.asset_key_for_opportunity(item)
        for item in core_opportunities
        if item.alertable or item.is_high_priority or item.is_watchlist or item.is_validated_digest
    }
    high_priority_core_asset_keys = {
        event_core_opportunities.asset_key_for_opportunity(item)
        for item in core_sections["strong"]
    }
    near_misses = event_near_miss.detect_near_miss_rows(
        core_source_rows,
        route_decisions=decisions,
    )
    _, raw_upgrade_candidates = event_near_miss.split_near_miss_candidates(near_misses)
    near_miss_candidates = tuple(
        item for item in near_misses
        if not event_near_miss.is_upgrade_candidate(item)
        and event_core_opportunities.incident_asset_key_for_values(
            item.incident_id,
            item.coin_id,
            item.symbol,
        ) not in promoted_core_asset_keys
        and event_core_opportunities.asset_key_for_values(item.coin_id, item.symbol) not in promoted_core_assets
    )
    upgrade_candidates = tuple(
        item for item in raw_upgrade_candidates
        if event_core_opportunities.incident_asset_key_for_values(
            item.incident_id,
            item.coin_id,
            item.symbol,
        ) not in {
            event_core_opportunities.incident_asset_key_for_opportunity(core)
            for core in core_sections["strong"]
        }
        and event_core_opportunities.asset_key_for_values(item.coin_id, item.symbol) not in high_priority_core_asset_keys
    )
    near_miss_asset_keys = {
        event_core_opportunities.asset_key_for_values(item.coin_id, item.symbol)
        for item in near_miss_candidates
    }
    near_miss_incident_asset_keys = {
        event_core_opportunities.incident_asset_key_for_values(item.incident_id, item.coin_id, item.symbol)
        for item in near_miss_candidates
    }
    local_core_rows = [
        item for item in core_sections["local"]
        if event_core_opportunities.asset_key_for_opportunity(item) not in near_miss_asset_keys
        and event_core_opportunities.incident_asset_key_for_opportunity(item) not in near_miss_incident_asset_keys
    ]
    latest = event_alpha_run_ledger.latest_run(runs, requested_profile) or {}
    selected_profile = str(latest.get("profile") or "default") if latest else "none"
    selected_namespace = str(latest.get("artifact_namespace") or "legacy") if latest else "none"
    requested = str(requested_profile or "latest").strip() or "latest"
    profile_match = (
        "n/a"
        if not latest or requested_profile is None
        else str(selected_profile == str(requested_profile)).lower()
    )
    mismatch_warning = event_alpha_run_ledger.run_profile_mismatch_warning(requested_profile, latest)
    lines = [
        "# Event Alpha Daily Brief",
        "",
        f"Generated at: {generated.isoformat()}",
        _format_clock_status(clock_status or {}),
        *_format_clock_warning_lines(clock_status or {}),
        f"Requested profile: {requested}",
        f"Artifact namespace: {artifact_namespace or 'any'}",
        f"Run mode: {run_mode or 'unknown'}",
        f"Run ledger path: {event_alpha_artifacts.safe_path_label(run_ledger_path) if run_ledger_path else 'unknown'}",
        f"Alert store path: {event_alpha_artifacts.safe_path_label(alert_store_path) if alert_store_path else 'unknown'}",
        f"Selected run profile: {selected_profile}",
        f"Selected run namespace: {selected_namespace}",
        f"Profile match: {profile_match}",
        "",
        "Research-only. Not a trade signal, paper trade, live RSI signal, or execution.",
        "Canonical operator view: Core Opportunities sections above. Diagnostics appendix contains raw/supporting/control rows and may repeat assets for debugging.",
        "",
        "## Executive Summary",
        f"- Core opportunities: {len(core_opportunities)} "
        f"(canonical_store_rows={len(stored_core_rows)}, "
        f"high_priority={len(core_sections['strong'])}, digest={len(core_sections['digest'])}, "
        f"watchlist={len(core_sections['watchlist'])}, near_miss={len(near_miss_candidates)}, "
        f"upgrade={len(upgrade_candidates)}, "
        f"local_or_capped={len(local_core_rows)})",
        f"- Alertable routed decisions: {core_alertable_count}",
        f"- Near-miss candidates: {len(near_miss_candidates)}",
        f"- Upgrade candidates: {len(upgrade_candidates)}",
        "- Opportunity lanes: "
        + ", ".join(
            f"{name}={len(items)}"
            for name, items in lane_sections.items()
            if name != "diagnostics"
        ),
        "",
        "## Burn-In Readiness",
        *_burn_in_readiness_lines(
            latest=latest,
            core_opportunities=core_opportunities,
            card_paths=card_paths,
            evidence_acquisition_rows=acquisition_rows,
            provider_health_rows=provider_health_rows or {},
            requested_profile=requested_profile,
        ),
        "",
        "## Opportunity Lanes",
        "Research-only lane classification. Not a trade signal.",
        "",
        "### Early Long Research",
        *_core_opportunity_lines(lane_sections["early"], limit=8),
        "",
        "### Confirmed Long Research",
        *_core_opportunity_lines(lane_sections["confirmed"], limit=8),
        "",
        "### Fade / Short-Review",
        *_core_opportunity_lines(lane_sections["fade"], limit=8),
        "",
        "### Risk Only",
        *_core_opportunity_lines(lane_sections["risk"], limit=8),
        "",
        "### Unconfirmed Research",
        *_core_opportunity_lines(lane_sections["unconfirmed"], limit=8),
        "",
        "## High-Priority Core Opportunities",
        *_core_opportunity_lines(core_sections["strong"], limit=8),
        "",
        "## Validated Digest Core Opportunities",
        *_core_opportunity_lines(core_sections["digest"], limit=8),
        "",
        "## Watchlist Core Opportunities",
        *_core_opportunity_lines(core_sections["watchlist"], limit=8),
        "",
        "## Near-Miss Candidates",
        *_near_miss_daily_lines(near_miss_candidates, limit=8),
        "",
        "## Upgrade Candidates",
        *_near_miss_daily_lines(upgrade_candidates, limit=8),
        "",
        "## Quality-Capped / Local-Only Candidates",
        *_core_opportunity_lines(local_core_rows, limit=8),
        "",
        "## Live Confirmation Gated Candidates",
        *_live_confirmation_gated_core_lines(core_opportunities, limit=8),
        "",
        "## Top Market Anomalies Needing Catalyst Search",
        *_market_anomaly_daily_lines(market_anomalies, limit=10),
        "",
        "## Fresh Official Exchange Catalysts",
        *_official_exchange_daily_lines(official_exchange_candidates, limit=10),
        "",
        "## Upcoming Scheduled Catalysts",
        *_scheduled_catalyst_daily_lines(scheduled_catalysts, limit=10),
        "",
        "## Unlock / Supply Risk",
        *_unlock_risk_daily_lines(unlock_candidates, limit=10),
        "",
        "## Derivatives Crowding / Fade-Review Research",
        *_derivatives_fade_review_daily_lines(fade_review_candidates, derivatives_state, limit=10),
        "",
        "## Catalyst Calendar Gaps",
        *_calendar_gap_daily_lines([*scheduled_catalysts, *unlock_candidates], limit=10),
        "",
        "## Near-Term Events Needing Market Watch",
        *_scheduled_market_watch_lines([*scheduled_catalysts, *unlock_candidates], limit=10),
        "",
        "## Canonical Incidents",
        *_canonical_incident_lines(incidents),
        "",
        "## System Health",
        *_system_health_summary_lines(latest),
        "",
        "## Source Coverage / Evidence Acquisition",
        *_source_coverage_summary_lines(
            [*core_source_rows, *alerts],
            near_miss_candidates,
            upgrade_candidates,
            acquisition_rows=acquisition_rows,
            source_coverage_report_path=source_coverage_report_path,
        ),
        "",
        "### Provider Health by Source Pack",
        *_provider_health_by_pack_lines(
            provider_health_rows or {},
            source_coverage_report_path=source_coverage_report_path,
        ),
        "",
        "### Evidence Acquisition Results",
        *_evidence_acquisition_result_lines(
            (*near_miss_candidates, *upgrade_candidates),
            acquisition_rows=acquisition_rows,
            core_opportunities=core_opportunities,
            limit=8,
        ),
        "",
        "### Candidates Blocked by Source Coverage",
        *_coverage_blocked_candidate_lines((*near_miss_candidates, *upgrade_candidates), limit=8),
        "",
        "## Market Freshness Readiness",
        *_market_freshness_readiness_lines([*core_source_rows, *alerts], requested_profile=requested_profile),
        "",
        "## Diagnostics Appendix",
        "### Diagnostic Appendix: Diagnostics / Source-Noise / Controls",
        (
            "- Hidden from main opportunity sections by default: "
            f"diagnostic_rows={diagnostic_core_rows}, "
            f"source_noise_controls={diagnostic_control_rows}, "
            f"quality_capped_support={diagnostic_capped_rows}, "
            f"diagnostic_lane_cores={len(lane_sections['diagnostics'])}"
        ),
        (
            "- Pass include_diagnostics in local tooling to inspect collapsed controls."
            if diagnostic_core_rows or diagnostic_control_rows or diagnostic_capped_rows
            else "- None."
        ),
        "",
        "### System Health / Providers / Budget",
    ]
    if mismatch_warning:
        lines.append(f"- Profile warning: {mismatch_warning}")
    if requested_profile and not runs and legacy_available and not include_legacy_artifacts:
        lines.append("- Profile warning: only legacy/default run rows were available; they were ignored for this profile brief")
    if latest:
        run_alertable = int(latest.get("alertable") or 0)
        alertable_text = str(core_alertable_count)
        if run_alertable != core_alertable_count:
            alertable_text = f"{core_alertable_count} (run_ledger_pre_core={run_alertable})"
        lines.extend([
            f"- Run: {latest.get('run_id') or 'unknown'}",
            f"- Profile: {latest.get('profile') or 'default'}",
            f"- Success: {str(bool(latest.get('success'))).lower()}",
            f"- Raw/events/candidates/alerts: {int(latest.get('raw_events') or 0)} / {int(latest.get('candidates') or 0)} / {int(latest.get('alerts') or 0)}",
            f"- Routed/alertable/sent: {int(latest.get('routed') or 0)} / {alertable_text} / {str(bool(latest.get('sent'))).lower()}",
            f"- Sent/delivered/block: {int(latest.get('send_items_delivered') or 0)}/{int(latest.get('send_items_attempted') or 0)} / {latest.get('send_block_reason') or 'none'}",
            "- Catalyst frames analyzed/validated/disagreements/unresolved: "
            f"{int(latest.get('catalyst_frames_analyzed') or latest.get('catalyst_frame_rows') or 0)} / "
            f"{int(latest.get('catalyst_frame_validations') or latest.get('catalyst_frame_validations_applied') or 0)} / "
            f"{int(latest.get('catalyst_frame_disagreements') or 0)} / "
            f"{int(latest.get('catalyst_frame_unresolved') or 0)}",
            f"- Catalyst frame rows skipped/missing: {int(latest.get('catalyst_frame_rows_skipped') or 0)}",
        ])
        catalyst_frame_skip = latest.get("catalyst_frame_skip_reasons") or {}
        if isinstance(catalyst_frame_skip, Mapping) and catalyst_frame_skip:
            lines.append(
                "- Catalyst frame skip reasons: "
                + ", ".join(f"{key}={int(value or 0)}" for key, value in sorted(catalyst_frame_skip.items()))
            )
        warnings = [str(w) for w in latest.get("warnings") or [] if str(w)]
        if warnings:
            lines.append("- Warnings: " + "; ".join(warnings[:6]))
    else:
        lines.append("- No run ledger rows found.")
    latest_notification = _latest_notification_run(notification_runs)
    if latest_notification is not None:
        lines.append(
            "- Notify lock/deliveries: "
            f"lock_acquired={str(bool(latest_notification.get('lock_acquired'))).lower()} "
            f"skipped_active_lock={str(bool(latest_notification.get('skipped_due_to_active_lock'))).lower()} "
            f"deliveries={int(latest_notification.get('deliveries_delivered') or 0)}d/"
            f"{int(latest_notification.get('deliveries_partial_delivered') or 0)}partial/"
            f"{int(latest_notification.get('deliveries_failed') or 0)}f/"
            f"{int(latest_notification.get('deliveries_skipped_duplicate') or 0)}dup/"
            f"{int(latest_notification.get('deliveries_skipped_in_flight') or 0)}flight/"
            f"{int(latest_notification.get('deliveries_blocked') or 0)}blocked"
        )
        if event_alpha_notification_runs.row_has_delivery_failures(latest_notification):
            lines.append(
                f"- Notify delivery failures: {int(latest_notification.get('deliveries_failed') or 0)} "
                "failed delivery row(s) — run --event-alpha-notification-deliveries-report"
            )
    lines.extend(["", "#### Provider Health"])
    lines.extend(_provider_health_lines(provider_health_rows or {}))
    lines.extend(["", "#### LLM Budget"])
    lines.extend(_llm_budget_lines(latest))
    lines.extend(["", "### Impact Hypotheses"])
    if latest:
        lines.append(
            f"- Generated/validated/promoted: {int(latest.get('impact_hypotheses') or 0)} / "
            f"{int(latest.get('hypotheses_validated') or 0)} / {int(latest.get('hypothesis_promotions') or 0)}"
        )
        lines.append(
            f"- Validation queries/results: {int(latest.get('hypothesis_search_queries') or 0)} / "
            f"{int(latest.get('hypothesis_search_results') or 0)}"
        )
        query_types = latest.get("hypothesis_search_queries_by_type") or {}
        result_types = latest.get("hypothesis_search_results_by_type") or {}
        if isinstance(query_types, Mapping) or isinstance(result_types, Mapping):
            lines.append(
                "- Validation query types: "
                f"queries={_format_counts(query_types if isinstance(query_types, Mapping) else {})}; "
                f"results={_format_counts(result_types if isinstance(result_types, Mapping) else {})}"
            )
        if int(latest.get("hypotheses_validated") or 0) <= 0:
            lines.append("- Validated hypotheses: none yet.")
        if int(latest.get("impact_hypotheses") or 0) > int(latest.get("hypotheses_validated") or 0):
            lines.append("- Top rejected/pending hypotheses: see Event Alpha pipeline report and local watchlist HYPOTHESIS rows.")
        hypothesis_skip = latest.get("hypothesis_search_skip_reasons") or {}
        if isinstance(hypothesis_skip, Mapping) and hypothesis_skip:
            lines.append(
                "- Hypothesis validation skips: "
                + ", ".join(f"{key}={int(value or 0)}" for key, value in sorted(hypothesis_skip.items()))
            )
    else:
        lines.append("- No run row available.")
    if hypotheses:
        status_counts = _field_counts(hypotheses, "status")
        stage_counts = _field_counts(hypotheses, "validation_stage")
        category_counts = _field_counts(hypotheses, "impact_category")
        schema_counts = _field_counts(hypotheses, "schema_version")
        why_counts = _multi_field_counts(hypotheses, "why_not_promoted")
        legacy_count = sum(
            1 for row in hypotheses
            if not str(row.get("schema_version") or "").startswith("event_impact_hypothesis_store_")
            or any(
                field not in row
                for field in ("validation_stage", "hypothesis_score", "external_entities", "crypto_candidate_assets")
            )
        )
        lines.append("- Stored rows: " + str(len(hypotheses)))
        lines.append("- Stored schema versions: " + _format_counts(schema_counts) + f" (legacy={legacy_count})")
        lines.append("- Stored statuses: " + _format_counts(status_counts))
        lines.append("- Stored validation stages: " + _format_counts(stage_counts))
        lines.append("- Stored categories: " + _format_counts(category_counts))
        lines.append("- Why not promoted: " + _format_counts(why_counts))
        pending = [
            row for row in hypotheses
            if str(row.get("status") or "") in {"validation_search_pending", "hypothesis"}
        ]
        validated = [
            row for row in hypotheses
            if str(row.get("status") or "") in {"validation_evidence_found", "validated"}
        ]
        rejected = [
            row for row in hypotheses
            if str(row.get("status") or "") == "rejected" or row.get("rejection_reasons")
        ]
        lines.append("- Validated stored hypotheses: " + (_brief_hypothesis_labels(validated[:3]) or "none"))
        lines.append("- Pending stored hypotheses: " + (_brief_hypothesis_labels(pending[:3]) or "none"))
        lines.append("- Top rejected hypotheses: " + (_brief_hypothesis_labels(rejected[:3]) or "none"))
        ranked = sorted(
            hypotheses,
            key=lambda row: _float(row.get("hypothesis_score") or _float(row.get("confidence")) * 100),
            reverse=True,
        )
        lines.append("- Top hypothesis scores: " + (_brief_hypothesis_labels(ranked[:3]) or "none"))
        rejected_samples = sum(
            1
            for row in hypotheses
            for sample in (row.get("rejected_validation_samples") or [])
            if isinstance(sample, Mapping) and (not bool(sample.get("accepted")) or sample.get("rejection_reason"))
        )
        if rejected_samples:
            lines.append(f"- Rejected validation evidence samples: {rejected_samples}")
            reason_counts: dict[str, int] = {}
            titles: list[str] = []
            for row in hypotheses:
                for sample in row.get("rejected_validation_samples") or []:
                    if not isinstance(sample, Mapping):
                        continue
                    if bool(sample.get("accepted")) and not sample.get("rejection_reason"):
                        continue
                    reason = str(sample.get("rejection_reason") or "unknown")
                    reason_counts[reason] = reason_counts.get(reason, 0) + 1
                    title = str(sample.get("result_title") or "").strip()
                    if title and title not in titles:
                        titles.append(title)
            lines.append("- Rejected evidence reasons: " + _format_counts(reason_counts))
            if titles:
                lines.append("- Rejected evidence examples: " + " | ".join(titles[:3]))
    elif latest and int(latest.get("impact_hypotheses") or 0) > 0:
        lines.append("- Stored rows: none loaded for this profile; inspect --event-impact-hypotheses-report.")
    lines.extend(["", "### Catalyst Search Skip Reasons"])
    if latest:
        skip_reasons = latest.get("catalyst_search_skip_reasons") or {}
        if isinstance(skip_reasons, Mapping) and skip_reasons:
            for key, value in sorted(skip_reasons.items()):
                lines.append(f"- {key}: {int(value or 0)}")
        elif int(latest.get("market_anomalies") or 0) > 0 and int(latest.get("catalyst_queries") or 0) == 0:
            lines.append("- unknown: market anomalies were present but no catalyst queries were generated.")
        else:
            lines.append("- None.")
    else:
        lines.append("- No run row available.")
    lines.extend(["", "### New Since Last Run"])
    lines.extend(_new_since_last_run_lines(runs))
    lines.extend(["", "### Watchlist Got Hotter"])
    lines.extend(_watchlist_hotter_lines(entries))
    lines.extend(["", "### Alertable Decisions"])
    if core_alertable_count > 0:
        lines.append(f"- {core_alertable_count} canonical alertable core opportunity/opportunities; see core opportunity sections above.")
    elif alertable and include_diagnostics:
        lines.append("- Raw pre-policy route attempts only; these are diagnostic rows and are not operator alert truth.")
        for decision in alertable[:10]:
            entry = decision.entry
            lines.append(f"- diagnostic {event_alpha_router.final_route_value(decision)}: {entry.symbol}/{entry.coin_id} state={event_watchlist.final_state_value(entry)} score={entry.latest_score} reason={decision.reason}")
    else:
        lines.append("- None.")
    lines.extend(["", "### Validated Impact Hypothesis Routing"])
    alertable_hypotheses = [
        decision for decision in decisions
        if decision.entry.relationship_type == "impact_hypothesis" and event_alpha_router.alertable_after_quality_gate(decision)
    ]
    impact_path_validated_hypotheses = [
        decision for decision in decisions
        if (
            decision.entry.relationship_type == "impact_hypothesis"
            and str((decision.entry.latest_score_components or {}).get("validation_stage") or "") in {
                "impact_path_validated",
                "market_confirmed",
                "promoted_to_radar",
            }
        )
    ]
    local_validated_hypotheses = [
        decision for decision in decisions
        if (
            decision.entry.relationship_type == "impact_hypothesis"
            and not event_alpha_router.alertable_after_quality_gate(decision)
            and event_watchlist.final_state_value(decision.entry) == event_watchlist.EventWatchlistState.RADAR.value
            and decision.entry.symbol.upper() != "SECTOR"
        )
    ]
    weak_local_hypotheses = [
        decision for decision in local_validated_hypotheses
        if (
            str((decision.entry.latest_score_components or {}).get("validation_stage") or "") == "catalyst_link_validated"
            or str((decision.entry.latest_score_components or {}).get("impact_path_strength") or "") in {"weak", "none"}
            or bool((decision.entry.latest_score_components or {}).get("why_digest_ineligible"))
        )
    ]
    generic_blocked_hypotheses = [
        decision for decision in local_validated_hypotheses
        if str((decision.entry.latest_score_components or {}).get("impact_path_type") or "") == "generic_cooccurrence_only"
    ]
    strong_opportunity_hypotheses = [
        decision for decision in decisions
        if decision.entry.relationship_type == "impact_hypothesis"
        and str((decision.entry.latest_score_components or {}).get("opportunity_level") or "") in {
            "watchlist",
            "high_priority",
        }
    ]
    market_unconfirmed_hypotheses = [
        decision for decision in local_validated_hypotheses
        if str((decision.entry.latest_score_components or {}).get("market_confirmation_level") or "") in {
            "",
            "none",
            "weak",
        }
        and str((decision.entry.latest_score_components or {}).get("opportunity_level") or "") in {
            "local_only",
            "exploratory",
            "",
        }
    ]
    exploratory_sector_hypotheses = [
        entry for entry in entries
        if entry.relationship_type == "impact_hypothesis"
        and event_watchlist.final_state_value(entry) == event_watchlist.EventWatchlistState.HYPOTHESIS.value
    ]
    rejected_hypotheses = [
        row for row in hypotheses
        if str(row.get("status") or "") == "rejected" or row.get("why_not_promoted") or row.get("rejection_reasons")
    ]
    lines.append("- Strong opportunity candidates: " + (_brief_core_opportunities(core_opportunities, section="strong", limit=5) or "none"))
    digest_candidates = _brief_core_opportunities(core_opportunities, section="digest", limit=5)
    if not digest_candidates and include_diagnostics:
        digest_candidates = (
            "raw diagnostic only: "
            + (_brief_decisions(alertable_hypotheses[:5]) or _brief_decisions(impact_path_validated_hypotheses[:5]) or "none")
        )
    lines.append("- Impact-path validated digest candidates: " + (digest_candidates or "none"))
    lines.append("- Validated but market-unconfirmed: " + (_brief_decisions(market_unconfirmed_hypotheses[:5]) or "none"))
    lines.append("- Weak validated local-only hypotheses: " + (_brief_decisions(weak_local_hypotheses[:5]) or "none"))
    lines.append("- Generic co-occurrence blocked: " + (_brief_decisions(generic_blocked_hypotheses[:5]) or "none"))
    lines.append("- Sector hypotheses awaiting validation: " + (_brief_entries(exploratory_sector_hypotheses[:5]) or "none"))
    lines.append("- Rejected/why-not-promoted hypotheses: " + (_brief_hypothesis_labels(rejected_hypotheses[:5]) or "none"))
    lines.append("- Market confirmation by playbook: " + _market_confirmation_by_playbook(decisions))
    lines.append("- Top upgrade candidates: " + (_upgrade_candidate_line(decisions) or "none"))
    lines.append("- Top downgrade risks: " + (_downgrade_risk_line(decisions) or "none"))
    lines.extend(["", "### Near-Miss Diagnostics"])
    lines.extend(_near_miss_diagnostic_lines(near_miss_candidates, limit=8))
    lines.extend(["", "### Upgrade Candidate Diagnostics"])
    lines.extend(_near_miss_diagnostic_lines(upgrade_candidates, limit=8))
    lines.extend(["", "### Signal Quality Summary"])
    lines.append("- Opportunity Verdict Distribution: " + _quality_decision_counts(decisions, "opportunity_level"))
    lines.append("- Impact Path Distribution: " + _quality_decision_counts(decisions, "impact_path_type"))
    lines.append("- Candidate Role Distribution: " + _quality_decision_counts(decisions, "candidate_role"))
    lines.append("- Incident Archetype Distribution: " + _quality_decision_counts(decisions, "event_archetype"))
    lines.append("- Cause Status Distribution: " + _quality_decision_counts(decisions, "cause_status"))
    lines.append("- Market Reaction Confirmed: " + _quality_decision_counts(decisions, "market_reaction_confirmed"))
    lines.append("- Causal Mechanism Confirmed: " + _quality_decision_counts(decisions, "causal_mechanism_confirmed"))
    lines.append("- Evidence Specificity Distribution: " + _quality_decision_counts(decisions, "evidence_specificity"))
    lines.append("- Market Confirmation Distribution: " + _quality_decision_counts(decisions, "market_confirmation_level"))
    lines.append("- Market Context Freshness: " + _quality_decision_counts(decisions, "market_context_freshness_status"))
    lines.append("- Top Upgrade Candidates: " + (_upgrade_candidate_line(decisions) or "none"))
    lines.append("- Top Downgrade Risks: " + (_downgrade_risk_line(decisions) or "none"))
    lines.append("- Candidate Discovery Funnel: " + _candidate_discovery_funnel_line(hypotheses))
    lines.append("- Feedback by Impact Path: " + _feedback_by_impact_path(alerts, feedback))
    lines.extend(["", "### Quality Gate Downgrades"])
    downgraded = _quality_gate_downgrades(decisions)
    lines.append("- Downgraded items: " + (_brief_decisions(downgraded[:5]) or "none"))
    lines.append("- Top blocked route attempts: " + (_blocked_route_attempts_line(downgraded) or "none"))
    lines.append("- Reason counts: " + _quality_gate_reason_counts(downgraded))
    lines.extend(["", "### Legacy Quality Conflicts"])
    conflicts = _legacy_quality_conflicts(alerts)
    lines.extend(_legacy_quality_conflict_lines(conflicts[:8]))
    research_review = event_alpha_notifications.select_research_review_candidates(
        decisions,
        cfg=event_alpha_notifications.EventAlphaNotificationConfig(
            research_review_digest_enabled=True,
            research_review_digest_max_items=5,
            research_review_digest_min_score=60,
            research_review_digest_include_local_only=False,
        ),
        now=generated,
    )
    research_review = tuple(
        item for item in research_review
        if event_core_opportunities.incident_asset_key_for_values(
            getattr(item.decision.entry, "incident_id", None),
            item.decision.entry.coin_id,
            item.decision.entry.symbol,
        ) not in promoted_core_asset_keys
        and event_core_opportunities.asset_key_for_values(item.decision.entry.coin_id, item.decision.entry.symbol)
        not in promoted_core_assets
    )
    lines.extend(["", "### Research Review Digest"])
    review_due = _lane_count(latest_notification, "lane_counts_due", event_alpha_notifications.LANE_RESEARCH_REVIEW_DIGEST)
    review_sent = _lane_count(latest_notification, "lane_counts_sent", event_alpha_notifications.LANE_RESEARCH_REVIEW_DIGEST)
    if latest:
        lines.append(
            "- Run ledger: "
            f"research_review_digest_enabled={str(bool(latest.get('research_review_digest_enabled'))).lower()} "
            f"research_review_digest_candidates={int(latest.get('research_review_digest_candidates') or 0)} "
            f"research_review_digest_would_send={int(latest.get('research_review_digest_would_send') or 0)} "
            f"research_review_digest_block={latest.get('research_review_digest_block_reason') or 'none'}"
        )
    lines.append(f"- Lane count sent/due: {review_sent}/{review_due}")
    lines.append("- Near-miss research review only; not alertable, missing confirmation, and not a trade signal.")
    planned_review_deliveries = _research_review_delivery_rows(run_ledger_path)
    if research_review:
        for item in research_review[:5]:
            entry = item.decision.entry
            lines.append(
                f"- {entry.symbol}/{entry.coin_id} level={event_alpha_notifications._research_review_level(item.decision) or 'unknown'} "
                f"score={event_alpha_notifications._research_review_score(item.decision):g} "
                f"why_not_alertable={'; '.join(item.why_not_alertable) or 'missing confirmation'}"
            )
    elif planned_review_deliveries:
        for row in planned_review_deliveries[:5]:
            lines.append(_research_review_delivery_line(row))
        if len(planned_review_deliveries) > 5:
            lines.append(f"- +{len(planned_review_deliveries) - 5} more research-review delivery candidates")
    else:
        lines.append("- None.")
    exploratory = event_alpha_notifications.select_exploratory_candidates(
        decisions,
        cfg=event_alpha_notifications.EventAlphaNotificationConfig(
            exploratory_digest_enabled=True,
            exploratory_digest_max_items=5,
        ),
        now=generated,
    )
    exploratory = tuple(
        item for item in exploratory
        if event_core_opportunities.incident_asset_key_for_values(
            getattr(item.decision.entry, "incident_id", None),
            item.decision.entry.coin_id,
            item.decision.entry.symbol,
        ) not in promoted_core_asset_keys
        and event_core_opportunities.asset_key_for_values(item.decision.entry.coin_id, item.decision.entry.symbol)
        not in promoted_core_assets
    )
    lines.extend(["", "### Exploratory Digest"])
    exploratory_due = _lane_count(latest_notification, "lane_counts_due", event_alpha_notifications.LANE_EXPLORATORY_DIGEST)
    exploratory_sent = _lane_count(latest_notification, "lane_counts_sent", event_alpha_notifications.LANE_EXPLORATORY_DIGEST)
    lines.append(f"- Lane count sent/due: {exploratory_sent}/{exploratory_due}")
    lines.append("- Unvalidated suppressed/store-only rows for learning; not alertable and not a trade signal.")
    if exploratory:
        for item in exploratory[:5]:
            entry = item.decision.entry
            lines.append(
                f"- {entry.symbol}/{entry.coin_id} score={entry.latest_score} "
                f"playbook={entry.latest_playbook_type or 'unknown'} reason={entry.suppressed_reason or item.decision.reason}"
            )
    else:
        lines.append("- None.")
    lines.extend(["", "### Active Watchlist"])
    active = [
        entry for entry in entries
        if not event_watchlist.state_is_quality_capped(entry)
        and event_watchlist.final_state_value(entry) in {
            event_watchlist.EventWatchlistState.RADAR.value,
            event_watchlist.EventWatchlistState.WATCHLIST.value,
            event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
            event_watchlist.EventWatchlistState.EVENT_PASSED.value,
            event_watchlist.EventWatchlistState.ARMED.value,
        }
    ]
    active = _dedupe_watchlist_entries(active)
    if active:
        for entry in sorted(active, key=lambda item: item.latest_score, reverse=True)[:5]:
            lines.append(
                f"- {event_watchlist.final_state_value(entry)}: {entry.symbol}/{entry.coin_id} "
                f"score={entry.latest_score} playbook={entry.latest_playbook_type or 'unknown'}"
                f"{_watchlist_identity_suffix(entry)}"
            )
    else:
        lines.append("- No active watchlist entries.")
    lines.extend(["", "### Quality-Capped Watchlist Rows"])
    capped = _dedupe_watchlist_entries([entry for entry in entries if event_watchlist.state_is_quality_capped(entry)])
    if capped:
        for entry in sorted(capped, key=lambda item: item.latest_score, reverse=True)[:10]:
            lines.append(
                f"- {entry.symbol}/{entry.coin_id}: requested={event_watchlist.requested_state_value(entry)} "
                f"final={event_watchlist.final_state_value(entry)} "
                f"level={entry.opportunity_level or 'unknown'} "
                f"path={entry.impact_path_type or 'unknown'} "
                f"score={entry.opportunity_score_final if entry.opportunity_score_final is not None else 'n/a'} "
                f"block={entry.quality_state_block_reason or 'quality_state_capped'}"
            )
    else:
        lines.append("- None.")
    lines.extend(["", "### Research Cards"])
    cards = [Path(path) for path in card_paths]
    if cards:
        grouped_cards = _card_groups_for_daily_brief(cards)
        for group_name in event_research_cards.CARD_INDEX_GROUPS:
            paths = grouped_cards.get(group_name, [])
            if group_name == "Diagnostic / Source-Noise / Control Cards" and not include_diagnostics:
                lines.append(f"#### {group_name}")
                hidden_count = len(paths)
                lines.append(
                    f"- Hidden from main card list by default: cards={hidden_count}, "
                    f"diagnostics={diagnostic_core_rows}, quality_capped_support={diagnostic_capped_rows}"
                )
                continue
            lines.append(f"#### {group_name}")
            if not paths:
                lines.append("- None.")
                continue
            collapsed_paths = event_research_cards.collapse_card_paths_for_group(
                paths,
                group_name=group_name,
                card_groups=grouped_cards,
            )
            for path, hidden_count in collapsed_paths[:20]:
                target = event_research_cards.card_feedback_target(path)
                suffix = f" · feedback target: `{target}`" if target else ""
                if hidden_count:
                    suffix += f" · +{hidden_count} related diagnostic/support card(s) hidden"
                display_path = event_artifact_paths.artifact_display_path(path)
                lines.append(f"- [{path.name}]({display_path}) · group: {group_name}{suffix}")
            if len(collapsed_paths) > 20:
                lines.append(f"- +{len(collapsed_paths) - 20} more card families")
    else:
        lines.append("- No cards written for this brief.")
    lines.extend(["", "### Missed Opportunities"])
    if missed:
        for row in sorted(missed, key=lambda item: abs(_float(item.get("return_pct"))), reverse=True)[:5]:
            lines.append(f"- {row.get('symbol') or row.get('coin_id')}: {row.get('move_window')} {row.get('return_pct')} stage={row.get('failure_stage')}")
    else:
        lines.append("- No missed-opportunity rows found.")
    lines.extend(["", "### Source Reliability"])
    lines.append(_compact(event_source_reliability.format_source_reliability_report(
        alerts,
        feedback_rows=feedback,
        missed_rows=missed,
        run_rows=runs[:10],
    )))
    lines.extend(["", "### Calibration Recommendations"])
    lines.append(_compact(event_alpha_calibration.format_calibration_report(
        alerts,
        feedback_rows=feedback,
        missed_rows=missed,
    )))
    lines.extend(["", "### Top Suppression Reasons"])
    lines.extend(_suppression_lines(decisions, entries))
    if core_alertable_count <= 0:
        lines.extend(["", "### Why No Alerts"])
        lines.append(_compact(event_alpha_explain.format_last_run_explanation(
            runs,
            alert_rows=alerts,
            requested_profile=requested_profile,
            artifact_namespace=artifact_namespace,
            include_test_artifacts=include_test_artifacts,
            include_legacy_artifacts=include_legacy_artifacts,
        )))
    elif alertable and include_diagnostics:
        lines.extend(["", "### Raw Pre-Policy Route Attempts / Diagnostics"])
        lines.append("- These rows were generated before canonical core/live-confirmation policy and are not proof of sent alerts.")
        for decision in alertable[:8]:
            lines.append(f"- {decision.entry.symbol}/{decision.entry.coin_id}: {decision.reason}")
    else:
        lines.extend(["", "### Why Alertable Core Routes Exist"])
        lines.append("- Canonical core opportunities passed final quality and live-confirmation gates; no raw pre-policy route text is shown by default.")
    return _strip_sensitive("\n".join(lines).rstrip() + "\n")


def write_daily_brief(
    path: str | Path,
    *,
    markdown: str,
    card_paths: Iterable[Path] = (),
) -> EventAlphaDailyBriefResult:
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    clean = _strip_sensitive(markdown)
    target.write_text(clean, encoding="utf-8")
    return EventAlphaDailyBriefResult(path=target, markdown=clean, cards=tuple(Path(p) for p in card_paths))


def format_daily_brief_result(result: EventAlphaDailyBriefResult) -> str:
    return "\n".join([
        "=" * 76,
        "EVENT ALPHA DAILY BRIEF WRITTEN (research artifact only)",
        "=" * 76,
        f"path: {event_artifact_paths.artifact_display_path(result.path)}",
        f"cards_linked: {len(result.cards)}",
        "No live RSI alerts, paper trades, live DB rows, or execution were changed.",
    ])


def _compact(report: str) -> str:
    lines = [line for line in str(report or "").splitlines() if line and not line.startswith("=")]
    return "\n".join(f"> {line}" for line in lines[:20])


def _burn_in_readiness_lines(
    *,
    latest: Mapping[str, Any],
    core_opportunities: Iterable[Any],
    card_paths: Iterable[Path],
    evidence_acquisition_rows: Iterable[Mapping[str, Any]],
    provider_health_rows: Mapping[str, Mapping[str, Any]],
    requested_profile: str | None,
) -> list[str]:
    cores = list(core_opportunities)
    cards = [Path(path) for path in card_paths if Path(path).name != "index.md"]
    feedback_targets = sum(1 for path in cards if event_research_cards.card_feedback_target(path))
    acquisition = [dict(row) for row in evidence_acquisition_rows if isinstance(row, Mapping)]
    accepted = sum(
        1 for row in acquisition
        if int(row.get("accepted_evidence_count") or 0) > 0
        or str(row.get("acquisition_status") or row.get("status") or "") in {
            "accepted_evidence_found",
            "accepted",
        }
    )
    send_requested = bool(latest.get("send_requested")) if latest else False
    sent = bool(latest.get("sent")) if latest else False
    delivered = int(latest.get("send_items_delivered") or latest.get("deliveries_delivered") or 0) if latest else 0
    no_send = bool(latest) and not send_requested and not sent and delivered <= 0
    health_rows = list((provider_health_rows or {}).values())
    backoff = sum(1 for row in health_rows if row.get("disabled_until"))
    degraded = sum(1 for row in health_rows if int(row.get("consecutive_failures") or 0) > 0 or row.get("last_error_safe"))
    provider_fetches = int(latest.get("provider_fetch_count") or 0) if latest else 0
    provider_hits = int(latest.get("provider_cache_hits") or 0) if latest else 0
    provider_misses = int(latest.get("provider_cache_misses") or 0) if latest else 0
    warnings = [str(item) for item in (latest.get("warnings") or []) if str(item)] if latest else []
    keys_missing = [item for item in warnings if "missing" in item.lower() or "disabled" in item.lower()]
    return [
        f"- Burn-in mode: {'no-send' if no_send else 'send-capable or unknown'} "
        f"(profile={requested_profile or latest.get('profile') or 'latest'})",
        f"- Provider coverage: health_rows={len(health_rows)} degraded={degraded} backoff={backoff} "
        f"fetches={provider_fetches} cache_hits={provider_hits} cache_misses={provider_misses}",
        f"- Opportunities found: core={len(cores)} high_priority={sum(1 for item in cores if getattr(item, 'is_high_priority', False))} "
        f"watchlist={sum(1 for item in cores if getattr(item, 'is_watchlist', False))}",
        f"- Evidence acquisition: rows={len(acquisition)} accepted={accepted}",
        f"- Feedback targets: cards_with_targets={feedback_targets}/{len(cards)}",
        "- What to review manually: provider gaps, source-pack evidence absence, core opportunity cards, near-miss rows, and feedback targets.",
        "- Missing keys/providers: "
        + ("; ".join(keys_missing[:5]) if keys_missing else "see provider readiness/status report for configured vs missing sources."),
    ]


def _system_health_summary_lines(latest: Mapping[str, Any]) -> list[str]:
    if not latest:
        return ["- No run ledger rows found; detailed diagnostics below."]
    return [
        f"- Latest run: {latest.get('run_id') or 'unknown'}",
        f"- Success: {str(bool(latest.get('success'))).lower()}",
        f"- Routed / alertable / sent: {int(latest.get('routed') or 0)} / "
        f"{int(latest.get('alertable') or 0)} / {str(bool(latest.get('sent'))).lower()}",
        f"- Catalyst frames analyzed / validated: "
        f"{int(latest.get('catalyst_frames_analyzed') or latest.get('catalyst_frame_rows') or 0)} / "
        f"{int(latest.get('catalyst_frame_validations') or latest.get('catalyst_frame_validations_applied') or 0)}",
        "- Detailed provider, budget, routing, and quality diagnostics are in the appendix below.",
    ]


def _near_miss_daily_lines(
    near_misses: Iterable[event_near_miss.EventNearMissCandidate],
    *,
    limit: int,
) -> list[str]:
    raw_rows = list(near_misses)
    rows = _dedupe_near_miss_candidates(raw_rows)
    if not rows:
        return ["- None."]
    lines: list[str] = []
    for item in rows[:limit]:
        interesting = _near_miss_interest(item)
        missing = _friendly_reason_list(item.missing_evidence) or "none"
        upgrade = _friendly_action_list(item.recommended_refresh_actions) or "operator review"
        invalidate = _near_miss_invalidation(item)
        lines.append(
            f"- {item.symbol}/{item.coin_id}: {interesting} "
            f"Score {item.opportunity_score_before:.0f}"
            + (
                f"->{item.opportunity_score_after:.0f}"
                if item.opportunity_score_after is not None
                and round(item.opportunity_score_after, 2) != round(item.opportunity_score_before, 2)
                else ""
            )
            + f", level={_friendly_level(item.opportunity_level_before)}"
            + (
                f"->{_friendly_level(item.opportunity_level_after)}"
                if item.opportunity_level_after
                and item.opportunity_level_after != item.opportunity_level_before
                else ""
            )
            + "."
        )
        lines.append(f"  missing: {missing}")
        lines.append(f"  would upgrade: {upgrade}")
        if item.market_refresh_attempted or item.refresh_upgrade_status:
            lines.append(
                "  targeted market refresh: "
                f"{str(item.market_refresh_success).lower()} "
                f"provider={item.market_refresh_provider or item.market_context_source or 'unknown'} "
                f"market={item.market_confirmation_before if item.market_confirmation_before is not None else 'n/a'}"
                f"->{item.market_confirmation_after if item.market_confirmation_after is not None else 'n/a'} "
                f"status={item.refresh_upgrade_status or item.upgrade_reason or item.no_upgrade_reason or 'pending'}"
            )
        lines.append(f"  would invalidate: {invalidate}")
    hidden_duplicates = max(0, len(raw_rows) - len(rows))
    if hidden_duplicates:
        lines.append(f"- +{hidden_duplicates} related duplicate/support near-miss row(s) hidden")
    if len(rows) > limit:
        lines.append(f"- +{len(rows) - limit} more near-miss candidate families")
    return lines


def _near_miss_diagnostic_lines(
    near_misses: Iterable[event_near_miss.EventNearMissCandidate],
    *,
    limit: int,
) -> list[str]:
    raw_rows = list(near_misses)
    rows = _dedupe_near_miss_candidates(raw_rows)
    if not rows:
        return ["- None."]
    lines: list[str] = []
    for item in rows[:limit]:
        refresh = (
            f"market_refresh={str(item.market_refresh_attempted).lower()}/"
            f"{str(item.market_refresh_success).lower()}"
        )
        lines.append(
            f"- {item.symbol}/{item.coin_id}: score={item.opportunity_score_before:.0f} "
            f"level={item.opportunity_level_before}->{item.opportunity_level_after or item.opportunity_level_before} "
            f"route={item.final_route_before or 'unknown'}->{item.final_route_after or item.final_route_before or 'unknown'} "
            f"raw_missing={', '.join(item.missing_evidence[:4]) or 'none'}; "
            f"actions={', '.join(item.recommended_refresh_actions[:4]) or 'operator_review'}; {refresh}"
            f" provider={item.market_refresh_provider or item.market_context_source or 'unknown'}"
            f" upgrade_status={item.refresh_upgrade_status or item.upgrade_reason or item.no_upgrade_reason or 'pending'}"
        )
    hidden_duplicates = max(0, len(raw_rows) - len(rows))
    if hidden_duplicates:
        lines.append(f"- +{hidden_duplicates} related duplicate/support diagnostic row(s) hidden")
    return lines


def _dedupe_near_miss_candidates(
    rows: Iterable[event_near_miss.EventNearMissCandidate],
) -> list[event_near_miss.EventNearMissCandidate]:
    grouped: dict[tuple[str, str], event_near_miss.EventNearMissCandidate] = {}
    for item in rows:
        key = (
            event_core_opportunities.asset_key_for_values(item.coin_id, item.symbol),
            _impact_family(getattr(item, "impact_path_type", None) or getattr(item, "playbook_type", None) or ""),
        )
        current = grouped.get(key)
        if current is None or item.opportunity_score_before > current.opportunity_score_before:
            grouped[key] = item
    return sorted(grouped.values(), key=lambda item: item.opportunity_score_before, reverse=True)


def _decision_family_key(decision: event_alpha_router.EventAlphaRouteDecision) -> tuple[str, str]:
    entry = decision.entry
    components = entry.latest_score_components or {}
    return (
        event_core_opportunities.asset_key_for_values(entry.coin_id, entry.symbol),
        _impact_family(components.get("impact_path_type") or entry.impact_path_type or entry.latest_playbook_type or ""),
    )


def _entry_family_key(entry: event_watchlist.EventWatchlistEntry) -> tuple[str, str]:
    components = entry.latest_score_components or {}
    return (
        event_core_opportunities.asset_key_for_values(entry.coin_id, entry.symbol),
        _impact_family(components.get("impact_path_type") or entry.impact_path_type or entry.latest_playbook_type or ""),
    )


def _dedupe_watchlist_entries(
    rows: Iterable[event_watchlist.EventWatchlistEntry],
) -> list[event_watchlist.EventWatchlistEntry]:
    grouped: dict[tuple[str, str], event_watchlist.EventWatchlistEntry] = {}
    for entry in rows:
        key = _entry_family_key(entry)
        current = grouped.get(key)
        if current is None or entry.latest_score > current.latest_score:
            grouped[key] = entry
    return sorted(grouped.values(), key=lambda item: item.latest_score, reverse=True)


def _impact_family(value: object) -> str:
    text = str(value or "").casefold()
    if any(token in text for token in ("fan", "sports", "world_cup", "world cup")):
        return "fan_token"
    if any(token in text for token in ("proxy", "preipo", "pre-ipo", "rwa", "venue_value", "tokenized")):
        return "proxy"
    if "listing" in text or "exchange" in text:
        return "listing"
    if "unlock" in text or "supply" in text:
        return "supply"
    if "security" in text or "exploit" in text:
        return "security"
    if "insufficient" in text or not text:
        return "unknown"
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_") or "unknown"


def _source_coverage_summary_lines(
    rows: Iterable[Mapping[str, Any] | object],
    near_misses: Iterable[event_near_miss.EventNearMissCandidate],
    upgrade_candidates: Iterable[event_near_miss.EventNearMissCandidate],
    *,
    acquisition_rows: Iterable[Mapping[str, Any]] = (),
    source_coverage_report_path: str | Path | None = None,
) -> list[str]:
    coverage = _load_source_coverage_json(source_coverage_report_path)
    if coverage:
        return _source_coverage_json_summary_lines(coverage, source_coverage_report_path=source_coverage_report_path)
    row_maps = [_row_mapping(row) for row in rows]
    row_maps = [row for row in row_maps if row]
    summary = event_source_registry.format_source_coverage_summary(row_maps)
    near = list(near_misses)
    upgrades = list(upgrade_candidates)
    gaps = [item for item in (*near, *upgrades) if item.source_coverage_gap]
    planned = [item for item in (*near, *upgrades) if item.evidence_acquisition_plan]
    planned_attempted = [item for item in (*near, *upgrades) if item.evidence_acquisition_attempted]
    executed_rows = [dict(row) for row in acquisition_rows if isinstance(row, Mapping)]
    provider_queries = sum(
        int(row.get("queries_executed") or row.get("evidence_acquisition_queries_executed") or 0)
        for row in executed_rows
    )
    accepted = sum(
        1 for row in executed_rows
        if str(row.get("status") or "") == event_evidence_acquisition.EvidenceAcquisitionStatus.ACCEPTED_EVIDENCE_FOUND.value
        or bool(row.get("accepted_evidence"))
    )
    no_results = sum(
        1 for row in executed_rows
        if str(row.get("status") or "") == event_evidence_acquisition.EvidenceAcquisitionStatus.NO_RESULTS.value
    )
    rejected_only = sum(
        1 for row in executed_rows
        if str(row.get("status") or "") == event_evidence_acquisition.EvidenceAcquisitionStatus.REJECTED_RESULTS_ONLY.value
    )
    accepted_by_source_class: dict[str, int] = {}
    article_quality_counts: dict[str, int] = {}
    for row in executed_rows:
        evidence_items = (*_evidence_items(row.get("accepted_evidence")), *_evidence_items(row.get("rejected_evidence_samples") or row.get("rejected_evidence")))
        accepted_items = _evidence_items(row.get("accepted_evidence"))
        for evidence in accepted_items:
            source_class = str(evidence.get("source_class") or "unknown")
            accepted_by_source_class[source_class] = accepted_by_source_class.get(source_class, 0) + 1
        for evidence in evidence_items:
            enrichment = evidence.get("source_enrichment") if isinstance(evidence.get("source_enrichment"), Mapping) else {}
            status = str(enrichment.get("article_quality_status") or "").strip()
            if status:
                article_quality_counts[status] = article_quality_counts.get(status, 0) + 1
    accepted_source_text = ", ".join(
        f"{source_class}={count}"
        for source_class, count in sorted(accepted_by_source_class.items(), key=lambda item: (-item[1], item[0]))
    ) or "none"
    article_quality_text = ", ".join(
        f"{status}={count}"
        for status, count in sorted(article_quality_counts.items(), key=lambda item: (-item[1], item[0]))
    ) or "none"
    next_source = _source_coverage_next_source(gaps, executed_rows)
    report_path = Path(source_coverage_report_path) if source_coverage_report_path else None
    report_status = "not written yet"
    if report_path is not None:
        report_label = event_artifact_paths.artifact_display_path(report_path)
        report_status = report_label if report_path.exists() else f"{report_label} (not written yet)"
    return [
        f"- Detailed source coverage report: {report_status}",
        f"- Source registry: {summary}",
        (
            "- Evidence acquisition funnel: "
            f"evidence_plans_created={len(planned) or len(planned_attempted)}, "
            f"llm_evidence_plans_created={len(planned)}, "
            f"acquisition_requests_executed={len(executed_rows)}, "
            f"deterministic_acquisition_requests_executed={len(executed_rows)}, "
            f"provider_queries_executed={provider_queries}, "
            f"accepted_evidence_found={accepted}, "
            f"no_results={no_results}, "
            f"rejected_only={rejected_only}"
        ),
        f"- Accepted evidence by source class: {accepted_source_text}",
        f"- Source enrichment article quality: {article_quality_text}",
        f"- Source coverage gaps: {len(gaps)} candidate(s) need healthier or more specific source coverage.",
        f"- What data source would most improve next run: {next_source}",
        *_source_activation_plan_lines(source_coverage_report_path),
        "- Evidence absence rule: broad/degraded RSS/GDELT/Polymarket gaps are not treated as strong negative proof.",
    ]


def _source_coverage_json_summary_lines(
    coverage: Mapping[str, Any],
    *,
    source_coverage_report_path: str | Path | None,
) -> list[str]:
    report_path = Path(source_coverage_report_path) if source_coverage_report_path else None
    json_path = _source_coverage_json_path(source_coverage_report_path)
    report_status = "not written yet"
    if report_path is not None:
        report_label = event_artifact_paths.artifact_display_path(report_path)
        report_status = report_label if report_path.exists() else f"{report_label} (not written yet)"
    lines = [
        f"- Detailed source coverage report: {report_status}",
        (
            "- CryptoPanic effective coverage: "
            f"configured={str(bool(coverage.get('cryptopanic_configured'))).lower()} "
            f"status={coverage.get('cryptopanic_health_status') or 'unknown'} "
            f"coverage={coverage.get('cryptopanic_coverage_status') or 'unknown'} "
            f"observed={str(bool(coverage.get('cryptopanic_observed'))).lower()} "
            f"successful_requests={int(coverage.get('cryptopanic_successful_requests') or 0)} "
            f"failed_requests={int(coverage.get('cryptopanic_failed_requests') or 0)} "
            f"accepted={int(coverage.get('cryptopanic_accepted_evidence') or 0)} "
            f"rejected={int(coverage.get('cryptopanic_rejected_evidence') or 0)} "
            f"stale_backoff_reconciled={str(bool(coverage.get('cryptopanic_backoff_reconciled_after_success'))).lower()}"
        ),
    ]
    recommendation = str(coverage.get("cryptopanic_recommendation") or "none")
    if recommendation and recommendation != "none":
        lines.append(f"- CryptoPanic recommendation: {recommendation}")
    packs = [pack for pack in coverage.get("packs") or [] if isinstance(pack, Mapping)]
    blocked = sum(int(pack.get("candidates_blocked_by_coverage_gap") or 0) for pack in packs)
    accepted = sum(int(pack.get("accepted_evidence_count") or 0) for pack in packs)
    rejected_only = sum(int(pack.get("rejected_only_count") or 0) for pack in packs)
    skipped_budget = sum(int(pack.get("skipped_budget_count") or 0) for pack in packs)
    provider_unavailable = sum(int(pack.get("provider_unavailable_count") or 0) for pack in packs)
    lines.append(
        "- Evidence acquisition funnel: "
        f"acquisition_requests_executed={int(coverage.get('acquisition_rows') or 0)}, "
        f"accepted_evidence_found={accepted}, "
        f"rejected_only={rejected_only}, "
        f"skipped_budget={skipped_budget}, "
        f"provider_unavailable={provider_unavailable}"
    )
    lines.append(f"- Source coverage gaps: {blocked} candidate(s) need healthier or more specific source coverage.")
    next_source = _source_coverage_json_next_source(packs, coverage)
    lines.append(f"- What data source would most improve next run: {next_source}")
    lines.append(
        "- Source coverage JSON: "
        + (event_artifact_paths.artifact_display_path(json_path) if json_path and json_path.exists() else "not written yet")
    )
    lines.extend(_source_activation_plan_lines(source_coverage_report_path, coverage=coverage))
    lines.append("- Evidence absence rule: broad/degraded RSS/GDELT/Polymarket gaps are not treated as strong negative proof.")
    return lines


def _source_activation_plan_lines(
    source_coverage_report_path: str | Path | None,
    *,
    coverage: Mapping[str, Any] | None = None,
) -> list[str]:
    base = Path(source_coverage_report_path).parent if source_coverage_report_path is not None else None
    readiness_md = base / event_alpha_source_coverage.LIVE_PROVIDER_READINESS_MD if base is not None else None
    readiness_label = (
        event_artifact_paths.artifact_display_path(readiness_md)
        if readiness_md is not None
        else event_alpha_source_coverage.LIVE_PROVIDER_READINESS_MD
    )
    priorities = []
    if coverage is not None:
        priorities = [item for item in coverage.get("category_priorities") or [] if isinstance(item, Mapping)]
    if not priorities:
        priorities = list(event_alpha_source_coverage.SOURCE_COVERAGE_CATEGORY_PRIORITIES)
    top = []
    for item in priorities[:3]:
        category = str(item.get("category") or "").strip()
        providers = item.get("providers") or ()
        if category:
            top.append(f"{category} ({', '.join(str(provider) for provider in providers if str(provider)) or 'providers TBD'})")
    lines = [
        f"- Live-provider activation readiness: {readiness_label}",
        "- Recommended next activation order: " + ("; ".join(top) if top else "none"),
    ]
    if base is not None:
        coinalyze_json = base / event_coinalyze_preflight.PREFLIGHT_JSON
        coinalyze_md = base / event_coinalyze_preflight.PREFLIGHT_MD
        coverage_preflight_status = str((coverage or {}).get("coinalyze_preflight_status") or "")
        coverage_rehearsal_status = str((coverage or {}).get("coinalyze_rehearsal_status") or "")
        coverage_rehearsal_path = str((coverage or {}).get("coinalyze_rehearsal_report_path") or "")
        coverage_ledger_path = str((coverage or {}).get("coinalyze_request_ledger_path") or "")
        if coinalyze_json.exists() and coinalyze_md.exists():
            try:
                payload = json.loads(coinalyze_json.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = {}
            status = coverage_preflight_status or str(payload.get("preflight_status") or "unreadable")
            lines.append(
                "- Coinalyze preflight: "
                f"{status} ({event_artifact_paths.artifact_display_path(coinalyze_md)})"
            )
        else:
            namespace = str((coverage or {}).get("artifact_namespace") or Path(base).name)
            profile = str((coverage or {}).get("profile") or "notify_llm_deep")
            lines.append(
                "- Coinalyze preflight: not generated "
                f"(command: make event-alpha-coinalyze-preflight ARTIFACT_NAMESPACE={namespace} PROFILE={profile} PYTHON=python3)"
            )
        if coverage_rehearsal_status and coverage_rehearsal_status != "not_generated":
            detail = f" ({coverage_rehearsal_path})" if coverage_rehearsal_path else ""
            ledger = f" ledger={coverage_ledger_path}" if coverage_ledger_path else ""
            lines.append(f"- Coinalyze rehearsal: {coverage_rehearsal_status}{detail}{ledger}")
        else:
            lines.append("- Coinalyze rehearsal: not generated")
    if readiness_md is None or not readiness_md.exists():
        lines.append("- Readiness command: make event-alpha-live-provider-readiness PROFILE=notify_llm_deep")
    return lines


def _source_coverage_json_next_source(packs: Iterable[Mapping[str, Any]], coverage: Mapping[str, Any]) -> str:
    candidates: list[tuple[int, str, str]] = []
    for pack in packs:
        actions = pack.get("recommended_actions")
        action_text = "; ".join(str(item) for item in actions[:2]) if isinstance(actions, list) else ""
        if not action_text:
            continue
        # If CryptoPanic is already observed healthy, avoid recommending it as
        # the "missing" next source. The pack action may still mention another
        # corroborating source, which remains useful.
        if (
            bool(coverage.get("cryptopanic_successful_requests"))
            and "cryptopanic" in action_text.casefold()
            and not any(
                token in action_text.casefold()
                for token in ("official", "sports", "coinalyze", "tokenomist", "binance", "bybit", "defillama")
            )
        ):
            continue
        priority = int(pack.get("candidates_blocked_by_coverage_gap") or 0)
        if priority <= 0:
            priority = int(pack.get("skipped_budget_count") or 0) + int(pack.get("provider_unavailable_count") or 0)
        candidates.append((priority, str(pack.get("source_pack") or "unknown"), action_text))
    if not candidates:
        return "none; current source-pack evidence is not the main blocker"
    _, pack_name, action = sorted(candidates, key=lambda item: (-item[0], item[1]))[0]
    return f"{pack_name}: {action}"


def _load_source_coverage_json(source_coverage_report_path: str | Path | None) -> Mapping[str, Any]:
    path = _source_coverage_json_path(source_coverage_report_path)
    if path is None or not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, Mapping) else {}


def _source_coverage_json_path(source_coverage_report_path: str | Path | None) -> Path | None:
    if source_coverage_report_path is None:
        return None
    path = Path(source_coverage_report_path)
    if path.suffix == ".json":
        return path
    return path.with_suffix(".json")


def _source_coverage_next_source(
    gaps: Iterable[event_near_miss.EventNearMissCandidate],
    acquisition_rows: Iterable[Mapping[str, Any]],
) -> str:
    pack_counts: dict[str, int] = {}
    for item in gaps:
        pack = str(item.source_pack or "market_anomaly_pack")
        pack_counts[pack] = pack_counts.get(pack, 0) + 1
    for row in acquisition_rows:
        status = str(row.get("status") or "")
        if status not in {"skipped_budget", "no_results", "rejected_results_only", "provider_unavailable", "provider_backoff", "failed_soft"}:
            continue
        pack = str(row.get("source_pack") or "market_anomaly_pack")
        pack_counts[pack] = pack_counts.get(pack, 0) + 1
    if not pack_counts:
        return "none; current source-pack evidence is not the main blocker"
    pack = sorted(pack_counts, key=lambda key: (-pack_counts[key], key))[0]
    suggestions = {
        "proxy_preipo_rwa_pack": "CryptoPanic tagged token news or official project source",
        "strategic_investment_pack": "CryptoPanic/official project confirmation plus DefiLlama protocol metrics",
        "security_shock_pack": "CryptoPanic tagged exploit coverage or official project update",
        "listing_liquidity_pack": "official Binance/Bybit exchange announcement",
        "fan_sports_pack": "sports fixture plus fan-token/project source",
        "market_anomaly_pack": "CryptoPanic tagged catalyst, official exchange/project source, or DefiLlama metrics",
        "unlock_supply_pack": "Tokenomist/structured unlock source",
        "perp_listing_squeeze_pack": "official perp listing plus Coinalyze OI/funding",
    }
    return suggestions.get(pack, f"{pack} source-pack evidence")


def _evidence_items(value: object) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, Mapping):
        return (value,)
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return tuple(item for item in value if isinstance(item, Mapping))
    return ()


def _provider_health_by_pack_lines(
    provider_health_rows: Mapping[str, Mapping[str, Any]],
    *,
    source_coverage_report_path: str | Path | None = None,
) -> list[str]:
    coverage = _load_source_coverage_json(source_coverage_report_path)
    if coverage:
        packs = [pack for pack in coverage.get("packs") or [] if isinstance(pack, Mapping)]
        if not packs:
            return ["- Source coverage JSON had no pack rows."]
        lines: list[str] = []
        for pack in packs:
            lines.append(
                f"- {pack.get('source_pack') or 'unknown'}: "
                f"coverage={pack.get('provider_coverage_status') or pack.get('source_pack_coverage_status') or 'unknown'} "
                f"healthy={_join_json_values(pack.get('healthy_providers'))} "
                f"unknown={_join_json_values(pack.get('unknown_or_unobserved_providers'))} "
                f"degraded={_join_json_values(pack.get('degraded_or_backoff_providers'))} "
                f"missing={_join_json_values(pack.get('missing_providers'))} "
                f"blocked={int(pack.get('candidates_blocked_by_coverage_gap') or 0)}"
            )
        return lines
    if not provider_health_rows:
        return ["- No provider health rows found."]
    lines: list[str] = []
    for pack_name in event_source_packs.source_pack_names():
        pack = event_source_packs.get_source_pack(pack_name)
        statuses: list[str] = []
        for provider in pack.preferred_providers[:5]:
            row = provider_health_rows.get(provider) or provider_health_rows.get(provider.replace("_announcements", ""))
            status = "unknown"
            if isinstance(row, Mapping):
                status = str(row.get("coverage_status") or row.get("status") or row.get("ready") or "unknown")
            statuses.append(f"{provider}={status}")
        lines.append(f"- {pack.name}: " + ", ".join(statuses))
    return lines


def _join_json_values(value: object) -> str:
    if isinstance(value, str):
        return value or "none"
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, Mapping)):
        items = [str(item) for item in value if str(item)]
        return ", ".join(items) if items else "none"
    return "none"


def _evidence_acquisition_result_lines(
    candidates: Iterable[event_near_miss.EventNearMissCandidate],
    *,
    acquisition_rows: Iterable[Mapping[str, Any]] = (),
    core_opportunities: Iterable[event_core_opportunities.CoreOpportunity] = (),
    limit: int,
) -> list[str]:
    executed = [dict(row) for row in acquisition_rows if isinstance(row, Mapping)]
    core_by_id = {
        item.core_opportunity_id: item
        for item in core_opportunities
        if item.core_opportunity_id
    }
    if executed:
        lines: list[str] = []
        status_counts: dict[str, int] = {}
        for row in executed:
            status = str(row.get("status") or "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        lines.append(
            "- Executed source-pack searches: "
            + ", ".join(f"{key}={value}" for key, value in sorted(status_counts.items()))
        )
        for row in executed[:limit]:
            accepted = row.get("accepted_evidence") if isinstance(row.get("accepted_evidence"), list) else ()
            rejected = row.get("rejected_evidence_samples") if isinstance(row.get("rejected_evidence_samples"), list) else ()
            core = core_by_id.get(str(row.get("core_opportunity_id") or ""))
            core_row = core.primary_row if core is not None else {}
            canonical_level = (
                core_row.get("final_opportunity_level")
                or (core.opportunity_level if core is not None else None)
                or row.get("final_opportunity_level")
                or row.get("opportunity_level_after")
                or "unknown"
            )
            canonical_source = core_row.get("final_verdict_source") or row.get("final_verdict_source") or "canonical_core"
            lines.append(
                f"- {row.get('symbol') or row.get('coin_id') or row.get('hypothesis_id') or 'UNKNOWN'}: "
                f"pack={row.get('source_pack') or 'unknown'} status={row.get('status') or 'unknown'} "
                f"accepted={len(accepted or ())} rejected={len(rejected or ())} "
                f"score={row.get('opportunity_score_before')}->{row.get('opportunity_score_after')} "
                f"evidence={row.get('acquisition_evidence_status') or 'unknown'} "
                f"final={row.get('final_upgrade_status') or row.get('acquisition_upgrade_status') or 'unchanged'} "
                f"verdict={canonical_level} "
                f"source={canonical_source}"
            )
        if len(executed) > limit:
            lines.append(f"- +{len(executed) - limit} more acquisition rows in local artifacts")
        return lines
    rows = [item for item in candidates if item.evidence_acquisition_attempted or item.evidence_acquisition_results]
    if not rows:
        return ["- None."]
    lines: list[str] = []
    for item in rows[:limit]:
        plan = item.evidence_acquisition_plan or {}
        queries = plan.get("evidence_query_plan") if isinstance(plan, Mapping) else ()
        needed = plan.get("evidence_needed") if isinstance(plan, Mapping) else ()
        lines.append(
            f"- {item.symbol}/{item.coin_id}: pack={item.source_pack or 'unknown'} "
            f"queries={len(queries) if isinstance(queries, Iterable) and not isinstance(queries, (str, bytes, Mapping)) else 0} "
            f"needed={'; '.join(str(value) for value in list(needed or ())[:3]) or 'none'} "
            f"result={item.upgrade_reason or item.no_upgrade_reason or item.refresh_upgrade_status or 'planned'}"
        )
    if len(rows) > limit:
        lines.append(f"- +{len(rows) - limit} more evidence acquisition candidates")
    return lines


def _coverage_blocked_candidate_lines(
    candidates: Iterable[event_near_miss.EventNearMissCandidate],
    *,
    limit: int,
) -> list[str]:
    rows = [item for item in candidates if item.source_coverage_gap or item.provider_coverage_status in {"degraded", "unavailable", "not_configured", "partial"}]
    if not rows:
        return ["- None."]
    lines: list[str] = []
    for item in rows[:limit]:
        lines.append(
            f"- {item.symbol}/{item.coin_id}: pack={item.source_pack or 'unknown'} "
            f"coverage={item.provider_coverage_status or 'unknown'} gap={item.source_coverage_gap or 'source_specificity_gap'} "
            f"absence_meaningful={str(bool(item.evidence_absence_is_meaningful)).lower()}"
        )
    if len(rows) > limit:
        lines.append(f"- +{len(rows) - limit} more coverage-blocked candidates")
    return lines


def _friendly_reason(reason: object) -> str:
    return event_alpha_reason_text.humanize_event_alpha_reason(reason)


def _friendly_reason_list(reasons: Iterable[object]) -> str:
    translated = [_friendly_reason(reason) for reason in reasons]
    translated = [reason for reason in translated if reason]
    return "; ".join(dict.fromkeys(translated[:5]))


def _friendly_action(action: object) -> str:
    return event_alpha_reason_text.humanize_event_alpha_action(action)


def _friendly_action_list(actions: Iterable[object]) -> str:
    translated = [_friendly_action(action) for action in actions]
    translated = [action for action in translated if action]
    return "; ".join(dict.fromkeys(translated[:5]))


def _friendly_level(level: object) -> str:
    return str(level or "unknown").replace("_", " ")


def _near_miss_interest(item: event_near_miss.EventNearMissCandidate) -> str:
    missing_text = " ".join(item.missing_evidence).casefold()
    if "cause_unknown_market_dislocation" in missing_text:
        return "token moved, but the cause is still unknown."
    if "generic_cooccurrence_only" in missing_text:
        return "source evidence mentions the token and catalyst together, but the impact mechanism is not proven."
    if item.opportunity_score_before >= 60:
        return "close to digest threshold but still missing confirmation."
    return "interesting enough for local research, but not ready for alert routing."


def _near_miss_invalidation(item: event_near_miss.EventNearMissCandidate) -> str:
    missing_text = " ".join(item.missing_evidence).casefold()
    if "cause_unknown_market_dislocation" in missing_text:
        return "an unrelated market move, no catalyst found, or fast mean reversion."
    if "generic_cooccurrence_only" in missing_text:
        return "no direct token impact path appears after source review."
    if "market" in missing_text:
        return "price/volume reaction remains weak or fades."
    return "identity, catalyst link, or market reaction fails review."


def _card_groups_for_daily_brief(paths: Iterable[Path]) -> dict[str, list[Path]]:
    grouped: dict[str, list[Path]] = {name: [] for name in event_research_cards.CARD_INDEX_GROUPS}
    group_map = event_research_cards.card_index_group_map(paths)
    for path in paths:
        p = Path(path)
        if p.name == "index.md":
            continue
        grouped.setdefault(group_map.get(p) or event_research_cards.card_index_group(p), []).append(p)
    return grouped


def _latest_notification_run(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any] | None:
    ordered = sorted(
        (dict(row) for row in rows if isinstance(row, Mapping)),
        key=lambda row: str(row.get("started_at") or ""),
        reverse=True,
    )
    return ordered[0] if ordered else None


def _provider_health_lines(rows: Mapping[str, Mapping[str, Any]]) -> list[str]:
    if not rows:
        return ["- No provider health rows found."]
    grouped: dict[str, list[tuple[str, Mapping[str, Any]]]] = {}
    for provider, row in rows.items():
        grouped.setdefault(str(row.get("provider_kind") or "unclassified"), []).append((str(provider), row))
    lines: list[str] = []
    for group in ("event_source", "enrichment", "catalyst_search", "llm", "unclassified"):
        items = grouped.get(group)
        if not items:
            continue
        lines.append(f"- {group}:")
        for provider, row in sorted(items)[:8]:
            disabled = row.get("disabled_until") or "none"
            lines.append(
                f"  - {provider}: failures={int(row.get('consecutive_failures') or 0)} "
                f"disabled_until={disabled} last_success={row.get('last_success_at') or 'never'}"
            )
    return lines or ["- No provider health rows found."]


def _llm_budget_lines(latest: Mapping[str, Any]) -> list[str]:
    if not latest:
        return ["- No latest run row; budget usage unknown."]
    return [
        f"- Cache hits/misses: {int(latest.get('llm_cache_hits') or 0)} / {int(latest.get('llm_cache_misses') or 0)}",
        f"- Calls attempted: {int(latest.get('llm_calls_attempted') or 0)}",
        f"- Skipped due budget: {int(latest.get('llm_skipped_due_budget') or 0)}",
    ]


def _new_since_last_run_lines(runs: list[dict[str, Any]]) -> list[str]:
    if not runs:
        return ["- No run history."]
    latest = runs[0]
    previous = runs[1] if len(runs) > 1 else {}
    fields = ("raw_events", "candidates", "alerts", "watchlist_entries", "alertable")
    lines = []
    for field in fields:
        delta = int(latest.get(field) or 0) - int(previous.get(field) or 0)
        lines.append(f"- {field}: {int(latest.get(field) or 0)} ({delta:+d} vs previous)")
    return lines


def _watchlist_hotter_lines(entries: list[event_watchlist.EventWatchlistEntry]) -> list[str]:
    hot = [
        entry for entry in entries
        if entry.score_jump > 0
        or entry.derivatives_crowding_upgraded
        or entry.cluster_confidence_upgraded
        or entry.event_time_upgraded
    ]
    if not hot:
        return ["- No hotter watchlist rows found."]
    lines = []
    for entry in sorted(hot, key=lambda item: (item.score_jump, item.latest_score), reverse=True)[:5]:
        reasons = ", ".join(entry.material_change_reasons) if entry.material_change_reasons else "material update"
        lines.append(f"- {entry.symbol}/{entry.coin_id}: score={entry.latest_score} jump={entry.score_jump} reasons={reasons}")
    return lines


def _watchlist_identity_suffix(entry: event_watchlist.EventWatchlistEntry) -> str:
    components = entry.latest_score_components or {}
    parts: list[str] = []
    asset_kind = components.get("asset_kind")
    role_source = components.get("role_source")
    collision = components.get("collision_risk")
    if asset_kind:
        parts.append(f"asset_kind={asset_kind}")
    if role_source:
        parts.append(f"role_source={role_source}")
    if collision:
        parts.append(f"collision={collision}")
    return " " + " ".join(parts) if parts else ""


def _suppression_lines(
    decisions: list[event_alpha_router.EventAlphaRouteDecision],
    entries: list[event_watchlist.EventWatchlistEntry],
) -> list[str]:
    counts: dict[str, int] = {}
    for decision in decisions:
        if event_alpha_router.alertable_after_quality_gate(decision):
            continue
        counts[decision.reason] = counts.get(decision.reason, 0) + 1
    for entry in entries:
        if entry.suppressed_reason:
            counts[entry.suppressed_reason] = counts.get(entry.suppressed_reason, 0) + 1
    if not counts:
        return ["- None."]
    return [f"- {reason}: {count}" for reason, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:5]]


def _core_alertable_count(core_opportunities: Iterable[event_core_opportunities.CoreOpportunity]) -> int:
    return sum(
        1 for item in core_opportunities
        if event_alpha_router.route_value_is_alertable(item.final_route_after_quality_gate)
    )


def _field_counts(rows: Iterable[Mapping[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get(field) or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return counts


def _multi_field_counts(rows: Iterable[Mapping[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        values = row.get(field) or []
        if isinstance(values, str):
            values = [values]
        for value in values:
            key = str(value or "").strip()
            if key:
                counts[key] = counts.get(key, 0) + 1
    return counts


def _format_counts(counts: Mapping[str, int]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items())) or "none"


def _brief_hypothesis_labels(rows: Iterable[Mapping[str, Any]]) -> str:
    labels: list[str] = []
    for row in rows:
        candidates = row.get("validated_candidate_assets") or row.get("crypto_candidate_assets") or row.get("suggested_candidate_assets") or []
        candidate_label = "none"
        if candidates and isinstance(candidates[0], Mapping):
            candidate_label = str(candidates[0].get("symbol") or candidates[0].get("coin_id") or "asset")
        labels.append(
            f"{row.get('impact_category') or 'unknown'}"
            f"/{row.get('external_asset') or 'unknown'}"
            f"/candidate={candidate_label}"
            f"({row.get('validation_stage') or row.get('status') or 'unknown'}"
            f",score={_float(row.get('hypothesis_score') or _float(row.get('confidence')) * 100):.0f}"
            f",v2={_float(row.get('opportunity_score_v2')):.0f}"
            f",path={row.get('impact_path_type') or 'unknown'}"
            f",main={row.get('main_frame_type') or 'unknown'}"
            f",role={row.get('candidate_role') or 'unknown'})"
        )
    return "; ".join(labels)


def _brief_decisions(rows: Iterable[event_alpha_router.EventAlphaRouteDecision]) -> str:
    labels = []
    seen: set[tuple[str, str]] = set()
    for decision in rows:
        key = _decision_family_key(decision)
        if key in seen:
            continue
        seen.add(key)
        entry = decision.entry
        components = entry.latest_score_components or {}
        final_route = event_alpha_router.final_route_value(decision)
        labels.append(
            f"{entry.symbol}/{entry.coin_id}"
            f"({event_watchlist.final_state_value(entry)},score={entry.latest_score},v2={_float(components.get('opportunity_score_v2')):.0f},"
            f"final={_float(components.get('opportunity_score_final')):.0f},"
            f"level={components.get('opportunity_level') or 'unknown'},"
            f"path={components.get('impact_path_type') or 'unknown'},role={components.get('candidate_role') or 'unknown'},"
            f"main={components.get('main_frame_type') or 'unknown'},"
            f"route={final_route},requested={decision.requested_route_before_quality_gate or decision.route.value},reason={decision.reason})"
        )
    return "; ".join(labels)


def _core_opportunity_lines(
    opportunities: Iterable[event_core_opportunities.CoreOpportunity],
    *,
    limit: int,
) -> list[str]:
    rows, collapsed_counts = _collapse_core_display_rows(opportunities)
    if not rows:
        return ["- None."]
    lines: list[str] = []
    for item in rows[:limit]:
        categories = ", ".join(item.supporting_categories[:4]) or "unknown"
        paths = ", ".join(item.supporting_impact_paths[:4]) or item.primary_impact_path
        lane = str(item.primary_row.get("opportunity_type") or "UNCLASSIFIED")
        market_state = str(item.primary_row.get("market_state_class") or item.primary_row.get("market_state") or "unknown")
        lane_reason = str(item.primary_row.get("why_now") or item.primary_row.get("opportunity_type_why_now") or "")
        diagnostics = ""
        if item.diagnostic_row_count or item.quality_capped_supporting_rows:
            diagnostics = (
                f" diagnostics_hidden={item.diagnostic_row_count}"
                f" quality_capped_support={item.quality_capped_supporting_rows}"
            )
        family_count = collapsed_counts.get(_core_display_family_key(item), 1)
        if family_count > 1:
            diagnostics += f" collapsed_family_rows={family_count - 1}"
        lines.append(
            f"- {item.core_opportunity_id} {item.symbol}/{item.coin_id}: "
            f"level={item.opportunity_level} route={item.final_route_after_quality_gate or 'local'} "
            f"state={item.final_state_after_quality_gate or 'unknown'} "
            f"score={item.opportunity_score_final:.0f} "
            f"lane={lane} market_state={market_state} "
            f"path={item.primary_impact_path} role={item.candidate_role} "
            f"asset_kind={item.asset_kind or 'unknown'} "
            f"role_source={item.role_source or 'unknown'} "
            f"collision={item.collision_risk or 'none'} "
            f"categories={categories} paths={paths}{diagnostics}"
        )
        if lane_reason:
            lines.append(f"  why_now: {lane_reason}")
        lines.append(
            f"  support: hypotheses={len(item.supporting_hypothesis_ids)} "
            f"categories={categories} impact_paths={paths} "
            f"hidden_diagnostics={item.diagnostic_row_count} "
            f"quality_capped_support={item.quality_capped_supporting_rows}"
        )
        if item.role_capabilities:
            caps = ", ".join(key for key, value in sorted(item.role_capabilities.items()) if value) or "none"
            lines.append(f"  role capabilities: {caps}")
        if item.identity_evidence:
            lines.append(f"  identity: confidence={item.identity_confidence if item.identity_confidence is not None else 'n/a'} evidence={item.identity_evidence[0]}")
        if item.role_validation_failures:
            lines.append(f"  role validation failures: {', '.join(item.role_validation_failures[:4])}")
        if item.supporting_evidence_quotes:
            lines.append(f"  evidence: {item.supporting_evidence_quotes[0]}")
        if item.why_other_rows_hidden != "no hidden supporting rows":
            lines.append(f"  collapsed: {item.why_other_rows_hidden}")
    if len(rows) > limit:
        lines.append(f"- +{len(rows) - limit} more core opportunities")
    return lines


def _collapse_core_display_rows(
    opportunities: Iterable[event_core_opportunities.CoreOpportunity],
) -> tuple[list[event_core_opportunities.CoreOpportunity], dict[tuple[str, str], int]]:
    grouped: dict[tuple[str, str], list[event_core_opportunities.CoreOpportunity]] = {}
    for item in opportunities:
        if _hide_core_from_default_display(item):
            continue
        grouped.setdefault(_core_display_family_key(item), []).append(item)
    rows: list[event_core_opportunities.CoreOpportunity] = []
    counts: dict[tuple[str, str], int] = {}
    for key, items in grouped.items():
        counts[key] = len(items)
        rows.append(sorted(items, key=_core_display_rank, reverse=True)[0])
    return rows, counts


def _core_display_rank(item: event_core_opportunities.CoreOpportunity) -> tuple[int, float, str]:
    if item.is_high_priority:
        route_rank = 5
    elif item.is_watchlist:
        route_rank = 4
    elif item.is_validated_digest:
        route_rank = 3
    elif item.alertable:
        route_rank = 2
    else:
        route_rank = 1
    return route_rank, item.opportunity_score_final, item.core_opportunity_id


def _core_display_family_key(item: event_core_opportunities.CoreOpportunity) -> tuple[str, str]:
    asset = event_core_opportunities.asset_key_for_opportunity(item)
    path = str(item.primary_impact_path or "").casefold()
    family = "proxy" if path in {"venue_value_capture", "proxy_attention", "proxy_exposure"} else path or "unknown"
    return asset, family


def _hide_core_from_default_display(item: event_core_opportunities.CoreOpportunity) -> bool:
    if str(item.symbol or "").upper() != "SECTOR":
        return False
    return not (item.alertable or item.is_high_priority or item.is_watchlist or item.is_validated_digest)


def _research_review_delivery_rows(run_ledger_path: str | Path | None) -> list[Mapping[str, Any]]:
    if run_ledger_path is None:
        return []
    path = Path(run_ledger_path).parent / "event_alpha_notification_deliveries.jsonl"
    if not path.exists():
        return []
    rows: list[Mapping[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if isinstance(row, Mapping) and str(row.get("lane") or "") == event_alpha_notifications.LANE_RESEARCH_REVIEW_DIGEST:
                rows.append(row)
    except (OSError, json.JSONDecodeError):
        return rows
    return sorted(rows, key=lambda row: str(row.get("attempted_at") or row.get("created_at") or ""), reverse=True)


def _research_review_delivery_line(row: Mapping[str, Any]) -> str:
    symbols = row.get("canonical_symbols") if isinstance(row.get("canonical_symbols"), list) else []
    coins = row.get("canonical_coin_ids") if isinstance(row.get("canonical_coin_ids"), list) else []
    core_ids = row.get("core_opportunity_ids") if isinstance(row.get("core_opportunity_ids"), list) else []
    if len(symbols) > 1:
        label = " + ".join(str(value) for value in symbols[:6])
        if len(symbols) > 6:
            label += f" +{len(symbols) - 6} more"
        coin = f"{len(coins)} coin(s)" if coins else "multiple"
        core_id = f"{len(core_ids)} core(s): " + ", ".join(str(value) for value in core_ids[:4])
    else:
        label = str(row.get("canonical_symbol") or (symbols[0] if symbols else "") or row.get("symbol") or "UNKNOWN")
        coin = str(row.get("canonical_coin_id") or (coins[0] if coins else "") or row.get("coin_id") or "unknown")
        core_id = str(row.get("core_opportunity_id") or (core_ids[0] if core_ids else "") or row.get("alert_id") or "unknown")
    state = str(row.get("delivery_state") or row.get("state") or "planned")
    mode = str(row.get("mode") or row.get("send_mode") or "")
    summary = row.get("channel_summary") if isinstance(row.get("channel_summary"), Mapping) else {}
    rendered = _int(row.get("rendered_candidate_count") or summary.get("rendered_candidate_count"))
    eligible = _int(row.get("eligible_candidate_count") or summary.get("eligible_candidate_count"))
    skipped = _int(row.get("skipped_candidate_count") or summary.get("skipped_candidate_count"))
    reason_counts = row.get("skipped_reason_counts") if isinstance(row.get("skipped_reason_counts"), Mapping) else summary.get("skipped_reason_counts") or summary.get("skip_reason_counts")
    family_summary = row.get("skipped_family_summary") if isinstance(row.get("skipped_family_summary"), list) else summary.get("skipped_family_summary")
    suffix = ""
    if eligible or rendered or skipped:
        suffix += f" candidates={rendered}/{eligible} rendered skipped={skipped}"
    if isinstance(reason_counts, Mapping) and reason_counts:
        suffix += f" skip_reasons={_format_count_map(reason_counts, limit=4)}"
    if isinstance(family_summary, list) and family_summary:
        families = []
        for family in family_summary[:3]:
            if not isinstance(family, Mapping):
                continue
            label = str(family.get("label") or family.get("candidate_family_id") or "unknown")
            count = _int(family.get("skipped_count"))
            families.append(f"{label}={count}")
        if families:
            suffix += f" skipped_families={', '.join(families)}"
            if len(family_summary) > len(families):
                suffix += f", +{len(family_summary) - len(families)} more"
    return (
        f"- {label}/{coin} core={core_id} "
        f"delivery={state} would_send={str(bool(row.get('would_send'))).lower()} "
        f"mode={mode or 'unknown'}{suffix}"
    )


def _format_count_map(counts: Mapping[str, Any], *, limit: int) -> str:
    items = sorted(
        ((str(key), _int(value)) for key, value in counts.items()),
        key=lambda item: (-item[1], item[0]),
    )
    shown = [f"{key}={value}" for key, value in items[:limit]]
    if len(items) > limit:
        shown.append(f"+{len(items) - limit} more")
    return ", ".join(shown) or "none"


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _market_anomaly_daily_lines(
    rows: Iterable[Mapping[str, Any]],
    *,
    limit: int,
) -> list[str]:
    candidates = [
        dict(row)
        for row in rows
        if isinstance(row, Mapping)
        and str(row.get("symbol") or "").upper() != "SECTOR"
        and str(row.get("row_type") or "") == "event_market_anomaly"
    ]
    if not candidates:
        return ["- None."]
    candidates.sort(key=lambda row: float(row.get("priority") or 0.0), reverse=True)
    lines: list[str] = []
    seen: set[str] = set()
    displayed = 0
    for row in candidates:
        key = str(row.get("canonical_asset_id") or row.get("coin_id") or row.get("symbol") or "")
        family = str(row.get("market_state_class") or row.get("anomaly_type") or "")
        dedupe_key = f"{key}|{family}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        snapshot = row.get("market_state_snapshot") if isinstance(row.get("market_state_snapshot"), Mapping) else {}
        packs = row.get("suggested_source_packs_to_search") if isinstance(row.get("suggested_source_packs_to_search"), list) else []
        why = row.get("why_interesting") if isinstance(row.get("why_interesting"), list) else []
        confirms = row.get("what_confirms") if isinstance(row.get("what_confirms"), list) else []
        invalidates = row.get("what_invalidates") if isinstance(row.get("what_invalidates"), list) else []
        lines.append(
            f"- {row.get('symbol') or row.get('coin_id') or 'UNKNOWN'}/{row.get('coin_id') or 'unknown'}: "
            f"type={row.get('market_state_class') or row.get('anomaly_type') or 'unknown'} "
            f"bucket={row.get('anomaly_bucket') or row.get('market_anomaly_bucket') or 'unknown'} "
            f"return_4h={_format_signed_pct(snapshot.get('return_4h'))} "
            f"return_24h={_format_signed_pct(snapshot.get('return_24h'))} "
            f"volume_z={_format_float(snapshot.get('volume_zscore_24h'))} "
            f"needs_catalyst_search={str(bool(row.get('needs_catalyst_search'))).lower()} "
            f"priority={_format_float(row.get('priority'))}"
        )
        if packs:
            lines.append("  search packs: " + ", ".join(str(item) for item in packs[:4]))
        if why:
            lines.append("  why_interesting: " + "; ".join(str(item) for item in why[:4]))
        if confirms:
            lines.append("  what_confirms: " + "; ".join(str(item) for item in confirms[:3]))
        if invalidates:
            lines.append("  what_invalidates: " + "; ".join(str(item) for item in invalidates[:3]))
        displayed += 1
        if displayed >= limit:
            break
    remaining = max(0, len(candidates) - displayed)
    if remaining:
        lines.append(f"- +{remaining} more market anomaly rows in local artifacts.")
    return lines


def _official_exchange_daily_lines(
    rows: Iterable[Mapping[str, Any]],
    *,
    limit: int,
) -> list[str]:
    candidates = [
        dict(row)
        for row in rows
        if isinstance(row, Mapping)
        and str(row.get("row_type") or "") == "official_listing_candidate"
    ]
    if not candidates:
        return ["- None."]
    priority = {
        "CONFIRMED_LONG_RESEARCH": 0,
        "EARLY_LONG_RESEARCH": 1,
        "FADE_SHORT_REVIEW": 2,
        "RISK_ONLY": 3,
        "UNCONFIRMED_RESEARCH": 4,
        "DIAGNOSTIC": 5,
    }
    candidates.sort(key=lambda row: (priority.get(str(row.get("opportunity_type") or ""), 9), str(row.get("published_at") or "")))
    lines: list[str] = []
    displayed = 0
    for row in candidates:
        lines.append(
            f"- {row.get('symbol') or 'UNRESOLVED'}/{row.get('coin_id') or 'unresolved'}: "
            f"{row.get('event_type') or 'unknown'} on {row.get('exchange') or 'exchange'} "
            f"lane={row.get('opportunity_type') or 'unknown'} "
            f"market_state={row.get('market_state') or 'unknown'} "
            f"pack={row.get('source_pack') or 'unknown'}"
        )
        if row.get("effective_time") or row.get("published_at"):
            lines.append(
                f"  timing: published={row.get('published_at') or 'unknown'} "
                f"effective={row.get('effective_time') or 'unknown'}"
            )
        warnings = [str(item) for item in row.get("resolver_warnings") or () if str(item)]
        if warnings:
            lines.append("  resolver: " + "; ".join(warnings[:3]))
        why_not = [str(item) for item in row.get("why_not_alertable") or () if str(item)]
        if why_not:
            lines.append("  why_not_alertable: " + "; ".join(why_not[:3]))
        if row.get("source_url"):
            lines.append(f"  source: {row.get('source_url')}")
        displayed += 1
        if displayed >= limit:
            break
    remaining = max(0, len(candidates) - displayed)
    if remaining:
        lines.append(f"- +{remaining} more official exchange rows in local artifacts.")
    return lines


def _scheduled_catalyst_daily_lines(
    rows: Iterable[Mapping[str, Any]],
    *,
    limit: int,
) -> list[str]:
    candidates = [
        dict(row)
        for row in rows
        if isinstance(row, Mapping)
        and str(row.get("row_type") or "") == "scheduled_catalyst_event"
        and str(row.get("event_type") or "") not in {"token_unlock", "vesting_cliff", "linear_emission"}
    ]
    if not candidates:
        return ["- None."]
    candidates.sort(key=lambda row: (str(row.get("event_start_time") or ""), str(row.get("symbol") or "")))
    lines: list[str] = []
    for row in candidates[: max(0, limit)]:
        lines.append(
            f"- {row.get('symbol') or 'UNRESOLVED'}/{row.get('coin_id') or 'unresolved'}: "
            f"{row.get('event_type') or 'unknown'} "
            f"status={row.get('event_status') or 'unknown'} "
            f"lane={row.get('opportunity_type') or 'unknown'} "
            f"market_state={row.get('market_state') or 'unknown'} "
            f"source_class={row.get('source_class') or 'unknown'}"
        )
        lines.append(f"  timing: start={row.get('event_start_time') or 'unknown'}")
        why_not = [str(item) for item in row.get("why_not_alertable") or () if str(item)]
        if why_not:
            lines.append("  why_not_alertable: " + "; ".join(why_not[:4]))
        if row.get("source_url"):
            lines.append(f"  source: {row.get('source_url')}")
    remaining = max(0, len(candidates) - limit)
    if remaining:
        lines.append(f"- +{remaining} more scheduled catalysts in local artifacts.")
    return lines


def _unlock_risk_daily_lines(
    rows: Iterable[Mapping[str, Any]],
    *,
    limit: int,
) -> list[str]:
    candidates = [
        dict(row)
        for row in rows
        if isinstance(row, Mapping)
        and str(row.get("row_type") or "") == "unlock_event"
    ]
    if not candidates:
        return ["- None."]
    priority = {
        "FADE_SHORT_REVIEW": 0,
        "RISK_ONLY": 1,
        "UNCONFIRMED_RESEARCH": 2,
        "DIAGNOSTIC": 3,
    }
    candidates.sort(key=lambda row: (priority.get(str(row.get("opportunity_type") or ""), 9), str(row.get("unlock_time") or "")))
    lines: list[str] = []
    for row in candidates[: max(0, limit)]:
        lines.append(
            f"- {row.get('symbol') or 'UNRESOLVED'}/{row.get('coin_id') or 'unresolved'}: "
            f"unlock={row.get('unlock_type') or 'unknown'} "
            f"pct_circ={_format_pct(row.get('unlock_pct_circulating_supply'))} "
            f"vs_adv={_format_float(row.get('unlock_vs_30d_adv'))} "
            f"lane={row.get('opportunity_type') or 'unknown'} "
            f"market_state={row.get('market_state') or 'unknown'}"
        )
        lines.append(f"  timing: unlock_time={row.get('unlock_time') or 'unknown'}")
        why_not = [str(item) for item in row.get("why_not_alertable") or () if str(item)]
        if why_not:
            lines.append("  why_not_alertable: " + "; ".join(why_not[:4]))
        if row.get("source_url"):
            lines.append(f"  source: {row.get('source_url')}")
    remaining = max(0, len(candidates) - limit)
    if remaining:
        lines.append(f"- +{remaining} more unlock rows in local artifacts.")
    return lines


def _derivatives_fade_review_daily_lines(
    fade_rows: Iterable[Mapping[str, Any]],
    state_rows: Iterable[Mapping[str, Any]],
    *,
    limit: int,
) -> list[str]:
    candidates = [dict(row) for row in fade_rows if isinstance(row, Mapping)]
    states = [dict(row) for row in state_rows if isinstance(row, Mapping)]
    lines = [
        "Research-only. Not a trade signal. FADE_SHORT_REVIEW means manual review of crowding/exhaustion risk after a completed move.",
        f"- Derivatives state rows: {len(states)}",
    ]
    if not candidates:
        lines.append("- Fade / short-review candidates: none.")
        return lines
    priority = {"extreme": 0, "high": 1, "moderate": 2, "none": 3}
    candidates.sort(
        key=lambda row: (
            priority.get(str(row.get("crowding_class") or "none"), 9),
            str(row.get("symbol") or ""),
        )
    )
    displayed = 0
    for row in candidates[: max(0, limit)]:
        lines.append(
            f"- {row.get('symbol') or 'UNKNOWN'}/{row.get('coin_id') or 'unknown'}: "
            f"lane={row.get('opportunity_type') or 'unknown'} "
            f"market_state={row.get('market_state') or 'unknown'} "
            f"crowding={row.get('crowding_class') or 'unknown'} "
            f"fade_ready={row.get('fade_readiness') or 'unknown'}"
        )
        lines.append(f"  move: {_derivatives_move_summary(row)}")
        evidence = [str(item) for item in row.get("crowding_exhaustion_evidence") or () if str(item)]
        lines.append("  crowding/exhaustion: " + ("; ".join(evidence[:6]) if evidence else "none"))
        invalidates = [str(item) for item in row.get("what_invalidates_fade_review") or () if str(item)]
        if invalidates:
            lines.append("  invalidates: " + "; ".join(invalidates[:4]))
        warnings = [str(item) for item in row.get("warnings") or () if str(item)]
        if warnings:
            lines.append("  warnings: " + "; ".join(warnings[:4]))
        displayed += 1
    remaining = max(0, len(candidates) - displayed)
    if remaining:
        lines.append(f"- +{remaining} more derivatives fade-review rows in local artifacts.")
    return lines


def _derivatives_move_summary(row: Mapping[str, Any]) -> str:
    snapshot = row.get("market_state_snapshot")
    if not isinstance(snapshot, Mapping):
        snapshot = {}
    unit = event_market_units.infer_return_unit(snapshot, default=event_market_units.RETURN_UNIT_PERCENT_POINTS)
    return (
        f"4h={event_market_units.format_return_pct(snapshot.get('return_4h'), unit)} "
        f"24h={event_market_units.format_return_pct(snapshot.get('return_24h'), unit)} "
        f"liquidity={_format_compact_number(snapshot.get('liquidity_usd'))} "
        f"spread_bps={_format_float(snapshot.get('spread_bps'))}"
    )


def _format_compact_number(value: object) -> str:
    parsed = _optional_float(value)
    if parsed is None:
        return "n/a"
    if abs(parsed) >= 1_000_000:
        return f"{parsed / 1_000_000:.1f}m"
    if abs(parsed) >= 1_000:
        return f"{parsed / 1_000:.1f}k"
    return f"{parsed:.1f}".rstrip("0").rstrip(".")


def _calendar_gap_daily_lines(
    rows: Iterable[Mapping[str, Any]],
    *,
    limit: int,
) -> list[str]:
    gaps: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        why_not = {str(item) for item in row.get("why_not_alertable") or ()}
        if (
            "source_url_missing" in why_not
            or "unlock_time_missing" in why_not
            or "structured_unlock_proof_missing" in why_not
            or not row.get("source_url")
        ):
            gaps.append(dict(row))
    if not gaps:
        return ["- None."]
    lines: list[str] = []
    for row in gaps[: max(0, limit)]:
        why_not = [str(item) for item in row.get("why_not_alertable") or () if str(item)]
        lines.append(
            f"- {row.get('symbol') or 'UNRESOLVED'}/{row.get('coin_id') or 'unresolved'}: "
            f"{row.get('event_type') or 'unknown'} missing={'; '.join(why_not[:3]) or 'source confirmation'}"
        )
    remaining = max(0, len(gaps) - limit)
    if remaining:
        lines.append(f"- +{remaining} more calendar gaps in local artifacts.")
    return lines


def _scheduled_market_watch_lines(
    rows: Iterable[Mapping[str, Any]],
    *,
    limit: int,
) -> list[str]:
    watch_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        lane = str(row.get("opportunity_type") or "")
        state = str(row.get("market_state") or "")
        if lane in {"EARLY_LONG_RESEARCH", "UNCONFIRMED_RESEARCH"} and state in {"no_reaction", "stealth_accumulation"}:
            watch_rows.append(dict(row))
    if not watch_rows:
        return ["- None."]
    watch_rows.sort(key=lambda row: (str(row.get("event_start_time") or row.get("unlock_time") or ""), str(row.get("symbol") or "")))
    lines: list[str] = []
    for row in watch_rows[: max(0, limit)]:
        lines.append(
            f"- {row.get('symbol') or 'UNRESOLVED'}/{row.get('coin_id') or 'unresolved'}: "
            f"{row.get('event_type') or 'unknown'} "
            f"lane={row.get('opportunity_type') or 'unknown'} "
            f"market_state={row.get('market_state') or 'unknown'} "
            f"next={row.get('event_start_time') or row.get('unlock_time') or 'unknown'}"
        )
    remaining = max(0, len(watch_rows) - limit)
    if remaining:
        lines.append(f"- +{remaining} more near-term events needing market watch.")
    return lines


def _format_signed_pct(value: object) -> str:
    parsed = _optional_float(value)
    return "n/a" if parsed is None else f"{parsed:+.1f}%"


def _format_float(value: object) -> str:
    parsed = _optional_float(value)
    return "n/a" if parsed is None else f"{parsed:.1f}"


def _format_pct(value: object) -> str:
    parsed = _optional_float(value)
    if parsed is None:
        return "n/a"
    if abs(parsed) <= 3.0:
        parsed *= 100.0
    return f"{parsed:.1f}%"


def _optional_float(value: object) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _live_confirmation_gated_core_lines(
    opportunities: Iterable[event_core_opportunities.CoreOpportunity],
    *,
    limit: int,
) -> list[str]:
    rows = [
        item
        for item in opportunities
        if bool(item.primary_row.get("live_confirmation_capped"))
        or (
            bool(item.primary_row.get("live_confirmation_required"))
            and not bool(item.primary_row.get("live_confirmation_passed"))
        )
    ]
    if not rows:
        return ["- None."]
    lines: list[str] = []
    for item in rows[:limit]:
        row = item.primary_row
        missing = row.get("live_confirmation_missing_requirements")
        if not isinstance(missing, list):
            missing = []
        upgrades = row.get("upgrade_requirements")
        if not isinstance(upgrades, list):
            upgrades = []
        lines.append(
            f"- {item.core_opportunity_id} {item.symbol}/{item.coin_id}: "
            f"requested={row.get('requested_opportunity_level_before_live_confirmation') or item.opportunity_level} "
            f"capped={row.get('final_opportunity_level') or item.opportunity_level} "
            f"status={row.get('evidence_acquisition_status') or 'unknown'} "
            f"confirmation={row.get('acquisition_confirmation_status') or 'unknown'} "
            f"reason={row.get('live_confirmation_reason') or row.get('quality_gate_block_reason') or 'live_confirmation_missing'}"
        )
        lines.append(
            "  upgrade: "
            + "; ".join(str(value) for value in (missing or upgrades)[:3])
        )
    if len(rows) > limit:
        lines.append(f"- +{len(rows) - limit} more live-confirmation gated candidates")
    return lines


def _core_opportunity_sections(
    opportunities: Iterable[event_core_opportunities.CoreOpportunity],
) -> dict[str, list[event_core_opportunities.CoreOpportunity]]:
    """Partition core opportunities into one operator-facing section each."""
    remaining = list(opportunities)
    sections: dict[str, list[event_core_opportunities.CoreOpportunity]] = {}

    def take(
        name: str,
        predicate: Callable[[event_core_opportunities.CoreOpportunity], bool],
    ) -> None:
        selected: list[event_core_opportunities.CoreOpportunity] = []
        rest: list[event_core_opportunities.CoreOpportunity] = []
        for item in remaining:
            if predicate(item):
                selected.append(item)
            else:
                rest.append(item)
        sections[name] = selected
        remaining[:] = rest

    take("strong", lambda item: item.is_high_priority)
    take("watchlist", lambda item: item.is_watchlist)
    take("digest", lambda item: item.is_validated_digest or item.alertable)
    sections["local"] = remaining
    return sections


def _core_opportunity_lane_sections(
    opportunities: Iterable[event_core_opportunities.CoreOpportunity],
) -> dict[str, list[event_core_opportunities.CoreOpportunity]]:
    sections: dict[str, list[event_core_opportunities.CoreOpportunity]] = {
        "early": [],
        "confirmed": [],
        "fade": [],
        "risk": [],
        "unconfirmed": [],
        "diagnostics": [],
    }
    for item in opportunities:
        lane = str(item.primary_row.get("opportunity_type") or "").strip().upper()
        if lane == "EARLY_LONG_RESEARCH":
            sections["early"].append(item)
        elif lane == "CONFIRMED_LONG_RESEARCH":
            sections["confirmed"].append(item)
        elif lane == "FADE_SHORT_REVIEW":
            sections["fade"].append(item)
        elif lane == "RISK_ONLY":
            sections["risk"].append(item)
        elif lane == "DIAGNOSTIC":
            sections["diagnostics"].append(item)
        else:
            sections["unconfirmed"].append(item)
    return sections


def _market_freshness_readiness_lines(
    rows: Iterable[Any],
    *,
    requested_profile: str | None,
    limit: int = 8,
) -> list[str]:
    normalized = [_row_mapping(row) for row in rows]
    visible_core = event_core_opportunities.visible_core_opportunities(normalized)
    statuses: dict[str, int] = {}
    capped: list[Mapping[str, Any]] = []
    missing: list[Mapping[str, Any]] = []
    refresh_needed: list[Mapping[str, Any]] = []
    for row in normalized:
        components = _components_for_row(row)
        status = str(
            row.get("market_context_freshness_status")
            or components.get("market_context_freshness_status")
            or "missing"
        )
        statuses[status] = statuses.get(status, 0) + 1
        cap = _truthy(row.get("market_context_freshness_cap_applied") if row.get("market_context_freshness_cap_applied") is not None else components.get("market_context_freshness_cap_applied"))
        if row.get("row_type") == "event_core_opportunity" and status in {"fresh", "fixture_allowed_stale"}:
            cap = False
        if cap or status in {"stale", "unknown", "missing"}:
            refresh_needed.append(row)
        if cap or status == "stale":
            capped.append(row)
        if status in {"missing", "unknown"}:
            missing.append(row)
    profile = str(requested_profile or "").casefold()
    can_refresh = profile not in {"fixture", "quality_validation", "catalyst_frame_e2e", "notify_llm_quality_frame", "catalyst_frame_validation"}
    lines = [
        "- Freshness statuses: " + _format_counts(statuses),
        f"- Fresh market context: {statuses.get('fresh', 0)}",
        f"- Capped by stale/unknown context: {len(capped)}",
        f"- Missing/unknown market context: {len(missing)}",
        f"- Needs targeted market refresh: {len(refresh_needed)}",
        f"- Live profile can perform refresh: {str(can_refresh).lower()}",
    ]
    if visible_core:
        lines.append("- Core opportunity freshness:")
        for item in visible_core[:limit]:
            line = _core_market_freshness_line(item)
            if line:
                lines.append(line)
        if len(visible_core) > limit:
            lines.append(f"  - +{len(visible_core) - limit} more core opportunities in diagnostics")
    else:
        for row in refresh_needed[:limit]:
            components = _components_for_row(row)
            label = _label_for_row(row, components)
            status = row.get("market_context_freshness_status") or components.get("market_context_freshness_status") or "missing"
            source = row.get("market_context_source") or components.get("market_context_source") or "unknown"
            cap = row.get("market_context_freshness_cap_applied")
            if cap is None:
                cap = components.get("market_context_freshness_cap_applied")
            lines.append(
                f"  - {label}: status={status} source={source} age={_market_age_label(row, components)} cap_applied={str(_truthy(cap)).lower()}"
            )
        if len(refresh_needed) > limit:
            lines.append(f"  - +{len(refresh_needed) - limit} more rows need refresh")
    return lines


def _core_market_freshness_line(item: event_core_opportunities.CoreOpportunity) -> str:
    rows = [item.primary_row, *item.supporting_rows]
    row_infos: list[tuple[str, str, str, bool, bool]] = []
    for row in rows:
        components = _components_for_row(row)
        status = str(row.get("market_context_freshness_status") or components.get("market_context_freshness_status") or "missing")
        source = str(row.get("market_context_source") or components.get("market_context_source") or "unknown")
        age = _market_age_label(row, components)
        cap_raw = row.get("market_context_freshness_cap_applied")
        if cap_raw is None:
            cap_raw = components.get("market_context_freshness_cap_applied")
        refresh_attempted = _truthy(row.get("market_refresh_attempted") or components.get("market_refresh_attempted"))
        row_infos.append((status, source, age, _truthy(cap_raw), refresh_attempted))
    if not row_infos:
        row_infos.append(("missing", "unknown", "unknown", False, False))
    status_rank = {"fresh": 0, "fixture_allowed_stale": 1, "stale": 2, "unknown": 3, "missing": 4}
    core_components = _components_for_row(item.primary_row)
    core_status = str(item.primary_row.get("market_context_freshness_status") or core_components.get("market_context_freshness_status") or "")
    core_source = str(item.primary_row.get("market_context_source") or core_components.get("market_context_source") or "")
    core_age = _market_age_label(item.primary_row, core_components)
    if not core_status:
        best = sorted(row_infos, key=lambda item_info: status_rank.get(item_info[0], 5))[0]
        core_status, core_source, core_age = best[0], best[1], best[2]
    if core_status in {"fresh", "fixture_allowed_stale"} and core_source.casefold() in {"", "missing", "unknown"}:
        core_source = "canonical_core_store"
    if core_status in {"fresh", "fixture_allowed_stale"} and core_age.casefold() in {"", "unknown", "missing"}:
        core_age = "n/a"
    support_infos = row_infos[1:] if len(row_infos) > 1 else ()
    support_gaps = sum(1 for status, _, _, cap, _ in support_infos if cap or status in {"stale", "unknown", "missing"})
    core_refresh_needed = core_status in {"", "stale", "unknown", "missing"}
    support_refresh_needed = 0 if core_status in {"fresh", "fixture_allowed_stale"} else support_gaps
    refresh_attempted = any(info[4] for info in row_infos)
    derivatives_line = _confirmation_status_line(
        item.primary_row,
        core_components,
        level_key="derivatives_confirmation_level",
        score_key="derivatives_confirmation_score",
        freshness_key="derivatives_freshness_status",
    )
    dex_line = _confirmation_status_line(
        item.primary_row,
        core_components,
        level_key="dex_liquidity_level",
        score_key="dex_liquidity_score",
        freshness_key="dex_freshness_status",
    )
    protocol_line = _confirmation_status_line(
        item.primary_row,
        core_components,
        level_key="protocol_metrics_level",
        score_key="protocol_metrics_score",
        freshness_key="protocol_metrics_freshness_status",
    )
    return (
        f"  - {item.core_opportunity_id} {item.symbol}/{item.coin_id}: "
        f"core_market_freshness_status={core_status or 'missing'} "
        f"core_market_context_source={core_source or 'unknown'} "
        f"core_market_context_age={core_age} "
        f"refresh_attempted={str(refresh_attempted).lower()} "
        f"derivatives={derivatives_line} "
        f"dex_liquidity={dex_line} "
        f"protocol_metrics={protocol_line} "
        f"core_market_refresh_needed={str(core_refresh_needed).lower()} "
        f"support_rows_stale_or_missing_count={support_gaps} "
        f"support_rows_needing_refresh_count={support_refresh_needed}"
    )


def _confirmation_status_line(
    row: Mapping[str, Any],
    components: Mapping[str, Any],
    *,
    level_key: str,
    score_key: str,
    freshness_key: str,
) -> str:
    level = row.get(level_key) or components.get(level_key) or "none"
    score = row.get(score_key) if row.get(score_key) is not None else components.get(score_key)
    freshness = row.get(freshness_key) or components.get(freshness_key) or "missing"
    score_text = "n/a" if score in (None, "") else str(score)
    return f"{level}/{score_text}/{freshness}"


def _row_mapping(row: Any) -> Mapping[str, Any]:
    if isinstance(row, event_watchlist.EventWatchlistEntry):
        data = dict(getattr(row, "__dict__", {}) or {})
        data.setdefault("latest_score_components", dict(row.latest_score_components or {}))
        return data
    if isinstance(row, Mapping):
        return row
    return dict(getattr(row, "__dict__", {}) or {})


def _components_for_row(row: Mapping[str, Any]) -> Mapping[str, Any]:
    for key in ("latest_score_components", "score_components", "_components"):
        value = row.get(key)
        if isinstance(value, Mapping):
            return value
    return {}


def _label_for_row(row: Mapping[str, Any], components: Mapping[str, Any]) -> str:
    symbol = row.get("symbol") or row.get("validated_symbol") or components.get("validated_symbol") or "UNKNOWN"
    coin = row.get("coin_id") or row.get("validated_coin_id") or components.get("validated_coin_id") or "unknown"
    return f"{symbol}/{coin}"


def _market_age_label(row: Mapping[str, Any], components: Mapping[str, Any]) -> str:
    value = row.get("market_context_age_hours")
    if value is None:
        value = components.get("market_context_age_hours")
    try:
        hours = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "unknown"
    if hours < 1:
        return f"{hours * 60:.0f}m"
    return f"{hours:.1f}h"


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "y"}
    return bool(value)


def _card_paths_for_daily_brief(paths: Iterable[Path], *, include_diagnostics: bool) -> list[Path]:
    cards = [Path(path) for path in paths]
    if include_diagnostics:
        return cards
    hidden_terms = (
        "source_noise_control",
        "ambiguous_control",
        "quality_blocked",
        "local_only",
        "store_only",
        "diagnostic",
    )
    return [
        path for path in cards
        if not any(term in path.name.casefold() for term in hidden_terms)
    ]


def _brief_core_opportunities(
    rows: Iterable[event_core_opportunities.CoreOpportunity],
    *,
    section: str,
    limit: int,
) -> str:
    if section == "strong":
        selected = [item for item in rows if item.is_high_priority or item.is_watchlist]
    elif section == "digest":
        selected = [item for item in rows if item.is_validated_digest and not (item.is_high_priority or item.is_watchlist)]
    else:
        selected = list(rows)
    labels = []
    for item in selected[:limit]:
        labels.append(
            f"{item.symbol}/{item.coin_id}"
            f"(core={item.core_opportunity_id},level={item.opportunity_level},"
            f"route={item.final_route_after_quality_gate or 'local'},"
            f"state={item.final_state_after_quality_gate or 'unknown'},"
            f"score={item.opportunity_score_final:.0f},"
            f"path={item.primary_impact_path},role={item.candidate_role},"
            f"support={len(item.supporting_rows)},diagnostics={item.diagnostic_row_count})"
        )
    return "; ".join(labels)


def _brief_entries(rows: Iterable[event_watchlist.EventWatchlistEntry]) -> str:
    labels: list[str] = []
    seen: set[tuple[str, str]] = set()
    for entry in rows:
        key = _entry_family_key(entry)
        if key in seen:
            continue
        seen.add(key)
        components = entry.latest_score_components or {}
        labels.append(
            f"{entry.symbol}/{entry.coin_id}"
            f"({components.get('impact_category') or entry.latest_playbook_type or 'unknown'},"
            f"score={entry.latest_score},v2={_float(components.get('opportunity_score_v2')):.0f},"
            f"path={components.get('impact_path_type') or 'unknown'},main={components.get('main_frame_type') or 'unknown'})"
        )
    return "; ".join(labels)


def _market_confirmation_by_playbook(rows: Iterable[event_alpha_router.EventAlphaRouteDecision]) -> str:
    counts: dict[str, dict[str, int]] = {}
    for decision in rows:
        entry = decision.entry
        if entry.relationship_type != "impact_hypothesis":
            continue
        components = entry.latest_score_components or {}
        playbook = str(entry.latest_effective_playbook_type or entry.latest_playbook_type or "unknown")
        level = str(components.get("market_confirmation_level") or "unknown")
        counts.setdefault(playbook, {})[level] = counts.setdefault(playbook, {}).get(level, 0) + 1
    if not counts:
        return "none"
    parts: list[str] = []
    for playbook, levels in sorted(counts.items()):
        parts.append(playbook + "[" + ",".join(f"{key}={value}" for key, value in sorted(levels.items())) + "]")
    return "; ".join(parts)


def _quality_decision_counts(rows: Iterable[event_alpha_router.EventAlphaRouteDecision], key: str) -> str:
    counts: dict[str, int] = {}
    for decision in rows:
        if decision.entry.relationship_type != "impact_hypothesis":
            continue
        components = decision.entry.latest_score_components or {}
        value = str(components.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return _format_counts(counts)


def _quality_gate_downgrades(
    rows: Iterable[event_alpha_router.EventAlphaRouteDecision],
) -> list[event_alpha_router.EventAlphaRouteDecision]:
    return [
        decision for decision in rows
        if decision.quality_gate_block_reason
        or (
            decision.requested_route_before_quality_gate
            and decision.final_route_after_quality_gate
            and decision.requested_route_before_quality_gate != decision.final_route_after_quality_gate
        )
    ]


def _blocked_route_attempts_line(rows: Iterable[event_alpha_router.EventAlphaRouteDecision]) -> str:
    labels: list[str] = []
    for decision in rows:
        labels.append(
            f"{decision.entry.symbol}/{decision.entry.coin_id}:"
            f"{decision.requested_route_before_quality_gate or 'unknown'}->"
            f"{decision.final_route_after_quality_gate or decision.route.value}"
        )
        if len(labels) >= 5:
            break
    return "; ".join(labels)


def _quality_gate_reason_counts(rows: Iterable[event_alpha_router.EventAlphaRouteDecision]) -> str:
    counts: dict[str, int] = {}
    for decision in rows:
        reason = str(decision.quality_gate_block_reason or "route_capped")
        counts[reason] = counts.get(reason, 0) + 1
    return _format_counts(counts)


def _legacy_quality_conflicts(rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    out = []
    for row in rows:
        classification = str(
            row.get("snapshot_quality_classification")
            or event_alpha_alert_store.classify_alert_snapshot(row)
        )
        if classification in event_alpha_alert_store.LEGACY_CONFLICT_CLASSIFICATIONS:
            out.append(row)
    return out


def _legacy_quality_conflict_lines(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    items = list(rows)
    if not items:
        return ["- none"]
    lines: list[str] = []
    for row in items:
        label = row.get("symbol") or row.get("validated_symbol") or row.get("coin_id") or row.get("alert_key") or "candidate"
        classification = str(row.get("snapshot_quality_classification") or event_alpha_alert_store.classify_alert_snapshot(row))
        lines.append(
            f"- {label}: classification={classification} "
            f"legacy_route={row.get('route') or 'unknown'} "
            f"final={row.get('final_route_after_quality_gate') or 'missing'} "
            f"level={row.get('opportunity_level') or 'unknown'} "
            f"score={row.get('opportunity_score_final') if row.get('opportunity_score_final') is not None else 'n/a'}"
        )
    return lines


def _candidate_discovery_funnel_line(rows: Iterable[Mapping[str, Any]]) -> str:
    generated = executed = raw_terms = candidate_like = accepted = rejected = validated = promoted = 0
    for row in rows:
        generated += len(row.get("generated_queries") or [])
        executed += len(row.get("executed_queries") or [])
        crypto = row.get("crypto_candidate_assets") or []
        rejects = row.get("rejected_candidate_assets") or []
        raw_terms += len(crypto) + len(rejects)
        candidate_like += sum(1 for item in [*crypto, *rejects] if isinstance(item, Mapping) and _candidate_like_term(item))
        accepted += sum(1 for item in crypto if isinstance(item, Mapping) and bool(item.get("accepted", item.get("validated", False))))
        rejected += len(rejects)
        if str(row.get("validation_stage") or "") in {"catalyst_link_validated", "impact_path_validated", "market_confirmed", "promoted_to_radar"}:
            validated += 1
        if str(row.get("opportunity_level") or "") in {"validated_digest", "watchlist", "high_priority"}:
            promoted += 1
    if not any((generated, executed, raw_terms, candidate_like, accepted, rejected, validated, promoted)):
        return "none"
    resolver_attempted = accepted + rejected
    return (
        f"generated={generated}, executed={executed}, raw_terms_extracted={raw_terms}, "
        f"candidate_like_terms={candidate_like}, resolver_accepted_candidates={accepted}, "
        f"resolver_attempted={resolver_attempted}, resolver_rejected_terms={rejected}, "
        f"context_validated_candidates={validated}, "
        f"promoted_candidates={promoted}"
    )


def _canonical_incident_lines(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    incidents = [dict(row) for row in rows if isinstance(row, Mapping)]
    if not incidents:
        return ["- Stored incidents: none loaded for this profile."]
    diagnostic_rows = [row for row in incidents if _incident_is_hidden(row)]
    visible = [row for row in incidents if not _incident_is_diagnostic(row)]
    if not visible:
        return [
            f"- Stored incidents: {len(incidents)}",
            f"- Diagnostic/raw/external-context observations hidden: {len(diagnostic_rows)}",
            "- Canonical incidents: none visible for this profile.",
        ]
    lines = [
        f"- Stored incidents: {len(incidents)}",
        f"- Diagnostic/raw/external-context observations hidden: {len(diagnostic_rows)}",
        "- Relevance statuses: " + _format_counts(_field_counts(incidents, "incident_relevance_status")),
        "- Event archetypes: " + _format_counts(_field_counts(visible, "event_archetype")),
        "- Cause statuses: " + _format_counts(_field_counts(visible, "current_cause_status")),
        "- Primary subjects: " + _format_counts(_field_counts(visible, "primary_subject")),
        "- New/updated: "
        f"multiple_source_updates={sum(1 for row in visible if int(row.get('source_update_count') or 0) > 1)}, "
        f"conflicting_claims={sum(1 for row in visible if row.get('conflicting_claims'))}",
        "- Market reaction but unknown/ruled-out cause: "
        + str(sum(
            1 for row in visible
            if (row.get("market_reaction_observed") or row.get("market_reaction_confirmed"))
            and str(row.get("current_cause_status") or "") in {"unknown", "ruled_out"}
        )),
        "- Confirmed cause missing market data: "
        + str(sum(
            1 for row in visible
            if str(row.get("current_cause_status") or "") == "confirmed"
            and not row.get("market_context_source")
        )),
        "- Weak unqualified incident links: "
        + str(sum(int(row.get("weak_link_count") or 0) for row in visible)),
    ]
    candidates = [row for row in visible if str(row.get("incident_relevance_status") or "") == "incident_candidate"]
    active = [
        row for row in visible
        if str(row.get("incident_relevance_status") or "") == "active_incident"
        and int(row.get("qualified_link_count") or 0) > 0
    ]
    linked = [
        row for row in visible
        if str(row.get("incident_relevance_status") or "") == "linked_incident"
        and int(row.get("qualified_link_count") or 0) > 0
    ]
    market_unknown = [
        row for row in visible
        if (row.get("market_reaction_observed") or row.get("market_reaction_confirmed"))
        and str(row.get("current_cause_status") or "") in {"unknown", "ruled_out"}
    ]
    lines.append(f"- Incident candidates: {len(candidates)}")
    lines.append(f"- Active incidents with qualified links: {len(active)}")
    lines.append(f"- Linked incidents with qualified links: {len(linked)}")
    lines.append(f"- Market reactions with unknown/ruled-out cause: {len(market_unknown)}")
    if candidates:
        labels = []
        for row in candidates[:5]:
            labels.append(
                f"{row.get('canonical_name') or row.get('incident_id')}: "
                f"reason={row.get('canonical_persistence_reason') or 'candidate'} "
                f"weak_links={int(row.get('weak_link_count') or 0)}"
            )
        lines.append("- Incident candidates awaiting qualified crypto link: " + " | ".join(labels))
    notable = sorted(
        visible,
        key=lambda row: (
            int(row.get("source_update_count") or 0),
            _float(row.get("incident_confidence")),
        ),
        reverse=True,
    )
    if notable:
        labels = []
        for row in notable[:5]:
            assets = row.get("linked_assets") or []
            asset_text = _incident_asset_summary(assets)
            labels.append(
                f"{row.get('canonical_name') or row.get('incident_id')}: "
                f"cause={row.get('current_cause_status') or 'unknown'} "
                f"archetype={row.get('event_archetype') or 'unknown'} "
                f"sources={int(row.get('source_update_count') or 0)}/"
                f"{int(row.get('independent_source_count') or 0)} "
                f"assets={asset_text}"
            )
        lines.append("- Notable incidents: " + " | ".join(labels))
    return lines


def _incident_is_hidden(row: Mapping[str, Any]) -> bool:
    status = str(row.get("incident_relevance_status") or "")
    return bool(row.get("diagnostic_only")) or status in {"raw_observation", "external_context_only", "diagnostic_only", "rejected_incident"}


def _incident_is_diagnostic(row: Mapping[str, Any]) -> bool:
    return _incident_is_hidden(row)


def _incident_asset_summary(value: Any) -> str:
    if not value:
        return "none"
    labels: list[str] = []
    for item in list(value)[:4]:
        if not isinstance(item, Mapping):
            continue
        labels.append(
            f"{item.get('symbol') or item.get('coin_id') or 'asset'}:"
            f"{item.get('role') or 'unknown'}"
        )
    return ", ".join(labels) or "none"


def _candidate_like_term(item: Mapping[str, Any]) -> bool:
    symbol = str(item.get("symbol") or "").strip()
    coin_id = str(item.get("coin_id") or "").strip()
    name = str(item.get("name") or item.get("project_name") or "").strip()
    source = str(item.get("source") or "").strip().casefold()
    mention_type = str(item.get("mention_type") or item.get("type") or "").strip().casefold()
    reason = str(item.get("reason") or item.get("rejection_reason") or item.get("identity_reason") or "").casefold()
    accepted = bool(item.get("accepted") or item.get("validated"))
    if any(token in reason for token in ("source_noise", "publisher", "word_collision", "url_only", "generic_symbol")):
        return False
    if any(token in mention_type for token in ("source_noise", "publisher", "navigation", "nav", "word_collision")):
        return False
    if source in {"taxonomy", "source_origin", "publisher", "nav", "navigation"} and not accepted:
        return False
    return bool(symbol or coin_id or name)


def _feedback_by_impact_path(alerts: Iterable[Mapping[str, Any]], feedback: Iterable[Mapping[str, Any]]) -> str:
    path_by_key: dict[str, str] = {}
    for row in alerts:
        key = str(row.get("alert_key") or row.get("alert_id") or "")
        if key:
            path_by_key[key] = str(row.get("impact_path_type") or "unknown")
    counts: dict[str, int] = {}
    for row in feedback:
        key = str(row.get("key") or row.get("alert_key") or row.get("alert_id") or "")
        path = str(row.get("impact_path_type") or path_by_key.get(key) or "unknown")
        label = str(row.get("label") or row.get("feedback") or "feedback")
        counts[f"{path}:{label}"] = counts.get(f"{path}:{label}", 0) + 1
    return _format_counts(counts)


def _upgrade_candidate_line(rows: Iterable[event_alpha_router.EventAlphaRouteDecision]) -> str:
    labels: list[str] = []
    seen: set[tuple[str, str]] = set()
    for decision in sorted(rows, key=lambda item: item.entry.latest_score, reverse=True):
        entry = decision.entry
        if event_alpha_router.alertable_after_quality_gate(decision) or entry.relationship_type != "impact_hypothesis":
            continue
        key = _decision_family_key(decision)
        if key in seen:
            continue
        components = entry.latest_score_components or {}
        upgrade = event_opportunity_verdict.explain_upgrade_path(components=components)
        if not upgrade.upgrade_requirements:
            continue
        seen.add(key)
        labels.append(
            f"{entry.symbol}/{entry.coin_id}: "
            + event_alpha_reason_text.humanize_event_alpha_reasons(upgrade.upgrade_requirements, limit=2)
        )
        if len(labels) >= 5:
            break
    return " | ".join(labels)


def _downgrade_risk_line(rows: Iterable[event_alpha_router.EventAlphaRouteDecision]) -> str:
    labels: list[str] = []
    seen: set[tuple[str, str]] = set()
    for decision in sorted(rows, key=lambda item: item.entry.latest_score, reverse=True):
        entry = decision.entry
        if not event_alpha_router.alertable_after_quality_gate(decision) and event_watchlist.final_state_value(entry) not in {"WATCHLIST", "HIGH_PRIORITY"}:
            continue
        key = _decision_family_key(decision)
        if key in seen:
            continue
        components = entry.latest_score_components or {}
        upgrade = event_opportunity_verdict.explain_upgrade_path(components=components)
        if not upgrade.downgrade_warnings:
            continue
        seen.add(key)
        labels.append(
            f"{entry.symbol}/{entry.coin_id}: "
            + event_alpha_reason_text.humanize_event_alpha_reasons(upgrade.downgrade_warnings, limit=2)
        )
        if len(labels) >= 5:
            break
    return " | ".join(labels)


def _float(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _lane_count(row: Mapping[str, Any] | None, field: str, lane: str) -> int:
    if not row:
        return 0
    counts = row.get(field) or {}
    if not isinstance(counts, Mapping):
        return 0
    try:
        return int(counts.get(lane) or 0)
    except (TypeError, ValueError):
        return 0


def _format_clock_status(status: Mapping[str, Any]) -> str:
    age = status.get("fixed_clock_age_hours")
    age_text = "n/a" if age is None else f"{float(age):.2f}h"
    return (
        "Clock: "
        f"mode={status.get('clock_mode') or 'unknown'}; "
        f"research_now={status.get('research_now') or 'unknown'}; "
        f"wall_clock_now={status.get('wall_clock_now') or 'unknown'}; "
        f"fixed_clock_age_hours={age_text}"
    )


def _format_clock_warning_lines(status: Mapping[str, Any]) -> list[str]:
    warnings = [str(item) for item in status.get("warnings") or () if str(item)]
    return [f"Clock warning: {warning}" for warning in warnings]


def _strip_sensitive(text: str) -> str:
    cleaned = (
        text.replace("OPENAI_API_KEY", "[redacted]")
        .replace("TELEGRAM_BOT_TOKEN", "[redacted]")
        .replace(".env", "[env-file]")
    )
    return event_artifact_paths.scrub_absolute_paths_from_markdown(cleaned)
