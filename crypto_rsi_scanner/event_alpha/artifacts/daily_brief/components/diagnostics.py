"""Diagnostics helpers for daily brief."""

from __future__ import annotations

from .runtime import *

def _canonical_incident_lines(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    incidents = [dict(row) for row in rows if isinstance(row, Mapping)]
    if not incidents:
        return ["- Stored incidents: none loaded for this profile."]
    diagnostic_rows = [row for row in incidents if _incident_is_hidden(row)]
    visible = [row for row in incidents if not _incident_is_diagnostic(row)]
    if not visible:
        return [
            f"- Stored incidents: {len(incidents)}",
            f"- Diagnostic/raw/external-context observations hidden: {len(diagnostic_rows)}",
            "- Canonical incidents: none visible for this profile.",
        ]
    lines = [
        f"- Stored incidents: {len(incidents)}",
        f"- Diagnostic/raw/external-context observations hidden: {len(diagnostic_rows)}",
        "- Relevance statuses: " + _format_counts(_field_counts(incidents, "incident_relevance_status")),
        "- Event archetypes: " + _format_counts(_field_counts(visible, "event_archetype")),
        "- Cause statuses: " + _format_counts(_field_counts(visible, "current_cause_status")),
        "- Primary subjects: " + _format_counts(_field_counts(visible, "primary_subject")),
        "- New/updated: "
        f"multiple_source_updates={sum(1 for row in visible if int(row.get('source_update_count') or 0) > 1)}, "
        f"conflicting_claims={sum(1 for row in visible if row.get('conflicting_claims'))}",
        "- Market reaction but unknown/ruled-out cause: "
        + str(sum(
            1 for row in visible
            if (row.get("market_reaction_observed") or row.get("market_reaction_confirmed"))
            and str(row.get("current_cause_status") or "") in {"unknown", "ruled_out"}
        )),
        "- Confirmed cause missing market data: "
        + str(sum(
            1 for row in visible
            if str(row.get("current_cause_status") or "") == "confirmed"
            and not row.get("market_context_source")
        )),
        "- Weak unqualified incident links: "
        + str(sum(int(row.get("weak_link_count") or 0) for row in visible)),
    ]
    candidates = [row for row in visible if str(row.get("incident_relevance_status") or "") == "incident_candidate"]
    active = [
        row for row in visible
        if str(row.get("incident_relevance_status") or "") == "active_incident"
        and int(row.get("qualified_link_count") or 0) > 0
    ]
    linked = [
        row for row in visible
        if str(row.get("incident_relevance_status") or "") == "linked_incident"
        and int(row.get("qualified_link_count") or 0) > 0
    ]
    market_unknown = [
        row for row in visible
        if (row.get("market_reaction_observed") or row.get("market_reaction_confirmed"))
        and str(row.get("current_cause_status") or "") in {"unknown", "ruled_out"}
    ]
    lines.append(f"- Incident candidates: {len(candidates)}")
    lines.append(f"- Active incidents with qualified links: {len(active)}")
    lines.append(f"- Linked incidents with qualified links: {len(linked)}")
    lines.append(f"- Market reactions with unknown/ruled-out cause: {len(market_unknown)}")
    if candidates:
        labels = []
        for row in candidates[:5]:
            labels.append(
                f"{row.get('canonical_name') or row.get('incident_id')}: "
                f"reason={row.get('canonical_persistence_reason') or 'candidate'} "
                f"weak_links={int(row.get('weak_link_count') or 0)}"
            )
        lines.append("- Incident candidates awaiting qualified crypto link: " + " | ".join(labels))
    notable = sorted(
        visible,
        key=lambda row: (
            int(row.get("source_update_count") or 0),
            _float(row.get("incident_confidence")),
        ),
        reverse=True,
    )
    if notable:
        labels = []
        for row in notable[:5]:
            assets = row.get("linked_assets") or []
            asset_text = _incident_asset_summary(assets)
            labels.append(
                f"{row.get('canonical_name') or row.get('incident_id')}: "
                f"cause={row.get('current_cause_status') or 'unknown'} "
                f"archetype={row.get('event_archetype') or 'unknown'} "
                f"sources={int(row.get('source_update_count') or 0)}/"
                f"{int(row.get('independent_source_count') or 0)} "
                f"assets={asset_text}"
            )
        lines.append("- Notable incidents: " + " | ".join(labels))
    return lines

def _incident_is_hidden(row: Mapping[str, Any]) -> bool:
    status = str(row.get("incident_relevance_status") or "")
    return bool(row.get("diagnostic_only")) or status in {"raw_observation", "external_context_only", "diagnostic_only", "rejected_incident"}

def _incident_is_diagnostic(row: Mapping[str, Any]) -> bool:
    return _incident_is_hidden(row)

def _incident_asset_summary(value: Any) -> str:
    if not value:
        return "none"
    labels: list[str] = []
    for item in list(value)[:4]:
        if not isinstance(item, Mapping):
            continue
        labels.append(
            f"{item.get('symbol') or item.get('coin_id') or 'asset'}:"
            f"{item.get('role') or 'unknown'}"
        )
    return ", ".join(labels) or "none"

def _candidate_like_term(item: Mapping[str, Any]) -> bool:
    symbol = str(item.get("symbol") or "").strip()
    coin_id = str(item.get("coin_id") or "").strip()
    name = str(item.get("name") or item.get("project_name") or "").strip()
    source = str(item.get("source") or "").strip().casefold()
    mention_type = str(item.get("mention_type") or item.get("type") or "").strip().casefold()
    reason = str(item.get("reason") or item.get("rejection_reason") or item.get("identity_reason") or "").casefold()
    accepted = bool(item.get("accepted") or item.get("validated"))
    if any(token in reason for token in ("source_noise", "publisher", "word_collision", "url_only", "generic_symbol")):
        return False
    if any(token in mention_type for token in ("source_noise", "publisher", "navigation", "nav", "word_collision")):
        return False
    if source in {"taxonomy", "source_origin", "publisher", "nav", "navigation"} and not accepted:
        return False
    return bool(symbol or coin_id or name)

def _feedback_by_impact_path(alerts: Iterable[Mapping[str, Any]], feedback: Iterable[Mapping[str, Any]]) -> str:
    del alerts  # Exact projections carry Core-owned attribution; aliases are forbidden.
    counts: dict[str, int] = {}
    for row in feedback:
        path = str(row.get("impact_path_type") or "unknown")
        label = str(row.get("feedback_label") or "feedback")
        counts[f"{path}:{label}"] = counts.get(f"{path}:{label}", 0) + 1
    return _format_counts(counts)

def _upgrade_candidate_line(rows: Iterable[event_alpha_router.EventAlphaRouteDecision]) -> str:
    labels: list[str] = []
    seen: set[tuple[str, str]] = set()
    for decision in sorted(rows, key=lambda item: item.entry.latest_score, reverse=True):
        entry = decision.entry
        if event_alpha_router.alertable_after_quality_gate(decision) or entry.relationship_type != "impact_hypothesis":
            continue
        key = _decision_family_key(decision)
        if key in seen:
            continue
        components = entry.latest_score_components or {}
        upgrade = event_opportunity_verdict.explain_upgrade_path(components=components)
        if not upgrade.upgrade_requirements:
            continue
        seen.add(key)
        labels.append(
            f"{entry.symbol}/{entry.coin_id}: "
            + event_alpha_reason_text.humanize_event_alpha_reasons(upgrade.upgrade_requirements, limit=2)
        )
        if len(labels) >= 5:
            break
    return " | ".join(labels)

def _downgrade_risk_line(rows: Iterable[event_alpha_router.EventAlphaRouteDecision]) -> str:
    labels: list[str] = []
    seen: set[tuple[str, str]] = set()
    for decision in sorted(rows, key=lambda item: item.entry.latest_score, reverse=True):
        entry = decision.entry
        if not event_alpha_router.alertable_after_quality_gate(decision) and event_watchlist.final_state_value(entry) not in {"WATCHLIST", "HIGH_PRIORITY"}:
            continue
        key = _decision_family_key(decision)
        if key in seen:
            continue
        components = entry.latest_score_components or {}
        upgrade = event_opportunity_verdict.explain_upgrade_path(components=components)
        if not upgrade.downgrade_warnings:
            continue
        seen.add(key)
        labels.append(
            f"{entry.symbol}/{entry.coin_id}: "
            + event_alpha_reason_text.humanize_event_alpha_reasons(upgrade.downgrade_warnings, limit=2)
        )
        if len(labels) >= 5:
            break
    return " | ".join(labels)

def _float(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0

def _lane_count(row: Mapping[str, Any] | None, field: str, lane: str) -> int:
    if not row:
        return 0
    counts = row.get(field) or {}
    if not isinstance(counts, Mapping):
        return 0
    try:
        return int(counts.get(lane) or 0)
    except (TypeError, ValueError):
        return 0

def _format_clock_status(status: Mapping[str, Any]) -> str:
    age = status.get("fixed_clock_age_hours")
    age_text = "n/a" if age is None else f"{float(age):.2f}h"
    return (
        "Clock: "
        f"mode={status.get('clock_mode') or 'unknown'}; "
        f"research_now={status.get('research_now') or 'unknown'}; "
        f"wall_clock_now={status.get('wall_clock_now') or 'unknown'}; "
        f"fixed_clock_age_hours={age_text}"
    )

def _format_clock_warning_lines(status: Mapping[str, Any]) -> list[str]:
    warnings = [str(item) for item in status.get("warnings") or () if str(item)]
    return [f"Clock warning: {warning}" for warning in warnings]

def _strip_sensitive(text: str) -> str:
    cleaned = (
        text.replace("OPENAI_API_KEY", "[redacted]")
        .replace("TELEGRAM_BOT_TOKEN", "[redacted]")
        .replace(".env", "[env-file]")
    )
    return event_artifact_paths.scrub_absolute_paths_from_markdown(cleaned)

__all__ = (
    '_canonical_incident_lines',
    '_incident_is_hidden',
    '_incident_is_diagnostic',
    '_incident_asset_summary',
    '_candidate_like_term',
    '_feedback_by_impact_path',
    '_upgrade_candidate_line',
    '_downgrade_risk_line',
    '_float',
    '_lane_count',
    '_format_clock_status',
    '_format_clock_warning_lines',
    '_strip_sensitive',
)
