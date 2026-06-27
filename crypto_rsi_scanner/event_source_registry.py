"""Source registry and coverage semantics for Event Alpha research evidence.

This module is pure metadata. It classifies where evidence came from, what that
source can safely prove, and whether missing evidence from that source should be
treated as meaningful. It cannot create alerts, trades, paper rows, live RSI
signals, or event-fade triggers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping
from urllib.parse import parse_qs, urlparse

from .event_resolver import clean_text


class SourceClass(str, Enum):
    OFFICIAL_PROJECT = "official_project"
    OFFICIAL_EXCHANGE = "official_exchange"
    STRUCTURED_CALENDAR = "structured_calendar"
    STRUCTURED_UNLOCK = "structured_unlock"
    CRYPTOPANIC_TAGGED = "cryptopanic_tagged"
    CRYPTO_NEWS = "crypto_news"
    BROAD_NEWS = "broad_news"
    PREDICTION_MARKET = "prediction_market"
    MARKET_RECAP = "market_recap"
    DERIVATIVES_DATA = "derivatives_data"
    SUPPLY_DATA = "supply_data"
    SEO_OR_AFFILIATE = "seo_or_affiliate"
    SOCIAL_OR_UNKNOWN = "social_or_unknown"


class SourceMission(str, Enum):
    TOKEN_IDENTITY = "token_identity"
    CATALYST_CONFIRMATION = "catalyst_confirmation"
    EVENT_TIME_CONFIRMATION = "event_time_confirmation"
    IMPACT_PATH_VALIDATION = "impact_path_validation"
    MARKET_CONFIRMATION = "market_confirmation"
    DERIVATIVES_CONFIRMATION = "derivatives_confirmation"
    SUPPLY_CONFIRMATION = "supply_confirmation"
    EXTERNAL_CONTEXT = "external_context"
    SOURCE_NOISE_CONTROL = "source_noise_control"


class ProviderCoverageStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    NOT_CONFIGURED = "not_configured"


@dataclass(frozen=True)
class SourceDescriptor:
    provider: str
    source_domain: str = ""
    source_url: str = ""
    source_class: str = SourceClass.SOCIAL_OR_UNKNOWN.value
    default_mission: str = SourceMission.EXTERNAL_CONTEXT.value
    source_quality_prior: float = 35.0
    confidence_cap: float = 50.0
    can_validate_token_identity: bool = False
    can_validate_catalyst: bool = False
    can_validate_impact_path: bool = False
    can_validate_event_time: bool = False
    reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourceRegistryAssessment:
    provider: str
    source_domain: str
    source_class: str
    source_mission: str
    source_quality_prior: float
    confidence_cap: float
    provider_coverage_status: str = ProviderCoverageStatus.COMPLETE.value
    can_validate_token_identity: bool = False
    can_validate_catalyst: bool = False
    can_validate_impact_path: bool = False
    can_validate_event_time: bool = False
    evidence_absence_is_meaningful: bool = False
    quality_capped: bool = False
    cryptopanic_currency_tag_match: bool = False
    narrative_heat: bool = False
    reason_codes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_metadata(self) -> dict[str, Any]:
        return {
            "source_provider": self.provider,
            "source_domain": self.source_domain,
            "source_class": self.source_class,
            "source_mission": self.source_mission,
            "source_quality_prior": self.source_quality_prior,
            "source_confidence_cap": self.confidence_cap,
            "provider_coverage_status": self.provider_coverage_status,
            "can_validate_token_identity": self.can_validate_token_identity,
            "can_validate_catalyst": self.can_validate_catalyst,
            "can_validate_impact_path": self.can_validate_impact_path,
            "can_validate_event_time": self.can_validate_event_time,
            "evidence_absence_is_meaningful": self.evidence_absence_is_meaningful,
            "source_quality_capped": self.quality_capped,
            "cryptopanic_currency_tag_match": self.cryptopanic_currency_tag_match,
            "narrative_heat": self.narrative_heat,
            "source_registry_reasons": self.reason_codes,
            "source_registry_warnings": self.warnings,
        }


@dataclass(frozen=True)
class FeedHealth:
    feed_url: str
    source_domain: str
    source_class: str
    quality: str
    last_success_at: str | None = None
    last_failure_at: str | None = None
    failure_type: str | None = None
    rows_fetched: int = 0
    rows_kept: int = 0
    rows_rejected: int = 0
    failure_count: int = 0
    quarantined: bool = False
    cooldown_reason: str | None = None
    reason_codes: tuple[str, ...] = ()


_OFFICIAL_EXCHANGE_HINTS = ("binance", "bybit", "coinbase", "okx", "kucoin", "bitget", "kraken")
_STRUCTURED_CALENDAR_HINTS = ("coinmarketcal", "coindar", "messari")
_UNLOCK_HINTS = ("tokenomist", "unlock", "vesting")
_DERIVATIVES_HINTS = ("coinalyze", "futures", "funding", "open-interest", "open_interest")
_SUPPLY_HINTS = ("etherscan", "arkham", "dune", "tokenomist")
_CRYPTO_NEWS_HINTS = ("coindesk", "cointelegraph", "decrypt", "theblock", "blockworks", "cryptoslate")
_SEO_HINTS = ("price prediction", "coupon", "invite code", "best crypto to buy", "sponsored")
_MARKET_RECAP_HINTS = ("market recap", "daily recap", "weekly recap", "top gainers", "crypto prices today")


def source_descriptor_for(
    provider: str | None = None,
    *,
    source_url: str | None = None,
    raw_json: Mapping[str, Any] | None = None,
    text: str | None = None,
) -> SourceDescriptor:
    """Return the default source contract for a provider/domain."""
    provider_text = clean_text(provider or "")
    url = str(source_url or "")
    parsed = urlparse(url)
    domain = clean_text(parsed.netloc)
    payload = raw_json or {}
    origin = clean_text(payload.get("source_origin") or payload.get("provider") or "")
    joined = " ".join(part for part in (provider_text, domain, origin, clean_text(text or "")) if part)
    reasons: list[str] = []

    if any(hint in joined for hint in _OFFICIAL_EXCHANGE_HINTS):
        reasons.append("official_exchange_source")
        return SourceDescriptor(
            provider=provider_text or "unknown",
            source_domain=domain,
            source_url=url,
            source_class=SourceClass.OFFICIAL_EXCHANGE.value,
            default_mission=SourceMission.CATALYST_CONFIRMATION.value,
            source_quality_prior=92.0,
            confidence_cap=95.0,
            can_validate_token_identity=True,
            can_validate_catalyst=True,
            can_validate_impact_path=True,
            can_validate_event_time=True,
            reason_codes=tuple(reasons),
        )
    if any(hint in joined for hint in ("official", "project blog", "github.com", "medium.com")):
        reasons.append("official_project_source")
        return SourceDescriptor(
            provider=provider_text or "unknown",
            source_domain=domain,
            source_url=url,
            source_class=SourceClass.OFFICIAL_PROJECT.value,
            default_mission=SourceMission.IMPACT_PATH_VALIDATION.value,
            source_quality_prior=88.0,
            confidence_cap=95.0,
            can_validate_token_identity=True,
            can_validate_catalyst=True,
            can_validate_impact_path=True,
            can_validate_event_time=True,
            reason_codes=tuple(reasons),
        )
    if any(hint in joined for hint in _UNLOCK_HINTS):
        reasons.append("structured_unlock_source")
        return SourceDescriptor(
            provider=provider_text or "unknown",
            source_domain=domain,
            source_url=url,
            source_class=SourceClass.STRUCTURED_UNLOCK.value,
            default_mission=SourceMission.SUPPLY_CONFIRMATION.value,
            source_quality_prior=88.0,
            confidence_cap=92.0,
            can_validate_token_identity=True,
            can_validate_catalyst=True,
            can_validate_impact_path=True,
            can_validate_event_time=True,
            reason_codes=tuple(reasons),
        )
    if any(hint in joined for hint in _STRUCTURED_CALENDAR_HINTS):
        reasons.append("structured_calendar_source")
        return SourceDescriptor(
            provider=provider_text or "unknown",
            source_domain=domain,
            source_url=url,
            source_class=SourceClass.STRUCTURED_CALENDAR.value,
            default_mission=SourceMission.CATALYST_CONFIRMATION.value,
            source_quality_prior=84.0,
            confidence_cap=90.0,
            can_validate_token_identity=True,
            can_validate_catalyst=True,
            can_validate_impact_path=False,
            can_validate_event_time=True,
            reason_codes=tuple(reasons),
        )
    if any(hint in joined for hint in _DERIVATIVES_HINTS):
        reasons.append("derivatives_data_source")
        return SourceDescriptor(
            provider=provider_text or "unknown",
            source_domain=domain,
            source_url=url,
            source_class=SourceClass.DERIVATIVES_DATA.value,
            default_mission=SourceMission.DERIVATIVES_CONFIRMATION.value,
            source_quality_prior=80.0,
            confidence_cap=90.0,
            can_validate_catalyst=False,
            reason_codes=tuple(reasons),
        )
    if any(hint in joined for hint in _SUPPLY_HINTS):
        reasons.append("supply_data_source")
        return SourceDescriptor(
            provider=provider_text or "unknown",
            source_domain=domain,
            source_url=url,
            source_class=SourceClass.SUPPLY_DATA.value,
            default_mission=SourceMission.SUPPLY_CONFIRMATION.value,
            source_quality_prior=78.0,
            confidence_cap=88.0,
            can_validate_token_identity=True,
            can_validate_catalyst=True,
            can_validate_impact_path=True,
            reason_codes=tuple(reasons),
        )
    if "cryptopanic" in joined:
        tags = _currency_tags(payload)
        reasons.append("cryptopanic_tagged" if tags else "cryptopanic_untagged")
        return SourceDescriptor(
            provider=provider_text or "unknown",
            source_domain=domain,
            source_url=url,
            source_class=SourceClass.CRYPTOPANIC_TAGGED.value if tags else SourceClass.CRYPTO_NEWS.value,
            default_mission=SourceMission.CATALYST_CONFIRMATION.value,
            source_quality_prior=74.0 if tags else 62.0,
            confidence_cap=88.0 if tags else 78.0,
            can_validate_token_identity=bool(tags),
            can_validate_catalyst=True,
            can_validate_impact_path=bool(tags),
            can_validate_event_time=False,
            reason_codes=tuple(reasons),
        )
    if any(hint in joined for hint in _SEO_HINTS):
        reasons.append("seo_or_affiliate_source")
        return SourceDescriptor(
            provider=provider_text or "unknown",
            source_domain=domain,
            source_url=url,
            source_class=SourceClass.SEO_OR_AFFILIATE.value,
            default_mission=SourceMission.SOURCE_NOISE_CONTROL.value,
            source_quality_prior=20.0,
            confidence_cap=30.0,
            reason_codes=tuple(reasons),
        )
    if any(hint in joined for hint in _MARKET_RECAP_HINTS):
        reasons.append("market_recap_source")
        return SourceDescriptor(
            provider=provider_text or "unknown",
            source_domain=domain,
            source_url=url,
            source_class=SourceClass.MARKET_RECAP.value,
            default_mission=SourceMission.SOURCE_NOISE_CONTROL.value,
            source_quality_prior=32.0,
            confidence_cap=40.0,
            reason_codes=tuple(reasons),
        )
    if "polymarket" in joined or "prediction market" in joined:
        reasons.append("prediction_market_context_source")
        return SourceDescriptor(
            provider=provider_text or "unknown",
            source_domain=domain,
            source_url=url,
            source_class=SourceClass.PREDICTION_MARKET.value,
            default_mission=SourceMission.EXTERNAL_CONTEXT.value,
            source_quality_prior=52.0,
            confidence_cap=62.0,
            can_validate_catalyst=True,
            can_validate_event_time=True,
            reason_codes=tuple(reasons),
        )
    if any(hint in joined for hint in _CRYPTO_NEWS_HINTS):
        reasons.append("crypto_news_source")
        return SourceDescriptor(
            provider=provider_text or "unknown",
            source_domain=domain,
            source_url=url,
            source_class=SourceClass.CRYPTO_NEWS.value,
            default_mission=SourceMission.CATALYST_CONFIRMATION.value,
            source_quality_prior=65.0,
            confidence_cap=80.0,
            can_validate_catalyst=True,
            reason_codes=tuple(reasons),
        )
    if "gdelt" in joined or domain:
        reasons.append("broad_news_source")
        return SourceDescriptor(
            provider=provider_text or "unknown",
            source_domain=domain,
            source_url=url,
            source_class=SourceClass.BROAD_NEWS.value,
            default_mission=SourceMission.EXTERNAL_CONTEXT.value,
            source_quality_prior=48.0,
            confidence_cap=58.0,
            can_validate_catalyst=True,
            reason_codes=tuple(reasons),
        )
    return SourceDescriptor(
        provider=provider_text or "unknown",
        source_domain=domain,
        source_url=url,
        reason_codes=("unknown_source",),
    )


def assess_source(
    row: Mapping[str, Any] | None = None,
    *,
    provider: str | None = None,
    source_url: str | None = None,
    raw_json: Mapping[str, Any] | None = None,
    text: str | None = None,
    symbol: str | None = None,
    coin_id: str | None = None,
    playbook_type: str | None = None,
    mission: str | SourceMission | None = None,
    provider_coverage_status: str | ProviderCoverageStatus | None = None,
) -> SourceRegistryAssessment:
    """Assess one evidence row under the source registry."""
    mapping = dict(row or {})
    payload = dict(raw_json or mapping.get("raw_json") or mapping.get("score_components") or {})
    provider_value = provider or mapping.get("provider") or mapping.get("source_provider") or mapping.get("source")
    source_url_value = source_url or mapping.get("source_url") or mapping.get("url")
    text_value = " ".join(
        str(value or "")
        for value in (
            text,
            mapping.get("title"),
            mapping.get("body"),
            mapping.get("description"),
            mapping.get("event_name"),
            mapping.get("canonical_incident_name"),
            mapping.get("evidence_quotes"),
        )
    )
    descriptor = source_descriptor_for(
        str(provider_value or ""),
        source_url=str(source_url_value or ""),
        raw_json=payload,
        text=text_value,
    )
    status = _coverage_status(provider_coverage_status or mapping.get("provider_coverage_status"))
    mission_value = str(mission.value if isinstance(mission, SourceMission) else mission or descriptor.default_mission)
    reasons = list(descriptor.reason_codes)
    warnings: list[str] = []
    prior = descriptor.source_quality_prior
    cap = descriptor.confidence_cap
    can_identity = descriptor.can_validate_token_identity
    can_catalyst = descriptor.can_validate_catalyst
    can_impact = descriptor.can_validate_impact_path
    can_time = descriptor.can_validate_event_time

    tags = _currency_tags(payload)
    tag_match = _asset_tag_match(tags, symbol=symbol or mapping.get("symbol") or mapping.get("validated_symbol"), coin_id=coin_id or mapping.get("coin_id") or mapping.get("validated_coin_id"))
    if descriptor.source_class == SourceClass.CRYPTOPANIC_TAGGED.value:
        if tag_match:
            prior = max(prior, 86.0)
            cap = max(cap, 92.0)
            can_identity = True
            can_impact = True
            reasons.append("cryptopanic_currency_tag_match")
        else:
            warnings.append("cryptopanic_missing_matching_currency_tag")
        if _narrative_heat(payload, text_value):
            prior = max(prior, 82.0)
            reasons.append("narrative_heat")

    asset_named = _asset_mentioned(text_value, symbol=symbol or mapping.get("symbol") or mapping.get("validated_symbol"), coin_id=coin_id or mapping.get("coin_id") or mapping.get("validated_coin_id"))
    if descriptor.source_class == SourceClass.PREDICTION_MARKET.value:
        if asset_named:
            can_identity = True
            can_impact = False
            cap = max(cap, 65.0)
            reasons.append("prediction_market_token_named_context")
        else:
            can_identity = False
            can_impact = False
            reasons.append("prediction_market_external_context_only")
            warnings.append("token_identity_not_validated_by_prediction_market")
    if descriptor.source_class == SourceClass.BROAD_NEWS.value:
        if not asset_named:
            warnings.append("broad_news_without_token_identity")
        can_identity = bool(asset_named)
        can_impact = bool(asset_named and _impact_language(text_value))
        cap = min(cap, 58.0 if can_impact else 52.0)
        reasons.append("broad_news_confidence_capped")
    if descriptor.source_class in {SourceClass.MARKET_RECAP.value, SourceClass.SEO_OR_AFFILIATE.value}:
        can_identity = False
        can_catalyst = False
        can_impact = False
        warnings.append("diagnostic_only_low_quality_source")
    if status != ProviderCoverageStatus.COMPLETE.value:
        warnings.append(f"provider_coverage_{status}")
        reasons.append("source_coverage_gap")
    absence = evidence_absence_is_meaningful(
        provider=descriptor.provider,
        source_class=descriptor.source_class,
        coverage_status=status,
        mission=mission_value,
    )
    quality_capped = cap < 80.0 or status in {
        ProviderCoverageStatus.DEGRADED.value,
        ProviderCoverageStatus.UNAVAILABLE.value,
        ProviderCoverageStatus.NOT_CONFIGURED.value,
    }
    if quality_capped:
        reasons.append("source_quality_capped")
    return SourceRegistryAssessment(
        provider=descriptor.provider,
        source_domain=descriptor.source_domain,
        source_class=descriptor.source_class,
        source_mission=mission_value,
        source_quality_prior=round(prior, 2),
        confidence_cap=round(cap, 2),
        provider_coverage_status=status,
        can_validate_token_identity=can_identity,
        can_validate_catalyst=can_catalyst,
        can_validate_impact_path=can_impact,
        can_validate_event_time=can_time,
        evidence_absence_is_meaningful=absence,
        quality_capped=quality_capped,
        cryptopanic_currency_tag_match=tag_match,
        narrative_heat="narrative_heat" in reasons,
        reason_codes=tuple(dict.fromkeys(reasons)),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def evidence_absence_is_meaningful(
    *,
    provider: str | None = None,
    source_class: str | None = None,
    coverage_status: str | ProviderCoverageStatus | None = None,
    mission: str | SourceMission | None = None,
) -> bool:
    """Return whether absence from this provider should lower confidence."""
    status = _coverage_status(coverage_status)
    if status != ProviderCoverageStatus.COMPLETE.value:
        return False
    source_class_value = str(source_class or "")
    mission_value = str(mission.value if isinstance(mission, SourceMission) else mission or "")
    strong_classes = {
        SourceClass.OFFICIAL_PROJECT.value,
        SourceClass.OFFICIAL_EXCHANGE.value,
        SourceClass.STRUCTURED_CALENDAR.value,
        SourceClass.STRUCTURED_UNLOCK.value,
        SourceClass.DERIVATIVES_DATA.value,
        SourceClass.SUPPLY_DATA.value,
    }
    if source_class_value in strong_classes:
        return True
    if source_class_value == SourceClass.CRYPTOPANIC_TAGGED.value and mission_value in {
        SourceMission.CATALYST_CONFIRMATION.value,
        SourceMission.IMPACT_PATH_VALIDATION.value,
    }:
        return True
    return False


def coverage_gap_reason(provider: str | None, status: str | ProviderCoverageStatus | None) -> str | None:
    value = _coverage_status(status)
    if value == ProviderCoverageStatus.COMPLETE.value:
        return None
    return f"provider_coverage_{value}:{provider or 'unknown'}"


def feed_health_from_fetch(
    *,
    feed_url: str,
    source_domain: str | None = None,
    last_success_at: str | None = None,
    last_failure_at: str | None = None,
    failure_type: str | None = None,
    rows_fetched: int = 0,
    rows_kept: int = 0,
    rows_rejected: int = 0,
    failure_count: int = 0,
) -> FeedHealth:
    domain = clean_text(source_domain or urlparse(str(feed_url)).netloc)
    descriptor = source_descriptor_for("project_blog_rss", source_url=feed_url, text=domain)
    failure = clean_text(failure_type or "")
    reasons: list[str] = list(descriptor.reason_codes)
    quarantined = False
    cooldown_reason = None
    if failure in {"http_403", "403", "feed_failure_403"}:
        quarantined = True
        cooldown_reason = "feed_403_quarantined"
        reasons.append("feed_403_quarantined")
    elif failure_count >= 3:
        quarantined = True
        cooldown_reason = "repeated_feed_failure_cooldown"
        reasons.append("repeated_feed_failure_cooldown")
    quality = "high" if descriptor.source_class in {SourceClass.OFFICIAL_PROJECT.value, SourceClass.OFFICIAL_EXCHANGE.value} else "medium"
    if descriptor.source_class in {SourceClass.MARKET_RECAP.value, SourceClass.SEO_OR_AFFILIATE.value}:
        quality = "low"
        reasons.append("diagnostic_only_feed")
    return FeedHealth(
        feed_url=feed_url,
        source_domain=domain,
        source_class=descriptor.source_class,
        quality=quality,
        last_success_at=last_success_at,
        last_failure_at=last_failure_at,
        failure_type=failure_type,
        rows_fetched=max(0, int(rows_fetched or 0)),
        rows_kept=max(0, int(rows_kept or 0)),
        rows_rejected=max(0, int(rows_rejected or 0)),
        failure_count=max(0, int(failure_count or 0)),
        quarantined=quarantined,
        cooldown_reason=cooldown_reason,
        reason_codes=tuple(dict.fromkeys(reasons)),
    )


def format_source_coverage_summary(rows: Iterable[Mapping[str, Any]]) -> str:
    counts: dict[str, int] = {}
    coverage: dict[str, int] = {}
    gaps = 0
    for row in rows:
        assessment = assess_source(row)
        counts[assessment.source_class] = counts.get(assessment.source_class, 0) + 1
        coverage[assessment.provider_coverage_status] = coverage.get(assessment.provider_coverage_status, 0) + 1
        if assessment.warnings or not assessment.evidence_absence_is_meaningful:
            gaps += 1
    if not counts:
        return "source_classes=none; coverage=none; gaps=0"
    source_text = ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
    coverage_text = ", ".join(f"{key}={value}" for key, value in sorted(coverage.items()))
    return f"source_classes={source_text}; coverage={coverage_text}; gaps={gaps}"


def _coverage_status(value: str | ProviderCoverageStatus | None) -> str:
    if isinstance(value, ProviderCoverageStatus):
        return value.value
    text = str(value or "").strip().casefold()
    if text in {item.value for item in ProviderCoverageStatus}:
        return text
    if text in {"healthy", "ok", "ready", "success"}:
        return ProviderCoverageStatus.COMPLETE.value
    if text in {"warning", "rate_limited"}:
        return ProviderCoverageStatus.DEGRADED.value
    if text in {"missing", "disabled", "not_ready"}:
        return ProviderCoverageStatus.NOT_CONFIGURED.value
    return ProviderCoverageStatus.COMPLETE.value


def _currency_tags(payload: Mapping[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    for key in ("currencies", "currency_tags", "currencyTags", "tags"):
        raw = payload.get(key)
        if isinstance(raw, Mapping):
            raw = raw.values()
        if isinstance(raw, str):
            values.extend(part.strip() for part in raw.replace(";", ",").split(","))
        elif isinstance(raw, Iterable):
            for item in raw:
                if isinstance(item, Mapping):
                    for child_key in ("code", "symbol", "slug", "coin_id", "title", "currency"):
                        if item.get(child_key):
                            values.append(str(item.get(child_key)))
                elif item not in (None, ""):
                    values.append(str(item))
    return tuple(dict.fromkeys(clean_text(value).upper() for value in values if clean_text(value)))


def _asset_tag_match(tags: Iterable[str], *, symbol: object = None, coin_id: object = None) -> bool:
    clean_tags = {clean_text(value).replace("-", " ").upper() for value in tags}
    candidates = {
        clean_text(symbol or "").upper(),
        clean_text(coin_id or "").replace("-", " ").upper(),
    }
    return bool(clean_tags.intersection(value for value in candidates if value))


def _narrative_heat(payload: Mapping[str, Any], text: str) -> bool:
    joined = clean_text(" ".join(str(value or "") for value in (
        text,
        payload.get("kind"),
        payload.get("filter"),
        payload.get("status"),
        payload.get("vote"),
        payload.get("metadata"),
    )))
    return any(token in joined for token in ("hot", "rising", "important", "bullish"))


def _asset_mentioned(text: str, *, symbol: object = None, coin_id: object = None) -> bool:
    clean = clean_text(text)
    terms = []
    if symbol:
        terms.extend((str(symbol), f"${symbol}", f"{symbol}usdt"))
    if coin_id:
        terms.extend((str(coin_id), str(coin_id).replace("-", " ")))
    for term in terms:
        norm = clean_text(term)
        if norm and norm in clean:
            return True
    return False


def _impact_language(text: str) -> bool:
    clean = clean_text(text)
    return any(token in clean for token in (
        "because",
        "drives",
        "benefits",
        "exposure",
        "value capture",
        "listed",
        "unlock",
        "exploit",
        "hack",
        "fan token",
        "revenue",
        "volume",
    ))
