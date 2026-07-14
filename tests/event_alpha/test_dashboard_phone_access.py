"""Guarded private phone-access regressions for the radar dashboard."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from crypto_rsi_scanner.event_alpha.dashboard import phone_access
from crypto_rsi_scanner.event_alpha.dashboard.phone_access import (
    LOCAL_DASHBOARD_URL,
    TAILSCALE_BINARY_ENV,
    disable_phone_access,
    discover_tailscale_binary,
    enable_phone_access,
    expected_serve_config,
    inspect_phone_access,
    main,
)


_BINARY = "/safe/tailscale"
_DNS = "radar-device.tail123.ts.net"
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _status_json(
    *,
    backend: str = "Running",
    online: object = True,
    dns_name: object = f"{_DNS}.",
) -> str:
    return json.dumps(
        {
            "BackendState": backend,
            "Self": {
                "Online": online,
                "DNSName": dns_name,
                "HostName": "private-host-must-not-print",
                "UserID": 12345,
            },
            "Peer": {"secret-node-key": {"UserID": 67890}},
        }
    )


class _FakeBoundaries:
    def __init__(
        self,
        *,
        serve: object | None = None,
        funnel: object | None = None,
        status_text: str | None = None,
        http_status: int = 200,
    ) -> None:
        self.serve = {} if serve is None else serve
        self.funnel = {} if funnel is None else funnel
        self.status_text = status_text or _status_json()
        self.local_status = http_status
        self.commands: list[tuple[str, ...]] = []
        self.http_calls: list[tuple[str, float]] = []
        self.fail_mutation = False

    def run(self, argv: tuple[str, ...]) -> phone_access._CommandResult:
        self.commands.append(argv)
        if argv == (_BINARY, "status", "--json"):
            return phone_access._CommandResult(0, self.status_text)
        if argv == (_BINARY, "serve", "status", "--json"):
            return phone_access._CommandResult(0, json.dumps(self.serve))
        if argv == (_BINARY, "funnel", "status", "--json"):
            return phone_access._CommandResult(0, json.dumps(self.funnel))
        if argv == (
            _BINARY,
            "serve",
            "--bg",
            "--https=443",
            "--yes",
            LOCAL_DASHBOARD_URL,
        ):
            if self.fail_mutation:
                return phone_access._CommandResult(1, "sensitive failure")
            self.serve = expected_serve_config(_DNS)
            return phone_access._CommandResult(0, "sensitive node metadata")
        if argv == (_BINARY, "serve", "--https=443", "off"):
            if self.fail_mutation:
                return phone_access._CommandResult(1, "sensitive failure")
            self.serve = {}
            self.funnel = {}
            return phone_access._CommandResult(0, "sensitive node metadata")
        raise AssertionError(f"unexpected command shape: {argv!r}")

    def http(self, url: str, timeout: float) -> int:
        self.http_calls.append((url, timeout))
        return self.local_status

    def dependencies(self) -> phone_access._PhoneAccessDependencies:
        return phone_access._PhoneAccessDependencies(
            environ={TAILSCALE_BINARY_ENV: _BINARY},
            which=lambda _name: "/path/tailscale",
            is_executable=lambda value: value == _BINARY,
            run=self.run,
            http_status=self.http,
        )


def test_binary_discovery_prefers_explicit_then_path_then_app_bundle() -> None:
    explicit = phone_access._PhoneAccessDependencies(
        environ={TAILSCALE_BINARY_ENV: "/explicit/tailscale"},
        which=lambda _name: "/path/tailscale",
        is_executable=lambda _value: True,
    )
    assert discover_tailscale_binary(explicit) == "/explicit/tailscale"

    path = phone_access._PhoneAccessDependencies(
        environ={},
        which=lambda _name: "/path/tailscale",
        is_executable=lambda value: value == "/path/tailscale",
    )
    assert discover_tailscale_binary(path) == "/path/tailscale"

    app = phone_access._PhoneAccessDependencies(
        environ={},
        which=lambda _name: None,
        is_executable=lambda value: value == phone_access.TAILSCALE_APP_BINARY,
    )
    assert discover_tailscale_binary(app) == phone_access.TAILSCALE_APP_BINARY


def test_readiness_is_read_only_and_accepts_empty_serve_config() -> None:
    fake = _FakeBoundaries()

    result = inspect_phone_access(fake.dependencies())

    assert result.ready is True
    assert result.enabled is False
    assert result.serve_state == "empty"
    assert result.funnel_state == "off"
    assert result.phone_url == f"https://{_DNS}/"
    assert fake.http_calls == [(LOCAL_DASHBOARD_URL, 2.0)]
    assert fake.commands == [
        (_BINARY, "status", "--json"),
        (_BINARY, "serve", "status", "--json"),
        (_BINARY, "funnel", "status", "--json"),
    ]


def test_status_accepts_only_the_exact_owned_proxy() -> None:
    owned = expected_serve_config(_DNS)
    fake = _FakeBoundaries(serve=owned, funnel=owned)

    result = inspect_phone_access(fake.dependencies())

    assert result.ready is True
    assert result.enabled is True
    assert result.serve_state == "owned"
    assert result.funnel_state == "off"


@pytest.mark.parametrize(
    ("fake", "blocker"),
    [
        (_FakeBoundaries(http_status=503), "local_dashboard_unavailable"),
        (_FakeBoundaries(status_text=_status_json(backend="Stopped")), "tailscale_not_running"),
        (_FakeBoundaries(status_text=_status_json(online=False)), "tailscale_self_offline"),
        (_FakeBoundaries(status_text=_status_json(dns_name="not-a-ts-domain.example")), "tailscale_dns_invalid"),
        (_FakeBoundaries(serve={"TCP": {"80": {"HTTP": True}}}), "serve_config_conflict"),
        (
            _FakeBoundaries(
                serve={
                    **expected_serve_config(_DNS),
                    "AllowFunnel": {f"{_DNS}:443": True},
                },
                funnel={"AllowFunnel": {f"{_DNS}:443": True}},
            ),
            "serve_config_conflict",
        ),
    ],
)
def test_readiness_fails_closed_for_unready_or_conflicting_state(
    fake: _FakeBoundaries,
    blocker: str,
) -> None:
    result = inspect_phone_access(fake.dependencies())

    assert result.ready is False
    assert blocker in result.blockers


def test_readiness_refuses_configured_funnel_even_with_empty_serve_status() -> None:
    fake = _FakeBoundaries(
        funnel={"AllowFunnel": {f"{_DNS}:443": True}},
    )

    result = inspect_phone_access(fake.dependencies())

    assert result.ready is False
    assert result.funnel_state == "configured"
    assert "funnel_configured" in result.blockers


def test_enable_requires_confirm_without_inspecting_or_mutating() -> None:
    fake = _FakeBoundaries()

    result = enable_phone_access(confirm=False, dependencies=fake.dependencies())

    assert result.ok is False
    assert result.reason == "confirmation_required"
    assert fake.commands == []
    assert fake.http_calls == []


def test_enable_invokes_only_exact_private_serve_command_and_verifies() -> None:
    fake = _FakeBoundaries()

    result = enable_phone_access(confirm=True, dependencies=fake.dependencies())

    assert result.ok is True
    assert result.changed is True
    assert result.status is not None and result.status.enabled is True
    mutation_commands = [row for row in fake.commands if "status" not in row]
    assert mutation_commands == [
        (
            _BINARY,
            "serve",
            "--bg",
            "--https=443",
            "--yes",
            LOCAL_DASHBOARD_URL,
        )
    ]
    assert all("funnel" not in row[:2] for row in mutation_commands)


def test_enable_is_idempotent_for_exact_owned_config() -> None:
    owned = expected_serve_config(_DNS)
    fake = _FakeBoundaries(serve=owned, funnel=owned)

    result = enable_phone_access(confirm=True, dependencies=fake.dependencies())

    assert result.ok is True
    assert result.changed is False
    assert all("--bg" not in row for row in fake.commands)


def test_enable_refuses_any_non_owned_nonempty_config() -> None:
    fake = _FakeBoundaries(serve={"Web": {"other.ts.net:443": {}}})

    result = enable_phone_access(confirm=True, dependencies=fake.dependencies())

    assert result.ok is False
    assert result.reason == "serve_config_conflict"
    assert all("--bg" not in row for row in fake.commands)


def test_disable_requires_confirm_and_never_resets() -> None:
    owned = expected_serve_config(_DNS)
    fake = _FakeBoundaries(serve=owned, funnel=owned)

    unconfirmed = disable_phone_access(confirm=False, dependencies=fake.dependencies())
    confirmed = disable_phone_access(confirm=True, dependencies=fake.dependencies())

    assert unconfirmed.reason == "confirmation_required"
    assert confirmed.ok is True
    assert confirmed.changed is True
    mutations = [row for row in fake.commands if "status" not in row]
    assert mutations == [(_BINARY, "serve", "--https=443", "off")]
    assert all("reset" not in row for row in fake.commands)


def test_disable_refuses_conflict_and_preserves_unrelated_config() -> None:
    conflict = {"TCP": {"8443": {"HTTPS": True}}}
    fake = _FakeBoundaries(serve=conflict)

    result = disable_phone_access(confirm=True, dependencies=fake.dependencies())

    assert result.ok is False
    assert result.changed is False
    assert fake.serve == conflict
    assert all("off" not in row for row in fake.commands)


def test_disable_can_remove_exact_owned_route_when_local_dashboard_is_down() -> None:
    owned = expected_serve_config(_DNS)
    fake = _FakeBoundaries(serve=owned, funnel=owned, http_status=503)

    result = disable_phone_access(confirm=True, dependencies=fake.dependencies())

    assert result.ok is True
    assert result.changed is True
    assert fake.serve == {}


def test_failed_mutation_is_generic_and_does_not_leak_command_output(capsys) -> None:
    fake = _FakeBoundaries()
    fake.fail_mutation = True

    result = main(["enable", "--confirm"], dependencies=fake.dependencies())
    output = capsys.readouterr()

    assert result == 1
    assert "enable_command_failed" in output.err
    assert "sensitive failure" not in output.err
    assert output.out == ""


def test_cli_status_is_concise_and_never_dumps_node_or_user_metadata(capsys) -> None:
    fake = _FakeBoundaries(serve=expected_serve_config(_DNS))

    result = main(["status"], dependencies=fake.dependencies())
    output = capsys.readouterr()

    assert result == 0
    assert f"url=https://{_DNS}/" in output.out
    assert "private-host-must-not-print" not in output.out
    assert "UserID" not in output.out
    assert "secret-node-key" not in output.out
    assert "BackendState" not in output.out
    assert output.err == ""


def test_invalid_or_duplicate_status_json_fails_closed_without_echoing_payload(capsys) -> None:
    duplicate = '{"BackendState":"Running","BackendState":"Stopped","Self":{}}'
    fake = _FakeBoundaries(status_text=duplicate)

    result = main(["readiness"], dependencies=fake.dependencies())
    output = capsys.readouterr()

    assert result == 1
    assert "tailscale_status_unavailable" in output.err
    assert duplicate not in output.err
    assert output.out == ""


def test_make_targets_propagate_confirmation_only_when_explicit() -> None:
    def dry_run(target: str, *assignments: str) -> str:
        completed = subprocess.run(
            ["make", "-n", target, "PYTHON=python3", *assignments],
            cwd=_REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout

    readiness = dry_run("radar-dashboard-phone-readiness")
    status = dry_run("radar-dashboard-phone-status")
    enable_without_confirm = dry_run("radar-dashboard-phone-enable")
    enable_with_confirm = dry_run("radar-dashboard-phone-enable", "CONFIRM=1")
    disable_with_confirm = dry_run("radar-dashboard-phone-disable", "CONFIRM=1")

    assert "dashboard.phone_access readiness" in readiness
    assert "dashboard.phone_access status" in status
    assert "--confirm" not in enable_without_confirm
    assert enable_with_confirm.count("--confirm") == 1
    assert disable_with_confirm.count("--confirm") == 1
    rendered = "\n".join(
        (readiness, status, enable_without_confirm, enable_with_confirm, disable_with_confirm)
    ).casefold()
    assert "0.0.0.0" not in rendered
    assert "funnel" not in rendered
    assert "serve reset" not in rendered
