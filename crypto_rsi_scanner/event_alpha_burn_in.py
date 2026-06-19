"""Burn-in scorecard for Event Alpha research artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class EventAlphaBurnInScorecard:
    days: int
    run_rows: list[dict[str, Any]]
    alert_rows: list[dict[str, Any]]
    feedback_rows: list[dict[str, Any]]
    missed_rows: list[dict[str, Any]]
    provider_health_rows: dict[str, dict[str, Any]]
    llm_budget_rows: list[dict[str, Any]]


def build_burn_in_scorecard(
    *,
    run_rows: Iterable[Mapping[str, Any]] = (),
    alert_rows: Iterable[Mapping[str, Any]] = (),
    feedback_rows: Iterable[Mapping[str, Any]] = (),
    missed_rows: Iterable[Mapping[str, Any]] = (),
    provider_health_rows: Mapping[str, Mapping[str, Any]] | None = None,
    llm_budget_rows: Iterable[Mapping[str, Any]] = (),
    days: int = 7,
    now: datetime | None = None,
) -> EventAlphaBurnInScorecard:
    cutoff = (now or datetime.now(timezone.utc)).astimezone(timezone.utc) - timedelta(days=max(1, int(days or 1)))
    return EventAlphaBurnInScorecard(
        days=max(1, int(days or 1)),
        run_rows=_filter_rows(run_rows, cutoff, ("started_at", "observed_at", "marked_at")),
        alert_rows=_filter_rows(alert_rows, cutoff, ("observed_at", "started_at")),
        feedback_rows=_filter_rows(feedback_rows, cutoff, ("marked_at", "observed_at")),
        missed_rows=_filter_rows(missed_rows, cutoff, ("observed_at", "detected_at", "created_at")),
        provider_health_rows={str(key): dict(value) for key, value in (provider_health_rows or {}).items()},
        llm_budget_rows=_filter_rows(llm_budget_rows, cutoff, ("date", "updated_at")),
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
        "top playbooks: " + _top_line(alerts, "playbook_type"),
        "worst sources: " + _worst_source_line(alerts, feedback),
        "",
        "recommendations:",
    ]
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
