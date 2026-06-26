"""Decision-path audit reports for Event Alpha research opportunities."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Iterable, Mapping

from . import event_alpha_quality_fields, event_alpha_router, event_opportunity_verdict, event_watchlist


def format_opportunity_audit(
    target: str,
    *,
    hypotheses: Iterable[Mapping[str, Any] | object] = (),
    watchlist_entries: Iterable[event_watchlist.EventWatchlistEntry | Mapping[str, Any]] = (),
    alert_rows: Iterable[Mapping[str, Any]] = (),
    route_decisions: Iterable[event_alpha_router.EventAlphaRouteDecision | Mapping[str, Any]] = (),
    incident_rows: Iterable[Mapping[str, Any]] = (),
    profile: str | None = None,
) -> str:
    """Explain one candidate's research-only decision path."""
    clean = str(target or "").strip()
    if not clean:
        return "Event opportunity audit failed: target is required."
    incidents = [dict(row) for row in incident_rows if isinstance(row, Mapping)]
    match = _find_match(clean, hypotheses, watchlist_entries, alert_rows, route_decisions, incidents)
    if match is None:
        return "\n".join([
            "=" * 76,
            "EVENT OPPORTUNITY AUDIT (research-only)",
            "=" * 76,
            f"target: {clean}",
            f"profile: {profile or 'default'}",
            "No matching hypothesis, watchlist row, alert snapshot, or route decision found.",
            "No secrets, sends, trades, paper rows, normal RSI rows, or event-fade state were touched.",
        ])
    row = match["row"]
    components = _components(row)
    incident = _incident_context(row, components, incidents)
    upgrade = event_opportunity_verdict.explain_upgrade_path(components=components)
    lines = [
        "=" * 76,
        "EVENT OPPORTUNITY AUDIT (research-only)",
        "=" * 76,
        f"target: {clean}",
        f"profile: {profile or 'default'}",
        f"matched_source: {match['source']}",
        f"quality_field_source: {_quality_source(row)}",
        "",
        "## Candidate summary",
        f"- symbol/coin: {_value(row, 'symbol', components.get('validated_symbol'), default='SECTOR')}/{_value(row, 'coin_id', components.get('validated_coin_id'), default='unknown')}",
        f"- event/hypothesis: {_value(row, 'event_id', 'hypothesis_id', default='unknown')}",
        f"- external catalyst: {_value(row, 'external_asset', components.get('external_asset'), default='unknown')}",
        f"- playbook: {_value(row, 'playbook_type', 'latest_playbook_type', components.get('playbook_type'), default='unknown')}",
        f"- state/tier: {_value(row, 'state', default='unknown')} / {_value(row, 'tier', 'latest_tier', default='unknown')}",
        "",
        "## Evidence chain",
        f"- raw source summary: {_value(row, 'raw_evidence_summary', 'event_name', 'latest_event_name', default='unknown')}",
        f"- source/provider: {_value(row, 'source', 'latest_source', default='unknown')}",
        f"- source count: {_value(row, 'source_count', default='0')}",
        f"- evidence quotes: {_list_value(row.get('evidence_quotes') or components.get('evidence_quotes'))}",
        f"- validation reasons: {_list_value(row.get('validation_reasons') or components.get('validation_reasons'))}",
        f"- external entities: {_asset_list(row.get('external_entities') or components.get('external_entities'))}",
        f"- crypto candidates: {_asset_list(row.get('crypto_candidate_assets') or components.get('crypto_candidate_assets'))}",
        f"- rejected candidates: {_asset_list(row.get('rejected_candidate_assets') or components.get('rejected_candidate_assets'))}",
        "",
        "## Identity decision",
        f"- validated symbol: {components.get('validated_symbol') or row.get('validated_symbol') or row.get('symbol') or 'unknown'}",
        f"- validated coin_id: {components.get('validated_coin_id') or row.get('validated_coin_id') or row.get('coin_id') or 'unknown'}",
        f"- candidate role: {components.get('candidate_role') or row.get('candidate_role') or 'unknown'}",
        f"- identity warnings: {_list_value(row.get('warnings') or components.get('warnings'))}",
        "",
        "## Incident",
        *_incident_lines(incident, row, components),
        "",
        "## Impact path decision",
        f"- impact path: {components.get('impact_path_type') or row.get('impact_path_type') or 'unknown'}",
        f"- strength: {components.get('impact_path_strength') or row.get('impact_path_strength') or 'unknown'}",
        f"- reason: {components.get('impact_path_reason') or row.get('impact_path_reason') or 'unknown'}",
        f"- digest gate: {components.get('digest_eligible_by_impact_path') if components.get('digest_eligible_by_impact_path') is not None else 'unknown'}",
        "",
        "## Evidence quality decision",
        f"- source/evidence: {components.get('source_class') or row.get('source_class') or 'unknown'} / {components.get('evidence_specificity') or row.get('evidence_specificity') or 'unknown'}",
        f"- evidence score: {components.get('evidence_quality_score') or row.get('evidence_quality_score') or 'n/a'}",
        "",
        "## Market confirmation decision",
        f"- market level/score: {components.get('market_confirmation_level') or row.get('market_confirmation_level') or 'unknown'} / {components.get('market_confirmation_score') or row.get('market_confirmation_score') or 'n/a'}",
        f"- market reasons: {_list_value(components.get('market_confirmation_reasons') or row.get('market_confirmation_reasons'))}",
        f"- market missing: {_list_value(components.get('market_confirmation_missing_fields') or row.get('market_confirmation_missing_fields'))}",
        "",
        "## Final opportunity verdict",
        f"- level/score: {components.get('opportunity_level') or row.get('opportunity_level') or 'unknown'} / {components.get('opportunity_score_final') or row.get('opportunity_score_final') or 'n/a'}",
        f"- reasons: {_list_value(components.get('opportunity_verdict_reasons') or row.get('opportunity_verdict_reasons'))}",
        f"- why local-only: {components.get('why_local_only') or row.get('why_local_only') or 'none'}",
        f"- why not watchlist: {components.get('why_not_watchlist') or row.get('why_not_watchlist') or 'none'}",
        "",
        "## Router decision",
        f"- route: {_value(row, 'route', default=match.get('route') or 'not_routed')}",
        f"- notification lane: {_value(row, 'lane', default=match.get('lane') or 'local_only')}",
        f"- router reason: {_value(row, 'route_reason', 'reason', default=match.get('reason') or 'not routed or stored locally')}",
        "- TRIGGERED_FADE was not created unless the row is already a deterministic proxy_fade/event_fade trigger.",
        "",
        "## Notification and feedback status",
        f"- delivery status: {_value(row, 'delivered_status', 'delivery_state', default='not_delivered_or_unknown')}",
        f"- feedback status: {_value(row, 'feedback_status', default='pending_or_unknown')}",
        f"- feedback label: {_value(row, 'label', 'feedback', default='none')}",
        "",
        "## Missing evidence",
        f"- missing requirements: {_list_value(components.get('missing_requirements') or row.get('missing_requirements'))}",
        "",
        "## What would upgrade this candidate",
        "- " + "; ".join(upgrade.upgrade_requirements[:8]),
        "",
        "## What would downgrade / invalidate this candidate",
        "- " + "; ".join(upgrade.downgrade_warnings[:8]),
        "",
        "## Feedback command",
        f"- make event-feedback-watch PROFILE={profile or 'notify_llm'} FEEDBACK_TARGET='{_audit_feedback_target(row, clean)}'",
        "",
        "No secrets, Telegram sends, trades, paper rows, normal RSI rows, or event-fade state were touched.",
    ]
    return "\n".join(lines)


def _find_match(
    target: str,
    hypotheses: Iterable[Mapping[str, Any] | object],
    entries: Iterable[event_watchlist.EventWatchlistEntry | Mapping[str, Any]],
    alerts: Iterable[Mapping[str, Any]],
    decisions: Iterable[event_alpha_router.EventAlphaRouteDecision | Mapping[str, Any]],
    incidents: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any] | None:
    clean = target[3:] if target.startswith("ea:") else target
    for decision in decisions:
        if isinstance(decision, event_alpha_router.EventAlphaRouteDecision):
            if target in {
                decision.alert_id,
                decision.card_id,
                "ea:" + decision.entry.key,
                decision.entry.key,
                decision.entry.event_id,
                decision.entry.symbol,
                decision.entry.coin_id,
            } or clean in {decision.entry.symbol, decision.entry.coin_id}:
                return {
                    "source": "route_decision",
                    "row": _entry_row(decision.entry),
                    "route": decision.route.value,
                    "lane": decision.lane.value,
                    "reason": decision.reason,
                }
        else:
            row = dict(decision)
            if _row_matches(row, clean, target):
                return {"source": "route_decision", "row": row}
    for entry in entries:
        row = _entry_row(entry)
        if _row_matches(row, clean, target):
            return {"source": "watchlist", "row": row}
    for row in alerts:
        row = dict(row)
        if _row_matches(row, clean, target):
            return {"source": "alert_snapshot", "row": row}
    for item in hypotheses:
        row = _row(item)
        if _row_matches(row, clean, target):
            return {"source": "impact_hypothesis", "row": row}
    for incident in incidents:
        row = dict(incident)
        if _row_matches(row, clean, target):
            return {"source": "incident", "row": row}
    return None


def _row_matches(row: Mapping[str, Any], clean: str, original: str) -> bool:
    keys = {
        row.get("alert_id"),
        row.get("alert_key"),
        row.get("card_id"),
        row.get("key"),
        row.get("event_id"),
        row.get("hypothesis_id"),
        row.get("incident_id"),
        row.get("canonical_name"),
        row.get("symbol"),
        row.get("coin_id"),
    }
    text_keys = {str(value) for value in keys if value not in (None, "")}
    return clean in text_keys or original in text_keys or ("ea:" + clean) in text_keys


def _entry_row(entry: event_watchlist.EventWatchlistEntry | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(entry, Mapping):
        return dict(entry)
    row = asdict(entry)
    row["alert_id"] = event_alpha_router.alert_id_for_entry(entry)
    row["card_id"] = event_alpha_router.card_id_for_entry(entry)
    return row


def _row(value: Mapping[str, Any] | object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if is_dataclass(value):
        return asdict(value)
    return dict(getattr(value, "__dict__", {}) or {})


def _components(row: Mapping[str, Any]) -> dict[str, Any]:
    components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else {}
    if not components and isinstance(row.get("score_components"), Mapping):
        components = row.get("score_components")
    out = dict(components)
    for key, value in row.items():
        if key in event_alpha_quality_fields.REQUIRED_QUALITY_FIELDS:
            if value not in (None, "", [], {}):
                out[key] = value
        elif key not in out and value not in (None, "", [], {}):
            out[key] = value
    return event_alpha_quality_fields.ensure_quality_fields(out)


def _incident_context(
    row: Mapping[str, Any],
    components: Mapping[str, Any],
    incidents: Iterable[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    incident_id = str(row.get("incident_id") or components.get("incident_id") or "")
    if not incident_id:
        return row if str(row.get("row_type") or "") == "event_incident" else None
    for incident in incidents:
        if str(incident.get("incident_id") or "") == incident_id:
            return incident
    return row if row.get("incident_id") else None


def _incident_lines(
    incident: Mapping[str, Any] | None,
    row: Mapping[str, Any],
    components: Mapping[str, Any],
) -> list[str]:
    source = incident or row
    incident_id = source.get("incident_id") or components.get("incident_id")
    if not incident_id:
        return ["- incident link: no_incident"]
    claim_history = source.get("claim_history") or components.get("claim_history") or ()
    linked_assets = source.get("linked_assets") or components.get("linked_assets") or ()
    reaction_confirmed = source.get("market_reaction_confirmed")
    if reaction_confirmed is None:
        reaction_confirmed = components.get("market_reaction_confirmed")
    reaction_observed = source.get("market_reaction_observed")
    if reaction_observed is None:
        reaction_observed = components.get("market_reaction_observed")
    if reaction_observed is None:
        reaction_observed = reaction_confirmed
    causal = source.get("causal_mechanism_confirmed")
    if causal is None:
        causal = components.get("causal_mechanism_confirmed")
    return [
        f"- incident_id: {incident_id}",
        f"- canonical name: {source.get('canonical_name') or source.get('canonical_incident_name') or components.get('canonical_incident_name') or 'unknown'}",
        f"- primary subject: {source.get('primary_subject') or components.get('primary_subject') or 'unknown'}",
        f"- affected ecosystem: {source.get('affected_ecosystem') or components.get('affected_ecosystem') or 'unknown'}",
        f"- current cause status: {source.get('current_cause_status') or source.get('cause_status') or components.get('cause_status') or 'unknown'}",
        f"- claim history: {_claim_history_value(claim_history)}",
        f"- conflicting claims: {_list_value(source.get('conflicting_claims') or components.get('conflicting_claims'))}",
        f"- source updates: {source.get('source_update_count') or len(source.get('source_raw_ids') or []) or 'unknown'} "
        f"(independent={source.get('independent_source_count') or len(source.get('independent_source_domains') or []) or 'unknown'})",
        f"- market reaction vs causal mechanism: observed={str(bool(reaction_observed)).lower()} "
        f"confirmed={str(bool(reaction_confirmed)).lower()} "
        f"causal={str(bool(causal)).lower()} "
        f"source={source.get('market_context_source') or components.get('market_context_source') or 'none'}",
        f"- linked assets and roles: {_asset_list(linked_assets) if linked_assets else _asset_role_summary(row, components)}",
    ]


def _claim_history_value(value: Any) -> str:
    if not value:
        return "none"
    labels: list[str] = []
    for item in list(value)[:4]:
        if isinstance(item, Mapping):
            labels.append(
                f"{item.get('claim_type') or 'claim'}:"
                f"{item.get('polarity') or 'unknown'}/"
                f"{item.get('cause_status') or 'unknown'}"
            )
        else:
            labels.append(str(item))
    return "; ".join(labels) or "none"


def _asset_role_summary(row: Mapping[str, Any], components: Mapping[str, Any]) -> str:
    symbol = components.get("validated_symbol") or row.get("validated_symbol") or row.get("symbol")
    coin_id = components.get("validated_coin_id") or row.get("validated_coin_id") or row.get("coin_id")
    role = components.get("candidate_role") or row.get("candidate_role") or "unknown"
    if symbol or coin_id:
        return f"{symbol or coin_id}({role})"
    return "none"


def _quality_source(row: Mapping[str, Any]) -> str:
    source = event_alpha_quality_fields.quality_source(row, components_key="latest_score_components")
    if source == "nested_score_components":
        return "nested_score_components"
    if source in {"partial_quality_fields", "recomputed"}:
        return "recomputed" if source == "recomputed" else "partial_top_level_recomputed"
    return source


def _value(row: Mapping[str, Any], *keys: Any, default: str = "unknown") -> str:
    for key in keys:
        if isinstance(key, str):
            value = row.get(key)
        else:
            value = key
        if value not in (None, "", [], {}):
            return str(value)
    return default


def _list_value(value: Any) -> str:
    if value in (None, "", [], ()):
        return "none"
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        return ", ".join(f"{key}={child}" for key, child in list(value.items())[:6])
    return "; ".join(str(item) for item in list(value)[:6])


def _asset_list(value: Any) -> str:
    if not value:
        return "none"
    if isinstance(value, Mapping):
        value = [value]
    rows = []
    for item in list(value)[:6]:
        if isinstance(item, Mapping):
            rows.append(
                f"{item.get('symbol') or item.get('coin_id') or item.get('name') or 'asset'}"
                f"({item.get('rejection_reason') or item.get('identity_reason') or item.get('source') or 'candidate'})"
            )
        else:
            rows.append(str(item))
    return "; ".join(rows)


def _audit_feedback_target(row: Mapping[str, Any], fallback: str) -> str:
    return str(row.get("alert_id") or row.get("key") or row.get("hypothesis_id") or fallback)
