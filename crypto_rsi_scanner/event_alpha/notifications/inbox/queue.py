"""Split implementation for `crypto_rsi_scanner/event_alpha/notifications/inbox.py` (queue)."""

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
from .. import delivery
from .. import pipeline as event_alpha_notifications
from .models import *  # noqa: F403

def build_ranked_review_queue(
    result: EventAlphaNotificationInboxResult,
    *,
    include_diagnostics: bool = False,
    limit: int | None = None,
) -> tuple[EventAlphaReviewQueueItem, ...]:
    """Return a compact operator queue ranked for burn-in review.

    The queue is a presentation layer only. It does not alter route decisions,
    delivery state, feedback rows, or Event Alpha scoring.
    """
    queue: list[EventAlphaReviewQueueItem] = []

    def add(items: Iterable[EventAlphaNotificationInboxItem], category: str) -> None:
        for item in items:
            if item.is_diagnostic and not include_diagnostics:
                continue
            queue.append(_review_queue_item(item, category))

    strict = tuple(
        item for item in (
            *result.sent_without_feedback,
            *result.partial_delivered_without_feedback,
            *result.would_send_without_feedback,
            *result.would_send_blocked_without_feedback,
            *result.high_priority_unreviewed,
            *result.triggered_fade_unreviewed,
        )
        if _item_alertable(item)
    )
    high = tuple(item for item in strict if _item_high_priority(item))
    digest = tuple(item for item in strict if item not in high)
    add(high, REVIEW_QUEUE_HIGH_PRIORITY_WOULD_SEND)
    add(digest, REVIEW_QUEUE_DIGEST_WOULD_SEND)
    add(result.research_review_without_feedback, REVIEW_QUEUE_RESEARCH_REVIEW_NEAR_MISS)
    add(result.exploratory_without_feedback, REVIEW_QUEUE_UPGRADE_CANDIDATE)
    local_learning = (*result.quality_gated_local_only, *result.weak_validated_local_only)
    if not include_diagnostics:
        local_learning = tuple(item for item in local_learning if not _item_is_diagnostic_control(item))
    add(local_learning, REVIEW_QUEUE_LOCAL_ONLY_LEARNING_ROW)
    if include_diagnostics:
        add(result.diagnostic_review_items, REVIEW_QUEUE_DIAGNOSTIC_ONLY)
    else:
        add(result.diagnostic_review_items_hidden, REVIEW_QUEUE_DIAGNOSTIC_ONLY)
        queue = [item for item in queue if item.category != REVIEW_QUEUE_DIAGNOSTIC_ONLY]

    deduped: dict[str, EventAlphaReviewQueueItem] = {}
    for item in queue:
        key = item.feedback_target or item.source_item.core_opportunity_id or item.source_item.alert_id
        prior = deduped.get(key)
        if prior is None or item.rank_score > prior.rank_score:
            deduped[key] = item
    ranked = sorted(
        deduped.values(),
        key=lambda item: (
            item.rank_score,
            _category_weight(item.category),
            item.symbol,
            item.coin_id,
        ),
        reverse=True,
    )
    if limit is not None:
        ranked = ranked[: max(0, int(limit))]
    return tuple(ranked)
def _review_queue_item(item: EventAlphaNotificationInboxItem, category: str) -> EventAlphaReviewQueueItem:
    score = _category_weight(category) + _item_score_hint(item) + _freshness_bonus(item) - _missing_evidence_penalty(item)
    return EventAlphaReviewQueueItem(
        category=category,
        rank_score=round(score, 2),
        symbol=item.symbol,
        coin_id=item.coin_id,
        tier=item.tier,
        route=item.final_route_after_quality_gate,
        reason=item.reason,
        card_basename=_card_label(item.card_path),
        feedback_target=item.feedback_target or item.alert_id,
        source_item=item,
    )
def _category_weight(category: str) -> float:
    return _REVIEW_QUEUE_WEIGHTS.get(category, 0.0)
def _item_alertable(item: EventAlphaNotificationInboxItem) -> bool:
    return bool(item.alertable_after_quality_gate) or event_alpha_router.route_value_is_alertable(item.final_route_after_quality_gate)
def _item_high_priority(item: EventAlphaNotificationInboxItem) -> bool:
    text = " ".join(str(part or "") for part in (
        item.tier,
        item.final_route_after_quality_gate,
        item.final_state_after_quality_gate,
        item.opportunity_level,
        item.reason,
    )).casefold()
    return "high_priority" in text or "triggered_fade" in text
def _item_is_diagnostic_control(item: EventAlphaNotificationInboxItem) -> bool:
    text = " ".join(str(part or "") for part in (
        item.playbook,
        item.item_type,
        item.reason,
        item.quality_gate_block_reason,
        item.opportunity_level,
    )).casefold()
    return bool(item.is_diagnostic) or any(token in text for token in (
        "source_noise",
        "ticker_collision",
        "word_collision",
        "diagnostic",
        "control",
    ))
def _item_score_hint(item: EventAlphaNotificationInboxItem) -> float:
    if item.actionability_score is not None:
        evidence_bonus = (item.evidence_confidence_score or 0.0) * 0.1
        return float(item.actionability_score) + evidence_bonus
    text = " ".join(str(part or "") for part in (
        item.reason,
        item.tier,
        item.opportunity_level,
        item.final_route_after_quality_gate,
    ))
    scores = [float(match.group(1)) for match in re.finditer(r"(?:score|rank|level)[=: ]+([0-9]+(?:\.[0-9]+)?)", text, flags=re.IGNORECASE)]
    if scores:
        return max(scores)
    if _item_high_priority(item):
        return 90.0
    if "watchlist" in text.casefold():
        return 75.0
    if "digest" in text.casefold():
        return 65.0
    if item.item_type == "near_miss_core":
        return 60.0
    if item.opportunity_level == "local_only":
        return 30.0
    return 45.0
def _freshness_bonus(item: EventAlphaNotificationInboxItem) -> float:
    text = item.reason.casefold()
    if "fresh" in text or "novel" in text:
        return 8.0
    if "stale" in text or "legacy" in text:
        return -8.0
    return 0.0
def _missing_evidence_penalty(item: EventAlphaNotificationInboxItem) -> float:
    text = " ".join(str(part or "") for part in (
        item.reason,
        item.quality_gate_block_reason,
    )).casefold()
    penalty = 0.0
    for token in ("missing", "unconfirmed", "no_results", "rejected", "source_noise", "generic"):
        if token in text:
            penalty += 4.0
    penalty += min(12.0, len(item.decision_missing_data) * 2.0)
    if item.risk_score is not None:
        penalty += max(0.0, float(item.risk_score) - 50.0) * 0.1
    return min(20.0, penalty)
def _human_queue_category(category: str) -> str:
    return {
        REVIEW_QUEUE_STRICT_ALERTABLE: "strict alert",
        REVIEW_QUEUE_HIGH_PRIORITY_WOULD_SEND: "high-priority would-send",
        REVIEW_QUEUE_DIGEST_WOULD_SEND: "digest would-send",
        REVIEW_QUEUE_RESEARCH_REVIEW_NEAR_MISS: "research-review near-miss",
        REVIEW_QUEUE_UPGRADE_CANDIDATE: "upgrade candidate",
        REVIEW_QUEUE_LOCAL_ONLY_LEARNING_ROW: "local-only learning",
        REVIEW_QUEUE_DIAGNOSTIC_ONLY: "diagnostic only",
    }.get(category, category.replace("_", " "))
def _countable_alertable(
    item: EventAlphaNotificationInboxItem,
    *,
    include_api_conflicts: bool,
) -> bool:
    if item.snapshot_quality_classification in _INBOX_LEGACY_CONFLICT_CLASSIFICATIONS:
        return bool(include_api_conflicts and item.alertable_after_quality_gate)
    return bool(item.alertable_after_quality_gate)
def _is_high_priority(item: EventAlphaNotificationInboxItem) -> bool:
    return item.tier == "HIGH_PRIORITY_WATCH" or "HIGH_PRIORITY" in item.reason.upper()
