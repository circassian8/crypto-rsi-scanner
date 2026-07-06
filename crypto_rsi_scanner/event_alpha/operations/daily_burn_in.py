"""Daily no-send Event Alpha burn-in operating loop."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from . import common


RUN_JSON = "event_alpha_daily_burn_in_run.json"
RUN_MD = "event_alpha_daily_burn_in_report.md"


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
        (
            BurnInStep("coinalyze_no_send_rehearsal", (python, "main.py", "--event-alpha-coinalyze-no-send-rehearsal", *base), timeout_seconds=readiness_timeout_seconds)
            if include_coinalyze_rehearsal
            else {
                "name": "coinalyze_no_send_rehearsal",
                "status": "skipped",
                "required": False,
                "timeout_seconds": readiness_timeout_seconds,
                "skip_reason": "requires RSI_EVENT_ALPHA_DAILY_BURN_IN_ALLOW_COINALYZE_REHEARSAL=1 and provider allow flags",
                "provider_category_impact": "derivatives/OI/funding live rehearsal not sampled in this run",
            }
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
        BurnInStep("artifact_doctor", (python, "main.py", "--event-alpha-artifact-doctor", *base), timeout_seconds=doctor_timeout_seconds),
        BurnInStep("burn_in_scorecard", (python, "-m", "crypto_rsi_scanner.event_alpha.operations.scorecard", "--profile", profile, "--artifact-namespace", namespace), timeout_seconds=report_timeout_seconds),
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
) -> dict[str, Any]:
    generated = (now or common.utc_now()).astimezone(timezone.utc)
    namespace = artifact_namespace or default_namespace(generated)
    context = common.context_for(profile=profile, artifact_namespace=namespace, base_dir=base_dir)
    context.namespace_dir.mkdir(parents=True, exist_ok=True)
    py = python or sys.executable
    allow_rehearsal = bool(
        include_coinalyze_rehearsal
        if include_coinalyze_rehearsal is not None
        else str(os.getenv("RSI_EVENT_ALPHA_DAILY_BURN_IN_ALLOW_COINALYZE_REHEARSAL") or "").lower() in {"1", "true", "yes"}
    )
    env = _safe_env(context, profile=profile, namespace=namespace)
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
    )
    step_rows: list[dict[str, Any]] = []
    for step in steps:
        if isinstance(step, Mapping):
            row = _skipped_step_row(step)
            step_rows.append(row)
            print(f"[burn-in] skipped {row.get('name')}: {row.get('skip_reason')}", flush=True)
            _write_run_artifacts(context=context, generated=generated, profile=profile, namespace=namespace, step_rows=step_rows, allow_rehearsal=allow_rehearsal, env=env, completed=False, smoke=smoke)
            continue
        print(f"[burn-in] starting {step.name} timeout={step.timeout_seconds}s", flush=True)
        row = _run_step(step, env=env, cwd=common.repo_root_from_module())
        step_rows.append(row)
        print(f"[burn-in] finished {step.name} status={row.get('status')} duration={row.get('duration_seconds')}s", flush=True)
        _write_run_artifacts(context=context, generated=generated, profile=profile, namespace=namespace, step_rows=step_rows, allow_rehearsal=allow_rehearsal, env=env, completed=False, smoke=smoke)
        if step.required and row["status"] != "passed" and not continue_on_error:
            break
    payload = _write_run_artifacts(context=context, generated=generated, profile=profile, namespace=namespace, step_rows=step_rows, allow_rehearsal=allow_rehearsal, env=env, completed=True, smoke=smoke)
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
) -> str:
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
    )
    lines = [
        "# Event Alpha Daily Live No-Send Burn-In Plan",
        "",
        f"- profile: `{profile}`",
        f"- artifact_namespace: `{namespace}`",
        f"- dry_run_plan: `True`",
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
    return "\n".join(lines).rstrip()


def _safe_env(context: Any, *, profile: str, namespace: str) -> dict[str, str]:
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
            "RSI_EVENT_DISCOVERY_COINALYZE_LIVE": "0",
            "RSI_EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE": "0",
            "RSI_EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE": "0",
            "RSI_EVENT_DISCOVERY_GDELT_LIVE": "0",
            "RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE": "0",
            "RSI_EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE": "0",
            "RSI_EVENT_DISCOVERY_UNIVERSE_LIVE": "0",
        }
    )
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
) -> dict[str, Any]:
    normalized_steps = [_normalize_step_row(row) for row in step_rows]
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
    )
    namespace_dir = payload.get("namespace_dir")
    print(f"event_alpha_daily_burn_in_run: {namespace_dir}/{RUN_JSON}")
    print(f"event_alpha_daily_burn_in_report: {namespace_dir}/{RUN_MD}")
    print(
        f"steps_passed={payload.get('steps_passed')} "
        f"steps_skipped={payload.get('steps_skipped')} steps_failed={payload.get('steps_failed')}"
    )
    print("No live sends, trades, paper trades, normal RSI rows, or Event Alpha TRIGGERED_FADE were created.")
    return 0 if not payload.get("required_failed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
