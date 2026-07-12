"""Immutable Outcome Eligibility v1 contract values and scalar helpers.

This internal module keeps the public ``outcome_eligibility`` facade focused on
identity joins and calibration decisions.  Constants are imported and
re-exported by that facade so existing callers retain the same public API.
"""

from __future__ import annotations

import math
import unicodedata
from datetime import datetime, timezone
from typing import Any


OUTCOME_ELIGIBILITY_CONTRACT_VERSION = 1
OUTCOME_DATA_SOURCES = frozenset(
    {"observed_market_prices", "pending_observation", "synthetic_fixture"}
)
OUTCOME_IDENTITY_FIELDS = (
    "run_id",
    "profile",
    "artifact_namespace",
    "candidate_id",
    "core_opportunity_id",
    "observed_at",
)
OUTCOME_HORIZONS = ("15m", "1h", "4h", "24h", "3d", "7d")
OUTCOME_HORIZON_SECONDS = {
    "15m": 15 * 60,
    "1h": 60 * 60,
    "4h": 4 * 60 * 60,
    "24h": 24 * 60 * 60,
    "3d": 3 * 24 * 60 * 60,
    "7d": 7 * 24 * 60 * 60,
}
OUTCOME_ENTRY_PRICE_MAX_STALENESS_SECONDS = 24 * 60 * 60
OUTCOME_MATURITY_STATUSES = frozenset({"pending", "matured", "missing_data"})
OUTCOME_PROVENANCE_STATUSES = frozenset(
    {"synthetic_fixture", "observed_market_prices", "missing"}
)
OUTCOME_HORIZON_METADATA_FIELDS = (
    "due_at",
    "price_observed_at",
    "price_at_horizon",
    "price_source",
    "price_observation_id",
    "maturity_status",
    "provenance_status",
)
OUTCOME_DIRECTION_BY_LANE = {
    "EARLY_LONG_RESEARCH": 1,
    "CONFIRMED_LONG_RESEARCH": 1,
    "FADE_SHORT_REVIEW": -1,
    "RISK_ONLY": -1,
}
OUTCOME_ALLOWED_LANES = frozenset(
    {*OUTCOME_DIRECTION_BY_LANE, "UNCONFIRMED_RESEARCH", "DIAGNOSTIC"}
)
OUTCOME_PRIMARY_HORIZON_BY_LANE = {
    "EARLY_LONG_RESEARCH": "3d",
    "CONFIRMED_LONG_RESEARCH": "24h",
    "FADE_SHORT_REVIEW": "24h",
    "RISK_ONLY": "24h",
    "UNCONFIRMED_RESEARCH": "24h",
    "DIAGNOSTIC": "24h",
}
OUTCOME_VALIDATION_STATUSES = frozenset(
    {"validated", "invalidated/noise", "inconclusive"}
)
OUTCOME_VALIDATED_LABELS = frozenset(
    {
        "continuation_good",
        "early_good",
        "fade_review_good",
        "risk_validated",
        "useful",
    }
)
OUTCOME_VALIDATED_STATUS_ALIASES = frozenset(
    {"continued", "continuation", "validated"}
)
OUTCOME_REQUIRED_TRUE_SAFETY_FIELDS = (
    "research_only",
    "no_send_rehearsal",
)
OUTCOME_REQUIRED_FALSE_SAFETY_FIELDS = (
    "sent",
    "normal_rsi_signal_written",
    "triggered_fade_created",
    "paper_trade_created",
    "trade_created",
)
OUTCOME_OPTIONAL_FALSE_SAFETY_FIELDS = (
    "alert_created",
    "created_alert",
    "execution_created",
    "execution_enabled",
    "live_trading_enabled",
    "normal_rsi_routing_enabled",
    "notification_send_enabled",
    "paper_trading_enabled",
    "send_enabled",
    "send_requested",
    "trade_execution_enabled",
    "trading_enabled",
)
OUTCOME_ZERO_SAFETY_FIELDS = (
    "alerts_created",
    "executions_created",
    "normal_rsi_signal_rows_written",
    "notifications_sent",
    "orders_created",
    "paper_trades_created",
    "send_items_attempted",
    "send_items_delivered",
    "strict_alerts_created",
    "telegram_sends",
    "trades_created",
    "triggered_fades_created",
)
OUTCOME_RETURN_RECOMPUTE_REL_TOLERANCE = 1e-9
OUTCOME_RETURN_RECOMPUTE_ABS_TOLERANCE = 1e-12
CANDIDATE_AUTHORITY_CONTRACT = {
    "row_type": "event_integrated_radar_candidate",
    "schema_id": "integrated_radar_candidate_v1",
    "schema_version": "event_alpha_schema_v1",
}
CORE_AUTHORITY_CONTRACT = {
    "row_type": "event_core_opportunity",
    "schema_id": "core_opportunity_v1",
    "schema_version": "event_core_opportunity_store_v1",
}
OUTCOME_INELIGIBLE_REASONS = frozenset(
    {
        "ambiguous_outcome_identity",
        "candidate_authority_contract_invalid",
        "core_authority_contract_invalid",
        "core_authority_generated_in_future",
        "diagnostic_lane",
        "duplicate_horizon_price_observation_id",
        "duplicate_outcome_identity",
        "horizon_metadata_contract_invalid",
        "horizon_return_contract_invalid",
        "identity_mismatch",
        "invalid_calibration_eligible_flag",
        "invalid_calibration_ineligible_reasons",
        "invalid_exact_identity_text",
        "invalid_observation_price",
        "invalid_outcome_data_source",
        "invalid_outcome_lane",
        "legacy_outcome_contract",
        "missing_exact_identity",
        "missing_observation_price",
        "missing_observation_price_id",
        "missing_observation_price_observed_at",
        "missing_observation_price_provenance",
        "missing_observation_price_source",
        "missing_outcome_evaluated_at",
        "missing_primary_horizon",
        "missing_primary_horizon_metadata",
        "outcome_identity_contract_invalid",
        "outcome_evaluated_in_future",
        "observation_price_after_candidate",
        "observation_price_after_evaluation",
        "observation_price_stale",
        "outcome_safety_contract_invalid",
        "outcome_validation_claim_direction_mismatch",
        "primary_horizon_due_in_future",
        "primary_horizon_due_mismatch",
        "primary_horizon_lane_mismatch",
        "primary_horizon_missing_due_at",
        "primary_horizon_missing_price_observed_at",
        "primary_horizon_missing_provenance",
        "primary_horizon_not_mature",
        "primary_horizon_pending",
        "primary_horizon_price_after_evaluation",
        "primary_horizon_price_before_due",
        "primary_horizon_price_lag_exceeded",
        "primary_horizon_return_invalid",
        "primary_horizon_return_mismatch",
        "horizon_exit_price_invalid",
        "horizon_exit_price_missing",
        "horizon_price_lineage_contract_invalid",
        "horizon_price_observation_id_missing",
        "horizon_price_source_missing",
        "horizon_return_recompute_mismatch",
        "synthetic_fixture",
        "unmatched_outcome_identity",
    }
)
OUTCOME_ELIGIBILITY_MARKERS = (
    "outcome_eligibility_contract_version",
    "outcome_data_source",
    "outcome_identity",
    "outcome_identity_key",
    "outcome_evaluated_at",
    "observation_price_provenance_status",
    "calibration_eligible",
    "calibration_ineligible_reasons",
    "primary_horizon",
    "horizon_metadata",
)
OUTCOME_ELIGIBILITY_REQUIRED_FIELDS = tuple(
    dict.fromkeys(
        (
            *OUTCOME_ELIGIBILITY_MARKERS,
            *OUTCOME_IDENTITY_FIELDS,
            "price_at_observation",
            "observation_price_source",
            "observation_price_id",
            "observation_price_observed_at",
            "primary_horizon_return",
        )
    )
)
OUTCOME_ATTRIBUTION_FIELDS = (
    "symbol",
    "coin_id",
    "opportunity_type",
    "playbook_type",
    "effective_playbook_type",
    "provider",
    "providers",
    "source_provider",
    "source_providers",
    "source_origin",
    "source_origins",
    "source_pack",
    "source_packs",
    "source_pack_id",
    "source_class",
    "source_strength",
    "market_state_class",
    "crowding_class",
    "thesis_origin",
    "primary_thesis_origin",
    "thesis_origins",
    "directional_bias",
    "catalyst_status",
    "confidence_band",
    "actionability_score_cohort",
    "evidence_confidence_score_cohort",
    "risk_score_cohort",
    "anomaly_type",
    "radar_route",
    "timing_state",
    "market_phase",
    "tradability_status",
)


def finite_number(value: Any) -> float | None:
    """Return a finite built-in numeric value as ``float``; reject coercion."""

    if type(value) not in (int, float):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def parse_aware_time(value: Any) -> datetime | None:
    """Parse an aware datetime and normalize it to UTC."""

    try:
        if isinstance(value, datetime):
            parsed = value
        else:
            text = str(value or "").strip()
            if not text:
                return None
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None


def iso_utc(value: datetime) -> str:
    """Render an aware datetime in canonical UTC ISO form."""

    return value.astimezone(timezone.utc).isoformat()


def identity_text(value: Any) -> str:
    """Return a literal string identity component without coercion."""

    return value if type(value) is str else ""


def canonical_identity_text(value: Any) -> bool:
    """Return whether an identity component is exact, normalized, and safe."""

    if type(value) is not str or not value or value != value.strip():
        return False
    if unicodedata.normalize("NFC", value) != value:
        return False
    return not any(
        unicodedata.category(character).startswith("C")
        or unicodedata.category(character) in {"Zl", "Zp"}
        for character in value
    )


__all__ = (
    "CANDIDATE_AUTHORITY_CONTRACT",
    "CORE_AUTHORITY_CONTRACT",
    "OUTCOME_ALLOWED_LANES",
    "OUTCOME_ATTRIBUTION_FIELDS",
    "OUTCOME_DATA_SOURCES",
    "OUTCOME_DIRECTION_BY_LANE",
    "OUTCOME_ELIGIBILITY_CONTRACT_VERSION",
    "OUTCOME_ELIGIBILITY_MARKERS",
    "OUTCOME_ELIGIBILITY_REQUIRED_FIELDS",
    "OUTCOME_ENTRY_PRICE_MAX_STALENESS_SECONDS",
    "OUTCOME_HORIZONS",
    "OUTCOME_HORIZON_METADATA_FIELDS",
    "OUTCOME_HORIZON_SECONDS",
    "OUTCOME_IDENTITY_FIELDS",
    "OUTCOME_INELIGIBLE_REASONS",
    "OUTCOME_MATURITY_STATUSES",
    "OUTCOME_OPTIONAL_FALSE_SAFETY_FIELDS",
    "OUTCOME_PRIMARY_HORIZON_BY_LANE",
    "OUTCOME_PROVENANCE_STATUSES",
    "OUTCOME_REQUIRED_FALSE_SAFETY_FIELDS",
    "OUTCOME_REQUIRED_TRUE_SAFETY_FIELDS",
    "OUTCOME_RETURN_RECOMPUTE_ABS_TOLERANCE",
    "OUTCOME_RETURN_RECOMPUTE_REL_TOLERANCE",
    "OUTCOME_VALIDATED_LABELS",
    "OUTCOME_VALIDATED_STATUS_ALIASES",
    "OUTCOME_VALIDATION_STATUSES",
    "OUTCOME_ZERO_SAFETY_FIELDS",
    "canonical_identity_text",
    "finite_number",
    "identity_text",
    "iso_utc",
    "parse_aware_time",
)
