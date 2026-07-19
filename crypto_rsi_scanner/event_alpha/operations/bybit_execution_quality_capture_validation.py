"""Descriptor-anchored contract validation for Bybit capture bundles."""

from __future__ import annotations

import math
from pathlib import Path
import os
import stat
from typing import Any, Mapping

from .bybit_execution_quality_capture import (
    AUTHORITY_FILENAME,
    CONTRACT_VERSION,
    MANIFEST_FILENAME,
    MAX_RESPONSES,
    MAX_RESPONSE_BYTES,
    OBSERVATIONS_FILENAME,
    RECEIPT_FILENAME,
    REQUEST_INDEX_FILENAME,
    SUMMARY_FILENAME,
    UNIVERSE_FILENAME,
    _NAMESPACE_RE,
    _SAFE_RAW_NAME_RE,
    _SHA256_RE,
    _canonical_bytes,
    _sha256,
    _utc_text,
)
from .bybit_execution_quality_capture_errors import (
    BybitExecutionQualityCaptureError,
)
from .bybit_execution_quality_set_freshness import (
    FRESHNESS_POLICY,
    MAXIMUM_AGE_SECONDS,
)
from .market_no_send_io import _open_verified_namespace_dir, parse_json_object_bytes
from .market_no_send_models import MarketNoSendError


def _same_file_snapshot(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        left.st_dev, left.st_ino, left.st_mode, left.st_nlink, left.st_size,
        left.st_mtime_ns, left.st_ctime_ns,
    ) == (
        right.st_dev, right.st_ino, right.st_mode, right.st_nlink, right.st_size,
        right.st_mtime_ns, right.st_ctime_ns,
    )


def _read_regular_bytes_at(directory_fd: int, name: str) -> bytes:
    if not name or Path(name).name != name or name in {".", ".."}:
        raise BybitExecutionQualityCaptureError("capture_artifact_name_invalid")
    descriptor: int | None = None
    try:
        before = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise BybitExecutionQualityCaptureError("capture_artifact_unreadable")
        descriptor = os.open(
            name,
            os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
            dir_fd=directory_fd,
        )
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or not _same_file_snapshot(before, opened):
            raise BybitExecutionQualityCaptureError("capture_artifact_unreadable")
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = None
            raw = handle.read(MAX_RESPONSE_BYTES + 1)
            completed = os.fstat(handle.fileno())
        after = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if (
            len(raw) > MAX_RESPONSE_BYTES
            or not _same_file_snapshot(opened, completed)
            or not _same_file_snapshot(completed, after)
            or len(raw) != completed.st_size
        ):
            raise BybitExecutionQualityCaptureError("capture_artifact_unreadable")
        return raw
    except BybitExecutionQualityCaptureError:
        raise
    except OSError as exc:
        raise BybitExecutionQualityCaptureError("capture_artifact_unreadable") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def parse_artifact_json(raw: bytes) -> dict[str, Any]:
    try:
        return parse_json_object_bytes(raw)
    except MarketNoSendError as exc:
        raise BybitExecutionQualityCaptureError("capture_artifact_invalid_json") from exc


def read_capture_bundle(
    namespace_dir: Path,
) -> tuple[
    dict[str, Any], bytes, dict[str, Any], bytes, dict[str, bytes], dict[str, str]
]:
    required_roles = {
        AUTHORITY_FILENAME: "source_authority",
        UNIVERSE_FILENAME: "radar_universe",
        SUMMARY_FILENAME: "capture_summary",
        REQUEST_INDEX_FILENAME: "request_index",
        OBSERVATIONS_FILENAME: "execution_quality_observations",
    }
    try:
        with _open_verified_namespace_dir(namespace_dir) as anchored:
            _base_fd, namespace_fd, _namespace, _identity = anchored
            receipt_raw = _read_regular_bytes_at(namespace_fd, RECEIPT_FILENAME)
            manifest_raw = _read_regular_bytes_at(namespace_fd, MANIFEST_FILENAME)
            receipt = parse_artifact_json(receipt_raw)
            manifest = parse_artifact_json(manifest_raw)
            descriptor_values = manifest.get("artifacts")
            if (
                not isinstance(descriptor_values, list)
                or not 5 < len(descriptor_values) <= MAX_RESPONSES + 5
            ):
                raise BybitExecutionQualityCaptureError(
                    "capture_artifact_index_invalid"
                )
            artifacts: dict[str, bytes] = {}
            roles: dict[str, str] = {}
            for descriptor in descriptor_values:
                if (
                    not isinstance(descriptor, Mapping)
                    or set(descriptor) != {"name", "role", "sha256", "size_bytes"}
                ):
                    raise BybitExecutionQualityCaptureError(
                        "capture_artifact_index_invalid"
                    )
                name = str(descriptor.get("name") or "")
                role = str(descriptor.get("role") or "")
                expected_role = required_roles.get(name)
                if (
                    name in artifacts
                    or name in {MANIFEST_FILENAME, RECEIPT_FILENAME}
                    or (expected_role is None and not _SAFE_RAW_NAME_RE.fullmatch(name))
                    or (expected_role is not None and role != expected_role)
                    or (
                        expected_role is None
                        and role != "accepted_raw_provider_response"
                    )
                ):
                    raise BybitExecutionQualityCaptureError(
                        "capture_artifact_name_invalid"
                    )
                raw = _read_regular_bytes_at(namespace_fd, name)
                if (
                    descriptor.get("sha256") != _sha256(raw)
                    or descriptor.get("size_bytes") != len(raw)
                ):
                    raise BybitExecutionQualityCaptureError(
                        "capture_fingerprint_mismatch"
                    )
                artifacts[name] = raw
                roles[name] = role
            if set(required_roles) - set(artifacts):
                raise BybitExecutionQualityCaptureError(
                    "capture_required_artifact_missing"
                )
    except BybitExecutionQualityCaptureError:
        raise
    except (MarketNoSendError, OSError) as exc:
        raise BybitExecutionQualityCaptureError("capture_artifact_unreadable") from exc
    return receipt, receipt_raw, manifest, manifest_raw, artifacts, roles


def _validate_fingerprint(value: object, *, name: str, raw: bytes) -> None:
    if (
        not isinstance(value, Mapping)
        or value.get("name") != name
        or value.get("sha256") != _sha256(raw)
        or value.get("size_bytes") != len(raw)
    ):
        raise BybitExecutionQualityCaptureError("capture_fingerprint_mismatch")


def validate_capture_pointer_bytes(raw: bytes) -> dict[str, Any]:
    try:
        pointer = parse_json_object_bytes(raw)
    except MarketNoSendError as exc:
        raise BybitExecutionQualityCaptureError("capture_pointer_invalid_json") from exc
    expected_keys = {
        "all_execution_quality_fresh_at_acquisition",
        "all_execution_quality_fresh_at_completion",
        "artifact_namespace", "campaign_attached", "capture_id", "completed_at",
        "contract_version", "evidence_authority_eligible", "observation_count",
        "execution_quality_set_freshness_policy",
        "maximum_execution_quality_age_at_completion_seconds",
        "maximum_execution_quality_age_policy_seconds",
        "protocol_v2_annex_bound", "protocol_v2_evidence_eligible",
        "protocol_v2_input_quality_eligible", "receipt", "request_count",
        "research_only", "schema_id", "schema_version", "source_authority", "status",
    }
    receipt = pointer.get("receipt")
    if (
        set(pointer) != expected_keys
        or pointer.get("schema_id")
        != "decision_radar.bybit_execution_quality_latest_pointer"
        or pointer.get("schema_version") != 2
        or pointer.get("contract_version") != CONTRACT_VERSION
        or pointer.get("status") != "complete"
        or not _NAMESPACE_RE.fullmatch(str(pointer.get("artifact_namespace") or ""))
        or not _SHA256_RE.fullmatch(str(pointer.get("capture_id") or ""))
        or pointer.get("evidence_authority_eligible") is not True
        or pointer.get("protocol_v2_evidence_eligible") is not False
        or type(pointer.get("protocol_v2_input_quality_eligible")) is not bool
        or type(pointer.get("all_execution_quality_fresh_at_acquisition"))
        is not bool
        or type(pointer.get("all_execution_quality_fresh_at_completion"))
        is not bool
        or pointer.get("execution_quality_set_freshness_policy")
        != FRESHNESS_POLICY
        or type(pointer.get("maximum_execution_quality_age_at_completion_seconds"))
        not in {int, float}
        or not math.isfinite(
            float(pointer["maximum_execution_quality_age_at_completion_seconds"])
        )
        or pointer.get("maximum_execution_quality_age_at_completion_seconds") < 0
        or pointer.get("maximum_execution_quality_age_policy_seconds")
        != MAXIMUM_AGE_SECONDS
        or pointer.get("protocol_v2_input_quality_eligible")
        is not pointer.get("all_execution_quality_fresh_at_completion")
        or pointer.get("protocol_v2_annex_bound") is not False
        or pointer.get("campaign_attached") is not False
        or pointer.get("research_only") is not True
        or type(pointer.get("request_count")) is not int
        or not 1 <= pointer["request_count"] <= MAX_RESPONSES
        or type(pointer.get("observation_count")) is not int
        or not 1 <= pointer["observation_count"] <= 30
        or not isinstance(receipt, Mapping)
        or set(receipt) != {"name", "sha256", "size_bytes"}
        or receipt.get("name") != RECEIPT_FILENAME
        or not _SHA256_RE.fullmatch(str(receipt.get("sha256") or ""))
        or type(receipt.get("size_bytes")) is not int
        or not 0 < receipt["size_bytes"] <= MAX_RESPONSE_BYTES
    ):
        raise BybitExecutionQualityCaptureError("capture_pointer_contract_invalid")
    _utc_text(pointer.get("completed_at"), "pointer_completed_at")
    source_authority = pointer.get("source_authority")
    if (
        not isinstance(source_authority, Mapping)
        or set(source_authority)
        != {
            "artifact_namespace", "authority_checked_at", "operator_state_sha256",
            "revision", "run_id",
        }
        or not _SHA256_RE.fullmatch(
            str(source_authority.get("operator_state_sha256") or "")
        )
        or type(source_authority.get("revision")) is not int
        or not isinstance(source_authority.get("artifact_namespace"), str)
        or not isinstance(source_authority.get("run_id"), str)
    ):
        raise BybitExecutionQualityCaptureError("capture_pointer_authority_invalid")
    _utc_text(source_authority.get("authority_checked_at"), "authority_checked_at")
    return pointer


def validate_capture_contracts(
    namespace: str,
    *,
    receipt: Mapping[str, object],
    receipt_raw: bytes,
    manifest: Mapping[str, object],
    manifest_raw: bytes,
    pointer: Mapping[str, object] | None = None,
) -> Mapping[str, object] | None:
    receipt_keys = {
        "all_execution_quality_fresh_at_acquisition",
        "all_execution_quality_fresh_at_completion",
        "artifact_namespace", "campaign_attached", "capture_id", "completed_at",
        "contract_version", "evidence_authority_eligible", "manifest",
        "execution_quality_set_freshness_policy",
        "maximum_execution_quality_age_at_completion_seconds",
        "maximum_execution_quality_age_policy_seconds",
        "observation_count", "protocol_v2_annex_bound",
        "protocol_v2_evidence_eligible", "protocol_v2_input_quality_eligible",
        "request_count", "research_only", "schema_id", "schema_version",
        "source_authority", "status",
    }
    manifest_keys = {
        "all_execution_quality_fresh_at_acquisition",
        "all_execution_quality_fresh_at_completion",
        "artifact_namespace", "artifacts", "campaign_attached", "capture_id",
        "completed_at", "contract_version", "event_alpha_triggered_fade",
        "evidence_authority_eligible", "execution_mode", "no_send",
        "execution_quality_set_freshness_policy",
        "maximum_execution_quality_age_at_completion_seconds",
        "maximum_execution_quality_age_policy_seconds",
        "normal_rsi_writes", "observation_count", "orders", "paper_trades",
        "protocol_v2_annex_bound", "protocol_v2_evidence_eligible",
        "protocol_v2_input_quality_eligible", "quote_asset", "request_count",
        "research_only", "schema_id", "schema_version", "source_authority",
        "started_at", "trades", "venue_id",
    }
    if (
        set(receipt) != receipt_keys
        or set(manifest) != manifest_keys
        or receipt.get("schema_id")
        != "decision_radar.bybit_execution_quality_completion_receipt"
        or receipt.get("schema_version") != 2
        or receipt.get("contract_version") != CONTRACT_VERSION
        or receipt.get("status") != "complete"
        or receipt.get("artifact_namespace") != namespace
        or receipt.get("evidence_authority_eligible") is not True
        or receipt.get("protocol_v2_evidence_eligible") is not False
        or type(receipt.get("protocol_v2_input_quality_eligible")) is not bool
        or type(receipt.get("all_execution_quality_fresh_at_acquisition"))
        is not bool
        or type(receipt.get("all_execution_quality_fresh_at_completion"))
        is not bool
        or receipt.get("execution_quality_set_freshness_policy")
        != FRESHNESS_POLICY
        or type(receipt.get("maximum_execution_quality_age_at_completion_seconds"))
        not in {int, float}
        or not math.isfinite(
            float(receipt["maximum_execution_quality_age_at_completion_seconds"])
        )
        or receipt.get("maximum_execution_quality_age_at_completion_seconds") < 0
        or receipt.get("maximum_execution_quality_age_policy_seconds")
        != MAXIMUM_AGE_SECONDS
        or receipt.get("protocol_v2_input_quality_eligible")
        is not receipt.get("all_execution_quality_fresh_at_completion")
        or receipt.get("protocol_v2_annex_bound") is not False
        or receipt.get("campaign_attached") is not False
        or receipt.get("research_only") is not True
        or manifest.get("schema_id")
        != "decision_radar.bybit_execution_quality_capture_manifest"
        or manifest.get("schema_version") != 2
        or manifest.get("contract_version") != CONTRACT_VERSION
        or manifest.get("artifact_namespace") != namespace
        or manifest.get("capture_id") != receipt.get("capture_id")
        or manifest.get("evidence_authority_eligible") is not True
        or manifest.get("protocol_v2_evidence_eligible") is not False
        or type(manifest.get("protocol_v2_input_quality_eligible")) is not bool
        or manifest.get("all_execution_quality_fresh_at_acquisition")
        is not receipt.get("all_execution_quality_fresh_at_acquisition")
        or manifest.get("all_execution_quality_fresh_at_completion")
        is not receipt.get("all_execution_quality_fresh_at_completion")
        or manifest.get("execution_quality_set_freshness_policy")
        != receipt.get("execution_quality_set_freshness_policy")
        or manifest.get("maximum_execution_quality_age_at_completion_seconds")
        != receipt.get("maximum_execution_quality_age_at_completion_seconds")
        or manifest.get("maximum_execution_quality_age_policy_seconds")
        != receipt.get("maximum_execution_quality_age_policy_seconds")
        or manifest.get("protocol_v2_annex_bound") is not False
        or manifest.get("campaign_attached") is not False
        or manifest.get("research_only") is not True
        or manifest.get("no_send") is not True
        or any(
            manifest.get(field) != 0
            for field in (
                "event_alpha_triggered_fade", "normal_rsi_writes", "orders",
                "paper_trades", "trades",
            )
        )
    ):
        raise BybitExecutionQualityCaptureError("capture_manifest_contract_invalid")
    _validate_fingerprint(
        receipt.get("manifest"), name=MANIFEST_FILENAME, raw=manifest_raw
    )
    if pointer is not None:
        try:
            pointer = validate_capture_pointer_bytes(_canonical_bytes(pointer))
        except (TypeError, ValueError) as exc:
            raise BybitExecutionQualityCaptureError(
                "capture_pointer_contract_invalid"
            ) from exc
        if (
            pointer.get("artifact_namespace") != namespace
            or pointer.get("capture_id") != receipt.get("capture_id")
        ):
            raise BybitExecutionQualityCaptureError("capture_pointer_contract_invalid")
        _validate_fingerprint(
            pointer.get("receipt"), name=RECEIPT_FILENAME, raw=receipt_raw
        )
    return pointer


__all__ = (
    "parse_artifact_json",
    "read_capture_bundle",
    "validate_capture_contracts",
    "validate_capture_pointer_bytes",
)
