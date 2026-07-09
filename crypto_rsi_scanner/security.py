"""Small local privacy helpers for runtime files.

The scanner stores credentials in ``.env`` and may persist recipient identifiers
or provider error text in logs and SQLite artifacts.  Runtime files therefore use
owner-only permissions even when the caller's default umask is permissive.
"""

from __future__ import annotations

import os
from pathlib import Path


PRIVATE_FILE_MODE = 0o600
PRIVATE_DIR_MODE = 0o700


def ensure_private_file(path: str | Path, *, create: bool = False) -> Path:
    """Create, when requested, and enforce owner-only access on ``path``."""

    target = Path(path).expanduser()
    if create and not target.exists():
        fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, PRIVATE_FILE_MODE)
        os.close(fd)
    if target.exists():
        target.chmod(PRIVATE_FILE_MODE)
    return target


def ensure_private_directory(path: str | Path, *, create: bool = False) -> Path:
    """Create, when requested, and enforce owner-only access on ``path``."""

    target = Path(path).expanduser()
    if create:
        target.mkdir(parents=True, exist_ok=True, mode=PRIVATE_DIR_MODE)
    if target.exists():
        target.chmod(PRIVATE_DIR_MODE)
    return target
