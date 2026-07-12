"""Core opportunity store IO helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .... import (
    config,
)
import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
import crypto_rsi_scanner.event_alpha.outcomes.feedback_eligibility as event_feedback_eligibility
import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
from ...artifacts import paths as event_artifact_paths
from .. import core_opportunities as event_core_opportunities
from .. import market_reaction as event_market_reaction
from .. import opportunity_verdict as event_opportunity_verdict
from .models import *  # noqa: F403 - split modules share historical model names


def write_core_opportunities(
    rows: Iterable[Any],
    *,
    cfg: EventCoreOpportunityStoreConfig,
    now: datetime | None = None,
    run_id: str | None = None,
    profile: str | None = None,
    run_mode: str | None = None,
    artifact_namespace: str | None = None,
    card_paths: Iterable[str | Path] = (),
) -> EventCoreOpportunityStoreWriteResult:
    """Append canonical core opportunity rows to a local JSONL artifact."""
    observed = _as_utc(now or datetime.now(timezone.utc)).isoformat()
    card_by_core = _card_path_by_core_id(card_paths)
    opportunities = event_core_opportunities.aggregate_core_opportunities(rows)
    out_rows = [
        _row_from_core_opportunity(
            item,
            generated_at=observed,
            run_id=run_id,
            profile=profile,
            run_mode=run_mode,
            artifact_namespace=artifact_namespace,
            card_path=card_by_core.get(item.core_opportunity_id),
        )
        for item in opportunities
    ]
    path = Path(cfg.path).expanduser()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not out_rows:
            return EventCoreOpportunityStoreWriteResult(path=path, attempted=True, success=True, rows_written=0)
        with path.open("a", encoding="utf-8") as fh:
            for row in out_rows:
                fh.write(json.dumps(_json_ready(row), sort_keys=True, separators=(",", ":")))
                fh.write("\n")
        return EventCoreOpportunityStoreWriteResult(path=path, attempted=True, success=True, rows_written=len(out_rows))
    except Exception as exc:  # noqa: BLE001 - research artifacts must fail soft.
        return EventCoreOpportunityStoreWriteResult(
            path=path,
            attempted=True,
            success=False,
            rows_written=0,
            block_reason=f"{type(exc).__name__}: {exc}",
        )


def load_core_opportunities(
    path: str | Path,
    *,
    limit: int | None = None,
    latest_run: bool = False,
    run_id: str | None = None,
    include_api: bool = True,
) -> EventCoreOpportunityStoreReadResult:
    """Load canonical core rows newest-first, tolerating old/bad rows."""
    p = Path(path).expanduser()
    all_rows = [
        row for row in _read_jsonl(p)
        if row.get("row_type") == "event_core_opportunity"
    ]
    all_rows.sort(key=lambda row: str(row.get("generated_at") or row.get("created_at") or ""), reverse=True)
    latest_id = _latest_run_id(all_rows)
    filtered = list(all_rows)
    if not include_api:
        filtered = [row for row in filtered if str(row.get("schema_version") or "") == EVENT_CORE_OPPORTUNITY_STORE_SCHEMA_VERSION]
    if run_id:
        filtered = [row for row in filtered if str(row.get("run_id") or "") == str(run_id)]
    elif latest_run and latest_id:
        filtered = [row for row in filtered if str(row.get("run_id") or "") == latest_id]
    if limit is not None and limit > 0:
        filtered = filtered[:limit]
    return EventCoreOpportunityStoreReadResult(
        path=p,
        rows_read=len(filtered),
        rows=filtered,
        total_rows_read=len(all_rows),
        latest_run_id=latest_id,
        latest_run_rows_available=sum(1 for row in all_rows if str(row.get("run_id") or "") == latest_id) if latest_id else 0,
        filters={
            "latest_run": bool(latest_run),
            "run_id": run_id,
            "include_api": bool(include_api),
            "limit": limit,
        },
    )


def normalize_core_opportunity_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return canonical raw rows with post-policy final fields persisted.

    Older artifacts can contain stale pre-policy values in fields such as
    ``final_opportunity_level`` even though the canonical read model caps them.
    This helper materializes the same canonical view back to JSONL rows.
    """
    observed = _as_utc(now or datetime.now(timezone.utc)).isoformat()
    opportunities = event_core_opportunities.aggregate_core_opportunities(rows)
    return [
        _row_from_core_opportunity(
            item,
            generated_at=str(item.primary_row.get("generated_at") or observed),
            run_id=_first_text([item.primary_row], ("run_id",)),
            profile=_first_text([item.primary_row], ("profile",)),
            run_mode=_first_text([item.primary_row], ("run_mode",)),
            artifact_namespace=_first_text([item.primary_row], ("artifact_namespace", "namespace")),
            card_path=_first_text([item.primary_row], ("card_path", "research_card_path")),
        )
        for item in opportunities
    ]


def normalize_core_opportunity_store(
    path: str | Path,
    *,
    run_id: str | None = None,
    latest_run: bool = True,
    now: datetime | None = None,
) -> EventCoreOpportunityStoreNormalizeResult:
    """Rewrite current-run core rows so raw artifacts match canonical verdicts."""
    p = Path(path).expanduser()
    try:
        rows = _read_jsonl(p)
        core_rows = [row for row in rows if row.get("row_type") == "event_core_opportunity"]
        if not rows or not core_rows:
            return EventCoreOpportunityStoreNormalizeResult(
                path=p,
                attempted=True,
                success=True,
                rows_read=len(core_rows),
                rows_written=0,
                rows_updated=0,
            )
        target_run_id = str(run_id or "").strip()
        if not target_run_id and latest_run:
            target_run_id = _latest_run_id(core_rows) or ""

        def _is_target(row: Mapping[str, Any]) -> bool:
            if row.get("row_type") != "event_core_opportunity":
                return False
            if target_run_id:
                return str(row.get("run_id") or "") == target_run_id
            return True

        target_rows = [row for row in rows if _is_target(row)]
        if not target_rows:
            return EventCoreOpportunityStoreNormalizeResult(
                path=p,
                attempted=True,
                success=True,
                rows_read=len(core_rows),
                rows_written=0,
                rows_updated=0,
            )
        normalized = normalize_core_opportunity_rows(target_rows, now=now)
        old_ready = [_json_ready(row) for row in target_rows]
        new_ready = [_json_ready(row) for row in normalized]
        if old_ready == new_ready:
            return EventCoreOpportunityStoreNormalizeResult(
                path=p,
                attempted=True,
                success=True,
                rows_read=len(core_rows),
                rows_written=0,
                rows_updated=0,
            )

        new_rows: list[dict[str, Any]] = []
        inserted = False
        for row in rows:
            if _is_target(row):
                if not inserted:
                    new_rows.extend(normalized)
                    inserted = True
                continue
            new_rows.append(row)
        if not inserted:
            new_rows.extend(normalized)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as fh:
            for row in new_rows:
                fh.write(json.dumps(_json_ready(row), sort_keys=True, separators=(",", ":")))
                fh.write("\n")
        return EventCoreOpportunityStoreNormalizeResult(
            path=p,
            attempted=True,
            success=True,
            rows_read=len(core_rows),
            rows_written=len(normalized),
            rows_updated=len(target_rows),
        )
    except Exception as exc:  # noqa: BLE001 - reports must fail soft.
        return EventCoreOpportunityStoreNormalizeResult(
            path=p,
            attempted=True,
            success=False,
            block_reason=f"{type(exc).__name__}: {exc}",
        )


def update_core_opportunity_card_links(
    path: str | Path,
    card_paths: Iterable[str | Path],
    *,
    run_id: str | None = None,
) -> EventCoreOpportunityCardLinkUpdateResult:
    """Rewrite canonical rows with generated research-card paths.

    The Event Alpha cycle writes core rows before rendering cards. Updating the
    existing rows keeps the canonical store authoritative without appending a
    second copy of the same core opportunities.
    """
    p = Path(path).expanduser()
    card_by_core = _card_path_by_core_id(card_paths)
    if not card_by_core:
        return EventCoreOpportunityCardLinkUpdateResult(path=p, attempted=True, success=True, rows_updated=0)
    try:
        rows = _read_jsonl(p)
        updated = 0
        for row in rows:
            if row.get("row_type") != "event_core_opportunity":
                continue
            if run_id and str(row.get("run_id") or "") != str(run_id):
                continue
            core_id = str(row.get("core_opportunity_id") or "").strip()
            card_path = card_by_core.get(core_id)
            if not card_path:
                continue
            rel_card_path = event_artifact_paths.artifact_display_path(card_path)
            if row.get("card_path") == rel_card_path:
                continue
            if event_artifact_paths.has_operator_absolute_path(card_path):
                row.setdefault("card_path_abs_debug", str(card_path))
                row.setdefault("research_card_path_abs_debug", str(card_path))
            row["card_path"] = rel_card_path
            row["research_card_path"] = rel_card_path
            row.setdefault("feedback_target", core_id)
            row.setdefault("feedback_target_type", "core_opportunity_id")
            updated += 1
        if updated:
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("w", encoding="utf-8") as fh:
                for row in rows:
                    fh.write(json.dumps(_json_ready(row), sort_keys=True, separators=(",", ":")))
                    fh.write("\n")
        return EventCoreOpportunityCardLinkUpdateResult(path=p, attempted=True, success=True, rows_updated=updated)
    except Exception as exc:  # noqa: BLE001 - research artifacts must fail soft.
        return EventCoreOpportunityCardLinkUpdateResult(
            path=p,
            attempted=True,
            success=False,
            rows_updated=0,
            block_reason=f"{type(exc).__name__}: {exc}",
        )


def load_canonical_core_opportunity_view(
    profile: str | None,
    artifact_namespace: str | None,
    core_opportunity_id: str,
    *,
    core_store_path: str | Path | None = None,
    alert_store_path: str | Path | None = None,
    evidence_acquisition_path: str | Path | None = None,
    incident_store_path: str | Path | None = None,
    feedback_path: str | Path | None = None,
    research_cards_dir: str | Path | None = None,
    latest_run: bool = True,
    include_api: bool = True,
    now: datetime | None = None,
) -> CanonicalCoreOpportunityView:
    """Load the canonical operator-facing view for one core opportunity.

    The returned object intentionally joins related research artifacts without
    changing any underlying state. It is the read-side source of truth for
    cards, audits, and diagnostics.
    """
    clean = str(core_opportunity_id or "").strip()
    evaluated_at = _as_utc(now or datetime.now(timezone.utc))
    try:
        from ...artifacts import context as event_alpha_artifacts

        context = event_alpha_artifacts.context_from_profile(
            profile,
            artifact_namespace=artifact_namespace,
        )
    except Exception:  # noqa: BLE001 - reports must stay usable with partial config.
        context = None
    resolved_profile = str(profile or getattr(context, "profile", "") or "").strip() or None
    resolved_namespace = str(artifact_namespace or getattr(context, "artifact_namespace", "") or "").strip() or None
    core_path = core_store_path or getattr(context, "core_opportunity_store_path", None)
    alert_path = alert_store_path or getattr(context, "alert_store_path", None)
    acquisition_path = evidence_acquisition_path or getattr(context, "evidence_acquisition_path", None)
    incident_path = incident_store_path or getattr(context, "incident_store_path", None)
    feedback_artifact_path = feedback_path or getattr(context, "feedback_path", None)
    cards_dir = research_cards_dir or getattr(context, "research_cards_dir", None)

    core_rows = load_core_opportunities(
        core_path,
        latest_run=latest_run,
        include_api=include_api,
    ).rows if core_path else []
    alert_rows = _load_alert_rows(alert_path)
    acquisition_rows = _load_acquisition_rows(acquisition_path)
    incident_rows = _load_incident_rows(incident_path)
    feedback_rows = _load_feedback_rows(feedback_artifact_path)
    if context is not None:
        try:
            core_rows = event_alpha_artifacts.filter_artifact_rows(
                core_rows,
                profile=resolved_profile,
                artifact_namespace=resolved_namespace,
                include_test_artifacts=True,
                include_api_artifacts=True,
            )
            alert_rows = event_alpha_artifacts.filter_artifact_rows(
                alert_rows,
                profile=resolved_profile,
                artifact_namespace=resolved_namespace,
                include_test_artifacts=True,
                include_api_artifacts=True,
            )
            acquisition_rows = event_alpha_artifacts.filter_artifact_rows(
                acquisition_rows,
                profile=resolved_profile,
                artifact_namespace=resolved_namespace,
                include_test_artifacts=True,
                include_api_artifacts=True,
            )
            incident_rows = event_alpha_artifacts.filter_artifact_rows(
                incident_rows,
                profile=resolved_profile,
                artifact_namespace=resolved_namespace,
                include_test_artifacts=True,
                include_api_artifacts=True,
            )
        except Exception:  # noqa: BLE001 - artifact joins should remain best-effort.
            pass
    card_paths = _markdown_card_paths(cards_dir)
    return canonical_core_opportunity_view_from_rows(
        clean,
        core_rows=core_rows,
        supporting_rows=alert_rows,
        evidence_acquisition_rows=acquisition_rows,
        alert_rows=alert_rows,
        incident_rows=incident_rows,
        feedback_rows=feedback_rows,
        card_paths=card_paths,
        profile=resolved_profile,
        artifact_namespace=resolved_namespace,
        now=evaluated_at,
    )


def load_core_evidence_acquisition_view(
    profile: str | None,
    artifact_namespace: str | None,
    core_opportunity_id: str,
    *,
    core_store_path: str | Path | None = None,
    evidence_acquisition_path: str | Path | None = None,
    latest_run: bool = True,
    include_api: bool = True,
) -> CoreEvidenceAcquisitionView:
    """Load the operator-facing source-acquisition state for one core opportunity."""
    view = load_canonical_core_opportunity_view(
        profile,
        artifact_namespace,
        core_opportunity_id,
        core_store_path=core_store_path,
        evidence_acquisition_path=evidence_acquisition_path,
        latest_run=latest_run,
        include_api=include_api,
    )
    if not view.found or not view.core_opportunity_id:
        return CoreEvidenceAcquisitionView(core_opportunity_id=str(core_opportunity_id or "").strip())
    return core_evidence_acquisition_view_from_rows(
        view.core_opportunity_id,
        core_rows=[view.canonical_core_row] if view.canonical_core_row else (),
        evidence_acquisition_rows=view.evidence_acquisition_rows,
        supporting_rows=(*view.supporting_rows, *view.diagnostic_rows),
    )


def core_evidence_acquisition_view_from_rows(
    core_opportunity_id: str,
    *,
    core_rows: Iterable[Mapping[str, Any] | object] = (),
    evidence_acquisition_rows: Iterable[Mapping[str, Any] | object] = (),
    supporting_rows: Iterable[Mapping[str, Any] | object] = (),
) -> CoreEvidenceAcquisitionView:
    """Build a canonical acquisition view from already-loaded artifacts."""
    core_row_list = [_row_dict(row) for row in core_rows]
    identifiers = {str(core_opportunity_id or "").strip()}
    for row in core_row_list:
        identifiers.update(_row_identifier_values(row))
    identifiers = {item for item in identifiers if item}
    rows = []
    for row in [
        *_acquisition_candidate_rows(core_row_list),
        *_acquisition_candidate_rows(evidence_acquisition_rows),
        *_acquisition_candidate_rows(supporting_rows),
    ]:
        if _acquisition_row_matches_core(row, identifiers):
            rows.append(row)
    return _build_core_evidence_acquisition_view(core_opportunity_id, rows)


def canonical_core_opportunity_view_from_rows(
    core_opportunity_id: str,
    *,
    core_rows: Iterable[Mapping[str, Any] | object] = (),
    supporting_rows: Iterable[Mapping[str, Any] | object] = (),
    evidence_acquisition_rows: Iterable[Mapping[str, Any] | object] = (),
    alert_rows: Iterable[Mapping[str, Any] | object] = (),
    incident_rows: Iterable[Mapping[str, Any] | object] = (),
    feedback_rows: Iterable[Mapping[str, Any] | object] = (),
    card_paths: Iterable[str | Path] = (),
    profile: str | None = None,
    artifact_namespace: str | None = None,
    now: datetime | None = None,
) -> CanonicalCoreOpportunityView:
    """Build a canonical core-opportunity view from already-loaded artifacts."""
    requested = str(core_opportunity_id or "").strip()
    evaluated_at = _as_utc(now or datetime.now(timezone.utc))
    warnings: list[str] = []
    core_row_list = [_row_dict(row) for row in core_rows]
    support_row_list = [_row_dict(row) for row in supporting_rows]
    acquisition_row_list = [_row_dict(row) for row in evidence_acquisition_rows]
    alert_row_list = [_row_dict(row) for row in alert_rows]
    incident_row_list = [_row_dict(row) for row in incident_rows]
    feedback_row_list = [_row_dict(row) for row in feedback_rows]
    if feedback_row_list:
        eligible_feedback, excluded_feedback, feedback_reason_counts = (
            event_feedback_eligibility.partition_joined_calibration_feedback(
                feedback_row_list,
                core_row_list,
                now=evaluated_at,
            )
        )
    else:
        eligible_feedback, excluded_feedback, feedback_reason_counts = (), (), {}
    feedback_diagnostics = {
        "feedback_rows_supplied": len(feedback_row_list),
        "feedback_rows_eligible": len(eligible_feedback),
        "feedback_rows_matched_to_core": 0,
        "feedback_rows_eligible_other_core": len(eligible_feedback),
        "feedback_rows_excluded": len(excluded_feedback),
        "feedback_exclusion_reason_counts": dict(feedback_reason_counts),
    }
    normalized_card_paths = tuple(Path(path) for path in card_paths)
    if not requested:
        return CanonicalCoreOpportunityView(
            profile=profile,
            artifact_namespace=artifact_namespace,
            requested_core_opportunity_id=requested,
            core_opportunity_id=None,
            found=False,
            **feedback_diagnostics,
            warnings=("missing_core_opportunity_id",),
        )
    resolved_target = _target_from_acquisition_rows(requested, acquisition_row_list) or requested
    core_items = core_opportunities_from_rows(core_row_list)
    opportunity = _find_core_opportunity(resolved_target, core_items)
    if opportunity is None and resolved_target != requested:
        opportunity = _find_core_opportunity(requested, core_items)
    if opportunity is None:
        resolution = event_core_opportunities.resolve_canonical_core_opportunity_id(
            {"core_opportunity_id": resolved_target},
            core_row_list,
        )
        warnings.extend(resolution.warnings)
        if resolution.canonical_core_opportunity_id and resolution.canonical_core_opportunity_id != resolved_target:
            opportunity = _find_core_opportunity(resolution.canonical_core_opportunity_id, core_items)
    if opportunity is None:
        return CanonicalCoreOpportunityView(
            profile=profile,
            artifact_namespace=artifact_namespace,
            requested_core_opportunity_id=requested,
            core_opportunity_id=resolved_target or None,
            found=False,
            **feedback_diagnostics,
            warnings=tuple(dict.fromkeys([*warnings, "core_opportunity_not_found"])),
        )

    canonical_id = opportunity.core_opportunity_id
    canonical_row = _canonical_store_row(canonical_id, core_row_list, opportunity)
    identifiers = _core_view_identifiers(canonical_row, opportunity)
    linked_support = tuple(_unique_rows(
        [row for row in [*support_row_list, *opportunity.supporting_rows] if _row_matches_identifiers(row, identifiers)]
    ))
    linked_diagnostics = tuple(_unique_rows(
        [row for row in [*opportunity.diagnostic_rows, *support_row_list] if _row_is_diagnostic_support(row, canonical_id, identifiers)]
    ))
    linked_acquisition = tuple(_unique_rows(
        [row for row in acquisition_row_list if _row_matches_identifiers(row, identifiers)]
    ))
    linked_alerts = tuple(_unique_rows(
        [row for row in alert_row_list if _row_matches_identifiers(row, identifiers)]
    ))
    linked_incidents = tuple(_unique_rows(
        [row for row in incident_row_list if _incident_matches_identifiers(row, identifiers)]
    ))
    incident_row = _best_incident_row(linked_incidents, canonical_row, opportunity)
    market_refresh_rows = tuple(_unique_rows(
        row for row in [canonical_row, *linked_support, *linked_acquisition, *linked_alerts, *linked_incidents]
        if _is_market_refresh_row(row)
    ))
    card_path = _research_card_path(canonical_row, canonical_id, normalized_card_paths)
    feedback_target = _first_text([canonical_row], ("feedback_target",)) or canonical_id
    canonical_feedback_identity = (
        event_feedback_eligibility.canonical_feedback_join_identity(canonical_row)
    )
    linked_feedback = tuple(
        dict(row)
        for row in eligible_feedback
        if canonical_feedback_identity is not None
        and event_feedback_eligibility.canonical_feedback_join_identity(row)
        == canonical_feedback_identity
    )
    feedback_diagnostics.update({
        "feedback_rows_matched_to_core": len(linked_feedback),
        "feedback_rows_eligible_other_core": (
            len(eligible_feedback) - len(linked_feedback)
        ),
    })
    feedback_status = "has_feedback" if linked_feedback else "pending_or_unknown"
    if requested != canonical_id:
        warnings.append(f"input_target_resolved_to_canonical:{requested}->{canonical_id}")
    return CanonicalCoreOpportunityView(
        profile=profile,
        artifact_namespace=artifact_namespace,
        requested_core_opportunity_id=requested,
        core_opportunity_id=canonical_id,
        found=True,
        canonical_core_row=canonical_row,
        core_opportunity=opportunity,
        supporting_rows=linked_support,
        diagnostic_rows=linked_diagnostics,
        evidence_acquisition_rows=linked_acquisition,
        market_refresh_rows=market_refresh_rows,
        research_card_path=card_path,
        alert_snapshot_rows=linked_alerts,
        incident_row=incident_row,
        incident_rows=linked_incidents,
        feedback_target=feedback_target,
        feedback_status=feedback_status,
        feedback_rows=linked_feedback,
        **feedback_diagnostics,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def core_opportunities_from_rows(rows: Iterable[Mapping[str, Any]]) -> tuple[event_core_opportunities.CoreOpportunity, ...]:
    """Convert stored canonical rows back into CoreOpportunity objects."""
    opportunities = event_core_opportunities.aggregate_core_opportunities(rows)
    normalized_rows = [
        _row_from_core_opportunity(
            item,
            generated_at=str(item.primary_row.get("generated_at") or datetime.now(timezone.utc).isoformat()),
            run_id=_first_text([item.primary_row], ("run_id",)),
            profile=_first_text([item.primary_row], ("profile",)),
            run_mode=_first_text([item.primary_row], ("run_mode",)),
            artifact_namespace=_first_text([item.primary_row], ("artifact_namespace", "namespace")),
            card_path=_first_text([item.primary_row], ("card_path", "research_card_path")),
        )
        for item in opportunities
    ]
    return event_core_opportunities.aggregate_core_opportunities(normalized_rows)


def format_core_opportunity_store_write_result(result: EventCoreOpportunityStoreWriteResult) -> str:
    return "\n".join([
        "Event core opportunities updated: "
        f"{result.path} rows={result.rows_written} success={str(result.success).lower()}"
        + (f" block={result.block_reason}" if result.block_reason else "")
    ])
