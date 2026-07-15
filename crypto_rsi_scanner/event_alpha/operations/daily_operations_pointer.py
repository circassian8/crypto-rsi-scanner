"""Exact dashboard-pointer containment for Decision Radar Daily Operations."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ..dashboard.pointer_mutation import (
    CurrentPointerMutation,
    current_pointer_mutation_lock,
)
from ..dashboard.readiness import (
    CURRENT_NAMESPACE_POINTER,
    resolve_authoritative_dashboard,
    validate_current_namespace_pointer_bytes,
)
from . import daily_operations_publication


POINTER_MAX_BYTES = 16_384


class _DailyOperationsPointerError(RuntimeError):
    """A stable, credential-free pointer containment failure."""


DailyOperationsPointerError = _DailyOperationsPointerError


@dataclass(frozen=True)
class CurrentPointerSnapshot:
    """Exact validated pointer bytes retained only for rollback containment."""

    artifact_namespace: str
    raw: bytes
    sha256: str


def current_namespace(base: Path) -> CurrentPointerSnapshot | None:
    """Read one stable current pointer while excluding every known writer."""

    try:
        with current_pointer_mutation_lock(base) as mutation:
            return _read_exact_pointer_snapshot(mutation, missing_ok=True)
    except Exception as exc:
        raise DailyOperationsPointerError("current_pointer_unavailable") from exc


def rollback(
    base: Path,
    failed_namespace: str,
    previous_pointer: CurrentPointerSnapshot | str,
) -> bool:
    """Restore exact receipt-bound prior bytes without republishing authority."""

    try:
        with current_pointer_mutation_lock(base) as mutation:
            return _rollback_locked(
                base,
                failed_namespace,
                previous_pointer,
                mutation,
            )
    except Exception:
        return False


def invalidate(base: Path, namespace: str) -> bool:
    """Remove only a pointer that still names the failed new authority."""

    try:
        with current_pointer_mutation_lock(base) as mutation:
            pointer = _read_exact_pointer_snapshot(mutation, missing_ok=True)
            if pointer is None or pointer.artifact_namespace != namespace:
                return True
            mutation.remove_regular(CURRENT_NAMESPACE_POINTER)
            return mutation.read_regular_bytes(
                CURRENT_NAMESPACE_POINTER,
                missing_ok=True,
            ) is None
    except Exception:
        return False


def _rollback_locked(
    base: Path,
    failed_namespace: str,
    previous_pointer: CurrentPointerSnapshot | str,
    mutation: CurrentPointerMutation,
) -> bool:
    if not isinstance(previous_pointer, CurrentPointerSnapshot):
        return False
    if (
        not previous_pointer.raw
        or len(previous_pointer.raw) > POINTER_MAX_BYTES
        or hashlib.sha256(previous_pointer.raw).hexdigest()
        != previous_pointer.sha256
    ):
        return False
    try:
        prior = validate_current_namespace_pointer_bytes(previous_pointer.raw)
    except Exception:
        return False
    if prior.get("artifact_namespace") != previous_pointer.artifact_namespace:
        return False
    if not _prior_pointer_is_still_authoritative(base, previous_pointer, prior):
        return False
    try:
        current = _read_exact_pointer_snapshot(mutation, missing_ok=False)
    except DailyOperationsPointerError:
        return False
    if current is None:
        return False
    if current.raw == previous_pointer.raw:
        return True
    if current.artifact_namespace != failed_namespace:
        return False
    wrote_prior = False
    try:
        mutation.write_bytes_atomic(CURRENT_NAMESPACE_POINTER, previous_pointer.raw)
        wrote_prior = True
        restored = _read_exact_pointer_snapshot(mutation, missing_ok=False)
        return bool(
            restored is not None
            and restored.raw == previous_pointer.raw
            and restored.sha256 == previous_pointer.sha256
        )
    except Exception:
        return False
    finally:
        if wrote_prior:
            try:
                restored_raw = mutation.read_regular_bytes(
                    CURRENT_NAMESPACE_POINTER,
                    missing_ok=True,
                )
                if restored_raw == previous_pointer.raw:
                    restored = _read_exact_pointer_snapshot(
                        mutation,
                        missing_ok=False,
                    )
                    if restored is None or restored.sha256 != previous_pointer.sha256:
                        mutation.remove_regular(CURRENT_NAMESPACE_POINTER)
            except Exception:
                pass


def _read_exact_pointer_snapshot(
    mutation: CurrentPointerMutation,
    *,
    missing_ok: bool,
) -> CurrentPointerSnapshot | None:
    """Read one stable, contract-valid pointer without accepting split reads."""

    try:
        raw = mutation.read_regular_bytes(
            CURRENT_NAMESPACE_POINTER,
            missing_ok=missing_ok,
        )
        if raw is None:
            return None
        if not raw or len(raw) > POINTER_MAX_BYTES:
            raise DailyOperationsPointerError("current_pointer_unavailable")
        pointer = validate_current_namespace_pointer_bytes(raw)
        confirmed = mutation.read_regular_bytes(CURRENT_NAMESPACE_POINTER)
    except Exception as exc:
        raise DailyOperationsPointerError("current_pointer_unavailable") from exc
    if confirmed != raw:
        raise DailyOperationsPointerError("current_pointer_drifted")
    return CurrentPointerSnapshot(
        artifact_namespace=str(pointer["artifact_namespace"]),
        raw=raw,
        sha256=hashlib.sha256(raw).hexdigest(),
    )


def _prior_pointer_is_still_authoritative(
    base: Path,
    previous_pointer: CurrentPointerSnapshot,
    pointer: Mapping[str, Any],
) -> bool:
    """Revalidate prior authority and bind its receipt to the saved raw bytes."""

    try:
        result = resolve_authoritative_dashboard(
            base,
            previous_pointer.artifact_namespace,
        )
        snapshot = result.snapshot
        expected = {
            "artifact_namespace": snapshot.artifact_namespace,
            "profile": snapshot.profile,
            "run_id": snapshot.run_id,
            "revision": snapshot.revision,
            "operator_state_sha256": snapshot.operator_state_sha256,
            "generation_authority_status": "authoritative",
        }
        if any(pointer.get(key) != value for key, value in expected.items()):
            return False
        validation = daily_operations_publication.validate_final_publication_contract(
            base,
            previous_pointer.artifact_namespace,
            require_current=False,
            require_operations=True,
        )
        publication = validation.publication_receipt
        embedded = publication.get("pointer") if isinstance(publication, Mapping) else None
    except Exception:
        return False
    return bool(
        validation.valid
        and isinstance(embedded, Mapping)
        and dict(embedded) == dict(pointer)
        and publication.get("pointer_sha256") == previous_pointer.sha256
    )


__all__ = (
    "CurrentPointerSnapshot",
    "DailyOperationsPointerError",
    "current_namespace",
    "invalidate",
    "rollback",
)
