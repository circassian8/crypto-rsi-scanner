"""Rendering helpers for Event Alpha router reports and no-send digests."""

from __future__ import annotations

import html
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Iterable, Mapping

import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist


def format_router_report(result: object) -> str:
    rows = [
        "=" * 76,
        "EVENT ALPHA ROUTER REPORT (research-only; no sends, trades, or paper rows)",
        "=" * 76,
        f"state_path: {getattr(result, 'state_path')}",
        f"router_enabled: {str(getattr(result, 'enabled')).lower()}",
        f"rows_read: {getattr(result, 'rows_read')} · decisions: {len(result.decisions)} · alertable: {len(result.alertable_decisions)}",
    ]
    if not result.enabled:
        rows.append("disabled: set RSI_EVENT_ALPHA_ROUTER_ENABLED=1 for route decisions.")
    if not result.decisions:
        rows.append("")
        rows.append("No watchlist rows to route.")
        return "\n".join(rows)
    counts: dict[str, int] = {}
    for decision in result.decisions:
        counts[decision.route.value] = counts.get(decision.route.value, 0) + 1
    rows.append("routes: " + ", ".join(f"{route}={count}" for route, count in sorted(counts.items())))
    lane_counts: dict[str, int] = {}
    for decision in result.decisions:
        lane_counts[decision.lane.value] = lane_counts.get(decision.lane.value, 0) + 1
    rows.append("lanes: " + ", ".join(f"{lane}={count}" for lane, count in sorted(lane_counts.items())))
    rows.append("")
    for decision in result.decisions:
        rows.extend(_decision_report_lines(decision))
    return "\n".join(rows).rstrip()


def _decision_report_lines(decision: object) -> list[str]:
    entry = decision.entry
    components = entry.latest_score_components or {}
    rows = [
        f"{decision.route.value:<24} score={entry.latest_score:>3} high={entry.highest_score:>3} {entry.symbol}/{entry.coin_id}",
        f"  alert_id: {decision.alert_id} · card_id: {decision.card_id}",
        f"  event: {entry.latest_event_name}",
        f"  state: {entry.previous_state or 'new'} -> {event_watchlist.final_state_value(entry)} · "
        f"watchlist_alertable={str(entry.should_alert).lower()}",
    ]
    if entry.state_quality_capped:
        rows.append(
            "  state quality gate: "
            f"requested={entry.requested_state_before_quality_gate or entry.state} "
            f"final={event_watchlist.final_state_value(entry)} "
            f"block={entry.quality_state_block_reason or 'quality_state_capped'}"
        )
    rows.append(f"  playbook: {entry.latest_playbook_type or 'unknown'} action={entry.latest_playbook_action or 'store_only'}")
    if entry.relationship_type == "impact_hypothesis" and (
        components.get("opportunity_level") or components.get("opportunity_score_final")
    ):
        rows.append(
            "  opportunity: "
            f"level={components.get('opportunity_level') or 'unknown'} "
            f"score={components.get('opportunity_score_final') if components.get('opportunity_score_final') is not None else 'n/a'} "
            f"market={components.get('market_confirmation_level') or 'unknown'} "
            f"evidence={components.get('source_class') or 'unknown'}/{components.get('evidence_specificity') or 'unknown'}"
        )
    rows.extend(_quality_and_routing_lines(decision, components))
    rows.append(f"  route reason: {decision.reason}")
    rows.append(f"  lane: {decision.lane.value}")
    rows.append(f"  card: {decision.card_id}.md")
    rows.append(f"  feedback: make event-feedback-useful FEEDBACK_TARGET={decision.alert_id}")
    if entry.latest_llm_asset_role:
        rows.append(
            f"  llm: role={entry.latest_llm_asset_role} "
            f"conf={entry.latest_llm_confidence if entry.latest_llm_confidence is not None else 0.0:.2f}"
        )
    warnings = (*entry.warnings, *decision.warnings)
    if warnings:
        rows.append("  warnings: " + "; ".join(dict.fromkeys(warnings)))
    if entry.suppressed_reason:
        rows.append(f"  watchlist suppressed: {entry.suppressed_reason}")
    rows.append("")
    return rows


def _quality_and_routing_lines(decision: object, components: Mapping[str, object]) -> list[str]:
    rows: list[str] = []
    if decision.requested_route_before_quality_gate or decision.quality_gate_block_reason:
        rows.append(
            "  quality gate: "
            f"requested={decision.requested_route_before_quality_gate or decision.route.value} "
            f"final={decision.final_route_after_quality_gate or decision.route.value} "
            f"level={decision.opportunity_level or components.get('opportunity_level') or 'unknown'} "
            f"score={decision.opportunity_score_final if decision.opportunity_score_final is not None else components.get('opportunity_score_final', 'n/a')} "
            f"block={decision.quality_gate_block_reason or 'none'}"
        )
    if decision.routing_score_source or decision.routing_verdict_used:
        rows.append(
            "  routing score: "
            f"source={decision.routing_score_source or 'unknown'} "
            f"value={decision.routing_score_used if decision.routing_score_used is not None else 'n/a'} "
            f"verdict={decision.routing_verdict_used or 'unknown'}"
        )
    return rows


def format_routed_telegram_digest(
    decisions: Iterable[object],
    *,
    profile: str | None = None,
    card_path_by_alert_id: Mapping[str, object] | None = None,
    alertable_after_quality_gate: Callable[[object], bool],
    final_route_value: Callable[[object], str],
    is_validated_hypothesis_digest_entry: Callable[[object], bool],
) -> str:
    """Render router-approved Event Alpha escalations for Telegram."""
    keep = [decision for decision in decisions if alertable_after_quality_gate(decision)]
    card_paths = {str(key): value for key, value in (card_path_by_alert_id or {}).items()}
    lines = [
        "<b>Event Alpha routed research alerts</b>",
        "<i>Research-only / DAY-1 UNVALIDATED. Not a trade signal, paper trade, or execution.</i>",
        "Validation status: DAY-1 UNVALIDATED",
        "Trading action: NONE",
        "Review before acting.",
    ]
    if profile:
        lines.append(f"profile={_esc(profile)}")
    if not keep:
        lines.append("No router-approved escalations.")
        return "\n".join(lines)
    for decision in keep:
        lines.extend(
            _digest_decision_lines(
                decision,
                profile=profile,
                card_paths=card_paths,
                final_route_value=final_route_value,
                is_validated_hypothesis_digest_entry=is_validated_hypothesis_digest_entry,
            )
        )
    return "\n".join(lines)


def _digest_decision_lines(
    decision: object,
    *,
    profile: str | None,
    card_paths: Mapping[str, object],
    final_route_value: Callable[[object], str],
    is_validated_hypothesis_digest_entry: Callable[[object], bool],
) -> list[str]:
    entry = decision.entry
    is_validated_hypothesis = is_validated_hypothesis_digest_entry(entry)
    lines = [
        "",
        f"<b>{_esc(final_route_value(decision))}</b> score={entry.latest_score} <b>{_esc(entry.symbol)}</b>",
    ]
    if is_validated_hypothesis:
        lines.append("<b>Validated impact hypothesis</b>")
        lines.append("Catalyst link validated, but this is not a calibrated strategy.")
    lines.append(_esc(entry.latest_event_name or "unknown event"))
    lines.append(f"tier={_esc(entry.latest_tier or 'unknown')} route={_esc(decision.route.value)} lane={_esc(decision.lane.value)}")
    if profile:
        lines.append(f"profile={_esc(profile)} notification_lane={_esc(decision.lane.value)}")
    lines.append(
        f"state={_esc(event_watchlist.final_state_value(entry))} playbook={_esc(entry.latest_playbook_type or 'unknown')} "
        f"external_catalyst={_esc(entry.external_asset or 'unknown')}"
    )
    lines.extend(_digest_context_lines(decision))
    if is_validated_hypothesis:
        lines.append("operator_note=Research-only. Not a trade signal. Review the local card before acting.")
    lines.extend(_digest_identity_lines(decision, card_paths))
    return lines


def _digest_context_lines(decision: object) -> list[str]:
    entry = decision.entry
    lines = [_event_time_line(entry), "market=" + _esc(_market_summary(entry.latest_market_snapshot))]
    if entry.latest_rule_playbook_type and entry.latest_rule_playbook_type != entry.latest_playbook_type:
        lines.append(f"rule_playbook={_esc(entry.latest_rule_playbook_type)}")
    if entry.latest_llm_asset_role:
        conf = entry.latest_llm_confidence if entry.latest_llm_confidence is not None else 0.0
        lines.append(f"llm_role={_esc(entry.latest_llm_asset_role)} llm_confidence={conf:.2f}")
    else:
        lines.append("llm_role=none llm_confidence=n/a")
    lines.append(f"route_reason={_esc(decision.reason)}")
    return lines


def _digest_identity_lines(decision: object, card_paths: Mapping[str, object]) -> list[str]:
    lines = [f"alert_id={_esc(decision.alert_id)}", f"card_id={_esc(decision.card_id)}"]
    card_path = card_paths.get(decision.alert_id)
    lines.append(f"research_card={_esc(card_path)}" if card_path else "research_card=not_written")
    lines.append(f"feedback=make event-feedback-useful FEEDBACK_TARGET={_esc(decision.alert_id)}")
    warnings = tuple(dict.fromkeys((*decision.entry.warnings, *decision.warnings)))
    if warnings:
        lines.append("warnings=" + _esc("; ".join(warnings[:3])))
    return lines


def _esc(value: object) -> str:
    return html.escape(str(value), quote=False)


def _event_time_line(entry: event_watchlist.EventWatchlistEntry) -> str:
    event_time = entry.event_time or "unknown"
    parsed = _parse_iso(event_time)
    if parsed is None:
        return f"event_time={_esc(event_time)} countdown=unknown"
    hours = (parsed - datetime.now(timezone.utc)).total_seconds() / 3600.0
    countdown = f"T-{hours:.1f}h" if hours >= 0 else f"T+{abs(hours):.1f}h"
    return f"event_time={_esc(event_time)} countdown={_esc(countdown)}"


def _market_summary(snapshot: Mapping[str, object] | None) -> str:
    if not snapshot:
        return "no market confirmation snapshot"
    bits = [f"{key}={snapshot[key]}" for key in ("price", "return_24h", "return_72h", "volume_zscore_24h", "rsi_1d", "rsi_4h") if snapshot.get(key) not in (None, "")]
    return ", ".join(bits[:5]) if bits else "market snapshot present"


def _parse_iso(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
