"""Canonical market-feature evidence projection regressions."""

from __future__ import annotations

from copy import deepcopy

import pytest

from crypto_rsi_scanner.event_alpha.artifacts import schema_v1
from crypto_rsi_scanner.event_alpha.radar import market_anomaly_scanner, market_state


def _temporal_evidence() -> dict[str, object]:
    return {
        "basis": "temporal_baseline",
        "status": "ready",
        "calculation": "price_horizon_return",
        "sample_count": 1,
        "current_observation_id": "mhobs-current",
        "baseline_first_observation_id": "mhobs-anchor",
        "baseline_last_observation_id": "mhobs-endpoint",
        "baseline_input_observation_count": 2,
        "baseline_observation_ids_sha256": "a" * 64,
        "providers": ["coingecko"],
        "data_modes": ["live"],
        "research_only": True,
    }


def _market_row() -> dict[str, object]:
    return {
        "symbol": "TRACE",
        "coin_id": "trace-token",
        "canonical_asset_id": "trace-token",
        "observed_at": "2026-07-19T09:00:00Z",
        "return_unit": "percent_points",
        "return_4h": 12.0,
        "return_24h": 18.0,
        "relative_return_vs_btc_4h": 8.0,
        "volume_zscore_24h": 3.0,
        "liquidity_usd": 50_000_000.0,
        "freshness_status": "fresh",
        "market_history_observation_id": "mhobs-current",
        "market_feature_evidence": {
            "liquidity_usd": {
                "basis": "provider_observed",
                "provider": "coingecko",
            },
            "temporal_return_4h": _temporal_evidence(),
        },
    }


def test_feature_evidence_survives_snapshot_and_anomaly_projection():
    source = _market_row()
    expected = deepcopy(source["market_feature_evidence"])

    snapshots, anomalies = market_anomaly_scanner.scan_market_rows([source])

    assert len(snapshots) == 1
    assert len(anomalies) == 1
    assert snapshots[0]["market_history_observation_id"] == "mhobs-current"
    assert snapshots[0]["market_feature_evidence_contract_version"] == 1
    assert snapshots[0]["market_feature_evidence"] == expected
    assert anomalies[0]["market_state_snapshot"]["market_feature_evidence"] == expected
    assert schema_v1.validate_row_against_schema(
        snapshots[0], "market_state_snapshot_v1"
    ) == []
    assert schema_v1.validate_row_against_schema(
        anomalies[0], "market_anomaly_v1"
    ) == []


def test_temporal_snapshot_identity_survives_canonical_decision_and_outcome(tmp_path):
    from crypto_rsi_scanner.event_alpha.artifacts.schema.decision_model import (
        validate_contract as validate_decision_contract,
    )
    from crypto_rsi_scanner.event_alpha.outcomes.integrated_radar_outcomes import (
        write_integrated_radar_outcome_placeholders,
    )
    from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import (
        decision_model_values,
    )
    from crypto_rsi_scanner.event_alpha.radar.integrated_radar import (
        build_integrated_candidates,
    )

    _snapshots, anomalies = market_anomaly_scanner.scan_market_rows([_market_row()])
    candidate = build_integrated_candidates(
        sidecar_rows={"market_anomaly": anomalies},
        profile="fixture",
        artifact_namespace="temporal-evidence-chain",
        run_mode="fixture",
        run_id="temporal-evidence-chain-run",
        observed_at="2026-07-19T09:00:00Z",
    )[0]
    projection = decision_model_values(candidate)

    assert candidate["market_snapshot"]["market_feature_evidence"] == (
        _market_row()["market_feature_evidence"]
    )
    assert projection["market_context_reference"]["market_snapshot_id"] == (
        "mhobs-current"
    )
    assert "mhobs-current" in projection["observation_ids"]

    tampered = deepcopy(projection)
    tampered["observation_ids"].remove("mhobs-current")
    assert "decision_projection_market_snapshot_observation_id_missing" in (
        validate_decision_contract(tampered)
    )

    historical = deepcopy(projection)
    historical.pop("market_observation_identity_bound")
    historical["observation_ids"].remove("mhobs-current")
    assert validate_decision_contract(historical) == []
    assert decision_model_values(historical) == historical

    outcomes = write_integrated_radar_outcome_placeholders(
        tmp_path,
        [candidate],
        observed_at="2026-07-19T09:01:00Z",
    )
    assert outcomes[0]["decision_projection"] == projection
    assert "mhobs-current" in outcomes[0]["observation_ids"]


def test_feature_evidence_projection_is_detached_from_mutable_input():
    source = _market_row()
    snapshot = market_state.snapshot_from_market_row(source)
    source["market_feature_evidence"]["temporal_return_4h"]["providers"].append(
        "mutated"
    )

    first = snapshot.to_dict()
    assert first["market_feature_evidence"]["temporal_return_4h"]["providers"] == [
        "coingecko"
    ]
    first["market_feature_evidence"]["temporal_return_4h"]["providers"].append(
        "also-mutated"
    )
    assert snapshot.to_dict()["market_feature_evidence"]["temporal_return_4h"][
        "providers"
    ] == ["coingecko"]


def test_feature_evidence_rejects_current_observation_drift_before_projection():
    source = _market_row()
    source["market_feature_evidence"]["temporal_return_4h"][
        "current_observation_id"
    ] = "mhobs-other"

    with pytest.raises(ValueError, match="current_observation_id_mismatch"):
        market_state.snapshot_from_market_row(source)


def test_schema_rejects_temporal_evidence_digest_drift_after_projection():
    snapshots, _ = market_anomaly_scanner.scan_market_rows([_market_row()])
    snapshots[0]["market_feature_evidence"]["temporal_return_4h"][
        "baseline_observation_ids_sha256"
    ] = "not-a-digest"

    errors = schema_v1.validate_row_against_schema(
        snapshots[0], "market_state_snapshot_v1"
    )

    assert errors == [
        "market_feature_evidence_invalid:temporal_return_4h:baseline_digest"
    ]


@pytest.mark.parametrize(
    "missing_field,error",
    (
        (
            "market_feature_evidence",
            "missing_for_history_observation",
        ),
        (
            "market_history_observation_id",
            "market_history_observation_id_missing",
        ),
    ),
)
def test_history_observation_and_temporal_evidence_are_one_closed_pair(
    missing_field,
    error,
):
    source = _market_row()
    source.pop(missing_field)

    with pytest.raises(ValueError, match=error):
        market_state.snapshot_from_market_row(source)


def test_schema_blocks_a_writer_that_drops_history_feature_evidence():
    snapshots, _ = market_anomaly_scanner.scan_market_rows([_market_row()])
    snapshots[0].pop("market_feature_evidence")

    assert schema_v1.validate_row_against_schema(
        snapshots[0], "market_state_snapshot_v1"
    ) == [
        "market_feature_evidence_invalid:value:missing_for_history_observation"
    ]


def test_pre_contract_history_snapshot_remains_readable():
    historical = market_state.snapshot_from_market_row({
        **_market_row(),
        "market_history_observation_id": None,
        "market_feature_evidence": {},
    }).to_dict()
    historical["row_type"] = "event_market_state_snapshot"
    historical["market_history_observation_id"] = "legacy-history-id"

    assert "market_feature_evidence_contract_version" not in historical
    assert schema_v1.validate_row_against_schema(
        historical, "market_state_snapshot_v1"
    ) == []


@pytest.mark.parametrize(
    "mutation,error",
    (
        (
            lambda row: row["market_feature_evidence"]["temporal_return_4h"].update(
                {"sample_count": 3}
            ),
            "sample_count",
        ),
        (
            lambda row: row["market_feature_evidence"]["temporal_return_4h"].update(
                {"calculation": "return_zscore_4h"}
            ),
            "calculation",
        ),
        (
            lambda row: row["market_feature_evidence"].update(
                {"liquidity_usd": {"basis": "provider_observed", "value": float("inf")}}
            ),
            "finite_number",
        ),
    ),
)
def test_feature_evidence_rejects_invalid_counts_semantics_and_json(
    mutation,
    error,
):
    source = _market_row()
    mutation(source)

    with pytest.raises(ValueError, match=error):
        market_state.snapshot_from_market_row(source)
