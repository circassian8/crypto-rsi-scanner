"""Exact research-feedback identity and calibration eligibility firewall.

The helpers in this module are deliberately pure.  They neither read nor write
artifacts and they do not alter notification, watchlist, outcome, or trading
state.  Legacy feedback remains readable, but only a complete v1 contract
joined to one exact core-opportunity authority may enter calibration.
"""

from __future__ import annotations

import copy
import hashlib
import json
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from ..radar.core.models import EVENT_CORE_OPPORTUNITY_STORE_SCHEMA_VERSION


FEEDBACK_ELIGIBILITY_CONTRACT_VERSION = 1
FEEDBACK_IDENTITY_FIELDS = (
    "run_id",
    "profile",
    "artifact_namespace",
    "core_opportunity_id",
)
FEEDBACK_ELIGIBILITY_MARKERS = (
    "feedback_eligibility_contract_version",
    "feedback_identity",
    "feedback_identity_key",
    "calibration_eligible",
    "calibration_ineligible_reasons",
)
FEEDBACK_ELIGIBILITY_REQUIRED_FIELDS = tuple(
    dict.fromkeys(
        (
            *FEEDBACK_ELIGIBILITY_MARKERS,
            *FEEDBACK_IDENTITY_FIELDS,
            "feedback_id",
            "feedback_target_type",
            "feedback_target",
            "target",
            "label",
            "marked_at",
            "marked_by",
            "source",
            "research_only",
        )
    )
)
MANUAL_MATCHED_FEEDBACK_SOURCE = "manual_cli"
FEEDBACK_TARGET_TYPE = "core_opportunity_id"
CORE_OPPORTUNITY_ROW_TYPE = "event_core_opportunity"
MAX_FEEDBACK_NOTES_CHARS = 4_096
VALID_FEEDBACK_LABELS = frozenset(
    {
        "useful",
        "junk",
        "watch",
        "false_positive",
        "late",
        "source_noise",
        "needs_confirmation",
        "missing_confirmation",
        "manipulation_risk",
        "duplicate",
        "promising_source_type",
        "missed",
        "traded_elsewhere",
        "ignored",
    }
)
FEEDBACK_INELIGIBLE_REASONS = frozenset(
    {
        "ambiguous_core_authority",
        "ambiguous_feedback_history",
        "ambiguous_feedback_timestamp",
        "core_authority_generated_in_future",
        "core_authority_identity_mismatch",
        "core_authority_safety_contract_invalid",
        "duplicate_core_authority",
        "duplicate_feedback_id",
        "duplicate_feedback_row",
        "feedback_before_core_generation",
        "feedback_identity_contract_invalid",
        "feedback_identity_key_mismatch",
        "feedback_marked_in_future",
        "feedback_safety_contract_invalid",
        "feedback_target_mismatch",
        "invalid_core_authority_attribution",
        "invalid_core_authority_contract",
        "invalid_calibration_eligible_flag",
        "invalid_calibration_ineligible_reasons",
        "invalid_feedback_contract_version",
        "invalid_feedback_label",
        "invalid_feedback_marked_at",
        "invalid_feedback_notes",
        "invalid_feedback_source",
        "invalid_feedback_target_type",
        "legacy_feedback_contract",
        "missing_core_authority",
        "missing_exact_feedback_identity",
        "missing_feedback_id",
        "missing_marked_by",
        "non_research_feedback",
        "partial_feedback_contract",
        "superseded_feedback",
    }
)

# Calibration cohort attribution is copied only from the one exact core row.
# Missing core values stay missing; feedback and outcome aliases are never used
# as fallbacks.
CORE_CALIBRATION_ATTRIBUTION_FIELDS = (
    "symbol",
    "coin_id",
    "source_provider",
    "source_provider_domain",
    "source_domain",
    "source_pack",
    "source_class",
    "lane",
    "playbook_type",
    "effective_playbook_type",
    "impact_path_type",
    "opportunity_level",
    "final_opportunity_level",
    "final_route_after_quality_gate",
    "decision_model_version",
    "thesis_origin",
    "directional_bias",
    "catalyst_status",
    "confidence_band",
    "timing_state",
    "tradability_status",
    "radar_route",
    "actionability_score_cohort",
    "anomaly_type",
)

_SIDE_EFFECT_BOOLEAN_FIELDS = (
    "created_alert",
    "execution_enabled",
    "normal_rsi_routing_enabled",
    "normal_rsi_signal_written",
    "notification_send_enabled",
    "paper_trade_created",
    "paper_trading_enabled",
    "send_attempted",
    "sent",
    "trade_created",
)
_SIDE_EFFECT_FALSE_OR_ZERO_FIELDS = ("triggered_fade_created",)
_SIDE_EFFECT_ZERO_FIELDS = (
    "normal_rsi_signal_rows_written",
    "paper_trades_created",
    "safety_failure_count",
    "strict_alerts_created",
    "telegram_sends",
    "trades_created",
    "triggered_fades_created",
)
_SOURCE_SAFETY_FAILURE_FIELDS = (
    "decision_source_path_safety_failed",
    "decision_source_secret_safety_failed",
    "decision_source_side_effect_safety_failed",
)


def has_feedback_eligibility_marker(row: Mapping[str, Any]) -> bool:
    """Return whether any v1 contract marker is present."""

    return any(field in row for field in FEEDBACK_ELIGIBILITY_MARKERS)


def canonical_feedback_identity(row: Mapping[str, Any]) -> dict[str, str]:
    """Return the exact four-field identity, preserving invalid values as empty."""

    return {field: _identity_text(row.get(field)) for field in FEEDBACK_IDENTITY_FIELDS}


def canonical_feedback_join_identity(row: Mapping[str, Any]) -> tuple[str, ...] | None:
    """Return an exact NFC join tuple; unsafe Unicode aliases are invalid."""

    identity = canonical_feedback_identity(row)
    if not all(identity.values()):
        return None
    return tuple(identity[field] for field in FEEDBACK_IDENTITY_FIELDS)


def canonical_feedback_identity_key(identity: Mapping[str, Any]) -> str:
    """Hash canonical sorted-key JSON for the exact four-field identity."""

    canonical = {
        field: _identity_text(identity.get(field))
        for field in FEEDBACK_IDENTITY_FIELDS
    }
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_feedback_eligibility_fields(row: Mapping[str, Any]) -> dict[str, Any]:
    """Build v1 markers for a producer row without mutating the input.

    Invalid producer inputs receive a truthful false eligibility flag and the
    closed, sorted row-local reasons.  Join/history reasons are intentionally
    absent because they can be known only while reading the complete artifact.
    """

    identity = canonical_feedback_identity(row)
    staged = dict(row)
    staged.update(
        {
            "feedback_eligibility_contract_version": FEEDBACK_ELIGIBILITY_CONTRACT_VERSION,
            "feedback_identity": identity,
            "feedback_identity_key": canonical_feedback_identity_key(identity),
            "calibration_eligible": False,
            "calibration_ineligible_reasons": [],
        }
    )
    reasons = feedback_ineligibility_reasons(staged)
    return {
        **identity,
        "feedback_eligibility_contract_version": FEEDBACK_ELIGIBILITY_CONTRACT_VERSION,
        "feedback_identity": identity,
        "feedback_identity_key": canonical_feedback_identity_key(identity),
        "calibration_eligible": not reasons,
        "calibration_ineligible_reasons": list(reasons),
    }


def feedback_ineligibility_reasons(row: Mapping[str, Any]) -> tuple[str, ...]:
    """Compute closed row-local reasons without trusting persisted declarations."""

    reasons: set[str] = set()
    marked = has_feedback_eligibility_marker(row)
    if not marked:
        reasons.add("legacy_feedback_contract")
    else:
        if any(field not in row for field in FEEDBACK_ELIGIBILITY_REQUIRED_FIELDS):
            reasons.add("partial_feedback_contract")
        if (
            type(row.get("feedback_eligibility_contract_version")) is not int
            or row.get("feedback_eligibility_contract_version")
            != FEEDBACK_ELIGIBILITY_CONTRACT_VERSION
        ):
            reasons.add("invalid_feedback_contract_version")

    identity = canonical_feedback_identity(row)
    exact_identity = canonical_feedback_join_identity(row)
    if exact_identity is None:
        reasons.add("missing_exact_feedback_identity")
    nested = row.get("feedback_identity")
    if (
        not isinstance(nested, Mapping)
        or set(nested) != set(FEEDBACK_IDENTITY_FIELDS)
        or any(type(nested.get(field)) is not str for field in FEEDBACK_IDENTITY_FIELDS)
        or dict(nested) != identity
    ):
        reasons.add("feedback_identity_contract_invalid")
    if row.get("feedback_identity_key") != canonical_feedback_identity_key(identity):
        reasons.add("feedback_identity_key_mismatch")

    core_id = identity["core_opportunity_id"]
    if row.get("feedback_target_type") != FEEDBACK_TARGET_TYPE:
        reasons.add("invalid_feedback_target_type")
    if (
        not core_id
        or row.get("feedback_target") != core_id
        or row.get("target") != core_id
    ):
        reasons.add("feedback_target_mismatch")
    if type(row.get("label")) is not str or row.get("label") not in VALID_FEEDBACK_LABELS:
        reasons.add("invalid_feedback_label")
    if type(row.get("marked_at")) is not str or not _canonical_text(row.get("marked_at")):
        reasons.add("invalid_feedback_marked_at")
    elif parse_aware_feedback_time(row.get("marked_at")) is None:
        reasons.add("invalid_feedback_marked_at")
    if row.get("research_only") is not True:
        reasons.add("non_research_feedback")
    if not _research_safety_contract_valid(row, require_research_only=True):
        reasons.add("feedback_safety_contract_invalid")
    if row.get("source") != MANUAL_MATCHED_FEEDBACK_SOURCE:
        reasons.add("invalid_feedback_source")
    if not _canonical_text(row.get("marked_by")):
        reasons.add("missing_marked_by")
    if not _canonical_text(row.get("feedback_id")):
        reasons.add("missing_feedback_id")
    if not _safe_feedback_notes(row.get("notes")):
        reasons.add("invalid_feedback_notes")
    return tuple(sorted(reasons))


def core_authority_ineligibility_reasons(
    row: Mapping[str, Any],
    *,
    now: Any = None,
) -> tuple[str, ...]:
    """Validate one canonical CoreOpportunity authority against its real schema."""

    evaluated_at = _external_now(now)
    return _core_authority_ineligibility_reasons(row, evaluated_at=evaluated_at)


def effective_feedback_state(
    row: Mapping[str, Any],
    *,
    additional_reasons: Iterable[str] = (),
) -> tuple[bool, tuple[str, ...]]:
    """Recompute effective row state and validate declared markers literally."""

    row_local = feedback_ineligibility_reasons(row)
    reasons = set(row_local)
    declared = row.get("calibration_ineligible_reasons")
    declared_valid = (
        isinstance(declared, list)
        and all(
            type(reason) is str and reason in FEEDBACK_INELIGIBLE_REASONS
            for reason in declared
        )
        and declared == sorted(set(declared))
    )
    if not declared_valid or tuple(declared) != row_local:
        reasons.add("invalid_calibration_ineligible_reasons")
    flag = row.get("calibration_eligible")
    if type(flag) is not bool or flag is not (not row_local):
        reasons.add("invalid_calibration_eligible_flag")
    for reason in additional_reasons:
        reasons.add(
            reason
            if type(reason) is str and reason in FEEDBACK_INELIGIBLE_REASONS
            else "ambiguous_feedback_history"
        )
    effective_reasons = tuple(sorted(reasons))
    return flag is True and not effective_reasons, effective_reasons


def effective_feedback_eligible(
    row: Mapping[str, Any],
    *,
    additional_reasons: Iterable[str] = (),
) -> bool:
    """Return the literal effective eligibility decision."""

    eligible, _reasons = effective_feedback_state(row, additional_reasons=additional_reasons)
    return eligible


def validate_contract(row: Mapping[str, Any]) -> list[str]:
    """Return stable schema-adapter errors; unmarked legacy rows stay readable."""

    if not has_feedback_eligibility_marker(row):
        return []
    errors: list[str] = []
    missing = [field for field in FEEDBACK_ELIGIBILITY_REQUIRED_FIELDS if field not in row]
    errors.extend(f"feedback_eligibility_missing_field:{field}" for field in missing)
    computed = feedback_ineligibility_reasons(row)
    declared = row.get("calibration_ineligible_reasons")
    if not isinstance(declared, list) or declared != list(computed):
        errors.append("feedback_eligibility_reasons_mismatch")
    expected_flag = not computed
    if type(row.get("calibration_eligible")) is not bool or row.get(
        "calibration_eligible"
    ) is not expected_flag:
        errors.append("feedback_calibration_eligible_mismatch")
    return errors


def partition_joined_calibration_feedback(
    feedback_rows: Iterable[Mapping[str, Any]],
    core_rows: Iterable[Mapping[str, Any]],
    *,
    now: Any = None,
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...], dict[str, int]]:
    """Partition latest feedback joined to exactly one core authority.

    The result is independent of input order.  Only the latest unambiguous row
    for an exact identity can be eligible.  Eligible projections are rebuilt
    from a narrow feedback label envelope plus core-owned cohort attribution;
    feedback/outcome attribution aliases are never carried through.
    """

    evaluated_at = _external_now(now)
    feedback = sorted(
        (dict(row) for row in feedback_rows if isinstance(row, Mapping)),
        key=_stable_row_json,
    )
    cores = sorted(
        (dict(row) for row in core_rows if isinstance(row, Mapping)),
        key=_stable_row_json,
    )
    added_reasons = [set() for _row in feedback]
    identity_groups = _collect_feedback_history_reasons(
        feedback,
        added_reasons,
        evaluated_at=evaluated_at,
    )
    cores_by_identity, invalid_cores, core_ids_present = _index_core_authorities(
        cores,
        evaluated_at=evaluated_at,
    )
    matched_core_by_index = _match_core_authorities(
        feedback,
        added_reasons,
        cores_by_identity=cores_by_identity,
        invalid_cores=invalid_cores,
        core_ids_present=core_ids_present,
    )
    _add_core_chronology_reasons(
        feedback,
        added_reasons,
        identity_groups=identity_groups,
        matched_core_by_index=matched_core_by_index,
    )
    return _materialize_feedback_partition(
        feedback,
        added_reasons,
        matched_core_by_index=matched_core_by_index,
    )


def _collect_feedback_history_reasons(
    feedback: list[dict[str, Any]],
    added_reasons: list[set[str]],
    *,
    evaluated_at: datetime,
) -> dict[tuple[str, ...], list[int]]:
    row_digest_counts = Counter(_stable_row_json(row) for row in feedback)
    feedback_id_counts = Counter(
        feedback_id
        for row in feedback
        if (feedback_id := _canonical_text(row.get("feedback_id"))) is not None
    )
    identity_groups: dict[tuple[str, ...], list[int]] = {}
    for index, row in enumerate(feedback):
        if row_digest_counts[_stable_row_json(row)] > 1:
            added_reasons[index].add("duplicate_feedback_row")
        feedback_id = _canonical_text(row.get("feedback_id"))
        if feedback_id is not None and feedback_id_counts[feedback_id] > 1:
            added_reasons[index].add("duplicate_feedback_id")
        identity = canonical_feedback_join_identity(row)
        if identity is not None:
            identity_groups.setdefault(identity, []).append(index)

    for indices in identity_groups.values():
        timestamp_groups: dict[datetime, list[int]] = {}
        history_is_ambiguous = False
        for index in indices:
            marked_at = parse_aware_feedback_time(feedback[index].get("marked_at"))
            if marked_at is None:
                history_is_ambiguous = True
                continue
            if marked_at > evaluated_at:
                added_reasons[index].add("feedback_marked_in_future")
                history_is_ambiguous = True
            timestamp_groups.setdefault(marked_at, []).append(index)
            if added_reasons[index] & {"duplicate_feedback_row", "duplicate_feedback_id"}:
                history_is_ambiguous = True
        history_is_ambiguous |= _add_equal_timestamp_reasons(
            feedback,
            added_reasons,
            timestamp_groups=timestamp_groups,
        )
        if history_is_ambiguous:
            for index in indices:
                added_reasons[index].add("ambiguous_feedback_history")
            continue
        latest_indices = timestamp_groups[max(timestamp_groups)]
        if len(latest_indices) != 1:
            for index in indices:
                added_reasons[index].add("ambiguous_feedback_history")
            continue
        latest_index = latest_indices[0]
        for index in indices:
            if index != latest_index:
                added_reasons[index].add("superseded_feedback")
    return identity_groups


def _add_equal_timestamp_reasons(
    feedback: list[dict[str, Any]],
    added_reasons: list[set[str]],
    *,
    timestamp_groups: Mapping[datetime, list[int]],
) -> bool:
    ambiguous = False
    for same_time_indices in timestamp_groups.values():
        if len(same_time_indices) <= 1:
            continue
        labels = {feedback[index].get("label") for index in same_time_indices}
        ids = {feedback[index].get("feedback_id") for index in same_time_indices}
        if len(labels) > 1 or len(ids) > 1:
            for index in same_time_indices:
                added_reasons[index].add("ambiguous_feedback_timestamp")
        ambiguous = True
    return ambiguous


def _index_core_authorities(
    cores: list[dict[str, Any]],
    *,
    evaluated_at: datetime,
) -> tuple[
    dict[tuple[str, ...], list[dict[str, Any]]],
    list[tuple[dict[str, Any], tuple[str, ...]]],
    set[str],
]:
    cores_by_identity: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    invalid_cores: list[tuple[dict[str, Any], tuple[str, ...]]] = []
    core_ids_present: set[str] = set()
    for core in cores:
        core_id = _loose_identity_text(core.get("core_opportunity_id"))
        if core_id is not None:
            core_ids_present.add(core_id)
        identity = canonical_feedback_join_identity(core)
        reasons = _core_authority_ineligibility_reasons(core, evaluated_at=evaluated_at)
        if identity is not None and not reasons:
            cores_by_identity.setdefault(identity, []).append(core)
        else:
            invalid_cores.append((core, reasons or ("invalid_core_authority_contract",)))
    return cores_by_identity, invalid_cores, core_ids_present


def _match_core_authorities(
    feedback: list[dict[str, Any]],
    added_reasons: list[set[str]],
    *,
    cores_by_identity: Mapping[tuple[str, ...], list[dict[str, Any]]],
    invalid_cores: list[tuple[dict[str, Any], tuple[str, ...]]],
    core_ids_present: set[str],
) -> dict[int, dict[str, Any]]:
    matched: dict[int, dict[str, Any]] = {}
    for index, row in enumerate(feedback):
        identity = canonical_feedback_join_identity(row)
        if identity is None:
            continue
        matches = cores_by_identity.get(identity, ())
        overlapping_invalid = [
            reasons
            for core, reasons in invalid_cores
            if _core_identity_overlaps(core, identity)
        ]
        if overlapping_invalid:
            for reasons in overlapping_invalid:
                added_reasons[index].update(reasons)
            if matches or len(overlapping_invalid) > 1:
                added_reasons[index].add("ambiguous_core_authority")
        elif len(matches) == 1:
            matched[index] = matches[0]
        elif len(matches) > 1:
            added_reasons[index].add("duplicate_core_authority")
        elif identity[-1] in core_ids_present:
            added_reasons[index].add("core_authority_identity_mismatch")
        else:
            added_reasons[index].add("missing_core_authority")
    return matched


def _add_core_chronology_reasons(
    feedback: list[dict[str, Any]],
    added_reasons: list[set[str]],
    *,
    identity_groups: Mapping[tuple[str, ...], list[int]],
    matched_core_by_index: Mapping[int, dict[str, Any]],
) -> None:
    for indices in identity_groups.values():
        matching_core = next(
            (matched_core_by_index[index] for index in indices if index in matched_core_by_index),
            None,
        )
        generated_at = (
            parse_aware_feedback_time(matching_core.get("generated_at"))
            if matching_core is not None
            else None
        )
        if generated_at is None:
            continue
        before_core = [
            index
            for index in indices
            if (
                (marked_at := parse_aware_feedback_time(feedback[index].get("marked_at")))
                is not None
                and marked_at < generated_at
            )
        ]
        if before_core:
            for index in before_core:
                added_reasons[index].add("feedback_before_core_generation")
            for index in indices:
                added_reasons[index].add("ambiguous_feedback_history")


def _materialize_feedback_partition(
    feedback: list[dict[str, Any]],
    added_reasons: list[set[str]],
    *,
    matched_core_by_index: Mapping[int, dict[str, Any]],
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...], dict[str, int]]:
    eligible: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter()
    for index, row in enumerate(feedback):
        is_eligible, reasons = effective_feedback_state(
            row,
            additional_reasons=added_reasons[index],
        )
        core = matched_core_by_index.get(index)
        if is_eligible and core is not None:
            eligible.append(_joined_calibration_projection(row, core))
            continue
        materialized = copy.deepcopy(row)
        materialized["calibration_eligible"] = False
        materialized["calibration_ineligible_reasons"] = list(reasons)
        excluded.append(materialized)
        reason_counts.update(reasons)
    eligible.sort(key=_stable_row_json)
    excluded.sort(key=_stable_row_json)
    return tuple(eligible), tuple(excluded), dict(sorted(reason_counts.items()))


def parse_aware_feedback_time(value: Any) -> datetime | None:
    """Parse a finite timezone-aware time and normalize it to UTC."""

    try:
        if isinstance(value, datetime):
            parsed = value
        elif type(value) is str:
            text = value.strip()
            if not text:
                return None
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        else:
            return None
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _joined_calibration_projection(
    feedback: Mapping[str, Any],
    core: Mapping[str, Any],
) -> dict[str, Any]:
    identity = canonical_feedback_identity(feedback)
    attribution = {
        field: copy.deepcopy(core.get(field))
        for field in CORE_CALIBRATION_ATTRIBUTION_FIELDS
    }
    projection: dict[str, Any] = {
        **identity,
        "feedback_identity": identity,
        "feedback_identity_key": canonical_feedback_identity_key(identity),
        "feedback_eligibility_contract_version": FEEDBACK_ELIGIBILITY_CONTRACT_VERSION,
        "feedback_id": feedback.get("feedback_id"),
        "feedback_target_type": FEEDBACK_TARGET_TYPE,
        "feedback_target": identity["core_opportunity_id"],
        "target": identity["core_opportunity_id"],
        "feedback_label": feedback.get("label"),
        "feedback_marked_at": feedback.get("marked_at"),
        "feedback_marked_by": feedback.get("marked_by"),
        "feedback_notes": feedback.get("notes"),
        "feedback_source": MANUAL_MATCHED_FEEDBACK_SOURCE,
        "research_only": True,
        "calibration_eligible": True,
        "calibration_ineligible_reasons": [],
        "core_attribution": attribution,
    }
    projection.update(attribution)
    return projection


def _identity_text(value: Any) -> str:
    return _canonical_text(value) or ""


def _canonical_text(value: Any) -> str | None:
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or unicodedata.normalize("NFC", value) != value
        or _has_unsafe_unicode(value)
    ):
        return None
    return value


def _safe_feedback_notes(value: Any) -> bool:
    if value is None:
        return True
    if type(value) is not str or len(value) > MAX_FEEDBACK_NOTES_CHARS:
        return False
    if unicodedata.normalize("NFC", value) != value:
        return False
    return not _has_unsafe_unicode(value, allowed_controls="\t\n\r")


def _has_unsafe_unicode(value: str, *, allowed_controls: str = "") -> bool:
    return any(
        (unicodedata.category(character).startswith("C") and character not in allowed_controls)
        for character in value
    )


def _external_now(value: Any) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    parsed = parse_aware_feedback_time(value)
    if parsed is None:
        raise ValueError("feedback eligibility now must be a finite timezone-aware timestamp")
    return parsed


def _core_authority_ineligibility_reasons(
    row: Mapping[str, Any],
    *,
    evaluated_at: datetime,
) -> tuple[str, ...]:
    # Keep the schema import lazy so the registry can later register this
    # feedback contract without creating a module-import cycle.
    from ..artifacts.schema.core_opportunity import CORE_OPPORTUNITY_SCHEMA
    from ..artifacts.schema.registry import validate_row_against_schema

    reasons: set[str] = set()
    if (
        row.get("schema_id") != CORE_OPPORTUNITY_SCHEMA.schema_id
        or row.get("schema_version") != EVENT_CORE_OPPORTUNITY_STORE_SCHEMA_VERSION
        or row.get("row_type") != CORE_OPPORTUNITY_ROW_TYPE
        or canonical_feedback_join_identity(row) is None
        or row.get("feedback_target_type") != FEEDBACK_TARGET_TYPE
        or row.get("feedback_target") != _identity_text(row.get("core_opportunity_id"))
    ):
        reasons.add("invalid_core_authority_contract")

    schema_errors = validate_row_against_schema(row, CORE_OPPORTUNITY_SCHEMA)
    if schema_errors:
        if any(
            error.startswith(
                (
                    "absolute_non_debug_path:",
                    "invalid_safety_count:",
                    "secret_field_unredacted:",
                    "unsafe_",
                )
            )
            for error in schema_errors
        ):
            reasons.add("core_authority_safety_contract_invalid")
        if any(
            not error.startswith(
                (
                    "absolute_non_debug_path:",
                    "invalid_safety_count:",
                    "secret_field_unredacted:",
                    "unsafe_",
                )
            )
            for error in schema_errors
        ):
            reasons.add("invalid_core_authority_contract")

    if not _research_safety_contract_valid(row, require_research_only=False):
        reasons.add("core_authority_safety_contract_invalid")
    if not _core_attribution_contract_valid(row):
        reasons.add("invalid_core_authority_attribution")

    generated_at = row.get("generated_at")
    parsed_generated_at = (
        parse_aware_feedback_time(generated_at)
        if _canonical_text(generated_at) is not None
        else None
    )
    if parsed_generated_at is None:
        reasons.add("invalid_core_authority_contract")
    elif parsed_generated_at > evaluated_at:
        reasons.add("core_authority_generated_in_future")
    return tuple(sorted(reasons))


def _research_safety_contract_valid(
    row: Mapping[str, Any],
    *,
    require_research_only: bool,
) -> bool:
    if require_research_only and row.get("research_only") is not True:
        return False
    if "research_only" in row and row.get("research_only") is not True:
        return False
    for field in (*_SIDE_EFFECT_BOOLEAN_FIELDS, *_SOURCE_SAFETY_FAILURE_FIELDS):
        if field in row and row.get(field) is not False:
            return False
    for field in _SIDE_EFFECT_FALSE_OR_ZERO_FIELDS:
        value = row.get(field)
        if field in row and not (value is False or (type(value) is int and value == 0)):
            return False
    for field in _SIDE_EFFECT_ZERO_FIELDS:
        if field in row and (type(row.get(field)) is not int or row.get(field) != 0):
            return False
    return True


def _core_attribution_contract_valid(row: Mapping[str, Any]) -> bool:
    for field in CORE_CALIBRATION_ATTRIBUTION_FIELDS:
        value = row.get(field)
        if value is None:
            continue
        if type(value) is not str:
            return False
        if unicodedata.normalize("NFC", value) != value or _has_unsafe_unicode(value):
            return False
    return True


def _loose_identity_text(value: Any) -> str | None:
    if type(value) is not str:
        return None
    text = unicodedata.normalize("NFC", value.strip())
    if not text or _has_unsafe_unicode(text):
        return None
    return text


def _core_identity_overlaps(
    core: Mapping[str, Any],
    identity: tuple[str, ...],
) -> bool:
    values = {
        field: _loose_identity_text(core.get(field))
        for field in FEEDBACK_IDENTITY_FIELDS
    }
    if values["core_opportunity_id"] != identity[-1]:
        return False
    expected = dict(zip(FEEDBACK_IDENTITY_FIELDS, identity, strict=True))
    return all(value is None or value == expected[field] for field, value in values.items())


def _stable_row_json(row: Mapping[str, Any]) -> str:
    try:
        return json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError, OverflowError):
        return json.dumps(
            _stable_json_value(row),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )


def _stable_json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _stable_json_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_stable_json_value(item) for item in value]
    if value is None or type(value) in (str, int, float, bool):
        return value
    return {"unsupported_type": f"{type(value).__module__}.{type(value).__qualname__}"}
