"""Focused Event Alpha impact-hypothesis lifecycle tests."""

from __future__ import annotations

from tests.event_alpha import _api_helpers as _event_alpha_api_helpers


globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


def test_hypothesis_family_and_watchlist_preserve_source_independence_state():
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as hypotheses
    from crypto_rsi_scanner.event_alpha.radar.impact_hypotheses import family
    from crypto_rsi_scanner.event_alpha.radar import source_independence
    from crypto_rsi_scanner.event_alpha.radar.watchlist import entries

    def contract(source_id: str, origin: str, word: str):
        return source_independence.assess_source_independence(
            [
                {
                    "source_id": source_id,
                    "source_url": f"https://{origin}/story",
                    "published_at": "2026-07-15T12:00:00Z",
                    "title": f"{word} catalyst report",
                    "body": " ".join(f"{word}{index}" for index in range(24)),
                }
            ]
        )

    def hypothesis(hypothesis_id: str, value):
        return hypotheses.EventImpactHypothesis(
            hypothesis_id=hypothesis_id,
            event_cluster_id="cluster:source-independence",
            incident_id="incident:source-independence",
            event_type="protocol_upgrade",
            external_asset="Protocol",
            impact_category="infrastructure_upgrade",
            candidate_sectors=("infrastructure",),
            candidate_symbols=("SRC",),
            confidence=0.8,
            source_independence=value,
            source_independence_status="assessed",
            independent_source_count=1,
            independent_corroboration_count=0,
            source_content_cluster_count=1,
        )

    merged = family._merge_duplicate_hypotheses(  # noqa: SLF001
        hypothesis("hyp:a", contract("a", "a.example", "alpha")),
        hypothesis("hyp:b", contract("b", "b.example", "bravo")),
    )

    assert merged.source_independence_status == "assessed"
    assert merged.independent_source_count == 2
    assert merged.independent_corroboration_count == 1
    assert merged.score_components["source_independence_status"] == "assessed"

    rejected = hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:rejected",
        event_cluster_id="cluster:source-independence",
        event_type="protocol_upgrade",
        external_asset="Protocol",
        impact_category="infrastructure_upgrade",
        candidate_sectors=("infrastructure",),
        candidate_symbols=("SRC",),
        source_independence_status="rejected",
        source_independence_errors=("source_independence_source_context_incomplete",),
    )
    components = entries._hypothesis_source_independence_fields(rejected)  # noqa: SLF001

    assert components["source_independence_status"] == "rejected"
    assert components["source_independence"] == {}
    assert components["source_independence_errors"] == [
        "source_independence_source_context_incomplete"
    ]


def test_event_impact_hypotheses_generate_seed_categories_and_queries():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import config
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses
    from crypto_rsi_scanner.event_core.models import EventDiscoveryResult, NormalizedEvent, RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)

    def raw(raw_id, title, body, *, provider="fixture", event_type="external_proxy_event", external="SpaceX"):
        return RawDiscoveredEvent(
            raw_id=raw_id,
            provider=provider,
            fetched_at=now,
            published_at=now,
            source_url=f"https://example.test/{raw_id}",
            title=title,
            body=body,
            raw_json={
                "event": {
                    "event_id": raw_id,
                    "event_name": title,
                    "event_type": event_type,
                    "event_time": "2026-06-20T13:30:00Z",
                    "event_time_confidence": 0.9,
                    "external_asset": external,
                    "description": body,
                    "confidence": 0.9,
                }
            },
            source_confidence=0.9,
            content_hash=raw_id,
        )

    def norm(raw_event, *, event_type="external_proxy_event", external="SpaceX"):
        return NormalizedEvent(
            event_id=raw_event.raw_id,
            raw_ids=(raw_event.raw_id,),
            event_name=raw_event.title,
            event_type=event_type,
            event_time=now,
            event_time_confidence=0.9,
            first_seen_time=now,
            source=raw_event.provider,
            source_urls=(raw_event.source_url,),
            external_asset=external,
            description=raw_event.body,
            confidence=0.9,
        )

    rows = [
        raw("spacex", "SpaceX pre-IPO exposure opens", "Tokenized stock venue launches SpaceX pre-IPO exposure."),
        raw("openai", "OpenAI pre-IPO market opens", "Crypto traders discuss OpenAI pre-IPO proxy exposure.", external="OpenAI"),
        raw("worldcup", "World Cup fan token prediction market", "CHZ-style fan tokens move before World Cup match.", event_type="sports_event", external="World Cup"),
        raw("genius", "GENIUS Act stablecoin reserve bill", "Stablecoin reserve rules and money market funds move forward.", event_type="regulatory_event", external="GENIUS Act"),
        RawDiscoveredEvent(
            raw_id="anomaly",
            provider="market_anomaly",
            fetched_at=now,
            published_at=now,
            source_url=None,
            title="PUMP market anomaly",
            body="No dated external catalyst found.",
            raw_json={"market": {"symbol": "PUMP", "coin_id": "pump"}, "anomaly": {"score": 90}},
            source_confidence=0.7,
            content_hash="anomaly",
        ),
    ]
    result = EventDiscoveryResult(
        raw_events=tuple(rows),
        normalized_events=tuple(norm(row, event_type=row.raw_json["event"]["event_type"], external=row.raw_json["event"]["external_asset"]) for row in rows if row.provider != "market_anomaly"),
        links=(),
        classifications=(),
        candidates=(),
    )
    hypotheses = event_impact_hypotheses.generate_impact_hypotheses(result, now=now)
    categories = {item.impact_category for item in hypotheses}
    assert "rwa_preipo_proxy" in categories
    assert "tokenized_stock_venue" in categories
    assert "ai_ipo_proxy" in categories
    assert "sports_fan_proxy" in categories
    assert "stablecoin_regulatory" in categories
    assert "market_anomaly_unknown" in categories
    spacex = next(item for item in hypotheses if item.impact_category == "rwa_preipo_proxy")
    assert "tokenized_stock_venues" in spacex.candidate_sectors
    assert "VELVET" in spacex.candidate_symbols
    assert any("VELVET SpaceX exposure" in query for query in spacex.search_queries)
    assert any("VELVET SpaceX pre-IPO exposure" in query for query in spacex.search_queries)
    assert any(
        detail["query_type"] == "candidate_discovery" and detail["query"] == "SpaceX crypto exposure"
        for detail in spacex.search_query_details
    )
    anomaly = next(item for item in hypotheses if item.impact_category == "market_anomaly_unknown")
    assert anomaly.status == "hypothesis"
    assert "TRIGGERED_FADE" not in event_impact_hypotheses.format_impact_hypothesis_report(hypotheses)


def test_event_impact_hypothesis_matching_uses_context_not_substrings():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses
    from crypto_rsi_scanner.event_core.models import EventDiscoveryResult, NormalizedEvent, RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)

    def row(raw_id, title, body, event_type="news", external=None):
        raw = RawDiscoveredEvent(
            raw_id=raw_id,
            provider="fixture",
            fetched_at=now,
            published_at=now,
            source_url=f"https://example.test/{raw_id}",
            title=title,
            body=body,
            raw_json={
                "event": {
                    "event_id": raw_id,
                    "event_name": title,
                    "event_type": event_type,
                    "external_asset": external,
                    "description": body,
                    "confidence": 0.85,
                }
            },
            source_confidence=0.85,
            content_hash=raw_id,
        )
        event = NormalizedEvent(
            event_id=raw_id,
            raw_ids=(raw_id,),
            event_name=title,
            event_type=event_type,
            event_time=None,
            event_time_confidence=0.0,
            first_seen_time=now,
            source="fixture",
            source_urls=(raw.source_url,),
            external_asset=external,
            description=body,
            confidence=0.85,
        )
        return raw, event

    negatives = [
        row("matched", "Matched market-anomaly filters", "The market signal was matched by research filters."),
        row("open", "Open interest rises", "Open markets and open-source tools are not OpenAI proxy catalysts."),
        row("prime", "Prime liquidity improves", "Prime market depth improved without prime minister or election context."),
        row("hype", "IPO hype builds", "Generic IPO hype without HYPE, Hyperliquid, tokenized stock, or explicit exposure."),
    ]
    result = EventDiscoveryResult(
        raw_events=tuple(raw for raw, _ in negatives),
        normalized_events=tuple(event for _, event in negatives),
        links=(),
        classifications=(),
        candidates=(),
    )
    hypotheses = event_impact_hypotheses.generate_impact_hypotheses(result, now=now)
    categories = {item.impact_category for item in hypotheses}
    assert "sports_fan_proxy" not in categories
    assert "ai_ipo_proxy" not in categories
    assert "political_meme_proxy" not in categories
    assert "rwa_preipo_proxy" not in categories

    positives = [
        row("sports", "World Cup fan token fixture", "Fan token attention rises before the World Cup kickoff.", "sports_event", "World Cup"),
        row("political", "Election meme prediction market", "Political meme tokens move around an election prediction market.", "political_event", "Election"),
        row("infra", "Prediction market oracle selected", "Chainlink oracle infrastructure will settle prediction market outcomes.", "infrastructure_event", "Polymarket"),
        row("stable", "GENIUS Act stablecoin reserve bill", "Stablecoin reserve regulation advances in the Senate.", "regulatory_event", "GENIUS Act"),
    ]
    positive_result = EventDiscoveryResult(
        raw_events=tuple(raw for raw, _ in positives),
        normalized_events=tuple(event for _, event in positives),
        links=(),
        classifications=(),
        candidates=(),
    )
    positive_categories = {
        item.impact_category
        for item in event_impact_hypotheses.generate_impact_hypotheses(positive_result, now=now)
    }
    assert "sports_fan_proxy" in positive_categories
    assert "political_meme_proxy" in positive_categories
    assert "prediction_market_infra" in positive_categories
    assert "stablecoin_regulatory" in positive_categories


def test_event_impact_hypothesis_category_refinements_for_validated_news():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses
    from crypto_rsi_scanner.event_core.models import EventDiscoveryResult, NormalizedEvent, RawDiscoveredEvent

    now = datetime(2026, 6, 23, 12, 0, tzinfo=timezone.utc)

    def row(raw_id, title, body, event_type="news", external=None):
        raw = RawDiscoveredEvent(
            raw_id=raw_id,
            provider="fixture",
            fetched_at=now,
            published_at=now,
            source_url=f"https://example.test/{raw_id}",
            title=title,
            body=body,
            raw_json={},
            source_confidence=0.85,
            content_hash=raw_id,
        )
        event = NormalizedEvent(
            event_id=raw_id,
            raw_ids=(raw_id,),
            event_name=title,
            event_type=event_type,
            event_time=None,
            event_time_confidence=0.0,
            first_seen_time=now,
            source="fixture",
            source_urls=(raw.source_url,),
            external_asset=external,
            description=body,
            confidence=0.85,
        )
        return raw, event

    cases = [
        row(
            "arb-prediction",
            "Arbitrum and Ethereum prediction market platform expands",
            "Arbitrum smart contracts and Ethereum settlement support a new prediction market platform for a Mike Tyson fight.",
            "infrastructure_event",
            "Polymarket",
        ),
        row(
            "sol-tokenized-equity",
            "Solana tokenized equity volume grows",
            "Solana venue activity rises as tokenized stock markets and synthetic exposure products gain volume.",
            "rwa_event",
            "tokenized equity",
        ),
        row(
            "btc-quantum-policy",
            "Bitcoin quantum-computing policy shock draws Trump comments",
            "Bitcoin technology risk rises as quantum-computing policy debate and Trump comments hit crypto headlines.",
            "technology_risk",
            "unknown",
        ),
        row(
            "zec-listing",
            "Zcash miner Nasdaq listing opens",
            "A Zcash mining company completes a public listing; liquidity and market access may change.",
            "listing_event",
            "Nasdaq",
        ),
        row(
            "rune-exploit",
            "THORChain exploit investigation begins",
            "THORChain RUNE faces an exploit and security incident investigation after an attack.",
            "security_event",
            "THORChain",
        ),
        row(
            "chz-world-cup",
            "World Cup fan token prediction market",
            "CHZ-style fan tokens move before a World Cup fixture and team kickoff.",
            "sports_event",
            "World Cup",
        ),
    ]
    result = EventDiscoveryResult(
        raw_events=tuple(raw for raw, _ in cases),
        normalized_events=tuple(event for _, event in cases),
        links=(),
        classifications=(),
        candidates=(),
    )
    by_event: dict[str, set[str]] = {}
    for item in event_impact_hypotheses.generate_impact_hypotheses(result, now=now):
        by_event.setdefault(item.source_event_ids[0], set()).add(item.impact_category)

    assert "prediction_market_infra" in by_event["arb-prediction"]
    assert "political_meme_proxy" not in by_event["arb-prediction"]
    assert {"tokenized_stock_venue", "rwa_preipo_proxy"} & by_event["sol-tokenized-equity"]
    assert "political_meme_proxy" not in by_event["sol-tokenized-equity"]
    assert "security_or_regulatory_shock" in by_event["btc-quantum-policy"]
    assert "political_meme_proxy" not in by_event["btc-quantum-policy"]
    assert "listing_liquidity_event" in by_event["zec-listing"]
    assert "security_or_regulatory_shock" not in by_event["zec-listing"]
    assert "security_or_regulatory_shock" in by_event["rune-exploit"]
    assert "sports_fan_proxy" in by_event["chz-world-cup"]


def test_event_impact_hypothesis_validation_is_identity_safe():
    import tempfile
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent
    from pathlib import Path

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    hypothesis = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp-test",
        event_cluster_id="spacex|ipo_proxy|2026-06-20",
        event_type="ipo_proxy",
        external_asset="SpaceX",
        impact_category="rwa_preipo_proxy",
        candidate_sectors=("tokenized_stock_venues",),
        candidate_symbols=("VELVET", "HYPE"),
        candidate_coin_ids=("velvet", "hyperliquid"),
        direction_hint="up_then_fade",
        playbook_hint="rwa_preipo_proxy",
        confidence=0.82,
        search_queries=("VELVET SpaceX pre-IPO exposure",),
        status="validation_search_pending",
    )

    queries = event_catalyst_search.generate_search_queries_for_hypothesis(hypothesis)
    assert "VELVET SpaceX exposure" in queries
    assert "VELVET SpaceX pre-IPO" in queries
    assert "VELVET SpaceX pre-IPO exposure" in queries
    assert "HYPE tokenized stock SpaceX" not in queries
    specs = event_catalyst_search.generate_search_query_specs_for_hypothesis(hypothesis)
    assert any(spec.query_type == "candidate_discovery" and spec.query == "SpaceX crypto exposure" for spec in specs)

    good = RawDiscoveredEvent(
        raw_id="good",
        provider="fixture_search",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/velvet-spacex",
        title="VELVET opens SpaceX pre-IPO exposure",
        body="Velvet Capital users can trade tokenized stock style exposure to SpaceX.",
        raw_json={},
        source_confidence=0.9,
        content_hash="good",
    )
    catalyst_only = RawDiscoveredEvent(
        raw_id="catalyst-only",
        provider="fixture_search",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/spacex",
        title="SpaceX pre-IPO market attention rises",
        body="No crypto token is named.",
        raw_json={},
        source_confidence=0.9,
        content_hash="catalyst-only",
    )
    url_only = RawDiscoveredEvent(
        raw_id="url-only",
        provider="fixture_search",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/search?q=VELVET+SpaceX",
        title="SpaceX pre-IPO market attention rises",
        body="No crypto token is named.",
        raw_json={},
        source_confidence=0.9,
        content_hash="url-only",
    )

    validated = event_impact_hypotheses.validate_hypotheses_with_raw_events([hypothesis], [good])[0]
    assert validated.status == "validated"
    assert validated.hypothesis_scope == "token"
    assert validated.candidate_symbols == ("VELVET",)
    assert any("identity_match" in reason for reason in validated.validation_reasons)
    with tempfile.TemporaryDirectory() as tmp:
        cfg = event_watchlist.EventWatchlistConfig(enabled=True, state_path=Path(tmp) / "watchlist.jsonl")
        first = event_watchlist.refresh_hypothesis_watchlist([hypothesis], cfg=cfg, now=now)
        second = event_watchlist.refresh_hypothesis_watchlist([validated], cfg=cfg, now=now)
        assert first.entries[0].state == event_watchlist.EventWatchlistState.HYPOTHESIS.value
        assert first.entries[0].symbol == "SECTOR"
        assert first.entries[0].coin_id == "rwa_preipo_proxy"
        assert first.entries[0].latest_score_components["candidate_symbols"] == ["VELVET", "HYPE"]
        assert first.entries[0].should_alert is False
        assert second.entries[0].state == event_watchlist.EventWatchlistState.RADAR.value
        assert second.entries[0].symbol == "VELVET"
        assert second.entries[0].coin_id == "velvet"
        assert second.entries[0].should_alert is True
        assert second.entries[0].state != event_watchlist.EventWatchlistState.TRIGGERED_FADE.value
    unchanged = event_impact_hypotheses.validate_hypotheses_with_raw_events([hypothesis], [catalyst_only])[0]
    assert unchanged.status == "rejected"
    assert unchanged.validation_stage == event_impact_hypotheses.ValidationStage.REJECTED.value
    assert "source_mentions_catalyst_without_candidate_asset" in unchanged.rejection_reasons
    rejected = event_impact_hypotheses.validate_hypotheses_with_raw_events([hypothesis], [url_only])[0]
    assert rejected.status != "validated"


def test_event_impact_path_validation_distinguishes_real_impact_from_cooccurrence():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import config
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent

    now = datetime(2026, 6, 24, 12, 0, tzinfo=timezone.utc)

    def raw(raw_id, title, body, market=None, provider="fixture_search"):
        market_payload = dict(market or {}) if market is not None else None
        if market_payload is not None:
            market_payload.setdefault("observed_at", now.isoformat())
        return RawDiscoveredEvent(
            raw_id=raw_id,
            provider=provider,
            fetched_at=now,
            published_at=now,
            source_url=f"https://example.test/{raw_id}",
            title=title,
            body=body,
            raw_json={"market": market_payload or {}} if market is not None else {},
            source_confidence=0.9,
            content_hash=raw_id,
        )

    def hypothesis(hypothesis_id, symbol, coin_id, category, external="unknown"):
        return event_impact_hypotheses.EventImpactHypothesis(
            hypothesis_id=hypothesis_id,
            event_cluster_id=f"cluster:{hypothesis_id}",
            event_type="news",
            external_asset=external,
            impact_category=category,
            candidate_sectors=("direct_token_events",),
            candidate_symbols=(symbol,),
            candidate_coin_ids=(coin_id,),
            direction_hint="volatility",
            playbook_hint=category,
            confidence=0.85,
            hypothesis_score=70,
            validation_stage=event_impact_hypotheses.ValidationStage.VALIDATION_SEARCH_PENDING.value,
            status=event_impact_hypotheses.HypothesisStatus.VALIDATION_SEARCH_PENDING.value,
        )

    cases = [
        (
            hypothesis("hyp:rune", "RUNE", "thorchain", "security_or_regulatory_shock", "THORChain"),
            raw(
                "rune",
                "THORChain exploit investigation",
                "THORChain RUNE faces an exploit and security incident after an attack.",
                market={"return_24h": 0.32, "volume_zscore_24h": 3.4, "volume_to_market_cap": 0.28},
            ),
            "exploit_security_event",
            "impact_path_validated",
            "exploit_security_event",
            "direct_subject",
            "strong",
            "watchlist",
        ),
        (
            hypothesis("hyp:zec", "ZEC", "zcash", "listing_liquidity_event", "Nasdaq"),
            raw(
                "zec",
                "Zcash miner Nasdaq listing opens",
                "Zcash ZEC miner completes a Nasdaq listing and public market access changes.",
                market={"return_72h": 0.54, "volume_zscore_24h": 2.5},
            ),
            "listing_liquidity_event",
            "impact_path_validated",
            "listing_liquidity_event",
            "direct_subject",
            "strong",
            "watchlist",
        ),
        (
            hypothesis("hyp:chz", "CHZ", "chiliz", "sports_fan_proxy", "World Cup"),
            raw(
                "chz",
                "World Cup fan token demand",
                "CHZ fan token demand rises into a World Cup fixture and team kickoff.",
                market={"return_24h": 0.27, "volume_zscore_24h": 3.1, "relative_strength_vs_btc": 0.20},
            ),
            "fan_token_event",
            "impact_path_validated",
            "fan_token_attention",
            "proxy_instrument",
            "strong",
            "watchlist",
        ),
        (
            hypothesis("hyp:btc", "BTC", "bitcoin", "security_or_regulatory_shock", "unknown"),
            raw("btc", "Bitcoin quantum policy debate", "Bitcoin quantum-computing policy debate and Trump comments hit broad crypto headlines."),
            "generic_policy_only",
            "catalyst_link_validated",
            "technology_risk",
            "macro_affected_asset",
            "weak",
            "local_only",
        ),
        (
            hypothesis("hyp:cftc", "BTC", "bitcoin", "security_or_regulatory_shock", "CFTC"),
            raw("cftc", "CFTC chair talks perps", "The CFTC chair discussed perps generally while Bitcoin appeared in broader market coverage."),
            "generic_policy_only",
            "catalyst_link_validated",
            "market_structure_policy",
            "macro_affected_asset",
            "weak",
            "local_only",
        ),
        (
            hypothesis("hyp:re", "RE", "real", "political_meme_proxy", "Trump"),
            raw("re", "Trump quantum cryptography order", "Trump quantum cryptography policy mentions RE token relation only as weak market co-occurrence."),
            "generic_policy_only",
            "catalyst_link_validated",
            "technology_risk",
            "macro_affected_asset",
            "weak",
            "local_only",
        ),
    ]
    original_allow_stale_fixture = config.EVENT_MARKET_CONTEXT_ALLOW_STALE_FIXTURE
    config.EVENT_MARKET_CONTEXT_ALLOW_STALE_FIXTURE = True
    try:
        for hypothesis, source, reason, stage, path_type, role, strength, expected_level in cases:
            validated = event_impact_hypotheses.validate_hypotheses_with_raw_events((hypothesis,), (source,))[0]
            assert validated.status == event_impact_hypotheses.HypothesisStatus.VALIDATED.value
            assert validated.impact_path_reason == reason
            assert validated.validation_stage == stage
            assert validated.impact_path_type == path_type
            assert validated.candidate_role == role
            assert validated.impact_path_strength == strength
            assert validated.opportunity_score_v2 is not None
            assert "impact_path_strength" in validated.opportunity_score_components
            assert validated.evidence_quality_score is not None
            assert validated.source_class
            assert validated.evidence_specificity
            assert validated.market_confirmation_level
            assert validated.opportunity_score_final is not None
            assert validated.opportunity_level == expected_level
            assert validated.manual_verification_items
            if strength == "weak":
                assert validated.digest_eligible_by_impact_path is False
                assert validated.why_digest_ineligible
                assert validated.why_local_only or validated.why_not_watchlist
            else:
                assert validated.digest_eligible_by_impact_path is True
    finally:
        config.EVENT_MARKET_CONTEXT_ALLOW_STALE_FIXTURE = original_allow_stale_fixture


def test_event_impact_hypothesis_persists_upgrade_and_downgrade_paths():
    # Validated hypotheses must persist the opportunity upgrade/downgrade
    # diagnostics on the row (and through the store), not only compute them
    # on-demand in reports. Research-only; no routing/send/trade behavior.
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses
    import crypto_rsi_scanner.event_alpha.radar.impact_hypothesis_store as event_impact_hypothesis_store
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent

    now = datetime(2026, 6, 24, 12, 0, tzinfo=timezone.utc)
    hypothesis = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:rune-upgrade",
        event_cluster_id="cluster:rune",
        event_type="news",
        external_asset="THORChain",
        impact_category="security_or_regulatory_shock",
        candidate_sectors=("direct_token_events",),
        candidate_symbols=("RUNE",),
        candidate_coin_ids=("thorchain",),
        direction_hint="volatility",
        playbook_hint="security_or_regulatory_shock",
        confidence=0.85,
        hypothesis_score=70,
        validation_stage=event_impact_hypotheses.ValidationStage.VALIDATION_SEARCH_PENDING.value,
        status=event_impact_hypotheses.HypothesisStatus.VALIDATION_SEARCH_PENDING.value,
    )
    source = RawDiscoveredEvent(
        raw_id="rune",
        provider="fixture_search",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/rune",
        title="THORChain exploit investigation",
        body="THORChain RUNE faces an exploit and security incident after an attack.",
        raw_json={"market": {"return_24h": 0.32, "volume_zscore_24h": 3.4, "volume_to_market_cap": 0.28}},
        source_confidence=0.9,
        content_hash="rune",
    )
    validated = event_impact_hypotheses.validate_hypotheses_with_raw_events((hypothesis,), (source,))[0]
    # Fields exist and are tuples (the dataclass default is an empty tuple).
    assert isinstance(validated.upgrade_requirements, tuple)
    assert isinstance(validated.downgrade_warnings, tuple)
    # explain_upgrade_path always emits at least one downgrade warning, so a
    # validated hypothesis should carry concrete diagnostics, not just defaults.
    assert validated.downgrade_warnings, "validated hypothesis should persist downgrade warnings"

    # And the fields survive into the persisted JSONL store row.
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_impact_hypotheses.jsonl"
        cfg = event_impact_hypothesis_store.EventImpactHypothesisStoreConfig(path=path)
        event_impact_hypothesis_store.write_impact_hypotheses(
            (validated,), cfg=cfg, run_id="r1", profile="quality_validation",
            run_mode="test", artifact_namespace="quality_validation", now=now,
        )
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        assert rows, "store should write at least one row"
        row = rows[0]
        assert "upgrade_requirements" in row and "downgrade_warnings" in row
        assert list(row["downgrade_warnings"]) == list(validated.downgrade_warnings)


def test_opportunity_confirmation_and_freshness_flags_require_semantic_truth():
    import crypto_rsi_scanner.event_alpha.radar.opportunity_verdict as verdicts

    false_context = verdicts._opportunity_context(  # noqa: SLF001
        impact_path=None,
        market_confirmation=None,
        evidence_quality=None,
        hypothesis=None,
        score_components={
            "market_reaction_confirmed": "false",
            "causal_mechanism_confirmed": "0",
            "freshness_cap_applied": "no",
            "market_context_freshness_cap_applied": 2,
        },
    )
    true_context = verdicts._opportunity_context(  # noqa: SLF001
        impact_path=None,
        market_confirmation=None,
        evidence_quality=None,
        hypothesis=None,
        score_components={
            "market_reaction_confirmed": "true",
            "causal_mechanism_confirmed": 1,
            "freshness_cap_applied": "yes",
        },
    )

    assert false_context.market_reaction_confirmed is False
    assert false_context.causal_mechanism_confirmed is False
    assert false_context.market_freshness_cap_applied is False
    assert true_context.market_reaction_confirmed is True
    assert true_context.causal_mechanism_confirmed is True
    assert true_context.market_freshness_cap_applied is True

    base_components = {
        "opportunity_level": "watchlist",
        "opportunity_score_final": 80,
        "impact_path_strength": "strong",
        "market_confirmation_level": "strong",
        "market_confirmation_score": 75,
        "evidence_quality_score": 80,
        "timing_event_window": 80,
        "liquidity_tradability": 80,
        "market_context_freshness_status": "fresh",
    }
    false_upgrade = verdicts.explain_upgrade_path(
        components={
            **base_components,
            "freshness_cap_applied": "false",
            "market_freshness_cap_applied": "off",
        }
    )
    true_upgrade = verdicts.explain_upgrade_path(
        components={**base_components, "freshness_cap_applied": "true"}
    )

    assert "market_context_stale" not in false_upgrade.downgrade_warnings
    assert "needs_fresh_market_confirmation" not in false_upgrade.upgrade_requirements
    assert "market_context_stale" in true_upgrade.downgrade_warnings
    assert "needs_fresh_market_confirmation" in true_upgrade.upgrade_requirements


def test_event_opportunity_verdict_uses_incident_confidence_and_cause_status():
    import crypto_rsi_scanner.event_alpha.radar.evidence_quality as event_evidence_quality
    import crypto_rsi_scanner.event_alpha.radar.impact_path_validator as event_impact_path_validator
    import crypto_rsi_scanner.event_alpha.radar.market_confirmation as event_market_confirmation
    import crypto_rsi_scanner.event_alpha.radar.opportunity_verdict as event_opportunity_verdict

    strong_market = event_market_confirmation.EventMarketConfirmationResult(
        market_confirmation_score=78,
        level="strong",
        reasons=("price_momentum", "volume_expansion"),
        data_quality=80,
    )
    strong_evidence = event_evidence_quality.EvidenceQualityResult(
        evidence_quality_score=82,
        source_class="crypto_news",
        evidence_specificity="direct_token_mechanism",
    )

    def path(role, *, cause="confirmed", polarity=("asserted",)):
        return event_impact_path_validator.ImpactPathValidation(
            impact_path_type=event_impact_path_validator.ImpactPathType.EXPLOIT_SECURITY_EVENT.value,
            impact_path_strength=event_impact_path_validator.ImpactPathStrength.STRONG.value,
            candidate_role=role,
            evidence_specificity_score=90,
            required_evidence_met=True,
            market_confirmation_required=False,
            digest_eligible_by_impact_path=True,
            why_digest_ineligible=None,
            impact_path_reason="exploit_security_event",
            opportunity_score_v2=82,
            cause_status=cause,
            claim_polarities=polarity,
        )

    ada_no_market = event_opportunity_verdict.evaluate_opportunity(
        impact_path=path(event_impact_path_validator.CandidateRole.ECOSYSTEM_AFFECTED_ASSET.value),
        market_confirmation=strong_market,
        evidence_quality=strong_evidence,
        hypothesis=SimpleNamespace(impact_category="security_or_regulatory_shock"),
        score_components={
            "incident_confidence": 84,
            "market_reaction_confirmed": False,
            "causal_mechanism_confirmed": True,
        },
    )
    assert ada_no_market.watchlist_eligible is False
    assert "ecosystem_asset_requires_market_reaction" in ada_no_market.verdict_reason_codes
    assert ada_no_market.opportunity_score_final <= 64

    rune_confirmed = event_opportunity_verdict.evaluate_opportunity(
        impact_path=path(event_impact_path_validator.CandidateRole.DIRECT_SUBJECT.value),
        market_confirmation=strong_market,
        evidence_quality=strong_evidence,
        hypothesis=SimpleNamespace(impact_category="security_or_regulatory_shock"),
        score_components={
            "incident_confidence": 88,
            "market_reaction_confirmed": True,
            "causal_mechanism_confirmed": True,
        },
    )
    assert rune_confirmed.watchlist_eligible is True
    assert "confirmed_direct_incident" in rune_confirmed.verdict_reason_codes
    assert "confirmed_causal_incident_with_market_reaction" in rune_confirmed.verdict_reason_codes

    memecore_ruled_out = event_opportunity_verdict.evaluate_opportunity(
        impact_path=path(
            event_impact_path_validator.CandidateRole.DIRECT_SUBJECT.value,
            cause="ruled_out",
            polarity=("ruled_out",),
        ),
        market_confirmation=strong_market,
        evidence_quality=strong_evidence,
        hypothesis=SimpleNamespace(impact_category="security_or_regulatory_shock"),
        score_components={
            "incident_confidence": 80,
            "market_reaction_confirmed": True,
            "causal_mechanism_confirmed": False,
        },
    )
    assert memecore_ruled_out.opportunity_level == "local_only"
    assert memecore_ruled_out.watchlist_eligible is False
    assert memecore_ruled_out.why_local_only == "incident_cause_ruled_out"

    rumored = event_opportunity_verdict.evaluate_opportunity(
        impact_path=path(
            event_impact_path_validator.CandidateRole.DIRECT_SUBJECT.value,
            cause="suspected",
            polarity=("rumored",),
        ),
        market_confirmation=strong_market,
        evidence_quality=strong_evidence,
        hypothesis=SimpleNamespace(impact_category="security_or_regulatory_shock"),
        score_components={
            "incident_confidence": 58,
            "market_reaction_confirmed": True,
            "causal_mechanism_confirmed": False,
        },
    )
    assert rumored.watchlist_eligible is False
    assert rumored.opportunity_score_final <= 59
    assert "unconfirmed_incident_cause_cap" in rumored.verdict_reason_codes


def test_event_impact_hypothesis_watchlist_uses_validated_asset_not_first_candidate():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    now = datetime(2026, 6, 23, 12, 0, tzinfo=timezone.utc)

    def hypothesis(
        hypothesis_id,
        symbols,
        coin_ids,
        validated_asset=None,
        *,
        category="security_or_regulatory_shock",
        playbook="security_or_regulatory_shock",
        status="validated",
        scope="token",
        impact_path_reason="exploit_security_event",
    ):
        return event_impact_hypotheses.EventImpactHypothesis(
            hypothesis_id=hypothesis_id,
            event_cluster_id=f"cluster:{hypothesis_id}",
            event_type="news",
            external_asset="unknown",
            impact_category=category,
            candidate_sectors=("infrastructure_tokens",),
            candidate_symbols=tuple(symbols),
            candidate_coin_ids=tuple(coin_ids),
            crypto_candidate_assets=tuple(
                {"source": "taxonomy", "symbol": symbol, "coin_id": coin_id}
                for symbol, coin_id in zip(symbols, coin_ids)
            ) + ((dict(validated_asset, validated=True),) if validated_asset else ()),
            validated_candidate_assets=((dict(validated_asset, validated=True),) if validated_asset else ()),
            hypothesis_scope=scope,
            playbook_hint=playbook,
            confidence=0.82,
            hypothesis_score=78,
            validation_stage=event_impact_hypotheses.ValidationStage.IMPACT_PATH_VALIDATED.value if status == "validated" else event_impact_hypotheses.ValidationStage.SECTOR_HYPOTHESIS.value,
            status=status,
            validation_reasons=("identity_match links candidate to catalyst",) if validated_asset else (),
            evidence_quotes=(f"{validated_asset.get('coin_id', '')} {validated_asset.get('symbol', '')} exploit catalyst link",) if validated_asset else (),
            impact_path_reason=impact_path_reason if validated_asset else None,
            impact_path_type=impact_path_reason if validated_asset else None,
            impact_path_strength="strong" if validated_asset else None,
            candidate_role="direct_subject" if validated_asset else None,
            evidence_specificity_score=88.0 if validated_asset else None,
            digest_eligible_by_impact_path=True if validated_asset else None,
            opportunity_score_v2=82.0 if validated_asset else None,
            opportunity_score_components={"impact_path_strength": 95.0, "source_evidence_specificity": 88.0} if validated_asset else {},
        )

    rune = hypothesis(
        "hyp:rune",
        ("LINK", "PYTH", "RUNE"),
        ("chainlink", "pyth-network", "thorchain"),
        {"source": "hypothesis_search", "symbol": "RUNE", "coin_id": "thorchain"},
    )
    arb = hypothesis(
        "hyp:arb",
        ("TRUMP", "UMA", "GNO"),
        ("official-trump", "uma", "gnosis"),
        {"source": "hypothesis_search", "symbol": "ARB", "coin_id": "arbitrum"},
        category="prediction_market_infra",
        playbook="infrastructure_mention",
        impact_path_reason="direct_token_event",
    )
    chz = hypothesis(
        "hyp:chz",
        ("CHZ", "ARG", "BAR"),
        ("chiliz", "argentine-football-association-fan-token", "fc-barcelona-fan-token"),
        {"source": "hypothesis_search", "symbol": "CHZ", "coin_id": "chiliz"},
        category="sports_fan_proxy",
        playbook="fan_sports_event",
        impact_path_reason="fan_token_event",
    )
    missing = hypothesis("hyp:missing", ("LINK", "PYTH"), ("chainlink", "pyth-network"), None)
    sector = hypothesis(
        "hyp:sector",
        ("VELVET",),
        ("velvet",),
        None,
        category="rwa_preipo_proxy",
        playbook="rwa_preipo_proxy",
        status="hypothesis",
        scope="sector",
    )

    with tempfile.TemporaryDirectory() as tmp:
        cfg = event_watchlist.EventWatchlistConfig(enabled=True, state_path=Path(tmp) / "watchlist.jsonl")
        result = event_watchlist.refresh_hypothesis_watchlist((rune, arb, chz, missing, sector), cfg=cfg, now=now)
    by_event = {entry.event_id: entry for entry in result.entries}
    assert by_event["hyp:rune"].symbol == "RUNE"
    assert by_event["hyp:rune"].coin_id == "thorchain"
    assert by_event["hyp:rune"].latest_score_components["hypothesis_id"] == "hyp:rune"
    assert by_event["hyp:rune"].latest_score_components["impact_category"] == "security_or_regulatory_shock"
    assert by_event["hyp:rune"].latest_score_components["validation_stage"] == "impact_path_validated"
    assert by_event["hyp:rune"].latest_score_components["impact_path_reason"] == "exploit_security_event"
    assert by_event["hyp:rune"].latest_score_components["impact_path_type"] == "exploit_security_event"
    assert by_event["hyp:rune"].latest_score_components["impact_path_strength"] == "strong"
    assert by_event["hyp:rune"].latest_score_components["candidate_role"] == "direct_subject"
    assert by_event["hyp:rune"].latest_score_components["opportunity_score_v2"] == 82.0
    assert by_event["hyp:rune"].latest_score_components["digest_eligible_by_impact_path"] is True
    assert by_event["hyp:rune"].latest_score_components["hypothesis_score"] == 78
    assert by_event["hyp:rune"].latest_score_components["score"] == 78
    assert by_event["hyp:rune"].latest_score_components["validated_symbol"] == "RUNE"
    assert by_event["hyp:rune"].latest_score_components["validated_coin_id"] == "thorchain"
    assert by_event["hyp:rune"].latest_score_components["route_eligibility"] == "validated_hypothesis_digest_candidate"
    assert any("first_candidate=LINK validated=RUNE" in warning for warning in by_event["hyp:rune"].warnings)
    assert by_event["hyp:arb"].symbol == "ARB"
    assert by_event["hyp:arb"].coin_id == "arbitrum"
    assert any("first_candidate=TRUMP validated=ARB" in warning for warning in by_event["hyp:arb"].warnings)
    assert by_event["hyp:chz"].symbol == "CHZ"
    assert by_event["hyp:chz"].coin_id == "chiliz"
    assert by_event["hyp:missing"].symbol == "SECTOR"
    assert by_event["hyp:missing"].coin_id == "security_or_regulatory_shock"
    assert "validated_hypothesis_missing_validated_asset" in by_event["hyp:missing"].warnings
    assert by_event["hyp:sector"].symbol == "SECTOR"
    assert by_event["hyp:sector"].state == event_watchlist.EventWatchlistState.HYPOTHESIS.value
    assert by_event["hyp:sector"].latest_score_components["route_eligibility"] == "local_only"


def test_event_impact_hypothesis_external_entities_never_become_crypto_candidates():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses
    from crypto_rsi_scanner.event_alpha.radar.llm.extraction_models import (
        EventLLMCryptoAssetMention,
        EventLLMRawEventExtraction,
    )
    from crypto_rsi_scanner.event_alpha.radar.llm.extractor import EventLLMExtractionReportRow
    from crypto_rsi_scanner.event_core.models import EventDiscoveryResult, NormalizedEvent, RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    names = ("OpenAI", "Anthropic", "SpaceX", "Stripe", "Databricks", "Anduril", "Figma", "Fannie Mae", "Freddie Mac")
    body = " ".join(f"{name} pre-IPO exposure" for name in names)
    raw = RawDiscoveredEvent(
        raw_id="external-entities-only",
        provider="rss",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/external-entities",
        title="External pre-IPO proxy basket gets attention",
        body=body,
        raw_json={},
        source_confidence=0.90,
        content_hash="external-entities-only",
    )
    event = NormalizedEvent(
        event_id=raw.raw_id,
        raw_ids=(raw.raw_id,),
        event_name=raw.title,
        event_type="ipo_proxy",
        event_time=None,
        event_time_confidence=0.0,
        first_seen_time=now,
        source=raw.provider,
        source_urls=(raw.source_url,),
        external_asset="OpenAI",
        description=body,
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
        crypto_asset_mentions=tuple(
            EventLLMCryptoAssetMention(
                name=name,
                symbol=name.upper().replace(" ", ""),
                coin_id=name.lower().replace(" ", "-"),
                contract_address=None,
                mention_type="project_or_token",
                confidence=0.90,
            )
            for name in names
        ),
    )
    hypotheses = event_impact_hypotheses.generate_impact_hypotheses(
        EventDiscoveryResult((raw,), (event,), (), (), ()),
        extraction_rows=(EventLLMExtractionReportRow(raw_event=raw, extraction=extraction),),
        now=now,
        taxonomy={},
    )
    candidate_symbols = {symbol for hypothesis in hypotheses for symbol in hypothesis.candidate_symbols}
    crypto_symbols = {
        str(asset.get("symbol") or "")
        for hypothesis in hypotheses
        for asset in hypothesis.crypto_candidate_assets
    }
    rejected_reasons = {
        str(asset.get("rejection_reason") or "")
        for hypothesis in hypotheses
        for asset in hypothesis.rejected_candidate_assets
    }
    for name in names:
        symbol = name.upper().replace(" ", "")
        assert symbol not in candidate_symbols
        assert symbol not in crypto_symbols
    assert "external_entity_not_crypto_candidate" in rejected_reasons
