"""Explain the most recent Event Alpha run in operator-friendly terms."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from . import event_alpha_artifacts, event_alpha_run_ledger


def format_last_run_explanation(
    run_rows: Iterable[Mapping[str, Any]],
    *,
    alert_rows: Iterable[Mapping[str, Any]] = (),
    requested_profile: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_legacy_artifacts: bool = False,
) -> str:
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
    lines = [
        "=" * 76,
        "EVENT ALPHA LAST RUN EXPLAINER (research-only)",
        "=" * 76,
    ]
    if not runs:
        lines.append("No Event Alpha run ledger rows found.")
        if requested_profile and legacy_available and not include_legacy_artifacts:
            lines.append("Legacy/default rows exist but were ignored for this profile-specific explanation.")
        lines.append("Run `make event-alpha-cycle-profile PROFILE=no_key_live` to create a research cycle row.")
        return "\n".join(lines)
    last = event_alpha_run_ledger.latest_run(runs, requested_profile) or runs[0]
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
        f"raw_events={_int(last.get('raw_events'))} · market_anomalies={_int(last.get('market_anomalies'))}",
        f"catalyst_queries={_int(last.get('catalyst_queries'))} · accepted={_int(last.get('catalyst_results_accepted'))} · rejected={_int(last.get('catalyst_results_rejected'))}",
        f"extraction_rows={_int(last.get('extraction_rows'))} · extraction_hints_applied={_int(last.get('extraction_hints_applied'))}",
        f"candidates={_int(last.get('candidates'))} · alerts={_int(last.get('alerts'))}",
        f"watchlist_entries={_int(last.get('watchlist_entries'))} · escalations={_int(last.get('watchlist_escalations'))}",
        f"routed={_int(last.get('routed'))} · alertable={_int(last.get('alertable'))}",
        f"send_requested={str(bool(last.get('send_requested'))).lower()} · send_attempted={str(bool(last.get('send_attempted'))).lower()} · sent={str(bool(last.get('sent'))).lower()}",
    ])
    if last.get("send_block_reason"):
        lines.append(f"send block reason: {last.get('send_block_reason')}")
    lines.append(
        "LLM budget/cache: "
        f"cache={_int(last.get('llm_cache_hits'))}/{_int(last.get('llm_cache_misses'))} "
        f"calls={_int(last.get('llm_calls_attempted'))} skipped_budget={_int(last.get('llm_skipped_due_budget'))}"
    )
    mismatch = event_alpha_run_ledger.run_profile_mismatch_warning(requested_profile, last)
    if mismatch:
        lines.append(f"profile warning: {mismatch}")
    warnings = [str(item) for item in last.get("warnings") or [] if str(item)]
    if warnings:
        lines.append("warnings: " + "; ".join(warnings[:8]))
    lines.append("")
    lines.append("suppression path:")
    lines.extend(_suppression_lines(last, alerts))
    lines.append("No alerts, paper trades, live DB rows, or execution were changed by this report.")
    return "\n".join(lines).rstrip()


def _suppression_lines(run: Mapping[str, Any], alerts: list[Mapping[str, Any]]) -> list[str]:
    if _int(run.get("raw_events")) == 0 and _int(run.get("market_anomalies")) == 0:
        return ["- no source events or market anomalies reached discovery; check provider/profile status"]
    if _int(run.get("candidates")) == 0:
        return ["- source evidence existed, but resolver/classifier gates produced zero candidates"]
    if _int(run.get("alerts")) == 0:
        return ["- candidates existed, but alert tiering suppressed every row"]
    if _int(run.get("routed")) == 0:
        return ["- alerts existed, but watchlist/router did not run or produced no decisions"]
    if _int(run.get("alertable")) == 0:
        reasons = _top_rejected_or_store_reasons(alerts)
        out = ["- router produced no alertable decisions; most rows were duplicates, store-only, cooled down, or below escalation rules"]
        if reasons:
            out.append("- top alert suppression reasons: " + "; ".join(reasons))
        return out
    if run.get("send_requested") and not run.get("sent"):
        return [f"- alertable decisions existed, but send was blocked: {run.get('send_block_reason') or 'unknown'}"]
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
