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


def clean_text(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", " ", text.casefold()).strip()


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
    text = clean_text(" ".join([
        event.event_name,
        event.description or "",
        event.external_asset or "",
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
    coin_id = clean_text(asset.coin_id)
    if coin_id and not _is_generic_asset_term(coin_id) and _phrase_in_text(coin_id, payload_text):
        evidence.append(asset.coin_id)
        return 1.00, "coin_id", evidence

    for chain, address in asset.contract_addresses.items():
        if address and clean_text(address) in payload_text:
            evidence.append(f"{chain}:{address}")
            return 1.00, "contract_address", evidence

    alias_hits = [
        alias for alias in asset.aliases
        if (
            len(clean_text(alias)) >= 4
            and not _is_generic_asset_term(alias)
            and _phrase_in_text(alias, payload_text)
        )
    ]
    if alias_hits:
        return 0.95, "known_alias", alias_hits[:3]

    name = clean_text(asset.name)
    symbol = asset.symbol.upper()
    symbol_hit = _symbol_in_text(symbol, event.event_name) or _symbol_in_text(symbol, event.description or "")
    if name and len(name) >= 4 and not _is_generic_asset_term(name) and _phrase_in_text(name, payload_text):
        evidence.append(asset.name)
        if symbol_hit:
            evidence.append(symbol)
            return 0.90, "name_and_symbol", evidence
        return 0.85, "name", evidence

    if symbol_hit and symbol_counts.get(symbol, 0) == 1 and _strong_symbol_context(symbol, event):
        return 0.70, "ticker_only_unique", [symbol]

    return 0.0, "no_match", []


def _phrase_in_text(phrase: str, text: str) -> bool:
    cleaned = clean_text(phrase)
    if not cleaned:
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(cleaned)}(?![a-z0-9])", text) is not None


def _is_generic_asset_term(value: object) -> bool:
    return clean_text(value) in GENERIC_ASSET_TERMS


def _symbol_in_text(symbol: str, text: str) -> bool:
    if not symbol:
        return False
    return re.search(rf"(?<![A-Za-z0-9])\$?{re.escape(symbol)}(?![A-Za-z0-9])", str(text or "")) is not None


def _strong_symbol_context(symbol: str, event: NormalizedEvent) -> bool:
    haystack = clean_text(f"{event.event_name} {event.description or ''}")
    context_words = ("token", "coin", "crypto", "listing", "unlock", "airdrop", "perp", "futures")
    return _phrase_in_text(symbol, haystack) and any(word in haystack for word in context_words)
