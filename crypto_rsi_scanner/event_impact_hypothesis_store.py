"""Profile-scoped JSONL store for Event Alpha impact hypotheses.

The store is a research artifact only. It records what the hypothesis engine
considered during an Event Alpha cycle so operator reviews can inspect the
candidate source, validation status, search queries, and watchlist promotion
links without relying on ephemeral console output.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


IMPACT_HYPOTHESIS_STORE_SCHEMA_VERSION = "event_impact_hypothesis_store_v1"


@dataclass(frozen=True)
class EventImpactHypothesisStoreConfig:
    path: Path


@dataclass(frozen=True)
class EventImpactHypothesisStoreWriteResult:
    path: Path
    attempted: bool
    success: bool
    rows_written: int = 0
    block_reason: str | None = None


@dataclass(frozen=True)
class EventImpactHypothesisStoreReadResult:
    path: Path
    rows_read: int
    rows: list[dict[str, Any]]


def write_impact_hypotheses(
    hypotheses: Iterable[object],
    *,
    cfg: EventImpactHypothesisStoreConfig,
    now: datetime | None = None,
    run_id: str | None = None,
    profile: str | None = None,
    run_mode: str | None = None,
    artifact_namespace: str | None = None,
) -> EventImpactHypothesisStoreWriteResult:
    """Append one row per generated hypothesis to a local JSONL artifact."""
    observed = _as_utc(now or datetime.now(timezone.utc)).isoformat()
    rows = [
        _row_from_hypothesis(
            item,
            observed_at=observed,
            run_id=run_id,
            profile=profile,
            run_mode=run_mode,
            artifact_namespace=artifact_namespace,
        )
        for item in hypotheses
    ]
    path = cfg.path.expanduser()
    try:
        if not rows:
            path.parent.mkdir(parents=True, exist_ok=True)
            return EventImpactHypothesisStoreWriteResult(path=path, attempted=True, success=True, rows_written=0)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(_json_ready(row), sort_keys=True, separators=(",", ":")))
                fh.write("\n")
        return EventImpactHypothesisStoreWriteResult(path=path, attempted=True, success=True, rows_written=len(rows))
    except Exception as exc:  # noqa: BLE001 - artifact writes must fail soft.
        return EventImpactHypothesisStoreWriteResult(
            path=path,
            attempted=True,
            success=False,
            rows_written=0,
            block_reason=f"{type(exc).__name__}: {exc}",
        )


def load_impact_hypotheses(path: str | Path, *, limit: int | None = None) -> EventImpactHypothesisStoreReadResult:
    """Load stored hypothesis rows newest-first, tolerating legacy/bad rows."""
    p = Path(path).expanduser()
    rows = [
        row for row in _read_jsonl(p)
        if row.get("row_type") == "event_impact_hypothesis"
    ]
    rows.sort(key=lambda row: str(row.get("observed_at") or row.get("created_at") or ""), reverse=True)
    if limit is not None and limit > 0:
        rows = rows[:limit]
    return EventImpactHypothesisStoreReadResult(path=p, rows_read=len(rows), rows=rows)


def format_impact_hypotheses_store_report(
    result: EventImpactHypothesisStoreReadResult,
    *,
    watchlist_rows: Iterable[Mapping[str, Any]] = (),
) -> str:
    """Return an operator-readable report for the hypothesis artifact."""
    rows = [
        "=" * 76,
        "EVENT IMPACT HYPOTHESES REPORT (research artifact only)",
        "=" * 76,
        f"path: {result.path}",
        f"rows_read: {result.rows_read}",
    ]
    if not result.rows:
        rows.extend(["", "No stored impact hypotheses found."])
        return "\n".join(rows)

    rows.append("categories: " + _format_counts(_counts(result.rows, "impact_category")))
    rows.append("statuses: " + _format_counts(_counts(result.rows, "status")))
    rows.append("scopes: " + _format_counts(_counts(result.rows, "hypothesis_scope")))
    rows.append("candidate_sources: " + _format_counts(_counts(result.rows, "candidate_source")))
    rows.append(
        "review states: "
        + f"pending={_status_count(result.rows, 'validation_search_pending') + _status_count(result.rows, 'hypothesis')} · "
        + f"validated={_status_count(result.rows, 'validated')} · rejected={_status_count(result.rows, 'rejected')}"
    )
    rows.append(
        "queries: "
        + str(sum(len(row.get("search_queries") or []) for row in result.rows))
    )
    promotion_ids = _promoted_hypothesis_ids(watchlist_rows)
    rows.append(f"watchlist promotions linked: {len(promotion_ids)}")
    rows.append("")
    for row in result.rows[:25]:
        hypothesis_id = str(row.get("hypothesis_id") or "unknown")
        promoted = "yes" if hypothesis_id in promotion_ids else "no"
        rows.append(
            f"- {row.get('status') or 'unknown'} conf={float(row.get('confidence') or 0):.2f} "
            f"{row.get('impact_category') or 'unknown'} external={row.get('external_asset') or 'unknown'} "
            f"scope={row.get('hypothesis_scope') or 'unknown'} promoted={promoted}"
        )
        rows.append(
            "  candidates: "
            + ", ".join(_asset_label(asset) for asset in (row.get("validated_candidate_assets") or row.get("suggested_candidate_assets") or [])[:8])
            if (row.get("validated_candidate_assets") or row.get("suggested_candidate_assets"))
            else "  candidates: none"
        )
        rows.append(f"  source={row.get('candidate_source') or 'unknown'} query_count={len(row.get('search_queries') or [])}")
        if row.get("validation_reasons"):
            rows.append("  validated: " + "; ".join(str(item) for item in row["validation_reasons"][:3]))
        if row.get("rejection_reasons"):
            rows.append("  rejected: " + "; ".join(str(item) for item in row["rejection_reasons"][:3]))
        if row.get("warnings"):
            rows.append("  warnings: " + "; ".join(str(item) for item in row["warnings"][:3]))
    return "\n".join(rows).rstrip()


def _row_from_hypothesis(
    hypothesis: object,
    *,
    observed_at: str,
    run_id: str | None,
    profile: str | None,
    run_mode: str | None,
    artifact_namespace: str | None,
) -> dict[str, Any]:
    if hasattr(hypothesis, "__dataclass_fields__"):
        data = asdict(hypothesis)
    else:
        data = dict(getattr(hypothesis, "__dict__", {}) or {})
    data.update({
        "schema_version": IMPACT_HYPOTHESIS_STORE_SCHEMA_VERSION,
        "row_type": "event_impact_hypothesis",
        "observed_at": observed_at,
        "run_id": run_id,
        "profile": profile or "default",
        "run_mode": run_mode,
        "artifact_namespace": artifact_namespace,
        "research_only": True,
    })
    return data


def _promoted_hypothesis_ids(watchlist_rows: Iterable[Mapping[str, Any]]) -> set[str]:
    out: set[str] = set()
    for row in watchlist_rows:
        if str(row.get("relationship_type") or "") != "impact_hypothesis":
            continue
        if str(row.get("state") or "").lower() not in {"radar", "watchlist", "high_priority"}:
            continue
        event_id = str(row.get("event_id") or "")
        if event_id:
            out.add(event_id)
    return out


def _counts(rows: Iterable[Mapping[str, Any]], field: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        key = str(row.get(field) or "unknown")
        out[key] = out.get(key, 0) + 1
    return out


def _status_count(rows: Iterable[Mapping[str, Any]], status: str) -> int:
    return sum(1 for row in rows if str(row.get("status") or "") == status)


def _format_counts(counts: Mapping[str, int]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items())) or "none"


def _asset_label(asset: Mapping[str, Any]) -> str:
    symbol = str(asset.get("symbol") or "").upper()
    coin_id = str(asset.get("coin_id") or "")
    name = str(asset.get("name") or "")
    label = symbol or coin_id or name or "asset"
    if coin_id and coin_id != label:
        label = f"{label}/{coin_id}"
    source = str(asset.get("source") or "")
    return f"{label} ({source})" if source else label


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            text = line.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(row, Mapping):
                rows.append(dict(row))
    return rows


def _json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_ready(val) for key, val in value.items()}
    return value


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
