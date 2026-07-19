"""Closed Daily Operations publication-receipt tests."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from crypto_rsi_scanner.event_alpha.artifacts import operator_state
from crypto_rsi_scanner.event_alpha.operations import daily_operations_publication as publication
from crypto_rsi_scanner.event_alpha.doctor.checks import operations as doctor_operations
from crypto_rsi_scanner.event_alpha.operations.market_no_send_io import (
    read_jsonl,
    read_json_object,
    write_bytes_atomic,
    write_json_atomic,
    write_jsonl,
)
from crypto_rsi_scanner.event_alpha.operations.market_no_send_models import (
    SAFETY_COUNTERS,
)


NOW = datetime(2026, 7, 15, 12, tzinfo=timezone.utc)
NAMESPACE = "radar_market_no_send_receipt_test"
CYCLE_ID = "a" * 32
RUN_ID = "2026-07-15T12:00:00+00:00|no_key_live"


def _fixture(base: Path) -> Path:
    namespace_dir = base / NAMESPACE
    namespace_dir.mkdir()
    run_row = {
        "run_id": RUN_ID,
        "profile": "no_key_live",
        "artifact_namespace": NAMESPACE,
        "run_mode": "operational",
    }
    ledger = namespace_dir / "event_alpha_runs.jsonl"
    write_jsonl(ledger, [run_row])
    operator = operator_state.begin_run(
        namespace_dir,
        run_row,
        run_ledger_path=ledger,
        updated_at=NOW,
    )
    operator = operator_state.record_doctor_status(
        namespace_dir,
        run_id=RUN_ID,
        profile="no_key_live",
        artifact_namespace=NAMESPACE,
        expected_revision=int(operator["revision"]),
        strict=True,
        schema_only=False,
        skip_api_checks=False,
        status="OK",
        blocker_count=0,
        warning_count=0,
        checked_at=NOW,
    )
    write_json_atomic(
        namespace_dir / publication.PILOT_AUDIT_FILENAME,
        {
            "contract_version": 1,
            "row_type": "event_market_no_send_pilot_audit",
            "artifact_namespace": NAMESPACE,
            "exact_run_id": RUN_ID,
            "attempt_status": "complete",
            "publication": {"status": "not_published"},
            "safety": {**SAFETY_COUNTERS, "no_send": True, "research_only": True},
        },
    )
    write_json_atomic(
        base / "radar_current_namespace.json",
        {
            "contract_version": 1,
            "artifact_namespace": NAMESPACE,
            "profile": "no_key_live",
            "run_id": RUN_ID,
            "revision": operator["revision"],
            "operator_state_sha256": operator_state.operator_authority_digest(
                operator
            ),
            "generation_authority_status": "authoritative",
            "authority_checked_at": NOW.isoformat(),
        },
    )
    terminal = {
        "contract_version": 1,
        "row_type": "decision_radar_daily_operations_cycle",
        "cycle_id": CYCLE_ID,
        "recorded_at": NOW.isoformat(),
        "artifact_namespace": NAMESPACE,
        "status": "succeeded",
        "reason": "published_and_restarted",
        "provider_call_attempted": True,
        "provider_request_succeeded": True,
        "pointer_published": True,
        "dashboard_restarted": True,
        "pointer_rolled_back": False,
        "pointer_invalidated": False,
        **SAFETY_COUNTERS,
        "no_send": True,
        "research_only": True,
    }
    write_jsonl(base / publication.CYCLE_LEDGER_FILENAME, [terminal])
    write_json_atomic(
        base / publication.STATE_FILENAME,
        {
            "contract_version": 1,
            "row_type": "decision_radar_daily_operations_state",
            "updated_at": NOW.isoformat(),
            "last_cycle_id": CYCLE_ID,
            "last_cycle_status": "succeeded",
            "last_cycle_reason": "published_and_restarted",
            "last_cycle_namespace": NAMESPACE,
            "last_successful_namespace": NAMESPACE,
            "last_successful_publication": NOW.isoformat(),
            "last_readiness_check": NOW.isoformat(),
            "live_provider_authorized": True,
            "provider_call_attempted": True,
            "pointer_published": True,
            "dashboard_restarted": True,
            "pointer_invalidated": False,
            "scheduler_enabled": False,
            "scheduler_loaded": False,
            "scheduler_healthy": True,
            "scheduler_reason": "not_installed",
            **SAFETY_COUNTERS,
            "no_send": True,
            "research_only": True,
        },
    )
    return namespace_dir


def test_reconcile_closes_prepublication_publication_and_operations_facts(
    tmp_path: Path,
) -> None:
    namespace_dir = _fixture(tmp_path)

    result = publication.reconcile_current_publication(
        tmp_path,
        dashboard={
            "owned": True,
            "running": True,
            "reason": "owned_running",
            "pid": 123,
        },
        recorded_at=NOW,
    )

    assert result.valid is True
    assert result.currently_authoritative is True
    assert result.publication_status == "published"
    assert result.operations_status == "dashboard_restarted"
    prepublication = read_json_object(
        namespace_dir / publication.PREPUBLICATION_AUDIT_FILENAME
    )
    assert prepublication["publication"]["status"] == "not_published"
    final = read_json_object(namespace_dir / publication.PUBLICATION_RECEIPT_FILENAME)
    operations = read_json_object(
        namespace_dir / publication.OPERATIONS_RECEIPT_FILENAME
    )
    assert final["prepublication_audit"]["publication_status_at_attempt_audit"] == (
        "not_published"
    )
    assert operations["publication_receipt_sha256"] == hashlib.sha256(
        (namespace_dir / publication.PUBLICATION_RECEIPT_FILENAME).read_bytes()
    ).hexdigest()
    state = read_json_object(tmp_path / publication.STATE_FILENAME)
    assert state["authorization_at_last_cycle"] is True
    assert state["authorization_checked_at_last_cycle"] == NOW.isoformat()


def test_reconcile_repairs_only_a_revalidated_pointer_timestamp(tmp_path: Path) -> None:
    namespace_dir = _fixture(tmp_path)
    publication.reconcile_current_publication(
        tmp_path,
        dashboard={"owned": True, "running": True, "reason": "owned_running"},
        recorded_at=NOW,
    )
    receipt = read_json_object(
        namespace_dir / publication.PUBLICATION_RECEIPT_FILENAME
    )
    pointer = read_json_object(tmp_path / "radar_current_namespace.json")
    pointer["authority_checked_at"] = "2026-07-15T12:05:00+00:00"
    write_json_atomic(tmp_path / "radar_current_namespace.json", pointer)

    result = publication.reconcile_current_publication(
        tmp_path,
        dashboard={"owned": True, "running": True, "reason": "owned_running"},
        recorded_at="2026-07-15T12:06:00+00:00",
    )

    assert result.valid is True
    assert read_json_object(tmp_path / "radar_current_namespace.json") == receipt[
        "pointer"
    ]


def test_receipts_are_create_only_and_tampering_breaks_contract(
    tmp_path: Path,
) -> None:
    namespace_dir = _fixture(tmp_path)
    publication.seal_prepublication_audit(tmp_path, NAMESPACE)
    publication.write_publication_receipt(
        tmp_path,
        NAMESPACE,
        cycle_id=CYCLE_ID,
        recorded_at=NOW,
    )

    with pytest.raises(
        publication.DailyOperationsPublicationError,
        match="publication_receipt_write_failed",
    ):
        publication.write_publication_receipt(
            tmp_path,
            NAMESPACE,
            cycle_id=CYCLE_ID,
            recorded_at=NOW,
        )

    receipt = read_json_object(
        namespace_dir / publication.PUBLICATION_RECEIPT_FILENAME
    )
    receipt["pointer_sha256"] = "0" * 64
    write_json_atomic(namespace_dir / publication.PUBLICATION_RECEIPT_FILENAME, receipt)
    invalid = publication.validate_final_publication_contract(
        tmp_path,
        NAMESPACE,
        require_current=True,
    )
    assert "publication_receipt_pointer_digest_mismatch" in invalid.errors


def test_equivalent_strict_doctor_reverification_preserves_publication(
    tmp_path: Path,
) -> None:
    namespace_dir = _fixture(tmp_path)
    publication.reconcile_current_publication(
        tmp_path,
        dashboard={"owned": True, "running": True, "reason": "owned_running"},
        recorded_at=NOW,
    )
    operator_path = namespace_dir / publication.OPERATOR_STATE_FILENAME
    operator = read_json_object(operator_path)
    operator["doctor"]["verified_at"] = "2026-07-15T12:10:00+00:00"
    operator["updated_at"] = "2026-07-15T12:10:00+00:00"
    write_json_atomic(operator_path, operator)

    equivalent = publication.validate_final_publication_contract(
        tmp_path,
        NAMESPACE,
        require_current=True,
        require_operations=True,
    )
    assert equivalent.valid is True

    operator["doctor"]["warning_count"] = 1
    write_json_atomic(operator_path, operator)
    changed = publication.validate_final_publication_contract(
        tmp_path,
        NAMESPACE,
        require_current=True,
        require_operations=True,
    )
    assert "publication_receipt_doctor_mismatch" in changed.errors


def test_reconcile_refuses_to_invent_missing_restart_success(tmp_path: Path) -> None:
    _fixture(tmp_path)
    write_jsonl(tmp_path / publication.CYCLE_LEDGER_FILENAME, [])

    with pytest.raises(
        publication.DailyOperationsPublicationError,
        match="current_authority_successful_terminal_cycle_not_unique",
    ):
        publication.reconcile_current_publication(
            tmp_path,
            dashboard={"owned": True, "running": True},
            recorded_at=NOW,
        )

    assert not (
        tmp_path / NAMESPACE / publication.PUBLICATION_RECEIPT_FILENAME
    ).exists()


@pytest.mark.parametrize(
    "tamper",
    ("missing_required_artifact", "schema_only_doctor"),
)
def test_reconcile_requires_complete_full_strict_operator_contract(
    tmp_path: Path,
    tamper: str,
) -> None:
    namespace_dir = _fixture(tmp_path)
    operator_path = namespace_dir / publication.OPERATOR_STATE_FILENAME
    operator = read_json_object(operator_path)
    if tamper == "missing_required_artifact":
        operator["artifacts"].pop("daily_brief")
    else:
        operator["doctor"]["schema_only"] = True
    write_json_atomic(operator_path, operator)
    pointer = read_json_object(tmp_path / "radar_current_namespace.json")
    pointer["operator_state_sha256"] = operator_state.operator_authority_digest(
        operator
    )
    write_json_atomic(tmp_path / "radar_current_namespace.json", pointer)

    with pytest.raises(
        publication.DailyOperationsPublicationError,
        match="publication_operator_state_invalid",
    ):
        publication.reconcile_current_publication(
            tmp_path,
            dashboard={"owned": True, "running": True},
            recorded_at=NOW,
        )

    assert not (
        namespace_dir / publication.PUBLICATION_RECEIPT_FILENAME
    ).exists()


def test_reconcile_rejects_blocked_full_strict_doctor(tmp_path: Path) -> None:
    namespace_dir = _fixture(tmp_path)
    operator_path = namespace_dir / publication.OPERATOR_STATE_FILENAME
    operator = read_json_object(operator_path)
    operator["doctor"]["status"] = "BLOCKED"
    write_json_atomic(operator_path, operator)
    pointer = read_json_object(tmp_path / "radar_current_namespace.json")
    pointer["operator_state_sha256"] = operator_state.operator_authority_digest(
        operator
    )
    write_json_atomic(tmp_path / "radar_current_namespace.json", pointer)

    with pytest.raises(
        publication.DailyOperationsPublicationError,
        match="publication_doctor_not_strict_clean",
    ):
        publication.reconcile_current_publication(
            tmp_path,
            dashboard={"owned": True, "running": True},
            recorded_at=NOW,
        )

    assert not (
        namespace_dir / publication.PUBLICATION_RECEIPT_FILENAME
    ).exists()


def test_operations_receipt_requires_current_owned_running_dashboard(
    tmp_path: Path,
) -> None:
    namespace_dir = _fixture(tmp_path)
    publication.seal_prepublication_audit(tmp_path, NAMESPACE)
    publication.write_publication_receipt(
        tmp_path,
        NAMESPACE,
        cycle_id=CYCLE_ID,
        recorded_at=NOW,
    )

    with pytest.raises(
        publication.DailyOperationsPublicationError,
        match="owned_dashboard_restart_not_verified",
    ):
        publication.write_operations_receipt(
            tmp_path,
            NAMESPACE,
            cycle_id=CYCLE_ID,
            dashboard={"owned": True, "running": False},
            recorded_at=NOW,
        )
    assert not (namespace_dir / publication.OPERATIONS_RECEIPT_FILENAME).exists()


def test_doctor_allows_prepublication_phase_but_blocks_current_missing_operations(
    tmp_path: Path,
) -> None:
    namespace_dir = _fixture(tmp_path)
    publication.seal_prepublication_audit(tmp_path, NAMESPACE)
    pointer = read_json_object(tmp_path / "radar_current_namespace.json")
    pointer["artifact_namespace"] = "prior_authority"
    write_json_atomic(tmp_path / "radar_current_namespace.json", pointer)
    blockers: list[str] = []
    doctor_operations._check_daily_operations_publication(
        SimpleNamespace(namespace_dir=namespace_dir), blockers
    )
    assert blockers == []

    operator = read_json_object(namespace_dir / publication.OPERATOR_STATE_FILENAME)
    pointer.update(
        {
            "artifact_namespace": NAMESPACE,
            "operator_state_sha256": operator_state.operator_authority_digest(
                operator
            ),
        }
    )
    write_json_atomic(tmp_path / "radar_current_namespace.json", pointer)
    publication.write_publication_receipt(
        tmp_path,
        NAMESPACE,
        cycle_id=CYCLE_ID,
        recorded_at=NOW,
    )
    blockers = []
    doctor_operations._check_daily_operations_publication(
        SimpleNamespace(namespace_dir=namespace_dir), blockers
    )
    assert any("current_authority_missing_operations_receipt" in row for row in blockers)


def test_doctor_blocks_an_unreadable_historical_receipt(tmp_path: Path) -> None:
    namespace_dir = _fixture(tmp_path)
    publication.seal_prepublication_audit(tmp_path, NAMESPACE)
    pointer = read_json_object(tmp_path / "radar_current_namespace.json")
    pointer["artifact_namespace"] = "prior_authority"
    write_json_atomic(tmp_path / "radar_current_namespace.json", pointer)
    write_bytes_atomic(
        namespace_dir / publication.PUBLICATION_RECEIPT_FILENAME,
        b"{not-json\n",
    )

    blockers: list[str] = []
    doctor_operations._check_daily_operations_publication(
        SimpleNamespace(namespace_dir=namespace_dir), blockers
    )

    assert any("publication_receipt_unreadable" in row for row in blockers)


def test_doctor_recognizes_current_managed_namespace_after_receipts_disappear(
    tmp_path: Path,
) -> None:
    namespace_dir = _fixture(tmp_path)
    publication.reconcile_current_publication(
        tmp_path,
        dashboard={"owned": True, "running": True, "reason": "owned_running"},
        recorded_at=NOW,
    )
    for filename in (
        publication.PREPUBLICATION_AUDIT_FILENAME,
        publication.PUBLICATION_RECEIPT_FILENAME,
        publication.OPERATIONS_RECEIPT_FILENAME,
    ):
        (namespace_dir / filename).unlink()

    blockers: list[str] = []
    doctor_operations._check_daily_operations_publication(
        SimpleNamespace(namespace_dir=namespace_dir), blockers
    )

    assert any(
        "current_authority_missing_publication_receipt" in row
        for row in blockers
    )
    assert any(
        "current_authority_missing_operations_receipt" in row
        for row in blockers
    )


def test_current_operations_contract_requires_valid_current_state(
    tmp_path: Path,
) -> None:
    _fixture(tmp_path)
    publication.reconcile_current_publication(
        tmp_path,
        dashboard={"owned": True, "running": True, "reason": "owned_running"},
        recorded_at=NOW,
    )
    (tmp_path / publication.STATE_FILENAME).unlink()

    result = publication.validate_final_publication_contract(
        tmp_path,
        NAMESPACE,
        require_current=True,
        require_operations=True,
    )

    assert result.valid is False
    assert "operations_receipt_current_maintenance_state_mismatch" in result.errors


def test_later_failed_terminal_row_invalidates_prior_success_receipt(
    tmp_path: Path,
) -> None:
    _fixture(tmp_path)
    publication.reconcile_current_publication(
        tmp_path,
        dashboard={"owned": True, "running": True, "reason": "owned_running"},
        recorded_at=NOW,
    )
    rows = read_jsonl(tmp_path / publication.CYCLE_LEDGER_FILENAME)
    failed = dict(rows[-1])
    failed.update(
        {
            "recorded_at": "2026-07-15T12:01:00+00:00",
            "status": "failed",
            "reason": "post_publication_failure",
            "pointer_published": False,
            "dashboard_restarted": False,
        }
    )
    write_jsonl(tmp_path / publication.CYCLE_LEDGER_FILENAME, [*rows, failed])

    result = publication.validate_final_publication_contract(
        tmp_path,
        NAMESPACE,
        require_current=True,
        require_operations=True,
    )

    assert result.valid is False
    assert "operations_receipt_terminal_cycle_missing" in result.errors


def test_current_operations_contract_allows_later_non_success_cycle(
    tmp_path: Path,
) -> None:
    _fixture(tmp_path)
    publication.reconcile_current_publication(
        tmp_path,
        dashboard={"owned": True, "running": True, "reason": "owned_running"},
        recorded_at=NOW,
    )
    later_at = "2026-07-15T13:00:00+00:00"
    later_cycle_id = "b" * 32
    rows = read_jsonl(tmp_path / publication.CYCLE_LEDGER_FILENAME)
    rows.append(
        {
            "contract_version": 1,
            "row_type": "decision_radar_daily_operations_cycle",
            "cycle_id": later_cycle_id,
            "recorded_at": later_at,
            "artifact_namespace": "radar_market_no_send_later_blocked",
            "status": "blocked",
            "reason": "provider_authorization_missing",
            "provider_call_attempted": False,
            "provider_request_succeeded": False,
            "pointer_published": False,
            "dashboard_restarted": False,
            "pointer_rolled_back": False,
            "pointer_invalidated": False,
            **SAFETY_COUNTERS,
            "no_send": True,
            "research_only": True,
        }
    )
    write_jsonl(tmp_path / publication.CYCLE_LEDGER_FILENAME, rows)
    state_path = tmp_path / publication.STATE_FILENAME
    state = read_json_object(state_path)
    state.update(
        {
            "updated_at": later_at,
            "last_cycle_id": later_cycle_id,
            "last_cycle_status": "blocked",
            "last_cycle_reason": "provider_authorization_missing",
            "last_cycle_namespace": "radar_market_no_send_later_blocked",
            "last_readiness_check": later_at,
            "authorization_at_last_cycle": False,
            "authorization_checked_at_last_cycle": later_at,
            "live_provider_authorized": False,
            "provider_call_attempted": False,
            "pointer_published": False,
            "dashboard_restarted": False,
        }
    )
    write_json_atomic(state_path, state)

    valid = publication.validate_final_publication_contract(
        tmp_path,
        NAMESPACE,
        require_current=True,
        require_operations=True,
    )

    assert valid.valid is True

    state["last_successful_publication"] = later_at
    write_json_atomic(state_path, state)
    drifted = publication.validate_final_publication_contract(
        tmp_path,
        NAMESPACE,
        require_current=True,
        require_operations=True,
    )
    assert "operations_receipt_current_maintenance_state_mismatch" in drifted.errors


def test_current_operations_contract_rejects_partial_provider_attempt_projection(
    tmp_path: Path,
) -> None:
    _fixture(tmp_path)
    publication.reconcile_current_publication(
        tmp_path,
        dashboard={"owned": True, "running": True, "reason": "owned_running"},
        recorded_at=NOW,
    )
    state_path = tmp_path / publication.STATE_FILENAME
    state = read_json_object(state_path)
    state["last_provider_attempt_status"] = "failed"
    write_json_atomic(state_path, state)

    result = publication.validate_final_publication_contract(
        tmp_path,
        NAMESPACE,
        require_current=True,
        require_operations=True,
    )

    assert result.valid is False
    assert "operations_receipt_current_maintenance_state_mismatch" in result.errors


@pytest.mark.parametrize("counter_value", ("not-an-integer", "0", False, 0.0, None))
def test_malformed_receipt_counter_returns_closed_invalid_result(
    tmp_path: Path,
    counter_value: object,
) -> None:
    namespace_dir = _fixture(tmp_path)
    publication.seal_prepublication_audit(tmp_path, NAMESPACE)
    publication.write_publication_receipt(
        tmp_path,
        NAMESPACE,
        cycle_id=CYCLE_ID,
        recorded_at=NOW,
    )
    receipt_path = namespace_dir / publication.PUBLICATION_RECEIPT_FILENAME
    receipt = read_json_object(receipt_path)
    receipt["safety"]["telegram_sends"] = counter_value
    write_json_atomic(receipt_path, receipt)

    result = publication.validate_final_publication_contract(
        tmp_path,
        NAMESPACE,
        require_current=True,
    )

    assert result.valid is False
    assert "publication_receipt_safety_mismatch" in result.errors
