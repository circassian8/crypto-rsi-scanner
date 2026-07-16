"""Closed point-in-time attribution for empirical missed opportunities.

The future endpoint decides whether a move is economically meaningful.  This
module never reads that endpoint: it classifies only the already-frozen replay
trace and observation fields that existed when the radar made its decision.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

from ..radar.decision_models import RadarDecisionConfig


REASON_TAXONOMY = (
    "no_anomaly_generated",
    "insufficient_history",
    "data_stale",
    "liquidity_gate",
    "spread_unavailable",
    "proxy_only_data_cap",
    "actionability_below_threshold",
    "risk_too_high",
    "duplicate_suppression",
    "identity_failure",
    "calendar_risk",
    "missing_technical_context",
    "catalyst_uncertainty",
    "feature_bug",
    "universe_exclusion",
    "outcome_outside_supported_horizon",
    "unclassified_decision_suppression",
)

_STAGE_REASONS = {
    "no_anomaly_generated": "no_anomaly_generated",
    "insufficient_history": "insufficient_history",
    "identity_failure": "identity_failure",
    "universe_exclusion": "universe_exclusion",
    "outside_selected_partition": "outcome_outside_supported_horizon",
    "canonical_projection_invalid": "feature_bug",
}
_TOKEN_REASONS = (
    (("stale", "freshness"), "data_stale"),
    (("liquidity", "turnover"), "liquidity_gate"),
    (("spread", "execution_quality"), "spread_unavailable"),
    (("proxy",), "proxy_only_data_cap"),
    (("duplicate", "dedupe", "cooldown"), "duplicate_suppression"),
    (("identity", "resolver"), "identity_failure"),
    (("calendar", "scheduled_risk"), "calendar_risk"),
    (("technical", "rsi"), "missing_technical_context"),
    (("catalyst", "source_evidence"), "catalyst_uncertainty"),
    (("risk", "manipulation"), "risk_too_high"),
    (("history", "baseline"), "insufficient_history"),
    (("schema", "projection", "unit", "feature"), "feature_bug"),
)
_PRIMARY_ORDER = REASON_TAXONOMY


def classify_missed_attribution(
    trace: Mapping[str, Any] | None,
    observation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return closed reason codes without consulting any future outcome."""

    row = dict(trace or {})
    observed = dict(observation or {})
    reasons: set[str] = set()
    evidence: list[dict[str, str]] = []
    stage = _text(row.get("failure_stage"))
    if stage in _STAGE_REASONS:
        _add(reasons, evidence, _STAGE_REASONS[stage], "failure_stage", stage)

    blockers = _strings(row.get("hard_blockers"))
    warnings = _strings(row.get("warnings"))
    for source, value in (("hard_blocker", item) for item in blockers):
        _token_reasons(reasons, evidence, source, value)
    for source, value in (("warning", item) for item in warnings):
        _token_reasons(reasons, evidence, source, value)

    if observed.get("point_in_time_universe_member") is False:
        _add(reasons, evidence, "universe_exclusion", "observation", "membership_false")
    baseline = _text(observed.get("baseline_status"))
    if baseline and baseline != "warm":
        _add(reasons, evidence, "insufficient_history", "baseline_status", baseline)
    freshness = _text(observed.get("freshness_status"))
    if freshness in {"stale", "expired", "future", "unknown"}:
        _add(reasons, evidence, "data_stale", "freshness_status", freshness)
    data_mode = _text(observed.get("data_quality_mode"))
    if "proxy" in data_mode:
        _add(reasons, evidence, "proxy_only_data_cap", "data_quality_mode", data_mode)

    spread = _text(row.get("spread_status"))
    if spread in {"unavailable", "missing", "stale", "unknown"}:
        _add(reasons, evidence, "spread_unavailable", "spread_status", spread)
    catalyst = _text(row.get("catalyst_status"))
    if catalyst in {"unknown", "missing", "unavailable", "unconfirmed"}:
        _add(reasons, evidence, "catalyst_uncertainty", "catalyst_status", catalyst)
    if row.get("rsi_context_present") is False:
        _add(
            reasons,
            evidence,
            "missing_technical_context",
            "rsi_context_present",
            "false",
        )

    cfg = RadarDecisionConfig()
    actionability = _number(row.get("actionability_score"))
    risk = _number(row.get("risk_score"))
    route = _text(row.get("radar_route"))
    if route == "diagnostic" and actionability is not None:
        if actionability < float(cfg.dashboard_watch_threshold):
            _add(
                reasons,
                evidence,
                "actionability_below_threshold",
                "actionability_score",
                str(actionability),
            )
    if risk is not None and risk >= 80.0:
        _add(reasons, evidence, "risk_too_high", "risk_score", str(risk))
    if route == "calendar_risk":
        _add(reasons, evidence, "calendar_risk", "radar_route", route)

    if not reasons:
        _add(
            reasons,
            evidence,
            "unclassified_decision_suppression",
            "failure_stage",
            stage or "missing",
        )
    ordered = [reason for reason in _PRIMARY_ORDER if reason in reasons]
    return {
        "primary_reason": ordered[0],
        "reason_codes": ordered,
        "reason_evidence": sorted(
            evidence,
            key=lambda item: (item["reason"], item["source"], item["value"]),
        ),
        "reason_taxonomy": list(REASON_TAXONOMY),
        "uses_future_outcome": False,
        "causal_claim": False,
        "research_only": True,
        "auto_apply": False,
    }


def closed_reason_counts(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Count all declared reasons, retaining explicit zero-sample rows."""

    counts: Counter[str] = Counter()
    primary: Counter[str] = Counter()
    for row in rows:
        reason = _text(row.get("primary_reason"))
        if reason in REASON_TAXONOMY:
            primary[reason] += 1
        for value in _strings(row.get("reason_codes")):
            if value in REASON_TAXONOMY:
                counts[value] += 1
    return [
        {
            "reason": reason,
            "primary_count": primary[reason],
            "contributing_count": counts[reason],
            "sample_status": "observed" if counts[reason] else "zero_sample",
            "research_only": True,
            "auto_apply": False,
        }
        for reason in REASON_TAXONOMY
    ]


def _token_reasons(
    reasons: set[str], evidence: list[dict[str, str]], source: str, value: str
) -> None:
    normalized = value.casefold()
    for tokens, reason in _TOKEN_REASONS:
        if any(token in normalized for token in tokens):
            _add(reasons, evidence, reason, source, value)


def _add(
    reasons: set[str],
    evidence: list[dict[str, str]],
    reason: str,
    source: str,
    value: str,
) -> None:
    reasons.add(reason)
    evidence.append({"reason": reason, "source": source, "value": value[:256]})


def _strings(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _text(value: Any) -> str:
    return str(value or "").strip().casefold()


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


__all__ = ["REASON_TAXONOMY", "classify_missed_attribution", "closed_reason_counts"]
