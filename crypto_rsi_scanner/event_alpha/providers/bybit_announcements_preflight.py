"""Bybit official-announcement preflight and bounded no-send rehearsal.

This module is deliberately research-only. The default preflight validates local
fixture/parser readiness and writes operator artifacts without network calls.
Live HTTP rehearsal requires an explicit allow flag/env var, no-send mode, a
small page/limit budget, and a request ledger.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request

from ... import config
from ...event_providers._announcement_common import _announcement_items
from ...event_providers.bybit_announcements import BybitAnnouncementProvider
from ..artifacts import paths as event_artifact_paths
from ..artifacts import schema_v1
from . import official_exchange as event_official_exchange
from . import official_exchange_activation as event_official_exchange_activation
from . import provider_health as event_provider_health


PREFLIGHT_JSON = "event_bybit_announcements_preflight.json"
PREFLIGHT_MD = "event_bybit_announcements_preflight.md"
REQUEST_LEDGER = "event_bybit_announcements_request_ledger.jsonl"
REHEARSAL_JSON = "event_bybit_announcements_rehearsal_report.json"
REHEARSAL_MD = "event_bybit_announcements_rehearsal_report.md"
ENV_ALLOW_LIVE_PREFLIGHT = "RSI_EVENT_ALPHA_BYBIT_ANNOUNCEMENTS_ALLOW_LIVE_PREFLIGHT"
ENV_PREFLIGHT_MAX_PAGES = "RSI_EVENT_ALPHA_BYBIT_ANNOUNCEMENTS_PREFLIGHT_MAX_PAGES"
ENV_PREFLIGHT_LIMIT = "RSI_EVENT_ALPHA_BYBIT_ANNOUNCEMENTS_PREFLIGHT_LIMIT"
ENV_PREFLIGHT_TAG = "RSI_EVENT_ALPHA_BYBIT_ANNOUNCEMENTS_PREFLIGHT_TAG"
PROVIDER_HEALTH_KEY = "bybit_announcements"
DEFAULT_PREFLIGHT_NAMESPACE = "bybit_announcements_preflight"
DEFAULT_REHEARSAL_NAMESPACE = "bybit_announcements_no_send_rehearsal"
SUPPORTED_PARAMS = ("locale", "type", "tag", "page", "limit")
SOURCE_PACKS = ("official_exchange_listing_pack", "official_perp_listing_pack", "official_exchange_risk_pack")
LANES_ENABLED = ("EARLY_LONG_RESEARCH", "CONFIRMED_LONG_RESEARCH", "RISK_ONLY")
_TRUTHY = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class BybitAnnouncementsPreflightReport:
    provider: str
    category: str
    configured: bool
    env_vars_required: tuple[str, ...]
    live_call_allowed: bool
    smoke_mode: bool
    preflight_status: str
    request_budget: str
    max_pages: int
    limit: int
    timeout_seconds: float
    cache_ttl_seconds: int
    request_ledger_path: str
    provider_health_key: str
    fixture_parser_status: str
    fixture_rows_observed: int
    supported_params: tuple[str, ...]
    lanes_enabled_if_healthy: tuple[str, ...]
    source_packs_enabled: tuple[str, ...]
    safety_notes: tuple[str, ...]
    generated_at: str
    fixture_path: str | None = None
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "event_bybit_announcements_preflight_v1",
            "row_type": "event_bybit_announcements_preflight",
            "provider": self.provider,
            "category": self.category,
            "configured": self.configured,
            "env_vars_required": list(self.env_vars_required),
            "live_call_allowed": self.live_call_allowed,
            "smoke_mode": self.smoke_mode,
            "preflight_status": self.preflight_status,
            "request_budget": self.request_budget,
            "max_pages": self.max_pages,
            "limit": self.limit,
            "timeout_seconds": self.timeout_seconds,
            "cache_ttl_seconds": self.cache_ttl_seconds,
            "request_ledger_path": self.request_ledger_path,
            "provider_health_key": self.provider_health_key,
            "fixture_parser_status": self.fixture_parser_status,
            "fixture_rows_observed": self.fixture_rows_observed,
            "supported_params": list(self.supported_params),
            "lanes_enabled_if_healthy": list(self.lanes_enabled_if_healthy),
            "source_packs_enabled": list(self.source_packs_enabled),
            "safety_notes": list(self.safety_notes),
            "generated_at": self.generated_at,
            "fixture_path": self.fixture_path,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class BybitAnnouncementsRehearsalReport:
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
    exchange_announcements_path: str
    official_exchange_events_path: str
    official_listing_candidates_path: str
    official_exchange_report_path: str
    max_pages: int
    limit: int
    requests_used: int
    http_successes: int
    announcements_inspected: int
    exchange_announcements_written: int
    official_events_written: int
    official_listing_candidates_written: int
    supported_params: tuple[str, ...]
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
        return bybit_announcements_rehearsal_report_row(self)


def bybit_announcements_rehearsal_report_row(report: BybitAnnouncementsRehearsalReport) -> dict[str, Any]:
    return {
        "schema_version": "event_bybit_announcements_rehearsal_v1",
        "row_type": "event_bybit_announcements_rehearsal_report",
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
        "exchange_announcements_path": report.exchange_announcements_path,
        "official_exchange_events_path": report.official_exchange_events_path,
        "official_listing_candidates_path": report.official_listing_candidates_path,
        "official_exchange_report_path": report.official_exchange_report_path,
        "max_pages": report.max_pages,
        "limit": report.limit,
        "requests_used": report.requests_used,
        "http_successes": report.http_successes,
        "announcements_inspected": report.announcements_inspected,
        "exchange_announcements_written": report.exchange_announcements_written,
        "official_events_written": report.official_events_written,
        "official_listing_candidates_written": report.official_listing_candidates_written,
        "supported_params": list(report.supported_params),
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


def build_preflight_report(
    *,
    namespace_dir: str | Path,
    smoke_mode: bool = False,
    allow_live_preflight: bool = False,
    now: datetime | None = None,
) -> BybitAnnouncementsPreflightReport:
    base = Path(namespace_dir).expanduser()
    allow_live = effective_allow_live_preflight(allow_live_preflight)
    live_allowed = bool(allow_live and not smoke_mode)
    fixture_path = _fixture_path()
    fixture_parser_status, fixture_rows, parser_warnings = _fixture_parser_status(fixture_path)
    if smoke_mode:
        status = "fixture_ready" if fixture_parser_status == "pass" else "fixture_parser_failed"
    elif not allow_live:
        status = "config_ready_no_live"
    else:
        status = "ready_for_no_send_rehearsal"
    max_pages = _max_pages()
    limit = _limit()
    return BybitAnnouncementsPreflightReport(
        provider=PROVIDER_HEALTH_KEY,
        category="official_exchange_announcements",
        configured=True,
        env_vars_required=(),
        live_call_allowed=live_allowed,
        smoke_mode=bool(smoke_mode),
        preflight_status=status,
        request_budget="bounded no-send research rehearsal only; no live call by default",
        max_pages=max_pages if live_allowed else 0,
        limit=limit if live_allowed else 0,
        timeout_seconds=float(config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_TIMEOUT or 10.0),
        cache_ttl_seconds=900,
        request_ledger_path=event_artifact_paths.artifact_display_path(base / REQUEST_LEDGER),
        provider_health_key=PROVIDER_HEALTH_KEY,
        fixture_parser_status=fixture_parser_status,
        fixture_rows_observed=fixture_rows,
        supported_params=SUPPORTED_PARAMS,
        lanes_enabled_if_healthy=LANES_ENABLED,
        source_packs_enabled=SOURCE_PACKS,
        safety_notes=(
            f"no live calls unless --event-alpha-bybit-announcements-allow-live-preflight or {ENV_ALLOW_LIVE_PREFLIGHT}=1 is explicit",
            "no Telegram sends, trades, paper trades, normal RSI rows, or Event Alpha TRIGGERED_FADE",
            "Bybit announcements endpoint is public; no API key is required or written",
        ),
        generated_at=(now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(),
        fixture_path=event_artifact_paths.artifact_display_path(fixture_path) if fixture_path else None,
        warnings=tuple(parser_warnings),
    )


def write_preflight_artifacts(report: BybitAnnouncementsPreflightReport, namespace_dir: str | Path) -> tuple[Path, Path]:
    base = Path(namespace_dir).expanduser()
    base.mkdir(parents=True, exist_ok=True)
    json_path = base / PREFLIGHT_JSON
    md_path = base / PREFLIGHT_MD
    payload = schema_v1.stamp_artifact_payload(report.to_dict(), path=json_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(format_preflight_report(report) + "\n", encoding="utf-8")
    return json_path, md_path


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
) -> tuple[BybitAnnouncementsPreflightReport, BybitAnnouncementsRehearsalReport, tuple[Path, Path, Path, Path]]:
    base = Path(namespace_dir).expanduser()
    base.mkdir(parents=True, exist_ok=True)
    observed = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    allow_live = effective_allow_live_preflight(allow_live_preflight)
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
    exchange_announcements_path = base / event_official_exchange.EXCHANGE_ANNOUNCEMENTS_FILENAME
    official_events_path = base / event_official_exchange.OFFICIAL_EXCHANGE_EVENTS_FILENAME
    candidates_path = base / event_official_exchange.OFFICIAL_LISTING_CANDIDATES_FILENAME
    official_report_path = base / event_official_exchange.OFFICIAL_EXCHANGE_REPORT_FILENAME
    warnings: list[str] = []
    status = "skipped_live_calls_disabled"
    error_class: str | None = None
    error_message_safe: str | None = None
    items: tuple[Mapping[str, Any], ...] = ()
    official_result: event_official_exchange.OfficialExchangeScanResult | None = None
    http_successes = 0
    provider_health_status = "not_observed"
    max_pages = _max_pages()
    limit = _limit()

    if not allow_live:
        status = "skipped_live_calls_disabled"
    elif not no_send_rehearsal:
        status = "live_call_blocked_no_send_missing"
    elif max_pages <= 0 or max_pages > 3 or limit <= 0 or limit > 50:
        status = "blocked_request_budget"
        warnings.append(f"bounded_page_limit_required max_pages={max_pages} limit={limit}")
    elif not _ledger_path_writable(ledger_path):
        status = "provider_unavailable"
        error_class = "request_ledger_unwritable"
        error_message_safe = "request ledger path is not writable"
    else:
        ledger = _LedgeredBybitOpener(
            ledger_path=ledger_path,
            max_requests=max_pages,
            opener=opener,
        )
        run_id = f"bybit-announcements-rehearsal-{int(observed.timestamp())}"
        try:
            items = _fetch_live_announcement_items(ledger, max_pages=max_pages, limit=limit)
        except Exception as exc:  # noqa: BLE001 - rehearsal must fail safely
            error_class = type(exc).__name__
            error_message_safe = _safe_error_message(exc)
        ledger_rows = _read_jsonl(ledger_path)
        http_successes = sum(1 for row in ledger_rows if bool(row.get("success")))
        status, error_class, error_message_safe = _rehearsal_status_from_ledger(
            ledger_rows,
            items=items,
            fallback_error_class=error_class,
            fallback_error_message=error_message_safe,
        )
        if http_successes > 0 and status in {"live_rehearsal_success", "live_rehearsal_no_results", "live_rehearsal_partial"}:
            official_result = event_official_exchange.run_official_exchange_scan_from_items(
                namespace_dir=base,
                provider_items={PROVIDER_HEALTH_KEY: items},
                profile=profile,
                artifact_namespace=artifact_namespace,
                run_mode="no_send_rehearsal",
                run_id=run_id,
                observed_at=observed,
                warnings=warnings,
            )
        provider_health_status = _record_provider_health(
            status=status,
            provider_health_path=provider_health_path,
            now=observed,
            run_id=run_id,
            successful_ledger_rows=http_successes,
            announcements_inspected=len(items),
            official_events_written=official_result.event_count if official_result else 0,
            error_class=error_class,
            error_message=error_message_safe,
        )

    report = _build_bybit_rehearsal_report(
        allow_live=allow_live,
        no_send_rehearsal=no_send_rehearsal,
        observed=observed,
        paths={
            "ledger": ledger_path,
            "preflight_json": preflight_json,
            "preflight_md": preflight_md,
            "rehearsal_json": rehearsal_json,
            "rehearsal_md": rehearsal_md,
            "exchange_announcements": exchange_announcements_path,
            "official_events": official_events_path,
            "candidates": candidates_path,
            "official_report": official_report_path,
        },
        max_pages=max_pages,
        limit=limit,
        status=status,
        http_successes=http_successes,
        items=items,
        official_result=official_result,
        provider_health_status=provider_health_status,
        error_class=error_class,
        error_message_safe=error_message_safe,
        warnings=warnings,
    )
    payload = schema_v1.stamp_artifact_payload(report.to_dict(), schema_id="provider_preflight_v1", path=rehearsal_json)
    rehearsal_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rehearsal_md.write_text(format_rehearsal_report(report) + "\n", encoding="utf-8")
    activation_report = event_official_exchange_activation.build_activation_report(
        namespace_dir=base,
        profile=profile,
        artifact_namespace=artifact_namespace,
        observed_at=observed,
        live_call_allowed_by_provider={
            event_official_exchange_activation.PROVIDER_BYBIT_PUBLIC: report.live_call_allowed,
        },
        no_send_rehearsal_by_provider={
            event_official_exchange_activation.PROVIDER_BYBIT_PUBLIC: report.no_send,
        },
        request_ledger_path_by_provider={
            event_official_exchange_activation.PROVIDER_BYBIT_PUBLIC: ledger_path if ledger_path.exists() else None,
        },
        provider_health_status_by_key={
            PROVIDER_HEALTH_KEY: provider_health_status,
        },
        warnings=warnings,
    )
    event_official_exchange_activation.write_activation_artifacts(activation_report, base)
    return preflight, report, (preflight_json, preflight_md, rehearsal_json, rehearsal_md)


def _build_bybit_rehearsal_report(
    *,
    allow_live: bool,
    no_send_rehearsal: bool,
    observed: datetime,
    paths: Mapping[str, Path],
    max_pages: int,
    limit: int,
    status: str,
    http_successes: int,
    items: tuple[Mapping[str, Any], ...],
    official_result: event_official_exchange.OfficialExchangeScanResult | None,
    provider_health_status: str,
    error_class: str | None,
    error_message_safe: str | None,
    warnings: Iterable[str],
) -> BybitAnnouncementsRehearsalReport:
    exchange_count, event_count, candidate_count = _official_result_counts(official_result)
    requests_used = len(_read_jsonl(paths["ledger"]))
    return BybitAnnouncementsRehearsalReport(
        provider=PROVIDER_HEALTH_KEY,
        status=status,
        configured=True,
        allow_live_preflight=allow_live,
        live_call_allowed=bool(allow_live and no_send_rehearsal and requests_used > 0),
        no_send=bool(no_send_rehearsal),
        research_only=True,
        generated_at=observed.isoformat(),
        request_ledger_path=event_artifact_paths.artifact_display_path(paths["ledger"]),
        preflight_json_path=event_artifact_paths.artifact_display_path(paths["preflight_json"]),
        preflight_report_path=event_artifact_paths.artifact_display_path(paths["preflight_md"]),
        rehearsal_json_path=event_artifact_paths.artifact_display_path(paths["rehearsal_json"]),
        rehearsal_report_path=event_artifact_paths.artifact_display_path(paths["rehearsal_md"]),
        exchange_announcements_path=event_artifact_paths.artifact_display_path(paths["exchange_announcements"]),
        official_exchange_events_path=event_artifact_paths.artifact_display_path(paths["official_events"]),
        official_listing_candidates_path=event_artifact_paths.artifact_display_path(paths["candidates"]),
        official_exchange_report_path=event_artifact_paths.artifact_display_path(paths["official_report"]),
        max_pages=max_pages,
        limit=limit,
        requests_used=requests_used,
        http_successes=http_successes,
        announcements_inspected=len(items),
        exchange_announcements_written=exchange_count,
        official_events_written=event_count,
        official_listing_candidates_written=candidate_count,
        supported_params=SUPPORTED_PARAMS,
        provider_health_status=provider_health_status,
        error_class=error_class,
        error_message_safe=error_message_safe,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _official_result_counts(
    official_result: event_official_exchange.OfficialExchangeScanResult | None,
) -> tuple[int, int, int]:
    if official_result is None:
        return 0, 0, 0
    return (
        official_result.announcement_count,
        official_result.event_count,
        official_result.candidate_count,
    )


def format_preflight_report(report: BybitAnnouncementsPreflightReport) -> str:
    lines = [
        "=" * 76,
        "BYBIT OFFICIAL ANNOUNCEMENTS PREFLIGHT (research-only, no-call by default)",
        "=" * 76,
        f"provider: {report.provider}",
        f"category: {report.category}",
        f"generated_at: {report.generated_at}",
        f"configured: {str(report.configured).lower()}",
        f"preflight_status: {report.preflight_status}",
        f"smoke_mode: {str(report.smoke_mode).lower()}",
        f"live_call_allowed: {str(report.live_call_allowed).lower()}",
        f"env_vars_required: {', '.join(report.env_vars_required) or 'none'}",
        f"provider_health_key: {report.provider_health_key}",
        f"request_ledger_path: {report.request_ledger_path}",
        f"request_budget: {report.request_budget}",
        f"max_pages: {report.max_pages}",
        f"limit: {report.limit}",
        f"timeout_seconds: {report.timeout_seconds:g}",
        f"cache_ttl_seconds: {report.cache_ttl_seconds}",
        f"fixture_parser_status: {report.fixture_parser_status}",
        f"fixture_rows_observed: {report.fixture_rows_observed}",
        f"supported_params: {', '.join(report.supported_params)}",
        f"lanes_enabled_if_healthy: {', '.join(report.lanes_enabled_if_healthy)}",
        f"source_packs_enabled: {', '.join(report.source_packs_enabled)}",
        "",
        "Safety notes:",
    ]
    lines.extend(f"- {item}" for item in report.safety_notes)
    if report.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in report.warnings)
    lines.append("")
    lines.append("No provider network calls were performed by this preflight.")
    return "\n".join(lines)


def format_rehearsal_report(report: BybitAnnouncementsRehearsalReport) -> str:
    lines = [
        "# Bybit Official Announcements Bounded No-Send Rehearsal",
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
        f"http_successes: {report.http_successes}",
        f"max_pages: {report.max_pages}",
        f"limit: {report.limit}",
        f"supported_params: {', '.join(report.supported_params)}",
        f"announcements_inspected: {report.announcements_inspected}",
        f"exchange_announcements_written: {report.exchange_announcements_written}",
        f"official_events_written: {report.official_events_written}",
        f"official_listing_candidates_written: {report.official_listing_candidates_written}",
        f"provider_health_status: {report.provider_health_status}",
        f"request_ledger_path: {report.request_ledger_path}",
        f"exchange_announcements_path: {report.exchange_announcements_path}",
        f"official_exchange_events_path: {report.official_exchange_events_path}",
        f"official_listing_candidates_path: {report.official_listing_candidates_path}",
        f"official_exchange_report_path: {report.official_exchange_report_path}",
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
    if report.status == "skipped_live_calls_disabled":
        lines.append(f"next_step: rerun only with --event-alpha-bybit-announcements-allow-live-preflight or {ENV_ALLOW_LIVE_PREFLIGHT}=1 after review")
    elif report.status == "blocked_request_budget":
        lines.append(f"next_step: keep {ENV_PREFLIGHT_MAX_PAGES} <= 3 and {ENV_PREFLIGHT_LIMIT} <= 50")
    else:
        lines.append("next_step: regenerate source coverage/daily brief and run artifact doctor before any further activation.")
    return "\n".join(lines)


def effective_allow_live_preflight(value: bool = False) -> bool:
    return bool(value or str(os.getenv(ENV_ALLOW_LIVE_PREFLIGHT, "")).strip().casefold() in _TRUTHY)


def _fixture_path() -> Path | None:
    return config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH


def _fixture_parser_status(path: Path | None) -> tuple[str, int, tuple[str, ...]]:
    if path is None:
        return "not_configured", 0, ("bybit_fixture_path_not_configured",)
    source = Path(path).expanduser()
    if not source.exists():
        return "missing_fixture", 0, (f"bybit_fixture_missing:{event_artifact_paths.artifact_display_path(source)}",)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
        items = _announcement_items(payload)
    except Exception as exc:  # noqa: BLE001
        return "failed", 0, (f"bybit_fixture_parser_failed:{type(exc).__name__}",)
    return "pass", len(items), ()


def _max_pages() -> int:
    raw = os.getenv(ENV_PREFLIGHT_MAX_PAGES, "").strip()
    if raw:
        try:
            return max(0, min(3, int(raw)))
        except ValueError:
            return 0
    return 1


def _limit() -> int:
    raw = os.getenv(ENV_PREFLIGHT_LIMIT, "").strip()
    if raw:
        try:
            return max(0, min(50, int(raw)))
        except ValueError:
            return 0
    return max(1, min(50, int(config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIMIT or 20)))


def _tag() -> str:
    return str(os.getenv(ENV_PREFLIGHT_TAG, "") or "").strip()


def _ledger_path_writable(path: Path) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8"):
            pass
        return True
    except OSError:
        return False


def _fetch_live_announcement_items(
    opener: Callable[[Request, float], Any],
    *,
    max_pages: int,
    limit: int,
) -> tuple[Mapping[str, Any], ...]:
    items: list[Mapping[str, Any]] = []
    for page in range(1, max_pages + 1):
        provider = BybitAnnouncementProvider(
            None,
            live_enabled=True,
            base_url=config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_BASE_URL,
            locale=config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LOCALE,
            announcement_type=config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_TYPE,
            tag=_tag(),
            page=page,
            limit=limit,
            timeout=float(config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_TIMEOUT or 10.0),
            opener=opener,
        )
        request = Request(provider._request_url(), headers={"Accept": "application/json", "User-Agent": "crypto-rsi-scanner/1.0"})
        with opener(request, provider.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        try:
            page_items = _announcement_items(payload)
        except ValueError:
            page_items = []
        items.extend(page_items)
        if len(page_items) < limit:
            break
    return tuple(items)


def _rehearsal_status_from_ledger(
    ledger_rows: Iterable[Mapping[str, Any]],
    *,
    items: Iterable[Mapping[str, Any]],
    fallback_error_class: str | None,
    fallback_error_message: str | None,
) -> tuple[str, str | None, str | None]:
    rows = [dict(row) for row in ledger_rows if isinstance(row, Mapping)]
    item_count = len(tuple(items))
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
    if errors and item_count <= 0:
        return "provider_unavailable", str(first_error.get("error_class") or fallback_error_class or "provider_error"), str(first_error.get("error_message_safe") or fallback_error_message or "")
    if item_count > 0 and errors:
        return "live_rehearsal_partial", str(first_error.get("error_class") or "partial_failure"), str(first_error.get("error_message_safe") or "")
    if item_count > 0:
        return "live_rehearsal_success", None, None
    return "live_rehearsal_no_results", None, None


def _record_provider_health(
    *,
    status: str,
    provider_health_path: str | Path,
    now: datetime,
    run_id: str,
    successful_ledger_rows: int,
    announcements_inspected: int,
    official_events_written: int,
    error_class: str | None,
    error_message: str | None,
) -> str:
    cfg = event_provider_health.EventProviderHealthConfig(path=Path(provider_health_path), max_consecutive_failures=1)
    has_success = successful_ledger_rows > 0
    has_rows = announcements_inspected > 0 and official_events_written > 0
    if status == "live_rehearsal_success" and has_success and has_rows:
        row = event_provider_health.record_provider_success(
            PROVIDER_HEALTH_KEY,
            cfg=cfg,
            run_id=run_id,
            now=now,
            provider_service=PROVIDER_HEALTH_KEY,
            provider_role="official_announcements_no_send_rehearsal",
        )
        row["provider_coverage_status"] = "observed_healthy"
        _rewrite_provider_health_row(cfg.path, row)
        return "observed_healthy"
    if status in {"live_rehearsal_no_results", "live_rehearsal_success"} and has_success:
        row = event_provider_health.record_provider_success(
            PROVIDER_HEALTH_KEY,
            cfg=cfg,
            run_id=run_id,
            now=now,
            provider_service=PROVIDER_HEALTH_KEY,
            provider_role="official_announcements_no_send_rehearsal",
        )
        row["provider_coverage_status"] = "observed_no_results"
        _rewrite_provider_health_row(cfg.path, row)
        return "observed_no_results"
    if status in {"live_rehearsal_partial"} and has_success:
        row = event_provider_health.record_provider_success(
            PROVIDER_HEALTH_KEY,
            cfg=cfg,
            run_id=run_id,
            now=now,
            provider_service=PROVIDER_HEALTH_KEY,
            provider_role="official_announcements_no_send_rehearsal",
        )
        row["provider_coverage_status"] = "observed_partial_success"
        _rewrite_provider_health_row(cfg.path, row)
        return "observed_partial_success"
    if status in {"auth_or_access_error", "rate_limited", "provider_unavailable"}:
        row = event_provider_health.record_provider_failure(
            PROVIDER_HEALTH_KEY,
            error_class or error_message or status,
            cfg=cfg,
            run_id=run_id,
            now=now,
            provider_service=PROVIDER_HEALTH_KEY,
            provider_role="official_announcements_no_send_rehearsal",
        )
        mapped = "auth_or_access_error" if status == "auth_or_access_error" else "rate_limited" if status == "rate_limited" else "provider_unavailable"
        row["provider_coverage_status"] = mapped
        _rewrite_provider_health_row(cfg.path, row)
        return mapped
    return "not_observed"


def _rewrite_provider_health_row(path: Path, row: Mapping[str, Any]) -> None:
    rows = event_provider_health.load_provider_health(path)
    rows[str(row.get("provider_key") or PROVIDER_HEALTH_KEY)] = dict(row)
    event_provider_health.write_provider_health(path, rows)


class _LedgeredBybitOpener:
    def __init__(
        self,
        *,
        ledger_path: Path,
        max_requests: int,
        opener: Callable[[Request, float], Any] | None,
    ) -> None:
        self.ledger_path = ledger_path
        self.max_requests = max_requests
        self.opener = opener
        self.used = 0

    def __call__(self, request: Request, timeout: float) -> Any:
        before = self.max_requests - self.used
        if before <= 0:
            exc = RequestBudgetExceeded("bybit announcements request budget exceeded")
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
        return _LedgeredBybitResponse(
            response=response,
            request=request,
            ledger_path=self.ledger_path,
            started_at=started,
            budget_before=before,
            budget_after=before - 1,
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
                error=exc,
            ),
        )


class _LedgeredBybitResponse:
    def __init__(
        self,
        *,
        response: Any,
        request: Request,
        ledger_path: Path,
        started_at: datetime,
        budget_before: int,
        budget_after: int,
    ) -> None:
        self.response = response
        self.request = request
        self.ledger_path = ledger_path
        self.started_at = started_at
        self.budget_before = budget_before
        self.budget_after = budget_after
        self.payload: bytes | None = None
        self.entered: Any = None

    def __enter__(self) -> "_LedgeredBybitResponse":
        if hasattr(self.response, "__enter__"):
            self.entered = self.response.__enter__()
        else:
            self.entered = self.response
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        finished = datetime.now(timezone.utc)
        row = _ledger_row(
            self.request,
            started_at=self.started_at,
            finished_at=finished,
            budget_before=self.budget_before,
            budget_after=self.budget_after,
            success=exc is None,
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
    response: Any | None = None,
    payload: bytes | None = None,
    error: Exception | None = None,
) -> dict[str, Any]:
    parsed = urlparse(request.full_url)
    query_params = {key: value for key, value in parse_qsl(parsed.query, keep_blank_values=True)}
    unsupported = sorted(key for key in query_params if key not in SUPPORTED_PARAMS)
    return {
        "schema_version": "event_bybit_announcements_request_ledger_v1",
        "provider": PROVIDER_HEALTH_KEY,
        "endpoint": parsed.path,
        "sanitized_url": _sanitized_url(request.full_url),
        "method": getattr(request, "method", None) or request.get_method(),
        "started_at": started_at.astimezone(timezone.utc).isoformat(),
        "finished_at": finished_at.astimezone(timezone.utc).isoformat(),
        "duration_ms": max(0, int((finished_at - started_at).total_seconds() * 1000)),
        "status_code": _status_code(response, error),
        "success": bool(success),
        "result_count": _result_count(payload),
        "query_params": query_params,
        "unsupported_query_params": unsupported,
        "error_class": type(error).__name__ if error else None,
        "error_message_safe": _safe_error_message(error),
        "request_budget_before": budget_before,
        "request_budget_after": budget_after,
        "live_call_allowed": True,
        "no_send_rehearsal": True,
        "token_redacted": True,
    }


def _append_ledger_row(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(dict(row), sort_keys=True) + "\n")


def _sanitized_url(url: str) -> str:
    parsed = urlparse(url)
    query = urlencode([(key, "<redacted>" if _secret_param(key) else value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)])
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
        return len(_announcement_items(parsed))
    except Exception:
        return None


def _safe_error_message(error: Exception | None) -> str | None:
    if error is None:
        return None
    if isinstance(error, HTTPError):
        return f"HTTP {error.code}: {error.reason}"[:240]
    if isinstance(error, URLError):
        return f"URL error: {error.reason}"[:240]
    return str(error)[:240]


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


def artifact_conflicts(namespace_dir: str | Path | None) -> dict[str, int]:
    out = {
        "bybit_announcements_preflight_secret_leak": 0,
        "bybit_announcements_preflight_live_call_allowed_in_smoke": 0,
        "bybit_announcements_preflight_missing_fixture_parser_status": 0,
        "bybit_announcements_rehearsal_secret_leak": 0,
        "bybit_announcements_rehearsal_live_without_ledger": 0,
        "bybit_announcements_rehearsal_live_without_explicit_allow": 0,
        "bybit_announcements_rehearsal_unsupported_params": 0,
        "bybit_announcements_rehearsal_forbidden_side_effect_claim": 0,
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
        out["bybit_announcements_preflight_secret_leak"] = 1
        out["bybit_announcements_rehearsal_secret_leak"] = 1
    preflight = _read_json(base / PREFLIGHT_JSON)
    if preflight:
        if bool(preflight.get("smoke_mode")) and bool(preflight.get("live_call_allowed")):
            out["bybit_announcements_preflight_live_call_allowed_in_smoke"] = 1
        if not str(preflight.get("fixture_parser_status") or "").strip():
            out["bybit_announcements_preflight_missing_fixture_parser_status"] = 1
    rehearsal = _read_json(base / REHEARSAL_JSON)
    ledger_rows = _read_jsonl(base / REQUEST_LEDGER)
    if rehearsal:
        live_allowed = bool(rehearsal.get("live_call_allowed"))
        if live_allowed and not ledger_rows:
            out["bybit_announcements_rehearsal_live_without_ledger"] = 1
        if live_allowed and not bool(rehearsal.get("allow_live_preflight")):
            out["bybit_announcements_rehearsal_live_without_explicit_allow"] = 1
        for key in (
            "strict_alerts_created",
            "telegram_sends",
            "trades_created",
            "paper_trades_created",
            "normal_rsi_signal_rows_written",
            "triggered_fade_created",
        ):
            if int(rehearsal.get(key) or 0) != 0:
                out["bybit_announcements_rehearsal_forbidden_side_effect_claim"] = 1
    for row in ledger_rows:
        unsupported = row.get("unsupported_query_params")
        if unsupported:
            out["bybit_announcements_rehearsal_unsupported_params"] += len(unsupported) if isinstance(unsupported, list) else 1
    if re.search(r"(?i)\b(send telegram|paper trade|live trade|execute order|triggered_fade created)\b", text):
        out["bybit_announcements_rehearsal_forbidden_side_effect_claim"] = 1
    return out


def _read_json(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        return {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, Mapping) else {}


def _secret_like(text: str) -> bool:
    return bool(re.search(r"(?i)(api[_-]?key|secret|token|authorization|bearer)\s*[=:]\s*['\"][A-Za-z0-9._-]{20,}['\"]", text))
