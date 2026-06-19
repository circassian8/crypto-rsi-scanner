"""Burn-in scorecard for Event Alpha research artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import event_alpha_artifacts


@dataclass(frozen=True)
class EventAlphaBurnInScorecard:
    days: int
    run_rows: list[dict[str, Any]]
    alert_rows: list[dict[str, Any]]
    feedback_rows: list[dict[str, Any]]
    missed_rows: list[dict[str, Any]]
    provider_health_rows: dict[str, dict[str, Any]]
    llm_budget_rows: list[dict[str, Any]]
    outcome_rows: list[dict[str, Any]]
    profile: str | None = None
    runs_with_alertable: int = 0
    alert_snapshot_rows: int = 0
    runs_with_alertable_but_no_alert_snapshots: int = 0
    feedback_row_count: int = 0
    outcome_row_count: int = 0
    missed_row_count: int = 0
    provider_health_row_count: int = 0
    llm_budget_row_count: int = 0
    artifact_namespace: str | None = None
    include_test_artifacts: bool = False
    include_legacy_artifacts: bool = False
    legacy_rows_skipped: int = 0
    test_rows_skipped: int = 0
    coverage_warnings: tuple[str, ...] = ()


def build_burn_in_scorecard(
    *,
    run_rows: Iterable[Mapping[str, Any]] = (),
    alert_rows: Iterable[Mapping[str, Any]] = (),
    feedback_rows: Iterable[Mapping[str, Any]] = (),
    missed_rows: Iterable[Mapping[str, Any]] = (),
    provider_health_rows: Mapping[str, Mapping[str, Any]] | None = None,
    llm_budget_rows: Iterable[Mapping[str, Any]] = (),
    outcome_rows: Iterable[Mapping[str, Any]] = (),
    profile: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_legacy_artifacts: bool = False,
    days: int = 7,
    now: datetime | None = None,
) -> EventAlphaBurnInScorecard:
    cutoff = (now or datetime.now(timezone.utc)).astimezone(timezone.utc) - timedelta(days=max(1, int(days or 1)))
    raw_run_data = _filter_rows(run_rows, cutoff, ("started_at", "observed_at", "marked_at"))
    raw_alert_data = _filter_rows(alert_rows, cutoff, ("observed_at", "started_at"))
    raw_feedback_data = _filter_rows(feedback_rows, cutoff, ("marked_at", "observed_at"))
    raw_missed_data = _filter_rows(missed_rows, cutoff, ("observed_at", "detected_at", "created_at"))
    raw_budget_data = _filter_rows(llm_budget_rows, cutoff, ("date", "updated_at"))
    raw_outcomes = _filter_rows(outcome_rows, cutoff, ("observed_at", "started_at"))
    raw_all = [*raw_run_data, *raw_alert_data, *raw_feedback_data, *raw_missed_data, *raw_budget_data, *raw_outcomes]
    legacy_skipped = 0 if include_legacy_artifacts else sum(1 for row in raw_all if event_alpha_artifacts.is_legacy_row(row))
    test_skipped = 0 if include_test_artifacts else sum(1 for row in raw_all if event_alpha_artifacts.is_non_operational_row(row))
    run_data = _artifact_filter(raw_run_data, profile, artifact_namespace, include_test_artifacts, include_legacy_artifacts)
    alert_data = _artifact_filter(raw_alert_data, profile, artifact_namespace, include_test_artifacts, include_legacy_artifacts)
    feedback_data = _artifact_filter(raw_feedback_data, profile, artifact_namespace, include_test_artifacts, include_legacy_artifacts)
    missed_data = _artifact_filter(raw_missed_data, profile, artifact_namespace, include_test_artifacts, include_legacy_artifacts)
    budget_data = _artifact_filter(raw_budget_data, profile, artifact_namespace, include_test_artifacts, include_legacy_artifacts)
    supplied_outcomes = _artifact_filter(raw_outcomes, profile, artifact_namespace, include_test_artifacts, include_legacy_artifacts)
    outcome_data = supplied_outcomes or _rows_with_outcomes(alert_data)
    health_data = {str(key): dict(value) for key, value in (provider_health_rows or {}).items()}
    runs_with_alertable = sum(1 for row in run_data if _int(row.get("alertable")) > 0)
    alert_counts_by_run_id: dict[str, int] = {}
    for row in alert_data:
        run_id = str(row.get("run_id") or "").strip()
        if run_id:
            alert_counts_by_run_id[run_id] = alert_counts_by_run_id.get(run_id, 0) + 1
    alertable_without_snapshots = sum(
        1 for row in run_data
        if _int(row.get("alertable")) > 0
        and event_alpha_artifacts.classify_snapshot_availability(
            row,
            None,
            alert_counts_by_run_id.get(str(row.get("run_id") or "").strip(), 0),
        ) not in {
            event_alpha_artifacts.SNAPSHOT_AVAILABLE,
            event_alpha_artifacts.SNAPSHOT_UNKNOWN_LEGACY,
        }
    )
    coverage = _coverage_warnings(
        run_data,
        alert_data,
        feedback_data,
        outcome_data,
        missed_data,
        health_data,
        profile=profile,
    )
    return EventAlphaBurnInScorecard(
        days=max(1, int(days or 1)),
        run_rows=run_data,
        alert_rows=alert_data,
        feedback_rows=feedback_data,
        missed_rows=missed_data,
        provider_health_rows=health_data,
        llm_budget_rows=budget_data,
        outcome_rows=outcome_data,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
        legacy_rows_skipped=legacy_skipped,
        test_rows_skipped=test_skipped,
        runs_with_alertable=runs_with_alertable,
        alert_snapshot_rows=len(alert_data),
        runs_with_alertable_but_no_alert_snapshots=alertable_without_snapshots,
        feedback_row_count=len(feedback_data),
        outcome_row_count=len(outcome_data),
        missed_row_count=len(missed_data),
        provider_health_row_count=len(health_data),
        llm_budget_row_count=len(budget_data),
        coverage_warnings=coverage,
    )


def load_llm_budget_rows(path: str | Path | None) -> list[dict[str, Any]]:
    if not path:
        return []
    p = Path(path).expanduser()
    if not p.exists():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = raw.get("entries") if isinstance(raw, Mapping) else raw
    return [dict(row) for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def format_burn_in_scorecard(scorecard: EventAlphaBurnInScorecard) -> str:
    runs = scorecard.run_rows
    alerts = scorecard.alert_rows
    feedback = scorecard.feedback_rows
    missed = scorecard.missed_rows
    health = scorecard.provider_health_rows
    budget = scorecard.llm_budget_rows
    successful = sum(1 for row in runs if bool(row.get("success")))
    lines = [
        "=" * 76,
        "EVENT ALPHA BURN-IN SCORECARD (research-only)",
        "=" * 76,
        f"window_days={scorecard.days}",
        f"profile={scorecard.profile or 'any'} namespace={scorecard.artifact_namespace or 'any'} "
        f"include_test_artifacts={str(scorecard.include_test_artifacts).lower()} "
        f"include_legacy_artifacts={str(scorecard.include_legacy_artifacts).lower()}",
        f"runs={len(runs)} successful={successful} failed={len(runs) - successful}",
        (
            "events/candidates/alertable: "
            f"{sum(_int(row.get('raw_events')) for row in runs)} / "
            f"{sum(_int(row.get('candidates')) for row in runs)} / "
            f"{sum(_int(row.get('alertable')) for row in runs)}"
        ),
        "alerts by tier: " + _count_line(alerts, "tier"),
        "alerts by playbook: " + _count_line(alerts, "playbook_type"),
        "feedback: " + _count_line(feedback, "label"),
        "missed by stage: " + _count_line(missed, "failure_stage"),
        "provider failures/backoffs: " + _provider_line(health),
        "LLM budget: " + _budget_line(budget),
        "artifact coverage: "
        f"runs_with_alertable={scorecard.runs_with_alertable} · "
        f"alert_snapshots={scorecard.alert_snapshot_rows} · "
        f"alertable_without_snapshots={scorecard.runs_with_alertable_but_no_alert_snapshots} · "
        f"feedback={scorecard.feedback_row_count} · outcomes={scorecard.outcome_row_count} · "
        f"missed={scorecard.missed_row_count} · provider_health={scorecard.provider_health_row_count} · "
        f"llm_budget={scorecard.llm_budget_row_count} · "
        f"legacy_skipped={scorecard.legacy_rows_skipped} · test_skipped={scorecard.test_rows_skipped}",
        "top playbooks: " + _top_line(alerts, "playbook_type"),
        "worst sources: " + _worst_source_line(alerts, feedback),
    ]
    if scorecard.coverage_warnings:
        lines.extend(["", "coverage warnings:"])
        lines.extend(f"- {warning}" for warning in scorecard.coverage_warnings)
    lines.extend(["", "recommendations:"])
    lines.extend(f"- {item}" for item in _recommendations(runs, alerts, feedback, missed, health))
    lines.append("No thresholds, alert tiers, paper trades, live DB rows, or execution were changed.")
    return "\n".join(lines).rstrip()


def _filter_rows(
    rows: Iterable[Mapping[str, Any]],
    cutoff: datetime,
    fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        parsed = None
        for field in fields:
            parsed = _dt(row.get(field))
            if parsed is not None:
                break
        if parsed is None or parsed >= cutoff:
            out.append(dict(row))
    return out


def _artifact_filter(
    rows: Iterable[Mapping[str, Any]],
    profile: str | None,
    artifact_namespace: str | None,
    include_test_artifacts: bool,
    include_legacy_artifacts: bool,
) -> list[dict[str, Any]]:
    return event_alpha_artifacts.filter_artifact_rows(
        rows,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )


def _count_line(rows: Iterable[Mapping[str, Any]], field: str) -> str:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get(field) or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items())) if counts else "none"


def _top_line(rows: Iterable[Mapping[str, Any]], field: str) -> str:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get(field) or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return ", ".join(f"{key}={count}" for key, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:5]) if counts else "none"


def _provider_line(rows: Mapping[str, Mapping[str, Any]]) -> str:
    bad = [
        f"{row.get('provider_key') or key}({int(row.get('consecutive_failures') or 0)})"
        for key, row in rows.items()
        if int(row.get("consecutive_failures") or 0) > 0 or row.get("disabled_until")
    ]
    return ", ".join(bad[:8]) if bad else "none"


def _budget_line(rows: Iterable[Mapping[str, Any]]) -> str:
    data = list(rows)
    calls = sum(_int(row.get("extractor_calls_attempted")) + _int(row.get("relationship_calls_attempted")) for row in data)
    hits = sum(_int(row.get("cache_hits")) for row in data)
    misses = sum(_int(row.get("cache_misses")) for row in data)
    skipped = sum(_int(row.get("skipped_due_budget")) for row in data)
    cost = sum(_float(row.get("estimated_cost_usd")) for row in data)
    return f"calls={calls} cache={hits}/{misses} skipped={skipped} estimated_cost=${cost:.4f}"


def _rows_with_outcomes(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    outcome_fields = (
        "primary_horizon_return",
        "return_1h",
        "return_4h",
        "return_24h",
        "return_72h",
        "return_7d",
        "max_favorable_excursion",
        "max_adverse_excursion",
        "mfe_mae_ratio",
        "direction_hit",
        "volatility_hit",
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        if any(row.get(field) not in (None, "") for field in outcome_fields):
            out.append(dict(row))
    return out


def _coverage_warnings(
    runs: list[dict[str, Any]],
    alerts: list[dict[str, Any]],
    feedback: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
    missed: list[dict[str, Any]],
    health: Mapping[str, Mapping[str, Any]],
    *,
    profile: str | None,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if not runs:
        if profile:
            warnings.append(f"no operational burn-in rows found for profile {profile}")
        else:
            warnings.append("no operational burn-in rows found")
    if any(_int(row.get("alertable")) > 0 for row in runs) and not alerts:
        warnings.append("alert snapshots missing for alertable runs")
    if alerts and not feedback:
        warnings.append("no feedback labels for routed alerts")
    if _matured_alerts(alerts) and not outcomes:
        warnings.append("no outcomes filled for matured alerts")
    if not missed:
        warnings.append("no missed-opportunity rows for burn-in window")
    live_profiles = {"no_key_live", "no_key_llm", "api_live", "full_llm_live", "research_send"}
    row_profiles = {str(row.get("profile") or "") for row in runs}
    profile_name = str(profile or "").strip()
    live_context = profile_name in live_profiles or bool(row_profiles & live_profiles)
    if live_context and not health:
        warnings.append("provider health missing for live profiles")
    return tuple(dict.fromkeys(warnings))


def _matured_alerts(alerts: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    matured: list[dict[str, Any]] = []
    for row in alerts:
        tier = str(row.get("tier") or row.get("latest_tier") or "")
        route = str(row.get("route") or "")
        if tier in {"WATCHLIST", "HIGH_PRIORITY_WATCH", "TRIGGERED_FADE"} or route in {
            "RESEARCH_DIGEST",
            "HIGH_PRIORITY_RESEARCH",
            "TRIGGERED_FADE_RESEARCH",
        }:
            matured.append(dict(row))
    return matured


def _worst_source_line(alerts: list[dict[str, Any]], feedback: list[dict[str, Any]]) -> str:
    junk_targets = {str(row.get("key") or row.get("target") or "") for row in feedback if row.get("label") == "junk"}
    counts: dict[str, int] = {}
    for row in alerts:
        key = str(row.get("alert_key") or "")
        if key not in junk_targets:
            continue
        source = str(row.get("source") or row.get("source_provider") or "unknown")
        counts[source] = counts.get(source, 0) + 1
    return ", ".join(f"{source}={count}" for source, count in sorted(counts.items())) if counts else "none"


def _recommendations(
    runs: list[dict[str, Any]],
    alerts: list[dict[str, Any]],
    feedback: list[dict[str, Any]],
    missed: list[dict[str, Any]],
    health: Mapping[str, Mapping[str, Any]],
) -> tuple[str, ...]:
    recs: list[str] = []
    if not runs:
        recs.append("run the no_key_live burn-in cycle daily before calibrating thresholds")
    if any(int(row.get("consecutive_failures") or 0) > 0 or row.get("disabled_until") for row in health.values()):
        recs.append("inspect degraded provider health before judging alert recall")
    junk = sum(1 for row in feedback if row.get("label") == "junk")
    useful = sum(1 for row in feedback if row.get("label") == "useful")
    if junk > useful and junk >= 2:
        recs.append("tighten source/resolver gates for playbooks producing junk feedback")
    if missed:
        recs.append("review missed-opportunity stages and add resolver/source coverage where repeated")
    if alerts and not feedback:
        recs.append("mark useful/junk/watch feedback for routed alerts to make calibration actionable")
    if not recs:
        recs.append("continue burn-in until feedback and outcomes cover multiple playbooks")
    return tuple(dict.fromkeys(recs))


def _dt(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value)
    if len(text) == 10 and text.count("-") == 2:
        text = text + "T00:00:00+00:00"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _int(value: object) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _float(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
