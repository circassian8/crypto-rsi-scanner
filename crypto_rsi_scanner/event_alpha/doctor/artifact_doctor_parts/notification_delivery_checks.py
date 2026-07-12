"""Notification Delivery Checks for the artifact doctor."""

from __future__ import annotations

from .runtime import *
from .notification_preview_io import (
    _active_preview_api_alerts_wording_count,
    _delivery_preview_body,
    _latest_preview_path,
    _notification_preview_api_alerts_wording,
    _telegram_preview_bodies,
)
from .outcome_checks import _tuple_value

def _notification_delivery_conflicts(
    *,
    delivery_rows: Iterable[Mapping[str, Any]],
    core_rows_by_id: Mapping[str, Mapping[str, Any]],
    latest_run_id: str | None = None,
    strict_scope: str = "all_rows",
    notification_preview_path: str | Path | None = None,
) -> dict[str, int]:
    out = _empty_notification_delivery_conflicts()
    scope = _normalize_delivery_strict_scope(strict_scope, latest_run_id=latest_run_id, strict=True)
    for row in _delivery.latest_rows_by_delivery(delivery_rows):
        row_run_id = str(row.get("run_id") or "").strip()
        is_latest_run = bool(latest_run_id and row_run_id == latest_run_id)
        _add_delivery_scope_counts(out, row, latest_run_id=latest_run_id, is_latest_run=is_latest_run)
        if scope == "latest_run" and latest_run_id and not is_latest_run:
            continue

        _add_counter_map(out, _delivery_status_field_conflicts(row))
        telegram_body = _delivery_preview_body(
            row,
            out,
            is_latest_run=is_latest_run,
            notification_preview_path=notification_preview_path,
        )
        lane = str(row.get("lane") or "")
        scalar_core_ids = _tuple_value(row.get("core_opportunity_id"))
        core_ids = _tuple_value(row.get("core_opportunity_ids")) or scalar_core_ids
        alert_ids = _tuple_value(row.get("alert_id"))
        cores = tuple(core_rows_by_id[core_id] for core_id in core_ids if core_id in core_rows_by_id)
        missing_core_ids = tuple(core_id for core_id in core_ids if core_id not in core_rows_by_id)
        if lane == "research_review_digest":
            _add_research_review_digest_conflicts(out, row, telegram_body, core_ids=core_ids, cores=cores)
        if lane not in {"daily_digest", "instant_escalation", "triggered_fade"}:
            continue
        _add_strict_delivery_identity_conflicts(
            out,
            row,
            lane=lane,
            scalar_core_ids=scalar_core_ids,
            core_ids=core_ids,
            alert_ids=alert_ids,
            missing_core_ids=missing_core_ids,
        )
        _add_strict_delivery_core_conflicts(out, lane=lane, cores=cores)
    return out

def _empty_notification_delivery_conflicts() -> dict[str, int]:
    return {
        "latest_run_delivery_rows": 0,
        "legacy_delivery_rows": 0,
        "stale_delivery_rows": 0,
        "delivery_identity_mismatch_core_store": 0,
        "delivery_core_id_missing": 0,
        "legacy_pre_core_delivery_identity": 0,
        "stale_delivery_identity_missing_core": 0,
        "delivery_feedback_target_missing": 0,
        "delivery_card_path_missing": 0,
        "delivery_alert_id_not_canonical": 0,
        "telegram_message_contains_absolute_path": 0,
        "telegram_message_contains_raw_debug_dump": 0,
        "research_review_digest_missing_confirmation_label": 0,
        "research_review_digest_contains_strict_alertable": 0,
        "research_review_digest_contains_hard_gated_candidate": 0,
        "research_review_digest_too_many_items": 0,
        "research_review_digest_missing_feedback_target": 0,
        "research_review_digest_skipped_without_reason": 0,
        "research_review_digest_missing_family_summary": 0,
        "research_review_digest_duplicate_visible_family_summary": 0,
        "research_review_digest_absolute_path": 0,
        "notification_body_card_mismatch_canonical": 0,
        "notification_body_feedback_mismatch_canonical": 0,
        "research_review_body_uses_hypothesis_target_when_core_exists": 0,
        "digest_item_without_live_confirmation": 0,
        "digest_item_rejected_results_only": 0,
        "strategic_broad_asset_digest_without_confirmation": 0,
        "unconfirmed_narrative_daily_digest": 0,
        "single_source_no_market_fan_token_digest": 0,
        "multi_item_delivery_missing_arrays": 0,
        "notification_preview_missing": 0,
        "notification_preview_relpath_missing": 0,
        "notification_preview_path_unresolvable": 0,
        "delivery_status_missing": 0,
        "delivery_status_detail_missing": 0,
        "delivery_mode_missing": 0,
        "delivery_state_inconsistent": 0,
        "delivery_would_send_sent_failed_inconsistent": 0,
    }

def _add_counter_map(out: dict[str, int], increments: Mapping[str, int]) -> None:
    for key, value in increments.items():
        out[key] += value

def _add_delivery_scope_counts(
    out: dict[str, int],
    row: Mapping[str, Any],
    *,
    latest_run_id: str | None,
    is_latest_run: bool,
) -> None:
    if not latest_run_id:
        return
    if is_latest_run:
        out["latest_run_delivery_rows"] += 1
        return
    out["stale_delivery_rows"] += 1
    if _delivery_is_api_pre_core_identity(row):
        out["legacy_delivery_rows"] += 1
    if _delivery_lacks_core_identity(row):
        out["stale_delivery_identity_missing_core"] += 1
        if _delivery_is_api_pre_core_identity(row):
            out["legacy_pre_core_delivery_identity"] += 1

def _add_research_review_digest_conflicts(
    out: dict[str, int],
    row: Mapping[str, Any],
    telegram_body: str,
    *,
    core_ids: tuple[str, ...],
    cores: tuple[Mapping[str, Any], ...],
) -> None:
    if "Not alertable" not in telegram_body or "Missing confirmation" not in telegram_body:
        out["research_review_digest_missing_confirmation_label"] += 1
    if re.search(r"/Users/|/tmp/|/private/tmp/", telegram_body):
        out["research_review_digest_absolute_path"] += 1
    if len(re.findall(r"(?m)^\d+\.\s*<b>", telegram_body)) > 10:
        out["research_review_digest_too_many_items"] += 1
    if not str(row.get("feedback_target") or "").strip():
        out["research_review_digest_missing_feedback_target"] += 1
    _add_research_review_skip_conflicts(out, row, telegram_body)
    if core_ids:
        _add_research_review_body_conflicts(out, row, telegram_body)
    for digest_core in cores:
        if _research_review_core_is_alertable(digest_core):
            out["research_review_digest_contains_strict_alertable"] += 1
        if _research_review_core_is_hard_gated(digest_core):
            out["research_review_digest_contains_hard_gated_candidate"] += 1

def _add_research_review_skip_conflicts(out: dict[str, int], row: Mapping[str, Any], telegram_body: str) -> None:
    summary = row.get("channel_summary") if isinstance(row.get("channel_summary"), Mapping) else {}
    skipped_count = _as_int(row.get("skipped_candidate_count") or summary.get("skipped_candidate_count"))
    if skipped_count <= 0:
        return
    reason_counts = _research_review_skip_reason_counts(row, summary)
    skipped_items = _research_review_skipped_items(row, summary)
    display_family_summary = _research_review_display_family_summary(row, summary)
    family_summary = _research_review_family_summary(row, summary, display_family_summary)
    has_reason_counts = isinstance(reason_counts, Mapping) and any(str(key).strip() for key in reason_counts)
    if not has_reason_counts:
        out["research_review_digest_skipped_without_reason"] += 1
    has_family_summary = _has_research_review_family_summary(family_summary)
    if skipped_count > 10 and not has_family_summary:
        out["research_review_digest_missing_family_summary"] += 1
    if re.search(r"(?im)\+\d+\s+more skipped candidates", telegram_body) and not has_family_summary:
        out["research_review_digest_missing_family_summary"] += 1
    if not has_family_summary:
        return
    family_keys = _research_review_family_keys(family_summary)
    if _display_family_summary_has_duplicate_visible_label(display_family_summary):
        out["research_review_digest_duplicate_visible_family_summary"] += 1
    if _research_review_material_skipped_items_missing_family(skipped_items, family_keys):
        out["research_review_digest_missing_family_summary"] += 1

def _research_review_skip_reason_counts(row: Mapping[str, Any], summary: Mapping[str, Any]) -> object:
    if isinstance(row.get("skipped_reason_counts"), Mapping):
        return row.get("skipped_reason_counts")
    return summary.get("skipped_reason_counts") or summary.get("skip_reason_counts")

def _research_review_skipped_items(row: Mapping[str, Any], summary: Mapping[str, Any]) -> object:
    if isinstance(row.get("skipped_candidates_sample"), list):
        return row.get("skipped_candidates_sample")
    return summary.get("skipped_candidates_sample") or summary.get("skipped_candidates") or []

def _research_review_display_family_summary(row: Mapping[str, Any], summary: Mapping[str, Any]) -> list[object] | None:
    if isinstance(row.get("skipped_display_family_summary"), list):
        return row.get("skipped_display_family_summary")
    value = summary.get("skipped_display_family_summary")
    return value if isinstance(value, list) else None

def _research_review_family_summary(
    row: Mapping[str, Any],
    summary: Mapping[str, Any],
    display_family_summary: list[object] | None,
) -> object:
    if isinstance(display_family_summary, list):
        return display_family_summary
    if isinstance(row.get("skipped_family_summary"), list):
        return row.get("skipped_family_summary")
    value = summary.get("skipped_family_summary")
    return value if isinstance(value, list) else []

def _has_research_review_family_summary(family_summary: object) -> bool:
    return isinstance(family_summary, list) and any(
        isinstance(item, Mapping)
        and str(item.get("display_family_id") or item.get("candidate_family_id") or item.get("label") or "").strip()
        for item in family_summary
    )

def _research_review_family_keys(family_summary: object) -> set[str]:
    if not isinstance(family_summary, list):
        return set()
    keys = {
        str(item.get("display_family_id") or item.get("candidate_family_id") or item.get("label") or "").strip()
        for item in family_summary
        if isinstance(item, Mapping)
    }
    keys.update(
        str(item.get("label") or f"{item.get('symbol')}/{item.get('coin_id')}" or "").strip()
        for item in family_summary
        if isinstance(item, Mapping)
    )
    return keys

def _display_family_summary_has_duplicate_visible_label(display_family_summary: object) -> bool:
    if not isinstance(display_family_summary, list):
        return False
    visible_labels: list[str] = []
    for family_item in display_family_summary:
        if not isinstance(family_item, Mapping) or bool(family_item.get("display_hidden")):
            continue
        label = str(
            family_item.get("display_label")
            or family_item.get("label")
            or f"{family_item.get('symbol')}/{family_item.get('coin_id')}"
            or ""
        ).strip().casefold()
        if label:
            visible_labels.append(label)
    return len(visible_labels) != len(set(visible_labels))

def _research_review_material_skipped_items_missing_family(skipped_items: object, family_keys: set[str]) -> bool:
    if not isinstance(skipped_items, list):
        return False
    for item in skipped_items:
        if not isinstance(item, Mapping):
            continue
        if _as_int(item.get("skipped_count")) < 10 and _as_float(item.get("score") or item.get("rank_score")) < 60:
            continue
        family_key = str(
            item.get("display_family_id")
            or f"{item.get('symbol')}/{item.get('coin_id')}"
            or item.get("candidate_family_id")
            or ""
        ).strip()
        if family_key and family_key not in family_keys:
            return True
    return False

def _add_research_review_body_conflicts(
    out: dict[str, int],
    row: Mapping[str, Any],
    telegram_body: str,
) -> None:
    body_lower = telegram_body.casefold()
    card_paths = _tuple_value(row.get("canonical_card_paths")) or _tuple_value(row.get("canonical_card_path"))
    feedback_targets = _tuple_value(row.get("feedback_targets")) or _tuple_value(row.get("feedback_target"))
    for card_path in card_paths:
        basename = Path(str(card_path)).name
        if basename and basename.casefold() not in body_lower:
            out["notification_body_card_mismatch_canonical"] += 1
    for target in feedback_targets:
        if target and str(target).casefold() not in body_lower:
            out["notification_body_feedback_mismatch_canonical"] += 1
    if re.search(r"(?im)^\s*feedback target:\s*hyp:", telegram_body):
        out["research_review_body_uses_hypothesis_target_when_core_exists"] += 1

def _add_strict_delivery_identity_conflicts(
    out: dict[str, int],
    row: Mapping[str, Any],
    *,
    lane: str,
    scalar_core_ids: tuple[str, ...],
    core_ids: tuple[str, ...],
    alert_ids: tuple[str, ...],
    missing_core_ids: tuple[str, ...],
) -> None:
    if lane == "daily_digest" and len(scalar_core_ids) > 1 and not _tuple_value(row.get("core_opportunity_ids")):
        out["multi_item_delivery_missing_arrays"] += 1
    requires_core = _delivery_requires_core_identity(row)
    if requires_core:
        if not core_ids:
            out["delivery_core_id_missing"] += 1
        if not str(row.get("feedback_target") or "").strip():
            out["delivery_feedback_target_missing"] += 1
        if not str(row.get("canonical_card_path") or "").strip():
            out["delivery_card_path_missing"] += 1
    if missing_core_ids:
        out["delivery_identity_mismatch_core_store"] += 1
    if requires_core and alert_ids and lane != "triggered_fade" and (not core_ids or set(alert_ids) != set(core_ids)):
        out["delivery_alert_id_not_canonical"] += 1

def _add_strict_delivery_core_conflicts(
    out: dict[str, int],
    *,
    lane: str,
    cores: tuple[Mapping[str, Any], ...],
) -> None:
    if not cores or lane not in {"daily_digest", "instant_escalation"}:
        return
    for delivery_core in cores:
        if _delivery_core_lacks_live_confirmation(delivery_core):
            out["digest_item_without_live_confirmation"] += 1
        if lane == "daily_digest" and _delivery_core_is_unconfirmed_narrative(delivery_core):
            out["unconfirmed_narrative_daily_digest"] += 1
            if _delivery_core_is_single_source_no_market_fan_token(delivery_core):
                out["single_source_no_market_fan_token_digest"] += 1
        if str(delivery_core.get("evidence_acquisition_status") or "") == "rejected_results_only":
            out["digest_item_rejected_results_only"] += 1
        if _delivery_core_is_strategic_broad_asset_context(delivery_core):
            out["strategic_broad_asset_digest_without_confirmation"] += 1

def _delivery_status_field_conflicts(row: Mapping[str, Any]) -> dict[str, int]:
    out = {
        "delivery_status_missing": 0,
        "delivery_status_detail_missing": 0,
        "delivery_mode_missing": 0,
        "delivery_state_inconsistent": 0,
        "delivery_would_send_sent_failed_inconsistent": 0,
    }
    delivery_mode = str(row.get("delivery_mode") or "").strip()
    delivery_state = str(row.get("delivery_state") or "").strip()
    status = str(row.get("status") or "").strip()
    status_detail = str(row.get("status_detail") or "").strip()
    if not delivery_state or not status:
        out["delivery_status_missing"] += 1
    if not status_detail:
        out["delivery_status_detail_missing"] += 1
    if not delivery_mode:
        out["delivery_mode_missing"] += 1
    if not delivery_state or not status_detail or not delivery_mode:
        return out

    state = str(row.get("state") or "")
    sent = _boolish(row.get("sent"))
    failed = _boolish(row.get("failed"))
    would_send = _boolish(row.get("would_send"))
    guard_enabled = _boolish(row.get("send_guard_enabled"))
    if delivery_state == _delivery.DELIVERY_STATE_SENT and not sent:
        out["delivery_state_inconsistent"] += 1
    if delivery_state == _delivery.DELIVERY_STATE_FAILED and not failed:
        out["delivery_state_inconsistent"] += 1
    if delivery_state == _delivery.DELIVERY_STATE_BLOCKED and (sent or failed):
        out["delivery_state_inconsistent"] += 1
    if sent and failed:
        out["delivery_would_send_sent_failed_inconsistent"] += 1
    if sent and status_detail != _delivery.STATUS_DETAIL_SENT:
        out["delivery_would_send_sent_failed_inconsistent"] += 1
    if state == _delivery.STATE_BLOCKED and sent:
        out["delivery_would_send_sent_failed_inconsistent"] += 1
    if status_detail == _delivery.STATUS_DETAIL_WOULD_SEND_GUARD_DISABLED and guard_enabled:
        out["delivery_would_send_sent_failed_inconsistent"] += 1
    if sent and not guard_enabled:
        out["delivery_would_send_sent_failed_inconsistent"] += 1
    if would_send and not (sent or failed) and delivery_state not in {
        _delivery.DELIVERY_STATE_BLOCKED,
        _delivery.DELIVERY_STATE_PREVIEW,
        _delivery.DELIVERY_STATE_SUPPRESSED,
    }:
        out["delivery_would_send_sent_failed_inconsistent"] += 1
    return out

def _notification_preview_consistency_conflicts(
    *,
    delivery_rows: Iterable[Mapping[str, Any]],
    latest_run: Mapping[str, Any] | None,
    core_rows: Iterable[Mapping[str, Any]],
    latest_run_id: str | None,
    notification_preview_path: str | Path | None = None,
) -> dict[str, int]:
    out = _empty_notification_preview_conflicts()
    if not latest_run:
        return out
    path = _latest_preview_path(
        delivery_rows,
        latest_run_id=latest_run_id,
        notification_preview_path=notification_preview_path,
    )
    if path is None:
        return out
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    summary = _parse_notification_preview_summary(text)
    out["notification_preview_api_alerts_wording"] += _active_preview_api_alerts_wording_count(
        delivery_rows,
        latest_run=latest_run,
        latest_run_id=latest_run_id,
        notification_preview_path=notification_preview_path,
    )
    if not summary:
        return out
    _add_counter_map(
        out,
        _notification_preview_run_field_conflicts(
            summary,
            latest_run=latest_run,
            core_rows=core_rows,
            latest_run_id=latest_run_id,
        ),
    )
    _add_counter_map(
        out,
        _notification_preview_counter_conflicts(
            summary,
            text=text,
            latest_run=latest_run,
        ),
    )
    _add_counter_map(
        out,
        _notification_preview_delivery_summary_conflicts(
            summary,
            text=text,
            latest_run=latest_run,
            delivery_rows=delivery_rows,
            latest_run_id=latest_run_id,
        ),
    )
    return out


def _empty_notification_preview_conflicts() -> dict[str, int]:
    return {
        "notification_preview_run_summary_mismatch": 0,
        "notification_preview_llm_summary_mismatch": 0,
        "notification_preview_lane_counts_mismatch": 0,
        "notification_preview_core_count_mismatch": 0,
        "notification_preview_alertable_count_mismatch": 0,
        "notification_preview_missing_send_guard_status": 0,
        "notification_preview_send_guard_status_missing": 0,
        "notification_preview_no_send_status_unclear": 0,
        "notification_preview_api_alerts_wording": 0,
        "notification_preview_research_candidate_count_mismatch": 0,
        "notification_preview_source_snapshot_count_mismatch": 0,
        "notification_preview_rendered_item_count_mismatch": 0,
        "notification_preview_counter_scope_mismatch": 0,
        "notification_preview_legacy_counter_scope_mismatch": 0,
    }


def _notification_preview_run_field_conflicts(
    summary: Mapping[str, Any],
    *,
    latest_run: Mapping[str, Any],
    core_rows: Iterable[Mapping[str, Any]],
    latest_run_id: str | None,
) -> dict[str, int]:
    out = {
        "notification_preview_run_summary_mismatch": 0,
        "notification_preview_core_count_mismatch": 0,
        "notification_preview_alertable_count_mismatch": 0,
    }
    if "completed" in summary:
        expected = bool(latest_run.get("cycle_completed", True))
        if bool(summary["completed"]) != expected:
            out["notification_preview_run_summary_mismatch"] += 1
    if "raw_events" in summary:
        if _as_int(summary["raw_events"]) != _as_int(latest_run.get("raw_events")):
            out["notification_preview_run_summary_mismatch"] += 1
    if "extraction_rows" in summary:
        if _as_int(summary["extraction_rows"]) != _as_int(latest_run.get("extraction_rows")):
            out["notification_preview_run_summary_mismatch"] += 1
    if "core_opportunities" in summary:
        expected_core = _as_int(latest_run.get("core_opportunity_rows_written"))
        if expected_core <= 0:
            expected_core = sum(
                1
                for row in core_rows
                if str(row.get("run_id") or "") == str(latest_run_id or "")
            )
        if _as_int(summary["core_opportunities"]) != expected_core:
            out["notification_preview_core_count_mismatch"] += 1
    if "alertable" in summary:
        if _as_int(summary["alertable"]) != _as_int(latest_run.get("alertable")):
            out["notification_preview_alertable_count_mismatch"] += 1
    return out


def _notification_preview_counter_conflicts(
    summary: Mapping[str, Any],
    *,
    text: str,
    latest_run: Mapping[str, Any],
) -> dict[str, int]:
    out = {
        "notification_preview_research_candidate_count_mismatch": 0,
        "notification_preview_source_snapshot_count_mismatch": 0,
        "notification_preview_rendered_item_count_mismatch": 0,
        "notification_preview_counter_scope_mismatch": 0,
        "notification_preview_legacy_counter_scope_mismatch": 0,
    }
    expected_counters = event_alpha_run_counters.canonical_run_counters(latest_run)
    preview_counter_values = summary.get("_counter_values") or {}
    counter_scope_keys = (
        "raw_events",
        "candidate_events",
        "current_generation_core_rows",
        "current_generation_visible_core_rows",
        "cumulative_store_rows",
        "alertable_decisions",
        "strict_alerts",
    )
    for key in counter_scope_keys:
        observed_values = tuple(preview_counter_values.get(key) or ())
        if (
            observed_values
            and any(_as_int(value) != expected_counters[key] for value in observed_values)
        ) or (
            not observed_values
            and key in summary
            and _as_int(summary[key]) != expected_counters[key]
        ):
            out["notification_preview_counter_scope_mismatch"] += 1
    research_values = tuple(preview_counter_values.get("research_candidates") or ())
    if (
        research_values
        and any(_as_int(value) != expected_counters["research_candidates"] for value in research_values)
    ) or (
        not research_values
        and "research_candidates" in summary
        and _as_int(summary["research_candidates"]) != expected_counters["research_candidates"]
    ):
        out["notification_preview_research_candidate_count_mismatch"] += 1
    snapshot_values = tuple(preview_counter_values.get("source_alert_snapshots") or ())
    if (
        snapshot_values
        and any(_as_int(value) != expected_counters["source_alert_snapshots"] for value in snapshot_values)
    ) or (
        not snapshot_values
        and "source_alert_snapshots" in summary
        and _as_int(summary["source_alert_snapshots"]) != expected_counters["source_alert_snapshots"]
    ):
        out["notification_preview_source_snapshot_count_mismatch"] += 1
    rendered_values = tuple(preview_counter_values.get("preview_rendered_items") or ())
    if (
        rendered_values
        and any(_as_int(value) != expected_counters["preview_rendered_items"] for value in rendered_values)
    ) or (
        not rendered_values
        and "preview_rendered_items" in summary
        and _as_int(summary["preview_rendered_items"]) != expected_counters["preview_rendered_items"]
    ):
        out["notification_preview_rendered_item_count_mismatch"] += 1
    if "core_opportunities" in summary:
        out["notification_preview_counter_scope_mismatch"] += 1
    if "raw_source_candidates" in summary:
        declared_scope = bool(re.search(
            r"(?i)Raw source candidates\s*\(deprecated alias:\s*candidate_events\):",
            text,
        ))
        if (
            not declared_scope
            or _as_int(summary["raw_source_candidates"]) != expected_counters["candidate_events"]
        ):
            out["notification_preview_legacy_counter_scope_mismatch"] += 1
    return out


def _notification_preview_delivery_summary_conflicts(
    summary: Mapping[str, Any],
    *,
    text: str,
    latest_run: Mapping[str, Any],
    delivery_rows: Iterable[Mapping[str, Any]],
    latest_run_id: str | None,
) -> dict[str, int]:
    out = {
        "notification_preview_llm_summary_mismatch": 0,
        "notification_preview_lane_counts_mismatch": 0,
        "notification_preview_missing_send_guard_status": 0,
        "notification_preview_send_guard_status_missing": 0,
        "notification_preview_no_send_status_unclear": 0,
    }
    if "llm_calls" in summary:
        if _as_int(summary["llm_calls"]) != _as_int(latest_run.get("llm_calls_attempted")):
            out["notification_preview_llm_summary_mismatch"] += 1
    if "llm_skips" in summary:
        if _as_int(summary["llm_skips"]) != _as_int(latest_run.get("llm_skipped_due_budget")):
            out["notification_preview_llm_summary_mismatch"] += 1
    if "lane_due" in summary:
        expected_due = sum(_as_int(value) for value in dict(latest_run.get("send_lane_items_attempted") or {}).values())
        if _as_int(summary["lane_due"]) != expected_due:
            out["notification_preview_lane_counts_mismatch"] += 1
    if "lane_sent" in summary:
        expected_sent = sum(_as_int(value) for value in dict(latest_run.get("send_lane_items_delivered") or {}).values())
        if _as_int(summary["lane_sent"]) != expected_sent:
            out["notification_preview_lane_counts_mismatch"] += 1
    has_guard_line = bool(re.search(r"(?im)^Send guard:\s*.+$", text))
    if not has_guard_line:
        out["notification_preview_missing_send_guard_status"] += 1
        out["notification_preview_send_guard_status_missing"] += 1
    if _preview_is_no_send_or_blocked(delivery_rows, latest_run_id=latest_run_id) and not re.search(
        r"(?i)(no-send rehearsal|would_send_but_guard_disabled|send guard is disabled|blocked_by_send_guard|notifications paused)",
        text,
    ):
        out["notification_preview_no_send_status_unclear"] += 1
    return out

def _parse_notification_preview_summary(text: str) -> dict[str, Any]:
    bodies = "\n".join(_telegram_preview_bodies(text)) or text
    out: dict[str, Any] = {}
    out["_counter_values"] = _notification_preview_counter_values(text)
    completed = re.search(r"(?im)^Completed:\s*(yes|no)\b", bodies)
    if completed:
        out["completed"] = completed.group(1).casefold() == "yes"
    raw_core = re.search(
        r"(?im)^Raw events:\s*(\d+)\s*[·-]\s*Core opportunities:\s*(\d+)\b",
        bodies,
    )
    if raw_core:
        out["raw_events"] = raw_core.group(1)
        out["core_opportunities"] = raw_core.group(2)
    event_funnel = re.search(
        r"(?im)^Raw events:\s*(\d+)\s*[·-]\s*Candidate events:\s*(\d+)\s*[·-]\s*Research candidates:\s*(\d+)\b",
        bodies,
    )
    if event_funnel:
        out["raw_events"] = event_funnel.group(1)
        out["candidate_events"] = event_funnel.group(2)
        out["research_candidates"] = event_funnel.group(3)
    core_scopes = re.search(
        r"(?im)^Source alert snapshots:\s*(\d+)\s*[·-]\s*Current-generation core rows:\s*(\d+)\s*[·-]\s*Current-generation visible core rows:\s*(\d+)\s*[·-]\s*Cumulative store rows:\s*(\d+)\b",
        bodies,
    )
    if core_scopes:
        out["source_alert_snapshots"] = core_scopes.group(1)
        out["current_generation_core_rows"] = core_scopes.group(2)
        out["current_generation_visible_core_rows"] = core_scopes.group(3)
        out["cumulative_store_rows"] = core_scopes.group(4)
    decision_scopes = re.search(
        r"(?im)^Alertable decisions:\s*(\d+)\s*[·-]\s*Strict alerts:\s*(\d+)\s*[·-]\s*Preview-rendered items:\s*(\d+)\b",
        bodies,
    )
    if decision_scopes:
        out["alertable_decisions"] = decision_scopes.group(1)
        out["strict_alerts"] = decision_scopes.group(2)
        out["preview_rendered_items"] = decision_scopes.group(3)
    for key, label in (
        ("research_candidates", "Research candidates"),
        ("strict_alerts", "Strict alerts"),
        ("preview_rendered_items", "Preview-rendered items"),
    ):
        match = re.search(rf"(?i)(?:^|[·|]\s*){re.escape(label)}:\s*(\d+)\b", bodies, flags=re.MULTILINE)
        if match:
            out[key] = match.group(1)
    rendered_summary = re.search(
        r"(?im)^-\s*(?:preview_rendered_items|Rendered candidate items):\s*(\d+)\b",
        text,
    )
    if rendered_summary:
        out["preview_rendered_items"] = rendered_summary.group(1)
    legacy_raw_source = re.search(
        r"(?i)(?:^|[·|]\s*)Raw source candidates(?:\s*\([^)]*\))?:\s*(\d+)\b",
        bodies,
        flags=re.MULTILINE,
    )
    if legacy_raw_source:
        out["raw_source_candidates"] = legacy_raw_source.group(1)
    alertable = re.search(r"(?im)^Alertable decisions:\s*(\d+)\b", bodies)
    if alertable:
        out["alertable"] = alertable.group(1)
    extraction = re.search(r"(?im)^Extraction rows:\s*(\d+)\b", bodies)
    if extraction:
        out["extraction_rows"] = extraction.group(1)
    llm = re.search(r"(?im)^LLM calls/skips:\s*(\d+)\s*/\s*(\d+)\b", bodies)
    if llm:
        out["llm_calls"] = llm.group(1)
        out["llm_skips"] = llm.group(2)
    lanes = re.search(r"(?im)^Delivery lanes:\s*due=(\d+)\s*[·-]\s*sent=(\d+)\b", bodies)
    if lanes:
        out["lane_due"] = lanes.group(1)
        out["lane_sent"] = lanes.group(2)
    return out


def _notification_preview_counter_values(text: str) -> dict[str, tuple[int, ...]]:
    labels = {
        "raw_events": ("raw_events", "Raw events"),
        "candidate_events": ("candidate_events", "Candidate events"),
        "research_candidates": ("research_candidates", "Research candidates"),
        "source_alert_snapshots": ("source_alert_snapshots", "Source alert snapshots"),
        "current_generation_core_rows": (
            "current_generation_core_rows",
            "Current-generation core rows",
        ),
        "current_generation_visible_core_rows": (
            "current_generation_visible_core_rows",
            "Current-generation visible core rows",
        ),
        "cumulative_store_rows": ("cumulative_store_rows", "Cumulative store rows"),
        "alertable_decisions": ("alertable_decisions", "Alertable decisions"),
        "strict_alerts": ("strict_alerts", "Strict alerts"),
        "preview_rendered_items": ("preview_rendered_items", "Preview-rendered items"),
    }
    values: dict[str, tuple[int, ...]] = {}
    for key, aliases in labels.items():
        alias_pattern = "|".join(re.escape(alias) for alias in aliases)
        matches = re.findall(
            rf"(?i)(?:{alias_pattern})\s*[:=]\s*(\d+)\b",
            text,
        )
        if matches:
            values[key] = tuple(int(value) for value in matches)
    return values


def _daily_brief_operator_semantic_conflicts(
    path: str | Path | None,
    *,
    latest_run: Mapping[str, Any] | None,
) -> dict[str, int]:
    out = {
        "daily_brief_counter_scope_confusion": 0,
        "daily_brief_freshness_scope_missing": 0,
        "daily_brief_current_core_freshness_total_mismatch": 0,
        "daily_brief_visible_core_freshness_total_mismatch": 0,
    }
    if path is None or not latest_run:
        return out
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    required_scopes = (
        "current_core_market_freshness",
        "quality_row_market_freshness",
        "support_row_market_freshness",
        "current_generation_visible_core_freshness",
    )
    for scope in required_scopes:
        if not re.search(rf"(?im)^-\s*{re.escape(scope)}:\s*total=\d+;\s*statuses=", text):
            out["daily_brief_freshness_scope_missing"] += 1
    freshness_lines = re.findall(r"(?im)^-\s*[^\n]*freshness[^\n]*statuses=[^\n]*$", text)
    out["daily_brief_freshness_scope_missing"] += sum(
        1 for line in freshness_lines if not any(scope in line for scope in required_scopes)
    )
    expected = event_alpha_run_counters.canonical_run_counters(latest_run)["current_generation_core_rows"]
    current_core = re.search(
        r"(?im)^-\s*current_core_market_freshness:\s*total=(\d+)\b",
        text,
    )
    if current_core and _as_int(current_core.group(1)) != expected:
        out["daily_brief_current_core_freshness_total_mismatch"] += 1
    expected_visible = event_alpha_run_counters.canonical_run_counters(latest_run)[
        "current_generation_visible_core_rows"
    ]
    visible_core = re.search(
        r"(?im)^-\s*current_generation_visible_core_freshness:\s*total=(\d+)\b",
        text,
    )
    if visible_core and _as_int(visible_core.group(1)) != expected_visible:
        out["daily_brief_visible_core_freshness_total_mismatch"] += 1
    if re.search(r"(?im)^-\s*Core opportunities:\s*\d+\b|canonical_store_rows=", text):
        out["daily_brief_counter_scope_confusion"] += 1
    for field in (
        "current_generation_core_rows",
        "current_generation_visible_core_rows",
        "cumulative_store_rows",
    ):
        if not re.search(rf"\b{field}=\d+\b", text):
            out["daily_brief_counter_scope_confusion"] += 1
    return out

def _preview_is_no_send_or_blocked(
    delivery_rows: Iterable[Mapping[str, Any]],
    *,
    latest_run_id: str | None,
) -> bool:
    for row in _delivery.latest_rows_by_delivery(delivery_rows):
        if latest_run_id and str(row.get("run_id") or "") != str(latest_run_id):
            continue
        if str(row.get("state") or "") == _delivery.STATE_BLOCKED:
            return True
    return False

def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0

def _as_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0

def _normalize_delivery_strict_scope(
    value: str | None,
    *,
    latest_run_id: str | None,
    strict: bool,
) -> str:
    cleaned = str(value or "").strip().casefold()
    if cleaned in {"latest_run", "all_rows", "legacy_included", "historical_included"}:
        return cleaned
    if strict and latest_run_id:
        return "latest_run"
    return "all_rows"

def _latest_run_id(run_rows: Iterable[Mapping[str, Any]]) -> str | None:
    ids = [str(row.get("run_id") or "").strip() for row in run_rows if str(row.get("run_id") or "").strip()]
    if not ids:
        return None
    return sorted(ids)[-1]

def _delivery_lacks_core_identity(row: Mapping[str, Any]) -> bool:
    lane = str(row.get("lane") or "").strip()
    if lane not in {"daily_digest", "instant_escalation"}:
        return False
    return not (_tuple_value(row.get("core_opportunity_ids")) or _tuple_value(row.get("core_opportunity_id")))

def _delivery_is_api_pre_core_identity(row: Mapping[str, Any]) -> bool:
    reason = str(row.get("identity_reconciliation_reason") or "").strip().casefold()
    if reason in {"legacy", "legacy_delivery", "external", "source_alert_identity_api"}:
        return True
    if str(row.get("legacy") or "").casefold() in {"1", "true", "yes"}:
        return True
    return _delivery_lacks_core_identity(row) and not str(row.get("feedback_target") or "").strip()

def _delivery_requires_core_identity(row: Mapping[str, Any]) -> bool:
    lane = str(row.get("lane") or "").strip()
    if lane not in {"daily_digest", "instant_escalation"}:
        return False
    reason = str(row.get("identity_reconciliation_reason") or "").strip().casefold()
    if reason in {"legacy", "legacy_delivery", "external", "source_alert_identity_api"}:
        return False
    if str(row.get("legacy") or "").casefold() in {"1", "true", "yes"}:
        return False
    return True

def _delivery_core_lacks_live_confirmation(core: Mapping[str, Any]) -> bool:
    if not event_alpha_router.route_value_is_alertable(core.get("final_route_after_quality_gate") or core.get("route")):
        return False
    status = str(core.get("evidence_acquisition_status") or "").strip()
    confirmation = str(core.get("acquisition_confirmation_status") or "").strip()
    accepted = max(
        _as_int(core.get("accepted_evidence_count")),
        _as_int(core.get("evidence_acquisition_accepted_count")),
        _as_int(core.get("accepted_count")),
    )
    source_class = str(core.get("source_class") or "").strip()
    market = str(core.get("market_confirmation_level") or "").casefold()
    freshness = str(core.get("market_context_freshness_status") or "").casefold()
    impact = str(core.get("impact_path_type") or "").casefold()
    strong_source = source_class in {
        "official_project",
        "official_exchange",
        "structured_event_calendar",
        "cryptopanic_tagged",
        "project_blog",
        "exchange_announcement",
    }
    direct_impact = impact in {
        "direct_token_event",
        "listing_liquidity_event",
        "unlock_supply_event",
        "exploit_security_event",
        "venue_value_capture",
        "fan_token_event",
    }
    fresh_market = market not in {"", "none", "missing", "unknown", "insufficient_data"} and freshness not in {"missing", "stale"}
    if accepted > 0 or confirmation == "confirms" or bool(core.get("acquisition_confirms_candidate")):
        return False
    if strong_source or (fresh_market and direct_impact):
        return False
    return status in {
        "",
        "rejected_results_only",
        "no_results",
        "skipped_budget",
        "provider_unavailable",
        "skipped_config",
        "not_configured",
    } or confirmation in {"", "does_not_confirm", "unresolved", "coverage_gap"}

def _delivery_core_is_unconfirmed_narrative(core: Mapping[str, Any]) -> bool:
    source_pack = str(core.get("source_pack") or "").strip().casefold()
    if source_pack not in {"fan_sports_pack", "proxy_preipo_rwa_pack", "political_meme_pack"}:
        return False
    if not event_alpha_router.route_value_is_alertable(core.get("final_route_after_quality_gate") or core.get("route")):
        return False
    return _delivery_core_lacks_narrative_digest_confirmation(core)

def _delivery_core_is_single_source_no_market_fan_token(core: Mapping[str, Any]) -> bool:
    source_pack = str(core.get("source_pack") or "").strip().casefold()
    if source_pack != "fan_sports_pack":
        return False
    accepted = max(
        _as_int(core.get("accepted_evidence_count")),
        _as_int(core.get("evidence_acquisition_accepted_count")),
        _as_int(core.get("accepted_count")),
    )
    provider_counts = _mapping_counts(core.get("accepted_provider_counts"))
    market = str(core.get("market_confirmation_level") or "").strip().casefold()
    freshness = str(core.get("market_context_freshness_status") or "").strip().casefold()
    no_market = market in {"", "none", "missing", "unknown", "insufficient_data"} or freshness in {"missing", "stale", "unknown"}
    return accepted <= 1 and provider_counts.get("cryptopanic", 0) >= 1 and no_market

def _delivery_core_lacks_narrative_digest_confirmation(core: Mapping[str, Any]) -> bool:
    accepted = max(
        _as_int(core.get("accepted_evidence_count")),
        _as_int(core.get("evidence_acquisition_accepted_count")),
        _as_int(core.get("accepted_count")),
    )
    source_class = str(core.get("source_class") or "").strip().casefold()
    official_or_structured = source_class in {
        "official_project",
        "official_exchange",
        "structured_calendar",
        "structured_unlock",
        "exchange_announcement",
    }
    market = str(core.get("market_confirmation_level") or "").strip().casefold()
    freshness = str(core.get("market_context_freshness_status") or "").strip().casefold()
    market_ok = market in {"moderate", "strong", "confirmed", "fresh"} and freshness not in {"missing", "stale", "unknown"}
    provider_counts = _mapping_counts(core.get("accepted_provider_counts"))
    reason_codes = " ".join(str(value) for value in _tuple_value(core.get("accepted_reason_codes")))
    reason_codes += " " + " ".join(str(value) for value in _mapping_counts(core.get("accepted_reason_code_counts")))
    cryptopanic_confirmed = provider_counts.get("cryptopanic", 0) > 0 and "cryptopanic_currency_tag_match" in reason_codes.casefold()
    if official_or_structured or accepted >= 2:
        return False
    if cryptopanic_confirmed and market_ok:
        return False
    return True

def _mapping_counts(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    out: dict[str, int] = {}
    for key, raw in value.items():
        try:
            count = int(raw or 0)
        except (TypeError, ValueError):
            continue
        out[str(key).strip().casefold()] = max(0, count)
    return out

def _delivery_core_is_strategic_broad_asset_context(core: Mapping[str, Any]) -> bool:
    if not _delivery_core_lacks_live_confirmation(core):
        return False
    symbol = str(core.get("symbol") or core.get("validated_symbol") or "").strip().upper()
    coin_id = str(core.get("coin_id") or core.get("validated_coin_id") or "").strip().casefold()
    if symbol not in {"BTC", "ETH", "SOL"} and coin_id not in {"bitcoin", "ethereum", "solana"}:
        return False
    impact = str(core.get("impact_path_type") or core.get("primary_impact_path") or "").strip().casefold()
    reason = str(core.get("impact_path_reason") or core.get("primary_impact_path_reason") or "").strip().casefold()
    if impact not in {"strategic_investment", "strategic_investment_or_valuation", "valuation_event"} and reason not in {
        "strategic_investment",
        "treasury_context",
        "external_equity_proxy_context",
    }:
        return False
    text = " ".join(
        str(core.get(key) or "")
        for key in (
            "canonical_incident_name",
            "incident_canonical_name",
            "latest_event_name",
            "event_name",
            "latest_source_title",
            "source_title",
            "latest_source",
            "source",
            "why_opportunity_visible",
            "final_verdict_reason",
        )
    ).casefold()
    return any(
        term in text
        for term in (
            "strategy",
            "microstrategy",
            "mstr",
            "treasury",
            "holdings",
            "valuation",
            "discount",
            "premium",
            "public company",
            "market structure",
        )
    )

def _research_review_core_is_alertable(core: Mapping[str, Any]) -> bool:
    route = str(core.get("final_route_after_quality_gate") or core.get("route") or "")
    level = str(core.get("final_opportunity_level") or core.get("opportunity_level") or "").strip()
    if event_alpha_router.route_value_is_alertable(route):
        return True
    return level in {"validated_digest", "watchlist", "high_priority"}

def _research_review_core_is_hard_gated(core: Mapping[str, Any]) -> bool:
    symbol = str(core.get("symbol") or core.get("validated_symbol") or "").strip().upper()
    coin_id = str(core.get("coin_id") or core.get("validated_coin_id") or "").strip().casefold()
    if symbol == "SECTOR" or coin_id.startswith("sector"):
        return True
    fields = " ".join(
        str(core.get(key) or "").casefold()
        for key in (
            "candidate_role",
            "relationship_type",
            "impact_path_type",
            "impact_path_reason",
            "playbook_type",
            "effective_playbook_type",
            "quality_gate_block_reason",
            "why_not_promoted",
            "why_local_only",
            "why_not_watchlist",
            "snapshot_class",
        )
    )
    return any(
        token in fields
        for token in (
            "source_noise",
            "ticker_word_collision",
            "ticker_collision",
            "word_collision",
            "generic_cooccurrence_only",
            "source_noise_control",
            "ambiguous_control",
            "diagnostic_support",
        )
    )

def _as_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0

def _boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().casefold()
    return text in {"1", "true", "yes", "y", "on"}

def _row_has_alertable_quality_conflict(row: Mapping[str, Any]) -> bool:
    components = row.get("score_components") if isinstance(row.get("score_components"), Mapping) else {}
    data = event_alpha_quality_fields.ensure_quality_fields(row, components=components)
    final_route, _ = event_alpha_router.quality_gate_route_for_row(row, components=components, require_quality=False)
    route_alertable = bool(row.get("route_alertable"))
    route = str(row.get("route") or "")
    persisted_alertable = route_alertable or event_alpha_router.route_value_is_alertable(route)
    final_alertable = event_alpha_router.route_value_is_alertable(final_route)
    if persisted_alertable and not final_alertable:
        return True
    if event_alpha_router.route_value_is_alertable(route) and route != final_route:
        return True
    if not final_alertable and not persisted_alertable:
        return False
    if final_route == "TRIGGERED_FADE_RESEARCH":
        return False
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

__all__ = (
    '_notification_delivery_conflicts',
    '_delivery_status_field_conflicts',
    '_notification_preview_consistency_conflicts',
    '_daily_brief_operator_semantic_conflicts',
    '_active_preview_api_alerts_wording_count',
    '_notification_preview_api_alerts_wording',
    '_latest_preview_path',
    '_parse_notification_preview_summary',
    '_preview_is_no_send_or_blocked',
    '_as_int',
    '_as_float',
    '_normalize_delivery_strict_scope',
    '_latest_run_id',
    '_delivery_lacks_core_identity',
    '_delivery_is_api_pre_core_identity',
    '_delivery_requires_core_identity',
    '_telegram_preview_bodies',
    '_delivery_core_lacks_live_confirmation',
    '_delivery_core_is_unconfirmed_narrative',
    '_delivery_core_is_single_source_no_market_fan_token',
    '_delivery_core_lacks_narrative_digest_confirmation',
    '_mapping_counts',
    '_delivery_core_is_strategic_broad_asset_context',
    '_research_review_core_is_alertable',
    '_research_review_core_is_hard_gated',
    '_as_int',
    '_boolish',
    '_row_has_alertable_quality_conflict',
)
