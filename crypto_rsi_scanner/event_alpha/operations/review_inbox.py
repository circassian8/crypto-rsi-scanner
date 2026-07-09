"""Daily Event Alpha review inbox for burn-in labels."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..artifacts import paths as event_artifact_paths
from ..artifacts import research_cards
from . import common
from . import evidence_semantics


INBOX_JSON = "event_alpha_daily_review_inbox.json"
INBOX_MD = "event_alpha_daily_review_inbox.md"
SECONDARY_VISIBLE_FAMILY_MIN_SCORE = 80
HIGH_VALUE_SECONDARY_BUCKETS = {
    "accepted_evidence_no_market_confirmation",
    "near_gate",
    "market_anomaly_missing_catalyst",
    "official_structured_missing_market",
    "high_value_skipped_family",
    "provider_confirmation_gap",
    "source_pack_high_priority",
    "fresh_candidate",
}
HIGH_VALUE_REASON_CODES = HIGH_VALUE_SECONDARY_BUCKETS | {
    "accepted_evidence_found",
    "quality_capped",
    "fade_review",
    "lane_critical_provider_gap",
    "missing_strong_source_review",
    "missing_market_confirmation_review",
}


@dataclass(frozen=True)
class ReviewItem:
    family: str
    visible_family_key: str
    primary_visible_family_key: str
    secondary_visible_family_key: str
    candidate_family_id: str
    core_family_ids: tuple[str, ...]
    duplicate_visible_family_count: int
    symbol_duplicate_count: int
    collapsed_symbol_family_count: int
    visible_family_rank: int
    symbol_family_rank: int
    selection_bucket: str
    allowed_second_family_reason: str
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
    card_not_available_reason: str
    feedback_target: str
    suggested_feedback_commands: tuple[str, ...]
    candidate_record_type: str
    candidate_provenance: str
    contract_counted_candidate: bool
    source_artifact: str
    source_artifact_row_type: str
    real_candidate_evidence: bool
    diagnostic_only: bool
    fixture_only: bool
    preflight_only: bool
    provider_gap: str | None = None
    review_value_score: int = 0
    review_value_reasons: tuple[str, ...] = ()
    review_value_reason_codes: tuple[str, ...] = ()
    downrank_reason_codes: tuple[str, ...] = ()
    family_rank: int = 0
    diversity_bucket: str = "general"
    selection_reason: str = ""
    selected_representative_reason: str = ""


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
        _item_from_group(family, family_rows, card_index=card_index, profile=profile, context=context)
        for family, family_rows in grouped
    ]
    items = _select_review_items(all_items, limit=max(1, int(limit or 10)))
    stale_paths = _stale_path_warnings(items, context=context)
    selected_primary = {item.primary_visible_family_key for item in items}
    second_family_count = sum(1 for item in items if item.symbol_family_rank > 1)
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
            "selected_primary_family_count": len(selected_primary),
            "collapsed_primary_family_count": max(0, len({item.primary_visible_family_key for item in all_items}) - len(selected_primary)),
            "second_family_items_count": second_family_count,
            "rejected_second_family_items_count": _rejected_second_family_count(all_items, items),
            "items": [item.__dict__ for item in items],
            "family_summaries": _family_summaries(all_items),
            "collapsed_family_summary": _symbol_family_summaries(all_items),
            "stale_path_warnings": stale_paths,
            "blockers": [
                f"stale_or_missing_review_path:{path}"
                for path in stale_paths
                if path
            ],
        }
    )
    payload = event_artifact_paths.normalize_operator_path_fields(
        payload,
        repo_root=common.repo_root_from_module(),
        artifact_base=context.base_dir,
    )
    common.write_json(context.namespace_dir / INBOX_JSON, payload)
    common.write_text(
        context.namespace_dir / INBOX_MD,
        event_artifact_paths.scrub_absolute_paths_from_markdown(
            format_review_inbox(payload),
            base=context.base_dir,
        ),
    )
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
    collapsed = payload.get("collapsed_family_summary") or []
    if collapsed:
        lines.extend(["## Collapsed Family Summary", ""])
        for row in collapsed:
            if isinstance(row, Mapping):
                lines.append(
                    f"- {row.get('primary_visible_family_key')}: {row.get('collapsed_symbol_family_count')} visible families; "
                    f"selected=`{row.get('selected_feedback_targets')}`"
                )
        lines.append("")
    items = [row for row in payload.get("items", []) or [] if isinstance(row, Mapping)]
    contract_items = [row for row in items if row.get("contract_counted_candidate") is True]
    non_contract_items = [row for row in items if row.get("contract_counted_candidate") is not True]
    high_value_items = [
        row for row in non_contract_items
        if _is_high_value_non_contract_item(row)
    ]
    support_items = [row for row in non_contract_items if row not in high_value_items]
    lines.extend(["## Review Items", ""])
    lines.extend(["## Contract-Counted Burn-In Candidates", ""])
    if not contract_items:
        lines.append("- No contract-counted burn-in candidates yet. No real candidate evidence yet.")
        lines.append("")
    for index, row in enumerate(contract_items, start=1):
        _append_review_item_lines(lines, index, row)
    lines.extend(["## High-Value Review Candidates Not Contract-Counted", ""])
    if not high_value_items:
        lines.append("- No high-value non-contract review candidates selected.")
        lines.append("")
    for index, row in enumerate(high_value_items, start=len(contract_items) + 1):
        _append_review_item_lines(lines, index, row)
    lines.extend(["## Diagnostic / Support Items", ""])
    if not support_items:
        lines.append("- No diagnostic or support review items selected.")
        lines.append("")
    for index, row in enumerate(support_items, start=len(contract_items) + len(high_value_items) + 1):
        _append_review_item_lines(lines, index, row)
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


def _is_high_value_non_contract_item(row: Mapping[str, Any]) -> bool:
    if row.get("diagnostic_only") is True or row.get("preflight_only") is True:
        return False
    if int(row.get("review_value_score") or 0) >= 50:
        return True
    codes = {str(item) for item in row.get("review_value_reason_codes") or []}
    lane = str(row.get("opportunity_type") or "").upper()
    return bool(codes & HIGH_VALUE_REASON_CODES or lane in {"EARLY_LONG_RESEARCH", "CONFIRMED_LONG_RESEARCH", "FADE_SHORT_REVIEW", "RISK_ONLY", "UNCONFIRMED_RESEARCH"})


def _append_review_item_lines(lines: list[str], index: int, row: Mapping[str, Any]) -> None:
    if not isinstance(row, Mapping):
        return
    lines.extend(
        [
            f"### {index}. {row.get('symbol') or 'UNKNOWN'} / {row.get('coin_id') or 'unknown'}",
            f"- family: `{row.get('family')}`",
            f"- visible_family_key: `{row.get('visible_family_key')}`",
            f"- primary_visible_family_key: `{row.get('primary_visible_family_key')}`",
            f"- secondary_visible_family_key: `{row.get('secondary_visible_family_key')}`",
            f"- duplicate_visible_family_count: `{row.get('duplicate_visible_family_count')}`",
            f"- symbol_duplicate_count: `{row.get('symbol_duplicate_count')}`",
            f"- collapsed_symbol_family_count: `{row.get('collapsed_symbol_family_count')}`",
            f"- visible_family_rank: `{row.get('visible_family_rank')}`",
            f"- symbol_family_rank: `{row.get('symbol_family_rank')}`",
            f"- selection_bucket: `{row.get('selection_bucket')}`",
            f"- allowed_second_family_reason: `{row.get('allowed_second_family_reason') or 'none'}`",
            f"- Provenance: `{row.get('candidate_provenance')}` from `{row.get('source_artifact')}` row_type=`{row.get('source_artifact_row_type')}`",
            f"- Counts toward burn-in candidate evidence: `{row.get('contract_counted_candidate')}`",
            f"- opportunity_type: `{row.get('opportunity_type')}`",
            f"- score: `{row.get('score')}`",
            f"- Review value: `{row.get('review_value_score')}` ({', '.join(row.get('review_value_reason_codes') or []) or 'general review'})",
            f"- downrank_reason_codes: `{', '.join(row.get('downrank_reason_codes') or []) or 'none'}`",
            f"- selection_reason: `{row.get('selection_reason')}`",
            f"- Why this needs human review: {row.get('why_not_alertable')}",
            f"- selected_representative_reason: `{row.get('selected_representative_reason') or row.get('collapsed_family_representative_reason')}`",
            f"- diversity_bucket: `{row.get('diversity_bucket')}`",
            f"- source_origin/source_pack: `{row.get('source_origin')}` / `{row.get('source_pack')}`",
            f"- evidence_status: `{row.get('evidence_status')}`",
            f"- market_state: `{row.get('market_state')}`",
            f"- why_not_alertable: {row.get('why_not_alertable')}",
            f"- what_confirms: {row.get('what_confirms')}",
            f"- what_invalidates: {row.get('what_invalidates')}",
            f"- card_path: `{row.get('card_path') or 'none'}`",
            f"- card_not_available_reason: `{row.get('card_not_available_reason') or 'none'}`",
            f"- feedback_target: `{row.get('feedback_target')}`",
            "- suggested_feedback_commands:",
        ]
    )
    for command in row.get("suggested_feedback_commands") or []:
        lines.append(f"  - `{command}`")
    if row.get("provider_gap"):
        lines.append(f"- provider_gap: {row.get('provider_gap')}")
    lines.append("")


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
            provenance = evidence_semantics.row_provenance(row)
            row.update(provenance)
            if provenance["diagnostic_only"] or provenance["preflight_only"]:
                continue
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


def _primary_visible_family_key(row: Mapping[str, Any]) -> str:
    symbol = str(row.get("symbol") or row.get("asset_symbol") or row.get("base_symbol") or "").strip().upper() or "UNKNOWN"
    coin_id = str(row.get("coin_id") or row.get("asset_coin_id") or "").strip().casefold() or "unknown"
    return f"{symbol}:{coin_id}"


def _secondary_visible_family_key(row: Mapping[str, Any], opportunity_type: str, bucket: str) -> str:
    return f"{_primary_visible_family_key(row)}:{opportunity_type.casefold()}:{bucket}"


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
                "primary_visible_family_key": item.primary_visible_family_key,
                "secondary_visible_family_key": item.secondary_visible_family_key,
                "symbol": item.symbol,
                "coin_id": item.coin_id,
                "duplicate_visible_family_count": item.duplicate_visible_family_count,
                "symbol_duplicate_count": item.symbol_duplicate_count,
                "collapsed_symbol_family_count": item.collapsed_symbol_family_count,
                "feedback_target": item.feedback_target,
                "core_family_ids": list(item.core_family_ids),
                "collapsed_family_representative_reason": item.collapsed_family_representative_reason,
            }
        )
    return rows


def _symbol_family_summaries(items: Iterable[ReviewItem]) -> list[dict[str, Any]]:
    groups: dict[str, list[ReviewItem]] = {}
    for item in items:
        groups.setdefault(item.primary_visible_family_key, []).append(item)
    rows: list[dict[str, Any]] = []
    for primary, values in sorted(groups.items(), key=lambda pair: (-sum(item.duplicate_visible_family_count for item in pair[1]), pair[0])):
        selected_targets = [
            item.feedback_target
            for item in sorted(values, key=lambda value: (-value.review_value_score, value.secondary_visible_family_key))
            if item.feedback_target
        ][:3]
        rows.append(
            {
                "primary_visible_family_key": primary,
                "collapsed_symbol_family_count": len(values),
                "symbol_duplicate_count": sum(item.duplicate_visible_family_count for item in values),
                "selected_feedback_targets": ", ".join(selected_targets),
            }
        )
    return rows


def _item_from_group(
    family: str,
    rows: list[dict[str, Any]],
    *,
    card_index: Mapping[str, Path],
    profile: str,
    context: Any,
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
    card_path = _display_card_path(card, context=context) if card else ""
    card_not_available_reason = "" if card_path else _card_not_available_reason(best)
    value_score, value_reasons, downrank_reasons, bucket = _review_value(best, opportunity_type, score, source_origin, source_pack, evidence_status, market_state, why, has_card=bool(card_path))
    primary_key = _primary_visible_family_key(best)
    secondary_key = _secondary_visible_family_key(best, opportunity_type, bucket)
    return ReviewItem(
        family=family,
        visible_family_key=family,
        primary_visible_family_key=primary_key,
        secondary_visible_family_key=secondary_key,
        candidate_family_id=candidate_family_id,
        core_family_ids=core_family_ids,
        duplicate_visible_family_count=len(rows),
        symbol_duplicate_count=len(rows),
        collapsed_symbol_family_count=1,
        visible_family_rank=0,
        symbol_family_rank=0,
        selection_bucket=bucket,
        allowed_second_family_reason="",
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
        card_not_available_reason=card_not_available_reason,
        feedback_target=target,
        suggested_feedback_commands=_feedback_commands(profile, target),
        candidate_record_type=str(best.get("candidate_record_type") or "candidate"),
        candidate_provenance=str(best.get("candidate_provenance") or "candidate"),
        contract_counted_candidate=bool(best.get("contract_counted_candidate")),
        source_artifact=str(best.get("source_artifact") or best.get("_source_file") or ""),
        source_artifact_row_type=str(best.get("source_artifact_row_type") or best.get("row_type") or ""),
        real_candidate_evidence=bool(best.get("real_candidate_evidence")),
        diagnostic_only=bool(best.get("diagnostic_only")),
        fixture_only=bool(best.get("fixture_only")),
        preflight_only=bool(best.get("preflight_only")),
        provider_gap=_provider_gap(best),
        review_value_score=value_score,
        review_value_reasons=tuple([*value_reasons, *downrank_reasons]),
        review_value_reason_codes=tuple(value_reasons),
        downrank_reason_codes=tuple(downrank_reasons),
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


def _card_not_available_reason(row: Mapping[str, Any]) -> str:
    if row.get("preflight_only") is True:
        return "preflight_rows_do_not_generate_research_cards"
    if row.get("diagnostic_only") is True or common.row_lane(row).upper() == "DIAGNOSTIC":
        return "diagnostic_rows_do_not_generate_research_cards"
    if str(row.get("candidate_record_type") or "") in {"market_anomaly", "fade_review_candidate"}:
        return "source_candidate_has_no_core_card"
    if str(row.get("candidate_provenance") or "") in {"market_anomaly", "fade_review_candidate"}:
        return "source_candidate_has_no_core_card"
    if not (row.get("core_opportunity_id") or row.get("candidate_id") or row.get("feedback_target")):
        return "missing_card_identity"
    return "card_artifact_not_found"


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
    ranked = sorted(items, key=lambda item: (-_priority(item), -item.score, item.secondary_visible_family_key))
    by_primary: dict[str, list[ReviewItem]] = {}
    for item in ranked:
        by_primary.setdefault(item.primary_visible_family_key, []).append(item)
    best_by_primary = [values[0] for values in by_primary.values()]
    secondaries = [
        replace(
            item,
            allowed_second_family_reason=f"high_value_secondary:{item.diversity_bucket}",
        )
        for values in by_primary.values()
        for item in values[1:]
        if _allowed_second_family(item, values[0])
    ]
    ranked = sorted(best_by_primary, key=lambda item: (-_priority(item), -item.score, item.secondary_visible_family_key))
    selected: list[ReviewItem] = []
    selected_keys: set[str] = set()
    desired_buckets = (
        "accepted_evidence_no_market_confirmation",
        "near_gate",
        "market_anomaly_missing_catalyst",
        "official_structured_missing_market",
        "high_value_skipped_family",
        "provider_confirmation_gap",
        "source_only_narrative",
    )
    for bucket in desired_buckets:
        candidate = next((item for item in ranked if item.diversity_bucket == bucket and item.primary_visible_family_key not in selected_keys), None)
        if candidate and len(selected) < limit:
            selected.append(candidate)
            selected_keys.add(candidate.primary_visible_family_key)
    for item in ranked:
        if len(selected) >= limit:
            break
        if item.primary_visible_family_key in selected_keys:
            continue
        selected.append(item)
        selected_keys.add(item.primary_visible_family_key)
    for item in sorted(secondaries, key=lambda value: (-_priority(value), -value.score, value.secondary_visible_family_key)):
        if len(selected) >= limit:
            break
        if item.secondary_visible_family_key in {selected_item.secondary_visible_family_key for selected_item in selected}:
            continue
        selected.append(item)
    ordered = sorted(
        selected,
        key=lambda item: (
            0 if item.contract_counted_candidate else 1,
            -_priority(item),
            -item.score,
            item.visible_family_key,
        ),
    )
    primary_counts = {
        primary: sum(item.duplicate_visible_family_count for item in values)
        for primary, values in by_primary.items()
    }
    family_counts = {primary: len(values) for primary, values in by_primary.items()}
    primary_seen: dict[str, int] = {}
    return [
        _ranked_item(item, index, primary_seen, primary_counts, family_counts)
        for index, item in enumerate(ordered, start=1)
    ]


def _rejected_second_family_count(all_items: list[ReviewItem], selected: list[ReviewItem]) -> int:
    selected_secondaries = {item.secondary_visible_family_key for item in selected}
    by_primary: dict[str, list[ReviewItem]] = {}
    for item in sorted(all_items, key=lambda value: (-_priority(value), value.secondary_visible_family_key)):
        by_primary.setdefault(item.primary_visible_family_key, []).append(item)
    rejected = 0
    for values in by_primary.values():
        if not values:
            continue
        rejected += sum(
            1
            for item in values[1:]
            if item.secondary_visible_family_key not in selected_secondaries and not _allowed_second_family(item, values[0])
        )
    return rejected


def _allowed_second_family(item: ReviewItem, primary_best: ReviewItem) -> bool:
    if item.diversity_bucket == primary_best.diversity_bucket:
        return False
    if item.diversity_bucket not in HIGH_VALUE_SECONDARY_BUCKETS:
        return False
    if item.review_value_score < SECONDARY_VISIBLE_FAMILY_MIN_SCORE:
        return False
    if "generic_context_source_downranked" in item.downrank_reason_codes:
        return False
    return True


def _ranked_item(
    item: ReviewItem,
    index: int,
    primary_seen: dict[str, int],
    primary_counts: Mapping[str, int],
    family_counts: Mapping[str, int],
) -> ReviewItem:
    primary_seen[item.primary_visible_family_key] = primary_seen.get(item.primary_visible_family_key, 0) + 1
    symbol_rank = primary_seen[item.primary_visible_family_key]
    return replace(
        item,
        family_rank=index,
        visible_family_rank=index,
        symbol_family_rank=symbol_rank,
        duplicate_visible_family_count=item.duplicate_visible_family_count,
        symbol_duplicate_count=primary_counts.get(item.primary_visible_family_key, item.duplicate_visible_family_count),
        collapsed_symbol_family_count=family_counts.get(item.primary_visible_family_key, 1),
        selection_bucket=item.diversity_bucket,
        selection_reason=_selection_reason(item, index),
        selected_representative_reason=item.collapsed_family_representative_reason,
    )


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
) -> tuple[int, list[str], list[str], str]:
    value = _legacy_priority(_legacy_review_item_for_value(opportunity_type, score, source_origin, source_pack, evidence_status, market_state, why))
    reasons: list[str] = []
    downrank_reasons: list[str] = []
    bucket = "general"
    source_text = f"{source_origin} {source_pack}".casefold()
    market_text = f"{market_state} {why}".casefold()
    evidence_text = evidence_status.casefold()
    lane_text = opportunity_type.casefold()
    why_text = why.casefold()
    source_strength = max(common.int_value(row.get("source_strength")), common.int_value(row.get("source_strength_score")))
    symbol = str(row.get("symbol") or row.get("asset_symbol") or "").strip().upper()
    if str(row.get("evidence_acquisition_status") or "").casefold() == "accepted_evidence_found":
        value += 58
        reasons.append("accepted_evidence_found")
        bucket = "accepted_evidence_no_market_confirmation" if bucket == "general" else bucket
    if any(token in source_text for token in ("cryptopanic", "rss", "gdelt", "news", "context")) and "official" not in source_text:
        value += 4
        reasons.append("source_only_context_review")
        bucket = "source_only_narrative"
        if any(token in source_text for token in ("project_blog_rss", "rss", "gdelt")) or symbol in {"BTC", "ETH"}:
            value -= 25 if symbol in {"BTC", "ETH"} else 15
            downrank_reasons.append("generic_context_source_downranked")
    if row.get("_source_file") == "event_market_anomalies.jsonl" or "anomaly" in market_text or source_pack == "market_anomaly_pack":
        value += 55
        reasons.append("market_anomaly_missing_catalyst")
        bucket = "market_anomaly_missing_catalyst"
    elif market_state.casefold() in {"late_momentum", "confirmed_breakout"} and "catalyst" in why_text:
        value += 35
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
        reasons.append("official_structured_missing_market")
        if bucket != "accepted_evidence_no_market_confirmation":
            bucket = "official_structured_missing_market"
    if source_strength >= 70 and ("blocked" in market_text or no_market):
        value += 45
        reasons.append("source_pack_high_priority")
        bucket = "source_pack_high_priority"
    gap_value, gap_reasons, gap_bucket = _specific_alertability_gap_reasons(why_text, accepted=accepted)
    if gap_reasons:
        value += gap_value
        reasons.extend(gap_reasons)
        if bucket == "general":
            bucket = gap_bucket
    if "near" in why_text:
        value += 45
        reasons.append("near_gate")
        bucket = "near_gate"
    if "quality" in why_text or "cap" in why_text:
        value += 10
        reasons.append("quality_capped")
    if row.get("skipped") is True or row.get("skip_reason") or "skip" in why_text:
        value += 40
        reasons.append("high_value_skipped_family")
        bucket = "high_value_skipped_family"
    gap = _provider_gap(row)
    if gap and any(token in gap.casefold() for token in ("coinalyze", "official", "unlock", "exchange", "provider", "confirmation")):
        value += 35
        reasons.append("provider_confirmation_gap")
        bucket = "provider_confirmation_gap"
        if any(token in gap.casefold() for token in ("coinalyze", "official", "unlock", "exchange")):
            value += 15
            reasons.append("lane_critical_provider_gap")
    if _is_fresh_candidate(row):
        value += 10
        reasons.append("fresh_candidate")
    if opportunity_type == "FADE_SHORT_REVIEW":
        value += 20
        reasons.append("fade_review")
    if "diagnostic" in lane_text:
        value -= 35
        downrank_reasons.append("diagnostic_hidden")
    if row.get("preflight_only") is True:
        value -= 40
        downrank_reasons.append("preflight_only_hidden")
    if row.get("fixture_only") is True:
        value -= 25
        downrank_reasons.append("fixture_only_hidden")
    if not has_card:
        value -= 5
        downrank_reasons.append("no_card_path_downranked")
    if _is_stale_candidate(row, market_state, why):
        value -= 20
        downrank_reasons.append("stale_candidate_downranked")
    if "unsupported" in why_text or "insufficient" in why_text:
        value -= 25
        downrank_reasons.append("unsupported_mechanism_downranked")
    if not reasons or not any(reason in HIGH_VALUE_REASON_CODES for reason in reasons):
        for reason in _fallback_review_reason_codes(
            opportunity_type=opportunity_type,
            source_text=source_text,
            market_text=market_text,
            evidence_text=evidence_text,
            source_strength=source_strength,
        ):
            if reason not in reasons:
                reasons.append(reason)
    return max(0, value), reasons, downrank_reasons, bucket


def _legacy_review_item_for_value(
    opportunity_type: str,
    score: int,
    source_origin: str,
    source_pack: str,
    evidence_status: str,
    market_state: str,
    why: str,
) -> ReviewItem:
    return ReviewItem(
        family="",
        visible_family_key="",
        primary_visible_family_key="",
        secondary_visible_family_key="",
        candidate_family_id="",
        core_family_ids=(),
        duplicate_visible_family_count=1,
        symbol_duplicate_count=1,
        collapsed_symbol_family_count=1,
        visible_family_rank=0,
        symbol_family_rank=0,
        selection_bucket="general",
        allowed_second_family_reason="",
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
        card_not_available_reason="no_candidate_card_artifact",
        feedback_target="",
        suggested_feedback_commands=(),
        candidate_record_type="candidate",
        candidate_provenance="candidate",
        contract_counted_candidate=False,
        source_artifact="",
        source_artifact_row_type="candidate",
        real_candidate_evidence=False,
        diagnostic_only=False,
        fixture_only=False,
        preflight_only=False,
    )


def _specific_alertability_gap_reasons(why_text: str, *, accepted: bool) -> tuple[int, list[str], str]:
    value = 0
    reasons: list[str] = []
    bucket = "source_pack_high_priority"
    if "strong_source_missing" in why_text or "strong source missing" in why_text:
        value += 25
        reasons.append("missing_strong_source_review")
    if "market_reaction_missing" in why_text or "market reaction missing" in why_text:
        value += 25
        reasons.append("missing_market_confirmation_review")
        bucket = "accepted_evidence_no_market_confirmation" if accepted else "source_pack_high_priority"
    return value, reasons, bucket


def _fallback_review_reason_codes(
    *,
    opportunity_type: str,
    source_text: str,
    market_text: str,
    evidence_text: str,
    source_strength: int,
) -> list[str]:
    reasons: list[str] = []
    if any(token in source_text for token in ("cryptopanic", "rss", "gdelt", "project_blog", "news", "context")):
        reasons.append("source_only_context_review")
    if "accepted" not in evidence_text and source_strength < 70:
        reasons.append("missing_strong_source_review")
    if any(token in market_text for token in ("unknown", "missing", "unconfirmed", "needs confirmation", "no market")):
        reasons.append("missing_market_confirmation_review")
    if not reasons and opportunity_type == "UNCONFIRMED_RESEARCH":
        reasons.append("general_unconfirmed_research_review")
    return reasons or ["general_unconfirmed_research_review"]


def _is_fresh_candidate(row: Mapping[str, Any]) -> bool:
    text = " ".join(str(row.get(field) or "") for field in ("freshness_status", "market_context_freshness_status", "source_freshness_status", "market_state_class")).casefold()
    if "fresh" in text or "current" in text:
        return True
    timestamp = common.timestamp_for_row(row)
    if timestamp is None:
        return False
    return (common.utc_now() - timestamp).total_seconds() <= 3 * 24 * 3600


def _is_stale_candidate(row: Mapping[str, Any], market_state: str, why: str) -> bool:
    text = " ".join(
        [
            str(market_state or ""),
            str(why or ""),
            str(row.get("freshness_status") or ""),
            str(row.get("market_context_freshness_status") or ""),
            str(row.get("source_freshness_status") or ""),
        ]
    ).casefold()
    return "stale" in text or "expired" in text


def _selection_reason(item: ReviewItem, rank: int) -> str:
    if item.diversity_bucket in {
        "source_only_narrative",
        "market_anomaly_missing_catalyst",
        "accepted_evidence_no_market_confirmation",
        "near_gate",
        "official_structured_missing_market",
        "high_value_skipped_family",
        "provider_confirmation_gap",
        "source_pack_high_priority",
        "fresh_candidate",
    }:
        return f"diversity_bucket:{item.diversity_bucket}"
    if rank == 1:
        return "top_review_value"
    return "next_highest_review_value"


def _display_card_path(path: str | Path, *, context: Any) -> str:
    return event_artifact_paths.artifact_display_path(
        path,
        repo_root=common.repo_root_from_module(),
        artifact_base=context.base_dir,
    )


def _resolve_review_card_path(raw_path: str, *, context: Any) -> Path | None:
    text = str(raw_path or "").strip()
    if not text or text.casefold() == "none":
        return None
    path = Path(text).expanduser()
    roots = [
        Path(context.base_dir),
        Path(context.namespace_dir),
        common.repo_root_from_module(),
        Path.cwd(),
    ]
    if path.is_absolute():
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        for root in roots:
            try:
                resolved.relative_to(root.resolve())
                return resolved
            except (OSError, ValueError):
                continue
        return None
    for root in roots:
        candidate = root / path
        if candidate.exists():
            return candidate
    return None


def _path_warning_label(raw_path: str, *, context: Any) -> str:
    text = str(raw_path or "").strip()
    if not text:
        return "missing:empty"
    path = Path(text).expanduser()
    if path.is_absolute():
        if _resolve_review_card_path(text, context=context) is None:
            return f"absolute_review_path_outside_allowed_roots:{path.name}"
        return event_artifact_paths.artifact_display_path(
            path,
            repo_root=common.repo_root_from_module(),
            artifact_base=context.base_dir,
        )
    return f"missing:{text}"


def _stale_path_warnings(items: Iterable[ReviewItem], *, context: Any) -> list[str]:
    warnings: list[str] = []
    for item in items:
        if not item.card_path:
            continue
        if _resolve_review_card_path(item.card_path, context=context) is None:
            warnings.append(_path_warning_label(item.card_path, context=context))
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
