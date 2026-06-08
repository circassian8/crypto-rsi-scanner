"""Local operational helpers for logs and launchd services."""

from __future__ import annotations

import os
import plistlib
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class LogFileStatus:
    path: Path
    exists: bool
    size_bytes: int
    rotate_at_bytes: int
    rotation_count: int
    latest_rotation: Path | None

    @property
    def needs_rotation(self) -> bool:
        return self.exists and self.rotate_at_bytes >= 0 and self.size_bytes > self.rotate_at_bytes


@dataclass(frozen=True)
class LogRotationResult:
    path: Path
    rotated_to: Path | None
    size_before: int
    deleted: tuple[Path, ...]
    reason: str


@dataclass(frozen=True)
class LaunchdServiceStatus:
    label: str
    domain: str
    loaded: bool
    state: str | None = None
    pid: int | None = None
    runs: int | None = None
    last_exit_code: int | None = None
    stdout_path: str | None = None
    stderr_path: str | None = None
    plist_path: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class LaunchdCommandResult:
    label: str
    domain: str
    ok: bool
    action: str
    output: str


@dataclass(frozen=True)
class MaintenanceAgentInstallResult:
    label: str
    plist_path: Path
    loaded: bool
    output: str


def _utc_stamp(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def format_bytes(size: int | float | None) -> str:
    if size is None:
        return "n/a"
    units = ("B", "KiB", "MiB", "GiB")
    value = float(size)
    for unit in units:
        if abs(value) < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{value:.1f} GiB"


def _rotation_paths(path: Path) -> list[Path]:
    return sorted(path.parent.glob(f"{path.name}.*"), key=lambda p: p.name)


def _next_rotation_path(path: Path, now: datetime | None = None) -> Path:
    base = path.parent / f"{path.name}.{_utc_stamp(now)}"
    candidate = base
    suffix = 1
    while candidate.exists():
        candidate = path.parent / f"{base.name}.{suffix}"
        suffix += 1
    return candidate


def _prune_rotations(path: Path, keep: int) -> tuple[Path, ...]:
    rotations = _rotation_paths(path)
    extra = rotations[:-keep] if keep > 0 else rotations
    deleted: list[Path] = []
    for old in extra:
        old.unlink(missing_ok=True)
        deleted.append(old)
    return tuple(deleted)


def log_file_status(
    paths: list[Path] | tuple[Path, ...],
    *,
    max_bytes: int,
) -> list[LogFileStatus]:
    statuses: list[LogFileStatus] = []
    for path in paths:
        path = Path(path).expanduser()
        rotations = _rotation_paths(path)
        exists = path.exists()
        statuses.append(
            LogFileStatus(
                path=path,
                exists=exists,
                size_bytes=path.stat().st_size if exists else 0,
                rotate_at_bytes=max_bytes,
                rotation_count=len(rotations),
                latest_rotation=rotations[-1] if rotations else None,
            )
        )
    return statuses


def rotate_logs(
    paths: list[Path] | tuple[Path, ...],
    *,
    max_bytes: int,
    keep: int,
    now: datetime | None = None,
) -> list[LogRotationResult]:
    """Rotate oversized logs with copy-truncate so active launchd FDs keep working."""
    results: list[LogRotationResult] = []
    for path in paths:
        path = Path(path).expanduser()
        if not path.exists():
            deleted = _prune_rotations(path, keep)
            results.append(LogRotationResult(path, None, 0, deleted, "missing"))
            continue

        size = path.stat().st_size
        if size <= max_bytes:
            deleted = _prune_rotations(path, keep)
            results.append(LogRotationResult(path, None, size, deleted, "below-threshold"))
            continue

        rotated_to = _next_rotation_path(path, now)
        shutil.copy2(path, rotated_to)
        with path.open("r+b") as fh:
            fh.truncate(0)
        deleted = _prune_rotations(path, keep)
        results.append(LogRotationResult(path, rotated_to, size, deleted, "rotated"))
    return results


def format_log_rotation(results: list[LogRotationResult]) -> str:
    lines = ["Log rotation complete"]
    for result in results:
        if result.rotated_to is not None:
            lines.append(
                f"{result.path}: rotated {format_bytes(result.size_before)} -> "
                f"{result.rotated_to}"
            )
        elif result.reason == "missing":
            lines.append(f"{result.path}: missing")
        else:
            lines.append(f"{result.path}: kept ({format_bytes(result.size_before)})")
        if result.deleted:
            lines.append(f"{result.path}: pruned {len(result.deleted)} old rotation(s)")
    return "\n".join(lines)


def _field(text: str, key: str) -> str | None:
    match = re.search(rf"^\s*{re.escape(key)} = (.+)$", text, re.MULTILINE)
    if not match:
        return None
    return match.group(1).strip()


def _int_field(text: str, key: str) -> int | None:
    value = _field(text, key)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_launchctl_print(label: str, domain: str, text: str) -> LaunchdServiceStatus:
    return LaunchdServiceStatus(
        label=label,
        domain=domain,
        loaded=True,
        state=_field(text, "state"),
        pid=_int_field(text, "pid"),
        runs=_int_field(text, "runs"),
        last_exit_code=_int_field(text, "last exit code"),
        stdout_path=_field(text, "stdout path"),
        stderr_path=_field(text, "stderr path"),
        plist_path=_field(text, "path"),
    )


def launchd_status(
    labels: list[str] | tuple[str, ...],
    *,
    uid: int | None = None,
    timeout_sec: float = 5.0,
) -> list[LaunchdServiceStatus]:
    uid = os.getuid() if uid is None else uid
    domain = f"gui/{uid}"
    statuses: list[LaunchdServiceStatus] = []
    for label in labels:
        service = f"{domain}/{label}"
        try:
            proc = subprocess.run(
                ["launchctl", "print", service],
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                check=False,
            )
        except Exception as exc:  # noqa: BLE001
            statuses.append(LaunchdServiceStatus(label, domain, loaded=False, error=str(exc)))
            continue
        text = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0:
            statuses.append(
                LaunchdServiceStatus(
                    label=label,
                    domain=domain,
                    loaded=False,
                    error=text.strip() or f"launchctl exited {proc.returncode}",
                )
            )
            continue
        statuses.append(_parse_launchctl_print(label, domain, text))
    return statuses


def format_launchd_status(statuses: list[LaunchdServiceStatus]) -> str:
    lines = ["LAUNCHD SERVICES"]
    for status in statuses:
        if not status.loaded:
            detail = f" ({status.error})" if status.error else ""
            lines.append(f"{status.label}: not loaded{detail}")
            continue
        bits = [status.state or "unknown"]
        if status.pid is not None:
            bits.append(f"pid {status.pid}")
        if status.runs is not None:
            bits.append(f"runs {status.runs}")
        if status.last_exit_code is not None:
            bits.append(f"last exit {status.last_exit_code}")
        lines.append(f"{status.label}: " + ", ".join(bits))
        if status.stdout_path:
            lines.append(f"  stdout: {status.stdout_path}")
        if status.stderr_path and status.stderr_path != status.stdout_path:
            lines.append(f"  stderr: {status.stderr_path}")
    return "\n".join(lines)


def restart_launchd_service(
    label: str,
    *,
    uid: int | None = None,
    timeout_sec: float = 10.0,
) -> LaunchdCommandResult:
    uid = os.getuid() if uid is None else uid
    domain = f"gui/{uid}"
    service = f"{domain}/{label}"
    try:
        proc = subprocess.run(
            ["launchctl", "kickstart", "-k", service],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        return LaunchdCommandResult(label, domain, False, "restart", str(exc))
    output = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return LaunchdCommandResult(label, domain, proc.returncode == 0, "restart", output)


def format_launchd_command(result: LaunchdCommandResult) -> str:
    state = "ok" if result.ok else "failed"
    lines = [f"launchd {result.action} {state}: {result.domain}/{result.label}"]
    if result.output:
        lines.append(result.output)
    return "\n".join(lines)


def maintenance_agent_plist(
    *,
    label: str,
    python_path: Path,
    main_path: Path,
    working_dir: Path,
    log_path: Path,
    hour: int,
    minute: int,
) -> dict:
    return {
        "Label": label,
        "ProgramArguments": [str(python_path), str(main_path), "--maintenance"],
        "WorkingDirectory": str(working_dir),
        "StandardOutPath": str(log_path),
        "StandardErrorPath": str(log_path),
        "StartCalendarInterval": {"Hour": int(hour), "Minute": int(minute)},
        "RunAtLoad": False,
        "EnvironmentVariables": {
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        },
    }


def write_maintenance_agent_plist(
    *,
    label: str,
    python_path: Path,
    main_path: Path,
    working_dir: Path,
    log_path: Path,
    hour: int,
    minute: int,
    launch_agents_dir: Path | None = None,
) -> Path:
    launch_agents_dir = launch_agents_dir or (Path.home() / "Library" / "LaunchAgents")
    launch_agents_dir.mkdir(parents=True, exist_ok=True)
    plist_path = launch_agents_dir / f"{label}.plist"
    plist = maintenance_agent_plist(
        label=label,
        python_path=python_path,
        main_path=main_path,
        working_dir=working_dir,
        log_path=log_path,
        hour=hour,
        minute=minute,
    )
    with plist_path.open("wb") as fh:
        plistlib.dump(plist, fh, sort_keys=False)
    return plist_path


def install_maintenance_agent(
    *,
    label: str,
    python_path: Path,
    main_path: Path,
    working_dir: Path,
    log_path: Path,
    hour: int,
    minute: int,
    uid: int | None = None,
    launch_agents_dir: Path | None = None,
    timeout_sec: float = 10.0,
) -> MaintenanceAgentInstallResult:
    uid = os.getuid() if uid is None else uid
    domain = f"gui/{uid}"
    plist_path = write_maintenance_agent_plist(
        label=label,
        python_path=python_path,
        main_path=main_path,
        working_dir=working_dir,
        log_path=log_path,
        hour=hour,
        minute=minute,
        launch_agents_dir=launch_agents_dir,
    )
    outputs: list[str] = []
    subprocess.run(
        ["launchctl", "bootout", domain, str(plist_path)],
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        check=False,
    )
    proc = subprocess.run(
        ["launchctl", "bootstrap", domain, str(plist_path)],
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        check=False,
    )
    outputs.append(((proc.stdout or "") + (proc.stderr or "")).strip())
    if proc.returncode == 0:
        return MaintenanceAgentInstallResult(label, plist_path, True, "\n".join(o for o in outputs if o))

    status = launchd_status((label,), uid=uid, timeout_sec=timeout_sec)[0]
    return MaintenanceAgentInstallResult(
        label,
        plist_path,
        status.loaded,
        "\n".join(o for o in outputs if o),
    )


def format_maintenance_agent_install(result: MaintenanceAgentInstallResult) -> str:
    state = "installed" if result.loaded else "install failed"
    lines = [f"maintenance LaunchAgent {state}: {result.label}", f"plist: {result.plist_path}"]
    if result.output:
        lines.append(result.output)
    return "\n".join(lines)
