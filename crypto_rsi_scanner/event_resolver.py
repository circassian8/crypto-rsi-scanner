"""Resolve normalized events to crypto assets without ticker-only guessing."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Iterable

from .event_models import DiscoveredAsset, EventAssetLink, NormalizedEvent

GENERIC_ASSET_TERMS = {
    "bill",
    "cash",
    "real",
    "just",
    "humanity",
}

COMMON_ENTITY_TERMS = {
    "open",
    "time",
    "magic",
    "mode",
    "base",
    "line",
    "world",
    "hype",
    "beat",
    "prime",
    "usa",
    "rain",
    "near",
    "ripple",
}

SOURCE_PUBLISHER_NAMES = {
    "bitcoin news",
    "bitcoin world",
    "coindesk",
    "coin desk",
    "crypto briefing",
    "the block",
    "cointelegraph",
    "coin telegraph",
    "decrypt",
    "beincrypto",
    "blockworks",
    "cryptoslate",
    "cryptonews.net",
    "cryptorank",
    "crypto economy",
    "the cryptonomist",
    "thedefiant",
    "thedefiant.io",
    "banklesstimes",
    "youhodler",
    "sekbernews.id",
    "investing.com",
    "tradingview",
    "yahoo finance",
    "coinmarketcap",
    "kucoin",
    "binance",
    "bybit",
    "okx",
}

MARKET_RECAP_PATTERNS = (
    "market recap",
    "weekly recap",
    "daily recap",
    "top stories",
    "market update",
    "performance update",
    "coin desk 20",
    "coindesk 20",
    "price analysis",
    "markets today",
)

DIRECT_EXTERNAL_ASSET_EVENT_TYPES = {
    "etf_approval",
    "etf_launch",
    "token_unlock",
    "exchange_listing",
    "perp_listing",
    "airdrop",
    "tge",
    "mainnet_launch",
    "governance",
    "protocol_upgrade",
}


def clean_text(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", " ", text.casefold()).strip()


def strip_publisher_suffix(value: object) -> str:
    """Remove common news-site suffixes so publisher names cannot resolve assets."""
    text = str(value or "").strip()
    if not text:
        return ""
    parts = re.split(r"\s+(?:[-–—|:]{1,2})\s+", text)
    if len(parts) < 2:
        return text
    tail = clean_text(parts[-1])
    if tail in SOURCE_PUBLISHER_NAMES:
        return " - ".join(parts[:-1]).strip()
    return text


def is_market_recap_event(event: NormalizedEvent) -> bool:
    text = clean_text(f"{strip_publisher_suffix(event.event_name)} {event.description or ''}")
    return any(pattern in text for pattern in MARKET_RECAP_PATTERNS)


def load_asset_aliases(path: str | Path | None) -> list[DiscoveredAsset]:
    if not path:
        return []
    p = Path(path).expanduser()
    if not p.exists():
        return []
    raw = json.loads(p.read_text(encoding="utf-8"))
    entries = raw.get("assets", raw) if isinstance(raw, dict) else raw
    if not isinstance(entries, list):
        raise ValueError("asset alias fixture must be a list or {'assets': [...]}")
    out: list[DiscoveredAsset] = []
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError("asset alias entries must be objects")
        out.append(DiscoveredAsset(
            coin_id=str(item.get("coin_id") or ""),
            symbol=str(item.get("symbol") or "").upper(),
            name=str(item.get("name") or ""),
            market_cap=item.get("market_cap"),
            volume_24h=item.get("volume_24h"),
            price=item.get("price"),
            categories=tuple(item.get("categories") or ()),
            contract_addresses=dict(item.get("contract_addresses") or {}),
            source=str(item.get("source") or "manual_alias"),
            aliases=tuple(str(a) for a in item.get("aliases") or ()),
        ))
    return out


def resolve_event_assets(
    event: NormalizedEvent,
    assets: Iterable[DiscoveredAsset],
    *,
    min_confidence: float = 0.80,
) -> list[EventAssetLink]:
    title = strip_publisher_suffix(event.event_name)
    description = strip_publisher_suffix(event.description or "")
    text = clean_text(" ".join([
        title,
        description,
    ]))
    assets_list = list(assets)
    symbol_counts = _symbol_counts(assets_list)
    links: list[EventAssetLink] = []
    for asset in assets_list:
        confidence, reason, evidence = _score_asset_match(event, text, asset, symbol_counts)
        if confidence >= min_confidence:
            links.append(EventAssetLink(
                event_id=event.event_id,
                coin_id=asset.coin_id,
                symbol=asset.symbol,
                name=asset.name,
                link_confidence=confidence,
                match_reason=reason,
                evidence=tuple(evidence),
            ))
    return sorted(links, key=lambda link: (-link.link_confidence, link.symbol))


def _symbol_counts(assets: Iterable[DiscoveredAsset]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for asset in assets:
        key = asset.symbol.upper()
        counts[key] = counts.get(key, 0) + 1
    return counts


def _score_asset_match(
    event: NormalizedEvent,
    text: str,
    asset: DiscoveredAsset,
    symbol_counts: dict[str, int],
) -> tuple[float, str, list[str]]:
    evidence: list[str] = []
    payload_text = text
    if _external_asset_can_identify_direct_asset(event):
        payload_text = clean_text(f"{payload_text} {event.external_asset or ''}")
    coin_id = clean_text(asset.coin_id)
    if coin_id and _direct_name_match_allowed(coin_id, payload_text) and _phrase_in_text(coin_id, payload_text):
        evidence.append(asset.coin_id)
        return _recap_adjusted(event, 1.00, "coin_id"), "coin_id", evidence

    for chain, address in asset.contract_addresses.items():
        if address and clean_text(address) in payload_text:
            evidence.append(f"{chain}:{address}")
            return 1.00, "contract_address", evidence

    alias_hits = [
        alias for alias in asset.aliases
        if (
            len(clean_text(alias)) >= 4
            and _direct_name_match_allowed(alias, payload_text)
            and _phrase_in_text(alias, payload_text)
        )
    ]
    if alias_hits:
        return _recap_adjusted(event, 0.95, "known_alias"), "known_alias", alias_hits[:3]

    name = clean_text(asset.name)
    symbol = asset.symbol.upper()
    symbol_hit = _symbol_in_text(symbol, strip_publisher_suffix(event.event_name)) or _symbol_in_text(
        symbol,
        strip_publisher_suffix(event.description or ""),
    )
    if name and len(name) >= 4 and _direct_name_match_allowed(name, payload_text) and _phrase_in_text(name, payload_text):
        evidence.append(asset.name)
        if symbol_hit:
            evidence.append(symbol)
            return _recap_adjusted(event, 0.90, "name_and_symbol"), "name_and_symbol", evidence
        return _recap_adjusted(event, 0.85, "name"), "name", evidence

    if symbol_hit and symbol_counts.get(symbol, 0) == 1 and _strong_symbol_context(symbol, event):
        return _recap_adjusted(event, 0.80, "ticker_explicit_context"), "ticker_explicit_context", [symbol]

    return 0.0, "no_match", []


def _external_asset_can_identify_direct_asset(event: NormalizedEvent) -> bool:
    """Use external_asset for direct events, but not proxy-event asset discovery."""
    return bool(event.external_asset) and event.event_type in DIRECT_EXTERNAL_ASSET_EVENT_TYPES


def _phrase_in_text(phrase: str, text: str) -> bool:
    cleaned = clean_text(phrase)
    if not cleaned:
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(cleaned)}(?![a-z0-9])", text) is not None


def _is_generic_asset_term(value: object) -> bool:
    return clean_text(value) in GENERIC_ASSET_TERMS or clean_text(value) in COMMON_ENTITY_TERMS


def _direct_name_match_allowed(value: object, text: str) -> bool:
    cleaned = clean_text(value)
    if not cleaned:
        return False
    if cleaned not in SOURCE_PUBLISHER_NAMES and not _is_generic_asset_term(cleaned):
        return True
    return _tight_asset_context(cleaned, text)


def _symbol_in_text(symbol: str, text: str) -> bool:
    if not symbol:
        return False
    return re.search(rf"(?<![A-Za-z0-9])\$?{re.escape(symbol)}(?![A-Za-z0-9])", str(text or "")) is not None


def _strong_symbol_context(symbol: str, event: NormalizedEvent) -> bool:
    raw_title = strip_publisher_suffix(event.event_name)
    raw_text = f"{raw_title} {event.description or ''}"
    haystack = clean_text(raw_text)
    if _explicit_symbol_reference(symbol, raw_text):
        return True
    symbol_text = clean_text(symbol)
    if symbol_text in COMMON_ENTITY_TERMS or len(symbol_text) <= 4:
        return _tight_asset_context(symbol_text, haystack)
    context_words = ("token", "coin", "crypto", "listing", "unlock", "airdrop", "perp", "perpetual", "futures")
    return _phrase_in_text(symbol, haystack) and any(word in haystack for word in context_words)


def _explicit_symbol_reference(symbol: str, text: str) -> bool:
    sym = re.escape(symbol.upper())
    raw = str(text or "")
    return (
        re.search(rf"(?<![A-Za-z0-9])\${sym}(?![A-Za-z0-9])", raw, re.IGNORECASE) is not None
        or re.search(rf"(?<![A-Za-z0-9]){sym}\s*[/_-]\s*(?:USDT|USD|USDC|BTC|ETH)(?![A-Za-z0-9])", raw, re.IGNORECASE) is not None
        or re.search(rf"(?<![A-Za-z0-9]){sym}(?:USDT|USD|USDC|BTC|ETH)(?![A-Za-z0-9])", raw, re.IGNORECASE) is not None
    )


def _tight_asset_context(term: str, text: str) -> bool:
    cleaned = clean_text(term)
    if not cleaned:
        return False
    return re.search(
        rf"(?<![a-z0-9]){re.escape(cleaned)}\s+(?:token|coin|perp|perpetual|futures?|listing)(?![a-z0-9])",
        text,
    ) is not None


def _recap_adjusted(event: NormalizedEvent, confidence: float, reason: str) -> float:
    if not is_market_recap_event(event):
        return confidence
    if reason == "contract_address":
        return confidence
    return min(confidence, 0.75)
