"""Provider circuit-breaker state for Event Alpha research providers."""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class EventProviderHealthConfig:
    path: Path
    max_consecutive_failures: int = 3
    backoff_minutes: float = 30.0
    fail_fast_on_dns: bool = True


@dataclass(frozen=True)
class ProviderHealthDecision:
    provider: str
    allowed: bool
    reason: str | None = None
    disabled_until: str | None = None


class HealthCheckedProvider:
    """Small circuit-breaker wrapper for research providers with ``search`` APIs."""

    def __init__(
        self,
        provider: Any,
        *,
        cfg: EventProviderHealthConfig,
        provider_kind: str = "catalyst_search",
        provider_service: str | None = None,
        provider_role: str = "catalyst_search",
    ) -> None:
        self.provider = provider
        self.cfg = cfg
        self.name = str(getattr(provider, "name", "provider"))
        self.provider_kind = provider_kind
        self.provider_service = provider_service or _service_from_name(self.name)
        self.provider_role = provider_role
        self.provider_key = provider_health_key(self.name, service=self.provider_service, role=self.provider_role)
        self.last_warnings: tuple[str, ...] = ()

    def search(
        self,
        queries: Iterable[Any],
        *,
        max_results_per_query: int,
        now: datetime | None = None,
    ) -> Any:
        query_rows = tuple(queries)
        decision = provider_allowed(
            self.name,
            cfg=self.cfg,
            now=now,
            provider_service=self.provider_service,
            provider_role=self.provider_role,
        )
        if not decision.allowed:
            self.last_warnings = (decision.reason or "provider in backoff",)
            return _empty_search_result(self.name, query_rows, decision.reason or "provider in backoff")
        try:
            result = self.provider.search(query_rows, max_results_per_query=max_results_per_query, now=now)
        except Exception as exc:  # noqa: BLE001 - fail-soft research wrapper
            record_provider_failure(
                self.name,
                exc,
                cfg=self.cfg,
                now=now,
                provider_kind=self.provider_kind,
                provider_service=self.provider_service,
                provider_role=self.provider_role,
            )
            self.last_warnings = (f"{self.name} failed: {exc}",)
            return _empty_search_result(self.name, query_rows, f"{self.name} failed: {exc}")
        warnings = tuple(getattr(result, "warnings", ()) or ())
        self.last_warnings = tuple(str(warning) for warning in warnings if str(warning))
        if warnings and int(getattr(result, "provider_fetch_count", 0) or 0) > 0:
            record_provider_failure(
                self.name,
                warnings[0],
                cfg=self.cfg,
                now=now,
                provider_kind=self.provider_kind,
                provider_service=self.provider_service,
                provider_role=self.provider_role,
            )
        else:
            record_provider_success(
                self.name,
                cfg=self.cfg,
                now=now,
                provider_kind=self.provider_kind,
                provider_service=self.provider_service,
                provider_role=self.provider_role,
            )
        return result


class HealthCheckedEventProvider:
    """Circuit-breaker wrapper for event-source providers with ``fetch_events``."""

    def __init__(
        self,
        provider: Any,
        *,
        cfg: EventProviderHealthConfig,
        provider_kind: str = "event_source",
        provider_service: str | None = None,
        provider_role: str = "event_source",
    ) -> None:
        self.provider = provider
        self.cfg = cfg
        self.name = str(getattr(provider, "name", "provider"))
        self.provider_kind = provider_kind
        self.provider_service = provider_service or _service_from_name(self.name)
        self.provider_role = provider_role
        self.provider_key = provider_health_key(self.name, service=self.provider_service, role=self.provider_role)
        self.last_warnings: tuple[str, ...] = ()

    def fetch_events(self, start: datetime, end: datetime, now: datetime | None = None) -> list[Any]:
        observed = _as_utc(now or datetime.now(timezone.utc))
        decision = provider_allowed(
            self.name,
            cfg=self.cfg,
            now=observed,
            provider_service=self.provider_service,
            provider_role=self.provider_role,
        )
        if not decision.allowed:
            self.last_warnings = (decision.reason or f"provider {self.name} in backoff",)
            return []
        try:
            rows = list(_call_with_optional_now(self.provider.fetch_events, start, end, now=observed))
        except Exception as exc:  # noqa: BLE001 - fail-soft research wrapper
            record_provider_failure(
                self.name,
                exc,
                cfg=self.cfg,
                now=observed,
                provider_kind=self.provider_kind,
                provider_service=self.provider_service,
                provider_role=self.provider_role,
            )
            self.last_warnings = (f"{self.name} failed: {type(exc).__name__}: {exc}",)
            return []
        self.last_warnings = tuple(str(warning) for warning in getattr(self.provider, "last_warnings", ()) or ())
        if self.last_warnings:
            record_provider_failure(
                self.name,
                self.last_warnings[0],
                cfg=self.cfg,
                now=observed,
                provider_kind=self.provider_kind,
                provider_service=self.provider_service,
                provider_role=self.provider_role,
            )
        else:
            record_provider_success(
                self.name,
                cfg=self.cfg,
                now=observed,
                provider_kind=self.provider_kind,
                provider_service=self.provider_service,
                provider_role=self.provider_role,
            )
        return rows


class HealthCheckedUniverseProvider:
    """Circuit-breaker wrapper for asset-universe enrichment providers."""

    def __init__(
        self,
        provider: Any,
        *,
        cfg: EventProviderHealthConfig,
        provider_kind: str = "enrichment",
        provider_service: str | None = None,
        provider_role: str = "universe",
    ) -> None:
        self.provider = provider
        self.cfg = cfg
        self.name = str(getattr(provider, "name", "provider"))
        self.provider_kind = provider_kind
        self.provider_service = provider_service or _service_from_name(self.name)
        self.provider_role = provider_role
        self.provider_key = provider_health_key(self.name, service=self.provider_service, role=self.provider_role)
        self.last_warnings: tuple[str, ...] = ()

    def fetch_assets(self, now: datetime | None = None) -> list[Any]:
        observed = _as_utc(now or datetime.now(timezone.utc))
        decision = provider_allowed(
            self.name,
            cfg=self.cfg,
            now=observed,
            provider_service=self.provider_service,
            provider_role=self.provider_role,
        )
        if not decision.allowed:
            self.last_warnings = (decision.reason or f"provider {self.name} in backoff",)
            return []
        try:
            rows = list(_call_with_optional_now(self.provider.fetch_assets, now=observed))
        except Exception as exc:  # noqa: BLE001 - fail-soft research wrapper
            record_provider_failure(
                self.name,
                exc,
                cfg=self.cfg,
                now=observed,
                provider_kind=self.provider_kind,
                provider_service=self.provider_service,
                provider_role=self.provider_role,
            )
            self.last_warnings = (f"{self.name} failed: {type(exc).__name__}: {exc}",)
            return []
        self.last_warnings = tuple(str(warning) for warning in getattr(self.provider, "last_warnings", ()) or ())
        if self.last_warnings:
            record_provider_failure(
                self.name,
                self.last_warnings[0],
                cfg=self.cfg,
                now=observed,
                provider_kind=self.provider_kind,
                provider_service=self.provider_service,
                provider_role=self.provider_role,
            )
        else:
            record_provider_success(
                self.name,
                cfg=self.cfg,
                now=observed,
                provider_kind=self.provider_kind,
                provider_service=self.provider_service,
                provider_role=self.provider_role,
            )
        return rows


class HealthCheckedDerivativesProvider:
    """Circuit-breaker wrapper for derivatives enrichment providers."""

    def __init__(
        self,
        provider: Any,
        *,
        cfg: EventProviderHealthConfig,
        provider_kind: str = "enrichment",
        provider_service: str | None = None,
        provider_role: str = "derivatives",
    ) -> None:
        self.provider = provider
        self.cfg = cfg
        self.name = str(getattr(provider, "name", "provider"))
        self.provider_kind = provider_kind
        self.provider_service = provider_service or _service_from_name(self.name)
        self.provider_role = provider_role
        self.provider_key = provider_health_key(self.name, service=self.provider_service, role=self.provider_role)
        self.last_warnings: tuple[str, ...] = ()

    def fetch_snapshots(self, now: datetime | None = None) -> dict[str, Any]:
        observed = _as_utc(now or datetime.now(timezone.utc))
        decision = provider_allowed(
            self.name,
            cfg=self.cfg,
            now=observed,
            provider_service=self.provider_service,
            provider_role=self.provider_role,
        )
        if not decision.allowed:
            self.last_warnings = (decision.reason or f"provider {self.name} in backoff",)
            return {}
        try:
            rows = dict(_call_with_optional_now(self.provider.fetch_snapshots, now=observed))
        except Exception as exc:  # noqa: BLE001 - fail-soft research wrapper
            record_provider_failure(
                self.name,
                exc,
                cfg=self.cfg,
                now=observed,
                provider_kind=self.provider_kind,
                provider_service=self.provider_service,
                provider_role=self.provider_role,
            )
            self.last_warnings = (f"{self.name} failed: {type(exc).__name__}: {exc}",)
            return {}
        self.last_warnings = tuple(str(warning) for warning in getattr(self.provider, "last_warnings", ()) or ())
        if self.last_warnings:
            record_provider_failure(
                self.name,
                self.last_warnings[0],
                cfg=self.cfg,
                now=observed,
                provider_kind=self.provider_kind,
                provider_service=self.provider_service,
                provider_role=self.provider_role,
            )
        else:
            record_provider_success(
                self.name,
                cfg=self.cfg,
                now=observed,
                provider_kind=self.provider_kind,
                provider_service=self.provider_service,
                provider_role=self.provider_role,
            )
        return rows


def load_provider_health(path: str | Path) -> dict[str, dict[str, Any]]:
    p = Path(path).expanduser()
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if isinstance(raw, Mapping):
        providers = raw.get("providers") if isinstance(raw.get("providers"), Mapping) else raw
        return {str(key): dict(value) for key, value in providers.items() if isinstance(value, Mapping)}
    return {}


def write_provider_health(path: str | Path, rows: Mapping[str, Mapping[str, Any]]) -> None:
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "event_provider_health_v1",
        "providers": {str(key): dict(value) for key, value in rows.items()},
    }
    p.write_text(json.dumps(_json_ready(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _call_with_optional_now(method: Any, *args: Any, now: datetime) -> Any:
    """Call provider methods with a deterministic clock only when supported."""
    try:
        signature = inspect.signature(method)
    except (TypeError, ValueError):
        return method(*args)
    parameters = signature.parameters
    accepts_now = "now" in parameters or any(
        param.kind == inspect.Parameter.VAR_KEYWORD for param in parameters.values()
    )
    if accepts_now:
        return method(*args, now=now)
    return method(*args)


def provider_allowed(
    provider: str,
    *,
    cfg: EventProviderHealthConfig,
    now: datetime | None = None,
    provider_service: str | None = None,
    provider_role: str | None = None,
) -> ProviderHealthDecision:
    rows = load_provider_health(cfg.path)
    key = provider_health_key(provider, service=provider_service, role=provider_role)
    row = rows.get(key) or rows.get(provider) or {}
    disabled_until = _dt(row.get("disabled_until"))
    observed = _as_utc(now or datetime.now(timezone.utc))
    if disabled_until is not None and disabled_until > observed:
        return ProviderHealthDecision(
            provider=key,
            allowed=False,
            reason=f"provider {key} in backoff until {disabled_until.isoformat()}",
            disabled_until=disabled_until.isoformat(),
        )
    return ProviderHealthDecision(provider=key, allowed=True)


def record_provider_success(
    provider: str,
    *,
    cfg: EventProviderHealthConfig,
    run_id: str | None = None,
    now: datetime | None = None,
    provider_kind: str | None = None,
    provider_service: str | None = None,
    provider_role: str | None = None,
) -> dict[str, Any]:
    rows = load_provider_health(cfg.path)
    observed = _as_utc(now or datetime.now(timezone.utc)).isoformat()
    key = provider_health_key(provider, service=provider_service, role=provider_role)
    row = dict(rows.get(key) or rows.get(provider) or {})
    row.update({
        "provider": provider,
        "provider_key": key,
        "provider_service": provider_service or row.get("provider_service") or _service_from_name(provider),
        "provider_role": provider_role or row.get("provider_role") or provider_kind or "unclassified",
        "last_success_at": observed,
        "consecutive_failures": 0,
        "disabled_until": None,
        "last_error_class": None,
        "run_id": run_id,
    })
    if provider_kind:
        row["provider_kind"] = provider_kind
    rows[key] = row
    write_provider_health(cfg.path, rows)
    return row


def record_provider_failure(
    provider: str,
    error: object,
    *,
    cfg: EventProviderHealthConfig,
    run_id: str | None = None,
    now: datetime | None = None,
    provider_kind: str | None = None,
    provider_service: str | None = None,
    provider_role: str | None = None,
) -> dict[str, Any]:
    rows = load_provider_health(cfg.path)
    observed_dt = _as_utc(now or datetime.now(timezone.utc))
    key = provider_health_key(provider, service=provider_service, role=provider_role)
    row = dict(rows.get(key) or rows.get(provider) or {})
    failures = int(row.get("consecutive_failures") or 0) + 1
    error_class = _error_class(error)
    disabled_until = None
    if failures >= max(1, cfg.max_consecutive_failures) or (cfg.fail_fast_on_dns and _dns_like(error)):
        disabled_until = (observed_dt + timedelta(minutes=max(0.0, cfg.backoff_minutes))).isoformat()
    row.update({
        "provider": provider,
        "provider_key": key,
        "provider_service": provider_service or row.get("provider_service") or _service_from_name(provider),
        "provider_role": provider_role or row.get("provider_role") or provider_kind or "unclassified",
        "last_failure_at": observed_dt.isoformat(),
        "consecutive_failures": failures,
        "disabled_until": disabled_until,
        "last_error_class": error_class,
        "run_id": run_id,
    })
    if provider_kind:
        row["provider_kind"] = provider_kind
    rows[key] = row
    write_provider_health(cfg.path, rows)
    return row


def format_provider_health_report(rows: Mapping[str, Mapping[str, Any]]) -> str:
    lines = [
        "=" * 76,
        "EVENT PROVIDER HEALTH (research-only)",
        "=" * 76,
        f"providers={len(rows)}",
    ]
    if not rows:
        lines.append("No provider health rows found.")
        return "\n".join(lines)
    lines.append("")
    lines.append("service health:")
    for service, items in _service_summary(rows).items():
        failures = sum(int(row.get("consecutive_failures") or 0) for _key, row in items)
        disabled = [
            str(row.get("provider_role") or row.get("provider_kind") or key)
            for key, row in items
            if row.get("disabled_until")
        ]
        status = "degraded" if failures or disabled else "healthy"
        lines.append(
            f"- {service}: {status} roles={len(items)} failures={failures} "
            f"disabled_roles={','.join(disabled) if disabled else 'none'}"
        )
    lines.append("")
    lines.append("role health:")
    grouped: dict[str, list[tuple[str, Mapping[str, Any]]]] = {}
    for provider, row in sorted(rows.items()):
        grouped.setdefault(str(row.get("provider_role") or row.get("provider_kind") or "unclassified"), []).append(
            (provider, row)
        )
    order = ("event_source", "enrichment", "catalyst_search", "llm", "unclassified")
    for group in [*order, *sorted(set(grouped) - set(order))]:
        items = grouped.get(group)
        if not items:
            continue
        lines.append("")
        lines.append(f"{group}:")
        for provider, row in items:
            lines.append(
                f"- {row.get('provider_key') or provider}: "
                f"service={row.get('provider_service') or _service_from_name(provider)} "
                f"failures={int(row.get('consecutive_failures') or 0)} "
                f"disabled_until={row.get('disabled_until') or 'none'} "
                f"last_success={row.get('last_success_at') or 'never'} "
                f"last_failure={row.get('last_failure_at') or 'never'} "
                f"last_error={row.get('last_error_class') or 'none'}"
            )
    return "\n".join(lines)


def provider_health_key(provider: str, *, service: str | None = None, role: str | None = None) -> str:
    """Return the health storage key, preserving legacy name-only callers."""
    clean_provider = str(provider or "provider").strip() or "provider"
    clean_service = _service_from_name(service or clean_provider)
    clean_role = str(role or "").strip()
    return f"{clean_service}:{clean_role}" if clean_role else clean_provider


def _service_summary(rows: Mapping[str, Mapping[str, Any]]) -> dict[str, list[tuple[str, Mapping[str, Any]]]]:
    grouped: dict[str, list[tuple[str, Mapping[str, Any]]]] = {}
    for key, row in sorted(rows.items()):
        service = str(row.get("provider_service") or _service_from_name(str(row.get("provider") or key)))
        grouped.setdefault(service, []).append((key, row))
    return grouped


def _service_from_name(name: object) -> str:
    text = str(name or "provider").strip().casefold()
    aliases = {
        "project_blog_rss": "rss",
        "prediction_market_events": "polymarket",
        "coingecko_universe": "coingecko",
        "coinalyze": "coinalyze",
        "cryptopanic": "cryptopanic",
        "gdelt": "gdelt",
        "openai": "openai",
    }
    return aliases.get(text, text.replace("_provider", "") or "provider")


def _empty_search_result(provider: str, queries: tuple[Any, ...], warning: str) -> Any:
    from . import event_catalyst_search

    return event_catalyst_search.CatalystSearchRunResult(
        provider=provider,
        queries=queries,
        warnings=(warning,),
        query_count=len(queries),
    )


def _error_class(error: object) -> str:
    if isinstance(error, BaseException):
        return type(error).__name__
    text = str(error or "").strip()
    return text.split(":", 1)[0] if text else "UnknownError"


def _dns_like(error: object) -> bool:
    text = f"{type(error).__name__ if isinstance(error, BaseException) else ''} {error}".casefold()
    return any(token in text for token in ("dns", "name resolution", "nodename", "gaierror", "temporary failure in name resolution"))


def _dt(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _as_utc(parsed)


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, datetime):
        return _as_utc(value).isoformat()
    return value
