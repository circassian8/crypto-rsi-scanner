"""Focused Event Alpha LLM analyzer and extractor tests."""

from __future__ import annotations

from tests.event_alpha import _api_helpers as _event_alpha_api_helpers


globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


def test_event_llm_model_enums_and_invalid_output_rejection():
    import crypto_rsi_scanner.event_alpha.radar.llm.analyzer as event_llm_analyzer
    from crypto_rsi_scanner.event_alpha.radar.llm.models import (
        ASSET_ROLE_VALUES,
        RECOMMENDED_ALERT_ACTION_VALUES,
        RELATIONSHIP_TYPE_VALUES,
    )
    from crypto_rsi_scanner.llm_providers.fixture import FixtureLLMRelationshipProvider

    assert "source_noise" in ASSET_ROLE_VALUES
    assert "publisher_suffix_false_positive" in RELATIONSHIP_TYPE_VALUES
    assert "triggered_fade_not_set_by_llm" in RECOMMENDED_ALERT_ACTION_VALUES

    provider = FixtureLLMRelationshipProvider(_llm_golden_fixture_path(), required=True)
    raw = provider.analyze_relationship({"case_id": "llm-velvet-spacex"}).raw
    assert raw is not None
    bad = dict(raw)
    bad["asset_role"] = "trade_signal"
    packet = {
        "event": {"event_id": "llm-velvet-spacex", "external_asset": "SpaceX"},
        "asset": {"coin_id": "velvet", "symbol": "VELVET"},
    }
    try:
        event_llm_analyzer.validate_llm_analysis(
            bad,
            packet,
            provider_name="fixture",
            model=None,
            prompt_version="llm_proxy_context_v1",
        )
    except event_llm_analyzer.EventLLMValidationError as exc:
        assert "invalid LLM asset_role" in str(exc)
    else:
        raise AssertionError("invalid LLM enum should be rejected")


def test_event_llm_fixture_provider_golden_outputs():
    from crypto_rsi_scanner.llm_providers.fixture import FixtureLLMRelationshipProvider

    provider = FixtureLLMRelationshipProvider(_llm_golden_fixture_path(), required=True)
    expected = {
        "llm-btc-bitcoin-world": ("source_noise", "publisher_suffix_false_positive", "store_only"),
        "llm-xrp-ripple-effects": ("ticker_word_collision", "word_collision_false_positive", "store_only"),
        "llm-hype-word-collision": ("ticker_word_collision", "word_collision_false_positive", "store_only"),
        "llm-kcs-kucoin-source": ("source_noise", "publisher_suffix_false_positive", "store_only"),
        "llm-chainlink-world-cup": ("infrastructure", "infrastructure_provider", "store_only"),
        "llm-velvet-spacex": ("proxy_venue", "proxy_exposure", "radar_digest"),
        "llm-chz-world-cup": ("proxy_instrument", "proxy_attention", "watchlist"),
        "llm-btc-etf": ("direct_beneficiary", "direct_protocol_event", "store_only"),
    }
    for case_id, values in expected.items():
        raw = provider.analyze_relationship({"case_id": case_id}).raw
        assert raw is not None
        assert (raw["asset_role"], raw["relationship_type"], raw["recommended_alert_action"]) == values


def test_event_llm_evidence_packet_and_quote_verification():
    import crypto_rsi_scanner.event_alpha.radar.llm.analyzer as event_llm_analyzer
    from crypto_rsi_scanner.llm_providers.fixture import FixtureLLMRelationshipProvider

    result = _llm_golden_result()
    packet = _llm_packet_for(result, "llm-velvet-spacex", "velvet")
    assert packet["event"]["clean_title"] == "Velvet Capital offers synthetic exposure to SpaceX pre-IPO trading"
    assert "Velvet Capital offers synthetic exposure" in packet["event"]["original_titles"][0]
    assert packet["resolver"]["candidate_assets"]
    assert packet["external_catalyst"]["name"] == "SpaceX"

    provider = FixtureLLMRelationshipProvider(_llm_golden_fixture_path(), required=True)
    raw = provider.analyze_relationship(packet).raw
    assert raw is not None
    analysis = event_llm_analyzer.validate_llm_analysis(
        raw,
        packet,
        provider_name="fixture",
        model=None,
        prompt_version="llm_proxy_context_v1",
    )
    assert analysis.asset_role == "proxy_venue"
    assert analysis.relationship_type == "proxy_exposure"
    assert all(quote.found_in_source for quote in analysis.evidence_quotes)


def test_event_llm_missing_quote_clamps_confidence():
    import crypto_rsi_scanner.event_alpha.radar.llm.analyzer as event_llm_analyzer
    from crypto_rsi_scanner.llm_providers.fixture import FixtureLLMRelationshipProvider

    result = _llm_golden_result()
    packet = _llm_packet_for(result, "llm-invalid-quote", "velvet")
    provider = FixtureLLMRelationshipProvider(_llm_golden_fixture_path(), required=True)
    raw = provider.analyze_relationship(packet).raw
    assert raw is not None
    analysis = event_llm_analyzer.validate_llm_analysis(
        raw,
        packet,
        provider_name="fixture",
        model=None,
        prompt_version="llm_proxy_context_v1",
    )
    assert analysis.confidence == 0.50
    assert any(not quote.found_in_source for quote in analysis.evidence_quotes)
    assert any("not found in source text" in warning for warning in analysis.warnings)


def test_event_llm_openai_provider_missing_key_fails_soft():
    from crypto_rsi_scanner.llm_providers.openai_provider import OpenAILLMRelationshipProvider

    result = OpenAILLMRelationshipProvider(api_key="", model="test-model").analyze_relationship({})
    assert result.raw is None
    assert result.warning and "missing OPENAI_API_KEY" in result.warning


def test_event_llm_openai_provider_uses_configured_timeout():
    import json
    from crypto_rsi_scanner.llm_providers.openai_provider import (
        OpenAILLMExtractionProvider,
        OpenAILLMRelationshipProvider,
    )

    class FakeResponse:
        status = 200

        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"output_text": json.dumps(self.payload)}).encode("utf-8")

    seen: list[float] = []

    def relationship_opener(request, timeout):
        seen.append(timeout)
        return FakeResponse({
            "asset_role": "source_noise",
            "relationship_type": "publisher_suffix_false_positive",
            "recommended_alert_action": "store_only",
            "confidence": 0.86,
            "reason": "publisher name only",
            "evidence_quotes": [],
            "external_catalyst": {
                "name": None,
                "catalyst_type": "unknown",
                "event_time": None,
                "confidence": 0.0,
                "evidence_quotes": [],
            },
            "source_quality": {
                "source_origin": None,
                "source_confidence": 0.5,
                "timing_quality": "unknown",
                "notes": "fixture",
            },
            "warnings": [],
        })

    def extraction_opener(request, timeout):
        seen.append(timeout)
        return FakeResponse({
            "confidence": 0.80,
            "external_catalysts": [],
            "crypto_asset_mentions": [],
            "false_positive_terms": [],
            "event_date_hints": [],
            "suggested_followup_queries": [],
            "warnings": [],
        })

    relationship = OpenAILLMRelationshipProvider(
        api_key="test-key",
        model="test-model",
        timeout=4.25,
        opener=relationship_opener,
    ).analyze_relationship({})
    extraction = OpenAILLMExtractionProvider(
        api_key="test-key",
        model="test-model",
        timeout=5.5,
        opener=extraction_opener,
    ).extract_raw_event({})

    assert relationship.warning is None
    assert extraction.warning is None
    assert seen == [4.25, 5.5]


def test_event_llm_shadow_report_formats_disagreements_and_warnings():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
    import crypto_rsi_scanner.event_alpha.radar.llm.analyzer as event_llm_analyzer
    from crypto_rsi_scanner.llm_providers.fixture import FixtureLLMRelationshipProvider

    result = _llm_golden_result()
    alerts = event_alerts.build_event_alert_candidates(
        result,
        cfg=event_alerts.EventAlertConfig(),
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
    )
    rows = event_llm_analyzer.analyze_event_candidates(
        result,
        alerts,
        FixtureLLMRelationshipProvider(_llm_golden_fixture_path(), required=True),
        cfg=event_llm_analyzer.EventLLMConfig(min_prefilter_score=0, max_candidates_per_run=50),
    )
    report = event_llm_analyzer.format_llm_shadow_report(rows)
    assert "EVENT LLM SHADOW REPORT" in report
    assert "rule:" in report
    assert "llm:" in report
    assert "DISAGREE" in report
    assert "one or more evidence quotes were not found in source text" in report


def test_event_llm_advisory_adjusts_research_alert_tiers_only():
    from dataclasses import replace
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts

    _, alerts, rows = _llm_golden_alerts_and_rows()
    rule = {
        (alert.discovery_candidate.event.event_id, alert.coin_id): alert
        for alert in alerts
    }
    adjusted = event_alerts.apply_llm_advisory(alerts, rows, event_alerts.EventAlertConfig())
    by_key = {
        (alert.discovery_candidate.event.event_id, alert.coin_id): alert
        for alert in adjusted
    }

    assert rule[("llm-btc-bitcoin-world", "bitcoin")].tier == event_alerts.EventAlertTier.RADAR_DIGEST
    assert by_key[("llm-btc-bitcoin-world", "bitcoin")].tier == event_alerts.EventAlertTier.STORE_ONLY
    assert by_key[("llm-btc-bitcoin-world", "bitcoin")].effective_playbook_type == "source_noise_control"
    assert by_key[("llm-btc-bitcoin-world", "bitcoin")].rule_playbook_type != "source_noise_control"
    assert by_key[("llm-xrp-ripple-effects", "xrp")].tier == event_alerts.EventAlertTier.STORE_ONLY
    assert by_key[("llm-xrp-ripple-effects", "xrp")].effective_playbook_type == "source_noise_control"
    assert by_key[("llm-kcs-kucoin-source", "kucoin-shares")].tier == event_alerts.EventAlertTier.STORE_ONLY
    assert by_key[("llm-chainlink-world-cup", "chainlink")].tier.value in {"STORE_ONLY", "RADAR_DIGEST"}
    assert by_key[("llm-chainlink-world-cup", "chainlink")].effective_playbook_type == "infrastructure_mention"
    assert by_key[("llm-chz-world-cup", "chiliz")].tier == event_alerts.EventAlertTier.WATCHLIST
    assert by_key[("llm-chz-world-cup", "chiliz")].effective_playbook_type != "ambiguous_control"
    assert by_key[("llm-velvet-spacex", "velvet")].tier == event_alerts.EventAlertTier.RADAR_DIGEST
    assert by_key[("llm-velvet-spacex", "velvet")].original_tier == event_alerts.EventAlertTier.STORE_ONLY
    assert by_key[("llm-velvet-spacex", "velvet")].effective_playbook_type == "proxy_attention"
    assert "proxy_venue" in (by_key[("llm-velvet-spacex", "velvet")].llm_adjustment_reason or "")

    invalid = rule[("llm-invalid-quote", "velvet")]
    forced_store = [replace(invalid, tier=event_alerts.EventAlertTier.STORE_ONLY)]
    clamped = event_alerts.apply_llm_advisory(forced_store, rows, event_alerts.EventAlertConfig())[0]
    assert clamped.tier == event_alerts.EventAlertTier.STORE_ONLY
    assert clamped.llm_confidence == 0.50

    missing = event_alerts.apply_llm_advisory(alerts, [], event_alerts.EventAlertConfig())
    assert [alert.tier for alert in missing] == [alert.tier for alert in alerts]
    assert all(alert.tier != event_alerts.EventAlertTier.TRIGGERED_FADE for alert in adjusted)


def test_event_llm_advisory_does_not_create_or_remove_triggered_fade():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts

    result = _event_discovery_fixture_result()
    alerts = event_alerts.build_event_alert_candidates(
        result,
        cfg=event_alerts.EventAlertConfig(),
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
    )
    adjusted = event_alerts.apply_llm_advisory(alerts, [], event_alerts.EventAlertConfig())
    by_symbol = {alert.symbol: alert for alert in adjusted}
    assert by_symbol["TESTVELVET"].tier == event_alerts.EventAlertTier.TRIGGERED_FADE

    _, llm_alerts, rows = _llm_golden_alerts_and_rows()
    llm_adjusted = event_alerts.apply_llm_advisory(llm_alerts, rows, event_alerts.EventAlertConfig())
    assert all(alert.tier != event_alerts.EventAlertTier.TRIGGERED_FADE for alert in llm_adjusted)


def test_event_llm_advisory_report_formats_before_after_and_warnings():
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts

    _, alerts, rows = _llm_golden_alerts_and_rows()
    adjusted = event_alerts.apply_llm_advisory(alerts, rows, event_alerts.EventAlertConfig())
    report = event_alerts.format_event_alert_report(adjusted)
    assert "llm: role=source_noise" in report
    assert "llm tier adjustment: RADAR_DIGEST -> STORE_ONLY" in report
    assert "llm adjustment reason:" in report
    assert "llm: role=proxy_venue" in report


def test_event_llm_cache_keys_include_provider_model_and_metadata():
    import json
    import tempfile
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.radar.llm.analyzer as event_llm_analyzer
    from crypto_rsi_scanner.llm_providers.fixture import FixtureLLMRelationshipProvider

    _, alerts, _ = _llm_golden_alerts_and_rows()
    result = _llm_golden_result()
    with tempfile.TemporaryDirectory() as tmp:
        cache_path = Path(tmp) / "llm_cache.json"
        provider = FixtureLLMRelationshipProvider(_llm_golden_fixture_path(), required=True)
        for model in ("model-a", "model-b"):
            event_llm_analyzer.analyze_event_candidates(
                result,
                alerts,
                provider,
                cfg=event_llm_analyzer.EventLLMConfig(
                    model=model,
                    min_prefilter_score=0,
                    max_candidates_per_run=1,
                    cache_path=cache_path,
                ),
            )
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        assert len(cache) == 2
        models = {entry["model"] for entry in cache.values()}
        assert models == {"model-a", "model-b"}
        for entry in cache.values():
            assert entry["schema_version"] == event_llm_analyzer.LLM_ANALYSIS_SCHEMA_VERSION
            assert entry["provider"] == "fixture"
            assert entry["prompt_version"] == "llm_proxy_context_v1"
            assert entry["packet_hash"]
            assert entry["analyzed_at"]
            assert isinstance(entry["raw"], dict)


def test_event_llm_runtime_deadline_skips_uncached_provider_calls():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.llm.analyzer as event_llm_analyzer
    from crypto_rsi_scanner.llm_providers.fixture import FixtureLLMRelationshipProvider

    result, alerts, _ = _llm_golden_alerts_and_rows(min_prefilter_score=0)

    class CountingProvider(FixtureLLMRelationshipProvider):
        def __init__(self, path):
            super().__init__(path, required=True)
            self.calls = 0

        def analyze_relationship(self, packet):
            self.calls += 1
            return super().analyze_relationship(packet)

    provider = CountingProvider(_llm_golden_fixture_path())
    rows = event_llm_analyzer.analyze_event_candidates(
        result,
        alerts,
        provider,
        cfg=event_llm_analyzer.EventLLMConfig(
            min_prefilter_score=0,
            max_candidates_per_run=2,
            deadline_at=datetime(2000, 1, 1, tzinfo=timezone.utc),
        ),
    )
    assert provider.calls == 0
    assert [row.cache_status for row in rows] == ["skipped_runtime", "skipped_runtime"]
    assert all(any("runtime deadline exhausted" in warning for warning in row.warnings) for row in rows)


def test_event_llm_relationship_calls_run_with_bounded_parallelism():
    import threading
    import time
    import crypto_rsi_scanner.event_alpha.radar.llm.analyzer as event_llm_analyzer
    from crypto_rsi_scanner.llm_providers.base import LLMProviderResult

    result, alerts, _ = _llm_golden_alerts_and_rows(min_prefilter_score=0)

    class SlowProvider:
        name = "fixture"
        model = "parallel-fixture"

        def __init__(self):
            self.active = 0
            self.max_active = 0
            self.calls = 0
            self.lock = threading.Lock()

        def analyze_relationship(self, packet):
            with self.lock:
                self.active += 1
                self.calls += 1
                self.max_active = max(self.max_active, self.active)
            try:
                time.sleep(0.05)
                return LLMProviderResult(raw={
                    "asset_role": "source_noise",
                    "relationship_type": "publisher_suffix_false_positive",
                    "recommended_alert_action": "store_only",
                    "confidence": 0.86,
                    "reason": "parallel fixture",
                    "evidence_quotes": [],
                    "external_catalyst": {
                        "name": None,
                        "catalyst_type": "unknown",
                        "event_time": None,
                        "confidence": 0.0,
                        "evidence_quotes": [],
                    },
                    "source_quality": {
                        "source_origin": None,
                        "source_confidence": 0.5,
                        "timing_quality": "unknown",
                        "notes": "parallel fixture",
                    },
                    "warnings": [],
                })
            finally:
                with self.lock:
                    self.active -= 1

    provider = SlowProvider()
    rows = event_llm_analyzer.analyze_event_candidates(
        result,
        alerts,
        provider,
        cfg=event_llm_analyzer.EventLLMConfig(
            min_prefilter_score=0,
            max_candidates_per_run=4,
            max_parallel_calls=4,
            require_evidence_quotes=False,
        ),
    )
    assert provider.calls == 4
    assert provider.max_active > 1
    assert len(rows) == 4
    assert [row.cache_status for row in rows] == ["miss", "miss", "miss", "miss"]


def test_event_llm_budget_ledger_persists_daily_caps_and_cost_limit():
    import json
    import tempfile
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.radar.llm.analyzer as event_llm_analyzer
    from crypto_rsi_scanner.llm_providers.fixture import FixtureLLMRelationshipProvider

    result, alerts, _ = _llm_golden_alerts_and_rows(min_prefilter_score=0)

    class CountingProvider(FixtureLLMRelationshipProvider):
        def __init__(self, path):
            super().__init__(path, required=True)
            self.calls = 0

        def analyze_relationship(self, packet):
            self.calls += 1
            return super().analyze_relationship(packet)

    with tempfile.TemporaryDirectory() as tmp:
        ledger_path = Path(tmp) / "llm_budget.json"
        first = CountingProvider(_llm_golden_fixture_path())
        rows = event_llm_analyzer.analyze_event_candidates(
            result,
            alerts[:1],
            first,
            cfg=event_llm_analyzer.EventLLMConfig(
                min_prefilter_score=0,
                max_candidates_per_run=1,
                max_calls_per_day=1,
                budget_ledger_path=ledger_path,
                estimated_cost_per_call_usd=0.02,
                max_estimated_cost_usd_per_day=0.02,
            ),
        )
        assert first.calls == 1
        assert rows[0].cache_status == "miss"
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        entry = ledger["entries"][0]
        assert entry["relationship_calls_attempted"] == 1
        assert entry["estimated_cost_usd"] == 0.02

        second = CountingProvider(_llm_golden_fixture_path())
        skipped = event_llm_analyzer.analyze_event_candidates(
            result,
            alerts[:1],
            second,
            cfg=event_llm_analyzer.EventLLMConfig(
                min_prefilter_score=0,
                max_candidates_per_run=1,
                max_calls_per_day=1,
                budget_ledger_path=ledger_path,
                estimated_cost_per_call_usd=0.02,
                max_estimated_cost_usd_per_day=0.02,
            ),
        )
        assert second.calls == 0
        assert skipped[0].cache_status == "skipped_budget"
        assert any("budget" in warning for warning in skipped[0].warnings)


def test_makefile_has_event_llm_eval_target():
    from pathlib import Path

    text = Path("Makefile").read_text(encoding="utf-8")
    assert "event-llm-eval:" in text
    assert "$(PYTHON) -m crypto_rsi_scanner.event_alpha.radar.llm.eval" in text
    assert "event-alert-no-key-llm-report:" in text


def test_event_alpha_profiles_and_make_targets_are_available():
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.config.profiles as event_alpha_profiles

    fixture = event_alpha_profiles.get_profile("fixture")
    assert fixture.config_overrides["EVENT_CATALYST_SEARCH_PROVIDER"] == "fixture"
    no_key = event_alpha_profiles.get_profile("no_key_live")
    assert no_key.config_overrides["EVENT_CATALYST_SEARCH_PROVIDERS"] == ("gdelt", "rss", "polymarket")
    send = event_alpha_profiles.get_profile("research_send")
    assert send.send is True
    report = event_alpha_profiles.format_profile_report(send)
    assert "still requires --event-alert-send" in report
    assert "artifact policy:" in report
    assert event_alpha_profiles.artifact_policy(send)["snapshot_policy"] == "alertable"
    assert event_alpha_profiles.artifact_policy(send)["card_auto_write"] is True
    try:
        event_alpha_profiles.get_profile("unknown")
    except ValueError as exc:
        assert "choose one of" in str(exc)
    else:
        raise AssertionError("unknown Event Alpha profile should fail")

    text = Path("Makefile").read_text(encoding="utf-8")
    assert "event-alpha-cycle-profile:" in text
    assert "--event-alpha-profile $(PROFILE)" in text


def test_event_alpha_artifact_context_display_uses_relative_paths():
    from pathlib import Path
    from crypto_rsi_scanner import scanner
    import crypto_rsi_scanner.event_alpha.artifacts.context as event_alpha_artifacts

    context = event_alpha_artifacts.context_from_profile(
        "fixture",
        base_dir=Path("event_fade_cache").resolve(),
        artifact_namespace="display_paths",
    )
    text = scanner._event_alpha_context_block(context)  # noqa: SLF001

    assert "artifact context:" in text
    assert "- run_ledger_path: event_fade_cache/display_paths/event_alpha_runs.jsonl" in text
    assert "- research_cards_dir: event_fade_cache/display_paths/research_cards" in text
    assert "/Users/" not in text
    assert "/tmp/" not in text


def test_event_llm_golden_eval_passes_and_detects_mismatch():
    import json
    import tempfile
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.radar.llm.eval as event_llm_eval

    result = event_llm_eval.run_fixture_eval(_llm_golden_fixture_path())
    assert result.success
    assert result.passed_cases == result.total_cases == 9
    assert any("llm-invalid-quote" in warning for warning in result.warnings)
    assert "PASS: all golden cases matched" in event_llm_eval.format_eval_result(result)

    with tempfile.TemporaryDirectory() as tmp:
        source = json.loads(_llm_golden_fixture_path().read_text(encoding="utf-8"))
        source["llm_outputs"][0]["expected"] = {
            "asset_role": "proxy_instrument",
            "relationship_type": source["llm_outputs"][0]["analysis"]["relationship_type"],
            "recommended_alert_action": source["llm_outputs"][0]["analysis"]["recommended_alert_action"],
        }
        path = Path(tmp) / "bad_llm_eval.json"
        path.write_text(json.dumps(source), encoding="utf-8")
        failed = event_llm_eval.run_fixture_eval(path)
        assert not failed.success
        assert any("asset_role expected" in mismatch for mismatch in failed.mismatches)


def test_event_llm_extractor_models_fixture_outputs_and_quote_validation():
    import crypto_rsi_scanner.event_alpha.radar.llm.extractor as event_llm_extractor
    from crypto_rsi_scanner.event_alpha.radar.llm.extraction_models import (
        ASSET_MENTION_TYPE_VALUES,
        CATALYST_TYPE_VALUES,
    )
    from crypto_rsi_scanner.llm_providers.fixture import FixtureLLMExtractionProvider

    assert "project_or_token" in ASSET_MENTION_TYPE_VALUES
    assert "ipo_proxy" in CATALYST_TYPE_VALUES
    raw_events, rows = _llm_extraction_rows()
    by_raw = {row.raw_event.raw_id: row for row in rows}
    velvet = by_raw["extract-velvet-spacex"].extraction
    assert velvet is not None
    assert velvet.external_catalysts[0].name == "SpaceX"
    assert velvet.crypto_asset_mentions[0].symbol == "VELVET"
    assert all(quote.found_in_source for quote in velvet.crypto_asset_mentions[0].evidence_quotes)

    invalid = by_raw["extract-invalid-quote"].extraction
    assert invalid is not None
    assert invalid.confidence == 0.50
    assert any("not found in source text" in warning for warning in invalid.warnings)

    provider = FixtureLLMExtractionProvider(_llm_extraction_golden_fixture_path(), required=True)
    raw = provider.extract_raw_event({"case_id": "extract-velvet-spacex"}).raw
    assert raw is not None
    bad = dict(raw)
    bad["crypto_asset_mentions"] = [dict(raw["crypto_asset_mentions"][0], mention_type="trade_signal")]
    packet = event_llm_extractor.build_raw_event_packet(raw_events[0])
    try:
        event_llm_extractor.validate_llm_extraction(
            bad,
            packet,
            provider_name="fixture",
            model=None,
            prompt_version="llm_raw_event_extraction_v1",
        )
    except event_llm_extractor.EventLLMExtractionValidationError as exc:
        assert "invalid LLM extraction mention_type" in str(exc)
    else:
        raise AssertionError("invalid extraction enum should be rejected")


def test_event_llm_extractor_identifies_source_noise_and_word_collisions():
    _, rows = _llm_extraction_rows()
    by_raw = {row.raw_event.raw_id: row for row in rows}
    bitcoin_world = by_raw["extract-bitcoin-world-source-noise"].extraction
    ripple = by_raw["extract-ripple-effects"].extraction
    hype = by_raw["extract-hype-word-collision"].extraction
    assert bitcoin_world is not None and bitcoin_world.false_positive_terms[0].text == "Bitcoin World"
    assert bitcoin_world.crypto_asset_mentions[0].mention_type == "publisher_or_source"
    assert ripple is not None and ripple.false_positive_terms[0].text == "ripple effects"
    assert ripple.crypto_asset_mentions[0].mention_type == "ordinary_word"
    assert hype is not None and hype.false_positive_terms[0].text == "hype"
    assert hype.crypto_asset_mentions[0].mention_type == "ordinary_word"


def test_event_llm_extractor_runtime_deadline_skips_uncached_provider_calls():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.llm.extractor as event_llm_extractor
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent
    from crypto_rsi_scanner.llm_providers.base import LLMProviderResult

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="deadline-proxy",
        provider="news",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/deadline-proxy",
        title="SpaceX pre-IPO exposure opens through DEADLINE token",
        body="DEADLINE token offers synthetic exposure to SpaceX pre-IPO markets.",
        raw_json={},
        source_confidence=0.90,
        content_hash="deadline-proxy",
    )

    class Provider:
        name = "fixture"

        def __init__(self):
            self.calls = 0

        def extract_raw_event(self, packet):
            self.calls += 1
            return LLMProviderResult(raw={
                "confidence": 0.80,
                "external_catalysts": [],
                "crypto_asset_mentions": [],
                "false_positive_terms": [],
                "event_date_hints": [],
                "suggested_followup_queries": [],
                "warnings": [],
            })

    provider = Provider()
    rows = event_llm_extractor.analyze_raw_events(
        [raw],
        provider,
        cfg=event_llm_extractor.EventLLMExtractorConfig(
            max_events_per_run=1,
            deadline_at=datetime(2000, 1, 1, tzinfo=timezone.utc),
        ),
    )
    assert provider.calls == 0
    assert rows[0].cache_status == "skipped_runtime"
    assert any("runtime deadline exhausted" in warning for warning in rows[0].warnings)


def test_event_llm_extractor_calls_run_with_bounded_parallelism():
    import threading
    import time
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.llm.extractor as event_llm_extractor
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent
    from crypto_rsi_scanner.llm_providers.base import LLMProviderResult

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    raw_events = [
        RawDiscoveredEvent(
            raw_id=f"parallel-proxy-{idx}",
            provider="news",
            fetched_at=now,
            published_at=now,
            source_url=f"https://example.test/parallel-proxy-{idx}",
            title=f"SpaceX pre-IPO exposure opens through PAR{idx} token",
            body=f"PAR{idx} token offers synthetic exposure to SpaceX pre-IPO markets.",
            raw_json={},
            source_confidence=0.90,
            content_hash=f"parallel-proxy-{idx}",
        )
        for idx in range(4)
    ]

    class SlowProvider:
        name = "fixture"
        model = "parallel-fixture"

        def __init__(self):
            self.active = 0
            self.max_active = 0
            self.calls = 0
            self.lock = threading.Lock()

        def extract_raw_event(self, packet):
            with self.lock:
                self.active += 1
                self.calls += 1
                self.max_active = max(self.max_active, self.active)
            try:
                time.sleep(0.05)
                return LLMProviderResult(raw={
                    "confidence": 0.80,
                    "external_catalysts": [],
                    "crypto_asset_mentions": [],
                    "false_positive_terms": [],
                    "event_date_hints": [],
                    "suggested_followup_queries": [],
                    "warnings": [],
                })
            finally:
                with self.lock:
                    self.active -= 1

    provider = SlowProvider()
    rows = event_llm_extractor.analyze_raw_events(
        raw_events,
        provider,
        cfg=event_llm_extractor.EventLLMExtractorConfig(
            max_events_per_run=4,
            max_parallel_calls=4,
            require_evidence_quotes=False,
        ),
    )
    assert provider.calls == 4
    assert provider.max_active > 1
    assert len(rows) == 4
    assert [row.cache_status for row in rows] == ["miss", "miss", "miss", "miss"]


def test_event_llm_extractor_openai_missing_key_fails_soft():
    from crypto_rsi_scanner.llm_providers.openai_provider import OpenAILLMExtractionProvider

    result = OpenAILLMExtractionProvider(api_key="", model="test-model").extract_raw_event({})
    assert result.raw is None
    assert result.warning and "missing OPENAI_API_KEY" in result.warning


def test_event_llm_extractor_enrichment_still_requires_resolver_validation():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.llm.extractor as event_llm_extractor
    from crypto_rsi_scanner.event_core.models import DiscoveredAsset, RawDiscoveredEvent
    from crypto_rsi_scanner.llm_providers.base import LLMProviderResult

    class Provider:
        name = "fixture"

        def extract_raw_event(self, packet):
            return LLMProviderResult(raw={
                "confidence": 0.91,
                "external_catalysts": [{
                    "name": "SpaceX",
                    "catalyst_type": "ipo_proxy",
                    "event_time": None,
                    "event_time_confidence": 0.0,
                    "confidence": 0.90,
                    "evidence_quotes": [{"text": "SpaceX exposure", "source_field": "body", "supports": "external catalyst"}],
                }],
                "crypto_asset_mentions": [{
                    "name": "Missed Proxy",
                    "symbol": "MISS",
                    "coin_id": None,
                    "contract_address": None,
                    "mention_type": "project_or_token",
                    "confidence": 0.90,
                    "evidence_quotes": [{"text": "MISS is the ticker", "source_field": "body", "supports": "asset mention"}],
                }],
                "false_positive_terms": [],
                "event_date_hints": [],
                "suggested_followup_queries": [],
                "warnings": [],
            })

    raw = RawDiscoveredEvent(
        raw_id="extract-missed-proxy",
        provider="test",
        fetched_at=datetime(2026, 6, 16, 12, tzinfo=timezone.utc),
        published_at=datetime(2026, 6, 16, 11, tzinfo=timezone.utc),
        source_url="https://example.test/missed-proxy",
        title="SpaceX exposure market opens",
        body="A source says MISS is the ticker for a new SpaceX exposure proxy.",
        raw_json={},
        source_confidence=0.90,
        content_hash="abc",
    )
    rows = event_llm_extractor.analyze_raw_events([raw], Provider())
    enriched = event_llm_extractor.enrich_raw_events_with_extractions([raw], rows)
    assert "LLM extracted research hints" in (enriched[0].body or "")
    assert event_discovery.run_discovery(enriched, [], now=datetime(2026, 6, 16, 12, tzinfo=timezone.utc)).candidates == ()

    assets = [DiscoveredAsset(
        coin_id="missed-proxy",
        symbol="MISS",
        name="Missed Proxy",
        aliases=("missed proxy", "miss"),
    )]
    result = event_discovery.run_discovery(
        enriched,
        assets,
        now=datetime(2026, 6, 16, 12, tzinfo=timezone.utc),
    )
    assert len(result.candidates) == 1
    assert result.candidates[0].asset.coin_id == "missed-proxy"


def test_event_llm_extract_report_and_eval_pass():
    import crypto_rsi_scanner.event_alpha.radar.llm.extract_eval as event_llm_extract_eval
    import crypto_rsi_scanner.event_alpha.radar.llm.extractor as event_llm_extractor

    _, rows = _llm_extraction_rows()
    report = event_llm_extractor.format_llm_extract_report(rows)
    assert "EVENT LLM RAW EXTRACTION REPORT" in report
    assert "Velvet Capital/VELVET" in report
    assert "false-positive terms: Bitcoin World" in report
    assert "warning: one or more evidence quotes were not found in source text" in report

    result = event_llm_extract_eval.run_fixture_eval(_llm_extraction_golden_fixture_path())
    assert result.success
    assert result.passed_cases == result.total_cases == 7
    assert any("extract-invalid-quote" in warning for warning in result.warnings)
    assert "PASS: all golden cases matched" in event_llm_extract_eval.format_eval_result(result)


def test_makefile_has_event_llm_extract_eval_target():
    from pathlib import Path

    text = Path("Makefile").read_text(encoding="utf-8")
    assert "event-llm-extract-eval:" in text
    assert "crypto_rsi_scanner.event_alpha.radar.llm.extract_eval" in text


def test_event_llm_extract_scanner_report_uses_runtime_config():
    import contextlib
    import io
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import config, scanner
    import crypto_rsi_scanner.event_alpha.notifications.delivery as delivery

    path = _llm_extraction_golden_fixture_path()
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
        "EVENT_LLM_EXTRACTOR_ENABLED": config.EVENT_LLM_EXTRACTOR_ENABLED,
        "EVENT_LLM_EXTRACTOR_MODE": config.EVENT_LLM_EXTRACTOR_MODE,
        "EVENT_LLM_EXTRACTOR_PROVIDER": config.EVENT_LLM_EXTRACTOR_PROVIDER,
        "EVENT_LLM_EXTRACTOR_MODEL": config.EVENT_LLM_EXTRACTOR_MODEL,
        "EVENT_LLM_EXTRACTOR_OPENAI_TIMEOUT": config.EVENT_LLM_EXTRACTOR_OPENAI_TIMEOUT,
        "EVENT_LLM_EXTRACTOR_MAX_EVENTS_PER_RUN": config.EVENT_LLM_EXTRACTOR_MAX_EVENTS_PER_RUN,
        "EVENT_LLM_EXTRACTOR_REQUIRE_EVIDENCE_QUOTES": config.EVENT_LLM_EXTRACTOR_REQUIRE_EVIDENCE_QUOTES,
        "EVENT_LLM_EXTRACTOR_CACHE_PATH": config.EVENT_LLM_EXTRACTOR_CACHE_PATH,
        "EVENT_LLM_EXTRACTOR_PROMPT_VERSION": config.EVENT_LLM_EXTRACTOR_PROMPT_VERSION,
        "EVENT_LLM_BUDGET_LEDGER_PATH": config.EVENT_LLM_BUDGET_LEDGER_PATH,
        "EVENT_LLM_MAX_PARALLEL_CALLS": config.EVENT_LLM_MAX_PARALLEL_CALLS,
    }
    budget_tmp = tempfile.TemporaryDirectory()
    config.EVENT_DISCOVERY_EVENTS_PATH = path
    config.EVENT_DISCOVERY_ALIASES_PATH = _llm_golden_fixture_path()
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
    config.EVENT_LLM_EXTRACTOR_ENABLED = False
    config.EVENT_LLM_EXTRACTOR_MODE = "shadow"
    config.EVENT_LLM_EXTRACTOR_PROVIDER = "fixture"
    config.EVENT_LLM_EXTRACTOR_MODEL = None
    config.EVENT_LLM_EXTRACTOR_OPENAI_TIMEOUT = 30.0
    config.EVENT_LLM_EXTRACTOR_MAX_EVENTS_PER_RUN = 50
    config.EVENT_LLM_EXTRACTOR_REQUIRE_EVIDENCE_QUOTES = True
    config.EVENT_LLM_EXTRACTOR_CACHE_PATH = None
    config.EVENT_LLM_EXTRACTOR_PROMPT_VERSION = "llm_raw_event_extraction_v1"
    config.EVENT_LLM_BUDGET_LEDGER_PATH = Path(budget_tmp.name) / "event_llm_budget.json"
    config.EVENT_LLM_MAX_PARALLEL_CALLS = 1
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_llm_extract_report(event_now="2026-06-15T16:00:00Z")
        text = out.getvalue()
        assert "EVENT LLM RAW EXTRACTION REPORT" in text
        assert "extract-velvet-spacex" in text
        assert "Velvet Capital/VELVET" in text
    finally:
        for name, value in original.items():
            setattr(config, name, value)
        budget_tmp.cleanup()
