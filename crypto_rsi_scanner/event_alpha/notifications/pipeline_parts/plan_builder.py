"""Plan Builder for the legacy notification pipeline."""

from __future__ import annotations

from .runtime import *

def build_notification_plan(
    decisions: Iterable[event_alpha_router.EventAlphaRouteDecision],
    *,
    storage: Any,
    cfg: EventAlphaNotificationConfig,
    now: datetime | None = None,
    include_health_heartbeat: bool = False,
    core_opportunity_rows: Iterable[Mapping[str, Any] | object] = (),
) -> EventAlphaNotificationPlan:
    """Return lane-specific due decisions without mutating storage."""
    observed = _as_utc(now or datetime.now(timezone.utc))
    raw_decisions = list(decisions)
    core_index = _core_index_for_decisions(raw_decisions, core_opportunity_rows)
    all_decisions, canonical_warnings = _canonicalize_decisions_for_notification(raw_decisions, core_index)
    quality_mode = _quality_mode(cfg.quality_mode)
    alertable = _filter_alertable_by_quality_mode(
        [decision for decision in all_decisions if event_alpha_router.alertable_after_quality_gate(decision)],
        quality_mode,
    )
    by_lane: dict[str, list[event_alpha_router.EventAlphaRouteDecision]] = {lane: [] for lane in LANES}
    blocked: dict[str, str] = {}

    daily_candidates = [decision for decision in alertable if _lane_for_decision(decision) == LANE_DAILY_DIGEST]
    daily_unconfirmed: list[event_alpha_router.EventAlphaRouteDecision] = []
    daily = _confirmed_daily_digest_decisions(
        daily_candidates,
        core_row_by_alert_id=core_index,
        cfg=cfg,
        unconfirmed=daily_unconfirmed,
    )
    daily = _dedupe_daily_digest_decisions(
        daily,
        core_row_by_alert_id=core_index,
        max_items=cfg.daily_digest_max_items,
    )
    if daily:
        due, reason = lane_due(storage, LANE_DAILY_DIGEST, cfg=cfg, now=observed)
        if due:
            by_lane[LANE_DAILY_DIGEST] = daily
        else:
            blocked[LANE_DAILY_DIGEST] = reason
    if daily_unconfirmed:
        blocked[LANE_DAILY_DIGEST] = (
            f"{len(daily_unconfirmed)} candidate(s) excluded from daily_digest: live confirmation missing"
        )

    instant = [decision for decision in alertable if _lane_for_decision(decision) == LANE_INSTANT_ESCALATION]
    if instant:
        due, reason = lane_due(storage, LANE_INSTANT_ESCALATION, cfg=cfg, now=observed)
        if due:
            remaining = max(
                0,
                cfg.max_instant_per_day - _sent_count_today(storage, LANE_INSTANT_ESCALATION, observed, cfg),
            )
            by_lane[LANE_INSTANT_ESCALATION] = instant[:remaining]
            if len(instant) > remaining:
                blocked[LANE_INSTANT_ESCALATION] = f"daily instant cap reached after {remaining} item(s)"
        else:
            blocked[LANE_INSTANT_ESCALATION] = reason

    triggered = [decision for decision in alertable if _lane_for_decision(decision) == LANE_TRIGGERED_FADE]
    if triggered:
        due_triggered: list[event_alpha_router.EventAlphaRouteDecision] = []
        blocked_count = 0
        for decision in triggered:
            due, reason = lane_due(
                storage,
                LANE_TRIGGERED_FADE,
                cfg=cfg,
                now=observed,
                alert_id=decision.alert_id,
            )
            if due:
                due_triggered.append(decision)
            else:
                blocked_count += 1
                blocked[LANE_TRIGGERED_FADE] = reason
        by_lane[LANE_TRIGGERED_FADE] = due_triggered
        if blocked_count and LANE_TRIGGERED_FADE not in blocked:
            blocked[LANE_TRIGGERED_FADE] = f"{blocked_count} triggered fade item(s) already sent"

    exploratory_items: tuple[EventAlphaExploratoryDigestItem, ...] = ()
    research_review_items: tuple[EventAlphaResearchReviewDigestItem, ...] = ()
    strict_due_count = sum(
        len(by_lane.get(lane, ()))
        for lane in (LANE_TRIGGERED_FADE, LANE_INSTANT_ESCALATION, LANE_DAILY_DIGEST)
    )
    strict_core_ids = _strict_lane_core_ids(by_lane, core_index)
    if cfg.research_review_digest_enabled:
        selected, eligible_count, skipped_items = select_research_review_candidates_with_diagnostics(
            all_decisions,
            cfg=cfg,
            now=observed,
            excluded_core_ids=strict_core_ids,
            core_row_by_alert_id=core_index,
        )
        selected = _with_unconfirmed_daily_review_items(
            selected,
            daily_unconfirmed,
            cfg=cfg,
            excluded_core_ids=strict_core_ids,
            core_row_by_alert_id=core_index,
        )
        if selected:
            if strict_due_count and not cfg.research_review_digest_send_with_alerts:
                blocked[LANE_RESEARCH_REVIEW_DIGEST] = "strict alert lane has due candidates"
            else:
                due, reason = lane_due(storage, LANE_RESEARCH_REVIEW_DIGEST, cfg=cfg, now=observed)
                if due:
                    research_review_items = selected
                else:
                    blocked[LANE_RESEARCH_REVIEW_DIGEST] = reason
    else:
        eligible_count = 0
        skipped_items = ()

    if cfg.exploratory_digest_enabled and quality_mode == "exploratory_only":
        selected = select_exploratory_candidates(all_decisions, cfg=cfg, now=observed)
        if selected:
            due, reason = lane_due(storage, LANE_EXPLORATORY_DIGEST, cfg=cfg, now=observed)
            if due:
                exploratory_items = selected
            else:
                blocked[LANE_EXPLORATORY_DIGEST] = reason

    heartbeat_due = False
    heartbeat_reason = "heartbeat disabled"
    if include_health_heartbeat and cfg.health_heartbeat_enabled:
        heartbeat_due, heartbeat_reason = lane_due(storage, LANE_HEALTH_HEARTBEAT, cfg=cfg, now=observed)
    elif include_health_heartbeat:
        heartbeat_reason = "health heartbeat disabled"

    by_lane = {lane: items for lane, items in by_lane.items() if items}
    return EventAlphaNotificationPlan(
        all_decisions=tuple(all_decisions),
        decisions_by_lane=by_lane,
        blocked_by_lane=blocked,
        heartbeat_due=heartbeat_due,
        heartbeat_reason=heartbeat_reason,
        exploratory_items=exploratory_items,
        research_review_items=research_review_items,
        research_review_eligible_count=eligible_count,
        research_review_skipped_items=skipped_items,
        cooldown_status=cooldown_status_by_lane(storage, cfg=cfg, now=observed),
        notification_scope=_clean_scope(cfg.notification_scope),
        scope_value=_scope_value(cfg),
        migration_warnings=legacy_meta_warnings(storage, cfg),
        core_row_by_alert_id=core_index,
        canonicalization_warnings=canonical_warnings,
    )

def _confirmed_daily_digest_decisions(
    decisions: Iterable[event_alpha_router.EventAlphaRouteDecision],
    *,
    core_row_by_alert_id: Mapping[str, Mapping[str, Any]],
    cfg: EventAlphaNotificationConfig,
    unconfirmed: list[event_alpha_router.EventAlphaRouteDecision],
) -> list[event_alpha_router.EventAlphaRouteDecision]:
    confirmed: list[event_alpha_router.EventAlphaRouteDecision] = []
    live_strict = _daily_digest_requires_live_confirmation(cfg)
    for decision in decisions:
        core = _core_row_for_decision(decision, core_row_by_alert_id) or {}
        if not live_strict or _daily_digest_has_confirmation(decision, core, cfg=cfg):
            confirmed.append(decision)
        else:
            unconfirmed.append(decision)
    return confirmed

def _daily_digest_requires_live_confirmation(cfg: EventAlphaNotificationConfig) -> bool:
    scope = " ".join(
        str(value or "").casefold()
        for value in (cfg.profile_name, cfg.artifact_namespace, cfg.notification_scope)
    )
    if any(token in scope for token in ("fixture", "smoke", "e2e", "test")):
        return False
    if not str(cfg.artifact_namespace or "").strip() and "deep" not in scope and "rehearsal" not in scope:
        return False
    return any(token in scope for token in ("notify_llm_deep", "cryptopanic", "live", "burn_in", "rehearsal", "send"))

def _daily_digest_has_confirmation(
    decision: event_alpha_router.EventAlphaRouteDecision,
    core: Mapping[str, Any],
    *,
    cfg: EventAlphaNotificationConfig | None = None,
) -> bool:
    cfg = cfg or EventAlphaNotificationConfig()
    entry = _decision_entry(decision)
    components = dict(getattr(entry, "latest_score_components", {}) or {})
    merged: dict[str, Any] = {**components, **dict(core)}
    symbol = str(merged.get("symbol") or merged.get("validated_symbol") or getattr(entry, "symbol", "") or "").strip().upper()
    coin_id = str(merged.get("coin_id") or merged.get("validated_coin_id") or getattr(entry, "coin_id", "") or "").strip()
    if _research_review_is_sector(symbol, coin_id):
        return False
    accepted = _accepted_evidence_count(merged)
    acquisition_status = str(merged.get("evidence_acquisition_status") or "").strip()
    acquisition_confirmation = str(merged.get("acquisition_confirmation_status") or "").strip()
    source_class = str(merged.get("source_class") or merged.get("source_origin_class") or "").casefold()
    reason_values = (
        *_iter_values(merged.get("accepted_reason_codes") or merged.get("reason_codes")),
        *_iter_values(merged.get("accepted_reason_code_counts")),
    )
    reason_codes = " ".join(str(item) for item in reason_values)
    source_pack = str(merged.get("source_pack") or "").casefold()
    market_confirmation = str(
        merged.get("market_confirmation_level")
        or merged.get("market_confirmation")
        or merged.get("market_reaction_confirmation")
        or ""
    ).casefold()
    market_freshness = str(
        merged.get("market_context_freshness_status")
        or merged.get("core_market_freshness_status")
        or merged.get("market_freshness_status")
        or ""
    ).casefold()
    impact = str(merged.get("impact_path_type") or merged.get("effective_playbook_type") or "").casefold()
    official_or_structured = source_class in {
        "official_project",
        "official_exchange",
        "structured_calendar",
        "structured_unlock",
        "exchange_announcement",
    }
    provider_counts = _mapping_counts(merged.get("accepted_provider_counts"))
    cryptopanic_accepted = provider_counts.get("cryptopanic", 0)
    cryptopanic_tagged = "cryptopanic_currency_tag_match" in reason_codes.casefold()
    fresh_market = _has_digest_market_confirmation(merged)
    narrative_source_pack = source_pack in {
        "fan_sports_pack",
        "proxy_preipo_rwa_pack",
        "political_meme_pack",
    }
    if narrative_source_pack:
        if bool(getattr(cfg, "allow_source_only_narrative_digest", False)):
            return (accepted > 0 and acquisition_status == "accepted_evidence_found") or acquisition_confirmation == "confirms"
        if official_or_structured:
            return True
        if accepted >= 2:
            return True
        if cryptopanic_tagged and cryptopanic_accepted > 0 and fresh_market:
            return True
        return False
    if accepted > 0 and acquisition_status == "accepted_evidence_found":
        return True
    if acquisition_confirmation == "confirms":
        return True
    if official_or_structured:
        return True
    if "cryptopanic_currency_tag_match" in reason_codes.casefold() and source_class in {"cryptopanic_tagged", "crypto_news"}:
        return True
    if source_pack in {"listing_liquidity_pack", "perp_listing_squeeze_pack", "unlock_supply_pack"} and source_class.startswith("official"):
        return True
    fresh_market = market_confirmation not in {"", "none", "missing", "unknown", "insufficient_data"}
    fresh_context = market_freshness not in {"", "missing", "stale", "unknown"}
    generic = impact in {"", "insufficient_data", "generic_cooccurrence", "source_noise_control", "ambiguous_control"}
    return fresh_market and fresh_context and not generic

def _has_digest_market_confirmation(row: Mapping[str, Any]) -> bool:
    market = str(
        row.get("market_confirmation_level")
        or row.get("market_confirmation")
        or row.get("market_reaction_confirmation")
        or ""
    ).casefold()
    freshness = str(
        row.get("market_context_freshness_status")
        or row.get("core_market_freshness_status")
        or row.get("market_freshness_status")
        or ""
    ).casefold()
    if market in {"moderate", "strong", "confirmed", "fresh"} and freshness not in {"missing", "stale", "unknown"}:
        return True
    score = _float_or_none(row.get("market_confirmation_score") or row.get("market_move_volume") or row.get("market_score"))
    return score is not None and score >= 40 and freshness not in {"missing", "stale", "unknown"}

def _mapping_counts(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    out: dict[str, int] = {}
    for key, raw in value.items():
        try:
            count = int(raw or 0)
        except (TypeError, ValueError):
            continue
        out[str(key).strip().casefold()] = max(0, count)
    return out

def _dedupe_daily_digest_decisions(
    decisions: Iterable[event_alpha_router.EventAlphaRouteDecision],
    *,
    core_row_by_alert_id: Mapping[str, Mapping[str, Any]],
    max_items: int,
) -> list[event_alpha_router.EventAlphaRouteDecision]:
    grouped: list[event_alpha_router.EventAlphaRouteDecision] = []
    seen: set[tuple[str, str, str]] = set()
    for decision in decisions:
        core = _core_row_for_decision(decision, core_row_by_alert_id) or {}
        key = _daily_digest_group_key(decision, core)
        if key in seen:
            continue
        seen.add(key)
        grouped.append(decision)
    limit = max(0, int(max_items or 0))
    return grouped[:limit] if limit else []

def _strict_lane_core_ids(
    by_lane: Mapping[str, Iterable[event_alpha_router.EventAlphaRouteDecision]],
    core_row_by_alert_id: Mapping[str, Mapping[str, Any]],
) -> set[str]:
    out: set[str] = set()
    for lane in (LANE_TRIGGERED_FADE, LANE_INSTANT_ESCALATION, LANE_DAILY_DIGEST):
        for decision in by_lane.get(lane, ()):
            core_id = _core_id_for_decision(decision, core_row_by_alert_id)
            if core_id:
                out.add(core_id)
    return out

def _core_id_for_decision(
    decision: event_alpha_router.EventAlphaRouteDecision,
    core_row_by_alert_id: Mapping[str, Mapping[str, Any]],
) -> str:
    core = _core_row_for_decision(decision, core_row_by_alert_id) or {}
    entry = _decision_entry(decision)
    components = getattr(entry, "latest_score_components", None) or {}
    return str(
        core.get("core_opportunity_id")
        or getattr(entry, "core_opportunity_id", None)
        or (components.get("core_opportunity_id") if isinstance(components, Mapping) else None)
        or (components.get("canonical_core_opportunity_id") if isinstance(components, Mapping) else None)
        or ""
    ).strip()

def _core_row_is_research_alertable(core: Mapping[str, Any]) -> bool:
    if not core:
        return False
    route = str(core.get("final_route_after_quality_gate") or core.get("route") or "").strip()
    if event_alpha_router.route_value_is_alertable(route):
        return True
    level = str(core.get("final_opportunity_level") or core.get("opportunity_level") or "").strip()
    return level in {"validated_digest", "watchlist", "high_priority"}

def _daily_digest_group_key(
    decision: event_alpha_router.EventAlphaRouteDecision,
    core: Mapping[str, Any],
) -> tuple[str, str, str]:
    entry = _decision_entry(decision)
    coin_id = str(core.get("coin_id") or core.get("validated_coin_id") or getattr(entry, "coin_id", "") or "").strip().casefold()
    if not coin_id:
        coin_id = str(core.get("symbol") or core.get("validated_symbol") or getattr(entry, "symbol", "") or "").strip().casefold()
    incident = str(
        core.get("incident_id")
        or core.get("canonical_incident_name")
        or core.get("event_family")
        or getattr(entry, "latest_event_name", "")
        or ""
    ).strip().casefold()
    impact = str(core.get("impact_path_type") or getattr(entry, "impact_path_type", "") or getattr(entry, "latest_effective_playbook_type", "") or "").strip().casefold()
    return (coin_id, incident, _impact_family(impact))

def _decision_entry(decision: object) -> object:
    return getattr(decision, "entry", decision)

def _impact_family(value: str) -> str:
    text = str(value or "").casefold()
    if "fan" in text or "sports" in text:
        return "fan_sports"
    if "proxy" in text or "rwa" in text or "preipo" in text or "pre_ipo" in text:
        return "proxy"
    if "listing" in text or "perp" in text:
        return "listing"
    if "unlock" in text or "supply" in text:
        return "supply"
    if "security" in text or "exploit" in text:
        return "security"
    return text or "unknown"

def _with_unconfirmed_daily_review_items(
    selected: tuple[EventAlphaResearchReviewDigestItem, ...],
    unconfirmed: Iterable[event_alpha_router.EventAlphaRouteDecision],
    *,
    cfg: EventAlphaNotificationConfig,
    excluded_core_ids: Iterable[str] = (),
    core_row_by_alert_id: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[EventAlphaResearchReviewDigestItem, ...]:
    if not unconfirmed:
        return selected
    items = list(selected)
    core_index = core_row_by_alert_id or {}
    seen = {item.decision.alert_id for item in items}
    seen_core_ids = {
        core_id
        for item in items
        for core_id in (_core_id_for_decision(item.decision, core_index),)
        if core_id
    }
    excluded = {str(item).strip() for item in excluded_core_ids if str(item).strip()}
    for decision in unconfirmed:
        if decision.alert_id in seen:
            continue
        core_id = _core_id_for_decision(decision, core_index)
        core = _core_row_for_decision(decision, core_index) or {}
        if core_id and (core_id in excluded or core_id in seen_core_ids):
            continue
        entry = _decision_entry(decision)
        components = dict(getattr(entry, "latest_score_components", {}) or {})
        score = _research_review_score(decision)
        if score < float(cfg.research_review_digest_min_score or 0.0):
            continue
        items.append(EventAlphaResearchReviewDigestItem(
            decision=decision,
            rank_score=score,
            why_included=("would be daily digest except live confirmation is missing",),
            why_not_alertable=tuple(_research_review_not_alertable_reasons(decision, components)) or (
                "live_confirmation_missing",
            ),
            what_would_upgrade=("accepted source-pack evidence or fresh market confirmation",),
        ))
        seen.add(decision.alert_id)
        if core_id:
            seen_core_ids.add(core_id)
    items.sort(
        key=lambda item: (
            item.rank_score,
            _research_review_score(item.decision),
            getattr(_decision_entry(item.decision), "last_seen_at", ""),
            getattr(_decision_entry(item.decision), "symbol", ""),
        ),
        reverse=True,
    )
    return tuple(items[: max(0, int(cfg.research_review_digest_max_items or 0))])

def _iter_values(value: object) -> tuple[object, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)):
        return (value,)
    if isinstance(value, Mapping):
        return tuple(value.values())
    try:
        return tuple(value)  # type: ignore[arg-type]
    except TypeError:
        return (value,)

def select_exploratory_candidates(
    decisions: Iterable[event_alpha_router.EventAlphaRouteDecision],
    *,
    cfg: EventAlphaNotificationConfig,
    now: datetime | None = None,
) -> tuple[EventAlphaExploratoryDigestItem, ...]:
    """Pick low-confidence/suppressed rows for a separate operator-learning digest.

    This deliberately does not make the rows alertable. It only surfaces stored
    evidence for manual review during notification burn-in.
    """
    _ = now  # currently reserved for freshness/ranking extensions.
    if not cfg.exploratory_digest_enabled or cfg.exploratory_digest_max_items <= 0:
        return ()
    items: list[EventAlphaExploratoryDigestItem] = []
    for decision in decisions:
        if bool(getattr(decision, "alertable", False)) or event_alpha_router.alertable_after_quality_gate(decision):
            continue
        entry = decision.entry
        if _is_promoted_or_validated_exploratory(entry, decision):
            continue
        if (entry.symbol or entry.coin_id) == "":
            continue
        if not (entry.latest_source or entry.source_count):
            continue
        reason = _suppression_reason(decision)
        if not reason:
            continue
        if entry.latest_score < int(cfg.exploratory_digest_min_score or 0):
            continue
        if _is_exploratory_control(entry) and not cfg.exploratory_digest_include_controls:
            continue
        if _is_ambiguous_exploratory(entry) and not _ambiguous_has_learning_value(entry):
            continue
        rank, why = _exploratory_rank(entry)
        verify = _exploratory_verify_steps(entry, reason)
        items.append(EventAlphaExploratoryDigestItem(
            decision=decision,
            rank_score=rank,
            why_included=tuple(why),
            what_to_verify=tuple(verify),
        ))
    items.sort(
        key=lambda item: (
            item.rank_score,
            item.decision.entry.latest_score,
            item.decision.entry.last_seen_at,
            item.decision.entry.symbol,
        ),
        reverse=True,
    )
    return tuple(items[: max(0, int(cfg.exploratory_digest_max_items or 0))])

def _is_promoted_or_validated_exploratory(
    entry: event_watchlist.EventWatchlistEntry,
    decision: event_alpha_router.EventAlphaRouteDecision,
) -> bool:
    components = dict(entry.latest_score_components or {})
    level = str(components.get("opportunity_level") or getattr(decision, "opportunity_level", None) or "")
    route = event_alpha_router.final_route_value(decision)
    state = event_watchlist.final_state_value(entry)
    validation_stage = str(components.get("validation_stage") or "")
    if level in {"validated_digest", "watchlist", "high_priority"}:
        return True
    if route and event_alpha_router.route_value_is_alertable(route):
        return True
    if state in {
        event_watchlist.EventWatchlistState.WATCHLIST.value,
        event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        event_watchlist.EventWatchlistState.TRIGGERED_FADE.value,
    }:
        return True
    return validation_stage in {"impact_path_validated", "market_confirmed", "promoted_to_radar"} and level not in {
        "local_only",
        "exploratory",
        "",
    }

def _quality_mode(value: str | None) -> str:
    mode = str(value or "validated_digest").strip().lower()
    if mode in {"exploratory_only", "validated_digest", "high_quality_only"}:
        return mode
    return "validated_digest"

def _filter_alertable_by_quality_mode(
    decisions: list[event_alpha_router.EventAlphaRouteDecision],
    mode: str,
) -> list[event_alpha_router.EventAlphaRouteDecision]:
    """Apply notification-level quality gates without changing routing decisions."""
    if mode == "exploratory_only":
        return [
            decision for decision in decisions
            if _route_value(decision) in {"", event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH.value}
        ]
    if mode == "high_quality_only":
        return [
            decision for decision in decisions
            if _route_value(decision) in {
                "",
                event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
                event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH.value,
            }
        ]
    return [
        decision for decision in decisions
        if _route_value(decision) in {
            "",
            event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
            event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
            event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH.value,
        }
    ]

def _route_value(decision: object) -> str:
    return event_alpha_router.final_route_value(decision)

def _research_review_level(decision: event_alpha_router.EventAlphaRouteDecision) -> str:
    entry = decision.entry
    components = dict(getattr(entry, "latest_score_components", {}) or {})
    for key in ("final_opportunity_level", "opportunity_level", "opportunity_verdict"):
        value = str(components.get(key) or "").strip()
        if value:
            return value
    return str(
        getattr(decision, "opportunity_level", None)
        or getattr(entry, "opportunity_level", None)
        or ""
    ).strip()

def _research_review_score(decision: event_alpha_router.EventAlphaRouteDecision) -> float:
    entry = decision.entry
    components = dict(getattr(entry, "latest_score_components", {}) or {})
    for value in (
        getattr(decision, "opportunity_score_final", None),
        components.get("final_opportunity_score"),
        components.get("opportunity_score_final"),
        getattr(entry, "opportunity_score_final", None),
        getattr(entry, "latest_score", None),
    ):
        parsed = _float_or_none(value)
        if parsed is not None:
            return parsed
    return 0.0

def _research_review_is_sector(symbol: object, coin_id: object) -> bool:
    symbol_text = str(symbol or "").strip().upper()
    coin_text = str(coin_id or "").strip().casefold()
    return symbol_text == "SECTOR" or coin_text.startswith("sector") or coin_text in {
        "sports_fan_proxy",
        "rwa_preipo_proxy",
        "ai_ipo_proxy",
        "market_anomaly",
    }

def _research_review_family_id(
    *,
    symbol: str,
    coin_id: str,
    core_opportunity_id: str | None,
    decision: event_alpha_router.EventAlphaRouteDecision | None = None,
    core: Mapping[str, Any] | None = None,
) -> str:
    core = core or {}
    for key in ("candidate_family_id", "event_family_id", "event_family", "incident_asset_key"):
        value = core.get(key)
        if value:
            return str(value)
    if core_opportunity_id:
        return str(core_opportunity_id)
    entry = decision.entry if decision else None
    incident = str(getattr(entry, "incident_id", "") or core.get("incident_id") or "").strip() if entry else str(core.get("incident_id") or "").strip()
    external = str(core.get("external_asset") or (getattr(entry, "external_asset", "") if entry else "")).strip()
    asset = str(coin_id or symbol or "unknown").strip().casefold()
    if incident:
        return f"{incident}:{asset}"
    if external:
        return f"{external.casefold()}:{asset}"
    return asset or "unknown"

def _research_review_hard_gate_reason(decision: event_alpha_router.EventAlphaRouteDecision) -> str | None:
    entry = decision.entry
    components = dict(getattr(entry, "latest_score_components", {}) or {})
    fields = " ".join(
        str(value or "").casefold()
        for value in (
            getattr(entry, "latest_playbook_type", None),
            getattr(entry, "latest_rule_playbook_type", None),
            getattr(entry, "latest_effective_playbook_type", None),
            getattr(entry, "relationship_type", None),
            getattr(entry, "latest_llm_asset_role", None),
            getattr(entry, "candidate_role", None),
            getattr(entry, "impact_path_type", None),
            components.get("candidate_role"),
            components.get("asset_role"),
            components.get("llm_asset_role"),
            components.get("relationship_type"),
            components.get("impact_path_type"),
            components.get("impact_path_reason"),
            components.get("snapshot_class"),
            components.get("row_classification"),
            getattr(decision, "quality_gate_block_reason", None),
            getattr(decision, "reason", None),
            getattr(entry, "suppressed_reason", None),
        )
    )
    blockers = {
        "source_noise": "source_noise",
        "ticker_word_collision": "ticker_collision",
        "ticker_collision": "ticker_collision",
        "word_collision": "ticker_collision",
        "generic_cooccurrence_only": "generic_cooccurrence_only",
        "source_noise_control": "source_noise_control",
        "ambiguous_control": "ambiguous_control",
        "diagnostic_support": "diagnostic_support",
        "support_row": "support_row",
    }
    for token, reason in blockers.items():
        if token in fields:
            return reason
    if str(components.get("is_diagnostic_snapshot") or "").strip().casefold() in {"1", "true", "yes"}:
        return "diagnostic_snapshot"
    return None

def _research_review_rank(
    entry: Any,
    components: Mapping[str, Any],
    score: float,
) -> tuple[float, list[str]]:
    market = max(
        _component_score(components, "market_confirmation_score"),
        _component_score(components, "market_move_volume"),
    )
    source_quality = max(
        _component_score(components, "evidence_quality_score"),
        _component_score(components, "source_quality"),
    )
    freshness = _component_score(components, "novelty_freshness")
    cluster = _component_score(components, "cluster_confidence")
    rank = score + 0.35 * market + 0.25 * source_quality + 0.15 * freshness + 0.15 * cluster
    reasons: list[str] = []
    if score:
        reasons.append(f"near-miss score {score:g}")
    if market >= 25:
        reasons.append(f"market confirmation {market:g}")
    if source_quality >= 40:
        reasons.append(f"source quality {source_quality:g}")
    if getattr(entry, "external_asset", None) or getattr(entry, "event_time", None):
        reasons.append("has catalyst context")
    if cluster >= 40:
        reasons.append(f"cluster confidence {cluster:g}")
    if freshness >= 40:
        reasons.append("fresh opportunity")
    if not reasons:
        reasons.append("selected for manual research review")
    return rank, reasons

def _research_review_not_alertable_reasons(
    decision: event_alpha_router.EventAlphaRouteDecision,
    components: Mapping[str, Any],
) -> list[str]:
    reasons: list[str] = []
    for key in (
        "why_not_promoted",
        "quality_gate_block_reason",
        "why_not_watchlist",
        "why_local_only",
        "live_confirmation_reason",
        "no_upgrade_reason",
    ):
        value = components.get(key)
        if value:
            reasons.extend(_as_list(value))
    if getattr(decision, "quality_gate_block_reason", None):
        reasons.append(str(decision.quality_gate_block_reason))
    if getattr(decision.entry, "suppressed_reason", None):
        reasons.append(str(decision.entry.suppressed_reason))
    if getattr(decision, "reason", None):
        reasons.append(str(decision.reason))
    cleaned = [_human_reason(item) for item in reasons if str(item or "").strip()]
    if not cleaned:
        cleaned.append("missing confirmation for strict alert lanes")
    return list(dict.fromkeys(cleaned))[:3]

def _research_review_upgrade_steps(
    entry: Any,
    decision: event_alpha_router.EventAlphaRouteDecision,
    components: Mapping[str, Any],
) -> list[str]:
    steps: list[str] = []
    for key in ("what_would_upgrade", "upgrade_requirements", "manual_verification_items"):
        steps.extend(str(item) for item in _as_list(components.get(key)) if str(item or "").strip())
    if not steps:
        steps.extend(_exploratory_verify_steps(entry, _suppression_reason(decision)))
    return list(dict.fromkeys(step.replace("_", " ") for step in steps if step))[:3]

def _canonicalize_decisions_for_notification(
    decisions: Iterable[event_alpha_router.EventAlphaRouteDecision],
    core_row_by_alert_id: Mapping[str, Mapping[str, Any]],
) -> tuple[list[event_alpha_router.EventAlphaRouteDecision], tuple[str, ...]]:
    canonical: list[event_alpha_router.EventAlphaRouteDecision] = []
    warnings: list[str] = []
    for decision in decisions:
        core = _core_row_for_decision(decision, core_row_by_alert_id)
        if not core:
            canonical.append(decision)
            continue
        final_route = _core_final_route(core)
        block_reason = _core_notification_block_reason(core)
        if block_reason:
            final_route = event_alpha_router.EventAlphaRoute.STORE_ONLY.value
            warnings.append(f"{decision.alert_id}:notification_core_gate:{block_reason}")
        alertable = event_alpha_router.route_value_is_alertable(final_route)
        route = _route_enum_for_value(final_route)
        lane = _lane_enum_for_route(final_route)
        reason = str(
            block_reason
            or core.get("why_opportunity_visible")
            or core.get("final_verdict_reason")
            or core.get("quality_gate_block_reason")
            or decision.reason
        )
        canonical.append(
            replace(
                decision,
                route=route,
                lane=lane,
                alertable=alertable,
                reason=reason,
                final_route_after_quality_gate=final_route,
                quality_gate_block_reason=block_reason or decision.quality_gate_block_reason,
                opportunity_level=str(core.get("final_opportunity_level") or core.get("opportunity_level") or decision.opportunity_level or ""),
                opportunity_score_final=_float_or_none(
                    core.get("opportunity_score_final")
                    or core.get("final_opportunity_score")
                    or decision.opportunity_score_final
                ),
            )
        )
    return canonical, tuple(dict.fromkeys(warnings))

def _core_index_for_decisions(
    decisions: Iterable[event_alpha_router.EventAlphaRouteDecision],
    core_rows: Iterable[Mapping[str, Any] | object],
) -> dict[str, dict[str, Any]]:
    _ = decisions
    index: dict[str, dict[str, Any]] = {}
    for raw in core_rows or ():
        row = _as_mapping(raw)
        if not row:
            continue
        for key in _core_identity_keys(row):
            index.setdefault(key, row)
            index.setdefault(f"ea:{key}", row)
    return index

def _core_row_for_decision(
    decision: event_alpha_router.EventAlphaRouteDecision,
    core_row_by_alert_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any] | None:
    if not core_row_by_alert_id:
        return None
    for key in _decision_identity_keys(decision):
        row = core_row_by_alert_id.get(key)
        if row:
            return dict(row)
    return None

def _decision_identity_keys(decision: event_alpha_router.EventAlphaRouteDecision) -> tuple[str, ...]:
    entry = decision.entry
    components = getattr(entry, "latest_score_components", None) or {}
    values: list[Any] = [
        decision.alert_id,
        decision.card_id,
        getattr(entry, "key", None),
        getattr(entry, "hypothesis_id", None),
        getattr(entry, "incident_id", None),
        components.get("core_opportunity_id") if isinstance(components, Mapping) else None,
        components.get("canonical_core_opportunity_id") if isinstance(components, Mapping) else None,
        components.get("primary_hypothesis_id") if isinstance(components, Mapping) else None,
        components.get("hypothesis_id") if isinstance(components, Mapping) else None,
        components.get("watchlist_key") if isinstance(components, Mapping) else None,
        components.get("alert_id") if isinstance(components, Mapping) else None,
    ]
    if isinstance(components, Mapping):
        for name in ("supporting_hypothesis_ids", "diagnostic_row_ids", "supporting_row_ids"):
            values.extend(_as_list(components.get(name)))
    return tuple(dict.fromkeys(str(item).strip() for item in values if str(item or "").strip()))

def _core_identity_keys(row: Mapping[str, Any]) -> tuple[str, ...]:
    values: list[Any] = [
        row.get("core_opportunity_id"),
        row.get("aggregated_candidate_id"),
        row.get("primary_hypothesis_id"),
        row.get("hypothesis_id"),
        row.get("watchlist_key"),
        row.get("alert_id"),
        row.get("key"),
    ]
    for name in ("supporting_hypothesis_ids", "diagnostic_row_ids", "supporting_row_ids", "source_alert_ids"):
        values.extend(_as_list(row.get(name)))
    clean = [str(item).strip() for item in values if str(item or "").strip()]
    return tuple(dict.fromkeys(clean))

def _core_final_route(core: Mapping[str, Any]) -> str:
    value = str(
        core.get("final_route_after_quality_gate")
        or core.get("route")
        or core.get("final_route")
        or event_alpha_router.EventAlphaRoute.STORE_ONLY.value
    )
    if value in {"WATCHLIST", "RADAR", "VALIDATED_DIGEST"}:
        return event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value
    if value == "HIGH_PRIORITY":
        return event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value
    if value in {"LOCAL_ONLY", "QUALITY_BLOCKED", "RAW_EVIDENCE", "HYPOTHESIS"}:
        return event_alpha_router.EventAlphaRoute.STORE_ONLY.value
    return value

def _core_notification_block_reason(core: Mapping[str, Any]) -> str | None:
    route = _core_final_route(core)
    if route == event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH.value:
        return None
    if not event_alpha_router.route_value_is_alertable(route):
        return "canonical_core_not_alertable"
    symbol = str(core.get("symbol") or core.get("validated_symbol") or "").strip()
    coin_id = str(core.get("coin_id") or core.get("validated_coin_id") or "").strip()
    if symbol.upper() == "SECTOR" or coin_id.startswith("sector") or not coin_id:
        return "sector_or_missing_validated_asset_not_digest_eligible"
    status = str(core.get("evidence_acquisition_status") or "").strip()
    confirmation = str(core.get("acquisition_confirmation_status") or "").strip()
    accepted = _accepted_evidence_count(core)
    market = str(core.get("market_confirmation_level") or "").strip().casefold()
    freshness = str(core.get("market_context_freshness_status") or "").strip().casefold()
    source_class = str(core.get("source_class") or "").strip().casefold()
    impact_path = str(core.get("impact_path_type") or "").strip().casefold()
    has_market_confirmation = market not in {"", "none", "missing", "unknown", "insufficient_data"} and freshness not in {"missing", "stale"}
    has_strong_source = source_class in {
        "official_project",
        "official_exchange",
        "structured_event_calendar",
        "cryptopanic_tagged",
        "project_blog",
        "exchange_announcement",
    }
    has_accepted_confirmation = accepted > 0 or confirmation == "confirms" or bool(core.get("acquisition_confirms_candidate"))
    direct_event = impact_path in {
        "direct_token_event",
        "listing_liquidity_event",
        "unlock_supply_event",
        "exploit_security_event",
        "venue_value_capture",
        "fan_token_event",
    }
    if _core_is_unconfirmed_broad_strategic_asset(core):
        return "delivery_blocked_broad_strategic_asset_unconfirmed"
    if has_accepted_confirmation or has_strong_source or (has_market_confirmation and direct_event):
        return None
    if status == "rejected_results_only" or confirmation == "does_not_confirm":
        return "rejected_results_only_not_confirmation"
    if status == "skipped_budget":
        return "skipped_budget_not_confirmation"
    if status == "no_results":
        return "no_results_not_confirmation"
    if status in {"provider_unavailable", "backoff", "skipped_config", "not_configured"}:
        return f"{status}_not_confirmation"
    return "live_confirmation_missing"

def _accepted_evidence_count(core: Mapping[str, Any]) -> int:
    for key in ("accepted_evidence_count", "evidence_acquisition_accepted_count", "accepted_count"):
        value = _float_or_none(core.get(key))
        if value is not None:
            return max(0, int(value))
    return 0

def _core_is_unconfirmed_broad_strategic_asset(core: Mapping[str, Any]) -> bool:
    """Block broad treasury/equity valuation context from digest delivery.

    BTC/ETH/SOL can be valid Event Alpha candidates, but live-style notification
    delivery should not promote broad Strategy/MSTR/treasury/equity valuation
    articles unless the token impact was independently confirmed.
    """
    accepted = _accepted_evidence_count(core)
    confirmation = str(core.get("acquisition_confirmation_status") or "").strip()
    if accepted > 0 or confirmation == "confirms" or bool(core.get("acquisition_confirms_candidate")):
        return False
    symbol = str(core.get("symbol") or core.get("validated_symbol") or "").strip().upper()
    coin_id = str(core.get("coin_id") or core.get("validated_coin_id") or "").strip().casefold()
    if symbol not in {"BTC", "ETH", "SOL"} and coin_id not in {"bitcoin", "ethereum", "solana"}:
        return False
    impact = str(core.get("impact_path_type") or core.get("primary_impact_path") or "").strip().casefold()
    reason = str(core.get("impact_path_reason") or core.get("primary_impact_path_reason") or "").strip().casefold()
    if impact not in {"strategic_investment", "strategic_investment_or_valuation", "valuation_event"} and reason not in {
        "strategic_investment",
        "treasury_context",
        "external_equity_proxy_context",
    }:
        return False
    text = " ".join(
        str(core.get(key) or "")
        for key in (
            "canonical_incident_name",
            "incident_canonical_name",
            "latest_event_name",
            "event_name",
            "latest_source_title",
            "source_title",
            "latest_source",
            "source",
            "why_opportunity_visible",
            "final_verdict_reason",
        )
    ).casefold()
    broad_terms = (
        "strategy",
        "microstrategy",
        "mstr",
        "treasury",
        "holdings",
        "valuation",
        "discount",
        "premium",
        "public company",
        "market structure",
        "equity valuation",
        "shares",
        "stock",
    )
    direct_terms = (
        "protocol upgrade",
        "network upgrade",
        "spot etf approved",
        "listing",
        "unlock",
        "exploit",
    )
    return any(term in text for term in broad_terms) and not any(term in text for term in direct_terms)

def _route_enum_for_value(value: object) -> event_alpha_router.EventAlphaRoute:
    raw = str(getattr(value, "value", value) or "")
    try:
        return event_alpha_router.EventAlphaRoute(raw)
    except ValueError:
        if raw == event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value:
            return event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH
        if raw == event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH.value:
            return event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH
        if raw == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value:
            return event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST
        return event_alpha_router.EventAlphaRoute.STORE_ONLY

def _lane_enum_for_route(value: object) -> event_alpha_router.EventAlphaRouteLane:
    lane = event_alpha_router.lane_value_for_route_value(value)
    try:
        return event_alpha_router.EventAlphaRouteLane(lane)
    except ValueError:
        return event_alpha_router.EventAlphaRouteLane.LOCAL_ONLY

def _as_mapping(value: Mapping[str, Any] | object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "to_row"):
        try:
            row = value.to_row()
            if isinstance(row, Mapping):
                return dict(row)
        except Exception:
            return {}
    if hasattr(value, "__dict__"):
        return dict(getattr(value, "__dict__", {}) or {})
    return {}

def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    if isinstance(value, str) and value.startswith("["):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return parsed
    return [value]

def _lane_for_decision(decision: event_alpha_router.EventAlphaRouteDecision) -> str:
    final_lane = event_alpha_router.final_lane_value(decision)
    if final_lane == event_alpha_router.EventAlphaRouteLane.TRIGGERED_FADE.value:
        return LANE_TRIGGERED_FADE
    if final_lane == event_alpha_router.EventAlphaRouteLane.INSTANT_ESCALATION.value:
        return LANE_INSTANT_ESCALATION
    if final_lane == event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST.value:
        return LANE_DAILY_DIGEST
    return LANE_DAILY_DIGEST

def _cooldown_hours(lane: str, cfg: EventAlphaNotificationConfig) -> float:
    if lane == LANE_DAILY_DIGEST:
        return cfg.daily_digest_cooldown_hours
    if lane == LANE_INSTANT_ESCALATION:
        return cfg.instant_escalation_cooldown_hours
    if lane == LANE_RESEARCH_REVIEW_DIGEST:
        return cfg.research_review_digest_cooldown_hours
    if lane == LANE_EXPLORATORY_DIGEST:
        return cfg.exploratory_digest_cooldown_hours
    if lane == LANE_HEALTH_HEARTBEAT:
        return cfg.health_heartbeat_cooldown_hours
    return 0.0

def _sent_count_today(
    storage: Any,
    lane: str,
    now: datetime,
    cfg: EventAlphaNotificationConfig | None = None,
) -> int:
    try:
        return int(storage.get_meta(_count_meta_key(lane, now, cfg)) or "0")
    except (TypeError, ValueError):
        return 0

def _count_meta_key(lane: str, now: datetime, cfg: EventAlphaNotificationConfig | None = None) -> str:
    suffix = {
        LANE_DAILY_DIGEST: "daily_digest",
        LANE_INSTANT_ESCALATION: "instant",
        LANE_TRIGGERED_FADE: "triggered",
        LANE_RESEARCH_REVIEW_DIGEST: "research_review",
        LANE_EXPLORATORY_DIGEST: "exploratory",
        LANE_HEALTH_HEARTBEAT: "health_heartbeat",
    }[_clean_lane(lane)]
    if cfg is not None and _clean_scope(cfg.notification_scope) != NOTIFICATION_SCOPE_GLOBAL:
        return f"event_alpha_notify:{_scope_value(cfg)}:sent_count:{suffix}:{now.date().isoformat()}"
    return f"event_alpha_sent_count_{suffix}_{now.date().isoformat()}"

def _triggered_alert_meta_key(alert_id: str, cfg: EventAlphaNotificationConfig | None = None) -> str:
    digest = hashlib.sha1(str(alert_id).encode("utf-8")).hexdigest()[:20]
    if cfg is not None and _clean_scope(cfg.notification_scope) != NOTIFICATION_SCOPE_GLOBAL:
        return f"event_alpha_notify:{_scope_value(cfg)}:triggered:{digest}"
    return f"event_alpha_sent_triggered_fade_alert_{digest}"

def _last_sent_meta_key(lane: str, cfg: EventAlphaNotificationConfig) -> str:
    lane_key = _clean_lane(lane)
    if _clean_scope(cfg.notification_scope) == NOTIFICATION_SCOPE_GLOBAL:
        return LAST_SENT_META_KEYS[lane_key]
    return f"event_alpha_notify:{_scope_value(cfg)}:last_sent:{lane_key}"

def _clean_lane(lane: str) -> str:
    value = str(lane or "").strip().lower()
    if value not in LAST_SENT_META_KEYS:
        raise ValueError(f"unknown Event Alpha notification lane: {lane!r}")
    return value

def _clean_scope(scope: str) -> str:
    value = str(scope or "").strip().lower()
    return value if value in NOTIFICATION_SCOPES else NOTIFICATION_SCOPE_GLOBAL

def _scope_value(cfg: EventAlphaNotificationConfig) -> str:
    scope = _clean_scope(cfg.notification_scope)
    if scope == NOTIFICATION_SCOPE_GLOBAL:
        return NOTIFICATION_SCOPE_GLOBAL
    if scope == NOTIFICATION_SCOPE_PROFILE:
        return _clean_token(cfg.profile_name or cfg.artifact_namespace or "default")
    return _clean_token(cfg.artifact_namespace or cfg.profile_name or "default")

def _clean_token(value: object) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9_.-]+", "_", text).strip("._-")
    return text or "default"

def _parse_iso(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _as_utc(parsed)

def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

def _format_clock_status(status: Mapping[str, Any]) -> str:
    age = status.get("fixed_clock_age_hours")
    age_text = "n/a" if age is None else f"{float(age):.2f}h"
    return (
        "clock: "
        f"mode={status.get('clock_mode') or 'unknown'} "
        f"research_now={status.get('research_now') or 'unknown'} "
        f"wall_clock_now={status.get('wall_clock_now') or 'unknown'} "
        f"fixed_clock_age={age_text}"
    )

def _fixed_clock_send_blocked(status: Mapping[str, Any]) -> bool:
    if str(status.get("clock_mode") or "") != "fixed":
        return False
    age = status.get("fixed_clock_age_hours")
    try:
        hours = float(age)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    return hours > 24.0 or hours < -1.0

def _esc(value: object) -> str:
    return html.escape(str(value), quote=False)

def _value(result: Any | None, attr: str, default: Any = None) -> Any:
    if result is None:
        return default
    if isinstance(result, Mapping):
        return result.get(attr, default)
    return getattr(result, attr, default)

def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0

def _mapping_value(result: Any | None, attr: str) -> dict[str, Any]:
    value = _value(result, attr, {})
    return dict(value) if isinstance(value, Mapping) else {}

def _num(result: Any | None, attr: str) -> int:
    if attr == "llm_calls_attempted":
        explicit = _value(result, attr, None)
        if explicit is not None:
            return _safe_int(explicit)
        return _llm_stats_from_result(result)["calls_attempted"]
    if attr == "llm_skipped_due_budget":
        explicit = _value(result, attr, None)
        if explicit is not None:
            return _safe_int(explicit)
        return _llm_stats_from_result(result)["skipped_due_budget"]
    if attr == "core_opportunities":
        value = _value(result, "core_opportunities", None)
        if value is None:
            value = _value(result, "core_opportunity_rows_written", 0)
        return _safe_int(value)
    value = _value(result, attr, 0)
    if isinstance(value, (list, tuple, set)):
        return len(value)
    return _safe_int(_value(result, attr, 0))

def _raw_source_candidate_count(result: Any | None) -> int:
    for attr in ("raw_source_candidates", "source_candidates", "candidate_rows", "candidates"):
        value = _num(result, attr)
        if value:
            return value
    return 0

__all__ = (
    'build_notification_plan',
    '_confirmed_daily_digest_decisions',
    '_daily_digest_requires_live_confirmation',
    '_daily_digest_has_confirmation',
    '_has_digest_market_confirmation',
    '_mapping_counts',
    '_dedupe_daily_digest_decisions',
    '_strict_lane_core_ids',
    '_core_id_for_decision',
    '_core_row_is_research_alertable',
    '_daily_digest_group_key',
    '_decision_entry',
    '_impact_family',
    '_with_unconfirmed_daily_review_items',
    '_iter_values',
    'select_exploratory_candidates',
    '_is_promoted_or_validated_exploratory',
    '_quality_mode',
    '_filter_alertable_by_quality_mode',
    '_route_value',
    '_research_review_level',
    '_research_review_score',
    '_research_review_is_sector',
    '_research_review_family_id',
    '_research_review_hard_gate_reason',
    '_research_review_rank',
    '_research_review_not_alertable_reasons',
    '_research_review_upgrade_steps',
    '_canonicalize_decisions_for_notification',
    '_core_index_for_decisions',
    '_core_row_for_decision',
    '_decision_identity_keys',
    '_core_identity_keys',
    '_core_final_route',
    '_core_notification_block_reason',
    '_accepted_evidence_count',
    '_core_is_unconfirmed_broad_strategic_asset',
    '_route_enum_for_value',
    '_lane_enum_for_route',
    '_as_mapping',
    '_as_list',
    '_lane_for_decision',
    '_cooldown_hours',
    '_sent_count_today',
    '_count_meta_key',
    '_triggered_alert_meta_key',
    '_last_sent_meta_key',
    '_clean_lane',
    '_clean_scope',
    '_scope_value',
    '_clean_token',
    '_parse_iso',
    '_as_utc',
    '_format_clock_status',
    '_fixed_clock_send_blocked',
    '_esc',
    '_value',
    '_safe_int',
    '_mapping_value',
    '_num',
    '_raw_source_candidate_count',
)
