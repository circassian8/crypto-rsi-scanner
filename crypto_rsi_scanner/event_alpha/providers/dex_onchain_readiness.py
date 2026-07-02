"""DEX/on-chain/protocol fundamentals readiness artifacts for Event Alpha.

This module is fixture/parser only by default. It prepares DEX-native liquidity,
pool-volume, and protocol-fundamental rows for later controlled activation, but
it never makes provider network calls, sends notifications, trades, paper
trades, writes normal RSI rows, executes orders, or creates ``TRIGGERED_FADE``.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from ... import config
from ..artifacts import paths as event_artifact_paths


READINESS_JSON = "event_dex_onchain_readiness.json"
READINESS_MD = "event_dex_onchain_readiness.md"
REQUEST_LEDGER = "event_dex_onchain_request_ledger.jsonl"
DEX_POOL_STATE_FILENAME = "event_dex_pool_state.jsonl"
DEX_POOL_ANOMALIES_FILENAME = "event_dex_pool_anomalies.jsonl"
PROTOCOL_FUNDAMENTALS_FILENAME = "event_protocol_fundamentals.jsonl"
ENV_ALLOW_LIVE_PREFLIGHT = "RSI_EVENT_ALPHA_DEX_ONCHAIN_ALLOW_LIVE_PREFLIGHT"
DEFAULT_NAMESPACE = "dex_onchain_readiness"

DEX_LIQUIDITY_EXPANSION = "dex_liquidity_expansion"
DEX_VOLUME_BREAKOUT = "dex_volume_breakout"
SUSPICIOUS_LOW_LIQUIDITY_PUMP = "suspicious_low_liquidity_pump"
PROTOCOL_REVENUE_TVL_GROWTH = "protocol_revenue_tvl_growth"
PROTOCOL_FUNDAMENTALS_DETERIORATION = "protocol_fundamentals_deterioration"

_TRUTHY = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class DexOnchainProviderReadinessRow:
    provider: str
    family: str
    configured: bool
    env_vars_required: tuple[str, ...]
    fixture_parser_status: str
    live_call_allowed: bool
    no_send_rehearsal: bool
    request_ledger_path: str
    max_requests_per_run: int
    supported_event_types: tuple[str, ...]
    source_packs_enabled: tuple[str, ...]
    provider_health_key: str
    fixture_path: str | None
    fixture_rows_observed: int
    normalized_rows_written: int
    anomaly_rows_written: int
    protocol_rows_written: int
    parser_error_safe: str | None = None
    strict_alerts_created: int = 0
    telegram_sends: int = 0
    trades_created: int = 0
    paper_trades_created: int = 0
    normal_rsi_signal_rows_written: int = 0
    triggered_fade_created: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "family": self.family,
            "configured": self.configured,
            "env_vars_required": list(self.env_vars_required),
            "fixture_parser_status": self.fixture_parser_status,
            "live_call_allowed": self.live_call_allowed,
            "no_send_rehearsal": self.no_send_rehearsal,
            "request_ledger_path": self.request_ledger_path,
            "max_requests_per_run": self.max_requests_per_run,
            "supported_event_types": list(self.supported_event_types),
            "source_packs_enabled": list(self.source_packs_enabled),
            "provider_health_key": self.provider_health_key,
            "fixture_path": self.fixture_path,
            "fixture_rows_observed": self.fixture_rows_observed,
            "normalized_rows_written": self.normalized_rows_written,
            "anomaly_rows_written": self.anomaly_rows_written,
            "protocol_rows_written": self.protocol_rows_written,
            "parser_error_safe": self.parser_error_safe,
            "strict_alerts_created": self.strict_alerts_created,
            "telegram_sends": self.telegram_sends,
            "trades_created": self.trades_created,
            "paper_trades_created": self.paper_trades_created,
            "normal_rsi_signal_rows_written": self.normal_rsi_signal_rows_written,
            "triggered_fade_created": self.triggered_fade_created,
        }


@dataclass(frozen=True)
class DexOnchainReadinessReport:
    profile: str | None
    artifact_namespace: str | None
    generated_at: str
    readiness_status: str
    configured: bool
    allow_live_preflight: bool
    live_call_allowed: bool
    no_send_rehearsal: bool
    research_only: bool
    smoke_mode: bool
    request_ledger_path: str
    dex_pool_state_path: str
    dex_pool_anomalies_path: str
    protocol_fundamentals_path: str
    provider_rows: tuple[DexOnchainProviderReadinessRow, ...]
    dex_pool_state_rows: int
    dex_pool_anomaly_rows: int
    protocol_fundamental_rows: int
    classification_counts: Mapping[str, int]
    warnings: tuple[str, ...] = ()
    strict_alerts_created: int = 0
    telegram_sends: int = 0
    trades_created: int = 0
    paper_trades_created: int = 0
    normal_rsi_signal_rows_written: int = 0
    triggered_fade_created: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "event_dex_onchain_readiness_v1",
            "row_type": "event_dex_onchain_readiness",
            "profile": self.profile,
            "artifact_namespace": self.artifact_namespace,
            "generated_at": self.generated_at,
            "readiness_status": self.readiness_status,
            "preflight_status": self.readiness_status,
            "configured": self.configured,
            "allow_live_preflight": self.allow_live_preflight,
            "live_call_allowed": self.live_call_allowed,
            "no_send_rehearsal": self.no_send_rehearsal,
            "research_only": self.research_only,
            "smoke_mode": self.smoke_mode,
            "request_ledger_path": self.request_ledger_path,
            "dex_pool_state_path": self.dex_pool_state_path,
            "dex_pool_anomalies_path": self.dex_pool_anomalies_path,
            "protocol_fundamentals_path": self.protocol_fundamentals_path,
            "providers": [row.to_dict() for row in self.provider_rows],
            "provider_rows": [row.to_dict() for row in self.provider_rows],
            "dex_pool_state_rows": self.dex_pool_state_rows,
            "dex_pool_anomaly_rows": self.dex_pool_anomaly_rows,
            "protocol_fundamental_rows": self.protocol_fundamental_rows,
            "classification_counts": dict(self.classification_counts),
            "warnings": list(self.warnings),
            "strict_alerts_created": self.strict_alerts_created,
            "telegram_sends": self.telegram_sends,
            "trades_created": self.trades_created,
            "paper_trades_created": self.paper_trades_created,
            "normal_rsi_signal_rows_written": self.normal_rsi_signal_rows_written,
            "triggered_fade_created": self.triggered_fade_created,
        }


@dataclass(frozen=True)
class DexOnchainReadinessResult:
    namespace_dir: Path
    readiness_json_path: Path
    readiness_md_path: Path
    dex_pool_state_path: Path
    dex_pool_anomalies_path: Path
    protocol_fundamentals_path: Path
    report: DexOnchainReadinessReport
    dex_pool_state_rows: tuple[dict[str, Any], ...]
    dex_pool_anomaly_rows: tuple[dict[str, Any], ...]
    protocol_fundamental_rows: tuple[dict[str, Any], ...]


def run_dex_onchain_readiness(
    *,
    namespace_dir: str | Path,
    profile: str | None = None,
    artifact_namespace: str | None = None,
    geckoterminal_path: str | Path | None = None,
    coingecko_dex_path: str | Path | None = None,
    defillama_path: str | Path | None = None,
    smoke_mode: bool = False,
    allow_live_preflight: bool = False,
    now: datetime | None = None,
) -> DexOnchainReadinessResult:
    """Write DEX/on-chain readiness and normalized fixture artifacts."""
    base = Path(namespace_dir).expanduser()
    base.mkdir(parents=True, exist_ok=True)
    observed = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    specs = _provider_specs(
        namespace_dir=base,
        geckoterminal_path=geckoterminal_path,
        coingecko_dex_path=coingecko_dex_path,
        defillama_path=defillama_path,
    )
    state_rows: list[dict[str, Any]] = []
    anomaly_rows: list[dict[str, Any]] = []
    protocol_rows: list[dict[str, Any]] = []
    provider_rows: list[DexOnchainProviderReadinessRow] = []
    warnings: list[str] = []
    for spec in specs:
        row, dex_rows, protocol_provider_rows, provider_warnings = _provider_readiness_row(
            spec,
            observed_at=observed,
            profile=profile,
            artifact_namespace=artifact_namespace,
        )
        provider_rows.append(row)
        state_rows.extend(dex_rows)
        protocol_rows.extend(protocol_provider_rows)
        warnings.extend(provider_warnings)
    anomaly_rows = _classify_dex_anomalies(
        state_rows,
        profile=profile,
        artifact_namespace=artifact_namespace,
        observed_at=observed,
    )
    protocol_rows = [
        _with_protocol_classification(row, profile=profile, artifact_namespace=artifact_namespace, observed_at=observed)
        for row in protocol_rows
    ]
    provider_rows = [
        _replace_provider_counts(row, state_rows=state_rows, anomalies=anomaly_rows, protocol_rows=protocol_rows)
        for row in provider_rows
    ]
    allow_live = effective_allow_live_preflight(allow_live_preflight)
    if allow_live:
        warnings.append("live_dex_onchain_fetch_not_implemented_fixture_only")
    status = _readiness_status(provider_rows)
    classification_counts = _classification_counts((*anomaly_rows, *protocol_rows))
    state_path = base / DEX_POOL_STATE_FILENAME
    anomaly_path = base / DEX_POOL_ANOMALIES_FILENAME
    protocol_path = base / PROTOCOL_FUNDAMENTALS_FILENAME
    _write_jsonl(state_path, state_rows)
    _write_jsonl(anomaly_path, anomaly_rows)
    _write_jsonl(protocol_path, protocol_rows)
    report = DexOnchainReadinessReport(
        profile=profile,
        artifact_namespace=artifact_namespace,
        generated_at=observed.isoformat(),
        readiness_status=status,
        configured=any(row.configured for row in provider_rows),
        allow_live_preflight=allow_live,
        live_call_allowed=False,
        no_send_rehearsal=True,
        research_only=True,
        smoke_mode=bool(smoke_mode),
        request_ledger_path=event_artifact_paths.artifact_display_path(base / REQUEST_LEDGER),
        dex_pool_state_path=event_artifact_paths.artifact_display_path(state_path),
        dex_pool_anomalies_path=event_artifact_paths.artifact_display_path(anomaly_path),
        protocol_fundamentals_path=event_artifact_paths.artifact_display_path(protocol_path),
        provider_rows=tuple(provider_rows),
        dex_pool_state_rows=len(state_rows),
        dex_pool_anomaly_rows=len(anomaly_rows),
        protocol_fundamental_rows=len(protocol_rows),
        classification_counts=classification_counts,
        warnings=tuple(dict.fromkeys(str(warning) for warning in warnings if str(warning))),
    )
    json_path, md_path = write_readiness_artifacts(report, base)
    return DexOnchainReadinessResult(
        namespace_dir=base,
        readiness_json_path=json_path,
        readiness_md_path=md_path,
        dex_pool_state_path=state_path,
        dex_pool_anomalies_path=anomaly_path,
        protocol_fundamentals_path=protocol_path,
        report=report,
        dex_pool_state_rows=tuple(state_rows),
        dex_pool_anomaly_rows=tuple(anomaly_rows),
        protocol_fundamental_rows=tuple(protocol_rows),
    )


def build_readiness_report(
    *,
    namespace_dir: str | Path,
    profile: str | None = None,
    artifact_namespace: str | None = None,
    geckoterminal_path: str | Path | None = None,
    coingecko_dex_path: str | Path | None = None,
    defillama_path: str | Path | None = None,
    smoke_mode: bool = False,
    allow_live_preflight: bool = False,
    now: datetime | None = None,
) -> DexOnchainReadinessReport:
    result = run_dex_onchain_readiness(
        namespace_dir=namespace_dir,
        profile=profile,
        artifact_namespace=artifact_namespace,
        geckoterminal_path=geckoterminal_path,
        coingecko_dex_path=coingecko_dex_path,
        defillama_path=defillama_path,
        smoke_mode=smoke_mode,
        allow_live_preflight=allow_live_preflight,
        now=now,
    )
    return result.report


def write_readiness_artifacts(report: DexOnchainReadinessReport, namespace_dir: str | Path) -> tuple[Path, Path]:
    base = Path(namespace_dir).expanduser()
    base.mkdir(parents=True, exist_ok=True)
    json_path = base / READINESS_JSON
    md_path = base / READINESS_MD
    json_path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(format_readiness_report(report) + "\n", encoding="utf-8")
    return json_path, md_path


def format_readiness_report(report: DexOnchainReadinessReport) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA DEX/ON-CHAIN READINESS (research-only, fixture/no-call by default)",
        "=" * 76,
        f"profile: {report.profile or 'unknown'}",
        f"artifact_namespace: {report.artifact_namespace or 'unknown'}",
        f"generated_at: {report.generated_at}",
        f"readiness_status: {report.readiness_status}",
        f"configured: {str(report.configured).lower()}",
        f"smoke_mode: {str(report.smoke_mode).lower()}",
        f"allow_live_preflight: {str(report.allow_live_preflight).lower()}",
        f"live_call_allowed: {str(report.live_call_allowed).lower()}",
        f"no_send_rehearsal: {str(report.no_send_rehearsal).lower()}",
        f"research_only: {str(report.research_only).lower()}",
        f"request_ledger_path: {report.request_ledger_path}",
        f"dex_pool_state_path: {report.dex_pool_state_path}",
        f"dex_pool_anomalies_path: {report.dex_pool_anomalies_path}",
        f"protocol_fundamentals_path: {report.protocol_fundamentals_path}",
        f"dex_pool_state_rows: {report.dex_pool_state_rows}",
        f"dex_pool_anomaly_rows: {report.dex_pool_anomaly_rows}",
        f"protocol_fundamental_rows: {report.protocol_fundamental_rows}",
        "classification_counts: " + _format_counts(report.classification_counts),
        "",
        "Provider rows:",
    ]
    if not report.provider_rows:
        lines.append("- none")
    for row in report.provider_rows:
        lines.extend([
            f"- {row.provider}",
            f"  family: {row.family}",
            f"  configured: {str(row.configured).lower()}",
            f"  env_vars_required: {_join(row.env_vars_required)}",
            f"  fixture_parser_status: {row.fixture_parser_status}",
            f"  live_call_allowed: {str(row.live_call_allowed).lower()}",
            f"  no_send_rehearsal: {str(row.no_send_rehearsal).lower()}",
            f"  request_ledger_path: {row.request_ledger_path}",
            f"  max_requests_per_run: {row.max_requests_per_run}",
            f"  supported_event_types: {_join(row.supported_event_types)}",
            f"  source_packs_enabled: {_join(row.source_packs_enabled)}",
            f"  fixture_path: {row.fixture_path or 'none'}",
            f"  fixture_rows_observed: {row.fixture_rows_observed}",
            f"  normalized_rows_written: {row.normalized_rows_written}",
            f"  anomaly_rows_written: {row.anomaly_rows_written}",
            f"  protocol_rows_written: {row.protocol_rows_written}",
        ])
        if row.parser_error_safe:
            lines.append(f"  parser_error_safe: {row.parser_error_safe}")
    if report.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in report.warnings)
    lines.extend([
        "",
        "No provider network calls were performed by this readiness check.",
        "No Telegram sends, trades, paper trades, normal RSI rows, execution, or Event Alpha TRIGGERED_FADE were created.",
    ])
    return "\n".join(lines)


def load_dex_pool_state(namespace_dir: str | Path | None) -> tuple[dict[str, Any], ...]:
    if namespace_dir is None:
        return ()
    return tuple(dict(row) for row in _read_jsonl(Path(namespace_dir).expanduser() / DEX_POOL_STATE_FILENAME))


def load_dex_pool_anomalies(namespace_dir: str | Path | None) -> tuple[dict[str, Any], ...]:
    if namespace_dir is None:
        return ()
    return tuple(dict(row) for row in _read_jsonl(Path(namespace_dir).expanduser() / DEX_POOL_ANOMALIES_FILENAME))


def load_protocol_fundamentals(namespace_dir: str | Path | None) -> tuple[dict[str, Any], ...]:
    if namespace_dir is None:
        return ()
    return tuple(dict(row) for row in _read_jsonl(Path(namespace_dir).expanduser() / PROTOCOL_FUNDAMENTALS_FILENAME))


def load_readiness_report(namespace_dir: str | Path | None) -> Mapping[str, Any]:
    if namespace_dir is None:
        return {}
    return _read_json(Path(namespace_dir).expanduser() / READINESS_JSON)


def artifact_conflicts(namespace_dir: str | Path | None) -> dict[str, int]:
    out = {
        "dex_onchain_readiness_secret_leak": 0,
        "dex_onchain_live_without_ledger": 0,
        "dex_onchain_live_call_allowed_in_smoke": 0,
        "dex_onchain_missing_fixture_parser_status": 0,
        "dex_onchain_forbidden_side_effect_claim": 0,
        "dex_low_liquidity_promoted_confirmed": 0,
        "protocol_metric_missing_source_time": 0,
    }
    if namespace_dir is None:
        return out
    base = Path(namespace_dir)
    paths = [
        base / READINESS_JSON,
        base / READINESS_MD,
        base / REQUEST_LEDGER,
        base / DEX_POOL_STATE_FILENAME,
        base / DEX_POOL_ANOMALIES_FILENAME,
        base / PROTOCOL_FUNDAMENTALS_FILENAME,
    ]
    existing = [path for path in paths if path.exists()]
    if not existing:
        return out
    text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in existing)
    if _secret_like(text):
        out["dex_onchain_readiness_secret_leak"] = 1
    data = _read_json(base / READINESS_JSON)
    provider_rows = data.get("providers") or data.get("provider_rows") or ()
    ledger_rows = _read_jsonl(base / REQUEST_LEDGER)
    if bool(data.get("smoke_mode")) and bool(data.get("live_call_allowed")):
        out["dex_onchain_live_call_allowed_in_smoke"] = 1
    if bool(data.get("live_call_allowed")) and not ledger_rows:
        out["dex_onchain_live_without_ledger"] = 1
    if isinstance(provider_rows, Iterable) and not isinstance(provider_rows, (str, bytes, Mapping)):
        for row in provider_rows:
            if not isinstance(row, Mapping):
                continue
            if not str(row.get("fixture_parser_status") or "").strip():
                out["dex_onchain_missing_fixture_parser_status"] += 1
            if bool(row.get("live_call_allowed")) and not ledger_rows:
                out["dex_onchain_live_without_ledger"] += 1
            if bool(data.get("smoke_mode")) and bool(row.get("live_call_allowed")):
                out["dex_onchain_live_call_allowed_in_smoke"] += 1
            for key in _SIDE_EFFECT_COUNTERS:
                if int(row.get(key) or 0) != 0:
                    out["dex_onchain_forbidden_side_effect_claim"] = 1
    for key in _SIDE_EFFECT_COUNTERS:
        if int(data.get(key) or 0) != 0:
            out["dex_onchain_forbidden_side_effect_claim"] = 1
    if re.search(r"(?i)\b(send telegram|paper trade|live trade|execute order|triggered_fade created)\b", text):
        out["dex_onchain_forbidden_side_effect_claim"] = 1
    for row in _read_jsonl(base / DEX_POOL_ANOMALIES_FILENAME):
        if str(row.get("classification") or "") == SUSPICIOUS_LOW_LIQUIDITY_PUMP and str(row.get("opportunity_type") or "") == "CONFIRMED_LONG_RESEARCH":
            out["dex_low_liquidity_promoted_confirmed"] += 1
    for row in _read_jsonl(base / PROTOCOL_FUNDAMENTALS_FILENAME):
        has_metric = any(row.get(key) not in (None, "", [], {}) for key in ("tvl_usd", "fees_24h", "revenue_24h", "tvl_change_24h_pct", "fees_change_24h_pct", "revenue_change_24h_pct"))
        if has_metric and not (row.get("source_url") and (row.get("observed_at") or row.get("published_at") or row.get("timestamp"))):
            out["protocol_metric_missing_source_time"] += 1
    return out


def effective_allow_live_preflight(value: bool = False) -> bool:
    return bool(value or str(os.getenv(ENV_ALLOW_LIVE_PREFLIGHT, "")).strip().casefold() in _TRUTHY)


def _provider_specs(
    *,
    namespace_dir: Path,
    geckoterminal_path: str | Path | None,
    coingecko_dex_path: str | Path | None,
    defillama_path: str | Path | None,
) -> tuple[dict[str, Any], ...]:
    ledger_path = event_artifact_paths.artifact_display_path(namespace_dir / REQUEST_LEDGER)
    return (
        {
            "provider": "geckoterminal",
            "family": "dex_onchain",
            "path": Path(geckoterminal_path).expanduser() if geckoterminal_path else Path(config.EVENT_ALPHA_DEX_GECKOTERMINAL_PATH),
            "env_vars_required": ("RSI_EVENT_ALPHA_DEX_GECKOTERMINAL_PATH",),
            "supported_event_types": ("dex_pool_liquidity", "dex_pool_volume", "dex_ohlcv", "new_pool"),
            "source_packs_enabled": ("dex_liquidity_pack", "market_anomaly_pack"),
            "max_requests_per_run": 20,
            "provider_health_key": "geckoterminal",
            "request_ledger_path": ledger_path,
        },
        {
            "provider": "coingecko_dex",
            "family": "dex_onchain",
            "path": Path(coingecko_dex_path).expanduser() if coingecko_dex_path else Path(config.EVENT_ALPHA_DEX_COINGECKO_PATH),
            "env_vars_required": ("RSI_EVENT_ALPHA_DEX_COINGECKO_PATH", "COINGECKO_API_KEY"),
            "supported_event_types": ("token_liquidity_pools", "dex_pool_liquidity", "dex_pool_volume"),
            "source_packs_enabled": ("dex_liquidity_pack", "market_anomaly_pack"),
            "max_requests_per_run": 20,
            "provider_health_key": "coingecko_dex",
            "request_ledger_path": ledger_path,
        },
        {
            "provider": "defillama_tvl_fees_revenue",
            "family": "protocol_fundamentals",
            "path": Path(defillama_path).expanduser() if defillama_path else Path(config.EVENT_ALPHA_PROTOCOL_DEFILLAMA_PATH),
            "env_vars_required": ("RSI_EVENT_ALPHA_PROTOCOL_DEFILLAMA_PATH",),
            "supported_event_types": ("protocol_tvl", "protocol_fees", "protocol_revenue", "protocol_volume"),
            "source_packs_enabled": ("protocol_fundamentals_pack", "strategic_investment_pack", "security_shock_pack"),
            "max_requests_per_run": 20,
            "provider_health_key": "defillama_tvl_fees_revenue",
            "request_ledger_path": ledger_path,
        },
    )


_SIDE_EFFECT_COUNTERS = (
    "strict_alerts_created",
    "telegram_sends",
    "trades_created",
    "paper_trades_created",
    "normal_rsi_signal_rows_written",
    "triggered_fade_created",
)


def _provider_readiness_row(
    spec: Mapping[str, Any],
    *,
    observed_at: datetime,
    profile: str | None,
    artifact_namespace: str | None,
) -> tuple[DexOnchainProviderReadinessRow, list[dict[str, Any]], list[dict[str, Any]], tuple[str, ...]]:
    provider = str(spec.get("provider") or "")
    path = spec.get("path")
    path_obj = Path(path).expanduser() if path else None
    configured = bool(path_obj and path_obj.exists())
    fixture_status = "not_configured"
    fixture_rows = 0
    dex_rows: list[dict[str, Any]] = []
    protocol_rows: list[dict[str, Any]] = []
    parser_error_safe: str | None = None
    warnings: list[str] = []
    if path_obj is not None and not path_obj.exists():
        fixture_status = "missing_fixture"
    elif path_obj is not None:
        try:
            items = _load_provider_items(provider, path_obj)
            fixture_rows = len(items)
            if provider in {"geckoterminal", "coingecko_dex"}:
                dex_rows = [
                    _normalize_dex_pool_row(
                        item,
                        provider=provider,
                        observed_at=observed_at,
                        profile=profile,
                        artifact_namespace=artifact_namespace,
                    )
                    for item in items
                ]
            elif provider == "defillama_tvl_fees_revenue":
                protocol_rows = [
                    _normalize_protocol_row(
                        item,
                        provider=provider,
                        observed_at=observed_at,
                        profile=profile,
                        artifact_namespace=artifact_namespace,
                    )
                    for item in items
                ]
            fixture_status = "pass" if (dex_rows or protocol_rows) else "no_rows"
        except Exception as exc:  # noqa: BLE001 - readiness must fail safely
            fixture_status = "failed"
            parser_error_safe = type(exc).__name__
            warnings.append(f"{provider}_fixture_parser_failed:{type(exc).__name__}")
    row = DexOnchainProviderReadinessRow(
        provider=provider,
        family=str(spec.get("family") or ""),
        configured=configured,
        env_vars_required=tuple(str(item) for item in spec.get("env_vars_required") or ()),
        fixture_parser_status=fixture_status,
        live_call_allowed=False,
        no_send_rehearsal=True,
        request_ledger_path=str(spec.get("request_ledger_path") or ""),
        max_requests_per_run=int(spec.get("max_requests_per_run") or 0),
        supported_event_types=tuple(str(item) for item in spec.get("supported_event_types") or ()),
        source_packs_enabled=tuple(str(item) for item in spec.get("source_packs_enabled") or ()),
        provider_health_key=str(spec.get("provider_health_key") or provider),
        fixture_path=event_artifact_paths.artifact_display_path(path_obj) if path_obj else None,
        fixture_rows_observed=fixture_rows,
        normalized_rows_written=len(dex_rows),
        anomaly_rows_written=0,
        protocol_rows_written=len(protocol_rows),
        parser_error_safe=parser_error_safe,
    )
    return row, dex_rows, protocol_rows, tuple(warnings)


def _replace_provider_counts(
    row: DexOnchainProviderReadinessRow,
    *,
    state_rows: Iterable[Mapping[str, Any]],
    anomalies: Iterable[Mapping[str, Any]],
    protocol_rows: Iterable[Mapping[str, Any]],
) -> DexOnchainProviderReadinessRow:
    provider = row.provider
    normalized = sum(1 for item in state_rows if str(item.get("provider") or "") == provider)
    anomaly_count = sum(1 for item in anomalies if str(item.get("provider") or "") == provider)
    protocol_count = sum(1 for item in protocol_rows if str(item.get("provider") or "") == provider)
    return replace(
        row,
        normalized_rows_written=normalized,
        anomaly_rows_written=anomaly_count,
        protocol_rows_written=protocol_count,
    )


def _load_provider_items(provider: str, path: Path) -> tuple[Mapping[str, Any], ...]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, Mapping):
        if provider == "geckoterminal":
            raw = data.get("data") or data.get("pools") or data.get("items") or data.get("rows") or []
        elif provider == "coingecko_dex":
            raw = data.get("pools") or data.get("data") or data.get("items") or data.get("rows") or []
        else:
            raw = data.get("protocols") or data.get("data") or data.get("items") or data.get("rows") or []
    else:
        raw = data
    if not isinstance(raw, Iterable) or isinstance(raw, (str, bytes, Mapping)):
        return ()
    return tuple(dict(item) for item in raw if isinstance(item, Mapping))


def _normalize_dex_pool_row(
    item: Mapping[str, Any],
    *,
    provider: str,
    observed_at: datetime,
    profile: str | None,
    artifact_namespace: str | None,
) -> dict[str, Any]:
    attrs = _mapping(item.get("attributes"))
    rel = _mapping(item.get("relationships"))
    base_token = _mapping(_mapping(rel.get("base_token")).get("data") or item.get("base_token"))
    network = str(_first(item, attrs, "network", "chain", "network_id") or "").strip()
    pool_id = str(item.get("id") or attrs.get("pool_id") or attrs.get("address") or item.get("address") or "").strip()
    symbol = _symbol(_first(item, attrs, base_token, "symbol", "base_symbol", "base_token_symbol", "ticker"))
    coin_id = str(_first(attrs, base_token, item, "coin_id", "coingecko_coin_id") or symbol.casefold()).strip()
    observed = str(_first(item, attrs, "observed_at", "timestamp", "updated_at") or observed_at.isoformat())
    liquidity = _float(_first(item, attrs, "pool_liquidity_usd", "liquidity_usd", "reserve_in_usd", "reserve_usd", "total_reserve_in_usd"))
    volume_24h = _float(_first(item, attrs, "dex_volume_24h", "volume_24h", "pool_volume_24h", "h24_volume_usd"))
    volume_usd = _mapping(attrs.get("volume_usd") or item.get("volume_usd"))
    if volume_24h is None:
        volume_24h = _float(_first(volume_usd, "h24", "24h"))
    price_change = _float(_first(item, attrs, "price_change_24h", "price_change_percentage_24h", "return_24h"))
    price_changes = _mapping(attrs.get("price_change_percentage") or item.get("price_change_percentage"))
    if price_change is None:
        price_change = _float(_first(price_changes, "h24", "24h"))
    liquidity_change = _as_pct(_float(_first(item, attrs, "dex_liquidity_change", "liquidity_change_24h", "pool_liquidity_change_pct")))
    volume_change = _as_pct(_float(_first(item, attrs, "dex_volume_change", "dex_volume_24h_change_pct", "volume_change_24h")))
    volume_z = _float(_first(item, attrs, "dex_volume_zscore_24h", "volume_zscore_24h", "volume_zscore"))
    if volume_z is None and volume_24h is not None and liquidity and liquidity > 0:
        volume_z = min(8.0, volume_24h / max(liquidity, 1.0))
    pool_age = _float(_first(item, attrs, "pool_age_hours", "age_hours"))
    market_snapshot = _mapping(item.get("market_snapshot") or attrs.get("market_snapshot"))
    if not market_snapshot:
        market_snapshot = {
            "return_unit": "percent_points",
            "return_24h": price_change,
            "volume_zscore_24h": volume_z,
            "volume_24h": volume_24h,
            "liquidity_usd": liquidity,
            "market_context_source": provider,
            "market_context_freshness_status": "fresh",
            "observed_at": observed,
        }
    source_url = str(_first(item, attrs, "source_url", "url") or _default_source_url(provider, network=network, pool_id=pool_id) or "").strip()
    row = {
        "schema_version": 1,
        "row_type": "event_dex_pool_state",
        "profile": profile,
        "artifact_namespace": artifact_namespace,
        "provider": provider,
        "source_provider": provider,
        "latest_source": provider,
        "source_family": "dex_onchain",
        "source_class": "market_data",
        "source_pack": "dex_liquidity_pack",
        "impact_path_type": "dex_liquidity_reaction",
        "source_strength": "market_data",
        "accepted_evidence_count": 0,
        "pool_id": pool_id,
        "network": network or None,
        "dex": _first(item, attrs, "dex", "dex_name", "exchange") or None,
        "symbol": symbol,
        "base_symbol": symbol,
        "coin_id": coin_id,
        "canonical_asset_id": str(_first(item, attrs, "canonical_asset_id") or coin_id or symbol).strip(),
        "pool_liquidity_usd": liquidity,
        "liquidity_usd": liquidity,
        "dex_volume_24h": volume_24h,
        "volume_24h": volume_24h,
        "dex_volume_zscore_24h": volume_z,
        "dex_volume_change": volume_change,
        "dex_volume_24h_change_pct": volume_change,
        "dex_liquidity_change": liquidity_change,
        "pool_liquidity_change_pct": liquidity_change,
        "pool_age_hours": pool_age,
        "price_change_24h": price_change,
        "source_url": source_url,
        "latest_source_url": source_url,
        "source_title": f"{symbol} DEX pool state" if symbol else "DEX pool state",
        "latest_source_title": f"{symbol} DEX pool state" if symbol else "DEX pool state",
        "observed_at": observed,
        "freshness_status": str(_first(item, attrs, "freshness_status") or "fresh"),
        "market_context_freshness_status": str(_first(item, attrs, "market_context_freshness_status") or "fresh"),
        "market_snapshot": market_snapshot,
        "dex_liquidity_snapshot": {},
        "research_only": True,
        "created_alert": False,
        "normal_rsi_signal_written": False,
        "triggered_fade_created": False,
        "paper_trade_created": False,
    }
    row["dex_liquidity_snapshot"] = {
        key: row.get(key)
        for key in (
            "pool_liquidity_usd",
            "liquidity_usd",
            "dex_volume_24h",
            "volume_24h",
            "dex_volume_zscore_24h",
            "dex_volume_change",
            "dex_volume_24h_change_pct",
            "dex_liquidity_change",
            "pool_liquidity_change_pct",
            "pool_age_hours",
            "source_url",
            "observed_at",
            "freshness_status",
            "provider",
        )
        if row.get(key) is not None
    }
    return {key: value for key, value in row.items() if value is not None}


def _classify_dex_anomalies(
    rows: Iterable[Mapping[str, Any]],
    *,
    profile: str | None,
    artifact_namespace: str | None,
    observed_at: datetime,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        classification = _dex_classification(row)
        if not classification:
            continue
        warnings: list[str] = []
        pool_liq = _float(row.get("pool_liquidity_usd") or row.get("liquidity_usd"))
        if classification == SUSPICIOUS_LOW_LIQUIDITY_PUMP:
            warnings.append("dex_low_liquidity_pump_diagnostic_only")
        anomaly = {
            "schema_version": 1,
            "row_type": "event_dex_pool_anomaly",
            "profile": profile,
            "artifact_namespace": artifact_namespace,
            "provider": row.get("provider"),
            "source_provider": row.get("source_provider") or row.get("provider"),
            "latest_source": row.get("latest_source") or row.get("provider"),
            "source_family": "dex_onchain",
            "source_class": "market_data",
            "source_pack": "dex_liquidity_pack",
            "impact_path_type": "dex_liquidity_reaction",
            "source_strength": "market_data",
            "accepted_evidence_count": 0,
            "classification": classification,
            "dex_anomaly_class": classification,
            "symbol": row.get("symbol"),
            "coin_id": row.get("coin_id"),
            "canonical_asset_id": row.get("canonical_asset_id"),
            "pool_id": row.get("pool_id"),
            "network": row.get("network"),
            "pool_liquidity_usd": pool_liq,
            "dex_volume_24h": row.get("dex_volume_24h"),
            "dex_volume_zscore_24h": row.get("dex_volume_zscore_24h"),
            "dex_liquidity_snapshot": row.get("dex_liquidity_snapshot"),
            "market_snapshot": row.get("market_snapshot"),
            "source_url": row.get("source_url"),
            "latest_source_url": row.get("latest_source_url") or row.get("source_url"),
            "source_title": row.get("source_title"),
            "latest_source_title": row.get("latest_source_title") or row.get("source_title"),
            "observed_at": row.get("observed_at") or observed_at.isoformat(),
            "freshness_status": row.get("freshness_status") or "fresh",
            "warnings": warnings,
            "research_only": True,
            "created_alert": False,
            "normal_rsi_signal_written": False,
            "triggered_fade_created": False,
            "paper_trade_created": False,
        }
        out.append({key: value for key, value in anomaly.items() if value not in (None, "", [], {})})
    return out


def _normalize_protocol_row(
    item: Mapping[str, Any],
    *,
    provider: str,
    observed_at: datetime,
    profile: str | None,
    artifact_namespace: str | None,
) -> dict[str, Any]:
    metrics = _mapping(item.get("metrics") or item.get("data"))
    protocol = _mapping(item.get("protocol"))
    symbol = _symbol(_first(item, metrics, protocol, "symbol", "token_symbol", "ticker"))
    coin_id = str(_first(item, metrics, protocol, "coin_id", "coingecko_id", "slug", "id") or symbol.casefold()).strip()
    observed = str(_first(item, metrics, "observed_at", "timestamp", "updated_at") or observed_at.isoformat())
    tvl = _float(_first(item, metrics, "tvl", "tvl_usd", "total_value_locked"))
    fees = _float(_first(item, metrics, "fees_24h", "daily_fees", "fees"))
    revenue = _float(_first(item, metrics, "revenue_24h", "daily_revenue", "revenue"))
    tvl_change = _as_pct(_float(_first(item, metrics, "tvl_change_24h_pct", "tvl_24h_change_pct", "tvl_change")))
    fees_change = _as_pct(_float(_first(item, metrics, "fees_change_24h_pct", "fees_24h_change_pct", "fees_change")))
    revenue_change = _as_pct(_float(_first(item, metrics, "revenue_change_24h_pct", "revenue_24h_change_pct", "revenue_change")))
    volume = _float(_first(item, metrics, "protocol_dex_volume_24h", "dex_volume_24h", "volume_24h"))
    volume_change = _as_pct(_float(_first(item, metrics, "protocol_volume_change_24h_pct", "dex_volume_change_24h_pct", "volume_change_24h")))
    market_snapshot = _mapping(item.get("market_snapshot") or metrics.get("market_snapshot"))
    source_url = str(_first(item, metrics, "source_url", "url") or _default_source_url(provider, coin_id=coin_id) or "").strip()
    row = {
        "schema_version": 1,
        "row_type": "event_protocol_fundamentals",
        "profile": profile,
        "artifact_namespace": artifact_namespace,
        "provider": provider,
        "source_provider": provider,
        "latest_source": provider,
        "source_family": "protocol_fundamentals",
        "source_class": "market_data",
        "source_pack": "protocol_fundamentals_pack",
        "impact_path_type": "protocol_fundamentals",
        "source_strength": "strong",
        "accepted_evidence_count": 1 if source_url else 0,
        "protocol_id": _first(item, metrics, protocol, "protocol_id", "slug", "id") or coin_id,
        "protocol_name": _first(item, metrics, protocol, "name", "protocol_name"),
        "symbol": symbol,
        "coin_id": coin_id,
        "canonical_asset_id": str(_first(item, metrics, protocol, "canonical_asset_id") or coin_id or symbol).strip(),
        "tvl_usd": tvl,
        "tvl": tvl,
        "fees_24h": fees,
        "revenue_24h": revenue,
        "protocol_revenue_24h": revenue,
        "tvl_change_24h_pct": tvl_change,
        "fees_change_24h_pct": fees_change,
        "revenue_change_24h_pct": revenue_change,
        "protocol_dex_volume_24h": volume,
        "protocol_volume_change_24h_pct": volume_change,
        "protocol_metrics_snapshot": {},
        "market_snapshot": market_snapshot,
        "source_url": source_url,
        "latest_source_url": source_url,
        "source_title": _first(item, metrics, protocol, "title", "name", "protocol_name") or f"{symbol} protocol fundamentals",
        "latest_source_title": _first(item, metrics, protocol, "title", "name", "protocol_name") or f"{symbol} protocol fundamentals",
        "observed_at": observed,
        "freshness_status": str(_first(item, metrics, "freshness_status") or "fresh"),
        "market_context_freshness_status": str(_first(item, metrics, "market_context_freshness_status") or "fresh"),
        "research_only": True,
        "created_alert": False,
        "normal_rsi_signal_written": False,
        "triggered_fade_created": False,
        "paper_trade_created": False,
    }
    row["protocol_metrics_snapshot"] = {
        key: row.get(key)
        for key in (
            "tvl",
            "tvl_usd",
            "fees_24h",
            "revenue_24h",
            "protocol_revenue_24h",
            "tvl_change_24h_pct",
            "fees_change_24h_pct",
            "revenue_change_24h_pct",
            "protocol_dex_volume_24h",
            "protocol_volume_change_24h_pct",
            "source_url",
            "observed_at",
            "freshness_status",
            "provider",
        )
        if row.get(key) is not None
    }
    return {key: value for key, value in row.items() if value is not None}


def _with_protocol_classification(
    row: Mapping[str, Any],
    *,
    profile: str | None,
    artifact_namespace: str | None,
    observed_at: datetime,
) -> dict[str, Any]:
    out = dict(row)
    out["profile"] = out.get("profile") or profile
    out["artifact_namespace"] = out.get("artifact_namespace") or artifact_namespace
    out["observed_at"] = out.get("observed_at") or observed_at.isoformat()
    classification = _protocol_classification(out)
    if classification:
        out["classification"] = classification
        out["protocol_fundamentals_class"] = classification
        reasons = [str(item) for item in out.get("reason_codes") or () if str(item)]
        if classification == PROTOCOL_FUNDAMENTALS_DETERIORATION:
            reasons.extend([
                "protocol_fundamentals_deterioration",
                "protocol_metric_source_url_present",
                "protocol_metric_time_present",
            ])
        elif classification == PROTOCOL_REVENUE_TVL_GROWTH:
            reasons.extend([
                "protocol_revenue_tvl_growth",
                "protocol_metric_source_url_present",
                "protocol_metric_time_present",
            ])
        out["reason_codes"] = list(dict.fromkeys(reasons))
    return out


def _dex_classification(row: Mapping[str, Any]) -> str | None:
    liquidity = _float(row.get("pool_liquidity_usd") or row.get("liquidity_usd"))
    volume = _float(row.get("dex_volume_24h") or row.get("volume_24h"))
    volume_z = _float(row.get("dex_volume_zscore_24h") or row.get("volume_zscore_24h"))
    price_change = _as_pct(_float(row.get("price_change_24h") or _mapping(row.get("market_snapshot")).get("return_24h")))
    liquidity_change = _as_pct(_float(row.get("dex_liquidity_change") or row.get("pool_liquidity_change_pct")))
    volume_change = _as_pct(_float(row.get("dex_volume_change") or row.get("dex_volume_24h_change_pct")))
    low_liquidity = liquidity is not None and liquidity < 100_000
    high_volume = (volume is not None and volume >= 250_000) or (volume_z is not None and volume_z >= 2.5) or (volume_change is not None and volume_change >= 35)
    if low_liquidity and price_change is not None and price_change >= 35:
        return SUSPICIOUS_LOW_LIQUIDITY_PUMP
    if liquidity is not None and liquidity >= 250_000 and liquidity_change is not None and liquidity_change >= 25:
        return DEX_LIQUIDITY_EXPANSION
    if liquidity is not None and liquidity >= 250_000 and high_volume:
        return DEX_VOLUME_BREAKOUT
    return None


def _protocol_classification(row: Mapping[str, Any]) -> str | None:
    tvl_change = _as_pct(_float(row.get("tvl_change_24h_pct")))
    fees_change = _as_pct(_float(row.get("fees_change_24h_pct")))
    revenue_change = _as_pct(_float(row.get("revenue_change_24h_pct")))
    growth = any(value is not None and value >= threshold for value, threshold in ((tvl_change, 8), (fees_change, 15), (revenue_change, 15)))
    deterioration = any(value is not None and value <= -threshold for value, threshold in ((tvl_change, 8), (fees_change, 15), (revenue_change, 15)))
    if deterioration:
        return PROTOCOL_FUNDAMENTALS_DETERIORATION
    if growth:
        return PROTOCOL_REVENUE_TVL_GROWTH
    return None


def _readiness_status(rows: Iterable[DexOnchainProviderReadinessRow]) -> str:
    materialized = tuple(rows)
    if materialized and all(row.fixture_parser_status == "pass" for row in materialized):
        return "fixture_ready"
    if any(row.fixture_parser_status == "pass" for row in materialized):
        return "fixture_partial"
    if materialized and all(row.fixture_parser_status in {"not_configured", "missing_fixture"} for row in materialized):
        return "missing_config"
    return "fixture_parser_failed"


def _classification_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get("classification") or row.get("dex_anomaly_class") or row.get("protocol_fundamentals_class") or "unknown")
        if key and key != "unknown":
            counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(dict(row), sort_keys=True, default=str, separators=(",", ":")) + "\n")


def _read_json(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        return {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, Mapping) else {}


def _read_jsonl(path: Path) -> tuple[Mapping[str, Any], ...]:
    if not path.exists():
        return ()
    out: list[Mapping[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, Mapping):
            out.append(row)
    return tuple(out)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _first(*sources_and_keys: Any) -> Any:
    sources: list[Mapping[str, Any]] = []
    keys: list[str] = []
    for item in sources_and_keys:
        if isinstance(item, Mapping):
            sources.append(item)
        elif isinstance(item, Iterable) and not isinstance(item, (str, bytes)):
            keys.extend(str(key) for key in item)
        else:
            keys.append(str(item))
    for source in sources:
        if not isinstance(source, Mapping):
            continue
        for key in keys:
            value = source.get(key)
            if value not in (None, "", [], {}):
                return value
    return None


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_pct(value: float | None) -> float | None:
    if value is None:
        return None
    return value * 100.0 if abs(value) <= 3.0 else value


def _symbol(value: Any) -> str:
    text = str(value or "").strip().upper()
    return re.sub(r"[^A-Z0-9]", "", text) or "UNKNOWN"


def _default_source_url(provider: str, *, network: str | None = None, pool_id: str | None = None, coin_id: str | None = None) -> str:
    if provider == "geckoterminal" and network and pool_id:
        return f"https://www.geckoterminal.com/{network}/pools/{pool_id}"
    if provider == "coingecko_dex" and coin_id:
        return f"https://www.coingecko.com/en/coins/{coin_id}"
    if provider == "defillama_tvl_fees_revenue" and coin_id:
        return f"https://defillama.com/protocol/{coin_id}"
    return ""


def _secret_like(text: str) -> bool:
    patterns = (
        r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}",
        r"\bghp_[A-Za-z0-9_]{20,}",
        r"(?i)(api[_-]?key|secret|token)\s*[=:]\s*['\"][A-Za-z0-9._-]{20,}['\"]",
        r"(?i)(api[_-]?key|secret|token)\s+[A-Za-z0-9._-]{24,}",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def _join(values: Iterable[Any]) -> str:
    items = [str(item) for item in values if str(item)]
    return ", ".join(items) if items else "none"


def _format_counts(counts: Mapping[str, int]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items())) if counts else "none"
