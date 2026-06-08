"""SQLite backup helpers.

The scanner DB runs in WAL mode and is shared by the daily scan plus the bot
listener, so backups must use SQLite's online backup API rather than copying the
main `.db` file directly. The API gives a consistent snapshot even while another
connection is reading/writing.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class BackupResult:
    path: Path
    size_bytes: int
    quick_check: str
    deleted: tuple[Path, ...]


def _utc_stamp(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _backup_name(source: Path, now: datetime | None = None) -> str:
    return f"{source.stem}-{_utc_stamp(now)}.db"


def verify_backup(path: Path) -> str:
    """Open a backup and run SQLite's integrity check."""
    conn = sqlite3.connect(str(path))
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
        result = str(row[0]) if row else ""
        if result.lower() != "ok":
            raise RuntimeError(f"SQLite integrity_check failed: {result}")
        return result
    finally:
        conn.close()


def prune_backups(backup_dir: Path, source_stem: str, keep: int) -> tuple[Path, ...]:
    """Keep the newest `keep` backups for this DB stem; delete older ones."""
    if keep <= 0:
        return ()
    backups = sorted(backup_dir.glob(f"{source_stem}-*.db"), key=lambda p: p.name)
    extra = backups[:-keep]
    deleted: list[Path] = []
    for path in extra:
        path.unlink(missing_ok=True)
        deleted.append(path)
    return tuple(deleted)


def backup_database(
    source: Path,
    backup_dir: Path,
    *,
    keep: int = 14,
    now: datetime | None = None,
) -> BackupResult:
    """Create, verify, and retain a SQLite DB backup.

    Writes through a temporary file first; the final `.db` appears only after the
    backup copied cleanly and passed `PRAGMA integrity_check`.
    """
    source = Path(source).expanduser()
    backup_dir = Path(backup_dir).expanduser()
    if not source.exists():
        raise FileNotFoundError(f"database not found: {source}")
    backup_dir.mkdir(parents=True, exist_ok=True)

    final = backup_dir / _backup_name(source, now)
    suffix = 1
    while final.exists():
        final = backup_dir / f"{source.stem}-{_utc_stamp(now)}-{suffix}.db"
        suffix += 1
    tmp = final.with_suffix(final.suffix + ".tmp")
    tmp.unlink(missing_ok=True)

    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True, timeout=30.0)
    dst = sqlite3.connect(str(tmp))
    try:
        src.execute("PRAGMA busy_timeout=30000")
        src.backup(dst)
    finally:
        dst.close()
        src.close()

    try:
        quick_check = verify_backup(tmp)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    tmp.replace(final)
    deleted = prune_backups(backup_dir, source.stem, keep)
    return BackupResult(
        path=final,
        size_bytes=final.stat().st_size,
        quick_check=quick_check,
        deleted=deleted,
    )


def format_backup_result(result: BackupResult) -> str:
    size_mb = result.size_bytes / (1024 * 1024)
    lines = [
        "SQLite backup complete",
        f"path: {result.path}",
        f"size: {size_mb:.2f} MB",
        f"integrity_check: {result.quick_check}",
        f"pruned: {len(result.deleted)} old backup(s)",
    ]
    return "\n".join(lines)
