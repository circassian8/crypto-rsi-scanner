"""Confirmation-gated macOS maintenance for the Lean Radar no-send cycle."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import os
from pathlib import Path
import plistlib
import subprocess
import sys
from typing import Callable, Mapping, Sequence

from .config import PROJECT_ROOT, LeanRadarSettings
from .path_security import (
    LeanPathSecurityError,
    anchored_path,
    atomic_write_regular_bytes,
    read_regular_bytes,
    require_regular_single_link,
    unlink_regular_file,
)
from .store import LeanRadarStore, LeanRadarStoreError


SERVICE_LABEL = "com.nasrenkaraf.crypto-rsi-scanner.lean-radar"
MAX_PLIST_BYTES = 64 * 1024
DEFAULT_PLIST_PATH = (
    Path.home() / "Library" / "LaunchAgents" / f"{SERVICE_LABEL}.plist"
)
LaunchctlRunner = Callable[[Sequence[str]], int]


class _LeanMaintenanceError(RuntimeError):
    """Raised when the owned maintenance service cannot be proven safe."""


LeanMaintenanceError = _LeanMaintenanceError


def service_plist_bytes(
    settings: LeanRadarSettings,
    *,
    python_executable: Path | None = None,
) -> bytes:
    interpreter = _validated_interpreter(python_executable)
    payload = {
        "Label": SERVICE_LABEL,
        "ProgramArguments": [
            str(interpreter),
            "-m",
            "crypto_rsi_scanner.lean_radar",
            "--db",
            str(settings.db_path),
            "scheduled-cycle",
        ],
        "WorkingDirectory": str(PROJECT_ROOT),
        "StartInterval": settings.cadence_minutes * 60,
        "RunAtLoad": False,
        "KeepAlive": False,
        "ProcessType": "Background",
    }
    encoded = plistlib.dumps(payload, fmt=plistlib.FMT_XML, sort_keys=True)
    if len(encoded) > MAX_PLIST_BYTES:
        raise LeanMaintenanceError("maintenance plist exceeds its size bound")
    return encoded


def maintenance_status(
    settings: LeanRadarSettings,
    *,
    evaluated_at: datetime | None = None,
    plist_path: Path = DEFAULT_PLIST_PATH,
    python_executable: Path | None = None,
) -> dict[str, object]:
    now = evaluated_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise LeanMaintenanceError("maintenance status time must be timezone-aware")
    now = now.astimezone(timezone.utc)
    try:
        expected = service_plist_bytes(
            settings,
            python_executable=python_executable,
        )
        expected_digest = hashlib.sha256(expected).hexdigest()
        interpreter_ready = True
        preparation_error = None
    except LeanMaintenanceError:
        expected_digest = None
        interpreter_ready = False
        preparation_error = "the configured Python executable is unavailable"
    installed = False
    owned = False
    conflict = False
    unsafe_path = False
    actual_digest: str | None = None
    runtime_available = False
    runtime_error: str | None = None
    try:
        database = LeanRadarStore(settings.db_path).database_status(
            evaluated_at=now,
        )
        runtime_available = database.get("status") in {"ready", "attention"}
        if not runtime_available:
            runtime_error = "Lean Radar runtime is not initialized"
    except LeanRadarStoreError:
        runtime_error = "Lean Radar runtime is unavailable or unsafe"
    try:
        with anchored_path(plist_path) as anchored:
            info = anchored.stat_leaf(missing_ok=True)
        if info is not None:
            secured = read_regular_bytes(
                plist_path,
                maximum_bytes=MAX_PLIST_BYTES,
            )
            installed = True
            actual_digest = secured.sha256
            owned = expected_digest is not None and actual_digest == expected_digest
            conflict = not owned
    except LeanPathSecurityError:
        unsafe_path = True
        conflict = True
    status = (
        "unsafe_path"
        if unsafe_path
        else "unowned_conflict"
        if conflict
        else "installed"
        if owned
        else "setup_required"
        if not runtime_available
        else "prepared_disabled"
        if interpreter_ready and sys.platform == "darwin"
        else "unsupported_host"
        if sys.platform != "darwin"
        else "preparation_blocked"
    )
    next_safe_command = (
        "CONFIRM=1 make lean-radar-bybit-universe-import "
        "LEAN_RADAR_BYBIT_CATALOG=/absolute/path/to/instruments-info.json"
        if status == "setup_required"
        else "CONFIRM=1 make lean-radar-maintenance-install"
        if status == "prepared_disabled"
        else "make lean-radar-cycle"
        if status == "installed"
        else "make lean-radar-maintenance-status"
    )
    return {
        "schema_version": "lean_maintenance_status_v1",
        "status": status,
        "service_label": SERVICE_LABEL,
        "plist_path": str(plist_path),
        "installed": installed,
        "installed_owned": owned,
        "enabled": owned,
        "prepared": interpreter_ready,
        "runtime_available": runtime_available,
        "runtime_error": runtime_error,
        "host_supported": sys.platform == "darwin",
        "cadence_minutes": settings.cadence_minutes,
        "next_scheduled_at": None,
        "expected_plist_sha256": expected_digest,
        "installed_plist_sha256": actual_digest,
        "preparation_error": preparation_error,
        "contains_authorization_or_credentials": False,
        "provider_call_attempted": False,
        "telegram_send_attempted": False,
        "install_command": "CONFIRM=1 make lean-radar-maintenance-install",
        "disable_command": "CONFIRM=1 make lean-radar-maintenance-uninstall",
        "manual_cycle_command": "make lean-radar-cycle",
        "next_safe_command": next_safe_command,
        "checked_at": now.isoformat(),
        "research_only": True,
    }


def install_maintenance(
    settings: LeanRadarSettings,
    *,
    confirm: bool,
    plist_path: Path = DEFAULT_PLIST_PATH,
    python_executable: Path | None = None,
    runner: LaunchctlRunner | None = None,
) -> dict[str, object]:
    if not confirm:
        return _confirmation_required("install")
    if sys.platform != "darwin":
        raise LeanMaintenanceError("Lean maintenance installation is macOS-only")
    payload = service_plist_bytes(
        settings,
        python_executable=python_executable,
    )
    digest = hashlib.sha256(payload).hexdigest()
    status = maintenance_status(
        settings,
        plist_path=plist_path,
        python_executable=python_executable,
    )
    if status["installed"] and not status["installed_owned"]:
        raise LeanMaintenanceError(
            "refusing to replace an unowned maintenance plist"
        )
    if status["status"] == "unsafe_path":
        raise LeanMaintenanceError("maintenance plist path is unsafe")
    if status["runtime_available"] is not True:
        raise LeanMaintenanceError(
            "Lean Radar runtime must be initialized before maintenance installation"
        )
    launchctl = runner or _run_launchctl
    domain = f"gui/{os.getuid()}"
    if status["installed_owned"] and launchctl(
        ("launchctl", "print", f"{domain}/{SERVICE_LABEL}")
    ) == 0:
        return {
            **status,
            "status": "already_installed",
            "mutation_performed": False,
        }
    if not status["installed"]:
        try:
            atomic_write_regular_bytes(
                plist_path,
                payload,
                maximum_bytes=MAX_PLIST_BYTES,
                mode=0o600,
                refuse_existing=True,
            )
        except LeanPathSecurityError as exc:
            raise LeanMaintenanceError(
                "maintenance plist could not be published safely"
            ) from exc
    if launchctl(("launchctl", "bootstrap", domain, str(plist_path))) != 0:
        try:
            unlink_regular_file(
                plist_path,
                maximum_bytes=MAX_PLIST_BYTES,
                expected_sha256=digest,
            )
        except LeanPathSecurityError:
            pass
        raise LeanMaintenanceError("launchd rejected the owned maintenance service")
    final = maintenance_status(
        settings,
        plist_path=plist_path,
        python_executable=python_executable,
    )
    if not final["installed_owned"]:
        raise LeanMaintenanceError("maintenance installation could not be verified")
    return {
        **final,
        "status": "installed",
        "mutation_performed": True,
    }


def uninstall_maintenance(
    settings: LeanRadarSettings,
    *,
    confirm: bool,
    plist_path: Path = DEFAULT_PLIST_PATH,
    python_executable: Path | None = None,
    runner: LaunchctlRunner | None = None,
) -> dict[str, object]:
    if not confirm:
        return _confirmation_required("uninstall")
    if sys.platform != "darwin":
        raise LeanMaintenanceError("Lean maintenance installation is macOS-only")
    status = maintenance_status(
        settings,
        plist_path=plist_path,
        python_executable=python_executable,
    )
    if not status["installed"]:
        return {
            **status,
            "status": "already_disabled",
            "mutation_performed": False,
        }
    if not status["installed_owned"]:
        raise LeanMaintenanceError("refusing to remove an unowned maintenance plist")
    launchctl = runner or _run_launchctl
    domain = f"gui/{os.getuid()}"
    loaded = launchctl(("launchctl", "print", f"{domain}/{SERVICE_LABEL}")) == 0
    if loaded and launchctl(
        ("launchctl", "bootout", f"{domain}/{SERVICE_LABEL}")
    ) != 0:
        raise LeanMaintenanceError("launchd did not disable the owned service")
    digest = status["installed_plist_sha256"]
    assert isinstance(digest, str)
    try:
        unlink_regular_file(
            plist_path,
            maximum_bytes=MAX_PLIST_BYTES,
            expected_sha256=digest,
        )
    except LeanPathSecurityError as exc:
        raise LeanMaintenanceError(
            "owned maintenance plist could not be removed safely"
        ) from exc
    final = maintenance_status(
        settings,
        plist_path=plist_path,
        python_executable=python_executable,
    )
    return {
        **final,
        "status": "disabled",
        "mutation_performed": True,
    }


def next_scheduled_time(
    *,
    last_attempted_at: str | None,
    cadence_minutes: int,
) -> str | None:
    if last_attempted_at is None:
        return None
    try:
        parsed = datetime.fromisoformat(last_attempted_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LeanMaintenanceError("stored cycle receipt clock is invalid") from exc
    if parsed.tzinfo is None:
        raise LeanMaintenanceError("stored cycle receipt clock is not timezone-aware")
    return (
        parsed.astimezone(timezone.utc) + timedelta(minutes=cadence_minutes)
    ).isoformat()


def _validated_interpreter(value: Path | None) -> Path:
    try:
        candidate = (value or Path(sys.executable)).expanduser().resolve(strict=True)
        with anchored_path(candidate) as anchored:
            info = anchored.stat_leaf()
            assert info is not None
            require_regular_single_link(info, maximum_bytes=256 * 1024 * 1024)
        if not os.access(candidate, os.X_OK):
            raise LeanMaintenanceError(
                "maintenance Python executable is not executable"
            )
    except (LeanPathSecurityError, OSError) as exc:
        raise LeanMaintenanceError(
            "maintenance Python executable is unavailable"
        ) from exc
    return candidate


def _confirmation_required(action: str) -> dict[str, object]:
    return {
        "schema_version": "lean_maintenance_status_v1",
        "status": "confirmation_required",
        "action": action,
        "mutation_performed": False,
        "provider_call_attempted": False,
        "telegram_send_attempted": False,
        "research_only": True,
    }


def _run_launchctl(command: Sequence[str]) -> int:
    try:
        completed = subprocess.run(
            tuple(command),
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return 127
    return int(completed.returncode)


__all__ = (
    "DEFAULT_PLIST_PATH",
    "MAX_PLIST_BYTES",
    "SERVICE_LABEL",
    "LeanMaintenanceError",
    "install_maintenance",
    "maintenance_status",
    "next_scheduled_time",
    "service_plist_bytes",
    "uninstall_maintenance",
)
