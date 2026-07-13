"""Credential-free pilot audit construction for market/no-send generations."""

from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..artifacts import operator_state
from ..dashboard.readiness import DashboardReadinessError, read_current_namespace_pointer
from ..radar.integrated import api as integrated_radar
from .market_no_send_features import finite_float, market_quality_counts
from .market_no_send_io import (
    read_json_object,
    read_jsonl,
    read_regular_bytes,
    safe_existing_namespace_dir,
    write_bytes_atomic,
    write_json_atomic,
)
from .market_no_send_models import (
    MarketNoSendError,
    MarketNoSendGenerationResult,
    MarketNoSendReadiness,
)


def write_pilot_audit(
    *,
    base: Path,
    namespace: str,
    checked_at: datetime,
    readiness: MarketNoSendReadiness,
    result: MarketNoSendGenerationResult | None,
    manifest_filename: str,
    json_filename: str,
    markdown_filename: str,
    safety_counters: Mapping[str, int],
) -> tuple[Path, Path, dict[str, Any]]:
    """Write JSON and Markdown summaries without provider calls."""

    namespace_dir, manifest, candidates, outcomes, operator = _load_generation(
        base,
        namespace,
        manifest_filename=manifest_filename,
    )
    pointer = _read_pointer(base)
    audit = _build_audit(
        namespace=namespace,
        checked_at=checked_at,
        readiness=readiness,
        result=result,
        namespace_dir=namespace_dir,
        manifest=manifest,
        candidates=candidates,
        outcomes=outcomes,
        operator=operator,
        pointer=pointer,
        safety_counters=safety_counters,
    )
    output_dir = namespace_dir or base
    json_path = output_dir / json_filename
    markdown_path = output_dir / markdown_filename
    write_json_atomic(json_path, audit)
    write_bytes_atomic(markdown_path, format_pilot_audit(audit).encode("utf-8"))
    return json_path, markdown_path, audit


def _load_generation(
    base: Path,
    namespace: str,
    *,
    manifest_filename: str,
) -> tuple[
    Path | None,
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    try:
        namespace_dir = safe_existing_namespace_dir(base, namespace)
    except MarketNoSendError:
        return None, {}, [], [], {}
    try:
        manifest = read_json_object(namespace_dir / manifest_filename)
    except MarketNoSendError:
        manifest = {}
    candidates = read_jsonl(namespace_dir / integrated_radar.INTEGRATED_CANDIDATES_FILENAME)
    outcomes = read_jsonl(namespace_dir / integrated_radar.INTEGRATED_OUTCOMES_FILENAME)
    loaded = operator_state.load_operator_state(namespace_dir)
    operator = dict(loaded.state or {}) if loaded.valid else {}
    return namespace_dir, manifest, candidates, outcomes, operator


def _read_pointer(base: Path) -> dict[str, Any]:
    try:
        return dict(read_current_namespace_pointer(base))
    except DashboardReadinessError as exc:
        return {"status": "unavailable", "reason": str(exc)}


def _build_audit(
    *,
    namespace: str,
    checked_at: datetime,
    readiness: MarketNoSendReadiness,
    result: MarketNoSendGenerationResult | None,
    namespace_dir: Path | None,
    manifest: Mapping[str, Any],
    candidates: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
    operator: Mapping[str, Any],
    pointer: Mapping[str, Any],
    safety_counters: Mapping[str, int],
) -> dict[str, Any]:
    result_payload = result.to_dict() if result is not None else {}
    doctor = operator.get("doctor") if isinstance(operator.get("doctor"), Mapping) else {}
    status = str(manifest.get("status") or result_payload.get("status") or "blocked")
    operator_digest = _operator_digest(namespace_dir)
    points_to_attempt = bool(
        pointer.get("artifact_namespace") == namespace
        and pointer.get("run_id") == manifest.get("run_id")
        and pointer.get("revision") == operator.get("revision")
        and pointer.get("operator_state_sha256") == operator_digest
    )
    publishable = bool(
        status == "complete"
        and manifest.get("candidate_source_mode") == "live_no_send"
        and manifest.get("provenance_contract_valid") is True
        and manifest.get("burn_in_counted") is True
        and doctor.get("authoritative") is True
        and doctor.get("blocker_count") == 0
    )
    publication_status, publication_reason = _publication_state(
        points_to_attempt=points_to_attempt,
        publishable=publishable,
        authorized=readiness.live_provider_authorized,
        has_manifest=bool(manifest),
    )
    candidate_path = (
        namespace_dir / integrated_radar.INTEGRATED_CANDIDATES_FILENAME
        if namespace_dir is not None else None
    )
    universe_audit = manifest.get("universe_audit")
    universe_audit = dict(universe_audit) if isinstance(universe_audit, Mapping) else {}
    quality = market_quality_counts(candidate_path) if candidate_path is not None else _empty_quality()
    history = universe_audit.get("market_history")
    if isinstance(history, Mapping):
        retention = history.get("retention")
        quality.update({
            "cache_scope": history.get("cache_scope"),
            "shared_cache_namespace": history.get("shared_cache_namespace"),
            "shared_seed_rows": int(history.get("shared_seed_rows") or 0),
            "generation_seed_rows": int(history.get("generation_seed_rows") or 0),
            "retention": dict(retention) if isinstance(retention, Mapping) else {},
        })
    route_counts = Counter(str(row.get("radar_route") or "diagnostic") for row in candidates)
    return {
        "contract_version": 1,
        "row_type": "event_market_no_send_pilot_audit",
        "generated_at": checked_at.isoformat(),
        "artifact_namespace": namespace,
        "attempt_status": status,
        "provider": str(manifest.get("provider") or result_payload.get("provider") or "coingecko"),
        "provider_call_attempted": _either_true(manifest, result_payload, "provider_call_attempted"),
        "provider_request_succeeded": _either_true(manifest, result_payload, "provider_request_succeeded"),
        "live_provider_authorized": _either_true(manifest, result_payload, "live_provider_authorized"),
        "data_acquisition_mode": str(manifest.get("data_acquisition_mode") or result_payload.get("data_acquisition_mode") or "preflight_only"),
        "candidate_source_mode": str(manifest.get("candidate_source_mode") or result_payload.get("candidate_source_mode") or "preflight_only"),
        "provenance_contract_valid": manifest.get("provenance_contract_valid") is True,
        "burn_in_eligible": manifest.get("burn_in_eligible") is True,
        "burn_in_counted": manifest.get("burn_in_counted") is True,
        "burn_in_reason": manifest.get("burn_in_reason") or "generation_not_available",
        "request_lineage": _request_lineage(manifest),
        "universe": universe_audit,
        "baseline": quality,
        "market_anomaly_count": int(manifest.get("market_anomaly_count") or 0),
        "candidate_count": len(candidates),
        "outcome_placeholder_count": len(outcomes),
        "candidate_outcome_count_match": len(candidates) == len(outcomes),
        "decision_route_counts": dict(sorted(route_counts.items())),
        "score_distributions": score_distributions(candidates),
        "visible_ideas": _visible_ideas(candidates),
        "doctor": dict(doctor),
        "publication": {
            "status": publication_status,
            "reason": publication_reason,
            "pointer_namespace": pointer.get("artifact_namespace"),
            "pointer_run_id": pointer.get("run_id"),
            "pointer_revision": pointer.get("revision"),
            "pointer_operator_state_sha256": pointer.get("operator_state_sha256"),
            "points_to_attempt": points_to_attempt,
        },
        "dashboard": {
            "url": "http://127.0.0.1:8765/",
            "trusted_current": points_to_attempt and publishable,
            "exact_run_id": manifest.get("run_id"),
            "operator_revision": operator.get("revision"),
        },
        "safety": {**dict(safety_counters), "no_send": True, "research_only": True},
        "next_safe_command": "make radar-dashboard" if points_to_attempt else readiness.next_safe_command,
    }


def _publication_state(
    *,
    points_to_attempt: bool,
    publishable: bool,
    authorized: bool,
    has_manifest: bool,
) -> tuple[str, str]:
    if points_to_attempt and publishable:
        return "published", "strict_clean_exact_generation"
    if points_to_attempt:
        return "not_published", "pointer_does_not_reference_a_publishable_generation"
    if not authorized and not has_manifest:
        return "not_attempted", "live_provider_authorization_missing"
    if not publishable:
        return "not_published", "generation_or_strict_doctor_not_publishable"
    return "not_published", "pointer_publication_not_completed"


def _empty_quality() -> dict[str, Any]:
    return {
        "baseline_status": "not_evaluated",
        "baseline_status_counts": {},
        "baseline_warm_assets": 0,
        "baseline_warming_assets": 0,
        "direct_feature_count": 0,
        "proxy_feature_count": 0,
    }


def _operator_digest(namespace_dir: Path | None) -> str | None:
    if namespace_dir is None:
        return None
    try:
        data = read_regular_bytes(
            namespace_dir / operator_state.OPERATOR_STATE_FILENAME
        )
    except MarketNoSendError:
        return None
    return hashlib.sha256(data).hexdigest()


def _request_lineage(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source_artifact": manifest.get("request_cache_artifact"),
        "source_sha256": manifest.get("request_cache_sha256"),
        "request_ledger": manifest.get("request_ledger_artifact"),
        "request_ledger_sha256": manifest.get("request_ledger_sha256"),
    }


def _either_true(
    first: Mapping[str, Any],
    second: Mapping[str, Any],
    key: str,
) -> bool:
    return first.get(key) is True or second.get(key) is True


def _visible_ideas(candidates: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": row.get("candidate_id"),
            "symbol": row.get("symbol"),
            "route": row.get("radar_route"),
            "actionable": row.get("radar_actionable") is True,
            "actionability_score": row.get("actionability_score"),
            "evidence_confidence_score": row.get("evidence_confidence_score"),
            "risk_score": row.get("risk_score"),
            "spread_status": row.get("spread_status"),
        }
        for row in candidates
        if str(row.get("radar_route") or "diagnostic") != "diagnostic"
    ][:20]


def score_distributions(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, int]]:
    output: dict[str, dict[str, int]] = {}
    for field in ("actionability_score", "evidence_confidence_score", "risk_score"):
        counts: Counter[str] = Counter()
        for row in rows:
            value = finite_float(row.get(field))
            if value is None:
                counts["missing"] += 1
            elif value < 25:
                counts["0_24"] += 1
            elif value < 50:
                counts["25_49"] += 1
            elif value < 70:
                counts["50_69"] += 1
            elif value < 85:
                counts["70_84"] += 1
            else:
                counts["85_100"] += 1
        output[field] = dict(sorted(counts.items()))
    return output


def format_pilot_audit(audit: Mapping[str, Any]) -> str:
    publication = audit.get("publication") if isinstance(audit.get("publication"), Mapping) else {}
    baseline = audit.get("baseline") if isinstance(audit.get("baseline"), Mapping) else {}
    safety = audit.get("safety") if isinstance(audit.get("safety"), Mapping) else {}
    universe = audit.get("universe") if isinstance(audit.get("universe"), Mapping) else {}
    lineage = audit.get("request_lineage") if isinstance(audit.get("request_lineage"), Mapping) else {}
    doctor = audit.get("doctor") if isinstance(audit.get("doctor"), Mapping) else {}
    dashboard = audit.get("dashboard") if isinstance(audit.get("dashboard"), Mapping) else {}
    lines = [
        "# Crypto Decision Radar market/no-send pilot audit",
        "",
        "Research-only. Human decision support; no trades, paper trades, RSI writes, fade triggers, or sends.",
        "",
        f"- attempt_status: {audit.get('attempt_status')}",
        f"- provider: {audit.get('provider')}",
        f"- live_provider_authorized: {str(audit.get('live_provider_authorized')).lower()}",
        f"- provider_call_attempted: {str(audit.get('provider_call_attempted')).lower()}",
        f"- provider_request_succeeded: {str(audit.get('provider_request_succeeded')).lower()}",
        f"- data_acquisition_mode: {audit.get('data_acquisition_mode')}",
        f"- candidate_source_mode: {audit.get('candidate_source_mode')}",
        f"- provenance_contract_valid: {str(audit.get('provenance_contract_valid')).lower()}",
        f"- burn_in_counted: {str(audit.get('burn_in_counted')).lower()}",
        f"- universe_fetched/kept/excluded: {universe.get('fetched_count', 0)}/{universe.get('kept_count', 0)}/{universe.get('excluded_count', 0)}",
        f"- baseline_status: {baseline.get('baseline_status')}",
        f"- baseline_cache_scope: {baseline.get('cache_scope')}",
        f"- baseline_shared_seed_rows: {baseline.get('shared_seed_rows', 0)}",
        f"- market_features_direct/proxy: {baseline.get('direct_feature_count', 0)}/{baseline.get('proxy_feature_count', 0)}",
        f"- spread_available_assets: {universe.get('spread_available_count', 0)}",
        f"- market_anomaly_count: {audit.get('market_anomaly_count')}",
        f"- candidate_count: {audit.get('candidate_count')}",
        f"- outcome_placeholder_count: {audit.get('outcome_placeholder_count')}",
        f"- publication_status: {publication.get('status')}",
        f"- publication_reason: {publication.get('reason')}",
        f"- pointer_namespace: {publication.get('pointer_namespace')}",
        f"- strict_doctor_status/blockers: {doctor.get('status', 'not_run')}/{doctor.get('blocker_count', 'unknown')}",
        f"- dashboard_trusted_current: {str(dashboard.get('trusted_current') is True).lower()}",
        f"- safety_zero: {all(value in (0, True) for value in safety.values())}",
        f"- next_safe_command: {audit.get('next_safe_command')}",
        "",
        "## Decision routes",
        "",
    ]
    route_counts = audit.get("decision_route_counts")
    if isinstance(route_counts, Mapping) and route_counts:
        lines.extend(f"- {key}: {value}" for key, value in sorted(route_counts.items()))
    else:
        lines.append("- none")
    lines.extend(["", "## Score distributions", ""])
    distributions = audit.get("score_distributions")
    if isinstance(distributions, Mapping) and distributions:
        for field, buckets in sorted(distributions.items()):
            values = buckets if isinstance(buckets, Mapping) else {}
            lines.append(
                f"- {field}: "
                + ", ".join(f"{key}={value}" for key, value in sorted(values.items()))
            )
    else:
        lines.append("- none")
    exclusions = universe.get("excluded_by_reason")
    lines.extend(["", "## Universe exclusions", ""])
    if isinstance(exclusions, Mapping) and exclusions:
        lines.extend(f"- {key}: {value}" for key, value in sorted(exclusions.items()))
    else:
        lines.append("- none")
    lines.extend(["", "## Request/cache lineage", ""])
    lines.extend(
        f"- {key}: {lineage.get(key)}"
        for key in ("source_artifact", "source_sha256", "request_ledger", "request_ledger_sha256")
    )
    lines.extend(["", "## Visible research ideas", ""])
    visible = audit.get("visible_ideas")
    if isinstance(visible, list) and visible:
        lines.extend(
            f"- {item.get('symbol')}: route={item.get('route')} "
            f"actionability={item.get('actionability_score')} "
            f"evidence={item.get('evidence_confidence_score')} "
            f"risk={item.get('risk_score')} spread={item.get('spread_status')}"
            for item in visible
            if isinstance(item, Mapping)
        )
    else:
        lines.append("- none")
    lines.extend(["", "## Safety counters", ""])
    lines.extend(f"- {key}: {value}" for key, value in sorted(safety.items()))
    lines.append("")
    return "\n".join(lines)
