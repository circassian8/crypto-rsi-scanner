"""Per-profile run lock for research-only Event Alpha notification cycles.

Scheduled day-1 notification runs can overlap (cron stacking, a slow run still
finishing when the next fires). An overlapping notify cycle could double-send a
digest or race on lane cooldown meta. This module provides a best-effort,
profile/namespace-scoped file lock so only one notification cycle runs at a time.

It owns *liveness* only. It never sends, ranks, trades, paper trades, writes
normal RSI signal rows, or creates ``TRIGGERED_FADE``; those remain reserved for
``event_fade.py`` + ``proxy_fade``. Acquisition fails soft: a corrupt or
unreadable lock file degrades to "no lock held" rather than crashing the scan.
"""

from __future__ import annotations

import json
import os
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOCK_SCHEMA_VERSION = "event_alpha_run_lock_v1"

# Acquisition states.
STATE_ACQUIRED = "acquired"
STATE_STALE_RECOVERED = "stale_recovered"
STATE_OVERLAP_ALLOWED = "overlap_allowed"
STATE_ACTIVE = "active"
STATE_DISABLED = "disabled"
# Inspection-only states.
STATE_MISSING = "missing"
STATE_HELD = "held"
STATE_STALE = "stale"

STALE_LOCK_RECOVERED_WARNING = "stale_notification_lock_recovered"


@dataclass(frozen=True)
class EventAlphaRunLockConfig:
    enabled: bool = True
    stale_minutes: float = 30.0
    allow_overlap: bool = False


@dataclass(frozen=True)
class RunLockStatus:
    state: str
    path: Path
    acquired: bool
    skipped_due_to_active_lock: bool
    stale_recovered: bool
    holder: dict[str, Any] | None
    message: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class EventAlphaRunLock:
    path: Path
    run_id: str
    profile: str
    namespace: str
    lock_name: str
    status: RunLockStatus
    owned: bool

    @property
    def acquired(self) -> bool:
        return self.status.acquired

    @property
    def skipped_due_to_active_lock(self) -> bool:
        return self.status.skipped_due_to_active_lock

    @property
    def stale_recovered(self) -> bool:
        return self.status.stale_recovered

    @property
    def warnings(self) -> tuple[str, ...]:
        return self.status.warnings


def lock_path_for_context(context: Any, lock_name: str = "notify") -> Path:
    """Return the profile/namespace-scoped lock path for one notification lane."""
    namespace_dir = Path(getattr(context, "namespace_dir", None) or getattr(context, "base_dir", Path(".")))
    return namespace_dir / f"event_alpha_{_clean_name(lock_name)}.lock"


def acquire_run_lock(
    context: Any,
    *,
    cfg: EventAlphaRunLockConfig | None = None,
    run_id: str,
    profile: str | None = None,
    namespace: str | None = None,
    command: str = "notify",
    lock_name: str = "notify",
    now: datetime | None = None,
    pid: int | None = None,
    hostname: str | None = None,
) -> EventAlphaRunLock:
    """Try to take the notification run lock; never raise on filesystem issues."""
    cfg = cfg or EventAlphaRunLockConfig()
    observed = _as_utc(now or datetime.now(timezone.utc))
    path = lock_path_for_context(context, lock_name)
    profile = profile or _clean(getattr(context, "profile", None)) or "default"
    namespace = namespace or _clean(getattr(context, "artifact_namespace", None)) or "default"
    pid = int(pid if pid is not None else os.getpid())
    hostname = hostname if hostname is not None else _hostname()
    name = _clean_name(lock_name)

    if not cfg.enabled:
        status = RunLockStatus(
            state=STATE_DISABLED,
            path=path,
            acquired=True,
            skipped_due_to_active_lock=False,
            stale_recovered=False,
            holder=None,
            message="run lock disabled (RSI_EVENT_ALPHA_NOTIFY_LOCK_ENABLED=0)",
        )
        return EventAlphaRunLock(path, run_id, profile, namespace, name, status, owned=False)

    holder = _read_lock(path)
    same_run = holder is not None and str(holder.get("run_id") or "") == str(run_id)
    fresh = holder is not None and not same_run and _is_fresh(holder, observed, cfg.stale_minutes)

    if fresh and not cfg.allow_overlap:
        status = RunLockStatus(
            state=STATE_ACTIVE,
            path=path,
            acquired=False,
            skipped_due_to_active_lock=True,
            stale_recovered=False,
            holder=holder,
            message=(
                "active notification lock held by "
                f"run_id={holder.get('run_id') or 'unknown'} pid={holder.get('pid') or 'unknown'} "
                f"acquired_at={holder.get('acquired_at') or 'unknown'}"
            ),
        )
        return EventAlphaRunLock(path, run_id, profile, namespace, name, status, owned=False)

    overlap = fresh and cfg.allow_overlap
    stale_recovered = holder is not None and not same_run and not fresh
    warnings = (STALE_LOCK_RECOVERED_WARNING,) if stale_recovered else ()

    payload = {
        "schema_version": LOCK_SCHEMA_VERSION,
        "run_id": str(run_id),
        "profile": profile,
        "namespace": namespace,
        "lock_name": name,
        "pid": pid,
        "acquired_at": observed.isoformat(),
        "command": str(command or "notify"),
        "hostname": hostname,
    }
    written = _write_lock(path, payload)
    if not written:
        # Could not persist the lock; degrade to "proceed without enforcement"
        # rather than blocking the research run.
        status = RunLockStatus(
            state=STATE_DISABLED,
            path=path,
            acquired=True,
            skipped_due_to_active_lock=False,
            stale_recovered=stale_recovered,
            holder=holder,
            message="run lock could not be written; proceeding without lock enforcement",
            warnings=warnings + ("notification_lock_write_failed",),
        )
        return EventAlphaRunLock(path, run_id, profile, namespace, name, status, owned=False)

    if overlap:
        state = STATE_OVERLAP_ALLOWED
        message = "overlap allowed (RSI_EVENT_ALPHA_NOTIFY_ALLOW_OVERLAP=1); proceeding alongside existing lock"
    elif stale_recovered:
        state = STATE_STALE_RECOVERED
        message = (
            "recovered stale notification lock previously held by "
            f"run_id={holder.get('run_id') or 'unknown'} pid={holder.get('pid') or 'unknown'}"
        )
    else:
        state = STATE_ACQUIRED
        message = "notification run lock acquired"

    status = RunLockStatus(
        state=state,
        path=path,
        acquired=True,
        skipped_due_to_active_lock=False,
        stale_recovered=stale_recovered,
        holder=holder,
        message=message,
        warnings=warnings,
    )
    return EventAlphaRunLock(path, run_id, profile, namespace, name, status, owned=True)


def release_run_lock(lock: EventAlphaRunLock | None) -> bool:
    """Best-effort release. Only removes a lock file this run owns; never raises."""
    if lock is None or not lock.owned:
        return False
    try:
        holder = _read_lock(lock.path)
        if holder is None:
            return False
        if str(holder.get("run_id") or "") != str(lock.run_id):
            # Another run took the lock over; do not delete theirs.
            return False
        lock.path.unlink()
        return True
    except OSError:
        return False


def inspect_run_lock(
    context: Any,
    *,
    lock_name: str = "notify",
    now: datetime | None = None,
    stale_minutes: float = 30.0,
) -> RunLockStatus:
    """Read-only view of the current lock holder for status/doctor reports."""
    path = lock_path_for_context(context, lock_name)
    observed = _as_utc(now or datetime.now(timezone.utc))
    holder = _read_lock(path)
    if holder is None:
        return RunLockStatus(
            state=STATE_MISSING,
            path=path,
            acquired=False,
            skipped_due_to_active_lock=False,
            stale_recovered=False,
            holder=None,
            message="no active notification lock",
        )
    fresh = _is_fresh(holder, observed, stale_minutes)
    return RunLockStatus(
        state=STATE_HELD if fresh else STATE_STALE,
        path=path,
        acquired=False,
        skipped_due_to_active_lock=fresh,
        stale_recovered=False,
        holder=holder,
        message=(
            f"{'fresh' if fresh else 'stale'} notification lock held by "
            f"run_id={holder.get('run_id') or 'unknown'} pid={holder.get('pid') or 'unknown'} "
            f"acquired_at={holder.get('acquired_at') or 'unknown'}"
        ),
    )


def _is_fresh(holder: dict[str, Any], now: datetime, stale_minutes: float) -> bool:
    ts = _parse_iso(holder.get("acquired_at"))
    if ts is None:
        return False
    if (now - ts).total_seconds() > max(0.0, float(stale_minutes)) * 60.0:
        return False
    return _holder_process_alive(holder)


def _holder_process_alive(holder: dict[str, Any]) -> bool:
    """Treat a dead holder PID on this host as not fresh so it can be recovered.

    Conservative: any uncertainty (different host, missing/odd PID, permission
    error) is treated as alive so we never steal a lock we cannot verify is dead.
    """
    host = str(holder.get("hostname") or "")
    if host and host != _hostname():
        return True
    raw_pid = holder.get("pid")
    try:
        pid = int(raw_pid)
    except (TypeError, ValueError):
        return True
    if pid <= 0:
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    return True


def _read_lock(path: Path) -> dict[str, Any] | None:
    try:
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _write_lock(path: Path, payload: dict[str, Any]) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, sort_keys=True, separators=(",", ":"))
        os.replace(tmp, path)
        return True
    except OSError:
        return False


def _hostname() -> str:
    try:
        return socket.gethostname()
    except OSError:
        return ""


def _parse_iso(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _as_utc(parsed)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _clean(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _clean_name(value: object) -> str:
    text = str(value or "").strip().lower()
    cleaned = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in text).strip("_-")
    return cleaned or "notify"
