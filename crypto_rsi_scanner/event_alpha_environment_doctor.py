"""Profile-aware environment doctor for scheduled Event Alpha notifications."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class EnvironmentCheck:
    name: str
    status: str
    detail: str


@dataclass(frozen=True)
class EventAlphaEnvironmentDoctorResult:
    profile: str
    artifact_namespace: str
    ready_for_scheduled_notify: bool
    python_executable: str
    working_directory: str
    checks: tuple[EnvironmentCheck, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    next_commands: tuple[str, ...]


def build_environment_doctor(
    *,
    profile: Any,
    context: Any,
    provider_status: Any,
    provider_health_rows: Mapping[str, Mapping[str, Any]],
    lock_path: str | Path,
    delivery_ledger_path: str | Path,
    notification_runs_path: str | Path,
    research_cards_dir: str | Path,
    telegram_token_present: bool,
    telegram_chat_ids_present: bool,
    send_guard_enabled: bool,
    llm_provider: str,
    llm_enabled: bool,
    llm_extractor_provider: str,
    llm_extractor_enabled: bool,
    openai_key_present: bool,
    clock_status: Mapping[str, Any],
    python_executable: str | None = None,
    working_directory: str | None = None,
) -> EventAlphaEnvironmentDoctorResult:
    """Build a redacted readiness report for scheduled notification targets."""
    prof_name = str(getattr(profile, "name", profile or "default"))
    namespace = str(getattr(context, "artifact_namespace", prof_name) or prof_name)
    is_send_profile = bool(getattr(profile, "send", False) or getattr(profile, "notification_burn_in", False))
    blockers: list[str] = []
    warnings: list[str] = []
    checks: list[EnvironmentCheck] = []

    _add_check(checks, "python", bool(python_executable or sys.executable), python_executable or sys.executable)
    cwd = working_directory or os.getcwd()
    _add_check(checks, "working_directory", Path(cwd).exists(), cwd)
    _add_check(checks, "profile", bool(prof_name), prof_name)
    _path_check(checks, blockers, "artifact_namespace_dir", Path(getattr(context, "namespace_dir", ".")), is_dir=True)
    _path_check(checks, blockers, "run_lock_path", Path(lock_path), is_dir=False)
    _path_check(checks, blockers, "delivery_ledger", Path(delivery_ledger_path), is_dir=False)
    _path_check(checks, blockers, "notification_runs", Path(notification_runs_path), is_dir=False)
    _path_check(checks, blockers, "research_cards", Path(research_cards_dir), is_dir=True)

    if is_send_profile and not telegram_token_present:
        blockers.append("TELEGRAM_BOT_TOKEN missing for notification profile")
    if is_send_profile and not telegram_chat_ids_present:
        blockers.append("TELEGRAM_CHAT_IDS missing for notification profile")
    if is_send_profile and not send_guard_enabled:
        blockers.append("RSI_EVENT_ALERTS_ENABLED is not set")
    _add_check(checks, "telegram_token", telegram_token_present, "present" if telegram_token_present else "missing")
    _add_check(checks, "telegram_chat_ids", telegram_chat_ids_present, "present" if telegram_chat_ids_present else "missing")
    _add_check(checks, "send_guard", send_guard_enabled, "RSI_EVENT_ALERTS_ENABLED=1" if send_guard_enabled else "disabled")

    ready_sources = int(getattr(provider_status, "ready_event_source_count", 0) or 0)
    ready_enrichment = int(getattr(provider_status, "ready_enrichment_count", 0) or 0)
    if ready_sources <= 0:
        blockers.append("no active event sources configured")
    _add_check(checks, "event_sources", ready_sources > 0, f"ready={ready_sources}")
    _add_check(checks, "enrichment_sources", ready_enrichment > 0, f"ready={ready_enrichment}")

    backoff = sum(1 for row in provider_health_rows.values() if row.get("disabled_until"))
    if backoff:
        warnings.append(f"{backoff} provider(s) currently in backoff")
    _add_check(checks, "provider_backoff", backoff == 0, f"backoff={backoff}")

    llm_detail = f"relationship={llm_provider or 'unknown'} enabled={_yes_no(llm_enabled)} extractor={llm_extractor_provider or 'unknown'} enabled={_yes_no(llm_extractor_enabled)}"
    if prof_name == "notify_llm" and (llm_provider == "openai" or llm_extractor_provider == "openai") and not openai_key_present:
        blockers.append("OPENAI_API_KEY missing for notify_llm OpenAI provider")
    elif (llm_provider == "openai" or llm_extractor_provider == "openai") and not openai_key_present:
        warnings.append("OpenAI provider configured without OPENAI_API_KEY")
    _add_check(checks, "llm_provider", True, llm_detail)

    clock_warnings = tuple(str(item) for item in clock_status.get("warnings", ()) or ())
    if any("fixed_clock_blocks_notification_send" in item for item in clock_warnings):
        blockers.append("fixed research clock blocks scheduled notification sends")
    if clock_warnings:
        warnings.extend(clock_warnings)
    _add_check(checks, "clock", not clock_warnings, str(clock_status.get("now") or clock_status.get("observed_at") or "wall-clock"))

    next_commands = (
        f"make event-alpha-notify-go-no-go PROFILE={prof_name}",
        f"make event-alpha-scheduler-status PROFILE={prof_name}",
        f"make event-alpha-notification-slo-report PROFILE={prof_name}",
        _scheduled_target(prof_name),
    )
    clean_blockers = tuple(dict.fromkeys(blockers))
    return EventAlphaEnvironmentDoctorResult(
        profile=prof_name,
        artifact_namespace=namespace,
        ready_for_scheduled_notify=not clean_blockers,
        python_executable=str(python_executable or sys.executable),
        working_directory=str(cwd),
        checks=tuple(checks),
        blockers=clean_blockers,
        warnings=tuple(dict.fromkeys(warnings)),
        next_commands=next_commands,
    )


def format_environment_doctor(result: EventAlphaEnvironmentDoctorResult) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA ENVIRONMENT DOCTOR (scheduled research notifications)",
        "=" * 76,
        f"profile: {result.profile}",
        f"artifact_namespace: {result.artifact_namespace}",
        f"READY_FOR_SCHEDULED_NOTIFY: {_yes_no(result.ready_for_scheduled_notify)}",
        f"python: {result.python_executable}",
        f"cwd: {result.working_directory}",
        "",
        "checks:",
    ]
    for check in result.checks:
        lines.append(f"- {check.name}: {check.status} ({check.detail})")
    lines.append("")
    lines.append("blockers:")
    lines.extend(f"- {item}" for item in result.blockers) if result.blockers else lines.append("- none")
    lines.append("")
    lines.append("warnings:")
    lines.extend(f"- {item}" for item in result.warnings) if result.warnings else lines.append("- none")
    lines.append("")
    lines.append("next commands:")
    lines.extend(f"- {item}" for item in result.next_commands)
    lines.append("Doctor output is redacted and research-only; it does not send or trade.")
    return "\n".join(lines).rstrip()


def _path_check(checks: list[EnvironmentCheck], blockers: list[str], name: str, path: Path, *, is_dir: bool) -> None:
    ok = _path_writable(path.expanduser(), is_dir=is_dir)
    _add_check(checks, name, ok, str(path))
    if not ok:
        blockers.append(f"{name} is not writable")


def _path_writable(path: Path, *, is_dir: bool) -> bool:
    target = path if is_dir else path.parent
    current = target
    while not current.exists() and current != current.parent:
        current = current.parent
    return current.exists() and current.is_dir() and os.access(current, os.W_OK)


def _add_check(checks: list[EnvironmentCheck], name: str, ok: bool, detail: str) -> None:
    checks.append(EnvironmentCheck(name=name, status="ok" if ok else "blocked", detail=detail))


def _scheduled_target(profile: str) -> str:
    if profile == "notify_llm":
        return "RSI_EVENT_ALERTS_ENABLED=1 make event-alpha-notify-llm-scheduled"
    return "RSI_EVENT_ALERTS_ENABLED=1 make event-alpha-notify-no-key-scheduled"


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
