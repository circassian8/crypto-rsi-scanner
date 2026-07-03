"""Validation labeling queue helpers."""

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

from ....event_discovery import VALIDATION_SAMPLE_FIELDS, VALIDATION_SAMPLE_SCHEMA_VERSION
from .models import *  # noqa: F403 - split modules share legacy model names


def _labeling_queue_item(row: Mapping[str, Any]) -> ValidationLabelingQueueItem | None:
    label = _label(row)
    signal_type = _signal_type(row)
    triggered = signal_type == "SHORT_TRIGGERED"
    missing_trigger_outcomes = tuple(
        field for field in REQUIRED_TRIGGER_OUTCOME_FIELDS if _num(row.get(field)) is None
    )
    missing_event_time_baseline = tuple(
        field for field in REQUIRED_EVENT_TIME_BASELINE_FIELDS if _num(row.get(field)) is None
    )
    missing_required_outcomes = (*missing_trigger_outcomes, *missing_event_time_baseline)

    if label and label not in KNOWN_LABELS:
        return _queue_item(
            row,
            priority=0,
            category="fix_unknown_label",
            suggested_label=", ".join(sorted(KNOWN_LABELS)),
            missing_fields=("human_label",),
        )
    if _review_status(row) == "reviewed" and not label:
        return _queue_item(
            row,
            priority=1,
            category="fill_review_label",
            suggested_label=_suggested_label(row),
            missing_fields=("human_label",),
        )
    if label and _review_status(row) != "reviewed":
        return _queue_item(
            row,
            priority=2,
            category="mark_reviewed_status",
            suggested_label=label,
            missing_fields=("review_status",),
        )
    if _is_reviewed_evidence(row) and (missing_provenance := _missing_review_provenance_fields(row)):
        return _queue_item(
            row,
            priority=3,
            category="add_review_provenance",
            suggested_label=label,
            missing_fields=missing_provenance,
        )
    if label and _point_in_time_violation(row):
        return _queue_item(
            row,
            priority=4,
            category="fix_point_in_time_evidence",
            suggested_label=label,
            missing_fields=(),
        )
    if label and _post_decision_source(row):
        return _queue_item(
            row,
            priority=5,
            category="review_post_decision_source",
            suggested_label=label,
            missing_fields=(),
        )
    if label and _missing_source_timing(row):
        return _queue_item(
            row,
            priority=6,
            category="add_source_timing",
            suggested_label=label,
            missing_fields=("first_seen_time", "raw_published_at", "raw_fetched_at"),
        )
    if label and triggered and _trigger_event_time_needs_confirmation(row):
        return _queue_item(
            row,
            priority=7,
            category="confirm_trigger_event_time",
            suggested_label=label,
            missing_fields=("event_time_source", "event_time_confidence"),
        )
    if label == POSITIVE_LABEL and _is_proxy_candidate(row) and _proxy_event_time_needs_human_confirmation(row):
        return _queue_item(
            row,
            priority=8,
            category="confirm_valid_proxy_event_time",
            suggested_label=label,
            missing_fields=_missing_proxy_event_time_review_fields(row, include_label=False),
        )
    if triggered and not label:
        return _queue_item(
            row,
            priority=9,
            category="label_triggered_candidate",
            suggested_label=_suggested_label(row),
            missing_fields=("human_label", *missing_required_outcomes),
        )
    if triggered and missing_required_outcomes:
        return _queue_item(
            row,
            priority=10,
            category="fill_trigger_outcomes",
            suggested_label=label or _suggested_label(row),
            missing_fields=missing_required_outcomes,
        )
    if not label and _is_proxy_candidate(row) and _proxy_event_time_needs_human_confirmation(row):
        return _queue_item(
            row,
            priority=11,
            category="confirm_proxy_event_time",
            suggested_label="valid_proxy_fade or false_positive",
            missing_fields=_missing_proxy_event_time_review_fields(row, include_label=True),
        )
    if not label and _is_proxy_candidate(row):
        return _queue_item(
            row,
            priority=12,
            category="label_proxy_candidate",
            suggested_label="valid_proxy_fade or false_positive",
            missing_fields=("human_label",),
        )
    if not label and _is_direct_or_ambiguous(row):
        return _queue_item(
            row,
            priority=13,
            category="label_negative_control",
            suggested_label=_suggested_label(row),
            missing_fields=("human_label",),
        )
    return None


def _queue_item(
    row: Mapping[str, Any],
    *,
    priority: int,
    category: str,
    suggested_label: str,
    missing_fields: tuple[str, ...],
) -> ValidationLabelingQueueItem:
    return ValidationLabelingQueueItem(
        priority=priority,
        category=category,
        asset_symbol=str(row.get("asset_symbol") or ""),
        asset_coin_id=str(row.get("asset_coin_id") or ""),
        event_id=str(row.get("event_id") or ""),
        event_name=str(row.get("event_name") or ""),
        relationship_type=str(row.get("relationship_type") or ""),
        signal_type=_signal_type(row),
        event_time=_string_or_none(row.get("event_time")),
        event_time_source=str(row.get("event_time_source") or ""),
        event_time_confidence=_num(row.get("event_time_confidence")),
        trigger_observed_at=_string_or_none(row.get("trigger_observed_at")),
        human_label=_label(row),
        suggested_label=suggested_label,
        missing_fields=missing_fields,
        source_urls=tuple(str(value) for value in _list_values(row.get("source_urls")) if value),
        source_origins=source_origin_values(row),
    )


def _missing_proxy_event_time_review_fields(
    row: Mapping[str, Any],
    *,
    include_label: bool,
) -> tuple[str, ...]:
    missing: list[str] = []
    if include_label and not _label(row):
        missing.append("human_label")
    if not _string_or_none(row.get("event_time")) and not _string_or_none(row.get("human_event_time")):
        missing.append("human_event_time")
    if not _string_or_none(row.get("human_event_time_source")):
        missing.append("human_event_time_source")
    if (_num(row.get("human_event_time_confidence")) or 0.0) < DEFAULT_MIN_TRIGGER_EVENT_TIME_CONFIDENCE:
        missing.append("human_event_time_confidence")
    return tuple(missing)


def _trigger_event_time_needs_confirmation(row: Mapping[str, Any]) -> bool:
    if _signal_type(row) != "SHORT_TRIGGERED":
        return False
    confidence = _review_event_time_confidence(row) or 0.0
    return confidence < DEFAULT_MIN_TRIGGER_EVENT_TIME_CONFIDENCE


def _proxy_event_time_needs_human_confirmation(row: Mapping[str, Any]) -> bool:
    if _string_or_none(row.get("human_event_time")):
        confidence = _num(row.get("human_event_time_confidence")) or 0.0
        source = _string_or_none(row.get("human_event_time_source"))
        if source and confidence >= DEFAULT_MIN_TRIGGER_EVENT_TIME_CONFIDENCE:
            return False
    event_time = _string_or_none(row.get("event_time"))
    confidence = _num(row.get("event_time_confidence")) or 0.0
    source = str(row.get("event_time_source") or "").strip()
    if not event_time:
        return True
    if confidence < DEFAULT_MIN_TRIGGER_EVENT_TIME_CONFIDENCE:
        return True
    return source != "explicit"


def _labeling_queue_sort_key(
    item: ValidationLabelingQueueItem,
) -> tuple[int, int, float, str, str, str]:
    return (
        item.priority,
        _event_time_quality_rank(item),
        -(item.event_time_confidence or 0.0),
        item.event_time or "",
        item.asset_symbol,
        item.event_name,
    )


def _event_time_quality_rank(item: ValidationLabelingQueueItem) -> int:
    if not item.event_time:
        return 4
    confidence = item.event_time_confidence
    if confidence is None:
        return 3
    if item.event_time_source == "explicit" and confidence >= DEFAULT_MIN_TRIGGER_EVENT_TIME_CONFIDENCE:
        return 0
    if confidence >= DEFAULT_MIN_TRIGGER_EVENT_TIME_CONFIDENCE:
        return 1
    return 2


def _suggested_label(row: Mapping[str, Any]) -> str:
    if _is_proxy_candidate(row):
        return "valid_proxy_fade or false_positive"
    if _bool(row.get("is_direct_beneficiary")):
        return "direct_event"
    relation = str(row.get("relationship_type") or "").strip()
    if relation == "ambiguous":
        return "ambiguous"
    return "direct_event or ambiguous"
