"""Focused propagation tests for Crypto Radar Decision Model v2 surfaces."""

from __future__ import annotations

from pathlib import Path


def _market_led_candidate(**overrides):
    row = {
        "schema_version": 1,
        "row_type": "event_integrated_radar_candidate",
        "candidate_id": "candidate-v2",
        "core_opportunity_id": "core-v2",
        "alert_key": "candidate-v2",
        "asset_symbol": "V2",
        "asset_coin_id": "v2-coin",
        "symbol": "V2",
        "coin_id": "v2-coin",
        "canonical_asset_id": "v2-coin",
        "observed_at": "2026-06-15T16:00:00Z",
        "instrument_resolver_status": "resolved",
        "instrument_resolver_confidence": 0.95,
        "instrument_identity_trusted": True,
        "is_tradable_asset": True,
        "event_name": "Fresh liquid breakout",
        "opportunity_type": "UNCONFIRMED_RESEARCH",
        "market_state_class": "confirmed_breakout",
        "market_anomaly_bucket": "high_liquidity_breakout",
        "market_state_snapshot": {
            "return_unit": "percent_points",
            "return_4h": 12.0,
            "return_24h": 20.0,
            "relative_return_vs_btc_4h": 8.0,
            "volume_zscore_24h": 3.0,
            "volume_to_market_cap": 0.25,
            "liquidity_usd": 10_000_000,
            "spread_bps": 20.0,
            "freshness_status": "fresh",
        },
        "source_pack": "market_anomaly_pack",
        "decision_model_version": "crypto_radar_decision_model_v2",
        "decision_model_enabled": True,
        "thesis_origin": "market_led",
        "primary_thesis_origin": "market_led",
        "thesis_origins": ["market_led"],
        "directional_bias": "long",
        "catalyst_status": "unknown",
        "confidence_band": "actionable",
        "timing_state": "active",
        "tradability_status": "good",
        "spread_status": "verified_good",
        "radar_route": "actionable_watch",
        "radar_route_reason": "fresh_liquid_market_structure",
        "radar_actionable": True,
        "actionability_score": 84.0,
        "evidence_confidence_score": 61.0,
        "risk_score": 38.0,
        "urgency_score": 74.0,
        "market_phase": "breakout",
        "preferred_horizon": "1d_3d",
        "expires_at": "2026-06-16T16:00:00+00:00",
        "chase_risk_score": 31.0,
        "actionability_score_components": {"liquidity": 20, "relative_move": 18},
        "actionability_penalty_components": {"unknown_catalyst": 5},
        "evidence_confidence_score_components": {"market_evidence": 42},
        "risk_score_components": {"manipulation_risk": 10},
        "decision_hard_blockers": (),
        "decision_soft_penalties": ("unknown_catalyst",),
        "decision_missing_data": ("derivatives",),
        "decision_warnings": ("unknown_catalyst", "manipulation_risk_review"),
        "why_still_worth_reviewing": ("fresh liquid breakout with relative strength",),
        "radar_what_confirms": ("continued volume-backed follow-through",),
        "radar_what_invalidates": ("failed breakout and mean reversion",),
        "anomaly_type": "high_liquidity_breakout",
        "research_only": True,
        "normal_rsi_signal_written": False,
        "triggered_fade_created": False,
        "paper_trade_created": False,
        "trade_created": False,
    }
    row.update(overrides)
    return row


def test_v2_fields_propagate_to_core_and_alert_reconciliation_without_legacy_promotion():
    from crypto_rsi_scanner.event_alpha.artifacts.alert_store import (
        reconcile_alert_snapshot_with_core_store,
    )
    from crypto_rsi_scanner.event_alpha.radar.core.merge import _apply_integrated_candidate_truth
    from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import decision_model_values
    from crypto_rsi_scanner.event_alpha.radar.market_reaction import (
        MarketReactionResult,
        MarketStateSnapshot,
    )

    candidate = _market_led_candidate()
    reaction = MarketReactionResult(
        market_state_snapshot=MarketStateSnapshot(),
        market_state="no_reaction",
        opportunity_type="UNCONFIRMED_RESEARCH",
        why_now="generic fallback",
    )
    core = _apply_integrated_candidate_truth(
        {}, primary=candidate, all_rows=(candidate,), reaction=reaction
    )

    assert core["opportunity_type"] == "UNCONFIRMED_RESEARCH"
    assert core["radar_route"] == "actionable_watch"
    assert core["radar_actionable"] is True
    assert core["actionability_penalty_components"] == candidate[
        "actionability_penalty_components"
    ]
    assert core.get("normal_rsi_signal_written") is not True
    assert core.get("triggered_fade_created") is not True

    reconciled = reconcile_alert_snapshot_with_core_store(
        {"alert_id": "alert-v2", "route": "STORE_ONLY"},
        {
            **core,
            "symbol": "V2",
            "coin_id": "v2-coin",
            "final_route_after_quality_gate": "STORE_ONLY",
            "final_opportunity_level": "local_only",
            "final_state_after_quality_gate": "RADAR",
        },
    )
    assert reconciled["radar_route"] == "actionable_watch"
    assert reconciled["actionability_score"] == core["actionability_score"]
    assert reconciled["catalyst_status"] == "unknown"
    assert decision_model_values({"opportunity_type": "CONFIRMED_LONG_RESEARCH"}) == {}
    assert decision_model_values({**candidate, "decision_model_enabled": "true"}) == {}
    assert decision_model_values({**candidate, "decision_model_enabled": None}) == {}
    assert decision_model_values({**candidate, "decision_model_version": "future"}) == {}


def test_v2_projection_preserves_explicit_empty_contract_fields_and_one_authority():
    from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import decision_model_values

    canonical = _market_led_candidate(
        actionability_penalty_components={},
        decision_hard_blockers=[],
        decision_soft_penalties=[],
        decision_missing_data=[],
    )
    unversioned_override = {
        "radar_actionable": False,
        "radar_route": "diagnostic",
        "actionability_score": 1.0,
        "decision_hard_blockers": ["legacy_override"],
    }

    projected = decision_model_values(canonical, unversioned_override)

    assert projected["radar_actionable"] is True
    assert projected["radar_route"] == "actionable_watch"
    assert projected["actionability_score"] == 84.0
    assert projected["actionability_penalty_components"] == {}
    assert projected["decision_hard_blockers"] == []
    assert projected["decision_soft_penalties"] == []
    assert projected["decision_missing_data"] == []

    disabled_root = {
        **canonical,
        "decision_model_enabled": False,
        "score_components": canonical,
    }
    malformed_root = {
        **canonical,
        "radar_actionable": False,
        "score_components": canonical,
    }
    assert decision_model_values(disabled_root) == {}
    assert decision_model_values(malformed_root) == {}
    assert decision_model_values(malformed_root, canonical) == {}


def test_v2_projection_remains_backward_compatible_before_contract_extension():
    from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import decision_model_values

    extended_fields = {
        "primary_thesis_origin",
        "thesis_origins",
        "spread_status",
        "urgency_score",
        "market_phase",
        "preferred_horizon",
        "expires_at",
        "chase_risk_score",
    }
    historical = {
        key: value
        for key, value in _market_led_candidate().items()
        if key not in extended_fields
    }

    projected = decision_model_values(historical)

    assert projected["decision_model_version"] == "crypto_radar_decision_model_v2"
    assert projected["radar_route"] == "actionable_watch"
    assert projected["thesis_origin"] == "market_led"
    assert "primary_thesis_origin" not in projected


def test_v2_projection_preserves_source_safety_attestations_and_diagnostic_aggregate():
    from crypto_rsi_scanner.event_alpha.outcomes.integrated_radar_outcomes import (
        _performance_observation_rows,
    )
    from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import decision_model_values

    diagnostic = _market_led_candidate(
        confidence_band="diagnostic",
        tradability_status="blocked",
        radar_route="diagnostic",
        radar_route_reason="source_safety_failed",
        radar_actionable=False,
        decision_hard_blockers=["secret_safety_failed"],
        decision_source_secret_safety_failed=True,
    )

    projected = decision_model_values(diagnostic)
    rows = _performance_observation_rows(
        Path("."),
        candidates=[diagnostic],
        core_rows=[],
        outcome_rows=[],
        delivery_rows=[],
        generated_at="2026-06-20T00:00:00+00:00",
        stale_after_days=14,
    )

    assert projected["decision_source_secret_safety_failed"] is True
    assert rows[0]["radar_route"] == "diagnostic"
    assert rows[0]["include_in_main_aggregate"] is False


def test_v2_projection_does_not_launder_unsafe_source_claims():
    from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import (
        decision_model_values,
    )

    malformed_or_unsafe = (
        _market_led_candidate(notification_send_enabled="false"),
        _market_led_candidate(telegram_sends={"count": 0}),
        _market_led_candidate(trade_created=[]),
        _market_led_candidate(paper_trade_created="false"),
        _market_led_candidate(normal_rsi_signal_written={}),
        _market_led_candidate(triggered_fade_created="0"),
        _market_led_candidate(provider_api_key="fixture-secret"),
        _market_led_candidate(operator_report_path="/tmp/unsafe-report.md"),
        _market_led_candidate(source_context={"research_only": "false"}),
    )

    for row in malformed_or_unsafe:
        assert decision_model_values(row) == {}

    safe = decision_model_values(_market_led_candidate(
        notification_send_enabled=False,
        telegram_sends=0,
        trades_created=0.0,
        paper_trades_created=0,
        normal_rsi_signal_rows_written=0,
        strict_alerts_created=0,
    ))
    assert safe
    assert all(safe["decision_safety_invariants"].values())


def test_closed_decision_projection_is_idempotent_and_preserves_calendar_rsi_and_lineage():
    from crypto_rsi_scanner.event_alpha.artifacts.schema.decision_model import validate_contract
    from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import (
        DECISION_PROJECTION_SCHEMA_VERSION,
        decision_model_values,
        decision_preview_lane,
    )

    raw = _market_led_candidate(
        candidate_id="calendar-rsi-v2",
        core_opportunity_id="calendar-rsi-core-v2",
        directional_bias="risk",
        confidence_band="exploratory",
        radar_route="calendar_risk",
        radar_route_reason="attached_calendar_or_scheduled_risk_research",
        radar_actionable=False,
        timing_state="scheduled",
        preferred_horizon="scheduled_window",
        why_now="Known high-impact window overlaps the research horizon.",
        source_origin="unified_calendar",
        source_origins=["unified_calendar", "market_anomaly"],
        source_provider="fixture-calendar",
        source_packs=["unified_calendar_pack", "market_anomaly_pack"],
        run_mode="fixture",
        run_id="calendar-rsi-run",
        profile="fixture",
        artifact_namespace="calendar-rsi",
        market_snapshot={
            "market_data_source": "fixture_coingecko",
            "observed_at": "2026-06-15T15:59:00Z",
            "freshness_status": "fresh",
            "market_snapshot_id": "calendar-rsi-market-1",
        },
        unified_calendar_context=[{
            "calendar_event_id": "calendar-fomc-v2",
            "event_kind": "central_bank",
            "scheduled_at": "2026-06-15T20:00:00Z",
            "time_certainty": "exact",
            "importance": "high",
            "source": "Fixture Calendar",
            "source_url": "https://example.invalid/calendar/fomc",
        }],
        rsi_context_version="rsi_technical_context_v1",
        rsi_context={
            "context_version": "rsi_technical_context_v1",
            "valid": True,
            "symbol": "V2",
            "coin_id": "v2-coin",
            "setup_type": "breakdown_risk",
            "rsi_value": 78.0,
            "rsi_timeframe": "1d",
            "observed_at": "2026-06-15T15:00:00Z",
            "freshness_status": "fresh",
        },
    )

    projected = decision_model_values(raw)
    projected_again = decision_model_values(projected)

    assert projected_again == projected
    assert validate_contract(projected) == []
    assert projected["decision_projection_schema_version"] == DECISION_PROJECTION_SCHEMA_VERSION
    assert decision_preview_lane(raw) == decision_preview_lane(projected) == "calendar_risk"
    assert projected["calendar_evidence_ids"] == ["calendar-fomc-v2"]
    assert projected["calendar_evidence"][0] == {
        "calendar_event_id": "calendar-fomc-v2",
        "evidence_reference": None,
        "category": "central_bank",
        "event_kind": "central_bank",
        "scheduled_at": "2026-06-15T20:00:00Z",
        "window_start": None,
        "window_end": None,
        "time_certainty": "exact",
        "importance": "high",
        "source": "Fixture Calendar",
        "source_url": "https://example.invalid/calendar/fomc",
    }
    assert projected["rsi_context"]["setup_type"] == "breakdown_risk"
    assert projected["rsi_context_references"][0]["observed_at"] == "2026-06-15T15:00:00Z"
    assert projected["market_context_reference"] == {
        "source": "fixture_coingecko",
        "observed_at": "2026-06-15T15:59:00Z",
        "freshness_status": "fresh",
        "market_snapshot_id": "calendar-rsi-market-1",
    }
    assert projected["observation_ids"] == [
        "calendar-rsi-v2",
        "calendar-rsi-core-v2",
        "calendar-rsi-market-1",
    ]
    assert projected["source_provider_lineage"] == {
        "data_mode": "fixture",
        "providers": ["fixture-calendar"],
        "origins": ["unified_calendar", "market_anomaly"],
        "source_packs": ["unified_calendar_pack", "market_anomaly_pack"],
        "provider_generation_id": "",
        "run_id": "calendar-rsi-run",
        "profile": "fixture",
        "artifact_namespace": "calendar-rsi",
    }
    assert projected["decision_evaluated_at"] == "2026-06-15T16:00:00Z"
    assert all(projected["decision_safety_invariants"].values())
    assert projected["hard_blockers"] == projected["decision_hard_blockers"]
    assert projected["missing_information"] == projected["decision_missing_data"]
    assert projected["what_confirms"] == projected["radar_what_confirms"]


def test_calendar_preview_keeps_every_canonical_item_and_rejects_false_calendar_routes():
    from crypto_rsi_scanner.event_alpha.artifacts.schema.decision_model import validate_contract
    from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import (
        decision_model_values,
        decision_preview_lane,
        group_decision_rows,
    )

    def calendar_candidate(candidate_id: str, event_id: str):
        return _market_led_candidate(
            candidate_id=candidate_id,
            core_opportunity_id=f"{candidate_id}-core",
            directional_bias="risk",
            confidence_band="exploratory",
            radar_route="calendar_risk",
            radar_route_reason="attached_calendar_or_scheduled_risk_research",
            radar_actionable=False,
            timing_state="scheduled",
            preferred_horizon="scheduled_window",
            unified_calendar_event={
                "event_id": event_id,
                "event_kind": "crypto_unlock",
                "scheduled_at": "2026-06-15T20:00:00Z",
                "time_certainty": "exact",
                "importance": "high",
            },
        )

    testlist = calendar_candidate("testlist-calendar", "calendar-testlist")
    testunlock = calendar_candidate("testunlock-calendar", "calendar-testunlock")
    testrumor = {
        **calendar_candidate("testrumor-calendar", "unused-calendar-id"),
        "unified_calendar_event": None,
        "scheduled_catalyst_event": {
            "event_type": "project",
            "event_start_time": "2026-06-15T20:00:00Z",
            "provider": "fixture-calendar",
            "source_url": "https://example.invalid/calendar/rumor",
        },
    }
    diagnostic = _market_led_candidate(
        candidate_id="non-calendar-diagnostic",
        core_opportunity_id="non-calendar-diagnostic-core",
        confidence_band="diagnostic",
        tradability_status="blocked",
        radar_route="diagnostic",
        radar_route_reason="hard_gate_blocked_research_promotion",
        radar_actionable=False,
        decision_hard_blockers=["canonical_asset_identity_untrusted"],
    )
    groups = group_decision_rows(
        (testlist, testunlock, testrumor, diagnostic),
        include_diagnostics=True,
    )

    assert {row["candidate_id"] for row in groups["calendar_risk"]} == {
        "testlist-calendar", "testunlock-calendar", "testrumor-calendar",
    }
    assert groups["decision_diagnostic"] == [diagnostic]
    for raw in (testlist, testunlock, testrumor):
        projected = decision_model_values(raw)
        assert decision_preview_lane(raw) == decision_preview_lane(projected) == "calendar_risk"
    rumor_projection = decision_model_values(testrumor)
    assert rumor_projection["calendar_evidence_ids"] == []
    assert rumor_projection["calendar_evidence"][0]["evidence_reference"] == (
        "candidate_schedule:testrumor-calendar"
    )

    false_calendar = {
        **testlist,
        "unified_calendar_event": None,
        "radar_route": "calendar_risk",
    }
    assert "decision_model_calendar_risk_without_calendar_evidence" in validate_contract(false_calendar)
    assert decision_model_values(false_calendar) == {}
    assert decision_preview_lane(false_calendar) == "decision_diagnostic"


def test_closed_projection_fails_closed_on_tampered_context_or_safety():
    from copy import deepcopy

    from crypto_rsi_scanner.event_alpha.artifacts.schema.decision_model import validate_contract
    from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import decision_model_values

    projected = decision_model_values(_market_led_candidate())
    alias_drift = {**projected, "hard_blockers": ["hidden_downstream_override"]}
    unsafe = {
        **projected,
        "decision_safety_invariants": {
            **projected["decision_safety_invariants"],
            "no_live_trading": False,
        },
    }

    assert decision_model_values(alias_drift) == {}
    assert decision_model_values(unsafe) == {}

    calendar_projection = decision_model_values(_market_led_candidate(
        directional_bias="risk",
        confidence_band="exploratory",
        timing_state="scheduled",
        radar_route="calendar_risk",
        radar_route_reason="attached_calendar_or_scheduled_risk_research",
        radar_actionable=False,
        preferred_horizon="scheduled_window",
        unified_calendar_event={
            "calendar_event_id": "calendar-fomc-v2",
            "event_kind": "central_bank",
            "scheduled_at": "2026-06-15T20:00:00Z",
            "time_certainty": "exact",
            "importance": "high",
            "source": "Fixture Calendar",
            "source_url": "https://example.invalid/calendar/fomc",
        },
    ))
    assert calendar_projection
    malformed_calendar_rows = []
    for field, value in (
        ("calendar_event_id", {"id": "calendar-fomc-v2"}),
        ("category", ["central_bank"]),
        ("time_certainty", {"value": "exact"}),
        ("importance", 3),
        ("source", {"provider": "fixture"}),
        ("source_url", ["https://example.invalid/calendar/fomc"]),
    ):
        malformed = deepcopy(calendar_projection)
        malformed["calendar_evidence"][0][field] = value
        malformed_calendar_rows.append(malformed)
    malformed_ids = deepcopy(calendar_projection)
    malformed_ids["calendar_evidence_ids"] = [{"id": "calendar-fomc-v2"}]
    malformed_calendar_rows.append(malformed_ids)

    for malformed in malformed_calendar_rows:
        assert validate_contract(malformed)
        assert decision_model_values(malformed) == {}


def test_projection_rejects_non_text_observation_identity_and_lineage():
    from copy import deepcopy

    from crypto_rsi_scanner.event_alpha.artifacts.schema.decision_model import (
        validate_contract,
    )
    from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import (
        decision_model_values,
    )

    projected = decision_model_values(_market_led_candidate())
    assert projected

    malformed_observation_ids = deepcopy(projected)
    malformed_observation_ids["observation_ids"] = [{"id": "candidate-v2"}]
    malformed_lineage_provider = deepcopy(projected)
    malformed_lineage_provider["source_provider_lineage"]["providers"] = [
        {"provider": "fixture"}
    ]
    malformed_lineage_origin = deepcopy(projected)
    malformed_lineage_origin["source_provider_lineage"]["origins"] = [
        ["market_anomaly"]
    ]
    malformed_lineage_mode = deepcopy(projected)
    malformed_lineage_mode["source_provider_lineage"]["data_mode"] = {
        "mode": "fixture"
    }

    for malformed in (
        malformed_observation_ids,
        malformed_lineage_provider,
        malformed_lineage_origin,
        malformed_lineage_mode,
    ):
        assert validate_contract(malformed)
        assert decision_model_values(malformed) == {}

    for malformed_raw in (
        _market_led_candidate(observation_ids=[{"id": "candidate-v2"}]),
        _market_led_candidate(candidate_id={"id": "candidate-v2"}),
        _market_led_candidate(provider={"name": "fixture"}),
        _market_led_candidate(
            source_provider_lineage={
                "data_mode": "fixture",
                "providers": [{"provider": "fixture"}],
                "origins": ["market_anomaly"],
                "source_packs": ["market_anomaly_pack"],
            }
        ),
        _market_led_candidate(
            market_context_source="fixture",
            market_context_observed_at="2026-06-15T16:00:00Z",
            market_context_freshness_status="fresh",
            market_snapshot_id={"id": "market-snapshot-v2"},
        ),
    ):
        assert decision_model_values(malformed_raw) == {}


def test_projection_rejects_non_text_operator_rationale_collections():
    from copy import deepcopy

    from crypto_rsi_scanner.event_alpha.artifacts.schema.decision_model import (
        validate_contract,
    )
    from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import (
        decision_model_values,
    )

    projected = decision_model_values(_market_led_candidate())
    assert projected

    malformed_support = deepcopy(projected)
    malformed_support["supporting_facts"] = [{"fact": "liquid breakout"}]
    malformed_aliases = deepcopy(projected)
    malformed_aliases["decision_warnings"] = [
        {"warning": "unknown_catalyst"}
    ]
    malformed_aliases["warnings"] = [{"warning": "unknown_catalyst"}]
    malformed_risks = deepcopy(projected)
    malformed_risks["main_risks"] = [True]

    for malformed in (
        malformed_support,
        malformed_aliases,
        malformed_risks,
    ):
        assert validate_contract(malformed)
        assert decision_model_values(malformed) == {}

    for malformed_raw in (
        _market_led_candidate(thesis_origins=[{"origin": "market_led"}]),
        _market_led_candidate(
            decision_warnings=[{"warning": "unknown_catalyst"}]
        ),
        _market_led_candidate(why_still_worth_reviewing=[True]),
        _market_led_candidate(
            supporting_facts=[{"fact": "liquid breakout"}]
        ),
        _market_led_candidate(supporting_evidence_quotes=[["liquid breakout"]]),
        _market_led_candidate(main_risks=[1]),
    ):
        assert decision_model_values(malformed_raw) == {}


def test_projection_keeps_rsi_references_typed_and_bound_to_context():
    from copy import deepcopy

    from crypto_rsi_scanner.event_alpha.artifacts.schema.decision_model import (
        validate_contract,
    )
    from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import (
        decision_model_values,
    )

    context = {
        "context_version": "rsi_technical_context_v1",
        "valid": True,
        "symbol": "V2",
        "coin_id": "v2-coin",
        "setup_type": "dip_buy",
        "rsi_value": 24.0,
        "rsi_timeframe": "1d",
        "observed_at": "2026-06-15T15:00:00Z",
        "freshness_status": "fresh",
    }
    projected = decision_model_values(_market_led_candidate(
        rsi_context_version="rsi_technical_context_v1",
        rsi_context=context,
    ))
    assert projected
    expected_reference = {
        "context_version": "rsi_technical_context_v1",
        "symbol": "V2",
        "coin_id": "v2-coin",
        "setup_type": "dip_buy",
        "rsi_timeframe": "1d",
        "observed_at": "2026-06-15T15:00:00Z",
        "freshness_status": "fresh",
        "valid": True,
    }
    assert projected["rsi_context_references"] == [expected_reference]

    non_mapping_reference = deepcopy(projected)
    non_mapping_reference["rsi_context_references"].append(True)
    malformed_reference_value = deepcopy(projected)
    malformed_reference_value["rsi_context_references"][0]["observed_at"] = {
        "at": "2026-06-15T15:00:00Z"
    }
    drifted_reference = deepcopy(projected)
    drifted_reference["rsi_context_references"][0]["symbol"] = "OTHER"
    malformed_context = deepcopy(projected)
    malformed_context["rsi_context"]["setup_type"] = ["dip_buy"]

    for malformed in (
        non_mapping_reference,
        malformed_reference_value,
        drifted_reference,
        malformed_context,
    ):
        assert validate_contract(malformed)
        assert decision_model_values(malformed) == {}

    assert decision_model_values(_market_led_candidate(
        rsi_context=context,
        rsi_context_references=[expected_reference, True],
    )) == {}
    assert decision_model_values(_market_led_candidate(
        rsi_context=context,
        rsi_context_references=[{**expected_reference, "symbol": "OTHER"}],
    )) == {}


def test_v2_projection_fails_closed_on_malformed_actionable_route():
    from crypto_rsi_scanner.event_alpha.artifacts.schema.decision_model import validate_contract
    from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import (
        decision_model_values,
        decision_preview_lane,
        group_decision_rows,
    )

    malformed = _market_led_candidate(
        radar_actionable=False,
        confidence_band="diagnostic",
        tradability_status="blocked",
        decision_hard_blockers=["canonical_asset_identity_untrusted"],
    )

    errors = validate_contract(malformed)
    assert "decision_model_watch_route_not_actionable" in errors
    assert "decision_model_hard_blocker_non_diagnostic_route" in errors
    assert decision_model_values(malformed) == {}
    assert decision_preview_lane(malformed) == "decision_diagnostic"
    assert all(not rows for rows in group_decision_rows([malformed]).values())
    diagnostic = group_decision_rows([malformed], include_diagnostics=True)
    assert diagnostic["decision_diagnostic"] == [malformed]


def test_cards_daily_brief_and_preview_render_v2_transparently_and_no_send():
    from crypto_rsi_scanner.event_alpha.artifacts.research_cards import render_research_card
    from crypto_rsi_scanner.event_alpha.radar.integrated_radar import (
        build_integrated_notification_delivery_rows,
        format_integrated_daily_brief,
        format_integrated_notification_preview_from_deliveries,
    )

    candidate = _market_led_candidate(
        why_now="strict catalyst route is STORE_ONLY because source is missing",
        opportunity_type_why_now="strict catalyst route is STORE_ONLY because source is missing",
    )
    diagnostic = _market_led_candidate(
        candidate_id="diagnostic-v2",
        alert_key="diagnostic-v2",
        symbol="DIAG",
        coin_id="diag",
        asset_symbol="DIAG",
        asset_coin_id="diag",
        opportunity_type="DIAGNOSTIC",
        radar_route="diagnostic",
        radar_actionable=False,
        confidence_band="diagnostic",
    )
    card = render_research_card("candidate-v2", alert_rows=(candidate,))
    assert card.found is True
    for text in (
        "## Crypto Decision Radar",
        "## Catalyst Radar Classification",
        "Radar actionable: true",
        "Actionability components: liquidity=20; relative_move=18",
        "Actionability penalties: unknown_catalyst=5",
        "Evidence-confidence components: market_evidence=42",
        "Risk components: manipulation_risk=10",
        "Missing data: derivatives",
        "Why now: fresh liquid breakout with relative strength",
        "Why this is still worth human review: fresh liquid breakout with relative strength",
        "Catalyst unknown:",
        "Higher manipulation risk:",
        "Research idea, not a trade instruction.",
        "Dashboard: /candidate/core-v2",
    ):
        assert text in card.markdown
    assert "['fresh liquid breakout" not in card.markdown
    assert "not alertable" not in card.markdown.casefold()
    assert (
        "- Why now: strict catalyst route is STORE_ONLY because source is missing"
        in card.markdown.split("## Catalyst Radar Classification", 1)[1]
    )

    unblocked_diagnostic_card = render_research_card(
        "diagnostic-v2", alert_rows=(diagnostic,)
    )
    assert "- Operator classification: Diagnostic Research Control" in (
        unblocked_diagnostic_card.markdown
    )
    blocked_diagnostic = {
        **diagnostic,
        "candidate_id": "blocked-diagnostic-v2",
        "alert_key": "blocked-diagnostic-v2",
        "symbol": "BLOCKED",
        "asset_symbol": "BLOCKED",
        "decision_hard_blockers": ["liquidity_below_minimum"],
    }
    blocked_diagnostic_card = render_research_card(
        "blocked-diagnostic-v2", alert_rows=(blocked_diagnostic,)
    )
    assert "- Operator classification: Blocked Diagnostic" in (
        blocked_diagnostic_card.markdown
    )

    deliveries = build_integrated_notification_delivery_rows((candidate, diagnostic))
    by_lane = {row["lane"]: row for row in deliveries}
    assert deliveries[0]["lane"] == "high_confidence"
    assert deliveries[1]["lane"] == "actionable"
    assert next(
        index for index, row in enumerate(deliveries) if row["lane"] == "unconfirmed_research"
    ) > next(index for index, row in enumerate(deliveries) if row["lane"] == "actionable")
    assert "unconfirmed_research" in by_lane
    assert "actionable" in by_lane
    assert "decision_diagnostic" not in by_lane
    assert by_lane["source_provider_health"]["skipped_item_count"] >= 1
    assert all(row["sent"] is False for row in deliveries)
    assert all(row["no_send_rehearsal"] is True for row in deliveries)

    brief = format_integrated_daily_brief(
        (candidate, diagnostic), delivery_rows=deliveries
    )
    preview = format_integrated_notification_preview_from_deliveries(
        deliveries, candidates=(candidate, diagnostic)
    )
    assert "## Actionable Ideas" in brief
    assert "## High-Confidence Ideas" in brief
    assert "## Rapid Market Anomalies" in brief
    assert "## Dashboard Watch" in brief
    assert "## Fade / Exhaustion Review" in brief
    assert "## Risk Watch" in brief
    assert "## Calendar / Scheduled Risk" in brief
    assert "Crypto Radar v2: route=actionable_watch" in brief
    assert "## Lane: Actionable Ideas" in preview
    assert "Decision why now: fresh liquid breakout with relative strength" in preview
    assert (
        "Catalyst Radar why now: strict catalyst route is STORE_ONLY because source is missing"
        in preview
    )
    assert "Catalyst unknown:" in preview
    assert "Higher manipulation risk:" in preview
    assert "Research idea, not a trade instruction." in preview
    assert "send_attempted: false" in preview
    assert "delivered: false" in preview


def test_v2_outcomes_inbox_and_feedback_keep_decision_context(tmp_path: Path):
    from crypto_rsi_scanner.event_alpha.artifacts import schema_v1
    from crypto_rsi_scanner.event_alpha.notifications.inbox.builder import _inbox_item
    from crypto_rsi_scanner.event_alpha.notifications.inbox.render import _append_item_section
    from crypto_rsi_scanner.event_alpha.outcomes.feedback_labels import (
        EventFeedbackConfig,
        load_feedback,
        mark_feedback,
        valid_labels,
    )
    from crypto_rsi_scanner.event_alpha.outcomes.integrated_radar_outcomes import (
        _outcome_row,
        write_integrated_radar_outcome_placeholders,
    )
    from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import (
        decision_model_values,
    )

    candidate = _market_led_candidate(
        symbol="TESTPERP",
        asset_symbol="TESTPERP",
        opportunity_type="CONFIRMED_LONG_RESEARCH",
    )
    outcome = _outcome_row(candidate, now="2026-06-15T17:00:00Z")
    assert outcome["thesis_origin"] == "market_led"
    assert outcome["catalyst_status"] == "unknown"
    assert outcome["confidence_band"] == "actionable"
    assert outcome["primary_thesis_origin"] == "market_led"
    assert outcome["thesis_origins"] == ["market_led"]
    assert outcome["market_phase"] == "breakout"
    assert outcome["evidence_confidence_score_cohort"] == "45_64"
    assert outcome["risk_score_cohort"] == "25_44"
    assert outcome["actionability_score_cohort"] == "70_84"
    assert outcome["anomaly_type"] == "high_liquidity_breakout"
    assert outcome["normal_rsi_signal_written"] is False
    assert outcome["triggered_fade_created"] is False

    placeholder_candidate = {
        **candidate,
        "run_id": "decision-v2-run",
        "profile": "fixture",
        "artifact_namespace": "decision_v2",
        "observed_at": "2026-06-15T16:00:00+00:00",
    }
    placeholders = write_integrated_radar_outcome_placeholders(
        tmp_path,
        (placeholder_candidate,),
        observed_at="2026-06-15T16:01:00+00:00",
    )
    assert len(placeholders) == 1
    assert placeholders[0]["outcome_data_source"] == "pending_observation"
    assert placeholders[0]["outcome_status"] == "pending"
    assert placeholders[0]["automatic_outcome"] is True
    assert placeholders[0]["human_preference_feedback"] is None
    assert placeholders[0]["calibration_eligible"] is False
    assert placeholders[0]["normal_rsi_signal_written"] is False
    assert placeholders[0]["triggered_fade_created"] is False
    assert schema_v1.validate_row_against_schema(
        placeholders[0], "outcome_row_v1"
    ) == []

    item = _inbox_item(candidate, None, {}, set(), {})
    assert item.radar_route == "actionable_watch"
    assert item.decision_projection == decision_model_values(candidate)
    assert item.primary_thesis_origin == "market_led"
    assert item.thesis_origins == ("market_led",)
    assert item.spread_status == "verified_good"
    assert item.urgency_score == 74.0
    assert item.market_phase == "breakout"
    assert item.preferred_horizon == "1d_3d"
    assert item.chase_risk_score == 31.0
    assert item.actionability_score == 84.0
    assert item.why_still_worth_reviewing == (
        "fresh liquid breakout with relative strength",
    )
    lines: list[str] = []
    _append_item_section(lines, "v2", (item,), profile="fixture")
    rendered = "\n".join(lines)
    assert "feedback_manipulation_risk" in rendered
    assert "radar_timing: phase=breakout" in rendered
    assert "feedback_missing_confirmation" in rendered
    assert "feedback_late" in rendered
    assert "feedback_useful" in rendered

    assert {"useful", "late", "manipulation_risk", "missing_confirmation"} <= set(valid_labels())
    cfg = EventFeedbackConfig(tmp_path / "feedback.jsonl")
    marked = mark_feedback(
        "core-v2",
        "manipulation_risk",
        cfg=cfg,
        context_rows=(candidate,),
    )
    assert marked.radar_route == "actionable_watch"
    assert marked.actionability_score == 84.0
    assert marked.why_still_worth_reviewing == (
        "fresh liquid breakout with relative strength",
    )
    loaded = load_feedback(cfg.path).records
    assert loaded[0].label == "manipulation_risk"
    assert loaded[0].decision_missing_data == ("derivatives",)


def test_canonical_daily_brief_v2_preview_is_explicit_and_config_gated():
    from unittest.mock import patch

    from crypto_rsi_scanner import config
    from crypto_rsi_scanner.event_alpha.artifacts.daily_brief import build_daily_brief

    candidate = _market_led_candidate()
    diagnostic = _market_led_candidate(
        candidate_id="diagnostic-v2",
        core_opportunity_id="diagnostic-core-v2",
        alert_key="diagnostic-v2",
        symbol="DIAG",
        coin_id="diag",
        asset_symbol="DIAG",
        asset_coin_id="diag",
        event_name="Explicit v2 diagnostic",
        radar_route="diagnostic",
        radar_actionable=False,
        confidence_band="diagnostic",
    )
    legacy = {
        **candidate,
        "candidate_id": "legacy-row",
        "core_opportunity_id": "legacy-core",
        "symbol": "LEGACY",
        "coin_id": "legacy",
        "asset_symbol": "LEGACY",
        "asset_coin_id": "legacy",
        "decision_model_version": None,
        "decision_model_enabled": None,
    }

    with patch.object(config, "EVENT_ALPHA_DECISION_MODEL_V2_PREVIEW_ENABLED", False):
        disabled = build_daily_brief(
            core_opportunity_rows=(candidate, diagnostic, legacy),
            include_api_artifacts=True,
        )
    assert "Crypto Radar Decision Model v2 Preview" not in disabled

    with (
        patch.object(config, "EVENT_ALPHA_DECISION_MODEL_V2_PREVIEW_ENABLED", True),
        patch.object(config, "EVENT_ALPHA_DECISION_MODEL_V2_SHOW_DIAGNOSTICS", True),
    ):
        default_hidden = build_daily_brief(
            core_opportunity_rows=(candidate, diagnostic, legacy),
            include_diagnostics=False,
            include_api_artifacts=True,
        )
    assert "## Crypto Radar Decision Model v2 Preview" in default_hidden
    assert "### Actionable Ideas" in default_hidden
    assert "### High-Confidence Ideas" in default_hidden
    assert "### Rapid Market Anomalies" in default_hidden
    assert "### Dashboard Watch" in default_hidden
    assert "### Fade / Exhaustion Review" in default_hidden
    assert "### Risk Watch" in default_hidden
    assert "### Calendar / Scheduled Risk" in default_hidden
    assert "Actionability components: liquidity=20; relative_move=18" in default_hidden
    assert "Actionability penalties: unknown_catalyst=5" in default_hidden
    assert "Evidence-confidence components: market_evidence=42" in default_hidden
    assert "Risk components: manipulation_risk=10" in default_hidden
    assert "Catalyst unknown:" in default_hidden
    assert "Research idea, not a trade instruction." in default_hidden
    assert "#### DIAG/diag" not in default_hidden
    assert "#### LEGACY/legacy" not in default_hidden

    with (
        patch.object(config, "EVENT_ALPHA_DECISION_MODEL_V2_PREVIEW_ENABLED", True),
        patch.object(config, "EVENT_ALPHA_DECISION_MODEL_V2_SHOW_DIAGNOSTICS", True),
    ):
        diagnostics = build_daily_brief(
            core_opportunity_rows=(candidate, diagnostic, legacy),
            include_diagnostics=True,
            include_api_artifacts=True,
        )
    assert "### Decision Diagnostics" in diagnostics
    assert "#### DIAG/diag - Explicit v2 diagnostic" in diagnostics
    assert "#### LEGACY/legacy" not in diagnostics

    with (
        patch.object(config, "EVENT_ALPHA_DECISION_MODEL_V2_PREVIEW_ENABLED", True),
        patch.object(config, "EVENT_ALPHA_DECISION_MODEL_V2_SHOW_DIAGNOSTICS", False),
    ):
        config_hidden = build_daily_brief(
            core_opportunity_rows=(candidate, diagnostic),
            include_diagnostics=True,
            include_api_artifacts=True,
        )
    assert "### Decision Diagnostics" not in config_hidden


def test_feedback_report_cohorts_only_explicit_v2_rows(tmp_path: Path):
    from dataclasses import replace

    from crypto_rsi_scanner.event_alpha.outcomes.feedback_labels import (
        EventFeedbackConfig,
        EventFeedbackReadResult,
        format_feedback_report,
        mark_feedback,
    )

    record = mark_feedback(
        "core-v2",
        "useful",
        cfg=EventFeedbackConfig(tmp_path / "feedback.jsonl"),
        context_rows=(_market_led_candidate(),),
    )
    legacy = replace(
        record,
        feedback_id="legacy-feedback",
        target="legacy-core",
        decision_model_version=None,
        decision_model_enabled=None,
        thesis_origin="catalyst_led",
        catalyst_status="confirmed",
        confidence_band="high_confidence",
        actionability_score_cohort="85_100",
        anomaly_type="legacy_should_not_count",
        label="junk",
    )
    report = format_feedback_report(EventFeedbackReadResult(
        path=tmp_path / "feedback.jsonl",
        rows_read=2,
        records=[record, legacy],
    ))
    cohort_section = report.split(
        "Crypto Radar Decision Model v2 feedback cohorts (explicit v2 rows only):",
        1,
    )[1]
    assert "- explicit_v2_rows: 1" in cohort_section
    assert "- thesis_origin:\n  - market_led: rows=1 labels=useful=1" in cohort_section
    assert "- catalyst_status:\n  - unknown: rows=1 labels=useful=1" in cohort_section
    assert "- confidence_band:\n  - actionable: rows=1 labels=useful=1" in cohort_section
    assert "- actionability_score_cohort:\n  - 70_84: rows=1 labels=useful=1" in cohort_section
    assert "- anomaly_type:\n  - high_liquidity_breakout: rows=1 labels=useful=1" in cohort_section
    assert "catalyst_led" not in cohort_section
    assert "legacy_should_not_count" not in cohort_section
