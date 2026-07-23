from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from crypto_rsi_scanner.lean_radar.cli import run
from crypto_rsi_scanner.lean_radar.dashboard_smoke import (
    SMOKE_NOW,
    build_preview_database,
)
from crypto_rsi_scanner.lean_radar.store import LeanRadarStore


def _cycle_market_rows(path: Path) -> Path:
    quiet = [100.0 + (0.2 if index % 2 else 0.0) for index in range(30)]
    rapid = [100.0 for _ in range(25)] + [100.0, 102.0, 104.0, 107.0, 110.0]
    values = (
        ("bitcoin", "btc", 1_000_000_000_000.0, 10_000_000_000.0, 1.0, 0.2, quiet),
        ("ethereum", "eth", 500_000_000_000.0, 5_000_000_000.0, 1.0, 0.3, quiet),
        ("solana", "sol", 100_000_000.0, 80_000_000.0, 12.0, 6.0, rapid),
        ("ripple", "xrp", 100_000_000_000.0, 1_000_000_000.0, 0.0, 0.0, quiet),
        ("dogecoin", "doge", 50_000_000_000.0, 500_000_000.0, 0.0, 0.0, quiet),
    )
    rows = [
        {
            "id": asset_id,
            "symbol": symbol,
            "name": asset_id.title(),
            "current_price": prices[-1],
            "market_cap": market_cap,
            "market_cap_rank": index,
            "total_volume": volume,
            "price_change_percentage_1h_in_currency": return_1h,
            "price_change_percentage_24h_in_currency": return_24h,
            "price_change_percentage_7d_in_currency": return_24h * 1.5,
            "return_unit": "percent_points",
            "spread_bps": 8.0,
            "sparkline_in_7d": {"price": prices},
        }
        for index, (
            asset_id,
            symbol,
            market_cap,
            volume,
            return_24h,
            return_1h,
            prices,
        ) in enumerate(values, start=1)
    ]
    path.write_text(json.dumps(rows), encoding="utf-8")
    return path


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
            "lean-radar",
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


def test_cycle_runs_one_complete_no_send_operator_sequence(tmp_path: Path) -> None:
    database = build_preview_database(tmp_path / "cycle.db")
    store = LeanRadarStore(database)
    market_rows = _cycle_market_rows(tmp_path / "market-rows.json")
    observed_at = SMOKE_NOW.replace(hour=13, minute=21)
    before_notifications = store.notification_states()

    code, payload = run(
        (
            "--db",
            str(database),
            "cycle",
            "--source-mode",
            "fixture",
            "--markets",
            str(market_rows),
            "--observed-at",
            observed_at.isoformat(),
        )
    )

    assert code == 0
    assert payload["status"] == "complete"
    assert payload["scan"]["status"] == "complete"
    assert payload["scan"]["snapshot_count"] == 5
    assert payload["outcomes"]["status"] in {"ready", "complete"}
    assert payload["health"]["data_freshness"] == "fresh"
    assert payload["telegram_preview"]["market_idea_freshness"] == "current"
    assert payload["provider_call_attempted"] is False
    assert payload["telegram_send_attempted"] is False
    assert payload["database_write_attempted"] is True
    assert payload["next_safe_command"] == "make lean-radar-dashboard"
    assert store.notification_states() == before_notifications
    for field in (
        "telegram_sends",
        "trades_created",
        "orders_created",
        "paper_trades_created",
        "normal_rsi_signal_rows_written",
        "triggered_fade_created",
    ):
        assert payload[field] == 0


def test_make_cycle_fails_safe_without_runtime_or_provider_call(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    database = tmp_path / "missing-cycle.db"

    completed = subprocess.run(
        (
            "make",
            "lean-radar-cycle",
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
            "RSI_EVENT_DISCOVERY_UNIVERSE_LIVE": "0",
            "RSI_EVENT_ALERTS_ENABLED": "0",
        },
    )

    assert completed.returncode != 0
    assert "Status: blocked" in completed.stdout
    assert "Scan: blocked" in completed.stdout
    assert "Telegram preview: 0 messages · 0 due items · no send" in completed.stdout
    assert "CONFIRM=1 make lean-radar-bybit-universe-import" in completed.stdout
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
