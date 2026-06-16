"""Review metrics for event-fade validation sample exports.

This module is research-only. It reads local JSONL/CSV artifacts produced by
the event-discovery exporter and summarizes manual labels/outcomes. It never
routes alerts, opens paper trades, writes live storage, or implies execution.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .event_discovery import VALIDATION_SAMPLE_SCHEMA_VERSION


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


@dataclass(frozen=True)
class EventFadeValidationReview:
    total_rows: int
    reviewed_rows: int
    unlabeled_rows: int
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
    missing_trigger_outcome_rows: int
    point_in_time_violation_rows: int
    min_proxy_candidates: int
    min_negative_controls: int
    min_triggered_reviewed: int
    min_trigger_precision: float
    min_mfe_mae_ratio: float
    promotion_blockers: tuple[str, ...]

    @property
    def promotion_ready(self) -> bool:
        return not self.promotion_blockers


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


def review_validation_sample(
    rows: Iterable[Mapping[str, Any]],
    *,
    min_proxy_candidates: int = 25,
    min_negative_controls: int = 50,
    min_triggered_reviewed: int = 10,
    min_trigger_precision: float = 0.60,
    min_mfe_mae_ratio: float = 1.50,
) -> EventFadeValidationReview:
    """Summarize manual labels/outcomes and promotion blockers."""
    data = [dict(row) for row in rows]
    reviewed = [row for row in data if _label(row)]
    label_counts = _label_counts(reviewed)
    unknown_label_rows = sum(1 for row in reviewed if _label(row) not in KNOWN_LABELS)
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
    pit_violation_rows = sum(1 for row in reviewed if _point_in_time_violation(row))
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

    blockers: list[str] = []
    if schema_mismatches:
        blockers.append(f"{schema_mismatches} row(s) have an unknown schema_version")
    if unknown_label_rows:
        blockers.append(f"{unknown_label_rows} reviewed row(s) use unknown human_label values")
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
    if missing_trigger_outcome_rows:
        blockers.append(
            f"{missing_trigger_outcome_rows} reviewed SHORT_TRIGGERED row(s) are missing outcome fields"
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

    return EventFadeValidationReview(
        total_rows=len(data),
        reviewed_rows=len(reviewed),
        unlabeled_rows=len(data) - len(reviewed),
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
        missing_trigger_outcome_rows=missing_trigger_outcome_rows,
        point_in_time_violation_rows=pit_violation_rows,
        min_proxy_candidates=min_proxy_candidates,
        min_negative_controls=min_negative_controls,
        min_triggered_reviewed=min_triggered_reviewed,
        min_trigger_precision=min_trigger_precision,
        min_mfe_mae_ratio=min_mfe_mae_ratio,
        promotion_blockers=tuple(blockers),
    )


def format_validation_review(review: EventFadeValidationReview) -> str:
    rows = [
        "=" * 78,
        "EVENT FADE VALIDATION SAMPLE REVIEW (research-only; no alerts, DB writes, paper trades, or orders)",
        "=" * 78,
        f"Rows: {review.total_rows} · reviewed: {review.reviewed_rows} · unlabeled: {review.unlabeled_rows}",
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
        f"  direct/non-proxy SHORT_TRIGGERED rows: {review.direct_or_nonproxy_triggered}",
        f"  point-in-time evidence violations: {review.point_in_time_violation_rows}",
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
        f"  reviewed triggered rows missing required outcomes: {review.missing_trigger_outcome_rows}",
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


def _signal_type(row: Mapping[str, Any]) -> str:
    return str(row.get("signal_type") or "").strip()


def _is_proxy_candidate(row: Mapping[str, Any]) -> bool:
    return _bool(row.get("is_proxy_narrative")) and not _bool(row.get("is_direct_beneficiary"))


def _is_direct_or_ambiguous(row: Mapping[str, Any]) -> bool:
    relation = str(row.get("relationship_type") or "").strip()
    return _bool(row.get("is_direct_beneficiary")) or relation == "ambiguous" or not _is_proxy_candidate(row)


def _point_in_time_violation(row: Mapping[str, Any]) -> bool:
    signal_type = _signal_type(row)
    if signal_type == "WATCHLIST":
        decision_time = _dt(row.get("event_time"))
    elif signal_type == "SHORT_TRIGGERED":
        decision_time = _dt(row.get("trigger_observed_at"))
    else:
        return False
    if decision_time is None:
        return True
    known_times = [
        _dt(row.get("first_seen_time")),
        _dt(row.get("fetched_at_min")),
        _dt(row.get("published_at_min")),
    ]
    known_times = [value for value in known_times if value is not None]
    return bool(known_times) and min(known_times) > decision_time


def _label_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        label = _label(row)
        counts[label] = counts.get(label, 0) + 1
    return counts


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


def _fmt_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def _fmt_num(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"
