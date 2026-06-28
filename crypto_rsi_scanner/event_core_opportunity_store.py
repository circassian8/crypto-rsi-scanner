"""Profile-scoped canonical CoreOpportunity JSONL artifacts.

The store is research-only. It records the final post-refresh, quality-gated
operator view so daily briefs, near-miss reports, cards, audits, and doctor
checks do not independently recompute conflicting opportunity state.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import event_core_opportunities


EVENT_CORE_OPPORTUNITY_STORE_SCHEMA_VERSION = "event_core_opportunity_store_v1"


@dataclass(frozen=True)
class EventCoreOpportunityStoreConfig:
    path: Path


@dataclass(frozen=True)
class EventCoreOpportunityStoreWriteResult:
    path: Path
    attempted: bool
    success: bool
    rows_written: int = 0
    block_reason: str | None = None


@dataclass(frozen=True)
class EventCoreOpportunityStoreReadResult:
    path: Path
    rows_read: int
    rows: list[dict[str, Any]]
    total_rows_read: int = 0
    latest_run_id: str | None = None
    latest_run_rows_available: int = 0
    filters: dict[str, Any] = field(default_factory=dict)


def write_core_opportunities(
    rows: Iterable[Any],
    *,
    cfg: EventCoreOpportunityStoreConfig,
    now: datetime | None = None,
    run_id: str | None = None,
    profile: str | None = None,
    run_mode: str | None = None,
    artifact_namespace: str | None = None,
    card_paths: Iterable[str | Path] = (),
) -> EventCoreOpportunityStoreWriteResult:
    """Append canonical core opportunity rows to a local JSONL artifact."""
    observed = _as_utc(now or datetime.now(timezone.utc)).isoformat()
    card_by_core = _card_path_by_core_id(card_paths)
    opportunities = event_core_opportunities.aggregate_core_opportunities(rows)
    out_rows = [
        _row_from_core_opportunity(
            item,
            generated_at=observed,
            run_id=run_id,
            profile=profile,
            run_mode=run_mode,
            artifact_namespace=artifact_namespace,
            card_path=card_by_core.get(item.core_opportunity_id),
        )
        for item in opportunities
    ]
    path = Path(cfg.path).expanduser()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not out_rows:
            return EventCoreOpportunityStoreWriteResult(path=path, attempted=True, success=True, rows_written=0)
        with path.open("a", encoding="utf-8") as fh:
            for row in out_rows:
                fh.write(json.dumps(_json_ready(row), sort_keys=True, separators=(",", ":")))
                fh.write("\n")
        return EventCoreOpportunityStoreWriteResult(path=path, attempted=True, success=True, rows_written=len(out_rows))
    except Exception as exc:  # noqa: BLE001 - research artifacts must fail soft.
        return EventCoreOpportunityStoreWriteResult(
            path=path,
            attempted=True,
            success=False,
            rows_written=0,
            block_reason=f"{type(exc).__name__}: {exc}",
        )


def load_core_opportunities(
    path: str | Path,
    *,
    limit: int | None = None,
    latest_run: bool = False,
    run_id: str | None = None,
    include_legacy: bool = True,
) -> EventCoreOpportunityStoreReadResult:
    """Load canonical core rows newest-first, tolerating old/bad rows."""
    p = Path(path).expanduser()
    all_rows = [
        row for row in _read_jsonl(p)
        if row.get("row_type") == "event_core_opportunity"
    ]
    all_rows.sort(key=lambda row: str(row.get("generated_at") or row.get("created_at") or ""), reverse=True)
    latest_id = _latest_run_id(all_rows)
    filtered = list(all_rows)
    if not include_legacy:
        filtered = [row for row in filtered if str(row.get("schema_version") or "") == EVENT_CORE_OPPORTUNITY_STORE_SCHEMA_VERSION]
    if run_id:
        filtered = [row for row in filtered if str(row.get("run_id") or "") == str(run_id)]
    elif latest_run and latest_id:
        filtered = [row for row in filtered if str(row.get("run_id") or "") == latest_id]
    if limit is not None and limit > 0:
        filtered = filtered[:limit]
    return EventCoreOpportunityStoreReadResult(
        path=p,
        rows_read=len(filtered),
        rows=filtered,
        total_rows_read=len(all_rows),
        latest_run_id=latest_id,
        latest_run_rows_available=sum(1 for row in all_rows if str(row.get("run_id") or "") == latest_id) if latest_id else 0,
        filters={
            "latest_run": bool(latest_run),
            "run_id": run_id,
            "include_legacy": bool(include_legacy),
            "limit": limit,
        },
    )


def core_opportunities_from_rows(rows: Iterable[Mapping[str, Any]]) -> tuple[event_core_opportunities.CoreOpportunity, ...]:
    """Convert stored canonical rows back into CoreOpportunity objects."""
    return event_core_opportunities.aggregate_core_opportunities(rows)


def merge_core_opportunity_verdict(
    initial: Mapping[str, Any] | None,
    market_refresh: Mapping[str, Any] | None = None,
    evidence_acquisition: Mapping[str, Any] | None = None,
    support_rows: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Return the deterministic final state from compatible candidate rows.

    Higher-quality final core rows win over stale supporting rows. Diagnostics
    are retained as support metadata by the aggregator and cannot downgrade the
    canonical visible opportunity.
    """
    rows: list[Mapping[str, Any]] = []
    for row in (initial, market_refresh, evidence_acquisition):
        if isinstance(row, Mapping) and row:
            rows.append(row)
    rows.extend(row for row in support_rows if isinstance(row, Mapping) and row)
    opportunities = event_core_opportunities.aggregate_core_opportunities(rows)
    if not opportunities:
        return {}
    item = opportunities[0]
    return _row_from_core_opportunity(
        item,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def format_core_opportunity_store_write_result(result: EventCoreOpportunityStoreWriteResult) -> str:
    return "\n".join([
        "Event core opportunities updated: "
        f"{result.path} rows={result.rows_written} success={str(result.success).lower()}"
        + (f" block={result.block_reason}" if result.block_reason else "")
    ])


def _row_from_core_opportunity(
    item: event_core_opportunities.CoreOpportunity,
    *,
    generated_at: str,
    run_id: str | None = None,
    profile: str | None = None,
    run_mode: str | None = None,
    artifact_namespace: str | None = None,
    card_path: str | Path | None = None,
) -> dict[str, Any]:
    primary = dict(item.primary_row)
    support = [dict(row) for row in item.supporting_rows]
    diagnostics = [dict(row) for row in item.diagnostic_rows]
    all_rows = [primary, *support, *diagnostics]
    market_before = _best_float(all_rows, ("market_confirmation_before", "market_confirmation_score_before"))
    market_after = _best_float(all_rows, ("market_confirmation_after", "market_confirmation_score_after", "market_confirmation_score"))
    evidence_before = _best_float(all_rows, ("evidence_quality_before", "evidence_quality_score_before"))
    evidence_after = _best_float(all_rows, ("evidence_quality_after", "evidence_quality_score_after", "evidence_quality_score"))
    initial_level = _first_text(all_rows, ("initial_opportunity_level", "opportunity_level_before", "opportunity_level_pre_refresh")) or item.opportunity_level
    initial_score = _first_float(all_rows, ("initial_opportunity_score", "opportunity_score_before", "opportunity_score_pre_refresh"))
    post_level = _first_text(all_rows, ("post_refresh_opportunity_level", "refreshed_opportunity_level", "opportunity_level_after_market_refresh")) or item.opportunity_level
    post_score = _first_float(all_rows, ("post_refresh_opportunity_score", "refreshed_opportunity_score", "opportunity_score_after_market_refresh"))
    support_ids = _row_ids(support)
    diagnostic_ids = _row_ids(diagnostics)
    return {
        "schema_version": EVENT_CORE_OPPORTUNITY_STORE_SCHEMA_VERSION,
        "row_type": "event_core_opportunity",
        "run_id": run_id,
        "profile": profile,
        "run_mode": run_mode,
        "artifact_namespace": artifact_namespace,
        "core_opportunity_id": item.core_opportunity_id,
        "symbol": item.symbol,
        "coin_id": item.coin_id,
        "incident_id": item.incident_id,
        "canonical_incident_name": item.canonical_incident_name,
        "candidate_role": item.candidate_role,
        "primary_impact_path": item.primary_impact_path,
        "primary_hypothesis_id": _first_text([primary], ("hypothesis_id", "primary_hypothesis_id")),
        "supporting_hypothesis_ids": list(item.supporting_hypothesis_ids),
        "supporting_categories": list(item.supporting_categories),
        "supporting_impact_paths": list(item.supporting_impact_paths),
        "supporting_evidence_quotes": list(item.supporting_evidence_quotes),
        "supporting_row_ids": support_ids,
        "diagnostic_row_ids": diagnostic_ids,
        "diagnostic_row_count": item.diagnostic_row_count,
        "hidden_diagnostic_count": item.diagnostic_row_count,
        "source_noise_control_count": item.source_noise_control_count,
        "quality_capped_support_count": item.quality_capped_supporting_rows,
        "initial_opportunity_level": initial_level,
        "initial_opportunity_score": initial_score if initial_score is not None else item.opportunity_score_final,
        "market_refresh_attempted": _any_truthy(all_rows, ("market_refresh_attempted", "targeted_market_refresh_attempted")),
        "market_refresh_success": _any_truthy(all_rows, ("market_refresh_success", "targeted_market_refresh_success")),
        "market_context_freshness_status": _first_text(all_rows, ("market_context_freshness_status",)),
        "market_context_source": _first_text(all_rows, ("market_context_source",)),
        "market_context_observed_at": _first_text(all_rows, ("market_context_observed_at",)),
        "market_context_age_hours": _first_float(all_rows, ("market_context_age_hours",)),
        "market_context_freshness_cap_applied": _any_truthy(all_rows, ("market_context_freshness_cap_applied",)),
        "market_context_data_quality": _first_text(all_rows, ("market_context_data_quality",)),
        "market_confirmation_before": market_before,
        "market_confirmation_after": market_after,
        "main_frame_type": _first_text(all_rows, ("main_frame_type",)),
        "main_frame_role": _first_text(all_rows, ("main_frame_role",)),
        "main_frame_subject": _first_text(all_rows, ("main_frame_subject",)),
        "main_frame_actor": _first_text(all_rows, ("main_frame_actor",)),
        "main_frame_object": _first_text(all_rows, ("main_frame_object",)),
        "main_frame_evidence_quote": _first_text(all_rows, ("main_frame_evidence_quote",)),
        "frame_status": _first_text(all_rows, ("frame_status", "catalyst_frame_status")),
        "selected_main_catalyst_reason": _first_text(all_rows, ("selected_main_catalyst_reason",)),
        "rule_predicted_impact_path": _first_text(all_rows, ("rule_predicted_impact_path",)),
        "llm_predicted_main_frame_type": _first_text(all_rows, ("llm_predicted_main_frame_type",)),
        "frame_rule_disagreement": _first_value(all_rows, ("frame_rule_disagreement",)),
        "negated_frame_ids": _first_list(all_rows, ("negated_frame_ids",)),
        "corrective_frame_ids": _first_list(all_rows, ("corrective_frame_ids",)),
        "frame_summary": _first_list(all_rows, ("frame_summary",)),
        "evidence_acquisition_attempted": _any_truthy(all_rows, ("evidence_acquisition_attempted", "source_acquisition_attempted")),
        "evidence_acquisition_status": _first_text(all_rows, ("evidence_acquisition_status", "acquisition_status", "source_acquisition_status")),
        "evidence_quality_before": evidence_before,
        "evidence_quality_after": evidence_after,
        "post_refresh_opportunity_level": post_level,
        "post_refresh_opportunity_score": post_score if post_score is not None else item.opportunity_score_final,
        "final_opportunity_level": item.opportunity_level,
        "final_opportunity_score": item.opportunity_score_final,
        "opportunity_level": item.opportunity_level,
        "opportunity_score_final": item.opportunity_score_final,
        "final_state_after_quality_gate": item.final_state_after_quality_gate,
        "final_route_after_quality_gate": item.final_route_after_quality_gate,
        "final_verdict_source": _first_text(all_rows, ("final_verdict_source", "opportunity_verdict_source", "verdict_source")) or "core_opportunity_merge",
        "final_verdict_reason": _first_text(all_rows, ("final_verdict_reason", "quality_gate_block_reason", "route_reason", "opportunity_verdict_reason")),
        "why_opportunity_visible": item.why_opportunity_visible,
        "why_other_rows_hidden": item.why_other_rows_hidden,
        "card_path": str(card_path) if card_path else None,
        "feedback_target": item.core_opportunity_id,
        "generated_at": generated_at,
    }


def _card_path_by_core_id(paths: Iterable[str | Path]) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        from . import event_research_cards
    except Exception:  # noqa: BLE001 - optional presentation helper.
        return out
    for value in paths:
        path = Path(value)
        core_id = event_research_cards.card_core_opportunity_id(path)
        if core_id:
            out.setdefault(core_id, str(path))
    return out


def _row_ids(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    ids: list[str] = []
    for row in rows:
        value = _first_text([row], ("row_id", "hypothesis_id", "alert_id", "watchlist_key", "key", "event_id"))
        if value:
            ids.append(value)
    return list(dict.fromkeys(ids))


def _first_text(rows: Iterable[Mapping[str, Any]], keys: tuple[str, ...]) -> str | None:
    for row in rows:
        components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else row.get("score_components")
        for key in keys:
            value = row.get(key)
            if value in (None, "", [], {}, ()):
                value = components.get(key) if isinstance(components, Mapping) else None
            text = str(value or "").strip()
            if text:
                return text
    return None


def _first_float(rows: Iterable[Mapping[str, Any]], keys: tuple[str, ...]) -> float | None:
    for row in rows:
        components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else row.get("score_components")
        for key in keys:
            value = row.get(key)
            if value in (None, "", [], {}, ()):
                value = components.get(key) if isinstance(components, Mapping) else None
            parsed = _float_or_none(value)
            if parsed is not None:
                return parsed
    return None


def _first_value(rows: Iterable[Mapping[str, Any]], keys: tuple[str, ...]) -> Any:
    for row in rows:
        components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else row.get("score_components")
        for key in keys:
            value = row.get(key)
            if value in (None, "", [], {}, ()):
                value = components.get(key) if isinstance(components, Mapping) else None
            if value not in (None, "", [], {}, ()):
                return value
    return None


def _first_list(rows: Iterable[Mapping[str, Any]], keys: tuple[str, ...]) -> list[Any]:
    value = _first_value(rows, keys)
    if value in (None, "", [], {}, ()):
        return []
    if isinstance(value, Mapping):
        return [dict(value)]
    if isinstance(value, str):
        return [item.strip() for item in value.split(";") if item.strip()]
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return list(value)
    return [value]


def _best_float(rows: Iterable[Mapping[str, Any]], keys: tuple[str, ...]) -> float | None:
    values = [
        parsed
        for row in rows
        for parsed in (_first_float([row], keys),)
        if parsed is not None
    ]
    return max(values) if values else None


def _any_truthy(rows: Iterable[Mapping[str, Any]], keys: tuple[str, ...]) -> bool:
    for row in rows:
        components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else row.get("score_components")
        for key in keys:
            value = row.get(key)
            if value in (None, "", [], {}, ()):
                value = components.get(key) if isinstance(components, Mapping) else None
            if _truthy(value):
                return True
    return False


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "y"}
    return bool(value)


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _latest_run_id(rows: Iterable[Mapping[str, Any]]) -> str | None:
    for row in rows:
        value = str(row.get("run_id") or "").strip()
        if value:
            return value
    return None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                text = line.strip()
                if not text:
                    continue
                try:
                    raw = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if isinstance(raw, Mapping):
                    rows.append(dict(raw))
    except OSError:
        return []
    return rows


def _json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return _as_utc(value).isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item) for item in value]
    return value
