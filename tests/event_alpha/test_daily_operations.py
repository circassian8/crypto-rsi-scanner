"""Focused Daily Operations coordinator tests with injected boundaries."""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from crypto_rsi_scanner.event_alpha.operations import daily_operations
from crypto_rsi_scanner.event_alpha.operations import daily_operations_pointer
from crypto_rsi_scanner.event_alpha.operations.daily_operations import (
    CYCLE_LEDGER_FILENAME,
    STATE_FILENAME,
    DailyOperationsDependencies,
    DailyOperationsError,
    run_daily_operations_cycle,
)
from crypto_rsi_scanner.event_alpha.operations.daily_operations_service import (
    DashboardOwnership,
    SchedulerHealth,
)
from crypto_rsi_scanner.event_alpha.operations.market_no_send_attempt import (
    LATEST_ATTEMPT_FILENAME,
)
from crypto_rsi_scanner.event_alpha.operations.market_no_send_io import (
    read_json_object,
    read_jsonl,
    write_json_atomic,
)
from crypto_rsi_scanner.event_alpha.operations.market_no_send_models import (
    MarketNoSendGenerationResult,
    MarketNoSendReadiness,
)


NOW = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)


def _pointer_payload(
    namespace: str,
    *,
    checked_at: str,
    digest_character: str = "a",
) -> dict[str, object]:
    return {
        "contract_version": 1,
        "artifact_namespace": namespace,
        "profile": "no_key_live",
        "run_id": f"run-{namespace}",
        "revision": 12,
        "operator_state_sha256": digest_character * 64,
        "generation_authority_status": "authoritative",
        "authority_checked_at": checked_at,
    }


def _readiness(
    namespace: str,
    *,
    authorized: bool = True,
    status: str = "ready",
    cadence_status: str = "eligible",
    reasons: tuple[str, ...] = (),
    next_eligible: str = "2026-07-15T13:00:00+00:00",
) -> MarketNoSendReadiness:
    return MarketNoSendReadiness(
        status=status,
        provider="coingecko",
        live_provider_authorized=authorized,
        provider_call_attempted=False,
        fixture_mode=False,
        no_send=True,
        research_only=True,
        top_n=30,
        fetch_limit=50,
        artifact_namespace=namespace,
        reasons=reasons,
        will_call_provider=status == "ready",
        cadence_status=cadence_status,
        next_eligible_observation_at=next_eligible,
    )


def _generation(namespace: str) -> MarketNoSendGenerationResult:
    return MarketNoSendGenerationResult(
        status="complete",
        profile="no_key_live",
        artifact_namespace=namespace,
        namespace_dir=Path("/tmp") / namespace,
        data_mode="live",
        provider="coingecko",
        observed_at=NOW.isoformat(),
        live_provider_authorized=True,
        provider_call_attempted=True,
        provider_request_succeeded=True,
        run_id="run-daily-ops",
        data_acquisition_mode="live_provider",
        candidate_source_mode="live_no_send",
        provenance_contract_valid=True,
    )


class _Boundaries:
    def __init__(
        self,
        *,
        authorized: bool = True,
        readiness_status: str = "ready",
        cadence_status: str = "eligible",
        dashboard_owned: bool = True,
        post_attempt_next_eligible: str = "2026-07-15T13:00:00+00:00",
    ) -> None:
        self.authorized = authorized
        self.readiness_status = readiness_status
        self.cadence_status = cadence_status
        self.dashboard_owned = dashboard_owned
        self.post_attempt_next_eligible = post_attempt_next_eligible
        self.readiness_calls = 0
        self.events: list[str] = []
        self.pointer = "previous-authority"
        self.restart_results = [True]
        self.rollback_result = True
        self.invalidate_result = True
        self.doctor_failure = False
        self.run_failure = False
        self.publish_failure = False
        self.calendar_path: Path | None = None
        self.calendar_resolver_failure = False
        self.last_run_environ: dict[str, str] = {}
        self.publication_receipt_failure = False
        self.operations_receipt_failure = False
        self.operations_receipt_overrides: dict[str, object] = {}
        self.final_validation_failure = False
        self.dashboard_probe_result = True
        self.last_probe_kwargs: dict[str, object] = {}
        self.current_pointer_failure = False

    def token_hex(self, size: int) -> str:
        return ("a" if size == 16 else "b") * (size * 2)

    def readiness(self, **kwargs: Any) -> MarketNoSendReadiness:
        self.events.append("readiness")
        self.readiness_calls += 1
        reasons: tuple[str, ...] = ()
        if not self.authorized:
            reasons = ("RSI_EVENT_DISCOVERY_UNIVERSE_LIVE=1 is required",)
        elif self.cadence_status == "waiting":
            reasons = ("observation cadence window has not elapsed",)
        return _readiness(
            kwargs["artifact_namespace"],
            authorized=self.authorized,
            status=self.readiness_status,
            cadence_status=self.cadence_status,
            reasons=reasons,
            next_eligible=(
                self.post_attempt_next_eligible
                if self.readiness_calls > 1
                else "2026-07-15T13:00:00+00:00"
            ),
        )

    def inspect_dashboard(self, **_kwargs: Any) -> DashboardOwnership:
        self.events.append("dashboard_preflight")
        return DashboardOwnership(
            self.dashboard_owned,
            True,
            self.dashboard_owned,
            "owned_running" if self.dashboard_owned else "dashboard_argv_mismatch",
            321 if self.dashboard_owned else None,
        )

    def wait_dashboard(self, **_kwargs: Any) -> DashboardOwnership:
        self.events.append("dashboard_restart_wait")
        return DashboardOwnership(
            self.dashboard_owned,
            True,
            self.dashboard_owned,
            "owned_running" if self.dashboard_owned else "dashboard_argv_mismatch",
            321 if self.dashboard_owned else None,
        )

    def scheduler(self, **_kwargs: Any) -> SchedulerHealth:
        self.events.append("scheduler_status")
        return SchedulerHealth(
            enabled=False,
            installed=False,
            loaded=False,
            running=False,
            healthy=True,
            reason="service_not_installed",
        )

    def run(self, **kwargs: Any) -> MarketNoSendGenerationResult:
        self.events.append("run")
        self.last_run_environ = dict(kwargs.get("environ") or {})
        if self.run_failure:
            raise RuntimeError("provider response must not escape")
        return _generation(kwargs["artifact_namespace"])

    def resolve_calendar(self, _base: str | Path) -> Path | None:
        self.events.append("resolve_calendar")
        if self.calendar_resolver_failure:
            from crypto_rsi_scanner.event_alpha.operations.official_macro_calendar import (
                OfficialMacroAcquisitionError,
            )

            raise OfficialMacroAcquisitionError("latest_success_attestation_failed")
        return self.calendar_path

    def record(self, _base: Path, _namespace: str, _result: Any) -> Path:
        self.events.append("record_attempt")
        return _base / LATEST_ATTEMPT_FILENAME

    def boundary_failure(self, base: Path, namespace: str, **_kwargs: Any) -> Path:
        self.events.append("record_boundary_failure")
        path = base / LATEST_ATTEMPT_FILENAME
        write_json_atomic(
            path,
            {
                "artifact_namespace": namespace,
                "provider_call_attempted": True,
                "provider_request_succeeded": False,
            },
        )
        return path

    def audit(self, _base: Path, _namespace: str, _result: Any) -> None:
        self.events.append("audit")

    def status(self, _base: Path, _namespace: str) -> dict[str, object]:
        self.events.append("generation_status")
        return {"complete": True}

    def doctor(self, _base: Path, _namespace: str) -> None:
        self.events.append("doctor")
        if self.doctor_failure:
            raise DailyOperationsError("strict_doctor_failed")

    def publish(
        self,
        _base: Path,
        namespace: str,
        _previous_pointer: Any,
    ) -> object:
        self.events.append("publish")
        if self.publish_failure:
            raise OSError("sanitized publication failure")
        self.pointer = namespace
        return object()

    def publication_receipt(
        self, _base: Path, _namespace: str, _cycle_id: str
    ) -> dict[str, object]:
        self.events.append("publication_receipt")
        if self.publication_receipt_failure:
            raise OSError("sanitized immutable receipt failure")
        return {"status": "published"}

    def operations_receipt(
        self,
        _base: Path,
        _namespace: str,
        _cycle_id: str,
        _dashboard: DashboardOwnership,
    ) -> dict[str, object]:
        self.events.append("operations_receipt")
        if self.operations_receipt_failure:
            raise OSError("sanitized operations receipt failure")
        return {
            "status": "dashboard_restarted",
            "cycle_id": _cycle_id,
            "artifact_namespace": _namespace,
            "run_id": "run-daily-ops",
            "revision": 12,
            "operator_state_sha256": "a" * 64,
            **self.operations_receipt_overrides,
        }

    def validate_final(self, _base: Path, _namespace: str) -> None:
        self.events.append("validate_final_publication")
        if self.final_validation_failure:
            raise OSError("sanitized final validation failure")

    def refresh_campaign(self, _base: Path) -> None:
        self.events.append("refresh_campaign_report")

    def probe_dashboard(self, **kwargs: Any) -> bool:
        self.events.append("dashboard_postreceipt_probe")
        self.last_probe_kwargs = dict(kwargs)
        return self.dashboard_probe_result

    def persist_current_status(
        self, _base: Path, _readiness: Any
    ) -> None:
        self.events.append("persist_current_status")

    def current(self, _base: Path) -> str:
        self.events.append("current_pointer")
        if self.current_pointer_failure:
            raise OSError("sanitized current pointer failure")
        return self.pointer

    def rollback(
        self,
        _base: Path,
        _failed_namespace: str,
        namespace: str,
    ) -> bool:
        self.events.append("rollback")
        if self.rollback_result:
            self.pointer = namespace
        return self.rollback_result

    def invalidate(self, _base: Path, namespace: str) -> bool:
        self.events.append("invalidate_pointer")
        if self.invalidate_result and self.pointer == namespace:
            self.pointer = None
        return self.invalidate_result

    def campaign_cadence(self, _base: Path, **_kwargs: Any) -> dict[str, object]:
        self.events.append("campaign_cadence")
        return {"next_provider_call_at": self.post_attempt_next_eligible}

    def restart(self, **_kwargs: Any) -> bool:
        self.events.append("restart")
        if len(self.restart_results) > 1:
            return self.restart_results.pop(0)
        return self.restart_results[0]

    def dependencies(self) -> DailyOperationsDependencies:
        return DailyOperationsDependencies(
            environ={
                "RSI_EVENT_DISCOVERY_UNIVERSE_LIVE": "1" if self.authorized else "0"
            },
            now=lambda: NOW,
            token_hex=self.token_hex,
            readiness=self.readiness,
            run_generation=self.run,
            record_attempt=self.record,
            record_boundary_failure=self.boundary_failure,
            write_audit=self.audit,
            write_publication_receipt=self.publication_receipt,
            write_operations_receipt=self.operations_receipt,
            validate_final_publication=self.validate_final,
            refresh_campaign_report=self.refresh_campaign,
            persist_current_status=self.persist_current_status,
            generation_status=self.status,
            strict_doctor=self.doctor,
            publish=self.publish,
            current_namespace=self.current,
            rollback=self.rollback,
            invalidate_pointer=self.invalidate,
            resolve_calendar_snapshot=self.resolve_calendar,
            campaign_cadence=self.campaign_cadence,
            inspect_dashboard=self.inspect_dashboard,
            restart_dashboard=self.restart,
            wait_dashboard_process=self.wait_dashboard,
            probe_dashboard=self.probe_dashboard,
            scheduler_health=self.scheduler,
        )


def test_dry_run_without_authorization_has_no_writes_or_provider_call(
    tmp_path: Path,
) -> None:
    fake = _Boundaries(authorized=False, readiness_status="blocked")

    result = run_daily_operations_cycle(
        artifact_base_dir=tmp_path,
        top_n=30,
        fetch_limit=None,
        dry_run=True,
        dependencies=fake.dependencies(),
    )

    assert result.status == "dry_run"
    assert result.reason == "provider_authorization_missing"
    assert "run" not in fake.events
    assert "publish" not in fake.events
    assert "restart" not in fake.events
    assert list(tmp_path.iterdir()) == []


def test_public_main_preserves_cli_dependency_injection(
    tmp_path: Path,
    capsys: Any,
) -> None:
    fake = _Boundaries(authorized=False, readiness_status="blocked")

    exit_code = daily_operations.main(
        [
            "cycle",
            "--dry-run",
            "--artifact-base",
            str(tmp_path),
            "--top-n",
            "30",
        ],
        dependencies=fake.dependencies(),
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "dry_run"
    assert payload["reason"] == "provider_authorization_missing"
    assert "run" not in fake.events
    assert list(tmp_path.iterdir()) == []


def test_cycle_without_authorization_journals_blocked_without_provider_call(
    tmp_path: Path,
) -> None:
    fake = _Boundaries(authorized=False, readiness_status="blocked")

    result = run_daily_operations_cycle(
        artifact_base_dir=tmp_path,
        top_n=30,
        fetch_limit=None,
        dependencies=fake.dependencies(),
    )

    assert result.status == "blocked"
    assert result.reason == "provider_authorization_missing"
    assert "run" not in fake.events
    assert [row["status"] for row in read_jsonl(tmp_path / CYCLE_LEDGER_FILENAME)] == [
        "attempted",
        "blocked",
    ]
    state = read_json_object(tmp_path / STATE_FILENAME)
    assert state["live_provider_authorized"] is False
    assert state["scheduler_enabled"] is False
    assert state["provider_call_attempted"] is False


def test_cadence_waiting_is_an_explicit_skipped_cycle(tmp_path: Path) -> None:
    fake = _Boundaries(readiness_status="blocked", cadence_status="waiting")

    result = run_daily_operations_cycle(
        artifact_base_dir=tmp_path,
        top_n=30,
        fetch_limit=None,
        dependencies=fake.dependencies(),
    )

    assert result.status == "skipped"
    assert result.reason == "observation_cadence_waiting"
    assert "run" not in fake.events
    assert read_jsonl(tmp_path / CYCLE_LEDGER_FILENAME)[-1]["status"] == "skipped"


def test_eligible_cycle_publishes_then_restarts_exact_owned_dashboard(
    tmp_path: Path,
) -> None:
    fake = _Boundaries()

    result = run_daily_operations_cycle(
        artifact_base_dir=tmp_path,
        top_n=30,
        fetch_limit=50,
        dependencies=fake.dependencies(),
    )

    assert result.status == "succeeded"
    assert result.provider_call_attempted is True
    assert result.provider_request_succeeded is True
    assert result.pointer_published is True
    assert result.dashboard_restarted is True
    assert fake.events.count("run") == 1
    assert fake.events.index("readiness") < fake.events.index("run")
    assert fake.events.index("doctor") < fake.events.index("publish")
    assert fake.events.index("publish") < fake.events.index("restart")
    assert fake.events.index("operations_receipt") < fake.events.index(
        "dashboard_postreceipt_probe"
    )
    assert fake.events.index("validate_final_publication") < fake.events.index(
        "dashboard_postreceipt_probe"
    )
    assert fake.events.index("dashboard_postreceipt_probe") < fake.events.index(
        "refresh_campaign_report"
    )
    assert fake.last_probe_kwargs == {
        "artifact_base": tmp_path,
        "expected_namespace": result.artifact_namespace,
        "expected_run_id": "run-daily-ops",
        "expected_revision": 12,
        "expected_operator_state_sha256": "a" * 64,
    }
    assert fake.pointer == result.artifact_namespace
    rows = read_jsonl(tmp_path / CYCLE_LEDGER_FILENAME)
    assert [row["status"] for row in rows] == ["attempted", "succeeded"]
    assert all(row["telegram_sends"] == 0 for row in rows)
    state = read_json_object(tmp_path / STATE_FILENAME)
    assert state["last_successful_namespace"] == result.artifact_namespace
    assert state["last_successful_publication"]


@pytest.mark.parametrize(
    ("scenario", "expected_status"),
    (
        ("authorization_blocked", "blocked"),
        ("cadence_waiting", "skipped"),
        ("cycle_already_running", "skipped"),
        ("readiness_failed", "failed"),
        ("calendar_attestation_failed", "blocked"),
        ("current_pointer_failed", "failed"),
        ("provider_boundary_failed", "failed"),
        ("strict_doctor_failed", "failed"),
        ("publication_failed", "failed"),
        ("dashboard_restart_failed", "failed"),
        ("operations_receipt_failed", "failed"),
        ("dashboard_probe_failed", "failed"),
        ("succeeded", "succeeded"),
    ),
)
def test_every_terminal_cycle_refreshes_campaign_truth_exactly_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
    expected_status: str,
) -> None:
    fake = _Boundaries(
        authorized=scenario != "authorization_blocked",
        readiness_status=(
            "blocked"
            if scenario in {"authorization_blocked", "cadence_waiting"}
            else "ready"
        ),
        cadence_status=("waiting" if scenario == "cadence_waiting" else "eligible"),
    )
    fake.calendar_resolver_failure = scenario == "calendar_attestation_failed"
    fake.current_pointer_failure = scenario == "current_pointer_failed"
    fake.run_failure = scenario == "provider_boundary_failed"
    fake.doctor_failure = scenario == "strict_doctor_failed"
    fake.publish_failure = scenario == "publication_failed"
    fake.operations_receipt_failure = scenario == "operations_receipt_failed"
    fake.dashboard_probe_result = scenario != "dashboard_probe_failed"
    if scenario == "dashboard_restart_failed":
        fake.restart_results = [False, True]
    if scenario == "cycle_already_running":
        monkeypatch.setattr(
            daily_operations,
            "_cycle_lock",
            lambda _base: nullcontext(False),
        )
    if scenario == "readiness_failed":
        def failed_readiness(**_kwargs: Any) -> MarketNoSendReadiness:
            raise OSError("sanitized readiness boundary failure")

        fake.readiness = failed_readiness

    result = run_daily_operations_cycle(
        artifact_base_dir=tmp_path,
        top_n=30,
        fetch_limit=50,
        dependencies=fake.dependencies(),
    )

    assert result.status == expected_status
    assert fake.events.count("refresh_campaign_report") == 1
    assert read_jsonl(tmp_path / CYCLE_LEDGER_FILENAME)[-1]["status"] == (
        expected_status
    )


def test_success_state_uses_post_attempt_next_eligible_time(tmp_path: Path) -> None:
    post_attempt = "2026-07-15T14:00:00+00:00"
    fake = _Boundaries(post_attempt_next_eligible=post_attempt)

    result = run_daily_operations_cycle(
        artifact_base_dir=tmp_path,
        top_n=30,
        fetch_limit=50,
        dependencies=fake.dependencies(),
    )

    assert result.status == "succeeded"
    assert fake.events.count("run") == 1
    assert fake.events.count("readiness") == 2
    state = read_json_object(tmp_path / STATE_FILENAME)
    assert state["next_eligible_observation_at"] == post_attempt


def test_cycle_passes_hash_attested_official_calendar_to_generation(
    tmp_path: Path,
) -> None:
    fake = _Boundaries()
    fake.calendar_path = tmp_path / "official_macro_calendar.json"

    result = run_daily_operations_cycle(
        artifact_base_dir=tmp_path,
        top_n=30,
        fetch_limit=50,
        dependencies=fake.dependencies(),
    )

    assert result.status == "succeeded"
    assert fake.events.index("resolve_calendar") < fake.events.index("run")
    assert fake.last_run_environ[
        "RSI_DECISION_RADAR_CALENDAR_SNAPSHOT_PATH"
    ] == str(fake.calendar_path)


def test_invalid_official_calendar_pointer_blocks_before_provider_boundary(
    tmp_path: Path,
) -> None:
    fake = _Boundaries()
    fake.calendar_resolver_failure = True

    result = run_daily_operations_cycle(
        artifact_base_dir=tmp_path,
        top_n=30,
        fetch_limit=50,
        dependencies=fake.dependencies(),
    )

    assert result.status == "blocked"
    assert result.reason == "calendar_snapshot_attestation_failed"
    assert "run" not in fake.events
    assert "publish" not in fake.events
    assert "restart" not in fake.events
    assert read_jsonl(tmp_path / CYCLE_LEDGER_FILENAME)[-1][
        "provider_call_attempted"
    ] is False


def test_strict_doctor_failure_never_calls_publish_and_preserves_pointer(
    tmp_path: Path,
) -> None:
    fake = _Boundaries()
    fake.doctor_failure = True

    result = run_daily_operations_cycle(
        artifact_base_dir=tmp_path,
        top_n=30,
        fetch_limit=None,
        dependencies=fake.dependencies(),
    )

    assert result.status == "failed"
    assert result.reason == "strict_doctor_failed"
    assert fake.pointer == "previous-authority"
    assert "publish" not in fake.events
    assert "restart" not in fake.events
    row = read_jsonl(tmp_path / CYCLE_LEDGER_FILENAME)[-1]
    assert row["provider_call_attempted"] is True
    assert row["pointer_published"] is False


def test_untrusted_current_pointer_blocks_before_provider_boundary(
    tmp_path: Path,
) -> None:
    fake = _Boundaries()
    fake.current_pointer_failure = True

    result = run_daily_operations_cycle(
        artifact_base_dir=tmp_path,
        top_n=30,
        fetch_limit=None,
        dependencies=fake.dependencies(),
    )

    assert result.status == "failed"
    assert result.reason == "current_pointer_unavailable"
    assert "run" not in fake.events
    assert "publish" not in fake.events
    assert "rollback" not in fake.events


def test_default_rollback_restores_exact_prior_pointer_bytes_without_receipt_mutation(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    pointer_path = tmp_path / daily_operations.CURRENT_NAMESPACE_POINTER
    prior_namespace = "prior-authority"
    failed_namespace = "failed-new-authority"
    write_json_atomic(
        pointer_path,
        _pointer_payload(
            prior_namespace,
            checked_at="2026-07-14T22:15:57.576094+00:00",
        ),
    )
    prior_raw = pointer_path.read_bytes()
    prior_dir = tmp_path / prior_namespace
    prior_dir.mkdir()
    receipt_path = prior_dir / "event_radar_publication_receipt.json"
    write_json_atomic(receipt_path, {"immutable": "prior-publication-receipt"})
    receipt_raw = receipt_path.read_bytes()
    snapshot = daily_operations._default_current_namespace(tmp_path)
    assert snapshot is not None

    write_json_atomic(
        pointer_path,
        _pointer_payload(
            failed_namespace,
            checked_at="2026-07-15T12:00:00+00:00",
            digest_character="b",
        ),
    )
    monkeypatch.setattr(
        daily_operations_pointer,
        "_prior_pointer_is_still_authoritative",
        lambda *_args, **_kwargs: True,
    )

    assert daily_operations._default_rollback(
        tmp_path,
        failed_namespace,
        snapshot,
    ) is True
    assert pointer_path.read_bytes() == prior_raw
    assert read_json_object(pointer_path)["authority_checked_at"] == (
        "2026-07-14T22:15:57.576094+00:00"
    )
    assert receipt_path.read_bytes() == receipt_raw


def test_default_rollback_refuses_missing_unsafe_or_drifted_pointer(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    pointer_path = tmp_path / daily_operations.CURRENT_NAMESPACE_POINTER
    assert daily_operations._default_current_namespace(tmp_path) is None

    unsafe_target = tmp_path / "unsafe-pointer-target.json"
    write_json_atomic(
        unsafe_target,
        _pointer_payload(
            "unsafe-authority",
            checked_at="2026-07-15T11:00:00+00:00",
        ),
    )
    pointer_path.symlink_to(unsafe_target)
    with pytest.raises(DailyOperationsError, match="current_pointer_unavailable"):
        daily_operations._default_current_namespace(tmp_path)
    pointer_path.unlink()

    write_json_atomic(
        pointer_path,
        _pointer_payload(
            "prior-authority",
            checked_at="2026-07-14T22:15:57.576094+00:00",
        ),
    )
    snapshot = daily_operations._default_current_namespace(tmp_path)
    assert snapshot is not None
    write_json_atomic(
        pointer_path,
        _pointer_payload(
            "externally-changed-authority",
            checked_at="2026-07-15T12:01:00+00:00",
            digest_character="c",
        ),
    )
    drifted_raw = pointer_path.read_bytes()
    monkeypatch.setattr(
        daily_operations_pointer,
        "_prior_pointer_is_still_authoritative",
        lambda *_args, **_kwargs: True,
    )

    assert daily_operations._default_rollback(
        tmp_path,
        "failed-new-authority",
        snapshot,
    ) is False
    assert pointer_path.read_bytes() == drifted_raw


def test_default_rollback_refuses_prior_authority_validation_drift(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    pointer_path = tmp_path / daily_operations.CURRENT_NAMESPACE_POINTER
    write_json_atomic(
        pointer_path,
        _pointer_payload(
            "prior-authority",
            checked_at="2026-07-14T22:15:57.576094+00:00",
        ),
    )
    snapshot = daily_operations._default_current_namespace(tmp_path)
    assert snapshot is not None
    write_json_atomic(
        pointer_path,
        _pointer_payload(
            "failed-new-authority",
            checked_at="2026-07-15T12:00:00+00:00",
            digest_character="b",
        ),
    )
    failed_raw = pointer_path.read_bytes()
    monkeypatch.setattr(
        daily_operations_pointer,
        "_prior_pointer_is_still_authoritative",
        lambda *_args, **_kwargs: False,
    )

    assert daily_operations._default_rollback(
        tmp_path,
        "failed-new-authority",
        snapshot,
    ) is False
    assert pointer_path.read_bytes() == failed_raw


def test_prior_rollback_requires_exact_saved_pointer_receipt_binding(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    pointer = _pointer_payload(
        "prior-authority",
        checked_at="2026-07-14T22:15:57.576094+00:00",
    )
    raw = (json.dumps(pointer, indent=2, sort_keys=True) + "\n").encode("utf-8")
    snapshot = daily_operations_pointer.CurrentPointerSnapshot(
        artifact_namespace="prior-authority",
        raw=raw,
        sha256=hashlib.sha256(raw).hexdigest(),
    )
    dashboard_snapshot = SimpleNamespace(
        artifact_namespace="prior-authority",
        profile=pointer["profile"],
        run_id=pointer["run_id"],
        revision=pointer["revision"],
        operator_state_sha256=pointer["operator_state_sha256"],
    )
    monkeypatch.setattr(
        daily_operations_pointer,
        "resolve_authoritative_dashboard",
        lambda *_args, **_kwargs: SimpleNamespace(snapshot=dashboard_snapshot),
    )
    receipt = {"pointer": dict(pointer), "pointer_sha256": "0" * 64}
    validation = SimpleNamespace(valid=True, publication_receipt=receipt)
    monkeypatch.setattr(
        daily_operations_pointer.daily_operations_publication,
        "validate_final_publication_contract",
        lambda *_args, **_kwargs: validation,
    )

    assert daily_operations_pointer._prior_pointer_is_still_authoritative(
        tmp_path,
        snapshot,
        pointer,
    ) is False
    receipt["pointer_sha256"] = snapshot.sha256
    receipt["pointer"] = {**pointer, "authority_checked_at": "2026-07-14T22:16:00+00:00"}
    assert daily_operations_pointer._prior_pointer_is_still_authoritative(
        tmp_path,
        snapshot,
        pointer,
    ) is False
    receipt["pointer"] = dict(pointer)
    assert daily_operations_pointer._prior_pointer_is_still_authoritative(
        tmp_path,
        snapshot,
        pointer,
    ) is True


def test_boundary_exception_recovers_reserved_provider_call_truth(
    tmp_path: Path,
) -> None:
    fake = _Boundaries()
    fake.run_failure = True

    result = run_daily_operations_cycle(
        artifact_base_dir=tmp_path,
        top_n=30,
        fetch_limit=None,
        dependencies=fake.dependencies(),
    )

    assert result.status == "failed"
    assert result.provider_call_attempted is True
    assert result.provider_request_succeeded is False
    assert "record_boundary_failure" in fake.events
    assert "publish" not in fake.events
    assert read_jsonl(tmp_path / CYCLE_LEDGER_FILENAME)[-1][
        "provider_call_attempted"
    ] is True


def test_failure_state_uses_post_attempt_reserved_next_eligible_time(
    tmp_path: Path,
) -> None:
    post_attempt = "2026-07-15T14:15:00+00:00"
    fake = _Boundaries(post_attempt_next_eligible=post_attempt)
    fake.run_failure = True

    result = run_daily_operations_cycle(
        artifact_base_dir=tmp_path,
        top_n=30,
        fetch_limit=None,
        dependencies=fake.dependencies(),
    )

    assert result.status == "failed"
    assert result.provider_call_attempted is True
    assert fake.events.count("run") == 1
    assert fake.events.count("readiness") == 2
    state = read_json_object(tmp_path / STATE_FILENAME)
    assert state["next_eligible_observation_at"] == post_attempt


def test_no_provider_attempt_does_not_advance_last_attempted_observation(
    tmp_path: Path,
) -> None:
    fake = _Boundaries()
    previous_attempt = "2026-07-14T10:00:00+00:00"
    write_json_atomic(
        tmp_path / STATE_FILENAME,
        {"last_attempted_observation": previous_attempt},
    )

    def blocked_generation(**kwargs: Any) -> MarketNoSendGenerationResult:
        return replace(
            _generation(kwargs["artifact_namespace"]),
            status="blocked",
            provider_call_attempted=False,
            provider_request_succeeded=False,
        )

    fake.run = blocked_generation

    result = run_daily_operations_cycle(
        artifact_base_dir=tmp_path,
        top_n=30,
        fetch_limit=50,
        dependencies=fake.dependencies(),
    )

    assert result.provider_call_attempted is False
    state = read_json_object(tmp_path / STATE_FILENAME)
    assert state["last_attempted_observation"] == previous_attempt


def test_restart_failure_rolls_back_previous_pointer(tmp_path: Path) -> None:
    fake = _Boundaries()
    fake.restart_results = [False, True]

    result = run_daily_operations_cycle(
        artifact_base_dir=tmp_path,
        top_n=30,
        fetch_limit=None,
        dependencies=fake.dependencies(),
    )

    assert result.status == "failed"
    assert result.reason == "dashboard_restart_failed"
    assert result.pointer_rolled_back is True
    assert result.pointer_published is False
    assert fake.pointer == "previous-authority"
    assert fake.events.index("publish") < fake.events.index("restart")
    assert fake.events.index("restart") < fake.events.index("rollback")


def test_failed_publication_has_no_success_receipt_and_rolls_back(
    tmp_path: Path,
) -> None:
    fake = _Boundaries()
    fake.publish_failure = True

    result = run_daily_operations_cycle(
        artifact_base_dir=tmp_path,
        top_n=30,
        fetch_limit=None,
        dependencies=fake.dependencies(),
    )

    assert result.status == "failed"
    assert result.reason == "publication_failed"
    assert result.pointer_rolled_back is True
    assert "publication_receipt" not in fake.events
    assert "operations_receipt" not in fake.events
    assert fake.events.index("publish") < fake.events.index("rollback")
    assert fake.events.index("rollback") < fake.events.index("restart")
    assert fake.pointer == "previous-authority"


def test_operations_receipt_failure_rolls_back_current_pointer(tmp_path: Path) -> None:
    fake = _Boundaries()
    fake.operations_receipt_failure = True

    result = run_daily_operations_cycle(
        artifact_base_dir=tmp_path,
        top_n=30,
        fetch_limit=None,
        dependencies=fake.dependencies(),
    )

    assert result.status == "failed"
    assert result.reason == "operations_receipt_failed"
    assert result.pointer_rolled_back is True
    assert fake.pointer == "previous-authority"
    assert fake.events.index("publication_receipt") < fake.events.index("restart")
    assert fake.events.index("restart") < fake.events.index("operations_receipt")


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("artifact_namespace", "other-namespace"),
        ("cycle_id", "c" * 32),
        ("run_id", "other-run"),
        ("revision", True),
        ("revision", 0),
        ("operator_state_sha256", "not-a-digest"),
    ),
)
def test_malformed_operations_receipt_never_reaches_dashboard_probe(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    fake = _Boundaries()
    fake.operations_receipt_overrides[field] = value

    result = run_daily_operations_cycle(
        artifact_base_dir=tmp_path,
        top_n=30,
        fetch_limit=None,
        dependencies=fake.dependencies(),
    )

    assert result.status == "failed"
    assert result.reason == "operations_receipt_failed"
    assert result.pointer_rolled_back is True
    assert "dashboard_postreceipt_probe" not in fake.events
    assert fake.pointer == "previous-authority"


def test_postreceipt_dashboard_probe_failure_rolls_back_current_pointer(
    tmp_path: Path,
) -> None:
    fake = _Boundaries()
    fake.dashboard_probe_result = False

    result = run_daily_operations_cycle(
        artifact_base_dir=tmp_path,
        top_n=30,
        fetch_limit=None,
        dependencies=fake.dependencies(),
    )

    assert result.status == "failed"
    assert result.reason == "dashboard_postreceipt_probe_failed"
    assert result.pointer_rolled_back is True
    assert fake.pointer == "previous-authority"
    assert fake.events.index("operations_receipt") < fake.events.index(
        "dashboard_postreceipt_probe"
    )
    assert fake.events.index("dashboard_postreceipt_probe") < fake.events.index(
        "rollback"
    )


def test_restart_failure_invalidates_new_pointer_when_rollback_fails(
    tmp_path: Path,
) -> None:
    fake = _Boundaries()
    fake.restart_results = [False]
    fake.rollback_result = False

    result = run_daily_operations_cycle(
        artifact_base_dir=tmp_path,
        top_n=30,
        fetch_limit=None,
        dependencies=fake.dependencies(),
    )

    assert result.status == "failed"
    assert result.pointer_rolled_back is False
    assert result.pointer_invalidated is True
    assert result.pointer_published is False
    assert fake.pointer is None
    assert fake.events.index("rollback") < fake.events.index("invalidate_pointer")


def test_restart_failure_with_no_prior_pointer_invalidates_failed_authority(
    tmp_path: Path,
) -> None:
    fake = _Boundaries()
    fake.pointer = None
    fake.restart_results = [False]

    result = run_daily_operations_cycle(
        artifact_base_dir=tmp_path,
        top_n=30,
        fetch_limit=None,
        dependencies=fake.dependencies(),
    )

    assert result.status == "failed"
    assert result.pointer_rolled_back is False
    assert result.pointer_invalidated is True
    assert fake.pointer is None
    assert "rollback" not in fake.events
    assert "invalidate_pointer" in fake.events


def test_restart_exception_rolls_back_and_records_terminal_failure(
    tmp_path: Path,
) -> None:
    fake = _Boundaries()

    def raise_once_then_succeed(**_kwargs: Any) -> bool:
        fake.events.append("restart")
        if fake.events.count("restart") == 1:
            raise OSError("sanitized restart boundary failure")
        return True

    fake.restart = raise_once_then_succeed

    result = run_daily_operations_cycle(
        artifact_base_dir=tmp_path,
        top_n=30,
        fetch_limit=None,
        dependencies=fake.dependencies(),
    )

    assert result.status == "failed"
    assert result.reason == "dashboard_restart_failed"
    assert result.pointer_rolled_back is True
    assert fake.pointer == "previous-authority"
    assert fake.events.count("restart") == 2
    assert read_jsonl(tmp_path / CYCLE_LEDGER_FILENAME)[-1]["status"] == "failed"


def test_terminal_state_failure_restores_previous_authority(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    fake = _Boundaries()
    original = daily_operations._record_terminal
    terminal_calls = 0

    def fail_once(*args: Any, **kwargs: Any) -> None:
        nonlocal terminal_calls
        terminal_calls += 1
        if terminal_calls == 1:
            raise OSError("simulated terminal persistence failure")
        original(*args, **kwargs)

    monkeypatch.setattr(daily_operations, "_record_terminal", fail_once)

    result = run_daily_operations_cycle(
        artifact_base_dir=tmp_path,
        top_n=30,
        fetch_limit=None,
        dependencies=fake.dependencies(),
    )

    assert result.status == "failed"
    assert result.reason == "postpublication_state_failed"
    assert result.pointer_rolled_back is True
    assert fake.pointer == "previous-authority"
    assert fake.events.count("restart") == 2
    state = read_json_object(tmp_path / STATE_FILENAME)
    assert state["last_cycle_status"] == "failed"


def test_unique_namespaces_include_subsecond_time_and_entropy() -> None:
    left = daily_operations.unique_namespace(NOW, "a" * 16)
    right = daily_operations.unique_namespace(NOW, "b" * 16)

    assert left != right
    assert left.startswith("radar_market_no_send_20260715t120000000000z_")
    assert right.endswith("_bbbbbbbbbbbb")
