"""Explain the most recent Event Alpha run in operator-friendly terms."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

import crypto_rsi_scanner.event_alpha.artifacts.context as event_alpha_artifacts
import crypto_rsi_scanner.event_alpha.artifacts.run_counters as event_alpha_run_counters
import crypto_rsi_scanner.event_alpha.artifacts.run_ledger as event_alpha_run_ledger


def format_last_run_explanation(
    run_rows: Iterable[Mapping[str, Any]],
    *,
    alert_rows: Iterable[Mapping[str, Any]] = (),
    requested_profile: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_api_artifacts: bool = False,
) -> str:
    raw_runs = [dict(row) for row in run_rows if isinstance(row, Mapping)]
    legacy_available = any(event_alpha_artifacts.is_api_row(row) for row in raw_runs)
    runs = event_alpha_artifacts.filter_artifact_rows(
        raw_runs,
        profile=requested_profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_api_artifacts=include_api_artifacts,
    )
    alerts = event_alpha_artifacts.filter_artifact_rows(
        alert_rows,
        profile=requested_profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_api_artifacts=include_api_artifacts,
    )
    lines = [
        "=" * 76,
        "EVENT ALPHA LAST RUN EXPLAINER (research-only)",
        "=" * 76,
    ]
    if not runs:
        lines.append("No Event Alpha run ledger rows found.")
        if requested_profile and legacy_available and not include_api_artifacts:
            lines.append("Legacy/default rows exist but were ignored for this profile-specific explanation.")
        lines.append("Run `make event-alpha-cycle-profile PROFILE=no_key_live` to create a research cycle row.")
        return "\n".join(lines)
    last = event_alpha_run_ledger.latest_run(runs, requested_profile) or runs[0]
    counters = event_alpha_run_counters.canonical_run_counters(last)
    send_state = event_alpha_run_counters.canonical_send_state(last)
    selected_profile = str(last.get("profile") or "default")
    profile_match = (
        "n/a"
        if requested_profile is None
        else str(selected_profile == str(requested_profile)).lower()
    )
    lines.extend([
        f"run_id: {last.get('run_id') or 'unknown'}",
        f"requested_profile: {requested_profile or 'latest'}",
        f"selected_run_profile: {selected_profile}",
        f"profile_match: {profile_match}",
        f"profile: {last.get('profile') or 'default'} · success={str(bool(last.get('success'))).lower()}",
        f"counter_schema_version={event_alpha_run_counters.COUNTER_SCHEMA_VERSION}",
        f"raw_events={counters['raw_events']} · market_anomalies={_int(last.get('market_anomalies'))}",
        f"catalyst_queries={_int(last.get('catalyst_queries'))} · accepted={_int(last.get('catalyst_results_accepted'))} · rejected={_int(last.get('catalyst_results_rejected'))}",
        f"extraction_rows={_int(last.get('extraction_rows'))} · extraction_hints_applied={_int(last.get('extraction_hints_applied'))}",
        (
            f"candidate_events={counters['candidate_events']} · "
            f"research_candidates={counters['research_candidates']} · "
            f"source_alert_snapshots={counters['source_alert_snapshots']}"
        ),
        (
            f"current_generation_core_rows={counters['current_generation_core_rows']} · "
            f"current_generation_visible_core_rows={counters['current_generation_visible_core_rows']} · "
            f"cumulative_store_rows={counters['cumulative_store_rows']}"
        ),
        f"watchlist_entries={_int(last.get('watchlist_entries'))} · escalations={_int(last.get('watchlist_escalations'))}",
        (
            f"routed_decisions={_int(last.get('routed'))} · "
            f"alertable_decisions={counters['alertable_decisions']} · "
            f"strict_alerts={counters['strict_alerts']} · "
            f"preview_rendered_items={counters['preview_rendered_items']}"
        ),
        (
            f"burn_in_mode={send_state['burn_in_mode']} · "
            f"send_guard_status={send_state['send_guard_status']} · "
            f"send_requested={str(send_state['send_requested']).lower()} · "
            f"send_attempted={str(send_state['send_attempted']).lower()} · "
            f"no_send_rehearsal={str(send_state['no_send_rehearsal']).lower()} · "
            f"delivered={send_state['send_items_delivered']}"
        ),
    ])
    if last.get("send_block_reason"):
        lines.append(f"send block reason: {last.get('send_block_reason')}")
    lines.append(
        "LLM budget/cache: "
        f"cache={_int(last.get('llm_cache_hits'))}/{_int(last.get('llm_cache_misses'))} "
        f"calls={_int(last.get('llm_calls_attempted'))} failed={_int(last.get('llm_calls_failed'))} "
        f"skipped_budget={_int(last.get('llm_skipped_due_budget'))} "
        f"skipped_provider_backoff={_int(last.get('llm_skipped_due_provider_backoff'))}"
    )
    mismatch = event_alpha_run_ledger.run_profile_mismatch_warning(requested_profile, last)
    if mismatch:
        lines.append(f"profile warning: {mismatch}")
    warnings = [str(item) for item in last.get("warnings") or [] if str(item)]
    if warnings:
        lines.append("warnings: " + "; ".join(warnings[:8]))
    lines.append("")
    lines.append("suppression path:")
    lines.extend(_suppression_lines(last, alerts, counters=counters))
    lines.append(
        "No source-alert snapshots, strict-alert decisions, paper trades, live DB rows, "
        "or execution were changed by this report."
    )
    return "\n".join(lines).rstrip()


def _suppression_lines(
    run: Mapping[str, Any],
    alerts: list[Mapping[str, Any]],
    *,
    counters: Mapping[str, int] | None = None,
) -> list[str]:
    scoped = dict(counters or event_alpha_run_counters.canonical_run_counters(run))
    if scoped["raw_events"] == 0 and _int(run.get("market_anomalies")) == 0:
        return ["- no source events or market anomalies reached discovery; check provider/profile status"]
    if scoped["candidate_events"] == 0:
        return ["- source evidence existed, but resolver/classifier gates produced zero candidate events"]
    if scoped["research_candidates"] == 0:
        return ["- candidate events existed, but research-selection gates produced zero research candidates"]
    if _int(run.get("routed")) == 0:
        return ["- research candidates existed, but watchlist/router did not run or produced no route decisions"]
    if scoped["alertable_decisions"] == 0:
        reasons = _top_rejected_or_store_reasons(alerts)
        out = ["- router produced no alertable decisions; most rows were duplicates, store-only, cooled down, or below escalation rules"]
        if reasons:
            out.append("- top route suppression reasons: " + "; ".join(reasons))
        return out
    if run.get("send_requested") and not run.get("sent"):
        return [f"- alertable decisions existed, but send was blocked: {run.get('send_block_reason') or 'unknown'}"]
    if scoped["strict_alerts"] == 0:
        return ["- alertable decisions existed, but none qualified as strict alerts; inspect scoped preview lanes"]
    return ["- alertable route decisions existed; inspect router and alert snapshot reports for details"]


def _top_rejected_or_store_reasons(alerts: list[Mapping[str, Any]]) -> list[str]:
    counts: dict[str, int] = {}
    for row in alerts:
        reason = str(row.get("rejected_reason") or row.get("suppressed_reason") or "")
        if not reason and str(row.get("tier") or "") == "STORE_ONLY":
            reason = "store_only"
        if reason:
            counts[reason] = counts.get(reason, 0) + 1
    return [f"{reason}={count}" for reason, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:5]]


def _int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
