"""Dependency reproducibility and cross-version CI policy tests."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_dependency_lock_and_make_targets_are_reproducible():
    requirements = (REPO_ROOT / "requirements.in").read_text(encoding="utf-8")
    lock = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    assert (REPO_ROOT / ".python-version").read_text(encoding="utf-8").strip() == "3.13"
    assert any("make lock-dependencies" in line for line in lock.splitlines()[:3])
    locked_requirement_lines = [line for line in lock.splitlines() if line and line[0].isalnum()]
    assert locked_requirement_lines
    assert all("==" in line for line in locked_requirement_lines)
    assert lock.count("--hash=sha256:") > 100
    direct_names = {
        re.split(r"[<>=!~]", line, maxsplit=1)[0].strip().casefold()
        for line in requirements.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    locked_names = {
        match.group(1).casefold()
        for match in re.finditer(r"^([A-Za-z0-9_.-]+)==", lock, re.MULTILINE)
    }
    assert direct_names <= locked_names
    assert "numpy==2.4.6 ; python_full_version < '3.12'" in lock
    assert "numpy==2.5.1 ; python_full_version >= '3.12'" in lock
    assert "DEPENDENCY_INPUT ?= requirements.in" in makefile
    assert "DEPENDENCY_LOCK ?= requirements.txt" in makefile
    assert "DEPENDENCY_MIN_PYTHON ?= 3.11" in makefile
    assert "UV_VERSION ?= 0.11.28" in makefile
    assert "PIP_AUDIT_VERSION ?= 2.10.1" in makefile
    assert "--universal --python-version $(DEPENDENCY_MIN_PYTHON) --generate-hashes" in makefile
    assert ".venv/bin/python -m pip install --require-hashes -r $(DEPENDENCY_LOCK)" in makefile
    assert "--strict --require-hashes --disable-pip" in makefile
    assert "dependency-verify: dependency-lock-check dependency-audit" in makefile

    audit_dry = subprocess.check_output(
        ["make", "-n", "dependency-audit", "PYTHON=python3"],
        cwd=REPO_ROOT,
        text=True,
    )
    assert "python3 -m pip_audit" in audit_dry
    assert "-r requirements.txt" in audit_dry


def test_github_actions_use_hash_lock_and_python_parity_without_live_paths():
    verify_text = (REPO_ROOT / ".github" / "workflows" / "verify.yml").read_text(encoding="utf-8")
    smoke_text = (REPO_ROOT / ".github" / "workflows" / "event-alpha-smoke.yml").read_text(encoding="utf-8")
    text = (verify_text + "\n" + smoke_text).casefold()

    assert "on:\n  push:\n  pull_request:" in verify_text
    assert "workflow_dispatch" not in verify_text
    assert "on:\n  workflow_dispatch:" in smoke_text
    assert "\n  push:" not in smoke_text
    assert "\n  pull_request:" not in smoke_text
    assert "permissions:\n  contents: read" in verify_text
    assert "permissions:\n  contents: read" in smoke_text
    assert 'python-version: ["3.11", "3.13"]' in verify_text
    assert 'python-version: ["3.11", "3.13"]' in smoke_text
    assert "python-version: ${{ matrix.python-version }}" in verify_text
    assert "python-version: ${{ matrix.python-version }}" in smoke_text
    assert "fail-fast: false" in verify_text
    assert "needs: dependency-audit" in verify_text
    assert "name: Dependency audit (Python ${{ matrix.python-version }})" in verify_text
    assert verify_text.count('python-version: ["3.11", "3.13"]') == 2
    assert "make dependency-lock-check UV=uv" in verify_text
    assert "make dependency-audit PYTHON=python3" in verify_text
    assert "uv==0.11.28 pip-audit==2.10.1" in verify_text
    assert "if: matrix.python-version == '3.13'" in verify_text
    assert verify_text.count("make verify PYTHON=python3") == 1
    assert verify_text.count("--require-hashes -r requirements.txt") == 1
    assert smoke_text.count("--require-hashes -r requirements.txt") == 1
    assert "cache-dependency-path: requirements.txt" in verify_text
    assert "cache-dependency-path: requirements.txt" in smoke_text
    for workflow in (verify_text, smoke_text):
        assert 'RSI_EVENT_ALERTS_ENABLED: "0"' in workflow
        assert 'RSI_EVENT_RESEARCH_NOW: "2026-06-15T16:00:00Z"' in workflow
        assert 'PYTEST_DISABLE_PLUGIN_AUTOLOAD: "1"' in workflow

    forbidden = (
        "allow_live",
        "allow-live",
        "rsi_event_alerts_enabled=1",
        'rsi_event_alerts_enabled: "1"',
        "secrets.",
        "telegram",
        "api_key",
        "api-secret",
        "api_secret",
        "bot_token",
        "event-alert-send",
        "event-alpha-cycle-send",
        "event-alpha-notify-cycle",
        "event-alpha-telegram-send-one-cycle",
        "--event-alert-send",
    )
    for item in forbidden:
        assert item not in text
    assert "make verify python=python3" in text
    assert "event-alpha-integrated-radar-smoke" in text
    assert "--upgrade pip" not in text


def test_dependabot_tracks_python_and_github_actions_dependencies():
    config = (REPO_ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    assert config.startswith("version: 2\n")
    assert config.count("package-ecosystem:") == 2
    assert "package-ecosystem: pip" in config
    assert "package-ecosystem: github-actions" in config
    assert config.count('directory: "/"') == 2
    assert config.count("interval: weekly") == 2
