"""Pure command planning for the daily no-send Event Alpha burn-in loop."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from . import common


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
        (python, "-m", "crypto_rsi_scanner.project_health.radar_north_star", "--check-burn-in-contract"),
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
