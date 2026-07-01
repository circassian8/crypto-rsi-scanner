"""Live-provider activation readiness for Event Alpha research.

This module is deliberately inspection-only. It records what would be required
to activate higher-value evidence providers, but it never performs live provider
requests, sends notifications, trades, paper trades, writes normal RSI rows, or
creates ``TRIGGERED_FADE``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import config, event_artifact_paths, event_alpha_source_coverage

READINESS_JSON = "event_live_provider_activation_readiness.json"
READINESS_MD = "event_live_provider_activation_readiness.md"


@dataclass(frozen=True)
class LiveProviderReadinessProvider:
    provider_name: str
    category: str
    priority_rank: int
    enabled_by_default: bool
    configured: bool
    env_vars_required: tuple[str, ...]
    secrets_redacted: bool
    live_call_allowed: bool
    fixture_available: bool
    preflight_status: str
    quota_or_rate_limit_policy: str
    request_ledger_path: str | None
    last_success: str | None
    last_error_safe: str | None
    source_packs_enabled: tuple[str, ...]
    opportunity_lanes_enabled: tuple[str, ...]
    artifact_outputs: tuple[str, ...]
    no_send_only: bool
    safety_notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "category": self.category,
            "priority_rank": self.priority_rank,
            "enabled_by_default": self.enabled_by_default,
            "configured": self.configured,
            "env_vars_required": list(self.env_vars_required),
            "secrets_redacted": self.secrets_redacted,
            "live_call_allowed": self.live_call_allowed,
            "fixture_available": self.fixture_available,
            "preflight_status": self.preflight_status,
            "quota_or_rate_limit_policy": self.quota_or_rate_limit_policy,
            "request_ledger_path": self.request_ledger_path,
            "last_success": self.last_success,
            "last_error_safe": self.last_error_safe,
            "source_packs_enabled": list(self.source_packs_enabled),
            "opportunity_lanes_enabled": list(self.opportunity_lanes_enabled),
            "artifact_outputs": list(self.artifact_outputs),
            "no_send_only": self.no_send_only,
            "safety_notes": list(self.safety_notes),
        }


@dataclass(frozen=True)
class LiveProviderReadinessReport:
    profile: str
    artifact_namespace: str
    generated_at: str
    smoke_mode: bool
    live_calls_allowed: bool
    research_only: bool
    providers: tuple[LiveProviderReadinessProvider, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "event_live_provider_activation_readiness_v1",
            "row_type": "event_live_provider_activation_readiness",
            "profile": self.profile,
            "artifact_namespace": self.artifact_namespace,
            "generated_at": self.generated_at,
            "smoke_mode": self.smoke_mode,
            "live_calls_allowed": self.live_calls_allowed,
            "research_only": self.research_only,
            "providers": [provider.to_dict() for provider in self.providers],
            "recommended_next_activation_order": [
                {
                    "rank": idx + 1,
                    "category": str(item.get("category") or ""),
                    "providers": list(item.get("providers") or ()),
                    "why_it_matters": str(item.get("reason") or ""),
                    "lanes_enabled": list(item.get("enabled_lanes") or ()),
                    "safety_guard": "readiness only; no live calls in smoke/tests; Telegram remains guarded",
                }
                for idx, item in enumerate(event_alpha_source_coverage.SOURCE_COVERAGE_CATEGORY_PRIORITIES)
            ],
        }


def build_readiness_report(
    *,
    profile: str,
    artifact_namespace: str,
    smoke_mode: bool = False,
    now: datetime | None = None,
) -> LiveProviderReadinessReport:
    observed = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    providers = tuple(_provider_rows(smoke_mode=smoke_mode))
    return LiveProviderReadinessReport(
        profile=str(profile or "default"),
        artifact_namespace=str(artifact_namespace or "default"),
        generated_at=observed.isoformat(),
        smoke_mode=bool(smoke_mode),
        live_calls_allowed=False,
        research_only=True,
        providers=providers,
    )


def write_readiness_artifacts(report: LiveProviderReadinessReport, out_dir: str | Path) -> tuple[Path, Path]:
    target = Path(out_dir).expanduser()
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / READINESS_JSON
    md_path = target / READINESS_MD
    json_path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(format_readiness_report(report) + "\n", encoding="utf-8")
    return json_path, md_path


def format_readiness_report(report: LiveProviderReadinessReport) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA LIVE-PROVIDER ACTIVATION READINESS (research-only)",
        "=" * 76,
        f"profile: {report.profile}",
        f"artifact_namespace: {report.artifact_namespace}",
        f"generated_at: {report.generated_at}",
        f"smoke_mode: {str(report.smoke_mode).lower()}",
        "live_calls_allowed: false",
        "note: no provider network calls, Telegram sends, trades, paper trades, RSI rows, or triggers are performed.",
        "",
        "Recommended next activation order:",
    ]
    for idx, item in enumerate(event_alpha_source_coverage.SOURCE_COVERAGE_CATEGORY_PRIORITIES, start=1):
        lines.extend([
            f"{idx}. {item.get('category')}",
            f"   providers: {_join(item.get('providers') or ())}",
            f"   lanes enabled: {_join(item.get('enabled_lanes') or ())}",
            f"   why it matters: {item.get('reason') or 'none'}",
            "   safety guard: enable explicitly, keep request ledgers/quota caps, no-send rehearsal first",
        ])
    lines.extend(["", "Provider readiness:"])
    for provider in report.providers:
        lines.extend([
            f"- {provider.provider_name} ({provider.category})",
            f"  priority_rank: {provider.priority_rank}",
            f"  configured: {str(provider.configured).lower()}",
            f"  preflight_status: {provider.preflight_status}",
            f"  env_vars_required: {_join(provider.env_vars_required)}",
            f"  fixture_available: {str(provider.fixture_available).lower()}",
            f"  live_call_allowed: {str(provider.live_call_allowed).lower()}",
            f"  quota_or_rate_limit_policy: {provider.quota_or_rate_limit_policy}",
            f"  request_ledger_path: {provider.request_ledger_path or 'none'}",
            f"  source_packs_enabled: {_join(provider.source_packs_enabled)}",
            f"  opportunity_lanes_enabled: {_join(provider.opportunity_lanes_enabled)}",
            f"  artifact_outputs: {_join(provider.artifact_outputs)}",
            f"  safety_notes: {_join(provider.safety_notes)}",
        ])
    return "\n".join(lines)


def _provider_rows(*, smoke_mode: bool) -> Iterable[LiveProviderReadinessProvider]:
    rows = (
        _row(
            "coinalyze",
            category="derivatives",
            priority_rank=1,
            env_vars=("RSI_EVENT_DISCOVERY_COINALYZE_API_KEY",),
            configured=bool(config.EVENT_DISCOVERY_COINALYZE_API_KEY),
            live_enabled=bool(config.EVENT_DISCOVERY_COINALYZE_LIVE),
            fixture_path=getattr(config, "EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH", None),
            source_packs=("perp_listing_squeeze_pack",),
            lanes=("FADE_SHORT_REVIEW", "CONFIRMED_LONG_RESEARCH"),
            quota="request ledger required; bounded symbols/pages; per-run timeout and daily budget caps",
            outputs=("event_derivatives_crowding_candidates.jsonl", "event_fade_short_review_candidates.jsonl"),
            ledger=None,
            status_if_missing="missing_config",
            smoke_mode=smoke_mode,
        ),
        _row(
            "bybit_announcements",
            category="official_exchange",
            priority_rank=2,
            env_vars=(),
            configured=bool(config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE),
            live_enabled=bool(config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE),
            fixture_path=getattr(config, "EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH", None),
            source_packs=("official_perp_listing_pack", "listing_liquidity_pack"),
            lanes=("EARLY_LONG_RESEARCH", "CONFIRMED_LONG_RESEARCH", "RISK_ONLY"),
            quota="public endpoint; per-run limit and timeout; disabled in smoke",
            outputs=("event_official_exchange_candidates.jsonl",),
            ledger=None,
            status_if_missing="disabled",
            smoke_mode=smoke_mode,
        ),
        _row(
            "binance_announcements",
            category="official_exchange",
            priority_rank=3,
            env_vars=(
                "RSI_EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_KEY",
                "RSI_EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_SECRET",
            ),
            configured=bool(
                config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE
                and config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_KEY
                and config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_SECRET
            ),
            live_enabled=bool(config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE),
            fixture_path=getattr(config, "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH", None),
            source_packs=("official_exchange_listing_pack", "official_exchange_risk_pack"),
            lanes=("EARLY_LONG_RESEARCH", "CONFIRMED_LONG_RESEARCH", "RISK_ONLY"),
            quota="signed websocket; bounded listen seconds/max messages; explicit listener command only",
            outputs=("event_official_exchange_candidates.jsonl",),
            ledger=None,
            status_if_missing="missing_config",
            smoke_mode=smoke_mode,
        ),
        _row(
            "tokenomist_messari_unlocks",
            category="structured_unlock_calendar",
            priority_rank=4,
            env_vars=("RSI_EVENT_DISCOVERY_TOKENOMIST_PATH", "MESSARI_API_KEY"),
            configured=bool(getattr(config, "EVENT_DISCOVERY_TOKENOMIST_PATH", None)),
            live_enabled=False,
            fixture_path=getattr(config, "EVENT_DISCOVERY_TOKENOMIST_PATH", None),
            source_packs=("unlock_supply_pack",),
            lanes=("RISK_ONLY", "FADE_SHORT_REVIEW"),
            quota="structured-calendar providers must stay bounded by event date window and request ledger",
            outputs=("event_scheduled_catalysts.jsonl", "event_unlock_risk_candidates.jsonl"),
            ledger=None,
            status_if_missing="missing_config",
            smoke_mode=smoke_mode,
        ),
        _row(
            "geckoterminal_defillama",
            category="dex_onchain",
            priority_rank=5,
            env_vars=(),
            configured=False,
            live_enabled=False,
            fixture_path=None,
            source_packs=("market_anomaly_pack", "protocol_fundamentals_pack"),
            lanes=("EARLY_LONG_RESEARCH", "CONFIRMED_LONG_RESEARCH", "RISK_ONLY"),
            quota="public/no-key sources still need per-run request caps, cache, and stale-data handling",
            outputs=("event_market_anomalies.jsonl",),
            ledger=None,
            status_if_missing="not_implemented",
            smoke_mode=smoke_mode,
        ),
        _row(
            "cryptopanic_rss_gdelt_context",
            category="news_context",
            priority_rank=6,
            env_vars=("RSI_EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN",),
            configured=bool(config.EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN),
            live_enabled=bool(config.EVENT_DISCOVERY_CRYPTOPANIC_LIVE),
            fixture_path=getattr(config, "EVENT_DISCOVERY_CRYPTOPANIC_PATH", None),
            source_packs=("proxy_preipo_rwa_pack", "fan_sports_pack", "security_shock_pack"),
            lanes=("UNCONFIRMED_RESEARCH", "research_review_digest"),
            quota="CryptoPanic weekly/daily/per-run ledger caps; context-only, not strict confirmation by itself",
            outputs=("event_evidence_acquisition.jsonl",),
            ledger=getattr(config, "EVENT_DISCOVERY_CRYPTOPANIC_REQUEST_LEDGER_PATH", None),
            status_if_missing="disabled",
            smoke_mode=smoke_mode,
        ),
    )
    return rows


def _row(
    provider_name: str,
    *,
    category: str,
    priority_rank: int,
    env_vars: tuple[str, ...],
    configured: bool,
    live_enabled: bool,
    fixture_path: str | Path | None,
    source_packs: tuple[str, ...],
    lanes: tuple[str, ...],
    quota: str,
    outputs: tuple[str, ...],
    ledger: str | Path | None,
    status_if_missing: str,
    smoke_mode: bool,
) -> LiveProviderReadinessProvider:
    fixture_available = bool(fixture_path and Path(fixture_path).exists())
    if configured and live_enabled and not smoke_mode:
        status = "ready"
    elif configured and smoke_mode:
        status = "quota_guarded"
    elif fixture_available and not live_enabled:
        status = "disabled"
    else:
        status = status_if_missing
    return LiveProviderReadinessProvider(
        provider_name=provider_name,
        category=category,
        priority_rank=priority_rank,
        enabled_by_default=False,
        configured=bool(configured),
        env_vars_required=env_vars,
        secrets_redacted=True,
        live_call_allowed=False,
        fixture_available=fixture_available,
        preflight_status=status,
        quota_or_rate_limit_policy=quota,
        request_ledger_path=event_artifact_paths.artifact_display_path(ledger) if ledger else None,
        last_success=None,
        last_error_safe=None,
        source_packs_enabled=source_packs,
        opportunity_lanes_enabled=lanes,
        artifact_outputs=outputs,
        no_send_only=True,
        safety_notes=(
            "research-only",
            "no live calls in smoke/tests",
            "no Telegram sends unless existing send guard is explicitly enabled",
            "no trades, paper trades, RSI rows, execution, or Event Alpha TRIGGERED_FADE",
        ),
    )


def _join(values: Iterable[Any]) -> str:
    items = [str(item) for item in values if str(item)]
    return ", ".join(items) if items else "none"
