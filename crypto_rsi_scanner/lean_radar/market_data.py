"""Lean market input normalization and one explicitly authorized live read."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
import math
import os
import re
from typing import Mapping, Sequence

import pandas as pd

from crypto_rsi_scanner import config as shared_config
from crypto_rsi_scanner.client import CoinGeckoClient
from crypto_rsi_scanner.indicators import wilder_rsi

from .models import BybitInstrument, MarketSnapshot, UniverseAsset
from .universe import LeanUniverseError, build_universe


LIVE_AUTH_ENV = "RSI_EVENT_DISCOVERY_UNIVERSE_LIVE"
MAX_LIVE_ROWS = 1_000
LIVE_PAGE_SIZE = 250
MAX_RANKED_PAGES = 4
MAX_WATCHLIST_IDS = 100
WATCHLIST_BATCH_SIZE = 50
MAX_LIVE_PROVIDER_CALLS = MAX_RANKED_PAGES + (
    MAX_WATCHLIST_IDS // WATCHLIST_BATCH_SIZE
)
_COINGECKO_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,127}$")


class _MarketDataError(ValueError):
    """Raised when market input cannot be interpreted without guessing units."""

    def __init__(
        self,
        message: str,
        *,
        telemetry: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.telemetry = dict(telemetry or {})


MarketDataError = _MarketDataError


def live_provider_authorized(environ: Mapping[str, str] | None = None) -> bool:
    env = os.environ if environ is None else environ
    return str(env.get(LIVE_AUTH_ENV, "")).strip().casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }


def fetch_live_market_rows(
    *,
    instruments: Sequence[BybitInstrument],
    manual_watchlist: Sequence[Mapping[str, object]] = (),
    environ: Mapping[str, str] | None = None,
    target_count: int = 200,
    page_size: int = LIVE_PAGE_SIZE,
    max_ranked_pages: int = MAX_RANKED_PAGES,
) -> tuple[tuple[Mapping[str, object], ...], dict[str, object]]:
    """Collect an exact, bounded CoinGecko volume-ranked universe.

    Ranked pages continue until the confirmed Bybit intersection reaches the
    target, CoinGecko is exhausted, or the explicit page budget is consumed.
    Missing manual-watchlist IDs then receive separate exact-ID requests.
    """

    if not live_provider_authorized(environ):
        raise MarketDataError(f"{LIVE_AUTH_ENV}=1 is required for a live scan")
    if shared_config.FIXTURE_DIR is not None:
        raise MarketDataError("fixture mode must be unset before a live scan")
    if (
        isinstance(target_count, bool)
        or not isinstance(target_count, int)
        or not 1 <= target_count <= 200
    ):
        raise MarketDataError("live eligible-asset target must be between 1 and 200")
    if (
        isinstance(page_size, bool)
        or not isinstance(page_size, int)
        or not 1 <= page_size <= LIVE_PAGE_SIZE
    ):
        raise MarketDataError("live market page size must be between 1 and 250")
    if (
        isinstance(max_ranked_pages, bool)
        or not isinstance(max_ranked_pages, int)
        or not 1 <= max_ranked_pages <= MAX_RANKED_PAGES
    ):
        raise MarketDataError("live ranked-page budget must be between 1 and 4")
    if not instruments:
        raise MarketDataError("confirmed Bybit instruments are required")
    requested_watchlist_ids = _watchlist_ids(manual_watchlist)

    async def collect() -> tuple[tuple[Mapping[str, object], ...], dict[str, object]]:
        client = CoinGeckoClient(timeout_seconds=8.0, max_retries=1)
        ranked_rows: list[Mapping[str, object]] = []
        targeted_rows: list[Mapping[str, object]] = []
        seen_ranked_ids: set[str] = set()
        request_ledger: list[dict[str, object]] = []
        request_type: str | None = None
        request_ordinal: int | None = None
        request_recorded = False
        exhausted = False
        eligible_count = 0
        try:
            async with client:
                for page in range(1, max_ranked_pages + 1):
                    request_type = "ranked_page"
                    request_ordinal = page
                    request_recorded = False
                    page_rows = await _request_market_rows(
                        client,
                        {
                            "vs_currency": "usd",
                            "order": "volume_desc",
                            "per_page": page_size,
                            "page": page,
                            "sparkline": "true",
                            "price_change_percentage": "1h,24h,7d",
                        },
                    )
                    request_ledger.append(
                        _request_receipt(
                            client.last_request_telemetry,
                            request_type=request_type,
                            ordinal=page,
                            result_count=len(page_rows),
                        )
                    )
                    request_recorded = True
                    for raw in page_rows:
                        canonical_id = _row_id(raw)
                        if canonical_id in seen_ranked_ids:
                            raise MarketDataError(
                                "CoinGecko ranked pages contain a duplicate asset identity"
                            )
                        seen_ranked_ids.add(canonical_id)
                        ranked_rows.append(
                            {**dict(raw), "_lean_acquisition_origin": "ranked"}
                        )
                    try:
                        eligible_count = build_universe(
                            ranked_rows,
                            instruments,
                            (),
                            limit=target_count,
                        ).eligible_ranked_count
                    except LeanUniverseError as exc:
                        raise MarketDataError(
                            "CoinGecko ranked market rows failed universe validation"
                        ) from exc
                    if eligible_count >= target_count:
                        break
                    if len(page_rows) < page_size:
                        exhausted = True
                        break

                missing_watchlist = tuple(
                    asset_id
                    for asset_id in requested_watchlist_ids
                    if asset_id not in seen_ranked_ids
                )
                bounded_watchlist = missing_watchlist[:MAX_WATCHLIST_IDS]
                seen_targeted: set[str] = set()
                for batch_number, offset in enumerate(
                    range(0, len(bounded_watchlist), WATCHLIST_BATCH_SIZE),
                    start=1,
                ):
                    batch = bounded_watchlist[offset : offset + WATCHLIST_BATCH_SIZE]
                    request_type = "targeted_watchlist"
                    request_ordinal = batch_number
                    request_recorded = False
                    page_rows = await _request_market_rows(
                        client,
                        {
                            "vs_currency": "usd",
                            "ids": ",".join(batch),
                            "order": "volume_desc",
                            "per_page": len(batch),
                            "page": 1,
                            "sparkline": "true",
                            "price_change_percentage": "1h,24h,7d",
                        },
                    )
                    request_ledger.append(
                        _request_receipt(
                            client.last_request_telemetry,
                            request_type=request_type,
                            ordinal=batch_number,
                            result_count=len(page_rows),
                            requested_ids=batch,
                        )
                    )
                    request_recorded = True
                    allowed = set(batch)
                    for raw in page_rows:
                        canonical_id = _row_id(raw)
                        if (
                            canonical_id not in allowed
                            or canonical_id in seen_ranked_ids
                            or canonical_id in seen_targeted
                        ):
                            raise MarketDataError(
                                "CoinGecko targeted response identity is inconsistent"
                            )
                        seen_targeted.add(canonical_id)
                        targeted_rows.append(
                            {
                                **dict(raw),
                                "_lean_acquisition_origin": "targeted_watchlist",
                            }
                        )
        except Exception as exc:
            if isinstance(exc, MarketDataError) and exc.telemetry:
                raise
            failure = _failure_telemetry(
                client.last_request_telemetry,
                request_ledger=request_ledger,
                request_type=request_type,
                ordinal=request_ordinal,
                request_recorded=request_recorded,
                validation_failure=isinstance(exc, MarketDataError),
            )
            message = (
                str(exc)
                if isinstance(exc, MarketDataError)
                else "live market collection failed"
            )
            raise MarketDataError(message, telemetry=failure) from exc
        page_budget_reached = (
            eligible_count < target_count
            and not exhausted
            and len(
                [
                    row
                    for row in request_ledger
                    if row["request_type"] == "ranked_page"
                ]
            )
            == max_ranked_pages
        )
        materialized = tuple(ranked_rows + targeted_rows)
        return materialized, {
            "schema_version": "lean_market_acquisition_v1",
            "provider": "coingecko",
            "endpoint_path": "/coins/markets",
            "order": "volume_desc",
            "eligible_target_count": target_count,
            "eligible_ranked_count": eligible_count,
            "ranked_page_count": sum(
                row["request_type"] == "ranked_page" for row in request_ledger
            ),
            "ranked_row_count": len(ranked_rows),
            "ranked_source_exhausted": exhausted,
            "ranked_page_budget_reached": page_budget_reached,
            "target_reached": eligible_count >= target_count,
            "watchlist_configured_count": len(requested_watchlist_ids),
            "watchlist_missing_from_ranked_count": len(missing_watchlist),
            "watchlist_targeted_requested_count": len(bounded_watchlist),
            "watchlist_targeted_returned_count": len(targeted_rows),
            "watchlist_target_budget_truncated_count": max(
                0, len(missing_watchlist) - len(bounded_watchlist)
            ),
            "result_count": len(materialized),
            "provider_call_count": len(request_ledger),
            "provider_call_budget": MAX_LIVE_PROVIDER_CALLS,
            "request_ledger": request_ledger,
            "research_only": True,
        }

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        try:
            return asyncio.run(collect())
        except MarketDataError:
            raise
        except Exception as exc:
            raise MarketDataError("live market collection failed") from exc
    raise MarketDataError("live market collection cannot run inside an active event loop")


async def _request_market_rows(
    client: CoinGeckoClient,
    params: dict[str, object],
) -> tuple[Mapping[str, object], ...]:
    payload = await client._get("/coins/markets", params)
    if not isinstance(payload, list) or len(payload) > LIVE_PAGE_SIZE:
        raise MarketDataError("CoinGecko market response is not a bounded array")
    if not all(isinstance(row, Mapping) for row in payload):
        raise MarketDataError("CoinGecko market response contains a non-object row")
    return tuple(payload)


def _row_id(row: Mapping[str, object]) -> str:
    value = row.get("id")
    if not isinstance(value, str):
        raise MarketDataError("CoinGecko market row has no typed asset identity")
    canonical_id = value.strip()
    if not _COINGECKO_ID.fullmatch(canonical_id):
        raise MarketDataError("CoinGecko market row asset identity is invalid")
    return canonical_id


def _watchlist_ids(
    manual_watchlist: Sequence[Mapping[str, object]],
) -> tuple[str, ...]:
    identities: list[str] = []
    seen: set[str] = set()
    for row in manual_watchlist:
        value = row.get("canonical_asset_id")
        if not isinstance(value, str):
            raise MarketDataError("watchlist asset identity is invalid")
        canonical_id = value.strip()
        if (
            not _COINGECKO_ID.fullmatch(canonical_id)
            or canonical_id in seen
        ):
            raise MarketDataError("watchlist asset identity is invalid or duplicated")
        seen.add(canonical_id)
        identities.append(canonical_id)
    return tuple(sorted(identities))


def _request_receipt(
    telemetry: Mapping[str, object] | None,
    *,
    request_type: str,
    ordinal: int,
    result_count: int,
    requested_ids: Sequence[str] = (),
) -> dict[str, object]:
    values = telemetry or {}
    receipt: dict[str, object] = {
        "request_type": request_type,
        "ordinal": ordinal,
        "endpoint_path": "/coins/markets",
        "http_status": values.get("http_status"),
        "result_count": result_count,
        "retry_count": values.get("retry_count", 0),
        "duration_ms": values.get("duration_ms"),
        "error_class": values.get("error_class"),
    }
    if requested_ids:
        encoded = "\n".join(requested_ids).encode("utf-8")
        receipt.update(
            {
                "requested_id_count": len(requested_ids),
                "requested_ids_sha256": hashlib.sha256(encoded).hexdigest(),
            }
        )
    return receipt


def _failure_telemetry(
    last_request: Mapping[str, object] | None,
    *,
    request_ledger: Sequence[Mapping[str, object]],
    request_type: str | None,
    ordinal: int | None,
    request_recorded: bool,
    validation_failure: bool,
) -> dict[str, object]:
    """Return bounded, secret-free truth for one failed acquisition attempt."""

    last = last_request or {}
    attempted_unrecorded = bool(request_type and last and not request_recorded)
    return {
        "schema_version": "lean_market_acquisition_failure_v1",
        "provider": "coingecko",
        "endpoint_path": "/coins/markets",
        "failure_class": (
            "market_data_validation"
            if validation_failure
            else "provider_request_failed"
        ),
        "failure_stage": request_type or "client_setup",
        "failure_ordinal": ordinal,
        "provider_call_count": len(request_ledger) + int(attempted_unrecorded),
        "completed_request_count": len(request_ledger),
        "request_recorded_before_failure": request_recorded,
        "request_ledger": [dict(row) for row in request_ledger],
        "last_request": {
            "endpoint_path": last.get("endpoint_path"),
            "http_status": last.get("http_status"),
            "retry_count": last.get("retry_count", 0),
            "duration_ms": last.get("duration_ms"),
            "error_class": last.get("error_class"),
        },
        "research_only": True,
    }


def normalize_snapshots(
    rows: Sequence[Mapping[str, object]],
    assets: Sequence[UniverseAsset],
    *,
    observed_at: datetime,
    source_mode: str,
) -> tuple[MarketSnapshot, ...]:
    if observed_at.tzinfo is None:
        raise MarketDataError("market observation time must be timezone-aware")
    if source_mode not in {"live_no_send", "imported_snapshot", "fixture"}:
        raise MarketDataError("market source mode is invalid")
    rows_by_id: dict[str, Mapping[str, object]] = {}
    for row in rows:
        canonical_id = row.get("id")
        if not isinstance(canonical_id, str) or not canonical_id.strip():
            continue
        key = canonical_id.strip()
        if key in rows_by_id:
            raise MarketDataError("market canonical identity is duplicated")
        rows_by_id[key] = row

    snapshots: list[MarketSnapshot] = []
    for asset in assets:
        row = rows_by_id.get(asset.canonical_asset_id)
        if row is None or not asset.active or asset.bybit_instrument is None:
            continue
        snapshots.append(
            normalize_snapshot(
                row,
                asset,
                observed_at=observed_at,
                source_mode=source_mode,
            )
        )
    return tuple(snapshots)


def normalize_snapshot(
    row: Mapping[str, object],
    asset: UniverseAsset,
    *,
    observed_at: datetime,
    source_mode: str,
) -> MarketSnapshot:
    declared_unit = row.get("return_unit")
    if declared_unit not in (None, "", "percent_points", "percentage_points"):
        raise MarketDataError("market return unit is not percent points")
    price = _positive(row.get("current_price"), "current_price")
    market_cap = _positive(row.get("market_cap"), "market_cap")
    volume = _positive(row.get("total_volume"), "total_volume")
    sparkline = _sparkline(row.get("sparkline_in_7d"))
    return_1h = _return_pp(
        row.get("price_change_percentage_1h_in_currency"),
        "price_change_percentage_1h_in_currency",
    )
    return_24h = _return_pp(
        row.get("price_change_percentage_24h_in_currency"),
        "price_change_percentage_24h_in_currency",
    )
    return_7d = _return_pp(
        row.get("price_change_percentage_7d_in_currency"),
        "price_change_percentage_7d_in_currency",
    )
    rsi = _rsi(sparkline)
    spread = _optional_nonnegative(row.get("spread_bps"), "spread_bps")
    available_returns = sum(
        value is not None for value in (return_1h, return_24h, return_7d)
    )
    data_quality = (
        "complete"
        if available_returns >= 3 and rsi is not None
        else "usable"
        if available_returns >= 2
        else "insufficient_market_context"
    )
    return MarketSnapshot(
        canonical_asset_id=asset.canonical_asset_id,
        symbol=asset.symbol,
        name=asset.name,
        bybit_instrument=asset.bybit_instrument,
        observed_at=observed_at.astimezone(timezone.utc).isoformat(),
        source_mode=source_mode,
        price_usd=price,
        market_cap_usd=market_cap,
        volume_usd_24h=volume,
        turnover_ratio_24h=volume / market_cap,
        return_1h_pp=return_1h,
        return_24h_pp=return_24h,
        return_7d_pp=return_7d,
        rsi_14=rsi,
        spread_bps=spread,
        sparkline_prices=sparkline,
        return_basis="coingecko_direct_percent_point_fields",
        rsi_basis=(
            "wilder_14_on_coingecko_7d_sparkline_points_proxy"
            if rsi is not None
            else "unavailable_insufficient_sparkline"
        ),
        data_quality=data_quality,
    )


def _sparkline(value: object) -> tuple[float, ...]:
    if not isinstance(value, Mapping):
        return ()
    prices = value.get("price")
    if not isinstance(prices, list) or len(prices) > 500:
        return ()
    normalized: list[float] = []
    for item in prices:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            return ()
        parsed = float(item)
        if not math.isfinite(parsed) or parsed <= 0:
            return ()
        normalized.append(parsed)
    return tuple(normalized)


def _rsi(prices: Sequence[float]) -> float | None:
    if len(prices) < 15:
        return None
    value = float(wilder_rsi(pd.Series(prices, dtype=float), period=14).iloc[-1])
    return value if math.isfinite(value) else None


def _positive(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MarketDataError(f"{label} is missing or invalid")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise MarketDataError(f"{label} must be positive and finite")
    return parsed


def _return_pp(value: object, label: str) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MarketDataError(f"{label} is invalid")
    parsed = float(value)
    if not math.isfinite(parsed) or abs(parsed) > 500:
        raise MarketDataError(f"{label} is outside plausible percent-point bounds")
    return parsed


def _optional_nonnegative(value: object, label: str) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MarketDataError(f"{label} is invalid")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0 or parsed > 10_000:
        raise MarketDataError(f"{label} is outside plausible bounds")
    return parsed


__all__ = (
    "LIVE_AUTH_ENV",
    "LIVE_PAGE_SIZE",
    "MAX_LIVE_PROVIDER_CALLS",
    "MAX_LIVE_ROWS",
    "MAX_RANKED_PAGES",
    "MAX_WATCHLIST_IDS",
    "MarketDataError",
    "fetch_live_market_rows",
    "live_provider_authorized",
    "normalize_snapshot",
    "normalize_snapshots",
)
