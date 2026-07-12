"""Event Alpha near-miss candidate builders."""

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
from .models import *  # noqa: F403 - split modules share historical model names


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


def near_miss_metadata_for_row(
    row: Mapping[str, Any] | object,
    *,
    cfg: EventNearMissConfig | None = None,
    now: datetime | None = None,
) -> EventNearMissCandidate | None:
    return _candidate_from_row(
        _row_from_object(row),
        route=None,
        cfg=cfg or EventNearMissConfig(),
        now=now,
    )


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


@dataclass(frozen=True)
class _NearMissCandidateState:
    quality: Mapping[str, Any]
    symbol: str
    coin_id: str
    score: float
    level: str
    final_route: str
    alertable: bool
    missing: tuple[str, ...]
    route_inconsistent: bool


def _candidate_from_row(
    row: Mapping[str, Any],
    *,
    route: Mapping[str, Any] | None,
    cfg: EventNearMissConfig,
    now: datetime | None = None,
) -> EventNearMissCandidate | None:
    state = _near_miss_candidate_state(row, route=route, cfg=cfg)
    if state is None:
        return None
    pack = event_source_packs.source_pack_for_playbook(
        str(row.get("playbook_type") or row.get("latest_effective_playbook_type") or state.quality.get("playbook_type") or ""),
        impact_path_type=str(state.quality.get("impact_path_type") or row.get("impact_path_type") or ""),
        impact_category=str(row.get("impact_category") or state.quality.get("impact_category") or ""),
    )
    provider_status = str(row.get("provider_coverage_status") or state.quality.get("provider_coverage_status") or "")
    source_assessment = event_source_registry.assess_source(
        row,
        symbol=state.symbol,
        coin_id=state.coin_id,
        playbook_type=str(row.get("playbook_type") or state.quality.get("playbook_type") or ""),
        provider_coverage_status=provider_status or None,
    )
    source_gap = event_source_registry.coverage_gap_reason(
        source_assessment.provider,
        source_assessment.provider_coverage_status,
    )
    missing = state.missing
    if source_gap:
        missing = tuple(dict.fromkeys((*missing, "needs_source_coverage", source_gap)))
    pack_eval = event_source_packs.evaluate_pack_evidence({**row, **source_assessment.to_metadata()}, pack=pack)
    pack_missing = tuple(str(item) for item in pack_eval.get("source_pack_missing_evidence") or ())
    if pack_missing:
        missing = tuple(dict.fromkeys((*missing, *pack_missing)))
    priority = _priority_score(state.score, state.level, missing, route_inconsistent=state.route_inconsistent)
    queries = _evidence_refresh_queries(row, max_queries=cfg.max_source_queries)
    planner_request = event_llm_evidence_planner.request_from_row(
        {
            **dict(row),
            **source_assessment.to_metadata(),
            "source_pack": pack.name,
            "source_pack_missing_evidence": pack_missing,
            "opportunity_level": state.level,
            "opportunity_score_final": state.score,
        },
        missing_evidence=missing,
        source_pack=pack.name,
    )
    planner_result = event_llm_evidence_planner.plan_evidence(planner_request)
    plan_metadata = planner_result.to_metadata()
    plan_selected = planner_result.selected and event_llm_evidence_planner.should_plan_evidence({
            **dict(row),
            "opportunity_level": state.level,
            "opportunity_score_final": state.score,
            "missing_requirements": missing,
            "source_pack": pack.name,
    })
    return EventNearMissCandidate(
        near_miss_id=_near_miss_id(row, symbol=state.symbol, coin_id=state.coin_id),
        refresh_id=_refresh_id(row, symbol=state.symbol, coin_id=state.coin_id),
        symbol=state.symbol,
        coin_id=state.coin_id,
        core_opportunity_id=_core_opportunity_id_for_row(row),
        hypothesis_id=_optional_str(row.get("hypothesis_id")),
        incident_id=_optional_str(row.get("incident_id")),
        opportunity_level_before=state.level,
        opportunity_score_before=state.score,
        final_route_before=state.final_route or None,
        missing_evidence=missing,
        recommended_refresh_actions=_recommended_refresh_actions(missing, row, pack=pack),
        priority_score=priority,
        market_context_before=_market_context(
            row,
            source=str(row.get("market_context_source") or "existing"),
            now=now or datetime.now(timezone.utc),
            cfg=cfg,
        ),
        market_context_source=str(row.get("market_context_source") or state.quality.get("market_context_source") or "") or None,
        market_context_age_seconds=_float(row.get("market_context_age_seconds") or state.quality.get("market_context_age_seconds")),
        market_context_data_quality=str(row.get("market_context_freshness_status") or state.quality.get("market_context_freshness_status") or row.get("market_context_data_quality") or state.quality.get("market_context_data_quality") or "") or None,
        market_confirmation_before=_float(state.quality.get("market_confirmation_score")),
        evidence_quality_before=_float(state.quality.get("evidence_quality_score")),
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


def _near_miss_candidate_state(
    row: Mapping[str, Any],
    *,
    route: Mapping[str, Any] | None,
    cfg: EventNearMissConfig,
) -> _NearMissCandidateState | None:
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
    if _row_is_promoted_core_opportunity(row, level=level, final_route=final_route, alertable=alertable):
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
    if _near_miss_has_fresh_context(
        level=level,
        near_watchlist=near_watchlist,
        blocked_by_refreshable=blocked_by_refreshable,
        blocked_by_market_refresh=blocked_by_market_refresh,
        route_inconsistent=route_inconsistent,
    ):
        return None
    if alertable and not (blocked_by_refreshable or near_watchlist or route_inconsistent):
        return None
    if not (near_digest or near_watchlist or route_inconsistent or blocked_by_refreshable):
        return None
    if level == "local_only" and score < cfg.digest_threshold - cfg.near_threshold_points and not blocked_by_refreshable:
        return None
    return _NearMissCandidateState(
        quality=quality,
        symbol=symbol,
        coin_id=coin_id,
        score=score,
        level=level,
        final_route=final_route,
        alertable=alertable,
        missing=missing,
        route_inconsistent=route_inconsistent,
    )


def _row_is_promoted_core_opportunity(
    row: Mapping[str, Any],
    *,
    level: str,
    final_route: str,
    alertable: bool,
) -> bool:
    return str(row.get("row_type") or "") == "event_core_opportunity" and (
        alertable
        or final_route == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value
        or level in {"validated_digest", "watchlist", "high_priority"}
    )


def _near_miss_has_fresh_context(
    *,
    level: str,
    near_watchlist: bool,
    blocked_by_refreshable: bool,
    blocked_by_market_refresh: bool,
    route_inconsistent: bool,
) -> bool:
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
    return promoted_with_fresh_context or digest_with_fresh_context


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
