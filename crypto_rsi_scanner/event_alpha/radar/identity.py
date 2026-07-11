"""Shared asset-identity matching for Event Alpha research paths."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse


COMMON_WORD_SYMBOLS = {
    "AI",
    "ALT",
    "API",
    "ARK",
    "ATOM",
    "BAN",
    "BAND",
    "BAT",
    "BIT",
    "BLUR",
    "BOND",
    "CASH",
    "CITY",
    "COW",
    "CREAM",
    "CROWN",
    "DASH",
    "DENT",
    "DODO",
    "DUSK",
    "FARM",
    "FEAR",
    "FIL",
    "FLUX",
    "FORTH",
    "GAS",
    "GODS",
    "HIGH",
    "HIVE",
    "HOOK",
    "HYPE",
    "ICE",
    "JASMY",
    "JOE",
    "JUST",
    "KEY",
    "LAYER",
    "MAGIC",
    "MASK",
    "MOBILE",
    "MOVE",
    "NEAR",
    "NMR",
    "OM",
    "ONE",
    "PEOPLE",
    "PRIME",
    "PROM",
    "PUMP",
    "RARE",
    "REAL",
    "ROSE",
    "SAFE",
    "SAND",
    "SPELL",
    "SUPER",
    "SUSHI",
    "TRUMP",
    "UMA",
    "USUAL",
    "WING",
}

STRENGTH_STRONG = "strong"
STRENGTH_WEAK = "weak"
STRENGTH_REJECTED = "rejected"
STRENGTH_NONE = "none"

ASSET_KIND_PROTOCOL_TOKEN = "protocol_token"
ASSET_KIND_VENUE_TOKEN = "venue_token"
ASSET_KIND_EXCHANGE_TOKEN = "exchange_token"
ASSET_KIND_FAN_TOKEN = "fan_token"
ASSET_KIND_MEME_TOKEN = "meme_token"
ASSET_KIND_INFRA_TOKEN = "infra_token"
ASSET_KIND_SYNTHETIC_ASSET = "synthetic_asset"
ASSET_KIND_TOKENIZED_EQUITY_VENUE = "tokenized_equity_venue"
ASSET_KIND_STABLECOIN = "stablecoin"
ASSET_KIND_WRAPPED_ASSET = "wrapped_asset"
ASSET_KIND_L1_ASSET = "l1_asset"
ASSET_KIND_UNKNOWN = "unknown"

ROLE_DIRECT_SUBJECT = "direct_subject"
ROLE_ECOSYSTEM_AFFECTED_ASSET = "ecosystem_affected_asset"
ROLE_PROXY_INSTRUMENT = "proxy_instrument"
ROLE_PROXY_VENUE = "proxy_venue"
ROLE_INFRASTRUCTURE_PROVIDER = "infrastructure_provider"
ROLE_ECOSYSTEM_BENEFICIARY = "ecosystem_beneficiary"
ROLE_COMPETITOR_BENEFICIARY = "competitor_beneficiary"
ROLE_MACRO_AFFECTED_ASSET = "macro_affected_asset"
ROLE_GENERIC_MENTION = "generic_mention"

ROLE_SOURCE_OFFICIAL_SOURCE = "official_source"
ROLE_SOURCE_RESOLVER_EXACT = "resolver_exact"
ROLE_SOURCE_TAXONOMY_CANDIDATE = "taxonomy_candidate"
ROLE_SOURCE_LLM_SUGGESTION = "llm_suggestion"
ROLE_SOURCE_MARKET_SYMBOL_ONLY = "market_symbol_only"
ROLE_SOURCE_CONTEXT_ONLY = "source_context_only"


@dataclass(frozen=True)
class AssetIdentity:
    symbol: str = ""
    coin_id: str | None = None
    project_name: str | None = None
    aliases: tuple[str, ...] = ()
    contract_addresses: tuple[str, ...] = ()
    is_common_word_symbol: bool = False
    identity_terms: tuple[str, ...] = ()

    @property
    def normalized_symbol(self) -> str:
        return str(self.symbol or "").strip().upper()

    @property
    def terms(self) -> tuple[str, ...]:
        values: list[str] = []
        for value in (
            self.coin_id,
            self.project_name,
            *(self.aliases or ()),
            *(self.identity_terms or ()),
        ):
            text = str(value or "").strip()
            if text:
                values.append(text)
        coin_id = str(self.coin_id or "").strip()
        if coin_id and "-" in coin_id:
            values.append(coin_id.replace("-", " "))
        return tuple(dict.fromkeys(values))


@dataclass(frozen=True)
class IdentityEvidence:
    strong_content: tuple[str, ...] = ()
    llm_quotes: tuple[str, ...] = ()
    url: str | None = None
    metadata: tuple[str, ...] = ()
    source_origin: tuple[str, ...] = ()


@dataclass(frozen=True)
class IdentityMatchResult:
    matched: bool
    strength: str
    reason: str | None
    evidence_field: str | None = None
    evidence_text: str | None = None


@dataclass(frozen=True)
class AssetRoleCapabilities:
    can_be_proxy_instrument: bool = False
    can_be_proxy_venue: bool = False
    can_be_direct_beneficiary: bool = True
    can_be_infrastructure: bool = False
    can_be_market_anomaly: bool = True

    def as_dict(self) -> dict[str, bool]:
        return {
            "can_be_proxy_instrument": self.can_be_proxy_instrument,
            "can_be_proxy_venue": self.can_be_proxy_venue,
            "can_be_direct_beneficiary": self.can_be_direct_beneficiary,
            "can_be_infrastructure": self.can_be_infrastructure,
            "can_be_market_anomaly": self.can_be_market_anomaly,
        }


@dataclass(frozen=True)
class AssetKnowledge:
    symbol: str
    coin_id: str
    official_name: str
    asset_kind: str = ASSET_KIND_UNKNOWN
    categories: tuple[str, ...] = ()
    sectors: tuple[str, ...] = ()
    official_domains: tuple[str, ...] = ()
    project_entities: tuple[str, ...] = ()
    exchange_pairs: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    excluded_aliases: tuple[str, ...] = ()
    ticker_collision_terms: tuple[str, ...] = ()
    known_proxy_relationships: tuple[str, ...] = ()
    broad_macro_asset: bool = False
    common_word_collision_risk: bool = False
    role_capabilities: AssetRoleCapabilities = field(default_factory=AssetRoleCapabilities)

    @property
    def normalized_symbol(self) -> str:
        return str(self.symbol or "").strip().upper()


@dataclass(frozen=True)
class AssetRoleValidation:
    accepted: bool
    final_role: str
    role_source: str
    identity_confidence: float
    identity_evidence: tuple[str, ...]
    collision_risk: str
    failures: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    asset_kind: str = ASSET_KIND_UNKNOWN
    role_capabilities: AssetRoleCapabilities = field(default_factory=AssetRoleCapabilities)


_DEFAULT_ASSET_KNOWLEDGE: tuple[AssetKnowledge, ...] = (
    AssetKnowledge(
        symbol="BTC",
        coin_id="bitcoin",
        official_name="Bitcoin",
        asset_kind=ASSET_KIND_L1_ASSET,
        categories=("l1", "macro_asset"),
        sectors=("bitcoin", "store_of_value"),
        aliases=("bitcoin", "btc"),
        ticker_collision_terms=("bitcoin world",),
        broad_macro_asset=True,
        role_capabilities=AssetRoleCapabilities(can_be_direct_beneficiary=True, can_be_market_anomaly=True),
    ),
    AssetKnowledge(
        symbol="ETH",
        coin_id="ethereum",
        official_name="Ethereum",
        asset_kind=ASSET_KIND_L1_ASSET,
        categories=("l1", "smart_contract_platform", "macro_asset"),
        sectors=("ethereum",),
        aliases=("ethereum", "ether", "eth"),
        broad_macro_asset=True,
        role_capabilities=AssetRoleCapabilities(can_be_direct_beneficiary=True, can_be_infrastructure=True, can_be_market_anomaly=True),
    ),
    AssetKnowledge(
        symbol="SOL",
        coin_id="solana",
        official_name="Solana",
        asset_kind=ASSET_KIND_L1_ASSET,
        categories=("l1", "smart_contract_platform", "macro_asset"),
        sectors=("solana",),
        aliases=("solana", "sol"),
        broad_macro_asset=True,
        role_capabilities=AssetRoleCapabilities(can_be_direct_beneficiary=True, can_be_infrastructure=True, can_be_market_anomaly=True),
    ),
    AssetKnowledge(
        symbol="RUNE",
        coin_id="thorchain",
        official_name="THORChain",
        asset_kind=ASSET_KIND_PROTOCOL_TOKEN,
        categories=("defi", "cross_chain_liquidity"),
        sectors=("thorchain",),
        aliases=("rune", "thorchain"),
        project_entities=("THORChain",),
        role_capabilities=AssetRoleCapabilities(can_be_direct_beneficiary=True, can_be_market_anomaly=True),
    ),
    AssetKnowledge(
        symbol="AAVE",
        coin_id="aave",
        official_name="Aave",
        asset_kind=ASSET_KIND_PROTOCOL_TOKEN,
        categories=("defi", "lending"),
        sectors=("aave",),
        aliases=("aave",),
        project_entities=("Aave", "Aave Labs"),
        role_capabilities=AssetRoleCapabilities(can_be_direct_beneficiary=True, can_be_market_anomaly=True),
    ),
    AssetKnowledge(
        symbol="ZEC",
        coin_id="zcash",
        official_name="Zcash",
        asset_kind=ASSET_KIND_L1_ASSET,
        categories=("privacy", "l1"),
        sectors=("zcash",),
        aliases=("zec", "zcash"),
        role_capabilities=AssetRoleCapabilities(can_be_direct_beneficiary=True, can_be_market_anomaly=True),
    ),
    AssetKnowledge(
        symbol="VELVET",
        coin_id="velvet",
        official_name="Velvet",
        asset_kind=ASSET_KIND_TOKENIZED_EQUITY_VENUE,
        categories=("rwa", "pre_ipo", "tokenized_equity_venue"),
        sectors=("rwa_preipo_proxy", "tokenized_stock_venue"),
        aliases=("velvet", "velvet capital", "velvet.trade"),
        known_proxy_relationships=("SpaceX pre-IPO exposure", "tokenized stock venue"),
        role_capabilities=AssetRoleCapabilities(can_be_proxy_venue=True, can_be_direct_beneficiary=True, can_be_market_anomaly=True),
    ),
    AssetKnowledge(
        symbol="CHZ",
        coin_id="chiliz",
        official_name="Chiliz",
        asset_kind=ASSET_KIND_FAN_TOKEN,
        categories=("fan_token", "sports"),
        sectors=("sports_fan_proxy",),
        aliases=("chz", "chiliz"),
        role_capabilities=AssetRoleCapabilities(can_be_proxy_instrument=True, can_be_direct_beneficiary=True, can_be_market_anomaly=True),
    ),
    AssetKnowledge(
        symbol="TRUMP",
        coin_id="official-trump",
        official_name="Official Trump",
        asset_kind=ASSET_KIND_MEME_TOKEN,
        categories=("meme", "political_meme"),
        sectors=("political_meme_proxy",),
        aliases=("trump", "official trump", "trump token"),
        ticker_collision_terms=("trump campaign", "trump administration", "trump policy"),
        common_word_collision_risk=True,
        role_capabilities=AssetRoleCapabilities(can_be_proxy_instrument=True, can_be_direct_beneficiary=True, can_be_market_anomaly=True),
    ),
    AssetKnowledge(
        symbol="HYPE",
        coin_id="hyperliquid",
        official_name="Hyperliquid",
        asset_kind=ASSET_KIND_VENUE_TOKEN,
        categories=("perp_venue", "exchange_ecosystem"),
        sectors=("perp_venue_attention",),
        aliases=("hyperliquid", "hype"),
        ticker_collision_terms=("hype",),
        common_word_collision_risk=True,
        role_capabilities=AssetRoleCapabilities(can_be_proxy_venue=True, can_be_direct_beneficiary=True, can_be_market_anomaly=True),
    ),
    AssetKnowledge(
        symbol="KCS",
        coin_id="kucoin-shares",
        official_name="KuCoin Token",
        asset_kind=ASSET_KIND_EXCHANGE_TOKEN,
        categories=("exchange_token",),
        sectors=("exchange"),
        aliases=("kcs", "kucoin token", "kucoin shares"),
        excluded_aliases=("kucoin",),
        ticker_collision_terms=("kucoin source", "kucoin announcement"),
        role_capabilities=AssetRoleCapabilities(can_be_direct_beneficiary=True, can_be_market_anomaly=True),
    ),
    AssetKnowledge(
        symbol="M",
        coin_id="memecore",
        official_name="MemeCore",
        asset_kind=ASSET_KIND_MEME_TOKEN,
        categories=("meme", "app"),
        sectors=("meme", "market_anomaly"),
        aliases=("memecore", "m"),
        common_word_collision_risk=True,
        role_capabilities=AssetRoleCapabilities(can_be_proxy_instrument=True, can_be_direct_beneficiary=True, can_be_market_anomaly=True),
    ),
    AssetKnowledge(
        symbol="LINK",
        coin_id="chainlink",
        official_name="Chainlink",
        asset_kind=ASSET_KIND_INFRA_TOKEN,
        categories=("oracle", "infrastructure"),
        sectors=("prediction_market_infra", "oracle"),
        aliases=("link", "chainlink"),
        common_word_collision_risk=True,
        role_capabilities=AssetRoleCapabilities(can_be_direct_beneficiary=True, can_be_infrastructure=True, can_be_market_anomaly=True),
    ),
    AssetKnowledge(
        symbol="USDT",
        coin_id="tether",
        official_name="Tether",
        asset_kind=ASSET_KIND_STABLECOIN,
        categories=("stablecoin",),
        aliases=("usdt", "tether"),
        role_capabilities=AssetRoleCapabilities(can_be_direct_beneficiary=True, can_be_market_anomaly=False),
    ),
    AssetKnowledge(
        symbol="WETH",
        coin_id="weth",
        official_name="Wrapped Ether",
        asset_kind=ASSET_KIND_WRAPPED_ASSET,
        categories=("wrapped_asset",),
        aliases=("weth", "wrapped ether"),
        role_capabilities=AssetRoleCapabilities(can_be_direct_beneficiary=False, can_be_market_anomaly=False),
    ),
)


def asset_knowledge_for(
    *,
    symbol: str | None = None,
    coin_id: str | None = None,
    name: str | None = None,
    categories: Iterable[object] = (),
    aliases: Iterable[object] = (),
    metadata: Mapping[str, Any] | None = None,
) -> AssetKnowledge:
    """Return lightweight asset knowledge for resolver and role validation."""
    meta = dict(metadata or {})
    symbol_u = str(symbol or meta.get("symbol") or "").strip().upper()
    coin = str(coin_id or meta.get("coin_id") or "").strip()
    official = str(name or meta.get("name") or meta.get("official_name") or coin or symbol_u or "unknown").strip()
    category_values = tuple(str(value) for value in (*tuple(categories or ()), *tuple(meta.get("categories") or ())) if str(value))
    alias_values = tuple(str(value) for value in (*tuple(aliases or ()), *tuple(meta.get("aliases") or ())) if str(value))
    identity_terms = {_clean_text(value) for value in (symbol_u, coin, official, *alias_values) if str(value or "").strip()}
    for item in _DEFAULT_ASSET_KNOWLEDGE:
        item_terms = {_clean_text(value) for value in (item.symbol, item.coin_id, item.official_name, *item.aliases) if str(value or "").strip()}
        if (
            (symbol_u and symbol_u == item.normalized_symbol)
            or (coin and _clean_text(coin) == _clean_text(item.coin_id))
            or (official and _clean_text(official) == _clean_text(item.official_name))
            or bool(identity_terms & item_terms)
        ):
            return _merge_asset_knowledge(item, meta)
    asset_kind = str(meta.get("asset_kind") or _infer_asset_kind(symbol_u, coin, official, category_values)).strip() or ASSET_KIND_UNKNOWN
    caps = _capabilities_for_kind(asset_kind)
    common = (
        (bool(symbol_u) and len(symbol_u) <= 1)
        or symbol_u in COMMON_WORD_SYMBOLS
        or any(_clean_text(symbol_u) == _clean_text(term) for term in alias_values)
    )
    return AssetKnowledge(
        symbol=symbol_u,
        coin_id=coin,
        official_name=official,
        asset_kind=asset_kind,
        categories=category_values,
        aliases=alias_values,
        broad_macro_asset=asset_kind == ASSET_KIND_L1_ASSET and symbol_u in {"BTC", "ETH", "SOL"},
        common_word_collision_risk=common,
        role_capabilities=caps,
    )


def validate_asset_role(
    knowledge: AssetKnowledge,
    requested_role: str,
    *,
    impact_category: str | None = None,
    impact_path_type: str | None = None,
    role_source: str | None = None,
    source_text: str | None = None,
    market_confirmation: float = 0.0,
    identity_confidence: float | None = None,
    identity_evidence: Iterable[object] = (),
) -> AssetRoleValidation:
    """Validate a candidate role against asset knowledge and source context."""
    role = str(requested_role or ROLE_GENERIC_MENTION)
    source = str(role_source or ROLE_SOURCE_RESOLVER_EXACT)
    text = _clean_text(source_text or "")
    failures: list[str] = []
    warnings: list[str] = []
    final_role = role
    confidence = float(identity_confidence if identity_confidence is not None else _default_identity_confidence(source))
    collision = "high" if knowledge.common_word_collision_risk else "none"
    if knowledge.common_word_collision_risk:
        warnings.append("common_word_or_ticker_collision_risk")

    if source == ROLE_SOURCE_TAXONOMY_CANDIDATE and role in {
        ROLE_DIRECT_SUBJECT,
        ROLE_ECOSYSTEM_AFFECTED_ASSET,
        ROLE_PROXY_INSTRUMENT,
        ROLE_PROXY_VENUE,
    }:
        if _source_directly_supports_role(knowledge, role, text):
            warnings.append("taxonomy_candidate_upgraded_by_source_evidence")
            source = ROLE_SOURCE_RESOLVER_EXACT
            confidence = max(confidence, 80.0)
        else:
            failures.append("taxonomy_candidate_not_affected_asset")
            final_role = ROLE_GENERIC_MENTION
            source = ROLE_SOURCE_TAXONOMY_CANDIDATE

    category = _clean_text(impact_category or "").replace(" ", "_")
    path_type = _clean_text(impact_path_type or "").replace(" ", "_")
    caps = knowledge.role_capabilities
    if role == ROLE_PROXY_INSTRUMENT and not caps.can_be_proxy_instrument:
        if _explicit_proxy_instrument_text(text):
            warnings.append("proxy_instrument_allowed_by_explicit_source_text")
        else:
            failures.append("asset_cannot_be_proxy_instrument")
            final_role = ROLE_GENERIC_MENTION
    if role == ROLE_PROXY_VENUE and not caps.can_be_proxy_venue:
        failures.append("asset_cannot_be_proxy_venue")
        final_role = ROLE_GENERIC_MENTION
    if role == ROLE_INFRASTRUCTURE_PROVIDER and not (caps.can_be_infrastructure or _infrastructure_text(text)):
        failures.append("asset_not_infrastructure_provider")
        final_role = ROLE_GENERIC_MENTION
    if role in {ROLE_DIRECT_SUBJECT, ROLE_ECOSYSTEM_AFFECTED_ASSET, ROLE_ECOSYSTEM_BENEFICIARY} and not caps.can_be_direct_beneficiary:
        failures.append("asset_cannot_be_direct_beneficiary")
        final_role = ROLE_GENERIC_MENTION
    if category == "sports_fan_proxy" and role in {ROLE_PROXY_INSTRUMENT, ROLE_DIRECT_SUBJECT}:
        if knowledge.asset_kind != ASSET_KIND_FAN_TOKEN and not _sports_text(text):
            failures.append("fan_token_event_requires_fan_token_or_sports_evidence")
            final_role = ROLE_GENERIC_MENTION
    if any(value in {category, path_type} for value in ("rwa_preipo_proxy", "ai_ipo_proxy", "tokenized_stock_venue", "venue_value_capture", "proxy_attention")):
        if role in {ROLE_PROXY_INSTRUMENT, ROLE_PROXY_VENUE} and not (caps.can_be_proxy_instrument or caps.can_be_proxy_venue):
            failures.append("proxy_event_requires_proxy_capability")
            final_role = ROLE_GENERIC_MENTION
    if category == "market_anomaly_unknown" and not caps.can_be_market_anomaly:
        failures.append("stable_or_wrapped_asset_not_market_anomaly_candidate")
        final_role = ROLE_GENERIC_MENTION
    broad_guard = _broad_strategic_context_guard(knowledge, text, category=category, market_confirmation=market_confirmation)
    if broad_guard:
        failures.append(broad_guard)
        final_role = ROLE_MACRO_AFFECTED_ASSET
        source = ROLE_SOURCE_CONTEXT_ONLY
        confidence = min(confidence, 45.0)

    accepted = not failures
    if accepted and role == ROLE_DIRECT_SUBJECT and source == ROLE_SOURCE_CONTEXT_ONLY:
        warnings.append("source_context_only_not_direct_subject")
    return AssetRoleValidation(
        accepted=accepted,
        final_role=final_role,
        role_source=source,
        identity_confidence=round(max(0.0, min(100.0, confidence)), 2),
        identity_evidence=tuple(str(value) for value in identity_evidence if str(value)),
        collision_risk=collision,
        failures=tuple(dict.fromkeys(failures)),
        warnings=tuple(dict.fromkeys(warnings)),
        asset_kind=knowledge.asset_kind,
        role_capabilities=knowledge.role_capabilities,
    )


def _merge_asset_knowledge(base: AssetKnowledge, meta: Mapping[str, Any]) -> AssetKnowledge:
    if not meta:
        return base
    return AssetKnowledge(
        symbol=str(meta.get("symbol") or base.symbol),
        coin_id=str(meta.get("coin_id") or base.coin_id),
        official_name=str(meta.get("official_name") or meta.get("name") or base.official_name),
        asset_kind=str(meta.get("asset_kind") or base.asset_kind),
        categories=tuple(dict.fromkeys((*base.categories, *(str(value) for value in meta.get("categories") or ())))),
        sectors=tuple(dict.fromkeys((*base.sectors, *(str(value) for value in meta.get("sectors") or ())))),
        official_domains=tuple(dict.fromkeys((*base.official_domains, *(str(value) for value in meta.get("official_domains") or ())))),
        project_entities=tuple(dict.fromkeys((*base.project_entities, *(str(value) for value in meta.get("project_entities") or ())))),
        exchange_pairs=tuple(dict.fromkeys((*base.exchange_pairs, *(str(value) for value in meta.get("exchange_pairs") or ())))),
        aliases=tuple(dict.fromkeys((*base.aliases, *(str(value) for value in meta.get("aliases") or ())))),
        excluded_aliases=tuple(dict.fromkeys((*base.excluded_aliases, *(str(value) for value in meta.get("excluded_aliases") or ())))),
        ticker_collision_terms=tuple(dict.fromkeys((*base.ticker_collision_terms, *(str(value) for value in meta.get("ticker_collision_terms") or ())))),
        known_proxy_relationships=tuple(dict.fromkeys((*base.known_proxy_relationships, *(str(value) for value in meta.get("known_proxy_relationships") or ())))),
        broad_macro_asset=bool(meta.get("broad_macro_asset", base.broad_macro_asset)),
        common_word_collision_risk=bool(meta.get("common_word_collision_risk", base.common_word_collision_risk)),
        role_capabilities=base.role_capabilities,
    )


def _infer_asset_kind(symbol: str, coin_id: str, name: str, categories: Iterable[str]) -> str:
    text = _clean_text(" ".join((symbol, coin_id, name, *tuple(categories))))
    if any(term in text for term in ("stable", "usd", "usdt", "usdc")):
        return ASSET_KIND_STABLECOIN
    if "wrapped" in text or symbol.startswith("W"):
        return ASSET_KIND_WRAPPED_ASSET if "wrapped" in text else ASSET_KIND_UNKNOWN
    if "fan" in text or "sports" in text:
        return ASSET_KIND_FAN_TOKEN
    if "meme" in text:
        return ASSET_KIND_MEME_TOKEN
    if "oracle" in text or "infrastructure" in text:
        return ASSET_KIND_INFRA_TOKEN
    if "exchange" in text or "venue" in text:
        return ASSET_KIND_VENUE_TOKEN
    if "l1" in text or "layer 1" in text:
        return ASSET_KIND_L1_ASSET
    return ASSET_KIND_PROTOCOL_TOKEN if any((symbol, coin_id, name)) else ASSET_KIND_UNKNOWN


def _capabilities_for_kind(asset_kind: str) -> AssetRoleCapabilities:
    if asset_kind == ASSET_KIND_TOKENIZED_EQUITY_VENUE:
        return AssetRoleCapabilities(can_be_proxy_venue=True, can_be_direct_beneficiary=True, can_be_market_anomaly=True)
    if asset_kind == ASSET_KIND_FAN_TOKEN:
        return AssetRoleCapabilities(can_be_proxy_instrument=True, can_be_direct_beneficiary=True, can_be_market_anomaly=True)
    if asset_kind == ASSET_KIND_INFRA_TOKEN:
        return AssetRoleCapabilities(can_be_direct_beneficiary=True, can_be_infrastructure=True, can_be_market_anomaly=True)
    if asset_kind in {ASSET_KIND_STABLECOIN, ASSET_KIND_WRAPPED_ASSET}:
        return AssetRoleCapabilities(can_be_direct_beneficiary=asset_kind == ASSET_KIND_STABLECOIN, can_be_market_anomaly=False)
    return AssetRoleCapabilities(can_be_direct_beneficiary=True, can_be_market_anomaly=True)


def _default_identity_confidence(role_source: str) -> float:
    return {
        ROLE_SOURCE_OFFICIAL_SOURCE: 95.0,
        ROLE_SOURCE_RESOLVER_EXACT: 88.0,
        ROLE_SOURCE_LLM_SUGGESTION: 70.0,
        ROLE_SOURCE_MARKET_SYMBOL_ONLY: 55.0,
        ROLE_SOURCE_TAXONOMY_CANDIDATE: 45.0,
        ROLE_SOURCE_CONTEXT_ONLY: 35.0,
    }.get(role_source, 60.0)


def _broad_strategic_context_guard(
    knowledge: AssetKnowledge,
    text: str,
    *,
    category: str,
    market_confirmation: float,
) -> str | None:
    if not knowledge.broad_macro_asset:
        return None
    strategic = category == "strategic_investment_or_valuation" or any(
        term in text
        for term in ("strategic investment", "stake", "acquisition", "valuation", "treasury valuation")
    )
    if not strategic:
        return None
    direct_terms = (
        f"bought {knowledge.normalized_symbol.casefold()}",
        f"buys {knowledge.normalized_symbol.casefold()}",
        f"holds {knowledge.normalized_symbol.casefold()}",
        f"holding {knowledge.normalized_symbol.casefold()}",
        f"added {knowledge.normalized_symbol.casefold()}",
        f"{knowledge.normalized_symbol.casefold()} treasury",
        f"{knowledge.coin_id.casefold()} treasury",
    )
    explicit_asset = any(term and term in text for term in direct_terms)
    if explicit_asset or market_confirmation >= 75.0:
        return None
    return "broad_macro_asset_context_only"


def _infrastructure_text(text: str) -> bool:
    return any(term in text for term in ("oracle", "infrastructure", "provider", "powers", "powered by", "settlement"))


def _sports_text(text: str) -> bool:
    return any(term in text for term in ("fan token", "world cup", "match", "fixture", "team", "sports"))


def _explicit_proxy_instrument_text(text: str) -> bool:
    return any(term in text for term in ("synthetic exposure", "token traders", "tokenized stock", "pre ipo", "pre-ipo")) and any(
        term in text for term in (" token", "$", "coin", "instrument", "exposure")
    )


def _source_directly_supports_role(knowledge: AssetKnowledge, role: str, text: str) -> bool:
    terms = _knowledge_identity_terms(knowledge)
    if not any(_term_in_clean_text(term, text) for term in terms):
        return False
    negative_markers = ("taxonomy candidate", "appears only", "only as", "background", "context only")
    if any(_window_contains_marker(text, term, negative_markers, before=4, after=8) for term in terms):
        return False
    if role in {ROLE_PROXY_INSTRUMENT, ROLE_PROXY_VENUE}:
        return any(
            marker in text
            for marker in (
                "synthetic exposure",
                "pre ipo",
                "pre-ipo",
                "tokenized stock",
                "meme exposure",
                "political meme proxy",
                "proxy",
                "fan token",
                "world cup",
                "trade",
                "trading",
                "market",
                "venue",
            )
        )
    if role in {ROLE_DIRECT_SUBJECT, ROLE_ECOSYSTEM_AFFECTED_ASSET, ROLE_ECOSYSTEM_BENEFICIARY}:
        direct_markers = (
            "exploit",
            "hack",
            "resumes trading",
            "halts trading",
            "listing",
            "lists",
            "delisting",
            "perp",
            "unlock",
            "airdrop",
            "tge",
            "launchpool",
            "stake",
            "strategic",
            "acquired",
            "buys",
            "merger",
        )
        return any(_window_contains_marker(text, term, direct_markers, before=8, after=8) for term in terms)
    return False


def _knowledge_identity_terms(knowledge: AssetKnowledge) -> tuple[str, ...]:
    values = (
        knowledge.symbol,
        knowledge.coin_id,
        knowledge.official_name,
        *knowledge.aliases,
        *knowledge.project_entities,
    )
    return tuple(dict.fromkeys(term for term in (_clean_text(value) for value in values) if term and len(term) >= 2))


def _window_contains_marker(
    text: str,
    term: str,
    markers: tuple[str, ...],
    *,
    before: int,
    after: int,
) -> bool:
    words = text.split()
    term_words = term.split()
    if not words or not term_words:
        return False
    for idx in range(0, len(words) - len(term_words) + 1):
        if words[idx : idx + len(term_words)] != term_words:
            continue
        start = max(0, idx - before)
        end = min(len(words), idx + len(term_words) + after)
        window = " ".join(words[start:end])
        if any(marker in window for marker in markers):
            return True
    return False


def match_asset_identity(identity: AssetIdentity, evidence: IdentityEvidence) -> IdentityMatchResult:
    """Match an asset identity against field-strength-aware evidence.

    Strong content and quote evidence can prove identity. Source-origin and
    URL-query-only matches are explicitly rejected so publisher names and search
    URLs cannot satisfy symbol identity.
    """
    symbol = identity.normalized_symbol
    if not symbol and not identity.terms and not identity.contract_addresses:
        return _none()
    is_common = identity.is_common_word_symbol or symbol in COMMON_WORD_SYMBOLS or len(symbol) == 1
    single_character_symbol = len(symbol) == 1
    strong_texts = _texts(evidence.strong_content)
    strong_blob = " ".join(strong_texts)
    strong_lower = strong_blob.casefold()
    url = str(evidence.url or "")

    for address in identity.contract_addresses:
        clean = str(address or "").strip()
        if not clean:
            continue
        if clean.casefold() in strong_lower:
            return _strong("identity_match_contract", "strong_content", _snippet_for(clean, strong_texts))
        if contract_in_url_path(url, clean):
            return _strong("identity_match_contract", "url_path_contract", clean)

    if symbol:
        if pair_symbol_in_text(strong_blob, symbol):
            return _strong("identity_match_pair", "strong_content", _snippet_for(symbol, strong_texts))
        if dollar_symbol_in_text(strong_blob, symbol):
            return _strong("identity_match_strong", "strong_content", _snippet_for(symbol, strong_texts))
        if not single_character_symbol and case_sensitive_symbol_in_text(strong_blob, symbol):
            return _strong("identity_match_strong", "strong_content", _snippet_for(symbol, strong_texts))
        if not single_character_symbol and token_context_in_text(_clean_text(strong_blob), symbol):
            return _strong("identity_match_token_context", "strong_content", _snippet_for(symbol, strong_texts))

    for term in identity.terms:
        normalized = _clean_text(term)
        if not normalized or len(normalized) < 3:
            continue
        if _term_in_clean_text(normalized, _clean_text(strong_blob)):
            reason = "identity_match_project" if identity.project_name and normalized == _clean_text(identity.project_name) else "identity_match_alias"
            return _strong(reason, "strong_content", _snippet_for(term, strong_texts))

    for quote in _texts(evidence.llm_quotes):
        quote_result = _quote_mentions_identity(identity, quote, is_common=is_common)
        if quote_result:
            return _strong("identity_quote_validated", "llm_quote", quote)

    if is_common and symbol and re.search(rf"(?<![a-z0-9]){re.escape(symbol.casefold())}(?![a-z0-9])", _clean_text(strong_blob)):
        return IdentityMatchResult(
            matched=False,
            strength=STRENGTH_REJECTED,
            reason="common_word_identity_rejected",
            evidence_field="strong_content",
            evidence_text=_snippet_for(symbol, strong_texts),
        )

    origin_text = _clean_text(" ".join(_texts(evidence.source_origin)))
    if _identity_in_clean_text(identity, origin_text, symbol=symbol):
        return IdentityMatchResult(False, STRENGTH_REJECTED, "identity_source_origin_rejected", "source_origin")

    metadata_text = _clean_text(" ".join(_texts(evidence.metadata)))
    if _identity_in_clean_text(identity, metadata_text, symbol=symbol):
        return IdentityMatchResult(False, STRENGTH_REJECTED, "identity_source_origin_rejected", "metadata")

    if _identity_in_url_only(identity, url, symbol=symbol):
        return IdentityMatchResult(False, STRENGTH_REJECTED, "identity_url_only_rejected", "weak_url")

    return _none()


def validated_llm_identity_quotes(payload: object, source_texts: Iterable[object]) -> tuple[str, ...]:
    """Return extraction quotes that appear verbatim in source text."""
    if not isinstance(payload, dict):
        return ()
    extraction = payload.get("llm_extraction")
    if not isinstance(extraction, dict):
        return ()
    source_text = " ".join(str(item or "") for item in source_texts)
    out: list[str] = []
    for key in ("crypto_asset_mentions", "external_catalysts", "false_positive_terms"):
        rows = extraction.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            for quote in row.get("evidence_quotes") or ():
                text = str(quote.get("text") if isinstance(quote, dict) else quote or "").strip()
                if text and text in source_text:
                    out.append(text)
    return tuple(dict.fromkeys(out))


def contract_in_url_path(source_url: str, address: str) -> bool:
    if not source_url or not address or not looks_contract_address(address):
        return False
    try:
        parsed = urlparse(source_url)
    except ValueError:
        return False
    address_l = address.casefold()
    if address_l in (parsed.query or "").casefold():
        return False
    return address_l in (parsed.path or "").casefold()


def looks_contract_address(address: str) -> bool:
    return bool(re.fullmatch(r"0x[a-fA-F0-9]{40}", str(address or "").strip()))


def pair_symbol_in_text(text: str, symbol: str) -> bool:
    if not symbol:
        return False
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(symbol)}(?:[-_/]?)USDT(?![A-Za-z0-9])", text, flags=re.IGNORECASE) is not None


def dollar_symbol_in_text(text: str, symbol: str) -> bool:
    if not symbol:
        return False
    return re.search(rf"(?<![A-Za-z0-9])\${re.escape(symbol)}(?![A-Za-z0-9])", text, flags=re.IGNORECASE) is not None


def case_sensitive_symbol_in_text(text: str, symbol: str) -> bool:
    if not symbol:
        return False
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(symbol)}(?![A-Za-z0-9])", text) is not None


def token_context_in_text(clean_text: str, symbol: str) -> bool:
    if not symbol:
        return False
    lower = symbol.casefold()
    return any(
        phrase in clean_text
        for phrase in (
            f"{lower} token",
            f"{lower} coin",
            f"{lower} crypto",
            f"token {lower}",
            f"coin {lower}",
        )
    )


def _quote_mentions_identity(identity: AssetIdentity, quote: str, *, is_common: bool) -> bool:
    if not quote:
        return False
    symbol = identity.normalized_symbol
    if symbol and (
        pair_symbol_in_text(quote, symbol)
        or dollar_symbol_in_text(quote, symbol)
        or (len(symbol) > 1 and case_sensitive_symbol_in_text(quote, symbol))
        or (len(symbol) > 1 and token_context_in_text(_clean_text(quote), symbol))
    ):
        return True
    for term in identity.terms:
        normalized = _clean_text(term)
        if normalized and len(normalized) >= 3 and _term_in_clean_text(normalized, _clean_text(quote)):
            return True
    if is_common:
        return False
    return bool(symbol and symbol.casefold() in quote.casefold())


def _identity_in_url_only(identity: AssetIdentity, source_url: str, *, symbol: str) -> bool:
    if not source_url:
        return False
    text = _clean_text(source_url)
    if symbol and re.search(rf"(?<![a-z0-9]){re.escape(symbol.casefold())}(?:usdt)?(?![a-z0-9])", text):
        return True
    for term in identity.terms:
        normalized = _clean_text(term)
        if normalized and _term_in_clean_text(normalized, text):
            return True
    for address in identity.contract_addresses:
        if str(address or "").casefold() in source_url.casefold() and not contract_in_url_path(source_url, str(address)):
            return True
    return False


def _identity_in_clean_text(identity: AssetIdentity, text: str, *, symbol: str) -> bool:
    if not text:
        return False
    if symbol and re.search(rf"(?<![a-z0-9]){re.escape(symbol.casefold())}(?![a-z0-9])", text):
        return True
    for term in identity.terms:
        normalized = _clean_text(term)
        if normalized and _term_in_clean_text(normalized, text):
            return True
    return False


def _term_in_clean_text(term: str, clean_text: str) -> bool:
    if not term or not clean_text:
        return False
    if " " in term:
        return term in clean_text
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", clean_text) is not None


def _clean_text(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def _texts(values: Iterable[object]) -> tuple[str, ...]:
    return tuple(str(value or "").strip() for value in values if str(value or "").strip())


def _snippet_for(term: object, texts: Iterable[str]) -> str | None:
    needle = str(term or "").strip()
    if not needle:
        return None
    for text in texts:
        idx = text.casefold().find(needle.casefold())
        if idx >= 0:
            start = max(0, idx - 40)
            end = min(len(text), idx + len(needle) + 40)
            return text[start:end].strip()
    for text in texts:
        if text:
            return text[:120].strip()
    return None


def _strong(reason: str, field: str, text: str | None) -> IdentityMatchResult:
    return IdentityMatchResult(True, STRENGTH_STRONG, reason, field, text)


def _none() -> IdentityMatchResult:
    return IdentityMatchResult(False, STRENGTH_NONE, None, None, None)
