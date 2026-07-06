"""Shared helpers for Event Alpha burn-in operating reports."""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..artifacts import context as artifact_context


SECRET_RE = re.compile(
    r"(api[_-]?key\b|auth[_-]?token\b|bearer\s+[a-z0-9._-]{12,}|sk-[a-z0-9_-]{12,}|"
    r"x-api-key\b|telegram[_-]?bot[_-]?token\b|provider[_-]?token\b)",
    re.IGNORECASE,
)
SAFETY_FIELDS: dict[str, Any] = {
    "research_only": True,
    "no_send_rehearsal": True,
    "strict_alerts_created": 0,
    "telegram_sends": 0,
    "trades_created": 0,
    "paper_trades_created": 0,
    "normal_rsi_signal_rows_written": 0,
    "triggered_fade_created": 0,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_utc(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def date_window(days: int, *, now: datetime | None = None) -> datetime:
    return (now or utc_now()).astimezone(timezone.utc) - timedelta(days=max(1, int(days or 1)))


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[3]


def context_for(
    *,
    profile: str | None,
    artifact_namespace: str | None,
    base_dir: str | Path | None = None,
) -> artifact_context.EventAlphaArtifactContext:
    return artifact_context.context_from_profile(
        profile or "live_burn_in_no_send",
        run_mode="burn_in",
        base_dir=base_dir,
        artifact_namespace=artifact_namespace,
    )


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path).expanduser()
    if not p.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                loaded = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(loaded, Mapping):
                rows.append(dict(loaded))
    except OSError:
        return []
    return rows


def read_json(path: str | Path) -> dict[str, Any]:
    p = Path(path).expanduser()
    if not p.exists():
        return {}
    try:
        loaded = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(loaded) if isinstance(loaded, Mapping) else {}


def write_json(path: str | Path, payload: Mapping[str, Any]) -> Path:
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(json_ready(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return p


def write_text(path: str | Path, text: str) -> Path:
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.rstrip() + "\n", encoding="utf-8")
    return p


def append_jsonl(path: str | Path, row: Mapping[str, Any]) -> Path:
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(json_ready(row), sort_keys=True) + "\n")
    return p


def json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_ready(item) for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return value


def rel_path(path: str | Path, *, root: str | Path | None = None) -> str:
    p = Path(path).expanduser()
    base = Path(root).expanduser() if root is not None else repo_root_from_module()
    try:
        return p.resolve().relative_to(base.resolve()).as_posix()
    except (OSError, ValueError):
        return p.as_posix()


def count_by(rows: Iterable[Mapping[str, Any]], *fields: str) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        key = next((str(row.get(field) or "").strip() for field in fields if str(row.get(field) or "").strip()), "unknown")
        counts[key] += 1
    return dict(sorted(counts.items()))


def int_value(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def float_value(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def item_family(row: Mapping[str, Any]) -> str:
    return str(
        row.get("canonical_asset_id")
        or row.get("core_opportunity_id")
        or row.get("coin_id")
        or row.get("asset_coin_id")
        or row.get("symbol")
        or row.get("asset_symbol")
        or row.get("feedback_target")
        or row.get("alert_key")
        or row.get("id")
        or "unknown"
    )


def row_score(row: Mapping[str, Any]) -> int:
    for field in ("opportunity_score", "score", "latest_score", "priority"):
        if field in row:
            return int_value(row.get(field))
    return 0


def row_lane(row: Mapping[str, Any]) -> str:
    return str(row.get("opportunity_type") or row.get("lane") or row.get("tier") or "unknown")


def timestamp_for_row(row: Mapping[str, Any]) -> datetime | None:
    for field in ("observed_at", "created_at", "started_at", "marked_at", "published_at", "generated_at"):
        parsed = parse_utc(row.get(field))
        if parsed is not None:
            return parsed
    return None


def table_line(label: str, counts: Mapping[str, int]) -> str:
    if not counts:
        return f"- {label}: none"
    return f"- {label}: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def secret_hits_in_text(text: str) -> list[str]:
    hits: list[str] = []
    for match in SECRET_RE.finditer(text or ""):
        token = match.group(0)
        if _natural_language_sk_phrase(token):
            continue
        if token and token not in hits:
            hits.append(token[:80])
    return hits


def _natural_language_sk_phrase(token: str) -> bool:
    if not token.lower().startswith("sk-"):
        return False
    rest = token[3:]
    slug_part = rest.split("_", 1)[0]
    if "_" in rest and slug_part.count("-") >= 3 and slug_part == slug_part.lower() and all(char.isalnum() or char == "-" for char in slug_part):
        return True
    if not rest or rest != rest.lower() or "_" in rest or not any(char == "-" for char in rest):
        return False
    if not any(char.isdigit() for char in rest):
        return True
    return rest.count("-") >= 3 and all(char.isalnum() or char == "-" for char in rest)


def load_contract(root: str | Path | None = None) -> dict[str, Any]:
    base = Path(root).expanduser() if root is not None else repo_root_from_module()
    contract = read_json(base / "research" / "event_alpha_burn_in_contract.json")
    if contract:
        return contract
    north_star = read_json(base / "research" / "EVENT_ALPHA_RADAR_NORTH_STAR.json")
    embedded = north_star.get("burn_in_contract")
    return dict(embedded) if isinstance(embedded, Mapping) else {}


def contract_threshold(contract: Mapping[str, Any], key: str) -> int:
    return int_value(contract.get(key))


def with_safety(payload: dict[str, Any]) -> dict[str, Any]:
    return {**SAFETY_FIELDS, **payload}
