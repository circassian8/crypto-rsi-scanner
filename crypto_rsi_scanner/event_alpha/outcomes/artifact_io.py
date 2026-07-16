"""Small artifact I/O helpers shared by Event Alpha outcome reports."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..artifacts import json_lines as artifact_json_lines
from ..artifacts import paths as event_artifact_paths
from ..artifacts import schema_v1
from ..operations import market_no_send_io
from ..radar import source_independence_store as event_source_independence_store


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        dict(event_source_independence_store.hydrate(path.parent, row))
        for row in artifact_json_lines.read_jsonl(path).rows
    ]


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_rows = market_no_send_io.read_jsonl(path)
    preserve_inline_digests = event_source_independence_store.inline_contract_digests(
        existing_rows
    )
    payload = _jsonl_bytes(
        path,
        rows,
        preserve_inline_digests=preserve_inline_digests,
    )
    market_no_send_io.write_bytes_atomic(path, payload)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stamped = schema_v1.stamp_artifact_payload(payload, path=path)
    data = json.dumps(json_ready(stamped), sort_keys=True).encode("utf-8")
    market_no_send_io.write_bytes_atomic(path, data)


def _jsonl_bytes(
    path: Path,
    rows: Iterable[Mapping[str, Any]],
    *,
    preserve_inline_digests: frozenset[str],
) -> bytes:
    lines: list[str] = []
    for row in rows:
        stamped = schema_v1.stamp_artifact_row(row, path=path)
        persisted = event_source_independence_store.externalize(
            path.parent,
            json_ready(stamped),
            preserve_inline_digests=preserve_inline_digests,
        )
        lines.append(json.dumps(persisted, sort_keys=True, separators=(",", ":")))
    return (("\n".join(lines) + "\n") if lines else "").encode("utf-8")


def json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_ready(item) for item in value]
    if isinstance(value, Path):
        return event_artifact_paths.artifact_display_path(value)
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return value


__all__ = ("json_ready", "read_jsonl", "write_json", "write_jsonl")
