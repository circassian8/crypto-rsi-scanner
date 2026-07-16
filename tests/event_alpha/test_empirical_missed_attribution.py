"""Point-in-time missed-opportunity attribution regressions."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.operations import empirical_missed_attribution


def test_closed_attribution_uses_trace_without_future_outcome() -> None:
    result = empirical_missed_attribution.classify_missed_attribution(
        {
            "failure_stage": None,
            "radar_route": "diagnostic",
            "hard_blockers": ["spread unavailable", "liquidity below minimum"],
            "warnings": ["catalyst unknown"],
            "actionability_score": 38.0,
            "risk_score": 82.0,
            "spread_status": "unavailable",
            "catalyst_status": "unknown",
            "rsi_context_present": False,
        },
        {
            "point_in_time_universe_member": True,
            "baseline_status": "warm",
            "data_quality_mode": "cross_sectional_proxy",
        },
    )

    assert result["primary_reason"] == "liquidity_gate"
    assert result["reason_codes"] == [
        "liquidity_gate",
        "spread_unavailable",
        "proxy_only_data_cap",
        "actionability_below_threshold",
        "risk_too_high",
        "missing_technical_context",
        "catalyst_uncertainty",
    ]
    assert result["uses_future_outcome"] is False
    assert result["causal_claim"] is False
    assert result["auto_apply"] is False


def test_stage_mapping_and_closed_zero_counts_are_explicit() -> None:
    rows = [
        empirical_missed_attribution.classify_missed_attribution(
            {"failure_stage": "no_anomaly_generated"},
            {"point_in_time_universe_member": True, "baseline_status": "warm"},
        ),
        empirical_missed_attribution.classify_missed_attribution(
            {"failure_stage": "canonical_projection_invalid"},
            {"point_in_time_universe_member": True, "baseline_status": "warm"},
        ),
    ]
    counts = empirical_missed_attribution.closed_reason_counts(rows)
    by_reason = {row["reason"]: row for row in counts}

    assert [row["reason"] for row in counts] == list(
        empirical_missed_attribution.REASON_TAXONOMY
    )
    assert by_reason["no_anomaly_generated"]["primary_count"] == 1
    assert by_reason["feature_bug"]["primary_count"] == 1
    assert by_reason["duplicate_suppression"]["sample_status"] == "zero_sample"
    assert by_reason["outcome_outside_supported_horizon"]["contributing_count"] == 0


def test_projection_unit_failure_is_explicit_feature_contract_concern() -> None:
    result = empirical_missed_attribution.classify_missed_attribution(
        {
            "failure_stage": "canonical_projection_invalid",
            "projection_validation_error_codes": [
                "return_fraction_implausible",
                "not_a_closed_code:secret-value",
            ],
            "projection_validation_concern_class": (
                "data_quality_feature_contract"
            ),
        },
        {
            "point_in_time_universe_member": True,
            "baseline_status": "warm",
        },
    )

    assert result["primary_reason"] == "feature_bug"
    assert result["projection_validation_error_codes"] == [
        "return_fraction_implausible"
    ]
    assert result["diagnostic_concern_class"] == (
        "data_quality_feature_contract"
    )
    assert any(
        row == {
            "reason": "feature_bug",
            "source": "projection_validation_error_code",
            "value": "return_fraction_implausible",
        }
        for row in result["reason_evidence"]
    )
