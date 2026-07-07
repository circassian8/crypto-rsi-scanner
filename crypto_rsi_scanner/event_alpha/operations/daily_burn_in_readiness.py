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
    if live_allowed and all(request_ledgers_writable.values()):
        candidate_status = "ready_for_mocked_candidate_mode" if daily_burn_in._env_truthy("RSI_EVENT_ALPHA_DAILY_BURN_IN_MOCK_PROVIDER_FIXTURES") else "ready_for_guarded_candidate_mode"
    elif missing:
        candidate_status = "missing_config"
    else:
        candidate_status = "blocked_by_default"
    payload = common.with_safety(
        {
            "schema_version": "event_alpha_daily_burn_in_readiness_v1",
            "row_type": "event_alpha_daily_burn_in_readiness",
            "generated_at": common.utc_now().isoformat(),
            "profile": profile,
            "artifact_namespace": namespace,
            "namespace_dir": common.rel_path(context.namespace_dir),
            "can_run_default_preflight_mode": True,
            "can_run_candidate_mode": bool(live_allowed and all(request_ledgers_writable.values())),
            "candidate_mode_status": candidate_status,
            "configured_providers": configured,
            "missing_config": missing,
            "allow_flags_set": allow_flags,
            "request_ledgers_writable": request_ledgers_writable,
            "expected_live_calls_default": 0,
            "expected_live_calls_candidate_mode": {key: int(row.get("request_budget") or 0) for key, row in provider_status.items() if row.get("live_call_allowed")},
            "no_send_guard_status": "enabled_no_send",
            "telegram_send_guard_status": "disabled_by_RSI_EVENT_ALERTS_ENABLED_0",
            "artifact_doctor_recent_status": daily_burn_in._doctor_status_payload(context).get("status") or "not_run",
            "provider_activation_status": provider_status,
            "next_safe_command": _readiness_next_command(candidate_status),
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
        f"- candidate_mode_status: `{payload.get('candidate_mode_status')}`",
        f"- configured_providers: `{', '.join(payload.get('configured_providers') or []) or 'none'}`",
        f"- missing_config: `{', '.join(payload.get('missing_config') or []) or 'none'}`",
        f"- expected_live_calls_default: `{payload.get('expected_live_calls_default')}`",
        f"- expected_live_calls_candidate_mode: `{payload.get('expected_live_calls_candidate_mode')}`",
        f"- no_send_guard_status: `{payload.get('no_send_guard_status')}`",
        f"- telegram_send_guard_status: `{payload.get('telegram_send_guard_status')}`",
        f"- artifact_doctor_recent_status: `{payload.get('artifact_doctor_recent_status')}`",
        f"- next_safe_command: `{payload.get('next_safe_command')}`",
    ]
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


def _readiness_next_command(status: str) -> str:
    if status == "ready_for_mocked_candidate_mode":
        return "make event-alpha-daily-live-no-send-burn-in-candidate-mode-smoke PYTHON=python3"
    if status == "ready_for_guarded_candidate_mode":
        return "make event-alpha-daily-live-no-send-burn-in CANDIDATE_MODE=1 PYTHON=python3"
    return "make event-alpha-daily-live-no-send-burn-in-plan CANDIDATE_MODE=1 PYTHON=python3"
