"""Credential-free pilot audit construction for market/no-send generations."""

from __future__ import annotations

import json
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
    output_dir = namespace_dir or base
    json_path = output_dir / json_filename
    previous_audit = _load_previous_audit(json_path, namespace=namespace)
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
    _preserve_publication_history(audit, previous_audit=previous_audit)
    markdown_path = output_dir / markdown_filename
    write_json_atomic(json_path, audit)
    write_bytes_atomic(markdown_path, format_pilot_audit(audit).encode("utf-8"))
    return json_path, markdown_path, audit


def _load_previous_audit(path: Path, *, namespace: str) -> dict[str, Any]:
    """Load only history belonging to the same immutable namespace."""

    try:
        previous = read_json_object(path)
    except MarketNoSendError:
        return {}
    if previous.get("artifact_namespace") != namespace:
        return {}
    return previous


def _preserve_publication_history(
    audit: dict[str, Any],
    *,
    previous_audit: Mapping[str, Any],
) -> None:
    """Keep authority history monotonic while current pointer state may change."""

    publication = audit.get("publication")
    if not isinstance(publication, dict):
        return
    previous_publication = previous_audit.get("publication")
    previous_publication = (
        previous_publication if isinstance(previous_publication, Mapping) else {}
    )
    same_run = bool(
        audit.get("exact_run_id")
        and previous_audit.get("exact_run_id") == audit.get("exact_run_id")
    )
    if same_run and audit.get("exact_operator_revision") is None:
        audit["exact_operator_revision"] = previous_audit.get("exact_operator_revision")
    currently_published = publication.get("status") == "published"
    previously_published = bool(
        same_run
        and (
            previous_publication.get("ever_authoritative") is True
            or previous_publication.get("status") == "published"
        )
    )
    ever_authoritative = currently_published or previously_published
    publication["ever_authoritative"] = ever_authoritative
    binding = (
        _authority_binding(audit, publication)
        if currently_published
        else previous_publication.get("authority_binding")
    )
    if not isinstance(binding, Mapping) and previously_published:
        binding = _authority_binding(previous_audit, previous_publication)
    publication["authority_binding"] = dict(binding) if isinstance(binding, Mapping) else None
    first_authoritative_at: str | None = None
    if previously_published:
        previous_first = previous_publication.get("first_authoritative_at")
        if isinstance(previous_first, str) and previous_first.strip():
            first_authoritative_at = previous_first.strip()
        else:
            previous_generated_at = previous_audit.get("generated_at")
            if isinstance(previous_generated_at, str) and previous_generated_at.strip():
                first_authoritative_at = previous_generated_at.strip()
    if first_authoritative_at is None and currently_published:
        generated_at = audit.get("generated_at")
        if isinstance(generated_at, str) and generated_at.strip():
            first_authoritative_at = generated_at.strip()
    publication["first_authoritative_at"] = first_authoritative_at


def has_bound_publication_authority(
    audit: Mapping[str, Any],
    operator: Mapping[str, Any],
    *,
    namespace: str,
    run_id: str,
) -> bool:
    """Accept historical authority only with an exact immutable operator binding."""

    publication = audit.get("publication")
    if not isinstance(publication, Mapping):
        return False
    binding = (
        _authority_binding(audit, publication)
        if publication.get("status") == "published"
        else publication.get("authority_binding")
        if publication.get("ever_authoritative") is True
        else None
    )
    expected = {
        "artifact_namespace": namespace,
        "run_id": run_id,
        "revision": operator.get("revision"),
        "operator_state_sha256": _operator_digest(operator),
    }
    return bool(
        isinstance(binding, Mapping)
        and audit.get("artifact_namespace") == namespace
        and audit.get("exact_run_id") == run_id
        and audit.get("exact_operator_revision") == operator.get("revision")
        and all(binding.get(key) == value for key, value in expected.items())
        and expected["operator_state_sha256"]
    )


def _authority_binding(
    audit: Mapping[str, Any],
    publication: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "artifact_namespace": publication.get("pointer_namespace"),
        "run_id": publication.get("pointer_run_id"),
        "revision": publication.get("pointer_revision"),
        "operator_state_sha256": publication.get("pointer_operator_state_sha256"),
    }


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
    operator_digest = _operator_digest(operator)
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
        and manifest.get("decision_radar_campaign_counted") is True
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
    idea_quality = market_quality_counts(candidate_path) if candidate_path is not None else _empty_quality()
    provenance = (
        manifest.get("market_provenance")
        if isinstance(manifest.get("market_provenance"), Mapping)
        else {}
    )
    data_quality = (
        provenance.get("data_quality")
        if isinstance(provenance.get("data_quality"), Mapping)
        else {}
    )
    quality = {**_empty_quality(), **dict(data_quality)}
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
    quality["baseline_status"] = _baseline_status(quality)
    quality["baseline_observations_per_asset"] = _history_observations_per_asset(
        namespace_dir
    )
    route_counts = Counter(str(row.get("radar_route") or "diagnostic") for row in candidates)
    provider_call_attempted = _either_true(
        manifest,
        result_payload,
        "provider_call_attempted",
    )
    acquisition_mode = str(
        manifest.get("data_acquisition_mode")
        or result_payload.get("data_acquisition_mode")
        or "preflight_only"
    )
    return {
        "contract_version": 1,
        "pilot_audit_contract_version": 1,
        "market_provenance_contract_version": provenance.get("contract_version"),
        "market_provenance_schema_version": provenance.get("schema_version"),
        "row_type": "event_market_no_send_pilot_audit",
        "generated_at": checked_at.isoformat(),
        "artifact_namespace": namespace,
        "exact_run_id": manifest.get("run_id"),
        "exact_operator_revision": operator.get("revision"),
        "attempt_status": status,
        "provider": str(manifest.get("provider") or result_payload.get("provider") or "coingecko"),
        "provider_adapter_invoked": provider_call_attempted,
        "network_call_attempted": provider_call_attempted and acquisition_mode == "live_provider",
        "provider_call_attempted": provider_call_attempted,
        "provider_request_succeeded": _either_true(manifest, result_payload, "provider_request_succeeded"),
        "live_provider_authorized": _either_true(manifest, result_payload, "live_provider_authorized"),
        "data_acquisition_mode": acquisition_mode,
        "candidate_source_mode": str(manifest.get("candidate_source_mode") or result_payload.get("candidate_source_mode") or "preflight_only"),
        "provenance_contract_valid": manifest.get("provenance_contract_valid") is True,
        "measurement_program": manifest.get("measurement_program"),
        "decision_radar_campaign_eligible": manifest.get("decision_radar_campaign_eligible") is True,
        "decision_radar_campaign_counted": manifest.get("decision_radar_campaign_counted") is True,
        "decision_radar_campaign_reason": manifest.get("decision_radar_campaign_reason") or "generation_not_available",
        "burn_in_eligible": manifest.get("burn_in_eligible") is True,
        "burn_in_counted": manifest.get("burn_in_counted") is True,
        "burn_in_reason": manifest.get("burn_in_reason") or "generation_not_available",
        "request_lineage": _request_lineage(manifest),
        "history_lineage": {
            "history_artifact": manifest.get("market_history_artifact"),
            "history_sha256": manifest.get("market_history_sha256"),
        },
        "universe": universe_audit,
        "baseline": quality,
        "feature_basis": dict(provenance.get("feature_basis") or {}),
        "idea_quality": idea_quality,
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
        "spread_available_count": 0,
    }


def _operator_digest(operator: Mapping[str, Any]) -> str | None:
    if not operator:
        return None
    try:
        return operator_state.operator_authority_digest(operator)
    except (TypeError, ValueError):
        return None


def _baseline_status(quality: Mapping[str, Any]) -> str:
    counts = quality.get("baseline_status_counts")
    counts = counts if isinstance(counts, Mapping) else {}
    if int(counts.get("warm") or 0) > 0:
        return "warm"
    if int(counts.get("warming") or 0) > 0:
        return "warming"
    if int(counts.get("cold") or 0) > 0:
        return "cold"
    return "not_evaluated"


def _history_observations_per_asset(namespace_dir: Path | None) -> dict[str, int]:
    if namespace_dir is None:
        return {}
    counts: Counter[str] = Counter()
    for row in read_jsonl(namespace_dir / "event_market_history.jsonl"):
        asset_id = str(
            row.get("coin_id")
            or row.get("canonical_asset_id")
            or row.get("symbol")
            or ""
        ).strip()
        if asset_id:
            counts[asset_id] += 1
    return dict(sorted(counts.items()))


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
    feature_basis = audit.get("feature_basis") if isinstance(audit.get("feature_basis"), Mapping) else {}
    observations = (
        baseline.get("baseline_observations_per_asset")
        if isinstance(baseline.get("baseline_observations_per_asset"), Mapping)
        else {}
    )
    baseline_counts = (
        baseline.get("baseline_status_counts")
        if isinstance(baseline.get("baseline_status_counts"), Mapping)
        else {}
    )
    lines = [
        "# Crypto Decision Radar market/no-send pilot audit",
        "",
        "Research-only. Human decision support; no trades, paper trades, RSI writes, fade triggers, or sends.",
        "",
        f"- pilot_audit_contract_version: {audit.get('pilot_audit_contract_version')}",
        f"- market_provenance_contract_version: {audit.get('market_provenance_contract_version')}",
        f"- market_provenance_schema_version: {audit.get('market_provenance_schema_version')}",
        f"- exact_namespace: {audit.get('artifact_namespace')}",
        f"- exact_run_id: {audit.get('exact_run_id')}",
        f"- exact_operator_revision: {audit.get('exact_operator_revision')}",
        f"- attempt_status: {audit.get('attempt_status')}",
        f"- provider: {audit.get('provider')}",
        f"- live_provider_authorized: {str(audit.get('live_provider_authorized')).lower()}",
        f"- provider_adapter_invoked: {str(audit.get('provider_adapter_invoked')).lower()}",
        f"- network_call_attempted: {str(audit.get('network_call_attempted')).lower()}",
        f"- provider_call_attempted: {str(audit.get('provider_call_attempted')).lower()}",
        f"- provider_request_succeeded: {str(audit.get('provider_request_succeeded')).lower()}",
        f"- data_acquisition_mode: {audit.get('data_acquisition_mode')}",
        f"- candidate_source_mode: {audit.get('candidate_source_mode')}",
        f"- provenance_contract_valid: {str(audit.get('provenance_contract_valid')).lower()}",
        f"- measurement_program: {audit.get('measurement_program')}",
        f"- decision_radar_campaign_counted: {str(audit.get('decision_radar_campaign_counted')).lower()}",
        f"- event_alpha_burn_in_counted: {str(audit.get('burn_in_counted')).lower()}",
        f"- universe_fetched/kept/excluded: {universe.get('fetched_count', 0)}/{universe.get('kept_count', 0)}/{universe.get('excluded_count', 0)}",
        f"- baseline_status: {baseline.get('baseline_status')}",
        "- baseline_cold/warming/warm: "
        f"{baseline_counts.get('cold', 0)}/{baseline_counts.get('warming', 0)}/{baseline_counts.get('warm', 0)}",
        f"- baseline_cache_scope: {baseline.get('cache_scope')}",
        f"- baseline_shared_seed_rows: {baseline.get('shared_seed_rows', 0)}",
        f"- market_features_direct/proxy: {baseline.get('direct_feature_count', 0)}/{baseline.get('proxy_feature_count', 0)}",
        f"- spread_available_assets: {baseline.get('spread_available_count', 0)}",
        f"- market_anomaly_count: {audit.get('market_anomaly_count')}",
        f"- candidate_count: {audit.get('candidate_count')}",
        f"- outcome_placeholder_count: {audit.get('outcome_placeholder_count')}",
        f"- publication_status: {publication.get('status')}",
        f"- publication_reason: {publication.get('reason')}",
        f"- ever_authoritative: {str(publication.get('ever_authoritative') is True).lower()}",
        f"- first_authoritative_at: {publication.get('first_authoritative_at')}",
        f"- pointer_namespace: {publication.get('pointer_namespace')}",
        f"- strict_doctor_status/blockers: {doctor.get('status', 'not_run')}/{doctor.get('blocker_count', 'unknown')}",
        f"- dashboard_trusted_current: {str(dashboard.get('trusted_current') is True).lower()}",
        f"- safety_zero: {all(value in (0, True) for value in safety.values())}",
        f"- next_safe_command: {audit.get('next_safe_command')}",
        "",
    ]
    lines.extend(["## Baseline observations per asset", ""])
    if observations:
        lines.extend(f"- {key}: {value}" for key, value in sorted(observations.items()))
    else:
        lines.append("- none")
    lines.extend(["", "## Feature basis", ""])
    if feature_basis:
        lines.extend(f"- {key}: {value}" for key, value in sorted(feature_basis.items()))
    else:
        lines.append("- none")
    lines.extend(["", "## Decision routes", ""])
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
