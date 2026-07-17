"""Bybit USDT-perpetual offline execution-quality contract regressions."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import socket
import subprocess

import pytest

from crypto_rsi_scanner.event_alpha.operations.bybit_execution_quality import (
    CONTRACT_VERSION,
    MAX_PLANNED_REQUESTS,
    BybitExecutionQualityError,
    build_bybit_public_request_plan,
    main,
    normalize_bybit_orderbook,
    run_fixture_smoke,
    select_bybit_usdt_perpetual_instruments,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "fixtures/bybit_execution_quality"


def _json(name: str) -> object:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _selected() -> tuple[object, ...]:
    return select_bybit_usdt_perpetual_instruments(
        _json("radar_assets.json"),
        _json("instruments_info.json"),
    )


def test_universe_intersection_accepts_only_exact_active_usdt_perpetuals() -> None:
    selected = _selected()

    assert [row.instrument_id for row in selected] == ["BTCUSDT", "ETHUSDT"]
    assert [row.canonical_asset_id for row in selected] == ["bitcoin", "ethereum"]
    assert [row.liquidity_rank for row in selected] == [1, 2]
    assert all(row.contract_type == "LinearPerpetual" for row in selected)
    assert all(row.status == "Trading" for row in selected)
    assert all(row.quote_asset == row.settle_asset == "USDT" for row in selected)


def test_universe_intersection_never_guesses_multiplier_or_partial_pages() -> None:
    radar = _json("radar_assets.json")
    payload = _json("instruments_info.json")
    selected = select_bybit_usdt_perpetual_instruments(radar, payload)

    assert "1000PEPEUSDT" not in {row.instrument_id for row in selected}
    partial = deepcopy(payload)
    partial["result"]["nextPageCursor"] = "next"
    with pytest.raises(BybitExecutionQualityError, match="page_incomplete"):
        select_bybit_usdt_perpetual_instruments(radar, partial)


@pytest.mark.parametrize(
    ("mutation", "error"),
    (
        (lambda rows: rows + [dict(rows[0])], "identity_not_unique"),
        (lambda rows: rows * 8, "exceeds_30"),
        (
            lambda rows: [dict(rows[0], liquidity_rank=31), *rows[1:]],
            "rank_exceeds_30",
        ),
    ),
)
def test_universe_identity_and_bound_fail_closed(mutation: object, error: str) -> None:
    radar = _json("radar_assets.json")
    with pytest.raises(BybitExecutionQualityError, match=error):
        select_bybit_usdt_perpetual_instruments(
            mutation(radar),
            _json("instruments_info.json"),
        )


def test_request_plan_is_bounded_public_get_only_and_non_executable() -> None:
    plan = build_bybit_public_request_plan(_selected())
    payload = plan.to_dict()

    assert payload["contract_version"] == CONTRACT_VERSION
    assert payload["venue_id"] == "bybit"
    assert payload["execution_mode"] == "perpetual"
    assert payload["quote_asset"] == "USDT"
    assert payload["request_count"] == 4
    assert payload["request_count"] <= MAX_PLANNED_REQUESTS
    assert {row["method"] for row in payload["requests"]} == {"GET"}
    assert {row["path"] for row in payload["requests"]} == {
        "/v5/market/instruments-info",
        "/v5/market/orderbook",
    }
    assert all(row["credentials_required"] is False for row in payload["requests"])
    assert all(row["private_data"] is False for row in payload["requests"])
    assert payload["provider_call_authorized"] is False
    assert payload["provider_call_planned"] is False
    assert payload["provider_call_attempted"] is False
    assert payload["order_operations_available"] is False
    assert payload["research_only"] is True


def test_orderbook_normalizes_quote_units_freshness_lineage_and_sequences() -> None:
    instrument = _selected()[0]
    snapshot = normalize_bybit_orderbook(
        _json("orderbook_btcusdt.json"),
        instrument=instrument,
        acquired_at="2026-07-17T12:00:01Z",
        request_lineage_id="test.bybit.btcusdt.1",
    )
    payload = snapshot.to_dict()

    assert payload["venue_id"] == "bybit"
    assert payload["execution_mode"] == "perpetual"
    assert payload["instrument_id"] == "BTCUSDT"
    assert payload["canonical_asset_id"] == "bitcoin"
    assert payload["quote_asset"] == payload["notional_currency"] == "USDT"
    assert payload["provider_observed_at"] == "2026-07-17T12:00:00Z"
    assert payload["snapshot_generated_at"] == "2026-07-17T12:00:00.100000Z"
    assert payload["acquired_at"] == "2026-07-17T12:00:01Z"
    assert payload["age_seconds"] == 1.0
    assert payload["freshness_status"] == "fresh"
    assert payload["best_bid"] == 100.0
    assert payload["best_ask"] == 100.1
    assert payload["mid_price"] == 100.05
    assert payload["spread_bps"] == pytest.approx(9.995002498751)
    assert payload["bid_depth_usdt_by_band"] == {
        5: 1_000.0,
        10: 2_999.0,
        25: 7_994.0,
        50: 7_994.0,
    }
    assert payload["ask_depth_usdt_by_band"] == {
        5: 1_001.0,
        10: 3_004.0,
        25: 8_014.0,
        50: 18_064.0,
    }
    assert payload["buy_price_impact_bps_by_notional_usdt"][500.0] is not None
    assert payload["sell_price_impact_bps_by_notional_usdt"][500.0] is not None
    assert payload["buy_price_impact_bps_by_notional_usdt"][10_000.0] is not None
    assert payload["impact_reference"] == "mid_price"
    assert payload["order_book_update_id"] == 230704
    assert payload["order_book_cross_sequence"] == 1432604333
    assert payload["request_lineage_id"] == "test.bybit.btcusdt.1"
    assert payload["research_only"] is True


def test_insufficient_book_depth_is_explicit_not_extrapolated() -> None:
    instrument = _selected()[0]
    snapshot = normalize_bybit_orderbook(
        _json("orderbook_btcusdt.json"),
        instrument=instrument,
        acquired_at="2026-07-17T12:00:01Z",
        request_lineage_id="test.bybit.btcusdt.depth",
        notionals_usdt=(100_000.0,),
    )

    assert snapshot.buy_price_impact_bps_by_notional_usdt == ((100_000.0, None),)
    assert snapshot.sell_price_impact_bps_by_notional_usdt == ((100_000.0, None),)


def test_stale_snapshot_stays_stale_without_weakening_freshness_gate() -> None:
    instrument = _selected()[0]
    snapshot = normalize_bybit_orderbook(
        _json("orderbook_btcusdt.json"),
        instrument=instrument,
        acquired_at="2026-07-17T12:01:00Z",
        request_lineage_id="test.bybit.btcusdt.stale",
    )

    assert snapshot.age_seconds == 60.0
    assert snapshot.freshness_status == "stale"


@pytest.mark.parametrize(
    ("mutation", "error"),
    (
        (lambda row: row["result"].update(s="ETHUSDT"), "instrument_mismatch"),
        (lambda row: row["result"]["b"].__setitem__(0, ["100.20", "10"]), "locked_or_crossed"),
        (lambda row: row["result"]["a"].reverse(), "asks_sort_invalid"),
        (lambda row: row.update(retCode=10001), "response_not_ok"),
        (lambda row: row.update(retCode=False), "response_not_ok"),
        (
            lambda row: row["result"].update(ts=row["result"]["cts"] - 1),
            "snapshot_clock_precedes",
        ),
    ),
)
def test_invalid_orderbook_identity_shape_and_status_fail_closed(
    mutation: object,
    error: str,
) -> None:
    payload = _json("orderbook_btcusdt.json")
    mutation(payload)
    with pytest.raises(BybitExecutionQualityError, match=error):
        normalize_bybit_orderbook(
            payload,
            instrument=_selected()[0],
            acquired_at="2026-07-17T12:00:01Z",
            request_lineage_id="test.bybit.invalid",
        )


def test_fixture_smoke_and_cli_are_offline_secret_free(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def forbidden_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("offline Bybit fixture smoke must not open a connection")

    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    monkeypatch.setenv("BYBIT_API_KEY", "must-not-print")
    monkeypatch.setenv("BYBIT_API_SECRET", "must-not-print")

    result = run_fixture_smoke(FIXTURE_DIR)
    assert result["provider_calls"] == 0
    assert result["network_called"] is False
    assert result["credentials_read"] is False
    assert result["orders_available"] is False
    assert result["research_only"] is True

    assert main(["--fixture-dir", str(FIXTURE_DIR)]) == 0
    output = capsys.readouterr()
    payload = json.loads(output.out)
    assert output.err == ""
    assert payload["selected_instrument_ids"] == ["BTCUSDT", "ETHUSDT"]
    assert payload["provider_calls"] == 0
    assert "must-not-print" not in output.out


def test_make_smoke_exposes_fixture_normalizer_not_provider_or_order_command() -> None:
    completed = subprocess.run(
        ["make", "-n", "radar-execution-quality-bybit-smoke", "PYTHON=python3"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "operations.bybit_execution_quality" in completed.stdout
    assert "--fixture-dir fixtures/bybit_execution_quality" in completed.stdout
    lowered = completed.stdout.casefold()
    assert "curl" not in lowered
    assert "place-order" not in lowered
    assert "execute-order" not in lowered
