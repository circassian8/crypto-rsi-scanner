"""Structured unlock/calendar preflight artifacts for Event Alpha research.

This module is fixture/parser only by default. It prepares provider-specific
activation rows for scheduled catalyst and unlock providers, but it never makes
provider network calls, sends notifications, trades, paper trades, writes normal
RSI rows, executes orders, or creates ``TRIGGERED_FADE``.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from ... import config, event_scheduled_catalysts
from ..artifacts import paths as event_artifact_paths


PREFLIGHT_JSON = "event_unlock_calendar_preflight.json"
PREFLIGHT_MD = "event_unlock_calendar_preflight.md"
REQUEST_LEDGER = "event_unlock_calendar_request_ledger.jsonl"
ENV_ALLOW_LIVE_PREFLIGHT = "RSI_EVENT_ALPHA_UNLOCK_CALENDAR_ALLOW_LIVE_PREFLIGHT"
DEFAULT_PREFLIGHT_NAMESPACE = "unlock_calendar_preflight"
_TRUTHY = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class UnlockCalendarProviderPreflightRow:
    provider: str
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
    scheduled_events_previewed: int
    unlock_candidates_previewed: int
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
            "scheduled_events_previewed": self.scheduled_events_previewed,
            "unlock_candidates_previewed": self.unlock_candidates_previewed,
            "parser_error_safe": self.parser_error_safe,
            "strict_alerts_created": self.strict_alerts_created,
            "telegram_sends": self.telegram_sends,
            "trades_created": self.trades_created,
            "paper_trades_created": self.paper_trades_created,
            "normal_rsi_signal_rows_written": self.normal_rsi_signal_rows_written,
            "triggered_fade_created": self.triggered_fade_created,
        }


@dataclass(frozen=True)
class UnlockCalendarPreflightReport:
    profile: str | None
    artifact_namespace: str | None
    generated_at: str
    preflight_status: str
    configured: bool
    allow_live_preflight: bool
    live_call_allowed: bool
    no_send_rehearsal: bool
    research_only: bool
    smoke_mode: bool
    request_ledger_path: str
    provider_rows: tuple[UnlockCalendarProviderPreflightRow, ...]
    warnings: tuple[str, ...] = ()
    strict_alerts_created: int = 0
    telegram_sends: int = 0
    trades_created: int = 0
    paper_trades_created: int = 0
    normal_rsi_signal_rows_written: int = 0
    triggered_fade_created: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "event_unlock_calendar_preflight_v1",
            "row_type": "event_unlock_calendar_preflight",
            "profile": self.profile,
            "artifact_namespace": self.artifact_namespace,
            "generated_at": self.generated_at,
            "preflight_status": self.preflight_status,
            "configured": self.configured,
            "allow_live_preflight": self.allow_live_preflight,
            "live_call_allowed": self.live_call_allowed,
            "no_send_rehearsal": self.no_send_rehearsal,
            "research_only": self.research_only,
            "smoke_mode": self.smoke_mode,
            "request_ledger_path": self.request_ledger_path,
            "providers": [row.to_dict() for row in self.provider_rows],
            "provider_rows": [row.to_dict() for row in self.provider_rows],
            "warnings": list(self.warnings),
            "strict_alerts_created": self.strict_alerts_created,
            "telegram_sends": self.telegram_sends,
            "trades_created": self.trades_created,
            "paper_trades_created": self.paper_trades_created,
            "normal_rsi_signal_rows_written": self.normal_rsi_signal_rows_written,
            "triggered_fade_created": self.triggered_fade_created,
        }


def build_preflight_report(
    *,
    namespace_dir: str | Path,
    profile: str | None = None,
    artifact_namespace: str | None = None,
    provider_filter: str | None = None,
    tokenomist_path: str | Path | None = None,
    messari_path: str | Path | None = None,
    coinmarketcal_path: str | Path | None = None,
    smoke_mode: bool = False,
    allow_live_preflight: bool = False,
    now: datetime | None = None,
) -> UnlockCalendarPreflightReport:
    base = Path(namespace_dir).expanduser()
    ledger_path = base / REQUEST_LEDGER
    allow_live = effective_allow_live_preflight(allow_live_preflight)
    selected_provider = str(provider_filter or "").strip()
    warnings: list[str] = []
    specs = _provider_specs(
        namespace_dir=base,
        tokenomist_path=tokenomist_path,
        messari_path=messari_path,
        coinmarketcal_path=coinmarketcal_path,
    )
    rows: list[UnlockCalendarProviderPreflightRow] = []
    for spec in specs:
        if selected_provider and spec["provider"] != selected_provider:
            continue
        rows.append(_provider_preflight_row(spec))
    if selected_provider and not rows:
        warnings.append(f"unknown_provider:{selected_provider}")
    if rows and all(row.fixture_parser_status == "pass" for row in rows):
        status = "fixture_ready"
    elif any(row.fixture_parser_status == "pass" for row in rows):
        status = "fixture_partial"
    elif rows and all(row.fixture_parser_status in {"not_configured", "missing_fixture"} for row in rows):
        status = "missing_config"
    else:
        status = "fixture_parser_failed"
    if allow_live:
        warnings.append("live_unlock_calendar_fetch_not_implemented_fixture_only")
    return UnlockCalendarPreflightReport(
        profile=profile,
        artifact_namespace=artifact_namespace,
        generated_at=(now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(),
        preflight_status=status,
        configured=any(row.configured for row in rows),
        allow_live_preflight=allow_live,
        live_call_allowed=False,
        no_send_rehearsal=True,
        research_only=True,
        smoke_mode=bool(smoke_mode),
        request_ledger_path=event_artifact_paths.artifact_display_path(ledger_path),
        provider_rows=tuple(rows),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def write_preflight_artifacts(report: UnlockCalendarPreflightReport, namespace_dir: str | Path) -> tuple[Path, Path]:
    base = Path(namespace_dir).expanduser()
    base.mkdir(parents=True, exist_ok=True)
    json_path = base / PREFLIGHT_JSON
    md_path = base / PREFLIGHT_MD
    json_path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(format_preflight_report(report) + "\n", encoding="utf-8")
    return json_path, md_path


def format_preflight_report(report: UnlockCalendarPreflightReport) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA UNLOCK/CALENDAR PREFLIGHT (research-only, fixture/no-call by default)",
        "=" * 76,
        f"profile: {report.profile or 'unknown'}",
        f"artifact_namespace: {report.artifact_namespace or 'unknown'}",
        f"generated_at: {report.generated_at}",
        f"preflight_status: {report.preflight_status}",
        f"configured: {str(report.configured).lower()}",
        f"smoke_mode: {str(report.smoke_mode).lower()}",
        f"allow_live_preflight: {str(report.allow_live_preflight).lower()}",
        f"live_call_allowed: {str(report.live_call_allowed).lower()}",
        f"no_send_rehearsal: {str(report.no_send_rehearsal).lower()}",
        f"research_only: {str(report.research_only).lower()}",
        f"request_ledger_path: {report.request_ledger_path}",
        "",
        "Provider rows:",
    ]
    if not report.provider_rows:
        lines.append("- none")
    for row in report.provider_rows:
        lines.extend([
            f"- {row.provider}",
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
            f"  scheduled_events_previewed: {row.scheduled_events_previewed}",
            f"  unlock_candidates_previewed: {row.unlock_candidates_previewed}",
        ])
        if row.parser_error_safe:
            lines.append(f"  parser_error_safe: {row.parser_error_safe}")
    if report.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in report.warnings)
    lines.extend([
        "",
        "No provider network calls were performed by this preflight.",
        "No Telegram sends, trades, paper trades, normal RSI rows, execution, or Event Alpha TRIGGERED_FADE were created.",
    ])
    return "\n".join(lines)


def load_preflight_report(namespace_dir: str | Path | None) -> Mapping[str, Any]:
    if namespace_dir is None:
        return {}
    return _read_json(Path(namespace_dir).expanduser() / PREFLIGHT_JSON)


def artifact_conflicts(namespace_dir: str | Path | None) -> dict[str, int]:
    out = {
        "unlock_calendar_preflight_secret_leak": 0,
        "unlock_calendar_preflight_live_without_ledger": 0,
        "unlock_calendar_preflight_live_call_allowed_in_smoke": 0,
        "unlock_calendar_preflight_missing_fixture_parser_status": 0,
        "unlock_calendar_preflight_forbidden_side_effect_claim": 0,
    }
    if namespace_dir is None:
        return out
    base = Path(namespace_dir)
    paths = [base / PREFLIGHT_JSON, base / PREFLIGHT_MD, base / REQUEST_LEDGER]
    existing = [path for path in paths if path.exists()]
    if not existing:
        return out
    text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in existing)
    if _secret_like(text):
        out["unlock_calendar_preflight_secret_leak"] = 1
    data = _read_json(base / PREFLIGHT_JSON)
    providers = data.get("providers") or data.get("provider_rows") or ()
    ledger_rows = _read_jsonl(base / REQUEST_LEDGER)
    if bool(data.get("smoke_mode")) and bool(data.get("live_call_allowed")):
        out["unlock_calendar_preflight_live_call_allowed_in_smoke"] = 1
    if bool(data.get("live_call_allowed")) and not ledger_rows:
        out["unlock_calendar_preflight_live_without_ledger"] = 1
    for row in providers if isinstance(providers, Iterable) and not isinstance(providers, (str, bytes, Mapping)) else ():
        if not isinstance(row, Mapping):
            continue
        if not str(row.get("fixture_parser_status") or "").strip():
            out["unlock_calendar_preflight_missing_fixture_parser_status"] += 1
        if bool(row.get("smoke_mode")) and bool(row.get("live_call_allowed")):
            out["unlock_calendar_preflight_live_call_allowed_in_smoke"] += 1
        if bool(row.get("live_call_allowed")) and not ledger_rows:
            out["unlock_calendar_preflight_live_without_ledger"] += 1
        for key in (
            "strict_alerts_created",
            "telegram_sends",
            "trades_created",
            "paper_trades_created",
            "normal_rsi_signal_rows_written",
            "triggered_fade_created",
        ):
            if int(row.get(key) or 0) != 0:
                out["unlock_calendar_preflight_forbidden_side_effect_claim"] = 1
    for key in (
        "strict_alerts_created",
        "telegram_sends",
        "trades_created",
        "paper_trades_created",
        "normal_rsi_signal_rows_written",
        "triggered_fade_created",
    ):
        if int(data.get(key) or 0) != 0:
            out["unlock_calendar_preflight_forbidden_side_effect_claim"] = 1
    if re.search(r"(?i)\b(send telegram|paper trade|live trade|execute order|triggered_fade created)\b", text):
        out["unlock_calendar_preflight_forbidden_side_effect_claim"] = 1
    return out


def effective_allow_live_preflight(value: bool = False) -> bool:
    return bool(value or str(os.getenv(ENV_ALLOW_LIVE_PREFLIGHT, "")).strip().casefold() in _TRUTHY)


def _provider_specs(
    *,
    namespace_dir: Path,
    tokenomist_path: str | Path | None,
    messari_path: str | Path | None,
    coinmarketcal_path: str | Path | None,
) -> tuple[dict[str, Any], ...]:
    ledger_path = event_artifact_paths.artifact_display_path(namespace_dir / REQUEST_LEDGER)
    return (
        {
            "provider": "tokenomist",
            "path": Path(tokenomist_path).expanduser() if tokenomist_path else Path(config.EVENT_ALPHA_SCHEDULED_CATALYST_TOKENOMIST_PATH),
            "env_vars_required": ("RSI_EVENT_ALPHA_SCHEDULED_CATALYST_TOKENOMIST_PATH", "TOKENOMIST_API_KEY"),
            "supported_event_types": ("token_unlock", "vesting_cliff", "linear_emission"),
            "source_packs_enabled": ("unlock_supply_pack",),
            "max_requests_per_run": 10,
            "provider_health_key": "tokenomist",
            "request_ledger_path": ledger_path,
        },
        {
            "provider": "messari_unlocks",
            "path": Path(messari_path).expanduser() if messari_path else Path(config.EVENT_ALPHA_SCHEDULED_CATALYST_MESSARI_PATH),
            "env_vars_required": ("RSI_EVENT_ALPHA_SCHEDULED_CATALYST_MESSARI_PATH", "MESSARI_API_KEY"),
            "supported_event_types": ("token_unlock", "vesting_cliff", "linear_emission"),
            "source_packs_enabled": ("unlock_supply_pack",),
            "max_requests_per_run": 10,
            "provider_health_key": "messari_unlocks",
            "request_ledger_path": ledger_path,
        },
        {
            "provider": "coinmarketcal",
            "path": Path(coinmarketcal_path).expanduser() if coinmarketcal_path else Path(config.EVENT_ALPHA_SCHEDULED_CATALYST_COINMARKETCAL_PATH),
            "env_vars_required": ("RSI_EVENT_ALPHA_SCHEDULED_CATALYST_COINMARKETCAL_PATH", "COINMARKETCAL_API_KEY"),
            "supported_event_types": (
                "protocol_upgrade",
                "mainnet",
                "testnet",
                "airdrop",
                "staking_reward",
                "governance_vote",
                "token_unlock",
                "other",
            ),
            "source_packs_enabled": ("project_event_pack", "unlock_supply_pack"),
            "max_requests_per_run": 10,
            "provider_health_key": "coinmarketcal",
            "request_ledger_path": ledger_path,
        },
    )


def _provider_preflight_row(spec: Mapping[str, Any]) -> UnlockCalendarProviderPreflightRow:
    provider = str(spec.get("provider") or "")
    path = spec.get("path")
    path_obj = Path(path).expanduser() if path else None
    configured = bool(path_obj and path_obj.exists())
    fixture_status = "not_configured"
    fixture_rows = 0
    scheduled_previewed = 0
    unlock_previewed = 0
    parser_error_safe: str | None = None
    if path_obj is not None and not path_obj.exists():
        fixture_status = "missing_fixture"
    elif path_obj is not None:
        try:
            items = _load_provider_items(provider, path_obj)
            fixture_rows = len(items)
            normalized_items = tuple(_normalize_provider_item(provider, item) for item in items)
            scheduled_rows, unlock_rows = _preview_rows(provider, normalized_items)
            scheduled_previewed = len(scheduled_rows)
            unlock_previewed = len(unlock_rows)
            fixture_status = "pass" if fixture_rows and scheduled_previewed else "no_rows"
        except Exception as exc:  # noqa: BLE001 - preflight must fail safely
            fixture_status = "failed"
            parser_error_safe = type(exc).__name__
    return UnlockCalendarProviderPreflightRow(
        provider=provider,
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
        scheduled_events_previewed=scheduled_previewed,
        unlock_candidates_previewed=unlock_previewed,
        parser_error_safe=parser_error_safe,
    )


def _load_provider_items(provider: str, path: Path) -> tuple[Mapping[str, Any], ...]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, Mapping):
        if provider == "coinmarketcal":
            raw = data.get("events") or data.get("items") or data.get("data") or []
        else:
            raw = data.get("unlocks") or data.get("items") or data.get("data") or []
    else:
        raw = data
    if not isinstance(raw, Iterable) or isinstance(raw, (str, bytes, Mapping)):
        return ()
    return tuple(dict(item) for item in raw if isinstance(item, Mapping))


def _normalize_provider_item(provider: str, item: Mapping[str, Any]) -> Mapping[str, Any]:
    if provider == "messari_unlocks":
        return event_scheduled_catalysts._normalize_messari_unlock_item(item)
    return dict(item)


def _preview_rows(
    provider: str,
    items: Iterable[Mapping[str, Any]],
) -> tuple[tuple[Mapping[str, Any], ...], tuple[Mapping[str, Any], ...]]:
    scheduled: list[Mapping[str, Any]] = []
    unlocks: list[Mapping[str, Any]] = []
    for item in items:
        source_class = "structured_calendar" if provider == "coinmarketcal" else "structured_unlock"
        event_type = (
            event_scheduled_catalysts._calendar_event_type(item)
            if provider == "coinmarketcal"
            else event_scheduled_catalysts._unlock_event_type(item)
        )
        row = event_scheduled_catalysts.normalize_scheduled_catalyst_event(
            item,
            provider=provider,
            observed_at=datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc),
            forced_event_type=event_type,
            forced_source_class=str(item.get("source_class") or source_class),
        )
        scheduled.append(row)
        if event_type in {"token_unlock", "vesting_cliff", "linear_emission"}:
            unlocks.append(event_scheduled_catalysts._unlock_candidate_for_event(row, item))
    return tuple(scheduled), tuple(unlocks)


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
