"""Index helpers for research cards."""

from __future__ import annotations

from .runtime import *

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

__all__ = (
    '_lineage_lines',
    'card_feedback_target',
    'card_core_opportunity_id',
    'card_has_current_lineage',
    '_feedback_target_for_card',
    '_find_card_core_opportunity',
    '_lineage_value',
    '_lineage_values',
    '_lineage_mappings',
)
