"""Event Alpha burn-in operating artifact tests."""

from __future__ import annotations

import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from crypto_rsi_scanner.event_alpha.operations import archive, common, daily_burn_in, feedback_progress, measurement, namespace_policy, review_inbox, scorecard, source_yield
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
    assert payload["visible_family_grouped"] is True
    assert payload["items"][0]["visible_family_key"] == "asset:test"
    assert payload["items"][0]["duplicate_visible_family_count"] == 2
    assert payload["blockers"] == []
    commands = payload["items"][0]["suggested_feedback_commands"]
    assert any("event-feedback-source-noise" in command for command in commands)
    assert any("event-feedback-needs-confirmation" in command for command in commands)
    assert all("/tmp/" not in str(item.get("card_path")) for item in payload["items"])
    assert (ns / review_inbox.INBOX_JSON).exists()
    assert (ns / review_inbox.INBOX_MD).exists()


def test_daily_review_inbox_ranks_by_review_value_and_diversifies(tmp_path):
    ns = tmp_path / "burn"
    _write_jsonl(
        ns / "event_integrated_radar_candidates.jsonl",
        [
            {
                "canonical_asset_id": "asset:strong",
                "symbol": "STRONG",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "opportunity_score": 80,
                "source_pack": "official_exchange",
                "evidence_status": "accepted",
                "market_state_class": "breakout",
            },
                {
                    "canonical_asset_id": "asset:source",
                    "symbol": "SRC",
                    "opportunity_type": "UNCONFIRMED_RESEARCH",
                    "opportunity_score": 5,
                    "source_pack": "project_blog_rss",
                    "source_provider": "rss",
                    "why_not_alertable": "source-only narrative needs confirmation",
                },
            {
                "canonical_asset_id": "asset:zero",
                "symbol": "ZERO",
                "opportunity_type": "DIAGNOSTIC",
                "opportunity_score": 0,
            },
        ],
    )
    _write_jsonl(
        ns / "event_market_anomalies.jsonl",
        [
            {
                "canonical_asset_id": "asset:anom",
                "symbol": "ANOM",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "priority": 4,
                "market_state_class": "market_anomaly",
                "why_not_alertable": "missing catalyst",
            }
        ],
    )
    payload = review_inbox.build_review_inbox(
        profile="live_burn_in_no_send",
        artifact_namespace="burn",
        base_dir=tmp_path,
        limit=3,
        now=datetime(2026, 7, 5, tzinfo=timezone.utc),
    )
    assert payload["items"][0]["score"] > 0
    buckets = {row["diversity_bucket"] for row in payload["items"]}
    assert "source_only_narrative" in buckets
    assert "market_anomaly_missing_catalyst" in buckets
    assert any("generic_context_source_downranked" in row["review_value_reasons"] for row in payload["items"])
    assert "Review value" in (ns / review_inbox.INBOX_MD).read_text(encoding="utf-8")


def test_daily_review_inbox_collapses_visible_families_and_prioritizes_useful_review(tmp_path):
    ns = tmp_path / "burn"
    btc_rows = [
        {
            "core_opportunity_id": f"core:btc:{index}",
            "symbol": "BTC",
            "coin_id": "bitcoin",
            "opportunity_type": "UNCONFIRMED_RESEARCH",
            "opportunity_score": 1,
            "source_pack": "project_blog_rss",
            "source_provider": "rss",
            "why_not_alertable": "source-only narrative needs confirmation",
        }
        for index in range(6)
    ]
    _write_jsonl(
        ns / "event_integrated_radar_candidates.jsonl",
        [
            *btc_rows,
            {
                "canonical_asset_id": "asset:chiliz",
                "core_opportunity_id": "core:chz:1",
                "symbol": "CHZ",
                "coin_id": "chiliz",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "opportunity_score": 20,
                "source_pack": "official_exchange",
                "source_provider": "bybit",
                "evidence_status": "accepted",
                "accepted_evidence_count": 2,
                "market_state_class": "unknown",
            },
            {
                "canonical_asset_id": "asset:ethereum",
                "core_opportunity_id": "core:eth:1",
                "symbol": "ETH",
                "coin_id": "ethereum",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "opportunity_score": 2,
                "source_pack": "gdelt_context",
                "source_provider": "gdelt",
                "why_not_alertable": "source-only narrative needs confirmation",
            },
            {
                "canonical_asset_id": "asset:velvet",
                "core_opportunity_id": "core:velvet:1",
                "symbol": "VELVET",
                "coin_id": "velvet",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "opportunity_score": 4,
                "source_pack": "cryptopanic_context",
                "source_provider": "cryptopanic",
                "skipped": True,
                "skip_reason": "research review skipped pending source confirmation",
                "provider_gap": "needs Coinalyze confirmation",
            },
        ],
    )
    _write_jsonl(
        ns / "event_market_anomalies.jsonl",
        [
            {
                "canonical_asset_id": "asset:anom",
                "symbol": "ANOM",
                "coin_id": "anom",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "priority": 8,
                "market_state_class": "market_anomaly",
                "why_not_alertable": "missing catalyst",
            }
        ],
    )
    payload = review_inbox.build_review_inbox(
        profile="live_burn_in_no_send",
        artifact_namespace="burn",
        base_dir=tmp_path,
        limit=10,
        now=datetime(2026, 7, 5, tzinfo=timezone.utc),
    )
    symbols = [row["symbol"] for row in payload["items"]]
    assert symbols.count("BTC") == 1
    assert symbols.count("ETH") == 1
    assert "CHZ" in symbols
    assert "VELVET" in symbols
    assert symbols.index("CHZ") < symbols.index("BTC")
    btc_item = next(row for row in payload["items"] if row["symbol"] == "BTC")
    assert btc_item["duplicate_visible_family_count"] == 6
    assert "generic_context_source_downranked" in btc_item["review_value_reasons"]
    velvet_item = next(row for row in payload["items"] if row["symbol"] == "VELVET")
    assert "actionable_provider_source_gap" in velvet_item["review_value_reasons"]
    buckets = {row["diversity_bucket"] for row in payload["items"]}
    assert {"source_only_narrative", "market_anomaly_missing_catalyst", "accepted_evidence_no_market_confirmation"}.issubset(buckets)
    assert any(row["visible_family_key"] == "BTC:bitcoin:unconfirmed_research:context" for row in payload["family_summaries"])


def test_daily_burn_in_timeout_writes_artifact_and_progress(tmp_path, capsys, monkeypatch):
    step = daily_burn_in.BurnInStep(
        "timeout_fixture",
        (sys.executable, "-c", "import time; print('before timeout', flush=True); time.sleep(1)"),
        required=True,
        timeout_seconds=0.05,
    )
    monkeypatch.setattr(daily_burn_in, "build_steps", lambda **kwargs: (step,))
    payload = daily_burn_in.run_daily_burn_in(
        profile="fixture",
        artifact_namespace="burn_timeout",
        base_dir=tmp_path,
        python=sys.executable,
        continue_on_error=False,
        smoke=True,
    )
    out = capsys.readouterr().out
    assert "[burn-in] starting timeout_fixture" in out
    assert "[burn-in] finished timeout_fixture status=timeout" in out
    assert payload["steps_timeout"] == 1
    assert payload["required_failed"] == ["timeout_fixture"]
    saved = common.read_json(tmp_path / "burn_timeout" / daily_burn_in.RUN_JSON)
    assert saved["completed"] is True
    assert saved["steps"][0]["status"] == "timeout"
    assert saved["steps"][0]["timeout_seconds"] == 0.05


def test_daily_burn_in_plan_prints_without_writing_artifacts(tmp_path, capsys):
    rc = daily_burn_in.main(
        [
            "--profile",
            "live_burn_in_no_send",
            "--artifact-namespace",
            "plan_only",
            "--base-dir",
            str(tmp_path),
            "--python",
            sys.executable,
            "--dry-run-plan",
        ]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "Event Alpha Daily Live No-Send Burn-In Plan" in out
    assert "No live providers were run by default." in out
    assert "Coinalyze rehearsal skipped unless explicit allow flags are set." in out
    assert not (tmp_path / "plan_only" / daily_burn_in.RUN_JSON).exists()


def test_namespace_policy_includes_only_active_burn_in_by_default(tmp_path):
    live = tmp_path / "live_burn_in_20260705"
    active = tmp_path / "active_no_send"
    live_rehearsal = tmp_path / "full_llm_live"
    notify = tmp_path / "notify_llm"
    notify_no_key = tmp_path / "notify_no_key"
    no_key = tmp_path / "no_key_live"
    fixture = tmp_path / "fixture_smoke"
    integrated_smoke = tmp_path / "integrated_radar_smoke"
    provider = tmp_path / "coinalyze_no_send_rehearsal"
    live.mkdir()
    active.mkdir()
    live_rehearsal.mkdir()
    notify.mkdir()
    notify_no_key.mkdir()
    no_key.mkdir()
    fixture.mkdir()
    integrated_smoke.mkdir()
    provider.mkdir()
    (live / daily_burn_in.RUN_JSON).write_text('{"generated_at":"2026-07-05T00:00:00+00:00"}\n', encoding="utf-8")
    namespace_policy.namespace_status.write_namespace_status(
        active,
        {"namespace": "active_no_send", "status": "active_no_send_burn_in"},
    )
    namespace_policy.namespace_status.write_namespace_status(
        live_rehearsal,
        {"namespace": "full_llm_live", "status": namespace_policy.namespace_status.STATUS_ACTIVE_LIVE_REHEARSAL},
    )
    _write_jsonl(no_key / "event_integrated_radar_candidates.jsonl", [{"candidate_id": "no-key"}])
    _write_jsonl(fixture / "event_integrated_radar_candidates.jsonl", [{"candidate_id": "fixture"}])
    payload = namespace_policy.build_namespace_policy(
        profile="live_burn_in_no_send",
        artifact_namespace="policy",
        base_dir=tmp_path,
        write=False,
    )
    assert payload["included_namespaces"] == ["active_no_send", "live_burn_in_20260705"]
    for namespace in ("notify_llm", "notify_no_key", "no_key_live", "fixture_smoke", "integrated_radar_smoke", "coinalyze_no_send_rehearsal", "full_llm_live"):
        assert namespace in payload["excluded_namespaces"]
    assert "notification_rehearsal_excluded_from_default_burn_in_measurement" in payload["exclusion_reasons"]["notify_llm"]
    assert "no_key_live_excluded_from_default_burn_in_measurement" in payload["exclusion_reasons"]["no_key_live"]
    assert "fixture_or_smoke_namespace_excluded_by_default" in payload["exclusion_reasons"]["integrated_radar_smoke"]
    assert "provider_rehearsal_excluded_from_default_burn_in_measurement" in payload["exclusion_reasons"]["coinalyze_no_send_rehearsal"]
    assert "active_live_rehearsal_not_burn_in" in payload["exclusion_reasons"]["full_llm_live"]
    assert payload["active_live_rehearsal_excluded_count"] == 1
    assert payload["no_key_excluded_count"] >= 2
    assert payload["fixture_excluded_count"] >= 2
    assert payload["provider_rehearsal_excluded_count"] >= 1


def test_namespace_policy_explicit_flags_include_excluded_namespaces_and_stale_requires_flag(tmp_path):
    notify = tmp_path / "notify_llm"
    stale = tmp_path / "old_stale"
    notify.mkdir()
    stale.mkdir()
    namespace_policy.namespace_status.write_namespace_status(
        stale,
        {"namespace": "old_stale", "status": namespace_policy.namespace_status.STATUS_STALE_DEPRECATED},
    )
    default = namespace_policy.build_namespace_policy(profile="live_burn_in_no_send", artifact_namespace="policy", base_dir=tmp_path, write=False)
    assert "notify_llm" in default["excluded_namespaces"]
    assert "old_stale" in default["excluded_namespaces"]
    with_notify = namespace_policy.build_namespace_policy(
        profile="live_burn_in_no_send",
        artifact_namespace="policy",
        base_dir=tmp_path,
        include_notification_rehearsals=True,
        write=False,
    )
    assert "notify_llm" in with_notify["included_namespaces"]
    assert with_notify["include_reasons"]["notify_llm"] == "explicit_flag:include_notification_rehearsals"
    blocked_stale = namespace_policy.build_namespace_policy(
        profile="live_burn_in_no_send",
        artifact_namespace="policy",
        base_dir=tmp_path,
        include_namespaces=("old_stale",),
        write=False,
    )
    assert "old_stale" in blocked_stale["excluded_namespaces"]
    assert "explicit_namespace_is_stale_requires_include_stale" in blocked_stale["exclusion_reasons"]["old_stale"]
    with_stale = namespace_policy.build_namespace_policy(
        profile="live_burn_in_no_send",
        artifact_namespace="policy",
        base_dir=tmp_path,
        include_namespaces=("old_stale",),
        include_stale_namespaces=True,
        write=False,
    )
    assert "old_stale" in with_stale["included_namespaces"]


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


def test_scorecard_default_policy_excludes_no_key_live_candidates(tmp_path, monkeypatch):
    live = tmp_path / "live_burn_in_20260705"
    no_key = tmp_path / "no_key_live"
    live.mkdir()
    no_key.mkdir()
    (live / daily_burn_in.RUN_JSON).write_text('{"generated_at":"2026-07-05T00:00:00+00:00"}\n', encoding="utf-8")
    _write_jsonl(live / "event_integrated_radar_candidates.jsonl", [{"candidate_id": "live", "opportunity_type": "UNCONFIRMED_RESEARCH"}])
    _write_jsonl(no_key / "event_integrated_radar_candidates.jsonl", [{"candidate_id": "no-key", "opportunity_type": "UNCONFIRMED_RESEARCH"}])
    monkeypatch.setattr(
        scorecard.common,
        "load_contract",
        lambda: radar_north_star.build_burn_in_contract(generated_at=datetime(2026, 7, 5, tzinfo=timezone.utc)),
    )
    payload = scorecard.build_scorecard(profile="live_burn_in_no_send", base_dir=tmp_path)
    assert payload["namespace_scope"] == "policy"
    assert payload["included_namespaces"] == ["live_burn_in_20260705"]
    assert payload["real_candidates_seen"] == 1
    assert payload["real_burn_in_candidate_count"] == 1
    assert payload["no_key_candidate_count"] == 1
    assert "no_key_live" in payload["excluded_namespaces"]


def test_scorecard_explicit_notification_namespace_is_diagnostic_not_contract(tmp_path, monkeypatch):
    ns = tmp_path / "notify_llm_deep_cryptopanic_rehearsal"
    _write_jsonl(
        ns / "event_integrated_radar_candidates.jsonl",
        [{"candidate_id": "notify-1", "opportunity_type": "UNCONFIRMED_RESEARCH", "generated_at": "2026-07-05T00:00:00+00:00"}],
    )
    monkeypatch.setattr(
        scorecard.common,
        "load_contract",
        lambda: radar_north_star.build_burn_in_contract(generated_at=datetime(2026, 7, 5, tzinfo=timezone.utc)),
    )
    payload = scorecard.build_scorecard(
        profile="notify_llm_deep",
        artifact_namespace="notify_llm_deep_cryptopanic_rehearsal",
        base_dir=tmp_path,
    )
    assert payload["namespace_scope"] == "single_namespace"
    assert payload["include_reason"] == "explicit_user_namespace"
    assert payload["burn_in_contract_scope"] == "explicit_single_namespace_diagnostic"
    assert payload["included_namespaces"] == ["notify_llm_deep_cryptopanic_rehearsal"]
    assert payload["real_candidates_seen"] == 1
    assert payload["real_burn_in_candidate_count"] == 0
    assert payload["notification_rehearsal_candidate_count"] == 1
    assert payload["enough_data"] is False
    assert "explicit_namespace_not_counted_for_burn_in_contract" in payload["enough_data_reasons"]


def test_scorecard_no_active_burn_in_namespaces_points_to_next_command(tmp_path, monkeypatch):
    (tmp_path / "notify_llm").mkdir()
    monkeypatch.setattr(
        scorecard.common,
        "load_contract",
        lambda: radar_north_star.build_burn_in_contract(generated_at=datetime(2026, 7, 5, tzinfo=timezone.utc)),
    )
    payload = scorecard.build_scorecard(profile="live_burn_in_no_send", base_dir=tmp_path)
    assert payload["included_namespaces"] == []
    assert payload["enough_data"] is False
    assert "no_active_burn_in_namespaces" in payload["enough_data_reasons"]
    assert payload["next_command"]


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
    assert dashboard["evidence_scope"] == "explicit_single_namespace_diagnostic"
    assert dashboard["burn_in_contract_scope"] == "explicit_single_namespace_diagnostic"
    assert dashboard["explicit_scope_warning"]
    assert dashboard["real_burn_in_candidate_count"] == 0
    assert dashboard["non_burn_in_candidate_count"] == 3
    assert dashboard["diagnostic_rows_excluded_from_main_aggregate"] == 1
    assert dashboard["low_sample_warning"] is True
    assert dashboard["auto_apply_thresholds"] is False
    assert dashboard["first_real_run_interpretation"]["real_candidates"] == 59
    yield_report = source_yield.build_source_yield_report(
        profile="live_burn_in_no_send",
        artifact_namespace="burn",
        base_dir=tmp_path,
    )
    assert yield_report["evidence_scope"] == "explicit_single_namespace_diagnostic"
    assert yield_report["explicit_scope_warning"]
    assert yield_report["real_burn_in_candidate_count"] == 0
    assert yield_report["non_burn_in_candidate_count"] == 3
    assert yield_report["recommendations_only"] is True
    assert yield_report["auto_apply"] is False
    assert yield_report["providers"]["coinalyze"]["recommended_action"] == "activate_next"


def test_fixture_only_source_yield_reports_fixture_scope(tmp_path):
    ns = tmp_path / "fixture_smoke"
    _write_jsonl(
        ns / "event_integrated_radar_candidates.jsonl",
        [{"candidate_id": "fixture-1", "provider": "rss", "source_pack": "rss_context", "generated_at": "2026-07-05T00:00:00+00:00"}],
    )
    payload = source_yield.build_source_yield_report(
        profile="fixture",
        artifact_namespace="fixture_smoke",
        base_dir=tmp_path,
    )
    assert payload["evidence_scope"] == "fixture"
    assert payload["burn_in_contract_scope"] == "explicit_single_namespace_diagnostic"
    assert payload["enough_data"] is False
    assert payload["real_burn_in_candidate_count"] == 0
    assert payload["non_burn_in_candidate_count"] == 1


def test_burn_in_archive_excludes_secrets_and_db_files(tmp_path):
    ns = tmp_path / "event_fade_cache" / "live_burn_in_20260705"
    ns.mkdir(parents=True)
    (ns / daily_burn_in.RUN_JSON).write_text('{"generated_at":"2026-07-05T00:00:00+00:00"}\n', encoding="utf-8")
    (ns / "event_alpha_daily_brief.md").write_text("brief\n", encoding="utf-8")
    (ns / "readiness.md").write_text("configured with COINALYZE_API_KEY name only\n", encoding="utf-8")
    (ns / "local.db").write_text("db\n", encoding="utf-8")
    (ns / "bad.json").write_text('{"api_key":"should-not-archive"}\n', encoding="utf-8")
    payload = archive.build_burn_in_archive(base_dir=tmp_path / "event_fade_cache", out_dir=tmp_path / "out")
    assert payload["files_considered"] == 4
    assert payload["files_archived"] == 3
    assert payload["secret_hit_count"] == 1
    assert payload["included_namespaces"] == ["live_burn_in_20260705"]
    with zipfile.ZipFile(tmp_path / "out" / archive.ARCHIVE_NAME) as zf:
        assert zf.namelist() == [
            "live_burn_in_20260705/event_alpha_daily_brief.md",
            "live_burn_in_20260705/event_alpha_daily_burn_in_run.json",
            "live_burn_in_20260705/readiness.md",
        ]


def test_burn_in_archive_dry_run_writes_manifest_without_zip(tmp_path):
    ns = tmp_path / "event_fade_cache" / "live_burn_in_20260705"
    ns.mkdir(parents=True)
    (ns / daily_burn_in.RUN_JSON).write_text('{"generated_at":"2026-07-05T00:00:00+00:00"}\n', encoding="utf-8")
    (ns / "event_alpha_daily_brief.md").write_text("brief\n", encoding="utf-8")
    payload = archive.build_burn_in_archive(base_dir=tmp_path / "event_fade_cache", out_dir=tmp_path / "out", dry_run=True)
    assert payload["dry_run"] is True
    assert payload["archive_created"] is False
    assert payload["files_archived"] == 2
    assert not (tmp_path / "out" / archive.ARCHIVE_NAME).exists()
    assert (tmp_path / "out" / archive.MANIFEST_JSON).exists()


def test_burn_in_archive_default_excludes_notification_and_no_key_namespaces(tmp_path):
    base = tmp_path / "event_fade_cache"
    live = base / "live_burn_in_20260705"
    notify = base / "notify_llm"
    no_key = base / "no_key_live"
    for ns in (live, notify, no_key):
        ns.mkdir(parents=True)
        (ns / "event_alpha_daily_brief.md").write_text(f"{ns.name}\n", encoding="utf-8")
    (live / daily_burn_in.RUN_JSON).write_text('{"generated_at":"2026-07-05T00:00:00+00:00"}\n', encoding="utf-8")
    payload = archive.build_burn_in_archive(base_dir=base, out_dir=tmp_path / "out", dry_run=True)
    assert payload["dry_run"] is True
    assert payload["archive_scope"] == "active_burn_in_namespaces"
    assert payload["included_namespaces"] == ["live_burn_in_20260705"]
    assert "notify_llm" in payload["excluded_namespaces"]
    assert "no_key_live" in payload["excluded_namespaces"]
    assert payload["file_count_by_namespace"] == {"live_burn_in_20260705": 2}
    assert payload["checksum_manifest"]["file_count"] == 2


def test_burn_in_archive_explicit_no_key_flag_includes_no_key_namespace(tmp_path):
    base = tmp_path / "event_fade_cache"
    no_key = base / "no_key_live"
    no_key.mkdir(parents=True)
    (no_key / "event_alpha_daily_brief.md").write_text("no key\n", encoding="utf-8")
    payload = archive.build_burn_in_archive(
        base_dir=base,
        out_dir=tmp_path / "out",
        dry_run=True,
        include_no_key_namespaces=True,
    )
    assert payload["included_namespaces"] == ["no_key_live"]
    assert payload["explicit_include_flags"]["include_no_key_namespaces"] is True


def test_secret_scanner_ignores_natural_language_sk_phrase_but_catches_keys():
    assert common.secret_hits_in_text("a sk-fragmenting-global-financial-system narrative") == []
    assert common.secret_hits_in_text('"no_api_keys_in_tests": true') == []
    assert common.secret_hits_in_text('{"api_key":"should-not-archive"}') == ["api_key"]
    assert common.secret_hits_in_text("token sk-ABC1234567890defghijk") == ["sk-ABC1234567890defghijk"]
