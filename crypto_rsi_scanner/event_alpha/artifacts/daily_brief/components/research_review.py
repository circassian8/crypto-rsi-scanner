"""Research Review helpers for daily brief."""

from __future__ import annotations

from .runtime import *

def _compact(report: str) -> str:
    lines = [line for line in str(report or "").splitlines() if line and not line.startswith("=")]
    return "\n".join(f"> {line}" for line in lines[:20])

def _burn_in_readiness_lines(
    *,
    latest: Mapping[str, Any],
    core_opportunities: Iterable[Any],
    card_paths: Iterable[Path],
    evidence_acquisition_rows: Iterable[Mapping[str, Any]],
    provider_health_rows: Mapping[str, Mapping[str, Any]],
    requested_profile: str | None,
) -> list[str]:
    cores = list(core_opportunities)
    cards = [Path(path) for path in card_paths if Path(path).name != "index.md"]
    feedback_targets = sum(1 for path in cards if event_research_cards.card_feedback_target(path))
    acquisition = [dict(row) for row in evidence_acquisition_rows if isinstance(row, Mapping)]
    accepted = sum(
        1 for row in acquisition
        if int(row.get("accepted_evidence_count") or 0) > 0
        or str(row.get("acquisition_status") or row.get("status") or "") in {
            "accepted_evidence_found",
            "accepted",
        }
    )
    send_requested = bool(latest.get("send_requested")) if latest else False
    sent = bool(latest.get("sent")) if latest else False
    delivered = int(latest.get("send_items_delivered") or latest.get("deliveries_delivered") or 0) if latest else 0
    no_send = bool(latest) and not send_requested and not sent and delivered <= 0
    health_rows = list((provider_health_rows or {}).values())
    backoff = sum(1 for row in health_rows if row.get("disabled_until"))
    degraded = sum(1 for row in health_rows if int(row.get("consecutive_failures") or 0) > 0 or row.get("last_error_safe"))
    provider_fetches = int(latest.get("provider_fetch_count") or 0) if latest else 0
    provider_hits = int(latest.get("provider_cache_hits") or 0) if latest else 0
    provider_misses = int(latest.get("provider_cache_misses") or 0) if latest else 0
    warnings = [str(item) for item in (latest.get("warnings") or []) if str(item)] if latest else []
    keys_missing = [item for item in warnings if "missing" in item.lower() or "disabled" in item.lower()]
    return [
        f"- Burn-in mode: {'no-send' if no_send else 'send-capable or unknown'} "
        f"(profile={requested_profile or latest.get('profile') or 'latest'})",
        f"- Provider coverage: health_rows={len(health_rows)} degraded={degraded} backoff={backoff} "
        f"fetches={provider_fetches} cache_hits={provider_hits} cache_misses={provider_misses}",
        f"- Opportunities found: core={len(cores)} high_priority={sum(1 for item in cores if getattr(item, 'is_high_priority', False))} "
        f"watchlist={sum(1 for item in cores if getattr(item, 'is_watchlist', False))}",
        f"- Evidence acquisition: rows={len(acquisition)} accepted={accepted}",
        f"- Feedback targets: cards_with_targets={feedback_targets}/{len(cards)}",
        "- What to review manually: provider gaps, source-pack evidence absence, core opportunity cards, near-miss rows, and feedback targets.",
        "- Missing keys/providers: "
        + ("; ".join(keys_missing[:5]) if keys_missing else "see provider readiness/status report for configured vs missing sources."),
    ]

def _system_health_summary_lines(latest: Mapping[str, Any]) -> list[str]:
    if not latest:
        return ["- No run ledger rows found; detailed diagnostics below."]
    return [
        f"- Latest run: {latest.get('run_id') or 'unknown'}",
        f"- Success: {str(bool(latest.get('success'))).lower()}",
        f"- Routed / alertable / sent: {int(latest.get('routed') or 0)} / "
        f"{int(latest.get('alertable') or 0)} / {str(bool(latest.get('sent'))).lower()}",
        f"- Catalyst frames analyzed / validated: "
        f"{int(latest.get('catalyst_frames_analyzed') or latest.get('catalyst_frame_rows') or 0)} / "
        f"{int(latest.get('catalyst_frame_validations') or latest.get('catalyst_frame_validations_applied') or 0)}",
        "- Detailed provider, budget, routing, and quality diagnostics are in the appendix below.",
    ]

def _near_miss_daily_lines(
    near_misses: Iterable[event_near_miss.EventNearMissCandidate],
    *,
    limit: int,
) -> list[str]:
    raw_rows = list(near_misses)
    rows = _dedupe_near_miss_candidates(raw_rows)
    if not rows:
        return ["- None."]
    lines: list[str] = []
    for item in rows[:limit]:
        interesting = _near_miss_interest(item)
        missing = _friendly_reason_list(item.missing_evidence) or "none"
        upgrade = _friendly_action_list(item.recommended_refresh_actions) or "operator review"
        invalidate = _near_miss_invalidation(item)
        lines.append(
            f"- {item.symbol}/{item.coin_id}: {interesting} "
            f"Score {item.opportunity_score_before:.0f}"
            + (
                f"->{item.opportunity_score_after:.0f}"
                if item.opportunity_score_after is not None
                and round(item.opportunity_score_after, 2) != round(item.opportunity_score_before, 2)
                else ""
            )
            + f", level={_friendly_level(item.opportunity_level_before)}"
            + (
                f"->{_friendly_level(item.opportunity_level_after)}"
                if item.opportunity_level_after
                and item.opportunity_level_after != item.opportunity_level_before
                else ""
            )
            + "."
        )
        lines.append(f"  missing: {missing}")
        lines.append(f"  would upgrade: {upgrade}")
        if item.market_refresh_attempted or item.refresh_upgrade_status:
            lines.append(
                "  targeted market refresh: "
                f"{str(item.market_refresh_success).lower()} "
                f"provider={item.market_refresh_provider or item.market_context_source or 'unknown'} "
                f"market={item.market_confirmation_before if item.market_confirmation_before is not None else 'n/a'}"
                f"->{item.market_confirmation_after if item.market_confirmation_after is not None else 'n/a'} "
                f"status={item.refresh_upgrade_status or item.upgrade_reason or item.no_upgrade_reason or 'pending'}"
            )
        lines.append(f"  would invalidate: {invalidate}")
    hidden_duplicates = max(0, len(raw_rows) - len(rows))
    if hidden_duplicates:
        lines.append(f"- +{hidden_duplicates} related duplicate/support near-miss row(s) hidden")
    if len(rows) > limit:
        lines.append(f"- +{len(rows) - limit} more near-miss candidate families")
    return lines

def _near_miss_diagnostic_lines(
    near_misses: Iterable[event_near_miss.EventNearMissCandidate],
    *,
    limit: int,
) -> list[str]:
    raw_rows = list(near_misses)
    rows = _dedupe_near_miss_candidates(raw_rows)
    if not rows:
        return ["- None."]
    lines: list[str] = []
    for item in rows[:limit]:
        refresh = (
            f"market_refresh={str(item.market_refresh_attempted).lower()}/"
            f"{str(item.market_refresh_success).lower()}"
        )
        lines.append(
            f"- {item.symbol}/{item.coin_id}: score={item.opportunity_score_before:.0f} "
            f"level={item.opportunity_level_before}->{item.opportunity_level_after or item.opportunity_level_before} "
            f"route={item.final_route_before or 'unknown'}->{item.final_route_after or item.final_route_before or 'unknown'} "
            f"raw_missing={', '.join(item.missing_evidence[:4]) or 'none'}; "
            f"actions={', '.join(item.recommended_refresh_actions[:4]) or 'operator_review'}; {refresh}"
            f" provider={item.market_refresh_provider or item.market_context_source or 'unknown'}"
            f" upgrade_status={item.refresh_upgrade_status or item.upgrade_reason or item.no_upgrade_reason or 'pending'}"
        )
    hidden_duplicates = max(0, len(raw_rows) - len(rows))
    if hidden_duplicates:
        lines.append(f"- +{hidden_duplicates} related duplicate/support diagnostic row(s) hidden")
    return lines

def _dedupe_near_miss_candidates(
    rows: Iterable[event_near_miss.EventNearMissCandidate],
) -> list[event_near_miss.EventNearMissCandidate]:
    grouped: dict[tuple[str, str], event_near_miss.EventNearMissCandidate] = {}
    for item in rows:
        key = (
            event_core_opportunities.asset_key_for_values(item.coin_id, item.symbol),
            _impact_family(getattr(item, "impact_path_type", None) or getattr(item, "playbook_type", None) or ""),
        )
        current = grouped.get(key)
        if current is None or item.opportunity_score_before > current.opportunity_score_before:
            grouped[key] = item
    return sorted(grouped.values(), key=lambda item: item.opportunity_score_before, reverse=True)

def _decision_family_key(decision: event_alpha_router.EventAlphaRouteDecision) -> tuple[str, str]:
    entry = decision.entry
    components = entry.latest_score_components or {}
    return (
        event_core_opportunities.asset_key_for_values(entry.coin_id, entry.symbol),
        _impact_family(components.get("impact_path_type") or entry.impact_path_type or entry.latest_playbook_type or ""),
    )

def _entry_family_key(entry: event_watchlist.EventWatchlistEntry) -> tuple[str, str]:
    components = entry.latest_score_components or {}
    return (
        event_core_opportunities.asset_key_for_values(entry.coin_id, entry.symbol),
        _impact_family(components.get("impact_path_type") or entry.impact_path_type or entry.latest_playbook_type or ""),
    )

def _dedupe_watchlist_entries(
    rows: Iterable[event_watchlist.EventWatchlistEntry],
) -> list[event_watchlist.EventWatchlistEntry]:
    grouped: dict[tuple[str, str], event_watchlist.EventWatchlistEntry] = {}
    for entry in rows:
        key = _entry_family_key(entry)
        current = grouped.get(key)
        if current is None or entry.latest_score > current.latest_score:
            grouped[key] = entry
    return sorted(grouped.values(), key=lambda item: item.latest_score, reverse=True)

def _impact_family(value: object) -> str:
    text = str(value or "").casefold()
    if any(token in text for token in ("fan", "sports", "world_cup", "world cup")):
        return "fan_token"
    if any(token in text for token in ("proxy", "preipo", "pre-ipo", "rwa", "venue_value", "tokenized")):
        return "proxy"
    if "listing" in text or "exchange" in text:
        return "listing"
    if "unlock" in text or "supply" in text:
        return "supply"
    if "security" in text or "exploit" in text:
        return "security"
    if "insufficient" in text or not text:
        return "unknown"
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_") or "unknown"

def _near_miss_interest(item: event_near_miss.EventNearMissCandidate) -> str:
    missing_text = " ".join(item.missing_evidence).casefold()
    if "cause_unknown_market_dislocation" in missing_text:
        return "token moved, but the cause is still unknown."
    if "generic_cooccurrence_only" in missing_text:
        return "source evidence mentions the token and catalyst together, but the impact mechanism is not proven."
    if item.opportunity_score_before >= 60:
        return "close to digest threshold but still missing confirmation."
    return "interesting enough for local research, but not ready for alert routing."

def _near_miss_invalidation(item: event_near_miss.EventNearMissCandidate) -> str:
    missing_text = " ".join(item.missing_evidence).casefold()
    if "cause_unknown_market_dislocation" in missing_text:
        return "an unrelated market move, no catalyst found, or fast mean reversion."
    if "generic_cooccurrence_only" in missing_text:
        return "no direct token impact path appears after source review."
    if "market" in missing_text:
        return "price/volume reaction remains weak or fades."
    return "identity, catalyst link, or market reaction fails review."

def _card_groups_for_daily_brief(paths: Iterable[Path]) -> dict[str, list[Path]]:
    grouped: dict[str, list[Path]] = {name: [] for name in event_research_cards.CARD_INDEX_GROUPS}
    group_map = event_research_cards.card_index_group_map(paths)
    for path in paths:
        p = Path(path)
        if p.name == "index.md":
            continue
        grouped.setdefault(group_map.get(p) or event_research_cards.card_index_group(p), []).append(p)
    return grouped

def _latest_notification_run(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any] | None:
    ordered = sorted(
        (dict(row) for row in rows if isinstance(row, Mapping)),
        key=lambda row: str(row.get("started_at") or ""),
        reverse=True,
    )
    return ordered[0] if ordered else None

def _provider_health_lines(rows: Mapping[str, Mapping[str, Any]]) -> list[str]:
    if not rows:
        return ["- No provider health rows found."]
    grouped: dict[str, list[tuple[str, Mapping[str, Any]]]] = {}
    for provider, row in rows.items():
        grouped.setdefault(str(row.get("provider_kind") or "unclassified"), []).append((str(provider), row))
    lines: list[str] = []
    for group in ("event_source", "enrichment", "catalyst_search", "llm", "unclassified"):
        items = grouped.get(group)
        if not items:
            continue
        lines.append(f"- {group}:")
        for provider, row in sorted(items)[:8]:
            disabled = row.get("disabled_until") or "none"
            lines.append(
                f"  - {provider}: failures={int(row.get('consecutive_failures') or 0)} "
                f"disabled_until={disabled} last_success={row.get('last_success_at') or 'never'}"
            )
    return lines or ["- No provider health rows found."]

def _llm_budget_lines(latest: Mapping[str, Any]) -> list[str]:
    if not latest:
        return ["- No latest run row; budget usage unknown."]
    return [
        f"- Cache hits/misses: {int(latest.get('llm_cache_hits') or 0)} / {int(latest.get('llm_cache_misses') or 0)}",
        f"- Calls attempted: {int(latest.get('llm_calls_attempted') or 0)}",
        f"- Skipped due budget: {int(latest.get('llm_skipped_due_budget') or 0)}",
    ]

def _new_since_last_run_lines(runs: list[dict[str, Any]]) -> list[str]:
    if not runs:
        return ["- No run history."]
    latest = runs[0]
    previous = runs[1] if len(runs) > 1 else {}
    fields = ("raw_events", "candidates", "alerts", "watchlist_entries", "alertable")
    lines = []
    for field in fields:
        delta = int(latest.get(field) or 0) - int(previous.get(field) or 0)
        lines.append(f"- {field}: {int(latest.get(field) or 0)} ({delta:+d} vs previous)")
    return lines

def _watchlist_hotter_lines(entries: list[event_watchlist.EventWatchlistEntry]) -> list[str]:
    hot = [
        entry for entry in entries
        if entry.score_jump > 0
        or entry.derivatives_crowding_upgraded
        or entry.cluster_confidence_upgraded
        or entry.event_time_upgraded
    ]
    if not hot:
        return ["- No hotter watchlist rows found."]
    lines = []
    for entry in sorted(hot, key=lambda item: (item.score_jump, item.latest_score), reverse=True)[:5]:
        reasons = ", ".join(entry.material_change_reasons) if entry.material_change_reasons else "material update"
        lines.append(f"- {entry.symbol}/{entry.coin_id}: score={entry.latest_score} jump={entry.score_jump} reasons={reasons}")
    return lines

def _watchlist_identity_suffix(entry: event_watchlist.EventWatchlistEntry) -> str:
    components = entry.latest_score_components or {}
    parts: list[str] = []
    asset_kind = components.get("asset_kind")
    role_source = components.get("role_source")
    collision = components.get("collision_risk")
    if asset_kind:
        parts.append(f"asset_kind={asset_kind}")
    if role_source:
        parts.append(f"role_source={role_source}")
    if collision:
        parts.append(f"collision={collision}")
    return " " + " ".join(parts) if parts else ""

def _suppression_lines(
    decisions: list[event_alpha_router.EventAlphaRouteDecision],
    entries: list[event_watchlist.EventWatchlistEntry],
) -> list[str]:
    counts: dict[str, int] = {}
    for decision in decisions:
        if event_alpha_router.alertable_after_quality_gate(decision):
            continue
        counts[decision.reason] = counts.get(decision.reason, 0) + 1
    for entry in entries:
        if entry.suppressed_reason:
            counts[entry.suppressed_reason] = counts.get(entry.suppressed_reason, 0) + 1
    if not counts:
        return ["- None."]
    return [f"- {reason}: {count}" for reason, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:5]]

def _core_alertable_count(core_opportunities: Iterable[event_core_opportunities.CoreOpportunity]) -> int:
    return sum(
        1 for item in core_opportunities
        if event_alpha_router.route_value_is_alertable(item.final_route_after_quality_gate)
    )

def _field_counts(rows: Iterable[Mapping[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get(field) or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return counts

def _multi_field_counts(rows: Iterable[Mapping[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        values = row.get(field) or []
        if isinstance(values, str):
            values = [values]
        for value in values:
            key = str(value or "").strip()
            if key:
                counts[key] = counts.get(key, 0) + 1
    return counts

def _format_counts(counts: Mapping[str, int]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items())) or "none"

def _brief_hypothesis_labels(rows: Iterable[Mapping[str, Any]]) -> str:
    labels: list[str] = []
    for row in rows:
        candidates = row.get("validated_candidate_assets") or row.get("crypto_candidate_assets") or row.get("suggested_candidate_assets") or []
        candidate_label = "none"
        if candidates and isinstance(candidates[0], Mapping):
            candidate_label = str(candidates[0].get("symbol") or candidates[0].get("coin_id") or "asset")
        labels.append(
            f"{row.get('impact_category') or 'unknown'}"
            f"/{row.get('external_asset') or 'unknown'}"
            f"/candidate={candidate_label}"
            f"({row.get('validation_stage') or row.get('status') or 'unknown'}"
            f",score={_float(row.get('hypothesis_score') or _float(row.get('confidence')) * 100):.0f}"
            f",v2={_float(row.get('opportunity_score_v2')):.0f}"
            f",path={row.get('impact_path_type') or 'unknown'}"
            f",main={row.get('main_frame_type') or 'unknown'}"
            f",role={row.get('candidate_role') or 'unknown'})"
        )
    return "; ".join(labels)

def _brief_decisions(rows: Iterable[event_alpha_router.EventAlphaRouteDecision]) -> str:
    labels = []
    seen: set[tuple[str, str]] = set()
    for decision in rows:
        key = _decision_family_key(decision)
        if key in seen:
            continue
        seen.add(key)
        entry = decision.entry
        components = entry.latest_score_components or {}
        final_route = event_alpha_router.final_route_value(decision)
        labels.append(
            f"{entry.symbol}/{entry.coin_id}"
            f"({event_watchlist.final_state_value(entry)},score={entry.latest_score},v2={_float(components.get('opportunity_score_v2')):.0f},"
            f"final={_float(components.get('opportunity_score_final')):.0f},"
            f"level={components.get('opportunity_level') or 'unknown'},"
            f"path={components.get('impact_path_type') or 'unknown'},role={components.get('candidate_role') or 'unknown'},"
            f"main={components.get('main_frame_type') or 'unknown'},"
            f"route={final_route},requested={decision.requested_route_before_quality_gate or decision.route.value},reason={decision.reason})"
        )
    return "; ".join(labels)

def _core_opportunity_lines(
    opportunities: Iterable[event_core_opportunities.CoreOpportunity],
    *,
    limit: int,
) -> list[str]:
    rows, collapsed_counts = _collapse_core_display_rows(opportunities)
    if not rows:
        return ["- None."]
    lines: list[str] = []
    for item in rows[:limit]:
        categories = ", ".join(item.supporting_categories[:4]) or "unknown"
        paths = ", ".join(item.supporting_impact_paths[:4]) or item.primary_impact_path
        lane = str(item.primary_row.get("opportunity_type") or "UNCLASSIFIED")
        market_state = str(item.primary_row.get("market_state_class") or item.primary_row.get("market_state") or "unknown")
        lane_reason = str(item.primary_row.get("why_now") or item.primary_row.get("opportunity_type_why_now") or "")
        diagnostics = ""
        if item.diagnostic_row_count or item.quality_capped_supporting_rows:
            diagnostics = (
                f" diagnostics_hidden={item.diagnostic_row_count}"
                f" quality_capped_support={item.quality_capped_supporting_rows}"
            )
        family_count = collapsed_counts.get(_core_display_family_key(item), 1)
        if family_count > 1:
            diagnostics += f" collapsed_family_rows={family_count - 1}"
        lines.append(
            f"- {item.core_opportunity_id} {item.symbol}/{item.coin_id}: "
            f"level={item.opportunity_level} route={item.final_route_after_quality_gate or 'local'} "
            f"state={item.final_state_after_quality_gate or 'unknown'} "
            f"score={item.opportunity_score_final:.0f} "
            f"lane={lane} market_state={market_state} "
            f"path={item.primary_impact_path} role={item.candidate_role} "
            f"asset_kind={item.asset_kind or 'unknown'} "
            f"role_source={item.role_source or 'unknown'} "
            f"collision={item.collision_risk or 'none'} "
            f"categories={categories} paths={paths}{diagnostics}"
        )
        if lane_reason:
            lines.append(f"  why_now: {lane_reason}")
        lines.append(
            f"  support: hypotheses={len(item.supporting_hypothesis_ids)} "
            f"categories={categories} impact_paths={paths} "
            f"hidden_diagnostics={item.diagnostic_row_count} "
            f"quality_capped_support={item.quality_capped_supporting_rows}"
        )
        if item.role_capabilities:
            caps = ", ".join(key for key, value in sorted(item.role_capabilities.items()) if value) or "none"
            lines.append(f"  role capabilities: {caps}")
        if item.identity_evidence:
            lines.append(f"  identity: confidence={item.identity_confidence if item.identity_confidence is not None else 'n/a'} evidence={item.identity_evidence[0]}")
        if item.role_validation_failures:
            lines.append(f"  role validation failures: {', '.join(item.role_validation_failures[:4])}")
        if item.supporting_evidence_quotes:
            lines.append(f"  evidence: {item.supporting_evidence_quotes[0]}")
        if item.why_other_rows_hidden != "no hidden supporting rows":
            lines.append(f"  collapsed: {item.why_other_rows_hidden}")
    if len(rows) > limit:
        lines.append(f"- +{len(rows) - limit} more core opportunities")
    return lines

def _collapse_core_display_rows(
    opportunities: Iterable[event_core_opportunities.CoreOpportunity],
) -> tuple[list[event_core_opportunities.CoreOpportunity], dict[tuple[str, str], int]]:
    grouped: dict[tuple[str, str], list[event_core_opportunities.CoreOpportunity]] = {}
    for item in opportunities:
        if _hide_core_from_default_display(item):
            continue
        grouped.setdefault(_core_display_family_key(item), []).append(item)
    rows: list[event_core_opportunities.CoreOpportunity] = []
    counts: dict[tuple[str, str], int] = {}
    for key, items in grouped.items():
        counts[key] = len(items)
        rows.append(sorted(items, key=_core_display_rank, reverse=True)[0])
    return rows, counts

def _core_display_rank(item: event_core_opportunities.CoreOpportunity) -> tuple[int, float, str]:
    if item.is_high_priority:
        route_rank = 5
    elif item.is_watchlist:
        route_rank = 4
    elif item.is_validated_digest:
        route_rank = 3
    elif item.alertable:
        route_rank = 2
    else:
        route_rank = 1
    return route_rank, item.opportunity_score_final, item.core_opportunity_id

def _core_display_family_key(item: event_core_opportunities.CoreOpportunity) -> tuple[str, str]:
    asset = event_core_opportunities.asset_key_for_opportunity(item)
    path = str(item.primary_impact_path or "").casefold()
    family = "proxy" if path in {"venue_value_capture", "proxy_attention", "proxy_exposure"} else path or "unknown"
    return asset, family

def _hide_core_from_default_display(item: event_core_opportunities.CoreOpportunity) -> bool:
    if str(item.symbol or "").upper() != "SECTOR":
        return False
    return not (item.alertable or item.is_high_priority or item.is_watchlist or item.is_validated_digest)

def _research_review_delivery_rows(run_ledger_path: str | Path | None) -> list[Mapping[str, Any]]:
    if run_ledger_path is None:
        return []
    path = Path(run_ledger_path).parent / "event_alpha_notification_deliveries.jsonl"
    if not path.exists():
        return []
    rows: list[Mapping[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if isinstance(row, Mapping) and str(row.get("lane") or "") == event_alpha_notifications.LANE_RESEARCH_REVIEW_DIGEST:
                rows.append(row)
    except (OSError, json.JSONDecodeError):
        return rows
    return sorted(rows, key=lambda row: str(row.get("attempted_at") or row.get("created_at") or ""), reverse=True)

def _research_review_delivery_line(row: Mapping[str, Any]) -> str:
    symbols = row.get("canonical_symbols") if isinstance(row.get("canonical_symbols"), list) else []
    coins = row.get("canonical_coin_ids") if isinstance(row.get("canonical_coin_ids"), list) else []
    core_ids = row.get("core_opportunity_ids") if isinstance(row.get("core_opportunity_ids"), list) else []
    if len(symbols) > 1:
        label = " + ".join(str(value) for value in symbols[:6])
        if len(symbols) > 6:
            label += f" +{len(symbols) - 6} more"
        coin = f"{len(coins)} coin(s)" if coins else "multiple"
        core_id = f"{len(core_ids)} core(s): " + ", ".join(str(value) for value in core_ids[:4])
    else:
        label = str(row.get("canonical_symbol") or (symbols[0] if symbols else "") or row.get("symbol") or "UNKNOWN")
        coin = str(row.get("canonical_coin_id") or (coins[0] if coins else "") or row.get("coin_id") or "unknown")
        core_id = str(row.get("core_opportunity_id") or (core_ids[0] if core_ids else "") or row.get("alert_id") or "unknown")
    state = str(row.get("delivery_state") or row.get("state") or "planned")
    mode = str(row.get("mode") or row.get("send_mode") or "")
    summary = row.get("channel_summary") if isinstance(row.get("channel_summary"), Mapping) else {}
    rendered = _int(row.get("rendered_candidate_count") or summary.get("rendered_candidate_count"))
    eligible = _int(row.get("eligible_candidate_count") or summary.get("eligible_candidate_count"))
    skipped = _int(row.get("skipped_candidate_count") or summary.get("skipped_candidate_count"))
    reason_counts = row.get("skipped_reason_counts") if isinstance(row.get("skipped_reason_counts"), Mapping) else summary.get("skipped_reason_counts") or summary.get("skip_reason_counts")
    family_summary = row.get("skipped_family_summary") if isinstance(row.get("skipped_family_summary"), list) else summary.get("skipped_family_summary")
    suffix = ""
    if eligible or rendered or skipped:
        suffix += f" candidates={rendered}/{eligible} rendered skipped={skipped}"
    if isinstance(reason_counts, Mapping) and reason_counts:
        suffix += f" skip_reasons={_format_count_map(reason_counts, limit=4)}"
    if isinstance(family_summary, list) and family_summary:
        families = []
        for family in family_summary[:3]:
            if not isinstance(family, Mapping):
                continue
            label = str(family.get("label") or family.get("candidate_family_id") or "unknown")
            count = _int(family.get("skipped_count"))
            families.append(f"{label}={count}")
        if families:
            suffix += f" skipped_families={', '.join(families)}"
            if len(family_summary) > len(families):
                suffix += f", +{len(family_summary) - len(families)} more"
    return (
        f"- {label}/{coin} core={core_id} "
        f"delivery={state} would_send={str(bool(row.get('would_send'))).lower()} "
        f"mode={mode or 'unknown'}{suffix}"
    )

def _format_count_map(counts: Mapping[str, Any], *, limit: int) -> str:
    items = sorted(
        ((str(key), _int(value)) for key, value in counts.items()),
        key=lambda item: (-item[1], item[0]),
    )
    shown = [f"{key}={value}" for key, value in items[:limit]]
    if len(items) > limit:
        shown.append(f"+{len(items) - limit} more")
    return ", ".join(shown) or "none"

def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0

__all__ = (
    '_compact',
    '_burn_in_readiness_lines',
    '_system_health_summary_lines',
    '_near_miss_daily_lines',
    '_near_miss_diagnostic_lines',
    '_dedupe_near_miss_candidates',
    '_decision_family_key',
    '_entry_family_key',
    '_dedupe_watchlist_entries',
    '_impact_family',
    '_near_miss_interest',
    '_near_miss_invalidation',
    '_card_groups_for_daily_brief',
    '_latest_notification_run',
    '_provider_health_lines',
    '_llm_budget_lines',
    '_new_since_last_run_lines',
    '_watchlist_hotter_lines',
    '_watchlist_identity_suffix',
    '_suppression_lines',
    '_core_alertable_count',
    '_field_counts',
    '_multi_field_counts',
    '_format_counts',
    '_brief_hypothesis_labels',
    '_brief_decisions',
    '_core_opportunity_lines',
    '_collapse_core_display_rows',
    '_core_display_rank',
    '_core_display_family_key',
    '_hide_core_from_default_display',
    '_research_review_delivery_rows',
    '_research_review_delivery_line',
    '_format_count_map',
    '_int',
)
