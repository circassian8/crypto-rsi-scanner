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

from . import event_core_opportunities


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
            if not card_path or row.get("card_path") == card_path:
                continue
            row["card_path"] = card_path
            row["research_card_path"] = card_path
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
    feedback_artifact_path = feedback_path or getattr(context, "feedback_path", None)
    cards_dir = research_cards_dir or getattr(context, "research_cards_dir", None)

    core_rows = load_core_opportunities(
        core_path,
        latest_run=latest_run,
        include_legacy=include_legacy,
    ).rows if core_path else []
    alert_rows = _load_alert_rows(alert_path)
    acquisition_rows = _load_acquisition_rows(acquisition_path)
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
        except Exception:  # noqa: BLE001 - artifact joins should remain best-effort.
            pass
    card_paths = _markdown_card_paths(cards_dir)
    return canonical_core_opportunity_view_from_rows(
        clean,
        core_rows=core_rows,
        supporting_rows=alert_rows,
        evidence_acquisition_rows=acquisition_rows,
        alert_rows=alert_rows,
        feedback_rows=feedback_rows,
        card_paths=card_paths,
        profile=resolved_profile,
        artifact_namespace=resolved_namespace,
    )


def canonical_core_opportunity_view_from_rows(
    core_opportunity_id: str,
    *,
    core_rows: Iterable[Mapping[str, Any] | object] = (),
    supporting_rows: Iterable[Mapping[str, Any] | object] = (),
    evidence_acquisition_rows: Iterable[Mapping[str, Any] | object] = (),
    alert_rows: Iterable[Mapping[str, Any] | object] = (),
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
    market_refresh_rows = tuple(_unique_rows(
        row for row in [canonical_row, *linked_support, *linked_acquisition, *linked_alerts]
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
        feedback_target=feedback_target,
        feedback_status=feedback_status,
        feedback_rows=linked_feedback,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def core_opportunities_from_rows(rows: Iterable[Mapping[str, Any]]) -> tuple[event_core_opportunities.CoreOpportunity, ...]:
    """Convert stored canonical rows back into CoreOpportunity objects."""
    return event_core_opportunities.aggregate_core_opportunities(rows)


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
    initial_level = _first_text(all_rows, ("initial_opportunity_level", "opportunity_level_before", "opportunity_level_pre_refresh")) or item.opportunity_level
    initial_score = _first_float(all_rows, ("initial_opportunity_score", "opportunity_score_before", "opportunity_score_pre_refresh"))
    post_level = _first_text(all_rows, ("post_refresh_opportunity_level", "refreshed_opportunity_level", "opportunity_level_after_market_refresh")) or item.opportunity_level
    post_score = _first_float(all_rows, ("post_refresh_opportunity_score", "refreshed_opportunity_score", "opportunity_score_after_market_refresh"))
    market_context = _best_market_context(all_rows)
    support_ids = _row_ids(support)
    diagnostic_ids = _row_ids(diagnostics)
    return {
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
        "state": item.final_state_after_quality_gate,
        "tier": item.final_route_after_quality_gate,
        "latest_tier": item.final_route_after_quality_gate,
        "route": item.final_route_after_quality_gate,
        "primary_hypothesis_id": _first_text([primary], ("hypothesis_id", "primary_hypothesis_id")),
        "supporting_hypothesis_ids": list(item.supporting_hypothesis_ids),
        "supporting_categories": list(item.supporting_categories),
        "supporting_impact_paths": list(item.supporting_impact_paths),
        "supporting_evidence_quotes": list(item.supporting_evidence_quotes),
        "evidence_quotes": list(item.supporting_evidence_quotes),
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
        "market_context_freshness_status": market_context.get("market_context_freshness_status"),
        "market_context_source": market_context.get("market_context_source"),
        "market_context_observed_at": market_context.get("market_context_observed_at"),
        "market_context_age_hours": market_context.get("market_context_age_hours"),
        "market_context_freshness_cap_applied": bool(market_context.get("market_context_freshness_cap_applied")),
        "market_context_data_quality": market_context.get("market_context_data_quality"),
        "market_confirmation_score": market_after,
        "market_confirmation_level": market_level,
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
        "evidence_acquisition_attempted": _any_truthy(all_rows, ("evidence_acquisition_attempted", "source_acquisition_attempted")),
        "evidence_acquisition_status": _first_text(all_rows, ("evidence_acquisition_status", "acquisition_status", "source_acquisition_status")),
        "evidence_acquisition_source_pack": source_pack,
        "source_pack": source_pack,
        "source_class": source_class,
        "evidence_specificity": evidence_specificity,
        "evidence_quality_score": evidence_score,
        "evidence_quality_before": evidence_before,
        "evidence_quality_after": evidence_after,
        "post_refresh_opportunity_level": post_level,
        "post_refresh_opportunity_score": post_score if post_score is not None else item.opportunity_score_final,
        "final_opportunity_level": item.opportunity_level,
        "final_opportunity_score": item.opportunity_score_final,
        "opportunity_level": item.opportunity_level,
        "opportunity_score_final": item.opportunity_score_final,
        "final_state_after_quality_gate": item.final_state_after_quality_gate,
        "final_route_after_quality_gate": item.final_route_after_quality_gate,
        "final_tier_after_quality_gate": item.final_route_after_quality_gate,
        "final_verdict_source": _first_text(all_rows, ("final_verdict_source", "opportunity_verdict_source", "verdict_source")) or "core_opportunity_merge",
        "final_verdict_reason": _first_text(all_rows, ("final_verdict_reason", "quality_gate_block_reason", "route_reason", "opportunity_verdict_reason")),
        "why_opportunity_visible": item.why_opportunity_visible,
        "why_other_rows_hidden": item.why_other_rows_hidden,
        "card_path": str(card_path) if card_path else None,
        "research_card_path": str(card_path) if card_path else None,
        "feedback_target": item.core_opportunity_id,
        "feedback_target_type": "core_opportunity_id",
        "generated_at": generated_at,
    }


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
        id_value = _first_text(
            [normalized],
            (
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
        row_type = str(normalized.get("row_type") or "row").strip()
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
