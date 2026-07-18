"""Offline Bybit direct 1h/4h bar contract regressions."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.operations.bybit_execution_quality import (
    select_bybit_usdt_perpetual_instruments,
)
from crypto_rsi_scanner.event_alpha.operations.bybit_intraday import (
    BAR_SCHEMA_VERSION,
    INTERVAL_SECONDS,
    KLINE_PATH,
    BybitIntradayError,
    build_bybit_kline_request,
    completed_kline_cutoff_ms,
    normalize_bybit_completed_kline,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
EXECUTION_FIXTURES = REPO_ROOT / "fixtures" / "bybit_execution_quality"
INTRADAY_FIXTURES = REPO_ROOT / "fixtures" / "bybit_intraday"
STARTED = datetime(2026, 7, 17, 12, 30, tzinfo=timezone.utc)
ACQUIRED = STARTED + timedelta(milliseconds=125)


def _json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _instrument():
    radar = _json(EXECUTION_FIXTURES / "radar_assets.json")
    payload = _json(EXECUTION_FIXTURES / "instruments_info.json")
    selected = select_bybit_usdt_perpetual_instruments(radar, payload)
    return next(row for row in selected if row.instrument_id == "BTCUSDT")


def _payload(interval: str) -> dict[str, object]:
    value = _json(INTRADAY_FIXTURES / f"klines_btcusdt_{interval}.json")
    assert isinstance(value, dict)
    return value


def _normalize(interval: str, payload: dict[str, object] | None = None):
    instrument = _instrument()
    request = build_bybit_kline_request(
        instrument,
        interval=interval,
        as_of=STARTED,
    )
    return normalize_bybit_completed_kline(
        payload or _payload(interval),
        instrument=instrument,
        request=request,
        request_started_at=STARTED,
        acquired_at=ACQUIRED,
        request_lineage_id=f"test.bybit.kline.{interval}",
    )


def test_request_uses_exact_latest_completed_bucket_and_public_contract() -> None:
    instrument = _instrument()

    one_hour = build_bybit_kline_request(
        instrument,
        interval="60",
        as_of=STARTED,
    )
    four_hour = build_bybit_kline_request(
        instrument,
        interval="240",
        as_of=STARTED,
    )

    assert one_hour.method == four_hour.method == "GET"
    assert one_hour.path == four_hour.path == KLINE_PATH
    assert one_hour.credentials_required is False
    assert one_hour.private_data is False
    assert one_hour.research_only is True
    assert dict(one_hour.query) == {
        "category": "linear",
        "symbol": "BTCUSDT",
        "interval": "60",
        "end": "1784289599999",
        "limit": "2",
    }
    assert dict(four_hour.query)["end"] == "1784289599999"
    assert completed_kline_cutoff_ms("2026-07-17T12:00:00Z", "60") == (
        1784289599999
    )


@pytest.mark.parametrize(
    ("interval", "label", "start", "end", "open_price", "turnover"),
    (
        ("60", "1h", "2026-07-17T11:00:00Z", "2026-07-17T12:00:00Z", 120000.0, 15182250.0),
        ("240", "4h", "2026-07-17T08:00:00Z", "2026-07-17T12:00:00Z", 118500.0, 61245000.0),
    ),
)
def test_normalizer_preserves_native_identity_units_and_latency(
    interval: str,
    label: str,
    start: str,
    end: str,
    open_price: float,
    turnover: float,
) -> None:
    bar = _normalize(interval)

    assert bar.schema_version == BAR_SCHEMA_VERSION
    assert bar.venue_id == "bybit"
    assert bar.execution_mode == "perpetual"
    assert bar.category == "linear"
    assert bar.instrument_id == "BTCUSDT"
    assert bar.canonical_asset_id == "bitcoin"
    assert bar.base_asset == bar.volume_unit == "BTC"
    assert bar.quote_asset == bar.settle_asset == bar.turnover_unit == "USDT"
    assert bar.contract_type == "LinearPerpetual"
    assert bar.instrument_status == "Trading"
    assert bar.interval == label
    assert bar.interval_seconds == INTERVAL_SECONDS[interval]
    assert bar.bar_start_at == start
    assert bar.bar_end_at == end
    assert bar.requested_end_at == end
    assert bar.observation_latency_seconds == 1800.125
    assert bar.freshness_status == "fresh"
    assert bar.open_price == open_price
    assert bar.close_price == 121000.0
    assert bar.price_unit == "USDT_per_base_asset"
    assert bar.turnover_usdt == turnover
    assert bar.bar_closed is True
    assert bar.point_in_time_status == "captured_after_close"
    assert bar.future_data_used is False
    assert bar.research_only is True
    assert "api.bybit.com/v5/market/kline" in bar.source_url


def test_open_or_wrong_bucket_candle_cannot_replace_completed_bar() -> None:
    payload = _payload("60")
    payload["result"]["list"] = [
        ["1784289600000", "121000", "122000", "120500", "121500", "10", "1215000"]
    ]

    with pytest.raises(BybitIntradayError, match="latest_completed_kline_missing"):
        _normalize("60", payload)


def test_latest_completed_bar_must_exist_even_when_older_rows_are_valid() -> None:
    payload = _payload("60")
    payload["result"]["list"] = payload["result"]["list"][1:]

    with pytest.raises(BybitIntradayError, match="latest_completed_kline_missing"):
        _normalize("60", payload)


def test_response_identity_and_reverse_sort_are_exact() -> None:
    wrong = _payload("60")
    wrong["result"]["symbol"] = "ETHUSDT"
    with pytest.raises(BybitIntradayError, match="identity_mismatch"):
        _normalize("60", wrong)

    unsorted = _payload("60")
    unsorted["result"]["list"].reverse()
    with pytest.raises(BybitIntradayError, match="sort_invalid"):
        _normalize("60", unsorted)


@pytest.mark.parametrize(
    ("index", "value", "reason"),
    (
        (1, "0", "open_invalid"),
        (2, "119000", "ohlc_invalid"),
        (3, "122000", "ohlc_invalid"),
        (5, "-1", "volume_invalid"),
        (6, "NaN", "turnover_invalid"),
    ),
)
def test_ohlcv_and_turnover_values_fail_closed(
    index: int,
    value: str,
    reason: str,
) -> None:
    payload = _payload("60")
    payload["result"]["list"][0][index] = value

    with pytest.raises(BybitIntradayError, match=reason):
        _normalize("60", payload)


def test_request_cutoff_interval_and_transport_contract_fail_closed() -> None:
    instrument = _instrument()
    with pytest.raises(BybitIntradayError, match="interval_unsupported"):
        build_bybit_kline_request(instrument, interval="120", as_of=STARTED)

    request = build_bybit_kline_request(
        instrument,
        interval="60",
        as_of=STARTED,
    )
    drifted = deepcopy(request)
    object.__setattr__(
        drifted,
        "query",
        tuple(
            (key, "1784289599000" if key == "end" else value)
            for key, value in request.query
        ),
    )
    with pytest.raises(BybitIntradayError, match="cutoff_unaligned"):
        normalize_bybit_completed_kline(
            _payload("60"),
            instrument=instrument,
            request=drifted,
            request_started_at=STARTED,
            acquired_at=ACQUIRED,
            request_lineage_id="test.bybit.kline.60",
        )


def test_response_and_provider_clocks_cannot_claim_future_evidence() -> None:
    with pytest.raises(BybitIntradayError, match="response_clock_invalid"):
        normalize_bybit_completed_kline(
            _payload("60"),
            instrument=_instrument(),
            request=build_bybit_kline_request(
                _instrument(), interval="60", as_of=STARTED
            ),
            request_started_at=STARTED,
            acquired_at=STARTED - timedelta(milliseconds=1),
            request_lineage_id="test.bybit.kline.60",
        )

    future = _payload("60")
    future["time"] = int((ACQUIRED + timedelta(minutes=2)).timestamp() * 1000)
    with pytest.raises(BybitIntradayError, match="provider_clock_future"):
        _normalize("60", future)


def test_stale_completed_bar_is_explicit_not_reinterpreted() -> None:
    instrument = _instrument()
    request = build_bybit_kline_request(
        instrument,
        interval="60",
        as_of=STARTED,
    )
    bar = normalize_bybit_completed_kline(
        _payload("60"),
        instrument=instrument,
        request=request,
        request_started_at=STARTED,
        acquired_at=STARTED + timedelta(hours=2),
        request_lineage_id="test.bybit.kline.stale",
    )

    assert bar.freshness_status == "stale"
    assert bar.observation_latency_seconds == 9000.0
    assert bar.bar_closed is True
    assert bar.future_data_used is False
