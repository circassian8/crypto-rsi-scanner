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
from .daily_burn_in_doctor import SCOPED_DOCTOR_JSON
from .daily_burn_in_readiness import READINESS_JSON


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
    doctor_required: bool = True,
    doctor_mode: str = "scoped_burn_in",
    candidate_mode: bool = False,
    candidate_mode_smoke: bool = False,
    provider_status: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[BurnInStep | dict[str, Any], ...]:
    base = ("--event-alpha-profile", profile, "--event-alpha-artifact-namespace", namespace)
    operation_base = ("--profile", profile, "--artifact-namespace", namespace)
    if smoke:
        return _smoke_steps(
            python=python,
            profile=profile,
            namespace=namespace,
            report_timeout_seconds=report_timeout_seconds,
        )
    if candidate_mode_smoke:
        return _candidate_mode_smoke_steps(
            python=python,
            profile=profile,
            namespace=namespace,
            base=base,
            operation_base=operation_base,
            report_timeout_seconds=report_timeout_seconds,
            doctor_timeout_seconds=doctor_timeout_seconds,
            doctor_required=doctor_required,
            doctor_mode=doctor_mode,
        )
    return _daily_steps(
        python=python,
        profile=profile,
        namespace=namespace,
        base=base,
        operation_base=operation_base,
        include_coinalyze_rehearsal=include_coinalyze_rehearsal,
        readiness_timeout_seconds=readiness_timeout_seconds,
        integrated_timeout_seconds=integrated_timeout_seconds,
        report_timeout_seconds=report_timeout_seconds,
        doctor_timeout_seconds=doctor_timeout_seconds,
        doctor_required=doctor_required,
        doctor_mode=doctor_mode,
        candidate_mode=candidate_mode,
        provider_status=provider_status,
    )


def _contract_step(python: str, report_timeout_seconds: float) -> BurnInStep:
    return BurnInStep(
        "burn_in_contract",
        (python, "-m", "crypto_rsi_scanner.project_health.radar_north_star", "--burn-in-contract-only"),
        timeout_seconds=report_timeout_seconds,
    )


def _smoke_steps(
    *,
    python: str,
    profile: str,
    namespace: str,
    report_timeout_seconds: float,
) -> tuple[BurnInStep, ...]:
    return (
        _contract_step(python, report_timeout_seconds),
        BurnInStep(
            "burn_in_smoke_fixture_step",
            (python, "-c", "print('burn_in_smoke_fixture_step: safe fixture-only runner check')"),
            required=True,
            timeout_seconds=report_timeout_seconds,
        ),
        BurnInStep(
            "burn_in_scorecard",
            (python, "-m", "crypto_rsi_scanner.event_alpha.operations.scorecard", "--profile", profile, "--artifact-namespace", namespace),
            timeout_seconds=report_timeout_seconds,
        ),
    )


def _candidate_mode_smoke_steps(
    *,
    python: str,
    profile: str,
    namespace: str,
    base: tuple[str, ...],
    operation_base: tuple[str, ...],
    report_timeout_seconds: float,
    doctor_timeout_seconds: float,
    doctor_required: bool,
    doctor_mode: str,
) -> tuple[BurnInStep, ...]:
    return (
        _contract_step(python, report_timeout_seconds),
        BurnInStep(
            "candidate_mode_fixture_providers",
            (
                python,
                "-m",
                "crypto_rsi_scanner.event_alpha.operations.daily_burn_in",
                "--write-candidate-mode-fixture-artifacts",
                *operation_base,
            ),
            required=True,
            timeout_seconds=report_timeout_seconds,
        ),
        BurnInStep(
            "review_inbox",
            (python, "-m", "crypto_rsi_scanner.event_alpha.operations.review_inbox", *operation_base),
            timeout_seconds=report_timeout_seconds,
        ),
        BurnInStep(
            "artifact_doctor",
            _doctor_command(
                python=python,
                profile=profile,
                namespace=namespace,
                base=base,
                operation_base=operation_base,
                doctor_mode=doctor_mode,
            ),
            required=doctor_required,
            timeout_seconds=doctor_timeout_seconds,
        ),
        BurnInStep(
            "burn_in_scorecard",
            (
                python,
                "-m",
                "crypto_rsi_scanner.event_alpha.operations.scorecard",
                *operation_base,
                "--include-fixture-namespaces",
                "--count-explicit-namespace-for-burn-in",
            ),
            timeout_seconds=report_timeout_seconds,
        ),
    )


def _provider_rehearsal_steps(
    *,
    python: str,
    base: tuple[str, ...],
    readiness_timeout_seconds: float,
    include_coinalyze_rehearsal: bool,
    candidate_mode: bool,
    provider_status: Mapping[str, Mapping[str, Any]] | None,
) -> tuple[BurnInStep | dict[str, Any], ...]:
    steps: list[BurnInStep | dict[str, Any]] = [
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
        )
    ]
    if candidate_mode:
        steps.append(
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
            )
        )
    return tuple(steps)


def _daily_steps(
    *,
    python: str,
    profile: str,
    namespace: str,
    base: tuple[str, ...],
    operation_base: tuple[str, ...],
    include_coinalyze_rehearsal: bool,
    readiness_timeout_seconds: float,
    integrated_timeout_seconds: float,
    report_timeout_seconds: float,
    doctor_timeout_seconds: float,
    doctor_required: bool,
    doctor_mode: str,
    candidate_mode: bool,
    provider_status: Mapping[str, Mapping[str, Any]] | None,
) -> tuple[BurnInStep | dict[str, Any], ...]:
    steps: list[BurnInStep | dict[str, Any]] = [
        _contract_step(python, report_timeout_seconds),
        BurnInStep("live_provider_readiness", (python, "main.py", "--event-alpha-live-provider-readiness", *base), timeout_seconds=readiness_timeout_seconds),
        BurnInStep("cryptopanic_preflight", (python, "main.py", "--event-alpha-cryptopanic-preflight", *base), timeout_seconds=readiness_timeout_seconds),
        BurnInStep("coinalyze_preflight", (python, "main.py", "--event-alpha-coinalyze-preflight", *base), timeout_seconds=readiness_timeout_seconds),
        *_provider_rehearsal_steps(
            python=python,
            base=base,
            readiness_timeout_seconds=readiness_timeout_seconds,
            include_coinalyze_rehearsal=include_coinalyze_rehearsal,
            candidate_mode=candidate_mode,
            provider_status=provider_status,
        ),
        BurnInStep("bybit_announcements_preflight", (python, "main.py", "--event-alpha-bybit-announcements-preflight", *base), timeout_seconds=readiness_timeout_seconds),
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
        BurnInStep(
            "artifact_doctor",
            _doctor_command(python=python, profile=profile, namespace=namespace, base=base, operation_base=operation_base, doctor_mode=doctor_mode),
            required=doctor_required,
            timeout_seconds=doctor_timeout_seconds,
        ),
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
    doctor_required: bool = True,
    doctor_mode: str = "scoped_burn_in",
    candidate_mode: bool = False,
    candidate_mode_smoke: bool = False,
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
        doctor_required=doctor_required,
        doctor_mode=doctor_mode,
        candidate_mode=candidate_mode,
        candidate_mode_smoke=candidate_mode_smoke,
        provider_status=provider_status,
    )
    step_rows: list[dict[str, Any]] = []
    interrupted = False
    interruption_reason = ""
    try:
        for step in steps:
            if isinstance(step, Mapping):
                row = _skipped_step_row(step)
                _augment_step_row(row, context=context, before_state=None, after_state=_namespace_step_state(context))
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
                    interrupted=interrupted,
                    interruption_reason=interruption_reason,
                )
                continue
            print(f"[burn-in] starting {step.name} timeout={step.timeout_seconds}s", flush=True)
            if step.name == "artifact_doctor":
                _write_scoped_doctor_pending(context=context, timeout_seconds=step.timeout_seconds, required=step.required, doctor_mode=doctor_mode)
            before_state = _namespace_step_state(context)
            try:
                row = _run_step(step, env=env, cwd=common.repo_root_from_module())
            except KeyboardInterrupt:
                interrupted = True
                interruption_reason = f"interrupted_during:{step.name}"
                now_iso = common.utc_now().isoformat()
                row = {
                    "name": step.name,
                    "status": "interrupted",
                    "required": step.required,
                    "started_at": now_iso,
                    "finished_at": now_iso,
                    "step_started_at": now_iso,
                    "step_finished_at": now_iso,
                    "duration_seconds": 0.0,
                    "timeout_seconds": step.timeout_seconds,
                    "returncode": None,
                    "command": " ".join(step.command),
                    "stdout_tail": "",
                    "stderr_tail": "KeyboardInterrupt",
                }
            after_state = _namespace_step_state(context)
            _augment_step_row(row, context=context, before_state=before_state, after_state=after_state)
            if step.name == "artifact_doctor":
                _write_step_doctor_status(context=context, row=row, doctor_mode=doctor_mode)
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
                    doctor_status=_doctor_status_payload(context),
                )
            print(f"[burn-in] finished {step.name} status={row.get('status')} duration={row.get('duration_seconds')}s", flush=True)
            _write_run_artifacts(context=context, generated=generated, profile=profile, namespace=namespace, step_rows=step_rows, allow_rehearsal=allow_rehearsal, env=env, completed=False, smoke=smoke, candidate_mode=candidate_mode, provider_status=provider_status, interrupted=interrupted, interruption_reason=interruption_reason)
            if interrupted or (step.required and row["status"] != "passed" and not continue_on_error):
                break
    except KeyboardInterrupt:
        interrupted = True
        interruption_reason = "interrupted"
    if candidate_mode:
        _postprocess_candidate_mode_artifacts(context=context, provider_status=provider_status)
    payload = _write_run_artifacts(context=context, generated=generated, profile=profile, namespace=namespace, step_rows=step_rows, allow_rehearsal=allow_rehearsal, env=env, completed=True, smoke=smoke, candidate_mode=candidate_mode, provider_status=provider_status, interrupted=interrupted, interruption_reason=interruption_reason)
    _write_candidate_mode_manifest(
        context=context,
        generated=generated,
        profile=profile,
        namespace=namespace,
        candidate_mode=candidate_mode,
        provider_status=provider_status,
        completed=True,
        doctor_status=_doctor_status_payload(context),
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
    doctor_required: bool = True,
    doctor_mode: str = "scoped_burn_in",
    candidate_mode: bool = False,
    candidate_mode_smoke: bool = False,
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
        doctor_required=doctor_required,
        doctor_mode=doctor_mode,
        candidate_mode=candidate_mode,
        candidate_mode_smoke=candidate_mode_smoke,
        provider_status=provider_status,
    )
    lines = [
        "# Event Alpha Daily Live No-Send Burn-In Plan",
        "",
        f"- profile: `{profile}`",
        f"- artifact_namespace: `{namespace}`",
        f"- dry_run_plan: `True`",
        f"- candidate_mode: `{candidate_mode}`",
        f"- candidate_mode_smoke: `{candidate_mode_smoke}`",
        f"- doctor_mode: `{doctor_mode}`",
        f"- doctor_timeout_seconds: `{doctor_timeout_seconds}`",
        f"- doctor_required: `{doctor_required}`",
        "- No live providers were run by default.",
        "- Coinalyze rehearsal skipped unless explicit allow flags are set.",
        "- No Telegram sends, trades, paper trades, normal RSI rows, or Event Alpha-created `TRIGGERED_FADE` are authorized.",
        "",
        "## Planned Steps",
        "",
    ]
    for step in steps:
        if isinstance(step, Mapping):
            command = str(step.get("command") or "").strip()
            suffix = f" command=`{command}`" if command else ""
            lines.append(f"- {step.get('name')}: skipped by default ({step.get('skip_reason')}){suffix}")
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
        f"- run_id: `{payload.get('run_id')}`",
        f"- profile: `{payload.get('profile')}`",
        f"- artifact_namespace: `{payload.get('artifact_namespace')}`",
        f"- namespace_dir: `{payload.get('namespace_dir')}`",
        f"- candidate_mode: `{payload.get('candidate_mode')}`",
        f"- live_provider_calls_allowed: `{payload.get('live_provider_calls_allowed')}`",
        f"- status: `{payload.get('status')}`",
        f"- final_status_reason: `{payload.get('final_status_reason')}`",
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
        "command": str(row.get("command") or ""),
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
    interrupted: bool = False,
    interruption_reason: str = "",
) -> dict[str, Any]:
    normalized_steps = [_normalize_step_row(row) for row in step_rows]
    provider_status = provider_status or {}
    live_allowed = any(bool(row.get("live_call_allowed")) for row in provider_status.values())
    final_status, final_status_reason = _final_run_status(
        normalized_steps,
        candidate_mode=candidate_mode,
        interrupted=interrupted,
        interruption_reason=interruption_reason,
    )
    if candidate_mode and final_status == "passed_no_candidates" and common.read_jsonl(context.namespace_dir / "event_integrated_radar_candidates.jsonl"):
        final_status = "passed"
        final_status_reason = "candidate artifacts present; contract-counting is reported in candidate-mode manifest"
    finished_at = common.utc_now().isoformat() if completed or interrupted else ""
    run_id = f"{generated.isoformat()}|daily_burn_in|{namespace}"
    payload = common.with_safety(
        {
            "schema_version": "event_alpha_daily_burn_in_run_v1",
            "row_type": "event_alpha_daily_burn_in_run",
            "run_id": run_id,
            "generated_at": generated.isoformat(),
            "started_at": generated.isoformat(),
            "finished_at": finished_at,
            "last_updated_at": common.utc_now().isoformat(),
            "profile": profile,
            "artifact_namespace": namespace,
            "namespace_dir": common.rel_path(context.namespace_dir),
            "completed": bool(completed),
            "status": final_status,
            "final_status_reason": final_status_reason,
            "smoke": bool(smoke),
            "candidate_mode": bool(candidate_mode),
            "no_send": True,
            "no_send_rehearsal": True,
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
            "steps_interrupted": sum(1 for row in normalized_steps if row.get("status") == "interrupted"),
            "required_failed": [
                row.get("name")
                for row in normalized_steps
                if row.get("required") and row.get("status") not in {"passed", "skipped"}
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
    stdout_tail, stdout_redactions = common.scrub_operator_text(str(out.get("stdout_tail") or ""))
    stderr_tail, stderr_redactions = common.scrub_operator_text(str(out.get("stderr_tail") or ""))
    out["stdout_tail"] = stdout_tail
    out["stderr_tail"] = stderr_tail
    out["stdout_tail_scrubbed"] = True
    out["stderr_tail_scrubbed"] = True
    out["stdout_tail_redaction_count"] = int(out.get("stdout_tail_redaction_count") or 0) + stdout_redactions
    out["stderr_tail_redaction_count"] = int(out.get("stderr_tail_redaction_count") or 0) + stderr_redactions
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
    out.setdefault("artifact_paths_written", [])
    out.setdefault("candidate_rows_written", 0)
    out.setdefault("provider_calls_attempted", 0)
    out.setdefault("live_calls_attempted", 0)
    out.setdefault("safety_side_effects", _zero_safety_side_effects())
    return out


def _final_run_status(
    steps: list[Mapping[str, Any]],
    *,
    candidate_mode: bool,
    interrupted: bool,
    interruption_reason: str,
) -> tuple[str, str]:
    if interrupted or any(str(row.get("status") or "") == "interrupted" for row in steps):
        return "interrupted", interruption_reason or "interrupted"
    required_timeouts = [str(row.get("name") or "") for row in steps if row.get("required") and row.get("status") == "timeout"]
    if required_timeouts:
        return "timeout_required_step", ",".join(required_timeouts)
    required_failed = [
        str(row.get("name") or "")
        for row in steps
        if row.get("required") and row.get("status") not in {"passed", "skipped"}
    ]
    if required_failed:
        return "failed_required_step", ",".join(required_failed)
    non_required_timeouts = [str(row.get("name") or "") for row in steps if not row.get("required") and row.get("status") == "timeout"]
    if non_required_timeouts:
        return "timeout_non_required_step", ",".join(non_required_timeouts)
    skipped = [str(row.get("name") or "") for row in steps if row.get("status") == "skipped"]
    failed_optional = [str(row.get("name") or "") for row in steps if not row.get("required") and row.get("status") == "failed"]
    if candidate_mode and not any(int(row.get("candidate_rows_written") or 0) for row in steps):
        return "passed_no_candidates", "candidate mode completed without candidate rows"
    if skipped or failed_optional:
        reason = []
        if skipped:
            reason.append("skipped=" + ",".join(skipped))
        if failed_optional:
            reason.append("optional_failed=" + ",".join(failed_optional))
        return "passed_with_skips", ";".join(reason) or "non-required steps skipped"
    return "passed", "all required steps passed"


def _zero_safety_side_effects() -> dict[str, int]:
    return {
        "strict_alerts_created": 0,
        "telegram_sends": 0,
        "trades_created": 0,
        "paper_trades_created": 0,
        "normal_rsi_signal_rows_written": 0,
        "triggered_fade_created": 0,
    }


def _flag_tuple(enabled: bool, flag: str) -> tuple[str, ...]:
    return (flag,) if enabled else ()


def _doctor_command(
    *,
    python: str,
    profile: str,
    namespace: str,
    base: tuple[str, ...],
    operation_base: tuple[str, ...],
    doctor_mode: str,
) -> tuple[str, ...]:
    if doctor_mode == "full_namespace":
        return (python, "main.py", "--event-alpha-artifact-doctor", *base)
    return (
        python,
        "-m",
        "crypto_rsi_scanner.event_alpha.operations.daily_burn_in",
        "--scoped-doctor",
        *operation_base,
    )


def _namespace_step_state(context: Any) -> dict[str, Any]:
    files: dict[str, float] = {}
    if context.namespace_dir.exists():
        for path in context.namespace_dir.rglob("*"):
            if path.is_file():
                try:
                    files[common.rel_path(path)] = path.stat().st_mtime
                except OSError:
                    continue
    return {
        "files": files,
        "candidate_rows": len(common.read_jsonl(context.namespace_dir / "event_integrated_radar_candidates.jsonl")),
        "ledger_rows": _request_ledger_row_total(context),
    }


def _augment_step_row(
    row: dict[str, Any],
    *,
    context: Any,
    before_state: Mapping[str, Any] | None,
    after_state: Mapping[str, Any],
) -> None:
    before_files = dict((before_state or {}).get("files") or {})
    after_files = dict(after_state.get("files") or {})
    changed_files = [
        path
        for path, mtime in after_files.items()
        if path not in before_files or before_files.get(path) != mtime
    ]
    before_candidates = int((before_state or {}).get("candidate_rows") or 0)
    after_candidates = int(after_state.get("candidate_rows") or 0)
    before_ledgers = int((before_state or {}).get("ledger_rows") or 0)
    after_ledgers = int(after_state.get("ledger_rows") or 0)
    row["artifact_paths_written"] = sorted(changed_files)
    row["candidate_rows_written"] = max(0, after_candidates - before_candidates)
    row["provider_calls_attempted"] = max(0, after_ledgers - before_ledgers)
    row["live_calls_attempted"] = max(0, after_ledgers - before_ledgers)
    row["safety_side_effects"] = _zero_safety_side_effects()


def _request_ledger_row_total(context: Any) -> int:
    return sum(
        len(common.read_jsonl(context.namespace_dir / name))
        for name in (COINALYZE_REQUEST_LEDGER, BYBIT_REQUEST_LEDGER)
    )


def _write_scoped_doctor_pending(*, context: Any, timeout_seconds: float, required: bool, doctor_mode: str) -> None:
    if doctor_mode != "scoped_burn_in":
        return
    payload = common.with_safety(
        {
            "schema_version": "event_alpha_daily_burn_in_doctor_status_v1",
            "row_type": "event_alpha_daily_burn_in_doctor_status",
            "generated_at": common.utc_now().isoformat(),
            "profile": context.profile,
            "artifact_namespace": context.artifact_namespace,
            "doctor_mode": doctor_mode,
            "status": "pending",
            "required": bool(required),
            "timeout_seconds": timeout_seconds,
            "blockers": [],
            "warnings": [],
            "scoped_to_current_namespace": True,
        }
    )
    _write_doctor_status(context, payload)


def _write_step_doctor_status(*, context: Any, row: Mapping[str, Any], doctor_mode: str) -> None:
    if doctor_mode != "scoped_burn_in":
        return
    if row.get("status") == "timeout":
        stdout_tail, stdout_redactions = common.scrub_operator_text(str(row.get("stdout_tail") or ""))
        stderr_tail, stderr_redactions = common.scrub_operator_text(str(row.get("stderr_tail") or ""))
        payload = common.with_safety(
            {
                "schema_version": "event_alpha_daily_burn_in_doctor_status_v1",
                "row_type": "event_alpha_daily_burn_in_doctor_status",
                "generated_at": common.utc_now().isoformat(),
                "profile": context.profile,
                "artifact_namespace": context.artifact_namespace,
                "doctor_mode": doctor_mode,
                "status": "timeout",
                "required": bool(row.get("required")),
                "timeout_seconds": row.get("timeout_seconds"),
                "blockers": ["scoped_doctor_timeout"],
                "warnings": [],
                "stdout_tail": stdout_tail,
                "stderr_tail": stderr_tail,
                "stdout_tail_scrubbed": True,
                "stderr_tail_scrubbed": True,
                "stdout_tail_redaction_count": stdout_redactions,
                "stderr_tail_redaction_count": stderr_redactions,
                "scoped_to_current_namespace": True,
            }
        )
        _write_doctor_status(context, payload)


def _doctor_status_payload(context: Any) -> dict[str, Any]:
    return common.read_json(context.namespace_dir / SCOPED_DOCTOR_JSON)


def _write_doctor_status(context: Any, payload: Mapping[str, Any]) -> None:
    from . import daily_burn_in_doctor

    daily_burn_in_doctor.write_doctor_status(context, payload)


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
    command = " ".join(run_step.command)
    status = dict((provider_status or {}).get(provider_key) or {})
    if not status:
        row = dict(default_skip)
        row.setdefault("command", command)
        return row
    row = dict(default_skip)
    row.setdefault("command", command)
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
    doctor_status: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not candidate_mode:
        return None
    counts = _candidate_mode_counts(context, provider_status)
    payload = common.with_safety(
        {
            "schema_version": "event_alpha_candidate_mode_manifest_v2",
            "row_type": "event_alpha_candidate_mode_manifest",
            "generated_at": generated.isoformat(),
            "last_updated_at": common.utc_now().isoformat(),
            "profile": profile,
            "artifact_namespace": namespace,
            "namespace_dir": common.rel_path(context.namespace_dir),
            "candidate_mode": True,
            "completed": bool(completed),
            "status": _candidate_manifest_status(counts, provider_status, completed=completed),
            "no_send": True,
            "no_send_rehearsal": True,
            "live_provider_calls_allowed": any(bool(row.get("live_call_allowed")) for row in provider_status.values()),
            "providers": {key: dict(value) for key, value in provider_status.items()},
            "skipped_missing_config": _providers_with_status(provider_status, "skipped_missing_config"),
            "skipped_live_calls_disabled": _providers_with_status(provider_status, "skipped_live_calls_disabled", "live_call_blocked_by_default"),
            "skipped_request_budget": _providers_with_status(provider_status, "request_budget_not_small"),
            "skipped_not_required_for_profile": [],
            "next_steps": _candidate_mode_next_steps(provider_status),
            "doctor_status": doctor_status or {},
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
    existing_ledgers = [
        str(value.get("request_ledger_path"))
        for key, value in provider_status.items()
        if int(ledger_counts.get(key) or 0) > 0 and str(value.get("request_ledger_path") or "").strip()
    ]
    source_artifacts = _existing_artifacts(
        context,
        (
            "event_alpha_live_provider_readiness.json",
            "event_coinalyze_preflight.json",
            "event_coinalyze_rehearsal_report.json",
            "event_bybit_announcements_preflight.json",
            "event_bybit_announcements_rehearsal_report.json",
            "event_exchange_announcements.jsonl",
            "event_official_exchange_events.jsonl",
            "event_derivatives_state.jsonl",
            "event_derivatives_crowding_candidates.jsonl",
            "event_alpha_source_coverage.json",
        ),
    )
    candidate_artifacts = _existing_artifacts(
        context,
        (
            "event_integrated_radar_candidates.jsonl",
            "event_core_opportunities.jsonl",
            "event_official_listing_candidates.jsonl",
            "event_fade_short_review_candidates.jsonl",
            "event_alpha_alerts.jsonl",
        ),
    )
    return {
        "candidate_rows": len(rows),
        "integrated_candidate_rows": len(rows),
        "notification_preview_rows": int((context.namespace_dir / "event_alpha_notification_preview.md").exists()),
        "preflight_diagnostic_rows": _json_doc_count(context.namespace_dir / "event_coinalyze_preflight.json") + _json_doc_count(context.namespace_dir / "event_bybit_announcements_preflight.json"),
        "readiness_rows": _json_doc_count(context.namespace_dir / "event_alpha_live_provider_readiness.json"),
        "source_coverage_rows": _json_doc_count(context.namespace_dir / "event_alpha_source_coverage.json"),
        "real_burn_in_candidate_count": sum(1 for row in rows if row.get("contract_counted_candidate") is True),
        "contract_counted_candidate_count": sum(1 for row in rows if row.get("contract_counted_candidate") is True),
        "fixture_candidate_count": sum(1 for row in rows if _is_fixture_candidate(row)),
        "provider_attempts": sum(1 for row in provider_status.values() if row.get("live_call_allowed")),
        "provider_skips": sum(1 for row in provider_status.values() if str(row.get("status") or "") != "ready_live_no_send"),
        "provider_successes": sum(1 for key in provider_status if int(ledger_counts.get(key) or 0) > 0),
        "request_ledger_rows": ledger_counts,
        "request_ledgers": sorted(existing_ledgers),
        "source_artifacts": source_artifacts,
        "candidate_artifacts": candidate_artifacts,
        "research_cards_written": len([path for path in context.research_cards_dir.glob("*.md") if path.name != "index.md"]) if context.research_cards_dir.exists() else 0,
        "source_coverage_marker_written": bool((context.namespace_dir / "event_alpha_source_coverage.json").exists() or (context.namespace_dir / "event_alpha_source_coverage.md").exists()),
        "readiness_marker_written": bool((context.namespace_dir / "event_live_provider_activation_readiness.json").exists() or (context.namespace_dir / "event_live_provider_activation_readiness.md").exists()),
        "notification_preview_marker_written": bool((context.namespace_dir / "event_alpha_notification_preview.md").exists()),
        "review_inbox_path": common.rel_path(context.namespace_dir / "event_alpha_daily_review_inbox.json") if (context.namespace_dir / "event_alpha_daily_review_inbox.json").exists() else "",
        "scorecard_path": common.rel_path(context.namespace_dir / "event_alpha_burn_in_scorecard.json") if (context.namespace_dir / "event_alpha_burn_in_scorecard.json").exists() else "",
        "providers_with_candidates": sorted(
            {
                _infer_candidate_provider(row)
                for row in rows
                if _infer_candidate_provider(row) in provider_status
            }
        ),
    }


def _json_doc_count(path: Path) -> int:
    return 1 if common.read_json(path) else 0


def _existing_artifacts(context: Any, names: tuple[str, ...]) -> list[str]:
    return [
        common.rel_path(context.namespace_dir / name)
        for name in names
        if (context.namespace_dir / name).exists()
    ]


def _candidate_manifest_status(counts: Mapping[str, Any], provider_status: Mapping[str, Mapping[str, Any]], *, completed: bool) -> str:
    if not completed:
        return "running"
    if int(counts.get("contract_counted_candidate_count") or 0) > 0:
        return "completed_with_contract_candidates"
    if int(counts.get("fixture_candidate_count") or 0) > 0:
        return "completed_fixture_candidates_only"
    if not any(bool(row.get("live_call_allowed")) for row in provider_status.values()):
        return "completed_no_candidate_providers"
    return "completed_no_candidates"


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
        "row_type": "event_alpha_run",
        "daily_burn_in_row_type": "daily_burn_in",
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
    parser.add_argument("--candidate-mode-smoke", action="store_true")
    parser.add_argument("--dry-run-plan", action="store_true")
    parser.add_argument("--scoped-doctor", action="store_true")
    parser.add_argument("--readiness-report", action="store_true")
    parser.add_argument("--write-candidate-mode-fixture-artifacts", action="store_true")
    parser.add_argument("--event-alpha-burn-in-candidate-mode", action="store_true")
    parser.add_argument("--readiness-timeout-seconds", type=float, default=60.0)
    parser.add_argument("--integrated-timeout-seconds", type=float, default=180.0)
    parser.add_argument("--report-timeout-seconds", type=float, default=60.0)
    parser.add_argument("--doctor-timeout-seconds", type=float, default=120.0)
    parser.add_argument("--doctor-mode", choices=("scoped_burn_in", "full_namespace"), default="scoped_burn_in")
    parser.add_argument("--doctor-optional", action="store_true")
    args = parser.parse_args(argv)
    if args.scoped_doctor:
        from . import daily_burn_in_doctor

        payload = daily_burn_in_doctor.run_scoped_doctor(profile=args.profile, artifact_namespace=args.artifact_namespace or default_namespace(), base_dir=args.base_dir)
        print(f"event_alpha_daily_burn_in_doctor_status: {payload['namespace_dir']}/{SCOPED_DOCTOR_JSON}")
        print(f"status={payload.get('status')} blockers={len(payload.get('blockers') or [])} warnings={len(payload.get('warnings') or [])}")
        return 1 if payload.get("blockers") else 0
    if args.readiness_report:
        from . import daily_burn_in_readiness

        payload = daily_burn_in_readiness.build_readiness_report(profile=args.profile, artifact_namespace=args.artifact_namespace or args.profile, base_dir=args.base_dir)
        print(f"event_alpha_daily_burn_in_readiness: {payload['namespace_dir']}/{READINESS_JSON}")
        print(f"candidate_mode_status={payload.get('candidate_mode_status')} can_run_candidate_mode={payload.get('can_run_candidate_mode')}")
        return 0
    if args.write_candidate_mode_fixture_artifacts:
        from . import candidate_mode_smoke

        payload = candidate_mode_smoke.write_candidate_mode_fixture_artifacts(profile=args.profile, artifact_namespace=args.artifact_namespace or "daily_burn_in_candidate_mode_smoke", base_dir=args.base_dir)
        print(f"event_alpha_candidate_mode_fixture_smoke: {payload['artifact_namespace']}/event_alpha_candidate_mode_fixture_smoke.json")
        print(f"fixture_candidates={payload.get('candidate_count')} live_calls_attempted={payload.get('live_calls_attempted')}")
        return 0
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
                doctor_required=not args.doctor_optional,
                doctor_mode=args.doctor_mode,
                candidate_mode=args.event_alpha_burn_in_candidate_mode,
                candidate_mode_smoke=args.candidate_mode_smoke,
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
        doctor_required=not args.doctor_optional,
        doctor_mode=args.doctor_mode,
        candidate_mode=args.event_alpha_burn_in_candidate_mode,
        candidate_mode_smoke=args.candidate_mode_smoke,
    )
    namespace_dir = payload.get("namespace_dir")
    print(f"event_alpha_daily_burn_in_run: {namespace_dir}/{RUN_JSON}")
    print(f"event_alpha_daily_burn_in_report: {namespace_dir}/{RUN_MD}")
    if payload.get("candidate_mode"):
        print(f"event_alpha_candidate_mode_manifest: {namespace_dir}/{CANDIDATE_MODE_MANIFEST_JSON}")
    print(
        f"steps_passed={payload.get('steps_passed')} "
        f"steps_skipped={payload.get('steps_skipped')} steps_failed={payload.get('steps_failed')} status={payload.get('status')}"
    )
    print("No live sends, trades, paper trades, normal RSI rows, or Event Alpha TRIGGERED_FADE were created.")
    if payload.get("status") == "interrupted":
        return 130
    return 0 if not payload.get("required_failed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
