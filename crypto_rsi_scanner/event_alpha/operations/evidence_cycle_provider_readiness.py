"""Provider/config projection for read-only evidence-cycle readiness."""

from __future__ import annotations

from datetime import datetime
import math
from typing import Any, Mapping, Sequence

from ..radar.evidence.provider_contract import (
    PLANNER_PROVIDER_HINTS,
    configured_local_path_status,
    matching_provider_health_status,
    persisted_health_blocks_provider,
)
from .evidence_cycle_readiness_models import EvidenceProviderReadiness


_CURRENT_AUTHORIZATIONS_KEY = "_CURRENT_EXPLICIT_LIVE_AUTHORIZATIONS"

def _provider_readiness_rows(
    settings: Mapping[str, object],
    *,
    fixture_only: bool,
    health_rows: Mapping[str, Mapping[str, Any]],
    now: datetime,
) -> tuple[EvidenceProviderReadiness, ...]:
    if fixture_only:
        return tuple(
            _fixture_provider_row(hint, health_rows=health_rows, now=now)
            for hint in PLANNER_PROVIDER_HINTS
        )
    rows = [
        _simple_provider_row(
            "cryptopanic",
            runtime_mapping="CryptoPanicCatalystSearchProvider",
            local_path=settings.get("EVENT_DISCOVERY_CRYPTOPANIC_PATH"),
            live_enabled=bool(settings.get("EVENT_DISCOVERY_CRYPTOPANIC_LIVE")),
            current_authorized=_current_authorization(
                settings, "EVENT_DISCOVERY_CRYPTOPANIC_LIVE"
            ),
            credential_required=True,
            credential_present=bool(settings.get("EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN")),
            http_fanout=_cryptopanic_http_fanout(settings),
            ignore_backoff=bool(settings.get("EVENT_ALPHA_IGNORE_PROVIDER_BACKOFF")),
            health_rows=health_rows,
            now=now,
        ),
        _simple_provider_row(
            "gdelt",
            runtime_mapping="GdeltCatalystSearchProvider",
            local_path=settings.get("EVENT_DISCOVERY_GDELT_PATH"),
            live_enabled=bool(settings.get("EVENT_DISCOVERY_GDELT_LIVE")),
            current_authorized=_current_authorization(
                settings, "EVENT_DISCOVERY_GDELT_LIVE"
            ),
            credential_required=False,
            credential_present=None,
            http_fanout=1,
            ignore_backoff=bool(settings.get("EVENT_ALPHA_IGNORE_PROVIDER_BACKOFF")),
            health_rows=health_rows,
            now=now,
        ),
        _simple_provider_row(
            "polymarket",
            runtime_mapping="PolymarketCatalystSearchProvider",
            local_path=settings.get("EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH"),
            live_enabled=bool(
                settings.get("EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE")
            ),
            current_authorized=_current_authorization(
                settings, "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE"
            ),
            credential_required=False,
            credential_present=None,
            http_fanout=1,
            ignore_backoff=bool(settings.get("EVENT_ALPHA_IGNORE_PROVIDER_BACKOFF")),
            health_rows=health_rows,
            now=now,
        ),
        _rss_provider_row(settings, health_rows=health_rows, now=now),
        _official_exchange_provider_row(settings, health_rows=health_rows, now=now),
        _local_only_provider_row(
            "coinmarketcal",
            "EventProviderCatalystSearchProvider(CoinMarketCalProvider)",
            settings.get("EVENT_DISCOVERY_COINMARKETCAL_PATH"),
            ignore_backoff=bool(settings.get("EVENT_ALPHA_IGNORE_PROVIDER_BACKOFF")),
            health_rows=health_rows,
            now=now,
        ),
        _local_only_provider_row(
            "tokenomist",
            "EventProviderCatalystSearchProvider(TokenomistProvider)",
            settings.get("EVENT_DISCOVERY_TOKENOMIST_PATH"),
            ignore_backoff=bool(settings.get("EVENT_ALPHA_IGNORE_PROVIDER_BACKOFF")),
            health_rows=health_rows,
            now=now,
        ),
        _unavailable_live_provider("coinalyze", health_rows=health_rows, now=now),
        _unavailable_live_provider("sports_fixtures", health_rows=health_rows, now=now),
    ]
    return tuple(sorted(rows, key=lambda row: row.provider_hint))


def _source_configuration_summary(
    providers: Sequence[EvidenceProviderReadiness],
) -> dict[str, tuple[str, ...]]:
    return {
        "selected_live_http_authorized": tuple(
            row.provider_hint
            for row in providers
            if row.current_provider_call_eligibility
        ),
        "profile_capable_not_currently_authorized": tuple(
            row.provider_hint
            for row in providers
            if row.profile_live_capability
            and not row.current_explicit_authorization
            and row.acquisition_mode != "local_file"
        ),
        "local_source_ready": tuple(
            row.provider_hint
            for row in providers
            if row.acquisition_mode in {"local_file", "local_composite"}
        ),
        "fixture_only_or_stub": tuple(
            row.provider_hint
            for row in providers
            if row.acquisition_mode in {"fixture", "fixture_stub"}
        ),
        "configured_but_no_http_call": tuple(
            row.provider_hint
            for row in providers
            if row.evidence_query_eligible
            and not row.current_provider_call_eligibility
        ),
        "unavailable_or_disabled": tuple(
            row.provider_hint
            for row in providers
            if not row.evidence_query_eligible
        ),
    }


def _fixture_provider_row(
    hint: str,
    *,
    health_rows: Mapping[str, Mapping[str, Any]],
    now: datetime,
) -> EvidenceProviderReadiness:
    status, disabled_until = _health_status((hint,), health_rows, now=now)
    return EvidenceProviderReadiness(
        provider_hint=hint,
        runtime_mapping="FixtureCatalystSearchProvider",
        mapping_kind="explicit_fixture_only",
        logical_provider_fanout=1,
        acquisition_mode="fixture",
        evidence_query_eligible=True,
        live_evidence_eligible=False,
        profile_live_capability=False,
        current_explicit_authorization=False,
        current_authorization_status="not_applicable_fixture_only",
        current_provider_call_eligibility=False,
        http_request_fanout_max_per_logical_query=0,
        credential_requirement="none",
        credential_present=None,
        configured_local_source_status="fixture_contract",
        persisted_health_status=status,
        persisted_health_disabled_until=disabled_until,
        blockers=(),
        warnings=(),
    )


def _simple_provider_row(
    hint: str,
    *,
    runtime_mapping: str,
    local_path: object,
    live_enabled: bool,
    current_authorized: bool,
    credential_required: bool,
    credential_present: bool | None,
    http_fanout: int,
    ignore_backoff: bool,
    health_rows: Mapping[str, Mapping[str, Any]],
    now: datetime,
) -> EvidenceProviderReadiness:
    local_status = _local_path_status(local_path)
    health_status, disabled_until = _health_status((hint,), health_rows, now=now)
    blockers: list[str] = []
    if local_status == "regular_file":
        mode = "local_file"
        query_eligible = live_eligible = True
        auth = "not_required_local_file"
        call_eligible = False
        fanout = 0
    elif local_status not in {"not_configured", "regular_file"}:
        mode = "invalid_local_path"
        query_eligible = live_eligible = call_eligible = False
        auth = "blocked_invalid_local_path"
        fanout = 0
        blockers.append(f"{hint}_configured_local_path_{local_status}")
    elif live_enabled and not current_authorized:
        mode = "profile_capable_not_currently_authorized"
        query_eligible = live_eligible = call_eligible = False
        auth = "profile_capability_present_but_explicit_current_authorization_absent"
        fanout = 0
        blockers.append(f"{hint}_current_explicit_authorization_absent")
    elif live_enabled and current_authorized and (
        not credential_required or credential_present
    ):
        mode = "live_http"
        query_eligible = live_eligible = call_eligible = True
        auth = "explicit_current_authorization_and_configuration_present"
        fanout = max(0, int(http_fanout))
    elif live_enabled and current_authorized:
        mode = "missing_configuration"
        query_eligible = live_eligible = call_eligible = False
        auth = "explicit_current_authorization_present_but_required_credential_missing"
        fanout = 0
        blockers.append(f"{hint}_credential_missing")
    elif current_authorized:
        mode = "profile_capability_disabled"
        query_eligible = live_eligible = call_eligible = False
        auth = "explicit_current_authorization_present_but_profile_capability_disabled"
        fanout = 0
        blockers.append(f"{hint}_profile_live_capability_disabled")
    else:
        mode = "disabled"
        query_eligible = live_eligible = call_eligible = False
        auth = "live_authorization_flag_absent"
        fanout = 0
        blockers.append(f"{hint}_live_authorization_absent")
    warnings: list[str] = []
    if persisted_health_blocks_provider(
        health_status, ignore_backoff=ignore_backoff
    ):
        query_eligible = live_eligible = call_eligible = False
        fanout = 0
        blockers.append(f"{hint}_persisted_health_{health_status}")
    elif health_status in {"backoff", "degraded"}:
        warnings.append(f"{hint}_persisted_health_{health_status}_explicitly_ignored")
    return EvidenceProviderReadiness(
        provider_hint=hint,
        runtime_mapping=runtime_mapping,
        mapping_kind="explicit",
        logical_provider_fanout=1,
        acquisition_mode=mode,
        evidence_query_eligible=query_eligible,
        live_evidence_eligible=live_eligible,
        profile_live_capability=live_enabled,
        current_explicit_authorization=current_authorized,
        current_authorization_status=auth,
        current_provider_call_eligibility=call_eligible,
        http_request_fanout_max_per_logical_query=fanout,
        credential_requirement="api_token" if credential_required else "none",
        credential_present=credential_present,
        configured_local_source_status=local_status,
        persisted_health_status=health_status,
        persisted_health_disabled_until=disabled_until,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
    )


def _rss_provider_row(
    settings: Mapping[str, object],
    *,
    health_rows: Mapping[str, Mapping[str, Any]],
    now: datetime,
) -> EvidenceProviderReadiness:
    local_status = _local_path_status(settings.get("EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH"))
    urls = tuple(settings.get("EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS") or ())
    live_enabled = bool(settings.get("EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE"))
    current_authorized = _current_authorization(
        settings, "EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE"
    )
    ignore_backoff = bool(settings.get("EVENT_ALPHA_IGNORE_PROVIDER_BACKOFF"))
    status, disabled_until = _health_status(("rss", "project_blog_rss"), health_rows, now=now)
    blockers: list[str] = []
    if local_status == "regular_file":
        mode, eligible, call, fanout, auth = (
            "local_file",
            True,
            False,
            0,
            "not_required_local_file",
        )
    elif local_status not in {"not_configured", "regular_file"}:
        mode, eligible, call, fanout, auth = (
            "invalid_local_path",
            False,
            False,
            0,
            "blocked_invalid_local_path",
        )
        blockers.append(f"project_blog_rss_configured_local_path_{local_status}")
    elif live_enabled and not current_authorized:
        mode, eligible, call, fanout, auth = (
            "profile_capable_not_currently_authorized",
            False,
            False,
            0,
            "profile_capability_present_but_explicit_current_authorization_absent",
        )
        blockers.append("project_blog_rss_current_explicit_authorization_absent")
    elif live_enabled and current_authorized and urls:
        mode, eligible, call, fanout, auth = (
            "live_http_feed_bundle",
            True,
            True,
            len(urls),
            "explicit_current_authorization_and_feed_configuration_present",
        )
    elif live_enabled and current_authorized:
        mode, eligible, call, fanout, auth = (
            "missing_configuration",
            False,
            False,
            0,
            "explicit_current_authorization_present_but_feed_list_missing",
        )
        blockers.append("project_blog_rss_feed_urls_missing")
    elif current_authorized:
        mode, eligible, call, fanout, auth = (
            "profile_capability_disabled",
            False,
            False,
            0,
            "explicit_current_authorization_present_but_profile_capability_disabled",
        )
        blockers.append("project_blog_rss_profile_live_capability_disabled")
    else:
        mode, eligible, call, fanout, auth = (
            "disabled",
            False,
            False,
            0,
            "live_authorization_flag_absent",
        )
        blockers.append("project_blog_rss_live_authorization_absent")
    warnings: tuple[str, ...] = ()
    if persisted_health_blocks_provider(status, ignore_backoff=ignore_backoff):
        eligible = call = False
        fanout = 0
        blockers.append(f"project_blog_rss_persisted_health_{status}")
    elif status in {"backoff", "degraded"}:
        warnings = (f"project_blog_rss_persisted_health_{status}_explicitly_ignored",)
    return EvidenceProviderReadiness(
        provider_hint="project_blog_rss",
        runtime_mapping="ProjectRssCatalystSearchProvider",
        mapping_kind="explicit_with_rss_alias",
        logical_provider_fanout=1,
        acquisition_mode=mode,
        evidence_query_eligible=eligible,
        live_evidence_eligible=eligible,
        profile_live_capability=live_enabled,
        current_explicit_authorization=current_authorized,
        current_authorization_status=auth,
        current_provider_call_eligibility=call,
        http_request_fanout_max_per_logical_query=fanout,
        credential_requirement="none",
        credential_present=None,
        configured_local_source_status=local_status,
        persisted_health_status=status,
        persisted_health_disabled_until=disabled_until,
        blockers=tuple(blockers),
        warnings=warnings,
    )


def _official_exchange_provider_row(
    settings: Mapping[str, object],
    *,
    health_rows: Mapping[str, Mapping[str, Any]],
    now: datetime,
) -> EvidenceProviderReadiness:
    binance_local = _local_path_status(
        settings.get("EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH")
    )
    bybit_local = _local_path_status(
        settings.get("EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH")
    )
    binance_live_flag = bool(
        settings.get("EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE")
    )
    binance_authorized = _current_authorization(
        settings, "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE"
    )
    binance_credentials = bool(
        settings.get("EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_KEY")
    ) and bool(settings.get("EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_SECRET"))
    bybit_live = bool(settings.get("EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE"))
    bybit_authorized = _current_authorization(
        settings, "EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE"
    )
    ignore_backoff = bool(settings.get("EVENT_ALPHA_IGNORE_PROVIDER_BACKOFF"))
    local_components = sum(
        status == "regular_file" for status in (binance_local, bybit_local)
    )
    live_components = int(
        binance_local == "not_configured"
        and binance_live_flag
        and binance_authorized
        and binance_credentials
    ) + int(
        bybit_local == "not_configured" and bybit_live and bybit_authorized
    )
    invalid = [
        name
        for name, status in (
            ("binance", binance_local),
            ("bybit", bybit_local),
        )
        if status not in {"regular_file", "not_configured"}
    ]
    blockers: list[str] = [f"{name}_announcements_configured_local_path_invalid" for name in invalid]
    if binance_live_flag and not binance_authorized:
        blockers.append("binance_announcements_current_explicit_authorization_absent")
    if bybit_live and not bybit_authorized:
        blockers.append("bybit_announcements_current_explicit_authorization_absent")
    if (
        binance_local == "not_configured"
        and binance_live_flag
        and binance_authorized
        and not binance_credentials
    ):
        blockers.append("binance_announcements_credentials_missing")
    if not local_components and not live_components:
        blockers.append("official_exchange_has_no_eligible_component")
    status, disabled_until = _health_status(
        ("binance_announcements", "bybit_announcements"), health_rows, now=now
    )
    if live_components:
        mode = "live_composite" if not local_components else "mixed_local_live_composite"
    elif local_components:
        mode = "local_composite"
    elif invalid:
        mode = "invalid_local_path"
    else:
        mode = "disabled"
    eligible = bool(local_components or live_components)
    call_eligible = bool(live_components)
    fanout = live_components
    warnings: tuple[str, ...] = ()
    if persisted_health_blocks_provider(status, ignore_backoff=ignore_backoff):
        eligible = call_eligible = False
        fanout = 0
        blockers.append(f"official_exchange_persisted_health_{status}")
    elif status in {"backoff", "degraded"}:
        warnings = (f"official_exchange_persisted_health_{status}_explicitly_ignored",)
    auth = (
        "explicit_current_component_authorization_and_configuration_present"
        if live_components
        else "no_live_component_authorized"
    )
    return EvidenceProviderReadiness(
        provider_hint="official_exchange",
        runtime_mapping="CompositeCatalystSearchProvider(binance_announcements,bybit_announcements)",
        mapping_kind="explicit_composite_with_two_aliases",
        logical_provider_fanout=2,
        acquisition_mode=mode,
        evidence_query_eligible=eligible,
        live_evidence_eligible=eligible,
        profile_live_capability=bool(binance_live_flag or bybit_live),
        current_explicit_authorization=bool(binance_authorized or bybit_authorized),
        current_authorization_status=auth,
        current_provider_call_eligibility=call_eligible,
        http_request_fanout_max_per_logical_query=fanout,
        credential_requirement="binance_api_key_and_secret_for_binance_component_only",
        credential_present=binance_credentials if binance_live_flag else None,
        configured_local_source_status=(
            f"binance={binance_local};bybit={bybit_local}"
        ),
        persisted_health_status=status,
        persisted_health_disabled_until=disabled_until,
        blockers=tuple(blockers),
        warnings=warnings,
    )


def _local_only_provider_row(
    hint: str,
    runtime_mapping: str,
    local_path: object,
    *,
    ignore_backoff: bool,
    health_rows: Mapping[str, Mapping[str, Any]],
    now: datetime,
) -> EvidenceProviderReadiness:
    local_status = _local_path_status(local_path)
    eligible = local_status == "regular_file"
    status, disabled_until = _health_status((hint,), health_rows, now=now)
    blockers = [] if eligible else [f"{hint}_local_source_{local_status}"]
    warnings: tuple[str, ...] = ()
    if persisted_health_blocks_provider(status, ignore_backoff=ignore_backoff):
        eligible = False
        blockers.append(f"{hint}_persisted_health_{status}")
    elif status in {"backoff", "degraded"}:
        warnings = (f"{hint}_persisted_health_{status}_explicitly_ignored",)
    return EvidenceProviderReadiness(
        provider_hint=hint,
        runtime_mapping=runtime_mapping,
        mapping_kind="explicit_local_only",
        logical_provider_fanout=1,
        acquisition_mode="local_file" if eligible else "missing_configuration",
        evidence_query_eligible=eligible,
        live_evidence_eligible=eligible,
        profile_live_capability=False,
        current_explicit_authorization=False,
        current_authorization_status="not_required_local_file" if eligible else "local_source_missing",
        current_provider_call_eligibility=False,
        http_request_fanout_max_per_logical_query=0,
        credential_requirement="none",
        credential_present=None,
        configured_local_source_status=local_status,
        persisted_health_status=status,
        persisted_health_disabled_until=disabled_until,
        blockers=tuple(blockers),
        warnings=warnings,
    )


def _unavailable_live_provider(
    hint: str,
    *,
    health_rows: Mapping[str, Mapping[str, Any]],
    now: datetime,
) -> EvidenceProviderReadiness:
    status, disabled_until = _health_status((hint,), health_rows, now=now)
    return EvidenceProviderReadiness(
        provider_hint=hint,
        runtime_mapping="None",
        mapping_kind="explicit_unavailable",
        logical_provider_fanout=1,
        acquisition_mode="unavailable",
        evidence_query_eligible=False,
        live_evidence_eligible=False,
        profile_live_capability=False,
        current_explicit_authorization=False,
        current_authorization_status="no_live_adapter_mapped",
        current_provider_call_eligibility=False,
        http_request_fanout_max_per_logical_query=0,
        credential_requirement="none",
        credential_present=None,
        configured_local_source_status="not_applicable",
        persisted_health_status=status,
        persisted_health_disabled_until=disabled_until,
        blockers=(f"{hint}_has_no_nonfixture_runtime_adapter",),
        warnings=(),
    )




def _cryptopanic_http_fanout(settings: Mapping[str, object]) -> int:
    currencies = tuple(
        part.strip()
        for part in str(settings.get("EVENT_DISCOVERY_CRYPTOPANIC_CURRENCIES") or "").split(",")
        if part.strip()
    )
    currency_count = max(1, len(dict.fromkeys(currencies)))
    per_request = max(
        1,
        int(settings.get("EVENT_DISCOVERY_CRYPTOPANIC_MAX_CURRENCIES_PER_REQUEST") or 1),
    )
    pages = max(
        1, int(settings.get("EVENT_DISCOVERY_CRYPTOPANIC_MAX_PAGES_PER_QUERY") or 1)
    )
    calculated = math.ceil(currency_count / per_request) * pages
    per_provider_run_cap = int(
        settings.get("EVENT_DISCOVERY_CRYPTOPANIC_REQUESTS_PER_RUN_LIMIT") or 0
    )
    return min(calculated, per_provider_run_cap) if per_provider_run_cap > 0 else calculated




def _local_path_status(path_value: object) -> str:
    return configured_local_path_status(path_value)


def _health_status(
    aliases: Sequence[str],
    health_rows: Mapping[str, Mapping[str, Any]],
    *,
    now: datetime,
) -> tuple[str, str | None]:
    return matching_provider_health_status(aliases, health_rows, now=now)


def _current_authorization(settings: Mapping[str, object], setting_name: str) -> bool:
    values = settings.get(_CURRENT_AUTHORIZATIONS_KEY)
    return bool(values.get(setting_name)) if isinstance(values, Mapping) else False

provider_readiness_rows = _provider_readiness_rows
source_configuration_summary = _source_configuration_summary

__all__ = ("provider_readiness_rows", "source_configuration_summary")
