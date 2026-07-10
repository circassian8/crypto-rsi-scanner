"""SQLite backup, restore, retention, and debris regressions."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tests.rsi import _api_helpers as _api

globals().update({name: getattr(_api, name) for name in dir(_api) if not name.startswith("__")})


def _sidecars(path: Path) -> tuple[Path, Path]:
    return Path(f"{path}-wal"), Path(f"{path}-shm")


def _open_immutable(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro&immutable=1", uri=True)


def test_sqlite_backup_api_integrity_retention_and_sidecar_pruning(tmp_path: Path):
    from crypto_rsi_scanner.backups import backup_database, latest_backup_status

    src = tmp_path / "source.db"
    backup_dir = tmp_path / "backups"
    conn = sqlite3.connect(src)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT)")
    conn.execute("INSERT INTO sample (value) VALUES ('ok')")
    conn.commit()
    conn.close()

    result = backup_database(
        src,
        backup_dir,
        keep=2,
        now=datetime(2026, 6, 8, 1, 2, 3, tzinfo=timezone.utc),
    )
    assert result.path.exists()
    assert result.quick_check == "ok"
    assert all(not path.exists() for path in _sidecars(result.path))
    copied = _open_immutable(result.path)
    try:
        assert copied.execute("SELECT value FROM sample").fetchone()[0] == "ok"
    finally:
        copied.close()

    old_wal, old_shm = _sidecars(result.path)
    old_wal.write_bytes(b"")
    old_shm.write_bytes(b"stale read sidecar")
    backup_database(src, backup_dir, keep=2, now=datetime(2026, 6, 8, 1, 2, 4, tzinfo=timezone.utc))
    third = backup_database(
        src,
        backup_dir,
        keep=2,
        now=datetime(2026, 6, 8, 1, 2, 5, tzinfo=timezone.utc),
    )
    backups = sorted(backup_dir.glob("source-*.db"))
    assert len(backups) == 2
    assert backups[-1] == third.path
    assert not result.path.exists()
    assert not old_wal.exists()
    assert not old_shm.exists()
    status = latest_backup_status(src, backup_dir)
    assert status.sidecar_count == 0
    assert status.temporary_count == 0
    assert status.debris_count == 0


def test_sqlite_restore_drill_is_immutable_and_checks_schema_counts(tmp_path: Path):
    from crypto_rsi_scanner.backups import (
        backup_database,
        format_restore_result,
        verify_backup,
        verify_restore,
    )

    src = tmp_path / "source.db"
    backup_dir = tmp_path / "backups"
    conn = sqlite3.connect(src)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE scans (id INTEGER PRIMARY KEY)")
    conn.execute("CREATE TABLE signals (id INTEGER PRIMARY KEY)")
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("CREATE TABLE paper_trades (id INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO scans DEFAULT VALUES")
    conn.execute("INSERT INTO meta (key, value) VALUES ('k', 'v')")
    conn.commit()
    conn.close()

    backup = backup_database(
        src,
        backup_dir,
        now=datetime(2026, 6, 8, 2, 0, 0, tzinfo=timezone.utc),
    )
    result = verify_restore(
        backup.path,
        expected_tables=("scans", "signals", "meta", "paper_trades"),
    )
    assert result.quick_check == "ok"
    assert result.table_counts["scans"] == 1
    assert result.table_counts["meta"] == 1
    assert "SQLite restore drill complete" in format_restore_result(result)
    assert all(not path.exists() for path in _sidecars(backup.path))

    wal, _ = _sidecars(backup.path)
    wal.write_bytes(b"pending WAL content")
    try:
        verify_backup(backup.path)
    except RuntimeError as exc:
        assert "non-empty WAL sidecar" in str(exc)
    else:
        raise AssertionError("non-empty backup WAL must block immutable verification")


def test_backup_freshness_status_reports_debris(tmp_path: Path):
    from crypto_rsi_scanner import config, status_report
    from crypto_rsi_scanner.backups import backup_database

    src = tmp_path / "rsi_scanner.db"
    backup_dir = tmp_path / "backups"
    conn = sqlite3.connect(src)
    conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

    st = _fresh_storage()
    orig_db = config.DB_PATH
    orig_dir = config.BACKUP_DIR
    orig_keep = config.BACKUP_KEEP
    orig_stale = config.BACKUP_STALE_HOURS
    orig_logs = config.LOG_FILES
    config.DB_PATH = src
    config.BACKUP_DIR = backup_dir
    config.BACKUP_KEEP = 2
    config.BACKUP_STALE_HOURS = 24
    config.LOG_FILES = []
    try:
        created = datetime(2026, 6, 8, 1, 0, 0, tzinfo=timezone.utc)
        backup = backup_database(src, backup_dir, keep=2, now=created)

        fresh = status_report.format_status(st, now=created + timedelta(hours=2))
        assert "backup: OK" in fresh
        assert "rsi_scanner-20260608T010000Z.db" in fresh
        assert "2.0h ago" in fresh
        assert "1/2 retained" in fresh
        assert "backup debris: clean" in fresh

        wal, shm = _sidecars(backup.path)
        wal.write_bytes(b"")
        shm.write_bytes(b"stale read sidecar")
        (backup_dir / "rsi_scanner-interrupted.db.tmp").write_bytes(b"partial")
        debris = status_report.format_status(st, now=created + timedelta(hours=2))
        assert "backup debris: WARNING 2 sidecar(s), 1 temporary file(s)" in debris

        stale = status_report.format_status(st, now=created + timedelta(hours=25))
        assert "backup: STALE" in stale

        config.BACKUP_DIR = tmp_path / "empty"
        missing = status_report.format_status(st, now=created + timedelta(hours=2))
        assert "backup: MISSING" in missing
        assert "run main.py --backup-db" in missing
        assert "backup debris: clean" in missing
    finally:
        config.DB_PATH = orig_db
        config.BACKUP_DIR = orig_dir
        config.BACKUP_KEEP = orig_keep
        config.BACKUP_STALE_HOURS = orig_stale
        config.LOG_FILES = orig_logs
        st.close()
