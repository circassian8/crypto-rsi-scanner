"""Bounded targeted market refresh for high-value Event Alpha families.

The coordinator is deliberately inert unless enabled by candidate mode or an
explicit targeted-refresh setting. It performs at most one provider batch call,
deduplicates by canonical asset, and writes research-only lineage artifacts.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .... import config
from ...artifacts import paths as event_artifact_paths
from ...artifacts import schema_v1
from .. import market_anomaly_scanner as event_market_anomaly_scanner
from .. import watchlist_market as event_watchlist_market
from .models import EventNearMissConfig, EventTargetedMarketRefreshQueueItem


TARGETED_MARKET_REFRESH_LEDGER_FILENAME = "event_targeted_market_refresh_ledger.jsonl"
TARGETED_MARKET_REFRESH_REPORT_JSON = "event_targeted_market_refresh_report.json"
TARGETED_MARKET_REFRESH_REPORT_MD = "event_targeted_market_refresh_report.md"
_TRUTHY = {"1", "true", "yes", "on"}
_SAFETY = {
    "research_only": True,
    "no_send_rehearsal": True,
    "strict_alerts_created": 0,
    "telegram_sends": 0,
    "trades_created": 0,
    "paper_trades_created": 0,
    "normal_rsi_signal_rows_written": 0,
    "triggered_fade_created": 0,
}


@dataclass(frozen=True)
class EventTargetedMarketRefreshResult:
    enabled: bool
    refresh_run_id: str
    provider: str
    queue: tuple[EventTargetedMarketRefreshQueueItem, ...]
    ledger_rows: tuple[dict[str, Any], ...]
    market_rows: tuple[dict[str, Any], ...]
    snapshot_rows: tuple[dict[str, Any], ...]
    ledger_path: Path
    report_json_path: Path
    report_md_path: Path
    request_count: int = 0
    attempted_assets: int = 0
    refreshed_assets: int = 0
    persisted_snapshot_rows: int = 0
    timed_out: bool = False
    warnings: tuple[str, ...] = ()


def targeted_refresh_enabled(*, explicit_enabled: bool = False, candidate_mode: bool | None = None) -> bool:
    if candidate_mode is None:
        candidate_mode = _env_truthy("RSI_EVENT_ALPHA_BURN_IN_CANDIDATE_MODE")
    return bool(explicit_enabled or candidate_mode)


def runtime_targeted_market_provider() -> event_watchlist_market.EventWatchlistMarketProvider | None:
    """Return a live provider only behind explicit, environment-owned gates."""
    candidate_mode = _env_truthy("RSI_EVENT_ALPHA_BURN_IN_CANDIDATE_MODE")
    targeted_enabled = _env_truthy("RSI_EVENT_ALPHA_TARGETED_MARKET_REFRESH_ENABLED")
    if not (candidate_mode or targeted_enabled):
        return None
    if not _env_truthy("RSI_EVENT_DISCOVERY_UNIVERSE_LIVE"):
        return None
    return event_watchlist_market.CoinGeckoWatchlistMarketProvider(live_enabled=True)


def select_targeted_market_refresh_families(
    rows: Iterable[Mapping[str, Any] | object],
    *,
    cfg: EventNearMissConfig | None = None,
) -> tuple[EventTargetedMarketRefreshQueueItem, ...]:
    """Select one highest-priority candidate family per canonical asset."""
    cfg = cfg or EventNearMissConfig()
    candidates: dict[str, tuple[tuple[int, float, str], dict[str, Any]]] = {}
    family_ids: dict[str, set[str]] = {}
    for value in rows:
        row = _row(value)
        if not row or not _needs_targeted_refresh(row):
            continue
        canonical = _canonical_asset_id(row)
        if not canonical or canonical in {"sector", "unknown"}:
            continue
        family_id = _family_id(row)
        family_ids.setdefault(canonical, set()).add(family_id)
        bucket, bucket_rank = _priority_bucket(row, cfg=cfg)
        score = _score(row)
        sort_key = (bucket_rank, -score, family_id)
        current = candidates.get(canonical)
        if current is None or sort_key < current[0]:
            selected = dict(row)
            selected["_targeted_priority_bucket"] = bucket
            candidates[canonical] = (sort_key, selected)
    ordered = sorted(candidates.items(), key=lambda item: item[1][0])
    limit = min(20, max(0, int(cfg.max_market_refresh_assets or 0)))
    if limit <= 0:
        return ()
    out: list[EventTargetedMarketRefreshQueueItem] = []
    for canonical, (_sort_key, row) in ordered[:limit]:
        symbol = str(row.get("symbol") or row.get("asset_symbol") or "").upper()
        coin_id = str(row.get("coin_id") or row.get("asset_coin_id") or canonical)
        bucket = str(row.get("_targeted_priority_bucket") or "fresh_candidate")
        family = _family_id(row)
        out.append(EventTargetedMarketRefreshQueueItem(
            refresh_id=f"tmr:{_digest(canonical + '|' + family)}",
            symbol=symbol,
            coin_id=coin_id,
            core_opportunity_id=_optional_text(row.get("core_opportunity_id")),
            hypothesis_id=_optional_text(row.get("hypothesis_id")),
            incident_id=_optional_text(row.get("incident_id")),
            reason=_refresh_reason(row),
            current_market_source=_optional_text(row.get("market_context_source") or row.get("market_data_source")),
            current_market_age_seconds=_float(row.get("market_context_age_seconds")),
            priority_score=_score(row),
            canonical_asset_id=canonical,
            priority_bucket=bucket,
            candidate_family_ids=tuple(sorted(family_ids.get(canonical) or {family})),
        ))
    return tuple(out)


def run_targeted_market_refresh(
    rows: Iterable[Mapping[str, Any] | object],
    *,
    namespace_dir: str | Path,
    profile: str,
    artifact_namespace: str,
    run_mode: str,
    run_id: str,
    provider: event_watchlist_market.EventWatchlistMarketProvider | object | None = None,
    cfg: EventNearMissConfig | None = None,
    enabled: bool | None = None,
    now: datetime | None = None,
) -> EventTargetedMarketRefreshResult:
    cfg = cfg or EventNearMissConfig()
    active = targeted_refresh_enabled(explicit_enabled=cfg.market_refresh_enabled) if enabled is None else bool(enabled)
    directory = Path(namespace_dir).expanduser()
    ledger_path = directory / TARGETED_MARKET_REFRESH_LEDGER_FILENAME
    report_json_path = directory / TARGETED_MARKET_REFRESH_REPORT_JSON
    report_md_path = directory / TARGETED_MARKET_REFRESH_REPORT_MD
    observed = _as_utc(now or datetime.now(timezone.utc))
    refresh_run_id = f"targeted-market:{_digest(run_id + '|' + observed.isoformat())}"
    queue = select_targeted_market_refresh_families(rows, cfg=cfg) if active else ()
    provider_name = str(getattr(provider, "name", None) or "none")
    warnings: list[str] = []
    fetched_rows: list[dict[str, Any]] = []
    error_class = ""
    request_count = 0
    timed_out = False
    started = time.monotonic()
    started_at = datetime.now(timezone.utc)
    if active and queue and provider is not None:
        request_count = 1
        try:
            fetched, provider_warnings = _fetch_provider_batch(
                provider,
                tuple(item.coin_id for item in queue),
                max_assets=len(queue),
                timeout_seconds=max(0.1, float(cfg.market_refresh_timeout_seconds or 5.0)),
            )
            fetched_rows = [dict(row) for row in fetched if isinstance(row, Mapping)]
            warnings.extend(str(value) for value in provider_warnings if str(value))
        except Exception as exc:  # noqa: BLE001 - bounded research provider path is fail-soft
            error_class = type(exc).__name__
            warnings.append(f"targeted_market_refresh_failed:{error_class}")
    elif active and queue:
        warnings.append("targeted_market_refresh_provider_unavailable")
    duration = max(0.0, time.monotonic() - started)
    timeout_seconds = max(0.1, float(cfg.market_refresh_timeout_seconds or 5.0))
    if request_count and duration > timeout_seconds:
        timed_out = True
        fetched_rows = []
        error_class = "TimeoutError"
        warnings.append("targeted_market_refresh_timeout")
    finished_at = datetime.now(timezone.utc)
    selected_assets = {item.canonical_asset_id for item in queue}
    fetched_rows = [row for row in fetched_rows if _canonical_asset_id(row) in selected_assets]
    snapshots, _anomalies = event_market_anomaly_scanner.scan_market_rows(
        fetched_rows,
        cfg=event_market_anomaly_scanner.MarketAnomalyScannerConfig(max_assets=len(queue) or 1),
        observed_at=observed,
        profile=profile,
        artifact_namespace=artifact_namespace,
        run_mode=run_mode,
        run_id=run_id,
    )
    snapshot_rows = tuple(_annotate_snapshot(row, refresh_run_id, provider_name, ledger_path, report_json_path) for row in snapshots)
    snapshot_by_asset = {_canonical_asset_id(row): row for row in snapshot_rows}
    ledger_rows = tuple(
        _ledger_row(
            item,
            refresh_run_id=refresh_run_id,
            provider=provider_name,
            snapshot=snapshot_by_asset.get(item.canonical_asset_id),
            active=active,
            attempted=bool(request_count),
            timed_out=timed_out,
            error_class=error_class,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=duration,
            timeout_seconds=timeout_seconds,
            run_id=run_id,
            profile=profile,
            artifact_namespace=artifact_namespace,
        )
        for item in queue
    )
    snapshot_path = directory / event_market_anomaly_scanner.MARKET_STATE_SNAPSHOT_FILENAME
    if active:
        directory.mkdir(parents=True, exist_ok=True)
        _replace_generation_jsonl(ledger_path, ledger_rows, refresh_run_id=refresh_run_id)
        _replace_generation_jsonl(
            snapshot_path,
            snapshot_rows,
            refresh_run_id=refresh_run_id,
        )
        report = _report_payload(
            refresh_run_id=refresh_run_id,
            run_id=run_id,
            profile=profile,
            artifact_namespace=artifact_namespace,
            provider=provider_name,
            queue=queue,
            ledger_rows=ledger_rows,
            request_count=request_count,
            timeout_seconds=timeout_seconds,
            timed_out=timed_out,
            warnings=warnings,
            ledger_path=ledger_path,
            snapshot_path=snapshot_path,
        )
        report["persisted_snapshot_rows"] = _count_run_rows(snapshot_path, run_id=run_id)
        report_json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report_md_path.write_text(_format_report(report), encoding="utf-8")
    persisted_snapshot_rows = _count_run_rows(snapshot_path, run_id=run_id)
    return EventTargetedMarketRefreshResult(
        enabled=active,
        refresh_run_id=refresh_run_id,
        provider=provider_name,
        queue=queue,
        ledger_rows=ledger_rows,
        market_rows=tuple(fetched_rows),
        snapshot_rows=snapshot_rows,
        ledger_path=ledger_path,
        report_json_path=report_json_path,
        report_md_path=report_md_path,
        request_count=request_count,
        attempted_assets=sum(1 for row in ledger_rows if row.get("attempted")),
        refreshed_assets=sum(1 for row in ledger_rows if row.get("status") == "refreshed"),
        persisted_snapshot_rows=persisted_snapshot_rows,
        timed_out=timed_out,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def apply_targeted_market_refresh_to_sidecars(
    sidecars: Mapping[str, Iterable[Mapping[str, Any]]],
    result: EventTargetedMarketRefreshResult,
) -> dict[str, tuple[dict[str, Any], ...]]:
    snapshots = {_canonical_asset_id(row): dict(row) for row in result.snapshot_rows}
    ledger = {str(row.get("canonical_asset_id") or ""): row for row in result.ledger_rows}
    out: dict[str, tuple[dict[str, Any], ...]] = {}
    for origin, rows in sidecars.items():
        enriched: list[dict[str, Any]] = []
        for value in rows:
            row = dict(value)
            asset = _canonical_asset_id(row)
            status = ledger.get(asset)
            if status is not None:
                row.update(_refresh_metadata(status, result))
            snapshot = snapshots.get(asset)
            if snapshot is not None:
                row["market_snapshot"] = _snapshot_market_payload(snapshot)
                row["latest_market_snapshot"] = _snapshot_market_payload(snapshot)
            enriched.append(row)
        out[origin] = tuple(enriched)
    return out


def annotate_targeted_market_refresh_candidates(
    candidates: Iterable[Mapping[str, Any]],
    result: EventTargetedMarketRefreshResult,
) -> tuple[dict[str, Any], ...]:
    ledger = {str(row.get("canonical_asset_id") or ""): row for row in result.ledger_rows}
    snapshots = {_canonical_asset_id(row): dict(row) for row in result.snapshot_rows}
    out: list[dict[str, Any]] = []
    for value in candidates:
        row = dict(value)
        asset = _canonical_asset_id(row)
        status = ledger.get(asset)
        if status is not None:
            row.update(_refresh_metadata(status, result))
        snapshot = snapshots.get(asset)
        if snapshot is not None:
            row["latest_market_snapshot"] = _snapshot_market_payload(snapshot)
            row["market_snapshot"] = _snapshot_market_payload(snapshot)
        out.append(row)
    return tuple(out)


def _fetch_provider_batch(provider: object, coin_ids: tuple[str, ...], *, max_assets: int, timeout_seconds: float) -> tuple[Iterable[Mapping[str, Any]], Iterable[str]]:
    method = getattr(provider, "fetch_market_rows")
    signature = inspect.signature(method)
    accepts_timeout = "timeout_seconds" in signature.parameters or any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )
    kwargs: dict[str, Any] = {"max_assets": max_assets}
    if accepts_timeout:
        kwargs["timeout_seconds"] = timeout_seconds
    value = method(coin_ids, **kwargs)
    if isinstance(value, tuple) and len(value) == 2:
        return value[0], value[1]
    return value or (), ()


def _annotate_snapshot(row: Mapping[str, Any], refresh_run_id: str, provider: str, ledger_path: Path, report_path: Path) -> dict[str, Any]:
    out = dict(row)
    out.update({
        "targeted_market_refresh_id": refresh_run_id,
        "targeted_market_refresh_attempted": True,
        "targeted_market_refresh_success": True,
        "market_refresh_provider": provider,
        "market_refresh_artifact": event_artifact_paths.artifact_display_path(report_path),
        "targeted_market_refresh_ledger_path": event_artifact_paths.artifact_display_path(ledger_path),
        **_SAFETY,
    })
    return out


def _ledger_row(
    item: EventTargetedMarketRefreshQueueItem,
    *,
    refresh_run_id: str,
    provider: str,
    snapshot: Mapping[str, Any] | None,
    active: bool,
    attempted: bool,
    timed_out: bool,
    error_class: str,
    started_at: datetime,
    finished_at: datetime,
    duration_seconds: float,
    timeout_seconds: float,
    run_id: str,
    profile: str,
    artifact_namespace: str,
) -> dict[str, Any]:
    status = "refreshed" if snapshot is not None else "timeout" if timed_out else "failed" if error_class else "missing_row" if attempted else "skipped_provider_unavailable" if active else "disabled"
    return {
        "schema_version": "event_targeted_market_refresh_ledger_v1",
        "row_type": "event_targeted_market_refresh_ledger",
        "targeted_market_refresh_id": refresh_run_id,
        "refresh_id": item.refresh_id,
        "run_id": run_id,
        "profile": profile,
        "artifact_namespace": artifact_namespace,
        "canonical_asset_id": item.canonical_asset_id,
        "symbol": item.symbol,
        "coin_id": item.coin_id,
        "candidate_family_ids": list(item.candidate_family_ids),
        "priority_bucket": item.priority_bucket,
        "priority_score": item.priority_score,
        "reason": item.reason,
        "attempted": attempted,
        "status": status,
        "provider": provider,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_seconds": round(duration_seconds, 6),
        "timeout_seconds": timeout_seconds,
        "error_class": error_class or None,
        "snapshot_id": snapshot.get("canonical_asset_id") if snapshot else None,
        **_SAFETY,
    }


def _refresh_metadata(status: Mapping[str, Any], result: EventTargetedMarketRefreshResult) -> dict[str, Any]:
    success = str(status.get("status") or "") == "refreshed"
    return {
        "market_refresh_attempted": bool(status.get("attempted")),
        "market_refresh_success": success,
        "market_refresh_status": status.get("status"),
        "market_refresh_provider": status.get("provider"),
        "market_refresh_observed_at": status.get("finished_at"),
        "targeted_market_refresh_attempted": bool(status.get("attempted")),
        "targeted_market_refresh_success": success,
        "targeted_market_refresh_id": result.refresh_run_id,
        "market_refresh_artifact": event_artifact_paths.artifact_display_path(result.report_json_path),
        "targeted_market_refresh_ledger_path": event_artifact_paths.artifact_display_path(result.ledger_path),
    }


def _report_payload(**values: Any) -> dict[str, Any]:
    queue = values.pop("queue")
    ledger_rows = values.pop("ledger_rows")
    warnings = values.pop("warnings")
    ledger_path = values.pop("ledger_path")
    snapshot_path = values.pop("snapshot_path")
    payload = {
        "schema_version": "event_targeted_market_refresh_report_v1",
        "row_type": "event_targeted_market_refresh_report",
        **values,
        "selected_assets": len(queue),
        "attempted_assets": sum(1 for row in ledger_rows if row.get("attempted")),
        "refreshed_assets": sum(1 for row in ledger_rows if row.get("status") == "refreshed"),
        "status_counts": _counts(str(row.get("status") or "unknown") for row in ledger_rows),
        "priority_bucket_counts": _counts(item.priority_bucket for item in queue),
        "ledger_path": event_artifact_paths.artifact_display_path(ledger_path),
        "snapshot_path": event_artifact_paths.artifact_display_path(snapshot_path),
        "warnings": list(dict.fromkeys(warnings)),
        **_SAFETY,
    }
    return schema_v1.stamp_artifact_payload(payload)


def _format_report(payload: Mapping[str, Any]) -> str:
    return "\n".join([
        "# Event Alpha Targeted Market Refresh",
        "",
        "Research-only bounded refresh. Not a trade signal.",
        "",
        f"- refresh_run_id: `{payload.get('refresh_run_id')}`",
        f"- provider: `{payload.get('provider')}`",
        f"- selected_assets: `{payload.get('selected_assets')}`",
        f"- request_count: `{payload.get('request_count')}`",
        f"- request_timeout_seconds: `{payload.get('timeout_seconds')}`",
        f"- timed_out: `{payload.get('timed_out')}`",
        f"- refreshed_assets: `{payload.get('refreshed_assets')}`",
        f"- persisted_snapshot_rows: `{payload.get('persisted_snapshot_rows')}`",
        f"- status_counts: `{payload.get('status_counts')}`",
        f"- priority_bucket_counts: `{payload.get('priority_bucket_counts')}`",
        f"- ledger_path: `{payload.get('ledger_path')}`",
        f"- snapshot_path: `{payload.get('snapshot_path')}`",
        "",
        "## Safety",
        "",
        f"- telegram_sends: `{payload.get('telegram_sends')}`",
        f"- trades_created: `{payload.get('trades_created')}`",
        f"- paper_trades_created: `{payload.get('paper_trades_created')}`",
        f"- normal_rsi_signal_rows_written: `{payload.get('normal_rsi_signal_rows_written')}`",
        f"- triggered_fade_created: `{payload.get('triggered_fade_created')}`",
    ]) + "\n"


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(schema_v1.stamp_artifact_row(row, path=path), sort_keys=True, separators=(",", ":")) + "\n")


def _replace_generation_jsonl(path: Path, rows: Iterable[Mapping[str, Any]], *, refresh_run_id: str) -> None:
    existing: list[dict[str, Any]] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, Mapping) and str(row.get("targeted_market_refresh_id") or "") != refresh_run_id:
                existing.append(dict(row))
    _write_jsonl(path, (*existing, *tuple(rows)))


def _snapshot_market_payload(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in snapshot.items()
        if key not in {"schema_id", "schema_version", "row_type", "profile", "artifact_namespace", "run_mode", "run_id"}
    }


def _needs_targeted_refresh(row: Mapping[str, Any]) -> bool:
    if row.get("is_theme_or_sector") is True or row.get("is_quote_asset") is True or row.get("diagnostic_only") is True:
        return False
    if row.get("targeted_market_refresh_needed") is True or row.get("market_refresh_needed") is True:
        return True
    freshness = str(row.get("market_context_freshness_status") or row.get("freshness_status") or "").casefold()
    if freshness in {"missing", "stale", "expired", "unknown", ""}:
        return True
    text = " ".join(str(row.get(key) or "") for key in ("why_not_alertable", "missing_fields", "reason_codes", "warnings")).casefold()
    return any(token in text for token in ("market_context", "market confirmation", "market_confirmation", "targeted_market_refresh", "market_reaction_missing"))


def _priority_bucket(row: Mapping[str, Any], *, cfg: EventNearMissConfig) -> tuple[str, int]:
    if int(_float(row.get("accepted_evidence_count")) or 0) > 0 or "accepted_evidence" in str(row.get("evidence_acquisition_status") or ""):
        return "accepted_evidence", 0
    score = _score(row)
    if any(0 <= threshold - score <= cfg.near_threshold_points for threshold in (cfg.digest_threshold, cfg.watchlist_threshold)) or "near_gate" in str(row.get("reason_codes") or ""):
        return "near_gate", 1
    source_text = " ".join(str(row.get(key) or "") for key in ("source_strength", "source_class", "source_pack", "source_origin", "provider")).casefold()
    if "official" in source_text or "structured" in source_text:
        return "official_structured", 2
    if "market_anomaly" in source_text or str(row.get("row_type") or "") == "event_market_anomaly":
        return "market_anomaly", 3
    if int(_float(row.get("review_value_score")) or 0) >= 50 or "high_value_skipped" in str(row.get("reason_codes") or ""):
        return "high_review_value_skipped", 4
    return "fresh_candidate", 5


def _refresh_reason(row: Mapping[str, Any]) -> str:
    text = " ".join(str(row.get(key) or "") for key in ("why_not_alertable", "missing_fields", "reason_codes")).casefold()
    if "stale" in text:
        return "stale_market_context"
    if "missing" in text or not row.get("market_snapshot"):
        return "missing_market_context"
    return "needs_fresh_market_confirmation"


def _canonical_asset_id(row: Mapping[str, Any]) -> str:
    return str(
        row.get("canonical_asset_id")
        or row.get("coin_id")
        or row.get("asset_coin_id")
        or row.get("id")
        or row.get("symbol")
        or ""
    ).strip().casefold()


def _family_id(row: Mapping[str, Any]) -> str:
    return str(row.get("core_opportunity_id") or row.get("candidate_family_id") or row.get("integrated_candidate_id") or row.get("candidate_id") or row.get("hypothesis_id") or _canonical_asset_id(row))


def _score(row: Mapping[str, Any]) -> float:
    return _float(row.get("review_value_score") or row.get("opportunity_score_final") or row.get("score") or row.get("priority_score")) or 0.0


def _row(value: Mapping[str, Any] | object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    data = getattr(value, "__dict__", None)
    return dict(data) if isinstance(data, Mapping) else {}


def _counts(values: Iterable[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        out[value] = out.get(value, 0) + 1
    return dict(sorted(out.items()))


def _count_run_rows(path: Path, *, run_id: str) -> int:
    if not path.exists():
        return 0
    count = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, Mapping) and str(row.get("run_id") or "") == run_id:
            count += 1
    return count


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _float(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _env_truthy(name: str) -> bool:
    return str(os.getenv(name, "")).strip().casefold() in _TRUTHY


__all__ = (
    "TARGETED_MARKET_REFRESH_LEDGER_FILENAME",
    "TARGETED_MARKET_REFRESH_REPORT_JSON",
    "TARGETED_MARKET_REFRESH_REPORT_MD",
    "EventTargetedMarketRefreshResult",
    "targeted_refresh_enabled",
    "runtime_targeted_market_provider",
    "select_targeted_market_refresh_families",
    "run_targeted_market_refresh",
    "apply_targeted_market_refresh_to_sidecars",
    "annotate_targeted_market_refresh_candidates",
)
