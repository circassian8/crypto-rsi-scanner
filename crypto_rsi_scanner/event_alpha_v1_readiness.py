"""Event Alpha v1 readiness gates for local research artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from . import event_alpha_artifacts, event_alpha_burn_in, event_alpha_burn_in_checklist, event_alpha_profiles


@dataclass(frozen=True)
class EventAlphaV1ProfileReadiness:
    profile: str
    successful_runs: int
    latest_run_at: str | None
    ready_for_research_send: bool
    ready_for_full_llm_live: bool
    ready_for_scheduled_burn_in: bool
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    recommended_commands: tuple[str, ...] = ()


@dataclass(frozen=True)
class EventAlphaV1ReadinessResult:
    generated_at: str
    ready_for_research_send: bool
    ready_for_full_llm_live: bool
    ready_for_scheduled_burn_in: bool
    profiles: tuple[EventAlphaV1ProfileReadiness, ...]
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
    card_paths: Iterable[str] = (),
    days: int = 7,
    now: datetime | None = None,
    profiles: Iterable[str] | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
) -> EventAlphaV1ReadinessResult:
    """Build explicit v1 readiness flags without mutating runtime behavior."""
    observed = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    run_data = event_alpha_artifacts.filter_artifact_rows(
        run_rows,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
    )
    alert_data = event_alpha_artifacts.filter_artifact_rows(
        alert_rows,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
    )
    feedback_data = event_alpha_artifacts.filter_artifact_rows(
        feedback_rows,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
    )
    missed_data = event_alpha_artifacts.filter_artifact_rows(
        missed_rows,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
    )
    outcome_data = event_alpha_artifacts.filter_artifact_rows(
        outcome_rows,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
    )
    budget_data = event_alpha_artifacts.filter_artifact_rows(
        llm_budget_rows,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
    )
    profile_names = tuple(profiles or ("no_key_live", "research_send", "full_llm_live"))
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
            card_paths=tuple(card_paths),
            days=days,
            now=observed,
            artifact_namespace=artifact_namespace,
            include_test_artifacts=include_test_artifacts,
        ))

    ready_send = any(row.ready_for_research_send for row in profile_rows)
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
        blockers.append("no Event Alpha run ledger rows found")
        commands.append("make event-alpha-cycle-profile PROFILE=no_key_live")
    if not ready_send:
        commands.append("make event-alpha-burn-in-checklist")
    if not ready_burn_in:
        commands.append("make event-alpha-health-guard PROFILE=no_key_live")
    return EventAlphaV1ReadinessResult(
        generated_at=observed.isoformat(),
        ready_for_research_send=ready_send,
        ready_for_full_llm_live=ready_llm,
        ready_for_scheduled_burn_in=ready_burn_in,
        profiles=tuple(profile_rows),
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
        f"READY_FOR_RESEARCH_SEND: {_yes_no(result.ready_for_research_send)}",
        f"READY_FOR_FULL_LLM_LIVE: {_yes_no(result.ready_for_full_llm_live)}",
        f"READY_FOR_SCHEDULED_BURN_IN: {_yes_no(result.ready_for_scheduled_burn_in)}",
        "",
        "profile matrix:",
    ]
    for row in result.profiles:
        lines.append(
            f"- {row.profile}: runs={row.successful_runs} latest={row.latest_run_at or 'none'} "
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
    card_paths: tuple[str, ...],
    days: int,
    now: datetime,
    artifact_namespace: str | None,
    include_test_artifacts: bool,
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
        profile=profile_name,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
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
    blockers = list(checklist.blockers)
    blockers.extend(provider_blockers)
    scheduled_ready = bool(matching_runs) and not provider_blockers
    research_send_ready = profile_name == "research_send" and checklist.ready_for_research_send and scheduled_ready
    full_llm_ready = (
        profile_name == "full_llm_live"
        and scheduled_ready
        and not provider_blockers
        and budget_skips == 0
    )
    commands = _commands_for_profile(profile_name, research_send_ready, full_llm_ready, scheduled_ready)
    try:
        event_alpha_profiles.get_profile(profile_name)
    except ValueError:
        blockers.append(f"unknown profile {profile_name}")
    return EventAlphaV1ProfileReadiness(
        profile=profile_name,
        successful_runs=len(matching_runs),
        latest_run_at=latest,
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
