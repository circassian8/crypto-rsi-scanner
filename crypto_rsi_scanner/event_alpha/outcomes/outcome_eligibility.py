"""Canonical outcome identity, maturity, provenance, and calibration firewall."""

from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping


OUTCOME_ELIGIBILITY_CONTRACT_VERSION = 1
OUTCOME_DATA_SOURCES = frozenset({"observed_market_prices", "synthetic_fixture"})
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
    "directional_bias",
    "catalyst_status",
    "confidence_band",
    "actionability_score_cohort",
    "anomaly_type",
    "radar_route",
    "timing_state",
    "tradability_status",
)


def has_outcome_eligibility_marker(row: Mapping[str, Any]) -> bool:
    return any(field in row for field in OUTCOME_ELIGIBILITY_MARKERS)


def canonical_outcome_identity(row: Mapping[str, Any]) -> dict[str, str]:
    """Return the canonical six-field identity mapping, preserving missing values as empty."""

    return {field: _identity_text(row.get(field)) for field in OUTCOME_IDENTITY_FIELDS}


def canonical_join_identity(
    row: Mapping[str, Any],
    *,
    allow_integrated_candidate_alias: bool = False,
) -> tuple[str, ...] | None:
    values = canonical_outcome_identity(row)
    if allow_integrated_candidate_alias and not values["candidate_id"]:
        values["candidate_id"] = _identity_text(row.get("integrated_candidate_id"))
    if not all(_canonical_identity_text(value) for value in values.values()):
        return None
    return tuple(values[field] for field in OUTCOME_IDENTITY_FIELDS)


def canonical_outcome_identity_key(identity: Mapping[str, Any]) -> str:
    canonical = {
        field: _identity_text(identity.get(field))
        for field in OUTCOME_IDENTITY_FIELDS
    }
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def valid_candidate_authority(row: Mapping[str, Any]) -> bool:
    """Require one canonical v1 integrated-candidate authority row."""

    return (
        canonical_join_identity(row) is not None
        and all(row.get(field) == value for field, value in CANDIDATE_AUTHORITY_CONTRACT.items())
        and row.get("research_only") is True
        and _authority_safety_contract_valid(row)
        and _authority_schema_valid(row, "integrated_radar_candidate_v1")
    )


def valid_core_authority(row: Mapping[str, Any]) -> bool:
    """Require one canonical v1 Core Opportunity authority row."""

    return (
        _core_join_key(row) is not None
        and all(row.get(field) == value for field, value in CORE_AUTHORITY_CONTRACT.items())
        and row.get("research_only") is True
        and parse_aware_time(row.get("generated_at")) is not None
        and _authority_safety_contract_valid(row)
        and _authority_schema_valid(row, "core_opportunity_v1")
    )


def build_outcome_identity_fields(candidate: Mapping[str, Any]) -> dict[str, Any]:
    identity = canonical_outcome_identity(candidate)
    return {
        **identity,
        "outcome_identity": identity,
        "outcome_identity_key": canonical_outcome_identity_key(identity),
    }


def primary_horizon_for_lane(lane: Any) -> str | None:
    """Return the canonical primary horizon for one literal research lane."""

    return OUTCOME_PRIMARY_HORIZON_BY_LANE.get(lane) if type(lane) is str else None


def build_synthetic_horizon_metadata(
    *,
    observed_at: Any,
    evaluated_at: Any,
) -> dict[str, dict[str, Any]]:
    """Build truthful fixture metadata without pretending synthetic returns are prices."""

    observed = parse_aware_time(observed_at)
    evaluated = parse_aware_time(evaluated_at)
    metadata: dict[str, dict[str, Any]] = {}
    for horizon in OUTCOME_HORIZONS:
        due = (
            observed + timedelta(seconds=OUTCOME_HORIZON_SECONDS[horizon])
            if observed is not None
            else None
        )
        maturity = (
            "pending"
            if due is not None and evaluated is not None and evaluated < due
            else "missing_data"
        )
        metadata[horizon] = {
            "due_at": iso_utc(due) if due is not None else None,
            "price_observed_at": None,
            "price_at_horizon": None,
            "price_source": None,
            "price_observation_id": None,
            "maturity_status": maturity,
            "provenance_status": "synthetic_fixture",
        }
    return metadata


def calibration_ineligibility_reasons(row: Mapping[str, Any]) -> tuple[str, ...]:
    """Compute the exact closed row-local reasons, excluding join-time ambiguity."""

    reasons: set[str] = set()
    if type(row.get("outcome_eligibility_contract_version")) is not int or row.get(
        "outcome_eligibility_contract_version"
    ) != OUTCOME_ELIGIBILITY_CONTRACT_VERSION:
        reasons.add("legacy_outcome_contract")

    data_source = row.get("outcome_data_source")
    if type(data_source) is not str or data_source not in OUTCOME_DATA_SOURCES:
        reasons.add("invalid_outcome_data_source")
    elif data_source == "synthetic_fixture":
        reasons.add("synthetic_fixture")

    identity = canonical_outcome_identity(row)
    if not all(identity.values()):
        reasons.add("missing_exact_identity")
    elif not all(_canonical_identity_text(value) for value in identity.values()):
        reasons.add("invalid_exact_identity_text")
    nested_identity = row.get("outcome_identity")
    if (
        not isinstance(nested_identity, Mapping)
        or set(nested_identity) != set(OUTCOME_IDENTITY_FIELDS)
        or any(type(nested_identity.get(field)) is not str for field in OUTCOME_IDENTITY_FIELDS)
        or dict(nested_identity) != identity
        or row.get("outcome_identity_key") != canonical_outcome_identity_key(identity)
    ):
        reasons.add("outcome_identity_contract_invalid")

    price = finite_number(row.get("price_at_observation"))
    if row.get("price_at_observation") is None:
        reasons.add("missing_observation_price")
    elif price is None or price <= 0:
        reasons.add("invalid_observation_price")
    if row.get("observation_price_provenance_status") != "observed_market_prices":
        reasons.add("missing_observation_price_provenance")
    observed = parse_aware_time(identity.get("observed_at"))
    evaluated = parse_aware_time(row.get("outcome_evaluated_at"))
    if data_source == "observed_market_prices":
        if not _canonical_identity_text(row.get("observation_price_source")):
            reasons.add("missing_observation_price_source")
        if not _canonical_identity_text(row.get("observation_price_id")):
            reasons.add("missing_observation_price_id")
        entry_observed_at = parse_aware_time(row.get("observation_price_observed_at"))
        if entry_observed_at is None:
            reasons.add("missing_observation_price_observed_at")
        else:
            if observed is None or entry_observed_at > observed:
                reasons.add("observation_price_after_candidate")
            elif (observed - entry_observed_at).total_seconds() > OUTCOME_ENTRY_PRICE_MAX_STALENESS_SECONDS:
                reasons.add("observation_price_stale")
            if evaluated is not None and entry_observed_at > evaluated:
                reasons.add("observation_price_after_evaluation")

    if evaluated is None:
        reasons.add("missing_outcome_evaluated_at")
    lane = row.get("opportunity_type")
    if type(lane) is not str or lane not in OUTCOME_ALLOWED_LANES:
        reasons.add("invalid_outcome_lane")
    elif lane == "DIAGNOSTIC":
        reasons.add("diagnostic_lane")
    if not _outcome_safety_contract_valid(row):
        reasons.add("outcome_safety_contract_invalid")

    primary = row.get("primary_horizon")
    metadata = row.get("horizon_metadata")
    if type(primary) is not str or primary not in OUTCOME_HORIZONS:
        reasons.add("missing_primary_horizon")
        primary = None
    expected_primary = primary_horizon_for_lane(lane)
    if primary is not None and expected_primary is not None and primary != expected_primary:
        reasons.add("primary_horizon_lane_mismatch")
    if not _horizon_metadata_contract_valid(metadata, observed_at=observed, evaluated_at=evaluated):
        reasons.add("horizon_metadata_contract_invalid")
    if not _horizon_return_contract_valid(
        row,
        metadata=metadata,
        data_source=data_source,
    ):
        reasons.add("horizon_return_contract_invalid")
    reasons.update(
        _horizon_price_lineage_reasons(
            row,
            metadata=metadata,
            data_source=data_source,
        )
    )
    primary_metadata = metadata.get(primary) if isinstance(metadata, Mapping) and primary else None
    if not isinstance(primary_metadata, Mapping):
        reasons.add("missing_primary_horizon_metadata")
    else:
        _add_primary_metadata_reasons(
            reasons,
            primary=str(primary),
            metadata=primary_metadata,
            observed_at=observed,
            evaluated_at=evaluated,
        )
    primary_return = finite_number(row.get("primary_horizon_return"))
    if primary_return is None:
        reasons.add("primary_horizon_return_invalid")
    elif primary is not None and not _primary_return_mappings_match(
        row,
        primary=str(primary),
        primary_return=primary_return,
    ):
        reasons.add("primary_horizon_return_mismatch")
    if _row_claims_validated(row) and deterministic_validation_status(row) != "validated":
        reasons.add("outcome_validation_claim_direction_mismatch")
    return tuple(sorted(reasons))


def effective_calibration_eligible(
    row: Mapping[str, Any],
    *,
    additional_reasons: Iterable[str] = (),
    evaluated_at: Any = None,
) -> bool:
    eligible, _reasons = effective_calibration_state(
        row,
        additional_reasons=additional_reasons,
        evaluated_at=evaluated_at,
    )
    return eligible


def effective_calibration_state(
    row: Mapping[str, Any],
    *,
    additional_reasons: Iterable[str] = (),
    evaluated_at: Any = None,
) -> tuple[bool, tuple[str, ...]]:
    computed = set(calibration_ineligibility_reasons(row))
    declared = row.get("calibration_ineligible_reasons")
    declared_valid = (
        isinstance(declared, list)
        and all(type(reason) is str and reason in OUTCOME_INELIGIBLE_REASONS for reason in declared)
        and declared == sorted(set(declared))
    )
    if not declared_valid or tuple(declared) != tuple(sorted(computed)):
        computed.add("invalid_calibration_ineligible_reasons")
    flag = row.get("calibration_eligible")
    if type(flag) is not bool or flag is not (not calibration_ineligibility_reasons(row)):
        computed.add("invalid_calibration_eligible_flag")
    for reason in additional_reasons:
        computed.add(
            reason
            if type(reason) is str and reason in OUTCOME_INELIGIBLE_REASONS
            else "ambiguous_outcome_identity"
        )
    trusted_evaluated_at = (
        datetime.now(timezone.utc) if evaluated_at is None else evaluated_at
    )
    external_evaluated = parse_aware_time(trusted_evaluated_at)
    if external_evaluated is None:
        computed.add("missing_outcome_evaluated_at")
    else:
        persisted_evaluated = parse_aware_time(row.get("outcome_evaluated_at"))
        if persisted_evaluated is not None and persisted_evaluated > external_evaluated:
            computed.add("outcome_evaluated_in_future")
        _add_external_clock_reasons(computed, row, external_evaluated)
    reasons = tuple(sorted(computed))
    return flag is True and not reasons, reasons


def validate_contract(row: Mapping[str, Any]) -> list[str]:
    """Return stable schema-adapter errors; unmarked legacy rows remain readable."""

    if not has_outcome_eligibility_marker(row):
        return []
    errors: list[str] = []
    missing = [field for field in OUTCOME_ELIGIBILITY_REQUIRED_FIELDS if field not in row]
    if missing:
        errors.extend(f"outcome_eligibility_missing_field:{field}" for field in missing)
    computed = calibration_ineligibility_reasons(row)
    declared = row.get("calibration_ineligible_reasons")
    if not isinstance(declared, list) or declared != list(computed):
        errors.append("outcome_eligibility_reasons_mismatch")
    expected_flag = not computed
    if type(row.get("calibration_eligible")) is not bool or row.get(
        "calibration_eligible"
    ) is not expected_flag:
        errors.append("outcome_calibration_eligible_mismatch")
    return errors


def partition_calibration_outcomes(
    rows: Iterable[Mapping[str, Any]],
    *,
    evaluated_at: Any = None,
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...], dict[str, int]]:
    trusted_evaluated_at = (
        datetime.now(timezone.utc) if evaluated_at is None else evaluated_at
    )
    materialized_rows = [dict(row) for row in rows if isinstance(row, Mapping)]
    identity_counts = Counter(
        identity
        for row in materialized_rows
        if (identity := canonical_join_identity(row)) is not None
    )
    malformed_alias_counts = Counter(
        alias
        for row in materialized_rows
        if canonical_join_identity(row) is None
        and (alias := _malformed_identity_alias(row)) is not None
    )
    eligible: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter()
    for materialized in materialized_rows:
        identity = canonical_join_identity(materialized)
        duplicate_reasons: tuple[str, ...] = ()
        if identity is not None and identity_counts[identity] > 1:
            duplicate_reasons = ("duplicate_outcome_identity",)
        elif identity is None:
            alias = _malformed_identity_alias(materialized)
            if alias is not None and malformed_alias_counts[alias] > 1:
                duplicate_reasons = ("ambiguous_outcome_identity",)
        is_eligible, reasons = effective_calibration_state(
            materialized,
            additional_reasons=duplicate_reasons,
            evaluated_at=trusted_evaluated_at,
        )
        materialized["calibration_eligible"] = is_eligible
        materialized["calibration_ineligible_reasons"] = list(reasons)
        if is_eligible:
            eligible.append(materialized)
        else:
            excluded.append(materialized)
            reason_counts.update(reasons)
    return tuple(eligible), tuple(excluded), dict(sorted(reason_counts.items()))


def partition_joined_calibration_outcomes(
    outcome_rows: Iterable[Mapping[str, Any]],
    candidate_rows: Iterable[Mapping[str, Any]],
    core_rows: Iterable[Mapping[str, Any]],
    *,
    evaluated_at: Any = None,
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...], dict[str, int]]:
    """Partition only outcomes backed by one exact candidate and one exact core row."""

    outcomes = [dict(row) for row in outcome_rows if isinstance(row, Mapping)]
    candidates = [dict(row) for row in candidate_rows if isinstance(row, Mapping)]
    cores = [dict(row) for row in core_rows if isinstance(row, Mapping)]
    trusted_evaluated_at = (
        datetime.now(timezone.utc) if evaluated_at is None else evaluated_at
    )
    outcomes_by_identity = _group_by_exact_identity(outcomes)
    candidates_by_identity = _group_by_exact_identity(candidates)
    cores_by_key: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for core in cores:
        key = _core_join_key(core)
        if key is not None:
            cores_by_key.setdefault(key, []).append(core)
    candidate_aliases = {
        alias
        for candidate in candidates
        for alias in _loose_identity_aliases(candidate)
    }
    eligible: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter()
    for outcome in outcomes:
        reasons: set[str] = set()
        identity = canonical_join_identity(outcome)
        candidate: Mapping[str, Any] | None = None
        core: Mapping[str, Any] | None = None
        if identity is None:
            reasons.add("ambiguous_outcome_identity")
        else:
            identity_outcomes = outcomes_by_identity.get(identity, ())
            identity_candidates = candidates_by_identity.get(identity, ())
            if len(identity_outcomes) > 1:
                reasons.add("duplicate_outcome_identity")
            if len(identity_candidates) != 1:
                reasons.add(
                    "identity_mismatch"
                    if any(alias in candidate_aliases for alias in _loose_identity_aliases(outcome))
                    else "unmatched_outcome_identity"
                )
                if len(identity_candidates) > 1:
                    reasons.add("ambiguous_outcome_identity")
            else:
                candidate = identity_candidates[0]
                if not valid_candidate_authority(candidate):
                    reasons.add("candidate_authority_contract_invalid")
                matching_cores = cores_by_key.get(_core_join_key(candidate) or (), ())
                if len(matching_cores) != 1:
                    reasons.add(
                        "ambiguous_outcome_identity"
                        if len(matching_cores) > 1
                        else "unmatched_outcome_identity"
                    )
                else:
                    core = matching_cores[0]
                    if not valid_core_authority(core):
                        reasons.add("core_authority_contract_invalid")
                    core_generated_at = parse_aware_time(core.get("generated_at"))
                    external_evaluated_at = parse_aware_time(trusted_evaluated_at)
                    if (
                        core_generated_at is not None
                        and external_evaluated_at is not None
                        and core_generated_at > external_evaluated_at
                    ):
                        reasons.add("core_authority_generated_in_future")
        materialized = dict(outcome)
        if candidate is not None and core is not None:
            for key, value in core.items():
                materialized[f"core_{key}"] = value
            for field in OUTCOME_ATTRIBUTION_FIELDS:
                materialized.pop(field, None)
                value = candidate.get(field)
                if value in (None, "", (), []):
                    value = core.get(field)
                materialized[field] = (
                    value if value not in (None, "", (), []) else "unknown"
                )
        is_eligible, effective_reasons = effective_calibration_state(
            materialized,
            additional_reasons=reasons,
            evaluated_at=trusted_evaluated_at,
        )
        materialized["calibration_eligible"] = is_eligible
        materialized["calibration_ineligible_reasons"] = list(effective_reasons)
        if is_eligible:
            eligible.append(materialized)
        else:
            excluded.append(materialized)
            reason_counts.update(effective_reasons)
    return tuple(eligible), tuple(excluded), dict(sorted(reason_counts.items()))


def primary_horizon_maturation_state(row: Mapping[str, Any]) -> str | None:
    primary = row.get("primary_horizon")
    metadata = row.get("horizon_metadata")
    if type(primary) is not str or primary not in OUTCOME_HORIZONS or not isinstance(metadata, Mapping):
        return None
    primary_metadata = metadata.get(primary)
    if not isinstance(primary_metadata, Mapping):
        return None
    status = primary_metadata.get("maturity_status")
    if status == "matured":
        return "matured"
    if status == "missing_data":
        return "missing_price_data"
    if status == "pending":
        if any(
            isinstance(metadata.get(horizon), Mapping)
            and metadata[horizon].get("maturity_status") == "matured"
            for horizon in OUTCOME_HORIZONS
            if horizon != primary
        ):
            return "partially_matured"
        return "pending"
    return None


def filled_horizon_count(row: Mapping[str, Any]) -> int:
    for key in ("return_by_horizon", "horizons"):
        values = row.get(key)
        if isinstance(values, Mapping):
            return sum(1 for horizon in OUTCOME_HORIZONS if finite_number(values.get(horizon)) is not None)
    return 1 if finite_number(row.get("primary_horizon_return")) is not None else 0


def deterministic_validation_status(row: Mapping[str, Any]) -> str:
    """Grade a mature primary move from canonical lane direction, never labels."""

    lane = row.get("opportunity_type")
    if type(lane) is not str or lane not in OUTCOME_ALLOWED_LANES:
        return "inconclusive"
    direction = OUTCOME_DIRECTION_BY_LANE.get(lane)
    primary_return = finite_number(row.get("primary_horizon_return"))
    if direction is None or primary_return is None:
        return "inconclusive"
    return "validated" if primary_return * direction > 0 else "invalidated/noise"


def finite_number(value: Any) -> float | None:
    if type(value) not in (int, float):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def parse_aware_time(value: Any) -> datetime | None:
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
    return value.astimezone(timezone.utc).isoformat()


def _horizon_metadata_contract_valid(
    value: Any,
    *,
    observed_at: datetime | None,
    evaluated_at: datetime | None,
) -> bool:
    if not isinstance(value, Mapping) or set(value) != set(OUTCOME_HORIZONS):
        return False
    for horizon in OUTCOME_HORIZONS:
        item = value.get(horizon)
        if not isinstance(item, Mapping) or set(item) != set(OUTCOME_HORIZON_METADATA_FIELDS):
            return False
        due = parse_aware_time(item.get("due_at"))
        expected_due = (
            observed_at + timedelta(seconds=OUTCOME_HORIZON_SECONDS[horizon])
            if observed_at is not None
            else None
        )
        if due is None or expected_due is None or due != expected_due:
            return False
        status = item.get("maturity_status")
        provenance = item.get("provenance_status")
        price_time = parse_aware_time(item.get("price_observed_at"))
        exit_price = finite_number(item.get("price_at_horizon"))
        price_source = item.get("price_source")
        price_observation_id = item.get("price_observation_id")
        if status not in OUTCOME_MATURITY_STATUSES or provenance not in OUTCOME_PROVENANCE_STATUSES:
            return False
        if status == "pending" and (
            evaluated_at is None
            or evaluated_at >= due
            or price_time is not None
            or item.get("price_at_horizon") is not None
            or price_source is not None
            or price_observation_id is not None
            or provenance == "observed_market_prices"
        ):
            return False
        if status == "missing_data" and (
            evaluated_at is None
            or evaluated_at < due
            or price_time is not None
            or item.get("price_at_horizon") is not None
            or price_source is not None
            or price_observation_id is not None
            or provenance == "observed_market_prices"
        ):
            return False
        max_lag = min(OUTCOME_HORIZON_SECONDS[horizon], 24 * 60 * 60)
        if status == "matured" and (
            evaluated_at is None
            or evaluated_at < due
            or price_time is None
            or price_time < due
            or price_time > due + timedelta(seconds=max_lag)
            or price_time > evaluated_at
            or exit_price is None
            or exit_price <= 0
            or not _canonical_identity_text(price_source)
            or not _canonical_identity_text(price_observation_id)
            or provenance != "observed_market_prices"
        ):
            return False
    return True


def _add_primary_metadata_reasons(
    reasons: set[str],
    *,
    primary: str,
    metadata: Mapping[str, Any],
    observed_at: datetime | None,
    evaluated_at: datetime | None,
) -> None:
    due = parse_aware_time(metadata.get("due_at"))
    price_time = parse_aware_time(metadata.get("price_observed_at"))
    expected_due = (
        observed_at + timedelta(seconds=OUTCOME_HORIZON_SECONDS[primary])
        if observed_at is not None
        else None
    )
    if due is None:
        reasons.add("primary_horizon_missing_due_at")
    elif expected_due is None or due != expected_due:
        reasons.add("primary_horizon_due_mismatch")
    status = metadata.get("maturity_status")
    if status == "pending":
        reasons.add("primary_horizon_pending")
    elif status != "matured":
        reasons.add("primary_horizon_not_mature")
    if status != "pending" and price_time is None:
        reasons.add("primary_horizon_missing_price_observed_at")
    if status != "pending" and metadata.get("provenance_status") != "observed_market_prices":
        reasons.add("primary_horizon_missing_provenance")
    if evaluated_at is not None and due is not None and due > evaluated_at:
        reasons.add("primary_horizon_due_in_future")
    if price_time is not None and due is not None:
        if price_time < due:
            reasons.add("primary_horizon_price_before_due")
        max_lag = min(OUTCOME_HORIZON_SECONDS[primary], 24 * 60 * 60)
        if price_time > due + timedelta(seconds=max_lag):
            reasons.add("primary_horizon_price_lag_exceeded")
    if price_time is not None and evaluated_at is not None and price_time > evaluated_at:
        reasons.add("primary_horizon_price_after_evaluation")


def _horizon_return_contract_valid(
    row: Mapping[str, Any],
    *,
    metadata: Any,
    data_source: Any,
) -> bool:
    returns = row.get("return_by_horizon")
    alias = row.get("horizons")
    if not isinstance(returns, Mapping) or set(returns) != set(OUTCOME_HORIZONS):
        return False
    if alias is not None and (
        not isinstance(alias, Mapping) or set(alias) != set(OUTCOME_HORIZONS)
    ):
        return False
    if not isinstance(metadata, Mapping):
        return False
    observation_price = finite_number(row.get("price_at_observation"))
    for horizon in OUTCOME_HORIZONS:
        value = returns.get(horizon)
        numeric = finite_number(value)
        if value is not None and numeric is None:
            return False
        if isinstance(alias, Mapping):
            alias_value = alias.get(horizon)
            alias_numeric = finite_number(alias_value)
            if alias_value is not None and alias_numeric is None:
                return False
            if alias_value is None and value is not None:
                return False
            if alias_value is not None and (value is None or alias_numeric != numeric):
                return False
        item = metadata.get(horizon)
        if not isinstance(item, Mapping):
            return False
        status = item.get("maturity_status")
        if data_source == "observed_market_prices":
            if status == "matured" and numeric is None:
                return False
            if status == "matured":
                exit_price = finite_number(item.get("price_at_horizon"))
                if observation_price is None or observation_price <= 0 or exit_price is None:
                    return False
                recomputed = exit_price / observation_price - 1.0
                if not math.isclose(
                    numeric,
                    recomputed,
                    rel_tol=OUTCOME_RETURN_RECOMPUTE_REL_TOLERANCE,
                    abs_tol=OUTCOME_RETURN_RECOMPUTE_ABS_TOLERANCE,
                ):
                    return False
            if status in {"pending", "missing_data"} and value is not None:
                return False
        elif value is not None and status != "matured":
            # Fixture returns are retained only as diagnostics and must carry
            # an explicit contract exclusion instead of looking observed.
            return False
    return True


def _horizon_price_lineage_reasons(
    row: Mapping[str, Any],
    *,
    metadata: Any,
    data_source: Any,
) -> set[str]:
    reasons: set[str] = set()
    if data_source != "observed_market_prices" or not isinstance(metadata, Mapping):
        return reasons
    observation_price = finite_number(row.get("price_at_observation"))
    returns = row.get("return_by_horizon")
    matured_observation_ids: list[str] = []
    for horizon in OUTCOME_HORIZONS:
        item = metadata.get(horizon)
        if not isinstance(item, Mapping):
            continue
        if item.get("maturity_status") != "matured":
            if any(
                item.get(field) is not None
                for field in ("price_at_horizon", "price_source", "price_observation_id")
            ):
                reasons.add("horizon_price_lineage_contract_invalid")
            continue
        raw_exit_price = item.get("price_at_horizon")
        exit_price = finite_number(raw_exit_price)
        if raw_exit_price is None:
            reasons.add("horizon_exit_price_missing")
        elif exit_price is None or exit_price <= 0:
            reasons.add("horizon_exit_price_invalid")
        if not _canonical_identity_text(item.get("price_source")):
            reasons.add("horizon_price_source_missing")
        price_observation_id = item.get("price_observation_id")
        if not _canonical_identity_text(price_observation_id):
            reasons.add("horizon_price_observation_id_missing")
        else:
            matured_observation_ids.append(str(price_observation_id))
        return_value = (
            finite_number(returns.get(horizon))
            if isinstance(returns, Mapping)
            else None
        )
        if (
            observation_price is not None
            and observation_price > 0
            and exit_price is not None
            and exit_price > 0
            and return_value is not None
            and not math.isclose(
                return_value,
                exit_price / observation_price - 1.0,
                rel_tol=OUTCOME_RETURN_RECOMPUTE_REL_TOLERANCE,
                abs_tol=OUTCOME_RETURN_RECOMPUTE_ABS_TOLERANCE,
            )
        ):
            reasons.add("horizon_return_recompute_mismatch")
    if len(matured_observation_ids) != len(set(matured_observation_ids)):
        reasons.add("duplicate_horizon_price_observation_id")
    entry_observation_id = row.get("observation_price_id")
    if (
        _canonical_identity_text(entry_observation_id)
        and entry_observation_id in matured_observation_ids
    ):
        reasons.add("duplicate_horizon_price_observation_id")
    return reasons


def _add_external_clock_reasons(
    reasons: set[str],
    row: Mapping[str, Any],
    evaluated_at: datetime,
) -> None:
    primary = row.get("primary_horizon")
    metadata = row.get("horizon_metadata")
    if type(primary) is not str or not isinstance(metadata, Mapping):
        return
    item = metadata.get(primary)
    if not isinstance(item, Mapping):
        return
    due = parse_aware_time(item.get("due_at"))
    price_time = parse_aware_time(item.get("price_observed_at"))
    if due is not None and due > evaluated_at:
        reasons.add("primary_horizon_due_in_future")
    if price_time is not None and price_time > evaluated_at:
        reasons.add("primary_horizon_price_after_evaluation")


def _outcome_safety_contract_valid(row: Mapping[str, Any]) -> bool:
    for field in OUTCOME_REQUIRED_TRUE_SAFETY_FIELDS:
        if row.get(field) is not True:
            return False
    for field in OUTCOME_REQUIRED_FALSE_SAFETY_FIELDS:
        if row.get(field) is not False:
            return False
    for field in OUTCOME_OPTIONAL_FALSE_SAFETY_FIELDS:
        if field in row and row.get(field) is not False:
            return False
    for field in OUTCOME_ZERO_SAFETY_FIELDS:
        if field in row and (type(row.get(field)) is not int or row.get(field) != 0):
            return False
    return True


def _authority_safety_contract_valid(row: Mapping[str, Any]) -> bool:
    for field in OUTCOME_REQUIRED_FALSE_SAFETY_FIELDS:
        if field in row and row.get(field) is not False:
            return False
    for field in OUTCOME_OPTIONAL_FALSE_SAFETY_FIELDS:
        if field in row and row.get(field) is not False:
            return False
    for field in OUTCOME_ZERO_SAFETY_FIELDS:
        if field in row and (type(row.get(field)) is not int or row.get(field) != 0):
            return False
    return True


def _authority_schema_valid(row: Mapping[str, Any], schema_id: str) -> bool:
    """Validate authority rows against the registered artifact schema lazily."""

    try:
        from ..artifacts.schema.registry import validate_row_against_schema

        return not validate_row_against_schema(row, schema_id)
    except (ImportError, KeyError, RuntimeError, TypeError, ValueError):
        return False


def _row_claims_validated(row: Mapping[str, Any]) -> bool:
    label = row.get("outcome_label")
    if type(label) is str and label.strip().casefold() in OUTCOME_VALIDATED_LABELS:
        return True
    for field in ("status", "validation_label", "validation_status"):
        value = row.get(field)
        if type(value) is str and value.strip().casefold() in OUTCOME_VALIDATED_STATUS_ALIASES:
            return True
    if row.get("direction_hit") is True:
        return True
    return False


def _primary_return_mappings_match(
    row: Mapping[str, Any],
    *,
    primary: str,
    primary_return: float,
) -> bool:
    returns = row.get("return_by_horizon")
    if not isinstance(returns, Mapping):
        return False
    mapped_return = finite_number(returns.get(primary))
    if mapped_return is None or mapped_return != primary_return:
        return False
    alias = row.get("horizons")
    if isinstance(alias, Mapping):
        alias_return = finite_number(alias.get(primary))
        if alias_return is None or alias_return != primary_return:
            return False
    return True


def _malformed_identity_alias(row: Mapping[str, Any]) -> tuple[str, str] | None:
    candidate_id = row.get("candidate_id")
    core_id = row.get("core_opportunity_id")
    candidate = candidate_id if type(candidate_id) is str and candidate_id else ""
    core = core_id if type(core_id) is str and core_id else ""
    return (candidate, core) if candidate or core else None


def _group_by_exact_identity(
    rows: Iterable[Mapping[str, Any]],
) -> dict[tuple[str, ...], list[dict[str, Any]]]:
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for row in rows:
        identity = canonical_join_identity(row)
        if identity is not None:
            grouped.setdefault(identity, []).append(dict(row))
    return grouped


def _core_join_key(row: Mapping[str, Any]) -> tuple[str, ...] | None:
    values = tuple(
        row.get(field)
        for field in ("core_opportunity_id", "run_id", "profile", "artifact_namespace")
    )
    if not all(_canonical_identity_text(value) for value in values):
        return None
    return values


def _loose_identity_aliases(row: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    aliases: list[tuple[str, str]] = []
    candidate = row.get("candidate_id") or row.get("integrated_candidate_id")
    core = row.get("core_opportunity_id")
    if type(candidate) is str and candidate:
        aliases.append(("candidate_id", candidate))
    if type(core) is str and core:
        aliases.append(("core_opportunity_id", core))
    return tuple(aliases)


def _identity_text(value: Any) -> str:
    return value if type(value) is str else ""


def _canonical_identity_text(value: Any) -> bool:
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
    "OUTCOME_DATA_SOURCES",
    "OUTCOME_ALLOWED_LANES",
    "OUTCOME_ATTRIBUTION_FIELDS",
    "OUTCOME_ELIGIBILITY_CONTRACT_VERSION",
    "OUTCOME_ELIGIBILITY_MARKERS",
    "OUTCOME_ELIGIBILITY_REQUIRED_FIELDS",
    "OUTCOME_ENTRY_PRICE_MAX_STALENESS_SECONDS",
    "OUTCOME_HORIZONS",
    "OUTCOME_HORIZON_METADATA_FIELDS",
    "OUTCOME_HORIZON_SECONDS",
    "OUTCOME_IDENTITY_FIELDS",
    "OUTCOME_INELIGIBLE_REASONS",
    "OUTCOME_DIRECTION_BY_LANE",
    "OUTCOME_MATURITY_STATUSES",
    "OUTCOME_PRIMARY_HORIZON_BY_LANE",
    "OUTCOME_OPTIONAL_FALSE_SAFETY_FIELDS",
    "OUTCOME_PROVENANCE_STATUSES",
    "OUTCOME_REQUIRED_FALSE_SAFETY_FIELDS",
    "OUTCOME_REQUIRED_TRUE_SAFETY_FIELDS",
    "OUTCOME_RETURN_RECOMPUTE_ABS_TOLERANCE",
    "OUTCOME_RETURN_RECOMPUTE_REL_TOLERANCE",
    "OUTCOME_VALIDATED_LABELS",
    "OUTCOME_VALIDATED_STATUS_ALIASES",
    "OUTCOME_VALIDATION_STATUSES",
    "OUTCOME_ZERO_SAFETY_FIELDS",
    "build_outcome_identity_fields",
    "build_synthetic_horizon_metadata",
    "calibration_ineligibility_reasons",
    "canonical_join_identity",
    "canonical_outcome_identity",
    "canonical_outcome_identity_key",
    "effective_calibration_eligible",
    "effective_calibration_state",
    "deterministic_validation_status",
    "filled_horizon_count",
    "finite_number",
    "has_outcome_eligibility_marker",
    "iso_utc",
    "parse_aware_time",
    "partition_calibration_outcomes",
    "partition_joined_calibration_outcomes",
    "primary_horizon_for_lane",
    "primary_horizon_maturation_state",
    "validate_contract",
    "valid_candidate_authority",
    "valid_core_authority",
)
