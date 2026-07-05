"""Config Reports commands from the scanner service."""

from __future__ import annotations

from .runtime import *

def _event_discovery_paths_configured() -> bool:
    return event_provider_status.build_event_discovery_provider_status(
        config
    ).ready_for_configured_review_cycle

def _event_discovery_refresh_diagnostics(
    result: event_discovery.EventDiscoveryResult,
    status_report: event_provider_status.EventDiscoveryProviderStatus,
) -> dict[str, Any]:
    warnings: list[str] = []
    if not result.raw_events:
        warnings.append(
            "no_raw_events_collected: configured event sources produced zero raw events; "
            "check provider warnings, credentials, rate limits, and query/window settings"
        )
    elif not result.candidates:
        warnings.append(
            "no_validation_candidates_built: raw events were collected but no high-confidence "
            "asset/classification candidates were built"
        )
    return {
        "provider_status": event_provider_status.provider_status_to_dict(status_report),
        "refresh_warnings": warnings,
    }

def _event_research_now(override: str | datetime | None = None) -> datetime:
    return event_research_now_from_config(override=override)

def event_research_now_from_config(override: str | datetime | None = None) -> datetime:
    """Return the configured event research clock, honoring an explicit override."""
    try:
        return event_clock.event_research_now(config.EVENT_RESEARCH_NOW, override=override)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

def _event_clock_status(override: str | datetime | None = None) -> dict[str, object]:
    try:
        return event_clock.event_clock_status(config.EVENT_RESEARCH_NOW, override=override)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

def _event_alpha_clock_line(status: dict[str, object]) -> str:
    age = status.get("fixed_clock_age_hours")
    age_text = "n/a" if age is None else f"{float(age):.2f}h"
    return (
        "clock: "
        f"mode={status.get('clock_mode') or 'unknown'} "
        f"research_now={status.get('research_now') or 'unknown'} "
        f"wall_clock_now={status.get('wall_clock_now') or 'unknown'} "
        f"fixed_clock_age={age_text}"
    )

def _event_alpha_notify_clock_warnings(status: dict[str, object]) -> tuple[str, ...]:
    if status.get("clock_mode") != "fixed":
        return ()
    warnings = [str(item) for item in status.get("warnings", ()) or () if str(item)]
    warnings.append("fixed research clock active for notification profile")
    return tuple(dict.fromkeys(warnings))

def _event_alpha_notify_fixed_clock_blocker(status: dict[str, object]) -> str | None:
    if bool(getattr(config, "EVENT_ALPHA_ALLOW_FIXED_NOW_FOR_NOTIFY", False)):
        return None
    blocker = event_clock.fixed_clock_notification_blocker(status)
    if not blocker:
        return None
    return f"fixed research clock blocks notification send: {blocker}"

def _event_discovery_result_from_config(
    now: datetime | None = None,
    *,
    raw_event_transform: Callable[[tuple[RawDiscoveredEvent]], Iterable[RawDiscoveredEvent]] | None = None,
) -> event_discovery.EventDiscoveryResult:
    cfg = event_discovery.EventDiscoveryConfig(
        min_link_confidence=config.EVENT_DISCOVERY_MIN_LINK_CONFIDENCE,
        min_classifier_confidence=config.EVENT_DISCOVERY_MIN_CLASSIFIER_CONFIDENCE,
        min_event_time_confidence=config.EVENT_DISCOVERY_MIN_EVENT_TIME_CONFIDENCE,
        allow_proxy_venue_trigger=config.EVENT_FADE_ALLOW_PROXY_VENUE_TRIGGER,
        lookback_hours=config.EVENT_DISCOVERY_LOOKBACK_HOURS,
        horizon_days=config.EVENT_DISCOVERY_HORIZON_DAYS,
    )
    return event_discovery.run_manual_discovery(
        config.EVENT_DISCOVERY_EVENTS_PATH,
        config.EVENT_DISCOVERY_ALIASES_PATH,
        binance_announcements_path=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH,
        binance_announcements_live=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE,
        binance_announcements_api_key=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_KEY,
        binance_announcements_api_secret=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_SECRET,
        binance_announcements_ws_url=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_WS_URL,
        binance_announcements_topic=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_TOPIC,
        binance_announcements_recv_window_ms=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_RECV_WINDOW_MS,
        binance_announcements_listen_seconds=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LISTEN_SECONDS,
        binance_announcements_max_messages=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_MAX_MESSAGES,
        bybit_announcements_path=config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH,
        bybit_announcements_live=config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE,
        bybit_announcements_base_url=config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_BASE_URL,
        bybit_announcements_locale=config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LOCALE,
        bybit_announcements_type=config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_TYPE,
        bybit_announcements_limit=config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIMIT,
        bybit_announcements_timeout=config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_TIMEOUT,
        coinmarketcal_path=config.EVENT_DISCOVERY_COINMARKETCAL_PATH,
        tokenomist_path=config.EVENT_DISCOVERY_TOKENOMIST_PATH,
        cryptopanic_path=config.EVENT_DISCOVERY_CRYPTOPANIC_PATH,
        cryptopanic_live=config.EVENT_DISCOVERY_CRYPTOPANIC_LIVE,
        cryptopanic_api_token=config.EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN,
        cryptopanic_base_url=config.EVENT_DISCOVERY_CRYPTOPANIC_BASE_URL,
        cryptopanic_plan=config.EVENT_DISCOVERY_CRYPTOPANIC_PLAN,
        cryptopanic_public=config.EVENT_DISCOVERY_CRYPTOPANIC_PUBLIC,
        cryptopanic_following=config.EVENT_DISCOVERY_CRYPTOPANIC_FOLLOWING,
        cryptopanic_filter=config.EVENT_DISCOVERY_CRYPTOPANIC_FILTER,
        cryptopanic_currencies=config.EVENT_DISCOVERY_CRYPTOPANIC_CURRENCIES,
        cryptopanic_regions=config.EVENT_DISCOVERY_CRYPTOPANIC_REGIONS,
        cryptopanic_kind=config.EVENT_DISCOVERY_CRYPTOPANIC_KIND,
        cryptopanic_search=config.EVENT_DISCOVERY_CRYPTOPANIC_SEARCH,
        cryptopanic_timeout=config.EVENT_DISCOVERY_CRYPTOPANIC_TIMEOUT,
        cryptopanic_request_ledger_path=_cryptopanic_request_ledger_path(),
        cryptopanic_profile=config.EVENT_ALPHA_ARTIFACT_NAMESPACE or "",
        cryptopanic_artifact_namespace=config.EVENT_ALPHA_ARTIFACT_NAMESPACE or "",
        cryptopanic_weekly_request_limit=config.EVENT_DISCOVERY_CRYPTOPANIC_WEEKLY_REQUEST_LIMIT,
        cryptopanic_requests_per_run_limit=config.EVENT_DISCOVERY_CRYPTOPANIC_REQUESTS_PER_RUN_LIMIT,
        cryptopanic_requests_per_day_soft_limit=config.EVENT_DISCOVERY_CRYPTOPANIC_REQUESTS_PER_DAY_SOFT_LIMIT,
        cryptopanic_min_seconds_between_requests=config.EVENT_DISCOVERY_CRYPTOPANIC_MIN_SECONDS_BETWEEN_REQUESTS,
        cryptopanic_max_pages_per_query=config.EVENT_DISCOVERY_CRYPTOPANIC_MAX_PAGES_PER_QUERY,
        cryptopanic_max_currencies_per_request=config.EVENT_DISCOVERY_CRYPTOPANIC_MAX_CURRENCIES_PER_REQUEST,
        gdelt_path=config.EVENT_DISCOVERY_GDELT_PATH,
        gdelt_live=config.EVENT_DISCOVERY_GDELT_LIVE,
        gdelt_base_url=config.EVENT_DISCOVERY_GDELT_BASE_URL,
        gdelt_query=config.EVENT_DISCOVERY_GDELT_QUERY,
        gdelt_max_records=config.EVENT_DISCOVERY_GDELT_MAX_RECORDS,
        gdelt_timeout=config.EVENT_DISCOVERY_GDELT_TIMEOUT,
        project_blog_rss_path=config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH,
        project_blog_rss_live=config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE,
        project_blog_rss_urls=config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS,
        project_blog_rss_timeout=config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_TIMEOUT,
        project_blog_rss_fail_fast_on_error=(
            config.EVENT_ALPHA_NOTIFY_FAST_FAIL_ON_DNS
            and str(config.EVENT_ALPHA_RUN_MODE or "") == "notification_burn_in"
        ),
        external_ipo_path=config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH,
        sports_fixtures_path=config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH,
        prediction_market_events_path=config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH,
        prediction_market_events_live=config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE,
        prediction_market_events_base_url=config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_BASE_URL,
        prediction_market_events_limit=config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIMIT,
        prediction_market_events_timeout=config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_TIMEOUT,
        coinalyze_derivatives_path=config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH,
        coinalyze_live=config.EVENT_DISCOVERY_COINALYZE_LIVE,
        coinalyze_api_key=config.EVENT_DISCOVERY_COINALYZE_API_KEY,
        coinalyze_symbols=config.EVENT_DISCOVERY_COINALYZE_SYMBOLS,
        coinalyze_auto_symbols=config.EVENT_DISCOVERY_COINALYZE_AUTO_SYMBOLS,
        coinalyze_base_url=config.EVENT_DISCOVERY_COINALYZE_BASE_URL,
        coinalyze_timeout=config.EVENT_DISCOVERY_COINALYZE_TIMEOUT,
        coinalyze_history_interval=config.EVENT_DISCOVERY_COINALYZE_HISTORY_INTERVAL,
        coinalyze_lookback_hours=config.EVENT_DISCOVERY_COINALYZE_LOOKBACK_HOURS,
        coinalyze_convert_to_usd=config.EVENT_DISCOVERY_COINALYZE_CONVERT_TO_USD,
        market_enrichment_enabled=config.EVENT_MARKET_ENRICHMENT_ENABLED,
        market_enrichment_path=config.EVENT_DISCOVERY_UNIVERSE_PATH,
        market_enrichment_live=config.EVENT_DISCOVERY_UNIVERSE_LIVE,
        market_enrichment_fetch_limit=config.EVENT_DISCOVERY_UNIVERSE_FETCH_LIMIT,
        market_enrichment_fail_soft=_event_alpha_notification_mode(),
        anomaly_scanner_enabled=config.EVENT_ANOMALY_SCANNER_ENABLED,
        anomaly_min_return_24h=config.EVENT_ANOMALY_MIN_RETURN_24H,
        anomaly_min_volume_mcap=config.EVENT_ANOMALY_MIN_VOLUME_MCAP,
        anomaly_min_volume_zscore=config.EVENT_ANOMALY_MIN_VOLUME_ZSCORE,
        anomaly_max_assets=config.EVENT_ANOMALY_MAX_ASSETS,
        tokenomist_supply_path=config.EVENT_DISCOVERY_TOKENOMIST_SUPPLY_PATH,
        etherscan_supply_path=config.EVENT_DISCOVERY_ETHERSCAN_SUPPLY_PATH,
        arkham_supply_path=config.EVENT_DISCOVERY_ARKHAM_SUPPLY_PATH,
        dune_supply_path=config.EVENT_DISCOVERY_DUNE_SUPPLY_PATH,
        universe_path=config.EVENT_DISCOVERY_UNIVERSE_PATH,
        universe_limit=config.EVENT_DISCOVERY_UNIVERSE_LIMIT or None,
        universe_live=config.EVENT_DISCOVERY_UNIVERSE_LIVE,
        universe_fetch_limit=config.EVENT_DISCOVERY_UNIVERSE_FETCH_LIMIT or None,
        cfg=cfg,
        fade_cfg=event_fade.runtime_config(config),
        now=now,
        raw_event_transform=raw_event_transform,
        provider_health_cfg=_event_provider_health_config_from_runtime(),
    )

def _event_alert_config_from_runtime() -> event_alerts.EventAlertConfig:
    return event_alerts.EventAlertConfig(
        enabled=config.EVENT_ALERTS_ENABLED,
        mode=config.EVENT_ALERT_MODE,
        min_digest_score=config.EVENT_ALERT_MIN_DIGEST_SCORE,
        min_watchlist_score=config.EVENT_ALERT_MIN_WATCHLIST_SCORE,
        min_high_priority_score=config.EVENT_ALERT_MIN_HIGH_PRIORITY_SCORE,
        max_digest_items=config.EVENT_ALERT_MAX_DIGEST_ITEMS,
        max_instant_per_day=config.EVENT_ALERT_MAX_INSTANT_PER_DAY,
        cooldown_hours=config.EVENT_ALERT_COOLDOWN_HOURS,
        allow_proxy_venue=config.EVENT_ALERT_ALLOW_PROXY_VENUE,
    )

def _event_alpha_priors_config_from_runtime() -> event_alpha_priors.EventAlphaPriorsConfig:
    return event_alpha_priors.EventAlphaPriorsConfig(
        enabled=config.EVENT_ALPHA_APPLY_PRIORS,
        path=config.EVENT_ALPHA_PRIORS_PATH,
        min_multiplier=config.EVENT_ALPHA_PRIORS_MIN_MULTIPLIER,
        max_multiplier=config.EVENT_ALPHA_PRIORS_MAX_MULTIPLIER,
    )

def _event_provider_health_config_from_runtime() -> event_provider_health.EventProviderHealthConfig:
    notification_mode = _event_alpha_notification_mode()
    return event_provider_health.EventProviderHealthConfig(
        path=config.EVENT_PROVIDER_HEALTH_PATH,
        max_consecutive_failures=(
            config.EVENT_ALPHA_NOTIFY_MAX_PROVIDER_FAILURES_BEFORE_SKIP
            if notification_mode
            else config.EVENT_PROVIDER_MAX_CONSECUTIVE_FAILURES
        ),
        backoff_minutes=config.EVENT_PROVIDER_BACKOFF_MINUTES,
        fail_fast_on_dns=(
            config.EVENT_ALPHA_NOTIFY_FAST_FAIL_ON_DNS
            if notification_mode
            else config.EVENT_PROVIDER_FAIL_FAST_ON_DNS
        ),
        ignore_backoff=bool(config.EVENT_ALPHA_IGNORE_PROVIDER_BACKOFF),
    )

def _event_alpha_notification_mode() -> bool:
    return str(config.EVENT_ALPHA_RUN_MODE or "") == "notification_burn_in"

def _event_alpha_retention_config_from_runtime() -> event_alpha_retention.EventAlphaRetentionConfig:
    return event_alpha_retention.EventAlphaRetentionConfig(
        runs_path=config.EVENT_ALPHA_RUN_LEDGER_PATH,
        alerts_path=config.EVENT_ALPHA_ALERT_STORE_PATH,
        cards_dir=config.EVENT_RESEARCH_CARDS_DIR,
        run_days=config.EVENT_ALPHA_RETENTION_DAYS_RUNS,
        alert_days=config.EVENT_ALPHA_RETENTION_DAYS_ALERTS,
        card_days=config.EVENT_ALPHA_RETENTION_DAYS_CARDS,
        keep_eval_cases=config.EVENT_ALPHA_RETENTION_KEEP_EVAL_CASES,
    )

def _event_llm_config_from_runtime() -> event_llm_analyzer.EventLLMConfig:
    return event_llm_analyzer.EventLLMConfig(
        enabled=config.EVENT_LLM_ENABLED,
        mode=config.EVENT_LLM_MODE,
        provider=config.EVENT_LLM_PROVIDER,
        model=config.EVENT_LLM_MODEL,
        max_candidates_per_run=config.EVENT_LLM_MAX_CANDIDATES_PER_RUN,
        min_prefilter_score=config.EVENT_LLM_MIN_PREFILTER_SCORE,
        require_evidence_quotes=config.EVENT_LLM_REQUIRE_EVIDENCE_QUOTES,
        cache_path=config.EVENT_LLM_CACHE_PATH,
        prompt_version=config.EVENT_LLM_PROMPT_VERSION,
        max_calls_per_run=config.EVENT_LLM_MAX_CALLS_PER_RUN,
        max_calls_per_day=config.EVENT_LLM_MAX_CALLS_PER_DAY,
        max_estimated_cost_usd_per_day=config.EVENT_LLM_MAX_ESTIMATED_COST_USD_PER_DAY,
        max_parallel_calls=config.EVENT_LLM_MAX_PARALLEL_CALLS,
        cache_ttl_hours=config.EVENT_LLM_CACHE_TTL_HOURS,
        budget_ledger_path=config.EVENT_LLM_BUDGET_LEDGER_PATH,
        estimated_cost_per_call_usd=config.EVENT_LLM_ESTIMATED_COST_PER_CALL_USD,
    )

def _event_llm_extractor_config_from_runtime() -> event_llm_extractor.EventLLMExtractorConfig:
    return event_llm_extractor.EventLLMExtractorConfig(
        enabled=config.EVENT_LLM_EXTRACTOR_ENABLED,
        mode=config.EVENT_LLM_EXTRACTOR_MODE,
        provider=config.EVENT_LLM_EXTRACTOR_PROVIDER,
        model=config.EVENT_LLM_EXTRACTOR_MODEL,
        max_events_per_run=config.EVENT_LLM_EXTRACTOR_MAX_EVENTS_PER_RUN,
        require_evidence_quotes=config.EVENT_LLM_EXTRACTOR_REQUIRE_EVIDENCE_QUOTES,
        cache_path=config.EVENT_LLM_EXTRACTOR_CACHE_PATH,
        prompt_version=config.EVENT_LLM_EXTRACTOR_PROMPT_VERSION,
        max_calls_per_run=config.EVENT_LLM_MAX_CALLS_PER_RUN,
        max_calls_per_day=config.EVENT_LLM_MAX_CALLS_PER_DAY,
        max_estimated_cost_usd_per_day=config.EVENT_LLM_MAX_ESTIMATED_COST_USD_PER_DAY,
        max_parallel_calls=config.EVENT_LLM_MAX_PARALLEL_CALLS,
        cache_ttl_hours=config.EVENT_LLM_CACHE_TTL_HOURS,
        budget_ledger_path=config.EVENT_LLM_BUDGET_LEDGER_PATH,
        estimated_cost_per_call_usd=config.EVENT_LLM_ESTIMATED_COST_PER_CALL_USD,
    )

def _event_llm_catalyst_frame_config_from_runtime() -> event_llm_catalyst_frames.EventLLMCatalystFrameConfig:
    return event_llm_catalyst_frames.EventLLMCatalystFrameConfig(
        enabled=config.EVENT_LLM_CATALYST_FRAMES_ENABLED,
        provider=config.EVENT_LLM_CATALYST_FRAMES_PROVIDER,
        model=config.EVENT_LLM_CATALYST_FRAMES_MODEL,
        max_rows_per_run=config.EVENT_LLM_CATALYST_FRAMES_MAX_ROWS_PER_RUN,
        min_source_score=config.EVENT_LLM_CATALYST_FRAMES_MIN_SOURCE_SCORE,
        use_enriched_text=config.EVENT_LLM_CATALYST_FRAMES_USE_ENRICHED_TEXT,
        only_ambiguous=config.EVENT_LLM_CATALYST_FRAMES_ONLY_AMBIGUOUS,
        prompt_version=config.EVENT_LLM_CATALYST_FRAMES_PROMPT_VERSION,
    )

def _event_impact_hypothesis_store_config_from_runtime() -> event_impact_hypothesis_store.EventImpactHypothesisStoreConfig:
    return event_impact_hypothesis_store.EventImpactHypothesisStoreConfig(
        path=config.EVENT_IMPACT_HYPOTHESIS_STORE_PATH,
    )

def _event_incident_store_config_from_runtime() -> event_incident_store.EventIncidentStoreConfig:
    return event_incident_store.EventIncidentStoreConfig(
        path=config.EVENT_INCIDENT_STORE_PATH,
        store_diagnostic=config.EVENT_INCIDENT_STORE_DIAGNOSTIC,
        store_raw_observations=config.EVENT_INCIDENT_STORE_RAW_OBSERVATIONS,
    )

def _event_watchlist_config_from_runtime() -> event_watchlist.EventWatchlistConfig:
    return event_watchlist.EventWatchlistConfig(
        enabled=config.EVENT_WATCHLIST_ENABLED,
        state_path=config.EVENT_WATCHLIST_STATE_PATH,
        expire_hours_after_event=config.EVENT_WATCHLIST_EXPIRE_HOURS_AFTER_EVENT,
    )

def _event_watchlist_monitor_market_rows_from_runtime() -> list[dict[str, Any]]:
    if str(config.EVENT_WATCHLIST_MONITOR_MARKET_SOURCE or "").lower() in {"cycle", "none", "off"}:
        return []
    market_path = config.EVENT_WATCHLIST_MONITOR_MARKET_PATH or config.EVENT_DISCOVERY_UNIVERSE_PATH
    return event_watchlist_market.load_market_rows(market_path)

def _event_watchlist_monitor_derivatives_rows_from_runtime() -> list[dict[str, Any]]:
    source = str(config.EVENT_WATCHLIST_MONITOR_DERIVATIVES_SOURCE or "").strip().lower()
    if source in {"cycle", "none", "off", "disabled"}:
        return []
    return event_watchlist_enrichment.load_enrichment_rows(config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH)

def _event_watchlist_monitor_supply_rows_from_runtime() -> list[dict[str, Any]]:
    source = str(config.EVENT_WATCHLIST_MONITOR_SUPPLY_SOURCE or "").strip().lower()
    if source in {"cycle", "none", "off", "disabled"}:
        return []
    rows: list[dict[str, Any]] = []
    for path in (
        config.EVENT_DISCOVERY_TOKENOMIST_SUPPLY_PATH,
        config.EVENT_DISCOVERY_ETHERSCAN_SUPPLY_PATH,
        config.EVENT_DISCOVERY_ARKHAM_SUPPLY_PATH,
        config.EVENT_DISCOVERY_DUNE_SUPPLY_PATH,
    ):
        rows.extend(event_watchlist_enrichment.load_enrichment_rows(path))
    return rows

def _event_watchlist_market_provider_from_runtime() -> event_watchlist_market.EventWatchlistMarketProvider | None:
    source = str(config.EVENT_WATCHLIST_MONITOR_MARKET_SOURCE or "").strip().lower()
    if source != "coingecko":
        return None
    return event_watchlist_market.CoinGeckoWatchlistMarketProvider(
        live_enabled=bool(config.EVENT_WATCHLIST_MONITOR_TARGETED_LOOKUP and config.EVENT_DISCOVERY_UNIVERSE_LIVE),
        cache_ttl_seconds=config.EVENT_WATCHLIST_MONITOR_MARKET_CACHE_TTL_SECONDS,
        provider_health_cfg=_event_provider_health_config_from_runtime() if _event_alpha_notification_mode() else None,
    )

def _event_watchlist_monitor_result_from_runtime(
    read_result: event_watchlist.EventWatchlistReadResult,
    *,
    now: datetime | None = None,
) -> event_watchlist_monitor.EventWatchlistMonitorResult:
    observed = _event_research_now(now)
    fixture_rows = _event_watchlist_monitor_market_rows_from_runtime()
    market_source = event_watchlist_market.market_rows_for_watchlist(
        read_result,
        source=config.EVENT_WATCHLIST_MONITOR_MARKET_SOURCE,
        fixture_rows=fixture_rows,
        cycle_rows=fixture_rows,
        targeted_lookup=config.EVENT_WATCHLIST_MONITOR_TARGETED_LOOKUP,
        targeted_provider=_event_watchlist_market_provider_from_runtime(),
        max_assets=config.EVENT_WATCHLIST_MONITOR_MAX_ASSETS,
        cache_ttl_seconds=config.EVENT_WATCHLIST_MONITOR_MARKET_CACHE_TTL_SECONDS,
        now=observed,
    )
    enrichment = event_watchlist_enrichment.enrichment_for_watchlist(
        read_result,
        derivatives_source=config.EVENT_WATCHLIST_MONITOR_DERIVATIVES_SOURCE,
        supply_source=config.EVENT_WATCHLIST_MONITOR_SUPPLY_SOURCE,
        derivatives_rows=_event_watchlist_monitor_derivatives_rows_from_runtime(),
        supply_rows=_event_watchlist_monitor_supply_rows_from_runtime(),
        max_assets=config.EVENT_WATCHLIST_MONITOR_ENRICHMENT_MAX_ASSETS,
    )
    return event_watchlist_monitor.monitor_watchlist(
        read_result,
        market_rows=market_source.rows,
        derivatives_by_asset=enrichment.derivatives,
        supply_by_asset=enrichment.supply,
        now=observed,
    )

def _event_alpha_router_config_from_runtime() -> event_alpha_router.EventAlphaRouterConfig:
    return event_alpha_router.EventAlphaRouterConfig(
        enabled=config.EVENT_ALPHA_ROUTER_ENABLED,
        daily_digest_enabled=config.EVENT_ALPHA_ROUTER_DAILY_DIGEST_ENABLED,
        instant_enabled=config.EVENT_ALPHA_ROUTER_INSTANT_ENABLED,
        max_digest_items=config.EVENT_ALPHA_ROUTER_MAX_DIGEST_ITEMS,
        validated_hypothesis_digest_enabled=config.EVENT_ALPHA_VALIDATED_HYPOTHESIS_DIGEST_ENABLED,
        max_validated_hypothesis_digest_items=config.EVENT_ALPHA_VALIDATED_HYPOTHESIS_MAX_ITEMS,
        validated_hypothesis_min_score=config.EVENT_ALPHA_VALIDATED_HYPOTHESIS_DIGEST_MIN_SCORE,
        validated_hypothesis_min_opportunity_score=config.EVENT_ALPHA_VALIDATED_HYPOTHESIS_MIN_OPPORTUNITY_SCORE,
        validated_hypothesis_min_final_score=config.EVENT_ALPHA_VALIDATED_HYPOTHESIS_MIN_FINAL_SCORE,
        validated_hypothesis_require_external_or_direct_event=(
            config.EVENT_ALPHA_VALIDATED_HYPOTHESIS_REQUIRE_EXTERNAL_OR_DIRECT_EVENT
        ),
        validated_hypothesis_require_impact_path=config.EVENT_ALPHA_VALIDATED_HYPOTHESIS_REQUIRE_IMPACT_PATH,
        weak_validated_local_only=config.EVENT_ALPHA_WEAK_VALIDATED_LOCAL_ONLY,
        allow_weak_path_with_market_confirmation=config.EVENT_ALPHA_ALLOW_WEAK_PATH_WITH_MARKET_CONFIRMATION,
        block_generic_cooccurrence_digest=config.EVENT_ALPHA_BLOCK_GENERIC_COOCCURRENCE_DIGEST,
        max_high_priority_per_day=config.EVENT_ALPHA_ROUTER_MAX_HIGH_PRIORITY_PER_DAY,
        per_key_cooldown_hours=config.EVENT_ALPHA_ROUTER_PER_KEY_COOLDOWN_HOURS,
        alert_on_score_jump=config.EVENT_ALPHA_ROUTER_ALERT_ON_SCORE_JUMP,
        score_jump_threshold=config.EVENT_ALPHA_ROUTER_SCORE_JUMP_THRESHOLD,
        alert_on_new_independent_source=config.EVENT_ALPHA_ROUTER_ALERT_ON_NEW_INDEPENDENT_SOURCE,
        alert_on_event_time_upgrade=config.EVENT_ALPHA_ROUTER_ALERT_ON_EVENT_TIME_UPGRADE,
        alert_on_derivatives_crowding_upgrade=config.EVENT_ALPHA_ROUTER_ALERT_ON_DERIVATIVES_CROWDING_UPGRADE,
        alert_on_cluster_confidence_upgrade=config.EVENT_ALPHA_ROUTER_ALERT_ON_CLUSTER_CONFIDENCE_UPGRADE,
    )

def _event_near_miss_config_from_runtime() -> event_near_miss.EventNearMissConfig:
    return event_near_miss.EventNearMissConfig(
        enabled=True,
        near_threshold_points=config.EVENT_ALPHA_NEAR_MISS_THRESHOLD_POINTS,
        digest_threshold=config.EVENT_ALPHA_VALIDATED_HYPOTHESIS_MIN_FINAL_SCORE,
        watchlist_threshold=78.0,
        max_candidates=config.EVENT_ALPHA_NEAR_MISS_MARKET_REFRESH_MAX_ASSETS,
        market_refresh_enabled=config.EVENT_ALPHA_NEAR_MISS_MARKET_REFRESH_ENABLED,
        max_market_refresh_assets=config.EVENT_ALPHA_NEAR_MISS_MARKET_REFRESH_MAX_ASSETS,
        market_refresh_timeout_seconds=config.EVENT_ALPHA_NEAR_MISS_MARKET_REFRESH_TIMEOUT_SECONDS,
    )

def _event_alpha_notification_config_from_runtime(
    profile_name: str | None = None,
) -> event_alpha_notifications.EventAlphaNotificationConfig:
    return event_alpha_notifications.EventAlphaNotificationConfig(
        enabled=config.EVENT_ALERTS_ENABLED,
        mode=config.EVENT_ALERT_MODE,
        notification_scope=config.EVENT_ALPHA_NOTIFY_SCOPE,
        profile_name=profile_name,
        artifact_namespace=config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
        daily_digest_cooldown_hours=config.EVENT_ALPHA_NOTIFY_DAILY_DIGEST_COOLDOWN_HOURS,
        daily_digest_max_items=config.EVENT_ALPHA_DAILY_DIGEST_MAX_ITEMS,
        instant_escalation_cooldown_hours=config.EVENT_ALPHA_NOTIFY_INSTANT_COOLDOWN_HOURS,
        max_instant_per_day=config.EVENT_ALPHA_NOTIFY_MAX_INSTANT_PER_DAY,
        health_heartbeat_enabled=config.EVENT_ALPHA_NOTIFY_HEALTH_HEARTBEAT_ENABLED,
        health_heartbeat_cooldown_hours=config.EVENT_ALPHA_NOTIFY_HEALTH_HEARTBEAT_COOLDOWN_HOURS,
        exploratory_digest_enabled=config.EVENT_ALPHA_EXPLORATORY_DIGEST_ENABLED,
        exploratory_digest_max_items=config.EVENT_ALPHA_EXPLORATORY_DIGEST_MAX_ITEMS,
        exploratory_digest_min_score=config.EVENT_ALPHA_EXPLORATORY_DIGEST_MIN_SCORE,
        exploratory_digest_cooldown_hours=config.EVENT_ALPHA_EXPLORATORY_DIGEST_COOLDOWN_HOURS,
        exploratory_digest_include_rejection_reasons=config.EVENT_ALPHA_EXPLORATORY_DIGEST_INCLUDE_REJECTION_REASONS,
        exploratory_digest_include_raw_evidence=config.EVENT_ALPHA_EXPLORATORY_DIGEST_INCLUDE_RAW_EVIDENCE,
        exploratory_digest_include_controls=config.EVENT_ALPHA_EXPLORATORY_DIGEST_INCLUDE_CONTROLS,
        research_review_digest_enabled=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_ENABLED,
        research_review_digest_max_items=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_MAX_ITEMS,
        research_review_digest_min_score=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_MIN_SCORE,
        research_review_digest_cooldown_hours=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_COOLDOWN_HOURS,
        research_review_digest_include_local_only=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_INCLUDE_LOCAL_ONLY,
        research_review_digest_include_sector=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_INCLUDE_SECTOR,
        research_review_digest_send_with_alerts=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_SEND_WITH_ALERTS,
        allow_source_only_narrative_digest=config.EVENT_ALPHA_ALLOW_SOURCE_ONLY_NARRATIVE_DIGEST,
        quality_mode=config.EVENT_ALPHA_NOTIFICATION_QUALITY_MODE,
    )

def _event_catalyst_search_config_from_runtime(
    *,
    enabled_override: bool | None = None,
) -> event_catalyst_search.EventCatalystSearchConfig:
    return event_catalyst_search.EventCatalystSearchConfig(
        enabled=config.EVENT_CATALYST_SEARCH_ENABLED if enabled_override is None else enabled_override,
        provider=config.EVENT_CATALYST_SEARCH_PROVIDER,
        providers=tuple(config.EVENT_CATALYST_SEARCH_PROVIDERS),
        max_anomalies=config.EVENT_CATALYST_SEARCH_MAX_ANOMALIES,
        max_queries_per_anomaly=config.EVENT_CATALYST_SEARCH_MAX_QUERIES_PER_ANOMALY,
        max_results_per_query=config.EVENT_CATALYST_SEARCH_MAX_RESULTS_PER_QUERY,
        min_anomaly_score=config.EVENT_CATALYST_SEARCH_MIN_ANOMALY_SCORE,
        require_live_source=config.EVENT_CATALYST_SEARCH_REQUIRE_LIVE_SOURCE,
        min_result_confidence=config.EVENT_CATALYST_SEARCH_MIN_RESULT_CONFIDENCE,
    )

def _event_impact_hypothesis_search_config_from_runtime(
    *,
    enabled_override: bool | None = None,
) -> event_catalyst_search.EventImpactHypothesisSearchConfig:
    return event_catalyst_search.EventImpactHypothesisSearchConfig(
        enabled=config.EVENT_IMPACT_HYPOTHESIS_SEARCH_ENABLED if enabled_override is None else enabled_override,
        max_hypotheses=config.EVENT_IMPACT_HYPOTHESIS_MAX_HYPOTHESES,
        max_queries_per_hypothesis=config.EVENT_IMPACT_HYPOTHESIS_MAX_QUERIES_PER_HYPOTHESIS,
        max_results_per_query=config.EVENT_CATALYST_SEARCH_MAX_RESULTS_PER_QUERY,
        min_confidence=config.EVENT_IMPACT_HYPOTHESIS_MIN_CONFIDENCE,
        min_result_confidence=config.EVENT_IMPACT_HYPOTHESIS_MIN_RESULT_CONFIDENCE,
        require_validated_identity=config.EVENT_IMPACT_HYPOTHESIS_REQUIRE_VALIDATED_IDENTITY,
        candidate_discovery_enabled=config.EVENT_IMPACT_HYPOTHESIS_CANDIDATE_DISCOVERY_ENABLED,
        max_candidate_discovery_queries=config.EVENT_IMPACT_HYPOTHESIS_MAX_DISCOVERY_QUERIES,
        max_candidate_discovery_results=config.EVENT_IMPACT_HYPOTHESIS_MAX_DISCOVERY_RESULTS,
    )

def _event_evidence_acquisition_config_from_runtime() -> event_evidence_acquisition.EvidenceAcquisitionConfig:
    return event_evidence_acquisition.EvidenceAcquisitionConfig(
        enabled=config.EVENT_ALPHA_EVIDENCE_ACQUISITION_ENABLED,
        max_candidates=config.EVENT_ALPHA_EVIDENCE_ACQUISITION_MAX_CANDIDATES,
        max_queries=config.EVENT_ALPHA_EVIDENCE_ACQUISITION_MAX_QUERIES,
        max_results_per_query=config.EVENT_CATALYST_SEARCH_MAX_RESULTS_PER_QUERY,
        timeout_seconds=config.EVENT_ALPHA_EVIDENCE_ACQUISITION_TIMEOUT_SECONDS,
        fixture_only=config.EVENT_ALPHA_EVIDENCE_ACQUISITION_FIXTURE_ONLY,
        artifact_path=config.EVENT_ALPHA_EVIDENCE_ACQUISITION_PATH,
    )

def _event_source_enrichment_config_from_runtime() -> event_source_enrichment.EventSourceEnrichmentConfig:
    return event_source_enrichment.EventSourceEnrichmentConfig(
        enabled=config.EVENT_SOURCE_ENRICHMENT_ENABLED,
        cache_dir=config.EVENT_SOURCE_ENRICHMENT_CACHE_DIR,
        timeout_seconds=config.EVENT_SOURCE_ENRICHMENT_TIMEOUT_SECONDS,
        max_chars=config.EVENT_SOURCE_ENRICHMENT_MAX_CHARS,
        max_rows_per_run=config.EVENT_SOURCE_ENRICHMENT_MAX_ROWS_PER_RUN,
        min_source_confidence=config.EVENT_SOURCE_ENRICHMENT_MIN_SOURCE_CONFIDENCE,
    )

def _event_feedback_config_from_runtime(path: str | None = None) -> event_feedback.EventFeedbackConfig:
    feedback_path = Path(path).expanduser() if path else config.EVENT_ALPHA_FEEDBACK_PATH
    if not feedback_path.is_absolute():
        feedback_path = config.DATA_DIR / feedback_path
    return event_feedback.EventFeedbackConfig(path=feedback_path)

def _event_alpha_alert_store_config_from_runtime(
    path: str | None = None,
) -> event_alpha_alert_store.EventAlphaAlertStoreConfig:
    alert_path = Path(path).expanduser() if path else config.EVENT_ALPHA_ALERT_STORE_PATH
    if not alert_path.is_absolute():
        alert_path = config.DATA_DIR / alert_path
    return event_alpha_alert_store.EventAlphaAlertStoreConfig(
        path=alert_path,
        snapshot_policy=config.EVENT_ALPHA_SNAPSHOT_POLICY,
        sampled_controls_limit=config.EVENT_ALPHA_SNAPSHOT_SAMPLED_CONTROLS,
    )

def _event_core_opportunity_store_config_from_runtime(
    path: str | None = None,
) -> event_core_opportunity_store.EventCoreOpportunityStoreConfig:
    core_path = Path(path).expanduser() if path else Path(getattr(config, "EVENT_CORE_OPPORTUNITY_STORE_PATH", config.EVENT_DISCOVERY_CACHE_DIR / "event_core_opportunities.jsonl"))
    if not core_path.is_absolute():
        core_path = config.DATA_DIR / core_path
    return event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=core_path)

def _event_alpha_run_ledger_config_from_runtime(path: str | None = None) -> event_alpha_run_ledger.EventAlphaRunLedgerConfig:
    ledger_path = Path(path).expanduser() if path else config.EVENT_ALPHA_RUN_LEDGER_PATH
    if not ledger_path.is_absolute():
        ledger_path = config.DATA_DIR / ledger_path
    return event_alpha_run_ledger.EventAlphaRunLedgerConfig(path=ledger_path)

def _event_alpha_notification_runs_config_from_runtime(
    path: str | None = None,
) -> event_alpha_notification_runs.EventAlphaNotificationRunsConfig:
    summary_path = Path(path).expanduser() if path else config.EVENT_ALPHA_NOTIFICATION_RUNS_PATH
    if not summary_path.is_absolute():
        summary_path = config.DATA_DIR / summary_path
    return event_alpha_notification_runs.EventAlphaNotificationRunsConfig(path=summary_path)

def _event_alpha_run_lock_config_from_runtime() -> event_alpha_run_lock.EventAlphaRunLockConfig:
    return event_alpha_run_lock.EventAlphaRunLockConfig(
        enabled=config.EVENT_ALPHA_NOTIFY_LOCK_ENABLED,
        stale_minutes=config.EVENT_ALPHA_NOTIFY_LOCK_STALE_MINUTES,
        allow_overlap=config.EVENT_ALPHA_NOTIFY_ALLOW_OVERLAP,
    )

def _cryptopanic_request_ledger_path() -> Path:
    explicit = getattr(config, "EVENT_DISCOVERY_CRYPTOPANIC_REQUEST_LEDGER_PATH", None)
    if explicit:
        explicit_path = Path(explicit).expanduser()
        if explicit_path.name != "cryptopanic_request_ledger.jsonl" or explicit_path.exists():
            return explicit_path
    health_path = Path(config.EVENT_PROVIDER_HEALTH_PATH).expanduser()
    if not health_path.is_absolute():
        health_path = config.DATA_DIR / health_path
    return health_path.with_name("cryptopanic_request_ledger.jsonl")

def _event_alpha_notify_context_from_runtime(
    profile_name: str | None,
) -> event_alpha_artifacts.EventAlphaArtifactContext:
    """Resolve the artifact context (namespace dir) for lock/delivery paths."""
    return event_alpha_artifacts.context_from_profile(
        profile_name,
        run_mode=config.EVENT_ALPHA_RUN_MODE or None,
        base_dir=config.EVENT_ALPHA_ARTIFACT_BASE_DIR,
        artifact_namespace=config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
    )

def _event_alpha_notification_delivery_config_from_runtime(
    context: event_alpha_artifacts.EventAlphaArtifactContext,
) -> event_alpha_notification_delivery.NotificationDeliveryConfig:
    return event_alpha_notification_delivery.config_for_context(
        context,
        dedupe_by_content=config.EVENT_ALPHA_NOTIFICATION_DEDUPE_BY_CONTENT,
        dedupe_window_hours=config.EVENT_ALPHA_NOTIFICATION_DEDUPE_WINDOW_HOURS,
        in_flight_grace_minutes=config.EVENT_ALPHA_NOTIFICATION_IN_FLIGHT_GRACE_MINUTES,
        partial_marks_cooldown=config.EVENT_ALPHA_NOTIFICATION_PARTIAL_MARKS_COOLDOWN,
    )

def _event_alpha_notification_pause_state(
    context: event_alpha_artifacts.EventAlphaArtifactContext,
) -> event_alpha_notification_pause.EventAlphaNotificationPauseState:
    return event_alpha_notification_pause.read_pause_state(
        context,
        env_paused=config.EVENT_ALPHA_NOTIFICATIONS_PAUSED,
        env_reason=config.EVENT_ALPHA_NOTIFICATIONS_PAUSE_REASON,
    )

def _apply_event_alpha_profile(profile_name: str | None) -> event_alpha_profiles.EventAlphaProfile | None:
    if not profile_name:
        return None
    profile = event_alpha_profiles.get_profile(profile_name)
    for attr, value in profile.config_overrides.items():
        value = _profile_override_value(attr, value)
        setattr(config, attr, value)
    _apply_event_alpha_artifact_context(profile.name)
    _normalize_profile_paths()
    return profile

_PROFILE_LOCAL_BUDGET_OVERRIDES: dict[str, type] = {
    "EVENT_ALPHA_EVIDENCE_ACQUISITION_MAX_CANDIDATES": int,
    "EVENT_ALPHA_EVIDENCE_ACQUISITION_MAX_QUERIES": int,
    "EVENT_ALPHA_EVIDENCE_ACQUISITION_TIMEOUT_SECONDS": float,
    "EVENT_CATALYST_SEARCH_MAX_ANOMALIES": int,
    "EVENT_CATALYST_SEARCH_MAX_QUERIES_PER_ANOMALY": int,
    "EVENT_CATALYST_SEARCH_MAX_RESULTS_PER_QUERY": int,
    "EVENT_DISCOVERY_CRYPTOPANIC_TIMEOUT": float,
    "EVENT_DISCOVERY_CRYPTOPANIC_WEEKLY_REQUEST_LIMIT": int,
    "EVENT_DISCOVERY_CRYPTOPANIC_REQUESTS_PER_RUN_LIMIT": int,
    "EVENT_DISCOVERY_CRYPTOPANIC_REQUESTS_PER_DAY_SOFT_LIMIT": int,
    "EVENT_DISCOVERY_CRYPTOPANIC_MIN_SECONDS_BETWEEN_REQUESTS": float,
    "EVENT_DISCOVERY_CRYPTOPANIC_MAX_PAGES_PER_QUERY": int,
    "EVENT_DISCOVERY_CRYPTOPANIC_MAX_CURRENCIES_PER_REQUEST": int,
    "EVENT_DISCOVERY_GDELT_TIMEOUT": float,
    "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_TIMEOUT": float,
    "EVENT_DISCOVERY_PROJECT_BLOG_RSS_TIMEOUT": float,
    "EVENT_IMPACT_HYPOTHESIS_MAX_DISCOVERY_QUERIES": int,
    "EVENT_IMPACT_HYPOTHESIS_MAX_DISCOVERY_RESULTS": int,
    "EVENT_IMPACT_HYPOTHESIS_MAX_HYPOTHESES": int,
    "EVENT_IMPACT_HYPOTHESIS_MAX_QUERIES_PER_HYPOTHESIS": int,
    "EVENT_LLM_CATALYST_FRAMES_MAX_ROWS_PER_RUN": int,
    "EVENT_LLM_MAX_CANDIDATES_PER_RUN": int,
    "EVENT_LLM_EXTRACTOR_MAX_EVENTS_PER_RUN": int,
    "EVENT_LLM_MAX_CALLS_PER_RUN": int,
    "EVENT_LLM_MAX_CALLS_PER_DAY": int,
    "EVENT_LLM_MAX_ESTIMATED_COST_USD_PER_DAY": float,
    "EVENT_LLM_ESTIMATED_COST_PER_CALL_USD": float,
    "EVENT_LLM_MAX_PARALLEL_CALLS": int,
    "EVENT_LLM_CACHE_TTL_HOURS": float,
    "EVENT_LLM_OPENAI_TIMEOUT": float,
    "EVENT_LLM_EXTRACTOR_OPENAI_TIMEOUT": float,
    "EVENT_SOURCE_ENRICHMENT_MAX_ROWS_PER_RUN": int,
    "EVENT_SOURCE_ENRICHMENT_TIMEOUT_SECONDS": float,
    "EVENT_ALPHA_NOTIFY_MAX_RUNTIME_SECONDS": float,
}

def _profile_override_value(attr: str, profile_value: Any) -> Any:
    """Let explicit runtime env vars intentionally tune profile caps."""
    caster = _PROFILE_LOCAL_BUDGET_OVERRIDES.get(attr)
    if caster is None:
        return profile_value
    raw = os.getenv(f"RSI_{attr}")
    if raw is None or raw == "":
        return profile_value
    try:
        return caster(raw)
    except (TypeError, ValueError):
        log.warning("Ignoring invalid local Event Alpha LLM budget override %s", f"RSI_{attr}")
        return profile_value

def _apply_event_alpha_context_to_config(context: event_alpha_artifacts.EventAlphaArtifactContext) -> None:
    config.EVENT_ALPHA_RUN_MODE = context.run_mode
    config.EVENT_ALPHA_ARTIFACT_NAMESPACE = context.artifact_namespace
    config.EVENT_ALPHA_ARTIFACT_BASE_DIR = context.base_dir
    config.EVENT_ALPHA_RUN_LEDGER_PATH = context.run_ledger_path
    config.EVENT_ALPHA_ALERT_STORE_PATH = context.alert_store_path
    config.EVENT_ALPHA_NOTIFICATION_RUNS_PATH = context.notification_runs_path
    config.EVENT_WATCHLIST_STATE_PATH = context.watchlist_state_path
    config.EVENT_ALPHA_FEEDBACK_PATH = context.feedback_path
    config.EVENT_ALPHA_MISSED_PATH = context.missed_path
    config.EVENT_ALPHA_PRIORS_PATH = context.priors_path
    config.EVENT_PROVIDER_HEALTH_PATH = context.provider_health_path
    config.EVENT_ALPHA_DAILY_BRIEF_PATH = context.daily_brief_path
    config.EVENT_IMPACT_HYPOTHESIS_STORE_PATH = context.impact_hypothesis_store_path
    config.EVENT_CORE_OPPORTUNITY_STORE_PATH = context.core_opportunity_store_path
    config.EVENT_INCIDENT_STORE_PATH = context.incident_store_path
    config.EVENT_ALPHA_EVIDENCE_ACQUISITION_PATH = context.evidence_acquisition_path
    config.EVENT_ALPHA_PROPOSED_EVAL_CASES_DIR = context.proposed_eval_cases_dir
    config.EVENT_RESEARCH_CARDS_DIR = context.research_cards_dir
    config.EVENT_LLM_BUDGET_LEDGER_PATH = context.llm_budget_ledger_path
    config.EVENT_ALPHA_OUTCOMES_PATH = context.outcomes_path

def _apply_event_alpha_artifact_context(profile_name: str | None = None) -> event_alpha_artifacts.EventAlphaArtifactContext:
    context = event_alpha_artifacts.context_from_profile(
        profile_name,
        run_mode=config.EVENT_ALPHA_RUN_MODE or None,
        base_dir=config.EVENT_ALPHA_ARTIFACT_BASE_DIR,
        artifact_namespace=config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
    )
    _apply_event_alpha_context_to_config(context)
    return context

def resolve_event_alpha_artifact_context_for_report(
    profile_name: str | None,
    artifact_namespace: str | None,
    run_mode: str | None = None,
    include_test_artifacts: bool = False,
) -> event_alpha_artifacts.EventAlphaArtifactContext:
    """Resolve and apply the exact artifact context a report should inspect."""
    if not profile_name and not artifact_namespace and not config.EVENT_ALPHA_ARTIFACT_NAMESPACE:
        base_dir = Path(config.EVENT_ALPHA_ARTIFACT_BASE_DIR).expanduser()
        if not base_dir.is_absolute():
            base_dir = config.DATA_DIR / base_dir
        context = event_alpha_artifacts.EventAlphaArtifactContext(
            profile="default",
            run_mode=run_mode or config.EVENT_ALPHA_RUN_MODE or "legacy",
            artifact_namespace="default",
            base_dir=base_dir,
            namespace_dir=base_dir,
            run_ledger_path=Path(config.EVENT_ALPHA_RUN_LEDGER_PATH),
            alert_store_path=Path(config.EVENT_ALPHA_ALERT_STORE_PATH),
            notification_runs_path=Path(config.EVENT_ALPHA_NOTIFICATION_RUNS_PATH),
            watchlist_state_path=Path(config.EVENT_WATCHLIST_STATE_PATH),
            feedback_path=Path(config.EVENT_ALPHA_FEEDBACK_PATH),
            missed_path=Path(config.EVENT_ALPHA_MISSED_PATH),
            priors_path=Path(config.EVENT_ALPHA_PRIORS_PATH),
            provider_health_path=Path(config.EVENT_PROVIDER_HEALTH_PATH),
            daily_brief_path=Path(config.EVENT_ALPHA_DAILY_BRIEF_PATH),
            impact_hypothesis_store_path=Path(config.EVENT_IMPACT_HYPOTHESIS_STORE_PATH),
            core_opportunity_store_path=Path(getattr(config, "EVENT_CORE_OPPORTUNITY_STORE_PATH", base_dir / "event_core_opportunities.jsonl")),
            incident_store_path=Path(config.EVENT_INCIDENT_STORE_PATH),
            evidence_acquisition_path=Path(config.EVENT_ALPHA_EVIDENCE_ACQUISITION_PATH),
            proposed_eval_cases_dir=Path(config.EVENT_ALPHA_PROPOSED_EVAL_CASES_DIR),
            research_cards_dir=Path(config.EVENT_RESEARCH_CARDS_DIR),
            llm_budget_ledger_path=Path(config.EVENT_LLM_BUDGET_LEDGER_PATH),
            outcomes_path=Path(getattr(config, "EVENT_ALPHA_OUTCOMES_PATH", base_dir / "event_alpha_outcomes.jsonl")),
        )
        _apply_event_alpha_context_to_config(context)
        _normalize_profile_paths()
        return context
    profile = _apply_event_alpha_profile(profile_name) if profile_name else None
    selected_profile = profile.name if profile else profile_name
    selected_namespace = artifact_namespace or (None if selected_profile else config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None)
    context = event_alpha_artifacts.context_from_profile(
        selected_profile,
        run_mode=run_mode or config.EVENT_ALPHA_RUN_MODE or None,
        base_dir=config.EVENT_ALPHA_ARTIFACT_BASE_DIR,
        artifact_namespace=selected_namespace,
    )
    _apply_event_alpha_context_to_config(context)
    _normalize_profile_paths()
    return context

def _event_alpha_context_block(context: event_alpha_artifacts.EventAlphaArtifactContext) -> str:
    def _display(path: Path) -> str:
        return event_artifact_paths.artifact_display_path(path, artifact_base=context.namespace_dir)

    return "\n".join([
        "artifact context:",
        f"- profile: {context.profile}",
        f"- artifact_namespace: {context.artifact_namespace}",
        f"- run_mode: {context.run_mode}",
        f"- run_ledger_path: {_display(context.run_ledger_path)}",
        f"- alert_store_path: {_display(context.alert_store_path)}",
        f"- notification_runs_path: {_display(context.notification_runs_path)}",
        f"- feedback_path: {_display(context.feedback_path)}",
        f"- provider_health_path: {_display(context.provider_health_path)}",
        f"- impact_hypothesis_store_path: {_display(context.impact_hypothesis_store_path)}",
        f"- core_opportunity_store_path: {_display(context.core_opportunity_store_path)}",
        f"- incident_store_path: {_display(context.incident_store_path)}",
        f"- evidence_acquisition_path: {_display(context.evidence_acquisition_path)}",
        f"- research_cards_dir: {_display(context.research_cards_dir)}",
    ])

def _event_alpha_report_path(path: str | None, fallback: Path) -> Path:
    if path:
        resolved = Path(path).expanduser()
        return resolved if resolved.is_absolute() else config.DATA_DIR / resolved
    return fallback

def _event_alpha_report_context(
    profile_name: str | None,
    artifact_namespace: str | None,
) -> event_alpha_artifacts.EventAlphaArtifactContext:
    if profile_name or artifact_namespace:
        return resolve_event_alpha_artifact_context_for_report(profile_name, artifact_namespace)
    base_dir = Path(config.EVENT_ALPHA_ARTIFACT_BASE_DIR).expanduser()
    if not base_dir.is_absolute():
        base_dir = config.DATA_DIR / base_dir
    return event_alpha_artifacts.EventAlphaArtifactContext(
        profile="default",
        run_mode=config.EVENT_ALPHA_RUN_MODE or "legacy",
        artifact_namespace=config.EVENT_ALPHA_ARTIFACT_NAMESPACE or "default",
        base_dir=base_dir,
        namespace_dir=base_dir,
        run_ledger_path=Path(config.EVENT_ALPHA_RUN_LEDGER_PATH),
        alert_store_path=Path(config.EVENT_ALPHA_ALERT_STORE_PATH),
        notification_runs_path=Path(config.EVENT_ALPHA_NOTIFICATION_RUNS_PATH),
        watchlist_state_path=Path(config.EVENT_WATCHLIST_STATE_PATH),
        feedback_path=Path(config.EVENT_ALPHA_FEEDBACK_PATH),
        missed_path=Path(config.EVENT_ALPHA_MISSED_PATH),
        priors_path=Path(config.EVENT_ALPHA_PRIORS_PATH),
        provider_health_path=Path(config.EVENT_PROVIDER_HEALTH_PATH),
        daily_brief_path=Path(config.EVENT_ALPHA_DAILY_BRIEF_PATH),
        impact_hypothesis_store_path=Path(config.EVENT_IMPACT_HYPOTHESIS_STORE_PATH),
        core_opportunity_store_path=Path(getattr(config, "EVENT_CORE_OPPORTUNITY_STORE_PATH", base_dir / "event_core_opportunities.jsonl")),
        incident_store_path=Path(config.EVENT_INCIDENT_STORE_PATH),
        evidence_acquisition_path=Path(config.EVENT_ALPHA_EVIDENCE_ACQUISITION_PATH),
        proposed_eval_cases_dir=Path(config.EVENT_ALPHA_PROPOSED_EVAL_CASES_DIR),
        research_cards_dir=Path(config.EVENT_RESEARCH_CARDS_DIR),
        llm_budget_ledger_path=Path(config.EVENT_LLM_BUDGET_LEDGER_PATH),
        outcomes_path=Path(getattr(config, "EVENT_ALPHA_OUTCOMES_PATH", base_dir / "event_alpha_outcomes.jsonl")),
    )

def _normalize_profile_paths() -> None:
    for attr in (
        "EVENT_DISCOVERY_UNIVERSE_PATH",
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS_PATH",
        "EVENT_CATALYST_SEARCH_FIXTURE_PATH",
        "EVENT_WATCHLIST_STATE_PATH",
        "EVENT_WATCHLIST_MONITOR_MARKET_PATH",
        "EVENT_ALPHA_ALERT_STORE_PATH",
        "EVENT_ALPHA_NOTIFICATION_RUNS_PATH",
        "EVENT_ALPHA_RUN_LEDGER_PATH",
        "EVENT_ALPHA_MISSED_PATH",
        "EVENT_ALPHA_PRIORS_PATH",
        "EVENT_ALPHA_OUTCOMES_PATH",
        "EVENT_PROVIDER_HEALTH_PATH",
        "EVENT_ALPHA_DAILY_BRIEF_PATH",
        "EVENT_IMPACT_HYPOTHESIS_STORE_PATH",
        "EVENT_CORE_OPPORTUNITY_STORE_PATH",
        "EVENT_INCIDENT_STORE_PATH",
        "EVENT_ALPHA_EVIDENCE_ACQUISITION_PATH",
        "EVENT_ALPHA_PROPOSED_EVAL_CASES_DIR",
        "EVENT_RESEARCH_CARDS_DIR",
        "EVENT_LLM_BUDGET_LEDGER_PATH",
    ):
        value = getattr(config, attr, None)
        if isinstance(value, Path):
            resolved = value.expanduser()
            if not resolved.is_absolute():
                resolved = config.DATA_DIR / resolved
            setattr(config, attr, resolved)
    rss_path = getattr(config, "EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS_PATH", None)
    if rss_path and not getattr(config, "EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS", ()):
        try:
            urls = [
                line.strip()
                for line in Path(rss_path).read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
            config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS = tuple(dict.fromkeys(urls))
        except OSError:
            config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS = ()

def _research_card_markdown_paths(cards_dir: str | Path, *, include_index: bool = False) -> list[Path]:
    directory = Path(cards_dir)
    if not directory.exists():
        return []
    return sorted(
        path for path in directory.glob("*.md")
        if include_index or path.name != "index.md"
    )

def _event_alpha_card_lineage_context(
    *,
    run_id: str | None,
    profile: str | None,
    run_mode: str | None,
    artifact_namespace: str | None,
) -> dict[str, str]:
    return {
        "run_id": str(run_id or "manual_card_write"),
        "profile": str(profile or "default"),
        "run_mode": str(run_mode or "legacy"),
        "artifact_namespace": str(artifact_namespace or "default"),
    }

def _latest_event_alpha_run_id(path: str | Path) -> str | None:
    rows = event_alpha_run_ledger.load_run_records(path, limit=1).rows
    if not rows:
        return None
    return str(rows[0].get("run_id") or "") or None

def _latest_event_alpha_profile_from_runs() -> str | None:
    rows = event_alpha_run_ledger.load_run_records(config.EVENT_ALPHA_RUN_LEDGER_PATH, limit=1).rows
    if not rows:
        return None
    profile = str(rows[0].get("profile") or "").strip()
    return profile if profile and profile != "default" else None

def _apply_event_alpha_report_profile(
    profile_name: str | None,
    *,
    infer_latest: bool = False,
) -> tuple[event_alpha_profiles.EventAlphaProfile | None, str | None]:
    selected = profile_name or (_latest_event_alpha_profile_from_runs() if infer_latest else None)
    if not selected:
        return None, None
    try:
        return _apply_event_alpha_profile(selected), None
    except ValueError as exc:
        return None, str(exc)

def _setup_event_discovery_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-5s %(message)s",
        datefmt="%H:%M:%S",
    )

def _event_alpha_inputs_configured() -> bool:
    return bool(
        config.EVENT_ANOMALY_SCANNER_ENABLED
        or config.EVENT_MARKET_ENRICHMENT_ENABLED
        or config.EVENT_CATALYST_SEARCH_ENABLED
        or _event_discovery_paths_configured()
    )

def event_alpha_cycle(
    verbose: bool = False,
    with_llm: bool = False,
    send: bool = False,
    event_now: str | datetime | None = None,
    profile_name: str | None = None,
) -> None:
    from .. import event_alpha as _event_alpha_service
    return _event_alpha_service.event_alpha_cycle(verbose, with_llm, send, event_now, profile_name)

def event_alpha_profile_report(profile_name: str, verbose: bool = False) -> None:
    """Print one Event Alpha operational profile."""
    _setup_event_discovery_logging(verbose)
    try:
        profile = event_alpha_profiles.get_profile(profile_name)
    except ValueError as exc:
        print(str(exc))
        return
    print(event_alpha_profiles.format_profile_report(profile))

class NotificationRuntimeBudget:
    """Small wall-clock budget helper for day-1 notification cycles."""

    def __init__(self, started_at: datetime, max_seconds: float) -> None:
        self.started_at = started_at.astimezone(timezone.utc) if started_at.tzinfo else started_at.replace(tzinfo=timezone.utc)
        self.max_seconds = float(max_seconds or 0.0)

    def remaining_seconds(self) -> float:
        if self.max_seconds <= 0:
            return 0.0
        elapsed = (datetime.now(timezone.utc) - self.started_at).total_seconds()
        return max(0.0, self.max_seconds - elapsed)

    def exhausted(self) -> bool:
        return self.max_seconds <= 0 or self.remaining_seconds() <= 0

    def warning_if_low(self, stage: str) -> str | None:
        if not self.exhausted():
            return None
        clean_stage = "".join(ch if ch.isalnum() else "_" for ch in str(stage or "stage").strip().lower()).strip("_")
        return f"notification_runtime_budget_exhausted_before_{clean_stage or 'stage'}"

def _notification_runtime_budget(started_at: datetime) -> NotificationRuntimeBudget:
    return NotificationRuntimeBudget(
        started_at,
        float(getattr(config, "EVENT_ALPHA_NOTIFY_MAX_RUNTIME_SECONDS", 120.0) or 0.0),
    )

def _notification_runtime_budget_exhausted(started_at: datetime) -> bool:
    return _notification_runtime_budget(started_at).exhausted()

def _notification_warnings_indicate_partial(warnings: Iterable[str]) -> bool:
    tokens = (
        "notification_cycle_failed_soft",
        "notification_runtime_budget_exhausted",
        "market_enrichment_live_fetch_failed",
        "failed",
        "failure",
        "timeout",
        "dns",
        "backoff",
        "429",
    )
    return any(any(token in str(warning).casefold() for token in tokens) for warning in warnings)

def _empty_notification_pipeline_result(
    *,
    now: datetime,
    warning: str,
    cycle_completed: bool = False,
) -> event_alpha_pipeline.EventAlphaPipelineResult:
    watch_cfg = _event_watchlist_config_from_runtime()
    router_cfg = _event_alpha_router_config_from_runtime()
    watchlist = event_watchlist.load_watchlist(watch_cfg.state_path or config.EVENT_WATCHLIST_STATE_PATH)
    router_result = event_alpha_router.route_watchlist(watchlist, cfg=router_cfg)
    return event_alpha_pipeline.EventAlphaPipelineResult(
        discovery_result=EventDiscoveryResult((), (), (), (), ()),
        alerts=[],
        catalyst_search_result=None,
        hypothesis_search_result=None,
        anomaly_lifecycle_result=None,
        extraction_rows=[],
        catalyst_frame_rows=[],
        relationship_rows=[],
        watchlist_result=None,
        watchlist_monitor_result=None,
        router_result=router_result,
        warnings=(warning,),
        cycle_completed=cycle_completed,
        partial_results=True,
    )

def format_event_alpha_notification_next_steps(
    *,
    profile: str,
    provider_health_rows: Mapping[str, Mapping[str, Any]] | None = None,
    result: Any | None = None,
    notification_row: Mapping[str, Any] | None = None,
) -> str:
    """Render post-run operator commands without mutating state."""
    rows = provider_health_rows or {}
    backoff_keys = tuple(
        str(row.get("provider_key") or key)
        for key, row in rows.items()
        if row.get("disabled_until")
    )
    would_send = _int_value(
        (notification_row or {}).get("would_send_count")
        if notification_row is not None
        else getattr(result, "send_would_send_items", 0)
    )
    cards_written = len(tuple(getattr(result, "research_card_paths", ()) or ()))
    alertable = _int_value(getattr(result, "alertable", 0))
    feedback_target = _first_notification_feedback_target(result)
    lines = [
        "=" * 76,
        "EVENT ALPHA NOTIFICATION NEXT STEPS",
        "=" * 76,
        f"- make event-alpha-notification-runs-report PROFILE={profile}",
        f"- make event-alpha-notification-inbox PROFILE={profile}",
        f"- make event-alpha-daily-brief PROFILE={profile}",
        f"- make event-alpha-artifact-doctor PROFILE={profile} STRICT=1",
        f"- make event-alpha-provider-health-report PROFILE={profile}",
    ]
    if backoff_keys:
        lines.append(
            f"- make event-alpha-provider-health-reset PROFILE={profile} "
            f"PROVIDER_KEY={backoff_keys[0]} CONFIRM=1"
        )
    if would_send > 0 or cards_written > 0 or alertable > 0:
        target = feedback_target or "<alert_id_or_card_id>"
        lines.append(f"- make event-feedback-watch PROFILE={profile} FEEDBACK_TARGET='{target}'")
    else:
        lines.append("- no alert/cards produced; review heartbeat status in the runs report and daily brief")
    lines.append("Research-only follow-up only; these commands do not trade, paper trade, or write normal RSI signals.")
    return "\n".join(lines).rstrip()

def _first_notification_feedback_target(result: Any | None) -> str | None:
    router_result = getattr(result, "router_result", None)
    decisions = tuple(getattr(router_result, "alertable_decisions", ()) or ())
    if not decisions:
        decisions = tuple(getattr(router_result, "decisions", ()) or ())
    for decision in decisions:
        alert_id = str(getattr(decision, "alert_id", "") or "").strip()
        if alert_id:
            return alert_id
        card_id = str(getattr(decision, "card_id", "") or "").strip()
        if card_id:
            return card_id
    for path in tuple(getattr(result, "research_card_paths", ()) or ()):
        stem = Path(path).stem
        if stem and stem != "index":
            return stem
    return None

def _int_value(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0

def _event_llm_provider(llm_cfg: event_llm_analyzer.EventLLMConfig):
    provider_name = llm_cfg.provider.strip().lower()
    if provider_name == "fixture":
        return FixtureLLMRelationshipProvider()
    if provider_name == "openai":
        if not llm_cfg.enabled:
            print("Event LLM OpenAI provider disabled. Set RSI_EVENT_LLM_ENABLED=1 to opt into live LLM calls.")
            return None
        return OpenAILLMRelationshipProvider(
            api_key=config.OPENAI_API_KEY,
            model=llm_cfg.model,
            prompt_version=llm_cfg.prompt_version,
            timeout=config.EVENT_LLM_OPENAI_TIMEOUT,
        )
    print(f"Unknown event LLM provider: {llm_cfg.provider}. Use fixture or openai.")
    return None

def _event_llm_extraction_provider(extractor_cfg: event_llm_extractor.EventLLMExtractorConfig):
    provider_name = extractor_cfg.provider.strip().lower()
    if provider_name == "fixture":
        return FixtureLLMExtractionProvider()
    if provider_name == "openai":
        if not extractor_cfg.enabled:
            print(
                "Event LLM OpenAI extractor disabled. "
                "Set RSI_EVENT_LLM_EXTRACTOR_ENABLED=1 to opt into live LLM calls."
            )
            return None
        return OpenAILLMExtractionProvider(
            api_key=config.OPENAI_API_KEY,
            model=extractor_cfg.model,
            prompt_version=extractor_cfg.prompt_version,
            timeout=config.EVENT_LLM_EXTRACTOR_OPENAI_TIMEOUT,
        )
    print(f"Unknown event LLM extractor provider: {extractor_cfg.provider}. Use fixture or openai.")
    return None

def _event_llm_catalyst_frame_provider(catalyst_frame_cfg: event_llm_catalyst_frames.EventLLMCatalystFrameConfig):
    provider_name = catalyst_frame_cfg.provider.strip().lower()
    if provider_name == "fixture":
        return FixtureLLMCatalystFrameProvider()
    if provider_name == "openai":
        if not catalyst_frame_cfg.enabled:
            print(
                "Event LLM catalyst-frame OpenAI provider disabled. "
                "Set RSI_EVENT_LLM_CATALYST_FRAMES_ENABLED=1 to opt into live LLM calls."
            )
            return None
        return OpenAILLMRelationshipProvider(
            api_key=config.OPENAI_API_KEY,
            model=catalyst_frame_cfg.model,
            prompt_version=catalyst_frame_cfg.prompt_version,
            timeout=config.EVENT_LLM_OPENAI_TIMEOUT,
        )
    print(f"Unknown event LLM catalyst-frame provider: {catalyst_frame_cfg.provider}. Use fixture or openai.")
    return None

def _event_catalyst_search_provider(
    search_cfg: event_catalyst_search.EventCatalystSearchConfig,
):
    from .. import event_alpha as _event_alpha_service
    return _event_alpha_service._event_catalyst_search_provider(search_cfg)

def _event_evidence_acquisition_providers_from_runtime(
    cfg: event_evidence_acquisition.EvidenceAcquisitionConfig,
):
    from .. import event_alpha as _event_alpha_service
    return _event_alpha_service._event_evidence_acquisition_providers_from_runtime(cfg)

def _send_event_alert_digest(
    alerts: list[event_alerts.EventAlertCandidate],
    cfg: event_alerts.EventAlertConfig,
    *,
    now: datetime | None = None,
) -> None:
    if not cfg.enabled:
        print("Event research alert sending disabled. Set RSI_EVENT_ALERTS_ENABLED=1 to opt in.")
        return
    if cfg.mode != "research_only":
        print("Event research alert sending blocked: RSI_EVENT_ALERT_MODE must remain research_only.")
        return
    digest = event_alerts.digest_candidates(alerts, cfg=cfg)
    if not digest:
        print("Event research alert sending skipped: no candidates above digest threshold.")
        return
    storage = Storage(config.DB_PATH)
    try:
        now = now or datetime.now(timezone.utc)
        due, reason = _event_alert_digest_due(storage, cfg, now)
        if not due:
            print(f"Event research alert sending held: {reason}.")
            return
        recipients = storage.active_subscribers() or config.TELEGRAM_CHAT_IDS
        sent = send_telegram(
            event_alerts.format_event_alert_telegram_digest(digest),
            parse_mode="HTML",
            chat_ids=recipients,
        )
        if sent:
            _mark_event_alert_digest_sent(storage, len(digest), now)
            print(f"Event research Telegram digest sent with {len(digest)} item(s).")
        else:
            print("Event research Telegram digest not sent: no channel delivered.")
    finally:
        storage.close()

def _send_event_alpha_routed_digest(
    decisions: list[event_alpha_router.EventAlphaRouteDecision],
    cfg: event_alerts.EventAlertConfig,
    *,
    now: datetime | None = None,
    profile: str | None = None,
    pipeline_result: event_alpha_pipeline.EventAlphaPipelineResult | None = None,
    card_path_by_alert_id: dict[str, str | Path] | None = None,
    include_health_heartbeat: bool = False,
    clock_status: dict[str, object] | None = None,
    delivery_cfg: event_alpha_notification_delivery.NotificationDeliveryConfig | None = None,
    run_id: str | None = None,
    namespace: str | None = None,
    pause_state: event_alpha_notification_pause.EventAlphaNotificationPauseState | None = None,
    core_opportunity_rows: Iterable[Mapping[str, object]] = (),
) -> event_alpha_pipeline.EventAlphaSendResult:
    from .. import event_alpha as _event_alpha_service
    return _event_alpha_service._send_event_alpha_routed_digest(decisions, cfg, now=now, profile=profile, pipeline_result=pipeline_result, card_path_by_alert_id=card_path_by_alert_id, include_health_heartbeat=include_health_heartbeat, clock_status=clock_status, delivery_cfg=delivery_cfg, run_id=run_id, namespace=namespace, pause_state=pause_state, core_opportunity_rows=core_opportunity_rows)

def _event_alert_digest_due(
    storage: Storage,
    cfg: event_alerts.EventAlertConfig,
    now: datetime,
) -> tuple[bool, str]:
    last_raw = storage.get_meta("event_alert_last_digest_at")
    if last_raw:
        try:
            last = datetime.fromisoformat(last_raw)
            last = last if last.tzinfo else last.replace(tzinfo=timezone.utc)
        except ValueError:
            last = None
        if last and (now - last.astimezone(timezone.utc)).total_seconds() / 3600.0 < cfg.cooldown_hours:
            return False, f"cooldown active for {cfg.cooldown_hours:g}h"
    day_key = f"event_alert_sent_count_{now.date().isoformat()}"
    try:
        sent_today = int(storage.get_meta(day_key) or "0")
    except ValueError:
        sent_today = 0
    if sent_today >= cfg.max_instant_per_day:
        return False, f"daily send cap reached ({cfg.max_instant_per_day})"
    return True, "due"

def _mark_event_alert_digest_sent(storage: Storage, item_count: int, now: datetime) -> None:
    storage.set_meta("event_alert_last_digest_at", now.isoformat())
    day_key = f"event_alert_sent_count_{now.date().isoformat()}"
    try:
        sent_today = int(storage.get_meta(day_key) or "0")
    except ValueError:
        sent_today = 0
    storage.set_meta(day_key, str(sent_today + 1))
    storage.set_meta("event_alert_last_digest_items", str(item_count))

def event_discovery_status(json_output: bool = False) -> None:
    """Print redacted readiness for research-only event-discovery providers."""
    status_report = event_provider_status.build_event_discovery_provider_status(config)
    if json_output:
        print(json.dumps(event_provider_status.provider_status_to_dict(status_report), indent=2, sort_keys=True))
    else:
        print(event_provider_status.format_event_discovery_provider_status(status_report))

def event_discovery_runs(limit: int | None = 10, json_output: bool = False) -> None:
    """Print recent event-discovery cache run diagnostics."""
    read = event_cache.load_discovery_runs(config.EVENT_DISCOVERY_CACHE_DIR, limit=limit)
    if json_output:
        print(json.dumps({
            "cache_dir": str(read.cache_dir),
            "runs_read": read.runs_read,
            "limit": read.limit,
            "rows": read.rows,
        }, indent=2, sort_keys=True))
        return
    print(_format_event_discovery_runs(read))

def _format_event_discovery_runs(read: event_cache.EventDiscoveryRunsReadResult) -> str:
    lines = [
        "EVENT DISCOVERY CACHE RUNS",
        f"Cache dir: {read.cache_dir}",
        f"Runs shown: {len(read.rows)}/{read.runs_read}",
    ]
    if not read.rows:
        lines.extend([
            "",
            "No discovery runs cached.",
            "Run `main.py --event-discovery-status`, then `main.py --event-discovery-refresh` with a working event source.",
        ])
        return "\n".join(lines)
    lines.append("")
    for row in read.rows:
        diagnostics = row.get("diagnostics") if isinstance(row.get("diagnostics"), dict) else {}
        provider_status = diagnostics.get("provider_status") if isinstance(diagnostics.get("provider_status"), dict) else {}
        warnings = diagnostics.get("refresh_warnings") if isinstance(diagnostics.get("refresh_warnings"), list) else []
        ready_sources = provider_status.get("ready_event_source_count", "?")
        ready = provider_status.get("ready_for_configured_review_cycle")
        ready_text = "yes" if ready is True else "no" if ready is False else "unknown"
        lines.append(
            f"- {row.get('observed_at', '?')} run={row.get('run_id', '?')} "
            f"raw={row.get('raw_events', 0)} normalized={row.get('normalized_events', 0)} "
            f"links={row.get('event_asset_links', 0)} classifications={row.get('classifications', 0)} "
            f"snapshots={row.get('candidate_snapshots', 0)} "
            f"ready_sources={ready_sources} ready={ready_text} warnings={len(warnings)}"
        )
        for warning in warnings:
            lines.append(f"  warning: {warning}")
    return "\n".join(lines)

def event_discovery_refresh(verbose: bool = False, event_now: str | datetime | None = None) -> None:
    """Fetch configured event-discovery sources and write observational cache artifacts."""
    _setup_event_discovery_logging(verbose)
    status_report = event_provider_status.build_event_discovery_provider_status(config)
    if not status_report.ready_for_configured_review_cycle:
        print(
            "No event-discovery sources ready. Set RSI_EVENT_DISCOVERY_EVENTS_PATH, "
            "another event-discovery fixture path, or opt into a live research provider. "
            "Run --event-discovery-status for a redacted readiness report."
        )
        return
    now = _event_research_now(event_now)
    result = _event_discovery_result_from_config(now=now)
    diagnostics = _event_discovery_refresh_diagnostics(result, status_report)
    write = event_cache.write_event_discovery_cache(
        result,
        config.EVENT_DISCOVERY_CACHE_DIR,
        observed_at=now,
        diagnostics=diagnostics,
    )
    print(
        "Event-discovery cache refresh: "
        f"raw={write.raw_events_written}, "
        f"normalized={write.normalized_events_written}, "
        f"links={write.event_asset_links_written}, "
        f"classifications={write.classifications_written}, "
        f"candidate_snapshots={write.candidate_snapshots_written}, "
        f"run={write.run_id}, dir={write.cache_dir}"
    )
    for warning in diagnostics["refresh_warnings"]:
        print(f"WARNING: {warning}")

__all__ = (
    '_event_discovery_paths_configured',
    '_event_discovery_refresh_diagnostics',
    '_event_research_now',
    'event_research_now_from_config',
    '_event_clock_status',
    '_event_alpha_clock_line',
    '_event_alpha_notify_clock_warnings',
    '_event_alpha_notify_fixed_clock_blocker',
    '_event_discovery_result_from_config',
    '_event_alert_config_from_runtime',
    '_event_alpha_priors_config_from_runtime',
    '_event_provider_health_config_from_runtime',
    '_event_alpha_notification_mode',
    '_event_alpha_retention_config_from_runtime',
    '_event_llm_config_from_runtime',
    '_event_llm_extractor_config_from_runtime',
    '_event_llm_catalyst_frame_config_from_runtime',
    '_event_impact_hypothesis_store_config_from_runtime',
    '_event_incident_store_config_from_runtime',
    '_event_watchlist_config_from_runtime',
    '_event_watchlist_monitor_market_rows_from_runtime',
    '_event_watchlist_monitor_derivatives_rows_from_runtime',
    '_event_watchlist_monitor_supply_rows_from_runtime',
    '_event_watchlist_market_provider_from_runtime',
    '_event_watchlist_monitor_result_from_runtime',
    '_event_alpha_router_config_from_runtime',
    '_event_near_miss_config_from_runtime',
    '_event_alpha_notification_config_from_runtime',
    '_event_catalyst_search_config_from_runtime',
    '_event_impact_hypothesis_search_config_from_runtime',
    '_event_evidence_acquisition_config_from_runtime',
    '_event_source_enrichment_config_from_runtime',
    '_event_feedback_config_from_runtime',
    '_event_alpha_alert_store_config_from_runtime',
    '_event_core_opportunity_store_config_from_runtime',
    '_event_alpha_run_ledger_config_from_runtime',
    '_event_alpha_notification_runs_config_from_runtime',
    '_event_alpha_run_lock_config_from_runtime',
    '_cryptopanic_request_ledger_path',
    '_event_alpha_notify_context_from_runtime',
    '_event_alpha_notification_delivery_config_from_runtime',
    '_event_alpha_notification_pause_state',
    '_apply_event_alpha_profile',
    '_profile_override_value',
    '_apply_event_alpha_context_to_config',
    '_apply_event_alpha_artifact_context',
    'resolve_event_alpha_artifact_context_for_report',
    '_event_alpha_context_block',
    '_event_alpha_report_path',
    '_event_alpha_report_context',
    '_normalize_profile_paths',
    '_research_card_markdown_paths',
    '_event_alpha_card_lineage_context',
    '_latest_event_alpha_run_id',
    '_latest_event_alpha_profile_from_runs',
    '_apply_event_alpha_report_profile',
    '_setup_event_discovery_logging',
    '_event_alpha_inputs_configured',
    'event_alpha_cycle',
    'event_alpha_profile_report',
    'NotificationRuntimeBudget',
    '_notification_runtime_budget',
    '_notification_runtime_budget_exhausted',
    '_notification_warnings_indicate_partial',
    '_empty_notification_pipeline_result',
    'format_event_alpha_notification_next_steps',
    '_first_notification_feedback_target',
    '_int_value',
    '_event_llm_provider',
    '_event_llm_extraction_provider',
    '_event_llm_catalyst_frame_provider',
    '_event_catalyst_search_provider',
    '_event_evidence_acquisition_providers_from_runtime',
    '_send_event_alert_digest',
    '_send_event_alpha_routed_digest',
    '_event_alert_digest_due',
    '_mark_event_alert_digest_sent',
    'event_discovery_status',
    'event_discovery_runs',
    '_format_event_discovery_runs',
    'event_discovery_refresh',
)
