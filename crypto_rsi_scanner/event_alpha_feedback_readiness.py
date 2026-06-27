"""Feedback-loop readiness checks for Event Alpha research artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import event_alpha_notification_inbox, event_watchlist


@dataclass(frozen=True)
class EventAlphaFeedbackReadinessResult:
    profile: str
    artifact_namespace: str
    cards_checked: int
    cards_with_lineage: int
    alert_rows_checked: int
    alert_rows_with_feedback_targets: int
    inbox_review_items: int
    feedback_rows: int
    calibration_ready_rows: int
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return not self.blockers


def build_feedback_readiness(
    *,
    profile: str,
    artifact_namespace: str,
    card_paths: Iterable[str | Path],
    alert_rows: Iterable[Mapping[str, Any]],
    feedback_rows: Iterable[Mapping[str, Any]],
    watchlist_entries: Iterable[event_watchlist.EventWatchlistEntry],
    inbox_result: event_alpha_notification_inbox.EventAlphaNotificationInboxResult | None = None,
) -> EventAlphaFeedbackReadinessResult:
    """Check whether local artifacts are ready for manual useful/junk feedback."""
    cards = [Path(path) for path in card_paths]
    alerts = [dict(row) for row in alert_rows if isinstance(row, Mapping)]
    feedback = [dict(row) for row in feedback_rows if isinstance(row, Mapping)]
    entries = list(watchlist_entries)
    cards_with_lineage = sum(1 for path in cards if _card_has_current_lineage(path))
    alert_targets = sum(1 for row in alerts if _alert_has_feedback_target(row))
    calibration_ready = sum(1 for row in [*alerts, *(_entry_row(entry) for entry in entries)] if _row_has_calibration_fields(row))
    inbox_items = _inbox_review_count(inbox_result)
    blockers: list[str] = []
    warnings: list[str] = []
    if cards and cards_with_lineage < len(cards):
        blockers.append("research_cards_missing_lineage")
    if alerts and alert_targets < len(alerts):
        blockers.append("alert_snapshots_missing_feedback_targets")
    if inbox_result is not None and inbox_items <= 0 and (alerts or cards):
        warnings.append("inbox_has_no_review_items")
    if alerts and calibration_ready <= 0:
        blockers.append("calibration_fields_missing")
    if not cards:
        warnings.append("no_research_cards_found")
    if not alerts:
        warnings.append("no_alert_snapshots_found")
    return EventAlphaFeedbackReadinessResult(
        profile=str(profile or "default"),
        artifact_namespace=str(artifact_namespace or "default"),
        cards_checked=len(cards),
        cards_with_lineage=cards_with_lineage,
        alert_rows_checked=len(alerts),
        alert_rows_with_feedback_targets=alert_targets,
        inbox_review_items=inbox_items,
        feedback_rows=len(feedback),
        calibration_ready_rows=calibration_ready,
        blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def format_feedback_readiness(result: EventAlphaFeedbackReadinessResult) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA FEEDBACK READINESS (research-only)",
        "=" * 76,
        f"profile: {result.profile}",
        f"artifact_namespace: {result.artifact_namespace}",
        f"ready: {str(result.ready).lower()}",
        f"cards_with_lineage: {result.cards_with_lineage}/{result.cards_checked}",
        f"alert_feedback_targets: {result.alert_rows_with_feedback_targets}/{result.alert_rows_checked}",
        f"inbox_review_items: {result.inbox_review_items}",
        f"feedback_rows: {result.feedback_rows}",
        f"calibration_ready_rows: {result.calibration_ready_rows}",
        "blockers: " + (", ".join(result.blockers) if result.blockers else "none"),
        "warnings: " + (", ".join(result.warnings) if result.warnings else "none"),
        "",
        "Checks: card lineage, alert/card feedback targets, inbox review queues, outcome target IDs, and calibration fields.",
        "Artifact-only check; no sends, trades, paper rows, normal RSI rows, or event-fade state were changed.",
    ]
    return "\n".join(lines)


def _card_has_current_lineage(path: Path) -> bool:
    if not path.exists() or path.name == "index.md":
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    required = ("- Run ID: ", "- Profile: ", "- Namespace: ", "- Generated at: ")
    if not all(token in text for token in required):
        return False
    return "legacy_lineage_missing" not in text


def _alert_has_feedback_target(row: Mapping[str, Any]) -> bool:
    return any(str(row.get(key) or "").strip() for key in ("alert_id", "card_id", "alert_key", "snapshot_id"))


def _row_has_calibration_fields(row: Mapping[str, Any]) -> bool:
    components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else row.get("score_components")
    if not isinstance(components, Mapping):
        components = {}
    return all(
        (row.get(key) not in (None, "", [], {}, ()) or components.get(key) not in (None, "", [], {}, ()))
        for key in ("impact_path_type", "candidate_role", "opportunity_level")
    )


def _entry_row(entry: event_watchlist.EventWatchlistEntry) -> dict[str, Any]:
    return {
        "key": entry.key,
        "impact_path_type": entry.impact_path_type,
        "candidate_role": entry.candidate_role,
        "opportunity_level": entry.opportunity_level,
        "latest_score_components": dict(entry.latest_score_components or {}),
    }


def _inbox_review_count(result: event_alpha_notification_inbox.EventAlphaNotificationInboxResult | None) -> int:
    if result is None:
        return 0
    return sum(len(getattr(result, field)) for field in (
        "sent_without_feedback",
        "partial_delivered_without_feedback",
        "would_send_without_feedback",
        "would_send_blocked_without_feedback",
        "quality_gated_local_only",
        "legacy_quality_conflicts",
        "exploratory_without_feedback",
        "high_priority_unreviewed",
        "triggered_fade_unreviewed",
    ))
