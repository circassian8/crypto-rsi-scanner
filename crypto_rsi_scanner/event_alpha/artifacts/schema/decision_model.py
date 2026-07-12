"""Schema fields and semantic checks for Crypto Radar Decision Model v2."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


DECISION_MODEL_VERSION = "crypto_radar_decision_model_v2"
ALLOWED_THESIS_ORIGINS = ("market_led", "catalyst_led", "technical_led", "macro_led", "mixed")
ALLOWED_DIRECTIONAL_BIASES = ("long", "fade_short_review", "risk", "neutral")
ALLOWED_CATALYST_STATUSES = ("confirmed", "plausible", "unknown", "not_required", "disproven")
ALLOWED_CONFIDENCE_BANDS = ("diagnostic", "exploratory", "actionable", "high_confidence")
ALLOWED_TIMING_STATES = ("early", "active", "extended", "exhausted", "scheduled", "stale")
ALLOWED_TRADABILITY_STATUSES = ("good", "acceptable", "poor", "blocked")
ALLOWED_RADAR_ROUTES = (
    "actionable_watch", "high_confidence_watch", "rapid_market_anomaly",
    "fade_exhaustion_review", "calendar_risk", "diagnostic",
)

FIELDS = (
    "decision_model_version", "decision_model_enabled", "thesis_origin",
    "directional_bias", "catalyst_status", "confidence_band", "timing_state",
    "tradability_status", "radar_route", "radar_route_reason", "radar_actionable",
    "actionability_score", "evidence_confidence_score", "risk_score",
    "actionability_score_components", "evidence_confidence_score_components",
    "risk_score_components", "actionability_penalty_components", "decision_hard_blockers",
    "decision_soft_penalties", "decision_warnings", "decision_missing_data",
    "why_still_worth_reviewing", "radar_what_confirms", "radar_what_invalidates",
    "actionability_score_cohort", "anomaly_type",
)
TYPES = {
    "decision_model_version": "str", "decision_model_enabled": "bool",
    "thesis_origin": "str", "directional_bias": "str", "catalyst_status": "str",
    "confidence_band": "str", "timing_state": "str", "tradability_status": "str",
    "radar_route": "str", "radar_route_reason": "str", "radar_actionable": "bool", "actionability_score": "float",
    "evidence_confidence_score": "float", "risk_score": "float",
    "actionability_score_components": "dict", "evidence_confidence_score_components": "dict",
    "risk_score_components": "dict", "actionability_penalty_components": "dict",
    "decision_hard_blockers": "list", "decision_soft_penalties": "list",
    "decision_warnings": "list", "decision_missing_data": "list",
    "why_still_worth_reviewing": "list", "radar_what_confirms": "list",
    "radar_what_invalidates": "list",
    "actionability_score_cohort": "str", "anomaly_type": "str",
}
ENUMS = {
    "thesis_origin": ALLOWED_THESIS_ORIGINS,
    "directional_bias": ALLOWED_DIRECTIONAL_BIASES,
    "catalyst_status": ALLOWED_CATALYST_STATUSES,
    "confidence_band": ALLOWED_CONFIDENCE_BANDS,
    "timing_state": ALLOWED_TIMING_STATES,
    "tradability_status": ALLOWED_TRADABILITY_STATUSES,
    "radar_route": ALLOWED_RADAR_ROUTES,
}


def validate_contract(row: Mapping[str, Any]) -> list[str]:
    """Fail closed on malformed explicit v2 rows without touching legacy rows."""

    if str(row.get("decision_model_version") or "") != DECISION_MODEL_VERSION:
        return ["unsupported_decision_model_version"]
    required = (
        "decision_model_enabled", "thesis_origin", "directional_bias", "catalyst_status",
        "confidence_band", "timing_state", "tradability_status", "radar_route",
        "radar_route_reason", "radar_actionable", "actionability_score",
        "evidence_confidence_score", "risk_score", "actionability_score_components",
        "evidence_confidence_score_components", "risk_score_components",
        "actionability_penalty_components", "decision_hard_blockers",
        "decision_soft_penalties", "decision_missing_data", "decision_warnings",
        "why_still_worth_reviewing", "radar_what_confirms", "radar_what_invalidates",
        "actionability_score_cohort",
    )
    errors = [
        f"decision_model_missing_field:{field}"
        for field in required
        if field not in row or row.get(field) is None or isinstance(row.get(field), str) and not str(row.get(field)).strip()
    ]
    if not isinstance(row.get("decision_model_enabled"), bool):
        errors.append("decision_model_invalid_type:decision_model_enabled")
    if not isinstance(row.get("radar_actionable"), bool):
        errors.append("decision_model_invalid_type:radar_actionable")
    for field, allowed in ENUMS.items():
        if str(row.get(field) or "") not in allowed:
            errors.append(f"decision_model_invalid_enum:{field}")
    for field in (
        "actionability_score_components", "evidence_confidence_score_components",
        "risk_score_components", "actionability_penalty_components",
    ):
        if not isinstance(row.get(field), Mapping):
            errors.append(f"decision_model_invalid_type:{field}")
    for field in (
        "decision_hard_blockers", "decision_soft_penalties", "decision_missing_data",
        "decision_warnings", "why_still_worth_reviewing", "radar_what_confirms",
        "radar_what_invalidates",
    ):
        if not _is_sequence(row.get(field)):
            errors.append(f"decision_model_invalid_type:{field}")
    if row.get("decision_model_enabled") is True:
        for field in (
            "actionability_score_components", "evidence_confidence_score_components",
            "risk_score_components",
        ):
            if isinstance(row.get(field), Mapping) and not row.get(field):
                errors.append(f"decision_model_empty_transparency_field:{field}")
        for field in (
            "decision_warnings", "why_still_worth_reviewing", "radar_what_confirms",
            "radar_what_invalidates",
        ):
            if _is_sequence(row.get(field)) and not tuple(row.get(field) or ()):
                errors.append(f"decision_model_empty_transparency_field:{field}")
    for field in ("actionability_score", "evidence_confidence_score", "risk_score"):
        try:
            score = float(row.get(field))
        except (TypeError, ValueError):
            errors.append(f"decision_model_invalid_score:{field}")
            continue
        if not 0.0 <= score <= 100.0:
            errors.append(f"decision_model_score_out_of_range:{field}")
    if row.get("radar_actionable") is True:
        if row.get("decision_hard_blockers"):
            errors.append("decision_model_actionable_with_hard_blocker")
        if str(row.get("tradability_status") or "") not in {"good", "acceptable"}:
            errors.append("decision_model_actionable_not_tradable")
        if str(row.get("confidence_band") or "") not in {"actionable", "high_confidence"}:
            errors.append("decision_model_actionable_band_mismatch")
    if row.get("thesis_origin") == "market_led" and row.get("catalyst_status") == "unknown":
        warnings = {
            item
            for field in ("decision_warnings", "decision_soft_penalties")
            for item in _items(row.get(field))
        }
        if not any("catalyst" in item.casefold() and "unknown" in item.casefold() for item in warnings):
            errors.append("decision_model_unknown_catalyst_warning_missing")
    return errors


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Iterable) and not isinstance(value, (str, bytes, Mapping))


def _items(value: Any) -> tuple[str, ...]:
    if value in (None, "", [], {}, ()):
        return ()
    if isinstance(value, str):
        return tuple(item.strip() for item in value.replace(";", ",").split(",") if item.strip())
    if isinstance(value, Mapping):
        return tuple(str(item) for item in value.values())
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return tuple(str(item) for item in value if str(item))
    return (str(value),)


__all__ = (
    "ALLOWED_CATALYST_STATUSES", "ALLOWED_CONFIDENCE_BANDS", "ALLOWED_DIRECTIONAL_BIASES",
    "ALLOWED_RADAR_ROUTES", "ALLOWED_THESIS_ORIGINS", "ALLOWED_TIMING_STATES",
    "ALLOWED_TRADABILITY_STATUSES", "DECISION_MODEL_VERSION", "ENUMS", "FIELDS", "TYPES",
    "validate_contract",
)
