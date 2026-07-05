"""Research Review Selection for the legacy notification pipeline."""

from __future__ import annotations

from .runtime import *

def select_research_review_candidates(
    decisions: Iterable[event_alpha_router.EventAlphaRouteDecision],
    *,
    cfg: EventAlphaNotificationConfig,
    now: datetime | None = None,
    excluded_core_ids: Iterable[str] = (),
    core_row_by_alert_id: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[EventAlphaResearchReviewDigestItem, ...]:
    """Pick near-miss/local research candidates without making them alertable."""
    selected, _eligible_count, _skipped = select_research_review_candidates_with_diagnostics(
        decisions,
        cfg=cfg,
        now=now,
        excluded_core_ids=excluded_core_ids,
        core_row_by_alert_id=core_row_by_alert_id,
    )
    return selected

def _research_review_skipped_item(
    decision: event_alpha_router.EventAlphaRouteDecision,
    reason: str,
    *,
    core_index: Mapping[str, Mapping[str, Any]],
    detail: str | None = None,
    rank_score: float | None = None,
) -> EventAlphaResearchReviewSkippedItem:
    entry = decision.entry
    core = _core_row_for_decision(decision, core_index) or {}
    components = dict(getattr(entry, "latest_score_components", {}) or {})
    symbol = str(core.get("symbol") or core.get("validated_symbol") or entry.symbol or components.get("validated_symbol") or "UNKNOWN")
    coin_id = str(core.get("coin_id") or core.get("validated_coin_id") or entry.coin_id or components.get("validated_coin_id") or "unknown")
    core_id = _core_id_for_decision(decision, core_index)
    card_path = str(core.get("research_card_path") or core.get("card_path") or components.get("research_card_path") or "") or None
    return EventAlphaResearchReviewSkippedItem(
        symbol=symbol,
        coin_id=coin_id,
        core_opportunity_id=core_id,
        score=_research_review_score(decision),
        rank_score=float(rank_score if rank_score is not None else _research_review_score(decision)),
        skip_reason=reason,
        candidate_family_id=_research_review_family_id(
            symbol=symbol,
            coin_id=coin_id,
            core_opportunity_id=core_id,
            decision=decision,
            core=core,
        ),
        opportunity_type=str(core.get("opportunity_type") or components.get("opportunity_type") or "").strip() or None,
        final_opportunity_level=str(
            core.get("final_opportunity_level")
            or components.get("opportunity_level")
            or getattr(decision, "opportunity_level", "")
            or ""
        ).strip() or None,
        card_path=event_artifact_paths.artifact_display_path(card_path) if card_path else None,
        detail=detail,
    )

def select_research_review_candidates_with_diagnostics(
    decisions: Iterable[event_alpha_router.EventAlphaRouteDecision],
    *,
    cfg: EventAlphaNotificationConfig,
    now: datetime | None = None,
    excluded_core_ids: Iterable[str] = (),
    core_row_by_alert_id: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[
    tuple[EventAlphaResearchReviewDigestItem, ...],
    int,
    tuple[EventAlphaResearchReviewSkippedItem, ...],
]:
    """Pick research-review rows plus explicit non-rendered candidate reasons."""
    _ = now
    if not cfg.research_review_digest_enabled or cfg.research_review_digest_max_items <= 0:
        return (), 0, ()
    min_score = float(cfg.research_review_digest_min_score or 0.0)
    items: list[EventAlphaResearchReviewDigestItem] = []
    skipped: list[EventAlphaResearchReviewSkippedItem] = []
    excluded = {str(item).strip() for item in excluded_core_ids if str(item).strip()}
    core_index = core_row_by_alert_id or {}
    seen_core_ids: set[str] = set()

    def add_skipped(
        decision: event_alpha_router.EventAlphaRouteDecision,
        reason: str,
        *,
        detail: str | None = None,
        rank_score: float | None = None,
    ) -> None:
        skipped.append(_research_review_skipped_item(
            decision,
            reason,
            core_index=core_index,
            detail=detail,
            rank_score=rank_score,
        ))

    for decision in decisions:
        if bool(getattr(decision, "alertable", False)) or event_alpha_router.alertable_after_quality_gate(decision):
            continue
        core_id = _core_id_for_decision(decision, core_index)
        core = _core_row_for_decision(decision, core_index) or {}
        if core_id and (core_id in excluded or core_id in seen_core_ids):
            add_skipped(decision, "already_represented" if core_id in excluded else "duplicate_family")
            continue
        if _core_row_is_research_alertable(core):
            add_skipped(decision, "already_represented", detail="core opportunity already has a promoted route")
            continue
        entry = decision.entry
        components = dict(getattr(entry, "latest_score_components", {}) or {})
        symbol = str(getattr(entry, "symbol", "") or components.get("validated_symbol") or "").strip()
        coin_id = str(getattr(entry, "coin_id", "") or components.get("validated_coin_id") or "").strip()
        if not symbol or not coin_id:
            add_skipped(decision, "hard_gated", detail="missing validated asset identity")
            continue
        if _research_review_is_sector(symbol, coin_id) and not cfg.research_review_digest_include_sector:
            add_skipped(decision, "hard_gated", detail="sector-only candidate excluded from review digest")
            continue
        level = _research_review_level(decision)
        if level == "local_only" and not cfg.research_review_digest_include_local_only:
            add_skipped(decision, "quality_blocked", detail="local-only candidates are hidden by digest config")
            continue
        if level not in {"exploratory", "local_only"}:
            add_skipped(decision, "quality_blocked", detail=f"level={level or 'unknown'}")
            continue
        score = _research_review_score(decision)
        if score < min_score:
            add_skipped(decision, "lower_rank", detail=f"score below min {min_score:g}")
            continue
        hard_gate = _research_review_hard_gate_reason(decision)
        if hard_gate:
            add_skipped(decision, "hard_gated", detail=hard_gate)
            continue
        rank, why = _research_review_rank(entry, components, score)
        why_not = _research_review_not_alertable_reasons(decision, components)
        upgrade = _research_review_upgrade_steps(entry, decision, components)
        items.append(
            EventAlphaResearchReviewDigestItem(
                decision=decision,
                rank_score=rank,
                why_included=tuple(why),
                why_not_alertable=tuple(why_not),
                what_would_upgrade=tuple(upgrade),
            )
        )
        if core_id:
            seen_core_ids.add(core_id)
    items.sort(
        key=lambda item: (
            item.rank_score,
            _research_review_score(item.decision),
            item.decision.entry.last_seen_at,
            item.decision.entry.symbol,
        ),
        reverse=True,
    )
    max_items = max(0, int(cfg.research_review_digest_max_items or 0))
    selected = tuple(items[:max_items])
    for item in items[max_items:]:
        skipped.append(_research_review_skipped_item(
            item.decision,
            "max_items",
            core_index=core_index,
            rank_score=item.rank_score,
            detail=f"ranked below top {max_items}",
        ))
    return selected, len(items), tuple(skipped)

def format_research_review_telegram_digest(
    items: Iterable[EventAlphaResearchReviewDigestItem],
    *,
    profile: str | None = None,
    card_path_by_alert_id: Mapping[str, str | Path] | None = None,
    core_row_by_alert_id: Mapping[str, Mapping[str, Any]] | None = None,
    cfg: EventAlphaNotificationConfig | None = None,
    eligible_count: int | None = None,
    skipped_items: Iterable[EventAlphaResearchReviewSkippedItem] = (),
) -> str:
    """Render near-miss research-review candidates for Telegram burn-in."""
    cfg = cfg or EventAlphaNotificationConfig()
    _ = cfg  # Kept for API compatibility; all review items are rendered.
    keep = list(items)
    skipped = list(skipped_items)
    lines = [
        "<b>Event Alpha Research Review</b>",
        "<i>Not alertable. Missing confirmation. Not a trade signal.</i>",
        f"Profile: {_esc(profile or 'unknown')}",
        f"Items: {len(keep)}",
        f"Eligible candidates: {int(eligible_count if eligible_count is not None else len(keep))}",
        f"Skipped candidates: {len(skipped)}",
    ]
    if not keep:
        lines.append("No research-review candidates.")
        return "\n".join(lines)
    displayed = 0
    for item in keep:
        decision = item.decision
        entry = decision.entry
        core = _core_row_for_decision(decision, core_row_by_alert_id or {}) or {}
        level = _human_level(_research_review_level(decision))
        score = _research_review_score(decision)
        card_label = _telegram_card_basename(decision, card_path_by_alert_id, core=core)
        feedback_target = _telegram_feedback_target(decision, core=core)
        symbol = str(core.get("symbol") or core.get("validated_symbol") or entry.symbol or "UNKNOWN")
        coin_id = str(core.get("coin_id") or core.get("validated_coin_id") or entry.coin_id or "unknown")
        lane = str(core.get("opportunity_type") or "UNCONFIRMED_RESEARCH")
        market_state = str(core.get("market_state_class") or core.get("market_state") or "unknown")
        block = [
            "",
            f"{displayed + 1}. <b>{_esc(symbol)} / {_esc(coin_id)}</b>",
            f"   Level: {_esc(level)} · Score: {_esc(f'{score:g}')}",
            f"   Opportunity: {_esc(_human_reason(lane))} · Market: {_esc(_human_reason(market_state))}",
            f"   Catalyst: {_esc(_candidate_catalyst_text(entry))}",
            f"   Impact path: {_esc(_human_playbook(entry.impact_path_type or entry.latest_effective_playbook_type or entry.latest_playbook_type or entry.relationship_type))}",
            f"   Why surfaced: {_esc(_human_why(item.why_included))}",
            f"   Why not alertable: {_esc(_human_why_not_alertable(item.why_not_alertable))}",
            f"   What would upgrade: {_esc(_human_check_next(item.what_would_upgrade))}",
            f"   Card: {_esc(card_label)}",
            f"   Feedback target: {_esc(feedback_target)}",
        ]
        lines.extend(block)
        displayed += 1
    lines.append("")
    if skipped:
        family_summary = _research_review_skipped_display_family_summary(skipped)
        lines.append("<b>Skipped candidate families</b>")
        family_display = _research_review_skipped_family_display(family_summary, limit=8)
        for family in family_display:
            lines.append(
                "- "
                f"{_esc(family['label'])}: {_esc(str(family['skipped_count']))} skipped · "
                f"reasons: {_esc(_format_counts(family.get('skip_reason_counts') or {}))}"
            )
        if len(family_summary) > len(family_display):
            lines.append(f"- +{len(family_summary) - len(family_display)} more skipped families in local artifacts/inbox.")
        lines.append("")
        lines.append("<b>Skipped raw sample</b>")
        sample = _diverse_skipped_sample(skipped, limit=5)
        for row in sample:
            label = f"{row.symbol} / {row.coin_id}"
            detail = f" · {row.detail}" if row.detail else ""
            lines.append(
                f"- {_esc(label)}: {_esc(row.skip_reason)}{_esc(detail)}"
            )
        if len(skipped) > len(sample):
            lines.append(f"- +{len(skipped) - len(sample)} more skipped candidates in local artifacts/inbox.")
        lines.append("")
    lines.append("Research cards and feedback commands are available in local artifacts/inbox.")
    return "\n".join(lines)

def _research_review_channel_summary(plan: EventAlphaNotificationPlan) -> dict[str, Any]:
    reason_counts: dict[str, int] = {}
    for item in plan.research_review_skipped_items:
        reason = str(item.skip_reason or "unknown")
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
    candidate_family_summary = _research_review_skipped_family_summary(plan.research_review_skipped_items)
    display_family_summary = _research_review_skipped_display_family_summary(plan.research_review_skipped_items)
    sample = _diverse_skipped_sample(plan.research_review_skipped_items, limit=20)
    rendered = len(plan.research_review_items)
    rendered_decisions = [item.decision for item in plan.research_review_items]
    rendered_candidate_ids = [
        decision.alert_id
        for decision in rendered_decisions
        if str(decision.alert_id or "").strip()
    ]
    rendered_core_ids = [
        core_id
        for decision in rendered_decisions
        for core_id in (_core_id_for_decision(decision, plan.core_row_by_alert_id),)
        if str(core_id or "").strip()
    ]
    return {
        "rendered_candidate_count": rendered,
        "eligible_candidate_count": int(plan.research_review_eligible_count or 0),
        "skipped_candidate_count": len(plan.research_review_skipped_items),
        "skip_reason_counts": dict(sorted(reason_counts.items())),
        "skipped_reason_counts": dict(sorted(reason_counts.items())),
        "skipped_candidates": [item.to_dict() for item in sample],
        "skipped_candidates_sample": [item.to_dict() for item in sample],
        "skipped_family_summary": display_family_summary,
        "skipped_display_family_summary": display_family_summary,
        "skipped_candidate_family_summary": candidate_family_summary,
        "skipped_family_count": len(display_family_summary),
        "skipped_candidate_family_count": len(candidate_family_summary),
        "selection_policy": "rank by research-review score, source quality, market confirmation, and recency; render top max_items",
        "max_items": rendered,
        "ranking_policy": "rank_score_desc_then_score_recency_symbol",
        "cooldown_policy": "research_review_digest lane cooldown",
        "rendered_candidate_ids": list(dict.fromkeys(rendered_candidate_ids)),
        "rendered_core_opportunity_ids": list(dict.fromkeys(rendered_core_ids)),
    }

def _research_review_skipped_family_summary(
    skipped_items: Iterable[EventAlphaResearchReviewSkippedItem],
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for item in skipped_items:
        family_id = item.candidate_family_id or item.core_opportunity_id or item.coin_id or item.symbol or "unknown"
        row = grouped.setdefault(
            family_id,
            {
                "candidate_family_id": family_id,
                "symbol": item.symbol,
                "coin_id": item.coin_id,
                "label": f"{item.symbol}/{item.coin_id}",
                "skipped_count": 0,
                "skip_reason_counts": {},
                "max_score": item.score,
                "sample_core_opportunity_ids": [],
            },
        )
        row["skipped_count"] = int(row["skipped_count"]) + 1
        reasons = row["skip_reason_counts"]
        reasons[item.skip_reason] = int(reasons.get(item.skip_reason, 0)) + 1
        row["max_score"] = max(float(row.get("max_score") or 0.0), float(item.score or 0.0))
        if item.core_opportunity_id and item.core_opportunity_id not in row["sample_core_opportunity_ids"]:
            row["sample_core_opportunity_ids"].append(item.core_opportunity_id)
    return sorted(
        grouped.values(),
        key=lambda row: (int(row.get("skipped_count") or 0), float(row.get("max_score") or 0.0), str(row.get("label") or "")),
        reverse=True,
    )

def _research_review_skipped_display_family_summary(
    skipped_items: Iterable[EventAlphaResearchReviewSkippedItem],
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for item in skipped_items:
        symbol = _norm_display_part(item.symbol)
        coin_id = _norm_display_part(item.coin_id)
        key = f"{symbol}|{coin_id}"
        label = f"{item.symbol}/{item.coin_id}"
        row = grouped.setdefault(
            key,
            {
                "display_family_id": key,
                "symbol": item.symbol,
                "coin_id": item.coin_id,
                "label": label,
                "broad_opportunity_family": _broad_opportunity_family(item),
                "skipped_count": 0,
                "skip_reason_counts": {},
                "max_score": item.score,
                "sample_core_opportunity_ids": [],
                "candidate_family_ids": [],
                "representative_card_path": item.card_path,
                "display_hidden": _display_family_hidden(item),
            },
        )
        row["skipped_count"] = int(row["skipped_count"]) + 1
        reasons = row["skip_reason_counts"]
        reasons[item.skip_reason] = int(reasons.get(item.skip_reason, 0)) + 1
        row["max_score"] = max(float(row.get("max_score") or 0.0), float(item.score or 0.0))
        if item.core_opportunity_id and item.core_opportunity_id not in row["sample_core_opportunity_ids"]:
            row["sample_core_opportunity_ids"].append(item.core_opportunity_id)
        if item.candidate_family_id and item.candidate_family_id not in row["candidate_family_ids"]:
            row["candidate_family_ids"].append(item.candidate_family_id)
        if not row.get("representative_card_path") and item.card_path:
            row["representative_card_path"] = item.card_path
        row["display_hidden"] = bool(row.get("display_hidden")) or _display_family_hidden(item)
    return sorted(
        grouped.values(),
        key=lambda row: (
            not bool(row.get("display_hidden")),
            int(row.get("skipped_count") or 0),
            float(row.get("max_score") or 0.0),
            str(row.get("label") or ""),
        ),
        reverse=True,
    )

def _norm_display_part(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "unknown").strip().casefold()).strip("-") or "unknown"

def _broad_opportunity_family(item: EventAlphaResearchReviewSkippedItem) -> str:
    for value in (item.opportunity_type, item.final_opportunity_level):
        text = str(value or "").strip()
        if text:
            return text
    family = str(item.candidate_family_id or "").strip()
    if ":" in family:
        return family.split(":", 1)[0]
    return family or "unknown"

def _display_family_hidden(item: EventAlphaResearchReviewSkippedItem) -> bool:
    symbol = str(item.symbol or "").casefold()
    coin_id = str(item.coin_id or "").casefold()
    family = " ".join(str(value or "").casefold() for value in (item.opportunity_type, item.final_opportunity_level, item.candidate_family_id, item.skip_reason))
    return symbol == "sector" or coin_id == "diagnostic" or "diagnostic" in family or "sector" in family

def _research_review_skipped_family_display(
    family_summary: Iterable[Mapping[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    """Return family-first display rows while preserving high-score small families."""

    rows = [dict(row) for row in family_summary]
    if limit <= 0:
        return []
    by_count = sorted(
        rows,
        key=lambda row: (
            int(row.get("skipped_count") or 0),
            float(row.get("max_score") or 0.0),
            str(row.get("label") or ""),
        ),
        reverse=True,
    )
    by_score = sorted(
        rows,
        key=lambda row: (
            float(row.get("max_score") or 0.0),
            int(row.get("skipped_count") or 0),
            str(row.get("label") or ""),
        ),
        reverse=True,
    )
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(row: Mapping[str, Any]) -> None:
        if bool(row.get("display_hidden")):
            return
        key = str(row.get("display_family_id") or row.get("candidate_family_id") or row.get("label") or "").strip()
        if not key or key in seen or len(selected) >= limit:
            return
        selected.append(dict(row))
        seen.add(key)

    for row in by_count[: max(1, limit // 2)]:
        add(row)
    for row in by_score:
        add(row)
    for row in by_count:
        add(row)
    return selected

def _format_counts(values: Mapping[str, Any]) -> str:
    items = sorted(
        ((str(key), int(value or 0)) for key, value in values.items()),
        key=lambda item: (-item[1], item[0]),
    )
    return ", ".join(f"{key}={value}" for key, value in items) or "none"

def _diverse_skipped_sample(
    skipped_items: Iterable[EventAlphaResearchReviewSkippedItem],
    *,
    limit: int,
) -> list[EventAlphaResearchReviewSkippedItem]:
    out: list[EventAlphaResearchReviewSkippedItem] = []
    seen: set[str] = set()
    materialized = list(skipped_items)
    for item in materialized:
        family_id = item.candidate_family_id or item.core_opportunity_id or item.coin_id or item.symbol or "unknown"
        if family_id in seen:
            continue
        out.append(item)
        seen.add(family_id)
        if len(out) >= limit:
            return out
    for item in materialized:
        if item not in out:
            out.append(item)
        if len(out) >= limit:
            return out
    return out

__all__ = (
    'select_research_review_candidates',
    'select_research_review_candidates_with_diagnostics',
    'format_research_review_telegram_digest',
    '_research_review_channel_summary',
    '_research_review_skipped_family_summary',
    '_research_review_skipped_display_family_summary',
    '_norm_display_part',
    '_broad_opportunity_family',
    '_display_family_hidden',
    '_research_review_skipped_family_display',
    '_format_counts',
    '_diverse_skipped_sample',
)
