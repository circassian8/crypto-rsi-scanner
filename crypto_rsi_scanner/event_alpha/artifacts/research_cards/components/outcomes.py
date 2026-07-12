"""Outcomes helpers for research cards."""

from __future__ import annotations

from .runtime import *

def _impact_hypothesis_lines(entry: event_watchlist.EventWatchlistEntry | None) -> list[str]:
    if entry is None:
        return []
    components = dict(entry.latest_score_components or {})
    if not _has_impact_hypothesis_context(entry, components):
        return []
    context = _impact_hypothesis_context(entry, components)
    lines = (
        _impact_hypothesis_incident_lines(components, context)
        + _impact_hypothesis_frame_lines(components, context)
        + _impact_hypothesis_candidate_lines(entry, components, context)
        + _impact_hypothesis_market_lines(components, context)
        + _impact_hypothesis_verdict_lines(entry, components, context)
    )
    if context["validation_reasons"]:
        lines.append("- Validation evidence: " + "; ".join(str(item) for item in context["validation_reasons"][:4]))
    if context["why_not_promoted"]:
        lines.append(
            "- Why not promoted diagnostics: "
            + event_alpha_reason_text.humanize_event_alpha_reasons(context["why_not_promoted"], limit=4)
        )
    return lines


def _has_impact_hypothesis_context(
    entry: event_watchlist.EventWatchlistEntry,
    components: Mapping[str, Any],
) -> bool:
    return entry.relationship_type == "impact_hypothesis" or any(
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


def _list_value(value: Any) -> list[Any]:
    return [value] if isinstance(value, str) else list(value or [])


def _impact_hypothesis_context(
    entry: event_watchlist.EventWatchlistEntry,
    components: Mapping[str, Any],
) -> dict[str, Any]:
    validated_asset = components.get("validated_asset") if isinstance(components.get("validated_asset"), Mapping) else {}
    verdict_copy = event_opportunity_verdict.build_verdict_aware_upgrade_downgrade_text(components)
    digest_eligible = components.get("digest_eligible_by_impact_path")
    if digest_eligible is None and _is_promoted_components(components):
        digest_eligible = True
    gate_line = _impact_hypothesis_quality_gate_line(entry, components)
    final_opportunity_level = components.get("final_opportunity_level") or components.get("opportunity_level") or "unknown"
    why_digest_ineligible = components.get("why_digest_ineligible") or verdict_copy.missing_evidence_text
    upgrade = event_opportunity_verdict.explain_upgrade_path(components=components)
    if _is_promoted_components(components):
        upgrade_text = verdict_copy.upgrade_text
        downgrade_text = verdict_copy.downgrade_text
    else:
        upgrade_text = (
            event_alpha_reason_text.humanize_event_alpha_reasons(upgrade.upgrade_requirements, limit=6)
            or verdict_copy.upgrade_text
        )
        downgrade_text = (
            event_alpha_reason_text.humanize_event_alpha_reasons(upgrade.downgrade_warnings, limit=6)
            or verdict_copy.downgrade_text
        )
    market = _impact_hypothesis_market_context(components)
    return {
        **market,
        "validated_symbol": components.get("validated_symbol") or validated_asset.get("symbol") or entry.symbol,
        "validated_coin_id": components.get("validated_coin_id") or validated_asset.get("coin_id") or entry.coin_id,
        "candidate_symbols": components.get("candidate_symbols") or [],
        "validation_reasons": _list_value(
            components.get("validation_reasons") or components.get("validation_reason") or []
        ),
        "gate_line": gate_line,
        "impact_path_reason": (
            components.get("impact_path_reason")
            or _canonical_reason_from_components(components)
            or "not available"
        ),
        "impact_path_type": components.get("impact_path_type") or components.get("primary_impact_path") or "not available",
        "candidate_role": components.get("candidate_role") or "not available",
        "asset_kind": components.get("asset_kind") or "unknown",
        "role_source": components.get("role_source") or components.get("asset_role_source") or "unknown",
        "impact_path_strength": (
            components.get("impact_path_strength")
            or _canonical_strength_from_components(components)
            or "not available"
        ),
        "digest_eligible": digest_eligible,
        "why_digest_ineligible": why_digest_ineligible,
        "final_opportunity_level": final_opportunity_level,
        "final_opportunity_score": components.get("final_opportunity_score") or components.get("opportunity_score_final"),
        "verdict_reasons": _list_value(components.get("opportunity_verdict_reasons") or []),
        "missing_requirements": _list_value(components.get("missing_requirements") or []),
        "manual_verification_items": _list_value(components.get("manual_verification_items") or []),
        "why_not_promoted": _list_value(components.get("why_not_promoted") or []),
        "upgrade_text": upgrade_text,
        "downgrade_text": downgrade_text,
        "local_only_due_to_weak_cooccurrence": _local_only_due_to_weak_cooccurrence(
            final_opportunity_level=final_opportunity_level,
            gate_line=gate_line,
            why_digest_ineligible=why_digest_ineligible,
        ),
    }


def _impact_hypothesis_market_context(components: Mapping[str, Any]) -> dict[str, Any]:
    market_context_source = components.get("market_context_source") or "not available"
    market_context_quality = (
        components.get("market_context_freshness_status")
        or components.get("market_context_data_quality")
        or "unknown"
    )
    market_confirmation_score = components.get("market_confirmation_score")
    market_confirmation_level = components.get("market_confirmation_level") or "not available"
    market_data_freshness = (
        components.get("market_data_freshness")
        or components.get("market_context_freshness_status")
        or "not available"
    )
    market_reaction_confirmation = components.get("market_reaction_confirmation") or market_confirmation_level
    market_confirmation_summary = (
        components.get("market_confirmation_summary")
        or _canonical_market_summary_from_components(components)
        or "not available"
    )
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
    return {
        "market_context_source": market_context_source,
        "market_context_age": _format_market_context_age(components),
        "market_context_quality": market_context_quality,
        "freshness_cap": components.get("market_context_freshness_cap_applied"),
        "market_reaction_confirmed": components.get("market_reaction_confirmed"),
        "causal_mechanism_confirmed": components.get("causal_mechanism_confirmed"),
        "market_confirmation_score": market_confirmation_score,
        "market_confirmation_level": market_confirmation_level,
        "market_data_freshness": market_data_freshness,
        "market_reaction_confirmation": market_reaction_confirmation,
        "market_confirmation_summary": market_confirmation_summary,
    }


def _local_only_due_to_weak_cooccurrence(
    *,
    final_opportunity_level: Any,
    gate_line: str,
    why_digest_ineligible: Any,
) -> bool:
    return (
        final_opportunity_level in {"local_only", "exploratory", "unknown", ""}
        and (
            "impact_path_not_validated" in gate_line
            or "weak_validated_local_only" in gate_line
            or str(why_digest_ineligible or "none").strip().casefold() not in {"", "none", "not available"}
        )
    )


def _impact_hypothesis_incident_lines(
    components: Mapping[str, Any],
    context: Mapping[str, Any],
) -> list[str]:
    return [
        f"- Validated asset: {context['validated_symbol'] or 'unknown'}/{context['validated_coin_id'] or 'unknown'}",
        f"- Incident: {components.get('canonical_incident_name') or 'unknown'} ({components.get('incident_id') or 'unknown'})",
        f"- Incident relevance: {components.get('incident_relevance_status') or 'unknown'} "
        f"score={components.get('incident_relevance_score') if components.get('incident_relevance_score') is not None else 'n/a'}",
        f"- Canonical persistence reason: {components.get('canonical_persistence_reason') or 'unknown'}",
        f"- Incident relevance reasons: {'; '.join(str(item) for item in (components.get('incident_relevance_reasons') or [])[:4]) if components.get('incident_relevance_reasons') else 'none'}",
    ]


def _impact_hypothesis_frame_lines(
    components: Mapping[str, Any],
    context: Mapping[str, Any],
) -> list[str]:
    negated_frame_ids = components.get("negated_frame_ids") or []
    corrective_frame_ids = components.get("corrective_frame_ids") or []
    rejected_impact_paths = components.get("rejected_impact_paths") or []
    frame_disagreement = components.get("frame_rule_disagreement")
    return [
        f"- Event archetype: {components.get('event_archetype') or 'unknown'}",
        f"- Main catalyst: {components.get('main_frame_type') or 'unknown'} ({components.get('main_frame_role') or 'unknown'})",
        f"- Frame status: {components.get('frame_status') or 'unknown'}",
        f"- Main catalyst subject/actor/object: {components.get('main_frame_subject') or 'unknown'} / {components.get('main_frame_actor') or 'unknown'} / {components.get('main_frame_object') or 'unknown'}",
        f"- Main catalyst evidence: {components.get('main_frame_evidence_quote') or 'none'}",
        f"- Main catalyst selected because: {components.get('selected_main_catalyst_reason') or 'unknown'}",
        f"- Rule vs LLM frame: rule={components.get('rule_predicted_impact_path') or 'unknown'} "
        f"llm={components.get('llm_predicted_main_frame_type') or 'unknown'} "
        f"disagreement={str(bool(frame_disagreement)).lower() if frame_disagreement is not None else 'unknown'} "
        f"resolution={components.get('disagreement_resolution') or 'unknown'}",
        f"- Background context: {components.get('background_context_summary') or 'none'}",
        f"- Negated/corrective frames: {len(negated_frame_ids) + len(corrective_frame_ids)}",
        f"- Rejected/background impact paths: {'; '.join(str(item) for item in rejected_impact_paths[:4]) if rejected_impact_paths else 'none'}",
        f"- Catalyst frame evidence: {_frame_summary_value(components.get('frame_summary') or [])}",
        f"- Primary subject: {components.get('primary_subject') or 'unknown'}",
        f"- Affected ecosystem: {components.get('affected_ecosystem') or 'unknown'}",
        f"- Cause status: {components.get('cause_status') or 'unknown'}",
        f"- Incident confidence: {components.get('incident_confidence') if components.get('incident_confidence') is not None else 'n/a'}",
        f"- Claim polarity: {', '.join(str(item) for item in (components.get('claim_polarities') or [])[:6]) if components.get('claim_polarities') else 'unknown'}",
        f"- Claim history: {_claim_history_summary(components.get('claim_history') or [])}",
        f"- Independent source domains: {', '.join(str(item) for item in (components.get('independent_source_domains') or components.get('source_domains') or [])[:6]) if (components.get('independent_source_domains') or components.get('source_domains')) else 'none'}",
        f"- Conflicting claims: {'; '.join(str(item) for item in (components.get('conflicting_claims') or [])[:4]) if components.get('conflicting_claims') else 'none'}",
    ]


def _impact_hypothesis_candidate_lines(
    entry: event_watchlist.EventWatchlistEntry,
    components: Mapping[str, Any],
    context: Mapping[str, Any],
) -> list[str]:
    role_evidence = components.get("role_evidence") or []
    return [
        f"- Original sector hypothesis: {', '.join(str(item) for item in (components.get('candidate_sectors') or [])[:6]) or components.get('hypothesis_scope') or 'unknown'}",
        f"- Candidate source: {entry.latest_source or 'impact_hypothesis'}",
        f"- Candidate Discovery Origin: {components.get('candidate_source') or components.get('source') or entry.latest_source or 'impact_hypothesis'}",
        f"- Candidate symbols considered: {', '.join(str(item) for item in context['candidate_symbols'][:8]) if context['candidate_symbols'] else 'none'}",
        f"- Playbook: {entry.latest_playbook_type or 'impact_hypothesis'}",
        f"- Impact path type: {context['impact_path_type']}",
        f"- Candidate role: {context['candidate_role']}",
        f"- Asset kind: {context['asset_kind']}",
        f"- Role source: {context['role_source']}",
        f"- Identity confidence: {components.get('identity_confidence') if components.get('identity_confidence') is not None else 'n/a'}",
        f"- Identity evidence: {_display_list_value(components.get('identity_evidence') or [])}",
        f"- Collision risk: {components.get('collision_risk') or 'none'}",
        f"- Role capabilities: {_role_capabilities_line(components.get('role_capabilities') or {})}",
        f"- Role validation failures: {_display_list_value(components.get('role_validation_failures') or [])}",
        f"- Candidate role confidence: {components.get('role_confidence') if components.get('role_confidence') is not None else 'n/a'}",
        f"- Candidate role evidence: {'; '.join(str(item) for item in role_evidence[:4]) if role_evidence else 'none'}",
        f"- Impact path strength: {context['impact_path_strength']}",
        f"- Impact path reason: {context['impact_path_reason']}",
    ]


def _impact_hypothesis_market_lines(
    components: Mapping[str, Any],
    context: Mapping[str, Any],
) -> list[str]:
    return [
        f"- Opportunity score v2: {components.get('opportunity_score_v2') if components.get('opportunity_score_v2') is not None else 'n/a'}",
        f"- Final opportunity verdict: {context['final_opportunity_level']} / {context['final_opportunity_score'] if context['final_opportunity_score'] is not None else 'n/a'}",
        f"- Final verdict source: {components.get('final_verdict_source') or 'initial'} ({components.get('final_verdict_reason') or 'no refresh override'})",
        f"- Source/evidence specificity: {components.get('evidence_specificity_score') if components.get('evidence_specificity_score') is not None else 'n/a'}",
        f"- Evidence quality: {components.get('source_class') or 'unknown'}/{components.get('evidence_specificity') or 'unknown'} / {components.get('evidence_quality_score') if components.get('evidence_quality_score') is not None else 'n/a'}",
        f"- Market confirmation: {context['market_confirmation_level']} / {context['market_confirmation_score'] if context['market_confirmation_score'] is not None else 'n/a'}",
        f"- Market freshness: {context['market_data_freshness']}",
        f"- Market reaction confirmation: {context['market_reaction_confirmation']}",
        f"- Market context source: {context['market_context_source']} ({context['market_context_quality']}; age={context['market_context_age']}; cap_applied={str(bool(context['freshness_cap'])).lower()})",
        "- Targeted market refresh: " + _targeted_market_refresh_line(components),
        f"- Market reaction confirmed: {str(bool(context['market_reaction_confirmed'])).lower() if context['market_reaction_confirmed'] is not None else 'unknown'}",
        f"- Causal mechanism confirmed: {str(bool(context['causal_mechanism_confirmed'])).lower() if context['causal_mechanism_confirmed'] is not None else 'unknown'}",
        f"- Market summary: {context['market_confirmation_summary']}",
    ]


def _impact_hypothesis_verdict_lines(
    entry: event_watchlist.EventWatchlistEntry,
    components: Mapping[str, Any],
    context: Mapping[str, Any],
) -> list[str]:
    manual_verification_items = context["manual_verification_items"]
    return [
        f"- Impact path digest eligible: {str(bool(context['digest_eligible'])).lower() if context['digest_eligible'] is not None else 'unknown'}",
        f"- Missing evidence / gate failure: {context['why_digest_ineligible']}",
        f"- Opportunity verdict reasons: {'; '.join(str(item) for item in context['verdict_reasons'][:4]) if context['verdict_reasons'] else 'none'}",
        f"- Missing requirements: {'; '.join(str(item) for item in context['missing_requirements'][:4]) if context['missing_requirements'] else 'none'}",
        f"- Quality gate: {context['gate_line']}",
        f"- Local-only due to weak co-occurrence: {str(context['local_only_due_to_weak_cooccurrence']).lower()}",
        f"- Why promoted/local-only: {_impact_hypothesis_promotion_line(entry, components, context['gate_line'])}",
        "- Safety label: catalyst link validated, but this is not a calibrated strategy or trade signal.",
        "- Why it may be wrong: " + _impact_hypothesis_wrong_line(components),
        "- What to verify manually: "
        + (
            "; ".join(str(item) for item in manual_verification_items[:4])
            if manual_verification_items
            else "independent catalyst source, asset identity, liquidity/organic volume, and whether the catalyst actually affects this token."
        ),
        "- What would upgrade this candidate: " + context["upgrade_text"],
        "- What would invalidate this candidate: " + context["downgrade_text"],
    ]

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
        for row in sorted(
            feedback_rows,
            key=lambda item: str(item.get("feedback_marked_at") or ""),
            reverse=True,
        )[:5]:
            lines.append(
                f"- feedback: {row.get('feedback_label') or 'unknown'} at "
                f"{row.get('feedback_marked_at') or 'unknown'} "
                f"by {row.get('feedback_marked_by') or 'unknown'}"
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
        display_status = str(outcome.get("outcome_display_status") or "")
        evidence_label = (
            "eligible exact-authority evidence"
            if display_status == "eligible_performance_evidence"
            else "excluded diagnostic; not performance evidence"
        )
        lines.append(
            f"- outcome ({evidence_label}): "
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


def _feedback_evidence_diagnostic_lines(
    diagnostics: Mapping[str, Any],
) -> list[str]:
    reason_counts = diagnostics.get("feedback_exclusion_reason_counts")
    reasons = (
        ", ".join(
            f"{reason}={count}"
            for reason, count in sorted(reason_counts.items())
        )
        if isinstance(reason_counts, Mapping) and reason_counts
        else "none"
    )
    return [
        f"- Feedback rows supplied: {diagnostics.get('feedback_rows_supplied', 0)}",
        f"- Eligible exact-Core feedback rows: {diagnostics.get('feedback_rows_eligible', 0)}",
        (
            "- Eligible feedback rows matched to this card: "
            f"{diagnostics.get('feedback_rows_matched_to_card', 0)}"
        ),
        (
            "- Eligible feedback rows for other Core opportunities: "
            f"{diagnostics.get('feedback_rows_eligible_other_core', 0)}"
        ),
        f"- Excluded feedback rows: {diagnostics.get('feedback_rows_excluded', 0)}",
        f"- Aggregate exclusion reasons: {reasons}",
        "- Excluded feedback is aggregate diagnostics only and never supplies a card label.",
    ]

__all__ = (
    '_impact_hypothesis_lines',
    '_impact_hypothesis_quality_gate_line',
    '_impact_hypothesis_promotion_line',
    '_impact_hypothesis_wrong_line',
    '_quality_gate_lines',
    '_monitor_lines',
    '_lifecycle_lines',
    '_feedback_evidence_diagnostic_lines',
)
