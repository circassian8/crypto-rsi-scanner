"""Operator Experience V1 dashboard read-model regressions."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from crypto_rsi_scanner.event_alpha.artifacts import fingerprints
from crypto_rsi_scanner.event_alpha.dashboard import history as dashboard_history
from crypto_rsi_scanner.event_alpha.dashboard import loader as dashboard_loader


_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_BASE = _ROOT / "fixtures/event_alpha/radar_dashboard"
_NOW = "2026-07-12T06:03:00+00:00"


def _copy_namespace(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    target = tmp_path / "current"
    shutil.copytree(_FIXTURE_BASE / "current", target)
    state = json.loads((target / "event_alpha_operator_state.json").read_text())
    return target, state


def _write_state(namespace_dir: Path, state: dict[str, object]) -> None:
    (namespace_dir / "event_alpha_operator_state.json").write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _add_artifact(
    namespace_dir: Path,
    state: dict[str, object],
    name: str,
    path: Path,
    *,
    kind: str,
    count: int,
) -> None:
    state["artifacts"][name] = {
        "status": "current",
        "run_id": state["run_id"],
        "path": path.name,
        "reason": None,
        "generated_at": state["generated_at"],
        "count": count,
        **fingerprints.fingerprint_path(path, kind=kind),
    }


def _identity(state: dict[str, object]) -> dict[str, object]:
    return {
        "run_id": state["run_id"],
        "profile": state["profile"],
        "artifact_namespace": state["artifact_namespace"],
    }


def _attempt(index: int, *, latest: bool = False) -> dict[str, object]:
    return {
        "contract_version": 1,
        "row_type": (
            "event_market_no_send_latest_attempt"
            if latest
            else "event_market_no_send_attempt"
        ),
        "attempt_id": f"attempt-{index}",
        "recorded_at": f"2026-07-12T0{index}:01:00+00:00",
        "artifact_namespace": f"radar_market_no_send_{index}",
        "status": "complete",
        "observed_at": f"2026-07-12T0{index}:00:00+00:00",
        "run_id": f"run-{index}",
        "provider": "coingecko",
        "data_mode": "live",
        "data_acquisition_mode": "live_provider",
        "provider_call_attempted": True,
        "provider_request_succeeded": True,
        "candidate_source_mode": "live_no_send",
        "failure_class": None,
        "measurement_program": "decision_radar_live_observation_campaign_v2",
        "decision_radar_campaign_counted": True,
        "burn_in_counted": False,
        "no_send": True,
        "research_only": True,
        "authorization_header": "must-not-enter-the-read-model",
    }


def test_exact_generation_supporting_data_is_bounded_and_not_mixed_with_history(
    tmp_path,
    monkeypatch,
):
    namespace_dir, state = _copy_namespace(tmp_path)
    identity = _identity(state)

    history_rows = [
        {
            "schema_id": "event_alpha.market_history_observation",
            "schema_version": 1,
            "observation_id": f"mhobs-{index}",
            "coin_id": "alpha",
            "canonical_asset_id": "alpha",
            "symbol": "ALPHA",
            "observed_at": f"2026-07-12T0{index}:00:00+00:00",
            "price": float(index),
            "research_only": True,
        }
        for index in (1, 2, 3)
    ]
    history_path = namespace_dir / "event_market_history.jsonl"
    history_path.write_text(
        "".join(json.dumps(row) + "\n" for row in history_rows),
        encoding="utf-8",
    )
    _add_artifact(
        namespace_dir,
        state,
        "market_history",
        history_path,
        kind="jsonl_lines",
        count=3,
    )

    outcome_path = namespace_dir / "event_integrated_radar_outcomes.jsonl"
    outcome_path.write_text(
        json.dumps(
            {
                **identity,
                "row_type": "event_integrated_radar_outcome",
                "core_opportunity_id": "core:alpha",
                "symbol": "ALPHA",
                "opportunity_type": "DIAGNOSTIC",
                "outcome_status": "pending",
                "research_only": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _add_artifact(
        namespace_dir,
        state,
        "integrated_outcomes",
        outcome_path,
        kind="jsonl_lines",
        count=1,
    )

    ledger_path = namespace_dir / "event_market_no_send_request_ledger.json"
    ledger_path.write_text(
        json.dumps(
            {
                **identity,
                "contract_version": 2,
                "row_type": "event_market_no_send_request_ledger",
                "endpoint_path": "/coins/markets",
                "market_history_artifact": history_path.name,
                "market_history_sha256": hashlib.sha256(history_path.read_bytes()).hexdigest(),
                "research_only": True,
                "no_send": True,
                "telegram_sends": 0,
                "trades_created": 0,
                "paper_trades_created": 0,
                "normal_rsi_signal_rows_written": 0,
                "triggered_fade_created": 0,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _add_artifact(
        namespace_dir,
        state,
        "market_no_send_request_ledger",
        ledger_path,
        kind="file_bytes",
        count=1,
    )
    _write_state(namespace_dir, state)
    monkeypatch.setattr(dashboard_history, "DASHBOARD_EXACT_MARKET_HISTORY_LIMIT", 2)

    snapshot = dashboard_loader.load_dashboard_snapshot(tmp_path, "current", now=_NOW)

    assert snapshot.generation_authoritative is True
    assert [row["observation_id"] for row in snapshot.exact_market_history] == [
        "mhobs-2",
        "mhobs-3",
    ]
    assert snapshot.exact_market_history_metadata == {
        "authority": "current_generation_fingerprint_verified",
        "artifact_name": "market_history",
        "sha256": hashlib.sha256(history_path.read_bytes()).hexdigest(),
        "fingerprint_kind": "jsonl_lines",
        "source_row_count": 3,
        "returned_row_count": 2,
        "truncated": True,
        "error": None,
        "row_limit": 2,
    }
    assert len(snapshot.current_outcomes) == 1
    assert snapshot.cumulative_outcomes == ()
    assert snapshot.current_outcomes_metadata["authority"] == (
        "current_generation_fingerprint_verified"
    )
    assert snapshot.current_request_ledger["endpoint_path"] == "/coins/markets"
    assert snapshot.current_request_ledger_metadata["returned_row_count"] == 1


def test_campaign_history_is_bounded_projected_and_explicitly_non_authoritative(
    tmp_path,
    monkeypatch,
):
    _copy_namespace(tmp_path)
    monkeypatch.setattr(dashboard_history, "DASHBOARD_CAMPAIGN_ATTEMPT_LIMIT", 2)
    monkeypatch.setattr(dashboard_history, "DASHBOARD_CAMPAIGN_OUTCOME_LIMIT", 2)

    (tmp_path / "event_market_no_send_attempts.jsonl").write_text(
        "".join(json.dumps(_attempt(index)) + "\n" for index in (1, 2, 3)),
        encoding="utf-8",
    )
    (tmp_path / "event_market_no_send_latest_attempt.json").write_text(
        json.dumps(_attempt(3, latest=True)) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "event_decision_radar_campaign_reservation.json").write_text(
        json.dumps(
            {
                "contract_version": 1,
                "row_type": "decision_radar_campaign_reservation",
                "artifact_namespace": "radar_market_no_send_3",
                "status": "released",
                "acquired_at": "2026-07-12T03:00:00+00:00",
                "expires_at": "2026-07-12T03:15:00+00:00",
                "next_provider_call_at": "2026-07-12T04:00:00+00:00",
                "provider_call_reserved_at": "2026-07-12T03:00:00+00:00",
                "released_at": "2026-07-12T03:01:00+00:00",
                "previous_reservation_status": "released",
                "process_id": 12345,
                "no_send": True,
                "research_only": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    shared = tmp_path / "radar_market_history_cache"
    shared.mkdir()
    (shared / "event_decision_radar_campaign_outcomes.jsonl").write_text(
        "".join(
            json.dumps({"core_opportunity_id": f"core:{index}", "outcome_status": "pending"})
            + "\n"
            for index in (1, 2, 3)
        ),
        encoding="utf-8",
    )

    snapshot = dashboard_loader.load_dashboard_snapshot(tmp_path, "current", now=_NOW)

    assert snapshot.generation_authoritative is True
    assert [row["attempt_id"] for row in snapshot.campaign_attempts] == [
        "attempt-2",
        "attempt-3",
    ]
    assert all("authorization_header" not in row for row in snapshot.campaign_attempts)
    assert "authorization_header" not in snapshot.campaign_latest_attempt
    assert "process_id" not in snapshot.campaign_reservation
    assert snapshot.campaign_reservation["next_provider_call_at"] == (
        "2026-07-12T04:00:00+00:00"
    )
    assert [row["core_opportunity_id"] for row in snapshot.campaign_outcomes] == [
        "core:2",
        "core:3",
    ]
    for metadata in snapshot.campaign_history_metadata.values():
        assert metadata["authority"] == "historical_non_authoritative"
    assert snapshot.campaign_history_metadata["event_market_no_send_attempts.jsonl"][
        "truncated"
    ] is True
    assert snapshot.campaign_history_metadata[
        "radar_market_history_cache/event_decision_radar_campaign_outcomes.jsonl"
    ]["truncated"] is True


def test_campaign_root_ledger_symlink_is_fail_soft_and_never_grants_authority(tmp_path):
    _copy_namespace(tmp_path)
    outside = tmp_path / "outside-attempts.jsonl"
    outside.write_text(json.dumps(_attempt(1)) + "\n", encoding="utf-8")
    (tmp_path / "event_market_no_send_attempts.jsonl").symlink_to(outside)

    snapshot = dashboard_loader.load_dashboard_snapshot(tmp_path, "current", now=_NOW)

    assert snapshot.generation_authoritative is True
    assert snapshot.campaign_attempts == ()
    assert snapshot.campaign_history_metadata["event_market_no_send_attempts.jsonl"][
        "error"
    ] == "artifact_symlink_not_allowed"


def test_exact_snapshots_avoid_parsing_redundant_source_cache(tmp_path, monkeypatch):
    namespace_dir, state = _copy_namespace(tmp_path)
    identity = _identity(state)
    snapshots_path = namespace_dir / "event_market_state_snapshots.jsonl"
    snapshots_path.write_text(
        json.dumps(
            {
                **identity,
                "row_type": "event_market_state_snapshot",
                "symbol": "ALPHA",
                "coin_id": "alpha",
                "observed_at": "2026-07-12T06:01:30+00:00",
                "return_24h": 2.5,
                "return_unit": "percent_points",
                "research_only": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _add_artifact(
        namespace_dir,
        state,
        "market_state_snapshots",
        snapshots_path,
        kind="jsonl_lines",
        count=1,
    )
    source_cache_path = namespace_dir / "event_market_no_send_market_rows.json"
    source_cache_path.write_text(
        json.dumps({**identity, "selected_market_row_count": 0, "rows": []}) + "\n",
        encoding="utf-8",
    )
    _add_artifact(
        namespace_dir,
        state,
        "market_no_send_source_cache",
        source_cache_path,
        kind="file_bytes",
        count=1,
    )
    _write_state(namespace_dir, state)

    original = dashboard_loader._current_manifest_json
    parsed_artifacts: list[str] = []

    def tracking_parser(blob, artifact_name, **kwargs):
        parsed_artifacts.append(artifact_name)
        return original(blob, artifact_name, **kwargs)

    monkeypatch.setattr(dashboard_loader, "_current_manifest_json", tracking_parser)
    snapshot = dashboard_loader.load_dashboard_snapshot(tmp_path, "current", now=_NOW)

    assert snapshot.generation_authoritative is True
    assert len(snapshot.current_market_observations) == 1
    assert "market_no_send_source_cache" not in parsed_artifacts
