"""Weekly tuning worksheet for Event Alpha research artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


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


def build_tuning_worksheet(
    *,
    alert_rows: Iterable[Mapping[str, Any]] = (),
    feedback_rows: Iterable[Mapping[str, Any]] = (),
    missed_rows: Iterable[Mapping[str, Any]] = (),
    run_rows: Iterable[Mapping[str, Any]] = (),
    priors_shadow_rows: Iterable[Mapping[str, Any]] = (),
) -> EventAlphaTuningWorksheet:
    """Build deterministic threshold/source suggestions without applying them."""
    alerts = [dict(row) for row in alert_rows if isinstance(row, Mapping)]
    feedback = [dict(row) for row in feedback_rows if isinstance(row, Mapping)]
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
    feedback_by_key = _feedback_labels_by_key(feedback)
    counts: dict[str, dict[str, int]] = {}
    for row in alerts:
        key = str(row.get("alert_key") or row.get("key") or "")
        labels = feedback_by_key.get(key, ())
        if not labels:
            continue
        playbook = str(row.get("playbook_type") or row.get("effective_playbook_type") or "unknown")
        bucket = counts.setdefault(playbook, {"useful": 0, "junk": 0, "watch": 0})
        for label in labels:
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
    feedback_by_key = _feedback_labels_by_key(feedback)
    counts: dict[str, dict[str, int]] = {}
    for row in alerts:
        key = str(row.get("alert_key") or row.get("key") or "")
        labels = feedback_by_key.get(key, ())
        if not labels:
            continue
        source = str(row.get("source") or row.get("source_provider") or "unknown")
        bucket = counts.setdefault(source, {"useful": 0, "junk": 0, "watch": 0})
        for label in labels:
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
            recommendation="review priors shadow rows before applying calibration priors",
            evidence=f"tier_changes={changed}",
            action_type="prior_review",
        ),)
    return ()


def _feedback_labels_by_key(feedback: list[dict[str, Any]]) -> dict[str, tuple[str, ...]]:
    out: dict[str, list[str]] = {}
    for row in feedback:
        key = str(row.get("key") or row.get("target") or "")
        if key:
            out.setdefault(key, []).append(str(row.get("label") or ""))
    return {key: tuple(value for value in values if value) for key, values in out.items()}
