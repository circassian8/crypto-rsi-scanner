"""Explicit human-review timing for canonical Decision Radar ideas.

Dashboard reads are intentionally observational and therefore cannot prove a
human view.  This module records the two human actions that matter for latency
measurement (first view and review completion) through a confirmed append-only
ledger.  Every event is bound to an exact receipt-backed Daily Operations idea.

The ledger is descriptive campaign evidence only.  It cannot change a route,
score, outcome, dashboard authority, or provider authorization, and it remains
ineligible for Protocol v2 until the sealed annex binds its clock and missing-
data rules.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import re
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..artifacts import fingerprints
from ..dashboard.loader import load_dashboard_snapshot
from ..radar.decision_model_surfaces import decision_model_values
from . import daily_operations_publication
from .market_no_send_io import read_regular_bytes, safe_existing_namespace_dir


SCHEMA_ID = "decision_radar.idea_review_timing_event"
SCHEMA_VERSION = 1
REPORT_SCHEMA_ID = "decision_radar.idea_review_timing_report"
REPORT_SCHEMA_VERSION = 1
REVIEW_QUEUE_COMMAND = "make radar-review-timing-queue PYTHON=.venv/bin/python"
OPERATOR_CONTEXT_SCHEMA_ID = "decision_radar.idea_review_operator_context"
OPERATOR_CONTEXT_SCHEMA_VERSION = 1
LEDGER_FILENAME = "event_decision_radar_review_timing_events.jsonl"
LEDGER_DIRECTORY = "radar_market_history_cache"
EVENT_TYPES = frozenset({"first_viewed", "review_completed"})
MAX_EVENT_BYTES = 12 * 1024
MAX_LEDGER_BYTES = 16 * 1024 * 1024
MAX_LEDGER_EVENTS = 4096
MAX_REPORT_RECORDS = 2048

_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_EVENT_ID_RE = re.compile(r"^decision-review-timing-v1:[0-9a-f]{64}$")
_IDENTITY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:+|\-]{0,199}$")
_ALIAS_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_SECRET_MARKER_RE = re.compile(
    rb"(?:authorization\s*[:=]\s*bearer|(?:api[_-]?key|access[_-]?token|"
    rb"password|passwd|secret|credential)\s*[:=]|-----BEGIN\s+(?:RSA\s+)?"
    rb"PRIVATE\s+KEY-----)",
    re.IGNORECASE,
)
_OPEN_SUPPORTS_DIR_FD = os.open in os.supports_dir_fd
_STAT_SUPPORTS_DIR_FD = os.stat in os.supports_dir_fd
_STAT_SUPPORTS_FOLLOW_SYMLINKS = os.stat in os.supports_follow_symlinks

_SAFETY = {
    "provider_calls": 0,
    "authorization_mutations": 0,
    "telegram_sends": 0,
    "trades": 0,
    "orders": 0,
    "event_alpha_paper_trades": 0,
    "normal_rsi_writes": 0,
    "event_alpha_triggered_fade": 0,
    "dashboard_authority_mutations": 0,
    "production_policy_mutations": 0,
}

_EVENT_FIELDS = frozenset(
    {
        "schema_id",
        "schema_version",
        "event_id",
        "event_digest",
        "event_type",
        "recorded_at",
        "artifact_namespace",
        "run_id",
        "profile",
        "revision",
        "operator_state_sha256",
        "idea_id",
        "core_opportunity_id",
        "decision_projection_sha256",
        "integrated_candidates_sha256",
        "core_opportunities_sha256",
        "publication_receipt_sha256",
        "operations_receipt_sha256",
        "idea_observed_at",
        "idea_available_at",
        "pipeline_latency_seconds",
        "radar_route",
        "primary_thesis_origin",
        "directional_bias",
        "decision_radar_campaign_counted",
        "reviewer_alias",
        "explicit_human_action",
        "clock_source",
        "research_only",
        "protocol_v2_evidence_eligible",
        "protocol_v2_annex_bound",
        "automatic_policy_effect",
        "safety",
    }
)

_BINDING_FIELDS = tuple(
    field
    for field in _EVENT_FIELDS
    if field
    not in {
        "event_id",
        "event_digest",
        "event_type",
        "recorded_at",
        "reviewer_alias",
        "explicit_human_action",
    }
)
_SOURCE_BINDING_FIELDS = frozenset(
    {
        "artifact_namespace",
        "run_id",
        "profile",
        "revision",
        "operator_state_sha256",
        "idea_id",
        "core_opportunity_id",
        "decision_projection_sha256",
        "integrated_candidates_sha256",
        "core_opportunities_sha256",
        "publication_receipt_sha256",
        "operations_receipt_sha256",
        "idea_observed_at",
        "idea_available_at",
        "pipeline_latency_seconds",
        "radar_route",
        "primary_thesis_origin",
        "directional_bias",
        "decision_radar_campaign_counted",
    }
)
_OPERATOR_CONTEXT_FIELDS = frozenset(
    {
        "schema_id",
        "schema_version",
        "canonical_asset_id",
        "symbol",
        "anomaly_type",
        "catalyst_status",
        "confidence_band",
        "market_phase",
        "timing_state",
        "preferred_horizon",
        "radar_actionable",
        "actionability_score",
        "evidence_confidence_score",
        "risk_score",
        "urgency_score",
        "candidate_identity_bound_by",
        "decision_values_bound_by",
        "presentation_only",
    }
)


class DecisionReviewTimingError(RuntimeError):
    """Stable fail-closed error for review-timing evidence."""


def review_timing_ledger_path(artifact_base_dir: str | Path) -> Path:
    """Return the one shared campaign ledger path without creating it."""

    base = _safe_existing_base(artifact_base_dir)
    return base / LEDGER_DIRECTORY / LEDGER_FILENAME


def load_idea_binding(
    artifact_base_dir: str | Path,
    artifact_namespace: str,
    idea_id: str,
    *,
    include_operator_context: bool = False,
) -> dict[str, Any]:
    """Load one genuine canonical idea through its final publication contract."""

    if type(include_operator_context) is not bool:
        raise ValueError("review_timing_operator_context_flag_invalid")

    base = _safe_existing_base(artifact_base_dir)
    namespace = _identity(artifact_namespace, "artifact_namespace")
    requested_idea = _identity(idea_id, "idea_id")
    namespace_dir = safe_existing_namespace_dir(base, namespace)
    publication = daily_operations_publication.validate_final_publication_contract(
        base,
        namespace,
        require_current=False,
        require_operations=True,
    )
    if not publication.valid:
        detail = publication.errors[0] if publication.errors else "unknown"
        raise DecisionReviewTimingError(
            f"review_timing_publication_contract_invalid:{detail}"
        )
    publication_receipt = _mapping(publication.publication_receipt)
    operations_receipt = _mapping(publication.operations_receipt)
    if not publication_receipt or not operations_receipt:
        raise DecisionReviewTimingError("review_timing_final_receipts_missing")

    available_at = _canonical_timestamp(
        operations_receipt.get("recorded_at"),
        field="idea_available_at",
    )
    try:
        snapshot = load_dashboard_snapshot(base, namespace)
    except Exception as exc:  # noqa: BLE001 - trust boundary stays fail closed
        raise DecisionReviewTimingError(
            "review_timing_exact_generation_invalid"
        ) from exc
    if not _historical_snapshot_receipt_eligible(snapshot):
        raise DecisionReviewTimingError("review_timing_generation_not_authoritative")

    matches = [
        dict(row)
        for row in snapshot.current_candidates
        if str(row.get("integrated_candidate_id") or row.get("candidate_id") or "")
        == requested_idea
    ]
    if len(matches) != 1:
        raise DecisionReviewTimingError("review_timing_idea_not_unique_in_generation")
    idea = matches[0]
    projection = decision_model_values(idea)
    if not projection or projection != _mapping(idea.get("decision_projection")):
        raise DecisionReviewTimingError("review_timing_decision_projection_invalid")
    if (
        idea.get("research_only") is not True
        or idea.get("decision_radar_campaign_counted") is not True
        or idea.get("decision_radar_campaign_eligible") is not True
        or idea.get("candidate_source_mode") != "live_no_send"
        or idea.get("data_acquisition_mode") != "live_provider"
    ):
        raise DecisionReviewTimingError("review_timing_idea_not_genuine_campaign_evidence")

    observed_at = _canonical_timestamp(
        projection.get("decision_evaluated_at"),
        field="idea_observed_at",
    )
    observed_time = _parse_timestamp(observed_at, field="idea_observed_at")
    available_time = _parse_timestamp(available_at, field="idea_available_at")
    if observed_time > available_time:
        raise DecisionReviewTimingError("review_timing_availability_precedes_idea")

    artifacts = _mapping(snapshot.operator_state.get("artifacts"))
    integrated_sha = _artifact_sha(artifacts, "integrated_candidates")
    core_sha = _artifact_sha(artifacts, "core_opportunities")
    publication_raw = read_regular_bytes(
        namespace_dir / daily_operations_publication.PUBLICATION_RECEIPT_FILENAME
    )
    operations_raw = read_regular_bytes(
        namespace_dir / daily_operations_publication.OPERATIONS_RECEIPT_FILENAME
    )
    if publication_raw is None or operations_raw is None:
        raise DecisionReviewTimingError("review_timing_final_receipt_bytes_missing")
    projection_sha = _digest_value(projection)
    pipeline_latency = _duration_seconds(observed_time, available_time)
    binding = {
        "artifact_namespace": namespace,
        "run_id": _identity(snapshot.run_id, "run_id"),
        "profile": _identity(snapshot.profile, "profile"),
        "revision": _positive_int(snapshot.revision, "revision"),
        "operator_state_sha256": _digest(snapshot.operator_state_sha256, "operator_state"),
        "idea_id": requested_idea,
        "core_opportunity_id": _identity(
            idea.get("core_opportunity_id"), "core_opportunity_id"
        ),
        "decision_projection_sha256": projection_sha,
        "integrated_candidates_sha256": integrated_sha,
        "core_opportunities_sha256": core_sha,
        "publication_receipt_sha256": hashlib.sha256(publication_raw).hexdigest(),
        "operations_receipt_sha256": hashlib.sha256(operations_raw).hexdigest(),
        "idea_observed_at": observed_at,
        "idea_available_at": available_at,
        "pipeline_latency_seconds": pipeline_latency,
        "radar_route": _identity(projection.get("radar_route"), "radar_route"),
        "primary_thesis_origin": _identity(
            projection.get("primary_thesis_origin"), "primary_thesis_origin"
        ),
        "directional_bias": _identity(
            projection.get("directional_bias"), "directional_bias"
        ),
        "decision_radar_campaign_counted": True,
    }
    if include_operator_context:
        binding["operator_review_context"] = _operator_review_context(
            idea,
            projection,
        )
    return binding


def build_review_timing_event(
    binding: Mapping[str, Any],
    *,
    event_type: str,
    reviewer_alias: str,
    recorded_at: datetime | str | None = None,
) -> dict[str, Any]:
    """Build one canonical explicit human-action event without writing."""

    kind = str(event_type or "").strip()
    if kind not in EVENT_TYPES:
        raise ValueError("review_timing_event_type_invalid")
    alias = str(reviewer_alias or "").strip()
    if not _ALIAS_RE.fullmatch(alias):
        raise ValueError("review_timing_reviewer_alias_invalid")
    bound = _validated_binding(binding)
    recorded = _canonical_timestamp(
        recorded_at or datetime.now(timezone.utc),
        field="recorded_at",
    )
    if _parse_timestamp(recorded, field="recorded_at") < _parse_timestamp(
        bound["idea_available_at"], field="idea_available_at"
    ):
        raise ValueError("review_timing_event_precedes_availability")
    identity_body = {
        "artifact_namespace": bound["artifact_namespace"],
        "idea_id": bound["idea_id"],
        "event_type": kind,
    }
    body: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "event_id": "decision-review-timing-v1:" + _digest_value(identity_body),
        "event_type": kind,
        "recorded_at": recorded,
        **bound,
        "reviewer_alias": alias,
        "explicit_human_action": True,
        "clock_source": "host_utc_clock_at_explicit_confirmed_command",
        "research_only": True,
        "protocol_v2_evidence_eligible": False,
        "protocol_v2_annex_bound": False,
        "automatic_policy_effect": "none",
        "safety": dict(_SAFETY),
    }
    event = {**body, "event_digest": _digest_value(body)}
    errors = validate_review_timing_event(event)
    if errors:
        raise ValueError("review_timing_event_invalid:" + ";".join(errors))
    return event


def validate_review_timing_event(event: Mapping[str, Any]) -> tuple[str, ...]:
    """Validate one self-contained canonical timing event."""

    errors: list[str] = []
    if not isinstance(event, Mapping):
        return ("event_not_mapping",)
    if set(event) != _EVENT_FIELDS:
        errors.append("event_fields_invalid")
    if event.get("schema_id") != SCHEMA_ID or event.get("schema_version") != SCHEMA_VERSION:
        errors.append("event_schema_invalid")
    kind = str(event.get("event_type") or "")
    if kind not in EVENT_TYPES:
        errors.append("event_type_invalid")
    event_id = str(event.get("event_id") or "")
    if not _EVENT_ID_RE.fullmatch(event_id):
        errors.append("event_id_invalid")
    else:
        try:
            expected_id = "decision-review-timing-v1:" + _digest_value(
                {
                    "artifact_namespace": event.get("artifact_namespace"),
                    "idea_id": event.get("idea_id"),
                    "event_type": kind,
                }
            )
        except ValueError:
            errors.append("event_id_binding_value_invalid")
        else:
            if event_id != expected_id:
                errors.append("event_id_binding_mismatch")
    for field in (
        "artifact_namespace",
        "run_id",
        "profile",
        "idea_id",
        "core_opportunity_id",
        "radar_route",
        "primary_thesis_origin",
        "directional_bias",
    ):
        if not _IDENTITY_RE.fullmatch(str(event.get(field) or "")):
            errors.append(f"{field}_invalid")
    revision = event.get("revision")
    if type(revision) is not int or revision < 1:
        errors.append("revision_invalid")
    for field in (
        "operator_state_sha256",
        "decision_projection_sha256",
        "integrated_candidates_sha256",
        "core_opportunities_sha256",
        "publication_receipt_sha256",
        "operations_receipt_sha256",
    ):
        if not _DIGEST_RE.fullmatch(str(event.get(field) or "")):
            errors.append(f"{field}_invalid")
    timestamps: dict[str, datetime] = {}
    for field in ("idea_observed_at", "idea_available_at", "recorded_at"):
        try:
            value = _canonical_timestamp(event.get(field), field=field)
            timestamps[field] = _parse_timestamp(value, field=field)
            if value != event.get(field):
                errors.append(f"{field}_not_canonical_utc")
        except (ValueError, DecisionReviewTimingError):
            errors.append(f"{field}_invalid")
    if set(timestamps) == {"idea_observed_at", "idea_available_at", "recorded_at"}:
        if timestamps["idea_observed_at"] > timestamps["idea_available_at"]:
            errors.append("availability_precedes_idea")
        if timestamps["recorded_at"] < timestamps["idea_available_at"]:
            errors.append("event_precedes_availability")
        expected = _duration_seconds(
            timestamps["idea_observed_at"], timestamps["idea_available_at"]
        )
        if event.get("pipeline_latency_seconds") != expected:
            errors.append("pipeline_latency_mismatch")
    value = event.get("pipeline_latency_seconds")
    if type(value) not in (int, float) or not math.isfinite(float(value)) or value < 0:
        errors.append("pipeline_latency_invalid")
    if not _ALIAS_RE.fullmatch(str(event.get("reviewer_alias") or "")):
        errors.append("reviewer_alias_invalid")
    if (
        event.get("decision_radar_campaign_counted") is not True
        or event.get("explicit_human_action") is not True
        or event.get("clock_source") != "host_utc_clock_at_explicit_confirmed_command"
        or event.get("research_only") is not True
        or event.get("protocol_v2_evidence_eligible") is not False
        or event.get("protocol_v2_annex_bound") is not False
        or event.get("automatic_policy_effect") != "none"
    ):
        errors.append("event_policy_state_invalid")
    if event.get("safety") != _SAFETY:
        errors.append("event_safety_invalid")
    try:
        payload = canonical_json_bytes(event)
    except ValueError:
        errors.append("event_not_canonical_json_value")
    else:
        if len(payload) > MAX_EVENT_BYTES:
            errors.append("event_too_large")
        if _SECRET_MARKER_RE.search(payload):
            errors.append("event_secret_marker_detected")
        declared = str(event.get("event_digest") or "")
        body = {key: value for key, value in event.items() if key != "event_digest"}
        if not _DIGEST_RE.fullmatch(declared) or declared != _digest_value(body):
            errors.append("event_digest_invalid")
    return tuple(dict.fromkeys(errors))


def validate_review_timing_events(
    events: Iterable[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    """Validate the bounded ledger plus cross-event sequence and binding rules."""

    rows = tuple(dict(row) for row in events)
    if len(rows) > MAX_LEDGER_EVENTS:
        raise DecisionReviewTimingError("review_timing_ledger_event_limit")
    by_event_id: dict[str, bytes] = {}
    by_idea: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for row in rows:
        errors = validate_review_timing_event(row)
        if errors:
            raise DecisionReviewTimingError(
                "review_timing_ledger_row_invalid:" + ";".join(errors)
            )
        payload = canonical_json_bytes(row)
        event_id = str(row["event_id"])
        if event_id in by_event_id:
            suffix = "_drift" if by_event_id[event_id] != payload else ""
            raise DecisionReviewTimingError(
                "review_timing_duplicate_event_id" + suffix
            )
        by_event_id[event_id] = payload
        key = (str(row["artifact_namespace"]), str(row["idea_id"]))
        kind = str(row["event_type"])
        group = by_idea.setdefault(key, {})
        if kind in group:
            raise DecisionReviewTimingError("review_timing_duplicate_event_type")
        group[kind] = row
    for group in by_idea.values():
        first = group.get("first_viewed")
        complete = group.get("review_completed")
        if complete is not None and first is None:
            raise DecisionReviewTimingError("review_timing_completion_without_first_view")
        if first is not None and complete is not None:
            if any(first.get(field) != complete.get(field) for field in _BINDING_FIELDS):
                raise DecisionReviewTimingError("review_timing_cross_event_binding_drift")
            if _parse_timestamp(
                complete["recorded_at"], field="recorded_at"
            ) < _parse_timestamp(first["recorded_at"], field="recorded_at"):
                raise DecisionReviewTimingError("review_timing_completion_precedes_first_view")
    return rows


def read_review_timing_events(
    artifact_base_dir: str | Path,
) -> tuple[dict[str, Any], ...]:
    """Read and fully validate the shared ledger without writing."""

    path = review_timing_ledger_path(artifact_base_dir)
    payload = _read_ledger_bytes(path)
    rows = _parse_ledger(payload)
    return validate_review_timing_events(rows)


def record_review_timing_event(
    artifact_base_dir: str | Path,
    *,
    artifact_namespace: str,
    idea_id: str,
    event_type: str,
    reviewer_alias: str,
    confirm: bool,
    recorded_at: datetime | str | None = None,
) -> dict[str, Any]:
    """Confirm and append one action; exact retries return the stored event."""

    if confirm is not True:
        raise PermissionError("review_timing_confirmation_required")
    binding = load_idea_binding(artifact_base_dir, artifact_namespace, idea_id)
    path = review_timing_ledger_path(artifact_base_dir)
    existing = read_review_timing_events(artifact_base_dir)
    key = (binding["artifact_namespace"], binding["idea_id"])
    kind = str(event_type or "")
    prior = next(
        (
            row
            for row in existing
            if (row["artifact_namespace"], row["idea_id"]) == key
            and row["event_type"] == kind
        ),
        None,
    )
    if prior is not None:
        _require_event_matches_binding(prior, binding)
        return _append_result("already_present", prior, len(existing), 0)
    if kind == "review_completed" and not any(
        (row["artifact_namespace"], row["idea_id"]) == key
        and row["event_type"] == "first_viewed"
        for row in existing
    ):
        raise DecisionReviewTimingError("review_timing_completion_without_first_view")
    event = build_review_timing_event(
        binding,
        event_type=kind,
        reviewer_alias=reviewer_alias,
        recorded_at=recorded_at,
    )
    return _append_event(path, event)


def build_review_timing_report(
    artifact_base_dir: str | Path,
    *,
    evaluated_at: datetime | str,
    maximum_records: int = MAX_REPORT_RECORDS,
) -> dict[str, Any]:
    """Build a point-in-time campaign projection and revalidate every source idea."""

    if type(maximum_records) is not int or not 1 <= maximum_records <= MAX_REPORT_RECORDS:
        raise ValueError("review_timing_report_bound_invalid")
    evaluated = _parse_timestamp(
        _canonical_timestamp(evaluated_at, field="evaluated_at"),
        field="evaluated_at",
    )
    all_events = read_review_timing_events(artifact_base_dir)
    selected = tuple(
        row
        for row in all_events
        if _parse_timestamp(row["recorded_at"], field="recorded_at") <= evaluated
    )
    groups: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for row in selected:
        key = (str(row["artifact_namespace"]), str(row["idea_id"]))
        groups.setdefault(key, {})[str(row["event_type"])] = row
    if len(groups) > maximum_records:
        raise DecisionReviewTimingError("review_timing_report_record_limit")

    records: list[dict[str, Any]] = []
    for namespace, idea_id in sorted(groups):
        source_binding = load_idea_binding(artifact_base_dir, namespace, idea_id)
        group = groups[(namespace, idea_id)]
        for event in group.values():
            _require_event_matches_binding(event, source_binding)
        records.append(_review_record(source_binding, group))
    first_count = sum(record["first_operator_viewed_at"] is not None for record in records)
    complete_count = sum(record["review_completed_at"] is not None for record in records)
    path = review_timing_ledger_path(artifact_base_dir)
    payload = _read_ledger_bytes(path)
    status = (
        "no_events"
        if not records
        else "complete"
        if complete_count == len(records)
        else "in_progress"
    )
    return {
        "schema_id": REPORT_SCHEMA_ID,
        "schema_version": REPORT_SCHEMA_VERSION,
        "row_type": "decision_radar_idea_review_timing_report",
        "generated_at": evaluated.isoformat(),
        "status": status,
        "ledger_path": f"{LEDGER_DIRECTORY}/{LEDGER_FILENAME}",
        "ledger_sha256": hashlib.sha256(payload).hexdigest(),
        "ledger_event_count": len(all_events),
        "events_in_window_count": len(selected),
        "events_after_evaluated_at_count": len(all_events) - len(selected),
        "idea_record_count": len(records),
        "idea_record_count_definition": (
            "unique_exact_namespace_idea_pairs_with_at_least_one_recorded_"
            "explicit_human_action"
        ),
        "report_scope": "recorded_explicit_human_actions_only",
        "eligible_idea_discovery_scope": "separate_receipt_backed_review_queue",
        "eligible_idea_discovery_command": REVIEW_QUEUE_COMMAND,
        "zero_idea_records_meaning": (
            "no_explicit_human_actions_recorded_not_no_eligible_ideas"
        ),
        "first_view_record_count": first_count,
        "completed_review_record_count": complete_count,
        "incomplete_review_record_count": len(records) - complete_count,
        "records": records,
        "idea_available_at_definition": (
            "exact owned-dashboard operations receipt recorded_at; conservative "
            "provable availability, never inferred from GET or HEAD"
        ),
        "human_action_definition": (
            "explicit confirmed command only; dashboard requests and health probes do not count"
        ),
        "latency_seconds_definition": "idea_available_at_to_review_completed_at",
        "decision_campaign_attachment": "descriptive_exact_identity",
        "protocol_v2_evidence_eligible": False,
        "protocol_v2_annex_bound": False,
        "provider_calls": 0,
        "dashboard_reads_recorded_as_human_actions": False,
        "automatic_policy_effect": "none",
        "research_only": True,
        "safety": dict(_SAFETY),
    }


def validate_review_timing_sources(
    artifact_base_dir: str | Path,
) -> dict[str, Any]:
    """Revalidate every ledger event against its immutable source generation."""

    events = read_review_timing_events(artifact_base_dir)
    identities = sorted(
        {(str(row["artifact_namespace"]), str(row["idea_id"])) for row in events}
    )
    for namespace, idea_id in identities:
        binding = load_idea_binding(artifact_base_dir, namespace, idea_id)
        for event in events:
            if (
                event["artifact_namespace"] == namespace
                and event["idea_id"] == idea_id
            ):
                _require_event_matches_binding(event, binding)
    payload = _read_ledger_bytes(review_timing_ledger_path(artifact_base_dir))
    namespaces = sorted({namespace for namespace, _idea_id in identities})
    return {
        "status": "valid" if events else "valid_empty",
        "ledger_sha256": hashlib.sha256(payload).hexdigest(),
        "event_count": len(events),
        "idea_count": len(identities),
        "source_namespace_count": len(namespaces),
        "source_namespaces": namespaces,
        "provider_calls": 0,
        "writes": 0,
        "protocol_v2_evidence_eligible": False,
        "research_only": True,
    }


def campaign_metric_values(report: Mapping[str, Any]) -> dict[str, int]:
    """Project the bounded timing counts used by the campaign summary."""

    fields = {
        "review_timing_idea_records": "idea_record_count",
        "review_timing_first_views": "first_view_record_count",
        "review_timing_completed_reviews": "completed_review_record_count",
        "review_timing_incomplete_reviews": "incomplete_review_record_count",
    }
    return {
        metric: _nonnegative_int(report.get(source_field))
        for metric, source_field in fields.items()
    }


def _review_record(
    binding: Mapping[str, Any],
    group: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    first = _mapping(group.get("first_viewed"))
    complete = _mapping(group.get("review_completed"))
    observed = _parse_timestamp(binding["idea_observed_at"], field="idea_observed_at")
    available = _parse_timestamp(binding["idea_available_at"], field="idea_available_at")
    first_time = (
        _parse_timestamp(first["recorded_at"], field="first_operator_viewed_at")
        if first
        else None
    )
    complete_time = (
        _parse_timestamp(complete["recorded_at"], field="review_completed_at")
        if complete
        else None
    )
    latency = _duration_seconds(available, complete_time) if complete_time else None
    return {
        **dict(binding),
        "first_operator_viewed_at": first_time.isoformat() if first_time else None,
        "review_completed_at": complete_time.isoformat() if complete_time else None,
        "time_to_first_view_seconds": (
            _duration_seconds(available, first_time) if first_time else None
        ),
        "review_duration_seconds": (
            _duration_seconds(first_time, complete_time)
            if first_time and complete_time
            else None
        ),
        "latency_seconds": latency,
        "idea_to_review_completed_seconds": (
            _duration_seconds(observed, complete_time) if complete_time else None
        ),
        "first_view_reviewer_alias": first.get("reviewer_alias") if first else None,
        "completion_reviewer_alias": complete.get("reviewer_alias") if complete else None,
        "review_status": (
            "complete" if complete else "in_review" if first else "not_viewed"
        ),
        "clock_source": {
            "idea_observed_at": "canonical_decision_projection_utc",
            "idea_available_at": "daily_operations_operations_receipt_utc",
            "first_operator_viewed_at": (
                "host_utc_clock_at_explicit_confirmed_command" if first else "unavailable"
            ),
            "review_completed_at": (
                "host_utc_clock_at_explicit_confirmed_command" if complete else "unavailable"
            ),
        },
        "decision_campaign_attached": True,
        "protocol_v2_evidence_eligible": False,
        "protocol_v2_annex_bound": False,
        "research_only": True,
    }


def _operator_review_context(
    idea: Mapping[str, Any],
    projection: Mapping[str, Any],
) -> dict[str, Any]:
    """Project digest-bound facts needed to identify a queue item quickly."""

    context = {
        "schema_id": OPERATOR_CONTEXT_SCHEMA_ID,
        "schema_version": OPERATOR_CONTEXT_SCHEMA_VERSION,
        "canonical_asset_id": _identity(
            idea.get("canonical_asset_id") or idea.get("coin_id"),
            "canonical_asset_id",
        ),
        "symbol": _identity(
            idea.get("symbol") or idea.get("validated_symbol"),
            "symbol",
        ),
        "anomaly_type": _identity(
            projection.get("anomaly_type") or idea.get("anomaly_type"),
            "anomaly_type",
        ),
        "catalyst_status": _identity(
            projection.get("catalyst_status"),
            "catalyst_status",
        ),
        "confidence_band": _identity(
            projection.get("confidence_band"),
            "confidence_band",
        ),
        "market_phase": _identity(
            projection.get("market_phase"),
            "market_phase",
        ),
        "timing_state": _identity(
            projection.get("timing_state"),
            "timing_state",
        ),
        "preferred_horizon": _identity(
            projection.get("preferred_horizon"),
            "preferred_horizon",
        ),
        "radar_actionable": projection.get("radar_actionable"),
        "actionability_score": _bounded_score(
            projection.get("actionability_score"),
            "actionability_score",
        ),
        "evidence_confidence_score": _bounded_score(
            projection.get("evidence_confidence_score"),
            "evidence_confidence_score",
        ),
        "risk_score": _bounded_score(
            projection.get("risk_score"),
            "risk_score",
        ),
        "urgency_score": _bounded_score(
            projection.get("urgency_score"),
            "urgency_score",
        ),
        "candidate_identity_bound_by": "integrated_candidates_sha256",
        "decision_values_bound_by": "decision_projection_sha256",
        "presentation_only": True,
    }
    if type(context["radar_actionable"]) is not bool:
        raise DecisionReviewTimingError(
            "review_timing_operator_context_radar_actionable_invalid"
        )
    if not operator_review_context_valid(context):  # pragma: no cover - builder guard
        raise DecisionReviewTimingError("review_timing_operator_context_invalid")
    return context


def operator_review_context_valid(value: object) -> bool:
    """Validate the closed presentation-only queue context."""

    if not isinstance(value, Mapping) or set(value) != _OPERATOR_CONTEXT_FIELDS:
        return False
    if (
        value.get("schema_id") != OPERATOR_CONTEXT_SCHEMA_ID
        or value.get("schema_version") != OPERATOR_CONTEXT_SCHEMA_VERSION
        or value.get("radar_actionable") not in {True, False}
        or type(value.get("radar_actionable")) is not bool
        or value.get("candidate_identity_bound_by")
        != "integrated_candidates_sha256"
        or value.get("decision_values_bound_by") != "decision_projection_sha256"
        or value.get("presentation_only") is not True
    ):
        return False
    for field in (
        "canonical_asset_id",
        "symbol",
        "anomaly_type",
        "catalyst_status",
        "confidence_band",
        "market_phase",
        "timing_state",
        "preferred_horizon",
    ):
        if not _IDENTITY_RE.fullmatch(str(value.get(field) or "")):
            return False
    return all(
        type(value.get(field)) in (int, float)
        and math.isfinite(float(value[field]))
        and 0 <= float(value[field]) <= 100
        for field in (
            "actionability_score",
            "evidence_confidence_score",
            "risk_score",
            "urgency_score",
        )
    )


def _append_event(path: Path, event: Mapping[str, Any]) -> dict[str, Any]:
    payload = canonical_json_bytes(event)
    parent_fd = _open_parent(path.parent)
    descriptor = -1
    try:
        before = _entry_stat(parent_fd, path.name)
        if before is not None and not stat.S_ISREG(before.st_mode):
            raise DecisionReviewTimingError("review_timing_ledger_unsafe")
        flags = (
            os.O_RDWR
            | os.O_APPEND
            | getattr(os, "O_CLOEXEC", 0)
            | _required_flag("O_NOFOLLOW")
        )
        if before is None:
            flags |= os.O_CREAT | os.O_EXCL
        try:
            descriptor = os.open(path.name, flags, 0o600, dir_fd=parent_fd)
        except OSError as exc:
            raise DecisionReviewTimingError("review_timing_ledger_unsafe") from exc
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or (
            before is not None and _identity_tuple(before) != _identity_tuple(opened)
        ):
            raise DecisionReviewTimingError("review_timing_ledger_unsafe")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        existing_payload = _read_descriptor(descriptor)
        rows = list(validate_review_timing_events(_parse_ledger(existing_payload)))
        event_id = str(event["event_id"])
        prior = next((row for row in rows if row["event_id"] == event_id), None)
        if prior is not None:
            if canonical_json_bytes(prior) != payload:
                raise DecisionReviewTimingError("review_timing_event_id_drift")
            return _append_result("already_present", prior, len(rows), 0)
        candidate_rows = validate_review_timing_events((*rows, event))
        appended = payload + b"\n"
        if len(existing_payload) + len(appended) > MAX_LEDGER_BYTES:
            raise DecisionReviewTimingError("review_timing_ledger_size_limit")
        _write_all(descriptor, appended)
        os.fsync(descriptor)
        after = os.fstat(descriptor)
        named = _entry_stat(parent_fd, path.name)
        if named is None or _identity_tuple(named) != _identity_tuple(after):
            raise DecisionReviewTimingError("review_timing_ledger_identity_drift")
        os.fsync(parent_fd)
        return _append_result("appended", event, len(candidate_rows), 1)
    finally:
        if descriptor >= 0:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)
        os.close(parent_fd)


def _read_ledger_bytes(path: Path) -> bytes:
    try:
        parent_info = path.parent.lstat()
    except FileNotFoundError:
        return b""
    if not stat.S_ISDIR(parent_info.st_mode) or stat.S_ISLNK(parent_info.st_mode):
        raise DecisionReviewTimingError("review_timing_ledger_parent_unsafe")
    parent_fd = _open_parent(path.parent)
    descriptor = -1
    try:
        before = _entry_stat(parent_fd, path.name)
        if before is None:
            return b""
        if not stat.S_ISREG(before.st_mode):
            raise DecisionReviewTimingError("review_timing_ledger_unsafe")
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | _required_flag("O_NOFOLLOW")
        try:
            descriptor = os.open(path.name, flags, dir_fd=parent_fd)
        except OSError as exc:
            raise DecisionReviewTimingError("review_timing_ledger_unsafe") from exc
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or _identity_tuple(before) != _identity_tuple(opened):
            raise DecisionReviewTimingError("review_timing_ledger_unsafe")
        payload = _read_descriptor(descriptor)
        after = os.fstat(descriptor)
        named = _entry_stat(parent_fd, path.name)
        if (
            not _same_snapshot(opened, after)
            or named is None
            or not _same_snapshot(after, named)
        ):
            raise DecisionReviewTimingError("review_timing_ledger_identity_drift")
        return payload
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(parent_fd)


def _parse_ledger(payload: bytes) -> tuple[dict[str, Any], ...]:
    if not payload:
        return ()
    if len(payload) > MAX_LEDGER_BYTES:
        raise DecisionReviewTimingError("review_timing_ledger_size_limit")
    if not payload.endswith(b"\n"):
        raise DecisionReviewTimingError("review_timing_ledger_partial_row")
    lines = payload[:-1].split(b"\n")
    if len(lines) > MAX_LEDGER_EVENTS:
        raise DecisionReviewTimingError("review_timing_ledger_event_limit")
    rows: list[dict[str, Any]] = []
    for line in lines:
        if not line or len(line) > MAX_EVENT_BYTES:
            raise DecisionReviewTimingError("review_timing_ledger_row_invalid")
        try:
            value = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DecisionReviewTimingError("review_timing_ledger_row_invalid") from exc
        if not isinstance(value, Mapping) or canonical_json_bytes(value) != line:
            raise DecisionReviewTimingError("review_timing_ledger_row_noncanonical")
        rows.append(dict(value))
    return tuple(rows)


def _open_parent(path: Path) -> int:
    _require_descriptor_support()
    value = Path(path).expanduser().absolute()
    if not value.anchor or any(part in {"", ".", ".."} for part in value.parts[1:]):
        raise DecisionReviewTimingError("review_timing_ledger_parent_unsafe")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | _required_flag("O_DIRECTORY")
        | _required_flag("O_NOFOLLOW")
    )
    descriptor: int | None = None
    try:
        root_before = os.stat(value.anchor, follow_symlinks=False)
        descriptor = os.open(value.anchor, flags)
        root_opened = os.fstat(descriptor)
        if not stat.S_ISDIR(root_opened.st_mode) or not _same_identity(
            root_before, root_opened
        ):
            raise OSError("review timing filesystem root changed")
        for component in value.parts[1:]:
            before = os.stat(component, dir_fd=descriptor, follow_symlinks=False)
            if not stat.S_ISDIR(before.st_mode):
                raise OSError("review timing parent component is not a directory")
            next_descriptor = os.open(component, flags, dir_fd=descriptor)
            try:
                opened = os.fstat(next_descriptor)
                named = os.stat(component, dir_fd=descriptor, follow_symlinks=False)
                if (
                    not stat.S_ISDIR(opened.st_mode)
                    or not _same_identity(before, opened)
                    or not _same_identity(opened, named)
                ):
                    raise OSError("review timing parent component changed")
            except BaseException:
                os.close(next_descriptor)
                raise
            os.close(descriptor)
            descriptor = next_descriptor
    except OSError as exc:
        if descriptor is not None:
            os.close(descriptor)
        raise DecisionReviewTimingError("review_timing_ledger_parent_unsafe") from exc
    if descriptor is None:
        raise DecisionReviewTimingError("review_timing_ledger_parent_unsafe")
    return descriptor


def _read_descriptor(descriptor: int) -> bytes:
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = os.read(descriptor, min(64 * 1024, MAX_LEDGER_BYTES + 1 - total))
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        total += len(chunk)
        if total > MAX_LEDGER_BYTES:
            raise DecisionReviewTimingError("review_timing_ledger_size_limit")


def _write_all(descriptor: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(descriptor, payload[offset:])
        if written <= 0:
            raise DecisionReviewTimingError("review_timing_ledger_append_failed")
        offset += written


def _validated_binding(binding: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(binding, Mapping) or set(binding) != _SOURCE_BINDING_FIELDS:
        raise ValueError("review_timing_binding_fields_invalid")
    # Round-trip through a synthetic event so all field constraints stay in one
    # validator.  The synthetic metadata is discarded afterward.
    clean = dict(binding)
    for field in ("artifact_namespace", "run_id", "profile", "idea_id", "core_opportunity_id"):
        _identity(clean.get(field), field)
    _positive_int(clean.get("revision"), "revision")
    for field in (
        "operator_state_sha256",
        "decision_projection_sha256",
        "integrated_candidates_sha256",
        "core_opportunities_sha256",
        "publication_receipt_sha256",
        "operations_receipt_sha256",
    ):
        _digest(clean.get(field), field)
    observed = _parse_timestamp(
        _canonical_timestamp(clean.get("idea_observed_at"), field="idea_observed_at"),
        field="idea_observed_at",
    )
    available = _parse_timestamp(
        _canonical_timestamp(clean.get("idea_available_at"), field="idea_available_at"),
        field="idea_available_at",
    )
    if observed > available or clean.get("pipeline_latency_seconds") != _duration_seconds(
        observed, available
    ):
        raise ValueError("review_timing_binding_latency_invalid")
    if clean.get("decision_radar_campaign_counted") is not True:
        raise ValueError("review_timing_binding_not_campaign_counted")
    return clean


def _require_event_matches_binding(
    event: Mapping[str, Any], binding: Mapping[str, Any]
) -> None:
    allowed_fields = _SOURCE_BINDING_FIELDS | {"operator_review_context"}
    if frozenset(binding) not in {_SOURCE_BINDING_FIELDS, allowed_fields}:
        raise DecisionReviewTimingError("review_timing_source_binding_fields_invalid")
    if "operator_review_context" in binding and not operator_review_context_valid(
        binding.get("operator_review_context")
    ):
        raise DecisionReviewTimingError("review_timing_operator_context_invalid")
    if any(
        event.get(field) != binding.get(field)
        for field in _SOURCE_BINDING_FIELDS
    ):
        raise DecisionReviewTimingError("review_timing_source_binding_drift")


def _artifact_sha(artifacts: Mapping[str, Any], name: str) -> str:
    value = _mapping(artifacts.get(name)).get("sha256")
    return _digest(value, f"{name}_sha256")


def _safe_existing_base(value: str | Path) -> Path:
    path = Path(value).expanduser().absolute()
    try:
        info = path.lstat()
    except OSError as exc:
        raise DecisionReviewTimingError("review_timing_artifact_base_unavailable") from exc
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
        raise DecisionReviewTimingError("review_timing_artifact_base_unsafe")
    return path


def _identity(value: object, field: str) -> str:
    text = str(value or "").strip()
    if not _IDENTITY_RE.fullmatch(text):
        raise DecisionReviewTimingError(f"review_timing_{field}_invalid")
    return text


def _digest(value: object, field: str) -> str:
    text = str(value or "")
    if not _DIGEST_RE.fullmatch(text):
        raise DecisionReviewTimingError(f"review_timing_{field}_invalid")
    return text


def _positive_int(value: object, field: str) -> int:
    if type(value) is not int or value < 1:
        raise DecisionReviewTimingError(f"review_timing_{field}_invalid")
    return value


def _nonnegative_int(value: object) -> int:
    return value if type(value) is int and value >= 0 else 0


def _bounded_score(value: object, field: str) -> int | float:
    if (
        type(value) not in (int, float)
        or not math.isfinite(float(value))
        or not 0 <= float(value) <= 100
    ):
        raise DecisionReviewTimingError(
            f"review_timing_operator_context_{field}_invalid"
        )
    return value


def _canonical_timestamp(value: datetime | str | object, *, field: str) -> str:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "")
        if not text or len(text) > 64:
            raise ValueError(f"review_timing_{field}_invalid")
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"review_timing_{field}_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"review_timing_{field}_invalid")
    return parsed.astimezone(timezone.utc).isoformat()


def _parse_timestamp(value: object, *, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise DecisionReviewTimingError(f"review_timing_{field}_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DecisionReviewTimingError(f"review_timing_{field}_invalid")
    return parsed.astimezone(timezone.utc)


def _duration_seconds(start: datetime, end: datetime | None) -> float:
    if end is None:
        raise ValueError("review_timing_duration_end_missing")
    value = (end - start).total_seconds()
    if not math.isfinite(value) or value < 0:
        raise ValueError("review_timing_duration_invalid")
    return round(value, 6)


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    try:
        return fingerprints.canonical_json_bytes(value)
    except fingerprints.FingerprintError as exc:
        raise ValueError("review_timing_value_not_canonical_json") from exc


def _digest_value(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _historical_snapshot_receipt_eligible(snapshot: object) -> bool:
    """Accept an exact old snapshot only when time expiry is its sole defect."""

    if getattr(snapshot, "generation_authoritative", False) is True:
        return True
    reasons = tuple(getattr(snapshot, "generation_authority_reasons", ()) or ())
    return bool(reasons) and all(
        reason in {"generation:stale", "doctor:stale"} for reason in reasons
    )


def _entry_stat(parent_fd: int, name: str) -> os.stat_result | None:
    try:
        return os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None


def _identity_tuple(value: os.stat_result) -> tuple[int, int]:
    return value.st_dev, value.st_ino


def _same_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return _identity_tuple(left) == _identity_tuple(right)


def _same_snapshot(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        _same_identity(left, right)
        and left.st_size == right.st_size
        and left.st_mtime_ns == right.st_mtime_ns
        and left.st_ctime_ns == right.st_ctime_ns
    )


def _required_flag(name: str) -> int:
    value = getattr(os, name, 0)
    if not value:
        raise DecisionReviewTimingError("review_timing_descriptor_features_unavailable")
    return value


def _require_descriptor_support() -> None:
    if not (
        _OPEN_SUPPORTS_DIR_FD
        and _STAT_SUPPORTS_DIR_FD
        and _STAT_SUPPORTS_FOLLOW_SYMLINKS
        and hasattr(os, "O_DIRECTORY")
        and hasattr(os, "O_NOFOLLOW")
    ):
        raise DecisionReviewTimingError("review_timing_descriptor_features_unavailable")


def _append_result(
    status_value: str,
    event: Mapping[str, Any],
    event_count: int,
    append_count: int,
) -> dict[str, Any]:
    return {
        "status": status_value,
        "event_id": event["event_id"],
        "event_type": event["event_type"],
        "artifact_namespace": event["artifact_namespace"],
        "idea_id": event["idea_id"],
        "recorded_at": event["recorded_at"],
        "ledger_event_count": event_count,
        "ledger_appends": append_count,
        "provider_calls": 0,
        "dashboard_authority_mutations": 0,
        "automatic_policy_effect": "none",
        "protocol_v2_evidence_eligible": False,
        "research_only": True,
    }


__all__ = (
    "DecisionReviewTimingError",
    "EVENT_TYPES",
    "LEDGER_DIRECTORY",
    "LEDGER_FILENAME",
    "REPORT_SCHEMA_ID",
    "REVIEW_QUEUE_COMMAND",
    "SCHEMA_ID",
    "build_review_timing_event",
    "build_review_timing_report",
    "campaign_metric_values",
    "canonical_json_bytes",
    "load_idea_binding",
    "read_review_timing_events",
    "record_review_timing_event",
    "review_timing_ledger_path",
    "validate_review_timing_event",
    "validate_review_timing_events",
    "validate_review_timing_sources",
)
