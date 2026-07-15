"""Closed catalyst-attribution propagation and copy-boundary regressions."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone


NOW = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)


def _raw_pair():
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent

    anomaly = RawDiscoveredEvent(
        raw_id="market_anomaly:TEST:1",
        provider="market_anomaly",
        fetched_at=NOW,
        published_at=NOW,
        source_url=None,
        title="TEST market anomaly",
        body="Test Token moved with no known catalyst.",
        raw_json={
            "market": {"symbol": "TEST", "coin_id": "test-token"},
            "anomaly": {"score": 90},
        },
        source_confidence=0.8,
        content_hash="anomaly-source-hash",
    )
    source = RawDiscoveredEvent(
        raw_id="official-test-listing",
        provider="official_exchange",
        fetched_at=NOW + timedelta(minutes=35),
        published_at=NOW + timedelta(minutes=30),
        source_url="https://exchange.example/test",
        title="Official exchange lists Test Token (TEST)",
        body="TEST spot trading is now available.",
        raw_json={
            "event": {
                "event_id": "official-test-listing",
                "event_name": "Official exchange lists Test Token (TEST)",
                "event_type": "exchange_listing",
            }
        },
        source_confidence=0.9,
        content_hash="listing-source-hash",
    )
    return anomaly, source


def _integrated_rows(*, published_at: str, role: str, impact_strength: str = "unknown"):
    identity = {
        "symbol": "TEST",
        "coin_id": "test-token",
        "canonical_asset_id": "test-token",
        "validated_symbol": "TEST",
        "validated_coin_id": "test-token",
        "instrument_resolver_status": "resolved",
        "instrument_resolver_confidence": 0.95,
        "instrument_identity_trusted": True,
        "is_tradable_asset": True,
    }
    market = {
        **identity,
        "row_type": "event_market_anomaly",
        "market_anomaly_id": "anomaly-test-1",
        "market_state": "confirmed_breakout",
        "market_state_class": "confirmed_breakout",
        "anomaly_bucket": "high_liquidity_breakout",
        "market_anomaly_bucket": "high_liquidity_breakout",
        "observed_at": NOW.isoformat(),
        "source_pack": "market_anomaly_pack",
        "research_only": True,
        "market_state_snapshot": {
            "return_unit": "percent_points",
            "return_4h": 12.0,
            "return_24h": 20.0,
            "relative_return_vs_btc_4h": 9.0,
            "volume_zscore_24h": 3.5,
            "volume_to_market_cap": 0.3,
            "liquidity_usd": 12_000_000,
            "spread_bps": 22.0,
            "freshness_status": "fresh",
            "observed_at": NOW.isoformat(),
        },
    }
    source = {
        **identity,
        "row_type": "official_listing_candidate",
        "provider": "official_exchange",
        "title": "Official exchange lists Test Token (TEST)",
        "source_url": "https://exchange.example/test",
        "published_at": published_at,
        "fetched_at": (NOW + timedelta(hours=2)).isoformat(),
        "source_class": "official_exchange",
        "source_pack": "official_exchange_listing_pack",
        "impact_path_type": "listing_liquidity_event",
        "accepted_evidence_count": 1,
        "source_strength": "official_structured",
        "candidate_role": role,
        "main_frame_role": "main_catalyst" if role == "direct_beneficiary" else role,
        "impact_path_strength": impact_strength,
    }
    return market, source


def _build_integrated(market, source):
    from crypto_rsi_scanner.event_alpha.radar.integrated_radar import (
        build_integrated_candidates,
    )

    return build_integrated_candidates(
        sidecar_rows={"market_anomaly": [market], "official_exchange": [source]},
        profile="fixture",
        artifact_namespace="catalyst_attribution_propagation",
        run_mode="fixture",
        run_id="catalyst-attribution-propagation",
        observed_at=NOW + timedelta(hours=2),
        asset_registry=(),
    )[0]


def test_raw_attachment_discovery_and_alert_copy_exact_retrospective_attribution():
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
    import crypto_rsi_scanner.event_alpha.radar.catalyst_attribution as attribution
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as catalyst_search
    import crypto_rsi_scanner.event_alpha.radar.discovery as discovery
    from crypto_rsi_scanner.event_core.models import DiscoveredAsset

    anomaly, source = _raw_pair()
    attached = catalyst_search.attach_search_results_to_anomaly(anomaly, (source,))
    value = attached[1].raw_json["catalyst_attribution"]

    assert not attribution.validate_source_binding(value, attached[0], attached[1])
    assert value["temporal_relation"] == "retrospective"
    assert value["evidence_use"] == "retrospective_context"
    assert value["causal_eligible"] is False
    assert "catalyst_attribution" not in source.raw_json

    asset = DiscoveredAsset(
        coin_id="test-token",
        symbol="TEST",
        name="Test Token",
        aliases=("test token", "test"),
    )
    result = discovery.run_discovery(
        attached,
        (asset,),
        now=NOW + timedelta(hours=1),
    )
    candidate = next(
        item for item in result.candidates
        if item.event.raw_ids == (source.raw_id,)
    )
    assert candidate.data_quality["catalyst_attributions"] == [value]
    alert = next(
        item for item in event_alerts.build_event_alert_candidates(
            result,
            now=NOW + timedelta(hours=1),
        )
        if item.discovery_candidate.event.raw_ids == (source.raw_id,)
    )
    assert alert.score_components["catalyst_attributions"] == [value]
    assert alert.score_components["catalyst_attributions"][0] is not value


def test_discovery_drops_attribution_that_no_longer_binds_exact_raw_source():
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as catalyst_search
    import crypto_rsi_scanner.event_alpha.radar.discovery as discovery
    from crypto_rsi_scanner.event_core.models import DiscoveredAsset

    anomaly, source = _raw_pair()
    attached = catalyst_search.attach_search_results_to_anomaly(anomaly, (source,))
    payload = deepcopy(attached[1].raw_json)
    payload["catalyst_attribution"]["source_id"] = "different-source"
    tampered = replace(attached[1], raw_json=payload)
    result = discovery.run_discovery(
        (attached[0], tampered),
        (
            DiscoveredAsset(
                coin_id="test-token",
                symbol="TEST",
                name="Test Token",
                aliases=("test token", "test"),
            ),
        ),
        now=NOW + timedelta(hours=1),
    )
    source_candidate = next(
        item for item in result.candidates
        if item.event.raw_ids == (source.raw_id,)
    )
    assert source_candidate.data_quality["catalyst_attributions"] == []


def test_integrated_and_core_copy_closed_attribution_without_input_mutation_or_side_effects():
    import crypto_rsi_scanner.event_alpha.radar.catalyst_attribution as attribution
    from crypto_rsi_scanner.event_alpha.radar.core.serialization import (
        _row_from_core_opportunity,
    )
    from crypto_rsi_scanner.event_alpha.radar.core_opportunities import (
        aggregate_core_opportunities,
    )

    post_market, post_source = _integrated_rows(
        published_at=(NOW + timedelta(minutes=30)).isoformat(),
        role="background_context",
    )
    original_market = deepcopy(post_market)
    original_source = deepcopy(post_source)
    post = _build_integrated(post_market, post_source)
    post_value = post["catalyst_attribution"]

    assert not attribution.validate_contract(post_value)
    assert post_value["temporal_relation"] == "retrospective"
    assert post_value["evidence_use"] == "retrospective_context"
    assert post_value["causal_eligible"] is False
    assert post["catalyst_attributions"] == [post_value]
    assert post_market == original_market
    assert post_source == original_source
    for field in (
        "created_alert",
        "triggered_fade_created",
        "paper_trade_created",
        "normal_rsi_signal_written",
        "notification_send_enabled",
    ):
        assert post[field] is False

    core = aggregate_core_opportunities((post,))[0]
    core_row = _row_from_core_opportunity(
        core,
        generated_at=(NOW + timedelta(hours=2)).isoformat(),
        run_id="catalyst-attribution-propagation",
        profile="fixture",
        run_mode="fixture",
        artifact_namespace="catalyst_attribution_propagation",
    )
    assert core_row["catalyst_attribution"] == post_value
    assert core_row["catalyst_attributions"] == [post_value]

    pre_market, pre_source = _integrated_rows(
        published_at=(NOW - timedelta(minutes=30)).isoformat(),
        role="direct_beneficiary",
        impact_strength="strong",
    )
    pre = _build_integrated(pre_market, pre_source)
    assert pre["catalyst_attribution"]["temporal_relation"] == "antecedent"
    assert pre["catalyst_attribution"]["evidence_use"] == "causal_candidate"
    assert pre["catalyst_attribution"]["causal_eligible"] is True


def test_integrated_dedupes_already_valid_attributions_without_stringifying_them():
    import crypto_rsi_scanner.event_alpha.radar.catalyst_attribution as attribution

    market, source = _integrated_rows(
        published_at=(NOW - timedelta(minutes=30)).isoformat(),
        role="direct_beneficiary",
        impact_strength="strong",
    )
    market["_source_origin"] = "market_anomaly"
    source["_source_origin"] = "official_exchange"
    value = attribution.assess_mapping_attribution(market, source)
    source["catalyst_attribution"] = deepcopy(value)
    source["catalyst_attributions"] = [deepcopy(value)]
    source["score_components"] = {"catalyst_attributions": [deepcopy(value)]}

    candidate = _build_integrated(market, source)

    assert candidate["catalyst_attribution"] == value
    assert candidate["catalyst_attributions"] == [value]
    assert isinstance(candidate["catalyst_attribution"], dict)


def test_integrated_rejects_valid_contract_that_no_longer_binds_source():
    import crypto_rsi_scanner.event_alpha.radar.catalyst_attribution as attribution

    market, source = _integrated_rows(
        published_at=(NOW - timedelta(minutes=30)).isoformat(),
        role="direct_beneficiary",
        impact_strength="strong",
    )
    value = attribution.assess_mapping_attribution(market, source)
    source["catalyst_attribution"] = deepcopy(value)
    source["title"] = "A different article replaced the bound source"

    candidate = _build_integrated(market, source)

    assert "catalyst_attribution" not in candidate
    assert "catalyst_attributions" not in candidate
    assert candidate["catalyst_attribution_rejected"] is True
    assert candidate["catalyst_attribution_rejection_reasons"] == [
        "catalyst_attribution_mapping_binding_mismatch"
    ]
    assert candidate["catalyst_status"] == "unknown"
    assert candidate["radar_route"] != "high_confidence_watch"
    assert any(
        "closed contract" in warning for warning in candidate["decision_warnings"]
    )


def test_integrated_rejects_ambiguous_mix_of_bound_and_foreign_attributions():
    import crypto_rsi_scanner.event_alpha.radar.catalyst_attribution as attribution

    market, source = _integrated_rows(
        published_at=(NOW - timedelta(minutes=30)).isoformat(),
        role="direct_beneficiary",
        impact_strength="strong",
    )
    bound = attribution.assess_mapping_attribution(market, source)
    foreign_market = {**market, "market_anomaly_id": "foreign-anomaly"}
    foreign = attribution.assess_mapping_attribution(foreign_market, source)
    source["catalyst_attributions"] = [deepcopy(bound), deepcopy(foreign)]

    candidate = _build_integrated(market, source)

    assert "catalyst_attribution" not in candidate
    assert "catalyst_attributions" not in candidate
    assert candidate["catalyst_attribution_rejected"] is True
    assert candidate["catalyst_status"] == "unknown"
    assert candidate["radar_route"] != "high_confidence_watch"
