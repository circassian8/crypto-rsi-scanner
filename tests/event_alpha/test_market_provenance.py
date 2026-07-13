"""Closed market-provenance and downstream propagation regressions."""

from __future__ import annotations

import re


_OBSERVED = "2026-06-15T16:00:00Z"
_LEDGER_SHA = "1" * 64
_SOURCE_SHA = "2" * 64


def _provenance(**overrides):
    row = {
        "schema_version": "crypto_radar_market_provenance_v2",
        "measurement_program": "decision_radar_live_observation_campaign_v2",
        "data_acquisition_mode": "live_provider",
        "candidate_source_mode": "live_no_send",
        "provider": "coingecko",
        "provider_call_attempted": True,
        "provider_call_succeeded": True,
        "live_provider_authorized": True,
        "request_ledger_path": "event_market_request_ledger.jsonl",
        "request_ledger_sha256": _LEDGER_SHA,
        "provider_source_artifact": "event_market_source_rows.jsonl",
        "provider_source_artifact_sha256": _SOURCE_SHA,
        "provider_generation_id": "market-generation-1",
        "cache_status": "write_through",
        "feature_basis": {
            "liquidity": "direct_coingecko_volume",
            "spread": "direct_execution_quality",
        },
        "data_quality": {"freshness_status": "fresh", "unit_status": "normalized"},
    }
    row.update(overrides)
    return row


def _decision_candidate(market_provenance):
    return {
        "schema_version": 1,
        "row_type": "event_integrated_radar_candidate",
        "candidate_id": "market-provenance-candidate",
        "core_opportunity_id": "market-provenance-core",
        "run_id": "market-provenance-run",
        "profile": "live_burn_in_no_send",
        "run_mode": "burn_in",
        "artifact_namespace": "market-provenance",
        "observed_at": _OBSERVED,
        "symbol": "PROV",
        "coin_id": "provenance-token",
        "opportunity_type": "UNCONFIRMED_RESEARCH",
        "source_origin": "market_anomaly",
        "source_origins": ["market_anomaly"],
        "source_pack": "market_anomaly_pack",
        "source_packs": ["market_anomaly_pack"],
        "market_context_source": "coingecko",
        "market_context_observed_at": _OBSERVED,
        "market_context_freshness_status": "fresh",
        "market_data_freshness": "fresh",
        "market_snapshot_id": "market-history-observation-1",
        "market_snapshot": {
            "market_data_source": "coingecko",
            "observed_at": _OBSERVED,
            "freshness_status": "fresh",
            "market_snapshot_id": "market-history-observation-1",
        },
        "market_provenance": market_provenance,
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
        "actionability_score": 82.0,
        "evidence_confidence_score": 63.0,
        "risk_score": 37.0,
        "urgency_score": 70.0,
        "market_phase": "breakout",
        "preferred_horizon": "1d_3d",
        "expires_at": "2026-06-16T16:00:00+00:00",
        "chase_risk_score": 32.0,
        "actionability_score_components": {"market_strength": 30.0},
        "actionability_penalty_components": {"unknown_catalyst": 5.0},
        "evidence_confidence_score_components": {"market_evidence": 42.0},
        "risk_score_components": {"manipulation_risk": 10.0},
        "decision_hard_blockers": [],
        "decision_soft_penalties": ["catalyst_unknown_soft_penalty"],
        "decision_missing_data": ["derivatives"],
        "decision_warnings": ["catalyst_unknown", "research_only_not_trade_instruction"],
        "why_still_worth_reviewing": ["fresh liquid market-led move"],
        "radar_what_confirms": ["continued volume-backed follow-through"],
        "radar_what_invalidates": ["failed breakout"],
        "actionability_score_cohort": "80_100",
        "anomaly_type": "high_liquidity_breakout",
        "research_only": True,
        "created_alert": False,
        "sent": False,
        "telegram_sends": 0,
        "trade_created": False,
        "paper_trade_created": False,
        "normal_rsi_signal_written": False,
        "triggered_fade_created": False,
    }


def test_mock_provenance_is_explicitly_never_burn_in_counted():
    from crypto_rsi_scanner.event_alpha.operations.market_provenance import (
        normalize_market_provenance,
    )

    normalized = normalize_market_provenance(
        _provenance(
            data_acquisition_mode="mock",
            candidate_source_mode="mocked_fixture",
            provider="mock_coingecko",
            live_provider_authorized=False,
            provider_generation_id="mock-generation-1",
            cache_status="not_applicable",
            provenance_contract_valid=True,
            burn_in_eligible=True,
            burn_in_counted=True,
        )
    )

    assert normalized["provenance_contract_valid"] is True
    assert normalized["data_acquisition_mode"] == "mocked_fixture"
    assert normalized["candidate_source_mode"] == "mocked_fixture"
    assert normalized["burn_in_eligible"] is False
    assert normalized["burn_in_counted"] is False
    assert normalized["burn_in_reason"] == "not_counted_separate_decision_radar_campaign"
    assert normalized["decision_radar_campaign_counted"] is False
    assert normalized["decision_radar_campaign_reason"] == "not_counted_non_live_mode:mocked_fixture"


def test_exact_authorized_live_no_send_campaign_provenance_is_counted_separately():
    from crypto_rsi_scanner.event_alpha.operations.market_provenance import (
        normalize_market_provenance,
    )

    normalized = normalize_market_provenance(_provenance())

    assert normalized["provenance_contract_valid"] is True
    assert normalized["decision_radar_campaign_eligible"] is True
    assert normalized["decision_radar_campaign_counted"] is True
    assert normalized["burn_in_eligible"] is False
    assert normalized["burn_in_counted"] is False
    assert normalized["burn_in_reason"] == "not_counted_separate_decision_radar_campaign"
    assert normalized["validation_errors"] == []


def test_decision_campaign_counting_is_separate_from_event_alpha_burn_in():
    from crypto_rsi_scanner.event_alpha.operations.market_provenance import (
        DECISION_RADAR_MEASUREMENT_PROGRAM,
        market_provenance_flat_fields,
        normalize_market_provenance,
    )

    normalized = normalize_market_provenance(
        _provenance(measurement_program=DECISION_RADAR_MEASUREMENT_PROGRAM)
    )
    flattened = market_provenance_flat_fields(normalized)

    assert normalized["provenance_contract_valid"] is True
    assert normalized["decision_radar_campaign_eligible"] is True
    assert normalized["decision_radar_campaign_counted"] is True
    assert normalized["decision_radar_campaign_reason"] == "counted_live_no_send_exact_lineage"
    assert normalized["burn_in_eligible"] is False
    assert normalized["burn_in_counted"] is False
    assert normalized["burn_in_reason"] == "not_counted_separate_decision_radar_campaign"
    assert flattened["contract_counted_candidate"] is True


def test_decision_campaign_projection_requires_complete_market_context_lineage():
    from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import (
        decision_model_values,
    )

    projected = decision_model_values(_decision_candidate(_provenance()))
    assert projected["market_context_reference"]["market_snapshot_id"]

    partial = {
        **projected,
        "market_context_reference": {"source": "coingecko"},
    }
    missing = {**projected, "market_context_reference": {}}
    assert decision_model_values(partial) == {}
    assert decision_model_values(missing) == {}


def test_runner_v2_aliases_normalize_with_row_feature_context():
    from crypto_rsi_scanner.event_alpha.operations.market_provenance import (
        market_provenance_values,
    )

    runner_provenance = {
        "contract_version": 2,
        "data_mode": "live",
        "data_acquisition_mode": "live_provider",
        "candidate_source_mode": "live_no_send",
        "provider": "coingecko",
        "provider_generation_id": "market-generation-1",
        "live_provider_authorized": True,
        "fixture_mode": False,
        "provider_call_attempted": True,
        "provider_request_succeeded": True,
        "provider_source_artifact": "event_market_source_rows.jsonl",
        "provider_source_sha256": _SOURCE_SHA,
        "request_ledger_path": "event_market_request_ledger.jsonl",
        "request_ledger_sha256": _LEDGER_SHA,
        "cache_status": "fresh_request_artifact",
        # These asserted trust fields must still be recomputed downstream.
        "provenance_contract_valid": False,
        "burn_in_eligible": False,
        "burn_in_counted": False,
    }
    normalized = market_provenance_values({
        "market_provenance": runner_provenance,
        "market_feature_basis": {"spread": "direct_execution_quality"},
        "market_data_quality": {"freshness_status": "fresh"},
    })

    assert normalized["schema_version"] == "crypto_radar_market_provenance_v2"
    assert normalized["contract_version"] == 2
    assert normalized["cache_status"] == "write_through"
    assert normalized["provider_source_artifact_sha256"] == _SOURCE_SHA
    assert normalized["feature_basis"] == {"spread": "direct_execution_quality"}
    assert normalized["data_quality"] == {"freshness_status": "fresh"}
    assert normalized["provenance_contract_valid"] is True
    assert normalized["burn_in_counted"] is True


def test_spoofed_live_count_claim_is_recomputed_and_rejected():
    from crypto_rsi_scanner.event_alpha.operations.market_provenance import (
        normalize_market_provenance,
    )

    normalized = normalize_market_provenance(
        _provenance(
            live_provider_authorized=False,
            request_ledger_path="event_market_source_rows.jsonl",
            provenance_contract_valid=True,
            burn_in_eligible=True,
            burn_in_counted=True,
        )
    )

    assert normalized["provenance_contract_valid"] is False
    assert normalized["burn_in_eligible"] is False
    assert normalized["burn_in_counted"] is False
    assert "live_provider_not_authorized" in normalized["validation_errors"]
    assert "request_ledger_source_artifact_not_distinct" in normalized["validation_errors"]


def test_operator_state_accepts_only_canonical_valid_market_provenance():
    from crypto_rsi_scanner.event_alpha.artifacts.schema.operator_state import (
        _validate_market_no_send_provenance,
    )
    from crypto_rsi_scanner.event_alpha.operations.market_provenance import (
        normalize_market_provenance,
    )

    valid = normalize_market_provenance(
        _provenance(
            request_ledger_path="event_market_no_send_request_ledger.json",
            provider_source_artifact="event_market_no_send_market_rows.json",
        )
    )
    assert _validate_market_no_send_provenance(valid) == []

    noncanonical = {**valid, "provider_call_attempted": "true"}
    assert "operator_state_market_no_send_provenance_not_canonical" in (
        _validate_market_no_send_provenance(noncanonical)
    )

    invalid = normalize_market_provenance(
        _provenance(
            live_provider_authorized=False,
            request_ledger_path="event_market_no_send_request_ledger.json",
            provider_source_artifact="event_market_no_send_market_rows.json",
        )
    )
    assert "operator_state_market_no_send_provenance_contract_invalid" in (
        _validate_market_no_send_provenance(invalid)
    )


def test_provenance_survives_merge_projection_core_preview_and_pending_outcome():
    from crypto_rsi_scanner.event_alpha.operations.market_provenance import (
        normalize_market_provenance,
    )
    from crypto_rsi_scanner.event_alpha.outcomes.integrated_radar_outcome_rows import (
        _outcome_placeholder_row,
    )
    from crypto_rsi_scanner.event_alpha.radar.core.merge import (
        _apply_integrated_candidate_truth,
    )
    from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import (
        decision_model_markdown_lines,
        decision_model_values,
    )
    from crypto_rsi_scanner.event_alpha.radar.integrated import api as integrated_radar
    from crypto_rsi_scanner.event_alpha.radar.market_reaction import (
        MarketReactionResult,
        MarketStateSnapshot,
    )

    candidate = _decision_candidate(_provenance())
    normalized = normalize_market_provenance(candidate["market_provenance"])
    merged = integrated_radar._merge_family(
        "market-provenance-family",
        [candidate],
        profile="no_key_live",
        artifact_namespace="market-provenance",
        run_mode="operational",
        run_id="market-provenance-run",
        observed_at=_OBSERVED,
    )
    assert merged["market_provenance"] == normalized
    assert merged["contract_counted_candidate"] is True

    projected = decision_model_values(candidate)
    assert projected["market_provenance"] == normalized
    assert projected["source_provider_lineage"]["market_provenance"] == normalized
    assert projected["source_provider_lineage"]["data_mode"] == "live_provider"
    assert projected["candidate_source_mode"] == "live_no_send"
    assert projected["burn_in_counted"] is False
    assert projected["decision_radar_campaign_counted"] is True
    assert projected["market_context_reference"] == {
        "source": "coingecko",
        "observed_at": _OBSERVED,
        "freshness_status": "fresh",
        "market_snapshot_id": "market-history-observation-1",
    }
    assert decision_model_values(projected) == projected

    reaction = MarketReactionResult(
        market_state_snapshot=MarketStateSnapshot(),
        market_state="no_reaction",
        opportunity_type="UNCONFIRMED_RESEARCH",
        why_now="generic fallback",
    )
    core = _apply_integrated_candidate_truth(
        {}, primary=candidate, all_rows=(candidate,), reaction=reaction
    )
    assert core["market_provenance"] == normalized
    assert core["burn_in_counted"] is False
    assert core["decision_radar_campaign_counted"] is True
    assert core["contract_counted_candidate"] is True
    assert core["market_context_reference"] == projected["market_context_reference"]
    assert core["decision_projection"]["market_context_reference"] == projected[
        "market_context_reference"
    ]

    preview = "\n".join(decision_model_markdown_lines(candidate))
    assert "live_provider / live_no_send / coingecko" in preview
    assert "Decision Radar campaign eligible / counted: true / true" in preview
    assert (
        "Market context reference: source=coingecko; "
        f"observed_at={_OBSERVED}; freshness=fresh; "
        "snapshot_id=market-history-observation-1"
    ) in preview

    outcome = _outcome_placeholder_row(candidate, now=_OBSERVED)
    assert outcome["market_provenance"] == normalized
    assert outcome["decision_projection"]["market_provenance"] == normalized
    assert outcome["decision_projection"]["market_context_reference"] == projected[
        "market_context_reference"
    ]
    assert outcome["burn_in_eligible"] is False
    assert outcome["burn_in_counted"] is False
    assert outcome["decision_radar_campaign_counted"] is True
    assert outcome["contract_counted_candidate"] is True


def test_research_card_keeps_hash_lineage_without_rendering_full_digests():
    from crypto_rsi_scanner.event_alpha.artifacts.research_cards import (
        render_research_card,
    )

    provenance = _provenance()
    candidate = {
        **_decision_candidate(provenance),
        "request_ledger_sha256": provenance["request_ledger_sha256"],
        "provider_source_artifact_sha256": provenance[
            "provider_source_artifact_sha256"
        ],
        "request_ledger_path": provenance["request_ledger_path"],
        "provider_source_artifact": provenance["provider_source_artifact"],
    }

    card = render_research_card(
        candidate["core_opportunity_id"], alert_rows=(candidate,)
    )

    assert card.found is True
    assert (
        "- Request/source SHA-256 recorded in canonical provenance: true / true"
        in card.markdown
    )
    assert "- Request ledger: event_market_request_ledger.jsonl" in card.markdown
    assert "- Provider source artifact: event_market_source_rows.jsonl" in card.markdown
    assert (
        "- Market context reference: source=coingecko; "
        f"observed_at={_OBSERVED}; freshness=fresh; "
        "snapshot_id=market-history-observation-1"
    ) in card.markdown
    assert _LEDGER_SHA not in card.markdown
    assert _SOURCE_SHA not in card.markdown
    assert re.search(r"\b[A-Fa-f0-9]{32,}\b", card.markdown) is None
