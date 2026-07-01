#!/usr/bin/env python3
"""Clamp future file mtimes before creating portable review archives."""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path


EXCLUDED_DIRS = {
    ".git",
    ".venv",
    ".pytest_cache",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
}


def normalize_path_timestamps(root: str | Path, *, now_ts: float | None = None) -> int:
    """Clamp future mtimes under ``root`` to ``now_ts``; return changed count."""

    base = Path(root).expanduser()
    if not base.exists():
        return 0
    now = float(time.time() if now_ts is None else now_ts)
    changed = 0
    paths = [base] if base.is_file() else list(base.rglob("*"))
    for path in paths:
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if not path.is_file():
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        if stat.st_mtime <= now:
            continue
        try:
            os.utime(path, (min(stat.st_atime, now), now))
        except OSError:
            continue
        changed += 1
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Clamp future file mtimes for review exports.")
    parser.add_argument("root", nargs="?", default=".", help="Root path to normalize.")
    args = parser.parse_args()
    changed = normalize_path_timestamps(args.root)
    print(f"normalized_future_mtimes={changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
