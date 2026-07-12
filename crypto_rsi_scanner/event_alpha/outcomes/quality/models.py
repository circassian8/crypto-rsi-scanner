"""Split implementation for `crypto_rsi_scanner/event_alpha/outcomes/quality.py` (models)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping
import crypto_rsi_scanner.event_alpha.artifacts.alert_store as event_alpha_alert_store
import crypto_rsi_scanner.event_alpha.outcomes.quality_fields as event_alpha_quality_fields
import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
from ...artifacts import reason_text as event_alpha_reason_text
from ...artifacts import context as event_alpha_artifacts
from ...radar import core_opportunities as event_core_opportunities
from ...radar import opportunity_verdict as event_opportunity_verdict
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import crypto_rsi_scanner.event_alpha.outcomes.quality_fields as event_alpha_quality_fields
from ...artifacts import run_ledger as event_alpha_run_ledger
from datetime import datetime, timezone
from types import SimpleNamespace
import crypto_rsi_scanner.event_alpha.radar.claim_semantics as event_claim_semantics
import crypto_rsi_scanner.event_alpha.radar.evidence_quality as event_evidence_quality
import crypto_rsi_scanner.event_alpha.radar.incident_graph as event_incident_graph
import crypto_rsi_scanner.event_alpha.radar.impact_path_validator as event_impact_path_validator
import crypto_rsi_scanner.event_alpha.radar.market_confirmation as event_market_confirmation
from crypto_rsi_scanner.event_core.models import NormalizedEvent, RawDiscoveredEvent
from ...radar import incidents as event_incident_store

@dataclass(frozen=True)
class EventAlphaQualityReviewResult:
    profile: str | None
    rows: tuple[dict[str, Any], ...]
    candidate_discovery_funnel: dict[str, int]
    stale_warning: str | None = None
STALE_QUALITY_ARTIFACT_WARNING = (
    "This namespace may contain pre-quality-layer artifacts; rerun profile to refresh."
)
@dataclass(frozen=True)
class EventAlphaQualityCoverageMissingRow:
    row_key: str
    missing_fields: tuple[str, ...]
@dataclass(frozen=True)
class EventAlphaQualityCoverageBucket:
    row_type: str
    rows: int
    complete: int
    missing_rows: tuple[EventAlphaQualityCoverageMissingRow, ...]
@dataclass(frozen=True)
class EventAlphaQualityCoverageResult:
    profile: str | None
    artifact_namespace: str | None
    run_id: str | None
    status: str
    stale_warning: str | None
    buckets: tuple[EventAlphaQualityCoverageBucket, ...]
    warnings: tuple[str, ...] = ()
DEFAULT_SIGNAL_QUALITY_CASES_PATH = Path("fixtures/event_discovery/event_alpha_signal_quality_cases.json")
@dataclass(frozen=True)
class SignalQualityCaseResult:
    case_id: str
    title: str
    passed: bool
    stage_failures: tuple[str, ...]
    expected: Mapping[str, Any]
    actual: Mapping[str, Any]
    diffs: tuple[str, ...]
@dataclass(frozen=True)
class SignalQualityEvalResult:
    path: Path
    total_cases: int
    passed_cases: int
    failed_cases: int
    case_results: tuple[SignalQualityCaseResult, ...]
@dataclass(frozen=True)
class EventAlphaSignalQualityExportResult:
    path: Path
    cases_written: int
    reasons: tuple[str, ...]
    feedback_rows_supplied: int = 0
    feedback_rows_eligible: int = 0
    feedback_rows_excluded: int = 0
    feedback_exclusion_reason_counts: dict[str, int] | None = None
@dataclass(frozen=True)
class EventAlphaTuningSuggestion:
    area: str
    recommendation: str
    evidence: str
    action_type: str = "manual_review"
@dataclass(frozen=True)
class EventAlphaTuningWorksheet:
    alert_rows: int
    feedback_rows: int
    missed_rows: int
    run_rows: int
    suggestions: tuple[EventAlphaTuningSuggestion, ...]
    feedback_rows_supplied: int = 0
    feedback_rows_excluded: int = 0
    feedback_exclusion_reason_counts: dict[str, int] | None = None
