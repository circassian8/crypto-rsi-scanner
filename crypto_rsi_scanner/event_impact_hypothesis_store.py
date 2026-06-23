"""Profile-scoped JSONL store for Event Alpha impact hypotheses.

The store is a research artifact only. It records what the hypothesis engine
considered during an Event Alpha cycle so operator reviews can inspect the
candidate source, validation status, search queries, and watchlist promotion
links without relying on ephemeral console output.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
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
    watchlist_rows: Iterable[Mapping[str, Any] | object] = (),
) -> EventImpactHypothesisStoreWriteResult:
    """Append one row per generated hypothesis to a local JSONL artifact."""
    observed = _as_utc(now or datetime.now(timezone.utc)).isoformat()
    promotion_by_hypothesis_id = _watchlist_promotion_map(watchlist_rows)
    rows = [
        _row_from_hypothesis(
            item,
            observed_at=observed,
            run_id=run_id,
            profile=profile,
            run_mode=run_mode,
            artifact_namespace=artifact_namespace,
            promoted_watchlist_key=promotion_by_hypothesis_id.get(str(getattr(item, "hypothesis_id", "") or "")),
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
    now: datetime | None = None,
    stale_hours: float = 24.0,
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
    rows.append("validation_stages: " + _format_counts(_counts(result.rows, "validation_stage")))
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
    rows.extend(_hypothesis_section(
        "Pending validation-search hypotheses",
        [
            row for row in result.rows
            if str(row.get("status") or "") in {"validation_search_pending", "hypothesis"}
        ],
        limit=8,
    ))
    rows.append("")
    rows.extend(_hypothesis_section(
        "Validated hypotheses",
        [
            row for row in result.rows
            if str(row.get("status") or "") in {"validation_evidence_found", "validated"}
        ],
        limit=8,
    ))
    rows.append("")
    rows.extend(_hypothesis_section(
        "Rejected hypotheses",
        [
            row for row in result.rows
            if str(row.get("status") or "") == "rejected" or row.get("rejection_reasons")
        ],
        limit=8,
        include_rejections=True,
    ))
    rows.append("")
    rows.extend(_query_section(result.rows))
    rows.append("")
    rows.extend(_rejected_validation_samples_section(result.rows))
    rows.append("")
    rows.extend(_promotion_section(result.rows, promotion_ids))
    rows.append("")
    rows.extend(_stale_section(result.rows, now=now, stale_hours=stale_hours))
    rows.append("")
    rows.append("Recent rows:")
    for row in result.rows[:25]:
        rows.extend(_format_hypothesis_row(row, promotion_ids=promotion_ids, include_rejections=True))
    return "\n".join(rows).rstrip()


def format_impact_hypotheses_inbox(
    result: EventImpactHypothesisStoreReadResult,
    *,
    now: datetime | None = None,
    stale_hours: float = 24.0,
) -> str:
    """Return a compact review queue for stored impact hypotheses."""
    current = _as_utc(now or datetime.now(timezone.utc))
    pending = [
        row for row in result.rows
        if str(row.get("status") or "") == "validation_search_pending"
    ]
    ambiguous_rejected = [
        row for row in result.rows
        if str(row.get("status") or "") == "rejected"
        and any("ambiguous" in str(reason).lower() or "unknown" in str(reason).lower() for reason in row.get("rejection_reasons") or ())
    ]
    high_conf_sector = [
        row for row in result.rows
        if str(row.get("hypothesis_scope") or "") == "sector"
        and str(row.get("status") or "") not in {"validation_evidence_found", "validated"}
        and float(row.get("confidence") or 0) >= 0.75
    ]
    stale = _stale_rows(result.rows, now=current, stale_hours=stale_hours)
    rows = [
        "=" * 76,
        "EVENT IMPACT HYPOTHESES INBOX (research review queue)",
        "=" * 76,
        f"path: {result.path}",
        f"rows_read: {result.rows_read}",
        (
            "needs_review: "
            f"pending={len(pending)} · ambiguous_rejected={len(ambiguous_rejected)} · "
            f"high_conf_sector={len(high_conf_sector)} · stale={len(stale)}"
        ),
        "",
        "Pending validation search:",
    ]
    rows.extend(_compact_hypothesis_rows(pending, limit=10))
    rows.extend(["", "Rejected with ambiguous/unknown reason:"])
    rows.extend(_compact_hypothesis_rows(ambiguous_rejected, limit=10, include_rejections=True))
    rows.extend(["", "High-confidence sector hypotheses without validation:"])
    rows.extend(_compact_hypothesis_rows(high_conf_sector, limit=10))
    rows.extend(["", f"Stale hypotheses older than {stale_hours:g}h:"])
    rows.extend(_compact_hypothesis_rows(stale, limit=10))
    rows.append("")
    rows.append("Research-only queue; no sends, trades, paper rows, live RSI rows, or trigger creation.")
    return "\n".join(rows).rstrip()


def _row_from_hypothesis(
    hypothesis: object,
    *,
    observed_at: str,
    run_id: str | None,
    profile: str | None,
    run_mode: str | None,
    artifact_namespace: str | None,
    promoted_watchlist_key: str | None = None,
) -> dict[str, Any]:
    if hasattr(hypothesis, "__dataclass_fields__"):
        data = asdict(hypothesis)
    else:
        data = dict(getattr(hypothesis, "__dict__", {}) or {})
    validated_asset = _first_mapping(data.get("validated_candidate_assets") or ())
    data.update({
        "schema_version": IMPACT_HYPOTHESIS_STORE_SCHEMA_VERSION,
        "row_type": "event_impact_hypothesis",
        "observed_at": observed_at,
        "run_id": run_id,
        "profile": profile or "default",
        "run_mode": run_mode,
        "artifact_namespace": artifact_namespace,
        "research_only": True,
        "candidate_sources": _candidate_sources(data.get("candidate_source")),
        "promoted_watchlist_key": promoted_watchlist_key,
        "validated_symbol": str(validated_asset.get("symbol") or "") or None,
        "validated_coin_id": str(validated_asset.get("coin_id") or "") or None,
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


def _watchlist_promotion_map(watchlist_rows: Iterable[Mapping[str, Any] | object]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in watchlist_rows:
        row = item if isinstance(item, Mapping) else getattr(item, "__dict__", {}) or {}
        if str(row.get("relationship_type") or "") != "impact_hypothesis":
            continue
        if str(row.get("state") or "").lower() not in {"radar", "watchlist", "high_priority"}:
            continue
        event_id = str(row.get("event_id") or "")
        key = str(row.get("key") or "")
        if event_id and key:
            out[event_id] = key
    return out


def _candidate_sources(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        raw = [str(item) for item in value]
    else:
        raw = str(value or "").replace("|", ",").split(",")
    return [item.strip() for item in raw if item.strip()]


def _first_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if isinstance(value, (list, tuple)):
        for item in value:
            if isinstance(item, Mapping):
                return item
    return {}


def _hypothesis_section(
    title: str,
    rows: list[Mapping[str, Any]],
    *,
    limit: int,
    include_rejections: bool = False,
) -> list[str]:
    out = [f"{title}: {len(rows)}"]
    out.extend(_compact_hypothesis_rows(rows, limit=limit, include_rejections=include_rejections))
    return out


def _compact_hypothesis_rows(
    rows: list[Mapping[str, Any]],
    *,
    limit: int,
    include_rejections: bool = False,
) -> list[str]:
    if not rows:
        return ["- none"]
    out: list[str] = []
    for row in rows[:limit]:
        out.append(
            f"- {row.get('status') or 'unknown'} stage={row.get('validation_stage') or 'unknown'} "
            f"score={float(row.get('hypothesis_score') or float(row.get('confidence') or 0) * 100):.1f} "
            f"conf={float(row.get('confidence') or 0):.2f} "
            f"{row.get('impact_category') or 'unknown'} external={row.get('external_asset') or 'unknown'} "
            f"scope={row.get('hypothesis_scope') or 'unknown'}"
        )
        candidates = row.get("validated_candidate_assets") or row.get("crypto_candidate_assets") or row.get("suggested_candidate_assets") or []
        if candidates:
            out.append("  candidates: " + ", ".join(_asset_label(asset) for asset in candidates[:6]))
        rejected_candidates = row.get("rejected_candidate_assets") or []
        if rejected_candidates:
            out.append("  rejected_candidates: " + ", ".join(_asset_label(asset) for asset in rejected_candidates[:4]))
        queries = row.get("search_queries") or []
        if queries:
            out.append("  queries: " + " | ".join(str(query) for query in queries[:3]))
        if row.get("validation_reasons"):
            out.append("  validated: " + "; ".join(str(item) for item in row["validation_reasons"][:3]))
        if include_rejections and row.get("rejection_reasons"):
            out.append("  rejected: " + "; ".join(str(item) for item in row["rejection_reasons"][:3]))
    if len(rows) > limit:
        out.append(f"- +{len(rows) - limit} more")
    return out


def _format_hypothesis_row(
    row: Mapping[str, Any],
    *,
    promotion_ids: set[str],
    include_rejections: bool = False,
) -> list[str]:
    hypothesis_id = str(row.get("hypothesis_id") or "unknown")
    promoted = "yes" if hypothesis_id in promotion_ids or row.get("promoted_watchlist_key") else "no"
    out = [
        (
            f"- {row.get('status') or 'unknown'} stage={row.get('validation_stage') or 'unknown'} "
            f"score={float(row.get('hypothesis_score') or float(row.get('confidence') or 0) * 100):.1f} "
            f"conf={float(row.get('confidence') or 0):.2f} "
            f"{row.get('impact_category') or 'unknown'} external={row.get('external_asset') or 'unknown'} "
            f"scope={row.get('hypothesis_scope') or 'unknown'} promoted={promoted}"
        )
    ]
    candidates = row.get("validated_candidate_assets") or row.get("crypto_candidate_assets") or row.get("suggested_candidate_assets") or []
    out.append(
        "  candidates: " + ", ".join(_asset_label(asset) for asset in candidates[:8])
        if candidates
        else "  candidates: none"
    )
    external_entities = row.get("external_entities") or []
    if external_entities:
        out.append("  external_entities: " + ", ".join(str(entity.get("name") or "") for entity in external_entities[:6] if isinstance(entity, Mapping)))
    rejected_candidates = row.get("rejected_candidate_assets") or []
    if rejected_candidates:
        out.append("  rejected_candidates: " + ", ".join(_asset_label(asset) for asset in rejected_candidates[:6]))
    out.append(f"  source={row.get('candidate_source') or 'unknown'} query_count={len(row.get('search_queries') or [])}")
    if row.get("validated_symbol") or row.get("validated_coin_id"):
        out.append(f"  validated_asset: {row.get('validated_symbol') or 'unknown'}/{row.get('validated_coin_id') or 'unknown'}")
    if row.get("promoted_watchlist_key"):
        out.append(f"  promoted_watchlist_key: {row.get('promoted_watchlist_key')}")
    if row.get("validation_reasons"):
        out.append("  validated: " + "; ".join(str(item) for item in row["validation_reasons"][:3]))
    if include_rejections and row.get("rejection_reasons"):
        out.append("  rejected: " + "; ".join(str(item) for item in row["rejection_reasons"][:3]))
    if row.get("warnings"):
        out.append("  warnings: " + "; ".join(str(item) for item in row["warnings"][:3]))
    return out


def _query_section(rows: list[Mapping[str, Any]], *, limit: int = 12) -> list[str]:
    queries: list[tuple[str, str]] = []
    for row in rows:
        details = row.get("search_query_details") or []
        if details:
            for item in details:
                if not isinstance(item, Mapping):
                    continue
                text = str(item.get("query") or "").strip()
                qtype = str(item.get("query_type") or "candidate_validation")
                if text and (text, qtype) not in queries:
                    queries.append((text, qtype))
            continue
        for query in row.get("search_queries") or []:
            text = str(query).strip()
            if text and (text, "candidate_validation") not in queries:
                queries.append((text, "candidate_validation"))
    out = [f"Generated search queries: {len(queries)}"]
    if not queries:
        out.append("- none")
        return out
    out.extend(f"- {qtype}: {query}" for query, qtype in queries[:limit])
    if len(queries) > limit:
        out.append(f"- +{len(queries) - limit} more")
    return out


def _rejected_validation_samples_section(rows: list[Mapping[str, Any]], *, limit: int = 12) -> list[str]:
    samples: list[Mapping[str, Any]] = []
    for row in rows:
        for sample in row.get("rejected_validation_samples") or []:
            if isinstance(sample, Mapping):
                samples.append(sample)
    out = [f"Rejected validation evidence samples: {len(samples)}"]
    if not samples:
        out.append("- none")
        return out
    for sample in samples[:limit]:
        out.append(
            f"- {sample.get('query_type') or 'unknown'} {sample.get('candidate_symbol') or 'SECTOR'} "
            f"score={sample.get('score') or 0} rejected={sample.get('rejection_reason') or 'none'} "
            f"title={sample.get('result_title') or 'unknown'}"
        )
    if len(samples) > limit:
        out.append(f"- +{len(samples) - limit} more")
    return out


def _promotion_section(rows: list[Mapping[str, Any]], promotion_ids: set[str]) -> list[str]:
    promoted = [
        row for row in rows
        if row.get("promoted_watchlist_key") or str(row.get("hypothesis_id") or "") in promotion_ids
    ]
    out = [f"Promotions / promoted watchlist keys: {len(promoted)}"]
    if not promoted:
        out.append("- none")
        return out
    for row in promoted[:10]:
        out.append(
            f"- {row.get('impact_category') or 'unknown'} external={row.get('external_asset') or 'unknown'} "
            f"key={row.get('promoted_watchlist_key') or 'linked-watchlist'}"
        )
    if len(promoted) > 10:
        out.append(f"- +{len(promoted) - 10} more")
    return out


def _stale_section(rows: list[Mapping[str, Any]], *, now: datetime | None, stale_hours: float) -> list[str]:
    stale = _stale_rows(rows, now=_as_utc(now or datetime.now(timezone.utc)), stale_hours=stale_hours)
    out = [f"Stale hypotheses older than {stale_hours:g}h: {len(stale)}"]
    out.extend(_compact_hypothesis_rows(stale, limit=8))
    return out


def _stale_rows(
    rows: list[Mapping[str, Any]],
    *,
    now: datetime,
    stale_hours: float,
) -> list[Mapping[str, Any]]:
    cutoff = now - timedelta(hours=max(0.0, stale_hours))
    stale: list[Mapping[str, Any]] = []
    for row in rows:
        if str(row.get("status") or "") in {"validation_evidence_found", "validated", "rejected"}:
            continue
        observed = _parse_datetime(row.get("observed_at") or row.get("created_at"))
        if observed is not None and observed < cutoff:
            stale.append(row)
    return stale


def _parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return _as_utc(datetime.fromisoformat(text.replace("Z", "+00:00")))
    except ValueError:
        return None


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
