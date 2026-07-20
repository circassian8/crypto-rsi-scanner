"""Split implementation for `crypto_rsi_scanner/event_alpha/radar/incidents.py` (report)."""

from __future__ import annotations

import json
from collections.abc import Iterable as IterableABC
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
import crypto_rsi_scanner.event_alpha.radar.claim_semantics as event_claim_semantics
import crypto_rsi_scanner.event_alpha.radar.incident_graph as event_incident_graph
from crypto_rsi_scanner.event_core.models import EventDiscoveryResult, RawDiscoveredEvent
from .models import *  # noqa: F403
from .relevance import _incident_flag_true

def format_incidents_report(result: EventIncidentStoreReadResult) -> str:
    """Return an operator-readable incident artifact report."""
    include_diagnostic = _incident_flag_true(
        result.filters.get("include_diagnostic")
    )
    include_raw = _incident_flag_true(
        result.filters.get("include_raw")
    ) or include_diagnostic
    include_external_context = _incident_flag_true(
        result.filters.get("include_external_context")
    ) or include_diagnostic
    diagnostic_rows = [row for row in result.rows if _is_strict_diagnostic_relevance(row)]
    raw_rows = [row for row in result.rows if _is_raw_observation_relevance(row)]
    external_context_rows = [row for row in result.rows if _is_external_context_relevance(row)]
    display_rows = [
        row for row in result.rows
        if not _is_hidden_relevance(
            row,
            include_diagnostic=include_diagnostic,
            include_raw=include_raw,
            include_external_context=include_external_context,
        )
    ]
    diagnostic_hidden = 0 if include_diagnostic else len(diagnostic_rows)
    raw_hidden = 0 if include_raw else len(raw_rows)
    external_context_hidden = 0 if include_external_context else len(external_context_rows)
    rows = [
        "=" * 76,
        "EVENT INCIDENTS REPORT (research artifact only)",
        "=" * 76,
        f"path: {result.path}",
        f"rows_read: {result.rows_read}",
        f"total_rows_available: {result.total_rows_read or result.rows_read}",
        f"latest_run_id: {result.latest_run_id or 'unknown'}",
        f"latest_run_rows_available: {result.latest_run_rows_available}",
        f"historical_rows_available: {result.historical_rows_available}",
        f"legacy_rows_available: {result.legacy_rows_available}",
        f"diagnostic_rows_hidden: {diagnostic_hidden}",
        f"diagnostic_rows_available: {len(diagnostic_rows)}",
        f"raw_observation_rows_hidden: {raw_hidden}",
        f"raw_observation_rows_available: {len(raw_rows)}",
        f"external_context_rows_hidden: {external_context_hidden}",
        f"external_context_rows_available: {len(external_context_rows)}",
        "filters: " + _format_filter_summary(result.filters),
    ]
    if not display_rows:
        rows.extend(["", "No stored incidents matched the current report filters."])
        return "\n".join(rows)

    rows.append("event_archetypes: " + _format_counts(_counts(display_rows, "event_archetype")))
    rows.append("incident_relevance_statuses: " + _format_counts(_counts(result.rows, "incident_relevance_status")))
    rows.append("visible_relevance_statuses: " + _format_counts(_counts(display_rows, "incident_relevance_status")))
    rows.append("incident_relevance_score_buckets: " + _format_counts(_score_buckets(result.rows, "incident_relevance_score")))
    rows.append("cause_statuses: " + _format_counts(_counts(display_rows, "current_cause_status")))
    rows.append("primary_subjects: " + _format_counts(_counts(display_rows, "primary_subject")))
    rows.append("subject_quality: " + _format_counts(_counts(result.rows, "incident_subject_quality")))
    rows.append("asset_roles: " + _format_counts(_asset_role_counts(display_rows)))
    rows.append(f"conflicting_claim_incidents: {sum(1 for row in display_rows if row.get('conflicting_claims'))}")
    rows.append(f"absence_of_validated_catalyst_claims: {_absence_claim_count(display_rows)}")
    rows.append(f"multiple_source_updates: {sum(1 for row in display_rows if int(row.get('source_update_count') or 0) > 1)}")
    rows.append(f"linked_to_hypotheses: {sum(1 for row in display_rows if row.get('linked_hypothesis_ids'))}")
    rows.append(f"linked_to_watchlist: {sum(1 for row in display_rows if row.get('linked_watchlist_keys'))}")
    rows.append(f"active_incidents: {sum(1 for row in display_rows if str(row.get('incident_relevance_status') or '') == RELEVANCE_ACTIVE_INCIDENT)}")
    rows.append(f"linked_incidents: {sum(1 for row in display_rows if str(row.get('incident_relevance_status') or '') == RELEVANCE_LINKED_INCIDENT)}")
    rows.append(f"incident_candidates: {sum(1 for row in display_rows if str(row.get('incident_relevance_status') or '') == RELEVANCE_INCIDENT_CANDIDATE)}")
    rows.append(f"external_context_only_hidden: {external_context_hidden}")
    rows.append(f"weak_unqualified_links: {sum(int(row.get('weak_link_count') or 0) for row in display_rows)}")
    rows.append(f"qualified_incident_links: {sum(int(row.get('qualified_link_count') or 0) for row in display_rows)}")
    rows.append(f"quality_blocked_incident_links: {sum(int(row.get('quality_blocked_link_count') or 0) for row in display_rows)}")
    rows.append(f"unknown_role_incident_links: {sum(int(row.get('unknown_role_link_count') or 0) for row in display_rows)}")
    unlinked_canonical = [
        row for row in display_rows
        if _is_operational_canonical_relevance(row)
        and not row.get("linked_hypothesis_ids")
        and not row.get("linked_watchlist_keys")
    ]
    rows.append(f"canonical_unlinked_incidents: {len(unlinked_canonical)}")
    rows.append(f"incident_linked_hypotheses_count: {sum(len(row.get('linked_hypothesis_ids') or ()) for row in display_rows)}")
    rows.append(f"incident_linked_watchlist_count: {sum(len(row.get('linked_watchlist_keys') or ()) for row in display_rows)}")
    rows.append("material_update_reasons: " + _format_counts(_material_reason_counts(display_rows)))
    rows.append(
        "market_reaction_unknown_cause: "
        + str(sum(
            1 for row in display_rows
            if (
                _incident_flag_true(row.get("market_reaction_observed"))
                or _incident_flag_true(row.get("market_reaction_confirmed"))
            )
            and row.get("current_cause_status") in {"unknown", "ruled_out"}
        ))
    )
    rows.append(
        "confirmed_cause_missing_market_data: "
        + str(sum(
            1 for row in display_rows
            if row.get("current_cause_status") == "confirmed" and not row.get("market_context_source")
        ))
    )
    rows.append("")
    if unlinked_canonical:
        rows.append("Top unlinked canonical incidents:")
        for row in unlinked_canonical[:10]:
            rows.append(
                f"- {row.get('canonical_name') or row.get('incident_id')}: "
                f"relevance={row.get('incident_relevance_status') or 'unknown'} "
                f"persistence={row.get('canonical_persistence_reason') or 'unknown'}"
            )
        rows.append("")
    rows.append("Notable incidents:")
    for row in display_rows[:25]:
        rows.extend(_incident_lines(row))
    rows.append("")
    rows.append("No sends, trades, paper rows, normal RSI rows, or event-fade state were changed.")
    return "\n".join(rows).rstrip()
def _incident_lines(row: Mapping[str, Any]) -> list[str]:
    assets = row.get("linked_assets") or []
    frame_disagreement = _incident_flag_true(row.get("frame_rule_disagreement"))
    reaction_confirmed = _incident_flag_true(row.get("market_reaction_confirmed"))
    reaction_observed = _incident_flag_true(
        row.get("market_reaction_observed")
    ) or reaction_confirmed
    causal_confirmed = _incident_flag_true(row.get("causal_mechanism_confirmed"))
    asset_text = ", ".join(
        f"{asset.get('symbol') or asset.get('coin_id') or 'asset'}:{asset.get('role') or 'unknown'}"
        for asset in list(assets)[:4]
        if isinstance(asset, Mapping)
    ) or "none"
    lines = [
        (
            f"- {row.get('incident_id')}: {row.get('canonical_name')} "
            f"archetype={row.get('event_archetype')} cause={row.get('current_cause_status')} "
            f"sources={row.get('source_update_count')}/{row.get('independent_source_count')} "
            f"confidence={row.get('incident_confidence')} "
            f"relevance={row.get('incident_relevance_status') or 'unknown'}:{row.get('incident_relevance_score') or 0}"
        ),
        f"  assets: {asset_text}",
        (
            "  catalyst_frames: "
            f"main={row.get('main_frame_type') or 'unknown'} "
            f"role={row.get('main_frame_role') or 'unknown'} "
            f"subject={row.get('main_frame_subject') or 'unknown'} "
            f"actor={row.get('main_frame_actor') or 'unknown'} "
            f"object={row.get('main_frame_object') or 'unknown'} "
            f"background={len(row.get('background_frame_ids') or [])} "
            f"negated={len(row.get('negated_frame_ids') or [])} "
            f"corrective={len(row.get('corrective_frame_ids') or [])} "
            f"rule={row.get('rule_predicted_impact_path') or 'unknown'} "
            f"llm={row.get('llm_predicted_main_frame_type') or 'unknown'} "
            f"disagreement={str(frame_disagreement).lower()} "
            f"resolution={row.get('disagreement_resolution') or 'unknown'} "
            f"context={row.get('background_context_summary') or 'none'}"
        ),
        "  persistence: "
        + str(row.get("canonical_persistence_reason") or "unknown")
        + " reasons="
        + (", ".join(str(item) for item in row.get("incident_relevance_reasons") or ()) or "none"),
        (
            "  link_quality: "
            f"raw={int(row.get('raw_link_count') or 0)} "
            f"qualified={int(row.get('qualified_link_count') or 0)} "
            f"weak={int(row.get('weak_link_count') or 0)} "
            f"quality_blocked={int(row.get('quality_blocked_link_count') or 0)} "
            f"unknown_role={int(row.get('unknown_role_link_count') or 0)} "
            f"reasons="
            + (", ".join(str(item) for item in row.get("link_quality_reasons") or ()) or "none")
        ),
        "  material_update_reasons: "
        + (", ".join(str(item) for item in row.get("material_update_reasons") or ()) or "none"),
        (
            "  market_vs_cause: "
            f"reaction_observed={str(reaction_observed).lower()} "
            f"reaction_confirmed={str(reaction_confirmed).lower()} "
            f"level={row.get('market_reaction_level') or 'unknown'} "
            f"causal={str(causal_confirmed).lower()} "
            f"source={row.get('market_context_source') or 'none'}"
        ),
    ]
    if row.get("conflicting_claims"):
        lines.append("  conflicting_claims: " + ", ".join(str(item) for item in row.get("conflicting_claims") or ()))
    if row.get("warnings"):
        lines.append("  warnings: " + ", ".join(str(item) for item in row.get("warnings") or ()))
    return lines
def _format_filter_summary(filters: Mapping[str, Any]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(filters.items())) or "none"
def _counts(rows: Iterable[Mapping[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return counts
def _score_buckets(rows: Iterable[Mapping[str, Any]], key: str) -> dict[str, int]:
    buckets = {"0-24": 0, "25-49": 0, "50-74": 0, "75-100": 0}
    for row in rows:
        score = _float(row.get(key))
        if score < 25:
            buckets["0-24"] += 1
        elif score < 50:
            buckets["25-49"] += 1
        elif score < 75:
            buckets["50-74"] += 1
        else:
            buckets["75-100"] += 1
    return {key: value for key, value in buckets.items() if value}
def _asset_role_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for asset in row.get("linked_assets") or ():
            if not isinstance(asset, Mapping):
                continue
            role = str(asset.get("role") or "unknown")
            counts[role] = counts.get(role, 0) + 1
    return counts
def _absence_claim_count(rows: Iterable[Mapping[str, Any]]) -> int:
    return sum(
        1
        for row in rows
        for claim in row.get("claim_history") or ()
        if isinstance(claim, Mapping)
        and str(claim.get("claim_type") or "") == "absence_of_validated_catalyst"
    )
def _format_counts(counts: Mapping[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
