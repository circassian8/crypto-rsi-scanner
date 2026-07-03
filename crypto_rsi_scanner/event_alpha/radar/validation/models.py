"""Validation review constants and models."""

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


POSITIVE_LABEL = "valid_proxy_fade"


DEFAULT_MIN_TRIGGER_EVENT_TIME_CONFIDENCE = 0.80


DEFAULT_BALANCED_PROXY_REVIEW_ROWS = 25


DEFAULT_BALANCED_CONTROL_REVIEW_ROWS = 50


DATE_HINT_MONTH_PATTERN = (
    "jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    "jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
)


DATE_HINT_PATTERNS = (
    re.compile(r"\b20\d{2}-\d{1,2}-\d{1,2}\b", re.IGNORECASE),
    re.compile(
        rf"\b(?:{DATE_HINT_MONTH_PATTERN})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?\s*[–-]\s*"
        rf"\d{{1,2}}(?:st|nd|rd|th)?[,]?\s+20\d{{2}}\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b(?:{DATE_HINT_MONTH_PATTERN})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?[,]?\s+20\d{{2}}\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:world cup|ipo|election|inauguration|fixture|match|listing|launch)[^.;:|()]{0,80}\b20\d{2}\b", re.IGNORECASE),
    re.compile(r"\b(?:today|tonight|tomorrow|same day|first day)\b", re.IGNORECASE),
)


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


REVIEW_PROVENANCE_FIELDS = (
    "reviewed_by",
    "reviewed_at",
)


REVIEW_FIELDS = (
    "review_status",
    *REVIEW_PROVENANCE_FIELDS,
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
    "outcome_price_interval",
    "outcome_price_source",
    "human_event_time",
    "human_event_time_source",
    "human_event_time_confidence",
    "human_event_time_notes",
)


ASSET_ROLE_REVIEW_METADATA_FIELDS = (
    "asset_role",
    "asset_role_confidence",
    "asset_role_reason",
    "asset_role_evidence",
)


REVIEW_MERGE_IGNORED_FIELDS = frozenset({"exported_at", *REVIEW_FIELDS, *ASSET_ROLE_REVIEW_METADATA_FIELDS})


REVIEW_EVIDENCE_FIELDS = tuple(
    field for field in VALIDATION_SAMPLE_FIELDS if field not in REVIEW_MERGE_IGNORED_FIELDS
)


REVIEW_TEMPLATE_FIELDS = (
    "event_id",
    "asset_coin_id",
    "asset_symbol",
    "asset_role",
    "relationship_type",
    "external_asset",
    "event_name",
    "event_type",
    "event_time",
    "event_time_confidence",
    "event_time_source",
    "human_event_time",
    "human_event_time_confidence",
    "human_event_time_source",
    "human_event_time_notes",
    "trigger_observed_at",
    "signal_type",
    "queue_category",
    "review_slice",
    "suggested_label",
    "missing_fields",
    "review_prompt",
    "event_time_review_hint",
    "source_date_hint",
    "primary_source_url",
    "primary_source_origin",
    "primary_raw_title",
    "source_search_url",
    "source_urls",
    "source_providers",
    "source_origins",
    "raw_published_at",
    "raw_fetched_at",
    "published_at_min",
    "published_at_max",
    "fetched_at_min",
    "fetched_at_max",
    "review_status",
    "reviewed_by",
    "reviewed_at",
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
    "outcome_price_interval",
    "outcome_price_source",
)


REVIEW_TEMPLATE_DERIVED_FIELDS = frozenset({
    "queue_category",
    "review_slice",
    "suggested_label",
    "missing_fields",
    "review_prompt",
    "event_time_review_hint",
    "source_date_hint",
    "primary_source_url",
    "primary_source_origin",
    "primary_raw_title",
    "source_search_url",
    "source_providers",
    "source_origins",
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
    interval: str | None = None
    source: str | None = None


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
    missing_review_provenance_rows: int
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
    low_confidence_trigger_event_time_rows: int
    point_in_time_violation_rows: int
    post_decision_source_rows: int
    missing_source_timing_rows: int
    min_proxy_candidates: int
    min_negative_controls: int
    min_triggered_reviewed: int
    min_trigger_precision: float
    min_mfe_mae_ratio: float
    min_trigger_event_time_confidence: float
    min_proxy_event_types: int
    min_proxy_source_providers: int
    min_trigger_btc_risk_buckets: int
    reviewed_proxy_event_types: int
    reviewed_proxy_source_providers: int
    reviewed_proxy_source_origins: int
    triggered_btc_risk_buckets: int
    event_type_cohorts: tuple["ValidationCohort", ...]
    relationship_type_cohorts: tuple["ValidationCohort", ...]
    asset_role_cohorts: tuple["ValidationCohort", ...]
    event_time_source_cohorts: tuple["ValidationCohort", ...]
    source_provider_cohorts: tuple["ValidationCohort", ...]
    source_origin_cohorts: tuple["ValidationCohort", ...]
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
class ValidationReviewTemplateIssue:
    row_index: int
    category: str
    event_id: str
    asset_symbol: str
    asset_coin_id: str
    relationship_type: str
    message: str
    missing_fields: tuple[str, ...] = ()
    changed_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class ValidationReviewTemplateCheck:
    template_rows: int
    edited_rows: int
    matched_rows: int
    evidence_changed_rows: int
    unmatched_reviewed_rows: int
    copied_fields: int
    issues: tuple[ValidationReviewTemplateIssue, ...]

    @property
    def issue_rows(self) -> int:
        return len(self.issues)

    @property
    def ready_to_apply(self) -> bool:
        return self.edited_rows > 0 and not self.issues


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
    event_time_source: str
    event_time_confidence: float | None
    trigger_observed_at: str | None
    human_label: str
    suggested_label: str
    missing_fields: tuple[str, ...]
    source_urls: tuple[str, ...]
    source_origins: tuple[str, ...]


@dataclass(frozen=True)
class ValidationLabelingQueue:
    total_rows: int
    needed_rows: int
    shown_rows: int
    limit: int | None
    items: tuple[ValidationLabelingQueueItem, ...]
