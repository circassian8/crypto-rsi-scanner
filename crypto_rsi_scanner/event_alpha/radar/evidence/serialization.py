"""Evidence acquisition artifact serialization helpers."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol

import crypto_rsi_scanner.event_alpha.radar.evidence_quality as event_evidence_quality
import crypto_rsi_scanner.event_alpha.radar.llm.evidence_planner as event_llm_evidence_planner
from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent
from ..resolver import clean_text
from ...providers import source_packs as event_source_packs
from ...providers import source_registry as event_source_registry
from ...operations import market_no_send_io
from .. import catalyst_search as event_catalyst_search
from .. import core_opportunities as event_core_opportunities
from .. import impact_hypotheses as event_impact_hypotheses
from .. import source_enrichment as event_source_enrichment
from .. import source_independence_store as event_source_independence_store
from .models import *  # noqa: F403 - split modules share historical model names


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
    if not rows:
        existing = market_no_send_io.read_regular_bytes(p, missing_ok=True)
        if existing is None:
            market_no_send_io.write_bytes_atomic(p, b"")
        return 0
    suffix = _persisted_jsonl_bytes(p, rows)
    existing = market_no_send_io.read_regular_bytes(p, missing_ok=True) or b""
    market_no_send_io.write_bytes_atomic(
        p,
        _append_jsonl_suffix(existing, suffix),
    )
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
                rows.append(
                    dict(event_source_independence_store.hydrate(p.parent, row))
                )
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
    changed = 0
    try:
        rows = market_no_send_io.read_jsonl(p)
    except (OSError, RuntimeError):
        return 0
    preserve_inline_digests = event_source_independence_store.inline_contract_digests(
        rows
    )
    core_rows = tuple(_row_from_object(item) for item in core_opportunity_rows)
    core_by_id = {
        str(row.get("core_opportunity_id") or "").strip(): row
        for row in core_rows
        if str(row.get("core_opportunity_id") or "").strip()
    }
    for row in rows:
        if row.get("row_type") != "event_evidence_acquisition":
            continue
        if run_id and str(row.get("run_id") or "") != str(run_id):
            continue
        if profile and str(row.get("profile") or "") != str(profile):
            continue
        if artifact_namespace and str(row.get("artifact_namespace") or row.get("namespace") or "") != str(artifact_namespace):
            continue
        resolution = event_core_opportunities.resolve_canonical_core_opportunity_id(row, core_rows)
        canonical = resolution.canonical_core_opportunity_id
        if not canonical:
            changed += _normalize_acquisition_final_fields(row)
            continue
        current = str(row.get("core_opportunity_id") or "").strip()
        if current != canonical:
            row["original_core_opportunity_id"] = current or None
            row["core_opportunity_id"] = canonical
            changed += 1
        core = core_by_id.get(canonical)
        if core:
            changed += _sync_acquisition_final_fields_from_core(row, core)
        changed += _normalize_acquisition_final_fields(row)
        row["core_opportunity_id_status"] = resolution.resolution_status
        if resolution.diagnostic_support_for_core_opportunity_id:
            row["diagnostic_support_for_core_opportunity_id"] = resolution.diagnostic_support_for_core_opportunity_id
        if resolution.warnings:
            existing = row.get("warnings") if isinstance(row.get("warnings"), list) else []
            row["warnings"] = list(dict.fromkeys([*existing, *resolution.warnings]))
    if changed:
        try:
            payload = _persisted_jsonl_bytes(
                p,
                rows,
                preserve_inline_digests=preserve_inline_digests,
            )
            market_no_send_io.write_bytes_atomic(p, payload)
        except (OSError, RuntimeError):
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
        rejected_display = (
            row.get("rejected_evidence_count")
            if row.get("rejected_evidence_count") is not None
            else len(row.get("rejected_evidence") or row.get("rejected_evidence_samples") or ())
        )
        lines.append(
            f"- {row.get('symbol') or row.get('coin_id') or 'UNKNOWN'} "
            f"pack={row.get('source_pack') or 'unknown'} status={row.get('status') or 'unknown'} "
            f"accepted={len(row.get('accepted_evidence') or ())} rejected={rejected_display} "
            f"score={row.get('opportunity_score_before')}->{row.get('opportunity_score_after')} "
            f"evidence={row.get('acquisition_evidence_status') or 'unknown'} "
            f"final={row.get('final_upgrade_status') or row.get('acquisition_upgrade_status') or 'unchanged'} "
            f"verdict={row.get('final_opportunity_level') or row.get('opportunity_level_after') or 'unknown'}"
        )
    lines.append("No sends, trades, paper rows, normal RSI rows, or trigger creation were performed.")
    return "\n".join(lines).rstrip()


def _artifact_row(
    result: EvidenceAcquisitionResult,
    *,
    context: Mapping[str, Any],
    observed_at: str,
) -> dict[str, Any]:
    query_metadata = tuple(query.to_metadata() for query in result.query_results)
    accepted_evidence = tuple(dict(item) for item in result.accepted_evidence)
    rejected_evidence = tuple(dict(item) for item in result.rejected_evidence)
    accepted_provider_counts = _provider_counts(result.accepted_evidence)
    rejected_provider_counts = _provider_counts(result.rejected_evidence)
    accepted_reason_code_counts = _reason_code_counts(result.accepted_evidence)
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
    row = {
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
        "accepted_evidence": accepted_evidence,
        "rejected_evidence": rejected_evidence,
        "rejected_evidence_samples": rejected_evidence[:5],
        "accepted_evidence_count": len(result.accepted_evidence),
        "rejected_evidence_count": len(result.rejected_evidence),
        "source_update_count": result.source_update_count,
        "independent_source_count": result.independent_source_count,
        "independent_corroboration_count": result.independent_corroboration_count,
        "source_content_cluster_count": result.source_content_cluster_count,
        "source_independence": dict(result.source_independence),
        "source_independence_status": result.source_independence_status,
        "source_independence_errors": list(result.source_independence_errors),
        "accepted_provider_counts": accepted_provider_counts,
        "rejected_provider_counts": rejected_provider_counts,
        "accepted_reason_code_counts": accepted_reason_code_counts,
        "evidence_acquisition_accepted_count": len(result.accepted_evidence),
        "evidence_acquisition_rejected_count": len(result.rejected_evidence),
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
    _normalize_acquisition_final_fields(row)
    return row


def _sync_acquisition_final_fields_from_core(row: dict[str, Any], core: Mapping[str, Any]) -> int:
    changed = 0
    mapping = {
        "final_opportunity_level": (
            core.get("final_opportunity_level")
            or core.get("opportunity_level")
        ),
        "opportunity_type": core.get("opportunity_type"),
        "final_route_after_quality_gate": core.get("final_route_after_quality_gate"),
        "final_state_after_quality_gate": core.get("final_state_after_quality_gate"),
        "final_opportunity_score": (
            core.get("final_opportunity_score")
            if core.get("final_opportunity_score") not in (None, "")
            else core.get("opportunity_score_final")
        ),
        "opportunity_score_final": core.get("opportunity_score_final"),
        "live_confirmation_status": core.get("live_confirmation_status"),
        "live_confirmation_reason": core.get("live_confirmation_reason"),
        "acquisition_confirmation_status": core.get("acquisition_confirmation_status"),
        "acquisition_confirms_candidate": core.get("acquisition_confirms_candidate"),
        "acquisition_confirms_impact_path": core.get("acquisition_confirms_impact_path"),
    }
    for key, value in mapping.items():
        if value in (None, "", [], {}, ()):
            continue
        if row.get(key) != value:
            row[key] = value
            changed += 1
    return changed


def _normalize_acquisition_final_fields(row: dict[str, Any]) -> int:
    accepted = _float(row.get("accepted_evidence_count") or row.get("evidence_acquisition_accepted_count")) or 0.0
    status = str(row.get("status") or row.get("evidence_acquisition_status") or "").casefold()
    acquisition_status = str(row.get("acquisition_evidence_status") or "").casefold()
    final_level = str(row.get("final_opportunity_level") or "").casefold()
    if accepted > 0:
        return 0
    if final_level not in PROMOTED_OPPORTUNITY_LEVELS:
        return 0
    if status not in UNCONFIRMED_ACQUISITION_STATUSES and acquisition_status not in {"rejected_only", "no_results", "failed"}:
        return 0
    changed = 0
    previous = row.get("final_opportunity_level")
    target = str(row.get("opportunity_level_after") or row.get("post_refresh_opportunity_level") or row.get("opportunity_level_before") or "exploratory")
    if str(target).casefold() in PROMOTED_OPPORTUNITY_LEVELS:
        target = "exploratory"
    row["final_opportunity_level_before_acquisition_normalization"] = previous
    row["final_opportunity_level"] = target
    if str(row.get("final_route_after_quality_gate") or "").upper() in {"RESEARCH_DIGEST", "WATCHLIST", "HIGH_PRIORITY_RESEARCH"}:
        row["final_route_after_quality_gate"] = "STORE_ONLY"
    if str(row.get("final_state_after_quality_gate") or "").upper() in {"WATCHLIST", "HIGH_PRIORITY"}:
        row["final_state_after_quality_gate"] = "RADAR"
    row["final_verdict_reason"] = row.get("final_verdict_reason") or _unconfirmed_acquisition_reason(status or acquisition_status)
    row["acquisition_final_level_normalized"] = True
    changed += 1
    return changed


def _unconfirmed_acquisition_reason(status: str) -> str:
    if status == "rejected_results_only" or status == "rejected_only":
        return "rejected_results_only_not_confirmation"
    if status == "skipped_budget":
        return "skipped_budget_not_confirmation"
    if status == "no_results":
        return "no_results_not_confirmation"
    if status in {"provider_unavailable", "provider_backoff", "failed"}:
        return "provider_unavailable_not_confirmation"
    return "evidence_acquisition_not_confirming"


def _provider_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        provider = str(
            row.get("provider")
            or row.get("provider_used")
            or row.get("provider_hint")
            or row.get("source_provider")
            or "unknown"
        ).strip() or "unknown"
        counts[provider] = counts.get(provider, 0) + 1
    return dict(sorted(counts.items()))


def _reason_code_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for code in row.get("reason_codes") or ():
            text = str(code or "").strip()
            if text:
                counts[text] = counts.get(text, 0) + 1
    return dict(sorted(counts.items()))


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


def _persisted_jsonl_bytes(
    path: Path,
    rows: Iterable[Mapping[str, Any]],
    *,
    preserve_inline_digests: frozenset[str] = frozenset(),
) -> bytes:
    lines: list[str] = []
    for row in rows:
        persisted = event_source_independence_store.externalize(
            path.parent,
            _json_ready(row),
            preserve_inline_digests=preserve_inline_digests,
        )
        lines.append(json.dumps(persisted, sort_keys=True, separators=(",", ":")))
    return (("\n".join(lines) + "\n") if lines else "").encode("utf-8")


def _append_jsonl_suffix(existing: bytes, suffix: bytes) -> bytes:
    if not suffix:
        return existing
    if existing and not existing.endswith(b"\n"):
        raise ValueError("existing evidence acquisition JSONL lacks a trailing newline")
    return existing + suffix
