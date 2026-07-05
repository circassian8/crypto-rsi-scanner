"""Utilities helpers for integrated radar."""

from __future__ import annotations

from .runtime import *

def _merged_list(rows: list[Mapping[str, Any]], key: str) -> tuple[str, ...]:
    values: list[str] = []
    for row in rows:
        raw = row.get(key)
        if isinstance(raw, (list, tuple, set)):
            values.extend(str(item) for item in raw if str(item))
        elif raw not in (None, ""):
            values.append(str(raw))
    return tuple(dict.fromkeys(values))

def _format_counts(values: Mapping[str, int] | Counter[Any]) -> str:
    items = [(str(key), int(value)) for key, value in dict(values).items() if int(value)]
    if not items:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(items))

def _list_label(values: Any, *, limit: int = 3) -> str:
    if values in (None, "", [], (), {}):
        return "none"
    if isinstance(values, str):
        return values
    if isinstance(values, Mapping):
        return ", ".join(f"{key}={value}" for key, value in list(values.items())[:limit]) or "none"
    if isinstance(values, Iterable):
        items = [str(item) for item in values if str(item)]
        if not items:
            return "none"
        suffix = f"; +{len(items) - limit} more" if len(items) > limit else ""
        return "; ".join(items[:limit]) + suffix
    return str(values)

def _artifact_has_absolute_operator_path(path: str | Path) -> bool:
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return event_artifact_paths.has_operator_absolute_path(text)

def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return value

def _parse_time(value: datetime | str | None) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None

def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

def _text(value: Any) -> str:
    return str(value or "").strip()

def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0

def _rate_text(value: Any) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "n/a"

def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]

__all__ = (
    '_merged_list',
    '_format_counts',
    '_list_label',
    '_artifact_has_absolute_operator_path',
    '_json_ready',
    '_parse_time',
    '_as_utc',
    '_text',
    '_int',
    '_rate_text',
    '_digest',
)
