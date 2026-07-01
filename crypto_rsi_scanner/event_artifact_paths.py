"""Portable artifact path helpers for Event Alpha operator surfaces."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any


_ABS_PATH_RE = re.compile(
    r"(/Users/[^\s)>\]\"']+|/private/tmp/[^\s)>\]\"']+|/tmp/[^\s)>\]\"']+|/mnt/data/[^\s)>\]\"']+)"
)


def repo_root() -> Path:
    """Return the repository root for this installed package checkout."""
    return Path(__file__).resolve().parent.parent


def artifact_relpath(path: str | Path | None, *, base: str | Path | None = None) -> str:
    """Return a stable POSIX relative path for an artifact."""
    if path in (None, ""):
        return ""
    raw = Path(str(path)).expanduser()
    roots = [Path(base).expanduser() if base is not None else repo_root(), Path.cwd()]
    if raw.is_absolute():
        for root in roots:
            try:
                return raw.resolve().relative_to(root.resolve()).as_posix()
            except (OSError, ValueError):
                continue
        parts = raw.parts
        if "event_fade_cache" in parts:
            idx = parts.index("event_fade_cache")
            return Path(*parts[idx:]).as_posix()
        return raw.name
    return raw.as_posix()


def artifact_display_path(path: str | Path | None, *, base: str | Path | None = None) -> str:
    """Return a human/operator safe artifact path label."""
    rel = artifact_relpath(path, base=base)
    return rel or "none"


def has_operator_absolute_path(value: Any) -> bool:
    """Return true when operator text or structured field exposes local absolute paths."""
    if value in (None, ""):
        return False
    if isinstance(value, Mapping):
        return any(has_operator_absolute_path(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(has_operator_absolute_path(item) for item in value)
    text = str(value)
    if str(repo_root()) in text:
        return True
    return bool(_ABS_PATH_RE.search(text))


def scrub_absolute_paths_from_markdown(text: str, *, base: str | Path | None = None) -> str:
    """Remove machine-local absolute path prefixes from operator Markdown."""
    if not text:
        return text
    root = Path(base).expanduser() if base is not None else repo_root()
    out = str(text).replace(str(root) + "/", "")

    def _replace(match: re.Match[str]) -> str:
        path = match.group(1)
        parts = Path(path).parts
        if "event_fade_cache" in parts:
            idx = parts.index("event_fade_cache")
            return Path(*parts[idx:]).as_posix()
        if "crypto-rsi-scanner" in parts:
            idx = parts.index("crypto-rsi-scanner")
            return Path(*parts[idx + 1:]).as_posix()
        return Path(path).name

    return _ABS_PATH_RE.sub(_replace, out)
