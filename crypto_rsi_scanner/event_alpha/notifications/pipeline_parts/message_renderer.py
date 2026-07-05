"""Message renderer for the notification pipeline."""

from __future__ import annotations

from .runtime import *

def format_exploratory_telegram_digest(
    items: Iterable[EventAlphaExploratoryDigestItem],
    *,
    profile: str | None = None,
    card_path_by_alert_id: Mapping[str, str | Path] | None = None,
    cfg: EventAlphaNotificationConfig | None = None,
) -> str:
    """Render low-confidence Event Alpha evidence for Telegram burn-in review."""
    cfg = cfg or EventAlphaNotificationConfig()
    _ = card_path_by_alert_id  # internal paths stay in artifacts/inbox, not Telegram.
    _ = cfg  # Kept for API compatibility; all exploratory items are rendered.
    keep = list(items)
    lines = [
        "<b>🟡 Exploratory Event Alpha Digest</b>",
        "<i>Low-confidence research leads — not trade signals</i>",
        f"Profile: {_esc(profile or 'unknown')}",
        f"Items: {len(keep)}",
        "Research-only / DAY-1 UNVALIDATED. No trades, paper trades, live RSI rows, execution, or TRIGGERED_FADE changes.",
    ]
    if not keep:
        lines.append("No exploratory candidates.")
        return "\n".join(lines)
    footer = "Research cards and feedback commands are available in local artifacts/inbox."
    displayed = 0
    for item in keep:
        decision = item.decision
        entry = decision.entry
        block = [
            "",
            f"{displayed + 1}. <b>{_esc(entry.symbol or entry.coin_id or 'UNKNOWN')} / {_esc(_human_asset_name(entry.coin_id))}</b>",
            f"   Move: {_esc(_move_summary(entry.latest_market_snapshot))}",
            f"   Volume/Mcap: {_esc(_volume_mcap_summary(entry.latest_market_snapshot))}",
            f"   Playbook: {_esc(_human_playbook(entry.latest_playbook_type or entry.latest_effective_playbook_type or entry.relationship_type))}",
            f"   Why surfaced: {_esc(_human_why(item.why_included))}",
            f"   Status: {_esc(_human_status(entry.state, entry.latest_tier, _suppression_reason(decision)))}",
            f"   Check next: {_esc(_human_check_next(item.what_to_verify))}",
            f"   Risk: {_esc(_human_risk(entry, decision))}",
        ]
        lines.extend(block)
        displayed += 1
    lines.append("")
    lines.append(footer)
    return "\n".join(lines)

def format_core_opportunity_telegram_digest(
    decisions: Iterable[event_alpha_router.EventAlphaRouteDecision],
    *,
    profile: str | None = None,
    card_path_by_alert_id: Mapping[str, object] | None = None,
    core_row_by_alert_id: Mapping[str, Mapping[str, Any]] | None = None,
    pipeline_result: Any | None = None,
    max_items: int | None = None,
) -> str:
    """Render a compact human-facing digest keyed by canonical core opportunities."""
    unique_keep: list[event_alpha_router.EventAlphaRouteDecision] = []
    seen_for_count: set[str] = set()
    for decision in decisions:
        if not event_alpha_router.alertable_after_quality_gate(decision):
            continue
        key = decision.alert_id
        if key in seen_for_count:
            continue
        seen_for_count.add(key)
        unique_keep.append(decision)
    total_items = len(unique_keep)
    limit = max(1, int(max_items or 0)) if max_items is not None else None
    keep = unique_keep[:limit] if limit is not None else unique_keep
    card_paths = {str(key): value for key, value in (card_path_by_alert_id or {}).items()}
    core_map = core_row_by_alert_id or {}
    title = "Event Alpha Research Digest"
    if any(event_alpha_router.final_route_value(item) == event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value for item in keep):
        title = "Event Alpha High-Priority Research"
    if any(
        str((_core_row_for_decision(item, core_map) or {}).get("opportunity_type") or "").upper() == "FADE_SHORT_REVIEW"
        for item in keep
    ):
        title = "Event Alpha Fade / Short-Review Research"
    if any(event_alpha_router.final_route_value(item) == event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH.value for item in keep):
        title = "Event Alpha Triggered Fade Research"
    lines = [
        f"<b>{_esc(title)}</b>",
        "<i>Research-only / unvalidated. Not a trade signal.</i>",
        f"Profile: {_esc(profile or 'default')}",
        f"Items: {len(keep)}",
    ]
    provider_summary = _provider_degradation_summary(pipeline_result)
    if provider_summary:
        lines.append(f"Provider status: {_esc(provider_summary)}")
    if not keep:
        lines.append("No router-approved escalations.")
        return "\n".join(lines)
    displayed = 0
    seen_core: set[str] = set()
    for decision in keep:
        core = _core_row_for_decision(decision, core_map) or {}
        core_id = str(core.get("core_opportunity_id") or "").strip()
        if core_id and core_id in seen_core:
            continue
        if core_id:
            seen_core.add(core_id)
        if max_items is not None and displayed >= max(1, int(max_items or 1)):
            break
        entry = decision.entry
        symbol = str(core.get("symbol") or core.get("validated_symbol") or entry.symbol or "UNKNOWN")
        coin_id = str(core.get("coin_id") or core.get("validated_coin_id") or entry.coin_id or "unknown")
        catalyst = str(
            core.get("canonical_incident_name")
            or core.get("incident_canonical_name")
            or core.get("event_name")
            or entry.latest_event_name
            or "unknown catalyst"
        )
        route = _human_route(event_alpha_router.final_route_value(decision))
        level = _human_reason(core.get("final_opportunity_level") or decision.opportunity_level or entry.opportunity_level or route)
        lane = _human_reason(core.get("opportunity_type") or "UNCONFIRMED_RESEARCH")
        market_state = _human_reason(core.get("market_state_class") or core.get("market_state") or "unknown")
        impact = _human_reason(core.get("impact_path_type") or entry.impact_path_type or entry.latest_effective_playbook_type)
        role = _human_reason(core.get("candidate_role") or entry.candidate_role or entry.relationship_type)
        evidence = _evidence_line(core)
        market = _market_line_for_core(core, entry)
        why = _truncate_text(
            core.get("why_opportunity_visible")
            or core.get("final_verdict_reason")
            or decision.reason
            or "quality-gated research lead",
            140,
        )
        verify = _truncate_text(_verification_line(core, entry), 130)
        displayed += 1
        lines.extend(
            [
                "",
                f"<b>{displayed}. {_esc(symbol)} / {_esc(coin_id)}</b>",
                f"Catalyst: {_esc(catalyst)}",
                f"Level: {_esc(level)} · Route: {_esc(route)}",
                f"Opportunity: {_esc(lane)} · Market: {_esc(market_state)}",
                f"Impact: {_esc(impact)} · Role: {_esc(role)}",
                f"Why surfaced: {_esc(why)}",
                f"Evidence: {_esc(evidence)}",
                f"Market: {_esc(market)}",
                f"Check next: {_esc(verify)}",
            ]
        )
        if str(core.get("opportunity_type") or "").upper() == "FADE_SHORT_REVIEW":
            lines.extend([
                "Fade review: move already happened; crowding/exhaustion evidence is present.",
                "Risk: review invalidation and liquidity manually. Research-only. Not a trade signal.",
            ])
        card = core.get("card_path") or core.get("research_card_path") or _first_card_path(card_paths, (core_id, decision.alert_id))
        if card:
            lines.append(f"Card: {_esc(Path(str(card)).name)}")
        if core_id:
            lines.append(f"Feedback target: {_esc(core_id)}")
    lines.append("")
    if total_items > len(keep):
        lines.append(f"+{total_items - len(keep)} more in local brief.")
    lines.append("Research cards and feedback commands are available in local artifacts/inbox.")
    return "\n".join(lines)

def _evidence_line(core: Mapping[str, Any]) -> str:
    accepted = _accepted_evidence_count(core)
    status = str(core.get("evidence_acquisition_status") or "unknown").strip()
    confirm = str(core.get("acquisition_confirmation_status") or "").strip()
    pack = str(core.get("source_pack") or "source pack unknown").strip()
    if accepted > 0:
        return f"{accepted} accepted evidence item(s) from {pack}"
    if status == "rejected_results_only" or confirm == "does_not_confirm":
        return f"not confirmed; acquisition found rejected-only evidence via {pack}"
    if status in {"no_results", "skipped_budget", "provider_unavailable", "skipped_config"}:
        return f"not confirmed; acquisition status {status} via {pack}"
    return f"{status or 'unknown'} via {pack}"

def _market_line_for_core(core: Mapping[str, Any], entry: Any) -> str:
    level = str(core.get("market_confirmation_level") or getattr(entry, "market_confirmation_level", None) or "unknown")
    freshness = str(core.get("market_context_freshness_status") or getattr(entry, "market_context_freshness_status", None) or "unknown")
    score = core.get("market_confirmation_score")
    if score is None:
        score = getattr(entry, "market_confirmation_score", None)
    if score is not None:
        return f"{_human_reason(level)}; freshness {_human_reason(freshness)}; score {_fmt_num(score)}"
    return f"{_human_reason(level)}; freshness {_human_reason(freshness)}"

def _verification_line(core: Mapping[str, Any], entry: Any) -> str:
    items = _as_list(core.get("upgrade_requirements")) or _as_list(core.get("manual_verification_items"))
    if not items:
        items = list(getattr(entry, "upgrade_requirements", ()) or getattr(entry, "manual_verification_items", ()) or ())
    if not items:
        return "review the local card and source evidence before acting"
    return "; ".join(str(item).replace("_", " ") for item in items[:2])

def _provider_degradation_summary(result: Any | None) -> str:
    warnings = [str(item) for item in getattr(result, "warnings", ()) or () if str(item)]
    if not warnings:
        return ""
    provider_warnings = [item for item in warnings if any(token in item.lower() for token in ("provider", "gdelt", "rss", "cryptopanic", "timeout", "429", "403"))]
    selected = provider_warnings[:3] or warnings[:2]
    return "; ".join(_truncate_text(item, 80) for item in selected)

def _first_card_path(card_paths: Mapping[str, object], keys: Iterable[str]) -> str | None:
    for key in keys:
        if not key:
            continue
        path = card_paths.get(str(key))
        if path:
            return str(path)
    return None

def _joined_unique(values: Iterable[Any]) -> str | None:
    clean = tuple(dict.fromkeys(str(item).strip() for item in values if str(item or "").strip()))
    return ",".join(clean) if clean else None

def _human_route(value: object) -> str:
    raw = str(getattr(value, "value", value) or "").strip()
    mapping = {
        "RESEARCH_DIGEST": "research digest",
        "HIGH_PRIORITY_RESEARCH": "high-priority research",
        "TRIGGERED_FADE_RESEARCH": "triggered fade research",
        "STORE_ONLY": "stored locally",
        "LOCAL_REPORT": "local report",
    }
    return mapping.get(raw, _human_reason(raw))

def _fmt_num(value: Any) -> str:
    number = _float_or_none(value)
    if number is None:
        return "n/a"
    return f"{number:.1f}".rstrip("0").rstrip(".")

def _truncate_text(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "..."

def _route_label(items: Iterable[event_alpha_router.EventAlphaRouteDecision]) -> str:
    for decision in items:
        route = getattr(decision, "route", None)
        if route is not None:
            return getattr(route, "value", str(route))
    return ""

def _suppression_reason(decision: event_alpha_router.EventAlphaRouteDecision) -> str:
    entry = decision.entry
    return str(
        entry.suppressed_reason
        or decision.reason
        or ("; ".join(entry.warnings) if entry.warnings else "")
    ).strip()

def _is_exploratory_control(entry: Any) -> bool:
    fields = " ".join(
        str(value or "").casefold()
        for value in (
            entry.latest_playbook_type,
            entry.latest_effective_playbook_type,
            entry.relationship_type,
            entry.latest_llm_asset_role,
            entry.latest_event_name,
        )
    )
    return any(token in fields for token in ("source_noise", "ticker_word_collision", "word_collision"))

def _is_ambiguous_exploratory(entry: Any) -> bool:
    fields = " ".join(
        str(value or "").casefold()
        for value in (
            entry.latest_playbook_type,
            entry.latest_effective_playbook_type,
            entry.relationship_type,
            entry.latest_llm_asset_role,
        )
    )
    return "ambiguous" in fields

def _ambiguous_has_learning_value(entry: Any) -> bool:
    components = dict(getattr(entry, "latest_score_components", {}) or {})
    return bool(
        entry.external_asset
        or entry.event_time
        or _component_score(components, "market_move_volume") >= 25
        or _component_score(components, "source_quality") >= 40
        or _component_score(components, "cluster_confidence") >= 40
        or int(getattr(entry, "source_count", 0) or 0) > 1
    )

def _exploratory_rank(entry: Any) -> tuple[float, list[str]]:
    components = dict(getattr(entry, "latest_score_components", {}) or {})
    market = _component_score(components, "market_move_volume")
    source_quality = _component_score(components, "source_quality")
    extraction = max(
        _component_score(components, "llm_extraction_confidence"),
        _component_score(components, "extraction_confidence"),
        float(getattr(entry, "latest_llm_confidence", 0.0) or 0.0) * 100.0,
    )
    cluster = _component_score(components, "cluster_confidence")
    freshness = _component_score(components, "novelty_freshness")
    catalyst = 20.0 if (entry.external_asset or entry.event_time) else _component_score(components, "catalyst_presence")
    hypothesis = _component_score(components, "hypothesis_confidence")
    rank = (
        float(getattr(entry, "latest_score", 0) or 0)
        + 0.45 * market
        + 0.30 * source_quality
        + 0.25 * extraction
        + 0.20 * cluster
        + 0.15 * freshness
        + catalyst
        + 0.30 * hypothesis
    )
    reasons: list[str] = []
    if str(getattr(entry, "state", "") or "") == "HYPOTHESIS":
        reasons.append("impact hypothesis awaiting validation")
    if market >= 25:
        reasons.append(f"market anomaly score {market:g}")
    if source_quality >= 40:
        reasons.append(f"source quality {source_quality:g}")
    if extraction >= 50:
        reasons.append(f"LLM/extraction confidence {extraction:g}")
    if catalyst:
        reasons.append("has catalyst/external-asset evidence")
    if hypothesis >= 40:
        reasons.append(f"hypothesis confidence {hypothesis:g}")
    if cluster >= 40:
        reasons.append(f"cluster confidence {cluster:g}")
    if freshness >= 40:
        reasons.append(f"freshness {freshness:g}")
    if not reasons:
        reasons.append("suppressed row retained for burn-in review")
    return rank, reasons

def _exploratory_verify_steps(entry: Any, reason: str) -> list[str]:
    playbook = str(entry.latest_playbook_type or entry.latest_effective_playbook_type or "").casefold()
    steps = []
    if str(getattr(entry, "state", "") or "") == "HYPOTHESIS":
        steps.append("validate candidate asset link to catalyst")
        steps.append("run targeted source search for candidate/catalyst")
    elif "market_anomaly" in playbook:
        steps.append("find independent catalyst/source evidence for the move")
        steps.append("check whether the move is liquidity noise or organic volume")
    elif "direct" in playbook or "listing" in playbook or "unlock" in playbook:
        steps.append("verify the direct event mechanics and timing")
        steps.append("check whether this belongs outside proxy-fade research")
    elif entry.external_asset:
        steps.append("confirm the crypto asset is actually linked to the external catalyst")
        steps.append("verify the catalyst timestamp and source provenance")
    else:
        steps.append("verify asset identity from source title/body, not publisher or URL noise")
        steps.append("look for a dated catalyst before escalating")
    if "duplicate" in str(reason).casefold():
        steps.append("check whether this is a repeated row rather than a new escalation")
    return steps

def _component_score(components: Mapping[str, Any], key: str) -> float:
    try:
        return float(components.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0

def _compact_market(snapshot: Mapping[str, Any] | None) -> str:
    data = dict(snapshot or {})
    if not data:
        return "missing"
    fields = []
    for key in ("price", "return_24h", "return_72h", "volume_zscore_24h", "volume_mcap"):
        if key in data and data.get(key) not in (None, ""):
            value = data.get(key)
            if isinstance(value, float):
                fields.append(f"{key}={value:.4g}")
            else:
                fields.append(f"{key}={value}")
    return " ".join(fields) if fields else "present"

def _human_asset_name(coin_id: object) -> str:
    text = str(coin_id or "unknown").strip()
    if not text:
        return "Unknown"
    return " ".join(part.capitalize() for part in re.split(r"[-_\s]+", text) if part) or text

def _human_playbook(value: object) -> str:
    text = str(value or "unknown").strip()
    mapping = {
        "market_anomaly_unknown": "market anomaly / unknown catalyst",
        "market_anomaly": "market anomaly",
        "proxy_fade": "proxy fade",
        "proxy_attention": "proxy attention",
        "direct_event": "direct event",
        "infrastructure_mention": "infrastructure mention",
        "source_noise_control": "source/noise control",
        "ambiguous_control": "relationship unclear",
        "ambiguous": "relationship unclear",
        "impact_hypothesis": "impact hypothesis",
        "rwa_preipo_proxy": "RWA/pre-IPO proxy",
        "ai_ipo_proxy": "AI IPO proxy",
        "sports_fan_proxy": "sports/fan-token proxy",
        "stablecoin_regulatory": "stablecoin regulatory",
    }
    return mapping.get(text, text.replace("_", " "))

def _human_state(value: object) -> str:
    text = str(value or "").strip()
    mapping = {
        "RAW_EVIDENCE": "raw evidence only",
        "HYPOTHESIS": "impact hypothesis awaiting validation",
        "STORE_ONLY": "stored for research only",
        "RADAR": "radar",
        "WATCHLIST": "watchlist",
        "HIGH_PRIORITY": "high priority",
        "EVENT_PASSED": "event passed",
        "ARMED": "armed",
        "TRIGGERED_FADE": "triggered fade",
        "INVALIDATED": "invalidated",
        "EXPIRED": "expired",
    }
    return mapping.get(text, text.replace("_", " ").lower() if text else "stored for research only")

def _human_reason(value: object) -> str:
    text = str(value or "").strip()
    normalized = text.casefold()
    mapping = {
        "raw/store-only evidence, no alertable watchlist state": "not alertable yet",
        "raw, expired, or invalidated watchlist state is stored only.": "not alertable yet",
        "event alpha router is disabled; retaining watchlist row as research evidence only.": "router disabled",
        "impact hypothesis awaiting asset validation": "not alertable yet",
        "impact hypothesis awaiting validation": "not alertable yet",
    }
    if normalized in mapping:
        return mapping[normalized]
    if "duplicate" in normalized:
        return "duplicate or repeated evidence"
    if "cooldown" in normalized:
        return "cooldown active"
    if "alertable" in normalized:
        return "not alertable yet"
    return text.replace("_", " ") if text else "not alertable yet"

def _human_level(value: object) -> str:
    text = str(value or "").strip()
    mapping = {
        "local_only": "local-only research",
        "exploratory": "exploratory research",
        "validated_digest": "validated digest",
        "watchlist": "watchlist",
        "high_priority": "high priority",
    }
    return mapping.get(text, text.replace("_", " ") if text else "research review")

def _candidate_catalyst_text(entry: Any) -> str:
    for value in (
        getattr(entry, "latest_event_name", None),
        getattr(entry, "external_asset", None),
        getattr(entry, "event_id", None),
    ):
        text = str(value or "").strip()
        if text:
            return _truncate_text(text.replace("|", " / "), 96)
    return "catalyst not confirmed"

def _human_why_not_alertable(reasons: Iterable[str]) -> str:
    output: list[str] = []
    for reason in reasons:
        text = _human_reason(reason)
        lower = text.casefold()
        if "confirmation" in lower and "missing" in lower:
            output.append("missing confirmation")
        elif "rejected results only" in lower:
            output.append("evidence search rejected the link")
        elif "skipped budget" in lower:
            output.append("evidence search unresolved")
        elif "local only" in lower:
            output.append("quality gate kept it local-only")
        elif "watchlist" in lower and "not" in lower:
            output.append("watchlist requirements not met")
        elif text:
            output.append(text)
    if not output:
        output.append("missing confirmation")
    return "; ".join(dict.fromkeys(output[:3]))

def _telegram_card_basename(
    decision: event_alpha_router.EventAlphaRouteDecision,
    card_path_by_alert_id: Mapping[str, str | Path] | None,
    *,
    core: Mapping[str, Any] | None = None,
) -> str:
    core = core or {}
    for value in (
        core.get("card_path"),
        core.get("research_card_path"),
        core.get("canonical_card_path"),
    ):
        text = str(value or "").strip()
        if text:
            return event_artifact_paths.artifact_display_path(text)
    card_paths = {str(key): value for key, value in (card_path_by_alert_id or {}).items()}
    for key in _decision_identity_keys(decision):
        path = card_paths.get(key)
        if path:
            return event_artifact_paths.artifact_display_path(path)
    return "local artifacts"

def _telegram_feedback_target(
    decision: event_alpha_router.EventAlphaRouteDecision,
    *,
    core: Mapping[str, Any] | None = None,
) -> str:
    core = core or {}
    for value in (
        core.get("feedback_target"),
        core.get("core_opportunity_id"),
        core.get("canonical_core_opportunity_id"),
    ):
        text = str(value or "").strip()
        if text:
            return text
    components = dict(getattr(decision.entry, "latest_score_components", {}) or {})
    for value in (
        components.get("core_opportunity_id"),
        components.get("canonical_core_opportunity_id"),
        getattr(decision.entry, "hypothesis_id", None),
        decision.alert_id,
    ):
        text = str(value or "").strip()
        if text:
            return text
    return "local inbox"

def _human_status(state: object, tier: object, reason: object) -> str:
    state_text = _human_state(state or tier)
    reason_text = _human_reason(reason)
    if reason_text and reason_text != state_text:
        return f"{state_text} — {reason_text}"
    return state_text

def _move_summary(snapshot: Mapping[str, Any] | None) -> str:
    data = dict(snapshot or {})
    parts = []
    for key, label in (("return_24h", "24h"), ("return_72h", "72h"), ("return_7d", "7d")):
        value = _float_or_none(data.get(key))
        if value is not None:
            parts.append(f"{_format_pct_return(value)} {label}")
    return ", ".join(parts) if parts else "n/a"

def _volume_mcap_summary(snapshot: Mapping[str, Any] | None) -> str:
    data = dict(snapshot or {})
    value = _float_or_none(data.get("volume_mcap"))
    if value is None:
        volume = _float_or_none(data.get("volume_24h") or data.get("spot_volume_24h"))
        market_cap = _float_or_none(data.get("market_cap"))
        if volume is not None and market_cap and market_cap > 0:
            value = volume / market_cap
    if value is None:
        return "n/a"
    return f"{value:.2f}"

def _format_pct_return(value: float) -> str:
    percent = value if abs(value) > 10 else value * 100.0
    sign = "+" if percent > 0 else ""
    return f"{sign}{percent:.1f}%"

def _float_or_none(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None

def _human_why(reasons: Iterable[str]) -> str:
    output: list[str] = []
    for reason in reasons:
        text = str(reason or "").strip()
        lower = text.casefold()
        if lower.startswith("market anomaly score"):
            output.append("unusual market move")
        elif "impact hypothesis" in lower:
            output.append("impact hypothesis")
        elif lower.startswith("hypothesis confidence"):
            output.append(text)
        elif lower.startswith("source quality"):
            output.append(text)
        elif lower.startswith("freshness"):
            output.append("fresh anomaly")
        elif lower.startswith("cluster confidence"):
            output.append(text)
        elif "catalyst" in lower or "external-asset" in lower:
            output.append("possible catalyst clue")
        elif "extraction confidence" in lower or "llm" in lower:
            output.append(text.replace("LLM/extraction", "extraction"))
        elif text:
            output.append(text.replace("_", " "))
    if not output:
        output.append("suppressed row retained for review")
    return "; ".join(dict.fromkeys(output[:4]))

def _human_check_next(steps: Iterable[str]) -> str:
    output: list[str] = []
    for step in steps:
        text = str(step or "").strip()
        lower = text.casefold()
        if "independent catalyst" in lower:
            output.append("find independent catalyst")
        elif "candidate asset link" in lower:
            output.append("validate asset-catalyst link")
        elif "targeted source search" in lower:
            output.append("run targeted source search")
        elif "liquidity noise" in lower or "organic volume" in lower:
            output.append("verify liquidity/organic volume")
        elif "direct event mechanics" in lower:
            output.append("verify event mechanics/timing")
        elif "proxy-fade" in lower:
            output.append("confirm outside proxy-fade path")
        elif "asset is actually linked" in lower:
            output.append("verify asset-catalyst link")
        elif "timestamp" in lower or "provenance" in lower:
            output.append("verify event time/source")
        elif "asset identity" in lower:
            output.append("verify asset identity")
        elif "dated catalyst" in lower:
            output.append("look for dated catalyst")
        elif text:
            output.append(text)
    if not output:
        output.append("review source evidence")
    return "; ".join(dict.fromkeys(output[:3]))

def _human_risk(entry: Any, decision: event_alpha_router.EventAlphaRouteDecision) -> str:
    risks: list[str] = []
    playbook = str(entry.latest_playbook_type or entry.latest_effective_playbook_type or "").casefold()
    relationship = str(entry.relationship_type or "").casefold()
    components = dict(getattr(entry, "latest_score_components", {}) or {})
    classifier = _component_score(components, "classifier")
    if "market_anomaly" in playbook:
        risks.append("no confirmed narrative")
    if str(getattr(entry, "state", "") or "") == "HYPOTHESIS":
        risks.append("asset impact not validated")
    if "ambiguous" in relationship or "ambiguous" in playbook:
        risks.append("relationship unclear")
    if classifier and classifier < 60:
        risks.append("low classifier confidence")
    if not getattr(entry, "event_time", None):
        risks.append("no dated catalyst")
    if int(getattr(entry, "source_count", 0) or 0) <= 1:
        risks.append("single-source evidence")
    warnings = tuple(dict.fromkeys((*getattr(entry, "warnings", ()), *getattr(decision, "warnings", ()))))
    if warnings and len(risks) < 3:
        risks.append(str(warnings[0]).replace("_", " "))
    return "; ".join(dict.fromkeys(risks[:3])) if risks else "needs manual confirmation"

__all__ = (
    'format_exploratory_telegram_digest',
    'format_core_opportunity_telegram_digest',
    '_evidence_line',
    '_market_line_for_core',
    '_verification_line',
    '_provider_degradation_summary',
    '_first_card_path',
    '_joined_unique',
    '_human_route',
    '_fmt_num',
    '_truncate_text',
    '_route_label',
    '_suppression_reason',
    '_is_exploratory_control',
    '_is_ambiguous_exploratory',
    '_ambiguous_has_learning_value',
    '_exploratory_rank',
    '_exploratory_verify_steps',
    '_component_score',
    '_compact_market',
    '_human_asset_name',
    '_human_playbook',
    '_human_state',
    '_human_reason',
    '_human_level',
    '_candidate_catalyst_text',
    '_human_why_not_alertable',
    '_telegram_card_basename',
    '_telegram_feedback_target',
    '_human_status',
    '_move_summary',
    '_volume_mcap_summary',
    '_format_pct_return',
    '_float_or_none',
    '_human_why',
    '_human_check_next',
    '_human_risk',
)
