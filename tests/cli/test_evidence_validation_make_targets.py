"""Static contracts for guarded Event Alpha evidence-validation Make targets."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _dry_run(target: str, *variables: str) -> str:
    return subprocess.check_output(
        ["make", "-n", target, "PYTHON=python3", *variables],
        cwd=REPO_ROOT,
        text=True,
    )


def test_evidence_cycle_readiness_target_is_observational() -> None:
    output = _dry_run(
        "event-alpha-evidence-cycle-readiness",
        "PROFILE=notify_llm_quality",
        "ARTIFACT_NAMESPACE=existing_evidence_plan",
    )

    assert "crypto_rsi_scanner.event_alpha.operations.evidence_cycle_readiness" in output
    assert "--profile notify_llm_quality" in output
    assert "--artifact-namespace existing_evidence_plan" in output
    assert "RSI_EVENT_ALERTS_ENABLED=0" in output
    assert "--require-cycle-ready" not in output
    assert "main.py --event-alpha-cycle" not in output
    assert "--event-alert-send" not in output
    assert "rm -rf" not in output


def test_guarded_evidence_validation_cycle_orders_one_no_send_namespace() -> None:
    namespace = "event_alpha_evidence_validation_static_contract"
    output = _dry_run(
        "event-alpha-evidence-validation-cycle",
        "PROFILE=notify_llm_quality",
        f"EVENT_ALPHA_EVIDENCE_VALIDATION_NAMESPACE={namespace}",
        "CONFIRM=1",
    )

    readiness = output.index(
        "crypto_rsi_scanner.event_alpha.operations.evidence_cycle_readiness"
    )
    confirmation = output.index('test "1" = "1"')
    cycle = output.index("main.py --event-alpha-cycle")
    coverage = output.index("main.py --event-alpha-source-coverage-report")
    brief = output.index("main.py --event-alpha-daily-brief")
    preview = output.index("main.py --event-alpha-notify-preview-from-artifacts")
    doctor = output.index("main.py --event-alpha-artifact-doctor")

    assert readiness < confirmation < cycle < coverage < brief < preview < doctor
    assert "--require-cycle-ready" in output
    assert output.count(f"RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE={namespace}") == 6
    assert output.count(f"--event-alpha-artifact-namespace {namespace}") == 5
    assert output.count("RSI_EVENT_ALERTS_ENABLED=0") == 6
    assert "--event-alpha-artifact-doctor-strict" in output
    assert "--event-alert-send" not in output
    assert "RSI_EVENT_ALERTS_ENABLED=1" not in output
    assert "RSI_EVENT_DISCOVERY_GDELT_LIVE=1" not in output
    assert "RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE=1" not in output
    assert "RSI_EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE=1" not in output
    assert "rm -rf" not in output


def test_evidence_validation_default_namespace_is_run_unique_shaped() -> None:
    output = _dry_run(
        "event-alpha-evidence-validation-cycle",
        "PROFILE=notify_llm_quality",
        "CONFIRM=1",
    )
    namespaces = set(
        re.findall(
            r"--artifact-namespace "
            r"(event_alpha_evidence_validation_\d{8}t\d{6}z_[0-9a-f]{8})",
            output,
        )
    )

    assert len(namespaces) == 1


def test_make_help_exposes_evidence_readiness_and_guarded_cycle() -> None:
    output = _dry_run("help")

    assert "event-alpha-evidence-cycle-readiness" in output
    assert "no calls or writes" in output
    assert "CONFIRM=1 make event-alpha-evidence-validation-cycle" in output
    assert "requires exact readiness and existing authorization" in output
