"""Event Alpha near-miss report rendering."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Mapping

import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
import crypto_rsi_scanner.event_alpha.outcomes.quality_fields as event_alpha_quality_fields
import crypto_rsi_scanner.event_alpha.radar.core_opportunities as event_core_opportunities
import crypto_rsi_scanner.event_alpha.radar.llm.evidence_planner as event_llm_evidence_planner
import crypto_rsi_scanner.event_alpha.radar.market_confirmation as event_market_confirmation
import crypto_rsi_scanner.event_alpha.radar.opportunity_verdict as event_opportunity_verdict
import crypto_rsi_scanner.event_alpha.providers.source_packs as event_source_packs
import crypto_rsi_scanner.event_alpha.providers.source_registry as event_source_registry
from .models import *  # noqa: F403 - split modules share historical model names


def format_near_miss_report(
    near_misses: Iterable[EventNearMissCandidate],
    *,
    profile: str | None = None,
) -> str:
    rows = [
        "=" * 76,
        "EVENT ALPHA NEAR-MISS REPORT (research-only; no sends/trades)",
        "=" * 76,
    ]
    if profile:
        rows.append(f"profile: {profile}")
    items = list(near_misses)
    near_items, upgrade_items = split_near_miss_candidates(items)
    rows.append(f"near_misses: {len(near_items)}")
    rows.append(f"upgrade_candidates: {len(upgrade_items)}")
    if not items:
        rows.append("")
        rows.append("No near-miss candidates found.")
        rows.append("Research-only report; no notifications, trades, paper rows, live RSI rows, or triggers were created.")
        return "\n".join(rows)
    rows.append("")
    for title, section_items in (
        ("Near-Miss Candidates", near_items),
        ("Upgrade Candidates", upgrade_items),
    ):
        rows.append(f"## {title}")
        if not section_items:
            rows.append("- none")
            rows.append("")
            continue
        for item in section_items:
            _append_candidate_report_lines(rows, item)
        rows.append("")
    rows.append("Research-only report; no notifications, trades, paper rows, live RSI rows, or triggers were created.")
    return "\n".join(rows)


def _append_candidate_report_lines(rows: list[str], item: EventNearMissCandidate) -> None:
    rows.append(
        f"- {item.symbol or 'UNKNOWN'}/{item.coin_id or 'unknown'} "
        f"score={item.opportunity_score_before:.0f}"
        + (
            f"->{item.opportunity_score_after:.0f}"
            if item.opportunity_score_after is not None
            and round(item.opportunity_score_after, 2) != round(item.opportunity_score_before, 2)
            else ""
        )
        + f" level={item.opportunity_level_before}"
        + (f"->{item.opportunity_level_after}" if item.opportunity_level_after and item.opportunity_level_after != item.opportunity_level_before else "")
    )
    rows.append(f"  near_miss_id: {item.near_miss_id}")
    if item.hypothesis_id:
        rows.append(f"  hypothesis_id: {item.hypothesis_id}")
    if item.incident_id:
        rows.append(f"  incident_id: {item.incident_id}")
    rows.append(f"  route: {item.final_route_before or 'unknown'}->{item.final_route_after or item.final_route_before or 'unknown'}")
    rows.append("  missing_evidence: " + (", ".join(item.missing_evidence) if item.missing_evidence else "none"))
    rows.append("  refresh_actions: " + (", ".join(item.recommended_refresh_actions) if item.recommended_refresh_actions else "none"))
    rows.append(
        "  market_refresh: "
        f"attempted={str(item.market_refresh_attempted).lower()} "
        f"success={str(item.market_refresh_success).lower()} "
        f"provider={item.market_refresh_provider or item.market_context_source or 'none'} "
        f"score={item.market_confirmation_before if item.market_confirmation_before is not None else 'n/a'}"
        f"->{item.market_confirmation_after if item.market_confirmation_after is not None else 'n/a'} "
        f"age={_format_age(item.market_context_age_seconds)} "
        f"quality={item.market_context_data_quality or 'unknown'} "
        f"status={item.refresh_upgrade_status or item.upgrade_reason or item.no_upgrade_reason or 'pending'}"
    )
    if item.derivatives_refresh_attempted or item.supply_refresh_attempted:
        rows.append(
            "  enrichment_refresh: "
            f"derivatives={str(item.derivatives_refresh_success).lower()} "
            f"supply={str(item.supply_refresh_success).lower()}"
        )
    if item.evidence_refresh_queries:
        rows.append("  evidence_queries: " + "; ".join(item.evidence_refresh_queries))
    rows.append(
        "  source_pack: "
        f"{item.source_pack or 'unknown'} coverage={item.provider_coverage_status or 'unknown'} "
        f"absence_meaningful={str(bool(item.evidence_absence_is_meaningful)).lower()} "
        f"gap={item.source_coverage_gap or 'none'}"
    )
    if item.evidence_acquisition_plan:
        needed = item.evidence_acquisition_plan.get("evidence_needed") or ()
        queries = item.evidence_acquisition_plan.get("evidence_query_plan") or ()
        rows.append(
            "  evidence_plan: "
            f"needed={'; '.join(str(value) for value in list(needed)[:4]) or 'none'} "
            f"queries={len(queries) if isinstance(queries, Iterable) and not isinstance(queries, (str, bytes, Mapping)) else 'n/a'}"
        )
    rows.append(f"  outcome: {item.upgrade_reason or item.no_upgrade_reason or 'pending_refresh'}")
    if item.warnings:
        rows.append("  warnings: " + "; ".join(item.warnings))


def _format_age(age_seconds: Any) -> str:
    value = _float(age_seconds)
    if value is None:
        return "n/a"
    age_hours = value / 3600.0
    if age_hours < 1:
        return f"{age_hours * 60:.0f}m"
    return f"{age_hours:.1f}h"
