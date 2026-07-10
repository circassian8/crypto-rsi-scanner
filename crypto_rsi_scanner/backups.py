"""SQLite backup helpers.

The scanner DB runs in WAL mode and is shared by the daily scan plus the bot
listener, so backups must use SQLite's online backup API rather than copying the
main `.db` file directly. The API gives a consistent snapshot even while another
connection is reading/writing.
"""

from __future__ import annotations

import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .security import ensure_private_directory, ensure_private_file


@dataclass(frozen=True)
class BackupResult:
    path: Path
    size_bytes: int
    quick_check: str
    deleted: tuple[Path, ...]


@dataclass(frozen=True)
class BackupStatus:
    backup_dir: Path
    source_stem: str
    path: Path | None
    created_at: datetime | None
    age_hours: float | None
    size_bytes: int
    count: int
    sidecar_count: int
    temporary_count: int
    stale_after_hours: float

    @property
    def missing(self) -> bool:
        return self.path is None

    @property
    def stale(self) -> bool:
        return self.age_hours is None or self.age_hours >= self.stale_after_hours

    @property
    def state(self) -> str:
        if self.missing:
            return "MISSING"
        if self.stale:
            return "STALE"
        return "OK"

    @property
    def debris_count(self) -> int:
        return self.sidecar_count + self.temporary_count


@dataclass(frozen=True)
class RestoreCheckResult:
    backup_path: Path
    size_bytes: int
    quick_check: str
    table_counts: dict[str, int]
    missing_tables: tuple[str, ...]


def _utc_stamp(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _backup_name(source: Path, now: datetime | None = None) -> str:
    return f"{source.stem}-{_utc_stamp(now)}.db"


def _created_at_from_name(source_stem: str, path: Path) -> datetime | None:
    prefix = f"{source_stem}-"
    suffix = ".db"
    if not path.name.startswith(prefix) or not path.name.endswith(suffix):
        return None
    rest = path.name[len(prefix):-len(suffix)]
    stamp = rest.split("-", 1)[0]
    try:
        return datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _file_time(path: Path) -> datetime | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except FileNotFoundError:
        return None


def _immutable_read_uri(path: Path) -> str:
    """Return a read-only SQLite URI that cannot create WAL/SHM sidecars."""
    return f"{path.resolve().as_uri()}?mode=ro&immutable=1"


def _sqlite_sidecars(path: Path) -> tuple[Path, Path]:
    return Path(f"{path}-wal"), Path(f"{path}-shm")


def _assert_no_pending_wal(path: Path) -> None:
    wal, _ = _sqlite_sidecars(path)
    try:
        wal_size = wal.stat().st_size
    except FileNotFoundError:
        return
    if wal_size:
        raise RuntimeError(
            f"backup has a non-empty WAL sidecar ({wal_size} bytes): {wal}"
        )


def _backup_debris_counts(backup_dir: Path, source_stem: str) -> tuple[int, int]:
    if not backup_dir.exists():
        return 0, 0
    sidecars = {
        *backup_dir.glob(f"{source_stem}-*.db-wal"),
        *backup_dir.glob(f"{source_stem}-*.db-shm"),
    }
    temporary = {
        *backup_dir.glob(f"{source_stem}-*.db.tmp"),
        *backup_dir.glob(f"{source_stem}-*.db.tmp-wal"),
        *backup_dir.glob(f"{source_stem}-*.db.tmp-shm"),
    }
    return len(sidecars), len(temporary)


def verify_backup(path: Path) -> str:
    """Open a backup and run SQLite's integrity check."""
    path = Path(path).expanduser()
    _assert_no_pending_wal(path)
    conn = sqlite3.connect(_immutable_read_uri(path), uri=True)
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
        result = str(row[0]) if row else ""
        if result.lower() != "ok":
            raise RuntimeError(f"SQLite integrity_check failed: {result}")
        return result
    finally:
        conn.close()


def _sqlite_tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {str(r[0]) for r in rows}


def verify_restore(
    backup_path: Path,
    *,
    expected_tables: tuple[str, ...] = (),
) -> RestoreCheckResult:
    """Restore a backup into a temporary DB, verify it, and check key tables."""
    backup_path = Path(backup_path).expanduser()
    if not backup_path.exists():
        raise FileNotFoundError(f"backup not found: {backup_path}")

    with tempfile.TemporaryDirectory(prefix="rsi-restore-drill-") as tmpdir:
        restored = Path(tmpdir) / "restore.db"
        _assert_no_pending_wal(backup_path)
        src = sqlite3.connect(_immutable_read_uri(backup_path), uri=True, timeout=30.0)
        dst = sqlite3.connect(str(restored))
        try:
            src.execute("PRAGMA busy_timeout=30000")
            src.backup(dst)
        finally:
            dst.close()
            src.close()

        quick_check = verify_backup(restored)
        conn = sqlite3.connect(str(restored))
        try:
            tables = _sqlite_tables(conn)
            missing = tuple(t for t in expected_tables if t not in tables)
            if missing:
                raise RuntimeError(f"restore missing expected table(s): {', '.join(missing)}")
            counts: dict[str, int] = {}
            for table in expected_tables:
                counts[table] = int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
        finally:
            conn.close()

        return RestoreCheckResult(
            backup_path=backup_path,
            size_bytes=backup_path.stat().st_size,
            quick_check=quick_check,
            table_counts=counts,
            missing_tables=missing,
        )


def prune_backups(backup_dir: Path, source_stem: str, keep: int) -> tuple[Path, ...]:
    """Keep the newest `keep` backups for this DB stem; delete older ones."""
    if keep <= 0:
        return ()
    backups = sorted(backup_dir.glob(f"{source_stem}-*.db"), key=lambda p: p.name)
    extra = backups[:-keep]
    deleted: list[Path] = []
    for path in extra:
        path.unlink(missing_ok=True)
        for sidecar in _sqlite_sidecars(path):
            sidecar.unlink(missing_ok=True)
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
    ensure_private_directory(backup_dir, create=True)

    final = backup_dir / _backup_name(source, now)
    suffix = 1
    while final.exists():
        final = backup_dir / f"{source.stem}-{_utc_stamp(now)}-{suffix}.db"
        suffix += 1
    tmp = final.with_suffix(final.suffix + ".tmp")
    tmp.unlink(missing_ok=True)
    ensure_private_file(tmp, create=True)

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
    ensure_private_file(final)
    deleted = prune_backups(backup_dir, source.stem, keep)
    return BackupResult(
        path=final,
        size_bytes=final.stat().st_size,
        quick_check=quick_check,
        deleted=deleted,
    )


def latest_backup_status(
    source: Path,
    backup_dir: Path,
    *,
    now: datetime | None = None,
    stale_after_hours: float = 72.0,
) -> BackupStatus:
    """Return freshness metadata for the newest retained backup."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)

    source = Path(source).expanduser()
    backup_dir = Path(backup_dir).expanduser()
    backups = sorted(backup_dir.glob(f"{source.stem}-*.db")) if backup_dir.exists() else []
    if not backups:
        sidecar_count, temporary_count = _backup_debris_counts(backup_dir, source.stem)
        return BackupStatus(
            backup_dir=backup_dir,
            source_stem=source.stem,
            path=None,
            created_at=None,
            age_hours=None,
            size_bytes=0,
            count=0,
            sidecar_count=sidecar_count,
            temporary_count=temporary_count,
            stale_after_hours=stale_after_hours,
        )

    def sort_key(path: Path) -> tuple[datetime, str]:
        created = _created_at_from_name(source.stem, path) or _file_time(path)
        return created or datetime.min.replace(tzinfo=timezone.utc), path.name

    latest = max(backups, key=sort_key)
    created_at = _created_at_from_name(source.stem, latest) or _file_time(latest)
    age_hours = None
    if created_at is not None:
        age_hours = max(0.0, (now - created_at.astimezone(timezone.utc)).total_seconds() / 3600.0)
    sidecar_count, temporary_count = _backup_debris_counts(backup_dir, source.stem)
    return BackupStatus(
        backup_dir=backup_dir,
        source_stem=source.stem,
        path=latest,
        created_at=created_at,
        age_hours=age_hours,
        size_bytes=latest.stat().st_size,
        count=len(backups),
        sidecar_count=sidecar_count,
        temporary_count=temporary_count,
        stale_after_hours=stale_after_hours,
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


def format_restore_result(result: RestoreCheckResult) -> str:
    size_mb = result.size_bytes / (1024 * 1024)
    counts = ", ".join(f"{name}={count}" for name, count in result.table_counts.items())
    lines = [
        "SQLite restore drill complete",
        f"path: {result.backup_path}",
        f"size: {size_mb:.2f} MB",
        f"integrity_check: {result.quick_check}",
    ]
    if counts:
        lines.append(f"tables: {counts}")
    return "\n".join(lines)
