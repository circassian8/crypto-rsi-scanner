"""Current-window truth checks for the Event Alpha measurement dashboard."""

from __future__ import annotations

import json
from pathlib import Path

from crypto_rsi_scanner.event_alpha.operations import measurement


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_measurement_interpretation_uses_only_selected_current_window(tmp_path):
    selected = tmp_path / "selected"
    _write_jsonl(
        selected / "event_integrated_radar_candidates.jsonl",
        [
            {
                "candidate_id": "current-1",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "review_state": "near_miss",
            },
            {
                "candidate_id": "current-2",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "review_state": "quality_capped",
            },
            {
                "candidate_id": "current-3",
                "opportunity_type": "DIAGNOSTIC",
            },
        ],
    )
    historical = tmp_path / "notify_llm_deep_cryptopanic_rehearsal"
    _write_jsonl(
        historical / "event_integrated_radar_candidates.jsonl",
        [
            {
                "candidate_id": f"historical-{index}",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "provider": "historical-provider",
            }
            for index in range(59)
        ],
    )

    payload = measurement.build_measurement_dashboard(
        profile="live_burn_in_no_send",
        artifact_namespace="selected",
        base_dir=tmp_path,
    )
    current = payload["current_window_interpretation"]
    assert "first_real_run_interpretation" not in payload
    assert current["source"] == "selected_filtered_namespaces"
    assert current["included_namespace_count"] == 1
    assert current["real_burn_in_candidate_count"] == 0
    assert current["non_burn_in_candidate_count"] == 3
    assert current["near_miss_count"] == 1
    assert current["quality_capped_count"] == 1
    assert current["feedback_rows_eligible"] == 0
    assert current["outcome_rows_eligible"] == 0
    assert payload["auto_apply_thresholds"] is False

    rendered = measurement.format_measurement_dashboard(payload)
    assert "## Current Window Interpretation" in rendered
    assert "notify_llm_deep_cryptopanic_rehearsal" not in rendered
    assert "real_candidates: `59`" not in rendered
    assert "historical-provider" not in json.dumps(payload, sort_keys=True)
