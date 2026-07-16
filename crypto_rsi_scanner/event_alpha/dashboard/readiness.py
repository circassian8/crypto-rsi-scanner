"""Authoritative namespace selection for the local read-only radar dashboard."""

from __future__ import annotations

import json
import hashlib
import re
import stat
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from ..artifacts import fingerprints as event_alpha_fingerprints
from ..operations.market_provenance import normalize_market_provenance
from .loader import _read_regular_file_once, load_dashboard_snapshot
from .models import DashboardLoadError, DashboardSnapshot
from .pointer_mutation import (
    CurrentPointerMutation,
    CurrentPointerMutationError,
    current_pointer_mutation_lock,
)


CURRENT_NAMESPACE_POINTER = "radar_current_namespace.json"
POINTER_CONTRACT_VERSION = 1
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_EXPECTED_POINTER_UNSET = object()
_POINTER_FIELDS = frozenset(
    {
        "contract_version",
        "artifact_namespace",
        "profile",
        "run_id",
        "revision",
        "operator_state_sha256",
        "generation_authority_status",
        "authority_checked_at",
    }
)
_REQUIRED_PRODUCT_ARTIFACTS = (
    "run_ledger",
    "core_opportunities",
    "research_cards",
    "daily_brief",
    "notification_preview",
    "decision_v2_notification_preview",
    "source_coverage_json",
    "source_coverage_md",
    "provider_readiness_json",
    "provider_readiness_md",
    "unified_calendar",
)
_MARKET_NO_SEND_REQUIRED_ARTIFACTS = (
    "market_no_send_source_cache",
    "market_no_send_request_ledger",
    "market_no_send_generation",
    "market_history",
    "integrated_candidates",
    "integrated_outcomes",
)
_LIVE_MARKET_REQUIRED_ARTIFACTS = ("provider_health",)


class DashboardReadinessError(RuntimeError):
    """Raised when no exact authoritative dashboard generation is available."""


@dataclass(frozen=True)
class _DashboardReadinessResult:
    snapshot: DashboardSnapshot
    namespace_source: str
    pointer_path: Path


@dataclass(frozen=True)
class DashboardAuthorityInspection:
    """Credential-free current-authority status from persisted artifacts only."""

    status: str
    artifact_namespace: str
    pointer_sha256: str
    reason: str


def resolve_authoritative_dashboard(
    artifact_base_dir: str | Path,
    artifact_namespace: str | None = None,
    *,
    now: datetime | str | None = None,
    max_generation_age_hours: float | None = None,
    max_doctor_age_hours: float | None = None,
) -> _DashboardReadinessResult:
    """Resolve an explicit namespace or the exact persisted pointer, then revalidate it."""

    return _resolve_authoritative_dashboard(
        artifact_base_dir,
        artifact_namespace,
        now=now,
        max_generation_age_hours=max_generation_age_hours,
        max_doctor_age_hours=max_doctor_age_hours,
        allow_managed_prepublication=False,
        require_managed_operations=True,
    )


def _resolve_dashboard_startup(
    artifact_base_dir: str | Path,
    *,
    now: datetime | str | None = None,
    max_generation_age_hours: float | None = None,
    max_doctor_age_hours: float | None = None,
) -> _DashboardReadinessResult:
    """Bind a pointer-started process after publication but before its ops receipt."""

    return _resolve_authoritative_dashboard(
        artifact_base_dir,
        now=now,
        max_generation_age_hours=max_generation_age_hours,
        max_doctor_age_hours=max_doctor_age_hours,
        allow_managed_prepublication=False,
        require_managed_operations=False,
    )


def _resolve_authoritative_dashboard(
    artifact_base_dir: str | Path,
    artifact_namespace: str | None = None,
    *,
    now: datetime | str | None = None,
    max_generation_age_hours: float | None = None,
    max_doctor_age_hours: float | None = None,
    allow_managed_prepublication: bool,
    require_managed_operations: bool,
) -> _DashboardReadinessResult:
    """Shared resolver with one private Daily Operations publication transition."""

    base = _artifact_base(artifact_base_dir)
    pointer_path = base / CURRENT_NAMESPACE_POINTER
    explicit = str(artifact_namespace or "").strip()
    pointer: Mapping[str, Any] | None = None
    if explicit:
        namespace = explicit
        source = "explicit"
    else:
        pointer = read_current_namespace_pointer(base)
        namespace = str(pointer["artifact_namespace"])
        source = "pointer"
    try:
        snapshot = load_dashboard_snapshot(
            base,
            namespace,
            now=now,
            max_generation_age_hours=max_generation_age_hours,
            max_doctor_age_hours=max_doctor_age_hours,
        )
    except DashboardLoadError as exc:
        raise DashboardReadinessError(str(exc)) from exc
    _require_authoritative(snapshot)
    _require_complete_product_artifacts(snapshot)
    _require_current_counts(snapshot)
    if pointer is not None:
        _require_pointer_matches_snapshot(pointer, snapshot)
    if not allow_managed_prepublication:
        _require_daily_operations_publication_contract(
            base,
            snapshot,
            require_current=pointer is not None,
            require_operations=require_managed_operations,
        )
    return _DashboardReadinessResult(
        snapshot=snapshot,
        namespace_source=source,
        pointer_path=pointer_path,
    )


def _require_daily_operations_publication_contract(
    base: Path,
    snapshot: DashboardSnapshot,
    *,
    require_current: bool,
    require_operations: bool = True,
) -> None:
    """Fail closed for v1.1-managed authority while allowing legacy reconcile."""

    from ..operations import daily_operations_publication

    try:
        managed = daily_operations_publication.is_daily_operations_managed_namespace(
            base,
            snapshot.artifact_namespace,
        )
    except Exception as exc:  # noqa: BLE001 - trust classification fails closed
        raise DashboardReadinessError(
            "dashboard final publication contract is unreadable"
        ) from exc
    if not managed:
        return
    validation = daily_operations_publication.validate_final_publication_contract(
        base,
        snapshot.artifact_namespace,
        require_current=require_current,
        require_operations=require_operations,
    )
    if not validation.valid:
        detail = validation.errors[0] if validation.errors else "unknown"
        raise DashboardReadinessError(
            f"dashboard final publication contract is invalid ({detail})"
        )


def publish_current_namespace_pointer(
    artifact_base_dir: str | Path,
    artifact_namespace: str | None = None,
    *,
    now: datetime | str | None = None,
    max_generation_age_hours: float | None = None,
    max_doctor_age_hours: float | None = None,
) -> _DashboardReadinessResult:
    """Publish the fixed pointer only after the dashboard loader proves authority."""

    return _publish_current_namespace_pointer(
        artifact_base_dir,
        artifact_namespace,
        now=now,
        max_generation_age_hours=max_generation_age_hours,
        max_doctor_age_hours=max_doctor_age_hours,
        allow_managed_prepublication=False,
    )


def publish_trusted_namespace_pointer(
    artifact_base_dir: str | Path,
    artifact_namespace: str,
    *,
    now: datetime | str | None = None,
    max_generation_age_hours: float | None = None,
    max_doctor_age_hours: float | None = None,
) -> _DashboardReadinessResult:
    """Explicitly publish one receipt-backed operational generation.

    The ordinary readiness path is deliberately read-only.  This guarded
    boundary refuses fixture and legacy namespaces by requiring the already
    existing closed Daily Operations publication and restart receipts before
    it delegates to the descriptor-anchored pointer writer.
    """

    namespace = str(artifact_namespace or "").strip()
    if not namespace:
        raise DashboardReadinessError(
            "explicit artifact namespace is required for dashboard publication"
        )
    base = _artifact_base(artifact_base_dir)
    from ..operations import daily_operations_publication

    try:
        managed = daily_operations_publication.is_daily_operations_managed_namespace(
            base,
            namespace,
        )
    except Exception as exc:  # noqa: BLE001 - trust classification fails closed
        raise DashboardReadinessError(
            "dashboard publication contract is unreadable"
        ) from exc
    if not managed:
        raise DashboardReadinessError(
            "dashboard publication requires a Daily Operations managed namespace; "
            "fixture and legacy namespaces cannot be published"
        )
    validation = daily_operations_publication.validate_final_publication_contract(
        base,
        namespace,
        require_current=False,
        require_operations=True,
    )
    if not validation.valid:
        detail = validation.errors[0] if validation.errors else "unknown"
        raise DashboardReadinessError(
            f"dashboard final publication contract is invalid ({detail})"
        )
    return publish_current_namespace_pointer(
        base,
        namespace,
        now=now,
        max_generation_age_hours=max_generation_age_hours,
        max_doctor_age_hours=max_doctor_age_hours,
    )


def inspect_current_dashboard_authority(
    artifact_base_dir: str | Path,
    *,
    now: datetime | str | None = None,
) -> DashboardAuthorityInspection:
    """Inspect current authority without provider, environment, or file writes."""

    base = _artifact_base(artifact_base_dir)
    pointer_path = base / CURRENT_NAMESPACE_POINTER
    data, read_error = _read_regular_file_once(pointer_path)
    if read_error == "artifact_missing":
        return DashboardAuthorityInspection("none", "", "", "pointer_missing")
    if read_error or data is None:
        return DashboardAuthorityInspection(
            "invalid", "", "", "pointer_unreadable_or_unsafe"
        )
    digest = hashlib.sha256(data).hexdigest()
    try:
        pointer = validate_current_namespace_pointer_bytes(data)
    except DashboardReadinessError as exc:
        return DashboardAuthorityInspection("invalid", "", digest, str(exc))
    namespace = str(pointer["artifact_namespace"])
    try:
        resolve_authoritative_dashboard(base, now=now)
    except DashboardReadinessError as exc:
        return DashboardAuthorityInspection(
            "stale_or_untrusted", namespace, digest, str(exc)
        )
    return DashboardAuthorityInspection(
        "authoritative", namespace, digest, "exact_authority_revalidated"
    )


def invalidate_current_namespace_pointer(
    artifact_base_dir: str | Path,
    expected_namespace: str,
) -> str:
    """Remove only the exact named current authority under the shared lock.

    Returns the SHA-256 digest of the pointer bytes that were removed.  A
    missing pointer or a namespace mismatch fails closed instead of being
    reported as a successful invalidation.
    """

    namespace = str(expected_namespace or "").strip()
    if not namespace:
        raise DashboardReadinessError(
            "explicit artifact namespace is required for dashboard invalidation"
        )
    base = _artifact_base(artifact_base_dir)
    try:
        with current_pointer_mutation_lock(base) as mutation:
            raw = mutation.read_regular_bytes(
                CURRENT_NAMESPACE_POINTER,
                missing_ok=True,
            )
            if raw is None:
                raise DashboardReadinessError(
                    "current namespace pointer is already absent"
                )
            pointer = validate_current_namespace_pointer_bytes(raw)
            if pointer.get("artifact_namespace") != namespace:
                raise DashboardReadinessError(
                    "current namespace pointer does not match the expected namespace"
                )
            digest = hashlib.sha256(raw).hexdigest()
            mutation.remove_regular(CURRENT_NAMESPACE_POINTER)
            if mutation.read_regular_bytes(
                CURRENT_NAMESPACE_POINTER,
                missing_ok=True,
            ) is not None:
                raise DashboardReadinessError(
                    "current namespace pointer invalidation could not be verified"
                )
            return digest
    except CurrentPointerMutationError as exc:
        raise DashboardReadinessError(
            "current namespace pointer mutation lock is unavailable"
        ) from exc


def _publish_prepublication_namespace_pointer(
    artifact_base_dir: str | Path,
    artifact_namespace: str | None = None,
    *,
    now: datetime | str | None = None,
    max_generation_age_hours: float | None = None,
    max_doctor_age_hours: float | None = None,
    expected_current_pointer_sha256: str | None | object = _EXPECTED_POINTER_UNSET,
) -> _DashboardReadinessResult:
    """Publish only inside the receipt-producing Daily Operations transition."""

    return _publish_current_namespace_pointer(
        artifact_base_dir,
        artifact_namespace,
        now=now,
        max_generation_age_hours=max_generation_age_hours,
        max_doctor_age_hours=max_doctor_age_hours,
        allow_managed_prepublication=True,
        expected_current_pointer_sha256=expected_current_pointer_sha256,
    )


def _publish_current_namespace_pointer(
    artifact_base_dir: str | Path,
    artifact_namespace: str | None = None,
    *,
    now: datetime | str | None = None,
    max_generation_age_hours: float | None = None,
    max_doctor_age_hours: float | None = None,
    allow_managed_prepublication: bool,
    expected_current_pointer_sha256: str | None | object = _EXPECTED_POINTER_UNSET,
) -> _DashboardReadinessResult:
    """Write the pointer after the selected publication contract is proven."""

    base = _artifact_base(artifact_base_dir)
    try:
        with current_pointer_mutation_lock(base) as mutation:
            if expected_current_pointer_sha256 is not _EXPECTED_POINTER_UNSET:
                _require_expected_current_pointer(
                    mutation,
                    expected_current_pointer_sha256,
                )
            result = _resolve_authoritative_dashboard(
                base,
                artifact_namespace,
                now=now,
                max_generation_age_hours=max_generation_age_hours,
                max_doctor_age_hours=max_doctor_age_hours,
                allow_managed_prepublication=allow_managed_prepublication,
                require_managed_operations=True,
            )
            snapshot = result.snapshot
            payload = {
                "contract_version": POINTER_CONTRACT_VERSION,
                "artifact_namespace": snapshot.artifact_namespace,
                "profile": snapshot.profile,
                "run_id": snapshot.run_id,
                "revision": snapshot.revision,
                "operator_state_sha256": snapshot.operator_state_sha256,
                "generation_authority_status": "authoritative",
                "authority_checked_at": snapshot.generation_authority_checked_at,
            }
            if _existing_pointer_has_same_authority(
                mutation,
                payload,
            ):
                return result
            previous_raw = _read_pointer_raw(mutation)
            published_raw = _pointer_bytes(payload)
            try:
                _write_pointer_atomic(mutation, payload)
                if not allow_managed_prepublication:
                    _resolve_authoritative_dashboard(
                        base,
                        now=now,
                        max_generation_age_hours=max_generation_age_hours,
                        max_doctor_age_hours=max_doctor_age_hours,
                        allow_managed_prepublication=False,
                        require_managed_operations=True,
                    )
            except Exception:
                try:
                    _restore_pointer_after_failed_validation(
                        mutation,
                        previous_raw=previous_raw,
                        published_raw=published_raw,
                    )
                except DashboardReadinessError as rollback_exc:
                    raise DashboardReadinessError(
                        "current namespace pointer rollback failed after publication validation"
                    ) from rollback_exc
                raise
            return _DashboardReadinessResult(
                snapshot=snapshot,
                namespace_source=result.namespace_source,
                pointer_path=result.pointer_path,
            )
    except CurrentPointerMutationError as exc:
        raise DashboardReadinessError(
            "current namespace pointer mutation lock is unavailable"
        ) from exc


def _require_expected_current_pointer(
    mutation: CurrentPointerMutation,
    expected_sha256: str | None | object,
) -> None:
    """Reject a Daily Operations publication if authority changed mid-cycle."""

    try:
        raw = mutation.read_regular_bytes(
            CURRENT_NAMESPACE_POINTER,
            missing_ok=True,
        )
    except Exception as exc:
        raise DashboardReadinessError(
            "current namespace pointer cannot be compared before publication"
        ) from exc
    if expected_sha256 is None:
        matches = raw is None
    else:
        matches = bool(
            isinstance(expected_sha256, str)
            and _SHA256_RE.fullmatch(expected_sha256)
            and raw is not None
            and hashlib.sha256(raw).hexdigest() == expected_sha256
        )
    if not matches:
        raise DashboardReadinessError(
            "current namespace pointer changed during Daily Operations publication"
        )


def _existing_pointer_has_same_authority(
    mutation: CurrentPointerMutation,
    payload: Mapping[str, Any],
) -> bool:
    """Keep publication bytes stable when readiness revalidates the same authority."""

    try:
        raw = mutation.read_regular_bytes(CURRENT_NAMESPACE_POINTER, missing_ok=True)
        if raw is None:
            return False
        existing = validate_current_namespace_pointer_bytes(raw)
    except (CurrentPointerMutationError, DashboardReadinessError):
        return False
    stable_fields = _POINTER_FIELDS.difference({"authority_checked_at"})
    return all(existing.get(field) == payload.get(field) for field in stable_fields)


def read_current_namespace_pointer(artifact_base_dir: str | Path) -> dict[str, Any]:
    """Read and validate the fixed pointer without following a leaf symlink."""

    path = _artifact_base(artifact_base_dir) / CURRENT_NAMESPACE_POINTER
    data, read_error = _read_regular_file_once(path)
    if read_error == "artifact_missing":
        raise DashboardReadinessError(
            "current namespace pointer is missing; inspect authority or explicitly publish "
            "a trusted namespace"
        )
    if read_error or data is None:
        raise DashboardReadinessError("current namespace pointer is unreadable or unsafe")
    return validate_current_namespace_pointer_bytes(data)


def validate_current_namespace_pointer_bytes(data: bytes) -> dict[str, Any]:
    """Validate one exact pointer buffer already read through a trusted fd."""

    try:
        parsed = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise DashboardReadinessError("current namespace pointer is invalid JSON") from exc
    if not isinstance(parsed, Mapping):
        raise DashboardReadinessError("current namespace pointer is not an object")
    pointer = dict(parsed)
    if set(pointer) != _POINTER_FIELDS:
        raise DashboardReadinessError("current namespace pointer fields do not match contract v1")
    if pointer.get("contract_version") != POINTER_CONTRACT_VERSION:
        raise DashboardReadinessError("current namespace pointer contract version is unsupported")
    for field in ("artifact_namespace", "profile", "run_id"):
        value = pointer.get(field)
        if not isinstance(value, str) or not value or value != value.strip():
            raise DashboardReadinessError(f"current namespace pointer has invalid {field}")
    revision = pointer.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise DashboardReadinessError("current namespace pointer has invalid revision")
    digest = pointer.get("operator_state_sha256")
    if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
        raise DashboardReadinessError("current namespace pointer has invalid operator-state fingerprint")
    if pointer.get("generation_authority_status") != "authoritative":
        raise DashboardReadinessError("current namespace pointer is not authoritative")
    checked_at = pointer.get("authority_checked_at")
    if not isinstance(checked_at, str) or _aware_timestamp(checked_at) is None:
        raise DashboardReadinessError("current namespace pointer has invalid authority timestamp")
    return pointer


def _require_authoritative(snapshot: DashboardSnapshot) -> None:
    if snapshot.generation_authoritative:
        return
    reasons = ",".join(snapshot.generation_authority_reasons[:6]) or "unknown"
    raise DashboardReadinessError(f"dashboard generation is not authoritative ({reasons})")


def _require_current_counts(snapshot: DashboardSnapshot) -> None:
    artifacts = snapshot.operator_state.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise DashboardReadinessError("dashboard generation has no exact artifact counts")
    expected = {
        "core_opportunities": len(snapshot.current_candidates),
        "unified_calendar": len(snapshot.current_calendar_events),
    }
    for artifact_name, observed in expected.items():
        entry = artifacts.get(artifact_name)
        if not isinstance(entry, Mapping) or entry.get("status") != "current":
            raise DashboardReadinessError(
                f"dashboard generation lacks current {artifact_name} artifact"
            )
        count = entry.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise DashboardReadinessError(
                f"dashboard generation has invalid current count for {artifact_name}"
            )
        if count != observed:
            raise DashboardReadinessError(
                f"dashboard generation current count does not match {artifact_name}"
            )
    if isinstance(snapshot.operator_state.get("market_no_send_provenance"), Mapping):
        candidate_count = _artifact_count(artifacts, "integrated_candidates")
        outcome_count = _artifact_count(artifacts, "integrated_outcomes")
        if candidate_count != outcome_count:
            raise DashboardReadinessError(
                "dashboard market generation candidate/outcome counts do not match"
            )


def _require_complete_product_artifacts(snapshot: DashboardSnapshot) -> None:
    artifacts = snapshot.operator_state.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise DashboardReadinessError("dashboard generation has no exact artifact manifest")
    required = _REQUIRED_PRODUCT_ARTIFACTS
    provenance = snapshot.operator_state.get("market_no_send_provenance")
    if isinstance(provenance, Mapping):
        required = (*required, *_MARKET_NO_SEND_REQUIRED_ARTIFACTS)
        normalized = normalize_market_provenance(provenance)
        if normalized.get("candidate_source_mode") == "live_no_send":
            required = (*required, *_LIVE_MARKET_REQUIRED_ARTIFACTS)
    for artifact_name in required:
        entry = artifacts.get(artifact_name)
        if not isinstance(entry, Mapping) or entry.get("status") != "current":
            raise DashboardReadinessError(
                f"dashboard generation lacks current {artifact_name} artifact"
            )
        metadata_error = event_alpha_fingerprints.fingerprint_metadata_error(entry)
        if metadata_error:
            raise DashboardReadinessError(
                f"dashboard generation {artifact_name} fingerprint is invalid ({metadata_error})"
            )


def _artifact_count(artifacts: Mapping[str, Any], artifact_name: str) -> int:
    entry = artifacts.get(artifact_name)
    count = entry.get("count") if isinstance(entry, Mapping) else None
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise DashboardReadinessError(
            f"dashboard generation has invalid current count for {artifact_name}"
        )
    return count


def _require_pointer_matches_snapshot(
    pointer: Mapping[str, Any],
    snapshot: DashboardSnapshot,
) -> None:
    expected = {
        "artifact_namespace": snapshot.artifact_namespace,
        "profile": snapshot.profile,
        "run_id": snapshot.run_id,
        "revision": snapshot.revision,
        "operator_state_sha256": snapshot.operator_state_sha256,
    }
    if any(pointer.get(field) != value for field, value in expected.items()):
        raise DashboardReadinessError("current namespace pointer does not match the exact operator generation")


def _artifact_base(value: str | Path) -> Path:
    base = Path(value).expanduser().resolve()
    try:
        info = base.lstat()
    except OSError as exc:
        raise DashboardReadinessError("dashboard artifact base is missing or unreadable") from exc
    if not stat.S_ISDIR(info.st_mode):
        raise DashboardReadinessError("dashboard artifact base is not a directory")
    return base


def _write_pointer_atomic(
    mutation: CurrentPointerMutation,
    payload: Mapping[str, Any],
) -> None:
    try:
        mutation.write_bytes_atomic(CURRENT_NAMESPACE_POINTER, _pointer_bytes(payload))
    except Exception as exc:
        raise DashboardReadinessError("current namespace pointer update failed") from exc


def _pointer_bytes(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(dict(payload), indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _read_pointer_raw(mutation: CurrentPointerMutation) -> bytes | None:
    try:
        return mutation.read_regular_bytes(
            CURRENT_NAMESPACE_POINTER,
            missing_ok=True,
        )
    except Exception as exc:
        raise DashboardReadinessError(
            "current namespace pointer cannot be preserved before publication"
        ) from exc


def _restore_pointer_after_failed_validation(
    mutation: CurrentPointerMutation,
    *,
    previous_raw: bytes | None,
    published_raw: bytes,
) -> None:
    """Restore exact prior bytes only when this transaction still owns the leaf."""

    current_raw = _read_pointer_raw(mutation)
    if current_raw == previous_raw:
        return
    if current_raw != published_raw:
        raise DashboardReadinessError(
            "current namespace pointer changed during publication rollback"
        )
    try:
        if previous_raw is None:
            mutation.remove_regular(CURRENT_NAMESPACE_POINTER)
        else:
            mutation.write_bytes_atomic(CURRENT_NAMESPACE_POINTER, previous_raw)
    except Exception as exc:
        raise DashboardReadinessError(
            "current namespace pointer could not be restored"
        ) from exc
    if _read_pointer_raw(mutation) != previous_raw:
        raise DashboardReadinessError(
            "current namespace pointer restoration could not be verified"
        )


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate JSON key")
        out[key] = value
    return out


def _aware_timestamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


__all__ = (
    "CURRENT_NAMESPACE_POINTER",
    "DashboardAuthorityInspection",
    "DashboardReadinessError",
    "inspect_current_dashboard_authority",
    "invalidate_current_namespace_pointer",
    "publish_current_namespace_pointer",
    "publish_trusted_namespace_pointer",
    "read_current_namespace_pointer",
    "resolve_authoritative_dashboard",
    "validate_current_namespace_pointer_bytes",
)
