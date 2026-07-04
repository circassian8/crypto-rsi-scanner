"""Validation review scoring helpers."""

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


@dataclass(frozen=True)
class _ValidationReviewThresholds:
    min_proxy_candidates: int
    min_negative_controls: int
    min_triggered_reviewed: int
    min_trigger_precision: float
    min_mfe_mae_ratio: float
    min_trigger_event_time_confidence: float
    min_proxy_event_types: int
    min_proxy_source_providers: int
    min_trigger_btc_risk_buckets: int


@dataclass(frozen=True)
class _ValidationReviewGroups:
    data: list[dict[str, Any]]
    reviewed: list[dict[str, Any]]
    reviewed_proxy: list[dict[str, Any]]
    negative_controls: list[dict[str, Any]]
    triggered_reviewed: list[dict[str, Any]]
    triggered_valid: list[dict[str, Any]]
    direct_or_nonproxy_triggered: list[dict[str, Any]]
    label_counts: Counter[str]


@dataclass(frozen=True)
class _ValidationReviewMetrics:
    missing_review_status_rows: int
    missing_human_label_rows: int
    missing_review_provenance_rows: int
    schema_mismatches: int
    unknown_label_rows: int
    valid_proxy_labels: int
    trigger_precision: float | None
    trigger_false_positive_rate: float | None
    avg_mfe: float | None
    avg_mae: float | None
    mfe_mae_ratio: float | None
    avg_24h: float | None
    avg_72h: float | None
    avg_7d: float | None
    avg_event_time_72h: float | None
    trigger_vs_event_time_72h_edge: float | None
    avg_trigger_latency: float | None
    median_trigger_latency: float | None
    negative_trigger_latency_rows: int
    missing_trigger_outcome_rows: int
    missing_event_time_baseline_rows: int
    low_confidence_trigger_event_time_rows: int
    missing_source_timing_rows: int
    pit_violation_rows: int
    post_decision_source_rows: int
    reviewed_proxy_event_types: int
    reviewed_proxy_source_providers: int
    reviewed_proxy_source_origins: int
    triggered_btc_risk_buckets: int


@dataclass(frozen=True)
class _ValidationReviewCohorts:
    event_type_cohorts: tuple[EventFadeValidationCohort, ...]
    relationship_type_cohorts: tuple[EventFadeValidationCohort, ...]
    asset_role_cohorts: tuple[EventFadeValidationCohort, ...]
    event_time_source_cohorts: tuple[EventFadeValidationCohort, ...]
    source_provider_cohorts: tuple[EventFadeValidationCohort, ...]
    source_origin_cohorts: tuple[EventFadeValidationCohort, ...]
    btc_risk_cohorts: tuple[EventFadeValidationCohort, ...]


def review_validation_sample(
    rows: Iterable[Mapping[str, Any]],
    *,
    min_proxy_candidates: int = 25,
    min_negative_controls: int = 50,
    min_triggered_reviewed: int = 10,
    min_trigger_precision: float = 0.60,
    min_mfe_mae_ratio: float = 1.50,
    min_trigger_event_time_confidence: float = DEFAULT_MIN_TRIGGER_EVENT_TIME_CONFIDENCE,
    min_proxy_event_types: int = 2,
    min_proxy_source_providers: int = 2,
    min_trigger_btc_risk_buckets: int = 2,
) -> EventFadeValidationReview:
    """Summarize manual review status, labels, outcomes, and promotion blockers."""
    data = [dict(row) for row in rows]
    thresholds = _validation_review_thresholds(
        min_proxy_candidates=min_proxy_candidates,
        min_negative_controls=min_negative_controls,
        min_triggered_reviewed=min_triggered_reviewed,
        min_trigger_precision=min_trigger_precision,
        min_mfe_mae_ratio=min_mfe_mae_ratio,
        min_trigger_event_time_confidence=min_trigger_event_time_confidence,
        min_proxy_event_types=min_proxy_event_types,
        min_proxy_source_providers=min_proxy_source_providers,
        min_trigger_btc_risk_buckets=min_trigger_btc_risk_buckets,
    )
    groups = _validation_review_groups(data)
    metrics = _validation_review_metrics(groups, thresholds)
    blockers = _validation_review_blockers(groups, metrics, thresholds)
    cohorts = _validation_review_cohorts(data)
    return _validation_review_result(groups, metrics, thresholds, blockers, cohorts)


def _validation_review_thresholds(
    *,
    min_proxy_candidates: int,
    min_negative_controls: int,
    min_triggered_reviewed: int,
    min_trigger_precision: float,
    min_mfe_mae_ratio: float,
    min_trigger_event_time_confidence: float,
    min_proxy_event_types: int,
    min_proxy_source_providers: int,
    min_trigger_btc_risk_buckets: int,
) -> _ValidationReviewThresholds:
    return _ValidationReviewThresholds(
        min_proxy_candidates=min_proxy_candidates,
        min_negative_controls=min_negative_controls,
        min_triggered_reviewed=min_triggered_reviewed,
        min_trigger_precision=min_trigger_precision,
        min_mfe_mae_ratio=min_mfe_mae_ratio,
        min_trigger_event_time_confidence=min_trigger_event_time_confidence,
        min_proxy_event_types=min_proxy_event_types,
        min_proxy_source_providers=min_proxy_source_providers,
        min_trigger_btc_risk_buckets=min_trigger_btc_risk_buckets,
    )


def _validation_review_groups(data: list[dict[str, Any]]) -> _ValidationReviewGroups:
    reviewed = [row for row in data if _is_reviewed_evidence(row)]
    label_counts = _label_counts(reviewed)
    reviewed_proxy = [row for row in reviewed if _is_proxy_candidate(row)]
    negative_controls = [
        row
        for row in reviewed
        if _label(row) in CONTROL_LABELS or _is_direct_or_ambiguous(row)
    ]
    triggered_reviewed = [row for row in reviewed if _signal_type(row) == "SHORT_TRIGGERED"]
    triggered_valid = [row for row in triggered_reviewed if _label(row) == POSITIVE_LABEL]
    direct_or_nonproxy_triggered = [
        row for row in triggered_reviewed if not _is_proxy_candidate(row)
    ]
    return _ValidationReviewGroups(
        data=data,
        reviewed=reviewed,
        reviewed_proxy=reviewed_proxy,
        negative_controls=negative_controls,
        triggered_reviewed=triggered_reviewed,
        triggered_valid=triggered_valid,
        direct_or_nonproxy_triggered=direct_or_nonproxy_triggered,
        label_counts=label_counts,
    )


def _validation_review_metrics(
    groups: _ValidationReviewGroups,
    thresholds: _ValidationReviewThresholds,
) -> _ValidationReviewMetrics:
    data = groups.data
    reviewed = groups.reviewed
    triggered_reviewed = groups.triggered_reviewed
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
    missing_review_provenance_rows = sum(
        1 for row in reviewed if _missing_review_provenance_fields(row)
    )
    schema_mismatches = sum(
        1
        for row in data
        if str(row.get("schema_version") or "") != VALIDATION_SAMPLE_SCHEMA_VERSION
    )
    trigger_precision = (
        len(groups.triggered_valid) / len(triggered_reviewed)
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
    low_confidence_trigger_event_time_rows = sum(
        1
        for row in triggered_reviewed
        if (_review_event_time_confidence(row) or 0.0) < thresholds.min_trigger_event_time_confidence
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
    reviewed_proxy_event_types = len(_event_types(groups.reviewed_proxy))
    reviewed_proxy_source_providers = len(_source_providers(groups.reviewed_proxy))
    reviewed_proxy_source_origins = len(_source_origins(groups.reviewed_proxy))
    triggered_btc_risk_buckets = len(_known_btc_risk_buckets(triggered_reviewed))
    return _ValidationReviewMetrics(
        missing_review_status_rows=missing_review_status_rows,
        missing_human_label_rows=missing_human_label_rows,
        missing_review_provenance_rows=missing_review_provenance_rows,
        schema_mismatches=schema_mismatches,
        unknown_label_rows=unknown_label_rows,
        valid_proxy_labels=groups.label_counts.get(POSITIVE_LABEL, 0),
        trigger_precision=trigger_precision,
        trigger_false_positive_rate=trigger_false_positive_rate,
        avg_mfe=avg_mfe,
        avg_mae=avg_mae,
        mfe_mae_ratio=mfe_mae_ratio,
        avg_24h=avg_24h,
        avg_72h=avg_72h,
        avg_7d=avg_7d,
        avg_event_time_72h=avg_event_time_72h,
        trigger_vs_event_time_72h_edge=trigger_vs_event_time_72h_edge,
        avg_trigger_latency=avg_trigger_latency,
        median_trigger_latency=median_trigger_latency,
        negative_trigger_latency_rows=negative_trigger_latency_rows,
        missing_trigger_outcome_rows=missing_trigger_outcome_rows,
        missing_event_time_baseline_rows=missing_event_time_baseline_rows,
        low_confidence_trigger_event_time_rows=low_confidence_trigger_event_time_rows,
        missing_source_timing_rows=missing_source_timing_rows,
        pit_violation_rows=pit_violation_rows,
        post_decision_source_rows=post_decision_source_rows,
        reviewed_proxy_event_types=reviewed_proxy_event_types,
        reviewed_proxy_source_providers=reviewed_proxy_source_providers,
        reviewed_proxy_source_origins=reviewed_proxy_source_origins,
        triggered_btc_risk_buckets=triggered_btc_risk_buckets,
    )


def _validation_review_blockers(
    groups: _ValidationReviewGroups,
    metrics: _ValidationReviewMetrics,
    thresholds: _ValidationReviewThresholds,
) -> list[str]:
    blockers: list[str] = []
    if metrics.schema_mismatches:
        blockers.append(f"{metrics.schema_mismatches} row(s) have an unknown schema_version")
    if metrics.unknown_label_rows:
        blockers.append(f"{metrics.unknown_label_rows} labeled row(s) use unknown human_label values")
    if metrics.missing_review_status_rows:
        blockers.append(
            f"{metrics.missing_review_status_rows} labeled row(s) are missing review_status=reviewed"
        )
    if metrics.missing_human_label_rows:
        blockers.append(
            f"{metrics.missing_human_label_rows} reviewed row(s) are missing human_label"
        )
    if metrics.missing_review_provenance_rows:
        blockers.append(
            f"{metrics.missing_review_provenance_rows} reviewed row(s) are missing review provenance"
        )
    if len(groups.reviewed_proxy) < thresholds.min_proxy_candidates:
        blockers.append(
            f"reviewed proxy candidates {len(groups.reviewed_proxy)}/{thresholds.min_proxy_candidates}"
        )
    if len(groups.negative_controls) < thresholds.min_negative_controls:
        blockers.append(
            f"reviewed direct/ambiguous controls {len(groups.negative_controls)}/{thresholds.min_negative_controls}"
        )
    if len(groups.triggered_reviewed) < thresholds.min_triggered_reviewed:
        blockers.append(
            f"reviewed SHORT_TRIGGERED candidates {len(groups.triggered_reviewed)}/{thresholds.min_triggered_reviewed}"
        )
    if (
        len(groups.reviewed_proxy) >= thresholds.min_proxy_candidates
        and metrics.reviewed_proxy_event_types < thresholds.min_proxy_event_types
    ):
        blockers.append(
            f"reviewed proxy event types {metrics.reviewed_proxy_event_types}/{thresholds.min_proxy_event_types}"
        )
    if (
        thresholds.min_proxy_candidates >= thresholds.min_proxy_source_providers
        and len(groups.reviewed_proxy) >= thresholds.min_proxy_candidates
        and metrics.reviewed_proxy_source_providers < thresholds.min_proxy_source_providers
    ):
        blockers.append(
            f"reviewed proxy source providers {metrics.reviewed_proxy_source_providers}/{thresholds.min_proxy_source_providers}"
        )
    if (
        len(groups.triggered_reviewed) >= thresholds.min_triggered_reviewed
        and metrics.triggered_btc_risk_buckets < thresholds.min_trigger_btc_risk_buckets
    ):
        blockers.append(
            f"reviewed trigger BTC risk buckets {metrics.triggered_btc_risk_buckets}/{thresholds.min_trigger_btc_risk_buckets}"
        )
    if metrics.trigger_precision is not None and metrics.trigger_precision < thresholds.min_trigger_precision:
        blockers.append(
            f"trigger precision {_fmt_pct(metrics.trigger_precision)} below {_fmt_pct(thresholds.min_trigger_precision)}"
        )
    if groups.direct_or_nonproxy_triggered:
        blockers.append(
            f"{len(groups.direct_or_nonproxy_triggered)} direct/non-proxy reviewed row(s) are SHORT_TRIGGERED"
        )
    if metrics.pit_violation_rows:
        blockers.append(
            f"{metrics.pit_violation_rows} reviewed row(s) use evidence first seen after the decision time"
        )
    if metrics.post_decision_source_rows:
        blockers.append(
            f"{metrics.post_decision_source_rows} reviewed row(s) include source evidence after the decision time"
        )
    if metrics.negative_trigger_latency_rows:
        blockers.append(
            f"{metrics.negative_trigger_latency_rows} reviewed SHORT_TRIGGERED row(s) trigger before event time"
        )
    if metrics.missing_trigger_outcome_rows:
        blockers.append(
            f"{metrics.missing_trigger_outcome_rows} reviewed SHORT_TRIGGERED row(s) are missing outcome fields"
        )
    if metrics.missing_event_time_baseline_rows:
        blockers.append(
            f"{metrics.missing_event_time_baseline_rows} reviewed SHORT_TRIGGERED row(s) are missing event-time baseline fields"
        )
    if metrics.low_confidence_trigger_event_time_rows:
        blockers.append(
            f"{metrics.low_confidence_trigger_event_time_rows} reviewed SHORT_TRIGGERED row(s) have event_time_confidence "
            f"below {_fmt_pct(thresholds.min_trigger_event_time_confidence)}"
        )
    if metrics.missing_source_timing_rows:
        blockers.append(
            f"{metrics.missing_source_timing_rows} reviewed row(s) are missing source timing evidence"
        )
    if (
        groups.triggered_reviewed
        and not metrics.missing_trigger_outcome_rows
        and (metrics.mfe_mae_ratio is None or metrics.mfe_mae_ratio < thresholds.min_mfe_mae_ratio)
    ):
        blockers.append(
            f"MFE/MAE {_fmt_num(metrics.mfe_mae_ratio)} below {_fmt_num(thresholds.min_mfe_mae_ratio)}"
        )
    if metrics.avg_72h is not None and metrics.avg_72h >= 0:
        blockers.append("reviewed SHORT_TRIGGERED rows do not show favorable 72h short returns")
    if (
        groups.triggered_reviewed
        and not metrics.missing_event_time_baseline_rows
        and metrics.trigger_vs_event_time_72h_edge is not None
        and metrics.trigger_vs_event_time_72h_edge <= 0
    ):
        blockers.append("post-event trigger does not beat event-time short baseline at 72h")
    return blockers


def _validation_review_cohorts(data: list[dict[str, Any]]) -> _ValidationReviewCohorts:
    event_type_cohorts = _cohorts(data, lambda row: str(row.get("event_type") or "unknown"))
    relationship_type_cohorts = _cohorts(
        data,
        lambda row: str(row.get("relationship_type") or "unknown"),
    )
    asset_role_cohorts = _cohorts(data, lambda row: str(row.get("asset_role") or "unknown"))
    event_time_source_cohorts = _cohorts(data, _event_time_source_bucket)
    source_provider_cohorts = _source_provider_cohorts(data)
    source_origin_cohorts = _source_origin_cohorts(data)
    btc_risk_cohorts = _cohorts(data, _btc_risk_bucket)
    return _ValidationReviewCohorts(
        event_type_cohorts=event_type_cohorts,
        relationship_type_cohorts=relationship_type_cohorts,
        asset_role_cohorts=asset_role_cohorts,
        event_time_source_cohorts=event_time_source_cohorts,
        source_provider_cohorts=source_provider_cohorts,
        source_origin_cohorts=source_origin_cohorts,
        btc_risk_cohorts=btc_risk_cohorts,
    )


def _validation_review_result(
    groups: _ValidationReviewGroups,
    metrics: _ValidationReviewMetrics,
    thresholds: _ValidationReviewThresholds,
    blockers: list[str],
    cohorts: _ValidationReviewCohorts,
) -> EventFadeValidationReview:
    return EventFadeValidationReview(
        total_rows=len(groups.data),
        reviewed_rows=len(groups.reviewed),
        unlabeled_rows=len(groups.data) - len(groups.reviewed),
        missing_review_status_rows=metrics.missing_review_status_rows,
        missing_human_label_rows=metrics.missing_human_label_rows,
        missing_review_provenance_rows=metrics.missing_review_provenance_rows,
        schema_mismatches=metrics.schema_mismatches,
        unknown_label_rows=metrics.unknown_label_rows,
        label_counts=groups.label_counts,
        reviewed_proxy_candidates=len(groups.reviewed_proxy),
        reviewed_negative_controls=len(groups.negative_controls),
        valid_proxy_labels=metrics.valid_proxy_labels,
        triggered_reviewed=len(groups.triggered_reviewed),
        triggered_valid=len(groups.triggered_valid),
        direct_or_nonproxy_triggered=len(groups.direct_or_nonproxy_triggered),
        trigger_precision=metrics.trigger_precision,
        trigger_false_positive_rate=metrics.trigger_false_positive_rate,
        avg_mfe=metrics.avg_mfe,
        avg_mae=metrics.avg_mae,
        mfe_mae_ratio=metrics.mfe_mae_ratio,
        avg_post_event_return_24h=metrics.avg_24h,
        avg_post_event_return_72h=metrics.avg_72h,
        avg_post_event_return_7d=metrics.avg_7d,
        avg_event_time_post_event_return_72h=metrics.avg_event_time_72h,
        avg_trigger_vs_event_time_return_72h_edge=metrics.trigger_vs_event_time_72h_edge,
        avg_trigger_latency_hours=metrics.avg_trigger_latency,
        median_trigger_latency_hours=metrics.median_trigger_latency,
        negative_trigger_latency_rows=metrics.negative_trigger_latency_rows,
        missing_trigger_outcome_rows=metrics.missing_trigger_outcome_rows,
        missing_event_time_baseline_rows=metrics.missing_event_time_baseline_rows,
        low_confidence_trigger_event_time_rows=metrics.low_confidence_trigger_event_time_rows,
        point_in_time_violation_rows=metrics.pit_violation_rows,
        post_decision_source_rows=metrics.post_decision_source_rows,
        missing_source_timing_rows=metrics.missing_source_timing_rows,
        min_proxy_candidates=thresholds.min_proxy_candidates,
        min_negative_controls=thresholds.min_negative_controls,
        min_triggered_reviewed=thresholds.min_triggered_reviewed,
        min_trigger_precision=thresholds.min_trigger_precision,
        min_mfe_mae_ratio=thresholds.min_mfe_mae_ratio,
        min_trigger_event_time_confidence=thresholds.min_trigger_event_time_confidence,
        min_proxy_event_types=thresholds.min_proxy_event_types,
        min_proxy_source_providers=thresholds.min_proxy_source_providers,
        min_trigger_btc_risk_buckets=thresholds.min_trigger_btc_risk_buckets,
        reviewed_proxy_event_types=metrics.reviewed_proxy_event_types,
        reviewed_proxy_source_providers=metrics.reviewed_proxy_source_providers,
        reviewed_proxy_source_origins=metrics.reviewed_proxy_source_origins,
        triggered_btc_risk_buckets=metrics.triggered_btc_risk_buckets,
        event_type_cohorts=cohorts.event_type_cohorts,
        relationship_type_cohorts=cohorts.relationship_type_cohorts,
        asset_role_cohorts=cohorts.asset_role_cohorts,
        event_time_source_cohorts=cohorts.event_time_source_cohorts,
        source_provider_cohorts=cohorts.source_provider_cohorts,
        source_origin_cohorts=cohorts.source_origin_cohorts,
        btc_risk_cohorts=cohorts.btc_risk_cohorts,
        promotion_blockers=tuple(blockers),
    )


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
    if review.missing_review_provenance_rows:
        steps.append(
            f"Fill reviewed_by and reviewed_at for {review.missing_review_provenance_rows} reviewed row(s)."
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
        review.min_proxy_candidates >= review.min_proxy_source_providers
        and review.reviewed_proxy_candidates >= review.min_proxy_candidates
        and review.reviewed_proxy_source_providers < review.min_proxy_source_providers
    ):
        provider_gap = review.min_proxy_source_providers - review.reviewed_proxy_source_providers
        steps.append(
            f"Add reviewed proxy examples from {provider_gap} more source provider(s) "
            f"(current {review.reviewed_proxy_source_providers}/{review.min_proxy_source_providers})."
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
    if review.low_confidence_trigger_event_time_rows:
        steps.append(
            f"Confirm event times from explicit source evidence for {review.low_confidence_trigger_event_time_rows} "
            "reviewed triggered row(s)."
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
