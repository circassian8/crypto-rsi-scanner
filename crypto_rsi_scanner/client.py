from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiohttp

from . import config

log = logging.getLogger(__name__)


class _RateLimiter:
    def __init__(self, calls_per_minute: int):
        self._interval = 60.0 / calls_per_minute
        self._lock = asyncio.Lock()
        self._last: float = 0.0

    async def acquire(self) -> None:
        async with self._lock:
            loop = asyncio.get_event_loop()
            now = loop.time()
            wait = self._last + self._interval - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = loop.time()


def _base_url_and_headers() -> tuple[str, dict[str, str]]:
    key = config.COINGECKO_API_KEY
    key_type = config.COINGECKO_KEY_TYPE
    if key and key_type == "pro":
        return "https://pro-api.coingecko.com/api/v3", {"x-cg-pro-api-key": key}
    if key:
        return "https://api.coingecko.com/api/v3", {"x-cg-demo-api-key": key}
    return "https://api.coingecko.com/api/v3", {}


class CoinGeckoClient:
    def __init__(self, *args: object, **kwargs: object):
        initialize_coingecko_client(self, *args, **kwargs)

    async def __aenter__(self) -> CoinGeckoClient:
        return await enter_coingecko_client(self)

    async def __aexit__(self, *exc: object) -> None:
        await exit_coingecko_client(self, *exc)

    def _fixture_json(self, *parts: str) -> object:
        return load_coingecko_fixture_json(self, *parts)

    async def _get(self, path: str, params: dict) -> dict:
        return await get_coingecko_json(self, path, params)

    async def get_top_markets(self, n: int) -> list[dict]:
        return await get_top_markets(self, n)

    async def get_top_markets_by_volume(self, n: int) -> list[dict]:
        return await get_top_markets_by_volume(self, n)

    async def get_market_chart(self, coin_id: str, days: int) -> dict:
        return await get_market_chart(self, coin_id, days)


def initialize_coingecko_client(
    self: CoinGeckoClient,
    calls_per_minute: int | None = None,
    *,
    timeout_seconds: float | None = None,
    max_retries: int | None = None,
) -> None:
    self.base_url, self.headers = _base_url_and_headers()
    cpm = calls_per_minute or config.CALLS_PER_MINUTE
    self._limiter = _RateLimiter(cpm)
    self._session: aiohttp.ClientSession | None = None
    self._fixture_dir: Path | None = config.FIXTURE_DIR
    notification_mode = str(getattr(config, "EVENT_ALPHA_RUN_MODE", "") or "") == "notification_burn_in"
    self.timeout_seconds = (
        float(timeout_seconds)
        if timeout_seconds is not None
        else (
            float(getattr(config, "EVENT_ALPHA_NOTIFY_PROVIDER_TIMEOUT_SECONDS", 5.0) or 5.0)
            if notification_mode
            else 30.0
        )
    )
    self.max_retries = (
        int(max_retries)
        if max_retries is not None
        else (
            1
            if notification_mode and bool(getattr(config, "EVENT_ALPHA_NOTIFY_FAST_FAIL_ON_DNS", True))
            else config.MAX_RETRIES
        )
    )
    # Sanitized, single-request telemetry. It intentionally never contains the
    # URL query, headers, API key, response body, or recipient identifiers.
    self.last_request_telemetry: dict[str, Any] | None = None


async def enter_coingecko_client(self: CoinGeckoClient) -> CoinGeckoClient:
    if self._fixture_dir is None:
        self._session = aiohttp.ClientSession(headers=self.headers)
    return self


async def exit_coingecko_client(self: CoinGeckoClient, *exc: object) -> None:
    if self._session:
        await self._session.close()


def load_coingecko_fixture_json(self: CoinGeckoClient, *parts: str) -> object:
    if self._fixture_dir is None:
        raise RuntimeError("fixture mode is not enabled")
    path = self._fixture_dir.joinpath(*parts)
    return json.loads(path.read_text(encoding="utf-8"))


async def get_coingecko_json(self: CoinGeckoClient, path: str, params: dict) -> Any:
    url = f"{self.base_url}{path}"
    max_retries = max(1, int(self.max_retries or 1))
    started_at = datetime.now(timezone.utc)
    started_monotonic = asyncio.get_running_loop().time()
    last_status: int | None = None
    for attempt in range(max_retries):
        await self._limiter.acquire()
        try:
            timeout = aiohttp.ClientTimeout(total=max(0.1, float(self.timeout_seconds or 30.0)))
            async with self._session.get(url, params=params, timeout=timeout) as resp:
                last_status = int(resp.status)
                if resp.status == 200:
                    payload = await resp.json()
                    _record_request_telemetry(
                        self,
                        path=path,
                        started_at=started_at,
                        started_monotonic=started_monotonic,
                        http_status=last_status,
                        retry_count=attempt,
                        error_class=None,
                        result_count=len(payload) if isinstance(payload, (list, dict)) else None,
                    )
                    return payload
                if resp.status == 429:
                    retry_after = resp.headers.get("Retry-After")
                    wait = float(retry_after) if retry_after and retry_after.isdigit() else 8.0 * (attempt + 1)
                    log.warning("Rate limited on %s, backing off %.0fs", path, wait)
                    await asyncio.sleep(wait)
                    continue
                if 500 <= resp.status < 600:
                    await asyncio.sleep(2.0 * (attempt + 1))
                    continue
                text = await resp.text()
                _record_request_telemetry(
                    self,
                    path=path,
                    started_at=started_at,
                    started_monotonic=started_monotonic,
                    http_status=last_status,
                    retry_count=attempt,
                    error_class="http_error",
                )
                raise RuntimeError(f"CoinGecko {resp.status}: {text[:200]}")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            if attempt == max_retries - 1:
                _record_request_telemetry(
                    self,
                    path=path,
                    started_at=started_at,
                    started_monotonic=started_monotonic,
                    http_status=last_status,
                    retry_count=attempt,
                    error_class=type(e).__name__,
                )
                raise
            log.warning("Request error on %s (attempt %d): %s", path, attempt + 1, e)
            await asyncio.sleep(2.0 * (attempt + 1))
    _record_request_telemetry(
        self,
        path=path,
        started_at=started_at,
        started_monotonic=started_monotonic,
        http_status=last_status,
        retry_count=max_retries - 1,
        error_class="request_retries_exhausted",
    )
    raise RuntimeError(f"CoinGecko request failed after {max_retries} retries: {path}")


def _record_request_telemetry(
    self: CoinGeckoClient,
    *,
    path: str,
    started_at: datetime,
    started_monotonic: float,
    http_status: int | None,
    retry_count: int,
    error_class: str | None,
    result_count: int | None = None,
) -> None:
    ended_at = datetime.now(timezone.utc)
    duration_ms = max(
        0,
        int(round((asyncio.get_running_loop().time() - started_monotonic) * 1000)),
    )
    self.last_request_telemetry = {
        "endpoint_path": path if path.startswith("/") else "/unknown",
        "request_started_at": started_at.isoformat(),
        "request_ended_at": ended_at.isoformat(),
        "duration_ms": duration_ms,
        "http_status": http_status,
        "result_count": result_count,
        "retry_count": max(0, int(retry_count)),
        "error_class": error_class,
        "cache_behavior": "network",
    }


async def get_top_markets(self: CoinGeckoClient, n: int) -> list[dict]:
    if self._fixture_dir is not None:
        data = self._fixture_json("top_markets.json")
        if not isinstance(data, list):
            raise RuntimeError(f"fixture top_markets.json must contain a list: {self._fixture_dir}")
        return data[:n]
    return await self._get(
        "/coins/markets",
        {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": min(n, 250),
            "page": 1,
            "sparkline": "true",
            "price_change_percentage": "24h,7d",
        },
    )


async def get_top_markets_by_volume(self: CoinGeckoClient, n: int) -> list[dict]:
    if self._fixture_dir is not None:
        data = self._fixture_json("top_markets.json")
        if not isinstance(data, list):
            raise RuntimeError(
                f"fixture top_markets.json must contain a list: {self._fixture_dir}"
            )
        rows = [row for row in data if isinstance(row, dict)]
        rows.sort(
            key=lambda row: (
                -float(row.get("total_volume", 0) or 0),
                str(row.get("id", "")),
            )
        )
        return rows[:n]
    return await self._get(
        "/coins/markets",
        {
            "vs_currency": "usd",
            "order": "volume_desc",
            "per_page": min(n, 250),
            "page": 1,
            "sparkline": "true",
            "price_change_percentage": "1h,24h,7d",
        },
    )


async def get_market_chart(self: CoinGeckoClient, coin_id: str, days: int) -> dict:
    if self._fixture_dir is not None:
        chart_dir = self._fixture_dir / "market_chart"
        exact = chart_dir / f"{coin_id}-{days}.json"
        fallback = chart_dir / f"{coin_id}.json"
        path = exact if exact.exists() else fallback
        if not path.exists():
            raise FileNotFoundError(
                f"missing CoinGecko chart fixture for {coin_id} ({days}d) in {chart_dir}"
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise RuntimeError(f"fixture chart must contain an object: {path}")
        return data
    return await self._get(
        f"/coins/{coin_id}/market_chart",
        {"vs_currency": "usd", "days": days},
    )
