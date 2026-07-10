"""Focused Event Alpha operating-pipeline and scanner tests."""

from __future__ import annotations

from tests.event_alpha import _api_helpers as _event_alpha_api_helpers


globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


def test_event_alpha_radar_scanner_report_with_fixture_anomalies():
    import contextlib
    import io
    from pathlib import Path
    from crypto_rsi_scanner import config, scanner
    import crypto_rsi_scanner.event_alpha.notifications.delivery as delivery

    original = {
        "EVENT_DISCOVERY_EVENTS_PATH": config.EVENT_DISCOVERY_EVENTS_PATH,
        "EVENT_DISCOVERY_ALIASES_PATH": config.EVENT_DISCOVERY_ALIASES_PATH,
        "EVENT_DISCOVERY_UNIVERSE_PATH": config.EVENT_DISCOVERY_UNIVERSE_PATH,
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE": config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE,
        "EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE": config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE,
        "EVENT_DISCOVERY_CRYPTOPANIC_PATH": config.EVENT_DISCOVERY_CRYPTOPANIC_PATH,
        "EVENT_DISCOVERY_CRYPTOPANIC_LIVE": config.EVENT_DISCOVERY_CRYPTOPANIC_LIVE,
        "EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN": config.EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN,
        "EVENT_DISCOVERY_GDELT_PATH": config.EVENT_DISCOVERY_GDELT_PATH,
        "EVENT_DISCOVERY_GDELT_LIVE": config.EVENT_DISCOVERY_GDELT_LIVE,
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH": config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH,
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE": config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE,
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS": config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS,
        "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH": config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH,
        "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE": config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE,
        "EVENT_DISCOVERY_COINALYZE_LIVE": config.EVENT_DISCOVERY_COINALYZE_LIVE,
        "EVENT_DISCOVERY_UNIVERSE_LIVE": config.EVENT_DISCOVERY_UNIVERSE_LIVE,
        "EVENT_DISCOVERY_UNIVERSE_FETCH_LIMIT": config.EVENT_DISCOVERY_UNIVERSE_FETCH_LIMIT,
        "EVENT_SOURCE_ENRICHMENT_ENABLED": config.EVENT_SOURCE_ENRICHMENT_ENABLED,
        "EVENT_SOURCE_ENRICHMENT_MAX_ROWS_PER_RUN": config.EVENT_SOURCE_ENRICHMENT_MAX_ROWS_PER_RUN,
        "EVENT_MARKET_ENRICHMENT_ENABLED": config.EVENT_MARKET_ENRICHMENT_ENABLED,
        "EVENT_ANOMALY_SCANNER_ENABLED": config.EVENT_ANOMALY_SCANNER_ENABLED,
        "EVENT_ANOMALY_MIN_RETURN_24H": config.EVENT_ANOMALY_MIN_RETURN_24H,
        "EVENT_ANOMALY_MIN_VOLUME_MCAP": config.EVENT_ANOMALY_MIN_VOLUME_MCAP,
        "EVENT_ANOMALY_MIN_VOLUME_ZSCORE": config.EVENT_ANOMALY_MIN_VOLUME_ZSCORE,
        "EVENT_ANOMALY_MAX_ASSETS": config.EVENT_ANOMALY_MAX_ASSETS,
    }
    config.EVENT_DISCOVERY_EVENTS_PATH = None
    config.EVENT_DISCOVERY_ALIASES_PATH = None
    config.EVENT_DISCOVERY_UNIVERSE_PATH = Path("fixtures/coingecko_smoke/top_markets.json")
    config.EVENT_DISCOVERY_UNIVERSE_LIVE = False
    config.EVENT_DISCOVERY_UNIVERSE_FETCH_LIMIT = 0
    config.EVENT_MARKET_ENRICHMENT_ENABLED = True
    config.EVENT_ANOMALY_SCANNER_ENABLED = True
    config.EVENT_ANOMALY_MIN_RETURN_24H = 0.03
    config.EVENT_ANOMALY_MIN_VOLUME_MCAP = 0.05
    config.EVENT_ANOMALY_MIN_VOLUME_ZSCORE = 3.0
    config.EVENT_ANOMALY_MAX_ASSETS = 10
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_alpha_radar_report(event_now="2026-06-15T16:00:00Z")
        text = out.getvalue()
        assert "EVENT RESEARCH ALERT REPORT" in text
        assert "market anomaly" in text
        assert "playbook: market_anomaly_unknown" in text
        assert "STORE_ONLY" in text
    finally:
        for name, value in original.items():
            setattr(config, name, value)


def test_event_alpha_pipeline_runs_watchlist_and_router_cycle():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.radar.pipeline as event_alpha_pipeline
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    result = _full_event_discovery_fixture_result()
    with tempfile.TemporaryDirectory() as tmp:
        pipe = event_alpha_pipeline.run_event_alpha_pipeline(
            result,
            alert_cfg=event_alerts.EventAlertConfig(),
            now=datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc),
            watchlist_cfg=event_watchlist.EventWatchlistConfig(
                enabled=True,
                state_path=Path(tmp) / "watchlist.jsonl",
            ),
            router_cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True),
            refresh_watchlist=True,
            route=True,
        )
        assert pipe.raw_events == 20
        assert pipe.candidates == 17
        assert pipe.clusters >= 1
        assert len(pipe.alerts) == 17
        assert pipe.watchlist_entries >= 17
        assert len(pipe.impact_hypotheses) >= 1
        assert pipe.watchlist_escalations >= 1
        assert pipe.routed >= 17
        assert pipe.alertable >= 1
        assert any(
            decision.route == event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH
            and decision.entry.symbol == "TESTVELVET"
            for decision in pipe.router_result.decisions
        )
        text = event_alpha_pipeline.format_event_alpha_pipeline_report(pipe)
        assert "EVENT ALPHA PIPELINE REPORT" in text
        assert "raw_events=20" in text
        assert "clusters=" in text
        assert "TRIGGERED_FADE_RESEARCH" in text
        assert "no trades, paper rows, or live RSI routing" in text

        disabled = event_alpha_pipeline.run_event_alpha_pipeline(
            result,
            alert_cfg=event_alerts.EventAlertConfig(),
            now=datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc),
            watchlist_cfg=event_watchlist.EventWatchlistConfig(
                enabled=False,
                state_path=Path(tmp) / "disabled-watchlist.jsonl",
            ),
            router_cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True),
            refresh_watchlist=True,
            route=True,
        )
        assert disabled.watchlist_result is None
        assert disabled.router_result is None
        assert "watchlist refresh skipped" in "; ".join(disabled.warnings)
        assert "router skipped" in "; ".join(disabled.warnings)


def test_event_alpha_pipeline_writes_non_alertable_hypothesis_rows():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as event_alpha_notifications
    import crypto_rsi_scanner.event_alpha.radar.pipeline as event_alpha_pipeline
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
    from crypto_rsi_scanner.event_core.models import EventDiscoveryResult, NormalizedEvent, RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="spacex-hypothesis",
        provider="rss",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/spacex-hypothesis",
        title="SpaceX pre-IPO exposure heats up",
        body="Tokenized stock venues may see attention around SpaceX pre-IPO markets.",
        raw_json={
            "event": {
                "event_id": "spacex-hypothesis",
                "event_name": "SpaceX pre-IPO exposure heats up",
                "event_type": "ipo_proxy",
                "event_time": "2026-06-20T13:30:00Z",
                "event_time_confidence": 0.85,
                "external_asset": "SpaceX",
                "description": "Tokenized stock venues may see attention around SpaceX pre-IPO markets.",
                "confidence": 0.88,
            }
        },
        source_confidence=0.88,
        content_hash="spacex-hypothesis",
    )
    event = NormalizedEvent(
        event_id="spacex-hypothesis",
        raw_ids=(raw.raw_id,),
        event_name=raw.title,
        event_type="ipo_proxy",
        event_time=now,
        event_time_confidence=0.85,
        first_seen_time=now,
        source=raw.provider,
        source_urls=(raw.source_url,),
        external_asset="SpaceX",
        description=raw.body,
        confidence=0.88,
    )
    result = EventDiscoveryResult(
        raw_events=(raw,),
        normalized_events=(event,),
        links=(),
        classifications=(),
        candidates=(),
    )

    with tempfile.TemporaryDirectory() as tmp:
        pipe = event_alpha_pipeline.run_event_alpha_pipeline(
            result,
            alert_cfg=event_alerts.EventAlertConfig(),
            now=now,
            watchlist_cfg=event_watchlist.EventWatchlistConfig(
                enabled=True,
                state_path=Path(tmp) / "watchlist.jsonl",
            ),
            router_cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True),
            refresh_watchlist=True,
            route=True,
        )
        assert len(pipe.impact_hypotheses) >= 1
        assert pipe.watchlist_entries >= 1
        hypothesis_entries = [
            entry for entry in pipe.watchlist_result.entries
            if entry.state == event_watchlist.EventWatchlistState.HYPOTHESIS.value
        ]
        assert hypothesis_entries
        assert all(entry.should_alert is False for entry in hypothesis_entries)
        by_state = {decision.entry.state: decision for decision in pipe.router_result.decisions}
        assert by_state[event_watchlist.EventWatchlistState.HYPOTHESIS.value].alertable is False
        assert by_state[event_watchlist.EventWatchlistState.HYPOTHESIS.value].route == event_alpha_router.EventAlphaRoute.STORE_ONLY
        cfg = event_alpha_notifications.EventAlphaNotificationConfig(
            enabled=True,
            exploratory_digest_enabled=True,
            exploratory_digest_include_controls=True,
            quality_mode="exploratory_only",
        )
        plan = event_alpha_notifications.build_notification_plan(
            pipe.router_result.decisions,
            storage=_NotifyFakeStorage(),
            cfg=cfg,
            now=now,
        )
        digest = event_alpha_notifications.format_exploratory_telegram_digest(
            plan.exploratory_items,
            profile="notify_no_key",
            cfg=cfg,
        )
        assert "impact hypothesis awaiting validation" in digest
        assert "not alertable yet" in digest


def test_event_alpha_pipeline_hypothesis_search_validates_before_token_watchlist():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.radar.pipeline as event_alpha_pipeline
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
    from crypto_rsi_scanner.event_core.models import EventDiscoveryResult, NormalizedEvent, RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="spacex-sector",
        provider="rss",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/spacex-sector",
        title="SpaceX pre-IPO exposure heats up",
        body="Tokenized stock venues may see attention around SpaceX pre-IPO markets.",
        raw_json={
            "event": {
                "event_id": "spacex-sector",
                "event_name": "SpaceX pre-IPO exposure heats up",
                "event_type": "ipo_proxy",
                "event_time": "2026-06-20T13:30:00Z",
                "event_time_confidence": 0.85,
                "external_asset": "SpaceX",
                "description": "Tokenized stock venues may see attention around SpaceX pre-IPO markets.",
                "confidence": 0.88,
            }
        },
        source_confidence=0.88,
        content_hash="spacex-sector",
    )
    validation = RawDiscoveredEvent(
        raw_id="velvet-validation",
        provider="fixture_search",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/velvet-spacex",
        title="VELVET opens SpaceX pre-IPO exposure",
        body="Velvet Capital users can trade tokenized stock style exposure to SpaceX.",
        raw_json={},
        source_confidence=0.92,
        content_hash="velvet-validation",
    )
    event = NormalizedEvent(
        event_id="spacex-sector",
        raw_ids=(raw.raw_id,),
        event_name=raw.title,
        event_type="ipo_proxy",
        event_time=now,
        event_time_confidence=0.85,
        first_seen_time=now,
        source=raw.provider,
        source_urls=(raw.source_url,),
        external_asset="SpaceX",
        description=raw.body,
        confidence=0.88,
    )
    result = EventDiscoveryResult(
        raw_events=(raw,),
        normalized_events=(event,),
        links=(),
        classifications=(),
        candidates=(),
    )
    provider = event_catalyst_search.FixtureCatalystSearchProvider(
        rows_by_query={"VELVET SpaceX pre-IPO exposure": (validation,)}
    )
    with tempfile.TemporaryDirectory() as tmp:
        pipe = event_alpha_pipeline.run_event_alpha_pipeline(
            result,
            alert_cfg=event_alerts.EventAlertConfig(),
            now=now,
            hypothesis_search_provider=provider,
            hypothesis_search_cfg=event_catalyst_search.EventImpactHypothesisSearchConfig(
                enabled=True,
                max_hypotheses=5,
                max_queries_per_hypothesis=4,
                min_confidence=0.50,
                min_result_confidence=0.50,
            ),
            watchlist_cfg=event_watchlist.EventWatchlistConfig(
                enabled=True,
                state_path=Path(tmp) / "watchlist.jsonl",
            ),
            router_cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True),
            refresh_watchlist=True,
            route=True,
        )
    assert pipe.hypothesis_search_queries > 0
    assert pipe.hypothesis_search_results >= 1
    assert pipe.hypotheses_validated >= 1
    entries = [entry for entry in pipe.watchlist_result.entries if entry.relationship_type == "impact_hypothesis"]
    assert any(entry.symbol == "VELVET" and entry.state == event_watchlist.EventWatchlistState.RADAR.value for entry in entries)
    assert all(entry.state != event_watchlist.EventWatchlistState.TRIGGERED_FADE.value for entry in entries)


def test_event_impact_hypothesis_store_persists_profile_scoped_rows():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses
    import crypto_rsi_scanner.event_alpha.radar.impact_hypothesis_store as event_impact_hypothesis_store

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    hypothesis = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:test",
        event_cluster_id="cluster:test",
        event_type="ipo_proxy",
        external_asset="SpaceX",
        impact_category=event_impact_hypotheses.ImpactCategory.RWA_PREIPO_PROXY.value,
        candidate_sectors=("tokenized_stock_venues",),
        candidate_symbols=("VELVET",),
        suggested_candidate_assets=({
            "source": "llm_extraction",
            "symbol": "VELVET",
            "coin_id": "velvet",
            "confidence": 0.91,
        },),
        candidate_source="llm_extraction",
        confidence=0.82,
        search_queries=("VELVET SpaceX pre-IPO exposure",),
        status=event_impact_hypotheses.HypothesisStatus.VALIDATION_SEARCH_PENDING.value,
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "notify_llm" / "event_impact_hypotheses.jsonl"
        write = event_impact_hypothesis_store.write_impact_hypotheses(
            (hypothesis,),
            cfg=event_impact_hypothesis_store.EventImpactHypothesisStoreConfig(path=path),
            now=now,
            run_id="run-1",
            profile="notify_llm",
            run_mode="notification_burn_in",
            artifact_namespace="notify_llm",
        )
        assert write.success is True
        assert write.rows_written == 1
        read = event_impact_hypothesis_store.load_impact_hypotheses(path)
        assert read.rows_read == 1
        row = read.rows[0]
        assert row["run_id"] == "run-1"
        assert row["profile"] == "notify_llm"
        assert row["artifact_namespace"] == "notify_llm"
        assert row["candidate_source"] == "llm_extraction"
        assert row["suggested_candidate_assets"][0]["symbol"] == "VELVET"
        report = event_impact_hypothesis_store.format_impact_hypotheses_store_report(read)
        assert "EVENT IMPACT HYPOTHESES REPORT" in report
        assert "candidate_sources: llm_extraction=1" in report
        assert "VELVET/velvet" in report


def test_event_alpha_daily_brief_summarizes_rejected_hypothesis_samples():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief

    text = event_alpha_daily_brief.build_daily_brief(
        run_rows=({
            "run_id": "r1",
            "profile": "notify_llm",
            "artifact_namespace": "notify_llm",
            "run_mode": "notification_burn_in",
            "started_at": "2026-06-18T12:00:00+00:00",
            "finished_at": "2026-06-18T12:01:00+00:00",
            "impact_hypotheses": 1,
            "hypotheses_validated": 0,
            "hypothesis_promotions": 0,
            "hypothesis_search_queries": 1,
            "hypothesis_search_results": 0,
        },),
        hypothesis_rows=({
            "row_type": "event_impact_hypothesis",
            "schema_version": "event_impact_hypothesis_store_v1",
            "profile": "notify_llm",
            "artifact_namespace": "notify_llm",
            "run_mode": "notification_burn_in",
            "status": "rejected",
            "validation_stage": "rejected",
            "impact_category": "ai_ipo_proxy",
            "external_asset": "OpenAI",
            "hypothesis_score": 44.0,
            "why_not_promoted": ["candidate_identity_not_validated"],
            "external_entities": [{"name": "OpenAI"}],
            "crypto_candidate_assets": [],
            "rejected_validation_samples": [{
                "result_title": "Generic OpenAI market recap",
                "rejection_reason": "result_identity_rejected",
            }],
        },),
        requested_profile="notify_llm",
        artifact_namespace="notify_llm",
        run_mode="notification_burn_in",
        generated_at=datetime(2026, 6, 18, 12, 2, tzinfo=timezone.utc),
    )
    assert "Rejected validation evidence samples: 1" in text
    assert "Rejected evidence reasons: result_identity_rejected=1" in text
    assert "Generic OpenAI market recap" in text


def test_event_impact_hypothesis_generation_uses_llm_suggested_assets_but_not_validation():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses
    from crypto_rsi_scanner.event_alpha.radar.llm.extraction_models import (
        EventLLMCryptoAssetMention,
        EventLLMRawEventExtraction,
    )
    from crypto_rsi_scanner.event_alpha.radar.llm.extractor import EventLLMExtractionReportRow
    from crypto_rsi_scanner.event_core.models import EventDiscoveryResult, NormalizedEvent, RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="spacex-llm-mention",
        provider="rss",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/spacex",
        title="SpaceX pre-IPO exposure heats up",
        body="New source says Velvet Capital is adjacent to SpaceX pre-IPO exposure.",
        raw_json={},
        source_confidence=0.90,
        content_hash="spacex-llm-mention",
    )
    event = NormalizedEvent(
        event_id="spacex-llm-mention",
        raw_ids=(raw.raw_id,),
        event_name=raw.title,
        event_type="ipo_proxy",
        event_time=now,
        event_time_confidence=0.85,
        first_seen_time=now,
        source=raw.provider,
        source_urls=(raw.source_url,),
        external_asset="SpaceX",
        description=raw.body,
        confidence=0.90,
    )
    extraction = EventLLMRawEventExtraction(
        schema_version="event_llm_extraction_v1",
        provider="fixture",
        model="fixture",
        prompt_version="test",
        raw_id=raw.raw_id,
        confidence=0.90,
        external_catalysts=(),
        crypto_asset_mentions=(
            EventLLMCryptoAssetMention(
                name="Velvet Capital",
                symbol="VELVET",
                coin_id="velvet",
                contract_address=None,
                mention_type="project_or_token",
                confidence=0.92,
            ),
        ),
    )
    hypotheses = event_impact_hypotheses.generate_impact_hypotheses(
        EventDiscoveryResult((raw,), (event,), (), (), ()),
        extraction_rows=(EventLLMExtractionReportRow(raw_event=raw, extraction=extraction),),
        now=now,
        taxonomy={},
    )
    assert hypotheses
    hypothesis = hypotheses[0]
    assert "VELVET" in hypothesis.candidate_symbols
    assert hypothesis.candidate_source == "llm_extraction"
    assert hypothesis.suggested_candidate_assets[0]["symbol"] == "VELVET"
    assert hypothesis.validated_candidate_assets == ()
    assert hypothesis.status == event_impact_hypotheses.HypothesisStatus.VALIDATION_SEARCH_PENDING.value


def test_event_impact_hypothesis_separates_external_entities_from_crypto_candidates():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses
    from crypto_rsi_scanner.event_alpha.radar.llm.extraction_models import (
        EventLLMCryptoAssetMention,
        EventLLMRawEventExtraction,
    )
    from crypto_rsi_scanner.event_alpha.radar.llm.extractor import EventLLMExtractionReportRow
    from crypto_rsi_scanner.event_core.models import EventDiscoveryResult, NormalizedEvent, RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="openai-llm-mention",
        provider="rss",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/openai",
        title="OpenAI pre-IPO proxy exposure heats up",
        body="Velvet Capital is discussed as a venue for OpenAI pre-IPO exposure.",
        raw_json={},
        source_confidence=0.90,
        content_hash="openai-llm-mention",
    )
    event = NormalizedEvent(
        event_id="openai-llm-mention",
        raw_ids=(raw.raw_id,),
        event_name=raw.title,
        event_type="ipo_proxy",
        event_time=now,
        event_time_confidence=0.85,
        first_seen_time=now,
        source=raw.provider,
        source_urls=(raw.source_url,),
        external_asset="OpenAI",
        description=raw.body,
        confidence=0.90,
    )
    extraction = EventLLMRawEventExtraction(
        schema_version="event_llm_extraction_v1",
        provider="fixture",
        model="fixture",
        prompt_version="test",
        raw_id=raw.raw_id,
        confidence=0.90,
        external_catalysts=(),
        crypto_asset_mentions=(
            EventLLMCryptoAssetMention(
                name="OpenAI",
                symbol="OPENAI",
                coin_id="openai",
                contract_address=None,
                mention_type="project_or_token",
                confidence=0.92,
            ),
            EventLLMCryptoAssetMention(
                name="Velvet Capital",
                symbol="VELVET",
                coin_id="velvet",
                contract_address=None,
                mention_type="project_or_token",
                confidence=0.88,
            ),
        ),
    )
    hypotheses = event_impact_hypotheses.generate_impact_hypotheses(
        EventDiscoveryResult((raw,), (event,), (), (), ()),
        extraction_rows=(EventLLMExtractionReportRow(raw_event=raw, extraction=extraction),),
        now=now,
        taxonomy={},
    )
    hypothesis = next(item for item in hypotheses if item.impact_category == "ai_ipo_proxy")
    assert any(entity["name"] == "OpenAI" for entity in hypothesis.external_entities)
    assert "OPENAI" not in hypothesis.candidate_symbols
    assert "VELVET" in hypothesis.candidate_symbols
    assert hypothesis.crypto_candidate_assets[0]["symbol"] == "VELVET"
    assert hypothesis.rejected_candidate_assets[0]["rejection_reason"] == "external_entity_not_crypto_candidate"
    assert hypothesis.validation_stage == event_impact_hypotheses.ValidationStage.VALIDATION_SEARCH_PENDING.value


def test_event_impact_hypothesis_search_skip_reason_buckets_are_specific():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    empty_provider = event_catalyst_search.FixtureCatalystSearchProvider(rows_by_query={})
    no_hypotheses = event_catalyst_search.run_hypothesis_search(
        (),
        empty_provider,
        cfg=event_catalyst_search.EventImpactHypothesisSearchConfig(enabled=True),
        now=now,
    )
    assert no_hypotheses.skip_reasons["no_hypotheses"] == 1

    low_conf = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:low",
        event_cluster_id=None,
        event_type="ipo_proxy",
        external_asset="SpaceX",
        impact_category=event_impact_hypotheses.ImpactCategory.RWA_PREIPO_PROXY.value,
        candidate_sectors=("tokenized_stock_venues",),
        candidate_symbols=("VELVET",),
        confidence=0.10,
    )
    low = event_catalyst_search.run_hypothesis_search(
        (low_conf,),
        empty_provider,
        cfg=event_catalyst_search.EventImpactHypothesisSearchConfig(enabled=True, min_confidence=0.50),
        now=now,
    )
    assert low.skip_reasons["low_confidence"] == 1

    missing_assets = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:missing",
        event_cluster_id=None,
        event_type="ipo_proxy",
        external_asset="SpaceX",
        impact_category=event_impact_hypotheses.ImpactCategory.RWA_PREIPO_PROXY.value,
        candidate_sectors=("tokenized_stock_venues",),
        candidate_symbols=(),
        confidence=0.90,
    )
    missing = event_catalyst_search.run_hypothesis_search(
        (missing_assets,),
        empty_provider,
        cfg=event_catalyst_search.EventImpactHypothesisSearchConfig(enabled=True, min_confidence=0.50),
        now=now,
    )
    assert missing.query_count > 0
    assert any(query.query_type == "candidate_discovery" for query in missing.queries)

    stale_result = RawDiscoveredEvent(
        raw_id="velvet-no-catalyst",
        provider="fixture_search",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/velvet",
        title="VELVET opens unrelated product",
        body="Velvet Capital launches a generic crypto vault with no named catalyst reference.",
        raw_json={},
        source_confidence=0.90,
        content_hash="velvet-no-catalyst",
    )
    provider = event_catalyst_search.FixtureCatalystSearchProvider(
        rows_by_query={"VELVET SpaceX pre-IPO exposure": (stale_result,)}
    )
    good = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:spacex",
        event_cluster_id=None,
        event_type="ipo_proxy",
        external_asset="SpaceX",
        impact_category=event_impact_hypotheses.ImpactCategory.RWA_PREIPO_PROXY.value,
        candidate_sectors=("tokenized_stock_venues",),
        candidate_symbols=("VELVET",),
        confidence=0.90,
    )
    result = event_catalyst_search.run_hypothesis_search(
        (good,),
        provider,
        cfg=event_catalyst_search.EventImpactHypothesisSearchConfig(
            enabled=True,
            min_confidence=0.50,
            min_result_confidence=0.50,
            require_validated_identity=True,
        ),
        now=now,
    )
    assert result.rejected_result_count >= 1
    assert result.skip_reasons["result_catalyst_missing"] >= 1
    assert "result_catalyst_missing" in result.rejected_result_events[0].result_score_reasons
    sampled = event_impact_hypotheses.attach_hypothesis_search_samples((good,), result)[0]
    assert sampled.rejected_validation_samples
    assert sampled.rejected_validation_samples[0]["query_type"] == "candidate_validation"
    assert sampled.rejected_validation_samples[0]["rejection_reason"] == "result_catalyst_missing"
    assert sampled.rejected_validation_samples[0]["result_score"] == 45


def test_event_alpha_pipeline_operating_cycle_runs_extraction_before_discovery():
    from datetime import datetime, timezone
    from pathlib import Path
    import tempfile
    import crypto_rsi_scanner.event_alpha.radar.pipeline as event_alpha_pipeline
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.llm.extractor as event_llm_extractor
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
    from crypto_rsi_scanner.event_core.models import DiscoveredAsset, RawDiscoveredEvent
    from crypto_rsi_scanner.llm_providers.base import LLMProviderResult

    now = datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="pipeline-llm-stealth",
        provider="test",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/pipeline-llm-stealth",
        title="SpaceX exposure desk opens",
        body="Stealth proxy venue is live for SpaceX exposure before the event.",
        raw_json={
            "event": {
                "event_id": "pipeline-llm-stealth",
                "event_name": "SpaceX proxy exposure opens",
                "event_type": "ipo_proxy",
                "event_time": "2026-06-16T13:30:00Z",
                "event_time_confidence": 1.0,
                "external_asset": "SpaceX",
                "confidence": 0.90,
                "description": "A proxy venue opened for SpaceX exposure.",
            }
        },
        source_confidence=0.90,
        content_hash="pipeline-llm-stealth",
    )
    asset = DiscoveredAsset(
        coin_id="stealth-alpha",
        symbol="STEALTH",
        name="Stealth Alpha",
        aliases=("stealth alpha",),
    )

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
                    "name": "Stealth Alpha",
                    "symbol": "STEALTH",
                    "coin_id": "stealth-alpha",
                    "contract_address": None,
                    "mention_type": "project_or_token",
                    "confidence": 0.90,
                    "evidence_quotes": [{"text": "Stealth proxy venue", "source_field": "body", "supports": "asset mention"}],
                }],
                "false_positive_terms": [],
                "event_date_hints": [],
                "suggested_followup_queries": [],
                "warnings": [],
            })

    seen = {
        "transform_calls": 0,
        "shadow_transform_applied": None,
        "advisory_transform_applied": None,
        "loader_now": None,
    }

    def loader(observed, raw_event_transform):
        seen["loader_now"] = observed
        transformed = tuple(raw_event_transform((raw,))) if raw_event_transform else (raw,)
        applied = bool(transformed[0].raw_json and transformed[0].raw_json.get("llm_extraction"))
        if raw_event_transform:
            seen["transform_calls"] += 1
            if seen["transform_calls"] == 1:
                seen["shadow_transform_applied"] = applied
            else:
                seen["advisory_transform_applied"] = applied
        return event_discovery.run_discovery(transformed, [asset], now=observed)

    with tempfile.TemporaryDirectory() as tmp:
        shadow_pipe = event_alpha_pipeline.run_event_alpha_operating_cycle(
            load_discovery_result=loader,
            alert_cfg=event_alerts.EventAlertConfig(),
            now=now,
            with_llm=True,
            extraction_provider=Provider(),
            extraction_cfg=event_llm_extractor.EventLLMExtractorConfig(mode="shadow", provider="fixture"),
            watchlist_cfg=event_watchlist.EventWatchlistConfig(
                enabled=True,
                state_path=Path(tmp) / "watchlist.jsonl",
            ),
            router_cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True),
            refresh_watchlist=True,
            route=True,
        )
        advisory_pipe = event_alpha_pipeline.run_event_alpha_operating_cycle(
            load_discovery_result=loader,
            alert_cfg=event_alerts.EventAlertConfig(),
            now=now,
            with_llm=True,
            extraction_provider=Provider(),
            extraction_cfg=event_llm_extractor.EventLLMExtractorConfig(mode="advisory", provider="fixture"),
            watchlist_cfg=event_watchlist.EventWatchlistConfig(
                enabled=True,
                state_path=Path(tmp) / "watchlist-advisory.jsonl",
            ),
            router_cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True),
            refresh_watchlist=True,
            route=True,
        )
    assert seen["loader_now"] == now
    assert seen["shadow_transform_applied"] is False
    assert seen["advisory_transform_applied"] is True
    assert shadow_pipe.extractions == 1
    assert shadow_pipe.extraction_hint_events == 0
    assert shadow_pipe.candidates == 0
    assert advisory_pipe.extractions == 1
    assert advisory_pipe.extraction_hint_events == 1
    assert advisory_pipe.candidates == 1
    assert advisory_pipe.alerts[0].symbol == "STEALTH"
    assert advisory_pipe.watchlist_entries >= 1
    assert advisory_pipe.routed >= 1


def test_event_alpha_cycle_scanner_runs_research_pipeline_with_fixture_anomalies():
    import contextlib
    import io
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import config, scanner

    original = {
        "EVENT_DISCOVERY_EVENTS_PATH": config.EVENT_DISCOVERY_EVENTS_PATH,
        "EVENT_DISCOVERY_ALIASES_PATH": config.EVENT_DISCOVERY_ALIASES_PATH,
        "EVENT_DISCOVERY_UNIVERSE_PATH": config.EVENT_DISCOVERY_UNIVERSE_PATH,
        "EVENT_DISCOVERY_UNIVERSE_LIVE": config.EVENT_DISCOVERY_UNIVERSE_LIVE,
        "EVENT_DISCOVERY_UNIVERSE_FETCH_LIMIT": config.EVENT_DISCOVERY_UNIVERSE_FETCH_LIMIT,
        "EVENT_MARKET_ENRICHMENT_ENABLED": config.EVENT_MARKET_ENRICHMENT_ENABLED,
        "EVENT_ANOMALY_SCANNER_ENABLED": config.EVENT_ANOMALY_SCANNER_ENABLED,
        "EVENT_ANOMALY_MIN_RETURN_24H": config.EVENT_ANOMALY_MIN_RETURN_24H,
        "EVENT_ANOMALY_MIN_VOLUME_MCAP": config.EVENT_ANOMALY_MIN_VOLUME_MCAP,
        "EVENT_ANOMALY_MIN_VOLUME_ZSCORE": config.EVENT_ANOMALY_MIN_VOLUME_ZSCORE,
        "EVENT_ANOMALY_MAX_ASSETS": config.EVENT_ANOMALY_MAX_ASSETS,
        "EVENT_WATCHLIST_ENABLED": config.EVENT_WATCHLIST_ENABLED,
        "EVENT_WATCHLIST_STATE_PATH": config.EVENT_WATCHLIST_STATE_PATH,
        "EVENT_ALPHA_ROUTER_ENABLED": config.EVENT_ALPHA_ROUTER_ENABLED,
        "EVENT_ALPHA_ALERT_STORE_PATH": config.EVENT_ALPHA_ALERT_STORE_PATH,
        "EVENT_ALPHA_RUN_LEDGER_PATH": config.EVENT_ALPHA_RUN_LEDGER_PATH,
        "EVENT_ALPHA_RUN_MODE": config.EVENT_ALPHA_RUN_MODE,
        "EVENT_ALPHA_ARTIFACT_NAMESPACE": config.EVENT_ALPHA_ARTIFACT_NAMESPACE,
        "EVENT_ALPHA_ARTIFACT_BASE_DIR": config.EVENT_ALPHA_ARTIFACT_BASE_DIR,
        "EVENT_ALERTS_ENABLED": config.EVENT_ALERTS_ENABLED,
    }
    with tempfile.TemporaryDirectory() as tmp:
        root_artifact_path = Path("event_fade_cache/event_alpha_runs.jsonl")
        root_existed = root_artifact_path.exists()
        config.EVENT_DISCOVERY_EVENTS_PATH = None
        config.EVENT_DISCOVERY_ALIASES_PATH = None
        config.EVENT_DISCOVERY_UNIVERSE_PATH = Path("fixtures/coingecko_smoke/top_markets.json")
        config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE = False
        config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE = False
        config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = None
        config.EVENT_DISCOVERY_CRYPTOPANIC_LIVE = False
        config.EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN = ""
        config.EVENT_DISCOVERY_GDELT_PATH = None
        config.EVENT_DISCOVERY_GDELT_LIVE = False
        config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = None
        config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE = False
        config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS = ()
        config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = None
        config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE = False
        config.EVENT_DISCOVERY_COINALYZE_LIVE = False
        config.EVENT_DISCOVERY_UNIVERSE_LIVE = False
        config.EVENT_DISCOVERY_UNIVERSE_FETCH_LIMIT = 0
        config.EVENT_SOURCE_ENRICHMENT_ENABLED = False
        config.EVENT_SOURCE_ENRICHMENT_MAX_ROWS_PER_RUN = 0
        config.EVENT_MARKET_ENRICHMENT_ENABLED = True
        config.EVENT_ANOMALY_SCANNER_ENABLED = True
        config.EVENT_ANOMALY_MIN_RETURN_24H = 0.03
        config.EVENT_ANOMALY_MIN_VOLUME_MCAP = 0.05
        config.EVENT_ANOMALY_MIN_VOLUME_ZSCORE = 3.0
        config.EVENT_ANOMALY_MAX_ASSETS = 10
        config.EVENT_WATCHLIST_ENABLED = True
        config.EVENT_WATCHLIST_STATE_PATH = Path(tmp) / "watchlist.jsonl"
        config.EVENT_ALPHA_ROUTER_ENABLED = True
        config.EVENT_ALPHA_ALERT_STORE_PATH = Path(tmp) / "event_alpha_alerts.jsonl"
        config.EVENT_ALPHA_RUN_LEDGER_PATH = Path(tmp) / "event_alpha_runs.jsonl"
        config.EVENT_ALPHA_RUN_MODE = "test"
        config.EVENT_ALPHA_ARTIFACT_NAMESPACE = "test"
        config.EVENT_ALPHA_ARTIFACT_BASE_DIR = Path(tmp)
        config.EVENT_ALERTS_ENABLED = False
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_cycle(event_now="2026-06-15T16:00:00Z")
            text = out.getvalue()
            assert "EVENT ALPHA PIPELINE REPORT" in text
            assert "raw_events=" in text
            assert "candidates=1" in text
            assert "impact_hypotheses=" in text
            assert "watchlist_entries=" in text
            assert "routed=" in text
            assert "routes: STORE_ONLY" in text
            assert "market_anomaly_unknown" in text
            assert "run ledger updated" in text.lower()
            assert config.EVENT_WATCHLIST_STATE_PATH.exists()
            assert config.EVENT_ALPHA_RUN_LEDGER_PATH.exists()
            run_rows = [
                __import__("json").loads(line)
                for line in config.EVENT_ALPHA_RUN_LEDGER_PATH.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            assert run_rows[-1]["run_mode"] == "test"
            assert run_rows[-1]["artifact_namespace"] == "test"
            assert root_artifact_path.exists() is root_existed
        finally:
            for name, value in original.items():
                setattr(config, name, value)


def test_event_alpha_cycle_with_llm_feeds_extraction_hints_upstream():
    import contextlib
    import io
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import config, scanner
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
                    "name": "Stealth Alpha",
                    "symbol": "STEALTH",
                    "coin_id": "stealth-alpha",
                    "contract_address": None,
                    "mention_type": "project_or_token",
                    "confidence": 0.90,
                    "evidence_quotes": [{"text": "Stealth proxy venue", "source_field": "body", "supports": "asset mention"}],
                }],
                "false_positive_terms": [],
                "event_date_hints": [],
                "suggested_followup_queries": [],
                "warnings": [],
            })

    attrs = (
        "EVENT_DISCOVERY_EVENTS_PATH",
        "EVENT_DISCOVERY_ALIASES_PATH",
        "EVENT_DISCOVERY_UNIVERSE_PATH",
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE",
        "EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE",
        "EVENT_DISCOVERY_CRYPTOPANIC_PATH",
        "EVENT_DISCOVERY_CRYPTOPANIC_LIVE",
        "EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN",
        "EVENT_DISCOVERY_GDELT_PATH",
        "EVENT_DISCOVERY_GDELT_LIVE",
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH",
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE",
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS",
        "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH",
        "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE",
        "EVENT_DISCOVERY_COINALYZE_LIVE",
        "EVENT_DISCOVERY_UNIVERSE_LIVE",
        "EVENT_SOURCE_ENRICHMENT_ENABLED",
        "EVENT_SOURCE_ENRICHMENT_MAX_ROWS_PER_RUN",
        "EVENT_MARKET_ENRICHMENT_ENABLED",
        "EVENT_ANOMALY_SCANNER_ENABLED",
        "EVENT_WATCHLIST_ENABLED",
        "EVENT_WATCHLIST_STATE_PATH",
        "EVENT_ALPHA_ROUTER_ENABLED",
        "EVENT_ALPHA_ALERT_STORE_PATH",
        "EVENT_ALPHA_RUN_LEDGER_PATH",
        "EVENT_ALPHA_RUN_MODE",
        "EVENT_ALPHA_ARTIFACT_NAMESPACE",
        "EVENT_ALPHA_ARTIFACT_BASE_DIR",
        "EVENT_ALERTS_ENABLED",
        "EVENT_LLM_BUDGET_LEDGER_PATH",
        "EVENT_LLM_EXTRACTOR_MODE",
        "EVENT_LLM_EXTRACTOR_PROVIDER",
        "EVENT_LLM_MODE",
        "EVENT_LLM_PROVIDER",
        "EVENT_LLM_CATALYST_FRAMES_ENABLED",
        "EVENT_LLM_CATALYST_FRAMES_PROVIDER",
    )
    original = {name: getattr(config, name) for name in attrs}
    original_extraction_provider = scanner._event_llm_extraction_provider
    original_relationship_provider = scanner._event_llm_provider
    raw_rows = [{
        "raw_id": "llm-cycle-stealth",
        "provider": "manual_json",
        "fetched_at": "2026-06-16T12:00:00Z",
        "published_at": "2026-06-16T11:00:00Z",
        "source_url": "https://example.test/stealth-alpha-cycle",
        "title": "SpaceX exposure desk opens before listing event",
        "body": "Stealth proxy venue is live for SpaceX exposure before the event.",
        "source_confidence": 0.90,
        "event": {
            "event_id": "stealth-cycle-spacex-event",
            "event_name": "SpaceX proxy exposure opens",
            "event_type": "ipo_proxy",
            "event_time": "2026-06-16T13:30:00Z",
            "event_time_confidence": 1.0,
            "external_asset": "SpaceX",
            "confidence": 0.90,
            "description": "A proxy venue opened for SpaceX exposure.",
        },
    }]
    alias_rows = {"assets": [{
        "coin_id": "stealth-alpha",
        "symbol": "STEALTH",
        "name": "Stealth Alpha",
        "aliases": ["stealth alpha"],
    }]}
    with tempfile.TemporaryDirectory() as tmp:
        event_path = Path(tmp) / "events.json"
        alias_path = Path(tmp) / "aliases.json"
        event_path.write_text(json.dumps(raw_rows), encoding="utf-8")
        alias_path.write_text(json.dumps(alias_rows), encoding="utf-8")
        config.EVENT_DISCOVERY_EVENTS_PATH = event_path
        config.EVENT_DISCOVERY_ALIASES_PATH = alias_path
        config.EVENT_DISCOVERY_UNIVERSE_PATH = None
        config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE = False
        config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE = False
        config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = None
        config.EVENT_DISCOVERY_CRYPTOPANIC_LIVE = False
        config.EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN = ""
        config.EVENT_DISCOVERY_GDELT_PATH = None
        config.EVENT_DISCOVERY_GDELT_LIVE = False
        config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = None
        config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE = False
        config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS = ()
        config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = None
        config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE = False
        config.EVENT_DISCOVERY_COINALYZE_LIVE = False
        config.EVENT_DISCOVERY_UNIVERSE_LIVE = False
        config.EVENT_SOURCE_ENRICHMENT_ENABLED = False
        config.EVENT_SOURCE_ENRICHMENT_MAX_ROWS_PER_RUN = 0
        config.EVENT_MARKET_ENRICHMENT_ENABLED = False
        config.EVENT_ANOMALY_SCANNER_ENABLED = False
        config.EVENT_WATCHLIST_ENABLED = True
        config.EVENT_WATCHLIST_STATE_PATH = Path(tmp) / "watchlist.jsonl"
        config.EVENT_ALPHA_ROUTER_ENABLED = True
        config.EVENT_ALPHA_ALERT_STORE_PATH = Path(tmp) / "event_alpha_alerts.jsonl"
        config.EVENT_ALPHA_RUN_LEDGER_PATH = Path(tmp) / "event_alpha_runs.jsonl"
        config.EVENT_ALPHA_RUN_MODE = "test"
        config.EVENT_ALPHA_ARTIFACT_NAMESPACE = "test"
        config.EVENT_ALPHA_ARTIFACT_BASE_DIR = Path(tmp)
        config.EVENT_ALERTS_ENABLED = False
        config.EVENT_LLM_BUDGET_LEDGER_PATH = Path(tmp) / "event_llm_budget.json"
        config.EVENT_LLM_EXTRACTOR_MODE = "advisory"
        config.EVENT_LLM_EXTRACTOR_PROVIDER = "fixture"
        config.EVENT_LLM_MODE = "shadow"
        config.EVENT_LLM_PROVIDER = "fixture"
        config.EVENT_LLM_CATALYST_FRAMES_ENABLED = False
        config.EVENT_LLM_CATALYST_FRAMES_PROVIDER = "fixture"
        scanner._event_llm_extraction_provider = lambda extractor_cfg: Provider()
        scanner._event_llm_provider = lambda llm_cfg: None
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_cycle(with_llm=True, event_now="2026-06-16T12:00:00Z")
            text = out.getvalue()
            assert "EVENT ALPHA PIPELINE REPORT" in text
            assert "extractions=1/1" in text
            assert "extraction_hints_applied=1" in text
            assert "candidates=1" in text
            assert "STEALTH/stealth-alpha" in text
            assert config.EVENT_WATCHLIST_STATE_PATH.exists()
            assert config.EVENT_ALPHA_RUN_LEDGER_PATH.exists()
        finally:
            scanner._event_llm_extraction_provider = original_extraction_provider
            scanner._event_llm_provider = original_relationship_provider
            for name, value in original.items():
                setattr(config, name, value)
