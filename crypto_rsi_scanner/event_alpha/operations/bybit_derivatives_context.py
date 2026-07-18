"""Offline Bybit USDT-perpetual derivatives-context contract.

The venue and instrument family are already fixed for Decision Radar research:
Bybit USDT-linear perpetuals.  This module normalizes already-supplied public
V5 ticker, settled funding, open-interest, and long/short-account-ratio bytes
for one exact execution-quality instrument.  It has no HTTP client,
authorization mutation, persistence, notification, order, or trading path.
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

from .bybit_execution_quality import (
    BYBIT_CATEGORY,
    CONTRACT_TYPE,
    EXECUTION_MODE,
    INSTRUMENT_STATUS,
    PUBLIC_API_BASE,
    QUOTE_ASSET,
    VENUE_ID,
    BybitEligibleInstrument,
    BybitPublicRequest,
    select_bybit_usdt_perpetual_instruments,
)


CONTRACT_VERSION = "crypto_radar_bybit_derivatives_context_v1"
SNAPSHOT_SCHEMA_VERSION = "crypto_radar.bybit_derivatives_context.v1"
TICKERS_PATH = "/v5/market/tickers"
FUNDING_HISTORY_PATH = "/v5/market/funding/history"
OPEN_INTEREST_PATH = "/v5/market/open-interest"
ACCOUNT_RATIO_PATH = "/v5/market/account-ratio"
OFFICIAL_TICKERS_DOC = "https://bybit-exchange.github.io/docs/v5/market/tickers"
OFFICIAL_FUNDING_DOC = (
    "https://bybit-exchange.github.io/docs/v5/market/history-fund-rate"
)
OFFICIAL_OPEN_INTEREST_DOC = (
    "https://bybit-exchange.github.io/docs/v5/market/open-interest"
)
OFFICIAL_ACCOUNT_RATIO_DOC = (
    "https://bybit-exchange.github.io/docs/v5/market/long-short-ratio"
)
HISTORY_PERIOD = "1h"
HISTORY_LIMIT = 2
MAX_RADAR_ASSETS = 30
REQUESTS_PER_INSTRUMENT = 4
MAX_PLANNED_REQUESTS = MAX_RADAR_ASSETS * REQUESTS_PER_INSTRUMENT
DEFAULT_FRESHNESS_SECONDS = 15.0
MAX_PROVIDER_CLOCK_SKEW_SECONDS = 60
MAX_ABSOLUTE_RETURN_FRACTION = Decimal("3")
_LINEAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class _BybitDerivativesContextError(ValueError):
    """Raised when public derivatives payloads violate the closed contract."""


@dataclass(frozen=True)
class _BybitDerivativesContextSnapshot:
    """One exact venue-native point-in-time derivatives context snapshot."""

    schema_version: str
    contract_version: str
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
    provider_observed_at: str
    acquired_at: str
    age_seconds: float
    freshness_status: str
    mark_price_usdt: float
    index_price_usdt: float
    mark_index_basis_bps: float
    return_24h_percent_points: float
    current_funding_rate_fraction: float
    current_funding_rate_percent_points: float
    next_funding_at: str
    funding_interval_hours: int
    latest_settled_funding_rate_fraction: float
    prior_settled_funding_rate_fraction: float
    settled_funding_mean_fraction: float
    latest_settled_funding_at: str
    open_interest_base_asset: float
    open_interest_usdt: float
    open_interest_change_1h_percent_points: float
    open_interest_observed_at: str
    long_account_ratio_fraction: float
    short_account_ratio_fraction: float
    long_short_account_ratio: float
    account_ratio_observed_at: str
    turnover_24h_usdt: float
    volume_24h_base_asset: float
    source_urls: tuple[tuple[str, str], ...]
    request_lineage_ids: tuple[tuple[str, str], ...]
    future_data_used: bool
    context_only: bool
    directional_authority: bool
    decision_policy_applied: bool
    protocol_v2_annex_bound: bool
    protocol_v2_evidence_eligible: bool
    research_only: bool = True

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["source_urls"] = dict(self.source_urls)
        value["request_lineage_ids"] = dict(self.request_lineage_ids)
        value["units"] = {
            "prices": "USDT_per_base_asset",
            "mark_index_basis": "basis_points",
            "returns": "percent_points",
            "funding_rates": "fraction_with_explicit_percent_point_projection",
            "open_interest_size": self.base_asset,
            "open_interest_value": "USDT",
            "open_interest_change": "percent_points",
            "account_ratios": "fraction",
            "turnover": "USDT",
            "volume": self.base_asset,
        }
        return value


BybitDerivativesContextError = _BybitDerivativesContextError
BybitDerivativesContextSnapshot = _BybitDerivativesContextSnapshot


@dataclass(frozen=True)
class _ValidatedPayloadParts:
    ticker: Mapping[str, Any]
    ticker_at: datetime
    funding_rows: tuple[tuple[Mapping[str, Any], int], ...]
    open_interest_rows: tuple[tuple[Mapping[str, Any], int], ...]
    account_ratio_rows: tuple[tuple[Mapping[str, Any], int], ...]
    observed_at: datetime


def _aware_utc(value: datetime | str, field: str) -> datetime:
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise BybitDerivativesContextError(f"{field}_invalid") from exc
    elif isinstance(value, datetime):
        parsed = value
    else:
        raise BybitDerivativesContextError(f"{field}_invalid")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BybitDerivativesContextError(f"{field}_timezone_missing")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _integer(value: object, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool):
        raise BybitDerivativesContextError(f"{field}_invalid")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise BybitDerivativesContextError(f"{field}_invalid") from exc
    if str(value).strip() != str(parsed) and not isinstance(value, int):
        raise BybitDerivativesContextError(f"{field}_invalid")
    if parsed < minimum:
        raise BybitDerivativesContextError(f"{field}_invalid")
    return parsed


def _decimal(
    value: object,
    field: str,
    *,
    minimum: Decimal | None = None,
    maximum_abs: Decimal | None = None,
) -> Decimal:
    if isinstance(value, bool):
        raise BybitDerivativesContextError(f"{field}_invalid")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise BybitDerivativesContextError(f"{field}_invalid") from exc
    if not parsed.is_finite():
        raise BybitDerivativesContextError(f"{field}_invalid")
    if minimum is not None and parsed < minimum:
        raise BybitDerivativesContextError(f"{field}_invalid")
    if maximum_abs is not None and abs(parsed) > maximum_abs:
        raise BybitDerivativesContextError(f"{field}_implausible")
    return parsed


def _valid_instrument(instrument: BybitEligibleInstrument) -> None:
    if (
        instrument.instrument_id != f"{instrument.base_asset}{QUOTE_ASSET}"
        or instrument.radar_symbol != instrument.base_asset
        or instrument.quote_asset != QUOTE_ASSET
        or instrument.settle_asset != QUOTE_ASSET
        or instrument.contract_type != CONTRACT_TYPE
        or instrument.status != INSTRUMENT_STATUS
    ):
        raise BybitDerivativesContextError("eligible_instrument_contract_invalid")


def build_bybit_derivatives_request_plan(
    instruments: Sequence[BybitEligibleInstrument],
) -> dict[str, object]:
    """Build a bounded public-GET-only plan without executing it."""

    if not instruments or len(instruments) > MAX_RADAR_ASSETS:
        raise BybitDerivativesContextError("derivatives_instrument_count_invalid")
    if len({row.instrument_id for row in instruments}) != len(instruments):
        raise BybitDerivativesContextError("derivatives_instrument_identity_duplicate")
    requests: list[BybitPublicRequest] = []
    for instrument in instruments:
        _valid_instrument(instrument)
        common = (("category", BYBIT_CATEGORY), ("symbol", instrument.instrument_id))
        requests.extend(
            (
                BybitPublicRequest("GET", TICKERS_PATH, common),
                BybitPublicRequest(
                    "GET",
                    FUNDING_HISTORY_PATH,
                    (*common, ("limit", str(HISTORY_LIMIT))),
                ),
                BybitPublicRequest(
                    "GET",
                    OPEN_INTEREST_PATH,
                    (*common, ("intervalTime", HISTORY_PERIOD), ("limit", str(HISTORY_LIMIT))),
                ),
                BybitPublicRequest(
                    "GET",
                    ACCOUNT_RATIO_PATH,
                    (*common, ("period", HISTORY_PERIOD), ("limit", str(HISTORY_LIMIT))),
                ),
            )
        )
    if len(requests) > MAX_PLANNED_REQUESTS:
        raise BybitDerivativesContextError("derivatives_request_bound_exceeded")
    return {
        "contract_version": CONTRACT_VERSION,
        "venue_id": VENUE_ID,
        "execution_mode": EXECUTION_MODE,
        "category": BYBIT_CATEGORY,
        "quote_asset": QUOTE_ASSET,
        "requests": [request.to_dict() for request in requests],
        "request_count": len(requests),
        "maximum_request_count": MAX_PLANNED_REQUESTS,
        "provider_call_authorized": False,
        "provider_call_planned": False,
        "provider_call_attempted": False,
        "credentials_required": False,
        "private_data": False,
        "orders_available": False,
        "research_only": True,
    }


def _response(
    payload: Mapping[str, Any],
    *,
    label: str,
    acquired: datetime,
) -> tuple[Mapping[str, Any], datetime]:
    if isinstance(payload.get("retCode"), bool) or payload.get("retCode") != 0:
        raise BybitDerivativesContextError(f"{label}_response_not_ok")
    result = payload.get("result")
    if not isinstance(result, Mapping):
        raise BybitDerivativesContextError(f"{label}_result_invalid")
    provider_ms = _integer(payload.get("time"), f"{label}_provider_time", minimum=1)
    provider_at = datetime.fromtimestamp(provider_ms / 1000, tz=timezone.utc)
    if provider_at > acquired + timedelta(seconds=MAX_PROVIDER_CLOCK_SKEW_SECONDS):
        raise BybitDerivativesContextError(f"{label}_provider_clock_future")
    return result, provider_at


def _rows(
    result: Mapping[str, Any],
    *,
    label: str,
    instrument_id: str,
    timestamp_field: str,
) -> list[tuple[Mapping[str, Any], int]]:
    raw_rows = result.get("list")
    if not isinstance(raw_rows, list) or len(raw_rows) != HISTORY_LIMIT:
        raise BybitDerivativesContextError(f"{label}_rows_invalid")
    parsed: list[tuple[Mapping[str, Any], int]] = []
    for raw in raw_rows:
        if not isinstance(raw, Mapping) or raw.get("symbol") != instrument_id:
            raise BybitDerivativesContextError(f"{label}_identity_mismatch")
        parsed.append((raw, _integer(raw.get(timestamp_field), f"{label}_timestamp", minimum=1)))
    timestamps = [timestamp for _row, timestamp in parsed]
    if len(set(timestamps)) != len(timestamps) or timestamps != sorted(timestamps, reverse=True):
        raise BybitDerivativesContextError(f"{label}_time_order_invalid")
    return parsed


def _validated_payload_parts(
    ticker_payload: Mapping[str, Any],
    funding_payload: Mapping[str, Any],
    open_interest_payload: Mapping[str, Any],
    account_ratio_payload: Mapping[str, Any],
    *,
    instrument: BybitEligibleInstrument,
    acquired: datetime,
) -> _ValidatedPayloadParts:
    ticker_result, ticker_at = _response(ticker_payload, label="ticker", acquired=acquired)
    funding_result, funding_at = _response(funding_payload, label="funding", acquired=acquired)
    oi_result, oi_at = _response(open_interest_payload, label="open_interest", acquired=acquired)
    ratio_result, ratio_at = _response(account_ratio_payload, label="account_ratio", acquired=acquired)
    if ticker_result.get("category") != BYBIT_CATEGORY:
        raise BybitDerivativesContextError("ticker_category_mismatch")
    ticker_rows = ticker_result.get("list")
    if not isinstance(ticker_rows, list) or len(ticker_rows) != 1:
        raise BybitDerivativesContextError("ticker_rows_invalid")
    ticker = ticker_rows[0]
    if not isinstance(ticker, Mapping) or ticker.get("symbol") != instrument.instrument_id:
        raise BybitDerivativesContextError("ticker_identity_mismatch")
    if funding_result.get("category") != BYBIT_CATEGORY:
        raise BybitDerivativesContextError("funding_category_mismatch")
    if (
        oi_result.get("category") != BYBIT_CATEGORY
        or oi_result.get("symbol") != instrument.instrument_id
    ):
        raise BybitDerivativesContextError("open_interest_identity_mismatch")

    histories = (
        ("funding", _rows(funding_result, label="funding", instrument_id=instrument.instrument_id, timestamp_field="fundingRateTimestamp"), funding_at),
        ("open_interest", _rows(oi_result, label="open_interest", instrument_id=instrument.instrument_id, timestamp_field="timestamp"), oi_at),
        ("account_ratio", _rows(ratio_result, label="account_ratio", instrument_id=instrument.instrument_id, timestamp_field="timestamp"), ratio_at),
    )
    observed_at = max(ticker_at, funding_at, oi_at, ratio_at)
    if acquired < observed_at:
        raise BybitDerivativesContextError("acquisition_precedes_provider_response")
    for label, rows, provider_at in histories:
        if any(timestamp > int(provider_at.timestamp() * 1000) for _row, timestamp in rows):
            raise BybitDerivativesContextError(f"{label}_future_row")
    return _ValidatedPayloadParts(
        ticker=ticker,
        ticker_at=ticker_at,
        funding_rows=tuple(histories[0][1]),
        open_interest_rows=tuple(histories[1][1]),
        account_ratio_rows=tuple(histories[2][1]),
        observed_at=observed_at,
    )


def normalize_bybit_derivatives_context(
    ticker_payload: Mapping[str, Any],
    funding_payload: Mapping[str, Any],
    open_interest_payload: Mapping[str, Any],
    account_ratio_payload: Mapping[str, Any],
    *,
    instrument: BybitEligibleInstrument,
    acquired_at: datetime | str,
    request_lineage_ids: Mapping[str, str],
    freshness_seconds: float = DEFAULT_FRESHNESS_SECONDS,
) -> BybitDerivativesContextSnapshot:
    """Normalize four exact public responses into one closed snapshot."""

    _valid_instrument(instrument)
    acquired = _aware_utc(acquired_at, "acquired_at")
    if not math.isfinite(freshness_seconds) or freshness_seconds <= 0:
        raise BybitDerivativesContextError("freshness_seconds_invalid")
    expected_lineage = {"ticker", "funding_history", "open_interest", "account_ratio"}
    if set(request_lineage_ids) != expected_lineage or any(
        not _LINEAGE_RE.fullmatch(str(value)) for value in request_lineage_ids.values()
    ):
        raise BybitDerivativesContextError("request_lineage_ids_invalid")

    parts = _validated_payload_parts(
        ticker_payload,
        funding_payload,
        open_interest_payload,
        account_ratio_payload,
        instrument=instrument,
        acquired=acquired,
    )
    ticker = parts.ticker
    funding_rows = parts.funding_rows
    oi_rows = parts.open_interest_rows
    ratio_rows = parts.account_ratio_rows
    ticker_at = parts.ticker_at
    observed_at = parts.observed_at

    mark = _decimal(ticker.get("markPrice"), "mark_price", minimum=Decimal("0.0000000001"))
    index = _decimal(ticker.get("indexPrice"), "index_price", minimum=Decimal("0.0000000001"))
    basis_bps = (mark - index) / index * Decimal("10000")
    if abs(basis_bps) > Decimal("5000"):
        raise BybitDerivativesContextError("mark_index_basis_implausible")
    return_24h = _decimal(
        ticker.get("price24hPcnt"),
        "return_24h",
        maximum_abs=MAX_ABSOLUTE_RETURN_FRACTION,
    )
    current_funding = _decimal(
        ticker.get("fundingRate"), "current_funding", maximum_abs=Decimal("0.1")
    )
    funding_interval = _integer(
        ticker.get("fundingIntervalHour"), "funding_interval_hours", minimum=1
    )
    if funding_interval > 24:
        raise BybitDerivativesContextError("funding_interval_hours_invalid")
    next_funding_ms = _integer(ticker.get("nextFundingTime"), "next_funding_time", minimum=1)
    if next_funding_ms < int(ticker_at.timestamp() * 1000):
        raise BybitDerivativesContextError("next_funding_time_past")

    settled_rates = [
        _decimal(row.get("fundingRate"), "settled_funding", maximum_abs=Decimal("0.1"))
        for row, _timestamp in funding_rows
    ]
    oi_values = [
        _decimal(row.get("openInterest"), "open_interest_history", minimum=Decimal("0"))
        for row, _timestamp in oi_rows
    ]
    prior_oi = oi_values[1]
    if prior_oi == 0:
        raise BybitDerivativesContextError("open_interest_prior_zero")
    oi_change = (oi_values[0] - prior_oi) / prior_oi * Decimal("100")

    latest_ratio = ratio_rows[0][0]
    buy_ratio = _decimal(latest_ratio.get("buyRatio"), "buy_ratio", minimum=Decimal("0"))
    sell_ratio = _decimal(latest_ratio.get("sellRatio"), "sell_ratio", minimum=Decimal("0"))
    if buy_ratio > 1 or sell_ratio > 1 or abs((buy_ratio + sell_ratio) - 1) > Decimal("0.001"):
        raise BybitDerivativesContextError("account_ratio_sum_invalid")
    if sell_ratio == 0:
        raise BybitDerivativesContextError("account_ratio_sell_zero")

    age = (acquired - observed_at).total_seconds()
    return BybitDerivativesContextSnapshot(
        schema_version=SNAPSHOT_SCHEMA_VERSION,
        contract_version=CONTRACT_VERSION,
        venue_id=VENUE_ID,
        execution_mode=EXECUTION_MODE,
        category=BYBIT_CATEGORY,
        instrument_id=instrument.instrument_id,
        canonical_asset_id=instrument.canonical_asset_id,
        base_asset=instrument.base_asset,
        quote_asset=instrument.quote_asset,
        settle_asset=instrument.settle_asset,
        contract_type=instrument.contract_type,
        instrument_status=instrument.status,
        provider_observed_at=_iso(observed_at),
        acquired_at=_iso(acquired),
        age_seconds=round(age, 6),
        freshness_status="fresh" if age <= freshness_seconds else "stale",
        mark_price_usdt=float(mark),
        index_price_usdt=float(index),
        mark_index_basis_bps=float(basis_bps),
        return_24h_percent_points=float(return_24h * Decimal("100")),
        current_funding_rate_fraction=float(current_funding),
        current_funding_rate_percent_points=float(current_funding * Decimal("100")),
        next_funding_at=_iso(datetime.fromtimestamp(next_funding_ms / 1000, tz=timezone.utc)),
        funding_interval_hours=funding_interval,
        latest_settled_funding_rate_fraction=float(settled_rates[0]),
        prior_settled_funding_rate_fraction=float(settled_rates[1]),
        settled_funding_mean_fraction=float(sum(settled_rates) / len(settled_rates)),
        latest_settled_funding_at=_iso(
            datetime.fromtimestamp(funding_rows[0][1] / 1000, tz=timezone.utc)
        ),
        open_interest_base_asset=float(
            _decimal(ticker.get("openInterest"), "open_interest", minimum=Decimal("0"))
        ),
        open_interest_usdt=float(
            _decimal(ticker.get("openInterestValue"), "open_interest_value", minimum=Decimal("0"))
        ),
        open_interest_change_1h_percent_points=float(oi_change),
        open_interest_observed_at=_iso(
            datetime.fromtimestamp(oi_rows[0][1] / 1000, tz=timezone.utc)
        ),
        long_account_ratio_fraction=float(buy_ratio),
        short_account_ratio_fraction=float(sell_ratio),
        long_short_account_ratio=float(buy_ratio / sell_ratio),
        account_ratio_observed_at=_iso(
            datetime.fromtimestamp(ratio_rows[0][1] / 1000, tz=timezone.utc)
        ),
        turnover_24h_usdt=float(
            _decimal(ticker.get("turnover24h"), "turnover_24h", minimum=Decimal("0"))
        ),
        volume_24h_base_asset=float(
            _decimal(ticker.get("volume24h"), "volume_24h", minimum=Decimal("0"))
        ),
        source_urls=tuple(sorted(_source_urls(instrument.instrument_id).items())),
        request_lineage_ids=tuple(sorted((key, str(value)) for key, value in request_lineage_ids.items())),
        future_data_used=False,
        context_only=True,
        directional_authority=False,
        decision_policy_applied=False,
        protocol_v2_annex_bound=False,
        protocol_v2_evidence_eligible=False,
        research_only=True,
    )


def _source_urls(instrument_id: str) -> dict[str, str]:
    common = {"category": BYBIT_CATEGORY, "symbol": instrument_id}
    return {
        "ticker": f"{PUBLIC_API_BASE}{TICKERS_PATH}?{urlencode(common)}",
        "funding_history": f"{PUBLIC_API_BASE}{FUNDING_HISTORY_PATH}?{urlencode({**common, 'limit': HISTORY_LIMIT})}",
        "open_interest": f"{PUBLIC_API_BASE}{OPEN_INTEREST_PATH}?{urlencode({**common, 'intervalTime': HISTORY_PERIOD, 'limit': HISTORY_LIMIT})}",
        "account_ratio": f"{PUBLIC_API_BASE}{ACCOUNT_RATIO_PATH}?{urlencode({**common, 'period': HISTORY_PERIOD, 'limit': HISTORY_LIMIT})}",
    }


def run_fixture_smoke(fixture_dir: Path) -> dict[str, object]:
    quality_dir = fixture_dir.parent / "bybit_execution_quality"
    radar = json.loads((quality_dir / "radar_assets.json").read_text(encoding="utf-8"))
    instruments = json.loads((quality_dir / "instruments_info.json").read_text(encoding="utf-8"))
    selected = select_bybit_usdt_perpetual_instruments(radar, instruments)
    instrument = next(row for row in selected if row.instrument_id == "BTCUSDT")
    names = ("ticker", "funding_history", "open_interest", "account_ratio")
    payloads = {
        name: json.loads((fixture_dir / f"{name}_btcusdt.json").read_text(encoding="utf-8"))
        for name in names
    }
    snapshot = normalize_bybit_derivatives_context(
        payloads["ticker"],
        payloads["funding_history"],
        payloads["open_interest"],
        payloads["account_ratio"],
        instrument=instrument,
        acquired_at="2026-07-18T07:44:01Z",
        request_lineage_ids={name: f"fixture.bybit.derivatives.{name}" for name in names},
    )
    return {
        "contract_version": CONTRACT_VERSION,
        "status": "complete",
        "mode": "offline_fixture",
        "snapshot": snapshot.to_dict(),
        "request_plan": build_bybit_derivatives_request_plan(selected),
        "provider_calls": 0,
        "writes": 0,
        "credentials_read": False,
        "private_data_read": False,
        "orders": 0,
        "trades": 0,
        "paper_trades": 0,
        "telegram_sends": 0,
        "normal_rsi_writes": 0,
        "event_alpha_triggered_fade": 0,
        "protocol_v2_evidence_eligible": False,
        "research_only": True,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=Path(__file__).resolve().parents[3] / "fixtures" / "bybit_derivatives_context",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_fixture_smoke(args.fixture_dir)
    except (BybitDerivativesContextError, OSError, ValueError, StopIteration) as exc:
        print(f"radar_bybit_derivatives_smoke_blocked: {type(exc).__name__}")
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


__all__ = (
    "ACCOUNT_RATIO_PATH",
    "CONTRACT_VERSION",
    "FUNDING_HISTORY_PATH",
    "MAX_ABSOLUTE_RETURN_FRACTION",
    "MAX_PLANNED_REQUESTS",
    "OFFICIAL_ACCOUNT_RATIO_DOC",
    "OFFICIAL_FUNDING_DOC",
    "OFFICIAL_OPEN_INTEREST_DOC",
    "OFFICIAL_TICKERS_DOC",
    "OPEN_INTEREST_PATH",
    "SNAPSHOT_SCHEMA_VERSION",
    "TICKERS_PATH",
    "BybitDerivativesContextError",
    "BybitDerivativesContextSnapshot",
    "build_bybit_derivatives_request_plan",
    "main",
    "normalize_bybit_derivatives_context",
    "run_fixture_smoke",
)


if __name__ == "__main__":
    raise SystemExit(main())
