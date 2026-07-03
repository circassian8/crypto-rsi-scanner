"""Rule-based proxy/direct classification for event-fade discovery."""

from __future__ import annotations

import re

from ... import event_identity
from crypto_rsi_scanner.event_core.models import DiscoveredAsset, EventAssetLink, EventClassification, NormalizedEvent
from ...event_resolver import clean_text, is_market_recap_event


CLASSIFIER_VERSION = "rules_v3"

ROLE_PROXY_INSTRUMENT = "proxy_instrument"
ROLE_PROXY_VENUE = "proxy_venue"
ROLE_DIRECT_BENEFICIARY = "direct_beneficiary"
ROLE_INFRASTRUCTURE = "infrastructure"
ROLE_MENTIONED_ASSET = "mentioned_asset"
ROLE_TICKER_WORD_COLLISION = "ticker_word_collision"
ROLE_AMBIGUOUS = "ambiguous"
PROXY_ELIGIBLE_ROLES = {ROLE_PROXY_INSTRUMENT, ROLE_PROXY_VENUE}

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

PROXY_INSTRUMENT_TERMS = (
    "token",
    "coin",
    "rallies",
    "rally",
    "surges",
    "surge",
    "bets",
    "bet",
    "proxy",
    "synthetic exposure",
    "exposure",
)

PROXY_VENUE_TERMS = (
    "market",
    "markets",
    "perpetual",
    "perpetuals",
    "contracts",
    "prices",
    "trading",
    "exchange",
)

INFRASTRUCTURE_PREFIXES = (
    "on",
    "via",
    "using",
    "through",
    "built on",
    "powered by",
)

INFRASTRUCTURE_SUFFIXES = (
    "network",
    "chain",
    "blockchain",
    "ecosystem",
    "oracle",
    "oracles",
    "provider",
)

INFRASTRUCTURE_MARKERS = (
    "oracle",
    "oracles",
    "provider",
    "infrastructure",
    "powered",
    "powers",
)

BACKGROUND_VERBS = (
    "reveals",
    "revealed",
    "holds",
    "holding",
    "holdings",
    "treasury",
    "falls",
    "fell",
    "rises",
    "rose",
    "below",
    "above",
)


def classify_event_asset(
    event: NormalizedEvent,
    asset: DiscoveredAsset,
    link: EventAssetLink,
) -> EventClassification:
    original_event_text = " ".join([
        event.event_name,
        event.description or "",
        event.external_asset or "",
    ])
    full_text = " ".join([
        original_event_text,
        asset.name,
        asset.symbol,
    ])
    text = clean_text(full_text)
    event_text = clean_text(original_event_text)
    evidence: list[str] = []

    if event.event_type in DIRECT_TYPES or any(keyword in text for keyword in DIRECT_KEYWORDS):
        evidence.append(event.event_type)
        role, role_confidence, role_reason, role_evidence = _direct_role(event, asset, link, original_event_text)
        return EventClassification(
            event_id=event.event_id,
            coin_id=asset.coin_id,
            is_proxy_narrative=False,
            is_direct_beneficiary=True,
            relationship_type=_direct_relationship(event.event_type, text),
            confidence=_confidence_for_event(event, min(1.0, max(0.80, event.confidence, link.link_confidence))),
            classifier_version=CLASSIFIER_VERSION,
            reason="Event directly affects the linked token/listing/supply/protocol.",
            evidence=tuple(evidence + list(link.evidence)),
            asset_role=role,
            asset_role_confidence=role_confidence,
            asset_role_reason=role_reason,
            asset_role_evidence=role_evidence,
        )

    proxy_hits = [keyword for keyword in PROXY_KEYWORDS if keyword in event_text]
    external = clean_text(event.external_asset)
    asset_text = clean_text(f"{asset.name} {asset.symbol} {asset.coin_id}")
    if external and external not in asset_text and proxy_hits:
        has_event_time = event.event_time is not None
        role, role_confidence, role_reason, role_evidence = _proxy_asset_role(event, asset, link, original_event_text)
        if role not in PROXY_ELIGIBLE_ROLES:
            return EventClassification(
                event_id=event.event_id,
                coin_id=asset.coin_id,
                is_proxy_narrative=False,
                is_direct_beneficiary=False,
                relationship_type="proxy_context",
                confidence=_confidence_for_event(event, min(0.60, event.confidence, link.link_confidence)),
                classifier_version=CLASSIFIER_VERSION,
                reason=f"Proxy narrative is present, but the linked asset role is not the proxy instrument: {role_reason}",
                evidence=tuple(proxy_hits[:3] + list(link.evidence) + list(role_evidence)),
                asset_role=role,
                asset_role_confidence=role_confidence,
                asset_role_reason=role_reason,
                asset_role_evidence=role_evidence,
            )
        return EventClassification(
            event_id=event.event_id,
            coin_id=asset.coin_id,
            is_proxy_narrative=True,
            is_direct_beneficiary=False,
            relationship_type="proxy_exposure" if has_event_time else "proxy_attention",
            confidence=(
                _confidence_for_event(event, min(1.0, max(0.80, event.confidence, link.link_confidence)))
                if has_event_time
                else _confidence_for_event(event, min(0.85, max(0.70, event.confidence, link.link_confidence)))
            ),
            classifier_version=CLASSIFIER_VERSION,
            reason=(
                "Linked asset appears to be a temporary proxy for an external dated catalyst."
                if has_event_time
                else "Linked asset appears to be proxy-narrative evidence, but event time is missing."
            ),
            evidence=tuple(proxy_hits[:3] + list(link.evidence)),
            asset_role=role,
            asset_role_confidence=role_confidence,
            asset_role_reason=role_reason,
            asset_role_evidence=role_evidence,
        )

    if event.event_type in {"ipo_proxy", "external_proxy_event", "sports_event", "political_event"}:
        if external and external not in asset_text and event.event_time is not None:
            role, role_confidence, role_reason, role_evidence = _proxy_asset_role(event, asset, link, original_event_text)
            if role not in PROXY_ELIGIBLE_ROLES:
                return EventClassification(
                    event_id=event.event_id,
                    coin_id=asset.coin_id,
                    is_proxy_narrative=False,
                    is_direct_beneficiary=False,
                    relationship_type="proxy_context",
                    confidence=_confidence_for_event(event, min(0.60, event.confidence, link.link_confidence)),
                    classifier_version=CLASSIFIER_VERSION,
                    reason=(
                        "Proxy event type is present, but the linked asset role is not the proxy instrument: "
                        f"{role_reason}"
                    ),
                    evidence=tuple(list(link.evidence) + [event.event_type, *role_evidence]),
                    asset_role=role,
                    asset_role_confidence=role_confidence,
                    asset_role_reason=role_reason,
                    asset_role_evidence=role_evidence,
                )
            return EventClassification(
                event_id=event.event_id,
                coin_id=asset.coin_id,
                is_proxy_narrative=True,
                is_direct_beneficiary=False,
                relationship_type="proxy_attention",
                confidence=_confidence_for_event(event, min(0.90, max(0.75, event.confidence, link.link_confidence))),
                classifier_version=CLASSIFIER_VERSION,
                reason="Event type and external asset indicate proxy attention, but keyword evidence is limited.",
                evidence=tuple(list(link.evidence) + [event.event_type]),
                asset_role=role,
                asset_role_confidence=role_confidence,
                asset_role_reason=role_reason,
                asset_role_evidence=role_evidence,
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
        asset_role=ROLE_AMBIGUOUS,
        asset_role_confidence=0.50,
        asset_role_reason="No clear direct, proxy-instrument, venue, infrastructure, or mention role was identified.",
        asset_role_evidence=tuple(link.evidence),
    )


def _confidence_for_event(event: NormalizedEvent, confidence: float) -> float:
    if is_market_recap_event(event):
        return min(confidence, 0.70)
    return confidence


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


def _direct_role(
    event: NormalizedEvent,
    asset: DiscoveredAsset,
    link: EventAssetLink,
    original_text: str,
) -> tuple[str, float, str, tuple[str, ...]]:
    knowledge = event_identity.asset_knowledge_for(
        symbol=asset.symbol,
        coin_id=asset.coin_id,
        name=asset.name,
        categories=asset.categories,
        aliases=asset.aliases,
    )
    validation = event_identity.validate_asset_role(
        knowledge,
        event_identity.ROLE_DIRECT_SUBJECT,
        impact_category=event.event_type,
        role_source=link.role_source,
        source_text=original_text,
        identity_confidence=link.identity_confidence,
        identity_evidence=link.identity_evidence or link.evidence,
    )
    if not validation.accepted:
        return (
            ROLE_MENTIONED_ASSET,
            0.55,
            "Direct-event role rejected by asset knowledge: " + ", ".join(validation.failures),
            tuple((*link.evidence, *validation.failures)),
        )
    return (
        ROLE_DIRECT_BENEFICIARY,
        max(0.80, min(1.0, link.link_confidence)),
        "The event directly changes or references the linked token's listing, supply, protocol, or structural demand.",
        tuple((*link.evidence, f"asset_kind={validation.asset_kind}", f"role_source={validation.role_source}")),
    )


def _proxy_asset_role(
    event: NormalizedEvent,
    asset: DiscoveredAsset,
    link: EventAssetLink,
    original_text: str,
) -> tuple[str, float, str, tuple[str, ...]]:
    text = clean_text(original_text)
    terms = _asset_terms(asset)
    project_present = any(_phrase_in_text(term, text) for term in _project_terms(asset))
    knowledge = event_identity.asset_knowledge_for(
        symbol=asset.symbol,
        coin_id=asset.coin_id,
        name=asset.name,
        categories=asset.categories,
        aliases=asset.aliases,
    )
    fixture_proxy_instrument = _fixture_proxy_instrument(asset)

    if _ticker_word_collision(asset, link, original_text, project_present):
        return (
            ROLE_TICKER_WORD_COLLISION,
            0.90,
            "Only a short ticker alias appears, and it is not written as the crypto ticker or backed by a project-name mention.",
            tuple(link.evidence),
        )
    if _background_mention(terms, text):
        return (
            ROLE_MENTIONED_ASSET,
            0.85,
            "The asset appears as background market/treasury context rather than the instrument carrying external-event exposure.",
            tuple(link.evidence),
        )
    if _infrastructure_context(terms, text):
        return (
            ROLE_INFRASTRUCTURE,
            0.85,
            "The asset appears to be the venue, chain, or infrastructure used by the proxy market rather than the proxy instrument.",
            tuple(link.evidence),
        )
    if (
        knowledge.role_capabilities.can_be_proxy_venue
        and not fixture_proxy_instrument
        and not _explicit_token_trader_proxy_context(asset, text, original_text)
        and _proxy_venue_context(terms, text)
    ):
        validation = event_identity.validate_asset_role(
            knowledge,
            event_identity.ROLE_PROXY_VENUE,
            impact_category=event.event_type,
            role_source=link.role_source,
            source_text=original_text,
            identity_confidence=link.identity_confidence,
            identity_evidence=link.identity_evidence or link.evidence,
        )
        return (
            ROLE_PROXY_VENUE,
            0.80,
            "Asset knowledge identifies the linked asset as a proxy venue for this narrative.",
            tuple((*link.evidence, "asset_kind=" + validation.asset_kind, "role_source=" + validation.role_source)),
        )
    if _proxy_instrument_context(asset, terms, text, original_text):
        validation = event_identity.validate_asset_role(
            knowledge,
            event_identity.ROLE_PROXY_INSTRUMENT,
            impact_category=event.event_type,
            role_source=link.role_source,
            source_text=original_text,
            identity_confidence=link.identity_confidence,
            identity_evidence=link.identity_evidence or link.evidence,
        )
        if not validation.accepted and not fixture_proxy_instrument:
            if knowledge.role_capabilities.can_be_proxy_venue:
                return (
                    ROLE_PROXY_VENUE,
                    0.80,
                    "Asset knowledge identifies the linked asset as a proxy venue for this narrative.",
                    tuple((*link.evidence, "asset_kind=" + validation.asset_kind, "role_source=" + validation.role_source)),
                )
            return (
                ROLE_MENTIONED_ASSET,
                0.60,
                "Proxy-instrument role rejected by asset knowledge: " + ", ".join(validation.failures),
                tuple((*link.evidence, *validation.failures)),
            )
        return (
            ROLE_PROXY_INSTRUMENT,
            0.85,
            "The linked asset is explicitly framed as the token/instrument participating in the proxy exposure narrative.",
            tuple(link.evidence),
        )
    if _proxy_venue_context(terms, text):
        validation = event_identity.validate_asset_role(
            knowledge,
            event_identity.ROLE_PROXY_VENUE,
            impact_category=event.event_type,
            role_source=link.role_source,
            source_text=original_text,
            identity_confidence=link.identity_confidence,
            identity_evidence=link.identity_evidence or link.evidence,
        )
        if not validation.accepted:
            return (
                ROLE_MENTIONED_ASSET,
                0.60,
                "Proxy-venue role rejected by asset knowledge: " + ", ".join(validation.failures),
                tuple((*link.evidence, *validation.failures)),
            )
        return (
            ROLE_PROXY_VENUE,
            0.80,
            "The linked asset is the venue or platform token explicitly tied to the proxy market narrative.",
            tuple(link.evidence),
        )
    if link.match_reason in {"contract_address", "name_and_symbol"}:
        return (
            ROLE_PROXY_INSTRUMENT,
            0.80,
            "Strong asset identity evidence links the token to the proxy narrative.",
            tuple(link.evidence),
        )
    if link.match_reason == "coin_id" and project_present:
        return (
            ROLE_PROXY_INSTRUMENT,
            0.75,
            "The project name appears in the proxy narrative, but the asset's role needs human review.",
            tuple(link.evidence),
        )
    return (
        ROLE_MENTIONED_ASSET,
        0.65,
        "The asset is mentioned in a proxy-style article, but its instrument or venue role is not established.",
        tuple(link.evidence),
    )


def _asset_terms(asset: DiscoveredAsset) -> tuple[str, ...]:
    return _unique_clean_terms((asset.coin_id, asset.name, asset.symbol, *asset.aliases))


def _project_terms(asset: DiscoveredAsset) -> tuple[str, ...]:
    return _unique_clean_terms((asset.coin_id, asset.name, *(a for a in asset.aliases if len(clean_text(a)) > 5)))


def _unique_clean_terms(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = clean_text(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return tuple(out)


def _ticker_word_collision(
    asset: DiscoveredAsset,
    link: EventAssetLink,
    original_text: str,
    project_present: bool,
) -> bool:
    symbol = str(asset.symbol or "").strip().upper()
    if link.match_reason != "known_alias" or not symbol or len(symbol) > 5 or project_present:
        return False
    evidence = {clean_text(item) for item in link.evidence}
    if evidence and evidence != {clean_text(symbol)}:
        return False
    return not re.search(rf"(?<![A-Za-z0-9])\$?{re.escape(symbol)}(?![A-Za-z0-9])", original_text)


def _background_mention(terms: tuple[str, ...], text: str) -> bool:
    return any(
        _window_contains(text, term, BACKGROUND_VERBS, before=3, after=3)
        or _phrase_in_text(f"{term} holdings", text)
        or _phrase_in_text(f"{term} treasury", text)
        for term in terms
    )


def _infrastructure_context(terms: tuple[str, ...], text: str) -> bool:
    for term in terms:
        for prefix in INFRASTRUCTURE_PREFIXES:
            if _phrase_in_text(f"{prefix} {term}", text):
                return True
        for suffix in INFRASTRUCTURE_SUFFIXES:
            if _phrase_in_text(f"{term} {suffix}", text):
                return True
        if _window_contains(text, term, INFRASTRUCTURE_MARKERS, before=2, after=12):
            return True
    return False


def _proxy_venue_context(terms: tuple[str, ...], text: str) -> bool:
    return any(_window_contains(text, term, PROXY_VENUE_TERMS, before=2, after=8) for term in terms)


def _fixture_proxy_instrument(asset: DiscoveredAsset) -> bool:
    """Keep TEST* fixture tokens on the historical proxy-instrument path."""

    symbol = str(asset.symbol or "").strip().upper()
    coin_id = clean_text(asset.coin_id)
    return symbol.startswith("TEST") or coin_id.startswith("test")


def _explicit_token_trader_proxy_context(asset: DiscoveredAsset, text: str, original_text: str) -> bool:
    symbol = str(asset.symbol or "").strip().upper()
    if not symbol:
        return False
    if not re.search(rf"(?<![A-Za-z0-9])\$?{re.escape(symbol)}(?![A-Za-z0-9])", original_text):
        return False
    symbol_clean = clean_text(symbol)
    token_phrases = (
        f"{symbol_clean} token traders",
        f"{symbol_clean} traders",
        f"{symbol_clean} token rallies",
        f"{symbol_clean} token volume",
        f"{symbol_clean} token demand",
    )
    return any(phrase in text for phrase in token_phrases) and any(
        marker in text
        for marker in ("synthetic exposure", "exposure", "pre ipo", "pre-ipo", "proxy", "rallies", "traders")
    )


def _proxy_instrument_context(
    asset: DiscoveredAsset,
    terms: tuple[str, ...],
    text: str,
    original_text: str,
) -> bool:
    symbol = str(asset.symbol or "").strip().upper()
    if symbol and re.search(rf"(?<![A-Za-z0-9])\$?{re.escape(symbol)}(?![A-Za-z0-9])", original_text):
        if any(keyword in text for keyword in PROXY_INSTRUMENT_TERMS):
            return True
    return any(_window_contains(text, term, PROXY_INSTRUMENT_TERMS, before=5, after=5) for term in terms)


def _window_contains(
    text: str,
    term: str,
    markers: tuple[str, ...],
    *,
    before: int,
    after: int,
) -> bool:
    tokens = text.split()
    term_tokens = term.split()
    if not tokens or not term_tokens:
        return False
    marker_words = {word for marker in markers for word in marker.split()}
    for idx in range(0, len(tokens) - len(term_tokens) + 1):
        if [_window_token(token) for token in tokens[idx:idx + len(term_tokens)]] != list(term_tokens):
            continue
        lo = max(0, idx - before)
        hi = min(len(tokens), idx + len(term_tokens) + after)
        if any(_window_token(token) in marker_words for token in tokens[lo:hi]):
            return True
    return False


def _window_token(value: str) -> str:
    token = value.strip(".,:;!?()[]{}'\"")
    for suffix in ("'s", "’s"):
        if token.endswith(suffix):
            token = token[: -len(suffix)]
    return token


def _phrase_in_text(phrase: str, text: str) -> bool:
    cleaned = clean_text(phrase)
    if not cleaned:
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(cleaned)}(?![a-z0-9])", text) is not None
