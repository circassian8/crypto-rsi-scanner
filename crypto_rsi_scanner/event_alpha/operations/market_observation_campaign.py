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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ... import config as project_config
from ..dashboard import readiness as dashboard_readiness
from ..dashboard.readiness import CURRENT_NAMESPACE_POINTER
from ..radar import market_history
from ..radar.integrated import api as integrated_radar
from . import market_no_send_audit, market_no_send_history_cache
from . import market_no_send_publication
from . import market_observation_campaign_cadence
from . import market_observation_outcomes
from .market_no_send_models import SAFETY_COUNTERS
from .market_no_send_attempt import ATTEMPT_LEDGER_FILENAME, LATEST_ATTEMPT_FILENAME
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
REQUEST_LEDGER_FILENAME = "event_market_no_send_request_ledger.json"
HISTORY_FILENAME = "event_market_history.jsonl"
OPERATOR_STATE_FILENAME = "event_alpha_operator_state.json"

_SAFETY_COUNTER_FIELDS = (
    "telegram_sends",
    "trades_created",
    "paper_trades_created",
    "normal_rsi_signal_rows_written",
    "triggered_fade_created",
)
_MATURED_STATES = {"matured", "complete", "completed", "observed", "scored"}
_PENDING_STATES = {"pending", "not_due"}
_MISSING_STATES = {"missing", "missing_data", "unavailable"}


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
    outcomes = _campaign_outcomes(base, counted_generations)
    outcome_metrics = _outcome_metrics(outcomes)
    baseline = _baseline_maturity(base, evaluated=evaluated)
    metrics = _campaign_metrics(counted_generations, outcome_metrics, baseline)
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
    return {
        "contract_version": 2,
        "schema_id": CAMPAIGN_REPORT_SCHEMA,
        "schema_version": CAMPAIGN_REPORT_SCHEMA,
        "row_type": "decision_radar_live_observation_campaign_report",
        "measurement_program": CAMPAIGN_PROGRAM,
        "generated_at": evaluated.isoformat(),
        "campaign_status": status,
        "measurement_scope": {
            "decision_radar_live_observation_campaign": "included",
            "event_alpha_catalyst_burn_in": "separate_not_aggregated",
            "historical_market_provenance_v2_adapter": "read_only",
            "historical_rows_rewritten": False,
        },
        "campaign_metrics": metrics,
        "baseline_maturity": baseline,
        "authoritative_generations": authoritative,
        "non_authoritative_complete_generations": non_authoritative,
        "provider_failed_attempts": provider_failed,
        "blocked_or_preflight_attempts": blocked,
        "excluded_invalid_generations": excluded_generations,
        "generation_validation": {
            "valid_generation_count": len(generations),
            "excluded_generation_count": len(excluded_generations),
            "exclusion_reason_counts": dict(sorted(Counter(
                reason
                for row in excluded_generations
                for reason in row.get("validation_errors", ())
            ).items())),
        },
        "pointer": pointer_state,
        "pointer_history": pointer_history,
        "outcomes": outcome_metrics,
        "data_quality_limitations": limitations,
        "next_observation": next_observation,
        "campaign_v2_conclusion": conclusion,
        "safety": {
            "research_only": True,
            "no_trade_recommendation": True,
            "provider_calls_made_by_report": 0,
            "provider_authorization_modified": False,
            "telegram_sends": 0,
            "trades_created": 0,
            "paper_trades_created": 0,
            "normal_rsi_signal_rows_written": 0,
            "triggered_fade_created": 0,
            "automatic_threshold_changes": False,
            "automatic_route_changes": False,
        },
    }


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

    return _render_campaign_report(report)


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
        audit = _read_json(namespace_dir / PILOT_AUDIT_FILENAME)
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
        generations.append(
            _generation_row(
                namespace_dir,
                manifest=manifest,
                audit=audit,
                validation=validation,
                current_authority=current_authority,
            )
        )
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
    candidates = read_jsonl(namespace_dir / integrated_radar.INTEGRATED_CANDIDATES_FILENAME)
    outcomes = (
        read_jsonl(namespace_dir / integrated_radar.INTEGRATED_OUTCOMES_FILENAME)
        if validation.integrated_outcome_artifact_bound else []
    )
    operator = _read_json(namespace_dir / OPERATOR_STATE_FILENAME)
    request = _read_json(namespace_dir / REQUEST_LEDGER_FILENAME)
    counted = validation.campaign_counted
    source = validation.counting_source
    reason = validation.counting_reason
    route_counts = Counter(
        _text(row.get("radar_route")) or "diagnostic" for row in candidates
    )
    run_id = _text(manifest.get("run_id") or audit.get("exact_run_id"))
    observed_at = _text(manifest.get("observed_at") or audit.get("generated_at"))
    publication = _mapping(audit.get("publication"))
    exact_pointer = _current_authority_matches(
        current_authority,
        namespace=namespace_dir.name,
        run_id=run_id,
    )
    audit_authority_bound = market_no_send_audit.has_bound_publication_authority(
        audit, operator, namespace=namespace_dir.name, run_id=run_id
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
        "publication": {
            "ever_authoritative": bool(
                audit_authority_bound or exact_pointer
            ),
            "first_authoritative_at": (
                _safe_timestamp(publication.get("first_authoritative_at"))
                if audit_authority_bound else None
            ) or (
                _safe_timestamp(audit.get("generated_at"))
                if audit_authority_bound else None
            ) or (
                _safe_timestamp(current_authority.get("authority_checked_at"))
                if exact_pointer else None
            ),
            "audit_authority_binding_valid": audit_authority_bound,
            "authority_source": (
                "pilot_audit_exact_binding" if audit_authority_bound
                else "current_pointer_exact_binding" if exact_pointer else None
            ),
            "audit_status": _text(publication.get("status")) or "not_recorded",
            "currently_authoritative": exact_pointer,
        },
        "safety": _generation_safety(manifest, audit),
        "artifact_names": {
            "manifest": RUN_MANIFEST_FILENAME,
            "pilot_audit": PILOT_AUDIT_FILENAME if audit else None,
            "request_ledger": REQUEST_LEDGER_FILENAME if request else None,
            "outcomes": integrated_radar.INTEGRATED_OUTCOMES_FILENAME,
        },
    }


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
        "provider_failed_attempts": 0,
        "blocked_attempts": 0,
    }


def _campaign_outcomes(
    base: Path,
    generations: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    candidates_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    pending_rows: list[dict[str, Any]] = []
    for generation in generations:
        namespace = _text(generation.get("artifact_namespace"))
        if not namespace:
            continue
        try:
            namespace_dir = safe_existing_namespace_dir(base, namespace)
        except MarketNoSendError:
            continue
        for source in read_jsonl(namespace_dir / integrated_radar.INTEGRATED_CANDIDATES_FILENAME):
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
    campaign_path = (
        base
        / market_no_send_history_cache.LIVE_HISTORY_CACHE_NAMESPACE
        / CAMPAIGN_OUTCOMES_FILENAME
    )
    campaign_rows: list[dict[str, Any]] = []
    try:
        ledger_sources = read_jsonl(campaign_path)
    except MarketNoSendError:
        ledger_sources = []
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
        "pending": counts["pending"],
        "matured": counts["matured"],
        "missing_data": counts["missing_data"],
        "other": counts["other"],
        "status_counts": dict(sorted(counts.items())),
        "source": source,
        "refresh_build_error_count": sum(refresh_errors.values()),
        "refresh_build_error_counts": dict(sorted(refresh_errors.items())),
        "human_feedback_optional": True,
        "automatic_threshold_changes": False,
    }


def _outcome_state(row: Mapping[str, Any]) -> str:
    state = _text(row.get("maturation_state") or row.get("outcome_status") or row.get("outcome_label")).casefold()
    if state in _MATURED_STATES:
        return "matured"
    if state in _MISSING_STATES:
        return "missing_data"
    metadata = _mapping(row.get("horizon_metadata"))
    horizon_states = {
        _text(_mapping(value).get("maturity_status")).casefold()
        for value in metadata.values()
    }
    if horizon_states & _MATURED_STATES:
        return "matured"
    if state in _PENDING_STATES or horizon_states & _PENDING_STATES:
        return "pending"
    if horizon_states and horizon_states <= _MISSING_STATES:
        return "missing_data"
    returns = _mapping(row.get("return_by_horizon") or row.get("horizons"))
    if any(_number(value) is not None for value in returns.values()):
        return "matured"
    return "other"


def _outcome_rank(row: Mapping[str, Any]) -> tuple[int, str]:
    rank = {"matured": 3, "missing_data": 2, "pending": 1, "other": 0}[_outcome_state(row)]
    return rank, _text(row.get("outcome_evaluated_at"))


def _baseline_maturity(base: Path, *, evaluated: datetime) -> dict[str, Any]:
    try:
        history_config = market_history.MarketHistoryConfig(
            minimum_observation_spacing=timedelta(
                minutes=int(project_config.DECISION_RADAR_MIN_OBSERVATION_SPACING_MINUTES)
            )
        )
    except (TypeError, ValueError):
        history_config = market_history.MarketHistoryConfig()
    try:
        result = market_no_send_history_cache.cache_readiness(
            base,
            history_filename=HISTORY_FILENAME,
            now=evaluated,
            config=history_config,
        )
    except TypeError:  # historical adapter during rolling upgrades
        result = market_no_send_history_cache.cache_readiness(
            base,
            history_filename=HISTORY_FILENAME,
        )
    output = dict(result)
    output.setdefault("baseline_feature_readiness", {})
    output.setdefault("baseline_counted_observation_count", output.get("baseline_observation_count", 0))
    output.setdefault("baseline_too_close_observation_count", 0)
    rejection_counts = _mapping(output.get("baseline_rejection_counts"))
    output.setdefault(
        "baseline_duplicate_observation_count",
        _int(rejection_counts.get("duplicate")),
    )
    output.setdefault(
        "baseline_duplicate_conflict_count",
        _int(rejection_counts.get("duplicate_conflict")),
    )
    output.setdefault(
        "minimum_observation_spacing_seconds",
        int(market_history.MarketHistoryConfig().minimum_observation_spacing.total_seconds()),
    )
    next_eligible = market_observation_campaign_cadence.legacy_next_eligible(output)
    output.setdefault("next_eligible_observation_at", next_eligible)
    return output


def _data_quality_limitations(metrics: Mapping[str, Any]) -> list[dict[str, Any]]:
    limitations: list[dict[str, Any]] = []
    selected = _int(metrics.get("selected_market_row_count"))
    spread = _int(metrics.get("spread_available_count"))
    if selected == 0 or spread < selected:
        limitations.append({
            "category": "execution_quality_spread",
            "detail": (
                f"Trusted spread coverage is {spread}/{selected}. Provider selection is deferred "
                "until the operator identifies the intended execution venue."
            ),
            "provider_selection": "deferred_pending_execution_venue",
        })
    if _int(metrics.get("proxy_feature_count")) > 0:
        limitations.append({
            "category": "proxy_market_features",
            "detail": (
                f"The campaign retains {_int(metrics.get('proxy_feature_count'))} proxy feature "
                "observations; proxy evidence remains explicitly quality-capped."
            ),
        })
    if _text(metrics.get("baseline_status")) != "warm":
        limitations.append({
            "category": "temporal_baseline_maturity",
            "detail": "The required feature/time-aware temporal baseline is not globally warm.",
        })
    return limitations


def _campaign_status(metrics: Mapping[str, Any], baseline: Mapping[str, Any]) -> str:
    if _int(metrics.get("real_cycles")) == 0:
        return "not_started"
    status = _text(baseline.get("baseline_status")) or "unknown"
    return "observing_warm_baseline" if status == "warm" else f"in_progress_baseline_{status}"


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
    summary = (
        f"Decision Radar campaign v2 has {_int(metrics.get('real_cycles'))} counted real/no-send "
        f"cycles and {_int(metrics.get('real_candidates'))} canonical {'idea' if _int(metrics.get('real_candidates')) == 1 else 'ideas'}; "
        f"{_int(metrics.get('pending_outcomes'))} {'outcome is' if _int(metrics.get('pending_outcomes')) == 1 else 'outcomes are'} pending and "
        f"{_int(metrics.get('matured_outcomes'))} are matured. "
        f"There are {len(provider_failed)} provider failures and {len(blocked)} blocked/preflight "
        f"attempts. Baseline status is {_text(baseline.get('baseline_status')) or 'unknown'} with "
        f"{_int(baseline.get('baseline_warm_asset_count'))}/{_int(baseline.get('baseline_asset_count'))} "
        f"warm assets. Pointer history contains {len(pointer_history)} bound {'generation' if len(pointer_history) == 1 else 'generations'} and current "
        f"authority is {_text(pointer.get('artifact_namespace')) or 'none'}. Data-quality limitation "
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
        "pointer_history_count": len(pointer_history),
        "current_authority": {
            key: pointer.get(key) for key in (
                "artifact_namespace", "run_id", "revision", "exact_operator_binding"
            )
        },
        "data_quality_limitation_categories": categories,
        "highest_value_missing_input_category": highest,
        "spread_provider_selection": "deferred_pending_operator_execution_venue",
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


def _load_root_attempts(base: Path) -> list[dict[str, Any]]:
    raw: list[Mapping[str, Any]] = []
    audit = _read_json(base / PILOT_AUDIT_FILENAME)
    if audit:
        raw.append(audit)
    receipt = _read_json(base / LATEST_ATTEMPT_FILENAME)
    if receipt:
        raw.append(receipt)
    raw.extend(read_jsonl(base / ATTEMPT_LEDGER_FILENAME))
    return [
        _attempt_row({}, row, namespace=_text(row.get("artifact_namespace")) or "unknown")
        for row in raw
        if _is_live_market_attempt({}, row)
    ]


def _attempt_row(
    manifest: Mapping[str, Any],
    audit: Mapping[str, Any],
    *,
    namespace: str,
) -> dict[str, Any]:
    status = _text(manifest.get("status") or audit.get("attempt_status") or audit.get("status") or "unknown")
    return {
        "attempt_id": _text(audit.get("attempt_id")) or None,
        "artifact_namespace": namespace,
        "run_id": _text(manifest.get("run_id") or audit.get("exact_run_id") or audit.get("run_id")) or None,
        "observed_at": _safe_timestamp(
            manifest.get("observed_at") or audit.get("observed_at") or audit.get("generated_at")
        ),
        "attempt_status": status,
        "provider": _text(manifest.get("provider") or audit.get("provider") or "coingecko"),
        "provider_call_attempted": _strict_true(manifest, audit, "provider_call_attempted"),
        "provider_request_succeeded": _strict_true(manifest, audit, "provider_request_succeeded"),
        "failure_class": _safe_error_class(
            manifest.get("failure_class") or audit.get("failure_class") or audit.get("error_class")
        ),
        "candidate_source_mode": _text(
            manifest.get("candidate_source_mode") or audit.get("candidate_source_mode") or "preflight_only"
        ),
        "no_send": (
            manifest.get("no_send") is True
            or audit.get("no_send") is True
            or _mapping(audit.get("safety")).get("no_send") is True
        ),
        "research_only": (
            manifest.get("research_only") is True
            or audit.get("research_only") is True
            or _mapping(audit.get("safety")).get("research_only") is True
        ),
    }


def _deduplicate_attempts(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    selected: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        attempt_id = _text(row.get("attempt_id"))
        key = (
            ("attempt_id", attempt_id)
            if attempt_id
            else (
                "legacy_attempt",
                row.get("artifact_namespace"),
                row.get("run_id"),
                row.get("observed_at"),
                row.get("attempt_status"),
                row.get("provider_call_attempted"),
                row.get("provider_request_succeeded"),
            )
        )
        selected[key] = dict(row)
    return sorted(selected.values(), key=_attempt_sort_key)


def _is_live_market_attempt(
    manifest: Mapping[str, Any],
    audit: Mapping[str, Any],
) -> bool:
    mode = _text(manifest.get("data_mode") or audit.get("data_mode")).casefold()
    acquisition = _text(
        manifest.get("data_acquisition_mode") or audit.get("data_acquisition_mode")
    ).casefold()
    candidate_mode = _text(
        manifest.get("candidate_source_mode") or audit.get("candidate_source_mode")
    ).casefold()
    provider = _text(manifest.get("provider") or audit.get("provider")).casefold()
    return bool(
        mode == "live"
        or acquisition in {"live_provider", "preflight_only"}
        or candidate_mode in {"live_no_send", "preflight_only"}
        or (provider == "coingecko" and audit.get("row_type") in {
            "event_market_no_send_pilot_audit",
            "event_market_no_send_latest_attempt",
        })
    ) and candidate_mode != "mocked_fixture" and mode != "mock"


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
    return {
        "artifact_namespace": snapshot.artifact_namespace,
        "profile": snapshot.profile,
        "run_id": snapshot.run_id,
        "revision": snapshot.revision,
        "operator_state_sha256": snapshot.operator_state_sha256,
        "authority_checked_at": snapshot.generation_authority_checked_at,
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


def _attempt_sort_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
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
