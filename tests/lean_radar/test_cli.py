from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from crypto_rsi_scanner.lean_radar.cli import run


def test_readiness_is_observational_and_does_not_create_database(tmp_path: Path) -> None:
    database = tmp_path / "missing.db"

    code, payload = run(("--db", str(database), "readiness"))

    assert code == 0
    assert payload["status"] == "setup_required"
    assert payload["provider_call_attempted"] is False
    assert payload["telegram_send_attempted"] is False
    assert not database.exists()


def test_catalog_import_requires_confirmation(tmp_path: Path) -> None:
    database = tmp_path / "lean.db"
    catalog = tmp_path / "catalog.json"
    source = (
        Path(__file__).resolve().parents[2]
        / "fixtures/bybit_execution_quality/instruments_info.json"
    )
    catalog.write_bytes(source.read_bytes())

    code, payload = run(
        ("--db", str(database), "bybit-import", "--catalog", str(catalog))
    )

    assert code == 2
    assert payload["status"] == "confirmation_required"
    assert payload["provider_call_attempted"] is False
    assert not database.exists()


def test_calendar_readiness_is_observational_and_import_is_confirmed(
    tmp_path: Path,
) -> None:
    database = tmp_path / "lean.db"
    calendar = tmp_path / "calendar.json"
    calendar.write_text(
        json.dumps(
            {
                "schema_version": "lean_calendar_import_v1",
                "source_observed_at": "2026-07-23T12:00:00Z",
                "source_name": "Official calendar bundle",
                "events": [
                    {
                        "event_id": "cpi-2026-07-24",
                        "title": "Consumer price index",
                        "category": "cpi",
                        "starts_at": "2026-07-24T12:30:00Z",
                        "time_certainty": "exact",
                        "importance": "high",
                        "affected_symbols": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    ready_code, ready = run(("--db", str(database), "calendar-readiness"))
    blocked_code, blocked = run(
        (
            "--db",
            str(database),
            "calendar-import",
            "--calendar",
            str(calendar),
        )
    )

    assert ready_code == 0
    assert ready["status"] == "setup_required"
    assert blocked_code == 2
    assert blocked["status"] == "confirmation_required"
    assert not database.exists()

    import_code, imported = run(
        (
            "--db",
            str(database),
            "calendar-import",
            "--calendar",
            str(calendar),
            "--confirm",
        )
    )
    assert import_code == 0
    assert imported["status"] == "imported"
    assert imported["calendar_event_count"] == 1
    assert database.exists()


def test_make_readiness_is_no_write_and_names_the_safe_import(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    database = tmp_path / "make-readiness.db"

    completed = subprocess.run(
        (
            "make",
            "lean-radar-readiness",
            f"PYTHON={sys.executable}",
            f"LEAN_RADAR_DB_PATH={database}",
        ),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert "Status: setup_required" in completed.stdout
    assert "CONFIRM=1 make lean-radar-bybit-universe-import" in completed.stdout
    assert "Research only · no send · no trading" in completed.stdout
    assert not database.exists()


def test_make_outcomes_and_health_are_safe_without_runtime_state(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    database = tmp_path / "missing-runtime.db"

    outcomes = subprocess.run(
        (
            "make",
            "lean-radar-outcomes",
            f"PYTHON={sys.executable}",
            f"LEAN_RADAR_DB_PATH={database}",
            "LEAN_RADAR_OUTCOMES_EVALUATED_AT=2026-07-23T12:00:00Z",
        ),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    health = subprocess.run(
        (
            "make",
            "lean-radar-health",
            f"PYTHON={sys.executable}",
            f"LEAN_RADAR_DB_PATH={database}",
            "LEAN_RADAR_HEALTH_EVALUATED_AT=2026-07-23T12:00:00Z",
        ),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert "Status: setup_required" in outcomes.stdout
    assert "Status: setup_required" in health.stdout
    assert "Research only · no send · no trading" in outcomes.stdout
    assert "Research only · no send · no trading" in health.stdout
    assert not database.exists()


def test_make_telegram_preview_and_readiness_are_no_send_no_write(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[2]
    database = tmp_path / "missing-telegram-runtime.db"
    common = (
        f"PYTHON={sys.executable}",
        f"LEAN_RADAR_DB_PATH={database}",
        "LEAN_RADAR_TELEGRAM_EVALUATED_AT=2026-07-23T12:00:00Z",
    )

    preview = subprocess.run(
        ("make", "lean-radar-telegram-preview", *common),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    readiness = subprocess.run(
        ("make", "lean-radar-telegram-readiness", *common),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
        env={
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
            "RSI_EVENT_ALERTS_ENABLED": "0",
        },
    )

    assert "Status: setup_required" in preview.stdout
    assert "No send attempted." in preview.stdout
    assert "Status: setup_required" in readiness.stdout
    assert "no provider call · no send" in readiness.stdout
    assert not database.exists()


def test_make_telegram_send_requires_both_explicit_guards(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    database = tmp_path / "never-created.db"

    unconfirmed = subprocess.run(
        (
            "make",
            "lean-radar-telegram-send",
            f"PYTHON={sys.executable}",
            f"LEAN_RADAR_DB_PATH={database}",
        ),
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
        env={
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
            "RSI_EVENT_ALERTS_ENABLED": "0",
        },
    )
    no_environment_guard = subprocess.run(
        (
            "make",
            "lean-radar-telegram-send",
            "CONFIRM=1",
            f"PYTHON={sys.executable}",
            f"LEAN_RADAR_DB_PATH={database}",
        ),
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
        env={
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
            "RSI_EVENT_ALERTS_ENABLED": "0",
        },
    )

    assert unconfirmed.returncode != 0
    assert "without CONFIRM=1" in unconfirmed.stderr
    assert no_environment_guard.returncode != 0
    assert "without RSI_EVENT_ALERTS_ENABLED=1" in no_environment_guard.stderr
    assert not database.exists()
