#!/usr/bin/env python3
"""Write the fixed Pro-review source archive with local research artifacts.

The archive intentionally overwrites the same filename every run:
``crypto_rsi_scanner_source_with_artifacts.zip``.
"""

from __future__ import annotations

import subprocess
import time
import zipfile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "crypto_rsi_scanner_source_with_artifacts.zip"

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    ".pytest_cache",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
    "node_modules",
    "backups",
}
EXCLUDE_FILE_NAMES = {
    ".env",
    ".DS_Store",
    ".claude/settings.local.json",
}
EXCLUDE_SUFFIXES = (
    ".pyc",
    ".pyo",
    ".db",
    ".db-wal",
    ".db-shm",
    ".sqlite",
    ".sqlite3",
    ".log",
    ".tmp",
    ".swp",
    ".zip",
)
ARTIFACT_ROOTS = {"event_fade_cache"}


def _tracked_paths() -> set[Path]:
    output = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", "HEAD"],
        cwd=ROOT,
        text=True,
    )
    return {ROOT / line for line in output.splitlines() if line.strip()}


def _artifact_paths() -> set[Path]:
    paths: set[Path] = set()
    for name in ARTIFACT_ROOTS:
        root = ROOT / name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file():
                paths.add(path)
    return paths


def _skip(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    parts = rel.parts
    if any(part in EXCLUDE_DIRS for part in parts):
        return True
    rel_text = rel.as_posix()
    if rel_text in EXCLUDE_FILE_NAMES or path.name in EXCLUDE_FILE_NAMES:
        return True
    if path.name.startswith(".env"):
        return True
    if path.suffix in EXCLUDE_SUFFIXES or any(path.name.endswith(suffix) for suffix in EXCLUDE_SUFFIXES):
        return True
    return False


def _validate(names: list[str]) -> list[str]:
    bad: list[str] = []
    for name in names:
        lower = name.lower()
        if (
            lower == ".env"
            or lower.endswith("/.env")
            or "/.env" in lower
            or lower.startswith(".git/")
            or "/.git/" in lower
            or lower.startswith(".venv/")
            or "/.venv/" in lower
            or "__pycache__/" in lower
            or ".pytest_cache/" in lower
            or lower.endswith((".db", ".db-wal", ".db-shm", ".sqlite", ".sqlite3", ".log", ".zip", ".pyc"))
        ):
            bad.append(name)
    return bad


def _zipinfo_for_path(path: Path, arcname: str, *, now_ts: float) -> zipfile.ZipInfo:
    """Create a zip entry while clamping future mtimes to export time."""

    stat = path.stat()
    # Zip timestamps cannot represent dates before 1980. More importantly for
    # review zips, do not preserve future-dated mtimes from host/archive clock
    # skew because extracted Makefiles can make every `make` command warn.
    mtime = min(max(stat.st_mtime, 315532800.0), now_ts)
    info = zipfile.ZipInfo(arcname, datetime.fromtimestamp(mtime).timetuple()[:6])
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = (stat.st_mode & 0xFFFF) << 16
    return info


def _write_file_to_zip(zf: zipfile.ZipFile, path: Path, arcname: str, *, now_ts: float) -> None:
    info = _zipinfo_for_path(path, arcname, now_ts=now_ts)
    with path.open("rb") as src, zf.open(info, "w") as dst:
        dst.write(src.read())


def main() -> int:
    paths = _tracked_paths() | _artifact_paths()
    entries = [
        path
        for path in sorted(paths, key=lambda item: item.relative_to(ROOT).as_posix())
        if path.exists() and path.is_file() and not _skip(path)
    ]

    if OUT.exists():
        OUT.unlink()
    now_ts = time.time()
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in entries:
            _write_file_to_zip(zf, path, path.relative_to(ROOT).as_posix(), now_ts=now_ts)

    with zipfile.ZipFile(OUT) as zf:
        names = zf.namelist()
    bad = _validate(names)
    artifact_entries = [name for name in names if name.startswith("event_fade_cache/")]
    research_cards = [
        name
        for name in artifact_entries
        if "/research_cards/" in name and name.endswith(".md") and not name.endswith("/index.md")
    ]

    print(OUT)
    print(f"size_bytes={OUT.stat().st_size}")
    print(f"entries={len(names)}")
    print(f"artifact_entries={len(artifact_entries)}")
    print(f"research_card_files={len(research_cards)}")
    print(f"bad_entries={len(bad)}")
    if bad:
        print("\n".join(bad[:50]))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
