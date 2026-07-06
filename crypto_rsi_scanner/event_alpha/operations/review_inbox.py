"""Daily Event Alpha review inbox for burn-in labels."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..artifacts import research_cards
from . import common


INBOX_JSON = "event_alpha_daily_review_inbox.json"
INBOX_MD = "event_alpha_daily_review_inbox.md"


@dataclass(frozen=True)
class ReviewItem:
    family: str
    visible_family_key: str
    candidate_family_id: str
    core_family_ids: tuple[str, ...]
    duplicate_visible_family_count: int
    visible_family_rank: int
    selection_bucket: str
    collapsed_family_representative_reason: str
    symbol: str
    coin_id: str
    opportunity_type: str
    score: int
    source_origin: str
    source_pack: str
    evidence_status: str
    market_state: str
    why_not_alertable: str
    what_confirms: str
    what_invalidates: str
    card_path: str
    feedback_target: str
    suggested_feedback_commands: tuple[str, ...]
    provider_gap: str | None = None
    review_value_score: int = 0
    review_value_reasons: tuple[str, ...] = ()
    family_rank: int = 0
    diversity_bucket: str = "general"
    selection_reason: str = ""


def build_review_inbox(
    *,
    profile: str,
    artifact_namespace: str,
    base_dir: str | Path | None = None,
    limit: int = 10,
    now: datetime | None = None,
) -> dict[str, Any]:
    context = common.context_for(profile=profile, artifact_namespace=artifact_namespace, base_dir=base_dir)
    rows = _candidate_rows(context)
    card_index = _card_index(context)
    grouped = _group_rows(rows)
    all_items = [
        _item_from_group(family, family_rows, card_index=card_index, profile=profile)
        for family, family_rows in grouped
    ]
    items = _select_review_items(all_items, limit=max(1, int(limit or 10)))
    stale_paths = _stale_path_warnings(items)
    payload = common.with_safety(
        {
            "schema_version": "event_alpha_daily_review_inbox_v1",
            "row_type": "event_alpha_daily_review_inbox",
            "generated_at": (now or common.utc_now()).isoformat(),
            "profile": profile,
            "artifact_namespace": artifact_namespace,
            "namespace_dir": common.rel_path(context.namespace_dir),
            "review_time_budget_minutes": 10,
            "family_grouped": True,
            "visible_family_grouped": True,
            "items_count": len(items),
            "items": [item.__dict__ for item in items],
            "family_summaries": _family_summaries(all_items),
            "stale_path_warnings": stale_paths,
            "blockers": [
                f"stale_or_missing_review_path:{path}"
                for path in stale_paths
                if path.startswith("/tmp/") or path.startswith("missing:")
            ],
        }
    )
    common.write_json(context.namespace_dir / INBOX_JSON, payload)
    common.write_text(context.namespace_dir / INBOX_MD, format_review_inbox(payload))
    return payload


def format_review_inbox(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Event Alpha Daily Review Inbox",
        "",
        "Research-only burn-in inbox. Labels append to feedback artifacts only; candidate/core/card rows are not mutated.",
        "",
        f"- generated_at: `{payload.get('generated_at')}`",
        f"- profile: `{payload.get('profile')}`",
        f"- artifact_namespace: `{payload.get('artifact_namespace')}`",
        f"- items_count: `{payload.get('items_count')}`",
        f"- family_grouped: `{payload.get('family_grouped')}`",
        f"- visible_family_grouped: `{payload.get('visible_family_grouped')}`",
        "",
    ]
    blockers = payload.get("blockers") or []
    if blockers:
        lines.extend(["## Blockers", ""])
        lines.extend(f"- {item}" for item in blockers)
        lines.append("")
    summaries = payload.get("family_summaries") or []
    if summaries:
        lines.extend(["## Visible Family Summary", ""])
        for row in summaries:
            if isinstance(row, Mapping):
                lines.append(
                    f"- {row.get('visible_family_key')}: {row.get('duplicate_visible_family_count')} candidate rows collapsed; "
                    f"representative=`{row.get('feedback_target')}` reason=`{row.get('collapsed_family_representative_reason')}`"
                )
        lines.append("")
    lines.extend(["## Review Items", ""])
    for index, row in enumerate(payload.get("items", []) or [], start=1):
        if not isinstance(row, Mapping):
            continue
        lines.extend(
            [
                f"### {index}. {row.get('symbol') or 'UNKNOWN'} / {row.get('coin_id') or 'unknown'}",
                f"- family: `{row.get('family')}`",
                f"- visible_family_key: `{row.get('visible_family_key')}`",
                f"- duplicate_visible_family_count: `{row.get('duplicate_visible_family_count')}`",
                f"- visible_family_rank: `{row.get('visible_family_rank')}`",
                f"- selection_bucket: `{row.get('selection_bucket')}`",
                f"- opportunity_type: `{row.get('opportunity_type')}`",
                f"- score: `{row.get('score')}`",
                f"- Review value: `{row.get('review_value_score')}` ({', '.join(row.get('review_value_reasons') or []) or 'general review'})",
                f"- selection_reason: `{row.get('selection_reason')}`",
                f"- diversity_bucket: `{row.get('diversity_bucket')}`",
                f"- source_origin/source_pack: `{row.get('source_origin')}` / `{row.get('source_pack')}`",
                f"- evidence_status: `{row.get('evidence_status')}`",
                f"- market_state: `{row.get('market_state')}`",
                f"- why_not_alertable: {row.get('why_not_alertable')}",
                f"- what_confirms: {row.get('what_confirms')}",
                f"- what_invalidates: {row.get('what_invalidates')}",
                f"- card_path: `{row.get('card_path') or 'none'}`",
                f"- feedback_target: `{row.get('feedback_target')}`",
                "- suggested_feedback_commands:",
            ]
        )
        for command in row.get("suggested_feedback_commands") or []:
            lines.append(f"  - `{command}`")
        if row.get("provider_gap"):
            lines.append(f"- provider_gap: {row.get('provider_gap')}")
        lines.append("")
    lines.extend(
        [
            "## Safety",
            "",
            f"- telegram_sends: `{payload.get('telegram_sends')}`",
            f"- trades_created: `{payload.get('trades_created')}`",
            f"- paper_trades_created: `{payload.get('paper_trades_created')}`",
            f"- normal_rsi_signal_rows_written: `{payload.get('normal_rsi_signal_rows_written')}`",
            f"- triggered_fade_created: `{payload.get('triggered_fade_created')}`",
        ]
    )
    return "\n".join(lines).rstrip()


def _candidate_rows(context: Any) -> list[dict[str, Any]]:
    filenames = (
        "event_integrated_radar_candidates.jsonl",
        "event_core_opportunities.jsonl",
        "event_alpha_alerts.jsonl",
        "event_market_anomalies.jsonl",
        "event_fade_short_review_candidates.jsonl",
    )
    rows: list[dict[str, Any]] = []
    for filename in filenames:
        for row in common.read_jsonl(context.namespace_dir / filename):
            row.setdefault("_source_file", filename)
            rows.append(row)
    return rows


def _card_index(context: Any) -> dict[str, Path]:
    cards: dict[str, Path] = {}
    for path in Path(context.research_cards_dir).glob("*.md"):
        if path.name == "index.md":
            continue
        target = research_cards.card_feedback_target(path)
        core_id = research_cards.card_core_opportunity_id(path)
        for key in (target, core_id, path.stem):
            if key:
                cards[str(key)] = path
    return cards


def _group_rows(rows: Iterable[Mapping[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        family = _visible_family_key(row)
        groups.setdefault(family, []).append(dict(row))
    return sorted(groups.items(), key=lambda item: (-max(common.row_score(row) for row in item[1]), item[0]))


def _visible_family_key(row: Mapping[str, Any]) -> str:
    canonical = str(row.get("canonical_asset_id") or "").strip()
    if _canonical_asset_id_reliable(canonical):
        return canonical
    symbol = str(row.get("symbol") or row.get("asset_symbol") or row.get("base_symbol") or "").strip().upper() or "UNKNOWN"
    coin_id = str(row.get("coin_id") or row.get("asset_coin_id") or "").strip().casefold() or "unknown"
    return f"{symbol}:{coin_id}:{_broad_family(row)}"


def _canonical_asset_id_reliable(value: str) -> bool:
    lowered = value.casefold()
    return bool(value and lowered not in {"unknown", "none", "null"} and not lowered.startswith(("core:", "ea:", "candidate:")))


def _broad_family(row: Mapping[str, Any]) -> str:
    lane = common.row_lane(row).casefold()
    source = " ".join(
        str(row.get(field) or "")
        for field in ("source_pack", "source_pack_id", "source_origin", "source_provider", "provider", "_source_file")
    ).casefold()
    if "official" in source or "binance" in source or "bybit" in source:
        source_family = "official_exchange"
    elif "unlock" in source or "calendar" in source:
        source_family = "structured_catalyst"
    elif "coinalyze" in source or "derivative" in source or "funding" in source:
        source_family = "derivatives"
    elif "market_anomal" in source or row.get("_source_file") == "event_market_anomalies.jsonl":
        source_family = "market_anomaly"
    elif "rss" in source or "gdelt" in source or "cryptopanic" in source or "news" in source:
        source_family = "context"
    else:
        source_family = "general"
    return f"{lane}:{source_family}"


def _representative_sort_key(row: Mapping[str, Any], *, card_index: Mapping[str, Path]) -> tuple[int, int, int, int, float, int, int]:
    accepted = max(common.int_value(row.get("accepted_evidence_count")), 1 if row.get("accepted_evidence") else 0)
    evidence_rank = _evidence_rank(str(row.get("evidence_status") or row.get("final_evidence_status") or row.get("source_status") or ""))
    market_strength = _market_strength(row)
    source_quality = _source_quality(row)
    parsed_time = common.timestamp_for_row(row)
    freshness = parsed_time.timestamp() if parsed_time is not None else 0.0
    target = _feedback_target(row, common.item_family(row))
    has_card = 1 if _card_for(row, target, card_index) else 0
    return (accepted, evidence_rank, market_strength, source_quality, freshness, common.row_score(row), has_card)


def _representative_reason(best: Mapping[str, Any], rows: list[dict[str, Any]]) -> str:
    parts = [f"selected from {len(rows)} visible-family rows"]
    if common.int_value(best.get("accepted_evidence_count")) > 0 or best.get("accepted_evidence"):
        parts.append("accepted evidence")
    if _market_strength(best) > 0:
        parts.append("stronger market/anomaly context")
    if _source_quality(best) > 0:
        parts.append("higher source quality")
    if common.row_score(best) > 0:
        parts.append(f"score {common.row_score(best)}")
    return "; ".join(parts)


def _family_summaries(items: Iterable[ReviewItem]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in sorted(items, key=lambda value: (-value.duplicate_visible_family_count, value.visible_family_key)):
        rows.append(
            {
                "visible_family_key": item.visible_family_key,
                "symbol": item.symbol,
                "coin_id": item.coin_id,
                "duplicate_visible_family_count": item.duplicate_visible_family_count,
                "feedback_target": item.feedback_target,
                "core_family_ids": list(item.core_family_ids),
                "collapsed_family_representative_reason": item.collapsed_family_representative_reason,
            }
        )
    return rows


def _item_from_group(
    family: str,
    rows: list[dict[str, Any]],
    *,
    card_index: Mapping[str, Path],
    profile: str,
) -> ReviewItem:
    best = max(rows, key=lambda row: _representative_sort_key(row, card_index=card_index))
    candidate_family_id = common.item_family(best)
    core_family_ids = tuple(sorted(dict.fromkeys(str(common.item_family(row)) for row in rows if common.item_family(row))))
    target = _feedback_target(best, family)
    card = _card_for(best, target, card_index)
    opportunity_type = common.row_lane(best)
    score = common.row_score(best)
    symbol = str(best.get("symbol") or best.get("asset_symbol") or best.get("base_symbol") or "UNKNOWN")
    coin_id = str(best.get("coin_id") or best.get("asset_coin_id") or best.get("canonical_asset_id") or "unknown")
    source_pack = str(best.get("source_pack") or best.get("source_pack_id") or best.get("source_class") or "unknown")
    source_origin = str(best.get("source_origin") or best.get("provider") or best.get("source_provider") or best.get("_source_file") or "unknown")
    evidence_status = str(best.get("evidence_status") or best.get("final_evidence_status") or best.get("source_status") or "needs_review")
    market_state = str(best.get("market_state_class") or best.get("market_state") or best.get("market_context_freshness_status") or "unknown")
    why = _why_not_alertable(best, opportunity_type)
    confirms = str(best.get("what_confirms") or best.get("confirm_if") or _default_confirm(opportunity_type))
    invalidates = str(best.get("what_invalidates") or best.get("invalidate_if") or _default_invalidate(opportunity_type))
    card_path = common.rel_path(card) if card else ""
    value_score, value_reasons, bucket = _review_value(best, opportunity_type, score, source_origin, source_pack, evidence_status, market_state, why, has_card=bool(card_path))
    return ReviewItem(
        family=family,
        visible_family_key=family,
        candidate_family_id=candidate_family_id,
        core_family_ids=core_family_ids,
        duplicate_visible_family_count=len(rows),
        visible_family_rank=0,
        selection_bucket=bucket,
        collapsed_family_representative_reason=_representative_reason(best, rows),
        symbol=symbol,
        coin_id=coin_id,
        opportunity_type=opportunity_type,
        score=score,
        source_origin=source_origin,
        source_pack=source_pack,
        evidence_status=evidence_status,
        market_state=market_state,
        why_not_alertable=why,
        what_confirms=confirms,
        what_invalidates=invalidates,
        card_path=card_path,
        feedback_target=target,
        suggested_feedback_commands=_feedback_commands(profile, target),
        provider_gap=_provider_gap(best),
        review_value_score=value_score,
        review_value_reasons=tuple(value_reasons),
        diversity_bucket=bucket,
    )


def _feedback_target(row: Mapping[str, Any], family: str) -> str:
    target = str(
        row.get("feedback_target")
        or row.get("core_opportunity_id")
        or row.get("alert_key")
        or row.get("candidate_id")
        or row.get("id")
        or family
    )
    return target if target.startswith("ea:") else f"ea:{target}"


def _card_for(row: Mapping[str, Any], target: str, card_index: Mapping[str, Path]) -> Path | None:
    for key in (
        target,
        target[3:] if target.startswith("ea:") else target,
        str(row.get("core_opportunity_id") or ""),
        str(row.get("card_id") or ""),
    ):
        if key in card_index:
            return card_index[key]
    raw = row.get("card_path")
    if raw:
        path = Path(str(raw)).expanduser()
        return path
    return None


def _why_not_alertable(row: Mapping[str, Any], lane: str) -> str:
    return str(
        row.get("why_not_alertable")
        or row.get("quality_gate_reason")
        or row.get("rejected_reason")
        or row.get("skip_reason")
        or ("needs confirmation/source review" if lane in {"UNCONFIRMED_RESEARCH", "STORE_ONLY"} else "review for usefulness")
    )


def _default_confirm(lane: str) -> str:
    if lane == "FADE_SHORT_REVIEW":
        return "fresh crowding/exhaustion evidence plus completed move"
    if lane == "RISK_ONLY":
        return "structured risk evidence with timestamp and materiality"
    if lane == "UNCONFIRMED_RESEARCH":
        return "official/structured source or accepted evidence acquisition result"
    return "fresh source evidence, market sanity, and resolver confidence"


def _default_invalidate(lane: str) -> str:
    if lane == "FADE_SHORT_REVIEW":
        return "stale derivatives, no crowding evidence, or continued squeeze"
    if lane == "RISK_ONLY":
        return "missing source time/materiality or risk reframed as long opportunity"
    return "source noise, duplicate, stale market move, or missing confirmation"


def _provider_gap(row: Mapping[str, Any]) -> str | None:
    for field in ("provider_gap", "source_gap", "provider_not_used_reason", "cryptopanic_not_used_reason"):
        value = row.get(field)
        if value:
            return str(value)
    return None


def _feedback_commands(profile: str, target: str) -> tuple[str, ...]:
    labels = (
        "useful",
        "junk",
        "watch",
        "late",
        "source-noise",
        "needs-confirmation",
        "duplicate",
        "promising-source-type",
    )
    return tuple(
        f"make event-feedback-{label} PROFILE={profile} FEEDBACK_TARGET='{target}'"
        for label in labels
    )


def _select_review_items(items: list[ReviewItem], *, limit: int) -> list[ReviewItem]:
    ranked = sorted(items, key=lambda item: (-_priority(item), -item.score, item.visible_family_key))
    selected: list[ReviewItem] = []
    selected_families: set[str] = set()
    desired_buckets = (
        "accepted_evidence_no_market_confirmation",
        "market_anomaly_missing_catalyst",
        "source_only_narrative",
    )
    for bucket in desired_buckets:
        candidate = next((item for item in ranked if item.diversity_bucket == bucket and item.visible_family_key not in selected_families), None)
        if candidate and len(selected) < limit:
            selected.append(candidate)
            selected_families.add(candidate.visible_family_key)
    for item in ranked:
        if len(selected) >= limit:
            break
        if item.visible_family_key in selected_families:
            continue
        selected.append(item)
        selected_families.add(item.visible_family_key)
    ordered = sorted(selected, key=lambda item: (-_priority(item), -item.score, item.visible_family_key))
    return [
        replace(
            item,
            family_rank=index,
            visible_family_rank=index,
            selection_bucket=item.diversity_bucket,
            selection_reason=_selection_reason(item, index),
        )
        for index, item in enumerate(ordered, start=1)
    ]


def _priority(item: ReviewItem) -> int:
    return item.review_value_score


def _evidence_rank(value: str) -> int:
    lowered = value.casefold()
    if "accepted" in lowered:
        return 3
    if "confirmed" in lowered or "structured" in lowered:
        return 2
    if "review" in lowered:
        return 1
    return 0


def _market_strength(row: Mapping[str, Any]) -> int:
    text = " ".join(str(row.get(field) or "") for field in ("market_state_class", "market_state", "market_confirmation_level", "why_not_alertable")).casefold()
    score = 0
    if any(token in text for token in ("breakout", "confirmed", "fresh", "strong")):
        score += 3
    if "anomaly" in text or row.get("_source_file") == "event_market_anomalies.jsonl":
        score += 2
    score += min(3, common.int_value(row.get("market_anomaly_strength")) // 25)
    return score


def _source_quality(row: Mapping[str, Any]) -> int:
    text = " ".join(str(row.get(field) or "") for field in ("source_pack", "source_pack_id", "source_origin", "source_provider", "provider")).casefold()
    score = min(4, common.int_value(row.get("source_strength")) // 25)
    if any(token in text for token in ("official", "bybit", "binance", "unlock", "calendar")):
        score += 3
    if "coinalyze" in text or "derivative" in text:
        score += 2
    if any(token in text for token in ("rss", "gdelt", "project_blog_rss")):
        score -= 1
    return score


def _legacy_priority(item: ReviewItem) -> int:
    base = item.score
    lane_bonus = {
        "FADE_SHORT_REVIEW": 30,
        "UNCONFIRMED_RESEARCH": 25,
        "RISK_ONLY": 20,
        "EARLY_LONG_RESEARCH": 18,
        "CONFIRMED_LONG_RESEARCH": 10,
    }.get(item.opportunity_type, 0)
    why = item.why_not_alertable.casefold()
    if "near" in why:
        lane_bonus += 12
    if "quality" in why or "cap" in why:
        lane_bonus += 10
    return base + lane_bonus


def _review_value(
    row: Mapping[str, Any],
    opportunity_type: str,
    score: int,
    source_origin: str,
    source_pack: str,
    evidence_status: str,
    market_state: str,
    why: str,
    *,
    has_card: bool,
) -> tuple[int, list[str], str]:
    value = _legacy_priority(
        ReviewItem(
            family="",
            visible_family_key="",
            candidate_family_id="",
            core_family_ids=(),
            duplicate_visible_family_count=1,
            visible_family_rank=0,
            selection_bucket="general",
            collapsed_family_representative_reason="",
            symbol="",
            coin_id="",
            opportunity_type=opportunity_type,
            score=score,
            source_origin=source_origin,
            source_pack=source_pack,
            evidence_status=evidence_status,
            market_state=market_state,
            why_not_alertable=why,
            what_confirms="",
            what_invalidates="",
            card_path="",
            feedback_target="",
            suggested_feedback_commands=(),
        )
    )
    reasons: list[str] = []
    bucket = "general"
    source_text = f"{source_origin} {source_pack}".casefold()
    market_text = f"{market_state} {why}".casefold()
    evidence_text = evidence_status.casefold()
    lane_text = opportunity_type.casefold()
    source_strength = max(common.int_value(row.get("source_strength")), common.int_value(row.get("source_strength_score")))
    if any(token in source_text for token in ("cryptopanic", "rss", "gdelt", "news", "context")) and "official" not in source_text:
        value += 8
        reasons.append("source_only_narrative")
        bucket = "source_only_narrative"
        if any(token in source_text for token in ("project_blog_rss", "rss", "gdelt")):
            value -= 12
            reasons.append("generic_context_source_downranked")
    if row.get("_source_file") == "event_market_anomalies.jsonl" or "anomaly" in market_text:
        value += 55
        reasons.append("market_anomaly_missing_catalyst")
        bucket = "market_anomaly_missing_catalyst"
    accepted = bool(row.get("accepted_evidence")) or common.int_value(row.get("accepted_evidence_count")) > 0 or "accepted" in evidence_text
    no_market = market_state.casefold() in {"unknown", "none", "missing", "unconfirmed"} or "no market" in market_text or "missing market" in market_text
    if accepted and no_market:
        value += 60
        reasons.append("accepted_evidence_no_market_confirmation")
        bucket = "accepted_evidence_no_market_confirmation"
    if any(token in source_text for token in ("official", "bybit", "binance", "unlock", "calendar")) and no_market:
        value += 50
        reasons.append("official_structured_missing_market_confirmation")
    if source_strength >= 70 and ("blocked" in market_text or no_market):
        value += 45
        reasons.append("high_source_strength_blocked_by_market")
    if "near" in why.casefold():
        value += 45
        reasons.append("near_gate")
    if "quality" in why.casefold() or "cap" in why.casefold():
        value += 10
        reasons.append("quality_capped")
    if row.get("skipped") is True or row.get("skip_reason") or "skip" in why.casefold():
        value += 40
        reasons.append("high_value_skipped_research_review")
    gap = _provider_gap(row)
    if gap and any(token in gap.casefold() for token in ("coinalyze", "official", "unlock", "exchange", "provider", "confirmation")):
        value += 35
        reasons.append("actionable_provider_source_gap")
    if opportunity_type == "FADE_SHORT_REVIEW":
        value += 20
        reasons.append("fade_review")
    if "diagnostic" in lane_text:
        value -= 35
        reasons.append("diagnostic_downranked")
    if not has_card:
        value -= 5
        reasons.append("no_card_downranked")
    if "unsupported" in why.casefold() or "insufficient" in why.casefold():
        value -= 25
        reasons.append("unsupported_mechanism_downranked")
    if not reasons:
        reasons.append("highest_remaining_review_value")
    return max(0, value), reasons, bucket


def _selection_reason(item: ReviewItem, rank: int) -> str:
    if item.diversity_bucket in {
        "source_only_narrative",
        "market_anomaly_missing_catalyst",
        "accepted_evidence_no_market_confirmation",
    }:
        return f"diversity_bucket:{item.diversity_bucket}"
    if rank == 1:
        return "top_review_value"
    return "next_highest_review_value"


def _stale_path_warnings(items: Iterable[ReviewItem]) -> list[str]:
    warnings: list[str] = []
    root = common.repo_root_from_module()
    for item in items:
        if not item.card_path:
            continue
        if item.card_path.startswith("/tmp/"):
            warnings.append(item.card_path)
            continue
        path = root / item.card_path if not Path(item.card_path).is_absolute() else Path(item.card_path)
        if not path.exists():
            warnings.append(f"missing:{item.card_path}")
    return warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write a compact Event Alpha daily review inbox.")
    parser.add_argument("--profile", default="notify_llm_deep")
    parser.add_argument("--artifact-namespace", default="notify_llm_deep_cryptopanic_rehearsal")
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(argv)
    payload = build_review_inbox(
        profile=args.profile,
        artifact_namespace=args.artifact_namespace,
        base_dir=args.base_dir,
        limit=args.limit,
    )
    print(f"event_alpha_daily_review_inbox: {payload['namespace_dir']}/{INBOX_MD}")
    print(f"items={payload['items_count']} blockers={len(payload.get('blockers') or [])}")
    print("Feedback labels append only; no candidate/core rows were mutated.")
    return 1 if payload.get("blockers") else 0


if __name__ == "__main__":
    raise SystemExit(main())
