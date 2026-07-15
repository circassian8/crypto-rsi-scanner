"""Guarded public Cloudflare Quick Tunnel access to the radar dashboard.

The dashboard itself remains bound to loopback.  This helper owns at most one
ephemeral ``cloudflared`` child and records the exact process identity needed
to inspect or stop it safely.  It intentionally does not install a service or
persist a tunnel across restarts.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
import ctypes
import ctypes.util
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import fcntl
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import struct
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterator
from urllib.parse import urlsplit


LOCAL_DASHBOARD_URL = "http://127.0.0.1:8765"
CLOUDFLARED_BINARY_ENV = "RSI_RADAR_CLOUDFLARED_BIN"
PUBLIC_MAX_LIFETIME_ENV = "RSI_RADAR_PUBLIC_MAX_LIFETIME_MINUTES"

_STATE_SCHEMA_VERSION = 2
_DEFAULT_MAX_LIFETIME = timedelta(hours=4)
_MIN_MAX_LIFETIME_MINUTES = 15
_MAX_MAX_LIFETIME_MINUTES = 24 * 60
_MAX_STATE_BYTES = 64 * 1024
_MAX_LOG_BYTES = 256 * 1024
_URL_POLL_ATTEMPTS = 40
_URL_POLL_SECONDS = 0.25
_REGISTRATION_POLL_ATTEMPTS = 80
_REGISTRATION_POLL_SECONDS = 0.25
_PUBLIC_DNS_SETTLE_SECONDS = 5.0
_PUBLIC_PROBE_ATTEMPTS = 30
_PUBLIC_PROBE_SECONDS = 1.0
_PUBLIC_PROBE_TIMEOUT_SECONDS = 2.5
_PUBLIC_BODY_PREFIX_BYTES = 16 * 1024
_PUBLIC_BODY_MARKER = b"Crypto Decision Radar"
_SAFE_CHILD_ENV_KEYS = frozenset(
    {"HOME", "LANG", "LC_ALL", "PATH", "SSL_CERT_DIR", "SSL_CERT_FILE", "TMPDIR"}
)
_QUICK_TUNNEL_HOST_RE = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.trycloudflare\.com$"
)
_URL_TOKEN_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


@dataclass(frozen=True)
class _SpawnedChild:
    """Exact child handle retained until public enable either commits or rolls back."""

    pid: int
    is_running: Callable[[], bool]
    stop: Callable[[], bool]


def _default_runtime_directory() -> Path:
    return Path.home() / "Library" / "Caches" / "crypto-rsi-scanner" / "dashboard-public"


def _default_state_path() -> Path:
    return _default_runtime_directory() / "state.json"


def _default_log_path() -> Path:
    return _default_runtime_directory() / "cloudflared.log"


def _default_config_paths() -> tuple[Path, ...]:
    root = Path.home() / ".cloudflared"
    return (root / "config.yml", root / "config.yaml")


@dataclass(frozen=True)
class _PublicAccessDependencies:
    """Injectable process, filesystem, clock, and HTTP boundaries."""

    environ: Mapping[str, str] = field(default_factory=lambda: os.environ)
    which: Callable[[str], str | None] = shutil.which
    is_executable: Callable[[str], bool] = lambda value: (
        Path(value).is_file() and os.access(value, os.X_OK)
    )
    http_status: Callable[[str, float], int] = lambda url, timeout: _local_http_status(
        url, timeout
    )
    public_http_ready: Callable[[str, float], bool] = (
        lambda url, timeout: _public_dashboard_ready(url, timeout)
    )
    spawn: Callable[[tuple[str, ...]], _SpawnedChild] = lambda argv: _spawn(argv)
    process_alive: Callable[[int], bool] = lambda pid: _process_alive(pid)
    process_matches: Callable[[int, tuple[str, ...]], bool] = (
        lambda pid, argv: _process_matches(pid, argv)
    )
    terminate: Callable[[int], bool] = lambda pid: _terminate_process_group(pid)
    sleep: Callable[[float], None] = time.sleep
    state_path: Path = field(default_factory=_default_state_path)
    log_path: Path = field(default_factory=_default_log_path)
    config_paths: tuple[Path, ...] = field(default_factory=_default_config_paths)
    path_exists: Callable[[Path], bool] = lambda path: path.exists()
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)


@dataclass(frozen=True)
class _PublicAccessStatus:
    """Secret-safe public-access state."""

    ready: bool
    dashboard_ready: bool
    cloudflared_found: bool
    process_state: str
    public_url: str | None
    expires_at: str | None
    blockers: tuple[str, ...]

    @property
    def enabled(self) -> bool:
        return self.ready and self.process_state == "owned" and self.public_url is not None


@dataclass(frozen=True)
class _PublicAccessOperation:
    """Result of an explicitly confirmed enable or disable operation."""

    ok: bool
    changed: bool
    status: _PublicAccessStatus | None
    reason: str | None = None


@dataclass(frozen=True)
class _OwnedState:
    pid: int
    public_url: str
    argv: tuple[str, ...]
    started_at: datetime
    expires_at: datetime


def discover_cloudflared_binary(
    dependencies: _PublicAccessDependencies | None = None,
) -> str | None:
    """Resolve an executable from an explicit override, then ``PATH``."""

    deps = dependencies or _PublicAccessDependencies()
    candidates = (
        str(deps.environ.get(CLOUDFLARED_BINARY_ENV, "")).strip(),
        str(deps.which("cloudflared") or "").strip(),
    )
    return next((value for value in candidates if value and deps.is_executable(value)), None)


def extract_quick_tunnel_url(text: str) -> str | None:
    """Return one unique canonical Quick Tunnel URL from bounded log text.

    Duplicate appearances of the same URL are expected.  Any malformed
    trycloudflare-like URL or more than one distinct canonical URL fails closed.
    """

    if not isinstance(text, str):
        return None
    candidates = [
        token.rstrip(".,;:!)]}")
        for token in _URL_TOKEN_RE.findall(text)
        if "trycloudflare.com" in token.casefold()
    ]
    if not candidates:
        return None
    canonical: set[str] = set()
    for candidate in candidates:
        if not _is_canonical_quick_tunnel_url(candidate):
            return None
        canonical.add(candidate)
    return next(iter(canonical)) if len(canonical) == 1 else None


def inspect_public_access(
    dependencies: _PublicAccessDependencies | None = None,
) -> _PublicAccessStatus:
    """Inspect readiness and helper-owned state without writes or mutations."""

    deps = dependencies or _PublicAccessDependencies()
    blockers: list[str] = []
    dashboard_ready = _dashboard_ready(deps)
    if not dashboard_ready:
        blockers.append("local_dashboard_unavailable")

    binary = discover_cloudflared_binary(deps)
    if binary is None:
        blockers.append("cloudflared_binary_missing")
    if _configured_cloudflared_path(deps) is not None:
        blockers.append("cloudflared_config_present")
    if _configured_max_lifetime(deps) is None:
        blockers.append("public_access_lifetime_invalid")

    state_kind, state = _classify_state(deps)
    if state_kind == "invalid":
        blockers.append("public_access_state_invalid")
    elif state_kind == "stale":
        blockers.append("public_access_state_stale")
    elif state_kind == "unowned":
        blockers.append("public_access_state_unowned")
    elif state_kind == "expired":
        blockers.append("public_access_expired")
    elif state_kind == "owned" and state is not None:
        try:
            public_ready = deps.public_http_ready(
                state.public_url, _PUBLIC_PROBE_TIMEOUT_SECONDS
            )
        except Exception:
            public_ready = False
        if not public_ready:
            blockers.append("public_dashboard_unavailable")

    public_url = state.public_url if state_kind == "owned" and state else None
    expires_at = _format_timestamp(state.expires_at) if state is not None else None
    return _PublicAccessStatus(
        ready=not blockers,
        dashboard_ready=dashboard_ready,
        cloudflared_found=binary is not None,
        process_state=state_kind,
        public_url=public_url,
        expires_at=expires_at,
        blockers=tuple(blockers),
    )


def enable_public_access(
    *,
    confirm: bool,
    dependencies: _PublicAccessDependencies | None = None,
) -> _PublicAccessOperation:
    """Start one ephemeral Quick Tunnel after explicit confirmation."""

    if not confirm:
        return _PublicAccessOperation(False, False, None, "confirmation_required")
    deps = dependencies or _PublicAccessDependencies()
    try:
        with _operation_lock(deps.state_path) as acquired:
            if not acquired:
                return _PublicAccessOperation(
                    False, False, None, "public_access_operation_busy"
                )
            return _enable_public_access_confirmed(deps)
    except OSError:
        return _PublicAccessOperation(
            False, False, None, "public_access_operation_lock_failed"
        )


def _enable_public_access_confirmed(
    deps: _PublicAccessDependencies,
) -> _PublicAccessOperation:
    before = inspect_public_access(deps)
    if not before.ready:
        return _PublicAccessOperation(False, False, before, _first_reason(before))
    if before.enabled:
        return _PublicAccessOperation(True, False, before)

    binary = discover_cloudflared_binary(deps)
    if binary is None:  # Defensive: inspection already proved this boundary.
        return _PublicAccessOperation(False, False, before, "cloudflared_binary_missing")
    command = _tunnel_command(binary, deps.log_path)
    try:
        _prepare_private_log(deps.log_path)
        child = deps.spawn(command)
    except Exception:
        return _PublicAccessOperation(False, False, before, "tunnel_start_failed")
    if (
        not isinstance(child, _SpawnedChild)
        or not isinstance(child.pid, int)
        or isinstance(child.pid, bool)
        or child.pid <= 1
    ):
        return _PublicAccessOperation(False, False, before, "tunnel_start_failed")
    pid = child.pid

    public_url = _poll_tunnel_url(deps, pid)
    if public_url is None:
        if not _cleanup_spawned_child(child):
            return _PublicAccessOperation(
                False, False, before, "tunnel_cleanup_failed"
            )
        _remove_log(deps.log_path)
        return _PublicAccessOperation(False, False, before, "tunnel_url_unavailable")
    if not _owned_live_process(deps, pid, command):
        if not _cleanup_spawned_child(child):
            return _PublicAccessOperation(
                False, False, before, "tunnel_cleanup_failed"
            )
        _remove_log(deps.log_path)
        return _PublicAccessOperation(False, False, before, "tunnel_process_unowned")
    if not _poll_tunnel_registration(deps, pid, command):
        if not _cleanup_spawned_child(child):
            return _PublicAccessOperation(
                False, False, before, "tunnel_cleanup_failed"
            )
        _remove_log(deps.log_path)
        return _PublicAccessOperation(
            False, False, before, "tunnel_registration_unavailable"
        )
    # Avoid caching an early NXDOMAIN before Cloudflare's issued hostname is live.
    deps.sleep(_PUBLIC_DNS_SETTLE_SECONDS)
    if not _poll_public_dashboard(deps, pid, command, public_url):
        if not _cleanup_spawned_child(child):
            return _PublicAccessOperation(
                False, False, before, "tunnel_cleanup_failed"
            )
        _remove_log(deps.log_path)
        return _PublicAccessOperation(
            False, False, before, "public_dashboard_unavailable"
        )

    started_at = _utc_now(deps)
    max_lifetime = _configured_max_lifetime(deps)
    if max_lifetime is None:  # Defensive: inspection already proved this boundary.
        if not _cleanup_spawned_child(child):
            return _PublicAccessOperation(False, False, before, "tunnel_cleanup_failed")
        _remove_log(deps.log_path)
        return _PublicAccessOperation(False, False, before, "public_access_lifetime_invalid")
    payload = {
        "schema_version": _STATE_SCHEMA_VERSION,
        "pid": pid,
        "public_url": public_url,
        "origin": LOCAL_DASHBOARD_URL,
        "argv": list(command),
        "started_at": _format_timestamp(started_at),
        "expires_at": _format_timestamp(started_at + max_lifetime),
    }
    try:
        _atomic_write_state(deps.state_path, payload)
    except Exception:
        cleaned = _cleanup_spawned_child(child)
        if cleaned:
            _remove_state(deps.state_path)
            _remove_log(deps.log_path)
        return _PublicAccessOperation(
            False,
            _path_lexists(deps.state_path),
            before,
            "public_access_state_write_failed" if cleaned else "tunnel_cleanup_failed",
        )

    after = inspect_public_access(deps)
    if not after.enabled:
        if _cleanup_spawned_child(child):
            _remove_state(deps.state_path)
            _remove_log(deps.log_path)
            return _PublicAccessOperation(
                False,
                False,
                inspect_public_access(deps),
                "post_enable_verification_failed",
            )
        # Retain the receipt and log so a confirmed disable can retry safely.
        return _PublicAccessOperation(False, True, after, "tunnel_cleanup_failed")
    return _PublicAccessOperation(True, True, after)


def disable_public_access(
    *,
    confirm: bool,
    dependencies: _PublicAccessDependencies | None = None,
) -> _PublicAccessOperation:
    """Stop only the exact live child described by the helper-owned receipt."""

    if not confirm:
        return _PublicAccessOperation(False, False, None, "confirmation_required")
    deps = dependencies or _PublicAccessDependencies()
    try:
        with _operation_lock(deps.state_path) as acquired:
            if not acquired:
                return _PublicAccessOperation(
                    False, False, None, "public_access_operation_busy"
                )
            return _disable_public_access_confirmed(deps)
    except OSError:
        return _PublicAccessOperation(
            False, False, None, "public_access_operation_lock_failed"
        )


def guard_public_access(
    *,
    confirm: bool,
    dependencies: _PublicAccessDependencies | None = None,
) -> _PublicAccessOperation:
    """Stop only an exact owned tunnel that is expired or no longer trusted."""

    if not confirm:
        return _PublicAccessOperation(False, False, None, "confirmation_required")
    deps = dependencies or _PublicAccessDependencies()
    try:
        with _operation_lock(deps.state_path) as acquired:
            if not acquired:
                return _PublicAccessOperation(
                    False, False, None, "public_access_operation_busy"
                )
            status = inspect_public_access(deps)
            unsafe_owned = status.process_state in {"owned", "expired"} and any(
                reason
                in {
                    "local_dashboard_unavailable",
                    "public_dashboard_unavailable",
                    "public_access_expired",
                }
                for reason in status.blockers
            )
            if not unsafe_owned:
                return _PublicAccessOperation(True, False, status)
            return _disable_public_access_confirmed(deps)
    except OSError:
        return _PublicAccessOperation(
            False, False, None, "public_access_operation_lock_failed"
        )


def _disable_public_access_confirmed(
    deps: _PublicAccessDependencies,
) -> _PublicAccessOperation:
    state_kind, state = _classify_state(deps)
    if state_kind == "absent":
        return _PublicAccessOperation(True, False, inspect_public_access(deps))
    if state_kind == "stale":
        _remove_state(deps.state_path)
        _remove_log(deps.log_path)
        return _PublicAccessOperation(True, True, inspect_public_access(deps))
    if state_kind not in {"owned", "expired"} or state is None:
        reason = (
            "public_access_state_unowned"
            if state_kind == "unowned"
            else "public_access_state_invalid"
        )
        return _PublicAccessOperation(False, False, inspect_public_access(deps), reason)
    if not _owned_live_process(deps, state.pid, state.argv):
        return _PublicAccessOperation(
            False,
            False,
            inspect_public_access(deps),
            "public_access_state_unowned",
        )
    try:
        stopped = deps.terminate(state.pid)
    except Exception:
        stopped = False
    try:
        still_alive = deps.process_alive(state.pid)
    except Exception:
        still_alive = True
    if not stopped or still_alive:
        return _PublicAccessOperation(
            False,
            False,
            inspect_public_access(deps),
            "tunnel_stop_failed",
        )
    _remove_state(deps.state_path)
    _remove_log(deps.log_path)
    return _PublicAccessOperation(True, True, inspect_public_access(deps))


def _tunnel_command(binary: str, log_path: Path) -> tuple[str, ...]:
    return (
        binary,
        "tunnel",
        "--protocol",
        "http2",
        "--url",
        LOCAL_DASHBOARD_URL,
        "--no-autoupdate",
        "--loglevel",
        "info",
        "--transport-loglevel",
        "warn",
        "--metrics",
        "127.0.0.1:0",
        "--logfile",
        str(log_path),
    )


def _classify_state(
    deps: _PublicAccessDependencies,
) -> tuple[str, _OwnedState | None]:
    loaded = _read_state(deps.state_path)
    if loaded is None:
        return ("absent", None) if not _path_lexists(deps.state_path) else ("invalid", None)
    state = _validated_state(loaded)
    if state is None:
        return "invalid", None
    if state.argv != _tunnel_command(state.argv[0], deps.log_path):
        return "unowned", state
    try:
        alive = deps.process_alive(state.pid)
    except Exception:
        alive = False
    if not alive:
        return "stale", state
    try:
        matches = deps.process_matches(state.pid, state.argv)
    except Exception:
        matches = False
    if not matches:
        return "unowned", state
    return ("expired", state) if _utc_now(deps) >= state.expires_at else ("owned", state)


def _validated_state(payload: object) -> _OwnedState | None:
    if not isinstance(payload, Mapping):
        return None
    if set(payload) != {
        "schema_version",
        "pid",
        "public_url",
        "origin",
        "argv",
        "started_at",
        "expires_at",
    }:
        return None
    if payload.get("schema_version") != _STATE_SCHEMA_VERSION:
        return None
    pid = payload.get("pid")
    public_url = payload.get("public_url")
    argv = payload.get("argv")
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 1:
        return None
    if not isinstance(public_url, str) or not _is_canonical_quick_tunnel_url(public_url):
        return None
    if payload.get("origin") != LOCAL_DASHBOARD_URL:
        return None
    if not isinstance(argv, list) or not argv or not all(isinstance(row, str) for row in argv):
        return None
    started_at = _parse_timestamp(payload.get("started_at"))
    expires_at = _parse_timestamp(payload.get("expires_at"))
    if started_at is None or expires_at is None or expires_at <= started_at:
        return None
    lifetime = expires_at - started_at
    if lifetime < timedelta(minutes=_MIN_MAX_LIFETIME_MINUTES) or lifetime > timedelta(
        minutes=_MAX_MAX_LIFETIME_MINUTES
    ):
        return None
    return _OwnedState(
        pid=pid,
        public_url=public_url,
        argv=tuple(argv),
        started_at=started_at,
        expires_at=expires_at,
    )


def _is_canonical_quick_tunnel_url(value: str) -> bool:
    if not value.startswith("https://") or value != value.lower():
        return False
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return bool(
        parsed.scheme == "https"
        and parsed.username is None
        and parsed.password is None
        and parsed.port is None
        and parsed.hostname is not None
        and _QUICK_TUNNEL_HOST_RE.fullmatch(parsed.hostname)
        and parsed.path == ""
        and parsed.query == ""
        and parsed.fragment == ""
        and value == f"https://{parsed.hostname}"
    )


def _poll_tunnel_url(deps: _PublicAccessDependencies, pid: int) -> str | None:
    for attempt in range(_URL_POLL_ATTEMPTS):
        public_url = extract_quick_tunnel_url(_read_bounded_log(deps.log_path))
        if public_url is not None:
            return public_url
        try:
            if not deps.process_alive(pid):
                return None
        except Exception:
            return None
        if attempt + 1 < _URL_POLL_ATTEMPTS:
            deps.sleep(_URL_POLL_SECONDS)
    return None


def _poll_tunnel_registration(
    deps: _PublicAccessDependencies,
    pid: int,
    argv: tuple[str, ...],
) -> bool:
    """Wait until cloudflared confirms an edge connection, not merely a URL."""

    for attempt in range(_REGISTRATION_POLL_ATTEMPTS):
        if b"Registered tunnel connection" in (
            _read_regular_file(deps.log_path, _MAX_LOG_BYTES) or b""
        ):
            return True
        if not _owned_live_process(deps, pid, argv):
            return False
        if attempt + 1 < _REGISTRATION_POLL_ATTEMPTS:
            deps.sleep(_REGISTRATION_POLL_SECONDS)
    return False


def _poll_public_dashboard(
    deps: _PublicAccessDependencies,
    pid: int,
    argv: tuple[str, ...],
    public_url: str,
) -> bool:
    """Require the issued URL to serve the trusted dashboard before publishing it."""

    for attempt in range(_PUBLIC_PROBE_ATTEMPTS):
        if not _owned_live_process(deps, pid, argv):
            return False
        try:
            if deps.public_http_ready(public_url, _PUBLIC_PROBE_TIMEOUT_SECONDS):
                return True
        except Exception:
            pass
        if attempt + 1 < _PUBLIC_PROBE_ATTEMPTS:
            deps.sleep(_PUBLIC_PROBE_SECONDS)
    return False


def _configured_cloudflared_path(deps: _PublicAccessDependencies) -> Path | None:
    for path in deps.config_paths:
        try:
            if deps.path_exists(path):
                return path
        except Exception:
            # An unreadable/indeterminate config location is unsafe too.
            return path
    return None


def _configured_max_lifetime(
    deps: _PublicAccessDependencies,
) -> timedelta | None:
    raw = str(deps.environ.get(PUBLIC_MAX_LIFETIME_ENV, "")).strip()
    if not raw:
        return _DEFAULT_MAX_LIFETIME
    try:
        minutes = int(raw)
    except ValueError:
        return None
    if not _MIN_MAX_LIFETIME_MINUTES <= minutes <= _MAX_MAX_LIFETIME_MINUTES:
        return None
    return timedelta(minutes=minutes)


def _read_state(path: Path) -> object | None:
    raw = _read_regular_file(path, _MAX_STATE_BYTES)
    if raw is None:
        return None
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None


def _read_bounded_log(path: Path) -> str:
    raw = _read_regular_file(path, _MAX_LOG_BYTES)
    if raw is None:
        return ""
    return raw.decode("utf-8", errors="replace")


def _read_regular_file(path: Path, maximum: int) -> bytes | None:
    try:
        metadata = path.lstat()
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or metadata.st_mode & 0o077
            or metadata.st_size > maximum
        ):
            return None
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        try:
            opened = os.fstat(descriptor)
            if (
                not stat.S_ISREG(opened.st_mode)
                or opened.st_uid != os.geteuid()
                or opened.st_mode & 0o077
                or opened.st_size > maximum
            ):
                return None
            payload = os.read(descriptor, maximum + 1)
            return payload if len(payload) <= maximum else None
        finally:
            os.close(descriptor)
    except OSError:
        return None


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _prepare_private_log(path: Path) -> None:
    _ensure_private_parent(path.parent)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise OSError("public-access log is not a regular file")
        os.fchmod(descriptor, 0o600)
    finally:
        os.close(descriptor)


@contextmanager
def _operation_lock(state_path: Path) -> Iterator[bool]:
    """Hold one non-blocking, private advisory lock for a mutation."""

    lock_path = state_path.with_name(".public_access.lock")
    _ensure_private_parent(lock_path.parent)
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(lock_path, flags, 0o600)
    acquired = False
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise OSError("public-access lock is not a regular file")
        os.fchmod(descriptor, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        acquired = True
        yield True
    finally:
        if acquired:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _atomic_write_state(path: Path, payload: Mapping[str, object]) -> None:
    _ensure_private_parent(path.parent)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        encoded = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode(
            "utf-8"
        )
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            descriptor = -1
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600, follow_symlinks=False)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _ensure_private_parent(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    metadata = path.lstat()
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or metadata.st_uid != os.geteuid()
    ):
        raise OSError("public-access runtime path is not a private directory")
    os.chmod(path, 0o700, follow_symlinks=False)


def _remove_state(path: Path) -> None:
    _remove_regular_file(path)


def _remove_log(path: Path) -> None:
    _remove_regular_file(path)


def _remove_regular_file(path: Path) -> None:
    try:
        metadata = path.lstat()
        if stat.S_ISREG(metadata.st_mode):
            path.unlink()
    except OSError:
        pass


def _path_lexists(path: Path) -> bool:
    try:
        path.lstat()
        return True
    except OSError:
        return False


def _dashboard_ready(deps: _PublicAccessDependencies) -> bool:
    try:
        return deps.http_status(LOCAL_DASHBOARD_URL, 2.0) == 200
    except Exception:
        return False


def _spawn(argv: tuple[str, ...]) -> _SpawnedChild:
    process = subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        env=_sanitized_child_environment(os.environ),
        shell=False,
        start_new_session=True,
    )
    return _SpawnedChild(
        pid=process.pid,
        is_running=lambda: process.poll() is None,
        stop=lambda: _terminate_spawned_process(process),
    )


def _sanitized_child_environment(source: Mapping[str, str]) -> dict[str, str]:
    """Drop tunnel credentials and behavior overrides from the child."""

    return {
        key: value
        for key, value in source.items()
        if key in _SAFE_CHILD_ENV_KEYS and isinstance(value, str)
    }


def _process_alive(pid: int) -> bool:
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 1:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _process_matches(pid: int, argv: tuple[str, ...]) -> bool:
    if not _process_alive(pid):
        return False
    proc_cmdline = Path(f"/proc/{pid}/cmdline")
    try:
        raw = proc_cmdline.read_bytes()
    except OSError:
        raw = b""
    if raw:
        try:
            actual = tuple(
                part.decode("utf-8") for part in raw.rstrip(b"\0").split(b"\0")
            )
        except UnicodeDecodeError:
            return False
        return actual == argv
    if sys.platform == "darwin":
        actual = _darwin_process_argv(pid)
        return actual == argv
    if any(any(character.isspace() for character in argument) for argument in argv):
        return False
    try:
        completed = subprocess.run(
            ("ps", "-ww", "-p", str(pid), "-o", "command="),
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0 and completed.stdout.strip() == " ".join(argv)


def _darwin_process_argv(pid: int) -> tuple[str, ...] | None:
    """Read exact argv through Darwin's KERN_PROCARGS2 sysctl."""

    library_name = ctypes.util.find_library("c")
    if not library_name:
        return None
    try:
        libc = ctypes.CDLL(library_name, use_errno=True)
        sysctl = libc.sysctl
        sysctl.argtypes = (
            ctypes.POINTER(ctypes.c_int),
            ctypes.c_uint,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_size_t),
            ctypes.c_void_p,
            ctypes.c_size_t,
        )
        sysctl.restype = ctypes.c_int
        mib = (ctypes.c_int * 3)(1, 49, pid)  # CTL_KERN, KERN_PROCARGS2, pid
        size = ctypes.c_size_t()
        if sysctl(mib, 3, None, ctypes.byref(size), None, 0) != 0:
            return None
        if size.value < struct.calcsize("i") or size.value > _MAX_STATE_BYTES:
            return None
        buffer = ctypes.create_string_buffer(size.value)
        if sysctl(mib, 3, buffer, ctypes.byref(size), None, 0) != 0:
            return None
        data = buffer.raw[: size.value]
        argument_count = struct.unpack_from("i", data)[0]
        if argument_count <= 0 or argument_count > 128:
            return None
        position = struct.calcsize("i")
        executable_end = data.find(b"\0", position)
        if executable_end < 0:
            return None
        position = executable_end + 1
        while position < len(data) and data[position] == 0:
            position += 1
        arguments: list[str] = []
        while len(arguments) < argument_count and position < len(data):
            argument_end = data.find(b"\0", position)
            if argument_end < 0:
                return None
            arguments.append(data[position:argument_end].decode("utf-8"))
            position = argument_end + 1
        return tuple(arguments) if len(arguments) == argument_count else None
    except (AttributeError, OSError, UnicodeDecodeError, ValueError):
        return None


def _terminate_process_group(pid: int) -> bool:
    try:
        os.killpg(pid, signal.SIGTERM)
    except (OSError, ValueError):
        return False
    for _ in range(30):
        if not _process_alive(pid):
            return True
        time.sleep(0.1)
    try:
        os.killpg(pid, signal.SIGKILL)
    except (OSError, ValueError):
        return False
    for _ in range(20):
        if not _process_alive(pid):
            return True
        time.sleep(0.1)
    return not _process_alive(pid)


def _owned_live_process(
    deps: _PublicAccessDependencies,
    pid: int,
    argv: tuple[str, ...],
) -> bool:
    try:
        return deps.process_alive(pid) and deps.process_matches(pid, argv)
    except Exception:
        return False


def _cleanup_spawned_child(child: _SpawnedChild) -> bool:
    """Roll back the exact Popen child retained by this enable invocation."""

    try:
        if not child.is_running():
            return True
        return bool(child.stop()) and not child.is_running()
    except Exception:
        return False


def _terminate_spawned_process(process: subprocess.Popen[bytes]) -> bool:
    """Stop and reap the exact newly spawned process group through its Popen handle."""

    if process.poll() is not None:
        return True
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=2)
        except (OSError, subprocess.SubprocessError):
            return False
    except (OSError, subprocess.SubprocessError):
        return process.poll() is not None
    return process.poll() is not None


def _local_http_status(url: str, timeout: float) -> int:
    if url != LOCAL_DASHBOARD_URL:
        raise ValueError("unsupported dashboard URL")
    connection = http.client.HTTPConnection("127.0.0.1", 8765, timeout=timeout)
    try:
        connection.request(
            "GET",
            "/",
            headers={"User-Agent": "crypto-rsi-scanner-dashboard-readiness/1"},
        )
        response = connection.getresponse()
        body_prefix = response.read(_PUBLIC_BODY_PREFIX_BYTES)
        return response.status if _response_is_dashboard(response, body_prefix) else 0
    finally:
        connection.close()


def _public_dashboard_ready(url: str, timeout: float) -> bool:
    """Verify that a canonical public URL resolves to this dashboard, not an edge error."""

    if not _is_canonical_quick_tunnel_url(url):
        return False
    hostname = urlsplit(url).hostname
    if hostname is None:
        return False
    connection = http.client.HTTPSConnection(hostname, 443, timeout=timeout)
    try:
        connection.request(
            "GET",
            "/",
            headers={"User-Agent": "crypto-rsi-scanner-dashboard-readiness/1"},
        )
        response = connection.getresponse()
        body_prefix = response.read(_PUBLIC_BODY_PREFIX_BYTES)
        return _response_is_dashboard(response, body_prefix)
    finally:
        connection.close()


def _response_is_dashboard(
    response: http.client.HTTPResponse,
    body_prefix: bytes,
) -> bool:
    return bool(
        response.status == 200
        and response.getheader("X-Robots-Tag") == "noindex, nofollow, noarchive"
        and "no-store" in (response.getheader("Cache-Control") or "").casefold()
        and (response.getheader("X-Content-Type-Options") or "").casefold()
        == "nosniff"
        and (response.getheader("Content-Type") or "")
        .casefold()
        .startswith("text/html")
        and _PUBLIC_BODY_MARKER in body_prefix
    )


def _utc_now(deps: _PublicAccessDependencies) -> datetime:
    value = deps.now()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None


def _first_reason(status: _PublicAccessStatus) -> str:
    return status.blockers[0] if status.blockers else "unsafe_state"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Guard temporary anonymous public access to the loopback radar dashboard."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("readiness")
    subparsers.add_parser("status")
    for command in ("enable", "disable", "guard"):
        mutation = subparsers.add_parser(command)
        mutation.add_argument("--confirm", action="store_true")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    dependencies: _PublicAccessDependencies | None = None,
) -> int:
    args = _parser().parse_args(argv)
    deps = dependencies or _PublicAccessDependencies()
    if args.command in {"readiness", "status"}:
        status = inspect_public_access(deps)
        print(
            _format_status(args.command, status),
            file=sys.stdout if status.ready else sys.stderr,
        )
        return 0 if status.ready else 1
    if args.command == "enable":
        operation = enable_public_access(confirm=args.confirm, dependencies=deps)
    elif args.command == "disable":
        operation = disable_public_access(confirm=args.confirm, dependencies=deps)
    else:
        operation = guard_public_access(confirm=args.confirm, dependencies=deps)
    print(
        _format_operation(args.command, operation),
        file=sys.stdout if operation.ok else sys.stderr,
    )
    return 0 if operation.ok else 1


def _format_status(command: str, status: _PublicAccessStatus) -> str:
    prefix = f"radar_dashboard_public_access_{command}:"
    operator = (
        " implications=temporary_unauthenticated_public_https_link"
        " next_safe_command='make radar-dashboard-public-readiness PYTHON=.venv/bin/python'"
        " authorization_boundary=explicit_confirmation_no_provider_credentials"
        " expected_provider_activity=cloudflare_tunnel_edge_only_no_market_provider"
        " enable_command='CONFIRM=1 make radar-dashboard-public-enable PYTHON=.venv/bin/python'"
        " rollback_disable_command='CONFIRM=1 make radar-dashboard-public-disable PYTHON=.venv/bin/python'"
    )
    if not status.ready:
        detail = f" process_state={status.process_state}"
        if status.process_state == "expired":
            detail += (
                " tunnel_may_still_be_public=true"
                " next_safe_action=confirmed_public_guard"
            )
        return f"{prefix} NOT_READY reason={_first_reason(status)}{detail}{operator}"
    state = "enabled" if status.enabled else "disabled"
    if command == "readiness" and status.enabled:
        url = "redacted_use_status"
    else:
        url = status.public_url if status.enabled else "available_after_confirmed_enable"
    expiry = status.expires_at or "none"
    return f"{prefix} READY state={state} url={url} expires_at={expiry}{operator}"


def _format_operation(command: str, operation: _PublicAccessOperation) -> str:
    prefix = f"radar_dashboard_public_access_{command}:"
    if not operation.ok:
        return f"{prefix} BLOCKED reason={operation.reason or 'unsafe_state'}"
    state = "ENABLED" if command == "enable" else "GUARDED" if command == "guard" else "DISABLED"
    changed = "yes" if operation.changed else "no"
    public_url = (
        operation.status.public_url
        if command == "enable" and operation.status is not None
        else None
    )
    url = public_url or "none"
    expiry = operation.status.expires_at if operation.status is not None else None
    return f"{prefix} {state} changed={changed} url={url} expires_at={expiry or 'none'}"


__all__ = (
    "CLOUDFLARED_BINARY_ENV",
    "LOCAL_DASHBOARD_URL",
    "PUBLIC_MAX_LIFETIME_ENV",
    "disable_public_access",
    "discover_cloudflared_binary",
    "enable_public_access",
    "extract_quick_tunnel_url",
    "guard_public_access",
    "inspect_public_access",
    "main",
)


if __name__ == "__main__":
    raise SystemExit(main())
