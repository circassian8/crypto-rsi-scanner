"""Deterministic Decision Radar live-observation campaign reporting.

The report is built only from local artifacts.  It never calls providers,
sends notifications, mutates a generation namespace, or changes decision
policy.  Historical market-provenance v2 ``burn_in_*`` fields are accepted only
through a read-only compatibility adapter and are exposed as Decision Radar
campaign measurements rather than Event Alpha catalyst burn-in evidence.
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ..outcomes import outcome_eligibility
from ..dashboard import readiness as dashboard_readiness
from ..dashboard.readiness import CURRENT_NAMESPACE_POINTER
from ..radar.integrated import api as integrated_radar
from . import daily_operations_publication
from . import decision_review_timing
from . import market_no_send_audit, market_no_send_history_cache
from . import market_no_send_publication
from . import market_observation_campaign_attempts
from . import market_observation_campaign_baseline
from . import market_observation_campaign_cadence
from . import market_observation_campaign_contract
from . import market_observation_campaign_episodes
from . import market_observation_campaign_scorecard
from . import market_observation_campaign_snapshots
from . import market_observation_outcomes
from .market_no_send_models import SAFETY_COUNTERS
from .market_no_send_io import read_json_object, read_jsonl, safe_existing_namespace_dir
from .market_no_send_models import MarketNoSendError
from .market_observation_campaign_render import (
    format_campaign_report as _render_campaign_report,
)


CAMPAIGN_PROGRAM = "decision_radar_live_observation_campaign_v2"
CAMPAIGN_REPORT_SCHEMA = "decision_radar_live_observation_campaign_report_v2"
CAMPAIGN_REPORT_JSON_FILENAME = "RADAR_LIVE_OBSERVATION_CAMPAIGN_REPORT.json"
CAMPAIGN_REPORT_MD_FILENAME = "RADAR_LIVE_OBSERVATION_CAMPAIGN_REPORT.md"
CAMPAIGN_OUTCOMES_FILENAME = "event_decision_radar_campaign_outcomes.jsonl"
RUN_MANIFEST_FILENAME = "event_market_no_send_generation.json"
PILOT_AUDIT_FILENAME = "event_market_no_send_pilot_audit.json"
PREPUBLICATION_AUDIT_FILENAME = (
    daily_operations_publication.PREPUBLICATION_AUDIT_FILENAME
)
PUBLICATION_RECEIPT_FILENAME = daily_operations_publication.PUBLICATION_RECEIPT_FILENAME
OPERATIONS_RECEIPT_FILENAME = daily_operations_publication.OPERATIONS_RECEIPT_FILENAME
REQUEST_LEDGER_FILENAME = "event_market_no_send_request_ledger.json"
HISTORY_FILENAME = "event_market_history.jsonl"
OPERATOR_STATE_FILENAME = "event_alpha_operator_state.json"

_attempt_row = market_observation_campaign_attempts.attempt_row
_attempt_sort_key = market_observation_campaign_attempts.attempt_sort_key
_deduplicate_attempts = market_observation_campaign_attempts.deduplicate_attempts
_is_live_market_attempt = market_observation_campaign_attempts.is_live_market_attempt
_load_root_attempts = market_observation_campaign_attempts.load_root_attempts

_SAFETY_COUNTER_FIELDS = (
    "telegram_sends",
    "trades_created",
    "paper_trades_created",
    "normal_rsi_signal_rows_written",
    "triggered_fade_created",
)
_MATURED_STATES = {"matured", "complete", "completed", "filled", "observed", "scored"}
_PENDING_STATES = {"pending", "not_due", "partially_matured"}
_MISSING_STATES = {"due_missing_price", "missing", "missing_data", "missing_price_data", "unavailable"}


def build_campaign_report(
    artifact_base_dir: str | Path,
    *,
    evaluated_at: datetime | str,
) -> dict[str, Any]:
    """Build one deterministic campaign report from local evidence."""

    base = _validated_existing_directory(artifact_base_dir, label="artifact base")
    evaluated = _require_aware_utc(evaluated_at, field_name="evaluated_at")
    pointer = _read_json(base / CURRENT_NAMESPACE_POINTER)
    current_authority, authority_error = _resolve_current_authority(
        base,
        evaluated=evaluated,
    )
    generations, generation_attempts, excluded_generations = _load_generations(
        base,
        current_authority=current_authority,
    )
    root_attempts = _load_root_attempts(base)
    attempts = _deduplicate_attempts((*generation_attempts, *root_attempts))

    authoritative = [
        row for row in generations if row["publication"]["ever_authoritative"] is True
    ]
    non_authoritative = [
        row for row in generations if row["publication"]["ever_authoritative"] is False
    ]
    provider_failed = [
        row
        for row in attempts
        if row["provider_call_attempted"] is True
        and row["provider_request_succeeded"] is False
    ]
    blocked = [
        row
        for row in attempts
        if row["provider_call_attempted"] is False
        or row["attempt_status"] in {"blocked", "preflight_only", "not_attempted"}
    ]

    counted_generations = [row for row in generations if row["campaign_counted"] is True]
    episode_input_generations = [
        *counted_generations,
        *(
            dict(value)
            for row in excluded_generations
            if isinstance(
                value := row.get("_candidate_snapshot_episode_input"),
                Mapping,
            )
        ),
    ]
    ledger_snapshot = market_observation_campaign_snapshots.campaign_outcome_ledger_snapshot(
        base,
        history_namespace=market_no_send_history_cache.LIVE_HISTORY_CACHE_NAMESPACE,
        filename=CAMPAIGN_OUTCOMES_FILENAME,
    )
    outcomes = _campaign_outcomes(
        base,
        counted_generations,
        ledger_snapshot=ledger_snapshot,
    )
    outcome_metrics = _outcome_metrics(outcomes)
    review_timing = decision_review_timing.build_review_timing_report(
        base,
        evaluated_at=evaluated,
    )
    episode_shadow, episode_input_audit = (
        market_observation_campaign_episodes.build_campaign_anomaly_episode_shadow(
            base,
            episode_input_generations,
            evaluated_at=evaluated,
            outcome_ledger_rows=ledger_snapshot["rows"],
            outcome_ledger_status=ledger_snapshot["status"],
            outcome_ledger_sha256=ledger_snapshot["sha256"],
        )
    )
    episode_scorecard = (
        market_observation_campaign_scorecard.build_campaign_decision_episode_scorecard(
            episode_shadow,
            episode_input_generations,
            ledger_snapshot,
            evaluated_at=evaluated,
        )
    )
    baseline = market_observation_campaign_baseline.build_baseline_maturity(
        base,
        evaluated=evaluated,
        history_filename=HISTORY_FILENAME,
        current_asset_ids=current_authority.get("_current_asset_ids"),
    )
    metrics = _campaign_metrics(counted_generations, outcome_metrics, baseline)
    metrics.update(decision_review_timing.campaign_metric_values(review_timing))
    metrics["provider_failed_attempts"] = len(provider_failed)
    metrics["blocked_attempts"] = len(blocked)
    pointer_state = _pointer_state(
        pointer,
        generations,
        current_authority=current_authority,
        authority_error=authority_error,
    )
    next_observation = market_observation_campaign_cadence.next_observation(
        base,
        baseline,
        evaluated=evaluated,
    )
    limitations = _data_quality_limitations(metrics)
    status = _campaign_status(metrics, baseline)
    pointer_history = _pointer_history(authoritative, pointer_state)
    conclusion = _campaign_conclusion(
        status=status,
        metrics=metrics,
        baseline=baseline,
        pointer=pointer_state,
        pointer_history=pointer_history,
        provider_failed=provider_failed,
        blocked=blocked,
        limitations=limitations,
    )
    return market_observation_campaign_contract.build_report_value(
        schema_id=CAMPAIGN_REPORT_SCHEMA,
        measurement_program=CAMPAIGN_PROGRAM,
        generated_at=evaluated.isoformat(),
        status=status,
        metrics=metrics,
        baseline=baseline,
        authoritative=authoritative,
        non_authoritative=non_authoritative,
        provider_failed=provider_failed,
        blocked=blocked,
        excluded=excluded_generations,
        valid_generation_count=len(generations),
        pointer=pointer_state,
        pointer_history=pointer_history,
        outcome_metrics=outcome_metrics,
        review_timing=review_timing,
        episode_shadow=episode_shadow,
        episode_input_audit=episode_input_audit,
        episode_scorecard=episode_scorecard,
        limitations=limitations,
        next_observation=next_observation,
        conclusion=conclusion,
    )


def write_campaign_report(
    artifact_base_dir: str | Path,
    output_dir: str | Path,
    *,
    evaluated_at: datetime | str | None = None,
) -> tuple[Path, Path, dict[str, Any]]:
    """Write the canonical JSON/Markdown pair without mutating input artifacts."""

    evaluated = (
        datetime.now(timezone.utc)
        if evaluated_at is None
        else _require_aware_utc(evaluated_at, field_name="evaluated_at")
    )
    report = build_campaign_report(artifact_base_dir, evaluated_at=evaluated)
    _validate_shadow_campaign_contracts(report)
    destination = _validated_existing_directory(output_dir, label="campaign output")
    json_path = destination / CAMPAIGN_REPORT_JSON_FILENAME
    markdown_path = destination / CAMPAIGN_REPORT_MD_FILENAME
    _write_atomic(
        json_path,
        (json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode(
            "utf-8"
        ),
    )
    _write_atomic(markdown_path, format_campaign_report(report).encode("utf-8"))
    return json_path, markdown_path, report


def format_campaign_report(report: Mapping[str, Any]) -> str:
    """Render the canonical report as deterministic operator-facing Markdown."""

    _validate_shadow_campaign_contracts(report)
    return _render_campaign_report(report)


def _validate_shadow_campaign_contracts(report: Mapping[str, Any]) -> None:
    from ..outcomes import anomaly_episode_shadow, decision_episode_scorecard

    value = _mapping(report.get("shadow_anomaly_episodes"))
    errors = anomaly_episode_shadow.validate_contract(value)
    if errors:
        raise MarketNoSendError(
            "shadow anomaly episode report contract invalid: " + ";".join(errors)
        )
    audit_errors = market_observation_campaign_episodes.validate_input_audit(
        _mapping(report.get("shadow_anomaly_episode_input_audit")),
        episode_value=value,
    )
    if audit_errors:
        raise MarketNoSendError(
            "shadow anomaly episode input audit invalid: "
            + ";".join(audit_errors)
        )
    scorecard_errors = decision_episode_scorecard.validate_contract(
        _mapping(report.get("decision_v2_episode_outcome_scorecard")),
        episode_value=value,
    )
    if scorecard_errors:
        raise MarketNoSendError(
            "decision episode scorecard report contract invalid: "
            + ";".join(scorecard_errors)
        )


def _load_generations(
    base: Path,
    *,
    current_authority: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    generations: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for namespace in _namespace_names(base):
        namespace_dir = safe_existing_namespace_dir(base, namespace)
        manifest = _read_json(namespace_dir / RUN_MANIFEST_FILENAME)
        pilot_audit = _read_json(namespace_dir / PILOT_AUDIT_FILENAME)
        audit = (
            _read_json(namespace_dir / PREPUBLICATION_AUDIT_FILENAME)
            or pilot_audit
        )
        if not manifest and not audit:
            continue
        if not _is_live_market_attempt(manifest, audit):
            continue
        status = _text(manifest.get("status") or audit.get("attempt_status") or "unknown")
        attempted = _strict_true(manifest, audit, "provider_call_attempted")
        succeeded = _strict_true(manifest, audit, "provider_request_succeeded")
        if status != "complete" or succeeded is not True:
            attempts.append(_attempt_row(manifest, audit, namespace=namespace))
            continue
        validation = market_no_send_publication.validate_countable_campaign_generation(
            manifest,
            namespace_dir=namespace_dir,
            namespace=namespace,
            contract_version=2,
            default_profile="no_key_live",
            request_cache_filename="event_market_no_send_market_rows.json",
            request_ledger_filename=REQUEST_LEDGER_FILENAME,
            safety_counters=SAFETY_COUNTERS,
            candidates_filename=integrated_radar.INTEGRATED_CANDIDATES_FILENAME,
        )
        if not validation.valid:
            excluded.append({
                "artifact_namespace": namespace,
                "run_id": _text(manifest.get("run_id") or audit.get("exact_run_id")) or None,
                "observed_at": _safe_timestamp(
                    manifest.get("observed_at") or audit.get("generated_at")
                ),
                "validation_errors": list(validation.validation_errors),
                "campaign_counting_source": validation.counting_source,
                "campaign_counting_reason": validation.counting_reason,
            })
            continue
        try:
            generation = _generation_row(
                namespace_dir,
                manifest=manifest,
                audit=audit,
                validation=validation,
                current_authority=current_authority,
            )
        except (MarketNoSendError, OSError, TypeError, ValueError) as exc:
            excluded.append({
                "artifact_namespace": namespace,
                "run_id": _text(
                    manifest.get("run_id") or audit.get("exact_run_id")
                ) or None,
                "observed_at": _safe_timestamp(
                    manifest.get("observed_at") or audit.get("generated_at")
                ),
                "validation_errors": [
                    "generation_snapshot:" + _validation_error_code(exc)
                ],
                "campaign_counting_source": validation.counting_source,
                "campaign_counting_reason": validation.counting_reason,
                "_candidate_snapshot_episode_input": {
                    "artifact_namespace": namespace,
                    "run_id": _text(
                        manifest.get("run_id") or audit.get("exact_run_id")
                    ) or None,
                    "campaign_counted": validation.campaign_counted,
                },
            })
            continue
        generations.append(generation)
    generations.sort(key=_generation_sort_key)
    attempts.sort(key=_attempt_sort_key)
    excluded.sort(key=_generation_sort_key)
    return generations, attempts, excluded


def _generation_row(
    namespace_dir: Path,
    *,
    manifest: Mapping[str, Any],
    audit: Mapping[str, Any],
    validation: market_no_send_publication.CampaignGenerationValidation,
    current_authority: Mapping[str, Any],
) -> dict[str, Any]:
    operator = _read_json(namespace_dir / OPERATOR_STATE_FILENAME)
    snapshots = market_observation_campaign_snapshots.capture_generation_snapshots(
        namespace_dir,
        manifest=manifest,
        validation=validation,
        operator_state=operator,
    )
    candidates = snapshots["candidate"]["rows"]
    outcomes = snapshots["integrated_outcome"]["rows"]
    request = _read_json(namespace_dir / REQUEST_LEDGER_FILENAME)
    counted = validation.campaign_counted
    source = validation.counting_source
    reason = validation.counting_reason
    route_counts = Counter(
        _text(row.get("radar_route")) or "diagnostic" for row in candidates
    )
    run_id = _text(manifest.get("run_id") or audit.get("exact_run_id"))
    observed_at = _text(manifest.get("observed_at") or audit.get("generated_at"))
    publication_values, publication_artifacts = _generation_publication(
        namespace_dir,
        run_id=run_id,
        audit=audit,
        operator=operator,
        current_authority=current_authority,
    )
    doctor = _mapping(operator.get("doctor")) or _mapping(audit.get("doctor"))
    quality = _generation_quality(manifest, audit)
    return {
        "artifact_namespace": namespace_dir.name,
        "run_id": run_id or None,
        "observed_at": observed_at or None,
        "status": "complete",
        "campaign_counted": counted,
        "campaign_counting_source": source,
        "campaign_counting_reason": reason,
        "provider": _text(manifest.get("provider") or audit.get("provider") or "coingecko"),
        "provider_call_attempted": _strict_true(manifest, audit, "provider_call_attempted"),
        "provider_request_succeeded": _strict_true(manifest, audit, "provider_request_succeeded"),
        "candidate_count": len(candidates),
        "manifest_candidate_count": _int(manifest.get("candidate_count")),
        "candidate_count_matches_manifest": len(candidates) == _int(manifest.get("candidate_count")),
        "route_counts": dict(sorted(route_counts.items())),
        "outcomes": _outcome_metrics(outcomes),
        "artifact_authority": {
            "core_bound": validation.core_artifact_bound,
            "core_row_count": validation.core_artifact_row_count,
            "integrated_outcomes_bound": validation.integrated_outcome_artifact_bound,
            "integrated_outcome_row_count": validation.integrated_outcome_artifact_row_count,
        },
        "campaign_outcome_refresh": {
            "error_counts": dict(sorted(_mapping(
                manifest.get("campaign_outcome_refresh_error_counts")
            ).items())),
            "failure_class": _safe_error_class(
                manifest.get("campaign_outcome_refresh_failure_class")
            ),
        },
        "data_quality": quality,
        "request_ledger": _request_summary(request),
        "doctor": {
            "authoritative": doctor.get("authoritative") is True,
            "status": _text(doctor.get("status")) or None,
            "blocker_count": _int(doctor.get("blocker_count")),
            "warning_count": _int(doctor.get("warning_count")),
            "revision": doctor.get("verified_revision") or operator.get("revision"),
        },
        "publication": publication_values,
        "safety": _generation_safety(manifest, audit),
        "artifact_names": {
            "manifest": RUN_MANIFEST_FILENAME,
            "pilot_audit": PILOT_AUDIT_FILENAME if audit else None,
            **publication_artifacts,
            "request_ledger": REQUEST_LEDGER_FILENAME if request else None,
            "outcomes": integrated_radar.INTEGRATED_OUTCOMES_FILENAME,
        },
        **market_observation_campaign_snapshots.private_generation_snapshot_fields(
            snapshots
        ),
    }


def _generation_publication(
    namespace_dir: Path,
    *,
    run_id: str,
    audit: Mapping[str, Any],
    operator: Mapping[str, Any],
    current_authority: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, str | None]]:
    attempt = _mapping(audit.get("publication"))
    exact_pointer = _current_authority_matches(
        current_authority,
        namespace=namespace_dir.name,
        run_id=run_id,
    )
    try:
        managed = daily_operations_publication.is_daily_operations_managed_namespace(
            namespace_dir.parent,
            namespace_dir.name,
        )
    except Exception:  # noqa: BLE001 - managed authority classification fails closed
        managed = True
    prepublication_audit_available = bool(
        _read_json(namespace_dir / PREPUBLICATION_AUDIT_FILENAME)
    )
    legacy_audit = bool(
        not managed
        and market_no_send_audit.has_bound_publication_authority(
            audit, operator, namespace=namespace_dir.name, run_id=run_id
        )
    )
    final = daily_operations_publication.validate_final_publication_contract(
        namespace_dir.parent,
        namespace_dir.name,
        require_operations=exact_pointer,
    )
    publication_errors = tuple(
        error for error in final.errors
        if error.startswith("publication_receipt")
        or error == "current_authority_missing_publication_receipt"
    )
    operations_errors = tuple(
        error for error in final.errors
        if error.startswith("operations_receipt")
        or error == "current_authority_missing_operations_receipt"
    )
    final_valid = final.publication_receipt is not None and not publication_errors
    operations_valid = bool(
        final.operations_receipt is not None and not operations_errors
    )
    legacy_pointer = bool(
        exact_pointer and not managed and final.publication_receipt is None
    )
    status = _publication_status(
        final=final,
        final_valid=final_valid,
        legacy_audit=legacy_audit,
        legacy_pointer=legacy_pointer,
        managed=managed,
    )
    current = bool(
        exact_pointer
        and ((final_valid and operations_valid) or legacy_audit or legacy_pointer)
    )
    values = {
        "ever_authoritative": bool(
            final_valid or legacy_audit or legacy_pointer
        ),
        "first_authoritative_at": _first_authoritative_at(
            final=final,
            final_valid=final_valid,
            attempt=attempt,
            audit=audit,
            legacy_audit=legacy_audit,
            exact_pointer=legacy_pointer,
            current_authority=current_authority,
        ),
        "audit_authority_binding_valid": legacy_audit,
        "final_publication_receipt_valid": final_valid,
        "operations_receipt_valid": operations_valid,
        "authority_source": (
            "final_publication_receipt_exact_binding" if final_valid
            else "pilot_audit_exact_binding" if legacy_audit
            else "legacy_current_pointer_exact_binding" if legacy_pointer
            else None
        ),
        "attempt_audit_status": _text(attempt.get("status")) or "not_recorded",
        "publication_status": status,
        "operations_status": (
            final.operations_status if operations_valid
            else "invalid" if final.operations_receipt is not None
            else "legacy_not_recorded" if legacy_audit or legacy_pointer
            else "not_recorded"
        ),
        "audit_status": status,
        "currently_authoritative": current,
        "contract_errors": list(final.errors),
    }
    artifacts = {
        "prepublication_audit": (
            PREPUBLICATION_AUDIT_FILENAME
            if prepublication_audit_available else None
        ),
        "publication_receipt": (
            PUBLICATION_RECEIPT_FILENAME
            if final.publication_receipt is not None else None
        ),
        "operations_receipt": (
            OPERATIONS_RECEIPT_FILENAME if final.operations_receipt is not None else None
        ),
    }
    return values, artifacts


def _publication_status(
    *,
    final: daily_operations_publication.FinalPublicationValidation,
    final_valid: bool,
    legacy_audit: bool,
    legacy_pointer: bool,
    managed: bool,
) -> str:
    if final_valid:
        return final.publication_status
    if legacy_audit:
        return "published_legacy_audit"
    if legacy_pointer:
        return "published_legacy_pointer"
    if final.publication_receipt is not None:
        return "invalid_final_receipt"
    return "missing_final_receipt" if managed else "not_published"


def _first_authoritative_at(
    *,
    final: daily_operations_publication.FinalPublicationValidation,
    final_valid: bool,
    attempt: Mapping[str, Any],
    audit: Mapping[str, Any],
    legacy_audit: bool,
    exact_pointer: bool,
    current_authority: Mapping[str, Any],
) -> str | None:
    operations_time = (
        _safe_timestamp(
            _mapping(
                _mapping(final.operations_receipt).get("maintenance_state")
            ).get("last_successful_publication")
        )
        if final_valid else None
    )
    receipt_time = (
        _safe_timestamp(_mapping(final.publication_receipt).get("recorded_at"))
        if final_valid else None
    )
    legacy_time = (
        _safe_timestamp(attempt.get("first_authoritative_at"))
        or _safe_timestamp(audit.get("generated_at"))
        if legacy_audit else None
    )
    pointer_time = (
        _safe_timestamp(current_authority.get("authority_checked_at"))
        if exact_pointer else None
    )
    return operations_time or receipt_time or legacy_time or pointer_time


def _campaign_counting(manifest: Mapping[str, Any]) -> tuple[bool, str, str]:
    """Return Decision Radar counting truth without rewriting v2 history."""

    provenance = _mapping(manifest.get("market_provenance"))
    common_valid = bool(
        manifest.get("status") == "complete"
        and manifest.get("candidate_source_mode") == "live_no_send"
        and manifest.get("data_acquisition_mode") == "live_provider"
        and manifest.get("live_provider_authorized") is True
        and manifest.get("provider_call_attempted") is True
        and manifest.get("provider_request_succeeded") is True
        and manifest.get("provenance_contract_valid") is True
        and manifest.get("no_send") is True
        and manifest.get("research_only") is True
    )
    if "decision_radar_campaign_counted" in manifest:
        counted = common_valid and manifest.get("decision_radar_campaign_counted") is True
        return (
            counted,
            "decision_radar_campaign_contract",
            _text(manifest.get("decision_radar_campaign_reason"))
            or ("counted_closed_campaign_contract" if counted else "campaign_contract_not_counted"),
        )
    legacy_v2 = bool(
        manifest.get("contract_version") == 2
        and provenance.get("contract_version") == 2
        and provenance.get("schema_version") == "crypto_radar_market_provenance_v2"
        and provenance.get("provenance_contract_valid") is True
        and provenance.get("burn_in_counted") is True
        and manifest.get("burn_in_counted") is True
    )
    counted = common_valid and legacy_v2
    return (
        counted,
        "historical_market_provenance_v2_read_only_adapter",
        "counted_valid_live_no_send_v2_lineage" if counted else "not_valid_campaign_evidence",
    )


def _generation_quality(
    manifest: Mapping[str, Any],
    audit: Mapping[str, Any],
) -> dict[str, Any]:
    provenance = _mapping(manifest.get("market_provenance"))
    quality = _mapping(provenance.get("data_quality"))
    if not quality:
        quality = _mapping(audit.get("baseline"))
    selected = _int(manifest.get("selected_market_row_count"))
    spread = _int(quality.get("spread_available_count"))
    return {
        "direct_feature_count": _int(quality.get("direct_feature_count")),
        "proxy_feature_count": _int(quality.get("proxy_feature_count")),
        "spread_available_count": spread,
        "selected_market_row_count": selected,
        "spread_coverage_ratio": round(spread / selected, 6) if selected else 0.0,
        "baseline_status_counts": dict(sorted(_mapping(quality.get("baseline_status_counts")).items())),
        "baseline_warm_assets": _int(quality.get("baseline_warm_assets")),
        "baseline_warming_assets": _int(quality.get("baseline_warming_assets")),
    }


def _request_summary(request: Mapping[str, Any]) -> dict[str, Any]:
    endpoint = _safe_endpoint(
        request.get("endpoint_path") or request.get("endpoint") or request.get("request_path")
    )
    status = request.get("http_status")
    if isinstance(status, bool) or not isinstance(status, int) or not 100 <= status <= 599:
        status = None
    duration = _number(request.get("duration_ms"))
    retries = request.get("retry_count")
    retries = retries if isinstance(retries, int) and not isinstance(retries, bool) and retries >= 0 else None
    return {
        "artifact": REQUEST_LEDGER_FILENAME if request else None,
        "endpoint_path": endpoint,
        "request_started_at": _safe_timestamp(request.get("request_started_at")),
        "request_ended_at": _safe_timestamp(request.get("request_ended_at")),
        "duration_ms": duration,
        "http_status": status,
        "result_count": _first_int(
            request,
            "result_count",
            "raw_market_row_count",
            "selected_market_row_count",
        ),
        "retry_count": retries,
        "error_class": _safe_error_class(request.get("error_class")),
        "cache_behavior": _text(request.get("cache_behavior") or request.get("cache_status")) or None,
        "live_provider_authorized": request.get("live_provider_authorized") is True,
        "no_send": request.get("no_send") is True,
    }


def _campaign_metrics(
    generations: Sequence[Mapping[str, Any]],
    outcomes: Mapping[str, Any],
    baseline: Mapping[str, Any],
) -> dict[str, Any]:
    routes: Counter[str] = Counter()
    direct = proxy = spread = selected = candidates = current_candidates = 0
    for generation in generations:
        routes.update({str(key): _int(value) for key, value in _mapping(generation.get("route_counts")).items()})
        quality = _mapping(generation.get("data_quality"))
        direct += _int(quality.get("direct_feature_count"))
        proxy += _int(quality.get("proxy_feature_count"))
        spread += _int(quality.get("spread_available_count"))
        selected += _int(quality.get("selected_market_row_count"))
        candidates += _int(generation.get("candidate_count"))
        if _mapping(generation.get("publication")).get("currently_authoritative") is True:
            current_candidates += _int(generation.get("candidate_count"))
    current_baseline = _mapping(baseline.get("current_universe_maturity"))
    return {
        "real_cycles": len(generations),
        "real_observations": selected,
        "real_candidates": candidates,
        "current_ideas": current_candidates,
        "historical_ideas": max(0, candidates - current_candidates),
        "route_counts": dict(sorted(routes.items())),
        "pending_outcomes": _int(outcomes.get("pending")),
        "matured_outcomes": _int(outcomes.get("matured")),
        "direct_feature_count": direct,
        "proxy_feature_count": proxy,
        "spread_available_count": spread,
        "selected_market_row_count": selected,
        "retained_observation_count": _int(baseline.get("baseline_observation_count")),
        "baseline_counted_observation_count": _int(
            baseline.get("baseline_counted_observation_count")
        ),
        "too_close_observation_count": _int(
            baseline.get("baseline_too_close_observation_count")
        ),
        "spread_coverage_ratio": round(spread / selected, 6) if selected else 0.0,
        "baseline_status": _text(baseline.get("baseline_status")) or "unknown",
        "baseline_warm_asset_count": _int(baseline.get("baseline_warm_asset_count")),
        "current_universe_baseline_status": (
            _text(current_baseline.get("status")) or "unavailable"
        ),
        "current_universe_expected_asset_count": _int(
            current_baseline.get("expected_asset_count")
        ),
        "current_universe_observed_asset_count": _int(
            current_baseline.get("observed_asset_count")
        ),
        "current_universe_warm_asset_count": _int(
            current_baseline.get("baseline_warm_asset_count")
        ),
        "provider_failed_attempts": 0,
        "blocked_attempts": 0,
    }


def _campaign_outcomes(
    base: Path,
    generations: Sequence[Mapping[str, Any]],
    *,
    ledger_snapshot: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    candidates_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    pending_rows: list[dict[str, Any]] = []
    for generation in generations:
        namespace = _text(generation.get("artifact_namespace"))
        if not namespace:
            continue
        sources = market_observation_campaign_snapshots.generation_candidate_rows(
            generation
        )
        if sources is None:
            # Compatibility for private callers passing pre-snapshot rows.  The
            # canonical report builder never takes this branch.
            try:
                namespace_dir = safe_existing_namespace_dir(base, namespace)
                sources = read_jsonl(
                    namespace_dir / integrated_radar.INTEGRATED_CANDIDATES_FILENAME
                )
            except MarketNoSendError:
                continue
        for source in sources:
            candidate = dict(source)
            candidate_id = _text(candidate.get("candidate_id"))
            if not candidate_id:
                continue
            candidates_by_key[(namespace, candidate_id)] = candidate
            pending_rows.append(
                market_observation_outcomes.candidate_pending_campaign_outcome(
                    candidate,
                    namespace=namespace,
                )
            )
    snapshot = (
        market_observation_campaign_snapshots.campaign_outcome_ledger_snapshot(
            base,
            history_namespace=market_no_send_history_cache.LIVE_HISTORY_CACHE_NAMESPACE,
            filename=CAMPAIGN_OUTCOMES_FILENAME,
        )
        if ledger_snapshot is None
        else dict(ledger_snapshot)
    )
    ledger_sources = snapshot.get("rows")
    if not isinstance(ledger_sources, (list, tuple)):
        ledger_sources = ()
    campaign_rows: list[dict[str, Any]] = []
    for source in ledger_sources:
        row = dict(source)
        key = (
            _text(row.get("source_artifact_namespace")),
            _text(row.get("candidate_id")),
        )
        candidate = candidates_by_key.get(key)
        if candidate is not None and market_observation_outcomes.campaign_ledger_outcome_valid(
            row,
            candidate,
            namespace=key[0],
        ):
            campaign_rows.append(row)
    # Every bound candidate contributes one fail-closed pending identity.  Only
    # canonical, candidate-equal, safety-valid ledger rows may add maturity.
    return _deduplicate_outcomes((*pending_rows, *campaign_rows))


def _deduplicate_outcomes(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for index, source in enumerate(rows):
        row = dict(source)
        identity = _text(row.get("outcome_identity_key")) or json.dumps(
            _mapping(row.get("outcome_identity")), sort_keys=True, separators=(",", ":")
        )
        if not identity or identity == "{}":
            identity = (
                f"row:{index}:{_text(row.get('candidate_id'))}:"
                f"{_text(row.get('observed_at'))}"
            )
        namespace = _text(row.get("source_artifact_namespace"))
        key = f"{namespace}\0{identity}"
        current = selected.get(key)
        if current is None or _outcome_rank(row) > _outcome_rank(current):
            selected[key] = row
    return [selected[key] for key in sorted(selected)]


def _outcome_metrics(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    materialized = list(rows)
    counts: Counter[str] = Counter(_outcome_state(row) for row in materialized)
    refresh_errors: Counter[str] = Counter()
    for row in materialized:
        errors = row.get("campaign_outcome_refresh_errors")
        if isinstance(errors, (list, tuple)):
            refresh_errors.update(
                _text(value) for value in errors if _text(value)
            )
    has_ledger = any(row.get("campaign_outcome_ledger") is True for row in materialized)
    has_candidate_base = any(
        row.get("campaign_outcome_source") == "canonical_candidate_pending_base"
        for row in materialized
    )
    source = (
        "canonical_candidate_pending_base_plus_campaign_ledger"
        if has_ledger and has_candidate_base
        else "campaign_outcome_ledger"
        if has_ledger
        else "canonical_candidate_pending_base"
    )
    return {
        "total": len(materialized),
        # Keep the v2 report's existing headline keys while exposing the exact
        # primary-horizon states in ``status_counts`` and dedicated fields.
        "pending": counts["not_due"],
        "matured": counts["matured"],
        "missing_data": counts["due_missing_price"],
        "not_due": counts["not_due"],
        "due_missing_price": counts["due_missing_price"],
        "other": counts["other"],
        "status_counts": dict(sorted(counts.items())),
        "source": source,
        "refresh_build_error_count": sum(refresh_errors.values()),
        "refresh_build_error_counts": dict(sorted(refresh_errors.items())),
        "human_feedback_optional": True,
        "automatic_threshold_changes": False,
    }


def _outcome_state(row: Mapping[str, Any]) -> str:
    primary = row.get("primary_horizon")
    metadata = row.get("horizon_metadata")
    if (
        type(primary) is str
        and primary in outcome_eligibility.OUTCOME_HORIZONS
        and isinstance(metadata, Mapping)
        and isinstance((primary_metadata := metadata.get(primary)), Mapping)
    ):
        primary_status = _text(primary_metadata.get("maturity_status")).casefold()
        if primary_status == "matured":
            return (
                "matured"
                if market_observation_outcomes.canonical_primary_outcome_return(row) is not None
                else "other"
            )
        if primary_status == "pending":
            return "not_due"
        if primary_status == "missing_data":
            return "due_missing_price"
        # A present canonical primary-horizon record is authoritative.  Do not
        # let a contradictory top-level or secondary-horizon state promote it.
        return "other"

    state = _text(row.get("maturation_state") or row.get("outcome_status") or row.get("outcome_label")).casefold()
    if state in _MATURED_STATES:
        if type(primary) is str:
            return (
                "matured"
                if market_observation_outcomes.canonical_primary_outcome_return(row) is not None
                else "other"
            )
        # Historical pre-contract summaries did not persist a primary horizon;
        # keep their explicit terminal state readable without projecting it as
        # a current canonical contract.
        return "matured"
    if state in _MISSING_STATES:
        return "due_missing_price"
    if state in _PENDING_STATES:
        return "not_due"
    if market_observation_outcomes.canonical_primary_outcome_return(row) is not None:
        return "matured"
    return "other"


def _outcome_rank(row: Mapping[str, Any]) -> tuple[int, str]:
    rank = {
        "matured": 3,
        "due_missing_price": 2,
        "not_due": 1,
        "other": 0,
    }[_outcome_state(row)]
    return rank, _text(row.get("outcome_evaluated_at"))


def _data_quality_limitations(metrics: Mapping[str, Any]) -> list[dict[str, Any]]:
    limitations: list[dict[str, Any]] = []
    selected = _int(metrics.get("selected_market_row_count"))
    spread = _int(metrics.get("spread_available_count"))
    if selected == 0 or spread < selected:
        limitations.append({
            "category": "execution_quality_spread",
            "detail": (
                f"Trusted spread coverage is {spread}/{selected}. Bybit USDT-linear perpetuals "
                "are the selected execution surface; coverage remains unavailable until a "
                "separately authorized immutable public-market capture succeeds and is bound "
                "into the campaign."
            ),
            "provider_selection": "selected_bybit_usdt_linear_perpetuals",
            "evidence_status": "awaiting_authorized_immutable_capture",
            "next_safe_command": (
                "make radar-execution-quality-bybit-readiness PYTHON=.venv/bin/python"
            ),
            "authorization_boundary": (
                "readiness_is_no_network; capture_requires_an_already_present_explicit_flag_"
                "plus_CONFIRM=1"
            ),
        })
    if _int(metrics.get("proxy_feature_count")) > 0:
        limitations.append({
            "category": "proxy_market_features",
            "detail": (
                f"The campaign retains {_int(metrics.get('proxy_feature_count'))} proxy feature "
                "observations; proxy evidence remains explicitly quality-capped."
            ),
        })
    current_baseline_status = _text(
        metrics.get("current_universe_baseline_status")
    )
    retained_baseline_status = _text(metrics.get("baseline_status"))
    evaluated_baseline_status = (
        current_baseline_status
        if current_baseline_status not in {"", "unavailable"}
        else retained_baseline_status
    )
    if evaluated_baseline_status != "warm":
        limitations.append({
            "category": "temporal_baseline_maturity",
            "detail": (
                "The exact current authoritative universe is not feature/time-aware warm."
                if current_baseline_status not in {"", "unavailable"}
                else "Current-universe maturity is unavailable; retained campaign history is not globally warm."
            ),
            "current_universe_status": current_baseline_status or "unavailable",
            "retained_history_status": retained_baseline_status or "unknown",
        })
    return limitations


def _campaign_status(metrics: Mapping[str, Any], baseline: Mapping[str, Any]) -> str:
    if _int(metrics.get("real_cycles")) == 0:
        return "not_started"
    status = _text(baseline.get("baseline_status")) or "unknown"
    return "observing_warm_baseline" if status == "warm" else f"in_progress_baseline_{status}"


def _count_phrase(count: int, singular: str, plural: str | None = None) -> str:
    return f"{count} {singular if count == 1 else plural or singular + 's'}"


def _outcome_phrase(count: int, state: str) -> str:
    return f"{_count_phrase(count, 'outcome')} {'is' if count == 1 else 'are'} {state}"


def _campaign_conclusion(
    *,
    status: str,
    metrics: Mapping[str, Any],
    baseline: Mapping[str, Any],
    pointer: Mapping[str, Any],
    pointer_history: Sequence[Mapping[str, Any]],
    provider_failed: Sequence[Mapping[str, Any]],
    blocked: Sequence[Mapping[str, Any]],
    limitations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    categories = [_text(_mapping(row).get("category")) for row in limitations]
    highest = _text(_mapping(limitations[0]).get("category")) if limitations else "none"
    pointer_target = {
        key: pointer.get(key)
        for key in ("artifact_namespace", "run_id", "revision", "status")
    } if pointer.get("artifact_namespace") else None
    current_authority = (
        {
            key: pointer.get(key)
            for key in (
                "artifact_namespace",
                "run_id",
                "revision",
                "exact_operator_binding",
            )
        }
        if pointer.get("status") == "authoritative"
        and pointer.get("exact_operator_binding") is True
        else None
    )
    authority_summary = (
        f"current authority is {_text(pointer.get('artifact_namespace'))}"
        if current_authority is not None
        else f"pointer target is {_text(pointer.get('artifact_namespace'))}, but no current authority is proven"
        if pointer_target is not None
        else "no pointer target or current authority is available"
    )
    pending_count = _int(metrics.get("pending_outcomes"))
    matured_count = _int(metrics.get("matured_outcomes"))
    current_baseline = _mapping(baseline.get("current_universe_maturity"))
    current_baseline_status = _text(current_baseline.get("status")) or "unavailable"
    summary = (
        f"Decision Radar campaign v2 has {_int(metrics.get('real_cycles'))} counted real/no-send "
        f"cycles and {_int(metrics.get('real_candidates'))} canonical {'idea' if _int(metrics.get('real_candidates')) == 1 else 'ideas'}; "
        f"{_outcome_phrase(pending_count, 'pending')} and "
        f"{_outcome_phrase(matured_count, 'matured')}. "
        f"Provider history contains {_count_phrase(len(provider_failed), 'provider failure')} and "
        f"{_count_phrase(len(blocked), 'blocked/preflight attempt')}. Baseline status is "
        f"{_text(baseline.get('baseline_status')) or 'unknown'} with "
        f"{_int(baseline.get('baseline_warm_asset_count'))}/{_int(baseline.get('baseline_asset_count'))} "
        f"warm retained assets; exact current-universe status is {current_baseline_status} with "
        f"{_int(current_baseline.get('baseline_warm_asset_count'))}/{_int(current_baseline.get('expected_asset_count'))} "
        f"warm assets. Pointer history contains {len(pointer_history)} bound {'generation' if len(pointer_history) == 1 else 'generations'} and {authority_summary}. Data-quality limitation "
        f"categories are {', '.join(categories) or 'none'}; highest-value missing input is {highest}."
    )
    return {
        "status": status,
        "summary": summary,
        "baseline_status": _text(baseline.get("baseline_status")) or "unknown",
        "baseline_coverage": {
            "retained_observations": _int(baseline.get("baseline_observation_count")),
            "counted_observations": _int(baseline.get("baseline_counted_observation_count")),
            "asset_count": _int(baseline.get("baseline_asset_count")),
            "warm_asset_count": _int(baseline.get("baseline_warm_asset_count")),
        },
        "current_universe_baseline": {
            "status": current_baseline_status,
            "expected_asset_count": _int(
                current_baseline.get("expected_asset_count")
            ),
            "observed_asset_count": _int(
                current_baseline.get("observed_asset_count")
            ),
            "warm_asset_count": _int(
                current_baseline.get("baseline_warm_asset_count")
            ),
            "missing_asset_count": _int(
                current_baseline.get("missing_asset_count")
            ),
        },
        "pointer_history_count": len(pointer_history),
        "current_authority": current_authority,
        "pointer_target": pointer_target,
        "data_quality_limitation_categories": categories,
        "highest_value_missing_input_category": highest,
        "spread_provider_selection": "selected_bybit_usdt_linear_perpetuals",
        "spread_evidence_status": "awaiting_authorized_immutable_capture",
        "spread_readiness_command": (
            "make radar-execution-quality-bybit-readiness PYTHON=.venv/bin/python"
        ),
        "research_only": True,
        "no_trade_recommendation": True,
    }


def _pointer_state(
    pointer: Mapping[str, Any],
    generations: Sequence[Mapping[str, Any]],
    *,
    current_authority: Mapping[str, Any],
    authority_error: str | None,
) -> dict[str, Any]:
    namespace = _text(current_authority.get("artifact_namespace")) or _text(
        pointer.get("artifact_namespace")
    )
    run_id = _text(current_authority.get("run_id")) or _text(pointer.get("run_id"))
    match = next(
        (
            row for row in generations
            if row.get("artifact_namespace") == namespace and row.get("run_id") == run_id
        ),
        None,
    )
    exact = bool(
        current_authority
        and match
        and _mapping(match.get("publication")).get("currently_authoritative") is True
    )
    return {
        "status": (
            "authoritative"
            if exact
            else "invalid_or_untrusted"
            if authority_error
            else "present_but_not_exact"
            if pointer
            else "unavailable"
        ),
        "artifact_namespace": namespace or None,
        "run_id": run_id or None,
        "revision": current_authority.get("revision") or pointer.get("revision"),
        "exact_operator_binding": exact,
        "generation_authority_status": (
            "authoritative" if exact else pointer.get("generation_authority_status")
        ),
        "authority_checked_at": _safe_timestamp(
            current_authority.get("authority_checked_at")
            or pointer.get("authority_checked_at")
        ),
        "readiness_validation": "passed" if current_authority else "failed",
        "readiness_error": authority_error,
    }


def _pointer_history(
    authoritative: Sequence[Mapping[str, Any]],
    pointer: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows = [
        {
            "artifact_namespace": row.get("artifact_namespace"),
            "run_id": row.get("run_id"),
            "observed_at": row.get("observed_at"),
            "first_authoritative_at": _mapping(row.get("publication")).get(
                "first_authoritative_at"
            ),
            "currently_authoritative": _mapping(row.get("publication")).get("currently_authoritative") is True,
            "source": _mapping(row.get("publication")).get("authority_source"),
        }
        for row in authoritative
    ]
    rows.sort(key=lambda row: (_text(row.get("observed_at")), _text(row.get("artifact_namespace"))))
    if pointer.get("artifact_namespace") and not any(
        row.get("artifact_namespace") == pointer.get("artifact_namespace")
        and row.get("run_id") == pointer.get("run_id")
        for row in rows
    ):
        rows.append({
            "artifact_namespace": pointer.get("artifact_namespace"),
            "run_id": pointer.get("run_id"),
            "observed_at": pointer.get("authority_checked_at"),
            "currently_authoritative": pointer.get("exact_operator_binding") is True,
            "source": "current_pointer",
        })
    return rows


def _resolve_current_authority(
    base: Path,
    *,
    evaluated: datetime,
) -> tuple[dict[str, Any], str | None]:
    """Use the dashboard's full readiness/fingerprint gate as current authority."""

    try:
        result = dashboard_readiness.resolve_authoritative_dashboard(
            base,
            now=evaluated,
        )
    except dashboard_readiness.DashboardReadinessError as exc:
        return {}, _validation_error_code(exc)
    snapshot = result.snapshot
    current_asset_ids = tuple(
        sorted(
            {
                _text(row.get("canonical_asset_id"))
                for row in getattr(snapshot, "current_market_observations", ())
                if isinstance(row, Mapping)
                and _text(row.get("canonical_asset_id"))
            }
        )
    )
    return {
        "artifact_namespace": snapshot.artifact_namespace,
        "profile": snapshot.profile,
        "run_id": snapshot.run_id,
        "revision": snapshot.revision,
        "operator_state_sha256": snapshot.operator_state_sha256,
        "authority_checked_at": snapshot.generation_authority_checked_at,
        "_current_asset_ids": current_asset_ids,
    }, None


def _current_authority_matches(
    current_authority: Mapping[str, Any],
    *,
    namespace: str,
    run_id: str,
) -> bool:
    return bool(
        current_authority
        and current_authority.get("artifact_namespace") == namespace
        and current_authority.get("run_id") == run_id
    )


def _generation_safety(
    manifest: Mapping[str, Any],
    audit: Mapping[str, Any],
) -> dict[str, Any]:
    audit_safety = _mapping(audit.get("safety"))
    output = {
        "no_send": manifest.get("no_send") is True or audit_safety.get("no_send") is True,
        "research_only": manifest.get("research_only") is True or audit_safety.get("research_only") is True,
    }
    for field in _SAFETY_COUNTER_FIELDS:
        output[field] = _int(manifest.get(field) if field in manifest else audit_safety.get(field))
    return output


def _namespace_names(base: Path) -> list[str]:
    names: list[str] = []
    try:
        entries = list(base.iterdir())
    except OSError as exc:
        raise MarketNoSendError("campaign artifact base is unreadable") from exc
    for entry in entries:
        try:
            info = entry.lstat()
        except OSError:
            continue
        if stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode):
            names.append(entry.name)
    return sorted(names)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return read_json_object(path)
    except (MarketNoSendError, OSError):
        return {}


def _validated_existing_directory(value: str | Path, *, label: str) -> Path:
    path = Path(value).expanduser().resolve()
    try:
        info = path.lstat()
    except OSError as exc:
        raise MarketNoSendError(f"{label} directory is missing or unreadable") from exc
    if not stat.S_ISDIR(info.st_mode):
        raise MarketNoSendError(f"{label} is not a directory")
    return path


def _write_atomic(path: Path, data: bytes) -> None:
    try:
        existing = path.lstat()
    except FileNotFoundError:
        existing = None
    if existing is not None and not stat.S_ISREG(existing.st_mode):
        raise MarketNoSendError("campaign report target is not a regular file")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError as exc:
        raise MarketNoSendError("campaign report write failed") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _generation_sort_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        _text(row.get("observed_at")),
        _text(row.get("artifact_namespace")),
        _text(row.get("run_id")),
    )


def _strict_true(
    primary: Mapping[str, Any],
    secondary: Mapping[str, Any],
    field: str,
) -> bool:
    if field in primary:
        return primary.get(field) is True
    return secondary.get(field) is True


def _safe_endpoint(value: Any) -> str | None:
    text = _text(value)
    if not text or not text.startswith("/") or "?" in text or "#" in text or "@" in text:
        return None
    return text if len(text) <= 240 else None


def _safe_error_class(value: Any) -> str | None:
    text = _text(value)
    if not text or len(text) > 80:
        return None
    if not all(character.isalnum() or character in "_-." for character in text):
        return None
    return text


def _validation_error_code(error: BaseException) -> str:
    text = str(error).strip()
    if not text:
        return type(error).__name__
    safe = "".join(
        character if character.isalnum() or character in "_:-,.()" else "_"
        for character in text[:240]
    ).strip("_")
    return safe or type(error).__name__


def _safe_timestamp(value: Any) -> str | None:
    parsed = _parse_time(value)
    return parsed.isoformat() if parsed else None


def _parse_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo is not None else None
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None


def _require_aware_utc(value: datetime | str, *, field_name: str) -> datetime:
    parsed = _parse_time(value)
    if parsed is None:
        raise MarketNoSendError(f"campaign {field_name} must be a timezone-aware timestamp")
    return parsed


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: Any) -> str:
    return str(value).strip() if value not in (None, "") else ""


def _int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _first_int(value: Mapping[str, Any], *fields: str) -> int | None:
    for field in fields:
        raw = value.get(field)
        if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 0:
            return raw
    return None


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


__all__ = ("CAMPAIGN_PROGRAM", "CAMPAIGN_REPORT_JSON_FILENAME", "CAMPAIGN_REPORT_MD_FILENAME",
           "CAMPAIGN_REPORT_SCHEMA", "build_campaign_report", "format_campaign_report",
           "write_campaign_report")
