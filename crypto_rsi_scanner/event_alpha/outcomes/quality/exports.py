"""Split implementation for `crypto_rsi_scanner/event_alpha/outcomes/quality.py` (exports)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping
import crypto_rsi_scanner.event_alpha.artifacts.alert_store as event_alpha_alert_store
import crypto_rsi_scanner.event_alpha.outcomes.quality_fields as event_alpha_quality_fields
import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
from ...artifacts import reason_text as event_alpha_reason_text
from ...artifacts import context as event_alpha_artifacts
from ...radar import core_opportunities as event_core_opportunities
from ...radar import opportunity_verdict as event_opportunity_verdict
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import crypto_rsi_scanner.event_alpha.outcomes.quality_fields as event_alpha_quality_fields
from ...artifacts import run_ledger as event_alpha_run_ledger
from datetime import datetime, timezone
from types import SimpleNamespace
import crypto_rsi_scanner.event_alpha.radar.claim_semantics as event_claim_semantics
import crypto_rsi_scanner.event_alpha.radar.evidence_quality as event_evidence_quality
import crypto_rsi_scanner.event_alpha.radar.incident_graph as event_incident_graph
import crypto_rsi_scanner.event_alpha.radar.impact_path_validator as event_impact_path_validator
import crypto_rsi_scanner.event_alpha.radar.market_confirmation as event_market_confirmation
from crypto_rsi_scanner.event_core.models import NormalizedEvent, RawDiscoveredEvent
from ...radar import incidents as event_incident_store
from .models import *  # noqa: F403

def export_signal_quality_cases(
    path: str | Path,
    *,
    alert_rows: Iterable[Mapping[str, Any]] = (),
    feedback_rows: Iterable[Mapping[str, Any]] = (),
    missed_rows: Iterable[Mapping[str, Any]] = (),
    hypothesis_rows: Iterable[Mapping[str, Any]] = (),
    generated_at: datetime | None = None,
) -> EventAlphaSignalQualityExportResult:
    """Write proposed benchmark cases from local artifacts only."""
    feedback_by_key = _feedback_by_key(feedback_rows)
    cases: list[dict[str, Any]] = []
    reasons: list[str] = []
    for row in alert_rows:
        if not isinstance(row, Mapping):
            continue
        feedback = _matching_feedback(row, feedback_by_key)
        reason = _case_reason(row, feedback=feedback)
        if not reason:
            continue
        cases.append(_case_from_row(row, reason=reason, feedback=feedback))
        reasons.append(reason)
    for row in hypothesis_rows:
        if not isinstance(row, Mapping):
            continue
        if str(row.get("opportunity_level") or "") in {"local_only", "exploratory"}:
            cases.append(_case_from_row(row, reason="local_only_weak_hypothesis"))
            reasons.append("local_only_weak_hypothesis")
    for row in missed_rows:
        if not isinstance(row, Mapping):
            continue
        cases.append(_case_from_row(row, reason="missed_opportunity_recall_case"))
        reasons.append("missed_opportunity_recall_case")
    deduped = _dedupe_cases(cases)
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "event_alpha_signal_quality_proposed_cases_v1",
        "generated_at": (generated_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(),
        "research_only": True,
        "cases": deduped,
    }
    target.write_text(json.dumps(_json_ready(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return EventAlphaSignalQualityExportResult(
        path=target,
        cases_written=len(deduped),
        reasons=tuple(dict.fromkeys(reasons)),
    )
def format_signal_quality_export_result(result: EventAlphaSignalQualityExportResult) -> str:
    return "\n".join([
        "=" * 76,
        "EVENT ALPHA SIGNAL-QUALITY CASE EXPORT (research-only)",
        "=" * 76,
        f"path: {result.path}",
        f"cases_written: {result.cases_written}",
        "reasons: " + (", ".join(result.reasons) or "none"),
        "Canonical fixtures were not modified. No sends, trades, paper rows, live RSI rows, or watchlist state were written.",
    ])
def _feedback_by_key(rows: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    out: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        for key in _row_keys(row):
            out[key] = row
    return out
def _matching_feedback(row: Mapping[str, Any], feedback_by_key: Mapping[str, Mapping[str, Any]]) -> Mapping[str, Any] | None:
    return next((feedback_by_key[key] for key in _row_keys(row) if key in feedback_by_key), None)
def _case_reason(row: Mapping[str, Any], *, feedback: Mapping[str, Any] | None) -> str | None:
    label = str((feedback or {}).get("label") or (feedback or {}).get("feedback") or "").lower()
    if label == "useful":
        return "useful_feedback_positive_case"
    if label == "junk":
        return "junk_feedback_negative_case"
    if label == "watch":
        return "watch_feedback_borderline_case"
    if str(row.get("opportunity_level") or "") in {"local_only", "exploratory"}:
        return "local_only_weak_case"
    if row.get("rejected_candidate_assets") or row.get("rejected_validation_samples"):
        return "high_scoring_rejected_candidate"
    if str(row.get("tier") or "") in {"RADAR_DIGEST", "WATCHLIST", "HIGH_PRIORITY_WATCH"}:
        return "delivered_alert_candidate"
    return None
def _case_from_row(row: Mapping[str, Any], *, reason: str, feedback: Mapping[str, Any] | None = None) -> dict[str, Any]:
    components = event_alpha_quality_fields.quality_components(row)
    symbol = row.get("symbol") or row.get("validated_symbol")
    coin_id = row.get("coin_id") or row.get("validated_coin_id")
    feedback_label = (feedback or {}).get("label") or (feedback or {}).get("feedback")
    expected_level = _expected_level_for_case(row, reason=reason, feedback_label=feedback_label)
    return {
        "case_id": _safe_case_id(row, reason),
        "reason_to_add_case": reason,
        "raw_evidence_summary": row.get("event_name") or row.get("latest_event_name") or row.get("title") or row.get("hypothesis_id") or "artifact row",
        "candidate_symbol": symbol,
        "candidate_coin_id": coin_id,
        "core_opportunity_id": row.get("core_opportunity_id") or (feedback or {}).get("core_opportunity_id"),
        "feedback_target": (feedback or {}).get("feedback_target") or (feedback or {}).get("target") or row.get("feedback_target"),
        "external_asset": row.get("external_asset"),
        "source_metadata": {
            "source": row.get("source") or row.get("latest_source"),
            "source_class": components.get("source_class"),
            "source_provider": row.get("source_provider") or (feedback or {}).get("source_provider"),
            "source_domain": row.get("source_domain") or (feedback or {}).get("source_domain"),
            "source_pack": row.get("source_pack") or (feedback or {}).get("source_pack"),
            "evidence_specificity": components.get("evidence_specificity"),
        },
        "impact_path": {
            "impact_path_type": components.get("impact_path_type"),
            "impact_path_strength": components.get("impact_path_strength"),
            "candidate_role": components.get("candidate_role"),
        },
        "market_confirmation": {
            "market_confirmation_score": components.get("market_confirmation_score"),
            "market_confirmation_level": components.get("market_confirmation_level"),
        },
        "evidence_quality": {
            "evidence_quality_score": components.get("evidence_quality_score"),
            "source_class": components.get("source_class"),
            "evidence_specificity": components.get("evidence_specificity"),
        },
        "opportunity": {
            "opportunity_score_final": components.get("opportunity_score_final"),
            "opportunity_level": components.get("opportunity_level"),
            "opportunity_verdict_reasons": components.get("opportunity_verdict_reasons") or [],
            "why_local_only": components.get("why_local_only"),
            "why_not_watchlist": components.get("why_not_watchlist"),
        },
        "expected_opportunity_level": expected_level,
        "expected_route_behavior": _expected_route_behavior(expected_level),
        "expected_current_decision": row.get("route") or row.get("tier") or row.get("latest_tier") or components.get("opportunity_level"),
        "suggested_expected_label": feedback_label,
        "why_this_should_become_eval_case": _why_eval_case(reason, feedback=feedback),
        "feedback": dict(feedback or {}),
    }
def _expected_level_for_case(row: Mapping[str, Any], *, reason: str, feedback_label: object) -> str:
    label = str(feedback_label or "").lower()
    if label == "junk" or "negative" in reason:
        return "local_only"
    if label == "useful" or "positive" in reason:
        return str(row.get("opportunity_level") or row.get("final_opportunity_level") or "validated_digest")
    if label == "watch":
        return "watchlist"
    if "missed" in reason:
        return "watchlist_or_validated_digest"
    return str(row.get("opportunity_level") or row.get("final_opportunity_level") or "review")
def _expected_route_behavior(level: str) -> str:
    if level in {"local_only", "exploratory"}:
        return "store_only_or_local_report"
    if level in {"watchlist", "watchlist_or_validated_digest"}:
        return "watchlist_if_quality_gates_pass"
    if level == "high_priority":
        return "high_priority_if_quality_gates_pass"
    return "research_digest_if_quality_gates_pass"
def _why_eval_case(reason: str, *, feedback: Mapping[str, Any] | None) -> str:
    note = str((feedback or {}).get("notes") or "").strip()
    if note:
        return f"{reason}: {note}"
    if reason == "missed_opportunity_recall_case":
        return "missed opportunity should test source/resolver/quality recall"
    if reason == "junk_feedback_negative_case":
        return "operator marked this as junk; preserve or tighten rejection behavior"
    if reason == "useful_feedback_positive_case":
        return "operator marked this as useful; preserve or improve promotion behavior"
    if reason == "watch_feedback_borderline_case":
        return "operator marked this as watch; keep as threshold/borderline eval"
    return reason
def _safe_case_id(row: Mapping[str, Any], reason: str) -> str:
    raw = str(row.get("alert_id") or row.get("alert_key") or row.get("key") or row.get("hypothesis_id") or row.get("symbol") or "case")
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in raw).strip("_")[:60] or "case"
    return f"{cleaned}_{reason}"
def _key(row: Mapping[str, Any]) -> str:
    return str(row.get("alert_key") or row.get("alert_id") or row.get("key") or row.get("hypothesis_id") or "")
def _row_keys(row: Mapping[str, Any]) -> tuple[str, ...]:
    keys: list[str] = []
    for field in (
        "key",
        "target",
        "feedback_target",
        "core_opportunity_id",
        "alert_key",
        "alert_id",
        "card_id",
        "hypothesis_id",
        "incident_id",
        "symbol",
        "coin_id",
        "asset_symbol",
        "asset_coin_id",
        "validated_symbol",
        "validated_coin_id",
    ):
        value = str(row.get(field) or "").strip()
        if not value:
            continue
        keys.append(value)
        if value.startswith("ea:"):
            keys.append(value[3:])
        else:
            keys.append(f"ea:{value}")
    return tuple(dict.fromkeys(keys))
def _dedupe_cases(cases: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for case in cases:
        key = str(case.get("case_id") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(dict(case))
    return out
def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value
