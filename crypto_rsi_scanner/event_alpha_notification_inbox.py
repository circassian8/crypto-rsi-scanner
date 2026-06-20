"""Operator inbox for Event Alpha day-1 notification review."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class EventAlphaNotificationInboxItem:
    alert_id: str
    alert_key: str
    run_id: str
    tier: str
    playbook: str
    card_path: str
    sent: bool
    would_send: bool
    reviewed: bool
    reason: str


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
    would_send_without_feedback: tuple[EventAlphaNotificationInboxItem, ...]
    high_priority_unreviewed: tuple[EventAlphaNotificationInboxItem, ...]
    triggered_fade_unreviewed: tuple[EventAlphaNotificationInboxItem, ...]
    heartbeat_only_runs: tuple[dict[str, Any], ...]
    provider_degraded_runs: tuple[dict[str, Any], ...]


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
) -> EventAlphaNotificationInboxResult:
    """Join notification, alert, card, and feedback artifacts into review queues."""
    runs = [dict(row) for row in notification_runs if isinstance(row, Mapping)]
    alerts = [dict(row) for row in alert_rows if isinstance(row, Mapping)]
    feedback = [dict(row) for row in feedback_rows if isinstance(row, Mapping)]
    cards_dir = Path(research_cards_dir).expanduser()
    card_paths = _card_paths(cards_dir)
    reviewed_ids = _reviewed_ids(feedback)
    runs_by_id = {str(row.get("run_id") or ""): row for row in runs if row.get("run_id")}
    items = [
        _inbox_item(row, runs_by_id.get(str(row.get("run_id") or "")), card_paths, reviewed_ids)
        for row in alerts
    ]
    sent_without_feedback = tuple(item for item in items if item.sent and not item.reviewed)
    would_send_without_feedback = tuple(
        item for item in items
        if item.would_send and not item.sent and not item.reviewed
    )
    high_priority_unreviewed = tuple(
        item for item in items
        if not item.reviewed and _is_high_priority(item)
    )
    triggered_fade_unreviewed = tuple(
        item for item in items
        if not item.reviewed and _is_triggered_fade(item)
    )
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
        would_send_without_feedback=would_send_without_feedback,
        high_priority_unreviewed=high_priority_unreviewed,
        triggered_fade_unreviewed=triggered_fade_unreviewed,
        heartbeat_only_runs=tuple(row for row in runs if _heartbeat_only(row)),
        provider_degraded_runs=tuple(row for row in runs if _provider_degraded(row)),
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
        "",
    ]
    _append_item_section(lines, "sent notifications without feedback", result.sent_without_feedback, profile=result.profile)
    _append_item_section(lines, "would-send notifications without feedback", result.would_send_without_feedback, profile=result.profile)
    _append_item_section(lines, "high-priority cards not reviewed", result.high_priority_unreviewed, profile=result.profile)
    _append_item_section(lines, "triggered-fade cards not reviewed", result.triggered_fade_unreviewed, profile=result.profile)
    _append_run_section(lines, "heartbeat-only runs", result.heartbeat_only_runs)
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
            f"- alert_id={item.alert_id} tier={item.tier} playbook={item.playbook} "
            f"sent={_yes_no(item.sent)} would_send={_yes_no(item.would_send)}"
        )
        lines.append(f"  card: {item.card_path or 'not_written'}")
        lines.append(f"  run_id: {item.run_id or 'unknown'}")
        lines.append(f"  reason: {item.reason}")
        lines.append(f"  feedback_useful: make event-feedback-useful PROFILE={profile} FEEDBACK_TARGET='{item.alert_id}'")
        lines.append(f"  feedback_junk: make event-feedback-junk PROFILE={profile} FEEDBACK_TARGET='{item.alert_id}'")
    lines.append("")


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
) -> EventAlphaNotificationInboxItem:
    alert_key = str(alert.get("alert_key") or "")
    alert_id = str(alert.get("alert_id") or (f"ea:{alert_key}" if alert_key else alert.get("snapshot_id") or "unknown"))
    card_id = str(alert.get("card_id") or "")
    card_path = _path_for_card(alert_id, alert_key, card_id, card_paths)
    lane = _lane_for_alert(alert)
    due = _lane_count(run, "lane_counts_due", lane)
    sent = _lane_count(run, "lane_counts_sent", lane) > 0
    would_send = bool(due or (run and _int(run.get("would_send_count")) > 0))
    ids = _alert_ids(alert, alert_id, alert_key, card_id)
    reviewed = bool(ids & reviewed_ids)
    return EventAlphaNotificationInboxItem(
        alert_id=alert_id,
        alert_key=alert_key,
        run_id=str(alert.get("run_id") or (run or {}).get("run_id") or ""),
        tier=str(alert.get("tier") or "UNKNOWN"),
        playbook=str(alert.get("playbook_type") or alert.get("effective_playbook_type") or "unknown"),
        card_path=str(card_path) if card_path else "",
        sent=sent,
        would_send=would_send,
        reviewed=reviewed,
        reason=str(alert.get("route_reason") or alert.get("reason") or (run or {}).get("block_reason") or "review pending"),
    )


def _lane_for_alert(alert: Mapping[str, Any]) -> str:
    route = str(alert.get("route") or "").upper()
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
    for field in ("event_id", "asset_coin_id", "asset_symbol", "snapshot_id"):
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


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
