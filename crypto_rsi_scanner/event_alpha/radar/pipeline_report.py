"""Report rendering for Event Alpha pipeline results."""

from __future__ import annotations

from collections.abc import Iterable

import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
import crypto_rsi_scanner.event_alpha.radar.anomaly_state as event_anomaly_state
import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
import crypto_rsi_scanner.event_alpha.radar.evidence_acquisition as event_evidence_acquisition
import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses
import crypto_rsi_scanner.event_alpha.notifications.watchlist_monitor as event_watchlist_monitor
from .pipeline import EventAlphaPipelineResult


def format_event_alpha_pipeline_report(result: EventAlphaPipelineResult) -> str:
    """Format a concise Event Alpha cycle summary."""
    lines = [
        "=" * 76,
        "EVENT ALPHA PIPELINE REPORT (research-only; no trades, paper rows, or live RSI routing)",
        "=" * 76,
        (
            f"raw_events={result.raw_events} · catalyst_queries={result.catalyst_queries} · "
            f"catalyst_results={result.catalyst_results} · "
            f"anomaly_lifecycle={result.anomaly_lifecycle_entries} · "
            f"extractions={result.extractions}/{len(result.extraction_rows)} · "
            f"extraction_hints_applied={result.extraction_hint_events} · "
            f"catalyst_frames={result.catalyst_frame_analyses}/{len(result.catalyst_frame_rows)} · "
            f"catalyst_frame_validations={result.catalyst_frame_validations_applied} · "
            f"candidates={result.candidates} · clusters={result.clusters} · alerts={len(result.alerts)}"
        ),
        (
            f"impact_hypotheses={len(result.impact_hypotheses)} · "
            f"hypotheses_validated={result.hypotheses_validated} · "
            f"hypothesis_search_queries={result.hypothesis_search_queries} · "
            f"hypothesis_search_results={result.hypothesis_search_results} · "
            f"hypothesis_promotions={result.hypothesis_promotions} · "
            f"near_misses={result.near_misses} · near_miss_upgrades={result.near_miss_upgrades} · "
            f"evidence_acquisition={result.evidence_acquisition_attempted} "
            f"accepted={result.evidence_acquisition_accepted} "
            f"upgraded={result.evidence_acquisition_upgraded}"
        ),
        (
            "hypothesis_search_query_types="
            + (
                _query_type_summary(result.hypothesis_search_result.queries)
                if result.hypothesis_search_result is not None
                else "none"
            )
        ),
        (
            "catalyst_search_skip_reasons="
            + (
                ", ".join(f"{key}={value}" for key, value in sorted(result.catalyst_search_skip_reasons.items()))
                if result.catalyst_search_skip_reasons
                else "none"
            )
        ),
        (
            "hypothesis_search_skip_reasons="
            + (
                ", ".join(f"{key}={value}" for key, value in sorted(result.hypothesis_search_skip_reasons.items()))
                if result.hypothesis_search_skip_reasons
                else "none"
            )
        ),
        (
            f"watchlist_entries={result.watchlist_entries} · "
            f"watchlist_escalations={result.watchlist_escalations} · "
            f"watchlist_monitor_active={result.watchlist_monitor_active_entries} · "
            f"watchlist_monitor_material={result.watchlist_monitor_material_updates} · "
            f"routed={result.routed} · alertable={result.alertable}"
        ),
        (
            f"send_requested={str(result.send_requested).lower()} · "
            f"send_attempted={str(result.send_attempted).lower()} · "
            f"send_success={str(result.send_success).lower()} · "
            f"send_items={result.send_items_delivered}/{result.send_items_attempted}"
            + (f" · send_block={result.send_block_reason}" if result.send_block_reason else "")
        ),
        (
            f"cycle_completed={str(result.cycle_completed).lower()} · "
            f"partial_results={str(result.partial_results).lower()}"
        ),
        (
            f"artifact_writes: hypotheses={result.hypothesis_rows_written} "
            f"success={str(result.hypothesis_write_success).lower()} · "
            f"incidents={result.incident_rows_written} "
            f"success={str(result.incident_write_success).lower()} · "
            f"snapshots={result.snapshot_rows_written} "
            f"success={str(result.snapshot_write_success).lower()}"
        ),
    ]
    if result.warnings:
        lines.append("warnings: " + "; ".join(result.warnings))
    if result.catalyst_search_result is not None:
        lines.append("")
        lines.append(event_catalyst_search.format_catalyst_search_report(result.catalyst_search_result))
    if result.hypothesis_search_result is not None:
        lines.append("")
        lines.append("Impact hypothesis validation search:")
        lines.append(event_catalyst_search.format_catalyst_search_report(result.hypothesis_search_result))
    if result.anomaly_lifecycle_result is not None:
        lines.append("")
        lines.append(event_anomaly_state.format_anomaly_lifecycle_report(result.anomaly_lifecycle_result))
    if result.evidence_acquisition_result is not None and result.evidence_acquisition_result.results:
        lines.append("")
        lines.append("Evidence acquisition execution:")
        lines.append(event_evidence_acquisition.format_acquisition_report(
            event_evidence_acquisition._artifact_row(result_item, context={}, observed_at="")
            for result_item in result.evidence_acquisition_result.results
        ))
    if result.impact_hypotheses:
        lines.append("")
        lines.append(event_impact_hypotheses.format_impact_hypothesis_report(result.impact_hypotheses))
    if result.watchlist_monitor_result is not None:
        lines.append("")
        lines.append(event_watchlist_monitor.format_watchlist_monitor_report(result.watchlist_monitor_result))
    lines.append("")
    lines.append(_tier_summary(result.alerts))
    if result.router_result is not None:
        lines.append(_route_summary(result.router_result))
    if result.watchlist_result is not None and result.watchlist_result.alert_entries:
        lines.append("")
        lines.append("Watchlist escalations:")
        for entry in result.watchlist_result.alert_entries[:10]:
            lines.append(
                f"- {entry.state} {entry.symbol}/{entry.coin_id} "
                f"score={entry.latest_score} playbook={entry.latest_playbook_type or 'unknown'}"
            )
    elif result.watchlist_result is not None and result.watchlist_result.entries:
        lines.append("")
        lines.append("Watchlist sample:")
        for entry in result.watchlist_result.entries[:5]:
            lines.append(
                f"- {entry.state} {entry.symbol}/{entry.coin_id} "
                f"score={entry.latest_score} playbook={entry.latest_playbook_type or 'unknown'}"
            )
    if result.router_result is not None and result.router_result.alertable_decisions:
        lines.append("")
        lines.append("Alertable route decisions:")
        for decision in result.router_result.alertable_decisions[:10]:
            entry = decision.entry
            lines.append(
                f"- {decision.route.value} {entry.symbol}/{entry.coin_id} "
                f"state={entry.state} score={entry.latest_score} reason={decision.reason}"
            )
    return "\n".join(lines).rstrip()


def _tier_summary(alerts: Iterable[event_alerts.EventAlertCandidate]) -> str:
    counts: dict[str, int] = {}
    for alert in alerts:
        counts[alert.tier.value] = counts.get(alert.tier.value, 0) + 1
    if not counts:
        return "alert_tiers: none"
    return "alert_tiers: " + ", ".join(f"{tier}={count}" for tier, count in sorted(counts.items()))


def _route_summary(result: event_alpha_router.EventAlphaRouterResult) -> str:
    counts: dict[str, int] = {}
    for decision in result.decisions:
        counts[decision.route.value] = counts.get(decision.route.value, 0) + 1
    if not counts:
        return "routes: none"
    return "routes: " + ", ".join(f"{route}={count}" for route, count in sorted(counts.items()))


def _query_type_summary(queries: Iterable[object]) -> str:
    counts: dict[str, int] = {}
    for query in queries:
        query_type = str(getattr(query, "query_type", "") or "candidate_validation")
        counts[query_type] = counts.get(query_type, 0) + 1
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
