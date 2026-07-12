"""Strict external-clock coverage for the feedback progress report."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.operations import common, feedback_progress
from crypto_rsi_scanner.event_alpha.outcomes import feedback_eligibility


NOW = datetime(2026, 7, 12, 12, 0, tzinfo=timezone.utc)
PROFILE = "fixture"
NAMESPACE = "feedback_clock"
RUN_ID = "run-feedback-clock"


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _core(core_id: str) -> dict:
    return {
        "schema_id": "core_opportunity_v1",
        "schema_version": "event_core_opportunity_store_v1",
        "row_type": "event_core_opportunity",
        "run_id": RUN_ID,
        "profile": PROFILE,
        "artifact_namespace": NAMESPACE,
        "run_mode": "fixture",
        "core_opportunity_id": core_id,
        "feedback_target": core_id,
        "feedback_target_type": "core_opportunity_id",
        "generated_at": "2026-07-01T00:00:00+00:00",
        "research_only": True,
        "symbol": "CLOCK",
        "coin_id": "clock",
        "opportunity_type": "CONFIRMED_LONG_RESEARCH",
        "source_provider": "fixture_provider",
        "source_provider_domain": "fixture.example",
        "source_domain": "fixture.example",
        "source_pack": "fixture_pack",
        "source_class": "fixture",
        "lane": "CONFIRMED_LONG_RESEARCH",
        "playbook_type": "listing",
        "effective_playbook_type": "listing",
        "impact_path_type": "listing",
        "candidate_role": "direct_beneficiary",
        "opportunity_level": "high_priority",
        "final_opportunity_level": "high_priority",
        "final_route_after_quality_gate": "HIGH_PRIORITY_RESEARCH",
        "thesis_origin": "catalyst_led",
        "directional_bias": "long",
        "catalyst_status": "confirmed",
        "confidence_band": "high_confidence",
        "timing_state": "early",
        "tradability_status": "acceptable",
        "radar_route": "high_confidence_watch",
        "actionability_score_cohort": "80_89",
        "anomaly_type": "none",
    }


def _feedback(core_id: str, *, marked_at: str | None) -> dict:
    row = {
        "schema_version": "event_alpha_feedback_v1",
        "row_type": "event_alpha_feedback",
        "feedback_id": f"feedback:{core_id}",
        "run_id": RUN_ID,
        "profile": PROFILE,
        "artifact_namespace": NAMESPACE,
        "run_mode": "fixture",
        "core_opportunity_id": core_id,
        "target": core_id,
        "feedback_target": core_id,
        "feedback_target_type": "core_opportunity_id",
        "label": "useful",
        "marked_by": "human-reviewer",
        "source": "manual_cli",
        "research_only": True,
        # These must never substitute for the feedback contract's marked_at.
        "created_at": NOW.isoformat(),
        "feedback_marked_at": NOW.isoformat(),
    }
    if marked_at is not None:
        row["marked_at"] = marked_at
    row.update(feedback_eligibility.build_feedback_eligibility_fields(row))
    return row


def test_feedback_progress_uses_closed_explicit_marked_at_window(tmp_path):
    timestamps = {
        "week-start": (NOW - timedelta(days=7)).isoformat(),
        "today-start": (NOW - timedelta(days=1)).isoformat(),
        "window-end": NOW.isoformat(),
        "before-week": (NOW - timedelta(days=7, microseconds=1)).isoformat(),
        "future": (NOW + timedelta(microseconds=1)).isoformat(),
        "naive": (NOW - timedelta(hours=1)).replace(tzinfo=None).isoformat(),
        "missing": None,
    }
    context = common.context_for(
        profile=PROFILE,
        artifact_namespace=NAMESPACE,
        base_dir=tmp_path,
    )
    _write_jsonl(
        context.core_opportunity_store_path,
        [_core(f"core:{name}") for name in timestamps],
    )
    _write_jsonl(
        context.feedback_path,
        [
            _feedback(f"core:{name}", marked_at=marked_at)
            for name, marked_at in timestamps.items()
        ],
    )

    payload = feedback_progress.build_feedback_progress(
        profile=PROFILE,
        artifact_namespace=NAMESPACE,
        base_dir=tmp_path,
        days=7,
        now=NOW,
    )

    assert payload["generated_at"] == NOW.isoformat()
    assert payload["window_days"] == 7
    assert payload["labels_total"] == 4
    assert payload["feedback_rows_eligible"] == 4
    assert payload["feedback_rows_excluded"] == 3
    assert payload["labels_this_week"] == 3
    assert payload["labels_today"] == 2
    assert payload["research_only"] is True
    assert payload["telegram_sends"] == 0
    assert payload["trades_created"] == 0
    assert payload["paper_trades_created"] == 0


def test_marked_at_window_never_falls_back_to_other_timestamps():
    cutoff = NOW - timedelta(days=7)

    assert feedback_progress._marked_at_in_window(
        {"marked_at": cutoff.isoformat()}, cutoff=cutoff, generated=NOW
    )
    assert feedback_progress._marked_at_in_window(
        {"marked_at": NOW.isoformat()}, cutoff=cutoff, generated=NOW
    )
    for row in (
        {"created_at": NOW.isoformat()},
        {"feedback_marked_at": NOW.isoformat()},
        {"marked_at": NOW.replace(tzinfo=None).isoformat()},
        {"marked_at": (NOW + timedelta(microseconds=1)).isoformat()},
        {"marked_at": (cutoff - timedelta(microseconds=1)).isoformat()},
    ):
        assert not feedback_progress._marked_at_in_window(
            row, cutoff=cutoff, generated=NOW
        )


def test_feedback_progress_rejects_naive_external_clock_before_writing(tmp_path):
    with pytest.raises(ValueError, match="timezone-aware"):
        feedback_progress.build_feedback_progress(
            profile=PROFILE,
            artifact_namespace=NAMESPACE,
            base_dir=tmp_path,
            now=NOW.replace(tzinfo=None),
        )
    assert not (tmp_path / NAMESPACE).exists()


def test_feedback_progress_captures_implicit_clock_once(tmp_path, monkeypatch):
    calls = 0

    def _clock() -> datetime:
        nonlocal calls
        calls += 1
        return NOW

    monkeypatch.setattr(feedback_progress.common, "utc_now", _clock)
    payload = feedback_progress.build_feedback_progress(
        profile=PROFILE,
        artifact_namespace=NAMESPACE,
        base_dir=tmp_path,
    )

    assert calls == 1
    assert payload["generated_at"] == NOW.isoformat()
    assert payload["labels_today"] == 0
    assert payload["labels_this_week"] == 0


def test_feedback_progress_with_external_clock_never_recaptures_now(tmp_path, monkeypatch):
    def _unexpected_clock() -> datetime:
        raise AssertionError("external feedback-progress clock must be reused")

    monkeypatch.setattr(feedback_progress.common, "utc_now", _unexpected_clock)
    payload = feedback_progress.build_feedback_progress(
        profile=PROFILE,
        artifact_namespace=NAMESPACE,
        base_dir=tmp_path,
        now=NOW,
    )

    assert payload["generated_at"] == NOW.isoformat()
