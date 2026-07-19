"""Immutable receipt contract for historical outcome-price recovery."""

from __future__ import annotations

from datetime import datetime, timezone
import math
import re
from typing import Any, Mapping

from ..outcomes import outcome_eligibility
from .market_no_send_io import parse_json_object_bytes
from .market_no_send_models import MarketNoSendError
from .outcome_price_recovery_capture import CAPTURE_CONTRACT_VERSION
from .outcome_price_recovery_error import OutcomePriceRecoveryError


APPLICATION_CONTRACT_VERSION = (
    "decision_radar_outcome_price_recovery_application_v1"
)
APPLICATION_RECEIPT_PREFIX = "event_outcome_price_recovery_application_"
APPLICATION_RECEIPT_SUFFIX = ".json"
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
    applied_count = value.get("applied_outcome_count")
    no_result_count = value.get("no_result_count")
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
        type(applied_count) is not int,
        type(applied_count) is int and applied_count <= 0,
        type(no_result_count) is not int,
        type(no_result_count) is int and no_result_count < 0,
        value.get("baseline_byte_identical") is not True,
        type(value.get("outcome_row_count_before")) is not int,
        type(value.get("outcome_row_count_after")) is not int,
        (
            type(value.get("outcome_row_count_before")) is int
            and type(applied_count) is int
            and value.get("outcome_row_count_before") < applied_count
        ),
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
        or len(changes) != applied_count
    ):
        raise OutcomePriceRecoveryError("recovery_application_receipt_invalid")
    identities: set[str] = set()
    request_ids: set[str] = set()
    target_identities: set[tuple[str, str]] = set()
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
        request_id = str(change.get("request_id") or "")
        outcome_identity = str(change.get("outcome_identity_key") or "")
        source_namespace = str(change.get("source_artifact_namespace") or "")
        target_identity = (source_namespace, outcome_identity)
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
            or outcome_identity in identities
            or request_id in request_ids
            or target_identity in target_identities
        ):
            raise OutcomePriceRecoveryError(
                "recovery_application_receipt_invalid"
            )
        identities.add(outcome_identity)
        request_ids.add(request_id)
        target_identities.add(target_identity)


def _fingerprint_valid(value: object) -> bool:
    return (
        isinstance(value, Mapping)
        and set(value) == {"sha256", "size_bytes"}
        and _SHA256_RE.fullmatch(str(value.get("sha256") or "")) is not None
        and type(value.get("size_bytes")) is int
        and value.get("size_bytes", -1) >= 0
    )


def _positive_number(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
        and float(value) > 0
    )


def _aware(value: object) -> datetime:
    parsed = outcome_eligibility.parse_aware_time(value)
    if parsed is None:
        raise OutcomePriceRecoveryError("recovery_application_clock_invalid")
    return parsed.astimezone(timezone.utc)


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


__all__ = (
    "APPLICATION_CONTRACT_VERSION",
    "APPLICATION_RECEIPT_PREFIX",
    "APPLICATION_RECEIPT_SUFFIX",
    "application_receipt_name",
    "validate_application_receipt_bytes",
    "validate_application_receipt_values",
)
