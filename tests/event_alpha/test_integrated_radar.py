"""Focused integrated-radar package architecture tests."""

from __future__ import annotations

import json
from collections import Counter
from tempfile import TemporaryDirectory


def test_integrated_radar_fixture_lane_counts_and_core_types_stay_stable():
    from crypto_rsi_scanner.event_alpha.artifacts import context as artifact_context
    from crypto_rsi_scanner.event_alpha.radar import integrated_radar

    with TemporaryDirectory() as tmp:
        context = artifact_context.context_from_profile(
            "fixture",
            run_mode="fixture",
            base_dir=tmp,
            artifact_namespace="pytest_integrated_radar",
        )
        result = integrated_radar.run_integrated_radar_cycle(
            context=context,
            fixture=True,
            observed_at="2026-06-15T16:00:00Z",
        )
        rows = [
            json.loads(line)
            for line in result.integrated_candidates_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        core_rows = [
            json.loads(line)
            for line in context.core_opportunity_store_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    assert Counter(row["opportunity_type"] for row in rows) == Counter(
        {
            "CONFIRMED_LONG_RESEARCH": 2,
            "DIAGNOSTIC": 2,
            "EARLY_LONG_RESEARCH": 1,
            "FADE_SHORT_REVIEW": 1,
            "RISK_ONLY": 2,
            "UNCONFIRMED_RESEARCH": 3,
        }
    )
    assert Counter(row["opportunity_type"] for row in core_rows) == Counter(
        {
            "CONFIRMED_LONG_RESEARCH": 2,
            "EARLY_LONG_RESEARCH": 1,
            "FADE_SHORT_REVIEW": 1,
            "RISK_ONLY": 2,
            "UNCONFIRMED_RESEARCH": 3,
        }
    )
    by_symbol = {row["symbol"]: row for row in rows}
    assert by_symbol["TESTPERP"]["opportunity_type"] == "CONFIRMED_LONG_RESEARCH"
    assert by_symbol["TESTFADE"]["opportunity_type"] == "FADE_SHORT_REVIEW"
    assert by_symbol["TESTLIST"]["opportunity_type"] == "EARLY_LONG_RESEARCH"
    assert by_symbol["SECTOR"]["opportunity_type"] == "DIAGNOSTIC"
    assert by_symbol["TESTPERP"]["normal_rsi_signal_written"] is False
    assert by_symbol["TESTFADE"]["triggered_fade_created"] is False

# --- Migrated from tests/test_indicators.py; keep standalone-compatible. ---
from tests.event_alpha import _api_helpers as _event_alpha_api_helpers

globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


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
    assert "HYPE tokenized stock SpaceX" in queries
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


def test_event_watchlist_refresh_tracks_escalations_and_suppresses_duplicates():
    import tempfile
    from dataclasses import replace
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
    from crypto_rsi_scanner.event_core.models import DiscoveredAsset, RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="watch-pumpx",
        provider="test",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/watch-pumpx",
        title="PumpX token offers synthetic exposure to SpaceX pre-IPO market",
        body="PumpX token holders can trade synthetic exposure to SpaceX before the IPO.",
        raw_json={
            "event": {
                "event_id": "watch-pumpx",
                "event_name": "PumpX SpaceX proxy watch",
                "event_type": "ipo_proxy",
                "event_time": "2026-06-20T13:30:00Z",
                "event_time_confidence": 0.90,
                "external_asset": "SpaceX",
                "confidence": 0.90,
                "description": "PumpX token holders can trade synthetic exposure to SpaceX before the IPO.",
            }
        },
        source_confidence=0.90,
        content_hash="watch-pumpx",
    )
    asset = DiscoveredAsset(
        coin_id="pumpx",
        symbol="PUMPX",
        name="PumpX",
        aliases=("pumpx token", "PumpX"),
    )
    discovery = event_discovery.run_discovery([raw], [asset], now=now)
    base = event_alerts.build_event_alert_candidates(discovery, now=now)[0]
    active_quality = {
        **base.score_components,
        "impact_path_type": "proxy_exposure",
        "impact_path_strength": "strong",
        "candidate_role": "proxy_instrument",
        "evidence_quality_score": 82,
        "source_class": "crypto_news",
        "evidence_specificity": "direct_value_capture",
        "market_confirmation_score": 58,
        "market_confirmation_level": "weak",
        "opportunity_score_final": 72,
        "opportunity_level": "validated_digest",
        "opportunity_verdict_reasons": ["fixture_valid_proxy_watch"],
        "why_local_only": "not_local_only",
        "why_not_watchlist": "needs_strong_market_confirmation",
        "manual_verification_items": ["verify proxy instrument and market confirmation"],
        "upgrade_requirements": ["needs_strong_market_confirmation"],
        "downgrade_warnings": [],
    }
    radar = replace(base, tier=event_alerts.EventAlertTier.RADAR_DIGEST, opportunity_score=60, score_components=active_quality)
    watch_quality = {**active_quality, "market_confirmation_score": 70, "market_confirmation_level": "moderate", "opportunity_score_final": 82, "opportunity_level": "watchlist", "why_not_watchlist": "already_watchlisted", "upgrade_requirements": []}
    watch = replace(base, tier=event_alerts.EventAlertTier.WATCHLIST, opportunity_score=75, score_components=watch_quality)

    with tempfile.TemporaryDirectory() as tmp:
        state_path = Path(tmp) / "watchlist.jsonl"
        cfg = event_watchlist.EventWatchlistConfig(enabled=True, state_path=state_path)
        first = event_watchlist.refresh_watchlist([radar], cfg=cfg, now=now)
        assert first.rows_written == 1
        assert first.entries[0].state == event_watchlist.EventWatchlistState.RADAR.value
        assert first.entries[0].should_alert is True
        assert first.entries[0].first_radar_at == now.isoformat()

        duplicate = event_watchlist.refresh_watchlist(
            [radar],
            cfg=cfg,
            now=datetime(2026, 6, 18, 13, 0, tzinfo=timezone.utc),
        )
        assert duplicate.entries[0].state == event_watchlist.EventWatchlistState.RADAR.value
        assert duplicate.entries[0].should_alert is False
        assert duplicate.entries[0].suppressed_reason == "duplicate state, no escalation"
        assert duplicate.entries[0].first_seen_at == first.entries[0].first_seen_at

        escalated = event_watchlist.refresh_watchlist(
            [watch],
            cfg=cfg,
            now=datetime(2026, 6, 18, 14, 0, tzinfo=timezone.utc),
        )
        assert escalated.entries[0].state == event_watchlist.EventWatchlistState.WATCHLIST.value
        assert escalated.entries[0].previous_state == event_watchlist.EventWatchlistState.RADAR.value
        assert escalated.entries[0].should_alert is True
        assert escalated.entries[0].highest_score == 75
        assert len(event_watchlist.load_watchlist(state_path, latest_only=False).entries) == 3


def test_event_watchlist_expiration_and_backward_compatible_reads():
    import json
    import tempfile
    from dataclasses import replace
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
    from crypto_rsi_scanner.event_core.models import DiscoveredAsset, RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="expired-proxy",
        provider="test",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/expired",
        title="PumpX token offers synthetic exposure to SpaceX pre-IPO market",
        body="PumpX token holders can trade synthetic exposure to SpaceX before the IPO.",
        raw_json={
            "event": {
                "event_id": "expired-proxy",
                "event_name": "Expired proxy event",
                "event_type": "ipo_proxy",
                "event_time": "2026-06-14T13:30:00Z",
                "event_time_confidence": 0.90,
                "external_asset": "SpaceX",
                "confidence": 0.90,
                "description": "PumpX token holders can trade synthetic exposure to SpaceX before the IPO.",
            }
        },
        source_confidence=0.90,
        content_hash="expired-proxy",
    )
    asset = DiscoveredAsset(coin_id="pumpx", symbol="PUMPX", name="PumpX", aliases=("pumpx token",))
    alert = event_alerts.build_event_alert_candidates(
        event_discovery.run_discovery([raw], [asset], now=now),
        now=now,
    )[0]
    alert = replace(alert, tier=event_alerts.EventAlertTier.RADAR_DIGEST, opportunity_score=60)

    with tempfile.TemporaryDirectory() as tmp:
        state_path = Path(tmp) / "watchlist.jsonl"
        cfg = event_watchlist.EventWatchlistConfig(
            enabled=True,
            state_path=state_path,
            expire_hours_after_event=72,
        )
        result = event_watchlist.refresh_watchlist([alert], cfg=cfg, now=now)
        assert result.entries[0].state == event_watchlist.EventWatchlistState.EXPIRED.value
        assert result.entries[0].should_alert is False
        assert result.entries[0].suppressed_reason == "terminal non-alert state"

        old_path = Path(tmp) / "old-watchlist.jsonl"
        old_path.write_text(
            json.dumps({
                "row_type": "event_watchlist_state",
                "key": "old|coin|rel||",
                "event_id": "old",
                "coin_id": "coin",
                "symbol": "OLD",
                "relationship_type": "proxy_attention",
                "state": "RADAR",
                "last_seen_at": now.isoformat(),
                "latest_score": 61,
            }) + "\nnot-json\n",
            encoding="utf-8",
        )
        loaded = event_watchlist.load_watchlist(old_path)
        assert loaded.rows_read == 1
        assert loaded.entries[0].state == event_watchlist.EventWatchlistState.RADAR.value
        assert loaded.entries[0].highest_score == 61


def test_event_alpha_router_routes_watchlist_escalations_safely():
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.playbooks as event_playbooks
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    def row(
        symbol,
        state,
        playbook,
        *,
        should_alert=True,
        score=75,
        suppressed_reason=None,
    ):
        quality = {
            "impact_path_type": "proxy_exposure",
            "impact_path_strength": "strong",
            "candidate_role": "proxy_instrument",
            "evidence_quality_score": 78,
            "source_class": "crypto_news",
            "evidence_specificity": "direct_value_capture",
            "market_confirmation_score": 62,
            "market_confirmation_level": "moderate",
            "opportunity_score_final": score,
            "opportunity_level": "high_priority"
            if state in {"HIGH_PRIORITY", "ARMED", "EVENT_PASSED"}
            else "watchlist",
            "opportunity_verdict_reasons": ["test_quality_fixture"],
            "why_local_only": "not_local_only",
            "why_not_watchlist": "already_watchlisted",
            "manual_verification_items": ["verify catalyst and market confirmation"],
            "upgrade_requirements": [],
            "downgrade_warnings": ["none"],
        }
        return event_watchlist.EventWatchlistEntry(
            schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
            row_type="event_watchlist_state",
            key=f"{symbol}|coin|rel|asset|time",
            cluster_id="spacex|ipo_proxy|2026-06-20",
            event_id=f"{symbol}-event",
            coin_id=symbol.lower(),
            symbol=symbol,
            relationship_type="proxy_exposure",
            external_asset="SpaceX",
            event_time="2026-06-20T13:30:00+00:00",
            state=state,
            previous_state="RADAR",
            first_seen_at="2026-06-18T12:00:00+00:00",
            last_seen_at="2026-06-18T13:00:00+00:00",
            source_count=1,
            highest_score=score,
            latest_score=score,
            latest_tier=state,
            latest_event_name=f"{symbol} SpaceX event",
            latest_source="test",
            latest_playbook_type=playbook,
            latest_playbook_score=score,
            latest_playbook_action="watchlist",
            latest_score_components=quality,
            should_alert=should_alert,
            suppressed_reason=suppressed_reason,
        )

    read = event_watchlist.EventWatchlistReadResult(
        state_path=Path("watchlist.jsonl"),
        rows_read=6,
        latest_only=True,
        entries=[
            row(
                "PFADE",
                event_watchlist.EventWatchlistState.TRIGGERED_FADE.value,
                event_playbooks.EventPlaybookType.PROXY_FADE.value,
                score=95,
            ),
            row(
                "BADTRIG",
                event_watchlist.EventWatchlistState.TRIGGERED_FADE.value,
                event_playbooks.EventPlaybookType.DIRECT_EVENT.value,
                score=90,
            ),
            row(
                "ATTN",
                event_watchlist.EventWatchlistState.WATCHLIST.value,
                event_playbooks.EventPlaybookType.PROXY_ATTENTION.value,
                score=74,
            ),
            row(
                "DUP",
                event_watchlist.EventWatchlistState.WATCHLIST.value,
                event_playbooks.EventPlaybookType.PROXY_ATTENTION.value,
                should_alert=False,
                suppressed_reason="duplicate state, no escalation",
            ),
            row(
                "ANOM",
                event_watchlist.EventWatchlistState.RAW_EVIDENCE.value,
                event_playbooks.EventPlaybookType.MARKET_ANOMALY.value,
                should_alert=False,
            ),
            row(
                "NOISE",
                event_watchlist.EventWatchlistState.RADAR.value,
                event_playbooks.EventPlaybookType.SOURCE_NOISE_CONTROL.value,
            ),
        ],
    )
    result = event_alpha_router.route_watchlist(
        read,
        cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True),
    )
    by_symbol = {decision.entry.symbol: decision for decision in result.decisions}
    assert by_symbol["PFADE"].route == event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH
    assert by_symbol["PFADE"].alertable is True
    assert by_symbol["BADTRIG"].route == event_alpha_router.EventAlphaRoute.LOCAL_REPORT
    assert by_symbol["BADTRIG"].alertable is False
    assert "non-proxy playbook cannot route triggered fade" in by_symbol["BADTRIG"].warnings
    assert by_symbol["ATTN"].route == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST
    assert by_symbol["DUP"].route == event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE
    assert by_symbol["ANOM"].route == event_alpha_router.EventAlphaRoute.STORE_ONLY
    assert by_symbol["NOISE"].route == event_alpha_router.EventAlphaRoute.STORE_ONLY

    text = event_alpha_router.format_router_report(result)
    assert "EVENT ALPHA ROUTER REPORT" in text
    assert "TRIGGERED_FADE_RESEARCH" in text
    assert "SUPPRESS_DUPLICATE" in text
    assert "no sends, trades, or paper rows" in text
    routed_digest = event_alpha_router.format_routed_telegram_digest(result.alertable_decisions)
    assert "Event Alpha routed research alerts" in routed_digest
    assert "PFADE" in routed_digest
    assert "ATTN" in routed_digest
    assert "BADTRIG" not in routed_digest
    assert "alert_id: ea:" in text
    assert "card_id: card_" in text
    assert "FEEDBACK_TARGET=ea:" in text
    assert "alert_id=ea:" in routed_digest


def test_event_alpha_router_daily_digest_for_validated_impact_hypotheses():
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    def entry(
        symbol,
        score=78,
        *,
        should_alert=True,
        impact_category="security_or_regulatory_shock",
        playbook="security_or_regulatory_shock",
        external_asset="unknown",
        evidence=None,
        validation_stage="impact_path_validated",
        impact_path_reason="exploit_security_event",
        impact_path_type=None,
        impact_path_strength="strong",
        candidate_role="direct_subject",
        opportunity_score_v2=None,
        opportunity_score_final=None,
        opportunity_level="validated_digest",
        market_confirmation_level="moderate",
        digest_eligible_by_impact_path=True,
        state=None,
    ):
        impact_path_type = impact_path_type or impact_path_reason
        opportunity_score_v2 = opportunity_score_v2 if opportunity_score_v2 is not None else score
        opportunity_score_final = opportunity_score_final if opportunity_score_final is not None else opportunity_score_v2
        evidence = evidence or (f"{symbol} {symbol.lower()} exploit catalyst link",)
        return event_watchlist.EventWatchlistEntry(
            schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
            row_type="event_watchlist_state",
            key=f"hypothesis|cluster:{symbol}|{impact_category}",
            cluster_id=f"cluster:{symbol}",
            event_id=f"hyp:{symbol}",
            coin_id=symbol.lower(),
            symbol=symbol,
            relationship_type="impact_hypothesis",
            external_asset=external_asset,
            event_time=None,
            state=state or event_watchlist.EventWatchlistState.RADAR.value,
            previous_state=event_watchlist.EventWatchlistState.HYPOTHESIS.value,
            first_seen_at="2026-06-23T12:00:00+00:00",
            last_seen_at="2026-06-23T12:30:00+00:00",
            source_count=1,
            highest_score=score,
            latest_score=score,
            latest_tier="HIGH_PRIORITY_WATCH" if state == event_watchlist.EventWatchlistState.HIGH_PRIORITY.value else "RADAR_DIGEST",
            latest_event_name=f"{symbol} validated impact hypothesis",
            latest_source="impact_hypothesis",
            latest_playbook_type=playbook,
            latest_effective_playbook_type=playbook,
            latest_playbook_score=score,
            latest_playbook_action="high_priority_watch" if state == event_watchlist.EventWatchlistState.HIGH_PRIORITY.value else "radar_digest",
            latest_score_components={
                "hypothesis_id": f"hyp:{symbol}",
                "impact_category": impact_category,
                "validation_stage": validation_stage,
                "impact_path_reason": impact_path_reason,
                "impact_path_type": impact_path_type,
                "impact_path_strength": impact_path_strength,
                "candidate_role": candidate_role,
                "evidence_specificity_score": 88,
                "digest_eligible_by_impact_path": digest_eligible_by_impact_path,
                "opportunity_score_v2": opportunity_score_v2,
                "opportunity_score_final": opportunity_score_final,
                "opportunity_level": opportunity_level,
                "market_confirmation_score": 50,
                "market_confirmation_level": market_confirmation_level,
                "evidence_quality_score": 82,
                "source_class": "crypto_news",
                "evidence_specificity": "direct_token_mechanism",
                "opportunity_verdict_reasons": ["direct_token_event_with_strong_evidence"],
                "manual_verification_items": ["verify independent source"],
                "opportunity_score_components": {
                    "impact_path_strength": 95 if impact_path_strength == "strong" else 35,
                    "source_evidence_specificity": 88,
                    "market_confirmation": 50,
                },
                "hypothesis_score": score,
                "score": score,
                "playbook_type": playbook,
                "effective_playbook_type": playbook,
                "validated_symbol": symbol,
                "validated_coin_id": symbol.lower(),
                "validated_asset": {"symbol": symbol, "coin_id": symbol.lower(), "name": symbol, "validated": True},
                "evidence_quotes": list(evidence),
                "validation_reasons": list(evidence),
            },
            material_change_reasons=("hypothesis_validated",),
            should_alert=should_alert,
        )

    def proxy_entry(symbol, score=72):
        quality = {
            "impact_path_type": "proxy_exposure",
            "impact_path_strength": "strong",
            "candidate_role": "proxy_instrument",
            "evidence_quality_score": 78,
            "source_class": "crypto_news",
            "evidence_specificity": "direct_value_capture",
            "market_confirmation_score": 55,
            "market_confirmation_level": "moderate",
            "opportunity_score_final": score,
            "opportunity_level": "watchlist",
            "opportunity_verdict_reasons": ["proxy_impact_path_explained"],
            "why_local_only": "not_local_only",
            "why_not_watchlist": "already_watchlisted",
            "manual_verification_items": ["verify market confirmation"],
            "upgrade_requirements": [],
            "downgrade_warnings": [],
        }
        return event_watchlist.EventWatchlistEntry(
            schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
            row_type="event_watchlist_state",
            key=f"proxy|cluster:{symbol}|proxy_attention",
            cluster_id=f"cluster:{symbol}",
            event_id=f"proxy:{symbol}",
            coin_id=symbol.lower(),
            symbol=symbol,
            relationship_type="proxy_attention",
            external_asset="SpaceX",
            event_time=None,
            state=event_watchlist.EventWatchlistState.RADAR.value,
            previous_state=event_watchlist.EventWatchlistState.RAW_EVIDENCE.value,
            first_seen_at="2026-06-23T12:00:00+00:00",
            last_seen_at="2026-06-23T12:30:00+00:00",
            source_count=2,
            highest_score=score,
            latest_score=score,
            latest_tier="RADAR_DIGEST",
            latest_event_name=f"{symbol} proxy candidate",
            latest_source="test",
            latest_playbook_type="proxy_attention",
            latest_playbook_score=score,
            latest_playbook_action="radar_digest",
            latest_score_components=quality,
            should_alert=True,
        )

    read = event_watchlist.EventWatchlistReadResult(
        state_path=Path("watchlist.jsonl"),
        rows_read=4,
        latest_only=True,
        entries=[
            entry("RUNE", 90, evidence=("THORChain RUNE faces an exploit and security incident investigation.",)),
            entry(
                "ZEC",
                82,
                impact_category="listing_liquidity_event",
                playbook="listing_volatility",
                evidence=("Zcash ZEC miner completes a Nasdaq listing and public market access changes.",),
                impact_path_reason="listing_liquidity_event",
            ),
            entry(
                "BTC",
                88,
                impact_category="political_meme_proxy",
                playbook="political_meme_event",
                evidence=("Bitcoin quantum-computing policy debate drew Trump comments.",),
                validation_stage="catalyst_link_validated",
                impact_path_reason="generic_policy_only",
                impact_path_type="technology_risk",
                impact_path_strength="weak",
                candidate_role="macro_affected_asset",
                opportunity_score_v2=76,
                digest_eligible_by_impact_path=False,
            ),
            entry("LOW", 50, evidence=("LOW token exploit catalyst link.",)),
            proxy_entry("VELVET", 72),
            entry("SECTOR", 70),
        ],
    )
    enabled = event_alpha_router.route_watchlist(
        read,
        cfg=event_alpha_router.EventAlphaRouterConfig(
            enabled=True,
            validated_hypothesis_digest_enabled=True,
            max_validated_hypothesis_digest_items=1,
            max_digest_items=2,
        ),
    )
    by_symbol = {decision.entry.symbol: decision for decision in enabled.decisions}
    assert by_symbol["RUNE"].route == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST
    assert by_symbol["RUNE"].lane == event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST
    assert by_symbol["RUNE"].alertable is True
    assert "digest opportunity verdict" in by_symbol["RUNE"].reason
    assert by_symbol["ZEC"].route == event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE
    assert by_symbol["ZEC"].alertable is False
    assert by_symbol["ZEC"].reason == "Validated impact hypothesis digest cap reached for this run."
    assert by_symbol["BTC"].route == event_alpha_router.EventAlphaRoute.STORE_ONLY
    assert by_symbol["BTC"].alertable is False
    assert "impact_path_not_digest_eligible" in by_symbol["BTC"].reason
    assert by_symbol["LOW"].route == event_alpha_router.EventAlphaRoute.STORE_ONLY
    assert by_symbol["LOW"].alertable is False
    assert "opportunity_score_final_below_threshold" in by_symbol["LOW"].reason
    assert by_symbol["VELVET"].route == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST
    assert by_symbol["VELVET"].alertable is True
    assert by_symbol["SECTOR"].alertable is False
    assert by_symbol["SECTOR"].route != event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH

    canonical = event_alpha_router.route_watchlist(
        event_watchlist.EventWatchlistReadResult(
            state_path=Path("watchlist.jsonl"),
            rows_read=2,
            latest_only=True,
            entries=[
                entry("AAVE", 72, opportunity_score_v2=64, opportunity_score_final=72, opportunity_level="validated_digest"),
                entry("VELVET", 96, opportunity_score_final=96, opportunity_level="high_priority", impact_category="tokenized_stock_venue", playbook="proxy_attention", impact_path_reason="venue_value_capture", impact_path_type="venue_value_capture", candidate_role="proxy_venue", external_asset="SpaceX", state=event_watchlist.EventWatchlistState.HIGH_PRIORITY.value),
                entry("BAD", 88, opportunity_score_v2=88, opportunity_score_final=40, opportunity_level="local_only"),
            ],
        ),
        cfg=event_alpha_router.EventAlphaRouterConfig(
            enabled=True,
            validated_hypothesis_digest_enabled=True,
            max_validated_hypothesis_digest_items=5,
        ),
    )
    canonical_by_symbol = {decision.entry.symbol: decision for decision in canonical.decisions}
    assert canonical_by_symbol["AAVE"].route == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST
    assert canonical_by_symbol["AAVE"].alertable is True
    assert canonical_by_symbol["AAVE"].routing_score_used == 72
    assert canonical_by_symbol["AAVE"].routing_score_source == "opportunity_score_final"
    assert canonical_by_symbol["AAVE"].routing_verdict_used == "validated_digest"
    assert canonical_by_symbol["VELVET"].route == event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH
    assert canonical_by_symbol["VELVET"].alertable is True
    assert "Validated impact hypothesis reached high-priority opportunity verdict" in canonical_by_symbol["VELVET"].reason
    assert canonical_by_symbol["BAD"].route == event_alpha_router.EventAlphaRoute.STORE_ONLY
    assert canonical_by_symbol["BAD"].alertable is False
    canonical_report = event_alpha_router.format_router_report(canonical)
    assert "source=opportunity_score_final value=72" in canonical_report
    assert "opportunity_score_v2_below_threshold" not in canonical_report

    disabled = event_alpha_router.route_watchlist(
        event_watchlist.EventWatchlistReadResult(
            state_path=Path("watchlist.jsonl"),
            rows_read=1,
            latest_only=True,
            entries=[entry("RUNE", 90, evidence=("THORChain RUNE exploit catalyst link.",))],
        ),
        cfg=event_alpha_router.EventAlphaRouterConfig(
            enabled=True,
            validated_hypothesis_digest_enabled=False,
        ),
    )
    only = disabled.decisions[0]
    assert only.route == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST
    assert only.alertable is False

    message = event_alpha_router.format_routed_telegram_digest([by_symbol["RUNE"]], profile="notify_llm")
    assert "Validated impact hypothesis" in message
    assert "Not a trade signal" in message
    assert "not a calibrated strategy" in message

    card = event_research_cards.render_research_card(
        "RUNE",
        watchlist_entries=[by_symbol["RUNE"].entry],
        route_decisions=[by_symbol["RUNE"]],
    )
    assert card.found is True
    assert "## Impact Hypothesis Context" in card.markdown
    assert "Validated asset: RUNE/rune" in card.markdown
    assert "Final opportunity verdict" in card.markdown
    assert "Evidence quality" in card.markdown
    assert "Market confirmation" in card.markdown
    assert "Impact path reason: exploit_security_event" in card.markdown
    assert "Quality gate: passed" in card.markdown
    assert "not a calibrated strategy or trade signal" in card.markdown
    assert "OPENAI_API_KEY" not in card.markdown
    assert "TELEGRAM_BOT_TOKEN" not in card.markdown


def test_event_alpha_near_miss_refreshes_market_context_without_triggering_fade():
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses
    import crypto_rsi_scanner.event_alpha.radar.near_miss as event_near_miss
    import crypto_rsi_scanner.event_alpha.artifacts.opportunity_audit as event_opportunity_audit
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    base_components = {
        "validated_symbol": "ENA",
        "validated_coin_id": "ethena",
        "impact_category": "security_or_regulatory_shock",
        "playbook_type": "security_or_regulatory_shock",
        "impact_path_type": "exploit_security_event",
        "impact_path_strength": "strong",
        "candidate_role": "direct_subject",
        "source_class": "crypto_news",
        "evidence_specificity": "direct_token_mechanism",
        "source_quality": 82,
        "evidence_quality_score": 82,
        "market_confirmation": 15,
        "market_confirmation_score": 15,
        "market_confirmation_level": "weak",
        "opportunity_score_final": 64,
        "opportunity_level": "exploratory",
        "missing_requirements": ["market_confirmation"],
        "why_not_watchlist": "market_confirmation",
        "opportunity_score_v2": 80,
    }
    hypothesis = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:ena",
        event_cluster_id="cluster:ena",
        event_type="security_event",
        external_asset="Ethena",
        impact_category="security_or_regulatory_shock",
        candidate_sectors=("security",),
        candidate_symbols=("ENA",),
        candidate_coin_ids=("ethena",),
        validated_candidate_assets=({"symbol": "ENA", "coin_id": "ethena", "validated": True},),
        crypto_candidate_assets=({"symbol": "ENA", "coin_id": "ethena", "accepted": True},),
        playbook_hint="security_or_regulatory_shock",
        confidence=0.86,
        hypothesis_score=82,
        score_components=base_components,
        validation_stage="impact_path_validated",
        status="validated",
        evidence_quotes=("ENA exploit security event was confirmed.",),
        impact_path_reason="exploit_security_event",
        impact_path_type="exploit_security_event",
        impact_path_strength="strong",
        candidate_role="direct_subject",
        evidence_quality_score=82,
        source_class="crypto_news",
        evidence_specificity="direct_token_mechanism",
        market_confirmation_score=15,
        market_confirmation_level="weak",
        market_confirmation_missing_fields=("market_confirmation",),
        opportunity_score_v2=80,
        opportunity_score_final=64,
        opportunity_level="exploratory",
        missing_requirements=("market_confirmation",),
        why_not_watchlist="market_confirmation",
    )
    near = event_near_miss.detect_near_miss_rows((hypothesis,), cfg=event_near_miss.EventNearMissConfig())
    assert len(near) == 1
    assert near[0].symbol == "ENA"
    assert near[0].core_opportunity_id
    assert "targeted_market_refresh" in near[0].recommended_refresh_actions
    queue = event_near_miss.targeted_market_refresh_queue((hypothesis,), cfg=event_near_miss.EventNearMissConfig())
    assert queue[0].refresh_id == f"refresh:{near[0].core_opportunity_id}"
    duplicate_hypothesis = __import__("dataclasses").replace(
        hypothesis,
        hypothesis_id="hyp:ena:support",
        opportunity_score_final=63,
        score_components={**hypothesis.score_components, "opportunity_score_final": 63},
    )
    deduped_queue = event_near_miss.targeted_market_refresh_queue(
        (hypothesis, duplicate_hypothesis),
        cfg=event_near_miss.EventNearMissConfig(),
    )
    assert len(deduped_queue) == 1
    assert deduped_queue[0].core_opportunity_id == near[0].core_opportunity_id
    assert queue[0].reason == "market_confirmation"

    generic = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:generic",
        event_cluster_id="cluster:generic",
        event_type="macro",
        external_asset="Bitcoin World",
        impact_category="market_anomaly_unknown",
        candidate_sectors=("macro",),
        candidate_symbols=("BTC",),
        candidate_coin_ids=("bitcoin",),
        score_components={
            **base_components,
            "validated_symbol": "BTC",
            "validated_coin_id": "bitcoin",
            "impact_path_type": "generic_cooccurrence_only",
            "candidate_role": "generic_mention",
            "opportunity_score_final": 64,
            "opportunity_level": "exploratory",
        },
        impact_path_type="generic_cooccurrence_only",
        candidate_role="generic_mention",
        opportunity_score_final=64,
        opportunity_level="exploratory",
    )
    assert event_near_miss.detect_near_miss_rows((generic,), cfg=event_near_miss.EventNearMissConfig()) == ()

    stale_velvet = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:velvet-stale",
        event_cluster_id="cluster:spacex",
        event_type="ipo_proxy",
        external_asset="SpaceX",
        impact_category="tokenized_stock_venue",
        candidate_sectors=("rwa",),
        candidate_symbols=("VELVET",),
        candidate_coin_ids=("velvet",),
        validated_candidate_assets=({"symbol": "VELVET", "coin_id": "velvet", "validated": True},),
        crypto_candidate_assets=({"symbol": "VELVET", "coin_id": "velvet", "accepted": True},),
        playbook_hint="proxy_attention",
        confidence=0.91,
        hypothesis_score=90,
        score_components={
            **base_components,
            "validated_symbol": "VELVET",
            "validated_coin_id": "velvet",
            "impact_category": "tokenized_stock_venue",
            "playbook_type": "proxy_attention",
            "impact_path_type": "venue_value_capture",
            "candidate_role": "proxy_venue",
            "external_asset": "SpaceX",
            "market_confirmation": 49,
            "market_confirmation_score": 49,
            "market_confirmation_level": "weak",
            "market_context_freshness_status": "stale",
            "market_context_freshness_cap_applied": True,
            "market_context_timestamp": "2026-06-14T00:00:00+00:00",
            "market_confirmation_warnings": ("market_context_stale_capped",),
            "market_confirmation_missing_fields": ("needs_fresh_market_confirmation",),
            "opportunity_score_final": 70,
            "opportunity_level": "validated_digest",
            "missing_requirements": ("needs_fresh_market_confirmation",),
            "why_not_watchlist": "needs_fresh_market_confirmation",
            "opportunity_score_v2": 88,
        },
        validation_stage="impact_path_validated",
        status="validated",
        evidence_quotes=("VELVET gives users SpaceX pre-IPO exposure.",),
        impact_path_reason="venue_value_capture",
        impact_path_type="venue_value_capture",
        impact_path_strength="strong",
        candidate_role="proxy_venue",
        evidence_quality_score=86,
        source_class="crypto_native",
        evidence_specificity="asset_and_catalyst",
        market_confirmation_score=49,
        market_confirmation_level="weak",
        market_confirmation_warnings=("market_context_stale_capped",),
        market_confirmation_missing_fields=("needs_fresh_market_confirmation",),
        market_context_timestamp="2026-06-14T00:00:00+00:00",
        market_context_freshness_status="stale",
        market_context_freshness_cap_applied=True,
        opportunity_score_v2=88,
        opportunity_score_final=70,
        opportunity_level="validated_digest",
        missing_requirements=("needs_fresh_market_confirmation",),
        why_not_watchlist="needs_fresh_market_confirmation",
    )
    stale_near = event_near_miss.detect_near_miss_rows((stale_velvet,), cfg=event_near_miss.EventNearMissConfig())
    assert len(stale_near) == 1
    assert stale_near[0].opportunity_level_before == "validated_digest"
    assert event_near_miss.is_upgrade_candidate(stale_near[0]) is True
    near_section, upgrade_section = event_near_miss.split_near_miss_candidates((*near, *stale_near))
    assert [item.symbol for item in near_section] == ["ENA"]
    assert [item.symbol for item in upgrade_section] == ["VELVET"]
    split_report = event_near_miss.format_near_miss_report((*near, *stale_near), profile="fixture")
    assert "## Near-Miss Candidates" in split_report
    assert "## Upgrade Candidates" in split_report
    assert "- ENA/ethena" in split_report.split("## Upgrade Candidates", 1)[0]
    assert "- VELVET/velvet" in split_report.split("## Upgrade Candidates", 1)[1]
    assert "targeted_market_refresh" in stale_near[0].recommended_refresh_actions
    stale_queue = event_near_miss.targeted_market_refresh_queue((stale_velvet,), cfg=event_near_miss.EventNearMissConfig())
    assert stale_queue[0].symbol == "VELVET"
    probe = event_near_miss.refresh_market_context_for_candidates(
        stale_queue,
        market_rows=({
            "coin_id": "velvet",
            "symbol": "VELVET",
            "return_24h": 82,
            "return_72h": 148,
            "volume_zscore_24h": 5.4,
            "volume_to_market_cap": 0.44,
            "timestamp": "2026-06-15T15:30:00+00:00",
            "source": "fixture_targeted_market_refresh",
        },),
        now=datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc),
    )
    assert probe[0]["success"] is True
    assert probe[0]["market_context_after"]["data_quality"] == "fresh"

    class FailingProvider:
        name = "failing_provider"

        def fetch_market_rows(self, coin_ids, *, max_assets=50):
            raise RuntimeError("boom")

    failed_probe = event_near_miss.refresh_market_context_for_candidates(
        stale_queue,
        targeted_market_provider=FailingProvider(),
        now=datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc),
    )
    assert failed_probe[0]["success"] is False
    assert failed_probe[0]["error_class"] == "RuntimeError"

    refreshed = event_near_miss.refresh_near_miss_hypotheses(
        (hypothesis,),
        cfg=event_near_miss.EventNearMissConfig(market_refresh_enabled=True, max_market_refresh_assets=5),
        market_rows=({
            "coin_id": "ethena",
            "symbol": "ENA",
            "return_24h": 58,
            "return_72h": 96,
            "volume_zscore_24h": 4.5,
            "volume_to_market_cap": 0.42,
            "timestamp": "2026-06-26T10:00:00+00:00",
            "source": "fixture_market",
        },),
        now=datetime(2026, 6, 26, 11, 0, tzinfo=timezone.utc),
    )
    updated = refreshed.hypotheses[0]
    refreshed_near = refreshed.near_misses[0]
    assert refreshed_near.market_refresh_attempted is True
    assert refreshed_near.market_refresh_success is True
    assert refreshed_near.market_refresh_provider == "cycle_rows"
    assert refreshed_near.refresh_upgrade_status in {"upgraded", "improved_score"}
    assert refreshed_near.opportunity_score_after > refreshed_near.opportunity_score_before
    assert updated.opportunity_level in {"validated_digest", "watchlist", "high_priority"}
    assert updated.opportunity_score_final >= 65
    assert updated.market_context_data_quality == "fresh"
    assert updated.opportunity_level_before_refresh == "exploratory"
    assert updated.opportunity_level_after_refresh == updated.opportunity_level
    assert updated.market_confirmation_after_refresh == updated.market_confirmation_score
    assert updated.score_components["final_opportunity_level"] == updated.opportunity_level
    assert updated.score_components["final_opportunity_score"] == updated.opportunity_score_final
    assert updated.score_components["final_verdict_source"] == "market_refresh"
    assert updated.score_components["market_data_freshness"] == "fresh"
    assert updated.score_components["market_reaction_confirmation"] in {"moderate", "strong"}
    assert updated.score_components["opportunity_score_v2"] == 80
    assert "TRIGGERED_FADE" not in event_near_miss.format_near_miss_report(refreshed.near_misses)

    report = event_near_miss.format_near_miss_report(refreshed.near_misses, profile="quality_validation")
    assert "ENA/ethena" in report
    assert "market_refresh: attempted=true success=true" in report
    assert "provider=cycle_rows" in report

    hypothesis_row = {
        **updated.__dict__,
        "profile": "quality_validation",
        "run_mode": "notification_burn_in",
        "artifact_namespace": "quality_validation",
    }
    daily = event_alpha_daily_brief.build_daily_brief(
        hypothesis_rows=[hypothesis_row],
        requested_profile="quality_validation",
        artifact_namespace="quality_validation",
    )
    assert "## Near-Miss Candidates" in daily
    assert "ENA/ethena" in daily

    audit = event_opportunity_audit.format_opportunity_audit("ENA", hypotheses=[updated], profile="quality_validation")
    assert "## Near-miss status" in audit
    assert "status: targeted refresh previously applied" in audit
    assert "targeted refresh:" in audit
    assert "market_confirmation=" in audit

    entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="hypothesis|cluster:ena|security_or_regulatory_shock",
        cluster_id="cluster:ena",
        event_id="hyp:ena",
        coin_id="ethena",
        symbol="ENA",
        relationship_type="impact_hypothesis",
        external_asset="Ethena",
        event_time=None,
        state=event_watchlist.EventWatchlistState.RADAR.value,
        previous_state=event_watchlist.EventWatchlistState.HYPOTHESIS.value,
        first_seen_at="2026-06-26T10:00:00+00:00",
        last_seen_at="2026-06-26T11:00:00+00:00",
        latest_score=80,
        latest_tier="RADAR_DIGEST",
        latest_event_name="ENA refreshed near miss",
        latest_source="fixture",
        latest_score_components=updated.score_components,
        opportunity_score_final=updated.opportunity_score_final,
        opportunity_level=updated.opportunity_level,
        should_alert=True,
    )
    routed = event_alpha_router.route_watchlist(
        event_watchlist.EventWatchlistReadResult(
            state_path=Path("watchlist.jsonl"),
            rows_read=1,
            latest_only=True,
            entries=[entry],
        ),
        cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True, validated_hypothesis_digest_enabled=True),
    )
    assert routed.decisions[0].route != event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH


def test_event_alpha_router_routes_material_changes_with_lanes():
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.playbooks as event_playbooks
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    def row(symbol, *, reasons=(), score_jump=0, state=None, playbook=None, should_alert=True, history=None):
        quality = {
            "impact_path_type": "proxy_exposure",
            "impact_path_strength": "strong",
            "candidate_role": "proxy_instrument",
            "evidence_quality_score": 78,
            "source_class": "crypto_news",
            "evidence_specificity": "direct_value_capture",
            "market_confirmation_score": 62,
            "market_confirmation_level": "moderate",
            "opportunity_score_final": 80,
            "opportunity_level": "watchlist",
            "opportunity_verdict_reasons": ["test_quality_fixture"],
            "why_local_only": "not_local_only",
            "why_not_watchlist": "already_watchlisted",
            "manual_verification_items": ["verify catalyst and market confirmation"],
            "upgrade_requirements": [],
            "downgrade_warnings": [],
        }
        return event_watchlist.EventWatchlistEntry(
            schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
            row_type="event_watchlist_state",
            key=f"{symbol}|coin|rel",
            cluster_id="spacex|ipo_proxy|2026-06-20",
            event_id=f"{symbol}-event",
            coin_id=symbol.lower(),
            symbol=symbol,
            relationship_type="proxy_attention",
            external_asset="SpaceX",
            event_time="2026-06-20T13:30:00+00:00",
            state=state or event_watchlist.EventWatchlistState.WATCHLIST.value,
            previous_state=state or event_watchlist.EventWatchlistState.WATCHLIST.value,
            first_seen_at="2026-06-18T12:00:00+00:00",
            last_seen_at="2026-06-18T14:00:00+00:00",
            source_count=2,
            highest_score=80,
            latest_score=80,
            latest_tier="WATCHLIST",
            latest_event_name=f"{symbol} SpaceX event",
            latest_source="test",
            latest_playbook_type=playbook or event_playbooks.EventPlaybookType.PROXY_ATTENTION.value,
            latest_playbook_score=80,
            latest_playbook_action="watchlist",
            latest_score_components=quality,
            should_alert=should_alert,
            score_jump=score_jump,
            material_change_reasons=tuple(reasons),
            alert_history=history or [
                {"observed_at": "2026-06-18T12:00:00+00:00", "should_alert": False},
                {"observed_at": "2026-06-18T14:00:00+00:00", "should_alert": should_alert},
            ],
            suppressed_reason=None if should_alert else "duplicate state, no escalation",
        )

    read = event_watchlist.EventWatchlistReadResult(
        state_path=Path("watchlist.jsonl"),
        rows_read=5,
        latest_only=True,
        entries=[
            row("JUMP", reasons=("score_jump",), score_jump=15),
            row("SRC", reasons=("new_independent_source",)),
            row("TIME", reasons=("event_time_upgrade",)),
            row(
                "COOL",
                reasons=("score_jump",),
                score_jump=15,
                history=[
                    {"observed_at": "2026-06-18T13:00:00+00:00", "should_alert": True},
                    {"observed_at": "2026-06-18T14:00:00+00:00", "should_alert": True},
                ],
            ),
            row("DUP", should_alert=False),
            row(
                "TRIG",
                state=event_watchlist.EventWatchlistState.TRIGGERED_FADE.value,
                playbook=event_playbooks.EventPlaybookType.PROXY_FADE.value,
                should_alert=False,
            ),
        ],
    )
    result = event_alpha_router.route_watchlist(read, cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True))
    by_symbol = {decision.entry.symbol: decision for decision in result.decisions}
    assert by_symbol["JUMP"].alertable is True
    assert by_symbol["JUMP"].lane == event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST
    assert by_symbol["SRC"].alertable is True
    assert by_symbol["TIME"].alertable is True
    assert by_symbol["COOL"].route == event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE
    assert "cooldown" in by_symbol["COOL"].reason.lower()
    assert by_symbol["DUP"].route == event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE
    assert by_symbol["TRIG"].route == event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH
    assert by_symbol["TRIG"].lane == event_alpha_router.EventAlphaRouteLane.TRIGGERED_FADE


def test_event_alpha_cycle_send_uses_router_approved_decisions_only():
    from pathlib import Path
    from crypto_rsi_scanner import config, scanner
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
    import crypto_rsi_scanner.event_alpha.radar.playbooks as event_playbooks
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    class FakeStorage:
        meta = {}

        def __init__(self, path):
            self.path = path
            self.closed = False

        def get_meta(self, key):
            return self.meta.get(key)

        def set_meta(self, key, value):
            self.meta[key] = value

        def active_subscribers(self):
            return ["chat"]

        def close(self):
            self.closed = True

    def entry(symbol, *, alertable=True, playbook=None, state=None):
        state = state or event_watchlist.EventWatchlistState.HIGH_PRIORITY.value
        playbook = playbook or event_playbooks.EventPlaybookType.PROXY_ATTENTION.value
        return event_watchlist.EventWatchlistEntry(
            schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
            row_type="event_watchlist_state",
            key=f"{symbol}|coin|{playbook}",
            cluster_id="spacex|ipo_proxy|2026-06-20",
            event_id=f"{symbol}-event",
            coin_id=symbol.lower(),
            symbol=symbol,
            relationship_type="proxy_attention",
            external_asset="SpaceX",
            event_time="2026-06-20T13:30:00+00:00",
            state=state,
            previous_state="WATCHLIST",
            first_seen_at="2026-06-18T12:00:00+00:00",
            last_seen_at="2026-06-18T13:00:00+00:00",
            source_count=1,
            highest_score=82,
            latest_score=82,
            latest_tier="HIGH_PRIORITY_WATCH",
            latest_event_name=f"{symbol} route event",
            latest_source="test",
            latest_playbook_type=playbook,
            latest_playbook_score=82,
            latest_playbook_action="high_priority_watch",
            should_alert=alertable,
            suppressed_reason=None if alertable else "duplicate state, no escalation",
        )

    sent = []

    def fake_send(message, *, parse_mode=None, chat_ids=None):
        sent.append((message, parse_mode, tuple(chat_ids or ())))
        return True

    original_storage = scanner.Storage
    original_send = scanner.send_telegram
    original_structured_send = scanner.send_telegram_structured
    original_ids = config.TELEGRAM_CHAT_IDS
    original_notification_flags = {
        "EVENT_ALPHA_ALLOW_FIXED_NOW_FOR_NOTIFY": config.EVENT_ALPHA_ALLOW_FIXED_NOW_FOR_NOTIFY,
        "EVENT_ALPHA_NOTIFY_SCOPE": config.EVENT_ALPHA_NOTIFY_SCOPE,
        "EVENT_ALPHA_EXPLORATORY_DIGEST_ENABLED": config.EVENT_ALPHA_EXPLORATORY_DIGEST_ENABLED,
        "EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_ENABLED": config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_ENABLED,
    }
    FakeStorage.meta = {}
    scanner.Storage = FakeStorage
    scanner.send_telegram = fake_send
    scanner.send_telegram_structured = fake_send
    config.TELEGRAM_CHAT_IDS = ["fallback"]
    config.EVENT_ALPHA_ALLOW_FIXED_NOW_FOR_NOTIFY = True
    config.EVENT_ALPHA_NOTIFY_SCOPE = "global"
    config.EVENT_ALPHA_EXPLORATORY_DIGEST_ENABLED = False
    config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_ENABLED = False
    try:
        cfg = event_alerts.EventAlertConfig(enabled=True)
        result = scanner._send_event_alpha_routed_digest([], cfg)
        assert result.requested is True
        assert result.attempted is False
        assert result.success is False
        assert result.block_reason == "no router-approved escalations"
        assert sent == []

        suppressed = event_alpha_router.EventAlphaRouteDecision(
            entry=entry("DUP", alertable=False),
            route=event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE,
            alertable=False,
            reason="duplicate",
        )
        result = scanner._send_event_alpha_routed_digest([suppressed], cfg)
        assert result.attempted is False
        assert result.block_reason == "no router-approved escalations"
        assert sent == []

        high = event_alpha_router.EventAlphaRouteDecision(
            entry=entry("HIGH"),
            route=event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH,
            alertable=True,
            reason="watchlist escalation",
        )
        result = scanner._send_event_alpha_routed_digest([suppressed, high], cfg)
        assert result.attempted is True
        assert result.success is True
        assert result.items_attempted == 1
        assert result.items_delivered == 1
        assert len(sent) == 1
        assert sent[0][1] == "HTML"
        assert sent[0][2] == ("chat",)
        assert "Event Alpha High-Priority Research" in sent[0][0]
        assert "high-priority research" in sent[0][0]
        assert "HIGH" in sent[0][0]
        assert "DUP" not in sent[0][0]
        assert any(
            key.startswith("event_alpha_sent_count_instant_") and value == "1"
            for key, value in FakeStorage.meta.items()
        )

        FakeStorage.meta = {}
        scanner.send_telegram = lambda message, *, parse_mode=None, chat_ids=None: False
        scanner.send_telegram_structured = lambda message, *, parse_mode=None, chat_ids=None: False
        failed = scanner._send_event_alpha_routed_digest([high], cfg)
        assert failed.attempted is True
        assert failed.success is False
        assert failed.items_attempted == 1
        assert failed.items_delivered == 0
        assert "no channel delivered" in failed.block_reason
        disabled = scanner._send_event_alpha_routed_digest([high], event_alerts.EventAlertConfig(enabled=False))
        assert disabled.requested is True
        assert disabled.attempted is False
        assert disabled.block_reason == "event alerts disabled"
    finally:
        scanner.Storage = original_storage
        scanner.send_telegram = original_send
        scanner.send_telegram_structured = original_structured_send
        config.TELEGRAM_CHAT_IDS = original_ids
        for name, value in original_notification_flags.items():
            setattr(config, name, value)


def test_event_alpha_core_digest_caps_daily_items_with_local_brief_overflow():
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as notif
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router

    decisions = [
        _notify_route_decision(
            f"CORE{i}",
            event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST,
            event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST,
        )
        for i in range(18)
    ]

    message = notif.format_core_opportunity_telegram_digest(decisions, profile="notify_llm_deep", max_items=5)

    assert "Items: 5" in message
    assert "1. CORE0 / core0" in message
    assert "5. CORE4 / core4" in message
    assert "6. CORE5 / core5" not in message
    assert "+13 more in local brief." in message


def test_event_alpha_live_daily_digest_requires_confirmation_and_dedupes_family():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as notif
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router

    class FakeStorage:
        def __init__(self):
            self.meta = {}

        def get_meta(self, key):
            return self.meta.get(key)

        def set_meta(self, key, value):
            self.meta[key] = value

    confirmed = _notify_route_decision(
        "CHZ",
        event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST,
        event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST,
    )
    duplicate = _notify_route_decision(
        "CHZ",
        event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST,
        event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST,
    )
    weak = _notify_route_decision(
        "SYN",
        event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST,
        event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST,
    )
    single_source_fan = _notify_route_decision(
        "FAN",
        event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST,
        event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST,
    )
    core_rows = [
        {
            "core_opportunity_id": "core-chz",
            "source_alert_ids": [confirmed.alert_id, duplicate.alert_id],
            "symbol": "CHZ",
            "coin_id": "chiliz",
            "incident_id": "world-cup",
            "impact_path_type": "fan_sports",
            "source_pack": "fan_sports_pack",
            "final_route_after_quality_gate": "RESEARCH_DIGEST",
            "final_opportunity_level": "validated_digest",
            "evidence_acquisition_status": "accepted_evidence_found",
            "accepted_evidence_count": 1,
            "accepted_provider_counts": {"cryptopanic": 1},
            "accepted_reason_codes": ["cryptopanic_currency_tag_match"],
            "source_class": "cryptopanic_tagged",
            "market_confirmation_level": "moderate",
            "market_context_freshness_status": "fresh",
        },
        {
            "core_opportunity_id": "core-fan",
            "source_alert_ids": [single_source_fan.alert_id],
            "symbol": "FAN",
            "coin_id": "fan-token",
            "incident_id": "world-cup-single-source",
            "impact_path_type": "fan_sports",
            "source_pack": "fan_sports_pack",
            "final_route_after_quality_gate": "RESEARCH_DIGEST",
            "final_opportunity_level": "validated_digest",
            "opportunity_level": "validated_digest",
            "opportunity_score_final": 82,
            "evidence_acquisition_status": "accepted_evidence_found",
            "accepted_evidence_count": 1,
            "accepted_provider_counts": {"cryptopanic": 1},
            "accepted_reason_codes": ["cryptopanic_currency_tag_match"],
            "source_class": "cryptopanic_tagged",
            "market_confirmation_level": "none",
            "market_context_freshness_status": "missing",
        },
        {
            "core_opportunity_id": "core-syn",
            "source_alert_ids": [weak.alert_id],
            "symbol": "SYN",
            "coin_id": "synapse",
            "incident_id": "strategic",
            "impact_path_type": "strategic_investment",
            "final_route_after_quality_gate": "RESEARCH_DIGEST",
            "final_opportunity_level": "validated_digest",
            "evidence_acquisition_status": "not_executed",
            "accepted_evidence_count": 0,
            "market_confirmation_level": "none",
            "market_context_freshness_status": "missing",
        },
    ]
    cfg = notif.EventAlphaNotificationConfig(
        enabled=True,
        profile_name="notify_llm_deep",
        artifact_namespace="notify_llm_deep_cryptopanic_rehearsal",
        daily_digest_cooldown_hours=0,
        daily_digest_max_items=5,
        research_review_digest_enabled=True,
        research_review_digest_min_score=0,
        research_review_digest_send_with_alerts=True,
    )

    plan = notif.build_notification_plan(
        [confirmed, duplicate, weak, single_source_fan],
        storage=FakeStorage(),
        cfg=cfg,
        now=datetime(2026, 6, 20, 12, tzinfo=timezone.utc),
        core_opportunity_rows=core_rows,
    )

    daily = plan.decisions_by_lane[notif.LANE_DAILY_DIGEST]
    assert len(daily) == 1
    assert daily[0].entry.symbol == "CHZ"
    assert all(item.entry.symbol != "SYN" for item in daily)
    assert any(getattr(item, "decision", item).entry.symbol == "FAN" for item in plan.research_review_items)
    assert all(item.entry.symbol != "FAN" for item in daily)


def test_event_alpha_status_profile_budget_and_unknown_profile():
    import contextlib
    import io
    import os
    from crypto_rsi_scanner import config, scanner
    import crypto_rsi_scanner.event_alpha.config.profiles as event_alpha_profiles

    profile_keys = set()
    for profile_name in event_alpha_profiles.profile_names():
        profile_keys.update(event_alpha_profiles.get_profile(profile_name).config_overrides)
    profile_keys.add("EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS")
    original = {
        name: getattr(config, name)
        for name in profile_keys
        if hasattr(config, name)
    }
    env_keys = (
        "RSI_EVENT_LLM_MAX_CANDIDATES_PER_RUN",
        "RSI_EVENT_LLM_EXTRACTOR_MAX_EVENTS_PER_RUN",
        "RSI_EVENT_LLM_MAX_CALLS_PER_RUN",
        "RSI_EVENT_LLM_MAX_CALLS_PER_DAY",
        "RSI_EVENT_LLM_MAX_ESTIMATED_COST_USD_PER_DAY",
        "RSI_EVENT_LLM_ESTIMATED_COST_PER_CALL_USD",
        "RSI_EVENT_LLM_MAX_PARALLEL_CALLS",
        "RSI_EVENT_LLM_OPENAI_TIMEOUT",
        "RSI_EVENT_LLM_EXTRACTOR_OPENAI_TIMEOUT",
        "RSI_EVENT_ALPHA_NOTIFY_MAX_RUNTIME_SECONDS",
        "RSI_EVENT_LLM_CACHE_TTL_HOURS",
    )
    original_env = {key: os.environ.get(key) for key in env_keys}
    try:
        profile = event_alpha_profiles.get_profile("full_llm_live")
        assert profile.config_overrides["EVENT_LLM_MAX_CALLS_PER_RUN"] > 0
        assert profile.config_overrides["EVENT_LLM_MAX_CALLS_PER_DAY"] > 0
        assert profile.config_overrides["EVENT_LLM_MAX_CANDIDATES_PER_RUN"] > 0
        assert profile.config_overrides["EVENT_LLM_EXTRACTOR_MAX_EVENTS_PER_RUN"] > 0
        assert profile.config_overrides["EVENT_LLM_OPENAI_TIMEOUT"] >= 30.0
        assert profile.config_overrides["EVENT_LLM_MAX_PARALLEL_CALLS"] >= 12
        assert "LLM budget defaults" in event_alpha_profiles.format_profile_report(profile)
        assert "artifact policy:" in event_alpha_profiles.format_profile_report(profile)
        assert event_alpha_profiles.get_profile("research_send").config_overrides["EVENT_ALPHA_SNAPSHOT_POLICY"] == "alertable"
        assert profile.config_overrides["EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS_PATH"].name == "public_rss_feeds.txt"
        assert event_alpha_profiles.get_profile("research_send").config_overrides[
            "EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS_PATH"
        ].name == "public_rss_feeds.txt"

        default_out = io.StringIO()
        with contextlib.redirect_stdout(default_out):
            scanner.event_alpha_status()
        profile_out = io.StringIO()
        with contextlib.redirect_stdout(profile_out):
            scanner.event_alpha_status(profile_name="no_key_live")
        full_llm_out = io.StringIO()
        with contextlib.redirect_stdout(full_llm_out):
            scanner.event_alpha_status(profile_name="full_llm_live")
        send_out = io.StringIO()
        with contextlib.redirect_stdout(send_out):
            scanner.event_alpha_status(profile_name="research_send")
        assert "profile: default" in default_out.getvalue()
        assert "profile: no_key_live" in profile_out.getvalue()
        assert default_out.getvalue() != profile_out.getvalue()
        assert "LLM budget:" in profile_out.getvalue()
        assert "max_candidates=" in full_llm_out.getvalue()
        assert "max_extract_events=" in full_llm_out.getvalue()
        assert "parallel=" in full_llm_out.getvalue()
        assert "timeouts=" in full_llm_out.getvalue()
        assert "watchlist_monitor:" in profile_out.getvalue()
        assert "- READY project_blog_rss" in full_llm_out.getvalue()
        assert "- READY project_blog_rss" in send_out.getvalue()

        os.environ["RSI_EVENT_LLM_MAX_CANDIDATES_PER_RUN"] = "111"
        os.environ["RSI_EVENT_LLM_EXTRACTOR_MAX_EVENTS_PER_RUN"] = "222"
        os.environ["RSI_EVENT_LLM_MAX_CALLS_PER_RUN"] = "333"
        os.environ["RSI_EVENT_LLM_MAX_CALLS_PER_DAY"] = "444"
        os.environ["RSI_EVENT_LLM_MAX_ESTIMATED_COST_USD_PER_DAY"] = "55.5"
        os.environ["RSI_EVENT_LLM_ESTIMATED_COST_PER_CALL_USD"] = "0.06"
        os.environ["RSI_EVENT_LLM_MAX_PARALLEL_CALLS"] = "7"
        os.environ["RSI_EVENT_LLM_OPENAI_TIMEOUT"] = "41"
        os.environ["RSI_EVENT_LLM_EXTRACTOR_OPENAI_TIMEOUT"] = "42"
        os.environ["RSI_EVENT_ALPHA_NOTIFY_MAX_RUNTIME_SECONDS"] = "543"
        os.environ["RSI_EVENT_LLM_CACHE_TTL_HOURS"] = "12"
        override_out = io.StringIO()
        with contextlib.redirect_stdout(override_out):
            scanner.event_alpha_status(profile_name="notify_llm")
        override_text = override_out.getvalue()
        assert "max_candidates=111" in override_text
        assert "max_extract_events=222" in override_text
        assert "max_run=333 max_day=444" in override_text
        assert "max_cost_day=55.5" in override_text
        assert "parallel=7" in override_text
        assert "timeouts=41/42s" in override_text
        assert "cache_ttl_hours=12" in override_text

        bad_out = io.StringIO()
        with contextlib.redirect_stdout(bad_out):
            scanner.event_alpha_status(profile_name="missing-profile")
        assert "unknown Event Alpha profile" in bad_out.getvalue()
    finally:
        for name, value in original.items():
            setattr(config, name, value)
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_event_watchlist_monitor_detects_material_updates_without_new_source():
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
    import crypto_rsi_scanner.event_alpha.notifications.watchlist_monitor as event_watchlist_monitor

    entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="spacex|velvet|proxy_attention",
        cluster_id="spacex|ipo_proxy|2026-06-20",
        event_id="velvet-event",
        coin_id="velvet",
        symbol="VELVET",
        relationship_type="proxy_attention",
        external_asset="SpaceX",
        event_time="2026-06-18T13:00:00+00:00",
        state=event_watchlist.EventWatchlistState.WATCHLIST.value,
        previous_state="RADAR",
        first_seen_at="2026-06-18T10:00:00+00:00",
        last_seen_at="2026-06-18T11:00:00+00:00",
        source_count=2,
        highest_score=72,
        latest_score=72,
        latest_tier="WATCHLIST",
        latest_event_name="VELVET SpaceX proxy",
        latest_source="fixture",
        latest_score_components={"derivatives_crowding": 55, "cluster_confidence": 70},
    )
    expired = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="old|old|proxy_attention",
        cluster_id="old",
        event_id="old-event",
        coin_id="old",
        symbol="OLD",
        relationship_type="proxy_attention",
        external_asset=None,
        event_time=None,
        state=event_watchlist.EventWatchlistState.EXPIRED.value,
        previous_state="RADAR",
        first_seen_at="2026-06-10T00:00:00+00:00",
        last_seen_at="2026-06-18T11:00:00+00:00",
        latest_event_name="old",
        latest_source="fixture",
    )
    read = event_watchlist.EventWatchlistReadResult(
        state_path=Path("watchlist.jsonl"),
        rows_read=2,
        entries=[entry, expired],
        latest_only=True,
    )
    result = event_watchlist_monitor.monitor_watchlist(
        read,
        market_rows=[{
            "id": "velvet",
            "symbol": "velvet",
            "name": "Velvet",
            "current_price": 1.25,
            "price_change_percentage_24h_in_currency": 38,
            "price_change_percentage_7d_in_currency": 120,
            "total_volume": 6000000,
            "market_cap": 20000000,
            "volume_zscore_24h": 4.2,
        }],
        now=pd.Timestamp("2026-06-18T14:00:00Z").to_pydatetime(),
    )
    assert result.active_entries == 1
    assert result.skipped_expired == 1
    row = result.rows[0]
    assert row.material_update is True
    assert "EVENT_PASSED" in row.state_transition_hints
    assert "DERIVATIVES_HEATED" in row.state_transition_hints
    assert "MARKET_SCORE_JUMP" in row.state_transition_hints
    assert "TRIGGERED_FADE" not in row.state_transition_hints
    assert "EVENT WATCHLIST MONITOR" in event_watchlist_monitor.format_watchlist_monitor_report(result)


def test_event_alpha_pipeline_routes_monitor_updates_without_new_source():
    import json
    import tempfile
    from dataclasses import asdict
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.radar.pipeline as event_alpha_pipeline
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.playbooks as event_playbooks
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
    from crypto_rsi_scanner.event_core.models import EventDiscoveryResult

    def entry(symbol, *, event_time, state=None):
        return event_watchlist.EventWatchlistEntry(
            schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
            row_type="event_watchlist_state",
            key=f"{symbol.lower()}|coin|proxy_attention",
            cluster_id=f"{symbol.lower()}|proxy|2026-06-18",
            event_id=f"{symbol.lower()}-event",
            coin_id=symbol.lower(),
            symbol=symbol,
            relationship_type="proxy_attention",
            external_asset="SpaceX",
            event_time=event_time,
            state=state or event_watchlist.EventWatchlistState.WATCHLIST.value,
            previous_state=event_watchlist.EventWatchlistState.RADAR.value,
            first_seen_at="2026-06-18T10:00:00+00:00",
            last_seen_at="2026-06-18T11:00:00+00:00",
            source_count=2,
            highest_score=72,
            latest_score=72,
            latest_tier="WATCHLIST",
            latest_event_name=f"{symbol} SpaceX proxy",
            latest_source="fixture",
            latest_playbook_type=event_playbooks.EventPlaybookType.PROXY_ATTENTION.value,
            latest_playbook_score=72,
            latest_playbook_action="watchlist",
            latest_score_components={
                "derivatives_crowding": 55,
                "cluster_confidence": 70,
                "impact_path_type": "proxy_exposure",
                "impact_path_strength": "strong",
                "candidate_role": "proxy_instrument",
                "evidence_quality_score": 78,
                "source_class": "crypto_native",
                "evidence_specificity": "asset_and_catalyst",
                "market_confirmation_score": 65,
                "market_confirmation_level": "confirmed",
                "opportunity_score_final": 80,
                "opportunity_level": "watchlist",
                "opportunity_verdict_reasons": ["fixture_monitor_route_quality_context"],
                "why_local_only": "not_local_only",
                "why_not_watchlist": "already_watchlisted",
                "manual_verification_items": ["verify source, catalyst timing, and liquidity"],
                "upgrade_requirements": [],
                "downgrade_warnings": [],
            },
            should_alert=False,
            suppressed_reason="duplicate state, no escalation",
        )

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "watchlist.jsonl"
        rows = [
            entry("APPROACH", event_time="2026-06-18T17:00:00+00:00"),
            entry("PASSED", event_time="2026-06-18T12:30:00+00:00"),
            entry("ARMED", event_time="2026-06-18T12:30:00+00:00", state=event_watchlist.EventWatchlistState.ARMED.value),
        ]
        path.write_text(
            "\n".join(json.dumps(asdict(row), sort_keys=True) for row in rows) + "\n",
            encoding="utf-8",
        )
        result = event_alpha_pipeline.run_event_alpha_pipeline(
            EventDiscoveryResult((), (), (), (), ()),
            now=datetime(2026, 6, 18, 13, 0, tzinfo=timezone.utc),
            watchlist_cfg=event_watchlist.EventWatchlistConfig(enabled=True, state_path=path),
            router_cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True),
            refresh_watchlist=False,
            route=True,
            watchlist_monitor_enabled=True,
            watchlist_monitor_market_rows=[{
                "id": "passed",
                "symbol": "passed",
                "price_change_percentage_24h_in_currency": 45,
                "total_volume": 6000000,
                "market_cap": 20000000,
                "volume_zscore_24h": 4.0,
            }],
            watchlist_monitor_route_updates=True,
        )
    assert result.watchlist_monitor_active_entries == 3
    assert result.watchlist_monitor_material_updates == 3
    assert result.router_result is not None
    by_symbol = {decision.entry.symbol: decision for decision in result.router_result.decisions}
    assert by_symbol["APPROACH"].alertable is True
    assert by_symbol["APPROACH"].lane == event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST
    assert by_symbol["PASSED"].alertable is True
    assert by_symbol["PASSED"].entry.state == event_watchlist.EventWatchlistState.EVENT_PASSED.value
    assert by_symbol["ARMED"].alertable is True
    assert by_symbol["ARMED"].entry.state == event_watchlist.EventWatchlistState.ARMED.value
    assert all(decision.entry.state != event_watchlist.EventWatchlistState.TRIGGERED_FADE.value for decision in by_symbol.values())
    assert "watchlist_monitor_material=3" in event_alpha_pipeline.format_event_alpha_pipeline_report(result)


def test_event_watchlist_scanner_refresh_and_report_with_fixture_anomalies():
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
        "EVENT_WATCHLIST_EXPIRE_HOURS_AFTER_EVENT": config.EVENT_WATCHLIST_EXPIRE_HOURS_AFTER_EVENT,
        "EVENT_ALPHA_ROUTER_ENABLED": config.EVENT_ALPHA_ROUTER_ENABLED,
        "EVENT_ALPHA_FEEDBACK_PATH": config.EVENT_ALPHA_FEEDBACK_PATH,
    }
    with tempfile.TemporaryDirectory() as tmp:
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
        config.EVENT_WATCHLIST_ENABLED = True
        config.EVENT_WATCHLIST_STATE_PATH = Path(tmp) / "watchlist.jsonl"
        config.EVENT_WATCHLIST_EXPIRE_HOURS_AFTER_EVENT = 72
        config.EVENT_ALPHA_ROUTER_ENABLED = True
        config.EVENT_ALPHA_FEEDBACK_PATH = Path(tmp) / "feedback.jsonl"
        try:
            refresh_out = io.StringIO()
            with contextlib.redirect_stdout(refresh_out):
                scanner.event_watchlist_refresh(event_now="2026-06-15T16:00:00Z")
            refresh_text = refresh_out.getvalue()
            assert "EVENT WATCHLIST REFRESH" in refresh_text
            assert "rows_written: 1" in refresh_text
            assert "alertable escalations: 0" in refresh_text

            report_out = io.StringIO()
            with contextlib.redirect_stdout(report_out):
                scanner.event_watchlist_report()
            report_text = report_out.getvalue()
            assert "EVENT WATCHLIST REPORT" in report_text
            assert "RAW_EVIDENCE" in report_text
            assert "SOL/solana" in report_text
            assert "playbook: market_anomaly_unknown" in report_text

            router_out = io.StringIO()
            with contextlib.redirect_stdout(router_out):
                scanner.event_alpha_router_report()
            router_text = router_out.getvalue()
            assert "EVENT ALPHA ROUTER REPORT" in router_text
            assert "router_enabled: true" in router_text
            assert "STORE_ONLY" in router_text
            assert "SOL/solana" in router_text

            feedback_out = io.StringIO()
            with contextlib.redirect_stdout(feedback_out):
                scanner.event_feedback_mark(
                    "SOL",
                    "junk",
                    notes="no catalyst",
                    marked_by="tester",
                )
            feedback_text = feedback_out.getvalue()
            assert "EVENT ALPHA FEEDBACK MARKED" in feedback_text
            assert "label: junk" in feedback_text
            assert "SOL/solana" in feedback_text

            feedback_report_out = io.StringIO()
            with contextlib.redirect_stdout(feedback_report_out):
                scanner.event_feedback_report()
            feedback_report = feedback_report_out.getvalue()
            assert "EVENT ALPHA FEEDBACK REPORT" in feedback_report
            assert "junk=1" in feedback_report
        finally:
            for name, value in original.items():
                setattr(config, name, value)


def test_makefile_has_event_alpha_no_key_target():
    from pathlib import Path

    text = Path("Makefile").read_text(encoding="utf-8")
    assert "event-alpha-eval:" in text
    assert "crypto_rsi_scanner.event_alpha.outcomes.eval" in text
    assert "event-alpha-no-key-report:" in text
    assert "--event-alpha-radar-report" in text
    assert "event-alpha-cycle:" in text
    assert "event-alpha-cycle-llm:" in text
    assert "event-catalyst-search-fixture-report:" in text
    assert "event-alpha-cycle-search:" in text
    assert "event-alpha-cycle-search-llm:" in text
    assert "--event-catalyst-search-report" in text
    assert "event-alpha-cycle-send:" in text
    assert "event-alpha-notify-cycle:" in text
    assert "event-alpha-notify-no-key:" in text
    assert "event-alpha-notify-llm:" in text
    assert "event-alpha-notify-preview:" in text
    assert "event-alpha-notify-go-no-go:" in text
    assert "event-alpha-notification-checklist:" in text
    assert "event-alpha-notification-runs-report:" in text
    assert "event-alpha-provider-health-report:" in text
    assert "event-alpha-provider-health-reset:" in text
    assert "event-alpha-day1-start:" in text
    assert "event-alpha-day1-start-llm:" in text
    assert "event-alpha-notify-start-no-key:" in text
    assert "event-alpha-notify-start-llm:" in text
    assert "event-alpha-send-test:" in text
    assert "event-alpha-runs-report:" in text
    assert "event-alpha-status:" in text
    assert "event-alpha-daily-report:" in text
    assert "event-alpha-daily-llm-report:" in text
    assert "event-alpha-daily-send:" in text
    assert "event-alpha-health:" in text
    assert "event-alpha-open-items:" in text
    assert "event-alpha-daily-brief:" in text
    assert "event-alpha-replay:" in text
    assert "event-alpha-prune-artifacts:" in text
    assert "--event-alpha-profile no_key_live" in text
    assert "--event-alpha-profile full_llm_live" in text
    assert "--event-alpha-profile research_send --event-alert-send" in text
    assert "--event-alpha-notify-cycle --event-alpha-profile $(PROFILE) --event-alert-send" in text
    assert "RSI_EVENT_ALERTS_ENABLED=1" in text
    assert "RSI_EVENT_WATCHLIST_MONITOR_ENABLED=1" in text
    assert "event-alpha-alerts-report:" in text
    assert "event-alpha-fill-outcomes:" in text
    assert "--event-alpha-cycle" in text
    assert "--event-alpha-alerts-report" in text
    assert "--event-alpha-fill-outcomes" in text
    assert "RSI_EVENT_ANOMALY_SCANNER_ENABLED=1" in text
    assert "RSI_EVENT_CATALYST_SEARCH_ENABLED=1" in text
    assert "RSI_EVENT_WATCHLIST_ENABLED=1" in text
    assert "RSI_EVENT_ALPHA_ROUTER_ENABLED=1" in text
    assert "RSI_EVENT_ALPHA_ALERT_STORE_PATH" in text
    assert "event-watchlist-refresh:" in text
    assert "event-watchlist-report:" in text
    assert "event-watchlist-monitor:" in text
    assert "event-alpha-router-report:" in text
    assert "event-alpha-missed-report:" in text
    assert "event-alpha-calibration-report:" in text
    assert "event-research-cards:" in text
    assert "event-feedback-report:" in text
    assert "event-feedback-useful:" in text
    assert "event-feedback-junk:" in text
    assert "event-feedback-watch:" in text
    assert "--event-watchlist-refresh" in text
    assert "--event-alpha-router-report" in text
    assert "--event-alpha-runs-report" in text
    assert "--event-alpha-status" in text


def test_event_identity_shared_matcher_field_safety():
    import crypto_rsi_scanner.event_alpha.radar.identity as event_identity

    hype = event_identity.AssetIdentity(symbol="HYPE", coin_id="hyperliquid")
    result = event_identity.match_asset_identity(
        hype,
        event_identity.IdentityEvidence(strong_content=("IPO hype keeps building",)),
    )
    assert result.reason == "common_word_identity_rejected"

    pump = event_identity.AssetIdentity(symbol="PUMP", coin_id="pump-token")
    url_only = event_identity.match_asset_identity(
        pump,
        event_identity.IdentityEvidence(url="https://search.example/?q=PUMPUSDT"),
    )
    assert url_only.reason == "identity_url_only_rejected"
    body_match = event_identity.match_asset_identity(
        pump,
        event_identity.IdentityEvidence(strong_content=("PUMPUSDT volume surged after listing rumors",)),
    )
    assert body_match.matched and body_match.reason == "identity_match_pair"

    btc = event_identity.AssetIdentity(symbol="BTC", coin_id="bitcoin", project_name="Bitcoin")
    publisher = event_identity.match_asset_identity(
        btc,
        event_identity.IdentityEvidence(source_origin=("Bitcoin World",)),
    )
    assert publisher.reason == "identity_source_origin_rejected"

    address = "0x1111111111111111111111111111111111111111"
    contract = event_identity.AssetIdentity(symbol="AAA", contract_addresses=(address,))
    path_match = event_identity.match_asset_identity(
        contract,
        event_identity.IdentityEvidence(url=f"https://etherscan.io/token/{address}"),
    )
    assert path_match.matched and path_match.evidence_field == "url_path_contract"
    query_match = event_identity.match_asset_identity(
        contract,
        event_identity.IdentityEvidence(url=f"https://search.example/?contract={address}"),
    )
    assert query_match.reason == "identity_url_only_rejected"


def test_event_watchlist_market_sources_select_active_rows():
    import tempfile
    from pathlib import Path

    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
    import crypto_rsi_scanner.event_alpha.radar.watchlist_market as event_watchlist_market

    entry = _test_watchlist_entry(state="WATCHLIST", symbol="VELVET", coin_id="velvet")
    read = event_watchlist.EventWatchlistReadResult(Path("state.jsonl"), 1, [entry], True)
    rows = [{"id": "velvet", "symbol": "velvet", "current_price": 1.23, "price_change_percentage_24h": 30}]
    selected = event_watchlist_market.market_rows_for_watchlist(read, source="cycle", cycle_rows=rows)
    assert selected.rows_selected == 1
    assert selected.rows[0]["id"] == "velvet"

    tmp = Path(tempfile.mkdtemp()) / "markets.json"
    tmp.write_text('[{"id":"velvet","symbol":"velvet","current_price":2.0}]')
    loaded = event_watchlist_market.load_market_rows(tmp)
    fixture = event_watchlist_market.market_rows_for_watchlist(read, source="fixture", fixture_rows=loaded)
    assert fixture.rows_selected == 1

    empty = event_watchlist_market.market_rows_for_watchlist(read, source="cycle", cycle_rows=[])
    assert empty.rows_selected == 0
    assert empty.warnings


def test_event_research_cards_write_files_and_index():
    from dataclasses import replace
    import tempfile
    from pathlib import Path

    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    entry = _test_watchlist_entry(state="HIGH_PRIORITY", symbol="VELVET", coin_id="velvet")
    rune = replace(
        _test_watchlist_entry(state="WATCHLIST", symbol="RUNE", coin_id="thorchain"),
        key="incident:rune|thorchain|security",
        relationship_type="impact_hypothesis",
        external_asset="THORChain",
        latest_event_name="THORChain exploit and RUNE resumes trading",
        latest_playbook_type="security_or_regulatory_shock",
        latest_effective_playbook_type="security_or_regulatory_shock",
        requested_state_before_quality_gate=event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        final_state_after_quality_gate=event_watchlist.EventWatchlistState.WATCHLIST.value,
        state_quality_capped=True,
        quality_state_block_reason="opportunity_level_caps_state:watchlist",
        latest_score_components={
            **entry.latest_score_components,
            "incident_id": "incident:rune",
            "validated_symbol": "RUNE",
            "validated_coin_id": "thorchain",
            "impact_path_type": "exploit_security_event",
            "impact_path_reason": "exploit_security_event",
            "candidate_role": "direct_subject",
            "impact_category": "security_or_regulatory_shock",
            "opportunity_level": "watchlist",
            "opportunity_score_final": 83,
        },
    )
    rune_suppressed = event_alpha_router.EventAlphaRouteDecision(
        entry=rune,
        route=event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE,
        alertable=False,
        reason="duplicate digest already sent",
        final_route_after_quality_gate=event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE.value,
        opportunity_level="watchlist",
        opportunity_score_final=83,
    )
    diagnostic = replace(
        _test_watchlist_entry(state="HIGH_PRIORITY", symbol="VELVET", coin_id="velvet"),
        key="cluster|velvet|source_noise_control",
        latest_playbook_type="source_noise_control",
        latest_effective_playbook_type="source_noise_control",
        latest_score_components={
            **entry.latest_score_components,
            "candidate_role": "source_noise",
            "impact_path_type": "generic_cooccurrence_only",
            "opportunity_level": "local_only",
            "opportunity_score_final": 0,
        },
    )
    out_dir = Path(tempfile.mkdtemp())
    result = event_research_cards.write_research_cards(
        out_dir,
        watchlist_entries=[entry, rune, diagnostic],
        alert_rows=[],
        route_decisions=[rune_suppressed],
    )
    assert result.cards_written == 2
    assert result.index_path.exists()
    card_text = "\n".join(path.read_text() for path in result.card_paths)
    assert "VELVET" in card_text
    assert "RUNE" in card_text
    rune_card = next(path for path in result.card_paths if "RUNE" in path.read_text())
    assert event_research_cards.card_core_opportunity_id(rune_card)
    assert event_research_cards.card_feedback_target(rune_card) == event_research_cards.card_core_opportunity_id(rune_card)
    assert rune_card.name in result.index_path.read_text()
    assert "Core Opportunity Cards" in result.index_path.read_text()
    assert "source_noise_control" not in result.index_path.read_text().split("## Core Opportunity Cards", 1)[1].split("## Diagnostic", 1)[0]


def test_event_alpha_explain_last_run_paths():
    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief
    import crypto_rsi_scanner.event_alpha.artifacts.explain as event_alpha_explain
    import crypto_rsi_scanner.event_alpha.artifacts.run_ledger as event_alpha_run_ledger

    quiet = event_alpha_explain.format_last_run_explanation([
        {"run_id": "r1", "run_mode": "burn_in", "artifact_namespace": "no_key_live", "success": True, "raw_events": 0, "market_anomalies": 0, "candidates": 0, "alerts": 0, "routed": 0, "alertable": 0}
    ])
    assert "no source events or market anomalies" in quiet
    routed = event_alpha_explain.format_last_run_explanation([
        {"run_id": "r2", "run_mode": "burn_in", "artifact_namespace": "no_key_live", "success": True, "raw_events": 3, "market_anomalies": 1, "candidates": 2, "alerts": 2, "routed": 2, "alertable": 0, "llm_skipped_due_budget": 1}
    ], alert_rows=[{"run_mode": "burn_in", "artifact_namespace": "no_key_live", "tier": "STORE_ONLY", "rejected_reason": "source_noise"}])
    assert "router produced no alertable decisions" in routed
    assert "skipped_budget=1" in routed

    rows = [
        {"run_id": "default-newer", "profile": "default", "run_mode": "burn_in", "artifact_namespace": "default", "started_at": "2026-06-19T12:00:00+00:00", "success": True},
        {"run_id": "no-key-older", "profile": "no_key_live", "run_mode": "burn_in", "artifact_namespace": "no_key_live", "started_at": "2026-06-19T10:00:00+00:00", "success": True},
    ]
    assert event_alpha_run_ledger.latest_run(rows)["run_id"] == "default-newer"
    assert event_alpha_run_ledger.latest_run(rows, "no_key_live")["run_id"] == "no-key-older"
    assert event_alpha_run_ledger.latest_runs_by_profile(rows)["no_key_live"]["run_id"] == "no-key-older"
    explain = event_alpha_explain.format_last_run_explanation(rows, requested_profile="no_key_live")
    assert "requested_profile: no_key_live" in explain
    assert "selected_run_profile: no_key_live" in explain
    assert "profile_match: true" in explain
    fallback = event_alpha_explain.format_last_run_explanation(rows, requested_profile="full_llm_live")
    assert "No Event Alpha run ledger rows found." in fallback
    markdown = event_alpha_daily_brief.build_daily_brief(
        run_rows=rows,
        requested_profile="no_key_live",
        clock_status={
            "clock_mode": "fixed",
            "research_now": "2026-06-15T16:00:00+00:00",
            "wall_clock_now": "2026-06-20T16:00:00+00:00",
            "fixed_clock_age_hours": 120.0,
            "warnings": ("fixed research clock active", "fixed research clock is stale by 120.0h"),
        },
    )
    assert "Requested profile: no_key_live" in markdown
    assert "Selected run profile: no_key_live" in markdown
    assert "Profile match: true" in markdown
    assert "Clock: mode=fixed" in markdown
    assert "fixed_clock_age_hours=120.00h" in markdown
    assert "Clock warning: fixed research clock is stale by 120.0h" in markdown
    legacy_warning = event_alpha_daily_brief.build_daily_brief(
        run_rows=[{"run_id": "legacy", "started_at": "2026-06-19T12:00:00+00:00", "success": True}],
        requested_profile="no_key_live",
    )
    assert "only legacy/default run rows were available" in legacy_warning


def test_event_watchlist_market_targeted_provider_and_fallback():
    import crypto_rsi_scanner.event_alpha.radar.watchlist_market as event_watchlist_market

    watchlist = type("Read", (), {
        "entries": [
            _test_watchlist_entry(state="WATCHLIST", symbol="VELVET", coin_id="velvet"),
        ]
    })()
    targeted = event_watchlist_market.FixtureWatchlistMarketProvider([
        {"id": "velvet", "symbol": "velvet", "price_change_percentage_24h": 22.0},
        {"id": "noise", "symbol": "noise"},
    ])
    result = event_watchlist_market.market_rows_for_watchlist(
        watchlist,
        source="fixture",
        fixture_rows=[{"id": "velvet", "symbol": "velvet", "price_change_percentage_24h": 4.0}],
        targeted_lookup=True,
        targeted_provider=targeted,
        cache_ttl_seconds=123,
    )
    assert result.assets_requested == 1
    assert result.rows_selected == 1
    assert result.rows[0]["price_change_percentage_24h"] == 22.0
    assert result.rows[0]["watchlist_market_source"] == "fixture"
    assert result.cache_status == "ttl=123s"

    fallback = event_watchlist_market.market_rows_for_watchlist(
        watchlist,
        source="coingecko",
        cycle_rows=[{"id": "velvet", "symbol": "velvet", "price_change_percentage_24h": 7.0}],
        targeted_lookup=True,
        cache_ttl_seconds=30,
    )
    assert fallback.rows[0]["price_change_percentage_24h"] == 7.0
    assert any("not configured" in warning for warning in fallback.warnings)


def test_watchlist_coingecko_targeted_provider_cache_and_fallback():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
    import crypto_rsi_scanner.event_alpha.radar.watchlist_market as event_watchlist_market
    import crypto_rsi_scanner.event_alpha.notifications.watchlist_monitor as event_watchlist_monitor

    calls = {"count": 0}

    def fetcher(ids):
        calls["count"] += 1
        return [
            {"id": coin_id, "symbol": coin_id[:3], "current_price": idx + 1, "price_change_percentage_24h": 20}
            for idx, coin_id in enumerate(ids)
        ]

    now = datetime(2026, 6, 18, 10, 0, tzinfo=timezone.utc)
    provider = event_watchlist_market.CoinGeckoWatchlistMarketProvider(
        fetcher=fetcher,
        cache_ttl_seconds=900,
        now_fn=lambda: now,
    )
    rows, warnings = provider.fetch_market_rows(["velvet", "bitcoin", "chiliz"], max_assets=2)
    assert warnings == ()
    assert len(rows) == 2
    assert calls["count"] == 1
    rows_again, _warnings_again = provider.fetch_market_rows(["bitcoin", "velvet"], max_assets=2)
    assert len(rows_again) == 2
    assert calls["count"] == 1
    assert provider.last_cache_status == "hit"

    entry = _test_watchlist_entry(state="WATCHLIST", symbol="VELVET", coin_id="velvet")
    read = event_watchlist.EventWatchlistReadResult(
        state_path=__import__("pathlib").Path("/tmp/watchlist.jsonl"),
        rows_read=1,
        entries=[entry],
        latest_only=True,
    )

    def failing_fetcher(ids):
        raise RuntimeError("boom")

    fallback = event_watchlist_market.market_rows_for_watchlist(
        read,
        source="coingecko",
        cycle_rows=[{"coin_id": "velvet", "symbol": "VELVET", "return_24h": 0.22, "volume_zscore_24h": 4.0}],
        targeted_lookup=True,
        targeted_provider=event_watchlist_market.CoinGeckoWatchlistMarketProvider(fetcher=failing_fetcher),
        now=now,
    )
    assert fallback.rows_selected == 1
    assert any("failed" in warning for warning in fallback.warnings)
    monitored = event_watchlist_monitor.monitor_watchlist(read, market_rows=fallback.rows, now=now)
    assert monitored.rows[0].material_update is True
    updated = event_watchlist_monitor.apply_monitor_updates_to_watchlist(read, monitored)
    assert updated.entries[0].state != "TRIGGERED_FADE"


def test_watchlist_monitor_uses_derivatives_and_supply_enrichment_without_triggering_fade():
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
    import crypto_rsi_scanner.event_alpha.radar.watchlist_enrichment as event_watchlist_enrichment
    import crypto_rsi_scanner.event_alpha.notifications.watchlist_monitor as event_watchlist_monitor

    entry = _test_watchlist_entry(state="WATCHLIST", symbol="VELVET", coin_id="velvet")
    read = event_watchlist.EventWatchlistReadResult(
        state_path=Path("watchlist.jsonl"),
        rows_read=1,
        entries=[entry],
        latest_only=True,
    )
    enrichment = event_watchlist_enrichment.enrichment_for_watchlist(
        read,
        derivatives_source="fixture",
        supply_source="fixture",
        dex_liquidity_source="fixture",
        protocol_metrics_source="fixture",
        derivatives_rows=[{"coin_id": "velvet", "derivatives_crowding": 68}],
        supply_rows=[{"coin_id": "velvet", "supply_pressure": 72}],
        dex_liquidity_rows=[{"coin_id": "velvet", "pool_liquidity_usd": 500_000, "dex_volume_24h": 900_000}],
        protocol_metrics_rows=[{"coin_id": "velvet", "tvl_change_24h_pct": 0.12}],
    )
    assert enrichment.assets_requested == 1
    assert enrichment.derivatives["velvet"]["derivatives_crowding"] == 68
    assert enrichment.supply["velvet"]["supply_pressure"] == 72
    assert enrichment.dex_liquidity["velvet"]["pool_liquidity_usd"] == 500_000
    assert enrichment.protocol_metrics["velvet"]["tvl_change_24h_pct"] == 0.12
    monitored = event_watchlist_monitor.monitor_watchlist(
        read,
        derivatives_by_asset=enrichment.derivatives,
        supply_by_asset=enrichment.supply,
        now=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )
    row = monitored.rows[0]
    assert row.material_update is True
    assert "DERIVATIVES_HEATED" in row.state_transition_hints
    assert "SUPPLY_PRESSURE_UPGRADED" in row.state_transition_hints
    updated = event_watchlist_monitor.apply_monitor_updates_to_watchlist(read, monitored)
    updated_entry = updated.entries[0]
    assert updated_entry.state == event_watchlist.EventWatchlistState.WATCHLIST.value
    assert "derivatives_crowding_upgrade" in updated_entry.material_change_reasons
    assert "supply_pressure_upgrade" in updated_entry.material_change_reasons
    assert "score_jump" in updated_entry.material_change_reasons
    routed = event_alpha_router.route_watchlist(
        updated,
        cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True),
    )
    decision = routed.decisions[0]
    assert decision.alertable is True
    assert decision.route != event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH


def test_event_alpha_research_review_skipped_sample_dedupes_by_family():
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as notif

    skipped = [
        notif.EventAlphaResearchReviewSkippedItem(
            symbol="CHZ",
            coin_id="chiliz",
            core_opportunity_id=f"agg:chz-{idx}",
            candidate_family_id=f"world-cup:chiliz:{idx % 3}",
            score=70 - idx,
            rank_score=70 - idx,
            skip_reason="max_items",
            card_path=f"research_cards/chz_{idx}.md",
        )
        for idx in range(8)
    ]
    skipped.append(
        notif.EventAlphaResearchReviewSkippedItem(
            symbol="VELVET",
            coin_id="velvet",
            core_opportunity_id="agg:velvet-spacex",
            candidate_family_id="spacex:velvet",
            score=65,
            rank_score=65,
            skip_reason="max_items",
        )
    )
    skipped.append(
        notif.EventAlphaResearchReviewSkippedItem(
            symbol="SECTOR",
            coin_id="diagnostic",
            core_opportunity_id="diag:sector",
            candidate_family_id="sector:diagnostic",
            score=80,
            rank_score=80,
            skip_reason="sector_excluded",
            opportunity_type="DIAGNOSTIC",
        )
    )
    sample = notif._diverse_skipped_sample(skipped, limit=10)  # noqa: SLF001
    assert "VELVET" in [item.symbol for item in sample]
    assert len({item.candidate_family_id for item in sample}) >= 5
    candidate_summary = notif._research_review_skipped_family_summary(skipped)  # noqa: SLF001
    assert len([row for row in candidate_summary if str(row["candidate_family_id"]).startswith("world-cup:chiliz")]) == 3
    summary = notif._research_review_skipped_display_family_summary(skipped)  # noqa: SLF001
    by_label = {row["label"]: row for row in summary}
    assert by_label["CHZ/chiliz"]["skipped_count"] == 8
    assert by_label["CHZ/chiliz"]["sample_core_opportunity_ids"][:2] == ["agg:chz-0", "agg:chz-1"]
    assert by_label["CHZ/chiliz"]["representative_card_path"] == "research_cards/chz_0.md"
    assert by_label["VELVET/velvet"]["skipped_count"] == 1
    assert by_label["SECTOR/diagnostic"]["display_hidden"] is True
    display = notif._research_review_skipped_family_display(summary, limit=2)  # noqa: SLF001
    assert {row["label"] for row in display} == {"CHZ/chiliz", "VELVET/velvet"}


def test_event_core_opportunities_aggregate_duplicates_and_hide_controls():
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.core_opportunities as event_core_opportunities
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    def row(symbol, *, category, path, role="proxy_venue", route="STORE_ONLY", level="local_only", score=58, playbook="proxy_attention"):
        return {
            "incident_id": "incident:spacex",
            "canonical_incident_name": "SpaceX pre-IPO exposure",
            "validated_symbol": symbol,
            "validated_coin_id": symbol.lower(),
            "candidate_role": role,
            "impact_category": category,
            "impact_path_type": path,
            "opportunity_level": level,
            "opportunity_score_final": score,
            "final_route_after_quality_gate": route,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.HIGH_PRIORITY.value
            if level == "high_priority"
            else event_watchlist.EventWatchlistState.RADAR.value,
            "latest_effective_playbook_type": playbook,
            "hypothesis_id": f"hyp:{symbol}:{category}",
            "evidence_quotes": [f"{symbol} evidence for {category}"],
        }

    rows = [
        row(
            "VELVET",
            category="tokenized_stock_venue",
            path="venue_value_capture",
            route=event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
            level="high_priority",
            score=94,
        ),
        {
            **row("VELVET", category="rwa_preipo_proxy", path="proxy_exposure", score=67),
            "incident_id": "incident:spacex-alt-headline",
            "hypothesis_id": "hyp:VELVET:rwa_preipo_proxy_alt_headline",
        },
        {
            **row("VELVET", category="unknown", path="insufficient_data", role="unknown_with_reason", score=0),
            "opportunity_level": "local_only",
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.QUALITY_BLOCKED.value,
            "state_quality_capped": True,
            "quality_state_block_reason": "impact_path_type_insufficient_data",
            "hypothesis_id": "hyp:VELVET:quality-capped-support",
        },
        row(
            "VELVET",
            category="publisher_noise",
            path="generic_cooccurrence_only",
            role="source_noise",
            playbook="source_noise_control",
        ),
        row("AAVE", category="strategic_investment", path="strategic_investment_or_valuation", role="direct_subject", score=72, level="validated_digest", route=event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value),
        row("RUNE", category="security_or_regulatory_shock", path="exploit_security_event", role="direct_subject", score=80, level="watchlist"),
        row("ZEC", category="listing_liquidity", path="listing_liquidity_event", role="direct_subject", score=70, level="validated_digest"),
    ]

    opportunities = event_core_opportunities.aggregate_core_opportunities(rows)
    velvet = [item for item in opportunities if item.symbol == "VELVET"]
    assert len(velvet) == 1
    assert velvet[0].final_route_after_quality_gate == event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value
    assert {"tokenized_stock_venue", "rwa_preipo_proxy"} <= set(velvet[0].supporting_categories)
    assert "hyp:VELVET:rwa_preipo_proxy_alt_headline" in velvet[0].supporting_hypothesis_ids
    assert velvet[0].source_noise_control_count == 1
    assert velvet[0].diagnostic_row_count == 2
    assert velvet[0].quality_capped_supporting_rows == 1
    assert len([item for item in opportunities if item.symbol == "AAVE"]) == 1
    assert len([item for item in opportunities if item.symbol == "RUNE"]) == 1
    assert len([item for item in opportunities if item.symbol == "ZEC"]) == 1


def test_daily_brief_core_opportunity_excludes_promoted_supporting_near_miss():
    from dataclasses import replace
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    components = {
        "incident_id": "incident:spacex",
        "validated_symbol": "VELVET",
        "validated_coin_id": "velvet",
        "validation_stage": "impact_path_validated",
        "impact_category": "tokenized_stock_venue",
        "impact_path_type": "venue_value_capture",
        "impact_path_strength": "strong",
        "candidate_role": "proxy_venue",
        "evidence_quality_score": 90,
        "source_class": "crypto_native",
        "evidence_specificity": "asset_and_catalyst",
        "market_confirmation_score": 90,
        "market_confirmation_level": "strong",
        "opportunity_score_final": 94,
        "opportunity_level": "high_priority",
        "supporting_categories": ["tokenized_stock_venue", "rwa_preipo_proxy"],
        "supporting_impact_paths": ["venue_value_capture", "proxy_exposure"],
        "supporting_evidence_quotes": ["VELVET users can trade SpaceX pre-IPO exposure."],
    }
    entry = replace(
        _test_watchlist_entry(state=event_watchlist.EventWatchlistState.HIGH_PRIORITY.value, symbol="VELVET", coin_id="velvet"),
        key="incident:spacex|velvet|proxy_venue",
        incident_id="incident:spacex",
        relationship_type="impact_hypothesis",
        latest_score=94,
        highest_score=94,
        latest_score_components=components,
        should_alert=True,
        material_change_reasons=("initial_validated_hypothesis",),
    )
    decision = event_alpha_router.EventAlphaRouteDecision(
        entry=entry,
        route=event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH,
        alertable=True,
        reason="Validated impact hypothesis reached high-priority opportunity verdict (94).",
        lane=event_alpha_router.EventAlphaRouteLane.INSTANT_ESCALATION,
        final_route_after_quality_gate=event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
        opportunity_level="high_priority",
        opportunity_score_final=94,
    )
    near_support_row = {
        "hypothesis_id": "hyp:velvet:support",
        "incident_id": "incident:spacex",
        "validated_symbol": "VELVET",
        "validated_coin_id": "velvet",
        "candidate_role": "proxy_venue",
        "impact_category": "rwa_preipo_proxy",
        "impact_path_type": "proxy_exposure",
        "impact_path_strength": "medium",
        "evidence_quality_score": 70,
        "source_class": "crypto_native",
        "evidence_specificity": "asset_and_catalyst",
        "market_confirmation_score": 40,
        "market_confirmation_level": "weak",
        "opportunity_score_final": 61,
        "opportunity_level": "exploratory",
        "why_not_watchlist": "needs_market_confirmation",
        "upgrade_requirements": ["market_confirmation"],
    }
    brief = event_alpha_daily_brief.build_daily_brief(
        run_rows=[],
        hypothesis_rows=[near_support_row],
        watchlist_entries=[entry],
        router_result=event_alpha_router.EventAlphaRouterResult(Path("state.jsonl"), 1, [decision], True),
        requested_profile="fixture",
    )
    assert "core_" in brief
    assert "VELVET/velvet" in brief
    near_section = brief.split("## Near-Miss Candidates", 1)[1].split("## Quality-Capped / Local-Only Candidates", 1)[0]
    assert "VELVET/velvet" not in near_section


def test_daily_brief_core_sections_hide_promoted_from_exploratory_and_near_miss():
    from dataclasses import replace
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    def decision(symbol, *, state, route, level, score, path, incident):
        components = {
            "incident_id": incident,
            "validated_symbol": symbol,
            "validated_coin_id": symbol.lower(),
            "validation_stage": "impact_path_validated",
            "impact_category": path,
            "impact_path_type": path,
            "impact_path_strength": "strong",
            "candidate_role": "direct_subject",
            "evidence_quality_score": 82,
            "source_class": "crypto_native",
            "evidence_specificity": "asset_and_catalyst",
            "market_confirmation_score": 72,
            "market_confirmation_level": "moderate",
            "opportunity_score_final": score,
            "opportunity_level": level,
            "supporting_evidence_quotes": [f"{symbol} catalyst evidence"],
        }
        entry = replace(
            _test_watchlist_entry(state=state, symbol=symbol, coin_id=symbol.lower()),
            key=f"{incident}|{symbol.lower()}|direct_subject",
            incident_id=incident,
            relationship_type="impact_hypothesis",
            latest_score=score,
            highest_score=score,
            latest_score_components=components,
            latest_event_name=f"{symbol} validated catalyst",
            suppressed_reason="not suppressed",
        )
        return event_alpha_router.EventAlphaRouteDecision(
            entry=entry,
            route=route,
            alertable=event_alpha_router.route_value_is_alertable(route.value),
            reason=f"{symbol} routed",
            lane=event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST,
            final_route_after_quality_gate=route.value,
            opportunity_level=level,
            opportunity_score_final=score,
        )

    velvet = decision(
        "VELVET",
        state=event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        route=event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH,
        level="high_priority",
        score=94,
        path="venue_value_capture",
        incident="incident:spacex",
    )
    aave = decision(
        "AAVE",
        state=event_watchlist.EventWatchlistState.RADAR.value,
        route=event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST,
        level="validated_digest",
        score=72,
        path="strategic_investment_or_valuation",
        incident="incident:aave",
    )
    rune = decision(
        "RUNE",
        state=event_watchlist.EventWatchlistState.WATCHLIST.value,
        route=event_alpha_router.EventAlphaRoute.LOCAL_REPORT,
        level="watchlist",
        score=78,
        path="exploit_security_event",
        incident="incident:rune",
    )
    memecore = _notify_suppressed_decision("M", score=63, reason="local-only learning row")
    result = event_alpha_router.EventAlphaRouterResult(
        Path("state.jsonl"),
        4,
        [velvet, aave, rune, memecore],
        True,
    )
    brief = event_alpha_daily_brief.build_daily_brief(
        watchlist_entries=[velvet.entry, aave.entry, rune.entry, memecore.entry],
        router_result=result,
        requested_profile="fixture",
    )
    strong = brief.split("## High-Priority Core Opportunities", 1)[1].split("## Validated Digest Core Opportunities", 1)[0]
    digest = brief.split("## Validated Digest Core Opportunities", 1)[1].split("## Watchlist Core Opportunities", 1)[0]
    watchlist = brief.split("## Watchlist Core Opportunities", 1)[1].split("## Near-Miss Candidates", 1)[0]
    near = brief.split("## Near-Miss Candidates", 1)[1].split("## Upgrade Candidates", 1)[0]
    upgrades = brief.split("## Upgrade Candidates", 1)[1].split("## Quality-Capped / Local-Only Candidates", 1)[0]
    exploratory = brief.split("### Exploratory Digest", 1)[1].split("### Active Watchlist", 1)[0]
    diagnostics = brief.split("## Diagnostics Appendix", 1)[1]
    assert strong.count("VELVET/velvet") == 1
    assert digest.count("AAVE/aave") == 1
    assert watchlist.count("RUNE/rune") == 1
    assert "VELVET/velvet" not in near
    assert "AAVE/aave" not in near
    assert "RUNE/rune" not in near
    assert "AAVE/aave" in upgrades
    assert "RUNE/rune" in upgrades
    assert "VELVET/velvet" not in upgrades
    assert "VELVET/velvet" not in exploratory
    assert "AAVE/aave" not in exploratory
    assert "RUNE/rune" not in exploratory
    assert "M/m" in exploratory
    assert "### Active Watchlist" in diagnostics
    assert "### Validated Impact Hypothesis Routing" in diagnostics


def test_daily_brief_near_miss_and_card_groups_are_operator_friendly():
    from pathlib import Path
    import tempfile
    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief

    memecore = {
        "hypothesis_id": "hyp:memecore",
        "incident_id": "incident:memecore",
        "validated_symbol": "M",
        "validated_coin_id": "memecore",
        "candidate_role": "direct_subject",
        "impact_category": "market_anomaly_unknown",
        "impact_path_type": "market_dislocation_unknown",
        "source_class": "broad_news",
        "evidence_specificity": "direct_token_mechanism",
        "market_confirmation_score": 35,
        "market_confirmation_level": "weak",
        "opportunity_score_final": 61,
        "opportunity_level": "exploratory",
        "why_not_watchlist": ["needs_strong_market_confirmation", "cause_unknown_market_dislocation"],
        "upgrade_requirements": ["needs_direct_token_mechanism", "needs_market_confirmation"],
    }
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        core = root / "card_velvet.md"
        near = root / "card_memecore.md"
        local = root / "card_btc.md"
        diagnostic = root / "card_kcs.md"
        core.write_text("Final opportunity verdict: high_priority\nFinal route: HIGH_PRIORITY_RESEARCH\n", encoding="utf-8")
        near.write_text("Final opportunity verdict: exploratory\nFinal route: STORE_ONLY\n", encoding="utf-8")
        local.write_text("Final route: STORE_ONLY\nLocal-only after quality/state gate.\n", encoding="utf-8")
        diagnostic.write_text("Playbook: source_noise_control\nImpact path type: generic_cooccurrence_only\n", encoding="utf-8")
        brief = event_alpha_daily_brief.build_daily_brief(
            hypothesis_rows=[memecore],
            card_paths=[core, near, local, diagnostic],
            requested_profile="fixture",
            include_test_artifacts=True,
            include_api_artifacts=True,
        )
    near_section = brief.split("## Near-Miss Candidates", 1)[1].split("## Quality-Capped / Local-Only Candidates", 1)[0]
    assert "M/memecore" in near_section
    assert "token moved, but the cause is still unknown" in near_section
    assert "needs proof that this event directly affects the token" in near_section
    assert "needs_strong_market_confirmation" not in near_section
    cards = brief.split("### Research Cards", 1)[1].split("### Missed Opportunities", 1)[0]
    core_cards = cards.split("#### Core Opportunity Cards", 1)[1].split("#### Near-Miss Cards", 1)[0]
    near_cards = cards.split("#### Near-Miss Cards", 1)[1].split("#### Local-Only / Quality-Capped Cards", 1)[0]
    local_cards = cards.split("#### Local-Only / Quality-Capped Cards", 1)[1].split("#### Diagnostic / Source-Noise / Control Cards", 1)[0]
    diagnostic_cards = cards.split("#### Diagnostic / Source-Noise / Control Cards", 1)[1]
    assert "card_velvet.md" in core_cards
    assert "card_memecore.md" not in core_cards
    assert "card_memecore.md" in near_cards
    assert "card_btc.md" in local_cards
    assert "card_kcs.md" not in diagnostic_cards
    assert "Hidden from main card list" in diagnostic_cards


def test_research_card_index_groups_core_local_near_miss_and_diagnostics():
    from datetime import datetime, timezone
    from pathlib import Path
    import tempfile
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        core = root / "card_velvet.md"
        near = root / "card_memecore.md"
        local = root / "card_btc.md"
        diagnostic = root / "card_kcs.md"
        legacy = root / "legacy_old.md"
        core.write_text("Final opportunity verdict: high_priority\nFinal route: HIGH_PRIORITY_RESEARCH\n", encoding="utf-8")
        near.write_text("Final opportunity verdict: exploratory\nFinal route: LOCAL_REPORT\n", encoding="utf-8")
        local.write_text("Final route: STORE_ONLY\nLocal-only after quality/state gate.\n", encoding="utf-8")
        diagnostic.write_text("Playbook: source_noise_control\nImpact path type: generic_cooccurrence_only\n", encoding="utf-8")
        legacy.write_text("legacy card\n", encoding="utf-8")
        index = event_research_cards._render_index(
            [core, near, local, diagnostic, legacy],
            datetime(2026, 6, 20, tzinfo=timezone.utc),
        )
    assert "## Core Opportunity Cards" in index
    assert "card_velvet.md" in index.split("## Core Opportunity Cards", 1)[1].split("## Near-Miss Cards", 1)[0]
    assert "card_memecore.md" in index.split("## Near-Miss Cards", 1)[1].split("## Local-Only / Quality-Capped Cards", 1)[0]
    assert "card_btc.md" in index.split("## Local-Only / Quality-Capped Cards", 1)[1].split("## Diagnostic / Source-Noise / Control Cards", 1)[0]
    assert "card_kcs.md" in index.split("## Diagnostic / Source-Noise / Control Cards", 1)[1].split("## Legacy Cards", 1)[0]
    assert "legacy_old.md" in index.split("## Legacy Cards", 1)[1]


def test_research_card_index_collapses_near_miss_support_cards_by_asset_family():
    from pathlib import Path
    import tempfile
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        chz_primary = root / "card_chz_accepted.md"
        chz_support = root / "card_chz_support.md"
        velvet_openai = root / "card_velvet_openai.md"
        velvet_stripe = root / "card_velvet_stripe.md"
        chz_primary.write_text(
            "- Asset: CHZ/chiliz\n"
            "- Event: Portugal · sports event\n"
            "- Playbook: fan_token_attention\n"
            "- Final route: STORE_ONLY\n"
            "- Evidence acquisition result: status=accepted_evidence_found accepted=1 rejected=0\n",
            encoding="utf-8",
        )
        chz_support.write_text(
            "- Asset: CHZ/chiliz\n"
            "- Event: World Cup · unlock supply event\n"
            "- Playbook: unlock_supply_event\n"
            "- Final route: SUPPRESS_DUPLICATE\n"
            "- Evidence acquisition result: status=not_executed accepted=0 rejected=0\n",
            encoding="utf-8",
        )
        velvet_openai.write_text(
            "- Asset: VELVET/velvet\n"
            "- Event: OpenAI · ipo proxy\n"
            "- Playbook: listing_liquidity_event\n"
            "- Final route: STORE_ONLY\n",
            encoding="utf-8",
        )
        velvet_stripe.write_text(
            "- Asset: VELVET/velvet\n"
            "- Event: Stripe · ipo proxy\n"
            "- Playbook: listing_liquidity_event\n"
            "- Final route: STORE_ONLY\n",
            encoding="utf-8",
        )
        collapsed = event_research_cards.collapse_card_paths_for_group(
            [chz_support, velvet_openai, chz_primary, velvet_stripe],
            group_name="Near-Miss Cards",
        )

    assert len(collapsed) == 2
    by_name = {path.name: hidden for path, hidden in collapsed}
    assert by_name["card_chz_accepted.md"] == 1
    assert by_name["card_velvet_openai.md"] == 1


def test_opportunity_audit_accepts_core_opportunity_id_and_hides_diagnostics_by_default():
    import crypto_rsi_scanner.event_alpha.radar.core_opportunities as event_core_opportunities
    import crypto_rsi_scanner.event_alpha.artifacts.opportunity_audit as event_opportunity_audit

    primary = {
        "incident_id": "incident:aave",
        "canonical_incident_name": "Kraken stake in Aave",
        "validated_symbol": "AAVE",
        "validated_coin_id": "aave",
        "candidate_role": "direct_subject",
        "impact_category": "strategic_investment",
        "impact_path_type": "strategic_investment_or_valuation",
        "opportunity_level": "validated_digest",
        "opportunity_score_final": 72,
        "final_route_after_quality_gate": "RESEARCH_DIGEST",
        "final_state_after_quality_gate": "RADAR",
        "hypothesis_id": "hyp:aave:kraken",
        "key": "incident:aave|aave|direct_subject|strategic_investment",
        "alert_id": "ea:aave-kraken",
        "card_id": "card_aave_kraken",
        "snapshot_id": "snap:aave",
        "evidence_quotes": ["Kraken in talks to buy 15% stake in DeFi lender Aave."],
        "main_frame_type": "acquisition_or_stake",
        "main_frame_actor": "Kraken",
    }
    diagnostic = {
        **primary,
        "hypothesis_id": "hyp:aave:kelpdao-background",
        "candidate_role": "source_noise",
        "latest_effective_playbook_type": "source_noise_control",
        "impact_category": "security_or_regulatory_shock",
        "impact_path_type": "exploit_security_event",
        "opportunity_level": "local_only",
        "opportunity_score_final": 0,
    }
    core_id = event_core_opportunities.aggregate_core_opportunities([primary, diagnostic])[0].core_opportunity_id
    audit = event_opportunity_audit.format_opportunity_audit(
        core_id,
        hypotheses=[primary, diagnostic],
        profile="fixture",
    )
    assert "## Core Opportunity" in audit
    assert "## Operator Presentation" in audit
    assert "Daily brief section: Validated Digest Core Opportunities" in audit
    assert "Research card group: Core Opportunity Cards" in audit
    assert core_id in audit
    assert "Kraken" in audit
    assert "hidden diagnostics: 1" in audit
    assert "watchlist keys:" in audit
    assert "alert ids: ea:aave-kraken" in audit
    assert "card ids/paths: card_aave_kraken" in audit
    assert "  - diagnostic:" not in audit
    by_hypothesis = event_opportunity_audit.format_opportunity_audit(
        "hyp:aave:kraken",
        hypotheses=[primary, diagnostic],
        profile="fixture",
    )
    assert core_id in by_hypothesis
    by_incident = event_opportunity_audit.format_opportunity_audit(
        "incident:aave",
        hypotheses=[primary, diagnostic],
        profile="fixture",
    )
    assert "Kraken stake in Aave" in by_incident
    audit_with_diagnostics = event_opportunity_audit.format_opportunity_audit(
        core_id,
        hypotheses=[primary, diagnostic],
        profile="fixture",
        include_diagnostics=True,
    )
    assert "  - diagnostic:" in audit_with_diagnostics
    orphan_audit = event_opportunity_audit.format_opportunity_audit(
        "core_missing",
        core_opportunity_rows=[primary],
        profile="fixture",
    )
    assert "matched_source: none" in orphan_audit
    assert "input target resolution status: orphan" in orphan_audit
    assert "visible_core_missing_store_row:core_missing" in orphan_audit
    assert "No matching hypothesis, watchlist row, alert snapshot, or route decision found." in orphan_audit


def test_research_cards_have_current_lineage_and_api_marker():
    from dataclasses import replace
    import crypto_rsi_scanner.event_alpha.radar.core_opportunities as event_core_opportunities
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    entry = replace(
        _test_watchlist_entry(
            state=event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
            symbol="VELVET",
            coin_id="velvet",
        ),
        incident_id="incident:velvet:spacex",
        hypothesis_id="hyp:velvet:spacex",
        latest_score_components={
            **_test_watchlist_entry(
                state=event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
                symbol="VELVET",
                coin_id="velvet",
            ).latest_score_components,
            "run_id": "run-123",
            "profile": "catalyst_frame_e2e",
            "artifact_namespace": "catalyst_frame_e2e",
            "incident_id": "incident:velvet:spacex",
            "hypothesis_id": "hyp:velvet:spacex",
            "source_raw_ids": ["velvet_spacex"],
            "source_event_ids": ["velvet-spacex-preipo"],
        },
    )
    core_id = event_core_opportunities.core_opportunity_id_for_row(entry)
    card = event_research_cards.render_research_card(
        entry.key,
        watchlist_entries=[entry],
        card_path="/tmp/card_velvet.md",
    )
    assert "- Run ID: run-123" in card.markdown
    assert "- Profile: catalyst_frame_e2e" in card.markdown
    assert "- Namespace: catalyst_frame_e2e" in card.markdown
    assert "- Incident ID: incident:velvet:spacex" in card.markdown
    assert "- Hypothesis ID: hyp:velvet:spacex" in card.markdown
    assert f"- Core opportunity ID: {core_id}" in card.markdown
    assert "- Card path: card_velvet.md" in card.markdown
    assert f"- Feedback target: {core_id}" in card.markdown
    assert "- Feedback target type: core_opportunity_id" in card.markdown
    assert "make event-feedback-useful PROFILE=catalyst_frame_e2e" in card.markdown
    assert "raw=velvet_spacex" in card.markdown
    assert "legacy_lineage_missing: false" in card.markdown
    assert "Lineage status: legacy_lineage_missing" not in card.markdown
    assert "Run ID: legacy_lineage_missing" not in card.markdown

    legacy = _test_watchlist_entry(
        state=event_watchlist.EventWatchlistState.WATCHLIST.value,
        symbol="AAVE",
        coin_id="aave",
    )
    legacy_card = event_research_cards.render_research_card(legacy.key, watchlist_entries=[legacy])
    assert "Lineage status: legacy_lineage_missing" in legacy_card.markdown
    assert "legacy_lineage_missing: true" in legacy_card.markdown
    assert "- Run ID: legacy_lineage_missing" in legacy_card.markdown
