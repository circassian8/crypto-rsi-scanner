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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from . import config, event_artifact_paths
from .derivatives_providers.coinalyze import CoinalyzeDerivativesProvider, resolve_future_market_symbols


PREFLIGHT_JSON = "event_coinalyze_preflight.json"
PREFLIGHT_MD = "event_coinalyze_preflight.md"
REHEARSAL_MD = "event_coinalyze_rehearsal_report.md"
REQUEST_LEDGER = "event_coinalyze_request_ledger.jsonl"
ENV_API_KEY = "RSI_EVENT_DISCOVERY_COINALYZE_API_KEY"
PROVIDER_HEALTH_KEY = "coinalyze"
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
    configured = bool(os.getenv(ENV_API_KEY, "").strip() or config.EVENT_DISCOVERY_COINALYZE_API_KEY)
    live_allowed = bool(allow_live_preflight and configured and not smoke_mode)
    fixture_path = _fixture_path()
    fixture_parser_status, fixture_symbols, parser_warnings = _fixture_parser_status(fixture_path)
    symbol_status = _fixture_symbol_mapping_status(fixture_symbols)
    if smoke_mode:
        status = "fixture_ready" if fixture_parser_status == "pass" else "fixture_parser_failed"
    elif not configured:
        status = "missing_config"
    elif not allow_live_preflight:
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
        max_requests_per_run=2 if live_allowed else 0,
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
        warnings=tuple(parser_warnings),
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


def artifact_conflicts(namespace_dir: str | Path | None) -> dict[str, int]:
    out = {
        "coinalyze_preflight_secret_leak": 0,
        "coinalyze_preflight_live_call_allowed_in_smoke": 0,
        "coinalyze_preflight_configured_missing_env": 0,
        "coinalyze_preflight_ready_without_request_ledger": 0,
        "coinalyze_preflight_missing_fixture_parser_status": 0,
        "coinalyze_preflight_forbidden_side_effect_claim": 0,
    }
    if namespace_dir is None:
        return out
    base = Path(namespace_dir)
    paths = [base / PREFLIGHT_JSON, base / PREFLIGHT_MD]
    existing = [path for path in paths if path.exists()]
    if not existing:
        return out
    text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in existing)
    if _secret_like(text):
        out["coinalyze_preflight_secret_leak"] = 1
    data: Mapping[str, Any] = {}
    try:
        parsed = json.loads((base / PREFLIGHT_JSON).read_text(encoding="utf-8"))
        if isinstance(parsed, Mapping):
            data = parsed
    except (OSError, json.JSONDecodeError):
        data = {}
    if bool(data.get("smoke_mode")) and bool(data.get("live_call_allowed")):
        out["coinalyze_preflight_live_call_allowed_in_smoke"] = 1
    if bool(data.get("configured")) and not (os.getenv(ENV_API_KEY, "").strip() or config.EVENT_DISCOVERY_COINALYZE_API_KEY):
        out["coinalyze_preflight_configured_missing_env"] = 1
    if str(data.get("preflight_status") or "") in {"ready_for_no_send_rehearsal", "ready_for_no_send_live_rehearsal"} and not str(data.get("request_ledger_path") or "").strip():
        out["coinalyze_preflight_ready_without_request_ledger"] = 1
    if not str(data.get("fixture_parser_status") or "").strip():
        out["coinalyze_preflight_missing_fixture_parser_status"] = 1
    if re.search(r"(?i)\b(send telegram|paper trade|live trade|execute order|triggered_fade created)\b", text):
        out["coinalyze_preflight_forbidden_side_effect_claim"] = 1
    return out


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
