"""Split implementation for `crypto_rsi_scanner/event_alpha/outcomes/quality.py` (coverage)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping
from .... import (
    event_alpha_alert_store,
    event_alpha_quality_fields,
    event_alpha_router,
    event_watchlist,
)
from ...artifacts import reason_text as event_alpha_reason_text
from ...artifacts import context as event_alpha_artifacts
from ...radar import core_opportunities as event_core_opportunities
from ...radar import opportunity_verdict as event_opportunity_verdict
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from .... import event_alpha_quality_fields
from ...artifacts import run_ledger as event_alpha_run_ledger
from datetime import datetime, timezone
from types import SimpleNamespace
from .... import (
    event_claim_semantics,
    event_evidence_quality,
    event_incident_graph,
    event_impact_path_validator,
    event_market_confirmation,
)
from crypto_rsi_scanner.event_core.models import NormalizedEvent, RawDiscoveredEvent
from ...radar import incidents as event_incident_store
from .models import *  # noqa: F403

def read_jsonl_rows(path: str | Path, *, row_type: str | None = None) -> list[dict[str, Any]]:
    """Read local JSONL artifact rows, tolerating missing/malformed files."""
    p = Path(path).expanduser()
    if not p.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with p.open("r", encoding="utf-8") as fh:
            for line in fh:
                text = line.strip()
                if not text:
                    continue
                try:
                    row = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, dict):
                    continue
                if row_type is not None and row.get("row_type") != row_type:
                    continue
                rows.append(row)
    except OSError:
        return []
    return rows
def build_latest_run_quality_coverage(
    *,
    profile: str | None = None,
    artifact_namespace: str | None = None,
    run_rows: Iterable[Mapping[str, Any]] = (),
    hypothesis_rows: Iterable[Mapping[str, Any]] = (),
    watchlist_rows: Iterable[Mapping[str, Any]] = (),
    alert_rows: Iterable[Mapping[str, Any]] = (),
    reference_quality_rows: Iterable[Mapping[str, Any]] = (),
    include_legacy: bool = False,
) -> EventAlphaQualityCoverageResult:
    """Build a top-level quality-field coverage report for the newest run only."""
    runs = [dict(row) for row in run_rows if isinstance(row, Mapping)]
    raw_hypotheses = [dict(row) for row in hypothesis_rows if isinstance(row, Mapping)]
    raw_watchlist = [dict(row) for row in watchlist_rows if isinstance(row, Mapping)]
    raw_alerts = [dict(row) for row in alert_rows if isinstance(row, Mapping)]
    raw_reference = [dict(row) for row in reference_quality_rows if isinstance(row, Mapping)]
    latest = event_alpha_run_ledger.latest_run(runs, profile)
    warnings: list[str] = []
    if not latest:
        buckets = (
            _bucket("hypothesis", ()),
            _bucket("watchlist", ()),
            _bucket("alert_snapshot", ()),
        )
        return EventAlphaQualityCoverageResult(
            profile=profile,
            artifact_namespace=artifact_namespace,
            run_id=None,
            status="WARN",
            stale_warning=stale_quality_artifact_warning(
                [*raw_hypotheses, *raw_watchlist, *raw_alerts],
                reference_rows=raw_reference,
            ),
            buckets=buckets,
            warnings=("no_latest_run_row",),
        )

    run_id = str(latest.get("run_id") or "")
    if not run_id:
        warnings.append("latest_run_missing_run_id")
    started = _parse_dt(latest.get("started_at"))
    finished = _parse_dt(latest.get("finished_at")) or started
    if started is None:
        warnings.append("latest_run_missing_started_at")
    if finished is None and started is None:
        warnings.append("latest_run_missing_finished_at")

    hypotheses = [
        dict(row) for row in raw_hypotheses
        if _row_in_latest_run(row, run_id=run_id, include_legacy=include_legacy)
    ]
    alerts = [
        dict(row) for row in raw_alerts
        if _row_in_latest_run(row, run_id=run_id, include_legacy=include_legacy)
    ]
    watchlist = [
        dict(row) for row in raw_watchlist
        if _watchlist_row_in_run_window(row, started=started, finished=finished, include_legacy=include_legacy)
    ]
    buckets = (
        _bucket("hypothesis", hypotheses),
        _bucket("watchlist", watchlist),
        _bucket("alert_snapshot", alerts),
    )
    missing = sum(len(bucket.missing_rows) for bucket in buckets)
    status = "BLOCKED" if missing else "OK"
    if not any(bucket.rows for bucket in buckets):
        status = "WARN"
        warnings.append("latest_run_has_no_quality_rows")
    return EventAlphaQualityCoverageResult(
        profile=profile,
        artifact_namespace=artifact_namespace,
        run_id=run_id or None,
        status=status,
        stale_warning=stale_quality_artifact_warning(
            [*raw_hypotheses, *raw_watchlist, *raw_alerts],
            reference_rows=raw_reference,
        ),
        buckets=buckets,
        warnings=tuple(dict.fromkeys(warnings)),
    )
def stale_quality_artifact_warning(
    rows: Iterable[Mapping[str, Any]],
    *,
    reference_rows: Iterable[Mapping[str, Any]] = (),
) -> str | None:
    """Warn when a namespace looks stale but the quality-validation namespace is clean."""
    current = [dict(row) for row in rows if isinstance(row, Mapping)]
    reference = [dict(row) for row in reference_rows if isinstance(row, Mapping)]
    if not current or not reference:
        return None
    current_missing = any(
        event_alpha_quality_fields.missing_top_level_quality_fields(row)
        for row in current
    )
    reference_clean = bool(reference) and all(
        not event_alpha_quality_fields.missing_top_level_quality_fields(row)
        for row in reference
    )
    return STALE_QUALITY_ARTIFACT_WARNING if current_missing and reference_clean else None
def format_quality_coverage_report(result: EventAlphaQualityCoverageResult) -> str:
    """Return an operator-readable fresh-run quality coverage report."""
    lines = [
        "=" * 76,
        "EVENT ALPHA QUALITY COVERAGE REPORT (fresh artifacts only)",
        "=" * 76,
        f"status: {result.status}",
        f"profile: {result.profile or 'default'}",
        f"namespace: {result.artifact_namespace or 'default'}",
        f"latest_run_id: {result.run_id or 'none'}",
        "required_fields: " + ", ".join(event_alpha_quality_fields.REQUIRED_QUALITY_FIELDS),
        "",
        "coverage:",
    ]
    for bucket in result.buckets:
        lines.append(
            f"- {bucket.row_type}: rows={bucket.rows} complete={bucket.complete} "
            f"missing_rows={len(bucket.missing_rows)}"
        )
        for missing in bucket.missing_rows[:10]:
            lines.append(
                f"  - {missing.row_key}: missing={', '.join(missing.missing_fields)}"
            )
        if len(bucket.missing_rows) > 10:
            lines.append(f"  - +{len(bucket.missing_rows) - 10} more missing rows")
    if result.stale_warning:
        lines.extend(["", f"stale_artifact_warning: {result.stale_warning}"])
    lines.extend(["", "warnings:"])
    lines.extend(f"- {item}" for item in result.warnings) if result.warnings else lines.append("- none")
    lines.append("")
    lines.append("Coverage checks local artifacts only; no sends, trades, paper rows, live RSI rows, or trigger state changed.")
    return "\n".join(lines).rstrip()
def _bucket(row_type: str, rows: Iterable[Mapping[str, Any]]) -> EventAlphaQualityCoverageBucket:
    data = [dict(row) for row in rows if isinstance(row, Mapping)]
    missing_rows: list[EventAlphaQualityCoverageMissingRow] = []
    for row in data:
        missing = event_alpha_quality_fields.missing_top_level_quality_fields(row)
        if missing:
            missing_rows.append(EventAlphaQualityCoverageMissingRow(_row_key(row), missing))
    return EventAlphaQualityCoverageBucket(
        row_type=row_type,
        rows=len(data),
        complete=len(data) - len(missing_rows),
        missing_rows=tuple(missing_rows),
    )
def _row_in_latest_run(row: Mapping[str, Any], *, run_id: str, include_legacy: bool) -> bool:
    data = dict(row)
    if not include_legacy and event_alpha_artifacts.is_legacy_row(data):
        return False
    if not run_id:
        return False
    return str(data.get("run_id") or "") == run_id
def _watchlist_row_in_run_window(
    row: Mapping[str, Any],
    *,
    started: datetime | None,
    finished: datetime | None,
    include_legacy: bool,
) -> bool:
    data = dict(row)
    if started is None:
        return False
    observed = _parse_dt(data.get("last_seen_at") or data.get("observed_at") or data.get("first_seen_at"))
    if observed is None:
        return False
    end = finished or started
    return (started - timedelta(seconds=5)) <= observed <= (end + timedelta(minutes=5))
def _row_key(row: Mapping[str, Any]) -> str:
    for key in (
        "alert_id",
        "alert_key",
        "hypothesis_id",
        "key",
        "event_id",
        "snapshot_id",
        "run_id",
    ):
        value = str(row.get(key) or "").strip()
        if value:
            return value[:160]
    return "unknown_row"
def _parse_dt(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
