"""CLI contract tests for the preview-first exact observed-outcome operator."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from crypto_rsi_scanner import scanner
from crypto_rsi_scanner.cli import dispatch as cli_dispatch
from crypto_rsi_scanner.cli.event_alpha_command_registry import EVENT_ALPHA_COMMANDS
from crypto_rsi_scanner.cli.parser import (
    COMMAND_FLAG_TO_SNAPSHOT,
    build_parser,
    classify_command,
    dispatch_key_from_args,
)
from crypto_rsi_scanner.cli.parser_integrated_radar import (
    OBSERVED_OUTCOME_COMMAND_DEST,
    OBSERVED_OUTCOME_OPTION_DESTS,
)
from crypto_rsi_scanner.cli.services import event_alpha_outcomes


ROOT = Path(__file__).resolve().parents[2]
CANDIDATES = "fixtures/event_discovery/observed_outcome_candidate.jsonl"
CORES = "fixtures/event_discovery/observed_outcome_core.jsonl"
CLOSES = "fixtures/event_discovery/observed_outcome_dense_ohlcv.json"
EVALUATED_AT = "2026-06-08T12:20:00Z"


def _command_args(*extra: str) -> list[str]:
    return [
        "--event-alpha-observed-outcome-build",
        "--event-alpha-observed-candidates",
        CANDIDATES,
        "--event-alpha-observed-cores",
        CORES,
        "--event-alpha-observed-closes",
        CLOSES,
        "--event-alpha-observed-candidate-id",
        "candidate-testobs",
        "--event-alpha-observed-core-id",
        "core-testobs",
        "--event-alpha-observed-evaluated-at",
        EVALUATED_AT,
        "--event-alpha-profile",
        "fixture",
        "--event-alpha-artifact-namespace",
        "observed-outcome-builder",
        *extra,
    ]


def test_observed_outcome_parser_and_registry_contract():
    parser = build_parser()
    defaults = parser.parse_args([])
    assert defaults.event_alpha_observed_outcome_build is False
    for destination in OBSERVED_OUTCOME_OPTION_DESTS:
        assert getattr(defaults, destination) is None

    args = parser.parse_args(_command_args("--json"))
    assert args.event_alpha_observed_outcome_build is True
    assert args.event_alpha_observed_candidates == CANDIDATES
    assert args.event_alpha_observed_cores == CORES
    assert args.event_alpha_observed_closes == CLOSES
    assert args.event_alpha_observed_candidate_id == "candidate-testobs"
    assert args.event_alpha_observed_core_id == "core-testobs"
    assert args.event_alpha_observed_evaluated_at == EVALUATED_AT
    assert args.json is True
    assert args.confirm is False
    assert args.out is None
    assert dispatch_key_from_args(args) == "event_alpha_observed_outcome_build"
    snapshot = classify_command(["--event-alpha-observed-outcome-build"])
    assert snapshot.command_group == "event_alpha_integrated_radar"

    registrations = {row.parsed_attr: row for row in EVENT_ALPHA_COMMANDS}
    for destination in (OBSERVED_OUTCOME_COMMAND_DEST, *OBSERVED_OUTCOME_OPTION_DESTS):
        row = registrations[destination]
        assert row.command_group == "event_alpha_integrated_radar"
        assert row.requires_no_send is True
        assert row.allows_live_provider_call is False


def test_cli_flag_snapshot_matches_every_visible_long_option():
    expected = []
    for action in build_parser()._actions:
        if action.help == argparse.SUPPRESS:
            continue
        for flag in action.option_strings:
            if not flag.startswith("--"):
                continue
            command = COMMAND_FLAG_TO_SNAPSHOT.get(flag)
            expected.append(
                {
                    "action_type": type(action).__name__,
                    "command_group": command.command_group if command else "option",
                    "default": action.default,
                    "destination": action.dest,
                    "flag": flag,
                }
            )
    expected.sort(key=lambda row: row["flag"])

    payload = json.loads(
        (ROOT / "research" / "CLI_FLAG_SNAPSHOT.json").read_text(encoding="utf-8")
    )
    assert payload["flag_count"] == len(expected)
    assert payload["flags"] == expected


def test_observed_outcome_dispatch_is_direct_and_does_not_apply_artifact_context(
    monkeypatch,
):
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        event_alpha_outcomes,
        "event_alpha_observed_outcome_build",
        lambda **kwargs: calls.append(kwargs),
    )
    monkeypatch.setattr(
        cli_dispatch,
        "bind_scanner_globals",
        lambda *_args, **_kwargs: pytest.fail("observed operator must not bind scanner globals"),
    )
    monkeypatch.setattr(
        scanner,
        "run",
        lambda **_kwargs: pytest.fail("observed operator must not fall through to the RSI scan"),
    )
    original_namespace = scanner.config.EVENT_ALPHA_ARTIFACT_NAMESPACE
    cli_dispatch.dispatch_args(build_parser().parse_args(_command_args("--json")))

    assert scanner.config.EVENT_ALPHA_ARTIFACT_NAMESPACE == original_namespace
    assert calls == [
        {
            "candidate_path": CANDIDATES,
            "core_path": CORES,
            "closes_path": CLOSES,
            "candidate_id": "candidate-testobs",
            "core_id": "core-testobs",
            "evaluated_at": EVALUATED_AT,
            "profile_assertion": "fixture",
            "artifact_namespace_assertion": "observed-outcome-builder",
            "out_path": None,
            "confirm": False,
            "json_output": True,
        }
    ]


def test_observed_outcome_orphan_option_and_command_conflict_exit_two(
    monkeypatch,
    capsys,
):
    monkeypatch.setattr(
        cli_dispatch,
        "bind_scanner_globals",
        lambda *_args, **_kwargs: pytest.fail("blocked observed args must not bind scanner globals"),
    )
    monkeypatch.setattr(
        scanner,
        "run",
        lambda **_kwargs: pytest.fail("blocked observed args must not run the RSI scanner"),
    )
    monkeypatch.setattr(
        event_alpha_outcomes,
        "event_alpha_observed_outcome_build",
        lambda **_kwargs: pytest.fail("conflicting observed command must not reach the service"),
    )

    orphan = build_parser().parse_args(
        ["--event-alpha-observed-candidates", "private-input.jsonl", "--json"]
    )
    with pytest.raises(SystemExit) as orphan_exit:
        cli_dispatch.dispatch_args(orphan)
    assert orphan_exit.value.code == 2
    orphan_payload = json.loads(capsys.readouterr().out)
    assert orphan_payload["errors"] == ["observed_outcome_command_required"]
    assert "private-input" not in json.dumps(orphan_payload)

    conflict = build_parser().parse_args(
        _command_args("--event-alpha-integrated-radar-cycle", "--json")
    )
    with pytest.raises(SystemExit) as conflict_exit:
        cli_dispatch.dispatch_args(conflict)
    assert conflict_exit.value.code == 2
    conflict_payload = json.loads(capsys.readouterr().out)
    assert conflict_payload["errors"] == ["observed_outcome_command_conflict"]


def test_observed_outcome_service_prints_result_and_maps_failure_to_exit_two(
    monkeypatch,
    capsys,
):
    from crypto_rsi_scanner.event_alpha.outcomes import observed_outcome_operator

    class Result:
        def __init__(self, ok: bool):
            self.ok = ok
            self.mode = "preview" if ok else "blocked"
            self.errors = () if ok else ("fixture_error",)
            self.outcome = {"research_only": True} if ok else None
            self.candidate_rows_supplied = 1
            self.core_rows_supplied = 1
            self.observations_supplied = 2
            self.observations_accepted = 2
            self.written = False

        def to_dict(self):
            return {
                "errors": list(self.errors),
                "mode": self.mode,
                "ok": self.ok,
                "written": self.written,
            }

        def to_json(self):
            return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    results = iter((Result(True), Result(False)))
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_operator(*args, **kwargs):
        calls.append((args, kwargs))
        return next(results)

    monkeypatch.setattr(
        observed_outcome_operator,
        "run_observed_outcome_operator",
        fake_operator,
    )
    kwargs = {
        "candidate_path": CANDIDATES,
        "core_path": CORES,
        "closes_path": CLOSES,
        "candidate_id": "candidate-testobs",
        "core_id": "core-testobs",
        "evaluated_at": EVALUATED_AT,
        "profile_assertion": "fixture",
        "artifact_namespace_assertion": "observed-outcome-builder",
        "out_path": None,
        "confirm": False,
        "json_output": True,
    }
    event_alpha_outcomes.event_alpha_observed_outcome_build(**kwargs)
    assert json.loads(capsys.readouterr().out)["ok"] is True
    with pytest.raises(SystemExit) as exc:
        event_alpha_outcomes.event_alpha_observed_outcome_build(**kwargs)
    assert exc.value.code == 2
    assert json.loads(capsys.readouterr().out)["errors"] == ["fixture_error"]
    assert calls[0][0] == (
        CANDIDATES,
        CORES,
        CLOSES,
        "candidate-testobs",
        "core-testobs",
        EVALUATED_AT,
    )
    assert calls[0][1] == {
        "profile_assertion": "fixture",
        "artifact_namespace_assertion": "observed-outcome-builder",
        "out_path": None,
        "confirm": False,
    }


def test_observed_outcome_make_targets_are_preview_first_and_confirm_gated():
    preview = subprocess.run(
        ["make", "-n", "event-alpha-observed-outcome-preview", "PYTHON=python3"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    assert "--event-alpha-observed-outcome-build" in preview
    assert "fixture-backed synthetic diagnostic outcome" in subprocess.run(
        ["make", "help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    assert "--out \"" not in preview
    assert "--confirm" not in preview
    assert "--json" in preview

    unconfirmed = subprocess.run(
        ["make", "-n", "event-alpha-observed-outcome-stage", "PYTHON=python3"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    assert "--out \"" in unconfirmed
    assert "--confirm" not in unconfirmed
    out_line = next(
        line.strip()
        for line in unconfirmed.splitlines()
        if line.strip().startswith("--out ")
    )
    out_value = shlex.split(out_line.removesuffix("\\").strip())[1]
    assert out_value
    assert Path(out_value).is_absolute()
    assert Path(out_value).parent == Path(out_value).parent.resolve()

    confirmed = subprocess.run(
        [
            "make",
            "-n",
            "event-alpha-observed-outcome-stage",
            "PYTHON=python3",
            "CONFIRM=1",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    assert "--out \"" in confirmed
    assert "--confirm" in confirmed


def test_observed_outcome_cli_preview_subprocess_is_read_only(tmp_path):
    result = subprocess.run(
        [sys.executable, "main.py", *_command_args("--json")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["mode"] == "preview"
    assert payload["written"] is False
    assert payload["outcome"]["research_only"] is True
    assert payload["outcome"]["calibration_eligible"] is False

    staged = tmp_path / "unconfirmed.jsonl"
    blocked = subprocess.run(
        [
            sys.executable,
            "main.py",
            *_command_args("--out", str(staged), "--json"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert blocked.returncode == 2
    assert "Traceback" not in blocked.stderr
    assert json.loads(blocked.stdout)["ok"] is False
    assert staged.exists() is False
