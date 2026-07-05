"""Market State helpers for research cards."""

from __future__ import annotations

from .runtime import *

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

__all__ = (
    '_market_lines',
    '_derivatives_supply_liquidity_lines',
    '_opportunity_lane_lines',
    '_format_market_context_age',
    '_targeted_market_refresh_line',
    '_float_value',
)
