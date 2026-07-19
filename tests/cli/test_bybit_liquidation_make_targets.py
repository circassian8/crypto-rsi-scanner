"""Static wiring checks for the detached Bybit liquidation import commands."""

from __future__ import annotations

from pathlib import Path
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE = "crypto_rsi_scanner.event_alpha.operations.bybit_liquidation_capture"
TRANSCRIPT = "BYBIT_LIQUIDATION_TRANSCRIPT=/tmp/operator-transcript.json"
NAMESPACE = (
    "BYBIT_LIQUIDATION_CAPTURE_NAMESPACE="
    "radar_bybit_liquidation_transcript_20260719t140000000000z_0123456789ab"
)


def _dry_run(target: str, *variables: str) -> str:
    return subprocess.check_output(
        ["make", "-n", target, *variables, "PYTHON=python3"],
        cwd=REPO_ROOT,
        text=True,
    )


def test_bybit_liquidation_transcript_make_targets_keep_explicit_boundaries() -> None:
    smoke = _dry_run("radar-derivatives-bybit-liquidation-capture-smoke")
    validate = _dry_run(
        "radar-derivatives-bybit-liquidation-validate-local",
        TRANSCRIPT,
    )
    imported = _dry_run(
        "radar-derivatives-bybit-liquidation-import-local",
        TRANSCRIPT,
        "CONFIRM=1",
    )
    status = _dry_run(
        "radar-derivatives-bybit-liquidation-status",
        NAMESPACE,
    )

    assert f"-m {MODULE} capture-smoke" in smoke
    assert "--artifact-base" not in smoke
    assert f"-m {MODULE} validate-local" in validate
    assert '--input "/tmp/operator-transcript.json"' in validate
    assert f"-m {MODULE} import-local" in imported
    assert "CONFIRM=1 is required" in imported
    assert "--artifact-base" in imported
    assert "--confirm" in imported
    assert f"-m {MODULE} status" in status
    assert "--namespace" in status
    assert NAMESPACE.split("=", 1)[1] in status
