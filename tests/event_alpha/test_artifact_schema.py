"""Focused pytest checks for Event Alpha schema v1."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.artifacts import schema_v1
from crypto_rsi_scanner.event_alpha.doctor import schema_doctor


def test_schema_registry_contains_required_ids():
    assert "integrated_radar_candidate_v1" in schema_v1.SCHEMAS
    assert "namespace_status_v1" in schema_v1.SCHEMAS
    assert schema_doctor.check_registry_schema_dependency_errors() == ()


def test_artifact_module_import_shims_match_new_package_paths():
    from crypto_rsi_scanner import (
        event_alpha_artifacts as old_context,
        event_alpha_namespace_status as old_namespace_status,
        event_alpha_retention as old_retention,
        event_alpha_run_ledger as old_run_ledger,
        event_alpha_run_lock as old_locks,
        event_artifact_paths as old_paths,
    )
    from crypto_rsi_scanner.event_alpha.artifacts import (
        context as new_context,
        locks as new_locks,
        paths as new_paths,
        retention as new_retention,
        run_ledger as new_run_ledger,
    )
    from crypto_rsi_scanner.event_alpha.namespace import status as new_namespace_status

    assert old_context.context_from_profile is new_context.context_from_profile
    assert old_context.EventAlphaArtifactContext is new_context.EventAlphaArtifactContext
    assert old_paths.artifact_display_path is new_paths.artifact_display_path
    assert old_paths.normalize_operator_path_fields is new_paths.normalize_operator_path_fields
    assert old_paths.repo_root() == new_paths.repo_root()
    assert old_run_ledger.append_run_record is new_run_ledger.append_run_record
    assert old_run_ledger.EventAlphaRunLedgerConfig is new_run_ledger.EventAlphaRunLedgerConfig
    assert old_retention.prune_event_alpha_artifacts is new_retention.prune_event_alpha_artifacts
    assert old_retention.EventAlphaRetentionConfig is new_retention.EventAlphaRetentionConfig
    assert old_locks.acquire_run_lock is new_locks.acquire_run_lock
    assert old_locks.EventAlphaRunLockConfig is new_locks.EventAlphaRunLockConfig
    assert old_locks._read_lock is new_locks._read_lock
    assert old_namespace_status.mark_namespace_stale is new_namespace_status.mark_namespace_stale
    assert old_namespace_status.EventAlphaNamespaceStatus is new_namespace_status.EventAlphaNamespaceStatus
