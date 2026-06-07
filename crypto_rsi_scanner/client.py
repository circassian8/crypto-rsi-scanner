from __future__ import annotations

import asyncio
import logging

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
    def __init__(self, calls_per_minute: int | None = None):
        self.base_url, self.headers = _base_url_and_headers()
        cpm = calls_per_minute or config.CALLS_PER_MINUTE
        self._limiter = _RateLimiter(cpm)
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> CoinGeckoClient:
        self._session = aiohttp.ClientSession(headers=self.headers)
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._session:
            await self._session.close()

    async def _get(self, path: str, params: dict) -> dict:
        url = f"{self.base_url}{path}"
        for attempt in range(config.MAX_RETRIES):
            await self._limiter.acquire()
            try:
                timeout = aiohttp.ClientTimeout(total=30)
                async with self._session.get(url, params=params, timeout=timeout) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    if resp.status == 429:
                        retry_after = resp.headers.get("Retry-After")
                        if retry_after and retry_after.isdigit():
                            wait = float(retry_after)
                        else:
                            wait = 8.0 * (attempt + 1)
                        log.warning("Rate limited on %s, backing off %.0fs", path, wait)
                        await asyncio.sleep(wait)
                        continue
                    if 500 <= resp.status < 600:
                        await asyncio.sleep(2.0 * (attempt + 1))
                        continue
                    text = await resp.text()
                    raise RuntimeError(f"CoinGecko {resp.status}: {text[:200]}")
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt == config.MAX_RETRIES - 1:
                    raise
                log.warning("Request error on %s (attempt %d): %s", path, attempt + 1, e)
                await asyncio.sleep(2.0 * (attempt + 1))
        raise RuntimeError(f"CoinGecko request failed after {config.MAX_RETRIES} retries: {path}")

    async def get_top_markets(self, n: int) -> list[dict]:
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

    async def get_market_chart(self, coin_id: str, days: int) -> dict:
        return await self._get(
            f"/coins/{coin_id}/market_chart",
            {"vs_currency": "usd", "days": days},
        )
