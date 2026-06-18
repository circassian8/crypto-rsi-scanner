"""Operational profiles for research-only Event Alpha Radar runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class EventAlphaProfile:
    name: str
    description: str
    config_overrides: Mapping[str, Any]
    with_llm: bool = False
    send: bool = False


def profile_names() -> tuple[str, ...]:
    return tuple(_PROFILES)


def get_profile(name: str) -> EventAlphaProfile:
    key = name.strip().lower()
    try:
        return _PROFILES[key]
    except KeyError as exc:
        raise ValueError(f"unknown Event Alpha profile {name!r}; choose one of: {', '.join(profile_names())}") from exc


def format_profile_report(profile: EventAlphaProfile) -> str:
    rows = [
        "=" * 76,
        "EVENT ALPHA PROFILE REPORT (research-only)",
        "=" * 76,
        f"profile={profile.name}",
        profile.description,
        f"with_llm={str(profile.with_llm).lower()} · send_requested={str(profile.send).lower()}",
        "",
        "config overrides:",
    ]
    if not profile.config_overrides:
        rows.append("- none")
    else:
        for key, value in sorted(profile.config_overrides.items()):
            rows.append(f"- {key}={value}")
    return "\n".join(rows)


_FIXTURE_UNIVERSE = Path("fixtures/coingecko_smoke/top_markets.json")
_DEFAULT_RSS_URLS = Path("fixtures/event_discovery/public_rss_feeds.txt")


_PROFILES: dict[str, EventAlphaProfile] = {
    "fixture": EventAlphaProfile(
        name="fixture",
        description="Offline fixture Event Alpha cycle with market anomaly detection and artifact routing.",
        config_overrides={
            "EVENT_DISCOVERY_UNIVERSE_PATH": _FIXTURE_UNIVERSE,
            "EVENT_DISCOVERY_UNIVERSE_LIVE": False,
            "EVENT_MARKET_ENRICHMENT_ENABLED": True,
            "EVENT_ANOMALY_SCANNER_ENABLED": True,
            "EVENT_ANOMALY_MIN_RETURN_24H": 0.03,
            "EVENT_ANOMALY_MIN_VOLUME_MCAP": 0.05,
            "EVENT_CATALYST_SEARCH_ENABLED": True,
            "EVENT_CATALYST_SEARCH_PROVIDER": "fixture",
            "EVENT_CATALYST_SEARCH_PROVIDERS": ("fixture",),
            "EVENT_WATCHLIST_ENABLED": True,
            "EVENT_ALPHA_ROUTER_ENABLED": True,
        },
    ),
    "no_key_live": EventAlphaProfile(
        name="no_key_live",
        description="No-key live research cycle using public RSS, GDELT, Polymarket, and live CoinGecko universe.",
        config_overrides={
            "EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE": True,
            "EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS_PATH": _DEFAULT_RSS_URLS,
            "EVENT_DISCOVERY_GDELT_LIVE": True,
            "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE": True,
            "EVENT_DISCOVERY_UNIVERSE_LIVE": True,
            "EVENT_DISCOVERY_UNIVERSE_FETCH_LIMIT": 250,
            "EVENT_MARKET_ENRICHMENT_ENABLED": True,
            "EVENT_ANOMALY_SCANNER_ENABLED": True,
            "EVENT_CATALYST_SEARCH_ENABLED": True,
            "EVENT_CATALYST_SEARCH_PROVIDER": "gdelt,rss,polymarket",
            "EVENT_CATALYST_SEARCH_PROVIDERS": ("gdelt", "rss", "polymarket"),
            "EVENT_WATCHLIST_ENABLED": True,
            "EVENT_ALPHA_ROUTER_ENABLED": True,
        },
    ),
    "no_key_llm": EventAlphaProfile(
        name="no_key_llm",
        description="No-key live sources with fixture LLM extraction/relationship metadata for offline-safe testing.",
        config_overrides={
            "EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE": True,
            "EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS_PATH": _DEFAULT_RSS_URLS,
            "EVENT_DISCOVERY_GDELT_LIVE": True,
            "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE": True,
            "EVENT_DISCOVERY_UNIVERSE_LIVE": True,
            "EVENT_MARKET_ENRICHMENT_ENABLED": True,
            "EVENT_ANOMALY_SCANNER_ENABLED": True,
            "EVENT_CATALYST_SEARCH_ENABLED": True,
            "EVENT_CATALYST_SEARCH_PROVIDER": "gdelt,rss,polymarket",
            "EVENT_CATALYST_SEARCH_PROVIDERS": ("gdelt", "rss", "polymarket"),
            "EVENT_LLM_PROVIDER": "fixture",
            "EVENT_LLM_MODE": "advisory",
            "EVENT_LLM_EXTRACTOR_PROVIDER": "fixture",
            "EVENT_LLM_EXTRACTOR_MODE": "advisory",
            "EVENT_WATCHLIST_ENABLED": True,
            "EVENT_ALPHA_ROUTER_ENABLED": True,
        },
        with_llm=True,
    ),
    "api_live": EventAlphaProfile(
        name="api_live",
        description="API-backed live event sources where configured, with no LLM calls by default.",
        config_overrides={
            "EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE": True,
            "EVENT_DISCOVERY_GDELT_LIVE": True,
            "EVENT_DISCOVERY_CRYPTOPANIC_LIVE": True,
            "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE": True,
            "EVENT_DISCOVERY_UNIVERSE_LIVE": True,
            "EVENT_MARKET_ENRICHMENT_ENABLED": True,
            "EVENT_ANOMALY_SCANNER_ENABLED": True,
            "EVENT_CATALYST_SEARCH_ENABLED": True,
            "EVENT_CATALYST_SEARCH_PROVIDER": "gdelt,rss,cryptopanic,polymarket",
            "EVENT_CATALYST_SEARCH_PROVIDERS": ("gdelt", "rss", "cryptopanic", "polymarket"),
            "EVENT_WATCHLIST_ENABLED": True,
            "EVENT_ALPHA_ROUTER_ENABLED": True,
        },
    ),
    "full_llm_live": EventAlphaProfile(
        name="full_llm_live",
        description="Live public/API sources with opt-in OpenAI extraction and relationship advisory.",
        config_overrides={
            "EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE": True,
            "EVENT_DISCOVERY_GDELT_LIVE": True,
            "EVENT_DISCOVERY_CRYPTOPANIC_LIVE": True,
            "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE": True,
            "EVENT_DISCOVERY_UNIVERSE_LIVE": True,
            "EVENT_MARKET_ENRICHMENT_ENABLED": True,
            "EVENT_ANOMALY_SCANNER_ENABLED": True,
            "EVENT_CATALYST_SEARCH_ENABLED": True,
            "EVENT_CATALYST_SEARCH_PROVIDER": "gdelt,rss,cryptopanic,polymarket",
            "EVENT_CATALYST_SEARCH_PROVIDERS": ("gdelt", "rss", "cryptopanic", "polymarket"),
            "EVENT_LLM_ENABLED": True,
            "EVENT_LLM_PROVIDER": "openai",
            "EVENT_LLM_MODE": "advisory",
            "EVENT_LLM_EXTRACTOR_ENABLED": True,
            "EVENT_LLM_EXTRACTOR_PROVIDER": "openai",
            "EVENT_LLM_EXTRACTOR_MODE": "advisory",
            "EVENT_WATCHLIST_ENABLED": True,
            "EVENT_ALPHA_ROUTER_ENABLED": True,
        },
        with_llm=True,
    ),
    "research_send": EventAlphaProfile(
        name="research_send",
        description="Research-send profile; still requires --event-alert-send and RSI_EVENT_ALERTS_ENABLED=1.",
        config_overrides={
            "EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE": True,
            "EVENT_DISCOVERY_GDELT_LIVE": True,
            "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE": True,
            "EVENT_DISCOVERY_UNIVERSE_LIVE": True,
            "EVENT_MARKET_ENRICHMENT_ENABLED": True,
            "EVENT_ANOMALY_SCANNER_ENABLED": True,
            "EVENT_CATALYST_SEARCH_ENABLED": True,
            "EVENT_CATALYST_SEARCH_PROVIDER": "gdelt,rss,polymarket",
            "EVENT_CATALYST_SEARCH_PROVIDERS": ("gdelt", "rss", "polymarket"),
            "EVENT_LLM_PROVIDER": "fixture",
            "EVENT_LLM_MODE": "advisory",
            "EVENT_LLM_EXTRACTOR_PROVIDER": "fixture",
            "EVENT_LLM_EXTRACTOR_MODE": "advisory",
            "EVENT_WATCHLIST_ENABLED": True,
            "EVENT_ALPHA_ROUTER_ENABLED": True,
        },
        with_llm=True,
        send=True,
    ),
}
