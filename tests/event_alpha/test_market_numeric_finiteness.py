"""Non-finite numeric evidence must remain unavailable across Radar layers."""

from __future__ import annotations

import json
from dataclasses import asdict


def test_nonfinite_values_cannot_create_market_confirmation():
    from crypto_rsi_scanner.event_alpha.radar import market_confirmation

    now = "2026-06-15T16:00:00Z"
    result = market_confirmation.evaluate_market_confirmation(
        {
            "market": {
                "return_24h": float("inf"),
                "volume_zscore_24h": float("inf"),
                "volume_to_market_cap": float("inf"),
            },
            "derivatives": {
                "derivatives_crowding": float("inf"),
                "open_interest_24h_change_pct": float("inf"),
                "funding_rate_8h": float("inf"),
            },
            "playbook_type": "listing_liquidity_event",
            "now": now,
            "market_context_observed_at": now,
            "market_context_max_age_hours": float("inf"),
        }
    )

    assert result.level == "none"
    assert result.market_confirmation_score == 0.0
    assert result.data_quality == 0.0
    assert result.score_components == {}
    assert "insufficient_data" in result.reasons
    json.dumps(asdict(result), allow_nan=False)


def test_nonfinite_values_cannot_create_reaction_or_derivatives_crowding():
    from crypto_rsi_scanner.event_alpha.radar import derivatives_crowding
    from crypto_rsi_scanner.event_alpha.radar import market_reaction

    now = "2026-06-15T16:00:00Z"
    reaction = market_reaction.evaluate_market_reaction(
        {
            "source_class": "broad_news",
            "source_pack": "market_anomaly_pack",
            "impact_path_type": "market_dislocation_unknown",
            "market_snapshot": {
                "return_24h": float("inf"),
                "return_4h": float("inf"),
                "relative_return_vs_btc": float("inf"),
                "volume_zscore_24h": float("inf"),
                "liquidity_usd": float("inf"),
            },
        }
    )
    reaction_snapshot = reaction.market_state_snapshot.to_dict()

    assert reaction.market_state == "no_reaction"
    assert "volume_turnover_zscore" not in reaction_snapshot
    assert "liquidity_usd" not in reaction_snapshot
    assert reaction_snapshot["observed_fields"] == 0

    state = derivatives_crowding.normalize_derivatives_state(
        {
            "symbol": "INFUSDT_PERP",
            "coin_id": "inf",
            "observed_at": now,
            "freshness_status": "fresh",
            "open_interest": float("inf"),
            "open_interest_delta_24h": float("inf"),
            "funding_rate": float("inf"),
            "funding_zscore": float("inf"),
            "liquidation_imbalance": float("inf"),
            "perp_spot_volume_ratio": float("inf"),
        },
        observed_at=now,
    )

    for field in (
        "open_interest",
        "open_interest_delta_24h",
        "funding_rate",
        "funding_zscore",
        "liquidation_imbalance",
        "perp_spot_volume_ratio",
    ):
        assert state[field] is None
    assert derivatives_crowding._crowding_evidence(state) == ()
    assert state["raw_payload_redacted"]["open_interest"] == "<non_finite>"
    json.dumps(state, allow_nan=False)


def test_nonfinite_or_shadowed_zero_universe_values_cannot_derive_liquidity(tmp_path):
    from crypto_rsi_scanner.event_alpha.radar import asset_registry

    path = tmp_path / "universe.json"
    path.write_text(
        """{"rows":[
            {"id":"infinite","symbol":"INF","total_volume":1e309},
            {"id":"zero","symbol":"ZERO","market_cap_rank":0,"rank":1,
             "total_volume":0,"volume_usd":100000000}
        ]}""",
        encoding="utf-8",
    )

    assets = {asset.coin_id: asset for asset in asset_registry.assets_from_coingecko_universe(path)}

    assert assets["infinite"].liquidity_tier is None
    assert assets["zero"].liquidity_tier is None
