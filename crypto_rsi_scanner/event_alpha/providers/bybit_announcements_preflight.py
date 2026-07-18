"""Bybit official-announcement preflight and bounded no-send rehearsal.

This module is deliberately research-only. The default preflight validates local
fixture/parser readiness and writes operator artifacts without network calls.
Live HTTP rehearsal requires the provider-specific environment gate, no-send
mode, a small page/limit budget, and a request ledger. A CLI/API allow boolean
may only accompany the environment gate as operator confirmation.
"""

from __future__ import annotations

import hashlib
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
from ...event_providers._announcement_common import (
    _announcement_items,
    _announcement_items_with_acquisition_time,
)
from ...event_providers.bybit_announcements import (
    BybitAnnouncementProvider,
    bybit_failure_message,
    bybit_request_id,
    bybit_response_diagnostics,
    build_bybit_public_request,
    classify_bybit_failure,
    raise_for_bybit_api_error,
    read_bounded_bybit_response,
)
from ..artifacts import paths as event_artifact_paths
from ..artifacts import schema_v1
from ..operations.market_no_send_io import write_bytes_immutable
from . import official_exchange as event_official_exchange
from . import official_exchange_activation as event_official_exchange_activation
from . import provider_health as event_provider_health
from . import request_lineage as event_request_lineage
from . import bybit_announcements_preflight_conflicts as preflight_conflict_checks
from . import bybit_announcements_preflight_render as preflight_render


PREFLIGHT_JSON = "event_bybit_announcements_preflight.json"
PREFLIGHT_MD = "event_bybit_announcements_preflight.md"
REQUEST_LEDGER = "event_bybit_announcements_request_ledger.jsonl"
ACCEPTED_SOURCE_PREFIX = "event_bybit_announcements_source_"
ACCEPTED_SOURCE_SUFFIX = ".json"
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
_ACCEPTED_SOURCE_NAME_RE = re.compile(
    rf"^{re.escape(ACCEPTED_SOURCE_PREFIX)}[0-9a-f]{{24}}{re.escape(ACCEPTED_SOURCE_SUFFIX)}$"
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


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
    accepted_source_response_count: int
    accepted_source_artifacts: tuple[str, ...]
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
    provider_generation_id: str = ""
    run_id: str = ""

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
        "accepted_source_response_count": report.accepted_source_response_count,
        "accepted_source_artifacts": list(report.accepted_source_artifacts),
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
        "provider_generation_id": report.provider_generation_id,
        "run_id": report.run_id,
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
            f"no live calls unless {ENV_ALLOW_LIVE_PREFLIGHT}=1 already exists in the environment; "
            "the CLI allow flag may only accompany that provider-specific gate",
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
    acquisition_clock: Callable[[], datetime] | None = None,
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

    paths = _bybit_rehearsal_artifact_paths(
        base,
        preflight_json=preflight_json,
        preflight_md=preflight_md,
    )
    ledger_path = paths["ledger"]
    rehearsal_json = paths["rehearsal_json"]
    rehearsal_md = paths["rehearsal_md"]
    exchange_announcements_path = paths["exchange_announcements"]
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
    generation_id = event_request_lineage.provider_generation_id(PROVIDER_HEALTH_KEY, observed)
    run_id = (
        f"bybit-announcements-rehearsal-{int(observed.timestamp() * 1_000_000)}-"
        f"{generation_id.rsplit(':', 1)[-1]}"
    )

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
            provider_generation_id=generation_id,
            run_id=run_id,
            profile=profile,
            artifact_namespace=artifact_namespace,
        )
        try:
            items = _fetch_live_announcement_items(
                ledger,
                max_pages=max_pages,
                limit=limit,
                acquisition_clock=acquisition_clock,
            )
        except Exception as exc:  # noqa: BLE001 - rehearsal must fail safely
            error_class = type(exc).__name__
            error_message_safe = _safe_error_message(exc)
        ledger_rows = event_request_lineage.generation_rows(_read_jsonl(ledger_path), generation_id)
        http_successes = sum(1 for row in ledger_rows if bool(row.get("success")))
        status, error_class, error_message_safe = _rehearsal_status_from_ledger(
            ledger_rows,
            items=items,
            fallback_error_class=error_class,
            fallback_error_message=error_message_safe,
        )
        if http_successes > 0 and status in {"live_rehearsal_success", "live_rehearsal_no_results", "live_rehearsal_partial"}:
            items = _bind_rehearsal_item_lineage(
                items,
                generation_id=generation_id,
                exchange_announcements_path=exchange_announcements_path,
                ledger_path=ledger_path,
            )
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
        paths=paths,
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
        generation_id=generation_id,
        run_id=run_id,
    )
    payload = schema_v1.stamp_artifact_payload(report.to_dict(), schema_id="provider_preflight_v1", path=rehearsal_json)
    rehearsal_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rehearsal_md.write_text(format_rehearsal_report(report) + "\n", encoding="utf-8")
    _write_bybit_activation_artifacts(
        base=base,
        profile=profile,
        artifact_namespace=artifact_namespace,
        observed=observed,
        report=report,
        paths=paths,
        provider_health_status=provider_health_status,
        warnings=warnings,
    )
    return preflight, report, (preflight_json, preflight_md, rehearsal_json, rehearsal_md)


def _bind_rehearsal_item_lineage(
    items: Iterable[Mapping[str, Any]],
    *,
    generation_id: str,
    exchange_announcements_path: Path,
    ledger_path: Path,
) -> tuple[Mapping[str, Any], ...]:
    fallback_source = event_artifact_paths.artifact_display_path(
        exchange_announcements_path
    )
    ledger_display = event_artifact_paths.artifact_display_path(ledger_path)
    return tuple(
        {
            **dict(item),
            "provider_generation_id": generation_id,
            "provider_request_succeeded": True,
            "provider_source_artifact": item.get("provider_source_artifact")
            or fallback_source,
            "request_ledger_path": ledger_display,
        }
        for item in items
    )


def _bybit_rehearsal_artifact_paths(
    base: Path,
    *,
    preflight_json: Path,
    preflight_md: Path,
) -> dict[str, Path]:
    return {
        "ledger": base / REQUEST_LEDGER,
        "preflight_json": preflight_json,
        "preflight_md": preflight_md,
        "rehearsal_json": base / REHEARSAL_JSON,
        "rehearsal_md": base / REHEARSAL_MD,
        "exchange_announcements": base / event_official_exchange.EXCHANGE_ANNOUNCEMENTS_FILENAME,
        "official_events": base / event_official_exchange.OFFICIAL_EXCHANGE_EVENTS_FILENAME,
        "candidates": base / event_official_exchange.OFFICIAL_LISTING_CANDIDATES_FILENAME,
        "official_report": base / event_official_exchange.OFFICIAL_EXCHANGE_REPORT_FILENAME,
    }


def _write_bybit_activation_artifacts(
    *,
    base: Path,
    profile: str | None,
    artifact_namespace: str | None,
    observed: datetime,
    report: BybitAnnouncementsRehearsalReport,
    paths: Mapping[str, Path],
    provider_health_status: str,
    warnings: Iterable[str],
) -> None:
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
            event_official_exchange_activation.PROVIDER_BYBIT_PUBLIC: (
                paths["ledger"] if paths["ledger"].exists() else None
            ),
        },
        provider_health_status_by_key={
            PROVIDER_HEALTH_KEY: provider_health_status,
        },
        warnings=warnings,
    )
    event_official_exchange_activation.write_activation_artifacts(activation_report, base)


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
    generation_id: str,
    run_id: str,
) -> BybitAnnouncementsRehearsalReport:
    exchange_count, event_count, candidate_count = _official_result_counts(official_result)
    generation_rows = event_request_lineage.generation_rows(
        _read_jsonl(paths["ledger"]), generation_id
    )
    requests_used = len(generation_rows)
    accepted_source_artifacts = tuple(
        str(row.get("accepted_source_artifact") or "")
        for row in generation_rows
        if bool(row.get("success")) and row.get("accepted_source_artifact")
    )
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
        accepted_source_response_count=len(accepted_source_artifacts),
        accepted_source_artifacts=accepted_source_artifacts,
        announcements_inspected=len(items),
        exchange_announcements_written=exchange_count,
        official_events_written=event_count,
        official_listing_candidates_written=candidate_count,
        supported_params=SUPPORTED_PARAMS,
        provider_health_status=provider_health_status,
        error_class=error_class,
        error_message_safe=error_message_safe,
        warnings=tuple(dict.fromkeys(warnings)),
        provider_generation_id=generation_id,
        run_id=run_id,
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
    return preflight_render.format_preflight_report(report)


def format_rehearsal_report(report: BybitAnnouncementsRehearsalReport) -> str:
    return preflight_render.format_rehearsal_report(
        report,
        env_allow_live_preflight=ENV_ALLOW_LIVE_PREFLIGHT,
        env_preflight_max_pages=ENV_PREFLIGHT_MAX_PAGES,
        env_preflight_limit=ENV_PREFLIGHT_LIMIT,
    )


def effective_allow_live_preflight(value: bool = False) -> bool:
    # A CLI/API boolean is never sufficient authority for a provider call. The
    # provider-specific environment gate must already be present so copied CLI
    # commands and generic dispatch cannot accidentally broaden live access.
    del value
    return str(os.getenv(ENV_ALLOW_LIVE_PREFLIGHT, "")).strip().casefold() in _TRUTHY


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
    acquisition_clock: Callable[[], datetime] | None = None,
) -> tuple[Mapping[str, Any], ...]:
    clock = acquisition_clock or (lambda: datetime.now(timezone.utc))
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
        request = build_bybit_public_request(provider._request_url())
        with opener(request, provider.timeout) as response:
            response_bytes = response.read()
            acquired_at = clock()
            payload = json.loads(response_bytes.decode("utf-8"))
            raise_for_bybit_api_error(payload)
        try:
            page_items = _announcement_items_with_acquisition_time(
                _announcement_items(payload),
                acquired_at=acquired_at,
            )
        except ValueError:
            page_items = ()
        source_artifact = str(
            getattr(response, "accepted_source_artifact", "") or ""
        )
        source_sha256 = str(
            getattr(response, "accepted_source_sha256", "") or ""
        )
        items.extend(
            {
                **dict(item),
                "provider_source_artifact": source_artifact or None,
                "provider_source_sha256": source_sha256 or None,
                "provider_source_page": page,
                "provider_source_immutable": bool(source_artifact),
            }
            for item in page_items
        )
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
    diagnostic_text = _ledger_error_diagnostic_text(errors)
    error_class = str(first_error.get("error_class") or "HTTPError")
    error_message = bybit_failure_message(first_error)
    classified = classify_bybit_failure(status_codes, diagnostic_text)
    if classified:
        return classified, error_class, error_message
    if any(str(row.get("error_class") or "") == "RequestBudgetExceeded" for row in errors):
        return "blocked_request_budget", "RequestBudgetExceeded", str(first_error.get("error_message_safe") or "")
    if errors and item_count <= 0:
        return "provider_unavailable", str(first_error.get("error_class") or fallback_error_class or "provider_error"), str(first_error.get("error_message_safe") or fallback_error_message or "")
    if item_count > 0 and errors:
        return "live_rehearsal_partial", str(first_error.get("error_class") or "partial_failure"), str(first_error.get("error_message_safe") or "")
    if item_count > 0:
        return "live_rehearsal_success", None, None
    return "live_rehearsal_no_results", None, None


def _ledger_error_diagnostic_text(rows: Iterable[Mapping[str, Any]]) -> str:
    return " ".join(
        " ".join((
            str(row.get("error_message_safe") or ""),
            str(row.get("response_body_summary_redacted") or ""),
        ))
        for row in rows
    ).casefold()


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
    if status in {
        "auth_or_access_error",
        "edge_forbidden",
        "rate_limited",
        "region_restricted",
        "provider_unavailable",
    }:
        row = event_provider_health.record_provider_failure(
            PROVIDER_HEALTH_KEY,
            error_class or error_message or status,
            cfg=cfg,
            run_id=run_id,
            now=now,
            provider_service=PROVIDER_HEALTH_KEY,
            provider_role="official_announcements_no_send_rehearsal",
        )
        mapped = status
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
        provider_generation_id: str = "",
        run_id: str = "",
        profile: str | None = None,
        artifact_namespace: str | None = None,
    ) -> None:
        self.ledger_path = ledger_path
        self.max_requests = max_requests
        self.opener = opener
        self.provider_generation_id = provider_generation_id
        self.run_id = run_id
        self.profile = profile
        self.artifact_namespace = artifact_namespace
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
            provider_generation_id=self.provider_generation_id,
            run_id=self.run_id,
            profile=self.profile,
            artifact_namespace=self.artifact_namespace,
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
                provider_generation_id=self.provider_generation_id,
                run_id=self.run_id,
                profile=self.profile,
                artifact_namespace=self.artifact_namespace,
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
        provider_generation_id: str,
        run_id: str,
        profile: str | None,
        artifact_namespace: str | None,
    ) -> None:
        self.response = response
        self.request = request
        self.ledger_path = ledger_path
        self.started_at = started_at
        self.budget_before = budget_before
        self.budget_after = budget_after
        self.provider_generation_id = provider_generation_id
        self.run_id = run_id
        self.profile = profile
        self.artifact_namespace = artifact_namespace
        self.payload: bytes | None = None
        self.entered: Any = None
        self.accepted_source_artifact: str | None = None
        self.accepted_source_sha256: str | None = None
        self.accepted_source_size_bytes: int | None = None

    def __enter__(self) -> "_LedgeredBybitResponse":
        if hasattr(self.response, "__enter__"):
            self.entered = self.response.__enter__()
        else:
            self.entered = self.response
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return _finish_ledgered_bybit_response(self, exc_type, exc, tb)

    def read(self) -> bytes:
        target = self.entered or self.response
        raw = read_bounded_bybit_response(target)
        self.payload = raw
        return raw


def _finish_ledgered_bybit_response(
    wrapped: _LedgeredBybitResponse,
    exc_type: Any,
    exc: Any,
    tb: Any,
) -> bool:
    finished = datetime.now(timezone.utc)
    persistence_error: Exception | None = None
    if exc is None and wrapped.payload is not None:
        try:
            artifact, digest, size = _persist_accepted_source_response(
                wrapped.ledger_path.parent,
                request=wrapped.request,
                payload=wrapped.payload,
            )
            wrapped.accepted_source_artifact = artifact
            wrapped.accepted_source_sha256 = digest
            wrapped.accepted_source_size_bytes = size
        except Exception as source_exc:  # noqa: BLE001 - fail the rehearsal closed
            persistence_error = source_exc
    effective_error = exc if isinstance(exc, Exception) else persistence_error
    row = _ledger_row(
        wrapped.request,
        started_at=wrapped.started_at,
        finished_at=finished,
        budget_before=wrapped.budget_before,
        budget_after=wrapped.budget_after,
        success=exc is None and persistence_error is None,
        response=wrapped.entered or wrapped.response,
        payload=wrapped.payload,
        error=effective_error,
        accepted_source_artifact=wrapped.accepted_source_artifact,
        accepted_source_sha256=wrapped.accepted_source_sha256,
        accepted_source_size_bytes=wrapped.accepted_source_size_bytes,
        provider_generation_id=wrapped.provider_generation_id,
        run_id=wrapped.run_id,
        profile=wrapped.profile,
        artifact_namespace=wrapped.artifact_namespace,
    )
    _append_ledger_row(wrapped.ledger_path, row)
    suppressed = False
    if hasattr(wrapped.response, "__exit__"):
        suppressed = bool(wrapped.response.__exit__(exc_type, exc, tb))
    if persistence_error is not None:
        raise persistence_error
    return suppressed


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
    accepted_source_artifact: str | None = None,
    accepted_source_sha256: str | None = None,
    accepted_source_size_bytes: int | None = None,
    provider_generation_id: str = "",
    run_id: str = "",
    profile: str | None = None,
    artifact_namespace: str | None = None,
) -> dict[str, Any]:
    parsed = urlparse(request.full_url)
    query_params = {key: value for key, value in parse_qsl(parsed.query, keep_blank_values=True)}
    unsupported = sorted(key for key in query_params if key not in SUPPORTED_PARAMS)
    response_diagnostics = bybit_response_diagnostics(response=response, payload=payload, error=error)
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
        "request_id": bybit_request_id(request),
        "accepted_source_artifact": accepted_source_artifact,
        "accepted_source_sha256": accepted_source_sha256,
        "accepted_source_size_bytes": accepted_source_size_bytes,
        "accepted_source_immutable": bool(accepted_source_artifact),
        **response_diagnostics,
        "request_budget_before": budget_before,
        "request_budget_after": budget_after,
        "live_call_allowed": True,
        "no_send_rehearsal": True,
        "token_redacted": True,
        "provider_generation_id": provider_generation_id,
        "run_id": run_id,
        "profile": profile,
        "artifact_namespace": artifact_namespace,
    }


def _persist_accepted_source_response(
    namespace_dir: Path,
    *,
    request: Request,
    payload: bytes,
) -> tuple[str, str, int]:
    request_id = str(bybit_request_id(request) or "")
    identity = hashlib.sha256(
        (f"{_sanitized_url(request.full_url)}\0{request_id}").encode("utf-8")
    ).hexdigest()[:24]
    filename = f"{ACCEPTED_SOURCE_PREFIX}{identity}{ACCEPTED_SOURCE_SUFFIX}"
    raw = bytes(payload)
    write_bytes_immutable(namespace_dir / filename, raw)
    return filename, hashlib.sha256(raw).hexdigest(), len(raw)


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
    return preflight_conflict_checks.artifact_conflicts(
        namespace_dir,
        preflight_json=PREFLIGHT_JSON,
        preflight_md=PREFLIGHT_MD,
        rehearsal_json=REHEARSAL_JSON,
        rehearsal_md=REHEARSAL_MD,
        request_ledger=REQUEST_LEDGER,
        accepted_source_prefix=ACCEPTED_SOURCE_PREFIX,
        accepted_source_suffix=ACCEPTED_SOURCE_SUFFIX,
        accepted_source_name_re=_ACCEPTED_SOURCE_NAME_RE,
        sha256_re=_SHA256_RE,
        read_jsonl=_read_jsonl,
    )
