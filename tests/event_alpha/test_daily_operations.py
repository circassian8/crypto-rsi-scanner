"""Focused Daily Operations coordinator tests with injected boundaries."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from crypto_rsi_scanner.event_alpha.operations import daily_operations
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
        self.calendar_path: Path | None = None
        self.calendar_resolver_failure = False
        self.last_run_environ: dict[str, str] = {}

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

    def publish(self, _base: Path, namespace: str) -> object:
        self.events.append("publish")
        self.pointer = namespace
        return object()

    def current(self, _base: Path) -> str:
        self.events.append("current_pointer")
        return self.pointer

    def rollback(self, _base: Path, namespace: str) -> bool:
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
    assert fake.pointer == result.artifact_namespace
    rows = read_jsonl(tmp_path / CYCLE_LEDGER_FILENAME)
    assert [row["status"] for row in rows] == ["attempted", "succeeded"]
    assert all(row["telegram_sends"] == 0 for row in rows)
    state = read_json_object(tmp_path / STATE_FILENAME)
    assert state["last_successful_namespace"] == result.artifact_namespace
    assert state["last_successful_publication"]


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
