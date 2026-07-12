"""Research-only Event Alpha cycle run ledger."""

from __future__ import annotations

import json
import logging
import math
import os
import stat
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import paths as event_artifact_paths
from . import run_counters as event_alpha_run_counters


RUN_LEDGER_SCHEMA_VERSION = "event_alpha_run_ledger_v1"
LOGGER = logging.getLogger(__name__)


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
    try:
        from . import operator_state as event_alpha_operator_state

        row = event_alpha_operator_state.enrich_run_row_from_core_store(path.parent, row)
    except (OSError, ValueError, TypeError):
        pass
    rewrite_normalized_run_records(path)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(_json_ready(row), sort_keys=True, separators=(",", ":")))
        fh.write("\n")
    try:
        from . import operator_state as event_alpha_operator_state
        from ..namespace import status as event_alpha_namespace_status

        event_alpha_operator_state.begin_run_if_newer(
            path.parent,
            row,
            run_ledger_path=path,
            updated_at=finished,
        )
        event_alpha_namespace_status.refresh_namespace_status(
            path.parent,
            profile=str(row.get("profile") or "default"),
            artifact_namespace=str(row.get("artifact_namespace") or path.parent.name),
            run_mode=str(row.get("run_mode") or ""),
            now=finished,
        )
    except (OSError, ValueError) as exc:
        # The persisted run remains authoritative; a missing/stale state file is
        # fail-closed by doctor/readiness checks and must never alter routing.
        LOGGER.warning("Event Alpha operator-state update failed for %s: %s", row.get("run_id"), exc)
    return row


def rewrite_normalized_run_records(path: str | Path) -> int:
    """Rewrite legacy run rows with portable paths; returns changed rows."""
    p = Path(path).expanduser()
    if not p.exists():
        return 0
    raw_rows: list[dict[str, Any]] = []
    try:
        with p.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    return 0
                if not isinstance(row, dict):
                    return 0
                raw_rows.append(row)
    except OSError:
        return 0
    normalized_rows = [
        event_artifact_paths.normalize_operator_path_fields(row)
        if row.get("row_type") == "event_alpha_run"
        else row
        for row in raw_rows
    ]
    changed = sum(1 for old, new in zip(raw_rows, normalized_rows, strict=False) if old != new)
    if not changed:
        return 0
    temp_path: Path | None = None
    try:
        original_mode = stat.S_IMODE(p.stat().st_mode)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=p.parent,
            prefix=f".{p.name}.",
            suffix=".tmp",
            delete=False,
        ) as fh:
            temp_path = Path(fh.name)
            for row in normalized_rows:
                fh.write(json.dumps(_json_ready(row), sort_keys=True, separators=(",", ":")))
                fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        temp_path.chmod(original_mode)
        os.replace(temp_path, p)
    except OSError:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
        return 0
    return changed


def run_id_for(started_at: datetime, profile: str | None) -> str:
    """Return the run_id used across run ledger and alert snapshot artifacts."""
    started = _as_utc(started_at)
    return f"{started.isoformat()}|{profile or 'default'}"


def load_run_records(path: str | Path, *, limit: int | None = None) -> EventAlphaRunLedgerReadResult:
    """Load recent run ledger rows, tolerating malformed legacy rows."""
    p = Path(path).expanduser()
    rows = [
        _normalize_run_row(row) for row in _read_jsonl(p)
        if row.get("row_type") == "event_alpha_run"
    ]
    rows.sort(key=lambda row: str(row.get("started_at") or ""), reverse=True)
    if limit is not None and limit > 0:
        rows = rows[:limit]
    return EventAlphaRunLedgerReadResult(path=p, rows_read=len(rows), rows=rows)


def reconcile_cryptopanic_counts(
    path: str | Path,
    *,
    profile: str | None = None,
    artifact_namespace: str | None = None,
    run_id: str | None = None,
    accepted_evidence: int | None = None,
    rejected_evidence: int | None = None,
    successful_requests: int | None = None,
    failed_requests: int | None = None,
    effective_provider_status: str | None = None,
    raw_provider_status: str | None = None,
    stale_backoff_reconciled: bool | None = None,
) -> int:
    """Rewrite latest matching row with authoritative CryptoPanic counters."""
    p = Path(path).expanduser()
    rows = _read_jsonl(p)
    if not rows:
        return 0
    candidates = [
        idx for idx, row in enumerate(rows)
        if row.get("row_type") == "event_alpha_run"
        and (not run_id or str(row.get("run_id") or "") == str(run_id))
        and (not profile or str(row.get("profile") or "") == str(profile))
        and (not artifact_namespace or str(row.get("artifact_namespace") or "") == str(artifact_namespace))
    ]
    if not candidates:
        return 0
    target_idx = max(candidates, key=lambda idx: str(rows[idx].get("started_at") or ""))
    row = rows[target_idx]
    before = dict(row)
    if accepted_evidence is not None:
        row["cryptopanic_accepted_evidence"] = int(accepted_evidence)
    if rejected_evidence is not None:
        row["cryptopanic_rejected_evidence"] = int(rejected_evidence)
    if successful_requests is not None:
        row["cryptopanic_successful_requests"] = int(successful_requests)
    if failed_requests is not None:
        row["cryptopanic_failed_requests"] = int(failed_requests)
    if effective_provider_status:
        row["cryptopanic_provider_status"] = str(effective_provider_status)
        row["cryptopanic_effective_provider_status"] = str(effective_provider_status)
    if raw_provider_status:
        row["cryptopanic_raw_provider_status"] = str(raw_provider_status)
    if stale_backoff_reconciled is not None:
        row["cryptopanic_stale_backoff_reconciled_after_success"] = bool(stale_backoff_reconciled)
    if before == row:
        return 0
    rows[target_idx] = row
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as fh:
        for item in rows:
            normalized = event_artifact_paths.normalize_operator_path_fields(item)
            fh.write(json.dumps(_json_ready(normalized), sort_keys=True, separators=(",", ":")))
            fh.write("\n")
    return 1


def _normalize_run_row(row: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(row)
    for key in (
        "catalyst_frames_analyzed",
        "catalyst_frame_validations",
        "catalyst_frame_disagreements",
        "catalyst_frame_unresolved",
        "catalyst_frame_rows_skipped",
    ):
        out[key] = _int(out.get(key))
    reasons = out.get("catalyst_frame_skip_reasons")
    out["catalyst_frame_skip_reasons"] = dict(reasons) if isinstance(reasons, Mapping) else {}
    return out


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
    from . import operator_state as event_alpha_operator_state

    for row in result.rows:
        _append_run_ledger_report_row(
            rows,
            event_alpha_operator_state.enrich_run_row_from_core_store(result.path.parent, row),
        )
    return "\n".join(rows).rstrip()


def _append_run_ledger_report_row(rows: list[str], row: Mapping[str, Any]) -> None:
    rows.append(
        f"{row.get('started_at', 'unknown')} profile={row.get('profile') or 'default'} "
        f"mode={row.get('run_mode') or 'legacy'} namespace={row.get('artifact_namespace') or 'legacy'} "
        f"clock={row.get('clock_mode') or 'unknown'} "
        f"notification_burn_in={str(bool(row.get('notification_burn_in'))).lower()} "
        f"success={str(bool(row.get('success'))).lower()} runtime={float(row.get('runtime_seconds') or 0):.2f}s"
    )
    _append_run_ledger_activity_lines(rows, row)
    _append_run_ledger_skip_and_lane_lines(rows, row)
    _append_run_ledger_write_lines(rows, row)
    if row.get("send_block_reason"):
        rows.append(f"  send_block: {row.get('send_block_reason')}")
    rows.append(
        "  "
        f"provider_fetch={int(row.get('provider_fetch_count') or 0)} "
        f"provider_cache={int(row.get('provider_cache_hits') or 0)}/{int(row.get('provider_cache_misses') or 0)} "
        f"llm_cache={int(row.get('llm_cache_hits') or 0)}/{int(row.get('llm_cache_misses') or 0)} "
        f"llm_calls={int(row.get('llm_calls_attempted') or 0)} "
        f"failed={int(row.get('llm_calls_failed') or 0)} "
        f"skipped_budget={int(row.get('llm_skipped_due_budget') or 0)} "
        f"skipped_provider_backoff={int(row.get('llm_skipped_due_provider_backoff') or 0)}"
    )
    warnings = [str(item) for item in row.get("warnings") or [] if str(item)]
    if warnings:
        rows.append("  warnings: " + "; ".join(warnings[:5]))
    if row.get("failure"):
        rows.append(f"  failure: {row.get('failure')}")


def _append_run_ledger_activity_lines(rows: list[str], row: Mapping[str, Any]) -> None:
    counters = event_alpha_run_counters.canonical_run_counters(row)
    send_state = event_alpha_run_counters.canonical_send_state(row)
    rows.append(
        "  "
        f"raw_events={counters['raw_events']} candidate_events={counters['candidate_events']} "
        f"research_candidates={counters['research_candidates']} source_alert_snapshots={counters['source_alert_snapshots']} "
        f"current_generation_core_rows={counters['current_generation_core_rows']} "
        f"current_generation_visible_core_rows={counters['current_generation_visible_core_rows']} "
        f"cumulative_store_rows={counters['cumulative_store_rows']} "
        f"alertable_decisions={counters['alertable_decisions']} strict_alerts={counters['strict_alerts']} "
        f"preview_rendered_items={counters['preview_rendered_items']}"
    )
    rows.append(
        "  "
        f"anomalies={int(row.get('market_anomalies') or 0)} "
        f"queries={int(row.get('catalyst_queries') or 0)} accepted={int(row.get('catalyst_results_accepted') or 0)} "
        f"rejected={int(row.get('catalyst_results_rejected') or 0)} routed={int(row.get('routed') or 0)} "
        f"sent={str(bool(row.get('sent'))).lower()} "
        f"send={int(row.get('send_items_delivered') or 0)}/{int(row.get('send_items_attempted') or 0)} "
        f"would_send={int(row.get('send_would_send_items') or 0)}"
    )
    rows.append(
        "  "
        f"burn_in_mode={send_state['burn_in_mode']} send_guard_status={send_state['send_guard_status']} "
        f"send_requested={str(send_state['send_requested']).lower()} "
        f"send_attempted={str(send_state['send_attempted']).lower()} "
        f"no_send_rehearsal={str(send_state['no_send_rehearsal']).lower()}"
    )
    rows.append(
        "  "
        f"hypotheses={int(row.get('impact_hypotheses') or 0)} "
        f"validated={int(row.get('hypotheses_validated') or 0)} "
        f"hypothesis_queries={int(row.get('hypothesis_search_queries') or 0)} "
        f"hypothesis_results={int(row.get('hypothesis_search_results') or 0)} "
        f"promotions={int(row.get('hypothesis_promotions') or 0)}"
    )
    rows.append(
        "  "
        f"evidence_acquisition attempted={int(row.get('evidence_acquisition_attempted') or 0)} "
        f"accepted={int(row.get('evidence_acquisition_accepted') or 0)} "
        f"rejected_only={int(row.get('evidence_acquisition_rejected_only') or 0)} "
        f"upgraded={int(row.get('evidence_acquisition_upgraded') or 0)} "
        f"rows={int(row.get('evidence_acquisition_rows_written') or 0)}"
    )
    if row.get("cryptopanic_configured") or row.get("cryptopanic_attempted") or row.get("cryptopanic_skip_reason"):
        rows.append(
            "  "
            f"cryptopanic configured={str(bool(row.get('cryptopanic_configured'))).lower()} "
            f"attempted={str(bool(row.get('cryptopanic_attempted'))).lower()} "
            f"requests={int(row.get('cryptopanic_requests_used') or 0)} "
            f"results={int(row.get('cryptopanic_results') or 0)} "
            f"accepted={int(row.get('cryptopanic_accepted_evidence') or 0)} "
            f"rejected={int(row.get('cryptopanic_rejected_evidence') or 0)} "
            f"status={row.get('cryptopanic_effective_provider_status') or row.get('cryptopanic_provider_status') or 'not_observed'} "
            f"skip={row.get('cryptopanic_skip_reason') or 'none'} "
            f"raw_status={row.get('cryptopanic_raw_provider_status') or row.get('cryptopanic_provider_status') or 'not_observed'} "
            f"successes={int(row.get('cryptopanic_successful_requests') or 0)} "
            f"failures={int(row.get('cryptopanic_failed_requests') or 0)} "
            f"stale_backoff_reconciled={str(bool(row.get('cryptopanic_stale_backoff_reconciled_after_success'))).lower()}"
        )
    rows.append(
        "  "
        f"catalyst_frames analyzed={int(row.get('catalyst_frames_analyzed') or 0)} "
        f"validated={int(row.get('catalyst_frame_validations') or 0)} "
        f"disagreements={int(row.get('catalyst_frame_disagreements') or 0)} "
        f"unresolved={int(row.get('catalyst_frame_unresolved') or 0)} "
        f"skipped={int(row.get('catalyst_frame_rows_skipped') or 0)}"
    )


def _append_run_ledger_skip_and_lane_lines(rows: list[str], row: Mapping[str, Any]) -> None:
    query_types = row.get("hypothesis_search_queries_by_type") or {}
    result_types = row.get("hypothesis_search_results_by_type") or {}
    if query_types or result_types:
        rows.append(
            "  hypothesis_query_types: "
            f"queries={_format_reason_counts(query_types)} "
            f"results={_format_reason_counts(result_types)}"
        )
    for key, label in (
        ("catalyst_search_skip_reasons", "catalyst_search_skip_reasons"),
        ("hypothesis_search_skip_reasons", "hypothesis_search_skip_reasons"),
        ("catalyst_frame_skip_reasons", "catalyst_frame_skip_reasons"),
    ):
        reasons = row.get(key) or {}
        if isinstance(reasons, Mapping) and reasons:
            rows.append(f"  {label}: " + _format_reason_counts(reasons))
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
    if row.get("research_review_digest_enabled") or row.get("research_review_digest_candidates"):
        rows.append(
            "  research_review_digest: "
            f"enabled={str(bool(row.get('research_review_digest_enabled'))).lower()} "
            f"candidates={int(row.get('research_review_digest_candidates') or 0)} "
            f"would_send={int(row.get('research_review_digest_would_send') or 0)} "
            f"sent={int(row.get('research_review_digest_sent') or 0)} "
            f"block={row.get('research_review_digest_block_reason') or 'none'}"
        )


def _append_run_ledger_write_lines(rows: list[str], row: Mapping[str, Any]) -> None:
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
    rows.append(
        "  "
        f"core_opportunity_store={int(row.get('core_opportunity_rows_written') or 0)} "
        f"attempted={str(bool(row.get('core_opportunity_write_attempted'))).lower()} "
        f"success={str(bool(row.get('core_opportunity_write_success'))).lower()} "
        f"block={row.get('core_opportunity_write_block_reason') or 'none'}"
    )
    calendar_normalization = row.get("unified_calendar_normalization")
    if isinstance(calendar_normalization, Mapping):
        from .schema.calendar import CALENDAR_NORMALIZATION_REJECTION_CODES

        raw_reasons = calendar_normalization.get("rejected_reason_counts")
        reason_counts = raw_reasons if isinstance(raw_reasons, Mapping) else {}
        safe_reasons = ",".join(
            f"{reason}={int(reason_counts.get(reason) or 0)}"
            for reason in sorted(CALENDAR_NORMALIZATION_REJECTION_CODES)
            if isinstance(reason_counts.get(reason), int)
            and not isinstance(reason_counts.get(reason), bool)
            and int(reason_counts.get(reason) or 0) > 0
        )
        rows.append(
            "  calendar_normalization: "
            f"input={int(calendar_normalization.get('input_rows') or 0)} "
            f"accepted={int(calendar_normalization.get('accepted_rows') or 0)} "
            f"output={int(calendar_normalization.get('output_rows') or 0)} "
            f"duplicates={int(calendar_normalization.get('duplicate_overwrite_rows') or 0)} "
            f"non_mapping={int(calendar_normalization.get('non_mapping_rows') or 0)} "
            f"rejected={int(calendar_normalization.get('rejected_rows') or 0)} "
            f"reasons={safe_reasons or 'none'}"
        )


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
    raw_card_paths = tuple(str(path) for path in getattr(result, "research_card_paths", ()) or ())
    card_paths = tuple(event_artifact_paths.artifact_display_path(path) for path in raw_card_paths)
    llm_stats = _llm_stats((*extraction_rows, *catalyst_frame_rows, *relationship_rows))
    catalyst_frame_counts = _catalyst_frame_counts(result, catalyst_frame_rows)
    acquisition = getattr(result, "evidence_acquisition_result", None)
    warnings = list(getattr(result, "warnings", ()) or ())
    clock_status = dict(getattr(result, "clock_status", {}) or {})
    if failure:
        warnings.append(failure)
    if (
        not with_llm
        and _int(getattr(result, "raw_events", 0)) > 0
        and not catalyst_frame_counts["skip_reasons"]
    ):
        catalyst_frame_counts["skip_reasons"] = {"profile_disabled": 1}
    run_id = getattr(result, "run_id", None) or run_id_for(started_at, profile)
    result_market_anomalies = _int(getattr(result, "market_anomalies", 0))
    market_anomalies = result_market_anomalies if result_market_anomalies or discovery is None else _market_anomaly_count(discovery)
    research_observed_at = getattr(result, "research_observed_at", None)
    wall_started_at = getattr(result, "wall_started_at", None) or started_at
    wall_finished_at = getattr(result, "wall_finished_at", None) or finished_at
    notify_burn = (
        bool(notification_burn_in)
        if notification_burn_in is not None
        else bool(getattr(result, "notification_burn_in", False))
        or str(getattr(result, "run_mode", "") or "") == "notification_burn_in"
        or str(profile or "").startswith("notify_")
    )
    row = _run_record_base_fields(
        result,
        profile=profile,
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        with_llm=with_llm,
        notify_burn=notify_burn,
        clock_status=clock_status,
        market_anomalies=market_anomalies,
        research_observed_at=research_observed_at,
        wall_started_at=wall_started_at,
        wall_finished_at=wall_finished_at,
    )
    row.update(_run_record_source_fields(
        result,
        catalyst=catalyst,
        discovery=discovery,
        extraction_rows=extraction_rows,
        catalyst_frame_rows=catalyst_frame_rows,
        catalyst_frame_counts=catalyst_frame_counts,
        warnings=warnings,
    ))
    row.update(_run_record_evidence_and_provider_fields(result, acquisition=acquisition))
    row.update(_run_record_notification_fields(
        result,
        profile=profile,
        notify_burn=notify_burn,
        send_requested=send_requested,
    ))
    row.update(_run_record_artifact_write_fields(
        result,
        raw_card_paths=raw_card_paths,
        card_paths=card_paths,
    ))
    row.update(_run_record_cache_and_path_fields(
        result,
        catalyst=catalyst,
        watchlist=watchlist,
        router=router,
        llm_stats=llm_stats,
        warnings=warnings,
        success=success,
        failure=failure,
    ))
    return event_artifact_paths.normalize_operator_path_fields(row)


def _run_record_base_fields(
    result: Any,
    *,
    profile: str | None,
    run_id: str,
    started_at: datetime,
    finished_at: datetime,
    with_llm: bool,
    notify_burn: bool,
    clock_status: Mapping[str, Any],
    market_anomalies: int,
    research_observed_at: Any,
    wall_started_at: Any,
    wall_finished_at: Any,
) -> dict[str, Any]:
    return {
        "schema_id": "run_ledger_v1",
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
        "research_observed_at": _iso_or_value(research_observed_at),
        "wall_started_at": _iso_or_value(wall_started_at),
        "wall_finished_at": _iso_or_value(wall_finished_at),
        "generated_at": finished_at.isoformat(),
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "runtime_seconds": round(max(0.0, (finished_at - started_at).total_seconds()), 4),
        "with_llm": bool(with_llm),
        "raw_events": _int(getattr(result, "raw_events", 0)),
        "cycle_completed": bool(getattr(result, "cycle_completed", True)),
        "partial_results": bool(getattr(result, "partial_results", False)),
        "market_anomalies": market_anomalies,
    }


def _run_record_source_fields(
    result: Any,
    *,
    catalyst: Any,
    discovery: Any,
    extraction_rows: list[Any],
    catalyst_frame_rows: list[Any],
    catalyst_frame_counts: Mapping[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    fields = {
        "market_state_snapshots": _int(getattr(result, "market_state_snapshots", 0)),
        "unified_calendar_rows": _int(getattr(result, "unified_calendar_rows", 0)),
        "unified_calendar_path": getattr(result, "unified_calendar_path", None),
        "unified_calendar_preview_path": getattr(result, "unified_calendar_preview_path", None),
        "decision_model_version": getattr(result, "decision_model_version", None),
        "decision_model_v2_enabled": getattr(result, "decision_model_v2_enabled", False) is True,
        "decision_model_v2_row_count": _int(getattr(result, "decision_model_v2_row_count", 0)),
        "official_exchange_events": _int(getattr(result, "official_exchange_events", 0)),
        "official_listing_candidates": _int(getattr(result, "official_listing_candidates", 0)),
        "scheduled_catalysts": _int(getattr(result, "scheduled_catalysts", 0)),
        "unlock_candidates": _int(getattr(result, "unlock_candidates", 0)),
        "derivatives_state_rows": _int(getattr(result, "derivatives_state_rows", 0)),
        "derivatives_crowding_candidates": _int(getattr(result, "derivatives_crowding_candidates", 0)),
        "fade_review_candidates": _int(getattr(result, "fade_review_candidates", 0)),
        "integrated_candidates": _int(getattr(result, "integrated_candidates", 0)),
        "integrated_candidates_path": str(getattr(result, "integrated_candidates_path", "") or ""),
        "integrated_report_path": str(getattr(result, "integrated_report_path", "") or ""),
        "integrated_input_manifest_path": str(getattr(result, "input_manifest_path", "") or ""),
        "integrated_source_coverage_json_path": str(getattr(result, "source_coverage_json_path", "") or ""),
        "source_coverage_json_path_rel": str(getattr(result, "source_coverage_json_path_rel", "") or ""),
        "source_coverage_md_path_rel": str(getattr(result, "source_coverage_md_path_rel", "") or ""),
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
        "catalyst_frames_analyzed": catalyst_frame_counts["analyzed"],
        "catalyst_frame_validations": catalyst_frame_counts["validations"],
        "catalyst_frame_disagreements": catalyst_frame_counts["disagreements"],
        "catalyst_frame_unresolved": catalyst_frame_counts["unresolved"],
        "catalyst_frame_rows_skipped": catalyst_frame_counts["skipped"],
        "catalyst_frame_skip_reasons": catalyst_frame_counts["skip_reasons"],
        "impact_hypotheses": len(tuple(getattr(result, "impact_hypotheses", ()) or ())),
        "hypotheses_validated": _int(getattr(result, "hypotheses_validated", 0)),
        "hypothesis_search_queries": _int(getattr(result, "hypothesis_search_queries", 0)),
        "hypothesis_search_results": _int(getattr(result, "hypothesis_search_results", 0)),
        "hypothesis_search_queries_by_type": _query_type_counts(getattr(result, "hypothesis_search_result", None), "queries"),
        "hypothesis_search_results_by_type": _query_type_counts(getattr(result, "hypothesis_search_result", None), "result_events"),
        "hypothesis_search_skip_reasons": _hypothesis_search_skip_reasons(result, warnings=warnings),
        "hypothesis_promotions": _int(getattr(result, "hypothesis_promotions", 0)),
    }
    calendar_normalization = getattr(result, "unified_calendar_normalization", None)
    if calendar_normalization is not None:
        from .schema.calendar import validate_run_ledger_normalization_contract

        if not isinstance(calendar_normalization, Mapping):
            raise ValueError("invalid unified calendar normalization telemetry")
        try:
            persisted_normalization = dict(calendar_normalization)
            reason_counts = persisted_normalization.get("rejected_reason_counts")
            if isinstance(reason_counts, Mapping):
                persisted_normalization["rejected_reason_counts"] = dict(reason_counts)
        except Exception:
            raise ValueError("invalid unified calendar normalization telemetry") from None
        validation_row = {
            "unified_calendar_rows": fields["unified_calendar_rows"],
            "unified_calendar_normalization": persisted_normalization,
        }
        try:
            validation_errors = validate_run_ledger_normalization_contract(validation_row)
        except Exception:
            raise ValueError("invalid unified calendar normalization telemetry") from None
        if validation_errors:
            raise ValueError("invalid unified calendar normalization telemetry") from None
        fields["unified_calendar_normalization"] = persisted_normalization
    return fields


def _run_record_evidence_and_provider_fields(result: Any, *, acquisition: Any) -> dict[str, Any]:
    return {
        "evidence_acquisition_attempted": _int(getattr(result, "evidence_acquisition_attempted", 0)),
        "evidence_acquisition_accepted": _int(getattr(result, "evidence_acquisition_accepted", 0)),
        "evidence_acquisition_rejected_only": _int(getattr(result, "evidence_acquisition_rejected_only", 0)),
        "evidence_acquisition_upgraded": _int(getattr(result, "evidence_acquisition_upgraded", 0)),
        "evidence_acquisition_rows_written": _int(getattr(acquisition, "rows_written", 0)) if acquisition is not None else 0,
        "evidence_acquisition_path": str(getattr(acquisition, "path", "") or ""),
        "evidence_acquisition_run_status": str(getattr(acquisition, "status", "") or ""),
        "evidence_acquisition_status_counts": _evidence_acquisition_status_counts(acquisition),
        "cryptopanic_configured": bool(getattr(result, "cryptopanic_configured", False)),
        "cryptopanic_attempted": bool(getattr(result, "cryptopanic_attempted", False)),
        "cryptopanic_requests_used": _int(getattr(result, "cryptopanic_requests_used", 0)),
        "cryptopanic_request_cache_hits": _int(getattr(result, "cryptopanic_request_cache_hits", 0)),
        "cryptopanic_request_cache_misses": _int(getattr(result, "cryptopanic_request_cache_misses", 0)),
        "cryptopanic_requests_deduped": _int(getattr(result, "cryptopanic_requests_deduped", 0)),
        "cryptopanic_invalid_currency_requests_skipped": _int(getattr(result, "cryptopanic_invalid_currency_requests_skipped", 0)),
        "cryptopanic_results": _int(getattr(result, "cryptopanic_results", 0)),
        "cryptopanic_accepted_evidence": _int(getattr(result, "cryptopanic_accepted_evidence", 0)),
        "cryptopanic_rejected_evidence": _int(getattr(result, "cryptopanic_rejected_evidence", 0)),
        "cryptopanic_provider_status": str(getattr(result, "cryptopanic_provider_status", "") or "not_observed"),
        "cryptopanic_skip_reason": getattr(result, "cryptopanic_skip_reason", None),
    }


def _run_record_notification_fields(
    result: Any,
    *,
    profile: str | None,
    notify_burn: bool,
    send_requested: bool,
) -> dict[str, Any]:
    counters = event_alpha_run_counters.canonical_run_counters(result)
    send_state = event_alpha_run_counters.canonical_send_state(result)
    if notify_burn:
        send_state["burn_in_mode"] = (
            "no_send_notification_burn_in"
            if send_state["no_send_rehearsal"]
            else "notification_burn_in_delivery_attempted"
        )
    fields = {
        "counter_schema_version": event_alpha_run_counters.COUNTER_SCHEMA_VERSION,
        "clusters": _int(getattr(result, "clusters", 0)),
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
        "research_review_digest_enabled": bool(getattr(result, "research_review_digest_enabled", False)),
        "research_review_digest_candidates": _int(getattr(result, "research_review_digest_candidates", 0)),
        "research_review_digest_would_send": _int(getattr(result, "research_review_digest_would_send", 0)),
        "research_review_digest_sent": _int(getattr(result, "research_review_digest_sent", 0)),
        "research_review_digest_block_reason": getattr(result, "research_review_digest_block_reason", None),
        "preview_rendered_items": _int(getattr(result, "preview_rendered_items", 0)),
        "preview_eligible_items": _int(getattr(result, "preview_eligible_items", 0)),
        "preview_skipped_items": _int(getattr(result, "preview_skipped_items", 0)),
        "preview_skip_reason_counts": dict(getattr(result, "preview_skip_reason_counts", {}) or {}),
        "integrated_delivery_rows": _int(getattr(result, "integrated_delivery_rows", 0)),
        "integrated_lanes_rendered": dict(getattr(result, "integrated_lanes_rendered", {}) or {}),
        "integrated_lanes_empty": dict(getattr(result, "integrated_lanes_empty", {}) or {}),
        "operator_absolute_path_count": _int(getattr(result, "operator_absolute_path_count", 0)),
        "artifact_doctor_status": getattr(result, "artifact_doctor_status", None),
        "notification_summary": _notification_summary(result, profile=profile, notify_burn=notify_burn),
        "send_block_reason": getattr(result, "send_block_reason", None),
        "sent": _int(getattr(result, "send_items_delivered", 0)) > 0,
    }
    fields.update(counters)
    fields.update(send_state)
    fields.update(event_alpha_run_counters.deprecated_counter_aliases(counters))
    return fields


def _run_record_artifact_write_fields(
    result: Any,
    *,
    raw_card_paths: tuple[str, ...],
    card_paths: tuple[str, ...],
) -> dict[str, Any]:
    return {
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
        "core_opportunity_store_path": getattr(result, "core_opportunity_store_path", None),
        "core_opportunity_write_attempted": bool(getattr(result, "core_opportunity_write_attempted", False)),
        "core_opportunity_write_success": bool(getattr(result, "core_opportunity_write_success", False)),
        "core_opportunity_rows_written": _int(getattr(result, "core_opportunity_rows_written", 0)),
        "core_opportunity_write_block_reason": getattr(result, "core_opportunity_write_block_reason", None),
        "cards_written": _int(getattr(result, "cards_written", len(card_paths))),
        "research_cards_written": _int(getattr(result, "research_cards_written", len(card_paths))),
        "research_card_paths": card_paths,
        "research_card_paths_abs_debug": raw_card_paths if raw_card_paths else (),
        "daily_brief_path": getattr(result, "daily_brief_path", None),
        "notification_preview_path": getattr(result, "notification_preview_path", None),
        "decision_v2_notification_preview_path": getattr(
            result, "decision_v2_notification_preview_path", None
        ),
        "source_coverage_path": getattr(result, "source_coverage_path", None),
        "live_provider_readiness_json_path": getattr(result, "live_provider_readiness_json_path", None),
        "live_provider_readiness_report_path": getattr(result, "live_provider_readiness_report_path", None),
    }


def _run_record_cache_and_path_fields(
    result: Any,
    *,
    catalyst: Any,
    watchlist: Any,
    router: Any,
    llm_stats: Mapping[str, int],
    warnings: list[str],
    success: bool,
    failure: str | None,
) -> dict[str, Any]:
    return {
        "provider_fetch_count": _int(getattr(catalyst, "provider_fetch_count", 0)),
        "provider_cache_hits": _int(getattr(catalyst, "provider_cache_hits", 0)),
        "provider_cache_misses": _int(getattr(catalyst, "provider_cache_misses", 0)),
        "llm_cache_hits": llm_stats["cache_hits"],
        "llm_cache_misses": llm_stats["cache_misses"],
        "llm_calls_attempted": llm_stats["calls_attempted"],
        "llm_calls_succeeded": llm_stats["calls_succeeded"],
        "llm_calls_failed": llm_stats["calls_failed"],
        "llm_skipped_due_budget": llm_stats["skipped_due_budget"],
        "llm_skipped_due_provider_backoff": llm_stats["skipped_due_provider_backoff"],
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
        "research_review_digest_enabled": bool(getattr(result, "research_review_digest_enabled", False)),
        "research_review_digest_candidates": _int(getattr(result, "research_review_digest_candidates", 0)),
        "research_review_digest_would_send": _int(getattr(result, "research_review_digest_would_send", 0)),
        "research_review_digest_sent": _int(getattr(result, "research_review_digest_sent", 0)),
        "research_review_digest_block_reason": getattr(result, "research_review_digest_block_reason", None),
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
        "calls_succeeded": 0,
        "calls_failed": 0,
        "skipped_due_budget": 0,
        "skipped_due_provider_backoff": 0,
    }
    for row in rows:
        status = str(getattr(row, "cache_status", "") or "")
        if status == "hit":
            stats["cache_hits"] += 1
        elif status == "miss":
            stats["cache_misses"] += 1
            stats["calls_attempted"] += 1
            if getattr(row, "analysis", None) is not None or getattr(row, "extraction", None) is not None:
                stats["calls_succeeded"] += 1
            else:
                stats["calls_failed"] += 1
        elif status == "skipped_budget":
            stats["skipped_due_budget"] += 1
        elif status == "skipped_provider_backoff":
            stats["skipped_due_provider_backoff"] += 1
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


def _evidence_acquisition_status_counts(acquisition: Any) -> dict[str, int]:
    out: dict[str, int] = {}
    if acquisition is None:
        return out
    for result in getattr(acquisition, "results", ()) or ():
        status = str(getattr(result, "status", "") or "unknown")
        out[status] = out.get(status, 0) + 1
    return out


def _catalyst_frame_counts(
    result: Any,
    catalyst_frame_rows: Iterable[Any],
) -> dict[str, int]:
    analyzed = len([
        row for row in catalyst_frame_rows
        if getattr(row, "analysis", None) is not None
    ])
    validations = _int(getattr(result, "catalyst_frame_validations_applied", 0))
    disagreements = 0
    unresolved = 0
    skipped = 0
    skip_reasons: dict[str, int] = {}
    discovery = getattr(result, "discovery_result", None)
    raw_events = getattr(discovery, "raw_events", ()) if discovery is not None else ()
    for raw in raw_events or ():
        payload = getattr(raw, "raw_json", None)
        if not isinstance(payload, Mapping):
            continue
        status = str(payload.get("catalyst_frame_status") or "").strip()
        if status in {"missing_required_frame_analysis", "not_required"}:
            skipped += 1
            reason = str(payload.get("catalyst_frame_skip_reason") or status or "unknown").strip()
            skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
        validation = payload.get("llm_catalyst_frame_validation")
        if not isinstance(validation, Mapping):
            continue
        if validation.get("frame_rule_disagreement"):
            disagreements += 1
        if str(validation.get("resolution") or "").strip() == "unresolved":
            unresolved += 1
    return {
        "analyzed": analyzed,
        "validations": validations,
        "disagreements": disagreements,
        "unresolved": unresolved,
        "skipped": skipped,
        "skip_reasons": skip_reasons,
    }


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


def _iso_or_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return _as_utc(value).isoformat()
    return value


def _int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
