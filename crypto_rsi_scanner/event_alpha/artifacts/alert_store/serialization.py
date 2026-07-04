"""Split implementation for `crypto_rsi_scanner/event_alpha/artifacts/alert_store.py` (serialization)."""

from __future__ import annotations

import json
import math
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
import crypto_rsi_scanner.event_alpha.outcomes.outcome_artifacts as event_alpha_outcomes
import crypto_rsi_scanner.event_alpha.outcomes.quality_fields as event_alpha_quality_fields
import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
import crypto_rsi_scanner.event_alpha.radar.core_opportunities as event_core_opportunities
import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards
import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
import crypto_rsi_scanner.event_alpha.radar.graph as event_graph
import crypto_rsi_scanner.event_alpha.radar.playbooks as event_playbooks
from ....event_alpha.notifications import delivery as event_alpha_notification_delivery
from .models import *  # noqa: F403

def _with_artifact_context(
    row: dict[str, Any],
    *,
    run_id: str | None,
    profile: str | None,
    run_mode: str | None,
    artifact_namespace: str | None,
) -> dict[str, Any]:
    out = dict(row)
    if run_id:
        out["run_id"] = run_id
    if profile:
        out["profile"] = profile
    if run_mode:
        out["run_mode"] = run_mode
    if artifact_namespace:
        out["artifact_namespace"] = artifact_namespace
    return out
def _first_present(row: Mapping[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if row.get(key) not in (None, ""):
            return row.get(key)
    return None
def _filter_snapshot_rows(
    rows: list[dict[str, Any]],
    *,
    policy: str,
    sampled_controls_limit: int,
    route_context: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    mode = (policy or "all").strip().lower()
    if mode == "all":
        return rows
    if mode == "non_store":
        return [row for row in rows if row.get("tier") != event_alerts.EventAlertTier.STORE_ONLY.value and not _is_diagnostic_support_snapshot(row)]
    if mode == "routed":
        if not route_context:
            return rows
        return [row for row in rows if str(row.get("alert_key") or "") in route_context]
    if mode == "alertable":
        if not route_context:
            return [
                row for row in rows
                if bool(row.get("alertable_after_quality_gate", row.get("route_alertable")))
                and event_alpha_router.route_value_is_alertable(row.get("final_route_after_quality_gate") or row.get("route"))
                and not _is_diagnostic_support_snapshot(row)
            ]
        return [
            row for row in rows
            if bool(
                row.get(
                    "alertable_after_quality_gate",
                    route_context.get(str(row.get("alert_key") or ""), {}).get(
                        "alertable_after_quality_gate",
                        route_context.get(str(row.get("alert_key") or ""), {}).get("route_alertable"),
                    ),
                )
            )
            and event_alpha_router.route_value_is_alertable(row.get("final_route_after_quality_gate") or row.get("route"))
            and not _is_diagnostic_support_snapshot(row)
        ]
    if mode == "sampled_controls":
        limit = max(0, int(sampled_controls_limit))
        kept: list[dict[str, Any]] = []
        controls = 0
        for row in rows:
            if row.get("tier") != event_alerts.EventAlertTier.STORE_ONLY.value:
                kept.append(row)
            elif controls < limit:
                kept.append(row)
                controls += 1
        return kept
    return rows
def _dedupe_canonical_alertable_snapshot_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep one alertable canonical snapshot per core opportunity and route.

    Support rows are still available through the CoreOpportunity store/cards.
    Writing many alertable snapshots for one canonical core makes inbox and
    doctor output look like duplicate alerts.
    """
    records: list[tuple[int, tuple[str, str] | None, tuple[float, float, str], dict[str, Any]]] = []
    best: dict[tuple[str, str], tuple[float, float, str, int]] = {}
    for idx, row in enumerate(rows):
        key = _canonical_alertable_snapshot_key(row)
        rank = _canonical_alertable_snapshot_rank(row)
        records.append((idx, key, rank, row))
        if key is None:
            continue
        current = best.get(key)
        candidate = (*rank, -idx)
        if current is None or candidate > current:
            best[key] = candidate
    kept: list[dict[str, Any]] = []
    for idx, key, _rank, row in records:
        if key is not None and best.get(key, (None, None, None, None))[3] != -idx:
            continue
        kept.append(row)
    return kept
def _canonical_alertable_snapshot_key(row: Mapping[str, Any]) -> tuple[str, str] | None:
    if _is_diagnostic_support_snapshot(row):
        return None
    core_id = str(row.get("core_opportunity_id") or "").strip()
    route = str(row.get("final_route_after_quality_gate") or row.get("route") or "").strip()
    if not core_id or not event_alpha_router.route_value_is_alertable(route):
        return None
    return core_id, route
def _canonical_alertable_snapshot_rank(row: Mapping[str, Any]) -> tuple[float, float, str]:
    score = _num(row.get("opportunity_score_final") or row.get("final_opportunity_score") or row.get("score")) or 0.0
    source_quality = _num(row.get("source_quality") or row.get("evidence_quality_score")) or 0.0
    identifier = str(row.get("snapshot_id") or row.get("alert_key") or row.get("alert_id") or "")
    return score, source_quality, identifier
def _first_after(rows: Iterable[Mapping[str, Any]], ts: datetime) -> Mapping[str, Any] | None:
    for row in rows:
        row_ts = _dt(row.get("timestamp"))
        if row_ts is not None and row_ts >= ts:
            return row
    return None
def _close_at_or_after(rows: Iterable[Mapping[str, Any]], ts: datetime) -> float | None:
    row = _first_after(rows, ts)
    return _num(row.get("close")) if row else None
def _cohort_line(label: str, rows: Iterable[Mapping[str, Any]], field: str) -> str:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get(field) or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return f"{label}: " + ", ".join(f"{key}={count}" for key, count in sorted(counts.items()))
def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows
def _optional_str(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
def _dt(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return _as_utc(value)
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return _as_utc(parsed)
def _num(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
def _fmt_pct(value: object) -> str:
    num = _num(value)
    return "n/a" if num is None else f"{num * 100:+.1f}%"
def _fmt_bool(value: object) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "n/a"
def _json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return _as_utc(value).isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_ready(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(child) for child in value]
    return value
def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
