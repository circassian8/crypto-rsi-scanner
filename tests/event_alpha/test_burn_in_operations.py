"""Event Alpha burn-in operating artifact tests."""

from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from crypto_rsi_scanner.event_alpha.operations import archive, common, feedback_progress, measurement, review_inbox, scorecard, source_yield
from crypto_rsi_scanner.project_health import radar_north_star


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def test_burn_in_contract_generated_with_lanes_and_no_auto_apply(tmp_path):
    json_path, md_path, payload = radar_north_star.write_burn_in_contract(out_dir=tmp_path)
    assert json_path.exists()
    assert md_path.exists()
    assert payload["min_live_no_send_cycles"] == 20
    assert payload["min_real_candidates"] == 300
    assert payload["min_human_labels"] == 150
    assert payload["min_labeled_near_misses"] == 50
    assert payload["min_outcome_rows"] == 100
    assert payload["auto_apply_thresholds"] is False
    assert set(radar_north_star.LANE_NAMES).issubset(payload["opportunity_lanes"])
    assert payload["telegram_sends"] == 0
    assert payload["trades_created"] == 0
    assert payload["paper_trades_created"] == 0
    assert payload["normal_rsi_signal_rows_written"] == 0
    assert payload["triggered_fade_created"] == 0


def test_daily_review_inbox_groups_candidates_and_uses_stable_feedback_commands(tmp_path):
    ns = tmp_path / "burn"
    _write_jsonl(
        ns / "event_integrated_radar_candidates.jsonl",
        [
            {
                "canonical_asset_id": "asset:test",
                "symbol": "TEST",
                "coin_id": "test",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "opportunity_score": 72,
                "source_pack": "cryptopanic_context",
                "source_provider": "cryptopanic",
                "why_not_alertable": "needs confirmation",
            },
            {
                "canonical_asset_id": "asset:test",
                "symbol": "TEST",
                "coin_id": "test",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "opportunity_score": 61,
            },
        ],
    )
    payload = review_inbox.build_review_inbox(
        profile="live_burn_in_no_send",
        artifact_namespace="burn",
        base_dir=tmp_path,
        limit=10,
        now=datetime(2026, 7, 5, tzinfo=timezone.utc),
    )
    assert payload["items_count"] == 1
    assert payload["family_grouped"] is True
    assert payload["blockers"] == []
    commands = payload["items"][0]["suggested_feedback_commands"]
    assert any("event-feedback-source-noise" in command for command in commands)
    assert any("event-feedback-needs-confirmation" in command for command in commands)
    assert all("/tmp/" not in str(item.get("card_path")) for item in payload["items"])
    assert (ns / review_inbox.INBOX_JSON).exists()
    assert (ns / review_inbox.INBOX_MD).exists()


def test_feedback_progress_and_scorecard_keep_thresholds_frozen(tmp_path, monkeypatch):
    ns = tmp_path / "burn"
    _write_jsonl(
        ns / "event_alpha_feedback.jsonl",
        [
            {"target": "ea:1", "feedback_target": "ea:1", "label": "useful", "lane": "UNCONFIRMED_RESEARCH", "marked_at": "2026-07-05T00:00:00+00:00"},
            {"target": "ea:2", "feedback_target": "ea:2", "label": "source_noise", "lane": "UNCONFIRMED_RESEARCH", "marked_at": "2026-07-05T00:00:00+00:00"},
        ],
    )
    (ns / review_inbox.INBOX_JSON).write_text(
        json.dumps({"items": [{"feedback_target": "ea:1"}, {"feedback_target": "ea:3"}]}) + "\n",
        encoding="utf-8",
    )
    progress = feedback_progress.build_feedback_progress(
        profile="live_burn_in_no_send",
        artifact_namespace="burn",
        base_dir=tmp_path,
        now=datetime(2026, 7, 5, tzinfo=timezone.utc),
    )
    assert progress["labels_total"] == 2
    assert progress["label_coverage_pct"] == 50.0
    monkeypatch.setattr(
        scorecard.common,
        "load_contract",
        lambda: radar_north_star.build_burn_in_contract(generated_at=datetime(2026, 7, 5, tzinfo=timezone.utc)),
    )
    score = scorecard.build_scorecard(profile="live_burn_in_no_send", artifact_namespace="burn", base_dir=tmp_path)
    assert score["labels_collected"] == 2
    assert score["enough_data"] is False
    assert score["auto_apply_thresholds"] is False
    assert all(value == "frozen_insufficient_data" for value in score["promotion_freeze_status_by_lane"].values())


def test_weekly_measurement_and_source_yield_are_recommendations_only(tmp_path):
    ns = tmp_path / "burn"
    _write_jsonl(
        ns / "event_integrated_radar_candidates.jsonl",
        [
            {"candidate_id": "1", "opportunity_type": "UNCONFIRMED_RESEARCH", "provider": "cryptopanic", "source_pack": "cryptopanic_context"},
            {"candidate_id": "2", "opportunity_type": "DIAGNOSTIC", "provider": "rss", "source_pack": "rss_context"},
            {"candidate_id": "3", "opportunity_type": "UNCONFIRMED_RESEARCH", "provider": "coinalyze", "source_pack": "derivatives"},
        ],
    )
    _write_jsonl(
        ns / "event_alpha_feedback.jsonl",
        [
            {"feedback_target": "1", "label": "source_noise", "provider": "rss", "source_pack": "rss_context", "marked_at": "2026-07-05T00:00:00+00:00"},
        ],
    )
    dashboard = measurement.build_measurement_dashboard(
        profile="live_burn_in_no_send",
        artifact_namespace="burn",
        base_dir=tmp_path,
    )
    assert dashboard["diagnostic_rows_excluded_from_main_aggregate"] == 1
    assert dashboard["low_sample_warning"] is True
    assert dashboard["auto_apply_thresholds"] is False
    assert dashboard["first_real_run_interpretation"]["real_candidates"] == 59
    yield_report = source_yield.build_source_yield_report(
        profile="live_burn_in_no_send",
        artifact_namespace="burn",
        base_dir=tmp_path,
    )
    assert yield_report["recommendations_only"] is True
    assert yield_report["auto_apply"] is False
    assert yield_report["providers"]["coinalyze"]["recommended_action"] == "activate_next"


def test_burn_in_archive_excludes_secrets_and_db_files(tmp_path):
    ns = tmp_path / "event_fade_cache" / "live_burn_in_20260705"
    ns.mkdir(parents=True)
    (ns / "event_alpha_daily_brief.md").write_text("brief\n", encoding="utf-8")
    (ns / "readiness.md").write_text("configured with COINALYZE_API_KEY name only\n", encoding="utf-8")
    (ns / "local.db").write_text("db\n", encoding="utf-8")
    (ns / "bad.json").write_text('{"api_key":"should-not-archive"}\n', encoding="utf-8")
    payload = archive.build_burn_in_archive(base_dir=tmp_path / "event_fade_cache", out_dir=tmp_path / "out")
    assert payload["files_considered"] == 3
    assert payload["files_archived"] == 2
    assert payload["secret_hit_count"] == 1
    with zipfile.ZipFile(tmp_path / "out" / archive.ARCHIVE_NAME) as zf:
        assert zf.namelist() == [
            "live_burn_in_20260705/event_alpha_daily_brief.md",
            "live_burn_in_20260705/readiness.md",
        ]


def test_secret_scanner_ignores_natural_language_sk_phrase_but_catches_keys():
    assert common.secret_hits_in_text("a sk-fragmenting-global-financial-system narrative") == []
    assert common.secret_hits_in_text('"no_api_keys_in_tests": true') == []
    assert common.secret_hits_in_text('{"api_key":"should-not-archive"}') == ["api_key"]
    assert common.secret_hits_in_text("token sk-ABC1234567890defghijk") == ["sk-ABC1234567890defghijk"]
