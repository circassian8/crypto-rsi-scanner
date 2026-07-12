"""Read-only helpers for presenting Crypto Radar Decision Model v2 fields.

The scoring model owns these values.  This module only projects already-
persisted fields into operator surfaces and deliberately returns no defaults
for legacy rows, so older artifacts cannot be silently promoted.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .decision_models import actionability_score_cohort


DECISION_MODEL_FIELD_NAMES = (
    "decision_model_version",
    "decision_model_enabled",
    "thesis_origin",
    "directional_bias",
    "catalyst_status",
    "confidence_band",
    "timing_state",
    "tradability_status",
    "radar_route",
    "radar_route_reason",
    "radar_actionable",
    "actionability_score",
    "evidence_confidence_score",
    "risk_score",
    "actionability_score_components",
    "actionability_penalty_components",
    "evidence_confidence_components",
    "evidence_confidence_score_components",
    "risk_score_components",
    "decision_hard_blockers",
    "decision_soft_penalties",
    "decision_warnings",
    "decision_missing_data",
    "why_still_worth_reviewing",
    "radar_what_confirms",
    "radar_what_invalidates",
    "actionability_score_cohort",
    "anomaly_type",
)

PREVIEW_LANE_TITLES = {
    "actionable_market_led": "Actionable Market-Led Ideas",
    "high_confidence_catalyst": "High-Confidence Catalyst Ideas",
    "rapid_market_anomaly": "Rapid Anomalies",
    "fade_exhaustion_review": "Fade / Exhaustion Review",
    "calendar_risk": "Calendar / Risk",
    "decision_diagnostic": "Decision Diagnostics",
}

PREVIEW_LANE_ORDER = tuple(PREVIEW_LANE_TITLES)


def decision_model_values(*rows: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return explicit v2 fields from mappings and their component payloads."""

    merged: dict[str, Any] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        for components_key in ("score_components", "latest_score_components"):
            components = row.get(components_key)
            if isinstance(components, Mapping):
                _copy_fields(merged, components)
        _copy_fields(merged, row)
    if not decision_model_is_enabled(merged):
        return {}
    if not merged.get("actionability_score_cohort"):
        cohort = actionability_score_cohort(merged.get("actionability_score"))
        if cohort:
            merged["actionability_score_cohort"] = cohort
    return merged


def decision_model_is_enabled(values: Mapping[str, Any]) -> bool:
    version = str(values.get("decision_model_version") or "").strip()
    enabled = values.get("decision_model_enabled")
    return version == "crypto_radar_decision_model_v2" and enabled is True


def decision_preview_lane(values: Mapping[str, Any]) -> str:
    """Map a v2 route to one operator preview lane without changing routing."""

    if not decision_model_is_enabled(values):
        return "decision_diagnostic"
    route = str(values.get("radar_route") or "diagnostic").strip().casefold()
    origin = str(values.get("thesis_origin") or "").strip().casefold()
    confidence = str(values.get("confidence_band") or "").strip().casefold()
    if route in {"actionable_watch", "high_confidence_watch"} and origin == "market_led":
        return "actionable_market_led"
    if route == "high_confidence_watch" or (
        route == "actionable_watch" and origin in {"catalyst_led", "mixed"} and confidence == "high_confidence"
    ):
        return "high_confidence_catalyst"
    if route == "rapid_market_anomaly":
        return "rapid_market_anomaly"
    if route == "fade_exhaustion_review":
        return "fade_exhaustion_review"
    if route == "calendar_risk":
        return "calendar_risk"
    if route == "actionable_watch":
        return "actionable_market_led" if origin in {"market_led", "technical_led"} else "high_confidence_catalyst"
    return "decision_diagnostic"


def group_decision_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    include_diagnostics: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    groups = {lane: [] for lane in PREVIEW_LANE_ORDER}
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        row = dict(raw)
        values = decision_model_values(row)
        if not values:
            continue
        lane = decision_preview_lane(values)
        if lane == "decision_diagnostic" and not include_diagnostics:
            continue
        groups[lane].append(row)
    for lane_rows in groups.values():
        lane_rows.sort(key=_decision_row_rank, reverse=True)
    return groups


def decision_model_markdown_lines(values: Mapping[str, Any]) -> list[str]:
    """Render transparent, non-prescriptive v2 decision details."""

    if not decision_model_is_enabled(values):
        return []
    lines = [
        f"- Decision model: {values.get('decision_model_version')}",
        f"- Radar route: {values.get('radar_route') or 'diagnostic'}",
        f"- Radar actionable: {str(bool(values.get('radar_actionable'))).lower()}",
        f"- Thesis origin / directional bias: {values.get('thesis_origin') or 'unknown'} / {values.get('directional_bias') or 'neutral'}",
        f"- Catalyst status: {values.get('catalyst_status') or 'unknown'}",
        f"- Confidence / timing / tradability: {values.get('confidence_band') or 'diagnostic'} / {values.get('timing_state') or 'stale'} / {values.get('tradability_status') or 'blocked'}",
        (
            "- Actionability / evidence confidence / risk: "
            f"{_score(values.get('actionability_score'))} / "
            f"{_score(values.get('evidence_confidence_score'))} / "
            f"{_score(values.get('risk_score'))}"
        ),
    ]
    reason = str(values.get("radar_route_reason") or "").strip()
    if reason:
        lines.append(f"- Route reason: {reason}")
    why = _items(values.get("why_still_worth_reviewing"))
    if why:
        lines.append(f"- Why this is still worth human review: {'; '.join(why[:6])}")
    for label, field in (
        ("Hard blockers", "decision_hard_blockers"),
        ("Soft penalties", "decision_soft_penalties"),
        ("Missing data", "decision_missing_data"),
        ("Decision warnings", "decision_warnings"),
        ("What confirms", "radar_what_confirms"),
        ("What invalidates", "radar_what_invalidates"),
    ):
        items = _items(values.get(field))
        lines.append(f"- {label}: {'; '.join(items[:6]) if items else 'none'}")
    for label, field in (
        ("Actionability components", "actionability_score_components"),
        ("Actionability penalties", "actionability_penalty_components"),
        ("Evidence-confidence components", "evidence_confidence_components"),
        ("Evidence-confidence components", "evidence_confidence_score_components"),
        ("Risk components", "risk_score_components"),
    ):
        components = values.get(field)
        if isinstance(components, Mapping) and components:
            rendered = "; ".join(f"{key}={value}" for key, value in sorted(components.items()))
            lines.append(f"- {label}: {rendered}")
    if str(values.get("catalyst_status") or "").casefold() == "unknown":
        lines.append("- Catalyst unknown: this lowers evidence confidence but is not, by itself, a hard blocker for a market-led idea.")
    if any("manip" in item.casefold() or "illiquid" in item.casefold() for item in _items(values.get("decision_warnings"))):
        lines.append("- Higher manipulation risk: review liquidity, spread, turnover, and venue concentration manually.")
    lines.append("- Research idea, not a trade instruction.")
    return lines


def _copy_fields(target: dict[str, Any], source: Mapping[str, Any]) -> None:
    for field in DECISION_MODEL_FIELD_NAMES:
        value = source.get(field)
        if value not in (None, "", [], {}, ()):
            target[field] = value


def _items(value: Any) -> list[str]:
    if value in (None, "", [], {}, ()):
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.replace(";", ",").split(",") if item.strip()]
    if isinstance(value, Mapping):
        return [f"{key}={child}" for key, child in value.items()]
    if isinstance(value, Iterable):
        return [str(item) for item in value if str(item)]
    return [str(value)]


def _score(value: Any) -> str:
    try:
        return f"{float(value):.1f}/100"
    except (TypeError, ValueError):
        return "n/a"


def _decision_row_rank(row: Mapping[str, Any]) -> tuple[float, float, str]:
    values = decision_model_values(row)
    try:
        actionability = float(values.get("actionability_score") or 0.0)
    except (TypeError, ValueError):
        actionability = 0.0
    try:
        evidence = float(values.get("evidence_confidence_score") or 0.0)
    except (TypeError, ValueError):
        evidence = 0.0
    return actionability, evidence, str(row.get("symbol") or "")


__all__ = (
    "DECISION_MODEL_FIELD_NAMES",
    "PREVIEW_LANE_ORDER",
    "PREVIEW_LANE_TITLES",
    "actionability_score_cohort",
    "decision_model_is_enabled",
    "decision_model_markdown_lines",
    "decision_model_values",
    "decision_preview_lane",
    "group_decision_rows",
)
