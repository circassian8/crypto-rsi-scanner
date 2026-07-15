"""Exact-snapshot adapter from counted Decision candidates to shadow episodes."""

from __future__ import annotations

import hashlib
import json
import math
import stat
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..outcomes import anomaly_episode_shadow, outcome_eligibility
from . import market_no_send_history_cache, market_observation_outcomes
from .market_no_send_io import parse_jsonl_bytes, read_regular_bytes
from .market_no_send_models import MarketNoSendError


INPUT_AUDIT_SCHEMA_ID = "event_alpha.shadow_anomaly_episode_input_audit"
INPUT_AUDIT_SCHEMA_VERSION = 1
_LEDGER_STATUSES = {"missing", "observed_empty", "observed", "unavailable"}
_INPUT_STATUSES = {"empty", "ready", "partial", "unavailable"}
_GENERATION_REJECTION_REASONS = {
    "generation_identity_invalid",
    "candidate_snapshot_missing",
    "candidate_snapshot_digest_invalid",
    "candidate_snapshot_size_invalid",
    "candidate_snapshot_artifact_invalid",
    "candidate_snapshot_binding_source_invalid",
    "candidate_snapshot_unverified",
}
_CANDIDATE_ROW_REJECTION_REASONS = {
    "source_origins_invalid",
    "candidate_authority_invalid",
    "candidate_generation_binding_invalid",
    "candidate_asset_identity_invalid",
    "market_anomaly_identity_invalid",
    "candidate_outcome_identity_invalid",
    "duplicate_candidate_identity",
}
_SNAPSHOT_BINDING_KEYS = {
    "artifact_namespace",
    "run_id",
    "candidate_artifact",
    "candidate_artifact_sha256",
    "candidate_artifact_size_bytes",
    "candidate_row_count",
    "binding_source",
}
_INPUT_AUDIT_KEYS = {
    "schema_id",
    "schema_version",
    "status",
    "candidate_input_status",
    "outcome_input_status",
    "input_status_reason_counts",
    "counted_generation_count",
    "candidate_snapshot_generation_count",
    "generation_rejection_count",
    "generation_rejection_reason_counts",
    "candidate_snapshot_bindings",
    "candidate_snapshot_binding_digest",
    "candidate_snapshot_row_count",
    "candidate_row_count",
    "market_anomaly_candidate_count",
    "out_of_scope_candidate_count",
    "unclassified_candidate_row_count",
    "candidate_authority_valid_count",
    "market_anomaly_candidate_rejection_count",
    "candidate_row_rejection_count",
    "candidate_row_rejection_reason_counts",
    "duplicate_candidate_group_count",
    "duplicate_candidate_row_count",
    "outcome_ledger_status",
    "outcome_ledger_sha256",
    "raw_outcome_row_count",
    "outcome_join_candidate_count",
    "exact_outcome_join_count",
    "missing_outcome_join_count",
    "ambiguous_outcome_join_count",
    "joined_outcome_row_count",
    "orphan_outcome_row_count",
    "outcome_evidence_status_counts",
    "invalid_outcome_row_count",
    "duplicate_outcome_identity_group_count",
    "duplicate_outcome_row_count",
    "conflicting_outcome_identity_group_count",
    "cross_candidate_outcome_collision_group_count",
    "cross_candidate_outcome_collision_candidate_count",
    "cross_candidate_outcome_collision_row_count",
    "episode_records_supplied",
    "episode_contract_digest",
    "episode_input_binding_digest",
    "provider_calls",
    "writes",
    "routing_changes",
    "priority_changes",
    "decision_score_changes",
    "score_adjustments",
    "calibration_changes",
    "threshold_changes",
    "authority_changes",
    "research_only",
    "auto_apply",
    "audit_digest",
}
_ZERO_SAFETY_FIELDS = (
    "provider_calls",
    "writes",
    "routing_changes",
    "priority_changes",
    "decision_score_changes",
    "score_adjustments",
    "calibration_changes",
    "threshold_changes",
    "authority_changes",
)
_INPUT_AUDIT_COUNT_FIELDS = (
    "counted_generation_count",
    "candidate_snapshot_generation_count",
    "generation_rejection_count",
    "candidate_snapshot_row_count",
    "candidate_row_count",
    "market_anomaly_candidate_count",
    "out_of_scope_candidate_count",
    "unclassified_candidate_row_count",
    "candidate_authority_valid_count",
    "market_anomaly_candidate_rejection_count",
    "candidate_row_rejection_count",
    "duplicate_candidate_group_count",
    "duplicate_candidate_row_count",
    "raw_outcome_row_count",
    "outcome_join_candidate_count",
    "exact_outcome_join_count",
    "missing_outcome_join_count",
    "ambiguous_outcome_join_count",
    "joined_outcome_row_count",
    "orphan_outcome_row_count",
    "invalid_outcome_row_count",
    "duplicate_outcome_identity_group_count",
    "duplicate_outcome_row_count",
    "conflicting_outcome_identity_group_count",
    "cross_candidate_outcome_collision_group_count",
    "cross_candidate_outcome_collision_candidate_count",
    "cross_candidate_outcome_collision_row_count",
    "episode_records_supplied",
)


def build_campaign_anomaly_episode_shadow(
    base: Path,
    generations: Sequence[Mapping[str, Any]],
    *,
    evaluated_at: Any,
    outcome_ledger_rows: Sequence[Mapping[str, Any]] | None = None,
    outcome_ledger_status: str | None = None,
    outcome_ledger_sha256: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return one pure episode value and its closed exact-input audit.

    The campaign builder supplies its already-captured candidate and outcome
    snapshots.  The optional ledger arguments retain compatibility for direct
    callers, while still reading the mutable ledger into one exact byte buffer.
    """

    candidates, candidate_audit = _counted_anomaly_candidates(generations)
    if outcome_ledger_rows is None:
        ledger_rows, ledger_status, ledger_sha256 = _raw_campaign_outcomes(base)
    else:
        ledger_rows = [dict(row) for row in outcome_ledger_rows]
        ledger_status = outcome_ledger_status
        ledger_sha256 = outcome_ledger_sha256
    if ledger_status not in _LEDGER_STATUSES:
        ledger_rows, ledger_status, ledger_sha256 = [], "unavailable", None
    records, outcome_audit = _episode_records(candidates, ledger_rows)
    value = anomaly_episode_shadow.build_shadow_anomaly_episodes(
        records,
        evaluated_at=evaluated_at,
    )
    audit = _build_input_audit(
        candidate_audit,
        outcome_audit,
        episode_value=value,
        ledger_status=ledger_status,
        ledger_sha256=ledger_sha256,
    )
    errors = validate_input_audit(audit, episode_value=value)
    if errors:
        raise MarketNoSendError(
            "shadow anomaly episode input audit invalid: " + ";".join(errors)
        )
    return value, audit


def validate_input_audit(
    audit: Mapping[str, Any],
    *,
    episode_value: Mapping[str, Any] | None = None,
) -> list[str]:
    """Validate exact keys, closure equations, digests, and safety constants."""

    if not isinstance(audit, Mapping):
        return ["audit_not_mapping"]
    errors: list[str] = []
    _validate_input_audit_header(audit, errors=errors)
    _validate_input_audit_counts(audit, errors=errors)
    _validate_input_audit_evidence(
        audit,
        episode_value=episode_value,
        errors=errors,
    )
    digest_values = dict(audit)
    digest_values.pop("audit_digest", None)
    if audit.get("audit_digest") != _digest(digest_values):
        errors.append("invalid_audit_digest")
    return sorted(set(errors))


def _validate_input_audit_header(
    audit: Mapping[str, Any],
    *,
    errors: list[str],
) -> None:
    _check_exact_keys(audit, _INPUT_AUDIT_KEYS, "audit", errors)
    if audit.get("schema_id") != INPUT_AUDIT_SCHEMA_ID:
        errors.append("invalid_schema_id")
    if type(audit.get("schema_version")) is not int or audit.get(
        "schema_version"
    ) != INPUT_AUDIT_SCHEMA_VERSION:
        errors.append("invalid_schema_version")
    if audit.get("status") not in _INPUT_STATUSES:
        errors.append("invalid_status")
    if audit.get("candidate_input_status") not in _INPUT_STATUSES:
        errors.append("invalid_candidate_input_status")
    if audit.get("outcome_input_status") not in _INPUT_STATUSES:
        errors.append("invalid_outcome_input_status")
    if audit.get("outcome_ledger_status") not in _LEDGER_STATUSES:
        errors.append("invalid_outcome_ledger_status")


def _validate_input_audit_counts(
    audit: Mapping[str, Any],
    *,
    errors: list[str],
) -> None:
    counts: dict[str, int] = {}
    for field in _INPUT_AUDIT_COUNT_FIELDS:
        value = audit.get(field)
        if type(value) is not int or value < 0:
            errors.append(f"invalid_{field}")
        else:
            counts[field] = value
    if len(counts) != len(_INPUT_AUDIT_COUNT_FIELDS):
        return
    equations = (
        (
            "generation_count_not_closed",
            counts["counted_generation_count"],
            counts["candidate_snapshot_generation_count"]
            + counts["generation_rejection_count"],
        ),
        (
            "candidate_snapshot_row_count_mismatch",
            counts["candidate_snapshot_row_count"],
            counts["candidate_row_count"],
        ),
        (
            "candidate_scope_count_not_closed",
            counts["candidate_row_count"],
            counts["market_anomaly_candidate_count"]
            + counts["out_of_scope_candidate_count"]
            + counts["unclassified_candidate_row_count"],
        ),
        (
            "market_candidate_count_not_closed",
            counts["market_anomaly_candidate_count"],
            counts["candidate_authority_valid_count"]
            + counts["market_anomaly_candidate_rejection_count"],
        ),
        (
            "candidate_rejection_count_not_closed",
            counts["candidate_row_rejection_count"],
            counts["market_anomaly_candidate_rejection_count"]
            + counts["unclassified_candidate_row_count"],
        ),
        (
            "outcome_join_count_not_closed",
            counts["candidate_authority_valid_count"],
            counts["exact_outcome_join_count"]
            + counts["missing_outcome_join_count"]
            + counts["ambiguous_outcome_join_count"],
        ),
        (
            "outcome_join_candidate_count_mismatch",
            counts["outcome_join_candidate_count"],
            counts["candidate_authority_valid_count"],
        ),
        (
            "outcome_row_count_not_closed",
            counts["raw_outcome_row_count"],
            counts["joined_outcome_row_count"]
            + counts["orphan_outcome_row_count"],
        ),
        (
            "episode_record_count_mismatch",
            counts["episode_records_supplied"],
            counts["candidate_authority_valid_count"],
        ),
    )
    errors.extend(reason for reason, left, right in equations if left != right)
    if counts["ambiguous_outcome_join_count"] != (
        counts["invalid_outcome_row_count"]
        + counts["duplicate_outcome_identity_group_count"]
        + counts["cross_candidate_outcome_collision_candidate_count"]
    ):
        errors.append("ambiguous_outcome_count_not_closed")
    if counts["joined_outcome_row_count"] != (
        counts["exact_outcome_join_count"]
        + counts["invalid_outcome_row_count"]
        + counts["duplicate_outcome_row_count"]
        + counts["cross_candidate_outcome_collision_row_count"]
    ):
        errors.append("joined_outcome_population_not_closed")
    if counts["conflicting_outcome_identity_group_count"] > counts[
        "duplicate_outcome_identity_group_count"
    ]:
        errors.append("conflicting_outcome_count_exceeds_duplicates")
    duplicate_groups = counts["duplicate_outcome_identity_group_count"]
    duplicate_rows = counts["duplicate_outcome_row_count"]
    if (duplicate_groups == 0) != (duplicate_rows == 0):
        errors.append("duplicate_outcome_zero_state_mismatch")
    if duplicate_rows < 2 * duplicate_groups:
        errors.append("duplicate_outcome_row_count_too_small")
    if duplicate_rows > counts["joined_outcome_row_count"]:
        errors.append("duplicate_outcome_rows_exceed_joined_population")
    collision_groups = counts["cross_candidate_outcome_collision_group_count"]
    collision_candidates = counts[
        "cross_candidate_outcome_collision_candidate_count"
    ]
    collision_rows = counts["cross_candidate_outcome_collision_row_count"]
    if len({collision_groups == 0, collision_candidates == 0, collision_rows == 0}) != 1:
        errors.append("cross_candidate_outcome_collision_zero_state_mismatch")
    if collision_candidates < 2 * collision_groups:
        errors.append("cross_candidate_outcome_collision_candidate_count_too_small")
    if collision_rows < collision_groups:
        errors.append("cross_candidate_outcome_collision_row_count_too_small")
    if collision_candidates > counts["ambiguous_outcome_join_count"]:
        errors.append("cross_candidate_outcome_collision_candidates_exceed_ambiguous")
    if collision_rows > counts["joined_outcome_row_count"]:
        errors.append("cross_candidate_outcome_collision_rows_exceed_joined_population")


def _validate_input_audit_evidence(
    audit: Mapping[str, Any],
    *,
    episode_value: Mapping[str, Any] | None,
    errors: list[str],
) -> None:
    _validate_reason_counts(
        audit,
        field="generation_rejection_reason_counts",
        expected=audit.get("generation_rejection_count"),
        allowed=_GENERATION_REJECTION_REASONS,
        errors=errors,
    )
    _validate_reason_counts(
        audit,
        field="candidate_row_rejection_reason_counts",
        expected=audit.get("candidate_row_rejection_count"),
        allowed=_CANDIDATE_ROW_REJECTION_REASONS,
        errors=errors,
    )
    _validate_candidate_rejection_closure(audit, errors=errors)
    _validate_reason_counts(
        audit,
        field="input_status_reason_counts",
        expected=None,
        allowed=None,
        errors=errors,
    )
    _validate_status_counts(
        audit.get("outcome_evidence_status_counts"),
        expected=audit.get("candidate_authority_valid_count"),
        errors=errors,
    )
    evidence = audit.get("outcome_evidence_status_counts")
    if isinstance(evidence, Mapping):
        if _nonnegative_int(evidence.get("ambiguous")) != _nonnegative_int(
            audit.get("ambiguous_outcome_join_count")
        ):
            errors.append("ambiguous_outcome_evidence_count_mismatch")
        if _nonnegative_int(evidence.get("available")) > _nonnegative_int(
            audit.get("exact_outcome_join_count")
        ):
            errors.append("available_outcome_evidence_exceeds_exact_joins")
        if _nonnegative_int(evidence.get("unavailable")) < _nonnegative_int(
            audit.get("missing_outcome_join_count")
        ):
            errors.append("unavailable_outcome_evidence_below_missing_joins")
    if audit.get("input_status_reason_counts") != _input_status_reason_counts(audit):
        errors.append("input_status_reason_counts_mismatch")
    _validate_snapshot_bindings(audit, errors=errors)
    _validate_ledger_binding(audit, errors=errors)
    for field in _ZERO_SAFETY_FIELDS:
        if type(audit.get(field)) is not int or audit.get(field) != 0:
            errors.append(f"invalid_{field}")
    if audit.get("research_only") is not True:
        errors.append("invalid_research_only")
    if audit.get("auto_apply") is not False:
        errors.append("invalid_auto_apply")

    expected_candidate_status = _candidate_input_status(audit)
    expected_outcome_status = _outcome_input_status(audit)
    expected_status = _overall_input_status(
        candidate_status=expected_candidate_status,
        outcome_status=expected_outcome_status,
        valid_candidates=_nonnegative_int(audit.get("candidate_authority_valid_count")),
    )
    if audit.get("candidate_input_status") != expected_candidate_status:
        errors.append("candidate_input_status_mismatch")
    if audit.get("outcome_input_status") != expected_outcome_status:
        errors.append("outcome_input_status_mismatch")
    if audit.get("status") != expected_status:
        errors.append("status_mismatch")

    if not _sha256_text(audit.get("episode_contract_digest")):
        errors.append("invalid_episode_contract_digest")
    if not _sha256_text(audit.get("episode_input_binding_digest")):
        errors.append("invalid_episode_input_binding_digest")
    if episode_value is not None:
        if audit.get("episode_contract_digest") != episode_value.get(
            "contract_digest"
        ):
            errors.append("episode_contract_digest_mismatch")
        if audit.get("episode_input_binding_digest") != episode_value.get(
            "input_binding_digest"
        ):
            errors.append("episode_input_binding_digest_mismatch")
        if audit.get("episode_records_supplied") != episode_value.get(
            "records_supplied"
        ):
            errors.append("episode_records_supplied_mismatch")


def _counted_anomaly_candidates(
    generations: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    generation_rejections: Counter[str] = Counter()
    row_rejections: Counter[str] = Counter()
    bindings: list[dict[str, Any]] = []
    provisional: list[dict[str, Any]] = []
    total = market_scope = out_of_scope = unclassified = 0
    counted = 0
    market_rejections = 0
    for generation in generations:
        if generation.get("campaign_counted") is not True:
            continue
        counted += 1
        reason = _generation_snapshot_rejection_reason(generation)
        if reason is not None:
            generation_rejections[reason] += 1
            continue
        snapshot_rows = generation.get("_candidate_snapshot_rows")
        assert isinstance(snapshot_rows, (list, tuple))
        binding = {
            "artifact_namespace": generation["artifact_namespace"],
            "run_id": generation["run_id"],
            "candidate_artifact": generation["_candidate_snapshot_artifact"],
            "candidate_artifact_sha256": generation[
                "_candidate_snapshot_sha256"
            ],
            "candidate_artifact_size_bytes": generation[
                "_candidate_snapshot_size_bytes"
            ],
            "candidate_row_count": len(snapshot_rows),
            "binding_source": generation["_candidate_snapshot_binding_source"],
        }
        bindings.append(binding)
        namespace = str(generation["artifact_namespace"])
        run_id = str(generation["run_id"])
        for source in snapshot_rows:
            total += 1
            candidate = dict(source)
            origins = candidate.get("source_origins")
            if not isinstance(origins, list) or not all(
                type(value) is str and value for value in origins
            ):
                unclassified += 1
                row_rejections["source_origins_invalid"] += 1
                continue
            if "market_anomaly" not in origins:
                out_of_scope += 1
                continue
            market_scope += 1
            reason = _candidate_rejection_reason(
                candidate,
                namespace=namespace,
                run_id=run_id,
            )
            if reason is not None:
                market_rejections += 1
                row_rejections[reason] += 1
                continue
            provisional.append(candidate)

    by_context: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in provisional:
        by_context[(str(row["artifact_namespace"]), str(row["candidate_id"]))].append(row)
    unique: list[dict[str, Any]] = []
    duplicate_rows = duplicate_groups = 0
    for grouped in by_context.values():
        if len(grouped) != 1:
            duplicate_groups += 1
            duplicate_rows += len(grouped)
            market_rejections += len(grouped)
            row_rejections["duplicate_candidate_identity"] += len(grouped)
            continue
        unique.append(grouped[0])
    unique.sort(key=_candidate_sort_key)
    bindings.sort(
        key=lambda row: (
            str(row["artifact_namespace"]),
            str(row["run_id"]),
        )
    )
    return unique, {
        "counted_generation_count": counted,
        "candidate_snapshot_generation_count": len(bindings),
        "generation_rejection_count": sum(generation_rejections.values()),
        "generation_rejection_reason_counts": dict(
            sorted(generation_rejections.items())
        ),
        "candidate_snapshot_bindings": bindings,
        "candidate_snapshot_binding_digest": _digest(bindings),
        "candidate_snapshot_row_count": sum(
            int(row["candidate_row_count"]) for row in bindings
        ),
        "candidate_row_count": total,
        "market_anomaly_candidate_count": market_scope,
        "out_of_scope_candidate_count": out_of_scope,
        "unclassified_candidate_row_count": unclassified,
        "candidate_authority_valid_count": len(unique),
        "market_anomaly_candidate_rejection_count": market_rejections,
        "candidate_row_rejection_count": sum(row_rejections.values()),
        "candidate_row_rejection_reason_counts": dict(sorted(row_rejections.items())),
        "duplicate_candidate_group_count": duplicate_groups,
        "duplicate_candidate_row_count": duplicate_rows,
    }


def _generation_snapshot_rejection_reason(
    generation: Mapping[str, Any],
) -> str | None:
    if not _exact_text(generation.get("artifact_namespace")) or not _exact_text(
        generation.get("run_id")
    ):
        return "generation_identity_invalid"
    rows = generation.get("_candidate_snapshot_rows")
    if not isinstance(rows, (list, tuple)) or not all(
        isinstance(row, Mapping) for row in rows
    ):
        return "candidate_snapshot_missing"
    if not _sha256_text(generation.get("_candidate_snapshot_sha256")):
        return "candidate_snapshot_digest_invalid"
    if type(generation.get("_candidate_snapshot_size_bytes")) is not int or generation.get(
        "_candidate_snapshot_size_bytes"
    ) < 0:
        return "candidate_snapshot_size_invalid"
    if generation.get("_candidate_snapshot_artifact") != (
        "event_integrated_radar_candidates.jsonl"
    ):
        return "candidate_snapshot_artifact_invalid"
    if generation.get("_candidate_snapshot_binding_source") not in {
        "manifest_candidate_artifact_sha256",
        "legacy_operator_candidate_binding",
    }:
        return "candidate_snapshot_binding_source_invalid"
    if generation.get("_candidate_snapshot_verified") is not True:
        return "candidate_snapshot_unverified"
    return None


def _candidate_rejection_reason(
    candidate: Mapping[str, Any],
    *,
    namespace: str,
    run_id: str,
) -> str | None:
    if not outcome_eligibility.valid_candidate_authority(candidate):
        return "candidate_authority_invalid"
    if (
        candidate.get("artifact_namespace") != namespace
        or candidate.get("run_id") != run_id
    ):
        return "candidate_generation_binding_invalid"
    coin_id = _exact_text(candidate.get("coin_id"))
    canonical_asset_id = _exact_text(candidate.get("canonical_asset_id"))
    if coin_id is None or canonical_asset_id is None or coin_id != canonical_asset_id:
        return "candidate_asset_identity_invalid"
    if _exact_text(candidate.get("market_anomaly_id")) is None:
        return "market_anomaly_identity_invalid"
    key = outcome_eligibility.build_outcome_identity_fields(candidate).get(
        "outcome_identity_key"
    )
    if not _sha256_text(key):
        return "candidate_outcome_identity_invalid"
    return None


def _raw_campaign_outcomes(
    base: Path,
) -> tuple[list[dict[str, Any]], str, str | None]:
    path = (
        base
        / market_no_send_history_cache.LIVE_HISTORY_CACHE_NAMESPACE
        / market_observation_outcomes.CAMPAIGN_OUTCOMES_FILENAME
    )
    try:
        parent = path.parent.lstat()
    except FileNotFoundError:
        return [], "missing", None
    except OSError:
        return [], "unavailable", None
    if not stat.S_ISDIR(parent.st_mode) or stat.S_ISLNK(parent.st_mode):
        return [], "unavailable", None
    try:
        raw = read_regular_bytes(path, missing_ok=True)
        if raw is None:
            return [], "missing", None
        rows = parse_jsonl_bytes(raw)
    except (MarketNoSendError, OSError, ValueError, RuntimeError):
        return [], "unavailable", None
    return (
        rows,
        "observed" if rows else "observed_empty",
        hashlib.sha256(raw).hexdigest(),
    )


def _episode_records(
    candidates: Sequence[Mapping[str, Any]],
    ledger_rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    component_by_candidate, used_indexes, component_counts = (
        _outcome_claim_components(candidates, ledger_rows)
    )
    duplicate_groups = component_counts["duplicate_groups"]
    duplicate_rows = component_counts["duplicate_rows"]
    conflict_groups = component_counts["conflict_groups"]
    collision_groups = component_counts["collision_groups"]
    collision_candidates = component_counts["collision_candidates"]
    collision_rows = component_counts["collision_rows"]
    invalid_rows = 0
    missing = exact = ambiguous = 0
    evidence_counts: Counter[str] = Counter()
    records: list[dict[str, Any]] = []
    for candidate_index, candidate in enumerate(candidates):
        namespace = str(candidate["artifact_namespace"])
        candidate_id = str(candidate["candidate_id"])
        identity = outcome_eligibility.build_outcome_identity_fields(candidate)
        identity_key = str(identity["outcome_identity_key"])
        component = component_by_candidate.get(candidate_index)
        evidence_status = "unavailable"
        evidence_reasons: list[str] = []
        primary_return: float | None = None
        if component is None:
            missing += 1
            evidence_reasons.append("outcome_ledger_missing")
        elif component[0] == "cross_candidate_collision":
            ambiguous += 1
            evidence_status = "ambiguous"
            evidence_reasons.append("outcome_row_claimed_by_multiple_candidates")
        elif component[0] == "duplicate_identity":
            ambiguous += 1
            evidence_status = "ambiguous"
            evidence_reasons.append("duplicate_outcome_identity")
            if len(
                {
                    _canonical_row(ledger_rows[index])
                    for index in component[1]
                }
            ) > 1:
                evidence_reasons.append("conflicting_outcome_identity")
        else:
            row = dict(ledger_rows[component[1][0]])
            if not market_observation_outcomes.campaign_ledger_outcome_valid(
                row,
                candidate,
                namespace=namespace,
            ):
                invalid_rows += 1
                ambiguous += 1
                evidence_status = "ambiguous"
                evidence_reasons.append("outcome_contract_invalid")
            else:
                exact += 1
                primary_return = _finite_number(row.get("primary_horizon_return"))
                if primary_return is None:
                    evidence_reasons.append("primary_outcome_unavailable")
                else:
                    evidence_status = "available"
        evidence_counts[evidence_status] += 1
        records.append({
            "artifact_namespace": namespace,
            "run_id": candidate["run_id"],
            "candidate_id": candidate_id,
            "outcome_identity_key": identity_key,
            "market_anomaly_id": candidate["market_anomaly_id"],
            "canonical_asset_id": candidate["canonical_asset_id"],
            "observed_at": candidate["observed_at"],
            "outcome_evidence_status": evidence_status,
            "outcome_evidence_reasons": sorted(set(evidence_reasons)),
            "primary_horizon_return": primary_return,
            "radar_route": candidate.get("radar_route"),
            "anomaly_type": candidate.get("anomaly_type"),
            "directional_bias": candidate.get("directional_bias"),
        })
    orphan_count = len(ledger_rows) - len(used_indexes)
    return records, {
        "raw_outcome_row_count": len(ledger_rows),
        "outcome_join_candidate_count": len(candidates),
        "exact_outcome_join_count": exact,
        "missing_outcome_join_count": missing,
        "ambiguous_outcome_join_count": ambiguous,
        "joined_outcome_row_count": len(used_indexes),
        "orphan_outcome_row_count": max(0, orphan_count),
        "outcome_evidence_status_counts": dict(sorted(evidence_counts.items())),
        "invalid_outcome_row_count": invalid_rows,
        "duplicate_outcome_identity_group_count": duplicate_groups,
        "duplicate_outcome_row_count": duplicate_rows,
        "conflicting_outcome_identity_group_count": conflict_groups,
        "cross_candidate_outcome_collision_group_count": collision_groups,
        "cross_candidate_outcome_collision_candidate_count": collision_candidates,
        "cross_candidate_outcome_collision_row_count": collision_rows,
    }


def _outcome_claim_components(
    candidates: Sequence[Mapping[str, Any]],
    ledger_rows: Sequence[Mapping[str, Any]],
) -> tuple[
    dict[int, tuple[str, tuple[int, ...]]],
    set[int],
    dict[str, int],
]:
    contexts: dict[tuple[str, str], list[int]] = defaultdict(list)
    keys: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(ledger_rows):
        namespace = _exact_text(row.get("source_artifact_namespace"))
        candidate_id = _exact_text(row.get("candidate_id"))
        if namespace is not None and candidate_id is not None:
            contexts[(namespace, candidate_id)].append(index)
        key = row.get("outcome_identity_key")
        if _sha256_text(key):
            keys[str(key)].append(index)

    candidate_claims: list[set[int]] = []
    reverse_claims: dict[int, list[int]] = defaultdict(list)
    for candidate_index, candidate in enumerate(candidates):
        identity = outcome_eligibility.build_outcome_identity_fields(candidate)
        indexes = set(keys.get(str(identity["outcome_identity_key"]), ()))
        indexes.update(
            contexts.get(
                (str(candidate["artifact_namespace"]), str(candidate["candidate_id"])),
                (),
            )
        )
        candidate_claims.append(indexes)
        for index in indexes:
            reverse_claims[index].append(candidate_index)

    used_indexes = set(reverse_claims)
    component_by_candidate: dict[int, tuple[str, tuple[int, ...]]] = {}
    duplicate_groups = duplicate_rows = conflict_groups = 0
    collision_groups = collision_candidates = collision_rows = 0
    unvisited = {
        candidate_index
        for candidate_index, indexes in enumerate(candidate_claims)
        if indexes
    }
    while unvisited:
        pending = [min(unvisited)]
        component_candidates: set[int] = set()
        component_rows: set[int] = set()
        while pending:
            candidate_index = pending.pop()
            if candidate_index in component_candidates:
                continue
            component_candidates.add(candidate_index)
            unvisited.discard(candidate_index)
            for row_index in candidate_claims[candidate_index]:
                component_rows.add(row_index)
                pending.extend(reverse_claims[row_index])
        row_indexes = tuple(sorted(component_rows))
        if len(component_candidates) > 1:
            component_kind = "cross_candidate_collision"
            collision_groups += 1
            collision_candidates += len(component_candidates)
            collision_rows += len(component_rows)
        elif len(component_rows) > 1:
            component_kind = "duplicate_identity"
            duplicate_groups += 1
            duplicate_rows += len(component_rows)
            if len(
                {_canonical_row(ledger_rows[index]) for index in component_rows}
            ) > 1:
                conflict_groups += 1
        else:
            component_kind = "single"
        for candidate_index in component_candidates:
            component_by_candidate[candidate_index] = (
                component_kind,
                row_indexes,
            )
    return component_by_candidate, used_indexes, {
        "duplicate_groups": duplicate_groups,
        "duplicate_rows": duplicate_rows,
        "conflict_groups": conflict_groups,
        "collision_groups": collision_groups,
        "collision_candidates": collision_candidates,
        "collision_rows": collision_rows,
    }


def _build_input_audit(
    candidate_audit: Mapping[str, Any],
    outcome_audit: Mapping[str, Any],
    *,
    episode_value: Mapping[str, Any],
    ledger_status: str,
    ledger_sha256: str | None,
) -> dict[str, Any]:
    base = {
        "schema_id": INPUT_AUDIT_SCHEMA_ID,
        "schema_version": INPUT_AUDIT_SCHEMA_VERSION,
        **dict(candidate_audit),
        "outcome_ledger_status": ledger_status,
        "outcome_ledger_sha256": ledger_sha256,
        **dict(outcome_audit),
        "episode_records_supplied": int(episode_value["records_supplied"]),
        "episode_contract_digest": episode_value["contract_digest"],
        "episode_input_binding_digest": episode_value["input_binding_digest"],
        "provider_calls": 0,
        "writes": 0,
        "routing_changes": 0,
        "priority_changes": 0,
        "decision_score_changes": 0,
        "score_adjustments": 0,
        "calibration_changes": 0,
        "threshold_changes": 0,
        "authority_changes": 0,
        "research_only": True,
        "auto_apply": False,
    }
    candidate_status = _candidate_input_status(base)
    outcome_status = _outcome_input_status(base)
    base["candidate_input_status"] = candidate_status
    base["outcome_input_status"] = outcome_status
    base["status"] = _overall_input_status(
        candidate_status=candidate_status,
        outcome_status=outcome_status,
        valid_candidates=int(base["candidate_authority_valid_count"]),
    )
    base["input_status_reason_counts"] = _input_status_reason_counts(base)
    base["audit_digest"] = _digest(base)
    return base


def _candidate_input_status(audit: Mapping[str, Any]) -> str:
    counted = _nonnegative_int(audit.get("counted_generation_count"))
    snapshots = _nonnegative_int(audit.get("candidate_snapshot_generation_count"))
    rows = _nonnegative_int(audit.get("candidate_snapshot_row_count"))
    rejected_generations = _nonnegative_int(audit.get("generation_rejection_count"))
    rejected_rows = _nonnegative_int(audit.get("candidate_row_rejection_count"))
    if counted > 0 and snapshots == 0 and rejected_generations > 0:
        return "unavailable"
    if counted == 0 or (rows == 0 and rejected_generations == 0):
        return "empty"
    if rejected_generations or rejected_rows:
        return "partial"
    return "ready"


def _outcome_input_status(audit: Mapping[str, Any]) -> str:
    candidates = _nonnegative_int(audit.get("candidate_authority_valid_count"))
    if candidates == 0:
        return "empty"
    ledger_status = audit.get("outcome_ledger_status")
    if ledger_status in {"missing", "unavailable"}:
        return "unavailable"
    counts = audit.get("outcome_evidence_status_counts")
    available = (
        _nonnegative_int(counts.get("available"))
        if isinstance(counts, Mapping)
        else 0
    )
    return "ready" if available == candidates else "partial"


def _overall_input_status(
    *,
    candidate_status: str,
    outcome_status: str,
    valid_candidates: int,
) -> str:
    if candidate_status == "unavailable":
        return "unavailable"
    if valid_candidates == 0:
        return "empty" if candidate_status in {"empty", "ready"} else "partial"
    return "ready" if candidate_status == outcome_status == "ready" else "partial"


def _input_status_reason_counts(audit: Mapping[str, Any]) -> dict[str, int]:
    reasons: Counter[str] = Counter()
    generation_rejections = _nonnegative_int(audit.get("generation_rejection_count"))
    row_rejections = _nonnegative_int(audit.get("candidate_row_rejection_count"))
    if generation_rejections:
        reasons["candidate_generation_rejected"] = generation_rejections
    if row_rejections:
        reasons["candidate_row_rejected"] = row_rejections
    if _nonnegative_int(audit.get("candidate_authority_valid_count")) == 0:
        reasons["no_eligible_market_anomaly_candidate"] = 1
    ledger_status = audit.get("outcome_ledger_status")
    if ledger_status != "observed":
        reasons[f"outcome_ledger_{ledger_status}"] = 1
    evidence = audit.get("outcome_evidence_status_counts")
    if isinstance(evidence, Mapping):
        for status, count in evidence.items():
            numeric = _nonnegative_int(count)
            if status != "available" and numeric:
                reasons[f"outcome_evidence_{status}"] = numeric
    return dict(sorted(reasons.items()))


def _validate_snapshot_bindings(
    audit: Mapping[str, Any],
    *,
    errors: list[str],
) -> None:
    bindings = audit.get("candidate_snapshot_bindings")
    if type(bindings) is not list:
        errors.append("candidate_snapshot_bindings_not_list")
        return
    row_total = 0
    sort_keys: list[tuple[str, str]] = []
    for index, binding in enumerate(bindings):
        if type(binding) is not dict:
            errors.append(f"candidate_snapshot_binding_{index}:not_object")
            continue
        _check_exact_keys(
            binding,
            _SNAPSHOT_BINDING_KEYS,
            f"candidate_snapshot_binding_{index}",
            errors,
        )
        if not _exact_text(binding.get("artifact_namespace")):
            errors.append(f"candidate_snapshot_binding_{index}:invalid_namespace")
        if not _exact_text(binding.get("run_id")):
            errors.append(f"candidate_snapshot_binding_{index}:invalid_run_id")
        if binding.get("candidate_artifact") != (
            "event_integrated_radar_candidates.jsonl"
        ):
            errors.append(f"candidate_snapshot_binding_{index}:invalid_artifact")
        if not _sha256_text(binding.get("candidate_artifact_sha256")):
            errors.append(f"candidate_snapshot_binding_{index}:invalid_sha256")
        for field in ("candidate_artifact_size_bytes", "candidate_row_count"):
            if type(binding.get(field)) is not int or binding.get(field) < 0:
                errors.append(f"candidate_snapshot_binding_{index}:invalid_{field}")
        if binding.get("binding_source") not in {
            "manifest_candidate_artifact_sha256",
            "legacy_operator_candidate_binding",
        }:
            errors.append(f"candidate_snapshot_binding_{index}:invalid_binding_source")
        row_total += _nonnegative_int(binding.get("candidate_row_count"))
        sort_keys.append(
            (str(binding.get("artifact_namespace") or ""), str(binding.get("run_id") or ""))
        )
    if sort_keys != sorted(sort_keys) or len(sort_keys) != len(set(sort_keys)):
        errors.append("candidate_snapshot_bindings_not_unique_sorted")
    if len(bindings) != audit.get("candidate_snapshot_generation_count"):
        errors.append("candidate_snapshot_generation_count_mismatch")
    if row_total != audit.get("candidate_snapshot_row_count"):
        errors.append("candidate_snapshot_binding_row_count_mismatch")
    if audit.get("candidate_snapshot_binding_digest") != _digest(bindings):
        errors.append("candidate_snapshot_binding_digest_mismatch")


def _validate_ledger_binding(
    audit: Mapping[str, Any],
    *,
    errors: list[str],
) -> None:
    status = audit.get("outcome_ledger_status")
    digest = audit.get("outcome_ledger_sha256")
    rows = _nonnegative_int(audit.get("raw_outcome_row_count"))
    if status in {"missing", "unavailable"}:
        if digest is not None or rows != 0:
            errors.append("invalid_unavailable_ledger_binding")
    elif status == "observed_empty":
        if not _sha256_text(digest) or rows != 0:
            errors.append("invalid_empty_ledger_binding")
    elif status == "observed":
        if not _sha256_text(digest) or rows == 0:
            errors.append("invalid_observed_ledger_binding")


def _validate_reason_counts(
    audit: Mapping[str, Any],
    *,
    field: str,
    expected: object,
    allowed: set[str] | None,
    errors: list[str],
) -> None:
    value = audit.get(field)
    if type(value) is not dict or any(
        not _exact_text(key) or type(count) is not int or count < 1
        for key, count in (value.items() if type(value) is dict else ())
    ):
        errors.append(f"invalid_{field}")
        return
    if allowed is not None and not set(value).issubset(allowed):
        errors.append(f"invalid_{field}_reason")
    if expected is not None and sum(value.values()) != expected:
        errors.append(f"{field}_count_mismatch")


def _validate_candidate_rejection_closure(
    audit: Mapping[str, Any],
    *,
    errors: list[str],
) -> None:
    reasons = audit.get("candidate_row_rejection_reason_counts")
    if type(reasons) is not dict or any(
        key not in _CANDIDATE_ROW_REJECTION_REASONS
        or type(count) is not int
        or count < 1
        for key, count in (reasons.items() if type(reasons) is dict else ())
    ):
        return
    source_origin_rejections = int(reasons.get("source_origins_invalid", 0))
    market_rejections = sum(
        int(count)
        for reason, count in reasons.items()
        if reason != "source_origins_invalid"
    )
    duplicate_rows = _nonnegative_int(audit.get("duplicate_candidate_row_count"))
    duplicate_groups = _nonnegative_int(
        audit.get("duplicate_candidate_group_count")
    )
    if source_origin_rejections != audit.get("unclassified_candidate_row_count"):
        errors.append("unclassified_candidate_rejection_count_mismatch")
    if market_rejections != audit.get("market_anomaly_candidate_rejection_count"):
        errors.append("market_candidate_rejection_reason_count_mismatch")
    if duplicate_rows != int(reasons.get("duplicate_candidate_identity", 0)):
        errors.append("duplicate_candidate_rejection_count_mismatch")
    if (duplicate_groups == 0) != (duplicate_rows == 0):
        errors.append("duplicate_candidate_zero_state_mismatch")
    if duplicate_rows < 2 * duplicate_groups:
        errors.append("duplicate_candidate_row_count_too_small")
    if duplicate_rows > _nonnegative_int(audit.get("market_anomaly_candidate_count")):
        errors.append("duplicate_candidate_rows_exceed_market_population")
    if duplicate_rows > _nonnegative_int(
        audit.get("market_anomaly_candidate_rejection_count")
    ):
        errors.append("duplicate_candidate_rows_exceed_rejections")


def _validate_status_counts(
    value: object,
    *,
    expected: object,
    errors: list[str],
) -> None:
    if type(value) is not dict or any(
        key not in {"available", "unavailable", "ambiguous"}
        or type(count) is not int
        or count < 1
        for key, count in (value.items() if type(value) is dict else ())
    ):
        errors.append("invalid_outcome_evidence_status_counts")
        return
    if type(expected) is int and sum(value.values()) != expected:
        errors.append("outcome_evidence_status_counts_not_closed")


def _candidate_sort_key(row: Mapping[str, Any]) -> tuple[str, ...]:
    return (
        str(row.get("observed_at") or ""),
        str(row.get("canonical_asset_id") or ""),
        str(row.get("artifact_namespace") or ""),
        str(row.get("run_id") or ""),
        str(row.get("candidate_id") or ""),
    )


def _canonical_row(row: Mapping[str, Any]) -> str:
    try:
        return json.dumps(
            row,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError):
        return "invalid:" + repr(
            sorted((str(key), type(value).__name__) for key, value in row.items())
        )


def _digest(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _check_exact_keys(
    row: Mapping[str, Any],
    expected: set[str],
    prefix: str,
    errors: list[str],
) -> None:
    actual = set(row)
    errors.extend(f"{prefix}:missing_key:{key}" for key in sorted(expected - actual))
    errors.extend(f"{prefix}:unknown_key:{key}" for key in sorted(actual - expected))


def _exact_text(value: object) -> str | None:
    return (
        value
        if type(value) is str
        and bool(value)
        and value == value.strip()
        and not any(ord(character) < 32 for character in value)
        else None
    )


def _sha256_text(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    converted = float(value)
    return converted if math.isfinite(converted) else None


def _nonnegative_int(value: object) -> int:
    return value if type(value) is int and value >= 0 else 0


__all__ = (
    "INPUT_AUDIT_SCHEMA_ID",
    "build_campaign_anomaly_episode_shadow",
    "validate_input_audit",
)
