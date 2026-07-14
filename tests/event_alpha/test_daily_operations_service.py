"""Launchd ownership and confirmation gates for Daily Operations v1."""

from __future__ import annotations

import json
import plistlib
import stat
from pathlib import Path
import subprocess

from crypto_rsi_scanner.event_alpha.operations import daily_operations_service as service
from crypto_rsi_scanner.event_alpha.operations.daily_operations_service import (
    CommandResult,
    SERVICE_LABEL,
    SERVICE_STATE_FILENAME,
    ServiceDependencies,
    expected_dashboard_argv,
    expected_service_argv,
    inspect_dashboard_ownership,
    install_service,
    uninstall_service,
)


UID = 501
REPO_ROOT = Path(__file__).resolve().parents[2]


def _launchctl_text(
    argv: tuple[str, ...],
    *,
    state: str = "running",
    pid: int = 991,
    last_exit_code: int | None = None,
    runs: int | None = None,
) -> str:
    arguments = "\n".join(f"\t\t{value}" for value in argv)
    telemetry = ""
    if last_exit_code is not None:
        telemetry += f"\tlast exit code = {last_exit_code}\n"
    if runs is not None:
        telemetry += f"\truns = {runs}\n"
    return (
        "gui/501/example = {\n"
        f"\tstate = {state}\n"
        "\targuments = {\n"
        f"{arguments}\n"
        "\t}\n"
        f"\tpid = {pid}\n"
        f"{telemetry}"
        "}\n"
    )


class _Launchd:
    def __init__(
        self,
        *,
        repo: Path,
        python: Path,
        artifact_base: Path,
        home: Path,
    ) -> None:
        self.repo = repo
        self.python = python
        self.artifact_base = artifact_base
        self.home = home
        self.loaded = False
        self.scheduler_last_exit_code: int | None = None
        self.scheduler_runs: int | None = None
        self.commands: list[tuple[str, ...]] = []
        self.dashboard_argv = expected_dashboard_argv(
            repo_root=repo,
            python_path=python,
            artifact_base=artifact_base,
        )

    @property
    def service_argv(self) -> tuple[str, ...]:
        return expected_service_argv(
            python_path=self.python,
            artifact_base=self.artifact_base,
            top_n=30,
            fetch_limit=50,
        )

    def run(self, argv: tuple[str, ...]) -> CommandResult:
        self.commands.append(argv)
        dashboard = f"gui/{UID}/{service.DASHBOARD_LABEL}"
        scheduler = f"gui/{UID}/{SERVICE_LABEL}"
        if argv == ("launchctl", "print", dashboard):
            return CommandResult(0, _launchctl_text(self.dashboard_argv, pid=77858))
        if argv == ("launchctl", "print", scheduler):
            if not self.loaded:
                return CommandResult(113, "not loaded")
            return CommandResult(
                0,
                _launchctl_text(
                    self.service_argv,
                    state="waiting",
                    last_exit_code=self.scheduler_last_exit_code,
                    runs=self.scheduler_runs,
                ),
            )
        if argv[:3] == ("launchctl", "bootstrap", f"gui/{UID}"):
            self.loaded = True
            return CommandResult(0, "")
        if argv == ("launchctl", "bootout", scheduler):
            self.loaded = False
            return CommandResult(0, "")
        raise AssertionError(f"unexpected launchd command: {argv!r}")

    def dependencies(self) -> ServiceDependencies:
        return ServiceDependencies(run=self.run, uid=UID, home=self.home)


def _paths(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    python = repo / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.touch()
    artifact_base = repo / "event_fade_cache"
    artifact_base.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    agents = home / "Library" / "LaunchAgents"
    return repo, python, artifact_base, home, agents


def test_dashboard_ownership_requires_the_complete_expected_argv(tmp_path: Path) -> None:
    repo, python, base, home, _agents = _paths(tmp_path)
    fake = _Launchd(repo=repo, python=python, artifact_base=base, home=home)

    owned = inspect_dashboard_ownership(
        artifact_base=base,
        repo_root_path=repo,
        python_path=python,
        dependencies=fake.dependencies(),
    )
    fake.dashboard_argv = (*fake.dashboard_argv[:-1], "8766")
    mismatch = inspect_dashboard_ownership(
        artifact_base=base,
        repo_root_path=repo,
        python_path=python,
        dependencies=fake.dependencies(),
    )

    assert owned.owned is True
    assert owned.pid == 77858
    assert mismatch.owned is False
    assert mismatch.reason == "dashboard_argv_mismatch"


def test_service_argv_binds_the_configured_scheduler_interval(tmp_path: Path) -> None:
    _repo, python, base, _home, _agents = _paths(tmp_path)

    argv = expected_service_argv(
        python_path=python,
        artifact_base=base,
        top_n=30,
        fetch_limit=50,
        interval_seconds=900,
    )

    assert argv[-4:] == ("--interval-seconds", "900", "--fetch-limit", "50")


def test_install_without_confirmation_never_writes_or_mutates_launchd(
    tmp_path: Path,
) -> None:
    repo, python, base, home, agents = _paths(tmp_path)
    fake = _Launchd(repo=repo, python=python, artifact_base=base, home=home)

    result = install_service(
        confirm=False,
        artifact_base=base,
        top_n=30,
        fetch_limit=50,
        repo_root_path=repo,
        python_path=python,
        launch_agents_dir=agents,
        dependencies=fake.dependencies(),
    )

    assert result.ok is False
    assert result.reason == "confirmation_required"
    assert not agents.exists()
    assert not (base / SERVICE_STATE_FILENAME).exists()
    assert all(command[1] == "print" for command in fake.commands)


def test_confirmed_install_writes_exact_private_plist_and_service_receipt(
    tmp_path: Path,
) -> None:
    repo, python, base, home, agents = _paths(tmp_path)
    fake = _Launchd(repo=repo, python=python, artifact_base=base, home=home)

    result = install_service(
        confirm=True,
        artifact_base=base,
        top_n=30,
        fetch_limit=50,
        interval_seconds=300,
        repo_root_path=repo,
        python_path=python,
        launch_agents_dir=agents,
        dependencies=fake.dependencies(),
    )

    plist_path = agents / f"{SERVICE_LABEL}.plist"
    assert result.ok is True
    assert result.changed is True
    assert result.health.enabled is True
    assert stat.S_IMODE(plist_path.stat().st_mode) == 0o600
    with plist_path.open("rb") as handle:
        plist = plistlib.load(handle)
    assert tuple(plist["ProgramArguments"]) == fake.service_argv
    assert plist["RunAtLoad"] is False
    assert plist["Umask"] == 0o077
    assert "RSI_EVENT_DISCOVERY_UNIVERSE_LIVE" not in plist["EnvironmentVariables"]
    receipt = json.loads((base / SERVICE_STATE_FILENAME).read_text(encoding="utf-8"))
    assert receipt["enabled"] is True
    assert receipt["operation"] == "install"
    assert receipt["telegram_sends"] == 0
    assert any(command[1] == "bootstrap" for command in fake.commands)


def test_loaded_scheduler_with_nonzero_last_exit_is_unhealthy(tmp_path: Path) -> None:
    repo, python, base, home, agents = _paths(tmp_path)
    fake = _Launchd(repo=repo, python=python, artifact_base=base, home=home)
    assert install_service(
        confirm=True,
        artifact_base=base,
        top_n=30,
        fetch_limit=50,
        repo_root_path=repo,
        python_path=python,
        launch_agents_dir=agents,
        dependencies=fake.dependencies(),
    ).ok is True
    fake.scheduler_last_exit_code = 78
    fake.scheduler_runs = 4

    health = service.inspect_scheduler_health(
        artifact_base=base,
        top_n=30,
        fetch_limit=50,
        repo_root_path=repo,
        python_path=python,
        launch_agents_dir=agents,
        dependencies=fake.dependencies(),
    )

    assert health.enabled is True
    assert health.loaded is True
    assert health.running is False
    assert health.healthy is False
    assert health.reason == "scheduler_last_exit_nonzero"
    assert health.last_exit_code == 78
    assert health.runs == 4


def test_confirmed_install_never_clobbers_target_created_during_write(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo, python, base, home, agents = _paths(tmp_path)
    fake = _Launchd(repo=repo, python=python, artifact_base=base, home=home)
    plist_path = agents / f"{SERVICE_LABEL}.plist"
    original_link = service.os.link

    def create_unowned_then_link(*args, **kwargs):
        plist_path.write_bytes(
            plistlib.dumps(
                {
                    "Label": "com.example.concurrent",
                    "ProgramArguments": ["/usr/bin/true"],
                }
            )
        )
        return original_link(*args, **kwargs)

    monkeypatch.setattr(service.os, "link", create_unowned_then_link)
    result = install_service(
        confirm=True,
        artifact_base=base,
        top_n=30,
        fetch_limit=50,
        repo_root_path=repo,
        python_path=python,
        launch_agents_dir=agents,
        dependencies=fake.dependencies(),
    )

    assert result.ok is False
    assert result.reason == "service_plist_write_failed"
    with plist_path.open("rb") as handle:
        assert plistlib.load(handle)["Label"] == "com.example.concurrent"
    assert all(command[1] != "bootstrap" for command in fake.commands)


def test_confirmed_install_detects_parent_swap_without_touching_new_parent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo, python, base, home, agents = _paths(tmp_path)
    fake = _Launchd(repo=repo, python=python, artifact_base=base, home=home)
    plist_path = agents / f"{SERVICE_LABEL}.plist"
    displaced = agents.with_name("LaunchAgents-displaced")
    original_link = service.os.link

    def swap_parent_then_link(*args, **kwargs):
        agents.rename(displaced)
        agents.mkdir(mode=0o700)
        plist_path.write_bytes(
            plistlib.dumps(
                {
                    "Label": "com.example.new-parent",
                    "ProgramArguments": ["/usr/bin/true"],
                }
            )
        )
        return original_link(*args, **kwargs)

    monkeypatch.setattr(service.os, "link", swap_parent_then_link)
    result = install_service(
        confirm=True,
        artifact_base=base,
        top_n=30,
        fetch_limit=50,
        repo_root_path=repo,
        python_path=python,
        launch_agents_dir=agents,
        dependencies=fake.dependencies(),
    )

    assert result.ok is False
    assert result.reason == "service_plist_write_failed"
    with plist_path.open("rb") as handle:
        assert plistlib.load(handle)["Label"] == "com.example.new-parent"
    assert not (displaced / f"{SERVICE_LABEL}.plist").exists()
    assert all(command[1] != "bootstrap" for command in fake.commands)


def test_confirmed_uninstall_removes_only_exact_owned_service(tmp_path: Path) -> None:
    repo, python, base, home, agents = _paths(tmp_path)
    fake = _Launchd(repo=repo, python=python, artifact_base=base, home=home)
    installed = install_service(
        confirm=True,
        artifact_base=base,
        top_n=30,
        fetch_limit=50,
        repo_root_path=repo,
        python_path=python,
        launch_agents_dir=agents,
        dependencies=fake.dependencies(),
    )
    assert installed.ok is True

    removed = uninstall_service(
        confirm=True,
        artifact_base=base,
        top_n=30,
        fetch_limit=50,
        repo_root_path=repo,
        python_path=python,
        launch_agents_dir=agents,
        dependencies=fake.dependencies(),
    )

    assert removed.ok is True
    assert removed.reason == "uninstalled"
    assert not (agents / f"{SERVICE_LABEL}.plist").exists()
    receipt = json.loads((base / SERVICE_STATE_FILENAME).read_text(encoding="utf-8"))
    assert receipt["enabled"] is False
    assert receipt["operation"] == "uninstall"
    assert ("launchctl", "bootout", f"gui/{UID}/{SERVICE_LABEL}") in fake.commands


def test_uninstall_refuses_regular_plist_swapped_after_bootout(tmp_path: Path) -> None:
    repo, python, base, home, agents = _paths(tmp_path)
    fake = _Launchd(repo=repo, python=python, artifact_base=base, home=home)
    assert install_service(
        confirm=True,
        artifact_base=base,
        top_n=30,
        fetch_limit=50,
        repo_root_path=repo,
        python_path=python,
        launch_agents_dir=agents,
        dependencies=fake.dependencies(),
    ).ok is True
    plist_path = agents / f"{SERVICE_LABEL}.plist"
    original_run = fake.run

    def swap_after_bootout(argv: tuple[str, ...]) -> service.CommandResult:
        result = original_run(argv)
        if argv == ("launchctl", "bootout", f"gui/{UID}/{SERVICE_LABEL}"):
            plist_path.write_bytes(
                plistlib.dumps(
                    {
                        "Label": "com.example.unowned",
                        "ProgramArguments": ["/usr/bin/true"],
                    }
                )
            )
        return result

    dependencies = ServiceDependencies(run=swap_after_bootout, uid=UID, home=home)
    removed = uninstall_service(
        confirm=True,
        artifact_base=base,
        top_n=30,
        fetch_limit=50,
        repo_root_path=repo,
        python_path=python,
        launch_agents_dir=agents,
        dependencies=dependencies,
    )

    assert removed.ok is False
    assert removed.reason == "service_plist_remove_failed"
    assert plist_path.exists()
    with plist_path.open("rb") as handle:
        assert plistlib.load(handle)["Label"] == "com.example.unowned"


def test_confirmed_install_with_unowned_dashboard_records_disabled_receipt(
    tmp_path: Path,
) -> None:
    repo, python, base, home, agents = _paths(tmp_path)
    fake = _Launchd(repo=repo, python=python, artifact_base=base, home=home)
    fake.dashboard_argv = (*fake.dashboard_argv[:-1], "9999")

    result = install_service(
        confirm=True,
        artifact_base=base,
        top_n=30,
        fetch_limit=50,
        repo_root_path=repo,
        python_path=python,
        launch_agents_dir=agents,
        dependencies=fake.dependencies(),
    )

    assert result.ok is False
    assert result.reason == "dashboard_argv_mismatch"
    assert not agents.exists()
    receipt = json.loads((base / SERVICE_STATE_FILENAME).read_text(encoding="utf-8"))
    assert receipt["enabled"] is False
    assert receipt["operation_ok"] is False
    assert all(command[1] != "bootstrap" for command in fake.commands)


def test_make_targets_keep_install_confirmation_explicit() -> None:
    def dry_run(target: str, *variables: str) -> str:
        result = subprocess.run(
            ["make", "-n", target, "PYTHON=python3", *variables],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout

    cycle = dry_run("radar-daily-ops-dry-run")
    install_without = dry_run("radar-daily-ops-install")
    install_with = dry_run("radar-daily-ops-install", "CONFIRM=1")
    uninstall_with = dry_run("radar-daily-ops-uninstall", "CONFIRM=1")

    assert "daily_operations cycle" in cycle
    assert "--dry-run" in cycle
    assert "--confirm" not in install_without
    assert install_with.count("--confirm") == 1
    assert uninstall_with.count("--confirm") == 1
