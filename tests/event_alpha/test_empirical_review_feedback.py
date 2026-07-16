from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.operations.empirical_review import (
    build_targeted_review_queue,
)
from crypto_rsi_scanner.event_alpha.operations.empirical_review_feedback import (
    append_feedback_event,
    build_feedback_event,
    build_feedback_report,
    canonical_json_bytes,
    read_feedback_ledger,
    validate_feedback_event,
)
from crypto_rsi_scanner.event_alpha.operations import (
    empirical_replay_store,
    empirical_review_feedback_cli,
)


RUN_FINGERPRINT = "a" * 64
PROTOCOL_SHA256 = "b" * 64


def _queue(run_fingerprint: str = RUN_FINGERPRINT) -> dict[str, object]:
    missed = {
        "missed_move_id": "missed-move-v1:" + "d" * 64,
        "directional_bias": "long",
        "primary_endpoint_return_fraction": 0.20,
        "qualifies_as_missed_opportunity": True,
        "observation": {
            "canonical_asset_id": "bitcoin",
            "symbol": "BTC",
            "observed_at": "2022-01-01T00:00:00+00:00",
            "partition": "development",
            "data_quality_mode": "historical_ohlcv",
            "baseline_status": "warm",
            "liquidity_tier": "high",
            "observation_digest": "e" * 64,
        },
        "outcome": {
            "status": "matured",
            "primary_direction_adjusted_return": 0.20,
            "max_favorable_excursion": 0.25,
            "max_adverse_excursion": -0.03,
            "return_unit": "fraction",
        },
    }
    return build_targeted_review_queue(
        [],
        {"episodes": []},
        {"partitions": {}},
        {
            "protocol_version": "decision_radar_empirical_validation_v1",
            "protocol_sha256": PROTOCOL_SHA256,
            "contract_digest": "c" * 64,
            "evidence_mode": "historical_replay",
            "missed_move_evaluation": {
                "missed_opportunity_count": 1,
                "missed_opportunities": [missed],
            },
        },
        run_fingerprint=run_fingerprint,
    )


def _stored_queue(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    configuration = {
        "mode": "fixture_smoke",
        "research_only": True,
        "auto_apply": False,
    }
    input_sha = "d" * 64
    code_sha = "e" * 64
    fingerprint = empirical_replay_store.run_fingerprint(
        protocol_sha256=PROTOCOL_SHA256,
        input_sha256=input_sha,
        code_sha256=code_sha,
        configuration=configuration,
    )
    queue = _queue(fingerprint)
    stored = empirical_replay_store.write_immutable_run(
        tmp_path / "runs",
        protocol_version="decision_radar_empirical_validation_v1",
        protocol_sha256=PROTOCOL_SHA256,
        input_sha256=input_sha,
        code_sha256=code_sha,
        configuration=configuration,
        artifacts={
            "targeted_review_queue.json": empirical_replay_store.canonical_json_bytes(
                queue
            )
        },
        metrics={"targeted_review_item_count": queue["item_count"]},
        safety={
            "research_only": True,
            "auto_apply": False,
            "provider_calls": 0,
            "authorization_mutations": 0,
            "telegram_sends": 0,
            "trades": 0,
            "orders": 0,
            "event_alpha_paper_trades": 0,
            "normal_rsi_writes": 0,
            "event_alpha_triggered_fade": 0,
            "dashboard_authority_mutations": 0,
        },
    )
    return stored.run_dir, queue


def _event(
    queue: dict[str, object],
    *,
    label: str = "useful",
    event_id: str | None = None,
    observed_at: str = "2026-07-16T12:00:00+00:00",
) -> dict[str, object]:
    item = queue["items"][0]
    assert isinstance(item, dict)
    return build_feedback_event(
        queue,
        review_item_id=str(item["review_item_id"]),
        label=label,
        observed_at=observed_at,
        reviewer_alias="owner",
        label_event_id=event_id,
    )


def test_feedback_event_binds_exact_queue_item_and_safety() -> None:
    queue = _queue()
    event = _event(queue)
    item = queue["items"][0]

    assert validate_feedback_event(queue, event) == ()
    assert event["queue_digest"] == queue["queue_digest"]
    assert event["run_fingerprint"] == RUN_FINGERPRINT
    assert event["protocol_sha256"] == PROTOCOL_SHA256
    assert event["review_item_id"] == item["review_item_id"]
    assert event["review_item_evidence_digest"] == item["evidence_digest"]
    assert event["evidence_mode"] == "historical_replay"
    assert event["feedback_effect"] == "review_metadata_only"
    assert event["policy_eligible"] is False
    assert event["auto_apply"] is False
    assert set(event["safety"].values()) == {0}


def test_feedback_validation_rejects_taxonomy_mode_identity_and_alias_drift() -> None:
    queue = _queue()
    event = _event(queue)

    wrong_label = deepcopy(event)
    wrong_label["label"] = "raise_actionability_threshold"
    assert "label_outside_closed_taxonomy" in validate_feedback_event(queue, wrong_label)

    wrong_mode = deepcopy(event)
    wrong_mode["evidence_mode"] = "live_no_send"
    assert "evidence_mode_mismatch" in validate_feedback_event(queue, wrong_mode)

    secret_alias = deepcopy(event)
    secret_alias["reviewer_alias"] = "api_key=not-allowed"
    assert "reviewer_alias_invalid" in validate_feedback_event(queue, secret_alias)

    drifted_queue = deepcopy(queue)
    drifted_queue["run_fingerprint"] = "f" * 64
    assert "queue_digest_mismatch" in validate_feedback_event(drifted_queue, event)


def test_append_requires_confirmation_and_exact_retry_is_idempotent(
    tmp_path: Path,
) -> None:
    queue = _queue()
    event = _event(queue, event_id="human-label-001")
    ledger = tmp_path / "empirical_review_feedback.jsonl"

    with pytest.raises(PermissionError, match="confirmation_required"):
        append_feedback_event(ledger, queue, event, confirm=False)
    assert not ledger.exists()

    first = append_feedback_event(ledger, queue, event, confirm=True)
    original = ledger.read_bytes()
    second = append_feedback_event(ledger, queue, event, confirm=True)

    assert first["status"] == "appended"
    assert first["feedback_ledger_appends"] == 1
    assert second["status"] == "already_present"
    assert second["feedback_ledger_appends"] == 0
    assert ledger.read_bytes() == original == canonical_json_bytes(event) + b"\n"
    assert read_feedback_ledger(ledger, queue) == (event,)


def test_duplicate_event_id_with_different_valid_bytes_fails_closed(
    tmp_path: Path,
) -> None:
    queue = _queue()
    first = _event(queue, label="useful", event_id="human-label-001")
    changed = _event(queue, label="not_useful", event_id="human-label-001")
    ledger = tmp_path / "empirical_review_feedback.jsonl"

    append_feedback_event(ledger, queue, first, confirm=True)
    original = ledger.read_bytes()
    with pytest.raises(RuntimeError, match="label_event_id_drift"):
        append_feedback_event(ledger, queue, changed, confirm=True)

    assert ledger.read_bytes() == original
    assert read_feedback_ledger(ledger, queue) == (first,)


def test_ledger_rejects_symlinks_and_noncanonical_or_partial_rows(
    tmp_path: Path,
) -> None:
    queue = _queue()
    event = _event(queue)
    outside = tmp_path / "outside.jsonl"
    outside.write_bytes(b"")
    symlink = tmp_path / "feedback.jsonl"
    symlink.symlink_to(outside)

    with pytest.raises(RuntimeError, match="ledger_unsafe"):
        append_feedback_event(symlink, queue, event, confirm=True)
    assert outside.read_bytes() == b""

    noncanonical = tmp_path / "noncanonical.jsonl"
    noncanonical.write_text(json.dumps(event) + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="row_noncanonical"):
        read_feedback_ledger(noncanonical, queue)

    partial = tmp_path / "partial.jsonl"
    partial.write_bytes(canonical_json_bytes(event))
    with pytest.raises(RuntimeError, match="partial_row"):
        read_feedback_ledger(partial, queue)


def test_parent_symlink_is_rejected_without_creating_ledger(tmp_path: Path) -> None:
    queue = _queue()
    event = _event(queue)
    real_parent = tmp_path / "real"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    ledger = linked_parent / "feedback.jsonl"

    with pytest.raises(RuntimeError, match="parent_unsafe"):
        append_feedback_event(ledger, queue, event, confirm=True)
    assert not (real_parent / "feedback.jsonl").exists()


def test_feedback_report_is_bounded_and_evidence_mode_scoped() -> None:
    queue = _queue()
    events = [
        _event(
            queue,
            label=label,
            event_id=f"human-label-{index:03d}",
            observed_at=f"2026-07-16T12:0{index}:00+00:00",
        )
        for index, label in enumerate(("useful", "too_late", "useful"), 1)
    ]

    report = build_feedback_report(queue, events, maximum_events=2)

    assert report["event_count"] == 3
    assert report["reviewed_item_count"] == 1
    assert len(report["events"]) == 2
    assert report["events_truncated"] is True
    assert [row["evidence_mode"] for row in report["evidence_modes"]] == [
        "historical_replay"
    ]
    assert report["evidence_modes"][0]["label_counts"]["useful"] == 2
    assert report["cross_evidence_mode_conclusions_allowed"] is False
    assert report["descriptive_only"] is True
    assert report["policy_eligible"] is False
    assert report["auto_apply"] is False
    assert len(report["report_digest"]) == 64


def test_read_missing_ledger_is_a_bounded_empty_result(tmp_path: Path) -> None:
    assert read_feedback_ledger(tmp_path / "feedback.jsonl", _queue()) == ()


def test_feedback_cli_loads_queue_only_from_complete_immutable_run(
    tmp_path: Path,
) -> None:
    run_dir, expected = _stored_queue(tmp_path)
    queue, manifest = empirical_review_feedback_cli.load_verified_queue(run_dir)

    assert queue == expected
    assert manifest["run_fingerprint"] == expected["run_fingerprint"]
    (run_dir / "targeted_review_queue.json").write_bytes(b"{}\n")
    with pytest.raises(RuntimeError, match="manifest_invalid"):
        empirical_review_feedback_cli.load_verified_queue(run_dir)


def test_feedback_cli_report_is_read_only_and_mark_stays_confirmed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_dir, queue = _stored_queue(tmp_path)
    ledger = tmp_path / "human" / "feedback.jsonl"
    ledger.parent.mkdir()

    assert empirical_review_feedback_cli.main([
        "--run-dir", str(run_dir), "--ledger", str(ledger), "report"
    ]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["event_count"] == 0
    assert report["provider_calls"] == 0
    assert not ledger.exists()

    item = queue["items"][0]
    with pytest.raises(PermissionError, match="confirmation_required"):
        empirical_review_feedback_cli.main([
            "--run-dir", str(run_dir),
            "--ledger", str(ledger),
            "mark",
            "--review-item-id", str(item["review_item_id"]),
            "--label", "useful",
            "--observed-at", "2026-07-16T12:00:00+00:00",
            "--reviewer-alias", "owner",
        ])
    assert not ledger.exists()
