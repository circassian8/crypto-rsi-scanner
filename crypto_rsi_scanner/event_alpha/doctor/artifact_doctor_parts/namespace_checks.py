"""Namespace Checks for the legacy artifact doctor."""

from __future__ import annotations

from .runtime import *

def _watchlist_quality_state_conflicts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    out = {
        "watchlist_state_conflicts_with_quality": 0,
        "universal_watchlist_state_conflicts": 0,
        "non_hypothesis_watchlist_quality_conflicts": 0,
        "hypothesis_watchlist_quality_conflicts": 0,
        "quality_capped_watchlist_rows": 0,
        "active_watchlist_rows_quality_capped": 0,
        "fresh_uncapped": 0,
        "legacy": 0,
    }
    for row in rows:
        state = event_watchlist.final_state_value(row)
        requested = event_watchlist.requested_state_value(row)
        requested_active = requested in {
            event_watchlist.EventWatchlistState.WATCHLIST.value,
            event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
            event_watchlist.EventWatchlistState.EVENT_PASSED.value,
            event_watchlist.EventWatchlistState.ARMED.value,
        }
        final_active = state in {
            event_watchlist.EventWatchlistState.WATCHLIST.value,
            event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
            event_watchlist.EventWatchlistState.EVENT_PASSED.value,
            event_watchlist.EventWatchlistState.ARMED.value,
        }
        persisted_capped = row.get("state_quality_capped") is True
        capped = persisted_capped and not final_active
        has_conflict = _row_has_watchlist_quality_conflict(row)
        if capped and requested_active:
            out["quality_capped_watchlist_rows"] += 1
            out["active_watchlist_rows_quality_capped"] += 1
            continue
        if has_conflict:
            out["watchlist_state_conflicts_with_quality"] += 1
            out["universal_watchlist_state_conflicts"] += 1
            if _is_hypothesis_watchlist_row(row):
                out["hypothesis_watchlist_quality_conflicts"] += 1
            else:
                out["non_hypothesis_watchlist_quality_conflicts"] += 1
            if event_alpha_artifacts.is_api_row(row):
                out["legacy"] += 1
            elif not capped or final_active:
                out["fresh_uncapped"] += 1
    return out

def _filter_watchlist_rows_for_doctor(
    rows: Iterable[Mapping[str, Any]],
    *,
    profile: str | None,
    artifact_namespace: str | None,
    include_test_artifacts: bool,
    include_api_artifacts: bool,
) -> list[dict[str, Any]]:
    """Filter watchlist rows while honoring path-scoped legacy metadata gaps.

    Older watchlist entries did not carry profile/run-mode fields even when
    they lived inside a profile namespace directory. Doctor callers pass rows
    from a resolved path, so missing metadata should not make those rows
    invisible to quality checks.
    """
    out: list[dict[str, Any]] = []
    profile_key = _clean_optional(profile)
    namespace_key = _clean_optional(artifact_namespace)
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        data = dict(row)
        if not include_test_artifacts and event_alpha_artifacts.is_non_operational_row(data):
            continue
        row_profile = _clean_optional(data.get("profile"))
        if profile_key is not None and row_profile not in (None, profile_key):
            continue
        row_ns = _clean_optional(data.get("artifact_namespace") or data.get("namespace"))
        if namespace_key is not None and row_ns not in (None, namespace_key):
            continue
        if not include_api_artifacts and event_alpha_artifacts.is_api_row(data):
            if _row_has_watchlist_quality_conflict(data) or event_watchlist.state_is_quality_capped(data):
                if profile and not data.get("profile"):
                    data["profile"] = profile
                if artifact_namespace and not (data.get("artifact_namespace") or data.get("namespace")):
                    data["artifact_namespace"] = artifact_namespace
                if not data.get("run_mode"):
                    data["run_mode"] = "notification_burn_in" if str(profile or "").startswith("notify_") else "burn_in"
                data["_path_scoped_metadata_inferred"] = True
            else:
                continue
        out.append(data)
    return out

def _clean_optional(value: Any) -> str | None:
    text = str(value or "").strip().casefold()
    return text or None

def _row_has_watchlist_quality_conflict(row: Mapping[str, Any]) -> bool:
    if event_watchlist.final_state_value(row) == event_watchlist.EventWatchlistState.TRIGGERED_FADE.value:
        return False
    requested = event_watchlist.requested_state_value(row)
    if requested not in {
        event_watchlist.EventWatchlistState.WATCHLIST.value,
        event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        event_watchlist.EventWatchlistState.EVENT_PASSED.value,
        event_watchlist.EventWatchlistState.ARMED.value,
    }:
        return False
    components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else {}
    data = event_alpha_quality_fields.ensure_quality_fields(row, components=components)
    level = str(data.get("opportunity_level") or "")
    if level in {"local_only", "exploratory", ""}:
        return True
    if str(data.get("impact_path_type") or "") == "insufficient_data":
        return True
    if str(data.get("candidate_role") or "") == "unknown_with_reason":
        return True
    if str(data.get("source_class") or "") == "insufficient_data":
        return True
    if str(data.get("evidence_specificity") or "") == "insufficient_data":
        return True
    try:
        score = float(data.get("opportunity_score_final") or 0.0)
    except (TypeError, ValueError):
        score = 0.0
    return score <= 0.0

def _is_hypothesis_watchlist_row(row: Mapping[str, Any]) -> bool:
    components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else {}
    return bool(row.get("hypothesis_id") or components.get("hypothesis_id") or str(row.get("relationship_type") or "") == "impact_hypothesis")

def _incident_linkage_summary(
    *,
    hypotheses: Iterable[Mapping[str, Any]],
    watchlist: Iterable[Mapping[str, Any]],
    alerts: Iterable[Mapping[str, Any]],
    incidents: Iterable[Mapping[str, Any]],
) -> dict[str, int]:
    out = {
        "hypothesis_rows_missing_incident_id": 0,
        "watchlist_hypothesis_rows_missing_incident_id": 0,
        "alert_hypothesis_rows_missing_incident_id": 0,
        "incident_rows_without_linked_hypotheses": 0,
        "incident_rows_without_linked_watchlist": 0,
        "canonical_unlinked_incidents": 0,
        "active_incident_without_qualified_link": 0,
        "linked_incident_without_qualified_link": 0,
        "weak_unqualified_incident_links": 0,
        "quality_blocked_links_present": 0,
        "quality_blocked_links_promoting_incident": 0,
        "fresh_missing_hypotheses": 0,
        "fresh_missing_watchlist": 0,
        "fresh_missing_alerts": 0,
        "legacy_missing_hypotheses": 0,
        "legacy_missing_watchlist": 0,
        "legacy_missing_alerts": 0,
        "diagnostic_incident_rows": 0,
        "raw_observation_incident_rows": 0,
        "external_context_incident_rows": 0,
        "rejected_incident_rows": 0,
        "incident_relevance_missing": 0,
        "invalid_canonical_incident_rows": 0,
        "garbage_primary_subject_incidents": 0,
    }
    for row in hypotheses:
        if dict(row).get("row_type") not in {"event_impact_hypothesis", ""}:
            continue
        if _row_has_no_incident(row):
            continue
        if not _row_incident_id(row):
            out["hypothesis_rows_missing_incident_id"] += 1
            if event_alpha_artifacts.is_api_row(row):
                out["legacy_missing_hypotheses"] += 1
            else:
                out["fresh_missing_hypotheses"] += 1
    for row in watchlist:
        if str(row.get("relationship_type") or "") != "impact_hypothesis":
            continue
        if _row_has_no_incident(row):
            continue
        if not _row_incident_id(row):
            out["watchlist_hypothesis_rows_missing_incident_id"] += 1
            if event_alpha_artifacts.is_api_row(row):
                out["legacy_missing_watchlist"] += 1
            else:
                out["fresh_missing_watchlist"] += 1
    for row in alerts:
        is_hypothesis = bool(row.get("hypothesis_id")) or str(row.get("relationship_type") or "") == "impact_hypothesis"
        if not is_hypothesis or _row_has_no_incident(row):
            continue
        if not _row_incident_id(row):
            out["alert_hypothesis_rows_missing_incident_id"] += 1
            if event_alpha_artifacts.is_api_row(row):
                out["legacy_missing_alerts"] += 1
            else:
                out["fresh_missing_alerts"] += 1
    for row in incidents:
        if dict(row).get("row_type") != "event_incident":
            continue
        subject_quality = str(row.get("incident_subject_quality") or "").strip()
        diagnostic = row.get("diagnostic_only") is True
        relevance = str(row.get("incident_relevance_status") or "").strip()
        if not relevance:
            out["incident_relevance_missing"] += 1
        if _is_garbage_incident_subject(row.get("primary_subject")):
            out["garbage_primary_subject_incidents"] += 1
        if relevance == "raw_observation":
            out["raw_observation_incident_rows"] += 1
        if relevance == "external_context_only":
            out["external_context_incident_rows"] += 1
        if relevance == "rejected_incident":
            out["rejected_incident_rows"] += 1
        relevance_is_hidden = (
            relevance in {"raw_observation", "external_context_only", "rejected_incident"}
            or (relevance == "diagnostic_only" and subject_quality != "invalid")
        )
        if diagnostic or (relevance_is_hidden and relevance in {"diagnostic_only", "rejected_incident"}):
            out["diagnostic_incident_rows"] += 1
            continue
        if relevance_is_hidden:
            continue
        elif subject_quality in {"invalid", "diagnostic_only"}:
            out["invalid_canonical_incident_rows"] += 1
        operational = relevance in {"canonical_incident", "linked_incident", "active_incident"} or (not relevance and not diagnostic)
        qualified_links = int(row.get("qualified_link_count") or 0)
        weak_links = int(row.get("weak_link_count") or 0)
        quality_blocked_links = int(row.get("quality_blocked_link_count") or 0)
        if relevance == "active_incident" and qualified_links <= 0:
            out["active_incident_without_qualified_link"] += 1
        if relevance == "linked_incident" and qualified_links <= 0:
            out["linked_incident_without_qualified_link"] += 1
        if weak_links > 0:
            out["weak_unqualified_incident_links"] += weak_links
        if quality_blocked_links > 0:
            out["quality_blocked_links_present"] += quality_blocked_links
        if relevance in {"linked_incident", "active_incident"} and quality_blocked_links > 0 and qualified_links <= 0:
            out["quality_blocked_links_promoting_incident"] += quality_blocked_links
        if operational and not row.get("linked_hypothesis_ids"):
            out["incident_rows_without_linked_hypotheses"] += 1
        if operational and not row.get("linked_watchlist_keys"):
            out["incident_rows_without_linked_watchlist"] += 1
        if operational and not row.get("linked_hypothesis_ids") and not row.get("linked_watchlist_keys"):
            out["canonical_unlinked_incidents"] += 1
    return out

def _is_garbage_incident_subject(value: Any) -> bool:
    text = str(value or "").strip().casefold()
    text = " ".join(text.replace("-", " ").replace("_", " ").split())
    if not text:
        return False
    if text in _GARBAGE_INCIDENT_SUBJECTS:
        return True
    if "invite code" in text or "referral code" in text:
        return True
    if text.startswith("best ") and text.endswith(" apps"):
        return True
    if text.endswith(" are") and " and " in text:
        return True
    return False

def _row_incident_id(row: Mapping[str, Any]) -> str:
    components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else {}
    score = row.get("score_components") if isinstance(row.get("score_components"), Mapping) else {}
    return str(row.get("incident_id") or components.get("incident_id") or score.get("incident_id") or "").strip()

def _row_has_no_incident(row: Mapping[str, Any]) -> bool:
    components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else {}
    score = row.get("score_components") if isinstance(row.get("score_components"), Mapping) else {}
    status = str(
        row.get("incident_link_status")
        or components.get("incident_link_status")
        or score.get("incident_link_status")
        or ""
    ).strip()
    reason = str(
        row.get("incident_link_reason")
        or components.get("incident_link_reason")
        or score.get("incident_link_reason")
        or ""
    ).strip()
    if status == "no_incident" and reason:
        return True
    warnings = " ".join(str(value) for value in row.get("warnings") or ())
    return "no_incident" in warnings

def _record_snapshot_availability_issue(
    row: Mapping[str, Any],
    availability: str,
    *,
    blockers: list[str],
    warnings: list[str],
    strict: bool,
) -> None:
    run_id = str(row.get("run_id") or "unknown")
    path = event_alpha_artifacts.safe_path_label(row.get("alert_store_path"))
    run_mode = str(row.get("run_mode") or "legacy")
    if availability == event_alpha_artifacts.SNAPSHOT_EXTERNAL_PATH:
        blockers.append(
            f"alertable_run_missing_matching_snapshot_rows: {run_id}; "
            f"snapshot_written_to_external_path={path}"
        )
    elif availability == event_alpha_artifacts.SNAPSHOT_TEST_OR_FIXTURE_EXTERNAL:
        warnings.append(
            f"fixture_snapshot_external_allowed: {run_id}; "
            f"snapshot_written_to_external_path={path}"
        )
    elif availability == event_alpha_artifacts.SNAPSHOT_UNKNOWN_LEGACY:
        message = (
            f"legacy_run_missing_snapshot_rows: {run_id}; "
            f"snapshot availability unknown for legacy/default row"
        )
        (blockers if strict else warnings).append(message)
    else:
        target = blockers if run_mode in {"burn_in", "operational"} else warnings
        target.append(f"alertable_run_missing_matching_snapshot_rows: {run_id}")

__all__ = (
    '_watchlist_quality_state_conflicts',
    '_filter_watchlist_rows_for_doctor',
    '_clean_optional',
    '_row_has_watchlist_quality_conflict',
    '_is_hypothesis_watchlist_row',
    '_incident_linkage_summary',
    '_is_garbage_incident_subject',
    '_row_incident_id',
    '_row_has_no_incident',
    '_record_snapshot_availability_issue',
)
