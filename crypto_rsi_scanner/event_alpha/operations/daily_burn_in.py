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


def default_namespace(now: datetime | None = None) -> str:
    stamp = (now or common.utc_now()).astimezone(timezone.utc).strftime("%Y%m%d")
    return f"live_burn_in_{stamp}"


def build_steps(*, python: str, profile: str, namespace: str, include_coinalyze_rehearsal: bool) -> tuple[BurnInStep | dict[str, Any], ...]:
    base = ("--event-alpha-profile", profile, "--event-alpha-artifact-namespace", namespace)
    steps: list[BurnInStep | dict[str, Any]] = [
        BurnInStep("burn_in_contract", (python, "-m", "crypto_rsi_scanner.project_health.radar_north_star", "--burn-in-contract-only")),
        BurnInStep("live_provider_readiness", (python, "main.py", "--event-alpha-live-provider-readiness", *base)),
        BurnInStep("cryptopanic_preflight", (python, "main.py", "--event-alpha-cryptopanic-preflight", *base)),
        BurnInStep("coinalyze_preflight", (python, "main.py", "--event-alpha-coinalyze-preflight", *base)),
        (
            BurnInStep("coinalyze_no_send_rehearsal", (python, "main.py", "--event-alpha-coinalyze-no-send-rehearsal", *base))
            if include_coinalyze_rehearsal
            else {
                "name": "coinalyze_no_send_rehearsal",
                "status": "skipped",
                "skip_reason": "requires RSI_EVENT_ALPHA_DAILY_BURN_IN_ALLOW_COINALYZE_REHEARSAL=1 and provider allow flags",
                "provider_category_impact": "derivatives/OI/funding live rehearsal not sampled in this run",
            }
        ),
        BurnInStep("bybit_announcements_preflight", (python, "main.py", "--event-alpha-bybit-announcements-preflight", *base)),
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
        ),
        BurnInStep("source_coverage", (python, "main.py", "--event-alpha-source-coverage-report", *base)),
        BurnInStep("notification_preview", (python, "main.py", "--event-alpha-notify-preview-from-artifacts", *base)),
        BurnInStep("daily_brief", (python, "main.py", "--event-alpha-daily-brief", *base)),
        BurnInStep("review_inbox", (python, "-m", "crypto_rsi_scanner.event_alpha.operations.review_inbox", "--profile", profile, "--artifact-namespace", namespace)),
        BurnInStep("artifact_doctor", (python, "main.py", "--event-alpha-artifact-doctor", *base)),
        BurnInStep("burn_in_scorecard", (python, "-m", "crypto_rsi_scanner.event_alpha.operations.scorecard", "--profile", profile, "--artifact-namespace", namespace)),
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
    steps = build_steps(python=py, profile=profile, namespace=namespace, include_coinalyze_rehearsal=allow_rehearsal)
    step_rows: list[dict[str, Any]] = []
    for step in steps:
        if isinstance(step, Mapping):
            step_rows.append(dict(step))
            continue
        row = _run_step(step, env=env, cwd=common.repo_root_from_module())
        step_rows.append(row)
        if step.required and row["status"] != "passed" and not continue_on_error:
            break
    payload = common.with_safety(
        {
            "schema_version": "event_alpha_daily_burn_in_run_v1",
            "row_type": "event_alpha_daily_burn_in_run",
            "generated_at": generated.isoformat(),
            "profile": profile,
            "artifact_namespace": namespace,
            "namespace_dir": common.rel_path(context.namespace_dir),
            "steps": step_rows,
            "steps_total": len(step_rows),
            "steps_passed": sum(1 for row in step_rows if row.get("status") == "passed"),
            "steps_skipped": sum(1 for row in step_rows if row.get("status") == "skipped"),
            "steps_failed": sum(1 for row in step_rows if row.get("status") == "failed"),
            "required_failed": [
                row.get("name")
                for row in step_rows
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
    common.append_jsonl(context.run_ledger_path, _ledger_row(payload))
    return payload


def format_daily_burn_in_report(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Event Alpha Daily Live No-Send Burn-In",
        "",
        "Research-only daily operating loop. No Telegram sends, trades, paper trades, normal RSI rows, live provider calls by default, or Event Alpha-created `TRIGGERED_FADE` are authorized by this report.",
        "",
        f"- generated_at: `{payload.get('generated_at')}`",
        f"- profile: `{payload.get('profile')}`",
        f"- artifact_namespace: `{payload.get('artifact_namespace')}`",
        f"- namespace_dir: `{payload.get('namespace_dir')}`",
        f"- steps: `{payload.get('steps_passed')}` passed, `{payload.get('steps_skipped')}` skipped, `{payload.get('steps_failed')}` failed",
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
        if row.get("skip_reason"):
            lines.append(f"- skip_reason: {row.get('skip_reason')}")
        if row.get("provider_category_impact"):
            lines.append(f"- provider/category impact: {row.get('provider_category_impact')}")
        if row.get("command"):
            lines.append(f"- command: `{row.get('command')}`")
        if row.get("duration_seconds") is not None:
            lines.append(f"- duration_seconds: `{row.get('duration_seconds')}`")
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
    proc = subprocess.run(
        list(step.command),
        cwd=cwd,
        env=dict(env),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    duration = round(time.monotonic() - before, 3)
    return {
        "name": step.name,
        "status": "passed" if proc.returncode == 0 else "failed",
        "required": step.required,
        "started_at": started.isoformat(),
        "duration_seconds": duration,
        "returncode": proc.returncode,
        "command": " ".join(step.command),
        "stdout_tail": _tail(proc.stdout),
        "stderr_tail": _tail(proc.stderr),
    }


def _tail(text: str, *, limit: int = 1200) -> str:
    clean = (text or "").strip()
    if len(clean) <= limit:
        return clean
    return clean[-limit:]


def _ledger_row(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "event_alpha_daily_burn_in_ledger_v1",
        "row_type": "daily_burn_in",
        "run_mode": "burn_in",
        "profile": payload.get("profile"),
        "artifact_namespace": payload.get("artifact_namespace"),
        "started_at": payload.get("generated_at"),
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
    args = parser.parse_args(argv)
    payload = run_daily_burn_in(
        profile=args.profile,
        artifact_namespace=args.artifact_namespace,
        python=args.python,
        base_dir=args.base_dir,
        continue_on_error=not args.stop_on_required_failure,
        include_coinalyze_rehearsal=args.include_coinalyze_rehearsal,
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
