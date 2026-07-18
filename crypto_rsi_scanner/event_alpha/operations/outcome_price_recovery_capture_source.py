"""Exact campaign-source bindings for immutable outcome recovery captures."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from ..outcomes import outcome_eligibility
from . import market_no_send_publication, market_observation_campaign_snapshots
from .market_no_send_history_cache import LIVE_HISTORY_CACHE_NAMESPACE
from .market_no_send_io import (
    parse_json_object_bytes,
    parse_jsonl_bytes,
    read_regular_bytes,
)
from .market_no_send_models import MarketNoSendError, SAFETY_COUNTERS
from .outcome_price_recovery_error import OutcomePriceRecoveryError
from .outcome_price_recovery_request import OutcomePriceRecoveryRequest


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def build_source_binding(
    base: Path,
    readiness: Mapping[str, Any],
    requests: Sequence[OutcomePriceRecoveryRequest],
) -> dict[str, Any]:
    """Bind exact history, ledger targets, and immutable source generations."""

    history = market_observation_campaign_snapshots.campaign_market_history_snapshot(
        base,
        history_namespace=LIVE_HISTORY_CACHE_NAMESPACE,
        filename="event_market_history.jsonl",
    )
    declared_history = readiness.get("price_history_snapshot")
    if (
        not isinstance(declared_history, Mapping)
        or history.get("status") not in {"observed", "observed_empty"}
        or history.get("sha256") != declared_history.get("sha256")
        or history.get("row_count") != declared_history.get("row_count")
    ):
        raise OutcomePriceRecoveryError("recovery_capture_history_binding_drift")
    ledger = market_observation_campaign_snapshots.campaign_outcome_ledger_snapshot(
        base,
        history_namespace=LIVE_HISTORY_CACHE_NAMESPACE,
        filename="event_decision_radar_campaign_outcomes.jsonl",
    )
    if ledger.get("status") not in {"observed", "observed_empty"}:
        raise OutcomePriceRecoveryError("recovery_capture_outcome_ledger_unavailable")
    ledger_rows = ledger.get("rows")
    if not isinstance(ledger_rows, tuple):
        raise OutcomePriceRecoveryError("recovery_capture_outcome_ledger_invalid")
    targets: list[dict[str, Any]] = []
    generations: list[dict[str, Any]] = []
    for request in requests:
        matches = [
            row for row in ledger_rows
            if row.get("outcome_identity_key") == request.outcome_identity_key
            and row.get("source_artifact_namespace")
            == request.source_artifact_namespace
        ]
        if len(matches) != 1:
            raise OutcomePriceRecoveryError(
                "recovery_capture_outcome_identity_not_unique"
            )
        target = dict(matches[0])
        if any((
            target.get("candidate_id") != request.candidate_id,
            target.get("core_opportunity_id") != request.core_opportunity_id,
            target.get("symbol") != request.symbol,
            target.get("coin_id") != request.coin_id,
            target.get("maturation_state") != "missing_data",
        )):
            raise OutcomePriceRecoveryError("recovery_capture_outcome_target_drift")
        targets.append({
            "request_id": request.request_id,
            "outcome_identity_key": request.outcome_identity_key,
            "source_artifact_namespace": request.source_artifact_namespace,
            "target_row_sha256": _sha256(_canonical_bytes(target)),
        })
        generations.append(_generation_binding(base, request))
    pointer = readiness.get("campaign_pointer")
    if not isinstance(pointer, Mapping) or pointer.get("status") != "authoritative":
        raise OutcomePriceRecoveryError("recovery_capture_campaign_pointer_invalid")
    binding = {
        "schema_id": "decision_radar.outcome_price_recovery_source_binding",
        "schema_version": 1,
        "campaign_pointer": dict(pointer),
        "price_history_snapshot": {
            key: declared_history.get(key)
            for key in ("status", "artifact", "sha256", "row_count", "binding_source")
        },
        "outcome_ledger_snapshot": {
            "artifact": ledger.get("artifact"),
            "sha256": ledger.get("sha256"),
            "size_bytes": ledger.get("size_bytes"),
            "row_count": ledger.get("row_count"),
            "binding_source": ledger.get("binding_source"),
        },
        "outcome_targets": targets,
        "source_generations": generations,
        "baseline_mutated": False,
        "campaign_outcomes_mutated": False,
        "research_only": True,
    }
    validate_source_binding(binding)
    return binding


def validate_source_binding(value: Mapping[str, Any]) -> None:
    """Validate the closed source binding without reopening mutable sources."""

    if set(value) != {
        "schema_id", "schema_version", "campaign_pointer",
        "price_history_snapshot", "outcome_ledger_snapshot", "outcome_targets",
        "source_generations", "baseline_mutated", "campaign_outcomes_mutated",
        "research_only",
    } or any((
        value.get("schema_id")
        != "decision_radar.outcome_price_recovery_source_binding",
        value.get("schema_version") != 1,
        value.get("baseline_mutated") is not False,
        value.get("campaign_outcomes_mutated") is not False,
        value.get("research_only") is not True,
    )):
        raise OutcomePriceRecoveryError("recovery_capture_source_binding_invalid")
    pointer = value.get("campaign_pointer")
    history = value.get("price_history_snapshot")
    ledger = value.get("outcome_ledger_snapshot")
    targets = value.get("outcome_targets")
    generations = value.get("source_generations")
    if (
        not isinstance(pointer, Mapping)
        or pointer.get("status") != "authoritative"
        or not isinstance(history, Mapping)
        or not _SHA256_RE.fullmatch(str(history.get("sha256") or ""))
        or type(history.get("row_count")) is not int
        or not isinstance(ledger, Mapping)
        or not _SHA256_RE.fullmatch(str(ledger.get("sha256") or ""))
        or type(ledger.get("row_count")) is not int
        or not isinstance(targets, list)
        or not targets
        or not isinstance(generations, list)
        or len(generations) != len(targets)
    ):
        raise OutcomePriceRecoveryError("recovery_capture_source_binding_invalid")
    for target, generation in zip(targets, generations, strict=True):
        if (
            not isinstance(target, Mapping)
            or set(target) != {
                "request_id", "outcome_identity_key",
                "source_artifact_namespace", "target_row_sha256",
            }
            or not _SHA256_RE.fullmatch(str(target.get("target_row_sha256") or ""))
            or not isinstance(generation, Mapping)
            or set(generation) != {
                "request_id", "artifact_namespace", "manifest",
                "candidate_artifact", "candidate_row_sha256", "core_artifact",
                "core_row_sha256",
            }
            or target.get("request_id") != generation.get("request_id")
            or target.get("source_artifact_namespace")
            != generation.get("artifact_namespace")
            or any(
                not _SHA256_RE.fullmatch(str(generation.get(field) or ""))
                for field in ("candidate_row_sha256", "core_row_sha256")
            )
            or any(
                not _fingerprint_valid(generation.get(field))
                for field in ("manifest", "candidate_artifact", "core_artifact")
            )
        ):
            raise OutcomePriceRecoveryError("recovery_capture_source_binding_invalid")


def _generation_binding(
    base: Path,
    request: OutcomePriceRecoveryRequest,
) -> dict[str, Any]:
    namespace = request.source_artifact_namespace
    namespace_dir = base / namespace
    manifest_raw = _read_required(namespace_dir / "event_market_no_send_generation.json")
    try:
        manifest = parse_json_object_bytes(manifest_raw)
    except (MarketNoSendError, ValueError) as exc:
        raise OutcomePriceRecoveryError(
            "recovery_capture_source_manifest_invalid"
        ) from exc
    validation = market_no_send_publication.validate_countable_campaign_generation(
        manifest,
        namespace_dir=namespace_dir,
        namespace=namespace,
        contract_version=2,
        default_profile="no_key_live",
        request_cache_filename="event_market_no_send_market_rows.json",
        request_ledger_filename="event_market_no_send_request_ledger.json",
        safety_counters=SAFETY_COUNTERS,
        candidates_filename="event_integrated_radar_candidates.jsonl",
    )
    if not validation.valid or not validation.core_artifact_bound:
        raise OutcomePriceRecoveryError("recovery_capture_source_generation_invalid")
    candidate_raw = _read_required(
        namespace_dir / "event_integrated_radar_candidates.jsonl"
    )
    core_raw = _read_required(namespace_dir / "event_core_opportunities.jsonl")
    try:
        candidates = parse_jsonl_bytes(candidate_raw)
        cores = parse_jsonl_bytes(core_raw)
    except (MarketNoSendError, ValueError) as exc:
        raise OutcomePriceRecoveryError(
            "recovery_capture_source_rows_invalid"
        ) from exc
    candidate_matches = [
        row for row in candidates
        if row.get("candidate_id") == request.candidate_id
        and row.get("core_opportunity_id") == request.core_opportunity_id
    ]
    core_matches = [
        row for row in cores
        if row.get("core_opportunity_id") == request.core_opportunity_id
        and row.get("integrated_candidate_id") == request.candidate_id
    ]
    if len(candidate_matches) != 1 or len(core_matches) != 1:
        raise OutcomePriceRecoveryError("recovery_capture_source_identity_not_unique")
    candidate = candidate_matches[0]
    core = core_matches[0]
    identity = outcome_eligibility.build_outcome_identity_fields(candidate)
    if any((
        identity.get("outcome_identity_key") != request.outcome_identity_key,
        candidate.get("symbol") != request.symbol,
        candidate.get("coin_id") != request.coin_id,
        core.get("symbol") != request.symbol,
        core.get("coin_id") != request.coin_id,
    )):
        raise OutcomePriceRecoveryError("recovery_capture_source_identity_drift")
    return {
        "request_id": request.request_id,
        "artifact_namespace": namespace,
        "manifest": _fingerprint(manifest_raw),
        "candidate_artifact": _fingerprint(candidate_raw),
        "candidate_row_sha256": _sha256(_canonical_bytes(candidate)),
        "core_artifact": _fingerprint(core_raw),
        "core_row_sha256": _sha256(_canonical_bytes(core)),
    }


def _read_required(path: Path) -> bytes:
    try:
        raw = read_regular_bytes(path)
    except MarketNoSendError as exc:
        raise OutcomePriceRecoveryError("recovery_capture_source_unreadable") from exc
    if raw is None:
        raise OutcomePriceRecoveryError("recovery_capture_source_unreadable")
    return raw


def _fingerprint(raw: bytes) -> dict[str, Any]:
    return {"sha256": _sha256(raw), "size_bytes": len(raw)}


def _fingerprint_valid(value: object) -> bool:
    return (
        isinstance(value, Mapping)
        and set(value) == {"sha256", "size_bytes"}
        and _SHA256_RE.fullmatch(str(value.get("sha256") or "")) is not None
        and type(value.get("size_bytes")) is int
        and value.get("size_bytes", 0) > 0
    )


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode()


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


__all__ = ("build_source_binding", "validate_source_binding")
