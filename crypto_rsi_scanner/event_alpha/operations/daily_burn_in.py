"""Daily no-send Event Alpha burn-in operating loop."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ... import config
from . import common


RUN_JSON = "event_alpha_daily_burn_in_run.json"
RUN_MD = "event_alpha_daily_burn_in_report.md"
CANDIDATE_MODE_MANIFEST_JSON = "event_alpha_candidate_mode_manifest.json"
COINALYZE_REQUEST_LEDGER = "event_coinalyze_request_ledger.jsonl"
BYBIT_REQUEST_LEDGER = "event_bybit_announcements_request_ledger.jsonl"
_TRUTHY = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class BurnInStep:
    name: str
    command: tuple[str, ...]
    required: bool = False
    timeout_seconds: float = 60.0


def default_namespace(now: datetime | None = None) -> str:
    stamp = (now or common.utc_now()).astimezone(timezone.utc).strftime("%Y%m%d")
    return f"live_burn_in_{stamp}"


def build_steps(
    *,
    python: str,
    profile: str,
    namespace: str,
    include_coinalyze_rehearsal: bool,
    smoke: bool = False,
    readiness_timeout_seconds: float = 60.0,
    integrated_timeout_seconds: float = 180.0,
    report_timeout_seconds: float = 60.0,
    doctor_timeout_seconds: float = 120.0,
    candidate_mode: bool = False,
    provider_status: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[BurnInStep | dict[str, Any], ...]:
    base = ("--event-alpha-profile", profile, "--event-alpha-artifact-namespace", namespace)
    if smoke:
        return (
            BurnInStep("burn_in_contract", (python, "-m", "crypto_rsi_scanner.project_health.radar_north_star", "--burn-in-contract-only"), timeout_seconds=report_timeout_seconds),
            BurnInStep("burn_in_smoke_fixture_step", (python, "-c", "print('burn_in_smoke_fixture_step: safe fixture-only runner check')"), required=True, timeout_seconds=report_timeout_seconds),
            BurnInStep("burn_in_scorecard", (python, "-m", "crypto_rsi_scanner.event_alpha.operations.scorecard", "--profile", profile, "--artifact-namespace", namespace), timeout_seconds=report_timeout_seconds),
        )
    steps: list[BurnInStep | dict[str, Any]] = [
        BurnInStep("burn_in_contract", (python, "-m", "crypto_rsi_scanner.project_health.radar_north_star", "--burn-in-contract-only"), timeout_seconds=report_timeout_seconds),
        BurnInStep("live_provider_readiness", (python, "main.py", "--event-alpha-live-provider-readiness", *base), timeout_seconds=readiness_timeout_seconds),
        BurnInStep("cryptopanic_preflight", (python, "main.py", "--event-alpha-cryptopanic-preflight", *base), timeout_seconds=readiness_timeout_seconds),
        BurnInStep("coinalyze_preflight", (python, "main.py", "--event-alpha-coinalyze-preflight", *base), timeout_seconds=readiness_timeout_seconds),
        _provider_step(
            provider_status,
            "coinalyze",
            default_skip={
                "name": "coinalyze_no_send_rehearsal",
                "status": "skipped",
                "required": False,
                "timeout_seconds": readiness_timeout_seconds,
                "skip_reason": "requires RSI_EVENT_ALPHA_DAILY_BURN_IN_ALLOW_COINALYZE_REHEARSAL=1 and provider allow flags",
                "provider_category_impact": "derivatives/OI/funding live rehearsal not sampled in this run",
            },
            run_step=BurnInStep(
                "coinalyze_no_send_rehearsal",
                (
                    python,
                    "main.py",
                    "--event-alpha-coinalyze-no-send-rehearsal",
                    *base,
                    *_flag_tuple(candidate_mode, "--event-alpha-coinalyze-allow-live-preflight"),
                ),
                timeout_seconds=readiness_timeout_seconds,
            ),
            enabled=include_coinalyze_rehearsal,
        ),
        BurnInStep("bybit_announcements_preflight", (python, "main.py", "--event-alpha-bybit-announcements-preflight", *base), timeout_seconds=readiness_timeout_seconds),
        *(
            (
                _provider_step(
                    provider_status,
                    "bybit_announcements",
                    default_skip={
                        "name": "bybit_announcements_no_send_rehearsal",
                        "status": "skipped",
                        "required": False,
                        "timeout_seconds": readiness_timeout_seconds,
                        "skip_reason": "Bybit live announcements remain no-live unless RSI_EVENT_ALPHA_BYBIT_ANNOUNCEMENTS_ALLOW_LIVE_PREFLIGHT=1 is explicit",
                        "provider_category_impact": "official exchange announcements live rehearsal not sampled in this run",
                    },
                    run_step=BurnInStep(
                        "bybit_announcements_no_send_rehearsal",
                        (
                            python,
                            "main.py",
                            "--event-alpha-bybit-announcements-no-send-rehearsal",
                            *base,
                            *_flag_tuple(candidate_mode, "--event-alpha-bybit-announcements-allow-live-preflight"),
                        ),
                        timeout_seconds=readiness_timeout_seconds,
                    ),
                    enabled=bool(provider_status and provider_status.get("bybit_announcements", {}).get("live_call_allowed")),
                ),
            )
            if candidate_mode
            else ()
        ),
        BurnInStep(
            "integrated_radar_cycle",
            (
                python,
                "main.py",
                "--event-alpha-integrated-radar-cycle",
                "--event-alpha-integrated-radar-auto",
                *base,
            ),
            required=True,
            timeout_seconds=integrated_timeout_seconds,
        ),
        BurnInStep("source_coverage", (python, "main.py", "--event-alpha-source-coverage-report", *base), timeout_seconds=report_timeout_seconds),
        BurnInStep("notification_preview", (python, "main.py", "--event-alpha-notify-preview-from-artifacts", *base), timeout_seconds=report_timeout_seconds),
        BurnInStep("daily_brief", (python, "main.py", "--event-alpha-daily-brief", *base), timeout_seconds=report_timeout_seconds),
        BurnInStep("review_inbox", (python, "-m", "crypto_rsi_scanner.event_alpha.operations.review_inbox", "--profile", profile, "--artifact-namespace", namespace), timeout_seconds=report_timeout_seconds),
        BurnInStep("artifact_doctor", (python, "main.py", "--event-alpha-artifact-doctor", *base), timeout_seconds=doctor_timeout_seconds),
        BurnInStep(
            "burn_in_scorecard",
            (
                python,
                "-m",
                "crypto_rsi_scanner.event_alpha.operations.scorecard",
                "--profile",
                profile,
                "--artifact-namespace",
                namespace,
                "--count-explicit-namespace-for-burn-in",
            ),
            timeout_seconds=report_timeout_seconds,
        ),
    ]
    return tuple(steps)


def run_daily_burn_in(
    *,
    profile: str = "live_burn_in_no_send",
    artifact_namespace: str | None = None,
    python: str | None = None,
    base_dir: str | Path | None = None,
    now: datetime | None = None,
    continue_on_error: bool = True,
    include_coinalyze_rehearsal: bool | None = None,
    smoke: bool = False,
    readiness_timeout_seconds: float = 60.0,
    integrated_timeout_seconds: float = 180.0,
    report_timeout_seconds: float = 60.0,
    doctor_timeout_seconds: float = 120.0,
    candidate_mode: bool = False,
) -> dict[str, Any]:
    generated = (now or common.utc_now()).astimezone(timezone.utc)
    namespace = artifact_namespace or default_namespace(generated)
    context = common.context_for(profile=profile, artifact_namespace=namespace, base_dir=base_dir)
    context.namespace_dir.mkdir(parents=True, exist_ok=True)
    py = python or sys.executable
    provider_status = _candidate_provider_status(context) if candidate_mode else {}
    allow_rehearsal = bool(
        include_coinalyze_rehearsal
        if include_coinalyze_rehearsal is not None
        else (
            _env_truthy("RSI_EVENT_ALPHA_DAILY_BURN_IN_ALLOW_COINALYZE_REHEARSAL")
            or (candidate_mode and bool(provider_status.get("coinalyze", {}).get("live_call_allowed")))
        )
    )
    env = _safe_env(context, profile=profile, namespace=namespace, candidate_mode=candidate_mode, provider_status=provider_status)
    _write_candidate_mode_manifest(
        context=context,
        generated=generated,
        profile=profile,
        namespace=namespace,
        candidate_mode=candidate_mode,
        provider_status=provider_status,
        completed=False,
    )
    steps = build_steps(
        python=py,
        profile=profile,
        namespace=namespace,
        include_coinalyze_rehearsal=allow_rehearsal,
        smoke=smoke,
        readiness_timeout_seconds=readiness_timeout_seconds,
        integrated_timeout_seconds=integrated_timeout_seconds,
        report_timeout_seconds=report_timeout_seconds,
        doctor_timeout_seconds=doctor_timeout_seconds,
        candidate_mode=candidate_mode,
        provider_status=provider_status,
    )
    step_rows: list[dict[str, Any]] = []
    for step in steps:
        if isinstance(step, Mapping):
            row = _skipped_step_row(step)
            step_rows.append(row)
            print(f"[burn-in] skipped {row.get('name')}: {row.get('skip_reason')}", flush=True)
            _write_run_artifacts(
                context=context,
                generated=generated,
                profile=profile,
                namespace=namespace,
                step_rows=step_rows,
                allow_rehearsal=allow_rehearsal,
                env=env,
                completed=False,
                smoke=smoke,
                candidate_mode=candidate_mode,
                provider_status=provider_status,
            )
            continue
        print(f"[burn-in] starting {step.name} timeout={step.timeout_seconds}s", flush=True)
        row = _run_step(step, env=env, cwd=common.repo_root_from_module())
        step_rows.append(row)
        if candidate_mode:
            _postprocess_candidate_mode_artifacts(context=context, provider_status=provider_status)
            _write_candidate_mode_manifest(
                context=context,
                generated=generated,
                profile=profile,
                namespace=namespace,
                candidate_mode=candidate_mode,
                provider_status=provider_status,
                completed=False,
            )
        print(f"[burn-in] finished {step.name} status={row.get('status')} duration={row.get('duration_seconds')}s", flush=True)
        _write_run_artifacts(context=context, generated=generated, profile=profile, namespace=namespace, step_rows=step_rows, allow_rehearsal=allow_rehearsal, env=env, completed=False, smoke=smoke, candidate_mode=candidate_mode, provider_status=provider_status)
        if step.required and row["status"] != "passed" and not continue_on_error:
            break
    if candidate_mode:
        _postprocess_candidate_mode_artifacts(context=context, provider_status=provider_status)
    payload = _write_run_artifacts(context=context, generated=generated, profile=profile, namespace=namespace, step_rows=step_rows, allow_rehearsal=allow_rehearsal, env=env, completed=True, smoke=smoke, candidate_mode=candidate_mode, provider_status=provider_status)
    _write_candidate_mode_manifest(
        context=context,
        generated=generated,
        profile=profile,
        namespace=namespace,
        candidate_mode=candidate_mode,
        provider_status=provider_status,
        completed=True,
    )
    common.append_jsonl(context.run_ledger_path, _ledger_row(payload))
    return payload


def format_daily_burn_in_plan(
    *,
    profile: str,
    namespace: str,
    python: str,
    include_coinalyze_rehearsal: bool,
    smoke: bool = False,
    readiness_timeout_seconds: float = 60.0,
    integrated_timeout_seconds: float = 180.0,
    report_timeout_seconds: float = 60.0,
    doctor_timeout_seconds: float = 120.0,
    candidate_mode: bool = False,
) -> str:
    provider_status = _candidate_provider_status(common.context_for(profile=profile, artifact_namespace=namespace)) if candidate_mode else {}
    steps = build_steps(
        python=python,
        profile=profile,
        namespace=namespace,
        include_coinalyze_rehearsal=include_coinalyze_rehearsal,
        smoke=smoke,
        readiness_timeout_seconds=readiness_timeout_seconds,
        integrated_timeout_seconds=integrated_timeout_seconds,
        report_timeout_seconds=report_timeout_seconds,
        doctor_timeout_seconds=doctor_timeout_seconds,
        candidate_mode=candidate_mode,
        provider_status=provider_status,
    )
    lines = [
        "# Event Alpha Daily Live No-Send Burn-In Plan",
        "",
        f"- profile: `{profile}`",
        f"- artifact_namespace: `{namespace}`",
        f"- dry_run_plan: `True`",
        f"- candidate_mode: `{candidate_mode}`",
        "- No live providers were run by default.",
        "- Coinalyze rehearsal skipped unless explicit allow flags are set.",
        "- No Telegram sends, trades, paper trades, normal RSI rows, or Event Alpha-created `TRIGGERED_FADE` are authorized.",
        "",
        "## Planned Steps",
        "",
    ]
    for step in steps:
        if isinstance(step, Mapping):
            lines.append(f"- {step.get('name')}: skipped by default ({step.get('skip_reason')})")
        else:
            lines.append(f"- {step.name}: timeout={step.timeout_seconds}s command=`{' '.join(step.command)}`")
    return "\n".join(lines).rstrip()


def format_daily_burn_in_report(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Event Alpha Daily Live No-Send Burn-In",
        "",
        "Research-only daily operating loop. No Telegram sends, trades, paper trades, normal RSI rows, live provider calls by default, or Event Alpha-created `TRIGGERED_FADE` are authorized by this report.",
        "",
        "No live providers were run by default.",
        "Coinalyze rehearsal skipped unless explicit allow flags are set.",
        "",
        f"- generated_at: `{payload.get('generated_at')}`",
        f"- profile: `{payload.get('profile')}`",
        f"- artifact_namespace: `{payload.get('artifact_namespace')}`",
        f"- namespace_dir: `{payload.get('namespace_dir')}`",
        f"- candidate_mode: `{payload.get('candidate_mode')}`",
        f"- live_provider_calls_allowed: `{payload.get('live_provider_calls_allowed')}`",
        f"- completed: `{payload.get('completed')}`",
        f"- steps: `{payload.get('steps_passed')}` passed, `{payload.get('steps_skipped')}` skipped, `{payload.get('steps_failed')}` failed",
        f"- steps_timeout: `{payload.get('steps_timeout')}`",
        f"- required_failed: `{', '.join(payload.get('required_failed') or []) or 'none'}`",
        "",
        "## Steps",
        "",
    ]
    for row in payload.get("steps", []) or []:
        if not isinstance(row, Mapping):
            continue
        lines.append(f"### {row.get('name')}")
        lines.append(f"- status: `{row.get('status')}`")
        lines.append(f"- required: `{bool(row.get('required'))}`")
        if row.get("skip_reason"):
            lines.append(f"- skip_reason: {row.get('skip_reason')}")
        if row.get("provider_category_impact"):
            lines.append(f"- provider/category impact: {row.get('provider_category_impact')}")
        if row.get("command"):
            lines.append(f"- command: `{row.get('command')}`")
        if row.get("duration_seconds") is not None:
            lines.append(f"- duration_seconds: `{row.get('duration_seconds')}`")
        if row.get("timeout_seconds") is not None:
            lines.append(f"- timeout_seconds: `{row.get('timeout_seconds')}`")
        if row.get("started_at"):
            lines.append(f"- started_at: `{row.get('started_at')}`")
        if row.get("finished_at"):
            lines.append(f"- finished_at: `{row.get('finished_at')}`")
        if row.get("step_started_at"):
            lines.append(f"- step_started_at: `{row.get('step_started_at')}`")
        if row.get("step_finished_at"):
            lines.append(f"- step_finished_at: `{row.get('step_finished_at')}`")
        if row.get("stdout_tail"):
            lines.append("- stdout_tail:")
            lines.append("```")
            lines.append(str(row.get("stdout_tail")))
            lines.append("```")
        if row.get("stderr_tail"):
            lines.append("- stderr_tail:")
            lines.append("```")
            lines.append(str(row.get("stderr_tail")))
            lines.append("```")
        lines.append("")
    lines.extend(
        [
            "## Safety Counters",
            "",
            f"- telegram_sends: `{payload.get('telegram_sends')}`",
            f"- trades_created: `{payload.get('trades_created')}`",
            f"- paper_trades_created: `{payload.get('paper_trades_created')}`",
            f"- normal_rsi_signal_rows_written: `{payload.get('normal_rsi_signal_rows_written')}`",
            f"- triggered_fade_created: `{payload.get('triggered_fade_created')}`",
        ]
    )
    if payload.get("candidate_mode"):
        lines.extend(["", "## Candidate Mode", ""])
        lines.append(f"- manifest: `{payload.get('candidate_mode_manifest_path')}`")
        lines.append(f"- skipped_missing_config: `{', '.join(payload.get('skipped_missing_config') or []) or 'none'}`")
        lines.append(f"- skipped_live_calls_disabled: `{', '.join(payload.get('skipped_live_calls_disabled') or []) or 'none'}`")
        lines.append(f"- next_steps: `{'; '.join(payload.get('next_steps') or []) or 'none'}`")
    return "\n".join(lines).rstrip()


def _safe_env(context: Any, *, profile: str, namespace: str, candidate_mode: bool = False, provider_status: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "RSI_EVENT_ALERTS_ENABLED": "0",
            "RSI_EVENT_ALPHA_RUN_MODE": "burn_in",
            "RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR": context.base_dir.as_posix(),
            "RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE": namespace,
            "RSI_EVENT_ALPHA_RUN_LEDGER_PATH": context.run_ledger_path.as_posix(),
            "RSI_EVENT_ALPHA_ALERT_STORE_PATH": context.alert_store_path.as_posix(),
            "RSI_EVENT_ALPHA_NOTIFICATION_RUNS_PATH": context.notification_runs_path.as_posix(),
            "RSI_EVENT_WATCHLIST_STATE_PATH": context.watchlist_state_path.as_posix(),
            "RSI_EVENT_ALPHA_FEEDBACK_PATH": context.feedback_path.as_posix(),
            "RSI_EVENT_ALPHA_MISSED_PATH": context.missed_path.as_posix(),
            "RSI_EVENT_PROVIDER_HEALTH_PATH": context.provider_health_path.as_posix(),
            "RSI_EVENT_ALPHA_DAILY_BRIEF_PATH": context.daily_brief_path.as_posix(),
            "RSI_EVENT_RESEARCH_CARDS_DIR": context.research_cards_dir.as_posix(),
            "RSI_EVENT_CORE_OPPORTUNITY_STORE_PATH": context.core_opportunity_store_path.as_posix(),
            "RSI_EVENT_ALPHA_EVIDENCE_ACQUISITION_PATH": context.evidence_acquisition_path.as_posix(),
            "RSI_EVENT_ALPHA_PROFILE": profile,
            "RSI_EVENT_ALPHA_BURN_IN_CANDIDATE_MODE": "1" if candidate_mode else "0",
            "RSI_EVENT_DISCOVERY_COINALYZE_LIVE": "0",
            "RSI_EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE": "0",
            "RSI_EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE": "0",
            "RSI_EVENT_DISCOVERY_GDELT_LIVE": "0",
            "RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE": "0",
            "RSI_EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE": "0",
            "RSI_EVENT_DISCOVERY_UNIVERSE_LIVE": "0",
        }
    )
    provider_status = provider_status or {}
    if candidate_mode and provider_status.get("coinalyze", {}).get("live_call_allowed"):
        env["RSI_EVENT_ALPHA_COINALYZE_ALLOW_LIVE_PREFLIGHT"] = "1"
    if candidate_mode and provider_status.get("bybit_announcements", {}).get("live_call_allowed"):
        env["RSI_EVENT_ALPHA_BYBIT_ANNOUNCEMENTS_ALLOW_LIVE_PREFLIGHT"] = "1"
    return env


def _run_step(step: BurnInStep, *, env: Mapping[str, str], cwd: Path) -> dict[str, Any]:
    started = common.utc_now()
    before = time.monotonic()
    try:
        proc = subprocess.run(
            list(step.command),
            cwd=cwd,
            env=dict(env),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=step.timeout_seconds,
        )
        status = "passed" if proc.returncode == 0 else "failed"
        returncode: int | None = proc.returncode
        stdout = proc.stdout
        stderr = proc.stderr
    except subprocess.TimeoutExpired as exc:
        status = "timeout"
        returncode = None
        stdout = _decode_timeout_stream(exc.stdout)
        stderr = _decode_timeout_stream(exc.stderr)
    duration = round(time.monotonic() - before, 3)
    finished = common.utc_now()
    return {
        "name": step.name,
        "status": status,
        "required": step.required,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "step_started_at": started.isoformat(),
        "step_finished_at": finished.isoformat(),
        "duration_seconds": duration,
        "timeout_seconds": step.timeout_seconds,
        "returncode": returncode,
        "command": " ".join(step.command),
        "stdout_tail": _tail(stdout),
        "stderr_tail": _tail(stderr),
    }


def _skipped_step_row(step: Mapping[str, Any]) -> dict[str, Any]:
    now = common.utc_now().isoformat()
    row = dict(step)
    return {
        **row,
        "name": row.get("name"),
        "status": "skipped",
        "required": False,
        "started_at": now,
        "finished_at": now,
        "step_started_at": now,
        "step_finished_at": now,
        "duration_seconds": 0.0,
        "timeout_seconds": row.get("timeout_seconds"),
        "skip_reason": row.get("skip_reason") or "skipped_by_plan",
    }


def _write_run_artifacts(
    *,
    context: Any,
    generated: datetime,
    profile: str,
    namespace: str,
    step_rows: list[dict[str, Any]],
    allow_rehearsal: bool,
    env: Mapping[str, str],
    completed: bool,
    smoke: bool,
    candidate_mode: bool = False,
    provider_status: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized_steps = [_normalize_step_row(row) for row in step_rows]
    provider_status = provider_status or {}
    live_allowed = any(bool(row.get("live_call_allowed")) for row in provider_status.values())
    payload = common.with_safety(
        {
            "schema_version": "event_alpha_daily_burn_in_run_v1",
            "row_type": "event_alpha_daily_burn_in_run",
            "generated_at": generated.isoformat(),
            "last_updated_at": common.utc_now().isoformat(),
            "profile": profile,
            "artifact_namespace": namespace,
            "namespace_dir": common.rel_path(context.namespace_dir),
            "completed": bool(completed),
            "smoke": bool(smoke),
            "candidate_mode": bool(candidate_mode),
            "no_send": True,
            "live_provider_calls_allowed": live_allowed,
            "candidate_mode_manifest_path": common.rel_path(context.namespace_dir / CANDIDATE_MODE_MANIFEST_JSON) if candidate_mode else "",
            "provider_activation_status": provider_status,
            "skipped_missing_config": _providers_with_status(provider_status, "skipped_missing_config"),
            "skipped_live_calls_disabled": _providers_with_status(provider_status, "skipped_live_calls_disabled", "live_call_blocked_by_default"),
            "next_steps": _candidate_mode_next_steps(provider_status) if candidate_mode else [],
            "steps": normalized_steps,
            "steps_total": len(normalized_steps),
            "steps_passed": sum(1 for row in normalized_steps if row.get("status") == "passed"),
            "steps_skipped": sum(1 for row in normalized_steps if row.get("status") == "skipped"),
            "steps_failed": sum(1 for row in normalized_steps if row.get("status") == "failed"),
            "steps_timeout": sum(1 for row in normalized_steps if row.get("status") == "timeout"),
            "required_failed": [
                row.get("name")
                for row in normalized_steps
                if row.get("required") and row.get("status") != "passed"
            ],
            "coinalyze_rehearsal_allowed": allow_rehearsal,
            "safe_environment": {
                "RSI_EVENT_ALERTS_ENABLED": env.get("RSI_EVENT_ALERTS_ENABLED"),
                "RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE": env.get("RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE"),
                "RSI_EVENT_ALPHA_RUN_MODE": env.get("RSI_EVENT_ALPHA_RUN_MODE"),
            },
        }
    )
    common.write_json(context.namespace_dir / RUN_JSON, payload)
    common.write_text(context.namespace_dir / RUN_MD, format_daily_burn_in_report(payload))
    return payload


def _normalize_step_row(row: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(row)
    status = str(out.get("status") or "").strip()
    if out.get("required") is None:
        out["required"] = False
    if status == "skipped" and not out.get("skip_reason"):
        out["skip_reason"] = "skipped_by_plan"
    started = out.get("started_at") or out.get("step_started_at")
    finished = out.get("finished_at") or out.get("step_finished_at") or started
    if started:
        out["started_at"] = started
        out.setdefault("step_started_at", started)
    if finished:
        out["finished_at"] = finished
        out.setdefault("step_finished_at", finished)
    return out


def _flag_tuple(enabled: bool, flag: str) -> tuple[str, ...]:
    return (flag,) if enabled else ()


def _provider_step(
    provider_status: Mapping[str, Mapping[str, Any]] | None,
    provider_key: str,
    *,
    default_skip: Mapping[str, Any],
    run_step: BurnInStep,
    enabled: bool,
) -> BurnInStep | dict[str, Any]:
    if enabled:
        return run_step
    status = dict((provider_status or {}).get(provider_key) or {})
    if not status:
        return dict(default_skip)
    row = dict(default_skip)
    row["skip_reason"] = status.get("skip_reason") or status.get("status") or row.get("skip_reason")
    row["provider_status"] = status.get("status")
    row["provider"] = provider_key
    row["configured"] = status.get("configured")
    row["allow_flag_set"] = status.get("allow_flag_set")
    row["live_call_allowed"] = status.get("live_call_allowed")
    row["request_ledger_path"] = status.get("request_ledger_path")
    return row


def _candidate_provider_status(context: Any) -> dict[str, dict[str, Any]]:
    coinalyze_key_present = bool(_configured_value("RSI_EVENT_DISCOVERY_COINALYZE_API_KEY", config.EVENT_DISCOVERY_COINALYZE_API_KEY))
    coinalyze_allow = _env_truthy("RSI_EVENT_ALPHA_COINALYZE_ALLOW_LIVE_PREFLIGHT")
    coinalyze_budget = _int_env("RSI_EVENT_ALPHA_COINALYZE_PREFLIGHT_MAX_REQUESTS", 8)
    coinalyze_symbols = tuple(_env_csv("RSI_EVENT_DISCOVERY_COINALYZE_SYMBOLS") or config.EVENT_DISCOVERY_COINALYZE_SYMBOLS or ())
    if not coinalyze_key_present:
        coinalyze_status = "skipped_missing_config"
        coinalyze_skip = "missing RSI_EVENT_DISCOVERY_COINALYZE_API_KEY"
        coinalyze_live = False
    elif not coinalyze_allow:
        coinalyze_status = "live_call_blocked_by_default"
        coinalyze_skip = "set RSI_EVENT_ALPHA_COINALYZE_ALLOW_LIVE_PREFLIGHT=1 for guarded no-send candidate mode"
        coinalyze_live = False
    elif coinalyze_budget <= 0 or coinalyze_budget > 10:
        coinalyze_status = "request_budget_not_small"
        coinalyze_skip = "set RSI_EVENT_ALPHA_COINALYZE_PREFLIGHT_MAX_REQUESTS to 1..10"
        coinalyze_live = False
    else:
        coinalyze_status = "ready_live_no_send"
        coinalyze_skip = ""
        coinalyze_live = True

    bybit_allow = _env_truthy("RSI_EVENT_ALPHA_BYBIT_ANNOUNCEMENTS_ALLOW_LIVE_PREFLIGHT")
    bybit_limit = _int_env("RSI_EVENT_ALPHA_BYBIT_ANNOUNCEMENTS_PREFLIGHT_LIMIT", int(config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIMIT or 20))
    if not bybit_allow:
        bybit_status = "skipped_live_calls_disabled"
        bybit_skip = "set RSI_EVENT_ALPHA_BYBIT_ANNOUNCEMENTS_ALLOW_LIVE_PREFLIGHT=1 for guarded no-send candidate mode"
        bybit_live = False
    elif bybit_limit <= 0 or bybit_limit > 50:
        bybit_status = "request_budget_not_small"
        bybit_skip = "set RSI_EVENT_ALPHA_BYBIT_ANNOUNCEMENTS_PREFLIGHT_LIMIT to 1..50"
        bybit_live = False
    else:
        bybit_status = "ready_live_no_send"
        bybit_skip = ""
        bybit_live = True

    return {
        "coinalyze": {
            "provider": "coinalyze",
            "configured": coinalyze_key_present,
            "allow_flag_set": coinalyze_allow,
            "live_call_allowed": coinalyze_live,
            "status": coinalyze_status,
            "skip_reason": coinalyze_skip,
            "request_budget": coinalyze_budget,
            "symbols_configured": len(coinalyze_symbols),
            "request_ledger_path": common.rel_path(context.namespace_dir / COINALYZE_REQUEST_LEDGER),
            "source_pack": "derivatives_crowding",
        },
        "bybit_announcements": {
            "provider": "bybit_announcements",
            "configured": True,
            "allow_flag_set": bybit_allow,
            "live_call_allowed": bybit_live,
            "status": bybit_status,
            "skip_reason": bybit_skip,
            "request_budget": bybit_limit,
            "request_ledger_path": common.rel_path(context.namespace_dir / BYBIT_REQUEST_LEDGER),
            "source_pack": "official_exchange_listing_pack",
        },
    }


def _write_candidate_mode_manifest(
    *,
    context: Any,
    generated: datetime,
    profile: str,
    namespace: str,
    candidate_mode: bool,
    provider_status: Mapping[str, Mapping[str, Any]],
    completed: bool,
) -> dict[str, Any] | None:
    if not candidate_mode:
        return None
    counts = _candidate_mode_counts(context, provider_status)
    payload = common.with_safety(
        {
            "schema_version": "event_alpha_candidate_mode_manifest_v1",
            "row_type": "event_alpha_candidate_mode_manifest",
            "generated_at": generated.isoformat(),
            "last_updated_at": common.utc_now().isoformat(),
            "profile": profile,
            "artifact_namespace": namespace,
            "namespace_dir": common.rel_path(context.namespace_dir),
            "candidate_mode": True,
            "completed": bool(completed),
            "no_send": True,
            "live_provider_calls_allowed": any(bool(row.get("live_call_allowed")) for row in provider_status.values()),
            "providers": {key: dict(value) for key, value in provider_status.items()},
            "skipped_missing_config": _providers_with_status(provider_status, "skipped_missing_config"),
            "skipped_live_calls_disabled": _providers_with_status(provider_status, "skipped_live_calls_disabled", "live_call_blocked_by_default"),
            "next_steps": _candidate_mode_next_steps(provider_status),
            **counts,
        }
    )
    common.write_json(context.namespace_dir / CANDIDATE_MODE_MANIFEST_JSON, payload)
    return payload


def _postprocess_candidate_mode_artifacts(*, context: Any, provider_status: Mapping[str, Mapping[str, Any]]) -> None:
    candidates_path = context.namespace_dir / "event_integrated_radar_candidates.jsonl"
    rows = common.read_jsonl(candidates_path)
    if not rows:
        return
    changed = False
    annotated: list[dict[str, Any]] = []
    for row in rows:
        out = dict(row)
        before = dict(out)
        _annotate_candidate_row(out, context=context, provider_status=provider_status)
        annotated.append(out)
        changed = changed or out != before
    if changed:
        _write_jsonl(candidates_path, annotated)


def _annotate_candidate_row(row: dict[str, Any], *, context: Any, provider_status: Mapping[str, Mapping[str, Any]]) -> None:
    provider = _infer_candidate_provider(row)
    ledger_path = _request_ledger_for_provider(provider, context)
    ledger_exists = bool(ledger_path and (context.namespace_dir / Path(ledger_path).name).exists())
    fixture = _is_fixture_candidate(row)
    diagnostic = str(row.get("opportunity_type") or row.get("lane") or "").upper() == "DIAGNOSTIC" or row.get("diagnostic_only") is True
    source_mode = str(row.get("candidate_source_mode") or "").strip()
    if not source_mode:
        source_mode = "mocked_fixture" if fixture else ("live_no_send" if ledger_exists else "artifact_replay")
    row.setdefault("candidate_provenance", "integrated_candidate")
    row.setdefault("provider", provider or "unknown")
    row.setdefault("source_origin", row.get("provider") or provider or row.get("source_origin") or "unknown")
    row.setdefault("source_pack", row.get("source_pack") or _source_pack_for_provider(provider))
    row["candidate_source_mode"] = source_mode
    if ledger_exists:
        row["request_ledger_path"] = ledger_path
    row["no_send_rehearsal"] = True
    row["research_only"] = True
    row["strict_alerts_created"] = 0
    row["telegram_sends"] = 0
    row["trades_created"] = 0
    row["paper_trades_created"] = 0
    row["normal_rsi_signal_rows_written"] = 0
    row["triggered_fade_created"] = 0
    row["contract_counted_candidate"] = bool(
        source_mode == "live_no_send"
        and ledger_exists
        and not fixture
        and not diagnostic
        and provider in provider_status
    )


def _candidate_mode_counts(context: Any, provider_status: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    rows = common.read_jsonl(context.namespace_dir / "event_integrated_radar_candidates.jsonl")
    ledger_counts = {
        key: len(common.read_jsonl(context.namespace_dir / Path(str(value.get("request_ledger_path") or "")).name))
        for key, value in provider_status.items()
        if value.get("request_ledger_path")
    }
    return {
        "candidate_rows": len(rows),
        "real_burn_in_candidate_count": sum(1 for row in rows if row.get("contract_counted_candidate") is True),
        "contract_counted_candidate_count": sum(1 for row in rows if row.get("contract_counted_candidate") is True),
        "fixture_candidate_count": sum(1 for row in rows if _is_fixture_candidate(row)),
        "request_ledger_rows": ledger_counts,
        "providers_with_candidates": sorted(
            {
                _infer_candidate_provider(row)
                for row in rows
                if _infer_candidate_provider(row) in provider_status
            }
        ),
    }


def _request_ledger_for_provider(provider: str, context: Any) -> str:
    if provider == "coinalyze":
        return common.rel_path(context.namespace_dir / COINALYZE_REQUEST_LEDGER)
    if provider in {"bybit", "bybit_announcements"}:
        return common.rel_path(context.namespace_dir / BYBIT_REQUEST_LEDGER)
    return ""


def _infer_candidate_provider(row: Mapping[str, Any]) -> str:
    text = " ".join(
        str(row.get(field) or "")
        for field in ("provider", "source_provider", "source_origin", "source_pack", "source_pack_id")
    ).casefold()
    if "coinalyze" in text or "derivative" in text or "funding" in text:
        return "coinalyze"
    if "bybit" in text:
        return "bybit_announcements"
    return str(row.get("provider") or row.get("source_provider") or row.get("source_origin") or "unknown")


def _source_pack_for_provider(provider: str) -> str:
    if provider == "coinalyze":
        return "derivatives_crowding"
    if provider in {"bybit", "bybit_announcements"}:
        return "official_exchange_listing_pack"
    return "unknown"


def _providers_with_status(provider_status: Mapping[str, Mapping[str, Any]], *statuses: str) -> list[str]:
    wanted = set(statuses)
    return sorted(key for key, row in provider_status.items() if str(row.get("status") or "") in wanted)


def _candidate_mode_next_steps(provider_status: Mapping[str, Mapping[str, Any]]) -> list[str]:
    steps: list[str] = []
    for key, row in sorted(provider_status.items()):
        status = str(row.get("status") or "")
        if status == "skipped_missing_config":
            steps.append(f"configure {key} credentials/settings before candidate-mode sampling")
        elif status in {"skipped_live_calls_disabled", "live_call_blocked_by_default"}:
            steps.append(f"set explicit allow flag for {key} to run guarded no-send candidate sampling")
        elif status == "request_budget_not_small":
            steps.append(f"set a small request budget for {key}")
    return steps or ["review candidate artifacts and labels; no thresholds auto-apply"]


def _is_fixture_candidate(row: Mapping[str, Any]) -> bool:
    text = " ".join(str(row.get(field) or "") for field in ("run_mode", "profile", "artifact_namespace", "source_origin", "source_pack", "candidate_source_mode")).casefold()
    return bool(row.get("fixture_only") is True or row.get("test_fixture") is True or "fixture" in text or "smoke" in text or "mocked_fixture" in text)


def _configured_value(env_name: str, config_value: Any) -> str:
    return str(os.getenv(env_name, "") or config_value or "").strip()


def _env_truthy(name: str) -> bool:
    return str(os.getenv(name) or "").strip().casefold() in _TRUTHY


def _env_csv(name: str) -> tuple[str, ...]:
    raw = os.getenv(name, "")
    return tuple(item.strip() for item in raw.split(",") if item.strip())


def _int_env(name: str, default: int) -> int:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return int(default)
    try:
        return int(raw)
    except ValueError:
        return 0


def _write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(dict(row), sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _decode_timeout_stream(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    return str(value or "")


def _tail(text: str, *, limit: int = 1200) -> str:
    clean = (text or "").strip()
    if len(clean) <= limit:
        return clean
    return clean[-limit:]


def _ledger_row(payload: Mapping[str, Any]) -> dict[str, Any]:
    started_at = payload.get("generated_at")
    return {
        "schema_version": "event_alpha_daily_burn_in_ledger_v1",
        "row_type": "daily_burn_in",
        "run_id": str(payload.get("run_id") or f"{started_at}|daily_burn_in|{payload.get('artifact_namespace') or payload.get('profile') or 'unknown'}"),
        "run_mode": "burn_in",
        "profile": payload.get("profile"),
        "artifact_namespace": payload.get("artifact_namespace"),
        "started_at": started_at,
        "success": not payload.get("required_failed") and int(payload.get("steps_failed") or 0) == 0,
        "steps_total": payload.get("steps_total"),
        "steps_passed": payload.get("steps_passed"),
        "steps_skipped": payload.get("steps_skipped"),
        "steps_failed": payload.get("steps_failed"),
        **{key: payload.get(key) for key in common.SAFETY_FIELDS},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a safe daily Event Alpha no-send burn-in loop.")
    parser.add_argument("--profile", default="live_burn_in_no_send")
    parser.add_argument("--artifact-namespace", default=None)
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--stop-on-required-failure", action="store_true")
    parser.add_argument("--include-coinalyze-rehearsal", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--dry-run-plan", action="store_true")
    parser.add_argument("--event-alpha-burn-in-candidate-mode", action="store_true")
    parser.add_argument("--readiness-timeout-seconds", type=float, default=60.0)
    parser.add_argument("--integrated-timeout-seconds", type=float, default=180.0)
    parser.add_argument("--report-timeout-seconds", type=float, default=60.0)
    parser.add_argument("--doctor-timeout-seconds", type=float, default=120.0)
    args = parser.parse_args(argv)
    if args.dry_run_plan:
        namespace = args.artifact_namespace or default_namespace()
        print(
            format_daily_burn_in_plan(
                profile=args.profile,
                namespace=namespace,
                python=args.python,
                include_coinalyze_rehearsal=args.include_coinalyze_rehearsal,
                smoke=args.smoke,
                readiness_timeout_seconds=args.readiness_timeout_seconds,
                integrated_timeout_seconds=args.integrated_timeout_seconds,
                report_timeout_seconds=args.report_timeout_seconds,
                doctor_timeout_seconds=args.doctor_timeout_seconds,
                candidate_mode=args.event_alpha_burn_in_candidate_mode,
            )
        )
        return 0
    payload = run_daily_burn_in(
        profile=args.profile,
        artifact_namespace=args.artifact_namespace,
        python=args.python,
        base_dir=args.base_dir,
        continue_on_error=not args.stop_on_required_failure,
        include_coinalyze_rehearsal=args.include_coinalyze_rehearsal,
        smoke=args.smoke,
        readiness_timeout_seconds=args.readiness_timeout_seconds,
        integrated_timeout_seconds=args.integrated_timeout_seconds,
        report_timeout_seconds=args.report_timeout_seconds,
        doctor_timeout_seconds=args.doctor_timeout_seconds,
        candidate_mode=args.event_alpha_burn_in_candidate_mode,
    )
    namespace_dir = payload.get("namespace_dir")
    print(f"event_alpha_daily_burn_in_run: {namespace_dir}/{RUN_JSON}")
    print(f"event_alpha_daily_burn_in_report: {namespace_dir}/{RUN_MD}")
    if payload.get("candidate_mode"):
        print(f"event_alpha_candidate_mode_manifest: {namespace_dir}/{CANDIDATE_MODE_MANIFEST_JSON}")
    print(
        f"steps_passed={payload.get('steps_passed')} "
        f"steps_skipped={payload.get('steps_skipped')} steps_failed={payload.get('steps_failed')}"
    )
    print("No live sends, trades, paper trades, normal RSI rows, or Event Alpha TRIGGERED_FADE were created.")
    return 0 if not payload.get("required_failed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
