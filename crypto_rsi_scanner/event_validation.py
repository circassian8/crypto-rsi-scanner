"""Review metrics for event-fade validation sample exports.

This module is research-only. It reads local JSONL/CSV artifacts produced by
the event-discovery exporter and summarizes manual review status, labels, and
outcomes. It never routes alerts, opens paper trades, writes live storage, or
implies execution.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .event_discovery import VALIDATION_SAMPLE_FIELDS, VALIDATION_SAMPLE_SCHEMA_VERSION


POSITIVE_LABEL = "valid_proxy_fade"
KNOWN_LABELS = frozenset({
    POSITIVE_LABEL,
    "false_positive",
    "direct_event",
    "ambiguous",
})
CONTROL_LABELS = frozenset({"direct_event", "ambiguous"})
REQUIRED_TRIGGER_OUTCOME_FIELDS = (
    "max_adverse_excursion",
    "max_favorable_excursion",
    "post_event_return_72h",
)
REQUIRED_EVENT_TIME_BASELINE_FIELDS = (
    "event_time_post_event_return_72h",
)
REVIEW_FIELDS = (
    "review_status",
    "human_label",
    "human_notes",
    "max_adverse_excursion",
    "max_favorable_excursion",
    "post_event_return_24h",
    "post_event_return_72h",
    "post_event_return_7d",
    "event_time_entry_price",
    "event_time_max_adverse_excursion",
    "event_time_max_favorable_excursion",
    "event_time_post_event_return_24h",
    "event_time_post_event_return_72h",
    "event_time_post_event_return_7d",
)
REVIEW_MERGE_IGNORED_FIELDS = frozenset({"exported_at", *REVIEW_FIELDS})
REVIEW_EVIDENCE_FIELDS = tuple(
    field for field in VALIDATION_SAMPLE_FIELDS if field not in REVIEW_MERGE_IGNORED_FIELDS
)
REVIEW_TEMPLATE_FIELDS = (
    "event_id",
    "asset_coin_id",
    "asset_symbol",
    "relationship_type",
    "event_name",
    "event_type",
    "event_time",
    "trigger_observed_at",
    "signal_type",
    "queue_category",
    "suggested_label",
    "missing_fields",
    "source_urls",
    "raw_published_at",
    "raw_fetched_at",
    "published_at_min",
    "published_at_max",
    "fetched_at_min",
    "fetched_at_max",
    "review_status",
    "human_label",
    "human_notes",
    "max_adverse_excursion",
    "max_favorable_excursion",
    "post_event_return_24h",
    "post_event_return_72h",
    "post_event_return_7d",
    "event_time_entry_price",
    "event_time_max_adverse_excursion",
    "event_time_max_favorable_excursion",
    "event_time_post_event_return_24h",
    "event_time_post_event_return_72h",
    "event_time_post_event_return_7d",
)
REVIEW_TEMPLATE_DERIVED_FIELDS = frozenset({
    "queue_category",
    "suggested_label",
    "missing_fields",
})
REVIEW_TEMPLATE_EVIDENCE_FIELDS = tuple(
    field
    for field in REVIEW_TEMPLATE_FIELDS
    if field not in REVIEW_MERGE_IGNORED_FIELDS and field not in REVIEW_TEMPLATE_DERIVED_FIELDS
)
OUTCOME_FIELDS = (
    "max_adverse_excursion",
    "max_favorable_excursion",
    "post_event_return_24h",
    "post_event_return_72h",
    "post_event_return_7d",
    "event_time_entry_price",
    "event_time_max_adverse_excursion",
    "event_time_max_favorable_excursion",
    "event_time_post_event_return_24h",
    "event_time_post_event_return_72h",
    "event_time_post_event_return_7d",
)


@dataclass(frozen=True)
class ValidationOutcomeCandle:
    timestamp: datetime
    close: float
    high: float | None = None
    low: float | None = None


@dataclass(frozen=True)
class ValidationOutcomeFillResult:
    rows: list[dict[str, Any]]
    sample_rows: int
    triggered_rows: int
    filled_rows: int
    missing_history_rows: int
    insufficient_history_rows: int
    skipped_existing_rows: int


@dataclass(frozen=True)
class EventFadeValidationReview:
    total_rows: int
    reviewed_rows: int
    unlabeled_rows: int
    missing_review_status_rows: int
    missing_human_label_rows: int
    schema_mismatches: int
    unknown_label_rows: int
    label_counts: dict[str, int]
    reviewed_proxy_candidates: int
    reviewed_negative_controls: int
    valid_proxy_labels: int
    triggered_reviewed: int
    triggered_valid: int
    direct_or_nonproxy_triggered: int
    trigger_precision: float | None
    trigger_false_positive_rate: float | None
    avg_mfe: float | None
    avg_mae: float | None
    mfe_mae_ratio: float | None
    avg_post_event_return_24h: float | None
    avg_post_event_return_72h: float | None
    avg_post_event_return_7d: float | None
    avg_event_time_post_event_return_72h: float | None
    avg_trigger_vs_event_time_return_72h_edge: float | None
    avg_trigger_latency_hours: float | None
    median_trigger_latency_hours: float | None
    negative_trigger_latency_rows: int
    missing_trigger_outcome_rows: int
    missing_event_time_baseline_rows: int
    point_in_time_violation_rows: int
    post_decision_source_rows: int
    missing_source_timing_rows: int
    min_proxy_candidates: int
    min_negative_controls: int
    min_triggered_reviewed: int
    min_trigger_precision: float
    min_mfe_mae_ratio: float
    min_proxy_event_types: int
    min_trigger_btc_risk_buckets: int
    reviewed_proxy_event_types: int
    triggered_btc_risk_buckets: int
    event_type_cohorts: tuple["ValidationCohort", ...]
    relationship_type_cohorts: tuple["ValidationCohort", ...]
    btc_risk_cohorts: tuple["ValidationCohort", ...]
    promotion_blockers: tuple[str, ...]

    @property
    def promotion_ready(self) -> bool:
        return not self.promotion_blockers


@dataclass(frozen=True)
class ValidationCohort:
    name: str
    total_rows: int
    reviewed_rows: int
    reviewed_proxy_candidates: int
    reviewed_negative_controls: int
    triggered_reviewed: int
    triggered_valid: int
    trigger_precision: float | None
    avg_mfe: float | None
    avg_mae: float | None
    mfe_mae_ratio: float | None
    avg_post_event_return_72h: float | None


@dataclass(frozen=True)
class ValidationSampleEvidenceChange:
    event_id: str
    asset_symbol: str
    asset_coin_id: str
    relationship_type: str
    changed_fields: tuple[str, ...]


@dataclass(frozen=True)
class ValidationSampleMergeResult:
    rows: list[dict[str, Any]]
    fresh_rows: int
    reviewed_rows: int
    matched_rows: int
    evidence_changed_rows: int
    evidence_changes: tuple[ValidationSampleEvidenceChange, ...]
    unmatched_reviewed_rows: int
    copied_fields: int


@dataclass(frozen=True)
class ValidationLabelingQueueItem:
    priority: int
    category: str
    asset_symbol: str
    asset_coin_id: str
    event_id: str
    event_name: str
    relationship_type: str
    signal_type: str
    event_time: str | None
    trigger_observed_at: str | None
    human_label: str
    suggested_label: str
    missing_fields: tuple[str, ...]
    source_urls: tuple[str, ...]


@dataclass(frozen=True)
class ValidationLabelingQueue:
    total_rows: int
    needed_rows: int
    shown_rows: int
    limit: int | None
    items: tuple[ValidationLabelingQueueItem, ...]


def load_validation_sample(path: str | Path) -> list[dict[str, Any]]:
    """Load a validation sample export from JSONL or CSV."""
    sample_path = Path(path).expanduser()
    text = sample_path.read_text(encoding="utf-8")
    if sample_path.suffix.casefold() == ".csv":
        return [_parse_csv_row(row) for row in csv.DictReader(text.splitlines())]
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(json.loads(stripped))
    return rows


def load_outcome_price_fixture(path: str | Path) -> dict[str, list[ValidationOutcomeCandle]]:
    """Load local price candles for artifact-only validation outcome filling."""
    fixture_path = Path(path).expanduser()
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    if isinstance(raw, Mapping):
        if isinstance(raw.get("prices"), list):
            items = raw["prices"]
            return _price_index_from_flat_rows(items)
        return _price_index_from_mapping(raw)
    if isinstance(raw, list):
        return _price_index_from_flat_rows(raw)
    raise ValueError("outcome price fixture must be a list, mapping, or {'prices': [...]}")


def fill_validation_outcomes(
    rows: Iterable[Mapping[str, Any]],
    price_index: Mapping[str, Iterable[ValidationOutcomeCandle]],
    *,
    overwrite: bool = False,
) -> ValidationOutcomeFillResult:
    """Fill triggered event-fade outcome fields from local price candles."""
    data = [dict(row) for row in rows]
    normalized_prices = {
        _asset_key(key): sorted(tuple(candles), key=lambda candle: candle.timestamp)
        for key, candles in price_index.items()
    }
    triggered = 0
    filled = 0
    missing_history = 0
    insufficient_history = 0
    skipped_existing = 0
    output: list[dict[str, Any]] = []
    for row in data:
        out = dict(row)
        if _signal_type(row) != "SHORT_TRIGGERED":
            output.append(out)
            continue
        triggered += 1
        if not overwrite and all(_num(row.get(field)) is not None for field in OUTCOME_FIELDS):
            skipped_existing += 1
            output.append(out)
            continue

        candles = _candles_for_row(row, normalized_prices)
        if not candles:
            missing_history += 1
            output.append(out)
            continue
        decision_time = _dt(row.get("trigger_observed_at")) or _dt(row.get("event_time"))
        if decision_time is None:
            insufficient_history += 1
            output.append(out)
            continue
        trigger_outcome = _short_outcome(
            candles,
            decision_time,
            entry_price=_num(row.get("entry_reference_price")),
        )
        if trigger_outcome is None:
            insufficient_history += 1
            output.append(out)
            continue
        changed = False
        for field in OUTCOME_FIELDS:
            if field.startswith("event_time_"):
                continue
            value = trigger_outcome.get(field)
            if value is None:
                continue
            if overwrite or _num(out.get(field)) is None:
                out[field] = value
                changed = True
        event_time = _dt(row.get("event_time"))
        if event_time is not None:
            event_time_outcome = _short_outcome(
                candles,
                event_time,
                entry_price=_close_asof(candles, event_time),
            )
            if event_time_outcome is not None:
                event_time_fields = _event_time_outcome_fields(event_time_outcome)
                for field, value in event_time_fields.items():
                    if value is None:
                        continue
                    if overwrite or _num(out.get(field)) is None:
                        out[field] = value
                        changed = True
        if changed:
            filled += 1
        output.append(out)
    return ValidationOutcomeFillResult(
        rows=output,
        sample_rows=len(data),
        triggered_rows=triggered,
        filled_rows=filled,
        missing_history_rows=missing_history,
        insufficient_history_rows=insufficient_history,
        skipped_existing_rows=skipped_existing,
    )


def merge_review_fields(
    fresh_rows: Iterable[Mapping[str, Any]],
    reviewed_rows: Iterable[Mapping[str, Any]],
) -> ValidationSampleMergeResult:
    """Copy human review fields only when the row's evidence fingerprint is unchanged."""
    return _merge_review_fields(fresh_rows, reviewed_rows, evidence_fields=REVIEW_EVIDENCE_FIELDS)


def _merge_review_fields(
    fresh_rows: Iterable[Mapping[str, Any]],
    reviewed_rows: Iterable[Mapping[str, Any]],
    *,
    evidence_fields: Iterable[str],
) -> ValidationSampleMergeResult:
    fresh = [dict(row) for row in fresh_rows]
    reviewed = [dict(row) for row in reviewed_rows]
    evidence_field_tuple = tuple(evidence_fields)
    reviewed_by_key = {
        key: row
        for row in reviewed
        if (key := _sample_key(row)) is not None and _has_review_data(row)
    }
    matched_keys: set[tuple[str, str, str]] = set()
    evidence_changes: list[ValidationSampleEvidenceChange] = []
    copied_fields = 0
    merged: list[dict[str, Any]] = []
    for row in fresh:
        out = dict(row)
        key = _sample_key(row)
        source = reviewed_by_key.get(key) if key is not None else None
        if source is not None:
            matched_keys.add(key)
            changed_fields = _changed_evidence_fields(out, source, evidence_field_tuple)
            if changed_fields:
                evidence_changes.append(_evidence_change_item(out, changed_fields))
                merged.append(out)
                continue
            for field in REVIEW_FIELDS:
                value = source.get(field)
                if _has_value(value):
                    out[field] = value
                    copied_fields += 1
        merged.append(out)
    return ValidationSampleMergeResult(
        rows=merged,
        fresh_rows=len(fresh),
        reviewed_rows=len(reviewed),
        matched_rows=len(matched_keys),
        evidence_changed_rows=len(evidence_changes),
        evidence_changes=tuple(evidence_changes),
        unmatched_reviewed_rows=max(0, len(reviewed_by_key) - len(matched_keys)),
        copied_fields=copied_fields,
    )


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
        key=lambda item: (
            item.priority,
            item.event_time or "",
            item.asset_symbol,
            item.event_name,
        ),
    )
    shown = needed[: max(0, limit)] if limit is not None else needed
    return ValidationLabelingQueue(
        total_rows=len(data),
        needed_rows=len(needed),
        shown_rows=len(shown),
        limit=limit,
        items=tuple(shown),
    )


def build_review_template_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    limit: int | None = 20,
) -> list[dict[str, Any]]:
    """Build compact, editable sidecar rows for human validation review."""
    data = [dict(row) for row in rows]
    pairs = _review_packet_items(data, limit=limit)
    return [_review_template_row(item, row) for item, row in pairs]


def format_review_template_jsonl(rows: Iterable[Mapping[str, Any]]) -> str:
    return "\n".join(
        json.dumps(_review_template_json_ready(row), sort_keys=True, separators=(",", ":"))
        for row in rows
    )


def format_review_template_csv(rows: Iterable[Mapping[str, Any]]) -> str:
    from io import StringIO

    out = StringIO()
    writer = csv.DictWriter(out, fieldnames=list(REVIEW_TEMPLATE_FIELDS), extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({
            field: _review_template_csv_cell(row.get(field))
            for field in REVIEW_TEMPLATE_FIELDS
        })
    return out.getvalue()


def write_review_template(
    rows: Iterable[Mapping[str, Any]],
    path: str | Path,
    *,
    limit: int | None = 20,
) -> Path:
    out = Path(path).expanduser()
    template_rows = build_review_template_rows(rows, limit=limit)
    if out.suffix.casefold() == ".csv":
        text = format_review_template_csv(template_rows)
    else:
        text = format_review_template_jsonl(template_rows)
        if text:
            text += "\n"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return out


def apply_review_template(
    sample_rows: Iterable[Mapping[str, Any]],
    reviewed_template_rows: Iterable[Mapping[str, Any]],
) -> ValidationSampleMergeResult:
    """Copy human review fields from a compact sidecar into validation rows."""
    return _merge_review_fields(
        sample_rows,
        reviewed_template_rows,
        evidence_fields=REVIEW_TEMPLATE_EVIDENCE_FIELDS,
    )


def format_merge_evidence_changes(
    result: ValidationSampleMergeResult,
    *,
    limit: int = 10,
) -> str:
    """Format rows whose prior review was skipped because evidence changed."""
    if not result.evidence_changes:
        return ""
    shown = result.evidence_changes[:limit]
    rows = ["Evidence-changed rows (review fields were not copied):"]
    for item in shown:
        label = item.asset_symbol or item.asset_coin_id or "unknown-asset"
        event_id = item.event_id or "unknown-event"
        relationship = item.relationship_type or "unknown"
        fields = ", ".join(item.changed_fields[:8])
        if len(item.changed_fields) > 8:
            fields += f", +{len(item.changed_fields) - 8} more"
        rows.append(f"- {label} {event_id} `{relationship}` changed: {fields}")
    remaining = len(result.evidence_changes) - len(shown)
    if remaining > 0:
        rows.append(f"- ... {remaining} more evidence-changed row(s)")
    return "\n".join(rows)


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
        trigger_time = item.trigger_observed_at or "n/a"
        label = item.human_label or "unlabeled"
        rows.append(
            f"{idx}. {item.category} · {item.asset_symbol} ({item.asset_coin_id}) · "
            f"signal={item.signal_type or 'NO_TRADE'} · rel={item.relationship_type}"
        )
        rows.append(f"   event: {item.event_name}")
        rows.append(f"   event_time: {event_time} · trigger: {trigger_time}")
        rows.append(
            f"   label: {label} · suggested: {item.suggested_label} · missing: {missing}"
        )
        if item.source_urls:
            rows.append("   sources: " + ", ".join(item.source_urls[:3]))
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


def review_validation_sample(
    rows: Iterable[Mapping[str, Any]],
    *,
    min_proxy_candidates: int = 25,
    min_negative_controls: int = 50,
    min_triggered_reviewed: int = 10,
    min_trigger_precision: float = 0.60,
    min_mfe_mae_ratio: float = 1.50,
    min_proxy_event_types: int = 2,
    min_trigger_btc_risk_buckets: int = 2,
) -> EventFadeValidationReview:
    """Summarize manual review status, labels, outcomes, and promotion blockers."""
    data = [dict(row) for row in rows]
    missing_review_status_rows = sum(
        1 for row in data if _label(row) and _review_status(row) != "reviewed"
    )
    missing_human_label_rows = sum(
        1 for row in data if _review_status(row) == "reviewed" and not _label(row)
    )
    unknown_label_rows = sum(
        1
        for row in data
        if _label(row) and _label(row) not in KNOWN_LABELS
    )
    reviewed = [
        row
        for row in data
        if _is_reviewed_evidence(row)
    ]
    label_counts = _label_counts(reviewed)
    schema_mismatches = sum(
        1
        for row in data
        if str(row.get("schema_version") or "") != VALIDATION_SAMPLE_SCHEMA_VERSION
    )

    reviewed_proxy = [row for row in reviewed if _is_proxy_candidate(row)]
    negative_controls = [
        row
        for row in reviewed
        if _label(row) in CONTROL_LABELS or _is_direct_or_ambiguous(row)
    ]
    valid_proxy_labels = label_counts.get(POSITIVE_LABEL, 0)

    triggered_reviewed = [row for row in reviewed if _signal_type(row) == "SHORT_TRIGGERED"]
    triggered_valid = [row for row in triggered_reviewed if _label(row) == POSITIVE_LABEL]
    direct_or_nonproxy_triggered = [
        row for row in triggered_reviewed if not _is_proxy_candidate(row)
    ]
    trigger_precision = (
        len(triggered_valid) / len(triggered_reviewed)
        if triggered_reviewed
        else None
    )
    trigger_false_positive_rate = (
        1.0 - trigger_precision
        if trigger_precision is not None
        else None
    )

    missing_trigger_outcome_rows = sum(
        1
        for row in triggered_reviewed
        if any(_num(row.get(field)) is None for field in REQUIRED_TRIGGER_OUTCOME_FIELDS)
    )
    missing_event_time_baseline_rows = sum(
        1
        for row in triggered_reviewed
        if any(_num(row.get(field)) is None for field in REQUIRED_EVENT_TIME_BASELINE_FIELDS)
    )
    missing_source_timing_rows = sum(1 for row in reviewed if _missing_source_timing(row))
    pit_violation_rows = sum(1 for row in reviewed if _point_in_time_violation(row))
    post_decision_source_rows = sum(1 for row in reviewed if _post_decision_source(row))
    mfe_values = _nums(row.get("max_favorable_excursion") for row in triggered_reviewed)
    mae_values = _nums(row.get("max_adverse_excursion") for row in triggered_reviewed)
    avg_mfe = _mean(mfe_values)
    avg_mae = _mean(mae_values)
    mfe_mae_ratio = (
        abs(avg_mfe) / abs(avg_mae)
        if avg_mfe is not None and avg_mae not in (None, 0)
        else None
    )
    avg_24h = _mean(_nums(row.get("post_event_return_24h") for row in triggered_reviewed))
    avg_72h = _mean(_nums(row.get("post_event_return_72h") for row in triggered_reviewed))
    avg_7d = _mean(_nums(row.get("post_event_return_7d") for row in triggered_reviewed))
    avg_event_time_72h = _mean(_nums(row.get("event_time_post_event_return_72h") for row in triggered_reviewed))
    trigger_vs_event_time_72h_edge = _mean(_trigger_vs_event_time_72h_edges(triggered_reviewed))
    trigger_latencies = _trigger_latencies_hours(triggered_reviewed)
    avg_trigger_latency = _mean(trigger_latencies)
    median_trigger_latency = _median(trigger_latencies)
    negative_trigger_latency_rows = sum(1 for value in trigger_latencies if value < 0)
    reviewed_proxy_event_types = len(_event_types(reviewed_proxy))
    triggered_btc_risk_buckets = len(_known_btc_risk_buckets(triggered_reviewed))

    blockers: list[str] = []
    if schema_mismatches:
        blockers.append(f"{schema_mismatches} row(s) have an unknown schema_version")
    if unknown_label_rows:
        blockers.append(f"{unknown_label_rows} labeled row(s) use unknown human_label values")
    if missing_review_status_rows:
        blockers.append(
            f"{missing_review_status_rows} labeled row(s) are missing review_status=reviewed"
        )
    if missing_human_label_rows:
        blockers.append(
            f"{missing_human_label_rows} reviewed row(s) are missing human_label"
        )
    if len(reviewed_proxy) < min_proxy_candidates:
        blockers.append(
            f"reviewed proxy candidates {len(reviewed_proxy)}/{min_proxy_candidates}"
        )
    if len(negative_controls) < min_negative_controls:
        blockers.append(
            f"reviewed direct/ambiguous controls {len(negative_controls)}/{min_negative_controls}"
        )
    if len(triggered_reviewed) < min_triggered_reviewed:
        blockers.append(
            f"reviewed SHORT_TRIGGERED candidates {len(triggered_reviewed)}/{min_triggered_reviewed}"
        )
    if (
        len(reviewed_proxy) >= min_proxy_candidates
        and reviewed_proxy_event_types < min_proxy_event_types
    ):
        blockers.append(
            f"reviewed proxy event types {reviewed_proxy_event_types}/{min_proxy_event_types}"
        )
    if (
        len(triggered_reviewed) >= min_triggered_reviewed
        and triggered_btc_risk_buckets < min_trigger_btc_risk_buckets
    ):
        blockers.append(
            f"reviewed trigger BTC risk buckets {triggered_btc_risk_buckets}/{min_trigger_btc_risk_buckets}"
        )
    if trigger_precision is not None and trigger_precision < min_trigger_precision:
        blockers.append(
            f"trigger precision {_fmt_pct(trigger_precision)} below {_fmt_pct(min_trigger_precision)}"
        )
    if direct_or_nonproxy_triggered:
        blockers.append(
            f"{len(direct_or_nonproxy_triggered)} direct/non-proxy reviewed row(s) are SHORT_TRIGGERED"
        )
    if pit_violation_rows:
        blockers.append(
            f"{pit_violation_rows} reviewed row(s) use evidence first seen after the decision time"
        )
    if post_decision_source_rows:
        blockers.append(
            f"{post_decision_source_rows} reviewed row(s) include source evidence after the decision time"
        )
    if negative_trigger_latency_rows:
        blockers.append(
            f"{negative_trigger_latency_rows} reviewed SHORT_TRIGGERED row(s) trigger before event time"
        )
    if missing_trigger_outcome_rows:
        blockers.append(
            f"{missing_trigger_outcome_rows} reviewed SHORT_TRIGGERED row(s) are missing outcome fields"
        )
    if missing_event_time_baseline_rows:
        blockers.append(
            f"{missing_event_time_baseline_rows} reviewed SHORT_TRIGGERED row(s) are missing event-time baseline fields"
        )
    if missing_source_timing_rows:
        blockers.append(
            f"{missing_source_timing_rows} reviewed row(s) are missing source timing evidence"
        )
    if (
        triggered_reviewed
        and not missing_trigger_outcome_rows
        and (mfe_mae_ratio is None or mfe_mae_ratio < min_mfe_mae_ratio)
    ):
        blockers.append(
            f"MFE/MAE {_fmt_num(mfe_mae_ratio)} below {_fmt_num(min_mfe_mae_ratio)}"
        )
    if avg_72h is not None and avg_72h >= 0:
        blockers.append("reviewed SHORT_TRIGGERED rows do not show favorable 72h short returns")
    if (
        triggered_reviewed
        and not missing_event_time_baseline_rows
        and trigger_vs_event_time_72h_edge is not None
        and trigger_vs_event_time_72h_edge <= 0
    ):
        blockers.append("post-event trigger does not beat event-time short baseline at 72h")

    event_type_cohorts = _cohorts(data, lambda row: str(row.get("event_type") or "unknown"))
    relationship_type_cohorts = _cohorts(
        data,
        lambda row: str(row.get("relationship_type") or "unknown"),
    )
    btc_risk_cohorts = _cohorts(data, _btc_risk_bucket)

    return EventFadeValidationReview(
        total_rows=len(data),
        reviewed_rows=len(reviewed),
        unlabeled_rows=len(data) - len(reviewed),
        missing_review_status_rows=missing_review_status_rows,
        missing_human_label_rows=missing_human_label_rows,
        schema_mismatches=schema_mismatches,
        unknown_label_rows=unknown_label_rows,
        label_counts=label_counts,
        reviewed_proxy_candidates=len(reviewed_proxy),
        reviewed_negative_controls=len(negative_controls),
        valid_proxy_labels=valid_proxy_labels,
        triggered_reviewed=len(triggered_reviewed),
        triggered_valid=len(triggered_valid),
        direct_or_nonproxy_triggered=len(direct_or_nonproxy_triggered),
        trigger_precision=trigger_precision,
        trigger_false_positive_rate=trigger_false_positive_rate,
        avg_mfe=avg_mfe,
        avg_mae=avg_mae,
        mfe_mae_ratio=mfe_mae_ratio,
        avg_post_event_return_24h=avg_24h,
        avg_post_event_return_72h=avg_72h,
        avg_post_event_return_7d=avg_7d,
        avg_event_time_post_event_return_72h=avg_event_time_72h,
        avg_trigger_vs_event_time_return_72h_edge=trigger_vs_event_time_72h_edge,
        avg_trigger_latency_hours=avg_trigger_latency,
        median_trigger_latency_hours=median_trigger_latency,
        negative_trigger_latency_rows=negative_trigger_latency_rows,
        missing_trigger_outcome_rows=missing_trigger_outcome_rows,
        missing_event_time_baseline_rows=missing_event_time_baseline_rows,
        point_in_time_violation_rows=pit_violation_rows,
        post_decision_source_rows=post_decision_source_rows,
        missing_source_timing_rows=missing_source_timing_rows,
        min_proxy_candidates=min_proxy_candidates,
        min_negative_controls=min_negative_controls,
        min_triggered_reviewed=min_triggered_reviewed,
        min_trigger_precision=min_trigger_precision,
        min_mfe_mae_ratio=min_mfe_mae_ratio,
        min_proxy_event_types=min_proxy_event_types,
        min_trigger_btc_risk_buckets=min_trigger_btc_risk_buckets,
        reviewed_proxy_event_types=reviewed_proxy_event_types,
        triggered_btc_risk_buckets=triggered_btc_risk_buckets,
        event_type_cohorts=event_type_cohorts,
        relationship_type_cohorts=relationship_type_cohorts,
        btc_risk_cohorts=btc_risk_cohorts,
        promotion_blockers=tuple(blockers),
    )


def format_validation_review(review: EventFadeValidationReview) -> str:
    rows = [
        "=" * 78,
        "EVENT FADE VALIDATION SAMPLE REVIEW (research-only; no alerts, DB writes, paper trades, or orders)",
        "=" * 78,
        (
            f"Rows: {review.total_rows} · reviewed: {review.reviewed_rows} · "
            f"unreviewed/incomplete: {review.unlabeled_rows}"
        ),
        (
            "Coverage: "
            f"proxy={review.reviewed_proxy_candidates}/{review.min_proxy_candidates} · "
            f"direct/ambiguous controls={review.reviewed_negative_controls}/{review.min_negative_controls}"
        ),
        "",
        "LABELS",
    ]
    if review.label_counts:
        for label in sorted(review.label_counts):
            rows.append(f"  {label:<18} {review.label_counts[label]}")
    else:
        rows.append("  No reviewed labels yet.")

    rows.extend([
        "",
        "TRIGGER QUALITY",
        (
            f"  reviewed SHORT_TRIGGERED: {review.triggered_reviewed} · "
            f"minimum: {review.min_triggered_reviewed} · "
            f"valid: {review.triggered_valid} · "
            f"precision: {_fmt_pct(review.trigger_precision)} · "
            f"minimum precision: {_fmt_pct(review.min_trigger_precision)} · "
            f"false-positive rate: {_fmt_pct(review.trigger_false_positive_rate)}"
        ),
        (
            f"  proxy event types: {review.reviewed_proxy_event_types}/{review.min_proxy_event_types} · "
            f"trigger BTC risk buckets: {review.triggered_btc_risk_buckets}/{review.min_trigger_btc_risk_buckets}"
        ),
        (
            f"  trigger latency: avg={_fmt_hours(review.avg_trigger_latency_hours)} · "
            f"median={_fmt_hours(review.median_trigger_latency_hours)} · "
            f"negative rows={review.negative_trigger_latency_rows}"
        ),
        f"  direct/non-proxy SHORT_TRIGGERED rows: {review.direct_or_nonproxy_triggered}",
        f"  labeled rows missing review_status=reviewed: {review.missing_review_status_rows}",
        f"  reviewed rows missing human_label: {review.missing_human_label_rows}",
        f"  point-in-time evidence violations: {review.point_in_time_violation_rows}",
        f"  rows with post-decision source evidence: {review.post_decision_source_rows}",
        f"  reviewed rows missing source timing: {review.missing_source_timing_rows}",
        "",
        "OUTCOMES",
        (
            f"  avg MFE: {_fmt_pct(review.avg_mfe)} · "
            f"avg MAE: {_fmt_pct(review.avg_mae)} · "
            f"MFE/MAE: {_fmt_num(review.mfe_mae_ratio)} · "
            f"minimum MFE/MAE: {_fmt_num(review.min_mfe_mae_ratio)}"
        ),
        (
            f"  avg post-event return: "
            f"24h={_fmt_pct(review.avg_post_event_return_24h)} · "
            f"72h={_fmt_pct(review.avg_post_event_return_72h)} · "
            f"7d={_fmt_pct(review.avg_post_event_return_7d)}"
        ),
        (
            f"  event-time short baseline: "
            f"72h={_fmt_pct(review.avg_event_time_post_event_return_72h)} · "
            f"trigger edge vs baseline={_fmt_pp(review.avg_trigger_vs_event_time_return_72h_edge)}"
        ),
        f"  reviewed triggered rows missing required outcomes: {review.missing_trigger_outcome_rows}",
        f"  reviewed triggered rows missing event-time baseline: {review.missing_event_time_baseline_rows}",
        "",
        "COHORTS",
        "  By event type:",
        *_format_cohort_lines(review.event_type_cohorts),
        "  By relationship type:",
        *_format_cohort_lines(review.relationship_type_cohorts),
        "  By BTC risk bucket:",
        *_format_cohort_lines(review.btc_risk_cohorts),
        "",
        "NEXT SAMPLE WORK",
        *_format_next_step_lines(validation_review_next_steps(review)),
        "",
        "PROMOTION STATUS",
    ])
    if review.promotion_ready:
        rows.append("  READY FOR HUMAN DECISION (this report does not promote automatically)")
    else:
        rows.append("  BLOCKED")
        for blocker in review.promotion_blockers:
            rows.append(f"  - {blocker}")
    return "\n".join(rows)


def validation_review_next_steps(review: EventFadeValidationReview) -> tuple[str, ...]:
    """Return concrete review work needed before event-fade promotion evidence is meaningful."""
    steps: list[str] = []
    if review.schema_mismatches:
        steps.append(
            f"Regenerate or migrate {review.schema_mismatches} row(s) with unknown schema_version."
        )
    if review.unknown_label_rows:
        steps.append(
            f"Fix {review.unknown_label_rows} labeled row(s) with unknown human_label values."
        )
    if review.missing_review_status_rows:
        steps.append(
            f"Set review_status=reviewed for {review.missing_review_status_rows} labeled row(s), "
            "or clear labels that are not fully reviewed."
        )
    if review.missing_human_label_rows:
        steps.append(
            f"Fill human_label for {review.missing_human_label_rows} row(s) marked reviewed."
        )
    if review.point_in_time_violation_rows:
        steps.append(
            f"Review or remove {review.point_in_time_violation_rows} row(s) first seen after decision time."
        )
    if review.post_decision_source_rows:
        steps.append(
            f"Review or remove {review.post_decision_source_rows} row(s) with post-decision source evidence."
        )
    if review.missing_source_timing_rows:
        steps.append(
            f"Add source timing evidence or remove {review.missing_source_timing_rows} reviewed row(s)."
        )
    proxy_gap = max(0, review.min_proxy_candidates - review.reviewed_proxy_candidates)
    if proxy_gap:
        steps.append(
            f"Add/review {proxy_gap} more proxy candidate row(s) "
            f"(current {review.reviewed_proxy_candidates}/{review.min_proxy_candidates})."
        )
    control_gap = max(0, review.min_negative_controls - review.reviewed_negative_controls)
    if control_gap:
        steps.append(
            f"Add/review {control_gap} more direct or ambiguous control row(s) "
            f"(current {review.reviewed_negative_controls}/{review.min_negative_controls})."
        )
    trigger_gap = max(0, review.min_triggered_reviewed - review.triggered_reviewed)
    if trigger_gap:
        steps.append(
            f"Add/review {trigger_gap} more SHORT_TRIGGERED row(s) with outcomes "
            f"(current {review.triggered_reviewed}/{review.min_triggered_reviewed})."
        )
    if (
        review.reviewed_proxy_candidates >= review.min_proxy_candidates
        and review.reviewed_proxy_event_types < review.min_proxy_event_types
    ):
        event_type_gap = review.min_proxy_event_types - review.reviewed_proxy_event_types
        steps.append(
            f"Add proxy examples from {event_type_gap} more event type(s) "
            f"(current {review.reviewed_proxy_event_types}/{review.min_proxy_event_types})."
        )
    if (
        review.triggered_reviewed >= review.min_triggered_reviewed
        and review.triggered_btc_risk_buckets < review.min_trigger_btc_risk_buckets
    ):
        risk_bucket_gap = review.min_trigger_btc_risk_buckets - review.triggered_btc_risk_buckets
        steps.append(
            f"Add triggered examples from {risk_bucket_gap} more BTC risk bucket(s) "
            f"(current {review.triggered_btc_risk_buckets}/{review.min_trigger_btc_risk_buckets})."
        )
    if review.missing_trigger_outcome_rows:
        steps.append(
            f"Fill trigger outcome fields for {review.missing_trigger_outcome_rows} reviewed triggered row(s)."
        )
    if review.missing_event_time_baseline_rows:
        steps.append(
            f"Fill event-time baseline outcomes for {review.missing_event_time_baseline_rows} reviewed triggered row(s)."
        )
    if review.negative_trigger_latency_rows:
        steps.append(
            f"Inspect {review.negative_trigger_latency_rows} triggered row(s) whose trigger precedes event time."
        )
    if steps:
        return tuple(steps)
    if review.promotion_ready:
        return (
            "Mechanical review gates are satisfied; explicit human approval is still required before promotion.",
        )
    return (
        "Resolve the promotion blockers above before expanding or promoting the sample.",
    )


def _format_next_step_lines(steps: tuple[str, ...]) -> list[str]:
    return [f"  - {step}" for step in steps]


def _format_cohort_lines(cohorts: tuple[ValidationCohort, ...]) -> list[str]:
    if not cohorts:
        return ["    none"]
    rows: list[str] = []
    for cohort in cohorts:
        rows.append(
            "    "
            f"{cohort.name:<24} rows={cohort.total_rows:<3} "
            f"reviewed={cohort.reviewed_rows:<3} "
            f"proxy={cohort.reviewed_proxy_candidates:<3} "
            f"controls={cohort.reviewed_negative_controls:<3} "
            f"trig={cohort.triggered_reviewed:<3} "
            f"precision={_fmt_pct(cohort.trigger_precision):<6} "
            f"mfe/mae={_fmt_num(cohort.mfe_mae_ratio):<5} "
            f"72h={_fmt_pct(cohort.avg_post_event_return_72h)}"
        )
    return rows


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
        key=lambda pair: (
            pair[0].priority,
            pair[0].event_time or "",
            pair[0].asset_symbol,
            pair[0].event_name,
        )
    )
    return pairs[: max(0, limit)] if limit is not None else pairs


def _format_review_packet_row(
    idx: int,
    item: ValidationLabelingQueueItem,
    row: Mapping[str, Any],
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
        f"- Suggested label: `{item.suggested_label}`",
        f"- Missing fields: `{missing}`",
        f"- Current label: `{current_label}`",
        f"- Event: `{_packet_text(row.get('event_type'))}` at `{_packet_text(item.event_time or 'unknown')}`",
        (
            f"- First seen: `{_packet_text(row.get('first_seen_time'))}` | "
            f"published=`{_packet_text(row.get('published_at_min'))}`..`{_packet_text(row.get('published_at_max'))}` | "
            f"fetched=`{_packet_text(row.get('fetched_at_min'))}`..`{_packet_text(row.get('fetched_at_max'))}`"
        ),
        (
            f"- Asset: `{symbol}` (`{coin_id}`) | relationship: "
            f"`{_packet_text(item.relationship_type or 'unknown')}`"
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
            f"MAE=`{_fmt_pct(_num(row.get('max_adverse_excursion')))}`"
        ),
        (
            "- Event-time baseline: "
            f"entry=`{_fmt_num(_num(row.get('event_time_entry_price')))}` | "
            f"72h=`{_fmt_pct(_num(row.get('event_time_post_event_return_72h')))}` | "
            f"trigger edge=`{_fmt_pp(edge_72h[0] if edge_72h else None)}`"
        ),
        f"- Classifier reason: {_packet_text(row.get('classification_reason'))}",
    ]
    fields.extend(_packet_bullets("Classifier evidence", row.get("classification_evidence")))
    fields.extend(_packet_bullets("Reason codes", row.get("reason_codes")))
    fields.extend(_packet_bullets("Warnings", row.get("warnings")))
    fields.extend(_packet_bullets("Missing data", row.get("missing_data")))
    fields.extend(_packet_bullets("Sources", row.get("source_urls")))
    fields.extend(_packet_bullets("Raw titles", row.get("raw_titles")))
    fields.extend([
        "- Review fields to fill:",
        "  - `review_status`: `reviewed`",
        "  - `human_label`: `valid_proxy_fade` | `false_positive` | `direct_event` | `ambiguous`",
        "  - `human_notes`: evidence-backed note",
    ])
    return fields


def _review_template_row(
    item: ValidationLabelingQueueItem,
    row: Mapping[str, Any],
) -> dict[str, Any]:
    out = {field: row.get(field) for field in REVIEW_TEMPLATE_FIELDS}
    out.update({
        "queue_category": item.category,
        "suggested_label": item.suggested_label,
        "missing_fields": list(item.missing_fields),
        "source_urls": list(item.source_urls),
    })
    return out


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


def _review_template_json_ready(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        field: _review_template_json_value(row.get(field))
        for field in REVIEW_TEMPLATE_FIELDS
    }


def _review_template_json_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _review_template_json_value(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_review_template_json_value(item) for item in value]
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return value


def _review_template_csv_cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (Mapping, list, tuple)):
        return json.dumps(_review_template_json_value(value), sort_keys=True)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _price_index_from_mapping(raw: Mapping[str, Any]) -> dict[str, list[ValidationOutcomeCandle]]:
    out: dict[str, list[ValidationOutcomeCandle]] = {}
    for key, values in raw.items():
        if key == "prices":
            continue
        if not isinstance(values, list):
            continue
        candles = [_parse_price_candle(item) for item in values]
        parsed = [candle for candle in candles if candle is not None]
        if parsed:
            out[_asset_key(key)] = sorted(parsed, key=lambda candle: candle.timestamp)
    return out


def _price_index_from_flat_rows(items: Iterable[Any]) -> dict[str, list[ValidationOutcomeCandle]]:
    out: dict[str, list[ValidationOutcomeCandle]] = {}
    for item in items:
        if not isinstance(item, Mapping):
            continue
        candle = _parse_price_candle(item)
        if candle is None:
            continue
        keys = _price_row_keys(item)
        for key in keys:
            out.setdefault(key, []).append(candle)
    return {
        key: sorted(candles, key=lambda candle: candle.timestamp)
        for key, candles in out.items()
    }


def _parse_price_candle(item: Mapping[str, Any]) -> ValidationOutcomeCandle | None:
    ts = _dt(item.get("timestamp") or item.get("time") or item.get("date"))
    close = _num(item.get("close") or item.get("price"))
    if ts is None or close is None or close <= 0:
        return None
    high = _num(item.get("high"))
    low = _num(item.get("low"))
    return ValidationOutcomeCandle(
        timestamp=ts,
        close=close,
        high=high if high is not None and high > 0 else None,
        low=low if low is not None and low > 0 else None,
    )


def _price_row_keys(item: Mapping[str, Any]) -> tuple[str, ...]:
    keys = {
        _asset_key(item.get("asset_coin_id")),
        _asset_key(item.get("coin_id")),
        _asset_key(item.get("id")),
        _asset_key(item.get("asset_symbol")),
        _asset_key(item.get("symbol")),
    }
    return tuple(key for key in keys if key)


def _candles_for_row(
    row: Mapping[str, Any],
    price_index: Mapping[str, list[ValidationOutcomeCandle]],
) -> list[ValidationOutcomeCandle]:
    for key in (
        _asset_key(row.get("asset_coin_id")),
        _asset_key(row.get("asset_symbol")),
    ):
        if key and key in price_index:
            return price_index[key]
    return []


def _short_outcome(
    candles: list[ValidationOutcomeCandle],
    decision_time: datetime,
    *,
    entry_price: float | None = None,
) -> dict[str, float] | None:
    entry = entry_price or _close_asof(candles, decision_time)
    if entry is None or entry <= 0:
        return None
    future = [
        candle for candle in candles
        if decision_time < candle.timestamp <= decision_time + timedelta(days=7)
    ]
    if not future:
        return None
    lows = [candle.low if candle.low is not None else candle.close for candle in future]
    highs = [candle.high if candle.high is not None else candle.close for candle in future]
    outcome: dict[str, float] = {
        "entry_price": entry,
        "max_favorable_excursion": max(0.0, (entry - min(lows)) / entry),
        "max_adverse_excursion": max(0.0, (max(highs) - entry) / entry),
    }
    for hours, field in (
        (24, "post_event_return_24h"),
        (72, "post_event_return_72h"),
        (168, "post_event_return_7d"),
    ):
        close = _close_asof_after(candles, decision_time, decision_time + timedelta(hours=hours))
        if close is not None:
            outcome[field] = close / entry - 1.0
    return outcome if all(field in outcome for field in REQUIRED_TRIGGER_OUTCOME_FIELDS) else None


def _event_time_outcome_fields(outcome: Mapping[str, float]) -> dict[str, float]:
    return {
        "event_time_entry_price": outcome.get("entry_price"),
        "event_time_max_adverse_excursion": outcome.get("max_adverse_excursion"),
        "event_time_max_favorable_excursion": outcome.get("max_favorable_excursion"),
        "event_time_post_event_return_24h": outcome.get("post_event_return_24h"),
        "event_time_post_event_return_72h": outcome.get("post_event_return_72h"),
        "event_time_post_event_return_7d": outcome.get("post_event_return_7d"),
    }


def _close_asof(
    candles: list[ValidationOutcomeCandle],
    ts: datetime,
) -> float | None:
    prior = [candle.close for candle in candles if candle.timestamp <= ts]
    return prior[-1] if prior else None


def _close_asof_after(
    candles: list[ValidationOutcomeCandle],
    start: datetime,
    ts: datetime,
) -> float | None:
    prior = [candle.close for candle in candles if start < candle.timestamp <= ts]
    return prior[-1] if prior else None


def _asset_key(value: object) -> str:
    return str(value or "").strip().casefold()


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
    if label and _point_in_time_violation(row):
        return _queue_item(
            row,
            priority=3,
            category="fix_point_in_time_evidence",
            suggested_label=label,
            missing_fields=(),
        )
    if label and _post_decision_source(row):
        return _queue_item(
            row,
            priority=4,
            category="review_post_decision_source",
            suggested_label=label,
            missing_fields=(),
        )
    if label and _missing_source_timing(row):
        return _queue_item(
            row,
            priority=5,
            category="add_source_timing",
            suggested_label=label,
            missing_fields=("first_seen_time", "raw_published_at", "raw_fetched_at"),
        )
    if triggered and not label:
        return _queue_item(
            row,
            priority=6,
            category="label_triggered_candidate",
            suggested_label=_suggested_label(row),
            missing_fields=("human_label", *missing_required_outcomes),
        )
    if triggered and missing_required_outcomes:
        return _queue_item(
            row,
            priority=7,
            category="fill_trigger_outcomes",
            suggested_label=label or _suggested_label(row),
            missing_fields=missing_required_outcomes,
        )
    if not label and _is_proxy_candidate(row):
        return _queue_item(
            row,
            priority=8,
            category="label_proxy_candidate",
            suggested_label="valid_proxy_fade or false_positive",
            missing_fields=("human_label",),
        )
    if not label and _is_direct_or_ambiguous(row):
        return _queue_item(
            row,
            priority=9,
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
        trigger_observed_at=_string_or_none(row.get("trigger_observed_at")),
        human_label=_label(row),
        suggested_label=suggested_label,
        missing_fields=missing_fields,
        source_urls=tuple(str(value) for value in _list_values(row.get("source_urls")) if value),
    )


def _suggested_label(row: Mapping[str, Any]) -> str:
    if _is_proxy_candidate(row):
        return "valid_proxy_fade or false_positive"
    if _bool(row.get("is_direct_beneficiary")):
        return "direct_event"
    relation = str(row.get("relationship_type") or "").strip()
    if relation == "ambiguous":
        return "ambiguous"
    return "direct_event or ambiguous"


def _parse_csv_row(row: Mapping[str, str]) -> dict[str, Any]:
    return {key: _parse_csv_cell(value) for key, value in row.items()}


def _parse_csv_cell(value: str | None) -> Any:
    if value is None or value == "":
        return None
    raw = value.strip()
    if raw in {"True", "true"}:
        return True
    if raw in {"False", "false"}:
        return False
    if raw.startswith(("{", "[")):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return value
    try:
        if any(ch in raw for ch in (".", "e", "E")):
            return float(raw)
        return int(raw)
    except ValueError:
        return value


def _label(row: Mapping[str, Any]) -> str:
    return str(row.get("human_label") or "").strip()


def _review_status(row: Mapping[str, Any]) -> str:
    return str(row.get("review_status") or "").strip().casefold()


def _signal_type(row: Mapping[str, Any]) -> str:
    return str(row.get("signal_type") or "").strip()


def _sample_key(row: Mapping[str, Any]) -> tuple[str, str, str] | None:
    event_id = str(row.get("event_id") or "").strip()
    coin_id = str(row.get("asset_coin_id") or "").strip().casefold()
    relationship = str(row.get("relationship_type") or "").strip().casefold()
    if event_id and coin_id and relationship:
        return (event_id, coin_id, relationship)
    event_name = str(row.get("event_name") or "").strip().casefold()
    symbol = str(row.get("asset_symbol") or "").strip().casefold()
    if event_name and symbol and relationship:
        return (event_name, symbol, relationship)
    return None


def _has_review_data(row: Mapping[str, Any]) -> bool:
    return any(_has_value(row.get(field)) for field in REVIEW_FIELDS)


def _changed_evidence_fields(
    fresh: Mapping[str, Any],
    reviewed: Mapping[str, Any],
    evidence_fields: Iterable[str],
) -> tuple[str, ...]:
    return tuple(
        field
        for field in evidence_fields
        if _fingerprint_value(fresh.get(field)) != _fingerprint_value(reviewed.get(field))
    )


def _evidence_change_item(
    row: Mapping[str, Any],
    changed_fields: tuple[str, ...],
) -> ValidationSampleEvidenceChange:
    return ValidationSampleEvidenceChange(
        event_id=str(row.get("event_id") or ""),
        asset_symbol=str(row.get("asset_symbol") or ""),
        asset_coin_id=str(row.get("asset_coin_id") or ""),
        relationship_type=str(row.get("relationship_type") or ""),
        changed_fields=changed_fields,
    )


def _fingerprint_value(value: object) -> str:
    normalized = _fingerprint_normalized(value)
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def _fingerprint_normalized(value: object) -> object:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        raw = value.strip()
        if raw == "":
            return None
        if raw in {"True", "true"}:
            return True
        if raw in {"False", "false"}:
            return False
        if raw.startswith(("{", "[")):
            try:
                return _fingerprint_normalized(json.loads(raw))
            except json.JSONDecodeError:
                return raw
        return raw
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return format(value, ".12g")
    if isinstance(value, Mapping):
        return {
            str(key): _fingerprint_normalized(nested)
            for key, nested in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple, set)):
        normalized = [_fingerprint_normalized(item) for item in value]
        return sorted(
            normalized,
            key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
        )
    return str(value).strip()


def _has_value(value: object) -> bool:
    return value is not None and value != ""


def _string_or_none(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _list_values(value: object) -> list[Any]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        raw = value.strip()
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                return [value]
            return parsed if isinstance(parsed, list) else [value]
        return [value]
    return [value]


def _is_proxy_candidate(row: Mapping[str, Any]) -> bool:
    return _bool(row.get("is_proxy_narrative")) and not _bool(row.get("is_direct_beneficiary"))


def _is_direct_or_ambiguous(row: Mapping[str, Any]) -> bool:
    relation = str(row.get("relationship_type") or "").strip()
    return _bool(row.get("is_direct_beneficiary")) or relation == "ambiguous" or not _is_proxy_candidate(row)


def _point_in_time_violation(row: Mapping[str, Any]) -> bool:
    decision_time = _decision_time(row)
    if decision_time is None:
        return _signal_type(row) in {"WATCHLIST", "SHORT_TRIGGERED"}
    known_times = _source_known_times(row, include_max=False)
    return bool(known_times) and min(known_times) > decision_time


def _post_decision_source(row: Mapping[str, Any]) -> bool:
    decision_time = _decision_time(row)
    if decision_time is None:
        return False
    return any(value > decision_time for value in _source_known_times(row, include_max=True))


def _missing_source_timing(row: Mapping[str, Any]) -> bool:
    return not _source_known_times(row, include_max=True)


def _decision_time(row: Mapping[str, Any]) -> datetime | None:
    signal_type = _signal_type(row)
    if signal_type == "SHORT_TRIGGERED":
        return _dt(row.get("trigger_observed_at"))
    return _dt(row.get("event_time"))


def _source_known_times(row: Mapping[str, Any], *, include_max: bool) -> list[datetime]:
    known_times = [
        _dt(row.get("first_seen_time")),
        _dt(row.get("fetched_at_min")),
        _dt(row.get("published_at_min")),
    ]
    if include_max:
        known_times.extend([
            _dt(row.get("fetched_at_max")),
            _dt(row.get("published_at_max")),
        ])
        known_times.extend(_dt(value) for value in _list_values(row.get("raw_fetched_at")))
        known_times.extend(_dt(value) for value in _list_values(row.get("raw_published_at")))
    return [value for value in known_times if value is not None]


def _label_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        label = _label(row)
        counts[label] = counts.get(label, 0) + 1
    return counts


def _trigger_vs_event_time_72h_edges(rows: Iterable[Mapping[str, Any]]) -> list[float]:
    out: list[float] = []
    for row in rows:
        trigger_return = _num(row.get("post_event_return_72h"))
        event_time_return = _num(row.get("event_time_post_event_return_72h"))
        if trigger_return is None or event_time_return is None:
            continue
        # Lower post-entry returns are better for a short, so positive means
        # the confirmed trigger beat a naive short at the event timestamp.
        out.append(event_time_return - trigger_return)
    return out


def _trigger_latencies_hours(rows: Iterable[Mapping[str, Any]]) -> list[float]:
    out: list[float] = []
    for row in rows:
        event_time = _dt(row.get("event_time"))
        trigger_time = _dt(row.get("trigger_observed_at"))
        if event_time is None or trigger_time is None:
            continue
        out.append((trigger_time - event_time).total_seconds() / 3600.0)
    return out


def _event_types(rows: Iterable[Mapping[str, Any]]) -> set[str]:
    out: set[str] = set()
    for row in rows:
        value = str(row.get("event_type") or "").strip()
        if value:
            out.add(value)
    return out


def _known_btc_risk_buckets(rows: Iterable[Mapping[str, Any]]) -> set[str]:
    return {
        bucket
        for row in rows
        if (bucket := _btc_risk_bucket(row)) != "btc_risk_unknown"
    }


def _cohorts(
    rows: Iterable[Mapping[str, Any]],
    key_fn,
) -> tuple[ValidationCohort, ...]:
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        key = str(key_fn(row) or "unknown").strip() or "unknown"
        groups.setdefault(key, []).append(row)
    cohorts = [_cohort(name, group) for name, group in groups.items()]
    return tuple(sorted(cohorts, key=lambda item: (-item.reviewed_rows, -item.total_rows, item.name)))


def _cohort(name: str, rows: list[Mapping[str, Any]]) -> ValidationCohort:
    reviewed = [row for row in rows if _is_reviewed_evidence(row)]
    reviewed_proxy = [row for row in reviewed if _is_proxy_candidate(row)]
    negative_controls = [
        row
        for row in reviewed
        if _label(row) in CONTROL_LABELS or _is_direct_or_ambiguous(row)
    ]
    triggered_reviewed = [row for row in reviewed if _signal_type(row) == "SHORT_TRIGGERED"]
    triggered_valid = [row for row in triggered_reviewed if _label(row) == POSITIVE_LABEL]
    trigger_precision = (
        len(triggered_valid) / len(triggered_reviewed)
        if triggered_reviewed
        else None
    )
    mfe_values = _nums(row.get("max_favorable_excursion") for row in triggered_reviewed)
    mae_values = _nums(row.get("max_adverse_excursion") for row in triggered_reviewed)
    avg_mfe = _mean(mfe_values)
    avg_mae = _mean(mae_values)
    mfe_mae_ratio = (
        abs(avg_mfe) / abs(avg_mae)
        if avg_mfe is not None and avg_mae not in (None, 0)
        else None
    )
    avg_72h = _mean(_nums(row.get("post_event_return_72h") for row in triggered_reviewed))
    return ValidationCohort(
        name=name,
        total_rows=len(rows),
        reviewed_rows=len(reviewed),
        reviewed_proxy_candidates=len(reviewed_proxy),
        reviewed_negative_controls=len(negative_controls),
        triggered_reviewed=len(triggered_reviewed),
        triggered_valid=len(triggered_valid),
        trigger_precision=trigger_precision,
        avg_mfe=avg_mfe,
        avg_mae=avg_mae,
        mfe_mae_ratio=mfe_mae_ratio,
        avg_post_event_return_72h=avg_72h,
    )


def _is_reviewed_evidence(row: Mapping[str, Any]) -> bool:
    return _review_status(row) == "reviewed" and _label(row) in KNOWN_LABELS


def _btc_risk_bucket(row: Mapping[str, Any]) -> str:
    score = _num(row.get("btc_risk_on_score"))
    if score is None:
        return "btc_risk_unknown"
    if score >= 80:
        return "btc_risk_on_high"
    if score >= 60:
        return "btc_risk_on_elevated"
    if score <= 30:
        return "btc_risk_off"
    return "btc_risk_neutral"


def _bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().casefold()
    return text in {"true", "1", "yes", "y"}


def _num(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dt(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _nums(values: Iterable[object]) -> list[float]:
    out: list[float] = []
    for value in values:
        n = _num(value)
        if n is not None:
            out.append(n)
    return out


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _fmt_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def _fmt_num(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def _fmt_pp(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:+.1f}pp"


def _fmt_hours(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1f}h"
