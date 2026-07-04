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

from ... import config
from ..artifacts import paths as event_artifact_paths
from ..artifacts import schema_v1
from ..radar import source_coverage as event_alpha_source_coverage
from . import dex_onchain_readiness as event_dex_onchain_readiness

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
    provider_fixture_available: bool
    provider_fixture_path: str | None
    sidecar_fixture_available: bool
    smoke_target_available: bool
    smoke_targets: tuple[str, ...]
    fixture_artifacts: tuple[str, ...]
    fixture_last_verified_status: str | None
    preflight_status: str
    activation_phase: str
    next_safe_command: str
    no_send_rehearsal_command: str
    expected_artifacts_after_rehearsal: tuple[str, ...]
    max_requests_per_run: int | None
    weekly_or_daily_budget: str | None
    timeout_seconds: int | None
    cache_ttl_seconds: int | None
    request_ledger_required: bool
    provider_health_key: str | None
    source_coverage_pack_impacts: tuple[str, ...]
    strict_lanes_unlocked_if_healthy: tuple[str, ...]
    lanes_that_remain_blocked_without_market_confirmation: tuple[str, ...]
    quota_or_rate_limit_policy: str
    request_ledger_path: str | None
    last_success: str | None
    last_error_safe: str | None
    source_packs_enabled: tuple[str, ...]
    opportunity_lanes_enabled: tuple[str, ...]
    artifact_outputs: tuple[str, ...]
    no_send_only: bool
    safety_notes: tuple[str, ...]
    latest_preflight_status: str | None = None
    latest_rehearsal_status: str | None = None
    latest_request_ledger_path: str | None = None
    latest_provider_health_status: str | None = None
    latest_rehearsal_generated_at: str | None = None
    latest_snapshots_written: int = 0
    latest_budget_used: int = 0

    def to_dict(self) -> dict[str, Any]:
        return live_provider_readiness_provider_row(self)


def live_provider_readiness_provider_row(provider: LiveProviderReadinessProvider) -> dict[str, Any]:
    return {
        "provider_name": provider.provider_name,
        "category": provider.category,
        "priority_rank": provider.priority_rank,
        "enabled_by_default": provider.enabled_by_default,
        "configured": provider.configured,
        "env_vars_required": list(provider.env_vars_required),
        "secrets_redacted": provider.secrets_redacted,
        "live_call_allowed": provider.live_call_allowed,
        "fixture_available": provider.fixture_available,
        "provider_fixture_available": provider.provider_fixture_available,
        "provider_fixture_path": provider.provider_fixture_path,
        "sidecar_fixture_available": provider.sidecar_fixture_available,
        "smoke_target_available": provider.smoke_target_available,
        "smoke_targets": list(provider.smoke_targets),
        "fixture_artifacts": list(provider.fixture_artifacts),
        "fixture_last_verified_status": provider.fixture_last_verified_status,
        "preflight_status": provider.preflight_status,
        "activation_phase": provider.activation_phase,
        "next_safe_command": provider.next_safe_command,
        "no_send_rehearsal_command": provider.no_send_rehearsal_command,
        "expected_artifacts_after_rehearsal": list(provider.expected_artifacts_after_rehearsal),
        "max_requests_per_run": provider.max_requests_per_run,
        "weekly_or_daily_budget": provider.weekly_or_daily_budget,
        "timeout_seconds": provider.timeout_seconds,
        "cache_ttl_seconds": provider.cache_ttl_seconds,
        "request_ledger_required": provider.request_ledger_required,
        "provider_health_key": provider.provider_health_key,
        "source_coverage_pack_impacts": list(provider.source_coverage_pack_impacts),
        "strict_lanes_unlocked_if_healthy": list(provider.strict_lanes_unlocked_if_healthy),
        "lanes_that_remain_blocked_without_market_confirmation": list(
            provider.lanes_that_remain_blocked_without_market_confirmation
        ),
        "quota_or_rate_limit_policy": provider.quota_or_rate_limit_policy,
        "request_ledger_path": provider.request_ledger_path,
        "last_success": provider.last_success,
        "last_error_safe": provider.last_error_safe,
        "source_packs_enabled": list(provider.source_packs_enabled),
        "opportunity_lanes_enabled": list(provider.opportunity_lanes_enabled),
        "artifact_outputs": list(provider.artifact_outputs),
        "no_send_only": provider.no_send_only,
        "safety_notes": list(provider.safety_notes),
        "latest_preflight_status": provider.latest_preflight_status,
        "latest_rehearsal_status": provider.latest_rehearsal_status,
        "latest_request_ledger_path": provider.latest_request_ledger_path,
        "latest_provider_health_status": provider.latest_provider_health_status,
        "latest_rehearsal_generated_at": provider.latest_rehearsal_generated_at,
        "latest_snapshots_written": provider.latest_snapshots_written,
        "latest_budget_used": provider.latest_budget_used,
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
            "activation_runbook": [
                {
                    "rank": provider.priority_rank,
                    "provider": provider.provider_name,
                    "phase": provider.activation_phase,
                    "next_safe_command": provider.next_safe_command,
                    "no_send_rehearsal_command": provider.no_send_rehearsal_command,
                    "expected_artifacts_after_rehearsal": list(provider.expected_artifacts_after_rehearsal),
                    "blocked_until_env_vars": list(provider.env_vars_required)
                    if provider.activation_phase in {"blocked", "config_ready_no_live"}
                    else [],
                }
                for provider in sorted(self.providers, key=lambda item: item.priority_rank)
            ],
            "official_exchange_activation_runbook": [
                "Bybit first official exchange live rehearsal: public HTTP, no key, explicit allow flag, no-send, bounded page/limit, request ledger required.",
                "Binance public/fixture second: validate parser/artifact flow without API key or live provider calls.",
                "Binance signed listener later: signed WebSocket only after explicit API key/secret env vars and bounded listener review.",
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
    providers = tuple(_provider_rows(smoke_mode=smoke_mode, artifact_namespace=artifact_namespace))
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
    payload = schema_v1.stamp_artifact_payload(report.to_dict(), path=json_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
            f"  activation_phase: {provider.activation_phase}",
            f"  configured: {str(provider.configured).lower()}",
            f"  preflight_status: {provider.preflight_status}",
            f"  env_vars_required: {_join(provider.env_vars_required)}",
            f"  fixture_available: {str(provider.fixture_available).lower()}",
            f"  provider_fixture_available: {str(provider.provider_fixture_available).lower()}",
            f"  provider_fixture_path: {provider.provider_fixture_path or 'none'}",
            f"  sidecar_fixture_available: {str(provider.sidecar_fixture_available).lower()}",
            f"  smoke_target_available: {str(provider.smoke_target_available).lower()}",
            f"  smoke_targets: {_join(provider.smoke_targets)}",
            f"  fixture_artifacts: {_join(provider.fixture_artifacts)}",
            f"  fixture_last_verified_status: {provider.fixture_last_verified_status or 'unknown'}",
            f"  live_call_allowed: {str(provider.live_call_allowed).lower()}",
            f"  next_safe_command: {provider.next_safe_command}",
            f"  no_send_rehearsal_command: {provider.no_send_rehearsal_command}",
            f"  expected_artifacts_after_rehearsal: {_join(provider.expected_artifacts_after_rehearsal)}",
            f"  max_requests_per_run: {provider.max_requests_per_run if provider.max_requests_per_run is not None else 'n/a'}",
            f"  weekly_or_daily_budget: {provider.weekly_or_daily_budget or 'n/a'}",
            f"  timeout_seconds: {provider.timeout_seconds if provider.timeout_seconds is not None else 'n/a'}",
            f"  cache_ttl_seconds: {provider.cache_ttl_seconds if provider.cache_ttl_seconds is not None else 'n/a'}",
            f"  request_ledger_required: {str(provider.request_ledger_required).lower()}",
            f"  provider_health_key: {provider.provider_health_key or 'none'}",
            f"  source_coverage_pack_impacts: {_join(provider.source_coverage_pack_impacts)}",
            f"  strict_lanes_unlocked_if_healthy: {_join(provider.strict_lanes_unlocked_if_healthy)}",
            f"  lanes_that_remain_blocked_without_market_confirmation: {_join(provider.lanes_that_remain_blocked_without_market_confirmation)}",
            f"  quota_or_rate_limit_policy: {provider.quota_or_rate_limit_policy}",
            f"  request_ledger_path: {provider.request_ledger_path or 'none'}",
            f"  source_packs_enabled: {_join(provider.source_packs_enabled)}",
            f"  opportunity_lanes_enabled: {_join(provider.opportunity_lanes_enabled)}",
            f"  artifact_outputs: {_join(provider.artifact_outputs)}",
            f"  latest_preflight_status: {provider.latest_preflight_status or 'not_generated'}",
            f"  latest_rehearsal_status: {provider.latest_rehearsal_status or 'not_generated'}",
            f"  latest_request_ledger_path: {provider.latest_request_ledger_path or 'none'}",
            f"  latest_provider_health_status: {provider.latest_provider_health_status or 'not_observed'}",
            f"  latest_rehearsal_generated_at: {provider.latest_rehearsal_generated_at or 'none'}",
            f"  latest_snapshots_written: {provider.latest_snapshots_written}",
            f"  latest_budget_used: {provider.latest_budget_used}",
            f"  safety_notes: {_join(provider.safety_notes)}",
        ])
        if not provider.configured and (provider.sidecar_fixture_available or provider.smoke_target_available):
            lines.append("  note: Live provider not configured, but fixture sidecar coverage exists.")
    lines.extend(["", "Activation Runbook:"])
    lines.extend([
        "- Bybit first official exchange live rehearsal: public HTTP, no key, explicit allow flag, bounded pages/limit, no-send, request ledger required.",
        "- Binance public/fixture second: fixture/public parser validation, no API key required, no live call by default.",
        "- Binance signed listener later: signed WebSocket only after explicit env vars and bounded listener command review.",
    ])
    for provider in sorted(report.providers, key=lambda item: item.priority_rank):
        lines.extend([
            f"- {provider.provider_name}: {provider.activation_phase}",
            f"  next: {provider.next_safe_command}",
            f"  rehearsal: {provider.no_send_rehearsal_command}",
            f"  artifacts: {_join(provider.expected_artifacts_after_rehearsal)}",
        ])
    blocked = [provider for provider in report.providers if provider.env_vars_required and not provider.configured]
    lines.extend(["", "Blocked Until:"])
    if blocked:
        for provider in blocked:
            lines.append(f"- {provider.provider_name}: configure {_join(provider.env_vars_required)}")
    else:
        lines.append("- none")
    return "\n".join(lines)


def _provider_rows(*, smoke_mode: bool, artifact_namespace: str) -> Iterable[LiveProviderReadinessProvider]:
    coinalyze_history = _coinalyze_history(artifact_namespace)
    bybit_history = _bybit_announcements_history(artifact_namespace)
    unlock_history = _unlock_calendar_history(artifact_namespace)
    dex_onchain_history = _dex_onchain_history(artifact_namespace)
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
            outputs=(
                "event_coinalyze_preflight.json",
                "event_coinalyze_preflight.md",
                "event_derivatives_crowding_candidates.jsonl",
                "event_fade_short_review_candidates.jsonl",
            ),
            ledger=None,
            status_if_missing="missing_config",
            smoke_mode=smoke_mode,
            sidecar_fixture_available=True,
            smoke_targets=("event-alpha-coinalyze-preflight-smoke", "event-alpha-derivatives-smoke", "event-alpha-fade-review-smoke"),
            fixture_artifacts=("event_derivatives_state.jsonl", "event_derivatives_crowding_candidates.jsonl", "event_fade_short_review_candidates.jsonl"),
            next_safe_command="make event-alpha-coinalyze-preflight PROFILE=notify_llm_deep PYTHON=python3",
            no_send_rehearsal_command="make event-alpha-coinalyze-no-send-rehearsal PROFILE=notify_llm_deep PYTHON=python3",
            max_requests_per_run=25,
            weekly_or_daily_budget="daily provider cap required before live rehearsal",
            timeout_seconds=30,
            cache_ttl_seconds=900,
            provider_health_key="coinalyze",
            lanes_blocked_without_market=("CONFIRMED_LONG_RESEARCH",),
            latest_preflight_status=coinalyze_history["latest_preflight_status"],
            latest_rehearsal_status=coinalyze_history["latest_rehearsal_status"],
            latest_request_ledger_path=coinalyze_history["latest_request_ledger_path"],
            latest_provider_health_status=coinalyze_history["latest_provider_health_status"],
            latest_rehearsal_generated_at=coinalyze_history["latest_rehearsal_generated_at"],
            latest_snapshots_written=coinalyze_history["latest_snapshots_written"],
            latest_budget_used=coinalyze_history["latest_budget_used"],
            activation_phase_override=coinalyze_history["activation_phase"],
        ),
        _row(
            "bybit_announcements_public",
            category="official_exchange",
            priority_rank=2,
            env_vars=(),
            configured=True,
            live_enabled=bool(config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE),
            fixture_path=getattr(config, "EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH", None),
            source_packs=("official_exchange_listing_pack", "official_perp_listing_pack", "official_exchange_risk_pack", "listing_liquidity_pack"),
            lanes=("EARLY_LONG_RESEARCH", "CONFIRMED_LONG_RESEARCH", "RISK_ONLY"),
            quota="public endpoint; explicit allow flag/env, no-send mode, max page/limit budget, and request ledger required",
            outputs=(
                "event_bybit_announcements_preflight.json",
                "event_bybit_announcements_preflight.md",
                "event_bybit_announcements_request_ledger.jsonl",
                "event_bybit_announcements_rehearsal_report.json",
                "event_bybit_announcements_rehearsal_report.md",
                "event_exchange_announcements.jsonl",
                "event_official_exchange_events.jsonl",
                "event_official_listing_candidates.jsonl",
                "event_official_exchange_activation.json",
                "event_official_exchange_activation.md",
            ),
            ledger=bybit_history["latest_request_ledger_path"],
            status_if_missing="config_ready_no_live",
            smoke_mode=smoke_mode,
            sidecar_fixture_available=True,
            smoke_targets=("event-alpha-bybit-announcements-preflight-smoke", "event-alpha-official-exchange-smoke"),
            fixture_artifacts=("event_bybit_announcements_preflight.json", "event_official_exchange_events.jsonl", "event_official_listing_candidates.jsonl"),
            next_safe_command="make event-alpha-bybit-announcements-preflight PROFILE=notify_llm_deep PYTHON=python3",
            no_send_rehearsal_command="make event-alpha-bybit-announcements-no-send-rehearsal PROFILE=notify_llm_deep PYTHON=python3",
            max_requests_per_run=3,
            weekly_or_daily_budget="bounded public endpoint rehearsal; default no-call; ledger mandatory when live_call_allowed=true",
            timeout_seconds=int(config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_TIMEOUT or 10),
            cache_ttl_seconds=900,
            provider_health_key="bybit_announcements",
            lanes_blocked_without_market=("CONFIRMED_LONG_RESEARCH",),
            latest_preflight_status=bybit_history["latest_preflight_status"],
            latest_rehearsal_status=bybit_history["latest_rehearsal_status"],
            latest_request_ledger_path=bybit_history["latest_request_ledger_path"],
            latest_provider_health_status=bybit_history["latest_provider_health_status"],
            latest_rehearsal_generated_at=bybit_history["latest_rehearsal_generated_at"],
            latest_snapshots_written=bybit_history["latest_snapshots_written"],
            latest_budget_used=bybit_history["latest_budget_used"],
            activation_phase_override=bybit_history["activation_phase"],
        ),
        _row(
            "binance_announcements_public_or_fixture",
            category="official_exchange",
            priority_rank=3,
            env_vars=(),
            configured=bool(getattr(config, "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH", None)),
            live_enabled=False,
            fixture_path=getattr(config, "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH", None),
            source_packs=("official_exchange_listing_pack", "official_exchange_risk_pack"),
            lanes=("EARLY_LONG_RESEARCH", "CONFIRMED_LONG_RESEARCH", "RISK_ONLY"),
            quota="offline fixture/public normalization lane; no secrets required; live polling remains guarded if added",
            outputs=(
                "event_exchange_announcements.jsonl",
                "event_official_exchange_events.jsonl",
                "event_official_listing_candidates.jsonl",
                "event_official_exchange_activation.json",
                "event_official_exchange_activation.md",
            ),
            ledger=None,
            status_if_missing="fixture_ready",
            smoke_mode=smoke_mode,
            sidecar_fixture_available=True,
            smoke_targets=("event-alpha-official-exchange-smoke",),
            fixture_artifacts=("event_exchange_announcements.jsonl", "event_official_exchange_events.jsonl", "event_official_listing_candidates.jsonl"),
            next_safe_command="make event-alpha-official-exchange-smoke PYTHON=python3",
            no_send_rehearsal_command="make event-alpha-official-exchange-smoke PYTHON=python3",
            max_requests_per_run=0,
            weekly_or_daily_budget="fixture/public normalization only; no live request budget",
            timeout_seconds=None,
            cache_ttl_seconds=None,
            provider_health_key="binance_announcements",
            lanes_blocked_without_market=("CONFIRMED_LONG_RESEARCH",),
        ),
        _row(
            "binance_announcements_signed_listener",
            category="official_exchange",
            priority_rank=4,
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
            outputs=(
                "event_exchange_announcements.jsonl",
                "event_official_exchange_events.jsonl",
                "event_official_listing_candidates.jsonl",
                "event_official_exchange_activation.json",
                "event_official_exchange_activation.md",
            ),
            ledger=None,
            status_if_missing="missing_config",
            smoke_mode=smoke_mode,
            sidecar_fixture_available=True,
            smoke_targets=("event-alpha-official-exchange-smoke",),
            fixture_artifacts=("event_exchange_announcements.jsonl", "event_official_exchange_events.jsonl", "event_official_listing_candidates.jsonl"),
            next_safe_command="make event-alpha-live-provider-readiness PROFILE=notify_llm_deep",
            no_send_rehearsal_command="main.py --event-discovery-binance-listen with bounded listen window, then no-send Event Alpha rehearsal",
            max_requests_per_run=100,
            weekly_or_daily_budget="bounded listen seconds/max messages; explicit command only",
            timeout_seconds=30,
            cache_ttl_seconds=900,
            provider_health_key="binance_announcements_signed_listener",
            lanes_blocked_without_market=("CONFIRMED_LONG_RESEARCH",),
        ),
        _row(
            "tokenomist",
            category="structured_unlock_calendar",
            priority_rank=5,
            env_vars=("RSI_EVENT_ALPHA_SCHEDULED_CATALYST_TOKENOMIST_PATH", "TOKENOMIST_API_KEY"),
            configured=Path(config.EVENT_ALPHA_SCHEDULED_CATALYST_TOKENOMIST_PATH).exists(),
            live_enabled=False,
            fixture_path=getattr(config, "EVENT_ALPHA_SCHEDULED_CATALYST_TOKENOMIST_PATH", None),
            source_packs=("unlock_supply_pack",),
            lanes=("RISK_ONLY", "FADE_SHORT_REVIEW"),
            quota="fixture/parser ready by default; any future live call requires explicit allow flag, request ledger, and event-window request cap",
            outputs=("event_unlock_calendar_preflight.json", "event_unlock_calendar_preflight.md", "event_scheduled_catalysts.jsonl", "event_unlock_candidates.jsonl"),
            ledger=unlock_history["latest_request_ledger_path"],
            status_if_missing="fixture_ready",
            smoke_mode=smoke_mode,
            sidecar_fixture_available=True,
            smoke_targets=("event-alpha-tokenomist-preflight", "event-alpha-scheduled-catalyst-smoke", "event-alpha-unlock-risk-smoke"),
            fixture_artifacts=("event_unlock_calendar_preflight.json", "event_scheduled_catalysts.jsonl", "event_unlock_candidates.jsonl"),
            next_safe_command="make event-alpha-tokenomist-preflight PROFILE=notify_llm_deep PYTHON=python3",
            no_send_rehearsal_command="make event-alpha-tokenomist-preflight PYTHON=python3",
            max_requests_per_run=10,
            weekly_or_daily_budget="event-window bounded; no live call implemented by default",
            timeout_seconds=20,
            cache_ttl_seconds=3600,
            provider_health_key="tokenomist",
            lanes_blocked_without_market=("CONFIRMED_LONG_RESEARCH", "FADE_SHORT_REVIEW"),
            latest_preflight_status=unlock_history["latest_preflight_status"],
            latest_rehearsal_status=unlock_history["latest_rehearsal_status"],
            latest_request_ledger_path=unlock_history["latest_request_ledger_path"],
            latest_provider_health_status=unlock_history["latest_provider_health_status"],
            latest_rehearsal_generated_at=unlock_history["latest_rehearsal_generated_at"],
            latest_snapshots_written=unlock_history["latest_snapshots_written"],
            latest_budget_used=unlock_history["latest_budget_used"],
            activation_phase_override=unlock_history["activation_phase"],
        ),
        _row(
            "messari_unlocks",
            category="structured_unlock_calendar",
            priority_rank=6,
            env_vars=("RSI_EVENT_ALPHA_SCHEDULED_CATALYST_MESSARI_PATH", "MESSARI_API_KEY"),
            configured=Path(config.EVENT_ALPHA_SCHEDULED_CATALYST_MESSARI_PATH).exists(),
            live_enabled=False,
            fixture_path=getattr(config, "EVENT_ALPHA_SCHEDULED_CATALYST_MESSARI_PATH", None),
            source_packs=("unlock_supply_pack",),
            lanes=("RISK_ONLY", "FADE_SHORT_REVIEW"),
            quota="fixture/parser ready by default; any future live call requires explicit allow flag, request ledger, and event-window request cap",
            outputs=("event_unlock_calendar_preflight.json", "event_unlock_calendar_preflight.md", "event_scheduled_catalysts.jsonl", "event_unlock_candidates.jsonl"),
            ledger=unlock_history["latest_request_ledger_path"],
            status_if_missing="fixture_ready",
            smoke_mode=smoke_mode,
            sidecar_fixture_available=True,
            smoke_targets=("event-alpha-messari-unlocks-preflight", "event-alpha-scheduled-catalyst-smoke", "event-alpha-unlock-risk-smoke"),
            fixture_artifacts=("event_unlock_calendar_preflight.json", "event_scheduled_catalysts.jsonl", "event_unlock_candidates.jsonl"),
            next_safe_command="make event-alpha-messari-unlocks-preflight PROFILE=notify_llm_deep PYTHON=python3",
            no_send_rehearsal_command="make event-alpha-messari-unlocks-preflight PYTHON=python3",
            max_requests_per_run=10,
            weekly_or_daily_budget="event-window bounded; no live call implemented by default",
            timeout_seconds=20,
            cache_ttl_seconds=3600,
            provider_health_key="messari_unlocks",
            lanes_blocked_without_market=("CONFIRMED_LONG_RESEARCH", "FADE_SHORT_REVIEW"),
            latest_preflight_status=unlock_history["latest_preflight_status"],
            latest_rehearsal_status=unlock_history["latest_rehearsal_status"],
            latest_request_ledger_path=unlock_history["latest_request_ledger_path"],
            latest_provider_health_status=unlock_history["latest_provider_health_status"],
            latest_rehearsal_generated_at=unlock_history["latest_rehearsal_generated_at"],
            latest_snapshots_written=unlock_history["latest_snapshots_written"],
            latest_budget_used=unlock_history["latest_budget_used"],
            activation_phase_override=unlock_history["activation_phase"],
        ),
        _row(
            "coinmarketcal",
            category="structured_unlock_calendar",
            priority_rank=7,
            env_vars=("RSI_EVENT_ALPHA_SCHEDULED_CATALYST_COINMARKETCAL_PATH", "COINMARKETCAL_API_KEY"),
            configured=Path(config.EVENT_ALPHA_SCHEDULED_CATALYST_COINMARKETCAL_PATH).exists(),
            live_enabled=False,
            fixture_path=getattr(config, "EVENT_ALPHA_SCHEDULED_CATALYST_COINMARKETCAL_PATH", None),
            source_packs=("project_event_pack", "unlock_supply_pack"),
            lanes=("EARLY_LONG_RESEARCH", "RISK_ONLY"),
            quota="fixture/parser ready by default; any future live call requires explicit allow flag, request ledger, and page/limit cap",
            outputs=("event_unlock_calendar_preflight.json", "event_unlock_calendar_preflight.md", "event_scheduled_catalysts.jsonl", "event_unlock_candidates.jsonl"),
            ledger=unlock_history["latest_request_ledger_path"],
            status_if_missing="fixture_ready",
            smoke_mode=smoke_mode,
            sidecar_fixture_available=True,
            smoke_targets=("event-alpha-coinmarketcal-preflight", "event-alpha-scheduled-catalyst-smoke"),
            fixture_artifacts=("event_unlock_calendar_preflight.json", "event_scheduled_catalysts.jsonl", "event_unlock_candidates.jsonl"),
            next_safe_command="make event-alpha-coinmarketcal-preflight PROFILE=notify_llm_deep PYTHON=python3",
            no_send_rehearsal_command="make event-alpha-coinmarketcal-preflight PYTHON=python3",
            max_requests_per_run=10,
            weekly_or_daily_budget="event-window bounded; no live call implemented by default",
            timeout_seconds=20,
            cache_ttl_seconds=3600,
            provider_health_key="coinmarketcal",
            lanes_blocked_without_market=("CONFIRMED_LONG_RESEARCH", "FADE_SHORT_REVIEW"),
            latest_preflight_status=unlock_history["latest_preflight_status"],
            latest_rehearsal_status=unlock_history["latest_rehearsal_status"],
            latest_request_ledger_path=unlock_history["latest_request_ledger_path"],
            latest_provider_health_status=unlock_history["latest_provider_health_status"],
            latest_rehearsal_generated_at=unlock_history["latest_rehearsal_generated_at"],
            latest_snapshots_written=unlock_history["latest_snapshots_written"],
            latest_budget_used=unlock_history["latest_budget_used"],
            activation_phase_override=unlock_history["activation_phase"],
        ),
        _row(
            "geckoterminal",
            category="dex_onchain",
            priority_rank=8,
            env_vars=("RSI_EVENT_ALPHA_DEX_GECKOTERMINAL_PATH",),
            configured=Path(config.EVENT_ALPHA_DEX_GECKOTERMINAL_PATH).exists(),
            live_enabled=False,
            fixture_path=getattr(config, "EVENT_ALPHA_DEX_GECKOTERMINAL_PATH", None),
            source_packs=("dex_liquidity_pack", "market_anomaly_pack"),
            lanes=("UNCONFIRMED_RESEARCH", "CONFIRMED_LONG_RESEARCH", "DIAGNOSTIC"),
            quota="fixture/parser ready by default; any future live call requires explicit allow flag, request ledger, and per-run pool cap",
            outputs=(
                event_dex_onchain_readiness.READINESS_JSON,
                event_dex_onchain_readiness.READINESS_MD,
                event_dex_onchain_readiness.DEX_POOL_STATE_FILENAME,
                event_dex_onchain_readiness.DEX_POOL_ANOMALIES_FILENAME,
            ),
            ledger=dex_onchain_history["latest_request_ledger_path"],
            status_if_missing="fixture_ready",
            smoke_mode=smoke_mode,
            sidecar_fixture_available=True,
            smoke_targets=("event-alpha-dex-onchain-readiness-smoke", "event-alpha-market-anomaly-smoke"),
            fixture_artifacts=(
                event_dex_onchain_readiness.READINESS_JSON,
                event_dex_onchain_readiness.DEX_POOL_STATE_FILENAME,
                event_dex_onchain_readiness.DEX_POOL_ANOMALIES_FILENAME,
            ),
            next_safe_command="make event-alpha-dex-onchain-readiness-smoke PYTHON=python3",
            no_send_rehearsal_command="make event-alpha-dex-onchain-readiness-smoke PYTHON=python3",
            max_requests_per_run=20,
            weekly_or_daily_budget="not implemented for live DEX/on-chain providers yet; readiness remains no-call",
            timeout_seconds=20,
            cache_ttl_seconds=900,
            provider_health_key="geckoterminal",
            lanes_blocked_without_market=("CONFIRMED_LONG_RESEARCH",),
            latest_preflight_status=dex_onchain_history["latest_preflight_status"],
            latest_rehearsal_status=dex_onchain_history["latest_rehearsal_status"],
            latest_request_ledger_path=dex_onchain_history["latest_request_ledger_path"],
            latest_provider_health_status=dex_onchain_history["latest_provider_health_status"],
            latest_rehearsal_generated_at=dex_onchain_history["latest_rehearsal_generated_at"],
            latest_snapshots_written=dex_onchain_history["latest_dex_pool_state_rows"],
            latest_budget_used=0,
            activation_phase_override=dex_onchain_history["activation_phase"],
        ),
        _row(
            "coingecko_dex",
            category="dex_onchain",
            priority_rank=9,
            env_vars=("RSI_EVENT_ALPHA_DEX_COINGECKO_PATH", "COINGECKO_API_KEY"),
            configured=Path(config.EVENT_ALPHA_DEX_COINGECKO_PATH).exists(),
            live_enabled=False,
            fixture_path=getattr(config, "EVENT_ALPHA_DEX_COINGECKO_PATH", None),
            source_packs=("dex_liquidity_pack", "market_anomaly_pack"),
            lanes=("UNCONFIRMED_RESEARCH", "CONFIRMED_LONG_RESEARCH", "DIAGNOSTIC"),
            quota="fixture/parser ready by default; CoinGecko DEX live calls not implemented in this readiness path",
            outputs=(
                event_dex_onchain_readiness.READINESS_JSON,
                event_dex_onchain_readiness.READINESS_MD,
                event_dex_onchain_readiness.DEX_POOL_STATE_FILENAME,
                event_dex_onchain_readiness.DEX_POOL_ANOMALIES_FILENAME,
            ),
            ledger=dex_onchain_history["latest_request_ledger_path"],
            status_if_missing="fixture_ready",
            smoke_mode=smoke_mode,
            sidecar_fixture_available=True,
            smoke_targets=("event-alpha-dex-onchain-readiness-smoke", "event-alpha-market-anomaly-smoke"),
            fixture_artifacts=(
                event_dex_onchain_readiness.READINESS_JSON,
                event_dex_onchain_readiness.DEX_POOL_STATE_FILENAME,
                event_dex_onchain_readiness.DEX_POOL_ANOMALIES_FILENAME,
            ),
            next_safe_command="make event-alpha-dex-onchain-readiness-smoke PYTHON=python3",
            no_send_rehearsal_command="make event-alpha-dex-onchain-readiness-smoke PYTHON=python3",
            max_requests_per_run=20,
            weekly_or_daily_budget="not implemented for live DEX/on-chain providers yet; readiness remains no-call",
            timeout_seconds=20,
            cache_ttl_seconds=900,
            provider_health_key="coingecko_dex",
            lanes_blocked_without_market=("CONFIRMED_LONG_RESEARCH",),
            latest_preflight_status=dex_onchain_history["latest_preflight_status"],
            latest_rehearsal_status=dex_onchain_history["latest_rehearsal_status"],
            latest_request_ledger_path=dex_onchain_history["latest_request_ledger_path"],
            latest_provider_health_status=dex_onchain_history["latest_provider_health_status"],
            latest_rehearsal_generated_at=dex_onchain_history["latest_rehearsal_generated_at"],
            latest_snapshots_written=dex_onchain_history["latest_dex_pool_state_rows"],
            latest_budget_used=0,
            activation_phase_override=dex_onchain_history["activation_phase"],
        ),
        _row(
            "defillama_tvl_fees_revenue",
            category="protocol_fundamentals",
            priority_rank=10,
            env_vars=("RSI_EVENT_ALPHA_PROTOCOL_DEFILLAMA_PATH",),
            configured=Path(config.EVENT_ALPHA_PROTOCOL_DEFILLAMA_PATH).exists(),
            live_enabled=False,
            fixture_path=getattr(config, "EVENT_ALPHA_PROTOCOL_DEFILLAMA_PATH", None),
            source_packs=("protocol_fundamentals_pack", "strategic_investment_pack", "security_shock_pack"),
            lanes=("EARLY_LONG_RESEARCH", "CONFIRMED_LONG_RESEARCH", "RISK_ONLY"),
            quota="fixture/parser ready by default; DefiLlama live calls not implemented in this readiness path",
            outputs=(
                event_dex_onchain_readiness.READINESS_JSON,
                event_dex_onchain_readiness.READINESS_MD,
                event_dex_onchain_readiness.PROTOCOL_FUNDAMENTALS_FILENAME,
            ),
            ledger=dex_onchain_history["latest_request_ledger_path"],
            status_if_missing="fixture_ready",
            smoke_mode=smoke_mode,
            sidecar_fixture_available=True,
            smoke_targets=("event-alpha-dex-onchain-readiness-smoke", "event-alpha-integrated-radar-smoke"),
            fixture_artifacts=(
                event_dex_onchain_readiness.READINESS_JSON,
                event_dex_onchain_readiness.PROTOCOL_FUNDAMENTALS_FILENAME,
            ),
            next_safe_command="make event-alpha-dex-onchain-readiness-smoke PYTHON=python3",
            no_send_rehearsal_command="make event-alpha-dex-onchain-readiness-smoke PYTHON=python3",
            max_requests_per_run=20,
            weekly_or_daily_budget="not implemented for live protocol-fundamental providers yet; readiness remains no-call",
            timeout_seconds=20,
            cache_ttl_seconds=900,
            provider_health_key="defillama_tvl_fees_revenue",
            lanes_blocked_without_market=("CONFIRMED_LONG_RESEARCH",),
            latest_preflight_status=dex_onchain_history["latest_preflight_status"],
            latest_rehearsal_status=dex_onchain_history["latest_rehearsal_status"],
            latest_request_ledger_path=dex_onchain_history["latest_request_ledger_path"],
            latest_provider_health_status=dex_onchain_history["latest_provider_health_status"],
            latest_rehearsal_generated_at=dex_onchain_history["latest_rehearsal_generated_at"],
            latest_snapshots_written=dex_onchain_history["latest_protocol_fundamental_rows"],
            latest_budget_used=0,
            activation_phase_override=dex_onchain_history["activation_phase"],
        ),
        _row(
            "cryptopanic_rss_gdelt_context",
            category="news_context",
            priority_rank=11,
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
            sidecar_fixture_available=False,
            smoke_targets=("event-alpha-notify-llm-deep-cryptopanic-no-send-rehearsal",),
            fixture_artifacts=("cryptopanic_request_ledger.jsonl", "event_evidence_acquisition.jsonl"),
            next_safe_command="make event-alpha-cryptopanic-preflight PROFILE=notify_llm_deep PYTHON=python3",
            no_send_rehearsal_command="make event-alpha-notify-llm-deep-cryptopanic-no-send-rehearsal PYTHON=python3",
            max_requests_per_run=25,
            weekly_or_daily_budget="weekly and daily soft caps enforced by CryptoPanic request ledger",
            timeout_seconds=20,
            cache_ttl_seconds=900,
            provider_health_key="cryptopanic",
            lanes_blocked_without_market=("CONFIRMED_LONG_RESEARCH",),
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
    sidecar_fixture_available: bool = False,
    smoke_targets: tuple[str, ...] = (),
    fixture_artifacts: tuple[str, ...] = (),
    next_safe_command: str = "make event-alpha-live-provider-readiness",
    no_send_rehearsal_command: str = "run the provider-specific no-send smoke target",
    max_requests_per_run: int | None = None,
    weekly_or_daily_budget: str | None = None,
    timeout_seconds: int | None = None,
    cache_ttl_seconds: int | None = None,
    provider_health_key: str | None = None,
    lanes_blocked_without_market: tuple[str, ...] = (),
    latest_preflight_status: str | None = None,
    latest_rehearsal_status: str | None = None,
    latest_request_ledger_path: str | None = None,
    latest_provider_health_status: str | None = None,
    latest_rehearsal_generated_at: str | None = None,
    latest_snapshots_written: int = 0,
    latest_budget_used: int = 0,
    activation_phase_override: str | None = None,
) -> LiveProviderReadinessProvider:
    provider_fixture_available = bool(fixture_path and Path(fixture_path).exists())
    fixture_available = bool(provider_fixture_available or sidecar_fixture_available or smoke_targets)
    if configured and live_enabled and not smoke_mode:
        status = "ready"
    elif configured and smoke_mode:
        status = "quota_guarded"
    elif status_if_missing == "fixture_ready" and fixture_available:
        status = "fixture_ready"
    elif fixture_available and not live_enabled:
        status = "disabled"
    else:
        status = status_if_missing
    if live_enabled and configured and not smoke_mode:
        activation_phase = "ready_for_no_send_live_rehearsal"
    elif configured:
        activation_phase = "config_ready_no_live"
    elif env_vars:
        activation_phase = "blocked"
    elif sidecar_fixture_available or smoke_targets:
        activation_phase = "fixture_ready"
    elif status_if_missing == "not_implemented":
        activation_phase = "not_implemented"
    else:
        activation_phase = "blocked"
    if activation_phase_override:
        activation_phase = activation_phase_override
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
        provider_fixture_available=provider_fixture_available,
        provider_fixture_path=event_artifact_paths.artifact_display_path(fixture_path) if fixture_path else None,
        sidecar_fixture_available=bool(sidecar_fixture_available),
        smoke_target_available=bool(smoke_targets),
        smoke_targets=smoke_targets,
        fixture_artifacts=fixture_artifacts,
        fixture_last_verified_status="covered_by_make_verify_or_smoke" if smoke_targets else None,
        preflight_status=status,
        activation_phase=activation_phase,
        next_safe_command=next_safe_command,
        no_send_rehearsal_command=no_send_rehearsal_command,
        expected_artifacts_after_rehearsal=outputs,
        max_requests_per_run=max_requests_per_run,
        weekly_or_daily_budget=weekly_or_daily_budget,
        timeout_seconds=timeout_seconds,
        cache_ttl_seconds=cache_ttl_seconds,
        request_ledger_required=bool(ledger or max_requests_per_run),
        provider_health_key=provider_health_key or provider_name,
        source_coverage_pack_impacts=source_packs,
        strict_lanes_unlocked_if_healthy=lanes,
        lanes_that_remain_blocked_without_market_confirmation=lanes_blocked_without_market,
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
        latest_preflight_status=latest_preflight_status,
        latest_rehearsal_status=latest_rehearsal_status,
        latest_request_ledger_path=latest_request_ledger_path,
        latest_provider_health_status=latest_provider_health_status,
        latest_rehearsal_generated_at=latest_rehearsal_generated_at,
        latest_snapshots_written=latest_snapshots_written,
        latest_budget_used=latest_budget_used,
    )


def _coinalyze_history(artifact_namespace: str) -> dict[str, Any]:
    from . import coinalyze_preflight as event_coinalyze_preflight

    base = Path(getattr(config, "EVENT_ALPHA_ARTIFACT_BASE_DIR", "event_fade_cache")).expanduser()
    namespace_dir = base / str(artifact_namespace or "default")
    preflight = _read_json(namespace_dir / event_coinalyze_preflight.PREFLIGHT_JSON)
    rehearsal = _read_json(namespace_dir / event_coinalyze_preflight.REHEARSAL_JSON)
    ledger = namespace_dir / event_coinalyze_preflight.REQUEST_LEDGER
    status = str(rehearsal.get("status") or "not_generated")
    if status in {"missing_config"}:
        activation_phase = "missing_config"
    elif status == "live_call_blocked_by_default":
        activation_phase = "config_ready_no_live"
    elif status == "live_rehearsal_success":
        activation_phase = "live_rehearsal_success"
    elif status == "live_rehearsal_partial":
        activation_phase = "live_rehearsal_partial"
    elif status and status != "not_generated" and status.startswith("blocked"):
        activation_phase = "blocked"
    else:
        activation_phase = str(preflight.get("preflight_status") or "not_generated")
    return {
        "latest_preflight_status": str(preflight.get("preflight_status") or "not_generated"),
        "latest_rehearsal_status": activation_phase if status == "not_generated" else status,
        "latest_request_ledger_path": event_artifact_paths.artifact_display_path(ledger) if ledger.exists() else None,
        "latest_provider_health_status": str(rehearsal.get("provider_health_status") or "not_observed"),
        "latest_rehearsal_generated_at": str(rehearsal.get("generated_at") or "") or None,
        "latest_snapshots_written": int(rehearsal.get("snapshots_written") or 0),
        "latest_budget_used": int(rehearsal.get("requests_used") or 0),
        "activation_phase": activation_phase,
    }


def _bybit_announcements_history(artifact_namespace: str) -> dict[str, Any]:
    from . import bybit_announcements_preflight as event_bybit_announcements_preflight

    base = Path(getattr(config, "EVENT_ALPHA_ARTIFACT_BASE_DIR", "event_fade_cache")).expanduser()
    namespace_dir = base / str(artifact_namespace or "default")
    preflight = _read_json(namespace_dir / event_bybit_announcements_preflight.PREFLIGHT_JSON)
    rehearsal = _read_json(namespace_dir / event_bybit_announcements_preflight.REHEARSAL_JSON)
    ledger = namespace_dir / event_bybit_announcements_preflight.REQUEST_LEDGER
    status = str(rehearsal.get("status") or "not_generated")
    if status == "live_call_blocked_by_default":
        activation_phase = "config_ready_no_live"
    elif status == "live_rehearsal_success":
        activation_phase = "live_rehearsal_success"
    elif status == "live_rehearsal_no_results":
        activation_phase = "observed_no_results"
    elif status == "live_rehearsal_partial":
        activation_phase = "live_rehearsal_partial"
    elif status in {"auth_or_access_error", "rate_limited", "provider_unavailable"}:
        activation_phase = status
    elif status and status != "not_generated" and status.startswith("blocked"):
        activation_phase = "blocked"
    else:
        activation_phase = str(preflight.get("preflight_status") or "config_ready_no_live")
    return {
        "latest_preflight_status": str(preflight.get("preflight_status") or "not_generated"),
        "latest_rehearsal_status": activation_phase if status == "not_generated" else status,
        "latest_request_ledger_path": event_artifact_paths.artifact_display_path(ledger) if ledger.exists() else None,
        "latest_provider_health_status": str(rehearsal.get("provider_health_status") or "not_observed"),
        "latest_rehearsal_generated_at": str(rehearsal.get("generated_at") or "") or None,
        "latest_snapshots_written": int(rehearsal.get("official_events_written") or rehearsal.get("announcements_inspected") or 0),
        "latest_budget_used": int(rehearsal.get("requests_used") or 0),
        "activation_phase": activation_phase,
    }


def _unlock_calendar_history(artifact_namespace: str) -> dict[str, Any]:
    from . import unlock_calendar_preflight as event_unlock_calendar_preflight

    base = Path(getattr(config, "EVENT_ALPHA_ARTIFACT_BASE_DIR", "event_fade_cache")).expanduser()
    namespace_dir = base / str(artifact_namespace or "default")
    preflight = _read_json(namespace_dir / event_unlock_calendar_preflight.PREFLIGHT_JSON)
    ledger = namespace_dir / event_unlock_calendar_preflight.REQUEST_LEDGER
    status = str(preflight.get("preflight_status") or "not_generated")
    provider_rows = preflight.get("providers") or preflight.get("provider_rows") or ()
    if not isinstance(provider_rows, Iterable) or isinstance(provider_rows, (str, bytes, Mapping)):
        provider_rows = ()
    fixture_rows = 0
    for row in provider_rows:
        if not isinstance(row, Mapping):
            continue
        try:
            fixture_rows += int(row.get("scheduled_events_previewed") or row.get("fixture_rows_observed") or 0)
        except (TypeError, ValueError):
            pass
    activation_phase = "fixture_ready" if status in {"fixture_ready", "fixture_partial"} else status
    return {
        "latest_preflight_status": status,
        "latest_rehearsal_status": status,
        "latest_request_ledger_path": event_artifact_paths.artifact_display_path(ledger) if ledger.exists() else None,
        "latest_provider_health_status": "not_observed",
        "latest_rehearsal_generated_at": str(preflight.get("generated_at") or "") or None,
        "latest_snapshots_written": fixture_rows,
        "latest_budget_used": 0,
        "activation_phase": activation_phase,
    }


def _dex_onchain_history(artifact_namespace: str) -> dict[str, Any]:
    base = Path(getattr(config, "EVENT_ALPHA_ARTIFACT_BASE_DIR", "event_fade_cache")).expanduser()
    namespace_dir = base / str(artifact_namespace or "default")
    readiness = _read_json(namespace_dir / event_dex_onchain_readiness.READINESS_JSON)
    ledger = namespace_dir / event_dex_onchain_readiness.REQUEST_LEDGER
    status = str(readiness.get("readiness_status") or "not_generated")
    activation_phase = "fixture_ready" if status in {"fixture_ready", "fixture_partial"} else status
    return {
        "latest_preflight_status": status,
        "latest_rehearsal_status": status,
        "latest_request_ledger_path": event_artifact_paths.artifact_display_path(ledger) if ledger.exists() else None,
        "latest_provider_health_status": "not_observed",
        "latest_rehearsal_generated_at": str(readiness.get("generated_at") or "") or None,
        "latest_dex_pool_state_rows": int(readiness.get("dex_pool_state_rows") or 0),
        "latest_protocol_fundamental_rows": int(readiness.get("protocol_fundamental_rows") or 0),
        "activation_phase": activation_phase,
    }


def _read_json(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        return {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, Mapping) else {}


def _join(values: Iterable[Any]) -> str:
    items = [str(item) for item in values if str(item)]
    return ", ".join(items) if items else "none"
