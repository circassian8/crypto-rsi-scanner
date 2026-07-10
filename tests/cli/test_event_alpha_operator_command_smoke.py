"""End-to-end no-send smokes for Event Alpha operator readiness commands."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _run_cli(args: list[str], *, artifact_base: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update(
        {
            "RSI_EVENT_ALERTS_ENABLED": "0",
            "RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR": str(artifact_base),
            "TELEGRAM_BOT_TOKEN": "",
            "TELEGRAM_CHAT_ID": "",
            "OPENAI_API_KEY": "",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        }
    )
    return subprocess.run(
        [sys.executable, "main.py", *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _assert_clean(result: subprocess.CompletedProcess, label: str) -> str:
    combined = (result.stdout or "") + (result.stderr or "")
    assert "Traceback" not in combined, f"{label} raised:\n{combined[-3000:]}"
    assert "NameError" not in combined
    assert "TypeError" not in combined
    assert result.returncode == 0, f"{label} exited {result.returncode}:\n{combined[-3000:]}"
    return combined


def test_event_alpha_operator_readiness_commands_dispatch_without_runtime_errors():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        artifact_base = root / "artifacts"
        checklist = _run_cli(
            [
                "--event-alpha-burn-in-checklist",
                "--days",
                "30",
                "--event-alpha-profile",
                "live_burn_in_no_send",
                "--event-alpha-artifact-namespace",
                "live_burn_in_no_send",
            ],
            artifact_base=artifact_base,
        )
        checklist_text = _assert_clean(checklist, "burn-in checklist")
        assert "authoritative_scorecard: event_alpha_burn_in_scorecard_v1" in checklist_text
        assert "READY_FOR_RESEARCH_SEND: no" in checklist_text

        v1 = _run_cli(
            [
                "--event-alpha-v1-readiness",
                "--days",
                "30",
                "--event-alpha-profile",
                "no_key_live",
                "--event-alpha-artifact-namespace",
                "no_key_live",
            ],
            artifact_base=artifact_base,
        )
        v1_text = _assert_clean(v1, "v1 readiness")
        assert "BURN_IN_CONTRACT_ENOUGH_DATA: no" in v1_text
        assert "READY_FOR_CALIBRATED_RESEARCH_SEND: no" in v1_text

        pack_path = root / "burn-in-pack.zip"
        pack = _run_cli(
            [
                "--event-alpha-export-burn-in-pack",
                str(pack_path),
                "--days",
                "30",
                "--event-alpha-profile",
                "live_burn_in_no_send",
                "--event-alpha-artifact-namespace",
                "live_burn_in_no_send",
            ],
            artifact_base=artifact_base,
        )
        _assert_clean(pack, "burn-in pack")
        assert pack_path.exists()
        with zipfile.ZipFile(pack_path) as archive:
            checklist_report = archive.read("reports/burn_in_checklist.txt").decode()
            v1_report = archive.read("reports/v1_readiness.txt").decode()
        assert "authoritative_scorecard: event_alpha_burn_in_scorecard_v1" in checklist_report
        assert "BURN_IN_CONTRACT_ENOUGH_DATA: no" in v1_report
