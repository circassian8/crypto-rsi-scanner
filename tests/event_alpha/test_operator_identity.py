"""Operator identity, role, and source-only normalization regressions."""

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

def test_event_asset_knowledge_and_role_validation_caps_taxonomy_and_broad_assets():
    import crypto_rsi_scanner.event_alpha.radar.identity as event_identity

    btc = event_identity.asset_knowledge_for(symbol="BTC", coin_id="bitcoin")
    rune = event_identity.asset_knowledge_for(symbol="RUNE", coin_id="thorchain")
    velvet = event_identity.asset_knowledge_for(symbol="VELVET", coin_id="velvet")
    link = event_identity.asset_knowledge_for(symbol="LINK", coin_id="chainlink")
    tether = event_identity.asset_knowledge_for(symbol="USDT", coin_id="tether")
    assert btc.broad_macro_asset is True
    assert rune.project_entities == ("THORChain",)
    assert velvet.role_capabilities.can_be_proxy_venue is True
    assert link.role_capabilities.can_be_infrastructure is True

    taxonomy = event_identity.validate_asset_role(
        link,
        event_identity.ROLE_DIRECT_SUBJECT,
        impact_category="security_or_regulatory_shock",
        role_source=event_identity.ROLE_SOURCE_TAXONOMY_CANDIDATE,
        source_text="THORChain confirms a RUNE exploit; Chainlink is an oracle taxonomy candidate.",
    )
    assert taxonomy.accepted is False
    assert taxonomy.final_role == event_identity.ROLE_GENERIC_MENTION
    assert "taxonomy_candidate_not_affected_asset" in taxonomy.failures

    broad = event_identity.validate_asset_role(
        btc,
        event_identity.ROLE_DIRECT_SUBJECT,
        impact_category="strategic_investment_or_valuation",
        source_text="Kraken buys a stake in Aave while Bitcoin markets are mentioned as context.",
        market_confirmation=20,
    )
    assert broad.accepted is False
    assert broad.final_role == event_identity.ROLE_MACRO_AFFECTED_ASSET
    assert "broad_macro_asset_context_only" in broad.failures

    stable = event_identity.validate_asset_role(
        tether,
        event_identity.ROLE_DIRECT_SUBJECT,
        impact_category="market_anomaly_unknown",
        source_text="USDT market anomaly without catalyst evidence.",
    )
    assert stable.accepted is False
    assert "stable_or_wrapped_asset_not_market_anomaly_candidate" in stable.failures


def test_event_impact_path_uses_asset_knowledge_for_roles_and_broad_context():
    from datetime import datetime, timezone
    from types import SimpleNamespace

    import crypto_rsi_scanner.event_alpha.radar.impact_path_validator as event_impact_path_validator
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent

    now = datetime(2026, 6, 20, tzinfo=timezone.utc)

    def raw(raw_id: str, title: str, body: str) -> RawDiscoveredEvent:
        return RawDiscoveredEvent(
            raw_id=raw_id,
            provider="fixture_news",
            fetched_at=now,
            published_at=now,
            source_url=f"https://example.com/{raw_id}",
            title=title,
            body=body,
            raw_json={},
            source_confidence=0.90,
            content_hash=raw_id,
        )

    aave_raw = raw(
        "aave_kraken",
        "Kraken buys strategic stake in Aave",
        "Kraken acquired a strategic stake in Aave; Bitcoin is mentioned only as broad market context.",
    )
    aave_hypothesis = SimpleNamespace(
        impact_category="strategic_investment_or_valuation",
        external_asset="Kraken",
        score_components={"validation_strength": 95, "market_confirmation": 45},
    )
    aave = event_impact_path_validator.validate_impact_path(
        aave_raw,
        aave_hypothesis,
        symbol="AAVE",
        coin_id="aave",
        score_components=aave_hypothesis.score_components,
    )
    assert aave.candidate_role == "direct_subject"
    assert aave.asset_kind == "protocol_token"
    assert aave.role_validation_failures == ()

    btc = event_impact_path_validator.validate_impact_path(
        aave_raw,
        aave_hypothesis,
        symbol="BTC",
        coin_id="bitcoin",
        score_components=aave_hypothesis.score_components,
    )
    assert btc.candidate_role == "macro_affected_asset"
    assert btc.impact_path_strength == "weak"
    assert btc.digest_eligible_by_impact_path is False
    assert "broad_macro_asset_context_only" in btc.role_validation_failures

    link = event_impact_path_validator.validate_impact_path(
        raw(
            "thor_link",
            "THORChain confirms RUNE exploit",
            "THORChain confirms a RUNE exploit; Chainlink appears only as an oracle taxonomy candidate.",
        ),
        SimpleNamespace(impact_category="security_or_regulatory_shock", external_asset="THORChain", score_components={"role_source": "taxonomy_candidate"}),
        symbol="LINK",
        coin_id="chainlink",
        score_components={"role_source": "taxonomy_candidate", "validation_strength": 40},
    )
    assert link.candidate_role == "generic_mention"
    assert link.role_source == "taxonomy_candidate"
    assert "taxonomy_candidate_not_affected_asset" in link.role_validation_failures

    velvet = event_impact_path_validator.validate_impact_path(
        raw(
            "velvet_spacex",
            "VELVET offers SpaceX pre-IPO exposure",
            "Velvet lets users trade tokenized stock exposure to SpaceX pre-IPO markets.",
        ),
        SimpleNamespace(impact_category="tokenized_stock_venue", external_asset="SpaceX", score_components={"validation_strength": 95}),
        symbol="VELVET",
        coin_id="velvet",
        score_components={"validation_strength": 95, "market_confirmation": 50},
    )
    assert velvet.candidate_role == "proxy_venue"
    assert velvet.asset_kind == "tokenized_equity_venue"
    assert velvet.digest_eligible_by_impact_path is True


def test_event_resolver_outputs_identity_metadata_and_rejects_generic_hype():
    from datetime import datetime, timezone

    from crypto_rsi_scanner.event_core.models import DiscoveredAsset, NormalizedEvent
    from crypto_rsi_scanner.event_alpha.radar.resolver import resolve_event_assets

    now = datetime(2026, 6, 20, tzinfo=timezone.utc)
    assets = [
        DiscoveredAsset("hyperliquid", "HYPE", "Hyperliquid", aliases=("hyperliquid", "hype")),
        DiscoveredAsset("bitcoin", "BTC", "Bitcoin", aliases=("bitcoin", "btc")),
    ]
    generic = NormalizedEvent(
        event_id="evt_hype_generic",
        raw_ids=("raw",),
        event_name="IPO hype builds before SpaceX listing",
        event_type="news",
        event_time=None,
        event_time_confidence=0.0,
        first_seen_time=now,
        source="fixture",
        source_urls=(),
        external_asset="SpaceX",
        description="Market hype rises, but no crypto project is named.",
        confidence=0.85,
    )
    assert resolve_event_assets(generic, assets) == []

    direct = NormalizedEvent(
        event_id="evt_hyperliquid",
        raw_ids=("raw",),
        event_name="Hyperliquid launches HYPEUSDT perp",
        event_type="perp_listing",
        event_time=None,
        event_time_confidence=0.0,
        first_seen_time=now,
        source="fixture",
        source_urls=(),
        external_asset="Hyperliquid",
        description="Hyperliquid lists HYPEUSDT and references the HYPE token.",
        confidence=0.90,
    )
    link = resolve_event_assets(direct, assets)[0]
    assert link.symbol == "HYPE"
    assert link.matched_field in {"coin_id", "alias", "symbol", "name_and_symbol"}
    assert link.identity_confidence and link.identity_confidence >= 80
    assert link.collision_risk == "high"
    assert link.role_source in {"resolver_exact", "market_symbol_only"}


def test_event_operator_surfaces_show_asset_identity_metadata():
    from dataclasses import replace

    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief
    import crypto_rsi_scanner.event_alpha.artifacts.opportunity_audit as event_opportunity_audit
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    components = {
        "validated_symbol": "VELVET",
        "validated_coin_id": "velvet",
        "impact_path_type": "venue_value_capture",
        "impact_path_strength": "strong",
        "candidate_role": "proxy_venue",
        "asset_kind": "tokenized_equity_venue",
        "role_source": "resolver_exact",
        "identity_confidence": 95.0,
        "identity_evidence": ["VELVET offers SpaceX pre-IPO tokenized stock exposure"],
        "collision_risk": "none",
        "role_capabilities": {"can_be_proxy_venue": True, "can_be_market_anomaly": True},
        "role_validation_failures": [],
        "evidence_quality_score": 85,
        "source_class": "cryptopanic_tagged",
        "evidence_specificity": "direct_token_mechanism",
        "market_confirmation_score": 75,
        "market_confirmation_level": "confirmed",
        "market_context_freshness_status": "fresh",
        "market_context_age_hours": 0.2,
        "market_context_stale": False,
        "market_context_freshness_cap_applied": False,
        "opportunity_score_final": 92,
        "opportunity_level": "high_priority",
        "opportunity_verdict_reasons": ["proxy_impact_path_explained"],
        "why_local_only": "not_local_only",
        "why_not_watchlist": "not_watchlist",
        "manual_verification_items": ["verify source and liquidity"],
        "upgrade_requirements": [],
        "downgrade_warnings": [],
    }
    entry = replace(
        _test_watchlist_entry(state=event_watchlist.EventWatchlistState.HIGH_PRIORITY.value, symbol="VELVET", coin_id="velvet"),
        key="incident-spacex|velvet|proxy_venue",
        relationship_type="impact_hypothesis",
        latest_score_components=components,
        latest_event_name="SpaceX proxy exposure",
    )
    card = event_research_cards.render_research_card(entry.key, watchlist_entries=[entry])
    assert "Asset kind: tokenized_equity_venue" in card.markdown
    assert "Role source: resolver_exact" in card.markdown
    assert "Identity evidence: VELVET offers SpaceX pre-IPO tokenized stock exposure" in card.markdown
    brief = event_alpha_daily_brief.build_daily_brief(watchlist_entries=[entry], requested_profile="fixture")
    assert "asset_kind=tokenized_equity_venue" in brief
    assert "role_source=resolver_exact" in brief
    audit = event_opportunity_audit.format_opportunity_audit(
        entry.key,
        watchlist_entries=[entry],
        profile="fixture",
    )
    assert "asset kind: tokenized_equity_venue" in audit
    assert "role capabilities: can_be_market_anomaly, can_be_proxy_venue" in audit


def test_live_confirmation_caps_source_only_narrative_digest_without_market():
    import crypto_rsi_scanner.event_alpha.radar.opportunity_verdict as event_opportunity_verdict

    verdict = event_opportunity_verdict.apply_live_confirmation_policy(
        {
            "profile": "notify_llm_deep",
            "artifact_namespace": "notify_llm_deep_cryptopanic_rehearsal",
            "symbol": "CHZ",
            "coin_id": "chiliz",
            "source_pack": "fan_sports_pack",
            "final_opportunity_level": "validated_digest",
            "opportunity_level": "validated_digest",
            "opportunity_score_final": 72,
            "impact_path_type": "fan_token_event",
            "evidence_acquisition_status": "accepted_evidence_found",
            "evidence_acquisition_accepted_count": 1,
            "accepted_provider_counts": {"cryptopanic": 1},
            "accepted_evidence_reason_codes": ["cryptopanic_currency_tag_match", "direct_token_mechanism"],
            "market_confirmation_level": "none",
            "market_context_freshness_status": "missing",
        }
    )
    assert verdict.required is True
    assert verdict.confirmed is False
    assert verdict.capped_level == "exploratory"
    assert verdict.reason == "source_only_narrative_without_market_confirmation"

    confirmed = event_opportunity_verdict.apply_live_confirmation_policy(
        {
            "profile": "notify_llm_deep",
            "artifact_namespace": "notify_llm_deep_cryptopanic_rehearsal",
            "symbol": "CHZ",
            "coin_id": "chiliz",
            "source_pack": "fan_sports_pack",
            "final_opportunity_level": "validated_digest",
            "opportunity_level": "validated_digest",
            "opportunity_score_final": 72,
            "impact_path_type": "fan_token_event",
            "evidence_acquisition_status": "accepted_evidence_found",
            "evidence_acquisition_accepted_count": 1,
            "accepted_provider_counts": {"cryptopanic": 1},
            "accepted_evidence_reason_codes": ["cryptopanic_currency_tag_match"],
            "market_confirmation_level": "moderate",
            "market_confirmation_score": 55,
            "market_context_freshness_status": "fresh",
        }
    )
    assert confirmed.confirmed is True
    assert confirmed.capped_level is None

    mispacked_unlock = event_opportunity_verdict.apply_live_confirmation_policy(
        {
            "profile": "notify_llm_deep",
            "artifact_namespace": "notify_llm_deep_cryptopanic_rehearsal",
            "symbol": "CHZ",
            "coin_id": "chiliz",
            "source_pack": "unlock_supply_pack",
            "source_class": "cryptopanic_tagged",
            "final_opportunity_level": "validated_digest",
            "opportunity_level": "validated_digest",
            "opportunity_score_final": 72,
            "impact_path_type": "unlock_supply_event",
            "supporting_categories": ["sports_fan_proxy"],
            "supporting_impact_paths": ["fan_token_attention"],
            "evidence_acquisition_status": "not_executed",
            "accepted_evidence_reason_codes": ["cryptopanic_currency_tag_match"],
            "market_confirmation_level": "none",
            "market_context_freshness_status": "missing",
        }
    )
    assert mispacked_unlock.confirmed is False
    assert mispacked_unlock.reason == "source_only_narrative_without_market_confirmation"

    structured_unlock = event_opportunity_verdict.apply_live_confirmation_policy(
        {
            "profile": "notify_llm_deep",
            "artifact_namespace": "notify_llm_deep_cryptopanic_rehearsal",
            "symbol": "UNLK",
            "coin_id": "unlock-token",
            "source_pack": "unlock_supply_pack",
            "source_class": "structured_unlock",
            "final_opportunity_level": "validated_digest",
            "opportunity_level": "validated_digest",
            "opportunity_score_final": 78,
            "impact_path_type": "unlock_supply_event",
            "evidence_acquisition_status": "accepted_evidence_found",
            "evidence_acquisition_accepted_count": 1,
            "accepted_provider_counts": {"tokenomist": 1},
            "accepted_evidence_reason_codes": ["structured_unlock_evidence", "tokenomist_unlock_match"],
            "market_context_freshness_status": "missing",
        }
    )
    assert structured_unlock.confirmed is True
    assert structured_unlock.capped_level is None


def test_core_store_load_normalizes_stale_source_only_narrative_digest():
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store

    stale = {
        "row_type": "event_core_opportunity",
        "schema_version": "event_core_opportunity_store_v1",
        "profile": "notify_llm_deep",
        "artifact_namespace": "notify_llm_deep_cryptopanic_rehearsal",
        "core_opportunity_id": "core_chz_source_only",
        "symbol": "CHZ",
        "coin_id": "chiliz",
        "incident_id": "world-cup-chz",
        "candidate_role": "direct_subject",
        "primary_impact_path": "fan_token_event",
        "impact_path_type": "fan_token_event",
        "opportunity_level": "validated_digest",
        "final_opportunity_level": "validated_digest",
        "opportunity_score_final": 72,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
        "final_state_after_quality_gate": "RADAR",
        "source_pack": "fan_sports_pack",
        "evidence_acquisition_status": "accepted_evidence_found",
        "evidence_acquisition_accepted_count": 1,
        "accepted_provider_counts": {"cryptopanic": 1},
        "accepted_evidence_reason_codes": ["cryptopanic_currency_tag_match"],
        "market_confirmation_level": "none",
        "market_context_freshness_status": "missing",
    }
    opportunity = event_core_opportunity_store.core_opportunities_from_rows([stale])[0]
    assert opportunity.opportunity_level == "exploratory"
    assert opportunity.final_route_after_quality_gate == event_alpha_router.EventAlphaRoute.STORE_ONLY.value
    assert opportunity.primary_row["live_confirmation_reason"] == "source_only_narrative_without_market_confirmation"

    stale_mispacked = {
        **stale,
        "core_opportunity_id": "core_chz_mispacked_unlock",
        "primary_impact_path": "unlock_supply_event",
        "impact_path_type": "unlock_supply_event",
        "source_pack": "unlock_supply_pack",
        "source_class": "cryptopanic_tagged",
        "evidence_acquisition_status": "not_executed",
        "evidence_acquisition_accepted_count": 0,
        "accepted_evidence_reason_codes": ["cryptopanic_currency_tag_match"],
        "supporting_categories": ["sports_fan_proxy"],
        "supporting_impact_paths": ["fan_token_attention"],
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE.value,
    }
    mispacked = event_core_opportunity_store.core_opportunities_from_rows([stale_mispacked])[0]
    assert mispacked.opportunity_level == "exploratory"
    assert mispacked.is_validated_digest is False
    assert mispacked.primary_row["live_confirmation_reason"] == "source_only_narrative_without_market_confirmation"


def test_core_store_normalize_rewrites_raw_source_only_narrative_digest():
    import json

    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store

    stale = {
        "row_type": "event_core_opportunity",
        "schema_version": "event_core_opportunity_store_v1",
        "run_id": "run-chz",
        "profile": "notify_llm_deep",
        "run_mode": "notification_burn_in",
        "artifact_namespace": "notify_llm_deep_cryptopanic_rehearsal",
        "core_opportunity_id": "core_chz_mispacked_unlock",
        "symbol": "CHZ",
        "coin_id": "chiliz",
        "incident_id": "world-cup-chz",
        "candidate_role": "proxy_instrument",
        "primary_impact_path": "unlock_supply_event",
        "impact_path_type": "unlock_supply_event",
        "opportunity_level": "validated_digest",
        "final_opportunity_level": "validated_digest",
        "opportunity_score_final": 72,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE.value,
        "source_pack": "unlock_supply_pack",
        "source_class": "cryptopanic_tagged",
        "evidence_acquisition_status": "not_executed",
        "accepted_evidence_count": 0,
        "accepted_evidence_reason_codes": ["cryptopanic_currency_tag_match"],
        "market_confirmation_level": "none",
        "market_context_freshness_status": "missing",
        "supporting_categories": ["sports_fan_proxy"],
        "supporting_impact_paths": ["fan_token_attention", "fan_token_event"],
        "live_confirmation_status": "confirmed",
        "generated_at": "2026-07-01T00:00:00+00:00",
    }
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_core_opportunities.jsonl"
        path.write_text(json.dumps(stale) + "\n", encoding="utf-8")
        result = event_core_opportunity_store.normalize_core_opportunity_store(path, latest_run=True)
        raw = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert result.success is True
    assert result.rows_updated == 1
    assert raw[0]["opportunity_level"] == "exploratory"
    assert raw[0]["final_opportunity_level"] == "exploratory"
    assert raw[0]["requested_opportunity_level_before_live_confirmation"] == "validated_digest"
    assert raw[0]["live_confirmation_status"] != "confirmed"
    assert raw[0]["live_confirmation_reason"] == "source_only_narrative_without_market_confirmation"
    assert raw[0]["final_route_after_quality_gate"] not in {
        event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
        event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
    }
