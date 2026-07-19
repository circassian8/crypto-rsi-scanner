"""Strict numeric contracts for immutable Bybit capture freshness evidence."""

from __future__ import annotations

from copy import deepcopy

from crypto_rsi_scanner.event_alpha.operations.bybit_derivatives_context_set_freshness import (
    MAXIMUM_CONTEXT_AGE_SECONDS,
    SET_FRESHNESS_POLICY,
    freshness_contract_valid as derivatives_freshness_contract_valid,
)
from crypto_rsi_scanner.event_alpha.operations.bybit_execution_quality_set_freshness import (
    FRESHNESS_POLICY as EXECUTION_FRESHNESS_POLICY,
    MAXIMUM_AGE_SECONDS,
    observation_freshness_contract_valid,
)
from crypto_rsi_scanner.event_alpha.operations.bybit_intraday_set_freshness import (
    BAR_RECENCY_POLICY,
    FRESHNESS_POLICY as INTRADAY_FRESHNESS_POLICY,
    MAXIMUM_PROVIDER_AGE_SECONDS,
    freshness_contract_valid as intraday_freshness_contract_valid,
)


def test_execution_freshness_rejects_non_finite_age() -> None:
    values: dict[str, object] = {
        "all_fresh": False,
        "all_fresh_at_acquisition": True,
        "all_fresh_at_completion": False,
        "freshness_policy": EXECUTION_FRESHNESS_POLICY,
        "maximum_age_at_completion_seconds": 20.0,
        "maximum_age_policy_seconds": MAXIMUM_AGE_SECONDS,
    }

    assert observation_freshness_contract_valid(values)
    for invalid in (float("inf"), float("-inf"), float("nan")):
        changed = deepcopy(values)
        changed["maximum_age_at_completion_seconds"] = invalid
        assert not observation_freshness_contract_valid(changed)


def test_intraday_freshness_rejects_non_finite_age_and_recency() -> None:
    values: dict[str, object] = {
        "all_bars_fresh": False,
        "all_bars_fresh_at_acquisition": True,
        "all_bars_fresh_at_completion": False,
        "intraday_set_freshness_policy": INTRADAY_FRESHNESS_POLICY,
        "maximum_provider_response_age_at_completion_seconds": 20.0,
        "maximum_provider_response_age_policy_seconds": MAXIMUM_PROVIDER_AGE_SECONDS,
        "minimum_bar_recency_remaining_at_completion_seconds": -1.0,
        "bar_recency_policy": BAR_RECENCY_POLICY,
        "protocol_v2_input_quality_eligible": False,
    }

    assert intraday_freshness_contract_valid(values)
    for field in (
        "maximum_provider_response_age_at_completion_seconds",
        "minimum_bar_recency_remaining_at_completion_seconds",
    ):
        for invalid in (float("inf"), float("-inf"), float("nan")):
            changed = deepcopy(values)
            changed[field] = invalid
            assert not intraday_freshness_contract_valid(changed)


def test_derivatives_freshness_rejects_non_finite_age() -> None:
    values: dict[str, object] = {
        "all_context_fresh": False,
        "all_context_fresh_at_acquisition": True,
        "all_context_fresh_at_completion": False,
        "derivatives_set_freshness_policy": SET_FRESHNESS_POLICY,
        "maximum_context_age_at_completion_seconds": 20.0,
        "maximum_context_age_policy_seconds": MAXIMUM_CONTEXT_AGE_SECONDS,
        "protocol_v2_input_quality_eligible": False,
    }

    assert derivatives_freshness_contract_valid(values)
    for invalid in (float("inf"), float("-inf"), float("nan")):
        changed = deepcopy(values)
        changed["maximum_context_age_at_completion_seconds"] = invalid
        assert not derivatives_freshness_contract_valid(changed)
