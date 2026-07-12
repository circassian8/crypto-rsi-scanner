"""Event Alpha v1 readiness gates for local research artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

import crypto_rsi_scanner.event_alpha.artifacts.context as event_alpha_artifacts
import crypto_rsi_scanner.event_alpha.outcomes.burn_in_checklist as event_alpha_burn_in_checklist
import crypto_rsi_scanner.event_alpha.config.profiles as event_alpha_profiles
from crypto_rsi_scanner.event_alpha.outcomes import burn_in as event_alpha_burn_in


@dataclass(frozen=True)
class EventAlphaV1ProfileReadiness:
    profile: str
    successful_runs: int
    latest_run_at: str | None
    ready_for_day1_notifications: bool
    ready_for_research_send: bool
    ready_for_full_llm_live: bool
    ready_for_scheduled_burn_in: bool
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    recommended_commands: tuple[str, ...] = ()


@dataclass(frozen=True)
class EventAlphaV1ReadinessResult:
    generated_at: str
    ready_for_day1_notifications: bool
    ready_for_research_send: bool
    ready_for_full_llm_live: bool
    ready_for_scheduled_burn_in: bool
    profiles: tuple[EventAlphaV1ProfileReadiness, ...]
    burn_in_contract_enough_data: bool | None = None
    burn_in_contract_reasons: tuple[str, ...] = ()
    promotion_freeze_status_by_lane: tuple[tuple[str, str], ...] = ()
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    recommended_commands: tuple[str, ...] = ()


def build_v1_readiness(
    *,
    run_rows: Iterable[Mapping[str, Any]] = (),
    alert_rows: Iterable[Mapping[str, Any]] = (),
    feedback_rows: Iterable[Mapping[str, Any]] = (),
    missed_rows: Iterable[Mapping[str, Any]] = (),
    provider_health_rows: Mapping[str, Mapping[str, Any]] | None = None,
    llm_budget_rows: Iterable[Mapping[str, Any]] = (),
    outcome_rows: Iterable[Mapping[str, Any]] = (),
    candidate_rows: Iterable[Mapping[str, Any]] = (),
    core_rows: Iterable[Mapping[str, Any]] = (),
    card_paths: Iterable[str] = (),
    days: int = 7,
    now: datetime | None = None,
    profiles: Iterable[str] | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_api_artifacts: bool = False,
    burn_in_contract_scorecard: Mapping[str, Any] | None = None,
) -> EventAlphaV1ReadinessResult:
    """Build explicit v1 readiness flags without mutating runtime behavior."""
    observed = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    run_data = event_alpha_artifacts.filter_artifact_rows(
        run_rows,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_api_artifacts=include_api_artifacts,
    )
    alert_data = event_alpha_artifacts.filter_artifact_rows(
        alert_rows,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_api_artifacts=include_api_artifacts,
    )
    feedback_data = event_alpha_artifacts.filter_artifact_rows(
        feedback_rows,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_api_artifacts=include_api_artifacts,
    )
    missed_data = event_alpha_artifacts.filter_artifact_rows(
        missed_rows,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_api_artifacts=include_api_artifacts,
    )
    outcome_data = event_alpha_artifacts.filter_artifact_rows(
        outcome_rows,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_api_artifacts=include_api_artifacts,
    )
    candidate_data = event_alpha_artifacts.filter_artifact_rows(
        candidate_rows,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_api_artifacts=include_api_artifacts,
    )
    core_data = event_alpha_artifacts.filter_artifact_rows(
        core_rows,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_api_artifacts=include_api_artifacts,
    )
    budget_data = event_alpha_artifacts.filter_artifact_rows(
        llm_budget_rows,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_api_artifacts=include_api_artifacts,
    )
    legacy_rows_available = any(
        event_alpha_artifacts.is_api_row(row)
        for row in run_rows
        if isinstance(row, Mapping)
    )
    profile_names = tuple(profiles or ("notify_no_key", "notify_llm", "no_key_live", "research_send", "full_llm_live"))
    profile_rows: list[EventAlphaV1ProfileReadiness] = []
    for profile_name in profile_names:
        profile_rows.append(_profile_readiness(
            profile_name,
            run_rows=run_data,
            alert_rows=alert_data,
            feedback_rows=feedback_data,
            missed_rows=missed_data,
            provider_health_rows=provider_health_rows or {},
            llm_budget_rows=budget_data,
            outcome_rows=outcome_data,
            candidate_rows=candidate_data,
            core_rows=core_data,
            card_paths=tuple(card_paths),
            days=days,
            now=observed,
            artifact_namespace=artifact_namespace,
            include_test_artifacts=include_test_artifacts,
            include_api_artifacts=include_api_artifacts,
        ))

    contract_scorecard = dict(burn_in_contract_scorecard or {})
    contract_enough_data = (
        contract_scorecard.get("enough_data") is True
        if contract_scorecard
        else None
    )
    contract_reasons = tuple(
        str(item) for item in contract_scorecard.get("enough_data_reasons") or () if str(item)
    )
    lane_status = contract_scorecard.get("promotion_freeze_status_by_lane")
    lane_status_rows = tuple(
        (str(lane), str(status))
        for lane, status in sorted(lane_status.items())
    ) if isinstance(lane_status, Mapping) else ()
    ready_day1 = any(row.ready_for_day1_notifications for row in profile_rows)
    ready_send = any(row.ready_for_research_send for row in profile_rows)
    if contract_enough_data is False:
        ready_send = False
    ready_llm = any(row.profile == "full_llm_live" and row.ready_for_full_llm_live for row in profile_rows)
    ready_burn_in = any(row.ready_for_scheduled_burn_in for row in profile_rows)
    blockers: list[str] = []
    warnings: list[str] = []
    commands: list[str] = []
    for row in profile_rows:
        blockers.extend(f"{row.profile}: {item}" for item in row.blockers)
        warnings.extend(f"{row.profile}: {item}" for item in row.warnings)
        commands.extend(row.recommended_commands)
    if not run_data:
        warnings.append("no Event Alpha run ledger rows found; calibrated research send still needs burn-in evidence")
        commands.append("make event-alpha-cycle-profile PROFILE=no_key_live")
        if legacy_rows_available and not include_api_artifacts:
            warnings.append("legacy/default run rows were ignored; run namespaced burn-in commands or pass --event-alpha-include-historical-artifacts for migration review")
    if not ready_send:
        commands.append("make event-alpha-burn-in-checklist")
    if not ready_burn_in:
        commands.append("make event-alpha-health-guard PROFILE=no_key_live")
    if contract_enough_data is False:
        blockers.append("authoritative 30-day burn-in contract is not mature")
    return EventAlphaV1ReadinessResult(
        generated_at=observed.isoformat(),
        ready_for_day1_notifications=ready_day1,
        ready_for_research_send=ready_send,
        ready_for_full_llm_live=ready_llm,
        ready_for_scheduled_burn_in=ready_burn_in,
        profiles=tuple(profile_rows),
        burn_in_contract_enough_data=contract_enough_data,
        burn_in_contract_reasons=contract_reasons,
        promotion_freeze_status_by_lane=lane_status_rows,
        blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(dict.fromkeys(warnings)),
        recommended_commands=tuple(dict.fromkeys(commands)),
    )


def format_v1_readiness_report(result: EventAlphaV1ReadinessResult) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA V1 READINESS (research-only)",
        "=" * 76,
        f"generated_at: {result.generated_at}",
        f"READY_TO_START_DAY1_NOTIFICATIONS: {_yes_no(result.ready_for_day1_notifications)}",
        f"READY_FOR_CALIBRATED_RESEARCH_SEND: {_yes_no(result.ready_for_research_send)}",
        f"READY_FOR_FULL_LLM_LIVE: {_yes_no(result.ready_for_full_llm_live)}",
        f"READY_FOR_SCHEDULED_BURN_IN: {_yes_no(result.ready_for_scheduled_burn_in)}",
        (
            "BURN_IN_CONTRACT_ENOUGH_DATA: "
            + (
                "unknown"
                if result.burn_in_contract_enough_data is None
                else _yes_no(result.burn_in_contract_enough_data)
            )
        ),
        "READY_FOR_TRADING: no (out of scope)",
        "Day-1 notifications are unvalidated research output; calibrated research send still requires burn-in evidence.",
        "",
        "profile matrix:",
    ]
    for row in result.profiles:
        lines.append(
            f"- {row.profile}: runs={row.successful_runs} latest={row.latest_run_at or 'none'} "
            f"day1_notifications={_yes_no(row.ready_for_day1_notifications)} "
            f"research_send={_yes_no(row.ready_for_research_send)} "
            f"full_llm_live={_yes_no(row.ready_for_full_llm_live)} "
            f"scheduled_burn_in={_yes_no(row.ready_for_scheduled_burn_in)}"
        )
        if row.blockers:
            lines.append("  blockers: " + "; ".join(row.blockers))
        if row.warnings:
            lines.append("  warnings: " + "; ".join(row.warnings[:6]))
    lines.extend(["", "blockers:"])
    lines.extend(f"- {item}" for item in result.blockers) if result.blockers else lines.append("- none")
    lines.extend(["", "warnings:"])
    lines.extend(f"- {item}" for item in result.warnings) if result.warnings else lines.append("- none")
    if result.burn_in_contract_reasons:
        lines.extend(["", "authoritative burn-in contract blockers:"])
        lines.extend(f"- {item}" for item in result.burn_in_contract_reasons)
    if result.promotion_freeze_status_by_lane:
        lines.extend(["", "promotion/freeze status by lane:"])
        lines.extend(f"- {lane}: {status}" for lane, status in result.promotion_freeze_status_by_lane)
    lines.extend(["", "recommended commands:"])
    lines.extend(f"- {item}" for item in result.recommended_commands) if result.recommended_commands else lines.append("- continue daily burn-in")
    lines.append("Readiness reports do not enable sends, change tiers, paper trade, write live signal rows, or execute.")
    return "\n".join(lines).rstrip()


def _profile_readiness(
    profile_name: str,
    *,
    run_rows: list[dict[str, Any]],
    alert_rows: Iterable[Mapping[str, Any]],
    feedback_rows: Iterable[Mapping[str, Any]],
    missed_rows: Iterable[Mapping[str, Any]],
    provider_health_rows: Mapping[str, Mapping[str, Any]],
    llm_budget_rows: Iterable[Mapping[str, Any]],
    outcome_rows: Iterable[Mapping[str, Any]],
    candidate_rows: Iterable[Mapping[str, Any]],
    core_rows: Iterable[Mapping[str, Any]],
    card_paths: tuple[str, ...],
    days: int,
    now: datetime,
    artifact_namespace: str | None,
    include_test_artifacts: bool,
    include_api_artifacts: bool,
) -> EventAlphaV1ProfileReadiness:
    matching_runs = [
        row for row in run_rows
        if _profile(row.get("profile")) == profile_name and bool(row.get("success"))
    ]
    scorecard = event_alpha_burn_in.build_burn_in_scorecard(
        run_rows=[row for row in run_rows if _profile(row.get("profile")) == profile_name],
        alert_rows=alert_rows,
        feedback_rows=feedback_rows,
        missed_rows=missed_rows,
        provider_health_rows=provider_health_rows,
        llm_budget_rows=llm_budget_rows,
        outcome_rows=outcome_rows,
        candidate_rows=candidate_rows,
        core_rows=core_rows,
        profile=profile_name,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_api_artifacts=include_api_artifacts,
        days=days,
        now=now,
    )
    checklist = event_alpha_burn_in_checklist.build_burn_in_checklist(scorecard, card_paths=card_paths)
    latest = max((str(row.get("started_at") or "") for row in matching_runs), default=None)
    provider_blockers = tuple(
        f"provider {row.get('provider_key') or key} in backoff"
        for key, row in provider_health_rows.items()
        if row.get("disabled_until")
    )
    budget_skips = sum(_int(row.get("skipped_due_budget")) for row in llm_budget_rows)
    warnings = list(checklist.warnings)
    if budget_skips:
        warnings.append("LLM budget skips observed")
    profile_is_notify = False
    try:
        profile = event_alpha_profiles.get_profile(profile_name)
        profile_is_notify = bool(profile.notification_burn_in)
    except ValueError:
        profile = None
    blockers = [] if profile_is_notify else list(checklist.blockers)
    if profile_is_notify and checklist.blockers:
        warnings.extend(f"calibrated burn-in blocker: {item}" for item in checklist.blockers)
    blockers.extend(provider_blockers)
    scheduled_ready = bool(matching_runs) and not provider_blockers
    day1_ready = profile_is_notify and scheduled_ready and not provider_blockers
    research_send_ready = profile_name == "research_send" and checklist.ready_for_research_send and scheduled_ready
    full_llm_ready = (
        profile_name == "full_llm_live"
        and scheduled_ready
        and not provider_blockers
        and budget_skips == 0
    )
    commands = _commands_for_profile(profile_name, research_send_ready, full_llm_ready, scheduled_ready)
    if profile is None:
        blockers.append(f"unknown profile {profile_name}")
    return EventAlphaV1ProfileReadiness(
        profile=profile_name,
        successful_runs=len(matching_runs),
        latest_run_at=latest,
        ready_for_day1_notifications=day1_ready,
        ready_for_research_send=research_send_ready,
        ready_for_full_llm_live=full_llm_ready,
        ready_for_scheduled_burn_in=scheduled_ready,
        blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(dict.fromkeys(warnings)),
        recommended_commands=commands,
    )


def _commands_for_profile(
    profile: str,
    research_send_ready: bool,
    full_llm_ready: bool,
    scheduled_ready: bool,
) -> tuple[str, ...]:
    if profile == "notify_no_key":
        return ("make event-alpha-notify-no-key",) if scheduled_ready else (
            "make event-alpha-preflight PROFILE=notify_no_key",
            "make event-alpha-notify-preview PROFILE=notify_no_key",
        )
    if profile == "notify_llm":
        return ("make event-alpha-notify-llm",) if scheduled_ready else (
            "make event-alpha-preflight PROFILE=notify_llm",
            "make event-alpha-notify-preview PROFILE=notify_llm",
        )
    if profile == "research_send":
        return ("RSI_EVENT_ALERTS_ENABLED=1 make event-alpha-daily-send PROFILE=research_send",) if research_send_ready else (
            "make event-alpha-burn-in-checklist",
            "make event-alpha-daily-brief PROFILE=research_send",
        )
    if profile == "full_llm_live":
        return ("make event-alpha-daily-llm-report PROFILE=full_llm_live",) if full_llm_ready else (
            "make event-alpha-health-guard PROFILE=full_llm_live",
            "make event-alpha-burn-in-llm",
        )
    return ("make event-alpha-burn-in-no-key",) if scheduled_ready else (
        f"make event-alpha-cycle-profile PROFILE={profile}",
        f"make event-alpha-health-guard PROFILE={profile}",
    )


def _profile(value: object) -> str:
    return str(value or "default").strip() or "default"


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _int(value: object) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0
