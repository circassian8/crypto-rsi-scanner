"""Split implementation for `crypto_rsi_scanner/event_alpha/notifications/inbox.py` (builder)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Mapping
import crypto_rsi_scanner.event_alpha.artifacts.alert_store as event_alpha_alert_store
import crypto_rsi_scanner.event_alpha.outcomes.quality_fields as event_alpha_quality_fields
import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
import crypto_rsi_scanner.event_alpha.radar.core_opportunities as event_core_opportunities
import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
from ...artifacts import research_cards as event_research_cards
from ...radar import core_opportunity_store as event_core_opportunity_store
from ...radar.decision_model_surfaces import decision_model_values
from ...outcomes import feedback_eligibility
from .. import delivery
from .. import pipeline as event_alpha_notifications
from .models import *  # noqa: F403

REVIEW_QUEUE_STRICT_ALERTABLE = "strict_alertable"
REVIEW_QUEUE_HIGH_PRIORITY_WOULD_SEND = "high_priority_would_send"
REVIEW_QUEUE_DIGEST_WOULD_SEND = "digest_would_send"
REVIEW_QUEUE_RESEARCH_REVIEW_NEAR_MISS = "research_review_near_miss"
REVIEW_QUEUE_UPGRADE_CANDIDATE = "upgrade_candidate"
REVIEW_QUEUE_LOCAL_ONLY_LEARNING_ROW = "local_only_learning_row"
REVIEW_QUEUE_DIAGNOSTIC_ONLY = "diagnostic_only"
_REVIEW_QUEUE_WEIGHTS = {
    REVIEW_QUEUE_STRICT_ALERTABLE: 700.0,
    REVIEW_QUEUE_HIGH_PRIORITY_WOULD_SEND: 650.0,
    REVIEW_QUEUE_DIGEST_WOULD_SEND: 600.0,
    REVIEW_QUEUE_RESEARCH_REVIEW_NEAR_MISS: 500.0,
    REVIEW_QUEUE_UPGRADE_CANDIDATE: 420.0,
    REVIEW_QUEUE_LOCAL_ONLY_LEARNING_ROW: 250.0,
    REVIEW_QUEUE_DIAGNOSTIC_ONLY: 50.0,
}


@dataclass(frozen=True)
class _InboxSourceRows:
    runs: list[dict[str, Any]]
    alerts: list[dict[str, Any]]
    feedback: list[dict[str, Any]]
    deliveries: list[dict[str, Any]]
    core_rows: list[dict[str, Any]]
    cards_dir: Path
    card_paths: dict[str, Path]
    card_paths_by_core: dict[str, Path]
    reviewed_ids: set[str]
    watch_by_alert: dict[str, event_watchlist.EventWatchlistEntry]
    delivery_state_by_run: dict[str, str]
    feedback_rows_supplied: int
    feedback_rows_eligible: int
    feedback_rows_excluded: int
    feedback_exclusion_reason_counts: dict[str, int]


@dataclass(frozen=True)
class _InboxReviewQueues:
    sent_without_feedback: tuple[EventAlphaNotificationInboxItem, ...]
    partial_delivered_without_feedback: tuple[EventAlphaNotificationInboxItem, ...]
    would_send_without_feedback: tuple[EventAlphaNotificationInboxItem, ...]
    would_send_blocked_without_feedback: tuple[EventAlphaNotificationInboxItem, ...]
    weak_validated_local_only: tuple[EventAlphaNotificationInboxItem, ...]
    quality_gated_local_only: tuple[EventAlphaNotificationInboxItem, ...]
    legacy_quality_conflicts: tuple[EventAlphaNotificationInboxItem, ...]
    research_review_without_feedback: tuple[EventAlphaNotificationInboxItem, ...]
    exploratory_without_feedback: tuple[EventAlphaNotificationInboxItem, ...]
    high_priority_unreviewed: tuple[EventAlphaNotificationInboxItem, ...]
    triggered_fade_unreviewed: tuple[EventAlphaNotificationInboxItem, ...]


def build_notification_inbox(
    *,
    notification_runs: Iterable[Mapping[str, Any]],
    alert_rows: Iterable[Mapping[str, Any]],
    feedback_rows: Iterable[Mapping[str, Any]],
    research_cards_dir: str | Path,
    profile: str,
    artifact_namespace: str,
    notification_runs_path: str | Path,
    alert_store_path: str | Path,
    feedback_path: str | Path,
    outcomes_path: str | Path | None = None,
    notification_delivery_rows: Iterable[Mapping[str, Any]] = (),
    watchlist_entries: Iterable[event_watchlist.EventWatchlistEntry] = (),
    core_opportunity_rows: Iterable[Mapping[str, Any]] = (),
    include_api_conflicts: bool = False,
    include_diagnostics: bool = False,
    now: Any = None,
) -> EventAlphaNotificationInboxResult:
    """Join notification, alert, card, and feedback artifacts into review queues."""
    source = _load_inbox_source_rows(
        notification_runs=notification_runs,
        alert_rows=alert_rows,
        feedback_rows=feedback_rows,
        research_cards_dir=research_cards_dir,
        notification_delivery_rows=notification_delivery_rows,
        watchlist_entries=watchlist_entries,
        core_opportunity_rows=core_opportunity_rows,
        now=now,
    )
    all_review_items = _build_event_alpha_review_items_from_rows(
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_diagnostics=True,
        notification_runs=source.runs,
        alert_rows=source.alerts,
        feedback_rows=source.feedback,
        research_cards_dir=source.cards_dir,
        notification_delivery_rows=source.deliveries,
        watchlist_entries=watchlist_entries,
        core_opportunity_rows=source.core_rows,
    )
    canonical_review_items = tuple(item for item in all_review_items if not item.is_diagnostic)
    diagnostic_review_items = tuple(item for item in all_review_items if item.is_diagnostic)
    items = [
        item for item in all_review_items
        if include_diagnostics or not item.is_diagnostic
    ]
    queues = _build_inbox_review_queues(
        items=items,
        canonical_review_items=canonical_review_items,
        source=source,
        include_api_conflicts=include_api_conflicts,
    )
    outcomes = _read_jsonl(Path(outcomes_path).expanduser()) if outcomes_path else []
    return EventAlphaNotificationInboxResult(
        profile=str(profile or "default"),
        artifact_namespace=str(artifact_namespace or "default"),
        notification_runs_path=Path(notification_runs_path).expanduser(),
        alert_store_path=Path(alert_store_path).expanduser(),
        feedback_path=Path(feedback_path).expanduser(),
        research_cards_dir=source.cards_dir,
        outcomes_path=Path(outcomes_path).expanduser() if outcomes_path else None,
        notification_runs_read=len(source.runs),
        alert_rows_read=len(source.alerts),
        feedback_rows_read=len(source.feedback),
        research_cards_read=len(source.card_paths),
        outcome_rows_read=len(outcomes),
        feedback_rows_supplied=source.feedback_rows_supplied,
        feedback_rows_eligible=source.feedback_rows_eligible,
        feedback_rows_excluded=source.feedback_rows_excluded,
        feedback_exclusion_reason_counts=source.feedback_exclusion_reason_counts,
        sent_without_feedback=queues.sent_without_feedback,
        partial_delivered_without_feedback=queues.partial_delivered_without_feedback,
        would_send_without_feedback=queues.would_send_without_feedback,
        would_send_blocked_without_feedback=queues.would_send_blocked_without_feedback,
        weak_validated_local_only=queues.weak_validated_local_only,
        quality_gated_local_only=queues.quality_gated_local_only,
        legacy_quality_conflicts=queues.legacy_quality_conflicts,
        research_review_without_feedback=queues.research_review_without_feedback,
        exploratory_without_feedback=queues.exploratory_without_feedback,
        high_priority_unreviewed=queues.high_priority_unreviewed,
        triggered_fade_unreviewed=queues.triggered_fade_unreviewed,
        heartbeat_only_runs=tuple(row for row in source.runs if _heartbeat_only(row)),
        duplicate_or_in_flight_runs=tuple(row for row in source.runs if _delivery_suppressed_run(row, source.delivery_state_by_run)),
        provider_degraded_runs=tuple(row for row in source.runs if _provider_degraded(row)),
        canonical_review_items=canonical_review_items,
        diagnostic_review_items_hidden=diagnostic_review_items if not include_diagnostics else (),
        diagnostic_review_items=diagnostic_review_items if include_diagnostics else (),
        canonical_review_items_with_cards=sum(1 for item in canonical_review_items if item.card_path),
        canonical_review_items_with_feedback_targets=sum(1 for item in canonical_review_items if item.feedback_target),
        diagnostic_review_items_with_feedback_targets=sum(1 for item in diagnostic_review_items if item.feedback_target),
        include_diagnostics=include_diagnostics,
    )


def _load_inbox_source_rows(
    *,
    notification_runs: Iterable[Mapping[str, Any]],
    alert_rows: Iterable[Mapping[str, Any]],
    feedback_rows: Iterable[Mapping[str, Any]],
    research_cards_dir: str | Path,
    notification_delivery_rows: Iterable[Mapping[str, Any]],
    watchlist_entries: Iterable[event_watchlist.EventWatchlistEntry],
    core_opportunity_rows: Iterable[Mapping[str, Any]],
    now: Any,
) -> _InboxSourceRows:
    runs = [dict(row) for row in notification_runs if isinstance(row, Mapping)]
    alerts = [dict(row) for row in alert_rows if isinstance(row, Mapping)]
    supplied_feedback = [dict(row) for row in feedback_rows if isinstance(row, Mapping)]
    deliveries = [dict(row) for row in notification_delivery_rows if isinstance(row, Mapping)]
    core_rows = [dict(row) for row in core_opportunity_rows if isinstance(row, Mapping)]
    feedback, excluded_feedback, feedback_reasons = (
        feedback_eligibility.partition_joined_calibration_feedback(
            supplied_feedback,
            core_rows,
            now=now,
        )
    )
    feedback = list(feedback)
    cards_dir = Path(research_cards_dir).expanduser()
    card_paths = _card_paths(cards_dir)
    return _InboxSourceRows(
        runs=runs,
        alerts=alerts,
        feedback=feedback,
        deliveries=deliveries,
        core_rows=core_rows,
        cards_dir=cards_dir,
        card_paths=card_paths,
        card_paths_by_core=_card_paths_by_core_id(cards_dir),
        reviewed_ids=_reviewed_ids(feedback),
        watch_by_alert={
            event_alpha_router.alert_id_for_entry(entry): entry
            for entry in watchlist_entries
        },
        delivery_state_by_run=_latest_delivery_state_by_run(deliveries),
        feedback_rows_supplied=len(supplied_feedback),
        feedback_rows_eligible=len(feedback),
        feedback_rows_excluded=len(excluded_feedback),
        feedback_exclusion_reason_counts=feedback_reasons,
    )


def _build_inbox_review_queues(
    *,
    items: Iterable[EventAlphaNotificationInboxItem],
    canonical_review_items: tuple[EventAlphaNotificationInboxItem, ...],
    source: _InboxSourceRows,
    include_api_conflicts: bool,
) -> _InboxReviewQueues:
    item_rows = tuple(items)
    countable = lambda item: _countable_alertable(item, include_api_conflicts=include_api_conflicts)
    quality_gated = tuple(
        item for item in item_rows
        if not item.is_diagnostic
        if item.snapshot_quality_classification == event_alpha_alert_store.SNAPSHOT_QUALITY_GATED_LOCAL
        and not item.reviewed
    )
    local_core_learning = tuple(
        item for item in item_rows
        if not item.is_diagnostic and item.item_type == "local_core_learning" and not item.reviewed
    )
    near_miss_core_items = tuple(
        item for item in item_rows
        if not item.is_diagnostic and item.item_type == "near_miss_core" and not item.reviewed
    )
    exploratory_delivery_items = tuple(
        item for item in _digest_delivery_items(
            source.deliveries,
            source.watch_by_alert,
            source.reviewed_ids,
            source.card_paths,
            lane=event_alpha_notifications.LANE_EXPLORATORY_DIGEST,
            default_tier="EXPLORATORY",
            default_playbook="exploratory",
            default_reason="exploratory digest item; low-confidence/store-only row needs review",
        )
        if not item.reviewed and not _delivery_item_duplicates_core(item, canonical_review_items)
    )
    research_review_delivery_items = tuple(
        item for item in _digest_delivery_items(
            source.deliveries,
            source.watch_by_alert,
            source.reviewed_ids,
            source.card_paths,
            lane=event_alpha_notifications.LANE_RESEARCH_REVIEW_DIGEST,
            default_tier="RESEARCH_REVIEW",
            default_playbook="research_review_digest",
            default_reason="research-review digest item; not alertable and missing confirmation",
        )
        if not item.reviewed
    )
    return _InboxReviewQueues(
        sent_without_feedback=tuple(
            item for item in item_rows
            if not item.is_diagnostic and item.sent and countable(item)
            and item.delivery_state != delivery.STATE_PARTIAL_DELIVERED and not item.reviewed
        ),
        partial_delivered_without_feedback=tuple(
            item for item in item_rows
            if not item.is_diagnostic and item.delivery_state == delivery.STATE_PARTIAL_DELIVERED
            and countable(item) and not item.reviewed
        ),
        would_send_without_feedback=tuple(
            item for item in item_rows
            if not item.is_diagnostic and item.would_send and countable(item)
            and not item.sent and not item.blocked_by_guard and not item.reviewed
        ),
        would_send_blocked_without_feedback=tuple(
            item for item in item_rows
            if not item.is_diagnostic and item.blocked_by_guard and countable(item) and not item.reviewed
        ),
        weak_validated_local_only=tuple(
            item for item in item_rows
            if not item.is_diagnostic
            if not item.quality_gate_block_reason and _is_weak_validated_local_only(item, source.alerts) and not item.reviewed
        ),
        quality_gated_local_only=tuple(dict.fromkeys((*quality_gated, *local_core_learning))),
        legacy_quality_conflicts=tuple(
            item for item in item_rows
            if not item.is_diagnostic
            if item.snapshot_quality_classification in _INBOX_LEGACY_CONFLICT_CLASSIFICATIONS
            and not item.reviewed
        ),
        research_review_without_feedback=research_review_delivery_items,
        exploratory_without_feedback=(*near_miss_core_items, *exploratory_delivery_items),
        high_priority_unreviewed=tuple(
            item for item in item_rows
            if not item.is_diagnostic and countable(item)
            and not item.reviewed and item.item_type == "core_opportunity"
            and not (item.sent or item.would_send or item.blocked_by_guard)
        ),
        triggered_fade_unreviewed=tuple(
            item for item in item_rows
            if not item.is_diagnostic and countable(item)
            and not item.reviewed and _is_triggered_fade(item)
            and not (item.sent or item.would_send or item.blocked_by_guard)
        ),
    )
def build_event_alpha_review_items(
    profile: str | None,
    namespace: str | None,
    include_diagnostics: bool = False,
    *,
    notification_runs: Iterable[Mapping[str, Any]] = (),
    alert_rows: Iterable[Mapping[str, Any]] = (),
    feedback_rows: Iterable[Mapping[str, Any]] = (),
    research_cards_dir: str | Path | None = None,
    notification_delivery_rows: Iterable[Mapping[str, Any]] = (),
    watchlist_entries: Iterable[event_watchlist.EventWatchlistEntry] = (),
    core_opportunity_rows: Iterable[Mapping[str, Any]] = (),
) -> tuple[EventAlphaNotificationInboxItem, ...]:
    """Return canonical-core-first review items for inbox/readiness/reporting.

    Core opportunities are the primary review objects. Alert snapshots linked to
    source-noise/support rows are diagnostics and are hidden unless requested.
    """
    return _build_event_alpha_review_items_from_rows(
        profile=profile,
        artifact_namespace=namespace,
        include_diagnostics=include_diagnostics,
        notification_runs=notification_runs,
        alert_rows=alert_rows,
        feedback_rows=feedback_rows,
        research_cards_dir=research_cards_dir,
        notification_delivery_rows=notification_delivery_rows,
        watchlist_entries=watchlist_entries,
        core_opportunity_rows=core_opportunity_rows,
    )
def _build_event_alpha_review_items_from_rows(
    *,
    profile: str | None,
    artifact_namespace: str | None,
    include_diagnostics: bool,
    notification_runs: Iterable[Mapping[str, Any]],
    alert_rows: Iterable[Mapping[str, Any]],
    feedback_rows: Iterable[Mapping[str, Any]],
    research_cards_dir: str | Path | None,
    notification_delivery_rows: Iterable[Mapping[str, Any]],
    watchlist_entries: Iterable[event_watchlist.EventWatchlistEntry],
    core_opportunity_rows: Iterable[Mapping[str, Any]],
) -> tuple[EventAlphaNotificationInboxItem, ...]:
    runs = [dict(row) for row in notification_runs if isinstance(row, Mapping)]
    alerts = [dict(row) for row in alert_rows if isinstance(row, Mapping)]
    feedback = [dict(row) for row in feedback_rows if isinstance(row, Mapping)]
    deliveries = [dict(row) for row in notification_delivery_rows if isinstance(row, Mapping)]
    core_rows = [dict(row) for row in core_opportunity_rows if isinstance(row, Mapping)]
    cards_dir = Path(research_cards_dir).expanduser() if research_cards_dir else Path()
    card_paths = _card_paths(cards_dir)
    card_paths_by_core = _card_paths_by_core_id(cards_dir)
    reviewed_ids = _reviewed_ids(feedback)
    runs_by_id = {str(row.get("run_id") or ""): row for row in runs if row.get("run_id")}
    delivery_state_by_run = _latest_delivery_state_by_run(deliveries)
    core_items = (
        event_core_opportunity_store.core_opportunities_from_rows(core_rows)
        if core_rows
        else ()
    )
    alerts_by_core = _alerts_by_core_id(alerts)
    consumed_alert_ids: set[int] = set()
    items: list[EventAlphaNotificationInboxItem] = []
    for core in core_items:
        if event_core_opportunities.core_opportunity_visibility_group(core, include_diagnostics=False) is None:
            continue
        snapshots = alerts_by_core.get(core.core_opportunity_id, [])
        snapshot = _best_snapshot_for_core(row for row in snapshots if not alert_snapshot_is_diagnostic(row))
        for row in snapshots:
            consumed_alert_ids.add(id(row))
        item = _inbox_item_from_core(
            core,
            snapshot=snapshot,
            runs_by_id=runs_by_id,
            card_paths_by_core=card_paths_by_core,
            reviewed_ids=reviewed_ids,
            delivery_state_by_run=delivery_state_by_run,
        )
        items.append(item)
    core_store_available = bool(core_rows)
    for alert in alerts:
        if id(alert) in consumed_alert_ids:
            if include_diagnostics and alert_snapshot_is_diagnostic(alert):
                items.append(_diagnostic_item_from_alert(alert, runs_by_id, card_paths, reviewed_ids, delivery_state_by_run))
            continue
        diagnostic = alert_snapshot_is_diagnostic(alert) or core_store_available
        item = _inbox_item(alert, runs_by_id.get(str(alert.get("run_id") or "")), card_paths, reviewed_ids, delivery_state_by_run)
        if diagnostic:
            item = _as_diagnostic_item(item, alert)
            if include_diagnostics:
                items.append(item)
        else:
            items.append(replace(
                item,
                item_type=_core_item_type_from_alert_stub(alert, item.alertable_after_quality_gate),
                feedback_target=str(alert.get("feedback_target") or item.alert_id),
                feedback_target_type=str(alert.get("feedback_target_type") or "alert_id"),
                core_opportunity_id=str(alert.get("core_opportunity_id") or ""),
            ))
    return tuple(_dedupe_review_items(items))
def _inbox_item_from_core(
    core: event_core_opportunities.CoreOpportunity,
    *,
    snapshot: Mapping[str, Any] | None,
    runs_by_id: Mapping[str, Mapping[str, Any]],
    card_paths_by_core: Mapping[str, Path],
    reviewed_ids: set[str],
    delivery_state_by_run: Mapping[str, str],
) -> EventAlphaNotificationInboxItem:
    row = dict(snapshot or core.primary_row)
    core_row = dict(core.primary_row)
    core_id = core.core_opportunity_id
    final_route = str(core.final_route_after_quality_gate or core_row.get("final_route_after_quality_gate") or core_row.get("route") or "")
    final_state = str(core.final_state_after_quality_gate or core_row.get("final_state_after_quality_gate") or core_row.get("state") or "")
    opportunity_level = str(core.opportunity_level or core_row.get("final_opportunity_level") or core_row.get("opportunity_level") or "")
    tier = str(row.get("final_tier_after_quality_gate") or row.get("tier") or _tier_for_core(core, final_route))
    run_id = str(row.get("run_id") or core_row.get("run_id") or "")
    lane = _lane_for_alert({"final_route_after_quality_gate": final_route, "tier": tier, "playbook_type": core.primary_impact_path})
    run = runs_by_id.get(run_id)
    delivery_state = str(row.get("delivered_status") or row.get("delivery_state") or delivery_state_by_run.get(run_id) or "")
    suppressed = delivery_state in (delivery.STATE_SKIPPED_DUPLICATE, delivery.STATE_SKIPPED_IN_FLIGHT)
    blocked_by_guard = delivery_state == delivery.STATE_BLOCKED or _guard_blocked(run)
    sent = (
        _lane_count(run, "lane_counts_sent", lane) > 0
        or delivery_state in (delivery.STATE_DELIVERED, delivery.STATE_PARTIAL_DELIVERED)
    )
    would_send = bool(_lane_count(run, "lane_counts_due", lane) or (run and _int(run.get("would_send_count")) > 0))
    if suppressed or not event_alpha_router.route_value_is_alertable(final_route):
        sent = False
        would_send = False
        blocked_by_guard = False
    card_path = _card_path_for_core(core_id, core_row, card_paths_by_core)
    feedback_target = (
        event_research_cards.card_feedback_target(card_path) if card_path and card_path.exists() else None
    ) or str(core_row.get("feedback_target") or core_id)
    ids = _core_review_ids(core, row, feedback_target, card_path)
    reviewed = bool(ids & reviewed_ids)
    return EventAlphaNotificationInboxItem(
        alert_id=core_id,
        alert_key=str(row.get("alert_id") or row.get("alert_key") or core_id),
        symbol=str(core.symbol or core_row.get("symbol") or core_row.get("validated_symbol") or "UNKNOWN"),
        coin_id=str(core.coin_id or core_row.get("coin_id") or core_row.get("validated_coin_id") or "unknown"),
        run_id=run_id,
        tier=tier,
        playbook=str(core_row.get("playbook_type") or core_row.get("effective_playbook_type") or core.primary_impact_path or "unknown"),
        card_path=str(card_path) if card_path else "",
        sent=sent,
        would_send=would_send,
        blocked_by_guard=blocked_by_guard,
        delivery_state=delivery_state,
        reviewed=reviewed,
        reason=str(row.get("route_reason") or core.why_opportunity_visible or row.get("reason") or "review pending"),
        final_route_after_quality_gate=final_route,
        final_tier_after_quality_gate=tier,
        quality_gate_block_reason=str(core_row.get("quality_gate_block_reason") or row.get("quality_gate_block_reason") or ""),
        alertable_after_quality_gate=event_alpha_router.route_value_is_alertable(final_route),
        snapshot_quality_classification=str(row.get("snapshot_quality_classification") or ""),
        item_type=_core_item_type(core),
        is_diagnostic=False,
        core_opportunity_id=core_id,
        feedback_target=feedback_target,
        feedback_target_type=str(core_row.get("feedback_target_type") or "core_opportunity_id"),
        final_state_after_quality_gate=final_state,
        opportunity_level=opportunity_level,
        **_inbox_decision_fields(core_row, row),
    )
def _diagnostic_item_from_alert(
    alert: Mapping[str, Any],
    runs_by_id: Mapping[str, Mapping[str, Any]],
    card_paths: Mapping[str, Path],
    reviewed_ids: set[str],
    delivery_state_by_run: Mapping[str, str],
) -> EventAlphaNotificationInboxItem:
    return _as_diagnostic_item(
        _inbox_item(alert, runs_by_id.get(str(alert.get("run_id") or "")), card_paths, reviewed_ids, delivery_state_by_run),
        alert,
    )
def _alerts_by_core_id(alerts: Iterable[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for row in alerts:
        core_id = str(row.get("core_opportunity_id") or row.get("diagnostic_support_for_core_opportunity_id") or "").strip()
        if not core_id:
            continue
        out.setdefault(core_id, []).append(dict(row))
    return out
def _best_snapshot_for_core(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any] | None:
    candidates = [dict(row) for row in rows if isinstance(row, Mapping)]
    if not candidates:
        return None

    def rank(row: Mapping[str, Any]) -> tuple[int, int, int, str]:
        diagnostic = alert_snapshot_is_diagnostic(row)
        snapshot_class = str(row.get("snapshot_class") or "")
        status = str(row.get("core_resolution_status") or row.get("snapshot_core_resolution_status") or "")
        canonical = (
            snapshot_class == event_alpha_alert_store.SNAPSHOT_CLASS_CANONICAL_CORE
            or status in {"canonical", event_alpha_alert_store.SNAPSHOT_CORE_RECONCILED}
            or bool(row.get("snapshot_core_reconciled"))
        ) and not diagnostic
        delivered = str(row.get("delivered_status") or row.get("delivery_state") or "") in {
            delivery.STATE_DELIVERED,
            delivery.STATE_PARTIAL_DELIVERED,
        }
        alertable = bool(row.get("alertable_after_quality_gate")) or event_alpha_router.route_value_is_alertable(
            str(row.get("final_route_after_quality_gate") or row.get("route") or "")
        )
        return (
            5 if canonical else 0,
            3 if alertable and not diagnostic else 0,
            2 if delivered else 0,
            str(row.get("observed_at") or row.get("snapshot_id") or ""),
        )

    return max(candidates, key=rank)
def _core_review_ids(
    core: event_core_opportunities.CoreOpportunity,
    row: Mapping[str, Any],
    feedback_target: str,
    card_path: Path | None,
) -> set[str]:
    ids = {
        core.core_opportunity_id,
        core.symbol,
        core.coin_id,
        core.incident_id or "",
        feedback_target,
        str(row.get("alert_id") or ""),
        str(row.get("alert_key") or ""),
        str(row.get("card_id") or ""),
        str(row.get("snapshot_id") or ""),
    }
    ids.update(str(value) for value in core.supporting_hypothesis_ids)
    if card_path:
        ids.update({str(card_path), card_path.name, card_path.stem})
        card_target = event_research_cards.card_feedback_target(card_path) if card_path.exists() else None
        if card_target:
            ids.add(card_target)
    ids = {item for item in ids if item}
    ids.update(f"ea:{item}" for item in list(ids) if item and not item.startswith("ea:"))
    ids.update(item[3:] for item in list(ids) if item.startswith("ea:"))
    return ids
def _core_item_type(core: event_core_opportunities.CoreOpportunity) -> str:
    if core.is_high_priority or core.is_watchlist or core.is_validated_digest or core.alertable:
        return "core_opportunity"
    level = str(core.opportunity_level or "").casefold()
    if level == "exploratory" or core.opportunity_score_final >= 50:
        return "near_miss_core"
    return "local_core_learning"
def _core_item_type_from_alert_stub(alert: Mapping[str, Any], alertable_after_quality_gate: bool) -> str:
    if alertable_after_quality_gate:
        return "core_opportunity"
    level = str(alert.get("opportunity_level") or alert.get("final_opportunity_level") or "").casefold()
    score = _float(alert.get("opportunity_score_final") or alert.get("opportunity_score"))
    if level == "exploratory" or score >= 50:
        return "near_miss_core"
    return "local_core_learning"
def _tier_for_core(core: event_core_opportunities.CoreOpportunity, final_route: str) -> str:
    route = str(final_route or "").upper()
    if "TRIGGERED_FADE" in route:
        return "TRIGGERED_FADE"
    if "HIGH_PRIORITY" in route or core.is_high_priority:
        return "HIGH_PRIORITY_WATCH"
    if "RESEARCH_DIGEST" in route or "WATCHLIST" in route or core.is_watchlist or core.is_validated_digest:
        return "RADAR_DIGEST"
    return "STORE_ONLY"
def _as_diagnostic_item(
    item: EventAlphaNotificationInboxItem,
    alert: Mapping[str, Any],
) -> EventAlphaNotificationInboxItem:
    item_type = _diagnostic_item_type(alert)
    target = str(alert.get("feedback_target") or alert.get("diagnostic_row_id") or alert.get("alert_id") or item.alert_id)
    return replace(
        item,
        item_type=item_type,
        is_diagnostic=True,
        sent=False,
        would_send=False,
        blocked_by_guard=False,
        alertable_after_quality_gate=False,
        core_opportunity_id=str(alert.get("core_opportunity_id") or ""),
        feedback_target=target,
        feedback_target_type=str(alert.get("feedback_target_type") or item_type),
    )
def _diagnostic_item_type(alert: Mapping[str, Any]) -> str:
    classification = str(alert.get("snapshot_quality_classification") or event_alpha_alert_store.classify_alert_snapshot(alert))
    snapshot_class = str(alert.get("snapshot_class") or "")
    playbook = str(alert.get("playbook_type") or alert.get("effective_playbook_type") or alert.get("latest_effective_playbook_type") or "").casefold()
    role = str(alert.get("candidate_role") or alert.get("asset_role") or "").casefold()
    if "source_noise" in playbook or role in {"source_noise", "ticker_word_collision"}:
        return "source_noise_control"
    if snapshot_class == event_alpha_alert_store.SNAPSHOT_CLASS_DIAGNOSTIC_SUPPORT:
        return "diagnostic_support_snapshot"
    if classification == event_alpha_alert_store.SNAPSHOT_QUALITY_GATED_LOCAL:
        return "quality_gated_local_support"
    if classification in _INBOX_LEGACY_CONFLICT_CLASSIFICATIONS:
        return "legacy_snapshot"
    if snapshot_class == event_alpha_alert_store.SNAPSHOT_CLASS_ORPHAN:
        return "orphan_snapshot"
    return "diagnostic_support_snapshot"
def _dedupe_review_items(items: Iterable[EventAlphaNotificationInboxItem]) -> list[EventAlphaNotificationInboxItem]:
    out: list[EventAlphaNotificationInboxItem] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        key = (
            "diagnostic" if item.is_diagnostic else "core",
            item.core_opportunity_id or item.feedback_target or item.alert_id,
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out
def _delivery_item_duplicates_core(
    item: EventAlphaNotificationInboxItem,
    core_items: Iterable[EventAlphaNotificationInboxItem],
) -> bool:
    identifiers = {item.alert_id, item.alert_key, item.symbol, item.coin_id}
    identifiers.update(value[3:] for value in list(identifiers) if value.startswith("ea:"))
    for core in core_items:
        core_ids = {core.alert_id, core.alert_key, core.core_opportunity_id, core.feedback_target, core.symbol, core.coin_id}
        core_ids.update(value[3:] for value in list(core_ids) if value.startswith("ea:"))
        if identifiers.intersection(value for value in core_ids if value):
            return True
    return False
def _inbox_item(
    alert: Mapping[str, Any],
    run: Mapping[str, Any] | None,
    card_paths: Mapping[str, Path],
    reviewed_ids: set[str],
    delivery_state_by_run: Mapping[str, str],
) -> EventAlphaNotificationInboxItem:
    alert_key = str(alert.get("alert_key") or "")
    alert_id = str(alert.get("alert_id") or (f"ea:{alert_key}" if alert_key else alert.get("snapshot_id") or "unknown"))
    card_id = str(alert.get("card_id") or "")
    card_path = _path_for_card(alert_id, alert_key, card_id, card_paths)
    final_route, quality_block, alertable_after_quality = _quality_gate_for_alert(alert)
    classification = str(alert.get("snapshot_quality_classification") or event_alpha_alert_store.classify_alert_snapshot(alert))
    if classification in _INBOX_LEGACY_CONFLICT_CLASSIFICATIONS:
        alertable_after_quality = False
    lane = _lane_for_alert(alert, final_route=final_route)
    due = _lane_count(run, "lane_counts_due", lane)
    run_id = str(alert.get("run_id") or (run or {}).get("run_id") or "")
    delivery_state = str(alert.get("delivered_status") or alert.get("delivery_state") or delivery_state_by_run.get(run_id) or "")
    suppressed = delivery_state in (delivery.STATE_SKIPPED_DUPLICATE, delivery.STATE_SKIPPED_IN_FLIGHT)
    blocked_by_guard = delivery_state == delivery.STATE_BLOCKED or _guard_blocked(run)
    sent = (
        _lane_count(run, "lane_counts_sent", lane) > 0
        or delivery_state in (delivery.STATE_DELIVERED, delivery.STATE_PARTIAL_DELIVERED)
    )
    would_send = bool(due or (run and _int(run.get("would_send_count")) > 0))
    if suppressed:
        would_send = False
    if not alertable_after_quality:
        sent = False
        would_send = False
        blocked_by_guard = False
    ids = _alert_ids(alert, alert_id, alert_key, card_id)
    reviewed = bool(ids & reviewed_ids)
    diagnostic = alert_snapshot_is_diagnostic(alert)
    item_type = _diagnostic_item_type(alert) if diagnostic else (
        "core_opportunity"
        if alertable_after_quality
        else _core_item_type_from_alert_stub(alert, alertable_after_quality)
    )
    return EventAlphaNotificationInboxItem(
        alert_id=alert_id,
        alert_key=alert_key,
        symbol=str(alert.get("symbol") or alert.get("asset_symbol") or alert.get("validated_symbol") or "UNKNOWN"),
        coin_id=str(alert.get("coin_id") or alert.get("asset_coin_id") or alert.get("validated_coin_id") or "unknown"),
        run_id=run_id,
        tier=str(alert.get("tier") or "UNKNOWN"),
        playbook=str(alert.get("playbook_type") or alert.get("effective_playbook_type") or "unknown"),
        card_path=str(card_path) if card_path else "",
        sent=sent,
        would_send=would_send,
        blocked_by_guard=blocked_by_guard,
        delivery_state=delivery_state,
        reviewed=reviewed,
        reason=str(alert.get("route_reason") or alert.get("reason") or (run or {}).get("block_reason") or "review pending"),
        final_route_after_quality_gate=final_route,
        final_tier_after_quality_gate=str(alert.get("final_tier_after_quality_gate") or alert.get("tier") or ""),
        quality_gate_block_reason=quality_block or "",
        alertable_after_quality_gate=alertable_after_quality,
        snapshot_quality_classification=classification,
        item_type=item_type,
        is_diagnostic=diagnostic,
        core_opportunity_id=str(alert.get("core_opportunity_id") or ""),
        feedback_target=str(alert.get("feedback_target") or alert_id),
        feedback_target_type=str(alert.get("feedback_target_type") or "alert_id"),
        final_state_after_quality_gate=str(alert.get("final_state_after_quality_gate") or alert.get("state") or ""),
        opportunity_level=str(alert.get("final_opportunity_level") or alert.get("opportunity_level") or ""),
        **_inbox_decision_fields(alert),
    )
def _digest_delivery_items(
    deliveries: Iterable[Mapping[str, Any]],
    watch_by_alert: Mapping[str, event_watchlist.EventWatchlistEntry],
    reviewed_ids: set[str],
    card_paths: Mapping[str, Path],
    *,
    lane: str,
    default_tier: str,
    default_playbook: str,
    default_reason: str,
) -> list[EventAlphaNotificationInboxItem]:
    items: list[EventAlphaNotificationInboxItem] = []
    for row in delivery.latest_rows_by_delivery(deliveries):
        if str(row.get("lane") or "") != lane:
            continue
        state = str(row.get("state") or "")
        alert_ids = [part.strip() for part in str(row.get("alert_id") or "").split(",") if part.strip()]
        if not alert_ids:
            alert_ids = [f"ea:{lane}"]
        for alert_id in alert_ids:
            entry = watch_by_alert.get(alert_id)
            key = alert_id[3:] if alert_id.startswith("ea:") else alert_id
            core_id = str(row.get("core_opportunity_id") or "").strip()
            symbol = str(row.get("canonical_symbol") or getattr(entry, "symbol", "") or "UNKNOWN")
            coin_id = str(row.get("canonical_coin_id") or getattr(entry, "coin_id", "") or "unknown")
            ids = {alert_id, key}
            if core_id:
                ids.add(core_id)
            if entry is not None:
                ids.update({entry.key, entry.event_id, entry.coin_id, entry.symbol, f"ea:{entry.key}"})
            reviewed = bool(ids & reviewed_ids)
            card_path = _path_for_card(alert_id, key, f"card_{key}", card_paths)
            sent = state in (delivery.STATE_DELIVERED, delivery.STATE_PARTIAL_DELIVERED)
            would_send = state in (delivery.STATE_BLOCKED, delivery.STATE_PLANNED, delivery.STATE_SENDING)
            items.append(EventAlphaNotificationInboxItem(
                alert_id=alert_id,
                alert_key=key,
                symbol=symbol,
                coin_id=coin_id,
                run_id=str(row.get("run_id") or ""),
                tier=str(getattr(entry, "latest_tier", "") or default_tier),
                playbook=str(getattr(entry, "latest_playbook_type", "") or default_playbook),
                card_path=str(row.get("canonical_card_path") or card_path or ""),
                sent=sent,
                would_send=would_send,
                blocked_by_guard=state == delivery.STATE_BLOCKED,
                delivery_state=state,
                reviewed=reviewed,
                reason=(
                    str(getattr(entry, "suppressed_reason", "") or "")
                    or str(row.get("status_detail") or "")
                    or default_reason
                ),
                core_opportunity_id=core_id,
                feedback_target=str(row.get("feedback_target") or core_id or alert_id),
                feedback_target_type=str(row.get("feedback_target_type") or ("core_opportunity_id" if core_id else "alert_id")),
                **_inbox_decision_fields(row),
            ))
    return items

def _inbox_decision_fields(*rows: Mapping[str, Any]) -> dict[str, Any]:
    values = decision_model_values(*rows)
    if not values:
        return {}
    return {
        "decision_model_version": str(values.get("decision_model_version") or ""),
        "decision_model_enabled": bool(values.get("decision_model_enabled", True)),
        "thesis_origin": str(values.get("thesis_origin") or ""),
        "primary_thesis_origin": str(values.get("primary_thesis_origin") or ""),
        "thesis_origins": _decision_text_tuple(values.get("thesis_origins")),
        "directional_bias": str(values.get("directional_bias") or ""),
        "catalyst_status": str(values.get("catalyst_status") or ""),
        "confidence_band": str(values.get("confidence_band") or ""),
        "timing_state": str(values.get("timing_state") or ""),
        "tradability_status": str(values.get("tradability_status") or ""),
        "spread_status": str(values.get("spread_status") or ""),
        "radar_route": str(values.get("radar_route") or ""),
        "radar_route_reason": str(values.get("radar_route_reason") or ""),
        "radar_actionable": bool(values.get("radar_actionable")),
        "actionability_score": _optional_float(values.get("actionability_score")),
        "evidence_confidence_score": _optional_float(values.get("evidence_confidence_score")),
        "risk_score": _optional_float(values.get("risk_score")),
        "urgency_score": _optional_float(values.get("urgency_score")),
        "market_phase": str(values.get("market_phase") or ""),
        "preferred_horizon": str(values.get("preferred_horizon") or ""),
        "expires_at": str(values.get("expires_at") or ""),
        "chase_risk_score": _optional_float(values.get("chase_risk_score")),
        "actionability_score_cohort": str(values.get("actionability_score_cohort") or ""),
        "anomaly_type": str(values.get("anomaly_type") or ""),
        "decision_missing_data": _decision_text_tuple(values.get("decision_missing_data")),
        "decision_warnings": _decision_text_tuple(values.get("decision_warnings")),
        "why_still_worth_reviewing": _decision_text_tuple(values.get("why_still_worth_reviewing")),
        "radar_what_confirms": _decision_text_tuple(values.get("radar_what_confirms")),
        "radar_what_invalidates": _decision_text_tuple(values.get("radar_what_invalidates")),
    }

def _decision_text_tuple(value: Any) -> tuple[str, ...]:
    if value in (None, "", [], {}, ()):
        return ()
    if isinstance(value, str):
        return tuple(item.strip() for item in value.replace(";", ",").split(",") if item.strip())
    if isinstance(value, Mapping):
        return tuple(f"{key}={child}" for key, child in value.items())
    if isinstance(value, Iterable):
        return tuple(str(item) for item in value if str(item))
    return (str(value),)

def _optional_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
def _latest_delivery_state_by_run(rows: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    by_run: dict[str, str] = {}
    priority = {
        delivery.STATE_DELIVERED: 5,
        delivery.STATE_PARTIAL_DELIVERED: 4,
        delivery.STATE_FAILED: 3,
        delivery.STATE_BLOCKED: 2,
        delivery.STATE_SKIPPED_DUPLICATE: 1,
        delivery.STATE_SKIPPED_IN_FLIGHT: 1,
    }
    for row in delivery.latest_rows_by_delivery(rows):
        run_id = str(row.get("run_id") or "")
        state = str(row.get("state") or "")
        if not run_id:
            continue
        current = by_run.get(run_id)
        if current is None or priority.get(state, 0) >= priority.get(current, 0):
            by_run[run_id] = state
    return by_run
def _delivery_suppressed_run(row: Mapping[str, Any], state_by_run: Mapping[str, str]) -> bool:
    state = state_by_run.get(str(row.get("run_id") or ""))
    return state in (delivery.STATE_SKIPPED_DUPLICATE, delivery.STATE_SKIPPED_IN_FLIGHT)
def _guard_blocked(row: Mapping[str, Any] | None) -> bool:
    if not row:
        return False
    if _int(row.get("deliveries_blocked")) > 0:
        return True
    reason = str(row.get("block_reason") or "").casefold()
    return "disabled" in reason or "guard" in reason or "research_only" in reason
def _quality_gate_for_alert(alert: Mapping[str, Any]) -> tuple[str, str | None, bool]:
    components = alert.get("score_components") if isinstance(alert.get("score_components"), Mapping) else {}
    has_quality = event_alpha_quality_fields.has_any_quality_field(alert, components_key="score_components")
    final_route, block = event_alpha_router.quality_gate_route_for_row(
        alert,
        components=components,
        require_quality=False,
    )
    if has_quality or alert.get("final_route_after_quality_gate") or alert.get("alertable_after_quality_gate") is not None:
        return final_route, block, event_alpha_router.route_value_is_alertable(final_route)
    route = str(alert.get("route") or final_route or "")
    route_alertable_raw = alert.get("route_alertable")
    if route_alertable_raw is None:
        alertable = event_alpha_router.route_value_is_alertable(route)
    else:
        alertable = bool(route_alertable_raw) and event_alpha_router.route_value_is_alertable(route)
    return route, block, alertable
def _lane_for_alert(alert: Mapping[str, Any], *, final_route: str | None = None) -> str:
    route = str(final_route or alert.get("final_route_after_quality_gate") or alert.get("route") or "").upper()
    tier = str(alert.get("tier") or "").upper()
    playbook = str(alert.get("playbook_type") or "").lower()
    if "TRIGGERED_FADE" in route or "TRIGGERED_FADE" in tier or playbook == "proxy_fade":
        return "triggered_fade"
    if "HIGH_PRIORITY" in route or tier == "HIGH_PRIORITY_WATCH":
        return "instant_escalation"
    return "daily_digest"
def _lane_count(row: Mapping[str, Any] | None, field: str, lane: str) -> int:
    if not row:
        return 0
    counts = row.get(field) or {}
    if not isinstance(counts, Mapping):
        return 0
    return _int(counts.get(lane))
