from __future__ import annotations

import socket
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.operations.empirical_replay_run import (
    execute_empirical_replay,
)
from crypto_rsi_scanner.event_alpha.operations.empirical_replay_store import (
    load_manifest,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = PROJECT_ROOT / "fixtures" / "backtest_smoke" / "klines"


def test_fixture_execution_is_immutable_resumable_bounded_and_authority_neutral(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_network(*_args, **_kwargs):
        raise AssertionError("empirical replay runner attempted network access")

    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    pointer = tmp_path / "radar_current_namespace.json"
    pointer.write_bytes(b'{"revision":123}\n')
    before = pointer.read_bytes()
    output = tmp_path / "research-lab"

    first = execute_empirical_replay(
        mode="fixture-smoke",
        input_dir=FIXTURES,
        output_root=output,
    )
    second = execute_empirical_replay(
        mode="fixture-smoke",
        input_dir=FIXTURES,
        output_root=output,
    )

    assert first.resumed is False
    assert second.resumed is True
    assert first.run_fingerprint == second.run_fingerprint
    assert first.run_dir == second.run_dir
    assert first.summary["idea_count"] > 0
    assert first.summary["episode_count"] > 0
    assert first.summary["matched_control_count"] >= 0
    assert first.summary["missed_endpoint_candidate_count"] >= 0
    assert sum(first.summary["benchmark_status_counts"].values()) == 8
    assert first.summary["evidence_strength_by_partition"]["fixture"] == "descriptive_only"
    assert first.summary["provider_calls"] == 0
    assert first.summary["dashboard_authority_mutations"] == 0
    assert pointer.read_bytes() == before
    assert not (output / "latest.json").exists()
    assert not (output / "radar_current_namespace.json").exists()
    manifest = load_manifest(first.run_dir)
    assert manifest["safety"]["provider_calls"] == 0
    assert manifest["safety"]["dashboard_authority_mutations"] == 0
    assert manifest["metrics"]["idea_count"] == first.summary["idea_count"]
    assert "replay_controls.json" in manifest["artifacts"]
    assert manifest["artifacts"]["replay_trace_examples.jsonl"]["size_bytes"] > 0


def test_existing_run_artifact_drift_fails_closed(tmp_path: Path) -> None:
    first = execute_empirical_replay(
        mode="fixture-smoke",
        input_dir=FIXTURES,
        output_root=tmp_path / "lab",
    )
    (first.run_dir / "runtime_report.json").write_text("{}\n")
    with pytest.raises(RuntimeError, match="manifest_invalid"):
        execute_empirical_replay(
            mode="fixture-smoke",
            input_dir=FIXTURES,
            output_root=tmp_path / "lab",
        )


def test_final_test_requires_valid_preexisting_seal_before_input_access(tmp_path: Path) -> None:
    missing_input = tmp_path / "does-not-exist"
    with pytest.raises(ValueError, match="requires a recommendation seal"):
        execute_empirical_replay(
            mode="final-test",
            input_dir=missing_input,
            output_root=tmp_path / "lab",
        )

    fake_seal = tmp_path / "seal.json"
    fake_seal.write_text("{}\n")
    with pytest.raises(ValueError, match="recommendation seal invalid"):
        execute_empirical_replay(
            mode="final-test",
            input_dir=missing_input,
            output_root=tmp_path / "lab",
            recommendation_seal_path=fake_seal,
        )


def test_non_final_mode_rejects_seal_before_input_access(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="only for final_test"):
        execute_empirical_replay(
            mode="medium",
            input_dir=tmp_path / "does-not-exist",
            output_root=tmp_path / "lab",
            recommendation_seal_path=tmp_path / "unused.json",
        )
