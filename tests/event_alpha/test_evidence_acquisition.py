"""Evidence-acquisition execution, reconciliation, provider, and operator regressions."""

from __future__ import annotations

from datetime import datetime, timezone
from tempfile import TemporaryDirectory

# --- Migrated from tests/test_indicators.py; keep standalone-compatible. ---
from tests.event_alpha import _api_helpers as _event_alpha_api_helpers

globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


def test_evidence_acquisition_final_upgrade_status_tracks_final_verdict_not_evidence_only():
    from types import SimpleNamespace
    import crypto_rsi_scanner.event_alpha.outcomes.quality_fields as event_alpha_quality_fields
    import crypto_rsi_scanner.event_alpha.radar.evidence_acquisition as event_evidence_acquisition

    result = event_evidence_acquisition.EvidenceAcquisitionResult(
        acquisition_id="acq:test",
        opportunity_id="core:velvet",
        core_opportunity_id="core:velvet",
        hypothesis_id="hyp:velvet",
        incident_id="incident:spacex",
        source_pack="proxy_preipo_rwa_pack",
        status="accepted_evidence_found",
        symbol="VELVET",
        coin_id="velvet",
        accepted_evidence=({"evidence_quality_score": 92, "reason_codes": ("cryptopanic_currency_tag_match",)},),
        evidence_quality_before=70,
        evidence_quality_after=92,
        impact_path_validation_before="impact_path_validated",
        impact_path_validation_after="impact_path_validated",
        opportunity_score_before=88.5,
        opportunity_level_before="high_priority",
    )
    before = SimpleNamespace(
        opportunity_score_final=88.5,
        opportunity_level="high_priority",
        score_components={
            "opportunity_score_final": 88.5,
            "opportunity_level": "high_priority",
            "market_refresh_success": True,
            "market_confirmation_score": 100,
            "market_confirmation_level": "strong",
            "market_context_freshness_status": "fresh",
        },
    )
    after = SimpleNamespace(
        opportunity_score_final=72.5,
        opportunity_level="validated_digest",
        evidence_quality_score=92,
        impact_path_type="venue_value_capture",
        score_components={
            "opportunity_score_final": 72.5,
            "opportunity_level": "validated_digest",
            "evidence_quality_score": 92,
            "market_confirmation_score": 35,
            "market_confirmation_level": "weak",
        },
    )
    finalized = event_evidence_acquisition._finalize_result(result, before=before, after=after)

    assert finalized.acquisition_evidence_status == "accepted_evidence_found"
    assert finalized.evidence_quality_upgraded is True
    assert finalized.final_upgrade_status == "unchanged"
    assert finalized.acquisition_upgrade_status == "unchanged"
    assert finalized.opportunity_score_delta == 0
    assert finalized.post_refresh_opportunity_level == "validated_digest"
    assert finalized.post_refresh_market_confirmation_score == 100
    assert finalized.post_refresh_market_confirmation_level == "strong"
    assert finalized.market_data_freshness == "fresh"
    assert finalized.market_reaction_confirmation == "strong"
    assert finalized.final_opportunity_level == "high_priority"
    assert finalized.final_verdict_source == "market_refresh"

    quality = event_alpha_quality_fields.ensure_quality_fields({
        "opportunity_score_final": 72.5,
        "opportunity_level": "validated_digest",
        "final_opportunity_score": 88.5,
        "final_opportunity_level": "high_priority",
    })
    assert quality["opportunity_score_final"] == 88.5
    assert quality["opportunity_level"] == "high_priority"


def test_evidence_acquisition_core_opportunity_dedupes_supporting_rows():
    import crypto_rsi_scanner.event_alpha.radar.evidence_acquisition as event_evidence_acquisition

    base = {
        "event_cluster_id": "cluster:spacex",
        "incident_id": "incident:spacex",
        "symbol": "VELVET",
        "coin_id": "velvet",
        "validated_symbol": "VELVET",
        "validated_coin_id": "velvet",
        "external_asset": "SpaceX",
        "playbook_type": "proxy_attention",
        "impact_category": "tokenized_stock_venue",
        "impact_path_type": "venue_value_capture",
        "candidate_role": "proxy_venue",
        "source_class": "crypto_news",
        "evidence_specificity": "asset_and_catalyst",
        "evidence_quality_score": 80,
        "market_confirmation_score": 60,
        "opportunity_score_final": 74,
        "opportunity_level": "validated_digest",
    }
    rows = (
        {**base, "hypothesis_id": "hyp:velvet:primary"},
        {**base, "hypothesis_id": "hyp:velvet:supporting", "impact_category": "rwa_preipo_proxy"},
    )
    result = event_evidence_acquisition.run_evidence_acquisition(
        rows,
        provider=None,
        providers_by_hint={},
        cfg=event_evidence_acquisition.EvidenceAcquisitionConfig(enabled=True, max_candidates=5, max_queries=1),
    )
    assert result.attempted == 1
    assert result.results[0].core_opportunity_id
    assert result.results[0].core_opportunity_id != "UNKNOWN"


def test_evidence_acquisition_empty_and_provider_failures_return_complete_result():
    import crypto_rsi_scanner.event_alpha.radar.evidence_acquisition as event_evidence_acquisition

    disabled = event_evidence_acquisition.run_evidence_acquisition(
        (),
        cfg=event_evidence_acquisition.EvidenceAcquisitionConfig(enabled=False),
    )
    assert disabled.status == "disabled"
    assert disabled.results == ()
    assert disabled.attempted == 0

    no_candidates = event_evidence_acquisition.run_evidence_acquisition(
        (),
        cfg=event_evidence_acquisition.EvidenceAcquisitionConfig(enabled=True),
    )
    assert no_candidates.status == "no_candidates"
    assert no_candidates.results == ()
    assert no_candidates.attempted == 0

    class FailingProvider:
        name = "fixture_dns_failure"

        def search(self, queries, *, max_results_per_query, now=None):
            raise OSError("DNS temporary failure in name resolution")

    row = {
        "hypothesis_id": "hyp:tao-provider-fail",
        "core_opportunity_id": "agg:tao-provider-fail",
        "symbol": "TAO",
        "coin_id": "bittensor",
        "validated_symbol": "TAO",
        "validated_coin_id": "bittensor",
        "external_asset": "Bittensor",
        "playbook_type": "strategic_investment",
        "impact_category": "strategic_investment_or_valuation",
        "impact_path_type": "strategic_investment_or_valuation",
        "candidate_role": "direct_subject",
        "opportunity_level": "validated_digest",
        "opportunity_score_final": 72,
        "source_pack": "strategic_investment_pack",
    }
    failed = event_evidence_acquisition.run_evidence_acquisition(
        (row,),
        provider=FailingProvider(),
        providers_by_hint={},
        cfg=event_evidence_acquisition.EvidenceAcquisitionConfig(
            enabled=True,
            max_candidates=1,
            max_queries=1,
        ),
    )
    assert failed.status == "failed_soft"
    assert failed.attempted == 1
    assert failed.results[0].status == "failed_soft"
    assert failed.results[0].query_results[0].status == "failed_soft"
    assert any("OSError" in warning for warning in failed.results[0].warnings)


def test_event_evidence_acquisition_executes_fixture_searches():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
    import crypto_rsi_scanner.event_alpha.radar.evidence_acquisition as event_evidence_acquisition
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent

    rune = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:rune-acquisition",
        event_cluster_id="cluster:rune",
        event_type="security_incident",
        external_asset="THORChain",
        impact_category="security_or_regulatory_shock",
        candidate_sectors=("defi_tokens",),
        candidate_symbols=("RUNE",),
        candidate_coin_ids=("thorchain",),
        impact_path_type="exploit_security_event",
        playbook_hint="security_or_regulatory_shock",
        confidence=0.78,
        hypothesis_score=64.0,
        opportunity_score_final=64.0,
        opportunity_level="exploratory",
        missing_requirements=("source evidence", "impact_path_validation"),
        validation_stage="catalyst_link_validated",
        score_components={
            "symbol": "RUNE",
            "coin_id": "thorchain",
            "validated_symbol": "RUNE",
            "validated_coin_id": "thorchain",
            "playbook_type": "security_or_regulatory_shock",
            "impact_path_type": "exploit_security_event",
            "opportunity_score_final": 64.0,
            "opportunity_level": "exploratory",
            "missing_requirements": ("source evidence", "impact_path_validation"),
        },
    )
    fetched = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
    accepted_raw = RawDiscoveredEvent(
        raw_id="raw:rune-accepted",
        provider="cryptopanic",
        fetched_at=fetched,
        published_at=fetched,
        source_url="https://cryptopanic.com/news/rune-exploit",
        title="RUNE exploit update: THORChain resumes trading after incident",
        body="RUNE and THORChain markets reacted after an exploit; the project resumes trading and publishes the security update.",
        raw_json={"currency_tags": ("RUNE",), "currencies": [{"code": "RUNE", "slug": "thorchain"}], "source_origin": "CryptoPanic"},
        source_confidence=0.88,
        content_hash="rune-accepted",
    )
    accepted_independent_raw = RawDiscoveredEvent(
        raw_id="raw:rune-independent",
        provider="cryptopanic",
        fetched_at=fetched,
        published_at=fetched,
        source_url="https://news.cryptopanic.com/rune-security-recovery",
        title="THORChain publishes independent RUNE security recovery details",
        body=(
            "THORChain validators completed the exploit recovery procedure and "
            "documented the separate security controls used before RUNE markets "
            "resumed normal settlement operations."
        ),
        raw_json={
            "currency_tags": ("RUNE",),
            "currencies": [{"code": "RUNE", "slug": "thorchain"}],
            "source_origin": "CryptoPanic",
        },
        source_confidence=0.92,
        content_hash="rune-independent",
    )
    rejected_raw = RawDiscoveredEvent(
        raw_id="raw:rune-rejected",
        provider="polymarket",
        fetched_at=fetched,
        published_at=fetched,
        source_url="https://polymarket.com/event/thorchain-hack",
        title="Will THORChain exploit be resolved this week?",
        body="Prediction market context tracks the exploit resolution, but does not mention RUNE token identity or market impact.",
        raw_json={"source_origin": "Polymarket"},
        source_confidence=0.70,
        content_hash="rune-rejected",
    )
    provider = event_catalyst_search.FixtureCatalystSearchProvider(rows_by_query={
        "RUNE hack incident security market reaction": (
            accepted_raw,
            accepted_independent_raw,
        ),
        "RUNE exploit official update": (rejected_raw,),
    })
    with TemporaryDirectory() as tmp:
        artifact_path = Path(tmp) / "event_evidence_acquisition.jsonl"
        result = event_evidence_acquisition.run_evidence_acquisition(
            (rune,),
            provider=provider,
            providers_by_hint={"cryptopanic": provider, "project_blog_rss": provider},
            cfg=event_evidence_acquisition.EvidenceAcquisitionConfig(
                enabled=True,
                max_candidates=3,
                max_queries=4,
                max_results_per_query=2,
                fixture_only=True,
                artifact_path=artifact_path,
            ),
            now=fetched,
            run_context={"run_id": "run:test", "profile": "quality_validation", "run_mode": "test", "artifact_namespace": "quality_validation"},
        )
        assert result.attempted == 1
        assert result.accepted == 1
        assert result.rows_written == 1
        assert result.results[0].status == "accepted_evidence_found"
        assert result.results[0].source_update_count == 2
        assert result.results[0].source_independence_status == "assessed"
        assert result.results[0].independent_source_count == 2
        assert result.results[0].independent_corroboration_count == 1
        assert any("cryptopanic_currency_tag_match" in item["reason_codes"] for item in result.results[0].accepted_evidence)
        accepted_sample = result.results[0].accepted_evidence[0]
        assert accepted_sample["source_class"] == "cryptopanic_tagged"
        assert "RUNE" in accepted_sample["currency_tags"]
        assert "THORCHAIN" in accepted_sample["currency_tags"]
        assert accepted_sample["cryptopanic_currency_tag_match"] is True
        assert accepted_sample["source_pack_impact_path_validating_source"] is True
        assert accepted_sample["source_pack_validated_digest_sufficient"] is True
        assert "impact_path_validation" in accepted_sample["source_can_prove"]
        assert result.path == artifact_path
        rows = event_evidence_acquisition.load_acquisition_results(artifact_path)
        assert rows[0]["symbol"] == "RUNE"
        assert rows[0]["coin_id"] == "thorchain"
        assert rows[0]["accepted_evidence"]
        assert rows[0]["evidence_acquisition_attempted"] is True
        assert rows[0]["evidence_acquisition_plan"]["source_pack"] == "security_shock_pack"
        assert rows[0]["evidence_acquisition_results"]["status"] == "accepted_evidence_found"
        assert "accepted_evidence_found" in rows[0]["query_execution_statuses"]
        assert "impact_path_validation" in rows[0]["source_can_prove"]
        assert "token_identity_validation" in rows[0]["source_can_prove"]
        assert "security_or_regulatory_shock" in rows[0]["source_useful_playbooks"]
        assert "official_confirmation" in rows[0]["source_cannot_prove"]
        import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_store

        acquisition = event_core_store._build_core_evidence_acquisition_view(  # noqa: SLF001
            rows[0]["core_opportunity_id"],
            rows,
        )
        assert acquisition.source_independence_status == "assessed"
        assert acquisition.independent_source_count == 2
        assert acquisition.independent_corroboration_count == 1


def test_event_evidence_acquisition_accepts_structured_tokenomist_unlocks():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
    import crypto_rsi_scanner.event_alpha.radar.evidence_acquisition as event_evidence_acquisition
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses
    import crypto_rsi_scanner.event_alpha.artifacts.opportunity_audit as event_opportunity_audit
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards
    from crypto_rsi_scanner.event_providers.tokenomist import TokenomistProvider

    _coinmarketcal_path, tokenomist_path = _structured_calendar_fixture_paths()
    now = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
    unlock = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:testunlock-acquisition",
        event_cluster_id="cluster:testunlock",
        event_type="token_unlock",
        external_asset="Test Unlock",
        impact_category="unlock_supply_pressure",
        candidate_sectors=("direct_token_events",),
        candidate_symbols=("TESTUNLOCK",),
        candidate_coin_ids=("testunlock",),
        impact_path_type="unlock_supply_event",
        playbook_hint="unlock_supply_pressure",
        confidence=0.82,
        hypothesis_score=68.0,
        opportunity_score_final=68.0,
        opportunity_level="validated_digest",
        missing_requirements=("market_confirmation",),
        validation_stage="impact_path_validated",
        score_components={
            "symbol": "TESTUNLOCK",
            "coin_id": "testunlock",
            "validated_symbol": "TESTUNLOCK",
            "validated_coin_id": "testunlock",
            "playbook_type": "unlock_supply_pressure",
            "impact_path_type": "unlock_supply_event",
            "opportunity_score_final": 68.0,
            "opportunity_level": "validated_digest",
            "market_confirmation_score": 72,
        },
    )
    provider = event_catalyst_search.EventProviderCatalystSearchProvider(
        lambda query: TokenomistProvider(tokenomist_path),
        name="tokenomist",
        filter_by_query=True,
        max_fetches_per_search=1,
    )
    with TemporaryDirectory() as tmp:
        artifact_path = Path(tmp) / "event_evidence_acquisition.jsonl"
        result = event_evidence_acquisition.run_evidence_acquisition(
            (unlock,),
            provider=provider,
            providers_by_hint={"tokenomist": provider},
            cfg=event_evidence_acquisition.EvidenceAcquisitionConfig(
                enabled=True,
                max_candidates=1,
                max_queries=2,
                max_results_per_query=2,
                fixture_only=False,
                artifact_path=artifact_path,
            ),
            now=now,
            run_context={
                "run_id": "run:testunlock",
                "profile": "structured_source_pack",
                "run_mode": "test",
                "artifact_namespace": "structured_source_pack",
            },
        )
    assert result.attempted == 1
    assert result.accepted == 1
    accepted = result.results[0].accepted_evidence[0]
    assert accepted["source_class"] == "structured_unlock"
    assert accepted["unlock_pct_circulating"] == 0.12
    assert accepted["unlock_materiality"] == "large"
    assert "structured_unlock_source" in accepted["reason_codes"]
    assert "material_unlock" in accepted["reason_codes"]
    assert accepted["source_pack_validated_digest_sufficient"] is True
    assert accepted["source_pack_watchlist_requirements_met"] is True
    card_sample = event_research_cards._accepted_evidence_sample_text(accepted)
    audit_sample = event_opportunity_audit._accepted_evidence_sample_text(accepted)
    assert "unlock_pct=0.12" in card_sample
    assert "materiality=large" in audit_sample


def test_event_evidence_acquisition_accepts_official_exchange_announcements_only_on_identity_match():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
    import crypto_rsi_scanner.event_alpha.radar.evidence_acquisition as event_evidence_acquisition
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses
    from crypto_rsi_scanner.event_providers.binance_announcements import BinanceAnnouncementProvider
    from crypto_rsi_scanner.event_providers.bybit_announcements import BybitAnnouncementProvider

    now = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
    start = datetime(2026, 6, 12, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    binance_path, bybit_path = _exchange_announcement_fixture_paths()
    listing_raw = BinanceAnnouncementProvider(binance_path, required=True).fetch_events(start, end)[0]
    perp_raw = BybitAnnouncementProvider(bybit_path, required=True).fetch_events(start, end)[0]

    listing = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:testlist-listing",
        event_cluster_id="cluster:testlist",
        event_type="exchange_listing",
        external_asset="Binance",
        impact_category="listing_liquidity_event",
        candidate_sectors=("direct_token_events",),
        candidate_symbols=("TESTLIST",),
        candidate_coin_ids=("testlist",),
        impact_path_type="listing_liquidity_event",
        playbook_hint="listing_volatility",
        confidence=0.82,
        hypothesis_score=66.0,
        opportunity_score_final=66.0,
        opportunity_level="validated_digest",
        validation_stage="impact_path_validated",
        score_components={
            "symbol": "TESTLIST",
            "coin_id": "testlist",
            "validated_symbol": "TESTLIST",
            "validated_coin_id": "testlist",
            "playbook_type": "listing_volatility",
            "impact_path_type": "listing_liquidity_event",
            "opportunity_score_final": 66.0,
            "opportunity_level": "validated_digest",
        },
    )
    perp = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:testperp-listing",
        event_cluster_id="cluster:testperp",
        event_type="perp_listing",
        external_asset="Bybit",
        impact_category="perp_listing",
        candidate_sectors=("direct_token_events",),
        candidate_symbols=("TESTPERP",),
        candidate_coin_ids=("testperp",),
        impact_path_type="perp_listing",
        playbook_hint="perp_listing_squeeze",
        confidence=0.82,
        hypothesis_score=67.0,
        opportunity_score_final=67.0,
        opportunity_level="validated_digest",
        validation_stage="impact_path_validated",
        score_components={
            "symbol": "TESTPERP",
            "coin_id": "testperp",
            "validated_symbol": "TESTPERP",
            "validated_coin_id": "testperp",
            "playbook_type": "perp_listing_squeeze",
            "impact_path_type": "perp_listing",
            "opportunity_score_final": 67.0,
            "opportunity_level": "validated_digest",
        },
    )
    mismatch = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:other-listing",
        event_cluster_id="cluster:other",
        event_type="exchange_listing",
        external_asset="Binance",
        impact_category="listing_liquidity_event",
        candidate_sectors=("direct_token_events",),
        candidate_symbols=("OTHER",),
        candidate_coin_ids=("other"),
        impact_path_type="listing_liquidity_event",
        playbook_hint="listing_volatility",
        confidence=0.82,
        hypothesis_score=66.0,
        opportunity_score_final=66.0,
        opportunity_level="validated_digest",
        validation_stage="impact_path_validated",
        score_components={
            "symbol": "OTHER",
            "coin_id": "other",
            "validated_symbol": "OTHER",
            "validated_coin_id": "other",
            "playbook_type": "listing_volatility",
            "impact_path_type": "listing_liquidity_event",
            "opportunity_score_final": 66.0,
            "opportunity_level": "validated_digest",
        },
    )
    substring_mismatch = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:test-substring-listing",
        event_cluster_id="cluster:test-substring",
        event_type="exchange_listing",
        external_asset="Binance",
        impact_category="listing_liquidity_event",
        candidate_sectors=("direct_token_events",),
        candidate_symbols=("TEST",),
        candidate_coin_ids=("test"),
        impact_path_type="listing_liquidity_event",
        playbook_hint="listing_volatility",
        confidence=0.82,
        hypothesis_score=66.0,
        opportunity_score_final=66.0,
        opportunity_level="validated_digest",
        validation_stage="impact_path_validated",
        score_components={
            "symbol": "TEST",
            "coin_id": "test",
            "validated_symbol": "TEST",
            "validated_coin_id": "test",
            "playbook_type": "listing_volatility",
            "impact_path_type": "listing_liquidity_event",
            "opportunity_score_final": 66.0,
            "opportunity_level": "validated_digest",
        },
    )

    provider = event_catalyst_search.FixtureCatalystSearchProvider(rows_by_query={
        "TESTLIST listing announcement": (listing_raw,),
        "TESTPERP perpetual futures listing announcement": (perp_raw,),
        "OTHER listing announcement": (listing_raw,),
        "TEST listing announcement": (listing_raw,),
    })
    result = event_evidence_acquisition.run_evidence_acquisition(
        (listing, perp, mismatch, substring_mismatch),
        provider=provider,
        providers_by_hint={"official_exchange": provider},
        cfg=event_evidence_acquisition.EvidenceAcquisitionConfig(
            enabled=True,
            max_candidates=4,
            max_queries=8,
            max_results_per_query=2,
            fixture_only=True,
        ),
        now=now,
    )

    by_hypothesis = {item.hypothesis_id: item for item in result.results}
    listing_result = by_hypothesis["hyp:testlist-listing"]
    perp_result = by_hypothesis["hyp:testperp-listing"]
    mismatch_result = by_hypothesis["hyp:other-listing"]
    substring_mismatch_result = by_hypothesis["hyp:test-substring-listing"]
    assert listing_result.status == "accepted_evidence_found"
    assert perp_result.status == "accepted_evidence_found"
    listing_evidence = listing_result.accepted_evidence[0]
    perp_evidence = perp_result.accepted_evidence[0]
    assert listing_evidence["source_class"] == "official_exchange"
    assert listing_evidence["exchange"] == "binance"
    assert listing_evidence["announcement_kind"] == "exchange_listing"
    assert listing_evidence["announcement_pairs"] == ("TESTLIST/USDT",)
    assert "official_exchange_listing" in listing_evidence["reason_codes"]
    assert listing_evidence["source_pack_validated_digest_sufficient"] is True
    assert listing_evidence["source_pack_watchlist_requirements_met"] is False
    assert perp_evidence["exchange"] == "bybit"
    assert perp_evidence["announcement_kind"] == "perp_listing"
    assert perp_evidence["announcement_contracts"] == ("TESTPERPUSDT",)
    assert perp_evidence["source_pack_validated_digest_sufficient"] is True
    assert perp_evidence["source_pack_watchlist_requirements_met"] is False
    assert mismatch_result.status == "rejected_results_only"
    assert "token_identity_rejected" in mismatch_result.rejected_evidence[0]["reason_codes"]
    assert substring_mismatch_result.status == "rejected_results_only"
    assert "token_identity_rejected" in substring_mismatch_result.rejected_evidence[0]["reason_codes"]


def test_event_evidence_acquisition_rejects_cryptopanic_tag_mismatch_and_heat_only():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
    import crypto_rsi_scanner.event_alpha.radar.evidence_acquisition as event_evidence_acquisition
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent

    rune = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:rune-hot-rejected",
        event_cluster_id="cluster:rune-hot",
        event_type="security_incident",
        external_asset="THORChain",
        impact_category="security_or_regulatory_shock",
        candidate_sectors=("defi_tokens",),
        candidate_symbols=("RUNE",),
        candidate_coin_ids=("thorchain",),
        impact_path_type="exploit_security_event",
        playbook_hint="security_or_regulatory_shock",
        confidence=0.78,
        hypothesis_score=64.0,
        opportunity_score_final=64.0,
        opportunity_level="exploratory",
        missing_requirements=("source evidence", "impact_path_validation"),
        validation_stage="catalyst_link_validated",
        score_components={
            "symbol": "RUNE",
            "coin_id": "thorchain",
            "validated_symbol": "RUNE",
            "validated_coin_id": "thorchain",
            "playbook_type": "security_or_regulatory_shock",
            "impact_path_type": "exploit_security_event",
            "opportunity_score_final": 64.0,
            "opportunity_level": "exploratory",
        },
    )
    fetched = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
    hot_but_unrelated = RawDiscoveredEvent(
        raw_id="raw:rune-hot-unrelated",
        provider="cryptopanic",
        fetched_at=fetched,
        published_at=fetched,
        source_url="https://cryptopanic.com/news/btc-hot",
        title="Bullish crypto market heat lifts majors",
        body="CryptoPanic marks this as hot and bullish. RUNE is only mentioned in a broad market recap without incident details.",
        raw_json={"currency_tags": ("BTC",), "kind": "hot", "source_origin": "CryptoPanic"},
        source_confidence=0.88,
        content_hash="rune-hot-unrelated",
    )
    provider = event_catalyst_search.FixtureCatalystSearchProvider(rows_by_query={
        "RUNE hack incident security market reaction": (hot_but_unrelated,),
        "RUNE exploit official update": (),
    })
    result = event_evidence_acquisition.run_evidence_acquisition(
        (rune,),
        provider=provider,
        providers_by_hint={"cryptopanic": provider, "project_blog_rss": provider},
        cfg=event_evidence_acquisition.EvidenceAcquisitionConfig(
            enabled=True,
            max_candidates=1,
            max_queries=2,
            max_results_per_query=2,
            fixture_only=True,
        ),
        now=fetched,
    )

    assert result.accepted == 0
    assert result.results[0].status == "rejected_results_only"
    rejected_reasons = set(result.results[0].rejected_evidence[0]["reason_codes"])
    assert "cryptopanic_currency_tag_mismatch" in rejected_reasons
    assert "cryptopanic_narrative_heat_only" in rejected_reasons


def test_event_evidence_acquisition_provider_unavailable_and_operator_surfaces():
    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
    import crypto_rsi_scanner.event_alpha.radar.evidence_acquisition as event_evidence_acquisition
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses
    import crypto_rsi_scanner.event_alpha.artifacts.opportunity_audit as event_opportunity_audit
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    velvet = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:velvet-acquisition",
        event_cluster_id="cluster:spacex",
        event_type="ipo_proxy",
        external_asset="SpaceX",
        impact_category="tokenized_stock_venue",
        candidate_sectors=("tokenized_stock_venues",),
        candidate_symbols=("VELVET",),
        candidate_coin_ids=("velvet",),
        impact_path_type="venue_value_capture",
        candidate_role="proxy_venue",
        playbook_hint="proxy_attention",
        confidence=0.82,
        hypothesis_score=72.0,
        opportunity_score_final=72.0,
        opportunity_level="validated_digest",
        validation_stage="impact_path_validated",
        score_components={
            "symbol": "VELVET",
            "coin_id": "velvet",
            "validated_symbol": "VELVET",
            "validated_coin_id": "velvet",
            "external_asset": "SpaceX",
            "playbook_type": "proxy_attention",
            "impact_category": "tokenized_stock_venue",
            "impact_path_type": "venue_value_capture",
            "candidate_role": "proxy_venue",
            "opportunity_score_final": 72.0,
            "opportunity_level": "validated_digest",
        },
    )
    unavailable = event_evidence_acquisition.run_evidence_acquisition(
        (velvet,),
        provider=None,
        providers_by_hint={},
        cfg=event_evidence_acquisition.EvidenceAcquisitionConfig(enabled=True, max_candidates=1, max_queries=1),
    )
    assert unavailable.results[0].status == "provider_unavailable"
    assert unavailable.results[0].query_results[0].evidence_absence_is_meaningful is True

    provider = event_catalyst_search.FixtureCatalystSearchProvider(rows_by_query={
        "VELVET SpaceX pre IPO tokenized stock": (
            event_catalyst_search._raw_event_from_fixture({
                "raw_id": "raw:velvet-acquisition",
                "provider": "cryptopanic",
                "source_url": "https://cryptopanic.com/news/velvet-spacex",
                "title": "VELVET offers SpaceX pre-IPO tokenized stock exposure",
                "body": "Velvet users can trade SpaceX pre-IPO exposure through tokenized stock markets, explaining VELVET venue value capture.",
                "raw_json": {"currency_tags": ["VELVET"], "source_origin": "CryptoPanic"},
                "source_confidence": 0.90,
            }),
        ),
        "SpaceX prediction market VELVET": (
            event_catalyst_search._raw_event_from_fixture({
                "raw_id": "raw:spacex-context-only",
                "provider": "polymarket",
                "source_url": "https://polymarket.com/event/spacex-ipo",
                "title": "SpaceX IPO prediction market volume rises",
                "body": "Prediction market context for SpaceX IPO odds; no VELVET token or venue value capture is described.",
                "raw_json": {"source_origin": "Polymarket"},
                "source_confidence": 0.70,
            }),
        ),
    })
    with TemporaryDirectory() as tmp:
        artifact_path = Path(tmp) / "event_evidence_acquisition.jsonl"
        result = event_evidence_acquisition.run_evidence_acquisition(
            (velvet,),
            provider=provider,
            providers_by_hint={"cryptopanic": provider, "polymarket": provider, "project_blog_rss": provider},
            cfg=event_evidence_acquisition.EvidenceAcquisitionConfig(
                enabled=True,
                max_candidates=1,
                max_queries=3,
                fixture_only=True,
                artifact_path=artifact_path,
            ),
            run_context={"profile": "quality_validation", "artifact_namespace": "quality_validation", "run_mode": "test"},
        )
        rows = event_evidence_acquisition.load_acquisition_results(artifact_path)
    brief = event_alpha_daily_brief.build_daily_brief(
        evidence_acquisition_rows=rows,
        requested_profile="quality_validation",
        artifact_namespace="quality_validation",
        include_test_artifacts=True,
    )
    assert "Executed source-pack searches" in brief
    assert "VELVET" in brief
    assert "accepted=1" in brief
    assert rows[0]["evidence_acquisition_plan"]["query_count"] == 3
    assert rows[0]["evidence_acquisition_results"]["accepted"] == 1
    assert rows[0]["provider_coverage_statuses"] == ["complete"]

    updated = result.hypotheses[0]
    components = dict(updated.score_components)
    assert components["evidence_acquisition_status"] == "accepted_evidence_found"
    assert components["evidence_acquisition_accepted_count"] == 1
    entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="hypothesis|cluster:spacex|velvet",
        cluster_id="cluster:spacex",
        event_id="hyp:velvet-acquisition",
        coin_id="velvet",
        symbol="VELVET",
        relationship_type="impact_hypothesis",
        external_asset="SpaceX",
        event_time=None,
        state=event_watchlist.EventWatchlistState.RADAR.value,
        previous_state=None,
        first_seen_at="2026-06-15T12:00:00+00:00",
        last_seen_at="2026-06-15T12:00:00+00:00",
        latest_source="cryptopanic",
        latest_playbook_type="proxy_attention",
        latest_score_components=components,
    )
    card = event_research_cards.render_research_card(entry.key, watchlist_entries=[entry])
    assert "Evidence acquisition result: status=accepted_evidence_found" in card.markdown
    assert "Accepted evidence reasons:" in card.markdown
    audit = event_opportunity_audit.format_opportunity_audit("VELVET", hypotheses=[updated], watchlist_entries=[entry])
    assert "execution result: status=accepted_evidence_found" in audit
    assert "accepted reason codes:" in audit


def test_event_alpha_evidence_acquisition_smoke_target_exists():
    makefile = Path("Makefile").read_text(encoding="utf-8")
    assert "event-alpha-evidence-acquisition-smoke" in makefile
    profiles = Path("crypto_rsi_scanner/event_alpha/config/profiles.py").read_text(encoding="utf-8")
    assert "evidence_acquisition_smoke" in profiles
    assert "EVENT_ALPHA_EVIDENCE_ACQUISITION_FIXTURE_ONLY" in profiles


def test_core_evidence_acquisition_view_aggregates_canonical_rows():
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store

    rows = _canonical_core_fixture_rows()
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            rows,
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=path),
            run_id="run-core-acquisition-view",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        core_rows = event_core_opportunity_store.load_core_opportunities(path, latest_run=True).rows
    by_symbol = {row["symbol"]: row for row in core_rows}
    acquisition_rows = [
        {
            "row_type": "event_evidence_acquisition",
            "core_opportunity_id": by_symbol["VELVET"]["core_opportunity_id"],
            "symbol": "VELVET",
            "coin_id": "velvet",
            "source_pack": "proxy_preipo_rwa_pack",
            "status": "accepted_evidence_found",
            "accepted_evidence": [{
                "title": "VELVET offers SpaceX pre-IPO tokenized stock exposure",
                "reason_codes": ["cryptopanic_currency_tag_match", "direct_token_mechanism"],
            }],
            "evidence_quality_before": 60,
            "evidence_quality_after": 91,
            "opportunity_score_before": 70,
            "opportunity_score_after": 92,
            "opportunity_level_before": "validated_digest",
            "opportunity_level_after": "high_priority",
        },
        {
            "row_type": "event_evidence_acquisition",
            "core_opportunity_id": by_symbol["RUNE"]["core_opportunity_id"],
            "symbol": "RUNE",
            "coin_id": "thorchain",
            "source_pack": "security_shock_pack",
            "status": "accepted_evidence_found",
            "accepted_evidence": [{
                "title": "RUNE exploit update: THORChain resumes trading after incident",
                "reason_codes": ["cryptopanic_currency_tag_match", "direct_token_mechanism"],
            }],
        },
        {
            "row_type": "event_evidence_acquisition",
            "core_opportunity_id": by_symbol["AAVE"]["core_opportunity_id"],
            "symbol": "AAVE",
            "coin_id": "aave",
            "source_pack": "strategic_investment_pack",
            "status": "no_results",
        },
        {
            "row_type": "event_evidence_acquisition",
            "core_opportunity_id": by_symbol["MEME"]["core_opportunity_id"],
            "symbol": "MEME",
            "coin_id": "memecore",
            "source_pack": "market_anomaly_pack",
            "status": "no_results",
        },
    ]

    velvet = event_core_opportunity_store.core_evidence_acquisition_view_from_rows(
        by_symbol["VELVET"]["core_opportunity_id"],
        core_rows=[by_symbol["VELVET"]],
        evidence_acquisition_rows=acquisition_rows,
    )
    rune = event_core_opportunity_store.core_evidence_acquisition_view_from_rows(
        by_symbol["RUNE"]["core_opportunity_id"],
        core_rows=[by_symbol["RUNE"]],
        evidence_acquisition_rows=acquisition_rows,
    )
    aave = event_core_opportunity_store.core_evidence_acquisition_view_from_rows(
        by_symbol["AAVE"]["core_opportunity_id"],
        core_rows=[by_symbol["AAVE"]],
        evidence_acquisition_rows=acquisition_rows,
    )
    meme = event_core_opportunity_store.core_evidence_acquisition_view_from_rows(
        by_symbol["MEME"]["core_opportunity_id"],
        core_rows=[by_symbol["MEME"]],
        evidence_acquisition_rows=acquisition_rows,
    )
    assert velvet.accepted_evidence_count == 1
    assert velvet.source_pack == "proxy_preipo_rwa_pack"
    assert "cryptopanic_currency_tag_match" in velvet.accepted_reason_codes
    assert "direct_token_mechanism" in velvet.accepted_reason_codes
    assert velvet.accepted_evidence_samples[0]["title"].startswith("VELVET offers SpaceX")
    assert rune.accepted_evidence_count == 1
    assert "RUNE exploit update" in rune.accepted_evidence_samples[0]["title"]
    assert aave.acquisition_status == "no_results"
    assert aave.source_pack == "strategic_investment_pack"
    assert meme.acquisition_status == "no_results"
    assert meme.source_pack == "market_anomaly_pack"


def test_evidence_acquisition_rows_reconcile_to_canonical_core_store_ids():
    import json
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store
    import crypto_rsi_scanner.event_alpha.radar.evidence_acquisition as event_evidence_acquisition

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        core_path = root / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            _canonical_core_fixture_rows(),
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=core_path),
            run_id="run-core-acquisition",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        core_rows = event_core_opportunity_store.load_core_opportunities(core_path, latest_run=True).rows
        meme_core = next(row["core_opportunity_id"] for row in core_rows if row["coin_id"] == "memecore")
        acquisition_path = root / "event_evidence_acquisition.jsonl"
        acquisition_path.write_text(
            json.dumps({
                "row_type": "event_evidence_acquisition",
                "run_id": "run-core-acquisition",
                "profile": "market_refresh_smoke",
                "artifact_namespace": "market_refresh_smoke",
                "core_opportunity_id": "core_api_memecore",
                "hypothesis_id": "hyp-meme-core",
                "incident_id": "incident-memecore",
                "symbol": "MEME",
                "coin_id": "memecore",
            }) + "\n",
            encoding="utf-8",
        )
        changed = event_evidence_acquisition.reconcile_acquisition_core_ids(
            acquisition_path,
            core_rows,
            run_id="run-core-acquisition",
            profile="market_refresh_smoke",
            artifact_namespace="market_refresh_smoke",
        )
        rows = event_evidence_acquisition.load_acquisition_results(acquisition_path)
    assert changed >= 1
    assert rows[0]["core_opportunity_id"] == meme_core
    assert rows[0]["core_opportunity_id_status"] == "diagnostic_support"
    assert rows[0]["original_core_opportunity_id"] == "core_api_memecore"


def test_evidence_acquisition_caps_stale_promoted_final_fields():
    import json
    import crypto_rsi_scanner.event_alpha.radar.evidence_acquisition as event_evidence_acquisition

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        acquisition_path = root / "event_evidence_acquisition.jsonl"
        acquisition_path.write_text(
            json.dumps({
                "row_type": "event_evidence_acquisition",
                "run_id": "run-acq-cap",
                "profile": "live_burn_in_no_send",
                "artifact_namespace": "live_burn_in_no_send",
                "core_opportunity_id": "core_tao",
                "symbol": "TAO",
                "coin_id": "bittensor",
                "status": "rejected_results_only",
                "accepted_evidence_count": 0,
                "final_opportunity_level": "validated_digest",
                "final_route_after_quality_gate": "RESEARCH_DIGEST",
                "final_state_after_quality_gate": "WATCHLIST",
            }) + "\n",
            encoding="utf-8",
        )
        changed = event_evidence_acquisition.reconcile_acquisition_core_ids(
            acquisition_path,
            [{
                "row_type": "event_core_opportunity",
                "core_opportunity_id": "core_tao",
                "symbol": "TAO",
                "coin_id": "bittensor",
                "final_opportunity_level": "validated_digest",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "final_route_after_quality_gate": "RESEARCH_DIGEST",
                "final_state_after_quality_gate": "WATCHLIST",
            }],
            run_id="run-acq-cap",
            profile="live_burn_in_no_send",
            artifact_namespace="live_burn_in_no_send",
        )
        rows = event_evidence_acquisition.load_acquisition_results(acquisition_path)

    assert changed >= 1
    assert rows[0]["core_opportunity_id"] == "core_tao"
    assert rows[0]["opportunity_type"] == "UNCONFIRMED_RESEARCH"
    assert rows[0]["final_opportunity_level"] == "exploratory"
    assert rows[0]["final_route_after_quality_gate"] == "STORE_ONLY"
    assert rows[0]["final_state_after_quality_gate"] == "RADAR"
    assert rows[0]["acquisition_final_level_normalized"] is True
    assert rows[0]["final_verdict_reason"] == "rejected_results_only_not_confirmation"


def test_source_coverage_reconciles_cryptopanic_backoff_after_successful_request():
    import json

    import crypto_rsi_scanner.event_alpha.radar.source_coverage as event_alpha_source_coverage
    import crypto_rsi_scanner.event_alpha.notifications.provider_status as event_provider_status

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        ledger = base / "cryptopanic_request_ledger.jsonl"
        ledger.write_text(
            json.dumps({
                "timestamp": "2026-07-01T00:00:00+00:00",
                "status_code": 200,
                "currencies": "CHZ",
                "normalized_request_key": "growth_weekly|CHZ",
            }) + "\n",
            encoding="utf-8",
        )
        report = event_alpha_source_coverage.build_source_coverage_report(
            provider_status_report=event_provider_status.EventDiscoveryProviderStatus(
                mode="research_only",
                cache_dir=str(base),
                lookback_hours=72,
                horizon_days=14,
                sources=(event_provider_status.ProviderStatus("cryptopanic", "event", True),),
                enrichment=(),
                warnings=(),
                next_steps=(),
            ),
            provider_health_rows={
                "cryptopanic:event_source": {
                    "provider_key": "cryptopanic:event_source",
                    "provider": "cryptopanic",
                    "provider_service": "event_source",
                    "disabled_until": "2026-07-01T01:00:00+00:00",
                }
            },
            evidence_acquisition_rows=[{
                "source_pack": "fan_sports_pack",
                "accepted_evidence": [{"provider": "cryptopanic", "source_class": "cryptopanic_tagged"}],
            }],
            profile="notify_llm_deep",
            artifact_namespace="notify_llm_deep_cryptopanic_rehearsal",
            cryptopanic_request_ledger_path=ledger,
            now=pd.Timestamp("2026-07-01T00:30:00Z").to_pydatetime(),
        )
    assert report.cryptopanic_health_status == "healthy"
    assert report.cryptopanic_backoff_reconciled_after_success is True
    assert report.cryptopanic_successful_requests == 1


def test_cryptopanic_run_stats_dedupes_query_and_result_accepted_evidence():
    import json

    from crypto_rsi_scanner import config, scanner
    import crypto_rsi_scanner.event_alpha.providers.provider_health as event_provider_health

    old_health_path = config.EVENT_PROVIDER_HEALTH_PATH
    old_token = config.EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN
    old_live = config.EVENT_DISCOVERY_CRYPTOPANIC_LIVE
    old_path = config.EVENT_DISCOVERY_CRYPTOPANIC_PATH
    try:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            health_path = base / "event_provider_health.json"
            config.EVENT_PROVIDER_HEALTH_PATH = health_path
            config.EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN = "test-token"
            config.EVENT_DISCOVERY_CRYPTOPANIC_LIVE = True
            config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = None
            event_provider_health.write_provider_health(health_path, {})
            ledger = health_path.with_name("cryptopanic_request_ledger.jsonl")
            ledger.write_text(
                json.dumps({
                    "timestamp": "2026-07-01T00:00:00+00:00",
                    "status_code": 200,
                    "currencies": "CHZ",
                    "normalized_request_key": "growth_weekly|CHZ",
                }) + "\n",
                encoding="utf-8",
            )
            evidence = {"provider": "cryptopanic", "source_url": "https://example.test/chz", "title": "CHZ World Cup demand"}
            result = SimpleNamespace(
                evidence_acquisition_result=SimpleNamespace(results=[
                    SimpleNamespace(
                        providers_used=("cryptopanic",),
                        query_results=(SimpleNamespace(
                            provider_hint="cryptopanic",
                            provider_used="cryptopanic",
                            query="CHZ",
                            results_seen=1,
                            provider_failures=(),
                            accepted_evidence=(evidence,),
                            rejected_evidence=(),
                        ),),
                        accepted_evidence=(evidence,),
                        rejected_evidence=(),
                        provider_failures=(),
                    )
                ])
            )
            stats = scanner._cryptopanic_stats_for_pipeline_result(result, provider_health_path=health_path)
    finally:
        config.EVENT_PROVIDER_HEALTH_PATH = old_health_path
        config.EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN = old_token
        config.EVENT_DISCOVERY_CRYPTOPANIC_LIVE = old_live
        config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = old_path
    assert stats["cryptopanic_accepted_evidence"] == 1
    assert stats["cryptopanic_successful_requests"] == 1


def test_research_card_source_coverage_uses_authoritative_json():
    import json
    from datetime import datetime, timezone

    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        cards_dir = base / "research_cards"
        (base / "event_alpha_source_coverage.json").write_text(
            json.dumps({
                "packs": [{
                    "source_pack": "fan_sports_pack",
                    "provider_coverage_status": "partial",
                    "evidence_absence_meaningful": True,
                    "providers_missing_for_confirmation": ["sports_fixtures"],
                    "providers_degraded_for_confirmation": ["gdelt", "project_blog_rss"],
                    "missing_providers": ["sports_fixtures"],
                    "degraded_or_backoff_providers": ["gdelt", "project_blog_rss"],
                    "coverage_gap_reason": "source_pack_coverage_partial;missing:sports_fixtures;degraded:gdelt,project_blog_rss",
                }]
            }),
            encoding="utf-8",
        )
        core_row = {
            "row_type": "event_core_opportunity",
            "schema_version": "event_core_opportunity_store_v1",
            "run_id": "run-1",
            "profile": "notify_llm_deep",
            "artifact_namespace": "ns",
            "core_opportunity_id": "core_chz_review",
            "symbol": "CHZ",
            "coin_id": "chiliz",
            "incident_id": "world-cup-chz",
            "canonical_incident_name": "World Cup fan token attention",
            "candidate_role": "proxy_instrument",
            "primary_impact_path": "fan_token_event",
            "impact_path_type": "fan_token_event",
            "opportunity_level": "exploratory",
            "final_opportunity_level": "exploratory",
            "opportunity_score_final": 64,
            "final_route_after_quality_gate": "STORE_ONLY",
            "final_state_after_quality_gate": "RADAR",
            "source_pack": "fan_sports_pack",
            "provider_coverage_status": "complete",
            "evidence_acquisition_status": "accepted_evidence_found",
            "evidence_acquisition_accepted_count": 1,
            "evidence_acquisition_accepted_evidence": [{
                "provider": "cryptopanic",
                "source_class": "cryptopanic_tagged",
                "title": "CHZ fan token demand builds into World Cup",
            }],
            "accepted_evidence_reason_codes": ["cryptopanic_currency_tag_match"],
            "generated_at": "2026-07-01T00:00:00+00:00",
        }
        result = event_research_cards.write_research_cards(
            cards_dir,
            watchlist_entries=[],
            alert_rows=[core_row],
            now=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        assert result.cards_written == 1
        text = result.card_paths[0].read_text(encoding="utf-8")
    assert "- Coverage status: partial" in text
    assert "missing:sports_fixtures" in text
    assert "degraded:gdelt" in text
    assert "Provider/source gaps: none" not in text


def test_market_reaction_rejected_evidence_is_unconfirmed_research():
    import crypto_rsi_scanner.event_alpha.radar.market_reaction as event_market_reaction

    result = event_market_reaction.evaluate_market_reaction({
        "source_class": "broad_news",
        "source_pack": "strategic_investment_pack",
        "impact_path_type": "strategic_investment",
        "evidence_quality_score": 42,
        "evidence_acquisition_status": "rejected_results_only",
        "market_snapshot": {
            "return_24h": 0.01,
            "volume_zscore_24h": 0.1,
            "market_context_freshness_status": "fresh",
        },
    })

    assert result.opportunity_type == "UNCONFIRMED_RESEARCH"
    assert "evidence_acquisition_rejected_results_only" in result.why_not_alertable


def test_event_alpha_source_coverage_coinalyze_links_only_existing_artifacts():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import config
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.radar.source_coverage as event_alpha_source_coverage
    import crypto_rsi_scanner.event_alpha.providers.coinalyze_preflight as event_coinalyze_preflight

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        provider_report = event_provider_status.build_event_discovery_provider_status(config)
        report = event_alpha_source_coverage.build_source_coverage_report(
            provider_status_report=provider_report,
            artifact_namespace="unit",
            profile="notify_llm_deep",
            artifact_namespace_dir=base,
            now=datetime(2026, 6, 15, tzinfo=timezone.utc),
        )
        text = event_alpha_source_coverage.format_source_coverage_report(report)
        assert "- Coinalyze preflight: not generated" in text
        assert "event_coinalyze_preflight.md" not in text
        assert "make event-alpha-coinalyze-preflight ARTIFACT_NAMESPACE=unit PROFILE=notify_llm_deep PYTHON=python3" in text

        preflight = event_coinalyze_preflight.build_preflight_report(
            namespace_dir=base,
            smoke_mode=True,
            now=datetime(2026, 6, 15, tzinfo=timezone.utc),
        )
        event_coinalyze_preflight.write_preflight_artifacts(preflight, base)
        report = event_alpha_source_coverage.build_source_coverage_report(
            provider_status_report=provider_report,
            artifact_namespace="unit",
            profile="notify_llm_deep",
            artifact_namespace_dir=base,
            now=datetime(2026, 6, 15, tzinfo=timezone.utc),
        )
        text = event_alpha_source_coverage.format_source_coverage_report(report)
        assert "- Coinalyze preflight report: event_coinalyze_preflight.md" in text
        assert "- Coinalyze preflight JSON: event_coinalyze_preflight.json" in text
        assert "Coinalyze supported metric status:" in text
        assert "basis=fixture_only" in text
        assert report.to_dict()["coinalyze_supported_metric_status"]["predicted_funding"] == "implemented"

        bad = base / "event_alpha_source_coverage.md"
        bad.write_text("- Coinalyze preflight report: event_coinalyze_preflight.md\n- Coinalyze preflight JSON: event_coinalyze_preflight.json\n", encoding="utf-8")
        (base / event_coinalyze_preflight.PREFLIGHT_JSON).unlink()
        result = event_alpha_artifact_doctor.diagnose_artifacts(
            profile="notify_llm_deep",
            artifact_namespace="unit",
            source_coverage_report_path=bad,
            include_test_artifacts=True,
            strict=True,
        )
        assert result.source_coverage_coinalyze_missing_linked_artifact >= 1
        assert result.status == "BLOCKED"
