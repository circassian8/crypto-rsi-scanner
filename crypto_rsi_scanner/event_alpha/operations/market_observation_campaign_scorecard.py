"""Read-once adapter from campaign snapshots to the Decision episode scorecard.

The adapter deliberately consumes only in-memory generation and ledger
snapshots.  It never reopens an artifact, rewrites source rows, or substitutes
the immutable per-generation outcome placeholders for the mutable campaign
outcome authority.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping, Sequence

from ..outcomes import anomaly_episode_shadow, decision_episode_scorecard
from ..outcomes.decision_episode_scorecard_contract import (
    OUTCOME_VALIDATION_SCHEMA_ID,
)
from . import market_no_send_history_cache, market_observation_outcomes
from .market_no_send_models import MarketNoSendError


_GENERATION_SOURCE_ROLES = {
    "candidate": "candidate",
    "core": "core",
}
_SNAPSHOT_LABELS = ("candidate", "core", "integrated_outcome")
_LEDGER_OBSERVED_STATUSES = {"observed", "observed_empty"}
_UNKNOWN_SCORE_COHORTS = {
    "actionability_score_cohort": "unknown",
    "evidence_confidence_score_cohort": "unknown",
    "risk_score_cohort": "unknown",
}


def build_campaign_decision_episode_scorecard(
    episode_value: Mapping[str, Any],
    episode_input_generations: Iterable[Mapping[str, Any]],
    campaign_ledger_snapshot: Mapping[str, Any],
    *,
    evaluated_at: Any,
) -> dict[str, Any]:
    """Build the closed scorecard from already-captured exact snapshots only.

    Every generation named by an episode member must resolve exactly once.
    Full candidate/Core artifacts from those generations and the full campaign
    ledger are retained so their original byte digests and row counts remain
    truthful.  Invalid ledger joins receive explicit invalid validation
    bindings and therefore cannot become scoreable representatives.
    """

    episode_errors = anomaly_episode_shadow.validate_contract(episode_value)
    if episode_errors:
        raise MarketNoSendError(
            "decision episode scorecard source episode invalid: "
            + ";".join(episode_errors)
        )
    generation_rows = _materialize_mappings(
        episode_input_generations,
        label="episode input generation",
    )
    required_identities = _episode_generation_identities(episode_value)
    selected = _select_episode_generations(generation_rows, required_identities)

    candidate_rows: list[dict[str, Any]] = []
    core_rows: list[dict[str, Any]] = []
    source_bindings: list[dict[str, Any]] = []
    for generation in selected:
        namespace, run_id = _generation_identity(generation)
        snapshots = {
            label: _generation_snapshot(
                generation,
                label=label,
                namespace=namespace,
                run_id=run_id,
            )
            for label in _SNAPSHOT_LABELS
        }
        for label, role in _GENERATION_SOURCE_ROLES.items():
            snapshot = snapshots[label]
            rows = snapshot["rows"]
            if label == "candidate":
                candidate_rows.extend(rows)
            else:
                core_rows.extend(rows)
            source_bindings.append(
                _source_binding(
                    snapshot,
                    source_role=role,
                    artifact_namespace=namespace,
                    run_id=run_id,
                )
            )

    outcome_rows, outcome_binding = _campaign_ledger_rows_and_binding(
        campaign_ledger_snapshot
    )
    if outcome_binding is not None:
        source_bindings.append(outcome_binding)
    validations = _campaign_outcome_validation_bindings(
        outcome_rows,
        candidate_rows=candidate_rows,
    )
    try:
        return decision_episode_scorecard.build_decision_episode_scorecard(
            episode_value,
            candidate_rows,
            core_rows,
            outcome_rows,
            evaluated_at=evaluated_at,
            source_artifact_bindings=source_bindings,
            outcome_validation_bindings=validations,
        )
    except (RuntimeError, TypeError, ValueError) as exc:
        raise MarketNoSendError(
            "decision episode scorecard adapter failed: " + str(exc)
        ) from exc


def _episode_generation_identities(
    episode_value: Mapping[str, Any],
) -> tuple[tuple[str, str], ...]:
    identities: set[tuple[str, str]] = set()
    for episode in episode_value.get("episodes", ()):
        for ref in episode.get("member_refs", ()):
            namespace = ref.get("artifact_namespace")
            run_id = ref.get("run_id")
            if not _exact_text(namespace) or not _exact_text(run_id):
                raise MarketNoSendError(
                    "decision episode member generation identity invalid"
                )
            identities.add((namespace, run_id))
    return tuple(sorted(identities))


def _select_episode_generations(
    generations: Sequence[Mapping[str, Any]],
    identities: Sequence[tuple[str, str]],
) -> tuple[Mapping[str, Any], ...]:
    indexed: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for generation in generations:
        identity = _optional_generation_identity(generation)
        if identity is not None:
            indexed.setdefault(identity, []).append(generation)
    selected: list[Mapping[str, Any]] = []
    for identity in identities:
        matches = indexed.get(identity, ())
        if len(matches) != 1:
            status = "missing" if not matches else "ambiguous"
            raise MarketNoSendError(
                "decision episode member generation "
                f"{status}: {identity[0]}|{identity[1]}"
            )
        selected.append(matches[0])
    return tuple(selected)


def _generation_snapshot(
    generation: Mapping[str, Any],
    *,
    label: str,
    namespace: str,
    run_id: str,
) -> dict[str, Any]:
    prefix = f"_{label}_snapshot_"
    raw_rows = generation.get(prefix + "rows")
    rows = _materialize_mappings(raw_rows, label=f"{label} snapshot row")
    artifact = generation.get(prefix + "artifact")
    digest = generation.get(prefix + "sha256")
    size_bytes = generation.get(prefix + "size_bytes")
    row_count = generation.get(prefix + "row_count")
    binding_source = generation.get(prefix + "binding_source")
    verified = generation.get(prefix + "verified")
    if any((
        verified is not True,
        not _artifact_name(artifact),
        not _sha256_digest(digest),
        type(size_bytes) is not int or size_bytes < 0,
        type(row_count) is not int or row_count != len(rows),
        not _exact_text(binding_source),
    )):
        raise MarketNoSendError(f"decision scorecard {label} snapshot metadata invalid")
    # Candidate/Core rows participate in exact scorecard joins and therefore
    # must carry their generation identity. Integrated outcome rows are not a
    # scorecard authority; their exact artifact bytes are still verified here,
    # but historical rows need not contain the newer namespace/run fields.
    if label != "integrated_outcome":
        for row in rows:
            if (
                row.get("artifact_namespace") != namespace
                or row.get("run_id") != run_id
            ):
                raise MarketNoSendError(
                    f"decision scorecard {label} snapshot generation mismatch"
                )
    return {
        "artifact": artifact,
        "sha256": digest,
        "size_bytes": size_bytes,
        "row_count": row_count,
        "binding_source": binding_source,
        "rows": rows,
    }


def _source_binding(
    snapshot: Mapping[str, Any],
    *,
    source_role: str,
    artifact_namespace: str,
    run_id: str,
) -> dict[str, Any]:
    return {
        "source_role": source_role,
        "artifact_namespace": artifact_namespace,
        "run_id": run_id,
        "artifact_name": snapshot["artifact"],
        "artifact_sha256": snapshot["sha256"],
        "artifact_size_bytes": snapshot["size_bytes"],
        "row_count": snapshot["row_count"],
        "binding_source": snapshot["binding_source"],
    }


def _campaign_ledger_rows_and_binding(
    snapshot: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    if not isinstance(snapshot, Mapping):
        raise MarketNoSendError("decision scorecard campaign ledger snapshot invalid")
    rows = _materialize_mappings(
        snapshot.get("rows"),
        label="campaign outcome ledger row",
    )
    status = snapshot.get("status")
    row_count = snapshot.get("row_count")
    if type(row_count) is not int or row_count != len(rows):
        raise MarketNoSendError(
            "decision scorecard campaign ledger row count mismatch"
        )
    if status not in _LEDGER_OBSERVED_STATUSES:
        if any((rows, row_count != 0, snapshot.get("sha256") is not None)):
            raise MarketNoSendError(
                "decision scorecard unavailable campaign ledger is not empty"
            )
        return [], None
    artifact = snapshot.get("artifact")
    digest = snapshot.get("sha256")
    size_bytes = snapshot.get("size_bytes")
    binding_source = snapshot.get("binding_source")
    if any((
        not _artifact_name(artifact),
        not _sha256_digest(digest),
        type(size_bytes) is not int or size_bytes < 0,
        not _exact_text(binding_source),
        status == "observed" and not rows,
        status == "observed_empty" and bool(rows),
    )):
        raise MarketNoSendError(
            "decision scorecard campaign ledger binding invalid"
        )
    binding = {
        "source_role": "outcome",
        "artifact_namespace": (
            market_no_send_history_cache.LIVE_HISTORY_CACHE_NAMESPACE
        ),
        "run_id": f"campaign-ledger-snapshot:{digest}",
        "artifact_name": artifact,
        "artifact_sha256": digest,
        "artifact_size_bytes": size_bytes,
        "row_count": row_count,
        "binding_source": binding_source,
    }
    return rows, binding


def _campaign_outcome_validation_bindings(
    outcomes: Sequence[Mapping[str, Any]],
    *,
    candidate_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    candidate_index: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for candidate in candidate_rows:
        namespace = candidate.get("artifact_namespace")
        candidate_id = candidate.get("candidate_id")
        if _exact_text(namespace) and _exact_text(candidate_id):
            candidate_index.setdefault((namespace, candidate_id), []).append(candidate)

    bindings: list[dict[str, Any]] = []
    for outcome in outcomes:
        outcome_digest = _digest(outcome)
        namespace = outcome.get("source_artifact_namespace")
        candidate_id = outcome.get("candidate_id")
        outcome_identity_key = outcome.get("outcome_identity_key")
        join_reasons: list[str] = []
        candidates = (
            candidate_index.get((namespace, candidate_id), ())
            if _exact_text(namespace) and _exact_text(candidate_id)
            else ()
        )
        if not _exact_text(namespace) or not _exact_text(candidate_id):
            join_reasons.append("campaign_outcome_candidate_identity_invalid")
        elif not candidates:
            join_reasons.append("campaign_outcome_candidate_binding_missing")
        elif len(candidates) > 1:
            join_reasons.append("campaign_outcome_candidate_binding_ambiguous")
        candidate = candidates[0] if len(candidates) == 1 else {}
        validation = market_observation_outcomes.campaign_ledger_outcome_validation(
            outcome,
            candidate,
            namespace=namespace if _exact_text(namespace) else "",
        )
        reasons = sorted(set((*validation.reasons, *join_reasons)))
        cohorts = dict(validation.canonical_score_cohorts)
        if set(cohorts) != set(_UNKNOWN_SCORE_COHORTS):
            cohorts = dict(_UNKNOWN_SCORE_COHORTS)
        binding = {
            "schema_id": OUTCOME_VALIDATION_SCHEMA_ID,
            "schema_version": 1,
            "artifact_namespace": namespace if _exact_text(namespace) else None,
            "candidate_id": candidate_id if _exact_text(candidate_id) else None,
            "outcome_identity_key": (
                outcome_identity_key
                if _sha256_digest(outcome_identity_key)
                else None
            ),
            "outcome_row_digest": outcome_digest,
            "valid": validation.valid and not join_reasons,
            "reasons": reasons,
            "score_cohort_status": (
                validation.score_cohort_status
                if not join_reasons
                else "invalid"
            ),
            "score_cohort_reason": (
                validation.score_cohort_reason
                if not join_reasons
                else join_reasons[0]
            ),
            "canonical_score_cohorts": cohorts,
        }
        bindings.append(binding)
    return bindings


def _materialize_mappings(value: Any, *, label: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise MarketNoSendError(f"{label} collection invalid")
    if not all(isinstance(row, Mapping) for row in value):
        raise MarketNoSendError(f"{label} invalid")
    return [dict(row) for row in value]


def _optional_generation_identity(
    generation: Mapping[str, Any],
) -> tuple[str, str] | None:
    namespace = generation.get("artifact_namespace")
    run_id = generation.get("run_id")
    if not _exact_text(namespace) or not _exact_text(run_id):
        return None
    return namespace, run_id


def _generation_identity(generation: Mapping[str, Any]) -> tuple[str, str]:
    identity = _optional_generation_identity(generation)
    if identity is None:
        raise MarketNoSendError("decision scorecard generation identity invalid")
    return identity


def _artifact_name(value: Any) -> bool:
    return (
        _exact_text(value)
        and "/" not in value
        and "\\" not in value
        and value not in {".", ".."}
    )


def _exact_text(value: Any) -> bool:
    return type(value) is str and bool(value) and value == value.strip()


def _sha256_digest(value: Any) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _digest(value: Any) -> str:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (OverflowError, TypeError, ValueError) as exc:
        raise MarketNoSendError(
            "decision scorecard outcome row is not canonical JSON"
        ) from exc
    return hashlib.sha256(encoded).hexdigest()


__all__ = ("build_campaign_decision_episode_scorecard",)
