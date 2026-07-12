"""Duplicate-key-safe JSON decoding for research artifact JSONL files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


class _DuplicateJsonObjectKey(ValueError):
    """Raised without echoing a potentially sensitive duplicate key or value."""


@dataclass(frozen=True)
class _JsonlReadDiagnostics:
    total_lines: int = 0
    accepted_rows: int = 0
    blank_lines: tuple[int, ...] = ()
    invalid_json_lines: tuple[int, ...] = ()
    duplicate_key_lines: tuple[int, ...] = ()
    non_object_lines: tuple[int, ...] = ()
    read_error: bool = False

    @property
    def rejected_line_count(self) -> int:
        return (
            len(self.invalid_json_lines)
            + len(self.duplicate_key_lines)
            + len(self.non_object_lines)
        )


@dataclass(frozen=True)
class _JsonlReadResult:
    rows: tuple[dict[str, Any], ...]
    diagnostics: _JsonlReadDiagnostics


def loads_no_duplicate_keys(text: str) -> Any:
    """Decode JSON while rejecting duplicate keys at every object depth."""

    return json.loads(text, object_pairs_hook=_object_without_duplicate_keys)


def read_jsonl(path: str | Path | None) -> _JsonlReadResult:
    """Read mapping rows fail-soft while retaining payload-free diagnostics."""

    if path is None:
        return _result(())
    source = Path(path).expanduser()
    if not source.exists():
        return _result(())
    rows: list[dict[str, Any]] = []
    blank: list[int] = []
    invalid: list[int] = []
    duplicate: list[int] = []
    non_object: list[int] = []
    total_lines = 0
    read_error = False
    try:
        with source.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                total_lines = line_number
                if not line.strip():
                    blank.append(line_number)
                    continue
                try:
                    value = loads_no_duplicate_keys(line)
                except _DuplicateJsonObjectKey:
                    duplicate.append(line_number)
                    continue
                except json.JSONDecodeError:
                    invalid.append(line_number)
                    continue
                if not isinstance(value, Mapping):
                    non_object.append(line_number)
                    continue
                rows.append(dict(value))
    except (OSError, UnicodeError):
        read_error = True
        rows.clear()
    diagnostics = _JsonlReadDiagnostics(
        total_lines=total_lines,
        accepted_rows=len(rows),
        blank_lines=tuple(blank),
        invalid_json_lines=tuple(invalid),
        duplicate_key_lines=tuple(duplicate),
        non_object_lines=tuple(non_object),
        read_error=read_error,
    )
    return _JsonlReadResult(rows=tuple(rows), diagnostics=diagnostics)


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise _DuplicateJsonObjectKey
        value[key] = item
    return value


def _result(rows: tuple[dict[str, Any], ...]) -> _JsonlReadResult:
    return _JsonlReadResult(
        rows=rows,
        diagnostics=_JsonlReadDiagnostics(accepted_rows=len(rows)),
    )


__all__ = (
    "loads_no_duplicate_keys",
    "read_jsonl",
)
