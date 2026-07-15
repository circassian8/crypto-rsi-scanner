"""Pure source/evidence quality scoring for Event Alpha hypotheses."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from crypto_rsi_scanner.event_alpha.providers import source_registry as event_source_registry
from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent
from .resolver import clean_text


class SourceClass(str, Enum):
    OFFICIAL_PROJECT = "official_project"
    OFFICIAL_EXCHANGE = "official_exchange"
    STRUCTURED_EVENT = "structured_event"
    CRYPTOPANIC_TAGGED = "cryptopanic_tagged"
    CRYPTO_NEWS = "crypto_news"
    BROAD_NEWS = "broad_news"
    PREDICTION_MARKET = "prediction_market"
    MARKET_RECAP = "market_recap"
    SOCIAL_OR_UNKNOWN = "social_or_unknown"


class EvidenceSpecificity(str, Enum):
    DIRECT_TOKEN_MECHANISM = "direct_token_mechanism"
    TOKEN_AND_CATALYST = "token_and_catalyst"
    CATALYST_ONLY = "catalyst_only"
    TOKEN_ONLY = "token_only"
    GENERIC_CONTEXT = "generic_context"
    SOURCE_NOISE = "source_noise"


@dataclass(frozen=True)
class EvidenceQualityResult:
    evidence_quality_score: float
    source_class: str
    evidence_specificity: str
    reason_codes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    source_reliability_prior: float | None = None


_LOW_QUALITY_TERMS = ("price prediction", "market recap", "today's crypto prices", "top gainers", "technical analysis")
_MECHANISM_TERMS = (
    "offers",
    "lets users trade",
    "exposure",
    "tokenized stock",
    "synthetic exposure",
    "listing",
    "listed on",
    "unlock",
    "vesting",
    "exploit",
    "hack",
    "resumes trading",
    "fan token",
    "trading pair",
    "airdrop",
    "tge",
    "stake",
    "strategic investment",
    "valuation",
    "acquisition",
)
_CATALYST_TERMS = (
    "ipo",
    "pre-ipo",
    "world cup",
    "election",
    "listing",
    "unlock",
    "exploit",
    "hack",
    "merger",
    "lawsuit",
    "cftc",
    "sec",
    "quantum",
    "prediction market",
    "stake",
    "strategic investment",
    "valuation",
    "acquisition",
)


def evaluate_evidence_quality(
    raw: RawDiscoveredEvent | Mapping[str, Any] | None,
    *,
    hypothesis: object | None = None,
    symbol: str | None = None,
    coin_id: str | None = None,
    source_reliability_prior: float | None = None,
    use_source_reliability_prior: bool = False,
) -> EvidenceQualityResult:
    """Score source hierarchy and whether text explains token-catalyst linkage."""
    raw_map = _raw_mapping(raw)
    provider = clean_text(raw_map.get("provider") or "")
    payload = raw_map.get("raw_json") if isinstance(raw_map.get("raw_json"), Mapping) else {}
    source_origin = clean_text(payload.get("source_origin") or payload.get("provider") or "")
    title = str(raw_map.get("title") or "")
    body = str(raw_map.get("body") or "")
    text = clean_text(" ".join(str(value or "") for value in (title, body, source_origin, payload.get("description"))))
    category = clean_text(getattr(hypothesis, "impact_category", "") if hypothesis is not None else "")

    registry = event_source_registry.assess_source(raw_map, symbol=symbol, coin_id=coin_id)
    source_class, base, reasons = _classify_source(registry)
    specificity, specificity_score, specificity_reasons = _specificity(
        text,
        symbol=symbol,
        coin_id=coin_id,
        category=category,
        payload=payload,
    )
    reasons.extend(specificity_reasons)
    score = max(base, specificity_score)
    if source_class in {SourceClass.OFFICIAL_EXCHANGE.value, SourceClass.STRUCTURED_EVENT.value}:
        score += 8.0
    if source_class == SourceClass.CRYPTOPANIC_TAGGED.value and specificity in {
        EvidenceSpecificity.DIRECT_TOKEN_MECHANISM.value,
        EvidenceSpecificity.TOKEN_AND_CATALYST.value,
    }:
        score += 10.0
    if source_class in {SourceClass.PREDICTION_MARKET.value, SourceClass.BROAD_NEWS.value} and specificity not in {
        EvidenceSpecificity.DIRECT_TOKEN_MECHANISM.value,
        EvidenceSpecificity.TOKEN_AND_CATALYST.value,
    }:
        score = min(score, 55.0)
        reasons.append("broad_or_external_source_capped")
    if source_class == SourceClass.MARKET_RECAP.value:
        score = min(score, 45.0)
        reasons.append("market_recap_capped")
    if specificity == EvidenceSpecificity.SOURCE_NOISE.value:
        score = min(score, 25.0)
        reasons.append("source_noise_capped")
    fixture_route_coverage = provider == "fixture" or provider.startswith("fixture_")
    if fixture_route_coverage:
        reasons.append("fixture_evidence_quality_route_coverage_only")
    else:
        contract_cap = registry.confidence_cap
        if not registry.can_validate_catalyst:
            contract_cap = min(contract_cap, 55.0)
            reasons.append("source_cannot_validate_catalyst")
        if score > contract_cap:
            score = contract_cap
            reasons.append("source_registry_confidence_cap_applied")
    prior_value = _prior_score(source_reliability_prior)
    if use_source_reliability_prior and prior_value is not None:
        adjustment = max(-10.0, min(10.0, prior_value - 50.0))
        score += adjustment
        reasons.append("source_reliability_prior_applied")
    return EvidenceQualityResult(
        evidence_quality_score=round(max(0.0, min(100.0, score)), 2),
        source_class=source_class,
        evidence_specificity=specificity,
        reason_codes=tuple(dict.fromkeys(reasons)),
        warnings=tuple(dict.fromkeys((*registry.warnings, *_warnings(source_class, specificity, text)))),
        source_reliability_prior=prior_value if use_source_reliability_prior else None,
    )


def _classify_source(
    registry: event_source_registry.SourceRegistryAssessment,
) -> tuple[str, float, list[str]]:
    source_class = registry.source_class
    reasons = list(registry.reason_codes)
    mapping = {
        event_source_registry.SourceClass.OFFICIAL_PROJECT.value: (SourceClass.OFFICIAL_PROJECT.value, 82.0),
        event_source_registry.SourceClass.OFFICIAL_EXCHANGE.value: (SourceClass.OFFICIAL_EXCHANGE.value, 86.0),
        event_source_registry.SourceClass.STRUCTURED_CALENDAR.value: (SourceClass.STRUCTURED_EVENT.value, 84.0),
        event_source_registry.SourceClass.STRUCTURED_UNLOCK.value: (SourceClass.STRUCTURED_EVENT.value, 84.0),
        event_source_registry.SourceClass.CRYPTOPANIC_TAGGED.value: (
            SourceClass.CRYPTOPANIC_TAGGED.value,
            72.0 if registry.cryptopanic_currency_tag_match else 62.0,
        ),
        event_source_registry.SourceClass.CRYPTO_NEWS.value: (SourceClass.CRYPTO_NEWS.value, 64.0),
        event_source_registry.SourceClass.BROAD_NEWS.value: (SourceClass.BROAD_NEWS.value, 48.0),
        event_source_registry.SourceClass.PREDICTION_MARKET.value: (SourceClass.PREDICTION_MARKET.value, 48.0),
        event_source_registry.SourceClass.MARKET_RECAP.value: (SourceClass.MARKET_RECAP.value, 35.0),
        event_source_registry.SourceClass.SEO_OR_AFFILIATE.value: (SourceClass.MARKET_RECAP.value, 25.0),
    }
    local_class, base = mapping.get(source_class, (SourceClass.SOCIAL_OR_UNKNOWN.value, 36.0))
    return local_class, base, reasons


def _specificity(
    text: str,
    *,
    symbol: str | None,
    coin_id: str | None,
    category: str,
    payload: Mapping[str, Any],
) -> tuple[str, float, list[str]]:
    asset = _asset_present(text, symbol=symbol, coin_id=coin_id)
    catalyst = any(_term_in_text(text, term) for term in _CATALYST_TERMS) or bool(payload.get("event_time"))
    mechanism = any(_term_in_text(text, term) for term in _MECHANISM_TERMS)
    if _publisher_noise(text, symbol=symbol, coin_id=coin_id):
        return EvidenceSpecificity.SOURCE_NOISE.value, 20.0, ["publisher_or_word_collision_noise"]
    if asset and catalyst and mechanism:
        return EvidenceSpecificity.DIRECT_TOKEN_MECHANISM.value, 90.0, ["direct_token_mechanism"]
    if asset and catalyst:
        return EvidenceSpecificity.TOKEN_AND_CATALYST.value, 72.0, ["token_and_catalyst"]
    if catalyst:
        return EvidenceSpecificity.CATALYST_ONLY.value, 46.0, ["catalyst_only"]
    if asset:
        score = 50.0
        if category in {"listing_liquidity_event", "unlock_supply_pressure", "security_or_regulatory_shock"} and mechanism:
            score = 70.0
        return EvidenceSpecificity.TOKEN_ONLY.value, score, ["token_only"]
    return EvidenceSpecificity.GENERIC_CONTEXT.value, 34.0, ["generic_context"]


def _asset_present(text: str, *, symbol: str | None, coin_id: str | None) -> bool:
    terms = [symbol, coin_id, str(coin_id or "").replace("-", " ")]
    if symbol:
        terms.extend((f"${symbol}", f"{symbol}usdt"))
    return any(_term_in_text(text, str(term)) for term in terms if str(term or "").strip())


def _publisher_noise(text: str, *, symbol: str | None, coin_id: str | None) -> bool:
    symbol_text = clean_text(symbol or coin_id or "")
    if not symbol_text:
        return False
    return (
        (symbol_text == "btc" and "bitcoin world" in text and "$btc" not in text and "btcusdt" not in text)
        or (symbol_text == "xrp" and "ripple effects" in text and "$xrp" not in text)
        or (symbol_text == "kcs" and "kucoin source" in text and "$kcs" not in text)
    )


def _warnings(source_class: str, specificity: str, text: str) -> tuple[str, ...]:
    warnings: list[str] = []
    if source_class in {SourceClass.BROAD_NEWS.value, SourceClass.PREDICTION_MARKET.value} and specificity in {
        EvidenceSpecificity.CATALYST_ONLY.value,
        EvidenceSpecificity.GENERIC_CONTEXT.value,
    }:
        warnings.append("source_does_not_explain_token_impact")
    if any(term in text for term in _LOW_QUALITY_TERMS):
        warnings.append("low_signal_market_recap")
    return tuple(warnings)


def _raw_mapping(raw: RawDiscoveredEvent | Mapping[str, Any] | None) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, Mapping):
        return dict(raw)
    return {
        "provider": raw.provider,
        "source_url": raw.source_url,
        "title": raw.title,
        "body": raw.body,
        "raw_json": raw.raw_json or {},
        "source_confidence": raw.source_confidence,
    }


def _prior_score(value: float | None) -> float | None:
    try:
        if value is None:
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    if 0.0 <= number <= 1.0:
        number *= 100.0
    return max(0.0, min(100.0, number))


def _term_in_text(text: str, term: str) -> bool:
    needle = clean_text(term)
    if not text or not needle:
        return False
    return f" {needle} " in f" {text} "
