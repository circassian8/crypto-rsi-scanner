"""Universe hygiene filters.

CoinGecko's market-cap list can include stablecoins, wrapped/staked receipts,
synthetics, stale listings, and very low-liquidity assets. Those entries pollute
live alerts, outcomes, paper trades, and backtests, so keep the screening logic
pure and shared by the live scanner and research paths.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import re
import unicodedata
from pathlib import Path

from . import config


_STABLE_SYMBOLS = {
    "usd", "usdt", "usdc", "dai", "usde", "fdusd", "tusd", "usdd", "pyusd",
    "usds", "busd", "gusd", "frax", "lusd", "usd0", "usdb", "crvusd",
    "usdx", "susd", "eusd", "usdp", "usdy", "usdl", "rlusd", "usd1",
    "usdg", "usdtb", "gho", "ylds", "usx", "usyc", "xaut", "paxg",
}

_STABLE_NAME_RE = re.compile(
    r"\b(stablecoin|stable coin|stables?|tether|usd[a-z0-9]*|u\.s\. dollar|dollars?|dai|frax)\b"
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
        symbol.startswith("usd")
        or symbol.endswith("usd")
        or "usd" in joined
        or "dollar" in name
        or "stable" in name
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


def _market_summary(market: dict, reason: str | None = None) -> dict:
    market_cap = _as_float(market.get("market_cap"))
    volume = _as_float(market.get("total_volume"))
    summary = {
        "rank": market.get("market_cap_rank"),
        "id": market.get("id"),
        "symbol": market.get("symbol"),
        "name": market.get("name"),
        "market_cap": market_cap,
        "total_volume": volume,
        "volume_to_mcap": (volume / market_cap if market_cap and market_cap > 0 and volume is not None else None),
        "pct_24h": _as_float(
            market.get("price_change_percentage_24h_in_currency")
            if market.get("price_change_percentage_24h_in_currency") is not None
            else market.get("price_change_percentage_24h")
        ),
    }
    if reason:
        summary["reason"] = reason
    return summary


def filter_markets_with_audit(
    markets: list[dict],
    limit: int | None = None,
    *,
    now: datetime | None = None,
    max_examples: int = 80,
) -> tuple[list[dict], Counter, dict]:
    kept: list[dict] = []
    excluded: Counter = Counter()
    excluded_examples: list[dict] = []
    for market in markets:
        reason = exclusion_reason(market)
        if reason:
            excluded[reason] += 1
            if len(excluded_examples) < max_examples:
                excluded_examples.append(_market_summary(market, reason))
            continue
        if limit is None or len(kept) < limit:
            kept.append(market)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    audit = {
        "generated_at": now.astimezone(timezone.utc).isoformat(),
        "requested_limit": limit,
        "fetched_count": len(markets),
        "kept_count": len(kept),
        "excluded_count": int(sum(excluded.values())),
        "excluded_by_reason": dict(sorted(excluded.items())),
        "kept": [_market_summary(m) for m in kept[:max_examples]],
        "excluded_examples": excluded_examples,
    }
    return kept, excluded, audit


def filter_markets(markets: list[dict], limit: int | None = None) -> tuple[list[dict], Counter]:
    kept, excluded, _ = filter_markets_with_audit(markets, limit=limit)
    return kept, excluded


def format_exclusions(excluded: Counter) -> str:
    if not excluded:
        return "none"
    return ", ".join(f"{reason}={count}" for reason, count in excluded.most_common())


def write_audit(audit: dict, path: Path | None = None) -> Path:
    path = Path(path or config.UNIVERSE_AUDIT_OUT).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    return path


def format_audit(audit: dict) -> str:
    if not audit:
        return "No universe hygiene audit has been recorded yet."
    lines = [
        "UNIVERSE HYGIENE AUDIT",
        f"generated: {audit.get('generated_at', 'unknown')}",
        f"fetched: {audit.get('fetched_count', 0)} · kept: {audit.get('kept_count', 0)} · "
        f"excluded: {audit.get('excluded_count', 0)}",
        "excluded by reason: " + format_exclusions(Counter(audit.get("excluded_by_reason") or {})),
    ]
    examples = audit.get("excluded_examples") or []
    if examples:
        lines.append("examples:")
        for item in examples[:12]:
            lines.append(
                f"  {item.get('symbol', '?')} {item.get('name', '?')} "
                f"rank={item.get('rank', '?')} reason={item.get('reason')}"
            )
    return "\n".join(lines)
