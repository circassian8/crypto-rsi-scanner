"""Source/provider reliability summaries for Event Alpha research artifacts."""

from __future__ import annotations

import math
from statistics import median
from typing import Any, Iterable, Mapping


def format_source_reliability_report(
    alert_rows: Iterable[Mapping[str, Any]],
    *,
    feedback_rows: Iterable[Mapping[str, Any]] = (),
    missed_rows: Iterable[Mapping[str, Any]] = (),
    run_rows: Iterable[Mapping[str, Any]] = (),
) -> str:
    alerts = [dict(row) for row in alert_rows if isinstance(row, Mapping)]
    feedback = [dict(row) for row in feedback_rows if isinstance(row, Mapping)]
    missed = [dict(row) for row in missed_rows if isinstance(row, Mapping)]
    runs = [dict(row) for row in run_rows if isinstance(row, Mapping)]
    merged = _merge_feedback(alerts, feedback)
    lines = [
        "=" * 76,
        "EVENT SOURCE RELIABILITY REPORT (research-only; recommendations only)",
        "=" * 76,
        f"alerts={len(alerts)} · feedback={len(feedback)} · missed={len(missed)} · runs={len(runs)}",
    ]
    if not merged and not missed and not runs:
        lines.append("")
        lines.append("No source reliability artifacts found.")
        return "\n".join(lines)
    lines.append(_feedback_by_provider_line(merged))
    line = _median_by_provider_line(merged, "primary_horizon_return", "median primary return")
    if line:
        lines.append(line)
    line = _median_by_provider_line(merged, "mfe_mae_ratio", "median MFE/MAE")
    if line:
        lines.append(line)
    missed_line = _missed_line(missed)
    if missed_line:
        lines.append(missed_line)
    health_line = _provider_health_line(runs)
    if health_line:
        lines.append(health_line)
    lines.append("")
    lines.append("recommended source priors:")
    lines.extend(f"- {item}" for item in _recommendations(merged, missed, runs))
    lines.append("No alert tiers, thresholds, paper trades, live DB rows, or execution were changed.")
    return "\n".join(line for line in lines if line is not None).rstrip()


def _merge_feedback(alerts: list[dict[str, Any]], feedback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key = {
        str(row.get("key") or row.get("target") or "").strip(): row
        for row in feedback
        if str(row.get("key") or row.get("target") or "").strip()
    }
    out: list[dict[str, Any]] = []
    for alert in alerts:
        merged = dict(alert)
        key = str(alert.get("alert_key") or alert.get("key") or "").strip()
        if key in by_key:
            merged["feedback_label"] = by_key[key].get("label")
            merged["feedback_notes"] = by_key[key].get("notes")
        out.append(merged)
    for row in feedback:
        if str(row.get("key") or "").strip():
            continue
        out.append(dict(row))
    return out


def _provider(row: Mapping[str, Any]) -> str:
    for key in ("source_provider", "provider", "source", "latest_source"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return "unknown"


def _feedback_by_provider_line(rows: list[Mapping[str, Any]]) -> str:
    grouped = _group(rows)
    parts: list[str] = []
    for provider, items in sorted(grouped.items()):
        useful = sum(1 for row in items if row.get("feedback_label") == "useful")
        junk = sum(1 for row in items if row.get("feedback_label") == "junk")
        watch = sum(1 for row in items if row.get("feedback_label") == "watch")
        parts.append(f"{provider}: useful={useful} junk={junk} watch={watch}")
    return "feedback by provider: " + "; ".join(parts) if parts else "feedback by provider: none"


def _median_by_provider_line(rows: list[Mapping[str, Any]], field: str, title: str) -> str:
    parts: list[str] = []
    for provider, items in sorted(_group(rows).items()):
        values = [_float(row.get(field)) for row in items]
        values = [value for value in values if value is not None]
        if not values:
            continue
        value = median(values)
        suffix = "x" if field == "mfe_mae_ratio" else "%"
        if suffix == "%":
            value *= 100
        parts.append(f"{provider}: {value:.2f}{suffix}")
    return f"{title} by provider: " + "; ".join(parts) if parts else ""


def _missed_line(rows: list[Mapping[str, Any]]) -> str:
    if not rows:
        return ""
    counts: dict[str, int] = {}
    for row in rows:
        key = f"{_provider(row)}:{row.get('failure_stage') or 'unknown'}"
        counts[key] = counts.get(key, 0) + 1
    return "missed by provider/stage: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def _provider_health_line(rows: list[Mapping[str, Any]]) -> str:
    if not rows:
        return ""
    warnings = sum(len(row.get("warnings") or ()) for row in rows)
    fetches = sum(int(row.get("provider_fetch_count") or 0) for row in rows)
    cache_hits = sum(int(row.get("provider_cache_hits") or 0) for row in rows)
    cache_misses = sum(int(row.get("provider_cache_misses") or 0) for row in rows)
    return (
        "provider health from run ledger: "
        f"fetches={fetches} cache={cache_hits}/{cache_misses} warnings={warnings}"
    )


def _recommendations(
    rows: list[Mapping[str, Any]],
    missed: list[Mapping[str, Any]],
    runs: list[Mapping[str, Any]],
) -> tuple[str, ...]:
    recs: list[str] = []
    for provider, items in sorted(_group(rows).items()):
        useful = sum(1 for row in items if row.get("feedback_label") == "useful")
        junk = sum(1 for row in items if row.get("feedback_label") == "junk")
        if useful > junk and useful >= 2:
            recs.append(f"positive prior for {provider}; keep current source gate until larger sample")
        if junk > useful and junk >= 2:
            recs.append(f"tighten or demote {provider}; junk feedback exceeds useful feedback")
    stage_counts: dict[str, int] = {}
    for row in missed:
        stage = str(row.get("failure_stage") or "unknown")
        stage_counts[stage] = stage_counts.get(stage, 0) + 1
    for stage, count in sorted(stage_counts.items()):
        if count >= 2:
            recs.append(f"coverage warning: {count} missed opportunities at {stage}")
    if runs and all(int(row.get("raw_events") or 0) == 0 for row in runs[:3]):
        recs.append("source coverage warning: recent runs collected zero raw events")
    if not recs:
        recs.append("collect more feedback and filled outcomes before changing source priors")
    return tuple(dict.fromkeys(recs))


def _group(rows: Iterable[Mapping[str, Any]]) -> dict[str, list[Mapping[str, Any]]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(_provider(row), []).append(row)
    return grouped


def _float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None
