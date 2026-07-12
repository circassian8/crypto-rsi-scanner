"""Deterministic artifact fingerprints shared by operator readers and writers.

The contract deliberately fingerprints exact file bytes.  Directory trees use
an unambiguous framed stream of sorted POSIX relative paths and exact file
bytes; symlinks and non-regular files are rejected rather than followed.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


FINGERPRINT_CONTRACT_VERSION = 1
FINGERPRINT_FIELDS = (
    "sha256",
    "size_bytes",
    "item_count",
    "fingerprint_kind",
    "fingerprint_contract_version",
)
FILE_BYTES_KIND = "file_bytes"
JSONL_LINES_KIND = "jsonl_lines"
DIRECTORY_TREE_KIND = "directory_tree_v1"
CANONICAL_RUN_ROW_KIND = "canonical_run_row"
PATH_FINGERPRINT_KINDS = {FILE_BYTES_KIND, JSONL_LINES_KIND, DIRECTORY_TREE_KIND}
ALL_FINGERPRINT_KINDS = {*PATH_FINGERPRINT_KINDS, CANONICAL_RUN_ROW_KIND}


class FingerprintError(ValueError):
    """Raised when a path cannot be fingerprinted without ambiguity."""


class _DuplicateJsonObjectKey(ValueError):
    """Raised internally when a ledger row has ambiguous JSON object keys."""


def fingerprint_path(path: str | Path, *, kind: str | None = None) -> dict[str, Any]:
    """Return the v1 fingerprint for one regular file or directory tree."""

    target = Path(path)
    try:
        info = target.lstat()
    except FileNotFoundError as exc:
        raise FingerprintError("path_missing") from exc
    except OSError as exc:
        raise FingerprintError(f"path_stat_failed:{type(exc).__name__}") from exc
    if stat.S_ISLNK(info.st_mode):
        raise FingerprintError("symlink_not_allowed")
    selected = str(kind or "").strip()
    if stat.S_ISDIR(info.st_mode):
        if selected and selected != DIRECTORY_TREE_KIND:
            raise FingerprintError("fingerprint_kind_path_type_mismatch")
        return _fingerprint_directory(target)
    if not stat.S_ISREG(info.st_mode):
        raise FingerprintError("non_regular_path_not_allowed")
    inferred = JSONL_LINES_KIND if target.suffix.casefold() == ".jsonl" else FILE_BYTES_KIND
    if selected and selected not in {FILE_BYTES_KIND, JSONL_LINES_KIND}:
        raise FingerprintError("fingerprint_kind_path_type_mismatch")
    data = _read_regular_file_once(target)
    return fingerprint_bytes(data, kind=selected or inferred)


def read_regular_file_bytes(path: str | Path) -> bytes:
    """Read exact bytes from one unchanged regular file without following symlinks."""

    return _read_regular_file_once(Path(path))


def fingerprint_bytes(data: bytes, *, kind: str = FILE_BYTES_KIND) -> dict[str, Any]:
    """Fingerprint one already-read immutable byte buffer."""

    selected = str(kind or "").strip()
    if selected not in {FILE_BYTES_KIND, JSONL_LINES_KIND}:
        raise FingerprintError("unsupported_bytes_fingerprint_kind")
    raw = bytes(data)
    item_count = _jsonl_nonblank_line_count(raw) if selected == JSONL_LINES_KIND else 1
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
        "item_count": item_count,
        "fingerprint_kind": selected,
        "fingerprint_contract_version": FINGERPRINT_CONTRACT_VERSION,
    }


def verify_bytes_fingerprint(
    data: bytes,
    expected_mapping: Mapping[str, Any],
) -> tuple[bool, str | None]:
    """Verify already-read bytes so callers can parse the same checked buffer."""

    metadata_error = fingerprint_metadata_error(
        expected_mapping,
        allowed_kinds={FILE_BYTES_KIND, JSONL_LINES_KIND},
    )
    if metadata_error:
        return False, metadata_error
    try:
        actual = fingerprint_bytes(
            data,
            kind=str(expected_mapping.get("fingerprint_kind") or ""),
        )
    except FingerprintError as exc:
        return False, str(exc)
    return _compare_fingerprints(actual, expected_mapping)


def verify_path_fingerprint(
    path: str | Path,
    expected_mapping: Mapping[str, Any],
) -> tuple[bool, str | None]:
    """Verify a path without exposing it in returned diagnostics."""

    metadata_error = fingerprint_metadata_error(
        expected_mapping,
        allowed_kinds=PATH_FINGERPRINT_KINDS,
    )
    if metadata_error:
        return False, metadata_error
    try:
        actual = fingerprint_path(
            path,
            kind=str(expected_mapping.get("fingerprint_kind") or ""),
        )
    except FingerprintError as exc:
        return False, str(exc)
    return _compare_fingerprints(actual, expected_mapping)


def canonical_run_row_fingerprint(row: Mapping[str, Any]) -> dict[str, Any]:
    """Fingerprint the canonical JSON representation of one persisted run row."""

    payload = canonical_json_bytes(row)
    return {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size_bytes": len(payload),
        "item_count": 1,
        "fingerprint_kind": CANONICAL_RUN_ROW_KIND,
        "fingerprint_contract_version": FINGERPRINT_CONTRACT_VERSION,
    }


def fingerprint_run_ledger_row(
    path: str | Path,
    identity: Mapping[str, Any],
) -> dict[str, Any]:
    """Fingerprint the one exact identity row in a cumulative run ledger."""

    normalized_identity = _run_identity(identity)
    if not all(normalized_identity.values()):
        raise FingerprintError("run_row_identity_incomplete")
    matches = load_matching_run_rows(path, normalized_identity)
    if len(matches) != 1:
        raise FingerprintError(f"run_row_match_count_mismatch:{len(matches)}")
    return {
        **canonical_run_row_fingerprint(matches[0]),
        "run_row_identity": normalized_identity,
        "run_row_match_count": 1,
    }


def canonical_json_bytes(value: Any) -> bytes:
    """Return deterministic UTF-8 JSON bytes for supported artifact values."""

    normalized = _canonical_value(value)
    try:
        text = json.dumps(
            normalized,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return text.encode("utf-8")
    except (TypeError, UnicodeEncodeError, ValueError) as exc:
        raise FingerprintError(f"canonical_json_failed:{type(exc).__name__}") from exc


def load_matching_run_rows(
    path: str | Path,
    identity: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    """Read exact-identity JSONL run rows from one cumulative ledger."""

    target = Path(path)
    raw = _read_regular_file_once(target)
    expected = _run_identity(identity)
    if not all(expected.values()):
        raise FingerprintError("run_row_identity_incomplete")
    matches: list[dict[str, Any]] = []
    for line_number, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        try:
            parsed = json.loads(line, object_pairs_hook=_json_object_without_duplicate_keys)
        except _DuplicateJsonObjectKey as exc:
            raise FingerprintError(f"run_ledger_duplicate_object_key:{line_number}") from exc
        except json.JSONDecodeError as exc:
            raise FingerprintError(f"run_ledger_invalid_jsonl:{line_number}") from exc
        if not isinstance(parsed, Mapping):
            raise FingerprintError(f"run_ledger_row_not_object:{line_number}")
        row = dict(parsed)
        if _run_identity(row) == expected:
            matches.append(row)
    return tuple(matches)


def verify_run_ledger_row_fingerprint(
    path: str | Path,
    expected_mapping: Mapping[str, Any],
) -> tuple[bool, str | None]:
    """Verify one exact canonical run row inside an append-only ledger."""

    metadata_error = fingerprint_metadata_error(
        expected_mapping,
        allowed_kinds={CANONICAL_RUN_ROW_KIND},
    )
    if metadata_error:
        return False, metadata_error
    identity = expected_mapping.get("run_row_identity")
    if not isinstance(identity, Mapping) or not all(_run_identity(identity).values()):
        return False, "run_row_identity_incomplete"
    match_count = expected_mapping.get("run_row_match_count")
    if isinstance(match_count, bool) or match_count != 1:
        return False, "run_row_match_count_invalid"
    try:
        matches = load_matching_run_rows(path, identity)
    except FingerprintError as exc:
        return False, str(exc)
    if len(matches) != 1:
        return False, f"run_row_match_count_mismatch:{len(matches)}"
    try:
        actual = canonical_run_row_fingerprint(matches[0])
    except FingerprintError as exc:
        return False, str(exc)
    return _compare_fingerprints(actual, expected_mapping)


def fingerprint_metadata_error(
    value: Mapping[str, Any],
    *,
    allowed_kinds: set[str] | frozenset[str] | None = None,
) -> str | None:
    """Return a stable diagnostic for malformed v1 fingerprint metadata."""

    if "run_row_sha256" in value:
        return "fingerprint_run_row_sha256_deprecated"
    missing = [field for field in FINGERPRINT_FIELDS if field not in value]
    if missing:
        return f"fingerprint_metadata_missing:{missing[0]}"
    digest = value.get("sha256")
    if not isinstance(digest, str) or len(digest) != 64 or any(
        char not in "0123456789abcdef" for char in digest
    ):
        return "fingerprint_sha256_invalid"
    for field in ("size_bytes", "item_count"):
        field_value = value.get(field)
        if isinstance(field_value, bool) or not isinstance(field_value, int) or field_value < 0:
            return f"fingerprint_{field}_invalid"
    version = value.get("fingerprint_contract_version")
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version != FINGERPRINT_CONTRACT_VERSION
    ):
        return "fingerprint_contract_version_unsupported"
    kind = value.get("fingerprint_kind")
    supported = set(allowed_kinds or ALL_FINGERPRINT_KINDS)
    if not isinstance(kind, str) or kind not in supported:
        return "fingerprint_kind_invalid"
    if kind != CANONICAL_RUN_ROW_KIND and any(
        field in value for field in ("run_row_identity", "run_row_match_count")
    ):
        return "fingerprint_run_row_fields_invalid_for_kind"
    return None


def has_any_fingerprint_metadata(value: Mapping[str, Any]) -> bool:
    """Return whether an entry attempts to use the fingerprint contract."""

    return any(field in value for field in FINGERPRINT_FIELDS) or any(
        field in value
        for field in ("run_row_identity", "run_row_match_count", "run_row_sha256")
    )


def verify_operator_entry_fingerprint(
    name: str,
    path: str | Path | None,
    entry: Mapping[str, Any],
    *,
    expected_run_identity: Mapping[str, Any],
    require_complete: bool,
) -> tuple[bool, str | None]:
    """Validate one current operator entry, preserving legacy read-only rows."""

    contract_present = "fingerprint_contract_version" in entry
    legacy_sha_only = _valid_legacy_sha_only(entry)
    has_metadata = has_any_fingerprint_metadata(entry)
    if not contract_present:
        if has_metadata and not legacy_sha_only:
            return False, "fingerprint_partial"
        if "sha256" in entry and not legacy_sha_only:
            return False, "legacy_sha256_invalid"
        if require_complete:
            return False, "fingerprint_missing"
        return True, None
    if path is None:
        return False, "fingerprint_path_unavailable"
    if str(name) == "run_ledger":
        identity = entry.get("run_row_identity")
        if not isinstance(identity, Mapping) or _run_identity(identity) != _run_identity(
            expected_run_identity
        ):
            return False, "run_ledger_fingerprint_identity_mismatch"
        return verify_run_ledger_row_fingerprint(path, entry)
    return verify_path_fingerprint(path, entry)


def _fingerprint_directory(root: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    digest.update(b"event-alpha-directory-tree-v1\0")
    total_size = 0
    file_count = 0
    before = _directory_snapshot(root)
    for relative, child, kind, _identity in before:
        if kind == "directory":
            continue
        data = _read_regular_file_once(child)
        path_bytes = relative.encode("utf-8")
        digest.update(len(path_bytes).to_bytes(8, "big"))
        digest.update(path_bytes)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
        total_size += len(data)
        file_count += 1
    after = _directory_snapshot(root)
    if tuple((relative, kind, identity) for relative, _path, kind, identity in before) != tuple(
        (relative, kind, identity) for relative, _path, kind, identity in after
    ):
        raise FingerprintError("directory_changed_during_fingerprint")
    return {
        "sha256": digest.hexdigest(),
        "size_bytes": total_size,
        "item_count": file_count,
        "fingerprint_kind": DIRECTORY_TREE_KIND,
        "fingerprint_contract_version": FINGERPRINT_CONTRACT_VERSION,
    }


def _read_regular_file_once(path: Path) -> bytes:
    try:
        before_path = path.lstat()
    except FileNotFoundError as exc:
        raise FingerprintError("path_missing") from exc
    except OSError as exc:
        raise FingerprintError(f"path_stat_failed:{type(exc).__name__}") from exc
    if stat.S_ISLNK(before_path.st_mode):
        raise FingerprintError("symlink_not_allowed")
    if not stat.S_ISREG(before_path.st_mode):
        raise FingerprintError("non_regular_path_not_allowed")
    try:
        with path.open("rb") as handle:
            before_fd = os.fstat(handle.fileno())
            data = handle.read()
            after_fd = os.fstat(handle.fileno())
        after_path = path.lstat()
    except FileNotFoundError as exc:
        raise FingerprintError("path_changed_during_read") from exc
    except OSError as exc:
        raise FingerprintError(f"path_read_failed:{type(exc).__name__}") from exc
    before_identity = _stat_identity(before_fd)
    if (
        before_identity != _stat_identity(before_path)
        or before_identity != _stat_identity(after_fd)
        or before_identity != _stat_identity(after_path)
    ):
        raise FingerprintError("path_changed_during_read")
    if len(data) != after_fd.st_size:
        raise FingerprintError("path_size_changed_during_read")
    return data


def _compare_fingerprints(
    actual: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> tuple[bool, str | None]:
    for field in FINGERPRINT_FIELDS:
        if actual.get(field) != expected.get(field):
            return False, f"fingerprint_content_mismatch:{field}"
    return True, None


def _directory_snapshot(root: Path) -> tuple[tuple[str, Path, str, tuple[int, int, int, int]], ...]:
    try:
        children = sorted(root.rglob("*"), key=lambda path: path.relative_to(root).as_posix())
    except OSError as exc:
        raise FingerprintError(f"directory_scan_failed:{type(exc).__name__}") from exc
    rows: list[tuple[str, Path, str, tuple[int, int, int, int]]] = []
    for child in children:
        try:
            info = child.lstat()
        except OSError as exc:
            raise FingerprintError(f"directory_entry_stat_failed:{type(exc).__name__}") from exc
        if stat.S_ISLNK(info.st_mode):
            raise FingerprintError("directory_symlink_not_allowed")
        if stat.S_ISDIR(info.st_mode):
            kind = "directory"
        elif stat.S_ISREG(info.st_mode):
            kind = "file"
        else:
            raise FingerprintError("directory_non_regular_entry_not_allowed")
        rows.append((child.relative_to(root).as_posix(), child, kind, _stat_identity(info)))
    return tuple(rows)


def _jsonl_nonblank_line_count(data: bytes) -> int:
    return sum(1 for line in data.splitlines() if line.strip())


def _run_identity(value: Mapping[str, Any]) -> dict[str, str]:
    return {
        "run_id": _identity_text(value.get("run_id")),
        "profile": _identity_text(value.get("profile")),
        "artifact_namespace": _identity_text(value.get("artifact_namespace")),
    }


def _identity_text(value: Any) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        return ""
    return value


def _json_object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for key, value in pairs:
        if key in parsed:
            raise _DuplicateJsonObjectKey
        parsed[key] = value
    return parsed


def _valid_legacy_sha_only(value: Mapping[str, Any]) -> bool:
    digest = value.get("sha256")
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(char not in "0123456789abcdef" for char in digest)
    ):
        return False
    return not any(
        field in value
        for field in (
            "size_bytes",
            "item_count",
            "fingerprint_kind",
            "fingerprint_contract_version",
            "run_row_identity",
            "run_row_match_count",
            "run_row_sha256",
        )
    )


def _canonical_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_value(child)
            for key, child in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_value(child) for child in value]
    if isinstance(value, (set, frozenset)):
        normalized = [_canonical_value(child) for child in value]
        return sorted(
            normalized,
            key=lambda child: json.dumps(child, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        )
    if isinstance(value, datetime):
        parsed = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
        return parsed.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        raise FingerprintError("canonical_json_non_finite_float")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise FingerprintError(f"canonical_json_unsupported_type:{type(value).__name__}")


def _stat_identity(value: os.stat_result) -> tuple[int, int, int, int]:
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns


__all__ = (
    "ALL_FINGERPRINT_KINDS",
    "CANONICAL_RUN_ROW_KIND",
    "DIRECTORY_TREE_KIND",
    "FILE_BYTES_KIND",
    "FINGERPRINT_CONTRACT_VERSION",
    "FINGERPRINT_FIELDS",
    "FingerprintError",
    "JSONL_LINES_KIND",
    "PATH_FINGERPRINT_KINDS",
    "canonical_json_bytes",
    "canonical_run_row_fingerprint",
    "fingerprint_bytes",
    "fingerprint_metadata_error",
    "fingerprint_path",
    "fingerprint_run_ledger_row",
    "has_any_fingerprint_metadata",
    "load_matching_run_rows",
    "read_regular_file_bytes",
    "verify_bytes_fingerprint",
    "verify_path_fingerprint",
    "verify_operator_entry_fingerprint",
    "verify_run_ledger_row_fingerprint",
)
