"""Validation review sample and packet helpers."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import quote_plus, urlparse

from ..discovery import VALIDATION_SAMPLE_FIELDS, VALIDATION_SAMPLE_SCHEMA_VERSION
from .models import *  # noqa: F403 - split modules share historical model names


def build_labeling_queue(
    rows: Iterable[Mapping[str, Any]],
    *,
    limit: int | None = None,
) -> ValidationLabelingQueue:
    """Prioritize validation rows that still need human review status, labels, or outcomes."""
    data = [dict(row) for row in rows]
    items = [_labeling_queue_item(row) for row in data]
    needed = sorted(
        (item for item in items if item is not None),
        key=_labeling_queue_sort_key,
    )
    shown = needed[: max(0, limit)] if limit is not None else needed
    return ValidationLabelingQueue(
        total_rows=len(data),
        needed_rows=len(needed),
        shown_rows=len(shown),
        limit=limit,
        items=tuple(shown),
    )


def format_labeling_queue(queue: ValidationLabelingQueue) -> str:
    rows = [
        "=" * 78,
        "EVENT FADE VALIDATION LABELING QUEUE (research-only; no alerts, DB writes, paper trades, or orders)",
        "=" * 78,
        (
            f"Rows: {queue.total_rows} · needing labels/status/outcomes: {queue.needed_rows} · "
            f"showing: {queue.shown_rows}"
        ),
    ]
    if queue.limit is not None:
        rows.append(f"Limit: {queue.limit}")
    if not queue.items:
        rows.append("")
        rows.append("No rows need labels, review status, or required trigger outcomes.")
        return "\n".join(rows)

    rows.append("")
    for idx, item in enumerate(queue.items, 1):
        missing = ", ".join(item.missing_fields) if item.missing_fields else "review required"
        event_time = item.event_time or "unknown"
        event_time_source = item.event_time_source or "unknown"
        event_time_confidence = _fmt_pct(item.event_time_confidence)
        trigger_time = item.trigger_observed_at or "n/a"
        label = item.human_label or "unlabeled"
        rows.append(
            f"{idx}. {item.category} · {item.asset_symbol} ({item.asset_coin_id}) · "
            f"signal={item.signal_type or 'NO_TRADE'} · rel={item.relationship_type}"
        )
        rows.append(f"   event: {item.event_name}")
        rows.append(
            f"   event_time: {event_time} · source: {event_time_source} · "
            f"confidence: {event_time_confidence} · trigger: {trigger_time}"
        )
        rows.append(
            f"   label: {label} · suggested: {item.suggested_label} · missing: {missing}"
        )
        if item.source_urls:
            rows.append("   sources: " + ", ".join(item.source_urls[:3]))
        if item.source_origins:
            rows.append("   origins: " + ", ".join(item.source_origins[:3]))
    return "\n".join(rows)


def format_review_packet(
    rows: Iterable[Mapping[str, Any]],
    *,
    limit: int | None = 20,
) -> str:
    """Format prioritized validation rows as a human-labeling Markdown packet."""
    data = [dict(row) for row in rows]
    queue = build_labeling_queue(data, limit=limit)
    pairs = _review_packet_items(data, limit=limit)
    out = [
        "# Event-Fade Validation Review Packet",
        "",
        "Research-only: no alerts, DB writes, paper trades, or orders.",
        "",
        (
            f"Rows: {queue.total_rows} | needing labels/status/outcomes: {queue.needed_rows} | "
            f"showing: {queue.shown_rows}"
        ),
    ]
    if queue.limit is not None:
        out.append(f"Limit: {queue.limit}")
    if not pairs:
        message = (
            "No rows shown by the current limit."
            if queue.needed_rows
            else "No rows need labels, review status, or required trigger outcomes."
        )
        out.extend(["", message])
        return "\n".join(out)

    out.append("")
    for idx, (item, row) in enumerate(pairs, 1):
        out.extend(_format_review_packet_row(idx, item, row))
        out.append("")
    return "\n".join(out).rstrip()


def format_balanced_review_packet(
    rows: Iterable[Mapping[str, Any]],
    *,
    proxy_limit: int | None = DEFAULT_BALANCED_PROXY_REVIEW_ROWS,
    control_limit: int | None = DEFAULT_BALANCED_CONTROL_REVIEW_ROWS,
    triggered_limit: int | None = None,
) -> str:
    """Format gate-balanced validation rows as a human-labeling Markdown packet."""
    data = [dict(row) for row in rows]
    pairs = _balanced_review_packet_items(
        data,
        proxy_limit=proxy_limit,
        control_limit=control_limit,
        triggered_limit=triggered_limit,
    )
    slice_counts: dict[str, int] = {}
    for review_slice, _item, _row in pairs:
        slice_counts[review_slice] = slice_counts.get(review_slice, 0) + 1
    slice_summary = ", ".join(
        f"{key}={value}" for key, value in sorted(slice_counts.items())
    ) or "none"
    out = [
        "# Event-Fade Balanced Review Packet",
        "",
        "Research-only: no alerts, DB writes, paper trades, or orders.",
        "",
        (
            f"Rows shown: {len(pairs)} | proxy_limit={proxy_limit} | "
            f"control_limit={control_limit} | triggered_limit={triggered_limit or 'all'}"
        ),
        f"Slices: {slice_summary}",
    ]
    if not pairs:
        out.extend(["", "No rows need balanced review."])
        return "\n".join(out)

    out.append("")
    for idx, (review_slice, item, row) in enumerate(pairs, 1):
        out.extend(_format_review_packet_row(idx, item, row, review_slice=review_slice))
        out.append("")
    return "\n".join(out).rstrip()


def _review_packet_items(
    rows: Iterable[Mapping[str, Any]],
    *,
    limit: int | None,
) -> list[tuple[ValidationLabelingQueueItem, Mapping[str, Any]]]:
    pairs: list[tuple[ValidationLabelingQueueItem, Mapping[str, Any]]] = []
    for row in rows:
        item = _labeling_queue_item(row)
        if item is not None:
            pairs.append((item, row))
    pairs.sort(
        key=lambda pair: _labeling_queue_sort_key(pair[0])
    )
    return pairs[: max(0, limit)] if limit is not None else pairs


def _balanced_review_packet_items(
    rows: Iterable[Mapping[str, Any]],
    *,
    proxy_limit: int | None = DEFAULT_BALANCED_PROXY_REVIEW_ROWS,
    control_limit: int | None = DEFAULT_BALANCED_CONTROL_REVIEW_ROWS,
    triggered_limit: int | None = None,
) -> list[tuple[str, ValidationLabelingQueueItem, Mapping[str, Any]]]:
    pairs = _review_packet_items(rows, limit=None)
    selected: list[tuple[str, ValidationLabelingQueueItem, Mapping[str, Any]]] = []
    used: set[tuple[str, str, str, str]] = set()

    def pair_key(item: ValidationLabelingQueueItem) -> tuple[str, str, str, str]:
        return (
            item.event_id,
            item.asset_coin_id,
            item.relationship_type,
            item.category,
        )

    def add_slice(review_slice: str, predicate, limit: int | None) -> None:
        candidates: list[tuple[int, ValidationLabelingQueueItem, Mapping[str, Any]]] = []
        for idx, (item, row) in enumerate(pairs):
            key = pair_key(item)
            if key in used or not predicate(item, row):
                continue
            candidates.append((idx, item, row))
        for item, row in _select_diverse_review_pairs(candidates, limit):
            key = pair_key(item)
            selected.append((review_slice, item, row))
            used.add(key)

    add_slice(
        "triggered",
        lambda item, row: _signal_type(row) == "SHORT_TRIGGERED"
        or item.category in {"label_triggered_candidate", "confirm_trigger_event_time", "fill_trigger_outcomes"},
        triggered_limit,
    )
    proxy_selected_before = len(selected)
    add_slice(
        "proxy_candidate",
        lambda item, row: _is_proxy_candidate(row) and _asset_role(row) == "proxy_instrument",
        proxy_limit,
    )
    proxy_remainder = None
    if proxy_limit is not None:
        proxy_remainder = max(0, proxy_limit - (len(selected) - proxy_selected_before))
    add_slice(
        "proxy_candidate",
        lambda item, row: _is_proxy_candidate(row) and _asset_role(row) != "proxy_instrument",
        proxy_remainder,
    )
    add_slice(
        "negative_control",
        lambda item, row: _is_direct_or_ambiguous(row),
        control_limit,
    )
    return selected


def _select_diverse_review_pairs(
    candidates: list[tuple[int, ValidationLabelingQueueItem, Mapping[str, Any]]],
    limit: int | None,
) -> list[tuple[ValidationLabelingQueueItem, Mapping[str, Any]]]:
    if limit is not None and limit <= 0:
        return []
    if limit is None:
        return [(item, row) for _idx, item, row in candidates]

    remaining = list(candidates)
    selected: list[tuple[ValidationLabelingQueueItem, Mapping[str, Any]]] = []
    counts: dict[str, Counter[str]] = {
        "asset": Counter(),
        "event_type": Counter(),
        "asset_role": Counter(),
        "relationship": Counter(),
        "origin": Counter(),
        "event": Counter(),
    }
    while remaining and len(selected) < limit:
        best_idx = min(
            range(len(remaining)),
            key=lambda idx: _review_diversity_score(remaining[idx], counts),
        )
        _original_idx, item, row = remaining.pop(best_idx)
        selected.append((item, row))
        dimensions = _review_diversity_dimensions(item, row)
        for key, value in dimensions.items():
            counts[key][value] += 1
    return selected


def _review_diversity_score(
    candidate: tuple[int, ValidationLabelingQueueItem, Mapping[str, Any]],
    counts: Mapping[str, Counter[str]],
) -> tuple[int, int, int, int, int, int, int]:
    original_idx, item, row = candidate
    dimensions = _review_diversity_dimensions(item, row)
    return (
        counts["asset"][dimensions["asset"]],
        counts["event_type"][dimensions["event_type"]],
        counts["asset_role"][dimensions["asset_role"]],
        counts["relationship"][dimensions["relationship"]],
        counts["origin"][dimensions["origin"]],
        counts["event"][dimensions["event"]],
        original_idx,
    )


def _review_diversity_dimensions(
    item: ValidationLabelingQueueItem,
    row: Mapping[str, Any],
) -> dict[str, str]:
    origin = _first_list_text(source_origin_values(row)) or "unknown_source_origin"
    return {
        "asset": _review_diversity_value(item.asset_coin_id or item.asset_symbol),
        "event_type": _review_diversity_value(row.get("event_type") or "unknown_event_type"),
        "asset_role": _review_diversity_value(row.get("asset_role") or "unknown_asset_role"),
        "relationship": _review_diversity_value(item.relationship_type or "unknown_relationship"),
        "origin": _review_diversity_value(origin),
        "event": _review_text_slug(item.event_name or row.get("event_name")),
    }


def _review_diversity_value(value: object) -> str:
    return str(value or "unknown").strip().casefold() or "unknown"


def _review_text_slug(value: object) -> str:
    text = str(value or "unknown").strip().casefold()
    slug = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return slug or "unknown"


def _format_review_packet_row(
    idx: int,
    item: ValidationLabelingQueueItem,
    row: Mapping[str, Any],
    *,
    review_slice: str | None = None,
) -> list[str]:
    symbol = item.asset_symbol or "UNKNOWN"
    coin_id = item.asset_coin_id or "unknown"
    event_name = _packet_text(item.event_name or "Unnamed event")
    missing = ", ".join(item.missing_fields) if item.missing_fields else "review required"
    current_label = item.human_label or "unlabeled"
    edge_72h = _trigger_vs_event_time_72h_edges((row,))
    fields = [
        f"## {idx}. {symbol} - {event_name}",
        "",
        f"- Queue category: `{item.category}`",
    ]
    if review_slice:
        fields.append(f"- Review slice: `{review_slice}`")
    fields.extend([
        f"- Suggested label: `{item.suggested_label}`",
        f"- Missing fields: `{missing}`",
        f"- Current label: `{current_label}`",
        (
            f"- Event: `{_packet_text(row.get('event_type'))}` at `{_packet_text(item.event_time or 'unknown')}` | "
            f"external=`{_packet_text(row.get('external_asset') or 'unknown')}` | "
            f"time_source=`{_packet_text(row.get('event_time_source') or 'unknown')}` | "
            f"time_confidence=`{_fmt_num(_num(row.get('event_time_confidence')))}`"
        ),
        (
            f"- First seen: `{_packet_text(row.get('first_seen_time'))}` | "
            f"published=`{_packet_text(row.get('published_at_min'))}`..`{_packet_text(row.get('published_at_max'))}` | "
            f"fetched=`{_packet_text(row.get('fetched_at_min'))}`..`{_packet_text(row.get('fetched_at_max'))}`"
        ),
        (
            f"- Asset: `{symbol}` (`{coin_id}`) | relationship: "
            f"`{_packet_text(item.relationship_type or 'unknown')}` | "
            f"role: `{_packet_text(row.get('asset_role') or 'unknown')}`"
        ),
        (
            "- Classification: "
            f"proxy=`{_bool(row.get('is_proxy_narrative'))}` | "
            f"direct=`{_bool(row.get('is_direct_beneficiary'))}` | "
            f"confidence=`{_fmt_num(_num(row.get('classifier_confidence')))}`"
        ),
        (
            "- Signal: "
            f"`{item.signal_type or 'NO_TRADE'}` | state=`{_packet_text(row.get('fade_state'))}` | "
            f"eligible=`{_bool(row.get('eligible'))}` | score=`{_fmt_num(_num(row.get('fade_score')))}`"
        ),
        (
            "- Timing/risk: "
            f"trigger=`{_packet_text(item.trigger_observed_at or 'n/a')}` | "
            f"entry=`{_fmt_num(_num(row.get('entry_reference_price')))}` | "
            f"invalidation=`{_fmt_num(_num(row.get('invalidation_level')))}` | "
            f"BTC risk=`{_fmt_num(_num(row.get('btc_risk_on_score')))}`"
        ),
        (
            "- Outcomes: "
            f"trigger 24h=`{_fmt_pct(_num(row.get('post_event_return_24h')))}` | "
            f"trigger 72h=`{_fmt_pct(_num(row.get('post_event_return_72h')))}` | "
            f"trigger 7d=`{_fmt_pct(_num(row.get('post_event_return_7d')))}` | "
            f"MFE=`{_fmt_pct(_num(row.get('max_favorable_excursion')))}` | "
            f"MAE=`{_fmt_pct(_num(row.get('max_adverse_excursion')))}` | "
            f"prices=`{_packet_text(row.get('outcome_price_interval') or 'unknown')}/"
            f"{_packet_text(row.get('outcome_price_source') or 'unknown')}`"
        ),
        (
            "- Event-time baseline: "
            f"entry=`{_fmt_num(_num(row.get('event_time_entry_price')))}` | "
            f"72h=`{_fmt_pct(_num(row.get('event_time_post_event_return_72h')))}` | "
            f"trigger edge=`{_fmt_pp(edge_72h[0] if edge_72h else None)}`"
        ),
        f"- Classifier reason: {_packet_text(row.get('classification_reason'))}",
    ])
    date_hint = _source_date_hint(row)
    if date_hint:
        fields.append(f"- Source date hint: {date_hint}")
    fields.extend(_packet_bullets("Classifier evidence", row.get("classification_evidence")))
    fields.extend(_packet_bullets("Reason codes", row.get("reason_codes")))
    fields.extend(_packet_bullets("Warnings", row.get("warnings")))
    fields.extend(_packet_bullets("Missing data", row.get("missing_data")))
    fields.extend(_packet_bullets("Sources", row.get("source_urls")))
    fields.extend(_packet_bullets("Source providers", _source_provider_values(row)))
    fields.extend(_packet_bullets("Source origins", source_origin_values(row)))
    source_search = _source_search_url(row)
    if source_search:
        fields.append(f"- Source search: {source_search}")
    fields.extend(_packet_bullets("Raw titles", row.get("raw_titles")))
    fields.extend([
        "- Review fields to fill:",
        "  - `review_status`: `reviewed`",
        "  - `reviewed_by`: reviewer name or handle",
        "  - `reviewed_at`: ISO timestamp when the row was reviewed",
        "  - `human_label`: `valid_proxy_fade` | `false_positive` | `direct_event` | `ambiguous`",
        "  - `human_notes`: evidence-backed note",
        "  - `human_event_time`: explicit catalyst time if the system missed or weakly inferred it",
        "  - `human_event_time_source`: source URL/title proving that time",
        "  - `human_event_time_confidence`: reviewer confidence from 0.0 to 1.0",
    ])
    return fields


def _packet_bullets(label: str, value: object, *, max_items: int = 5) -> list[str]:
    values = [_packet_text(item) for item in _list_values(value) if _packet_text(item)]
    if not values:
        return [f"- {label}: none"]
    out = [f"- {label}:"]
    for item in values[:max_items]:
        out.append(f"  - {item}")
    if len(values) > max_items:
        out.append(f"  - ... {len(values) - max_items} more")
    return out


def _packet_text(value: object) -> str:
    if value in (None, ""):
        return "n/a"
    if isinstance(value, (dict, list, tuple)):
        try:
            value = json.dumps(value, sort_keys=True)
        except TypeError:
            value = str(value)
    return " ".join(str(value).split())
