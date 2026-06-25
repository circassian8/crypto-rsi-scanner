"""Export proposed Event Alpha signal-quality benchmark cases from artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import event_alpha_quality_fields


@dataclass(frozen=True)
class EventAlphaSignalQualityExportResult:
    path: Path
    cases_written: int
    reasons: tuple[str, ...]


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
        feedback = feedback_by_key.get(_key(row))
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
        key = str(row.get("key") or row.get("alert_key") or row.get("alert_id") or "")
        if key:
            out[key] = row
    return out


def _case_reason(row: Mapping[str, Any], *, feedback: Mapping[str, Any] | None) -> str | None:
    label = str((feedback or {}).get("label") or (feedback or {}).get("feedback") or "").lower()
    if label == "useful":
        return "useful_feedback_positive_case"
    if label == "junk":
        return "junk_feedback_negative_case"
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
    return {
        "case_id": _safe_case_id(row, reason),
        "reason_to_add_case": reason,
        "raw_evidence_summary": row.get("event_name") or row.get("latest_event_name") or row.get("title") or row.get("hypothesis_id") or "artifact row",
        "candidate_symbol": symbol,
        "candidate_coin_id": coin_id,
        "external_asset": row.get("external_asset"),
        "source_metadata": {
            "source": row.get("source") or row.get("latest_source"),
            "source_class": components.get("source_class"),
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
        "expected_current_decision": row.get("route") or row.get("tier") or row.get("latest_tier") or components.get("opportunity_level"),
        "suggested_expected_label": (feedback or {}).get("label") or (feedback or {}).get("feedback"),
        "feedback": dict(feedback or {}),
    }


def _safe_case_id(row: Mapping[str, Any], reason: str) -> str:
    raw = str(row.get("alert_id") or row.get("alert_key") or row.get("key") or row.get("hypothesis_id") or row.get("symbol") or "case")
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in raw).strip("_")[:60] or "case"
    return f"{cleaned}_{reason}"


def _key(row: Mapping[str, Any]) -> str:
    return str(row.get("alert_key") or row.get("alert_id") or row.get("key") or row.get("hypothesis_id") or "")


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
