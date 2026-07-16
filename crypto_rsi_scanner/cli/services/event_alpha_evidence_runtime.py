"""Build authorization-gated runtime providers for evidence acquisition."""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

from ...event_alpha.providers import provider_health as event_provider_health
from ...event_alpha.radar import catalyst_search as event_catalyst_search
from ...event_alpha.radar import evidence_acquisition as event_evidence_acquisition
from ...event_alpha.radar.evidence.provider_contract import (
    FIXTURE_DISPATCH_HINTS,
    PLANNER_PROVIDER_HINTS,
    configured_local_path_status,
    explicit_live_authorizations,
)
from ...event_providers.binance_announcements import BinanceAnnouncementProvider
from ...event_providers.bybit_announcements import BybitAnnouncementProvider
from ...event_providers.coinmarketcal import CoinMarketCalProvider
from ...event_providers.tokenomist import TokenomistProvider


def _source_live_enabled(config_module: ModuleType, setting: str) -> bool:
    """Require both effective config and an already-present environment opt-in."""

    return bool(
        getattr(config_module, setting, False)
        and explicit_live_authorizations().get(setting, False)
    )


def _source_local_path(path_value: object) -> object | None:
    """Accept genuine operator files while rejecting fixture-like paths."""

    return (
        path_value
        if configured_local_path_status(path_value) == "regular_file"
        else None
    )


def _health_checked(
    provider: object,
    *,
    provider_health_cfg: event_provider_health.EventProviderHealthConfig,
) -> object:
    """Apply the existing persisted event-source circuit breaker."""

    return event_provider_health.HealthCheckedProvider(
        provider,
        cfg=provider_health_cfg,
        provider_kind="event_source",
        provider_role="event_source",
    )


def _news_providers(
    cfg: event_evidence_acquisition.EvidenceAcquisitionConfig,
    *,
    config_module: ModuleType,
    provider_health_cfg: event_provider_health.EventProviderHealthConfig,
    request_ledger_path: Path,
) -> dict[str, object | None]:
    cryptopanic_path = _source_local_path(
        config_module.EVENT_DISCOVERY_CRYPTOPANIC_PATH
    )
    cryptopanic_live = _source_live_enabled(
        config_module, "EVENT_DISCOVERY_CRYPTOPANIC_LIVE"
    )
    cryptopanic = event_catalyst_search.CryptoPanicCatalystSearchProvider(
        path=cryptopanic_path,
        live_enabled=cryptopanic_live,
        api_token=config_module.EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN,
        base_url=config_module.EVENT_DISCOVERY_CRYPTOPANIC_BASE_URL,
        plan=config_module.EVENT_DISCOVERY_CRYPTOPANIC_PLAN,
        public=config_module.EVENT_DISCOVERY_CRYPTOPANIC_PUBLIC,
        following=config_module.EVENT_DISCOVERY_CRYPTOPANIC_FOLLOWING,
        filter_name=config_module.EVENT_DISCOVERY_CRYPTOPANIC_FILTER,
        currencies=config_module.EVENT_DISCOVERY_CRYPTOPANIC_CURRENCIES,
        regions=config_module.EVENT_DISCOVERY_CRYPTOPANIC_REGIONS,
        kind=config_module.EVENT_DISCOVERY_CRYPTOPANIC_KIND,
        timeout=min(
            config_module.EVENT_DISCOVERY_CRYPTOPANIC_TIMEOUT,
            cfg.timeout_seconds,
        ),
        request_ledger_path=request_ledger_path,
        profile=config_module.EVENT_ALPHA_ARTIFACT_NAMESPACE or "",
        artifact_namespace=config_module.EVENT_ALPHA_ARTIFACT_NAMESPACE or "",
        weekly_request_limit=config_module.EVENT_DISCOVERY_CRYPTOPANIC_WEEKLY_REQUEST_LIMIT,
        requests_per_run_limit=config_module.EVENT_DISCOVERY_CRYPTOPANIC_REQUESTS_PER_RUN_LIMIT,
        requests_per_day_soft_limit=config_module.EVENT_DISCOVERY_CRYPTOPANIC_REQUESTS_PER_DAY_SOFT_LIMIT,
        min_seconds_between_requests=config_module.EVENT_DISCOVERY_CRYPTOPANIC_MIN_SECONDS_BETWEEN_REQUESTS,
        max_pages_per_query=config_module.EVENT_DISCOVERY_CRYPTOPANIC_MAX_PAGES_PER_QUERY,
        max_currencies_per_request=config_module.EVENT_DISCOVERY_CRYPTOPANIC_MAX_CURRENCIES_PER_REQUEST,
    ) if cryptopanic_path is not None or (
        cryptopanic_live
        and bool(config_module.EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN)
    ) else None

    rss_path = _source_local_path(
        config_module.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH
    )
    rss_live = _source_live_enabled(
        config_module, "EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE"
    )
    rss = event_catalyst_search.ProjectRssCatalystSearchProvider(
        path=rss_path,
        live_enabled=rss_live,
        feed_urls=config_module.EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS,
        timeout=min(
            config_module.EVENT_DISCOVERY_PROJECT_BLOG_RSS_TIMEOUT,
            cfg.timeout_seconds,
        ),
    ) if rss_path is not None or (
        rss_live and bool(config_module.EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS)
    ) else None
    checked_rss = (
        _health_checked(rss, provider_health_cfg=provider_health_cfg)
        if rss is not None
        else None
    )

    polymarket_path = _source_local_path(
        config_module.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH
    )
    polymarket_live = _source_live_enabled(
        config_module, "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE"
    )
    polymarket = event_catalyst_search.PolymarketCatalystSearchProvider(
        path=polymarket_path,
        live_enabled=polymarket_live,
        base_url=config_module.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_BASE_URL,
        limit=config_module.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIMIT,
        timeout=min(
            config_module.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_TIMEOUT,
            cfg.timeout_seconds,
        ),
    ) if polymarket_path is not None or polymarket_live else None

    gdelt_path = _source_local_path(config_module.EVENT_DISCOVERY_GDELT_PATH)
    gdelt_live = _source_live_enabled(config_module, "EVENT_DISCOVERY_GDELT_LIVE")
    gdelt = event_catalyst_search.GdeltCatalystSearchProvider(
        path=gdelt_path,
        live_enabled=gdelt_live,
        base_url=config_module.EVENT_DISCOVERY_GDELT_BASE_URL,
        max_records=config_module.EVENT_DISCOVERY_GDELT_MAX_RECORDS,
        timeout=min(config_module.EVENT_DISCOVERY_GDELT_TIMEOUT, cfg.timeout_seconds),
        max_fetches_per_search=1,
    ) if gdelt_path is not None or gdelt_live else None

    return {
        "cryptopanic": (
            _health_checked(cryptopanic, provider_health_cfg=provider_health_cfg)
            if cryptopanic is not None
            else None
        ),
        "project_blog_rss": checked_rss,
        "rss": checked_rss,
        "polymarket": (
            _health_checked(polymarket, provider_health_cfg=provider_health_cfg)
            if polymarket is not None
            else None
        ),
        "gdelt": (
            _health_checked(gdelt, provider_health_cfg=provider_health_cfg)
            if gdelt is not None
            else None
        ),
    }


def _exchange_providers(
    cfg: event_evidence_acquisition.EvidenceAcquisitionConfig,
    *,
    config_module: ModuleType,
    provider_health_cfg: event_provider_health.EventProviderHealthConfig,
) -> dict[str, object | None]:
    binance_path = _source_local_path(
        config_module.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH
    )
    binance_live = _source_live_enabled(
        config_module, "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE"
    )
    binance = event_catalyst_search.EventProviderCatalystSearchProvider(
        lambda query: BinanceAnnouncementProvider(
            binance_path,
            live_enabled=binance_live,
            api_key=config_module.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_KEY,
            api_secret=config_module.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_SECRET,
            ws_url=config_module.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_WS_URL,
            topic=config_module.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_TOPIC,
            recv_window_ms=config_module.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_RECV_WINDOW_MS,
            listen_seconds=min(
                config_module.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LISTEN_SECONDS,
                cfg.timeout_seconds,
            ),
            max_messages=config_module.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_MAX_MESSAGES,
        ),
        name="binance_announcements",
        filter_by_query=True,
        max_fetches_per_search=1,
    ) if binance_path is not None or (
        binance_live
        and bool(config_module.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_KEY)
        and bool(config_module.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_SECRET)
    ) else None
    checked_binance = (
        _health_checked(binance, provider_health_cfg=provider_health_cfg)
        if binance is not None
        else None
    )

    bybit_path = _source_local_path(
        config_module.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH
    )
    bybit_live = _source_live_enabled(
        config_module, "EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE"
    )
    bybit = event_catalyst_search.EventProviderCatalystSearchProvider(
        lambda query: BybitAnnouncementProvider(
            bybit_path,
            live_enabled=bybit_live,
            base_url=config_module.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_BASE_URL,
            locale=config_module.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LOCALE,
            announcement_type=config_module.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_TYPE,
            limit=config_module.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIMIT,
            timeout=min(
                config_module.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_TIMEOUT,
                cfg.timeout_seconds,
            ),
        ),
        name="bybit_announcements",
        filter_by_query=True,
        max_fetches_per_search=1,
    ) if bybit_path is not None or bybit_live else None
    checked_bybit = (
        _health_checked(bybit, provider_health_cfg=provider_health_cfg)
        if bybit is not None
        else None
    )
    exchange_providers = tuple(
        provider
        for provider in (checked_binance, checked_bybit)
        if provider is not None
    )
    return {
        "official_exchange": (
            event_catalyst_search.CompositeCatalystSearchProvider(
                exchange_providers
            )
            if exchange_providers
            else None
        ),
        "binance_announcements": checked_binance,
        "bybit_announcements": checked_bybit,
    }


def build_evidence_acquisition_providers(
    cfg: event_evidence_acquisition.EvidenceAcquisitionConfig,
    *,
    config_module: ModuleType,
    provider_health_cfg: event_provider_health.EventProviderHealthConfig,
    request_ledger_path: Path,
) -> dict[str, object | None]:
    """Return explicit source dispatch with no live-style fixture fallback."""

    if cfg.fixture_only:
        fixture_provider = event_catalyst_search.FixtureCatalystSearchProvider(
            path=config_module.EVENT_CATALYST_SEARCH_FIXTURE_PATH,
        )
        return {key: fixture_provider for key in FIXTURE_DISPATCH_HINTS}

    providers: dict[str, object | None] = {"default": None, "fixture": None}
    providers.update(
        _news_providers(
            cfg,
            config_module=config_module,
            provider_health_cfg=provider_health_cfg,
            request_ledger_path=request_ledger_path,
        )
    )
    providers.update(
        _exchange_providers(
            cfg,
            config_module=config_module,
            provider_health_cfg=provider_health_cfg,
        )
    )

    coinmarketcal_path = _source_local_path(
        config_module.EVENT_DISCOVERY_COINMARKETCAL_PATH
    )
    coinmarketcal = event_catalyst_search.EventProviderCatalystSearchProvider(
        lambda query: CoinMarketCalProvider(coinmarketcal_path),
        name="coinmarketcal",
        filter_by_query=True,
        max_fetches_per_search=1,
    ) if coinmarketcal_path is not None else None
    providers["coinmarketcal"] = (
        _health_checked(coinmarketcal, provider_health_cfg=provider_health_cfg)
        if coinmarketcal is not None
        else None
    )

    tokenomist_path = _source_local_path(config_module.EVENT_DISCOVERY_TOKENOMIST_PATH)
    tokenomist = event_catalyst_search.EventProviderCatalystSearchProvider(
        lambda query: TokenomistProvider(tokenomist_path),
        name="tokenomist",
        filter_by_query=True,
        max_fetches_per_search=1,
    ) if tokenomist_path is not None else None
    providers["tokenomist"] = (
        _health_checked(tokenomist, provider_health_cfg=provider_health_cfg)
        if tokenomist is not None
        else None
    )
    providers["coinalyze"] = None
    providers["sports_fixtures"] = None
    for key in PLANNER_PROVIDER_HINTS:
        providers.setdefault(key, None)
    return providers


__all__ = ["build_evidence_acquisition_providers"]
