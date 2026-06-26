"""Research-only Event Alpha cycle run ledger."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


RUN_LEDGER_SCHEMA_VERSION = "event_alpha_run_ledger_v1"


@dataclass(frozen=True)
class EventAlphaRunLedgerConfig:
    path: Path


@dataclass(frozen=True)
class EventAlphaRunLedgerReadResult:
    path: Path
    rows_read: int
    rows: list[dict[str, Any]]


def append_run_record(
    result: Any,
    *,
    cfg: EventAlphaRunLedgerConfig,
    profile: str | None,
    started_at: datetime,
    finished_at: datetime,
    with_llm: bool,
    send_requested: bool,
    notification_burn_in: bool | None = None,
    success: bool = True,
    failure: str | None = None,
) -> dict[str, Any]:
    """Append one Event Alpha cycle summary row to a local JSONL artifact."""
    started = _as_utc(started_at)
    finished = _as_utc(finished_at)
    row = _run_record(
        result,
        profile=profile,
        started_at=started,
        finished_at=finished,
        with_llm=with_llm,
        send_requested=send_requested,
        notification_burn_in=notification_burn_in,
        success=success,
        failure=failure,
    )
    path = cfg.path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(_json_ready(row), sort_keys=True, separators=(",", ":")))
        fh.write("\n")
    return row


def run_id_for(started_at: datetime, profile: str | None) -> str:
    """Return the run_id used across run ledger and alert snapshot artifacts."""
    started = _as_utc(started_at)
    return f"{started.isoformat()}|{profile or 'default'}"


def load_run_records(path: str | Path, *, limit: int | None = None) -> EventAlphaRunLedgerReadResult:
    """Load recent run ledger rows, tolerating malformed legacy rows."""
    p = Path(path).expanduser()
    rows = [
        row for row in _read_jsonl(p)
        if row.get("row_type") == "event_alpha_run"
    ]
    rows.sort(key=lambda row: str(row.get("started_at") or ""), reverse=True)
    if limit is not None and limit > 0:
        rows = rows[:limit]
    return EventAlphaRunLedgerReadResult(path=p, rows_read=len(rows), rows=rows)


def latest_run(rows: Iterable[Mapping[str, Any]], profile: str | None = None) -> dict[str, Any] | None:
    """Return the newest run, optionally preferring a matching profile."""
    ordered = _sorted_runs(rows)
    if not ordered:
        return None
    wanted = _profile_key(profile)
    if wanted is None:
        return dict(ordered[0])
    for row in ordered:
        if _profile_key(row.get("profile")) == wanted:
            return dict(row)
    return dict(ordered[0])


def latest_runs_by_profile(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Return newest run row per profile using the run ledger timestamp order."""
    out: dict[str, dict[str, Any]] = {}
    for row in _sorted_runs(rows):
        profile = _profile_key(row.get("profile")) or "default"
        out.setdefault(profile, dict(row))
    return out


def run_profile_mismatch_warning(requested_profile: str | None, selected_run: Mapping[str, Any] | None) -> str | None:
    """Return a human-readable profile mismatch warning for report headers."""
    wanted = _profile_key(requested_profile)
    if wanted is None or not selected_run:
        return None
    selected = _profile_key(selected_run.get("profile")) or "default"
    if selected == wanted:
        return None
    return f"requested profile {wanted!r} has no run row; showing latest {selected!r} run instead"


def format_run_ledger_report(result: EventAlphaRunLedgerReadResult) -> str:
    rows = [
        "=" * 76,
        "EVENT ALPHA RUNS REPORT (research artifact only)",
        "=" * 76,
        f"path: {result.path}",
        f"rows_read: {result.rows_read}",
    ]
    if not result.rows:
        rows.append("")
        rows.append("No Event Alpha cycle run rows found.")
        return "\n".join(rows)

    success = sum(1 for row in result.rows if bool(row.get("success")))
    failed = len(result.rows) - success
    rows.append(f"success={success} · failure={failed}")
    rows.append("")
    for row in result.rows:
        rows.append(
            f"{row.get('started_at', 'unknown')} profile={row.get('profile') or 'default'} "
            f"mode={row.get('run_mode') or 'legacy'} namespace={row.get('artifact_namespace') or 'legacy'} "
            f"clock={row.get('clock_mode') or 'unknown'} "
            f"notification_burn_in={str(bool(row.get('notification_burn_in'))).lower()} "
            f"success={str(bool(row.get('success'))).lower()} runtime={float(row.get('runtime_seconds') or 0):.2f}s"
        )
        rows.append(
            "  "
            f"raw={int(row.get('raw_events') or 0)} anomalies={int(row.get('market_anomalies') or 0)} "
            f"queries={int(row.get('catalyst_queries') or 0)} accepted={int(row.get('catalyst_results_accepted') or 0)} "
            f"rejected={int(row.get('catalyst_results_rejected') or 0)} candidates={int(row.get('candidates') or 0)} "
            f"alerts={int(row.get('alerts') or 0)} routed={int(row.get('routed') or 0)} "
            f"alertable={int(row.get('alertable') or 0)} sent={str(bool(row.get('sent'))).lower()} "
            f"send={int(row.get('send_items_delivered') or 0)}/{int(row.get('send_items_attempted') or 0)} "
            f"would_send={int(row.get('send_would_send_items') or 0)}"
        )
        rows.append(
            "  "
            f"hypotheses={int(row.get('impact_hypotheses') or 0)} "
            f"validated={int(row.get('hypotheses_validated') or 0)} "
            f"hypothesis_queries={int(row.get('hypothesis_search_queries') or 0)} "
            f"hypothesis_results={int(row.get('hypothesis_search_results') or 0)} "
            f"promotions={int(row.get('hypothesis_promotions') or 0)}"
        )
        query_types = row.get("hypothesis_search_queries_by_type") or {}
        result_types = row.get("hypothesis_search_results_by_type") or {}
        if query_types or result_types:
            rows.append(
                "  hypothesis_query_types: "
                f"queries={_format_reason_counts(query_types)} "
                f"results={_format_reason_counts(result_types)}"
            )
        skip_reasons = row.get("catalyst_search_skip_reasons") or {}
        if isinstance(skip_reasons, Mapping) and skip_reasons:
            rows.append("  catalyst_search_skip_reasons: " + _format_reason_counts(skip_reasons))
        hypothesis_skip_reasons = row.get("hypothesis_search_skip_reasons") or {}
        if isinstance(hypothesis_skip_reasons, Mapping) and hypothesis_skip_reasons:
            rows.append("  hypothesis_search_skip_reasons: " + _format_reason_counts(hypothesis_skip_reasons))
        lane_attempted = row.get("send_lane_items_attempted") or {}
        lane_delivered = row.get("send_lane_items_delivered") or {}
        if lane_attempted or lane_delivered:
            rows.append(
                "  send_lanes: "
                + ", ".join(
                    f"{lane}={int(lane_delivered.get(lane) or 0)}/{int(lane_attempted.get(lane) or 0)}"
                    for lane in sorted(set(lane_attempted) | set(lane_delivered))
                )
            )
        rows.append(
            "  "
            f"snapshots={int(row.get('snapshot_rows_written') or 0)} "
            f"attempted={str(bool(row.get('snapshot_write_attempted'))).lower()} "
            f"success={str(bool(row.get('snapshot_write_success'))).lower()} "
            f"block={row.get('snapshot_write_block_reason') or 'none'}"
        )
        rows.append(
            "  "
            f"hypothesis_store={int(row.get('hypothesis_rows_written') or 0)} "
            f"attempted={str(bool(row.get('hypothesis_write_attempted'))).lower()} "
            f"success={str(bool(row.get('hypothesis_write_success'))).lower()} "
            f"block={row.get('hypothesis_write_block_reason') or 'none'}"
        )
        rows.append(
            "  "
            f"incident_store={int(row.get('incident_rows_written') or 0)} "
            f"attempted={str(bool(row.get('incident_write_attempted'))).lower()} "
            f"success={str(bool(row.get('incident_write_success'))).lower()} "
            f"block={row.get('incident_write_block_reason') or 'none'} "
            f"linked_hypotheses={int(row.get('incident_linked_hypotheses') or 0)} "
            f"linked_watchlist={int(row.get('incident_linked_watchlist_rows') or 0)}"
        )
        if row.get("send_block_reason"):
            rows.append(f"  send_block: {row.get('send_block_reason')}")
        rows.append(
            "  "
            f"provider_fetch={int(row.get('provider_fetch_count') or 0)} "
            f"provider_cache={int(row.get('provider_cache_hits') or 0)}/{int(row.get('provider_cache_misses') or 0)} "
            f"llm_cache={int(row.get('llm_cache_hits') or 0)}/{int(row.get('llm_cache_misses') or 0)} "
            f"llm_calls={int(row.get('llm_calls_attempted') or 0)} skipped_budget={int(row.get('llm_skipped_due_budget') or 0)}"
        )
        warnings = [str(item) for item in row.get("warnings") or [] if str(item)]
        if warnings:
            rows.append("  warnings: " + "; ".join(warnings[:5]))
        if row.get("failure"):
            rows.append(f"  failure: {row.get('failure')}")
    return "\n".join(rows).rstrip()


def _run_record(
    result: Any,
    *,
    profile: str | None,
    started_at: datetime,
    finished_at: datetime,
    with_llm: bool,
    send_requested: bool,
    notification_burn_in: bool | None,
    success: bool,
    failure: str | None,
) -> dict[str, Any]:
    catalyst = getattr(result, "catalyst_search_result", None)
    discovery = getattr(result, "discovery_result", None)
    watchlist = getattr(result, "watchlist_result", None)
    router = getattr(result, "router_result", None)
    extraction_rows = list(getattr(result, "extraction_rows", ()) or ())
    catalyst_frame_rows = list(getattr(result, "catalyst_frame_rows", ()) or ())
    relationship_rows = list(getattr(result, "relationship_rows", ()) or ())
    card_paths = tuple(str(path) for path in getattr(result, "research_card_paths", ()) or ())
    llm_stats = _llm_stats((*extraction_rows, *catalyst_frame_rows, *relationship_rows))
    warnings = list(getattr(result, "warnings", ()) or ())
    clock_status = dict(getattr(result, "clock_status", {}) or {})
    if failure:
        warnings.append(failure)
    run_id = getattr(result, "run_id", None) or run_id_for(started_at, profile)
    notify_burn = (
        bool(notification_burn_in)
        if notification_burn_in is not None
        else bool(getattr(result, "notification_burn_in", False))
        or str(getattr(result, "run_mode", "") or "") == "notification_burn_in"
        or str(profile or "").startswith("notify_")
    )
    return {
        "schema_version": RUN_LEDGER_SCHEMA_VERSION,
        "row_type": "event_alpha_run",
        "run_id": run_id,
        "profile": profile or "default",
        "run_mode": getattr(result, "run_mode", None),
        "artifact_namespace": getattr(result, "artifact_namespace", None),
        "notification_burn_in": notify_burn,
        "clock_mode": clock_status.get("clock_mode"),
        "research_now": clock_status.get("research_now"),
        "wall_clock_now": clock_status.get("wall_clock_now"),
        "fixed_clock_age_hours": clock_status.get("fixed_clock_age_hours"),
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "runtime_seconds": round(max(0.0, (finished_at - started_at).total_seconds()), 4),
        "with_llm": bool(with_llm),
        "raw_events": _int(getattr(result, "raw_events", 0)),
        "cycle_completed": bool(getattr(result, "cycle_completed", True)),
        "partial_results": bool(getattr(result, "partial_results", False)),
        "market_anomalies": _market_anomaly_count(discovery),
        "catalyst_queries": _int(getattr(result, "catalyst_queries", 0)),
        "catalyst_results_accepted": _int(getattr(catalyst, "attached_result_count", 0)),
        "catalyst_results_rejected": _int(getattr(catalyst, "rejected_result_count", 0)),
        "catalyst_search_skip_reasons": _catalyst_search_skip_reasons(
            result,
            warnings=warnings,
            discovery=discovery,
        ),
        "extraction_rows": len(extraction_rows),
        "extraction_hints_applied": _int(getattr(result, "extraction_hint_events", 0)),
        "catalyst_frame_rows": len(catalyst_frame_rows),
        "catalyst_frame_validations_applied": _int(getattr(result, "catalyst_frame_validations_applied", 0)),
        "impact_hypotheses": len(tuple(getattr(result, "impact_hypotheses", ()) or ())),
        "hypotheses_validated": _int(getattr(result, "hypotheses_validated", 0)),
        "hypothesis_search_queries": _int(getattr(result, "hypothesis_search_queries", 0)),
        "hypothesis_search_results": _int(getattr(result, "hypothesis_search_results", 0)),
        "hypothesis_search_queries_by_type": _query_type_counts(getattr(result, "hypothesis_search_result", None), "queries"),
        "hypothesis_search_results_by_type": _query_type_counts(getattr(result, "hypothesis_search_result", None), "result_events"),
        "hypothesis_search_skip_reasons": _hypothesis_search_skip_reasons(result, warnings=warnings),
        "hypothesis_promotions": _int(getattr(result, "hypothesis_promotions", 0)),
        "candidates": _int(getattr(result, "candidates", 0)),
        "clusters": _int(getattr(result, "clusters", 0)),
        "alerts": len(list(getattr(result, "alerts", ()) or ())),
        "watchlist_entries": _int(getattr(result, "watchlist_entries", 0)),
        "watchlist_escalations": _int(getattr(result, "watchlist_escalations", 0)),
        "watchlist_monitor_active_entries": _int(getattr(result, "watchlist_monitor_active_entries", 0)),
        "watchlist_monitor_material_updates": _int(getattr(result, "watchlist_monitor_material_updates", 0)),
        "routed": _int(getattr(result, "routed", 0)),
        "alertable": _int(getattr(result, "alertable", 0)),
        "send_requested": bool(getattr(result, "send_requested", send_requested)),
        "send_attempted": bool(getattr(result, "send_attempted", False)),
        "send_success": bool(getattr(result, "send_success", False)),
        "send_items_attempted": _int(getattr(result, "send_items_attempted", 0)),
        "send_items_delivered": _int(getattr(result, "send_items_delivered", 0)),
        "send_would_send_items": _int(getattr(result, "send_would_send_items", 0)),
        "send_lane_items_attempted": dict(getattr(result, "send_lane_items_attempted", {}) or {}),
        "send_lane_items_delivered": dict(getattr(result, "send_lane_items_delivered", {}) or {}),
        "send_heartbeat_due": bool(getattr(result, "send_heartbeat_due", False)),
        "send_heartbeat_sent": bool(getattr(result, "send_heartbeat_sent", False)),
        "send_cooldown_blocks": dict(getattr(result, "send_cooldown_blocks", {}) or {}),
        "notification_summary": _notification_summary(result, profile=profile, notify_burn=notify_burn),
        "send_block_reason": getattr(result, "send_block_reason", None),
        "sent": bool(getattr(result, "send_success", False)),
        "snapshot_write_attempted": bool(getattr(result, "snapshot_write_attempted", False)),
        "snapshot_write_success": bool(getattr(result, "snapshot_write_success", False)),
        "snapshot_rows_written": _int(getattr(result, "snapshot_rows_written", 0)),
        "snapshot_write_block_reason": getattr(result, "snapshot_write_block_reason", None),
        "hypothesis_store_path": getattr(result, "hypothesis_store_path", None),
        "hypothesis_write_attempted": bool(getattr(result, "hypothesis_write_attempted", False)),
        "hypothesis_write_success": bool(getattr(result, "hypothesis_write_success", False)),
        "hypothesis_rows_written": _int(getattr(result, "hypothesis_rows_written", 0)),
        "hypothesis_write_block_reason": getattr(result, "hypothesis_write_block_reason", None),
        "incident_store_path": getattr(result, "incident_store_path", None),
        "incident_write_attempted": bool(getattr(result, "incident_write_attempted", False)),
        "incident_write_success": bool(getattr(result, "incident_write_success", False)),
        "incident_rows_written": _int(getattr(result, "incident_rows_written", 0)),
        "incidents_written": _int(getattr(result, "incident_rows_written", 0)),
        "incident_store_success": bool(getattr(result, "incident_write_success", False)),
        "incident_linked_hypotheses": _incident_linked_hypotheses(result),
        "incident_linked_watchlist_rows": _incident_linked_watchlist_rows(result),
        "incident_write_block_reason": getattr(result, "incident_write_block_reason", None),
        "research_cards_written": len(card_paths),
        "research_card_paths": card_paths,
        "provider_fetch_count": _int(getattr(catalyst, "provider_fetch_count", 0)),
        "provider_cache_hits": _int(getattr(catalyst, "provider_cache_hits", 0)),
        "provider_cache_misses": _int(getattr(catalyst, "provider_cache_misses", 0)),
        "llm_cache_hits": llm_stats["cache_hits"],
        "llm_cache_misses": llm_stats["cache_misses"],
        "llm_calls_attempted": llm_stats["calls_attempted"],
        "llm_skipped_due_budget": llm_stats["skipped_due_budget"],
        "watchlist_path": str(getattr(watchlist, "state_path", "") or ""),
        "run_ledger_path": getattr(result, "run_ledger_path", None),
        "alert_store_path": getattr(result, "alert_store_path", None),
        "watchlist_state_path": getattr(result, "watchlist_state_path", None),
        "research_cards_dir": getattr(result, "research_cards_dir", None),
        "router_enabled": bool(getattr(router, "enabled", False)),
        "warnings": tuple(dict.fromkeys(str(warning) for warning in warnings if str(warning))),
        "success": bool(success),
        "failure": failure,
}


def _notification_summary(result: Any, *, profile: str | None, notify_burn: bool) -> dict[str, Any]:
    lane_due = dict(getattr(result, "send_lane_items_attempted", {}) or {})
    lane_sent = dict(getattr(result, "send_lane_items_delivered", {}) or {})
    warnings = tuple(str(warning) for warning in getattr(result, "warnings", ()) or () if str(warning))
    provider_blocks = tuple(
        warning for warning in warnings
        if any(token in warning.casefold() for token in ("backoff", "failed", "failure", "timeout", "dns", "429"))
    )
    return {
        "notification_profile": profile or getattr(result, "profile", None) or "default",
        "notification_burn_in": bool(notify_burn),
        "scope": getattr(result, "notification_scope", None),
        "scope_value": getattr(result, "notification_scope_value", None),
        "cycle_completed": bool(getattr(result, "cycle_completed", True)),
        "partial_results": bool(getattr(result, "partial_results", False)),
        "lane_counts_due": lane_due,
        "lane_counts_sent": lane_sent,
        "heartbeat_due": bool(getattr(result, "send_heartbeat_due", False)),
        "heartbeat_sent": bool(getattr(result, "send_heartbeat_sent", False)),
        "would_send_count": _int(getattr(result, "send_would_send_items", 0)),
        "block_reason": getattr(result, "send_block_reason", None),
        "cooldown_blocks": dict(getattr(result, "send_cooldown_blocks", {}) or {}),
        "provider_fail_fast_blocks": provider_blocks,
        "runtime_budget_exhausted": any("notification_runtime_budget_exhausted" in warning for warning in warnings),
    }


def _incident_linked_hypotheses(result: Any) -> int:
    return sum(
        1
        for item in getattr(result, "impact_hypotheses", ()) or ()
        if _value(item, "incident_id")
    )


def _incident_linked_watchlist_rows(result: Any) -> int:
    watchlist = getattr(result, "watchlist_result", None)
    entries = getattr(watchlist, "entries", ()) or ()
    return sum(
        1
        for entry in entries
        if str(_value(entry, "relationship_type") or "") == "impact_hypothesis"
        and (
            _value(entry, "incident_id")
            or (
                isinstance(_value(entry, "latest_score_components"), Mapping)
                and _value(entry, "latest_score_components").get("incident_id")
            )
        )
    )


def _value(item: Any, key: str) -> Any:
    if isinstance(item, Mapping):
        return item.get(key)
    return getattr(item, key, None)


def _llm_stats(rows: Iterable[object]) -> dict[str, int]:
    stats = {
        "cache_hits": 0,
        "cache_misses": 0,
        "calls_attempted": 0,
        "skipped_due_budget": 0,
    }
    for row in rows:
        status = str(getattr(row, "cache_status", "") or "")
        if status == "hit":
            stats["cache_hits"] += 1
        elif status == "miss":
            stats["cache_misses"] += 1
            stats["calls_attempted"] += 1
        elif status == "skipped_budget":
            stats["skipped_due_budget"] += 1
        warnings = tuple(getattr(row, "warnings", ()) or ())
        if any("budget exhausted" in str(warning) for warning in warnings):
            stats["skipped_due_budget"] += 1
    return stats


def _query_type_counts(container: Any, attr: str) -> dict[str, int]:
    if container is None:
        return {}
    rows = getattr(container, attr, ()) or ()
    out: dict[str, int] = {}
    for row in rows:
        query = row if attr == "queries" else getattr(row, "query", None)
        query_type = str(getattr(query, "query_type", "") or "candidate_validation")
        out[query_type] = out.get(query_type, 0) + 1
    return out


def _market_anomaly_count(discovery: Any) -> int:
    raw_events = tuple(getattr(discovery, "raw_events", ()) or ())
    count = 0
    for raw in raw_events:
        if str(getattr(raw, "provider", "") or "") == "market_anomaly":
            count += 1
            continue
        payload = getattr(raw, "raw_json", None)
        if isinstance(payload, Mapping) and isinstance(payload.get("anomaly"), Mapping):
            count += 1
    return count


def _catalyst_search_skip_reasons(
    result: Any,
    *,
    warnings: Iterable[str],
    discovery: Any,
) -> dict[str, int]:
    raw = getattr(result, "catalyst_search_skip_reasons", None)
    if raw is None:
        catalyst = getattr(result, "catalyst_search_result", None)
        raw = getattr(catalyst, "skip_reasons", None) if catalyst is not None else None
    out: dict[str, int] = {}
    if isinstance(raw, Mapping):
        for key, value in raw.items():
            clean = str(key or "").strip()
            if not clean:
                continue
            out[clean] = out.get(clean, 0) + max(1, _int(value))
    warning_text = " ".join(str(item or "") for item in warnings).casefold()
    if "notification_runtime_budget_exhausted_before_catalyst_search" in warning_text:
        out["runtime_budget_exhausted"] = out.get("runtime_budget_exhausted", 0) + 1
    if ("provider_backoff" in warning_text or "backoff" in warning_text) and "provider_backoff" not in out:
        out["provider_backoff"] = out.get("provider_backoff", 0) + 1
    if "catalyst search skipped: no provider available" in warning_text and "provider_unavailable" not in out:
        out["provider_unavailable"] = out.get("provider_unavailable", 0) + 1
    if not out and _market_anomaly_count(discovery) > 0 and _int(getattr(result, "catalyst_queries", 0)) == 0:
        out["unknown"] = 1
    return out


def _hypothesis_search_skip_reasons(
    result: Any,
    *,
    warnings: Iterable[str],
) -> dict[str, int]:
    raw = getattr(result, "hypothesis_search_skip_reasons", None)
    if raw is None:
        hypothesis = getattr(result, "hypothesis_search_result", None)
        raw = getattr(hypothesis, "skip_reasons", None) if hypothesis is not None else None
    out: dict[str, int] = {}
    if isinstance(raw, Mapping):
        for key, value in raw.items():
            clean = str(key or "").strip()
            if clean:
                out[clean] = out.get(clean, 0) + max(1, _int(value))
    warning_text = " ".join(str(item or "") for item in warnings).casefold()
    if "hypothesis search skipped: no provider available" in warning_text and "provider_unavailable" not in out:
        out["provider_unavailable"] = out.get("provider_unavailable", 0) + 1
    if "hypothesis search provider failed" in warning_text and not {"provider_unavailable", "provider_backoff"} & set(out):
        out["provider_unavailable"] = out.get("provider_unavailable", 0) + 1
    return out


def _format_reason_counts(reasons: Mapping[str, Any]) -> str:
    return ", ".join(
        f"{key}={_int(value)}"
        for key, value in sorted(reasons.items())
        if str(key)
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _sorted_runs(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out = [dict(row) for row in rows if isinstance(row, Mapping)]
    out.sort(key=lambda row: str(row.get("started_at") or row.get("observed_at") or ""), reverse=True)
    return out


def _profile_key(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return text


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, datetime):
        return _as_utc(value).isoformat()
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def _int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
