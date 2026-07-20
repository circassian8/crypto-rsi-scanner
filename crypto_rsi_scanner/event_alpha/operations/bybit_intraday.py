"""Offline direct 1h/4h Bybit USDT-perpetual bar contract.

The intended Decision Radar execution surface is Bybit USDT-linear
perpetuals.  This module normalizes already-supplied public V5 trade-price
klines for the exact native instrument selected by the execution-quality
contract.  It contains no HTTP client, authorization mutation, persistence,
notification, order, or trading path.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping, Sequence
from urllib.parse import urlencode

import pandas as pd

from ...indicators import wilder_rsi

from .bybit_execution_quality import (
    BYBIT_CATEGORY,
    PUBLIC_API_BASE,
    QUOTE_ASSET,
    BybitEligibleInstrument,
    BybitExecutionQualityError,
    BybitPublicRequest,
    bybit_eligible_instrument_from_values,
    select_bybit_usdt_perpetual_instruments,
)


CONTRACT_VERSION = "crypto_radar_bybit_intraday_v3"
BAR_SCHEMA_VERSION = "crypto_radar.bybit_intraday_bar.v3"
KLINE_PATH = "/v5/market/kline"
OFFICIAL_KLINE_DOC = "https://bybit-exchange.github.io/docs/v5/market/kline"
INTERVAL_SECONDS = {"60": 60 * 60, "240": 4 * 60 * 60}
INTERVAL_LABELS = {"60": "1h", "240": "4h"}
KLINE_LIMIT = 200
RSI_PERIOD = 14
RSI_METHOD = "wilder_rma_sma_seed"
MAX_PROVIDER_CLOCK_SKEW_SECONDS = 60
MAX_PROVIDER_RESPONSE_AGE_SECONDS = 15.0
_LINEAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class _BybitIntradayError(ValueError):
    """Raised when an offline kline violates the closed contract."""


@dataclass(frozen=True)
class _BybitIntradayBar:
    """One exact latest-completed trade-price bar for a native contract."""

    schema_version: str
    venue_id: str
    execution_mode: str
    category: str
    instrument_id: str
    canonical_asset_id: str
    base_asset: str
    quote_asset: str
    settle_asset: str
    contract_type: str
    instrument_status: str
    interval: str
    interval_seconds: int
    bar_start_at: str
    bar_end_at: str
    requested_end_at: str
    request_started_at: str
    response_acquired_at: str
    provider_response_generated_at: str
    provider_response_age_seconds: float
    provider_response_freshness_status: str
    observation_latency_seconds: float
    bar_close_recency_status: str
    freshness_policy: str
    freshness_status: str
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    price_unit: str
    volume_base_asset: float
    volume_unit: str
    turnover_usdt: float
    turnover_unit: str
    bar_closed: bool
    point_in_time_status: str
    future_data_used: bool
    rsi_status: str
    rsi_timeframe: str
    rsi_period: int
    wilder_rsi: float | None
    wilder_rsi_unit: str
    rsi_method: str
    rsi_candle_close_time: str
    rsi_available_at: str
    rsi_source_bar_count: int
    rsi_source_lineage_id: str
    rsi_future_data_used: bool
    source_url: str
    request_lineage_id: str
    research_only: bool = True

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


# Stable public names expose one closed model/error bundle without declaring
# multiple public ownership classes in this behavior module.
BybitIntradayError = _BybitIntradayError
BybitIntradayBar = _BybitIntradayBar
_ParsedKline = tuple[int, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal]


def _aware_utc(value: datetime | str, field: str) -> datetime:
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise BybitIntradayError(f"{field}_invalid") from exc
    elif isinstance(value, datetime):
        parsed = value
    else:
        raise BybitIntradayError(f"{field}_invalid")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BybitIntradayError(f"{field}_timezone_missing")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _decimal(value: object, field: str, *, allow_zero: bool = False) -> Decimal:
    if isinstance(value, bool):
        raise BybitIntradayError(f"{field}_invalid")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise BybitIntradayError(f"{field}_invalid") from exc
    if not parsed.is_finite() or parsed < 0 or (not allow_zero and parsed == 0):
        raise BybitIntradayError(f"{field}_invalid")
    return parsed


def _integer(value: object, field: str) -> int:
    if isinstance(value, bool):
        raise BybitIntradayError(f"{field}_invalid")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise BybitIntradayError(f"{field}_invalid") from exc
    if str(value).strip() != str(parsed) and not isinstance(value, int):
        raise BybitIntradayError(f"{field}_invalid")
    return parsed


def _valid_instrument(instrument: BybitEligibleInstrument) -> None:
    if type(instrument) is not BybitEligibleInstrument:
        raise BybitIntradayError("eligible_instrument_contract_invalid")
    try:
        bybit_eligible_instrument_from_values(instrument.to_dict())
    except BybitExecutionQualityError as exc:
        raise BybitIntradayError("eligible_instrument_contract_invalid") from exc


def completed_kline_cutoff_ms(as_of: datetime | str, interval: str) -> int:
    """Return the final millisecond before the current interval bucket."""

    if interval not in INTERVAL_SECONDS:
        raise BybitIntradayError("kline_interval_unsupported")
    observed = _aware_utc(as_of, "as_of")
    interval_ms = INTERVAL_SECONDS[interval] * 1000
    current_bucket_start = int(observed.timestamp() * 1000) // interval_ms * interval_ms
    if current_bucket_start <= 0:
        raise BybitIntradayError("kline_cutoff_invalid")
    return current_bucket_start - 1


def build_bybit_kline_request(
    instrument: BybitEligibleInstrument,
    *,
    interval: str,
    as_of: datetime | str,
) -> BybitPublicRequest:
    """Build one public GET for the exact latest completed interval."""

    _valid_instrument(instrument)
    end_ms = completed_kline_cutoff_ms(as_of, interval)
    return BybitPublicRequest(
        method="GET",
        path=KLINE_PATH,
        query=(
            ("category", BYBIT_CATEGORY),
            ("symbol", instrument.instrument_id),
            ("interval", interval),
            ("end", str(end_ms)),
            ("limit", str(KLINE_LIMIT)),
        ),
    )


def _request_url(request: BybitPublicRequest) -> str:
    return f"{PUBLIC_API_BASE}{request.path}?{urlencode(request.query)}"


def _validated_request(
    request: BybitPublicRequest,
    instrument: BybitEligibleInstrument,
) -> tuple[str, int]:
    _valid_instrument(instrument)
    query = dict(request.query)
    if (
        request.method != "GET"
        or request.path != KLINE_PATH
        or request.credentials_required
        or request.private_data
        or not request.research_only
        or set(query) != {"category", "symbol", "interval", "end", "limit"}
        or query.get("category") != BYBIT_CATEGORY
        or query.get("symbol") != instrument.instrument_id
        or query.get("interval") not in INTERVAL_SECONDS
        or query.get("limit") != str(KLINE_LIMIT)
    ):
        raise BybitIntradayError("kline_request_contract_invalid")
    interval = str(query["interval"])
    end_ms = _integer(query.get("end"), "kline_request_end")
    interval_ms = INTERVAL_SECONDS[interval] * 1000
    if end_ms <= 0 or (end_ms + 1) % interval_ms != 0:
        raise BybitIntradayError("kline_request_cutoff_unaligned")
    return interval, end_ms


def _wilder_rsi_value(rows: Sequence[_ParsedKline]) -> tuple[str, float | None]:
    """Compute latest Wilder RSI from only the closed rows in this response."""

    if len(rows) < RSI_PERIOD + 1:
        return "insufficient_history", None
    closes = pd.Series(
        [float(row[4]) for row in reversed(rows)],
        dtype="float64",
    )
    value = float(wilder_rsi(closes, period=RSI_PERIOD).iloc[-1])
    if not math.isfinite(value) or not 0.0 <= value <= 100.0:
        raise BybitIntradayError("wilder_rsi_invalid")
    return "observed", value


def normalize_bybit_completed_kline(
    payload: Mapping[str, Any],
    *,
    instrument: BybitEligibleInstrument,
    request: BybitPublicRequest,
    request_started_at: datetime | str,
    acquired_at: datetime | str,
    request_lineage_id: str,
) -> BybitIntradayBar:
    """Normalize the exact latest completed trade-price candle."""

    interval, requested_end_ms = _validated_request(request, instrument)
    started = _aware_utc(request_started_at, "request_started_at")
    acquired = _aware_utc(acquired_at, "acquired_at")
    if acquired < started:
        raise BybitIntradayError("kline_response_clock_invalid")
    if not _LINEAGE_RE.fullmatch(request_lineage_id):
        raise BybitIntradayError("request_lineage_id_invalid")
    if isinstance(payload.get("retCode"), bool) or payload.get("retCode") != 0:
        raise BybitIntradayError("bybit_kline_response_not_ok")
    result = payload.get("result")
    if not isinstance(result, Mapping):
        raise BybitIntradayError("bybit_kline_result_invalid")
    if (
        result.get("category") != BYBIT_CATEGORY
        or result.get("symbol") != instrument.instrument_id
    ):
        raise BybitIntradayError("bybit_kline_identity_mismatch")
    rows = result.get("list")
    if not isinstance(rows, list) or not rows or len(rows) > KLINE_LIMIT:
        raise BybitIntradayError("bybit_kline_rows_invalid")
    provider_ms = _integer(payload.get("time"), "bybit_kline_provider_time")
    provider_at = datetime.fromtimestamp(provider_ms / 1000, tz=timezone.utc)
    if provider_at > acquired + timedelta(seconds=MAX_PROVIDER_CLOCK_SKEW_SECONDS):
        raise BybitIntradayError("bybit_kline_provider_clock_future")
    provider_age = max(0.0, (acquired - provider_at).total_seconds())

    parsed_rows: list[_ParsedKline] = []
    seen_starts: set[int] = set()
    for index, raw in enumerate(rows):
        if not isinstance(raw, list) or len(raw) != 7:
            raise BybitIntradayError(f"bybit_kline_row_{index}_shape_invalid")
        start_ms = _integer(raw[0], "bybit_kline_start")
        if start_ms in seen_starts:
            raise BybitIntradayError("bybit_kline_start_duplicate")
        seen_starts.add(start_ms)
        open_price = _decimal(raw[1], "bybit_kline_open")
        high_price = _decimal(raw[2], "bybit_kline_high")
        low_price = _decimal(raw[3], "bybit_kline_low")
        close_price = _decimal(raw[4], "bybit_kline_close")
        volume = _decimal(raw[5], "bybit_kline_volume", allow_zero=True)
        turnover = _decimal(raw[6], "bybit_kline_turnover", allow_zero=True)
        if high_price < max(open_price, low_price, close_price) or low_price > min(
            open_price, high_price, close_price
        ):
            raise BybitIntradayError("bybit_kline_ohlc_invalid")
        parsed_rows.append(
            (start_ms, open_price, high_price, low_price, close_price, volume, turnover)
        )
    if [row[0] for row in parsed_rows] != sorted(
        (row[0] for row in parsed_rows), reverse=True
    ):
        raise BybitIntradayError("bybit_kline_sort_invalid")

    interval_ms = INTERVAL_SECONDS[interval] * 1000
    expected_start_ms = requested_end_ms + 1 - interval_ms
    exact = [row for row in parsed_rows if row[0] == expected_start_ms]
    if len(exact) != 1:
        raise BybitIntradayError("latest_completed_kline_missing")
    expected_starts = [
        expected_start_ms - index * interval_ms for index in range(len(parsed_rows))
    ]
    if [row[0] for row in parsed_rows] != expected_starts:
        raise BybitIntradayError("completed_kline_sequence_not_contiguous")
    start_ms, open_price, high_price, low_price, close_price, volume, turnover = exact[0]
    end_ms = start_ms + interval_ms
    end_at = datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc)
    if end_ms != requested_end_ms + 1 or end_at > started:
        raise BybitIntradayError("kline_not_completed_before_request")
    if provider_at < end_at:
        raise BybitIntradayError("provider_response_precedes_completed_kline")
    latency = (acquired - end_at).total_seconds()
    if latency < 0:
        raise BybitIntradayError("kline_observation_latency_negative")
    bar_recency = "fresh" if latency < INTERVAL_SECONDS[interval] else "stale"
    provider_freshness = (
        "fresh" if provider_age <= MAX_PROVIDER_RESPONSE_AGE_SECONDS else "stale"
    )
    freshness = (
        "fresh"
        if bar_recency == "fresh" and provider_freshness == "fresh"
        else "stale"
    )
    start_at = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc)
    requested_end_at = datetime.fromtimestamp(
        (requested_end_ms + 1) / 1000, tz=timezone.utc
    )
    rsi_status, latest_rsi = _wilder_rsi_value(parsed_rows)
    return BybitIntradayBar(
        schema_version=BAR_SCHEMA_VERSION,
        venue_id="bybit",
        execution_mode="perpetual",
        category=BYBIT_CATEGORY,
        instrument_id=instrument.instrument_id,
        canonical_asset_id=instrument.canonical_asset_id,
        base_asset=instrument.base_asset,
        quote_asset=instrument.quote_asset,
        settle_asset=instrument.settle_asset,
        contract_type=instrument.contract_type,
        instrument_status=instrument.status,
        interval=INTERVAL_LABELS[interval],
        interval_seconds=INTERVAL_SECONDS[interval],
        bar_start_at=_iso(start_at),
        bar_end_at=_iso(end_at),
        requested_end_at=_iso(requested_end_at),
        request_started_at=_iso(started),
        response_acquired_at=_iso(acquired),
        provider_response_generated_at=_iso(provider_at),
        provider_response_age_seconds=round(provider_age, 6),
        provider_response_freshness_status=provider_freshness,
        observation_latency_seconds=latency,
        bar_close_recency_status=bar_recency,
        freshness_policy="completed_bar_and_current_provider_response",
        freshness_status=freshness,
        open_price=float(open_price),
        high_price=float(high_price),
        low_price=float(low_price),
        close_price=float(close_price),
        price_unit="USDT_per_base_asset",
        volume_base_asset=float(volume),
        volume_unit=instrument.base_asset,
        turnover_usdt=float(turnover),
        turnover_unit="USDT",
        bar_closed=True,
        point_in_time_status="captured_after_close",
        future_data_used=False,
        rsi_status=rsi_status,
        rsi_timeframe=INTERVAL_LABELS[interval],
        rsi_period=RSI_PERIOD,
        wilder_rsi=latest_rsi,
        wilder_rsi_unit="index_0_100",
        rsi_method=RSI_METHOD,
        rsi_candle_close_time=_iso(end_at),
        rsi_available_at=_iso(acquired),
        rsi_source_bar_count=len(parsed_rows),
        rsi_source_lineage_id=request_lineage_id,
        rsi_future_data_used=False,
        source_url=_request_url(request),
        request_lineage_id=request_lineage_id,
    )


def _fixture_smoke(fixture_dir: Path) -> dict[str, object]:
    radar = json.loads(
        (fixture_dir.parent / "bybit_execution_quality" / "radar_assets.json").read_text()
    )
    instruments_payload = json.loads(
        (
            fixture_dir.parent
            / "bybit_execution_quality"
            / "instruments_info.json"
        ).read_text()
    )
    selected = select_bybit_usdt_perpetual_instruments(radar, instruments_payload)
    instrument = next(row for row in selected if row.instrument_id == "BTCUSDT")
    started = datetime(2026, 7, 17, 12, 30, tzinfo=timezone.utc)
    bars = []
    for interval in INTERVAL_SECONDS:
        request = build_bybit_kline_request(
            instrument, interval=interval, as_of=started
        )
        payload = json.loads(
            (fixture_dir / f"klines_btcusdt_{interval}.json").read_text()
        )
        bars.append(
            normalize_bybit_completed_kline(
                payload,
                instrument=instrument,
                request=request,
                request_started_at=started,
                acquired_at=started + timedelta(milliseconds=125),
                request_lineage_id=f"fixture.bybit.kline.{interval}",
            ).to_dict()
        )
    return {
        "contract_version": CONTRACT_VERSION,
        "status": "complete",
        "venue_id": "bybit",
        "execution_mode": "perpetual",
        "instrument_id": instrument.instrument_id,
        "intervals": ["1h", "4h"],
        "bar_count": len(bars),
        "bars": bars,
        "provider_calls": 0,
        "writes": 0,
        "orders": 0,
        "trades": 0,
        "paper_trades": 0,
        "telegram_sends": 0,
        "normal_rsi_writes": 0,
        "event_alpha_triggered_fade": 0,
        "research_only": True,
        "fixture_only": True,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=Path(__file__).resolve().parents[3] / "fixtures" / "bybit_intraday",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        payload = _fixture_smoke(args.fixture_dir)
    except (BybitIntradayError, OSError, ValueError, StopIteration) as exc:
        print(f"radar_bybit_intraday_smoke_blocked: {type(exc).__name__}")
        return 1
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


__all__ = (
    "BAR_SCHEMA_VERSION",
    "CONTRACT_VERSION",
    "INTERVAL_LABELS",
    "INTERVAL_SECONDS",
    "KLINE_LIMIT",
    "KLINE_PATH",
    "OFFICIAL_KLINE_DOC",
    "RSI_METHOD",
    "RSI_PERIOD",
    "BybitIntradayBar",
    "BybitIntradayError",
    "build_bybit_kline_request",
    "completed_kline_cutoff_ms",
    "main",
    "normalize_bybit_completed_kline",
)


if __name__ == "__main__":
    raise SystemExit(main())
