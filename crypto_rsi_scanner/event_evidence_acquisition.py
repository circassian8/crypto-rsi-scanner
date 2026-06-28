"""Source-pack evidence acquisition for Event Alpha research artifacts.

This module executes bounded, provider-backed evidence searches suggested by
``event_llm_evidence_planner``. It is research-only: no sends, no trades, no
paper rows, no normal RSI signal rows, and no event-fade trigger creation.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol

from . import (
    event_catalyst_search,
    event_core_opportunities,
    event_evidence_quality,
    event_impact_hypotheses,
    event_llm_evidence_planner,
    event_source_packs,
    event_source_registry,
)
from .event_models import RawDiscoveredEvent
from .event_resolver import clean_text


SCHEMA_VERSION = "event_evidence_acquisition_v1"


class EvidenceAcquisitionStatus(str, Enum):
    PLANNED = "planned"
    EXECUTED = "executed"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_BACKOFF = "provider_backoff"
    NO_RESULTS = "no_results"
    ACCEPTED_EVIDENCE_FOUND = "accepted_evidence_found"
    REJECTED_RESULTS_ONLY = "rejected_results_only"
    FAILED_SOFT = "failed_soft"
    SKIPPED_BUDGET = "skipped_budget"
    SKIPPED_CONFIG = "skipped_config"


class EvidenceSearchProvider(Protocol):
    name: str

    def search(
        self,
        queries: Iterable[event_catalyst_search.SearchQuery],
        *,
        max_results_per_query: int,
        now: datetime | None = None,
    ) -> event_catalyst_search.CatalystSearchRunResult:
        ...


@dataclass(frozen=True)
class EvidenceAcquisitionConfig:
    enabled: bool = False
    max_candidates: int = 10
    max_queries: int = 20
    max_results_per_query: int = 5
    timeout_seconds: float = 8.0
    fixture_only: bool = False
    artifact_path: Path | None = None


@dataclass(frozen=True)
class EvidenceAcquisitionRequest:
    acquisition_id: str
    opportunity_id: str
    core_opportunity_id: str | None
    hypothesis_id: str | None
    incident_id: str | None
    symbol: str
    coin_id: str
    event_name: str
    external_asset: str
    source_pack: str
    opportunity_score_before: float
    opportunity_level_before: str
    evidence_quality_before: float | None
    impact_path_validation_before: str | None
    query_plan: tuple[event_llm_evidence_planner.EvidencePlanQuery, ...]
    provider_coverage_status: str = event_source_registry.ProviderCoverageStatus.COMPLETE.value
    row: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class EvidenceAcquisitionQueryResult:
    query: str
    provider_hint: str
    provider_used: str | None
    purpose: str
    status: str
    results_seen: int = 0
    accepted_evidence: tuple[Mapping[str, Any], ...] = ()
    rejected_evidence: tuple[Mapping[str, Any], ...] = ()
    provider_failures: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    evidence_absence_is_meaningful: bool = False

    def to_metadata(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "provider_hint": self.provider_hint,
            "provider_used": self.provider_used,
            "purpose": self.purpose,
            "status": self.status,
            "results_seen": self.results_seen,
            "accepted_evidence": tuple(dict(item) for item in self.accepted_evidence),
            "rejected_evidence": tuple(dict(item) for item in self.rejected_evidence),
            "provider_failures": self.provider_failures,
            "warnings": self.warnings,
            "evidence_absence_is_meaningful": self.evidence_absence_is_meaningful,
        }


@dataclass(frozen=True)
class EvidenceAcquisitionResult:
    acquisition_id: str
    opportunity_id: str
    core_opportunity_id: str | None
    hypothesis_id: str | None
    incident_id: str | None
    source_pack: str
    status: str
    symbol: str = ""
    coin_id: str = ""
    event_name: str = ""
    external_asset: str = ""
    queries_executed: int = 0
    providers_used: tuple[str, ...] = ()
    provider_failures: tuple[str, ...] = ()
    accepted_evidence: tuple[Mapping[str, Any], ...] = ()
    rejected_evidence: tuple[Mapping[str, Any], ...] = ()
    query_results: tuple[EvidenceAcquisitionQueryResult, ...] = ()
    evidence_quality_before: float | None = None
    evidence_quality_after: float | None = None
    impact_path_validation_before: str | None = None
    impact_path_validation_after: str | None = None
    opportunity_score_before: float = 0.0
    opportunity_score_after: float = 0.0
    opportunity_level_before: str = "local_only"
    opportunity_level_after: str = "local_only"
    acquisition_evidence_status: str = "no_results"
    evidence_quality_delta: float | None = None
    opportunity_score_delta: float = 0.0
    opportunity_level_delta: str = "unchanged"
    evidence_quality_upgraded: bool = False
    impact_path_validation_upgraded: bool = False
    market_confirmation_upgraded: bool = False
    final_upgrade_status: str = "unchanged"
    initial_opportunity_score: float | None = None
    initial_opportunity_level: str | None = None
    post_refresh_opportunity_score: float | None = None
    post_refresh_opportunity_level: str | None = None
    post_refresh_market_confirmation_score: float | None = None
    post_refresh_market_confirmation_level: str | None = None
    post_refresh_evidence_quality_score: float | None = None
    final_opportunity_score: float | None = None
    final_opportunity_level: str | None = None
    final_verdict_source: str = "initial"
    final_verdict_reason: str | None = None
    market_data_freshness: str | None = None
    market_reaction_confirmation: str | None = None
    acquisition_upgrade_status: str = "unchanged"
    acquisition_upgrade_reason: str | None = None
    no_upgrade_reason: str | None = None
    warnings: tuple[str, ...] = ()

    def to_metadata(self) -> dict[str, Any]:
        reason_codes = tuple(dict.fromkeys(
            str(code)
            for item in self.accepted_evidence
            for code in item.get("reason_codes", ())
            if str(code)
        ))
        return {
            "evidence_acquisition_id": self.acquisition_id,
            "evidence_acquisition_symbol": self.symbol,
            "evidence_acquisition_coin_id": self.coin_id,
            "evidence_acquisition_event_name": self.event_name,
            "evidence_acquisition_external_asset": self.external_asset,
            "evidence_acquisition_status": self.status,
            "evidence_acquisition_source_pack": self.source_pack,
            "evidence_acquisition_queries_executed": self.queries_executed,
            "evidence_acquisition_providers_used": self.providers_used,
            "evidence_acquisition_provider_failures": self.provider_failures,
            "evidence_acquisition_accepted_count": len(self.accepted_evidence),
            "evidence_acquisition_rejected_count": len(self.rejected_evidence),
            "evidence_acquisition_accepted_evidence": tuple(dict(item) for item in self.accepted_evidence[:5]),
            "evidence_acquisition_rejected_samples": tuple(dict(item) for item in self.rejected_evidence[:5]),
            "accepted_evidence_reason_codes": reason_codes,
            "acquisition_evidence_status": self.acquisition_evidence_status,
            "evidence_acquisition_score_before": self.evidence_quality_before,
            "evidence_acquisition_score_after": self.evidence_quality_after,
            "evidence_quality_delta": self.evidence_quality_delta,
            "evidence_quality_upgraded": self.evidence_quality_upgraded,
            "impact_path_validation_before_acquisition": self.impact_path_validation_before,
            "impact_path_validation_after_acquisition": self.impact_path_validation_after,
            "impact_path_validation_upgraded": self.impact_path_validation_upgraded,
            "market_confirmation_upgraded": self.market_confirmation_upgraded,
            "opportunity_score_before_acquisition": self.opportunity_score_before,
            "opportunity_score_after_acquisition": self.opportunity_score_after,
            "opportunity_score_delta": self.opportunity_score_delta,
            "opportunity_level_before_acquisition": self.opportunity_level_before,
            "opportunity_level_after_acquisition": self.opportunity_level_after,
            "opportunity_level_delta": self.opportunity_level_delta,
            "final_upgrade_status": self.final_upgrade_status,
            "initial_opportunity_score": self.initial_opportunity_score,
            "initial_opportunity_level": self.initial_opportunity_level,
            "post_refresh_opportunity_score": self.post_refresh_opportunity_score,
            "post_refresh_opportunity_level": self.post_refresh_opportunity_level,
            "post_refresh_market_confirmation_score": self.post_refresh_market_confirmation_score,
            "post_refresh_market_confirmation_level": self.post_refresh_market_confirmation_level,
            "post_refresh_evidence_quality_score": self.post_refresh_evidence_quality_score,
            "final_opportunity_score": self.final_opportunity_score,
            "final_opportunity_level": self.final_opportunity_level,
            "final_verdict_source": self.final_verdict_source,
            "final_verdict_reason": self.final_verdict_reason,
            "market_data_freshness": self.market_data_freshness,
            "market_reaction_confirmation": self.market_reaction_confirmation,
            "acquisition_upgrade_status": self.acquisition_upgrade_status,
            "acquisition_upgrade_reason": self.acquisition_upgrade_reason,
            "no_upgrade_reason": self.no_upgrade_reason,
            "evidence_acquisition_warnings": self.warnings,
            "evidence_acquisition_results": {
                "status": self.status,
                "queries_executed": self.queries_executed,
                "accepted": len(self.accepted_evidence),
                "rejected": len(self.rejected_evidence),
                "providers_used": self.providers_used,
                "upgrade_status": self.acquisition_upgrade_status,
                "final_upgrade_status": self.final_upgrade_status,
                "upgrade_reason": self.acquisition_upgrade_reason,
                "no_upgrade_reason": self.no_upgrade_reason,
            },
        }


@dataclass(frozen=True)
class EventEvidenceAcquisitionRunResult:
    hypotheses: tuple[object, ...]
    results: tuple[EvidenceAcquisitionResult, ...]
    path: Path | None = None
    rows_written: int = 0
    status: str = "complete"
    warnings: tuple[str, ...] = ()

    @property
    def attempted(self) -> int:
        return len(self.results)

    @property
    def accepted(self) -> int:
        return sum(1 for result in self.results if result.accepted_evidence)

    @property
    def rejected_only(self) -> int:
        return sum(
            1
            for result in self.results
            if result.rejected_evidence and not result.accepted_evidence
        )

    @property
    def upgraded(self) -> int:
        return sum(1 for result in self.results if result.acquisition_upgrade_status == "upgraded")


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


def write_acquisition_results(
    path: str | Path,
    results: Iterable[EvidenceAcquisitionResult],
    *,
    run_context: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> int:
    """Append compact acquisition rows to a local research JSONL artifact."""
    observed = _as_utc(now or datetime.now(timezone.utc)).isoformat()
    context = dict(run_context or {})
    p = Path(path).expanduser()
    rows = [_artifact_row(result, context=context, observed_at=observed) for result in results]
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(_json_ready(row), sort_keys=True, separators=(",", ":")))
            fh.write("\n")
    return len(rows)


def load_acquisition_results(path: str | Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    p = Path(path).expanduser()
    if not p.exists():
        return []
    rows: list[dict[str, Any]] = []
    with p.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and row.get("row_type") == "event_evidence_acquisition":
                rows.append(row)
    rows.sort(key=lambda row: str(row.get("observed_at") or ""), reverse=True)
    return rows[:limit] if limit and limit > 0 else rows


def reconcile_acquisition_core_ids(
    path: str | Path,
    core_opportunity_rows: Iterable[Mapping[str, Any] | object],
    *,
    run_id: str | None = None,
    profile: str | None = None,
    artifact_namespace: str | None = None,
) -> int:
    """Rewrite acquisition rows so they point at canonical core opportunities.

    Acquisition planning can run before the final canonical core store is
    written. This post-store reconciliation is artifact-only and keeps
    evidence rows from carrying orphan pre-aggregation core IDs.
    """
    p = Path(path).expanduser()
    if not p.exists():
        return 0
    rows: list[dict[str, Any]] = []
    changed = 0
    try:
        with p.open("r", encoding="utf-8") as fh:
            for line in fh:
                text = line.strip()
                if not text:
                    continue
                try:
                    raw = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if isinstance(raw, dict):
                    rows.append(raw)
    except OSError:
        return 0
    for row in rows:
        if row.get("row_type") != "event_evidence_acquisition":
            continue
        if run_id and str(row.get("run_id") or "") != str(run_id):
            continue
        if profile and str(row.get("profile") or "") != str(profile):
            continue
        if artifact_namespace and str(row.get("artifact_namespace") or row.get("namespace") or "") != str(artifact_namespace):
            continue
        resolution = event_core_opportunities.resolve_canonical_core_opportunity_id(row, core_opportunity_rows)
        canonical = resolution.canonical_core_opportunity_id
        if not canonical:
            continue
        current = str(row.get("core_opportunity_id") or "").strip()
        if current != canonical:
            row["original_core_opportunity_id"] = current or None
            row["core_opportunity_id"] = canonical
            changed += 1
        row["core_opportunity_id_status"] = resolution.resolution_status
        if resolution.diagnostic_support_for_core_opportunity_id:
            row["diagnostic_support_for_core_opportunity_id"] = resolution.diagnostic_support_for_core_opportunity_id
        if resolution.warnings:
            existing = row.get("warnings") if isinstance(row.get("warnings"), list) else []
            row["warnings"] = list(dict.fromkeys([*existing, *resolution.warnings]))
    if changed:
        try:
            with p.open("w", encoding="utf-8") as fh:
                for row in rows:
                    fh.write(json.dumps(_json_ready(row), sort_keys=True, separators=(",", ":")))
                    fh.write("\n")
        except OSError:
            return 0
    return changed


def format_acquisition_report(rows: Iterable[Mapping[str, Any]]) -> str:
    data = [dict(row) for row in rows if isinstance(row, Mapping)]
    lines = [
        "=" * 76,
        "EVENT EVIDENCE ACQUISITION REPORT (research artifact only)",
        "=" * 76,
        f"rows={len(data)}",
    ]
    if not data:
        lines.append("No acquisition rows found.")
        return "\n".join(lines)
    status_counts: dict[str, int] = {}
    pack_counts: dict[str, int] = {}
    for row in data:
        status_counts[str(row.get("status") or "unknown")] = status_counts.get(str(row.get("status") or "unknown"), 0) + 1
        pack_counts[str(row.get("source_pack") or "unknown")] = pack_counts.get(str(row.get("source_pack") or "unknown"), 0) + 1
    lines.append("statuses: " + _counts_line(status_counts))
    lines.append("source_packs: " + _counts_line(pack_counts))
    for row in data[:12]:
        lines.append(
            f"- {row.get('symbol') or row.get('coin_id') or 'UNKNOWN'} "
            f"pack={row.get('source_pack') or 'unknown'} status={row.get('status') or 'unknown'} "
            f"accepted={len(row.get('accepted_evidence') or ())} rejected={len(row.get('rejected_evidence_samples') or ())} "
            f"score={row.get('opportunity_score_before')}->{row.get('opportunity_score_after')} "
            f"evidence={row.get('acquisition_evidence_status') or 'unknown'} "
            f"final={row.get('final_upgrade_status') or row.get('acquisition_upgrade_status') or 'unchanged'} "
            f"verdict={row.get('final_opportunity_level') or row.get('opportunity_level_after') or 'unknown'}"
        )
    lines.append("No sends, trades, paper rows, normal RSI rows, or trigger creation were performed.")
    return "\n".join(lines).rstrip()


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
        search_query = event_catalyst_search.SearchQuery(
            anomaly_raw_id=request.hypothesis_id or request.opportunity_id,
            query=plan_query.query,
            symbol=request.symbol,
            rank=rank,
            query_type=plan_query.purpose,
            coin_id=request.coin_id,
            project_name=request.coin_id.replace("-", " ") if request.coin_id else None,
            aliases=tuple(dict.fromkeys(value for value in (request.coin_id, request.coin_id.replace("-", " ") if request.coin_id else "", request.symbol) if value)),
        )
        selected_provider = _provider_for_hint(plan_query.provider_hint, providers_by_hint, provider)
        provider_name = getattr(selected_provider, "name", None) if selected_provider is not None else None
        if selected_provider is None:
            status = EvidenceAcquisitionStatus.PROVIDER_UNAVAILABLE.value
            failure = f"{plan_query.provider_hint}:not_configured"
            failures.append(failure)
            query_results.append(EvidenceAcquisitionQueryResult(
                query=plan_query.query,
                provider_hint=plan_query.provider_hint,
                provider_used=None,
                purpose=plan_query.purpose,
                status=status,
                provider_failures=(failure,),
                evidence_absence_is_meaningful=_absence_meaningful_for_hint(plan_query.provider_hint, request.provider_coverage_status),
            ))
            continue
        if cfg.fixture_only and "fixture" not in str(provider_name or "").casefold():
            failure = f"{plan_query.provider_hint}:fixture_only_provider_skipped"
            failures.append(failure)
            query_results.append(EvidenceAcquisitionQueryResult(
                query=plan_query.query,
                provider_hint=plan_query.provider_hint,
                provider_used=provider_name,
                purpose=plan_query.purpose,
                status=EvidenceAcquisitionStatus.SKIPPED_CONFIG.value,
                provider_failures=(failure,),
            ))
            continue
        providers_used.append(str(provider_name or plan_query.provider_hint))
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
            query_results.append(EvidenceAcquisitionQueryResult(
                query=plan_query.query,
                provider_hint=plan_query.provider_hint,
                provider_used=provider_name,
                purpose=plan_query.purpose,
                status=status,
                provider_failures=(failure,),
                warnings=(str(exc),),
            ))
            continue
        query_accepted: list[Mapping[str, Any]] = []
        query_rejected: list[Mapping[str, Any]] = []
        warnings = tuple(str(item) for item in getattr(search_result, "warnings", ()) or () if str(item))
        result_events = tuple(getattr(search_result, "result_events", ()) or ())
        if _provider_unavailable_from_warnings(warnings):
            status = EvidenceAcquisitionStatus.PROVIDER_UNAVAILABLE.value
            failures.extend(f"{plan_query.provider_hint}:{warning}" for warning in warnings[:3])
        elif _provider_backoff_from_warnings(warnings):
            status = EvidenceAcquisitionStatus.PROVIDER_BACKOFF.value
            failures.extend(f"{plan_query.provider_hint}:{warning}" for warning in warnings[:3])
        elif not result_events:
            status = EvidenceAcquisitionStatus.NO_RESULTS.value
        else:
            status = EvidenceAcquisitionStatus.EXECUTED.value
        for result_event in result_events:
            raw = getattr(result_event, "raw_event", None)
            if raw is None:
                continue
            accepted, sample = _validate_raw_result(raw, search_query, request, plan_query)
            if accepted:
                query_accepted.append(sample)
                accepted_evidence.append(sample)
                accepted_raw.append(_annotate_accepted_raw(raw, request, sample))
            else:
                query_rejected.append(sample)
                rejected_evidence.append(sample)
        if query_accepted:
            status = EvidenceAcquisitionStatus.ACCEPTED_EVIDENCE_FOUND.value
        elif query_rejected:
            status = EvidenceAcquisitionStatus.REJECTED_RESULTS_ONLY.value
        query_results.append(EvidenceAcquisitionQueryResult(
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
        ))
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
    reason_codes: list[str] = []
    reject_reasons: list[str] = []
    identity_ok = event_catalyst_search.result_mentions_anomaly_identity(raw, query, None)
    if not identity_ok and plan_query.must_validate_asset:
        reject_reasons.append("token_identity_rejected")
    if not _catalyst_link_ok(text, request, plan_query):
        reject_reasons.append("catalyst_missing")
    if assessment.source_class in pack.context_only_sources:
        reject_reasons.append("source_context_only")
    if plan_query.must_validate_asset and not bool(pack_eval.get("source_pack_impact_path_validating_source")):
        reject_reasons.append("source_pack_missing_impact_path_validator")
    if quality.evidence_specificity in {
        event_evidence_quality.EvidenceSpecificity.GENERIC_CONTEXT.value,
        event_evidence_quality.EvidenceSpecificity.CATALYST_ONLY.value,
        event_evidence_quality.EvidenceSpecificity.TOKEN_ONLY.value,
    }:
        reject_reasons.append("impact_path_missing")
    if assessment.confidence_cap < 45 or quality.evidence_quality_score < 45:
        reject_reasons.append("source_quality_too_low")
    if quality.evidence_specificity == event_evidence_quality.EvidenceSpecificity.SOURCE_NOISE.value:
        reject_reasons.append("source_noise")
    if query.symbol.upper() in event_catalyst_search.COMMON_WORD_SYMBOLS and not _case_sensitive_symbol(raw, query.symbol):
        reject_reasons.append("ticker_collision")
    if _generic_cooccurrence(text, request):
        reject_reasons.append("generic_cooccurrence_only")

    if assessment.source_class == event_source_registry.SourceClass.OFFICIAL_EXCHANGE.value:
        reason_codes.append("official_exchange_listing")
    if assessment.source_class == event_source_registry.SourceClass.OFFICIAL_PROJECT.value:
        reason_codes.append("official_project_confirmation")
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

    accepted = not reject_reasons
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
        "query": plan_query.query,
        "provider_hint": plan_query.provider_hint,
        "purpose": plan_query.purpose,
    }
    return accepted, sample


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


def _artifact_row(
    result: EvidenceAcquisitionResult,
    *,
    context: Mapping[str, Any],
    observed_at: str,
) -> dict[str, Any]:
    query_metadata = tuple(query.to_metadata() for query in result.query_results)
    query_execution_statuses = tuple(dict.fromkeys(
        str(query.get("status") or "")
        for query in query_metadata
        if str(query.get("status") or "")
    ))
    provider_coverage_statuses = tuple(dict.fromkeys(
        str(item.get("provider_coverage_status") or "")
        for item in (*result.accepted_evidence, *result.rejected_evidence)
        if str(item.get("provider_coverage_status") or "")
    ))
    coverage_gaps = tuple(dict.fromkeys(
        failure
        for query in result.query_results
        for failure in query.provider_failures
        if failure
    ))
    source_contract = event_source_registry.source_contract_metadata(
        {
            "symbol": result.symbol,
            "coin_id": result.coin_id,
            "provider_coverage_status": (
                provider_coverage_statuses[0]
                if len(provider_coverage_statuses) == 1
                else event_source_registry.ProviderCoverageStatus.COMPLETE.value
            ),
        },
        evidence_rows=(*result.accepted_evidence, *result.rejected_evidence),
        symbol=result.symbol,
        coin_id=result.coin_id,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "row_type": "event_evidence_acquisition",
        "observed_at": observed_at,
        "research_only": True,
        "run_id": context.get("run_id"),
        "profile": context.get("profile") or "default",
        "namespace": context.get("artifact_namespace") or context.get("namespace"),
        "artifact_namespace": context.get("artifact_namespace") or context.get("namespace"),
        "run_mode": context.get("run_mode"),
        "acquisition_id": result.acquisition_id,
        "core_opportunity_id": result.core_opportunity_id,
        "hypothesis_id": result.hypothesis_id,
        "incident_id": result.incident_id,
        "symbol": result.symbol,
        "coin_id": result.coin_id,
        "event_name": result.event_name,
        "external_asset": result.external_asset,
        "source_pack": result.source_pack,
        "status": result.status,
        "evidence_acquisition_attempted": True,
        "evidence_acquisition_plan": {
            "source_pack": result.source_pack,
            "query_count": len(result.query_results),
            "queries": query_metadata,
            "research_only": True,
        },
        "evidence_acquisition_results": result.to_metadata()["evidence_acquisition_results"],
        "query_execution_statuses": query_execution_statuses,
        "provider_coverage_statuses": provider_coverage_statuses,
        "provider_coverage_gaps": coverage_gaps,
        "source_can_prove": source_contract["source_can_prove"],
        "source_cannot_prove": source_contract["source_cannot_prove"],
        "source_useful_playbooks": source_contract["source_useful_playbooks"],
        "evidence_absence_is_meaningful": source_contract["evidence_absence_is_meaningful"],
        "source_coverage_gap_reasons": source_contract["source_coverage_gap_reasons"],
        "queries": query_metadata,
        "queries_executed": result.queries_executed,
        "providers_used": result.providers_used,
        "provider_failures": result.provider_failures,
        "accepted_evidence": tuple(dict(item) for item in result.accepted_evidence[:5]),
        "rejected_evidence_samples": tuple(dict(item) for item in result.rejected_evidence[:5]),
        "acquisition_evidence_status": result.acquisition_evidence_status,
        "evidence_quality_before": result.evidence_quality_before,
        "evidence_quality_after": result.evidence_quality_after,
        "evidence_quality_delta": result.evidence_quality_delta,
        "evidence_quality_upgraded": result.evidence_quality_upgraded,
        "impact_path_validation_before": result.impact_path_validation_before,
        "impact_path_validation_after": result.impact_path_validation_after,
        "impact_path_validation_upgraded": result.impact_path_validation_upgraded,
        "market_confirmation_upgraded": result.market_confirmation_upgraded,
        "opportunity_score_before": result.opportunity_score_before,
        "opportunity_score_after": result.opportunity_score_after,
        "opportunity_score_delta": result.opportunity_score_delta,
        "opportunity_level_before": result.opportunity_level_before,
        "opportunity_level_after": result.opportunity_level_after,
        "opportunity_level_delta": result.opportunity_level_delta,
        "initial_opportunity_score": result.initial_opportunity_score,
        "initial_opportunity_level": result.initial_opportunity_level,
        "post_refresh_opportunity_score": result.post_refresh_opportunity_score,
        "post_refresh_opportunity_level": result.post_refresh_opportunity_level,
        "post_refresh_market_confirmation_score": result.post_refresh_market_confirmation_score,
        "post_refresh_market_confirmation_level": result.post_refresh_market_confirmation_level,
        "post_refresh_evidence_quality_score": result.post_refresh_evidence_quality_score,
        "final_opportunity_score": result.final_opportunity_score,
        "final_opportunity_level": result.final_opportunity_level,
        "final_verdict_source": result.final_verdict_source,
        "final_verdict_reason": result.final_verdict_reason,
        "market_data_freshness": result.market_data_freshness,
        "market_reaction_confirmation": result.market_reaction_confirmation,
        "final_upgrade_status": result.final_upgrade_status,
        "acquisition_upgrade_status": result.acquisition_upgrade_status,
        "acquisition_upgrade_reason": result.acquisition_upgrade_reason,
        "no_upgrade_reason": result.no_upgrade_reason,
        "warnings": result.warnings,
    }


def _apply_final_verdict_metadata(components: dict[str, Any], result: EvidenceAcquisitionResult) -> None:
    fields = {
        "initial_opportunity_score": result.initial_opportunity_score,
        "initial_opportunity_level": result.initial_opportunity_level,
        "post_refresh_opportunity_score": result.post_refresh_opportunity_score,
        "post_refresh_opportunity_level": result.post_refresh_opportunity_level,
        "post_refresh_market_confirmation_score": result.post_refresh_market_confirmation_score,
        "post_refresh_market_confirmation_level": result.post_refresh_market_confirmation_level,
        "post_refresh_evidence_quality_score": result.post_refresh_evidence_quality_score,
        "final_opportunity_score": result.final_opportunity_score,
        "final_opportunity_level": result.final_opportunity_level,
        "final_verdict_source": result.final_verdict_source,
        "final_verdict_reason": result.final_verdict_reason,
        "market_data_freshness": result.market_data_freshness,
        "market_reaction_confirmation": result.market_reaction_confirmation,
        "final_upgrade_status": result.final_upgrade_status,
        "acquisition_evidence_status": result.acquisition_evidence_status,
        "evidence_quality_delta": result.evidence_quality_delta,
        "opportunity_score_delta": result.opportunity_score_delta,
        "opportunity_level_delta": result.opportunity_level_delta,
        "evidence_quality_upgraded": result.evidence_quality_upgraded,
        "impact_path_validation_upgraded": result.impact_path_validation_upgraded,
        "market_confirmation_upgraded": result.market_confirmation_upgraded,
    }
    for key, value in fields.items():
        if value not in (None, "", [], {}, ()):
            components[key] = value
    if result.final_opportunity_score is not None:
        components["opportunity_score_final"] = result.final_opportunity_score
    if result.final_opportunity_level:
        components["opportunity_level"] = result.final_opportunity_level
    if result.post_refresh_market_confirmation_score is not None:
        components["market_confirmation_score"] = result.post_refresh_market_confirmation_score
        components["post_refresh_market_confirmation_score"] = result.post_refresh_market_confirmation_score
    if result.post_refresh_market_confirmation_level:
        components["market_confirmation_level"] = result.post_refresh_market_confirmation_level
        components["post_refresh_market_confirmation_level"] = result.post_refresh_market_confirmation_level
    if result.post_refresh_market_confirmation_level:
        components["market_reaction_confirmation"] = result.post_refresh_market_confirmation_level
    if result.market_reaction_confirmation:
        components["market_reaction_confirmation"] = result.market_reaction_confirmation
    if result.market_data_freshness:
        components["market_data_freshness"] = result.market_data_freshness
        components.setdefault("market_context_freshness_status", result.market_data_freshness)
    elif components.get("market_context_freshness_status"):
        components["market_data_freshness"] = components.get("market_context_freshness_status")


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


def _raw_mapping(raw: RawDiscoveredEvent) -> dict[str, Any]:
    payload = dict(raw.raw_json or {})
    return {
        **payload,
        "provider": raw.provider,
        "source_url": raw.source_url,
        "title": raw.title,
        "body": raw.body,
        "raw_json": payload,
        "source_confidence": raw.source_confidence,
    }


def _row_from_object(item: object | Mapping[str, Any] | None) -> dict[str, Any]:
    if item is None:
        return {}
    if isinstance(item, Mapping):
        return dict(item)
    return dict(getattr(item, "__dict__", {}) or {})


def _merge_preserving_non_empty(base: Mapping[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in dict(overlay).items():
        if value in (None, "", [], {}, ()):
            continue
        merged[key] = value
    return merged


def _find_hypothesis(hypotheses: Iterable[object], hypothesis_id: str | None) -> object | None:
    if not hypothesis_id:
        return None
    for item in hypotheses:
        if str(getattr(item, "hypothesis_id", "") or "") == hypothesis_id:
            return item
    return None


def _catalyst_link_ok(
    text: str,
    request: EvidenceAcquisitionRequest,
    plan_query: event_llm_evidence_planner.EvidencePlanQuery,
) -> bool:
    terms = [
        request.external_asset,
        request.event_name,
        request.source_pack.replace("_pack", "").replace("_", " "),
        plan_query.purpose.replace("_", " "),
    ]
    catalyst_terms = (
        "listing", "perp", "futures", "unlock", "vesting", "exploit", "hack",
        "pre ipo", "pre-ipo", "tokenized stock", "exposure", "stake",
        "strategic investment", "valuation", "world cup", "fan token",
        "prediction market", "official", "announcement", "acquisition",
    )
    if any(clean_text(term) and clean_text(term) in text for term in terms):
        return True
    return any(term in text for term in catalyst_terms)


def _generic_cooccurrence(text: str, request: EvidenceAcquisitionRequest) -> bool:
    asset = clean_text(request.symbol or request.coin_id)
    if not asset or asset not in text:
        return False
    mechanism_terms = ("because", "driven by", "after", "listing", "unlock", "exploit", "hack", "exposure", "stake", "valuation", "resumes trading")
    return not any(term in text for term in mechanism_terms)


def _denial_or_correction(text: str) -> bool:
    return any(term in text for term in ("denies", "denied", "not affiliated", "false report", "correction", "not hacked", "ruled out"))


def _case_sensitive_symbol(raw: RawDiscoveredEvent, symbol: str) -> bool:
    if not symbol:
        return False
    haystack = " ".join(str(value or "") for value in (raw.title, raw.body))
    return symbol.upper() in haystack or f"${symbol.upper()}" in haystack


def _provider_unavailable_from_warnings(warnings: Iterable[str]) -> bool:
    text = " ".join(str(warning) for warning in warnings).casefold()
    return any(token in text for token in ("missing api token", "missing api key", "not configured", "requires"))


def _provider_backoff_from_warnings(warnings: Iterable[str]) -> bool:
    return "backoff" in " ".join(str(warning) for warning in warnings).casefold()


def _absence_meaningful_for_hint(provider_hint: str, coverage_status: str) -> bool:
    status = str(coverage_status or event_source_registry.ProviderCoverageStatus.COMPLETE.value)
    if status != event_source_registry.ProviderCoverageStatus.COMPLETE.value:
        return False
    hint = str(provider_hint or "").casefold()
    return hint in {"official_exchange", "project_blog_rss", "tokenomist", "coinalyze", "binance_announcements", "bybit_announcements"}


def _request_dedupe_key(request: EvidenceAcquisitionRequest | None) -> str | None:
    if request is None:
        return None
    if request.core_opportunity_id:
        return "|".join(("core", request.core_opportunity_id, request.source_pack))
    return "|".join(("asset", request.incident_id or "", request.coin_id or request.symbol, request.source_pack))


def _core_opportunity_id_for_row(row: Mapping[str, Any]) -> str | None:
    explicit = str(row.get("core_opportunity_id") or row.get("aggregated_candidate_id") or "").strip()
    if explicit:
        return explicit
    try:
        return event_core_opportunities.core_opportunity_id_for_row(row)
    except Exception:  # noqa: BLE001 - acquisition planning must fail soft.
        return None


def _evidence_status(
    status: str,
    *,
    accepted_evidence: Iterable[Mapping[str, Any]],
    rejected_evidence: Iterable[Mapping[str, Any]],
) -> str:
    if tuple(accepted_evidence):
        return "accepted_evidence_found"
    if tuple(rejected_evidence):
        return "rejected_only"
    if status == EvidenceAcquisitionStatus.NO_RESULTS.value:
        return "no_results"
    if status in {
        EvidenceAcquisitionStatus.FAILED_SOFT.value,
        EvidenceAcquisitionStatus.PROVIDER_UNAVAILABLE.value,
        EvidenceAcquisitionStatus.PROVIDER_BACKOFF.value,
    }:
        return "failed"
    return "no_results"


def _canonical_final_verdict(
    *,
    before: object | None,
    after: object | None,
    before_score: float,
    before_level: str,
    after_score: float,
    after_level: str,
    accepted: bool,
) -> tuple[float, str, str, str]:
    before_components = dict(getattr(before, "score_components", {}) or {})
    after_components = dict(getattr(after, "score_components", {}) or {})
    before_has_refresh = bool(before_components.get("market_refresh_success") or getattr(before, "market_refresh_success", False))
    after_has_refresh = bool(after_components.get("market_refresh_success") or getattr(after, "market_refresh_success", False))
    after_weaker = (
        _level_rank(after_level) < _level_rank(before_level)
        or after_score < before_score - 0.01
    )
    if before_has_refresh and after_weaker and not after_has_refresh:
        source = "market_refresh"
        reason = "preserved_stronger_market_refresh_verdict"
        return before_score, before_level, source, reason
    if accepted and after_has_refresh:
        return after_score, after_level, "combined_refresh", "accepted_evidence_with_market_refresh"
    if accepted:
        return after_score, after_level, "evidence_acquisition", "accepted_source_pack_evidence"
    if after_has_refresh:
        return after_score, after_level, "market_refresh", "market_refresh_verdict"
    return before_score, before_level, "initial", "no_canonical_refresh_change"


def _score_from_object(item: object | None, fallback: float) -> float:
    if item is None:
        return fallback
    components = dict(getattr(item, "score_components", {}) or {})
    return (
        _float(getattr(item, "final_opportunity_score", None))
        or _float(components.get("final_opportunity_score"))
        or _float(getattr(item, "opportunity_score_final", None))
        or _float(components.get("opportunity_score_final"))
        or _float(getattr(item, "hypothesis_score", None))
        or fallback
    )


def _level_from_object(item: object | None, fallback: str) -> str:
    if item is None:
        return fallback
    components = dict(getattr(item, "score_components", {}) or {})
    return str(
        getattr(item, "final_opportunity_level", "")
        or components.get("final_opportunity_level")
        or getattr(item, "opportunity_level", "")
        or components.get("opportunity_level")
        or fallback
    )


def _level_delta(before: str, after: str) -> str:
    diff = _level_rank(after) - _level_rank(before)
    if diff > 0:
        return "up"
    if diff < 0:
        return "down"
    return "unchanged"


def _level_rank(level: str | None) -> int:
    return {
        "local_only": 0,
        "exploratory": 1,
        "validated_digest": 2,
        "watchlist": 3,
        "high_priority": 4,
    }.get(str(level or "").casefold(), 0)


def _impact_path_rank(value: str | None) -> int:
    text = str(value or "").casefold()
    if "impact_path_validated" in text or "strong" in text:
        return 3
    if "catalyst_link_validated" in text or "medium" in text:
        return 2
    if text and "insufficient" not in text:
        return 1
    return 0


def _market_score_from_components(components: Mapping[str, Any]) -> float:
    return _float(components.get("market_confirmation_score") or components.get("market_confirmation")) or 0.0


def _market_level_from_components(components: Mapping[str, Any]) -> str | None:
    value = components.get("market_confirmation_level") or components.get("post_refresh_market_confirmation_level")
    return str(value) if value not in (None, "") else None


def _market_level_from_score(score: float) -> str | None:
    if score >= 70:
        return "strong"
    if score >= 40:
        return "moderate"
    if score > 0:
        return "weak"
    return "none"


def _market_freshness_from_components(components: Mapping[str, Any]) -> str | None:
    value = (
        components.get("market_data_freshness")
        or components.get("market_context_freshness_status")
        or _nested_market_freshness(components.get("market_context_after"))
        or _nested_market_freshness(components.get("market_context_before"))
    )
    return str(value) if value not in (None, "") else None


def _best_market_freshness(*components_list: Mapping[str, Any]) -> str | None:
    values = [
        _market_freshness_from_components(components)
        for components in components_list
        if isinstance(components, Mapping)
    ]
    for preferred in ("fresh", "fixture_allowed_stale", "stale", "unknown", "missing"):
        if preferred in values:
            return preferred
    return next((value for value in values if value), None)


def _nested_market_freshness(value: object) -> str | None:
    if not isinstance(value, Mapping):
        return None
    freshness = value.get("freshness_status") or value.get("data_quality")
    return str(freshness) if freshness not in (None, "") else None


def _components_for_final_verdict(
    *,
    final_source: str,
    before_components: Mapping[str, Any],
    after_components: Mapping[str, Any],
) -> Mapping[str, Any]:
    if final_source == "market_refresh":
        return before_components
    if final_source == "combined_refresh":
        merged = dict(before_components)
        merged.update({key: value for key, value in after_components.items() if value not in (None, "", [], {}, ())})
        before_score = _market_score_from_components(before_components)
        after_score = _market_score_from_components(after_components)
        if before_score > after_score:
            merged["market_confirmation_score"] = before_score
            before_level = _market_level_from_components(before_components) or _market_level_from_score(before_score)
            if before_level:
                merged["market_confirmation_level"] = before_level
        if not merged.get("market_context_freshness_status"):
            freshness = _market_freshness_from_components(before_components) or _market_freshness_from_components(after_components)
            if freshness:
                merged["market_context_freshness_status"] = freshness
        return merged
    return after_components or before_components


def _optional_delta(before: object, after: object) -> float | None:
    before_number = _float(before)
    after_number = _float(after)
    if before_number is None or after_number is None:
        return None
    return round(after_number - before_number, 2)


def _no_upgrade_reason(status: str, failures: Iterable[str]) -> str:
    if status == EvidenceAcquisitionStatus.NO_RESULTS.value:
        return "no_source_pack_results"
    if status == EvidenceAcquisitionStatus.REJECTED_RESULTS_ONLY.value:
        return "source_pack_results_rejected"
    if status in {EvidenceAcquisitionStatus.PROVIDER_UNAVAILABLE.value, EvidenceAcquisitionStatus.PROVIDER_BACKOFF.value}:
        return "provider_unavailable_or_backoff"
    if failures:
        return "provider_failures"
    return "no_accepted_evidence"


def _acquisition_id(opportunity_id: str, hypothesis_id: str | None, source_pack: str) -> str:
    seed = "|".join((opportunity_id, hypothesis_id or "", source_pack))
    return "acq:" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


def _float(value: object) -> float | None:
    try:
        if value in (None, "", [], {}, ()):
            return None
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _counts_line(counts: Mapping[str, int]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items())) or "none"


def _json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return _as_utc(value).isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _json_ready(child) for key, child in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item) for item in value]
    return value
