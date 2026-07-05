"""Dispatch the ops CLI commands end-to-end in a subprocess.

Regression guard for the 2026-07-03 outage: the ops command family
(``--status``, ``--backup-db``, ``--verify-restore``, ``--rotate-logs``)
crashed with ``ModuleNotFoundError`` at dispatch time while ``make verify``
stayed green, because nothing in the gate ever *executed* these commands.

These smokes run the real ``main.py`` dispatch path. Backup/restore/log
writes are redirected to a temp directory; the DB access is the same
read-only pattern the launchd agents use. No network, no sends, no trades.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _run_cli(args: list[str], env_overrides: dict[str, str]) -> subprocess.CompletedProcess:
    import os

    env = dict(os.environ)
    env.update(
        {
            "RSI_EVENT_ALERTS_ENABLED": "0",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        }
    )
    env.update(env_overrides)
    return subprocess.run(
        [sys.executable, "main.py", *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _assert_clean(result: subprocess.CompletedProcess, label: str) -> None:
    combined = (result.stdout or "") + (result.stderr or "")
    assert "Traceback" not in combined, f"{label} raised:\n{combined[-2000:]}"
    assert result.returncode == 0, f"{label} exited {result.returncode}:\n{combined[-2000:]}"


def test_status_command_dispatches():
    result = _run_cli(["--status"], {})
    _assert_clean(result, "--status")
    assert "RSI SCANNER STATUS" in result.stdout


def test_backup_restore_and_rotate_commands_dispatch():
    with tempfile.TemporaryDirectory() as tmp:
        backup_dir = str(Path(tmp) / "backups")
        log_file = Path(tmp) / "smoke.log"
        log_file.write_text("smoke\n", encoding="utf-8")

        backup = _run_cli(["--backup-db"], {"RSI_BACKUP_DIR": backup_dir})
        _assert_clean(backup, "--backup-db")
        assert "integrity_check: ok" in backup.stdout

        restore = _run_cli(["--verify-restore"], {"RSI_BACKUP_DIR": backup_dir})
        _assert_clean(restore, "--verify-restore")

        rotate = _run_cli(["--rotate-logs"], {"RSI_LOG_FILES": str(log_file)})
        _assert_clean(rotate, "--rotate-logs")


if __name__ == "__main__":  # standalone-compatible like the other suites
    test_status_command_dispatches()
    test_backup_restore_and_rotate_commands_dispatch()
    print("ok")
