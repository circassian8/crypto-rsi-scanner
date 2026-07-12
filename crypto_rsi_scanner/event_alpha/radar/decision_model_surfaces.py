"""Read-only helpers for presenting Crypto Radar Decision Model v2 fields.

The scoring model owns these values.  This module only projects already-
persisted fields into operator surfaces and deliberately returns no defaults
for legacy rows, so older artifacts cannot be silently promoted.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any
from urllib.parse import quote

from ..artifacts.schema.decision_model import validate_contract
from .decision_models import actionability_score_cohort


DECISION_MODEL_FIELD_NAMES = (
    "research_only",
    "decision_model_version",
    "decision_model_enabled",
    "thesis_origin",
    "primary_thesis_origin",
    "thesis_origins",
    "directional_bias",
    "catalyst_status",
    "confidence_band",
    "timing_state",
    "tradability_status",
    "spread_status",
    "radar_route",
    "radar_route_reason",
    "radar_actionable",
    "actionability_score",
    "evidence_confidence_score",
    "risk_score",
    "urgency_score",
    "market_phase",
    "preferred_horizon",
    "expires_at",
    "chase_risk_score",
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
    "decision_source_side_effect_safety_failed",
    "decision_source_secret_safety_failed",
    "decision_source_path_safety_failed",
)

PREVIEW_LANE_TITLES = {
    "high_confidence": "High-Confidence Ideas",
    "actionable": "Actionable Ideas",
    "rapid_market_anomaly": "Rapid Market Anomalies",
    "dashboard_watch": "Dashboard Watch",
    "fade_exhaustion_review": "Fade / Exhaustion Review",
    "risk_watch": "Risk Watch",
    "calendar_risk": "Calendar / Scheduled Risk",
    "decision_diagnostic": "Decision Diagnostics",
}

PREVIEW_LANE_ORDER = tuple(PREVIEW_LANE_TITLES)


def decision_model_values(*rows: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return one complete, explicit v2 authority without cross-row merging.

    Argument order is authority order.  A malformed explicit v2 payload fails
    closed instead of borrowing fields from a later row or an unversioned
    mapping.  Explicit empty lists/maps are meaningful canonical values and
    must survive projection into outcomes and other persisted surfaces.
    """

    for row in rows:
        if not isinstance(row, Mapping):
            continue
        authorities: list[Mapping[str, Any]] = [row]
        authorities.extend(
            components
            for components_key in ("score_components", "latest_score_components")
            if isinstance((components := row.get(components_key)), Mapping)
        )
        for authority in authorities:
            if not _has_decision_model_marker(authority):
                continue
            if not decision_model_is_enabled(authority):
                return {}
            projection = _project_fields(authority)
            if not projection.get("actionability_score_cohort"):
                cohort = actionability_score_cohort(projection.get("actionability_score"))
                if cohort:
                    projection["actionability_score_cohort"] = cohort
            contract_payload = dict(authority)
            contract_payload.update(projection)
            if validate_contract(contract_payload):
                return {}
            return projection
    return {}


def decision_model_is_enabled(values: Mapping[str, Any]) -> bool:
    version = str(values.get("decision_model_version") or "").strip()
    enabled = values.get("decision_model_enabled")
    return version == "crypto_radar_decision_model_v2" and enabled is True


def decision_preview_lane(values: Mapping[str, Any]) -> str:
    """Map a v2 route to one operator preview lane without changing routing."""

    projected = decision_model_values(values)
    if not projected:
        return "decision_diagnostic"
    route = str(projected.get("radar_route") or "diagnostic").strip().casefold()
    if route == "high_confidence_watch":
        return "high_confidence"
    if route == "actionable_watch":
        return "actionable"
    if route == "rapid_market_anomaly":
        return "rapid_market_anomaly"
    if route == "dashboard_watch":
        return "dashboard_watch"
    if route == "fade_exhaustion_review":
        return "fade_exhaustion_review"
    if route == "risk_watch":
        return "risk_watch"
    if route == "calendar_risk":
        return "calendar_risk"
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
            if include_diagnostics and _row_has_decision_model_marker(row):
                groups["decision_diagnostic"].append(row)
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

    raw_values = values
    projected = decision_model_values(values)
    if not projected:
        return []
    values = projected
    lines = [
        f"- Decision model: {values.get('decision_model_version')}",
        f"- Radar route: {values.get('radar_route') or 'diagnostic'}",
        f"- Radar actionable: {str(bool(values.get('radar_actionable'))).lower()}",
        (
            "- Primary / contributing origins: "
            f"{values.get('primary_thesis_origin') or values.get('thesis_origin') or 'unknown'} / "
            f"{', '.join(_items(values.get('thesis_origins'))) or values.get('thesis_origin') or 'unknown'}"
        ),
        f"- Directional bias: {values.get('directional_bias') or 'neutral'}",
        f"- Catalyst status: {values.get('catalyst_status') or 'unknown'}",
        (
            "- Confidence / phase / timing: "
            f"{values.get('confidence_band') or 'diagnostic'} / "
            f"{values.get('market_phase') or 'unknown'} / {values.get('timing_state') or 'stale'}"
        ),
        (
            "- Tradability / spread: "
            f"{values.get('tradability_status') or 'blocked'} / {values.get('spread_status') or 'unavailable'}"
        ),
        (
            "- Actionability / evidence confidence / risk: "
            f"{_score(values.get('actionability_score'))} / "
            f"{_score(values.get('evidence_confidence_score'))} / "
            f"{_score(values.get('risk_score'))}"
        ),
        (
            "- Urgency / chase risk: "
            f"{_score(values.get('urgency_score'))} / {_score(values.get('chase_risk_score'))}"
        ),
        (
            "- Preferred horizon / expiry: "
            f"{values.get('preferred_horizon') or 'unknown'} / {values.get('expires_at') or 'not set'}"
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
    dashboard_id = next(
        (
            str(raw_values.get(field) or "").strip()
            for field in ("core_opportunity_id", "candidate_id", "integrated_candidate_id")
            if str(raw_values.get(field) or "").strip()
        ),
        "",
    )
    if dashboard_id:
        lines.append(f"- Dashboard: /candidate/{quote(dashboard_id, safe='')}")
    lines.append("- Research idea, not a trade instruction.")
    return lines


def _project_fields(source: Mapping[str, Any]) -> dict[str, Any]:
    return {
        field: source[field]
        for field in DECISION_MODEL_FIELD_NAMES
        if field in source and source.get(field) is not None and source.get(field) != ""
    }


def _has_decision_model_marker(source: Mapping[str, Any]) -> bool:
    return any(
        source.get(field) not in (None, "")
        for field in ("decision_model_version", "decision_model_enabled")
    )


def _row_has_decision_model_marker(row: Mapping[str, Any]) -> bool:
    if _has_decision_model_marker(row):
        return True
    return any(
        isinstance(row.get(key), Mapping) and _has_decision_model_marker(row[key])
        for key in ("score_components", "latest_score_components")
    )


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
