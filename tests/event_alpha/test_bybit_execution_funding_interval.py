"""Holding-interval funding-set reconciliation for modeled Bybit positions."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import socket

import pytest

from crypto_rsi_scanner.event_alpha.operations.bybit_execution_funding import (
    INTERVAL_SCHEMA_VERSION,
    MAX_INTERVAL_SETTLEMENTS,
    OFFICIAL_FUNDING_HISTORY_URL,
    OFFICIAL_INSTRUMENT_INFO_URL,
    OFFICIAL_MARK_PRICE_KLINE_URL,
    BybitExecutionFundingError,
    BybitFundingSettlementInput,
    model_bybit_funding_interval_scenario,
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
        entry_request_lineage_id=f"test.funding.interval.{position_side}.entry",
        exit_request_lineage_id=f"test.funding.interval.{position_side}.exit",
        entry_instrument_constraints_observed_at="2026-07-17T11:59:59Z",
        entry_instrument_constraints_lineage_id="test.funding.interval.catalog.entry",
        exit_instrument_constraints_observed_at="2026-07-17T12:59:59Z",
        exit_instrument_constraints_lineage_id="test.funding.interval.catalog.exit",
    )


def _settlement(
    settled_at: str,
    *,
    rate: str,
    mark: str,
    suffix: str,
) -> BybitFundingSettlementInput:
    return BybitFundingSettlementInput(
        funding_rate_fraction=rate,
        settlement_mark_price_usdt=mark,
        funding_settled_at=settled_at,
        assumption_id=f"fixture-settlement-{suffix}",
        funding_rate_source_reference=OFFICIAL_FUNDING_HISTORY_URL,
        funding_rate_source_observed_at="2026-07-17T13:05:00Z",
        funding_rate_lineage_id=f"fixture.bybit.funding.{suffix}",
        settlement_mark_source_reference=OFFICIAL_MARK_PRICE_KLINE_URL,
        settlement_mark_source_observed_at="2026-07-17T13:05:01Z",
        settlement_mark_lineage_id=f"fixture.bybit.mark.{suffix}",
    )


def _interval(
    position_side: str = "long",
    *,
    source: object | None = None,
    **changes: object,
) -> object:
    times = (
        "2026-07-17T12:20:00Z",
        "2026-07-17T12:40:00Z",
    )
    kwargs: dict[str, object] = {
        "settlements": (
            _settlement(times[0], rate="0.0001", mark="105", suffix="one"),
            _settlement(times[1], rate="-0.0002", mark="106", suffix="two"),
        ),
        "expected_funding_settlement_times": times,
        "funding_schedule_assumption_id": "fixture-funding-schedule",
        "funding_schedule_source_reference": OFFICIAL_INSTRUMENT_INFO_URL,
        "funding_schedule_source_observed_at": "2026-07-17T11:50:00Z",
        "funding_schedule_effective_from": "2026-07-17T11:00:00Z",
        "funding_schedule_effective_until": "2026-07-17T14:00:00Z",
        "funding_schedule_lineage_id": "fixture.bybit.schedule.20260717",
    }
    kwargs.update(changes)
    return model_bybit_funding_interval_scenario(
        source if source is not None else _round_trip(position_side),
        **kwargs,
    )


def test_interval_reconciles_exact_set_and_signed_cashflows() -> None:
    result = _interval().to_dict()

    assert result["schema_version"] == INTERVAL_SCHEMA_VERSION
    assert result["source_settlement_schema_version"].endswith(".v1")
    assert result["venue_id"] == "bybit"
    assert result["execution_mode"] == "perpetual"
    assert result["instrument_id"] == "BTCUSDT"
    assert result["position_side"] == "long"
    assert result["base_quantity"] == "15"
    assert result["expected_funding_settlement_times"] == (
        "2026-07-17T12:20:00Z",
        "2026-07-17T12:40:00Z",
    )
    assert result["supplied_funding_settlement_times"] == (
        result["expected_funding_settlement_times"]
    )
    assert result["expected_funding_settlement_count"] == 2
    assert result["funding_event_count"] == 2
    assert result["expected_settlement_set_reconciled"] is True
    assert result["funding_settlement_order_strict"] is True
    assert len(result["settlements"]) == 2
    assert result["total_unsigned_funding_transfer_usdt"] == pytest.approx(0.4755)
    assert result["total_position_funding_cashflow_usdt"] == pytest.approx(0.1605)
    assert result["total_position_funding_cost_usdt"] == pytest.approx(-0.1605)
    assert result["net_after_visible_book_and_funding_usdt"] == pytest.approx(147.9105)
    assert result["total_visible_book_and_funding_cost_usdt"] == pytest.approx(
        result["gross_mid_mark_return_usdt"]
        - result["net_after_visible_book_and_funding_usdt"]
    )
    assert result["arithmetic_exact_for_supplied_inputs"] is True
    assert result["operator_supplied_schedule_coverage_complete"] is True
    assert result["coverage_scope"] == (
        "operator_supplied_unsealed_expected_settlement_schedule"
    )
    assert result["holding_interval_funding_coverage_complete"] is False
    assert result["funding_schedule_source_sealed"] is False
    assert result["funding_rate_sources_sealed"] is False
    assert result["settlement_mark_sources_sealed"] is False
    assert result["fees_included"] is False
    assert result["latency_cost_included"] is False
    assert result["beyond_visible_book_slippage_included"] is False
    assert result["protocol_v2_annex_bound"] is False
    assert result["protocol_v2_evidence_eligible"] is False
    assert result["provider_calls"] == 0
    assert result["writes_performed"] is False
    json.dumps(result, allow_nan=False)


def test_short_interval_reverses_the_aggregate_position_cashflow() -> None:
    long = _interval("long").to_dict()
    short = _interval("short").to_dict()

    assert short["total_position_funding_cashflow_usdt"] == pytest.approx(
        -long["total_position_funding_cashflow_usdt"]
    )
    assert short["total_position_funding_cost_usdt"] == pytest.approx(
        -long["total_position_funding_cost_usdt"]
    )
    assert short["net_after_visible_book_and_funding_usdt"] == pytest.approx(
        short["net_visible_book_return_usdt"]
        + short["total_position_funding_cashflow_usdt"]
    )


def test_empty_expected_schedule_is_an_exact_zero_transfer_scenario() -> None:
    result = _interval(
        settlements=(),
        expected_funding_settlement_times=(),
    ).to_dict()

    assert result["funding_event_count"] == 0
    assert result["expected_funding_settlement_count"] == 0
    assert result["expected_settlement_set_reconciled"] is True
    assert result["total_unsigned_funding_transfer_usdt"] == 0.0
    assert result["total_position_funding_cashflow_usdt"] == 0.0
    assert result["net_after_visible_book_and_funding_usdt"] == (
        result["net_visible_book_return_usdt"]
    )
    assert result["holding_interval_funding_coverage_complete"] is False


@pytest.mark.parametrize(
    ("changes", "error"),
    (
        (
            {"expected_funding_settlement_times": ("2026-07-17T12:20:00Z",)},
            "funding_settlement_set_mismatch",
        ),
        (
            {
                "expected_funding_settlement_times": (
                    "2026-07-17T12:40:00Z",
                    "2026-07-17T12:20:00Z",
                ),
            },
            "not_strictly_increasing",
        ),
        (
            {
                "expected_funding_settlement_times": (
                    "2026-07-17T12:00:01Z",
                    "2026-07-17T12:40:00Z",
                ),
            },
            "outside_modeled_holding_interval",
        ),
        ({"settlements": "not-a-sequence"}, "settlements_must_be_sequence"),
        (
            {"expected_funding_settlement_times": "not-a-sequence"},
            "must_be_sequence",
        ),
        (
            {"settlements": ({"funding_settled_at": "2026-07-17T12:20:00Z"},)},
            "settlement_input_type_invalid",
        ),
    ),
)
def test_set_identity_and_order_fail_closed(
    changes: dict[str, object],
    error: str,
) -> None:
    with pytest.raises(BybitExecutionFundingError, match=error):
        _interval(**changes)


@pytest.mark.parametrize(
    ("changes", "error"),
    (
        (
            {"funding_schedule_source_observed_at": "2026-07-17T12:00:02Z"},
            "observed_after_position_open",
        ),
        (
            {"funding_schedule_effective_from": "2026-07-17T12:00:02Z"},
            "effective_window_incomplete",
        ),
        (
            {"funding_schedule_effective_until": "2026-07-17T13:00:00Z"},
            "effective_window_incomplete",
        ),
        (
            {"funding_schedule_source_reference": "https://example.com/schedule"},
            "source_reference_invalid",
        ),
        (
            {"funding_schedule_assumption_id": "bad assumption"},
            "assumption_id_invalid",
        ),
        (
            {"funding_schedule_lineage_id": "bad lineage"},
            "lineage_id_invalid",
        ),
    ),
)
def test_schedule_source_and_effective_window_fail_closed(
    changes: dict[str, object],
    error: str,
) -> None:
    with pytest.raises(BybitExecutionFundingError, match=error):
        _interval(**changes)


@pytest.mark.parametrize(
    ("duplicate_field", "error"),
    (
        ("assumption_id", "duplicate_assumption_id"),
        ("funding_rate_lineage_id", "duplicate_funding_rate_lineage_id"),
        ("settlement_mark_lineage_id", "duplicate_settlement_mark_lineage_id"),
    ),
)
def test_duplicate_event_identity_fails_closed(
    duplicate_field: str,
    error: str,
) -> None:
    first = _settlement(
        "2026-07-17T12:20:00Z",
        rate="0.0001",
        mark="105",
        suffix="one",
    )
    second = _settlement(
        "2026-07-17T12:40:00Z",
        rate="-0.0002",
        mark="106",
        suffix="two",
    )
    second = replace(second, **{duplicate_field: getattr(first, duplicate_field)})

    with pytest.raises(BybitExecutionFundingError, match=error):
        _interval(settlements=(first, second))


def test_interval_input_bound_fails_before_parsing() -> None:
    oversized = tuple("invalid" for _ in range(MAX_INTERVAL_SETTLEMENTS + 1))

    with pytest.raises(BybitExecutionFundingError, match="too_many"):
        _interval(expected_funding_settlement_times=oversized)
    with pytest.raises(BybitExecutionFundingError, match="settlements_too_many"):
        _interval(settlements=oversized)


def test_interval_projection_performs_no_network_or_file_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _round_trip()

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("funding interval projection must remain pure")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)

    result = _interval(source=source)

    assert result.provider_calls == 0
    assert result.credentials_read is False
    assert result.private_data_read is False
    assert result.writes_performed is False
    assert result.research_only is True


def test_tampered_source_round_trip_fails_closed() -> None:
    source = replace(_round_trip(), funding_included=True)

    with pytest.raises(BybitExecutionFundingError, match="round_trip_contract_invalid"):
        model_bybit_funding_interval_scenario(
            source,
            settlements=(),
            expected_funding_settlement_times=(),
            funding_schedule_assumption_id="fixture-funding-schedule",
            funding_schedule_source_reference="research-assumption:funding-schedule",
            funding_schedule_source_observed_at="2026-07-17T11:50:00Z",
            funding_schedule_effective_from="2026-07-17T11:00:00Z",
            funding_schedule_effective_until="2026-07-17T14:00:00Z",
            funding_schedule_lineage_id="fixture.bybit.schedule.20260717",
        )
