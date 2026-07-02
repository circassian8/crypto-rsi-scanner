"""Portable artifact path helpers for Event Alpha operator surfaces."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Iterable


_ABS_PATH_RE = re.compile(
    r"(/Users/[^\s)>\]\"']+|/private/tmp/[^\s)>\]\"']+|/tmp/[^\s)>\]\"']+|/mnt/data/[^\s)>\]\"']+)"
)


def repo_root() -> Path:
    """Return the repository root for this installed package checkout."""
    return Path(__file__).resolve().parents[3]


def artifact_relpath(
    path: str | Path | None,
    *,
    base: str | Path | None = None,
    repo_root: str | Path | None = None,
    artifact_base: str | Path | None = None,
) -> str:
    """Return a stable POSIX relative path for an artifact."""
    if path in (None, ""):
        return ""
    raw = Path(str(path)).expanduser()
    root_value = repo_root if repo_root is not None else None
    roots = [
        Path(base).expanduser() if base is not None else None,
        Path(root_value).expanduser() if root_value is not None else globals()["repo_root"](),
        Path(artifact_base).expanduser() if artifact_base is not None else None,
        Path.cwd(),
    ]
    if raw.is_absolute():
        for root in roots:
            if root is None:
                continue
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


def artifact_display_path(
    path: str | Path | None,
    *,
    base: str | Path | None = None,
    repo_root: str | Path | None = None,
    artifact_base: str | Path | None = None,
) -> str:
    """Return a human/operator safe artifact path label."""
    rel = artifact_relpath(path, base=base, repo_root=repo_root, artifact_base=artifact_base)
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


def normalize_operator_path_fields(
    row: Mapping[str, Any],
    *,
    rel_field_names: Iterable[str] | None = None,
    debug_abs_suffix: str = "_abs_debug",
    repo_root: str | Path | None = None,
    artifact_base: str | Path | None = None,
) -> dict[str, Any]:
    """Return a copy with operator path fields made portable.

    Fields whose names end with ``debug_abs_suffix`` are left untouched. For
    other path-like fields, absolute paths are converted to repo/artifact
    relative labels and the original absolute value is preserved beside it as a
    ``*_abs_debug`` field. Nested mappings and lists are normalized recursively,
    so structured JSONL artifacts cannot leak machine-local paths in child
    fields such as ``canonical_card_paths`` or ``research_card_paths``.
    """
    rel_names = set(rel_field_names or ())
    normalized, _debug_value = _normalize_operator_value(
        dict(row),
        key_name="",
        rel_names=rel_names,
        debug_abs_suffix=debug_abs_suffix,
        repo_root=repo_root,
        artifact_base=artifact_base,
    )
    return dict(normalized) if isinstance(normalized, Mapping) else dict(row)


def _is_operator_path_field(key: str, *, rel_names: set[str]) -> bool:
    clean = key.casefold()
    if clean in rel_names:
        return True
    if clean.endswith("_relpath") or clean.endswith("_relpaths"):
        return False
    return (
        clean.endswith("_path")
        or clean.endswith("_paths")
        or clean.endswith("_dir")
        or clean.endswith("_dirs")
        or "card_path" in clean
    )


def _normalize_operator_value(
    value: Any,
    *,
    key_name: str,
    rel_names: set[str],
    debug_abs_suffix: str,
    repo_root: str | Path | None,
    artifact_base: str | Path | None,
) -> tuple[Any, Any]:
    if key_name.endswith(debug_abs_suffix):
        return value, None
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        debug_values: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            normalized, debug_value = _normalize_operator_value(
                item,
                key_name=key_text,
                rel_names=rel_names,
                debug_abs_suffix=debug_abs_suffix,
                repo_root=repo_root,
                artifact_base=artifact_base,
            )
            out[key_text] = normalized
            if debug_value not in (None, "", [], ()):
                debug_values.setdefault(f"{key_text}{debug_abs_suffix}", debug_value)
        for key, debug_value in debug_values.items():
            out.setdefault(key, debug_value)
        return out, None
    if isinstance(value, (list, tuple, set)):
        normalized_items = []
        debug_items = []
        for item in value:
            normalized, debug = _normalize_operator_value(
                item,
                key_name=key_name,
                rel_names=rel_names,
                debug_abs_suffix=debug_abs_suffix,
                repo_root=repo_root,
                artifact_base=artifact_base,
            )
            normalized_items.append(normalized)
            if debug not in (None, "", [], ()):
                debug_items.append(debug)
        normalized_seq: Any = tuple(normalized_items) if isinstance(value, tuple) else list(normalized_items)
        return normalized_seq, debug_items
    if _is_operator_path_field(key_name, rel_names=rel_names):
        return _normalize_path_value(value, repo_root=repo_root, artifact_base=artifact_base)
    return value, None


def _normalize_path_value(
    value: Any,
    *,
    repo_root: str | Path | None,
    artifact_base: str | Path | None,
) -> tuple[Any, Any]:
    if value in (None, ""):
        return value, None
    if isinstance(value, (list, tuple, set)):
        normalized_items = []
        debug_items = []
        for item in value:
            normalized, debug = _normalize_path_value(
                item,
                repo_root=repo_root,
                artifact_base=artifact_base,
            )
            normalized_items.append(normalized)
            if debug not in (None, ""):
                debug_items.append(debug)
        return tuple(normalized_items) if isinstance(value, tuple) else list(normalized_items), debug_items
    text = str(value)
    if has_operator_absolute_path(text) or Path(text).expanduser().is_absolute():
        return artifact_display_path(text, repo_root=repo_root, artifact_base=artifact_base), text
    return text, None
