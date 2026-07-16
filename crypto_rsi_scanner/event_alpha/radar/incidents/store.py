"""Split implementation for `crypto_rsi_scanner/event_alpha/radar/incidents.py` (store)."""

from __future__ import annotations

import json
from collections.abc import Iterable as IterableABC
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
import crypto_rsi_scanner.event_alpha.radar.claim_semantics as event_claim_semantics
import crypto_rsi_scanner.event_alpha.radar.incident_graph as event_incident_graph
import crypto_rsi_scanner.event_alpha.radar.source_independence_store as event_source_independence_store
from crypto_rsi_scanner.event_core.models import EventDiscoveryResult, RawDiscoveredEvent
from .models import *  # noqa: F403

def build_incident_rows(
    discovery_result: EventDiscoveryResult,
    *,
    hypotheses: Iterable[object] = (),
    watchlist_rows: Iterable[Mapping[str, Any] | object] = (),
    now: datetime | None = None,
    run_id: str | None = None,
    profile: str | None = None,
    run_mode: str | None = None,
    artifact_namespace: str | None = None,
) -> list[dict[str, Any]]:
    """Build serializable incident rows from a discovery result and links."""
    observed = _as_utc(now or datetime.now(timezone.utc)).isoformat()
    raw_by_id = {raw.raw_id: raw for raw in discovery_result.raw_events}
    incidents = event_incident_graph.build_incidents(discovery_result.normalized_events, raw_by_id)
    hypotheses_by_incident = _hypotheses_by_incident(hypotheses)
    watchlist_by_incident = _watchlist_by_incident(watchlist_rows)
    rows = []
    for incident in incidents:
        matching_hypotheses = hypotheses_by_incident.get(incident.incident_id, [])
        matching_watchlist = watchlist_by_incident.get(incident.incident_id, [])
        rows.append(_row_from_incident(
            incident,
            raw_by_id=raw_by_id,
            observed_at=observed,
            run_id=run_id,
            profile=profile,
            run_mode=run_mode,
            artifact_namespace=artifact_namespace,
            hypotheses=matching_hypotheses,
            watchlist_rows=matching_watchlist,
        ))
    return rows
def write_incidents(
    discovery_result: EventDiscoveryResult,
    *,
    cfg: EventIncidentStoreConfig,
    hypotheses: Iterable[object] = (),
    watchlist_rows: Iterable[Mapping[str, Any] | object] = (),
    now: datetime | None = None,
    run_id: str | None = None,
    profile: str | None = None,
    run_mode: str | None = None,
    artifact_namespace: str | None = None,
) -> EventIncidentStoreWriteResult:
    """Append canonical incident rows to a local JSONL artifact."""
    path = cfg.path.expanduser()
    try:
        rows = build_incident_rows(
            discovery_result,
            hypotheses=hypotheses,
            watchlist_rows=watchlist_rows,
            now=now,
            run_id=run_id,
            profile=profile,
            run_mode=run_mode,
            artifact_namespace=artifact_namespace,
        )
        debug_store = _debug_allows_diagnostic(profile=profile, run_mode=run_mode)
        store_diagnostic = bool(cfg.store_diagnostic or debug_store)
        store_raw_observations = bool(cfg.store_raw_observations or cfg.store_diagnostic or debug_store)
        rows = [_row_with_effective_relevance(_row_with_effective_subject_quality(row)) for row in rows]
        rows_to_write = [
            row for row in rows
            if _should_persist_incident_row(
                row,
                store_diagnostic=store_diagnostic,
                store_raw_observations=store_raw_observations,
            )
        ]
        path.parent.mkdir(parents=True, exist_ok=True)
        persisted_rows = [
            event_source_independence_store.externalize(
                path.parent,
                _json_ready(row),
            )
            for row in rows_to_write
        ]
        with path.open("a", encoding="utf-8") as fh:
            for persisted in persisted_rows:
                fh.write(json.dumps(persisted, sort_keys=True, separators=(",", ":")))
                fh.write("\n")
        return EventIncidentStoreWriteResult(path=path, attempted=True, success=True, rows_written=len(rows_to_write))
    except Exception as exc:  # noqa: BLE001 - artifact writes must fail soft.
        return EventIncidentStoreWriteResult(
            path=path,
            attempted=True,
            success=False,
            rows_written=0,
            block_reason=f"{type(exc).__name__}: {exc}",
        )
def load_incidents(
    path: str | Path,
    *,
    limit: int | None = None,
    latest_run: bool = False,
    run_id: str | None = None,
    include_api: bool = True,
    include_diagnostic: bool = False,
    include_raw: bool = False,
    include_external_context: bool = False,
) -> EventIncidentStoreReadResult:
    """Load stored incidents newest-first, tolerating malformed legacy rows."""
    p = Path(path).expanduser()
    all_rows = [
        row for row in _read_jsonl(p)
        if row.get("row_type") == "event_incident"
    ]
    all_rows.sort(key=lambda row: str(row.get("last_updated_at") or row.get("observed_at") or ""), reverse=True)
    latest_id = _latest_run_id(all_rows)
    latest_count = sum(1 for row in all_rows if _row_run_id(row) == latest_id) if latest_id else 0
    legacy_count = sum(1 for row in all_rows if _is_api_row(row))
    rows = _filter_rows(
        all_rows,
        latest_run=latest_run,
        latest_run_id=latest_id,
        run_id=run_id,
        include_api=include_api,
    )
    rows = [_row_with_effective_relevance(_row_with_effective_subject_quality(row)) for row in rows]
    if limit is not None and limit > 0:
        rows = rows[:limit]
    return EventIncidentStoreReadResult(
        path=p,
        rows_read=len(rows),
        rows=rows,
        total_rows_read=len(all_rows),
        latest_run_id=latest_id,
        latest_run_rows_available=latest_count,
        historical_rows_available=max(0, len(all_rows) - latest_count),
        legacy_rows_available=legacy_count,
        filters={
            "latest_run": bool(latest_run),
            "run_id": run_id,
            "include_api": bool(include_api),
            "include_diagnostic": bool(include_diagnostic),
            "include_raw": bool(include_raw),
            "include_external_context": bool(include_external_context),
            "limit": limit,
        },
    )
def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(value, Mapping):
                    rows.append(
                        dict(
                            event_source_independence_store.hydrate(
                                path.parent,
                                value,
                            )
                        )
                    )
    except OSError:
        return []
    return rows
def _filter_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    latest_run: bool,
    latest_run_id: str | None,
    run_id: str | None,
    include_api: bool,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        data = dict(row)
        if not include_api and _is_api_row(data):
            continue
        if run_id and _row_run_id(data) != run_id:
            continue
        if latest_run and latest_run_id and _row_run_id(data) != latest_run_id:
            continue
        out.append(data)
    return out
def _latest_run_id(rows: Iterable[Mapping[str, Any]]) -> str | None:
    for row in rows:
        run_id = _row_run_id(row)
        if run_id:
            return run_id
    return None
def _row_run_id(row: Mapping[str, Any]) -> str | None:
    value = row.get("run_id")
    return str(value) if value not in (None, "") else None
def _is_api_row(row: Mapping[str, Any]) -> bool:
    return not str(row.get("schema_version") or "").startswith("event_incident_store_")
