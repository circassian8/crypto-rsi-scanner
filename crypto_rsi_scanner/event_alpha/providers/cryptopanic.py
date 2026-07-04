"""CryptoPanic operational preflight helpers for Event Alpha research runs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import crypto_rsi_scanner.event_alpha.notifications.provider_status as event_provider_status
from ...event_providers import cryptopanic as cryptopanic_provider
from . import provider_health as event_provider_health
from . import source_packs as event_source_packs


@dataclass(frozen=True)
class CryptoPanicPreflightReport:
    profile: str
    artifact_namespace: str
    token_configured: bool
    live_enabled: bool
    endpoint_url: str
    plan: str
    weekly_limit: int
    rolling_7d_usage: int
    daily_soft_limit: int
    today_usage: int
    per_run_limit: int
    remaining_weekly: int | None
    provider_health_status: str
    provider_in_backoff: bool
    provider_health_keys: tuple[str, ...]
    last_failure_class: str | None
    source_packs: tuple[str, ...]
    will_attempt_no_send: bool
    skip_reason: str | None
    status: str
    provider_health_path: Path
    request_ledger_path: Path | None


def cryptopanic_source_packs() -> tuple[str, ...]:
    return tuple(
        name
        for name, pack in sorted(event_source_packs.SOURCE_PACKS.items())
        if "cryptopanic" in set(pack.preferred_providers)
    )


def build_cryptopanic_preflight(
    *,
    profile: str,
    artifact_namespace: str,
    provider_status_report: event_provider_status.EventDiscoveryProviderStatus,
    provider_health_rows: Mapping[str, Mapping[str, Any]],
    provider_health_path: str | Path,
    request_ledger_path: str | Path | None,
    token_configured: bool,
    live_enabled: bool,
    endpoint_url: str,
    plan: str,
    weekly_limit: int,
    daily_soft_limit: int,
    per_run_limit: int,
    catalyst_search_providers: tuple[str, ...] = (),
    no_send: bool = True,
    now: datetime | None = None,
) -> CryptoPanicPreflightReport:
    observed = now or datetime.now(timezone.utc)
    usage = cryptopanic_provider.cryptopanic_usage_summary(
        request_ledger_path,
        now=observed,
        weekly_limit=weekly_limit,
        daily_soft_limit=daily_soft_limit,
    )
    health_items = _cryptopanic_health_items(provider_health_rows, now=observed)
    health_status = _combined_health_status(tuple(status for _, status, _ in health_items))
    keys = tuple(key for key, _, _ in health_items)
    last_failure = next(
        (
            str(row.get("last_error_class") or "")
            for _, status, row in health_items
            if status in {"backoff", "degraded"} and str(row.get("last_error_class") or "")
        ),
        None,
    )
    provider_ready = _cryptopanic_ready(provider_status_report)
    in_profile = "cryptopanic" in {item.strip().lower() for item in catalyst_search_providers if item.strip()}
    quota_exhausted = bool(usage.remaining_weekly is not None and usage.remaining_weekly <= 0)
    will_attempt = bool(
        no_send
        and live_enabled
        and token_configured
        and in_profile
        and provider_ready
        and health_status != "backoff"
        and not quota_exhausted
    )
    skip_reason = None
    if not will_attempt:
        if not token_configured:
            skip_reason = "missing_api_key"
        elif quota_exhausted:
            skip_reason = "quota_exhausted"
        elif not live_enabled:
            skip_reason = "profile_disabled"
        elif not in_profile:
            skip_reason = "provider_not_in_profile"
        elif health_status == "backoff":
            skip_reason = "provider_backoff"
        elif not provider_ready:
            skip_reason = "provider_not_ready"
        elif not no_send:
            skip_reason = "not_no_send_mode"
        else:
            skip_reason = "unknown"
    if not token_configured:
        status = "NOT_CONFIGURED"
    elif quota_exhausted:
        status = "QUOTA_EXHAUSTED"
    elif health_status == "backoff":
        status = "IN_BACKOFF"
    elif will_attempt:
        status = "READY"
    else:
        status = "UNKNOWN"
    return CryptoPanicPreflightReport(
        profile=profile,
        artifact_namespace=artifact_namespace,
        token_configured=bool(token_configured),
        live_enabled=bool(live_enabled),
        endpoint_url=endpoint_url,
        plan=plan,
        weekly_limit=int(weekly_limit),
        rolling_7d_usage=int(usage.rolling_7d_requests),
        daily_soft_limit=int(daily_soft_limit),
        today_usage=int(usage.today_requests),
        per_run_limit=int(per_run_limit),
        remaining_weekly=usage.remaining_weekly,
        provider_health_status=health_status,
        provider_in_backoff=health_status == "backoff",
        provider_health_keys=keys,
        last_failure_class=last_failure,
        source_packs=cryptopanic_source_packs(),
        will_attempt_no_send=will_attempt,
        skip_reason=skip_reason,
        status=status,
        provider_health_path=Path(provider_health_path),
        request_ledger_path=Path(request_ledger_path).expanduser() if request_ledger_path else None,
    )


def format_cryptopanic_preflight(report: CryptoPanicPreflightReport) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA CRYPTOPANIC PREFLIGHT (research-only)",
        "=" * 76,
        f"profile: {report.profile}",
        f"artifact_namespace: {report.artifact_namespace}",
        f"provider_health_path: {report.provider_health_path}",
        f"request_ledger_path: {report.request_ledger_path or 'none'}",
        f"endpoint: {report.endpoint_url.rstrip('/')}/posts/",
        f"plan: {report.plan}",
        f"status: {report.status}",
        f"CryptoPanic token configured: {_yes_no(report.token_configured)} (redacted)",
        f"CryptoPanic live enabled: {_yes_no(report.live_enabled)}",
        f"weekly usage: {report.rolling_7d_usage}/{report.weekly_limit}",
        f"weekly remaining: {report.remaining_weekly if report.remaining_weekly is not None else 'unlimited'}",
        f"daily soft usage: {report.today_usage}/{report.daily_soft_limit}",
        f"per-run cap: {report.per_run_limit}",
        f"provider health status: {report.provider_health_status}",
        f"provider in backoff: {_yes_no(report.provider_in_backoff)}",
        f"last failure class: {report.last_failure_class or 'none'}",
        f"will attempt CryptoPanic in no-send mode: {_yes_no(report.will_attempt_no_send)}",
        f"skip reason: {report.skip_reason or 'none'}",
        "provider health keys:",
    ]
    lines.extend(f"- {key}" for key in report.provider_health_keys) if report.provider_health_keys else lines.append("- none")
    lines.append("CryptoPanic-dependent source packs:")
    lines.extend(f"- {pack}" for pack in report.source_packs) if report.source_packs else lines.append("- none")
    lines.append("")
    lines.append("Reset only CryptoPanic backoff with:")
    lines.append(f"make event-alpha-provider-health-reset PROFILE={report.profile} SERVICE=cryptopanic CONFIRM=1")
    lines.append("No API token value is printed. No sends, trades, paper rows, normal RSI rows, or triggers are changed.")
    return "\n".join(lines)


def _cryptopanic_ready(report: event_provider_status.EventDiscoveryProviderStatus) -> bool:
    for item in report.sources:
        if item.name == "cryptopanic_news":
            return bool(item.ready)
    return False


def _cryptopanic_health_items(
    rows: Mapping[str, Mapping[str, Any]],
    *,
    now: datetime,
) -> tuple[tuple[str, str, Mapping[str, Any]], ...]:
    out: list[tuple[str, str, Mapping[str, Any]]] = []
    for key, row in rows.items():
        joined = " ".join(str(value or "").casefold() for value in (
            key,
            row.get("provider"),
            row.get("provider_key"),
            row.get("provider_service"),
        ))
        if "cryptopanic" not in joined:
            continue
        out.append((str(row.get("provider_key") or key), event_provider_health.provider_health_status(row, now=now), row))
    return tuple(out)


def _combined_health_status(statuses: tuple[str, ...]) -> str:
    if not statuses:
        return "not_observed"
    if "backoff" in statuses:
        return "backoff"
    if "degraded" in statuses:
        return "degraded"
    return "healthy"


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
