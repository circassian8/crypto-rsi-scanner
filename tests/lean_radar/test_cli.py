from __future__ import annotations

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
