"""Read-only inspection of one exact, receipt-backed Decision Radar card."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from ..dashboard.loader import load_dashboard_snapshot
from ..dashboard.secure_reader import open_anchored_namespace
from ..radar.decision_model_surfaces import decision_model_values
from . import daily_operations_publication
from . import decision_review_timing as timing


SCHEMA_ID = "decision_radar.idea_review_card_inspection"
SCHEMA_VERSION = 1
MAX_CARD_BYTES = 512 * 1024


def inspect_review_card(
    artifact_base_dir: str | Path,
    artifact_namespace: str,
    idea_id: str,
    *,
    evaluated_at: datetime | str | None = None,
) -> dict[str, Any]:
    """Return an exact verified card without recording a human timing event."""

    checked_at = timing._parse_timestamp(
        timing._canonical_timestamp(
            evaluated_at or datetime.now(timezone.utc),
            field="evaluated_at",
        ),
        field="evaluated_at",
    )
    base = timing._safe_existing_base(artifact_base_dir)
    namespace = timing._identity(artifact_namespace, "artifact_namespace")
    requested_idea = timing._identity(idea_id, "idea_id")
    binding = timing.load_idea_binding(
        base,
        namespace,
        requested_idea,
        include_operator_context=True,
    )
    snapshot = load_dashboard_snapshot(base, namespace, now=checked_at)
    _require_snapshot_matches_binding(snapshot, binding)

    matches = [
        dict(row)
        for row in snapshot.current_candidates
        if str(row.get("integrated_candidate_id") or row.get("candidate_id") or "")
        == requested_idea
        and str(row.get("core_opportunity_id") or "")
        == binding["core_opportunity_id"]
    ]
    if len(matches) != 1:
        raise timing.DecisionReviewTimingError(
            "review_card_idea_not_unique_in_generation"
        )
    core = matches[0]
    projection = decision_model_values(core)
    if (
        not projection
        or timing._digest_value(projection)
        != binding["decision_projection_sha256"]
    ):
        raise timing.DecisionReviewTimingError(
            "review_card_decision_projection_drift"
        )

    stored_card_path = core.get("research_card_path") or core.get("card_path")
    member = _card_member(stored_card_path, namespace=namespace)
    artifacts = timing._mapping(snapshot.operator_state.get("artifacts"))
    card_tree = timing._mapping(artifacts.get("research_cards"))
    if (
        card_tree.get("status") != "current"
        or card_tree.get("path") != "research_cards"
        or card_tree.get("run_id") != binding["run_id"]
    ):
        raise timing.DecisionReviewTimingError(
            "review_card_tree_manifest_invalid"
        )
    with open_anchored_namespace(snapshot.namespace_dir) as reader:
        card_bytes, read_error = reader.read_verified_directory_member(
            "research_cards",
            member,
            expected_fingerprint=card_tree,
            max_member_bytes=MAX_CARD_BYTES,
        )
    if read_error or card_bytes is None:
        raise timing.DecisionReviewTimingError(
            "review_card_exact_read_invalid:" + (read_error or "unreadable")
        )
    if timing._SECRET_MARKER_RE.search(card_bytes):
        raise timing.DecisionReviewTimingError("review_card_secret_marker_detected")
    try:
        markdown = card_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise timing.DecisionReviewTimingError("review_card_utf8_invalid") from exc
    _require_card_lineage(markdown, binding)

    expires_at = timing._canonical_timestamp(
        projection.get("expires_at"),
        field="expires_at",
    )
    expired = (
        timing._parse_timestamp(expires_at, field="expires_at") <= checked_at
    )
    current_contract = daily_operations_publication.validate_final_publication_contract(
        base,
        namespace,
        require_current=True,
        require_operations=True,
    )
    current_authority = current_contract.valid
    warning_parts = []
    if not current_authority:
        warning_parts.append(
            "historical published generation; not the current dashboard authority"
        )
    if expired:
        warning_parts.append(f"idea expired at {expires_at}")
    if not warning_parts:
        warning_parts.append("current unexpired research idea")

    return {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "row_type": "decision_radar_idea_review_card_inspection",
        "status": "verified",
        "evaluated_at": checked_at.isoformat(),
        "artifact_namespace": namespace,
        "run_id": binding["run_id"],
        "profile": binding["profile"],
        "revision": binding["revision"],
        "operator_state_sha256": binding["operator_state_sha256"],
        "idea_id": requested_idea,
        "core_opportunity_id": binding["core_opportunity_id"],
        "radar_route": binding["radar_route"],
        "operator_review_context": binding["operator_review_context"],
        "expires_at": expires_at,
        "idea_temporal_status": "expired" if expired else "unexpired",
        "current_dashboard_authority": current_authority,
        "generation_role": (
            "current_dashboard_authority"
            if current_authority
            else "historical_published_generation"
        ),
        "operator_warning": "; ".join(warning_parts),
        "card_display_path": str(stored_card_path),
        "card_namespace_relative_path": (
            PurePosixPath("research_cards") / member
        ).as_posix(),
        "card_sha256": hashlib.sha256(card_bytes).hexdigest(),
        "card_size_bytes": len(card_bytes),
        "research_cards_tree_sha256": card_tree.get("sha256"),
        "card_markdown": markdown,
        "inspection_records_human_timing_event": False,
        "confirmed_view_still_required_for_timing_evidence": True,
        "provider_calls": 0,
        "writes": 0,
        "research_only": True,
        "safety": dict(timing._SAFETY),
    }


def _require_snapshot_matches_binding(
    snapshot: object,
    binding: Mapping[str, Any],
) -> None:
    identity = {
        "artifact_namespace": getattr(snapshot, "artifact_namespace", None),
        "run_id": getattr(snapshot, "run_id", None),
        "profile": getattr(snapshot, "profile", None),
        "revision": getattr(snapshot, "revision", None),
        "operator_state_sha256": getattr(snapshot, "operator_state_sha256", None),
    }
    if any(identity[field] != binding[field] for field in identity):
        raise timing.DecisionReviewTimingError("review_card_snapshot_binding_drift")
    artifacts = timing._mapping(getattr(snapshot, "operator_state", {}).get("artifacts"))
    if (
        timing._artifact_sha(artifacts, "integrated_candidates")
        != binding["integrated_candidates_sha256"]
        or timing._artifact_sha(artifacts, "core_opportunities")
        != binding["core_opportunities_sha256"]
    ):
        raise timing.DecisionReviewTimingError("review_card_artifact_binding_drift")


def _card_member(value: object, *, namespace: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or value != value.strip():
        raise timing.DecisionReviewTimingError("review_card_path_invalid")
    if "\\" in value or "\x00" in value:
        raise timing.DecisionReviewTimingError("review_card_path_invalid")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise timing.DecisionReviewTimingError("review_card_path_invalid")
    parts = path.parts
    suffix_valid = (
        len(parts) == 2
        and parts[0] == "research_cards"
        or len(parts) >= 3
        and parts[-3] == namespace
        and parts[-2] == "research_cards"
    )
    leaf = parts[-1]
    if (
        not suffix_valid
        or leaf == "index.md"
        or not leaf.startswith("card_")
        or not leaf.endswith(".md")
        or PurePosixPath(leaf).name != leaf
    ):
        raise timing.DecisionReviewTimingError("review_card_path_invalid")
    return PurePosixPath(leaf)


def _require_card_lineage(
    markdown: str,
    binding: Mapping[str, Any],
) -> None:
    required = (
        f"- Run ID: {binding['run_id']}",
        f"- Profile: {binding['profile']}",
        f"- Namespace: {binding['artifact_namespace']}",
        f"- Core opportunity ID: {binding['core_opportunity_id']}",
    )
    if not all(line in markdown.splitlines() for line in required):
        raise timing.DecisionReviewTimingError("review_card_lineage_mismatch")


__all__ = (
    "MAX_CARD_BYTES",
    "SCHEMA_ID",
    "inspect_review_card",
)
