"""Profile-scoped canonical CoreOpportunity JSONL artifacts.

The store is research-only. It records the final post-refresh, quality-gated
operator view so daily briefs, near-miss reports, cards, audits, and doctor
checks do not independently recompute conflicting opportunity state.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import (
    config,
    event_alpha_router,
    event_core_opportunities,
    event_artifact_paths,
    event_market_reaction,
    event_opportunity_verdict,
    event_watchlist,
)


EVENT_CORE_OPPORTUNITY_STORE_SCHEMA_VERSION = "event_core_opportunity_store_v1"


@dataclass(frozen=True)
class EventCoreOpportunityStoreConfig:
    path: Path


@dataclass(frozen=True)
class EventCoreOpportunityStoreWriteResult:
    path: Path
    attempted: bool
    success: bool
    rows_written: int = 0
    block_reason: str | None = None


@dataclass(frozen=True)
class EventCoreOpportunityStoreReadResult:
    path: Path
    rows_read: int
    rows: list[dict[str, Any]]
    total_rows_read: int = 0
    latest_run_id: str | None = None
    latest_run_rows_available: int = 0
    filters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EventCoreOpportunityCardLinkUpdateResult:
    path: Path
    attempted: bool
    success: bool
    rows_updated: int = 0
    block_reason: str | None = None


@dataclass(frozen=True)
class EventCoreOpportunityStoreNormalizeResult:
    path: Path
    attempted: bool
    success: bool
    rows_read: int = 0
    rows_written: int = 0
    rows_updated: int = 0
    block_reason: str | None = None


@dataclass(frozen=True)
class CanonicalCoreOpportunityView:
    """Single read model for one operator-facing Event Alpha opportunity."""

    profile: str | None
    artifact_namespace: str | None
    requested_core_opportunity_id: str
    core_opportunity_id: str | None
    found: bool
    canonical_core_row: dict[str, Any] | None = None
    core_opportunity: event_core_opportunities.CoreOpportunity | None = None
    supporting_rows: tuple[dict[str, Any], ...] = ()
    diagnostic_rows: tuple[dict[str, Any], ...] = ()
    evidence_acquisition_rows: tuple[dict[str, Any], ...] = ()
    market_refresh_rows: tuple[dict[str, Any], ...] = ()
    research_card_path: str | None = None
    alert_snapshot_rows: tuple[dict[str, Any], ...] = ()
    incident_row: dict[str, Any] | None = None
    incident_rows: tuple[dict[str, Any], ...] = ()
    feedback_target: str | None = None
    feedback_status: str = "pending_or_unknown"
    feedback_rows: tuple[dict[str, Any], ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def symbol(self) -> str | None:
        return _first_text([self.canonical_core_row or {}], ("symbol", "validated_symbol"))

    @property
    def coin_id(self) -> str | None:
        return _first_text([self.canonical_core_row or {}], ("coin_id", "validated_coin_id"))

    @property
    def opportunity_level(self) -> str | None:
        return _first_text([self.canonical_core_row or {}], ("final_opportunity_level", "opportunity_level"))

    @property
    def final_route_after_quality_gate(self) -> str | None:
        return _first_text([self.canonical_core_row or {}], ("final_route_after_quality_gate", "route"))

    @property
    def final_state_after_quality_gate(self) -> str | None:
        return _first_text([self.canonical_core_row or {}], ("final_state_after_quality_gate", "state"))


@dataclass(frozen=True)
class CoreEvidenceAcquisitionView:
    """Canonical source-acquisition read model for one core opportunity."""

    core_opportunity_id: str
    acquisition_attempted: bool = False
    acquisition_status: str = "not_executed"
    source_pack: str | None = None
    accepted_evidence_count: int = 0
    rejected_evidence_count: int = 0
    accepted_reason_codes: tuple[str, ...] = ()
    rejected_reason_codes: tuple[str, ...] = ()
    accepted_provider_counts: Mapping[str, int] | None = None
    rejected_provider_counts: Mapping[str, int] | None = None
    accepted_reason_code_counts: Mapping[str, int] | None = None
    accepted_evidence_samples: tuple[dict[str, Any], ...] = ()
    rejected_evidence_samples: tuple[dict[str, Any], ...] = ()
    provider_failures: tuple[str, ...] = ()
    evidence_quality_before: float | None = None
    evidence_quality_after: float | None = None
    opportunity_score_before: float | None = None
    opportunity_score_after: float | None = None
    opportunity_level_before: str | None = None
    opportunity_level_after: str | None = None
    final_upgrade_status: str | None = None
    no_upgrade_reason: str | None = None
    diagnostic_rows: tuple[dict[str, Any], ...] = ()

    def to_metadata(self) -> dict[str, Any]:
        return {
            "status": self.acquisition_status,
            "source_pack": self.source_pack,
            "accepted": self.accepted_evidence_count,
            "rejected": self.rejected_evidence_count,
            "accepted_reason_codes": self.accepted_reason_codes,
            "rejected_reason_codes": self.rejected_reason_codes,
            "accepted_provider_counts": dict(self.accepted_provider_counts or {}),
            "rejected_provider_counts": dict(self.rejected_provider_counts or {}),
            "accepted_reason_code_counts": dict(self.accepted_reason_code_counts or {}),
            "provider_failures": self.provider_failures,
            "evidence_quality_before": self.evidence_quality_before,
            "evidence_quality_after": self.evidence_quality_after,
            "opportunity_score_before": self.opportunity_score_before,
            "opportunity_score_after": self.opportunity_score_after,
            "opportunity_level_before": self.opportunity_level_before,
            "opportunity_level_after": self.opportunity_level_after,
            "final_upgrade_status": self.final_upgrade_status,
            "no_upgrade_reason": self.no_upgrade_reason,
        }


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
    include_legacy: bool = True,
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
    if not include_legacy:
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
            "include_legacy": bool(include_legacy),
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
    include_legacy: bool = True,
) -> CanonicalCoreOpportunityView:
    """Load the canonical operator-facing view for one core opportunity.

    The returned object intentionally joins related research artifacts without
    changing any underlying state. It is the read-side source of truth for
    cards, audits, and diagnostics.
    """
    clean = str(core_opportunity_id or "").strip()
    try:
        from . import event_alpha_artifacts

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
        include_legacy=include_legacy,
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
                include_legacy_artifacts=True,
            )
            alert_rows = event_alpha_artifacts.filter_artifact_rows(
                alert_rows,
                profile=resolved_profile,
                artifact_namespace=resolved_namespace,
                include_test_artifacts=True,
                include_legacy_artifacts=True,
            )
            acquisition_rows = event_alpha_artifacts.filter_artifact_rows(
                acquisition_rows,
                profile=resolved_profile,
                artifact_namespace=resolved_namespace,
                include_test_artifacts=True,
                include_legacy_artifacts=True,
            )
            incident_rows = event_alpha_artifacts.filter_artifact_rows(
                incident_rows,
                profile=resolved_profile,
                artifact_namespace=resolved_namespace,
                include_test_artifacts=True,
                include_legacy_artifacts=True,
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
    )


def load_core_evidence_acquisition_view(
    profile: str | None,
    artifact_namespace: str | None,
    core_opportunity_id: str,
    *,
    core_store_path: str | Path | None = None,
    evidence_acquisition_path: str | Path | None = None,
    latest_run: bool = True,
    include_legacy: bool = True,
) -> CoreEvidenceAcquisitionView:
    """Load the operator-facing source-acquisition state for one core opportunity."""
    view = load_canonical_core_opportunity_view(
        profile,
        artifact_namespace,
        core_opportunity_id,
        core_store_path=core_store_path,
        evidence_acquisition_path=evidence_acquisition_path,
        latest_run=latest_run,
        include_legacy=include_legacy,
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
) -> CanonicalCoreOpportunityView:
    """Build a canonical core-opportunity view from already-loaded artifacts."""
    requested = str(core_opportunity_id or "").strip()
    warnings: list[str] = []
    core_row_list = [_row_dict(row) for row in core_rows]
    support_row_list = [_row_dict(row) for row in supporting_rows]
    acquisition_row_list = [_row_dict(row) for row in evidence_acquisition_rows]
    alert_row_list = [_row_dict(row) for row in alert_rows]
    incident_row_list = [_row_dict(row) for row in incident_rows]
    feedback_row_list = [_row_dict(row) for row in feedback_rows]
    normalized_card_paths = tuple(Path(path) for path in card_paths)
    if not requested:
        return CanonicalCoreOpportunityView(
            profile=profile,
            artifact_namespace=artifact_namespace,
            requested_core_opportunity_id=requested,
            core_opportunity_id=None,
            found=False,
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
    linked_feedback = tuple(_unique_rows(
        [row for row in feedback_row_list if _feedback_matches(row, identifiers, feedback_target)]
    ))
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


def merge_core_opportunity_verdict(
    initial: Mapping[str, Any] | None,
    market_refresh: Mapping[str, Any] | None = None,
    evidence_acquisition: Mapping[str, Any] | None = None,
    support_rows: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Return the deterministic final state from compatible candidate rows.

    Higher-quality final core rows win over stale supporting rows. Diagnostics
    are retained as support metadata by the aggregator and cannot downgrade the
    canonical visible opportunity.
    """
    rows: list[Mapping[str, Any]] = []
    for row in (initial, market_refresh, evidence_acquisition):
        if isinstance(row, Mapping) and row:
            rows.append(row)
    rows.extend(row for row in support_rows if isinstance(row, Mapping) and row)
    opportunities = event_core_opportunities.aggregate_core_opportunities(rows)
    if not opportunities:
        return {}
    item = opportunities[0]
    return _row_from_core_opportunity(
        item,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def format_core_opportunity_store_write_result(result: EventCoreOpportunityStoreWriteResult) -> str:
    return "\n".join([
        "Event core opportunities updated: "
        f"{result.path} rows={result.rows_written} success={str(result.success).lower()}"
        + (f" block={result.block_reason}" if result.block_reason else "")
    ])


def _row_from_core_opportunity(
    item: event_core_opportunities.CoreOpportunity,
    *,
    generated_at: str,
    run_id: str | None = None,
    profile: str | None = None,
    run_mode: str | None = None,
    artifact_namespace: str | None = None,
    card_path: str | Path | None = None,
) -> dict[str, Any]:
    primary = dict(item.primary_row)
    support = [dict(row) for row in item.supporting_rows]
    diagnostics = [dict(row) for row in item.diagnostic_rows]
    all_rows = [primary, *support, *diagnostics]
    market_before = _best_float(all_rows, ("market_confirmation_before", "market_confirmation_score_before"))
    market_after = _best_float(all_rows, ("market_confirmation_after", "market_confirmation_score_after", "market_confirmation_score"))
    evidence_before = _best_float(all_rows, ("evidence_quality_before", "evidence_quality_score_before"))
    evidence_after = _best_float(all_rows, ("evidence_quality_after", "evidence_quality_score_after", "evidence_quality_score"))
    source_pack = _best_source_pack(all_rows, item.primary_impact_path)
    source_class = _first_text(all_rows, ("source_class",))
    evidence_specificity = _first_text(all_rows, ("evidence_specificity",))
    evidence_score = evidence_after if evidence_after is not None else _first_float(all_rows, ("evidence_quality_score",))
    market_level = _first_text(all_rows, ("market_confirmation_level", "market_reaction_confirmation", "post_refresh_market_confirmation_level"))
    impact_path_reason = (
        _first_text(all_rows, ("impact_path_reason",))
        or _canonical_impact_path_reason(item.primary_impact_path, source_pack)
    )
    impact_path_strength = (
        _first_text(all_rows, ("impact_path_strength",))
        or _canonical_impact_path_strength(item.opportunity_level, item.primary_impact_path, evidence_score, market_after)
    )
    initial_level = _first_text(all_rows, ("initial_opportunity_level", "opportunity_level_before", "opportunity_level_pre_refresh")) or item.opportunity_level
    initial_score = _first_float(all_rows, ("initial_opportunity_score", "opportunity_score_before", "opportunity_score_pre_refresh"))
    post_level = _first_text(all_rows, ("post_refresh_opportunity_level", "refreshed_opportunity_level", "opportunity_level_after_market_refresh")) or item.opportunity_level
    post_score = _first_float(all_rows, ("post_refresh_opportunity_score", "refreshed_opportunity_score", "opportunity_score_after_market_refresh"))
    market_context = _best_market_context(all_rows)
    derivatives_confirmation = _best_confirmation_context(
        all_rows,
        score_keys=("derivatives_confirmation_score",),
        level_keys=("derivatives_confirmation_level",),
        reasons_keys=("derivatives_confirmation_reasons",),
        freshness_keys=("derivatives_freshness_status",),
    )
    dex_liquidity_confirmation = _best_confirmation_context(
        all_rows,
        score_keys=("dex_liquidity_score",),
        level_keys=("dex_liquidity_level",),
        reasons_keys=("dex_liquidity_reasons",),
        freshness_keys=("dex_freshness_status",),
    )
    protocol_metrics_confirmation = _best_confirmation_context(
        all_rows,
        score_keys=("protocol_metrics_score",),
        level_keys=("protocol_metrics_level",),
        reasons_keys=("protocol_metrics_reasons",),
        freshness_keys=("protocol_metrics_freshness_status",),
    )
    acquisition = _build_core_evidence_acquisition_view(item.core_opportunity_id, all_rows)
    source_pack = acquisition.source_pack or source_pack
    evidence_before = acquisition.evidence_quality_before if acquisition.evidence_quality_before is not None else evidence_before
    evidence_after = acquisition.evidence_quality_after if acquisition.evidence_quality_after is not None else evidence_after
    evidence_score = evidence_after if evidence_after is not None else evidence_score
    if str(market_level or "").casefold() in {"", "unknown", "missing", "none", "insufficient_data"} and market_after is not None:
        market_level = _market_level_from_score(market_after)
    impact_path_reason = impact_path_reason or _canonical_impact_path_reason(item.primary_impact_path, source_pack)
    if str(impact_path_strength or "").casefold() in {"", "unknown", "missing", "none", "insufficient_data"} and str(item.primary_impact_path or "").casefold() not in {"", "unknown", "missing", "none", "insufficient_data", "generic_cooccurrence_only"}:
        impact_path_strength = _canonical_impact_path_strength(item.opportunity_level, item.primary_impact_path, evidence_score, market_after)
    initial_level = acquisition.opportunity_level_before or initial_level
    initial_score = acquisition.opportunity_score_before if acquisition.opportunity_score_before is not None else initial_score
    post_level = acquisition.opportunity_level_after or post_level
    post_score = acquisition.opportunity_score_after if acquisition.opportunity_score_after is not None else post_score
    accepted_source = _accepted_evidence_source_summary(acquisition.accepted_evidence_samples)
    latest_source = _first_real_text(all_rows, ("latest_source", "source", "source_provider", "provider")) or accepted_source.get("provider")
    source_count = _canonical_source_count(all_rows, acquisition)
    market_summary = _canonical_market_summary(
        market_level=market_level,
        market_score=market_after,
        market_context=market_context,
    )
    market_snapshot = _best_market_snapshot(all_rows)
    if not market_snapshot and market_after is not None:
        market_snapshot = {
            "market_confirmation_level": market_level,
            "market_confirmation_score": market_after,
            "market_context_source": market_context.get("market_context_source"),
            "market_context_freshness_status": market_context.get("market_context_freshness_status"),
            "market_context_age_hours": market_context.get("market_context_age_hours"),
            "summary_only": True,
        }
    support_ids = _row_ids(support)
    diagnostic_ids = _row_ids(diagnostics)
    live_policy_input = {
        **primary,
        "profile": profile or primary.get("profile"),
        "run_mode": run_mode or primary.get("run_mode"),
        "artifact_namespace": artifact_namespace or primary.get("artifact_namespace"),
        "symbol": item.symbol,
        "coin_id": item.coin_id,
        "candidate_role": item.candidate_role,
        "impact_path_type": item.primary_impact_path,
        "primary_impact_path": item.primary_impact_path,
        "opportunity_level": item.opportunity_level,
        "final_opportunity_level": item.opportunity_level,
        "opportunity_score_final": item.opportunity_score_final,
        "final_opportunity_score": item.opportunity_score_final,
        "source_class": source_class,
        "evidence_specificity": evidence_specificity,
        "evidence_quality_score": evidence_score,
        "market_confirmation_score": market_after,
        "market_confirmation_level": market_level,
        "market_context_freshness_status": market_context.get("market_context_freshness_status"),
        "canonical_incident_name": item.canonical_incident_name,
        "incident_canonical_name": item.canonical_incident_name,
        "latest_event_name": _first_text(all_rows, ("latest_event_name", "event_name", "canonical_incident_name")),
        "event_name": _first_text(all_rows, ("event_name", "latest_event_name", "canonical_incident_name")),
        "latest_source_title": accepted_source.get("title") or _first_text(all_rows, ("latest_source_title", "source_title", "title")),
        "source_title": accepted_source.get("title") or _first_text(all_rows, ("source_title", "latest_source_title", "title")),
        "supporting_categories": list(item.supporting_categories),
        "supporting_impact_paths": list(item.supporting_impact_paths),
        "playbook_type": item.primary_impact_path,
        "effective_playbook_type": item.primary_impact_path,
        "impact_path_reason": impact_path_reason,
        "evidence_acquisition_status": acquisition.acquisition_status,
        "evidence_acquisition_accepted_count": acquisition.accepted_evidence_count,
        "evidence_acquisition_rejected_count": acquisition.rejected_evidence_count,
        "accepted_evidence_count": acquisition.accepted_evidence_count,
        "rejected_evidence_count": acquisition.rejected_evidence_count,
        "accepted_evidence_reason_codes": list(acquisition.accepted_reason_codes),
        "accepted_provider_counts": dict(acquisition.accepted_provider_counts or {}),
        "rejected_provider_counts": dict(acquisition.rejected_provider_counts or {}),
        "accepted_reason_code_counts": dict(acquisition.accepted_reason_code_counts or {}),
        "source_pack": source_pack,
    }
    live_policy = event_opportunity_verdict.apply_live_confirmation_policy(
        live_policy_input,
        profile=profile,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
        allow_sector_digest=bool(config.EVENT_ALPHA_ALLOW_SECTOR_DIGEST),
        allow_source_only_narrative_digest=bool(config.EVENT_ALPHA_ALLOW_SOURCE_ONLY_NARRATIVE_DIGEST),
    )
    final_level = live_policy.capped_level or item.opportunity_level
    final_score = live_policy.capped_score if live_policy.capped_score is not None else item.opportunity_score_final
    final_state = _canonical_core_state(item, final_level, live_policy)
    final_route, route_adjustment_reason = _canonical_core_route(item, primary, final_level=final_level)
    final_verdict_reason = (
        _first_text(all_rows, ("final_verdict_reason", "quality_gate_block_reason", "route_reason", "opportunity_verdict_reason"))
        or _default_core_verdict_reason(item.opportunity_level)
    )
    if live_policy.required and not live_policy.confirmed and live_policy.reason:
        final_verdict_reason = (
            f"Live confirmation gate capped {item.opportunity_level} to {final_level}: "
            f"{live_policy.reason}."
        )
    if route_adjustment_reason and not (live_policy.required and not live_policy.confirmed):
        final_verdict_reason = _canonical_route_adjusted_verdict_reason(final_level)
    acquisition_confirmation = event_opportunity_verdict.classify_acquisition_confirmation(live_policy_input)
    reaction = event_market_reaction.evaluate_market_reaction({
        **live_policy_input,
        "market_snapshot": market_snapshot,
        "market_confirmation_level": market_level,
        "market_confirmation_score": market_after,
        "market_context_freshness_status": market_context.get("market_context_freshness_status"),
    })
    official_event = _first_mapping(all_rows, ("official_exchange_event",))
    scheduled_event = _first_mapping(all_rows, ("scheduled_catalyst_event",))
    unlock_event = _first_mapping(all_rows, ("unlock_event",))
    derivatives_state_snapshot = _first_mapping(all_rows, ("derivatives_state_snapshot", "derivatives_snapshot"))
    crowding_class = _first_text(all_rows, ("crowding_class",))
    fade_readiness = _first_text(all_rows, ("fade_readiness",))
    crowding_exhaustion_evidence = _first_list(all_rows, ("crowding_exhaustion_evidence",))
    what_confirms_fade_review = _first_list(all_rows, ("what_confirms_fade_review",))
    what_invalidates_fade_review = _first_list(all_rows, ("what_invalidates_fade_review",))
    derivatives_warning_codes = list(dict.fromkeys((
        *_first_list(all_rows, ("derivatives_warning_codes",)),
        *_first_list(all_rows, ("warnings",)),
    )))
    latest_source_url = (
        accepted_source.get("source_url")
        or _first_text(all_rows, ("latest_source_url", "source_url", "official_exchange_url"))
        or _mapping_text(official_event, ("source_url", "url"))
        or _mapping_text(scheduled_event, ("source_url", "url"))
        or _mapping_text(unlock_event, ("source_url", "url"))
    )
    latest_source_title = (
        accepted_source.get("title")
        or _first_text(all_rows, ("latest_source_title", "source_title", "title", "event_name"))
        or _mapping_text(official_event, ("title", "event_name"))
        or _mapping_text(scheduled_event, ("title", "event_name"))
        or _mapping_text(unlock_event, ("title", "event_name"))
    )
    latest_source_provider = (
        accepted_source.get("provider")
        or latest_source
        or _mapping_text(official_event, ("provider", "exchange"))
        or _mapping_text(scheduled_event, ("provider", "source_class"))
        or _mapping_text(unlock_event, ("provider", "source_class"))
    )
    row = {
        "schema_version": EVENT_CORE_OPPORTUNITY_STORE_SCHEMA_VERSION,
        "row_type": "event_core_opportunity",
        "run_id": run_id,
        "profile": profile,
        "run_mode": run_mode,
        "artifact_namespace": artifact_namespace,
        "core_opportunity_id": item.core_opportunity_id,
        "symbol": item.symbol,
        "coin_id": item.coin_id,
        "incident_id": item.incident_id,
        "canonical_incident_name": item.canonical_incident_name,
        "candidate_role": item.candidate_role,
        "primary_impact_path": item.primary_impact_path,
        "impact_path_type": item.primary_impact_path,
        "relationship_type": item.primary_impact_path,
        "playbook_type": item.primary_impact_path,
        "effective_playbook_type": item.primary_impact_path,
        "latest_playbook_type": item.primary_impact_path,
        "state": final_state,
        "tier": final_route,
        "latest_tier": final_route,
        "route": final_route,
        "primary_hypothesis_id": _first_text([primary], ("hypothesis_id", "primary_hypothesis_id")),
        "supporting_hypothesis_ids": list(item.supporting_hypothesis_ids),
        "supporting_categories": list(item.supporting_categories),
        "supporting_impact_paths": list(item.supporting_impact_paths),
        "supporting_evidence_quotes": list(item.supporting_evidence_quotes),
        "evidence_quotes": list(item.supporting_evidence_quotes),
        "source_count": source_count,
        "latest_source": latest_source,
        "latest_source_url": latest_source_url,
        "latest_source_title": latest_source_title,
        "source_provider": latest_source_provider,
        "source_url": latest_source_url,
        "official_exchange_event": official_event,
        "official_exchange_provider": _mapping_text(official_event, ("provider",)),
        "official_exchange": _mapping_text(official_event, ("exchange",)),
        "official_exchange_event_type": _mapping_text(official_event, ("event_type",)),
        "official_exchange_title": _mapping_text(official_event, ("title", "event_name")),
        "official_exchange_url": _mapping_text(official_event, ("source_url", "url")),
        "official_exchange_published_at": _mapping_text(official_event, ("published_at",)),
        "official_exchange_effective_time": _mapping_text(official_event, ("effective_time",)),
        "official_exchange_reason_codes": _mapping_list(official_event, ("reason_codes",)),
        "scheduled_catalyst_event": scheduled_event,
        "unlock_event": unlock_event,
        "derivatives_state_snapshot": derivatives_state_snapshot,
        "crowding_class": crowding_class,
        "fade_readiness": fade_readiness,
        "crowding_exhaustion_evidence": crowding_exhaustion_evidence,
        "what_confirms_fade_review": what_confirms_fade_review,
        "what_invalidates_fade_review": what_invalidates_fade_review,
        "derivatives_warning_codes": derivatives_warning_codes,
        "supporting_row_ids": support_ids,
        "diagnostic_row_ids": diagnostic_ids,
        "diagnostic_row_count": item.diagnostic_row_count,
        "hidden_diagnostic_count": item.diagnostic_row_count,
        "source_noise_control_count": item.source_noise_control_count,
        "quality_capped_support_count": item.quality_capped_supporting_rows,
        "initial_opportunity_level": initial_level,
        "initial_opportunity_score": initial_score if initial_score is not None else item.opportunity_score_final,
        "market_refresh_attempted": _any_truthy(all_rows, ("market_refresh_attempted", "targeted_market_refresh_attempted")),
        "market_refresh_success": _any_truthy(all_rows, ("market_refresh_success", "targeted_market_refresh_success")),
        "market_snapshot": market_snapshot,
        "latest_market_snapshot": market_snapshot,
        "market_state_snapshot": reaction.market_state_snapshot.to_dict(),
        "market_state": reaction.market_state,
        "market_state_class": reaction.market_state,
        "opportunity_type": reaction.opportunity_type,
        "opportunity_type_why_now": reaction.why_now,
        "opportunity_type_evidence": list(reaction.evidence_summary),
        "opportunity_type_what_confirms": list(reaction.what_confirms),
        "opportunity_type_what_invalidates": list(reaction.what_invalidates),
        "opportunity_type_why_not_alertable": list(reaction.why_not_alertable),
        "opportunity_type_source_requirements_met": reaction.source_requirements_met,
        "opportunity_type_market_requirements_met": reaction.market_requirements_met,
        "opportunity_type_fade_requirements_met": reaction.fade_requirements_met,
        "opportunity_type_source_strength": reaction.source_strength,
        "opportunity_type_warnings": list(reaction.warnings),
        "opportunity_type_reason_codes": list(reaction.reason_codes),
        "source_strength": reaction.source_strength,
        "source_requirements_met": reaction.source_requirements_met,
        "market_requirements_met": reaction.market_requirements_met,
        "fade_requirements_met": reaction.fade_requirements_met,
        "why_now": reaction.why_now,
        "what_confirms": list(reaction.what_confirms),
        "what_invalidates": list(reaction.what_invalidates),
        "why_not_alertable": list(reaction.why_not_alertable),
        "opportunity_type_warnings_compact": list(reaction.warnings),
        "market_context_freshness_status": market_context.get("market_context_freshness_status"),
        "market_context_source": market_context.get("market_context_source"),
        "market_context_observed_at": market_context.get("market_context_observed_at"),
        "market_context_age_hours": market_context.get("market_context_age_hours"),
        "market_context_freshness_cap_applied": bool(market_context.get("market_context_freshness_cap_applied")),
        "market_context_data_quality": market_context.get("market_context_data_quality"),
        "integrated_market_confirmation_level": _first_text(all_rows, ("integrated_market_confirmation_level",)),
        "integrated_market_confirmation_score": _first_float(all_rows, ("integrated_market_confirmation_score",)),
        "integrated_market_reaction_confirmation": _first_text(all_rows, ("integrated_market_reaction_confirmation",)),
        "integrated_market_context_source": _first_text(all_rows, ("integrated_market_context_source",)),
        "integrated_market_freshness_status": _first_text(all_rows, ("integrated_market_freshness_status",)),
        "market_confirmation_score": market_after,
        "market_confirmation_level": market_level,
        "market_confirmation_summary": market_summary,
        "derivatives_confirmation_score": derivatives_confirmation.get("score"),
        "derivatives_confirmation_level": derivatives_confirmation.get("level"),
        "derivatives_confirmation_reasons": list(derivatives_confirmation.get("reasons") or ()),
        "derivatives_freshness_status": derivatives_confirmation.get("freshness_status"),
        "dex_liquidity_score": dex_liquidity_confirmation.get("score"),
        "dex_liquidity_level": dex_liquidity_confirmation.get("level"),
        "dex_liquidity_reasons": list(dex_liquidity_confirmation.get("reasons") or ()),
        "dex_freshness_status": dex_liquidity_confirmation.get("freshness_status"),
        "protocol_metrics_score": protocol_metrics_confirmation.get("score"),
        "protocol_metrics_level": protocol_metrics_confirmation.get("level"),
        "protocol_metrics_reasons": list(protocol_metrics_confirmation.get("reasons") or ()),
        "protocol_metrics_freshness_status": protocol_metrics_confirmation.get("freshness_status"),
        "market_data_freshness": market_context.get("market_context_freshness_status"),
        "market_reaction_confirmation": market_level,
        "market_confirmation_before": market_before,
        "market_confirmation_after": market_after,
        "main_frame_type": _first_text(all_rows, ("main_frame_type",)),
        "main_frame_role": _first_text(all_rows, ("main_frame_role",)),
        "main_frame_subject": _first_text(all_rows, ("main_frame_subject",)),
        "main_frame_actor": _first_text(all_rows, ("main_frame_actor",)),
        "main_frame_object": _first_text(all_rows, ("main_frame_object",)),
        "main_frame_evidence_quote": _first_text(all_rows, ("main_frame_evidence_quote",)),
        "frame_status": _first_text(all_rows, ("frame_status", "catalyst_frame_status")),
        "selected_main_catalyst_reason": _first_text(all_rows, ("selected_main_catalyst_reason",)),
        "rule_predicted_impact_path": _first_text(all_rows, ("rule_predicted_impact_path",)),
        "llm_predicted_main_frame_type": _first_text(all_rows, ("llm_predicted_main_frame_type",)),
        "frame_rule_disagreement": _first_value(all_rows, ("frame_rule_disagreement",)),
        "negated_frame_ids": _first_list(all_rows, ("negated_frame_ids",)),
        "corrective_frame_ids": _first_list(all_rows, ("corrective_frame_ids",)),
        "frame_summary": _first_list(all_rows, ("frame_summary",)),
        "evidence_acquisition_attempted": acquisition.acquisition_attempted or _any_truthy(all_rows, ("evidence_acquisition_attempted", "source_acquisition_attempted")),
        "evidence_acquisition_status": acquisition.acquisition_status or _first_text(all_rows, ("evidence_acquisition_status", "acquisition_status", "source_acquisition_status")),
        "evidence_acquisition_source_pack": source_pack,
        "source_pack": source_pack,
        "evidence_acquisition_accepted_count": acquisition.accepted_evidence_count,
        "evidence_acquisition_rejected_count": acquisition.rejected_evidence_count,
        "accepted_evidence_count": acquisition.accepted_evidence_count,
        "rejected_evidence_count": acquisition.rejected_evidence_count,
        "accepted_provider_counts": dict(acquisition.accepted_provider_counts or {}),
        "rejected_provider_counts": dict(acquisition.rejected_provider_counts or {}),
        "accepted_reason_code_counts": dict(acquisition.accepted_reason_code_counts or {}),
        "evidence_acquisition_accepted_evidence": list(acquisition.accepted_evidence_samples),
        "evidence_acquisition_rejected_samples": list(acquisition.rejected_evidence_samples),
        "accepted_evidence_reason_codes": list(acquisition.accepted_reason_codes),
        "rejected_evidence_reason_codes": list(acquisition.rejected_reason_codes),
        "evidence_acquisition_provider_failures": list(acquisition.provider_failures),
        "evidence_acquisition_results": {
            **acquisition.to_metadata(),
            "acquisition_evidence_status": _first_text(all_rows, ("acquisition_evidence_status",)),
        },
        "final_upgrade_status": acquisition.final_upgrade_status or _first_text(all_rows, ("final_upgrade_status", "acquisition_upgrade_status")),
        "no_upgrade_reason": acquisition.no_upgrade_reason or _first_text(all_rows, ("no_upgrade_reason",)),
        "source_class": source_class,
        "evidence_specificity": evidence_specificity,
        "evidence_quality_score": evidence_score,
        "evidence_quality_before": evidence_before,
        "evidence_quality_after": evidence_after,
        "impact_path_strength": impact_path_strength,
        "impact_path_reason": impact_path_reason,
        "digest_eligible_by_impact_path": final_level in {"validated_digest", "watchlist", "high_priority"},
        "manual_verification_items": _canonical_manual_verification_items(item, source_pack, final_level=final_level, live_policy=live_policy),
        "upgrade_requirements": _canonical_upgrade_requirements(final_level, live_policy=live_policy),
        "downgrade_warnings": _canonical_downgrade_warnings(item.primary_impact_path, final_level),
        "post_refresh_opportunity_level": post_level,
        "post_refresh_opportunity_score": post_score if post_score is not None else item.opportunity_score_final,
        "requested_opportunity_level_before_live_confirmation": item.opportunity_level,
        "requested_opportunity_score_before_live_confirmation": item.opportunity_score_final,
        "requested_route_before_live_confirmation": item.final_route_after_quality_gate,
        "requested_state_before_live_confirmation": item.final_state_after_quality_gate,
        "final_opportunity_level": final_level,
        "final_opportunity_score": final_score,
        "opportunity_level": final_level,
        "opportunity_score_final": final_score,
        "final_state_after_quality_gate": final_state,
        "final_route_after_quality_gate": final_route,
        "final_tier_after_quality_gate": final_route,
        "canonical_route_adjustment_reason": route_adjustment_reason,
        "live_confirmation_required": live_policy.required,
        "live_confirmation_passed": live_policy.confirmed,
        "live_confirmation_status": live_policy.status,
        "live_confirmation_reason": live_policy.reason,
        "live_confirmation_capped": bool(live_policy.capped_level),
        "live_confirmation_original_level": item.opportunity_level,
        "live_confirmation_capped_level": live_policy.capped_level,
        "live_confirmation_missing_requirements": list(live_policy.missing_requirements),
        "acquisition_confirms_candidate": acquisition_confirmation.confirms_candidate,
        "acquisition_confirms_impact_path": acquisition_confirmation.confirms_impact_path,
        "acquisition_confirmation_status": acquisition_confirmation.status,
        "acquisition_confirmation_reason": acquisition_confirmation.reason,
        "source_pack_confirmation_status": acquisition_confirmation.status,
        "final_verdict_source": _first_text(all_rows, ("final_verdict_source", "opportunity_verdict_source", "verdict_source")) or "core_opportunity_merge",
        "final_verdict_reason": final_verdict_reason,
        "why_opportunity_visible": item.why_opportunity_visible,
        "why_other_rows_hidden": item.why_other_rows_hidden,
        "card_path": event_artifact_paths.artifact_display_path(card_path) if card_path else None,
        "research_card_path": event_artifact_paths.artifact_display_path(card_path) if card_path else None,
        "feedback_target": item.core_opportunity_id,
        "feedback_target_type": "core_opportunity_id",
        "generated_at": generated_at,
    }
    if card_path and event_artifact_paths.has_operator_absolute_path(card_path):
        row["card_path_abs_debug"] = str(card_path)
        row["research_card_path_abs_debug"] = str(card_path)
    return _apply_integrated_candidate_truth(row, primary=primary, all_rows=all_rows, reaction=reaction)


def _canonical_core_route(
    item: event_core_opportunities.CoreOpportunity,
    primary: Mapping[str, Any],
    *,
    final_level: str | None = None,
) -> tuple[str, str | None]:
    current = str(item.final_route_after_quality_gate or "").strip()
    level = str(final_level or item.opportunity_level or "").strip()
    if current == event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH.value:
        return current, None
    if level not in {
        event_opportunity_verdict.OpportunityLevel.VALIDATED_DIGEST.value,
        event_opportunity_verdict.OpportunityLevel.WATCHLIST.value,
        event_opportunity_verdict.OpportunityLevel.HIGH_PRIORITY.value,
    } and current in {
        event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
        event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
    }:
        return (
            event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
            f"core_route_capped_by_live_confirmation:{level}",
        )
    if current in {
        event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
        event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
        event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE.value,
    }:
        return current, None
    if _core_route_quality_blocked(primary):
        return current or event_alpha_router.EventAlphaRoute.STORE_ONLY.value, None
    if level == event_opportunity_verdict.OpportunityLevel.HIGH_PRIORITY.value:
        return (
            event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
            f"core_route_derived_from_opportunity_level:{level}",
        )
    if level in {
        event_opportunity_verdict.OpportunityLevel.WATCHLIST.value,
        event_opportunity_verdict.OpportunityLevel.VALIDATED_DIGEST.value,
    }:
        return (
            event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
            f"core_route_derived_from_opportunity_level:{level}",
        )
    return current or event_alpha_router.EventAlphaRoute.STORE_ONLY.value, None


def _canonical_core_state(
    item: event_core_opportunities.CoreOpportunity,
    final_level: str,
    live_policy: event_opportunity_verdict.LiveConfirmationVerdict,
) -> str:
    current = str(item.final_state_after_quality_gate or item.primary_row.get("state") or "").strip()
    if current == event_watchlist.EventWatchlistState.TRIGGERED_FADE.value:
        return current
    if not live_policy.capped_level:
        return current
    if final_level == event_opportunity_verdict.OpportunityLevel.LOCAL_ONLY.value:
        return event_watchlist.EventWatchlistState.RAW_EVIDENCE.value
    return event_watchlist.EventWatchlistState.RADAR.value


def _apply_integrated_candidate_truth(
    row: dict[str, Any],
    *,
    primary: Mapping[str, Any],
    all_rows: Iterable[Mapping[str, Any]],
    reaction: event_market_reaction.MarketReactionResult,
) -> dict[str, Any]:
    """Preserve already-classified integrated radar candidates at rest.

    Integrated radar candidates are the post-sidecar policy surface. The core
    store may add stricter quality/live-confirmation caps, but it must not
    recompute a generic market-reaction lane and silently upgrade capped rows.
    """
    integrated = _first_integrated_candidate(primary, all_rows)
    if integrated is None:
        return row
    row["source_row_type"] = "event_integrated_radar_candidate"
    row["integrated_candidate_id"] = integrated.get("candidate_id")
    row["integrated_candidate_family_id"] = integrated.get("candidate_family_id")
    row["generic_recomputed_opportunity_type"] = reaction.opportunity_type
    row["generic_recomputed_market_state_class"] = reaction.market_state
    for key in (
        "opportunity_type",
        "market_state_class",
        "market_state",
        "final_opportunity_level",
        "opportunity_level",
        "route",
        "tier",
        "latest_tier",
        "final_route_after_quality_gate",
        "final_tier_after_quality_gate",
        "state",
        "final_state_after_quality_gate",
        "score",
        "opportunity_score_final",
        "final_opportunity_score",
        "source_strength",
        "candidate_role",
        "asset_role",
        "source_requirements_met",
        "market_requirements_met",
        "fade_requirements_met",
        "risk_requirements_met",
        "canonical_asset_id",
        "asset_registry_symbol",
        "asset_registry_coin_id",
        "asset_registry_name",
        "asset_registry_liquidity_tier",
        "instrument_resolver_status",
        "instrument_resolver_confidence",
        "instrument_resolver_match_reason",
        "is_tradable_asset",
        "is_theme_or_sector",
        "is_quote_asset",
        "quote_asset_excluded",
        "base_asset_excluded",
        "diagnostics_reason",
        "integrated_market_confirmation_level",
        "integrated_market_confirmation_score",
        "integrated_market_reaction_confirmation",
        "integrated_market_context_source",
        "integrated_market_freshness_status",
        "crowding_class",
        "fade_readiness",
        "why_now",
        "source_origin",
        "source_origins",
        "source_pack",
        "source_packs",
        "source_url",
        "latest_source_url",
        "latest_source_title",
        "source_class",
        "supporting_evidence_quotes",
    ):
        value = integrated.get(key)
        if value not in (None, "", [], {}, ()):
            row[key] = value
    for src_key, dst_key in (
        ("what_confirms", "what_confirms"),
        ("what_invalidates", "what_invalidates"),
        ("why_not_alertable", "why_not_alertable"),
        ("reason_codes", "reason_codes"),
        ("warnings", "warnings"),
        ("crowding_exhaustion_evidence", "crowding_exhaustion_evidence"),
        ("what_confirms_fade_review", "what_confirms_fade_review"),
        ("what_invalidates_fade_review", "what_invalidates_fade_review"),
        ("derivatives_warning_codes", "derivatives_warning_codes"),
        ("instrument_resolver_warnings", "instrument_resolver_warnings"),
        ("asset_registry_venues", "asset_registry_venues"),
        ("asset_registry_spot_symbols", "asset_registry_spot_symbols"),
        ("asset_registry_perp_symbols", "asset_registry_perp_symbols"),
        ("asset_registry_coinalyze_symbols", "asset_registry_coinalyze_symbols"),
        ("asset_registry_bybit_symbols", "asset_registry_bybit_symbols"),
        ("asset_registry_binance_symbols", "asset_registry_binance_symbols"),
    ):
        value = integrated.get(src_key)
        if value not in (None, "", [], {}, ()):
            row[dst_key] = list(value) if isinstance(value, (list, tuple, set)) else [value]
    row["opportunity_type_why_now"] = integrated.get("why_now") or row.get("opportunity_type_why_now")
    row["opportunity_type_what_confirms"] = list(integrated.get("what_confirms") or row.get("opportunity_type_what_confirms") or ())
    row["opportunity_type_what_invalidates"] = list(integrated.get("what_invalidates") or row.get("opportunity_type_what_invalidates") or ())
    row["opportunity_type_why_not_alertable"] = list(integrated.get("why_not_alertable") or row.get("opportunity_type_why_not_alertable") or ())
    row["opportunity_type_reason_codes"] = list(integrated.get("reason_codes") or row.get("opportunity_type_reason_codes") or ())
    row["opportunity_type_warnings"] = list(integrated.get("warnings") or row.get("opportunity_type_warnings") or ())
    for key in (
        "market_state_snapshot",
        "latest_market_snapshot",
        "market_snapshot",
        "official_exchange_event",
        "scheduled_catalyst_event",
        "unlock_event",
        "derivatives_state_snapshot",
        "derivatives_snapshot",
    ):
        value = integrated.get(key)
        if isinstance(value, Mapping) and value:
            row[key] = dict(value)
    official = row.get("official_exchange_event") if isinstance(row.get("official_exchange_event"), Mapping) else {}
    if official:
        row["official_exchange_provider"] = _mapping_text(official, ("provider",)) or row.get("official_exchange_provider")
        row["official_exchange"] = _mapping_text(official, ("exchange",)) or row.get("official_exchange")
        row["official_exchange_event_type"] = _mapping_text(official, ("event_type",)) or row.get("official_exchange_event_type")
        row["official_exchange_title"] = _mapping_text(official, ("title", "event_name")) or row.get("official_exchange_title")
        row["official_exchange_url"] = _mapping_text(official, ("source_url", "url")) or row.get("official_exchange_url")
        row["official_exchange_published_at"] = _mapping_text(official, ("published_at",)) or row.get("official_exchange_published_at")
        row["official_exchange_effective_time"] = _mapping_text(official, ("effective_time",)) or row.get("official_exchange_effective_time")
        row["official_exchange_reason_codes"] = _mapping_list(official, ("reason_codes",)) or row.get("official_exchange_reason_codes")
        row["latest_source_url"] = row.get("latest_source_url") or row.get("official_exchange_url")
        row["source_url"] = row.get("source_url") or row.get("official_exchange_url")
        row["latest_source_title"] = row.get("latest_source_title") or row.get("official_exchange_title")
    if _opportunity_rank_value(str(row.get("opportunity_type") or "")) > _opportunity_rank_value(str(integrated.get("opportunity_type") or "")):
        row["integrated_core_silent_upgrade"] = True
    return row


def _first_integrated_candidate(
    primary: Mapping[str, Any],
    rows: Iterable[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    if (
        str(primary.get("row_type") or "") == "event_integrated_radar_candidate"
        or str(primary.get("source_row_type") or "") == "event_integrated_radar_candidate"
    ):
        return primary
    for row in rows:
        if (
            str(row.get("row_type") or "") == "event_integrated_radar_candidate"
            or str(row.get("source_row_type") or "") == "event_integrated_radar_candidate"
        ):
            return row
    return None


def _opportunity_rank_value(value: str) -> int:
    return {
        "DIAGNOSTIC": 0,
        "UNCONFIRMED_RESEARCH": 1,
        "RISK_ONLY": 2,
        "EARLY_LONG_RESEARCH": 3,
        "CONFIRMED_LONG_RESEARCH": 4,
        "FADE_SHORT_REVIEW": 5,
    }.get(str(value or "").upper(), -1)


def _core_route_quality_blocked(primary: Mapping[str, Any]) -> bool:
    route, block = event_alpha_router.quality_gate_route_for_row(primary, require_quality=True)
    if block:
        return True
    if route == event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH.value:
        return False
    if _truthy(primary.get("state_quality_capped")):
        return True
    return False


def _default_core_verdict_reason(level: str | None) -> str:
    level_text = str(level or "unknown").strip() or "unknown"
    return f"Core opportunity verdict reached {level_text}."


def _canonical_route_adjusted_verdict_reason(level: str | None) -> str:
    level_text = str(level or "unknown").strip() or "unknown"
    return (
        f"Core opportunity verdict reached {level_text}; "
        "final route derived from canonical opportunity level."
    )


def _accepted_evidence_source_summary(samples: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    for sample in samples:
        if not isinstance(sample, Mapping):
            continue
        provider = _text_or_none(sample.get("provider")) or _text_or_none(sample.get("provider_hint"))
        title = _text_or_none(sample.get("title"))
        source_url = _text_or_none(sample.get("source_url"))
        if provider or title or source_url:
            return {"provider": provider, "title": title, "source_url": source_url}
    return {}


def _first_mapping(rows: Iterable[Mapping[str, Any]], keys: tuple[str, ...]) -> dict[str, Any] | None:
    for row in rows:
        for key in keys:
            value = row.get(key)
            if isinstance(value, Mapping) and value:
                return dict(value)
    return None


def _mapping_text(row: Mapping[str, Any] | None, keys: tuple[str, ...]) -> str | None:
    if not isinstance(row, Mapping):
        return None
    for key in keys:
        value = _text_or_none(row.get(key))
        if value:
            return value
    return None


def _mapping_list(row: Mapping[str, Any] | None, keys: tuple[str, ...]) -> list[str]:
    if not isinstance(row, Mapping):
        return []
    out: list[str] = []
    for key in keys:
        raw = row.get(key)
        if isinstance(raw, str):
            if raw:
                out.append(raw)
        elif isinstance(raw, Mapping):
            out.extend(str(value) for value in raw.values() if str(value or ""))
        elif isinstance(raw, Iterable):
            out.extend(str(item) for item in raw if str(item or ""))
    return list(dict.fromkeys(out))


def _canonical_source_count(
    rows: Iterable[Mapping[str, Any]],
    acquisition: CoreEvidenceAcquisitionView,
) -> int:
    counts = [
        _float_or_none(_first_value(rows, ("source_count", "independent_source_count", "source_update_count"))),
        float(acquisition.accepted_evidence_count) if acquisition.accepted_evidence_count else None,
    ]
    count = max((int(value) for value in counts if value is not None), default=0)
    return count


def _first_real_text(rows: Iterable[Mapping[str, Any]], keys: tuple[str, ...]) -> str | None:
    text = _first_text(rows, keys)
    return None if _is_filler_text(text) else text


def _is_filler_text(value: Any) -> bool:
    return str(value or "").strip().casefold() in {
        "",
        "unknown",
        "missing",
        "none",
        "not available",
        "n/a",
        "insufficient_data",
        "impact_hypothesis",
        "watchlist",
        "alert_snapshot",
        "core_opportunity",
    }


def _canonical_impact_path_reason(primary_path: str | None, source_pack: str | None) -> str | None:
    path = str(primary_path or "").strip()
    pack = str(source_pack or "").strip()
    if path in {"proxy_attention", "proxy_exposure", "venue_value_capture"} or pack == "proxy_preipo_rwa_pack":
        return "venue_value_capture"
    if path in {"strategic_investment_or_valuation", "acquisition_or_stake"} or pack == "strategic_investment_pack":
        return "strategic_investment"
    if path == "exploit_security_event":
        return "exploit_security_event"
    if path == "listing_liquidity_event":
        return "listing_liquidity_event"
    if path == "market_dislocation_unknown":
        return "cause_unknown_market_dislocation"
    return path or None


def _canonical_impact_path_strength(
    level: str | None,
    primary_path: str | None,
    evidence_score: float | None,
    market_score: float | None,
) -> str | None:
    path = str(primary_path or "").strip()
    lvl = str(level or "").strip()
    if path in {"insufficient_data", "generic_cooccurrence_only", ""}:
        return "none" if path else None
    if lvl in {"high_priority", "watchlist"}:
        return "strong"
    if lvl == "validated_digest":
        return "medium"
    if (evidence_score or 0.0) >= 75 and (market_score or 0.0) >= 50:
        return "medium"
    return "weak"


def _canonical_market_summary(
    *,
    market_level: str | None,
    market_score: float | None,
    market_context: Mapping[str, Any],
) -> str | None:
    if not market_level and market_score is None and not market_context:
        return None
    parts = []
    if market_level:
        score_text = f" / {market_score:.0f}" if market_score is not None else ""
        parts.append(f"{market_level}{score_text}")
    freshness = market_context.get("market_context_freshness_status")
    source = market_context.get("market_context_source")
    age = market_context.get("market_context_age_hours")
    if freshness or source:
        age_text = ""
        if isinstance(age, (int, float)):
            age_text = f"; age={age:.1f}h" if age >= 1 else f"; age={age * 60:.0f}m"
        parts.append(f"freshness={freshness or 'not available'} source={source or 'not available'}{age_text}")
    return "; ".join(parts) if parts else None


def _market_level_from_score(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 75:
        return "strong"
    if score >= 50:
        return "moderate"
    if score > 0:
        return "weak"
    return "none"


def _best_market_snapshot(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    for row in rows:
        for source in (
            row.get("latest_market_snapshot"),
            row.get("market_snapshot"),
            row.get("market_context"),
        ):
            if isinstance(source, Mapping) and source:
                return dict(source)
        components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else row.get("score_components")
        if isinstance(components, Mapping):
            for source in (
                components.get("latest_market_snapshot"),
                components.get("market_snapshot"),
                components.get("market_context"),
            ):
                if isinstance(source, Mapping) and source:
                    return dict(source)
    return {}


def _canonical_manual_verification_items(
    item: event_core_opportunities.CoreOpportunity,
    source_pack: str | None,
    *,
    final_level: str | None = None,
    live_policy: event_opportunity_verdict.LiveConfirmationVerdict | None = None,
) -> list[str]:
    if live_policy and live_policy.required and not live_policy.confirmed:
        return list(live_policy.manual_verification_items)
    level = final_level or item.opportunity_level
    if level == "high_priority":
        return [
            "verify independent source corroboration",
            "verify exposure/value-capture claim remains valid",
            "verify liquidity and market confirmation are still fresh",
        ]
    if level == "watchlist":
        return ["verify second source, market confirmation, derivatives/liquidity, and catalyst timing"]
    if level == "validated_digest":
        return ["verify market reaction, official/second-source confirmation, and source-pack coverage"]
    if str(source_pack or "") == "market_anomaly_pack":
        return ["find causal catalyst evidence and confirm the move is not purely mechanical"]
    return ["validate catalyst, token identity, impact path, and market confirmation"]


def _canonical_upgrade_requirements(
    level: str | None,
    *,
    live_policy: event_opportunity_verdict.LiveConfirmationVerdict | None = None,
) -> list[str]:
    if live_policy and live_policy.required and not live_policy.confirmed:
        return list(live_policy.missing_requirements)
    if level == "high_priority":
        return ["sustained_fresh_market_confirmation", "stronger_source_corroboration", "derivatives_or_liquidity_support"]
    if level == "watchlist":
        return ["fresh_stronger_market_confirmation", "second_independent_source", "derivatives_or_liquidity_support"]
    if level == "validated_digest":
        return ["fresh_price_volume_reaction", "official_or_second_source_confirmation", "derivatives_or_supply_confirmation"]
    return ["validated_catalyst", "direct_token_mechanism", "identity_validation", "market_confirmation"]


def _canonical_downgrade_warnings(primary_path: str | None, level: str | None) -> list[str]:
    if level in {"high_priority", "watchlist", "validated_digest"}:
        if str(primary_path or "") in {"proxy_attention", "proxy_exposure", "venue_value_capture"}:
            return ["source_correction_or_denial", "exposure_value_capture_invalid", "market_confirmation_fades", "liquidity_drifts_lower", "catalyst_stale"]
        if str(primary_path or "") == "strategic_investment_or_valuation":
            return ["deal_denied_or_corrected", "token_value_capture_invalid", "market_reaction_absent", "market_context_stale"]
        return ["source_correction_or_denial", "impact_path_invalid", "market_confirmation_fades", "liquidity_drifts_lower"]
    return ["source_noise", "weak_cooccurrence_only", "market_move_without_catalyst"]


def _acquisition_candidate_rows(rows: Iterable[Mapping[str, Any] | object]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in rows:
        row = _row_dict(item)
        merged = _row_with_score_components(row)
        if _row_has_acquisition_metadata(merged):
            out.append(merged)
    return out


def _build_core_evidence_acquisition_view(
    core_opportunity_id: str,
    rows: Iterable[Mapping[str, Any]],
) -> CoreEvidenceAcquisitionView:
    clean_core = str(core_opportunity_id or "").strip()
    primary: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for raw in rows:
        row = _row_with_score_components(raw)
        if not _row_has_acquisition_metadata(row):
            continue
        if _is_diagnostic_acquisition_row(row, clean_core):
            diagnostics.append(dict(row))
        else:
            primary.append(dict(row))
    if not primary:
        return CoreEvidenceAcquisitionView(
            core_opportunity_id=clean_core,
            diagnostic_rows=tuple(_unique_rows(diagnostics)),
        )

    accepted_samples = _unique_evidence_samples(
        sample
        for row in primary
        for sample in _evidence_samples(row, ("evidence_acquisition_accepted_evidence", "accepted_evidence"))
    )
    rejected_samples = _unique_evidence_samples(
        sample
        for row in primary
        for sample in _evidence_samples(row, ("evidence_acquisition_rejected_samples", "rejected_evidence_samples", "rejected_evidence"))
    )
    accepted_count = max(
        len(accepted_samples),
        *(_int_or_zero(_nested_result_value(row, "accepted")) for row in primary),
        *(_int_or_zero(_first_value([row], ("evidence_acquisition_accepted_count", "accepted_evidence_count"))) for row in primary),
    )
    rejected_count = max(
        len(rejected_samples),
        *(_int_or_zero(_nested_result_value(row, "rejected")) for row in primary),
        *(_int_or_zero(_first_value([row], ("evidence_acquisition_rejected_count", "rejected_evidence_count"))) for row in primary),
    )
    accepted_reasons = _unique_strings(
        [
            *(
                str(reason)
                for row in primary
                for reason in _first_list([row], ("accepted_evidence_reason_codes",))
                if str(reason or "").strip()
            ),
            *(
                str(reason)
                for sample in accepted_samples
                for reason in _as_list_values(sample.get("reason_codes"))
                if str(reason or "").strip()
            ),
        ]
    )
    rejected_reasons = _unique_strings(
        [
            *(
                str(reason)
                for row in primary
                for reason in _first_list([row], ("rejected_evidence_reason_codes",))
                if str(reason or "").strip()
            ),
            *(
                str(reason)
                for sample in rejected_samples
                for reason in _as_list_values(sample.get("reason_codes"))
                if str(reason or "").strip()
            ),
        ]
    )
    accepted_provider_counts = _merge_count_maps(row.get("accepted_provider_counts") for row in primary)
    rejected_provider_counts = _merge_count_maps(row.get("rejected_provider_counts") for row in primary)
    accepted_reason_code_counts = _merge_count_maps(row.get("accepted_reason_code_counts") for row in primary)
    provider_failures = _unique_strings(
        failure
        for row in primary
        for failure in (
            *tuple(_first_list([row], ("evidence_acquisition_provider_failures", "provider_failures", "provider_coverage_gaps"))),
            *tuple(_query_provider_failures(row)),
        )
        if str(failure or "").strip()
    )
    status = _best_acquisition_status(primary, accepted_count=accepted_count, rejected_count=rejected_count)
    source_pack = _best_source_pack(primary, _first_text(primary, ("impact_path_type", "primary_impact_path")))
    return CoreEvidenceAcquisitionView(
        core_opportunity_id=clean_core,
        acquisition_attempted=_any_truthy(primary, ("evidence_acquisition_attempted", "source_acquisition_attempted")) or status != "not_executed",
        acquisition_status=status,
        source_pack=source_pack,
        accepted_evidence_count=accepted_count,
        rejected_evidence_count=rejected_count,
        accepted_reason_codes=tuple(accepted_reasons),
        rejected_reason_codes=tuple(rejected_reasons),
        accepted_provider_counts=accepted_provider_counts,
        rejected_provider_counts=rejected_provider_counts,
        accepted_reason_code_counts=accepted_reason_code_counts,
        accepted_evidence_samples=tuple(accepted_samples[:5]),
        rejected_evidence_samples=tuple(rejected_samples[:5]),
        provider_failures=tuple(provider_failures),
        evidence_quality_before=_first_float(primary, ("evidence_quality_before", "evidence_acquisition_score_before", "evidence_quality_score_before")),
        evidence_quality_after=_best_float(primary, ("evidence_quality_after", "evidence_acquisition_score_after", "evidence_quality_score_after", "post_refresh_evidence_quality_score")),
        opportunity_score_before=_first_float(primary, ("opportunity_score_before", "opportunity_score_before_acquisition", "initial_opportunity_score")),
        opportunity_score_after=_best_float(primary, ("opportunity_score_after", "opportunity_score_after_acquisition", "post_refresh_opportunity_score", "final_opportunity_score", "opportunity_score_final")),
        opportunity_level_before=_first_text(primary, ("opportunity_level_before", "opportunity_level_before_acquisition", "initial_opportunity_level")),
        opportunity_level_after=_first_text(primary, ("opportunity_level_after", "opportunity_level_after_acquisition", "post_refresh_opportunity_level", "final_opportunity_level", "opportunity_level")),
        final_upgrade_status=_first_text(primary, ("final_upgrade_status", "acquisition_upgrade_status")),
        no_upgrade_reason=_first_text(primary, ("no_upgrade_reason",)),
        diagnostic_rows=tuple(_unique_rows(diagnostics)),
    )


def _row_with_score_components(row: Mapping[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for key in ("score_components", "latest_score_components"):
        value = row.get(key)
        if isinstance(value, Mapping):
            merged.update(dict(value))
    merged.update(dict(row))
    return merged


def _merge_count_maps(values: Iterable[object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        if not isinstance(value, Mapping):
            continue
        for key, raw in value.items():
            text = str(key or "").strip()
            if not text:
                continue
            try:
                number = int(raw or 0)
            except (TypeError, ValueError):
                continue
            counts[text] = counts.get(text, 0) + max(0, number)
    return counts


def _row_has_acquisition_metadata(row: Mapping[str, Any]) -> bool:
    if str(row.get("row_type") or "") == "event_evidence_acquisition":
        return True
    return any(
        key in row and row.get(key) not in (None, "", [], {}, ())
        for key in (
            "evidence_acquisition_attempted",
            "source_acquisition_attempted",
            "evidence_acquisition_status",
            "acquisition_status",
            "source_acquisition_status",
            "evidence_acquisition_results",
            "evidence_acquisition_accepted_evidence",
            "accepted_evidence",
            "evidence_acquisition_rejected_samples",
            "rejected_evidence_samples",
            "provider_failures",
            "evidence_acquisition_provider_failures",
        )
    )


def _is_diagnostic_acquisition_row(row: Mapping[str, Any], core_opportunity_id: str) -> bool:
    status = str(row.get("core_opportunity_id_status") or "").strip()
    if status == "diagnostic_support":
        return True
    diagnostic_target = str(row.get("diagnostic_support_for_core_opportunity_id") or "").strip()
    if diagnostic_target and diagnostic_target == core_opportunity_id:
        return True
    return bool(row.get("is_diagnostic_snapshot"))


def _acquisition_row_matches_core(row: Mapping[str, Any], identifiers: set[str]) -> bool:
    explicit = str(row.get("core_opportunity_id") or "").strip()
    if explicit:
        return explicit in identifiers
    return _row_matches_identifiers(row, identifiers)


def _evidence_samples(row: Mapping[str, Any], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for key in keys:
        value = row.get(key)
        if value in (None, "", [], {}, ()):
            nested = row.get("evidence_acquisition_results")
            value = nested.get(key) if isinstance(nested, Mapping) else value
        for sample in _as_sequence(value):
            if isinstance(sample, Mapping):
                samples.append(dict(sample))
            elif str(sample or "").strip():
                samples.append({"title": str(sample).strip()})
    return samples


def _unique_evidence_samples(samples: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for sample in samples:
        normalized = dict(sample)
        key = "|".join(str(normalized.get(field) or "").strip() for field in ("source_url", "title", "quote", "evidence_quote"))
        if not key.strip("|"):
            key = json.dumps(_json_ready(normalized), sort_keys=True, separators=(",", ":"))
        if key in seen:
            continue
        seen.add(key)
        out.append(normalized)
    return out


def _query_provider_failures(row: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    for query in _as_sequence(row.get("queries")):
        if isinstance(query, Mapping):
            failures.extend(str(item) for item in _as_sequence(query.get("provider_failures")) if str(item or "").strip())
    return failures


def _nested_result_value(row: Mapping[str, Any], key: str) -> Any:
    nested = row.get("evidence_acquisition_results")
    if isinstance(nested, Mapping):
        return nested.get(key)
    return None


def _best_acquisition_status(
    rows: Iterable[Mapping[str, Any]],
    *,
    accepted_count: int,
    rejected_count: int,
) -> str:
    if accepted_count > 0:
        return "accepted_evidence_found"
    if rejected_count > 0:
        return "rejected_results_only"
    statuses = [
        str(_first_text([row], ("evidence_acquisition_status", "acquisition_status", "source_acquisition_status", "status")) or "").strip()
        for row in rows
    ]
    statuses = [status for status in statuses if status]
    if not statuses:
        return "not_executed"
    rank = {
        "accepted_evidence_found": 7,
        "executed": 6,
        "rejected_results_only": 5,
        "no_results": 4,
        "provider_backoff": 3,
        "provider_unavailable": 3,
        "failed_soft": 2,
        "skipped_budget": 1,
        "skipped_config": 1,
        "planned": 0,
        "not_executed": 0,
    }
    return sorted(statuses, key=lambda status: rank.get(status, 0), reverse=True)[0]


def _unique_strings(values: Iterable[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _as_sequence(value: Any) -> list[Any]:
    if value in (None, "", [], {}, ()):
        return []
    if isinstance(value, Mapping):
        return [dict(value)]
    if isinstance(value, str):
        return [item.strip() for item in value.split(";") if item.strip()]
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return list(value)
    return [value]


def _int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _load_alert_rows(path: str | Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    try:
        from . import event_alpha_alert_store

        return [dict(row) for row in event_alpha_alert_store.load_alert_snapshots(path).rows]
    except Exception:  # noqa: BLE001 - partial artifact views should fail soft.
        return []


def _load_acquisition_rows(path: str | Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    try:
        from . import event_evidence_acquisition

        return [dict(row) for row in event_evidence_acquisition.load_acquisition_results(path)]
    except Exception:  # noqa: BLE001 - partial artifact views should fail soft.
        return []


def _load_incident_rows(path: str | Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    try:
        from . import event_incident_store

        return [
            dict(row)
            for row in event_incident_store.load_incidents(
                path,
                latest_run=False,
                include_legacy=True,
                include_diagnostic=True,
                include_raw=True,
                include_external_context=True,
            ).rows
        ]
    except Exception:  # noqa: BLE001 - partial artifact views should fail soft.
        return []


def _load_feedback_rows(path: str | Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    try:
        from . import event_feedback

        return [asdict(record) for record in event_feedback.load_feedback(path).records]
    except Exception:  # noqa: BLE001 - partial artifact views should fail soft.
        return []


def _markdown_card_paths(path: str | Path | None) -> tuple[Path, ...]:
    if path is None:
        return ()
    root = Path(path).expanduser()
    if not root.exists():
        return ()
    if root.is_file():
        return (root,) if root.suffix.lower() == ".md" else ()
    try:
        return tuple(path for path in root.glob("*.md") if path.name != "index.md")
    except OSError:
        return ()


def _card_path_by_core_id(paths: Iterable[str | Path]) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        from . import event_research_cards
    except Exception:  # noqa: BLE001 - optional presentation helper.
        return out
    for value in paths:
        path = Path(value)
        core_id = event_research_cards.card_core_opportunity_id(path)
        if core_id:
            out.setdefault(core_id, str(path))
    return out


def _find_core_opportunity(
    target: str,
    opportunities: Iterable[event_core_opportunities.CoreOpportunity],
) -> event_core_opportunities.CoreOpportunity | None:
    clean = target[3:] if target.startswith("ea:") else target
    clean_l = clean.casefold()
    for item in opportunities:
        identifiers = {
            item.core_opportunity_id,
            item.symbol,
            item.coin_id,
            item.incident_id or "",
            item.canonical_incident_name or "",
            str(item.primary_row.get("alert_id") or ""),
            str(item.primary_row.get("card_id") or ""),
            str(item.primary_row.get("snapshot_id") or ""),
            str(item.primary_row.get("key") or ""),
            str(item.primary_row.get("alert_key") or ""),
            str(item.primary_row.get("hypothesis_id") or ""),
        }
        identifiers.update(str(value) for value in item.supporting_hypothesis_ids)
        identifiers.update(_as_list_values(item.primary_row.get("supporting_row_ids")))
        identifiers.update(_as_list_values(item.primary_row.get("diagnostic_row_ids")))
        for row in (*item.supporting_rows, *item.diagnostic_rows):
            identifiers.update(_row_identifier_values(row))
        if clean in identifiers or clean_l in {value.casefold() for value in identifiers if value}:
            return item
    return None


def _target_from_acquisition_rows(target: str, rows: Iterable[Mapping[str, Any]]) -> str | None:
    clean = str(target or "").strip()
    clean_l = clean.casefold()
    for row in rows:
        candidates = {
            str(row.get("original_core_opportunity_id") or ""),
            str(row.get("requested_core_opportunity_id") or ""),
            str(row.get("support_row_id") or ""),
            str(row.get("hypothesis_id") or ""),
        }
        if clean in candidates or clean_l in {item.casefold() for item in candidates if item}:
            resolved = str(row.get("core_opportunity_id") or "").strip()
            if resolved:
                return resolved
    return None


def _canonical_store_row(
    core_id: str,
    core_rows: Iterable[Mapping[str, Any]],
    opportunity: event_core_opportunities.CoreOpportunity,
) -> dict[str, Any]:
    for row in core_rows:
        if str(row.get("core_opportunity_id") or "") == core_id:
            return dict(row)
    row = _row_from_core_opportunity(
        opportunity,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
    return dict(row)


def _core_view_identifiers(
    canonical_row: Mapping[str, Any],
    opportunity: event_core_opportunities.CoreOpportunity,
) -> set[str]:
    identifiers = set(_row_identifier_values(canonical_row))
    identifiers.add(opportunity.core_opportunity_id)
    identifiers.add(opportunity.symbol)
    identifiers.add(opportunity.coin_id)
    identifiers.add(opportunity.incident_id or "")
    identifiers.add(opportunity.canonical_incident_name or "")
    identifiers.update(str(value) for value in opportunity.supporting_hypothesis_ids)
    identifiers.update(_as_list_values(canonical_row.get("supporting_row_ids")))
    identifiers.update(_as_list_values(canonical_row.get("diagnostic_row_ids")))
    for row in (*opportunity.supporting_rows, *opportunity.diagnostic_rows):
        identifiers.update(_row_identifier_values(row))
    return {str(value) for value in identifiers if str(value or "").strip()}


def _row_identifier_values(row: Mapping[str, Any]) -> set[str]:
    values = {
        row.get("core_opportunity_id"),
        row.get("diagnostic_support_for_core_opportunity_id"),
        row.get("original_core_opportunity_id"),
        row.get("feedback_target"),
        row.get("target"),
        row.get("alert_id"),
        row.get("alert_key"),
        row.get("card_id"),
        row.get("snapshot_id"),
        row.get("watchlist_key"),
        row.get("key"),
        row.get("event_id"),
        row.get("hypothesis_id"),
        row.get("incident_id"),
        row.get("symbol"),
        row.get("validated_symbol"),
        row.get("coin_id"),
        row.get("validated_coin_id"),
        row.get("asset_symbol"),
        row.get("asset_coin_id"),
    }
    for key in ("supporting_hypothesis_ids", "supporting_row_ids", "diagnostic_row_ids", "source_event_ids", "event_ids"):
        values.update(_as_list_values(row.get(key)))
    return {str(value) for value in values if str(value or "").strip()}


def _row_matches_identifiers(row: Mapping[str, Any], identifiers: set[str]) -> bool:
    direct_values = {
        row.get("core_opportunity_id"),
        row.get("diagnostic_support_for_core_opportunity_id"),
        row.get("original_core_opportunity_id"),
        row.get("feedback_target"),
        row.get("target"),
        row.get("alert_id"),
        row.get("alert_key"),
        row.get("card_id"),
        row.get("snapshot_id"),
        row.get("watchlist_key"),
        row.get("key"),
        row.get("event_id"),
        row.get("hypothesis_id"),
    }
    for key in ("supporting_hypothesis_ids", "supporting_row_ids", "diagnostic_row_ids", "source_event_ids", "event_ids"):
        direct_values.update(_as_list_values(row.get(key)))
    if {str(value) for value in direct_values if str(value or "").strip()}.intersection(identifiers):
        return True
    incident = str(row.get("incident_id") or "").strip()
    asset_values = {
        str(value)
        for value in (
            row.get("symbol"),
            row.get("validated_symbol"),
            row.get("coin_id"),
            row.get("validated_coin_id"),
            row.get("asset_symbol"),
            row.get("asset_coin_id"),
        )
        if str(value or "").strip()
    }
    return bool(incident and incident in identifiers and asset_values.intersection(identifiers))


def _row_is_diagnostic_support(row: Mapping[str, Any], core_id: str, identifiers: set[str]) -> bool:
    if str(row.get("diagnostic_support_for_core_opportunity_id") or "") == core_id:
        return True
    if not _row_matches_identifiers(row, identifiers):
        return False
    return event_core_opportunities.row_is_diagnostic(row)


def _incident_matches_identifiers(row: Mapping[str, Any], identifiers: set[str]) -> bool:
    direct_values = {
        row.get("incident_id"),
        row.get("canonical_name"),
        row.get("canonical_incident_name"),
        row.get("primary_subject"),
        row.get("main_frame_subject"),
    }
    if {str(value) for value in direct_values if str(value or "").strip()}.intersection(identifiers):
        return True
    linked_assets = row.get("linked_assets")
    if isinstance(linked_assets, Iterable) and not isinstance(linked_assets, (str, bytes, Mapping)):
        for item in linked_assets:
            if not isinstance(item, Mapping):
                continue
            values = {
                item.get("symbol"),
                item.get("coin_id"),
                item.get("asset_symbol"),
                item.get("asset_coin_id"),
            }
            if {str(value) for value in values if str(value or "").strip()}.intersection(identifiers):
                return True
    return False


def _best_incident_row(
    rows: Iterable[Mapping[str, Any]],
    canonical_row: Mapping[str, Any],
    opportunity: event_core_opportunities.CoreOpportunity,
) -> dict[str, Any] | None:
    candidates = [dict(row) for row in rows if isinstance(row, Mapping)]
    if not candidates:
        return None
    incident_id = str(canonical_row.get("incident_id") or opportunity.incident_id or "").strip()
    if incident_id:
        exact = [row for row in candidates if str(row.get("incident_id") or "").strip() == incident_id]
        if exact:
            candidates = exact
    status_rank = {
        "active_incident": 5,
        "linked_incident": 4,
        "canonical_incident": 3,
        "incident_candidate": 2,
    }
    return sorted(
        candidates,
        key=lambda row: (
            status_rank.get(str(row.get("incident_relevance_status") or "").strip(), 0),
            float(row.get("incident_relevance_score") or 0.0),
            str(row.get("last_updated_at") or row.get("observed_at") or ""),
        ),
        reverse=True,
    )[0]


def _is_market_refresh_row(row: Mapping[str, Any]) -> bool:
    return _any_truthy(
        [row],
        (
            "market_refresh_attempted",
            "targeted_market_refresh_attempted",
            "market_refresh_success",
            "targeted_market_refresh_success",
        ),
    ) or any(
        key in row
        for key in (
            "market_context_after",
            "market_confirmation_after",
            "market_context_observed_at",
            "market_context_freshness_status",
        )
    )


def _research_card_path(
    canonical_row: Mapping[str, Any],
    core_id: str,
    paths: Iterable[Path],
) -> str | None:
    existing = _first_text([canonical_row], ("research_card_path", "card_path"))
    if existing:
        return existing
    try:
        from . import event_research_cards
    except Exception:  # noqa: BLE001 - optional presentation helper.
        return None
    for path in paths:
        if event_research_cards.card_core_opportunity_id(path) == core_id:
            return str(path)
    return None


def _feedback_matches(row: Mapping[str, Any], identifiers: set[str], feedback_target: str | None) -> bool:
    explicit_target = str(row.get("target") or "").strip()
    if explicit_target and (explicit_target == feedback_target or explicit_target in identifiers):
        return True
    return _row_matches_identifiers(row, identifiers)


def _unique_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        normalized = dict(row)
        row_type = str(normalized.get("row_type") or "row").strip()
        if row_type == "event_alpha_alert_snapshot":
            id_value = _first_text(
                [normalized],
                (
                    "alert_id",
                    "snapshot_id",
                    "card_id",
                    "alert_key",
                    "core_opportunity_id",
                ),
            )
            snapshot_class = str(normalized.get("snapshot_class") or normalized.get("core_resolution_status") or "").strip()
            if id_value and snapshot_class:
                id_value = f"{id_value}:{snapshot_class}"
        else:
            id_value = _first_text(
                [normalized],
                (
                    "acquisition_id",
                    "core_opportunity_id",
                    "diagnostic_support_for_core_opportunity_id",
                    "original_core_opportunity_id",
                    "alert_id",
                    "snapshot_id",
                    "hypothesis_id",
                    "key",
                    "event_id",
                ),
            )
        dedupe_key = (
            f"{row_type}:{id_value}"
            if id_value
            else json.dumps(_json_ready(normalized), sort_keys=True, separators=(",", ":"))
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        out.append(normalized)
    return out


def _row_dict(value: Mapping[str, Any] | object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if is_dataclass(value):
        return asdict(value)
    return dict(getattr(value, "__dict__", {}) or {})


def _as_list_values(value: Any) -> set[str]:
    if value in (None, "", [], {}, ()):
        return set()
    if isinstance(value, str):
        return {item.strip() for item in value.replace("|", ";").split(";") if item.strip()}
    if isinstance(value, Mapping):
        return {str(item) for item in value.values() if str(item or "").strip()}
    if isinstance(value, Iterable):
        return {str(item) for item in value if str(item or "").strip()}
    return {str(value)}


def _row_ids(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    ids: list[str] = []
    for row in rows:
        value = _first_text([row], ("row_id", "hypothesis_id", "alert_id", "watchlist_key", "key", "event_id"))
        if value:
            ids.append(value)
    return list(dict.fromkeys(ids))


def _first_text(rows: Iterable[Mapping[str, Any]], keys: tuple[str, ...]) -> str | None:
    for row in rows:
        components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else row.get("score_components")
        for key in keys:
            value = row.get(key)
            if value in (None, "", [], {}, ()):
                value = components.get(key) if isinstance(components, Mapping) else None
            text = str(value or "").strip()
            if text:
                return text
    return None


def _first_float(rows: Iterable[Mapping[str, Any]], keys: tuple[str, ...]) -> float | None:
    for row in rows:
        components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else row.get("score_components")
        for key in keys:
            value = row.get(key)
            if value in (None, "", [], {}, ()):
                value = components.get(key) if isinstance(components, Mapping) else None
            parsed = _float_or_none(value)
            if parsed is not None:
                return parsed
    return None


def _first_value(rows: Iterable[Mapping[str, Any]], keys: tuple[str, ...]) -> Any:
    for row in rows:
        components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else row.get("score_components")
        for key in keys:
            value = row.get(key)
            if value in (None, "", [], {}, ()):
                value = components.get(key) if isinstance(components, Mapping) else None
            if value not in (None, "", [], {}, ()):
                return value
    return None


def _first_list(rows: Iterable[Mapping[str, Any]], keys: tuple[str, ...]) -> list[Any]:
    value = _first_value(rows, keys)
    if value in (None, "", [], {}, ()):
        return []
    if isinstance(value, Mapping):
        return [dict(value)]
    if isinstance(value, str):
        return [item.strip() for item in value.split(";") if item.strip()]
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return list(value)
    return [value]


def _best_float(rows: Iterable[Mapping[str, Any]], keys: tuple[str, ...]) -> float | None:
    values = [
        parsed
        for row in rows
        for parsed in (_first_float([row], keys),)
        if parsed is not None
    ]
    return max(values) if values else None


def _best_market_context(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for row in rows:
        components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else row.get("score_components")
        for source in (row, components if isinstance(components, Mapping) else None):
            if not isinstance(source, Mapping):
                continue
            candidates.append(_market_context_from_flat(source))
            for key in ("market_context_after", "market_context", "market_data_context"):
                nested = source.get(key)
                if isinstance(nested, Mapping):
                    candidates.append(_market_context_from_nested(nested))
    candidates = [item for item in candidates if _market_context_has_value(item)]
    if not candidates:
        return {}
    candidates.sort(key=_market_context_rank, reverse=True)
    return candidates[0]


def _best_confirmation_context(
    rows: Iterable[Mapping[str, Any]],
    *,
    score_keys: tuple[str, ...],
    level_keys: tuple[str, ...],
    reasons_keys: tuple[str, ...],
    freshness_keys: tuple[str, ...],
) -> dict[str, Any]:
    score = _best_float(rows, score_keys)
    return {
        "score": score,
        "level": _first_text(rows, level_keys) or (_market_level_from_score(score) if score is not None else None),
        "reasons": _first_list(rows, reasons_keys),
        "freshness_status": _first_text(rows, freshness_keys),
    }


def _market_context_from_flat(source: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "market_context_freshness_status": _text_or_none(source.get("market_context_freshness_status")),
        "market_context_source": _text_or_none(source.get("market_context_source")),
        "market_context_observed_at": _text_or_none(source.get("market_context_observed_at")),
        "market_context_age_hours": _float_or_none(source.get("market_context_age_hours")),
        "market_context_freshness_cap_applied": _truthy(source.get("market_context_freshness_cap_applied")),
        "market_context_data_quality": _text_or_none(source.get("market_context_data_quality")),
    }


def _market_context_from_nested(source: Mapping[str, Any]) -> dict[str, Any]:
    snapshot = source.get("market_snapshot") if isinstance(source.get("market_snapshot"), Mapping) else {}
    data_quality = _text_or_none(source.get("data_quality")) or _text_or_none(snapshot.get("data_quality"))
    observed_at = (
        _text_or_none(source.get("timestamp"))
        or _text_or_none(source.get("observed_at"))
        or _text_or_none(snapshot.get("timestamp"))
        or _text_or_none(snapshot.get("observed_at"))
    )
    age_seconds = _float_or_none(source.get("age_seconds"))
    age_hours = _float_or_none(source.get("age_hours"))
    if age_hours is None and age_seconds is not None:
        age_hours = age_seconds / 3600.0
    source_name = _text_or_none(source.get("source")) or _text_or_none(snapshot.get("source"))
    freshness = _text_or_none(source.get("freshness_status")) or _text_or_none(source.get("market_context_freshness_status"))
    if not freshness and data_quality in {"fresh", "fixture_allowed_stale", "stale", "missing", "unknown"}:
        freshness = data_quality
    if not freshness and observed_at:
        freshness = "fresh"
    cap_value = source.get("freshness_cap_applied", source.get("market_context_freshness_cap_applied"))
    return {
        "market_context_freshness_status": freshness,
        "market_context_source": source_name,
        "market_context_observed_at": observed_at,
        "market_context_age_hours": age_hours,
        "market_context_freshness_cap_applied": _truthy(cap_value),
        "market_context_data_quality": data_quality,
    }


def _market_context_has_value(item: Mapping[str, Any]) -> bool:
    return any(value not in (None, "", [], {}, ()) for value in item.values())


def _market_context_rank(item: Mapping[str, Any]) -> tuple[int, int, int, int, int, int]:
    status = str(item.get("market_context_freshness_status") or "").casefold()
    source = str(item.get("market_context_source") or "").casefold()
    data_quality = str(item.get("market_context_data_quality") or "").casefold()
    observed_at = str(item.get("market_context_observed_at") or "").strip()
    age = item.get("market_context_age_hours")
    cap = bool(item.get("market_context_freshness_cap_applied"))
    return (
        3 if status == "fresh" else 2 if status == "fixture_allowed_stale" else 1 if status == "stale" else 0,
        1 if source not in {"", "missing", "unknown"} else 0,
        1 if data_quality not in {"", "missing", "unknown"} else 0,
        1 if observed_at else 0,
        1 if age not in (None, "", "unknown") else 0,
        0 if cap else 1,
    )


def _text_or_none(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _best_source_pack(rows: Iterable[Mapping[str, Any]], impact_path: str | None) -> str | None:
    prioritized: list[str] = []
    fallback: list[str] = []
    for row in rows:
        components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else row.get("score_components")
        values = (
            row.get("evidence_acquisition_source_pack"),
            row.get("source_pack"),
            components.get("evidence_acquisition_source_pack") if isinstance(components, Mapping) else None,
            components.get("source_pack") if isinstance(components, Mapping) else None,
        )
        status = str(
            row.get("evidence_acquisition_status")
            or (components.get("evidence_acquisition_status") if isinstance(components, Mapping) else "")
            or ""
        )
        for value in values:
            text = str(value or "").strip()
            if not text:
                continue
            if status == "accepted_evidence_found" or text != "market_anomaly_pack":
                prioritized.append(text)
            else:
                fallback.append(text)
    if prioritized:
        return prioritized[0]
    if fallback:
        return fallback[0]
    try:
        from . import event_source_packs
        impact = str(impact_path or "")
        pack_impact = "venue_value_capture" if impact.casefold() in {"proxy_attention", "proxy_exposure"} else impact
        return event_source_packs.source_pack_for_playbook(
            "proxy_attention" if pack_impact.casefold() in {"venue_value_capture", "proxy_exposure"} else impact,
            impact_path_type=pack_impact,
        ).name
    except Exception:  # noqa: BLE001 - optional source-pack helper.
        return None


def _any_truthy(rows: Iterable[Mapping[str, Any]], keys: tuple[str, ...]) -> bool:
    for row in rows:
        components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else row.get("score_components")
        for key in keys:
            value = row.get(key)
            if value in (None, "", [], {}, ()):
                value = components.get(key) if isinstance(components, Mapping) else None
            if _truthy(value):
                return True
    return False


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "y"}
    return bool(value)


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _latest_run_id(rows: Iterable[Mapping[str, Any]]) -> str | None:
    for row in rows:
        value = str(row.get("run_id") or "").strip()
        if value:
            return value
    return None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                text = line.strip()
                if not text:
                    continue
                try:
                    raw = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if isinstance(raw, Mapping):
                    rows.append(dict(raw))
    except OSError:
        return []
    return rows


def _json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return _as_utc(value).isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item) for item in value]
    return value
