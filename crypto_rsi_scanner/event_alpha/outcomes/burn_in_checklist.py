"""Burn-in acceptance checklist for Event Alpha research-send readiness."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from crypto_rsi_scanner.event_alpha.outcomes import burn_in as event_alpha_burn_in


@dataclass(frozen=True)
class EventAlphaBurnInChecklist:
    ready_for_research_send: bool
    checks: dict[str, str] = field(default_factory=dict)
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    next_actions: tuple[str, ...] = ()


def build_burn_in_checklist(
    scorecard: event_alpha_burn_in.EventAlphaBurnInScorecard | Mapping[str, Any],
    *,
    card_paths: tuple[str, ...] = (),
    min_successful_runs: int = 1,
) -> EventAlphaBurnInChecklist:
    """Score local burn-in artifacts without mutating thresholds or routing."""
    if isinstance(scorecard, Mapping):
        return _build_contract_checklist(scorecard)

    checks: dict[str, str] = {}
    blockers: list[str] = []
    warnings: list[str] = []
    next_actions: list[str] = []

    successful = sum(1 for row in scorecard.run_rows if bool(row.get("success")))
    checks["successful_runs"] = f"{successful}/{max(1, min_successful_runs)}"
    if successful < max(1, min_successful_runs):
        blockers.append("no recent successful Event Alpha cycle runs")
        next_actions.append("run an Event Alpha burn-in cycle for the target profile")
    if scorecard.legacy_rows_skipped:
        warnings.append(f"legacy/default artifact rows ignored: {scorecard.legacy_rows_skipped}")
        next_actions.append("use namespaced burn-in commands before judging promotion readiness")
    if scorecard.test_rows_skipped:
        warnings.append(f"test/fixture/replay artifact rows ignored: {scorecard.test_rows_skipped}")

    checks["alert_snapshots"] = str(scorecard.alert_snapshot_rows)
    if scorecard.runs_with_alertable_but_no_alert_snapshots:
        blockers.append("alertable runs do not have alert snapshot artifacts")
        next_actions.append("fix alert snapshot storage before evaluating send readiness")

    checks["feedback_labels"] = str(scorecard.feedback_row_count)
    if scorecard.alert_snapshot_rows and scorecard.feedback_row_count == 0:
        blockers.append("no feedback labels collected for alert snapshots")
        next_actions.append("mark useful/junk/watch feedback for routed alerts")

    checks["outcome_rows"] = str(scorecard.outcome_row_count)
    if _needs_outcomes(scorecard) and scorecard.outcome_row_count == 0:
        blockers.append("matured alert snapshots do not have filled outcomes")
        next_actions.append("run the Event Alpha outcome fill/report workflow")

    checks["missed_rows"] = str(scorecard.missed_row_count)
    if scorecard.missed_row_count == 0:
        warnings.append("no missed-opportunity report rows in the burn-in window")
        next_actions.append("run the missed-opportunity report so recall gaps are visible")

    health_rows = scorecard.provider_health_rows
    checks["provider_health_rows"] = str(scorecard.provider_health_row_count)
    if scorecard.provider_health_row_count == 0:
        warnings.append("provider health artifact is missing")
        next_actions.append("run provider-aware status/cycle commands before judging live-source quality")
    for key, row in health_rows.items():
        failures = _int(row.get("consecutive_failures"))
        if row.get("disabled_until"):
            blockers.append(f"provider {row.get('provider_key') or key} is in backoff")
        elif failures:
            warnings.append(f"provider {row.get('provider_key') or key} has {failures} consecutive failure(s)")

    skipped_budget = sum(_int(row.get("skipped_due_budget")) for row in scorecard.llm_budget_rows)
    checks["llm_budget_skipped"] = str(skipped_budget)
    if skipped_budget:
        warnings.append("LLM calls were skipped due to budget caps")

    high_priority = _high_priority_alerts(scorecard.alert_rows)
    research_card_paths = tuple(path for path in card_paths if str(path).rsplit("/", 1)[-1] != "index.md")
    checks["high_priority_or_triggered_alerts"] = str(len(high_priority))
    checks["research_cards"] = str(len(research_card_paths))
    if high_priority and not research_card_paths:
        warnings.append("high-priority/triggered alert snapshots have no research cards")
        next_actions.append("write research cards for high-priority/triggered rows")

    if scorecard.coverage_warnings:
        warnings.extend(scorecard.coverage_warnings)

    if not high_priority:
        checks["high_priority_alert_absence"] = "not_blocking"

    ready = not blockers
    if ready and not next_actions:
        next_actions.append("continue burn-in and review calibration before enabling research_send")
    return EventAlphaBurnInChecklist(
        ready_for_research_send=ready,
        checks=checks,
        blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(dict.fromkeys(warnings)),
        next_actions=tuple(dict.fromkeys(next_actions)),
    )


def _build_contract_checklist(scorecard: Mapping[str, Any]) -> EventAlphaBurnInChecklist:
    """Evaluate the authoritative 30-day North Star burn-in contract."""

    contract = scorecard.get("contract") if isinstance(scorecard.get("contract"), Mapping) else {}
    checks = {
        "authoritative_scorecard": "event_alpha_burn_in_scorecard_v1",
        "window_days": f"{_int(scorecard.get('window_days'))}/{_int(contract.get('duration_days')) or 30}",
        "live_no_send_cycles": (
            f"{_int(scorecard.get('live_no_send_cycles_completed'))}/"
            f"{_int(contract.get('min_live_no_send_cycles'))}"
        ),
        "real_candidates": (
            f"{_int(scorecard.get('real_burn_in_candidate_count'))}/"
            f"{_int(contract.get('min_real_candidates'))}"
        ),
        "human_labels": (
            f"{_int(scorecard.get('labels_collected'))}/"
            f"{_int(contract.get('min_human_labels'))}"
        ),
        "labeled_near_misses": (
            f"{_int(scorecard.get('labeled_near_misses'))}/"
            f"{_int(contract.get('min_labeled_near_misses'))}"
        ),
        "outcome_rows": (
            f"{_int(scorecard.get('outcome_rows'))}/"
            f"{_int(contract.get('min_outcome_rows'))}"
        ),
        "burn_in_contract_enough_data": "yes" if scorecard.get("enough_data") is True else "no",
        "auto_apply_thresholds": "enabled" if scorecard.get("auto_apply_thresholds") is True else "disabled",
    }
    blockers = [
        f"burn-in contract threshold not met: {reason}"
        for reason in scorecard.get("enough_data_reasons") or ()
    ]
    if scorecard.get("auto_apply_thresholds") is True:
        blockers.append("auto_apply_thresholds must remain disabled")
    for field in (
        "telegram_sends",
        "trades_created",
        "paper_trades_created",
        "normal_rsi_signal_rows_written",
        "triggered_fade_created",
    ):
        if _int(scorecard.get(field)) > 0:
            blockers.append(f"safety invariant violated: {field}={_int(scorecard.get(field))}")

    lane_status = scorecard.get("promotion_freeze_status_by_lane")
    frozen_lanes = [
        str(lane)
        for lane, status in (lane_status.items() if isinstance(lane_status, Mapping) else ())
        if str(status).startswith("frozen")
    ]
    checks["promotion_lanes_frozen"] = str(len(frozen_lanes))
    if frozen_lanes and not blockers:
        blockers.append("promotion lanes remain frozen")

    next_actions = [
        "continue policy-scoped 30-day live no-send burn-in cycles",
        "collect human labels and mature near-miss/outcome rows before promotion review",
    ]
    next_command = str(scorecard.get("next_command") or "").strip()
    if next_command:
        next_actions.insert(0, next_command)
    warnings = tuple(str(item) for item in scorecard.get("warnings") or () if str(item))
    ready = scorecard.get("enough_data") is True and not blockers
    return EventAlphaBurnInChecklist(
        ready_for_research_send=ready,
        checks=checks,
        blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(dict.fromkeys(warnings)),
        next_actions=tuple(dict.fromkeys(next_actions)),
    )


def format_burn_in_checklist(checklist: EventAlphaBurnInChecklist) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA BURN-IN ACCEPTANCE CHECKLIST (research-only)",
        "=" * 76,
        f"READY_FOR_RESEARCH_SEND: {'yes' if checklist.ready_for_research_send else 'no'}",
        "",
        "checks:",
    ]
    if checklist.checks:
        lines.extend(f"- {key}: {value}" for key, value in sorted(checklist.checks.items()))
    else:
        lines.append("- none")
    lines.extend(["", "blockers:"])
    lines.extend(f"- {item}" for item in checklist.blockers) if checklist.blockers else lines.append("- none")
    lines.extend(["", "warnings:"])
    lines.extend(f"- {item}" for item in checklist.warnings) if checklist.warnings else lines.append("- none")
    lines.extend(["", "next actions:"])
    lines.extend(f"- {item}" for item in checklist.next_actions) if checklist.next_actions else lines.append("- none")
    lines.append("No sends, paper trades, live DB rows, normal RSI alerts, or execution were changed.")
    return "\n".join(lines).rstrip()


def _needs_outcomes(scorecard: event_alpha_burn_in.EventAlphaBurnInScorecard) -> bool:
    return any(
        str(row.get("tier") or "") in {"WATCHLIST", "HIGH_PRIORITY_WATCH", "TRIGGERED_FADE"}
        or str(row.get("route") or "") in {"RESEARCH_DIGEST", "HIGH_PRIORITY_RESEARCH", "TRIGGERED_FADE_RESEARCH"}
        for row in scorecard.alert_rows
    )


def _high_priority_alerts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row for row in rows
        if str(row.get("tier") or "") in {"HIGH_PRIORITY_WATCH", "TRIGGERED_FADE"}
        or str(row.get("route") or "") in {"HIGH_PRIORITY_RESEARCH", "TRIGGERED_FADE_RESEARCH"}
    ]


def _int(value: object) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0
