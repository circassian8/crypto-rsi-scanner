"""Diagnostics helpers for legacy research cards."""

from __future__ import annotations

from .runtime import *

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

__all__ = (
    '_outcome_tracking_lines',
    '_outcome_horizon_value',
    '_monitor_value',
    '_verify_lines',
    '_claim_history_summary',
    '_frame_summary_value',
    '_history_lines',
    '_warnings',
    '_score',
    '_playbook_copy',
    '_why_it_matters',
    '_default_invalidation',
    '_trade_readiness_lines',
    '_check_value',
    '_card_components',
    '_float',
    '_playbook_direction',
)
