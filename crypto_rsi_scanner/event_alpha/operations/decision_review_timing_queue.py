"""Read-only discovery queue for exact Decision Radar review timing.

The queue is deliberately separate from the append-only timing ledger.  It
uses bounded campaign summaries only for discovery, then revalidates every
selected generation and idea through the closed publication contract before
showing a human action.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
import shlex
from typing import Any

from ..dashboard.loader import load_dashboard_snapshot
from . import daily_operations_publication
from . import decision_review_timing as timing


QUEUE_SCHEMA_ID = "decision_radar.idea_review_timing_queue"
QUEUE_SCHEMA_VERSION = 1
MAX_QUEUE_GENERATIONS = 256
MAX_QUEUE_IDEAS = 512


def build_review_timing_queue(
    artifact_base_dir: str | Path,
    generation_rows: Iterable[Mapping[str, Any]],
    *,
    evaluated_at: datetime | str,
) -> dict[str, Any]:
    """Discover exact receipt-backed ideas that await explicit human action."""

    evaluated = timing._parse_timestamp(
        timing._canonical_timestamp(evaluated_at, field="evaluated_at"),
        field="evaluated_at",
    )
    base = timing._safe_existing_base(artifact_base_dir)
    summaries = tuple(dict(row) for row in generation_rows)
    if len(summaries) > MAX_QUEUE_GENERATIONS:
        raise timing.DecisionReviewTimingError(
            "review_timing_queue_generation_limit"
        )

    eligible_bindings: list[dict[str, Any]] = []
    eligible_generation_count = 0
    skipped_reason_counts: dict[str, int] = {}
    skipped_candidate_count = 0
    seen_namespaces: set[str] = set()
    for summary in summaries:
        namespace = timing._identity(
            summary.get("artifact_namespace"), "artifact_namespace"
        )
        if namespace in seen_namespaces:
            raise timing.DecisionReviewTimingError(
                "review_timing_queue_namespace_duplicate"
            )
        seen_namespaces.add(namespace)
        candidate_count = timing._nonnegative_int(summary.get("candidate_count"))
        if candidate_count == 0:
            continue
        if candidate_count > MAX_QUEUE_IDEAS:
            raise timing.DecisionReviewTimingError(
                "review_timing_queue_candidate_limit"
            )
        reason = _generation_exclusion_reason(summary)
        if reason is not None:
            skipped_candidate_count += candidate_count
            skipped_reason_counts[reason] = skipped_reason_counts.get(reason, 0) + 1
            continue
        eligible_generation_count += 1
        idea_ids = _receipt_backed_generation_idea_ids(
            base,
            namespace,
            expected_candidate_count=candidate_count,
        )
        for idea_id in idea_ids:
            eligible_bindings.append(
                timing.load_idea_binding(base, namespace, idea_id)
            )
            if len(eligible_bindings) > MAX_QUEUE_IDEAS:
                raise timing.DecisionReviewTimingError(
                    "review_timing_queue_idea_limit"
                )

    all_events = timing.read_review_timing_events(base)
    selected_events = tuple(
        row
        for row in all_events
        if timing._parse_timestamp(row["recorded_at"], field="recorded_at")
        <= evaluated
    )
    grouped_events: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for event in selected_events:
        key = (str(event["artifact_namespace"]), str(event["idea_id"]))
        grouped_events.setdefault(key, {})[str(event["event_type"])] = event

    records: list[dict[str, Any]] = []
    for binding in sorted(
        eligible_bindings,
        key=lambda row: (
            str(row["idea_available_at"]),
            str(row["artifact_namespace"]),
            str(row["idea_id"]),
        ),
    ):
        key = (str(binding["artifact_namespace"]), str(binding["idea_id"]))
        group = grouped_events.get(key, {})
        for event in group.values():
            timing._require_event_matches_binding(event, binding)
        record = timing._review_record(binding, group)
        record.update(_queue_action(base, record))
        records.append(record)

    not_viewed_count = sum(row["review_status"] == "not_viewed" for row in records)
    in_review_count = sum(row["review_status"] == "in_review" for row in records)
    complete_count = sum(row["review_status"] == "complete" for row in records)
    action_required_count = not_viewed_count + in_review_count
    status = (
        "no_eligible_ideas"
        if not records
        else "action_required"
        if action_required_count
        else "complete"
    )
    return {
        "schema_id": QUEUE_SCHEMA_ID,
        "schema_version": QUEUE_SCHEMA_VERSION,
        "row_type": "decision_radar_idea_review_timing_queue",
        "generated_at": evaluated.isoformat(),
        "status": status,
        "generation_summaries_considered": len(summaries),
        "eligible_generation_count": eligible_generation_count,
        "eligible_idea_count": len(records),
        "action_required_count": action_required_count,
        "not_viewed_count": not_viewed_count,
        "in_review_count": in_review_count,
        "complete_count": complete_count,
        "skipped_candidate_count": skipped_candidate_count,
        "skipped_generation_reason_counts": dict(sorted(skipped_reason_counts.items())),
        "events_in_window_count": len(selected_events),
        "events_after_evaluated_at_count": len(all_events) - len(selected_events),
        "records": records,
        "eligibility_contract": (
            "campaign-counted live/no-send idea with valid final publication and "
            "owned-dashboard operations receipts; exact source generation revalidated"
        ),
        "excluded_legacy_or_unpublished_ideas_create_timing_evidence": False,
        "dashboard_reads_recorded_as_human_actions": False,
        "commands_require_explicit_confirmation": True,
        "provider_calls": 0,
        "writes": 0,
        "protocol_v2_evidence_eligible": False,
        "protocol_v2_annex_bound": False,
        "automatic_policy_effect": "none",
        "research_only": True,
        "safety": dict(timing._SAFETY),
    }


def _generation_exclusion_reason(summary: Mapping[str, Any]) -> str | None:
    if summary.get("campaign_counted") is not True:
        return "not_campaign_counted"
    publication = timing._mapping(summary.get("publication"))
    if publication.get("ever_authoritative") is not True:
        return "never_authoritative"
    if publication.get("final_publication_receipt_valid") is not True:
        return "final_publication_receipt_missing"
    if publication.get("operations_receipt_valid") is not True:
        return "operations_receipt_missing"
    return None


def _receipt_backed_generation_idea_ids(
    artifact_base_dir: Path,
    artifact_namespace: str,
    *,
    expected_candidate_count: int,
) -> tuple[str, ...]:
    publication = daily_operations_publication.validate_final_publication_contract(
        artifact_base_dir,
        artifact_namespace,
        require_current=False,
        require_operations=True,
    )
    if not publication.valid:
        detail = publication.errors[0] if publication.errors else "unknown"
        raise timing.DecisionReviewTimingError(
            f"review_timing_queue_publication_contract_invalid:{detail}"
        )
    operations_receipt = timing._mapping(publication.operations_receipt)
    timing._canonical_timestamp(
        operations_receipt.get("recorded_at"), field="idea_available_at"
    )
    try:
        snapshot = load_dashboard_snapshot(artifact_base_dir, artifact_namespace)
    except Exception as exc:  # noqa: BLE001 - trust boundary stays fail closed
        raise timing.DecisionReviewTimingError(
            "review_timing_queue_exact_generation_invalid"
        ) from exc
    if not timing._historical_snapshot_receipt_eligible(snapshot):
        raise timing.DecisionReviewTimingError(
            "review_timing_queue_generation_not_authoritative"
        )
    candidates = snapshot.current_candidates
    if isinstance(candidates, (str, bytes, bytearray)) or not isinstance(
        candidates, Sequence
    ):
        raise timing.DecisionReviewTimingError(
            "review_timing_queue_candidates_invalid"
        )
    if len(candidates) != expected_candidate_count:
        raise timing.DecisionReviewTimingError(
            "review_timing_queue_candidate_count_mismatch"
        )
    idea_ids = tuple(
        timing._identity(
            timing._mapping(row).get("integrated_candidate_id")
            or timing._mapping(row).get("candidate_id"),
            "idea_id",
        )
        for row in candidates
    )
    if len(set(idea_ids)) != len(idea_ids):
        raise timing.DecisionReviewTimingError(
            "review_timing_queue_idea_id_duplicate"
        )
    return tuple(sorted(idea_ids))


def _queue_action(
    artifact_base_dir: Path,
    record: Mapping[str, Any],
) -> dict[str, Any]:
    status = str(record.get("review_status") or "")
    if status == "complete":
        return {
            "next_action": "none",
            "next_make_target": None,
            "next_safe_command": None,
            "requires_explicit_confirmation": False,
        }
    if status == "not_viewed":
        action = "record_first_view"
        target = "radar-review-timing-view"
    elif status == "in_review":
        action = "record_review_completion"
        target = "radar-review-timing-complete"
    else:
        raise timing.DecisionReviewTimingError(
            "review_timing_queue_status_invalid"
        )
    command = " ".join(
        (
            "CONFIRM=1",
            "make",
            target,
            "EVENT_ALPHA_ARTIFACT_BASE_DIR=" + shlex.quote(str(artifact_base_dir)),
            "RADAR_REVIEW_NAMESPACE="
            + shlex.quote(str(record["artifact_namespace"])),
            "RADAR_REVIEW_IDEA_ID=" + shlex.quote(str(record["idea_id"])),
            "RADAR_REVIEWER_ALIAS=YOUR_ALIAS",
            "PYTHON=.venv/bin/python",
        )
    )
    return {
        "next_action": action,
        "next_make_target": target,
        "next_safe_command": command,
        "reviewer_alias_placeholder": "replace YOUR_ALIAS before running",
        "requires_explicit_confirmation": True,
    }


__all__ = (
    "QUEUE_SCHEMA_ID",
    "build_review_timing_queue",
)
