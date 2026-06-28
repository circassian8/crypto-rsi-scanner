"""Playbook-specific evidence source packs for Event Alpha.

Source packs define which evidence sources are preferred for each research
playbook. They are advisory metadata for reports, cards, near-miss refresh, and
evidence planning only; they do not create alert tiers or event-fade triggers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from . import event_source_registry


@dataclass(frozen=True)
class SourcePack:
    name: str
    playbooks: tuple[str, ...]
    preferred_source_classes: tuple[str, ...]
    preferred_providers: tuple[str, ...]
    minimum_evidence: tuple[str, ...]
    validation_requirements: tuple[str, ...]
    context_only_sources: tuple[str, ...] = ()
    impact_path_families: tuple[str, ...] = ()
    market_refresh_required: bool = False
    derivatives_refresh_required: bool = False
    supply_refresh_required: bool = False

    def to_metadata(self) -> dict[str, Any]:
        return {
            "source_pack": self.name,
            "source_pack_playbooks": self.playbooks,
            "source_pack_preferred_source_classes": self.preferred_source_classes,
            "source_pack_preferred_providers": self.preferred_providers,
            "source_pack_minimum_evidence": self.minimum_evidence,
            "source_pack_validation_requirements": self.validation_requirements,
            "source_pack_context_only_sources": self.context_only_sources,
            "source_pack_impact_path_families": self.impact_path_families,
            "source_pack_market_refresh_required": self.market_refresh_required,
            "source_pack_derivatives_refresh_required": self.derivatives_refresh_required,
            "source_pack_supply_refresh_required": self.supply_refresh_required,
        }


SOURCE_PACKS: dict[str, SourcePack] = {
    "listing_liquidity_pack": SourcePack(
        name="listing_liquidity_pack",
        playbooks=("listing_volatility", "direct_event", "exchange_listing"),
        preferred_source_classes=(
            event_source_registry.SourceClass.OFFICIAL_EXCHANGE.value,
            event_source_registry.SourceClass.CRYPTO_NEWS.value,
        ),
        preferred_providers=("binance_announcements", "bybit_announcements", "okx_announcements", "coinbase"),
        minimum_evidence=("official listing announcement", "asset/pair identity", "listing or trading start time"),
        validation_requirements=("official_exchange_source", "symbol_or_pair_match", "liquidity_or_volume_context"),
        impact_path_families=("listing_liquidity_event", "direct_listing"),
        market_refresh_required=True,
    ),
    "perp_listing_squeeze_pack": SourcePack(
        name="perp_listing_squeeze_pack",
        playbooks=("perp_listing_squeeze", "listing_volatility", "direct_event"),
        preferred_source_classes=(
            event_source_registry.SourceClass.OFFICIAL_EXCHANGE.value,
            event_source_registry.SourceClass.DERIVATIVES_DATA.value,
        ),
        preferred_providers=("binance_announcements", "bybit_announcements", "coinalyze", "binance_futures"),
        minimum_evidence=("official perp listing", "contract/pair identity", "funding or open-interest context"),
        validation_requirements=("official_exchange_source", "derivatives_confirmation", "market_confirmation"),
        impact_path_families=("perp_listing", "listing_liquidity_event"),
        market_refresh_required=True,
        derivatives_refresh_required=True,
    ),
    "unlock_supply_pack": SourcePack(
        name="unlock_supply_pack",
        playbooks=("unlock_supply_pressure", "direct_event"),
        preferred_source_classes=(
            event_source_registry.SourceClass.STRUCTURED_UNLOCK.value,
            event_source_registry.SourceClass.SUPPLY_DATA.value,
            event_source_registry.SourceClass.OFFICIAL_PROJECT.value,
        ),
        preferred_providers=("tokenomist", "project_blog_rss", "etherscan", "arkham", "dune"),
        minimum_evidence=("unlock size", "unlock time", "circulating/float impact"),
        validation_requirements=("structured_unlock_source", "supply_pressure", "token_identity"),
        impact_path_families=("unlock_supply_event", "unlock_supply_pressure"),
        supply_refresh_required=True,
    ),
    "proxy_preipo_rwa_pack": SourcePack(
        name="proxy_preipo_rwa_pack",
        playbooks=("proxy_attention", "proxy_fade", "rwa_preipo_proxy", "tokenized_stock_venue"),
        preferred_source_classes=(
            event_source_registry.SourceClass.OFFICIAL_PROJECT.value,
            event_source_registry.SourceClass.CRYPTOPANIC_TAGGED.value,
            event_source_registry.SourceClass.CRYPTO_NEWS.value,
            event_source_registry.SourceClass.PREDICTION_MARKET.value,
        ),
        preferred_providers=("project_blog_rss", "cryptopanic", "gdelt", "polymarket"),
        minimum_evidence=("proxy venue/instrument claim", "external catalyst", "token/venue value capture"),
        validation_requirements=("impact_path_validation", "token_identity", "market_confirmation"),
        context_only_sources=(event_source_registry.SourceClass.PREDICTION_MARKET.value, event_source_registry.SourceClass.BROAD_NEWS.value),
        impact_path_families=("venue_value_capture", "proxy_exposure", "rwa_preipo_proxy", "tokenized_stock_venue"),
        market_refresh_required=True,
        derivatives_refresh_required=True,
    ),
    "ai_ipo_proxy_pack": SourcePack(
        name="ai_ipo_proxy_pack",
        playbooks=("proxy_attention", "proxy_fade", "ai_ipo_proxy"),
        preferred_source_classes=(
            event_source_registry.SourceClass.OFFICIAL_PROJECT.value,
            event_source_registry.SourceClass.CRYPTOPANIC_TAGGED.value,
            event_source_registry.SourceClass.CRYPTO_NEWS.value,
            event_source_registry.SourceClass.BROAD_NEWS.value,
        ),
        preferred_providers=("project_blog_rss", "cryptopanic", "gdelt"),
        minimum_evidence=("AI company catalyst", "crypto asset named", "proxy or venue mechanism"),
        validation_requirements=("impact_path_validation", "asset_identity", "market_confirmation"),
        context_only_sources=(event_source_registry.SourceClass.BROAD_NEWS.value,),
        impact_path_families=("ai_ipo_proxy", "venue_value_capture", "proxy_exposure"),
        market_refresh_required=True,
    ),
    "security_shock_pack": SourcePack(
        name="security_shock_pack",
        playbooks=("security_or_regulatory_shock", "direct_event"),
        preferred_source_classes=(
            event_source_registry.SourceClass.OFFICIAL_PROJECT.value,
            event_source_registry.SourceClass.CRYPTO_NEWS.value,
            event_source_registry.SourceClass.BROAD_NEWS.value,
        ),
        preferred_providers=("project_blog_rss", "cryptopanic", "gdelt"),
        minimum_evidence=("incident source", "affected protocol/token", "cause or corrective status"),
        validation_requirements=("impact_path_validation", "incident_relevance", "market_confirmation"),
        context_only_sources=(event_source_registry.SourceClass.BROAD_NEWS.value,),
        impact_path_families=("exploit_security_event", "security_or_regulatory_shock"),
        market_refresh_required=True,
    ),
    "fan_sports_pack": SourcePack(
        name="fan_sports_pack",
        playbooks=("fan_sports_proxy", "proxy_attention"),
        preferred_source_classes=(
            event_source_registry.SourceClass.OFFICIAL_PROJECT.value,
            event_source_registry.SourceClass.STRUCTURED_CALENDAR.value,
            event_source_registry.SourceClass.CRYPTO_NEWS.value,
        ),
        preferred_providers=("sports_fixtures", "project_blog_rss", "cryptopanic", "gdelt"),
        minimum_evidence=("fixture/event time", "fan token named", "attention/demand path"),
        validation_requirements=("event_time_confirmation", "token_identity", "impact_path_validation"),
        context_only_sources=(event_source_registry.SourceClass.BROAD_NEWS.value,),
        impact_path_families=("fan_token_event", "sports_fan_proxy"),
        market_refresh_required=True,
    ),
    "political_meme_pack": SourcePack(
        name="political_meme_pack",
        playbooks=("political_meme_proxy", "proxy_attention"),
        preferred_source_classes=(
            event_source_registry.SourceClass.BROAD_NEWS.value,
            event_source_registry.SourceClass.PREDICTION_MARKET.value,
            event_source_registry.SourceClass.CRYPTO_NEWS.value,
        ),
        preferred_providers=("gdelt", "polymarket", "cryptopanic"),
        minimum_evidence=("dated political catalyst", "token named", "meme/proxy attention path"),
        validation_requirements=("external_context", "token_identity", "market_confirmation"),
        context_only_sources=(event_source_registry.SourceClass.BROAD_NEWS.value, event_source_registry.SourceClass.PREDICTION_MARKET.value),
        impact_path_families=("political_meme_proxy", "proxy_attention"),
        market_refresh_required=True,
    ),
    "strategic_investment_pack": SourcePack(
        name="strategic_investment_pack",
        playbooks=("strategic_investment", "protocol_business_event", "direct_event"),
        preferred_source_classes=(
            event_source_registry.SourceClass.OFFICIAL_PROJECT.value,
            event_source_registry.SourceClass.CRYPTO_NEWS.value,
            event_source_registry.SourceClass.BROAD_NEWS.value,
        ),
        preferred_providers=("project_blog_rss", "cryptopanic", "gdelt"),
        minimum_evidence=("investment or stake claim", "protocol/token subject", "valuation or business impact"),
        validation_requirements=("impact_path_validation", "token_identity", "second_source_confirmation", "denial_or_correction_search"),
        context_only_sources=(event_source_registry.SourceClass.MARKET_RECAP.value, event_source_registry.SourceClass.SEO_OR_AFFILIATE.value),
        impact_path_families=("strategic_investment_or_valuation", "protocol_business_event", "acquisition_or_stake"),
        market_refresh_required=True,
    ),
    "market_anomaly_pack": SourcePack(
        name="market_anomaly_pack",
        playbooks=("market_anomaly", "market_anomaly_unknown"),
        preferred_source_classes=(
            event_source_registry.SourceClass.OFFICIAL_PROJECT.value,
            event_source_registry.SourceClass.OFFICIAL_EXCHANGE.value,
            event_source_registry.SourceClass.CRYPTO_NEWS.value,
        ),
        preferred_providers=("project_blog_rss", "cryptopanic", "gdelt", "binance_announcements", "bybit_announcements"),
        minimum_evidence=("fresh market anomaly", "independent catalyst source", "asset identity"),
        validation_requirements=("market_confirmation", "source_pack_search", "impact_path_validation"),
        context_only_sources=(event_source_registry.SourceClass.MARKET_RECAP.value, event_source_registry.SourceClass.SEO_OR_AFFILIATE.value),
        impact_path_families=("market_dislocation_unknown", "market_anomaly_unknown"),
        market_refresh_required=True,
    ),
}


def get_source_pack(name: str | None) -> SourcePack:
    return SOURCE_PACKS.get(str(name or "").strip(), SOURCE_PACKS["market_anomaly_pack"])


def source_pack_for_playbook(
    playbook_type: str | None = None,
    *,
    impact_path_type: str | None = None,
    impact_category: str | None = None,
) -> SourcePack:
    text = " ".join(str(value or "") for value in (playbook_type, impact_path_type, impact_category)).casefold()
    if "perp" in text and "listing" in text:
        return SOURCE_PACKS["perp_listing_squeeze_pack"]
    if "listing" in text or "exchange_listing" in text:
        return SOURCE_PACKS["listing_liquidity_pack"]
    if "unlock" in text or "vesting" in text or "supply" in text:
        return SOURCE_PACKS["unlock_supply_pack"]
    if "spacex" in text or "preipo" in text or "pre-ipo" in text or "rwa" in text or "tokenized_stock" in text or "venue_value_capture" in text:
        return SOURCE_PACKS["proxy_preipo_rwa_pack"]
    if "ai_ipo" in text or "openai" in text or "anthropic" in text:
        return SOURCE_PACKS["ai_ipo_proxy_pack"]
    if "exploit" in text or "hack" in text or "security" in text or "regulatory" in text:
        return SOURCE_PACKS["security_shock_pack"]
    if "fan" in text or "sports" in text or "world_cup" in text:
        return SOURCE_PACKS["fan_sports_pack"]
    if "political" in text or "election" in text or "meme" in text:
        return SOURCE_PACKS["political_meme_pack"]
    if any(term in text for term in ("strategic", "investment", "valuation", "stake", "acquisition", "business_event")):
        return SOURCE_PACKS["strategic_investment_pack"]
    return SOURCE_PACKS["market_anomaly_pack"]


def evaluate_pack_evidence(
    row: Mapping[str, Any],
    *,
    pack: SourcePack | None = None,
) -> dict[str, Any]:
    selected = pack or source_pack_for_playbook(
        str(row.get("playbook_type") or row.get("latest_effective_playbook_type") or ""),
        impact_path_type=str(row.get("impact_path_type") or ""),
        impact_category=str(row.get("impact_category") or ""),
    )
    assessment = event_source_registry.assess_source(row)
    source_class = assessment.source_class
    context_only = source_class in selected.context_only_sources
    preferred = source_class in selected.preferred_source_classes
    missing = []
    if context_only:
        missing.append("source_is_context_only")
    if not preferred:
        missing.append("preferred_source_missing")
    if selected.market_refresh_required and not _has_field(row, ("market_confirmation_score", "market_confirmation", "return_24h", "volume_zscore_24h")):
        missing.append("market_confirmation")
    if selected.derivatives_refresh_required and not _has_field(row, ("derivatives_crowding", "funding_rate", "open_interest_24h_change_pct")):
        missing.append("derivatives_confirmation")
    if selected.supply_refresh_required and not _has_field(row, ("supply_pressure", "unlock_pct_circulating", "supply_event")):
        missing.append("supply_confirmation")
    return {
        **selected.to_metadata(),
        **assessment.to_metadata(),
        "source_pack_preferred_source_present": preferred,
        "source_pack_context_only": context_only,
        "source_pack_missing_evidence": tuple(dict.fromkeys(missing)),
        "source_pack_requirements_met": not missing and assessment.provider_coverage_status == event_source_registry.ProviderCoverageStatus.COMPLETE.value,
    }


def source_pack_names() -> tuple[str, ...]:
    return tuple(SOURCE_PACKS)


def _has_field(row: Mapping[str, Any], keys: Iterable[str]) -> bool:
    components = row.get("score_components") if isinstance(row.get("score_components"), Mapping) else {}
    latest = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else {}
    for key in keys:
        if row.get(key) not in (None, "", [], {}, ()):
            return True
        if components.get(key) not in (None, "", [], {}, ()):
            return True
        if latest.get(key) not in (None, "", [], {}, ()):
            return True
    return False
