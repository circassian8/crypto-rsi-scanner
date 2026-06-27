"""Feedback-loop readiness checks for Event Alpha research artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import event_alpha_notification_inbox, event_core_opportunities, event_research_cards, event_watchlist


@dataclass(frozen=True)
class EventAlphaFeedbackReadinessResult:
    profile: str
    artifact_namespace: str
    cards_checked: int
    cards_with_lineage: int
    cards_with_feedback_target: int
    core_opportunity_cards_ready: int
    near_miss_cards_ready: int
    local_only_cards_ready: int
    alert_rows_checked: int
    alert_rows_with_feedback_targets: int
    inbox_review_items: int
    feedback_rows: int
    calibration_ready_rows: int
    visible_core_opportunities: int = 0
    visible_core_opportunities_with_cards: int = 0
    visible_core_opportunities_with_feedback_targets: int = 0
    visible_core_opportunities_missing_cards: int = 0
    visible_core_opportunities_missing_feedback_targets: int = 0
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

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
    research_cards = [path for path in cards if path.name != "index.md"]
    card_core_ids = {value for path in research_cards for value in (event_research_cards.card_core_opportunity_id(path),) if value}
    card_feedback_targets = {value for path in research_cards for value in (event_research_cards.card_feedback_target(path),) if value}
    cards_with_lineage = sum(1 for path in research_cards if event_research_cards.card_has_current_lineage(path))
    cards_with_target = sum(1 for path in research_cards if event_research_cards.card_feedback_target(path))
    ready_by_group = _ready_card_groups(research_cards)
    alert_targets = sum(1 for row in alerts if _alert_has_feedback_target(row))
    calibration_ready = sum(1 for row in [*alerts, *(_entry_row(entry) for entry in entries)] if _row_has_calibration_fields(row))
    inbox_items = _inbox_review_count(inbox_result)
    visible_core = event_core_opportunities.visible_core_opportunities([*entries, *alerts])
    alert_core_targets = {
        str(row.get("core_opportunity_id") or "")
        for row in alerts
        if str(row.get("core_opportunity_id") or "")
    }
    alert_feedback_targets = {
        str(row.get("feedback_target") or "")
        for row in alerts
        if str(row.get("feedback_target") or "")
    }
    visible_with_cards = sum(1 for item in visible_core if item.core_opportunity_id in card_core_ids)
    visible_with_targets = sum(
        1
        for item in visible_core
        if item.core_opportunity_id in card_feedback_targets
        or item.core_opportunity_id in alert_core_targets
        or item.core_opportunity_id in alert_feedback_targets
    )
    missing_cards = max(0, len(visible_core) - visible_with_cards)
    missing_targets = max(0, len(visible_core) - visible_with_targets)
    blockers: list[str] = []
    warnings: list[str] = []
    if research_cards and cards_with_lineage < len(research_cards):
        blockers.append("research_cards_missing_lineage")
    if research_cards and cards_with_target < len(research_cards):
        blockers.append("research_cards_missing_feedback_target")
    if alerts and alert_targets < len(alerts):
        blockers.append("alert_snapshots_missing_feedback_targets")
    if missing_cards:
        blockers.append("visible_core_opportunities_missing_cards")
    if missing_targets:
        blockers.append("visible_core_opportunities_missing_feedback_targets")
    if inbox_result is not None and inbox_items <= 0 and (alerts or cards):
        warnings.append("inbox_has_no_review_items")
    if alerts and calibration_ready <= 0:
        blockers.append("calibration_fields_missing")
    if not research_cards:
        warnings.append("no_research_cards_found")
    if not alerts:
        warnings.append("no_alert_snapshots_found")
    return EventAlphaFeedbackReadinessResult(
        profile=str(profile or "default"),
        artifact_namespace=str(artifact_namespace or "default"),
        cards_checked=len(research_cards),
        cards_with_lineage=cards_with_lineage,
        cards_with_feedback_target=cards_with_target,
        core_opportunity_cards_ready=ready_by_group.get("Core Opportunity Cards", 0),
        near_miss_cards_ready=ready_by_group.get("Near-Miss Cards", 0),
        local_only_cards_ready=ready_by_group.get("Local-Only / Quality-Capped Cards", 0),
        alert_rows_checked=len(alerts),
        alert_rows_with_feedback_targets=alert_targets,
        inbox_review_items=inbox_items,
        feedback_rows=len(feedback),
        calibration_ready_rows=calibration_ready,
        visible_core_opportunities=len(visible_core),
        visible_core_opportunities_with_cards=visible_with_cards,
        visible_core_opportunities_with_feedback_targets=visible_with_targets,
        visible_core_opportunities_missing_cards=missing_cards,
        visible_core_opportunities_missing_feedback_targets=missing_targets,
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
        f"cards_with_feedback_target: {result.cards_with_feedback_target}/{result.cards_checked}",
        (
            "card_groups_ready: "
            f"core={result.core_opportunity_cards_ready}, "
            f"near_miss={result.near_miss_cards_ready}, "
            f"local_only={result.local_only_cards_ready}"
        ),
        f"alert_feedback_targets: {result.alert_rows_with_feedback_targets}/{result.alert_rows_checked}",
        (
            "visible_core_opportunities: "
            f"{result.visible_core_opportunities} "
            f"cards={result.visible_core_opportunities_with_cards}/{result.visible_core_opportunities} "
            f"feedback_targets={result.visible_core_opportunities_with_feedback_targets}/{result.visible_core_opportunities}"
        ),
        (
            "visible_core_missing: "
            f"cards={result.visible_core_opportunities_missing_cards}, "
            f"feedback_targets={result.visible_core_opportunities_missing_feedback_targets}"
        ),
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

def _ready_card_groups(paths: Iterable[Path]) -> dict[str, int]:
    counts: dict[str, int] = {
        "Core Opportunity Cards": 0,
        "Near-Miss Cards": 0,
        "Local-Only / Quality-Capped Cards": 0,
    }
    for path in paths:
        if not event_research_cards.card_has_current_lineage(path):
            continue
        if not event_research_cards.card_feedback_target(path):
            continue
        group = event_research_cards.card_index_group(path)
        if group in counts:
            counts[group] += 1
    return counts


def _alert_has_feedback_target(row: Mapping[str, Any]) -> bool:
    return any(str(row.get(key) or "").strip() for key in (
        "feedback_target",
        "core_opportunity_id",
        "alert_id",
        "card_id",
        "alert_key",
        "snapshot_id",
    ))


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
