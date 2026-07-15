"""Closed publication receipts for Decision Radar Daily Operations.

The pilot audit records the attempt before publication.  These immutable
receipts record the later authority and owned-dashboard operations facts
without rewriting that earlier evidence.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ..artifacts import fingerprints, operator_state
from ..dashboard.readiness import (
    CURRENT_NAMESPACE_POINTER,
    DashboardReadinessError,
    read_current_namespace_pointer,
    validate_current_namespace_pointer_bytes,
)
from ..dashboard.pointer_mutation import (
    CurrentPointerMutation,
    CurrentPointerMutationError,
    current_pointer_mutation_lock,
)
from .market_no_send_io import (
    parse_json_object_bytes,
    read_json_object,
    read_jsonl,
    read_regular_bytes,
    safe_existing_namespace_dir,
    write_bytes_immutable,
    write_json_atomic,
    write_json_immutable,
)
from .market_no_send_models import MarketNoSendError, SAFETY_COUNTERS


CONTRACT_VERSION = 1
PREPUBLICATION_AUDIT_FILENAME = "event_market_no_send_prepublication_audit.json"
PUBLICATION_RECEIPT_FILENAME = "event_radar_publication_receipt.json"
OPERATIONS_RECEIPT_FILENAME = "event_radar_dashboard_operations_receipt.json"
PILOT_AUDIT_FILENAME = "event_market_no_send_pilot_audit.json"
OPERATOR_STATE_FILENAME = "event_alpha_operator_state.json"
CYCLE_LEDGER_FILENAME = "event_radar_daily_operations_cycles.jsonl"
STATE_FILENAME = "event_radar_daily_operations_state.json"


class _DailyOperationsPublicationError(RuntimeError):
    """A stable, credential-free final-publication contract error."""


DailyOperationsPublicationError = _DailyOperationsPublicationError


@dataclass(frozen=True)
class _FinalPublicationValidation:
    valid: bool
    currently_authoritative: bool
    publication_status: str
    operations_status: str
    errors: tuple[str, ...]
    publication_receipt: Mapping[str, Any] | None = None
    operations_receipt: Mapping[str, Any] | None = None


FinalPublicationValidation = _FinalPublicationValidation


def is_daily_operations_managed_namespace(
    base: str | Path,
    namespace: str,
) -> bool:
    """Recognize receipt-managed history even if namespace receipts disappear."""

    root = Path(base).expanduser().absolute()
    namespace_dir = safe_existing_namespace_dir(root, namespace)
    if any(
        _leaf_present(namespace_dir / filename)
        for filename in (
            PREPUBLICATION_AUDIT_FILENAME,
            PUBLICATION_RECEIPT_FILENAME,
            OPERATIONS_RECEIPT_FILENAME,
        )
    ):
        return True
    state_path = root / STATE_FILENAME
    state_present = _leaf_present(state_path)
    state = _read_optional_json(state_path)
    if state_present and not state:
        return True
    if namespace in {
        state.get("artifact_namespace"),
        state.get("last_successful_namespace"),
    }:
        return True
    try:
        rows = read_jsonl(root / CYCLE_LEDGER_FILENAME)
    except MarketNoSendError:
        return _leaf_present(root / CYCLE_LEDGER_FILENAME)
    return any(row.get("artifact_namespace") == namespace for row in rows)


def seal_prepublication_audit(base: str | Path, namespace: str) -> Path:
    """Copy exact pilot-audit bytes into a create-only immutable artifact."""

    namespace_dir = safe_existing_namespace_dir(Path(base), namespace)
    raw = read_regular_bytes(namespace_dir / PILOT_AUDIT_FILENAME)
    if raw is None:
        raise DailyOperationsPublicationError("prepublication_audit_missing")
    audit = parse_json_object_bytes(raw)
    if (
        audit.get("row_type") != "event_market_no_send_pilot_audit"
        or audit.get("artifact_namespace") != namespace
    ):
        raise DailyOperationsPublicationError("prepublication_audit_identity_mismatch")
    target = namespace_dir / PREPUBLICATION_AUDIT_FILENAME
    try:
        write_bytes_immutable(target, raw)
    except MarketNoSendError as exc:
        raise DailyOperationsPublicationError("prepublication_audit_seal_failed") from exc
    return target


def write_publication_receipt(
    base: str | Path,
    namespace: str,
    *,
    cycle_id: str,
    recorded_at: datetime | str | None = None,
) -> Mapping[str, Any]:
    """Persist one immutable receipt after exact pointer publication."""

    root = Path(base).expanduser().absolute()
    namespace_dir = safe_existing_namespace_dir(root, namespace)
    operator = _validated_operator_state(namespace_dir)
    pointer, pointer_raw = _current_pointer(root)
    _require_exact_authority(namespace, operator, pointer)
    doctor = _mapping(operator.get("doctor"))
    _require_strict_doctor(operator, doctor)
    prepublication_raw = read_regular_bytes(
        namespace_dir / PREPUBLICATION_AUDIT_FILENAME
    )
    if prepublication_raw is None:
        raise DailyOperationsPublicationError("sealed_prepublication_audit_missing")
    prepublication = parse_json_object_bytes(prepublication_raw)
    if prepublication.get("artifact_namespace") != namespace:
        raise DailyOperationsPublicationError("sealed_prepublication_audit_identity_mismatch")
    artifacts = _mapping(operator.get("artifacts"))
    if not artifacts:
        raise DailyOperationsPublicationError("operator_artifact_fingerprints_missing")
    recorded = _timestamp(recorded_at)
    receipt = {
        "contract_version": CONTRACT_VERSION,
        "row_type": "decision_radar_final_publication_receipt",
        "status": "published",
        "recorded_at": recorded,
        "cycle_id": _identity(cycle_id, "cycle_id"),
        "artifact_namespace": namespace,
        "profile": operator.get("profile"),
        "run_id": operator.get("run_id"),
        "revision": operator.get("revision"),
        "operator_state_sha256": operator_state.operator_authority_digest(operator),
        "artifact_fingerprints_sha256": _canonical_digest(artifacts),
        "doctor_result_sha256": _canonical_digest(doctor),
        "doctor": _doctor_projection(doctor),
        "pointer": dict(pointer),
        "pointer_sha256": hashlib.sha256(pointer_raw).hexdigest(),
        "prepublication_audit": {
            "artifact": PREPUBLICATION_AUDIT_FILENAME,
            "sha256": hashlib.sha256(prepublication_raw).hexdigest(),
            "attempt_status": prepublication.get("attempt_status"),
            "publication_status_at_attempt_audit": _mapping(
                prepublication.get("publication")
            ).get("status"),
        },
        "safety": {**SAFETY_COUNTERS, "no_send": True, "research_only": True},
    }
    try:
        write_json_immutable(namespace_dir / PUBLICATION_RECEIPT_FILENAME, receipt)
    except MarketNoSendError as exc:
        raise DailyOperationsPublicationError("publication_receipt_write_failed") from exc
    validation = validate_final_publication_contract(
        root,
        namespace,
        require_current=True,
        require_operations=False,
    )
    if validation.errors:
        raise DailyOperationsPublicationError(validation.errors[0])
    return receipt


def write_operations_receipt(
    base: str | Path,
    namespace: str,
    *,
    cycle_id: str,
    dashboard: Mapping[str, Any] | object,
    recorded_at: datetime | str | None = None,
) -> Mapping[str, Any]:
    """Persist the owned-restart receipt after terminal success is journaled."""

    root = Path(base).expanduser().absolute()
    namespace_dir = safe_existing_namespace_dir(root, namespace)
    publication_raw = read_regular_bytes(
        namespace_dir / PUBLICATION_RECEIPT_FILENAME
    )
    if publication_raw is None:
        raise DailyOperationsPublicationError("publication_receipt_missing")
    publication = parse_json_object_bytes(publication_raw)
    validation = validate_final_publication_contract(
        root,
        namespace,
        require_current=True,
        require_operations=False,
    )
    if validation.errors:
        raise DailyOperationsPublicationError(validation.errors[0])
    dashboard_values = _dashboard_values(dashboard)
    if dashboard_values["owned"] is not True or dashboard_values["running"] is not True:
        raise DailyOperationsPublicationError("owned_dashboard_restart_not_verified")
    terminal = _terminal_cycle_row(root, namespace=namespace, cycle_id=cycle_id)
    state = _state_for_success(root, namespace=namespace, cycle_id=cycle_id)
    receipt = {
        "contract_version": CONTRACT_VERSION,
        "row_type": "decision_radar_dashboard_operations_receipt",
        "status": "dashboard_restarted",
        "recorded_at": _timestamp(recorded_at),
        "cycle_id": publication.get("cycle_id"),
        "artifact_namespace": publication.get("artifact_namespace"),
        "profile": publication.get("profile"),
        "run_id": publication.get("run_id"),
        "revision": publication.get("revision"),
        "operator_state_sha256": publication.get("operator_state_sha256"),
        "artifact_fingerprints_sha256": publication.get(
            "artifact_fingerprints_sha256"
        ),
        "doctor_result_sha256": publication.get("doctor_result_sha256"),
        "pointer_sha256": publication.get("pointer_sha256"),
        "publication_receipt_sha256": hashlib.sha256(publication_raw).hexdigest(),
        "terminal_cycle_row_sha256": _canonical_digest(terminal),
        "maintenance_state": {
            "last_successful_namespace": state.get("last_successful_namespace"),
            "last_successful_publication": state.get("last_successful_publication"),
            "last_cycle_id": state.get("last_cycle_id"),
            "authorization_at_last_cycle": state.get(
                "authorization_at_last_cycle"
            ),
            "authorization_checked_at_last_cycle": state.get(
                "authorization_checked_at_last_cycle"
            ),
        },
        "dashboard": dashboard_values,
        "safety": {**SAFETY_COUNTERS, "no_send": True, "research_only": True},
    }
    try:
        write_json_immutable(namespace_dir / OPERATIONS_RECEIPT_FILENAME, receipt)
    except MarketNoSendError as exc:
        raise DailyOperationsPublicationError("operations_receipt_write_failed") from exc
    final = validate_final_publication_contract(
        root,
        namespace,
        require_current=True,
        require_operations=True,
    )
    if not final.valid:
        raise DailyOperationsPublicationError(final.errors[0])
    return receipt


def validate_final_publication_contract(
    base: str | Path,
    namespace: str,
    *,
    require_current: bool = False,
    require_operations: bool = False,
) -> FinalPublicationValidation:
    """Return one closed invalid result for every malformed receipt shape."""

    try:
        return _validate_final_publication_contract(
            base,
            namespace,
            require_current=require_current,
            require_operations=require_operations,
        )
    except Exception:  # noqa: BLE001 - validation is a fail-closed trust boundary
        return FinalPublicationValidation(
            False,
            False,
            "unavailable",
            "unavailable",
            ("publication_contract_validation_failed",),
        )


def _validate_final_publication_contract(
    base: str | Path,
    namespace: str,
    *,
    require_current: bool = False,
    require_operations: bool = False,
) -> FinalPublicationValidation:
    """Validate immutable receipts against exact namespace and pointer facts."""

    root = Path(base).expanduser().absolute()
    errors: list[str] = []
    try:
        namespace_dir = safe_existing_namespace_dir(root, namespace)
        operator = _validated_operator_state(namespace_dir)
    except (DailyOperationsPublicationError, MarketNoSendError, OSError):
        return FinalPublicationValidation(
            False, False, "unavailable", "unavailable", ("publication_namespace_unavailable",)
        )
    pointer: Mapping[str, Any] = {}
    pointer_raw: bytes | None = None
    try:
        pointer, pointer_raw = _current_pointer(root)
    except DailyOperationsPublicationError:
        pointer = {}
    operator_digest = _operator_digest(operator)
    currently_authoritative = bool(
        pointer
        and pointer.get("artifact_namespace") == namespace
        and pointer.get("run_id") == operator.get("run_id")
        and pointer.get("revision") == operator.get("revision")
        and pointer.get("operator_state_sha256") == operator_digest
    )
    publication_path = namespace_dir / PUBLICATION_RECEIPT_FILENAME
    operations_path = namespace_dir / OPERATIONS_RECEIPT_FILENAME
    publication_present = _leaf_present(publication_path)
    operations_present = _leaf_present(operations_path)
    publication, publication_raw = _read_optional_receipt(publication_path)
    operations, operations_raw = _read_optional_receipt(operations_path)
    if publication is not None:
        errors.extend(
            _publication_errors(
                namespace_dir,
                namespace=namespace,
                operator=operator,
                pointer=pointer,
                pointer_raw=pointer_raw,
                currently_authoritative=currently_authoritative,
                receipt=publication,
            )
        )
    elif publication_present:
        errors.append("publication_receipt_unreadable")
    elif require_current or currently_authoritative:
        errors.append("current_authority_missing_publication_receipt")
    if operations is not None:
        if publication is None or publication_raw is None:
            errors.append("operations_receipt_without_publication_receipt")
        else:
            errors.extend(
                _operations_errors(
                    root,
                    namespace=namespace,
                    publication=publication,
                    publication_raw=publication_raw,
                    receipt=operations,
                    currently_authoritative=currently_authoritative,
                )
            )
    elif operations_present:
        errors.append("operations_receipt_unreadable")
    elif require_operations:
        errors.append("current_authority_missing_operations_receipt")
    if require_current and not currently_authoritative:
        errors.append("publication_pointer_not_current")
    publication_status = (
        str(publication.get("status") or "invalid") if publication else "missing"
    )
    operations_status = (
        str(operations.get("status") or "invalid") if operations else "missing"
    )
    deduplicated = tuple(dict.fromkeys(errors))
    return FinalPublicationValidation(
        valid=not deduplicated,
        currently_authoritative=currently_authoritative,
        publication_status=publication_status,
        operations_status=operations_status,
        errors=deduplicated,
        publication_receipt=publication,
        operations_receipt=operations,
    )


def reconcile_current_publication(
    base: str | Path,
    *,
    dashboard: Mapping[str, Any] | object,
    recorded_at: datetime | str | None = None,
) -> FinalPublicationValidation:
    """Seal receipts for a proven prior success without provider/process I/O.

    Reconciliation is deliberately limited to the exact current pointer and a
    unique terminal Daily Operations row that already recorded both pointer
    publication and an owned dashboard restart.  It does not call a provider,
    restart a process, or invent a missing historical success.
    """

    root = Path(base).expanduser().absolute()
    pointer, _pointer_raw = _current_pointer(root)
    namespace = str(pointer.get("artifact_namespace") or "")
    matches = [
        row
        for row in read_jsonl(root / CYCLE_LEDGER_FILENAME)
        if row.get("artifact_namespace") == namespace
        and row.get("status") == "succeeded"
        and row.get("pointer_published") is True
        and row.get("dashboard_restarted") is True
        and _safe_receipt(row)
    ]
    if len(matches) != 1:
        raise DailyOperationsPublicationError(
            "current_authority_successful_terminal_cycle_not_unique"
        )
    cycle_id = str(matches[0].get("cycle_id") or "")
    namespace_dir = safe_existing_namespace_dir(root, namespace)
    _restore_revalidated_pointer_binding(root, namespace, namespace_dir)
    if read_regular_bytes(
        namespace_dir / PREPUBLICATION_AUDIT_FILENAME,
        missing_ok=True,
    ) is None:
        seal_prepublication_audit(root, namespace)
    if read_regular_bytes(
        namespace_dir / PUBLICATION_RECEIPT_FILENAME,
        missing_ok=True,
    ) is None:
        write_publication_receipt(
            root,
            namespace,
            cycle_id=cycle_id,
            recorded_at=recorded_at,
        )
    _backfill_historical_authorization(root, namespace=namespace, cycle_id=cycle_id)
    if read_regular_bytes(
        namespace_dir / OPERATIONS_RECEIPT_FILENAME,
        missing_ok=True,
    ) is None:
        write_operations_receipt(
            root,
            namespace,
            cycle_id=cycle_id,
            dashboard=dashboard,
            recorded_at=recorded_at,
        )
    validation = validate_final_publication_contract(
        root,
        namespace,
        require_current=True,
        require_operations=True,
    )
    if not validation.valid:
        raise DailyOperationsPublicationError(validation.errors[0])
    return validation


def _restore_revalidated_pointer_binding(
    root: Path,
    namespace: str,
    namespace_dir: Path,
) -> None:
    """Repair only the old readiness behavior that refreshed a pointer clock.

    Final receipts bind the exact publication bytes. Before v1.1 made pointer
    publication idempotent, a successful readiness recheck could rewrite only
    ``authority_checked_at``. Explicit reconciliation may restore the embedded
    publication pointer after every other authority field and receipt binding
    validates; no broader pointer drift is repaired.
    """

    try:
        with current_pointer_mutation_lock(root) as mutation:
            _restore_revalidated_pointer_binding_locked(
                root,
                namespace,
                namespace_dir,
                mutation,
            )
    except CurrentPointerMutationError as exc:
        raise DailyOperationsPublicationError(
            "current_pointer_mutation_lock_failed"
        ) from exc


def _restore_revalidated_pointer_binding_locked(
    root: Path,
    namespace: str,
    namespace_dir: Path,
    mutation: CurrentPointerMutation,
) -> None:
    publication_raw = read_regular_bytes(
        namespace_dir / PUBLICATION_RECEIPT_FILENAME,
        missing_ok=True,
    )
    if publication_raw is None:
        return
    receipt = parse_json_object_bytes(publication_raw)
    embedded = _mapping(receipt.get("pointer"))
    try:
        current_raw = mutation.read_regular_bytes(CURRENT_NAMESPACE_POINTER)
        if current_raw is None:
            raise DailyOperationsPublicationError("current_pointer_unavailable")
        current = validate_current_namespace_pointer_bytes(current_raw)
    except Exception as exc:
        raise DailyOperationsPublicationError("current_pointer_unavailable") from exc
    if embedded == current:
        return
    if set(embedded) != set(current):
        raise DailyOperationsPublicationError(
            "publication_pointer_drift_not_repairable"
        )
    changed = {key for key in current if current.get(key) != embedded.get(key)}
    if changed != {"authority_checked_at"}:
        raise DailyOperationsPublicationError(
            "publication_pointer_drift_not_repairable"
        )
    operator = _validated_operator_state(namespace_dir)
    _require_exact_authority(namespace, operator, current)
    _require_exact_authority(namespace, operator, embedded)
    errors = _publication_errors(
        namespace_dir,
        namespace=namespace,
        operator=operator,
        pointer=embedded,
        pointer_raw=_pretty_json_bytes(embedded),
        currently_authoritative=True,
        receipt=receipt,
    )
    if errors:
        raise DailyOperationsPublicationError(errors[0])
    mutation.write_bytes_atomic(
        CURRENT_NAMESPACE_POINTER,
        _pretty_json_bytes(embedded),
    )


def _backfill_historical_authorization(
    root: Path,
    *,
    namespace: str,
    cycle_id: str,
) -> None:
    """Project only persisted legacy readiness facts into the v1.1 fields."""

    state = read_json_object(root / STATE_FILENAME)
    if (
        state.get("last_cycle_id") != cycle_id
        or state.get("last_successful_namespace") != namespace
    ):
        raise DailyOperationsPublicationError("maintenance_state_identity_mismatch")
    changed = False
    if "authorization_at_last_cycle" not in state:
        historical = state.get("live_provider_authorized")
        if not isinstance(historical, bool):
            raise DailyOperationsPublicationError(
                "historical_authorization_fact_missing"
            )
        state["authorization_at_last_cycle"] = historical
        changed = True
    if "authorization_checked_at_last_cycle" not in state:
        checked = state.get("last_readiness_check")
        if not isinstance(checked, str) or not checked.strip():
            raise DailyOperationsPublicationError(
                "historical_authorization_check_time_missing"
            )
        _timestamp(checked)
        state["authorization_checked_at_last_cycle"] = checked
        changed = True
    if changed:
        write_json_atomic(root / STATE_FILENAME, state)


def _publication_errors(
    namespace_dir: Path,
    *,
    namespace: str,
    operator: Mapping[str, Any],
    pointer: Mapping[str, Any],
    pointer_raw: bytes | None,
    currently_authoritative: bool,
    receipt: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    doctor = _mapping(operator.get("doctor"))
    artifacts = _mapping(operator.get("artifacts"))
    expected = {
        "contract_version": CONTRACT_VERSION,
        "row_type": "decision_radar_final_publication_receipt",
        "status": "published",
        "artifact_namespace": namespace,
        "profile": operator.get("profile"),
        "run_id": operator.get("run_id"),
        "revision": operator.get("revision"),
        "operator_state_sha256": _operator_digest(operator),
        "artifact_fingerprints_sha256": _canonical_digest(artifacts),
    }
    if any(receipt.get(key) != value for key, value in expected.items()):
        errors.append("publication_receipt_identity_mismatch")
    receipt_doctor = _mapping(receipt.get("doctor"))
    historical_doctor = dict(doctor)
    historical_doctor["verified_at"] = receipt_doctor.get("verified_at")
    receipt_verified_at = receipt_doctor.get("verified_at")
    try:
        receipt_doctor_time_valid = bool(
            isinstance(receipt_verified_at, str)
            and receipt_verified_at.strip()
            and _timestamp(receipt_verified_at)
        )
    except DailyOperationsPublicationError:
        receipt_doctor_time_valid = False
    if (
        set(receipt_doctor) != set(_doctor_projection(doctor))
        or not receipt_doctor_time_valid
        or _doctor_binding_projection(receipt_doctor)
        != _doctor_binding_projection(doctor)
        or receipt.get("doctor_result_sha256")
        != _canonical_digest(historical_doctor)
    ):
        errors.append("publication_receipt_doctor_mismatch")
    prepublication = _mapping(receipt.get("prepublication_audit"))
    sealed_raw = read_regular_bytes(
        namespace_dir / PREPUBLICATION_AUDIT_FILENAME,
        missing_ok=True,
    )
    if (
        sealed_raw is None
        or prepublication.get("artifact") != PREPUBLICATION_AUDIT_FILENAME
        or prepublication.get("sha256") != hashlib.sha256(sealed_raw).hexdigest()
    ):
        errors.append("publication_receipt_prepublication_audit_mismatch")
    embedded_pointer = _mapping(receipt.get("pointer"))
    embedded_raw = _pretty_json_bytes(embedded_pointer)
    if receipt.get("pointer_sha256") != hashlib.sha256(embedded_raw).hexdigest():
        errors.append("publication_receipt_pointer_digest_mismatch")
    if currently_authoritative and (
        pointer_raw is None
        or embedded_pointer != pointer
        or receipt.get("pointer_sha256") != hashlib.sha256(pointer_raw).hexdigest()
    ):
        errors.append("publication_receipt_current_pointer_mismatch")
    if not _safe_receipt(receipt):
        errors.append("publication_receipt_safety_mismatch")
    return errors


def _operations_errors(
    root: Path,
    *,
    namespace: str,
    publication: Mapping[str, Any],
    publication_raw: bytes,
    receipt: Mapping[str, Any],
    currently_authoritative: bool,
) -> list[str]:
    errors: list[str] = []
    exact_fields = (
        "cycle_id",
        "artifact_namespace",
        "profile",
        "run_id",
        "revision",
        "operator_state_sha256",
        "artifact_fingerprints_sha256",
        "doctor_result_sha256",
        "pointer_sha256",
    )
    if (
        receipt.get("contract_version") != CONTRACT_VERSION
        or receipt.get("row_type")
        != "decision_radar_dashboard_operations_receipt"
        or receipt.get("status") != "dashboard_restarted"
        or any(receipt.get(key) != publication.get(key) for key in exact_fields)
        or receipt.get("publication_receipt_sha256")
        != hashlib.sha256(publication_raw).hexdigest()
    ):
        errors.append("operations_receipt_publication_mismatch")
    dashboard = _mapping(receipt.get("dashboard"))
    if dashboard.get("owned") is not True or dashboard.get("running") is not True:
        errors.append("operations_receipt_dashboard_not_owned_running")
    cycle_id = str(receipt.get("cycle_id") or "")
    try:
        terminal = _terminal_cycle_row(root, namespace=namespace, cycle_id=cycle_id)
        if receipt.get("terminal_cycle_row_sha256") != _canonical_digest(terminal):
            errors.append("operations_receipt_terminal_cycle_mismatch")
    except DailyOperationsPublicationError:
        errors.append("operations_receipt_terminal_cycle_missing")
    maintenance = _mapping(receipt.get("maintenance_state"))
    if (
        maintenance.get("last_successful_namespace") != namespace
        or maintenance.get("last_cycle_id") != cycle_id
        or not _valid_timestamp(maintenance.get("last_successful_publication"))
        or not isinstance(maintenance.get("authorization_at_last_cycle"), bool)
        or not _valid_timestamp(
            maintenance.get("authorization_checked_at_last_cycle")
        )
    ):
        errors.append("operations_receipt_maintenance_state_mismatch")
    if currently_authoritative:
        state = _read_optional_json(root / STATE_FILENAME)
        if not _valid_current_maintenance_state(
            state,
            namespace=namespace,
            last_successful_publication=maintenance.get(
                "last_successful_publication"
            ),
        ):
            errors.append("operations_receipt_current_maintenance_state_mismatch")
    if not _safe_receipt(receipt):
        errors.append("operations_receipt_safety_mismatch")
    return errors


def _require_exact_authority(
    namespace: str,
    operator: Mapping[str, Any],
    pointer: Mapping[str, Any],
) -> None:
    expected = {
        "artifact_namespace": namespace,
        "profile": operator.get("profile"),
        "run_id": operator.get("run_id"),
        "revision": operator.get("revision"),
        "operator_state_sha256": _operator_digest(operator),
        "generation_authority_status": "authoritative",
    }
    if any(pointer.get(key) != value for key, value in expected.items()):
        raise DailyOperationsPublicationError("published_pointer_identity_mismatch")


def _require_strict_doctor(
    operator: Mapping[str, Any], doctor: Mapping[str, Any]
) -> None:
    if (
        doctor.get("authoritative") is not True
        or doctor.get("status") not in {"OK", "WARN"}
        or doctor.get("strict") is not True
        or doctor.get("schema_only") is not False
        or doctor.get("skip_api_checks") is not False
        or doctor.get("blocker_count") != 0
        or doctor.get("run_id") != operator.get("run_id")
        or doctor.get("verified_revision") != operator.get("revision")
    ):
        raise DailyOperationsPublicationError("publication_doctor_not_strict_clean")


def _validated_operator_state(namespace_dir: Path) -> Mapping[str, Any]:
    """Load one complete canonical operator contract before sealing authority."""

    loaded = operator_state.load_operator_state(namespace_dir)
    if not loaded.valid or loaded.state is None:
        raise DailyOperationsPublicationError("publication_operator_state_invalid")
    return loaded.state


def _terminal_cycle_row(
    root: Path,
    *,
    namespace: str,
    cycle_id: str,
) -> Mapping[str, Any]:
    terminal_rows = [
        row
        for row in read_jsonl(root / CYCLE_LEDGER_FILENAME)
        if row.get("artifact_namespace") == namespace
        and row.get("cycle_id") == cycle_id
        and row.get("status") in {"skipped", "blocked", "succeeded", "failed"}
    ]
    if len(terminal_rows) != 1:
        raise DailyOperationsPublicationError("successful_terminal_cycle_missing")
    terminal = terminal_rows[0]
    if (
        terminal.get("status") != "succeeded"
        or terminal.get("pointer_published") is not True
        or terminal.get("dashboard_restarted") is not True
        or not _safe_receipt(terminal)
    ):
        raise DailyOperationsPublicationError("successful_terminal_cycle_missing")
    return terminal


def _state_for_success(
    root: Path,
    *,
    namespace: str,
    cycle_id: str,
) -> Mapping[str, Any]:
    state = read_json_object(root / STATE_FILENAME)
    if (
        state.get("last_cycle_id") != cycle_id
        or state.get("last_cycle_status") != "succeeded"
        or state.get("last_successful_namespace") != namespace
        or state.get("pointer_published") is not True
        or state.get("dashboard_restarted") is not True
        or not _safe_receipt(state)
    ):
        raise DailyOperationsPublicationError("successful_maintenance_state_missing")
    return state


def _current_pointer(root: Path) -> tuple[Mapping[str, Any], bytes]:
    try:
        pointer = read_current_namespace_pointer(root)
        raw = read_regular_bytes(root / CURRENT_NAMESPACE_POINTER)
    except (DashboardReadinessError, MarketNoSendError) as exc:
        raise DailyOperationsPublicationError("current_pointer_unavailable") from exc
    if raw is None:
        raise DailyOperationsPublicationError("current_pointer_unavailable")
    return pointer, raw


def _read_optional_receipt(path: Path) -> tuple[Mapping[str, Any] | None, bytes | None]:
    try:
        raw = read_regular_bytes(path, missing_ok=True)
        return (parse_json_object_bytes(raw), raw) if raw is not None else (None, None)
    except MarketNoSendError:
        return None, None


def _leaf_present(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError:
        return True
    return True


def _read_optional_json(path: Path) -> Mapping[str, Any]:
    try:
        return read_json_object(path)
    except MarketNoSendError:
        return {}


def _dashboard_values(value: Mapping[str, Any] | object) -> dict[str, Any]:
    source = value if isinstance(value, Mapping) else {
        "owned": getattr(value, "owned", False),
        "running": getattr(value, "running", False),
        "reason": getattr(value, "reason", "not_observed"),
        "pid": getattr(value, "pid", None),
    }
    pid = source.get("pid")
    return {
        "owned": source.get("owned") is True,
        "running": source.get("running") is True,
        "reason": str(source.get("reason") or "not_observed")[:80],
        "pid": pid if isinstance(pid, int) and not isinstance(pid, bool) and pid > 0 else None,
    }


def _doctor_projection(doctor: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: doctor.get(key)
        for key in (
            "authoritative",
            "status",
            "strict",
            "blocker_count",
            "warning_count",
            "verified_revision",
            "verified_at",
        )
    }


def _doctor_binding_projection(doctor: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: doctor.get(key)
        for key in (
            "authoritative",
            "status",
            "strict",
            "blocker_count",
            "warning_count",
            "verified_revision",
        )
    }


def _safe_receipt(value: Mapping[str, Any]) -> bool:
    safety = _mapping(value.get("safety"))
    if value.get("no_send") is True and value.get("research_only") is True:
        safety = value
    return bool(
        safety.get("no_send") is True
        and safety.get("research_only") is True
        and all(_exact_zero(safety.get(field)) for field in SAFETY_COUNTERS)
    )


def _exact_zero(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value == 0


def _valid_current_maintenance_state(
    state: Mapping[str, Any],
    *,
    namespace: str,
    last_successful_publication: object,
) -> bool:
    """Validate current state while allowing a later non-success cycle.

    The immutable operations receipt describes the successful publication
    cycle.  A subsequent skipped, blocked, or failed cycle legitimately changes
    ``last_cycle_id``; the stable facts are the last-success namespace and its
    exact publication timestamp.
    """

    required_booleans = (
        "live_provider_authorized",
        "provider_call_attempted",
        "pointer_published",
        "dashboard_restarted",
        "pointer_invalidated",
        "scheduler_enabled",
        "scheduler_loaded",
        "scheduler_healthy",
    )
    status = state.get("last_cycle_status")
    if (
        state.get("contract_version") != CONTRACT_VERSION
        or state.get("row_type") != "decision_radar_daily_operations_state"
        or status not in {"skipped", "blocked", "succeeded", "failed"}
        or not _valid_identity(state.get("last_cycle_id"))
        or not _valid_identity(state.get("last_cycle_reason"))
        or not _valid_identity(state.get("last_cycle_namespace"))
        or not _valid_timestamp(state.get("updated_at"))
        or not _valid_timestamp(state.get("last_readiness_check"))
        or state.get("last_successful_namespace") != namespace
        or state.get("last_successful_publication")
        != last_successful_publication
        or not _valid_timestamp(state.get("last_successful_publication"))
        or not isinstance(state.get("authorization_at_last_cycle"), bool)
        or state.get("authorization_at_last_cycle")
        != state.get("live_provider_authorized")
        or not _valid_timestamp(
            state.get("authorization_checked_at_last_cycle")
        )
        or any(not isinstance(state.get(field), bool) for field in required_booleans)
        or (
            status == "succeeded"
            and (
                state.get("last_cycle_namespace") != namespace
                or state.get("pointer_published") is not True
                or state.get("dashboard_restarted") is not True
            )
        )
        or (
            status != "succeeded"
            and (
                state.get("pointer_published") is not False
                or state.get("dashboard_restarted") is not False
            )
        )
        or not _valid_identity(state.get("scheduler_reason"))
        or not _safe_receipt(state)
    ):
        return False
    return True


def _valid_identity(value: object) -> bool:
    clean = str(value or "").strip()
    return bool(
        clean
        and len(clean) <= 160
        and all(character.isalnum() or character in "_.-" for character in clean)
    )


def _valid_timestamp(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        _timestamp(value)
    except DailyOperationsPublicationError:
        return False
    return True


def _operator_digest(operator: Mapping[str, Any]) -> str | None:
    try:
        return operator_state.operator_authority_digest(operator)
    except (TypeError, ValueError):
        return None


def _canonical_digest(value: Any) -> str:
    try:
        raw = fingerprints.canonical_json_bytes(value)
    except fingerprints.FingerprintError as exc:
        raise DailyOperationsPublicationError("publication_binding_not_canonical") from exc
    return hashlib.sha256(raw).hexdigest()


def _pretty_json_bytes(value: Mapping[str, Any]) -> bytes:
    import json

    return (json.dumps(dict(value), indent=2, sort_keys=True) + "\n").encode("utf-8")


def _timestamp(value: datetime | str | None) -> str:
    if value is None:
        parsed = datetime.now(timezone.utc)
    elif isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as exc:
            raise DailyOperationsPublicationError("publication_timestamp_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DailyOperationsPublicationError("publication_timestamp_invalid")
    return parsed.astimezone(timezone.utc).isoformat()


def _identity(value: object, field: str) -> str:
    clean = str(value or "").strip()
    if not clean or len(clean) > 160 or not all(
        character.isalnum() or character in "_.-" for character in clean
    ):
        raise DailyOperationsPublicationError(f"publication_{field}_invalid")
    return clean


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


__all__ = (
    "DailyOperationsPublicationError",
    "FinalPublicationValidation",
    "OPERATIONS_RECEIPT_FILENAME",
    "PREPUBLICATION_AUDIT_FILENAME",
    "PUBLICATION_RECEIPT_FILENAME",
    "is_daily_operations_managed_namespace",
    "seal_prepublication_audit",
    "reconcile_current_publication",
    "validate_final_publication_contract",
    "write_operations_receipt",
    "write_publication_receipt",
)
