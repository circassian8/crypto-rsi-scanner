"""Provider readiness and provider preflight CLI command handlers."""

from __future__ import annotations

from ._scanner_bindings import bind_scanner_globals

PROVIDER_READINESS_COMMAND_GROUP = "provider_readiness"


def handle(args) -> bool:
    bind_scanner_globals(globals())
    if args.event_alpha_provider_health_report:
        event_alpha_provider_health_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
        )
        return True
    if args.event_alpha_cryptopanic_preflight:
        event_alpha_cryptopanic_preflight(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
        )
        return True
    if args.event_alpha_source_coverage_report:
        event_alpha_source_coverage_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
        )
        return True
    if args.event_alpha_live_provider_readiness or args.event_alpha_live_provider_readiness_smoke:
        event_alpha_live_provider_readiness_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            smoke_mode=bool(args.event_alpha_live_provider_readiness_smoke),
        )
        return True
    if args.event_alpha_dex_onchain_readiness or args.event_alpha_dex_onchain_readiness_smoke:
        event_alpha_dex_onchain_readiness_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            smoke_mode=bool(args.event_alpha_dex_onchain_readiness_smoke),
            include_test_artifacts=args.event_alpha_include_test_artifacts,
        )
        return True
    if (
        args.event_alpha_unlock_calendar_preflight
        or args.event_alpha_tokenomist_preflight
        or args.event_alpha_messari_unlocks_preflight
        or args.event_alpha_coinmarketcal_preflight
    ):
        provider_filter = args.event_alpha_unlock_calendar_provider
        if args.event_alpha_tokenomist_preflight:
            provider_filter = "tokenomist"
        elif args.event_alpha_messari_unlocks_preflight:
            provider_filter = "messari_unlocks"
        elif args.event_alpha_coinmarketcal_preflight:
            provider_filter = "coinmarketcal"
        event_alpha_unlock_calendar_preflight_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            provider=provider_filter,
            smoke_mode=bool(args.event_alpha_include_test_artifacts),
            include_test_artifacts=args.event_alpha_include_test_artifacts,
        )
        return True
    if args.event_alpha_coinalyze_preflight or args.event_alpha_coinalyze_preflight_smoke:
        event_alpha_coinalyze_preflight_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            smoke_mode=bool(args.event_alpha_coinalyze_preflight_smoke),
            allow_live_preflight=bool(args.event_alpha_coinalyze_allow_live_preflight),
        )
        return True
    if args.event_alpha_coinalyze_no_send_rehearsal:
        event_alpha_coinalyze_no_send_rehearsal(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            allow_live_preflight=bool(args.event_alpha_coinalyze_allow_live_preflight),
        )
        return True
    if args.event_alpha_bybit_announcements_preflight or args.event_alpha_bybit_announcements_preflight_smoke:
        event_alpha_bybit_announcements_preflight_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            smoke_mode=bool(args.event_alpha_bybit_announcements_preflight_smoke),
            allow_live_preflight=bool(args.event_alpha_bybit_announcements_allow_live_preflight),
        )
        return True
    if args.event_alpha_bybit_announcements_no_send_rehearsal:
        event_alpha_bybit_announcements_no_send_rehearsal(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            allow_live_preflight=bool(args.event_alpha_bybit_announcements_allow_live_preflight),
        )
        return True
    if args.event_alpha_official_exchange_report:
        event_alpha_official_exchange_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
            binance_path=args.event_alpha_official_exchange_binance,
            bybit_path=args.event_alpha_official_exchange_bybit,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
        )
        return True
    return False
