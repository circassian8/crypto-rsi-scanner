"""Guarded Tailscale Serve access to the loopback-only radar dashboard."""

from __future__ import annotations

import argparse
import http.client
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Callable, Mapping, Sequence


LOCAL_DASHBOARD_URL = "http://127.0.0.1:8765"
TAILSCALE_BINARY_ENV = "RSI_RADAR_TAILSCALE_BIN"
TAILSCALE_APP_BINARY = "/Applications/Tailscale.app/Contents/MacOS/Tailscale"
_MAX_JSON_BYTES = 2 * 1024 * 1024
_DNS_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


@dataclass(frozen=True)
class _CommandResult:
    """Minimal, injectable subprocess result."""

    returncode: int
    stdout: str = ""


@dataclass(frozen=True)
class _PhoneAccessDependencies:
    """External boundaries used by phone-access checks and mutations."""

    environ: Mapping[str, str] = field(default_factory=lambda: os.environ)
    which: Callable[[str], str | None] = shutil.which
    is_executable: Callable[[str], bool] = lambda value: (
        Path(value).is_file() and os.access(value, os.X_OK)
    )
    run: Callable[[tuple[str, ...]], _CommandResult] = lambda argv: _run_command(argv)
    http_status: Callable[[str, float], int] = lambda url, timeout: _local_http_status(
        url, timeout
    )


@dataclass(frozen=True)
class _PhoneAccessStatus:
    """Secret-safe projection of local dashboard and Tailscale state."""

    ready: bool
    dashboard_ready: bool
    tailscale_found: bool
    backend_running: bool
    self_online: bool
    dns_name: str | None
    serve_state: str
    funnel_state: str
    blockers: tuple[str, ...]

    @property
    def enabled(self) -> bool:
        return self.ready and self.serve_state == "owned"

    @property
    def phone_url(self) -> str | None:
        return f"https://{self.dns_name}/" if self.dns_name else None


@dataclass(frozen=True)
class _PhoneAccessOperation:
    """Result of an explicitly confirmed enable or disable operation."""

    ok: bool
    changed: bool
    status: _PhoneAccessStatus | None
    reason: str | None = None


def discover_tailscale_binary(
    dependencies: _PhoneAccessDependencies | None = None,
) -> str | None:
    """Resolve an executable from the explicit override, PATH, then macOS app."""

    deps = dependencies or _PhoneAccessDependencies()
    candidates = (
        str(deps.environ.get(TAILSCALE_BINARY_ENV, "")).strip(),
        str(deps.which("tailscale") or "").strip(),
        TAILSCALE_APP_BINARY,
    )
    return next((value for value in candidates if value and deps.is_executable(value)), None)


def expected_serve_config(dns_name: str) -> dict[str, object]:
    """Return the sole Serve config this helper owns."""

    host = dns_name.removesuffix(".").lower()
    return {
        "TCP": {"443": {"HTTPS": True}},
        "Web": {
            f"{host}:443": {
                "Handlers": {"/": {"Proxy": LOCAL_DASHBOARD_URL}},
            }
        },
    }


def inspect_phone_access(
    dependencies: _PhoneAccessDependencies | None = None,
) -> _PhoneAccessStatus:
    """Read local/Tailscale state without writing config or dashboard artifacts."""

    status, _binary = _inspect_with_binary(dependencies or _PhoneAccessDependencies())
    return status


def enable_phone_access(
    *,
    confirm: bool,
    dependencies: _PhoneAccessDependencies | None = None,
) -> _PhoneAccessOperation:
    """Enable only the exact private tailnet proxy after explicit confirmation."""

    if not confirm:
        return _PhoneAccessOperation(False, False, None, "confirmation_required")
    deps = dependencies or _PhoneAccessDependencies()
    before, binary = _inspect_with_binary(deps)
    if not before.ready or binary is None:
        return _PhoneAccessOperation(False, False, before, _first_reason(before))
    if before.serve_state == "owned":
        return _PhoneAccessOperation(True, False, before)
    command = (
        binary,
        "serve",
        "--bg",
        "--https=443",
        "--yes",
        LOCAL_DASHBOARD_URL,
    )
    if not _command_succeeded(deps, command):
        return _PhoneAccessOperation(False, False, before, "enable_command_failed")
    after, _ = _inspect_with_binary(deps)
    if not after.enabled:
        return _PhoneAccessOperation(False, True, after, "post_enable_verification_failed")
    return _PhoneAccessOperation(True, True, after)


def disable_phone_access(
    *,
    confirm: bool,
    dependencies: _PhoneAccessDependencies | None = None,
) -> _PhoneAccessOperation:
    """Remove port 443 only when the complete config is exactly helper-owned."""

    if not confirm:
        return _PhoneAccessOperation(False, False, None, "confirmation_required")
    deps = dependencies or _PhoneAccessDependencies()
    before, binary = _inspect_with_binary(deps)
    if binary is None:
        return _PhoneAccessOperation(False, False, before, "tailscale_binary_missing")
    if before.serve_state == "empty" and _disable_prerequisites(before):
        return _PhoneAccessOperation(True, False, before)
    if before.serve_state != "owned" or not _disable_prerequisites(before):
        return _PhoneAccessOperation(False, False, before, _first_reason(before))
    if not _command_succeeded(deps, (binary, "serve", "--https=443", "off")):
        return _PhoneAccessOperation(False, False, before, "disable_command_failed")
    after, _ = _inspect_with_binary(deps)
    if after.serve_state != "empty" or not _disable_prerequisites(after):
        return _PhoneAccessOperation(False, True, after, "post_disable_verification_failed")
    return _PhoneAccessOperation(True, True, after)


def _inspect_with_binary(
    deps: _PhoneAccessDependencies,
) -> tuple[_PhoneAccessStatus, str | None]:
    blockers: list[str] = []
    dashboard_ready = _dashboard_ready(deps)
    if not dashboard_ready:
        blockers.append("local_dashboard_unavailable")
    binary = discover_tailscale_binary(deps)
    if binary is None:
        blockers.append("tailscale_binary_missing")
        return _status(False, False, None, "unavailable", "unavailable", blockers), None
    raw_status = _command_json(deps, (binary, "status", "--json"))
    backend_running, self_online, dns_name = _status_values(raw_status)
    _append_status_blockers(blockers, raw_status, backend_running, self_online, dns_name)
    serve_config = _command_json(deps, (binary, "serve", "status", "--json"))
    serve_state = _serve_state(serve_config, dns_name)
    if serve_state in {"unavailable", "conflict"}:
        blockers.append(f"serve_config_{serve_state}")
    funnel_config = _command_json(deps, (binary, "funnel", "status", "--json"))
    funnel_state = _funnel_state(funnel_config, serve_config)
    if funnel_state != "off":
        blockers.append(f"funnel_{funnel_state}")
    result = _PhoneAccessStatus(
        ready=not blockers,
        dashboard_ready=dashboard_ready,
        tailscale_found=True,
        backend_running=backend_running,
        self_online=self_online,
        dns_name=dns_name,
        serve_state=serve_state,
        funnel_state=funnel_state,
        blockers=tuple(blockers),
    )
    return result, binary


def _status(
    backend_running: bool,
    self_online: bool,
    dns_name: str | None,
    serve_state: str,
    funnel_state: str,
    blockers: list[str],
) -> _PhoneAccessStatus:
    return _PhoneAccessStatus(
        ready=False,
        dashboard_ready="local_dashboard_unavailable" not in blockers,
        tailscale_found=False,
        backend_running=backend_running,
        self_online=self_online,
        dns_name=dns_name,
        serve_state=serve_state,
        funnel_state=funnel_state,
        blockers=tuple(blockers),
    )


def _status_values(payload: object) -> tuple[bool, bool, str | None]:
    if not isinstance(payload, Mapping):
        return False, False, None
    own = payload.get("Self")
    own_map = own if isinstance(own, Mapping) else {}
    dns_name = _valid_dns_name(own_map.get("DNSName"))
    return payload.get("BackendState") == "Running", own_map.get("Online") is True, dns_name


def _append_status_blockers(
    blockers: list[str],
    payload: object,
    backend_running: bool,
    self_online: bool,
    dns_name: str | None,
) -> None:
    if payload is None:
        blockers.append("tailscale_status_unavailable")
        return
    if not backend_running:
        blockers.append("tailscale_not_running")
    if not self_online:
        blockers.append("tailscale_self_offline")
    if dns_name is None:
        blockers.append("tailscale_dns_invalid")


def _serve_state(payload: object, dns_name: str | None) -> str:
    if payload is None:
        return "unavailable"
    if payload == {}:
        return "empty"
    if dns_name and payload == expected_serve_config(dns_name):
        return "owned"
    return "conflict"


def _funnel_state(payload: object, serve_config: object) -> str:
    if payload is None:
        return "unavailable"
    if payload == {}:
        return "off"
    if payload == serve_config and isinstance(payload, Mapping):
        allow = payload.get("AllowFunnel")
        if allow in (None, {}):
            return "off"
    if isinstance(payload, Mapping) and _mapping_contains_enabled_funnel(payload):
        return "configured"
    return "unrecognized"


def _mapping_contains_enabled_funnel(payload: Mapping[object, object]) -> bool:
    allow = payload.get("AllowFunnel")
    return isinstance(allow, Mapping) and any(value is True for value in allow.values())


def _valid_dns_name(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    name = value.strip().removesuffix(".").lower()
    if len(name) > 253 or not name.endswith(".ts.net"):
        return None
    labels = name.split(".")
    if len(labels) < 3 or any(not _DNS_LABEL_RE.fullmatch(label) for label in labels):
        return None
    return name


def _dashboard_ready(deps: _PhoneAccessDependencies) -> bool:
    try:
        return deps.http_status(LOCAL_DASHBOARD_URL, 2.0) == 200
    except Exception:
        return False


def _command_json(deps: _PhoneAccessDependencies, argv: tuple[str, ...]) -> object:
    result = _invoke(deps, argv)
    if result is None or result.returncode != 0:
        return None
    text = result.stdout.strip()
    if not text or len(text.encode("utf-8")) > _MAX_JSON_BYTES:
        return None
    try:
        parsed = json.loads(text, object_pairs_hook=_unique_object)
    except (json.JSONDecodeError, UnicodeError, ValueError):
        return None
    return {} if parsed is None else parsed


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _invoke(
    deps: _PhoneAccessDependencies,
    argv: tuple[str, ...],
) -> _CommandResult | None:
    try:
        return deps.run(argv)
    except Exception:
        return None


def _command_succeeded(deps: _PhoneAccessDependencies, argv: tuple[str, ...]) -> bool:
    result = _invoke(deps, argv)
    return result is not None and result.returncode == 0


def _run_command(argv: tuple[str, ...]) -> _CommandResult:
    completed = subprocess.run(
        argv,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return _CommandResult(returncode=completed.returncode, stdout=completed.stdout)


def _local_http_status(url: str, timeout: float) -> int:
    if url != LOCAL_DASHBOARD_URL:
        raise ValueError("unsupported dashboard URL")
    connection = http.client.HTTPConnection("127.0.0.1", 8765, timeout=timeout)
    try:
        connection.request("GET", "/")
        response = connection.getresponse()
        response.read(1)
        return response.status
    finally:
        connection.close()


def _disable_prerequisites(status: _PhoneAccessStatus) -> bool:
    ignored = {"local_dashboard_unavailable"}
    return not (set(status.blockers) - ignored)


def _first_reason(status: _PhoneAccessStatus) -> str:
    return status.blockers[0] if status.blockers else "unsafe_state"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Guard private phone access to the loopback-only radar dashboard."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("readiness")
    subparsers.add_parser("status")
    for command in ("enable", "disable"):
        mutation = subparsers.add_parser(command)
        mutation.add_argument("--confirm", action="store_true")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    dependencies: _PhoneAccessDependencies | None = None,
) -> int:
    args = _parser().parse_args(argv)
    deps = dependencies or _PhoneAccessDependencies()
    if args.command in {"readiness", "status"}:
        status = inspect_phone_access(deps)
        print(_format_status(args.command, status), file=sys.stdout if status.ready else sys.stderr)
        return 0 if status.ready else 1
    operation = (
        enable_phone_access(confirm=args.confirm, dependencies=deps)
        if args.command == "enable"
        else disable_phone_access(confirm=args.confirm, dependencies=deps)
    )
    print(_format_operation(args.command, operation), file=sys.stdout if operation.ok else sys.stderr)
    return 0 if operation.ok else 1


def _format_status(command: str, status: _PhoneAccessStatus) -> str:
    prefix = f"radar_dashboard_phone_access_{command}:"
    operator = (
        " implications=private_tailnet_https_to_loopback_dashboard"
        " next_safe_command='make radar-dashboard-phone-readiness PYTHON=.venv/bin/python'"
        " authorization_boundary=existing_tailnet_identity_plus_explicit_confirmation"
        " expected_provider_activity=none"
        " enable_command='CONFIRM=1 make radar-dashboard-phone-enable PYTHON=.venv/bin/python'"
        " rollback_disable_command='CONFIRM=1 make radar-dashboard-phone-disable PYTHON=.venv/bin/python'"
    )
    if not status.ready:
        return f"{prefix} NOT_READY reason={_first_reason(status)}{operator}"
    state = "enabled" if status.enabled else "disabled"
    url = status.phone_url if status.enabled else "available_after_enable"
    return (
        f"{prefix} READY state={state} url={url} "
        f"loopback_origin={LOCAL_DASHBOARD_URL}{operator}"
    )


def _format_operation(command: str, operation: _PhoneAccessOperation) -> str:
    prefix = f"radar_dashboard_phone_access_{command}:"
    if not operation.ok:
        return f"{prefix} BLOCKED reason={operation.reason or 'unsafe_state'}"
    state = "ENABLED" if command == "enable" else "DISABLED"
    url = operation.status.phone_url if command == "enable" and operation.status else "none"
    changed = "yes" if operation.changed else "no"
    return f"{prefix} {state} changed={changed} url={url} loopback_origin={LOCAL_DASHBOARD_URL}"


__all__ = (
    "LOCAL_DASHBOARD_URL",
    "TAILSCALE_BINARY_ENV",
    "disable_phone_access",
    "discover_tailscale_binary",
    "enable_phone_access",
    "expected_serve_config",
    "inspect_phone_access",
    "main",
)


if __name__ == "__main__":
    raise SystemExit(main())
