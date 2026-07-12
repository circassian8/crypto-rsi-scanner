"""Split implementation for `crypto_rsi_scanner/event_alpha/outcomes/quality.py` (scoring)."""

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
from .. import feedback_eligibility
from .models import *  # noqa: F403

def build_tuning_worksheet(
    *,
    alert_rows: Iterable[Mapping[str, Any]] = (),
    feedback_rows: Iterable[Mapping[str, Any]] = (),
    core_rows: Iterable[Mapping[str, Any]] = (),
    missed_rows: Iterable[Mapping[str, Any]] = (),
    run_rows: Iterable[Mapping[str, Any]] = (),
    priors_shadow_rows: Iterable[Mapping[str, Any]] = (),
    now: Any = None,
) -> EventAlphaTuningWorksheet:
    """Build deterministic threshold/source suggestions without applying them."""
    alerts = [dict(row) for row in alert_rows if isinstance(row, Mapping)]
    supplied_feedback = [dict(row) for row in feedback_rows if isinstance(row, Mapping)]
    feedback, excluded_feedback, feedback_reasons = (
        feedback_eligibility.partition_joined_alert_feedback(
            supplied_feedback,
            core_rows,
            alerts,
            now=now,
        )
    )
    feedback = list(feedback)
    missed = [dict(row) for row in missed_rows if isinstance(row, Mapping)]
    runs = [dict(row) for row in run_rows if isinstance(row, Mapping)]
    suggestions: list[EventAlphaTuningSuggestion] = []
    suggestions.extend(_playbook_feedback_suggestions(alerts, feedback))
    suggestions.extend(_source_feedback_suggestions(alerts, feedback))
    suggestions.extend(_missed_suggestions(missed))
    suggestions.extend(_run_suggestions(runs))
    suggestions.extend(_priors_suggestions(priors_shadow_rows))
    if not suggestions:
        suggestions.append(EventAlphaTuningSuggestion(
            area="sample",
            recommendation="collect more burn-in rows before changing thresholds",
            evidence=f"alerts={len(alerts)} feedback={len(feedback)} missed={len(missed)} runs={len(runs)}",
        ))
    return EventAlphaTuningWorksheet(
        alert_rows=len(alerts),
        feedback_rows=len(feedback),
        missed_rows=len(missed),
        run_rows=len(runs),
        suggestions=tuple(dict.fromkeys(suggestions)),
        feedback_rows_supplied=len(supplied_feedback),
        feedback_rows_excluded=len(excluded_feedback),
        feedback_exclusion_reason_counts=feedback_reasons,
    )
def format_tuning_worksheet(worksheet: EventAlphaTuningWorksheet) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA WEEKLY TUNING WORKSHEET (research-only)",
        "=" * 76,
        (
            "inputs: "
            f"alerts={worksheet.alert_rows} feedback={worksheet.feedback_rows} "
            f"missed={worksheet.missed_rows} runs={worksheet.run_rows}"
        ),
        (
            "feedback authority: "
            f"supplied={worksheet.feedback_rows_supplied} "
            f"eligible={worksheet.feedback_rows} "
            f"excluded={worksheet.feedback_rows_excluded}"
        ),
        "",
        "suggestions:",
    ]
    for item in worksheet.suggestions:
        lines.append(f"- [{item.area}] {item.recommendation}")
        lines.append(f"  evidence: {item.evidence}")
        lines.append(f"  action: {item.action_type}")
    lines.append("No thresholds, priors, alert tiers, paper trades, live DB rows, or execution were changed.")
    return "\n".join(lines).rstrip()
def _playbook_feedback_suggestions(
    alerts: list[dict[str, Any]],
    feedback: list[dict[str, Any]],
) -> tuple[EventAlphaTuningSuggestion, ...]:
    counts: dict[str, dict[str, int]] = {}
    for row in feedback:
        playbook = str(row.get("playbook_type") or row.get("effective_playbook_type") or "unknown")
        bucket = counts.setdefault(playbook, {"useful": 0, "junk": 0, "watch": 0})
        label = str(row.get("feedback_label") or "")
        if label in bucket:
            bucket[label] += 1
    out: list[EventAlphaTuningSuggestion] = []
    for playbook, bucket in sorted(counts.items()):
        useful = bucket.get("useful", 0) + bucket.get("watch", 0)
        junk = bucket.get("junk", 0)
        if junk >= 2 and junk > useful:
            out.append(EventAlphaTuningSuggestion(
                area=f"playbook:{playbook}",
                recommendation="consider raising this playbook's alert threshold or requiring stronger identity/source evidence",
                evidence=f"junk={junk} useful_or_watch={useful}",
                action_type="threshold_review",
            ))
        elif useful >= 2 and useful > junk:
            out.append(EventAlphaTuningSuggestion(
                area=f"playbook:{playbook}",
                recommendation="consider preserving this playbook's current threshold and collecting more outcomes before any boost",
                evidence=f"useful_or_watch={useful} junk={junk}",
                action_type="prior_review",
            ))
    return tuple(out)
def _source_feedback_suggestions(
    alerts: list[dict[str, Any]],
    feedback: list[dict[str, Any]],
) -> tuple[EventAlphaTuningSuggestion, ...]:
    counts: dict[str, dict[str, int]] = {}
    for row in feedback:
        source = str(row.get("source_provider") or row.get("source_domain") or "unknown")
        bucket = counts.setdefault(source, {"useful": 0, "junk": 0, "watch": 0})
        label = str(row.get("feedback_label") or "")
        if label in bucket:
            bucket[label] += 1
    out: list[EventAlphaTuningSuggestion] = []
    for source, bucket in sorted(counts.items()):
        useful = bucket.get("useful", 0) + bucket.get("watch", 0)
        junk = bucket.get("junk", 0)
        if junk >= 2 and junk > useful:
            out.append(EventAlphaTuningSuggestion(
                area=f"source:{source}",
                recommendation="consider demoting or adding extra review gates for this source",
                evidence=f"junk={junk} useful_or_watch={useful}",
                action_type="source_prior_review",
            ))
    return tuple(out)
def _missed_suggestions(missed: list[dict[str, Any]]) -> tuple[EventAlphaTuningSuggestion, ...]:
    counts: dict[str, int] = {}
    for row in missed:
        stage = str(row.get("failure_stage") or "unknown")
        counts[stage] = counts.get(stage, 0) + 1
    out: list[EventAlphaTuningSuggestion] = []
    for stage, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        if count < 2:
            continue
        if stage == "resolver_missed_asset":
            recommendation = "add resolver aliases/eval cases for repeatedly missed assets"
        elif stage == "no_source_event":
            recommendation = "review source coverage or catalyst-search queries for this missed cohort"
        elif stage == "watchlist_not_escalated":
            recommendation = "review watchlist escalation thresholds and market-confirmation requirements"
        else:
            recommendation = "review repeated missed-opportunity stage before tuning thresholds"
        out.append(EventAlphaTuningSuggestion(
            area=f"missed:{stage}",
            recommendation=recommendation,
            evidence=f"missed_count={count}",
            action_type="eval_case_review",
        ))
    return tuple(out)
def _run_suggestions(runs: list[dict[str, Any]]) -> tuple[EventAlphaTuningSuggestion, ...]:
    if not runs:
        return (EventAlphaTuningSuggestion(
            area="runs",
            recommendation="schedule daily no-key burn-in before tuning",
            evidence="run ledger is empty",
            action_type="operations",
        ),)
    failures = sum(1 for row in runs if not bool(row.get("success")))
    if failures:
        return (EventAlphaTuningSuggestion(
            area="runs",
            recommendation="fix run failures before interpreting alert precision or recall",
            evidence=f"failed_runs={failures} total_runs={len(runs)}",
            action_type="operations",
        ),)
    return ()
def _priors_suggestions(rows: Iterable[Mapping[str, Any]]) -> tuple[EventAlphaTuningSuggestion, ...]:
    data = [dict(row) for row in rows if isinstance(row, Mapping)]
    if not data:
        return ()
    changed = sum(1 for row in data if row.get("tier_before") != row.get("tier_after"))
    if changed:
        return (EventAlphaTuningSuggestion(
            area="priors_shadow",
            recommendation="review priors shadow rows; runtime prior application remains policy-disabled",
            evidence=f"tier_changes={changed}",
            action_type="prior_review",
        ),)
    return ()
