"""Delivery models for the notification pipeline."""

from __future__ import annotations

from .runtime import *

@dataclass(frozen=True)
class EventAlphaNotificationConfig:
    enabled: bool = False
    mode: str = "research_only"
    notification_scope: str = NOTIFICATION_SCOPE_GLOBAL
    profile_name: str | None = None
    artifact_namespace: str | None = None
    daily_digest_cooldown_hours: float = 12.0
    daily_digest_max_items: int = 5
    instant_escalation_cooldown_hours: float = 1.0
    max_instant_per_day: int = 3
    health_heartbeat_enabled: bool = True
    health_heartbeat_cooldown_hours: float = 24.0
    triggered_fade_dedupe: bool = True
    exploratory_digest_enabled: bool = False
    exploratory_digest_max_items: int = 10
    exploratory_digest_min_score: int = 0
    exploratory_digest_cooldown_hours: float = 24.0
    exploratory_digest_include_rejection_reasons: bool = True
    exploratory_digest_include_raw_evidence: bool = True
    exploratory_digest_include_controls: bool = False
    research_review_digest_enabled: bool = False
    research_review_digest_max_items: int = 3
    research_review_digest_min_score: float = 60.0
    research_review_digest_cooldown_hours: float = 12.0
    research_review_digest_include_local_only: bool = False
    research_review_digest_include_sector: bool = False
    research_review_digest_send_with_alerts: bool = False
    allow_source_only_narrative_digest: bool = False
    quality_mode: str = "validated_digest"

@dataclass(frozen=True)
class EventAlphaExploratoryDigestItem:
    decision: event_alpha_router.EventAlphaRouteDecision
    rank_score: float
    why_included: tuple[str, ...] = ()
    what_to_verify: tuple[str, ...] = ()

@dataclass(frozen=True)
class EventAlphaResearchReviewDigestItem:
    decision: event_alpha_router.EventAlphaRouteDecision
    rank_score: float
    why_included: tuple[str, ...] = ()
    why_not_alertable: tuple[str, ...] = ()
    what_would_upgrade: tuple[str, ...] = ()

@dataclass(frozen=True)
class EventAlphaResearchReviewSkippedItem:
    symbol: str
    coin_id: str
    core_opportunity_id: str | None
    score: float
    rank_score: float
    skip_reason: str
    candidate_family_id: str | None = None
    opportunity_type: str | None = None
    final_opportunity_level: str | None = None
    card_path: str | None = None
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "coin_id": self.coin_id,
            "core_opportunity_id": self.core_opportunity_id,
            "candidate_family_id": self.candidate_family_id,
            "opportunity_type": self.opportunity_type,
            "final_opportunity_level": self.final_opportunity_level,
            "score": self.score,
            "rank_score": self.rank_score,
            "skip_reason": self.skip_reason,
            "card_path": self.card_path,
            "detail": self.detail,
        }

@dataclass(frozen=True)
class EventAlphaNotificationPlan:
    all_decisions: tuple[event_alpha_router.EventAlphaRouteDecision, ...] = ()
    decisions_by_lane: dict[str, list[event_alpha_router.EventAlphaRouteDecision]] = field(default_factory=dict)
    blocked_by_lane: dict[str, str] = field(default_factory=dict)
    heartbeat_due: bool = False
    heartbeat_reason: str = "heartbeat disabled"
    exploratory_items: tuple[EventAlphaExploratoryDigestItem, ...] = ()
    research_review_items: tuple[EventAlphaResearchReviewDigestItem, ...] = ()
    research_review_eligible_count: int = 0
    research_review_skipped_items: tuple[EventAlphaResearchReviewSkippedItem, ...] = ()
    cooldown_status: dict[str, dict[str, Any]] = field(default_factory=dict)
    notification_scope: str = NOTIFICATION_SCOPE_GLOBAL
    scope_value: str = NOTIFICATION_SCOPE_GLOBAL
    migration_warnings: tuple[str, ...] = ()
    core_row_by_alert_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    canonicalization_warnings: tuple[str, ...] = ()

    @property
    def decision_count(self) -> int:
        return sum(len(items) for items in self.decisions_by_lane.values())

    @property
    def would_send_count(self) -> int:
        return (
            self.decision_count
            + len(self.research_review_items)
            + len(self.exploratory_items)
            + (1 if self.heartbeat_due else 0)
        )

    @property
    def lane_counts(self) -> dict[str, int]:
        counts = {lane: len(self.decisions_by_lane.get(lane, ())) for lane in LANES}
        counts[LANE_RESEARCH_REVIEW_DIGEST] = len(self.research_review_items)
        counts[LANE_EXPLORATORY_DIGEST] = len(self.exploratory_items)
        counts[LANE_HEALTH_HEARTBEAT] = 1 if self.heartbeat_due else 0
        return counts

@dataclass(frozen=True)
class DeliveryIdentity:
    notification_item_ids: tuple[str, ...]
    source_alert_ids: tuple[str, ...]
    core_opportunity_ids: tuple[str, ...] = ()
    canonical_symbols: tuple[str, ...] = ()
    canonical_coin_ids: tuple[str, ...] = ()
    canonical_card_paths: tuple[str, ...] = ()
    feedback_targets: tuple[str, ...] = ()
    requested_alert_id: str | None = None
    alert_id: str | None = None
    core_opportunity_id: str | None = None
    canonical_symbol: str | None = None
    canonical_coin_id: str | None = None
    canonical_card_path: str | None = None
    feedback_target: str | None = None
    identity_reconciled: bool = False
    identity_reconciliation_reason: str | None = None
    notification_preview_path: str | None = None
    notification_preview_relpath: str | None = None

__all__ = (
    'EventAlphaNotificationConfig',
    'EventAlphaExploratoryDigestItem',
    'EventAlphaResearchReviewDigestItem',
    'EventAlphaResearchReviewSkippedItem',
    'EventAlphaNotificationPlan',
    'DeliveryIdentity',
)
