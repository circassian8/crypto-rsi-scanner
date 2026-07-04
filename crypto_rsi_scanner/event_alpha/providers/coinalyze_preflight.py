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
from urllib.request import Request

from ... import config
from ...derivatives_providers.coinalyze import CoinalyzeDerivativesProvider, resolve_future_market_symbols
from ..artifacts import paths as event_artifact_paths
from ..artifacts import schema_v1
from ..radar import derivatives_crowding as event_derivatives_crowding
from . import provider_health as event_provider_health
from .coinalyze_preflight_report import (
    format_preflight_report,
    format_rehearsal_report,
    _format_counts,
    _format_metric_status,
    _metrics_by_report_status,
)
from .coinalyze_preflight_ledger import (
    RequestBudgetExceeded,
    _LedgeredCoinalyzeOpener,
    _LedgeredCoinalyzeResponse,
    _append_ledger_row,
    _default_urlopen,
    _endpoint,
    _ledger_row,
    _result_count,
    _safe_error_message,
    _sanitized_url,
    _secret_param,
    _status_code,
)


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
SUPPORTED_METRIC_STATUS = dict(event_derivatives_crowding.DERIVATIVES_LIVE_METRIC_IMPLEMENTATION_STATUS)
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
    "predicted-funding-rate",
    "open-interest-history",
    "liquidation-history",
    "long-short-ratio-history",
    "ohlcv-history",
)
_TRUTHY = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class _CoinalyzeLiveRehearsalResult:
    status: str
    error_class: str | None
    error_message_safe: str | None
    snapshots_written: int
    crowding_written: int
    fade_written: int
    candidate_rows: tuple[dict[str, Any], ...]
    provider_health_status: str


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
    crowding_class_counts: dict[str, int]
    fade_readiness_counts: dict[str, int]
    symbols_with_extreme_crowding: tuple[str, ...]
    symbols_with_confirmed_long_crowding_warning: tuple[str, ...]
    supported_metric_status: Mapping[str, str]
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
        return coinalyze_rehearsal_report_row(self)


def coinalyze_rehearsal_report_row(report: CoinalyzeRehearsalReport) -> dict[str, Any]:
    return {
        "schema_version": "event_coinalyze_rehearsal_v1",
        "row_type": "event_coinalyze_rehearsal_report",
        "provider": report.provider,
        "status": report.status,
        "configured": report.configured,
        "allow_live_preflight": report.allow_live_preflight,
        "live_call_allowed": report.live_call_allowed,
        "no_send": report.no_send,
        "research_only": report.research_only,
        "generated_at": report.generated_at,
        "request_ledger_path": report.request_ledger_path,
        "preflight_json_path": report.preflight_json_path,
        "preflight_report_path": report.preflight_report_path,
        "rehearsal_json_path": report.rehearsal_json_path,
        "rehearsal_report_path": report.rehearsal_report_path,
        "derivatives_state_path": report.derivatives_state_path,
        "derivatives_candidates_path": report.derivatives_candidates_path,
        "fade_review_candidates_path": report.fade_review_candidates_path,
        "max_requests_per_run": report.max_requests_per_run,
        "requests_used": report.requests_used,
        "symbols_requested": list(report.symbols_requested),
        "symbols_resolved": list(report.symbols_resolved),
        "snapshots_written": report.snapshots_written,
        "crowding_candidates_written": report.crowding_candidates_written,
        "fade_review_candidates_written": report.fade_review_candidates_written,
        "crowding_class_counts": dict(report.crowding_class_counts),
        "fade_readiness_counts": dict(report.fade_readiness_counts),
        "symbols_with_extreme_crowding": list(report.symbols_with_extreme_crowding),
        "symbols_with_confirmed_long_crowding_warning": list(report.symbols_with_confirmed_long_crowding_warning),
        "supported_metric_status": dict(report.supported_metric_status),
        "implemented_metrics": _metrics_with_status(
            report.supported_metric_status,
            event_derivatives_crowding.METRIC_STATUS_IMPLEMENTED,
        ),
        "fixture_only_metrics": _metrics_with_status(
            report.supported_metric_status,
            event_derivatives_crowding.METRIC_STATUS_FIXTURE_ONLY,
        ),
        "missing_or_planned_metrics": _metrics_with_status(
            report.supported_metric_status,
            event_derivatives_crowding.METRIC_STATUS_MISSING_FROM_RESPONSE,
            event_derivatives_crowding.METRIC_STATUS_NOT_IMPLEMENTED,
            event_derivatives_crowding.METRIC_STATUS_PROVIDER_UNAVAILABLE,
        ),
        "provider_health_status": report.provider_health_status,
        "error_class": report.error_class,
        "error_message_safe": report.error_message_safe,
        "warnings": list(report.warnings),
        "strict_alerts_created": report.strict_alerts_created,
        "telegram_sends": report.telegram_sends,
        "trades_created": report.trades_created,
        "paper_trades_created": report.paper_trades_created,
        "normal_rsi_signal_rows_written": report.normal_rsi_signal_rows_written,
        "triggered_fade_created": report.triggered_fade_created,
    }


def _metrics_with_status(metric_status: Mapping[str, str], *statuses: str) -> list[str]:
    allowed = set(statuses)
    return [
        metric
        for metric, status in metric_status.items()
        if status in allowed
    ]


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
    supported_metric_status: Mapping[str, str]
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
            "supported_metric_status": dict(self.supported_metric_status),
            "implemented_metrics": [
                metric
                for metric, status in self.supported_metric_status.items()
                if status == event_derivatives_crowding.METRIC_STATUS_IMPLEMENTED
            ],
            "fixture_only_metrics": [
                metric
                for metric, status in self.supported_metric_status.items()
                if status == event_derivatives_crowding.METRIC_STATUS_FIXTURE_ONLY
            ],
            "missing_or_planned_metrics": [
                metric
                for metric, status in self.supported_metric_status.items()
                if status in {
                    event_derivatives_crowding.METRIC_STATUS_MISSING_FROM_RESPONSE,
                    event_derivatives_crowding.METRIC_STATUS_NOT_IMPLEMENTED,
                    event_derivatives_crowding.METRIC_STATUS_PROVIDER_UNAVAILABLE,
                }
            ],
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
        supported_metric_status=dict(SUPPORTED_METRIC_STATUS),
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
    payload = schema_v1.stamp_artifact_payload(report.to_dict(), path=json_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
        next_step = "run the bounded no-send rehearsal only with explicit allow flag and request ledger enforcement"
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
    candidate_rows: tuple[dict[str, Any], ...] = ()
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
        live_result = _run_live_coinalyze_rehearsal(
            base=base,
            ledger_path=ledger_path,
            derivatives_state_path=derivatives_state_path,
            derivatives_candidates_path=derivatives_candidates_path,
            fade_review_path=fade_review_path,
            provider_health_path=provider_health_path,
            requested_symbols=requested_symbols,
            explicit_symbols=explicit_symbols,
            max_requests=max_requests,
            profile=profile,
            artifact_namespace=artifact_namespace,
            opener=opener,
            clock=clock,
            warnings=warnings,
            observed=observed,
        )
        status = live_result.status
        error_class = live_result.error_class
        error_message_safe = live_result.error_message_safe
        snapshots_written = live_result.snapshots_written
        crowding_written = live_result.crowding_written
        fade_written = live_result.fade_written
        candidate_rows = live_result.candidate_rows
        provider_health_status = live_result.provider_health_status

    requests_used = len(_read_jsonl(ledger_path))
    crowding_class_counts = _counts(str(row.get("crowding_class") or "unknown") for row in candidate_rows)
    fade_readiness_counts = _counts(str(row.get("fade_readiness") or "unknown") for row in candidate_rows)
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
        crowding_class_counts=crowding_class_counts,
        fade_readiness_counts=fade_readiness_counts,
        symbols_with_extreme_crowding=_symbols_with_crowding_class(candidate_rows, "extreme"),
        symbols_with_confirmed_long_crowding_warning=_symbols_with_confirmed_long_crowding_warning(candidate_rows),
        supported_metric_status=_metric_status_from_state_rows(_read_jsonl(derivatives_state_path)),
        provider_health_status=provider_health_status,
        error_class=error_class,
        error_message_safe=error_message_safe,
        warnings=tuple(dict.fromkeys(warnings)),
    )
    payload = schema_v1.stamp_artifact_payload(report.to_dict(), schema_id="provider_preflight_v1", path=rehearsal_json)
    rehearsal_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rehearsal_md.write_text(format_rehearsal_report(report) + "\n", encoding="utf-8")
    return preflight, report, (preflight_json, preflight_md, rehearsal_json, rehearsal_md)


def _run_live_coinalyze_rehearsal(
    *,
    base: Path,
    ledger_path: Path,
    derivatives_state_path: Path,
    derivatives_candidates_path: Path,
    fade_review_path: Path,
    provider_health_path: str | Path,
    requested_symbols: tuple[str, ...],
    explicit_symbols: bool,
    max_requests: int,
    profile: str | None,
    artifact_namespace: str | None,
    opener: Callable[[Request, float], Any] | None,
    clock: Callable[[], float] | None,
    warnings: list[str],
    observed: datetime,
) -> _CoinalyzeLiveRehearsalResult:
    ledger = _LedgeredCoinalyzeOpener(
        ledger_path=ledger_path,
        api_key=_api_key(),
        max_requests=max_requests,
        opener=opener,
        now=observed,
    )
    provider: CoinalyzeDerivativesProvider | None = None
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
        error_class = None
        error_message_safe = None
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
    run_id = f"coinalyze-rehearsal-{int(observed.timestamp())}"
    state_rows = _derivatives_state_rows(
        snapshots.values(),
        observed_at=observed,
        profile=profile,
        artifact_namespace=artifact_namespace,
        run_id=run_id,
    )
    candidate_rows: tuple[dict[str, Any], ...] = ()
    candidate_evaluation_complete = False
    crowding_written = 0
    fade_written = 0
    if state_rows:
        try:
            derivatives_result = event_derivatives_crowding.run_derivatives_crowding_scan_from_state_rows(
                namespace_dir=base,
                state_rows=state_rows,
                profile=profile,
                artifact_namespace=artifact_namespace,
                run_mode="no_send_rehearsal",
                run_id=run_id,
                observed_at=observed,
                no_send_rehearsal=True,
                warnings=warnings,
            )
            candidate_rows = derivatives_result.candidate_rows
            candidate_evaluation_complete = derivatives_result.evaluated_candidate_count >= len(state_rows)
            crowding_written = derivatives_result.evaluated_candidate_count
            fade_written = derivatives_result.fade_review_candidate_count
        except Exception as exc:  # noqa: BLE001 - rehearsal artifacts must fail safe
            _write_jsonl(derivatives_state_path, state_rows)
            _write_jsonl(derivatives_candidates_path, [])
            _write_jsonl(fade_review_path, [])
            warnings.append(f"derivatives_candidate_evaluation_failed:{type(exc).__name__}")
            error_class = error_class or type(exc).__name__
            error_message_safe = error_message_safe or _safe_error_message(exc, _api_key())
    if status == "live_rehearsal_success" and state_rows and not candidate_evaluation_complete:
        status = "live_rehearsal_partial"
        error_class = error_class or "candidate_evaluation_partial"
        error_message_safe = error_message_safe or "derivatives candidate evaluation did not complete"
    snapshots_written = len(state_rows)
    provider_health_status = _record_provider_health(
        status=status,
        provider_health_path=provider_health_path,
        now=observed,
        run_id=run_id,
        successful_ledger_rows=sum(1 for row in ledger_rows if bool(row.get("success"))),
        derivatives_state_rows=snapshots_written,
        candidate_evaluation_complete=candidate_evaluation_complete,
        error_class=error_class,
        error_message=error_message_safe,
    )
    return _CoinalyzeLiveRehearsalResult(
        status=status,
        error_class=error_class,
        error_message_safe=error_message_safe,
        snapshots_written=snapshots_written,
        crowding_written=crowding_written,
        fade_written=fade_written,
        candidate_rows=candidate_rows,
        provider_health_status=provider_health_status,
    )


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
    return 7 if explicit_symbols else 8


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
    run_id: str,
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
                run_id=run_id,
            )
        )
        rows[-1]["no_send_rehearsal"] = True
        rows[-1]["strict_alerts_created"] = 0
        rows[-1]["telegram_sends"] = 0
        rows[-1]["trades_created"] = 0
        rows[-1]["paper_trades_created"] = 0
        rows[-1]["normal_rsi_signal_rows_written"] = 0
        rows[-1]["triggered_fade_created"] = 0
    return rows


def _symbols_from_state_file(path: Path) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            str(row.get("symbol") or "").upper()
            for row in _read_jsonl(path)
            if str(row.get("symbol") or "").strip()
        )
    )


def _counts(values: Iterable[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        text = str(value or "").strip() or "unknown"
        out[text] = out.get(text, 0) + 1
    return dict(sorted(out.items()))


def _metric_status_from_state_rows(rows: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    materialized = [dict(row) for row in rows if isinstance(row, Mapping)]
    if not materialized:
        return dict(SUPPORTED_METRIC_STATUS)
    out: dict[str, str] = {}
    priority = {
        event_derivatives_crowding.METRIC_STATUS_IMPLEMENTED: 5,
        event_derivatives_crowding.METRIC_STATUS_FIXTURE_ONLY: 4,
        event_derivatives_crowding.METRIC_STATUS_MISSING_FROM_RESPONSE: 3,
        event_derivatives_crowding.METRIC_STATUS_NOT_IMPLEMENTED: 2,
        event_derivatives_crowding.METRIC_STATUS_PROVIDER_UNAVAILABLE: 1,
    }
    for metric in SUPPORTED_METRICS:
        observed_statuses: list[str] = []
        for row in materialized:
            status = row.get("supported_metric_status")
            if isinstance(status, Mapping) and str(status.get(metric) or "").strip():
                observed_statuses.append(str(status.get(metric)))
        if observed_statuses:
            out[metric] = max(observed_statuses, key=lambda value: priority.get(value, 0))
        else:
            out[metric] = SUPPORTED_METRIC_STATUS.get(metric, event_derivatives_crowding.METRIC_STATUS_NOT_IMPLEMENTED)
    return out


def _symbols_with_crowding_class(rows: Iterable[Mapping[str, Any]], crowding_class: str) -> tuple[str, ...]:
    target = crowding_class.casefold()
    symbols = (
        str(row.get("symbol") or "").upper()
        for row in rows
        if str(row.get("crowding_class") or "").casefold() == target
    )
    return tuple(dict.fromkeys(symbol for symbol in symbols if symbol))


def _symbols_with_confirmed_long_crowding_warning(rows: Iterable[Mapping[str, Any]]) -> tuple[str, ...]:
    symbols: list[str] = []
    for row in rows:
        if str(row.get("opportunity_type") or "").upper() != "CONFIRMED_LONG_RESEARCH":
            continue
        warnings = [str(item) for item in row.get("warnings") or () if str(item)]
        if not any("crowding" in warning.casefold() for warning in warnings):
            continue
        symbol = str(row.get("symbol") or "").upper()
        if symbol:
            symbols.append(symbol)
    return tuple(dict.fromkeys(symbols))


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    materialized = [schema_v1.stamp_artifact_row(row, path=path) for row in rows if isinstance(row, Mapping)]
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
    successful_ledger_rows: int,
    derivatives_state_rows: int,
    candidate_evaluation_complete: bool,
    error_class: str | None,
    error_message: str | None,
) -> str:
    cfg = event_provider_health.EventProviderHealthConfig(path=Path(provider_health_path), max_consecutive_failures=1)
    has_successful_ledger = successful_ledger_rows > 0
    has_derivatives_state = derivatives_state_rows > 0
    if status == "live_rehearsal_success" and has_successful_ledger and has_derivatives_state and candidate_evaluation_complete:
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
    if status in {"live_rehearsal_success", "live_rehearsal_partial"} and has_successful_ledger:
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
        "coinalyze_rehearsal_success_without_crowding_candidates": 0,
        "coinalyze_provider_health_healthy_without_successful_ledger": 0,
        "coinalyze_rehearsal_forbidden_side_effect_claim": 0,
        "coinalyze_supported_metric_implemented_missing_state": 0,
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
    state_rows = _read_jsonl(base / event_derivatives_crowding.DERIVATIVES_STATE_FILENAME)
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
        if status == "live_rehearsal_success" and int(rehearsal_data.get("crowding_candidates_written") or 0) <= 0:
            out["coinalyze_rehearsal_success_without_crowding_candidates"] = 1
        supported_status = rehearsal_data.get("supported_metric_status")
        if isinstance(supported_status, Mapping) and status in {"live_rehearsal_success", "live_rehearsal_partial"}:
            for metric, metric_status in supported_status.items():
                if str(metric_status) != event_derivatives_crowding.METRIC_STATUS_IMPLEMENTED:
                    continue
                if not any(_state_metric_has_value(row, str(metric)) for row in state_rows):
                    out["coinalyze_supported_metric_implemented_missing_state"] += 1
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
    if _coinalyze_health_observed_healthy(health_rows) and (
        not any(row.get("provider") == "coinalyze" and row.get("success") for row in ledger_rows)
        or not state_rows
    ):
        out["coinalyze_provider_health_healthy_without_successful_ledger"] = 1
    return out


def _state_metric_has_value(row: Mapping[str, Any], metric: str) -> bool:
    values = {
        "open_interest": ("open_interest", "open_interest_delta_1h", "open_interest_delta_4h", "open_interest_delta_24h"),
        "funding_rate": ("funding_rate",),
        "predicted_funding": ("predicted_funding_rate",),
        "liquidations": ("liquidation_long_usd", "liquidation_short_usd", "liquidation_imbalance"),
        "long_short_ratio": ("long_short_ratio",),
        "basis": ("basis",),
        "perp_volume": ("perp_volume", "perp_spot_volume_ratio"),
    }
    return any(row.get(key) not in (None, "", [], {}, ()) for key in values.get(metric, ()))


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


def _coinalyze_health_observed_healthy(rows: Iterable[Mapping[str, Any]]) -> bool:
    for row in rows:
        if "coinalyze" not in " ".join(str(row.get(key) or "") for key in ("provider", "provider_key", "provider_service")).casefold():
            continue
        status = str(row.get("provider_coverage_status") or "").casefold()
        if status == "observed_healthy":
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
