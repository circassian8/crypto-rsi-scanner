"""Rule-based proxy/direct classification for event-fade discovery."""

from __future__ import annotations

from .event_models import DiscoveredAsset, EventAssetLink, EventClassification, NormalizedEvent
from .event_resolver import clean_text


CLASSIFIER_VERSION = "rules_v2"

PROXY_KEYWORDS = (
    "exposure to",
    "synthetic exposure",
    "pre-ipo",
    "pre ipo",
    "tokenized stock",
    "stock token",
    "trade spacex",
    "trade openai",
    "trade anthropic",
    "prediction market",
    "fan token",
    "world cup",
    "election",
    "inauguration",
    "celebrity",
)

DIRECT_TYPES = {
    "token_unlock",
    "exchange_listing",
    "perp_listing",
    "airdrop",
    "tge",
    "mainnet_launch",
    "governance",
    "protocol_upgrade",
    "etf_approval",
    "etf_launch",
}

DIRECT_KEYWORDS = (
    "etf approval",
    "spot etf",
    "exchange listing",
    "binance listing",
    "bybit listing",
    "token unlock",
    "airdrop",
    "tge",
    "mainnet",
    "protocol upgrade",
)


def classify_event_asset(
    event: NormalizedEvent,
    asset: DiscoveredAsset,
    link: EventAssetLink,
) -> EventClassification:
    text = clean_text(" ".join([
        event.event_name,
        event.description or "",
        event.external_asset or "",
        asset.name,
        asset.symbol,
    ]))
    evidence: list[str] = []

    if event.event_type in DIRECT_TYPES or any(keyword in text for keyword in DIRECT_KEYWORDS):
        evidence.append(event.event_type)
        return EventClassification(
            event_id=event.event_id,
            coin_id=asset.coin_id,
            is_proxy_narrative=False,
            is_direct_beneficiary=True,
            relationship_type=_direct_relationship(event.event_type, text),
            confidence=min(1.0, max(0.80, event.confidence, link.link_confidence)),
            classifier_version=CLASSIFIER_VERSION,
            reason="Event directly affects the linked token/listing/supply/protocol.",
            evidence=tuple(evidence + list(link.evidence)),
        )

    proxy_hits = [keyword for keyword in PROXY_KEYWORDS if keyword in text]
    external = clean_text(event.external_asset)
    asset_text = clean_text(f"{asset.name} {asset.symbol} {asset.coin_id}")
    if external and external not in asset_text and proxy_hits:
        has_event_time = event.event_time is not None
        return EventClassification(
            event_id=event.event_id,
            coin_id=asset.coin_id,
            is_proxy_narrative=True,
            is_direct_beneficiary=False,
            relationship_type="proxy_exposure" if has_event_time else "proxy_attention",
            confidence=(
                min(1.0, max(0.80, event.confidence, link.link_confidence))
                if has_event_time
                else min(0.85, max(0.70, event.confidence, link.link_confidence))
            ),
            classifier_version=CLASSIFIER_VERSION,
            reason=(
                "Linked asset appears to be a temporary proxy for an external dated catalyst."
                if has_event_time
                else "Linked asset appears to be proxy-narrative evidence, but event time is missing."
            ),
            evidence=tuple(proxy_hits[:3] + list(link.evidence)),
        )

    if event.event_type in {"ipo_proxy", "external_proxy_event", "sports_event", "political_event"}:
        if external and external not in asset_text and event.event_time is not None:
            return EventClassification(
                event_id=event.event_id,
                coin_id=asset.coin_id,
                is_proxy_narrative=True,
                is_direct_beneficiary=False,
                relationship_type="proxy_attention",
                confidence=min(0.90, max(0.75, event.confidence, link.link_confidence)),
                classifier_version=CLASSIFIER_VERSION,
                reason="Event type and external asset indicate proxy attention, but keyword evidence is limited.",
                evidence=tuple(list(link.evidence) + [event.event_type]),
            )

    return EventClassification(
        event_id=event.event_id,
        coin_id=asset.coin_id,
        is_proxy_narrative=False,
        is_direct_beneficiary=False,
        relationship_type="ambiguous",
        confidence=min(0.60, event.confidence, link.link_confidence),
        classifier_version=CLASSIFIER_VERSION,
        reason="Insufficient evidence for proxy or direct-beneficiary classification.",
        evidence=tuple(link.evidence),
    )


def _direct_relationship(event_type: str, text: str) -> str:
    if event_type:
        mapping = {
            "token_unlock": "direct_unlock",
            "exchange_listing": "direct_listing",
            "perp_listing": "direct_listing",
            "mainnet_launch": "direct_protocol_upgrade",
            "governance": "direct_protocol_upgrade",
            "protocol_upgrade": "direct_protocol_upgrade",
        }
        if event_type in mapping:
            return mapping[event_type]
    if "etf" in text:
        return "direct_token_event"
    return "direct_token_event"
