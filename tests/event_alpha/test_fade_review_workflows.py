"""Event-fade sidecar, review-bundle, cache, and scanner workflow regressions."""

from __future__ import annotations

import json
from collections import Counter
from tempfile import TemporaryDirectory

import pytest

from tests.event_alpha import _api_helpers as _event_alpha_api_helpers

globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


@pytest.fixture(autouse=True)
def _isolate_local_discovery_from_live_providers(monkeypatch):
    from crypto_rsi_scanner import config

    _force_disable_event_discovery_live(monkeypatch, config)


def test_event_fade_validation_review_template_roundtrips_sidecar_labels():
    import tempfile
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    template_rows = event_validation.build_review_template_rows(rows, limit=2)
    assert len(template_rows) == 2
    assert template_rows[0]["asset_symbol"] == "TESTVELVET"
    assert template_rows[0]["queue_category"] == "label_triggered_candidate"
    assert template_rows[0]["event_time_confidence"] == 1.0
    assert template_rows[0]["event_time_source"] == "explicit"
    assert template_rows[0]["external_asset"] == "SpaceX"
    assert template_rows[0]["human_event_time"] is None
    assert template_rows[0]["suggested_label"] == "valid_proxy_fade or false_positive"
    assert template_rows[0]["source_origins"] == ["example.test"]
    assert template_rows[0]["source_providers"] == ["manual_json"]
    assert template_rows[0]["primary_source_url"] == "https://example.test/velvet-spacex-duplicate"
    assert template_rows[0]["primary_source_origin"] == "example.test"
    assert (
        template_rows[0]["primary_raw_title"]
        == "TestVelvet offers synthetic exposure to SpaceX pre-IPO trading before launch"
    )
    assert "TestVelvet+offers+synthetic+exposure" in template_rows[0]["source_search_url"]
    assert "Verify source evidence" in template_rows[0]["review_prompt"]
    assert "explicit/high confidence" in template_rows[0]["event_time_review_hint"]
    assert template_rows[0]["missing_fields"] == [
        "human_label",
        "max_adverse_excursion",
        "max_favorable_excursion",
        "post_event_return_72h",
        "event_time_post_event_return_72h",
    ]

    template_rows[0]["review_status"] = "reviewed"
    template_rows[0]["reviewed_by"] = "human"
    template_rows[0]["reviewed_at"] = "2026-06-17T11:00:00+00:00"
    template_rows[0]["human_label"] = "valid_proxy_fade"
    template_rows[0]["human_notes"] = "Reviewed source evidence."
    template_rows[0]["primary_source_url"] = "https://example.test/helper-column-change"
    template_rows[0]["review_prompt"] = "Helper-only reviewer note changed."
    template_rows[0]["source_search_url"] = "https://example.test/helper-search-change"
    template_rows[0]["source_providers"] = ["helper_provider"]
    template_rows[0]["post_event_return_72h"] = -0.21
    result = event_validation.apply_review_template(rows, template_rows)
    assert result.matched_rows == 1
    assert result.evidence_changed_rows == 0
    assert result.copied_fields == 6
    velvet = next(row for row in result.rows if row["asset_symbol"] == "TESTVELVET")
    assert velvet["review_status"] == "reviewed"
    assert velvet["reviewed_by"] == "human"
    assert velvet["reviewed_at"] == "2026-06-17T11:00:00+00:00"
    assert velvet["human_label"] == "valid_proxy_fade"
    assert velvet["human_notes"] == "Reviewed source evidence."
    assert velvet["post_event_return_72h"] == -0.21

    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / "review_template.csv"
        jsonl_path = Path(tmp) / "review_template.jsonl"
        event_validation.write_review_template(rows, csv_path, limit=1)
        event_validation.write_review_template(rows, jsonl_path, limit=1)
        csv_rows = event_validation.load_validation_sample(csv_path)
        jsonl_rows = event_validation.load_validation_sample(jsonl_path)
        assert csv_rows[0]["asset_symbol"] == "TESTVELVET"
        assert csv_rows[0]["external_asset"] == "SpaceX"
        assert csv_rows[0]["primary_source_url"] == "https://example.test/velvet-spacex-duplicate"
        assert "Verify source evidence" in csv_rows[0]["review_prompt"]
        assert "TestVelvet+offers+synthetic+exposure" in csv_rows[0]["source_search_url"]
        assert "source_date_hint" in csv_rows[0]
        assert csv_rows[0]["source_providers"] == ["manual_json"]
        assert csv_rows[0]["missing_fields"][0] == "human_label"
        assert jsonl_rows[0]["asset_symbol"] == "TESTVELVET"


def test_event_fade_validation_balanced_review_template_samples_gates():
    from collections import Counter
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    template_rows = event_validation.build_balanced_review_template_rows(
        rows,
        proxy_limit=2,
        control_limit=3,
    )
    slices = Counter(row["review_slice"] for row in template_rows)
    assert slices["triggered"] == 1
    assert slices["proxy_candidate"] == 2
    assert slices["negative_control"] == 3
    assert any(row["asset_symbol"] == "TESTVELVET" for row in template_rows)
    assert any(row["suggested_label"] == "direct_event" for row in template_rows)
    assert all("primary_source_url" in row for row in template_rows)
    assert all("external_asset" in row for row in template_rows)
    assert all("source_providers" in row for row in template_rows)
    assert all(row.get("source_search_url") for row in template_rows)

    csv_text = event_validation.format_review_template_csv(template_rows)
    assert "review_slice" in csv_text.splitlines()[0]
    assert "negative_control" in csv_text

    packet = event_validation.format_balanced_review_packet(
        rows,
        proxy_limit=2,
        control_limit=3,
    )
    assert "# Event-Fade Balanced Review Packet" in packet
    assert "Rows shown: 6 | proxy_limit=2 | control_limit=3 | triggered_limit=all" in packet
    assert "Slices: negative_control=3, proxy_candidate=2, triggered=1" in packet
    assert "- Review slice: `triggered`" in packet
    assert "- Review slice: `proxy_candidate`" in packet
    assert "- Review slice: `negative_control`" in packet
    assert "external=`SpaceX`" in packet
    assert "Source providers:" in packet
    assert "Source search:" in packet


def test_event_fade_validation_balanced_review_template_diversifies_controls():
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    def control_row(symbol: str, idx: int, *, origin: str = "example.test") -> dict:
        return {
            "event_id": f"control-{symbol.lower()}-{idx}",
            "asset_coin_id": symbol.lower(),
            "asset_symbol": symbol,
            "event_name": f"{symbol} market context story {idx}",
            "event_type": "other",
            "relationship_type": "ambiguous",
            "asset_role": "ambiguous",
            "is_proxy_narrative": False,
            "is_direct_beneficiary": False,
            "signal_type": "NO_TRADE",
            "source_urls": [f"https://{origin}/{symbol.lower()}-{idx}"],
            "raw_titles": [f"{symbol} market context story {idx}"],
        }

    rows = [
        *(control_row("BTC", idx) for idx in range(1, 6)),
        control_row("ETH", 1),
        control_row("SOL", 1),
    ]

    priority_rows = event_validation.build_review_template_rows(rows, limit=3)
    assert [row["asset_symbol"] for row in priority_rows] == ["BTC", "BTC", "BTC"]

    balanced_rows = event_validation.build_balanced_review_template_rows(
        rows,
        proxy_limit=0,
        control_limit=3,
        triggered_limit=0,
    )
    assert [row["review_slice"] for row in balanced_rows] == ["negative_control"] * 3
    assert {row["asset_symbol"] for row in balanced_rows} == {"BTC", "ETH", "SOL"}


def test_event_fade_validation_balanced_review_template_prefers_proxy_instruments():
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    def proxy_row(symbol: str, role: str, idx: int) -> dict:
        return {
            "event_id": f"proxy-{symbol.lower()}-{idx}",
            "asset_coin_id": symbol.lower(),
            "asset_symbol": symbol,
            "event_name": f"{symbol} external proxy story {idx}",
            "event_type": "ipo_proxy",
            "relationship_type": "proxy_attention",
            "asset_role": role,
            "is_proxy_narrative": True,
            "is_direct_beneficiary": False,
            "signal_type": "NO_TRADE",
            "source_urls": [f"https://example.test/{symbol.lower()}-{idx}"],
            "raw_titles": [f"{symbol} external proxy story {idx}"],
        }

    rows = [
        proxy_row("VENUE1", "proxy_venue", 1),
        proxy_row("VENUE2", "proxy_venue", 2),
        proxy_row("INST1", "proxy_instrument", 1),
        proxy_row("VENUE3", "proxy_venue", 3),
        proxy_row("INST2", "proxy_instrument", 2),
    ]

    instruments_only = event_validation.build_balanced_review_template_rows(
        rows,
        proxy_limit=2,
        control_limit=0,
        triggered_limit=0,
    )
    assert [row["review_slice"] for row in instruments_only] == ["proxy_candidate"] * 2
    assert {row["asset_role"] for row in instruments_only} == {"proxy_instrument"}
    assert {row["asset_symbol"] for row in instruments_only} == {"INST1", "INST2"}

    with_fill = event_validation.build_balanced_review_template_rows(
        rows,
        proxy_limit=4,
        control_limit=0,
        triggered_limit=0,
    )
    assert [row["asset_role"] for row in with_fill[:2]] == ["proxy_instrument", "proxy_instrument"]
    assert sum(row["asset_role"] == "proxy_venue" for row in with_fill) == 2


def test_event_fade_validation_review_template_skips_changed_sidecar_evidence():
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    template_rows = event_validation.build_review_template_rows(rows, limit=1)
    template_rows[0]["review_status"] = "reviewed"
    template_rows[0]["human_label"] = "valid_proxy_fade"
    template_rows[0]["human_notes"] = "Reviewed compact source evidence."
    sample_row = next(row for row in rows if row["asset_symbol"] == "TESTVELVET")
    sample_row["source_urls"] = ["https://example.test/changed-source"]

    result = event_validation.apply_review_template(rows, template_rows)
    assert result.matched_rows == 1
    assert result.evidence_changed_rows == 1
    assert result.copied_fields == 0
    assert result.evidence_changes[0].changed_fields == ("source_urls",)
    velvet = next(row for row in result.rows if row["asset_symbol"] == "TESTVELVET")
    assert velvet["review_status"] == ""
    assert velvet["human_label"] == ""

    check = event_validation.check_review_template(rows, template_rows)
    assert not check.ready_to_apply
    assert check.issues[0].category == "evidence_changed"
    assert check.issues[0].changed_fields == ("source_urls",)
    assert "Evidence fields changed" in event_validation.format_review_template_check(check)


def test_event_fade_validation_review_blocks_late_or_weak_trigger_evidence():
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    triggered = next(row for row in rows if row["asset_symbol"] == "TESTVELVET")
    triggered["human_label"] = "false_positive"
    triggered["review_status"] = "reviewed"
    _stamp_review_provenance(triggered)
    triggered["first_seen_time"] = "2026-06-14T00:00:00+00:00"
    triggered["fetched_at_min"] = "2026-06-14T00:00:00+00:00"
    triggered["published_at_min"] = "2026-06-14T00:00:00+00:00"
    triggered["fetched_at_max"] = "2026-06-14T00:00:00+00:00"
    triggered["published_at_max"] = "2026-06-14T00:00:00+00:00"
    triggered["trigger_observed_at"] = "2026-06-13T12:00:00+00:00"
    triggered["max_favorable_excursion"] = 0.03
    triggered["max_adverse_excursion"] = 0.08
    triggered["post_event_return_72h"] = 0.04

    review = event_validation.review_validation_sample(
        rows,
        min_proxy_candidates=1,
        min_negative_controls=0,
        min_triggered_reviewed=1,
        min_trigger_precision=0.60,
        min_mfe_mae_ratio=1.5,
        min_proxy_event_types=1,
        min_trigger_btc_risk_buckets=1,
    )
    assert review.promotion_ready is False
    assert review.trigger_precision == 0.0
    assert review.point_in_time_violation_rows == 1
    assert review.post_decision_source_rows == 1
    assert any("trigger precision 0.0% below 60.0%" == blocker for blocker in review.promotion_blockers)
    assert any("evidence first seen after the decision time" in blocker for blocker in review.promotion_blockers)
    assert any("source evidence after the decision time" in blocker for blocker in review.promotion_blockers)
    assert review.negative_trigger_latency_rows == 1
    assert any("trigger before event time" in blocker for blocker in review.promotion_blockers)
    assert any("MFE/MAE 0.38 below 1.50" == blocker for blocker in review.promotion_blockers)
    assert "reviewed SHORT_TRIGGERED rows do not show favorable 72h short returns" in review.promotion_blockers


def test_event_fade_validation_review_flags_mixed_late_source_evidence():
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    triggered = next(row for row in rows if row["asset_symbol"] == "TESTVELVET")
    triggered["human_label"] = "valid_proxy_fade"
    triggered["review_status"] = "reviewed"
    _stamp_review_provenance(triggered)
    triggered["max_favorable_excursion"] = 0.42
    triggered["max_adverse_excursion"] = 0.08
    triggered["post_event_return_72h"] = -0.22
    triggered["event_time_post_event_return_72h"] = -0.12
    triggered["fetched_at_min"] = "2026-06-15T12:00:00+00:00"
    triggered["fetched_at_max"] = "2026-06-17T12:00:00+00:00"
    triggered["raw_fetched_at"] = [
        "2026-06-15T12:00:00+00:00",
        "2026-06-17T12:00:00+00:00",
    ]

    review = event_validation.review_validation_sample(
        rows,
        min_proxy_candidates=1,
        min_negative_controls=0,
        min_triggered_reviewed=1,
        min_trigger_precision=0.90,
        min_mfe_mae_ratio=2.0,
        min_proxy_event_types=1,
        min_trigger_btc_risk_buckets=1,
    )
    assert review.point_in_time_violation_rows == 0
    assert review.post_decision_source_rows == 1
    assert "1 reviewed row(s) include source evidence after the decision time" in review.promotion_blockers
    assert (
        "Review or remove 1 row(s) with post-decision source evidence."
        in event_validation.validation_review_next_steps(review)
    )

    queue = event_validation.build_labeling_queue(rows)
    item = next(item for item in queue.items if item.asset_symbol == "TESTVELVET")
    assert item.category == "review_post_decision_source"


def test_event_fade_validation_review_flags_late_control_evidence():
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    direct = next(
        row
        for row in rows
        if row["asset_symbol"] == "TESTBTC" and row["relationship_type"] == "direct_token_event"
    )
    direct["human_label"] = "direct_event"
    direct["review_status"] = "reviewed"
    _stamp_review_provenance(direct)
    direct["event_time"] = "2026-06-15T13:30:00+00:00"
    direct["first_seen_time"] = "2026-06-15T14:00:00+00:00"
    direct["published_at_min"] = "2026-06-15T14:00:00+00:00"
    direct["published_at_max"] = "2026-06-15T14:00:00+00:00"
    direct["fetched_at_min"] = "2026-06-15T14:00:00+00:00"
    direct["fetched_at_max"] = "2026-06-15T14:00:00+00:00"
    direct["raw_published_at"] = ["2026-06-15T14:00:00+00:00"]
    direct["raw_fetched_at"] = ["2026-06-15T14:00:00+00:00"]

    review = event_validation.review_validation_sample(
        rows,
        min_proxy_candidates=0,
        min_negative_controls=1,
        min_triggered_reviewed=0,
    )
    assert review.reviewed_negative_controls == 1
    assert review.point_in_time_violation_rows == 1
    assert review.post_decision_source_rows == 1
    assert any("evidence first seen after the decision time" in blocker for blocker in review.promotion_blockers)
    assert any("source evidence after the decision time" in blocker for blocker in review.promotion_blockers)

    queue = event_validation.build_labeling_queue(rows)
    item = next(item for item in queue.items if item.asset_symbol == "TESTBTC")
    assert item.category == "fix_point_in_time_evidence"


def test_event_fade_validation_review_blocks_missing_source_timing():
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    direct = next(
        row
        for row in rows
        if row["asset_symbol"] == "TESTBTC" and row["relationship_type"] == "direct_token_event"
    )
    direct["human_label"] = "direct_event"
    direct["review_status"] = "reviewed"
    _stamp_review_provenance(direct)
    direct["first_seen_time"] = ""
    direct["published_at_min"] = ""
    direct["published_at_max"] = ""
    direct["fetched_at_min"] = ""
    direct["fetched_at_max"] = ""
    direct["raw_published_at"] = []
    direct["raw_fetched_at"] = []

    review = event_validation.review_validation_sample(
        rows,
        min_proxy_candidates=0,
        min_negative_controls=1,
        min_triggered_reviewed=0,
    )
    assert review.reviewed_negative_controls == 1
    assert review.missing_source_timing_rows == 1
    assert "1 reviewed row(s) are missing source timing evidence" in review.promotion_blockers
    assert (
        "Add source timing evidence or remove 1 reviewed row(s)."
        in event_validation.validation_review_next_steps(review)
    )

    queue = event_validation.build_labeling_queue(rows)
    item = next(item for item in queue.items if item.asset_symbol == "TESTBTC")
    assert item.category == "add_source_timing"
    assert "first_seen_time" in item.missing_fields


def test_event_alert_scanner_report_uses_local_fixtures_without_sending():
    import contextlib
    import io
    from crypto_rsi_scanner import config, scanner

    events_path, aliases_path = _event_discovery_fixture_paths()
    original = {
        "EVENT_DISCOVERY_EVENTS_PATH": config.EVENT_DISCOVERY_EVENTS_PATH,
        "EVENT_DISCOVERY_ALIASES_PATH": config.EVENT_DISCOVERY_ALIASES_PATH,
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH": config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH,
        "EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH": config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH,
        "EVENT_DISCOVERY_COINMARKETCAL_PATH": config.EVENT_DISCOVERY_COINMARKETCAL_PATH,
        "EVENT_DISCOVERY_TOKENOMIST_PATH": config.EVENT_DISCOVERY_TOKENOMIST_PATH,
        "EVENT_DISCOVERY_CRYPTOPANIC_PATH": config.EVENT_DISCOVERY_CRYPTOPANIC_PATH,
        "EVENT_DISCOVERY_GDELT_PATH": config.EVENT_DISCOVERY_GDELT_PATH,
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH": config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH,
        "EVENT_DISCOVERY_EXTERNAL_IPO_PATH": config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH,
        "EVENT_DISCOVERY_SPORTS_FIXTURES_PATH": config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH,
        "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH": config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH,
        "EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH": config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH,
        "EVENT_DISCOVERY_UNIVERSE_PATH": config.EVENT_DISCOVERY_UNIVERSE_PATH,
        "EVENT_DISCOVERY_LOOKBACK_HOURS": config.EVENT_DISCOVERY_LOOKBACK_HOURS,
        "EVENT_DISCOVERY_HORIZON_DAYS": config.EVENT_DISCOVERY_HORIZON_DAYS,
        "EVENT_ALERTS_ENABLED": config.EVENT_ALERTS_ENABLED,
    }
    config.EVENT_DISCOVERY_EVENTS_PATH = events_path
    config.EVENT_DISCOVERY_ALIASES_PATH = aliases_path
    config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH = None
    config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH = None
    config.EVENT_DISCOVERY_COINMARKETCAL_PATH = None
    config.EVENT_DISCOVERY_TOKENOMIST_PATH = None
    config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = None
    config.EVENT_DISCOVERY_GDELT_PATH = None
    config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = None
    config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH = None
    config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH = None
    config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = None
    config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH = None
    config.EVENT_DISCOVERY_UNIVERSE_PATH = None
    config.EVENT_DISCOVERY_LOOKBACK_HOURS = 120
    config.EVENT_DISCOVERY_HORIZON_DAYS = 2
    config.EVENT_ALERTS_ENABLED = False
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_alert_report(send=False, event_now="2026-06-15T16:00:00Z")
        text = out.getvalue()
        assert "EVENT RESEARCH ALERT REPORT" in text
        assert "research-only; not trade signals" in text
        assert "TESTVELVET/testvelvet" in text
        assert "TRIGGERED_FADE" in text
        assert "what user should verify:" in text
    finally:
        for name, value in original.items():
            setattr(config, name, value)


def test_event_alert_scanner_report_with_llm_advisory_uses_runtime_config():
    import contextlib
    import io
    from crypto_rsi_scanner import config, scanner

    path = _llm_golden_fixture_path()
    original = {
        "EVENT_DISCOVERY_EVENTS_PATH": config.EVENT_DISCOVERY_EVENTS_PATH,
        "EVENT_DISCOVERY_ALIASES_PATH": config.EVENT_DISCOVERY_ALIASES_PATH,
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH": config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH,
        "EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH": config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH,
        "EVENT_DISCOVERY_COINMARKETCAL_PATH": config.EVENT_DISCOVERY_COINMARKETCAL_PATH,
        "EVENT_DISCOVERY_TOKENOMIST_PATH": config.EVENT_DISCOVERY_TOKENOMIST_PATH,
        "EVENT_DISCOVERY_CRYPTOPANIC_PATH": config.EVENT_DISCOVERY_CRYPTOPANIC_PATH,
        "EVENT_DISCOVERY_GDELT_PATH": config.EVENT_DISCOVERY_GDELT_PATH,
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH": config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH,
        "EVENT_DISCOVERY_EXTERNAL_IPO_PATH": config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH,
        "EVENT_DISCOVERY_SPORTS_FIXTURES_PATH": config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH,
        "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH": config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH,
        "EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH": config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH,
        "EVENT_DISCOVERY_UNIVERSE_PATH": config.EVENT_DISCOVERY_UNIVERSE_PATH,
        "EVENT_DISCOVERY_LOOKBACK_HOURS": config.EVENT_DISCOVERY_LOOKBACK_HOURS,
        "EVENT_DISCOVERY_HORIZON_DAYS": config.EVENT_DISCOVERY_HORIZON_DAYS,
        "EVENT_ALERTS_ENABLED": config.EVENT_ALERTS_ENABLED,
        "EVENT_LLM_ENABLED": config.EVENT_LLM_ENABLED,
        "EVENT_LLM_MODE": config.EVENT_LLM_MODE,
        "EVENT_LLM_PROVIDER": config.EVENT_LLM_PROVIDER,
        "EVENT_LLM_MODEL": config.EVENT_LLM_MODEL,
        "EVENT_LLM_OPENAI_TIMEOUT": config.EVENT_LLM_OPENAI_TIMEOUT,
        "EVENT_LLM_MAX_CANDIDATES_PER_RUN": config.EVENT_LLM_MAX_CANDIDATES_PER_RUN,
        "EVENT_LLM_MIN_PREFILTER_SCORE": config.EVENT_LLM_MIN_PREFILTER_SCORE,
        "EVENT_LLM_REQUIRE_EVIDENCE_QUOTES": config.EVENT_LLM_REQUIRE_EVIDENCE_QUOTES,
        "EVENT_LLM_MAX_CALLS_PER_RUN": config.EVENT_LLM_MAX_CALLS_PER_RUN,
        "EVENT_LLM_MAX_CALLS_PER_DAY": config.EVENT_LLM_MAX_CALLS_PER_DAY,
        "EVENT_LLM_MAX_ESTIMATED_COST_USD_PER_DAY": config.EVENT_LLM_MAX_ESTIMATED_COST_USD_PER_DAY,
        "EVENT_LLM_ESTIMATED_COST_PER_CALL_USD": config.EVENT_LLM_ESTIMATED_COST_PER_CALL_USD,
        "EVENT_LLM_MAX_PARALLEL_CALLS": config.EVENT_LLM_MAX_PARALLEL_CALLS,
        "EVENT_LLM_CACHE_TTL_HOURS": config.EVENT_LLM_CACHE_TTL_HOURS,
        "EVENT_LLM_CACHE_PATH": config.EVENT_LLM_CACHE_PATH,
        "EVENT_LLM_BUDGET_LEDGER_PATH": config.EVENT_LLM_BUDGET_LEDGER_PATH,
        "EVENT_LLM_PROMPT_VERSION": config.EVENT_LLM_PROMPT_VERSION,
    }
    config.EVENT_DISCOVERY_EVENTS_PATH = path
    config.EVENT_DISCOVERY_ALIASES_PATH = path
    config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH = None
    config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH = None
    config.EVENT_DISCOVERY_COINMARKETCAL_PATH = None
    config.EVENT_DISCOVERY_TOKENOMIST_PATH = None
    config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = None
    config.EVENT_DISCOVERY_GDELT_PATH = None
    config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = None
    config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH = None
    config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH = None
    config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = None
    config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH = None
    config.EVENT_DISCOVERY_UNIVERSE_PATH = None
    config.EVENT_DISCOVERY_LOOKBACK_HOURS = 120
    config.EVENT_DISCOVERY_HORIZON_DAYS = 14
    config.EVENT_ALERTS_ENABLED = False
    config.EVENT_LLM_ENABLED = False
    config.EVENT_LLM_MODE = "advisory"
    config.EVENT_LLM_PROVIDER = "fixture"
    config.EVENT_LLM_MODEL = None
    config.EVENT_LLM_OPENAI_TIMEOUT = 30.0
    config.EVENT_LLM_MAX_CANDIDATES_PER_RUN = 50
    config.EVENT_LLM_MIN_PREFILTER_SCORE = 0
    config.EVENT_LLM_REQUIRE_EVIDENCE_QUOTES = True
    config.EVENT_LLM_MAX_CALLS_PER_RUN = 50
    config.EVENT_LLM_MAX_CALLS_PER_DAY = 50
    config.EVENT_LLM_MAX_ESTIMATED_COST_USD_PER_DAY = 0.0
    config.EVENT_LLM_ESTIMATED_COST_PER_CALL_USD = 0.0
    config.EVENT_LLM_MAX_PARALLEL_CALLS = 1
    config.EVENT_LLM_CACHE_TTL_HOURS = 0.0
    config.EVENT_LLM_CACHE_PATH = None
    config.EVENT_LLM_BUDGET_LEDGER_PATH = None
    config.EVENT_LLM_PROMPT_VERSION = "llm_proxy_context_v1"
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_alert_report(send=False, with_llm=True, event_now="2026-06-15T16:00:00Z")
        text = out.getvalue()
        assert "EVENT RESEARCH ALERT REPORT" in text
        assert "llm tier adjustment: RADAR_DIGEST -> STORE_ONLY" in text
        assert "llm: role=source_noise" in text
        assert "llm adjustment reason:" in text
    finally:
        for name, value in original.items():
            setattr(config, name, value)


def test_event_fade_export_cache_sample_scanner_writes_latest_cached_rows():
    import contextlib
    import io
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import config, scanner

    values = _full_event_discovery_config_values()
    attrs = tuple(values) + ("EVENT_DISCOVERY_CACHE_DIR",)
    original = {name: getattr(config, name) for name in attrs}
    for name, value in values.items():
        setattr(config, name, value)
    with tempfile.TemporaryDirectory() as tmp:
        cache_dir = Path(tmp) / "cache"
        out_path = Path(tmp) / "cached_sample.jsonl"
        config.EVENT_DISCOVERY_CACHE_DIR = cache_dir
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                scanner.event_discovery_refresh(event_now="2026-06-15T16:00:00Z")
                scanner.event_discovery_refresh(event_now="2026-06-15T16:00:00Z")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_fade_export_cache_sample(str(out_path))
            text = out.getvalue()
            assert "Event-fade cached validation sample" in text
            assert "read 34 snapshot(s)" in text
            assert "exported 17 latest row(s)" in text

            rows = [
                json.loads(line)
                for line in out_path.read_text(encoding="utf-8").splitlines()
            ]
            assert len(rows) == 17
            velvet = next(row for row in rows if row["asset_symbol"] == "TESTVELVET")
            assert velvet["schema_version"] == "event_fade_validation_sample_v1"
            assert velvet["row_type"] == "candidate"
            assert velvet["signal_type"] == "SHORT_TRIGGERED"
            assert "payload_row_type" not in velvet
        finally:
            for name, value in original.items():
                setattr(config, name, value)


def test_event_fade_auto_scanner_report_uses_local_fixtures():
    import contextlib
    import io
    from crypto_rsi_scanner import config, scanner

    events_path, aliases_path = _event_discovery_fixture_paths()
    binance_path, bybit_path = _exchange_announcement_fixture_paths()
    coinmarketcal_path, tokenomist_path = _structured_calendar_fixture_paths()
    cryptopanic_path, gdelt_path, blog_path = _news_fixture_paths()
    ipo_path, sports_path, prediction_path = _external_catalyst_fixture_paths()
    tokenomist_supply_path, etherscan_supply_path, arkham_supply_path, dune_supply_path = _supply_fixture_paths()
    attrs = (
        "EVENT_DISCOVERY_EVENTS_PATH",
        "EVENT_DISCOVERY_ALIASES_PATH",
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH",
        "EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH",
        "EVENT_DISCOVERY_COINMARKETCAL_PATH",
        "EVENT_DISCOVERY_TOKENOMIST_PATH",
        "EVENT_DISCOVERY_CRYPTOPANIC_PATH",
        "EVENT_DISCOVERY_GDELT_PATH",
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH",
        "EVENT_DISCOVERY_EXTERNAL_IPO_PATH",
        "EVENT_DISCOVERY_SPORTS_FIXTURES_PATH",
        "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH",
        "EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH",
        "EVENT_DISCOVERY_TOKENOMIST_SUPPLY_PATH",
        "EVENT_DISCOVERY_ETHERSCAN_SUPPLY_PATH",
        "EVENT_DISCOVERY_ARKHAM_SUPPLY_PATH",
        "EVENT_DISCOVERY_DUNE_SUPPLY_PATH",
        "EVENT_DISCOVERY_UNIVERSE_PATH",
        "EVENT_DISCOVERY_LOOKBACK_HOURS",
        "EVENT_DISCOVERY_HORIZON_DAYS",
    )
    original = {name: getattr(config, name) for name in attrs}
    config.EVENT_DISCOVERY_EVENTS_PATH = events_path
    config.EVENT_DISCOVERY_ALIASES_PATH = aliases_path
    config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH = binance_path
    config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH = bybit_path
    config.EVENT_DISCOVERY_COINMARKETCAL_PATH = coinmarketcal_path
    config.EVENT_DISCOVERY_TOKENOMIST_PATH = tokenomist_path
    config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = cryptopanic_path
    config.EVENT_DISCOVERY_GDELT_PATH = gdelt_path
    config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = blog_path
    config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH = ipo_path
    config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH = sports_path
    config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = prediction_path
    config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH = _derivatives_fixture_path()
    config.EVENT_DISCOVERY_TOKENOMIST_SUPPLY_PATH = tokenomist_supply_path
    config.EVENT_DISCOVERY_ETHERSCAN_SUPPLY_PATH = etherscan_supply_path
    config.EVENT_DISCOVERY_ARKHAM_SUPPLY_PATH = arkham_supply_path
    config.EVENT_DISCOVERY_DUNE_SUPPLY_PATH = dune_supply_path
    config.EVENT_DISCOVERY_UNIVERSE_PATH = _coingecko_universe_fixture_path()
    config.EVENT_DISCOVERY_LOOKBACK_HOURS = 120
    config.EVENT_DISCOVERY_HORIZON_DAYS = 2
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_fade_auto_report(event_now="2026-06-15T16:00:00Z")
        text = out.getvalue()
        assert "EVENT FADE AUTO REPORT" in text
        assert "TRIGGERED\n  TESTVELVET" in text
        assert "TESTAI" in text
        assert "REJECTED / NO TRADE" in text
        assert "  TESTLIST     coin=testlist" in text
        assert "AMBIGUOUS" in text
        assert "  TESTPUMP     coin=testpump" in text
    finally:
        for name, value in original.items():
            setattr(config, name, value)


def test_event_fade_export_sample_scanner_writes_jsonl_fixture():
    import contextlib
    import io
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import config, scanner

    values = _full_event_discovery_config_values()
    original = {name: getattr(config, name) for name in values}
    for name, value in values.items():
        setattr(config, name, value)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "sample.jsonl"
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_fade_export_sample(str(out_path), event_now="2026-06-15T16:00:00Z")
            text = out.getvalue()
            assert "wrote" in text
            assert out_path.exists()
            rows = [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines()]
            assert len(rows) == 17
            assert any(row["asset_symbol"] == "TESTVELVET" for row in rows)
            assert all(row["human_label"] == "" for row in rows)
    finally:
        for name, value in original.items():
            setattr(config, name, value)


def test_event_fade_review_sample_scanner_reads_jsonl_fixture():
    import contextlib
    import io
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import scanner
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "sample.jsonl"
        event_discovery.write_validation_sample(rows, out_path)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_fade_review_sample(str(out_path))
        text = out.getvalue()
        assert "EVENT FADE VALIDATION SAMPLE REVIEW" in text
        assert "Rows: 17" in text
        assert "BLOCKED" in text
        assert "reviewed proxy candidates 0/25" in text


def test_event_fade_labeling_queue_scanner_reads_jsonl_fixture():
    import contextlib
    import io
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import scanner
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "sample.jsonl"
        event_discovery.write_validation_sample(rows, out_path)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_fade_labeling_queue(str(out_path), limit=3)
        text = out.getvalue()
        assert "EVENT FADE VALIDATION LABELING QUEUE" in text
        assert "showing: 3" in text
        assert "label_triggered_candidate" in text
        assert "TESTVELVET" in text


def test_event_fade_review_packet_scanner_writes_markdown_fixture():
    import contextlib
    import io
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import scanner
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    with tempfile.TemporaryDirectory() as tmp:
        sample_path = Path(tmp) / "sample.jsonl"
        packet_path = Path(tmp) / "packet.md"
        event_discovery.write_validation_sample(rows, sample_path)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_fade_review_packet(str(sample_path), str(packet_path), limit=1)
        text = out.getvalue()
        assert "Event-fade review packet" in text
        assert "wrote 1/17 row(s) needing review" in text

        packet = packet_path.read_text(encoding="utf-8")
        assert "# Event-Fade Validation Review Packet" in packet
        assert "## 1. TESTVELVET - SpaceX IPO trading start" in packet
        assert "Review fields to fill" in packet


def test_event_fade_review_template_scanner_exports_and_applies_sidecar():
    import contextlib
    import io
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import scanner
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    with tempfile.TemporaryDirectory() as tmp:
        sample_path = Path(tmp) / "sample.jsonl"
        template_path = Path(tmp) / "review_template.csv"
        reviewed_path = Path(tmp) / "reviewed.jsonl"
        event_discovery.write_validation_sample(rows, sample_path)

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_fade_export_review_template(
                str(sample_path),
                str(template_path),
                limit=1,
            )
        text = out.getvalue()
        assert "Event-fade review template" in text
        assert "wrote 1/17 row(s) needing review" in text

        template_rows = event_validation.load_validation_sample(template_path)
        template_rows[0]["review_status"] = "reviewed"
        template_rows[0]["reviewed_by"] = "Codex"
        template_rows[0]["reviewed_at"] = "2026-06-17T11:30:00+00:00"
        template_rows[0]["human_label"] = "valid_proxy_fade"
        template_rows[0]["human_notes"] = "Reviewed compact sidecar."
        template_path.write_text(
            event_validation.format_review_template_csv(template_rows),
            encoding="utf-8",
        )

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_fade_apply_review_template(
                str(sample_path),
                str(template_path),
                str(reviewed_path),
            )
        text = out.getvalue()
        assert "Event-fade review template apply" in text
        assert "1 matched row(s)" in text
        assert "0 evidence-changed row(s)" in text
        assert "EVENT FADE VALIDATION SAMPLE REVIEW" in text
        assert "Rows: 17" in text
        assert "reviewed: 1" in text
        assert "NEXT SAMPLE WORK" in text

        written = [
            json.loads(line)
            for line in reviewed_path.read_text(encoding="utf-8").splitlines()
        ]
        velvet = next(row for row in written if row["asset_symbol"] == "TESTVELVET")
        assert velvet["reviewed_by"] == "Codex"
        assert velvet["reviewed_at"] == "2026-06-17T11:30:00+00:00"
        assert velvet["human_label"] == "valid_proxy_fade"
        assert velvet["human_notes"] == "Reviewed compact sidecar."


def test_event_fade_check_review_template_scanner_dry_checks_sidecar():
    import contextlib
    import io
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import scanner
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    rows = [{
        "event_id": "event-control",
        "asset_symbol": "CTRL",
        "asset_coin_id": "control-token",
        "event_name": "Control narrative mention",
        "relationship_type": "ambiguous",
        "signal_type": "NO_TRADE",
        "is_proxy_narrative": False,
        "is_direct_beneficiary": False,
        "first_seen_time": "2026-06-17T10:00:00+00:00",
        "source_urls": [],
        "raw_published_at": ["2026-06-17T09:00:00+00:00"],
        "raw_fetched_at": ["2026-06-17T10:00:00+00:00"],
    }]

    with tempfile.TemporaryDirectory() as tmp:
        sample_path = Path(tmp) / "sample.jsonl"
        template_path = Path(tmp) / "review_template.csv"
        event_discovery.write_validation_sample(rows, sample_path)
        template_rows = event_validation.build_review_template_rows(rows, limit=1)
        template_rows[0]["review_status"] = "reviewed"
        template_rows[0]["reviewed_by"] = "Codex"
        template_rows[0]["reviewed_at"] = "2026-06-17T11:30:00+00:00"
        template_rows[0]["human_label"] = "ambiguous"
        template_path.write_text(
            event_validation.format_review_template_csv(template_rows),
            encoding="utf-8",
        )

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_fade_check_review_template(str(sample_path), str(template_path))
        text = out.getvalue()
        assert "EVENT FADE REVIEW TEMPLATE CHECK" in text
        assert "Status: ready to apply." in text
        assert "edited rows: 1" in text


def test_event_fade_review_bundle_scanner_writes_workspace():
    import contextlib
    import csv
    import io
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import scanner
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    with tempfile.TemporaryDirectory() as tmp:
        sample_path = Path(tmp) / "sample.jsonl"
        bundle_dir = Path(tmp) / "review_bundle"
        event_discovery.write_validation_sample(rows, sample_path)

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_fade_review_bundle(
                str(sample_path),
                str(bundle_dir),
                limit=1,
                prices_path=str(_outcome_prices_fixture_path()),
                event_now="2026-06-15T16:00:00Z",
            )
        text = out.getvalue()
        assert "Event-fade review bundle" in text
        assert "needing_review=17" in text
        assert "showing=1" in text

        expected = {
            "README.md",
            "manifest.json",
            "validation_sample.jsonl",
            "validation_sample_with_outcomes.jsonl",
            "labeling_queue.txt",
            "review_packet.md",
            "review_packet_balanced.md",
            "review_template.csv",
            "review_template_balanced.csv",
            "review_guide.md",
            "review_report.txt",
        }
        assert expected == {path.name for path in bundle_dir.iterdir()}

        readme = (bundle_dir / "README.md").read_text(encoding="utf-8")
        assert "Research-only" in readme
        assert "validation_sample_with_outcomes.jsonl" in readme
        assert "review_guide.md" in readme
        assert "review_packet_balanced.md" in readme
        assert "review_template_balanced.csv" in readme
        assert "source_providers" in readme
        assert "manifest.json" in readme

        guide = (bundle_dir / "review_guide.md").read_text(encoding="utf-8")
        assert "Event-Fade Review Guide" in guide
        assert "`valid_proxy_fade`" in guide
        assert "`false_positive`" in guide
        assert "`direct_event`" in guide
        assert "`ambiguous`" in guide
        assert "reviewed_by" in guide
        assert "reviewed_at" in guide
        assert "human_event_time" in guide
        assert "external_asset" in guide
        assert "primary_source_url" in guide
        assert "source_search_url" in guide
        assert "source_date_hint" in guide
        assert "source_providers" in guide
        assert "review_prompt" in guide
        assert "helper columns are not copied back" in guide
        assert "review_template_balanced.csv" in guide

        manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["source"]["sample_path"] == str(sample_path)
        assert manifest["source"]["review_rows"] == 17
        assert manifest["queue"]["shown_rows"] == 1
        assert manifest["files"]["review_packet_balanced"] == "review_packet_balanced.md"
        assert manifest["files"]["review_template"] == "review_template.csv"
        assert manifest["files"]["review_template_balanced"] == "review_template_balanced.csv"
        assert manifest["files"]["review_guide"] == "review_guide.md"
        assert manifest["balanced_review_template"]["rows"] >= 1
        assert manifest["balanced_review_template"]["proxy_limit"] == 25
        assert manifest["balanced_review_template"]["control_limit"] == 50
        assert manifest["outcome_fill"]["filled_rows"] == 1
        assert manifest["review"]["promotion_ready"] is False
        assert manifest["review"]["reviewed_proxy_event_types"] == 0
        assert manifest["review"]["min_proxy_event_types"] == 2
        assert manifest["review"]["reviewed_proxy_source_providers"] == 0
        assert manifest["review"]["min_proxy_source_providers"] == 2
        assert manifest["review"]["reviewed_proxy_source_origins"] == 0
        assert manifest["review"]["low_confidence_trigger_event_time_rows"] == 0
        assert manifest["sample_summary"]["rows"] == 17
        assert manifest["sample_summary"]["proxy_candidates"] == 6
        assert manifest["sample_summary"]["direct_beneficiaries"] == 9
        assert manifest["sample_summary"]["short_triggered_rows"] == 1
        assert manifest["sample_summary"]["asset_roles"]["proxy_instrument"] == 6
        assert manifest["sample_summary"]["source_providers"]["manual_json"] == 5
        assert manifest["sample_summary"]["source_provider_summary"]["manual_json"]["rows"] == 5
        assert manifest["sample_summary"]["source_provider_summary"]["manual_json"]["short_triggered_rows"] == 1
        assert manifest["sample_summary"]["source_provider_summary"]["cryptopanic"]["direct_beneficiaries"] == 2
        assert manifest["sample_summary"]["source_origins"]["example.test"] == 13
        assert manifest["sample_summary"]["source_origin_summary"]["example.test"]["short_triggered_rows"] == 1
        template_header = (bundle_dir / "review_template.csv").read_text(encoding="utf-8").splitlines()[0]
        assert "external_asset" in template_header
        assert "primary_source_url" in template_header
        assert "primary_raw_title" in template_header
        assert "source_search_url" in template_header
        assert "source_date_hint" in template_header
        assert "source_providers" in template_header
        assert "event_time_review_hint" in template_header
        balanced_header = (bundle_dir / "review_template_balanced.csv").read_text(encoding="utf-8").splitlines()[0]
        assert "review_slice" in balanced_header
        assert "external_asset" in balanced_header
        assert "primary_source_url" in balanced_header
        assert "source_search_url" in balanced_header
        assert "source_date_hint" in balanced_header
        assert "source_providers" in balanced_header
        assert "Sample summary:" in readme
        assert "Proxy candidates: 6" in readme
        assert "Asset roles: direct_beneficiary=9, proxy_instrument=6, ambiguous=2" in readme
        assert "Source provider detail:" in readme
        assert "Source origins:" in readme
        assert "Source origin detail:" in readme
        assert "Review gates:" in readme
        assert "Proxy diversity: event_types=0/2, source_providers=0/2, source_origins=0" in readme
        assert "manual_json: rows=5, proxy=1, direct=3, triggered=1, missing_time=1" in readme

        packet = (bundle_dir / "review_packet.md").read_text(encoding="utf-8")
        assert "## 1. TESTVELVET - SpaceX IPO trading start" in packet
        assert "trigger 72h=`-20.8%`" in packet
        balanced_packet = (bundle_dir / "review_packet_balanced.md").read_text(encoding="utf-8")
        assert "# Event-Fade Balanced Review Packet" in balanced_packet
        assert "- Review slice: `triggered`" in balanced_packet
        assert "- Review slice: `negative_control`" in balanced_packet
        assert "Source search:" in balanced_packet
        assert "Source providers:" in balanced_packet

        report = (bundle_dir / "review_report.txt").read_text(encoding="utf-8")
        assert "EVENT FADE VALIDATION SAMPLE REVIEW" in report
        assert "reviewed proxy candidates 0/25" in report

        template_text = (bundle_dir / "review_template.csv").read_text(encoding="utf-8")
        template_rows = list(csv.DictReader(template_text.splitlines()))
        assert len(template_rows) == 1
        assert template_rows[0]["asset_symbol"] == "TESTVELVET"

        filled_text = (bundle_dir / "validation_sample_with_outcomes.jsonl").read_text(
            encoding="utf-8"
        )
        filled_rows = [json.loads(line) for line in filled_text.splitlines()]
        velvet = next(row for row in filled_rows if row["asset_symbol"] == "TESTVELVET")
        assert round(velvet["post_event_return_72h"], 4) == -0.2083


def test_event_fade_review_bundle_scanner_auto_exports_price_fixture():
    import contextlib
    import io
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import scanner
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    with tempfile.TemporaryDirectory() as tmp:
        sample_path = Path(tmp) / "sample.jsonl"
        bundle_dir = Path(tmp) / "review_bundle"
        event_discovery.write_validation_sample(rows, sample_path)

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_fade_review_bundle(
                str(sample_path),
                str(bundle_dir),
                limit=1,
                auto_export_prices=True,
                price_days=30,
                price_fixture_dir=str(_outcome_klines_fixture_dir()),
                event_now="2026-06-15T16:00:00Z",
            )
        text = out.getvalue()
        assert "Outcome price fixture" in text
        assert "Outcome-filled sample" in text

        expected = {
            "README.md",
            "manifest.json",
            "validation_sample.jsonl",
            "validation_sample_with_outcomes.jsonl",
            "outcome_prices.json",
            "labeling_queue.txt",
            "review_packet.md",
            "review_packet_balanced.md",
            "review_template.csv",
            "review_template_balanced.csv",
            "review_guide.md",
            "review_report.txt",
        }
        assert expected == {path.name for path in bundle_dir.iterdir()}

        manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["price_export"]["exported"] is True
        assert manifest["price_export"]["assets_written"] == 1
        assert manifest["price_export"]["price_rows_written"] == 5
        assert manifest["files"]["outcome_prices"] == "outcome_prices.json"
        assert manifest["files"]["review_packet_balanced"] == "review_packet_balanced.md"
        assert manifest["files"]["review_template_balanced"] == "review_template_balanced.csv"
        assert manifest["outcome_fill"]["prices_path"] == str(bundle_dir / "outcome_prices.json")
        assert manifest["outcome_fill"]["filled_rows"] == 1

        readme = (bundle_dir / "README.md").read_text(encoding="utf-8")
        assert "Auto price export: yes" in readme
        assert "`outcome_prices.json`" in readme

        prices = json.loads((bundle_dir / "outcome_prices.json").read_text(encoding="utf-8"))
        assert prices["schema_version"] == "event_fade_outcome_prices_v1"
        assert len(prices["prices"]) == 5

        filled_rows = [
            json.loads(line)
            for line in (bundle_dir / "validation_sample_with_outcomes.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()
        ]
        velvet = next(row for row in filled_rows if row["asset_symbol"] == "TESTVELVET")
        assert round(velvet["post_event_return_72h"], 4) == -0.2083


def test_event_fade_cache_review_bundle_scanner_writes_workspace():
    import contextlib
    import csv
    import io
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import config, scanner
    import crypto_rsi_scanner.event_alpha.artifacts.cache as event_cache

    result = _full_event_discovery_fixture_result()
    original_cache_dir = config.EVENT_DISCOVERY_CACHE_DIR
    with tempfile.TemporaryDirectory() as tmp:
        cache_dir = Path(tmp) / "cache"
        bundle_dir = Path(tmp) / "cache_review_bundle"
        config.EVENT_DISCOVERY_CACHE_DIR = cache_dir
        try:
            event_cache.write_event_discovery_cache(
                result,
                cache_dir,
                observed_at=datetime(2026, 6, 16, 12, 30, tzinfo=timezone.utc),
            )
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_fade_cache_review_bundle(
                    str(bundle_dir),
                    limit=1,
                    prices_path=str(_outcome_prices_fixture_path()),
                    event_now="2026-06-15T16:00:00Z",
                )
            text = out.getvalue()
            assert "Event-fade cached review bundle" in text
            assert "snapshots_read=17" in text
            assert "rows=17" in text
            assert "needing_review=17" in text

            expected = {
                "README.md",
                "manifest.json",
                "validation_sample.jsonl",
                "validation_sample_with_outcomes.jsonl",
                "labeling_queue.txt",
                "review_packet.md",
                "review_packet_balanced.md",
                "review_template.csv",
                "review_template_balanced.csv",
                "review_guide.md",
                "review_report.txt",
            }
            assert expected == {path.name for path in bundle_dir.iterdir()}

            readme = (bundle_dir / "README.md").read_text(encoding="utf-8")
            assert f"Input sample: `cache:{cache_dir}`" in readme

            manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
            assert manifest["source"]["sample_path"] == f"cache:{cache_dir}"
            assert manifest["source"]["review_rows"] == 17
            assert manifest["queue"]["shown_rows"] == 1
            assert manifest["files"]["review_packet_balanced"] == "review_packet_balanced.md"
            assert manifest["balanced_review_template"]["rows"] >= 1
            assert manifest["outcome_fill"]["prices_path"] == str(_outcome_prices_fixture_path())
            assert manifest["sample_summary"]["rows"] == 17
            assert manifest["sample_summary"]["asset_roles"]["proxy_instrument"] == 6
            assert manifest["sample_summary"]["source_provider_summary"]["manual_json"]["short_triggered_rows"] == 1
            assert manifest["review"]["reviewed_proxy_source_providers"] == 0
            assert manifest["review"]["min_proxy_source_providers"] == 2

            template_text = (bundle_dir / "review_template.csv").read_text(encoding="utf-8")
            template_rows = list(csv.DictReader(template_text.splitlines()))
            assert len(template_rows) == 1
            assert template_rows[0]["asset_symbol"] == "TESTVELVET"

            filled_text = (bundle_dir / "validation_sample_with_outcomes.jsonl").read_text(
                encoding="utf-8"
            )
            filled_rows = [json.loads(line) for line in filled_text.splitlines()]
            velvet = next(row for row in filled_rows if row["asset_symbol"] == "TESTVELVET")
            assert round(velvet["post_event_return_72h"], 4) == -0.2083
        finally:
            config.EVENT_DISCOVERY_CACHE_DIR = original_cache_dir


def test_event_fade_cache_review_bundle_warns_on_empty_cache():
    import contextlib
    import io
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import config, scanner

    original_cache_dir = config.EVENT_DISCOVERY_CACHE_DIR
    with tempfile.TemporaryDirectory() as tmp:
        cache_dir = Path(tmp) / "empty_cache"
        bundle_dir = Path(tmp) / "empty_bundle"
        config.EVENT_DISCOVERY_CACHE_DIR = cache_dir
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_fade_cache_review_bundle(
                    str(bundle_dir),
                    limit=5,
                    event_now="2026-06-15T16:00:00Z",
                )
            text = out.getvalue()
            assert "snapshots_read=0" in text
            assert "rows=0" in text
            assert "No validation rows were available" in text
            assert "event-discovery-status" in text

            manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
            assert manifest["source"]["review_rows"] == 0
            assert manifest["sample_summary"]["rows"] == 0
            assert manifest["sample_summary"]["asset_roles"] == {}
            assert manifest["sample_summary"]["source_provider_summary"] == {}
            assert manifest["warnings"]
            assert "No validation rows were available" in manifest["warnings"][0]

            readme = (bundle_dir / "README.md").read_text(encoding="utf-8")
            assert "Warnings:" in readme
            assert "No validation rows were available" in readme
            assert "Sample summary:" in readme
            assert "Asset roles: none" in readme
        finally:
            config.EVENT_DISCOVERY_CACHE_DIR = original_cache_dir


def test_event_fade_merge_sample_scanner_writes_merged_jsonl():
    import contextlib
    import io
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import scanner
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery

    fresh = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    reviewed = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    reviewed_row = next(row for row in reviewed if row["asset_symbol"] == "TESTVELVET")
    reviewed_row["human_label"] = "valid_proxy_fade"
    reviewed_row["post_event_return_72h"] = -0.22
    with tempfile.TemporaryDirectory() as tmp:
        fresh_path = Path(tmp) / "fresh.jsonl"
        reviewed_path = Path(tmp) / "reviewed.jsonl"
        merged_path = Path(tmp) / "merged.jsonl"
        event_discovery.write_validation_sample(fresh, fresh_path)
        event_discovery.write_validation_sample(reviewed, reviewed_path)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_fade_merge_sample(str(fresh_path), str(reviewed_path), str(merged_path))
        text = out.getvalue()
        assert "matched row(s)" in text
        assert "0 evidence-changed row(s)" in text
        rows = [json.loads(line) for line in merged_path.read_text(encoding="utf-8").splitlines()]
        velvet = next(row for row in rows if row["asset_symbol"] == "TESTVELVET")
        assert velvet["human_label"] == "valid_proxy_fade"
        assert velvet["post_event_return_72h"] == -0.22


def test_event_fade_merge_sample_scanner_reports_changed_evidence():
    import contextlib
    import io
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import scanner
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery

    fresh = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    reviewed = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    fresh_row = next(row for row in fresh if row["asset_symbol"] == "TESTVELVET")
    fresh_row["raw_content_hashes"] = ["changed-source-hash"]
    reviewed_row = next(row for row in reviewed if row["asset_symbol"] == "TESTVELVET")
    reviewed_row["review_status"] = "reviewed"
    _stamp_review_provenance(reviewed_row)
    reviewed_row["human_label"] = "valid_proxy_fade"
    reviewed_row["post_event_return_72h"] = -0.22
    with tempfile.TemporaryDirectory() as tmp:
        fresh_path = Path(tmp) / "fresh.jsonl"
        reviewed_path = Path(tmp) / "reviewed.jsonl"
        merged_path = Path(tmp) / "merged.jsonl"
        event_discovery.write_validation_sample(fresh, fresh_path)
        event_discovery.write_validation_sample(reviewed, reviewed_path)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_fade_merge_sample(str(fresh_path), str(reviewed_path), str(merged_path))
        text = out.getvalue()
        assert "1 evidence-changed row(s)" in text
        assert "Evidence-changed rows" in text
        assert "TESTVELVET" in text
        assert "raw_content_hashes" in text
        rows = [json.loads(line) for line in merged_path.read_text(encoding="utf-8").splitlines()]
        velvet = next(row for row in rows if row["asset_symbol"] == "TESTVELVET")
        assert velvet["human_label"] == ""
        assert velvet["post_event_return_72h"] is None
