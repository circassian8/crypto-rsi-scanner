"""Focused Event Alpha operator behavior tests."""

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
