"""Event Alpha burn-in operating artifact tests."""

from __future__ import annotations

import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from crypto_rsi_scanner.event_alpha.artifacts import paths as event_artifact_paths
from crypto_rsi_scanner.event_alpha.doctor.checks import operations as doctor_operations_checks
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
    assert payload["items"][0]["primary_visible_family_key"] == "TEST:test"
    assert payload["items"][0]["secondary_visible_family_key"].startswith("TEST:test:")
    assert payload["items"][0]["duplicate_visible_family_count"] == 2
    assert payload["items"][0]["symbol_duplicate_count"] == 2
    assert payload["items"][0]["candidate_provenance"] == "integrated_candidate"
    assert payload["items"][0]["source_artifact"] == "event_integrated_radar_candidates.jsonl"
    assert payload["items"][0]["source_artifact_row_type"] == "integrated_candidate"
    assert payload["items"][0]["real_candidate_evidence"] is True
    assert payload["items"][0]["contract_counted_candidate"] is True
    assert payload["blockers"] == []
    commands = payload["items"][0]["suggested_feedback_commands"]
    assert any("event-feedback-source-noise" in command for command in commands)
    assert any("event-feedback-needs-confirmation" in command for command in commands)
    assert all("/tmp/" not in str(item.get("card_path")) for item in payload["items"])
    assert (ns / review_inbox.INBOX_JSON).exists()
    assert (ns / review_inbox.INBOX_MD).exists()
    md = (ns / review_inbox.INBOX_MD).read_text(encoding="utf-8")
    assert "Provenance" in md
    assert "Counts toward burn-in candidate evidence" in md


def test_daily_review_inbox_normalizes_absolute_temp_card_paths(tmp_path):
    ns = tmp_path / "burn"
    card = ns / "research_cards" / "core_early.md"
    card.parent.mkdir(parents=True)
    card.write_text("# EARLY card\n", encoding="utf-8")
    _write_jsonl(
        ns / "event_integrated_radar_candidates.jsonl",
        [
            {
                "candidate_id": "cand:early",
                "symbol": "EARLY",
                "coin_id": "early",
                "opportunity_type": "EARLY_LONG_RESEARCH",
                "opportunity_score": 70,
                "candidate_provenance": "integrated_candidate",
                "source_artifact": "event_integrated_radar_candidates.jsonl",
                "card_path": str(card),
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
    item = payload["items"][0]
    assert payload["blockers"] == []
    assert item["card_path"] == "burn/research_cards/core_early.md"
    assert not Path(item["card_path"]).is_absolute()
    assert (tmp_path / item["card_path"]).exists()
    rendered = (ns / review_inbox.INBOX_MD).read_text(encoding="utf-8")
    assert not event_artifact_paths.has_operator_absolute_path(payload)
    assert str(tmp_path) not in json.dumps(payload)
    assert str(tmp_path) not in rendered
    assert "/tmp/" not in rendered
    assert "/mnt/data/" not in rendered
    assert "/Users/" not in rendered


def test_daily_review_inbox_blocks_missing_relative_card_path(tmp_path):
    ns = tmp_path / "burn"
    _write_jsonl(
        ns / "event_integrated_radar_candidates.jsonl",
        [
            {
                "candidate_id": "cand:missing",
                "symbol": "MISS",
                "coin_id": "miss",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "opportunity_score": 52,
                "candidate_provenance": "integrated_candidate",
                "source_artifact": "event_integrated_radar_candidates.jsonl",
                "card_path": "burn/research_cards/missing.md",
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
    assert any("stale_or_missing_review_path:missing:burn/research_cards/missing.md" in blocker for blocker in payload["blockers"])


def test_daily_review_inbox_prioritizes_contract_counted_candidates(tmp_path):
    ns = tmp_path / "burn"
    _write_jsonl(
        ns / "event_integrated_radar_candidates.jsonl",
        [
            {
                "row_type": "event_integrated_radar_candidate",
                "candidate_id": "support",
                "symbol": "SUPPORT",
                "coin_id": "support",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "opportunity_score_final": 95,
                "source_pack": "cryptopanic_context",
                "source_origin": "cryptopanic",
                "candidate_source_mode": "artifact_replay",
                "contract_counted_candidate": False,
            },
            {
                "row_type": "event_integrated_radar_candidate",
                "candidate_id": "live",
                "symbol": "LIVE",
                "coin_id": "live",
                "opportunity_type": "CONFIRMED_LONG_RESEARCH",
                "opportunity_score_final": 25,
                "source_pack": "official_exchange_listing_pack",
                "source_origin": "bybit_announcements",
                "provider": "bybit_announcements",
                "candidate_source_mode": "live_no_send",
                "request_ledger_path": "burn/event_bybit_announcements_request_ledger.jsonl",
                "contract_counted_candidate": True,
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
    assert payload["items"][0]["symbol"] == "LIVE"
    assert payload["items"][0]["contract_counted_candidate"] is True
    md = (ns / review_inbox.INBOX_MD).read_text(encoding="utf-8")
    assert "## Contract-Counted Burn-In Candidates" in md
    assert "## High-Value Non-Counted Review Candidates" in md
    assert "## Diagnostics / Support" in md
    assert md.index("LIVE / live") < md.index("SUPPORT / support")


def test_daily_review_inbox_reports_no_real_candidate_evidence(tmp_path):
    ns = tmp_path / "burn"
    _write_jsonl(
        ns / "event_integrated_radar_candidates.jsonl",
        [
            {
                "row_type": "event_integrated_radar_candidate",
                "candidate_id": "support",
                "symbol": "SUPPORT",
                "coin_id": "support",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "candidate_source_mode": "artifact_replay",
                "contract_counted_candidate": False,
            }
        ],
    )
    review_inbox.build_review_inbox(
        profile="live_burn_in_no_send",
        artifact_namespace="burn",
        base_dir=tmp_path,
        limit=10,
        now=datetime(2026, 7, 5, tzinfo=timezone.utc),
    )
    md = (ns / review_inbox.INBOX_MD).read_text(encoding="utf-8")
    assert "No contract-counted burn-in candidates yet." in md
    assert "No real candidate evidence yet." in md


def test_daily_review_inbox_records_core_and_skipped_notification_provenance(tmp_path):
    ns = tmp_path / "burn"
    _write_jsonl(
        ns / "event_core_opportunities.jsonl",
        [
            {
                "core_opportunity_id": "core:1",
                "symbol": "CORE",
                "coin_id": "core",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "opportunity_score": 34,
                "why_not_alertable": "needs evidence review",
            }
        ],
    )
    _write_jsonl(
        ns / "event_alpha_alerts.jsonl",
        [
            {
                "alert_key": "alert:1",
                "symbol": "SKIP",
                "coin_id": "skip",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "opportunity_score": 21,
                "skipped": True,
                "skip_reason": "research review skipped pending confirmation",
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
    by_symbol = {row["symbol"]: row for row in payload["items"]}
    assert by_symbol["CORE"]["candidate_provenance"] == "core_opportunity"
    assert by_symbol["CORE"]["contract_counted_candidate"] is False
    assert by_symbol["SKIP"]["candidate_provenance"] == "notification_skipped_candidate"
    assert by_symbol["SKIP"]["source_artifact"] == "event_alpha_alerts.jsonl"


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
    assert all(row["opportunity_type"] != "DIAGNOSTIC" for row in payload["items"])
    assert any("generic_context_source_downranked" in row["downrank_reason_codes"] for row in payload["items"])
    assert "Review value" in (ns / review_inbox.INBOX_MD).read_text(encoding="utf-8")


def test_daily_review_inbox_uses_specific_fallback_reason_codes(tmp_path):
    ns = tmp_path / "burn"
    _write_jsonl(
        ns / "event_integrated_radar_candidates.jsonl",
        [
            {
                "canonical_asset_id": "asset:plain",
                "symbol": "PLAIN",
                "coin_id": "plain",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "opportunity_score": 3,
                "source_pack": "manual_context",
                "source_provider": "manual",
                "market_state_class": "unknown",
                "evidence_status": "needs_review",
            }
        ],
    )
    payload = review_inbox.build_review_inbox(
        profile="live_burn_in_no_send",
        artifact_namespace="burn",
        base_dir=tmp_path,
        limit=1,
        now=datetime(2026, 7, 5, tzinfo=timezone.utc),
    )
    reasons = payload["items"][0]["review_value_reason_codes"]
    assert "highest_remaining_review_value" not in reasons
    assert "source_only_context_review" in reasons
    assert "missing_strong_source_review" in reasons
    assert "missing_market_confirmation_review" in reasons


def test_daily_review_inbox_derives_specific_reasons_from_alertability_gaps(tmp_path):
    ns = tmp_path / "burn"
    _write_jsonl(
        ns / "event_integrated_radar_candidates.jsonl",
        [
            {
                "canonical_asset_id": "asset:sourcegap",
                "symbol": "SRCGAP",
                "coin_id": "sourcegap",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "opportunity_score": 30,
                "source_pack": "official_exchange_listing_pack",
                "market_state_class": "unknown",
                "why_not_alertable": ["strong_source_missing", "market_reaction_missing"],
                "evidence_status": "needs_review",
            },
            {
                "canonical_asset_id": "asset:anomgap",
                "symbol": "ANOMGAP",
                "coin_id": "anomgap",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "opportunity_score": 25,
                "source_pack": "market_anomaly_pack",
                "market_state_class": "confirmed_breakout",
                "why_not_alertable": "catalyst missing",
                "evidence_status": "needs_review",
            },
        ],
    )
    payload = review_inbox.build_review_inbox(
        profile="live_burn_in_no_send",
        artifact_namespace="burn",
        base_dir=tmp_path,
        limit=2,
        now=datetime(2026, 7, 5, tzinfo=timezone.utc),
    )
    by_symbol = {row["symbol"]: row for row in payload["items"]}
    source_reasons = by_symbol["SRCGAP"]["review_value_reason_codes"]
    assert "missing_strong_source_review" in source_reasons
    assert "missing_market_confirmation_review" in source_reasons
    assert "accepted_evidence_found" not in source_reasons
    anomaly_reasons = by_symbol["ANOMGAP"]["review_value_reason_codes"]
    assert "market_anomaly_missing_catalyst" in anomaly_reasons


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
    assert btc_item["symbol_duplicate_count"] == 6
    assert "generic_context_source_downranked" in btc_item["downrank_reason_codes"]
    velvet_item = next(row for row in payload["items"] if row["symbol"] == "VELVET")
    assert "high_value_skipped_family" in velvet_item["review_value_reason_codes"]
    assert "provider_confirmation_gap" in velvet_item["review_value_reason_codes"]
    buckets = {row["diversity_bucket"] for row in payload["items"]}
    assert {"source_only_narrative", "market_anomaly_missing_catalyst", "accepted_evidence_no_market_confirmation"}.issubset(buckets)
    assert any(row["visible_family_key"] == "BTC:bitcoin:unconfirmed_research:context" for row in payload["family_summaries"])
    assert any(row["primary_visible_family_key"] == "BTC:bitcoin" for row in payload["collapsed_family_summary"])
    assert all(row["symbol_family_rank"] == 1 for row in payload["items"])


def test_daily_review_inbox_allows_second_same_symbol_only_for_high_value_bucket(tmp_path):
    ns = tmp_path / "burn"
    _write_jsonl(
        ns / "event_integrated_radar_candidates.jsonl",
        [
            {
                "symbol": "CHZ",
                "coin_id": "chiliz",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "opportunity_score": 40,
                "source_pack": "official_exchange",
                "source_provider": "bybit",
                "accepted_evidence_count": 1,
                "market_state_class": "unknown",
            },
            {
                "symbol": "CHZ",
                "coin_id": "chiliz",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "opportunity_score": 35,
                "source_pack": "cryptopanic_context",
                "source_provider": "cryptopanic",
                "provider_gap": "needs Coinalyze confirmation",
                "skip_reason": "research review skipped pending confirmation",
            },
            {
                "symbol": "BTC",
                "coin_id": "bitcoin",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "opportunity_score": 10,
                "source_pack": "gdelt_context",
                "source_provider": "gdelt",
            },
            {
                "symbol": "BTC",
                "coin_id": "bitcoin",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "opportunity_score": 9,
                "source_pack": "project_blog_rss",
                "source_provider": "rss",
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
    symbols = [row["symbol"] for row in payload["items"]]
    assert symbols.count("CHZ") == 2
    assert symbols.count("BTC") == 1
    second_chz = [row for row in payload["items"] if row["symbol"] == "CHZ" and row["symbol_family_rank"] == 2][0]
    assert second_chz["allowed_second_family_reason"].startswith("high_value_secondary:")


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
    assert saved["steps"][0]["required"] is True
    assert saved["steps"][0]["command"]
    assert saved["steps"][0]["started_at"]
    assert saved["steps"][0]["finished_at"]


def test_daily_burn_in_skipped_step_records_skip_metadata(tmp_path, monkeypatch):
    skipped = {
        "name": "coinalyze_no_send_rehearsal",
        "status": "skipped",
        "timeout_seconds": 7,
        "skip_reason": "explicitly disabled for fixture",
    }
    monkeypatch.setattr(daily_burn_in, "build_steps", lambda **kwargs: (skipped,))
    payload = daily_burn_in.run_daily_burn_in(
        profile="fixture",
        artifact_namespace="burn_skipped",
        base_dir=tmp_path,
        python=sys.executable,
        smoke=True,
    )
    row = payload["steps"][0]
    assert row["status"] == "skipped"
    assert row["required"] is False
    assert row["timeout_seconds"] == 7
    assert row["skip_reason"] == "explicitly disabled for fixture"
    assert row["started_at"]
    assert row["finished_at"]


def test_daily_burn_in_default_remains_no_candidate_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_burn_in, "build_steps", lambda **kwargs: ())
    payload = daily_burn_in.run_daily_burn_in(
        profile="live_burn_in_no_send",
        artifact_namespace="burn_default",
        base_dir=tmp_path,
        python=sys.executable,
    )
    assert payload["candidate_mode"] is False
    assert payload["live_provider_calls_allowed"] is False
    assert payload["telegram_sends"] == 0
    assert payload["trades_created"] == 0
    assert payload["paper_trades_created"] == 0
    assert payload["normal_rsi_signal_rows_written"] == 0
    assert payload["triggered_fade_created"] == 0
    assert not (tmp_path / "burn_default" / daily_burn_in.CANDIDATE_MODE_MANIFEST_JSON).exists()


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
    no_run = tmp_path / "live_burn_in_no_send"
    live_rehearsal = tmp_path / "full_llm_live"
    notify = tmp_path / "notify_llm"
    notify_no_key = tmp_path / "notify_no_key"
    no_key = tmp_path / "no_key_live"
    fixture = tmp_path / "fixture_smoke"
    integrated_smoke = tmp_path / "integrated_radar_smoke"
    provider = tmp_path / "coinalyze_no_send_rehearsal"
    live.mkdir()
    active.mkdir()
    no_run.mkdir()
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
    _write_jsonl(no_run / "event_integrated_radar_candidates.jsonl", [{"candidate_id": "no-run"}])
    _write_jsonl(fixture / "event_integrated_radar_candidates.jsonl", [{"candidate_id": "fixture"}])
    payload = namespace_policy.build_namespace_policy(
        profile="live_burn_in_no_send",
        artifact_namespace="policy",
        base_dir=tmp_path,
        write=False,
    )
    assert payload["namespace_policy_version"] == "burn_in_namespace_policy_v3"
    assert payload["included_namespaces"] == ["live_burn_in_20260705"]
    for namespace in ("active_no_send", "live_burn_in_no_send", "notify_llm", "notify_no_key", "no_key_live", "fixture_smoke", "integrated_radar_smoke", "coinalyze_no_send_rehearsal", "full_llm_live"):
        assert namespace in payload["excluded_namespaces"]
    assert "active_burn_in_status_without_daily_burn_in_run_artifact" in payload["exclusion_reasons"]["active_no_send"]
    assert "live_burn_in_namespace_without_daily_burn_in_run_artifact" in payload["exclusion_reasons"]["live_burn_in_no_send"]
    assert "notification_rehearsal_excluded_from_default_burn_in_measurement" in payload["exclusion_reasons"]["notify_llm"]
    assert "no_key_live_excluded_from_default_burn_in_measurement" in payload["exclusion_reasons"]["no_key_live"]
    assert "fixture_or_smoke_namespace_excluded_by_default" in payload["exclusion_reasons"]["integrated_radar_smoke"]
    assert "provider_rehearsal_excluded_from_default_burn_in_measurement" in payload["exclusion_reasons"]["coinalyze_no_send_rehearsal"]
    assert "active_live_rehearsal_not_burn_in" in payload["exclusion_reasons"]["full_llm_live"]
    assert payload["active_live_rehearsal_excluded_count"] == 1
    assert payload["no_key_excluded_count"] >= 2
    assert payload["fixture_excluded_count"] >= 2
    assert payload["provider_rehearsal_excluded_count"] >= 1
    assert payload["included_without_burn_in_run_count"] == 0


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
    assert with_notify["included_without_burn_in_run_count"] == 1
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
    assert progress["labels_total"] == 0
    assert progress["label_coverage_pct"] == 0.0
    assert progress["feedback_rows_supplied"] == 2
    assert progress["feedback_rows_excluded"] == 2
    monkeypatch.setattr(
        scorecard.common,
        "load_contract",
        lambda: radar_north_star.build_burn_in_contract(generated_at=datetime(2026, 7, 5, tzinfo=timezone.utc)),
    )
    score = scorecard.build_scorecard(profile="live_burn_in_no_send", artifact_namespace="burn", base_dir=tmp_path)
    assert score["labels_collected"] == 0
    assert score["feedback_rows_supplied"] == 2
    assert score["feedback_rows_excluded"] == 2
    assert score["feedback_exclusion_reason_counts"]["legacy_feedback_contract"] == 2
    assert score["enough_data"] is False
    assert score["auto_apply_thresholds"] is False
    assert all(value == "frozen_insufficient_data" for value in score["promotion_freeze_status_by_lane"].values())


def test_scorecard_default_policy_excludes_no_key_live_candidates(tmp_path, monkeypatch):
    fixed_now = datetime(2026, 7, 12, tzinfo=timezone.utc)
    live = tmp_path / "live_burn_in_20260705"
    no_key = tmp_path / "no_key_live"
    live.mkdir()
    no_key.mkdir()
    (live / daily_burn_in.RUN_JSON).write_text('{"generated_at":"2026-07-05T00:00:00+00:00"}\n', encoding="utf-8")
    _write_jsonl(live / "event_integrated_radar_candidates.jsonl", [{"candidate_id": "live", "opportunity_type": "UNCONFIRMED_RESEARCH", "generated_at": fixed_now.isoformat()}])
    _write_jsonl(no_key / "event_integrated_radar_candidates.jsonl", [{"candidate_id": "no-key", "opportunity_type": "UNCONFIRMED_RESEARCH", "generated_at": fixed_now.isoformat()}])
    monkeypatch.setattr(
        scorecard.common,
        "load_contract",
        lambda: radar_north_star.build_burn_in_contract(generated_at=datetime(2026, 7, 5, tzinfo=timezone.utc)),
    )
    payload = scorecard.build_scorecard(
        profile="live_burn_in_no_send",
        base_dir=tmp_path,
        now=fixed_now,
    )
    assert payload["namespace_scope"] == "policy"
    assert payload["included_namespaces"] == ["live_burn_in_20260705"]
    assert payload["evidence_scope"] == "active_burn_in_no_candidate_evidence"
    assert payload["candidate_rows_seen"] == 1
    assert payload["real_candidates_seen"] == 0
    assert payload["real_burn_in_candidate_count"] == 0
    assert payload["contract_counted_candidate_count"] == 0
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
    assert payload["evidence_scope"] == "explicit_single_namespace_diagnostic"
    assert payload["included_namespaces"] == ["notify_llm_deep_cryptopanic_rehearsal"]
    assert payload["candidate_rows_seen"] == 1
    assert payload["real_candidates_seen"] == 0
    assert payload["real_burn_in_candidate_count"] == 0
    assert payload["notification_rehearsal_candidate_count"] == 1
    assert payload["contract_counted_candidate_count"] == 0
    assert payload["enough_data"] is False
    assert "explicit_namespace_not_counted_for_burn_in_contract" in payload["enough_data_reasons"]


def test_scorecard_no_active_burn_in_namespaces_points_to_next_command(tmp_path, monkeypatch):
    (tmp_path / "notify_llm").mkdir()
    no_run = tmp_path / "live_burn_in_no_send"
    no_run.mkdir()
    _write_jsonl(no_run / "event_integrated_radar_candidates.jsonl", [{"candidate_id": "no-run"}])
    monkeypatch.setattr(
        scorecard.common,
        "load_contract",
        lambda: radar_north_star.build_burn_in_contract(generated_at=datetime(2026, 7, 5, tzinfo=timezone.utc)),
    )
    payload = scorecard.build_scorecard(profile="live_burn_in_no_send", base_dir=tmp_path)
    assert payload["included_namespaces"] == []
    assert payload["evidence_scope"] == "no_active_burn_in_namespaces"
    assert payload["enough_data"] is False
    assert "no_active_burn_in_namespaces" in payload["enough_data_reasons"]
    assert payload["next_command"]


def test_scorecard_active_burn_in_without_candidates_has_no_candidate_scope(tmp_path, monkeypatch):
    live = tmp_path / "live_burn_in_20260705"
    live.mkdir()
    (live / daily_burn_in.RUN_JSON).write_text('{"generated_at":"2026-07-05T00:00:00+00:00"}\n', encoding="utf-8")
    monkeypatch.setattr(
        scorecard.common,
        "load_contract",
        lambda: radar_north_star.build_burn_in_contract(generated_at=datetime(2026, 7, 5, tzinfo=timezone.utc)),
    )
    payload = scorecard.build_scorecard(profile="live_burn_in_no_send", base_dir=tmp_path)
    assert payload["included_namespaces"] == ["live_burn_in_20260705"]
    assert payload["evidence_scope"] == "active_burn_in_no_candidate_evidence"
    assert payload["real_burn_in_candidate_count"] == 0
    assert payload["candidate_evidence_explanation"] == "burn-in run completed but no real candidate artifacts were produced"


def test_scorecard_active_burn_in_preflight_only_scope_is_explicit(tmp_path, monkeypatch):
    live = tmp_path / "live_burn_in_20260705"
    live.mkdir()
    (live / daily_burn_in.RUN_JSON).write_text('{"generated_at":"2026-07-05T00:00:00+00:00"}\n', encoding="utf-8")
    (live / "event_alpha_live_provider_readiness.json").write_text('{"generated_at":"2026-07-05T00:00:00+00:00"}\n', encoding="utf-8")
    (live / "event_alpha_source_coverage.json").write_text('{"generated_at":"2026-07-05T00:00:00+00:00"}\n', encoding="utf-8")
    monkeypatch.setattr(
        scorecard.common,
        "load_contract",
        lambda: radar_north_star.build_burn_in_contract(generated_at=datetime(2026, 7, 5, tzinfo=timezone.utc)),
    )
    payload = scorecard.build_scorecard(profile="live_burn_in_no_send", base_dir=tmp_path)
    assert payload["evidence_scope"] == "active_burn_in_preflight_only"
    assert payload["contract_counted_candidate_count"] == 0
    assert payload["readiness_rows"] == 1
    assert payload["source_coverage_rows"] == 1
    assert payload["namespaces_with_only_preflight_rows"] == ["live_burn_in_20260705"]


def test_weekly_measurement_and_source_yield_are_recommendations_only(tmp_path):
    fixed_now = datetime(2026, 7, 12, tzinfo=timezone.utc)
    ns = tmp_path / "burn"
    _write_jsonl(
        ns / "event_integrated_radar_candidates.jsonl",
        [
            {"candidate_id": "1", "opportunity_type": "UNCONFIRMED_RESEARCH", "provider": "cryptopanic", "source_pack": "cryptopanic_context", "generated_at": fixed_now.isoformat()},
            {"candidate_id": "2", "opportunity_type": "DIAGNOSTIC", "provider": "rss", "source_pack": "rss_context", "generated_at": fixed_now.isoformat()},
            {"candidate_id": "3", "opportunity_type": "UNCONFIRMED_RESEARCH", "provider": "coinalyze", "source_pack": "derivatives", "generated_at": fixed_now.isoformat()},
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
        now=fixed_now,
    )
    assert dashboard["evidence_scope"] == "explicit_single_namespace_diagnostic"
    assert dashboard["burn_in_contract_scope"] == "explicit_single_namespace_diagnostic"
    assert dashboard["explicit_scope_warning"]
    assert dashboard["real_burn_in_candidate_count"] == 0
    assert dashboard["non_burn_in_candidate_count"] == 3
    assert dashboard["diagnostic_rows_excluded_from_main_aggregate"] == 1
    assert dashboard["low_sample_warning"] is True
    assert dashboard["auto_apply_thresholds"] is False
    assert "first_real_run_interpretation" not in dashboard
    assert dashboard["current_window_interpretation"]["non_burn_in_candidate_count"] == 3
    yield_report = source_yield.build_source_yield_report(
        profile="live_burn_in_no_send",
        artifact_namespace="burn",
        base_dir=tmp_path,
        now=fixed_now,
    )
    assert yield_report["evidence_scope"] == "explicit_single_namespace_diagnostic"
    assert yield_report["explicit_scope_warning"]
    assert yield_report["real_burn_in_candidate_count"] == 0
    assert yield_report["non_burn_in_candidate_count"] == 3
    assert yield_report["recommendations_only"] is True
    assert yield_report["auto_apply"] is False
    assert yield_report["real_candidate_rows"] == 0
    assert yield_report["source_yield_confidence"] == "insufficient_labels"
    assert "coinalyze" not in yield_report["providers"]


def test_source_yield_readiness_only_has_no_candidate_yield(tmp_path):
    ns = tmp_path / "live_burn_in_20260705"
    ns.mkdir()
    (ns / daily_burn_in.RUN_JSON).write_text('{"generated_at":"2026-07-05T00:00:00+00:00"}\n', encoding="utf-8")
    (ns / "event_alpha_live_provider_readiness.json").write_text('{"generated_at":"2026-07-05T00:00:00+00:00"}\n', encoding="utf-8")
    payload = source_yield.build_source_yield_report(profile="live_burn_in_no_send", base_dir=tmp_path)
    assert payload["evidence_scope"] == "active_burn_in_preflight_only"
    assert payload["real_candidate_rows"] == 0
    assert payload["provider_readiness_rows"] == 1
    assert payload["candidate_count"] == 0
    assert payload["providers"] == {}


def test_source_yield_candidate_mode_missing_config_is_activation_not_yield_failure(tmp_path):
    ns = tmp_path / "live_burn_in_20260705"
    ns.mkdir()
    (ns / daily_burn_in.RUN_JSON).write_text(
        json.dumps(
            {
                "row_type": "event_alpha_daily_burn_in_run",
                "generated_at": "2026-07-05T00:00:00+00:00",
                "candidate_mode": True,
                "steps": [],
                "research_only": True,
                "no_send_rehearsal": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    common.write_json(
        ns / daily_burn_in.CANDIDATE_MODE_MANIFEST_JSON,
        {
            "row_type": "event_alpha_candidate_mode_manifest",
            "generated_at": "2026-07-05T00:00:00+00:00",
            "profile": "live_burn_in_no_send",
            "artifact_namespace": "live_burn_in_20260705",
            "candidate_mode": True,
            "providers": {
                "coinalyze": {
                    "status": "skipped_missing_config",
                    "configured": False,
                    "allow_flag_set": False,
                    "live_call_allowed": False,
                    "request_ledger_path": "live_burn_in_20260705/event_coinalyze_request_ledger.jsonl",
                }
            },
            "request_ledger_rows": {"coinalyze": 0},
            "research_only": True,
            "no_send_rehearsal": True,
        },
    )
    payload = source_yield.build_source_yield_report(profile="live_burn_in_no_send", base_dir=tmp_path)
    assert payload["evidence_scope"] == "active_burn_in_candidate_mode_no_candidates"
    assert payload["real_candidate_rows"] == 0
    assert payload["providers"]["coinalyze"]["activation_status"] == "skipped_missing_config"
    assert payload["providers"]["coinalyze"]["candidate_count"] == 0
    assert payload["providers"]["coinalyze"]["recommended_action"] == "activate_next/missing_config"
    assert payload["providers"]["coinalyze"]["candidate_production_status"] == "missing_config"
    assert payload["providers"]["coinalyze"]["source_yield_confidence"] == "activation_pending"


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
    assert payload["evidence_scope"] == "explicit_single_namespace_diagnostic"
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
    assert payload["burn_in_run_artifacts"] == 1
    assert payload["readiness_artifacts"] == 1
    assert payload["candidate_artifacts"] == 0
    assert payload["support_artifacts"]["readiness_artifacts"] == 1
    with zipfile.ZipFile(tmp_path / "out" / archive.ARCHIVE_NAME) as zf:
        assert zf.namelist() == [
            "live_burn_in_20260705/event_alpha_daily_brief.md",
            "live_burn_in_20260705/event_alpha_daily_burn_in_run.json",
            "live_burn_in_20260705/readiness.md",
        ]


def test_burn_in_archive_allows_redacted_status_phrases(tmp_path):
    ns = tmp_path / "event_fade_cache" / "live_burn_in_20260705"
    ns.mkdir(parents=True)
    (ns / daily_burn_in.RUN_JSON).write_text('{"generated_at":"2026-07-05T00:00:00+00:00"}\n', encoding="utf-8")
    (ns / "readiness.md").write_text(
        "\n".join(
            [
                "missing_api_key",
                "missing_config",
                "token configured: no (redacted)",
                "api key configured: no",
                "API key values are never printed",
                "No API token value is printed",
                "configured=false",
            ]
        ),
        encoding="utf-8",
    )
    payload = archive.build_burn_in_archive(base_dir=tmp_path / "event_fade_cache", out_dir=tmp_path / "out", dry_run=True)
    assert payload["secret_hit_count"] == 0
    assert payload["secret_blocker_count"] == 0
    assert payload["secret_allowed_status_count"] >= 6
    assert all(detail["status"] != "blocker" for detail in payload["secret_hit_details"])


def test_burn_in_archive_blocks_actual_secret_values_and_redacts_details(tmp_path):
    ns = tmp_path / "event_fade_cache" / "live_burn_in_20260705"
    ns.mkdir(parents=True)
    (ns / daily_burn_in.RUN_JSON).write_text('{"generated_at":"2026-07-05T00:00:00+00:00"}\n', encoding="utf-8")
    (ns / "bad.md").write_text(
        "Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456\nX-API-Key: live-secret-value-1234567890\n",
        encoding="utf-8",
    )
    payload = archive.build_burn_in_archive(base_dir=tmp_path / "event_fade_cache", out_dir=tmp_path / "out", dry_run=True)
    assert payload["secret_hit_count"] == 2
    assert payload["secret_blocker_count"] == 2
    blocker_details = [detail for detail in payload["secret_hit_details"] if detail["status"] == "blocker"]
    assert len(blocker_details) == 2
    assert all("<redacted>" in detail["excerpt"] for detail in blocker_details)
    assert "abcdefghijklmnopqrstuvwxyz123456" not in json.dumps(payload["secret_hit_details"])


def test_burn_in_archive_dry_run_writes_manifest_without_zip(tmp_path):
    ns = tmp_path / "event_fade_cache" / "live_burn_in_20260705"
    ns.mkdir(parents=True)
    (ns / daily_burn_in.RUN_JSON).write_text('{"generated_at":"2026-07-05T00:00:00+00:00"}\n', encoding="utf-8")
    (ns / "event_alpha_daily_brief.md").write_text("brief\n", encoding="utf-8")
    _write_jsonl(ns / "event_integrated_radar_candidates.jsonl", [{"candidate_id": "candidate-1"}])
    payload = archive.build_burn_in_archive(base_dir=tmp_path / "event_fade_cache", out_dir=tmp_path / "out", dry_run=True)
    assert payload["dry_run"] is True
    assert payload["archive_created"] is False
    assert payload["files_archived"] == 3
    assert payload["candidate_artifacts"] == 1
    assert payload["candidate_evidence_artifacts"] == 1
    assert not (tmp_path / "out" / archive.ARCHIVE_NAME).exists()
    assert (tmp_path / "out" / archive.MANIFEST_JSON).exists()


def test_burn_in_archive_default_excludes_notification_and_no_key_namespaces(tmp_path):
    base = tmp_path / "event_fade_cache"
    live = base / "live_burn_in_20260705"
    notify = base / "notify_llm"
    no_key = base / "no_key_live"
    no_run = base / "live_burn_in_no_send"
    for ns in (live, notify, no_key, no_run):
        ns.mkdir(parents=True)
        (ns / "event_alpha_daily_brief.md").write_text(f"{ns.name}\n", encoding="utf-8")
    (live / daily_burn_in.RUN_JSON).write_text('{"generated_at":"2026-07-05T00:00:00+00:00"}\n', encoding="utf-8")
    payload = archive.build_burn_in_archive(base_dir=base, out_dir=tmp_path / "out", dry_run=True)
    assert payload["dry_run"] is True
    assert payload["archive_scope"] == "active_burn_in_namespaces"
    assert payload["included_namespaces"] == ["live_burn_in_20260705"]
    assert "notify_llm" in payload["excluded_namespaces"]
    assert "no_key_live" in payload["excluded_namespaces"]
    assert "live_burn_in_no_send" in payload["excluded_namespaces"]
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
    assert payload["archive_scope"] == "explicit_namespace_diagnostic"
    assert payload["included_without_burn_in_run_count"] == 1


def test_burn_in_archive_dry_run_with_no_active_burn_in_archives_no_history(tmp_path):
    base = tmp_path / "event_fade_cache"
    for name in ("live_burn_in_no_send", "notify_llm", "integrated_radar_smoke"):
        ns = base / name
        ns.mkdir(parents=True)
        (ns / "event_alpha_daily_brief.md").write_text(name, encoding="utf-8")
    payload = archive.build_burn_in_archive(base_dir=base, out_dir=tmp_path / "out", dry_run=True)
    assert payload["included_namespaces"] == []
    assert payload["no_active_burn_in_namespaces"] is True
    assert payload["files_archived"] == 0
    assert payload["file_count_by_namespace"] == {}


def test_burn_in_doctor_operations_check_blocks_bad_candidate_semantics():
    blockers: list[str] = []
    warnings: list[str] = []
    ctx = SimpleNamespace(
        burn_in_scorecard={
            "evidence_scope": "real_burn_in_evidence",
            "contract_counted_candidate_count": 1,
            "real_burn_in_candidate_count": 0,
            "readiness_rows": 1,
        },
        source_yield_report={
            "real_candidate_rows": 0,
            "provider_readiness_rows": 1,
            "providers": {"coinalyze": {"candidate_count": 1}},
        },
        daily_review_inbox={
            "items": [
                {
                    "symbol": "READY",
                    "candidate_provenance": "",
                    "source_artifact": "",
                    "preflight_only": True,
                    "diagnostic_only": False,
                }
            ],
        },
    )
    doctor_operations_checks.apply_checks(ctx, blockers, warnings)
    assert any("burn_in_scorecard_contract_count_exceeds_real_candidates" in blocker for blocker in blockers)
    assert any("source_yield_counts_non_real_rows_as_candidate_yield" in blocker for blocker in blockers)
    assert any("source_yield_counts_readiness_or_preflight_as_candidate_yield" in blocker for blocker in blockers)
    assert any("review_inbox_selected_items_missing_provenance=1" in blocker for blocker in blockers)
    assert any("review_inbox_selected_diagnostic_or_preflight_only=1" in blocker for blocker in blockers)


def test_burn_in_doctor_blocks_review_inbox_path_hygiene_regressions():
    blockers: list[str] = []
    warnings: list[str] = []
    ctx = SimpleNamespace(
        burn_in_scorecard={},
        source_yield_report={},
        daily_review_inbox={
            "blockers": ["stale_or_missing_review_path:missing:burn/research_cards/missing.md"],
            "items": [
                {
                    "candidate_provenance": "integrated_candidate",
                    "source_artifact": "event_integrated_radar_candidates.jsonl",
                    "card_path": "/tmp/local/research_cards/core_bad.md",
                },
                {
                    "candidate_provenance": "integrated_candidate",
                    "source_artifact": "event_integrated_radar_candidates.jsonl",
                },
            ],
        },
        daily_review_inbox_markdown="- card_path: `/tmp/local/research_cards/core_bad.md`",
    )
    doctor_operations_checks.apply_checks(ctx, blockers, warnings)
    assert any("daily_review_inbox_blockers=1" in blocker for blocker in blockers)
    assert any("review_inbox_operator_card_paths_absolute=1" in blocker for blocker in blockers)
    assert any("review_inbox_markdown_contains_local_absolute_path" in blocker for blocker in blockers)
    assert any("review_inbox_selected_items_missing_card_path_or_reason=1" in blocker for blocker in blockers)


def test_burn_in_doctor_accepts_relative_review_inbox_card_path_in_temp_base(tmp_path):
    ns = tmp_path / "burn"
    card = ns / "research_cards" / "core_ok.md"
    card.parent.mkdir(parents=True)
    card.write_text("# OK card\n", encoding="utf-8")
    blockers: list[str] = []
    warnings: list[str] = []
    ctx = SimpleNamespace(
        namespace_dir=ns,
        burn_in_scorecard={},
        source_yield_report={},
        daily_review_inbox={
            "blockers": [],
            "items": [
                {
                    "candidate_provenance": "integrated_candidate",
                    "source_artifact": "event_integrated_radar_candidates.jsonl",
                    "card_path": "burn/research_cards/core_ok.md",
                }
            ],
        },
    )
    doctor_operations_checks.apply_checks(ctx, blockers, warnings)
    assert blockers == []
    assert warnings == []


def test_burn_in_doctor_candidate_mode_manifest_and_provenance_checks():
    blockers: list[str] = []
    warnings: list[str] = []
    ctx = SimpleNamespace(
        profile="live_burn_in_no_send",
        artifact_namespace="live_burn_in_20260705",
        namespace_status=None,
        daily_burn_in_run={"candidate_mode": True, "steps": []},
        candidate_mode_manifest={},
        burn_in_scorecard={},
        source_yield_report={},
        daily_review_inbox={},
        burn_in_archive_manifest={},
        integrated_conflicts={},
        integrated_candidates=[
            {
                "candidate_id": "missing",
                "contract_counted_candidate": True,
                "candidate_source_mode": "live_no_send",
                "provider": "",
                "source_pack": "",
                "source_origin": "",
            },
            {
                "candidate_id": "fixture",
                "contract_counted_candidate": True,
                "candidate_source_mode": "mocked_fixture",
                "provider": "fixture",
                "source_pack": "fixture",
                "source_origin": "fixture",
            },
            {
                "candidate_id": "preflight",
                "contract_counted_candidate": True,
                "candidate_source_mode": "preflight_only",
                "candidate_provenance": "integrated_candidate",
                "provider": "coinalyze",
                "source_pack": "derivatives",
                "source_origin": "coinalyze",
            },
        ],
    )
    doctor_operations_checks.apply_checks(ctx, blockers, warnings)
    assert any("daily_burn_in_candidate_mode_manifest_missing" in warning for warning in warnings)
    assert any("daily_burn_in_contract_candidate_missing_provenance=3" in blocker for blocker in blockers)
    assert any("daily_burn_in_live_candidate_missing_request_ledger=1" in blocker for blocker in blockers)
    assert any("daily_burn_in_fixture_candidate_counted_as_real=1" in blocker for blocker in blockers)
    assert any("daily_burn_in_preflight_row_counted_as_candidate=1" in blocker for blocker in blockers)


def test_burn_in_doctor_operations_checks_daily_run_and_archive_scope():
    blockers: list[str] = []
    warnings: list[str] = []
    ctx = SimpleNamespace(
        profile="live_burn_in_no_send",
        artifact_namespace="live_burn_in_20260705",
        namespace_status=None,
        daily_burn_in_run={},
        burn_in_scorecard={},
        source_yield_report={},
        daily_review_inbox={},
        burn_in_archive_manifest={},
        integrated_conflicts={},
    )
    doctor_operations_checks.apply_checks(ctx, blockers, warnings)
    assert any("daily_burn_in_run_missing" in blocker for blocker in blockers)

    blockers.clear()
    ctx.daily_burn_in_run = {
        "row_type": "event_alpha_daily_burn_in_run",
        "steps": [
            {"name": "doctor"},
            {"name": "brief", "status": "passed", "required": False, "command": "python main.py --brief"},
            {"name": "skipped", "status": "skipped", "required": False},
        ],
        "normal_rsi_signal_rows_written": 1,
    }
    ctx.integrated_conflicts = {"integrated_preview_lane_mismatch": 1}
    ctx.burn_in_archive_manifest = {
        "archive_scope": "active_burn_in_namespaces",
        "included_without_burn_in_run_count": 1,
    }
    doctor_operations_checks.apply_checks(ctx, blockers, warnings)
    assert any("daily_burn_in_run_step_missing_status=1" in warning for warning in warnings)
    assert any("daily_burn_in_run_step_missing_required=1" in warning for warning in warnings)
    assert any("daily_burn_in_run_step_missing_timeout=1" in warning for warning in warnings)
    assert any("daily_burn_in_run_step_skipped_missing_reason=1" in warning for warning in warnings)
    assert any("daily_burn_in_run_forbidden_side_effect_claim=1" in blocker for blocker in blockers)
    assert any("daily_burn_in_integrated_preview_mismatch" in blocker for blocker in blockers)
    assert any("daily_burn_in_archive_includes_non_burn_in_by_default" in blocker for blocker in blockers)


def test_daily_burn_in_step_tails_are_scrubbed_before_persisting(tmp_path, monkeypatch):
    repo_path = Path.cwd() / "event_fade_cache" / "burn_tail" / "event_alpha_daily_brief.md"
    step = daily_burn_in.BurnInStep("tail_fixture", (sys.executable, "-c", "print('fixture')"), required=True, timeout_seconds=5)
    monkeypatch.setattr(daily_burn_in, "build_steps", lambda **kwargs: (step,))

    def fake_run_step(step, *, env, cwd):
        return {
            "name": step.name,
            "status": "passed",
            "required": step.required,
            "timeout_seconds": step.timeout_seconds,
            "duration_seconds": 0.01,
            "command": " ".join(step.command),
            "stdout_tail": f"wrote {repo_path}",
            "stderr_tail": "Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456",
        }

    monkeypatch.setattr(daily_burn_in, "_run_step", fake_run_step)
    payload = daily_burn_in.run_daily_burn_in(
        profile="fixture",
        artifact_namespace="burn_tail",
        base_dir=tmp_path,
        python=sys.executable,
        smoke=True,
    )
    row = payload["steps"][0]
    assert row["stdout_tail_scrubbed"] is True
    assert row["stderr_tail_scrubbed"] is True
    assert row["stdout_tail_redaction_count"] >= 1
    assert row["stderr_tail_redaction_count"] >= 1
    assert "/Users/" not in row["stdout_tail"]
    assert "Authorization: Bearer <redacted>" in row["stderr_tail"]


def test_burn_in_doctor_blocks_unsanitized_tails_and_secret_blockers():
    blockers: list[str] = []
    warnings: list[str] = []
    ctx = SimpleNamespace(
        profile="live_burn_in_no_send",
        artifact_namespace="live_burn_in_20260705",
        namespace_status=None,
        daily_burn_in_run={
            "row_type": "event_alpha_daily_burn_in_run",
            "steps": [
                {
                    "name": "bad_tail",
                    "status": "passed",
                    "required": False,
                    "timeout_seconds": 1,
                    "stdout_tail": "/Users/nasrenkaraf/crypto-rsi-scanner/event_fade_cache/live/file.md",
                    "stderr_tail": "X-API-Key: live-secret-value-1234567890",
                }
            ],
        },
        candidate_mode_manifest={},
        burn_in_scorecard={},
        source_yield_report={},
        daily_review_inbox={},
        burn_in_archive_manifest={"archive_scope": "active_burn_in_namespaces", "secret_blocker_count": 1},
        integrated_conflicts={},
        integrated_candidates=[],
    )
    doctor_operations_checks.apply_checks(ctx, blockers, warnings)
    assert any("daily_burn_in_step_tail_unsanitized_absolute_paths=1" in blocker for blocker in blockers)
    assert any("daily_burn_in_step_tail_unsanitized_secret_values=1" in blocker for blocker in blockers)
    assert any("daily_burn_in_archive_secret_blocker_count=1" in blocker for blocker in blockers)
    assert any("daily_burn_in_step_tail_missing_scrub_flags=2" in warning for warning in warnings)


def test_burn_in_doctor_operations_ignores_legacy_source_yield_without_semantic_fields():
    blockers: list[str] = []
    warnings: list[str] = []
    ctx = SimpleNamespace(
        burn_in_scorecard={},
        source_yield_report={
            "schema_version": "event_alpha_source_yield_report_v1",
            "candidate_count": 11,
            "providers": {"legacy": {"candidate_count": 11}},
        },
        daily_review_inbox={},
    )
    doctor_operations_checks.apply_checks(ctx, blockers, warnings)
    assert blockers == []
    assert warnings == []


def test_burn_in_doctor_operations_warns_when_generic_context_outranks_accepted_evidence():
    blockers: list[str] = []
    warnings: list[str] = []
    ctx = SimpleNamespace(
        burn_in_scorecard={},
        source_yield_report={},
        daily_review_inbox={
            "items": [
                {
                    "candidate_provenance": "integrated_candidate",
                    "source_artifact": "event_integrated_radar_candidates.jsonl",
                    "downrank_reason_codes": ["generic_context_source_downranked"],
                    "card_not_available_reason": "source_candidate_has_no_core_card",
                },
                {
                    "candidate_provenance": "integrated_candidate",
                    "source_artifact": "event_integrated_radar_candidates.jsonl",
                    "review_value_reason_codes": ["accepted_evidence_found"],
                    "card_not_available_reason": "source_candidate_has_no_core_card",
                },
            ],
        },
    )
    doctor_operations_checks.apply_checks(ctx, blockers, warnings)
    assert blockers == []
    assert any("review_inbox_generic_context_outranks_accepted_evidence" in warning for warning in warnings)


def test_secret_scanner_ignores_natural_language_sk_phrase_but_catches_keys():
    assert common.secret_hits_in_text("a sk-fragmenting-global-financial-system narrative") == []
    assert common.secret_hits_in_text('"no_api_keys_in_tests": true') == []
    assert common.secret_hits_in_text('{"api_key":"should-not-archive"}') == ["api_key"]
    assert common.secret_hits_in_text("token sk-ABC1234567890defghijk") == ["sk-ABC1234567890defghijk"]
    details = list(common.classify_secret_hits_in_text("token configured: no (redacted)\napi_key=actual-secret-value-1234567890"))
    assert any(detail["status"] == "allowed_status" for detail in details)
    assert any(detail["status"] == "blocker" for detail in details)
