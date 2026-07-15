"""Pure shadow declustering for exact market-anomaly outcome observations.

The contract deliberately does not estimate independent sample size.  It forms
fixed, half-open episode windows from the first observation in each episode;
canonical outcome horizons remain separate evidence and may overlap.  Nothing
in this module changes routing, priority, scores, calibration, or thresholds.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping

from .anomaly_episode_partition import (
    aware_time as _aware_time,
    decluster_identity_refs as _decluster_identity_refs,
    identity_collision_errors as _identity_collision_errors,
    identity_ref_sort_key as _identity_ref_sort_key,
    identity_sensitivity_counts as _identity_sensitivity_counts,
    required_window_end as _required_window_end,
    safe_window_end as _safe_window_end,
)


SCHEMA_ID = "event_alpha.shadow_anomaly_episodes"
EPISODE_SCHEMA_ID = "event_alpha.shadow_anomaly_episode"
SCHEMA_VERSION = 1
METHOD = "fixed_start_window_declustering"
PRIMARY_GAP_HOURS = 24
SENSITIVITY_GAP_HOURS = (12, 24, 48)
MAX_MEMBER_REFS = 256
MAX_EXCLUSION_REFS = 256

_REQUIRED_TEXT_FIELDS = (
    "artifact_namespace",
    "run_id",
    "candidate_id",
    "outcome_identity_key",
    "market_anomaly_id",
    "canonical_asset_id",
)
_OPTIONAL_CONTEXT_FIELDS = (
    "radar_route",
    "anomaly_type",
    "directional_bias",
)
_OUTCOME_EVIDENCE_STATUSES = {"available", "unavailable", "ambiguous"}
_FALSE_POLICY = {
    "routing_eligible": False,
    "priority_eligible": False,
    "decision_score_eligible": False,
    "score_adjustment_eligible": False,
    "calibration_eligible": False,
    "threshold_change_eligible": False,
    "auto_apply": False,
}
_ROOT_KEYS = {
    "schema_id",
    "schema_version",
    "method",
    "status",
    "evaluated_at",
    "boundary_rule",
    "primary_gap_hours",
    "sensitivity_gap_hours",
    "records_supplied",
    "records_eligible",
    "records_excluded",
    "primary_episode_count",
    "primary_repeat_member_count",
    "sensitivity_counts",
    "episodes",
    "exclusion_reason_counts",
    "exclusion_digest",
    "exclusion_ref_count",
    "exclusion_refs",
    "exclusion_refs_truncated",
    "input_binding_digest",
    "statistical_independence_claim",
    "cross_asset_independence_claim",
    "validation_coverage",
    "research_only",
    "contract_digest",
    *_FALSE_POLICY,
}
_EPISODE_KEYS = {
    "schema_id",
    "schema_version",
    "method",
    "episode_id",
    "episode_digest",
    "canonical_asset_id",
    "episode_start_at",
    "last_member_observed_at",
    "window_end_exclusive_at",
    "primary_gap_hours",
    "member_count",
    "representative",
    "member_binding_digest",
    "member_ref_count",
    "member_refs",
    "member_refs_truncated",
    "outcome_evidence_status_counts",
    "statistical_independence_claim",
    "cross_asset_independence_claim",
    "research_only",
    *_FALSE_POLICY,
}
_MEMBER_REF_KEYS = {
    *_REQUIRED_TEXT_FIELDS,
    "observed_at",
    "outcome_evidence_status",
    "outcome_evidence_reasons",
    "primary_horizon_return",
    *_OPTIONAL_CONTEXT_FIELDS,
    "record_digest",
}
_EXCLUSION_REF_KEYS = {"record_digest", "reason_codes", "occurrence_count"}
_VALIDATION_COVERAGE = {
    "member_refs": "complete_with_hard_bound",
    "max_member_refs": MAX_MEMBER_REFS,
    "exclusion_refs": "complete_with_hard_bound",
    "max_exclusion_refs": MAX_EXCLUSION_REFS,
    "full_membership_bound_by_digest": True,
    "validator_full_member_recomputation": "always",
    "validator_full_exclusion_recomputation": "always",
    "sensitivity_count_validation": "full_partition_recomputation",
    "bound_exceeded_policy": "fail_closed_without_contract",
}


@dataclass(frozen=True)
class _Member:
    artifact_namespace: str
    run_id: str
    candidate_id: str
    outcome_identity_key: str
    market_anomaly_id: str
    canonical_asset_id: str
    observed_at: str
    observed_time: datetime
    outcome_evidence_status: str
    outcome_evidence_reasons: tuple[str, ...]
    primary_horizon_return: float | None
    radar_route: str | None
    anomaly_type: str | None
    directional_bias: str | None
    record_digest: str

    def identity_ref(self) -> dict[str, str]:
        return {
            "artifact_namespace": self.artifact_namespace,
            "run_id": self.run_id,
            "candidate_id": self.candidate_id,
            "outcome_identity_key": self.outcome_identity_key,
            "market_anomaly_id": self.market_anomaly_id,
            "canonical_asset_id": self.canonical_asset_id,
            "observed_at": self.observed_at,
        }

    def public_ref(self) -> dict[str, Any]:
        return {
            **self.identity_ref(),
            "outcome_evidence_status": self.outcome_evidence_status,
            "outcome_evidence_reasons": list(self.outcome_evidence_reasons),
            "primary_horizon_return": self.primary_horizon_return,
            "radar_route": self.radar_route,
            "anomaly_type": self.anomaly_type,
            "directional_bias": self.directional_bias,
            "record_digest": self.record_digest,
        }


@dataclass(frozen=True)
class _Exclusion:
    record_digest: str
    reason_codes: tuple[str, ...]


def build_shadow_anomaly_episodes(
    records: Iterable[Mapping[str, Any]],
    *,
    evaluated_at: datetime | str,
) -> dict[str, Any]:
    """Return the closed v1 shadow episode contract without mutating inputs."""

    evaluated = _required_evaluation_time(evaluated_at)
    supplied = list(records)
    members: list[_Member] = []
    exclusions: list[_Exclusion] = []
    for raw in supplied:
        member, reasons, record_digest = _member_from_record(
            raw,
            evaluated_at=evaluated,
        )
        if member is None:
            exclusions.append(_Exclusion(record_digest, tuple(sorted(reasons))))
        else:
            members.append(member)
    members, ambiguous = _exclude_ambiguous_bindings(members)
    exclusions.extend(ambiguous)
    ordered_members = tuple(sorted(members, key=_member_sort_key))
    primary_groups = _decluster(ordered_members, gap_hours=PRIMARY_GAP_HOURS)
    episodes = [_episode_payload(group) for group in primary_groups]
    exclusion_payload = _exclusion_payload(exclusions)
    sensitivity_counts = {}
    for gap in SENSITIVITY_GAP_HOURS:
        episode_count = len(_decluster(ordered_members, gap_hours=gap))
        sensitivity_counts[f"{gap}h"] = {
            "episode_count": episode_count,
            "repeat_member_count": len(ordered_members) - episode_count,
        }
    primary_repeat_count = len(ordered_members) - len(episodes)
    payload: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "method": METHOD,
        "status": "empty" if not supplied else "partial" if exclusions else "ready",
        "evaluated_at": evaluated.isoformat(),
        "boundary_rule": "member_observed_at_lt_episode_start_plus_window",
        "primary_gap_hours": PRIMARY_GAP_HOURS,
        "sensitivity_gap_hours": list(SENSITIVITY_GAP_HOURS),
        "records_supplied": len(supplied),
        "records_eligible": len(ordered_members),
        "records_excluded": len(supplied) - len(ordered_members),
        "primary_episode_count": len(episodes),
        "primary_repeat_member_count": primary_repeat_count,
        "sensitivity_counts": sensitivity_counts,
        "episodes": episodes,
        **exclusion_payload,
        "input_binding_digest": _digest(
            [member.identity_ref() for member in ordered_members]
        ),
        "statistical_independence_claim": False,
        "cross_asset_independence_claim": False,
        "validation_coverage": dict(_VALIDATION_COVERAGE),
        "research_only": True,
        **_FALSE_POLICY,
    }
    payload["contract_digest"] = _digest(payload)
    errors = validate_contract(payload)
    if errors:
        raise RuntimeError(
            "shadow_anomaly_episode_contract_invalid:" + ";".join(errors)
        )
    return payload


def validate_contract(payload: Mapping[str, Any]) -> list[str]:
    """Validate the closed persisted projection and its bounded evidence."""

    if not isinstance(payload, Mapping):
        return ["contract_not_mapping"]
    errors: list[str] = []
    _check_exact_keys(payload, _ROOT_KEYS, "contract", errors)
    expected_values = {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "method": METHOD,
        "boundary_rule": "member_observed_at_lt_episode_start_plus_window",
        "primary_gap_hours": PRIMARY_GAP_HOURS,
        "sensitivity_gap_hours": list(SENSITIVITY_GAP_HOURS),
        "statistical_independence_claim": False,
        "cross_asset_independence_claim": False,
        "validation_coverage": _VALIDATION_COVERAGE,
        "research_only": True,
        **_FALSE_POLICY,
    }
    for key, expected in expected_values.items():
        if payload.get(key) != expected or type(payload.get(key)) is not type(expected):
            errors.append(f"invalid_{key}")
    try:
        evaluated = _required_evaluation_time(payload.get("evaluated_at"))
    except (TypeError, ValueError):
        evaluated = None
        errors.append("invalid_evaluated_at")
    errors.extend(_validate_root_counts(payload))
    errors.extend(_validate_sensitivity_counts(payload))
    errors.extend(_validate_episode_contracts(payload, evaluated_at=evaluated))
    errors.extend(_validate_exclusion_contract(payload))
    if not _is_sha256(payload.get("input_binding_digest")):
        errors.append("invalid_input_binding_digest")
    contract_digest = payload.get("contract_digest")
    digest_values = dict(payload)
    digest_values.pop("contract_digest", None)
    if not _digest_matches(contract_digest, digest_values):
        errors.append("invalid_contract_digest")
    return sorted(set(errors))


def _validate_root_counts(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    count_names = (
        "records_supplied",
        "records_eligible",
        "records_excluded",
        "primary_episode_count",
        "primary_repeat_member_count",
        "exclusion_ref_count",
    )
    counts: dict[str, int] = {}
    for name in count_names:
        value = payload.get(name)
        if type(value) is not int or value < 0:
            errors.append(f"invalid_{name}")
        else:
            counts[name] = value
    if len(counts) != len(count_names):
        return errors
    if counts["records_supplied"] != (
        counts["records_eligible"] + counts["records_excluded"]
    ):
        errors.append("record_count_not_closed")
    if counts["primary_episode_count"] + counts["primary_repeat_member_count"] != (
        counts["records_eligible"]
    ):
        errors.append("primary_count_not_closed")
    episodes = payload.get("episodes")
    if type(episodes) is not list or len(episodes) != counts["primary_episode_count"]:
        errors.append("primary_episode_count_mismatch")
    expected_status = (
        "empty"
        if counts["records_supplied"] == 0
        else "partial"
        if counts["records_excluded"] > 0
        else "ready"
    )
    if type(payload.get("status")) is not str or payload.get("status") != expected_status:
        errors.append("invalid_status")
    return errors


def _validate_sensitivity_counts(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    counts = payload.get("sensitivity_counts")
    expected_keys = {f"{gap}h" for gap in SENSITIVITY_GAP_HOURS}
    if type(counts) is not dict or set(counts) != expected_keys:
        return ["invalid_sensitivity_counts"]
    eligible = payload.get("records_eligible")
    episode_values: list[int] = []
    repeat_values: list[int] = []
    for gap in SENSITIVITY_GAP_HOURS:
        row = counts.get(f"{gap}h")
        if type(row) is not dict or set(row) != {
            "episode_count",
            "repeat_member_count",
        }:
            errors.append(f"invalid_sensitivity_{gap}h")
            continue
        episode_count = row.get("episode_count")
        repeat_count = row.get("repeat_member_count")
        if (
            type(episode_count) is not int
            or episode_count < 0
            or type(repeat_count) is not int
            or repeat_count < 0
        ):
            errors.append(f"invalid_sensitivity_{gap}h")
            continue
        if type(eligible) is int and episode_count + repeat_count != eligible:
            errors.append(f"sensitivity_{gap}h_not_closed")
        episode_values.append(episode_count)
        repeat_values.append(repeat_count)
        if gap == PRIMARY_GAP_HOURS and (
            episode_count != payload.get("primary_episode_count")
            or repeat_count != payload.get("primary_repeat_member_count")
        ):
            errors.append("primary_sensitivity_mismatch")
    if len(episode_values) == 3 and episode_values != sorted(
        episode_values,
        reverse=True,
    ):
        errors.append("sensitivity_episode_counts_not_monotonic")
    if len(repeat_values) == 3 and repeat_values != sorted(repeat_values):
        errors.append("sensitivity_repeat_counts_not_monotonic")
    return errors


def _validate_episode_contracts(
    payload: Mapping[str, Any],
    *,
    evaluated_at: datetime | None,
) -> list[str]:
    episodes = payload.get("episodes")
    if type(episodes) is not list:
        return ["episodes_not_list"]
    errors: list[str] = []
    exposed_identities: list[dict[str, str]] = []
    actual_partition_digests: list[object] = []
    episode_order: list[tuple[Any, ...]] = []
    asset_windows: dict[str, list[tuple[datetime, datetime]]] = defaultdict(list)
    member_total = 0
    for index, episode in enumerate(episodes):
        episode_errors, identities, window = _validate_episode(
            episode,
            evaluated_at=evaluated_at,
        )
        errors.extend(f"episode_{index}:{error}" for error in episode_errors)
        if type(episode) is dict:
            member_count = episode.get("member_count")
            if type(member_count) is int and member_count >= 0:
                member_total += member_count
            exposed_identities.extend(identities)
            actual_partition_digests.append(episode.get("member_binding_digest"))
            if window is not None:
                asset_id, start, end, order_key = window
                asset_windows[asset_id].append((start, end))
                episode_order.append(order_key)
    if member_total != payload.get("records_eligible"):
        errors.append("episode_member_count_not_closed")
    if episode_order != sorted(episode_order):
        errors.append("episodes_not_canonically_ordered")
    for windows in asset_windows.values():
        ordered = sorted(windows)
        if any(current[0] < previous[1] for previous, current in zip(ordered, ordered[1:])):
            errors.append("primary_episode_windows_overlap")
    ordered_identities = sorted(exposed_identities, key=_identity_ref_sort_key)
    if len(ordered_identities) != payload.get("records_eligible"):
        errors.append("exposed_member_count_mismatch")
    if payload.get("input_binding_digest") != _digest(ordered_identities):
        errors.append("input_binding_digest_mismatch")
    errors.extend(_identity_collision_errors(ordered_identities))
    expected_groups = _decluster_identity_refs(
        ordered_identities,
        gap_hours=PRIMARY_GAP_HOURS,
    )
    if actual_partition_digests != [_digest(group) for group in expected_groups]:
        errors.append("primary_episode_partition_mismatch")
    if payload.get("sensitivity_counts") != _identity_sensitivity_counts(
        ordered_identities,
        gap_hours=SENSITIVITY_GAP_HOURS,
    ):
        errors.append("sensitivity_partition_mismatch")
    return errors


def _validate_episode(
    episode: object,
    *,
    evaluated_at: datetime | None,
) -> tuple[list[str], list[dict[str, str]], tuple[Any, ...] | None]:
    if type(episode) is not dict:
        return ["not_object"], [], None
    errors: list[str] = []
    _check_exact_keys(episode, _EPISODE_KEYS, "episode", errors)
    for key, expected in {
        "schema_id": EPISODE_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "method": METHOD,
        "primary_gap_hours": PRIMARY_GAP_HOURS,
        "statistical_independence_claim": False,
        "cross_asset_independence_claim": False,
        "research_only": True,
        **_FALSE_POLICY,
    }.items():
        if episode.get(key) != expected or type(episode.get(key)) is not type(expected):
            errors.append(f"invalid_{key}")
    asset_id = episode.get("canonical_asset_id")
    if not _valid_exact_text(asset_id, maximum=256):
        errors.append("invalid_canonical_asset_id")
    start = _aware_time(episode.get("episode_start_at"))
    last = _aware_time(episode.get("last_member_observed_at"))
    end = _aware_time(episode.get("window_end_exclusive_at"))
    if start is None or last is None or end is None:
        errors.append("invalid_episode_times")
    else:
        for field, parsed in (
            ("episode_start_at", start),
            ("last_member_observed_at", last),
            ("window_end_exclusive_at", end),
        ):
            if episode.get(field) != parsed.isoformat():
                errors.append(f"{field}_not_canonical_utc")
        expected_end = _safe_window_end(start, gap_hours=PRIMARY_GAP_HOURS)
        if expected_end is None:
            errors.append("episode_window_overflow")
        elif last < start or end != expected_end or last >= end:
            errors.append("invalid_episode_boundary")
    identities = _validate_episode_members(
        episode,
        asset_id=asset_id if type(asset_id) is str else None,
        start=start,
        end=end,
        evaluated_at=evaluated_at,
        errors=errors,
    )
    _validate_episode_digests(episode, identities=identities, errors=errors)
    order_key = None
    if start is not None and end is not None and type(asset_id) is str:
        representative = episode.get("representative")
        suffix = _identity_ref_sort_key(representative) if type(representative) is dict else ()
        order_key = (start, asset_id, *suffix[2:])
    window = (asset_id, start, end, order_key) if order_key is not None else None
    return errors, identities, window


def _validate_episode_members(
    episode: Mapping[str, Any],
    *,
    asset_id: str | None,
    start: datetime | None,
    end: datetime | None,
    evaluated_at: datetime | None,
    errors: list[str],
) -> list[dict[str, str]]:
    member_count = episode.get("member_count")
    refs = episode.get("member_refs")
    ref_count = episode.get("member_ref_count")
    truncated = episode.get("member_refs_truncated")
    if type(member_count) is not int or member_count < 1:
        errors.append("invalid_member_count")
        member_count = 0
    if type(refs) is not list or type(ref_count) is not int or type(truncated) is not bool:
        errors.append("invalid_member_refs")
        return []
    if (
        member_count > MAX_MEMBER_REFS
        or ref_count != len(refs)
        or ref_count != member_count
    ):
        errors.append("member_ref_count_mismatch")
    if truncated is not False:
        errors.append("member_ref_truncation_mismatch")
    identities: list[dict[str, str]] = []
    times: list[datetime] = []
    for index, ref in enumerate(refs):
        ref_errors, identity, observed = _validate_member_ref(ref)
        errors.extend(f"member_ref_{index}:{error}" for error in ref_errors)
        if identity is not None:
            identities.append(identity)
            if identity["canonical_asset_id"] != asset_id:
                errors.append(f"member_ref_{index}:asset_mismatch")
        if observed is not None:
            times.append(observed)
            if start is not None and end is not None and not (start <= observed < end):
                errors.append(f"member_ref_{index}:outside_episode_window")
            if evaluated_at is not None and observed > evaluated_at:
                errors.append(f"member_ref_{index}:future_observation")
    representative = episode.get("representative")
    if not refs or representative != refs[0]:
        errors.append("representative_not_first_member")
    if times != sorted(times):
        errors.append("member_refs_not_time_ordered")
    if identities != sorted(identities, key=_identity_ref_sort_key):
        errors.append("member_refs_not_canonically_ordered")
    if start is not None and times and times[0] != start:
        errors.append("representative_start_mismatch")
    if times and _aware_time(episode.get("last_member_observed_at")) != times[-1]:
        errors.append("last_member_time_mismatch")
    _validate_outcome_status_counts(
        episode,
        member_count=member_count,
        refs=refs,
        errors=errors,
    )
    return identities


def _validate_member_ref(
    ref: object,
) -> tuple[list[str], dict[str, str] | None, datetime | None]:
    if type(ref) is not dict:
        return ["not_object"], None, None
    errors: list[str] = []
    _check_exact_keys(ref, _MEMBER_REF_KEYS, "member_ref", errors)
    identity: dict[str, str] = {}
    for field in _REQUIRED_TEXT_FIELDS:
        value = ref.get(field)
        if field == "outcome_identity_key" and not _is_sha256(value):
            errors.append(f"invalid_{field}")
        elif not _valid_exact_text(value, maximum=256):
            errors.append(f"invalid_{field}")
        else:
            identity[field] = value
    observed = _aware_time(ref.get("observed_at"))
    if observed is None:
        errors.append("invalid_observed_at")
    else:
        identity["observed_at"] = observed.isoformat()
        if ref.get("observed_at") != observed.isoformat():
            errors.append("observed_at_not_canonical_utc")
    status = ref.get("outcome_evidence_status")
    if type(status) is not str or status not in _OUTCOME_EVIDENCE_STATUSES:
        errors.append("invalid_outcome_evidence_status")
    reasons = ref.get("outcome_evidence_reasons")
    if (
        type(reasons) is not list
        or not all(_valid_exact_text(reason, maximum=128) for reason in reasons)
        or reasons != sorted(set(reasons))
    ):
        errors.append("invalid_outcome_evidence_reasons")
    primary_return = ref.get("primary_horizon_return")
    if primary_return is not None and (
        type(primary_return) is not float or _finite_number(primary_return) is None
    ):
        errors.append("invalid_primary_horizon_return")
    if status == "available" and primary_return is None:
        errors.append("available_outcome_without_value")
    if status != "available" and primary_return is not None:
        errors.append("nonavailable_outcome_with_value")
    for field in _OPTIONAL_CONTEXT_FIELDS:
        value = ref.get(field)
        if value is not None and not _valid_exact_text(value, maximum=128):
            errors.append(f"invalid_{field}")
    digest = ref.get("record_digest")
    if len(identity) == len(_REQUIRED_TEXT_FIELDS) + 1:
        if not _is_sha256(digest) or digest != _digest(identity):
            errors.append("invalid_record_digest")
    elif not _is_sha256(digest):
        errors.append("invalid_record_digest")
    return errors, identity if len(identity) == len(_REQUIRED_TEXT_FIELDS) + 1 else None, observed


def _validate_episode_digests(
    episode: Mapping[str, Any],
    *,
    identities: list[dict[str, str]],
    errors: list[str],
) -> None:
    member_digest = episode.get("member_binding_digest")
    if not _is_sha256(member_digest):
        errors.append("invalid_member_binding_digest")
    if episode.get("episode_id") != f"shadow-anomaly-episode-v1:{member_digest}":
        errors.append("invalid_episode_id")
    if not _digest_matches(member_digest, identities):
        errors.append("member_binding_digest_mismatch")
    episode_digest = episode.get("episode_digest")
    if not _digest_matches(episode_digest, _episode_digest_values(episode)):
        errors.append("invalid_episode_digest")


def _validate_outcome_status_counts(
    episode: Mapping[str, Any],
    *,
    member_count: int,
    refs: list[Any],
    errors: list[str],
) -> None:
    counts = episode.get("outcome_evidence_status_counts")
    if type(counts) is not dict or any(
        type(key) is not str
        or key not in _OUTCOME_EVIDENCE_STATUSES
        or type(value) is not int
        or value < 1
        for key, value in (counts.items() if type(counts) is dict else ())
    ):
        errors.append("invalid_outcome_evidence_status_counts")
        return
    if sum(counts.values()) != member_count:
        errors.append("outcome_evidence_status_count_mismatch")
    recomputed = dict(sorted(Counter(
        ref.get("outcome_evidence_status")
        for ref in refs
        if type(ref) is dict
        and ref.get("outcome_evidence_status") in _OUTCOME_EVIDENCE_STATUSES
    ).items()))
    if counts != recomputed:
        errors.append("outcome_evidence_status_counts_not_recomputed")


def _validate_exclusion_contract(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    refs = payload.get("exclusion_refs")
    ref_count = payload.get("exclusion_ref_count")
    truncated = payload.get("exclusion_refs_truncated")
    reason_counts = payload.get("exclusion_reason_counts")
    if type(refs) is not list or type(ref_count) is not int or type(truncated) is not bool:
        return ["invalid_exclusion_refs"]
    if (
        ref_count != len(refs)
        or ref_count > MAX_EXCLUSION_REFS
        or truncated is not False
    ):
        errors.append("exclusion_ref_count_mismatch")
    occurrence_total = 0
    recomputed_reasons: Counter[str] = Counter()
    sort_keys: list[tuple[Any, ...]] = []
    for index, ref in enumerate(refs):
        if type(ref) is not dict:
            errors.append(f"exclusion_ref_{index}:not_object")
            continue
        _check_exact_keys(ref, _EXCLUSION_REF_KEYS, f"exclusion_ref_{index}", errors)
        digest = ref.get("record_digest")
        reasons = ref.get("reason_codes")
        count = ref.get("occurrence_count")
        if not _is_sha256(digest):
            errors.append(f"exclusion_ref_{index}:invalid_record_digest")
        if (
            type(reasons) is not list
            or not reasons
            or not all(_valid_exact_text(reason, maximum=128) for reason in reasons)
            or reasons != sorted(set(reasons))
        ):
            errors.append(f"exclusion_ref_{index}:invalid_reason_codes")
            reasons = []
        if type(count) is not int or count < 1:
            errors.append(f"exclusion_ref_{index}:invalid_occurrence_count")
            count = 0
        occurrence_total += count
        recomputed_reasons.update({reason: count for reason in reasons})
        sort_keys.append((str(digest or ""), tuple(reasons)))
    if sort_keys != sorted(sort_keys):
        errors.append("exclusion_refs_not_canonically_ordered")
    if type(reason_counts) is not dict or any(
        not _valid_exact_text(key, maximum=128)
        or type(value) is not int
        or value < 1
        for key, value in (reason_counts.items() if type(reason_counts) is dict else ())
    ):
        errors.append("invalid_exclusion_reason_counts")
    if occurrence_total != payload.get("records_excluded"):
        errors.append("exclusion_count_not_closed")
    if reason_counts != dict(sorted(recomputed_reasons.items())):
        errors.append("exclusion_reason_counts_mismatch")
    if not _digest_matches(payload.get("exclusion_digest"), refs):
        errors.append("exclusion_digest_mismatch")
    return errors


def _check_exact_keys(
    row: Mapping[str, Any],
    expected: set[str],
    prefix: str,
    errors: list[str],
) -> None:
    actual = set(row)
    for key in sorted(expected - actual, key=str):
        errors.append(f"{prefix}:missing_key:{key}")
    for key in sorted(actual - expected, key=str):
        errors.append(f"{prefix}:unknown_key:{key}")


def _is_sha256(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _digest_matches(expected: object, value: object) -> bool:
    if not _is_sha256(expected):
        return False
    try:
        return expected == _digest(value)
    except (OverflowError, TypeError, ValueError):
        return False


def _member_from_record(
    raw: object,
    *,
    evaluated_at: datetime,
) -> tuple[_Member | None, tuple[str, ...], str]:
    record_digest = _safe_record_digest(raw)
    if not isinstance(raw, Mapping):
        return None, ("record_not_mapping",), record_digest
    reasons: list[str] = []
    values: dict[str, str] = {}
    for field in _REQUIRED_TEXT_FIELDS:
        value = raw.get(field)
        if field == "outcome_identity_key" and not _is_sha256(value):
            reasons.append(f"invalid_{field}")
        elif not _valid_exact_text(value, maximum=256):
            reasons.append(f"invalid_{field}")
        else:
            values[field] = value
    observed = _aware_time(raw.get("observed_at"))
    if observed is None:
        reasons.append("invalid_observed_at")
    if reasons or observed is None:
        return None, tuple(sorted(set(reasons))), record_digest
    identity = {
        **values,
        "observed_at": observed.isoformat(),
    }
    record_digest = _digest(identity)
    if observed > evaluated_at:
        return None, ("future_observation",), record_digest
    if _safe_window_end(
        observed,
        gap_hours=max(SENSITIVITY_GAP_HOURS),
    ) is None:
        return None, ("observation_window_overflow",), record_digest
    status, status_reasons, primary_return = _outcome_evidence(raw)
    context = {
        field: _optional_exact_text(raw.get(field), maximum=128)
        for field in _OPTIONAL_CONTEXT_FIELDS
    }
    member = _Member(
        **values,
        observed_at=observed.isoformat(),
        observed_time=observed,
        outcome_evidence_status=status,
        outcome_evidence_reasons=status_reasons,
        primary_horizon_return=primary_return,
        radar_route=context["radar_route"],
        anomaly_type=context["anomaly_type"],
        directional_bias=context["directional_bias"],
        record_digest=record_digest,
    )
    return member, (), record_digest


def _outcome_evidence(
    raw: Mapping[str, Any],
) -> tuple[str, tuple[str, ...], float | None]:
    supplied_status = raw.get("outcome_evidence_status")
    supplied_reasons = raw.get("outcome_evidence_reasons")
    reasons: list[str] = []
    if supplied_reasons is not None:
        if (
            type(supplied_reasons) is list
            and all(type(value) is str for value in supplied_reasons)
            and supplied_reasons == sorted(set(supplied_reasons))
            and all(
                _valid_exact_text(value, maximum=128)
                for value in supplied_reasons
            )
        ):
            reasons.extend(supplied_reasons)
        else:
            reasons.append("outcome_evidence_reasons_invalid")
    if supplied_status is None:
        status = "unavailable"
        reasons.append("outcome_evidence_not_supplied")
    elif type(supplied_status) is str and supplied_status in _OUTCOME_EVIDENCE_STATUSES:
        status = supplied_status
    else:
        status = "unavailable"
        reasons.append("outcome_evidence_status_invalid")
    raw_return = raw.get("primary_horizon_return")
    primary_return = _finite_number(raw_return)
    if status == "available" and primary_return is None:
        status = "unavailable"
        reasons.append("available_outcome_missing_finite_primary_return")
    elif status != "available" and raw_return is not None:
        primary_return = None
        reasons.append("nonavailable_outcome_value_ignored")
    return status, tuple(sorted(set(reasons))), primary_return


def _exclude_ambiguous_bindings(
    members: Iterable[_Member],
) -> tuple[list[_Member], list[_Exclusion]]:
    rows = list(members)
    reasons: dict[int, set[str]] = defaultdict(set)
    contracts = (
        (
            "ambiguous_candidate_binding",
            lambda row: (row.artifact_namespace, row.run_id, row.candidate_id),
        ),
        (
            "ambiguous_outcome_binding",
            lambda row: (
                row.artifact_namespace,
                row.run_id,
                row.outcome_identity_key,
            ),
        ),
        (
            "ambiguous_anomaly_binding",
            lambda row: (row.artifact_namespace, row.run_id, row.market_anomaly_id),
        ),
    )
    for reason, key_for in contracts:
        grouped: dict[tuple[str, ...], list[int]] = defaultdict(list)
        for index, row in enumerate(rows):
            grouped[key_for(row)].append(index)
        for indexes in grouped.values():
            if len(indexes) > 1:
                for index in indexes:
                    reasons[index].add(reason)
    eligible = [row for index, row in enumerate(rows) if index not in reasons]
    excluded = [
        _Exclusion(rows[index].record_digest, tuple(sorted(reason_codes)))
        for index, reason_codes in reasons.items()
    ]
    return eligible, excluded


def _decluster(
    members: Iterable[_Member],
    *,
    gap_hours: int,
) -> list[tuple[_Member, ...]]:
    by_asset: dict[str, list[_Member]] = defaultdict(list)
    for member in members:
        by_asset[member.canonical_asset_id].append(member)
    episodes: list[tuple[_Member, ...]] = []
    for asset_id in sorted(by_asset):
        ordered = sorted(by_asset[asset_id], key=_member_sort_key)
        current: list[_Member] = []
        episode_end: datetime | None = None
        for member in ordered:
            if episode_end is None or member.observed_time >= episode_end:
                if current:
                    episodes.append(tuple(current))
                current = [member]
                episode_end = _required_window_end(
                    member.observed_time,
                    gap_hours=gap_hours,
                )
            else:
                current.append(member)
        if current:
            episodes.append(tuple(current))
    return sorted(episodes, key=lambda group: _member_sort_key(group[0]))


def _episode_payload(members: tuple[_Member, ...]) -> dict[str, Any]:
    representative = members[0]
    identity_refs = [member.identity_ref() for member in members]
    member_digest = _digest(identity_refs)
    public_refs = [member.public_ref() for member in members]
    if len(public_refs) > MAX_MEMBER_REFS:
        raise ValueError("shadow anomaly episode member bound exceeded")
    status_counts = dict(sorted(Counter(
        member.outcome_evidence_status for member in members
    ).items()))
    payload: dict[str, Any] = {
        "schema_id": EPISODE_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "method": METHOD,
        "episode_id": f"shadow-anomaly-episode-v1:{member_digest}",
        "canonical_asset_id": representative.canonical_asset_id,
        "episode_start_at": representative.observed_at,
        "last_member_observed_at": members[-1].observed_at,
        "window_end_exclusive_at": _required_window_end(
            representative.observed_time,
            gap_hours=PRIMARY_GAP_HOURS,
        ).isoformat(),
        "primary_gap_hours": PRIMARY_GAP_HOURS,
        "member_count": len(members),
        "representative": representative.public_ref(),
        "member_binding_digest": member_digest,
        "member_ref_count": len(public_refs),
        "member_refs": public_refs,
        "member_refs_truncated": False,
        "outcome_evidence_status_counts": status_counts,
        "statistical_independence_claim": False,
        "cross_asset_independence_claim": False,
        "research_only": True,
        **_FALSE_POLICY,
    }
    payload["episode_digest"] = _digest(_episode_digest_values(payload))
    return payload


def _episode_digest_values(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: payload.get(key)
        for key in (
            "schema_id",
            "schema_version",
            "method",
            "episode_id",
            "canonical_asset_id",
            "episode_start_at",
            "last_member_observed_at",
            "window_end_exclusive_at",
            "primary_gap_hours",
            "member_count",
            "member_binding_digest",
            "member_ref_count",
            "member_refs_truncated",
            "statistical_independence_claim",
            "cross_asset_independence_claim",
            "research_only",
            *_FALSE_POLICY,
        )
    }


def _exclusion_payload(exclusions: Iterable[_Exclusion]) -> dict[str, Any]:
    grouped: Counter[tuple[str, tuple[str, ...]]] = Counter(
        (item.record_digest, item.reason_codes) for item in exclusions
    )
    entries = [
        {
            "record_digest": record_digest,
            "reason_codes": list(reason_codes),
            "occurrence_count": count,
        }
        for (record_digest, reason_codes), count in sorted(grouped.items())
    ]
    if len(entries) > MAX_EXCLUSION_REFS:
        raise ValueError("shadow anomaly episode exclusion bound exceeded")
    reason_counts = Counter(
        reason
        for item in exclusions
        for reason in item.reason_codes
    )
    return {
        "exclusion_reason_counts": dict(sorted(reason_counts.items())),
        "exclusion_digest": _digest(entries),
        "exclusion_ref_count": len(entries),
        "exclusion_refs": entries,
        "exclusion_refs_truncated": False,
    }


def _member_sort_key(member: _Member) -> tuple[Any, ...]:
    return (
        member.observed_time,
        member.canonical_asset_id,
        member.artifact_namespace,
        member.run_id,
        member.candidate_id,
        member.outcome_identity_key,
        member.market_anomaly_id,
    )


def _required_evaluation_time(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif type(value) is str and value == value.strip() and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("evaluated_at must be an aware UTC timestamp") from exc
    else:
        raise ValueError("evaluated_at must be an aware UTC timestamp")
    if (
        parsed.tzinfo is None
        or parsed.utcoffset() is None
        or parsed.utcoffset() != timedelta(0)
    ):
        raise ValueError("evaluated_at must be an aware UTC timestamp")
    return parsed.astimezone(timezone.utc)


def _valid_exact_text(value: object, *, maximum: int) -> bool:
    return (
        type(value) is str
        and 0 < len(value) <= maximum
        and value == value.strip()
        and not any(ord(character) < 32 for character in value)
    )


def _optional_exact_text(value: object, *, maximum: int) -> str | None:
    return value if _valid_exact_text(value, maximum=maximum) else None


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        result = float(value)
    except (OverflowError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return 0.0 if result == 0.0 else result


def _safe_record_digest(raw: object) -> str:
    if not isinstance(raw, Mapping):
        return _digest({"record_type": type(raw).__name__})
    projection = {
        field: _safe_digest_value(raw.get(field))
        for field in (
            *_REQUIRED_TEXT_FIELDS,
            "observed_at",
        )
    }
    return _digest(projection)


def _safe_digest_value(value: object) -> object:
    if value is None or type(value) in {str, bool, int}:
        return value
    if type(value) is float:
        return value if math.isfinite(value) else {"nonfinite": str(value)}
    return {"invalid_type": type(value).__name__}


def _digest(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


__all__ = (
    "EPISODE_SCHEMA_ID",
    "MAX_EXCLUSION_REFS",
    "MAX_MEMBER_REFS",
    "METHOD",
    "PRIMARY_GAP_HOURS",
    "SCHEMA_ID",
    "SCHEMA_VERSION",
    "SENSITIVITY_GAP_HOURS",
    "build_shadow_anomaly_episodes",
    "validate_contract",
)
