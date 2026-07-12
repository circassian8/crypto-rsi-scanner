"""Small artifact I/O helpers shared by Event Alpha outcome reports."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..artifacts import json_lines as artifact_json_lines
from ..artifacts import paths as event_artifact_paths
from ..artifacts import schema_v1


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return list(artifact_json_lines.read_jsonl(path).rows)


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            stamped = schema_v1.stamp_artifact_row(row, path=path)
            handle.write(
                json.dumps(json_ready(stamped), sort_keys=True, separators=(",", ":"))
                + "\n"
            )


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stamped = schema_v1.stamp_artifact_payload(payload, path=path)
    path.write_text(json.dumps(json_ready(stamped), sort_keys=True), encoding="utf-8")


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
