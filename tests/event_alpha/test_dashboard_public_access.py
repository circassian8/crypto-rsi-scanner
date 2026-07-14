"""Guarded public Cloudflare Quick Tunnel access for the radar dashboard."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
import subprocess

import pytest

from crypto_rsi_scanner.event_alpha.dashboard import public_access
from crypto_rsi_scanner.event_alpha.dashboard.public_access import (
    CLOUDFLARED_BINARY_ENV,
    LOCAL_DASHBOARD_URL,
    disable_public_access,
    discover_cloudflared_binary,
    enable_public_access,
    extract_quick_tunnel_url,
    inspect_public_access,
    main,
)


_BINARY = "/safe/cloudflared"
_PUBLIC_URL = "https://calm-river-123.trycloudflare.com"
_PID = 43121
_REPO_ROOT = Path(__file__).resolve().parents[2]


class _FakeResponse:
    def __init__(self, headers: dict[str, str] | None = None) -> None:
        self.status = 200
        self.headers = {
            "Cache-Control": "no-store",
            "Content-Type": "text/html; charset=utf-8",
            "X-Content-Type-Options": "nosniff",
            "X-Robots-Tag": "noindex, nofollow, noarchive",
            **(headers or {}),
        }

    def getheader(self, name: str) -> str | None:
        return self.headers.get(name)


class _FakeBoundaries:
    def __init__(
        self,
        root: Path,
        *,
        http_status: int = 200,
        local_identity: bool = True,
        public_ready: bool | list[bool] = True,
        binary_available: bool = True,
        log_text: str = (
            f"INF Quick Tunnel available at {_PUBLIC_URL}\n"
            "INF Registered tunnel connection\n"
        ),
    ) -> None:
        self.state_path = root / "public_access_state.json"
        self.log_path = root / "cloudflared.log"
        self.local_status = http_status
        self.local_identity = local_identity
        self.public_results = (
            list(public_ready) if isinstance(public_ready, list) else [public_ready]
        )
        self.binary_available = binary_available
        self.log_text = log_text
        self.http_calls: list[tuple[str, float]] = []
        self.public_http_calls: list[tuple[str, float]] = []
        self.spawned: list[tuple[str, ...]] = []
        self.terminated: list[int] = []
        self.sleeps: list[float] = []
        self.alive: dict[int, bool] = {}
        self.process_commands: dict[int, tuple[str, ...]] = {}
        self.fail_terminate = False

    @property
    def expected_command(self) -> tuple[str, ...]:
        return (
            _BINARY,
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
            str(self.log_path),
        )

    def http(self, url: str, timeout: float) -> int:
        self.http_calls.append((url, timeout))
        return self.local_status if self.local_identity else 0

    def spawn(self, argv: tuple[str, ...]) -> public_access._SpawnedChild:
        self.spawned.append(argv)
        self.log_path.write_text(self.log_text, encoding="utf-8")
        self.alive[_PID] = True
        self.process_commands[_PID] = argv
        return public_access._SpawnedChild(
            pid=_PID,
            is_running=lambda: self.process_alive(_PID),
            stop=lambda: self.terminate(_PID),
        )

    def public_http(self, url: str, timeout: float) -> bool:
        self.public_http_calls.append((url, timeout))
        if len(self.public_results) > 1:
            return self.public_results.pop(0)
        return self.public_results[0]

    def process_alive(self, pid: int) -> bool:
        return self.alive.get(pid, False)

    def process_matches(self, pid: int, argv: tuple[str, ...]) -> bool:
        return self.process_commands.get(pid) == argv

    def terminate(self, pid: int) -> bool:
        self.terminated.append(pid)
        if self.fail_terminate or not self.alive.get(pid, False):
            return False
        self.alive[pid] = False
        return True

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)

    def dependencies(self) -> public_access._PublicAccessDependencies:
        return public_access._PublicAccessDependencies(
            environ={CLOUDFLARED_BINARY_ENV: _BINARY},
            which=lambda _name: _BINARY if self.binary_available else None,
            is_executable=lambda value: self.binary_available and value == _BINARY,
            http_status=self.http,
            public_http_ready=self.public_http,
            spawn=self.spawn,
            process_alive=self.process_alive,
            process_matches=self.process_matches,
            terminate=self.terminate,
            sleep=self.sleep,
            state_path=self.state_path,
            log_path=self.log_path,
            config_paths=(
                self.state_path.parent / "config.yml",
                self.state_path.parent / "config.yaml",
            ),
        )


def test_binary_discovery_prefers_explicit_override_then_path(tmp_path: Path) -> None:
    explicit = public_access._PublicAccessDependencies(
        environ={CLOUDFLARED_BINARY_ENV: "/explicit/cloudflared"},
        which=lambda _name: "/path/cloudflared",
        is_executable=lambda _value: True,
        state_path=tmp_path / "state.json",
        log_path=tmp_path / "cloudflared.log",
    )
    assert discover_cloudflared_binary(explicit) == "/explicit/cloudflared"

    path = public_access._PublicAccessDependencies(
        environ={},
        which=lambda _name: "/path/cloudflared",
        is_executable=lambda value: value == "/path/cloudflared",
        state_path=tmp_path / "state.json",
        log_path=tmp_path / "cloudflared.log",
    )
    assert discover_cloudflared_binary(path) == "/path/cloudflared"


@pytest.mark.parametrize(
    "text",
    [
        "http://calm-river-123.trycloudflare.com",
        "https://calm-river-123.trycloudflare.com.attacker.example",
        "https://user@calm-river-123.trycloudflare.com",
        "https://calm-river-123.trycloudflare.com:8443",
        "https://calm-river-123.trycloudflare.com/private",
        "https://calm-river-123.trycloudflare.com?token=secret",
        "https://calm-river-123.trycloudflare.com#fragment",
        "https://trycloudflare.com",
        "https://UPPER.trycloudflare.com",
        (
            "https://first-tunnel.trycloudflare.com "
            "https://second-tunnel.trycloudflare.com"
        ),
    ],
)
def test_quick_tunnel_url_parser_rejects_noncanonical_or_ambiguous_urls(text: str) -> None:
    assert extract_quick_tunnel_url(text) is None


def test_quick_tunnel_url_parser_accepts_one_unique_canonical_https_url() -> None:
    text = (
        "INF account-id=must-not-print\n"
        f"INF Your quick Tunnel has been created! Visit it at {_PUBLIC_URL}\n"
        f"INF repeated-location={_PUBLIC_URL}\n"
    )

    assert extract_quick_tunnel_url(text) == _PUBLIC_URL


def test_readiness_is_read_only_for_an_authoritative_loopback_dashboard(
    tmp_path: Path,
) -> None:
    fake = _FakeBoundaries(tmp_path)

    result = inspect_public_access(fake.dependencies())

    assert result.ready is True
    assert result.enabled is False
    assert result.public_url is None
    assert result.blockers == ()
    assert fake.http_calls == [(LOCAL_DASHBOARD_URL, 2.0)]
    assert fake.spawned == []
    assert fake.terminated == []
    assert not fake.state_path.exists()
    assert not fake.log_path.exists()


def test_dashboard_identity_requires_security_headers_and_body_marker() -> None:
    response = _FakeResponse()

    assert public_access._response_is_dashboard(
        response, b"<title>Crypto Decision Radar</title>"
    )
    assert not public_access._response_is_dashboard(
        _FakeResponse({"X-Robots-Tag": ""}),
        b"<title>Crypto Decision Radar</title>",
    )
    assert not public_access._response_is_dashboard(
        response, b"<title>Unrelated local service</title>"
    )


@pytest.mark.parametrize(
    ("fake_options", "blocker"),
    [
        ({"http_status": 503}, "local_dashboard_unavailable"),
        ({"http_status": 200, "local_identity": False}, "local_dashboard_unavailable"),
        ({"binary_available": False}, "cloudflared_binary_missing"),
    ],
)
def test_readiness_fails_closed_before_publication(
    tmp_path: Path,
    fake_options: dict[str, object],
    blocker: str,
) -> None:
    fake = _FakeBoundaries(tmp_path, **fake_options)

    result = inspect_public_access(fake.dependencies())

    assert result.ready is False
    assert result.enabled is False
    assert blocker in result.blockers
    assert fake.spawned == []
    assert fake.terminated == []


def test_readiness_and_enable_refuse_ambient_cloudflared_configuration(
    tmp_path: Path,
) -> None:
    fake = _FakeBoundaries(tmp_path)
    config_path = tmp_path / "config.yml"
    config_path.write_text("tunnel: unrelated-named-tunnel\n", encoding="utf-8")

    status = inspect_public_access(fake.dependencies())
    operation = enable_public_access(confirm=True, dependencies=fake.dependencies())

    assert status.ready is False
    assert "cloudflared_config_present" in status.blockers
    assert operation.ok is False
    assert operation.reason == "cloudflared_config_present"
    assert fake.spawned == []
    assert fake.terminated == []
    assert config_path.read_text(encoding="utf-8") == "tunnel: unrelated-named-tunnel\n"


def test_enable_requires_confirmation_without_even_inspecting_state(tmp_path: Path) -> None:
    fake = _FakeBoundaries(tmp_path)

    result = enable_public_access(confirm=False, dependencies=fake.dependencies())

    assert result.ok is False
    assert result.changed is False
    assert result.reason == "confirmation_required"
    assert fake.http_calls == []
    assert fake.spawned == []
    assert fake.terminated == []
    assert not fake.state_path.exists()


def test_confirmed_enable_uses_one_fixed_argv_and_persists_only_safe_state(
    tmp_path: Path,
) -> None:
    fake = _FakeBoundaries(tmp_path)

    result = enable_public_access(confirm=True, dependencies=fake.dependencies())

    assert result.ok is True
    assert result.changed is True
    assert result.status is not None and result.status.enabled is True
    assert result.status.public_url == _PUBLIC_URL
    assert fake.spawned == [fake.expected_command]
    assert fake.terminated == []
    assert fake.public_http_calls
    assert {url for url, _timeout in fake.public_http_calls} == {_PUBLIC_URL}
    persisted = json.loads(fake.state_path.read_text(encoding="utf-8"))
    assert persisted["pid"] == _PID
    assert persisted["public_url"] == _PUBLIC_URL
    assert persisted["origin"] == LOCAL_DASHBOARD_URL
    assert persisted["argv"] == list(fake.expected_command)
    assert "must-not-print" not in json.dumps(persisted)


def test_enable_never_starts_when_dashboard_is_not_authoritative(tmp_path: Path) -> None:
    fake = _FakeBoundaries(tmp_path, http_status=503)

    result = enable_public_access(confirm=True, dependencies=fake.dependencies())

    assert result.ok is False
    assert result.reason == "local_dashboard_unavailable"
    assert fake.spawned == []
    assert not fake.state_path.exists()


def test_enable_cleans_up_child_when_no_canonical_public_url_appears(
    tmp_path: Path,
) -> None:
    fake = _FakeBoundaries(
        tmp_path,
        log_text=(
            "ERR credential=must-not-print "
            "https://lookalike.trycloudflare.com.attacker.example\n"
        ),
    )

    result = enable_public_access(confirm=True, dependencies=fake.dependencies())

    assert result.ok is False
    assert result.changed is False
    assert result.reason == "tunnel_url_unavailable"
    assert fake.spawned == [fake.expected_command]
    assert fake.terminated == [_PID]
    assert not fake.state_path.exists()


def test_enable_cleans_up_when_edge_registration_never_appears(
    tmp_path: Path,
) -> None:
    fake = _FakeBoundaries(
        tmp_path,
        log_text=f"INF Quick Tunnel available at {_PUBLIC_URL}\n",
    )

    result = enable_public_access(confirm=True, dependencies=fake.dependencies())

    assert result.ok is False
    assert result.reason == "tunnel_registration_unavailable"
    assert fake.terminated == [_PID]
    assert not fake.state_path.exists()
    assert not fake.log_path.exists()


def test_enable_cleans_up_when_issued_url_does_not_serve_the_dashboard(
    tmp_path: Path,
) -> None:
    fake = _FakeBoundaries(tmp_path, public_ready=False)

    result = enable_public_access(confirm=True, dependencies=fake.dependencies())

    assert result.ok is False
    assert result.changed is False
    assert result.reason == "public_dashboard_unavailable"
    assert fake.spawned == [fake.expected_command]
    assert fake.terminated == [_PID]
    assert len(fake.public_http_calls) == public_access._PUBLIC_PROBE_ATTEMPTS
    assert not fake.state_path.exists()
    assert not fake.log_path.exists()


def test_enable_rolls_back_if_post_write_public_verification_fails(
    tmp_path: Path,
) -> None:
    fake = _FakeBoundaries(tmp_path, public_ready=[True, False])

    result = enable_public_access(confirm=True, dependencies=fake.dependencies())

    assert result.ok is False
    assert result.changed is False
    assert result.reason == "post_enable_verification_failed"
    assert fake.terminated == [_PID]
    assert fake.alive[_PID] is False
    assert not fake.state_path.exists()
    assert not fake.log_path.exists()


def test_enable_reaps_its_exact_child_when_argv_inspection_is_unavailable(
    tmp_path: Path,
) -> None:
    fake = _FakeBoundaries(tmp_path)
    dependencies = replace(
        fake.dependencies(),
        process_matches=lambda _pid, _argv: False,
    )

    result = enable_public_access(confirm=True, dependencies=dependencies)

    assert result.ok is False
    assert result.reason == "tunnel_process_unowned"
    assert fake.terminated == [_PID]
    assert fake.alive[_PID] is False
    assert not fake.state_path.exists()
    assert not fake.log_path.exists()


def test_enable_is_idempotent_only_for_the_exact_owned_live_process(tmp_path: Path) -> None:
    fake = _FakeBoundaries(tmp_path)
    first = enable_public_access(confirm=True, dependencies=fake.dependencies())
    assert first.ok is True
    fake.spawned.clear()

    second = enable_public_access(confirm=True, dependencies=fake.dependencies())

    assert second.ok is True
    assert second.changed is False
    assert second.status is not None and second.status.enabled is True
    assert fake.spawned == []


def test_status_refuses_a_dead_process_without_cleaning_or_restarting_it(
    tmp_path: Path,
) -> None:
    fake = _FakeBoundaries(tmp_path)
    assert enable_public_access(confirm=True, dependencies=fake.dependencies()).ok is True
    fake.spawned.clear()
    fake.alive[_PID] = False

    result = inspect_public_access(fake.dependencies())

    assert result.ready is False
    assert result.enabled is False
    assert "public_access_state_stale" in result.blockers
    assert fake.spawned == []
    assert fake.terminated == []
    assert fake.state_path.exists()


def test_confirmed_disable_clears_a_dead_receipt_without_signaling_any_pid(
    tmp_path: Path,
) -> None:
    fake = _FakeBoundaries(tmp_path)
    assert enable_public_access(confirm=True, dependencies=fake.dependencies()).ok is True
    fake.terminated.clear()
    fake.alive[_PID] = False

    result = disable_public_access(confirm=True, dependencies=fake.dependencies())

    assert result.ok is True
    assert result.changed is True
    assert fake.terminated == []
    assert not fake.state_path.exists()
    assert not fake.log_path.exists()


def test_mutations_refuse_state_whose_pid_no_longer_matches_owned_command(
    tmp_path: Path,
) -> None:
    fake = _FakeBoundaries(tmp_path)
    assert enable_public_access(confirm=True, dependencies=fake.dependencies()).ok is True
    fake.spawned.clear()
    fake.process_commands[_PID] = ("/unrelated/process", "--important")

    enable = enable_public_access(confirm=True, dependencies=fake.dependencies())
    disable = disable_public_access(confirm=True, dependencies=fake.dependencies())

    assert enable.ok is False
    assert enable.reason == "public_access_state_unowned"
    assert disable.ok is False
    assert disable.reason == "public_access_state_unowned"
    assert fake.spawned == []
    assert fake.terminated == []
    assert fake.state_path.exists()


@pytest.mark.parametrize("state_text", ["not-json", "x" * (64 * 1024 + 1)])
def test_malformed_or_oversized_state_is_never_overwritten_or_used_to_kill(
    tmp_path: Path,
    state_text: str,
) -> None:
    fake = _FakeBoundaries(tmp_path)
    fake.state_path.write_text(state_text, encoding="utf-8")

    status = inspect_public_access(fake.dependencies())
    enable = enable_public_access(confirm=True, dependencies=fake.dependencies())
    disable = disable_public_access(confirm=True, dependencies=fake.dependencies())

    assert status.ready is False
    assert "public_access_state_invalid" in status.blockers
    assert enable.reason == "public_access_state_invalid"
    assert disable.reason == "public_access_state_invalid"
    assert fake.spawned == []
    assert fake.terminated == []
    assert fake.state_path.read_text(encoding="utf-8") == state_text


def test_symlink_state_is_invalid_and_never_followed_or_removed(tmp_path: Path) -> None:
    fake = _FakeBoundaries(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_text('{"sensitive":"preserve"}\n', encoding="utf-8")
    fake.state_path.symlink_to(outside)

    status = inspect_public_access(fake.dependencies())
    operation = disable_public_access(confirm=True, dependencies=fake.dependencies())

    assert status.ready is False
    assert "public_access_state_invalid" in status.blockers
    assert operation.ok is False
    assert operation.reason == "public_access_state_invalid"
    assert fake.state_path.is_symlink()
    assert outside.read_text(encoding="utf-8") == '{"sensitive":"preserve"}\n'
    assert fake.terminated == []


def test_enable_refuses_a_symlink_log_without_spawning_or_touching_its_target(
    tmp_path: Path,
) -> None:
    fake = _FakeBoundaries(tmp_path)
    outside = tmp_path / "outside.log"
    outside.write_text("preserve-sensitive-log-target\n", encoding="utf-8")
    fake.log_path.symlink_to(outside)

    operation = enable_public_access(confirm=True, dependencies=fake.dependencies())

    assert operation.ok is False
    assert operation.reason == "tunnel_start_failed"
    assert fake.spawned == []
    assert fake.terminated == []
    assert fake.log_path.is_symlink()
    assert outside.read_text(encoding="utf-8") == "preserve-sensitive-log-target\n"


def test_disable_requires_confirmation_and_stops_only_the_owned_pid(tmp_path: Path) -> None:
    fake = _FakeBoundaries(tmp_path)
    assert enable_public_access(confirm=True, dependencies=fake.dependencies()).ok is True
    fake.terminated.clear()

    unconfirmed = disable_public_access(confirm=False, dependencies=fake.dependencies())
    confirmed = disable_public_access(confirm=True, dependencies=fake.dependencies())

    assert unconfirmed.ok is False
    assert unconfirmed.reason == "confirmation_required"
    assert confirmed.ok is True
    assert confirmed.changed is True
    assert fake.terminated == [_PID]
    assert not fake.state_path.exists()


def test_disable_can_stop_the_owned_tunnel_when_dashboard_has_gone_stale(
    tmp_path: Path,
) -> None:
    fake = _FakeBoundaries(tmp_path)
    assert enable_public_access(confirm=True, dependencies=fake.dependencies()).ok is True
    fake.terminated.clear()
    fake.local_status = 503

    result = disable_public_access(confirm=True, dependencies=fake.dependencies())

    assert result.ok is True
    assert result.changed is True
    assert fake.terminated == [_PID]
    assert not fake.state_path.exists()


def test_disable_uses_persisted_argv_if_binary_discovery_changes(
    tmp_path: Path,
) -> None:
    fake = _FakeBoundaries(tmp_path)
    assert enable_public_access(confirm=True, dependencies=fake.dependencies()).ok is True
    fake.terminated.clear()
    fake.binary_available = False

    result = disable_public_access(confirm=True, dependencies=fake.dependencies())

    assert result.ok is True
    assert result.changed is True
    assert fake.terminated == [_PID]
    assert not fake.state_path.exists()


def test_default_spawner_passes_fixed_argv_without_a_shell(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, dict[str, object]]] = []

    class _Process:
        pid = _PID

    def fake_popen(argv: object, **kwargs: object) -> _Process:
        calls.append((argv, kwargs))
        return _Process()

    monkeypatch.setattr(public_access.subprocess, "Popen", fake_popen)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PATH", "/safe/bin")
    monkeypatch.setenv("TUNNEL_TOKEN", "must-not-reach-child")
    monkeypatch.setenv("TUNNEL_LOGLEVEL", "debug")
    monkeypatch.setenv(CLOUDFLARED_BINARY_ENV, _BINARY)
    monkeypatch.setenv("UNRELATED_SECRET", "must-not-reach-child")
    dependencies = public_access._PublicAccessDependencies(
        state_path=tmp_path / "state.json",
        log_path=tmp_path / "cloudflared.log",
        config_paths=(),
    )
    argv = (_BINARY, "tunnel", "--url", LOCAL_DASHBOARD_URL)

    spawned = dependencies.spawn(argv)
    assert spawned.pid == _PID
    assert len(calls) == 1
    actual_argv, options = calls[0]
    assert actual_argv == argv
    assert isinstance(actual_argv, tuple)
    assert options["shell"] is False
    assert options["start_new_session"] is True
    assert options["stdin"] is subprocess.DEVNULL
    assert options["stdout"] is subprocess.DEVNULL
    assert options["stderr"] is subprocess.DEVNULL
    child_environment = options["env"]
    assert isinstance(child_environment, dict)
    assert child_environment["HOME"] == str(tmp_path)
    assert child_environment["PATH"] == "/safe/bin"
    assert set(child_environment) <= {
        "HOME",
        "LANG",
        "LC_ALL",
        "PATH",
        "SSL_CERT_DIR",
        "SSL_CERT_FILE",
        "TMPDIR",
    }
    assert "TUNNEL_TOKEN" not in child_environment
    assert "TUNNEL_LOGLEVEL" not in child_environment
    assert CLOUDFLARED_BINARY_ENV not in child_environment
    assert "UNRELATED_SECRET" not in child_environment


def test_cli_output_is_sanitized_and_reveals_url_only_after_confirmed_enable(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake = _FakeBoundaries(
        tmp_path,
        log_text=(
            "INF account-id=secret-account ip=192.0.2.44\n"
            f"INF Quick Tunnel available at {_PUBLIC_URL}\n"
            "INF Registered tunnel connection\n"
        ),
    )

    assert main(["readiness"], dependencies=fake.dependencies()) == 0
    readiness = capsys.readouterr()
    assert "trycloudflare.com" not in readiness.out
    assert readiness.err == ""

    assert main(["enable"], dependencies=fake.dependencies()) == 1
    unconfirmed = capsys.readouterr()
    assert "confirmation_required" in unconfirmed.err
    assert "trycloudflare.com" not in unconfirmed.err

    assert main(["enable", "--confirm"], dependencies=fake.dependencies()) == 0
    confirmed = capsys.readouterr()
    assert f"url={_PUBLIC_URL}" in confirmed.out
    assert "secret-account" not in confirmed.out
    assert "192.0.2.44" not in confirmed.out
    assert confirmed.err == ""

    assert main(["readiness"], dependencies=fake.dependencies()) == 0
    enabled_readiness = capsys.readouterr()
    assert _PUBLIC_URL not in enabled_readiness.out
    assert "url=redacted_use_status" in enabled_readiness.out
    assert enabled_readiness.err == ""

    assert main(["status"], dependencies=fake.dependencies()) == 0
    enabled_status = capsys.readouterr()
    assert f"url={_PUBLIC_URL}" in enabled_status.out
    assert "secret-account" not in enabled_status.out
    assert "192.0.2.44" not in enabled_status.out
    assert enabled_status.err == ""


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

    readiness = dry_run("radar-dashboard-public-readiness")
    status = dry_run("radar-dashboard-public-status")
    enable_without_confirm = dry_run("radar-dashboard-public-enable")
    enable_with_confirm = dry_run("radar-dashboard-public-enable", "CONFIRM=1")
    disable_without_confirm = dry_run("radar-dashboard-public-disable")
    disable_with_confirm = dry_run("radar-dashboard-public-disable", "CONFIRM=1")

    assert "dashboard.public_access readiness" in readiness
    assert "dashboard.public_access status" in status
    assert "--confirm" not in enable_without_confirm
    assert enable_with_confirm.count("--confirm") == 1
    assert "--confirm" not in disable_without_confirm
    assert disable_with_confirm.count("--confirm") == 1
    rendered = "\n".join(
        (
            readiness,
            status,
            enable_without_confirm,
            enable_with_confirm,
            disable_without_confirm,
            disable_with_confirm,
        )
    )
    assert LOCAL_DASHBOARD_URL not in rendered
    assert "0.0.0.0" not in rendered
    assert "tailscale" not in rendered.casefold()
