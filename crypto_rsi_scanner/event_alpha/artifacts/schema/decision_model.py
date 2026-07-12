"""Schema fields and semantic checks for Crypto Radar Decision Model v2."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
import math
from typing import Any


DECISION_MODEL_VERSION = "crypto_radar_decision_model_v2"
ALLOWED_THESIS_ORIGINS = (
    "market_led", "catalyst_led", "technical_led", "derivatives_led", "onchain_led",
    "fundamental_led", "macro_led", "mixed",
)
ALLOWED_DIRECTIONAL_BIASES = ("long", "fade_short_review", "risk", "neutral")
ALLOWED_CATALYST_STATUSES = ("confirmed", "plausible", "unknown", "not_required", "disproven")
ALLOWED_CONFIDENCE_BANDS = ("diagnostic", "exploratory", "actionable", "high_confidence")
ALLOWED_TIMING_STATES = ("early", "active", "extended", "exhausted", "scheduled", "stale")
ALLOWED_TRADABILITY_STATUSES = ("good", "acceptable", "poor", "blocked")
ALLOWED_SPREAD_STATUSES = (
    "verified_good", "verified_acceptable", "verified_wide", "unavailable", "stale",
)
ALLOWED_MARKET_PHASES = (
    "emerging", "breakout", "acceleration", "active", "extended", "exhaustion", "reversal",
)
ALLOWED_PREFERRED_HORIZONS = ("intraday", "1d_3d", "3d_7d", "scheduled_window")
ALLOWED_RADAR_ROUTES = (
    "dashboard_watch", "actionable_watch", "high_confidence_watch", "rapid_market_anomaly",
    "fade_exhaustion_review", "risk_watch", "calendar_risk", "diagnostic",
)

FIELDS = (
    "decision_model_version", "decision_model_enabled", "thesis_origin",
    "primary_thesis_origin", "thesis_origins",
    "directional_bias", "catalyst_status", "confidence_band", "timing_state",
    "tradability_status", "spread_status", "radar_route", "radar_route_reason", "radar_actionable",
    "actionability_score", "evidence_confidence_score", "risk_score",
    "urgency_score", "market_phase", "preferred_horizon", "expires_at", "chase_risk_score",
    "actionability_score_components", "evidence_confidence_score_components",
    "risk_score_components", "actionability_penalty_components", "decision_hard_blockers",
    "decision_soft_penalties", "decision_warnings", "decision_missing_data",
    "why_still_worth_reviewing", "radar_what_confirms", "radar_what_invalidates",
    "actionability_score_cohort", "anomaly_type",
    "decision_source_side_effect_safety_failed", "decision_source_secret_safety_failed",
    "decision_source_path_safety_failed",
)
TYPES = {
    "decision_model_version": "str", "decision_model_enabled": "bool",
    "thesis_origin": "str", "primary_thesis_origin": "str", "thesis_origins": "list",
    "directional_bias": "str", "catalyst_status": "str",
    "confidence_band": "str", "timing_state": "str", "tradability_status": "str",
    "spread_status": "str", "radar_route": "str", "radar_route_reason": "str",
    "radar_actionable": "bool", "actionability_score": "float",
    "evidence_confidence_score": "float", "risk_score": "float",
    "urgency_score": "float", "market_phase": "str", "preferred_horizon": "str",
    "expires_at": "str", "chase_risk_score": "float",
    "actionability_score_components": "dict", "evidence_confidence_score_components": "dict",
    "risk_score_components": "dict", "actionability_penalty_components": "dict",
    "decision_hard_blockers": "list", "decision_soft_penalties": "list",
    "decision_warnings": "list", "decision_missing_data": "list",
    "why_still_worth_reviewing": "list", "radar_what_confirms": "list",
    "radar_what_invalidates": "list",
    "actionability_score_cohort": "str", "anomaly_type": "str",
    "decision_source_side_effect_safety_failed": "bool",
    "decision_source_secret_safety_failed": "bool",
    "decision_source_path_safety_failed": "bool",
}
ENUMS = {
    "thesis_origin": ALLOWED_THESIS_ORIGINS,
    "primary_thesis_origin": ALLOWED_THESIS_ORIGINS,
    "directional_bias": ALLOWED_DIRECTIONAL_BIASES,
    "catalyst_status": ALLOWED_CATALYST_STATUSES,
    "confidence_band": ALLOWED_CONFIDENCE_BANDS,
    "timing_state": ALLOWED_TIMING_STATES,
    "tradability_status": ALLOWED_TRADABILITY_STATUSES,
    "spread_status": ALLOWED_SPREAD_STATUSES,
    "market_phase": ALLOWED_MARKET_PHASES,
    "preferred_horizon": ALLOWED_PREFERRED_HORIZONS,
    "radar_route": ALLOWED_RADAR_ROUTES,
}


def validate_contract(row: Mapping[str, Any]) -> list[str]:
    """Fail closed on malformed explicit v2 rows without touching legacy rows."""

    return _validate_contract(row)


def _validate_contract(row: Mapping[str, Any]) -> list[str]:
    """Validate one explicit contract behind the stable public entrypoint."""

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
    extended_fields = (
        "primary_thesis_origin", "thesis_origins", "spread_status", "urgency_score",
        "market_phase", "preferred_horizon", "expires_at", "chase_risk_score",
    )
    extended_contract = any(field in row for field in extended_fields)
    if extended_contract:
        errors.extend(
            f"decision_model_missing_field:{field}"
            for field in extended_fields
            if field not in row or field != "expires_at" and row.get(field) is None
        )
    if not isinstance(row.get("decision_model_enabled"), bool):
        errors.append("decision_model_invalid_type:decision_model_enabled")
    if not isinstance(row.get("radar_actionable"), bool):
        errors.append("decision_model_invalid_type:radar_actionable")
    for field, allowed in ENUMS.items():
        if field in extended_fields and not extended_contract:
            continue
        if str(row.get(field) or "") not in allowed:
            errors.append(f"decision_model_invalid_enum:{field}")
    for field in (
        "actionability_score_components", "evidence_confidence_score_components",
        "risk_score_components", "actionability_penalty_components",
    ):
        if not isinstance(row.get(field), Mapping):
            errors.append(f"decision_model_invalid_type:{field}")
    if extended_contract:
        origins = _items(row.get("thesis_origins"))
        if not origins:
            errors.append("decision_model_empty_transparency_field:thesis_origins")
        elif any(origin not in ALLOWED_THESIS_ORIGINS for origin in origins) or (
            row.get("decision_model_enabled") is True and "mixed" in origins
        ):
            errors.append("decision_model_invalid_thesis_origins")
        elif len(origins) != len(set(origins)):
            errors.append("decision_model_duplicate_thesis_origins")
        elif origins[0] != str(row.get("primary_thesis_origin") or ""):
            errors.append("decision_model_primary_thesis_origin_order_mismatch")
    for field in (
        "decision_hard_blockers", "decision_soft_penalties", "decision_missing_data",
        "decision_warnings", "why_still_worth_reviewing", "radar_what_confirms",
        "radar_what_invalidates",
    ):
        if not _is_sequence(row.get(field)):
            errors.append(f"decision_model_invalid_type:{field}")
    source_safety_blockers = {
        "decision_source_side_effect_safety_failed": "research_safety_invariant_failed",
        "decision_source_secret_safety_failed": "secret_safety_failed",
        "decision_source_path_safety_failed": "operator_path_safety_failed",
    }
    hard_blockers = set(_items(row.get("decision_hard_blockers")))
    for field, blocker in source_safety_blockers.items():
        if field in row and not isinstance(row.get(field), bool):
            errors.append(f"decision_model_invalid_type:{field}")
        if row.get(field) is True and blocker not in hard_blockers:
            errors.append(f"decision_model_source_safety_attestation_without_blocker:{field}")
    if row.get("decision_model_enabled") is True:
        if row.get("research_only") is not True:
            errors.append("decision_model_research_only_required")
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
    errors.extend(_validate_scores_and_expiry(row, extended_contract=extended_contract))
    if row.get("radar_actionable") is True:
        if row.get("decision_hard_blockers"):
            errors.append("decision_model_actionable_with_hard_blocker")
        if str(row.get("tradability_status") or "") not in {"good", "acceptable"}:
            errors.append("decision_model_actionable_not_tradable")
        if extended_contract and str(row.get("spread_status") or "") not in {"verified_good", "verified_acceptable"}:
            errors.append("decision_model_actionable_spread_unverified")
        if str(row.get("confidence_band") or "") not in {"actionable", "high_confidence"}:
            errors.append("decision_model_actionable_band_mismatch")
    elif str(row.get("confidence_band") or "") in {"actionable", "high_confidence"}:
        errors.append("decision_model_non_actionable_band_mismatch")
    route = str(row.get("radar_route") or "")
    if route in {"actionable_watch", "high_confidence_watch", "rapid_market_anomaly"} and row.get("radar_actionable") is not True:
        errors.append("decision_model_watch_route_not_actionable")
    if route in {"dashboard_watch", "risk_watch", "calendar_risk"} and row.get("radar_actionable") is not False:
        errors.append("decision_model_observational_route_marked_actionable")
    if route == "high_confidence_watch" and str(row.get("confidence_band") or "") != "high_confidence":
        errors.append("decision_model_high_confidence_route_band_mismatch")
    if row.get("decision_hard_blockers") and route != "diagnostic":
        errors.append("decision_model_hard_blocker_non_diagnostic_route")
    if extended_contract:
        has_calendar = _has_calendar_evidence(row)
        if route == "calendar_risk" and not has_calendar:
            errors.append("decision_model_calendar_risk_without_calendar_evidence")
        if route == "risk_watch" and has_calendar:
            errors.append("decision_model_risk_watch_with_calendar_evidence")
    if row.get("thesis_origin") == "market_led" and row.get("catalyst_status") == "unknown":
        warnings = {
            item
            for field in ("decision_warnings", "decision_soft_penalties")
            for item in _items(row.get(field))
        }
        if not any("catalyst" in item.casefold() and "unknown" in item.casefold() for item in warnings):
            errors.append("decision_model_unknown_catalyst_warning_missing")
    if extended_contract:
        errors.extend(_validate_market_return_units(row))
    return errors


def _validate_scores_and_expiry(
    row: Mapping[str, Any],
    *,
    extended_contract: bool,
) -> list[str]:
    errors: list[str] = []
    score_fields = ["actionability_score", "evidence_confidence_score", "risk_score"]
    if extended_contract:
        score_fields.extend(("urgency_score", "chase_risk_score"))
    for field in score_fields:
        try:
            score = float(row.get(field))
        except (TypeError, ValueError):
            errors.append(f"decision_model_invalid_score:{field}")
            continue
        if not 0.0 <= score <= 100.0:
            errors.append(f"decision_model_score_out_of_range:{field}")
    expires_at = row.get("expires_at")
    expiry = _aware_timestamp(expires_at) if expires_at not in (None, "") else None
    if expires_at not in (None, "") and expiry is None:
        errors.append("decision_model_invalid_timestamp:expires_at")
    evaluated_at = next(
        (
            _aware_timestamp(row.get(field))
            for field in ("decision_evaluated_at", "evaluated_at", "generated_at", "observed_at")
            if row.get(field) not in (None, "")
        ),
        None,
    )
    if expiry is not None and evaluated_at is not None and expiry <= evaluated_at and row.get("radar_actionable") is True:
        errors.append("decision_model_expired_idea_actionable")
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


def _aware_timestamp(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _has_calendar_evidence(row: Mapping[str, Any]) -> bool:
    for field in (
        "unified_calendar_event", "calendar_event", "scheduled_catalyst_event", "unlock_event",
    ):
        if isinstance(row.get(field), Mapping) and bool(row.get(field)):
            return True
    nearby = row.get("nearby_calendar_events") or row.get("calendar_events")
    if _is_sequence(nearby) and any(isinstance(item, Mapping) and bool(item) for item in nearby):
        return True
    return _aware_timestamp(row.get("scheduled_at")) is not None


def _validate_market_return_units(row: Mapping[str, Any]) -> list[str]:
    return_fields = (
        "return_5m", "return_15m", "return_1h", "return_4h", "return_24h", "return_72h",
        "return_7d", "relative_return_vs_btc", "relative_return_vs_eth",
        "relative_return_vs_sector", "relative_return_vs_btc_1h",
        "relative_return_vs_btc_4h", "relative_return_vs_btc_24h",
        "relative_return_vs_eth_1h", "relative_return_vs_eth_4h",
        "relative_return_vs_eth_24h", "open_interest_delta", "open_interest_delta_1h",
        "open_interest_delta_4h", "open_interest_delta_24h", "dex_volume_change",
        "dex_liquidity_change",
    )
    errors: list[str] = []
    for snapshot_field in ("latest_market_snapshot", "market_snapshot", "market_state_snapshot"):
        snapshot = row.get(snapshot_field)
        if not isinstance(snapshot, Mapping):
            continue
        values = tuple(field for field in return_fields if snapshot.get(field) not in (None, ""))
        if not values:
            continue
        common_unit = _return_unit(snapshot.get("return_unit"))
        raw_overrides = next(
            (
                snapshot.get(field)
                for field in ("return_units", "return_unit_by_field", "field_return_units")
                if field in snapshot
            ),
            None,
        )
        if raw_overrides is not None and not isinstance(raw_overrides, Mapping):
            errors.append(f"decision_model_invalid_return_unit_metadata:{snapshot_field}")
            overrides: Mapping[str, Any] = {}
        else:
            overrides = raw_overrides or {}
        for field in overrides:
            if str(field) not in return_fields:
                errors.append(f"decision_model_unknown_return_unit_field:{snapshot_field}:{field}")
        for field in values:
            unit = _return_unit(overrides.get(field)) if field in overrides else common_unit
            if unit is None:
                errors.append(f"decision_model_return_unit_missing:{snapshot_field}:{field}")
                continue
            value = _finite_number(snapshot.get(field))
            if value is None:
                errors.append(f"decision_model_invalid_return_value:{snapshot_field}:{field}")
                continue
            if unit == "fraction" and abs(value) > 3.0:
                errors.append(f"decision_model_implausible_fraction_return:{snapshot_field}:{field}")
            if unit == "percent_points" and abs(value) > 300.0:
                errors.append(f"decision_model_implausible_percent_return:{snapshot_field}:{field}")
    return list(dict.fromkeys(errors))


def _return_unit(value: object) -> str | None:
    text = str(value or "").strip().casefold()
    if text in {"fraction", "fractions", "decimal", "raw_fraction"}:
        return "fraction"
    if text in {"percent", "percentage", "percent_points", "percentage_points", "pct", "pct_points"}:
        return "percent_points"
    return None


def _finite_number(value: object) -> float | None:
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


__all__ = (
    "ALLOWED_CATALYST_STATUSES", "ALLOWED_CONFIDENCE_BANDS", "ALLOWED_DIRECTIONAL_BIASES",
    "ALLOWED_MARKET_PHASES", "ALLOWED_PREFERRED_HORIZONS", "ALLOWED_RADAR_ROUTES",
    "ALLOWED_SPREAD_STATUSES", "ALLOWED_THESIS_ORIGINS", "ALLOWED_TIMING_STATES",
    "ALLOWED_TRADABILITY_STATUSES", "DECISION_MODEL_VERSION", "ENUMS", "FIELDS",
    "TYPES", "validate_contract",
)
