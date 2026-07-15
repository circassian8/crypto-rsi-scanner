"""Guarded Decision Radar Daily Operations v1 coordinator.

The coordinator performs one readiness-gated, research-only market observation
at most, strict-doctors it, publishes it, and only then restarts the exact owned
loopback dashboard. Installation is delegated to the confirmation-gated service
module; importing or inspecting this module never installs a service.
"""

from __future__ import annotations

import fcntl
import os
import secrets
import stat
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence

from ... import config
from ..dashboard.readiness import (
    CURRENT_NAMESPACE_POINTER,
    _publish_prepublication_namespace_pointer,
)
from . import (
    daily_operations_current_status,
    daily_operations_pointer,
    daily_operations_service,
    daily_operations_publication,
    market_no_send,
    market_no_send_attempt,
    market_no_send_calendar,
    market_no_send_campaign_guard,
    market_observation_campaign,
    official_macro_calendar,
)
from .market_no_send_io import (
    _open_verified_namespace_dir,
    read_json_object,
    read_jsonl,
    write_json_atomic,
    write_jsonl,
)
from .market_no_send_models import (
    MarketNoSendGenerationResult,
    MarketNoSendReadiness,
    SAFETY_COUNTERS,
)


CONTRACT_VERSION = 1
STATE_FILENAME = "event_radar_daily_operations_state.json"
CYCLE_LEDGER_FILENAME = "event_radar_daily_operations_cycles.jsonl"
CYCLE_LEDGER_MAX_ROWS = 512
_CYCLE_LOCK_FILENAME = ".event_radar_daily_operations_cycle.lock"
_JOURNAL_LOCK_FILENAME = ".event_radar_daily_operations_journal.lock"
_TERMINAL_STATUSES = frozenset({"skipped", "blocked", "succeeded", "failed"})


class _DailyOperationsError(RuntimeError):
    """A concise, credential-free Daily Operations failure."""


DailyOperationsError = _DailyOperationsError


@dataclass(frozen=True)
class _DailyOperationsReadiness:
    checked_at: str
    artifact_namespace: str
    status: str
    reason: str
    market: MarketNoSendReadiness
    dashboard: daily_operations_service.DashboardOwnership
    scheduler: daily_operations_service.SchedulerHealth

    @property
    def ready(self) -> bool:
        return self.status == "ready"

    def to_dict(self) -> dict[str, object]:
        return {
            "contract_version": CONTRACT_VERSION,
            "checked_at": self.checked_at,
            "artifact_namespace": self.artifact_namespace,
            "status": self.status,
            "reason": self.reason,
            "ready": self.ready,
            "market": self.market.to_dict(),
            "dashboard": self.dashboard.to_dict(),
            "scheduler": self.scheduler.to_dict(),
            **SAFETY_COUNTERS,
            "no_send": True,
            "research_only": True,
        }


DailyOperationsReadiness = _DailyOperationsReadiness


@dataclass(frozen=True)
class _DailyOperationsCycleResult:
    cycle_id: str
    artifact_namespace: str
    status: str
    reason: str
    checked_at: str
    provider_call_attempted: bool = False
    provider_request_succeeded: bool = False
    pointer_published: bool = False
    dashboard_restarted: bool = False
    pointer_rolled_back: bool = False
    pointer_invalidated: bool = False
    dry_run: bool = False

    @property
    def ok(self) -> bool:
        return self.status in {"skipped", "blocked", "succeeded", "dry_run"}

    def to_dict(self) -> dict[str, object]:
        return {
            **asdict(self),
            "contract_version": CONTRACT_VERSION,
            "ok": self.ok,
            **SAFETY_COUNTERS,
            "no_send": True,
            "research_only": True,
        }


DailyOperationsCycleResult = _DailyOperationsCycleResult


_CurrentPointerSnapshot = daily_operations_pointer.CurrentPointerSnapshot


def _default_strict_doctor(base: Path, namespace: str) -> None:
    namespace_dir = base / namespace
    python = str(Path(sys.executable).expanduser().absolute())
    main_path = str(daily_operations_service.repository_root() / "main.py")
    environment = dict(os.environ)
    environment.update(
        {
            "RSI_EVENT_ALERTS_ENABLED": "0",
            "RSI_EVENT_ALPHA_RUN_MODE": "operational",
            "RSI_EVENT_ALPHA_TARGETED_MARKET_REFRESH_ENABLED": "0",
            "RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR": str(base),
        }
    )
    completed = subprocess.run(
        (
            python,
            main_path,
            "--event-alpha-artifact-doctor",
            "--event-alpha-profile",
            "no_key_live",
            "--event-alpha-artifact-namespace",
            namespace,
            "--event-alpha-artifact-doctor-strict",
        ),
        cwd=namespace_dir,
        env=environment,
        capture_output=True,
        text=True,
        timeout=180.0,
        check=False,
    )
    if completed.returncode != 0:
        raise DailyOperationsError("strict_doctor_failed")


def _default_audit(
    base: Path,
    namespace: str,
    result: MarketNoSendGenerationResult,
) -> None:
    market_no_send.write_market_no_send_pilot_audit(
        base,
        namespace,
        result=result,
    )
    daily_operations_publication.seal_prepublication_audit(base, namespace)


def _default_publication_receipt(
    base: Path,
    namespace: str,
    cycle_id: str,
) -> Mapping[str, Any]:
    return daily_operations_publication.write_publication_receipt(
        base,
        namespace,
        cycle_id=cycle_id,
    )


def _default_operations_receipt(
    base: Path,
    namespace: str,
    cycle_id: str,
    dashboard: daily_operations_service.DashboardOwnership,
) -> Mapping[str, Any]:
    return daily_operations_publication.write_operations_receipt(
        base,
        namespace,
        cycle_id=cycle_id,
        dashboard=dashboard,
    )


def _default_validate_final_publication(
    base: Path,
    namespace: str,
) -> None:
    validation = daily_operations_publication.validate_final_publication_contract(
        base,
        namespace,
        require_current=True,
        require_operations=True,
    )
    if not validation.valid:
        raise DailyOperationsError(validation.errors[0])


def _default_refresh_campaign_report(base: Path) -> None:
    output_dir = daily_operations_service.repository_root() / "research"
    market_observation_campaign.write_campaign_report(
        base,
        output_dir,
        evaluated_at=datetime.now(timezone.utc),
    )


def _default_persist_current_status(
    base: Path,
    readiness: DailyOperationsReadiness,
) -> None:
    daily_operations_current_status.persist_current_status(base, readiness)


def _default_current_namespace(base: Path) -> _CurrentPointerSnapshot | None:
    try:
        return daily_operations_pointer.current_namespace(base)
    except daily_operations_pointer.DailyOperationsPointerError as exc:
        raise DailyOperationsError("current_pointer_unavailable") from exc


def _default_rollback(
    base: Path,
    failed_namespace: str,
    previous_pointer: _CurrentPointerSnapshot | str,
) -> bool:
    return daily_operations_pointer.rollback(
        base,
        failed_namespace,
        previous_pointer,
    )


def _default_invalidate_pointer(base: Path, namespace: str) -> bool:
    return daily_operations_pointer.invalidate(base, namespace)


def _default_publish(
    base: Path,
    namespace: str,
    previous_pointer: _CurrentPointerSnapshot | str | None,
) -> Any:
    if previous_pointer is not None and not isinstance(
        previous_pointer,
        _CurrentPointerSnapshot,
    ):
        raise DailyOperationsError("current_pointer_unavailable")
    expected = previous_pointer.sha256 if previous_pointer is not None else None

    def publisher(root: Path, name: str, **kwargs: Any) -> Any:
        return _publish_prepublication_namespace_pointer(
            root,
            name,
            expected_current_pointer_sha256=expected,
            **kwargs,
        )

    return market_no_send.publish_market_no_send_generation(
        base,
        namespace,
        publisher=publisher,
    )


@dataclass(frozen=True)
class _DailyOperationsDependencies:
    environ: Mapping[str, str] = field(default_factory=lambda: os.environ)
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
    token_hex: Callable[[int], str] = secrets.token_hex
    readiness: Callable[..., MarketNoSendReadiness] = (
        market_no_send.build_market_no_send_readiness
    )
    run_generation: Callable[..., MarketNoSendGenerationResult] = (
        market_no_send.run_market_no_send_generation
    )
    record_attempt: Callable[[Path, str, MarketNoSendGenerationResult], Path] = (
        market_no_send_attempt.record_attempt
    )
    record_boundary_failure: Callable[..., Path] = market_no_send_attempt.record_boundary_failure
    write_audit: Callable[[Path, str, MarketNoSendGenerationResult], None] = _default_audit
    write_publication_receipt: Callable[[Path, str, str], Mapping[str, Any]] = (
        _default_publication_receipt
    )
    write_operations_receipt: Callable[
        [Path, str, str, daily_operations_service.DashboardOwnership],
        Mapping[str, Any],
    ] = _default_operations_receipt
    validate_final_publication: Callable[[Path, str], None] = (
        _default_validate_final_publication
    )
    refresh_campaign_report: Callable[[Path], None] = _default_refresh_campaign_report
    persist_current_status: Callable[[Path, DailyOperationsReadiness], None] = (
        _default_persist_current_status
    )
    generation_status: Callable[[Path, str], dict[str, Any]] = (
        market_no_send.market_no_send_generation_status
    )
    strict_doctor: Callable[[Path, str], None] = _default_strict_doctor
    publish: Callable[
        [Path, str, _CurrentPointerSnapshot | str | None], Any
    ] = _default_publish
    current_namespace: Callable[
        [Path], _CurrentPointerSnapshot | str | None
    ] = _default_current_namespace
    rollback: Callable[
        [Path, str, _CurrentPointerSnapshot | str], bool
    ] = _default_rollback
    invalidate_pointer: Callable[[Path, str], bool] = _default_invalidate_pointer
    resolve_calendar_snapshot: Callable[[str | Path], Path | None] = (
        official_macro_calendar.resolve_latest_official_macro_snapshot
    )
    campaign_cadence: Callable[..., dict[str, object]] = (
        market_no_send_campaign_guard.assess_campaign_reservation
    )
    inspect_dashboard: Callable[..., daily_operations_service.DashboardOwnership] = (
        daily_operations_service.inspect_dashboard_ownership
    )
    restart_dashboard: Callable[..., bool] = daily_operations_service.restart_owned_dashboard
    wait_dashboard_process: Callable[..., daily_operations_service.DashboardOwnership] = (
        daily_operations_service.wait_for_owned_dashboard_process
    )
    probe_dashboard: Callable[..., bool] = daily_operations_service.probe_owned_dashboard
    scheduler_health: Callable[..., daily_operations_service.SchedulerHealth] = (
        daily_operations_service.inspect_scheduler_health
    )


DailyOperationsDependencies = _DailyOperationsDependencies


def unique_namespace(now: datetime, token: str) -> str:
    observed = _as_utc(now)
    suffix = "".join(ch for ch in str(token).lower() if ch in "0123456789abcdef")[:12]
    if len(suffix) < 8:
        raise DailyOperationsError("namespace token is invalid")
    stamp = observed.strftime("%Y%m%dt%H%M%S%fZ").lower()
    return f"radar_market_no_send_{stamp}_{suffix}"


def build_daily_operations_readiness(
    *,
    artifact_base_dir: str | Path,
    artifact_namespace: str,
    top_n: int,
    fetch_limit: int | None,
    interval_seconds: int = daily_operations_service.DEFAULT_INTERVAL_SECONDS,
    dependencies: DailyOperationsDependencies | None = None,
) -> DailyOperationsReadiness:
    """Run every read-only gate used before an automatic provider attempt."""

    deps = dependencies or DailyOperationsDependencies()
    base = _read_only_base(artifact_base_dir)
    checked = _as_utc(deps.now())
    market = deps.readiness(
        artifact_base_dir=base,
        artifact_namespace=artifact_namespace,
        top_n=top_n,
        fetch_limit=fetch_limit,
        environ=deps.environ,
        fixture_dir=config.FIXTURE_DIR,
        now=checked,
    )
    dashboard = deps.inspect_dashboard(artifact_base=base)
    scheduler = deps.scheduler_health(
        artifact_base=base,
        top_n=top_n,
        fetch_limit=fetch_limit,
        interval_seconds=interval_seconds,
    )
    if not market.ready:
        status, reason = _blocked_readiness_status(market)
    elif not dashboard.owned:
        status, reason = "blocked", dashboard.reason
    else:
        status, reason = "ready", "eligible"
    return DailyOperationsReadiness(
        checked_at=checked.isoformat(),
        artifact_namespace=artifact_namespace,
        status=status,
        reason=reason,
        market=market,
        dashboard=dashboard,
        scheduler=scheduler,
    )


def run_daily_operations_cycle(
    *,
    artifact_base_dir: str | Path,
    top_n: int,
    fetch_limit: int | None,
    interval_seconds: int = daily_operations_service.DEFAULT_INTERVAL_SECONDS,
    dry_run: bool = False,
    dependencies: DailyOperationsDependencies | None = None,
) -> DailyOperationsCycleResult:
    """Run zero or one readiness-gated live/no-send observation."""

    deps = dependencies or DailyOperationsDependencies()
    checked = _as_utc(deps.now())
    cycle_id = deps.token_hex(16)
    namespace = unique_namespace(checked, deps.token_hex(8))
    base = _read_only_base(artifact_base_dir) if dry_run else market_no_send._validated_artifact_base(artifact_base_dir)
    if dry_run:
        readiness = build_daily_operations_readiness(
            artifact_base_dir=base,
            artifact_namespace=namespace,
            top_n=top_n,
            fetch_limit=fetch_limit,
            interval_seconds=interval_seconds,
            dependencies=deps,
        )
        return DailyOperationsCycleResult(
            cycle_id=cycle_id,
            artifact_namespace=namespace,
            status="dry_run",
            reason=readiness.reason,
            checked_at=readiness.checked_at,
            dry_run=True,
        )

    with _cycle_lock(base) as acquired:
        if not acquired:
            result = DailyOperationsCycleResult(
                cycle_id=cycle_id,
                artifact_namespace=namespace,
                status="skipped",
                reason="cycle_already_running",
                checked_at=checked.isoformat(),
            )
            _record_terminal(base, result, readiness=None, attempted_observation_at=None)
            deps.refresh_campaign_report(base)
            return result
        _append_cycle_row(
            base,
            _cycle_row(
                cycle_id=cycle_id,
                namespace=namespace,
                status="attempted",
                reason="readiness_pending",
                recorded_at=checked,
            ),
        )
        try:
            readiness = build_daily_operations_readiness(
                artifact_base_dir=base,
                artifact_namespace=namespace,
                top_n=top_n,
                fetch_limit=fetch_limit,
                interval_seconds=interval_seconds,
                dependencies=deps,
            )
        except Exception:  # noqa: BLE001 - never persist arbitrary exception text
            return _finish(
                base,
                DailyOperationsCycleResult(
                    cycle_id, namespace, "failed", "readiness_failed", checked.isoformat()
                ),
                readiness=None,
                dependencies=deps,
            )
        if not readiness.ready:
            return _finish(
                base,
                DailyOperationsCycleResult(
                    cycle_id,
                    namespace,
                    readiness.status,
                    readiness.reason,
                    readiness.checked_at,
                ),
                readiness=readiness,
                dependencies=deps,
            )
        return _execute_ready_cycle(
            base=base,
            namespace=namespace,
            cycle_id=cycle_id,
            readiness=readiness,
            top_n=top_n,
            fetch_limit=fetch_limit,
            dependencies=deps,
        )


def _execute_ready_cycle(
    *,
    base: Path,
    namespace: str,
    cycle_id: str,
    readiness: DailyOperationsReadiness,
    top_n: int,
    fetch_limit: int | None,
    dependencies: DailyOperationsDependencies,
) -> DailyOperationsCycleResult:
    try:
        previous_pointer = dependencies.current_namespace(base)
    except Exception:
        return _finish(
            base,
            DailyOperationsCycleResult(
                cycle_id,
                namespace,
                "failed",
                "current_pointer_unavailable",
                readiness.checked_at,
            ),
            readiness=readiness,
            dependencies=dependencies,
        )
    attempted_at = _as_utc(dependencies.now()).isoformat()
    try:
        generation_environ = _generation_environ(base, dependencies)
    except DailyOperationsError as exc:
        return _finish(
            base,
            DailyOperationsCycleResult(
                cycle_id,
                namespace,
                "blocked",
                str(exc),
                readiness.checked_at,
            ),
            readiness=readiness,
            dependencies=dependencies,
        )
    try:
        generation = dependencies.run_generation(
            artifact_base_dir=base,
            artifact_namespace=namespace,
            top_n=top_n,
            fetch_limit=fetch_limit,
            environ=generation_environ,
        )
        dependencies.record_attempt(base, namespace, generation)
    except Exception as exc:  # noqa: BLE001 - exact attempt receipt sanitizes
        try:
            dependencies.record_boundary_failure(
                base,
                namespace,
                failure=exc,
                manifest_filename=market_no_send.RUN_MANIFEST_FILENAME,
            )
        except Exception:
            pass
        attempted, request_succeeded = _attempt_receipt_flags(base, namespace)
        if attempted:
            readiness, _refreshed = _refresh_post_attempt_cadence(
                base=base,
                namespace=namespace,
                readiness=readiness,
                top_n=top_n,
                fetch_limit=fetch_limit,
                dependencies=dependencies,
            )
        return _finish(
            base,
            DailyOperationsCycleResult(
                cycle_id,
                namespace,
                "failed",
                "generation_failed",
                readiness.checked_at,
                provider_call_attempted=attempted,
                provider_request_succeeded=request_succeeded,
            ),
            readiness=readiness,
            attempted_observation_at=attempted_at,
            dependencies=dependencies,
        )
    if not generation.complete:
        if generation.provider_call_attempted:
            readiness, _refreshed = _refresh_post_attempt_cadence(
                base=base,
                namespace=namespace,
                readiness=readiness,
                top_n=top_n,
                fetch_limit=fetch_limit,
                dependencies=dependencies,
            )
        return _finish(
            base,
            DailyOperationsCycleResult(
                cycle_id,
                namespace,
                _incomplete_generation_status(generation),
                _generation_reason(generation),
                readiness.checked_at,
                provider_call_attempted=generation.provider_call_attempted,
                provider_request_succeeded=generation.provider_request_succeeded,
            ),
            readiness=readiness,
            attempted_observation_at=attempted_at,
            dependencies=dependencies,
        )
    cadence_refreshed = True
    if generation.provider_call_attempted:
        readiness, cadence_refreshed = _refresh_post_attempt_cadence(
            base=base,
            namespace=namespace,
            readiness=readiness,
            top_n=top_n,
            fetch_limit=fetch_limit,
            dependencies=dependencies,
        )
    if not cadence_refreshed:
        return _finish(
            base,
            DailyOperationsCycleResult(
                cycle_id,
                namespace,
                "failed",
                "post_attempt_cadence_refresh_failed",
                readiness.checked_at,
                provider_call_attempted=generation.provider_call_attempted,
                provider_request_succeeded=generation.provider_request_succeeded,
            ),
            readiness=readiness,
            attempted_observation_at=attempted_at,
            dependencies=dependencies,
        )
    return _publish_complete_generation(
        base=base,
        namespace=namespace,
        cycle_id=cycle_id,
        readiness=readiness,
        attempted_at=attempted_at,
        previous_pointer=previous_pointer,
        generation=generation,
        dependencies=dependencies,
    )


def _generation_environ(
    base: Path,
    dependencies: DailyOperationsDependencies,
) -> dict[str, str]:
    """Attach only a hash-attested official snapshot when none is explicit."""

    environment = dict(dependencies.environ)
    configured = str(
        environment.get(market_no_send_calendar.CALENDAR_SNAPSHOT_PATH_ENV) or ""
    ).strip()
    if configured:
        return environment
    try:
        snapshot = dependencies.resolve_calendar_snapshot(
            base / official_macro_calendar.DEFAULT_OFFICIAL_MACRO_BASE.name
        )
    except official_macro_calendar.OfficialMacroAcquisitionError as exc:
        raise DailyOperationsError("calendar_snapshot_attestation_failed") from exc
    if snapshot is not None:
        environment[market_no_send_calendar.CALENDAR_SNAPSHOT_PATH_ENV] = str(snapshot)
    return environment


def _refresh_post_attempt_cadence(
    *,
    base: Path,
    namespace: str,
    readiness: DailyOperationsReadiness,
    top_n: int,
    fetch_limit: int | None,
    dependencies: DailyOperationsDependencies,
) -> tuple[DailyOperationsReadiness, bool]:
    """Re-read local cadence receipts after a call without calling a provider."""

    checked = _as_utc(dependencies.now())
    try:
        market = dependencies.readiness(
            artifact_base_dir=base,
            artifact_namespace=f"{namespace}_post_attempt",
            top_n=top_n,
            fetch_limit=fetch_limit,
            environ=dependencies.environ,
            fixture_dir=config.FIXTURE_DIR,
            now=checked,
        )
        reservation = dependencies.campaign_cadence(base, checked_at=checked)
        effective = _latest_timestamp(
            market.next_eligible_observation_at,
            reservation.get("next_provider_call_at"),
        )
        if effective is None:
            raise DailyOperationsError("post-attempt cadence receipt is missing")
        next_time = _parse_timestamp(effective)
        market = replace(
            market,
            next_eligible_observation_at=effective,
            cadence_status="waiting" if next_time > checked else market.cadence_status,
        )
        return (
            replace(readiness, checked_at=checked.isoformat(), market=market),
            True,
        )
    except Exception:
        unavailable = replace(
            readiness.market,
            next_eligible_observation_at=None,
            cadence_status="unknown",
        )
        return (
            replace(readiness, checked_at=checked.isoformat(), market=unavailable),
            False,
        )


def _publish_complete_generation(
    *,
    base: Path,
    namespace: str,
    cycle_id: str,
    readiness: DailyOperationsReadiness,
    attempted_at: str,
    previous_pointer: _CurrentPointerSnapshot | str | None,
    generation: MarketNoSendGenerationResult,
    dependencies: DailyOperationsDependencies,
) -> DailyOperationsCycleResult:
    common = {
        "provider_call_attempted": generation.provider_call_attempted,
        "provider_request_succeeded": generation.provider_request_succeeded,
    }
    try:
        dependencies.write_audit(base, namespace, generation)
        status = dependencies.generation_status(base, namespace)
        if status.get("complete") is not True:
            raise DailyOperationsError("generation_incomplete")
        dependencies.strict_doctor(base, namespace)
    except Exception as exc:  # noqa: BLE001 - stage-coded, never payload text
        reason = str(exc) if isinstance(exc, DailyOperationsError) else "prepublication_failed"
        result = DailyOperationsCycleResult(
            cycle_id,
            namespace,
            "failed",
            reason,
            readiness.checked_at,
            **common,
        )
        return _finish(
            base,
            result,
            readiness=readiness,
            attempted_observation_at=attempted_at,
            dependencies=dependencies,
        )
    try:
        dependencies.publish(base, namespace, previous_pointer)
    except Exception:
        return _finish_contained_failure(
            base,
            namespace=namespace,
            cycle_id=cycle_id,
            reason="publication_failed",
            readiness=readiness,
            attempted_at=attempted_at,
            previous_pointer=previous_pointer,
            common=common,
            dependencies=dependencies,
        )
    try:
        dependencies.write_publication_receipt(base, namespace, cycle_id)
    except Exception:
        return _finish_contained_failure(
            base,
            namespace=namespace,
            cycle_id=cycle_id,
            reason="publication_receipt_failed",
            readiness=readiness,
            attempted_at=attempted_at,
            previous_pointer=previous_pointer,
            common=common,
            dependencies=dependencies,
        )
    try:
        dashboard_restarted = dependencies.restart_dashboard(artifact_base=base)
    except Exception:  # noqa: BLE001 - fail closed without exposing command output
        dashboard_restarted = False
    try:
        dashboard = (
            dependencies.wait_dashboard_process(artifact_base=base)
            if dashboard_restarted
            else None
        )
    except Exception:  # noqa: BLE001 - ownership failure is stage-coded below
        dashboard = None
    if not (
        dashboard_restarted and dashboard is not None and dashboard.owned and dashboard.running
    ):
        return _finish_contained_failure(
            base,
            namespace=namespace,
            cycle_id=cycle_id,
            reason="dashboard_restart_failed",
            readiness=readiness,
            attempted_at=attempted_at,
            previous_pointer=previous_pointer,
            common=common,
            dependencies=dependencies,
        )
    return _finalize_published_generation(
        base=base,
        namespace=namespace,
        cycle_id=cycle_id,
        readiness=readiness,
        attempted_at=attempted_at,
        previous_pointer=previous_pointer,
        generation_run_id=generation.run_id,
        dashboard=dashboard,
        common=common,
        dependencies=dependencies,
    )


def _finalize_published_generation(
    *,
    base: Path,
    namespace: str,
    cycle_id: str,
    readiness: DailyOperationsReadiness,
    attempted_at: str,
    previous_pointer: _CurrentPointerSnapshot | str | None,
    generation_run_id: object,
    dashboard: daily_operations_service.DashboardOwnership,
    common: Mapping[str, Any],
    dependencies: DailyOperationsDependencies,
) -> DailyOperationsCycleResult:
    """Close terminal state, operations evidence, and the exact HTTP probe."""

    result = DailyOperationsCycleResult(
        cycle_id,
        namespace,
        "succeeded",
        "published_and_restarted",
        readiness.checked_at,
        pointer_published=True,
        dashboard_restarted=True,
        **common,
    )
    stage = "postpublication_state_failed"
    try:
        _record_terminal(
            base,
            result,
            readiness=readiness,
            attempted_observation_at=attempted_at,
        )
        dependencies.persist_current_status(base, readiness)
        stage = "operations_receipt_failed"
        operations_receipt = dependencies.write_operations_receipt(
            base,
            namespace,
            cycle_id,
            dashboard,
        )
        probe_identity = _operations_receipt_probe_identity(
            operations_receipt,
            namespace=namespace,
            cycle_id=cycle_id,
            generation_run_id=generation_run_id,
        )
        stage = "final_publication_contract_failed"
        dependencies.validate_final_publication(base, namespace)
        stage = "dashboard_postreceipt_probe_failed"
        if not dependencies.probe_dashboard(
            artifact_base=base,
            **probe_identity,
        ):
            raise DailyOperationsError(stage)
        stage = "campaign_report_refresh_failed"
        dependencies.refresh_campaign_report(base)
        return result
    except Exception as exc:
        rolled_back, invalidated = _contain_failed_authority(
            base=base,
            failed_namespace=namespace,
            previous_pointer=previous_pointer,
            dependencies=dependencies,
        )
        if not rolled_back and not invalidated:
            raise DailyOperationsError("authority_containment_failed") from exc
        failed = DailyOperationsCycleResult(
            cycle_id,
            namespace,
            "failed",
            stage,
            readiness.checked_at,
            pointer_rolled_back=rolled_back,
            pointer_invalidated=invalidated,
            **common,
        )
        try:
            return _finish(
                base,
                failed,
                readiness=readiness,
                attempted_observation_at=attempted_at,
                dependencies=dependencies,
            )
        except Exception as terminal_exc:
            raise DailyOperationsError(stage) from terminal_exc


def _operations_receipt_probe_identity(
    receipt: Mapping[str, Any],
    *,
    namespace: str,
    cycle_id: str,
    generation_run_id: object,
) -> dict[str, object]:
    """Extract one exact, closed dashboard identity or fail the receipt stage."""

    run_id = receipt.get("run_id")
    revision = receipt.get("revision")
    digest = receipt.get("operator_state_sha256")
    if (
        receipt.get("status") != "dashboard_restarted"
        or receipt.get("artifact_namespace") != namespace
        or receipt.get("cycle_id") != cycle_id
        or not isinstance(generation_run_id, str)
        or not generation_run_id
        or run_id != generation_run_id
        or not isinstance(run_id, str)
        or not run_id
        or len(run_id) > 512
        or not all(32 <= ord(character) < 127 for character in run_id)
        or not isinstance(revision, int)
        or isinstance(revision, bool)
        or revision < 1
        or not isinstance(digest, str)
        or len(digest) != 64
        or not all(character in "0123456789abcdef" for character in digest)
    ):
        raise DailyOperationsError("operations_receipt_failed")
    return {
        "expected_namespace": namespace,
        "expected_run_id": run_id,
        "expected_revision": revision,
        "expected_operator_state_sha256": digest,
    }


def _finish_contained_failure(
    base: Path,
    *,
    namespace: str,
    cycle_id: str,
    reason: str,
    readiness: DailyOperationsReadiness,
    attempted_at: str,
    previous_pointer: _CurrentPointerSnapshot | str | None,
    common: Mapping[str, bool],
    dependencies: DailyOperationsDependencies,
) -> DailyOperationsCycleResult:
    rolled_back, invalidated = _contain_failed_authority(
        base=base,
        failed_namespace=namespace,
        previous_pointer=previous_pointer,
        dependencies=dependencies,
    )
    if not rolled_back and not invalidated:
        raise DailyOperationsError("authority_containment_failed")
    result = DailyOperationsCycleResult(
        cycle_id,
        namespace,
        "failed",
        reason,
        readiness.checked_at,
        pointer_rolled_back=rolled_back,
        pointer_invalidated=invalidated,
        **common,
    )
    return _finish(
        base,
        result,
        readiness=readiness,
        attempted_observation_at=attempted_at,
        dependencies=dependencies,
    )


def _contain_failed_authority(
    *,
    base: Path,
    failed_namespace: str,
    previous_pointer: _CurrentPointerSnapshot | str | None,
    dependencies: DailyOperationsDependencies,
) -> tuple[bool, bool]:
    try:
        rolled_back = bool(
            previous_pointer is not None
            and dependencies.rollback(base, failed_namespace, previous_pointer)
        )
    except Exception:
        rolled_back = False
    if rolled_back:
        try:
            dependencies.restart_dashboard(artifact_base=base)
        except Exception:  # noqa: BLE001 - the pointer is already contained
            pass
        return True, False
    try:
        invalidated = dependencies.invalidate_pointer(base, failed_namespace)
    except Exception:
        invalidated = False
    return False, invalidated


def daily_operations_status(
    *,
    artifact_base_dir: str | Path,
    top_n: int,
    fetch_limit: int | None,
    interval_seconds: int = daily_operations_service.DEFAULT_INTERVAL_SECONDS,
    dependencies: DailyOperationsDependencies | None = None,
) -> dict[str, object]:
    """Read scheduler and bounded cycle state without writes or provider calls."""

    deps = dependencies or DailyOperationsDependencies()
    base = _read_only_base(artifact_base_dir)
    state = _read_state(base)
    rows = read_jsonl(base / CYCLE_LEDGER_FILENAME)
    scheduler = deps.scheduler_health(
        artifact_base=base,
        top_n=top_n,
        fetch_limit=fetch_limit,
        interval_seconds=interval_seconds,
    )
    return {
        "contract_version": CONTRACT_VERSION,
        "scheduler": scheduler.to_dict(),
        "service": _read_service_state(base),
        "state": state,
        "recent_cycles": rows[-50:],
        "cycle_rows_retained": len(rows),
        "live_provider_authorized": _truthy(
            deps.environ.get(market_no_send.LIVE_AUTH_ENV)
        ),
        **SAFETY_COUNTERS,
        "no_send": True,
        "research_only": True,
    }


def _finish(
    base: Path,
    result: DailyOperationsCycleResult,
    *,
    readiness: DailyOperationsReadiness | None,
    attempted_observation_at: str | None = None,
    dependencies: DailyOperationsDependencies,
) -> DailyOperationsCycleResult:
    _record_terminal(
        base,
        result,
        readiness=readiness,
        attempted_observation_at=attempted_observation_at,
    )
    if readiness is not None:
        dependencies.persist_current_status(base, readiness)
    dependencies.refresh_campaign_report(base)
    return result


def _record_terminal(
    base: Path,
    result: DailyOperationsCycleResult,
    *,
    readiness: DailyOperationsReadiness | None,
    attempted_observation_at: str | None,
) -> None:
    if result.status not in _TERMINAL_STATUSES:
        raise DailyOperationsError("invalid terminal daily operations status")
    now = datetime.now(timezone.utc)
    _append_cycle_row(
        base,
        _cycle_row(
            cycle_id=result.cycle_id,
            namespace=result.artifact_namespace,
            status=result.status,
            reason=result.reason,
            recorded_at=now,
            provider_call_attempted=result.provider_call_attempted,
            provider_request_succeeded=result.provider_request_succeeded,
            pointer_published=result.pointer_published,
            dashboard_restarted=result.dashboard_restarted,
            pointer_rolled_back=result.pointer_rolled_back,
            pointer_invalidated=result.pointer_invalidated,
        ),
    )
    previous = _read_state(base)
    succeeded = result.status == "succeeded"
    state = {
        "contract_version": CONTRACT_VERSION,
        "row_type": "decision_radar_daily_operations_state",
        "updated_at": now.isoformat(),
        "last_cycle_id": result.cycle_id,
        "last_cycle_status": result.status,
        "last_cycle_reason": result.reason,
        "last_cycle_namespace": result.artifact_namespace,
        "last_readiness_check": (
            readiness.checked_at if readiness is not None else result.checked_at
        ),
        "last_attempted_observation": (
            (attempted_observation_at if result.provider_call_attempted else None)
            or previous.get("last_attempted_observation")
        ),
        "last_successful_publication": (
            now.isoformat()
            if succeeded
            else previous.get("last_successful_publication")
        ),
        "last_successful_namespace": (
            result.artifact_namespace
            if succeeded
            else previous.get("last_successful_namespace")
        ),
        "next_eligible_observation_at": (
            readiness.market.next_eligible_observation_at
            if readiness is not None
            else previous.get("next_eligible_observation_at")
        ),
        "live_provider_authorized": (
            readiness.market.live_provider_authorized
            if readiness is not None
            else previous.get("live_provider_authorized", False)
        ),
        "authorization_at_last_cycle": (
            readiness.market.live_provider_authorized
            if readiness is not None
            else previous.get(
                "authorization_at_last_cycle",
                previous.get("live_provider_authorized"),
            )
        ),
        "authorization_checked_at_last_cycle": (
            readiness.checked_at
            if readiness is not None
            else previous.get("authorization_checked_at_last_cycle")
        ),
        "provider_call_attempted": result.provider_call_attempted,
        "pointer_published": result.pointer_published,
        "dashboard_restarted": result.dashboard_restarted,
        "pointer_invalidated": result.pointer_invalidated,
        "scheduler_enabled": (
            readiness.scheduler.enabled
            if readiness is not None
            else previous.get("scheduler_enabled", False)
        ),
        "scheduler_loaded": (
            readiness.scheduler.loaded
            if readiness is not None
            else previous.get("scheduler_loaded", False)
        ),
        "scheduler_healthy": (
            readiness.scheduler.healthy
            if readiness is not None
            else previous.get("scheduler_healthy", False)
        ),
        "scheduler_reason": (
            readiness.scheduler.reason
            if readiness is not None
            else previous.get("scheduler_reason", "not_observed")
        ),
        "scheduler_last_exit_code": (
            readiness.scheduler.last_exit_code
            if readiness is not None
            else previous.get("scheduler_last_exit_code")
        ),
        "scheduler_runs": (
            readiness.scheduler.runs
            if readiness is not None
            else previous.get("scheduler_runs")
        ),
        **SAFETY_COUNTERS,
        "no_send": True,
        "research_only": True,
    }
    write_json_atomic(base / STATE_FILENAME, state)


def _cycle_row(
    *,
    cycle_id: str,
    namespace: str,
    status: str,
    reason: str,
    recorded_at: datetime,
    provider_call_attempted: bool = False,
    provider_request_succeeded: bool = False,
    pointer_published: bool = False,
    dashboard_restarted: bool = False,
    pointer_rolled_back: bool = False,
    pointer_invalidated: bool = False,
) -> dict[str, object]:
    return {
        "contract_version": CONTRACT_VERSION,
        "row_type": "decision_radar_daily_operations_cycle",
        "cycle_id": _safe_identity(cycle_id),
        "recorded_at": _as_utc(recorded_at).isoformat(),
        "artifact_namespace": _safe_identity(namespace),
        "status": status,
        "reason": _safe_reason(reason),
        "provider_call_attempted": provider_call_attempted is True,
        "provider_request_succeeded": provider_request_succeeded is True,
        "pointer_published": pointer_published is True,
        "dashboard_restarted": dashboard_restarted is True,
        "pointer_rolled_back": pointer_rolled_back is True,
        "pointer_invalidated": pointer_invalidated is True,
        **SAFETY_COUNTERS,
        "no_send": True,
        "research_only": True,
    }


def _append_cycle_row(base: Path, row: Mapping[str, object]) -> None:
    with _journal_lock(base):
        rows = read_jsonl(base / CYCLE_LEDGER_FILENAME)
        retained = [*rows, dict(row)][-CYCLE_LEDGER_MAX_ROWS:]
        write_jsonl(base / CYCLE_LEDGER_FILENAME, retained)


def _read_state(base: Path) -> dict[str, Any]:
    try:
        return read_json_object(base / STATE_FILENAME)
    except Exception:
        return {}


def _read_service_state(base: Path) -> dict[str, Any]:
    try:
        return read_json_object(base / daily_operations_service.SERVICE_STATE_FILENAME)
    except Exception:
        return {
            "contract_version": 1,
            "row_type": "decision_radar_daily_operations_service",
            "prepared": True,
            "enabled": False,
            "installed": False,
            "loaded": False,
            "running": False,
            "healthy": True,
            "reason": "not_installed",
            "scheduler_reason": "service_not_installed",
            "scheduler_label": daily_operations_service.SERVICE_LABEL,
            "no_send": True,
            "research_only": True,
        }


def _attempt_receipt_flags(base: Path, namespace: str) -> tuple[bool, bool]:
    receipt: Mapping[str, Any] = {}
    try:
        candidate = read_json_object(base / market_no_send_attempt.LATEST_ATTEMPT_FILENAME)
        if candidate.get("artifact_namespace") == namespace:
            receipt = candidate
    except Exception:
        receipt = {}
    attempted = receipt.get("provider_call_attempted") is True
    if not attempted:
        attempted = market_no_send_campaign_guard.provider_call_may_have_been_reserved(
            base,
            artifact_namespace=namespace,
        )
    return attempted, receipt.get("provider_request_succeeded") is True


@contextmanager
def _cycle_lock(base: Path) -> Iterator[bool]:
    with _root_lock(base, _CYCLE_LOCK_FILENAME, nonblocking=True) as locked:
        yield locked


@contextmanager
def _journal_lock(base: Path) -> Iterator[bool]:
    with _root_lock(base, _JOURNAL_LOCK_FILENAME, nonblocking=False) as locked:
        yield locked


@contextmanager
def _root_lock(base: Path, filename: str, *, nonblocking: bool) -> Iterator[bool]:
    descriptor: int | None = None
    locked = False
    try:
        with _open_verified_namespace_dir(base) as anchored:
            _base_fd, namespace_fd, _namespace, _identity = anchored
            flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
            descriptor = os.open(filename, flags, 0o600, dir_fd=namespace_fd)
            opened = os.fstat(descriptor)
            current = os.stat(filename, dir_fd=namespace_fd, follow_symlinks=False)
            if not stat.S_ISREG(opened.st_mode) or (
                opened.st_dev,
                opened.st_ino,
            ) != (current.st_dev, current.st_ino):
                raise DailyOperationsError("daily operations lock identity changed")
            operation = fcntl.LOCK_EX | (fcntl.LOCK_NB if nonblocking else 0)
            try:
                fcntl.flock(descriptor, operation)
            except BlockingIOError:
                yield False
                return
            locked = True
            yield True
    finally:
        if descriptor is not None:
            if locked:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)


def _blocked_readiness_status(readiness: MarketNoSendReadiness) -> tuple[str, str]:
    if readiness.cadence_status == "waiting":
        return "skipped", "observation_cadence_waiting"
    combined = " ".join(readiness.reasons).casefold()
    if "backoff" in combined:
        return "skipped", "provider_backoff_active"
    if "reservation" in combined or "already running" in combined:
        return "skipped", "campaign_reservation_busy"
    if not readiness.live_provider_authorized:
        return "blocked", "provider_authorization_missing"
    if readiness.fixture_mode:
        return "blocked", "fixture_mode_enabled"
    return "blocked", "market_readiness_blocked"


def _incomplete_generation_status(result: MarketNoSendGenerationResult) -> str:
    if result.status == "blocked" and result.provider_call_attempted is not True:
        return "skipped"
    return "failed"


def _generation_reason(result: MarketNoSendGenerationResult) -> str:
    failure = str(result.failure_class or "").casefold()
    if failure in {"campaign_reservation_busy", "locked_readiness_blocked"}:
        return failure
    if result.provider_call_attempted and not result.provider_request_succeeded:
        return "provider_request_failed"
    return "generation_incomplete"


def _read_only_base(value: str | Path) -> Path:
    raw = Path(value).expanduser().absolute()
    try:
        info = raw.lstat()
    except OSError as exc:
        raise DailyOperationsError("artifact base is unavailable") from exc
    if not stat.S_ISDIR(info.st_mode):
        raise DailyOperationsError("artifact base is not a directory")
    return raw.resolve()


def _safe_identity(value: object) -> str:
    clean = str(value or "").strip()
    if not clean or len(clean) > 160 or not all(
        character.isalnum() or character in "_.-" for character in clean
    ):
        raise DailyOperationsError("daily operations identity is invalid")
    return clean


def _safe_reason(value: object) -> str:
    clean = str(value or "unknown").strip().casefold().replace(" ", "_")
    if not clean or len(clean) > 80 or not all(
        character.isalnum() or character in "_.-" for character in clean
    ):
        return "operation_failed"
    return clean


def _latest_timestamp(*values: object) -> str | None:
    parsed: list[datetime] = []
    for value in values:
        if value in (None, ""):
            continue
        try:
            parsed.append(_parse_timestamp(value))
        except DailyOperationsError:
            continue
    return max(parsed).isoformat() if parsed else None


def _parse_timestamp(value: object) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise DailyOperationsError("daily operations timestamp is invalid") from exc
    return _as_utc(parsed)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise DailyOperationsError("daily operations clock must be timezone-aware")
    return value.astimezone(timezone.utc)


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on"}


def _parser() -> Any:
    """Return the CLI parser while keeping the historical private hook."""
    from .daily_operations_cli import build_parser

    return build_parser()


def main(
    argv: Sequence[str] | None = None,
    *,
    dependencies: DailyOperationsDependencies | None = None,
    service_dependencies: daily_operations_service.ServiceDependencies | None = None,
) -> int:
    from .daily_operations_cli import run_cli

    return run_cli(
        argv,
        dependencies=dependencies,
        service_dependencies=service_dependencies,
    )


if __name__ == "__main__":  # pragma: no cover - exercised through module CLI
    raise SystemExit(main())


__all__ = (
    "CYCLE_LEDGER_FILENAME",
    "DailyOperationsCycleResult",
    "DailyOperationsDependencies",
    "DailyOperationsError",
    "DailyOperationsReadiness",
    "STATE_FILENAME",
    "build_daily_operations_readiness",
    "daily_operations_status",
    "main",
    "run_daily_operations_cycle",
    "unique_namespace",
)
