"""Universe hygiene filters.

CoinGecko's market-cap list can include stablecoins, wrapped/staked receipts,
synthetics, stale listings, and very low-liquidity assets. Those entries pollute
live alerts, outcomes, paper trades, and backtests, so keep the screening logic
pure and shared by the live scanner and research paths.
"""

from __future__ import annotations

from collections import Counter
import re
import unicodedata

from . import config


_STABLE_SYMBOLS = {
    "usd", "usdt", "usdc", "dai", "usde", "fdusd", "tusd", "usdd", "pyusd",
    "usds", "busd", "gusd", "frax", "lusd", "usd0", "usdb", "crvusd",
    "usdx", "susd", "eusd", "usdp", "usdy", "usdl", "rlusd",
}

_STABLE_NAME_RE = re.compile(
    r"\b(stablecoin|stable coin|stable|tether|usd|u\.s\. dollar|dollar|dai|frax)\b"
)

_DERIVATIVE_NAME_RE = re.compile(
    r"\b("
    r"wrapped|bridged|staked|restaked|liquid staked|liquid staking|"
    r"staking token|receipt|synthetic|binance-peg|wormhole|axelar"
    r")\b"
)


def _clean_text(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Cf")
    return text.casefold().strip()


def _as_float(value: object) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def candidate_count(target: int) -> int:
    """How many CoinGecko market rows to request before hygiene filtering."""
    extra = max(target * config.UNIVERSE_FETCH_MULTIPLIER, target + config.UNIVERSE_EXTRA_CANDIDATES)
    return min(config.UNIVERSE_MAX_CANDIDATES, max(target, extra))


def exclusion_reason(market: dict) -> str | None:
    """Return a machine-readable exclusion reason, or None when keepable."""
    symbol = _clean_text(market.get("symbol"))
    coin_id = _clean_text(market.get("id"))
    name = _clean_text(market.get("name"))
    joined = f"{coin_id} {name}"

    if not symbol or not coin_id:
        return "missing_identity"

    if symbol in _STABLE_SYMBOLS:
        return "stable_like"
    if _STABLE_NAME_RE.search(name) and (
        symbol.endswith("usd") or "usd" in joined or "stable" in name
    ):
        return "stable_like"

    if symbol in config.EXCLUDE_SYMBOLS:
        return "excluded_symbol"

    if _DERIVATIVE_NAME_RE.search(joined):
        return "wrapped_staked_or_synthetic"

    price = _as_float(market.get("current_price"))
    market_cap = _as_float(market.get("market_cap"))
    volume = _as_float(market.get("total_volume"))
    pct_24h = _as_float(
        market.get("price_change_percentage_24h_in_currency")
        if market.get("price_change_percentage_24h_in_currency") is not None
        else market.get("price_change_percentage_24h")
    )

    if price is not None and price <= 0:
        return "invalid_price"
    if market_cap is not None and market_cap <= 0:
        return "invalid_market_cap"
    if (
        config.UNIVERSE_MIN_MARKET_CAP_USD > 0
        and market_cap is not None
        and market_cap < config.UNIVERSE_MIN_MARKET_CAP_USD
    ):
        return "low_market_cap"
    if (
        market_cap is not None
        and market_cap > 0
        and volume is not None
        and volume / market_cap < config.UNIVERSE_MIN_VOLUME_TO_MCAP
    ):
        return "low_liquidity"
    if pct_24h is not None and abs(pct_24h) > config.UNIVERSE_MAX_ABS_24H_CHANGE:
        return "suspicious_24h_move"

    return None


def filter_markets(markets: list[dict], limit: int | None = None) -> tuple[list[dict], Counter]:
    kept: list[dict] = []
    excluded: Counter = Counter()
    for market in markets:
        reason = exclusion_reason(market)
        if reason:
            excluded[reason] += 1
            continue
        kept.append(market)
        if limit is not None and len(kept) >= limit:
            break
    return kept, excluded


def format_exclusions(excluded: Counter) -> str:
    if not excluded:
        return "none"
    return ", ".join(f"{reason}={count}" for reason, count in excluded.most_common())
