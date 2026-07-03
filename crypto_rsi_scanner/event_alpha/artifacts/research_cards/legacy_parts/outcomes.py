"""Outcomes helpers for legacy research cards."""

from __future__ import annotations

from .runtime import *

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

__all__ = (
    '_impact_hypothesis_lines',
    '_impact_hypothesis_quality_gate_line',
    '_impact_hypothesis_promotion_line',
    '_impact_hypothesis_wrong_line',
    '_quality_gate_lines',
    '_monitor_lines',
    '_lifecycle_lines',
)
