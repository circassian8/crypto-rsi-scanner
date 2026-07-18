"""Confirmed ledger-only application of immutable historical price recovery.

This module makes no provider call.  It applies only qualifying prices from a
fully validated immutable capture while holding the shared campaign lock.  The
market-history baseline must be byte-identical before and after, and any failure
before the immutable application receipt restores the exact prior ledger bytes.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence

from ..artifacts import schema_v1
from ..outcomes import outcome_eligibility
from . import market_observation_outcomes
from .market_no_send_history_cache import LIVE_HISTORY_CACHE_NAMESPACE
from .market_no_send_io import (
    parse_json_object_bytes,
    parse_jsonl_bytes,
    read_regular_bytes,
)
from .market_no_send_models import MarketNoSendError
from .outcome_price_recovery import recovery_request_from_values
from .outcome_price_recovery_capture import (
    CAPTURE_CONTRACT_VERSION,
    load_latest_outcome_price_recovery_capture,
)
from .outcome_price_recovery_capture_source import build_source_binding
from .outcome_price_recovery_application_io import (
    AnchoredRecoveryApplicationState,
    locked_recovery_application_state,
    read_application_state_optional,
    read_application_state_required,
    restore_application_state_atomic,
    write_application_state_atomic,
    write_application_state_immutable,
)
from .outcome_price_recovery_error import OutcomePriceRecoveryError
from .outcome_price_recovery_request import OutcomePriceRecoveryRequest


APPLICATION_CONTRACT_VERSION = (
    "decision_radar_outcome_price_recovery_application_v1"
)
APPLICATION_RECEIPT_PREFIX = "event_outcome_price_recovery_application_"
APPLICATION_RECEIPT_SUFFIX = ".json"
APPLY_COMMAND = (
    "CONFIRM=1 make radar-outcome-price-recovery-apply PYTHON=.venv/bin/python"
)
STATUS_COMMAND = (
    "make radar-outcome-price-recovery-application-status PYTHON=.venv/bin/python"
)
_HISTORY_FILENAME = "event_market_history.jsonl"
_OUTCOME_FILENAME = "event_decision_radar_campaign_outcomes.jsonl"
_CANDIDATE_FILENAME = "event_integrated_radar_candidates.jsonl"
_RECOVERY_PRICE_SOURCE = "coingecko_market_chart_range_historical_recovery"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_NAMESPACE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_RECEIPT_KEYS = {
    "schema_id",
    "schema_version",
    "status",
    "application_contract_version",
    "capture_contract_version",
    "capture_id",
    "capture_artifact_namespace",
    "capture_pointer_sha256",
    "capture_receipt_sha256",
    "applied_at",
    "application_receipt",
    "provider_calls",
    "applied_outcome_count",
    "no_result_count",
    "baseline_before",
    "baseline_after",
    "baseline_byte_identical",
    "outcome_ledger_before",
    "outcome_ledger_after",
    "outcome_row_count_before",
    "outcome_row_count_after",
    "target_changes",
    "calibration_eligible",
    "protocol_v2_annex_bound",
    "protocol_v2_evidence_eligible",
    "research_only",
    "no_send",
    "orders",
    "trades",
    "paper_trades",
    "normal_rsi_writes",
    "event_alpha_triggered_fade",
    "writes_performed",
}


def apply_outcome_price_recovery(
    artifact_base_dir: str | Path,
    *,
    confirm: bool,
    applied_at: datetime | None = None,
) -> dict[str, Any]:
    """Apply one latest immutable capture to exact bound outcome rows only."""

    if not confirm:
        raise OutcomePriceRecoveryError(
            "recovery_application_explicit_confirmation_required"
        )
    base = Path(artifact_base_dir).expanduser().absolute()
    capture = load_latest_outcome_price_recovery_capture(base)
    application_time = _utc(applied_at or datetime.now(timezone.utc))
    if application_time < _aware(capture.get("completed_at")):
        raise OutcomePriceRecoveryError("recovery_application_clock_invalid")
    results = capture.get("results")
    if not isinstance(results, list) or len(results) != capture.get("request_count"):
        raise OutcomePriceRecoveryError("recovery_application_capture_invalid")
    qualifying = [
        dict(row) for row in results
        if isinstance(row, Mapping) and row.get("qualifying_price_found") is True
    ]
    if not qualifying:
        return _no_work_result(capture)
    receipt_name = application_receipt_name(str(capture["capture_id"]))
    state_dir = base / LIVE_HISTORY_CACHE_NAMESPACE
    ledger_path = state_dir / _OUTCOME_FILENAME
    with locked_recovery_application_state(base) as state:
        prior_history = read_application_state_required(
            state,
            _HISTORY_FILENAME,
            "recovery_application_history",
        )
        prior_ledger = read_application_state_required(
            state,
            _OUTCOME_FILENAME,
            "recovery_application_ledger",
        )
        prior_rows = _parse_rows(prior_ledger)
        existing_receipt_raw = read_application_state_optional(
            state,
            receipt_name,
            "recovery_application_receipt",
        )
        if existing_receipt_raw is not None:
            existing_receipt = validate_application_receipt_bytes(
                existing_receipt_raw
            )
            _validate_current_application_state(
                capture=capture,
                receipt=existing_receipt,
                rows=prior_rows,
                qualifying=qualifying,
                history_raw=prior_history,
                ledger_raw=prior_ledger,
            )
            return {
                **existing_receipt,
                "contract_version": APPLICATION_CONTRACT_VERSION,
                "status": "already_applied",
                "receipt_sha256": _sha256(existing_receipt_raw),
                "provider_calls": 0,
                **_safety(writes_performed=False),
            }
        requests = tuple(
            recovery_request_from_values(row["request"])
            for row in qualifying
        )
        _revalidate_capture_sources(base, capture, requests, prior_history)
        updated_rows, changes = _updated_ledger_rows(
            base=base,
            capture=capture,
            prior_rows=prior_rows,
            qualifying=qualifying,
            applied_at=application_time,
            receipt_name=receipt_name,
        )
        updated_ledger = _jsonl_bytes(ledger_path, updated_rows)
        if updated_ledger == prior_ledger or len(changes) != len(qualifying):
            raise OutcomePriceRecoveryError(
                "recovery_application_exact_change_count_invalid"
            )
        parsed_updated = _parse_rows(updated_ledger)
        _assert_only_target_rows_changed(prior_rows, parsed_updated, changes)
        baseline_before = _fingerprint(prior_history)
        receipt = _application_receipt(
            capture=capture,
            applied_at=application_time,
            receipt_name=receipt_name,
            baseline=baseline_before,
            ledger_before=_fingerprint(prior_ledger),
            ledger_after=_fingerprint(updated_ledger),
            row_count=len(prior_rows),
            changes=changes,
            no_result_count=len(results) - len(qualifying),
        )
        validate_application_receipt_values(receipt)
        ledger_written = False
        try:
            ledger_written = True
            write_application_state_atomic(
                state,
                _OUTCOME_FILENAME,
                updated_ledger,
                "recovery_application_ledger_write_failed",
            )
            observed_ledger = read_application_state_required(
                state,
                _OUTCOME_FILENAME,
                "recovery_application_written_ledger",
            )
            if observed_ledger != updated_ledger:
                raise OutcomePriceRecoveryError(
                    "recovery_application_ledger_postwrite_drift"
                )
            observed_history = read_application_state_required(
                state,
                _HISTORY_FILENAME,
                "recovery_application_history_postwrite",
            )
            if observed_history != prior_history:
                raise OutcomePriceRecoveryError(
                    "recovery_application_baseline_changed"
                )
            write_application_state_immutable(
                state,
                receipt_name,
                _pretty_bytes(receipt),
                "recovery_application_receipt_write_failed",
            )
        except Exception as exc:
            if ledger_written:
                _restore_ledger(state, prior_ledger, prior_history)
            if isinstance(exc, OutcomePriceRecoveryError):
                raise
            raise OutcomePriceRecoveryError(
                "recovery_application_failed"
            ) from exc
        return {
            **receipt,
            "contract_version": APPLICATION_CONTRACT_VERSION,
            "receipt_sha256": _sha256(_pretty_bytes(receipt)),
            "next_safe_command": (
                "make radar-market-campaign-report PYTHON=.venv/bin/python"
            ),
        }


def outcome_price_recovery_application_status(
    artifact_base_dir: str | Path,
) -> dict[str, Any]:
    """Inspect latest capture/application truth without calls or writes."""

    base = Path(artifact_base_dir).expanduser().absolute()
    try:
        capture = load_latest_outcome_price_recovery_capture(base)
    except OutcomePriceRecoveryError as exc:
        return _unavailable_status(exc.reason_code)
    receipt_name = application_receipt_name(str(capture["capture_id"]))
    try:
        with locked_recovery_application_state(base) as state:
            raw = read_application_state_optional(
                state,
                receipt_name,
                "recovery_application_receipt",
            )
            if raw is None:
                qualifying = int(capture.get("qualifying_price_count") or 0)
                return {
                    "contract_version": APPLICATION_CONTRACT_VERSION,
                    "status": "pending_application" if qualifying else "no_work",
                    "reason": (
                        "confirmed_application_required"
                        if qualifying
                        else "latest_capture_has_no_qualifying_prices"
                    ),
                    "capture_id": capture.get("capture_id"),
                    "qualifying_price_count": qualifying,
                    "provider_calls": 0,
                    "next_safe_command": APPLY_COMMAND if qualifying else STATUS_COMMAND,
                    **_safety(writes_performed=False),
                }
            receipt = validate_application_receipt_bytes(raw)
            if receipt.get("capture_id") != capture.get("capture_id"):
                raise OutcomePriceRecoveryError(
                    "recovery_application_receipt_capture_mismatch"
                )
            results = capture.get("results")
            qualifying_rows = [
                dict(row) for row in results
                if isinstance(row, Mapping)
                and row.get("qualifying_price_found") is True
            ] if isinstance(results, list) else []
            history_raw = read_application_state_required(
                state,
                _HISTORY_FILENAME,
                "recovery_application_history",
            )
            ledger_raw = read_application_state_required(
                state,
                _OUTCOME_FILENAME,
                "recovery_application_ledger",
            )
            _validate_current_application_state(
                capture=capture,
                receipt=receipt,
                rows=_parse_rows(ledger_raw),
                qualifying=qualifying_rows,
                history_raw=history_raw,
                ledger_raw=ledger_raw,
            )
    except OutcomePriceRecoveryError as exc:
        return _unavailable_status(
            exc.reason_code,
            capture_id=capture.get("capture_id"),
        )
    return {
        **receipt,
        "contract_version": APPLICATION_CONTRACT_VERSION,
        "status": "applied",
        "receipt_sha256": _sha256(raw),
        "provider_calls": 0,
        "next_safe_command": (
            "make radar-market-campaign-report PYTHON=.venv/bin/python"
        ),
        **_safety(writes_performed=False),
    }


def _no_work_result(capture: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "contract_version": APPLICATION_CONTRACT_VERSION,
        "status": "no_work",
        "reason": "latest_capture_has_no_qualifying_prices",
        "capture_id": capture.get("capture_id"),
        "provider_calls": 0,
        "applied_outcome_count": 0,
        "baseline_byte_identical": True,
        "next_safe_command": STATUS_COMMAND,
        **_safety(writes_performed=False),
    }


def application_receipt_name(capture_id: str) -> str:
    if not _SHA256_RE.fullmatch(str(capture_id or "")):
        raise OutcomePriceRecoveryError(
            "recovery_application_capture_id_invalid"
        )
    return f"{APPLICATION_RECEIPT_PREFIX}{capture_id}{APPLICATION_RECEIPT_SUFFIX}"


def validate_application_receipt_bytes(raw: bytes) -> dict[str, Any]:
    try:
        value = parse_json_object_bytes(raw)
    except (MarketNoSendError, ValueError) as exc:
        raise OutcomePriceRecoveryError(
            "recovery_application_receipt_invalid"
        ) from exc
    validate_application_receipt_values(value)
    return value


def validate_application_receipt_values(value: Mapping[str, Any]) -> None:
    if set(value) != _RECEIPT_KEYS or any((
        value.get("schema_id")
        != "decision_radar.outcome_price_recovery_application_receipt",
        value.get("schema_version") != 1,
        value.get("status") != "applied",
        value.get("application_contract_version")
        != APPLICATION_CONTRACT_VERSION,
        value.get("capture_contract_version") != CAPTURE_CONTRACT_VERSION,
        not _SHA256_RE.fullmatch(str(value.get("capture_id") or "")),
        not _NAMESPACE_RE.fullmatch(
            str(value.get("capture_artifact_namespace") or "")
        ),
        not _SHA256_RE.fullmatch(str(value.get("capture_pointer_sha256") or "")),
        not _SHA256_RE.fullmatch(str(value.get("capture_receipt_sha256") or "")),
        value.get("application_receipt")
        != application_receipt_name(str(value.get("capture_id") or "")),
        value.get("provider_calls") != 0,
        type(value.get("applied_outcome_count")) is not int,
        value.get("applied_outcome_count", 0) <= 0,
        type(value.get("no_result_count")) is not int,
        value.get("no_result_count", -1) < 0,
        value.get("baseline_byte_identical") is not True,
        value.get("outcome_row_count_before")
        != value.get("outcome_row_count_after"),
        value.get("calibration_eligible") is not False,
        value.get("protocol_v2_annex_bound") is not False,
        value.get("protocol_v2_evidence_eligible") is not False,
        not _safety_valid(value, writes_performed=True),
    )):
        raise OutcomePriceRecoveryError("recovery_application_receipt_invalid")
    try:
        applied_at = _aware(value.get("applied_at"))
    except OutcomePriceRecoveryError as exc:
        raise OutcomePriceRecoveryError(
            "recovery_application_receipt_invalid"
        ) from exc
    before = value.get("baseline_before")
    after = value.get("baseline_after")
    ledger_before = value.get("outcome_ledger_before")
    ledger_after = value.get("outcome_ledger_after")
    changes = value.get("target_changes")
    if (
        not _fingerprint_valid(before)
        or after != before
        or not _fingerprint_valid(ledger_before)
        or not _fingerprint_valid(ledger_after)
        or ledger_after == ledger_before
        or not isinstance(changes, list)
        or len(changes) != value.get("applied_outcome_count")
    ):
        raise OutcomePriceRecoveryError("recovery_application_receipt_invalid")
    identities: set[str] = set()
    for change in changes:
        required_text = (
            "request_id",
            "outcome_identity_key",
            "source_artifact_namespace",
            "candidate_id",
            "primary_horizon",
            "price_observation_id",
        )
        try:
            price_observed_at = _aware(change.get("price_observed_at"))
        except (AttributeError, OutcomePriceRecoveryError) as exc:
            raise OutcomePriceRecoveryError(
                "recovery_application_receipt_invalid"
            ) from exc
        if (
            not isinstance(change, Mapping)
            or set(change) != {
                "request_id", "outcome_identity_key", "source_artifact_namespace",
                "candidate_id", "target_before_sha256", "target_after_sha256",
                "primary_horizon", "price_observed_at", "price_usd",
                "price_observation_id", "raw_response_sha256",
            }
            or not _SHA256_RE.fullmatch(str(change.get("target_before_sha256") or ""))
            or not _SHA256_RE.fullmatch(str(change.get("target_after_sha256") or ""))
            or not _SHA256_RE.fullmatch(str(change.get("raw_response_sha256") or ""))
            or change.get("target_before_sha256") == change.get("target_after_sha256")
            or not _positive_number(change.get("price_usd"))
            or any(
                type(change.get(field)) is not str
                or not str(change.get(field)).strip()
                for field in required_text
            )
            or not _SHA256_RE.fullmatch(
                str(change.get("outcome_identity_key") or "")
            )
            or not _NAMESPACE_RE.fullmatch(
                str(change.get("source_artifact_namespace") or "")
            )
            or change.get("primary_horizon")
            not in outcome_eligibility.OUTCOME_HORIZONS
            or price_observed_at > applied_at
            or change.get("outcome_identity_key") in identities
        ):
            raise OutcomePriceRecoveryError(
                "recovery_application_receipt_invalid"
            )
        identities.add(change["outcome_identity_key"])


def _revalidate_capture_sources(
    base: Path,
    capture: Mapping[str, Any],
    requests: Sequence[OutcomePriceRecoveryRequest],
    history_raw: bytes,
) -> None:
    binding = capture.get("source_binding")
    if not isinstance(binding, Mapping):
        raise OutcomePriceRecoveryError("recovery_application_source_binding_invalid")
    history_binding = binding.get("price_history_snapshot")
    if (
        not isinstance(history_binding, Mapping)
        or history_binding.get("sha256") != _sha256(history_raw)
        or history_binding.get("row_count") != len(_parse_rows(history_raw))
    ):
        raise OutcomePriceRecoveryError("recovery_application_baseline_drift")
    readiness = {
        "campaign_pointer": binding.get("campaign_pointer"),
        "price_history_snapshot": history_binding,
    }
    current = build_source_binding(base, readiness, requests)
    if current != dict(binding):
        raise OutcomePriceRecoveryError("recovery_application_source_binding_drift")


def _updated_ledger_rows(
    *,
    base: Path,
    capture: Mapping[str, Any],
    prior_rows: Sequence[Mapping[str, Any]],
    qualifying: Sequence[Mapping[str, Any]],
    applied_at: datetime,
    receipt_name: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = [deepcopy(dict(row)) for row in prior_rows]
    changes: list[dict[str, Any]] = []
    seen_indexes: set[int] = set()
    for result in qualifying:
        request = recovery_request_from_values(result["request"])
        indexes = [
            index for index, row in enumerate(rows)
            if row.get("outcome_identity_key") == request.outcome_identity_key
            and row.get("source_artifact_namespace")
            == request.source_artifact_namespace
        ]
        if len(indexes) != 1 or indexes[0] in seen_indexes:
            raise OutcomePriceRecoveryError(
                "recovery_application_outcome_identity_not_unique"
            )
        index = indexes[0]
        seen_indexes.add(index)
        prior = rows[index]
        candidate = _bound_candidate(base, capture, request)
        before_sha = _row_sha256(prior)
        updated = _apply_result_to_row(
            prior,
            result=result,
            request=request,
            capture=capture,
            applied_at=applied_at,
            receipt_name=receipt_name,
        )
        validation = market_observation_outcomes.campaign_ledger_outcome_validation(
            updated,
            candidate,
            namespace=request.source_artifact_namespace,
        )
        if not validation.valid or outcome_eligibility.validate_contract(updated):
            raise OutcomePriceRecoveryError(
                "recovery_application_outcome_contract_invalid"
            )
        rows[index] = updated
        changes.append({
            "request_id": request.request_id,
            "outcome_identity_key": request.outcome_identity_key,
            "source_artifact_namespace": request.source_artifact_namespace,
            "candidate_id": request.candidate_id,
            "target_before_sha256": before_sha,
            "target_after_sha256": _row_sha256(updated),
            "primary_horizon": request.primary_horizon,
            "price_observed_at": result["price_observed_at"],
            "price_usd": result["price_usd"],
            "price_observation_id": result["price_observation_id"],
            "raw_response_sha256": result["raw_response_sha256"],
        })
    return rows, changes


def _apply_result_to_row(
    prior: Mapping[str, Any],
    *,
    result: Mapping[str, Any],
    request: OutcomePriceRecoveryRequest,
    capture: Mapping[str, Any],
    applied_at: datetime,
    receipt_name: str,
) -> dict[str, Any]:
    if any((
        prior.get("maturation_state") != "missing_data",
        prior.get("candidate_id") != request.candidate_id,
        prior.get("core_opportunity_id") != request.core_opportunity_id,
        prior.get("symbol") != request.symbol,
        prior.get("coin_id") != request.coin_id,
        prior.get("primary_horizon") != request.primary_horizon,
        result.get("status") != "complete",
        result.get("qualifying_price_found") is not True,
        not _positive_number(result.get("price_usd")),
    )):
        raise OutcomePriceRecoveryError("recovery_application_target_invalid")
    metadata = deepcopy(prior.get("horizon_metadata"))
    returns = deepcopy(prior.get("return_by_horizon"))
    aliases = deepcopy(prior.get("horizons"))
    if not all(isinstance(value, Mapping) for value in (metadata, returns, aliases)):
        raise OutcomePriceRecoveryError("recovery_application_target_invalid")
    horizon = metadata.get(request.primary_horizon)
    if not isinstance(horizon, Mapping) or any((
        horizon.get("due_at") not in {request.due_at, request.due_at.replace("Z", "+00:00")},
        horizon.get("maturity_status") != "missing_data",
        horizon.get("price_observed_at") is not None,
        horizon.get("price_at_horizon") is not None,
        horizon.get("price_source") is not None,
        horizon.get("price_observation_id") is not None,
    )):
        raise OutcomePriceRecoveryError("recovery_application_target_invalid")
    entry_price = outcome_eligibility.finite_number(prior.get("price_at_observation"))
    exit_price = outcome_eligibility.finite_number(result.get("price_usd"))
    if entry_price is None or entry_price <= 0 or exit_price is None or exit_price <= 0:
        raise OutcomePriceRecoveryError("recovery_application_target_invalid")
    observed = _aware(result.get("price_observed_at"))
    due = _aware(request.due_at)
    latest = _aware(request.allowed_latest_price_at)
    evaluated = _aware(prior.get("outcome_evaluated_at"))
    acquired = _aware(result.get("response_received_at"))
    if not (due <= observed <= latest <= evaluated <= acquired <= applied_at):
        raise OutcomePriceRecoveryError("recovery_application_clock_invalid")
    horizon_values = dict(horizon)
    horizon_values.update({
        "price_observed_at": outcome_eligibility.iso_utc(observed),
        "price_at_horizon": exit_price,
        "price_source": _RECOVERY_PRICE_SOURCE,
        "price_observation_id": result.get("price_observation_id"),
        "maturity_status": "matured",
        "provenance_status": "observed_market_prices",
    })
    metadata_values = dict(metadata)
    metadata_values[request.primary_horizon] = horizon_values
    primary_return = exit_price / entry_price - 1.0
    return_values = dict(returns)
    alias_values = dict(aliases)
    return_values[request.primary_horizon] = primary_return
    alias_values[request.primary_horizon] = primary_return
    updated = deepcopy(dict(prior))
    updated.update({
        "horizon_metadata": metadata_values,
        "return_by_horizon": return_values,
        "horizons": alias_values,
        "primary_horizon_return": primary_return,
        "outcome_status": "matured",
        "maturation_state": "matured",
        "outcome_label": "inconclusive",
        "validation_status": "inconclusive",
        "include_in_performance": False,
        "calibration_eligible": False,
        "historical_price_recovery": True,
        "historical_price_recovery_contract_version": 1,
        "historical_price_recovery_capture_id": capture.get("capture_id"),
        "historical_price_recovery_capture_namespace": capture.get(
            "artifact_namespace"
        ),
        "historical_price_recovery_request_id": request.request_id,
        "historical_price_recovery_id": result.get("recovery_id"),
        "historical_price_recovery_raw_response_sha256": result.get(
            "raw_response_sha256"
        ),
        "historical_price_recovery_market_observed_at": result.get(
            "price_observed_at"
        ),
        "historical_price_recovery_acquired_at": result.get(
            "response_received_at"
        ),
        "historical_price_recovery_applied_at": _iso(applied_at),
        "historical_price_recovery_point_in_time": False,
        "historical_price_recovery_application_receipt": receipt_name,
    })
    updated["calibration_ineligible_reasons"] = list(
        outcome_eligibility.calibration_ineligibility_reasons(updated)
    )
    updated["calibration_eligible"] = False
    updated["include_in_performance"] = False
    return updated


def _bound_candidate(
    base: Path,
    capture: Mapping[str, Any],
    request: OutcomePriceRecoveryRequest,
) -> dict[str, Any]:
    binding = capture.get("source_binding")
    generations = (
        binding.get("source_generations")
        if isinstance(binding, Mapping)
        else None
    )
    if not isinstance(generations, list):
        raise OutcomePriceRecoveryError("recovery_application_source_binding_invalid")
    matches = [
        row for row in generations
        if isinstance(row, Mapping) and row.get("request_id") == request.request_id
    ]
    if len(matches) != 1:
        raise OutcomePriceRecoveryError("recovery_application_source_binding_invalid")
    generation = matches[0]
    path = base / request.source_artifact_namespace / _CANDIDATE_FILENAME
    raw = _read_artifact_required(
        path,
        "recovery_application_candidate_artifact",
    )
    if not _fingerprint_matches(raw, generation.get("candidate_artifact")):
        raise OutcomePriceRecoveryError("recovery_application_candidate_drift")
    rows = _parse_rows(raw)
    candidates = [
        row for row in rows
        if row.get("candidate_id") == request.candidate_id
        and row.get("core_opportunity_id") == request.core_opportunity_id
    ]
    if len(candidates) != 1 or _row_sha256(candidates[0]) != generation.get(
        "candidate_row_sha256"
    ):
        raise OutcomePriceRecoveryError("recovery_application_candidate_drift")
    return candidates[0]


def _validate_current_application_state(
    *,
    capture: Mapping[str, Any],
    receipt: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    qualifying: Sequence[Mapping[str, Any]],
    history_raw: bytes,
    ledger_raw: bytes,
) -> None:
    if receipt.get("capture_id") != capture.get("capture_id"):
        raise OutcomePriceRecoveryError(
            "recovery_application_receipt_capture_mismatch"
        )
    changes = receipt.get("target_changes")
    if not isinstance(changes, list) or len(changes) != len(qualifying):
        raise OutcomePriceRecoveryError("recovery_application_receipt_invalid")
    if (
        _fingerprint(history_raw) != receipt.get("baseline_after")
        or _fingerprint(ledger_raw) != receipt.get("outcome_ledger_after")
        or len(rows) != receipt.get("outcome_row_count_after")
    ):
        raise OutcomePriceRecoveryError(
            "recovery_application_current_state_drift"
        )
    for change, result in zip(changes, qualifying, strict=True):
        request = recovery_request_from_values(result["request"])
        if not _change_matches_capture(
            change,
            result=result,
            request=request,
            capture=capture,
        ):
            raise OutcomePriceRecoveryError(
                "recovery_application_receipt_invalid"
            )
        matches = [
            row for row in rows
            if row.get("outcome_identity_key") == request.outcome_identity_key
            and row.get("source_artifact_namespace")
            == request.source_artifact_namespace
        ]
        if len(matches) != 1 or not _row_matches_recovery(
            matches[0],
            capture=capture,
            result=result,
            change=change,
        ):
            raise OutcomePriceRecoveryError(
                "recovery_application_current_target_drift"
            )


def _change_matches_capture(
    change: Mapping[str, Any],
    *,
    result: Mapping[str, Any],
    request: OutcomePriceRecoveryRequest,
    capture: Mapping[str, Any],
) -> bool:
    binding = capture.get("source_binding")
    targets = binding.get("outcome_targets") if isinstance(binding, Mapping) else None
    target_matches = [
        row for row in targets
        if isinstance(row, Mapping) and row.get("request_id") == request.request_id
    ] if isinstance(targets, list) else []
    return (
        len(target_matches) == 1
        and change.get("request_id") == request.request_id
        and change.get("outcome_identity_key") == request.outcome_identity_key
        and change.get("source_artifact_namespace")
        == request.source_artifact_namespace
        and change.get("candidate_id") == request.candidate_id
        and change.get("primary_horizon") == request.primary_horizon
        and change.get("price_observed_at") == result.get("price_observed_at")
        and change.get("price_usd") == result.get("price_usd")
        and change.get("price_observation_id")
        == result.get("price_observation_id")
        and change.get("raw_response_sha256")
        == result.get("raw_response_sha256")
        and change.get("target_before_sha256")
        == target_matches[0].get("target_row_sha256")
    )


def _row_matches_recovery(
    row: Mapping[str, Any],
    *,
    capture: Mapping[str, Any],
    result: Mapping[str, Any],
    change: Mapping[str, Any],
) -> bool:
    request = recovery_request_from_values(result["request"])
    metadata = row.get("horizon_metadata")
    horizon = (
        metadata.get(request.primary_horizon)
        if isinstance(metadata, Mapping)
        else None
    )
    return (
        isinstance(horizon, Mapping)
        and row.get("historical_price_recovery") is True
        and row.get("historical_price_recovery_capture_id")
        == capture.get("capture_id")
        and row.get("historical_price_recovery_request_id") == request.request_id
        and row.get("historical_price_recovery_raw_response_sha256")
        == result.get("raw_response_sha256")
        and horizon.get("price_observation_id") == result.get("price_observation_id")
        and horizon.get("price_source") == _RECOVERY_PRICE_SOURCE
        and _row_sha256(row) == change.get("target_after_sha256")
        and row.get("calibration_eligible") is False
        and row.get("include_in_performance") is False
    )


def _assert_only_target_rows_changed(
    before: Sequence[Mapping[str, Any]],
    after: Sequence[Mapping[str, Any]],
    changes: Sequence[Mapping[str, Any]],
) -> None:
    if len(before) != len(after):
        raise OutcomePriceRecoveryError(
            "recovery_application_outcome_row_count_changed"
        )
    expected = {
        (
            str(row.get("source_artifact_namespace")),
            str(row.get("outcome_identity_key")),
        )
        for row in changes
    }
    changed = {
        (
            str(left.get("source_artifact_namespace")),
            str(left.get("outcome_identity_key")),
        )
        for left, right in zip(before, after, strict=True)
        if _row_sha256(left) != _row_sha256(right)
    }
    if changed != expected:
        raise OutcomePriceRecoveryError(
            "recovery_application_non_target_row_changed"
        )


def _application_receipt(
    *,
    capture: Mapping[str, Any],
    applied_at: datetime,
    receipt_name: str,
    baseline: Mapping[str, Any],
    ledger_before: Mapping[str, Any],
    ledger_after: Mapping[str, Any],
    row_count: int,
    changes: Sequence[Mapping[str, Any]],
    no_result_count: int,
) -> dict[str, Any]:
    return {
        "schema_id": "decision_radar.outcome_price_recovery_application_receipt",
        "schema_version": 1,
        "status": "applied",
        "application_contract_version": APPLICATION_CONTRACT_VERSION,
        "capture_contract_version": CAPTURE_CONTRACT_VERSION,
        "capture_id": capture["capture_id"],
        "capture_artifact_namespace": capture["artifact_namespace"],
        "capture_pointer_sha256": capture["pointer_sha256"],
        "capture_receipt_sha256": capture["receipt_sha256"],
        "applied_at": _iso(applied_at),
        "application_receipt": receipt_name,
        "provider_calls": 0,
        "applied_outcome_count": len(changes),
        "no_result_count": no_result_count,
        "baseline_before": dict(baseline),
        "baseline_after": dict(baseline),
        "baseline_byte_identical": True,
        "outcome_ledger_before": dict(ledger_before),
        "outcome_ledger_after": dict(ledger_after),
        "outcome_row_count_before": row_count,
        "outcome_row_count_after": row_count,
        "target_changes": [dict(row) for row in changes],
        "calibration_eligible": False,
        "protocol_v2_annex_bound": False,
        "protocol_v2_evidence_eligible": False,
        **_safety(writes_performed=True),
    }


def _restore_ledger(
    state: AnchoredRecoveryApplicationState,
    prior_ledger: bytes,
    prior_history: bytes,
) -> None:
    try:
        restore_application_state_atomic(
            state,
            _OUTCOME_FILENAME,
            prior_ledger,
            "recovery_application_rollback_failed",
        )
        if read_application_state_required(
            state,
            _OUTCOME_FILENAME,
            "recovery_application_rollback",
        ) != prior_ledger:
            raise OutcomePriceRecoveryError(
                "recovery_application_rollback_failed"
            )
        if read_application_state_required(
            state,
            _HISTORY_FILENAME,
            "recovery_application_rollback_history",
        ) != prior_history:
            raise OutcomePriceRecoveryError(
                "recovery_application_baseline_changed"
            )
    except OutcomePriceRecoveryError:
        raise
    except (MarketNoSendError, OSError) as exc:
        raise OutcomePriceRecoveryError(
            "recovery_application_rollback_failed"
        ) from exc


def _jsonl_bytes(path: Path, rows: Sequence[Mapping[str, Any]]) -> bytes:
    lines = [
        json.dumps(
            schema_v1.stamp_artifact_row(row, path=path),
            sort_keys=True,
            separators=(",", ":"),
        )
        for row in rows
    ]
    return (("\n".join(lines) + "\n") if lines else "").encode()


def _parse_rows(raw: bytes) -> list[dict[str, Any]]:
    try:
        return parse_jsonl_bytes(raw)
    except (MarketNoSendError, ValueError) as exc:
        raise OutcomePriceRecoveryError(
            "recovery_application_jsonl_invalid"
        ) from exc


def _read_artifact_required(path: Path, reason: str) -> bytes:
    try:
        raw = read_regular_bytes(path)
    except MarketNoSendError as exc:
        raise OutcomePriceRecoveryError(f"{reason}_unreadable") from exc
    if raw is None:
        raise OutcomePriceRecoveryError(f"{reason}_missing")
    return raw


def _row_sha256(row: Mapping[str, Any]) -> str:
    return _sha256(json.dumps(
        dict(row),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode())


def _fingerprint(raw: bytes) -> dict[str, Any]:
    return {"sha256": _sha256(raw), "size_bytes": len(raw)}


def _fingerprint_valid(value: object) -> bool:
    return (
        isinstance(value, Mapping)
        and set(value) == {"sha256", "size_bytes"}
        and _SHA256_RE.fullmatch(str(value.get("sha256") or "")) is not None
        and type(value.get("size_bytes")) is int
        and value.get("size_bytes", -1) >= 0
    )


def _fingerprint_matches(raw: bytes, value: object) -> bool:
    return _fingerprint_valid(value) and dict(value) == _fingerprint(raw)  # type: ignore[arg-type]


def _pretty_bytes(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(dict(value), indent=2, sort_keys=True) + "\n").encode()


def _positive_number(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
        and float(value) > 0
    )


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _aware(value: object) -> datetime:
    parsed = outcome_eligibility.parse_aware_time(value)
    if parsed is None:
        raise OutcomePriceRecoveryError("recovery_application_clock_invalid")
    return parsed.astimezone(timezone.utc)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise OutcomePriceRecoveryError("recovery_application_clock_invalid")
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


def _safety(*, writes_performed: bool) -> dict[str, Any]:
    return {
        "research_only": True,
        "no_send": True,
        "orders": 0,
        "trades": 0,
        "paper_trades": 0,
        "normal_rsi_writes": 0,
        "event_alpha_triggered_fade": 0,
        "writes_performed": writes_performed,
    }


def _safety_valid(value: Mapping[str, Any], *, writes_performed: bool) -> bool:
    return all((
        value.get("research_only") is True,
        value.get("no_send") is True,
        value.get("orders") == 0,
        value.get("trades") == 0,
        value.get("paper_trades") == 0,
        value.get("normal_rsi_writes") == 0,
        value.get("event_alpha_triggered_fade") == 0,
        value.get("writes_performed") is writes_performed,
    ))


def _unavailable_status(
    reason: str,
    *,
    capture_id: object = None,
) -> dict[str, Any]:
    return {
        "contract_version": APPLICATION_CONTRACT_VERSION,
        "status": "unavailable",
        "reason": reason,
        "capture_id": capture_id,
        "provider_calls": 0,
        "next_safe_command": (
            "make radar-outcome-price-recovery-status PYTHON=.venv/bin/python"
        ),
        **_safety(writes_performed=False),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("apply", "status"))
    parser.add_argument("--artifact-base", default="event_fade_cache")
    parser.add_argument("--confirm", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "status":
            result = outcome_price_recovery_application_status(
                args.artifact_base
            )
        else:
            result = apply_outcome_price_recovery(
                args.artifact_base,
                confirm=args.confirm,
            )
    except OutcomePriceRecoveryError as exc:
        result = {
            "status": "blocked",
            "reason": exc.reason_code,
            "provider_calls": 0,
            **_safety(writes_performed=False),
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if args.command == "status" or result.get("status") in {
        "applied", "already_applied", "no_work"
    } else 2


if __name__ == "__main__":
    sys.exit(main())


__all__ = (
    "APPLICATION_CONTRACT_VERSION",
    "APPLICATION_RECEIPT_PREFIX",
    "APPLICATION_RECEIPT_SUFFIX",
    "APPLY_COMMAND",
    "STATUS_COMMAND",
    "application_receipt_name",
    "apply_outcome_price_recovery",
    "outcome_price_recovery_application_status",
    "validate_application_receipt_bytes",
    "validate_application_receipt_values",
)
