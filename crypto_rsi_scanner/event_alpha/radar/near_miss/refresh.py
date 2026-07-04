"""Event Alpha near-miss refresh helpers."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Mapping

import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
import crypto_rsi_scanner.event_alpha.outcomes.quality_fields as event_alpha_quality_fields
import crypto_rsi_scanner.event_alpha.radar.core_opportunities as event_core_opportunities
import crypto_rsi_scanner.event_alpha.radar.llm.evidence_planner as event_llm_evidence_planner
import crypto_rsi_scanner.event_alpha.radar.market_confirmation as event_market_confirmation
import crypto_rsi_scanner.event_alpha.radar.opportunity_verdict as event_opportunity_verdict
import crypto_rsi_scanner.event_alpha.providers.source_packs as event_source_packs
import crypto_rsi_scanner.event_alpha.providers.source_registry as event_source_registry
from .models import *  # noqa: F403 - split modules share legacy model names


@dataclass(frozen=True)
class _NearMissRefreshRows:
    market_row: Mapping[str, Any] | None
    derivatives_row: Mapping[str, Any] | None
    supply_row: Mapping[str, Any] | None
    source_row: Mapping[str, Any] | None
    attempted_market: bool
    provider_name: str | None
    provider_error_class: str | None
    provider_warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class _NearMissEvidenceRefresh:
    evidence_before: float | None
    evidence_after: float | None
    evidence_success: bool


@dataclass(frozen=True)
class _NearMissMarketRefresh:
    market_context: dict[str, Any]
    market_result: event_market_confirmation.EventMarketConfirmationResult
    market_success: bool


@dataclass(frozen=True)
class _NearMissVerdictRefresh:
    verdict: event_opportunity_verdict.OpportunityVerdict
    upgrade_path: event_opportunity_verdict.OpportunityUpgradePath
    refresh_upgrade_status: str
    upgrade_reason: str | None
    no_upgrade_reason: str | None


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
    context_before = _market_context(row, source=str(row.get("market_context_source") or "existing"), now=now, cfg=cfg)
    rows = _near_miss_refresh_rows(
        symbol=symbol,
        coin_id=coin_id,
        market_rows=market_rows,
        derivatives_rows=derivatives_rows,
        supply_rows=supply_rows,
        source_rows=source_rows,
        targeted_market_provider=targeted_market_provider,
        market_refresh_allowed=market_refresh_allowed,
    )
    evidence = _near_miss_evidence_refresh(row, rows.source_row, cfg=cfg)
    if _near_miss_has_no_refresh_evidence(rows, evidence):
        return _near_miss_no_evidence_result(hypothesis, near, context_before, rows, cfg=cfg)

    market = _near_miss_market_refresh(row, rows, cfg=cfg, now=now)
    components = _near_miss_refresh_components(
        row,
        near,
        rows,
        evidence,
        market,
        market_before=market_before,
        context_before=context_before,
        cfg=cfg,
    )
    verdict = _near_miss_verdict_refresh(
        hypothesis,
        near,
        rows,
        evidence,
        market,
        components,
    )
    metadata = _near_miss_refresh_metadata(
        near,
        components,
        evidence,
        market,
        verdict,
        market_before=market_before,
    )
    updated = _near_miss_updated_hypothesis(hypothesis, metadata, market, verdict)
    candidate = _near_miss_refreshed_candidate(
        near,
        row,
        rows,
        evidence,
        market,
        verdict,
        metadata,
        market_before=market_before,
        context_before=context_before,
        cfg=cfg,
    )
    return updated, candidate, rows.provider_warnings


def _near_miss_refresh_rows(
    *,
    symbol: str,
    coin_id: str,
    market_rows: Iterable[Mapping[str, Any]],
    derivatives_rows: Iterable[Mapping[str, Any]],
    supply_rows: Iterable[Mapping[str, Any]],
    source_rows: Iterable[Mapping[str, Any]],
    targeted_market_provider: object | None,
    market_refresh_allowed: bool,
) -> _NearMissRefreshRows:
    market_row = _find_asset_row(market_rows, symbol=symbol, coin_id=coin_id)
    provider_warnings: list[str] = []
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
    return _NearMissRefreshRows(
        market_row=market_row,
        derivatives_row=_find_asset_row(derivatives_rows, symbol=symbol, coin_id=coin_id),
        supply_row=_find_asset_row(supply_rows, symbol=symbol, coin_id=coin_id),
        source_row=_find_asset_row(source_rows, symbol=symbol, coin_id=coin_id),
        attempted_market=market_refresh_allowed,
        provider_name=provider_name,
        provider_error_class=provider_error_class,
        provider_warnings=tuple(provider_warnings),
    )


def _near_miss_evidence_refresh(
    row: Mapping[str, Any],
    source_row: Mapping[str, Any] | None,
    *,
    cfg: EventNearMissConfig,
) -> _NearMissEvidenceRefresh:
    evidence_before = _float(row.get("evidence_quality_score"))
    evidence_after = evidence_before
    evidence_success = False
    if cfg.source_refresh_enabled and source_row:
        refreshed_evidence = _float(source_row.get("evidence_quality_score") or source_row.get("source_quality"))
        if refreshed_evidence is not None:
            evidence_after = max(evidence_before or 0.0, refreshed_evidence)
            evidence_success = evidence_after > (evidence_before or 0.0)
    return _NearMissEvidenceRefresh(
        evidence_before=evidence_before,
        evidence_after=evidence_after,
        evidence_success=evidence_success,
    )


def _near_miss_has_no_refresh_evidence(
    rows: _NearMissRefreshRows,
    evidence: _NearMissEvidenceRefresh,
) -> bool:
    return (
        not rows.market_row
        and not rows.derivatives_row
        and not rows.supply_row
        and not evidence.evidence_success
    )


def _near_miss_no_evidence_result(
    hypothesis: object,
    near: EventNearMissCandidate,
    context_before: Mapping[str, Any],
    rows: _NearMissRefreshRows,
    *,
    cfg: EventNearMissConfig,
) -> tuple[object, EventNearMissCandidate, tuple[str, ...]]:
    return hypothesis, replace(
        near,
        market_refresh_attempted=rows.attempted_market,
        market_refresh_success=False,
        market_refresh_provider=rows.provider_name,
        market_refresh_error_class=rows.provider_error_class,
        market_context_before=context_before,
        evidence_refresh_attempted=bool(cfg.source_refresh_enabled and near.evidence_refresh_queries),
        evidence_refresh_success=False,
        refresh_upgrade_status="failed" if rows.attempted_market else "not_attempted",
        no_upgrade_reason="no_new_refresh_evidence",
        warnings=tuple(dict.fromkeys((*near.warnings, *rows.provider_warnings))),
    ), rows.provider_warnings


def _near_miss_market_refresh(
    row: Mapping[str, Any],
    rows: _NearMissRefreshRows,
    *,
    cfg: EventNearMissConfig,
    now: datetime,
) -> _NearMissMarketRefresh:
    market_context = _market_context(
        rows.market_row,
        source=rows.provider_name or "near_miss_market_refresh",
        now=now,
        cfg=cfg,
    )
    market_input = event_market_confirmation.EventMarketConfirmationInput(
        market_snapshot=market_context["market_snapshot"],
        derivatives_snapshot=rows.derivatives_row,
        supply_snapshot=rows.supply_row,
        playbook_type=str(row.get("playbook_hint") or row.get("playbook_type") or ""),
        impact_category=str(row.get("impact_category") or ""),
        now=now,
        market_context_observed_at=market_context["timestamp"],
        market_context_source=market_context["source"],
        market_context_max_age_hours=max(0.0, float(cfg.stale_after_seconds or 0.0)) / 3600.0,
        allow_stale_fixture_market_context=False,
    )
    return _NearMissMarketRefresh(
        market_context=market_context,
        market_result=event_market_confirmation.evaluate_market_confirmation(market_input),
        market_success=bool(rows.market_row),
    )


def _near_miss_refresh_components(
    row: Mapping[str, Any],
    near: EventNearMissCandidate,
    rows: _NearMissRefreshRows,
    evidence: _NearMissEvidenceRefresh,
    market: _NearMissMarketRefresh,
    *,
    market_before: float | None,
    context_before: Mapping[str, Any],
    cfg: EventNearMissConfig,
) -> dict[str, Any]:
    market_context = market.market_context
    market_result = market.market_result
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
        "market_refresh_attempted": rows.attempted_market,
        "market_refresh_success": market.market_success,
        "market_refresh_provider": rows.provider_name or ("cycle_rows" if rows.market_row else None),
        "market_refresh_error_class": rows.provider_error_class,
        "market_context_before": context_before,
        "market_context_after": market_context,
        "market_confirmation_before": market_before,
        "market_confirmation_after": market_result.market_confirmation_score,
        "derivatives_refresh_attempted": _playbook_needs_derivatives(row),
        "derivatives_refresh_success": bool(rows.derivatives_row),
        "supply_refresh_attempted": _playbook_needs_supply(row),
        "supply_refresh_success": bool(rows.supply_row),
        "derivative_confirmation_reasons": [
            reason for reason in market_result.reasons
            if reason in {"derivatives_crowding", "funding_heated", "oi_expansion"}
        ],
        "supply_confirmation_reasons": [
            reason for reason in market_result.reasons
            if reason == "supply_pressure"
        ],
        "evidence_refresh_attempted": bool(cfg.source_refresh_enabled and near.evidence_refresh_queries),
        "evidence_refresh_success": evidence.evidence_success,
        "evidence_quality_before": evidence.evidence_before,
        "evidence_quality_after": evidence.evidence_after,
    })
    if evidence.evidence_after is not None:
        components["source_quality"] = max(_float(components.get("source_quality")) or 0.0, evidence.evidence_after)
        components["evidence_quality_score"] = evidence.evidence_after
    return components


def _near_miss_verdict_refresh(
    hypothesis: object,
    near: EventNearMissCandidate,
    rows: _NearMissRefreshRows,
    evidence: _NearMissEvidenceRefresh,
    market: _NearMissMarketRefresh,
    components: Mapping[str, Any],
) -> _NearMissVerdictRefresh:
    verdict = event_opportunity_verdict.evaluate_opportunity(
        impact_path=None,
        market_confirmation=market.market_result,
        evidence_quality=None,
        hypothesis=hypothesis,
        score_components=components,
    )
    upgrade_path = event_opportunity_verdict.explain_upgrade_path(
        verdict=verdict,
        impact_path=None,
        market_confirmation=market.market_result,
        evidence_quality=None,
        components=components,
    )
    upgraded = _level_rank(verdict.opportunity_level) > _level_rank(near.opportunity_level_before)
    score_changed = abs(float(verdict.opportunity_score_final) - near.opportunity_score_before) >= 0.01
    if upgraded:
        return _NearMissVerdictRefresh(
            verdict=verdict,
            upgrade_path=upgrade_path,
            refresh_upgrade_status="upgraded",
            upgrade_reason=f"near_miss_refresh_upgraded:{near.opportunity_level_before}->{verdict.opportunity_level}",
            no_upgrade_reason=None,
        )
    if score_changed and verdict.opportunity_score_final > near.opportunity_score_before:
        return _NearMissVerdictRefresh(
            verdict=verdict,
            upgrade_path=upgrade_path,
            refresh_upgrade_status="improved_score",
            upgrade_reason="near_miss_refresh_improved_score",
            no_upgrade_reason=None,
        )
    if (
        not market.market_success
        and not evidence.evidence_success
        and not rows.derivatives_row
        and not rows.supply_row
    ):
        no_upgrade_reason = "no_new_refresh_evidence"
    elif market.market_context["data_quality"] in {"stale", "unknown", "missing"}:
        no_upgrade_reason = "market_refresh_stale"
    else:
        no_upgrade_reason = "refreshed_evidence_below_upgrade_threshold"
    return _NearMissVerdictRefresh(
        verdict=verdict,
        upgrade_path=upgrade_path,
        refresh_upgrade_status="unchanged",
        upgrade_reason=None,
        no_upgrade_reason=no_upgrade_reason,
    )


def _near_miss_refresh_metadata(
    near: EventNearMissCandidate,
    components: Mapping[str, Any],
    evidence: _NearMissEvidenceRefresh,
    market: _NearMissMarketRefresh,
    verdict_refresh: _NearMissVerdictRefresh,
    *,
    market_before: float | None,
) -> dict[str, Any]:
    market_result = market.market_result
    verdict = verdict_refresh.verdict
    upgrade_path = verdict_refresh.upgrade_path
    return {
        **components,
        "initial_opportunity_score": near.opportunity_score_before,
        "initial_opportunity_level": near.opportunity_level_before,
        "post_refresh_opportunity_score": verdict.opportunity_score_final,
        "post_refresh_opportunity_level": verdict.opportunity_level,
        "post_refresh_market_confirmation_level": market_result.level,
        "post_refresh_market_confirmation_score": market_result.market_confirmation_score,
        "post_refresh_evidence_quality_score": evidence.evidence_after,
        "final_opportunity_score": verdict.opportunity_score_final,
        "final_opportunity_level": verdict.opportunity_level,
        "final_verdict_source": "combined_refresh" if evidence.evidence_success else "market_refresh",
        "final_verdict_reason": (
            verdict_refresh.upgrade_reason
            or verdict_refresh.no_upgrade_reason
            or "targeted_market_refresh_recomputed_verdict"
        ),
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
        "market_context_snapshot": dict(market.market_context["market_snapshot"]),
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
        "refresh_upgrade_status": verdict_refresh.refresh_upgrade_status,
        "refresh_upgrade_reason": verdict_refresh.upgrade_reason,
        "upgrade_reason": verdict_refresh.upgrade_reason,
        "no_upgrade_reason": verdict_refresh.no_upgrade_reason,
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


def _near_miss_updated_hypothesis(
    hypothesis: object,
    metadata: Mapping[str, Any],
    market: _NearMissMarketRefresh,
    verdict_refresh: _NearMissVerdictRefresh,
) -> object:
    market_result = market.market_result
    verdict = verdict_refresh.verdict
    upgrade_path = verdict_refresh.upgrade_path
    current_components = dict(getattr(hypothesis, "score_components", {}) or {})
    current_components.update(metadata)
    replace_kwargs = {
        "market_confirmation_score": market_result.market_confirmation_score,
        "market_confirmation_level": market_result.level,
        "market_confirmation_reasons": market_result.reasons,
        "market_confirmation_warnings": market_result.warnings,
        "market_confirmation_missing_fields": market_result.missing_fields,
        "market_confirmation_summary": market_result.confirmation_summary,
        "market_context_source": market.market_context["source"],
        "market_context_timestamp": market.market_context["timestamp"],
        "market_context_age_seconds": market.market_context["age_seconds"],
        "market_context_age_hours": metadata["market_context_age_hours"],
        "market_context_observed_at": market_result.market_context_observed_at,
        "market_context_freshness_status": market_result.market_context_freshness_status,
        "market_context_freshness_cap_applied": market_result.freshness_cap_applied,
        "market_context_data_quality": market.market_context["data_quality"],
        "market_context_snapshot": dict(market.market_context["market_snapshot"]),
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
        return replace(hypothesis, **replace_kwargs)
    except TypeError:
        return hypothesis


def _near_miss_refreshed_candidate(
    near: EventNearMissCandidate,
    row: Mapping[str, Any],
    rows: _NearMissRefreshRows,
    evidence: _NearMissEvidenceRefresh,
    market: _NearMissMarketRefresh,
    verdict_refresh: _NearMissVerdictRefresh,
    metadata: Mapping[str, Any],
    *,
    market_before: float | None,
    context_before: Mapping[str, Any],
    cfg: EventNearMissConfig,
) -> EventNearMissCandidate:
    market_result = market.market_result
    verdict = verdict_refresh.verdict
    return replace(
        near,
        opportunity_level_after=verdict.opportunity_level,
        opportunity_score_after=verdict.opportunity_score_final,
        market_refresh_attempted=rows.attempted_market,
        market_refresh_success=market.market_success,
        market_refresh_provider=metadata["market_refresh_provider"],
        market_refresh_error_class=rows.provider_error_class,
        market_context_source=market.market_context["source"],
        market_context_age_seconds=market.market_context["age_seconds"],
        market_context_data_quality=market.market_context["data_quality"],
        market_context_before=context_before,
        market_context_after=market.market_context,
        market_confirmation_before=market_before,
        market_confirmation_after=market_result.market_confirmation_score,
        refresh_upgrade_status=verdict_refresh.refresh_upgrade_status,
        derivatives_refresh_attempted=_playbook_needs_derivatives(row),
        derivatives_refresh_success=bool(rows.derivatives_row),
        supply_refresh_attempted=_playbook_needs_supply(row),
        supply_refresh_success=bool(rows.supply_row),
        derivative_confirmation_reasons=tuple(metadata["derivative_confirmation_reasons"]),
        supply_confirmation_reasons=tuple(metadata["supply_confirmation_reasons"]),
        evidence_refresh_attempted=bool(cfg.source_refresh_enabled and near.evidence_refresh_queries),
        evidence_refresh_success=evidence.evidence_success,
        evidence_quality_before=evidence.evidence_before,
        evidence_quality_after=evidence.evidence_after,
        upgrade_reason=verdict_refresh.upgrade_reason,
        no_upgrade_reason=verdict_refresh.no_upgrade_reason,
        final_route_after=_route_for_level(verdict.opportunity_level),
        warnings=tuple(dict.fromkeys((*near.warnings, *rows.provider_warnings, *market_result.warnings))),
    )
