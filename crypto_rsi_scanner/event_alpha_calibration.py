"""Research-only calibration summaries for Event Alpha Radar artifacts."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping


def format_calibration_report(
    alert_rows: Iterable[Mapping[str, Any]],
    *,
    feedback_rows: Iterable[Mapping[str, Any]] = (),
    missed_rows: Iterable[Mapping[str, Any]] = (),
) -> str:
    """Print deterministic calibration guidance without changing thresholds."""
    alerts = [dict(row) for row in alert_rows if isinstance(row, Mapping)]
    feedback = [dict(row) for row in feedback_rows if isinstance(row, Mapping)]
    missed = [dict(row) for row in missed_rows if isinstance(row, Mapping)]
    merged = _merge_feedback(alerts, feedback)
    lines = [
        "=" * 76,
        "EVENT ALPHA CALIBRATION REPORT (research-only; recommendations only)",
        "=" * 76,
        f"alerts={len(alerts)} · feedback={len(feedback)} · missed={len(missed)}",
    ]
    if not merged and not missed:
        lines.append("")
        lines.append("No calibration artifacts found.")
        return "\n".join(lines)
    for title, field in (
        ("feedback by playbook", "playbook_type"),
        ("feedback by source", "source"),
        ("feedback by provider", "source_provider"),
        ("feedback by tier", "tier"),
        ("LLM role usefulness", "llm_asset_role"),
        ("cluster confidence bucket", "cluster_confidence_bucket"),
    ):
        line = _feedback_line(title, merged, field)
        if line:
            lines.append(line)
    for field, label in (
        ("playbook_type", "median primary horizon return by playbook"),
        ("playbook_type", "median MFE/MAE by playbook"),
    ):
        if "MFE/MAE" in label:
            line = _median_line(label, merged, field, "mfe_mae_ratio")
        else:
            line = _median_line(label, merged, field, "primary_horizon_return")
        if line:
            lines.append(line)
    direction = _hit_line("direction hit rate by playbook", merged, "direction_hit")
    if direction:
        lines.append(direction)
    volatility = _hit_line("volatility hit rate by playbook", merged, "volatility_hit")
    if volatility:
        lines.append(volatility)
    missed_line = _count_line("missed opportunities by failure stage", missed, "failure_stage")
    if missed_line:
        lines.append(missed_line)
    lines.append("")
    lines.append("recommendations:")
    lines.extend(f"- {item}" for item in _recommendations(merged, missed))
    lines.append("No thresholds, alert tiers, paper trades, live DB rows, or execution were changed.")
    return "\n".join(lines).rstrip()


def build_calibration_priors(
    alert_rows: Iterable[Mapping[str, Any]],
    *,
    feedback_rows: Iterable[Mapping[str, Any]] = (),
    generated_at: datetime | None = None,
    min_sample: int = 5,
) -> dict[str, Any]:
    """Build reviewable priors from artifacts without applying them."""
    alerts = [dict(row) for row in alert_rows if isinstance(row, Mapping)]
    feedback = [dict(row) for row in feedback_rows if isinstance(row, Mapping)]
    merged = _merge_feedback(alerts, feedback)
    generated = (generated_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    payload = {
        "schema_version": "event_alpha_calibration_priors_v1",
        "generated_at": generated,
        "min_sample": int(min_sample),
        "min_sample_warning": len(merged) < int(min_sample),
        "playbook_priors": _prior_group(merged, "playbook_type", min_sample=min_sample),
        "provider_priors": _prior_group(merged, "source_provider", fallback_field="source", min_sample=min_sample),
        "llm_role_priors": _prior_group(merged, "llm_asset_role", min_sample=min_sample),
        "tier_priors": _prior_group(merged, "tier", min_sample=min_sample),
        "research_only": True,
    }
    return payload


def write_calibration_priors(
    path: str | Path,
    alert_rows: Iterable[Mapping[str, Any]],
    *,
    feedback_rows: Iterable[Mapping[str, Any]] = (),
    generated_at: datetime | None = None,
    min_sample: int = 5,
) -> dict[str, Any]:
    payload = build_calibration_priors(
        alert_rows,
        feedback_rows=feedback_rows,
        generated_at=generated_at,
        min_sample=min_sample,
    )
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(_json_ready(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def format_priors_export(path: str | Path, payload: Mapping[str, Any]) -> str:
    groups = [
        f"playbooks={len(payload.get('playbook_priors') or {})}",
        f"providers={len(payload.get('provider_priors') or {})}",
        f"llm_roles={len(payload.get('llm_role_priors') or {})}",
        f"tiers={len(payload.get('tier_priors') or {})}",
    ]
    warning = "yes" if payload.get("min_sample_warning") else "no"
    return "\n".join([
        "=" * 76,
        "EVENT ALPHA CALIBRATION PRIORS EXPORTED (research-only; not applied)",
        "=" * 76,
        f"path: {Path(path).expanduser()}",
        f"generated_at: {payload.get('generated_at')}",
        "groups: " + ", ".join(groups),
        f"min_sample_warning: {warning}",
        "No thresholds, alert tiers, paper trades, live DB rows, or execution were changed.",
    ])


def _merge_feedback(
    alert_rows: list[dict[str, Any]],
    feedback_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    feedback_by_key: dict[str, dict[str, Any]] = {}
    for row in feedback_rows:
        key = str(row.get("key") or row.get("target") or "").strip()
        if key:
            feedback_by_key[key] = row
    out: list[dict[str, Any]] = []
    for row in alert_rows:
        merged = dict(row)
        key = str(row.get("alert_key") or row.get("key") or "").strip()
        feedback = feedback_by_key.get(key)
        if feedback:
            merged["feedback_label"] = feedback.get("label")
            merged["feedback_notes"] = feedback.get("notes")
        merged["cluster_confidence_bucket"] = _cluster_bucket(row)
        out.append(merged)
    for row in feedback_rows:
        if str(row.get("key") or "").strip():
            continue
        out.append({
            "playbook_type": row.get("playbook_type") or "unmatched",
            "source": row.get("source") or "feedback",
            "tier": row.get("route") or "feedback",
            "feedback_label": row.get("label"),
            "llm_asset_role": row.get("llm_asset_role"),
            "cluster_confidence_bucket": "unknown",
        })
    return out


def _feedback_line(title: str, rows: list[Mapping[str, Any]], field: str) -> str:
    grouped = _group(rows, field)
    parts: list[str] = []
    for key, items in sorted(grouped.items()):
        useful = sum(1 for row in items if row.get("feedback_label") == "useful")
        junk = sum(1 for row in items if row.get("feedback_label") == "junk")
        watch = sum(1 for row in items if row.get("feedback_label") == "watch")
        if useful or junk or watch:
            parts.append(f"{key}: useful={useful} junk={junk} watch={watch}")
    return f"{title}: " + "; ".join(parts) if parts else ""


def _median_line(title: str, rows: list[Mapping[str, Any]], group_field: str, value_field: str) -> str:
    parts: list[str] = []
    for key, items in sorted(_group(rows, group_field).items()):
        values = [_float(row.get(value_field)) for row in items]
        values = [value for value in values if value is not None]
        if values:
            suffix = "x" if value_field == "mfe_mae_ratio" else "%"
            scaled = median(values) if suffix == "x" else median(values) * 100
            parts.append(f"{key}: {scaled:.2f}{suffix}")
    return f"{title}: " + "; ".join(parts) if parts else ""


def _hit_line(title: str, rows: list[Mapping[str, Any]], field: str) -> str:
    parts: list[str] = []
    for key, items in sorted(_group(rows, "playbook_type").items()):
        values = [row.get(field) for row in items if row.get(field) is not None]
        if values:
            hits = sum(bool(value) for value in values)
            parts.append(f"{key}: {hits}/{len(values)}")
    return f"{title}: " + "; ".join(parts) if parts else ""


def _count_line(title: str, rows: list[Mapping[str, Any]], field: str) -> str:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get(field) or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return f"{title}: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())) if counts else ""


def _recommendations(rows: list[Mapping[str, Any]], missed: list[Mapping[str, Any]]) -> tuple[str, ...]:
    recs: list[str] = []
    by_playbook = _group(rows, "playbook_type")
    for playbook, items in sorted(by_playbook.items()):
        useful = sum(1 for row in items if row.get("feedback_label") == "useful")
        junk = sum(1 for row in items if row.get("feedback_label") == "junk")
        if junk > useful and junk >= 2:
            recs.append(f"raise manual review threshold or tighten source gates for {playbook}")
        elif useful > junk and useful >= 2:
            recs.append(f"preserve current {playbook} routing until more outcomes accrue")
    stages = {str(row.get("failure_stage") or "unknown") for row in missed}
    if "resolver_missed_asset" in stages:
        recs.append("review resolver aliases and LLM extraction validation for missed asset links")
    if "no_source_event" in stages:
        recs.append("review source coverage and catalyst-search queries for large movers with no evidence")
    if not recs:
        recs.append("collect more reviewed feedback/outcome rows before changing thresholds")
    return tuple(dict.fromkeys(recs))


def _prior_group(
    rows: list[Mapping[str, Any]],
    field: str,
    *,
    fallback_field: str | None = None,
    min_sample: int,
) -> dict[str, Any]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        key = str(row.get(field) or (row.get(fallback_field) if fallback_field else "") or "unknown")
        grouped.setdefault(key, []).append(row)
    out: dict[str, Any] = {}
    for key, items in sorted(grouped.items()):
        useful = sum(1 for row in items if row.get("feedback_label") == "useful")
        junk = sum(1 for row in items if row.get("feedback_label") == "junk")
        watch = sum(1 for row in items if row.get("feedback_label") == "watch")
        primary = [_float(row.get("primary_horizon_return")) for row in items]
        primary = [value for value in primary if value is not None]
        score_adjustment = 0
        if useful > junk and useful >= 2:
            score_adjustment = 3
        elif junk > useful and junk >= 2:
            score_adjustment = -5
        out[key] = {
            "samples": len(items),
            "useful": useful,
            "junk": junk,
            "watch": watch,
            "median_primary_horizon_return": median(primary) if primary else None,
            "score_adjustment": score_adjustment,
            "min_sample_warning": len(items) < min_sample,
        }
    return out


def _group(rows: Iterable[Mapping[str, Any]], field: str) -> dict[str, list[Mapping[str, Any]]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        key = str(row.get(field) or "unknown")
        grouped.setdefault(key, []).append(row)
    return grouped


def _cluster_bucket(row: Mapping[str, Any]) -> str:
    value = _float(row.get("cluster_confidence"))
    if value is None:
        components = row.get("score_components")
        value = _float(components.get("cluster_confidence")) if isinstance(components, Mapping) else None
    if value is None:
        return "unknown"
    if value >= 75:
        return "high"
    if value >= 45:
        return "medium"
    return "low"


def _float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value
