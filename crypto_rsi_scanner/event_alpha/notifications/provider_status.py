"""Readiness report for research-only event-discovery providers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import crypto_rsi_scanner.event_alpha.providers.source_packs as event_source_packs


@dataclass(frozen=True)
class ProviderStatus:
    name: str
    category: str
    ready: bool
    details: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class EventDiscoveryProviderStatus:
    mode: str
    cache_dir: str
    lookback_hours: int
    horizon_days: int
    sources: tuple[ProviderStatus, ...]
    enrichment: tuple[ProviderStatus, ...]
    warnings: tuple[str, ...]
    next_steps: tuple[str, ...]

    @property
    def ready_event_source_count(self) -> int:
        return sum(1 for item in self.sources if item.ready)

    @property
    def ready_enrichment_count(self) -> int:
        return sum(1 for item in self.enrichment if item.ready)

    @property
    def ready_for_configured_review_cycle(self) -> bool:
        return self.ready_event_source_count > 0


def _is_path_configured(value: Any) -> bool:
    return value is not None and str(value) != ""


def _present(value: Any) -> bool:
    if isinstance(value, (list, tuple, set)):
        return bool(value)
    return bool(value)


def _flag(value: bool) -> str:
    return "on" if value else "off"


def _presence(value: Any) -> str:
    return "present" if _present(value) else "missing"


def _path_detail(value: Any) -> str:
    return "fixture=yes" if _is_path_configured(value) else "fixture=no"


def _optional_path_name(value: Any) -> str:
    if not _is_path_configured(value):
        return "none"
    return Path(value).name


def _status(
    *,
    name: str,
    category: str,
    ready: bool,
    details: tuple[str, ...],
    notes: tuple[str, ...] = (),
) -> ProviderStatus:
    return ProviderStatus(
        name=name,
        category=category,
        ready=bool(ready),
        details=details,
        notes=notes,
    )


def _event_source_statuses(cfg: Any) -> tuple[ProviderStatus, ...]:
    return (
        _status(
            name="manual_json",
            category="event_source",
            ready=_is_path_configured(cfg.EVENT_DISCOVERY_EVENTS_PATH),
            details=(_path_detail(cfg.EVENT_DISCOVERY_EVENTS_PATH),),
        ),
        _status(
            name="binance_announcements",
            category="event_source",
            ready=(
                _is_path_configured(cfg.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH)
                or (
                    cfg.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE
                    and _present(cfg.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_KEY)
                    and _present(cfg.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_SECRET)
                )
            ),
            details=(
                _path_detail(cfg.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH),
                f"live={_flag(cfg.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE)}",
                f"api_key={_presence(cfg.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_KEY)}",
                f"api_secret={_presence(cfg.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_SECRET)}",
            ),
            notes=("direct listing/perp events; cannot bypass proxy gate",),
        ),
        _status(
            name="bybit_announcements",
            category="event_source",
            ready=(
                _is_path_configured(cfg.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH)
                or cfg.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE
            ),
            details=(
                _path_detail(cfg.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH),
                f"live={_flag(cfg.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE)}",
            ),
            notes=("direct listing/perp events; cannot bypass proxy gate",),
        ),
        _status(
            name="coinmarketcal_calendar",
            category="event_source",
            ready=_is_path_configured(cfg.EVENT_DISCOVERY_COINMARKETCAL_PATH),
            details=(_path_detail(cfg.EVENT_DISCOVERY_COINMARKETCAL_PATH),),
        ),
        _status(
            name="tokenomist_unlocks",
            category="event_source",
            ready=_is_path_configured(cfg.EVENT_DISCOVERY_TOKENOMIST_PATH),
            details=(_path_detail(cfg.EVENT_DISCOVERY_TOKENOMIST_PATH),),
            notes=("direct supply events; cannot bypass proxy gate",),
        ),
        _status(
            name="cryptopanic_news",
            category="event_source",
            ready=(
                _is_path_configured(cfg.EVENT_DISCOVERY_CRYPTOPANIC_PATH)
                or (
                    cfg.EVENT_DISCOVERY_CRYPTOPANIC_LIVE
                    and _present(cfg.EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN)
                )
            ),
            details=(
                _path_detail(cfg.EVENT_DISCOVERY_CRYPTOPANIC_PATH),
                f"live={_flag(cfg.EVENT_DISCOVERY_CRYPTOPANIC_LIVE)}",
                f"api_token={_presence(cfg.EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN)}",
            ),
        ),
        _status(
            name="gdelt_news",
            category="event_source",
            ready=_is_path_configured(cfg.EVENT_DISCOVERY_GDELT_PATH) or cfg.EVENT_DISCOVERY_GDELT_LIVE,
            details=(
                _path_detail(cfg.EVENT_DISCOVERY_GDELT_PATH),
                f"live={_flag(cfg.EVENT_DISCOVERY_GDELT_LIVE)}",
            ),
        ),
        _status(
            name="project_blog_rss",
            category="event_source",
            ready=(
                _is_path_configured(cfg.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH)
                or (
                    cfg.EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE
                    and _present(cfg.EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS)
                )
            ),
            details=(
                _path_detail(cfg.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH),
                f"live={_flag(cfg.EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE)}",
                f"url_count={len(getattr(cfg, 'EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS', ()) or ())}",
                f"url_file={_optional_path_name(getattr(cfg, 'EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS_PATH', None))}",
            ),
        ),
        _status(
            name="external_ipo",
            category="event_source",
            ready=_is_path_configured(cfg.EVENT_DISCOVERY_EXTERNAL_IPO_PATH),
            details=(_path_detail(cfg.EVENT_DISCOVERY_EXTERNAL_IPO_PATH),),
        ),
        _status(
            name="sports_fixtures",
            category="event_source",
            ready=_is_path_configured(cfg.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH),
            details=(_path_detail(cfg.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH),),
        ),
        _status(
            name="prediction_market_events",
            category="event_source",
            ready=(
                _is_path_configured(cfg.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH)
                or cfg.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE
            ),
            details=(
                _path_detail(cfg.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH),
                f"live={_flag(cfg.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE)}",
                f"limit={int(getattr(cfg, 'EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIMIT', 0) or 0)}",
            ),
            notes=("external catalyst evidence; cannot bypass proxy gate",),
        ),
    )


def _event_enrichment_statuses(cfg: Any) -> tuple[ProviderStatus, ...]:
    return (
        _status(
            name="asset_aliases",
            category="enrichment",
            ready=_is_path_configured(cfg.EVENT_DISCOVERY_ALIASES_PATH),
            details=(f"path={Path(cfg.EVENT_DISCOVERY_ALIASES_PATH).name}",),
        ),
        _status(
            name="coingecko_universe",
            category="enrichment",
            ready=_is_path_configured(cfg.EVENT_DISCOVERY_UNIVERSE_PATH) or cfg.EVENT_DISCOVERY_UNIVERSE_LIVE,
            details=(
                _path_detail(cfg.EVENT_DISCOVERY_UNIVERSE_PATH),
                f"live={_flag(cfg.EVENT_DISCOVERY_UNIVERSE_LIVE)}",
            ),
        ),
        _status(
            name="coinalyze_derivatives",
            category="enrichment",
            ready=(
                _is_path_configured(cfg.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH)
                or (
                    cfg.EVENT_DISCOVERY_COINALYZE_LIVE
                    and _present(cfg.EVENT_DISCOVERY_COINALYZE_API_KEY)
                    and (
                        _present(cfg.EVENT_DISCOVERY_COINALYZE_SYMBOLS)
                        or cfg.EVENT_DISCOVERY_COINALYZE_AUTO_SYMBOLS
                    )
                )
            ),
            details=(
                _path_detail(cfg.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH),
                f"live={_flag(cfg.EVENT_DISCOVERY_COINALYZE_LIVE)}",
                f"api_key={_presence(cfg.EVENT_DISCOVERY_COINALYZE_API_KEY)}",
                f"symbols={len(getattr(cfg, 'EVENT_DISCOVERY_COINALYZE_SYMBOLS', ()) or ())}",
                f"auto_symbols={_flag(cfg.EVENT_DISCOVERY_COINALYZE_AUTO_SYMBOLS)}",
            ),
            notes=("enrichment only; cannot create events or bypass proxy gate",),
        ),
        _status(
            name="tokenomist_supply",
            category="enrichment",
            ready=_is_path_configured(cfg.EVENT_DISCOVERY_TOKENOMIST_SUPPLY_PATH),
            details=(_path_detail(cfg.EVENT_DISCOVERY_TOKENOMIST_SUPPLY_PATH),),
        ),
        _status(
            name="etherscan_supply",
            category="enrichment",
            ready=_is_path_configured(cfg.EVENT_DISCOVERY_ETHERSCAN_SUPPLY_PATH),
            details=(_path_detail(cfg.EVENT_DISCOVERY_ETHERSCAN_SUPPLY_PATH),),
        ),
        _status(
            name="arkham_supply",
            category="enrichment",
            ready=_is_path_configured(cfg.EVENT_DISCOVERY_ARKHAM_SUPPLY_PATH),
            details=(_path_detail(cfg.EVENT_DISCOVERY_ARKHAM_SUPPLY_PATH),),
        ),
        _status(
            name="dune_supply",
            category="enrichment",
            ready=_is_path_configured(cfg.EVENT_DISCOVERY_DUNE_SUPPLY_PATH),
            details=(_path_detail(cfg.EVENT_DISCOVERY_DUNE_SUPPLY_PATH),),
        ),
    )


def _provider_status_warnings(cfg: Any, sources: tuple[ProviderStatus, ...]) -> tuple[str, ...]:
    warnings: list[str] = []
    if not any(item.ready for item in sources):
        warnings.append(
            "No event sources are ready; configured refresh/review-cycle commands will not build validation rows."
        )
    if cfg.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE and (
        not _present(cfg.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_KEY)
        or not _present(cfg.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_SECRET)
    ):
        warnings.append("Binance announcements live mode is enabled but credentials are incomplete.")
    if cfg.EVENT_DISCOVERY_CRYPTOPANIC_LIVE and not _present(cfg.EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN):
        warnings.append("CryptoPanic live mode is enabled but the API token is missing.")
    if cfg.EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE and not _present(cfg.EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS):
        warnings.append("Project blog/RSS live mode is enabled but no RSS/Atom URLs are configured.")
    if cfg.EVENT_DISCOVERY_COINALYZE_LIVE and not _present(cfg.EVENT_DISCOVERY_COINALYZE_API_KEY):
        warnings.append("Coinalyze live enrichment is enabled but the API key is missing.")
    return tuple(warnings)


def _provider_status_next_steps(sources: tuple[ProviderStatus, ...]) -> tuple[str, ...]:
    next_steps = (
        "Enable at least one event source, for example public RSS feeds, Polymarket prediction events, GDELT live, CryptoPanic live, or local event fixtures.",
        "No-key option: make event-fade-public-rss-review-cycle EVENT_FADE_REVIEW_BUNDLE_EXPORT_PRICES=1",
        "Dated catalyst option: make event-fade-polymarket-review-cycle EVENT_FADE_REVIEW_BUNDLE_EXPORT_PRICES=1",
        "Then run: make event-fade-configured-review-cycle EVENT_FADE_REVIEW_BUNDLE_EXPORT_PRICES=1",
    )
    if any(item.ready for item in sources):
        next_steps = (
            "Run: make event-fade-configured-review-cycle EVENT_FADE_REVIEW_BUNDLE_EXPORT_PRICES=1",
            "Review the generated bundle sidecar/packet, then run main.py --event-fade-review-sample on the reviewed sample.",
        )
    return next_steps


def build_event_discovery_provider_status(cfg: Any) -> EventDiscoveryProviderStatus:
    """Return redacted provider readiness for the event-discovery workflow."""

    sources = _event_source_statuses(cfg)
    enrichment = _event_enrichment_statuses(cfg)

    return EventDiscoveryProviderStatus(
        mode=str(getattr(cfg, "EVENT_DISCOVERY_MODE", "research_only")),
        cache_dir=str(cfg.EVENT_DISCOVERY_CACHE_DIR),
        lookback_hours=int(cfg.EVENT_DISCOVERY_LOOKBACK_HOURS),
        horizon_days=int(cfg.EVENT_DISCOVERY_HORIZON_DAYS),
        sources=sources,
        enrichment=enrichment,
        warnings=_provider_status_warnings(cfg, sources),
        next_steps=_provider_status_next_steps(sources),
    )


def provider_status_to_dict(report: EventDiscoveryProviderStatus) -> dict[str, Any]:
    def item_to_dict(item: ProviderStatus) -> dict[str, Any]:
        return {
            "name": item.name,
            "category": item.category,
            "ready": item.ready,
            "details": list(item.details),
            "notes": list(item.notes),
        }

    return {
        "mode": report.mode,
        "cache_dir": report.cache_dir,
        "lookback_hours": report.lookback_hours,
        "horizon_days": report.horizon_days,
        "ready_event_source_count": report.ready_event_source_count,
        "ready_enrichment_count": report.ready_enrichment_count,
        "ready_for_configured_review_cycle": report.ready_for_configured_review_cycle,
        "sources": [item_to_dict(item) for item in report.sources],
        "enrichment": [item_to_dict(item) for item in report.enrichment],
        "warnings": list(report.warnings),
        "next_steps": list(report.next_steps),
    }


def format_event_discovery_provider_status(report: EventDiscoveryProviderStatus) -> str:
    configured = tuple(item for item in (*report.sources, *report.enrichment) if item.ready)
    not_configured = tuple(item for item in (*report.sources, *report.enrichment) if not item.ready)
    healthy = tuple(item.name for item in configured)
    lines = [
        "EVENT DISCOVERY PROVIDER STATUS",
        f"Mode: {report.mode}",
        f"Cache dir: {report.cache_dir}",
        f"Window: lookback {report.lookback_hours}h, horizon {report.horizon_days}d",
        "",
        "Event sources:",
    ]
    for item in report.sources:
        mark = "READY" if item.ready else "off"
        details = "; ".join(item.details)
        lines.append(f"- {mark:5} {item.name}: {details}")
        for note in item.notes:
            lines.append(f"        note: {note}")

    lines.append("")
    lines.append("Enrichment:")
    for item in report.enrichment:
        mark = "READY" if item.ready else "off"
        details = "; ".join(item.details)
        lines.append(f"- {mark:5} {item.name}: {details}")
        for note in item.notes:
            lines.append(f"        note: {note}")

    lines.extend(
        [
            "",
            "Summary:",
            f"- ready event sources: {report.ready_event_source_count}/{len(report.sources)}",
            f"- ready enrichment sources: {report.ready_enrichment_count}/{len(report.enrichment)}",
            f"- configured review cycle ready: {'yes' if report.ready_for_configured_review_cycle else 'no'}",
        ]
    )
    lines.extend([
        "",
        "Provider readiness summary:",
        "- providers_configured: " + (_join_names(item.name for item in configured) or "none"),
        "- providers_not_configured: " + (_join_names(item.name for item in not_configured) or "none"),
        "- providers_healthy: " + (_join_names(healthy) or "none"),
        "- providers_degraded_or_backoff: see provider-health report; none in static readiness snapshot",
    ])
    pack_lines = _source_pack_gap_lines(report)
    if pack_lines:
        lines.extend(["", "Source pack coverage gaps:"])
        lines.extend(pack_lines)
    if report.warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in report.warnings)
    if report.next_steps:
        lines.append("")
        lines.append("Next:")
        lines.extend(f"- {step}" for step in report.next_steps)
    return "\n".join(lines)


def _source_pack_gap_lines(report: EventDiscoveryProviderStatus) -> list[str]:
    ready_by_name = {item.name: item.ready for item in (*report.sources, *report.enrichment)}
    # Map provider status names onto the provider names used by source packs.
    provider_aliases = {
        "project_blog_rss": "project_blog_rss",
        "gdelt_news": "gdelt",
        "cryptopanic_news": "cryptopanic",
        "prediction_market_events": "polymarket",
        "binance_announcements": "binance_announcements",
        "bybit_announcements": "bybit_announcements",
        "tokenomist_unlocks": "tokenomist",
        "tokenomist_supply": "tokenomist",
        "coinalyze_derivatives": "coinalyze",
        "coingecko_universe": "coingecko",
    }
    ready_providers = {
        alias
        for status_name, alias in provider_aliases.items()
        if ready_by_name.get(status_name)
    }
    lines: list[str] = []
    for pack in event_source_packs.SOURCE_PACKS.values():
        preferred = set(pack.preferred_providers)
        missing = tuple(sorted(provider for provider in preferred if provider not in ready_providers))
        if not missing:
            continue
        absence_meaningful = any(
            provider in ready_providers
            for provider in preferred
            if provider in {"binance_announcements", "bybit_announcements", "tokenomist", "coinalyze"}
        )
        lines.append(
            f"- {pack.name}: missing={_join_names(missing)} "
            f"evidence_absence_meaningful={str(absence_meaningful).lower()} "
            f"preferred={_join_names(preferred)}"
        )
    return lines[:12]


def _join_names(values: Any) -> str:
    return ", ".join(str(item) for item in sorted(set(values)) if str(item))
