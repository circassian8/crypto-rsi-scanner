"""Readiness report for daily burn-in candidate mode."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

from . import common

READINESS_JSON = "event_alpha_daily_burn_in_readiness.json"
READINESS_MD = "event_alpha_daily_burn_in_readiness.md"


def build_readiness_report(
    *,
    profile: str = "live_burn_in_no_send",
    artifact_namespace: str | None = None,
    base_dir: str | Path | None = None,
) -> dict[str, Any]:
    from . import daily_burn_in

    namespace = artifact_namespace or profile
    context = common.context_for(profile=profile, artifact_namespace=namespace, base_dir=base_dir)
    provider_status = daily_burn_in._candidate_provider_status(context)
    configured = sorted(key for key, row in provider_status.items() if row.get("configured"))
    missing = sorted(key for key, row in provider_status.items() if row.get("status") == "skipped_missing_config")
    allow_flags = {key: bool(row.get("allow_flag_set")) for key, row in provider_status.items()}
    live_allowed = sorted(key for key, row in provider_status.items() if row.get("live_call_allowed"))
    request_ledgers_writable = _request_ledgers_writable(context, provider_status)
    doctor_status = daily_burn_in._doctor_status_payload(context).get("status") or "not_run"
    doctor_blocked = str(doctor_status) in {"blocked", "failed", "strict_blockers"}
    ready_providers = sorted(
        key for key in live_allowed
        if request_ledgers_writable.get(key) and not doctor_blocked
    )
    config_ready_no_live = sorted(
        key for key, row in provider_status.items()
        if row.get("configured") and key not in ready_providers
    )
    missing_allow = sorted(
        key for key, row in provider_status.items()
        if row.get("configured") and row.get("allow_flag_set") is not True
    )
    any_ready = bool(ready_providers)
    all_ready = bool(provider_status) and all(
        key in ready_providers for key in provider_status
    )
    fastest_ready_provider = _fastest_config_ready_provider(
        provider_status,
        ready_providers=ready_providers,
    )
    ready_status = _candidate_mode_ready_status(
        provider_status=provider_status,
        missing=missing,
        live_allowed=live_allowed,
        request_ledgers_writable=request_ledgers_writable,
        doctor_status=str(doctor_status),
    )
    candidate_status = _legacy_candidate_status(ready_status, mocked=daily_burn_in._env_truthy("RSI_EVENT_ALPHA_DAILY_BURN_IN_MOCK_PROVIDER_FIXTURES"))
    payload = common.with_safety(
        {
            "schema_version": "event_alpha_daily_burn_in_readiness_v1",
            "row_type": "event_alpha_daily_burn_in_readiness",
            "generated_at": common.utc_now().isoformat(),
            "profile": profile,
            "artifact_namespace": namespace,
            "namespace_dir": common.rel_path(context.namespace_dir),
            "can_run_default_preflight_mode": True,
            "can_run_candidate_mode": any_ready,
            "candidate_mode_ready_with_any_provider": any_ready,
            "candidate_mode_ready_with_all_priority_providers": all_ready,
            "fastest_ready_provider": fastest_ready_provider,
            "providers_config_ready_no_live": config_ready_no_live,
            "providers_missing_config": missing,
            "providers_missing_allow_flag": missing_allow,
            "candidate_mode_status": candidate_status,
            "candidate_mode_ready_status": ready_status,
            "configured_providers": configured,
            "missing_config": missing,
            "allow_flags_set": allow_flags,
            "request_ledgers_writable": request_ledgers_writable,
            "expected_live_calls_default": 0,
            "expected_live_calls_candidate_mode": {key: int(row.get("request_budget") or 0) for key, row in provider_status.items() if row.get("live_call_allowed")},
            "no_send_guard_status": "enabled_no_send",
            "telegram_send_guard_status": "disabled_by_RSI_EVENT_ALERTS_ENABLED_0",
            "artifact_doctor_recent_status": doctor_status,
            "provider_activation_status": provider_status,
            "next_safe_command": _readiness_next_command(ready_status),
            "next_safe_commands": _next_safe_commands(
                profile=profile,
                any_ready=any_ready,
                ready_providers=ready_providers,
                missing_config=missing,
                missing_allow=missing_allow,
            ),
            "next_steps": daily_burn_in._candidate_mode_next_steps(provider_status),
        }
    )
    common.write_json(context.namespace_dir / READINESS_JSON, payload)
    common.write_text(context.namespace_dir / READINESS_MD, format_readiness_report(payload))
    return payload


def format_readiness_report(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Event Alpha Daily Burn-In Readiness",
        "",
        "Research-only readiness report. No live calls are made by this command.",
        "",
        f"- can_run_default_preflight_mode: `{payload.get('can_run_default_preflight_mode')}`",
        f"- can_run_candidate_mode: `{payload.get('can_run_candidate_mode')}`",
        f"- candidate_mode_ready_with_any_provider: `{payload.get('candidate_mode_ready_with_any_provider')}`",
        f"- candidate_mode_ready_with_all_priority_providers: `{payload.get('candidate_mode_ready_with_all_priority_providers')}`",
        f"- fastest_ready_provider: `{payload.get('fastest_ready_provider') or 'none'}`",
        f"- providers_config_ready_no_live: `{', '.join(payload.get('providers_config_ready_no_live') or []) or 'none'}`",
        f"- providers_missing_config: `{', '.join(payload.get('providers_missing_config') or []) or 'none'}`",
        f"- providers_missing_allow_flag: `{', '.join(payload.get('providers_missing_allow_flag') or []) or 'none'}`",
        f"- candidate_mode_status: `{payload.get('candidate_mode_status')}`",
        f"- candidate_mode_ready_status: `{payload.get('candidate_mode_ready_status')}`",
        f"- configured_providers: `{', '.join(payload.get('configured_providers') or []) or 'none'}`",
        f"- missing_config: `{', '.join(payload.get('missing_config') or []) or 'none'}`",
        f"- allow_flags_set: `{payload.get('allow_flags_set')}`",
        f"- request_ledgers_writable: `{payload.get('request_ledgers_writable')}`",
        f"- expected_live_calls_default: `{payload.get('expected_live_calls_default')}`",
        f"- expected_live_calls_candidate_mode: `{payload.get('expected_live_calls_candidate_mode')}`",
        f"- no_send_guard_status: `{payload.get('no_send_guard_status')}`",
        f"- telegram_send_guard_status: `{payload.get('telegram_send_guard_status')}`",
        f"- artifact_doctor_recent_status: `{payload.get('artifact_doctor_recent_status')}`",
        f"- next_safe_command: `{payload.get('next_safe_command')}`",
        "- next_safe_commands:",
    ]
    lines.extend(f"  {index}. `{command}`" for index, command in enumerate(payload.get("next_safe_commands") or (), start=1))
    return "\n".join(lines).rstrip()


def _request_ledgers_writable(context: Any, provider_status: Mapping[str, Mapping[str, Any]]) -> dict[str, bool]:
    result: dict[str, bool] = {}
    context.namespace_dir.mkdir(parents=True, exist_ok=True)
    for key, row in provider_status.items():
        rel = str(row.get("request_ledger_path") or "")
        path = context.namespace_dir / Path(rel).name if rel else context.namespace_dir / f"{key}_request_ledger.jsonl"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            result[key] = os.access(path.parent, os.W_OK)
        except OSError:
            result[key] = False
    return result


def _candidate_mode_ready_status(
    *,
    provider_status: Mapping[str, Mapping[str, Any]],
    missing: list[str],
    live_allowed: list[str],
    request_ledgers_writable: Mapping[str, bool],
    doctor_status: str,
) -> str:
    if doctor_status in {"blocked", "failed", "strict_blockers"}:
        return "blocked_by_doctor"
    if not provider_status:
        return "no_candidate_providers_configured"
    if live_allowed and all(request_ledgers_writable.get(key) for key in live_allowed):
        return "ready_for_bounded_no_send_rehearsal"
    configured_without_live = [key for key, row in provider_status.items() if row.get("configured") and not row.get("live_call_allowed")]
    if configured_without_live:
        return "config_ready_no_live"
    return "no_candidate_providers_configured"


def _legacy_candidate_status(status: str, *, mocked: bool) -> str:
    if status == "ready_for_bounded_no_send_rehearsal":
        return "ready_for_mocked_candidate_mode" if mocked else "ready_for_guarded_candidate_mode"
    if status == "blocked_by_missing_config":
        return "missing_config"
    if status == "config_ready_no_live":
        return "blocked_by_default"
    return status


def _readiness_next_command(status: str) -> str:
    if status == "ready_for_bounded_no_send_rehearsal":
        return "make event-alpha-daily-live-no-send-burn-in CANDIDATE_MODE=1 PYTHON=python3"
    if status == "blocked_by_missing_config":
        return "make event-alpha-daily-burn-in-readiness PYTHON=python3"
    return "make event-alpha-daily-live-no-send-burn-in-plan CANDIDATE_MODE=1 PYTHON=python3"


def _fastest_config_ready_provider(
    provider_status: Mapping[str, Mapping[str, Any]],
    *,
    ready_providers: list[str],
) -> str | None:
    for key in ("bybit_announcements", "coinalyze"):
        if key in ready_providers:
            return key
    for key in ("bybit_announcements", "coinalyze"):
        row = provider_status.get(key) or {}
        if row.get("configured"):
            return key
    return next(
        (key for key, row in sorted(provider_status.items()) if row.get("configured")),
        None,
    )


def _next_safe_commands(
    *,
    profile: str,
    any_ready: bool,
    ready_providers: list[str],
    missing_config: list[str],
    missing_allow: list[str],
) -> list[str]:
    commands: list[str] = []
    if "bybit_announcements" in ready_providers:
        commands.append(
            f"make event-alpha-daily-live-no-send-burn-in CANDIDATE_MODE=1 PROFILE={profile} PYTHON=python3"
        )
    else:
        commands.append(f"make event-alpha-bybit-announcements-preflight PROFILE={profile} PYTHON=python3")
    if "bybit_announcements" in missing_allow:
        commands.append(
            "set RSI_EVENT_ALPHA_BYBIT_ANNOUNCEMENTS_ALLOW_LIVE_PREFLIGHT=1 manually only after approving the Bybit no-send preflight"
        )
    if "coinalyze" in missing_config:
        commands.append(
            "configure RSI_EVENT_DISCOVERY_COINALYZE_API_KEY locally; never write the key to artifacts"
        )
    elif "coinalyze" in missing_allow:
        commands.append(
            "set RSI_EVENT_ALPHA_COINALYZE_ALLOW_LIVE_PREFLIGHT=1 manually only after approving the Coinalyze no-send preflight"
        )
    if any_ready and "bybit_announcements" not in ready_providers:
        commands.insert(
            0,
            f"make event-alpha-daily-live-no-send-burn-in CANDIDATE_MODE=1 PROFILE={profile} PYTHON=python3",
        )
    commands.append(f"make event-alpha-daily-burn-in-readiness PROFILE={profile} PYTHON=python3")
    return commands
