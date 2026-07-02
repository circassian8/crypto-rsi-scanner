"""Unified official-exchange activation artifacts for Event Alpha research.

The activation layer is a provider-neutral status view over official exchange
announcement artifacts. It never fetches providers, sends notifications, opens
paper/live trades, writes normal RSI rows, executes orders, or creates
``TRIGGERED_FADE``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from ... import config
from ..artifacts import paths as event_artifact_paths
from . import official_exchange as event_official_exchange


ACTIVATION_JSON = "event_official_exchange_activation.json"
ACTIVATION_MD = "event_official_exchange_activation.md"

PROVIDER_BYBIT_PUBLIC = "bybit_announcements_public"
PROVIDER_BINANCE_PUBLIC_OR_FIXTURE = "binance_announcements_public_or_fixture"
PROVIDER_BINANCE_SIGNED_LISTENER = "binance_announcements_signed_listener"

LEGACY_BYBIT_PROVIDER = "bybit_announcements"
LEGACY_BINANCE_PROVIDER = "binance_announcements"

SHARED_SCHEMA_FIELDS = (
    "provider",
    "mode",
    "configured",
    "live_call_allowed",
    "no_send_rehearsal",
    "request_ledger_path",
    "provider_health_key",
    "source_url_count",
    "announcements_seen",
    "official_events_written",
    "listing_candidates_written",
    "risk_candidates_written",
    "strict_alerts_created",
    "telegram_sends",
)

RISK_EVENT_TYPES = {"delisting", "trading_suspension", "maintenance"}
LISTING_SOURCE_PACKS = {
    "official_exchange_listing_pack",
    "official_perp_listing_pack",
    "listing_liquidity_pack",
    "perp_listing_squeeze_pack",
}
HEALTHY_STATUSES = {"observed_healthy", "observed_partial_success", "observed_no_results", "fixture_ready"}


@dataclass(frozen=True)
class OfficialExchangeActivationProviderRow:
    provider: str
    mode: str
    configured: bool
    live_call_allowed: bool
    no_send_rehearsal: bool
    request_ledger_path: str | None
    provider_health_key: str
    source_url_count: int
    announcements_seen: int
    official_events_written: int
    listing_candidates_written: int
    risk_candidates_written: int
    provider_health_status: str = "not_observed"
    strict_alerts_created: int = 0
    telegram_sends: int = 0
    trades_created: int = 0
    paper_trades_created: int = 0
    normal_rsi_signal_rows_written: int = 0
    triggered_fade_created: int = 0
    skip_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "mode": self.mode,
            "configured": self.configured,
            "live_call_allowed": self.live_call_allowed,
            "no_send_rehearsal": self.no_send_rehearsal,
            "request_ledger_path": self.request_ledger_path,
            "provider_health_key": self.provider_health_key,
            "provider_health_status": self.provider_health_status,
            "source_url_count": self.source_url_count,
            "announcements_seen": self.announcements_seen,
            "official_events_written": self.official_events_written,
            "listing_candidates_written": self.listing_candidates_written,
            "risk_candidates_written": self.risk_candidates_written,
            "strict_alerts_created": self.strict_alerts_created,
            "telegram_sends": self.telegram_sends,
            "trades_created": self.trades_created,
            "paper_trades_created": self.paper_trades_created,
            "normal_rsi_signal_rows_written": self.normal_rsi_signal_rows_written,
            "triggered_fade_created": self.triggered_fade_created,
            "skip_reason": self.skip_reason,
        }


@dataclass(frozen=True)
class OfficialExchangeActivationReport:
    profile: str
    artifact_namespace: str
    generated_at: str
    research_only: bool
    rows: tuple[OfficialExchangeActivationProviderRow, ...]
    activation_json_path: str
    activation_report_path: str
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "event_official_exchange_activation_v1",
            "row_type": "event_official_exchange_activation",
            "profile": self.profile,
            "artifact_namespace": self.artifact_namespace,
            "generated_at": self.generated_at,
            "research_only": self.research_only,
            "activation_json_path": self.activation_json_path,
            "activation_report_path": self.activation_report_path,
            "shared_schema_fields": list(SHARED_SCHEMA_FIELDS),
            "providers": [row.to_dict() for row in self.rows],
            "warnings": list(self.warnings),
        }


def build_activation_report(
    *,
    namespace_dir: str | Path,
    profile: str | None = None,
    artifact_namespace: str | None = None,
    observed_at: datetime | str | None = None,
    live_call_allowed_by_provider: Mapping[str, bool] | None = None,
    no_send_rehearsal_by_provider: Mapping[str, bool] | None = None,
    request_ledger_path_by_provider: Mapping[str, str | Path | None] | None = None,
    provider_health_status_by_key: Mapping[str, str] | None = None,
    warnings: Iterable[str] = (),
) -> OfficialExchangeActivationReport:
    base = Path(namespace_dir).expanduser()
    live_overrides = dict(live_call_allowed_by_provider or {})
    no_send_overrides = dict(no_send_rehearsal_by_provider or {})
    ledger_overrides = dict(request_ledger_path_by_provider or {})
    health_overrides = {str(key): str(value) for key, value in (provider_health_status_by_key or {}).items()}
    generated_at = _as_utc(_parse_time(observed_at) or datetime.now(timezone.utc)).isoformat()
    json_path = base / ACTIVATION_JSON
    md_path = base / ACTIVATION_MD

    announcements = _load_jsonl(base / event_official_exchange.EXCHANGE_ANNOUNCEMENTS_FILENAME)
    events = event_official_exchange.load_official_exchange_events(base)
    candidates = event_official_exchange.load_official_listing_candidates(base)

    bybit_rehearsal = _read_json(base / "event_bybit_announcements_rehearsal_report.json")
    bybit_ledger = base / "event_bybit_announcements_request_ledger.jsonl"

    bybit_counts = _counts_for_provider(
        provider=LEGACY_BYBIT_PROVIDER,
        announcements=announcements,
        events=events,
        candidates=candidates,
    )
    bybit_health = _provider_health_status(
        "bybit_announcements",
        health_overrides=health_overrides,
        fallback=str(
            bybit_rehearsal.get("provider_health_status")
            or ("fixture_ready" if bybit_counts["official_events_written"] else "")
        ),
    )
    bybit_configured = True
    bybit_live = bool(live_overrides.get(PROVIDER_BYBIT_PUBLIC, bybit_rehearsal.get("live_call_allowed") or False))
    bybit_no_send = bool(no_send_overrides.get(PROVIDER_BYBIT_PUBLIC, bybit_rehearsal.get("no_send", True)))
    bybit_ledger_path = ledger_overrides.get(PROVIDER_BYBIT_PUBLIC)
    if bybit_ledger_path is None and (bybit_ledger.exists() or bybit_live):
        bybit_ledger_path = bybit_ledger

    binance_counts = _counts_for_provider(
        provider=LEGACY_BINANCE_PROVIDER,
        announcements=announcements,
        events=events,
        candidates=candidates,
    )
    binance_fixture_path = getattr(config, "EVENT_ALPHA_OFFICIAL_EXCHANGE_BINANCE_PATH", None) or getattr(
        config,
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH",
        None,
    )
    binance_public_configured = bool(binance_counts["announcements_seen"] or _path_exists(binance_fixture_path))
    binance_public_health = _provider_health_status(
        "binance_announcements",
        health_overrides=health_overrides,
        fallback="fixture_ready" if binance_counts["official_events_written"] else "not_observed",
    )

    signed_configured = bool(
        getattr(config, "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE", False)
        and getattr(config, "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_KEY", "")
        and getattr(config, "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_SECRET", "")
    )
    signed_health = _provider_health_status(
        PROVIDER_BINANCE_SIGNED_LISTENER,
        health_overrides=health_overrides,
        fallback="not_observed",
    )

    rows = (
        OfficialExchangeActivationProviderRow(
            provider=PROVIDER_BYBIT_PUBLIC,
            mode="public_http_no_key",
            configured=bybit_configured,
            live_call_allowed=bybit_live,
            no_send_rehearsal=bybit_no_send,
            request_ledger_path=_display_path(bybit_ledger_path) if bybit_ledger_path else None,
            provider_health_key="bybit_announcements",
            provider_health_status=bybit_health,
            source_url_count=bybit_counts["source_url_count"],
            announcements_seen=bybit_counts["announcements_seen"],
            official_events_written=bybit_counts["official_events_written"],
            listing_candidates_written=bybit_counts["listing_candidates_written"],
            risk_candidates_written=bybit_counts["risk_candidates_written"],
            skip_reason=None if bybit_counts["announcements_seen"] else "no_bybit_announcements_artifact_rows_loaded",
        ),
        OfficialExchangeActivationProviderRow(
            provider=PROVIDER_BINANCE_PUBLIC_OR_FIXTURE,
            mode="public_or_fixture_parser",
            configured=binance_public_configured,
            live_call_allowed=False,
            no_send_rehearsal=True,
            request_ledger_path=None,
            provider_health_key="binance_announcements",
            provider_health_status=binance_public_health,
            source_url_count=binance_counts["source_url_count"],
            announcements_seen=binance_counts["announcements_seen"],
            official_events_written=binance_counts["official_events_written"],
            listing_candidates_written=binance_counts["listing_candidates_written"],
            risk_candidates_written=binance_counts["risk_candidates_written"],
            skip_reason=None if binance_counts["announcements_seen"] else "no_binance_public_or_fixture_rows_loaded",
        ),
        OfficialExchangeActivationProviderRow(
            provider=PROVIDER_BINANCE_SIGNED_LISTENER,
            mode="signed_websocket_listener",
            configured=signed_configured,
            live_call_allowed=False,
            no_send_rehearsal=True,
            request_ledger_path=_display_path(ledger_overrides.get(PROVIDER_BINANCE_SIGNED_LISTENER))
            if ledger_overrides.get(PROVIDER_BINANCE_SIGNED_LISTENER)
            else None,
            provider_health_key=PROVIDER_BINANCE_SIGNED_LISTENER,
            provider_health_status=signed_health,
            source_url_count=0,
            announcements_seen=0,
            official_events_written=0,
            listing_candidates_written=0,
            risk_candidates_written=0,
            skip_reason=None if signed_configured else "blocked_without_signed_listener_env",
        ),
    )
    return OfficialExchangeActivationReport(
        profile=str(profile or "unknown"),
        artifact_namespace=str(artifact_namespace or "unknown"),
        generated_at=generated_at,
        research_only=True,
        rows=rows,
        activation_json_path=event_artifact_paths.artifact_display_path(json_path),
        activation_report_path=event_artifact_paths.artifact_display_path(md_path),
        warnings=tuple(dict.fromkeys(str(item) for item in warnings if str(item))),
    )


def write_activation_artifacts(report: OfficialExchangeActivationReport, namespace_dir: str | Path) -> tuple[Path, Path]:
    base = Path(namespace_dir).expanduser()
    base.mkdir(parents=True, exist_ok=True)
    json_path = base / ACTIVATION_JSON
    md_path = base / ACTIVATION_MD
    json_path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(format_activation_report(report) + "\n", encoding="utf-8")
    return json_path, md_path


def format_activation_report(report: OfficialExchangeActivationReport) -> str:
    lines = [
        "# Event Alpha Official Exchange Activation",
        "",
        "Research-only. Not a trade signal. No Telegram sends, trades, paper trades, normal RSI rows, or Event Alpha TRIGGERED_FADE.",
        f"profile: {report.profile}",
        f"artifact_namespace: {report.artifact_namespace}",
        f"generated_at: {report.generated_at}",
        f"activation_json_path: {report.activation_json_path}",
        f"activation_report_path: {report.activation_report_path}",
        "",
        "## Provider Rows",
    ]
    for row in report.rows:
        lines.extend(
            [
                f"- {row.provider}",
                f"  mode: {row.mode}",
                f"  configured: {str(row.configured).lower()}",
                f"  live_call_allowed: {str(row.live_call_allowed).lower()}",
                f"  no_send_rehearsal: {str(row.no_send_rehearsal).lower()}",
                f"  request_ledger_path: {row.request_ledger_path or 'none'}",
                f"  provider_health_key: {row.provider_health_key}",
                f"  provider_health_status: {row.provider_health_status}",
                f"  source_url_count: {row.source_url_count}",
                f"  announcements_seen: {row.announcements_seen}",
                f"  official_events_written: {row.official_events_written}",
                f"  listing_candidates_written: {row.listing_candidates_written}",
                f"  risk_candidates_written: {row.risk_candidates_written}",
                f"  strict_alerts_created: {row.strict_alerts_created}",
                f"  telegram_sends: {row.telegram_sends}",
                f"  trades_created: {row.trades_created}",
                f"  paper_trades_created: {row.paper_trades_created}",
                f"  normal_rsi_signal_rows_written: {row.normal_rsi_signal_rows_written}",
                f"  triggered_fade_created: {row.triggered_fade_created}",
                f"  skip_reason: {row.skip_reason or 'none'}",
            ]
        )
    lines.extend(
        [
            "",
            "## Activation Runbook",
            "- Bybit first official exchange live rehearsal: public HTTP, no key, explicit allow flag, bounded pages/limit, no-send, ledger required.",
            "- Binance public/fixture second: fixture/public parser validation, no API key required, no live call by default.",
            "- Binance signed listener later: signed WebSocket only after explicit env vars and bounded listener command review.",
        ]
    )
    if report.warnings:
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {warning}" for warning in report.warnings)
    return "\n".join(lines)


def load_activation_report(path: str | Path | None) -> Mapping[str, Any]:
    if path is None:
        return {}
    source = Path(path).expanduser()
    if source.is_dir():
        source = source / ACTIVATION_JSON
    return _read_json(source)


def load_activation_rows(path: str | Path | None) -> tuple[dict[str, Any], ...]:
    payload = load_activation_report(path)
    rows = payload.get("providers") if isinstance(payload, Mapping) else None
    if not isinstance(rows, Iterable) or isinstance(rows, (str, bytes)):
        return ()
    return tuple(dict(row) for row in rows if isinstance(row, Mapping))


def activation_artifact_stats(namespace_dir: str | Path | None) -> dict[str, Any]:
    if namespace_dir is None:
        return {
            "status": "not_generated",
            "json_path": None,
            "report_path": None,
            "rows": (),
        }
    base = Path(namespace_dir).expanduser()
    json_path = base / ACTIVATION_JSON
    md_path = base / ACTIVATION_MD
    payload = _read_json(json_path)
    rows = load_activation_rows(json_path) if json_path.exists() else ()
    return {
        "status": "generated" if json_path.exists() or md_path.exists() else "not_generated",
        "json_path": event_artifact_paths.artifact_display_path(json_path) if json_path.exists() else None,
        "report_path": event_artifact_paths.artifact_display_path(md_path) if md_path.exists() else None,
        "rows": rows,
        "providers_loaded": tuple(str(row.get("provider") or "") for row in rows if str(row.get("provider") or "")),
        "generated_at": str(payload.get("generated_at") or "") if payload else None,
    }


def artifact_conflicts(namespace_dir: str | Path | None) -> dict[str, int]:
    out = {
        "official_exchange_activation_missing_shared_schema": 0,
        "official_exchange_activation_live_without_ledger": 0,
        "official_exchange_activation_signed_listener_secret_leak": 0,
        "official_exchange_activation_forbidden_side_effect_claim": 0,
    }
    if namespace_dir is None:
        return out
    base = Path(namespace_dir).expanduser()
    json_path = base / ACTIVATION_JSON
    md_path = base / ACTIVATION_MD
    if not json_path.exists() and not md_path.exists():
        return out
    texts: list[str] = []
    for path in (json_path, md_path):
        if path.exists():
            try:
                texts.append(path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                pass
    joined = "\n".join(texts)
    if PROVIDER_BINANCE_SIGNED_LISTENER in joined and _text_has_secret_like_value(joined):
        out["official_exchange_activation_signed_listener_secret_leak"] = 1
    rows = load_activation_rows(json_path)
    for row in rows:
        missing = [field for field in SHARED_SCHEMA_FIELDS if field not in row]
        if missing:
            out["official_exchange_activation_missing_shared_schema"] += 1
        if bool(row.get("live_call_allowed")):
            ledger = str(row.get("request_ledger_path") or "").strip()
            if not ledger or not _displayed_path_exists(base, ledger):
                out["official_exchange_activation_live_without_ledger"] += 1
        if any(_safe_int(row.get(key)) for key in (
            "strict_alerts_created",
            "telegram_sends",
            "trades_created",
            "paper_trades_created",
            "normal_rsi_signal_rows_written",
            "triggered_fade_created",
        )):
            out["official_exchange_activation_forbidden_side_effect_claim"] += 1
    return out


def row_is_healthy(row: Mapping[str, Any]) -> bool:
    status = str(row.get("provider_health_status") or "").strip()
    if status in HEALTHY_STATUSES:
        return True
    return int(row.get("official_events_written") or 0) > 0 and str(row.get("mode") or "") == "public_or_fixture_parser"


def _counts_for_provider(
    *,
    provider: str,
    announcements: Iterable[Mapping[str, Any]],
    events: Iterable[Mapping[str, Any]],
    candidates: Iterable[Mapping[str, Any]],
) -> dict[str, int]:
    announcement_rows = [dict(row) for row in announcements if str(row.get("provider") or "") == provider]
    event_rows = [dict(row) for row in events if str(row.get("provider") or "") == provider]
    candidate_rows = [dict(row) for row in candidates if str(row.get("provider") or "") == provider]
    source_url_count = sum(1 for row in (*announcement_rows, *event_rows, *candidate_rows) if str(row.get("source_url") or row.get("url") or "").strip())
    risk_count = sum(
        1
        for row in candidate_rows
        if str(row.get("event_type") or "") in RISK_EVENT_TYPES
        or str(row.get("source_pack") or "") == "official_exchange_risk_pack"
        or str(row.get("opportunity_type") or "").upper() == "RISK_ONLY"
    )
    listing_count = sum(
        1
        for row in candidate_rows
        if (
            str(row.get("source_pack") or "") in LISTING_SOURCE_PACKS
            or str(row.get("event_type") or "") not in RISK_EVENT_TYPES
        )
    )
    return {
        "source_url_count": source_url_count,
        "announcements_seen": len(announcement_rows),
        "official_events_written": len(event_rows),
        "listing_candidates_written": listing_count,
        "risk_candidates_written": risk_count,
    }


def _load_jsonl(path: Path) -> tuple[dict[str, Any], ...]:
    if not path.exists():
        return ()
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, Mapping):
            out.append(dict(parsed))
    return tuple(out)


def _read_json(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        return {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, Mapping) else {}


def _provider_health_status(
    key: str,
    *,
    health_overrides: Mapping[str, str],
    fallback: str,
) -> str:
    if key in health_overrides:
        return str(health_overrides[key] or "not_observed")
    return str(fallback or "not_observed")


def _path_exists(path: str | Path | None) -> bool:
    if path is None:
        return False
    try:
        return Path(path).expanduser().exists()
    except (OSError, TypeError):
        return False


def _display_path(path: str | Path | None) -> str | None:
    if path is None:
        return None
    return event_artifact_paths.artifact_display_path(Path(path).expanduser())


def _displayed_path_exists(base: Path, displayed: str) -> bool:
    if not displayed:
        return False
    path = Path(displayed).expanduser()
    if path.exists():
        return True
    return (base / displayed).exists()


def _parse_time(value: datetime | str | None) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _safe_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _text_has_secret_like_value(text: str) -> bool:
    patterns = (
        r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}",
        r"\bghp_[A-Za-z0-9_]{20,}",
        r"(?i)(api[_-]?key|secret|token)\s*[=:]\s*['\"][A-Za-z0-9._-]{20,}['\"]",
        r"(?i)(api[_-]?key|secret|token)\s+[A-Za-z0-9._-]{24,}",
        r"(?i)x-mbx-apikey\s*[=:]\s*['\"][A-Za-z0-9._-]{20,}['\"]",
        r"(?i)signature=[A-Za-z0-9._-]{16,}",
    )
    return any(re.search(pattern, text) for pattern in patterns)
