"""Research-only calibration summaries for Event Alpha Radar artifacts."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping

from . import feedback_eligibility


CALIBRATION_PRIORS_SCHEMA_VERSION = "event_alpha_calibration_priors_v2"
CALIBRATION_PRIORS_ROW_TYPE = "event_alpha_calibration_priors"
PRIOR_GROUP_NAMES = (
    "playbook_priors",
    "provider_priors",
    "llm_role_priors",
    "tier_priors",
    "source_pack_priors",
    "source_domain_priors",
    "market_confirmation_priors",
    "catalyst_frame_priors",
)


def format_calibration_report(
    alert_rows: Iterable[Mapping[str, Any]],
    *,
    feedback_rows: Iterable[Mapping[str, Any]] = (),
    core_rows: Iterable[Mapping[str, Any]] = (),
    missed_rows: Iterable[Mapping[str, Any]] = (),
    now: Any = None,
) -> str:
    """Print deterministic calibration guidance without changing thresholds."""
    alerts = [dict(row) for row in alert_rows if isinstance(row, Mapping)]
    feedback = [dict(row) for row in feedback_rows if isinstance(row, Mapping)]
    cores = [dict(row) for row in core_rows if isinstance(row, Mapping)]
    missed = [dict(row) for row in missed_rows if isinstance(row, Mapping)]
    evaluated_at = _trusted_now(now)
    eligible, excluded, reason_counts = (
        feedback_eligibility.partition_joined_calibration_feedback(
            feedback,
            cores,
            now=evaluated_at,
        )
    )
    merged = [_prepare_feedback_projection(row) for row in eligible]
    lines = [
        "=" * 76,
        "EVENT ALPHA CALIBRATION REPORT (research-only; recommendations only)",
        "=" * 76,
        f"alerts={len(alerts)} · feedback_supplied={len(feedback)} · "
        f"feedback_eligible={len(eligible)} · feedback_excluded={len(excluded)} · "
        f"missed={len(missed)}",
        "feedback_firewall="
        f"v{feedback_eligibility.FEEDBACK_ELIGIBILITY_CONTRACT_VERSION} · "
        f"evaluated_at={evaluated_at.isoformat()}",
        "feedback_exclusion_reasons=" + _format_reason_counts(reason_counts),
    ]
    if not merged and not missed:
        lines.append("")
        lines.append("No calibration artifacts found.")
        return "\n".join(lines)
    for title, field in (
        ("feedback by playbook", "playbook_type"),
        ("feedback by source", "feedback_source"),
        ("feedback by provider", "source_provider"),
        ("feedback by source domain", "source_domain"),
        ("feedback by provider/domain", "provider_domain_key"),
        ("feedback by tier", "final_route_after_quality_gate"),
        ("feedback by route/lane", "route_lane_key"),
        ("LLM role usefulness", "llm_asset_role"),
        ("feedback by impact path type", "impact_path_type"),
        ("feedback by candidate role", "candidate_role"),
        ("feedback by source class", "source_class"),
        ("feedback by source pack", "source_pack"),
        ("feedback by accepted evidence reason", "accepted_evidence_reason_codes"),
        ("feedback by incident id", "incident_id"),
        ("feedback by evidence specificity", "evidence_specificity"),
        ("feedback by market confirmation level", "market_confirmation_level"),
        ("feedback by market freshness", "market_context_freshness_status"),
        ("feedback by catalyst frame status", "catalyst_frame_status"),
        ("feedback by main frame type", "main_frame_type"),
        ("feedback by opportunity level", "opportunity_level"),
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
    core_rows: Iterable[Mapping[str, Any]] = (),
    generated_at: Any = None,
    now: Any = None,
    min_sample: int = 5,
) -> dict[str, Any]:
    """Build reviewable priors from artifacts without applying them."""
    if type(min_sample) is not int or min_sample < 1:
        raise ValueError("min_sample must be a positive integer")
    alerts = [dict(row) for row in alert_rows if isinstance(row, Mapping)]
    feedback = [dict(row) for row in feedback_rows if isinstance(row, Mapping)]
    cores = [dict(row) for row in core_rows if isinstance(row, Mapping)]
    evaluated_at = _trusted_now(now if now is not None else generated_at)
    generated_dt = _trusted_now(generated_at if generated_at is not None else evaluated_at)
    if generated_dt < evaluated_at:
        raise ValueError("generated_at must not precede the feedback firewall evaluation time")
    eligible, excluded, reason_counts = (
        feedback_eligibility.partition_joined_calibration_feedback(
            feedback,
            cores,
            now=evaluated_at,
        )
    )
    merged = [_prepare_feedback_projection(row) for row in eligible]
    groups = {
        "playbook_priors": _prior_group(merged, "playbook_type", min_sample=min_sample),
        "provider_priors": _prior_group(merged, "source_provider", min_sample=min_sample),
        "llm_role_priors": _prior_group(merged, "llm_asset_role", min_sample=min_sample),
        "tier_priors": _prior_group(
            merged,
            "final_route_after_quality_gate",
            min_sample=min_sample,
        ),
        "source_pack_priors": _prior_group(merged, "source_pack", min_sample=min_sample),
        "source_domain_priors": _prior_group(merged, "source_domain", min_sample=min_sample),
        "market_confirmation_priors": _prior_group(
            merged,
            "market_confirmation_level",
            min_sample=min_sample,
        ),
        "catalyst_frame_priors": _prior_group(
            merged,
            "main_frame_type",
            min_sample=min_sample,
        ),
    }
    eligible_for_auto_apply = any(
        row.get("score_adjustment") not in (None, 0)
        for group in groups.values()
        for row in group.values()
    )
    payload = {
        "schema_version": CALIBRATION_PRIORS_SCHEMA_VERSION,
        "row_type": CALIBRATION_PRIORS_ROW_TYPE,
        "generated_at": generated_dt.isoformat(),
        "feedback_firewall_evaluated_at": evaluated_at.isoformat(),
        "feedback_firewall_applied": True,
        "feedback_eligibility_contract_version": (
            feedback_eligibility.FEEDBACK_ELIGIBILITY_CONTRACT_VERSION
        ),
        "alert_rows_supplied": len(alerts),
        "feedback_rows_supplied": len(feedback),
        "feedback_rows_eligible": len(eligible),
        "feedback_rows_excluded": len(excluded),
        "feedback_exclusion_reason_counts": dict(reason_counts),
        "min_sample": min_sample,
        "min_sample_warning": len(merged) < min_sample,
        **groups,
        "research_only": True,
        "recommendation_only": True,
        "eligible_for_auto_apply": eligible_for_auto_apply,
        "auto_apply": False,
    }
    return payload


def write_calibration_priors(
    path: str | Path,
    alert_rows: Iterable[Mapping[str, Any]],
    *,
    feedback_rows: Iterable[Mapping[str, Any]] = (),
    core_rows: Iterable[Mapping[str, Any]] = (),
    generated_at: Any = None,
    now: Any = None,
    min_sample: int = 5,
) -> dict[str, Any]:
    payload = build_calibration_priors(
        alert_rows,
        feedback_rows=feedback_rows,
        core_rows=core_rows,
        generated_at=generated_at,
        now=now,
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
        "feedback: "
        f"supplied={payload.get('feedback_rows_supplied')} "
        f"eligible={payload.get('feedback_rows_eligible')} "
        f"excluded={payload.get('feedback_rows_excluded')}",
        "feedback_exclusion_reasons: "
        + _format_reason_counts(payload.get("feedback_exclusion_reason_counts") or {}),
        f"min_sample_warning: {warning}",
        f"eligible_for_auto_apply: {'yes' if payload.get('eligible_for_auto_apply') is True else 'no'}",
        f"auto_apply: {'yes' if payload.get('auto_apply') is True else 'no'}",
        "No thresholds, alert tiers, paper trades, live DB rows, or execution were changed.",
    ])


def _feedback_line(title: str, rows: list[Mapping[str, Any]], field: str) -> str:
    grouped = _group(
        (row for row in rows if _has_group_value(row.get(field))),
        field,
    )
    parts: list[str] = []
    for key, items in sorted(grouped.items()):
        useful = sum(1 for row in items if row.get("feedback_label") == "useful")
        junk = sum(1 for row in items if row.get("feedback_label") == "junk")
        watch = sum(1 for row in items if row.get("feedback_label") == "watch")
        ignored = sum(1 for row in items if row.get("feedback_label") in {"ignored", "ignore"})
        labeled = useful + junk + watch + ignored
        if labeled:
            useful_rate = useful / labeled if labeled else 0.0
            junk_rate = junk / labeled if labeled else 0.0
            samples = ", ".join(_sample_targets(items, limit=2))
            reasons = ", ".join(_sample_reasons(items, limit=2))
            parts.append(
                f"{key}: useful={useful} junk={junk} watch={watch} ignored={ignored} "
                f"useful_rate={useful_rate:.0%} junk_rate={junk_rate:.0%}"
                + (f" samples={samples}" if samples else "")
                + (f" reasons={reasons}" if reasons else "")
            )
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


def _provider_domain_key(row: Mapping[str, Any]) -> str:
    provider = str(row.get("source_provider") or "unknown")
    domain = str(row.get("source_provider_domain") or row.get("source_domain") or "unknown")
    return f"{provider}/{domain}"


def _route_lane_key(row: Mapping[str, Any]) -> str:
    route = str(row.get("final_route_after_quality_gate") or "unknown")
    lane = str(row.get("lane") or "unknown")
    return f"{route}/{lane}"


def _sample_targets(rows: Iterable[Mapping[str, Any]], *, limit: int) -> tuple[str, ...]:
    out: list[str] = []
    for row in rows:
        value = str(
            row.get("feedback_target")
            or row.get("core_opportunity_id")
            or ""
        ).strip()
        if value:
            out.append(value)
        if len(out) >= limit:
            break
    return tuple(dict.fromkeys(out))


def _sample_reasons(rows: Iterable[Mapping[str, Any]], *, limit: int) -> tuple[str, ...]:
    out: list[str] = []
    for row in rows:
        value = str(row.get("feedback_notes") or "").strip()
        if value:
            out.append(value[:80])
        if len(out) >= limit:
            break
    return tuple(dict.fromkeys(out))


def _prior_group(
    rows: list[Mapping[str, Any]],
    field: str,
    *,
    min_sample: int,
) -> dict[str, Any]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        key = str(row.get(field) or "unknown")
        grouped.setdefault(key, []).append(row)
    out: dict[str, Any] = {}
    for key, items in sorted(grouped.items()):
        useful = sum(1 for row in items if row.get("feedback_label") == "useful")
        junk = sum(1 for row in items if row.get("feedback_label") == "junk")
        watch = sum(1 for row in items if row.get("feedback_label") == "watch")
        primary = [_float(row.get("primary_horizon_return")) for row in items]
        primary = [value for value in primary if value is not None]
        score_adjustment = 0
        if key != "unknown" and len(items) >= min_sample:
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


def _prepare_feedback_projection(row: Mapping[str, Any]) -> dict[str, Any]:
    prepared = dict(row)
    prepared["provider_domain_key"] = _provider_domain_key(prepared)
    prepared["route_lane_key"] = _route_lane_key(prepared)
    return prepared


def _trusted_now(value: Any) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    parsed = feedback_eligibility.parse_aware_feedback_time(value)
    if parsed is None:
        raise ValueError("calibration now must be a finite timezone-aware timestamp")
    return parsed


def _format_reason_counts(values: Mapping[str, Any]) -> str:
    parts = [
        f"{key}={value}"
        for key, value in sorted(values.items())
        if type(key) is str and type(value) is int and value > 0
    ]
    return ", ".join(parts) if parts else "none"


def _group(rows: Iterable[Mapping[str, Any]], field: str) -> dict[str, list[Mapping[str, Any]]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        value = row.get(field)
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes, Mapping)):
            keys = tuple(dict.fromkeys(str(item) for item in value if str(item)))
        else:
            keys = (str(value or "unknown"),)
        for key in keys or ("unknown",):
            grouped.setdefault(key, []).append(row)
    return grouped


def _has_group_value(value: Any) -> bool:
    if value is None or value == "":
        return False
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, Mapping)):
        return any(str(item) for item in value)
    return True


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
