"""Fingerprint authority helpers for the Event Alpha operator manifest.

This module owns exact artifact-path resolution, current-entry construction,
fingerprint verification, and the read-only downgrade of legacy authority
claims.  Operator-state orchestration remains in :mod:`operator_state`.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

from . import fingerprints as artifact_fingerprints


def resolve_namespace_artifact_path(base: Path, raw_path: str) -> Path | None:
    """Resolve one exact in-namespace artifact path without basename fallback."""

    raw_candidate = Path(raw_path).expanduser()
    path_candidates = (
        (raw_candidate,)
        if raw_candidate.is_absolute()
        else (Path.cwd() / raw_candidate, base / raw_candidate)
    )
    resolved: Path | None = None
    base_lexical = Path(os.path.abspath(os.fspath(base.expanduser())))
    base_resolved = base_lexical.resolve()
    for candidate_path in path_candidates:
        try:
            candidate_lexical = Path(os.path.abspath(os.fspath(candidate_path.expanduser())))
            relative = candidate_lexical.relative_to(base_lexical)
            if _path_has_symlink_component(base_lexical, relative):
                continue
            candidate_resolved = candidate_lexical.resolve()
            candidate_resolved.relative_to(base_resolved)
        except (OSError, ValueError):
            continue
        if candidate_resolved.exists():
            resolved = candidate_resolved
            break
    return resolved


def portable_path(path: str | Path, *, base: Path) -> str:
    """Return an exact namespace-relative artifact path or fail closed."""

    raw = Path(path).expanduser()
    if not raw.is_absolute():
        raw = (Path.cwd() / raw).resolve()
    try:
        return raw.resolve().relative_to(base.resolve()).as_posix()
    except (OSError, ValueError) as exc:
        raise ValueError(f"operator artifact path outside namespace: {raw}") from exc


def fingerprinted_artifact_entry(
    name: str,
    *,
    base: Path,
    run_id: str,
    profile: str,
    artifact_namespace: str,
    path: str | Path,
    now: str,
    count: int | None,
    current_status: str,
    missing_status: str,
    failed_status: str,
) -> dict[str, Any]:
    """Build one honest current entry or a reasoned non-current fallback."""

    portable = portable_path(path, base=base)
    resolved = resolve_namespace_artifact_path(base, str(path))
    if resolved is None:
        return _unavailable_artifact_entry(
            run_id=run_id,
            path=portable,
            now=now,
            reason="artifact_path_missing_for_fingerprint",
            count=count,
            status=missing_status,
        )
    if name == "run_ledger":
        identity = {
            "run_id": str(run_id),
            "profile": str(profile or "default"),
            "artifact_namespace": str(artifact_namespace or base.name),
        }
        try:
            fingerprint = artifact_fingerprints.fingerprint_run_ledger_row(
                resolved,
                identity,
            )
        except artifact_fingerprints.FingerprintError as exc:
            return _unavailable_artifact_entry(
                run_id=run_id,
                path=portable,
                now=now,
                reason=f"run_ledger_fingerprint_failed:{exc}",
                count=count,
                status=failed_status,
            )
    else:
        try:
            fingerprint = artifact_fingerprints.fingerprint_path(resolved)
        except artifact_fingerprints.FingerprintError as exc:
            return _unavailable_artifact_entry(
                run_id=run_id,
                path=portable,
                now=now,
                reason=f"artifact_fingerprint_failed:{exc}",
                count=count,
                status=failed_status,
            )
    entry: dict[str, Any] = {
        "status": current_status,
        "run_id": str(run_id),
        "path": portable,
        "generated_at": now,
        "reason": None,
        **fingerprint,
    }
    if count is not None:
        entry["count"] = max(0, int(count))
    return entry


def operator_artifact_fingerprint_error(
    state: Mapping[str, Any],
    *,
    base: str | Path,
    require_complete: bool,
    current_status: str,
) -> str | None:
    """Validate current artifact fingerprints without upgrading legacy entries."""

    namespace_dir = Path(base).expanduser()
    artifacts = state.get("artifacts")
    if not isinstance(artifacts, Mapping):
        return "artifacts_not_object"
    expected_identity = {
        "run_id": str(state.get("run_id") or "").strip(),
        "profile": str(state.get("profile") or "").strip(),
        "artifact_namespace": str(state.get("artifact_namespace") or "").strip(),
    }
    for name, raw_entry in artifacts.items():
        if not isinstance(raw_entry, Mapping):
            continue
        entry = dict(raw_entry)
        if str(entry.get("status") or "") != current_status:
            continue
        path_text = str(entry.get("path") or "").strip()
        resolved = resolve_namespace_artifact_path(namespace_dir, path_text)
        verified, reason = artifact_fingerprints.verify_operator_entry_fingerprint(
            str(name),
            resolved,
            entry,
            expected_run_identity=expected_identity,
            require_complete=require_complete,
        )
        if not verified:
            simple_reasons = {
                "fingerprint_partial": "artifact_fingerprint_partial",
                "fingerprint_missing": "artifact_fingerprint_missing",
                "legacy_sha256_invalid": "artifact_legacy_sha256_invalid",
                "fingerprint_path_unavailable": "artifact_fingerprint_path_unavailable",
            }
            prefix = simple_reasons.get(str(reason), "artifact_fingerprint_invalid")
            suffix = "" if prefix != "artifact_fingerprint_invalid" else f":{reason or 'unknown'}"
            return f"{prefix}:{name}{suffix}"
    return None


def downgrade_legacy_doctor_authority(
    state: dict[str, Any],
    *,
    base: Path,
    completed_statuses: set[str] | frozenset[str],
    current_status: str,
) -> dict[str, Any]:
    """Return a non-persisted stale view for a coherent legacy authority claim."""

    doctor = state.get("doctor") if isinstance(state.get("doctor"), Mapping) else {}
    if not _coherent_authoritative_doctor_claim(state, doctor, completed_statuses):
        return state
    legacy_error = operator_artifact_fingerprint_error(
        state,
        base=base,
        require_complete=False,
        current_status=current_status,
    )
    complete_error = operator_artifact_fingerprint_error(
        state,
        base=base,
        require_complete=True,
        current_status=current_status,
    )
    if legacy_error is not None or not str(complete_error or "").startswith(
        "artifact_fingerprint_missing:"
    ):
        return state
    downgraded = dict(state)
    downgraded["doctor"] = {
        **dict(doctor),
        "status": "stale",
        "authoritative": False,
        "strict": False,
        "schema_only": False,
        "skip_api_checks": False,
        "verified_at": None,
        "verified_revision": None,
        "blocker_count": 0,
        "warning_count": 0,
    }
    return downgraded


def _unavailable_artifact_entry(
    *,
    run_id: str,
    path: str,
    now: str,
    reason: str,
    count: int | None,
    status: str,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "status": status,
        "run_id": str(run_id),
        "path": path,
        "generated_at": now,
        "reason": reason,
    }
    if count is not None:
        entry["count"] = max(0, int(count))
    return entry


def _coherent_authoritative_doctor_claim(
    state: Mapping[str, Any],
    doctor: Mapping[str, Any],
    completed_statuses: set[str] | frozenset[str],
) -> bool:
    revision = state.get("revision")
    verified_revision = doctor.get("verified_revision")
    return (
        doctor.get("authoritative") is True
        and str(doctor.get("status") or "") in completed_statuses
        and doctor.get("strict") is True
        and doctor.get("schema_only") is False
        and doctor.get("skip_api_checks") is False
        and str(doctor.get("run_id") or "") == str(state.get("run_id") or "")
        and isinstance(revision, int)
        and not isinstance(revision, bool)
        and isinstance(verified_revision, int)
        and not isinstance(verified_revision, bool)
        and verified_revision == revision
        and _is_nonnegative_int(doctor.get("blocker_count"))
        and _is_nonnegative_int(doctor.get("warning_count"))
        and bool(str(doctor.get("verified_at") or "").strip())
    )


def _path_has_symlink_component(base: Path, relative: Path) -> bool:
    current = base
    if current.is_symlink():
        return True
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def _is_nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


__all__ = (
    "downgrade_legacy_doctor_authority",
    "fingerprinted_artifact_entry",
    "operator_artifact_fingerprint_error",
    "portable_path",
    "resolve_namespace_artifact_path",
)
