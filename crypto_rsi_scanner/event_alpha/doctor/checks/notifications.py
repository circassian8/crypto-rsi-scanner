"""Notification delivery and preview consistency checks."""

from __future__ import annotations

from ._utils import Messages, ctx_mapping, ctx_value, emit

STALE_PRE_CANONICAL_NOTIFICATION_WARNING = (
    "This namespace contains pre-canonical notification delivery rows. Do not use it "
    "for send-readiness. Run notify_llm_deep_rehearsal or fixture final check."
)


def apply_checks(ctx: object, blockers: Messages, warnings: Messages) -> None:
    strict = bool(ctx_value(ctx, "strict", False))
    delivery_summary = ctx_value(ctx, "delivery_summary", None)
    delivery_conflicts = ctx_mapping(ctx, "delivery_conflicts")
    preview_conflicts = ctx_mapping(ctx, "preview_conflicts")

    if ctx_value(ctx, "research_review_enabled_but_lane_missing", 0):
        emit(blockers, warnings, "research_review_digest_enabled_but_lane_missing=1", blocker=strict)
    if ctx_value(ctx, "research_review_candidates_without_delivery", 0):
        emit(blockers, warnings, "research_review_digest_candidates_without_delivery=1", blocker=strict)
    if getattr(delivery_summary, "failed", 0):
        warnings.append(
            f"notification deliveries failed: {delivery_summary.failed} failed delivery row(s) for this profile/namespace"
        )

    for key in (
        "delivery_identity_mismatch_core_store",
        "delivery_core_id_missing",
        "delivery_feedback_target_missing",
        "delivery_card_path_missing",
        "delivery_alert_id_not_canonical",
        "delivery_status_missing",
        "delivery_status_detail_missing",
        "delivery_mode_missing",
        "delivery_state_inconsistent",
        "delivery_would_send_sent_failed_inconsistent",
        "digest_item_without_live_confirmation",
        "digest_item_rejected_results_only",
        "strategic_broad_asset_digest_without_confirmation",
        "unconfirmed_narrative_daily_digest",
        "single_source_no_market_fan_token_digest",
        "telegram_message_contains_absolute_path",
        "telegram_message_contains_raw_debug_dump",
        "multi_item_delivery_missing_arrays",
        "notification_body_card_mismatch_canonical",
        "notification_body_feedback_mismatch_canonical",
        "research_review_body_uses_hypothesis_target_when_core_exists",
    ):
        count = delivery_conflicts.get(key, 0)
        if count:
            emit(blockers, warnings, f"{key}={count}", blocker=strict)

    for key in (
        "research_review_digest_missing_confirmation_label",
        "research_review_digest_contains_strict_alertable",
        "research_review_digest_contains_hard_gated_candidate",
        "research_review_digest_too_many_items",
        "research_review_digest_missing_feedback_target",
        "research_review_digest_skipped_without_reason",
        "research_review_digest_missing_family_summary",
        "research_review_digest_duplicate_visible_family_summary",
        "research_review_digest_absolute_path",
    ):
        count = delivery_conflicts.get(key, 0)
        if not count:
            continue
        message = f"{key}={count}"
        if key in {
            "research_review_digest_contains_strict_alertable",
            "research_review_digest_contains_hard_gated_candidate",
            "research_review_digest_missing_feedback_target",
            "research_review_digest_skipped_without_reason",
            "research_review_digest_missing_family_summary",
            "research_review_digest_duplicate_visible_family_summary",
            "research_review_digest_absolute_path",
        }:
            emit(blockers, warnings, message, blocker=strict)
        else:
            warnings.append(message)

    if delivery_conflicts.get("notification_preview_missing", 0):
        warnings.append(f"notification_preview_missing={delivery_conflicts['notification_preview_missing']}")
    for key in (
        "notification_preview_relpath_missing",
        "notification_preview_path_unresolvable",
    ):
        count = delivery_conflicts.get(key, 0)
        if count:
            emit(blockers, warnings, f"{key}={count}", blocker=strict)

    for key in (
        "notification_preview_run_summary_mismatch",
        "notification_preview_llm_summary_mismatch",
        "notification_preview_lane_counts_mismatch",
        "notification_preview_core_count_mismatch",
        "notification_preview_alertable_count_mismatch",
        "notification_preview_missing_send_guard_status",
        "notification_preview_send_guard_status_missing",
        "notification_preview_no_send_status_unclear",
        "notification_preview_legacy_alerts_wording",
    ):
        count = preview_conflicts.get(key, 0)
        if count:
            emit(blockers, warnings, f"{key}={count}", blocker=strict)

    if delivery_conflicts.get("stale_delivery_identity_missing_core", 0):
        warnings.append(
            "stale_delivery_identity_missing_core="
            f"{delivery_conflicts['stale_delivery_identity_missing_core']}"
        )
    if delivery_conflicts.get("legacy_pre_core_delivery_identity", 0):
        warnings.append(
            "legacy_pre_core_delivery_identity="
            f"{delivery_conflicts['legacy_pre_core_delivery_identity']}"
        )
    if delivery_conflicts.get("stale_delivery_identity_missing_core", 0) or delivery_conflicts.get(
        "legacy_pre_core_delivery_identity", 0
    ):
        warnings.append(STALE_PRE_CANONICAL_NOTIFICATION_WARNING)
