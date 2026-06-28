"""Operator inbox for Event Alpha day-1 notification review."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import event_alpha_alert_store
from . import event_alpha_notification_delivery as delivery
from . import event_alpha_quality_fields
from . import (
    event_alpha_notifications,
    event_alpha_router,
    event_core_opportunities,
    event_core_opportunity_store,
    event_research_cards,
    event_watchlist,
)

_INBOX_LEGACY_CONFLICT_CLASSIFICATIONS = {
    event_alpha_alert_store.SNAPSHOT_LEGACY_CONFLICT,
    event_alpha_alert_store.SNAPSHOT_STALE_PRE_QUALITY_GATE,
}


@dataclass(frozen=True)
class EventAlphaNotificationInboxItem:
    alert_id: str
    alert_key: str
    symbol: str
    coin_id: str
    run_id: str
    tier: str
    playbook: str
    card_path: str
    sent: bool
    would_send: bool
    blocked_by_guard: bool
    delivery_state: str
    reviewed: bool
    reason: str
    final_route_after_quality_gate: str = ""
    final_tier_after_quality_gate: str = ""
    quality_gate_block_reason: str = ""
    alertable_after_quality_gate: bool = True
    snapshot_quality_classification: str = ""
    item_type: str = "core_opportunity"
    is_diagnostic: bool = False
    core_opportunity_id: str = ""
    feedback_target: str = ""
    feedback_target_type: str = ""
    final_state_after_quality_gate: str = ""
    opportunity_level: str = ""


@dataclass(frozen=True)
class EventAlphaNotificationInboxResult:
    profile: str
    artifact_namespace: str
    notification_runs_path: Path
    alert_store_path: Path
    feedback_path: Path
    research_cards_dir: Path
    outcomes_path: Path | None
    notification_runs_read: int
    alert_rows_read: int
    feedback_rows_read: int
    research_cards_read: int
    outcome_rows_read: int
    sent_without_feedback: tuple[EventAlphaNotificationInboxItem, ...]
    partial_delivered_without_feedback: tuple[EventAlphaNotificationInboxItem, ...]
    would_send_without_feedback: tuple[EventAlphaNotificationInboxItem, ...]
    would_send_blocked_without_feedback: tuple[EventAlphaNotificationInboxItem, ...]
    weak_validated_local_only: tuple[EventAlphaNotificationInboxItem, ...]
    quality_gated_local_only: tuple[EventAlphaNotificationInboxItem, ...]
    legacy_quality_conflicts: tuple[EventAlphaNotificationInboxItem, ...]
    exploratory_without_feedback: tuple[EventAlphaNotificationInboxItem, ...]
    high_priority_unreviewed: tuple[EventAlphaNotificationInboxItem, ...]
    triggered_fade_unreviewed: tuple[EventAlphaNotificationInboxItem, ...]
    heartbeat_only_runs: tuple[dict[str, Any], ...]
    duplicate_or_in_flight_runs: tuple[dict[str, Any], ...]
    provider_degraded_runs: tuple[dict[str, Any], ...]
    canonical_review_items: tuple[EventAlphaNotificationInboxItem, ...] = ()
    diagnostic_review_items_hidden: tuple[EventAlphaNotificationInboxItem, ...] = ()
    diagnostic_review_items: tuple[EventAlphaNotificationInboxItem, ...] = ()
    canonical_review_items_with_cards: int = 0
    canonical_review_items_with_feedback_targets: int = 0
    diagnostic_review_items_with_feedback_targets: int = 0
    include_diagnostics: bool = False


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
    include_legacy_conflicts: bool = False,
    include_diagnostics: bool = False,
) -> EventAlphaNotificationInboxResult:
    """Join notification, alert, card, and feedback artifacts into review queues."""
    runs = [dict(row) for row in notification_runs if isinstance(row, Mapping)]
    alerts = [dict(row) for row in alert_rows if isinstance(row, Mapping)]
    feedback = [dict(row) for row in feedback_rows if isinstance(row, Mapping)]
    deliveries = [dict(row) for row in notification_delivery_rows if isinstance(row, Mapping)]
    core_rows = [dict(row) for row in core_opportunity_rows if isinstance(row, Mapping)]
    cards_dir = Path(research_cards_dir).expanduser()
    card_paths = _card_paths(cards_dir)
    card_paths_by_core = _card_paths_by_core_id(cards_dir)
    reviewed_ids = _reviewed_ids(feedback)
    watch_by_alert = {
        event_alpha_router.alert_id_for_entry(entry): entry
        for entry in watchlist_entries
    }
    runs_by_id = {str(row.get("run_id") or ""): row for row in runs if row.get("run_id")}
    delivery_state_by_run = _latest_delivery_state_by_run(deliveries)
    all_review_items = _build_event_alpha_review_items_from_rows(
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_diagnostics=True,
        notification_runs=runs,
        alert_rows=alerts,
        feedback_rows=feedback,
        research_cards_dir=cards_dir,
        notification_delivery_rows=deliveries,
        watchlist_entries=watchlist_entries,
        core_opportunity_rows=core_rows,
    )
    canonical_review_items = tuple(item for item in all_review_items if not item.is_diagnostic)
    diagnostic_review_items = tuple(item for item in all_review_items if item.is_diagnostic)
    items = [
        item for item in all_review_items
        if include_diagnostics or not item.is_diagnostic
    ]
    quality_gated_local_only = tuple(
        item for item in items
        if not item.is_diagnostic
        if item.snapshot_quality_classification == event_alpha_alert_store.SNAPSHOT_QUALITY_GATED_LOCAL
        and not item.reviewed
    )
    legacy_quality_conflicts = tuple(
        item for item in items
        if not item.is_diagnostic
        if item.snapshot_quality_classification in _INBOX_LEGACY_CONFLICT_CLASSIFICATIONS
        and not item.reviewed
    )
    partial_delivered_without_feedback = tuple(
        item for item in items
        if not item.is_diagnostic
        if item.delivery_state == delivery.STATE_PARTIAL_DELIVERED
        and _countable_alertable(item, include_legacy_conflicts=include_legacy_conflicts)
        and not item.reviewed
    )
    sent_without_feedback = tuple(
        item for item in items
        if not item.is_diagnostic
        if item.sent
        and _countable_alertable(item, include_legacy_conflicts=include_legacy_conflicts)
        and item.delivery_state != delivery.STATE_PARTIAL_DELIVERED
        and not item.reviewed
    )
    would_send_without_feedback = tuple(
        item for item in items
        if not item.is_diagnostic
        if item.would_send
        and _countable_alertable(item, include_legacy_conflicts=include_legacy_conflicts)
        and not item.sent
        and not item.blocked_by_guard
        and not item.reviewed
    )
    would_send_blocked_without_feedback = tuple(
        item for item in items
        if not item.is_diagnostic
        if item.blocked_by_guard
        and _countable_alertable(item, include_legacy_conflicts=include_legacy_conflicts)
        and not item.reviewed
    )
    weak_validated_local_only = tuple(
        item for item in items
        if not item.is_diagnostic
        if not item.quality_gate_block_reason and _is_weak_validated_local_only(item, alerts) and not item.reviewed
    )
    high_priority_unreviewed = tuple(
        item for item in items
        if not item.is_diagnostic
        and _countable_alertable(item, include_legacy_conflicts=include_legacy_conflicts)
        and not item.reviewed and item.item_type == "core_opportunity"
        and not (item.sent or item.would_send or item.blocked_by_guard)
    )
    triggered_fade_unreviewed = tuple(
        item for item in items
        if not item.is_diagnostic
        and _countable_alertable(item, include_legacy_conflicts=include_legacy_conflicts)
        and not item.reviewed and _is_triggered_fade(item)
        and not (item.sent or item.would_send or item.blocked_by_guard)
    )
    near_miss_core_items = tuple(
        item for item in items
        if not item.is_diagnostic and item.item_type == "near_miss_core" and not item.reviewed
    )
    exploratory_delivery_items = tuple(
        item for item in _exploratory_items(deliveries, watch_by_alert, reviewed_ids, card_paths)
        if not item.reviewed and not _delivery_item_duplicates_core(item, canonical_review_items)
    )
    exploratory_without_feedback = (*near_miss_core_items, *exploratory_delivery_items)
    local_core_learning = tuple(
        item for item in items
        if not item.is_diagnostic and item.item_type == "local_core_learning" and not item.reviewed
    )
    quality_gated_local_only = tuple(dict.fromkeys((*quality_gated_local_only, *local_core_learning)))
    outcomes = _read_jsonl(Path(outcomes_path).expanduser()) if outcomes_path else []
    return EventAlphaNotificationInboxResult(
        profile=str(profile or "default"),
        artifact_namespace=str(artifact_namespace or "default"),
        notification_runs_path=Path(notification_runs_path).expanduser(),
        alert_store_path=Path(alert_store_path).expanduser(),
        feedback_path=Path(feedback_path).expanduser(),
        research_cards_dir=cards_dir,
        outcomes_path=Path(outcomes_path).expanduser() if outcomes_path else None,
        notification_runs_read=len(runs),
        alert_rows_read=len(alerts),
        feedback_rows_read=len(feedback),
        research_cards_read=len(card_paths),
        outcome_rows_read=len(outcomes),
        sent_without_feedback=sent_without_feedback,
        partial_delivered_without_feedback=partial_delivered_without_feedback,
        would_send_without_feedback=would_send_without_feedback,
        would_send_blocked_without_feedback=would_send_blocked_without_feedback,
        weak_validated_local_only=weak_validated_local_only,
        quality_gated_local_only=quality_gated_local_only,
        legacy_quality_conflicts=legacy_quality_conflicts,
        exploratory_without_feedback=exploratory_without_feedback,
        high_priority_unreviewed=high_priority_unreviewed,
        triggered_fade_unreviewed=triggered_fade_unreviewed,
        heartbeat_only_runs=tuple(row for row in runs if _heartbeat_only(row)),
        duplicate_or_in_flight_runs=tuple(row for row in runs if _delivery_suppressed_run(row, delivery_state_by_run)),
        provider_degraded_runs=tuple(row for row in runs if _provider_degraded(row)),
        canonical_review_items=canonical_review_items,
        diagnostic_review_items_hidden=diagnostic_review_items if not include_diagnostics else (),
        diagnostic_review_items=diagnostic_review_items if include_diagnostics else (),
        canonical_review_items_with_cards=sum(1 for item in canonical_review_items if item.card_path),
        canonical_review_items_with_feedback_targets=sum(1 for item in canonical_review_items if item.feedback_target),
        diagnostic_review_items_with_feedback_targets=sum(1 for item in diagnostic_review_items if item.feedback_target),
        include_diagnostics=include_diagnostics,
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


def format_notification_inbox(result: EventAlphaNotificationInboxResult) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA NOTIFICATION INBOX (research-only / review queue)",
        "=" * 76,
        f"profile: {result.profile}",
        f"artifact_namespace: {result.artifact_namespace}",
        f"notification_runs_path: {result.notification_runs_path}",
        f"alert_store_path: {result.alert_store_path}",
        f"feedback_path: {result.feedback_path}",
        f"research_cards_dir: {result.research_cards_dir}",
        f"outcomes_path: {result.outcomes_path or 'not loaded'}",
        (
            "rows: "
            f"notification_runs={result.notification_runs_read} "
            f"alerts={result.alert_rows_read} "
            f"feedback={result.feedback_rows_read} "
            f"cards={result.research_cards_read} "
            f"outcomes={result.outcome_rows_read}"
        ),
        (
            "review_items: "
            f"canonical={len(result.canonical_review_items)} "
            f"canonical_cards={result.canonical_review_items_with_cards} "
            f"canonical_feedback_targets={result.canonical_review_items_with_feedback_targets} "
            f"diagnostics_hidden={len(result.diagnostic_review_items_hidden)} "
            f"diagnostics_visible={len(result.diagnostic_review_items)}"
        ),
        "",
    ]
    _append_item_section(
        lines,
        "delivered core opportunities needing feedback",
        result.sent_without_feedback,
        profile=result.profile,
    )
    _append_item_section(
        lines,
        "partial-delivered core opportunities needing delivery review",
        result.partial_delivered_without_feedback,
        profile=result.profile,
    )
    _append_item_section(lines, "would-send core opportunities blocked by preview mode", result.would_send_without_feedback, profile=result.profile)
    _append_item_section(lines, "would-send core opportunities blocked by guard without feedback", result.would_send_blocked_without_feedback, profile=result.profile)
    _append_item_section(lines, "near-misses for optional review", result.exploratory_without_feedback, profile=result.profile)
    _append_item_section(lines, "local-only learning rows for optional review", (*result.quality_gated_local_only, *result.weak_validated_local_only), profile=result.profile)
    _append_item_section(lines, "legacy quality conflicts for migration review", result.legacy_quality_conflicts, profile=result.profile)
    _append_item_section(lines, "high-priority/watchlist/digest core opportunities not reviewed", result.high_priority_unreviewed, profile=result.profile)
    _append_item_section(lines, "triggered-fade cards not reviewed", result.triggered_fade_unreviewed, profile=result.profile)
    if result.diagnostic_review_items:
        _append_item_section(lines, "diagnostic/support snapshots", result.diagnostic_review_items, profile=result.profile)
    elif result.diagnostic_review_items_hidden:
        lines.append(f"diagnostic/support snapshots hidden by default: {len(result.diagnostic_review_items_hidden)}")
        lines.append("- pass the diagnostics flag in local tooling to inspect source-noise/control snapshots")
        lines.append("")
    _append_run_section(lines, "heartbeat-only runs", result.heartbeat_only_runs)
    _append_run_section(lines, "duplicate/in-flight suppressed runs", result.duplicate_or_in_flight_runs)
    _append_run_section(lines, "provider-degraded notification runs", result.provider_degraded_runs)
    lines.append("Review queue is artifact-only; it does not send, trade, paper trade, or alter Event Alpha tiers.")
    return "\n".join(lines).rstrip()


def _append_item_section(
    lines: list[str],
    title: str,
    items: Iterable[EventAlphaNotificationInboxItem],
    *,
    profile: str,
) -> None:
    rows = list(items)
    lines.append(f"{title}: {len(rows)}")
    if not rows:
        lines.append("- none")
        lines.append("")
        return
    for item in rows[:20]:
        lines.append(
            f"- {item.symbol or 'UNKNOWN'}/{item.coin_id or 'unknown'} alert_id={item.alert_id} "
            f"tier={item.tier} playbook={item.playbook} "
            f"sent={_yes_no(item.sent)} would_send={_yes_no(item.would_send)} "
            f"delivery_state={item.delivery_state or 'none'}"
        )
        lines.append(f"  card: {item.card_path or 'not_written'}")
        lines.append(f"  run_id: {item.run_id or 'unknown'}")
        if item.quality_gate_block_reason:
            lines.append(
                f"  quality_gate: final={item.final_route_after_quality_gate or 'unknown'} "
                f"tier={item.final_tier_after_quality_gate or item.tier or 'unknown'} "
                f"block={item.quality_gate_block_reason}"
            )
        if item.snapshot_quality_classification:
            lines.append(f"  snapshot_classification: {item.snapshot_quality_classification}")
        lines.append(f"  reason: {item.reason}")
        target = item.feedback_target or item.alert_id
        lines.append(f"  feedback_target: {target}")
        lines.append(f"  feedback_useful: make event-feedback-useful PROFILE={profile} FEEDBACK_TARGET='{target}'")
        lines.append(f"  feedback_junk: make event-feedback-junk PROFILE={profile} FEEDBACK_TARGET='{target}'")
    lines.append("")


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
        alert_id=str(row.get("alert_id") or core_id),
        alert_key=str(row.get("alert_key") or core_id),
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


def alert_snapshot_is_diagnostic(row: Mapping[str, Any]) -> bool:
    """Return true for support/control snapshots that should be hidden by default."""
    return (
        bool(row.get("is_diagnostic_snapshot"))
        or str(row.get("snapshot_class") or "") == event_alpha_alert_store.SNAPSHOT_CLASS_DIAGNOSTIC_SUPPORT
        or str(row.get("core_resolution_status") or "") == "diagnostic_support"
        or str(row.get("snapshot_core_resolution_status") or "") == "diagnostic_support"
        or str(row.get("core_opportunity_id_status") or "") == "diagnostic_support"
        or event_core_opportunities.row_is_diagnostic(row)
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


def _card_paths_by_core_id(cards_dir: Path) -> dict[str, Path]:
    if not cards_dir or not cards_dir.exists():
        return {}
    out: dict[str, Path] = {}
    for path in cards_dir.glob("*.md"):
        if path.name == "index.md":
            continue
        core_id = event_research_cards.card_core_opportunity_id(path)
        if core_id:
            out.setdefault(core_id, path)
    return out


def _card_path_for_core(
    core_id: str,
    row: Mapping[str, Any],
    paths_by_core: Mapping[str, Path],
) -> Path | None:
    for key in ("research_card_path", "card_path"):
        value = str(row.get(key) or "").strip()
        if value:
            return Path(value)
    return paths_by_core.get(core_id)


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


def _append_run_section(lines: list[str], title: str, rows: Iterable[Mapping[str, Any]]) -> None:
    items = list(rows)
    lines.append(f"{title}: {len(items)}")
    if not items:
        lines.append("- none")
        lines.append("")
        return
    for row in items[:20]:
        lines.append(
            f"- run_id={row.get('run_id') or 'unknown'} "
            f"started_at={row.get('started_at') or 'unknown'} "
            f"profile={row.get('notification_profile') or row.get('profile') or 'default'} "
            f"scope={row.get('scope') or 'unknown'}:{row.get('scope_value') or 'unknown'}"
        )
        warnings = [str(item) for item in row.get("warnings") or [] if str(item)]
        if warnings:
            lines.append("  warnings: " + "; ".join(warnings[:5]))
        provider = row.get("provider_fail_fast_blocks") or []
        if provider:
            lines.append("  provider_fail_fast_blocks: " + "; ".join(str(item) for item in provider[:5]))
    lines.append("")


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
    )


def _exploratory_items(
    deliveries: Iterable[Mapping[str, Any]],
    watch_by_alert: Mapping[str, event_watchlist.EventWatchlistEntry],
    reviewed_ids: set[str],
    card_paths: Mapping[str, Path],
) -> list[EventAlphaNotificationInboxItem]:
    items: list[EventAlphaNotificationInboxItem] = []
    for row in delivery.latest_rows_by_delivery(deliveries):
        if str(row.get("lane") or "") != event_alpha_notifications.LANE_EXPLORATORY_DIGEST:
            continue
        state = str(row.get("state") or "")
        alert_ids = [part.strip() for part in str(row.get("alert_id") or "").split(",") if part.strip()]
        if not alert_ids:
            alert_ids = ["ea:exploratory"]
        for alert_id in alert_ids:
            entry = watch_by_alert.get(alert_id)
            key = alert_id[3:] if alert_id.startswith("ea:") else alert_id
            ids = {alert_id, key}
            if entry is not None:
                ids.update({entry.key, entry.event_id, entry.coin_id, entry.symbol, f"ea:{entry.key}"})
            reviewed = bool(ids & reviewed_ids)
            card_path = _path_for_card(alert_id, key, f"card_{key}", card_paths)
            sent = state in (delivery.STATE_DELIVERED, delivery.STATE_PARTIAL_DELIVERED)
            would_send = state in (delivery.STATE_BLOCKED, delivery.STATE_PLANNED, delivery.STATE_SENDING)
            items.append(EventAlphaNotificationInboxItem(
                alert_id=alert_id,
                alert_key=key,
                symbol=str(getattr(entry, "symbol", "") or "UNKNOWN"),
                coin_id=str(getattr(entry, "coin_id", "") or "unknown"),
                run_id=str(row.get("run_id") or ""),
                tier=str(getattr(entry, "latest_tier", "") or "EXPLORATORY"),
                playbook=str(getattr(entry, "latest_playbook_type", "") or "exploratory"),
                card_path=str(card_path) if card_path else "",
                sent=sent,
                would_send=would_send,
                blocked_by_guard=state == delivery.STATE_BLOCKED,
                delivery_state=state,
                reviewed=reviewed,
                reason=(
                    str(getattr(entry, "suppressed_reason", "") or "")
                    or "exploratory digest item; low-confidence/store-only row needs review"
                ),
            ))
    return items


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


def _countable_alertable(
    item: EventAlphaNotificationInboxItem,
    *,
    include_legacy_conflicts: bool,
) -> bool:
    if item.snapshot_quality_classification in _INBOX_LEGACY_CONFLICT_CLASSIFICATIONS:
        return bool(include_legacy_conflicts and item.alertable_after_quality_gate)
    return bool(item.alertable_after_quality_gate)


def _lane_for_alert(alert: Mapping[str, Any], *, final_route: str | None = None) -> str:
    route = str(final_route or alert.get("final_route_after_quality_gate") or alert.get("route") or "").upper()
    tier = str(alert.get("tier") or "").upper()
    playbook = str(alert.get("playbook_type") or "").lower()
    if "TRIGGERED_FADE" in route or "TRIGGERED_FADE" in tier or playbook == "proxy_fade":
        return "triggered_fade"
    if "HIGH_PRIORITY" in route or tier == "HIGH_PRIORITY_WATCH":
        return "instant_escalation"
    return "daily_digest"


def _is_high_priority(item: EventAlphaNotificationInboxItem) -> bool:
    return item.tier == "HIGH_PRIORITY_WATCH" or "HIGH_PRIORITY" in item.reason.upper()


def _is_triggered_fade(item: EventAlphaNotificationInboxItem) -> bool:
    return item.tier == "TRIGGERED_FADE" or item.playbook == "proxy_fade" or "TRIGGERED_FADE" in item.reason.upper()


def _is_weak_validated_local_only(
    item: EventAlphaNotificationInboxItem,
    alerts: Iterable[Mapping[str, Any]],
) -> bool:
    for alert in alerts:
        alert_key = str(alert.get("alert_key") or "")
        alert_id = str(alert.get("alert_id") or (f"ea:{alert_key}" if alert_key else ""))
        if item.alert_id not in {alert_id, f"ea:{alert_key}"} and item.alert_key != alert_key:
            continue
        if str(alert.get("relationship_type") or "") != "impact_hypothesis":
            return False
        if bool(alert.get("route_alertable")):
            return False
        components = alert.get("score_components") if isinstance(alert.get("score_components"), Mapping) else {}
        stage = str(alert.get("validation_stage") or components.get("validation_stage") or "")
        impact_path_strength = str(alert.get("impact_path_strength") or components.get("impact_path_strength") or "")
        impact_path_type = str(alert.get("impact_path_type") or components.get("impact_path_type") or "")
        opportunity_level = str(alert.get("opportunity_level") or components.get("opportunity_level") or "")
        why_digest_ineligible = str(alert.get("why_digest_ineligible") or components.get("why_digest_ineligible") or "")
        reason_text = " ".join(str(value or "") for value in (
            alert.get("route_reason"),
            alert.get("reason"),
            *((alert.get("quality_warnings") or []) if isinstance(alert.get("quality_warnings"), list) else []),
        )).casefold()
        return (
            stage == "catalyst_link_validated"
            or impact_path_strength in {"weak", "none"}
            or impact_path_type == "generic_cooccurrence_only"
            or opportunity_level in {"local_only", "exploratory"}
            or bool(why_digest_ineligible)
            or "impact_path_not_validated" in reason_text
            or "weak_validated" in reason_text
            or "generic_cooccurrence" in reason_text
        )
    return False


def _reviewed_ids(rows: Iterable[Mapping[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for row in rows:
        for field in ("target", "key", "event_id", "coin_id", "symbol", "card_id", "alert_id"):
            value = str(row.get(field) or "").strip()
            if value:
                ids.add(value)
                if value.startswith("ea:"):
                    ids.add(value[3:])
                else:
                    ids.add(f"ea:{value}")
    return ids


def _alert_ids(alert: Mapping[str, Any], alert_id: str, alert_key: str, card_id: str) -> set[str]:
    ids = {value for value in (alert_id, alert_key, card_id) if value}
    for field in ("event_id", "coin_id", "symbol", "asset_coin_id", "asset_symbol", "validated_coin_id", "validated_symbol", "snapshot_id"):
        value = str(alert.get(field) or "").strip()
        if value:
            ids.add(value)
    ids.update(f"ea:{value}" for value in list(ids) if value and not value.startswith("ea:"))
    ids.update(value[3:] for value in list(ids) if value.startswith("ea:"))
    return ids


def _card_paths(cards_dir: Path) -> dict[str, Path]:
    if not cards_dir.exists():
        return {}
    paths = {
        path.stem: path
        for path in cards_dir.glob("*.md")
        if path.name != "index.md"
    }
    return paths


def _path_for_card(
    alert_id: str,
    alert_key: str,
    card_id: str,
    paths: Mapping[str, Path],
) -> Path | None:
    for key in (card_id, alert_id.replace("ea:", "card_"), f"card_{alert_key}"):
        clean = _card_key(key)
        if clean in paths:
            return paths[clean]
    return None


def _card_key(value: str) -> str:
    text = str(value or "").strip()
    if text.endswith(".md"):
        text = text[:-3]
    return text


def _lane_count(row: Mapping[str, Any] | None, field: str, lane: str) -> int:
    if not row:
        return 0
    counts = row.get(field) or {}
    if not isinstance(counts, Mapping):
        return 0
    return _int(counts.get(lane))


def _heartbeat_only(row: Mapping[str, Any]) -> bool:
    due = row.get("lane_counts_due") or {}
    sent = row.get("lane_counts_sent") or {}
    non_heartbeat_due = sum(_int(value) for key, value in dict(due).items() if key != "health_heartbeat")
    non_heartbeat_sent = sum(_int(value) for key, value in dict(sent).items() if key != "health_heartbeat")
    return bool(row.get("heartbeat_due") or row.get("heartbeat_sent")) and non_heartbeat_due == 0 and non_heartbeat_sent == 0


def _provider_degraded(row: Mapping[str, Any]) -> bool:
    return bool(
        row.get("partial_results")
        or _int(row.get("provider_failure_count")) > 0
        or row.get("provider_fail_fast_blocks")
        or row.get("runtime_budget_exhausted")
        or _degraded_warning(row.get("warnings") or ())
    )


def _degraded_warning(warnings: Iterable[Any]) -> bool:
    tokens = ("failed", "failure", "timeout", "dns", "429", "backoff", "runtime_budget")
    return any(any(token in str(warning).casefold() for token in tokens) for warning in warnings)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
