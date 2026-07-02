"""No-call Coinalyze readiness preflight for Event Alpha research.

This module is intentionally inert: it validates local configuration and
fixture parser readiness, writes operator artifacts, and never sends
notifications, trades, paper trades, writes normal RSI rows, or creates
``TRIGGERED_FADE``.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request

from . import config, event_artifact_paths, event_derivatives_crowding, event_provider_health
from .derivatives_providers.coinalyze import CoinalyzeDerivativesProvider, resolve_future_market_symbols


PREFLIGHT_JSON = "event_coinalyze_preflight.json"
PREFLIGHT_MD = "event_coinalyze_preflight.md"
REHEARSAL_JSON = "event_coinalyze_rehearsal_report.json"
REHEARSAL_MD = "event_coinalyze_rehearsal_report.md"
REQUEST_LEDGER = "event_coinalyze_request_ledger.jsonl"
ENV_API_KEY = "RSI_EVENT_DISCOVERY_COINALYZE_API_KEY"
ENV_ALLOW_LIVE_PREFLIGHT = "RSI_EVENT_ALPHA_COINALYZE_ALLOW_LIVE_PREFLIGHT"
ENV_PREFLIGHT_BASE_SYMBOLS = "RSI_EVENT_DISCOVERY_COINALYZE_PREFLIGHT_BASE_SYMBOLS"
ENV_PREFLIGHT_MAX_REQUESTS = "RSI_EVENT_ALPHA_COINALYZE_PREFLIGHT_MAX_REQUESTS"
PROVIDER_HEALTH_KEY = "coinalyze"
DEFAULT_PREFLIGHT_NAMESPACE = "coinalyze_preflight"
DEFAULT_REHEARSAL_NAMESPACE = "coinalyze_no_send_rehearsal"
DEFAULT_PREFLIGHT_BASE_SYMBOLS = ("BTC", "ETH", "SOL")
SMALL_REQUEST_BUDGET_LIMIT = 10
SUPPORTED_METRICS = (
    "open_interest",
    "funding_rate",
    "predicted_funding",
    "liquidations",
    "long_short_ratio",
    "basis",
    "perp_volume",
)
LANES_ENABLED = (
    "FADE_SHORT_REVIEW",
    "CONFIRMED_LONG_RESEARCH crowding warnings",
    "RISK_ONLY liquidity/crowding risk",
)
SOURCE_PACKS = (
    "perp_listing_squeeze_pack",
    "market_anomaly_pack",
    "proxy_preipo_rwa_pack",
)
FIXTURE_SYMBOLS = ("BTC", "ETH", "SOL", "TESTPERP", "TESTFADE")
_LIVE_ENDPOINTS_PER_BATCH = (
    "open-interest",
    "funding-rate",
    "open-interest-history",
    "liquidation-history",
    "long-short-ratio-history",
    "ohlcv-history",
)
_TRUTHY = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class CoinalyzeRehearsalReport:
    provider: str
    status: str
    configured: bool
    allow_live_preflight: bool
    live_call_allowed: bool
    no_send: bool
    research_only: bool
    generated_at: str
    request_ledger_path: str
    preflight_json_path: str
    preflight_report_path: str
    rehearsal_json_path: str
    rehearsal_report_path: str
    derivatives_state_path: str
    derivatives_candidates_path: str
    fade_review_candidates_path: str
    max_requests_per_run: int
    requests_used: int
    symbols_requested: tuple[str, ...]
    symbols_resolved: tuple[str, ...]
    snapshots_written: int
    crowding_candidates_written: int
    fade_review_candidates_written: int
    provider_health_status: str
    error_class: str | None = None
    error_message_safe: str | None = None
    warnings: tuple[str, ...] = ()
    strict_alerts_created: int = 0
    telegram_sends: int = 0
    trades_created: int = 0
    paper_trades_created: int = 0
    normal_rsi_signal_rows_written: int = 0
    triggered_fade_created: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "event_coinalyze_rehearsal_v1",
            "row_type": "event_coinalyze_rehearsal_report",
            "provider": self.provider,
            "status": self.status,
            "configured": self.configured,
            "allow_live_preflight": self.allow_live_preflight,
            "live_call_allowed": self.live_call_allowed,
            "no_send": self.no_send,
            "research_only": self.research_only,
            "generated_at": self.generated_at,
            "request_ledger_path": self.request_ledger_path,
            "preflight_json_path": self.preflight_json_path,
            "preflight_report_path": self.preflight_report_path,
            "rehearsal_json_path": self.rehearsal_json_path,
            "rehearsal_report_path": self.rehearsal_report_path,
            "derivatives_state_path": self.derivatives_state_path,
            "derivatives_candidates_path": self.derivatives_candidates_path,
            "fade_review_candidates_path": self.fade_review_candidates_path,
            "max_requests_per_run": self.max_requests_per_run,
            "requests_used": self.requests_used,
            "symbols_requested": list(self.symbols_requested),
            "symbols_resolved": list(self.symbols_resolved),
            "snapshots_written": self.snapshots_written,
            "crowding_candidates_written": self.crowding_candidates_written,
            "fade_review_candidates_written": self.fade_review_candidates_written,
            "provider_health_status": self.provider_health_status,
            "error_class": self.error_class,
            "error_message_safe": self.error_message_safe,
            "warnings": list(self.warnings),
            "strict_alerts_created": self.strict_alerts_created,
            "telegram_sends": self.telegram_sends,
            "trades_created": self.trades_created,
            "paper_trades_created": self.paper_trades_created,
            "normal_rsi_signal_rows_written": self.normal_rsi_signal_rows_written,
            "triggered_fade_created": self.triggered_fade_created,
        }


@dataclass(frozen=True)
class CoinalyzePreflightReport:
    provider: str
    category: str
    configured: bool
    env_vars_required: tuple[str, ...]
    live_call_allowed: bool
    smoke_mode: bool
    preflight_status: str
    request_budget: str
    max_requests_per_run: int
    timeout_seconds: float
    cache_ttl_seconds: int
    request_ledger_path: str
    provider_health_key: str
    fixture_parser_status: str
    fixture_symbol_mapping_status: str
    supported_metrics: tuple[str, ...]
    lanes_enabled_if_healthy: tuple[str, ...]
    source_packs_enabled: tuple[str, ...]
    safety_notes: tuple[str, ...]
    generated_at: str
    fixture_path: str | None = None
    fixture_symbols_observed: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "event_coinalyze_preflight_v1",
            "row_type": "event_coinalyze_preflight",
            "provider": self.provider,
            "category": self.category,
            "configured": self.configured,
            "env_vars_required": list(self.env_vars_required),
            "live_call_allowed": self.live_call_allowed,
            "smoke_mode": self.smoke_mode,
            "preflight_status": self.preflight_status,
            "request_budget": self.request_budget,
            "max_requests_per_run": self.max_requests_per_run,
            "timeout_seconds": self.timeout_seconds,
            "cache_ttl_seconds": self.cache_ttl_seconds,
            "request_ledger_path": self.request_ledger_path,
            "provider_health_key": self.provider_health_key,
            "fixture_parser_status": self.fixture_parser_status,
            "fixture_symbol_mapping_status": self.fixture_symbol_mapping_status,
            "supported_metrics": list(self.supported_metrics),
            "lanes_enabled_if_healthy": list(self.lanes_enabled_if_healthy),
            "source_packs_enabled": list(self.source_packs_enabled),
            "safety_notes": list(self.safety_notes),
            "generated_at": self.generated_at,
            "fixture_path": self.fixture_path,
            "fixture_symbols_observed": list(self.fixture_symbols_observed),
            "warnings": list(self.warnings),
        }


def build_preflight_report(
    *,
    namespace_dir: str | Path,
    smoke_mode: bool = False,
    allow_live_preflight: bool = False,
    now: datetime | None = None,
) -> CoinalyzePreflightReport:
    base = Path(namespace_dir).expanduser()
    configured = bool(_api_key())
    allow_live = effective_allow_live_preflight(allow_live_preflight)
    live_allowed = bool(allow_live and configured and not smoke_mode)
    fixture_path = _fixture_path()
    fixture_parser_status, fixture_symbols, parser_warnings = _fixture_parser_status(fixture_path)
    symbol_status = _fixture_symbol_mapping_status(fixture_symbols)
    requested_symbols, explicit_symbols = _requested_live_symbols()
    max_requests = _max_requests_per_run(explicit_symbols=explicit_symbols)
    if smoke_mode:
        status = "fixture_ready" if fixture_parser_status == "pass" else "fixture_parser_failed"
    elif not configured:
        status = "missing_config"
    elif not allow_live:
        status = "config_ready_no_live"
    else:
        status = "ready_for_no_send_rehearsal"
    return CoinalyzePreflightReport(
        provider="coinalyze",
        category="derivatives_oi_funding",
        configured=configured,
        env_vars_required=(ENV_API_KEY,),
        live_call_allowed=live_allowed,
        smoke_mode=bool(smoke_mode),
        preflight_status=status,
        request_budget="bounded no-send research rehearsal only; no broad live fetching by default",
        max_requests_per_run=max_requests if live_allowed else 0,
        timeout_seconds=float(config.EVENT_DISCOVERY_COINALYZE_TIMEOUT or 30.0),
        cache_ttl_seconds=900,
        request_ledger_path=event_artifact_paths.artifact_display_path(base / REQUEST_LEDGER),
        provider_health_key=PROVIDER_HEALTH_KEY,
        fixture_parser_status=fixture_parser_status,
        fixture_symbol_mapping_status=symbol_status,
        supported_metrics=SUPPORTED_METRICS,
        lanes_enabled_if_healthy=LANES_ENABLED,
        source_packs_enabled=SOURCE_PACKS,
        safety_notes=(
            "no live calls unless --event-alpha-coinalyze-allow-live-preflight is explicit",
            "no Telegram sends, trades, paper trades, normal RSI rows, or Event Alpha TRIGGERED_FADE",
            "API key values are never printed or written to artifacts",
        ),
        generated_at=(now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(),
        fixture_path=event_artifact_paths.artifact_display_path(fixture_path) if fixture_path else None,
        fixture_symbols_observed=tuple(sorted(fixture_symbols)),
        warnings=tuple((*parser_warnings, *(_symbol_warnings(requested_symbols) if live_allowed else ()))),
    )


def write_preflight_artifacts(report: CoinalyzePreflightReport, namespace_dir: str | Path) -> tuple[Path, Path]:
    base = Path(namespace_dir).expanduser()
    base.mkdir(parents=True, exist_ok=True)
    json_path = base / PREFLIGHT_JSON
    md_path = base / PREFLIGHT_MD
    json_path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(format_preflight_report(report) + "\n", encoding="utf-8")
    return json_path, md_path


def write_rehearsal_report(report: CoinalyzePreflightReport, namespace_dir: str | Path) -> Path:
    base = Path(namespace_dir).expanduser()
    base.mkdir(parents=True, exist_ok=True)
    path = base / REHEARSAL_MD
    if not report.configured:
        status = "missing_config"
        next_step = f"configure {ENV_API_KEY}, then rerun preflight"
    elif not report.live_call_allowed:
        status = "live_call_blocked_by_default"
        next_step = "rerun only with explicit --event-alpha-coinalyze-allow-live-preflight after reviewing quota and doctor output"
    else:
        status = "ready_for_future_bounded_no_send_rehearsal"
        next_step = "future implementation may run one or two metadata requests with request ledger enforcement"
    lines = [
        "# Coinalyze No-Send Rehearsal Stub",
        "",
        f"status: {status}",
        f"provider: {report.provider}",
        f"configured: {str(report.configured).lower()}",
        f"live_call_allowed: {str(report.live_call_allowed).lower()}",
        f"request_ledger_path: {report.request_ledger_path}",
        f"next_step: {next_step}",
        "",
        "Research-only. No live Telegram sends, trades, paper trades, normal RSI rows, or Event Alpha TRIGGERED_FADE.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run_no_send_rehearsal(
    *,
    namespace_dir: str | Path,
    provider_health_path: str | Path,
    profile: str | None = None,
    artifact_namespace: str | None = None,
    allow_live_preflight: bool = False,
    no_send_rehearsal: bool = True,
    opener: Callable[[Request, float], Any] | None = None,
    now: datetime | None = None,
    clock: Callable[[], float] | None = None,
) -> tuple[CoinalyzePreflightReport, CoinalyzeRehearsalReport, tuple[Path, Path, Path, Path]]:
    """Run a guarded Coinalyze no-send rehearsal.

    The default path never calls Coinalyze. Live calls require a configured key,
    an explicit allow flag or env var, this no-send command path, a writable
    request ledger, and a small request budget.
    """

    base = Path(namespace_dir).expanduser()
    base.mkdir(parents=True, exist_ok=True)
    observed = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    allow_live = effective_allow_live_preflight(allow_live_preflight)
    configured = bool(_api_key())
    requested_symbols, explicit_symbols = _requested_live_symbols()
    requested_budget = _required_request_budget(requested_symbols, explicit_symbols=explicit_symbols)
    max_requests = _max_requests_per_run(explicit_symbols=explicit_symbols)
    preflight = build_preflight_report(
        namespace_dir=base,
        smoke_mode=False,
        allow_live_preflight=allow_live,
        now=observed,
    )
    preflight_json, preflight_md = write_preflight_artifacts(preflight, base)

    ledger_path = base / REQUEST_LEDGER
    rehearsal_json = base / REHEARSAL_JSON
    rehearsal_md = base / REHEARSAL_MD
    derivatives_state_path = base / event_derivatives_crowding.DERIVATIVES_STATE_FILENAME
    derivatives_candidates_path = base / event_derivatives_crowding.DERIVATIVES_CROWDING_CANDIDATES_FILENAME
    fade_review_path = base / event_derivatives_crowding.FADE_SHORT_REVIEW_CANDIDATES_FILENAME
    warnings = list(_symbol_warnings(requested_symbols))
    status = "provider_unavailable"
    error_class: str | None = None
    error_message_safe: str | None = None
    snapshots_written = 0
    crowding_written = 0
    fade_written = 0
    provider_health_status = "not_observed"

    if not configured:
        status = "missing_config"
    elif not allow_live:
        status = "live_call_blocked_by_default"
    elif not no_send_rehearsal:
        status = "live_call_blocked_no_send_missing"
    elif max_requests > SMALL_REQUEST_BUDGET_LIMIT or requested_budget > max_requests:
        status = "blocked_request_budget"
        warnings.append(f"request_budget_required={requested_budget} max_requests_per_run={max_requests}")
    elif not _ledger_path_writable(ledger_path):
        status = "provider_unavailable"
        error_class = "request_ledger_unwritable"
        error_message_safe = "request ledger path is not writable"
    else:
        ledger = _LedgeredCoinalyzeOpener(
            ledger_path=ledger_path,
            api_key=_api_key(),
            max_requests=max_requests,
            opener=opener,
            now=observed,
        )
        try:
            provider = CoinalyzeDerivativesProvider(
                None,
                live_enabled=True,
                api_key=_api_key(),
                symbols=requested_symbols if explicit_symbols else (),
                base_symbols=requested_symbols if not explicit_symbols else (),
                auto_symbols=not explicit_symbols,
                base_url=config.EVENT_DISCOVERY_COINALYZE_BASE_URL,
                timeout=float(config.EVENT_DISCOVERY_COINALYZE_TIMEOUT or 10.0),
                history_interval=config.EVENT_DISCOVERY_COINALYZE_HISTORY_INTERVAL,
                lookback_hours=int(config.EVENT_DISCOVERY_COINALYZE_LOOKBACK_HOURS or 24),
                convert_to_usd=bool(config.EVENT_DISCOVERY_COINALYZE_CONVERT_TO_USD),
                opener=ledger,
                clock=clock,
                required=False,
            )
            snapshots = provider.fetch_snapshots()
        except Exception as exc:  # noqa: BLE001 - rehearsal must fail safely
            snapshots = {}
            error_class = type(exc).__name__
            error_message_safe = _safe_error_message(exc, _api_key())
        if provider_warnings := tuple(getattr(provider, "last_warnings", ()) or ()):
            warnings.extend(provider_warnings)
        ledger_rows = _read_jsonl(ledger_path)
        status, error_class, error_message_safe = _rehearsal_status_from_ledger(
            ledger_rows,
            snapshots=snapshots,
            fallback_error_class=error_class,
            fallback_error_message=error_message_safe,
        )
        state_rows = _derivatives_state_rows(
            snapshots.values(),
            observed_at=observed,
            profile=profile,
            artifact_namespace=artifact_namespace,
        )
        if state_rows:
            _write_jsonl(derivatives_state_path, state_rows)
            _write_jsonl(derivatives_candidates_path, [])
            _write_jsonl(fade_review_path, [])
        snapshots_written = len(state_rows)
        crowding_written = 0
        fade_written = 0
        provider_health_status = _record_provider_health(
            status=status,
            provider_health_path=provider_health_path,
            now=observed,
            run_id=f"coinalyze-rehearsal-{int(observed.timestamp())}",
            error_class=error_class,
            error_message=error_message_safe,
        )

    requests_used = len(_read_jsonl(ledger_path))
    report = CoinalyzeRehearsalReport(
        provider="coinalyze",
        status=status,
        configured=configured,
        allow_live_preflight=allow_live,
        live_call_allowed=bool(configured and allow_live and no_send_rehearsal and status not in {"blocked_request_budget", "provider_unavailable"} and requests_used > 0),
        no_send=bool(no_send_rehearsal),
        research_only=True,
        generated_at=observed.isoformat(),
        request_ledger_path=event_artifact_paths.artifact_display_path(ledger_path),
        preflight_json_path=event_artifact_paths.artifact_display_path(preflight_json),
        preflight_report_path=event_artifact_paths.artifact_display_path(preflight_md),
        rehearsal_json_path=event_artifact_paths.artifact_display_path(rehearsal_json),
        rehearsal_report_path=event_artifact_paths.artifact_display_path(rehearsal_md),
        derivatives_state_path=event_artifact_paths.artifact_display_path(derivatives_state_path),
        derivatives_candidates_path=event_artifact_paths.artifact_display_path(derivatives_candidates_path),
        fade_review_candidates_path=event_artifact_paths.artifact_display_path(fade_review_path),
        max_requests_per_run=max_requests,
        requests_used=requests_used,
        symbols_requested=requested_symbols,
        symbols_resolved=_symbols_from_state_file(derivatives_state_path),
        snapshots_written=snapshots_written,
        crowding_candidates_written=crowding_written,
        fade_review_candidates_written=fade_written,
        provider_health_status=provider_health_status,
        error_class=error_class,
        error_message_safe=error_message_safe,
        warnings=tuple(dict.fromkeys(warnings)),
    )
    rehearsal_json.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rehearsal_md.write_text(format_rehearsal_report(report) + "\n", encoding="utf-8")
    return preflight, report, (preflight_json, preflight_md, rehearsal_json, rehearsal_md)


def format_preflight_report(report: CoinalyzePreflightReport) -> str:
    lines = [
        "=" * 76,
        "COINALYZE DERIVATIVES PREFLIGHT (research-only, no-call by default)",
        "=" * 76,
        f"provider: {report.provider}",
        f"category: {report.category}",
        f"generated_at: {report.generated_at}",
        f"configured: {str(report.configured).lower()}",
        f"preflight_status: {report.preflight_status}",
        f"smoke_mode: {str(report.smoke_mode).lower()}",
        f"live_call_allowed: {str(report.live_call_allowed).lower()}",
        f"env_vars_required: {', '.join(report.env_vars_required)}",
        f"provider_health_key: {report.provider_health_key}",
        f"request_ledger_path: {report.request_ledger_path}",
        f"request_budget: {report.request_budget}",
        f"max_requests_per_run: {report.max_requests_per_run}",
        f"timeout_seconds: {report.timeout_seconds:g}",
        f"cache_ttl_seconds: {report.cache_ttl_seconds}",
        f"fixture_parser_status: {report.fixture_parser_status}",
        f"fixture_symbol_mapping_status: {report.fixture_symbol_mapping_status}",
        f"fixture_symbols_observed: {', '.join(report.fixture_symbols_observed) or 'none'}",
        f"supported_metrics: {', '.join(report.supported_metrics)}",
        f"lanes_enabled_if_healthy: {', '.join(report.lanes_enabled_if_healthy)}",
        f"source_packs_enabled: {', '.join(report.source_packs_enabled)}",
        "",
        "Safety notes:",
    ]
    lines.extend(f"- {item}" for item in report.safety_notes)
    if report.warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {item}" for item in report.warnings)
    lines.append("")
    lines.append("No provider network calls were performed by this preflight.")
    return "\n".join(lines)


def format_rehearsal_report(report: CoinalyzeRehearsalReport) -> str:
    lines = [
        "# Coinalyze Bounded No-Send Rehearsal",
        "",
        "Research-only. Not a trade signal. No Telegram sends, trades, paper trades, normal RSI rows, or Event Alpha TRIGGERED_FADE.",
        f"status: {report.status}",
        f"provider: {report.provider}",
        f"configured: {str(report.configured).lower()}",
        f"allow_live_preflight: {str(report.allow_live_preflight).lower()}",
        f"live_call_allowed: {str(report.live_call_allowed).lower()}",
        f"no_send: {str(report.no_send).lower()}",
        f"research_only: {str(report.research_only).lower()}",
        f"requests_used: {report.requests_used}",
        f"max_requests_per_run: {report.max_requests_per_run}",
        f"symbols_requested: {', '.join(report.symbols_requested) or 'none'}",
        f"symbols_resolved: {', '.join(report.symbols_resolved) or 'none'}",
        f"snapshots_written: {report.snapshots_written}",
        f"crowding_candidates_written: {report.crowding_candidates_written}",
        f"fade_review_candidates_written: {report.fade_review_candidates_written}",
        f"provider_health_status: {report.provider_health_status}",
        f"request_ledger_path: {report.request_ledger_path}",
        f"derivatives_state_path: {report.derivatives_state_path}",
        f"derivatives_crowding_candidates_path: {report.derivatives_candidates_path}",
        f"fade_review_candidates_path: {report.fade_review_candidates_path}",
        f"strict_alerts_created: {report.strict_alerts_created}",
        f"telegram_sends: {report.telegram_sends}",
        f"trades_created: {report.trades_created}",
        f"paper_trades_created: {report.paper_trades_created}",
        f"normal_rsi_signal_rows_written: {report.normal_rsi_signal_rows_written}",
        f"triggered_fade_created: {report.triggered_fade_created}",
    ]
    if report.error_class:
        lines.append(f"error_class: {report.error_class}")
    if report.error_message_safe:
        lines.append(f"error_message_safe: {report.error_message_safe}")
    if report.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in report.warnings)
    if report.status == "missing_config":
        lines.append(f"next_step: configure {ENV_API_KEY}, then rerun without live calls first")
    elif report.status == "live_call_blocked_by_default":
        lines.append(f"next_step: rerun only with --event-alpha-coinalyze-allow-live-preflight or {ENV_ALLOW_LIVE_PREFLIGHT}=1 after review")
    elif report.status == "blocked_request_budget":
        lines.append(f"next_step: keep {ENV_PREFLIGHT_MAX_REQUESTS} small and at least the required endpoint count for this symbol mode")
    else:
        lines.append("next_step: regenerate source coverage/daily brief and run artifact doctor before any further activation.")
    return "\n".join(lines)


def effective_allow_live_preflight(value: bool = False) -> bool:
    return bool(value or str(os.getenv(ENV_ALLOW_LIVE_PREFLIGHT, "")).strip().casefold() in _TRUTHY)


def _api_key() -> str:
    return str(os.getenv(ENV_API_KEY, "").strip() or config.EVENT_DISCOVERY_COINALYZE_API_KEY or "").strip()


def _requested_live_symbols() -> tuple[tuple[str, ...], bool]:
    explicit = tuple(_env_csv("RSI_EVENT_DISCOVERY_COINALYZE_SYMBOLS") or config.EVENT_DISCOVERY_COINALYZE_SYMBOLS or ())
    if explicit:
        return tuple(dict.fromkeys(symbol.upper() for symbol in explicit if symbol.strip()))[:3], True
    bases = tuple(_env_csv(ENV_PREFLIGHT_BASE_SYMBOLS) or DEFAULT_PREFLIGHT_BASE_SYMBOLS)
    return tuple(dict.fromkeys(symbol.upper() for symbol in bases if symbol.strip()))[:3], False


def _required_request_budget(symbols: Iterable[str], *, explicit_symbols: bool) -> int:
    count = len(tuple(symbols))
    if count <= 0:
        return 0
    batches = 1 if count <= 20 else ((count + 19) // 20)
    return batches * len(_LIVE_ENDPOINTS_PER_BATCH) + (0 if explicit_symbols else 1)


def _max_requests_per_run(*, explicit_symbols: bool) -> int:
    raw = os.getenv(ENV_PREFLIGHT_MAX_REQUESTS, "").strip()
    if raw:
        try:
            return max(0, int(raw))
        except ValueError:
            return 0
    return 6 if explicit_symbols else 7


def _symbol_warnings(symbols: Iterable[str]) -> tuple[str, ...]:
    values = tuple(symbols)
    warnings: list[str] = []
    if not values:
        warnings.append("coinalyze_preflight_symbols_empty")
    if len(values) >= 3:
        raw_symbols = _env_csv("RSI_EVENT_DISCOVERY_COINALYZE_SYMBOLS") or config.EVENT_DISCOVERY_COINALYZE_SYMBOLS or ()
        raw_bases = _env_csv(ENV_PREFLIGHT_BASE_SYMBOLS) or DEFAULT_PREFLIGHT_BASE_SYMBOLS
        if len(tuple(raw_symbols or raw_bases)) > 3:
            warnings.append("coinalyze_preflight_symbols_truncated_to_3")
    return tuple(warnings)


def _env_csv(name: str) -> tuple[str, ...]:
    raw = os.getenv(name, "")
    return tuple(item.strip() for item in raw.split(",") if item.strip())


def _ledger_path_writable(path: Path) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8"):
            pass
        return True
    except OSError:
        return False


def _derivatives_state_rows(
    snapshots: Iterable[Mapping[str, Any]],
    *,
    observed_at: datetime,
    profile: str | None,
    artifact_namespace: str | None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for snapshot in snapshots:
        if not isinstance(snapshot, Mapping):
            continue
        symbol = str(snapshot.get("symbol") or snapshot.get("base_symbol") or "").upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        row = dict(snapshot)
        row.setdefault("provider", "coinalyze")
        rows.append(
            event_derivatives_crowding.normalize_derivatives_state(
                row,
                observed_at=observed_at,
                profile=profile,
                artifact_namespace=artifact_namespace,
                run_mode="no_send_rehearsal",
                run_id=f"coinalyze-rehearsal-{int(observed_at.timestamp())}",
            )
        )
    return rows


def _symbols_from_state_file(path: Path) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            str(row.get("symbol") or "").upper()
            for row in _read_jsonl(path)
            if str(row.get("symbol") or "").strip()
        )
    )


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    materialized = [dict(row) for row in rows if isinstance(row, Mapping)]
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in materialized), encoding="utf-8")


def _read_jsonl(path: Path) -> tuple[dict[str, Any], ...]:
    if not path.exists():
        return ()
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, Mapping):
            rows.append(dict(parsed))
    return tuple(rows)


def _rehearsal_status_from_ledger(
    ledger_rows: Iterable[Mapping[str, Any]],
    *,
    snapshots: Mapping[str, Any],
    fallback_error_class: str | None,
    fallback_error_message: str | None,
) -> tuple[str, str | None, str | None]:
    rows = [dict(row) for row in ledger_rows if isinstance(row, Mapping)]
    if not rows:
        return "provider_unavailable", fallback_error_class or "no_request_rows", fallback_error_message
    status_codes = {int(row.get("status_code") or 0) for row in rows if row.get("status_code") not in (None, "")}
    errors = [row for row in rows if not bool(row.get("success"))]
    first_error = errors[0] if errors else {}
    if 401 in status_codes or 403 in status_codes:
        return "auth_or_access_error", str(first_error.get("error_class") or "HTTPError"), str(first_error.get("error_message_safe") or "")
    if 429 in status_codes:
        return "rate_limited", str(first_error.get("error_class") or "HTTPError"), str(first_error.get("error_message_safe") or "")
    if any(str(row.get("error_class") or "") == "RequestBudgetExceeded" for row in errors):
        return "blocked_request_budget", "RequestBudgetExceeded", str(first_error.get("error_message_safe") or "")
    if errors and not snapshots:
        return "provider_unavailable", str(first_error.get("error_class") or fallback_error_class or "provider_error"), str(first_error.get("error_message_safe") or fallback_error_message or "")
    if snapshots and errors:
        return "live_rehearsal_partial", str(first_error.get("error_class") or "partial_failure"), str(first_error.get("error_message_safe") or "")
    if snapshots:
        return "live_rehearsal_success", None, None
    return "provider_unavailable", fallback_error_class or "empty_snapshots", fallback_error_message


def _record_provider_health(
    *,
    status: str,
    provider_health_path: str | Path,
    now: datetime,
    run_id: str,
    error_class: str | None,
    error_message: str | None,
) -> str:
    cfg = event_provider_health.EventProviderHealthConfig(path=Path(provider_health_path), max_consecutive_failures=1)
    if status == "live_rehearsal_success":
        row = event_provider_health.record_provider_success(
            PROVIDER_HEALTH_KEY,
            cfg=cfg,
            run_id=run_id,
            now=now,
            provider_service="coinalyze",
            provider_role="derivatives_no_send_rehearsal",
        )
        row["provider_coverage_status"] = "observed_healthy"
        rows = event_provider_health.load_provider_health(cfg.path)
        rows[str(row.get("provider_key") or PROVIDER_HEALTH_KEY)] = row
        event_provider_health.write_provider_health(cfg.path, rows)
        return "observed_healthy"
    if status == "live_rehearsal_partial":
        row = event_provider_health.record_provider_success(
            PROVIDER_HEALTH_KEY,
            cfg=cfg,
            run_id=run_id,
            now=now,
            provider_service="coinalyze",
            provider_role="derivatives_no_send_rehearsal",
        )
        row["provider_coverage_status"] = "observed_partial_success"
        rows = event_provider_health.load_provider_health(cfg.path)
        rows[str(row.get("provider_key") or PROVIDER_HEALTH_KEY)] = row
        event_provider_health.write_provider_health(cfg.path, rows)
        return "observed_partial_success"
    if status in {"auth_or_access_error", "rate_limited", "provider_unavailable"}:
        row = event_provider_health.record_provider_failure(
            PROVIDER_HEALTH_KEY,
            error_class or error_message or status,
            cfg=cfg,
            run_id=run_id,
            now=now,
            provider_service="coinalyze",
            provider_role="derivatives_no_send_rehearsal",
        )
        mapped = "auth_or_access_error" if status == "auth_or_access_error" else "rate_limited" if status == "rate_limited" else "provider_unavailable"
        row["provider_coverage_status"] = mapped
        rows = event_provider_health.load_provider_health(cfg.path)
        rows[str(row.get("provider_key") or PROVIDER_HEALTH_KEY)] = row
        event_provider_health.write_provider_health(cfg.path, rows)
        return mapped
    return "not_observed"


class _LedgeredCoinalyzeOpener:
    def __init__(
        self,
        *,
        ledger_path: Path,
        api_key: str,
        max_requests: int,
        opener: Callable[[Request, float], Any] | None,
        now: datetime,
    ) -> None:
        self.ledger_path = ledger_path
        self.api_key = api_key
        self.max_requests = max_requests
        self.opener = opener
        self.started_now = now
        self.used = 0

    def __call__(self, request: Request, timeout: float) -> Any:
        before = self.max_requests - self.used
        if before <= 0:
            exc = RequestBudgetExceeded("coinalyze request budget exceeded")
            self._append_row(request, started_at=datetime.now(timezone.utc), finished_at=datetime.now(timezone.utc), before=before, after=before, exc=exc)
            raise exc
        self.used += 1
        started = datetime.now(timezone.utc)
        try:
            response = (self.opener or _default_urlopen)(request, timeout)
        except Exception as exc:  # noqa: BLE001
            finished = datetime.now(timezone.utc)
            self._append_row(request, started_at=started, finished_at=finished, before=before, after=before - 1, exc=exc)
            raise
        return _LedgeredCoinalyzeResponse(
            response=response,
            request=request,
            ledger_path=self.ledger_path,
            started_at=started,
            budget_before=before,
            budget_after=before - 1,
            api_key=self.api_key,
        )

    def _append_row(
        self,
        request: Request,
        *,
        started_at: datetime,
        finished_at: datetime,
        before: int,
        after: int,
        exc: Exception,
    ) -> None:
        _append_ledger_row(
            self.ledger_path,
            _ledger_row(
                request,
                started_at=started_at,
                finished_at=finished_at,
                budget_before=before,
                budget_after=after,
                success=False,
                api_key=self.api_key,
                error=exc,
            ),
        )


class _LedgeredCoinalyzeResponse:
    def __init__(
        self,
        *,
        response: Any,
        request: Request,
        ledger_path: Path,
        started_at: datetime,
        budget_before: int,
        budget_after: int,
        api_key: str,
    ) -> None:
        self.response = response
        self.request = request
        self.ledger_path = ledger_path
        self.started_at = started_at
        self.budget_before = budget_before
        self.budget_after = budget_after
        self.api_key = api_key
        self.payload: bytes | None = None
        self.entered: Any = None

    def __enter__(self) -> "_LedgeredCoinalyzeResponse":
        if hasattr(self.response, "__enter__"):
            self.entered = self.response.__enter__()
        else:
            self.entered = self.response
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        finished = datetime.now(timezone.utc)
        success = exc is None
        row = _ledger_row(
            self.request,
            started_at=self.started_at,
            finished_at=finished,
            budget_before=self.budget_before,
            budget_after=self.budget_after,
            success=success,
            api_key=self.api_key,
            response=self.entered or self.response,
            payload=self.payload,
            error=exc if isinstance(exc, Exception) else None,
        )
        _append_ledger_row(self.ledger_path, row)
        if hasattr(self.response, "__exit__"):
            return bool(self.response.__exit__(exc_type, exc, tb))
        return False

    def read(self) -> bytes:
        target = self.entered or self.response
        raw = target.read()
        self.payload = raw
        return raw


class RequestBudgetExceeded(RuntimeError):
    pass


def _default_urlopen(request: Request, timeout: float) -> Any:
    from urllib.request import urlopen

    return urlopen(request, timeout=timeout)


def _ledger_row(
    request: Request,
    *,
    started_at: datetime,
    finished_at: datetime,
    budget_before: int,
    budget_after: int,
    success: bool,
    api_key: str,
    response: Any | None = None,
    payload: bytes | None = None,
    error: Exception | None = None,
) -> dict[str, Any]:
    status_code = _status_code(response, error)
    safe_error = _safe_error_message(error, api_key) if error else None
    return {
        "schema_version": "event_coinalyze_request_ledger_v1",
        "provider": "coinalyze",
        "endpoint": _endpoint(request.full_url),
        "sanitized_url": _sanitized_url(request.full_url),
        "method": getattr(request, "method", None) or request.get_method(),
        "started_at": started_at.astimezone(timezone.utc).isoformat(),
        "finished_at": finished_at.astimezone(timezone.utc).isoformat(),
        "duration_ms": max(0, int((finished_at - started_at).total_seconds() * 1000)),
        "status_code": status_code,
        "success": bool(success),
        "result_count": _result_count(payload),
        "error_class": type(error).__name__ if error else None,
        "error_message_safe": safe_error,
        "request_budget_before": budget_before,
        "request_budget_after": budget_after,
        "live_call_allowed": True,
        "token_redacted": True,
        "no_send_rehearsal": True,
    }


def _append_ledger_row(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(dict(row), sort_keys=True) + "\n")


def _endpoint(url: str) -> str:
    parsed = urlparse(url)
    return parsed.path.rstrip("/").rsplit("/", 1)[-1]


def _sanitized_url(url: str) -> str:
    parsed = urlparse(url)
    query = urlencode(
        [
            (key, "<redacted>" if _secret_param(key) else value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        ]
    )
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, ""))


def _secret_param(key: str) -> bool:
    lowered = key.casefold()
    return "key" in lowered or "token" in lowered or "secret" in lowered


def _status_code(response: Any | None, error: Exception | None) -> int | None:
    if isinstance(error, HTTPError):
        return int(error.code)
    for obj in (response,):
        if obj is None:
            continue
        for attr in ("status", "code"):
            value = getattr(obj, attr, None)
            if value not in (None, ""):
                try:
                    return int(value)
                except (TypeError, ValueError):
                    pass
        getcode = getattr(obj, "getcode", None)
        if callable(getcode):
            try:
                return int(getcode())
            except (TypeError, ValueError):
                pass
    return None


def _result_count(payload: bytes | None) -> int | None:
    if payload is None:
        return None
    try:
        parsed = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if isinstance(parsed, list):
        return len(parsed)
    if isinstance(parsed, Mapping):
        for key in ("data", "result", "results", "snapshots"):
            value = parsed.get(key)
            if isinstance(value, list):
                return len(value)
        return 1
    return None


def _safe_error_message(error: Exception | None, api_key: str) -> str | None:
    if error is None:
        return None
    text = str(error)
    if isinstance(error, HTTPError):
        text = f"HTTP {error.code}: {error.reason}"
    elif isinstance(error, URLError):
        text = f"URL error: {error.reason}"
    if api_key:
        text = text.replace(api_key, "<coinalyze-api-key>")
    return text[:240]


def artifact_conflicts(namespace_dir: str | Path | None) -> dict[str, int]:
    out = {
        "coinalyze_preflight_secret_leak": 0,
        "coinalyze_preflight_live_call_allowed_in_smoke": 0,
        "coinalyze_preflight_configured_missing_env": 0,
        "coinalyze_preflight_ready_without_request_ledger": 0,
        "coinalyze_preflight_missing_fixture_parser_status": 0,
        "coinalyze_preflight_forbidden_side_effect_claim": 0,
        "coinalyze_rehearsal_secret_leak": 0,
        "coinalyze_rehearsal_live_without_ledger": 0,
        "coinalyze_rehearsal_live_call_allowed_in_smoke": 0,
        "coinalyze_rehearsal_live_without_explicit_allow": 0,
        "coinalyze_rehearsal_request_budget_exceeded": 0,
        "coinalyze_rehearsal_success_without_derivatives_state": 0,
        "coinalyze_provider_health_healthy_without_successful_ledger": 0,
        "coinalyze_rehearsal_forbidden_side_effect_claim": 0,
    }
    if namespace_dir is None:
        return out
    base = Path(namespace_dir)
    paths = [base / PREFLIGHT_JSON, base / PREFLIGHT_MD, base / REHEARSAL_JSON, base / REHEARSAL_MD, base / REQUEST_LEDGER]
    existing = [path for path in paths if path.exists()]
    if not existing:
        return out
    text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in existing)
    if _secret_like(text):
        out["coinalyze_preflight_secret_leak"] = 1
        out["coinalyze_rehearsal_secret_leak"] = 1
    data: Mapping[str, Any] = {}
    try:
        parsed = json.loads((base / PREFLIGHT_JSON).read_text(encoding="utf-8"))
        if isinstance(parsed, Mapping):
            data = parsed
    except (OSError, json.JSONDecodeError):
        data = {}
    if data:
        if bool(data.get("smoke_mode")) and bool(data.get("live_call_allowed")):
            out["coinalyze_preflight_live_call_allowed_in_smoke"] = 1
        if bool(data.get("configured")) and not _api_key():
            out["coinalyze_preflight_configured_missing_env"] = 1
        if str(data.get("preflight_status") or "") in {"ready_for_no_send_rehearsal", "ready_for_no_send_live_rehearsal"} and not str(data.get("request_ledger_path") or "").strip():
            out["coinalyze_preflight_ready_without_request_ledger"] = 1
        if not str(data.get("fixture_parser_status") or "").strip():
            out["coinalyze_preflight_missing_fixture_parser_status"] = 1
    if re.search(r"(?i)\b(send telegram|paper trade|live trade|execute order|triggered_fade created)\b", text):
        out["coinalyze_preflight_forbidden_side_effect_claim"] = 1
    rehearsal_data: Mapping[str, Any] = {}
    try:
        parsed = json.loads((base / REHEARSAL_JSON).read_text(encoding="utf-8"))
        if isinstance(parsed, Mapping):
            rehearsal_data = parsed
    except (OSError, json.JSONDecodeError):
        rehearsal_data = {}
    ledger_rows = _read_jsonl(base / REQUEST_LEDGER)
    if rehearsal_data:
        status = str(rehearsal_data.get("status") or "")
        live_allowed = bool(rehearsal_data.get("live_call_allowed"))
        requests_used = int(rehearsal_data.get("requests_used") or 0)
        max_requests = int(rehearsal_data.get("max_requests_per_run") or 0)
        if live_allowed and not ledger_rows:
            out["coinalyze_rehearsal_live_without_ledger"] = 1
        if bool(rehearsal_data.get("smoke_mode")) and live_allowed:
            out["coinalyze_rehearsal_live_call_allowed_in_smoke"] = 1
        if live_allowed and not bool(rehearsal_data.get("allow_live_preflight")):
            out["coinalyze_rehearsal_live_without_explicit_allow"] = 1
        if max_requests >= 0 and requests_used > max_requests:
            out["coinalyze_rehearsal_request_budget_exceeded"] = 1
        if status in {"live_rehearsal_success", "live_rehearsal_partial"} and int(rehearsal_data.get("snapshots_written") or 0) <= 0:
            out["coinalyze_rehearsal_success_without_derivatives_state"] = 1
        for key in (
            "strict_alerts_created",
            "telegram_sends",
            "trades_created",
            "paper_trades_created",
            "normal_rsi_signal_rows_written",
            "triggered_fade_created",
        ):
            if int(rehearsal_data.get(key) or 0) != 0:
                out["coinalyze_rehearsal_forbidden_side_effect_claim"] = 1
    if re.search(r"(?i)\b(send telegram|paper trade|live trade|execute order|triggered_fade created)\b", text):
        out["coinalyze_rehearsal_forbidden_side_effect_claim"] = 1
    health_rows = _provider_health_rows(base / "event_provider_health.json")
    if _coinalyze_health_healthy(health_rows) and not any(
        row.get("provider") == "coinalyze" and row.get("success") for row in ledger_rows
    ):
        out["coinalyze_provider_health_healthy_without_successful_ledger"] = 1
    return out


def _provider_health_rows(path: Path) -> tuple[Mapping[str, Any], ...]:
    if not path.exists():
        return ()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    providers = raw.get("providers") if isinstance(raw, Mapping) else None
    if isinstance(providers, Mapping):
        return tuple(dict(value) for value in providers.values() if isinstance(value, Mapping))
    return ()


def _coinalyze_health_healthy(rows: Iterable[Mapping[str, Any]]) -> bool:
    for row in rows:
        if "coinalyze" not in " ".join(str(row.get(key) or "") for key in ("provider", "provider_key", "provider_service")).casefold():
            continue
        status = str(row.get("provider_coverage_status") or "").casefold()
        if status in {"observed_healthy", "observed_partial_success"}:
            return True
        if row.get("last_success_at") and not int(row.get("consecutive_failures") or 0):
            return True
    return False


def _fixture_path() -> Path | None:
    raw = config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH or "fixtures/event_discovery/coinalyze_derivatives.json"
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path if path.exists() else None


def _fixture_parser_status(path: Path | None) -> tuple[str, set[str], list[str]]:
    if path is None:
        return "missing_fixture", set(), ["fixture_missing"]
    warnings: list[str] = []
    symbols: set[str] = set()
    try:
        snapshots = CoinalyzeDerivativesProvider(path).fetch_snapshots()
    except Exception as exc:  # noqa: BLE001 - preflight must fail soft
        return "failed", set(), [f"fixture_parser_error:{type(exc).__name__}"]
    for key, snapshot in snapshots.items():
        symbols.add(str(getattr(snapshot, "base_symbol", "") or key).upper())
        missing_metrics = [
            field for field in (
                "open_interest",
                "funding_rate_8h",
                "liquidations_24h",
                "long_short_ratio",
                "basis",
            )
            if getattr(snapshot, field, None) is None and getattr(snapshot, "perp_available", False)
        ]
        if missing_metrics:
            warnings.append(f"{key}:missing_metrics:{','.join(missing_metrics)}")
    return ("pass" if snapshots else "empty_fixture"), symbols, warnings


def _fixture_symbol_mapping_status(symbols: set[str]) -> str:
    markets = [
        {"symbol": f"{symbol}USDT_PERP", "base_asset": symbol, "quote_asset": "USDT", "is_perpetual": True}
        for symbol in FIXTURE_SYMBOLS
    ]
    resolved = set(resolve_future_market_symbols(markets, FIXTURE_SYMBOLS))
    expected = {f"{symbol}USDT_PERP" for symbol in FIXTURE_SYMBOLS}
    if expected <= resolved:
        return "pass"
    fixture_ready = {"TESTPERP", "TESTFADE", "TESTLIST", "TESTVELVET"} & symbols
    if fixture_ready:
        return "fixture_parser_pass_mapping_incomplete"
    return "missing_fixture_symbols"


def _secret_like(text: str) -> bool:
    return bool(
        re.search(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}", text)
        or re.search(r"(?i)(api[_-]?key|token|secret)\s*[=:]\s*['\"][A-Za-z0-9._-]{20,}['\"]", text)
    )
