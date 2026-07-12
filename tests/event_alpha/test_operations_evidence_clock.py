"""Strict evidence-clock and Core-cohort regressions for operating reports."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.operations import (
    daily_burn_in,
    measurement,
    scorecard,
    source_yield,
)


def _write_json(path: Path, row: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _candidate(candidate_id: str, generated_at: str | None) -> dict[str, object]:
    row: dict[str, object] = {
        "row_type": "event_integrated_radar_candidate",
        "candidate_id": candidate_id,
        "opportunity_type": "UNCONFIRMED_RESEARCH",
    }
    if generated_at is not None:
        row["generated_at"] = generated_at
    return row


def _core(
    *,
    core_id: str,
    run_id: str,
    generated_at: datetime,
    near_miss: bool,
    quality_capped: bool,
) -> dict[str, object]:
    row: dict[str, object] = {
        "row_type": "event_core_opportunity",
        "core_opportunity_id": core_id,
        "run_id": run_id,
        "profile": "clocked",
        "artifact_namespace": "clocked",
        "generated_at": generated_at.isoformat(),
        "symbol": "NEAR" if near_miss else "CLEAR",
        "coin_id": "near" if near_miss else "clear",
        "opportunity_score_final": 60 if near_miss else 0,
        "opportunity_level": "local_only",
        "final_route_after_quality_gate": "STORE_ONLY",
        "impact_path_type": "direct_token_event",
        "candidate_role": "direct_instrument",
        "source_class": "official",
        "evidence_specificity": "strong",
        "market_confirmation_score": 20,
        "why_not_watchlist": "market_confirmation" if near_miss else "",
        "provider": "quality-near-provider",
        "reason": "quality cap and near miss prose must not classify this row",
    }
    if quality_capped:
        row["final_state_after_quality_gate"] = "QUALITY_BLOCKED"
    return row


def test_reports_share_one_closed_clock_and_stale_docs_cannot_change_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 7, 12, 12, 0, tzinfo=timezone.utc)
    cutoff = fixed_now - timedelta(days=7)
    namespace = tmp_path / "clocked"
    _write_jsonl(
        namespace / "event_integrated_radar_candidates.jsonl",
        [
            _candidate("at-cutoff", cutoff.isoformat()),
            _candidate("at-now", fixed_now.isoformat()),
            _candidate("stale", (cutoff - timedelta(microseconds=1)).isoformat()),
            _candidate("future", (fixed_now + timedelta(microseconds=1)).isoformat()),
            _candidate("naive", (fixed_now - timedelta(days=1)).replace(tzinfo=None).isoformat()),
            _candidate("missing", None),
        ],
    )
    _write_json(
        namespace / daily_burn_in.RUN_JSON,
        {"generated_at": (cutoff - timedelta(seconds=1)).isoformat()},
    )
    _write_json(
        namespace / daily_burn_in.CANDIDATE_MODE_MANIFEST_JSON,
        {
            "generated_at": (cutoff - timedelta(seconds=1)).isoformat(),
            "providers": {
                "stale-provider": {
                    "status": "ready_live_no_send",
                    "configured": True,
                    "allow_flag_set": True,
                    "live_call_allowed": True,
                }
            },
            "request_ledger_rows": {"stale-provider": 1},
        },
    )
    _write_json(
        namespace / "event_alpha_source_coverage.json",
        {"generated_at": cutoff.isoformat(), "provider": "boundary-provider"},
    )

    def unexpected_clock_read() -> datetime:
        raise AssertionError("explicit report clock must not recapture common.utc_now")

    monkeypatch.setattr(scorecard.common, "utc_now", unexpected_clock_read)
    score = scorecard.build_scorecard(
        profile="clocked",
        artifact_namespace="clocked",
        base_dir=tmp_path,
        days=7,
        now=fixed_now,
    )
    yield_report = source_yield.build_source_yield_report(
        profile="clocked",
        artifact_namespace="clocked",
        base_dir=tmp_path,
        days=7,
        now=fixed_now,
    )

    assert score["generated_at"] == fixed_now.isoformat()
    assert score["candidate_rows_seen"] == 2
    assert score["live_no_send_cycles_completed"] == 0
    assert score["burn_in_run_count"] == 0
    assert score["source_coverage_rows"] == 1
    assert score["provider_categories_observed"] == ["boundary-provider"]
    assert yield_report["generated_at"] == fixed_now.isoformat()
    assert yield_report["candidate_count"] == 2
    assert yield_report["live_cycles"] == 0
    assert yield_report["burn_in_run_count"] == 0
    assert yield_report["source_coverage_rows"] == 1
    assert "stale-provider" not in yield_report["providers"]
    assert "no_live_no_send_cycles" in yield_report["enough_data_reasons"]


def test_source_yield_json_docs_require_aware_timestamp_inside_exact_bounds(
    tmp_path: Path,
) -> None:
    fixed_now = datetime(2026, 7, 12, 12, 0, tzinfo=timezone.utc)
    cutoff = fixed_now - timedelta(days=7)
    timestamps = {
        "cutoff": cutoff.isoformat(),
        "now": fixed_now.isoformat(),
        "stale": (cutoff - timedelta(microseconds=1)).isoformat(),
        "future": (fixed_now + timedelta(microseconds=1)).isoformat(),
        "naive": (fixed_now - timedelta(days=1)).replace(tzinfo=None).isoformat(),
        "missing": None,
    }
    for namespace, generated_at in timestamps.items():
        row = {"row_type": "event_alpha_candidate_mode_manifest"}
        if generated_at is not None:
            row["generated_at"] = generated_at
        _write_json(
            tmp_path / namespace / daily_burn_in.CANDIDATE_MODE_MANIFEST_JSON,
            row,
        )

    rows = source_yield._namespace_json_docs(  # noqa: SLF001 - evidence boundary regression
        tmp_path,
        list(timestamps),
        daily_burn_in.CANDIDATE_MODE_MANIFEST_JSON,
        cutoff=cutoff,
        evaluated_at=fixed_now,
    )

    assert [row["generated_at"] for row in rows] == [
        cutoff.isoformat(),
        fixed_now.isoformat(),
    ]


def test_scorecard_core_cohort_is_run_scoped_deduped_and_prose_safe(
    tmp_path: Path,
) -> None:
    fixed_now = datetime(2026, 7, 12, 12, 0, tzinfo=timezone.utc)
    namespace = tmp_path / "clocked"
    shared = {
        "row_type": "event_integrated_radar_candidate",
        "candidate_id": "linked-candidate",
        "core_opportunity_id": "core:clear",
        "run_id": "run-clear",
        "profile": "clocked",
        "artifact_namespace": "clocked",
        "generated_at": (fixed_now - timedelta(hours=1)).isoformat(),
        "review_state": "near_miss",
        "state_quality_capped": True,
        "provider": "quality-near-provider",
        "reason": "near quality cap words are not an authoritative Core state",
    }
    _write_jsonl(namespace / "event_integrated_radar_candidates.jsonl", [shared])
    _write_jsonl(
        namespace / "event_core_opportunities.jsonl",
        [
            _core(
                core_id="core:near",
                run_id="run-one",
                generated_at=fixed_now - timedelta(hours=3),
                near_miss=False,
                quality_capped=False,
            ),
            _core(
                core_id="core:near",
                run_id="run-one",
                generated_at=fixed_now - timedelta(hours=2),
                near_miss=True,
                quality_capped=True,
            ),
            _core(
                core_id="core:near",
                run_id="run-two",
                generated_at=fixed_now - timedelta(hours=1),
                near_miss=True,
                quality_capped=True,
            ),
            _core(
                core_id="core:clear",
                run_id="run-clear",
                generated_at=fixed_now - timedelta(hours=1),
                near_miss=False,
                quality_capped=False,
            ),
        ],
    )

    payload = scorecard.build_scorecard(
        profile="clocked",
        artifact_namespace="clocked",
        base_dir=tmp_path,
        days=7,
        now=fixed_now,
    )

    assert payload["core_opportunities_seen"] == 3
    assert payload["research_candidates"] == 3
    assert payload["near_misses_seen"] == 2
    assert payload["quality_capped_rows"] == 2
    assert payload["near_misses"] == 2
    assert payload["quality_capped"] == 2


def test_source_yield_rejects_naive_explicit_clock(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        source_yield.build_source_yield_report(
            profile="clocked",
            artifact_namespace="clocked",
            base_dir=tmp_path,
            now=datetime(2026, 7, 12, 12, 0),
        )


def test_measurement_and_source_yield_require_all_five_contract_thresholds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 7, 12, 12, 0, tzinfo=timezone.utc)
    namespace = tmp_path / "live_burn_in_20260712"
    _write_json(
        namespace / daily_burn_in.RUN_JSON,
        {"generated_at": fixed_now.isoformat()},
    )
    feedback_rows = [{"feedback_id": f"feedback-{index}"} for index in range(150)]
    outcome_rows = [{"observation_id": f"outcome-{index}"} for index in range(100)]

    monkeypatch.setattr(
        measurement,
        "_load_dashboard_learning_evidence",
        lambda *_args: (
            [],
            [],
            list(outcome_rows),
            list(outcome_rows),
            [],
            {},
            [],
            list(feedback_rows),
            list(feedback_rows),
            [],
            {},
            {},
        ),
    )
    monkeypatch.setattr(
        source_yield,
        "_load_source_yield_learning_evidence",
        lambda *_args: (
            [],
            [],
            list(outcome_rows),
            list(outcome_rows),
            [],
            {},
            list(feedback_rows),
            list(feedback_rows),
            [],
            {},
            {},
        ),
    )

    dashboard = measurement.build_measurement_dashboard(
        profile="live_burn_in_no_send",
        base_dir=tmp_path,
        now=fixed_now,
    )
    yield_report = source_yield.build_source_yield_report(
        profile="live_burn_in_no_send",
        base_dir=tmp_path,
        now=fixed_now,
    )

    for payload in (dashboard, yield_report):
        assert payload["enough_data"] is False
        assert "min_live_no_send_cycles:1/20" in payload["enough_data_reasons"]
        assert "min_real_candidates:0/300" in payload["enough_data_reasons"]
        assert "min_labeled_near_misses:0/50" in payload["enough_data_reasons"]
        assert not any(
            reason.startswith("min_human_labels:")
            for reason in payload["enough_data_reasons"]
        )
        assert not any(
            reason.startswith("min_outcome_rows:")
            for reason in payload["enough_data_reasons"]
        )
