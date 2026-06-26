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

from . import (
    event_alpha_router,
    event_alpha_quality_fields,
    event_market_confirmation,
    event_opportunity_verdict,
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
class EventNearMissCandidate:
    near_miss_id: str
    symbol: str
    coin_id: str
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
    market_context_source: str | None = None
    market_context_age_seconds: float | None = None
    market_context_data_quality: str | None = None
    market_confirmation_before: float | None = None
    market_confirmation_after: float | None = None
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
    out: list[EventNearMissCandidate] = []
    for item in rows:
        row = _row_from_object(item)
        if not row:
            continue
        identity = _row_identity(row)
        route = _lookup_route(route_by_key, row)
        candidate = _candidate_from_row(row, route=route, cfg=cfg)
        if candidate is None:
            continue
        out.append(candidate)
    out.sort(key=lambda item: item.priority_score, reverse=True)
    return tuple(out[: max(1, int(cfg.max_candidates or 1))])


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
    rows.append(f"near_misses: {len(items)}")
    if not items:
        rows.append("")
        rows.append("No near-miss candidates found.")
        rows.append("Research-only report; no notifications, trades, paper rows, live RSI rows, or triggers were created.")
        return "\n".join(rows)
    rows.append("")
    for item in items:
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
            f"source={item.market_context_source or 'none'} "
            f"score={item.market_confirmation_before if item.market_confirmation_before is not None else 'n/a'}"
            f"->{item.market_confirmation_after if item.market_confirmation_after is not None else 'n/a'} "
            f"age={item.market_context_age_seconds if item.market_context_age_seconds is not None else 'n/a'} "
            f"quality={item.market_context_data_quality or 'unknown'}"
        )
        if item.derivatives_refresh_attempted or item.supply_refresh_attempted:
            rows.append(
                "  enrichment_refresh: "
                f"derivatives={str(item.derivatives_refresh_success).lower()} "
                f"supply={str(item.supply_refresh_success).lower()}"
            )
        if item.evidence_refresh_queries:
            rows.append("  evidence_queries: " + "; ".join(item.evidence_refresh_queries))
        rows.append(f"  outcome: {item.upgrade_reason or item.no_upgrade_reason or 'pending_refresh'}")
        if item.warnings:
            rows.append("  warnings: " + "; ".join(item.warnings))
    rows.append("")
    rows.append("Research-only report; no notifications, trades, paper rows, live RSI rows, or triggers were created.")
    return "\n".join(rows)


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
    market_row = _find_asset_row(market_rows, symbol=symbol, coin_id=coin_id)
    provider_warnings: list[str] = []
    attempted_market = market_refresh_allowed
    if market_refresh_allowed and not market_row and targeted_market_provider is not None and coin_id:
        try:
            fetched = targeted_market_provider.fetch_market_rows((coin_id,), max_assets=1)  # type: ignore[attr-defined]
            fetched_rows, fetched_warnings = _normalize_provider_rows(fetched)
            provider_warnings.extend(fetched_warnings)
            market_row = _find_asset_row(fetched_rows, symbol=symbol, coin_id=coin_id)
        except Exception as exc:  # noqa: BLE001 - fail-soft research refresh
            provider_warnings.append(f"targeted_market_refresh_failed:{type(exc).__name__}")
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
            evidence_refresh_attempted=bool(cfg.source_refresh_enabled and near.evidence_refresh_queries),
            evidence_refresh_success=False,
            no_upgrade_reason="no_new_refresh_evidence",
            warnings=tuple(dict.fromkeys((*near.warnings, *provider_warnings))),
        ), tuple(provider_warnings)
    market_context = _market_context(market_row, source="near_miss_market_refresh", now=now, cfg=cfg)
    market_input = event_market_confirmation.EventMarketConfirmationInput(
        market_snapshot=market_context["market_snapshot"],
        derivatives_snapshot=derivatives_row,
        supply_snapshot=supply_row,
        playbook_type=str(row.get("playbook_hint") or row.get("playbook_type") or ""),
        impact_category=str(row.get("impact_category") or ""),
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
        "market_context_data_quality": market_context["data_quality"],
        "market_refresh_attempted": attempted_market,
        "market_refresh_success": market_success,
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
        upgrade_reason = f"near_miss_refresh_upgraded:{near.opportunity_level_before}->{verdict.opportunity_level}"
    elif score_changed and verdict.opportunity_score_final > near.opportunity_score_before:
        upgrade_reason = "near_miss_refresh_improved_score"
    else:
        if not market_success and not evidence_success and not derivatives_row and not supply_row:
            no_upgrade_reason = "no_new_refresh_evidence"
        elif market_context["data_quality"] == "stale":
            no_upgrade_reason = "market_refresh_stale"
        else:
            no_upgrade_reason = "refreshed_evidence_below_upgrade_threshold"
    metadata = {
        **components,
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
        "market_context_snapshot": dict(market_context["market_snapshot"]),
        "near_miss_id": near.near_miss_id,
        "opportunity_level_before": near.opportunity_level_before,
        "opportunity_level_after": verdict.opportunity_level,
        "opportunity_score_before": near.opportunity_score_before,
        "opportunity_score_after": verdict.opportunity_score_final,
        "upgrade_reason": upgrade_reason,
        "no_upgrade_reason": no_upgrade_reason,
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
        market_context_source=market_context["source"],
        market_context_age_seconds=market_context["age_seconds"],
        market_context_data_quality=market_context["data_quality"],
        market_confirmation_before=market_before,
        market_confirmation_after=market_result.market_confirmation_score,
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
    "upgrade_reason",
    "no_upgrade_reason",
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
    symbol = str(row.get("validated_symbol") or row.get("symbol") or "").strip().upper()
    coin_id = str(row.get("validated_coin_id") or row.get("coin_id") or "").strip()
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
        row.get("warnings"),
        row.get("rejection_reasons"),
    )).casefold()
    if "source_noise" in text or "ticker_collision" in text or "ticker_word_collision" in text:
        return None
    if str(quality.get("impact_path_type") or "") == "generic_cooccurrence_only":
        return None
    if str(quality.get("candidate_role") or "") in {"source_noise", "ticker_word_collision", "generic_mention"}:
        return None
    score = _float(quality.get("opportunity_score_final")) or 0.0
    level = str(quality.get("opportunity_level") or "local_only")
    final_route = _final_route_for_route(route) if route is not None else str(row.get("final_route_after_quality_gate") or row.get("route") or "")
    alertable = event_alpha_router.route_value_is_alertable(final_route) if final_route else False
    missing = _missing_evidence(quality, row)
    near_digest = 0 <= cfg.digest_threshold - score <= cfg.near_threshold_points
    near_watchlist = 0 <= cfg.watchlist_threshold - score <= cfg.near_threshold_points
    route_inconsistent = level in {"validated_digest", "watchlist", "high_priority"} and not alertable
    blocked_by_refreshable = any(_refreshable_missing_reason(value) for value in missing)
    if not (near_digest or near_watchlist or route_inconsistent or blocked_by_refreshable):
        return None
    if level == "local_only" and score < cfg.digest_threshold - cfg.near_threshold_points and not blocked_by_refreshable:
        return None
    priority = _priority_score(score, level, missing, route_inconsistent=route_inconsistent)
    queries = _evidence_refresh_queries(row, max_queries=cfg.max_source_queries)
    return EventNearMissCandidate(
        near_miss_id=_near_miss_id(row, symbol=symbol, coin_id=coin_id),
        symbol=symbol,
        coin_id=coin_id,
        hypothesis_id=_optional_str(row.get("hypothesis_id")),
        incident_id=_optional_str(row.get("incident_id")),
        opportunity_level_before=level,
        opportunity_score_before=score,
        final_route_before=final_route or None,
        missing_evidence=missing,
        recommended_refresh_actions=_recommended_refresh_actions(missing, row),
        priority_score=priority,
        market_confirmation_before=_float(quality.get("market_confirmation_score")),
        evidence_quality_before=_float(quality.get("evidence_quality_score")),
        evidence_refresh_queries=queries,
    )


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


def _recommended_refresh_actions(missing: Iterable[str], row: Mapping[str, Any]) -> tuple[str, ...]:
    actions: list[str] = []
    if any("market" in reason or "volume" in reason or "liquidity" in reason for reason in missing):
        actions.append("targeted_market_refresh")
    if _playbook_needs_derivatives(row):
        actions.append("targeted_derivatives_refresh")
    if _playbook_needs_supply(row):
        actions.append("targeted_supply_refresh")
    if any("source" in reason or "evidence" in reason or "impact_path" in reason for reason in missing):
        actions.append("targeted_evidence_refresh")
    return tuple(dict.fromkeys(actions or ("operator_review",)))


def _refreshable_missing_reason(reason: str) -> bool:
    text = reason.casefold()
    return any(part in text for part in ("market", "volume", "liquidity", "source", "evidence", "impact_path", "derivatives", "supply"))


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
    timestamp = row.get("timestamp") or row.get("market_timestamp") or row.get("observed_at") or row.get("fetched_at")
    age = _age_seconds(timestamp, now)
    quality = "fresh" if age is None or age <= cfg.stale_after_seconds else "stale"
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
    symbol = str(row.get("validated_symbol") or row.get("symbol") or "").strip().upper()
    coin_id = str(row.get("validated_coin_id") or row.get("coin_id") or "").strip()
    if symbol:
        keys.append(f"symbol:{symbol}")
    if coin_id:
        keys.append(f"coin_id:{coin_id}")
    return tuple(dict.fromkeys(keys))


def _row_identity(row: Mapping[str, Any]) -> str:
    return "|".join(_identity_keys(row)) or "unknown"


def _near_miss_id(row: Mapping[str, Any], *, symbol: str, coin_id: str) -> str:
    base = str(row.get("hypothesis_id") or row.get("event_id") or row.get("key") or coin_id or symbol)
    return "near:" + base.replace(" ", "_")[:96]


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
