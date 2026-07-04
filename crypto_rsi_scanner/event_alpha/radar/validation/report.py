"""Validation review report rendering."""

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
from .models import *  # noqa: F403 - split modules share legacy model names


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
            f"proxy source providers: {review.reviewed_proxy_source_providers}/{review.min_proxy_source_providers} · "
            f"proxy source origins: {review.reviewed_proxy_source_origins} · "
            f"trigger BTC risk buckets: {review.triggered_btc_risk_buckets}/{review.min_trigger_btc_risk_buckets}"
        ),
        (
            f"  trigger latency: avg={_fmt_hours(review.avg_trigger_latency_hours)} · "
            f"median={_fmt_hours(review.median_trigger_latency_hours)} · "
            f"negative rows={review.negative_trigger_latency_rows}"
        ),
        (
            f"  low-confidence trigger event times: {review.low_confidence_trigger_event_time_rows} · "
            f"minimum confidence: {_fmt_pct(review.min_trigger_event_time_confidence)}"
        ),
        f"  direct/non-proxy SHORT_TRIGGERED rows: {review.direct_or_nonproxy_triggered}",
        f"  labeled rows missing review_status=reviewed: {review.missing_review_status_rows}",
        f"  reviewed rows missing human_label: {review.missing_human_label_rows}",
        f"  reviewed rows missing provenance: {review.missing_review_provenance_rows}",
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
        "  By asset role:",
        *_format_cohort_lines(review.asset_role_cohorts),
        "  By event time source:",
        *_format_cohort_lines(review.event_time_source_cohorts),
        "  By source provider:",
        *_format_cohort_lines(review.source_provider_cohorts),
        "  By source origin:",
        *_format_cohort_lines(review.source_origin_cohorts),
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
