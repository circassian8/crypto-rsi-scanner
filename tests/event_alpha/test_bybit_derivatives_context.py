"""Venue-native Bybit derivatives-context contract regressions."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import socket

import pytest

from crypto_rsi_scanner.event_alpha.operations.bybit_derivatives_context import (
    MAX_PLANNED_REQUESTS,
    BybitDerivativesContextError,
    build_bybit_derivatives_request_plan,
    main,
    normalize_bybit_derivatives_context,
    run_fixture_smoke,
)
from crypto_rsi_scanner.event_alpha.operations.bybit_execution_quality import (
    select_bybit_usdt_perpetual_instruments,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "fixtures/bybit_derivatives_context"
QUALITY_DIR = REPO_ROOT / "fixtures/bybit_execution_quality"
NAMES = ("ticker", "funding_history", "open_interest", "account_ratio")


def _json(directory: Path, name: str) -> object:
    return json.loads((directory / name).read_text(encoding="utf-8"))


def _instrument() -> object:
    selected = select_bybit_usdt_perpetual_instruments(
        _json(QUALITY_DIR, "radar_assets.json"),
        _json(QUALITY_DIR, "instruments_info.json"),
    )
    return next(row for row in selected if row.instrument_id == "BTCUSDT")


def _payloads() -> dict[str, object]:
    return {
        name: _json(FIXTURE_DIR, f"{name}_btcusdt.json")
        for name in NAMES
    }


def _snapshot(**overrides: object) -> object:
    payloads = _payloads()
    values = {
        "instrument": _instrument(),
        "acquired_at": "2026-07-18T07:44:01Z",
        "request_lineage_ids": {
            name: f"test.bybit.derivatives.{name}" for name in NAMES
        },
    }
    values.update(overrides)
    return normalize_bybit_derivatives_context(
        payloads["ticker"],
        payloads["funding_history"],
        payloads["open_interest"],
        payloads["account_ratio"],
        **values,
    )


def test_request_plan_is_bounded_public_get_only_and_non_executable() -> None:
    selected = select_bybit_usdt_perpetual_instruments(
        _json(QUALITY_DIR, "radar_assets.json"),
        _json(QUALITY_DIR, "instruments_info.json"),
    )

    plan = build_bybit_derivatives_request_plan(selected)

    assert plan["venue_id"] == "bybit"
    assert plan["execution_mode"] == "perpetual"
    assert plan["category"] == "linear"
    assert plan["quote_asset"] == "USDT"
    assert plan["request_count"] == 8
    assert plan["request_count"] <= MAX_PLANNED_REQUESTS == 120
    assert {row["path"] for row in plan["requests"]} == {
        "/v5/market/tickers",
        "/v5/market/funding/history",
        "/v5/market/open-interest",
        "/v5/market/account-ratio",
    }
    assert all(row["method"] == "GET" for row in plan["requests"])
    assert all(row["credentials_required"] is False for row in plan["requests"])
    assert all(row["private_data"] is False for row in plan["requests"])
    assert plan["provider_call_authorized"] is False
    assert plan["provider_call_planned"] is False
    assert plan["provider_call_attempted"] is False
    assert plan["orders_available"] is False


def test_snapshot_preserves_native_identity_units_clocks_and_point_in_time_values() -> None:
    value = _snapshot().to_dict()

    assert value["schema_version"] == "crypto_radar.bybit_derivatives_context.v2"
    assert value["instrument_id"] == "BTCUSDT"
    assert value["canonical_asset_id"] == "bitcoin"
    assert value["quote_asset"] == value["settle_asset"] == "USDT"
    assert value["provider_observed_at"] == "2026-07-18T07:44:00Z"
    assert value["provider_latest_response_at"] == "2026-07-18T07:44:00Z"
    assert value["provider_response_span_seconds"] == 0.0
    assert value["provider_observed_at_policy"] == "oldest_component_response"
    assert value["provider_response_times"] == {
        name: "2026-07-18T07:44:00Z" for name in NAMES
    }
    assert value["acquired_at"] == "2026-07-18T07:44:01Z"
    assert value["age_seconds"] == 1.0
    assert value["freshness_status"] == "fresh"
    assert value["mark_price_usdt"] == 120000.0
    assert value["index_price_usdt"] == 119980.0
    assert value["mark_index_basis_bps"] == pytest.approx(1.66694449)
    assert value["return_24h_percent_points"] == 2.5
    assert value["current_funding_rate_fraction"] == 0.0001
    assert value["current_funding_rate_percent_points"] == 0.01
    assert value["latest_settled_funding_rate_fraction"] == 0.00008
    assert value["prior_settled_funding_rate_fraction"] == 0.00012
    assert value["latest_settled_funding_at"] == "2026-07-18T00:00:00Z"
    assert value["open_interest_base_asset"] == 5000.0
    assert value["open_interest_usdt"] == 600000000.0
    assert value["open_interest_change_1h_percent_points"] == pytest.approx(
        4.166666667
    )
    assert value["long_account_ratio_fraction"] == 0.55
    assert value["short_account_ratio_fraction"] == 0.45
    assert value["long_short_account_ratio"] == pytest.approx(1.222222222)
    assert value["units"]["funding_rates"].startswith("fraction")
    assert value["units"]["open_interest_value"] == "USDT"
    assert set(value["source_urls"]) == set(NAMES)
    assert set(value["request_lineage_ids"]) == set(NAMES)
    assert value["future_data_used"] is False
    assert value["context_only"] is True
    assert value["directional_authority"] is False
    assert value["decision_policy_applied"] is False
    assert value["protocol_v2_annex_bound"] is False
    assert value["protocol_v2_evidence_eligible"] is False
    assert value["research_only"] is True
    assert "radar_route" not in value
    assert "directional_bias" not in value


def test_stale_context_remains_stale_without_weakening_freshness() -> None:
    value = _snapshot(acquired_at="2026-07-18T07:45:00Z").to_dict()

    assert value["age_seconds"] == 60.0
    assert value["freshness_status"] == "stale"


def test_composite_freshness_uses_oldest_provider_response() -> None:
    payloads = _payloads()
    funding = deepcopy(payloads["funding_history"])
    funding["time"] = 1784360580000
    payloads["funding_history"] = funding

    value = normalize_bybit_derivatives_context(
        payloads["ticker"],
        payloads["funding_history"],
        payloads["open_interest"],
        payloads["account_ratio"],
        instrument=_instrument(),
        acquired_at="2026-07-18T07:44:01Z",
        request_lineage_ids={
            name: f"test.bybit.derivatives.{name}" for name in NAMES
        },
    ).to_dict()

    assert value["provider_observed_at"] == "2026-07-18T07:43:00Z"
    assert value["provider_latest_response_at"] == "2026-07-18T07:44:00Z"
    assert value["provider_response_span_seconds"] == 60.0
    assert value["provider_response_times"]["funding_history"] == (
        "2026-07-18T07:43:00Z"
    )
    assert value["age_seconds"] == 61.0
    assert value["freshness_status"] == "stale"


@pytest.mark.parametrize(
    ("name", "mutation", "error"),
    (
        ("ticker", lambda row: row.update(retCode=True), "ticker_response_not_ok"),
        (
            "ticker",
            lambda row: row["result"]["list"][0].update(symbol="ETHUSDT"),
            "ticker_identity_mismatch",
        ),
        (
            "ticker",
            lambda row: row["result"]["list"][0].update(fundingRate="10"),
            "current_funding_implausible",
        ),
        (
            "ticker",
            lambda row: row["result"]["list"][0].update(price24hPcnt="10.0"),
            "return_24h_implausible",
        ),
        (
            "funding_history",
            lambda row: row["result"]["list"].reverse(),
            "funding_time_order_invalid",
        ),
        (
            "open_interest",
            lambda row: row["result"]["list"][1].update(openInterest="0"),
            "open_interest_prior_zero",
        ),
        (
            "account_ratio",
            lambda row: row["result"]["list"][0].update(buyRatio="0.8"),
            "account_ratio_sum_invalid",
        ),
        (
            "account_ratio",
            lambda row: row["result"]["list"][0].update(timestamp="1784360641000"),
            "account_ratio_future_row",
        ),
    ),
)
def test_malformed_derivatives_payloads_fail_closed(
    name: str,
    mutation: object,
    error: str,
) -> None:
    payloads = _payloads()
    changed = deepcopy(payloads[name])
    mutation(changed)
    payloads[name] = changed

    with pytest.raises(BybitDerivativesContextError, match=error):
        normalize_bybit_derivatives_context(
            payloads["ticker"],
            payloads["funding_history"],
            payloads["open_interest"],
            payloads["account_ratio"],
            instrument=_instrument(),
            acquired_at="2026-07-18T07:44:01Z",
            request_lineage_ids={
                source: f"test.bybit.derivatives.{source}" for source in NAMES
            },
        )


def test_lineage_is_closed_and_fixture_smoke_never_uses_network_or_side_effects(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(BybitDerivativesContextError, match="lineage"):
        _snapshot(request_lineage_ids={"ticker": "incomplete"})
    monkeypatch.setattr(
        socket,
        "create_connection",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("network must remain unused")
        ),
    )

    result = run_fixture_smoke(FIXTURE_DIR)
    assert result["provider_calls"] == 0
    assert result["writes"] == 0
    assert result["orders"] == 0
    assert result["trades"] == 0
    assert result["paper_trades"] == 0
    assert result["telegram_sends"] == 0
    assert result["normal_rsi_writes"] == 0
    assert result["event_alpha_triggered_fade"] == 0
    assert result["protocol_v2_evidence_eligible"] is False
    assert main(["--fixture-dir", str(FIXTURE_DIR)]) == 0
    rendered = json.loads(capsys.readouterr().out)
    assert rendered["mode"] == "offline_fixture"
    assert rendered["provider_calls"] == 0
