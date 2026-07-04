"""Evidence acquisition execution helpers."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol

from .... import (
    event_evidence_quality,
    event_llm_evidence_planner,
)
from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent
from ....event_resolver import clean_text
from ...providers import source_packs as event_source_packs
from ...providers import source_registry as event_source_registry
from .. import catalyst_search as event_catalyst_search
from .. import core_opportunities as event_core_opportunities
from .. import impact_hypotheses as event_impact_hypotheses
from .. import source_enrichment as event_source_enrichment
from .models import *  # noqa: F403 - split modules share legacy model names


def run_evidence_acquisition(
    hypotheses: Iterable[object],
    *,
    near_misses: Iterable[object] = (),
    provider: EvidenceSearchProvider | None = None,
    providers_by_hint: Mapping[str, EvidenceSearchProvider | None] | None = None,
    cfg: EvidenceAcquisitionConfig | None = None,
    now: datetime | None = None,
    run_context: Mapping[str, Any] | None = None,
) -> EventEvidenceAcquisitionRunResult:
    """Execute bounded source-pack acquisition and return updated hypotheses."""
    cfg = cfg or EvidenceAcquisitionConfig()
    hypothesis_rows = tuple(hypotheses)
    observed = _as_utc(now or datetime.now(timezone.utc))
    if not cfg.enabled:
        return EventEvidenceAcquisitionRunResult(
            hypotheses=hypothesis_rows,
            results=(),
            path=cfg.artifact_path,
            status="disabled",
            warnings=(),
        )

    requests = _select_requests(
        hypothesis_rows,
        near_misses=near_misses,
        max_candidates=cfg.max_candidates,
    )
    if not requests:
        return EventEvidenceAcquisitionRunResult(
            hypotheses=hypothesis_rows,
            results=(),
            path=cfg.artifact_path,
            status="no_candidates",
            warnings=(),
        )

    results: list[EvidenceAcquisitionResult] = []
    accepted_raw_by_hypothesis: dict[str, list[RawDiscoveredEvent]] = {}
    remaining_queries = max(0, int(cfg.max_queries or 0))
    for request in requests:
        if remaining_queries <= 0:
            results.append(_budget_skipped_result(request))
            continue
        query_plan = request.query_plan[:remaining_queries]
        remaining_queries -= len(query_plan)
        result, accepted_raw = _execute_request(
            request,
            query_plan=query_plan,
            provider=provider,
            providers_by_hint=providers_by_hint or {},
            cfg=cfg,
            now=observed,
        )
        results.append(result)
        if accepted_raw and request.hypothesis_id:
            accepted_raw_by_hypothesis.setdefault(request.hypothesis_id, []).extend(accepted_raw)

    updated_hypotheses = tuple(hypothesis_rows)
    if accepted_raw_by_hypothesis:
        all_raw = tuple(raw for rows in accepted_raw_by_hypothesis.values() for raw in rows)
        updated_hypotheses = event_impact_hypotheses.validate_hypotheses_with_raw_events(
            updated_hypotheses,
            all_raw,
        )
    results_by_hypothesis = {result.hypothesis_id: result for result in results if result.hypothesis_id}
    updated_hypotheses = tuple(
        _attach_result_to_hypothesis(item, results_by_hypothesis.get(str(getattr(item, "hypothesis_id", "") or "")))
        for item in updated_hypotheses
    )
    finalized = tuple(
        _finalize_result(result, before=_find_hypothesis(hypothesis_rows, result.hypothesis_id), after=_find_hypothesis(updated_hypotheses, result.hypothesis_id))
        for result in results
    )
    updated_hypotheses = tuple(
        _attach_result_to_hypothesis(item, next((r for r in finalized if r.hypothesis_id == str(getattr(item, "hypothesis_id", "") or "")), None))
        for item in updated_hypotheses
    )
    rows_written = 0
    warnings: list[str] = []
    if cfg.artifact_path is not None:
        try:
            rows_written = write_acquisition_results(
                cfg.artifact_path,
                finalized,
                run_context=run_context or {},
                now=observed,
            )
        except Exception as exc:  # noqa: BLE001 - artifact writes must fail soft.
            warnings.append(f"evidence acquisition artifact write failed: {type(exc).__name__}: {exc}")
    return EventEvidenceAcquisitionRunResult(
        hypotheses=updated_hypotheses,
        results=finalized,
        path=cfg.artifact_path,
        rows_written=rows_written,
        status=_run_result_status(finalized, artifact_warnings=warnings),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _select_requests(
    hypotheses: tuple[object, ...],
    *,
    near_misses: Iterable[object],
    max_candidates: int,
) -> tuple[EvidenceAcquisitionRequest, ...]:
    rows_by_id = {str(getattr(item, "hypothesis_id", "") or ""): item for item in hypotheses}
    requests: list[EvidenceAcquisitionRequest] = []
    seen: set[str] = set()
    for near in near_misses:
        request = _request_from_near_miss(near, rows_by_id)
        key = _request_dedupe_key(request) if request else None
        if request and key not in seen:
            requests.append(request)
            seen.add(key or request.acquisition_id)
    for hypothesis in hypotheses:
        if len(requests) >= max(1, int(max_candidates or 1)):
            break
        row = _row_from_object(hypothesis)
        if not event_llm_evidence_planner.should_plan_evidence(row):
            continue
        request = _request_from_row(row)
        key = _request_dedupe_key(request) if request else None
        if request and key not in seen:
            requests.append(request)
            seen.add(key or request.acquisition_id)
    return tuple(requests[: max(1, int(max_candidates or 1))])


def _request_from_near_miss(
    near: object,
    hypotheses_by_id: Mapping[str, object],
) -> EvidenceAcquisitionRequest | None:
    row = _row_from_object(near)
    hypothesis_id = str(row.get("hypothesis_id") or "").strip()
    hypothesis = hypotheses_by_id.get(hypothesis_id)
    source = _row_from_object(hypothesis) if hypothesis is not None else row
    merged = _merge_preserving_non_empty(source, row)
    plan = row.get("evidence_acquisition_plan") if isinstance(row.get("evidence_acquisition_plan"), Mapping) else None
    return _request_from_row(merged, plan=plan)


def _request_from_row(
    row: Mapping[str, Any],
    *,
    plan: Mapping[str, Any] | None = None,
) -> EvidenceAcquisitionRequest | None:
    row_for_request = dict(row)
    core_id = _core_opportunity_id_for_row(row_for_request)
    if core_id:
        row_for_request.setdefault("core_opportunity_id", core_id)
    request = event_llm_evidence_planner.request_from_row(
        row_for_request,
        source_pack=str(row_for_request.get("source_pack") or ""),
    )
    if not (str(request.symbol or "").strip() or str(request.coin_id or "").strip()):
        return None
    planner = event_llm_evidence_planner.plan_evidence(request)
    query_plan = _queries_from_plan(plan) if plan else planner.query_plan
    query_plan = _normalize_query_plan_for_request(query_plan, request)
    if not query_plan:
        return None
    hypothesis_id = str(row_for_request.get("hypothesis_id") or request.opportunity_id or "").strip() or None
    incident_id = str(row_for_request.get("incident_id") or "").strip() or None
    source_pack = str(row_for_request.get("source_pack") or planner.source_pack or request.source_pack or "market_anomaly_pack")
    return EvidenceAcquisitionRequest(
        acquisition_id=_acquisition_id(core_id or request.opportunity_id, hypothesis_id, source_pack),
        opportunity_id=request.opportunity_id,
        core_opportunity_id=core_id,
        hypothesis_id=hypothesis_id,
        incident_id=incident_id,
        symbol=request.symbol,
        coin_id=request.coin_id,
        event_name=request.event_name,
        external_asset=request.external_asset,
        source_pack=source_pack,
        opportunity_score_before=_float(row.get("opportunity_score_final")) or request.score,
        opportunity_level_before=str(row.get("opportunity_level") or request.opportunity_level),
        evidence_quality_before=_float(row.get("evidence_quality_score")),
        impact_path_validation_before=str(row.get("impact_path_type") or row.get("validation_stage") or "") or None,
        query_plan=query_plan,
        provider_coverage_status=str(row.get("provider_coverage_status") or event_source_registry.ProviderCoverageStatus.COMPLETE.value),
        row=row_for_request,
    )


def _execute_request(
    request: EvidenceAcquisitionRequest,
    *,
    query_plan: tuple[event_llm_evidence_planner.EvidencePlanQuery, ...],
    provider: EvidenceSearchProvider | None,
    providers_by_hint: Mapping[str, EvidenceSearchProvider | None],
    cfg: EvidenceAcquisitionConfig,
    now: datetime,
) -> tuple[EvidenceAcquisitionResult, tuple[RawDiscoveredEvent, ...]]:
    query_results: list[EvidenceAcquisitionQueryResult] = []
    accepted_evidence: list[Mapping[str, Any]] = []
    rejected_evidence: list[Mapping[str, Any]] = []
    accepted_raw: list[RawDiscoveredEvent] = []
    failures: list[str] = []
    providers_used: list[str] = []
    for rank, plan_query in enumerate(query_plan, start=1):
        query_result, query_accepted, query_rejected, query_raw, provider_used = _execute_plan_query(
            request,
            plan_query=plan_query,
            rank=rank,
            provider=provider,
            providers_by_hint=providers_by_hint,
            cfg=cfg,
            now=now,
            failures=failures,
        )
        query_results.append(query_result)
        accepted_evidence.extend(query_accepted)
        rejected_evidence.extend(query_rejected)
        accepted_raw.extend(query_raw)
        if provider_used:
            providers_used.append(provider_used)
    final_status = _aggregate_status(query_results)
    result = EvidenceAcquisitionResult(
        acquisition_id=request.acquisition_id,
        opportunity_id=request.opportunity_id,
        core_opportunity_id=request.core_opportunity_id,
        hypothesis_id=request.hypothesis_id,
        incident_id=request.incident_id,
        source_pack=request.source_pack,
        status=final_status,
        symbol=request.symbol,
        coin_id=request.coin_id,
        event_name=request.event_name,
        external_asset=request.external_asset,
        queries_executed=len(query_plan),
        providers_used=tuple(dict.fromkeys(providers_used)),
        provider_failures=tuple(dict.fromkeys(failures)),
        accepted_evidence=tuple(accepted_evidence[:8]),
        rejected_evidence=tuple(rejected_evidence[:8]),
        query_results=tuple(query_results),
        acquisition_evidence_status=_evidence_status(final_status, accepted_evidence=accepted_evidence, rejected_evidence=rejected_evidence),
        evidence_quality_before=request.evidence_quality_before,
        evidence_quality_after=max(
            [request.evidence_quality_before or 0.0, *(_float(item.get("evidence_quality_score")) or 0.0 for item in accepted_evidence)]
        ) if accepted_evidence else request.evidence_quality_before,
        impact_path_validation_before=request.impact_path_validation_before,
        impact_path_validation_after=request.impact_path_validation_before,
        opportunity_score_before=request.opportunity_score_before,
        opportunity_score_after=request.opportunity_score_before,
        opportunity_level_before=request.opportunity_level_before,
        opportunity_level_after=request.opportunity_level_before,
        initial_opportunity_score=request.opportunity_score_before,
        initial_opportunity_level=request.opportunity_level_before,
        post_refresh_opportunity_score=request.opportunity_score_before,
        post_refresh_opportunity_level=request.opportunity_level_before,
        final_opportunity_score=request.opportunity_score_before,
        final_opportunity_level=request.opportunity_level_before,
        final_verdict_source="initial",
        final_verdict_reason=None if accepted_evidence else _no_upgrade_reason(final_status, failures),
        acquisition_upgrade_status="unchanged",
        final_upgrade_status="unchanged",
        no_upgrade_reason=None if accepted_evidence else _no_upgrade_reason(final_status, failures),
        warnings=tuple(dict.fromkeys(
            warning
            for query_result in query_results
            for warning in (*query_result.warnings, *query_result.provider_failures)
            if warning
        )),
    )
    return result, tuple(accepted_raw)


def _execute_plan_query(
    request: EvidenceAcquisitionRequest,
    *,
    plan_query: event_llm_evidence_planner.EvidencePlanQuery,
    rank: int,
    provider: EvidenceSearchProvider | None,
    providers_by_hint: Mapping[str, EvidenceSearchProvider | None],
    cfg: EvidenceAcquisitionConfig,
    now: datetime,
    failures: list[str],
) -> tuple[EvidenceAcquisitionQueryResult, tuple[Mapping[str, Any], ...], tuple[Mapping[str, Any], ...], tuple[RawDiscoveredEvent, ...], str | None]:
    search_query = event_catalyst_search.SearchQuery(
        anomaly_raw_id=request.hypothesis_id or request.opportunity_id,
        query=plan_query.query,
        symbol=request.symbol,
        rank=rank,
        query_type=plan_query.purpose,
        coin_id=request.coin_id,
        project_name=request.coin_id.replace("-", " ") if request.coin_id else None,
        aliases=tuple(dict.fromkeys(
            value
            for value in (request.coin_id, request.coin_id.replace("-", " ") if request.coin_id else "", request.symbol)
            if value
        )),
    )
    selected_provider = _provider_for_hint(plan_query.provider_hint, providers_by_hint, provider)
    provider_name = getattr(selected_provider, "name", None) if selected_provider is not None else None
    if selected_provider is None:
        failure = f"{plan_query.provider_hint}:not_configured"
        failures.append(failure)
        return (
            EvidenceAcquisitionQueryResult(
                query=plan_query.query,
                provider_hint=plan_query.provider_hint,
                provider_used=None,
                purpose=plan_query.purpose,
                status=EvidenceAcquisitionStatus.PROVIDER_UNAVAILABLE.value,
                provider_failures=(failure,),
                evidence_absence_is_meaningful=_absence_meaningful_for_hint(plan_query.provider_hint, request.provider_coverage_status),
            ),
            (),
            (),
            (),
            None,
        )
    if cfg.fixture_only and "fixture" not in str(provider_name or "").casefold():
        failure = f"{plan_query.provider_hint}:fixture_only_provider_skipped"
        failures.append(failure)
        return (
            EvidenceAcquisitionQueryResult(
                query=plan_query.query,
                provider_hint=plan_query.provider_hint,
                provider_used=provider_name,
                purpose=plan_query.purpose,
                status=EvidenceAcquisitionStatus.SKIPPED_CONFIG.value,
                provider_failures=(failure,),
            ),
            (),
            (),
            (),
            None,
        )
    try:
        search_result = selected_provider.search(
            (search_query,),
            max_results_per_query=cfg.max_results_per_query,
            now=now,
        )
    except Exception as exc:  # noqa: BLE001 - acquisition must fail soft.
        status = EvidenceAcquisitionStatus.PROVIDER_BACKOFF.value if "backoff" in str(exc).casefold() else EvidenceAcquisitionStatus.FAILED_SOFT.value
        failure = f"{plan_query.provider_hint}:{type(exc).__name__}"
        failures.append(failure)
        return (
            EvidenceAcquisitionQueryResult(
                query=plan_query.query,
                provider_hint=plan_query.provider_hint,
                provider_used=provider_name,
                purpose=plan_query.purpose,
                status=status,
                provider_failures=(failure,),
                warnings=(str(exc),),
            ),
            (),
            (),
            (),
            str(provider_name or plan_query.provider_hint),
        )
    return _query_result_from_search_result(
        request,
        plan_query=plan_query,
        search_query=search_query,
        search_result=search_result,
        provider_name=provider_name,
        failures=failures,
    ) + (str(provider_name or plan_query.provider_hint),)


def _query_result_from_search_result(
    request: EvidenceAcquisitionRequest,
    *,
    plan_query: event_llm_evidence_planner.EvidencePlanQuery,
    search_query: event_catalyst_search.SearchQuery,
    search_result: object,
    provider_name: str | None,
    failures: list[str],
) -> tuple[EvidenceAcquisitionQueryResult, tuple[Mapping[str, Any], ...], tuple[Mapping[str, Any], ...], tuple[RawDiscoveredEvent, ...]]:
    query_accepted: list[Mapping[str, Any]] = []
    query_rejected: list[Mapping[str, Any]] = []
    accepted_raw: list[RawDiscoveredEvent] = []
    warnings = tuple(str(item) for item in getattr(search_result, "warnings", ()) or () if str(item))
    result_events = tuple(getattr(search_result, "result_events", ()) or ())
    status = _query_status_from_search_warnings(plan_query, warnings, result_events, failures)
    for result_event in result_events:
        raw = getattr(result_event, "raw_event", None)
        if raw is None:
            continue
        accepted, sample = _validate_raw_result(raw, search_query, request, plan_query)
        if accepted:
            query_accepted.append(sample)
            accepted_raw.append(_annotate_accepted_raw(raw, request, sample))
        else:
            query_rejected.append(sample)
    if query_accepted:
        status = EvidenceAcquisitionStatus.ACCEPTED_EVIDENCE_FOUND.value
    elif query_rejected:
        status = EvidenceAcquisitionStatus.REJECTED_RESULTS_ONLY.value
    return (
        EvidenceAcquisitionQueryResult(
            query=plan_query.query,
            provider_hint=plan_query.provider_hint,
            provider_used=provider_name,
            purpose=plan_query.purpose,
            status=status,
            results_seen=len(result_events),
            accepted_evidence=tuple(query_accepted),
            rejected_evidence=tuple(query_rejected[:5]),
            provider_failures=tuple(failures[-3:]),
            warnings=warnings,
            evidence_absence_is_meaningful=_absence_meaningful_for_hint(plan_query.provider_hint, request.provider_coverage_status),
        ),
        tuple(query_accepted),
        tuple(query_rejected),
        tuple(accepted_raw),
    )


def _query_status_from_search_warnings(
    plan_query: event_llm_evidence_planner.EvidencePlanQuery,
    warnings: tuple[str, ...],
    result_events: tuple[object, ...],
    failures: list[str],
) -> str:
    if _provider_unavailable_from_warnings(warnings):
        failures.extend(f"{plan_query.provider_hint}:{warning}" for warning in warnings[:3])
        return EvidenceAcquisitionStatus.PROVIDER_UNAVAILABLE.value
    if _provider_backoff_from_warnings(warnings):
        failures.extend(f"{plan_query.provider_hint}:{warning}" for warning in warnings[:3])
        return EvidenceAcquisitionStatus.PROVIDER_BACKOFF.value
    if not result_events:
        return EvidenceAcquisitionStatus.NO_RESULTS.value
    return EvidenceAcquisitionStatus.EXECUTED.value


def _validate_raw_result(
    raw: RawDiscoveredEvent,
    query: event_catalyst_search.SearchQuery,
    request: EvidenceAcquisitionRequest,
    plan_query: event_llm_evidence_planner.EvidencePlanQuery,
) -> tuple[bool, dict[str, Any]]:
    raw_map = _raw_mapping(raw)
    text = clean_text(" ".join(str(value or "") for value in (
        raw.title,
        raw.body,
        raw.source_url,
        raw_map.get("description"),
        raw_map.get("source_origin"),
        raw_map.get("event_name"),
    )))
    pack = event_source_packs.get_source_pack(request.source_pack)
    assessment = event_source_registry.assess_source(
        raw_map,
        symbol=request.symbol,
        coin_id=request.coin_id,
        playbook_type=str((request.row or {}).get("playbook_type") or ""),
        mission=event_source_registry.SourceMission.IMPACT_PATH_VALIDATION.value,
        provider_coverage_status=request.provider_coverage_status,
    )
    pack_eval = event_source_packs.evaluate_pack_evidence(
        {
            **raw_map,
            "symbol": request.symbol,
            "coin_id": request.coin_id,
            "validated_symbol": request.symbol,
            "validated_coin_id": request.coin_id,
            "playbook_type": (request.row or {}).get("playbook_type"),
            "impact_path_type": (request.row or {}).get("impact_path_type"),
            "impact_category": (request.row or {}).get("impact_category"),
            "provider_coverage_status": request.provider_coverage_status,
            "market_confirmation_score": (request.row or {}).get("market_confirmation_score"),
            "score_components": (request.row or {}).get("score_components"),
        },
        pack=pack,
    )
    quality = event_evidence_quality.evaluate_evidence_quality(
        raw,
        symbol=request.symbol,
        coin_id=request.coin_id,
    )
    reject_reasons, official_exchange_identity_ok, currency_tags = _raw_result_reject_reasons(
        raw,
        raw_map=raw_map,
        text=text,
        query=query,
        request=request,
        plan_query=plan_query,
        pack=pack,
        assessment=assessment,
        pack_eval=pack_eval,
        quality=quality,
    )
    reason_codes = _raw_result_reason_codes(
        raw_map=raw_map,
        text=text,
        plan_query=plan_query,
        assessment=assessment,
        quality=quality,
        official_exchange_identity_ok=official_exchange_identity_ok,
        reject_reasons=reject_reasons,
    )

    accepted = not reject_reasons
    exchange_metadata = _exchange_metadata_from_raw_map(raw_map)
    structured_metadata = _structured_metadata_from_raw_map(raw_map)
    sample = {
        "accepted": accepted,
        "raw_id": raw.raw_id,
        "provider": raw.provider,
        "source_url": raw.source_url,
        "title": raw.title[:220],
        "source_class": assessment.source_class,
        "source_mission": assessment.source_mission,
        "provider_coverage_status": assessment.provider_coverage_status,
        "source_coverage_gap_reason": assessment.source_coverage_gap_reason,
        "evidence_absence_is_meaningful": assessment.evidence_absence_is_meaningful,
        "source_can_prove": assessment.can_prove,
        "source_cannot_prove": assessment.cannot_prove,
        "source_useful_playbooks": assessment.useful_playbooks,
        "evidence_quality_score": quality.evidence_quality_score,
        "evidence_specificity": quality.evidence_specificity,
        "reason_codes": tuple(dict.fromkeys(reason_codes if accepted else reject_reasons)),
        "source_registry_reasons": assessment.reason_codes[:6],
        "source_pack_context_only": bool(pack_eval.get("source_pack_context_only")),
        "source_pack_impact_path_validating_source": bool(pack_eval.get("source_pack_impact_path_validating_source")),
        "source_pack_validated_digest_sufficient": bool(pack_eval.get("source_pack_validated_digest_sufficient")),
        "source_pack_watchlist_requirements_met": bool(pack_eval.get("source_pack_watchlist_requirements_met")),
        "source_pack_high_priority_requirements_met": bool(pack_eval.get("source_pack_high_priority_requirements_met")),
        "source_pack_missing_evidence": tuple(pack_eval.get("source_pack_missing_evidence") or ()),
        "currency_tags": currency_tags,
        "cryptopanic_currency_tag_match": assessment.cryptopanic_currency_tag_match,
        "narrative_heat": assessment.narrative_heat,
        "source_enrichment": event_source_enrichment.source_enrichment_metadata(raw),
        **exchange_metadata,
        **structured_metadata,
        "query": plan_query.query,
        "provider_hint": plan_query.provider_hint,
        "purpose": plan_query.purpose,
    }
    return accepted, sample


def _raw_result_reject_reasons(
    raw: RawDiscoveredEvent,
    *,
    raw_map: Mapping[str, Any],
    text: str,
    query: event_catalyst_search.SearchQuery,
    request: EvidenceAcquisitionRequest,
    plan_query: event_llm_evidence_planner.EvidencePlanQuery,
    pack: event_source_packs.SourcePack,
    assessment: event_source_registry.SourceAssessment,
    pack_eval: Mapping[str, Any],
    quality: event_evidence_quality.EvidenceQualityAssessment,
) -> tuple[list[str], bool, tuple[str, ...]]:
    reject_reasons: list[str] = []
    official_exchange_identity_ok = _official_exchange_identity_match(raw_map, request)
    if assessment.source_class == event_source_registry.SourceClass.OFFICIAL_EXCHANGE.value:
        identity_ok = official_exchange_identity_ok
    else:
        identity_ok = event_catalyst_search.result_mentions_anomaly_identity(raw, query, None)
    if not identity_ok and plan_query.must_validate_asset:
        reject_reasons.append("token_identity_rejected")
    if not _catalyst_link_ok(text, request, plan_query):
        reject_reasons.append("catalyst_missing")
    if assessment.source_class in pack.context_only_sources:
        reject_reasons.append("source_context_only")
    currency_tags = _currency_tags_from_raw_map(raw_map)
    if (
        assessment.source_class == event_source_registry.SourceClass.CRYPTOPANIC_TAGGED.value
        and plan_query.must_validate_asset
        and currency_tags
        and not assessment.cryptopanic_currency_tag_match
    ):
        reject_reasons.append("cryptopanic_currency_tag_mismatch")
    if plan_query.must_validate_asset and not bool(pack_eval.get("source_pack_impact_path_validating_source")):
        reject_reasons.append("source_pack_missing_impact_path_validator")
    _append_pack_specific_reject_reasons(pack, pack_eval, reject_reasons)
    if _quality_blocks_impact_path(quality, official_exchange_identity_ok, assessment, pack_eval):
        reject_reasons.append("impact_path_missing")
    if assessment.confidence_cap < 45 or quality.evidence_quality_score < 45:
        reject_reasons.append("source_quality_too_low")
    if quality.evidence_specificity == event_evidence_quality.EvidenceSpecificity.SOURCE_NOISE.value:
        reject_reasons.append("source_noise")
    if (
        assessment.narrative_heat
        and not assessment.cryptopanic_currency_tag_match
        and quality.evidence_specificity != event_evidence_quality.EvidenceSpecificity.DIRECT_TOKEN_MECHANISM.value
    ):
        reject_reasons.append("cryptopanic_narrative_heat_only")
    if query.symbol.upper() in event_catalyst_search.COMMON_WORD_SYMBOLS and not _case_sensitive_symbol(raw, query.symbol):
        reject_reasons.append("ticker_collision")
    if _generic_cooccurrence(text, request):
        reject_reasons.append("generic_cooccurrence_only")
    return reject_reasons, official_exchange_identity_ok, currency_tags


def _append_pack_specific_reject_reasons(
    pack: event_source_packs.SourcePack,
    pack_eval: Mapping[str, Any],
    reject_reasons: list[str],
) -> None:
    missing = set(str(item) for item in pack_eval.get("source_pack_missing_evidence") or ())
    if pack.name == "unlock_supply_pack":
        for reason in ("needs_supply_materiality", "unlock_not_material", "stale_unlock_data"):
            if reason in missing:
                reject_reasons.append(reason)
    if pack.name == "project_event_pack" and "low_authority_calendar_event" in missing:
        reject_reasons.append("low_authority_calendar_event")


def _quality_blocks_impact_path(
    quality: event_evidence_quality.EvidenceQualityAssessment,
    official_exchange_identity_ok: bool,
    assessment: event_source_registry.SourceAssessment,
    pack_eval: Mapping[str, Any],
) -> bool:
    if quality.evidence_specificity not in {
        event_evidence_quality.EvidenceSpecificity.GENERIC_CONTEXT.value,
        event_evidence_quality.EvidenceSpecificity.CATALYST_ONLY.value,
        event_evidence_quality.EvidenceSpecificity.TOKEN_ONLY.value,
    }:
        return False
    return not (
        official_exchange_identity_ok
        and assessment.source_class == event_source_registry.SourceClass.OFFICIAL_EXCHANGE.value
        and bool(pack_eval.get("source_pack_impact_path_validating_source"))
    )


def _raw_result_reason_codes(
    *,
    raw_map: Mapping[str, Any],
    text: str,
    plan_query: event_llm_evidence_planner.EvidencePlanQuery,
    assessment: event_source_registry.SourceAssessment,
    quality: event_evidence_quality.EvidenceQualityAssessment,
    official_exchange_identity_ok: bool,
    reject_reasons: list[str],
) -> list[str]:
    reason_codes: list[str] = []
    if assessment.source_class == event_source_registry.SourceClass.OFFICIAL_EXCHANGE.value:
        reason_codes.append("official_exchange_listing")
        if official_exchange_identity_ok:
            reason_codes.append("official_exchange_identity_match")
    if assessment.source_class == event_source_registry.SourceClass.OFFICIAL_PROJECT.value:
        reason_codes.append("official_project_confirmation")
    if assessment.source_class == event_source_registry.SourceClass.STRUCTURED_CALENDAR.value:
        reason_codes.append("structured_calendar_source")
        if assessment.can_validate_event_time:
            reason_codes.append("event_time_confirmation")
    if assessment.source_class == event_source_registry.SourceClass.STRUCTURED_UNLOCK.value:
        _append_structured_unlock_reason_codes(raw_map, assessment, reason_codes)
    if assessment.cryptopanic_currency_tag_match:
        reason_codes.append("cryptopanic_currency_tag_match")
    if quality.evidence_specificity == event_evidence_quality.EvidenceSpecificity.DIRECT_TOKEN_MECHANISM.value:
        reason_codes.append("direct_token_mechanism")
    if plan_query.purpose == "second_source_confirmation":
        reason_codes.append("second_source_confirmation")
    if plan_query.purpose == "denial_search" and _denial_or_correction(text):
        reason_codes.append("denial_or_correction_found")
    if not reason_codes and not reject_reasons:
        reason_codes.append("second_source_confirmation")
    return reason_codes


def _append_structured_unlock_reason_codes(
    raw_map: Mapping[str, Any],
    assessment: event_source_registry.SourceAssessment,
    reason_codes: list[str],
) -> None:
    reason_codes.append("structured_unlock_source")
    if assessment.can_validate_event_time:
        reason_codes.append("event_time_confirmation")
    unlock_materiality = _structured_metadata_from_raw_map(raw_map).get("unlock_materiality")
    if unlock_materiality in {"material", "large"}:
        reason_codes.append("material_unlock")
    if unlock_materiality == "large":
        reason_codes.append("large_unlock")


def _annotate_accepted_raw(
    raw: RawDiscoveredEvent,
    request: EvidenceAcquisitionRequest,
    sample: Mapping[str, Any],
) -> RawDiscoveredEvent:
    payload = dict(raw.raw_json or {})
    payload["event_evidence_acquisition"] = {
        "acquisition_id": request.acquisition_id,
        "source_pack": request.source_pack,
        "reason_codes": list(sample.get("reason_codes") or ()),
        "research_only": True,
    }
    return replace(raw, raw_json=payload)


def _attach_result_to_hypothesis(item: object, result: EvidenceAcquisitionResult | None) -> object:
    if result is None or not hasattr(item, "__dataclass_fields__"):
        return item
    components = dict(getattr(item, "score_components", {}) or {})
    components.update(result.to_metadata())
    components["source_pack"] = result.source_pack
    components["evidence_acquisition_attempted"] = True
    _apply_final_verdict_metadata(components, result)
    if result.evidence_quality_after is not None:
        components["evidence_quality_score"] = max(
            _float(components.get("evidence_quality_score")) or 0.0,
            result.evidence_quality_after,
        )
    validation_reasons = tuple(dict.fromkeys((
        *tuple(getattr(item, "validation_reasons", ()) or ()),
        *tuple(
            str(code)
            for evidence in result.accepted_evidence
            for code in evidence.get("reason_codes", ())
            if str(code)
        ),
    )))
    warnings = tuple(dict.fromkeys((*tuple(getattr(item, "warnings", ()) or ()), *result.warnings)))
    replace_kwargs: dict[str, Any] = {
        "score_components": components,
        "validation_reasons": validation_reasons,
        "warnings": warnings,
    }
    for field_name, value in (
        ("opportunity_score_final", result.final_opportunity_score),
        ("opportunity_level", result.final_opportunity_level),
        ("market_confirmation_level", result.post_refresh_market_confirmation_level),
        ("evidence_quality_score", result.post_refresh_evidence_quality_score),
    ):
        if value not in (None, "") and hasattr(item, field_name):
            replace_kwargs[field_name] = value
    return replace(item, **replace_kwargs)


def _finalize_result(
    result: EvidenceAcquisitionResult,
    *,
    before: object | None,
    after: object | None,
) -> EvidenceAcquisitionResult:
    before_components = dict(getattr(before, "score_components", {}) or {})
    after_components = dict(getattr(after, "score_components", {}) or {})
    before_score = _score_from_object(before, result.opportunity_score_before)
    before_level = _level_from_object(before, result.opportunity_level_before)
    after_score = _score_from_object(after, result.opportunity_score_before)
    after_level = _level_from_object(after, result.opportunity_level_before)
    after_quality = _float(getattr(after, "evidence_quality_score", None)) or _float(after_components.get("evidence_quality_score")) or result.evidence_quality_after
    after_path = str(getattr(after, "impact_path_type", "") or after_components.get("impact_path_type") or getattr(after, "validation_stage", "") or result.impact_path_validation_after or "") or None
    final_score, final_level, final_source, final_reason = _canonical_final_verdict(
        before=before,
        after=after,
        before_score=before_score,
        before_level=before_level,
        after_score=after_score,
        after_level=after_level,
        accepted=bool(result.accepted_evidence),
    )
    status = "unchanged"
    reason = None
    no_upgrade = result.no_upgrade_reason
    level_delta = _level_delta(before_level, final_level)
    score_delta = round(final_score - before_score, 2)
    evidence_delta = _optional_delta(result.evidence_quality_before, after_quality)
    evidence_upgraded = evidence_delta is not None and evidence_delta > 0
    impact_upgraded = _impact_path_rank(after_path) > _impact_path_rank(result.impact_path_validation_before)
    market_upgraded = _market_score_from_components(after_components) > _market_score_from_components(before_components)
    if result.status in {EvidenceAcquisitionStatus.FAILED_SOFT.value, EvidenceAcquisitionStatus.PROVIDER_UNAVAILABLE.value, EvidenceAcquisitionStatus.PROVIDER_BACKOFF.value}:
        status = "failed"
    elif _level_rank(final_level) > _level_rank(before_level) or score_delta > 0.01:
        status = "upgraded"
        reason = "accepted_source_pack_evidence"
        no_upgrade = None
    elif _level_rank(final_level) < _level_rank(before_level) or score_delta < -0.01:
        status = "downgraded"
        no_upgrade = "accepted_evidence_lowered_final_verdict" if result.accepted_evidence else "final_verdict_downgraded"
    elif result.accepted_evidence:
        status = "unchanged"
        no_upgrade = "accepted_evidence_did_not_change_final_verdict"
    market_components = _components_for_final_verdict(
        final_source=final_source,
        before_components=before_components,
        after_components=after_components,
    )
    market_score = _market_score_from_components(market_components)
    market_level = _market_level_from_components(market_components) or _market_level_from_score(market_score)
    market_freshness = _best_market_freshness(
        market_components,
        before_components,
        after_components,
    )
    return replace(
        result,
        evidence_quality_after=after_quality,
        impact_path_validation_after=after_path,
        opportunity_score_after=round(after_score, 2),
        opportunity_level_after=after_level,
        acquisition_evidence_status=_evidence_status(result.status, accepted_evidence=result.accepted_evidence, rejected_evidence=result.rejected_evidence),
        evidence_quality_delta=evidence_delta,
        opportunity_score_delta=score_delta,
        opportunity_level_delta=level_delta,
        evidence_quality_upgraded=evidence_upgraded,
        impact_path_validation_upgraded=impact_upgraded,
        market_confirmation_upgraded=market_upgraded,
        final_upgrade_status=status,
        initial_opportunity_score=round(before_score, 2),
        initial_opportunity_level=before_level,
        post_refresh_opportunity_score=round(after_score, 2),
        post_refresh_opportunity_level=after_level,
        post_refresh_market_confirmation_score=round(market_score, 2),
        post_refresh_market_confirmation_level=market_level,
        post_refresh_evidence_quality_score=after_quality,
        final_opportunity_score=round(final_score, 2),
        final_opportunity_level=final_level,
        final_verdict_source=final_source,
        final_verdict_reason=final_reason or reason or no_upgrade,
        market_data_freshness=market_freshness,
        market_reaction_confirmation=market_level,
        acquisition_upgrade_status=status,
        acquisition_upgrade_reason=reason,
        no_upgrade_reason=no_upgrade,
    )


def _queries_from_plan(plan: Mapping[str, Any]) -> tuple[event_llm_evidence_planner.EvidencePlanQuery, ...]:
    out: list[event_llm_evidence_planner.EvidencePlanQuery] = []
    for key in ("evidence_query_plan", "evidence_official_searches", "evidence_denial_searches"):
        rows = plan.get(key)
        if not isinstance(rows, Iterable) or isinstance(rows, (str, bytes, Mapping)):
            continue
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            query = str(row.get("query") or "").strip()
            if not query:
                continue
            out.append(event_llm_evidence_planner.EvidencePlanQuery(
                query=query,
                provider_hint=str(row.get("provider_hint") or "fixture"),
                purpose=str(row.get("purpose") or "source_pack_search"),
                must_validate_asset=bool(row.get("must_validate_asset", True)),
            ))
    return tuple(dict.fromkeys(out))


def _normalize_query_plan_for_request(
    queries: Iterable[event_llm_evidence_planner.EvidencePlanQuery],
    request: event_llm_evidence_planner.EvidencePlannerRequest,
) -> tuple[event_llm_evidence_planner.EvidencePlanQuery, ...]:
    """Replace stale generic asset placeholders after identity is known."""
    asset = (request.symbol or request.coin_id or "").strip()
    if not asset:
        return tuple(queries)
    normalized: list[event_llm_evidence_planner.EvidencePlanQuery] = []
    for query in queries:
        text = re.sub(r"(?<![\w-])asset(?![\w-])", asset, query.query, flags=re.IGNORECASE)
        normalized.append(replace(query, query=text) if text != query.query else query)
    return tuple(dict.fromkeys(normalized))


def _provider_for_hint(
    hint: str,
    providers_by_hint: Mapping[str, EvidenceSearchProvider | None],
    default_provider: EvidenceSearchProvider | None,
) -> EvidenceSearchProvider | None:
    key = str(hint or "").strip().lower()
    aliases = {
        "official_exchange": ("official_exchange", "binance_announcements", "bybit_announcements"),
        "project_blog_rss": ("project_blog_rss", "rss"),
        "rss": ("rss", "project_blog_rss"),
    }
    for candidate in (key, *aliases.get(key, ())):
        if candidate in providers_by_hint:
            return providers_by_hint[candidate]
    return default_provider


def _aggregate_status(results: Iterable[EvidenceAcquisitionQueryResult]) -> str:
    statuses = [result.status for result in results]
    if not statuses:
        return EvidenceAcquisitionStatus.PLANNED.value
    if EvidenceAcquisitionStatus.ACCEPTED_EVIDENCE_FOUND.value in statuses:
        return EvidenceAcquisitionStatus.ACCEPTED_EVIDENCE_FOUND.value
    if all(status == EvidenceAcquisitionStatus.NO_RESULTS.value for status in statuses):
        return EvidenceAcquisitionStatus.NO_RESULTS.value
    if any(status == EvidenceAcquisitionStatus.REJECTED_RESULTS_ONLY.value for status in statuses):
        return EvidenceAcquisitionStatus.REJECTED_RESULTS_ONLY.value
    if any(status == EvidenceAcquisitionStatus.PROVIDER_BACKOFF.value for status in statuses):
        return EvidenceAcquisitionStatus.PROVIDER_BACKOFF.value
    if any(status == EvidenceAcquisitionStatus.PROVIDER_UNAVAILABLE.value for status in statuses):
        return EvidenceAcquisitionStatus.PROVIDER_UNAVAILABLE.value
    if any(status == EvidenceAcquisitionStatus.FAILED_SOFT.value for status in statuses):
        return EvidenceAcquisitionStatus.FAILED_SOFT.value
    return EvidenceAcquisitionStatus.EXECUTED.value


def _run_result_status(
    results: Iterable[EvidenceAcquisitionResult],
    *,
    artifact_warnings: Iterable[str] = (),
) -> str:
    statuses = [str(result.status or "") for result in results]
    if any(artifact_warnings):
        return EvidenceAcquisitionStatus.FAILED_SOFT.value
    if not statuses:
        return "no_candidates"
    if any(status == EvidenceAcquisitionStatus.FAILED_SOFT.value for status in statuses):
        return EvidenceAcquisitionStatus.FAILED_SOFT.value
    if any(status == EvidenceAcquisitionStatus.PROVIDER_BACKOFF.value for status in statuses):
        return EvidenceAcquisitionStatus.PROVIDER_BACKOFF.value
    if any(status == EvidenceAcquisitionStatus.PROVIDER_UNAVAILABLE.value for status in statuses):
        return EvidenceAcquisitionStatus.PROVIDER_UNAVAILABLE.value
    if all(status == EvidenceAcquisitionStatus.SKIPPED_BUDGET.value for status in statuses):
        return EvidenceAcquisitionStatus.SKIPPED_BUDGET.value
    if all(status == EvidenceAcquisitionStatus.SKIPPED_CONFIG.value for status in statuses):
        return EvidenceAcquisitionStatus.SKIPPED_CONFIG.value
    return "complete"


def _budget_skipped_result(request: EvidenceAcquisitionRequest) -> EvidenceAcquisitionResult:
    return EvidenceAcquisitionResult(
        acquisition_id=request.acquisition_id,
        opportunity_id=request.opportunity_id,
        core_opportunity_id=request.core_opportunity_id,
        hypothesis_id=request.hypothesis_id,
        incident_id=request.incident_id,
        source_pack=request.source_pack,
        status=EvidenceAcquisitionStatus.SKIPPED_BUDGET.value,
        symbol=request.symbol,
        coin_id=request.coin_id,
        event_name=request.event_name,
        external_asset=request.external_asset,
        evidence_quality_before=request.evidence_quality_before,
        evidence_quality_after=request.evidence_quality_before,
        impact_path_validation_before=request.impact_path_validation_before,
        impact_path_validation_after=request.impact_path_validation_before,
        opportunity_score_before=request.opportunity_score_before,
        opportunity_score_after=request.opportunity_score_before,
        opportunity_level_before=request.opportunity_level_before,
        opportunity_level_after=request.opportunity_level_before,
        acquisition_upgrade_status="failed",
        no_upgrade_reason="evidence_acquisition_budget_exhausted",
    )
