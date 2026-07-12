"""Operator-state helpers shared by Event Alpha report commands."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from ....event_alpha.artifacts import operator_state as _operator_state
from ....event_alpha.doctor import aggregation as _doctor_aggregation
from ....event_alpha.namespace import status as event_alpha_namespace_status


def record_operator_artifacts(
    context: Any,
    artifacts: Mapping[str, str | Path],
    *,
    succeeded: bool,
    failure_reason: str = "artifact_write_failed",
    run_row: Mapping[str, Any] | None,
) -> None:
    if run_row is None:
        return
    loaded = _operator_state.load_operator_state(context.namespace_dir)
    state = dict(loaded.state or {}) if loaded.valid else {}
    if not _operator_state.state_matches_run(
        state,
        run_row,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
    ):
        return
    run_id = str(run_row.get("run_id") or "")
    try:
        for name, path in artifacts.items():
            _operator_state.record_artifact(
                context.namespace_dir,
                run_id=run_id,
                profile=context.profile,
                artifact_namespace=context.artifact_namespace,
                name=name,
                path=path,
                status="current" if succeeded else "failed",
                skip_reason=None if succeeded else failure_reason,
            )
        event_alpha_namespace_status.refresh_namespace_status(
            context.namespace_dir,
            profile=context.profile,
            artifact_namespace=context.artifact_namespace,
            run_mode=str(run_row.get("run_mode") or context.run_mode),
        )
    except (OSError, ValueError):
        return


def ensure_operator_state_from_latest_run(
    context: Any,
    run_rows: Iterable[Mapping[str, Any]],
) -> dict[str, Any] | None:
    latest = _operator_state.latest_matching_run(
        run_rows,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
    )
    if latest is None:
        return None
    try:
        state = _operator_state.begin_run_if_newer(
            context.namespace_dir,
            latest,
            run_ledger_path=context.run_ledger_path,
        )
        if not _operator_state.state_matches_run(
            state,
            latest,
            profile=context.profile,
            artifact_namespace=context.artifact_namespace,
        ):
            return None
        event_alpha_namespace_status.refresh_namespace_status(
            context.namespace_dir,
            profile=context.profile,
            artifact_namespace=context.artifact_namespace,
            run_mode=str(latest.get("run_mode") or context.run_mode),
        )
    except (OSError, ValueError):
        return None
    return latest


def operator_revision_for_run(
    context: Any,
    run_row: Mapping[str, Any] | None,
) -> int | None:
    if run_row is None:
        return None
    loaded = _operator_state.load_operator_state(context.namespace_dir)
    if not loaded.valid or not _operator_state.state_matches_run(
        loaded.state,
        run_row,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
    ):
        return None
    try:
        return int((loaded.state or {}).get("revision"))
    except (TypeError, ValueError):
        return None


def record_operator_doctor_result(
    context: Any,
    result: Any,
    *,
    run_row: Mapping[str, Any] | None,
    expected_revision: int | None,
    strict: bool,
    schema_only: bool,
    skip_api_checks: bool,
) -> bool | None:
    if not strict or schema_only or skip_api_checks:
        return None
    if run_row is None or expected_revision is None:
        return False
    loaded = _operator_state.load_operator_state(context.namespace_dir)
    state = dict(loaded.state or {}) if loaded.valid else {}
    if not _operator_state.state_matches_run(
        state,
        run_row,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
    ):
        return False
    run_id = str(run_row.get("run_id") or "")
    try:
        _operator_state.record_doctor_status(
            context.namespace_dir,
            run_id=run_id,
            profile=context.profile,
            artifact_namespace=context.artifact_namespace,
            expected_revision=expected_revision,
            strict=strict,
            schema_only=schema_only,
            skip_api_checks=skip_api_checks,
            status=_doctor_aggregation.determine_doctor_status(result),
            blocker_count=len(tuple(getattr(result, "blockers", ()) or ())),
            warning_count=len(tuple(getattr(result, "warnings", ()) or ())),
        )
        event_alpha_namespace_status.refresh_namespace_status(
            context.namespace_dir,
            profile=context.profile,
            artifact_namespace=context.artifact_namespace,
            run_mode=str(run_row.get("run_mode") or context.run_mode),
        )
        return True
    except (OSError, ValueError):
        return False


__all__ = (
    "ensure_operator_state_from_latest_run",
    "operator_revision_for_run",
    "record_operator_artifacts",
    "record_operator_doctor_result",
)
