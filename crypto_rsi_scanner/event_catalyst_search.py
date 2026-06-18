"""Offline catalyst-search scaffolding for market-anomaly research rows.

This module does not fetch search results or create alerts. It only generates
review queries and attaches externally supplied source events to a market
anomaly so the normal discovery/resolver/classifier pipeline can validate them.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from typing import Any, Iterable, Mapping

from .event_models import RawDiscoveredEvent

QUERY_TEMPLATES = (
    "{symbol} crypto why up",
    "{symbol} Binance listing",
    "{symbol} perp listing",
    "{symbol} token unlock",
    "{symbol} airdrop",
    "{symbol} OpenAI exposure",
    "{symbol} SpaceX exposure",
    "{symbol} exploit",
    "{symbol} DWF Labs",
)


def generate_search_queries_for_anomaly(raw_market_anomaly_event: RawDiscoveredEvent) -> tuple[str, ...]:
    """Return deterministic review queries for a market-anomaly raw event."""
    symbol = _event_symbol(raw_market_anomaly_event)
    if not symbol:
        return ()
    return tuple(template.format(symbol=symbol) for template in QUERY_TEMPLATES)


def attach_search_results_to_anomaly(
    raw_event: RawDiscoveredEvent,
    result_events: Iterable[RawDiscoveredEvent],
) -> tuple[RawDiscoveredEvent, ...]:
    """Attach manually supplied source events to an anomaly with provenance.

    The returned rows are still raw event evidence. They must pass normal
    normalization, asset resolution, classification, and playbook tiering before
    they can become research alerts.
    """
    queries = generate_search_queries_for_anomaly(raw_event)
    annotated_parent = _annotate_raw_event(
        raw_event,
        {
            "market_anomaly_catalyst_search": {
                "role": "parent_anomaly",
                "queries": list(queries),
                "research_only": True,
                "live_fetch": False,
            }
        },
    )
    parent_ref = {
        "raw_id": raw_event.raw_id,
        "provider": raw_event.provider,
        "title": raw_event.title,
        "symbol": _event_symbol(raw_event),
    }
    attached = [
        _annotate_raw_event(
            event,
            {
                "market_anomaly_catalyst_search": {
                    "role": "attached_source_evidence",
                    "parent": parent_ref,
                    "queries": list(queries),
                    "research_only": True,
                    "live_fetch": False,
                }
            },
        )
        for event in result_events
    ]
    return (annotated_parent, *attached)


def _annotate_raw_event(raw: RawDiscoveredEvent, extra: Mapping[str, Any]) -> RawDiscoveredEvent:
    payload = dict(raw.raw_json or {})
    payload.update(extra)
    return replace(raw, raw_json=payload, content_hash=_content_hash(payload))


def _event_symbol(raw: RawDiscoveredEvent) -> str:
    payload = raw.raw_json if isinstance(raw.raw_json, dict) else {}
    market = payload.get("market") if isinstance(payload.get("market"), dict) else {}
    asset = payload.get("asset") if isinstance(payload.get("asset"), dict) else {}
    candidates = (
        market.get("symbol"),
        asset.get("symbol"),
        payload.get("symbol"),
    )
    for value in candidates:
        symbol = str(value or "").strip().upper()
        if symbol:
            return symbol
    title = raw.title.strip().split()
    if title:
        token = title[0].strip("():,").upper()
        if token and len(token) <= 12:
            return token
    return ""


def _content_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
