"""Markdown research cards for routed Event Alpha candidates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
import re
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse

from ... import (
    event_artifact_paths,
    event_alpha_router,
    event_core_opportunities,
    event_core_opportunity_store,
    event_graph,
    event_llm_evidence_planner,
    event_market_units,
    event_opportunity_verdict,
    event_source_packs,
    event_source_registry,
    event_watchlist,
    event_watchlist_monitor,
)
from . import reason_text as event_alpha_reason_text


@dataclass(frozen=True)
class EventResearchCardResult:
    key: str
    markdown: str
    found: bool


@dataclass(frozen=True)
class EventResearchCardWriteResult:
    out_dir: Path
    cards_written: int
    index_path: Path
    card_paths: tuple[Path, ...]


CARD_INDEX_GROUPS = (
    "Early Long Research Cards",
    "Confirmed Long Research Cards",
    "Fade / Short-Review Cards",
    "Risk Only Cards",
    "Unconfirmed Research Cards",
    "Core Opportunity Cards",
    "Near-Miss Cards",
    "Local-Only / Quality-Capped Cards",
    "Diagnostic / Source-Noise / Control Cards",
    "Legacy Cards",
)


def card_index_group(path: Path, *, card_groups: Mapping[Path | str, str] | None = None) -> str:
    """Return the operator-facing research-card group for an existing card file."""
    return _card_index_group(Path(path), card_groups=card_groups)


def card_group_for_opportunity_lane(value: object) -> str | None:
    """Return the lane-first card group for an Event Alpha opportunity lane."""
    return _lane_card_group(value)


def card_index_group_map(paths: Iterable[str | Path]) -> dict[Path, str]:
    """Return card groups, preferring the local index.md when available."""
    cards = [Path(path) for path in paths]
    out: dict[Path, str] = {}
    for index_path in _candidate_index_paths(cards):
        out.update(_parse_index_groups(index_path))
    for path in cards:
        if path.name == "index.md":
            continue
        out.setdefault(path, _card_index_group(path))
    return out


def collapse_card_paths_for_group(
    paths: Iterable[str | Path],
    *,
    group_name: str | None = None,
    card_groups: Mapping[Path | str, str] | None = None,
) -> tuple[tuple[Path, int], ...]:
    """Collapse related card paths into primary card plus hidden count."""
    grouped: dict[tuple[str, str, str, str], list[Path]] = {}
    for value in paths:
        path = Path(value)
        key = _card_family_key(path, group_name=group_name, card_groups=card_groups)
        grouped.setdefault(key, []).append(path)
    collapsed: list[tuple[Path, int]] = []
    for items in grouped.values():
        ordered = sorted(items, key=_card_primary_sort_key)
        collapsed.append((ordered[0], max(0, len(ordered) - 1)))
    return tuple(sorted(collapsed, key=lambda item: item[0].name))


def render_research_card(
    key: str,
    *,
    watchlist_entries: Iterable[event_watchlist.EventWatchlistEntry] = (),
    alert_rows: Iterable[Mapping[str, Any]] = (),
    route_decisions: Iterable[event_alpha_router.EventAlphaRouteDecision] = (),
    clusters: Iterable[event_graph.EventCluster] = (),
    monitor_rows: Iterable[event_watchlist_monitor.EventWatchlistMonitorRow | Mapping[str, Any]] = (),
    feedback_rows: Iterable[Mapping[str, Any]] = (),
    outcome_rows: Iterable[Mapping[str, Any]] = (),
    generated_at: datetime | None = None,
    lineage_context: Mapping[str, Any] | None = None,
    card_path: str | Path | None = None,
) -> EventResearchCardResult:
    """Render one Markdown card from local research artifacts."""
    clean_key = str(key or "").strip()
    entry_rows = list(watchlist_entries)
    alert_row_list = list(alert_rows)
    decision_rows = list(route_decisions)
    monitor_row_list = list(monitor_rows)
    feedback_row_list = list(feedback_rows)
    outcome_row_list = list(outcome_rows)
    entry = _find_entry(clean_key, entry_rows)
    alert = _find_alert(clean_key, alert_row_list)
    decision = _find_decision(clean_key, decision_rows)
    core_rows = [row for row in alert_row_list if isinstance(row, Mapping) and row.get("row_type") == "event_core_opportunity"]
    core_view = event_core_opportunity_store.canonical_core_opportunity_view_from_rows(
        clean_key,
        core_rows=core_rows,
        supporting_rows=[*alert_row_list, *decision_rows, *entry_rows],
        alert_rows=alert_row_list,
        feedback_rows=feedback_row_list,
        card_paths=[card_path] if card_path is not None else (),
    ) if core_rows else None
    core = (
        core_view.core_opportunity
        if core_view is not None and core_view.found
        else _find_card_core_opportunity(clean_key, entry, alert, decision, decision_rows)
    )
    if core is not None:
        if entry is None or (alert is not None and alert.get("row_type") == "event_core_opportunity"):
            entry = _entry_from_core_opportunity(core)
        alert = _canonical_card_alert(core, core_view.canonical_core_row if core_view is not None and core_view.canonical_core_row else alert)
    cluster = _find_cluster(clean_key, list(clusters), entry, alert)
    monitor_row = _find_monitor_row(clean_key, monitor_row_list, entry, alert)
    feedback = _matching_rows(clean_key, feedback_row_list, entry, alert)
    outcome = _find_outcome(clean_key, outcome_row_list, entry, alert) or alert
    if entry is None and alert is None:
        return EventResearchCardResult(
            key=clean_key,
            markdown=f"# Event Research Card\n\nNo watchlist or alert snapshot matched `{clean_key}`.",
            found=False,
        )
    playbook = _value(entry, alert, "latest_playbook_type", "playbook_type") or "unknown"
    symbol = _value(entry, alert, "symbol", "asset_symbol") or "UNKNOWN"
    coin_id = _value(entry, alert, "coin_id", "asset_coin_id") or "unknown"
    canonical_asset_id = _value(entry, alert, "canonical_asset_id", "canonical_asset_id")
    event_name = _value(entry, alert, "latest_event_name", "event_name") or "unknown event"
    tier = _value(entry, alert, "latest_tier", "tier") or "unknown"
    state = event_watchlist.final_state_value(entry) if entry is not None else str(alert.get("final_state_after_quality_gate") or alert.get("state") or "snapshot")
    generated_iso = (generated_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    summary_identity_lines = [f"- Asset: {symbol}/{coin_id}"]
    if canonical_asset_id:
        summary_identity_lines.append(f"- Canonical asset: {canonical_asset_id}")
    lines = [
        f"# {symbol} Event Research Card",
        "",
        "Research artifact only. Not a trade signal, paper trade, live RSI signal, or execution.",
        "",
        "## Summary",
        *summary_identity_lines,
        f"- Event: {event_name}",
        f"- State / alert tier: {state} / {tier}",
        f"- Playbook: {playbook}",
    ]
    lane_lines = _opportunity_lane_lines(entry, alert)
    if lane_lines:
        lines.extend(["", "## Opportunity Lane"])
        lines.extend(lane_lines)
    analyst_lines = _analyst_summary_lines(entry, alert)
    if analyst_lines:
        lines.extend(["", "## Analyst Summary"])
        lines.extend(analyst_lines)
    if decision is not None:
        lines.append(f"- Route: {event_alpha_router.final_route_value(decision)} ({decision.reason})")
        if decision.quality_gate_block_reason or decision.requested_route_before_quality_gate:
            lines.append(
                "- Quality gate: "
                f"{decision.requested_route_before_quality_gate or decision.route.value} -> "
                f"{event_alpha_router.final_route_value(decision)}"
                + (
                    f" ({decision.quality_gate_block_reason})"
                    if decision.quality_gate_block_reason
                    else " (allowed)"
                )
            )
    lines.extend(["", "## Artifact Lineage"])
    lines.extend(_lineage_lines(
        clean_key,
        entry=entry,
        alert=alert,
        decision=decision,
        core=core,
        generated_iso=generated_iso,
        lineage_context=lineage_context,
        card_path=card_path,
    ))
    lines.extend([
        "",
        "## Cluster Context",
    ])
    lines.extend(_cluster_lines(cluster))
    lines.extend([
        "",
        "## Playbook",
        _playbook_copy(playbook, alert, entry),
        "",
        "## External Catalyst",
        f"- External asset: {_value(entry, alert, 'external_asset', 'external_asset') or 'unknown'}",
        f"- Event time: {_value(entry, alert, 'event_time', 'event_time') or 'unknown'}",
        "",
        "## Evidence Sources",
    ])
    lines.extend(_source_lines(entry, alert))
    official_exchange_lines = _official_exchange_evidence_lines(entry, alert)
    if official_exchange_lines:
        lines.extend(["", "## Official Exchange Evidence"])
        lines.extend(official_exchange_lines)
    scheduled_lines = _scheduled_catalyst_lines(entry, alert)
    if scheduled_lines:
        lines.extend(["", "## Scheduled Catalyst / Unlock Details"])
        lines.extend(scheduled_lines)
    derivatives_lines = _derivatives_crowding_lines(entry, alert)
    if derivatives_lines:
        lines.extend(["", "## Derivatives / Crowding"])
        lines.extend(derivatives_lines)
    lines.extend(["", "## Source Coverage / Evidence Acquisition"])
    lines.extend(_source_acquisition_lines(entry, alert, card_path=card_path, lineage_context=lineage_context))
    lines.extend([
        "",
        "## Accepted / Rejected Asset Links",
        f"- Relationship: {_value(entry, alert, 'relationship_type', 'relationship_type') or 'unknown'}",
        f"- Rule playbook: {_value(entry, alert, 'latest_rule_playbook_type', 'rule_playbook_type') or 'unknown'}",
        f"- Effective playbook: {_value(entry, alert, 'latest_effective_playbook_type', 'playbook_type') or playbook}",
    ])
    lines.extend(["", "## Quality Gate Result"])
    lines.extend(_quality_gate_lines(entry, alert, decision))
    if entry is not None and event_watchlist.state_is_quality_capped(entry):
        _, state_block_reason = event_watchlist.quality_cap_watchlist_state(
            event_watchlist.requested_state_value(entry),
            entry.latest_score_components,
        )
        lines.extend([
            "",
            "## Lifecycle State Gate",
            "- Local-only after quality/state gate.",
            (
                f"- Requested {event_watchlist.requested_state_value(entry)} blocked because "
                f"{entry.quality_state_block_reason or state_block_reason or 'quality verdict did not allow active watchlist state'}."
            ),
            "- What would upgrade this candidate: " + (
                event_alpha_reason_text.humanize_event_alpha_reasons(entry.upgrade_requirements, limit=3)
                if entry.upgrade_requirements
                else "recompute quality with validated impact path, specific evidence, and market confirmation"
            ),
        ])
    hypothesis_lines = _impact_hypothesis_lines(entry)
    if hypothesis_lines:
        lines.extend(["", "## Impact Hypothesis Context"])
        lines.extend(hypothesis_lines)
    lines.extend([
        "",
        "## LLM Interpretation",
        f"- Role: {_value(entry, alert, 'latest_llm_asset_role', 'llm_asset_role') or 'none'}",
        f"- Confidence: {_value(entry, alert, 'latest_llm_confidence', 'llm_confidence') or 'n/a'}",
        f"- Reason: {str(alert.get('llm_reason') or alert.get('llm_adjustment_reason') or 'n/a') if alert else 'n/a'}",
        "",
        "## Market Confirmation",
    ])
    lines.extend(_market_lines(entry, alert))
    lines.extend([
        "",
        "## Derivatives / Supply / Liquidity",
    ])
    lines.extend(_derivatives_supply_liquidity_lines(entry, alert))
    lines.extend(["", "## Latest Monitor Update"])
    lines.extend(_monitor_lines(monitor_row))
    lines.extend([
        "",
        "## Lifecycle Timeline",
    ])
    lines.extend(_lifecycle_lines(entry, alert, monitor_row, feedback, outcome))
    lines.extend([
        "",
        "## Why This Matters",
        _why_it_matters(playbook, entry, alert),
        "",
        "## What To Verify",
    ])
    lines.extend(_verify_lines(alert, playbook))
    lines.extend([
        "",
        "## Research Review Checklist",
    ])
    lines.extend(_trade_readiness_lines(entry, alert, playbook, state))
    lines.extend([
        "",
        "## Invalidation / Why Wrong",
        f"- {_value(None, alert, '', 'playbook_invalidation') or _default_invalidation(playbook, alert, entry)}",
        "",
        "## Alert History",
    ])
    lines.extend(_history_lines(entry))
    warnings = _warnings(entry, alert, decision)
    if warnings:
        lines.extend(["", "## Warnings / Source-Noise Rejections"])
        lines.extend(f"- {warning}" for warning in warnings)
    lines.extend(["", "## Outcome Tracking"])
    lines.extend(_outcome_tracking_lines(outcome))
    return EventResearchCardResult(key=clean_key, markdown="\n".join(lines).rstrip() + "\n", found=True)


def render_selected_cards(
    *,
    watchlist_entries: Iterable[event_watchlist.EventWatchlistEntry],
    alert_rows: Iterable[Mapping[str, Any]] = (),
    route_decisions: Iterable[event_alpha_router.EventAlphaRouteDecision] = (),
    clusters: Iterable[event_graph.EventCluster] = (),
    monitor_rows: Iterable[event_watchlist_monitor.EventWatchlistMonitorRow | Mapping[str, Any]] = (),
    feedback_rows: Iterable[Mapping[str, Any]] = (),
    outcome_rows: Iterable[Mapping[str, Any]] = (),
    limit: int = 10,
) -> str:
    cluster_rows = list(clusters)
    monitor = list(monitor_rows)
    entries = [
        entry for entry in watchlist_entries
        if event_watchlist.final_state_value(entry) in {
            event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
            event_watchlist.EventWatchlistState.TRIGGERED_FADE.value,
            event_watchlist.EventWatchlistState.WATCHLIST.value,
        } and not event_watchlist.state_is_quality_capped(entry)
    ][: max(1, limit)]
    if not entries:
        return "# Event Research Cards\n\nNo selected watchlist entries found.\n"
    cards = [
        render_research_card(
            entry.key,
            watchlist_entries=watchlist_entries,
            alert_rows=alert_rows,
            route_decisions=route_decisions,
            clusters=cluster_rows,
            monitor_rows=monitor,
            feedback_rows=feedback_rows,
            outcome_rows=outcome_rows,
        ).markdown
        for entry in entries
    ]
    return "\n---\n\n".join(cards)


def write_research_cards(
    out_dir: str | Path,
    *,
    watchlist_entries: Iterable[event_watchlist.EventWatchlistEntry],
    alert_rows: Iterable[Mapping[str, Any]] = (),
    route_decisions: Iterable[event_alpha_router.EventAlphaRouteDecision] = (),
    clusters: Iterable[event_graph.EventCluster] = (),
    monitor_rows: Iterable[event_watchlist_monitor.EventWatchlistMonitorRow | Mapping[str, Any]] = (),
    feedback_rows: Iterable[Mapping[str, Any]] = (),
    outcome_rows: Iterable[Mapping[str, Any]] = (),
    include_all_alertable: bool = True,
    selected_tiers: Iterable[str] | None = None,
    limit: int = 25,
    now: datetime | None = None,
    lineage_context: Mapping[str, Any] | None = None,
) -> EventResearchCardWriteResult:
    """Write selected Markdown cards and an index under a local artifact dir."""
    target = Path(out_dir).expanduser()
    target.mkdir(parents=True, exist_ok=True)
    for stale_card in target.glob("card_*.md"):
        if stale_card.is_file():
            stale_card.unlink()
    observed = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    alert_row_list = list(alert_rows)
    entries = _selected_entries(
        list(watchlist_entries),
        list(route_decisions),
        alert_rows=alert_row_list,
        include_all_alertable=include_all_alertable,
        selected_tiers=selected_tiers,
    )
    card_paths: list[Path] = []
    card_groups: dict[Path, str] = {}
    for entry in entries[: max(1, limit)]:
        path = target / _card_filename(entry)
        card = render_research_card(
            entry.key,
            watchlist_entries=entries,
            alert_rows=alert_row_list,
            route_decisions=route_decisions,
            clusters=clusters,
            monitor_rows=monitor_rows,
            feedback_rows=feedback_rows,
            outcome_rows=outcome_rows,
            generated_at=observed,
            lineage_context=lineage_context,
            card_path=path,
        )
        if not card.found:
            continue
        path.write_text(_strip_sensitive(card.markdown), encoding="utf-8")
        card_paths.append(path)
        rendered_group = _card_index_group_for_text(card.markdown.casefold())
        card_groups[path] = rendered_group or _card_index_group_for_entry(entry, route_decisions)
    index = _render_index(card_paths, observed, card_groups=card_groups)
    index_path = target / "index.md"
    index_path.write_text(index, encoding="utf-8")
    return EventResearchCardWriteResult(
        out_dir=target,
        cards_written=len(card_paths),
        index_path=index_path,
        card_paths=tuple(card_paths),
    )


def format_card_write_result(result: EventResearchCardWriteResult) -> str:
    return "\n".join([
        "=" * 76,
        "EVENT RESEARCH CARDS WRITTEN (research artifact only)",
        "=" * 76,
        f"out_dir: {result.out_dir}",
        f"cards_written: {result.cards_written}",
        f"index: {result.index_path}",
        *(f"- {path}" for path in result.card_paths[:20]),
        "No live RSI alerts, paper trades, live DB rows, or execution were changed.",
    ])


def _lineage_lines(
    key: str,
    *,
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
    decision: event_alpha_router.EventAlphaRouteDecision | None,
    core: event_core_opportunities.CoreOpportunity | None,
    generated_iso: str,
    lineage_context: Mapping[str, Any] | None = None,
    card_path: str | Path | None = None,
) -> list[str]:
    run_id = _lineage_value("run_id", entry=entry, alert=alert, decision=decision, core=core, lineage_context=lineage_context)
    profile = _lineage_value("profile", entry=entry, alert=alert, decision=decision, core=core, lineage_context=lineage_context)
    namespace = _lineage_value("artifact_namespace", "namespace", entry=entry, alert=alert, decision=decision, core=core, lineage_context=lineage_context)
    missing = not (run_id and profile and namespace)
    legacy_label = "legacy_lineage_missing" if missing else None
    watchlist_key = str(getattr(entry, "key", "") or _lineage_value("key", "alert_key", entry=entry, alert=alert, decision=decision, core=core, lineage_context=lineage_context) or key)
    hypothesis_id = _lineage_value("hypothesis_id", entry=entry, alert=alert, decision=decision, core=core, lineage_context=lineage_context)
    incident_id = _lineage_value("incident_id", entry=entry, alert=alert, decision=decision, core=core, lineage_context=lineage_context)
    alert_id = _lineage_value("alert_id", entry=entry, alert=alert, decision=decision, core=core, lineage_context=lineage_context)
    snapshot_id = _lineage_value("snapshot_id", entry=entry, alert=alert, decision=decision, core=core, lineage_context=lineage_context)
    raw_ids = _lineage_values("source_raw_ids", "raw_ids", entry=entry, alert=alert, decision=decision, core=core, lineage_context=lineage_context)
    event_ids = _lineage_values("source_event_ids", "event_ids", "event_id", entry=entry, alert=alert, decision=decision, core=core, lineage_context=lineage_context)
    core_id = (core.core_opportunity_id if core is not None else _lineage_value("core_opportunity_id", entry=entry, alert=alert, decision=decision, core=core, lineage_context=lineage_context))
    source_row_type = _lineage_value("source_row_type", entry=entry, alert=alert, decision=decision, core=core, lineage_context=lineage_context)
    integrated_candidate_id = _lineage_value("integrated_candidate_id", entry=entry, alert=alert, decision=decision, core=core, lineage_context=lineage_context)
    feedback_target, feedback_target_type = _feedback_target_for_card(
        core_id=core_id,
        alert_id=alert_id,
        hypothesis_id=hypothesis_id,
        incident_id=incident_id,
        watchlist_key=watchlist_key,
        card_path=card_path,
    )
    card_path_label = event_artifact_paths.artifact_display_path(card_path)
    profile_for_command = profile or "default"
    return [
        f"- Generated at: {generated_iso}",
        f"- Lineage status: {legacy_label or 'current'}",
        f"- legacy_lineage_missing: {str(bool(legacy_label)).lower()}",
        f"- Run ID: {run_id or legacy_label}",
        f"- Profile: {profile or legacy_label}",
        f"- Namespace: {namespace or legacy_label}",
        f"- Incident ID: {incident_id or 'none'}",
        f"- Hypothesis ID: {hypothesis_id or 'none'}",
        f"- Watchlist key: {watchlist_key}",
        f"- Core opportunity ID: {core_id or 'none'}",
        f"- Alert ID: {alert_id or 'none'}",
        f"- Snapshot ID: {snapshot_id or 'none'}",
        f"- Source row type: {source_row_type or 'none'}",
        f"- Integrated candidate ID: {integrated_candidate_id or 'none'}",
        f"- Source raw/event IDs: raw={_list_label(raw_ids)} events={_list_label(event_ids)}",
        f"- Card path: {card_path_label}",
        f"- Feedback target: {feedback_target}",
        f"- Feedback target type: {feedback_target_type}",
        f"- Feedback command useful: make event-feedback-useful PROFILE={profile_for_command} FEEDBACK_TARGET='{feedback_target}'",
        f"- Feedback command junk: make event-feedback-junk PROFILE={profile_for_command} FEEDBACK_TARGET='{feedback_target}'",
        f"- Feedback command watch: make event-feedback-watch PROFILE={profile_for_command} FEEDBACK_TARGET='{feedback_target}'",
        f"- Feedback command ignore: python3 main.py --event-feedback-ignore '{feedback_target}' --event-alpha-profile {profile_for_command}",
        f"- Cluster ID: {_value(entry, alert, 'cluster_id', 'cluster_id') or _lineage_value('cluster_id', entry=entry, alert=alert, decision=decision, core=core, lineage_context=lineage_context) or 'unknown'}",
    ]


def card_feedback_target(path: str | Path) -> str | None:
    """Return the feedback target embedded in a research card, if any."""
    p = Path(path)
    if not p.exists() or p.name == "index.md":
        return None
    text = p.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"^- Feedback target:\s*(.+?)\s*$", text, flags=re.MULTILINE)
    if not match:
        return None
    target = match.group(1).strip()
    return target if target and target.lower() != "none" else None


def card_core_opportunity_id(path: str | Path) -> str | None:
    """Return the embedded core opportunity id from a research card, if present."""
    p = Path(path)
    if not p.exists() or p.name == "index.md":
        return None
    text = p.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"^- Core opportunity ID:\s*(.+?)\s*$", text, flags=re.MULTILINE)
    if not match:
        return None
    value = match.group(1).strip()
    return value if value and value.lower() != "none" else None


def card_has_current_lineage(path: str | Path) -> bool:
    p = Path(path)
    if not p.exists() or p.name == "index.md":
        return False
    text = p.read_text(encoding="utf-8", errors="replace")
    required = ("- Run ID: ", "- Profile: ", "- Namespace: ", "- Generated at: ")
    if not all(token in text for token in required):
        return False
    return not any(
        marker in text
        for marker in (
            "Lineage status: legacy_lineage_missing",
            "legacy_lineage_missing: true",
            "Run ID: legacy_lineage_missing",
            "Profile: legacy_lineage_missing",
            "Namespace: legacy_lineage_missing",
        )
    )


def _feedback_target_for_card(
    *,
    core_id: str | None,
    alert_id: str | None,
    hypothesis_id: str | None,
    incident_id: str | None,
    watchlist_key: str | None,
    card_path: str | Path | None,
) -> tuple[str, str]:
    for target_type, value in (
        ("core_opportunity_id", core_id),
        ("alert_id", alert_id),
        ("hypothesis_id", hypothesis_id),
        ("incident_id", incident_id),
        ("watchlist_key", watchlist_key),
        ("card_path", str(card_path) if card_path is not None else None),
    ):
        text = str(value or "").strip()
        if text and text.lower() != "none":
            return text, target_type
    return "none", "none"


def _find_card_core_opportunity(
    key: str,
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
    decision: event_alpha_router.EventAlphaRouteDecision | None,
    decisions: Iterable[event_alpha_router.EventAlphaRouteDecision],
) -> event_core_opportunities.CoreOpportunity | None:
    rows: list[Any] = []
    if decision is not None:
        rows.append(decision)
    if entry is not None:
        rows.append(entry)
    if alert is not None:
        rows.append(alert)
    rows.extend(decisions)
    for opportunity in event_core_opportunities.aggregate_core_opportunities(rows):
        identifiers = {
            opportunity.core_opportunity_id,
            opportunity.symbol,
            opportunity.coin_id,
            opportunity.incident_id or "",
            str(opportunity.primary_row.get("key") or ""),
            str(opportunity.primary_row.get("alert_key") or ""),
            str(opportunity.primary_row.get("hypothesis_id") or ""),
        }
        identifiers.update(str(value) for value in opportunity.supporting_hypothesis_ids)
        if key in identifiers or key.lower() in {value.lower() for value in identifiers if value}:
            return opportunity
    return None


def _lineage_value(
    *keys: str,
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
    decision: event_alpha_router.EventAlphaRouteDecision | None,
    core: event_core_opportunities.CoreOpportunity | None,
    lineage_context: Mapping[str, Any] | None = None,
) -> str | None:
    for mapping in _lineage_mappings(entry=entry, alert=alert, decision=decision, core=core, lineage_context=lineage_context):
        for key in keys:
            value = mapping.get(key)
            if value not in (None, "", [], {}, ()):
                return str(value)
    return None


def _lineage_values(
    *keys: str,
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
    decision: event_alpha_router.EventAlphaRouteDecision | None,
    core: event_core_opportunities.CoreOpportunity | None,
    lineage_context: Mapping[str, Any] | None = None,
) -> tuple[str, ...]:
    values: list[str] = []
    for mapping in _lineage_mappings(entry=entry, alert=alert, decision=decision, core=core, lineage_context=lineage_context):
        for key in keys:
            raw = mapping.get(key)
            if raw in (None, "", [], {}, ()):
                continue
            if isinstance(raw, str):
                values.append(raw)
            elif isinstance(raw, Mapping):
                values.extend(str(item) for item in raw.values() if str(item or ""))
            elif isinstance(raw, Iterable):
                values.extend(str(item) for item in raw if str(item or ""))
            else:
                values.append(str(raw))
    return tuple(dict.fromkeys(values))


def _lineage_mappings(
    *,
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
    decision: event_alpha_router.EventAlphaRouteDecision | None,
    core: event_core_opportunities.CoreOpportunity | None,
    lineage_context: Mapping[str, Any] | None = None,
) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    if alert is not None:
        rows.append(alert)
        components = alert.get("score_components")
        if isinstance(components, Mapping):
            rows.append(components)
    if decision is not None:
        rows.append({
            "alert_id": decision.alert_id,
            "card_id": decision.card_id,
            "route": decision.route.value,
        })
        rows.append(getattr(decision.entry, "__dict__", {}) or {})
        rows.append(decision.entry.latest_score_components or {})
    if entry is not None:
        rows.append(getattr(entry, "__dict__", {}) or {})
        rows.append(entry.latest_score_components or {})
    if core is not None:
        rows.append({
            "core_opportunity_id": core.core_opportunity_id,
            "incident_id": core.incident_id,
        })
        rows.append(core.primary_row)
        components = core.primary_row.get("latest_score_components") or core.primary_row.get("score_components")
        if isinstance(components, Mapping):
            rows.append(components)
    if lineage_context is not None:
        rows.append(lineage_context)
    return tuple(rows)


def _list_label(values: Iterable[str]) -> str:
    rows = [str(value) for value in values if str(value or "")]
    if not rows:
        return "none"
    return ", ".join(rows[:6]) + (f", +{len(rows) - 6} more" if len(rows) > 6 else "")


def _find_entry(key: str, entries: list[event_watchlist.EventWatchlistEntry]) -> event_watchlist.EventWatchlistEntry | None:
    clean_key = key[3:] if key.startswith("ea:") else key
    if clean_key.startswith("card_"):
        clean_key = clean_key[5:]
    key_l = clean_key.lower()
    matches = [
        entry for entry in entries
        if clean_key in {entry.key, entry.event_id}
        or key_l in {entry.symbol.lower(), entry.coin_id.lower()}
    ]
    return matches[0] if matches else None


def _selected_entries(
    entries: list[event_watchlist.EventWatchlistEntry],
    decisions: list[event_alpha_router.EventAlphaRouteDecision],
    *,
    alert_rows: Iterable[Mapping[str, Any]] = (),
    include_all_alertable: bool,
    selected_tiers: Iterable[str] | None,
) -> list[event_watchlist.EventWatchlistEntry]:
    selected_by_key: dict[str, event_watchlist.EventWatchlistEntry] = {}
    all_by_key = {entry.key: entry for entry in entries}
    alert_row_list = list(alert_rows)
    stored_core_rows = [
        dict(row) for row in alert_row_list
        if isinstance(row, Mapping) and row.get("row_type") == "event_core_opportunity"
    ]
    if stored_core_rows:
        ordered: list[event_watchlist.EventWatchlistEntry] = []
        seen_core: set[str] = set()
        for opportunity in event_core_opportunities.visible_core_opportunities(stored_core_rows):
            if opportunity.core_opportunity_id in seen_core:
                continue
            ordered.append(_entry_from_core_opportunity(opportunity))
            seen_core.add(opportunity.core_opportunity_id)
        for row in stored_core_rows:
            core_id = str(row.get("core_opportunity_id") or "").strip()
            if not core_id or core_id in seen_core:
                continue
            fallback = event_core_opportunities.aggregate_core_opportunities([row])
            if not fallback:
                continue
            ordered.append(_entry_from_core_opportunity(fallback[0]))
            seen_core.add(core_id)
        if ordered:
            return ordered
    states = set(selected_tiers or {
        event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        event_watchlist.EventWatchlistState.TRIGGERED_FADE.value,
        event_watchlist.EventWatchlistState.WATCHLIST.value,
        "HIGH_PRIORITY_WATCH",
    })
    for entry in entries:
        if (
            event_watchlist.final_state_value(entry) in states
            or entry.latest_tier in states
        ) and (
            not event_watchlist.state_is_quality_capped(entry)
            or event_watchlist.final_state_value(entry) in {
                event_watchlist.EventWatchlistState.WATCHLIST.value,
                event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
                event_watchlist.EventWatchlistState.TRIGGERED_FADE.value,
            }
        ):
            selected_by_key[entry.key] = entry
    if include_all_alertable:
        for decision in decisions:
            if event_alpha_router.alertable_after_quality_gate(decision):
                selected_by_key[decision.entry.key] = decision.entry
    core_rows = [*decisions, *entries, *alert_row_list]
    visible_core = event_core_opportunities.visible_core_opportunities(core_rows)
    if visible_core:
        ordered: list[event_watchlist.EventWatchlistEntry] = []
        seen_core: set[str] = set()
        for opportunity in visible_core:
            if opportunity.core_opportunity_id in seen_core:
                continue
            entry = _entry_for_core_opportunity(opportunity, all_by_key)
            if entry is None:
                continue
            selected_by_key.setdefault(entry.key, entry)
            ordered.append(entry)
            seen_core.add(opportunity.core_opportunity_id)
            if len(ordered) >= max(len(visible_core), 1):
                break
        for entry in selected_by_key.values():
            if entry.key not in {item.key for item in ordered} and not event_core_opportunities.row_is_diagnostic(entry):
                ordered.append(entry)
        if ordered:
            return ordered
    if selected_by_key:
        core = event_core_opportunities.aggregate_core_opportunities([*decisions, *selected_by_key.values()])
        if core:
            ordered: list[event_watchlist.EventWatchlistEntry] = []
            for opportunity in core:
                key = str(opportunity.primary_row.get("key") or "")
                entry = selected_by_key.get(key)
                if entry is not None and entry.key not in {item.key for item in ordered}:
                    ordered.append(entry)
            for entry in selected_by_key.values():
                if entry.key not in {item.key for item in ordered} and not event_core_opportunities.row_is_diagnostic(entry):
                    ordered.append(entry)
            return ordered
    return sorted(
        selected_by_key.values(),
        key=lambda entry: (entry.last_seen_at, entry.latest_score, entry.symbol),
        reverse=True,
    )


def _entry_for_core_opportunity(
    opportunity: event_core_opportunities.CoreOpportunity,
    entries_by_key: Mapping[str, event_watchlist.EventWatchlistEntry],
) -> event_watchlist.EventWatchlistEntry | None:
    for key in event_core_opportunities.row_key_candidates_for_opportunity(opportunity):
        entry = entries_by_key.get(key)
        if entry is not None and _entry_matches_core_identity(entry, opportunity):
            return entry
    symbol = opportunity.symbol.upper()
    coin = opportunity.coin_id.casefold()
    for entry in entries_by_key.values():
        if (
            (symbol and entry.symbol.upper() == symbol)
            or (coin and entry.coin_id.casefold() == coin)
        ) and _entry_matches_core_identity(entry, opportunity):
            return entry
    return _entry_from_core_opportunity(opportunity)


def _entry_matches_core_identity(
    entry: event_watchlist.EventWatchlistEntry,
    opportunity: event_core_opportunities.CoreOpportunity,
) -> bool:
    symbol_match = bool(opportunity.symbol and entry.symbol.upper() == opportunity.symbol.upper())
    coin_match = bool(opportunity.coin_id and entry.coin_id.casefold() == opportunity.coin_id.casefold())
    if not (symbol_match or coin_match):
        return False
    if opportunity.supporting_hypothesis_ids:
        entry_hypothesis_ids = {
            str(value or "")
            for value in (
                entry.hypothesis_id,
                entry.latest_score_components.get("hypothesis_id") if isinstance(entry.latest_score_components, Mapping) else None,
            )
            if str(value or "")
        }
        if not entry_hypothesis_ids.intersection(opportunity.supporting_hypothesis_ids):
            return False
    if event_core_opportunities.row_is_diagnostic(entry):
        return opportunity.primary_impact_path in {
            "generic_cooccurrence_only",
            "insufficient_data",
            "source_noise_control",
        } or opportunity.candidate_role in {"unknown", "unknown_with_reason", "source_noise"}
    return True


def _entry_from_core_opportunity(
    opportunity: event_core_opportunities.CoreOpportunity,
) -> event_watchlist.EventWatchlistEntry:
    row = opportunity.primary_row
    observed = _first_text(row, "last_seen_at", "observed_at", "updated_at", "created_at") or datetime.now(timezone.utc).isoformat()
    final_state = (
        opportunity.final_state_after_quality_gate
        or _first_text(row, "final_state_after_quality_gate", "state")
        or event_watchlist.EventWatchlistState.RADAR.value
    )
    components = _core_score_components(opportunity)
    latest_score = int(round(_float_value(opportunity.opportunity_score_final) or _float_value(row.get("latest_score")) or _float_value(row.get("score")) or 0.0))
    return event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_card_synthetic",
        key=_first_text(row, "key", "alert_key", "watchlist_key") or opportunity.core_opportunity_id,
        cluster_id=_first_text(row, "cluster_id") or opportunity.incident_id,
        event_id=_first_text(row, "event_id", "hypothesis_id", "alert_id") or opportunity.core_opportunity_id,
        coin_id=opportunity.coin_id or _first_text(row, "coin_id", "validated_coin_id") or "unknown",
        symbol=opportunity.symbol or _first_text(row, "symbol", "validated_symbol") or "UNKNOWN",
        relationship_type=opportunity.primary_impact_path or _first_text(row, "relationship_type", "effective_playbook_type") or "event_alpha",
        external_asset=_first_text(row, "external_asset", "external_catalyst", "external_asset_name") or opportunity.canonical_incident_name,
        event_time=_first_text(row, "event_time"),
        state=final_state,
        previous_state=_first_text(row, "previous_state"),
        first_seen_at=_first_text(row, "first_seen_at") or observed,
        last_seen_at=observed,
        incident_id=opportunity.incident_id or _first_text(row, "incident_id"),
        hypothesis_id=_first_text(row, "hypothesis_id"),
        incident_canonical_name=opportunity.canonical_incident_name or _first_text(row, "incident_canonical_name"),
        requested_state_before_quality_gate=_first_text(row, "requested_state_before_quality_gate", "state"),
        final_state_after_quality_gate=final_state,
        quality_state_block_reason=_first_text(row, "quality_state_block_reason"),
        state_quality_capped=_bool_value(row.get("state_quality_capped")),
        source_count=int(_float_value(row.get("source_count")) or 0),
        highest_score=latest_score,
        latest_score=latest_score,
        latest_tier=_first_text(row, "latest_tier", "tier", "final_tier_after_quality_gate", "final_route_after_quality_gate", "route") or "",
        latest_event_name=_first_text(row, "latest_event_name", "event_name", "canonical_incident_name") or opportunity.canonical_incident_name,
        latest_source=_first_text(row, "latest_source", "source", "provider"),
        latest_playbook_type=_first_text(row, "effective_playbook_type", "playbook_type", "primary_impact_path") or opportunity.primary_impact_path,
        latest_rule_playbook_type=_first_text(row, "rule_playbook_type"),
        latest_effective_playbook_type=_first_text(row, "effective_playbook_type", "playbook_type", "primary_impact_path") or opportunity.primary_impact_path,
        latest_playbook_score=latest_score,
        latest_playbook_action=_first_text(row, "playbook_action"),
        latest_market_snapshot=_mapping_value(row.get("latest_market_snapshot")) or _mapping_value(row.get("market_snapshot")) or {},
        latest_score_components=components,
        impact_path_type=opportunity.primary_impact_path or _first_text(row, "impact_path_type"),
        impact_path_strength=_first_text(row, "impact_path_strength"),
        candidate_role=opportunity.candidate_role or _first_text(row, "candidate_role"),
        evidence_quality_score=_float_value(row.get("evidence_quality_score")),
        source_class=_first_text(row, "source_class"),
        evidence_specificity=_first_text(row, "evidence_specificity"),
        market_confirmation_score=_float_value(row.get("market_confirmation_score")),
        market_confirmation_level=_first_text(row, "market_confirmation_level"),
        market_context_freshness_status=_first_text(row, "market_context_freshness_status"),
        market_context_age_hours=row.get("market_context_age_hours"),
        market_context_stale=row.get("market_context_stale") if isinstance(row.get("market_context_stale"), bool) else None,
        market_context_freshness_cap_applied=row.get("market_context_freshness_cap_applied") if isinstance(row.get("market_context_freshness_cap_applied"), bool) else None,
        opportunity_score_final=_float_value(opportunity.opportunity_score_final) or _float_value(row.get("opportunity_score_final")),
        opportunity_level=opportunity.opportunity_level or _first_text(row, "opportunity_level"),
        opportunity_verdict_reasons=_list_value(row.get("opportunity_verdict_reasons")),
        why_local_only=_first_text(row, "why_local_only"),
        why_not_watchlist=_first_text(row, "why_not_watchlist"),
        manual_verification_items=_list_value(row.get("manual_verification_items")),
        upgrade_requirements=_list_value(row.get("upgrade_requirements")),
        downgrade_warnings=_list_value(row.get("downgrade_warnings")),
        should_alert=_bool_value(row.get("should_alert")),
        suppressed_reason=_first_text(row, "suppressed_reason"),
        warnings=tuple(_list_value(row.get("warnings"))),
    )


def _core_score_components(opportunity: event_core_opportunities.CoreOpportunity) -> dict[str, Any]:
    row = opportunity.primary_row
    components: dict[str, Any] = {}
    for key in ("latest_score_components", "score_components"):
        value = row.get(key)
        if isinstance(value, Mapping):
            components.update(value)
    for key in (
        "core_opportunity_id",
        "incident_id",
        "hypothesis_id",
        "validated_symbol",
        "validated_coin_id",
        "candidate_role",
        "primary_impact_path",
        "impact_path_type",
        "relationship_type",
        "impact_category",
        "impact_path_reason",
        "opportunity_level",
        "opportunity_score_final",
        "initial_opportunity_score",
        "initial_opportunity_level",
        "post_refresh_opportunity_score",
        "post_refresh_opportunity_level",
        "post_refresh_market_confirmation_level",
        "post_refresh_market_confirmation_score",
        "post_refresh_evidence_quality_score",
        "final_opportunity_score",
        "final_opportunity_level",
        "final_verdict_source",
        "final_verdict_reason",
        "market_data_freshness",
        "market_reaction_confirmation",
        "market_context_freshness_status",
        "market_context_source",
        "market_context_observed_at",
        "market_context_age_hours",
        "market_context_freshness_cap_applied",
        "market_context_data_quality",
        "market_confirmation_score",
        "market_confirmation_level",
        "market_confirmation_after",
        "market_state_snapshot",
        "source_row_type",
        "integrated_candidate_id",
        "integrated_candidate_family_id",
        "market_state",
        "market_state_class",
        "opportunity_type",
        "opportunity_type_why_now",
        "opportunity_type_evidence",
        "opportunity_type_what_confirms",
        "opportunity_type_what_invalidates",
        "opportunity_type_why_not_alertable",
        "opportunity_type_source_requirements_met",
        "opportunity_type_market_requirements_met",
        "opportunity_type_fade_requirements_met",
        "opportunity_type_source_strength",
        "opportunity_type_warnings",
        "opportunity_type_reason_codes",
        "source_strength",
        "source_requirements_met",
        "market_requirements_met",
        "fade_requirements_met",
        "why_now",
        "what_confirms",
        "what_invalidates",
        "why_not_alertable",
        "reason_codes",
        "warnings",
        "final_route_after_quality_gate",
        "final_tier_after_quality_gate",
        "final_state_after_quality_gate",
        "source_pack",
        "source_packs",
        "source_origin",
        "source_origins",
        "source_url",
        "latest_source_url",
        "latest_source_title",
        "official_exchange_event",
        "official_exchange_provider",
        "official_exchange",
        "official_exchange_event_type",
        "official_exchange_title",
        "official_exchange_url",
        "official_exchange_published_at",
        "official_exchange_effective_time",
        "official_exchange_reason_codes",
        "scheduled_catalyst_event",
        "unlock_event",
        "derivatives_state_snapshot",
        "derivatives_snapshot",
        "crowding_class",
        "fade_readiness",
        "crowding_exhaustion_evidence",
        "what_confirms_fade_review",
        "what_invalidates_fade_review",
        "derivatives_warning_codes",
        "integrated_market_confirmation_level",
        "integrated_market_confirmation_score",
        "integrated_market_reaction_confirmation",
        "integrated_market_context_source",
        "integrated_market_freshness_status",
        "evidence_acquisition_source_pack",
        "evidence_acquisition_attempted",
        "evidence_acquisition_status",
        "evidence_acquisition_results",
        "evidence_acquisition_accepted_count",
        "evidence_acquisition_rejected_count",
        "evidence_acquisition_accepted_evidence",
        "evidence_acquisition_rejected_samples",
        "accepted_evidence_reason_codes",
        "rejected_evidence_reason_codes",
        "evidence_acquisition_provider_failures",
        "final_upgrade_status",
        "no_upgrade_reason",
        "source_class",
        "evidence_specificity",
        "evidence_quality_score",
        "evidence_quality_after",
        "quality_state_block_reason",
        "feedback_target",
        "feedback_target_type",
        "main_frame_type",
        "main_frame_role",
        "main_frame_subject",
        "main_frame_actor",
        "main_frame_object",
        "main_frame_evidence_quote",
        "frame_status",
        "selected_main_catalyst_reason",
        "rule_predicted_impact_path",
        "llm_predicted_main_frame_type",
        "frame_rule_disagreement",
        "negated_frame_ids",
        "corrective_frame_ids",
        "frame_summary",
    ):
        value = row.get(key)
        if value not in (None, "", [], {}, ()):
            components[key] = value
    components.setdefault("core_opportunity_id", opportunity.core_opportunity_id)
    components.setdefault("feedback_target", opportunity.core_opportunity_id)
    components.setdefault("feedback_target_type", "core_opportunity_id")
    components.setdefault("incident_id", opportunity.incident_id)
    components.setdefault("validated_symbol", opportunity.symbol)
    components.setdefault("validated_coin_id", opportunity.coin_id)
    components.setdefault("candidate_role", opportunity.candidate_role)
    components.setdefault("impact_path_type", opportunity.primary_impact_path)
    if opportunity.primary_impact_path and str(components.get("impact_path_type") or "").casefold() in {
        "",
        "unknown",
        "insufficient_data",
        "generic_cooccurrence_only",
    }:
        components["impact_path_type"] = opportunity.primary_impact_path
    components.setdefault("relationship_type", opportunity.primary_impact_path)
    components.setdefault("opportunity_level", opportunity.opportunity_level)
    components.setdefault("opportunity_score_final", opportunity.opportunity_score_final)
    if components.get("final_opportunity_level") not in (None, ""):
        components["opportunity_level"] = components.get("final_opportunity_level")
    if components.get("final_opportunity_score") not in (None, ""):
        components["opportunity_score_final"] = components.get("final_opportunity_score")
    components.setdefault("final_route_after_quality_gate", opportunity.final_route_after_quality_gate)
    components.setdefault("final_state_after_quality_gate", opportunity.final_state_after_quality_gate)
    return components


def _first_text(row: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if value not in (None, "", [], {}, ()):
            return str(value)
    return None


def _mapping_value(value: object) -> dict[str, Any] | None:
    return dict(value) if isinstance(value, Mapping) else None


def _list_value(value: object) -> list[str]:
    if value in (None, "", [], {}, ()):
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(";") if item.strip()]
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, Mapping)):
        return [str(item) for item in value if str(item or "")]
    return [str(value)]


def _display_list_value(value: object, *, limit: int = 6) -> str:
    items = _list_value(value)
    if not items:
        return "none"
    return "; ".join(items[:limit])


def _role_capabilities_line(value: object) -> str:
    if not isinstance(value, Mapping):
        return "unknown"
    enabled = [str(key) for key, child in sorted(value.items()) if bool(child)]
    return ", ".join(enabled) if enabled else "none"


def _bool_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _card_filename(entry: event_watchlist.EventWatchlistEntry) -> str:
    base = event_alpha_router.card_id_for_entry(entry)
    return _slug(base)[:180] + ".md"


def _slug(value: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9._-]+", "_", value)).strip("._") or "event_card"


def _render_index(
    paths: list[Path],
    observed: datetime,
    *,
    card_groups: Mapping[Path | str, str] | None = None,
) -> str:
    grouped: dict[str, list[Path]] = {
        "Early Long Research Cards": [],
        "Confirmed Long Research Cards": [],
        "Fade / Short-Review Cards": [],
        "Risk Only Cards": [],
        "Unconfirmed Research Cards": [],
        "Core Opportunity Cards": [],
        "Near-Miss Cards": [],
        "Local-Only / Quality-Capped Cards": [],
        "Diagnostic / Source-Noise / Control Cards": [],
        "Legacy Cards": [],
    }
    for path in paths:
        grouped[_card_index_group(path, card_groups=card_groups)].append(path)
    lines = [
        "# Event Research Cards",
        "",
        f"Generated at: {observed.isoformat()}",
        "",
    ]
    for group, group_paths in grouped.items():
        lines.extend(["", f"## {group}", ""])
        if group_paths:
            for path, hidden_count in collapse_card_paths_for_group(
                group_paths,
                group_name=group,
                card_groups=card_groups,
            ):
                target = card_feedback_target(path)
                group_label = _card_index_group(path, card_groups=card_groups)
                suffix = f" · group: {group_label}"
                if hidden_count:
                    suffix += f" · +{hidden_count} related diagnostic/support card(s) hidden"
                if target:
                    suffix += f" · feedback target: `{target}`"
                lines.append(f"- [{path.name}]({path.name}){suffix}")
                if target:
                    lines.append(f"  - useful: `make event-feedback-useful FEEDBACK_TARGET='{target}'`")
                    lines.append(f"  - junk: `make event-feedback-junk FEEDBACK_TARGET='{target}'`")
                    lines.append(f"  - watch: `make event-feedback-watch FEEDBACK_TARGET='{target}'`")
        elif group == "Core Opportunity Cards":
            lines.append("No cards selected.")
        elif group == "Diagnostic / Source-Noise / Control Cards":
            lines.append("Diagnostics are hidden from the main card list by default; inspect the daily brief or opportunity audit when needed.")
        else:
            lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def _candidate_index_paths(paths: Iterable[Path]) -> tuple[Path, ...]:
    indexes: list[Path] = []
    parents: set[Path] = set()
    for path in paths:
        p = Path(path)
        if p.name == "index.md":
            indexes.append(p)
        else:
            parents.add(p.parent)
    for parent in parents:
        candidate = parent / "index.md"
        if candidate.exists():
            indexes.append(candidate)
    return tuple(dict.fromkeys(indexes))


def _parse_index_groups(path: Path) -> dict[Path, str]:
    if not path.exists():
        return {}
    current: str | None = None
    out: dict[Path, str] = {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            name = stripped[3:].strip()
            current = name if name in CARD_INDEX_GROUPS else None
            continue
        if current is None or not stripped.startswith("- ["):
            continue
        match = re.search(r"\[([^\]]+\.md)\]\(([^)]+)\)", stripped)
        if not match:
            continue
        target = Path(match.group(2))
        if not target.is_absolute():
            target = path.parent / target
        out[target] = current
        out[path.parent / match.group(1)] = current
    return out


def _card_index_group(path: Path, *, card_groups: Mapping[Path | str, str] | None = None) -> str:
    if card_groups:
        mapped = card_groups.get(path) or card_groups.get(str(path)) or card_groups.get(path.name)
        if mapped in CARD_INDEX_GROUPS:
            return str(mapped)
    name = path.name.casefold()
    if "legacy" in name:
        return "Legacy Cards"
    if "source_noise_control" in name or "ambiguous_control" in name or "diagnostic" in name:
        return "Diagnostic / Source-Noise / Control Cards"
    if "quality_blocked" in name or "local_only" in name or "store_only" in name:
        return "Local-Only / Quality-Capped Cards"
    if "near_miss" in name or "near-miss" in name:
        return "Near-Miss Cards"
    if path.exists():
        text = path.read_text(encoding="utf-8", errors="replace").casefold()
        content_group = _card_index_group_for_text(text)
        if content_group is not None:
            return content_group
    return "Core Opportunity Cards"


def _card_family_key(
    path: Path,
    *,
    group_name: str | None = None,
    card_groups: Mapping[Path | str, str] | None = None,
) -> tuple[str, str, str, str]:
    group = group_name or _card_index_group(path, card_groups=card_groups)
    text = ""
    if path.exists():
        text = path.read_text(encoding="utf-8", errors="replace")
    asset = _card_metadata_line(text, "Asset") or _card_metadata_line(text, "Symbol") or path.stem
    event = (
        _card_metadata_line(text, "Event")
        or _card_metadata_line(text, "External catalyst")
        or _card_metadata_line(text, "Canonical incident")
        or path.stem
    )
    playbook = (
        _card_metadata_line(text, "Playbook")
        or _card_metadata_line(text, "Impact path")
        or _card_metadata_line(text, "Primary impact path")
        or path.stem
    )
    if group in {"Near-Miss Cards", "Local-Only / Quality-Capped Cards"}:
        return (
            group,
            _card_family_asset(asset),
            "operator_family",
            "operator_family",
        )
    return (
        group,
        _card_family_asset(asset),
        _card_family_event(event),
        _card_family_playbook(playbook),
    )


def _card_primary_sort_key(path: Path) -> tuple[int, int, int, int, str]:
    text = ""
    if path.exists():
        text = path.read_text(encoding="utf-8", errors="replace")
    accepted = _card_accepted_evidence_count(text)
    suppress_duplicate = 1 if re.search(r"(?im)^\s*[-*]\s*Final route:\s*SUPPRESS_DUPLICATE\b", text or "") else 0
    store_only = 1 if re.search(r"(?im)^\s*[-*]\s*Final route:\s*STORE_ONLY\b", text or "") else 0
    score = _card_primary_score(text)
    return (-accepted, suppress_duplicate, store_only, -score, path.name)


def _card_accepted_evidence_count(text: str) -> int:
    values: list[int] = []
    for pattern in (
        r"(?im)^\s*[-*]\s*Accepted evidence count:\s*(\d+)\b",
        r"(?im)\baccepted=(\d+)\b",
    ):
        for match in re.finditer(pattern, text or ""):
            try:
                values.append(int(match.group(1)))
            except (TypeError, ValueError):
                continue
    return max(values) if values else 0


def _card_primary_score(text: str) -> int:
    values: list[float] = []
    for pattern in (
        r"(?im)^\s*[-*]\s*Final opportunity verdict:\s*[A-Za-z_/-]+\s*/\s*([0-9]+(?:\.[0-9]+)?)",
        r"(?im)\bscore[=:]\s*([0-9]+(?:\.[0-9]+)?)\b",
    ):
        for match in re.finditer(pattern, text or ""):
            try:
                values.append(float(match.group(1)))
            except (TypeError, ValueError):
                continue
    return int(max(values)) if values else 0


def _card_metadata_line(text: str, label: str) -> str | None:
    pattern = rf"(?im)^\s*[-*]\s*{re.escape(label)}:\s*(.+?)\s*$"
    match = re.search(pattern, text or "")
    if not match:
        return None
    return match.group(1).strip()


def _card_family_asset(value: str) -> str:
    text = str(value or "").casefold()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    parts = text.split()
    return parts[0] if parts else "unknown"


def _card_family_event(value: str) -> str:
    text = str(value or "").casefold().split("·", 1)[0]
    for token in ("spacex", "world cup", "kraken", "thorchain", "zcash", "aave", "kelpdao"):
        if token in text:
            return token.replace(" ", "_")
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    return "_".join(text.split()[:5]) or "unknown"


def _card_family_playbook(value: str) -> str:
    text = str(value or "").casefold()
    if any(token in text for token in ("preipo", "pre-ipo", "proxy", "tokenized", "rwa", "venue_value")):
        return "proxy"
    if "fan" in text or "sports" in text or "world cup" in text:
        return "fan_token"
    if "source_noise" in text or "control" in text or "diagnostic" in text:
        return "diagnostic"
    if "listing" in text or "exchange" in text:
        return "listing"
    if "exploit" in text or "security" in text:
        return "security"
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    return "_".join(text.split()[:3]) or "unknown"


def _card_index_group_for_entry(
    entry: event_watchlist.EventWatchlistEntry,
    decisions: Iterable[event_alpha_router.EventAlphaRouteDecision],
) -> str:
    components = dict(entry.latest_score_components or {})
    lane = str(components.get("opportunity_type") or "").strip().upper()
    lane_group = _lane_card_group(lane)
    if lane_group is not None:
        return lane_group
    text = " ".join(str(value or "") for value in (
        entry.latest_effective_playbook_type,
        entry.latest_playbook_type,
        entry.candidate_role,
        entry.impact_path_type,
        entry.source_class,
        entry.evidence_specificity,
        entry.quality_state_block_reason,
        components.get("candidate_role"),
        components.get("impact_path_type"),
        components.get("source_class"),
        components.get("evidence_specificity"),
        components.get("quality_gate_block_reason"),
    )).casefold()
    if "source_noise" in text or "ticker_word_collision" in text or "generic_cooccurrence_only" in text:
        return "Diagnostic / Source-Noise / Control Cards"
    level = str(entry.opportunity_level or components.get("opportunity_level") or "").casefold()
    final_route = str(components.get("final_route_after_quality_gate") or components.get("route") or "")
    for decision in decisions:
        if decision.entry.key == entry.key:
            final_route = event_alpha_router.final_route_value(decision)
            break
    if level in {"validated_digest", "watchlist", "high_priority"} or event_alpha_router.route_value_is_alertable(final_route):
        return "Core Opportunity Cards"
    if event_watchlist.state_is_quality_capped(entry) or event_watchlist.final_state_value(entry) == event_watchlist.EventWatchlistState.QUALITY_BLOCKED.value:
        return "Local-Only / Quality-Capped Cards"
    score = _float(components.get("opportunity_score_final") or entry.opportunity_score_final) or 0.0
    if level == "exploratory" or score >= 50:
        return "Near-Miss Cards"
    return "Local-Only / Quality-Capped Cards"


def _card_index_group_for_text(text: str) -> str | None:
    match = re.search(r"opportunity type:\s*([a-z0-9_/-]+)", text, flags=re.IGNORECASE)
    if match:
        lane_group = _lane_card_group(match.group(1))
        if lane_group is not None:
            return lane_group
    if (
        "source_noise_control" in text
        or "ticker_word_collision" in text
        or "generic_cooccurrence_only" in text
        or "publisher/source name is not asset identity" in text
        or "ticker/common-word collision risk" in text
    ):
        return "Diagnostic / Source-Noise / Control Cards"
    if "local-only after quality/state gate" in text or "quality_blocked" in text:
        return "Local-Only / Quality-Capped Cards"
    if "final opportunity verdict: local_only" in text:
        return "Local-Only / Quality-Capped Cards"
    if "final opportunity verdict: exploratory" in text:
        return "Near-Miss Cards"
    if "final route: store_only" in text:
        return "Local-Only / Quality-Capped Cards"
    if (
        "final opportunity verdict: high_priority" in text
        or "final opportunity verdict: watchlist" in text
        or "final opportunity verdict: validated_digest" in text
        or "final route: high_priority_research" in text
        or "final route: research_digest" in text
        or "final route: watchlist" in text
        or "route: high_priority_research" in text
        or "route: research_digest" in text
    ):
        return "Core Opportunity Cards"
    return None


def _lane_card_group(value: object) -> str | None:
    lane = str(value or "").strip().upper()
    mapping = {
        "EARLY_LONG_RESEARCH": "Early Long Research Cards",
        "CONFIRMED_LONG_RESEARCH": "Confirmed Long Research Cards",
        "FADE_SHORT_REVIEW": "Fade / Short-Review Cards",
        "RISK_ONLY": "Risk Only Cards",
        "UNCONFIRMED_RESEARCH": "Unconfirmed Research Cards",
        "DIAGNOSTIC": "Diagnostic / Source-Noise / Control Cards",
    }
    return mapping.get(lane)


def _components_are_integrated_radar(components: Mapping[str, Any]) -> bool:
    return (
        str(components.get("source_row_type") or "") == "event_integrated_radar_candidate"
        or bool(components.get("integrated_candidate_id"))
    )


def _text_is_integrated_radar_card(text: str) -> bool:
    lowered = text.casefold()
    candidate_match = re.search(r"(?im)^-\s*integrated candidate id:\s*(.+?)\s*$", text)
    return (
        "source row type: event_integrated_radar_candidate" in lowered
        or (
            candidate_match is not None
            and candidate_match.group(1).strip().casefold() not in {"", "none"}
        )
    )


def _strip_sensitive(markdown: str) -> str:
    out = markdown.replace("OPENAI_API_KEY", "[redacted]").replace("TELEGRAM_BOT_TOKEN", "[redacted]")
    out = out.replace(".env", "[env-file]")
    return event_artifact_paths.scrub_absolute_paths_from_markdown(out)


def _find_alert(key: str, rows: list[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    clean_key = key[3:] if key.startswith("ea:") else key
    key_l = clean_key.lower()
    matches: list[Mapping[str, Any]] = []
    for row in rows:
        values = {
            str(row.get("alert_key") or ""),
            str(row.get("alert_id") or ""),
            str(row.get("card_id") or ""),
            str(row.get("snapshot_id") or ""),
            str(row.get("core_opportunity_id") or ""),
            str(row.get("event_id") or ""),
            str(row.get("hypothesis_id") or ""),
            str(row.get("incident_id") or ""),
            str(row.get("asset_symbol") or ""),
            str(row.get("asset_coin_id") or ""),
        }
        if clean_key in values or key_l in {value.lower() for value in values}:
            matches.append(row)
    if not matches:
        return None
    return sorted(
        matches,
        key=lambda row: (
            str(row.get("row_type") or "") == "event_core_opportunity",
            bool(row.get("final_route_after_quality_gate")),
            _float_value(row.get("opportunity_score_final") or row.get("final_opportunity_score")) or 0.0,
        ),
        reverse=True,
    )[0]


def _find_decision(
    key: str,
    decisions: list[event_alpha_router.EventAlphaRouteDecision],
) -> event_alpha_router.EventAlphaRouteDecision | None:
    clean_key = key[3:] if key.startswith("ea:") else key
    key_l = clean_key.lower()
    for decision in decisions:
        entry = decision.entry
        if clean_key in {entry.key, entry.event_id, decision.alert_id, decision.card_id} or key_l in {
            entry.symbol.lower(),
            entry.coin_id.lower(),
        }:
            return decision
    return None


def _find_cluster(
    key: str,
    clusters: list[event_graph.EventCluster],
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
) -> event_graph.EventCluster | None:
    key_l = key.lower()
    identifiers = {
        key,
        key_l,
        str(getattr(entry, "cluster_id", "") or ""),
        str(getattr(entry, "event_id", "") or ""),
        str(alert.get("cluster_id") or "") if alert else "",
        str(alert.get("event_id") or "") if alert else "",
    }
    identifiers_l = {item.lower() for item in identifiers if item}
    for cluster in clusters:
        if cluster.cluster_id in identifiers or cluster.cluster_id.lower() in identifiers_l:
            return cluster
        if any(str(event_id).lower() in identifiers_l for event_id in cluster.event_ids):
            return cluster
        for link in cluster.asset_links:
            if key_l in {link.symbol.lower(), link.coin_id.lower()}:
                return cluster
    return None


def _find_monitor_row(
    key: str,
    rows: list[event_watchlist_monitor.EventWatchlistMonitorRow | Mapping[str, Any]],
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
) -> event_watchlist_monitor.EventWatchlistMonitorRow | Mapping[str, Any] | None:
    clean_key = key[3:] if key.startswith("ea:") else key
    key_l = clean_key.lower()
    identifiers = {
        clean_key,
        key_l,
        str(getattr(entry, "key", "") or ""),
        str(getattr(entry, "symbol", "") or ""),
        str(getattr(entry, "coin_id", "") or ""),
        str(alert.get("alert_key") or "") if alert else "",
        str(alert.get("asset_symbol") or "") if alert else "",
        str(alert.get("asset_coin_id") or "") if alert else "",
    }
    identifiers_l = {item.lower() for item in identifiers if item}
    for row in rows:
        values = {
            str(_monitor_value(row, "key") or ""),
            str(_monitor_value(row, "symbol") or ""),
            str(_monitor_value(row, "coin_id") or ""),
        }
        if clean_key in values or key_l in {value.lower() for value in values} or identifiers_l & {
            value.lower() for value in values if value
        }:
            return row
    return None


def _matching_rows(
    key: str,
    rows: list[Mapping[str, Any]],
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
) -> list[Mapping[str, Any]]:
    clean_key = key[3:] if key.startswith("ea:") else key
    key_l = clean_key.lower()
    identifiers = {
        clean_key,
        str(getattr(entry, "key", "") or ""),
        str(getattr(entry, "event_id", "") or ""),
        str(getattr(entry, "symbol", "") or ""),
        str(getattr(entry, "coin_id", "") or ""),
        str(alert.get("alert_key") or "") if alert else "",
        str(alert.get("event_id") or "") if alert else "",
        str(alert.get("asset_symbol") or "") if alert else "",
        str(alert.get("asset_coin_id") or "") if alert else "",
    }
    identifiers_l = {item.lower() for item in identifiers if item}
    matches: list[Mapping[str, Any]] = []
    for row in rows:
        values = {
            str(row.get("key") or ""),
            str(row.get("target") or ""),
            str(row.get("alert_key") or ""),
            str(row.get("event_id") or ""),
            str(row.get("symbol") or row.get("asset_symbol") or ""),
            str(row.get("coin_id") or row.get("asset_coin_id") or ""),
        }
        values_l = {value.lower() for value in values if value}
        if key_l in values_l or identifiers_l & values_l:
            matches.append(row)
    return matches


def _find_outcome(
    key: str,
    rows: list[Mapping[str, Any]],
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
) -> Mapping[str, Any] | None:
    matches = _matching_rows(key, rows, entry, alert)
    if not matches:
        return None
    return sorted(matches, key=lambda row: str(row.get("observed_at") or row.get("updated_at") or ""), reverse=True)[0]


def _value(entry: Any | None, alert: Mapping[str, Any] | None, entry_field: str, alert_field: str) -> Any:
    if entry is not None and entry_field:
        value = getattr(entry, entry_field, None)
        if value not in (None, ""):
            return value
    if alert is not None:
        value = alert.get(alert_field)
        if value not in (None, ""):
            return value
        if entry_field:
            value = alert.get(entry_field)
            if value not in (None, ""):
                return value
    return None


def _canonical_card_alert(
    opportunity: event_core_opportunities.CoreOpportunity,
    alert: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = dict(alert or {})
    primary = dict(opportunity.primary_row or {})
    for key, value in primary.items():
        row.setdefault(key, value)
    row.update({
        "core_opportunity_id": opportunity.core_opportunity_id,
        "symbol": opportunity.symbol,
        "coin_id": opportunity.coin_id,
        "asset_symbol": opportunity.symbol,
        "asset_coin_id": opportunity.coin_id,
        "event_name": opportunity.canonical_incident_name or row.get("event_name") or row.get("latest_event_name"),
        "canonical_incident_name": opportunity.canonical_incident_name,
        "candidate_role": opportunity.candidate_role,
        "primary_impact_path": opportunity.primary_impact_path,
        "impact_path_type": opportunity.primary_impact_path,
        "relationship_type": opportunity.primary_impact_path,
        "playbook_type": row.get("playbook_type") or row.get("effective_playbook_type") or opportunity.primary_impact_path,
        "effective_playbook_type": row.get("effective_playbook_type") or row.get("playbook_type") or opportunity.primary_impact_path,
        "state": opportunity.final_state_after_quality_gate,
        "tier": opportunity.final_route_after_quality_gate,
        "latest_tier": opportunity.final_route_after_quality_gate,
        "route": opportunity.final_route_after_quality_gate,
        "final_route_after_quality_gate": opportunity.final_route_after_quality_gate,
        "final_tier_after_quality_gate": row.get("final_tier_after_quality_gate") or opportunity.final_route_after_quality_gate,
        "final_state_after_quality_gate": opportunity.final_state_after_quality_gate,
        "opportunity_level": opportunity.opportunity_level,
        "opportunity_score_final": opportunity.opportunity_score_final,
        "final_opportunity_level": row.get("final_opportunity_level") or opportunity.opportunity_level,
        "final_opportunity_score": row.get("final_opportunity_score") or opportunity.opportunity_score_final,
        "feedback_target": row.get("feedback_target") or opportunity.core_opportunity_id,
        "feedback_target_type": row.get("feedback_target_type") or "core_opportunity_id",
    })
    components = _core_score_components(opportunity)
    existing = row.get("score_components") if isinstance(row.get("score_components"), Mapping) else {}
    row["score_components"] = {**dict(existing), **components}
    return row


def _cluster_lines(cluster: event_graph.EventCluster | None) -> list[str]:
    if cluster is None:
        return ["- No cluster graph data found in local artifacts."]
    accepted = [link for link in cluster.asset_links if link.accepted]
    rejected = [link for link in cluster.asset_links if not link.accepted]
    providers = sorted({evidence.source for evidence in cluster.evidence if evidence.source})
    origins = sorted({
        _origin(url)
        for evidence in cluster.evidence
        for url in evidence.source_urls
        if url
    })
    lines = [
        f"- Cluster ID: {cluster.cluster_id}",
        f"- Cluster confidence: {cluster.cluster_confidence}",
        f"- Independent sources: {cluster.independent_source_count}",
        f"- Event-time consensus: {cluster.event_time_consensus}",
        f"- Source providers: {', '.join(providers) if providers else 'unknown'}",
        f"- Source origins: {', '.join(origins) if origins else 'unknown'}",
    ]
    accepted_by_kind: dict[str, list[str]] = {}
    for link in accepted:
        accepted_by_kind.setdefault(link.accepted_kind, []).append(f"{link.symbol}/{link.coin_id}")
    if accepted_by_kind:
        lines.append(
            "- Accepted links by kind: "
            + "; ".join(
                f"{kind}={', '.join(values)}"
                for kind, values in sorted(accepted_by_kind.items())
            )
        )
    else:
        lines.append("- Accepted links by kind: none")
    if rejected:
        lines.append(
            "- Rejected/noise links: "
            + "; ".join(
                f"{link.symbol}/{link.coin_id}:{link.rejected_reason or 'rejected'}"
                for link in rejected[:8]
            )
        )
    else:
        lines.append("- Rejected/noise links: none")
    if cluster.source_urls:
        lines.append("- Top evidence URLs: " + "; ".join(cluster.source_urls[:5]))
    if cluster.warnings:
        lines.append("- Cluster warnings: " + "; ".join(cluster.warnings))
    return lines


def _origin(url: str) -> str:
    parsed = urlparse(str(url))
    return parsed.netloc or parsed.path or "unknown"


def _card_components(
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
) -> dict[str, Any]:
    components = dict(entry.latest_score_components if entry else {})
    if alert:
        alert_components = alert.get("score_components") if isinstance(alert.get("score_components"), Mapping) else {}
        latest = alert.get("latest_score_components") if isinstance(alert.get("latest_score_components"), Mapping) else {}
        components.update(dict(alert_components or {}))
        components.update(dict(latest or {}))
        components.update({key: value for key, value in alert.items() if value not in (None, "", [], {}, ())})
    if entry is not None:
        for key, value in {
            "latest_source": entry.latest_source,
            "source_count": entry.source_count,
            "symbol": entry.symbol,
            "coin_id": entry.coin_id,
            "impact_path_type": entry.impact_path_type,
            "impact_path_strength": entry.impact_path_strength,
            "candidate_role": entry.candidate_role,
            "market_confirmation_level": entry.market_confirmation_level,
            "market_confirmation_score": entry.market_confirmation_score,
            "market_context_freshness_status": entry.market_context_freshness_status,
            "market_context_age_hours": entry.market_context_age_hours,
            "opportunity_level": entry.opportunity_level,
            "opportunity_score_final": entry.opportunity_score_final,
        }.items():
            if value not in (None, "", [], {}, ()) and key not in components:
                components[key] = value
    return components


def _accepted_evidence_samples(components: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = components.get("evidence_acquisition_accepted_evidence") or components.get("accepted_evidence")
    if isinstance(raw, Mapping):
        return [raw]
    if isinstance(raw, Iterable) and not isinstance(raw, (str, bytes)):
        return [item for item in raw if isinstance(item, Mapping)]
    return []


def _first_accepted_evidence_sample(components: Mapping[str, Any]) -> Mapping[str, Any]:
    samples = _accepted_evidence_samples(components)
    return samples[0] if samples else {}


def _int_value(value: object) -> int | None:
    try:
        return int(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _is_promoted_components(components: Mapping[str, Any]) -> bool:
    level = str(components.get("final_opportunity_level") or components.get("opportunity_level") or "").casefold()
    route = str(components.get("final_route_after_quality_gate") or components.get("route") or "").upper()
    return level in {"validated_digest", "watchlist", "high_priority"} or event_alpha_router.route_value_is_alertable(route)


def _canonical_reason_from_components(components: Mapping[str, Any]) -> str | None:
    path = str(components.get("impact_path_type") or components.get("primary_impact_path") or "").strip()
    pack = str(components.get("source_pack") or components.get("evidence_acquisition_source_pack") or "").strip()
    if path in {"proxy_attention", "proxy_exposure", "venue_value_capture"} or pack == "proxy_preipo_rwa_pack":
        return "venue_value_capture"
    if path == "strategic_investment_or_valuation" or pack == "strategic_investment_pack":
        return "strategic_investment"
    if path == "market_dislocation_unknown":
        return "cause_unknown_market_dislocation"
    return path or None


def _canonical_strength_from_components(components: Mapping[str, Any]) -> str | None:
    level = str(components.get("final_opportunity_level") or components.get("opportunity_level") or "").casefold()
    path = str(components.get("impact_path_type") or components.get("primary_impact_path") or "").casefold()
    if path in {"", "insufficient_data", "generic_cooccurrence_only"}:
        return None
    if level in {"high_priority", "watchlist"}:
        return "strong"
    if level == "validated_digest":
        return "medium"
    return None


def _canonical_market_summary_from_components(components: Mapping[str, Any]) -> str | None:
    level = components.get("market_confirmation_level") or components.get("market_reaction_confirmation")
    score = components.get("market_confirmation_score")
    freshness = components.get("market_data_freshness") or components.get("market_context_freshness_status")
    source = components.get("market_context_source")
    if not any(value not in (None, "", [], {}, ()) for value in (level, score, freshness, source)):
        return None
    parts = []
    if level or score is not None:
        parts.append(f"{level or 'not available'} / {score if score is not None else 'n/a'}")
    if freshness or source:
        parts.append(f"freshness={freshness or 'not available'} source={source or 'not available'}")
    return "; ".join(parts)


def _source_lines(entry: event_watchlist.EventWatchlistEntry | None, alert: Mapping[str, Any] | None) -> list[str]:
    components = _card_components(entry, alert)
    sample = _first_accepted_evidence_sample(components)
    official_event = components.get("official_exchange_event") if isinstance(components.get("official_exchange_event"), Mapping) else {}
    scheduled_event = components.get("scheduled_catalyst_event") if isinstance(components.get("scheduled_catalyst_event"), Mapping) else {}
    unlock_event = components.get("unlock_event") if isinstance(components.get("unlock_event"), Mapping) else {}
    structured_event = official_event or scheduled_event or unlock_event
    latest_source = _display_text(
        components.get("latest_source")
        or components.get("source")
        or components.get("source_provider")
        or structured_event.get("provider")
        or structured_event.get("exchange")
    ) or _display_text(sample.get("provider") if sample else None) or _display_text(sample.get("provider_hint") if sample else None)
    source_url = (
        components.get("source_url")
        or components.get("latest_source_url")
        or structured_event.get("source_url")
        or structured_event.get("url")
        or (sample.get("source_url") if sample else None)
    )
    source_title = components.get("latest_source_title") or structured_event.get("title") or structured_event.get("event_name") or (sample.get("title") if sample else None)
    accepted_count = _int_value(components.get("evidence_acquisition_accepted_count")) or len(_accepted_evidence_samples(components))
    source_count = _int_value(components.get("source_count")) or (entry.source_count if entry is not None else 0) or accepted_count
    lines: list[str] = [
        f"- Latest source: {latest_source or 'not available'}",
        f"- Source count: {source_count if source_count else 'not available'}",
    ]
    if accepted_count:
        lines.append(f"- Accepted evidence count: {accepted_count}")
    if source_title:
        lines.append(f"- Latest evidence title: {source_title}")
    if source_url:
        lines.append(f"- URL: {source_url}")
    provider = _display_text(components.get("source_provider")) or _display_text(sample.get("provider") if sample else None)
    if provider:
        lines.append(f"- Provider: {provider}")
    return lines


def _official_exchange_evidence_lines(
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
) -> list[str]:
    components = _card_components(entry, alert)
    event = components.get("official_exchange_event") if isinstance(components.get("official_exchange_event"), Mapping) else {}
    source_pack = str(components.get("source_pack") or "")
    source_class = str(components.get("source_class") or "")
    event_type = str(components.get("official_exchange_event_type") or event.get("event_type") or components.get("event_type") or "")
    if (
        source_class != "official_exchange"
        and not source_pack.startswith("official_exchange")
        and not source_pack.startswith("official_perp")
        and not event
    ):
        return []
    reason_codes = _list_strings(
        components.get("official_exchange_reason_codes")
        or event.get("reason_codes")
        or components.get("reason_codes")
        or components.get("accepted_evidence_reason_codes")
    )
    pairs = _list_strings(components.get("pairs") or event.get("pairs") or components.get("announcement_pairs"))
    contracts = _list_strings(components.get("contracts") or event.get("contracts") or components.get("announcement_contracts"))
    exchange = components.get("official_exchange") or event.get("exchange") or components.get("exchange")
    title = components.get("official_exchange_title") or event.get("title") or event.get("event_name") or components.get("latest_source_title")
    url = components.get("official_exchange_url") or event.get("source_url") or event.get("url") or components.get("source_url")
    published = components.get("official_exchange_published_at") or event.get("published_at") or components.get("published_at")
    effective = components.get("official_exchange_effective_time") or event.get("effective_time") or components.get("effective_time")
    lines = [
        f"- Exchange: {_display_text(exchange) or 'unknown'}",
        f"- Event type: {event_type or 'unknown'}",
        f"- Title: {_display_text(title) or 'unknown'}",
        f"- Source pack: {source_pack or 'unknown'}",
        f"- Token identity: {'resolved' if components.get('coin_id') or components.get('validated_coin_id') else 'unresolved'}",
        f"- Impact path: {_display_text(components.get('impact_path_type')) or 'unknown'}",
    ]
    if pairs:
        lines.append("- Pairs: " + ", ".join(pairs[:6]))
    if contracts:
        lines.append("- Contracts: " + ", ".join(contracts[:6]))
    if reason_codes:
        lines.append("- Reason codes: " + ", ".join(reason_codes[:8]))
    if published or effective:
        lines.append(
            "- Timing: "
            f"published={published or 'unknown'} "
            f"effective={effective or 'unknown'}"
        )
    if url:
        lines.append(f"- Official source: {url}")
    return lines


def _scheduled_catalyst_lines(
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
) -> list[str]:
    components = _card_components(entry, alert)
    scheduled_event = components.get("scheduled_catalyst_event") if isinstance(components.get("scheduled_catalyst_event"), Mapping) else {}
    unlock_event = components.get("unlock_event") if isinstance(components.get("unlock_event"), Mapping) else {}
    event = unlock_event or scheduled_event
    row_type = str(components.get("row_type") or "")
    source_pack = str(components.get("source_pack") or "")
    impact = str(components.get("impact_path_type") or "")
    if not (
        row_type in {"scheduled_catalyst_event", "unlock_event"}
        or event
        or "unlock" in source_pack
        or "project_event" in source_pack
        or "unlock" in impact
    ):
        return []
    lines = [
        f"- Event type: {_display_text(components.get('event_type') or event.get('event_type')) or 'unknown'}",
        f"- Event status: {_display_text(components.get('event_status') or event.get('event_status')) or 'unknown'}",
        f"- Source class: {_display_text(components.get('source_class') or event.get('source_class')) or 'unknown'}",
        f"- Source pack: {source_pack or 'unknown'}",
        f"- Event start: {_display_text(components.get('event_start_time') or components.get('unlock_time') or event.get('event_start_time') or event.get('unlock_time')) or 'unknown'}",
        f"- Market state: {_display_text(components.get('market_state')) or 'unknown'}",
        f"- Opportunity type: {_display_text(components.get('opportunity_type')) or 'unknown'}",
    ]
    if components.get("unlock_time") or event.get("unlock_time") or components.get("unlock_pct_circulating_supply") is not None or event.get("unlock_pct_circulating_supply") is not None:
        lines.extend([
            f"- Unlock time: {_display_text(components.get('unlock_time') or event.get('unlock_time')) or 'unknown'}",
            f"- Unlock type: {_display_text(components.get('unlock_type') or event.get('unlock_type')) or 'unknown'}",
            f"- Unlock pct circulating: {_display_text(components.get('unlock_pct_circulating_supply') or event.get('unlock_pct_circulating_supply')) or 'n/a'}",
            f"- Unlock vs 30d ADV: {_display_text(components.get('unlock_vs_30d_adv') or event.get('unlock_vs_30d_adv')) or 'n/a'}",
            f"- Structured unlock proof: {str(bool(components.get('structured_unlock_evidence') or event.get('structured_unlock_evidence'))).lower()}",
        ])
    confirms = _list_strings(components.get("what_confirms"))
    invalidates = _list_strings(components.get("what_invalidates"))
    why_not = _list_strings(components.get("why_not_alertable"))
    if confirms:
        lines.append("- What confirms: " + "; ".join(confirms[:4]))
    if invalidates:
        lines.append("- What invalidates: " + "; ".join(invalidates[:4]))
    if why_not:
        lines.append("- Why not alertable: " + "; ".join(why_not[:5]))
    source_url = components.get("source_url") or event.get("source_url") or event.get("url")
    if source_url:
        lines.append(f"- Source: {source_url}")
    return lines


def _derivatives_crowding_lines(
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
) -> list[str]:
    components = _card_components(entry, alert)
    state = components.get("derivatives_state_snapshot")
    if not isinstance(state, Mapping):
        state = {}
    opportunity = str(components.get("opportunity_type") or components.get("opportunity_type_original") or "")
    crowding = str(components.get("crowding_class") or "").strip()
    has_derivatives = bool(state) or opportunity == "FADE_SHORT_REVIEW" or bool(crowding)
    if not has_derivatives:
        return []
    evidence = _list_strings(components.get("crowding_exhaustion_evidence"))
    confirms = _list_strings(components.get("what_confirms_fade_review") or components.get("what_confirms"))
    invalidates = _list_strings(components.get("what_invalidates_fade_review") or components.get("what_invalidates"))
    lines = [
        "- Research-only. Not a trade signal.",
        f"- Provider: {_display_text(state.get('provider')) or 'unknown'}",
        f"- Market: {_display_text(state.get('market')) or 'unknown'}",
        f"- OI delta: 1h={_display_pct(state.get('open_interest_delta_1h'))} "
        f"4h={_display_pct(state.get('open_interest_delta_4h'))} "
        f"24h={_display_pct(state.get('open_interest_delta_24h'))}",
        f"- Funding: current={_display_pct(state.get('funding_rate'))} "
        f"predicted={_derivatives_metric_pct(state, 'predicted_funding', 'predicted_funding_rate')} "
        f"z={_display_text(state.get('funding_zscore')) or 'n/a'} "
        f"unit={_display_text(state.get('funding_rate_unit')) or 'unknown'}",
        f"- Basis: {_derivatives_metric_pct(state, 'basis', 'basis')} "
        f"unit={_display_text(state.get('basis_unit')) or 'unknown'}",
        f"- Liquidation imbalance: {_display_text(state.get('liquidation_imbalance')) or 'n/a'}",
        f"- Metric status: {_derivatives_metric_status_summary(state)}",
        f"- Unit metadata: {_derivatives_unit_summary(state)}",
        f"- Freshness: snapshot={_display_text(state.get('derivatives_snapshot_freshness_status') or state.get('freshness_status')) or 'unknown'} "
        f"oi={_display_text(state.get('open_interest_freshness')) or 'unknown'} "
        f"funding={_display_text(state.get('funding_freshness')) or 'unknown'} "
        f"liquidations={_display_text(state.get('liquidation_freshness')) or 'unknown'} "
        f"long_short={_display_text(state.get('long_short_freshness')) or 'unknown'} "
        f"basis={_display_text(state.get('basis_freshness')) or 'unknown'}",
        f"- Crowding class: {crowding or 'unknown'}",
        f"- Fade readiness: {_display_text(components.get('fade_readiness')) or 'unknown'}",
    ]
    coinalyze_namespace = _display_text(state.get("coinalyze_artifact_namespace") or components.get("coinalyze_artifact_namespace"))
    coinalyze_path = _display_text(state.get("coinalyze_source_artifact_path") or components.get("coinalyze_source_artifact_path"))
    coinalyze_health = _display_text(state.get("coinalyze_provider_health_status") or components.get("coinalyze_provider_health_status"))
    if coinalyze_namespace or coinalyze_path:
        lines.append(
            "- Coinalyze source: "
            f"namespace={coinalyze_namespace or 'unknown'} "
            f"path={coinalyze_path or 'unknown'} "
            f"provider_health={coinalyze_health or 'not_observed'}"
        )
    if evidence:
        lines.append("- Crowding / exhaustion evidence: " + "; ".join(evidence[:8]))
    if confirms:
        lines.append("- What confirms fade review: " + "; ".join(confirms[:5]))
    if invalidates:
        lines.append("- What invalidates fade review: " + "; ".join(invalidates[:5]))
    warnings = _list_strings(components.get("warnings"))
    if warnings:
        lines.append("- Warnings: " + "; ".join(warnings[:6]))
    return lines


def _derivatives_metric_pct(state: Mapping[str, Any], metric: str, key: str) -> str:
    if _float(state.get(key)) is not None:
        return _display_pct(state.get(key))
    status = state.get("supported_metric_status")
    if isinstance(status, Mapping) and status.get(metric):
        return str(status.get(metric))
    return "missing_from_response"


def _derivatives_metric_status_summary(state: Mapping[str, Any]) -> str:
    status = state.get("supported_metric_status")
    if not isinstance(status, Mapping):
        return "none"
    metrics = ("open_interest", "funding_rate", "predicted_funding", "liquidations", "long_short_ratio", "basis", "perp_volume")
    parts = [f"{metric}={status.get(metric)}" for metric in metrics if status.get(metric)]
    return ", ".join(parts) if parts else "none"


def _derivatives_unit_summary(state: Mapping[str, Any]) -> str:
    units = state.get("unit_metadata") if isinstance(state.get("unit_metadata"), Mapping) else state
    keys = ("open_interest_unit", "funding_rate_unit", "basis_unit", "liquidation_unit", "volume_unit")
    parts = [f"{key}={units.get(key)}" for key in keys if units.get(key)]  # type: ignore[union-attr]
    return ", ".join(parts) if parts else "none"


def _display_pct(value: Any) -> str:
    parsed = _float(value)
    if parsed is None:
        return "n/a"
    if abs(parsed) <= 3.0:
        parsed *= 100.0
    return f"{parsed:+.2f}%"


def _list_strings(value: Any) -> list[str]:
    if value in (None, "", [], (), {}):
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [str(key) for key in value.keys()]
    if isinstance(value, Iterable):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]


def _display_text(value: Any) -> str | None:
    text = str(value or "").strip()
    if text.casefold() in {
        "",
        "unknown",
        "missing",
        "none",
        "not available",
        "n/a",
        "insufficient_data",
        "impact_hypothesis",
        "watchlist",
        "alert_snapshot",
        "core_opportunity",
    }:
        return None
    return text


def _source_acquisition_lines(
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
    *,
    card_path: str | Path | None = None,
    lineage_context: Mapping[str, Any] | None = None,
) -> list[str]:
    components = _card_components(entry, alert)
    if not components and entry is None:
        return ["- Source pack: unknown", "- Evidence acquisition: no local metadata."]
    pack_name = str(components.get("source_pack") or "")
    if not pack_name:
        impact_for_pack = str(components.get("impact_path_type") or "")
        if impact_for_pack.casefold() in {"proxy_attention", "proxy_exposure"}:
            impact_for_pack = "venue_value_capture"
        pack = event_source_packs.source_pack_for_playbook(
            str(components.get("playbook_type") or components.get("latest_effective_playbook_type") or (entry.latest_playbook_type if entry else "") or ""),
            impact_path_type=impact_for_pack,
            impact_category=str(components.get("impact_category") or ""),
        )
        pack_name = pack.name
    assessment = event_source_registry.assess_source(
        components,
        symbol=str(components.get("validated_symbol") or (entry.symbol if entry else "") or ""),
        coin_id=str(components.get("validated_coin_id") or (entry.coin_id if entry else "") or ""),
        provider_coverage_status=components.get("provider_coverage_status"),
    )
    plan = components.get("evidence_acquisition_plan") if isinstance(components.get("evidence_acquisition_plan"), Mapping) else {}
    needed = plan.get("evidence_needed") if isinstance(plan, Mapping) else components.get("evidence_needed")
    queries = plan.get("evidence_query_plan") if isinstance(plan, Mapping) else components.get("evidence_query_plan")
    failures = components.get("evidence_acquisition_failures") or assessment.warnings
    acquisition = components.get("evidence_acquisition_results") if isinstance(components.get("evidence_acquisition_results"), Mapping) else {}
    accepted_evidence = components.get("evidence_acquisition_accepted_evidence") or ()
    accepted_reasons = components.get("accepted_evidence_reason_codes") or ()
    if isinstance(failures, str):
        failures = [failures]
    if isinstance(needed, str):
        needed = [needed]
    if isinstance(queries, str):
        queries = [queries]
    upgrade = event_opportunity_verdict.explain_upgrade_path(components=components)
    verdict_copy = event_opportunity_verdict.build_verdict_aware_upgrade_downgrade_text(components)
    pack = event_source_packs.get_source_pack(pack_name)
    contract = event_source_registry.source_contract_metadata(
        components,
        evidence_rows=tuple(item for item in accepted_evidence if isinstance(item, Mapping)),
        assessment=assessment,
    )
    coverage_pack = _source_coverage_pack_for_card(
        pack_name,
        card_path=card_path,
        lineage_context=lineage_context,
    )
    if coverage_pack:
        failures = _coverage_pack_gap_lines(coverage_pack) or failures
    coverage_status = (
        coverage_pack.get("provider_coverage_status")
        if coverage_pack
        else (components.get("provider_coverage_status") or assessment.provider_coverage_status)
    )
    absence_meaningful = (
        coverage_pack.get("evidence_absence_meaningful")
        if coverage_pack and coverage_pack.get("evidence_absence_meaningful") is not None
        else components.get("evidence_absence_is_meaningful", assessment.evidence_absence_is_meaningful)
    )
    lines = [
        f"- Source pack: {pack_name}",
        f"- Coverage status: {coverage_status or 'unknown'}",
        f"- Evidence absence meaningful: {str(bool(absence_meaningful)).lower()}",
        f"- Source quality prior/cap: {components.get('source_quality_prior') or assessment.source_quality_prior}/{components.get('source_confidence_cap') or assessment.confidence_cap}",
        "- Source can prove: " + _source_contract_text(contract.get("source_can_prove")),
        "- Source cannot prove: " + _source_contract_text(contract.get("source_cannot_prove")),
        "- Relevant playbooks: " + _source_contract_text(contract.get("source_useful_playbooks")),
        f"- Evidence acquisition attempted: {str(bool(components.get('evidence_acquisition_attempted'))).lower()}",
        (
            f"- Evidence acquisition result: status={acquisition.get('status') or components.get('evidence_acquisition_status') or 'not_executed'} "
            f"evidence={components.get('acquisition_evidence_status') or acquisition.get('acquisition_evidence_status') or 'not available'} "
            f"accepted={acquisition.get('accepted', components.get('evidence_acquisition_accepted_count', 0))} "
            f"rejected={acquisition.get('rejected', components.get('evidence_acquisition_rejected_count', 0))} "
            f"final={acquisition.get('final_upgrade_status') or components.get('final_upgrade_status') or components.get('acquisition_upgrade_status') or 'unchanged'}"
        ),
        (
            f"- Final verdict after refresh: {components.get('final_opportunity_level') or components.get('opportunity_level') or 'not available'} "
            f"/ {components.get('final_opportunity_score') or components.get('opportunity_score_final') or 'n/a'} "
            f"source={components.get('final_verdict_source') or 'not available'}"
        ),
        "- Accepted evidence reasons: " + ("; ".join(str(item) for item in list(accepted_reasons or ())[:5]) if accepted_reasons else "none"),
        "- Accepted evidence samples: "
        + (
            "; ".join(_accepted_evidence_sample_text(item) for item in list(accepted_evidence or ())[:2])
            if accepted_evidence
            else "none"
        ),
        "- Article/source quality: " + _source_enrichment_summary(accepted_evidence),
        "- Evidence needed: " + ("; ".join(str(item) for item in list(needed or ())[:5]) if needed else "; ".join(pack.minimum_evidence[:4])),
        f"- Planned queries: {len(queries or ()) if isinstance(queries, Iterable) and not isinstance(queries, (str, bytes, Mapping)) else 0}",
        "- Provider/source gaps: " + ("; ".join(str(item) for item in list(failures or ())[:4]) if failures else "none"),
        "- What source would upgrade this: "
        + (
            verdict_copy.upgrade_text
            if _is_promoted_components(components)
            else (event_alpha_reason_text.humanize_event_alpha_reasons(upgrade.upgrade_requirements, limit=4) or "; ".join(pack.validation_requirements[:4]))
        ),
        "- What source would downgrade this: " + verdict_copy.downgrade_text,
    ]
    return lines


def _source_coverage_pack_for_card(
    pack_name: str,
    *,
    card_path: str | Path | None,
    lineage_context: Mapping[str, Any] | None,
) -> Mapping[str, Any] | None:
    json_paths: list[Path] = []
    if lineage_context:
        for key in ("source_coverage_json_path", "event_alpha_source_coverage_json_path"):
            value = lineage_context.get(key)
            if value:
                json_paths.append(Path(str(value)).expanduser())
    if card_path:
        path = Path(card_path).expanduser()
        json_paths.append(path.parent.parent / "event_alpha_source_coverage.json")
    seen: set[Path] = set()
    for path in json_paths:
        if path in seen or not path.exists():
            continue
        seen.add(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for pack in data.get("packs") or ():
            if isinstance(pack, Mapping) and str(pack.get("source_pack") or "") == str(pack_name or ""):
                return pack
    return None


def _coverage_pack_gap_lines(pack: Mapping[str, Any]) -> list[str]:
    items: list[str] = []
    for label, key in (
        ("missing", "providers_missing_for_confirmation"),
        ("degraded", "providers_degraded_for_confirmation"),
        ("missing", "missing_providers"),
        ("degraded", "degraded_or_backoff_providers"),
    ):
        values = pack.get(key)
        if isinstance(values, Iterable) and not isinstance(values, (str, bytes, Mapping)):
            for value in values:
                text = str(value or "").strip()
                if text:
                    items.append(f"{label}:{text}")
    reason = str(pack.get("coverage_gap_reason") or "").strip()
    if reason and reason not in {"none", "unknown"}:
        items.append(reason)
    return list(dict.fromkeys(items))


def _analyst_summary_lines(
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
) -> list[str]:
    components = _card_components(entry, alert)
    if not components:
        return []
    plan = components.get("evidence_acquisition_plan") if isinstance(components.get("evidence_acquisition_plan"), Mapping) else None
    summary = event_llm_evidence_planner.generate_analyst_summary(components, plan=plan)
    lines = [
        f"- Why surfaced: {summary.why_surfaced}",
        f"- Alertability: {summary.why_not_alertable}",
        f"- What would upgrade: {summary.what_would_upgrade}",
        f"- What would invalidate: {summary.what_would_invalidate}",
        "- Check next: " + "; ".join(summary.what_to_check_next[:4]),
    ]
    if summary.warnings:
        lines.append("- Analyst warnings: " + "; ".join(summary.warnings[:4]))
    return lines


def _source_contract_text(values: object, *, limit: int = 5) -> str:
    if values in (None, "", [], {}, ()):
        return "none"
    if isinstance(values, str):
        items = [part.strip() for part in values.replace(";", ",").split(",") if part.strip()]
    elif isinstance(values, Mapping):
        items = [str(value) for value in values.values() if str(value)]
    elif isinstance(values, Iterable):
        items = [str(value) for value in values if str(value)]
    else:
        items = [str(values)]
    items = list(dict.fromkeys(items))
    if not items:
        return "none"
    shown = [_human_contract_value(item) for item in items[:limit]]
    suffix = f"; +{len(items) - limit} more" if len(items) > limit else ""
    return "; ".join(shown) + suffix


def _accepted_evidence_sample_text(item: object) -> str:
    if not isinstance(item, Mapping):
        return str(item)[:160]
    title = str(item.get("title") or item.get("source_url") or "evidence")[:120]
    details: list[str] = []
    tags = item.get("currency_tags")
    if tags:
        if isinstance(tags, str):
            tag_text = tags
        elif isinstance(tags, Iterable) and not isinstance(tags, (bytes, bytearray, Mapping)):
            tag_text = ",".join(str(tag) for tag in list(tags)[:4] if str(tag))
        else:
            tag_text = str(tags)
        if tag_text:
            details.append(f"tags={tag_text}")
    if item.get("cryptopanic_currency_tag_match"):
        details.append("tag_match=true")
    exchange = item.get("exchange")
    if exchange:
        details.append(f"exchange={exchange}")
    pairs = item.get("announcement_pairs")
    if pairs:
        pair_text = pairs if isinstance(pairs, str) else ",".join(str(pair) for pair in list(pairs)[:4] if str(pair))
        if pair_text:
            details.append(f"pairs={pair_text}")
    contracts = item.get("announcement_contracts")
    if contracts:
        contract_text = contracts if isinstance(contracts, str) else ",".join(str(contract) for contract in list(contracts)[:4] if str(contract))
        if contract_text:
            details.append(f"contracts={contract_text}")
    event_time = item.get("structured_event_time")
    if event_time:
        details.append(f"event_time={event_time}")
    category = item.get("calendar_event_category")
    if category:
        details.append(f"category={category}")
    unlock_pct = item.get("unlock_pct_circulating")
    if unlock_pct not in (None, ""):
        details.append(f"unlock_pct={unlock_pct}")
    materiality = item.get("unlock_materiality")
    if materiality:
        details.append(f"materiality={materiality}")
    enrichment = item.get("source_enrichment") if isinstance(item.get("source_enrichment"), Mapping) else {}
    quality_status = enrichment.get("article_quality_status")
    if quality_status:
        details.append(f"article={quality_status}")
    return title + (f" ({'; '.join(details)})" if details else "")


def _source_enrichment_summary(items: object) -> str:
    if not isinstance(items, Iterable) or isinstance(items, (str, bytes, Mapping)):
        return "not available"
    parts: list[str] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        enrichment = item.get("source_enrichment") if isinstance(item.get("source_enrichment"), Mapping) else {}
        status = enrichment.get("article_quality_status")
        cleaner = enrichment.get("cleaner_version")
        ratio = enrichment.get("boilerplate_ratio")
        triage = enrichment.get("source_triage_decision")
        warnings = enrichment.get("warnings") or ()
        if status:
            detail = f"{status}"
            if cleaner:
                detail += f" cleaner={cleaner}"
            if ratio not in (None, ""):
                detail += f" boilerplate={ratio}"
            if triage:
                detail += f" triage={triage}"
            if warnings:
                detail += " warnings=" + ",".join(str(warning) for warning in list(warnings)[:3])
            parts.append(detail)
    return "; ".join(parts[:3]) if parts else "not available"


def _human_contract_value(value: object) -> str:
    return str(value).replace("_", " ")


def _market_lines(entry: event_watchlist.EventWatchlistEntry | None, alert: Mapping[str, Any] | None) -> list[str]:
    snapshot = dict(entry.latest_market_snapshot if entry else {})
    if alert is not None:
        components = _card_components(entry, alert)
        for key in ("latest_market_snapshot", "market_snapshot"):
            if isinstance(components.get(key), Mapping):
                snapshot.update(dict(components[key]))
        if isinstance(components.get("market_state_snapshot"), Mapping):
            snapshot.setdefault("market_state_snapshot", dict(components["market_state_snapshot"]))
        for key in ("market_price", "return_24h", "return_72h", "return_7d", "volume_24h", "market_cap"):
            if alert.get(key) is not None:
                snapshot[key] = alert.get(key)
    else:
        components = _card_components(entry, alert)
    integrated_level = components.get("integrated_market_confirmation_level")
    integrated_score = components.get("integrated_market_confirmation_score")
    integrated_reaction = components.get("integrated_market_reaction_confirmation")
    integrated_source = components.get("integrated_market_context_source")
    integrated_freshness = components.get("integrated_market_freshness_status")
    market_state = components.get("market_state_class") or components.get("market_state")
    market_requirements_met = components.get("market_requirements_met")
    market_level = components.get("market_confirmation_level") or components.get("market_reaction_confirmation")
    market_score = components.get("market_confirmation_score")
    freshness = components.get("market_data_freshness") or components.get("market_context_freshness_status")
    context_source = components.get("market_context_source")
    context_age = _format_market_context_age(components)
    lines: list[str] = []
    if integrated_level or integrated_reaction or market_state:
        lines.append(
            "- Integrated market state: "
            f"{market_state or integrated_reaction or 'unknown'} "
            f"(confirmation={integrated_level or integrated_reaction or 'not applicable'}, "
            f"score={integrated_score if integrated_score is not None else 'n/a'}, "
            f"requirements_met={str(bool(market_requirements_met)).lower() if market_requirements_met is not None else 'unknown'}, "
            f"freshness={integrated_freshness or 'unknown'}, source={integrated_source or 'integrated_market_state'})"
        )
    if not snapshot and (market_level or market_score is not None or freshness or context_source):
        if not (str(market_level or "").casefold() in {"", "none", "missing", "unknown"} and lines):
            lines.append(f"- Market confirmation: {market_level or 'not available'} / {market_score if market_score is not None else 'n/a'}")
        lines.extend([
            f"- Market freshness: {freshness or 'not available'}",
            f"- Market context source: {context_source or 'not available'} (age={context_age})",
            "- Market snapshot: computed from refresh summary; raw snapshot not stored.",
        ])
        return lines
    if not snapshot:
        return lines or ["- Market data: not available."]
    if (market_level or market_score is not None) and not (
        str(market_level or "").casefold() in {"", "none", "missing", "unknown"} and lines
    ):
        lines.append(f"- Market confirmation: {market_level or 'not available'} / {market_score if market_score is not None else 'n/a'}")
    if freshness or context_source:
        lines.append(f"- Market freshness/source: {freshness or 'not available'} / {context_source or 'not available'} (age={context_age})")
    if snapshot.get("summary_only"):
        lines.append("- Market snapshot: computed from refresh summary; raw snapshot not stored.")
    snapshot_unit = event_market_units.infer_return_unit(snapshot, default=event_market_units.RETURN_UNIT_FRACTION)
    for key in ("price", "market_price", "return_24h", "return_72h", "return_7d", "volume_24h", "market_cap"):
        if snapshot.get(key) is not None:
            if key.startswith("return_"):
                lines.append(f"- {key}: {event_market_units.format_return_pct(snapshot.get(key), snapshot_unit)}")
            else:
                lines.append(f"- {key}: {snapshot.get(key)}")
    return lines or ["- Market data: not available."]


def _derivatives_supply_liquidity_lines(
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
) -> list[str]:
    components = _card_components(entry, alert)
    derivatives_state = components.get("derivatives_state_snapshot")
    if not isinstance(derivatives_state, Mapping):
        derivatives_state = components.get("derivatives_snapshot") if isinstance(components.get("derivatives_snapshot"), Mapping) else {}
    unlock_event = components.get("unlock_event") if isinstance(components.get("unlock_event"), Mapping) else {}
    crowding = components.get("crowding_class") or components.get("derivatives_crowding")
    fade_readiness = components.get("fade_readiness")
    lines: list[str] = []
    if derivatives_state or crowding or fade_readiness:
        lines.append(f"- Derivatives crowding: {_display_text(crowding) or 'not classified'}")
        lines.append(f"- Fade readiness: {_display_text(fade_readiness) or 'not fade-ready'}")
        lines.append(
            "- Derivatives confirmation: "
            f"{components.get('derivatives_confirmation_level') or derivatives_state.get('freshness_status') or 'classified'} / "
            f"{components.get('derivatives_confirmation_score') if components.get('derivatives_confirmation_score') is not None else 'n/a'} "
            f"(freshness={components.get('derivatives_freshness_status') or derivatives_state.get('freshness_status') or 'unknown'})"
        )
        if components.get("derivatives_warning_codes") or components.get("warnings"):
            warnings = _list_strings(components.get("derivatives_warning_codes") or components.get("warnings"))
            if warnings:
                lines.append("- Derivatives warnings: " + "; ".join(warnings[:6]))
    else:
        lines.append("- Derivatives crowding: not available.")
        lines.append("- Derivatives confirmation: not available / n/a (freshness=unknown)")
    lines.extend([
        f"- DEX liquidity confirmation: {_score(entry, alert, 'dex_liquidity_level')} / {_score(entry, alert, 'dex_liquidity_score')} "
        f"(freshness={_score(entry, alert, 'dex_freshness_status')})",
        f"- Protocol metrics confirmation: {_score(entry, alert, 'protocol_metrics_level')} / {_score(entry, alert, 'protocol_metrics_score')} "
        f"(freshness={_score(entry, alert, 'protocol_metrics_freshness_status')})",
    ])
    if unlock_event:
        lines.append(
            "- Supply pressure: structured unlock evidence "
            f"type={unlock_event.get('unlock_type') or unlock_event.get('event_type') or 'unknown'} "
            f"pct_circ={unlock_event.get('unlock_pct_circulating_supply') if unlock_event.get('unlock_pct_circulating_supply') is not None else 'n/a'} "
            f"vs_adv={unlock_event.get('unlock_vs_30d_adv') if unlock_event.get('unlock_vs_30d_adv') is not None else 'n/a'}"
        )
    else:
        lines.append(f"- Supply pressure: {_score(entry, alert, 'supply_pressure')}")
    lines.append(f"- Cluster confidence: {_score(entry, alert, 'cluster_confidence')}")
    return lines


def _opportunity_lane_lines(entry: event_watchlist.EventWatchlistEntry | None, alert: Mapping[str, Any] | None) -> list[str]:
    components = _card_components(entry, alert)
    lane = components.get("opportunity_type")
    market_state = components.get("market_state") or components.get("market_state_class")
    snapshot = components.get("market_state_snapshot") if isinstance(components.get("market_state_snapshot"), Mapping) else {}
    if not lane and not market_state and not snapshot:
        return []
    confirms = _list_value(components.get("opportunity_type_what_confirms") or components.get("what_confirms"))
    invalidates = _list_value(components.get("opportunity_type_what_invalidates") or components.get("what_invalidates"))
    why_not = _list_value(components.get("opportunity_type_why_not_alertable") or components.get("why_not_alertable"))
    evidence = _list_value(components.get("opportunity_type_evidence"))
    lines = [
        f"- Opportunity type: {lane or 'not classified'}",
        f"- Why now: {components.get('opportunity_type_why_now') or components.get('why_now') or 'not available'}",
        f"- Market state: {market_state or 'not available'}",
        f"- Evidence: {'; '.join(evidence[:4]) if evidence else 'not available'}",
        f"- What confirms: {'; '.join(confirms[:4]) if confirms else 'not available'}",
        f"- What invalidates: {'; '.join(invalidates[:4]) if invalidates else 'not available'}",
    ]
    if why_not:
        lines.append(f"- Why not alertable: {'; '.join(why_not[:4])}")
    if snapshot:
        compact = []
        snapshot_unit = event_market_units.infer_return_unit(snapshot, default=event_market_units.RETURN_UNIT_PERCENT_POINTS)
        for key in (
            "return_5m",
            "return_15m",
            "return_1h",
            "return_4h",
            "return_24h",
            "relative_return_vs_btc",
            "volume_turnover_zscore",
            "open_interest_delta",
            "funding_level",
            "liquidation_imbalance",
            "event_age_hours",
            "freshness_status",
        ):
            value = snapshot.get(key)
            if value not in (None, "", [], {}, ()):
                if key.startswith("return_") or key.startswith("relative_return_") or key in {"open_interest_delta", "funding_level"}:
                    compact.append(f"{key}={event_market_units.format_return_pct(value, snapshot_unit)}")
                else:
                    compact.append(f"{key}={value}")
        lines.append(f"- Market state snapshot: {'; '.join(compact[:8]) if compact else 'present but sparse'}")
    lines.append("- Research-only / not a trade signal.")
    return lines


def _impact_hypothesis_lines(entry: event_watchlist.EventWatchlistEntry | None) -> list[str]:
    if entry is None:
        return []
    components = dict(entry.latest_score_components or {})
    has_hypothesis_context = entry.relationship_type == "impact_hypothesis" or any(
        components.get(key) not in (None, "", [], {}, ())
        for key in (
            "hypothesis_id",
            "primary_hypothesis_id",
            "supporting_hypothesis_ids",
            "main_frame_type",
            "main_frame_subject",
            "impact_path_reason",
        )
    )
    if not has_hypothesis_context:
        return []
    validated_asset = components.get("validated_asset") if isinstance(components.get("validated_asset"), Mapping) else {}
    validated_symbol = components.get("validated_symbol") or validated_asset.get("symbol") or entry.symbol
    validated_coin_id = components.get("validated_coin_id") or validated_asset.get("coin_id") or entry.coin_id
    candidate_symbols = components.get("candidate_symbols") or []
    validation_reasons = components.get("validation_reasons") or components.get("validation_reason") or []
    if isinstance(validation_reasons, str):
        validation_reasons = [validation_reasons]
    gate_line = _impact_hypothesis_quality_gate_line(entry, components)
    impact_path_reason = components.get("impact_path_reason") or _canonical_reason_from_components(components) or "not available"
    impact_path_type = components.get("impact_path_type") or components.get("primary_impact_path") or "not available"
    candidate_role = components.get("candidate_role") or "not available"
    asset_kind = components.get("asset_kind") or "unknown"
    role_source = components.get("role_source") or components.get("asset_role_source") or "unknown"
    identity_confidence = components.get("identity_confidence")
    identity_evidence = components.get("identity_evidence") or []
    collision_risk = components.get("collision_risk") or "none"
    role_capabilities = components.get("role_capabilities") or {}
    role_validation_failures = components.get("role_validation_failures") or []
    incident_id = components.get("incident_id") or "unknown"
    canonical_incident_name = components.get("canonical_incident_name") or "unknown"
    event_archetype = components.get("event_archetype") or "unknown"
    primary_subject = components.get("primary_subject") or "unknown"
    affected_ecosystem = components.get("affected_ecosystem") or "unknown"
    cause_status = components.get("cause_status") or "unknown"
    main_frame_type = components.get("main_frame_type") or "unknown"
    main_frame_role = components.get("main_frame_role") or "unknown"
    main_frame_subject = components.get("main_frame_subject") or "unknown"
    main_frame_actor = components.get("main_frame_actor") or "unknown"
    main_frame_object = components.get("main_frame_object") or "unknown"
    main_frame_quote = components.get("main_frame_evidence_quote") or "none"
    frame_status = components.get("frame_status") or "unknown"
    selected_main_reason = components.get("selected_main_catalyst_reason") or "unknown"
    rule_predicted_path = components.get("rule_predicted_impact_path") or "unknown"
    llm_predicted_path = components.get("llm_predicted_main_frame_type") or "unknown"
    frame_disagreement = components.get("frame_rule_disagreement")
    disagreement_resolution = components.get("disagreement_resolution") or "unknown"
    background_context_summary = components.get("background_context_summary") or "none"
    negated_frame_ids = components.get("negated_frame_ids") or []
    corrective_frame_ids = components.get("corrective_frame_ids") or []
    rejected_impact_paths = components.get("rejected_impact_paths") or []
    frame_summary = components.get("frame_summary") or []
    claim_polarities = components.get("claim_polarities") or []
    claim_history = components.get("claim_history") or []
    independent_source_domains = components.get("independent_source_domains") or components.get("source_domains") or []
    conflicting_claims = components.get("conflicting_claims") or []
    role_confidence = components.get("role_confidence")
    role_evidence = components.get("role_evidence") or []
    market_context_source = components.get("market_context_source") or "not available"
    market_context_age = _format_market_context_age(components)
    market_context_quality = (
        components.get("market_context_freshness_status")
        or components.get("market_context_data_quality")
        or "unknown"
    )
    freshness_cap = components.get("market_context_freshness_cap_applied")
    market_reaction_confirmed = components.get("market_reaction_confirmed")
    causal_mechanism_confirmed = components.get("causal_mechanism_confirmed")
    incident_confidence = components.get("incident_confidence")
    impact_path_strength = components.get("impact_path_strength") or _canonical_strength_from_components(components) or "not available"
    opportunity_score_v2 = components.get("opportunity_score_v2")
    evidence_specificity = components.get("evidence_specificity_score")
    verdict_copy = event_opportunity_verdict.build_verdict_aware_upgrade_downgrade_text(components)
    why_digest_ineligible = components.get("why_digest_ineligible") or verdict_copy.missing_evidence_text
    digest_eligible = components.get("digest_eligible_by_impact_path")
    if digest_eligible is None and _is_promoted_components(components):
        digest_eligible = True
    evidence_quality_score = components.get("evidence_quality_score")
    source_class = components.get("source_class") or "unknown"
    evidence_specificity_class = components.get("evidence_specificity") or "unknown"
    market_confirmation_score = components.get("market_confirmation_score")
    market_confirmation_level = components.get("market_confirmation_level") or "not available"
    market_data_freshness = components.get("market_data_freshness") or components.get("market_context_freshness_status") or "not available"
    market_reaction_confirmation = components.get("market_reaction_confirmation") or market_confirmation_level
    market_confirmation_summary = components.get("market_confirmation_summary") or _canonical_market_summary_from_components(components) or "not available"
    integrated_market_level = components.get("integrated_market_confirmation_level")
    if integrated_market_level:
        market_confirmation_level = integrated_market_level
        market_confirmation_score = components.get("integrated_market_confirmation_score")
        market_reaction_confirmation = components.get("integrated_market_reaction_confirmation") or integrated_market_level
        market_context_source = components.get("integrated_market_context_source") or market_context_source
        market_data_freshness = components.get("integrated_market_freshness_status") or market_data_freshness
        market_context_quality = components.get("integrated_market_freshness_status") or market_context_quality
        market_confirmation_summary = (
            f"{integrated_market_level} / "
            f"{market_confirmation_score if market_confirmation_score is not None else 'n/a'}; "
            f"freshness={market_data_freshness} source={market_context_source}"
        )
    opportunity_score_final = components.get("opportunity_score_final")
    opportunity_level = components.get("opportunity_level") or "unknown"
    final_opportunity_score = components.get("final_opportunity_score") or opportunity_score_final
    final_opportunity_level = components.get("final_opportunity_level") or opportunity_level
    verdict_reasons = components.get("opportunity_verdict_reasons") or []
    missing_requirements = components.get("missing_requirements") or []
    manual_verification_items = components.get("manual_verification_items") or []
    if isinstance(verdict_reasons, str):
        verdict_reasons = [verdict_reasons]
    if isinstance(missing_requirements, str):
        missing_requirements = [missing_requirements]
    if isinstance(manual_verification_items, str):
        manual_verification_items = [manual_verification_items]
    why_not_promoted = components.get("why_not_promoted") or []
    if isinstance(why_not_promoted, str):
        why_not_promoted = [why_not_promoted]
    upgrade = event_opportunity_verdict.explain_upgrade_path(components=components)
    if _is_promoted_components(components):
        upgrade_text = verdict_copy.upgrade_text
        downgrade_text = verdict_copy.downgrade_text
    else:
        upgrade_text = event_alpha_reason_text.humanize_event_alpha_reasons(upgrade.upgrade_requirements, limit=6) or verdict_copy.upgrade_text
        downgrade_text = event_alpha_reason_text.humanize_event_alpha_reasons(upgrade.downgrade_warnings, limit=6) or verdict_copy.downgrade_text
    local_only_due_to_weak_cooccurrence = (
        final_opportunity_level in {"local_only", "exploratory", "unknown", ""}
        and (
            "impact_path_not_validated" in gate_line
            or "weak_validated_local_only" in gate_line
            or str(why_digest_ineligible or "none").strip().casefold() not in {"", "none", "not available"}
        )
    )
    lines = [
        f"- Validated asset: {validated_symbol or 'unknown'}/{validated_coin_id or 'unknown'}",
        f"- Incident: {canonical_incident_name} ({incident_id})",
        f"- Incident relevance: {components.get('incident_relevance_status') or 'unknown'} "
        f"score={components.get('incident_relevance_score') if components.get('incident_relevance_score') is not None else 'n/a'}",
        f"- Canonical persistence reason: {components.get('canonical_persistence_reason') or 'unknown'}",
        f"- Incident relevance reasons: {'; '.join(str(item) for item in (components.get('incident_relevance_reasons') or [])[:4]) if components.get('incident_relevance_reasons') else 'none'}",
        f"- Event archetype: {event_archetype}",
        f"- Main catalyst: {main_frame_type} ({main_frame_role})",
        f"- Frame status: {frame_status}",
        f"- Main catalyst subject/actor/object: {main_frame_subject} / {main_frame_actor} / {main_frame_object}",
        f"- Main catalyst evidence: {main_frame_quote}",
        f"- Main catalyst selected because: {selected_main_reason}",
        f"- Rule vs LLM frame: rule={rule_predicted_path} llm={llm_predicted_path} "
        f"disagreement={str(bool(frame_disagreement)).lower() if frame_disagreement is not None else 'unknown'} "
        f"resolution={disagreement_resolution}",
        f"- Background context: {background_context_summary}",
        f"- Negated/corrective frames: {len(negated_frame_ids) + len(corrective_frame_ids)}",
        f"- Rejected/background impact paths: {'; '.join(str(item) for item in rejected_impact_paths[:4]) if rejected_impact_paths else 'none'}",
        f"- Catalyst frame evidence: {_frame_summary_value(frame_summary)}",
        f"- Primary subject: {primary_subject}",
        f"- Affected ecosystem: {affected_ecosystem}",
        f"- Cause status: {cause_status}",
        f"- Incident confidence: {incident_confidence if incident_confidence is not None else 'n/a'}",
        f"- Claim polarity: {', '.join(str(item) for item in claim_polarities[:6]) if claim_polarities else 'unknown'}",
        f"- Claim history: {_claim_history_summary(claim_history)}",
        f"- Independent source domains: {', '.join(str(item) for item in independent_source_domains[:6]) if independent_source_domains else 'none'}",
        f"- Conflicting claims: {'; '.join(str(item) for item in conflicting_claims[:4]) if conflicting_claims else 'none'}",
        f"- Original sector hypothesis: {', '.join(str(item) for item in (components.get('candidate_sectors') or [])[:6]) or components.get('hypothesis_scope') or 'unknown'}",
        f"- Candidate source: {entry.latest_source or 'impact_hypothesis'}",
        f"- Candidate Discovery Origin: {components.get('candidate_source') or components.get('source') or entry.latest_source or 'impact_hypothesis'}",
        f"- Candidate symbols considered: {', '.join(str(item) for item in candidate_symbols[:8]) if candidate_symbols else 'none'}",
        f"- Playbook: {entry.latest_playbook_type or 'impact_hypothesis'}",
        f"- Impact path type: {impact_path_type}",
        f"- Candidate role: {candidate_role}",
        f"- Asset kind: {asset_kind}",
        f"- Role source: {role_source}",
        f"- Identity confidence: {identity_confidence if identity_confidence is not None else 'n/a'}",
        f"- Identity evidence: {_display_list_value(identity_evidence)}",
        f"- Collision risk: {collision_risk}",
        f"- Role capabilities: {_role_capabilities_line(role_capabilities)}",
        f"- Role validation failures: {_display_list_value(role_validation_failures)}",
        f"- Candidate role confidence: {role_confidence if role_confidence is not None else 'n/a'}",
        f"- Candidate role evidence: {'; '.join(str(item) for item in role_evidence[:4]) if role_evidence else 'none'}",
        f"- Impact path strength: {impact_path_strength}",
        f"- Impact path reason: {impact_path_reason}",
        f"- Opportunity score v2: {opportunity_score_v2 if opportunity_score_v2 is not None else 'n/a'}",
        f"- Final opportunity verdict: {final_opportunity_level} / {final_opportunity_score if final_opportunity_score is not None else 'n/a'}",
        f"- Final verdict source: {components.get('final_verdict_source') or 'initial'} ({components.get('final_verdict_reason') or 'no refresh override'})",
        f"- Source/evidence specificity: {evidence_specificity if evidence_specificity is not None else 'n/a'}",
        f"- Evidence quality: {source_class}/{evidence_specificity_class} / {evidence_quality_score if evidence_quality_score is not None else 'n/a'}",
        f"- Market confirmation: {market_confirmation_level} / {market_confirmation_score if market_confirmation_score is not None else 'n/a'}",
        f"- Market freshness: {market_data_freshness}",
        f"- Market reaction confirmation: {market_reaction_confirmation}",
        f"- Market context source: {market_context_source} ({market_context_quality}; age={market_context_age}; cap_applied={str(bool(freshness_cap)).lower()})",
        "- Targeted market refresh: "
        + _targeted_market_refresh_line(components),
        f"- Market reaction confirmed: {str(bool(market_reaction_confirmed)).lower() if market_reaction_confirmed is not None else 'unknown'}",
        f"- Causal mechanism confirmed: {str(bool(causal_mechanism_confirmed)).lower() if causal_mechanism_confirmed is not None else 'unknown'}",
        f"- Market summary: {market_confirmation_summary}",
        f"- Impact path digest eligible: {str(bool(digest_eligible)).lower() if digest_eligible is not None else 'unknown'}",
        f"- Missing evidence / gate failure: {why_digest_ineligible}",
        f"- Opportunity verdict reasons: {'; '.join(str(item) for item in verdict_reasons[:4]) if verdict_reasons else 'none'}",
        f"- Missing requirements: {'; '.join(str(item) for item in missing_requirements[:4]) if missing_requirements else 'none'}",
        f"- Quality gate: {gate_line}",
        f"- Local-only due to weak co-occurrence: {str(local_only_due_to_weak_cooccurrence).lower()}",
        f"- Why promoted/local-only: {_impact_hypothesis_promotion_line(entry, components, gate_line)}",
        "- Safety label: catalyst link validated, but this is not a calibrated strategy or trade signal.",
        "- Why it may be wrong: " + _impact_hypothesis_wrong_line(components),
        "- What to verify manually: "
        + (
            "; ".join(str(item) for item in manual_verification_items[:4])
            if manual_verification_items
            else "independent catalyst source, asset identity, liquidity/organic volume, and whether the catalyst actually affects this token."
        ),
        "- What would upgrade this candidate: "
        + upgrade_text,
        "- What would invalidate this candidate: "
        + downgrade_text,
    ]
    if validation_reasons:
        lines.append("- Validation evidence: " + "; ".join(str(item) for item in validation_reasons[:4]))
    if why_not_promoted:
        lines.append(
            "- Why not promoted diagnostics: "
            + event_alpha_reason_text.humanize_event_alpha_reasons(why_not_promoted, limit=4)
        )
    return lines


def _impact_hypothesis_quality_gate_line(
    entry: event_watchlist.EventWatchlistEntry,
    components: Mapping[str, Any],
) -> str:
    """Return operator-facing quality gate text for a card context block.

    Canonical core cards already carry final quality-gated route fields. Using
    the raw validated-hypothesis router gate on their synthetic card entry can
    create stale local-only text because the synthetic row is no longer an
    ``impact_hypothesis`` relationship row.
    """
    final_route = str(components.get("final_route_after_quality_gate") or "").strip()
    if components.get("core_opportunity_id") and final_route:
        route_upper = final_route.upper()
        if event_alpha_router.route_value_is_alertable(final_route):
            return f"passed final quality gate ({route_upper})"
        if route_upper in {"SUPPRESS_DUPLICATE", "SUPPRESS_IN_FLIGHT"}:
            return f"passed quality gate; route suppressed ({route_upper})"
        reason = (
            components.get("quality_gate_block_reason")
            or components.get("why_digest_ineligible")
            or components.get("why_local_only")
            or components.get("final_opportunity_level")
            or components.get("opportunity_level")
            or route_upper
        )
        return f"local-only: {reason}"
    gate_block = event_alpha_router.validated_hypothesis_digest_block_reason(entry)
    return "passed for capped research digest" if gate_block is None else f"local-only: {gate_block}"


def _impact_hypothesis_promotion_line(
    entry: event_watchlist.EventWatchlistEntry,
    components: Mapping[str, Any],
    gate_line: str,
) -> str:
    if entry.suppressed_reason:
        return entry.suppressed_reason
    final_reason = components.get("final_verdict_reason")
    final_level = str(components.get("final_opportunity_level") or components.get("opportunity_level") or "").strip()
    final_route = str(components.get("final_route_after_quality_gate") or "").strip()
    if final_reason and (final_level or final_route):
        return str(final_reason)
    if gate_line.startswith("passed"):
        return f"promoted by final verdict ({final_level or final_route or 'allowed'})"
    return f"kept local-only by final verdict ({final_level or final_route or 'store-only'})"


def _impact_hypothesis_wrong_line(components: Mapping[str, Any]) -> str:
    impact_path = str(components.get("impact_path_type") or "").casefold()
    frame = str(components.get("main_frame_type") or components.get("event_archetype") or "").casefold()
    role = str(components.get("candidate_role") or "").casefold()
    if impact_path == "strategic_investment_or_valuation" or frame == "acquisition_or_stake":
        return "talks are denied, the source is corrected, no market reaction appears, or the valuation is not relevant to token value."
    if impact_path in {"venue_value_capture", "proxy_exposure"} or role == "proxy_venue":
        return "the venue/exposure claim is denied, source evidence is corrected, or attention and market confirmation fade."
    if impact_path == "market_dislocation_unknown" or frame == "market_dislocation_unknown":
        return "cause remains unknown, no exploit/catalyst is confirmed, or the move mean-reverts without independent evidence."
    return "validation may be source-thin, asset link may be narrative-only, and the catalyst impact may not move this token."


def _format_market_context_age(components: Mapping[str, Any]) -> str:
    age_hours = _float_value(components.get("market_context_age_hours"))
    if age_hours is None:
        age_seconds = _float_value(components.get("market_context_age_seconds") or components.get("market_context_age"))
        if age_seconds is not None:
            age_hours = age_seconds / 3600.0
    if age_hours is None:
        return "n/a"
    if age_hours < 1:
        return f"{age_hours * 60:.0f}m"
    return f"{age_hours:.1f}h"


def _targeted_market_refresh_line(components: Mapping[str, Any]) -> str:
    attempted = components.get("market_refresh_attempted")
    if attempted in (None, "", [], {}):
        return "not attempted"
    success = bool(components.get("market_refresh_success"))
    provider = components.get("market_refresh_provider") or components.get("market_context_source") or "unknown"
    before_level = components.get("opportunity_level_before_refresh") or components.get("opportunity_level_before") or "unknown"
    after_level = components.get("opportunity_level_after_refresh") or components.get("opportunity_level_after") or components.get("opportunity_level") or "unknown"
    before_score = components.get("opportunity_score_before_refresh") or components.get("opportunity_score_before")
    after_score = components.get("opportunity_score_after_refresh") or components.get("opportunity_score_after") or components.get("opportunity_score_final")
    before_market = components.get("market_confirmation_before_refresh") or components.get("market_confirmation_before")
    after_market = components.get("market_confirmation_after_refresh") or components.get("market_confirmation_after") or components.get("market_confirmation_score")
    status = (
        components.get("refresh_upgrade_status")
        or components.get("refresh_upgrade_reason")
        or components.get("upgrade_reason")
        or components.get("no_upgrade_reason")
        or "pending"
    )
    return (
        f"attempted={str(bool(attempted)).lower()} success={str(success).lower()} "
        f"provider={provider} verdict={before_level}->{after_level} "
        f"score={before_score if before_score is not None else 'n/a'}->{after_score if after_score is not None else 'n/a'} "
        f"market={before_market if before_market is not None else 'n/a'}->{after_market if after_market is not None else 'n/a'} "
        f"status={status}"
    )


def _float_value(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _quality_gate_lines(
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
    decision: event_alpha_router.EventAlphaRouteDecision | None,
) -> list[str]:
    components = dict(entry.latest_score_components if entry else {})
    if alert is not None:
        components.update({key: value for key, value in alert.items() if value not in (None, "", [], {})})
    requested = (
        getattr(decision, "requested_route_before_quality_gate", None)
        if decision is not None
        else components.get("requested_route_before_quality_gate")
    ) or components.get("route") or "unknown"
    final = (
        getattr(decision, "final_route_after_quality_gate", None)
        if decision is not None
        else components.get("final_route_after_quality_gate")
    ) or components.get("route") or "unknown"
    final_tier = components.get("final_tier_after_quality_gate") or components.get("tier") or "unknown"
    classification = components.get("snapshot_quality_classification") or "unknown"
    block = (
        getattr(decision, "quality_gate_block_reason", None)
        if decision is not None
        else components.get("quality_gate_block_reason")
    ) or "none"
    opportunity_level = (
        getattr(decision, "opportunity_level", None)
        if decision is not None
        else components.get("opportunity_level")
    ) or _value(entry, alert, "opportunity_level", "opportunity_level") or "unknown"
    opportunity_score = (
        getattr(decision, "opportunity_score_final", None)
        if decision is not None
        else components.get("opportunity_score_final")
    )
    if opportunity_score is None:
        opportunity_score = _value(entry, alert, "opportunity_score_final", "opportunity_score_final") or "n/a"
    allowed = str(block) == "none" and str(final) == str(requested)
    return [
        f"- Requested route: {requested}",
        f"- Final route: {final}",
        f"- Final tier: {final_tier}",
        f"- Snapshot classification: {classification}",
        f"- Result: {'allowed' if allowed else 'blocked/downgraded'}",
        f"- Block reason: {block}",
        f"- Opportunity verdict: {opportunity_level} / {opportunity_score}",
        f"- Why blocked / allowed: {block if block != 'none' else 'opportunity verdict permits the final route'}",
    ]


def _monitor_lines(row: event_watchlist_monitor.EventWatchlistMonitorRow | Mapping[str, Any] | None) -> list[str]:
    if row is None:
        return [
            "- No watchlist monitor row found.",
            "- Monitor data is observation-only and cannot create TRIGGERED_FADE.",
        ]
    hints = _monitor_value(row, "state_transition_hints") or ()
    if isinstance(hints, str):
        hints = tuple(part.strip() for part in hints.split(",") if part.strip())
    lines = [
        f"- Material update: {str(bool(_monitor_value(row, 'material_update'))).lower()}",
        f"- State transition hints: {', '.join(str(item) for item in hints) if hints else 'none'}",
        f"- Return 24h / 72h / 7d: {_monitor_value(row, 'return_24h')} / {_monitor_value(row, 'return_72h')} / {_monitor_value(row, 'return_7d')}",
        f"- Volume z-score / volume-to-market-cap: {_monitor_value(row, 'volume_zscore_24h')} / {_monitor_value(row, 'volume_to_market_cap')}",
        f"- Derivatives crowding: {_monitor_value(row, 'derivatives_crowding')}",
        f"- Supply pressure: {_monitor_value(row, 'supply_pressure')}",
        f"- Event countdown hours: {_monitor_value(row, 'event_countdown_hours') or 'n/a'}",
        f"- Event age hours: {_monitor_value(row, 'event_age_hours') or 'n/a'}",
        "- Monitor data is observation-only and cannot create TRIGGERED_FADE.",
    ]
    return lines


def _lifecycle_lines(
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
    monitor_row: event_watchlist_monitor.EventWatchlistMonitorRow | Mapping[str, Any] | None,
    feedback_rows: list[Mapping[str, Any]],
    outcome: Mapping[str, Any] | None,
) -> list[str]:
    lines: list[str] = []
    timeline_fields = (
        ("first_seen", "first_seen_at"),
        ("radar", "first_radar_at"),
        ("watchlisted", "first_watchlisted_at"),
        ("high_priority", "first_high_priority_at"),
        ("event_passed", "first_event_passed_at"),
        ("armed", "first_armed_at"),
        ("triggered", "first_triggered_at"),
        ("invalidated", "first_invalidated_at"),
        ("expired", "first_expired_at"),
        ("last_seen", "last_seen_at"),
    )
    if entry is not None:
        for label, field in timeline_fields:
            value = getattr(entry, field, None)
            if value:
                lines.append(f"- {label}: {value}")
    if alert is not None and alert.get("observed_at"):
        lines.append(f"- alert_snapshot: {alert.get('observed_at')}")
    if monitor_row is not None:
        hints = _monitor_value(monitor_row, "state_transition_hints") or ()
        if isinstance(hints, str):
            hints = tuple(part.strip() for part in hints.split(",") if part.strip())
        lines.append(
            "- latest_monitor: "
            f"material={str(bool(_monitor_value(monitor_row, 'material_update'))).lower()} "
            f"hints={', '.join(str(item) for item in hints) if hints else 'none'}"
        )
    if feedback_rows:
        for row in sorted(feedback_rows, key=lambda item: str(item.get("marked_at") or ""), reverse=True)[:5]:
            lines.append(
                f"- feedback: {row.get('label') or 'unknown'} at {row.get('marked_at') or 'unknown'} "
                f"by {row.get('marked_by') or 'unknown'}"
            )
    else:
        lines.append("- feedback: none")
    if outcome is not None and any(outcome.get(field) not in (None, "") for field in (
        "primary_horizon_return",
        "return_24h",
        "return_72h",
        "return_7d",
        "direction_hit",
        "mfe_mae_ratio",
    )):
        lines.append(
            "- outcome: "
            f"primary={_display_pct(outcome.get('primary_horizon_return'))} "
            f"24h={_display_pct(outcome.get('return_24h'))} "
            f"72h={_display_pct(outcome.get('return_72h'))} "
            f"7d={_display_pct(outcome.get('return_7d'))} "
            f"direction_hit={outcome.get('direction_hit', 'blank')} "
            f"mfe_mae={outcome.get('mfe_mae_ratio', 'blank')}"
        )
    else:
        lines.append("- outcome: not filled")
    return lines or ["- No lifecycle timestamps found."]


def _outcome_tracking_lines(outcome: Mapping[str, Any] | None) -> list[str]:
    if outcome is None:
        return [
            "- Outcome status: pending",
            "- Outcome label: not filled",
            "- Research-only outcome; not PnL, not a trade, not a paper trade.",
        ]
    primary_horizon = str(outcome.get("primary_horizon") or "unknown")
    rel_btc = _outcome_horizon_value(outcome.get("relative_return_vs_btc_by_horizon"), primary_horizon)
    if rel_btc in (None, ""):
        rel_btc = outcome.get("relative_return_vs_btc_24h")
    rel_eth = _outcome_horizon_value(outcome.get("relative_return_vs_eth_by_horizon"), primary_horizon)
    thesis_rel_btc = _outcome_horizon_value(outcome.get("thesis_relative_return_vs_btc_by_horizon"), primary_horizon)
    thesis_favorable = outcome.get("thesis_favorable_excursion")
    thesis_adverse = outcome.get("thesis_adverse_excursion")
    if thesis_favorable in (None, ""):
        thesis_favorable = _outcome_horizon_value(outcome.get("thesis_favorable_excursion_by_window"), primary_horizon)
    if thesis_adverse in (None, ""):
        thesis_adverse = _outcome_horizon_value(outcome.get("thesis_adverse_excursion_by_window"), primary_horizon)
    mfe = outcome.get("mfe")
    mae = outcome.get("mae")
    if mfe in (None, ""):
        mfe = _outcome_horizon_value(outcome.get("max_favorable_excursion_by_window"), primary_horizon)
    if mae in (None, ""):
        mae = _outcome_horizon_value(outcome.get("max_adverse_excursion_by_window"), primary_horizon)
    status = str(outcome.get("outcome_status") or "pending")
    missing_reason = str(outcome.get("missing_data_reason") or "").strip()
    lines = [
        f"- Outcome status: {status}",
        f"- Outcome label: {outcome.get('outcome_label') or 'unknown'}",
        f"- Primary horizon: {primary_horizon}",
        f"- Asset primary return: {_display_pct(outcome.get('primary_horizon_return'))}",
        f"- Asset relative return vs BTC: {_display_pct(rel_btc)}",
        f"- Asset relative return vs ETH: {_display_pct(rel_eth)}",
        f"- Raw asset MFE / MAE: {_display_pct(mfe)} / {_display_pct(mae)}",
        f"- Thesis direction: {outcome.get('thesis_direction') or 'unknown'}",
        f"- Thesis-favorable move: {_display_pct(outcome.get('thesis_primary_move'))}",
        f"- Thesis relative return vs BTC: {_display_pct(thesis_rel_btc)}",
        f"- Thesis-favorable excursion: {_display_pct(thesis_favorable)}",
        f"- Thesis-adverse excursion: {_display_pct(thesis_adverse)}",
        f"- Thesis interpretation: {outcome.get('thesis_outcome_interpretation') or 'not available'}",
        f"- Time to peak / trough: {outcome.get('time_to_peak_hours') or outcome.get('time_to_peak') or 'unknown'} / {outcome.get('time_to_trough_hours') or outcome.get('time_to_trough') or 'unknown'}",
        f"- Catalyst confirmed after observation: {outcome.get('catalyst_confirmed_after_observation') or 'unknown'}",
        f"- Market confirmed after observation: {outcome.get('market_confirmed_after_observation') or 'unknown'}",
    ]
    if missing_reason:
        lines.append(f"- Missing data reason: {missing_reason}")
    lines.append("- Research-only outcome; not PnL, not a trade, not a paper trade.")
    return lines


def _outcome_horizon_value(value: Any, horizon: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(horizon) or value.get("24h")
    return value


def _monitor_value(row: event_watchlist_monitor.EventWatchlistMonitorRow | Mapping[str, Any], field: str) -> Any:
    if isinstance(row, Mapping):
        return row.get(field)
    return getattr(row, field, None)


def _verify_lines(alert: Mapping[str, Any] | None, playbook: str) -> list[str]:
    items = []
    if alert is not None:
        raw = alert.get("playbook_what_to_verify") or alert.get("what_to_verify")
        if isinstance(raw, (list, tuple)):
            items.extend(str(item) for item in raw if str(item))
    if not items:
        if "listing" in playbook:
            items = ["confirm listing venue/mechanics", "check opening liquidity and spread"]
        elif "unlock" in playbook:
            items = ["confirm unlock size", "compare unlock size to liquidity"]
        elif "market_anomaly" in playbook:
            items = ["find source evidence", "verify asset identity"]
        elif "proxy_fade" in playbook:
            items = ["confirm post-event failure", "confirm invalidation level"]
        else:
            items = ["verify source evidence", "verify asset identity"]
    return [f"- {item}" for item in items]


def _claim_history_summary(value: Any) -> str:
    if not value:
        return "none"
    rows: list[str] = []
    for item in list(value)[:4]:
        if isinstance(item, Mapping):
            rows.append(
                f"{item.get('claim_type') or 'claim'}:"
                f"{item.get('polarity') or 'unknown'}/"
                f"{item.get('cause_status') or 'unknown'}"
            )
        else:
            rows.append(str(item))
    return "; ".join(rows) or "none"


def _frame_summary_value(value: Any) -> str:
    if not value:
        return "none"
    rows: list[str] = []
    for item in list(value)[:4]:
        if isinstance(item, Mapping):
            rows.append(
                f"{item.get('frame_role') or 'frame'}:"
                f"{item.get('frame_type') or 'unknown'}"
                f"({item.get('subject') or 'unknown'})"
            )
        else:
            rows.append(str(item))
    return "; ".join(rows) or "none"


def _history_lines(entry: event_watchlist.EventWatchlistEntry | None) -> list[str]:
    if entry is None or not entry.alert_history:
        return ["- No watchlist alert history found."]
    lines = []
    for item in entry.alert_history[-8:]:
        lines.append(
            f"- {item.get('observed_at', 'unknown')}: state={item.get('state', 'unknown')} "
            f"tier={item.get('tier', 'unknown')} score={item.get('score', 0)}"
        )
    return lines


def _warnings(
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
    decision: event_alpha_router.EventAlphaRouteDecision | None,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if entry is not None:
        warnings.extend(entry.warnings)
    if alert is not None:
        for field in ("warnings", "rejected_reason", "llm_adjustment_reason"):
            value = alert.get(field)
            if isinstance(value, (list, tuple)):
                warnings.extend(str(item) for item in value if str(item))
            elif value:
                warnings.append(str(value))
    if decision is not None:
        warnings.extend(decision.warnings)
    return tuple(dict.fromkeys(warnings))


def _score(entry: event_watchlist.EventWatchlistEntry | None, alert: Mapping[str, Any] | None, key: str) -> Any:
    if entry is not None and key in entry.latest_score_components:
        return entry.latest_score_components.get(key)
    components = alert.get("score_components") if alert is not None else None
    if isinstance(components, Mapping):
        return components.get(key, "n/a")
    return "n/a"


def _playbook_copy(
    playbook: str,
    alert: Mapping[str, Any] | None,
    entry: event_watchlist.EventWatchlistEntry | None = None,
) -> str:
    components = _card_components(entry, alert)
    impact_path = str(components.get("impact_path_type") or "").casefold()
    frame = str(components.get("main_frame_type") or components.get("event_archetype") or "").casefold()
    level = str(components.get("opportunity_level") or "").casefold()
    role = str(components.get("candidate_role") or "").casefold()
    if impact_path == "strategic_investment_or_valuation" or frame == "acquisition_or_stake":
        return "- Hypothesis: validated strategic investment / valuation catalyst may change market expectations for the token or protocol."
    if impact_path in {"venue_value_capture", "proxy_exposure"} or role == "proxy_venue":
        priority = "high-priority " if level == "high_priority" else ""
        return f"- Hypothesis: validated {priority}proxy venue/exposure narrative may concentrate attention around the external catalyst."
    if impact_path == "exploit_security_event":
        return "- Hypothesis: validated security or exploit catalyst may change risk appetite, liquidity, and volatility for the affected asset."
    if impact_path == "listing_liquidity_event":
        return "- Hypothesis: validated listing or liquidity catalyst may change venue access, treasury demand, or short-term volatility."
    if impact_path == "market_dislocation_unknown" or frame == "market_dislocation_unknown":
        return "- Hypothesis: market dislocation is real, but the cause is still unconfirmed; keep it local until causal evidence appears."
    if alert is not None and alert.get("playbook_hypothesis"):
        return f"- Hypothesis: {alert.get('playbook_hypothesis')}"
    if "listing" in playbook:
        return "- Hypothesis: exchange listing mechanics may create volatility around new liquidity access."
    if "unlock" in playbook:
        return "- Hypothesis: unlock supply may pressure price if liquidity is thin."
    if "market_anomaly" in playbook:
        return "- Hypothesis: market move is unusual, but catalyst evidence is unknown."
    if playbook == "proxy_fade":
        return "- Hypothesis: proxy narrative may fade after the dated catalyst and failed reclaim."
    return "- Hypothesis: event/catalyst relationship needs manual review."


def _why_it_matters(
    playbook: str,
    entry: event_watchlist.EventWatchlistEntry | None = None,
    alert: Mapping[str, Any] | None = None,
) -> str:
    components = _card_components(entry, alert)
    impact_path = str(components.get("impact_path_type") or "").casefold()
    frame = str(components.get("main_frame_type") or components.get("event_archetype") or "").casefold()
    if impact_path == "strategic_investment_or_valuation" or frame == "acquisition_or_stake":
        return "Strategic investment or valuation news can alter perceived protocol value, governance expectations, and token risk appetite."
    if impact_path == "exploit_security_event":
        return "Confirmed exploit or security events can affect liquidity access, confidence, volatility, and direct token risk."
    if impact_path == "listing_liquidity_event":
        return "Listing and liquidity events can change venue access, available demand, spreads, and realized volatility."
    if impact_path == "market_dislocation_unknown" or frame == "market_dislocation_unknown":
        return "Large unexplained moves are useful only as catalyst-search and missed-opportunity evidence until a causal mechanism is found."
    if "listing" in playbook:
        return "Listings can change venue access, liquidity, spreads, and short-term volatility."
    if "unlock" in playbook:
        return "Unlocks can add sellable supply into shallow liquidity."
    if "market_anomaly" in playbook:
        return "Large moves without source evidence are useful missed-opportunity and catalyst-search inputs."
    if playbook == "proxy_fade":
        return "Temporary proxy narratives can unwind after the external catalyst passes."
    return "The row helps calibrate source quality, resolver precision, and playbook thresholds."


def _default_invalidation(
    playbook: str,
    alert: Mapping[str, Any] | None = None,
    entry: event_watchlist.EventWatchlistEntry | None = None,
) -> str:
    components = _card_components(entry, alert)
    impact_path = str(components.get("impact_path_type") or "").casefold()
    frame = str(components.get("main_frame_type") or components.get("event_archetype") or "").casefold()
    role = str(components.get("candidate_role") or "").casefold()
    if impact_path == "strategic_investment_or_valuation" or frame == "acquisition_or_stake":
        return "Talks are denied, the source is corrected, no market reaction appears, or the valuation/stake is not relevant to token value."
    if impact_path in {"venue_value_capture", "proxy_exposure"} or role == "proxy_venue":
        return "Proxy venue/exposure is denied, source evidence is corrected, attention shifts away, or the market fails to confirm the narrative."
    if impact_path == "exploit_security_event":
        return "The exploit/security claim is denied or corrected, the incident is unrelated to the asset, liquidity normalizes, or market impact fades."
    if impact_path == "listing_liquidity_event":
        return "The listing/liquidity event is stale, denied, already priced, too small to matter, or fails to change trading conditions."
    if impact_path == "market_dislocation_unknown" or frame == "market_dislocation_unknown":
        return "No exploit/catalyst is confirmed, the move mean-reverts without new evidence, or the asset link remains unexplained."
    if "listing" in playbook:
        return "Listing is stale, liquidity is deep, or volatility does not expand."
    if "unlock" in playbook:
        return "Unlock is small, already absorbed, or liquidity is sufficient."
    if "market_anomaly" in playbook:
        return "No credible catalyst or asset identity evidence emerges."
    if playbook == "proxy_fade":
        return "Price reclaims event VWAP/invalidation level or proxy narrative persists."
    return "Source evidence fails identity/catalyst review."


def _trade_readiness_lines(
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
    playbook: str,
    state: str,
) -> list[str]:
    components = alert.get("score_components") if alert is not None and isinstance(alert.get("score_components"), Mapping) else {}
    rich_components = _card_components(entry, alert)
    timing = _value(entry, alert, "event_time", "event_time") or "unknown"
    direction = _value(None, alert, "", "expected_direction") or _playbook_direction(playbook)
    horizon = _value(None, alert, "", "primary_horizon") or "manual"
    invalidation = _value(None, alert, "", "playbook_invalidation") or _default_invalidation(playbook, alert, entry)
    market_confirmation = (
        rich_components.get("integrated_market_confirmation_level")
        or rich_components.get("market_state_class")
        or _check_value(components, "market_move_volume")
    )
    crowding_class = _display_text(rich_components.get("crowding_class"))
    fade_readiness = _display_text(rich_components.get("fade_readiness"))
    if crowding_class or fade_readiness:
        derivatives_crowding = crowding_class or "classified"
        if fade_readiness:
            derivatives_crowding += f" / fade_readiness={fade_readiness}"
    else:
        derivatives_crowding = _score(entry, alert, "derivatives_crowding")
    unlock_event = rich_components.get("unlock_event")
    if isinstance(unlock_event, Mapping) and unlock_event:
        supply_risk = (
            "structured_unlock "
            f"pct_circ={unlock_event.get('unlock_pct_circulating_supply') if unlock_event.get('unlock_pct_circulating_supply') is not None else 'n/a'} "
            f"vs_adv={unlock_event.get('unlock_vs_30d_adv') if unlock_event.get('unlock_vs_30d_adv') is not None else 'n/a'}"
        )
    else:
        supply_risk = _score(entry, alert, "supply_pressure")
    lines = [
        f"- Catalyst clarity: {_check_value(components, 'external_catalyst')}",
        f"- Event timing quality: {timing} / {_check_value(components, 'event_time_quality')}",
        f"- Market confirmation: {market_confirmation}",
        f"- Derivatives crowding: {derivatives_crowding}",
        f"- Liquidity/supply risk: supply={supply_risk} liquidity=manual review",
        f"- Current lifecycle state: {state}",
        f"- Primary playbook: {playbook}",
        f"- Expected direction / horizon: {direction} / {horizon}",
        f"- Invalidation / why wrong: {invalidation}",
    ]
    if playbook == "proxy_fade":
        lines.append("- Manual verification: confirm post-event failure, failed reclaim, and invalidation level before treating as research-actionable.")
    elif "listing" in playbook:
        lines.append("- Manual verification: confirm venue, listing mechanics, opening liquidity, spread, and whether the event is already priced.")
    elif "unlock" in playbook:
        lines.append("- Manual verification: confirm unlock size, circulating-supply impact, recipient wallets, and available liquidity.")
    elif "market_anomaly" in playbook:
        lines.append("- Manual verification: catalyst unvalidated; find source evidence and confirm asset identity before escalation.")
    else:
        lines.append("- Manual verification: confirm source evidence, asset identity, playbook fit, and why the thesis could be wrong.")
    return lines


def _check_value(components: Mapping[str, Any], key: str) -> str:
    value = components.get(key)
    return "n/a" if value is None else str(value)


def _card_components(
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
) -> dict[str, Any]:
    components: dict[str, Any] = {}
    if entry is not None:
        components.update(entry.latest_score_components or {})
        for key in (
            "impact_path_type",
            "candidate_role",
            "source_class",
            "evidence_specificity",
            "opportunity_level",
            "opportunity_score_final",
            "market_confirmation_level",
            "main_frame_type",
            "event_archetype",
        ):
            value = getattr(entry, key, None)
            if value not in (None, ""):
                components.setdefault(key, value)
    if alert is not None:
        raw = alert.get("score_components")
        if isinstance(raw, Mapping):
            components.update({key: value for key, value in raw.items() if value not in (None, "")})
        latest = alert.get("latest_score_components")
        if isinstance(latest, Mapping):
            components.update({key: value for key, value in latest.items() if value not in (None, "")})
        for key, value in alert.items():
            if value not in (None, "", [], {}):
                existing = components.get(key)
                if (
                    key == "opportunity_type"
                    and existing not in (None, "", value)
                    and "card_component_conflict:opportunity_type" not in _list_value(components.get("warnings"))
                ):
                    warnings = _list_value(components.get("warnings"))
                    warnings.append("card_component_conflict:opportunity_type")
                    components["warnings"] = warnings
                components[key] = value
    return components


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _playbook_direction(playbook: str) -> str:
    if playbook in {"proxy_fade", "unlock_supply_pressure"}:
        return "down"
    if "listing" in playbook:
        return "volatility"
    if "market_anomaly" in playbook:
        return "unknown"
    return "manual"
