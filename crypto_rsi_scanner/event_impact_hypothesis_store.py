"""Profile-scoped JSONL store for Event Alpha impact hypotheses.

The store is a research artifact only. It records what the hypothesis engine
considered during an Event Alpha cycle so operator reviews can inspect the
candidate source, validation status, search queries, and watchlist promotion
links without relying on ephemeral console output.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
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
    total_rows_read: int = 0
    latest_run_id: str | None = None
    latest_run_rows_available: int = 0
    historical_rows_available: int = 0
    legacy_rows_available: int = 0
    filters: dict[str, Any] = field(default_factory=dict)


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


def load_impact_hypotheses(
    path: str | Path,
    *,
    limit: int | None = None,
    latest_run: bool = False,
    run_id: str | None = None,
    since: str | datetime | None = None,
    include_legacy: bool = True,
) -> EventImpactHypothesisStoreReadResult:
    """Load stored hypothesis rows newest-first, tolerating legacy/bad rows."""
    p = Path(path).expanduser()
    all_rows = [
        row for row in _read_jsonl(p)
        if row.get("row_type") == "event_impact_hypothesis"
    ]
    all_rows.sort(key=lambda row: str(row.get("observed_at") or row.get("created_at") or ""), reverse=True)
    latest_id = _latest_run_id(all_rows)
    latest_count = sum(1 for row in all_rows if _row_run_id(row) == latest_id) if latest_id else 0
    legacy_count = sum(1 for row in all_rows if _is_legacy_row(row))
    rows = _filter_rows(
        all_rows,
        latest_run=latest_run,
        latest_run_id=latest_id,
        run_id=run_id,
        since=since,
        include_legacy=include_legacy,
    )
    if limit is not None and limit > 0:
        rows = rows[:limit]
    return EventImpactHypothesisStoreReadResult(
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
            "since": since.isoformat() if isinstance(since, datetime) else since,
            "include_legacy": bool(include_legacy),
            "limit": limit,
        },
    )


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
        f"total_rows_available: {result.total_rows_read or result.rows_read}",
        f"latest_run_id: {result.latest_run_id or 'unknown'}",
        f"latest_run_rows_available: {result.latest_run_rows_available}",
        f"historical_rows_available: {result.historical_rows_available}",
        f"legacy_rows_available: {result.legacy_rows_available}",
        "filters: " + _format_filter_summary(result.filters),
    ]
    if not result.rows:
        rows.extend(["", "No stored impact hypotheses matched the current report filters."])
        return "\n".join(rows)

    rows.extend(_schema_audit_section(result.rows))
    rows.append("categories: " + _format_counts(_counts(result.rows, "impact_category")))
    rows.append("statuses: " + _format_counts(_counts(result.rows, "status")))
    rows.append("validation_stages: " + _format_counts(_counts(result.rows, "validation_stage")))
    rows.append("impact_path_reasons: " + _format_counts(_counts(result.rows, "impact_path_reason")))
    rows.append("impact_path_types: " + _format_counts(_counts(result.rows, "impact_path_type")))
    rows.append("impact_path_strengths: " + _format_counts(_counts(result.rows, "impact_path_strength")))
    rows.append("candidate_roles: " + _format_counts(_counts(result.rows, "candidate_role")))
    rows.append("why_not_promoted: " + _format_counts(_reason_counts(result.rows, "why_not_promoted")))
    rows.extend(_entity_audit_section(result.rows))
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
        + " · generated_by_type="
        + _format_counts(_query_type_counts(result.rows, "generated_queries"))
        + " · executed_by_type="
        + _format_counts(_query_type_counts(result.rows, "executed_queries"))
    )
    promotion_ids = _promoted_hypothesis_ids(watchlist_rows)
    rows.append(f"watchlist promotions linked: {len(promotion_ids)}")
    rows.append(
        "route eligibility note: promoted hypothesis rows are watchlist links; "
        "the Event Alpha router quality gate decides digest vs local-only."
    )
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
    rows.extend(_why_not_promoted_section(result.rows))
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
        if row.get("impact_path_reason"):
            out.append(f"  impact_path_reason: {row.get('impact_path_reason')}")
        if row.get("impact_path_type") or row.get("opportunity_score_v2") is not None:
            out.append(
                "  impact_path: "
                f"type={row.get('impact_path_type') or 'unknown'} "
                f"role={row.get('candidate_role') or 'unknown'} "
                f"strength={row.get('impact_path_strength') or 'unknown'} "
                f"v2={row.get('opportunity_score_v2') if row.get('opportunity_score_v2') is not None else 'n/a'} "
                f"digest_eligible={str(bool(row.get('digest_eligible_by_impact_path'))).lower()}"
            )
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
    if str(row.get("status") or "") == "validated" and row.get("validated_symbol") and row.get("promoted_watchlist_key"):
        out.append("  route_eligibility: linked_watchlist_candidate; router_quality_gate_decides_digest")
    if row.get("validation_reasons"):
        out.append("  validated: " + "; ".join(str(item) for item in row["validation_reasons"][:3]))
    if row.get("impact_path_reason"):
        out.append(f"  impact_path_reason: {row.get('impact_path_reason')}")
    if row.get("impact_path_type") or row.get("opportunity_score_v2") is not None:
        out.append(
            "  impact_path: "
            f"type={row.get('impact_path_type') or 'unknown'} "
            f"role={row.get('candidate_role') or 'unknown'} "
            f"strength={row.get('impact_path_strength') or 'unknown'} "
            f"specificity={row.get('evidence_specificity_score') if row.get('evidence_specificity_score') is not None else 'n/a'} "
            f"v2={row.get('opportunity_score_v2') if row.get('opportunity_score_v2') is not None else 'n/a'}"
        )
    if row.get("why_digest_ineligible"):
        out.append(f"  why_digest_ineligible: {row.get('why_digest_ineligible')}")
    if include_rejections and row.get("rejection_reasons"):
        out.append("  rejected: " + "; ".join(str(item) for item in row["rejection_reasons"][:3]))
    if row.get("why_not_promoted"):
        out.append("  why_not_promoted: " + "; ".join(_effective_why_not_promoted(row)[:4]))
    warnings = [str(item) for item in row.get("warnings") or []]
    mismatch = _candidate_order_mismatch_warning(row)
    if mismatch:
        warnings.append(mismatch)
    if warnings:
        out.append("  warnings: " + "; ".join(dict.fromkeys(warnings[:4])))
    return out


def _schema_audit_section(rows: list[Mapping[str, Any]]) -> list[str]:
    versions = _counts(rows, "schema_version")
    required = (
        "validation_stage",
        "hypothesis_score",
        "external_entities",
        "crypto_candidate_assets",
    )
    missing = {
        field: sum(1 for row in rows if field not in row)
        for field in required
    }
    legacy = [row for row in rows if _is_legacy_row(row)]
    return [
        "schema_audit: "
        f"versions={_format_counts(versions)} · legacy_rows={len(legacy)} · "
        + " · ".join(f"missing_{field}={count}" for field, count in missing.items())
    ]


def _candidate_order_mismatch_warning(row: Mapping[str, Any]) -> str | None:
    validated = str(row.get("validated_symbol") or "").strip().upper()
    if not validated:
        return None
    symbols = row.get("candidate_symbols") or ()
    if not isinstance(symbols, (list, tuple)) or not symbols:
        return None
    first = str(symbols[0] or "").strip().upper()
    if first and first != validated:
        return f"validated_asset_mismatch_candidate_order:first_candidate={first} validated={validated}"
    return None


def _query_section(rows: list[Mapping[str, Any]], *, limit: int = 12) -> list[str]:
    queries: list[tuple[str, str]] = []
    for row in rows:
        details = row.get("generated_queries") or row.get("search_query_details") or []
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
    out = [
        f"Generated search queries: {len(queries)}",
        "generated_query_type_counts: " + _format_counts(_query_type_counts(rows, "generated_queries")),
        "executed_query_type_counts: " + _format_counts(_query_type_counts(rows, "executed_queries")),
    ]
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
                if not bool(sample.get("accepted")) or sample.get("rejection_reason"):
                    samples.append(sample)
    out = [f"Rejected validation evidence samples: {len(samples)}"]
    if not samples:
        out.append("- none")
        return out
    for sample in samples[:limit]:
        out.append(
            f"- {sample.get('query_type') or 'unknown'} {sample.get('candidate_symbol') or 'SECTOR'} "
            f"score={sample.get('result_score') or sample.get('score') or 0} rejected={sample.get('rejection_reason') or 'none'} "
            f"title={sample.get('result_title') or 'unknown'}"
        )
    if len(samples) > limit:
        out.append(f"- +{len(samples) - limit} more")
    return out


def _why_not_promoted_section(rows: list[Mapping[str, Any]], *, limit: int = 10) -> list[str]:
    counts = _reason_counts(rows, "why_not_promoted")
    out = ["Why not promoted diagnostics: " + _format_counts(counts)]
    if not counts:
        return out
    top_rows = [
        row for row in rows
        if _effective_why_not_promoted(row)
    ]
    for row in top_rows[:limit]:
        out.append(
            f"- {row.get('impact_category') or 'unknown'} external={row.get('external_asset') or 'unknown'} "
            f"stage={row.get('validation_stage') or 'unknown'} reasons="
            + ";".join(str(item) for item in _effective_why_not_promoted(row)[:4])
        )
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


def _reason_counts(rows: Iterable[Mapping[str, Any]], field: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        values = _effective_why_not_promoted(row) if field == "why_not_promoted" else row.get(field) or []
        if isinstance(values, str):
            values = [values]
        for value in values:
            key = str(value or "").strip()
            if key:
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


def _format_filter_summary(filters: Mapping[str, Any]) -> str:
    if not filters:
        return "none"
    parts = []
    for key in ("latest_run", "run_id", "since", "include_legacy", "limit"):
        value = filters.get(key)
        if value not in (None, ""):
            parts.append(f"{key}={value}")
    return ", ".join(parts) or "none"


def _row_run_id(row: Mapping[str, Any]) -> str:
    return str(row.get("run_id") or "").strip()


def _latest_run_id(rows: Iterable[Mapping[str, Any]]) -> str | None:
    for row in rows:
        run_id = _row_run_id(row)
        if run_id:
            return run_id
    return None


def _filter_rows(
    rows: list[dict[str, Any]],
    *,
    latest_run: bool,
    latest_run_id: str | None,
    run_id: str | None,
    since: str | datetime | None,
    include_legacy: bool,
) -> list[dict[str, Any]]:
    cutoff = _parse_datetime(since) if since is not None else None
    target_run = str(run_id or "").strip()
    out: list[dict[str, Any]] = []
    for row in rows:
        if target_run and _row_run_id(row) != target_run:
            continue
        if latest_run and latest_run_id and _row_run_id(row) != latest_run_id:
            continue
        if cutoff is not None:
            observed = _parse_datetime(row.get("observed_at") or row.get("created_at"))
            if observed is None or observed < cutoff:
                continue
        if not include_legacy and _is_legacy_row(row):
            continue
        out.append(row)
    return out


def _is_legacy_row(row: Mapping[str, Any]) -> bool:
    required = (
        "validation_stage",
        "hypothesis_score",
        "external_entities",
        "crypto_candidate_assets",
    )
    return (
        str(row.get("schema_version") or "") != IMPACT_HYPOTHESIS_STORE_SCHEMA_VERSION
        or any(field not in row for field in required)
    )


def _effective_why_not_promoted(row: Mapping[str, Any]) -> tuple[str, ...]:
    values = row.get("why_not_promoted") or []
    if isinstance(values, str):
        raw = [values]
    else:
        raw = list(values)
    if _is_legacy_row(row) and "validation_stage" not in row:
        raw.append("legacy_schema_missing_stage")
    return tuple(dict.fromkeys(str(value) for value in raw if str(value or "").strip()))


def _query_type_counts(rows: Iterable[Mapping[str, Any]], field: str) -> dict[str, int]:
    out: dict[str, int] = {}
    fallback_field = "search_query_details" if field == "generated_queries" else ""
    for row in rows:
        details = row.get(field) or (row.get(fallback_field) if fallback_field else None) or []
        if not details and field == "generated_queries":
            details = [{"query": query, "query_type": "candidate_validation"} for query in row.get("search_queries") or []]
        for item in details:
            if not isinstance(item, Mapping):
                continue
            qtype = str(item.get("query_type") or "candidate_validation")
            out[qtype] = out.get(qtype, 0) + 1
    return out


_SUSPICIOUS_EXTERNAL_CANDIDATES = {
    "openai",
    "anthropic",
    "spacex",
    "space x",
    "stripe",
    "databricks",
    "anduril",
    "figma",
}


def _entity_audit_section(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    external_seen: set[str] = set()
    crypto_seen: set[str] = set()
    suspicious: list[str] = []
    for row in rows:
        external = str(row.get("external_asset") or "").strip()
        if external:
            external_seen.add(external)
        for entity in row.get("external_entities") or []:
            if isinstance(entity, Mapping):
                name = str(entity.get("name") or "").strip()
                if name:
                    external_seen.add(name)
        for asset in _candidate_asset_rows(row):
            label = _asset_label(asset)
            if label:
                crypto_seen.add(label)
            values = {
                _clean_audit_value(asset.get("name")),
                _clean_audit_value(asset.get("symbol")),
                _clean_audit_value(asset.get("coin_id")),
            }
            if values & _SUSPICIOUS_EXTERNAL_CANDIDATES:
                suspicious.append(label or str(asset))
    line = (
        "entity_audit: "
        f"external_entities_seen={len(external_seen)} · "
        f"crypto_candidates_seen={len(crypto_seen)} · "
        f"suspicious_external_as_candidate={len(suspicious)}"
    )
    if suspicious:
        line += " · examples=" + ", ".join(dict.fromkeys(suspicious[:5]))
    return [line]


def _candidate_asset_rows(row: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    out: list[Mapping[str, Any]] = []
    for field in ("crypto_candidate_assets", "validated_candidate_assets", "suggested_candidate_assets", "rejected_candidate_assets"):
        for asset in row.get(field) or []:
            if isinstance(asset, Mapping):
                out.append(asset)
    if not out:
        for symbol in row.get("candidate_symbols") or []:
            if str(symbol or "").strip():
                out.append({"symbol": str(symbol).strip().upper(), "source": "candidate_symbols"})
    return out


def _clean_audit_value(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().replace("-", " ").split())


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
