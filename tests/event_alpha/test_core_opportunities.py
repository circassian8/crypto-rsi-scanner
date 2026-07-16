"""Core-opportunity storage and operator-view regressions."""

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

def test_event_watchlist_validated_hypothesis_market_confirmation_promotes_state():
    import tempfile
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    hypothesis = SimpleNamespace(
        hypothesis_id="h-velvet",
        event_cluster_id="spacex|ipo|2026-06-20",
        status="validated",
        validation_stage="impact_path_validated",
        hypothesis_score=82,
        confidence=0.82,
        candidate_symbols=("VELVET",),
        candidate_coin_ids=("velvet",),
        validated_symbol="VELVET",
        validated_coin_id="velvet",
        candidate_sectors=("tokenized_stock_venues",),
        source_raw_ids=("r1", "r2"),
        impact_category="rwa_preipo_proxy",
        hypothesis_scope="token",
        playbook_hint="proxy_attention",
        external_asset="SpaceX",
        opportunity_level="watchlist",
        opportunity_score_final=82,
        market_confirmation_level="moderate",
        market_confirmation_score=62,
        evidence_quality_score=78,
        source_class="crypto_news",
        evidence_specificity="direct_value_capture",
        impact_path_type="proxy_exposure",
        impact_path_strength="strong",
        candidate_role="proxy_venue",
        score_components={"event_clarity": 80, "derivatives_crowding": 20},
    )
    with tempfile.TemporaryDirectory() as tmp:
        result = event_watchlist.refresh_hypothesis_watchlist(
            [hypothesis],
            cfg=event_watchlist.EventWatchlistConfig(enabled=True, state_path=__import__("pathlib").Path(tmp) / "watch.jsonl"),
            now=datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc),
        )
    entry = result.entries[0]
    assert entry.state == event_watchlist.EventWatchlistState.WATCHLIST.value
    assert entry.latest_tier == "WATCHLIST"
    assert "market_confirmation_upgraded" in entry.material_change_reasons
    assert entry.should_alert
    assert entry.state != event_watchlist.EventWatchlistState.TRIGGERED_FADE.value


def test_event_incident_primary_subject_validator_quarantines_garbage_before_persistence():
    from datetime import datetime, timezone
    from pathlib import Path
    import tempfile

    import crypto_rsi_scanner.event_alpha.radar.incident_graph as event_incident_graph
    import crypto_rsi_scanner.event_alpha.radar.incidents as event_incident_store
    from crypto_rsi_scanner.event_core.models import EventDiscoveryResult, NormalizedEvent, RawDiscoveredEvent

    invalid_subjects = (
        "About",
        "All",
        "Best Prediction Market Apps",
        "Bitcoin And MSTR Are",
        "During",
        "Here",
        "LLM",
        "Need",
        "Not",
        "Polymarket Invite Code SBWIRE",
        "Polymarket Referral Code SBWIRE",
    )
    for subject in invalid_subjects:
        result = event_incident_graph.validate_incident_primary_subject(subject)
        assert result.status in {"invalid_subject", "diagnostic_only"}
        assert result.normalized_subject is None
    assert event_incident_graph.validate_incident_primary_subject("OpenAI This").normalized_subject == "OpenAI"
    assert event_incident_graph.validate_incident_primary_subject("World Cup").normalized_subject == "World Cup"
    for subject in ("SpaceX", "OpenAI", "Anthropic", "THORChain", "SecondFi", "Solana"):
        assert event_incident_graph.validate_incident_primary_subject(subject).status == "valid"

    now = datetime(2026, 6, 26, 16, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        "raw_about",
        "fixture_news",
        now,
        now,
        "https://example.com/about",
        "About",
        "About unlock supply event with no validated crypto subject.",
        {},
        0.72,
        "hash-about",
    )
    event = NormalizedEvent(
        "evt_about",
        (raw.raw_id,),
        "About",
        "unlock",
        None,
        0.0,
        now,
        "fixture_news",
        (raw.source_url,),
        "About",
        raw.body,
        0.72,
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_incidents.jsonl"
        write = event_incident_store.write_incidents(
            EventDiscoveryResult((raw,), (event,), (), (), ()),
            cfg=event_incident_store.EventIncidentStoreConfig(path=path, store_diagnostic=True),
            now=now,
            run_id="run-about",
            profile="notify_llm_quality",
            run_mode="notification_burn_in",
            artifact_namespace="notify_llm_quality",
        )
        assert write.success is True
        loaded = event_incident_store.load_incidents(path)
        assert loaded.rows[0]["diagnostic_only"] is True
        assert loaded.rows[0]["incident_subject_quality"] == "diagnostic_only"
        assert loaded.rows[0]["incident_relevance_status"] == "diagnostic_only"
        assert loaded.rows[0]["canonical_persistence_reason"] == "diagnostic_subject_only"
        report = event_incident_store.format_incidents_report(loaded)
        assert "diagnostic_rows_hidden: 1" in report
        visible = event_incident_store.load_incidents(path, include_diagnostic=True)
        visible_report = event_incident_store.format_incidents_report(visible)
        assert "diagnostic_rows_hidden: 0" in visible_report


def test_event_llm_evidence_planner_fixture_cases():
    import crypto_rsi_scanner.event_alpha.radar.llm.evidence_planner as event_llm_evidence_planner

    aave = event_llm_evidence_planner.plan_evidence({
        "core_opportunity_id": "core:aave",
        "symbol": "AAVE",
        "coin_id": "aave",
        "external_asset": "Kraken",
        "playbook_type": "strategic_investment",
        "impact_path_type": "strategic_investment_or_valuation",
        "opportunity_score_final": 72,
        "opportunity_level": "validated_digest",
        "missing_requirements": ("official_source",),
    })
    assert aave.selected is True
    assert aave.source_pack == "strategic_investment_pack"
    assert any("AAVE" in query.query and "Kraken" in query.query for query in aave.query_plan)
    assert any("denies" in query.query.casefold() for query in aave.denial_searches)
    assert aave.official_confirmation_queries
    assert "official_confirmation" in aave.query_intents
    assert any("valuation" in item or "stake" in item for item in aave.expected_proof_criteria)
    assert "confirm token/project identity with non-URL evidence" in aave.checklist

    velvet = event_llm_evidence_planner.plan_evidence({
        "core_opportunity_id": "core:velvet",
        "symbol": "VELVET",
        "coin_id": "velvet",
        "external_asset": "SpaceX",
        "playbook_type": "proxy_attention",
        "impact_path_type": "venue_value_capture",
        "candidate_role": "proxy_venue",
        "opportunity_score_final": 79,
        "opportunity_level": "watchlist",
    })
    assert velvet.source_pack == "proxy_preipo_rwa_pack"
    assert any(query.provider_hint == "polymarket" and query.must_validate_asset is False for query in velvet.query_plan)
    assert velvet.market_refresh_requests == ("velvet",)
    assert any("external exposure mechanism" in item for item in velvet.expected_proof_criteria)
    assert "check denial/correction sources for proxy relationship" in velvet.manual_checklist

    rune = event_llm_evidence_planner.plan_evidence({
        "core_opportunity_id": "core:rune",
        "symbol": "RUNE",
        "coin_id": "thorchain",
        "playbook_type": "security_or_regulatory_shock",
        "impact_path_type": "exploit_security_event",
        "opportunity_score_final": 80,
        "opportunity_level": "watchlist",
    })
    assert rune.source_pack == "security_shock_pack"
    assert any("exploit" in query.query.casefold() for query in rune.query_plan)
    assert any("denial" in item.casefold() for item in rune.expected_proof_criteria)

    generic = event_llm_evidence_planner.plan_evidence({
        "core_opportunity_id": "core:generic",
        "symbol": "BTC",
        "coin_id": "bitcoin",
        "provider": "polymarket",
        "playbook_type": "political_meme_proxy",
        "opportunity_score_final": 45,
        "opportunity_level": "local_only",
    })
    assert generic.selected is False
    assert "planner_not_selected_below_prefilter" in generic.warnings
    assert generic.source_pack == "political_meme_pack"
    assert "prediction_market_context_only_until_token_identity_validated" in generic.warnings


def test_event_llm_evidence_planner_contradiction_summary_and_budget():
    import crypto_rsi_scanner.event_alpha.radar.llm.evidence_planner as event_llm_evidence_planner

    exploit_denied = {
        "core_opportunity_id": "core:aave-denial",
        "symbol": "AAVE",
        "coin_id": "aave",
        "event_name": "Aave not hacked after KelpDAO exploit rumors",
        "playbook_type": "security_or_regulatory_shock",
        "impact_path_type": "exploit_security_event",
        "opportunity_score_final": 70,
        "opportunity_level": "watchlist",
    }
    contradiction = event_llm_evidence_planner.detect_contradiction_or_denial(exploit_denied)
    assert contradiction.blocks_validation is True
    assert contradiction.reason == "exploit_or_hack_denied"
    assert any("exploit" in query.query.casefold() for query in contradiction.denial_queries)
    planned = event_llm_evidence_planner.plan_evidence(exploit_denied)
    assert "exploit_denial_blocks_security_path" in planned.warnings

    listing_denied = event_llm_evidence_planner.detect_contradiction_or_denial({
        "symbol": "TEST",
        "coin_id": "test-token",
        "event_name": "Exchange denies listing TEST after fake listing rumor",
        "playbook_type": "listing_volatility",
        "impact_path_type": "listing_liquidity_event",
        "opportunity_score_final": 64,
        "opportunity_level": "validated_digest",
    })
    assert listing_denied.blocks_validation is True
    assert listing_denied.reason == "listing_denied_or_fake"

    velvet_row = {
        "core_opportunity_id": "core:velvet-summary",
        "symbol": "VELVET",
        "coin_id": "velvet",
        "external_asset": "SpaceX",
        "playbook_type": "proxy_attention",
        "impact_path_type": "venue_value_capture",
        "candidate_role": "proxy_venue",
        "opportunity_score_final": 82,
        "opportunity_level": "high_priority",
        "final_route_after_quality_gate": "HIGH_PRIORITY_RESEARCH",
        "evidence_acquisition_plan": planned.to_metadata(),
    }
    velvet_plan = event_llm_evidence_planner.plan_evidence(velvet_row)
    summary = event_llm_evidence_planner.generate_analyst_summary(velvet_row, plan=velvet_plan)
    assert "VELVET surfaced as high_priority" in summary.why_surfaced
    assert "SpaceX" not in summary.why_surfaced  # summary is sourced from structured route fields, not invented copy.
    assert "source" in summary.what_would_upgrade.casefold() or "evidence" in summary.what_would_upgrade.casefold()
    assert any("identity" in item for item in summary.what_to_check_next)

    weak_btc = {
        "core_opportunity_id": "core:btc-weak",
        "symbol": "BTC",
        "coin_id": "bitcoin",
        "event_name": "Bitcoin World writes broad policy recap",
        "playbook_type": "political_meme_proxy",
        "impact_path_type": "insufficient_data",
        "opportunity_score_final": 0,
        "opportunity_level": "local_only",
        "final_route_after_quality_gate": "STORE_ONLY",
        "why_local_only": ("missing_direct_impact_path",),
    }
    weak_summary = event_llm_evidence_planner.generate_analyst_summary(weak_btc)
    assert "Not alertable" in weak_summary.why_not_alertable
    assert "missing_direct_impact_path" in weak_summary.why_not_alertable

    budget = event_llm_evidence_planner.select_llm_analyst_tools(
        [
            {
                "core_opportunity_id": "core:triage",
                "symbol": "RUNE",
                "coin_id": "thorchain",
                "source_url": "https://fixture.test/rune",
                "source_triage_decision": "send_to_llm_frame_analyzer",
                "playbook_type": "security_or_regulatory_shock",
                "impact_path_type": "exploit_security_event",
                "opportunity_score_final": 80,
                "opportunity_level": "watchlist",
            },
            {
                "core_opportunity_id": "core:budget-skip",
                "symbol": "AAVE",
                "coin_id": "aave",
                "source_url": "https://fixture.test/aave",
                "playbook_type": "strategic_investment",
                "impact_path_type": "strategic_investment_or_valuation",
                "opportunity_score_final": 78,
                "opportunity_level": "validated_digest",
            },
        ],
        cfg=event_llm_evidence_planner.LLMAnalystToolBudgetConfig(provider="fixture", max_calls_per_run=3),
    )
    assert budget.triage_llm_calls == 1
    assert budget.query_planner_llm_calls == 1
    assert budget.summary_llm_calls == 1
    assert budget.skipped_by_budget == 1

    missing_key = event_llm_evidence_planner.select_llm_analyst_tools(
        [weak_btc],
        cfg=event_llm_evidence_planner.LLMAnalystToolBudgetConfig(provider="openai", api_key_present=False),
    )
    assert missing_key.skipped_missing_api_key == 1
    assert "missing_api_key" in missing_key.warnings


def test_event_near_miss_source_pack_and_operator_surfaces():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief
    import crypto_rsi_scanner.event_alpha.radar.near_miss as event_near_miss
    import crypto_rsi_scanner.event_alpha.artifacts.opportunity_audit as event_opportunity_audit
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    row = {
        "hypothesis_id": "hyp:velvet-source-gap",
        "event_cluster_id": "cluster:spacex",
        "symbol": "VELVET",
        "coin_id": "velvet",
        "validated_symbol": "VELVET",
        "validated_coin_id": "velvet",
        "external_asset": "SpaceX",
        "provider": "gdelt",
        "provider_coverage_status": "degraded",
        "title": "SpaceX IPO coverage mentions Velvet exposure",
        "playbook_type": "proxy_attention",
        "impact_category": "tokenized_stock_venue",
        "impact_path_type": "venue_value_capture",
        "candidate_role": "proxy_venue",
        "source_class": "broad_news",
        "evidence_specificity": "token_and_catalyst",
        "evidence_quality_score": 58,
        "market_confirmation_score": 35,
        "opportunity_score_final": 64,
        "opportunity_level": "exploratory",
        "missing_requirements": ("impact_path_validation", "source evidence"),
        "why_not_watchlist": "impact_path_not_validated",
        "score_components": {
            "validated_symbol": "VELVET",
            "validated_coin_id": "velvet",
            "external_asset": "SpaceX",
            "playbook_type": "proxy_attention",
            "impact_category": "tokenized_stock_venue",
            "impact_path_type": "venue_value_capture",
            "candidate_role": "proxy_venue",
            "source_class": "broad_news",
            "evidence_specificity": "token_and_catalyst",
            "evidence_quality_score": 58,
            "market_confirmation_score": 35,
            "opportunity_score_final": 64,
            "opportunity_level": "exploratory",
            "missing_requirements": ("impact_path_validation", "source evidence"),
            "why_not_watchlist": "impact_path_not_validated",
        },
    }
    near = event_near_miss.detect_near_miss_rows((row,), cfg=event_near_miss.EventNearMissConfig())
    assert len(near) == 1
    assert near[0].source_pack == "proxy_preipo_rwa_pack"
    assert near[0].provider_coverage_status == "degraded"
    assert near[0].source_coverage_gap == "provider_coverage_degraded:gdelt"
    assert near[0].evidence_absence_is_meaningful is False
    assert "source_pack_search" in near[0].recommended_refresh_actions
    assert near[0].evidence_acquisition_attempted is True
    assert near[0].evidence_acquisition_plan["evidence_acquisition_source_pack"] == "proxy_preipo_rwa_pack"

    report = event_near_miss.format_near_miss_report(near, profile="quality_validation")
    assert "source_pack: proxy_preipo_rwa_pack" in report
    assert "coverage=degraded" in report
    assert "evidence_plan:" in report

    brief = event_alpha_daily_brief.build_daily_brief(
        hypothesis_rows=[{**row, "profile": "quality_validation", "artifact_namespace": "quality_validation", "run_mode": "notification_burn_in"}],
        requested_profile="quality_validation",
        artifact_namespace="quality_validation",
    )
    assert "## Source Coverage / Evidence Acquisition" in brief
    assert "Candidates Blocked by Source Coverage" in brief
    assert "VELVET/velvet" in brief

    entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="hypothesis|cluster:spacex|velvet",
        cluster_id="cluster:spacex",
        event_id="hyp:velvet-source-gap",
        coin_id="velvet",
        symbol="VELVET",
        relationship_type="impact_hypothesis",
        external_asset="SpaceX",
        event_time=None,
        state=event_watchlist.EventWatchlistState.RADAR.value,
        previous_state=None,
        first_seen_at=datetime(2026, 6, 15, tzinfo=timezone.utc).isoformat(),
        last_seen_at=datetime(2026, 6, 15, tzinfo=timezone.utc).isoformat(),
        latest_source="gdelt",
        latest_playbook_type="proxy_attention",
        latest_score_components={
            **row["score_components"],
            "source_pack": near[0].source_pack,
            "provider_coverage_status": near[0].provider_coverage_status,
            "evidence_absence_is_meaningful": near[0].evidence_absence_is_meaningful,
            "source_coverage_gap": near[0].source_coverage_gap,
            "source_quality_prior": near[0].source_quality_prior,
            "source_confidence_cap": near[0].source_confidence_cap,
            "evidence_acquisition_attempted": near[0].evidence_acquisition_attempted,
            "evidence_acquisition_plan": near[0].evidence_acquisition_plan,
            "evidence_acquisition_failures": near[0].evidence_acquisition_failures,
        },
    )
    card = event_research_cards.render_research_card(entry.key, watchlist_entries=[entry])
    assert "## Analyst Summary" in card.markdown
    assert "Why surfaced: VELVET surfaced" in card.markdown
    assert "What would upgrade: source/evidence proof:" in card.markdown
    assert "## Technical Evidence Acquisition Detail" in card.markdown
    assert "Source pack: proxy_preipo_rwa_pack" in card.markdown
    assert "Coverage status: degraded" in card.markdown
    assert "Source can prove:" in card.markdown
    assert "Source cannot prove:" in card.markdown
    assert "Relevant playbooks:" in card.markdown
    assert "OPENAI_API_KEY" not in card.markdown

    audit = event_opportunity_audit.format_opportunity_audit("VELVET", hypotheses=[row], watchlist_entries=[entry])
    assert "## Source coverage and acquisition plan" in audit
    assert "source pack: proxy_preipo_rwa_pack" in audit
    assert "provider coverage: degraded" in audit
    assert "source can prove:" in audit
    assert "source cannot prove:" in audit
    assert "relevant playbooks:" in audit


def test_event_core_opportunity_store_persists_canonical_rows():
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    rows = _canonical_core_fixture_rows()
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_core_opportunities.jsonl"
        result = event_core_opportunity_store.write_core_opportunities(
            rows,
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=path),
            run_id="run-core-store",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        assert result.success
        assert result.rows_written == 4
        loaded = event_core_opportunity_store.load_core_opportunities(path, latest_run=True)
        assert loaded.rows_read == 4
        by_symbol = {row["symbol"]: row for row in loaded.rows}
        assert by_symbol["VELVET"]["final_opportunity_level"] == "high_priority"
        assert by_symbol["VELVET"]["final_route_after_quality_gate"] == event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value
        assert by_symbol["RUNE"]["final_state_after_quality_gate"] == event_watchlist.EventWatchlistState.WATCHLIST.value
        assert set(by_symbol) == {"AAVE", "MEME", "RUNE", "VELVET"}


def test_event_core_opportunity_store_materializes_canonical_empty_jsonl(tmp_path):
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store

    path = tmp_path / "event_core_opportunities.jsonl"
    result = event_core_opportunity_store.write_core_opportunities(
        (),
        cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=path),
        run_id="run-clean-zero",
        profile="no_key_live",
        run_mode="burn_in",
        artifact_namespace="clean_zero",
    )

    assert result.success is True
    assert result.rows_written == 0
    assert path.is_file()
    assert path.read_bytes() == b""
    assert event_core_opportunity_store.load_core_opportunities(
        path,
        run_id="run-clean-zero",
    ).rows == []


def test_core_store_first_write_matches_read_normalization_for_diagnostic_support():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    primary = {
        "row_type": "event_impact_hypothesis",
        "hypothesis_id": "hyp-primary",
        "incident_id": "incident-noise-pair",
        "canonical_incident_name": "Ambiguous source-noise pair",
        "validated_symbol": "TEST",
        "validated_coin_id": "test-token",
        "candidate_role": "proxy_venue",
        "impact_category": "rwa_preipo_proxy",
        "impact_path_type": "proxy_attention",
        "opportunity_level": "local_only",
        "opportunity_score_final": 48,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
        "latest_effective_playbook_type": "proxy_attention",
    }
    diagnostic = {
        **primary,
        "hypothesis_id": "hyp-source-noise",
        "candidate_role": "source_noise",
        "impact_category": "publisher_noise",
        "impact_path_type": "generic_cooccurrence_only",
        "latest_effective_playbook_type": "source_noise_control",
    }
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_core_opportunities.jsonl"
        result = event_core_opportunity_store.write_core_opportunities(
            [primary, diagnostic],
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=path),
            now=now,
            run_id="run-diagnostic-idempotence",
            profile="notify_no_key",
            run_mode="notification_burn_in",
            artifact_namespace="notify_no_key",
        )
        assert result.success is True
        stored = event_core_opportunity_store.load_core_opportunities(path, latest_run=True).rows
        normalized = event_core_opportunity_store.normalize_core_opportunity_rows(stored, now=now)

    assert len(stored) == len(normalized) == 1
    assert stored[0]["diagnostic_row_count"] == 1
    assert stored[0]["source_noise_control_count"] == 1
    assert stored[0]["opportunity_type"] == "DIAGNOSTIC"
    assert normalized[0]["opportunity_type"] == stored[0]["opportunity_type"]
    assert normalized[0]["final_opportunity_level"] == stored[0]["final_opportunity_level"]
    assert normalized[0]["final_route_after_quality_gate"] == stored[0]["final_route_after_quality_gate"]


def test_event_core_opportunity_store_derives_route_from_final_verdict():
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    rows = [{
        "row_type": "event_impact_hypothesis",
        "hypothesis_id": "hyp-digest-store-only",
        "incident_id": "incident-digest-store-only",
        "canonical_incident_name": "Digest-worthy core with stale route",
        "symbol": "TEST",
        "coin_id": "test-token",
        "validated_symbol": "TEST",
        "validated_coin_id": "test-token",
        "candidate_role": "direct_subject",
        "impact_path_type": "strategic_investment",
        "impact_path_reason": "strategic_investment",
        "opportunity_level": "validated_digest",
        "opportunity_score_final": 72,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
        "final_verdict_reason": "Validated impact hypothesis kept local-only: stale primary route.",
        "evidence_specificity": "direct_token_mechanism",
        "source_class": "crypto_news",
        "market_confirmation_level": "none",
    }]
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_core_opportunities.jsonl"
        result = event_core_opportunity_store.write_core_opportunities(
            rows,
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=path),
            run_id="run-core-route-normalized",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        assert result.success
        loaded = event_core_opportunity_store.load_core_opportunities(path, latest_run=True)

    stored = loaded.rows[0]
    assert stored["final_opportunity_level"] == "validated_digest"
    assert stored["final_route_after_quality_gate"] == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value
    assert stored["route"] == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value
    assert stored["canonical_route_adjustment_reason"] == "core_route_derived_from_opportunity_level:validated_digest"
    assert "final route derived from canonical opportunity level" in stored["final_verdict_reason"]
    assert "local-only" not in stored["final_verdict_reason"]


def test_live_core_confirmation_caps_unconfirmed_digest_candidates():
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    rows = [
        {
            "row_type": "event_impact_hypothesis",
            "hypothesis_id": "hyp-eth-skipped-budget",
            "incident_id": "incident-eth-strategic",
            "symbol": "ETH",
            "coin_id": "ethereum",
            "validated_symbol": "ETH",
            "validated_coin_id": "ethereum",
            "candidate_role": "direct_beneficiary",
            "impact_path_type": "strategic_investment",
            "opportunity_level": "validated_digest",
            "opportunity_score_final": 74,
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
            "source_class": "crypto_news",
            "evidence_specificity": "direct_token_mechanism",
            "evidence_quality_score": 80,
            "market_confirmation_score": 20,
            "market_context_freshness_status": "missing",
            "evidence_acquisition_status": "skipped_budget",
            "source_pack": "strategic_investment_pack",
        },
        {
            "row_type": "event_impact_hypothesis",
            "hypothesis_id": "hyp-tao-rejected-only",
            "incident_id": "incident-tao-strategic",
            "symbol": "TAO",
            "coin_id": "bittensor",
            "candidate_role": "direct_beneficiary",
            "impact_path_type": "strategic_investment",
            "opportunity_level": "validated_digest",
            "opportunity_score_final": 72,
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
            "source_class": "crypto_news",
            "evidence_specificity": "direct_token_mechanism",
            "evidence_quality_score": 78,
            "evidence_acquisition_status": "rejected_results_only",
            "evidence_acquisition_rejected_count": 2,
            "source_pack": "strategic_investment_pack",
        },
        {
            "row_type": "event_impact_hypothesis",
            "hypothesis_id": "hyp-sector-sports",
            "incident_id": "incident-sector-sports",
            "symbol": "SECTOR",
            "coin_id": "sports_fan_proxy",
            "candidate_role": "sector_hypothesis",
            "impact_path_type": "sports_fan_proxy",
            "opportunity_level": "validated_digest",
            "opportunity_score_final": 70,
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
            "source_class": "structured_calendar",
            "evidence_specificity": "event_time_only",
            "evidence_quality_score": 78,
            "evidence_acquisition_status": "no_results",
            "source_pack": "fan_sports_pack",
        },
    ]
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            rows,
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=path),
            run_id="run-live-confirmation-caps",
            profile="live_burn_in_no_send",
            run_mode="notification_burn_in",
            artifact_namespace="live_burn_in_no_send",
        )
        stored = event_core_opportunity_store.load_core_opportunities(path, latest_run=True).rows
    by_symbol = {row["symbol"]: row for row in stored}
    assert by_symbol["ETH"]["final_opportunity_level"] == "exploratory"
    assert by_symbol["ETH"]["final_route_after_quality_gate"] == event_alpha_router.EventAlphaRoute.STORE_ONLY.value
    assert by_symbol["ETH"]["acquisition_confirmation_status"] == "unresolved"
    assert by_symbol["ETH"]["live_confirmation_reason"] == "skipped_budget_not_confirmation"
    assert by_symbol["TAO"]["final_opportunity_level"] == "exploratory"
    assert by_symbol["TAO"]["acquisition_confirmation_status"] == "does_not_confirm"
    assert by_symbol["TAO"]["live_confirmation_reason"] == "rejected_results_only_not_confirmation"
    assert by_symbol["SECTOR"]["final_opportunity_level"] == "local_only"
    assert by_symbol["SECTOR"]["live_confirmation_reason"] == "sector_only_digest_not_allowed"
    assert all(row["final_route_after_quality_gate"] == event_alpha_router.EventAlphaRoute.STORE_ONLY.value for row in stored)


def test_live_core_confirmation_allows_accepted_and_official_evidence():
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    rows = [
        {
            "row_type": "event_impact_hypothesis",
            "hypothesis_id": "hyp-velvet-accepted",
            "incident_id": "incident-spacex",
            "symbol": "VELVET",
            "coin_id": "velvet",
            "candidate_role": "proxy_venue",
            "impact_path_type": "venue_value_capture",
            "opportunity_level": "high_priority",
            "opportunity_score_final": 91,
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
            "source_class": "cryptopanic_tagged",
            "evidence_specificity": "direct_token_mechanism",
            "evidence_quality_score": 91,
            "market_confirmation_score": 88,
            "market_context_freshness_status": "fresh",
            "evidence_acquisition_status": "accepted_evidence_found",
            "evidence_acquisition_accepted_count": 1,
            "accepted_evidence_reason_codes": ["cryptopanic_currency_tag_match", "direct_token_mechanism"],
            "source_pack": "proxy_preipo_rwa_pack",
        },
        {
            "row_type": "event_impact_hypothesis",
            "hypothesis_id": "hyp-listing-official",
            "incident_id": "incident-listing",
            "symbol": "LIST",
            "coin_id": "listing-token",
            "candidate_role": "direct_beneficiary",
            "impact_path_type": "listing_liquidity_event",
            "opportunity_level": "validated_digest",
            "opportunity_score_final": 72,
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
            "source_class": "official_exchange",
            "evidence_specificity": "official_direct_event",
            "evidence_quality_score": 82,
            "evidence_acquisition_status": "no_results",
            "source_pack": "listing_liquidity_pack",
        },
    ]
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            rows,
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=path),
            run_id="run-live-confirmation-accepted",
            profile="live_burn_in_no_send",
            run_mode="notification_burn_in",
            artifact_namespace="live_burn_in_no_send",
        )
        stored = event_core_opportunity_store.load_core_opportunities(path, latest_run=True).rows
    by_symbol = {row["symbol"]: row for row in stored}
    assert by_symbol["VELVET"]["final_opportunity_level"] == "high_priority"
    assert by_symbol["VELVET"]["final_route_after_quality_gate"] == event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value
    assert by_symbol["VELVET"]["live_confirmation_passed"] is True
    assert by_symbol["VELVET"]["acquisition_confirmation_status"] == "confirms"
    assert by_symbol["LIST"]["final_opportunity_level"] == "validated_digest"
    assert by_symbol["LIST"]["final_route_after_quality_gate"] == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value
    assert by_symbol["LIST"]["live_confirmation_reason"] == "official_or_structured_source_confirmation"


def test_live_confirmation_caps_broad_treasury_valuation_but_allows_direct_project_stake():
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    rows = [
        {
            "row_type": "event_impact_hypothesis",
            "hypothesis_id": "hyp-btc-strategy-valuation",
            "incident_id": "incident-strategy-valuation",
            "symbol": "BTC",
            "coin_id": "bitcoin",
            "candidate_role": "direct_subject",
            "impact_category": "strategic_investment_or_valuation",
            "impact_path_type": "strategic_investment_or_valuation",
            "impact_path_reason": "strategic_investment",
            "opportunity_level": "validated_digest",
            "opportunity_score_final": 78,
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
            "canonical_incident_name": "Strategy trades below Bitcoin treasury valuation",
            "latest_source_title": "MSTR valuation discount widens versus Bitcoin holdings",
            "source_class": "crypto_news",
            "evidence_specificity": "direct_token_mechanism",
            "evidence_quality_score": 90,
            "market_confirmation_score": 0,
            "market_confirmation_level": "none",
            "market_context_freshness_status": "missing",
            "evidence_acquisition_status": "planned",
            "source_pack": "strategic_investment_pack",
        },
        {
            "row_type": "event_impact_hypothesis",
            "hypothesis_id": "hyp-aave-kraken-stake",
            "incident_id": "incident-aave-kraken",
            "symbol": "AAVE",
            "coin_id": "aave",
            "candidate_role": "direct_subject",
            "impact_category": "strategic_investment_or_valuation",
            "impact_path_type": "strategic_investment_or_valuation",
            "impact_path_reason": "strategic_investment",
            "opportunity_level": "validated_digest",
            "opportunity_score_final": 78,
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
            "canonical_incident_name": "Kraken takes strategic stake in Aave ecosystem",
            "latest_source_title": "Kraken strategic investment directly names AAVE",
            "source_class": "crypto_news",
            "evidence_specificity": "direct_token_mechanism",
            "evidence_quality_score": 90,
            "market_confirmation_score": 0,
            "market_confirmation_level": "none",
            "market_context_freshness_status": "missing",
            "evidence_acquisition_status": "planned",
            "source_pack": "strategic_investment_pack",
        },
    ]
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            rows,
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=path),
            run_id="run-live-broad-strategy",
            profile="live_burn_in_no_send",
            run_mode="notification_burn_in",
            artifact_namespace="live_burn_in_no_send",
        )
        stored = event_core_opportunity_store.load_core_opportunities(path, latest_run=True).rows
    by_symbol = {row["symbol"]: row for row in stored}
    assert by_symbol["BTC"]["final_opportunity_level"] == "exploratory"
    assert by_symbol["BTC"]["final_route_after_quality_gate"] == event_alpha_router.EventAlphaRoute.STORE_ONLY.value
    assert by_symbol["BTC"]["live_confirmation_passed"] is False
    assert by_symbol["BTC"]["live_confirmation_reason"] == "evidence_acquisition_not_executed"
    assert by_symbol["AAVE"]["final_opportunity_level"] == "validated_digest"
    assert by_symbol["AAVE"]["final_route_after_quality_gate"] == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value
    assert by_symbol["AAVE"]["live_confirmation_reason"] == "strong_direct_original_source_evidence"


def test_live_confirmation_gated_rows_surface_in_reports():
    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief
    import crypto_rsi_scanner.event_alpha.outcomes.quality as event_alpha_quality_review
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    row = {
        "row_type": "event_impact_hypothesis",
        "hypothesis_id": "hyp-doge-skipped-budget",
        "incident_id": "incident-doge-strategic",
        "symbol": "DOGE",
        "coin_id": "dogecoin",
        "candidate_role": "direct_beneficiary",
        "impact_path_type": "strategic_investment",
        "opportunity_level": "validated_digest",
        "opportunity_score_final": 73,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
        "source_class": "crypto_news",
        "evidence_specificity": "direct_token_mechanism",
        "evidence_quality_score": 78,
        "market_confirmation_score": 10,
        "market_context_freshness_status": "missing",
        "evidence_acquisition_status": "skipped_budget",
        "source_pack": "strategic_investment_pack",
    }
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            [row],
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=path),
            run_id="run-live-confirmation-report",
            profile="live_burn_in_no_send",
            run_mode="notification_burn_in",
            artifact_namespace="live_burn_in_no_send",
        )
        stored = event_core_opportunity_store.load_core_opportunities(path, latest_run=True).rows
    brief = event_alpha_daily_brief.build_daily_brief(
        core_opportunity_rows=stored,
        requested_profile="live_burn_in_no_send",
        artifact_namespace="live_burn_in_no_send",
        include_test_artifacts=True,
    )
    assert "## Live Confirmation Gated Candidates" in brief
    assert "DOGE/dogecoin" in brief
    assert "skipped_budget_not_confirmation" in brief
    digest_section = brief.split("## Validated Digest Core Opportunities", 1)[1].split("## Watchlist Core Opportunities", 1)[0]
    assert "DOGE/dogecoin" not in digest_section

    review = event_alpha_quality_review.format_quality_review(
        event_alpha_quality_review.build_quality_review(
            profile="live_burn_in_no_send",
            core_opportunity_rows=stored,
        )
    )
    assert "live_confirmation_gates:" in review
    assert "skipped_budget_capped=1" in review
    assert "Live Confirmation Gated Candidates:" in review


def test_event_core_opportunity_store_uses_refreshed_nested_market_context():
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store

    rows = _canonical_core_fixture_rows()
    velvet = dict(rows[0])
    velvet.update({
        "market_context_freshness_status": "fresh",
        "market_context_source": "missing",
        "market_context_age_hours": "unknown",
        "market_context_data_quality": "missing",
        "market_context_freshness_cap_applied": True,
        "market_context_after": {
            "timestamp": "2026-06-15T15:30:00+00:00",
            "age_seconds": 1800,
            "data_quality": "fresh",
            "source": "fixture_targeted_market_refresh",
            "market_snapshot": {
                "symbol": "VELVET",
                "coin_id": "velvet",
                "source": "fixture_targeted_market_refresh",
                "timestamp": "2026-06-15T15:30:00+00:00",
            },
        },
    })
    rows[0] = velvet

    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_core_opportunities.jsonl"
        result = event_core_opportunity_store.write_core_opportunities(
            rows,
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=path),
            run_id="run-core-market-context",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        assert result.success
        loaded = event_core_opportunity_store.load_core_opportunities(path, latest_run=True)
    stored = next(row for row in loaded.rows if row["symbol"] == "VELVET")
    assert stored["market_context_freshness_status"] == "fresh"
    assert stored["market_context_source"] == "fixture_targeted_market_refresh"
    assert stored["market_context_data_quality"] == "fresh"
    assert stored["market_context_age_hours"] == 0.5
    assert stored["market_context_freshness_cap_applied"] is False


def test_event_core_opportunity_store_preserves_integrated_market_snapshot_identity():
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store

    rows = _canonical_core_fixture_rows()
    velvet = dict(rows[0])
    velvet.update({
        "market_context_freshness_status": "missing",
        "market_context_source": "missing",
        "market_context_age_hours": "unknown",
        "market_context_data_quality": "missing",
        "market_context_freshness_cap_applied": True,
        "market_snapshot": {
            "symbol": "VELVET",
            "coin_id": "velvet",
            "market_data_source": "coingecko",
            "observed_at": "2026-06-15T15:30:00+00:00",
            "freshness_status": "fresh",
            "market_snapshot_id": "market-history-velvet-1",
        },
    })
    rows[0] = velvet

    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_core_opportunities.jsonl"
        result = event_core_opportunity_store.write_core_opportunities(
            rows,
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=path),
            run_id="run-core-market-snapshot",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        assert result.success
        loaded = event_core_opportunity_store.load_core_opportunities(path, latest_run=True)
    stored = next(row for row in loaded.rows if row["symbol"] == "VELVET")
    assert stored["market_context_source"] == "coingecko"
    assert stored["market_context_observed_at"] == "2026-06-15T15:30:00+00:00"
    assert stored["market_context_freshness_status"] == "fresh"
    assert stored["market_snapshot_id"] == "market-history-velvet-1"
    assert stored["market_context_reference"] == {
        "source": "coingecko",
        "observed_at": "2026-06-15T15:30:00+00:00",
        "freshness_status": "fresh",
        "market_snapshot_id": "market-history-velvet-1",
    }


def test_event_core_opportunity_store_prevents_stale_support_near_miss():
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store
    import crypto_rsi_scanner.event_alpha.radar.near_miss as event_near_miss

    rows = _canonical_core_fixture_rows()
    merged = event_core_opportunity_store.merge_core_opportunity_verdict(
        rows[0],
        support_rows=[rows[1]],
    )
    assert merged["symbol"] == "VELVET"
    assert merged["final_opportunity_level"] == "high_priority"

    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            rows,
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=path),
            run_id="run-core-near-miss",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        loaded = event_core_opportunity_store.load_core_opportunities(path, latest_run=True)
    near = event_near_miss.detect_near_miss_rows(loaded.rows)
    symbols = {item.symbol for item in near}
    assert "VELVET" not in symbols
    assert "RUNE" not in symbols


def test_event_alpha_daily_brief_uses_canonical_core_store_rows():
    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store

    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            _canonical_core_fixture_rows(),
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=path),
            run_id="run-core-brief",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        loaded = event_core_opportunity_store.load_core_opportunities(path, latest_run=True)
    brief = event_alpha_daily_brief.build_daily_brief(
        core_opportunity_rows=loaded.rows,
        requested_profile="market_refresh_smoke",
        artifact_namespace="market_refresh_smoke",
        run_mode="burn_in",
        generated_at=pd.Timestamp("2026-06-15T12:00:00Z").to_pydatetime(),
    )
    assert "Current-generation visible core opportunity identities: 4" in brief
    assert "## High-Priority Core Opportunities" in brief
    high_section = brief.split("## High-Priority Core Opportunities", 1)[1].split("## Validated Digest Core Opportunities", 1)[0]
    near_section = brief.split("## Near-Miss Candidates", 1)[1].split("## Upgrade Candidates", 1)[0]
    assert "VELVET/velvet" in high_section
    assert "VELVET/velvet" not in near_section


def test_canonical_core_resolution_links_diagnostics_and_orphans():
    import crypto_rsi_scanner.event_alpha.radar.core_opportunities as event_core_opportunities
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store

    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            _canonical_core_fixture_rows(),
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=path),
            run_id="run-core-resolution",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        store_rows = event_core_opportunity_store.load_core_opportunities(path, latest_run=True).rows
    velvet_core = next(row["core_opportunity_id"] for row in store_rows if row["symbol"] == "VELVET")
    rune_core = next(row["core_opportunity_id"] for row in store_rows if row["symbol"] == "RUNE")

    rune_resolution = event_core_opportunities.resolve_canonical_core_opportunity_id(
        {
            "incident_id": "incident-thorchain-exploit",
            "validated_symbol": "RUNE",
            "validated_coin_id": "thorchain",
            "candidate_role": "direct_beneficiary",
            "impact_path_type": "exploit_security_event",
        },
        store_rows,
    )
    assert rune_resolution.resolution_status == "canonical"
    assert rune_resolution.canonical_core_opportunity_id == rune_core

    diagnostic = event_core_opportunities.resolve_canonical_core_opportunity_id(
        {
            "core_opportunity_id": "core_601f14c59028",
            "incident_id": "incident-spacex",
            "validated_symbol": "VELVET",
            "validated_coin_id": "velvet",
            "candidate_role": "source_noise",
            "latest_effective_playbook_type": "source_noise_control",
            "impact_path_type": "generic_cooccurrence_only",
        },
        store_rows,
    )
    assert diagnostic.resolution_status == "diagnostic_support"
    assert diagnostic.diagnostic_support_for_core_opportunity_id == velvet_core
    assert "noncanonical_core_id_replaced:core_601f14c59028" in diagnostic.warnings

    orphan = event_core_opportunities.resolve_canonical_core_opportunity_id(
        {
            "core_opportunity_id": "core_missing_visible",
            "incident_id": "incident-orphan",
            "validated_symbol": "ORPHAN",
            "validated_coin_id": "orphan",
            "candidate_role": "direct_beneficiary",
            "impact_path_type": "listing_liquidity_event",
            "opportunity_level": "watchlist",
        },
        store_rows,
    )
    assert orphan.resolution_status == "orphan"
    assert "visible_core_missing_store_row:core_missing_visible" in orphan.warnings

    explicit_orphan = event_core_opportunities.resolve_canonical_core_opportunity_id(
        {"core_opportunity_id": "core_missing_from_store"},
        store_rows,
    )
    assert explicit_orphan.resolution_status == "orphan"
    assert explicit_orphan.canonical_core_opportunity_id == "core_missing_from_store"
    assert "visible_core_missing_store_row:core_missing_from_store" in explicit_orphan.warnings


def test_research_cards_use_canonical_core_store_groups():
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        store_path = root / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            _canonical_core_fixture_rows(),
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=store_path),
            run_id="run-core-cards",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        store_rows = event_core_opportunity_store.load_core_opportunities(store_path, latest_run=True).rows
        result = event_research_cards.write_research_cards(
            root / "cards",
            watchlist_entries=[],
            alert_rows=store_rows,
        )
        store_ids = {row["core_opportunity_id"] for row in store_rows}
        groups = event_research_cards.card_index_group_map(result.card_paths)
        reviewable_core_groups = {
            "Early Long Research Cards",
            "Confirmed Long Research Cards",
            "Fade / Short-Review Cards",
            "Risk Only Cards",
            "Unconfirmed Research Cards",
            "Core Opportunity Cards",
        }
        core_paths = [path for path in result.card_paths if groups[path] in reviewable_core_groups]
        assert core_paths
        assert all(event_research_cards.card_core_opportunity_id(path) in store_ids for path in core_paths)
        index_text = result.index_path.read_text(encoding="utf-8")
        promoted_sections = "\n".join(
            index_text.split(f"## {group_name}", 1)[1].split("\n## ", 1)[0]
            for group_name in reviewable_core_groups
            if f"## {group_name}" in index_text
        )
        local_section = index_text.split("## Local-Only / Quality-Capped Cards", 1)[1].split("## Diagnostic", 1)[0]
        assert "RUNE" in "".join(path.read_text(encoding="utf-8") for path in core_paths)
        assert "card_core_aa617f5bc943" in promoted_sections
        assert any(
            "memecore" in path.read_text(encoding="utf-8").casefold()
            for path, group in groups.items()
            if group == "Unconfirmed Research Cards"
        )
        link_update = event_core_opportunity_store.update_core_opportunity_card_links(
            store_path,
            result.card_paths,
            run_id="run-core-cards",
        )
        assert link_update.success
        assert link_update.rows_updated == len(store_ids)
        linked_rows = event_core_opportunity_store.load_core_opportunities(store_path, latest_run=True).rows
        assert all(row.get("card_path") for row in linked_rows)


def test_research_card_index_groups_normal_unconfirmed_lane_before_near_miss_fallback():
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards

    with TemporaryDirectory() as tmp:
        card_path = Path(tmp) / "card_chz.md"
        card_path.write_text(
            "# CHZ Event Research Card\n\n"
            "- Opportunity type: UNCONFIRMED_RESEARCH\n"
            "- Quality: exploratory\n",
            encoding="utf-8",
        )
        groups = event_research_cards.card_index_group_map([card_path])
        assert groups[card_path] == "Unconfirmed Research Cards"


def test_research_cards_backfill_aggregated_support_core_rows():
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    rows = _canonical_core_fixture_rows()
    hidden_support = {
        **rows[-1],
        "hypothesis_id": "hyp-meme-generic-support",
        "core_opportunity_id": "core_memecore_generic_support",
        "impact_path_type": "generic_cooccurrence_only",
        "primary_impact_path": "generic_cooccurrence_only",
        "candidate_role": "generic_mention",
        "opportunity_level": "local_only",
        "opportunity_score_final": 0,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.HYPOTHESIS.value,
        "evidence_specificity": "insufficient_data",
        "evidence_quality_score": 0,
    }
    rows.append(hidden_support)
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        store_path = root / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            rows,
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=store_path),
            run_id="run-core-cards-hidden-support",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        store_rows = event_core_opportunity_store.load_core_opportunities(store_path, latest_run=True).rows
        result = event_research_cards.write_research_cards(
            root / "cards",
            watchlist_entries=[],
            alert_rows=store_rows,
            limit=50,
        )
        link_update = event_core_opportunity_store.update_core_opportunity_card_links(
            store_path,
            result.card_paths,
            run_id="run-core-cards-hidden-support",
        )
        linked_rows = event_core_opportunity_store.load_core_opportunities(store_path, latest_run=True).rows
        by_id = {row["core_opportunity_id"]: row for row in linked_rows}
        assert link_update.success
        assert by_id["core_memecore_generic_support"]["card_path"]
        assert any(
            event_research_cards.card_core_opportunity_id(path) == "core_memecore_generic_support"
            for path in result.card_paths
        )


def test_research_card_primary_fields_use_canonical_core_row():
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        store_path = root / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            _canonical_core_fixture_rows(),
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=store_path),
            run_id="run-core-card-primary",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        store_rows = event_core_opportunity_store.load_core_opportunities(store_path, latest_run=True).rows
    velvet = {
        **next(row for row in store_rows if row["symbol"] == "VELVET"),
        "validation_stage": "impact_path_validated",
        "main_frame_type": "proxy_attention",
        "main_frame_role": "main_catalyst",
        "main_frame_subject": "SpaceX",
        "main_frame_actor": "Velvet",
        "main_frame_object": "pre-IPO exposure",
        "frame_status": "validated",
        "latest_source": "impact_hypothesis",
        "source_provider": "impact_hypothesis",
        "evidence_acquisition_accepted_count": 1,
        "evidence_acquisition_accepted_evidence": [{
            "title": "VELVET offers SpaceX pre-IPO tokenized stock exposure",
            "provider": "cryptopanic",
            "source_url": "https://cryptopanic.com/news/velvet-spacex-pre-ipo",
            "reason_codes": ["cryptopanic_currency_tag_match", "direct_token_mechanism"],
        }],
        "accepted_evidence_reason_codes": ["cryptopanic_currency_tag_match", "direct_token_mechanism"],
        "evidence_acquisition_results": {"status": "accepted_evidence_found", "accepted": 1, "rejected": 0},
    }
    stale_support = {
        **velvet,
        "row_type": "event_alpha_alert_snapshot",
        "tier": "STORE_ONLY",
        "state": "RADAR",
        "route": "STORE_ONLY",
        "opportunity_level": "local_only",
        "opportunity_score_final": 0,
        "impact_path_type": "insufficient_data",
        "evidence_acquisition_attempted": False,
        "evidence_acquisition_status": "not_executed",
    }
    card = event_research_cards.render_research_card(
        velvet["core_opportunity_id"],
        watchlist_entries=[],
        alert_rows=[stale_support, velvet],
    )
    assert "- State / alert tier: HIGH_PRIORITY / HIGH_PRIORITY_RESEARCH" in card.markdown
    assert "- Source pack: proxy_preipo_rwa_pack" in card.markdown
    assert "- Latest source: cryptopanic" in card.markdown
    assert "- Latest source: unknown" not in card.markdown
    assert "- Latest source: not available" not in card.markdown
    assert "- Evidence acquisition attempted: true" in card.markdown
    assert "accepted=1" in card.markdown
    assert "cryptopanic_currency_tag_match" in card.markdown
    assert "VELVET offers SpaceX pre-IPO tokenized stock exposure" in card.markdown
    assert "- Impact path strength: strong" in card.markdown
    assert "- Impact path strength: unknown" not in card.markdown
    assert "- Impact path reason: venue_value_capture" in card.markdown
    assert "- Impact path digest eligible: true" in card.markdown
    assert "- Market confirmation: strong / 88" in card.markdown
    assert "No market snapshot stored" not in card.markdown
    assert "Market data: not available" not in card.markdown
    assert "Already high priority" in card.markdown
    assert "blocked by generic cooccurrence" not in card.markdown
    assert "needs proof that this event directly affects the token" not in card.markdown
    assert "no token value-capture mechanism is visible" not in card.markdown
    assert "- Opportunity verdict: high_priority / 92.0" in card.markdown
    assert "- Relationship: venue_value_capture" in card.markdown
    assert "- Quality gate: passed final quality gate (HIGH_PRIORITY_RESEARCH)" in card.markdown
    assert "- Why promoted/local-only: Core opportunity verdict reached high_priority." in card.markdown
    assert "Quality gate: local-only" not in card.markdown
    assert "validated impact hypothesis promoted to RADAR" not in card.markdown
    assert "STORE_ONLY" not in card.markdown.split("## Artifact Lineage", 1)[0]


def test_opportunity_audit_primary_sections_use_canonical_core_view():
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store
    import crypto_rsi_scanner.event_alpha.artifacts.opportunity_audit as event_opportunity_audit

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        store_path = root / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            _canonical_core_fixture_rows(),
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=store_path),
            run_id="run-core-audit-primary",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        store_rows = event_core_opportunity_store.load_core_opportunities(store_path, latest_run=True).rows
    velvet = {
        **next(row for row in store_rows if row["symbol"] == "VELVET"),
        "evidence_acquisition_accepted_count": 1,
        "evidence_acquisition_accepted_evidence": [{
            "title": "VELVET offers SpaceX pre-IPO tokenized stock exposure",
            "provider": "cryptopanic",
            "source_url": "https://cryptopanic.com/news/velvet-spacex-pre-ipo",
            "reason_codes": ["cryptopanic_currency_tag_match", "direct_token_mechanism"],
        }],
        "accepted_evidence_reason_codes": ["cryptopanic_currency_tag_match", "direct_token_mechanism"],
        "evidence_acquisition_results": {"status": "accepted_evidence_found", "accepted": 1, "rejected": 0},
    }
    stale_support = {
        **velvet,
        "row_type": "event_alpha_alert_snapshot",
        "opportunity_level": "local_only",
        "opportunity_score_final": 0,
        "impact_path_type": "insufficient_data",
        "upgrade_requirements": ["blocked_by_generic_cooccurrence", "needs_direct_token_mechanism"],
        "downgrade_warnings": ["no_value_capture"],
    }
    incident_row = {
        "row_type": "event_incident",
        "run_id": "run-core-audit-primary",
        "profile": "market_refresh_smoke",
        "artifact_namespace": "market_refresh_smoke",
        "incident_id": velvet["incident_id"],
        "canonical_name": "SpaceX pre-IPO exposure via Velvet",
        "canonical_incident_name": "SpaceX pre-IPO exposure via Velvet",
        "incident_relevance_status": "active_incident",
        "incident_relevance_score": 100.0,
        "primary_subject": "SpaceX pre-IPO exposure",
        "main_frame_type": "proxy_attention",
        "main_frame_role": "main_catalyst",
        "main_frame_subject": "SpaceX pre-IPO exposure",
        "main_frame_actor": "Velvet",
        "main_frame_object": "pre-IPO trading venue",
        "main_frame_evidence_quote": "Velvet users can trade SpaceX pre-IPO exposure",
        "linked_assets": [{"symbol": "VELVET", "coin_id": "velvet", "role": "proxy_venue"}],
    }
    audit = event_opportunity_audit.format_opportunity_audit(
        velvet["core_opportunity_id"],
        core_opportunity_rows=[velvet],
        alert_rows=[stale_support],
        incident_rows=[incident_row],
        profile="market_refresh_smoke",
    )
    assert "- impact path: venue_value_capture" in audit
    assert "- strength: strong" in audit
    assert "- reason: venue_value_capture" in audit
    assert "- source pack: proxy_preipo_rwa_pack" in audit
    assert "accepted reason codes: cryptopanic_currency_tag_match; direct_token_mechanism" in audit
    assert "VELVET offers SpaceX pre-IPO tokenized stock exposure" in audit
    assert "- market level/score: strong / 88" in audit
    assert "Already high priority" in audit
    assert "blocked by generic cooccurrence" not in audit
    assert "needs proof that this event directly affects the token" not in audit
    assert "no token value-capture mechanism is visible" not in audit
    assert "- main catalyst frame: proxy_attention (main_catalyst)" in audit
    assert "- main catalyst subject/actor/object: SpaceX pre-IPO exposure / Velvet / pre-IPO trading venue" in audit
    assert "- main catalyst evidence: Velvet users can trade SpaceX pre-IPO exposure" in audit
