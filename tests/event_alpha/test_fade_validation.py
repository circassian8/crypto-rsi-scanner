"""Event-fade validation schema, review-gate, and human-evidence regressions."""

from __future__ import annotations

import json
from collections import Counter
from tempfile import TemporaryDirectory

from tests.event_alpha import _api_helpers as _event_alpha_api_helpers

globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})

def test_event_classification_proxy_direct_and_ambiguous_cases():
    result = _event_discovery_fixture_result()
    by_coin = {classification.coin_id: classification for classification in result.classifications}
    assert by_coin["testvelvet"].is_proxy_narrative is True
    assert by_coin["testvelvet"].is_direct_beneficiary is False
    assert by_coin["testvelvet"].relationship_type == "proxy_exposure"
    assert by_coin["testbtc"].is_proxy_narrative is False
    assert by_coin["testbtc"].is_direct_beneficiary is True
    assert by_coin["testbtc"].relationship_type == "direct_token_event"
    assert by_coin["testtoken"].relationship_type == "direct_listing"
    assert by_coin["testpump"].relationship_type == "ambiguous"


def test_event_fade_auto_report_groups_discovered_candidates():
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery

    result = _full_event_discovery_fixture_result()
    report = event_discovery.format_event_fade_auto_report(result)
    assert "EVENT FADE AUTO REPORT" in report
    assert "no alerts, DB writes, paper trades, or orders" in report
    assert "EVENT RADAR" in report
    for section in (
        "PROXY WATCHLIST",
        "BLOWOFF RISK",
        "EVENT PASSED",
        "ARMED",
        "TRIGGERED",
        "REJECTED / NO TRADE",
        "AMBIGUOUS",
    ):
        assert section in report
    assert "TRIGGERED\n  TESTVELVET" in report
    assert "BLOWOFF RISK\n  TESTAI" in report
    assert "PROXY WATCHLIST\n  TESTPRED" in report
    assert "REJECTED / NO TRADE" in report
    assert "  TESTLIST     coin=testlist" in report
    assert "TESTUNLOCK" in report
    assert "AMBIGUOUS" in report
    assert "  TESTPUMP     coin=testpump" in report
    assert "missing:" in report
    assert "sources:" in report
    assert "invalidation: 8.65" in report


def test_event_fade_validation_sample_rows_and_serializers():
    import csv
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery

    exported_at = datetime(2026, 6, 16, 12, 5, tzinfo=timezone.utc)
    result = _full_event_discovery_fixture_result()
    rows = event_discovery.event_fade_validation_sample_rows(result, exported_at=exported_at)
    assert len(rows) == len(result.candidates)
    assert set(rows[0]) == set(event_discovery.VALIDATION_SAMPLE_FIELDS)

    velvet = next(row for row in rows if row["asset_symbol"] == "TESTVELVET")
    assert velvet["schema_version"] == "event_fade_validation_sample_v1"
    assert velvet["exported_at"] == "2026-06-16T12:05:00+00:00"
    assert velvet["event_name"] == "SpaceX IPO trading start"
    assert velvet["event_time_source"] == "explicit"
    assert velvet["raw_ids"] == ["velvet-spacex-proxy-1", "velvet-spacex-proxy-duplicate"]
    assert len(velvet["raw_titles"]) == 2
    assert len(velvet["raw_content_hashes"]) == 2
    assert velvet["raw_published_at"] == [
        "2026-06-13T10:00:00+00:00",
        "2026-06-13T11:00:00+00:00",
    ]
    assert velvet["raw_fetched_at"] == [
        "2026-06-15T15:00:00+00:00",
        "2026-06-15T15:30:00+00:00",
    ]
    assert velvet["published_at_min"] == "2026-06-13T10:00:00+00:00"
    assert velvet["published_at_max"] == "2026-06-13T11:00:00+00:00"
    assert velvet["fetched_at_min"] == "2026-06-15T15:00:00+00:00"
    assert velvet["fetched_at_max"] == "2026-06-15T15:30:00+00:00"
    assert velvet["source_count"] == 2
    assert velvet["relationship_type"] == "proxy_exposure"
    assert velvet["is_proxy_narrative"] is True
    assert velvet["is_direct_beneficiary"] is False
    assert velvet["asset_role"] == "proxy_instrument"
    assert velvet["asset_role_confidence"] >= 0.75
    assert velvet["asset_role_reason"]
    assert velvet["asset_role_evidence"]
    assert velvet["signal_type"] == "SHORT_TRIGGERED"
    assert velvet["fade_state"] == "TRIGGERED_SHORT"
    assert velvet["eligible"] is True
    assert velvet["component_scores"]["post_event_failure"] >= 80
    assert velvet["reason_codes"]
    assert velvet["warnings"] == ["alert-only mode; no live order placed"]
    assert velvet["trigger_observed_at"] is not None
    assert velvet["entry_reference_price"] == 7.2
    assert velvet["invalidation_level"] == 8.65
    assert velvet["human_label"] == ""
    assert velvet["human_notes"] == ""
    assert velvet["reviewed_by"] == ""
    assert velvet["reviewed_at"] == ""
    assert velvet["max_adverse_excursion"] is None
    assert velvet["post_event_return_7d"] is None
    assert velvet["event_time_entry_price"] is None
    assert velvet["event_time_post_event_return_72h"] is None

    listing = next(
        row
        for row in rows
        if row["asset_symbol"] == "TESTLIST" and row["relationship_type"] == "direct_listing"
    )
    assert listing["eligible"] is False
    assert listing["signal_type"] == "NO_TRADE"
    assert listing["large_holder_exchange_inflow"] is True
    assert listing["missing_data"] == ["technical"]

    jsonl = event_discovery.format_validation_sample_jsonl(rows)
    parsed = [json.loads(line) for line in jsonl.splitlines()]
    assert len(parsed) == len(rows)
    assert parsed[0]["schema_version"] == "event_fade_validation_sample_v1"

    csv_text = event_discovery.format_validation_sample_csv(rows)
    csv_rows = list(csv.DictReader(csv_text.splitlines()))
    assert len(csv_rows) == len(rows)
    assert json.loads(csv_rows[0]["component_scores"])
    assert json.loads(csv_rows[0]["source_urls"])

    with tempfile.TemporaryDirectory() as tmp:
        jsonl_path = Path(tmp) / "sample.jsonl"
        csv_path = Path(tmp) / "sample.csv"
        event_discovery.write_validation_sample(rows, jsonl_path)
        event_discovery.write_validation_sample(rows, csv_path)
        assert len(jsonl_path.read_text(encoding="utf-8").splitlines()) == len(rows)
        assert len(list(csv.DictReader(csv_path.read_text(encoding="utf-8").splitlines()))) == len(rows)


def test_event_fade_validation_review_blocks_unlabeled_export():
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    review = event_validation.review_validation_sample(rows)
    assert review.total_rows == len(rows)
    assert review.reviewed_rows == 0
    assert review.unlabeled_rows == len(rows)
    assert review.promotion_ready is False
    assert "reviewed proxy candidates 0/25" in review.promotion_blockers
    assert "reviewed direct/ambiguous controls 0/50" in review.promotion_blockers
    assert "reviewed SHORT_TRIGGERED candidates 0/10" in review.promotion_blockers
    next_steps = event_validation.validation_review_next_steps(review)
    assert "Add/review 25 more proxy candidate row(s) (current 0/25)." in next_steps
    assert "Add/review 50 more direct or ambiguous control row(s) (current 0/50)." in next_steps
    assert "Add/review 10 more SHORT_TRIGGERED row(s) with outcomes (current 0/10)." in next_steps

    report = event_validation.format_validation_review(review)
    assert "EVENT FADE VALIDATION SAMPLE REVIEW" in report
    assert "No reviewed labels yet" in report
    assert "NEXT SAMPLE WORK" in report
    assert "Add/review 25 more proxy candidate row(s)" in report
    assert "PROMOTION STATUS" in report
    assert "BLOCKED" in report


def test_event_fade_validation_review_requires_explicit_review_status_and_label():
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    labeled_without_status = next(row for row in rows if row["asset_symbol"] == "TESTVELVET")
    labeled_without_status["human_label"] = "valid_proxy_fade"
    labeled_without_status["max_favorable_excursion"] = 0.42
    labeled_without_status["max_adverse_excursion"] = 0.08
    labeled_without_status["post_event_return_72h"] = -0.22
    labeled_without_status["event_time_post_event_return_72h"] = -0.12
    reviewed_without_label = next(row for row in rows if row["asset_symbol"] == "TESTBTC")
    reviewed_without_label["review_status"] = "reviewed"
    invalid_label = next(row for row in rows if row["asset_symbol"] == "TESTAI")
    invalid_label["human_label"] = "valid_proxy"

    review = event_validation.review_validation_sample(
        rows,
        min_proxy_candidates=1,
        min_negative_controls=1,
        min_triggered_reviewed=1,
    )
    assert review.reviewed_rows == 0
    assert sum(cohort.reviewed_rows for cohort in review.event_type_cohorts) == 0
    assert sum(cohort.triggered_reviewed for cohort in review.event_type_cohorts) == 0
    assert review.unknown_label_rows == 1
    assert review.missing_review_status_rows == 2
    assert review.missing_human_label_rows == 1
    assert "1 labeled row(s) use unknown human_label values" in review.promotion_blockers
    assert "2 labeled row(s) are missing review_status=reviewed" in review.promotion_blockers
    assert "1 reviewed row(s) are missing human_label" in review.promotion_blockers
    next_steps = event_validation.validation_review_next_steps(review)
    assert "Fix 1 labeled row(s) with unknown human_label values." in next_steps
    assert (
        "Set review_status=reviewed for 2 labeled row(s), or clear labels that are not fully reviewed."
        in next_steps
    )
    assert "Fill human_label for 1 row(s) marked reviewed." in next_steps

    queue = event_validation.build_labeling_queue(rows, limit=3)
    categories = [item.category for item in queue.items]
    assert categories[0] == "fix_unknown_label"
    assert "fill_review_label" in categories
    assert "mark_reviewed_status" in categories


def test_event_fade_validation_review_requires_provenance_for_promotion():
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    triggered = next(row for row in rows if row["asset_symbol"] == "TESTVELVET")
    triggered["review_status"] = "reviewed"
    triggered["human_label"] = "valid_proxy_fade"
    triggered["max_favorable_excursion"] = 0.42
    triggered["max_adverse_excursion"] = 0.08
    triggered["post_event_return_72h"] = -0.22
    triggered["event_time_post_event_return_72h"] = -0.12

    review = event_validation.review_validation_sample(
        rows,
        min_proxy_candidates=1,
        min_negative_controls=0,
        min_triggered_reviewed=1,
        min_trigger_precision=0.90,
        min_mfe_mae_ratio=2.0,
        min_proxy_event_types=1,
        min_proxy_source_providers=1,
        min_trigger_btc_risk_buckets=1,
    )
    assert review.reviewed_rows == 1
    assert review.missing_review_provenance_rows == 1
    assert review.promotion_ready is False
    assert "1 reviewed row(s) are missing review provenance" in review.promotion_blockers
    assert (
        "Fill reviewed_by and reviewed_at for 1 reviewed row(s)."
        in event_validation.validation_review_next_steps(review)
    )

    report = event_validation.format_validation_review(review)
    assert "reviewed rows missing provenance: 1" in report

    queue = event_validation.build_labeling_queue(rows)
    item = next(item for item in queue.items if item.asset_symbol == "TESTVELVET")
    assert item.category == "add_review_provenance"
    assert item.missing_fields == ("reviewed_by", "reviewed_at")


def test_event_fade_validation_review_metrics_and_file_loaders():
    import tempfile
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())

    def pick(symbol, relationship=None):
        for row in rows:
            if row["asset_symbol"] != symbol:
                continue
            if relationship is not None and row["relationship_type"] != relationship:
                continue
            return row
        raise AssertionError(f"missing row for {symbol}")

    def mark(symbol, label, relationship=None):
        row = pick(symbol, relationship)
        row["human_label"] = label
        row["review_status"] = "reviewed"
        _stamp_review_provenance(row)
        row["first_seen_time"] = "2026-06-12T00:00:00+00:00"
        row["published_at_min"] = "2026-06-12T00:00:00+00:00"
        row["published_at_max"] = "2026-06-12T00:00:00+00:00"
        row["fetched_at_min"] = "2026-06-12T00:00:00+00:00"
        row["fetched_at_max"] = "2026-06-12T00:00:00+00:00"
        row["raw_published_at"] = ["2026-06-12T00:00:00+00:00"]
        row["raw_fetched_at"] = ["2026-06-12T00:00:00+00:00"]
        return row

    velvet = mark("TESTVELVET", "valid_proxy_fade")
    velvet["max_favorable_excursion"] = 0.42
    velvet["max_adverse_excursion"] = 0.08
    velvet["post_event_return_24h"] = -0.11
    velvet["post_event_return_72h"] = -0.22
    velvet["post_event_return_7d"] = -0.31
    velvet["event_time_entry_price"] = 8.0
    velvet["event_time_max_favorable_excursion"] = 0.33
    velvet["event_time_max_adverse_excursion"] = 0.03
    velvet["event_time_post_event_return_24h"] = -0.10
    velvet["event_time_post_event_return_72h"] = -0.12
    velvet["event_time_post_event_return_7d"] = -0.25

    mark("TESTAI", "valid_proxy_fade")
    mark("TESTPRED", "false_positive")
    mark("TESTBTC", "direct_event")
    mark("TESTLIST", "direct_event", "direct_listing")
    mark("TESTPUMP", "ambiguous")

    review = event_validation.review_validation_sample(
        rows,
        min_proxy_candidates=3,
        min_negative_controls=3,
        min_triggered_reviewed=1,
        min_trigger_precision=0.90,
        min_mfe_mae_ratio=2.0,
        min_proxy_event_types=2,
        min_trigger_btc_risk_buckets=1,
    )
    assert review.promotion_ready is True
    assert review.reviewed_rows == 6
    assert review.missing_review_status_rows == 0
    assert review.missing_human_label_rows == 0
    assert review.reviewed_proxy_candidates == 3
    assert review.reviewed_negative_controls == 3
    assert review.label_counts["valid_proxy_fade"] == 2
    assert review.label_counts["false_positive"] == 1
    assert review.triggered_reviewed == 1
    assert review.triggered_valid == 1
    assert review.trigger_precision == 1.0
    assert review.trigger_false_positive_rate == 0.0
    assert review.avg_mfe == 0.42
    assert review.avg_mae == 0.08
    assert round(review.mfe_mae_ratio, 2) == 5.25
    assert review.avg_post_event_return_72h == -0.22
    assert review.avg_event_time_post_event_return_72h == -0.12
    assert round(review.avg_trigger_vs_event_time_return_72h_edge, 2) == 0.10
    assert round(review.avg_trigger_latency_hours, 2) == 22.5
    assert round(review.median_trigger_latency_hours, 2) == 22.5
    assert review.negative_trigger_latency_rows == 0
    assert review.reviewed_proxy_event_types == 2
    assert review.reviewed_proxy_source_providers == 3
    assert review.reviewed_proxy_source_origins == 1
    assert review.triggered_btc_risk_buckets == 1
    assert review.missing_event_time_baseline_rows == 0
    assert review.low_confidence_trigger_event_time_rows == 0
    assert review.point_in_time_violation_rows == 0
    assert review.post_decision_source_rows == 0
    assert review.missing_source_timing_rows == 0
    assert review.promotion_blockers == ()
    assert event_validation.validation_review_next_steps(review) == (
        "Mechanical review gates are satisfied; explicit human approval is still required before promotion.",
    )

    event_type_cohorts = {cohort.name: cohort for cohort in review.event_type_cohorts}
    assert event_type_cohorts["ipo_proxy"].reviewed_rows == 2
    assert event_type_cohorts["ipo_proxy"].triggered_reviewed == 1
    assert event_type_cohorts["ipo_proxy"].trigger_precision == 1.0
    assert event_type_cohorts["ipo_proxy"].avg_post_event_return_72h == -0.22
    assert event_type_cohorts["etf_approval"].reviewed_negative_controls == 1

    relationship_cohorts = {cohort.name: cohort for cohort in review.relationship_type_cohorts}
    assert relationship_cohorts["proxy_exposure"].reviewed_proxy_candidates == 3
    assert relationship_cohorts["direct_listing"].reviewed_negative_controls == 1
    assert relationship_cohorts["ambiguous"].reviewed_negative_controls == 1

    asset_role_cohorts = {cohort.name: cohort for cohort in review.asset_role_cohorts}
    assert asset_role_cohorts["proxy_instrument"].reviewed_proxy_candidates == 3
    assert asset_role_cohorts["direct_beneficiary"].reviewed_negative_controls == 2
    assert asset_role_cohorts["ambiguous"].reviewed_negative_controls == 1

    time_source_cohorts = {cohort.name: cohort for cohort in review.event_time_source_cohorts}
    assert time_source_cohorts["explicit"].reviewed_proxy_candidates == 3
    assert time_source_cohorts["missing_event_time"].reviewed_negative_controls == 1

    source_cohorts = {cohort.name: cohort for cohort in review.source_provider_cohorts}
    assert source_cohorts["manual_json"].reviewed_rows == 3
    assert source_cohorts["manual_json"].reviewed_proxy_candidates == 1
    assert source_cohorts["cryptopanic"].reviewed_proxy_candidates == 1
    assert source_cohorts["prediction_market_events"].reviewed_proxy_candidates == 1

    origin_cohorts = {cohort.name: cohort for cohort in review.source_origin_cohorts}
    assert origin_cohorts["example.test"].reviewed_proxy_candidates == 3
    assert origin_cohorts["example.test"].reviewed_negative_controls == 2
    assert origin_cohorts["binance.com"].reviewed_negative_controls == 1

    btc_cohorts = {cohort.name: cohort for cohort in review.btc_risk_cohorts}
    assert btc_cohorts["btc_risk_neutral"].triggered_reviewed == 1
    assert btc_cohorts["btc_risk_unknown"].reviewed_negative_controls == 2

    report = event_validation.format_validation_review(review)
    assert "READY FOR HUMAN DECISION" in report
    assert "precision: 100.0%" in report
    assert "72h=-22.0%" in report
    assert "event-time short baseline" in report
    assert "trigger edge vs baseline=+10.0pp" in report
    assert "proxy event types: 2/2" in report
    assert "proxy source providers: 3/2" in report
    assert "proxy source origins: 1" in report
    assert "trigger BTC risk buckets: 1/1" in report
    assert "reviewed rows missing source timing: 0" in report
    assert "trigger latency: avg=22.5h" in report
    assert "low-confidence trigger event times: 0" in report
    assert "rows with post-decision source evidence: 0" in report
    assert "labeled rows missing review_status=reviewed: 0" in report
    assert "reviewed rows missing human_label: 0" in report
    assert "NEXT SAMPLE WORK" in report
    assert "explicit human approval is still required" in report
    assert "COHORTS" in report
    assert "By event type:" in report
    assert "ipo_proxy" in report
    assert "By asset role:" in report
    assert "proxy_instrument" in report
    assert "By event time source:" in report
    assert "explicit" in report
    assert "By source provider:" in report
    assert "prediction_market_events" in report
    assert "By source origin:" in report
    assert "example.test" in report
    assert "By BTC risk bucket:" in report

    with tempfile.TemporaryDirectory() as tmp:
        jsonl_path = Path(tmp) / "reviewed.jsonl"
        csv_path = Path(tmp) / "reviewed.csv"
        event_discovery.write_validation_sample(rows, jsonl_path)
        event_discovery.write_validation_sample(rows, csv_path)
        loaded_jsonl = event_validation.load_validation_sample(jsonl_path)
        loaded_csv = event_validation.load_validation_sample(csv_path)
        assert event_validation.review_validation_sample(
            loaded_jsonl,
            min_proxy_candidates=3,
            min_negative_controls=3,
            min_triggered_reviewed=1,
            min_trigger_precision=0.90,
            min_mfe_mae_ratio=2.0,
            min_proxy_event_types=2,
            min_trigger_btc_risk_buckets=1,
        ).promotion_ready
        assert event_validation.review_validation_sample(
            loaded_csv,
            min_proxy_candidates=3,
            min_negative_controls=3,
            min_triggered_reviewed=1,
            min_trigger_precision=0.90,
            min_mfe_mae_ratio=2.0,
            min_proxy_event_types=2,
            min_trigger_btc_risk_buckets=1,
        ).promotion_ready


def test_event_fade_validation_review_blocks_single_source_proxy_sample():
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    for symbol in {"TESTAI", "TESTPRED"}:
        row = next(row for row in rows if row["asset_symbol"] == symbol)
        row["human_label"] = "valid_proxy_fade" if symbol == "TESTAI" else "false_positive"
        row["review_status"] = "reviewed"
        _stamp_review_provenance(row)
        row["raw_providers"] = ("manual_json",)
        row["source"] = "manual_json"
        row["first_seen_time"] = "2026-06-12T00:00:00+00:00"
        row["published_at_min"] = "2026-06-12T00:00:00+00:00"
        row["published_at_max"] = "2026-06-12T00:00:00+00:00"
        row["fetched_at_min"] = "2026-06-12T00:00:00+00:00"
        row["fetched_at_max"] = "2026-06-12T00:00:00+00:00"
        row["raw_published_at"] = ["2026-06-12T00:00:00+00:00"]
        row["raw_fetched_at"] = ["2026-06-12T00:00:00+00:00"]

    review = event_validation.review_validation_sample(
        rows,
        min_proxy_candidates=2,
        min_negative_controls=0,
        min_triggered_reviewed=0,
        min_proxy_event_types=1,
        min_proxy_source_providers=2,
        min_trigger_btc_risk_buckets=0,
    )
    assert review.promotion_ready is False
    assert review.reviewed_proxy_candidates == 2
    assert review.reviewed_proxy_source_providers == 1
    assert "reviewed proxy source providers 1/2" in review.promotion_blockers
    assert (
        "Add reviewed proxy examples from 1 more source provider(s) (current 1/2)."
        in event_validation.validation_review_next_steps(review)
    )
    report = event_validation.format_validation_review(review)
    assert "proxy source providers: 1/2" in report
    assert "By source provider:" in report
    assert "manual_json" in report


def test_event_fade_validation_reports_google_news_publisher_origins():
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    for symbol, title in (
        ("TESTAI", "TESTAI offers OpenAI pre-IPO exposure - CoinDesk"),
        ("TESTPRED", "TESTPRED opens prediction-market exposure - thedefiant.io"),
    ):
        row = next(row for row in rows if row["asset_symbol"] == symbol)
        row["human_label"] = "valid_proxy_fade"
        row["review_status"] = "reviewed"
        _stamp_review_provenance(row)
        row["raw_providers"] = ["project_blog_rss"]
        row["source"] = "project_blog_rss"
        row["source_urls"] = ["https://news.google.com/rss/articles/example?oc=5"]
        row["raw_titles"] = [title]
        row["first_seen_time"] = "2026-06-12T00:00:00+00:00"
        row["published_at_min"] = "2026-06-12T00:00:00+00:00"
        row["published_at_max"] = "2026-06-12T00:00:00+00:00"
        row["fetched_at_min"] = "2026-06-12T00:00:00+00:00"
        row["fetched_at_max"] = "2026-06-12T00:00:00+00:00"
        row["raw_published_at"] = ["2026-06-12T00:00:00+00:00"]
        row["raw_fetched_at"] = ["2026-06-12T00:00:00+00:00"]

    review = event_validation.review_validation_sample(
        rows,
        min_proxy_candidates=2,
        min_negative_controls=0,
        min_triggered_reviewed=0,
        min_proxy_event_types=1,
        min_proxy_source_providers=2,
        min_trigger_btc_risk_buckets=0,
    )
    assert review.reviewed_proxy_source_providers == 1
    assert review.reviewed_proxy_source_origins == 2
    assert "reviewed proxy source providers 1/2" in review.promotion_blockers

    origin_cohorts = {cohort.name: cohort for cohort in review.source_origin_cohorts}
    assert origin_cohorts["coindesk"].reviewed_proxy_candidates == 1
    assert origin_cohorts["thedefiant.io"].reviewed_proxy_candidates == 1

    report = event_validation.format_validation_review(review)
    assert "proxy source origins: 2" in report
    assert "By source origin:" in report
    assert "coindesk" in report
    assert "thedefiant.io" in report

    queue_rows = [
        dict(row)
        for row in rows
        if row["asset_symbol"] in {"TESTAI", "TESTPRED"}
    ]
    for row in queue_rows:
        row["human_label"] = ""
        row["review_status"] = ""

    queue = event_validation.build_labeling_queue(queue_rows, limit=10)
    origin_items = {
        item.asset_symbol: item.source_origins
        for item in queue.items
        if item.asset_symbol in {"TESTAI", "TESTPRED"}
    }
    assert origin_items["TESTAI"] == ("coindesk",)
    assert origin_items["TESTPRED"] == ("thedefiant.io",)
    queue_report = event_validation.format_labeling_queue(queue)
    assert "origins: coindesk" in queue_report
    assert "origins: thedefiant.io" in queue_report

    template_rows = event_validation.build_review_template_rows(queue_rows, limit=10)
    template_by_symbol = {row["asset_symbol"]: row for row in template_rows}
    assert template_by_symbol["TESTAI"]["source_origins"] == ["coindesk"]
    assert template_by_symbol["TESTPRED"]["source_origins"] == ["thedefiant.io"]


def test_event_fade_validation_review_blocks_narrow_event_or_btc_samples():
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    for row in rows:
        if row["asset_symbol"] in {"TESTVELVET", "TESTAI"}:
            row["human_label"] = "valid_proxy_fade"
            row["review_status"] = "reviewed"
            _stamp_review_provenance(row)
        elif row["asset_symbol"] in {"TESTBTC", "TESTPUMP"}:
            row["human_label"] = "direct_event" if row["asset_symbol"] == "TESTBTC" else "ambiguous"
            row["review_status"] = "reviewed"
            _stamp_review_provenance(row)

    velvet = next(row for row in rows if row["asset_symbol"] == "TESTVELVET")
    velvet["max_favorable_excursion"] = 0.42
    velvet["max_adverse_excursion"] = 0.08
    velvet["post_event_return_72h"] = -0.22
    velvet["event_time_post_event_return_72h"] = -0.12

    review = event_validation.review_validation_sample(
        rows,
        min_proxy_candidates=2,
        min_negative_controls=2,
        min_triggered_reviewed=1,
        min_trigger_precision=0.90,
        min_mfe_mae_ratio=2.0,
        min_proxy_event_types=2,
        min_trigger_btc_risk_buckets=2,
    )
    assert review.promotion_ready is False
    assert review.reviewed_proxy_event_types == 1
    assert review.triggered_btc_risk_buckets == 1
    assert "reviewed proxy event types 1/2" in review.promotion_blockers
    assert "reviewed trigger BTC risk buckets 1/2" in review.promotion_blockers


def test_event_fade_validation_review_blocks_low_confidence_trigger_event_time():
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    triggered = next(row for row in rows if row["asset_symbol"] == "TESTVELVET")
    triggered["human_label"] = "valid_proxy_fade"
    triggered["review_status"] = "reviewed"
    _stamp_review_provenance(triggered)
    triggered["event_time_confidence"] = 0.60
    triggered["event_time_source"] = "text_date"
    triggered["max_favorable_excursion"] = 0.42
    triggered["max_adverse_excursion"] = 0.08
    triggered["post_event_return_72h"] = -0.22
    triggered["event_time_post_event_return_72h"] = -0.12

    review = event_validation.review_validation_sample(
        rows,
        min_proxy_candidates=1,
        min_negative_controls=0,
        min_triggered_reviewed=1,
        min_trigger_precision=0.90,
        min_mfe_mae_ratio=1.5,
        min_trigger_event_time_confidence=0.80,
        min_proxy_event_types=1,
        min_trigger_btc_risk_buckets=1,
    )
    assert review.promotion_ready is False
    assert review.low_confidence_trigger_event_time_rows == 1
    assert (
        "1 reviewed SHORT_TRIGGERED row(s) have event_time_confidence below 80.0%"
        in review.promotion_blockers
    )
    assert event_validation.validation_review_next_steps(review) == (
        "Confirm event times from explicit source evidence for 1 reviewed triggered row(s).",
    )
    report = event_validation.format_validation_review(review)
    assert "low-confidence trigger event times: 1" in report
    assert "By event time source:" in report
    assert "text_date" in report


def test_event_fade_validation_merge_preserves_review_fields():
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    fresh = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    reviewed = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    source = next(row for row in reviewed if row["asset_symbol"] == "TESTVELVET")
    source["review_status"] = "reviewed"
    source["reviewed_by"] = "Codex"
    source["reviewed_at"] = "2026-06-17T10:15:00+00:00"
    source["human_label"] = "valid_proxy_fade"
    source["human_notes"] = "Reviewed SpaceX proxy event."
    source["max_favorable_excursion"] = 0.42
    source["max_adverse_excursion"] = 0.08
    source["post_event_return_24h"] = -0.11
    source["post_event_return_72h"] = -0.22
    source["post_event_return_7d"] = -0.31
    stale = dict(source)
    stale["event_id"] = "missing-event"
    reviewed.append(stale)

    result = event_validation.merge_review_fields(fresh, reviewed)
    assert result.fresh_rows == len(fresh)
    assert result.reviewed_rows == len(reviewed)
    assert result.matched_rows == 1
    assert result.evidence_changed_rows == 0
    assert result.unmatched_reviewed_rows == 1
    assert result.copied_fields == 10

    merged = next(row for row in result.rows if row["asset_symbol"] == "TESTVELVET")
    assert merged["reviewed_by"] == "Codex"
    assert merged["reviewed_at"] == "2026-06-17T10:15:00+00:00"
    assert merged["human_label"] == "valid_proxy_fade"
    assert merged["human_notes"] == "Reviewed SpaceX proxy event."
    assert merged["max_favorable_excursion"] == 0.42
    assert merged["post_event_return_72h"] == -0.22
    other = next(row for row in result.rows if row["asset_symbol"] == "TESTPUMP")
    assert other["human_label"] == ""


def test_event_fade_validation_merge_skips_changed_evidence():
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    fresh = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    reviewed = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    fresh_row = next(row for row in fresh if row["asset_symbol"] == "TESTVELVET")
    source = next(row for row in reviewed if row["asset_symbol"] == "TESTVELVET")
    source["review_status"] = "reviewed"
    source["human_label"] = "valid_proxy_fade"
    source["human_notes"] = "Reviewed original source evidence."
    source["post_event_return_72h"] = -0.22
    fresh_row["raw_content_hashes"] = ["changed-source-hash"]

    result = event_validation.merge_review_fields(fresh, reviewed)
    assert result.matched_rows == 1
    assert result.evidence_changed_rows == 1
    assert result.copied_fields == 0
    assert len(result.evidence_changes) == 1
    assert result.evidence_changes[0].asset_symbol == "TESTVELVET"
    assert result.evidence_changes[0].changed_fields == ("raw_content_hashes",)
    evidence_report = event_validation.format_merge_evidence_changes(result)
    assert "TESTVELVET" in evidence_report
    assert "raw_content_hashes" in evidence_report

    merged = next(row for row in result.rows if row["asset_symbol"] == "TESTVELVET")
    assert merged["review_status"] == ""
    assert merged["human_label"] == ""
    assert merged["human_notes"] == ""
    assert merged["post_event_return_72h"] is None


def test_event_fade_validation_uses_human_event_time_for_review_metrics():
    from datetime import datetime, timedelta, timezone
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    event_time = datetime(2026, 6, 20, 0, 0, tzinfo=timezone.utc)
    trigger_time = event_time + timedelta(hours=6)
    row = {
        "schema_version": "event_fade_validation_sample_v1",
        "event_id": "hype-spacex-human-time",
        "asset_symbol": "HYPE",
        "asset_coin_id": "hyperliquid",
        "event_name": "Hyperliquid SpaceX pre-IPO market",
        "event_type": "ipo_proxy",
        "relationship_type": "proxy_exposure",
        "asset_role": "proxy_instrument",
        "signal_type": "SHORT_TRIGGERED",
        "event_time": "",
        "event_time_source": "",
        "event_time_confidence": None,
        "human_event_time": event_time.isoformat(),
        "human_event_time_source": "https://example.test/hype-spacex",
        "human_event_time_confidence": 0.95,
        "is_proxy_narrative": True,
        "is_direct_beneficiary": False,
        "trigger_observed_at": trigger_time.isoformat(),
        "review_status": "reviewed",
        "reviewed_by": "human",
        "reviewed_at": "2026-06-17T12:00:00+00:00",
        "human_label": "valid_proxy_fade",
        "source": "project_blog_rss",
        "raw_providers": ["project_blog_rss"],
        "source_urls": ["https://example.test/hype-spacex"],
        "first_seen_time": (event_time - timedelta(hours=3)).isoformat(),
        "published_at_min": (event_time - timedelta(hours=3)).isoformat(),
        "published_at_max": (event_time - timedelta(hours=3)).isoformat(),
        "fetched_at_min": (event_time - timedelta(hours=2)).isoformat(),
        "fetched_at_max": (event_time - timedelta(hours=2)).isoformat(),
        "raw_published_at": [(event_time - timedelta(hours=3)).isoformat()],
        "raw_fetched_at": [(event_time - timedelta(hours=2)).isoformat()],
        "btc_risk_on_score": 35,
    }
    candles = [
        event_validation.ValidationOutcomeCandle(event_time, close=10.0, high=10.0, low=10.0, interval="1h", source="fixture"),
        event_validation.ValidationOutcomeCandle(trigger_time, close=9.0, high=9.0, low=9.0, interval="1h", source="fixture"),
        event_validation.ValidationOutcomeCandle(event_time + timedelta(hours=24), close=8.0, high=9.2, low=7.5, interval="1h", source="fixture"),
        event_validation.ValidationOutcomeCandle(trigger_time + timedelta(hours=24), close=7.0, high=7.5, low=6.5, interval="1h", source="fixture"),
        event_validation.ValidationOutcomeCandle(event_time + timedelta(hours=72), close=7.0, high=7.2, low=6.8, interval="1h", source="fixture"),
        event_validation.ValidationOutcomeCandle(trigger_time + timedelta(hours=72), close=5.5, high=6.0, low=5.0, interval="1h", source="fixture"),
        event_validation.ValidationOutcomeCandle(event_time + timedelta(hours=168), close=6.0, high=6.2, low=5.8, interval="1h", source="fixture"),
        event_validation.ValidationOutcomeCandle(trigger_time + timedelta(hours=168), close=4.5, high=5.0, low=4.0, interval="1h", source="fixture"),
    ]

    filled = event_validation.fill_validation_outcomes([row], {"hyperliquid": candles})
    assert filled.filled_rows == 1
    filled_row = filled.rows[0]
    assert filled_row["event_time"] == ""
    assert filled_row["human_event_time"] == event_time.isoformat()
    assert round(filled_row["event_time_entry_price"], 4) == 10.0
    assert round(filled_row["event_time_post_event_return_72h"], 4) == -0.3
    assert round(filled_row["post_event_return_72h"], 4) == -0.3889

    review = event_validation.review_validation_sample(
        filled.rows,
        min_proxy_candidates=1,
        min_negative_controls=0,
        min_triggered_reviewed=1,
        min_proxy_event_types=1,
        min_proxy_source_providers=1,
        min_trigger_btc_risk_buckets=1,
    )
    assert review.low_confidence_trigger_event_time_rows == 0
    assert review.point_in_time_violation_rows == 0
    assert review.post_decision_source_rows == 0
    assert review.missing_source_timing_rows == 0
    assert review.missing_event_time_baseline_rows == 0
    assert review.avg_trigger_latency_hours == 6.0
    assert review.promotion_ready is True
    time_source_cohorts = {cohort.name: cohort for cohort in review.event_time_source_cohorts}
    assert time_source_cohorts["human_confirmed"].reviewed_proxy_candidates == 1
    report = event_validation.format_validation_review(review)
    assert "human_confirmed" in report


def test_event_fade_validation_labeling_queue_flags_low_confidence_trigger_time():
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    prices = event_validation.load_outcome_price_fixture(_outcome_prices_fixture_path())
    filled = event_validation.fill_validation_outcomes(rows, prices)
    triggered = next(row for row in filled.rows if row["asset_symbol"] == "TESTVELVET")
    triggered["human_label"] = "valid_proxy_fade"
    triggered["review_status"] = "reviewed"
    _stamp_review_provenance(triggered)
    triggered["event_time_source"] = "text_date"
    triggered["event_time_confidence"] = 0.60

    queue = event_validation.build_labeling_queue(filled.rows)
    item = next(item for item in queue.items if item.asset_symbol == "TESTVELVET")
    assert item.category == "confirm_trigger_event_time"
    assert item.suggested_label == "valid_proxy_fade"
    assert item.missing_fields == ("event_time_source", "event_time_confidence")
    assert item.event_time_source == "text_date"
    assert item.event_time_confidence == 0.60

    report = event_validation.format_labeling_queue(queue)
    assert "confirm_trigger_event_time" in report
    assert "source: text_date" in report
    assert "confidence: 60.0%" in report

    template_rows = event_validation.build_review_template_rows(filled.rows, limit=1)
    assert template_rows[0]["asset_symbol"] == "TESTVELVET"
    assert template_rows[0]["queue_category"] == "confirm_trigger_event_time"


def test_event_fade_validation_labeling_queue_prefers_explicit_event_times():
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    rows = [
        {
            "event_id": "event-text-date",
            "asset_symbol": "TEXTDATE",
            "asset_coin_id": "textdate",
            "event_name": "Text Date Proxy",
            "relationship_type": "proxy_exposure",
            "signal_type": "NO_TRADE",
            "event_time": "2026-06-10T00:00:00+00:00",
            "event_time_source": "text_date",
            "event_time_confidence": 0.60,
            "is_proxy_narrative": True,
            "is_direct_beneficiary": False,
        },
        {
            "event_id": "event-missing-time",
            "asset_symbol": "MISSINGTIME",
            "asset_coin_id": "missingtime",
            "event_name": "Missing Time Proxy",
            "relationship_type": "proxy_exposure",
            "signal_type": "NO_TRADE",
            "event_time": "",
            "event_time_source": "",
            "event_time_confidence": None,
            "is_proxy_narrative": True,
            "is_direct_beneficiary": False,
        },
        {
            "event_id": "event-explicit",
            "asset_symbol": "EXPLICIT",
            "asset_coin_id": "explicit",
            "event_name": "Explicit Proxy",
            "relationship_type": "proxy_exposure",
            "signal_type": "NO_TRADE",
            "event_time": "2026-06-20T00:00:00+00:00",
            "event_time_source": "explicit",
            "event_time_confidence": 1.0,
            "is_proxy_narrative": True,
            "is_direct_beneficiary": False,
        },
    ]

    queue = event_validation.build_labeling_queue(rows)
    assert [item.asset_symbol for item in queue.items] == [
        "TEXTDATE",
        "MISSINGTIME",
        "EXPLICIT",
    ]
    assert [item.category for item in queue.items] == [
        "confirm_proxy_event_time",
        "confirm_proxy_event_time",
        "label_proxy_candidate",
    ]
    assert queue.items[0].missing_fields == (
        "human_label",
        "human_event_time_source",
        "human_event_time_confidence",
    )
    assert queue.items[1].missing_fields == (
        "human_label",
        "human_event_time",
        "human_event_time_source",
        "human_event_time_confidence",
    )


def test_event_fade_validation_review_template_roundtrips_human_event_time():
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    rows = [{
        "event_id": "event-missing-time",
        "asset_symbol": "HYPE",
        "asset_coin_id": "hyperliquid",
        "external_asset": "SpaceX",
        "event_name": "Hyperliquid SpaceX pre-IPO market",
        "relationship_type": "proxy_exposure",
        "signal_type": "NO_TRADE",
        "event_time": "",
        "event_time_source": "",
        "event_time_confidence": None,
        "is_proxy_narrative": True,
        "is_direct_beneficiary": False,
        "first_seen_time": "2026-06-17T10:00:00+00:00",
        "raw_published_at": ["2026-06-17T09:00:00+00:00"],
        "raw_fetched_at": ["2026-06-17T10:00:00+00:00"],
        "source_urls": ["https://example.test/hype-spacex"],
        "raw_titles": ["Hyperliquid launches SpaceX pre-IPO market"],
    }]

    template_rows = event_validation.build_review_template_rows(rows, limit=1)
    assert template_rows[0]["queue_category"] == "confirm_proxy_event_time"
    assert template_rows[0]["external_asset"] == "SpaceX"
    assert template_rows[0]["human_event_time"] is None
    assert template_rows[0]["primary_source_url"] == "https://example.test/hype-spacex"
    assert template_rows[0]["primary_raw_title"] == "Hyperliquid launches SpaceX pre-IPO market"
    assert "Hyperliquid+launches+SpaceX" in template_rows[0]["source_search_url"]
    assert "fill human_event_time" in template_rows[0]["review_prompt"]
    assert "No machine event time" in template_rows[0]["event_time_review_hint"]
    assert template_rows[0]["missing_fields"] == [
        "human_label",
        "human_event_time",
        "human_event_time_source",
        "human_event_time_confidence",
    ]

    template_rows[0]["review_status"] = "reviewed"
    template_rows[0]["reviewed_by"] = "human"
    template_rows[0]["reviewed_at"] = "2026-06-17T11:00:00+00:00"
    template_rows[0]["human_label"] = "valid_proxy_fade"
    template_rows[0]["human_event_time"] = "2026-06-20T13:30:00+00:00"
    template_rows[0]["human_event_time_source"] = "https://example.test/hype-spacex"
    template_rows[0]["human_event_time_confidence"] = 0.95
    template_rows[0]["human_event_time_notes"] = "Source states the market opens at 13:30 UTC."
    result = event_validation.apply_review_template(rows, template_rows)
    assert result.matched_rows == 1
    assert result.evidence_changed_rows == 0
    assert result.copied_fields == 8
    out = result.rows[0]
    assert out["event_time"] == ""
    assert out["reviewed_by"] == "human"
    assert out["reviewed_at"] == "2026-06-17T11:00:00+00:00"
    assert out["human_event_time"] == "2026-06-20T13:30:00+00:00"
    assert out["human_event_time_source"] == "https://example.test/hype-spacex"
    assert out["human_event_time_confidence"] == 0.95
    assert out["human_event_time_notes"] == "Source states the market opens at 13:30 UTC."


def test_event_fade_validation_review_template_check_requires_valid_proxy_event_time():
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    rows = [{
        "event_id": "event-missing-time",
        "asset_symbol": "HYPE",
        "asset_coin_id": "hyperliquid",
        "event_name": "Hyperliquid SpaceX pre-IPO market",
        "relationship_type": "proxy_exposure",
        "signal_type": "NO_TRADE",
        "event_time": "",
        "event_time_source": "",
        "event_time_confidence": None,
        "is_proxy_narrative": True,
        "is_direct_beneficiary": False,
        "first_seen_time": "2026-06-17T10:00:00+00:00",
        "raw_published_at": ["2026-06-17T09:00:00+00:00"],
        "raw_fetched_at": ["2026-06-17T10:00:00+00:00"],
        "source_urls": ["https://example.test/hype-spacex"],
        "raw_titles": ["Hyperliquid launches SpaceX pre-IPO market"],
    }]

    template_rows = event_validation.build_review_template_rows(rows, limit=1)
    template_rows[0]["review_status"] = "reviewed"
    template_rows[0]["reviewed_by"] = "human"
    template_rows[0]["reviewed_at"] = "2026-06-17T11:00:00+00:00"
    template_rows[0]["human_label"] = "valid_proxy_fade"

    check = event_validation.check_review_template(rows, template_rows)
    assert not check.ready_to_apply
    assert check.edited_rows == 1
    assert check.issues[0].category == "confirm_valid_proxy_event_time"
    assert check.issues[0].missing_fields == (
        "human_event_time",
        "human_event_time_source",
        "human_event_time_confidence",
    )
    formatted = event_validation.format_review_template_check(check)
    assert "Status: not ready to apply." in formatted
    assert "confirm_valid_proxy_event_time" in formatted

    template_rows[0]["human_event_time"] = "2026-06-20T13:30:00+00:00"
    template_rows[0]["human_event_time_source"] = "https://example.test/hype-spacex"
    template_rows[0]["human_event_time_confidence"] = 0.95
    check = event_validation.check_review_template(rows, template_rows)
    assert check.ready_to_apply
    assert check.issue_rows == 0
    assert "Status: ready to apply." in event_validation.format_review_template_check(check)


def test_event_fade_validation_review_template_surfaces_source_date_hints():
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    rows = [{
        "event_id": "event-world-cup-tonight",
        "asset_symbol": "USAT",
        "asset_coin_id": "usa-fan-token",
        "event_name": "USA vs Paraguay kicks off World Cup 2026 tonight",
        "relationship_type": "proxy_attention",
        "asset_role": "proxy_instrument",
        "event_type": "sports_event",
        "signal_type": "NO_TRADE",
        "event_time": "",
        "event_time_source": "",
        "event_time_confidence": None,
        "is_proxy_narrative": True,
        "is_direct_beneficiary": False,
        "source_urls": ["https://example.test/usat-world-cup-tonight"],
        "raw_titles": ["USA vs Paraguay kicks off World Cup 2026 tonight, and crypto is already on the pitch"],
    }]

    template_rows = event_validation.build_review_template_rows(rows, limit=1)
    assert template_rows[0]["queue_category"] == "confirm_proxy_event_time"
    assert template_rows[0]["source_date_hint"] == "World Cup 2026; tonight"

    csv_text = event_validation.format_review_template_csv(template_rows)
    assert "source_date_hint" in csv_text.splitlines()[0]
    assert "World Cup 2026; tonight" in csv_text

    packet = event_validation.format_review_packet(rows, limit=1)
    assert "Source date hint: World Cup 2026; tonight" in packet


def test_event_fade_validation_review_packet_formats_human_evidence():
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    prices = event_validation.load_outcome_price_fixture(_outcome_prices_fixture_path())
    filled = event_validation.fill_validation_outcomes(rows, prices)
    packet = event_validation.format_review_packet(filled.rows, limit=1)

    assert "# Event-Fade Validation Review Packet" in packet
    assert "Rows: 17 | needing labels/status/outcomes: 17 | showing: 1" in packet
    assert "## 1. TESTVELVET - SpaceX IPO trading start" in packet
    assert "- Queue category: `label_triggered_candidate`" in packet
    assert "- Suggested label: `valid_proxy_fade or false_positive`" in packet
    assert "- Missing fields: `human_label`" in packet
    assert "time_source=`explicit` | time_confidence=`1.00`" in packet
    assert "trigger 72h=`-20.8%`" in packet
    assert "Event-time baseline: entry=`8.00` | 72h=`-20.0%` | trigger edge=`+0.8pp`" in packet
    assert "Classifier evidence:" in packet
    assert "Sources:" in packet
    assert "Source providers:" in packet
    assert "manual_json" in packet
    assert "Source origins:" in packet
    assert "example.test" in packet
    assert "Source search:" in packet
    assert "TestVelvet+offers+synthetic+exposure" in packet
    assert "human_label" in packet
