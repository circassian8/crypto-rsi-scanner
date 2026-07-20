"""Decision-price latency decomposition for modeled Bybit round trips."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import socket

import pytest

from crypto_rsi_scanner.event_alpha.operations.bybit_execution_latency import (
    OFFICIAL_ORDERBOOK_URL,
    SCHEMA_VERSION,
    BybitDecisionBookReferenceInput,
    BybitExecutionLatencyError,
    model_bybit_decision_price_latency_scenario,
)
from crypto_rsi_scanner.event_alpha.operations.bybit_execution_quality import (
    model_bybit_visible_book_round_trip,
    select_bybit_usdt_perpetual_instruments,
)


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures/bybit_execution_quality"


def _json(name: str) -> object:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _round_trip(position_side: str = "long") -> object:
    instrument = select_bybit_usdt_perpetual_instruments(
        _json("radar_assets.json"),
        _json("instruments_info.json"),
    )[0]
    return model_bybit_visible_book_round_trip(
        _json("orderbook_btcusdt.json"),
        _json("orderbook_btcusdt_exit.json"),
        instrument=instrument,
        exit_instrument=instrument,
        position_side=position_side,
        base_quantity="15.000",
        entry_acquired_at="2026-07-17T12:00:01Z",
        exit_acquired_at="2026-07-17T13:00:01Z",
        entry_request_lineage_id=f"test.latency.{position_side}.execution.entry",
        exit_request_lineage_id=f"test.latency.{position_side}.execution.exit",
        entry_instrument_constraints_observed_at="2026-07-17T11:59:59Z",
        entry_instrument_constraints_lineage_id=(
            f"test.latency.{position_side}.catalog.entry"
        ),
        exit_instrument_constraints_observed_at="2026-07-17T12:59:59Z",
        exit_instrument_constraints_lineage_id=(
            f"test.latency.{position_side}.catalog.exit"
        ),
    )


def _entry_reference(position_side: str = "long", **changes: object) -> object:
    values: dict[str, object] = {
        "instrument_id": "BTCUSDT",
        "best_bid": "99.80",
        "best_ask": "99.90",
        "provider_observed_at": "2026-07-17T11:59:59Z",
        "acquired_at": "2026-07-17T11:59:59.100Z",
        "decision_at": "2026-07-17T11:59:59.200Z",
        "source_reference": OFFICIAL_ORDERBOOK_URL,
        "request_lineage_id": f"test.latency.{position_side}.reference.entry",
    }
    values.update(changes)
    return BybitDecisionBookReferenceInput(**values)


def _exit_reference(position_side: str = "long", **changes: object) -> object:
    values: dict[str, object] = {
        "instrument_id": "BTCUSDT",
        "best_bid": "110.20",
        "best_ask": "110.30",
        "provider_observed_at": "2026-07-17T12:59:59Z",
        "acquired_at": "2026-07-17T12:59:59.100Z",
        "decision_at": "2026-07-17T12:59:59.200Z",
        "source_reference": OFFICIAL_ORDERBOOK_URL,
        "request_lineage_id": f"test.latency.{position_side}.reference.exit",
    }
    values.update(changes)
    return BybitDecisionBookReferenceInput(**values)


def _scenario(position_side: str = "long") -> object:
    return model_bybit_decision_price_latency_scenario(
        _round_trip(position_side),
        entry_reference=_entry_reference(position_side),
        exit_reference=_exit_reference(position_side),
    )


@pytest.mark.parametrize(
    (
        "position_side",
        "reference_gross",
        "execution_gross",
        "entry_cost",
        "exit_cost",
        "total_cost",
        "net_visible",
    ),
    (
        ("long", 156.0, 150.0, 3.0, 3.0, 6.0, 147.75),
        ("short", -156.0, -150.0, -3.0, -3.0, -6.0, -152.25),
    ),
)
def test_latency_cost_decomposes_decision_and_execution_midpoints(
    position_side: str,
    reference_gross: float,
    execution_gross: float,
    entry_cost: float,
    exit_cost: float,
    total_cost: float,
    net_visible: float,
) -> None:
    result = _scenario(position_side).to_dict()

    assert result["schema_version"] == SCHEMA_VERSION
    assert result["source_round_trip_schema_version"].endswith("round_trip.v3")
    assert result["venue_id"] == "bybit"
    assert result["execution_mode"] == "perpetual"
    assert result["instrument_id"] == "BTCUSDT"
    assert result["position_side"] == position_side
    assert result["base_quantity"] == "15"
    assert result["entry_decision_mid_price_usdt"] == "99.85"
    assert result["entry_execution_mid_price_usdt"] == "100.05"
    assert result["exit_decision_mid_price_usdt"] == "110.25"
    assert result["exit_execution_mid_price_usdt"] == "110.05"
    assert result["entry_reference_mid_notional_usdt"] == 1497.75
    assert result["decision_reference_gross_return_usdt"] == reference_gross
    assert result["execution_book_gross_mid_mark_return_usdt"] == execution_gross
    assert result["entry_latency_cost_usdt"] == entry_cost
    assert result["exit_latency_cost_usdt"] == exit_cost
    assert result["total_latency_cost_usdt"] == total_cost
    assert result["total_latency_cashflow_usdt"] == -total_cost
    assert result["total_visible_book_cost_usdt"] == 2.25
    assert result["net_visible_book_return_usdt"] == net_visible
    assert result[
        "net_from_decision_reference_after_latency_and_visible_book_usdt"
    ] == net_visible
    assert result["decision_reference_to_execution_mid_identity_reconciled"] is True
    assert result["decision_reference_to_visible_book_identity_reconciled"] is True
    assert result["latency_cost_sign_convention"] == (
        "positive_adverse_negative_favorable_relative_to_decision_mid"
    )
    assert result["cost_benchmark"] == "decision_book_mid_price"
    assert result["arithmetic_exact_for_supplied_inputs"] is True
    assert result["actual_order_submission_observed"] is False
    assert result["actual_fill_observed"] is False
    assert result["realized_execution_latency_observed"] is False
    assert result["decision_reference_sources_sealed"] is False
    assert result["latency_cost_policy_sealed"] is False
    assert result["fees_included"] is False
    assert result["funding_included"] is False
    assert result["spread_added_separately"] is False
    assert result["beyond_visible_book_slippage_included"] is False
    assert result["unavailable_cost_policy_sealed"] is False
    assert result["protocol_v2_annex_bound"] is False
    assert result["protocol_v2_evidence_eligible"] is False
    assert result["realized_execution"] is False
    assert result["provider_calls"] == 0
    assert result["credentials_read"] is False
    assert result["private_data_read"] is False
    assert result["writes_performed"] is False
    assert result["research_only"] is True
    json.dumps(result, allow_nan=False)


def test_latency_reference_clocks_retain_provider_and_local_boundaries() -> None:
    result = _scenario().to_dict()
    entry = result["entry_reference_projection"]
    exit_value = result["exit_reference_projection"]

    assert entry["mid_price"] == "99.85"
    assert entry["market_drift_window_microseconds"] == 1_000_000
    assert entry["decision_to_execution_book_observation_microseconds"] == 800_000
    assert entry["decision_to_execution_book_acquisition_microseconds"] == 1_800_000
    assert exit_value["mid_price"] == "110.25"
    assert exit_value["market_drift_window_microseconds"] == 1_000_000
    assert exit_value["decision_to_execution_book_observation_microseconds"] == 800_000
    assert exit_value["decision_to_execution_book_acquisition_microseconds"] == 1_800_000
    assert entry["source_status"] == "operator_supplied_unsealed_decision_book"
    assert entry["matching_engine_timestamp_basis"] is True
    assert entry["source_sealed"] is False


@pytest.mark.parametrize(
    ("role", "changes", "error"),
    (
        ("entry", {"best_bid": 99.8}, "must_be_decimal_text"),
        ("entry", {"best_bid": "NaN"}, "best_bid_invalid"),
        ("entry", {"best_ask": "0"}, "best_ask_invalid"),
        ("entry", {"best_bid": "100", "best_ask": "100"}, "book_crossed"),
        ("entry", {"instrument_id": "ETHUSDT"}, "instrument_mismatch"),
        ("entry", {"provider_observed_at": "2026-07-17T11:59:59"}, "timezone_missing"),
        (
            "entry",
            {"acquired_at": "2026-07-17T11:59:58Z"},
            "reference_timeline_invalid",
        ),
        (
            "entry",
            {"decision_at": "2026-07-17T12:00:00Z"},
            "decision_not_before_execution_book",
        ),
        (
            "exit",
            {
                "provider_observed_at": "2026-07-17T12:00:00.500Z",
                "acquired_at": "2026-07-17T12:00:01Z",
                "decision_at": "2026-07-17T12:00:01.100Z",
            },
            "not_after_modeled_position_open",
        ),
        (
            "entry",
            {"source_reference": "https://example.com/?token=secret"},
            "source_reference_invalid",
        ),
        ("entry", {"request_lineage_id": "bad lineage"}, "lineage_id_invalid"),
    ),
)
def test_reference_units_identity_time_and_lineage_fail_closed(
    role: str,
    changes: dict[str, object],
    error: str,
) -> None:
    entry = _entry_reference(**changes) if role == "entry" else _entry_reference()
    exit_value = _exit_reference(**changes) if role == "exit" else _exit_reference()

    with pytest.raises(BybitExecutionLatencyError, match=error):
        model_bybit_decision_price_latency_scenario(
            _round_trip(),
            entry_reference=entry,
            exit_reference=exit_value,
        )


def test_reference_and_execution_lineages_cannot_be_reused() -> None:
    round_trip = _round_trip()
    with pytest.raises(BybitExecutionLatencyError, match="reuses_execution_lineage"):
        model_bybit_decision_price_latency_scenario(
            round_trip,
            entry_reference=_entry_reference(
                request_lineage_id=round_trip.entry.request_lineage_id
            ),
            exit_reference=_exit_reference(),
        )
    with pytest.raises(BybitExecutionLatencyError, match="lineages_not_distinct"):
        model_bybit_decision_price_latency_scenario(
            round_trip,
            entry_reference=_entry_reference(request_lineage_id="same.reference"),
            exit_reference=_exit_reference(request_lineage_id="same.reference"),
        )
    with pytest.raises(
        BybitExecutionLatencyError,
        match="reference_and_execution_lineages_not_distinct",
    ):
        model_bybit_decision_price_latency_scenario(
            round_trip,
            entry_reference=_entry_reference(
                request_lineage_id=round_trip.exit.request_lineage_id
            ),
            exit_reference=_exit_reference(),
        )


@pytest.mark.parametrize(
    "changes",
    (
        {"latency_cost_included": True},
        {"realized_execution": True},
        {"fees_included": True},
        {"funding_included": True},
        {"research_only": False},
    ),
)
def test_round_trip_contract_drift_fails_closed(changes: dict[str, object]) -> None:
    with pytest.raises(BybitExecutionLatencyError, match="round_trip_contract_invalid"):
        model_bybit_decision_price_latency_scenario(
            replace(_round_trip(), **changes),
            entry_reference=_entry_reference(),
            exit_reference=_exit_reference(),
        )


def test_latency_projection_performs_no_network_or_file_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    round_trip = _round_trip()
    entry = _entry_reference()
    exit_value = _exit_reference()

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("latency projection must remain pure")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)

    result = model_bybit_decision_price_latency_scenario(
        round_trip,
        entry_reference=entry,
        exit_reference=exit_value,
    )
    assert result.provider_calls == 0
    assert result.writes_performed is False
