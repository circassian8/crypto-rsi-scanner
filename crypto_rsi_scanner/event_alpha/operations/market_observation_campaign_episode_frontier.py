"""Closed Protocol-v2 route/origin coverage over frozen Decision episodes.

The Decision episode scorecard already preserves exact candidate, Core, outcome,
and episode bindings.  This projection adds no new evaluation.  It expands the
scorecard's observed-only cohorts across the complete canonical Decision-v2
route and primary-origin taxonomies so zero-coverage categories remain visible.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from ..outcomes import decision_episode_scorecard
from ..radar.decision_models import RadarResearchRoute, ThesisOrigin


SCHEMA_ID = "decision_radar.protocol_v2_episode_coverage_frontier"
SCHEMA_VERSION = 1
EPISODE_INDEPENDENCE_STATUS = (
    "fixed_start_declustered_not_statistically_independent"
)
CANONICAL_ROUTES = tuple(route.value for route in RadarResearchRoute)
CANONICAL_PRIMARY_ORIGINS = tuple(
    origin.value for origin in ThesisOrigin if origin is not ThesisOrigin.MIXED
)
_OUTCOME_STATES = (
    "contract_excluded",
    "due_missing_price",
    "matured",
    "not_due",
)
_ROW_KEYS = frozenset((
    "name",
    "coverage_status",
    "episode_count",
    "matured_episode_count",
    "due_missing_price_episode_count",
    "not_due_episode_count",
    "contract_excluded_episode_count",
    "scoreable_directional_episode_count",
    "aligned_episode_count",
))
_ROOT_KEYS = frozenset((
    "schema_id",
    "schema_version",
    "status",
    "source_scorecard_schema_id",
    "source_scorecard_schema_version",
    "source_scorecard_contract_digest",
    "source_scorecard_input_binding_digest",
    "source_scorecard_evaluated_at",
    "episode_count",
    "repeat_member_count",
    "matured_episode_count",
    "route_population_count",
    "observed_route_count",
    "zero_episode_route_count",
    "unobserved_route_names",
    "route_coverage",
    "primary_origin_population_count",
    "observed_primary_origin_count",
    "zero_episode_primary_origin_count",
    "unobserved_primary_origin_names",
    "primary_origin_coverage",
    "canonical_category_coverage_complete",
    "minimum_sample_policy_sealed",
    "minimum_sample_count",
    "sample_sufficiency_evaluable",
    "episode_independence_status",
    "statistical_independence_claim",
    "cross_asset_independence_claim",
    "matched_control_available",
    "protocol_v2_annex_bound",
    "protocol_v2_evidence_eligible",
    "routing_changes",
    "score_changes",
    "threshold_changes",
    "provider_calls",
    "writes",
    "research_only",
    "contract_digest",
))


def build_protocol_v2_episode_coverage_frontier(
    scorecard: Mapping[str, Any],
) -> dict[str, Any]:
    """Expand one valid scorecard into complete route/origin coverage."""

    source_errors = decision_episode_scorecard.validate_contract(scorecard)
    if source_errors:
        raise ValueError(
            "episode_coverage_source_scorecard_invalid:" + ";".join(source_errors)
        )
    value = _build_values(scorecard)
    errors = validate_protocol_v2_episode_coverage_frontier(
        value,
        scorecard=scorecard,
    )
    if errors:  # pragma: no cover - construction and validation share constants
        raise AssertionError("episode coverage frontier invalid:" + ";".join(errors))
    return value


def validate_protocol_v2_episode_coverage_frontier(
    value: object,
    *,
    scorecard: Mapping[str, Any] | None = None,
) -> list[str]:
    """Validate exact schema, count closures, source binding, and digest."""

    if not isinstance(value, Mapping):
        return ["frontier_not_mapping"]
    errors: list[str] = []
    if set(value) != _ROOT_KEYS:
        errors.append("frontier_schema_mismatch")
        return errors
    constants = {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "source_scorecard_schema_id": decision_episode_scorecard.SCHEMA_ID,
        "source_scorecard_schema_version": (
            decision_episode_scorecard.SCHEMA_VERSION
        ),
        "minimum_sample_policy_sealed": False,
        "minimum_sample_count": None,
        "sample_sufficiency_evaluable": False,
        "episode_independence_status": EPISODE_INDEPENDENCE_STATUS,
        "statistical_independence_claim": False,
        "cross_asset_independence_claim": False,
        "matched_control_available": False,
        "protocol_v2_annex_bound": False,
        "protocol_v2_evidence_eligible": False,
        "routing_changes": 0,
        "score_changes": 0,
        "threshold_changes": 0,
        "provider_calls": 0,
        "writes": 0,
        "research_only": True,
    }
    for field, expected in constants.items():
        if value.get(field) != expected or type(value.get(field)) is not type(expected):
            errors.append(f"invalid_{field}")
    for field in (
        "source_scorecard_contract_digest",
        "source_scorecard_input_binding_digest",
    ):
        if not _is_sha256(value.get(field)):
            errors.append(f"invalid_{field}")
    if not _is_utc_timestamp(value.get("source_scorecard_evaluated_at")):
        errors.append("invalid_source_scorecard_evaluated_at")
    route_rows = _validate_coverage_rows(
        value.get("route_coverage"),
        canonical_names=CANONICAL_ROUTES,
        label="route",
        errors=errors,
    )
    origin_rows = _validate_coverage_rows(
        value.get("primary_origin_coverage"),
        canonical_names=CANONICAL_PRIMARY_ORIGINS,
        label="primary_origin",
        errors=errors,
    )
    _validate_summary(
        value,
        route_rows=route_rows,
        origin_rows=origin_rows,
        errors=errors,
    )
    digest_values = dict(value)
    digest_values.pop("contract_digest", None)
    if value.get("contract_digest") != _digest(digest_values):
        errors.append("invalid_contract_digest")
    if scorecard is not None:
        source_errors = decision_episode_scorecard.validate_contract(scorecard)
        if source_errors:
            errors.extend(f"source_scorecard:{error}" for error in source_errors)
        else:
            try:
                expected = _build_values(scorecard)
            except (KeyError, TypeError, ValueError) as exc:
                errors.append(f"source_scorecard_projection:{type(exc).__name__}")
            else:
                if dict(value) != expected:
                    errors.append("source_scorecard_projection_mismatch")
    return sorted(set(errors))


def _build_values(scorecard: Mapping[str, Any]) -> dict[str, Any]:
    exclusive = scorecard.get("exclusive_cohorts")
    if not isinstance(exclusive, Mapping):
        raise ValueError("scorecard_exclusive_cohorts_invalid")
    route_rows = _complete_coverage(
        exclusive.get("radar_route"),
        canonical_names=CANONICAL_ROUTES,
        label="route",
    )
    origin_rows = _complete_coverage(
        exclusive.get("primary_thesis_origin"),
        canonical_names=CANONICAL_PRIMARY_ORIGINS,
        label="primary_origin",
    )
    unobserved_routes = [
        row["name"] for row in route_rows if row["episode_count"] == 0
    ]
    unobserved_origins = [
        row["name"] for row in origin_rows if row["episode_count"] == 0
    ]
    episode_count = _nonnegative_int(scorecard.get("primary_episode_count"))
    matured_count = _nonnegative_int(scorecard.get("matured_episode_count"))
    complete = not unobserved_routes and not unobserved_origins
    payload: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "status": (
            "empty"
            if episode_count == 0
            else "descriptive_complete_unsealed"
            if complete
            else "descriptive_incomplete"
        ),
        "source_scorecard_schema_id": scorecard.get("schema_id"),
        "source_scorecard_schema_version": scorecard.get("schema_version"),
        "source_scorecard_contract_digest": scorecard.get("contract_digest"),
        "source_scorecard_input_binding_digest": scorecard.get(
            "input_binding_digest"
        ),
        "source_scorecard_evaluated_at": scorecard.get("evaluated_at"),
        "episode_count": episode_count,
        "repeat_member_count": _nonnegative_int(
            scorecard.get("primary_repeat_member_count")
        ),
        "matured_episode_count": matured_count,
        "route_population_count": len(CANONICAL_ROUTES),
        "observed_route_count": len(CANONICAL_ROUTES) - len(unobserved_routes),
        "zero_episode_route_count": len(unobserved_routes),
        "unobserved_route_names": unobserved_routes,
        "route_coverage": route_rows,
        "primary_origin_population_count": len(CANONICAL_PRIMARY_ORIGINS),
        "observed_primary_origin_count": (
            len(CANONICAL_PRIMARY_ORIGINS) - len(unobserved_origins)
        ),
        "zero_episode_primary_origin_count": len(unobserved_origins),
        "unobserved_primary_origin_names": unobserved_origins,
        "primary_origin_coverage": origin_rows,
        "canonical_category_coverage_complete": complete,
        "minimum_sample_policy_sealed": False,
        "minimum_sample_count": None,
        "sample_sufficiency_evaluable": False,
        "episode_independence_status": EPISODE_INDEPENDENCE_STATUS,
        "statistical_independence_claim": False,
        "cross_asset_independence_claim": False,
        "matched_control_available": False,
        "protocol_v2_annex_bound": False,
        "protocol_v2_evidence_eligible": False,
        "routing_changes": 0,
        "score_changes": 0,
        "threshold_changes": 0,
        "provider_calls": 0,
        "writes": 0,
        "research_only": True,
    }
    payload["contract_digest"] = _digest(payload)
    return payload


def _complete_coverage(
    raw_rows: object,
    *,
    canonical_names: Sequence[str],
    label: str,
) -> list[dict[str, Any]]:
    if type(raw_rows) is not list:
        raise ValueError(f"scorecard_{label}_cohorts_invalid")
    observed: dict[str, Mapping[str, Any]] = {}
    for raw in raw_rows:
        if not isinstance(raw, Mapping):
            raise ValueError(f"scorecard_{label}_cohort_invalid")
        name = raw.get("name")
        if type(name) is not str or name not in canonical_names or name in observed:
            raise ValueError(f"scorecard_{label}_cohort_name_invalid")
        observed[name] = raw
    return [
        _coverage_row(name, observed.get(name)) for name in canonical_names
    ]


def _coverage_row(
    name: str,
    source: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if source is None:
        source = {
            "episode_count": 0,
            "matured_episode_count": 0,
            "outcome_state_counts": {state: 0 for state in _OUTCOME_STATES},
            "scoreable_directional_episode_count": 0,
            "aligned_episode_count": 0,
        }
    states = source.get("outcome_state_counts")
    if not isinstance(states, Mapping):
        raise ValueError("episode coverage outcome states invalid")
    episode_count = _nonnegative_int(source.get("episode_count"))
    return {
        "name": name,
        "coverage_status": "observed" if episode_count else "unobserved",
        "episode_count": episode_count,
        "matured_episode_count": _nonnegative_int(
            source.get("matured_episode_count")
        ),
        "due_missing_price_episode_count": _nonnegative_int(
            states.get("due_missing_price")
        ),
        "not_due_episode_count": _nonnegative_int(states.get("not_due")),
        "contract_excluded_episode_count": _nonnegative_int(
            states.get("contract_excluded")
        ),
        "scoreable_directional_episode_count": _nonnegative_int(
            source.get("scoreable_directional_episode_count")
        ),
        "aligned_episode_count": _nonnegative_int(
            source.get("aligned_episode_count")
        ),
    }


def _validate_coverage_rows(
    value: object,
    *,
    canonical_names: Sequence[str],
    label: str,
    errors: list[str],
) -> list[Mapping[str, Any]]:
    if type(value) is not list:
        errors.append(f"{label}_coverage_not_list")
        return []
    rows = [row for row in value if isinstance(row, Mapping)]
    if len(rows) != len(value):
        errors.append(f"{label}_coverage_row_not_mapping")
        return rows
    names = [row.get("name") for row in rows]
    if names != list(canonical_names):
        errors.append(f"{label}_coverage_names_mismatch")
    for index, row in enumerate(rows):
        if set(row) != _ROW_KEYS:
            errors.append(f"{label}_coverage_{index}_schema_mismatch")
            continue
        counts = {
            field: row.get(field)
            for field in _ROW_KEYS
            if field.endswith("_count")
        }
        if any(type(count) is not int or count < 0 for count in counts.values()):
            errors.append(f"{label}_coverage_{index}_count_invalid")
            continue
        episode_count = row["episode_count"]
        expected_status = "observed" if episode_count else "unobserved"
        if row.get("coverage_status") != expected_status:
            errors.append(f"{label}_coverage_{index}_status_mismatch")
        if episode_count != sum(
            row[field]
            for field in (
                "matured_episode_count",
                "due_missing_price_episode_count",
                "not_due_episode_count",
                "contract_excluded_episode_count",
            )
        ):
            errors.append(f"{label}_coverage_{index}_outcomes_not_closed")
        if row["aligned_episode_count"] > row["scoreable_directional_episode_count"]:
            errors.append(f"{label}_coverage_{index}_alignment_invalid")
        if row["scoreable_directional_episode_count"] > episode_count:
            errors.append(f"{label}_coverage_{index}_scoreable_invalid")
    return rows


def _validate_summary(
    value: Mapping[str, Any],
    *,
    route_rows: Sequence[Mapping[str, Any]],
    origin_rows: Sequence[Mapping[str, Any]],
    errors: list[str],
) -> None:
    count_fields = (
        "episode_count",
        "repeat_member_count",
        "matured_episode_count",
        "route_population_count",
        "observed_route_count",
        "zero_episode_route_count",
        "primary_origin_population_count",
        "observed_primary_origin_count",
        "zero_episode_primary_origin_count",
    )
    if any(type(value.get(field)) is not int or value.get(field) < 0 for field in count_fields):
        errors.append("frontier_count_invalid")
        return
    unobserved_routes = [
        row.get("name") for row in route_rows if row.get("episode_count") == 0
    ]
    unobserved_origins = [
        row.get("name") for row in origin_rows if row.get("episode_count") == 0
    ]
    if any((
        value.get("route_population_count") != len(CANONICAL_ROUTES),
        value.get("primary_origin_population_count")
        != len(CANONICAL_PRIMARY_ORIGINS),
        value.get("unobserved_route_names") != unobserved_routes,
        value.get("unobserved_primary_origin_names") != unobserved_origins,
        value.get("zero_episode_route_count") != len(unobserved_routes),
        value.get("zero_episode_primary_origin_count") != len(unobserved_origins),
        value.get("observed_route_count")
        != len(CANONICAL_ROUTES) - len(unobserved_routes),
        value.get("observed_primary_origin_count")
        != len(CANONICAL_PRIMARY_ORIGINS) - len(unobserved_origins),
        sum(row.get("episode_count", 0) for row in route_rows)
        != value.get("episode_count"),
        sum(row.get("episode_count", 0) for row in origin_rows)
        != value.get("episode_count"),
        sum(row.get("matured_episode_count", 0) for row in route_rows)
        != value.get("matured_episode_count"),
        sum(row.get("matured_episode_count", 0) for row in origin_rows)
        != value.get("matured_episode_count"),
    )):
        errors.append("frontier_summary_not_closed")
    complete = not unobserved_routes and not unobserved_origins
    if value.get("canonical_category_coverage_complete") is not complete:
        errors.append("frontier_complete_status_mismatch")
    expected_status = (
        "empty"
        if value.get("episode_count") == 0
        else "descriptive_complete_unsealed"
        if complete
        else "descriptive_incomplete"
    )
    if value.get("status") != expected_status:
        errors.append("frontier_status_mismatch")


def _nonnegative_int(value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("episode coverage count invalid")
    return value


def _is_sha256(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_utc_timestamp(value: object) -> bool:
    if type(value) is not str:
        return False
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    return (
        parsed.tzinfo is not None
        and parsed.utcoffset() == timezone.utc.utcoffset(parsed)
    )


def _digest(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = (
    "CANONICAL_PRIMARY_ORIGINS",
    "CANONICAL_ROUTES",
    "EPISODE_INDEPENDENCE_STATUS",
    "SCHEMA_ID",
    "SCHEMA_VERSION",
    "build_protocol_v2_episode_coverage_frontier",
    "validate_protocol_v2_episode_coverage_frontier",
)
