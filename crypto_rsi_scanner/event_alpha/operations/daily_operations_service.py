"""Confirmation-gated launchd service and owned-dashboard boundaries."""

from __future__ import annotations

import json
import http.client
import os
import plistlib
import secrets
import stat
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping

from .market_no_send_io import write_json_atomic


SERVICE_LABEL = "com.nasrenkaraf.crypto-radar-daily-operations"
DASHBOARD_LABEL = "com.nasrenkaraf.crypto-radar-dashboard"
SERVICE_MODULE = "crypto_rsi_scanner.event_alpha.operations.daily_operations"
DASHBOARD_MODULE = "crypto_rsi_scanner.event_alpha.dashboard"
DEFAULT_INTERVAL_SECONDS = 300
DEFAULT_DASHBOARD_HOST = "127.0.0.1"
DEFAULT_DASHBOARD_PORT = 8765
SERVICE_STATE_FILENAME = "event_radar_daily_operations_service.json"
_DASHBOARD_BODY_MARKER = b"Crypto Decision Radar"
_DASHBOARD_PROBE_BYTES = 16 * 1024


@dataclass(frozen=True)
class _CommandResult:
    returncode: int
    output: str = ""


CommandResult = _CommandResult


@dataclass(frozen=True)
class _DashboardOwnership:
    owned: bool
    loaded: bool
    running: bool
    reason: str
    pid: int | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


DashboardOwnership = _DashboardOwnership


@dataclass(frozen=True)
class _SchedulerHealth:
    enabled: bool
    installed: bool
    loaded: bool
    running: bool
    healthy: bool
    reason: str
    label: str = SERVICE_LABEL
    plist_path: str | None = None
    pid: int | None = None
    last_exit_code: int | None = None
    runs: int | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


SchedulerHealth = _SchedulerHealth


@dataclass(frozen=True)
class _ServiceOperation:
    ok: bool
    changed: bool
    reason: str
    health: SchedulerHealth

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["health"] = self.health.to_dict()
        return payload


ServiceOperation = _ServiceOperation


def _run_command(argv: tuple[str, ...]) -> CommandResult:
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=15.0,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001 - sanitized at this boundary
        return CommandResult(1, type(exc).__name__)
    output = ((completed.stdout or "") + (completed.stderr or "")).strip()
    return CommandResult(completed.returncode, output)


def _http_dashboard_ready(
    host: str,
    port: int,
    timeout: float,
    *,
    expected_namespace: str,
    expected_run_id: str,
    expected_revision: int,
    expected_operator_state_sha256: str,
) -> bool:
    if not _valid_dashboard_probe_identity(
        expected_namespace=expected_namespace,
        expected_run_id=expected_run_id,
        expected_revision=expected_revision,
        expected_operator_state_sha256=expected_operator_state_sha256,
    ):
        return False
    connection = http.client.HTTPConnection(host, int(port), timeout=timeout)
    try:
        connection.request(
            "GET",
            "/",
            headers={"User-Agent": "crypto-radar-daily-operations/1"},
        )
        response = connection.getresponse()
        body = response.read(_DASHBOARD_PROBE_BYTES)
        cache_directives = {
            directive.strip().casefold()
            for directive in (response.getheader("Cache-Control") or "").split(",")
            if directive.strip()
        }
        return bool(
            response.status == 200
            and "no-store" in cache_directives
            and response.getheader("X-Content-Type-Options") == "nosniff"
            and response.getheader("X-Crypto-Radar-Namespace")
            == expected_namespace
            and response.getheader("X-Crypto-Radar-Run-Id") == expected_run_id
            and response.getheader("X-Crypto-Radar-Revision")
            == str(expected_revision)
            and response.getheader("X-Crypto-Radar-Operator-State-SHA256")
            == expected_operator_state_sha256
            and _DASHBOARD_BODY_MARKER in body
        )
    finally:
        connection.close()


@dataclass(frozen=True)
class _ServiceDependencies:
    run: Callable[[tuple[str, ...]], CommandResult] = _run_command
    http_dashboard_ready: Callable[..., bool] = _http_dashboard_ready
    sleep: Callable[[float], None] = time.sleep
    uid: int = field(default_factory=os.getuid)
    home: Path = field(default_factory=Path.home)


ServiceDependencies = _ServiceDependencies


def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_python_path() -> Path:
    project_python = repository_root() / ".venv" / "bin" / "python"
    if project_python.is_file():
        return project_python.absolute()
    return Path(sys.executable).expanduser().absolute()


def default_artifact_base() -> Path:
    from ... import config

    return Path(config.EVENT_ALPHA_ARTIFACT_BASE_DIR).expanduser().resolve()


def expected_dashboard_argv(
    *,
    repo_root: Path,
    python_path: Path,
    artifact_base: Path,
    host: str = DEFAULT_DASHBOARD_HOST,
    port: int = DEFAULT_DASHBOARD_PORT,
) -> tuple[str, ...]:
    """Return the only dashboard argv Daily Operations may restart."""

    return (
        "/usr/bin/env",
        f"PYTHONPATH={repo_root}",
        str(python_path),
        "-u",
        "-m",
        DASHBOARD_MODULE,
        "--artifact-base",
        str(artifact_base),
        "--host",
        host,
        "--port",
        str(int(port)),
    )


def expected_service_argv(
    *,
    python_path: Path,
    artifact_base: Path,
    top_n: int,
    fetch_limit: int | None,
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
) -> tuple[str, ...]:
    argv = [
        str(python_path),
        "-u",
        "-m",
        SERVICE_MODULE,
        "cycle",
        "--artifact-base",
        str(artifact_base),
        "--top-n",
        str(int(top_n)),
        "--interval-seconds",
        str(int(interval_seconds)),
    ]
    if fetch_limit is not None:
        argv.extend(("--fetch-limit", str(int(fetch_limit))))
    return tuple(argv)


def inspect_dashboard_ownership(
    *,
    artifact_base: str | Path,
    repo_root_path: str | Path | None = None,
    python_path: str | Path | None = None,
    host: str = DEFAULT_DASHBOARD_HOST,
    port: int = DEFAULT_DASHBOARD_PORT,
    dependencies: ServiceDependencies | None = None,
) -> DashboardOwnership:
    deps = dependencies or ServiceDependencies()
    repo = Path(repo_root_path or repository_root()).expanduser().resolve()
    python = Path(python_path or default_python_path()).expanduser().absolute()
    base = Path(artifact_base).expanduser().resolve()
    service = f"gui/{deps.uid}/{DASHBOARD_LABEL}"
    result = deps.run(("launchctl", "print", service))
    if result.returncode != 0:
        return DashboardOwnership(False, False, False, "dashboard_not_loaded")
    argv = _launchctl_arguments(result.output)
    expected = expected_dashboard_argv(
        repo_root=repo,
        python_path=python,
        artifact_base=base,
        host=host,
        port=port,
    )
    if argv != expected:
        return DashboardOwnership(False, True, False, "dashboard_argv_mismatch")
    state = _launchctl_field(result.output, "state")
    pid = _launchctl_int_field(result.output, "pid")
    running = state == "running" and pid is not None
    return DashboardOwnership(
        owned=running,
        loaded=True,
        running=running,
        reason="owned_running" if running else "dashboard_not_running",
        pid=pid,
    )


def restart_owned_dashboard(
    *,
    artifact_base: str | Path,
    repo_root_path: str | Path | None = None,
    python_path: str | Path | None = None,
    host: str = DEFAULT_DASHBOARD_HOST,
    port: int = DEFAULT_DASHBOARD_PORT,
    dependencies: ServiceDependencies | None = None,
) -> bool:
    deps = dependencies or ServiceDependencies()
    ownership = inspect_dashboard_ownership(
        artifact_base=artifact_base,
        repo_root_path=repo_root_path,
        python_path=python_path,
        host=host,
        port=port,
        dependencies=deps,
    )
    if not ownership.owned:
        return False
    service = f"gui/{deps.uid}/{DASHBOARD_LABEL}"
    result = deps.run(("launchctl", "kickstart", "-k", service))
    return result.returncode == 0


def probe_owned_dashboard(
    *,
    artifact_base: str | Path,
    repo_root_path: str | Path | None = None,
    python_path: str | Path | None = None,
    host: str = DEFAULT_DASHBOARD_HOST,
    port: int = DEFAULT_DASHBOARD_PORT,
    expected_namespace: str,
    expected_run_id: str,
    expected_revision: int,
    expected_operator_state_sha256: str,
    attempts: int = 50,
    delay_seconds: float = 0.1,
    dependencies: ServiceDependencies | None = None,
) -> bool:
    """Prove the exact owned process serves trusted content after final receipt."""

    deps = dependencies or ServiceDependencies()
    if not _valid_dashboard_probe_identity(
        expected_namespace=expected_namespace,
        expected_run_id=expected_run_id,
        expected_revision=expected_revision,
        expected_operator_state_sha256=expected_operator_state_sha256,
    ):
        return False
    bounded_attempts = min(max(int(attempts), 1), 150)
    for attempt in range(bounded_attempts):
        try:
            before = inspect_dashboard_ownership(
                artifact_base=artifact_base,
                repo_root_path=repo_root_path,
                python_path=python_path,
                host=host,
                port=port,
                dependencies=deps,
            )
            before_pid = before.pid
            if (
                before.owned
                and before.running
                and isinstance(before_pid, int)
                and not isinstance(before_pid, bool)
                and before_pid > 0
                and deps.http_dashboard_ready(
                    host,
                    int(port),
                    0.5,
                    expected_namespace=expected_namespace,
                    expected_run_id=expected_run_id,
                    expected_revision=expected_revision,
                    expected_operator_state_sha256=expected_operator_state_sha256,
                )
            ):
                after = inspect_dashboard_ownership(
                    artifact_base=artifact_base,
                    repo_root_path=repo_root_path,
                    python_path=python_path,
                    host=host,
                    port=port,
                    dependencies=deps,
                )
                if (
                    after.owned
                    and after.running
                    and after.pid == before_pid
                ):
                    return True
        except Exception:
            pass
        if attempt + 1 < bounded_attempts:
            try:
                deps.sleep(max(0.0, min(float(delay_seconds), 1.0)))
            except Exception:
                return False
    return False


def _valid_dashboard_probe_identity(
    *,
    expected_namespace: object,
    expected_run_id: object,
    expected_revision: object,
    expected_operator_state_sha256: object,
) -> bool:
    """Validate the closed, header-safe authority identity before probing."""

    def safe_text(value: object) -> bool:
        return bool(
            isinstance(value, str)
            and value
            and len(value) <= 512
            and all(32 <= ord(character) < 127 for character in value)
        )

    return bool(
        safe_text(expected_namespace)
        and safe_text(expected_run_id)
        and isinstance(expected_revision, int)
        and not isinstance(expected_revision, bool)
        and expected_revision >= 1
        and isinstance(expected_operator_state_sha256, str)
        and len(expected_operator_state_sha256) == 64
        and all(
            character in "0123456789abcdef"
            for character in expected_operator_state_sha256
        )
    )


def wait_for_owned_dashboard_process(
    *,
    artifact_base: str | Path,
    repo_root_path: str | Path | None = None,
    python_path: str | Path | None = None,
    host: str = DEFAULT_DASHBOARD_HOST,
    port: int = DEFAULT_DASHBOARD_PORT,
    attempts: int = 50,
    delay_seconds: float = 0.1,
    dependencies: ServiceDependencies | None = None,
) -> DashboardOwnership:
    """Wait briefly for kickstart to expose the exact owned running process."""

    deps = dependencies or ServiceDependencies()
    ownership = DashboardOwnership(False, False, False, "dashboard_not_loaded")
    bounded_attempts = min(max(int(attempts), 1), 150)
    for attempt in range(bounded_attempts):
        ownership = inspect_dashboard_ownership(
            artifact_base=artifact_base,
            repo_root_path=repo_root_path,
            python_path=python_path,
            host=host,
            port=port,
            dependencies=deps,
        )
        if ownership.owned:
            return ownership
        if attempt + 1 < bounded_attempts:
            try:
                deps.sleep(max(0.0, min(float(delay_seconds), 1.0)))
            except Exception:
                break
    return ownership


def service_plist(
    *,
    repo_root_path: Path,
    python_path: Path,
    artifact_base: Path,
    log_path: Path,
    top_n: int,
    fetch_limit: int | None,
    interval_seconds: int,
) -> dict[str, object]:
    interval = int(interval_seconds)
    if interval < 60:
        raise ValueError("daily operations interval must be at least 60 seconds")
    return {
        "Label": SERVICE_LABEL,
        "ProgramArguments": list(
            expected_service_argv(
                python_path=python_path,
                artifact_base=artifact_base,
                top_n=top_n,
                fetch_limit=fetch_limit,
                interval_seconds=interval,
            )
        ),
        "WorkingDirectory": str(repo_root_path),
        "StandardOutPath": str(log_path),
        "StandardErrorPath": str(log_path),
        "Umask": 0o077,
        "StartInterval": interval,
        "RunAtLoad": False,
        "EnvironmentVariables": {
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "PYTHONPATH": str(repo_root_path),
            "RSI_EVENT_ALERTS_ENABLED": "0",
            "RSI_EVENT_ALPHA_RUN_MODE": "operational",
            "RSI_EVENT_ALPHA_TARGETED_MARKET_REFRESH_ENABLED": "0",
            "RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR": str(artifact_base),
        },
    }


def inspect_scheduler_health(
    *,
    artifact_base: str | Path,
    top_n: int,
    fetch_limit: int | None,
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    repo_root_path: str | Path | None = None,
    python_path: str | Path | None = None,
    launch_agents_dir: str | Path | None = None,
    log_path: str | Path | None = None,
    dependencies: ServiceDependencies | None = None,
) -> SchedulerHealth:
    deps = dependencies or ServiceDependencies()
    repo = Path(repo_root_path or repository_root()).expanduser().resolve()
    python = Path(python_path or default_python_path()).expanduser().absolute()
    base = Path(artifact_base).expanduser().resolve()
    agents = Path(launch_agents_dir or (deps.home / "Library" / "LaunchAgents"))
    log = Path(log_path or (deps.home / "Library" / "Logs" / "crypto-radar-daily-operations.log"))
    plist_path = agents / f"{SERVICE_LABEL}.plist"
    expected = service_plist(
        repo_root_path=repo,
        python_path=python,
        artifact_base=base,
        log_path=log,
        top_n=top_n,
        fetch_limit=fetch_limit,
        interval_seconds=interval_seconds,
    )
    installed, plist_reason = _plist_matches(plist_path, expected)
    service = f"gui/{deps.uid}/{SERVICE_LABEL}"
    result = deps.run(("launchctl", "print", service))
    if result.returncode != 0:
        reason = plist_reason if plist_reason != "owned" else "scheduler_not_loaded"
        return SchedulerHealth(
            enabled=False,
            installed=installed,
            loaded=False,
            running=False,
            healthy=not installed,
            reason=reason,
            plist_path=str(plist_path),
        )
    argv = _launchctl_arguments(result.output)
    expected_argv = tuple(str(value) for value in expected["ProgramArguments"])
    if argv != expected_argv or not installed:
        return SchedulerHealth(
            enabled=False,
            installed=installed,
            loaded=True,
            running=False,
            healthy=False,
            reason="scheduler_ownership_mismatch",
            plist_path=str(plist_path),
            pid=_launchctl_int_field(result.output, "pid"),
        )
    state = _launchctl_field(result.output, "state")
    pid = _launchctl_int_field(result.output, "pid")
    running = state == "running"
    last_exit_code = _launchctl_int_field(result.output, "last exit code")
    runs = _launchctl_int_field(result.output, "runs")
    failed_last_run = not running and last_exit_code not in {None, 0}
    return SchedulerHealth(
        enabled=True,
        installed=True,
        loaded=True,
        running=running,
        healthy=not failed_last_run,
        reason=(
            "scheduler_last_exit_nonzero"
            if failed_last_run
            else "owned_loaded"
        ),
        plist_path=str(plist_path),
        pid=pid,
        last_exit_code=last_exit_code,
        runs=runs,
    )


def install_service(
    *,
    confirm: bool,
    artifact_base: str | Path,
    top_n: int,
    fetch_limit: int | None,
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    repo_root_path: str | Path | None = None,
    python_path: str | Path | None = None,
    launch_agents_dir: str | Path | None = None,
    log_path: str | Path | None = None,
    dependencies: ServiceDependencies | None = None,
) -> ServiceOperation:
    deps = dependencies or ServiceDependencies()
    health_args = dict(
        artifact_base=artifact_base,
        top_n=top_n,
        fetch_limit=fetch_limit,
        interval_seconds=interval_seconds,
        repo_root_path=repo_root_path,
        python_path=python_path,
        launch_agents_dir=launch_agents_dir,
        log_path=log_path,
        dependencies=deps,
    )
    if not confirm:
        health = inspect_scheduler_health(**health_args)
        return ServiceOperation(False, False, "confirmation_required", health)
    ownership = inspect_dashboard_ownership(
        artifact_base=artifact_base,
        repo_root_path=repo_root_path,
        python_path=python_path,
        dependencies=deps,
    )
    if not ownership.owned:
        health = inspect_scheduler_health(**health_args)
        return _record_service_operation(
            artifact_base,
            interval_seconds,
            "install",
            ServiceOperation(False, False, ownership.reason, health),
        )
    health = inspect_scheduler_health(**health_args)
    if health.loaded and not health.enabled:
        return _record_service_operation(
            artifact_base,
            interval_seconds,
            "install",
            ServiceOperation(False, False, "scheduler_ownership_mismatch", health),
        )
    if health.enabled:
        return _record_service_operation(
            artifact_base,
            interval_seconds,
            "install",
            ServiceOperation(True, False, "already_installed", health),
        )

    repo = Path(repo_root_path or repository_root()).expanduser().resolve()
    python = Path(python_path or default_python_path()).expanduser().absolute()
    base = Path(artifact_base).expanduser().resolve()
    agents = Path(launch_agents_dir or (deps.home / "Library" / "LaunchAgents"))
    log = Path(log_path or (deps.home / "Library" / "Logs" / "crypto-radar-daily-operations.log"))
    plist_path = agents / f"{SERVICE_LABEL}.plist"
    payload = service_plist(
        repo_root_path=repo,
        python_path=python,
        artifact_base=base,
        log_path=log,
        top_n=top_n,
        fetch_limit=fetch_limit,
        interval_seconds=interval_seconds,
    )
    try:
        _write_owned_plist(plist_path, payload)
        log.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError:
        failed = inspect_scheduler_health(**health_args)
        return _record_service_operation(
            artifact_base,
            interval_seconds,
            "install",
            ServiceOperation(False, False, "service_plist_write_failed", failed),
        )
    service = f"gui/{deps.uid}"
    boot = deps.run(("launchctl", "bootstrap", service, str(plist_path)))
    installed = inspect_scheduler_health(**health_args)
    if boot.returncode != 0 or not installed.enabled:
        operation = ServiceOperation(False, True, "scheduler_bootstrap_failed", installed)
    else:
        operation = ServiceOperation(True, True, "installed", installed)
    return _record_service_operation(
        artifact_base,
        interval_seconds,
        "install",
        operation,
    )


def uninstall_service(
    *,
    confirm: bool,
    artifact_base: str | Path,
    top_n: int,
    fetch_limit: int | None,
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    repo_root_path: str | Path | None = None,
    python_path: str | Path | None = None,
    launch_agents_dir: str | Path | None = None,
    log_path: str | Path | None = None,
    dependencies: ServiceDependencies | None = None,
) -> ServiceOperation:
    deps = dependencies or ServiceDependencies()
    health_args = dict(
        artifact_base=artifact_base,
        top_n=top_n,
        fetch_limit=fetch_limit,
        interval_seconds=interval_seconds,
        repo_root_path=repo_root_path,
        python_path=python_path,
        launch_agents_dir=launch_agents_dir,
        log_path=log_path,
        dependencies=deps,
    )
    health = inspect_scheduler_health(**health_args)
    if not confirm:
        return ServiceOperation(False, False, "confirmation_required", health)
    if health.loaded and not health.enabled:
        return _record_service_operation(
            artifact_base,
            interval_seconds,
            "uninstall",
            ServiceOperation(False, False, "scheduler_ownership_mismatch", health),
        )
    if not health.installed and not health.loaded:
        return _record_service_operation(
            artifact_base,
            interval_seconds,
            "uninstall",
            ServiceOperation(True, False, "already_uninstalled", health),
        )
    repo = Path(repo_root_path or repository_root()).expanduser().resolve()
    python = Path(python_path or default_python_path()).expanduser().absolute()
    base = Path(artifact_base).expanduser().resolve()
    log = Path(
        log_path
        or (deps.home / "Library" / "Logs" / "crypto-radar-daily-operations.log")
    )
    expected_plist = service_plist(
        repo_root_path=repo,
        python_path=python,
        artifact_base=base,
        log_path=log,
        top_n=top_n,
        fetch_limit=fetch_limit,
        interval_seconds=interval_seconds,
    )
    service = f"gui/{deps.uid}/{SERVICE_LABEL}"
    if health.loaded:
        stopped = deps.run(("launchctl", "bootout", service))
        if stopped.returncode != 0:
            return _record_service_operation(
                artifact_base,
                interval_seconds,
                "uninstall",
                ServiceOperation(False, False, "scheduler_bootout_failed", health),
            )
    plist_path = Path(health.plist_path or "")
    try:
        _remove_owned_plist(plist_path, expected_plist)
    except OSError:
        failed = inspect_scheduler_health(**health_args)
        return _record_service_operation(
            artifact_base,
            interval_seconds,
            "uninstall",
            ServiceOperation(
                False,
                False,
                "service_plist_remove_failed",
                failed,
            ),
        )
    final = inspect_scheduler_health(**health_args)
    return _record_service_operation(
        artifact_base,
        interval_seconds,
        "uninstall",
        ServiceOperation(True, True, "uninstalled", final),
    )


def _record_service_operation(
    artifact_base: str | Path,
    interval_seconds: int,
    operation_name: str,
    operation: ServiceOperation,
) -> ServiceOperation:
    payload = {
        "contract_version": 1,
        "row_type": "decision_radar_daily_operations_service",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "prepared": True,
        "operation": operation_name,
        "operation_ok": operation.ok,
        "operation_changed": operation.changed,
        "enabled": operation.health.enabled,
        "installed": operation.health.installed,
        "loaded": operation.health.loaded,
        "running": operation.health.running,
        "healthy": operation.health.healthy,
        "reason": operation.reason,
        "scheduler_reason": operation.health.reason,
        "scheduler_last_exit_code": operation.health.last_exit_code,
        "scheduler_runs": operation.health.runs,
        "scheduler_label": SERVICE_LABEL,
        "interval_seconds": int(interval_seconds),
        "trades_created": 0,
        "paper_trades_created": 0,
        "normal_rsi_signal_rows_written": 0,
        "triggered_fade_created": 0,
        "telegram_sends": 0,
        "no_send": True,
        "research_only": True,
    }
    try:
        write_json_atomic(
            Path(artifact_base).expanduser().resolve() / SERVICE_STATE_FILENAME,
            payload,
        )
    except Exception:
        return ServiceOperation(
            False,
            operation.changed,
            "service_receipt_write_failed",
            operation.health,
        )
    return operation


def _launchctl_arguments(text: str) -> tuple[str, ...]:
    lines = text.splitlines()
    inside = False
    values: list[str] = []
    for raw in lines:
        stripped = raw.strip()
        if not inside and stripped == "arguments = {":
            inside = True
            continue
        if inside and stripped == "}":
            return tuple(values)
        if inside and stripped:
            values.append(stripped)
    return ()


def _launchctl_field(text: str, key: str) -> str | None:
    prefix = f"{key} = "
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith(prefix):
            return stripped[len(prefix) :].strip()
    return None


def _launchctl_int_field(text: str, key: str) -> int | None:
    value = _launchctl_field(text, key)
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _plist_matches(path: Path, expected: Mapping[str, object]) -> tuple[bool, str]:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False, "service_not_installed"
    except OSError:
        return False, "service_plist_unreadable"
    if not stat.S_ISREG(info.st_mode):
        return False, "service_plist_not_regular"
    try:
        with path.open("rb") as handle:
            payload = plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException):
        return False, "service_plist_invalid"
    return (True, "owned") if payload == dict(expected) else (False, "service_plist_mismatch")


def _write_owned_plist(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    parent_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | os.O_NOFOLLOW
    parent_descriptor = os.open(path.parent, parent_flags)
    descriptor = -1
    temporary_name: str | None = None
    target_linked = False
    try:
        parent_snapshot = os.fstat(parent_descriptor)
        if not stat.S_ISDIR(parent_snapshot.st_mode):
            raise OSError("service plist parent is not a directory")
        installed, reason = _plist_matches_at(parent_descriptor, path.name, payload)
        if installed:
            return
        if reason != "service_not_installed":
            raise OSError("refusing to replace an unowned service plist")

        for _attempt in range(16):
            candidate = f".{path.name}.{secrets.token_hex(8)}"
            try:
                descriptor = os.open(
                    candidate,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=parent_descriptor,
                )
            except FileExistsError:
                continue
            temporary_name = candidate
            break
        if descriptor < 0 or temporary_name is None:
            raise OSError("unable to create private service plist temporary")

        os.fchmod(descriptor, 0o600)
        encoded = plistlib.dumps(dict(payload), sort_keys=False)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            descriptor = -1
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())

        _assert_directory_identity(path.parent, parent_snapshot)
        installed, reason = _plist_matches_at(parent_descriptor, path.name, payload)
        if installed or reason != "service_not_installed":
            raise OSError("refusing to replace a service plist created concurrently")
        os.link(
            temporary_name,
            path.name,
            src_dir_fd=parent_descriptor,
            dst_dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        target_linked = True
        _assert_same_directory_entry(
            parent_descriptor,
            temporary_name,
            path.name,
        )
        _assert_directory_identity(path.parent, parent_snapshot)
        os.unlink(temporary_name, dir_fd=parent_descriptor)
        temporary_name = None
        os.fsync(parent_descriptor)
        target_linked = False
    except Exception:
        if target_linked and temporary_name is not None:
            _remove_link_if_same(
                parent_descriptor,
                temporary_name,
                path.name,
            )
        raise
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary_name is not None:
            try:
                os.unlink(temporary_name, dir_fd=parent_descriptor)
            except FileNotFoundError:
                pass
        os.close(parent_descriptor)


def _plist_matches_at(
    parent_descriptor: int,
    name: str,
    expected: Mapping[str, object],
) -> tuple[bool, str]:
    descriptor = -1
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | os.O_NOFOLLOW,
            dir_fd=parent_descriptor,
        )
    except FileNotFoundError:
        return False, "service_not_installed"
    except OSError:
        return False, "service_plist_unreadable"
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > 256 * 1024:
            return False, "service_plist_not_regular"
        with os.fdopen(os.dup(descriptor), "rb") as handle:
            try:
                decoded = plistlib.load(handle)
            except plistlib.InvalidFileException:
                return False, "service_plist_invalid"
        return (
            (True, "owned")
            if decoded == dict(expected)
            else (False, "service_plist_mismatch")
        )
    finally:
        os.close(descriptor)


def _assert_directory_identity(path: Path, expected: os.stat_result) -> None:
    try:
        current = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise OSError("service plist parent changed during write") from exc
    if not (
        stat.S_ISDIR(current.st_mode)
        and current.st_dev == expected.st_dev
        and current.st_ino == expected.st_ino
    ):
        raise OSError("service plist parent changed during write")


def _assert_same_directory_entry(
    parent_descriptor: int,
    left_name: str,
    right_name: str,
) -> None:
    left = os.stat(left_name, dir_fd=parent_descriptor, follow_symlinks=False)
    right = os.stat(right_name, dir_fd=parent_descriptor, follow_symlinks=False)
    if not _same_file_snapshot(left, right):
        raise OSError("service plist create-only link identity mismatch")


def _remove_link_if_same(
    parent_descriptor: int,
    source_name: str,
    target_name: str,
) -> None:
    try:
        _assert_same_directory_entry(parent_descriptor, source_name, target_name)
        os.unlink(target_name, dir_fd=parent_descriptor)
    except OSError:
        pass


def _remove_owned_plist(path: Path, expected: Mapping[str, object]) -> None:
    """Re-attest exact owned bytes and identity through a no-follow directory fd."""

    parent_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | os.O_NOFOLLOW
    parent_descriptor = os.open(path.parent, parent_flags)
    descriptor = -1
    try:
        descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_descriptor)
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or opened.st_size > 256 * 1024:
            raise OSError("refusing to remove a non-regular service plist")
        with os.fdopen(os.dup(descriptor), "rb") as handle:
            try:
                payload = plistlib.load(handle)
            except plistlib.InvalidFileException as exc:
                raise OSError("refusing to remove an invalid service plist") from exc
        if payload != dict(expected):
            raise OSError("refusing to remove an unowned service plist")
        current = os.stat(path.name, dir_fd=parent_descriptor, follow_symlinks=False)
        if not _same_file_snapshot(opened, current):
            raise OSError("service plist changed during removal")
        os.unlink(path.name, dir_fd=parent_descriptor)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(parent_descriptor)


def _same_file_snapshot(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        stat.S_ISREG(right.st_mode)
        and left.st_dev == right.st_dev
        and left.st_ino == right.st_ino
        and left.st_size == right.st_size
        and left.st_mtime_ns == right.st_mtime_ns
        and left.st_ctime_ns == right.st_ctime_ns
    )


def format_json(value: Mapping[str, object]) -> str:
    return json.dumps(dict(value), indent=2, sort_keys=True)


__all__ = (
    "DASHBOARD_LABEL",
    "DEFAULT_INTERVAL_SECONDS",
    "DashboardOwnership",
    "SERVICE_LABEL",
    "SERVICE_STATE_FILENAME",
    "SchedulerHealth",
    "ServiceDependencies",
    "ServiceOperation",
    "expected_dashboard_argv",
    "expected_service_argv",
    "inspect_dashboard_ownership",
    "inspect_scheduler_health",
    "install_service",
    "restart_owned_dashboard",
    "probe_owned_dashboard",
    "service_plist",
    "uninstall_service",
    "wait_for_owned_dashboard_process",
)
