"""Renderer helpers for research cards."""

from __future__ import annotations

from .runtime import *
from ....radar.decision_model_surfaces import (
    decision_model_markdown_lines,
    decision_model_values,
)

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
    candidate_rows: Iterable[Mapping[str, Any]] = (),
    generated_at: datetime | None = None,
    lineage_context: Mapping[str, Any] | None = None,
    card_path: str | Path | None = None,
) -> EventResearchCardResult:
    """Render one Markdown card from local research artifacts."""
    clean_key = str(key or "").strip()
    observed = (generated_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    context = _research_card_context(
        clean_key,
        watchlist_entries=watchlist_entries,
        alert_rows=alert_rows,
        route_decisions=route_decisions,
        clusters=clusters,
        monitor_rows=monitor_rows,
        feedback_rows=feedback_rows,
        outcome_rows=outcome_rows,
        candidate_rows=candidate_rows,
        evaluated_at=observed,
        card_path=card_path,
    )
    if context["entry"] is None and context["alert"] is None:
        return EventResearchCardResult(
            key=clean_key,
            markdown=f"# Event Research Card\n\nNo watchlist or alert snapshot matched `{clean_key}`.",
            found=False,
        )
    context["generated_iso"] = observed.isoformat()
    context["lineage_context"] = lineage_context
    context["card_path"] = card_path
    lines = _research_card_summary_lines(context)
    _append_research_card_evidence_sections(lines, context)
    _append_research_card_review_sections(lines, context)
    return EventResearchCardResult(key=clean_key, markdown="\n".join(lines).rstrip() + "\n", found=True)


def _research_card_context(
    clean_key: str,
    *,
    watchlist_entries: Iterable[event_watchlist.EventWatchlistEntry],
    alert_rows: Iterable[Mapping[str, Any]],
    route_decisions: Iterable[event_alpha_router.EventAlphaRouteDecision],
    clusters: Iterable[event_graph.EventCluster],
    monitor_rows: Iterable[event_watchlist_monitor.EventWatchlistMonitorRow | Mapping[str, Any]],
    feedback_rows: Iterable[Mapping[str, Any]],
    outcome_rows: Iterable[Mapping[str, Any]],
    candidate_rows: Iterable[Mapping[str, Any]],
    evaluated_at: datetime,
    card_path: str | Path | None,
) -> dict[str, Any]:
    entry_rows = list(watchlist_entries)
    alert_row_list = list(alert_rows)
    decision_rows = list(route_decisions)
    feedback_row_list = list(feedback_rows)
    entry = _find_entry(clean_key, entry_rows)
    alert = _find_alert(clean_key, alert_row_list)
    decision = _find_decision(clean_key, decision_rows)
    core_rows = [
        row
        for row in alert_row_list
        if isinstance(row, Mapping) and row.get("row_type") == "event_core_opportunity"
    ]
    eligible_feedback, excluded_feedback, feedback_reason_counts = (
        event_feedback_eligibility.partition_joined_calibration_feedback(
            feedback_row_list,
            core_rows,
            now=evaluated_at,
        )
    )
    integrated_candidate_rows = [
        dict(row)
        for row in (*candidate_rows, *alert_row_list)
        if isinstance(row, Mapping)
        and row.get("row_type") == "event_integrated_radar_candidate"
    ]
    core_view = _research_card_core_view(
        clean_key,
        core_rows=core_rows,
        alert_rows=alert_row_list,
        decision_rows=decision_rows,
        entry_rows=entry_rows,
        card_path=card_path,
        evaluated_at=evaluated_at,
    )
    core = (
        core_view.core_opportunity
        if core_view is not None and core_view.found
        else _find_card_core_opportunity(clean_key, entry, alert, decision, decision_rows)
    )
    if core is not None:
        if entry is None or (alert is not None and alert.get("row_type") == "event_core_opportunity"):
            entry = _entry_from_core_opportunity(core)
        canonical_row = core_view.canonical_core_row if core_view is not None and core_view.canonical_core_row else alert
        alert = _canonical_card_alert(core, canonical_row)
    matching_feedback = _matching_rows(
        clean_key,
        list(eligible_feedback),
        entry,
        alert,
    )
    outcome = _authoritative_card_outcome(
        clean_key,
        outcome_rows=outcome_rows,
        candidate_rows=integrated_candidate_rows,
        core_rows=core_rows,
        entry=entry,
        alert=alert,
        evaluated_at=evaluated_at,
    )
    return {
        "clean_key": clean_key,
        "entry": entry,
        "alert": alert,
        "decision": decision,
        "core": core,
        "cluster": _find_cluster(clean_key, list(clusters), entry, alert),
        "monitor_row": _find_monitor_row(clean_key, list(monitor_rows), entry, alert),
        "feedback": matching_feedback,
        "feedback_evidence_diagnostics": {
            "feedback_rows_supplied": len(feedback_row_list),
            "feedback_rows_eligible": len(eligible_feedback),
            "feedback_rows_matched_to_card": len(matching_feedback),
            "feedback_rows_eligible_other_core": (
                len(eligible_feedback) - len(matching_feedback)
            ),
            "feedback_rows_excluded": len(excluded_feedback),
            "feedback_exclusion_reason_counts": dict(feedback_reason_counts),
        },
        "outcome": outcome,
    }


def _authoritative_card_outcome(
    clean_key: str,
    *,
    outcome_rows: Iterable[Mapping[str, Any]],
    candidate_rows: Iterable[Mapping[str, Any]],
    core_rows: Iterable[Mapping[str, Any]],
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
    evaluated_at: datetime,
) -> Mapping[str, Any] | None:
    supplied = [dict(row) for row in outcome_rows if isinstance(row, Mapping)]
    if not supplied:
        return None
    eligible, excluded, _reason_counts = (
        event_outcome_eligibility.partition_joined_calibration_outcomes(
            supplied,
            candidate_rows,
            core_rows,
            evaluated_at=evaluated_at,
        )
    )
    exact = _find_outcome(clean_key, list(eligible), entry, alert)
    if exact is not None:
        return {
            **dict(exact),
            "outcome_display_status": "eligible_performance_evidence",
            "outcome_display_maturation_state": (
                event_outcome_eligibility.primary_horizon_maturation_state(exact)
                or "unknown"
            ),
            "outcome_display_validation_status": (
                event_outcome_eligibility.deterministic_validation_status(exact)
            ),
        }
    diagnostic = _find_outcome(clean_key, list(excluded), entry, alert)
    if diagnostic is not None:
        return {
            **dict(diagnostic),
            "outcome_display_status": "excluded_non_performance_diagnostic",
            "outcome_display_maturation_state": "excluded",
            "outcome_display_validation_status": "inconclusive",
        }
    return None


def _research_card_core_view(
    clean_key: str,
    *,
    core_rows: list[Mapping[str, Any]],
    alert_rows: list[Mapping[str, Any]],
    decision_rows: list[event_alpha_router.EventAlphaRouteDecision],
    entry_rows: list[event_watchlist.EventWatchlistEntry],
    card_path: str | Path | None,
    evaluated_at: datetime,
) -> Any | None:
    if not core_rows:
        return None
    return event_core_opportunity_store.canonical_core_opportunity_view_from_rows(
        clean_key,
        core_rows=core_rows,
        supporting_rows=[*alert_rows, *decision_rows, *entry_rows],
        alert_rows=alert_rows,
        card_paths=[card_path] if card_path is not None else (),
        now=evaluated_at,
    )


def _research_card_summary_lines(context: Mapping[str, Any]) -> list[str]:
    entry = context["entry"]
    alert = context["alert"]
    decision = context["decision"]
    core = context["core"]
    clean_key = context["clean_key"]
    playbook = _value(entry, alert, "latest_playbook_type", "playbook_type") or "unknown"
    symbol = _value(entry, alert, "symbol", "asset_symbol") or "UNKNOWN"
    coin_id = _value(entry, alert, "coin_id", "asset_coin_id") or "unknown"
    canonical_asset_id = _value(entry, alert, "canonical_asset_id", "canonical_asset_id")
    event_name = _value(entry, alert, "latest_event_name", "event_name") or "unknown event"
    tier = _value(entry, alert, "latest_tier", "tier") or "unknown"
    state = _research_card_state(entry, alert)
    summary_identity_lines = [f"- Asset: {symbol}/{coin_id}"]
    if canonical_asset_id:
        summary_identity_lines.append(f"- Canonical asset: {canonical_asset_id}")
    lines = [
        f"# {symbol} Event Research Card",
        "",
        "Research artifact only. Not a trade signal, paper trade, live RSI signal, or execution.",
        "Research idea, not a trade instruction.",
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
    decision_values = decision_model_values(alert, _card_components(entry, alert))
    decision_lines = decision_model_markdown_lines(decision_values)
    if decision_lines:
        lines.extend(["", "## Crypto Radar Decision"])
        lines.extend(decision_lines)
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
        generated_iso=context["generated_iso"],
        lineage_context=context["lineage_context"],
        card_path=context["card_path"],
    ))
    return lines


def _research_card_state(
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
) -> str:
    if entry is not None:
        return event_watchlist.final_state_value(entry)
    return str(alert.get("final_state_after_quality_gate") or alert.get("state") or "snapshot")


def _append_research_card_evidence_sections(lines: list[str], context: Mapping[str, Any]) -> None:
    entry = context["entry"]
    alert = context["alert"]
    cluster = context["cluster"]
    playbook = _value(entry, alert, "latest_playbook_type", "playbook_type") or "unknown"
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
    lines.extend(_source_acquisition_lines(
        entry,
        alert,
        card_path=context["card_path"],
        lineage_context=context["lineage_context"],
    ))
    lines.extend([
        "",
        "## Accepted / Rejected Asset Links",
        f"- Relationship: {_value(entry, alert, 'relationship_type', 'relationship_type') or 'unknown'}",
        f"- Rule playbook: {_value(entry, alert, 'latest_rule_playbook_type', 'rule_playbook_type') or 'unknown'}",
        f"- Effective playbook: {_value(entry, alert, 'latest_effective_playbook_type', 'playbook_type') or playbook}",
    ])
    lines.extend(["", "## Quality Gate Result"])
    lines.extend(_quality_gate_lines(entry, alert, context["decision"]))
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


def _append_research_card_review_sections(lines: list[str], context: Mapping[str, Any]) -> None:
    entry = context["entry"]
    alert = context["alert"]
    decision = context["decision"]
    monitor_row = context["monitor_row"]
    feedback = context["feedback"]
    outcome = context["outcome"]
    playbook = _value(entry, alert, "latest_playbook_type", "playbook_type") or "unknown"
    state = _research_card_state(entry, alert)
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
    if context["feedback_evidence_diagnostics"].get("feedback_rows_supplied"):
        lines.extend(["", "## Feedback Evidence Diagnostics"])
        lines.extend(
            _feedback_evidence_diagnostic_lines(
                context["feedback_evidence_diagnostics"]
            )
        )
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

def render_selected_cards(
    *,
    watchlist_entries: Iterable[event_watchlist.EventWatchlistEntry],
    alert_rows: Iterable[Mapping[str, Any]] = (),
    route_decisions: Iterable[event_alpha_router.EventAlphaRouteDecision] = (),
    clusters: Iterable[event_graph.EventCluster] = (),
    monitor_rows: Iterable[event_watchlist_monitor.EventWatchlistMonitorRow | Mapping[str, Any]] = (),
    feedback_rows: Iterable[Mapping[str, Any]] = (),
    outcome_rows: Iterable[Mapping[str, Any]] = (),
    candidate_rows: Iterable[Mapping[str, Any]] = (),
    generated_at: datetime | None = None,
    limit: int = 10,
) -> str:
    cluster_rows = list(clusters)
    monitor = list(monitor_rows)
    observed = (generated_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
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
            candidate_rows=candidate_rows,
            generated_at=observed,
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
    candidate_rows: Iterable[Mapping[str, Any]] = (),
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
            candidate_rows=candidate_rows,
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

def _list_label(values: Iterable[str]) -> str:
    rows = [str(value) for value in values if str(value or "")]
    if not rows:
        return "none"
    return ", ".join(rows[:6]) + (f", +{len(rows) - 6} more" if len(rows) > 6 else "")

def _slug(value: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9._-]+", "_", value)).strip("._") or "event_card"

def _render_index(
    paths: list[Path],
    observed: datetime,
    *,
    card_groups: Mapping[Path | str, str] | None = None,
) -> str:
    grouped: dict[str, list[Path]] = {group: [] for group in CARD_INDEX_GROUPS}
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

__all__ = (
    'render_research_card',
    'render_selected_cards',
    'write_research_cards',
    'format_card_write_result',
    '_list_label',
    '_slug',
    '_render_index',
    '_candidate_index_paths',
    '_parse_index_groups',
    '_card_index_group',
    '_card_family_key',
    '_card_primary_sort_key',
    '_card_accepted_evidence_count',
    '_card_primary_score',
    '_card_metadata_line',
    '_card_family_asset',
    '_card_family_event',
    '_card_family_playbook',
    '_card_index_group_for_entry',
    '_card_index_group_for_text',
    '_lane_card_group',
    '_components_are_integrated_radar',
    '_text_is_integrated_radar_card',
    '_strip_sensitive',
)
