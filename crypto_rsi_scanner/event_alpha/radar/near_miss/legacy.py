"""Near-miss detection and targeted refresh for Event Alpha research rows.

This module is artifact-only. It can identify candidates close to promotion,
refresh already-validated market/derivatives/supply/evidence context, and
recompute the existing opportunity verdict. It cannot create alerts, paper
trades, normal RSI rows, execution, or event-fade triggers.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Mapping

from .... import (
    event_alpha_router,
    event_alpha_quality_fields,
    event_core_opportunities,
    event_llm_evidence_planner,
    event_market_confirmation,
    event_opportunity_verdict,
    event_source_packs,
    event_source_registry,
)


@dataclass(frozen=True)
class EventNearMissConfig:
    enabled: bool = True
    near_threshold_points: float = 10.0
    digest_threshold: float = 65.0
    watchlist_threshold: float = 78.0
    max_candidates: int = 20
    market_refresh_enabled: bool = False
    max_market_refresh_assets: int = 20
    market_refresh_timeout_seconds: float = 5.0
    stale_after_seconds: float = 6 * 3600
    source_refresh_enabled: bool = False
    max_source_queries: int = 2


@dataclass(frozen=True)
class EventTargetedMarketRefreshQueueItem:
    refresh_id: str
    symbol: str
    coin_id: str
    core_opportunity_id: str | None
    hypothesis_id: str | None
    incident_id: str | None
    reason: str
    current_market_source: str | None
    current_market_age_seconds: float | None
    priority_score: float


@dataclass(frozen=True)
class EventNearMissCandidate:
    near_miss_id: str
    refresh_id: str | None
    symbol: str
    coin_id: str
    core_opportunity_id: str | None
    hypothesis_id: str | None
    incident_id: str | None
    opportunity_level_before: str
    opportunity_score_before: float
    opportunity_level_after: str | None = None
    opportunity_score_after: float | None = None
    final_route_before: str | None = None
    final_route_after: str | None = None
    missing_evidence: tuple[str, ...] = ()
    recommended_refresh_actions: tuple[str, ...] = ()
    priority_score: float = 0.0
    market_refresh_attempted: bool = False
    market_refresh_success: bool = False
    market_refresh_provider: str | None = None
    market_refresh_error_class: str | None = None
    market_context_source: str | None = None
    market_context_age_seconds: float | None = None
    market_context_data_quality: str | None = None
    market_context_before: Mapping[str, Any] | None = None
    market_context_after: Mapping[str, Any] | None = None
    market_confirmation_before: float | None = None
    market_confirmation_after: float | None = None
    refresh_upgrade_status: str | None = None
    derivatives_refresh_attempted: bool = False
    derivatives_refresh_success: bool = False
    supply_refresh_attempted: bool = False
    supply_refresh_success: bool = False
    derivative_confirmation_reasons: tuple[str, ...] = ()
    supply_confirmation_reasons: tuple[str, ...] = ()
    evidence_refresh_attempted: bool = False
    evidence_refresh_success: bool = False
    evidence_refresh_queries: tuple[str, ...] = ()
    evidence_quality_before: float | None = None
    evidence_quality_after: float | None = None
    source_pack: str | None = None
    provider_coverage_status: str | None = None
    evidence_absence_is_meaningful: bool = False
    source_coverage_gap: str | None = None
    source_quality_prior: float | None = None
    source_confidence_cap: float | None = None
    evidence_acquisition_attempted: bool = False
    evidence_acquisition_plan: Mapping[str, Any] | None = None
    evidence_acquisition_results: Mapping[str, Any] | None = None
    evidence_acquisition_failures: tuple[str, ...] = ()
    upgrade_reason: str | None = None
    no_upgrade_reason: str | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class EventNearMissRefreshResult:
    hypotheses: tuple[object, ...]
    near_misses: tuple[EventNearMissCandidate, ...]
    refreshed_count: int = 0
    upgraded_count: int = 0
    warnings: tuple[str, ...] = ()


def is_upgrade_candidate(candidate: EventNearMissCandidate) -> bool:
    """Return true for already-promoted rows that are missing evidence for a higher tier."""
    level = str(candidate.opportunity_level_before or "").casefold()
    route = str(candidate.final_route_before or "").upper()
    if level in {"validated_digest", "watchlist"}:
        return True
    if route in {
        event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
        event_alpha_router.EventAlphaRoute.LOCAL_REPORT.value,
    } and candidate.opportunity_score_before >= 60:
        return True
    return False


def split_near_miss_candidates(
    candidates: Iterable[EventNearMissCandidate],
) -> tuple[tuple[EventNearMissCandidate, ...], tuple[EventNearMissCandidate, ...]]:
    near: list[EventNearMissCandidate] = []
    upgrade: list[EventNearMissCandidate] = []
    for candidate in candidates:
        (upgrade if is_upgrade_candidate(candidate) else near).append(candidate)
    return tuple(near), tuple(upgrade)


def detect_near_miss_rows(
    rows: Iterable[Mapping[str, Any] | object],
    *,
    route_decisions: Iterable[object] = (),
    cfg: EventNearMissConfig | None = None,
) -> tuple[EventNearMissCandidate, ...]:
    """Identify persisted rows that are close to useful research routing."""
    cfg = cfg or EventNearMissConfig()
    if not cfg.enabled:
        return ()
    route_by_key = _route_by_identity(route_decisions)
    out_by_key: dict[tuple[str, str, str, str], EventNearMissCandidate] = {}
    for item in rows:
        row = _row_from_object(item)
        if not row:
            continue
        route = _lookup_route(route_by_key, row)
        candidate = _candidate_from_row(row, route=route, cfg=cfg)
        if candidate is None:
            continue
        key = _near_miss_group_key(row, candidate)
        existing = out_by_key.get(key)
        if existing is None or candidate.priority_score > existing.priority_score:
            out_by_key[key] = candidate
    out = list(out_by_key.values())
    out.sort(key=lambda item: item.priority_score, reverse=True)
    return tuple(out[: max(1, int(cfg.max_candidates or 1))])


def targeted_market_refresh_queue(
    rows: Iterable[Mapping[str, Any] | object],
    *,
    route_decisions: Iterable[object] = (),
    cfg: EventNearMissConfig | None = None,
) -> tuple[EventTargetedMarketRefreshQueueItem, ...]:
    """Build a bounded, auditable queue for targeted market-context refreshes."""
    out: list[EventTargetedMarketRefreshQueueItem] = []
    for item in detect_near_miss_rows(rows, route_decisions=route_decisions, cfg=cfg):
        if "targeted_market_refresh" not in item.recommended_refresh_actions:
            continue
        reason = next((_clean_reason(value) for value in item.missing_evidence if _refreshable_market_reason(value)), "needs_fresh_market_confirmation")
        before = dict(item.market_context_before or {})
        out.append(EventTargetedMarketRefreshQueueItem(
            refresh_id=item.refresh_id or item.near_miss_id,
            symbol=item.symbol,
            coin_id=item.coin_id,
            core_opportunity_id=item.core_opportunity_id,
            hypothesis_id=item.hypothesis_id,
            incident_id=item.incident_id,
            reason=reason,
            current_market_source=str(before.get("source") or item.market_context_source or "") or None,
            current_market_age_seconds=_float(before.get("age_seconds")) if before else item.market_context_age_seconds,
            priority_score=item.priority_score,
        ))
    return tuple(out)


def refresh_market_context_for_candidates(
    queue: Iterable[EventTargetedMarketRefreshQueueItem],
    *,
    market_rows: Iterable[Mapping[str, Any]] = (),
    targeted_market_provider: object | None = None,
    now: datetime | None = None,
    cfg: EventNearMissConfig | None = None,
) -> tuple[dict[str, Any], ...]:
    """Fetch market rows for queued candidates without mutating hypotheses.

    The unified pipeline uses :func:`refresh_near_miss_hypotheses` for mutation,
    but this helper gives reports/tests a pure view of attempted/success/failure
    provider details for the targeted refresh queue.
    """
    cfg = cfg or EventNearMissConfig()
    observed = _as_utc(now or datetime.now(timezone.utc))
    fixture_rows = [dict(row) for row in market_rows if isinstance(row, Mapping)]
    results: list[dict[str, Any]] = []
    for item in queue:
        before = {
            "source": item.current_market_source,
            "age_seconds": item.current_market_age_seconds,
        }
        provider_name = getattr(targeted_market_provider, "name", None) or ("fixture_rows" if fixture_rows else "none")
        error_class = None
        warnings: list[str] = []
        row = _find_asset_row(fixture_rows, symbol=item.symbol, coin_id=item.coin_id)
        attempted = bool(row or targeted_market_provider)
        if row is None and targeted_market_provider is not None:
            try:
                fetched = targeted_market_provider.fetch_market_rows((item.coin_id,), max_assets=1)  # type: ignore[attr-defined]
                fetched_rows, fetched_warnings = _normalize_provider_rows(fetched)
                warnings.extend(fetched_warnings)
                row = _find_asset_row(fetched_rows, symbol=item.symbol, coin_id=item.coin_id)
            except Exception as exc:  # noqa: BLE001 - fail-soft research helper
                error_class = type(exc).__name__
                warnings.append(f"targeted_market_refresh_failed:{error_class}")
        after = _market_context(row, source=str(provider_name), now=observed, cfg=cfg)
        results.append({
            "refresh_id": item.refresh_id,
            "symbol": item.symbol,
            "coin_id": item.coin_id,
            "attempted": attempted,
            "success": bool(row),
            "provider": provider_name,
            "error_class": error_class,
            "market_context_before": before,
            "market_context_after": after,
            "warnings": tuple(dict.fromkeys(warnings)),
        })
    return tuple(results)


def refresh_near_miss_hypotheses(
    hypotheses: Iterable[object],
    *,
    cfg: EventNearMissConfig | None = None,
    market_rows: Iterable[Mapping[str, Any]] = (),
    targeted_market_provider: object | None = None,
    derivatives_rows: Iterable[Mapping[str, Any]] = (),
    supply_rows: Iterable[Mapping[str, Any]] = (),
    source_rows: Iterable[Mapping[str, Any]] = (),
    now: datetime | None = None,
) -> EventNearMissRefreshResult:
    """Refresh near-miss hypotheses and recompute final opportunity verdicts."""
    cfg = cfg or EventNearMissConfig()
    original = tuple(hypotheses)
    if not cfg.enabled:
        return EventNearMissRefreshResult(hypotheses=original, near_misses=())
    observed = _as_utc(now or datetime.now(timezone.utc))
    near = detect_near_miss_rows(original, cfg=cfg)
    near_ids = {item.hypothesis_id for item in near if item.hypothesis_id}
    if not near_ids:
        return EventNearMissRefreshResult(hypotheses=original, near_misses=near)
    if not cfg.market_refresh_enabled and not cfg.source_refresh_enabled:
        return EventNearMissRefreshResult(hypotheses=original, near_misses=near)
    refreshed: list[object] = []
    near_by_id = {item.hypothesis_id: item for item in near if item.hypothesis_id}
    refreshed_candidates: list[EventNearMissCandidate] = []
    warnings: list[str] = []
    refresh_budget = max(0, int(cfg.max_market_refresh_assets or 0))
    refreshed_assets = 0
    upgraded = 0
    for hypothesis in original:
        hypothesis_id = str(getattr(hypothesis, "hypothesis_id", "") or "")
        near_candidate = near_by_id.get(hypothesis_id)
        if near_candidate is None:
            refreshed.append(hypothesis)
            continue
        allow_refresh = cfg.market_refresh_enabled and (refresh_budget <= 0 or refreshed_assets < refresh_budget)
        result = _refresh_one_hypothesis(
            hypothesis,
            near_candidate,
            cfg=cfg,
            market_rows=market_rows,
            targeted_market_provider=targeted_market_provider if allow_refresh else None,
            derivatives_rows=derivatives_rows,
            supply_rows=supply_rows,
            source_rows=source_rows,
            now=observed,
            market_refresh_allowed=allow_refresh,
        )
        refreshed.append(result[0])
        refreshed_candidates.append(result[1])
        warnings.extend(result[2])
        if result[1].market_refresh_attempted:
            refreshed_assets += 1
        if result[1].upgrade_reason:
            upgraded += 1
    merged_candidates = tuple(refreshed_candidates or near)
    return EventNearMissRefreshResult(
        hypotheses=tuple(refreshed),
        near_misses=merged_candidates,
        refreshed_count=sum(1 for item in merged_candidates if item.market_refresh_attempted or item.evidence_refresh_attempted),
        upgraded_count=upgraded,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def format_near_miss_report(
    near_misses: Iterable[EventNearMissCandidate],
    *,
    profile: str | None = None,
) -> str:
    rows = [
        "=" * 76,
        "EVENT ALPHA NEAR-MISS REPORT (research-only; no sends/trades)",
        "=" * 76,
    ]
    if profile:
        rows.append(f"profile: {profile}")
    items = list(near_misses)
    near_items, upgrade_items = split_near_miss_candidates(items)
    rows.append(f"near_misses: {len(near_items)}")
    rows.append(f"upgrade_candidates: {len(upgrade_items)}")
    if not items:
        rows.append("")
        rows.append("No near-miss candidates found.")
        rows.append("Research-only report; no notifications, trades, paper rows, live RSI rows, or triggers were created.")
        return "\n".join(rows)
    rows.append("")
    for title, section_items in (
        ("Near-Miss Candidates", near_items),
        ("Upgrade Candidates", upgrade_items),
    ):
        rows.append(f"## {title}")
        if not section_items:
            rows.append("- none")
            rows.append("")
            continue
        for item in section_items:
            _append_candidate_report_lines(rows, item)
        rows.append("")
    rows.append("Research-only report; no notifications, trades, paper rows, live RSI rows, or triggers were created.")
    return "\n".join(rows)


def _append_candidate_report_lines(rows: list[str], item: EventNearMissCandidate) -> None:
    rows.append(
        f"- {item.symbol or 'UNKNOWN'}/{item.coin_id or 'unknown'} "
        f"score={item.opportunity_score_before:.0f}"
        + (
            f"->{item.opportunity_score_after:.0f}"
            if item.opportunity_score_after is not None
            and round(item.opportunity_score_after, 2) != round(item.opportunity_score_before, 2)
            else ""
        )
        + f" level={item.opportunity_level_before}"
        + (f"->{item.opportunity_level_after}" if item.opportunity_level_after and item.opportunity_level_after != item.opportunity_level_before else "")
    )
    rows.append(f"  near_miss_id: {item.near_miss_id}")
    if item.hypothesis_id:
        rows.append(f"  hypothesis_id: {item.hypothesis_id}")
    if item.incident_id:
        rows.append(f"  incident_id: {item.incident_id}")
    rows.append(f"  route: {item.final_route_before or 'unknown'}->{item.final_route_after or item.final_route_before or 'unknown'}")
    rows.append("  missing_evidence: " + (", ".join(item.missing_evidence) if item.missing_evidence else "none"))
    rows.append("  refresh_actions: " + (", ".join(item.recommended_refresh_actions) if item.recommended_refresh_actions else "none"))
    rows.append(
        "  market_refresh: "
        f"attempted={str(item.market_refresh_attempted).lower()} "
        f"success={str(item.market_refresh_success).lower()} "
        f"provider={item.market_refresh_provider or item.market_context_source or 'none'} "
        f"score={item.market_confirmation_before if item.market_confirmation_before is not None else 'n/a'}"
        f"->{item.market_confirmation_after if item.market_confirmation_after is not None else 'n/a'} "
        f"age={_format_age(item.market_context_age_seconds)} "
        f"quality={item.market_context_data_quality or 'unknown'} "
        f"status={item.refresh_upgrade_status or item.upgrade_reason or item.no_upgrade_reason or 'pending'}"
    )
    if item.derivatives_refresh_attempted or item.supply_refresh_attempted:
        rows.append(
            "  enrichment_refresh: "
            f"derivatives={str(item.derivatives_refresh_success).lower()} "
            f"supply={str(item.supply_refresh_success).lower()}"
        )
    if item.evidence_refresh_queries:
        rows.append("  evidence_queries: " + "; ".join(item.evidence_refresh_queries))
    rows.append(
        "  source_pack: "
        f"{item.source_pack or 'unknown'} coverage={item.provider_coverage_status or 'unknown'} "
        f"absence_meaningful={str(bool(item.evidence_absence_is_meaningful)).lower()} "
        f"gap={item.source_coverage_gap or 'none'}"
    )
    if item.evidence_acquisition_plan:
        needed = item.evidence_acquisition_plan.get("evidence_needed") or ()
        queries = item.evidence_acquisition_plan.get("evidence_query_plan") or ()
        rows.append(
            "  evidence_plan: "
            f"needed={'; '.join(str(value) for value in list(needed)[:4]) or 'none'} "
            f"queries={len(queries) if isinstance(queries, Iterable) and not isinstance(queries, (str, bytes, Mapping)) else 'n/a'}"
        )
    rows.append(f"  outcome: {item.upgrade_reason or item.no_upgrade_reason or 'pending_refresh'}")
    if item.warnings:
        rows.append("  warnings: " + "; ".join(item.warnings))

def near_miss_metadata_for_row(row: Mapping[str, Any] | object, *, cfg: EventNearMissConfig | None = None) -> EventNearMissCandidate | None:
    return _candidate_from_row(_row_from_object(row), route=None, cfg=cfg or EventNearMissConfig())


def _refresh_one_hypothesis(
    hypothesis: object,
    near: EventNearMissCandidate,
    *,
    cfg: EventNearMissConfig,
    market_rows: Iterable[Mapping[str, Any]],
    targeted_market_provider: object | None,
    derivatives_rows: Iterable[Mapping[str, Any]],
    supply_rows: Iterable[Mapping[str, Any]],
    source_rows: Iterable[Mapping[str, Any]],
    now: datetime,
    market_refresh_allowed: bool,
) -> tuple[object, EventNearMissCandidate, tuple[str, ...]]:
    row = _row_from_object(hypothesis)
    symbol = near.symbol
    coin_id = near.coin_id
    market_before = _float(row.get("market_confirmation_score"))
    evidence_before = _float(row.get("evidence_quality_score"))
    context_before = _market_context(row, source=str(row.get("market_context_source") or "existing"), now=now, cfg=cfg)
    market_row = _find_asset_row(market_rows, symbol=symbol, coin_id=coin_id)
    provider_warnings: list[str] = []
    attempted_market = market_refresh_allowed
    provider_name = "cycle_rows" if market_row else None
    provider_error_class = None
    if market_refresh_allowed and not market_row and targeted_market_provider is not None and coin_id:
        try:
            provider_name = str(getattr(targeted_market_provider, "name", None) or "targeted_provider")
            fetched = targeted_market_provider.fetch_market_rows((coin_id,), max_assets=1)  # type: ignore[attr-defined]
            fetched_rows, fetched_warnings = _normalize_provider_rows(fetched)
            provider_warnings.extend(fetched_warnings)
            market_row = _find_asset_row(fetched_rows, symbol=symbol, coin_id=coin_id)
        except Exception as exc:  # noqa: BLE001 - fail-soft research refresh
            provider_error_class = type(exc).__name__
            provider_warnings.append(f"targeted_market_refresh_failed:{provider_error_class}")
    derivatives_row = _find_asset_row(derivatives_rows, symbol=symbol, coin_id=coin_id)
    supply_row = _find_asset_row(supply_rows, symbol=symbol, coin_id=coin_id)
    source_row = _find_asset_row(source_rows, symbol=symbol, coin_id=coin_id)
    evidence_after = evidence_before
    evidence_success = False
    if cfg.source_refresh_enabled and source_row:
        refreshed_evidence = _float(source_row.get("evidence_quality_score") or source_row.get("source_quality"))
        if refreshed_evidence is not None:
            evidence_after = max(evidence_before or 0.0, refreshed_evidence)
            evidence_success = evidence_after > (evidence_before or 0.0)
    if not market_row and not derivatives_row and not supply_row and not evidence_success:
        return hypothesis, replace(
            near,
            market_refresh_attempted=attempted_market,
            market_refresh_success=False,
            market_refresh_provider=provider_name,
            market_refresh_error_class=provider_error_class,
            market_context_before=context_before,
            evidence_refresh_attempted=bool(cfg.source_refresh_enabled and near.evidence_refresh_queries),
            evidence_refresh_success=False,
            refresh_upgrade_status="failed" if attempted_market else "not_attempted",
            no_upgrade_reason="no_new_refresh_evidence",
            warnings=tuple(dict.fromkeys((*near.warnings, *provider_warnings))),
        ), tuple(provider_warnings)
    market_context = _market_context(market_row, source=provider_name or "near_miss_market_refresh", now=now, cfg=cfg)
    market_input = event_market_confirmation.EventMarketConfirmationInput(
        market_snapshot=market_context["market_snapshot"],
        derivatives_snapshot=derivatives_row,
        supply_snapshot=supply_row,
        playbook_type=str(row.get("playbook_hint") or row.get("playbook_type") or ""),
        impact_category=str(row.get("impact_category") or ""),
        now=now,
        market_context_observed_at=market_context["timestamp"],
        market_context_source=market_context["source"],
        market_context_max_age_hours=max(0.0, float(cfg.stale_after_seconds or 0.0)) / 3600.0,
        allow_stale_fixture_market_context=False,
    )
    market_result = event_market_confirmation.evaluate_market_confirmation(market_input)
    market_success = bool(market_row)
    components = _quality_components_for_row(row)
    components.update({
        "market_confirmation": max(_float(components.get("market_confirmation")) or 0.0, market_result.market_confirmation_score),
        "market_confirmation_score": market_result.market_confirmation_score,
        "market_confirmation_level": market_result.level,
        "market_context_source": market_context["source"],
        "market_context_timestamp": market_context["timestamp"],
        "market_context_age_seconds": market_context["age_seconds"],
        "market_context_age_hours": (
            round(float(market_context["age_seconds"]) / 3600.0, 4)
            if market_context["age_seconds"] is not None
            else None
        ),
        "market_context_data_quality": market_context["data_quality"],
        "market_context_freshness_status": market_result.market_context_freshness_status,
        "market_context_observed_at": market_result.market_context_observed_at,
        "market_context_freshness_cap_applied": market_result.freshness_cap_applied,
        "market_refresh_attempted": attempted_market,
        "market_refresh_success": market_success,
        "market_refresh_provider": provider_name or ("cycle_rows" if market_row else None),
        "market_refresh_error_class": provider_error_class,
        "market_context_before": context_before,
        "market_context_after": market_context,
        "market_confirmation_before": market_before,
        "market_confirmation_after": market_result.market_confirmation_score,
        "derivatives_refresh_attempted": _playbook_needs_derivatives(row),
        "derivatives_refresh_success": bool(derivatives_row),
        "supply_refresh_attempted": _playbook_needs_supply(row),
        "supply_refresh_success": bool(supply_row),
        "derivative_confirmation_reasons": [
            reason for reason in market_result.reasons
            if reason in {"derivatives_crowding", "funding_heated", "oi_expansion"}
        ],
        "supply_confirmation_reasons": [
            reason for reason in market_result.reasons
            if reason == "supply_pressure"
        ],
        "evidence_refresh_attempted": bool(cfg.source_refresh_enabled and near.evidence_refresh_queries),
        "evidence_refresh_success": evidence_success,
        "evidence_quality_before": evidence_before,
        "evidence_quality_after": evidence_after,
    })
    if evidence_after is not None:
        components["source_quality"] = max(_float(components.get("source_quality")) or 0.0, evidence_after)
        components["evidence_quality_score"] = evidence_after
    verdict = event_opportunity_verdict.evaluate_opportunity(
        impact_path=None,
        market_confirmation=market_result,
        evidence_quality=None,
        hypothesis=hypothesis,
        score_components=components,
    )
    upgrade_path = event_opportunity_verdict.explain_upgrade_path(
        verdict=verdict,
        impact_path=None,
        market_confirmation=market_result,
        evidence_quality=None,
        components=components,
    )
    upgraded = _level_rank(verdict.opportunity_level) > _level_rank(near.opportunity_level_before)
    score_changed = abs(float(verdict.opportunity_score_final) - near.opportunity_score_before) >= 0.01
    upgrade_reason = None
    no_upgrade_reason = None
    if upgraded:
        refresh_upgrade_status = "upgraded"
        upgrade_reason = f"near_miss_refresh_upgraded:{near.opportunity_level_before}->{verdict.opportunity_level}"
    elif score_changed and verdict.opportunity_score_final > near.opportunity_score_before:
        refresh_upgrade_status = "improved_score"
        upgrade_reason = "near_miss_refresh_improved_score"
    else:
        refresh_upgrade_status = "unchanged"
        if not market_success and not evidence_success and not derivatives_row and not supply_row:
            no_upgrade_reason = "no_new_refresh_evidence"
        elif market_context["data_quality"] in {"stale", "unknown", "missing"}:
            no_upgrade_reason = "market_refresh_stale"
        else:
            no_upgrade_reason = "refreshed_evidence_below_upgrade_threshold"
    metadata = {
        **components,
        "initial_opportunity_score": near.opportunity_score_before,
        "initial_opportunity_level": near.opportunity_level_before,
        "post_refresh_opportunity_score": verdict.opportunity_score_final,
        "post_refresh_opportunity_level": verdict.opportunity_level,
        "post_refresh_market_confirmation_level": market_result.level,
        "post_refresh_market_confirmation_score": market_result.market_confirmation_score,
        "post_refresh_evidence_quality_score": evidence_after,
        "final_opportunity_score": verdict.opportunity_score_final,
        "final_opportunity_level": verdict.opportunity_level,
        "final_verdict_source": "combined_refresh" if evidence_success else "market_refresh",
        "final_verdict_reason": upgrade_reason or no_upgrade_reason or "targeted_market_refresh_recomputed_verdict",
        "market_data_freshness": market_result.market_context_freshness_status,
        "market_reaction_confirmation": market_result.level,
        "opportunity_score_final": verdict.opportunity_score_final,
        "opportunity_level": verdict.opportunity_level,
        "opportunity_verdict_reasons": verdict.verdict_reason_codes,
        "missing_requirements": verdict.missing_requirements,
        "manual_verification_items": verdict.manual_verification_items,
        "why_local_only": verdict.why_local_only,
        "why_not_watchlist": verdict.why_not_watchlist,
        "upgrade_requirements": upgrade_path.upgrade_requirements,
        "downgrade_warnings": upgrade_path.downgrade_warnings,
        "market_confirmation_reasons": market_result.reasons,
        "market_confirmation_warnings": market_result.warnings,
        "market_confirmation_missing_fields": market_result.missing_fields,
        "market_confirmation_summary": market_result.confirmation_summary,
        "market_data_freshness": market_result.market_context_freshness_status,
        "market_reaction_confirmation": market_result.level,
        "market_context_snapshot": dict(market_context["market_snapshot"]),
        "near_miss_id": near.near_miss_id,
        "opportunity_level_before": near.opportunity_level_before,
        "opportunity_level_after": verdict.opportunity_level,
        "opportunity_score_before": near.opportunity_score_before,
        "opportunity_score_after": verdict.opportunity_score_final,
        "opportunity_level_before_refresh": near.opportunity_level_before,
        "opportunity_level_after_refresh": verdict.opportunity_level,
        "opportunity_score_before_refresh": near.opportunity_score_before,
        "opportunity_score_after_refresh": verdict.opportunity_score_final,
        "market_confirmation_before_refresh": market_before,
        "market_confirmation_after_refresh": market_result.market_confirmation_score,
        "refresh_upgrade_status": refresh_upgrade_status,
        "refresh_upgrade_reason": upgrade_reason,
        "upgrade_reason": upgrade_reason,
        "no_upgrade_reason": no_upgrade_reason,
        "source_pack": near.source_pack,
        "provider_coverage_status": near.provider_coverage_status,
        "evidence_absence_is_meaningful": near.evidence_absence_is_meaningful,
        "source_coverage_gap": near.source_coverage_gap,
        "source_quality_prior": near.source_quality_prior,
        "source_confidence_cap": near.source_confidence_cap,
        "evidence_acquisition_attempted": near.evidence_acquisition_attempted,
        "evidence_acquisition_plan": near.evidence_acquisition_plan,
        "evidence_acquisition_results": near.evidence_acquisition_results,
        "evidence_acquisition_failures": near.evidence_acquisition_failures,
    }
    current_components = dict(getattr(hypothesis, "score_components", {}) or {})
    current_components.update(metadata)
    replace_kwargs = {
        "market_confirmation_score": market_result.market_confirmation_score,
        "market_confirmation_level": market_result.level,
        "market_confirmation_reasons": market_result.reasons,
        "market_confirmation_warnings": market_result.warnings,
        "market_confirmation_missing_fields": market_result.missing_fields,
        "market_confirmation_summary": market_result.confirmation_summary,
        "market_context_source": market_context["source"],
        "market_context_timestamp": market_context["timestamp"],
        "market_context_age_seconds": market_context["age_seconds"],
        "market_context_age_hours": metadata["market_context_age_hours"],
        "market_context_observed_at": market_result.market_context_observed_at,
        "market_context_freshness_status": market_result.market_context_freshness_status,
        "market_context_freshness_cap_applied": market_result.freshness_cap_applied,
        "market_context_data_quality": market_context["data_quality"],
        "market_context_snapshot": dict(market_context["market_snapshot"]),
        "market_reaction_confirmed": market_result.level in {"weak", "moderate", "strong"},
        "opportunity_score_final": verdict.opportunity_score_final,
        "opportunity_level": verdict.opportunity_level,
        "opportunity_verdict_reasons": verdict.verdict_reason_codes,
        "missing_requirements": verdict.missing_requirements,
        "manual_verification_items": verdict.manual_verification_items,
        "why_local_only": verdict.why_local_only,
        "why_not_watchlist": verdict.why_not_watchlist,
        "upgrade_requirements": upgrade_path.upgrade_requirements,
        "downgrade_warnings": upgrade_path.downgrade_warnings,
        "score_components": current_components,
    }
    for key in _OPTIONAL_HYPOTHESIS_FIELDS:
        if hasattr(hypothesis, key):
            replace_kwargs[key] = metadata.get(key)
    try:
        updated = replace(hypothesis, **replace_kwargs)
    except TypeError:
        updated = hypothesis
    candidate = replace(
        near,
        opportunity_level_after=verdict.opportunity_level,
        opportunity_score_after=verdict.opportunity_score_final,
        market_refresh_attempted=attempted_market,
        market_refresh_success=market_success,
        market_refresh_provider=metadata["market_refresh_provider"],
        market_refresh_error_class=provider_error_class,
        market_context_source=market_context["source"],
        market_context_age_seconds=market_context["age_seconds"],
        market_context_data_quality=market_context["data_quality"],
        market_context_before=context_before,
        market_context_after=market_context,
        market_confirmation_before=market_before,
        market_confirmation_after=market_result.market_confirmation_score,
        refresh_upgrade_status=refresh_upgrade_status,
        derivatives_refresh_attempted=_playbook_needs_derivatives(row),
        derivatives_refresh_success=bool(derivatives_row),
        supply_refresh_attempted=_playbook_needs_supply(row),
        supply_refresh_success=bool(supply_row),
        derivative_confirmation_reasons=tuple(metadata["derivative_confirmation_reasons"]),
        supply_confirmation_reasons=tuple(metadata["supply_confirmation_reasons"]),
        evidence_refresh_attempted=bool(cfg.source_refresh_enabled and near.evidence_refresh_queries),
        evidence_refresh_success=evidence_success,
        evidence_quality_before=evidence_before,
        evidence_quality_after=evidence_after,
        upgrade_reason=upgrade_reason,
        no_upgrade_reason=no_upgrade_reason,
        final_route_after=_route_for_level(verdict.opportunity_level),
        warnings=tuple(dict.fromkeys((*near.warnings, *provider_warnings, *market_result.warnings))),
    )
    return updated, candidate, tuple(provider_warnings)


_OPTIONAL_HYPOTHESIS_FIELDS = {
    "market_refresh_attempted",
    "market_refresh_success",
    "market_refresh_provider",
    "market_refresh_error_class",
    "market_context_before",
    "market_context_after",
    "market_confirmation_before",
    "market_confirmation_after",
    "derivatives_refresh_attempted",
    "derivatives_refresh_success",
    "supply_refresh_attempted",
    "supply_refresh_success",
    "derivative_confirmation_reasons",
    "supply_confirmation_reasons",
    "evidence_refresh_attempted",
    "evidence_refresh_results",
    "evidence_quality_before",
    "evidence_quality_after",
    "opportunity_level_before",
    "opportunity_level_after",
    "opportunity_score_before",
    "opportunity_score_after",
    "opportunity_level_before_refresh",
    "opportunity_level_after_refresh",
    "opportunity_score_before_refresh",
    "opportunity_score_after_refresh",
    "initial_opportunity_score",
    "initial_opportunity_level",
    "post_refresh_opportunity_score",
    "post_refresh_opportunity_level",
    "post_refresh_market_confirmation_level",
    "post_refresh_market_confirmation_score",
    "post_refresh_evidence_quality_score",
    "final_opportunity_score",
    "final_opportunity_level",
    "final_verdict_source",
    "final_verdict_reason",
    "market_data_freshness",
    "market_reaction_confirmation",
    "market_confirmation_before_refresh",
    "market_confirmation_after_refresh",
    "refresh_upgrade_status",
    "refresh_upgrade_reason",
    "upgrade_reason",
    "no_upgrade_reason",
    "source_pack",
    "provider_coverage_status",
    "evidence_absence_is_meaningful",
    "source_coverage_gap",
    "source_quality_prior",
    "source_confidence_cap",
    "evidence_acquisition_attempted",
    "evidence_acquisition_plan",
    "evidence_acquisition_results",
    "evidence_acquisition_failures",
}


def _candidate_from_row(
    row: Mapping[str, Any],
    *,
    route: Mapping[str, Any] | None,
    cfg: EventNearMissConfig,
) -> EventNearMissCandidate | None:
    if not row:
        return None
    quality = event_alpha_quality_fields.ensure_quality_fields(row, components=_quality_components_for_row(row))
    symbol, coin_id = _asset_identity_from_row(row)
    if not symbol or symbol == "SECTOR" or not coin_id:
        return None
    text = " ".join(str(value or "") for value in (
        quality.get("impact_path_type"),
        quality.get("candidate_role"),
        quality.get("source_class"),
        quality.get("evidence_specificity"),
        quality.get("why_local_only"),
        quality.get("why_not_watchlist"),
        quality.get("opportunity_verdict_reasons"),
        quality.get("quality_gate_block_reason"),
        row.get("warnings"),
        row.get("rejection_reasons"),
    )).casefold()
    if "source_noise" in text or "ticker_collision" in text or "ticker_word_collision" in text:
        return None
    if "quality_context_missing" in text and (
        "insufficient_data" in text
        or "generic_cooccurrence_only" in text
        or (_float(quality.get("opportunity_score_final")) or 0.0) <= 0
    ):
        return None
    if str(quality.get("impact_path_type") or "") == "generic_cooccurrence_only":
        return None
    if str(quality.get("candidate_role") or "") in {"source_noise", "ticker_word_collision", "generic_mention"}:
        return None
    score = _float(quality.get("opportunity_score_final")) or 0.0
    if score <= 0:
        return None
    level = str(quality.get("opportunity_level") or "local_only")
    final_route = _final_route_for_route(route) if route is not None else str(row.get("final_route_after_quality_gate") or row.get("route") or "")
    alertable = event_alpha_router.route_value_is_alertable(final_route) if final_route else False
    if str(row.get("row_type") or "") == "event_core_opportunity" and (
        alertable
        or final_route == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value
        or level in {"validated_digest", "watchlist", "high_priority"}
    ):
        return None
    market_refresh_reasons = _market_refresh_reasons(quality, row)
    if level in {"watchlist", "high_priority"} and not market_refresh_reasons:
        return None
    missing = _missing_evidence(quality, row)
    if market_refresh_reasons:
        missing = tuple(dict.fromkeys((*missing, *market_refresh_reasons)))
    near_digest = 0 <= cfg.digest_threshold - score <= cfg.near_threshold_points
    near_watchlist = 0 <= cfg.watchlist_threshold - score <= cfg.near_threshold_points
    route_inconsistent = level in {"validated_digest", "watchlist", "high_priority"} and not alertable
    blocked_by_refreshable = any(_refreshable_missing_reason(value) for value in missing)
    blocked_by_market_refresh = any(_refreshable_market_reason(value) for value in missing)
    promoted_with_fresh_context = (
        level in {"watchlist", "high_priority"}
        and not blocked_by_refreshable
        and not blocked_by_market_refresh
        and not route_inconsistent
    )
    digest_with_fresh_context = (
        level == "validated_digest"
        and not near_watchlist
        and not blocked_by_refreshable
        and not blocked_by_market_refresh
        and not route_inconsistent
    )
    if alertable and not (blocked_by_refreshable or near_watchlist or route_inconsistent):
        return None
    if promoted_with_fresh_context or digest_with_fresh_context:
        return None
    if not (near_digest or near_watchlist or route_inconsistent or blocked_by_refreshable):
        return None
    if level == "local_only" and score < cfg.digest_threshold - cfg.near_threshold_points and not blocked_by_refreshable:
        return None
    pack = event_source_packs.source_pack_for_playbook(
        str(row.get("playbook_type") or row.get("latest_effective_playbook_type") or quality.get("playbook_type") or ""),
        impact_path_type=str(quality.get("impact_path_type") or row.get("impact_path_type") or ""),
        impact_category=str(row.get("impact_category") or quality.get("impact_category") or ""),
    )
    provider_status = str(row.get("provider_coverage_status") or quality.get("provider_coverage_status") or "")
    source_assessment = event_source_registry.assess_source(
        row,
        symbol=symbol,
        coin_id=coin_id,
        playbook_type=str(row.get("playbook_type") or quality.get("playbook_type") or ""),
        provider_coverage_status=provider_status or None,
    )
    source_gap = event_source_registry.coverage_gap_reason(
        source_assessment.provider,
        source_assessment.provider_coverage_status,
    )
    if source_gap:
        missing = tuple(dict.fromkeys((*missing, "needs_source_coverage", source_gap)))
    pack_eval = event_source_packs.evaluate_pack_evidence({**row, **source_assessment.to_metadata()}, pack=pack)
    pack_missing = tuple(str(item) for item in pack_eval.get("source_pack_missing_evidence") or ())
    if pack_missing:
        missing = tuple(dict.fromkeys((*missing, *pack_missing)))
    priority = _priority_score(score, level, missing, route_inconsistent=route_inconsistent)
    queries = _evidence_refresh_queries(row, max_queries=cfg.max_source_queries)
    planner_request = event_llm_evidence_planner.request_from_row(
        {
            **dict(row),
            **source_assessment.to_metadata(),
            "source_pack": pack.name,
            "source_pack_missing_evidence": pack_missing,
            "opportunity_level": level,
            "opportunity_score_final": score,
        },
        missing_evidence=missing,
        source_pack=pack.name,
    )
    planner_result = event_llm_evidence_planner.plan_evidence(planner_request)
    plan_metadata = planner_result.to_metadata()
    plan_selected = planner_result.selected and event_llm_evidence_planner.should_plan_evidence({
        **dict(row),
        "opportunity_level": level,
        "opportunity_score_final": score,
        "missing_requirements": missing,
        "source_pack": pack.name,
    })
    return EventNearMissCandidate(
        near_miss_id=_near_miss_id(row, symbol=symbol, coin_id=coin_id),
        refresh_id=_refresh_id(row, symbol=symbol, coin_id=coin_id),
        symbol=symbol,
        coin_id=coin_id,
        core_opportunity_id=_core_opportunity_id_for_row(row),
        hypothesis_id=_optional_str(row.get("hypothesis_id")),
        incident_id=_optional_str(row.get("incident_id")),
        opportunity_level_before=level,
        opportunity_score_before=score,
        final_route_before=final_route or None,
        missing_evidence=missing,
        recommended_refresh_actions=_recommended_refresh_actions(missing, row, pack=pack),
        priority_score=priority,
        market_context_before=_market_context(row, source=str(row.get("market_context_source") or "existing"), now=datetime.now(timezone.utc), cfg=cfg),
        market_context_source=str(row.get("market_context_source") or quality.get("market_context_source") or "") or None,
        market_context_age_seconds=_float(row.get("market_context_age_seconds") or quality.get("market_context_age_seconds")),
        market_context_data_quality=str(row.get("market_context_freshness_status") or quality.get("market_context_freshness_status") or row.get("market_context_data_quality") or quality.get("market_context_data_quality") or "") or None,
        market_confirmation_before=_float(quality.get("market_confirmation_score")),
        evidence_quality_before=_float(quality.get("evidence_quality_score")),
        evidence_refresh_queries=queries,
        source_pack=pack.name,
        provider_coverage_status=source_assessment.provider_coverage_status,
        evidence_absence_is_meaningful=source_assessment.evidence_absence_is_meaningful,
        source_coverage_gap=source_gap,
        source_quality_prior=source_assessment.source_quality_prior,
        source_confidence_cap=source_assessment.confidence_cap,
        evidence_acquisition_attempted=plan_selected,
        evidence_acquisition_plan=plan_metadata if plan_selected else None,
        evidence_acquisition_failures=tuple(planner_result.provider_gaps),
        warnings=tuple(dict.fromkeys((*source_assessment.warnings, *planner_result.warnings))),
    )


def _near_miss_group_key(row: Mapping[str, Any], candidate: EventNearMissCandidate) -> tuple[str, str, str, str]:
    if candidate.core_opportunity_id:
        return ("core_opportunity", candidate.core_opportunity_id, "", "")
    quality = event_alpha_quality_fields.ensure_quality_fields(row, components=_quality_components_for_row(row))
    incident = candidate.incident_id or str(row.get("event_cluster_id") or row.get("cluster_id") or row.get("event_id") or "unknown")
    asset = candidate.coin_id or candidate.symbol
    path = str(quality.get("impact_path_type") or row.get("impact_path_type") or "unknown")
    role = str(quality.get("candidate_role") or row.get("candidate_role") or "unknown")
    return (incident, asset, path, role)


def _core_opportunity_id_for_row(row: Mapping[str, Any]) -> str | None:
    explicit = _optional_str(row.get("core_opportunity_id") or row.get("aggregated_candidate_id"))
    if explicit:
        return explicit
    try:
        return event_core_opportunities.core_opportunity_id_for_row(row)
    except Exception:  # noqa: BLE001 - near-miss reports must fail soft
        return None


def _missing_evidence(quality: Mapping[str, Any], row: Mapping[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    for key in (
        "why_not_watchlist",
        "why_local_only",
        "missing_requirements",
        "upgrade_requirements",
        "market_confirmation_missing_fields",
        "manual_verification_items",
    ):
        raw = quality.get(key) if key in quality else row.get(key)
        if isinstance(raw, str):
            values.append(raw)
        elif isinstance(raw, Iterable):
            values.extend(str(item) for item in raw if str(item))
    if _float(quality.get("market_confirmation_score")) is not None and (_float(quality.get("market_confirmation_score")) or 0.0) < 50:
        values.append("market_confirmation")
    return tuple(dict.fromkeys(_clean_reason(value) for value in values if _clean_reason(value)))


def _market_refresh_reasons(quality: Mapping[str, Any], row: Mapping[str, Any]) -> tuple[str, ...]:
    status = str(
        row.get("market_context_freshness_status")
        or quality.get("market_context_freshness_status")
        or row.get("market_context_data_quality")
        or quality.get("market_context_data_quality")
        or ""
    ).casefold()
    cap = _truthy(
        row.get("market_context_freshness_cap_applied")
        if row.get("market_context_freshness_cap_applied") is not None
        else quality.get("market_context_freshness_cap_applied")
    )
    warnings = _iter_texts(row.get("market_confirmation_warnings") or quality.get("market_confirmation_warnings"))
    missing = _iter_texts(row.get("market_confirmation_missing_fields") or quality.get("market_confirmation_missing_fields"))
    out: list[str] = []
    if status in {"stale", "missing", "unknown"}:
        out.append(f"market_context_{status}")
    if cap:
        out.append("market_context_freshness_cap_applied")
    for value in (*warnings, *missing):
        text = _clean_reason(value)
        if text in {
            "market_context_stale_capped",
            "market_context_missing",
            "market_context_unknown_timestamp",
            "needs_fresh_market_confirmation",
        }:
            out.append(text)
    return tuple(dict.fromkeys(out))


def _recommended_refresh_actions(
    missing: Iterable[str],
    row: Mapping[str, Any],
    *,
    pack: event_source_packs.SourcePack | None = None,
) -> tuple[str, ...]:
    actions: list[str] = []
    if any(_refreshable_market_reason(reason) for reason in missing):
        actions.append("targeted_market_refresh")
    if _playbook_needs_derivatives(row):
        actions.append("targeted_derivatives_refresh")
    if _playbook_needs_supply(row):
        actions.append("targeted_supply_refresh")
    if any("source" in reason or "evidence" in reason or "impact_path" in reason for reason in missing):
        actions.append("targeted_evidence_refresh")
        actions.append("source_pack_search")
    if any("official" in reason or "listing" in reason or "unlock" in reason for reason in missing):
        actions.append("official_source_search")
    if pack is not None:
        if pack.market_refresh_required:
            actions.append("targeted_market_refresh")
        if pack.derivatives_refresh_required:
            actions.append("targeted_derivatives_refresh")
        if pack.supply_refresh_required:
            actions.append("targeted_supply_refresh")
    return tuple(dict.fromkeys(actions or ("operator_review",)))


def _refreshable_missing_reason(reason: str) -> bool:
    text = reason.casefold()
    return any(part in text for part in ("market", "volume", "liquidity", "source", "evidence", "impact_path", "derivatives", "supply"))


def _refreshable_market_reason(reason: str) -> bool:
    text = reason.casefold()
    return any(part in text for part in ("market", "volume", "liquidity", "fresh", "stale"))


def _quality_components_for_row(row: Mapping[str, Any]) -> dict[str, Any]:
    components = row.get("latest_score_components")
    if not isinstance(components, Mapping):
        components = row.get("score_components")
    out = dict(components or {})
    for key, value in row.items():
        if key in event_alpha_quality_fields.REQUIRED_QUALITY_FIELDS or key in {
            "impact_category",
            "playbook_type",
            "playbook_hint",
            "validation_stage",
            "validated_symbol",
            "validated_coin_id",
            "hypothesis_score",
            "score",
            "opportunity_score_v2",
            "incident_confidence",
            "market_reaction_confirmed",
            "causal_mechanism_confirmed",
        }:
            if value not in (None, "", [], {}, ()):
                out[key] = value
    return out


def _market_context(row: Mapping[str, Any] | None, *, source: str, now: datetime, cfg: EventNearMissConfig) -> dict[str, Any]:
    if not row:
        return {
            "market_snapshot": {},
            "source": "missing",
            "timestamp": None,
            "age_seconds": None,
            "data_quality": "missing",
        }
    timestamp = (
        row.get("market_context_observed_at")
        or row.get("market_context_timestamp")
        or row.get("watchlist_market_observed_at")
        or row.get("timestamp")
        or row.get("market_timestamp")
        or row.get("observed_at")
        or row.get("fetched_at")
        or row.get("updated_at")
    )
    age = _age_seconds(timestamp, now)
    if timestamp in (None, ""):
        quality = "unknown"
    elif age is None:
        quality = "unknown"
    elif age <= cfg.stale_after_seconds:
        quality = "fresh"
    else:
        quality = "stale"
    return {
        "market_snapshot": dict(row),
        "source": str(row.get("watchlist_market_source") or row.get("source") or source),
        "timestamp": str(timestamp) if timestamp not in (None, "") else None,
        "age_seconds": age,
        "data_quality": quality,
    }


def _find_asset_row(rows: Iterable[Mapping[str, Any]], *, symbol: str, coin_id: str) -> dict[str, Any] | None:
    clean_symbol = symbol.strip().upper()
    clean_coin = coin_id.strip().casefold()
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        row_coin = str(row.get("coin_id") or row.get("id") or "").strip().casefold()
        row_symbol = str(row.get("symbol") or row.get("base_symbol") or row.get("asset_symbol") or row.get("base_asset") or "").strip().upper()
        if (clean_coin and row_coin == clean_coin) or (clean_symbol and row_symbol == clean_symbol):
            return dict(row)
    return None


def _asset_identity_from_row(row: Mapping[str, Any]) -> tuple[str, str]:
    symbol = str(row.get("validated_symbol") or row.get("symbol") or "").strip().upper()
    coin_id = str(row.get("validated_coin_id") or row.get("coin_id") or "").strip()
    if symbol and coin_id:
        return symbol, coin_id
    for key in ("validated_candidate_assets", "crypto_candidate_assets"):
        raw_assets = row.get(key)
        if not isinstance(raw_assets, Iterable) or isinstance(raw_assets, (str, bytes, Mapping)):
            continue
        for asset in raw_assets:
            if not isinstance(asset, Mapping):
                continue
            accepted = asset.get("validated")
            if accepted is False:
                continue
            asset_symbol = str(asset.get("symbol") or "").strip().upper()
            asset_coin = str(asset.get("coin_id") or asset.get("id") or "").strip()
            if asset_symbol and asset_coin:
                return asset_symbol, asset_coin
    symbols = row.get("candidate_symbols")
    coins = row.get("candidate_coin_ids")
    if not symbol and isinstance(symbols, Iterable) and not isinstance(symbols, (str, bytes, Mapping)):
        symbol = str(next((item for item in symbols if str(item or "").strip()), "")).strip().upper()
    if not coin_id and isinstance(coins, Iterable) and not isinstance(coins, (str, bytes, Mapping)):
        coin_id = str(next((item for item in coins if str(item or "").strip()), "")).strip()
    return symbol, coin_id


def _normalize_provider_rows(raw: Any) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    rows_raw = raw
    if isinstance(raw, tuple) and raw:
        rows_raw = raw[0]
        if len(raw) > 1 and isinstance(raw[1], Iterable) and not isinstance(raw[1], (str, bytes)):
            warnings.extend(str(item) for item in raw[1] if str(item))
    if not isinstance(rows_raw, Iterable) or isinstance(rows_raw, (str, bytes, Mapping)):
        return [], warnings
    return [dict(row) for row in rows_raw if isinstance(row, Mapping)], warnings


def _evidence_refresh_queries(row: Mapping[str, Any], *, max_queries: int) -> tuple[str, ...]:
    symbol = str(row.get("validated_symbol") or row.get("symbol") or "").strip().upper()
    external = str(row.get("external_asset") or row.get("incident_primary_subject") or row.get("impact_category") or "").strip()
    impact = str(row.get("impact_path_type") or row.get("impact_category") or "").casefold()
    queries: list[str] = []
    if symbol and external:
        queries.append(f"{symbol} {external} exposure")
    if symbol and "exploit" in impact:
        queries.append(f"{symbol} exploit confirmed")
    if symbol and "listing" in impact:
        queries.append(f"{symbol} listing announcement")
    if symbol and "unlock" in impact:
        queries.append(f"{symbol} token unlock")
    return tuple(dict.fromkeys(queries))[: max(0, int(max_queries or 0))]


def _route_by_identity(route_decisions: Iterable[object]) -> dict[str, Mapping[str, Any]]:
    out: dict[str, Mapping[str, Any]] = {}
    for decision in route_decisions:
        entry = getattr(decision, "entry", None)
        data = {
            "final_route_after_quality_gate": event_alpha_router.final_route_value(decision),
            "alertable": event_alpha_router.alertable_after_quality_gate(decision),
            "route_reason": getattr(decision, "reason", None),
        }
        for key in _identity_keys(_row_from_object(entry)):
            out[key] = data
    return out


def _lookup_route(route_by_key: Mapping[str, Mapping[str, Any]], row: Mapping[str, Any]) -> Mapping[str, Any] | None:
    for key in _identity_keys(row):
        if key in route_by_key:
            return route_by_key[key]
    return None


def _identity_keys(row: Mapping[str, Any]) -> tuple[str, ...]:
    keys: list[str] = []
    for key in ("hypothesis_id", "event_id", "key", "alert_id"):
        value = str(row.get(key) or "").strip()
        if value:
            keys.append(f"{key}:{value}")
    symbol, coin_id = _asset_identity_from_row(row)
    if symbol:
        keys.append(f"symbol:{symbol}")
    if coin_id:
        keys.append(f"coin_id:{coin_id}")
    return tuple(dict.fromkeys(keys))


def _row_identity(row: Mapping[str, Any]) -> str:
    return "|".join(_identity_keys(row)) or "unknown"


def _near_miss_id(row: Mapping[str, Any], *, symbol: str, coin_id: str) -> str:
    base = str(_core_opportunity_id_for_row(row) or row.get("hypothesis_id") or row.get("event_id") or row.get("key") or coin_id or symbol)
    return "near:" + base.replace(" ", "_")[:96]


def _refresh_id(row: Mapping[str, Any], *, symbol: str, coin_id: str) -> str:
    base = str(_core_opportunity_id_for_row(row) or row.get("hypothesis_id") or row.get("event_id") or coin_id or symbol)
    return "refresh:" + base.replace(" ", "_")[:96]


def _final_route_for_route(route: Mapping[str, Any]) -> str:
    return str(route.get("final_route_after_quality_gate") or route.get("route") or "")


def _route_for_level(level: str) -> str:
    if level == event_opportunity_verdict.OpportunityLevel.HIGH_PRIORITY.value:
        return event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value
    if level in {
        event_opportunity_verdict.OpportunityLevel.VALIDATED_DIGEST.value,
        event_opportunity_verdict.OpportunityLevel.WATCHLIST.value,
    }:
        return event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value
    if level == event_opportunity_verdict.OpportunityLevel.EXPLORATORY.value:
        return event_alpha_router.EventAlphaRoute.LOCAL_REPORT.value
    return event_alpha_router.EventAlphaRoute.STORE_ONLY.value


def _priority_score(score: float, level: str, missing: tuple[str, ...], *, route_inconsistent: bool) -> float:
    priority = score
    if level == "validated_digest":
        priority += 15
    elif level == "watchlist":
        priority += 20
    elif level == "exploratory":
        priority += 5
    if route_inconsistent:
        priority += 20
    if any("market" in item for item in missing):
        priority += 6
    if any("source" in item or "evidence" in item for item in missing):
        priority += 4
    return round(priority, 2)


def _playbook_needs_derivatives(row: Mapping[str, Any]) -> bool:
    text = " ".join(str(row.get(key) or "") for key in ("playbook_type", "playbook_hint", "impact_category", "impact_path_type")).casefold()
    return any(token in text for token in ("perp", "squeeze", "proxy", "listing"))


def _playbook_needs_supply(row: Mapping[str, Any]) -> bool:
    text = " ".join(str(row.get(key) or "") for key in ("playbook_type", "playbook_hint", "impact_category", "impact_path_type")).casefold()
    return "unlock" in text or "supply" in text


def _level_rank(level: str) -> int:
    order = {
        "local_only": 0,
        "exploratory": 1,
        "validated_digest": 2,
        "watchlist": 3,
        "high_priority": 4,
    }
    return order.get(str(level or ""), 0)


def _clean_reason(value: str) -> str:
    return str(value or "").strip().replace(" ", "_")


def _iter_texts(value: Any) -> tuple[str, ...]:
    if value in (None, "", [], {}, ()):
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Mapping):
        return tuple(str(key) for key in value)
    if isinstance(value, Iterable):
        return tuple(str(item) for item in value if str(item))
    return (str(value),)


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _optional_str(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_age(age_seconds: Any) -> str:
    value = _float(age_seconds)
    if value is None:
        return "n/a"
    age_hours = value / 3600.0
    if age_hours < 1:
        return f"{age_hours * 60:.0f}m"
    return f"{age_hours:.1f}h"


def _age_seconds(timestamp: Any, now: datetime) -> float | None:
    if timestamp in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
    except ValueError:
        return None
    parsed = _as_utc(parsed)
    return max(0.0, (now - parsed).total_seconds())


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _row_from_object(item: Mapping[str, Any] | object | None) -> dict[str, Any]:
    if item is None:
        return {}
    if isinstance(item, Mapping):
        data = dict(item)
    else:
        data = dict(getattr(item, "__dict__", {}) or {})
    components = data.get("latest_score_components")
    if isinstance(components, Mapping):
        for key, value in components.items():
            data.setdefault(key, value)
    score_components = data.get("score_components")
    if isinstance(score_components, Mapping):
        for key, value in score_components.items():
            data.setdefault(key, value)
    return data
