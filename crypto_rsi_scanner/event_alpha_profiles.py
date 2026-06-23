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
    snapshot_policy: str = "all"
    card_auto_write: bool = False
    card_write_tiers: tuple[str, ...] = ()
    watchlist_monitor_enabled: bool = False
    targeted_market_source: str = "cycle"
    send_lane_policy: str = "no_send"
    send_guard: str = "send disabled unless --event-alert-send and RSI_EVENT_ALERTS_ENABLED=1 are both set"
    notification_burn_in: bool = False


def profile_names() -> tuple[str, ...]:
    return tuple(_PROFILES)


def get_profile(name: str) -> EventAlphaProfile:
    key = name.strip().lower()
    try:
        return _PROFILES[key]
    except KeyError as exc:
        raise ValueError(f"unknown Event Alpha profile {name!r}; choose one of: {', '.join(profile_names())}") from exc


def format_profile_report(profile: EventAlphaProfile) -> str:
    policy = artifact_policy(profile)
    rows = [
        "=" * 76,
        "EVENT ALPHA PROFILE REPORT (research-only)",
        "=" * 76,
        f"profile={profile.name}",
        profile.description,
        f"with_llm={str(profile.with_llm).lower()} · send_requested={str(profile.send).lower()}",
        f"notification_burn_in={str(profile.notification_burn_in).lower()}",
        "",
        "config overrides:",
    ]
    if not profile.config_overrides:
        rows.append("- none")
    else:
        for key, value in sorted(profile.config_overrides.items()):
            rows.append(f"- {key}={value}")
    budget_keys = [
        "EVENT_LLM_MAX_CALLS_PER_RUN",
        "EVENT_LLM_MAX_CALLS_PER_DAY",
        "EVENT_LLM_MAX_ESTIMATED_COST_USD_PER_DAY",
        "EVENT_LLM_ESTIMATED_COST_PER_CALL_USD",
        "EVENT_LLM_CACHE_TTL_HOURS",
    ]
    budget = {key: profile.config_overrides.get(key) for key in budget_keys if key in profile.config_overrides}
    if budget:
        rows.extend(["", "LLM budget defaults:"])
        for key, value in budget.items():
            rows.append(f"- {key}={value}")
    rows.extend(["", "artifact policy:"])
    for key, value in policy.items():
        rows.append(f"- {key}={value}")
    return "\n".join(rows)


def artifact_policy(profile: EventAlphaProfile) -> dict[str, Any]:
    """Return the explicit local-artifact/send contract for a profile."""
    overrides = dict(profile.config_overrides)
    tiers = overrides.get("EVENT_RESEARCH_CARDS_WRITE_TIERS", profile.card_write_tiers)
    if isinstance(tiers, str):
        tiers = tuple(part.strip() for part in tiers.split(",") if part.strip())
    else:
        tiers = tuple(tiers)
    budget = {
        "max_calls_per_run": overrides.get("EVENT_LLM_MAX_CALLS_PER_RUN", "default"),
        "max_calls_per_day": overrides.get("EVENT_LLM_MAX_CALLS_PER_DAY", "default"),
        "max_cost_usd_per_day": overrides.get("EVENT_LLM_MAX_ESTIMATED_COST_USD_PER_DAY", "default"),
        "cache_ttl_hours": overrides.get("EVENT_LLM_CACHE_TTL_HOURS", "default"),
    }
    return {
        "snapshot_policy": overrides.get("EVENT_ALPHA_SNAPSHOT_POLICY", profile.snapshot_policy),
        "card_auto_write": overrides.get("EVENT_RESEARCH_CARDS_AUTO_WRITE", profile.card_auto_write),
        "card_write_tiers": tiers,
        "watchlist_monitor_enabled": overrides.get(
            "EVENT_WATCHLIST_MONITOR_ENABLED",
            profile.watchlist_monitor_enabled,
        ),
        "targeted_market_source": overrides.get(
            "EVENT_WATCHLIST_MONITOR_MARKET_SOURCE",
            profile.targeted_market_source,
        ),
        "llm_budget_caps": budget,
        "send_lane_policy": profile.send_lane_policy,
        "send_guard": profile.send_guard,
        "notification_burn_in": profile.notification_burn_in,
    }


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
        snapshot_policy="all",
        watchlist_monitor_enabled=False,
    ),
    "no_key_live": EventAlphaProfile(
        name="no_key_live",
        description="No-key live research cycle using public RSS, GDELT, Polymarket, and live CoinGecko universe.",
        config_overrides={
            "EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE": True,
            "EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS_PATH": _DEFAULT_RSS_URLS,
            "EVENT_DISCOVERY_PROJECT_BLOG_RSS_TIMEOUT": 5.0,
            "EVENT_DISCOVERY_GDELT_LIVE": True,
            "EVENT_DISCOVERY_GDELT_TIMEOUT": 5.0,
            "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE": True,
            "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_TIMEOUT": 5.0,
            "EVENT_DISCOVERY_UNIVERSE_LIVE": True,
            "EVENT_DISCOVERY_UNIVERSE_FETCH_LIMIT": 250,
            "EVENT_MARKET_ENRICHMENT_ENABLED": True,
            "EVENT_ANOMALY_SCANNER_ENABLED": True,
            "EVENT_CATALYST_SEARCH_ENABLED": True,
            "EVENT_CATALYST_SEARCH_PROVIDER": "gdelt,rss,polymarket",
            "EVENT_CATALYST_SEARCH_PROVIDERS": ("gdelt", "rss", "polymarket"),
            "EVENT_WATCHLIST_ENABLED": True,
            "EVENT_WATCHLIST_MONITOR_ENABLED": True,
            "EVENT_WATCHLIST_MONITOR_MARKET_SOURCE": "cycle",
            "EVENT_ALPHA_ROUTER_ENABLED": True,
            "EVENT_ALPHA_SNAPSHOT_POLICY": "sampled_controls",
        },
        snapshot_policy="sampled_controls",
        watchlist_monitor_enabled=True,
        targeted_market_source="cycle",
    ),
    "no_key_llm": EventAlphaProfile(
        name="no_key_llm",
        description="No-key live sources with fixture LLM extraction/relationship metadata for offline-safe testing.",
        config_overrides={
            "EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE": True,
            "EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS_PATH": _DEFAULT_RSS_URLS,
            "EVENT_DISCOVERY_GDELT_LIVE": True,
            "EVENT_DISCOVERY_CRYPTOPANIC_LIVE": True,
            "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE": True,
            "EVENT_DISCOVERY_UNIVERSE_LIVE": True,
            "EVENT_MARKET_ENRICHMENT_ENABLED": True,
            "EVENT_ANOMALY_SCANNER_ENABLED": True,
            "EVENT_CATALYST_SEARCH_ENABLED": True,
            "EVENT_CATALYST_SEARCH_PROVIDER": "gdelt,rss,cryptopanic,polymarket",
            "EVENT_CATALYST_SEARCH_PROVIDERS": ("gdelt", "rss", "cryptopanic", "polymarket"),
            "EVENT_LLM_PROVIDER": "fixture",
            "EVENT_LLM_MODE": "advisory",
            "EVENT_LLM_EXTRACTOR_PROVIDER": "fixture",
            "EVENT_LLM_EXTRACTOR_MODE": "advisory",
            "EVENT_WATCHLIST_ENABLED": True,
            "EVENT_ALPHA_ROUTER_ENABLED": True,
            "EVENT_ALPHA_SNAPSHOT_POLICY": "sampled_controls",
        },
        with_llm=True,
        snapshot_policy="sampled_controls",
    ),
    "api_live": EventAlphaProfile(
        name="api_live",
        description="API-backed live event sources where configured, with no LLM calls by default.",
        config_overrides={
            "EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE": True,
            "EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS_PATH": _DEFAULT_RSS_URLS,
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
            "EVENT_ALPHA_SNAPSHOT_POLICY": "sampled_controls",
        },
        snapshot_policy="sampled_controls",
    ),
    "full_llm_live": EventAlphaProfile(
        name="full_llm_live",
        description="Live public/API sources with opt-in OpenAI extraction and relationship advisory.",
        config_overrides={
            "EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE": True,
            "EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS_PATH": _DEFAULT_RSS_URLS,
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
            "EVENT_LLM_OPENAI_TIMEOUT": 15.0,
            "EVENT_LLM_MAX_CALLS_PER_RUN": 20,
            "EVENT_LLM_MAX_CALLS_PER_DAY": 80,
            "EVENT_LLM_MAX_ESTIMATED_COST_USD_PER_DAY": 1.0,
            "EVENT_LLM_ESTIMATED_COST_PER_CALL_USD": 0.005,
            "EVENT_LLM_CACHE_TTL_HOURS": 168,
            "EVENT_LLM_EXTRACTOR_ENABLED": True,
            "EVENT_LLM_EXTRACTOR_PROVIDER": "openai",
            "EVENT_LLM_EXTRACTOR_MODE": "advisory",
            "EVENT_LLM_EXTRACTOR_OPENAI_TIMEOUT": 15.0,
            "EVENT_WATCHLIST_ENABLED": True,
            "EVENT_WATCHLIST_MONITOR_ENABLED": True,
            "EVENT_WATCHLIST_MONITOR_MARKET_SOURCE": "cycle",
            "EVENT_ALPHA_ROUTER_ENABLED": True,
            "EVENT_ALPHA_SNAPSHOT_POLICY": "sampled_controls",
        },
        with_llm=True,
        snapshot_policy="sampled_controls",
        watchlist_monitor_enabled=True,
        targeted_market_source="cycle",
    ),
    "research_send": EventAlphaProfile(
        name="research_send",
        description="Research-send profile; still requires --event-alert-send and RSI_EVENT_ALERTS_ENABLED=1.",
        config_overrides={
            "EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE": True,
            "EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS_PATH": _DEFAULT_RSS_URLS,
            "EVENT_DISCOVERY_GDELT_LIVE": True,
            "EVENT_DISCOVERY_CRYPTOPANIC_LIVE": True,
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
            "EVENT_ALPHA_SNAPSHOT_POLICY": "alertable",
            "EVENT_ALPHA_NOTIFY_SCOPE": "namespace",
            "EVENT_ALPHA_NOTIFY_MAX_RUNTIME_SECONDS": 120.0,
            "EVENT_ALPHA_NOTIFY_PROVIDER_TIMEOUT_SECONDS": 5.0,
            "EVENT_ALPHA_NOTIFY_MAX_PROVIDER_FAILURES_BEFORE_SKIP": 1,
            "EVENT_ALPHA_NOTIFY_FAST_FAIL_ON_DNS": True,
            "EVENT_ALPHA_NOTIFY_ALLOW_PARTIAL_RESULTS": True,
            "EVENT_RESEARCH_CARDS_AUTO_WRITE": True,
            "EVENT_RESEARCH_CARDS_WRITE_TIERS": ("HIGH_PRIORITY_WATCH", "TRIGGERED_FADE"),
            "EVENT_WATCHLIST_ENABLED": True,
            "EVENT_WATCHLIST_MONITOR_ENABLED": True,
            "EVENT_WATCHLIST_MONITOR_MARKET_SOURCE": "cycle",
            "EVENT_ALPHA_ROUTER_ENABLED": True,
        },
        with_llm=True,
        send=True,
        snapshot_policy="alertable",
        card_auto_write=True,
        card_write_tiers=("HIGH_PRIORITY_WATCH", "TRIGGERED_FADE"),
        watchlist_monitor_enabled=True,
        targeted_market_source="cycle",
        send_lane_policy="research_digest_only",
        send_guard="requires --event-alert-send and RSI_EVENT_ALERTS_ENABLED=1; no paper/live trading",
    ),
    "notify_no_key": EventAlphaProfile(
        name="notify_no_key",
        description=(
            "Day-1 no-key Event Alpha notification burn-in using public RSS, GDELT, "
            "Polymarket, live CoinGecko universe, market enrichment, anomalies, and catalyst search."
        ),
        config_overrides={
            "EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE": True,
            "EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS_PATH": _DEFAULT_RSS_URLS,
            "EVENT_DISCOVERY_PROJECT_BLOG_RSS_TIMEOUT": 5.0,
            "EVENT_DISCOVERY_GDELT_LIVE": True,
            "EVENT_DISCOVERY_GDELT_TIMEOUT": 5.0,
            "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE": True,
            "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_TIMEOUT": 5.0,
            "EVENT_DISCOVERY_UNIVERSE_LIVE": True,
            "EVENT_DISCOVERY_UNIVERSE_FETCH_LIMIT": 250,
            "EVENT_MARKET_ENRICHMENT_ENABLED": True,
            "EVENT_ANOMALY_SCANNER_ENABLED": True,
            "EVENT_CATALYST_SEARCH_ENABLED": True,
            "EVENT_CATALYST_SEARCH_PROVIDER": "gdelt,rss,polymarket",
            "EVENT_CATALYST_SEARCH_PROVIDERS": ("gdelt", "rss", "polymarket"),
            "EVENT_IMPACT_HYPOTHESIS_SEARCH_ENABLED": True,
            "EVENT_LLM_ENABLED": False,
            "EVENT_LLM_PROVIDER": "fixture",
            "EVENT_LLM_MODE": "shadow",
            "EVENT_LLM_EXTRACTOR_ENABLED": False,
            "EVENT_LLM_EXTRACTOR_PROVIDER": "fixture",
            "EVENT_LLM_EXTRACTOR_MODE": "shadow",
            "EVENT_ALPHA_RUN_MODE": "notification_burn_in",
            "EVENT_ALPHA_SNAPSHOT_POLICY": "alertable",
            "EVENT_ALPHA_NOTIFY_SCOPE": "namespace",
            "EVENT_ALPHA_NOTIFY_MAX_RUNTIME_SECONDS": 120.0,
            "EVENT_ALPHA_NOTIFY_PROVIDER_TIMEOUT_SECONDS": 5.0,
            "EVENT_ALPHA_NOTIFY_MAX_PROVIDER_FAILURES_BEFORE_SKIP": 1,
            "EVENT_ALPHA_NOTIFY_FAST_FAIL_ON_DNS": True,
            "EVENT_ALPHA_NOTIFY_ALLOW_PARTIAL_RESULTS": True,
            "EVENT_ALPHA_NOTIFY_DAILY_DIGEST_COOLDOWN_HOURS": 0.0,
            "EVENT_ALPHA_NOTIFY_INSTANT_COOLDOWN_HOURS": 0.0,
            "EVENT_ALPHA_NOTIFY_HEALTH_HEARTBEAT_COOLDOWN_HOURS": 0.0,
            "EVENT_ALPHA_EXPLORATORY_DIGEST_ENABLED": True,
            "EVENT_ALPHA_EXPLORATORY_DIGEST_MAX_ITEMS": 10,
            "EVENT_ALPHA_EXPLORATORY_DIGEST_COOLDOWN_HOURS": 0.0,
            "EVENT_ALPHA_NOTIFICATION_DEDUPE_BY_CONTENT": False,
            "EVENT_ALPHA_NOTIFICATION_DEDUPE_WINDOW_HOURS": 0.0,
            "EVENT_RESEARCH_CARDS_AUTO_WRITE": True,
            "EVENT_RESEARCH_CARDS_WRITE_TIERS": ("HIGH_PRIORITY_WATCH", "TRIGGERED_FADE", "WATCHLIST"),
            "EVENT_WATCHLIST_ENABLED": True,
            "EVENT_WATCHLIST_MONITOR_ENABLED": True,
            "EVENT_WATCHLIST_MONITOR_MARKET_SOURCE": "cycle",
            "EVENT_WATCHLIST_MONITOR_ROUTE_UPDATES": True,
            "EVENT_ALPHA_ROUTER_ENABLED": True,
        },
        snapshot_policy="alertable",
        card_auto_write=True,
        card_write_tiers=("HIGH_PRIORITY_WATCH", "TRIGGERED_FADE", "WATCHLIST"),
        watchlist_monitor_enabled=True,
        targeted_market_source="cycle",
        send_lane_policy="notification_lanes",
        send_guard="requires --event-alert-send plus RSI_EVENT_ALERTS_ENABLED=1 for actual delivery",
        notification_burn_in=True,
    ),
    "notify_llm": EventAlphaProfile(
        name="notify_llm",
        description=(
            "Day-1 Event Alpha notification burn-in with no-key public sources plus "
            "strictly budgeted OpenAI extraction/advisory metadata."
        ),
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
            "EVENT_CATALYST_SEARCH_PROVIDER": "gdelt,rss,cryptopanic,polymarket",
            "EVENT_CATALYST_SEARCH_PROVIDERS": ("gdelt", "rss", "cryptopanic", "polymarket"),
            "EVENT_IMPACT_HYPOTHESIS_SEARCH_ENABLED": True,
            "EVENT_SOURCE_ENRICHMENT_ENABLED": True,
            "EVENT_SOURCE_ENRICHMENT_TIMEOUT_SECONDS": 5.0,
            "EVENT_SOURCE_ENRICHMENT_MAX_CHARS": 12000,
            "EVENT_SOURCE_ENRICHMENT_MAX_ROWS_PER_RUN": 10,
            "EVENT_SOURCE_ENRICHMENT_MIN_SOURCE_CONFIDENCE": 0.55,
            "EVENT_LLM_ENABLED": True,
            "EVENT_LLM_PROVIDER": "openai",
            "EVENT_LLM_MODE": "advisory",
            "EVENT_LLM_OPENAI_TIMEOUT": 10.0,
            "EVENT_LLM_MAX_CALLS_PER_RUN": 10,
            "EVENT_LLM_MAX_CALLS_PER_DAY": 50,
            "EVENT_LLM_MAX_ESTIMATED_COST_USD_PER_DAY": 1.0,
            "EVENT_LLM_ESTIMATED_COST_PER_CALL_USD": 0.005,
            "EVENT_LLM_CACHE_TTL_HOURS": 168,
            "EVENT_LLM_EXTRACTOR_ENABLED": True,
            "EVENT_LLM_EXTRACTOR_PROVIDER": "openai",
            "EVENT_LLM_EXTRACTOR_MODE": "advisory",
            "EVENT_LLM_EXTRACTOR_OPENAI_TIMEOUT": 10.0,
            "EVENT_ALPHA_RUN_MODE": "notification_burn_in",
            "EVENT_ALPHA_SNAPSHOT_POLICY": "alertable",
            "EVENT_ALPHA_NOTIFY_SCOPE": "namespace",
            "EVENT_ALPHA_NOTIFY_MAX_RUNTIME_SECONDS": 120.0,
            "EVENT_ALPHA_NOTIFY_PROVIDER_TIMEOUT_SECONDS": 5.0,
            "EVENT_ALPHA_NOTIFY_MAX_PROVIDER_FAILURES_BEFORE_SKIP": 1,
            "EVENT_ALPHA_NOTIFY_FAST_FAIL_ON_DNS": True,
            "EVENT_ALPHA_NOTIFY_ALLOW_PARTIAL_RESULTS": True,
            "EVENT_ALPHA_EXPLORATORY_DIGEST_ENABLED": True,
            "EVENT_ALPHA_EXPLORATORY_DIGEST_MAX_ITEMS": 10,
            "EVENT_ALPHA_EXPLORATORY_DIGEST_COOLDOWN_HOURS": 24.0,
            "EVENT_RESEARCH_CARDS_AUTO_WRITE": True,
            "EVENT_RESEARCH_CARDS_WRITE_TIERS": ("HIGH_PRIORITY_WATCH", "TRIGGERED_FADE", "WATCHLIST"),
            "EVENT_WATCHLIST_ENABLED": True,
            "EVENT_WATCHLIST_MONITOR_ENABLED": True,
            "EVENT_WATCHLIST_MONITOR_MARKET_SOURCE": "cycle",
            "EVENT_WATCHLIST_MONITOR_ROUTE_UPDATES": True,
            "EVENT_ALPHA_ROUTER_ENABLED": True,
        },
        with_llm=True,
        snapshot_policy="alertable",
        card_auto_write=True,
        card_write_tiers=("HIGH_PRIORITY_WATCH", "TRIGGERED_FADE", "WATCHLIST"),
        watchlist_monitor_enabled=True,
        targeted_market_source="cycle",
        send_lane_policy="notification_lanes",
        send_guard="requires --event-alert-send plus RSI_EVENT_ALERTS_ENABLED=1 for actual delivery",
        notification_burn_in=True,
    ),
    "notify_llm_deep": EventAlphaProfile(
        name="notify_llm_deep",
        description=(
            "Deeper opt-in Event Alpha notification burn-in with OpenAI extraction/advisory, "
            "bounded full-source enrichment, and conservative daily LLM budget caps."
        ),
        config_overrides={
            "EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE": True,
            "EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS_PATH": _DEFAULT_RSS_URLS,
            "EVENT_DISCOVERY_GDELT_LIVE": True,
            "EVENT_DISCOVERY_CRYPTOPANIC_LIVE": True,
            "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE": True,
            "EVENT_DISCOVERY_UNIVERSE_LIVE": True,
            "EVENT_DISCOVERY_UNIVERSE_FETCH_LIMIT": 350,
            "EVENT_MARKET_ENRICHMENT_ENABLED": True,
            "EVENT_ANOMALY_SCANNER_ENABLED": True,
            "EVENT_CATALYST_SEARCH_ENABLED": True,
            "EVENT_CATALYST_SEARCH_PROVIDER": "gdelt,rss,cryptopanic,polymarket",
            "EVENT_CATALYST_SEARCH_PROVIDERS": ("gdelt", "rss", "cryptopanic", "polymarket"),
            "EVENT_IMPACT_HYPOTHESIS_SEARCH_ENABLED": True,
            "EVENT_IMPACT_HYPOTHESIS_MAX_HYPOTHESES": 20,
            "EVENT_IMPACT_HYPOTHESIS_MAX_QUERIES_PER_HYPOTHESIS": 5,
            "EVENT_SOURCE_ENRICHMENT_ENABLED": True,
            "EVENT_SOURCE_ENRICHMENT_TIMEOUT_SECONDS": 5.0,
            "EVENT_SOURCE_ENRICHMENT_MAX_CHARS": 16000,
            "EVENT_SOURCE_ENRICHMENT_MAX_ROWS_PER_RUN": 20,
            "EVENT_SOURCE_ENRICHMENT_MIN_SOURCE_CONFIDENCE": 0.50,
            "EVENT_LLM_ENABLED": True,
            "EVENT_LLM_PROVIDER": "openai",
            "EVENT_LLM_MODE": "advisory",
            "EVENT_LLM_OPENAI_TIMEOUT": 12.0,
            "EVENT_LLM_MAX_CALLS_PER_RUN": 25,
            "EVENT_LLM_MAX_CALLS_PER_DAY": 100,
            "EVENT_LLM_MAX_ESTIMATED_COST_USD_PER_DAY": 3.0,
            "EVENT_LLM_ESTIMATED_COST_PER_CALL_USD": 0.01,
            "EVENT_LLM_CACHE_TTL_HOURS": 168,
            "EVENT_LLM_EXTRACTOR_ENABLED": True,
            "EVENT_LLM_EXTRACTOR_PROVIDER": "openai",
            "EVENT_LLM_EXTRACTOR_MODE": "advisory",
            "EVENT_LLM_EXTRACTOR_OPENAI_TIMEOUT": 12.0,
            "EVENT_ALPHA_RUN_MODE": "notification_burn_in",
            "EVENT_ALPHA_SNAPSHOT_POLICY": "alertable",
            "EVENT_ALPHA_NOTIFY_SCOPE": "namespace",
            "EVENT_ALPHA_NOTIFY_MAX_RUNTIME_SECONDS": 180.0,
            "EVENT_ALPHA_NOTIFY_PROVIDER_TIMEOUT_SECONDS": 5.0,
            "EVENT_ALPHA_NOTIFY_MAX_PROVIDER_FAILURES_BEFORE_SKIP": 1,
            "EVENT_ALPHA_NOTIFY_FAST_FAIL_ON_DNS": True,
            "EVENT_ALPHA_NOTIFY_ALLOW_PARTIAL_RESULTS": True,
            "EVENT_ALPHA_EXPLORATORY_DIGEST_ENABLED": True,
            "EVENT_ALPHA_EXPLORATORY_DIGEST_MAX_ITEMS": 10,
            "EVENT_ALPHA_EXPLORATORY_DIGEST_COOLDOWN_HOURS": 24.0,
            "EVENT_RESEARCH_CARDS_AUTO_WRITE": True,
            "EVENT_RESEARCH_CARDS_WRITE_TIERS": ("HIGH_PRIORITY_WATCH", "TRIGGERED_FADE", "WATCHLIST"),
            "EVENT_WATCHLIST_ENABLED": True,
            "EVENT_WATCHLIST_MONITOR_ENABLED": True,
            "EVENT_WATCHLIST_MONITOR_MARKET_SOURCE": "cycle",
            "EVENT_WATCHLIST_MONITOR_ROUTE_UPDATES": True,
            "EVENT_ALPHA_ROUTER_ENABLED": True,
        },
        with_llm=True,
        snapshot_policy="alertable",
        card_auto_write=True,
        card_write_tiers=("HIGH_PRIORITY_WATCH", "TRIGGERED_FADE", "WATCHLIST"),
        watchlist_monitor_enabled=True,
        targeted_market_source="cycle",
        send_lane_policy="notification_lanes",
        send_guard="requires --event-alert-send plus RSI_EVENT_ALERTS_ENABLED=1 for actual delivery",
        notification_burn_in=True,
    ),
}
