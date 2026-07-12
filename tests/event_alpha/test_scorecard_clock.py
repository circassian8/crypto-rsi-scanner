"""Deterministic research-clock regressions for burn-in scorecards."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.operations import daily_burn_in, scorecard
from crypto_rsi_scanner.project_health import radar_north_star


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_authoritative_scorecard_fixed_clock_controls_window_and_generated_at(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fixed_now = datetime(2020, 1, 31, 12, 0, tzinfo=timezone.utc)
    namespace = tmp_path / "live_burn_in_20200131"
    namespace.mkdir()
    (namespace / daily_burn_in.RUN_JSON).write_text(
        '{"generated_at":"2020-01-31T11:00:00+00:00"}\n',
        encoding="utf-8",
    )
    _write_jsonl(
        namespace / "event_integrated_radar_candidates.jsonl",
        [
            {
                "candidate_id": "fixed-clock-candidate",
                "generated_at": "2020-01-31T11:00:00+00:00",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
            }
        ],
    )
    monkeypatch.setattr(
        scorecard.common,
        "load_contract",
        lambda: radar_north_star.build_burn_in_contract(generated_at=fixed_now),
    )

    payload = scorecard.build_authoritative_scorecard(
        base_dir=tmp_path,
        now=fixed_now,
    )

    assert payload["generated_at"] == fixed_now.isoformat()
    assert payload["window_days"] == 30
    assert payload["live_no_send_cycles_completed"] == 1
    assert payload["candidate_rows_seen"] == 1


def test_authoritative_scorecard_rejects_naive_clock(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        scorecard.build_authoritative_scorecard(
            base_dir=tmp_path,
            now=datetime(2020, 1, 31, 12, 0),
        )
