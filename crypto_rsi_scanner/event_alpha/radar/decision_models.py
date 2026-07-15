"""Public value models for Crypto Radar Decision Model v2."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Mapping


DECISION_MODEL_VERSION = "crypto_radar_decision_model_v2"


class ThesisOrigin(str, Enum):
    MARKET_LED = "market_led"
    CATALYST_LED = "catalyst_led"
    TECHNICAL_LED = "technical_led"
    DERIVATIVES_LED = "derivatives_led"
    ONCHAIN_LED = "onchain_led"
    FUNDAMENTAL_LED = "fundamental_led"
    MACRO_LED = "macro_led"
    MIXED = "mixed"


class DirectionalBias(str, Enum):
    LONG = "long"
    FADE_SHORT_REVIEW = "fade_short_review"
    RISK = "risk"
    NEUTRAL = "neutral"


class CatalystStatus(str, Enum):
    CONFIRMED = "confirmed"
    PLAUSIBLE = "plausible"
    UNKNOWN = "unknown"
    NOT_REQUIRED = "not_required"
    DISPROVEN = "disproven"


class ConfidenceBand(str, Enum):
    DIAGNOSTIC = "diagnostic"
    EXPLORATORY = "exploratory"
    ACTIONABLE = "actionable"
    HIGH_CONFIDENCE = "high_confidence"


class TimingState(str, Enum):
    EARLY = "early"
    ACTIVE = "active"
    EXTENDED = "extended"
    EXHAUSTED = "exhausted"
    SCHEDULED = "scheduled"
    STALE = "stale"


class TradabilityStatus(str, Enum):
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    BLOCKED = "blocked"


class SpreadStatus(str, Enum):
    VERIFIED_GOOD = "verified_good"
    VERIFIED_ACCEPTABLE = "verified_acceptable"
    VERIFIED_WIDE = "verified_wide"
    UNAVAILABLE = "unavailable"
    STALE = "stale"


class MarketPhase(str, Enum):
    EMERGING = "emerging"
    BREAKOUT = "breakout"
    ACCELERATION = "acceleration"
    ACTIVE = "active"
    EXTENDED = "extended"
    EXHAUSTION = "exhaustion"
    REVERSAL = "reversal"


class PreferredHorizon(str, Enum):
    INTRADAY = "intraday"
    ONE_TO_THREE_DAYS = "1d_3d"
    THREE_TO_SEVEN_DAYS = "3d_7d"
    SCHEDULED_WINDOW = "scheduled_window"


class RadarResearchRoute(str, Enum):
    DASHBOARD_WATCH = "dashboard_watch"
    ACTIONABLE_WATCH = "actionable_watch"
    HIGH_CONFIDENCE_WATCH = "high_confidence_watch"
    RAPID_MARKET_ANOMALY = "rapid_market_anomaly"
    FADE_EXHAUSTION_REVIEW = "fade_exhaustion_review"
    RISK_WATCH = "risk_watch"
    CALENDAR_RISK = "calendar_risk"
    DIAGNOSTIC = "diagnostic"


_RUNTIME_FIELDS = {
    "enabled": ("bool", ("EVENT_ALPHA_DECISION_MODEL_V2_ENABLED",)),
    "market_led_enabled": (
        "bool",
        ("EVENT_ALPHA_DECISION_MODEL_V2_MARKET_LED_ENABLED", "EVENT_ALPHA_RADAR_MARKET_LED_ENABLED"),
    ),
    "catalyst_led_enabled": (
        "bool",
        ("EVENT_ALPHA_DECISION_MODEL_V2_CATALYST_LED_ENABLED", "EVENT_ALPHA_RADAR_CATALYST_LED_ENABLED"),
    ),
    "actionability_threshold": (
        "float",
        ("EVENT_ALPHA_DECISION_MODEL_V2_ACTIONABLE_THRESHOLD", "EVENT_ALPHA_RADAR_ACTIONABILITY_THRESHOLD"),
    ),
    "dashboard_watch_threshold": (
        "float",
        ("EVENT_ALPHA_DECISION_MODEL_V2_DASHBOARD_WATCH_THRESHOLD",),
    ),
    "high_confidence_threshold": (
        "float",
        ("EVENT_ALPHA_DECISION_MODEL_V2_HIGH_CONFIDENCE_THRESHOLD", "EVENT_ALPHA_RADAR_HIGH_CONFIDENCE_THRESHOLD"),
    ),
    "high_confidence_evidence_threshold": (
        "float",
        ("EVENT_ALPHA_DECISION_MODEL_V2_HIGH_CONFIDENCE_EVIDENCE_THRESHOLD",),
    ),
    "rapid_anomaly_actionability_threshold": (
        "float",
        ("EVENT_ALPHA_DECISION_MODEL_V2_RAPID_ANOMALY_THRESHOLD",),
    ),
    "rapid_anomaly_urgency_threshold": (
        "float",
        ("EVENT_ALPHA_DECISION_MODEL_V2_RAPID_ANOMALY_URGENCY_THRESHOLD",),
    ),
    "dashboard_watch_route_enabled": (
        "bool", ("EVENT_ALPHA_DECISION_MODEL_V2_ROUTE_DASHBOARD_WATCH_ENABLED",),
    ),
    "actionable_watch_route_enabled": (
        "bool", ("EVENT_ALPHA_DECISION_MODEL_V2_ROUTE_ACTIONABLE_WATCH_ENABLED",),
    ),
    "high_confidence_route_enabled": (
        "bool", ("EVENT_ALPHA_DECISION_MODEL_V2_ROUTE_HIGH_CONFIDENCE_WATCH_ENABLED",),
    ),
    "rapid_anomaly_route_enabled": (
        "bool", ("EVENT_ALPHA_DECISION_MODEL_V2_ROUTE_RAPID_MARKET_ANOMALY_ENABLED",),
    ),
    "fade_exhaustion_route_enabled": (
        "bool", ("EVENT_ALPHA_DECISION_MODEL_V2_ROUTE_FADE_EXHAUSTION_REVIEW_ENABLED",),
    ),
    "calendar_risk_route_enabled": (
        "bool", ("EVENT_ALPHA_DECISION_MODEL_V2_ROUTE_CALENDAR_RISK_ENABLED",),
    ),
    "risk_watch_route_enabled": (
        "bool", ("EVENT_ALPHA_DECISION_MODEL_V2_ROUTE_RISK_WATCH_ENABLED",),
    ),
    "minimum_liquidity_usd": (
        "float",
        ("EVENT_ALPHA_DECISION_MODEL_V2_MIN_LIQUIDITY_USD", "EVENT_ALPHA_RADAR_MIN_LIQUIDITY_USD"),
    ),
    "good_liquidity_usd": (
        "float",
        ("EVENT_ALPHA_DECISION_MODEL_V2_GOOD_LIQUIDITY_USD", "EVENT_ALPHA_RADAR_GOOD_LIQUIDITY_USD"),
    ),
    "maximum_spread_bps": (
        "float",
        ("EVENT_ALPHA_DECISION_MODEL_V2_MAX_SPREAD_BPS", "EVENT_ALPHA_RADAR_MAX_SPREAD_BPS"),
    ),
    "good_spread_bps": (
        "float",
        ("EVENT_ALPHA_DECISION_MODEL_V2_GOOD_SPREAD_BPS", "EVENT_ALPHA_RADAR_GOOD_SPREAD_BPS"),
    ),
    "minimum_volume_zscore": (
        "float",
        ("EVENT_ALPHA_DECISION_MODEL_V2_MIN_VOLUME_ZSCORE", "EVENT_ALPHA_RADAR_MIN_VOLUME_ZSCORE"),
    ),
    "minimum_volume_to_market_cap": (
        "float",
        ("EVENT_ALPHA_DECISION_MODEL_V2_MIN_VOLUME_TO_MARKET_CAP", "EVENT_ALPHA_RADAR_MIN_VOLUME_TO_MARKET_CAP"),
    ),
}


@dataclass(frozen=True)
class RadarDecisionConfig:
    """Configurable research thresholds with safe runtime defaults."""

    enabled: bool = True
    market_led_enabled: bool = True
    catalyst_led_enabled: bool = True
    dashboard_watch_threshold: float = 45.0
    actionability_threshold: float = 65.0
    high_confidence_threshold: float = 80.0
    high_confidence_evidence_threshold: float = 75.0
    rapid_anomaly_actionability_threshold: float = 68.0
    rapid_anomaly_urgency_threshold: float = 72.0
    dashboard_watch_route_enabled: bool = True
    actionable_watch_route_enabled: bool = True
    high_confidence_route_enabled: bool = True
    rapid_anomaly_route_enabled: bool = True
    fade_exhaustion_route_enabled: bool = True
    calendar_risk_route_enabled: bool = True
    risk_watch_route_enabled: bool = True
    minimum_liquidity_usd: float = 250_000.0
    good_liquidity_usd: float = 5_000_000.0
    maximum_spread_bps: float = 150.0
    good_spread_bps: float = 50.0
    minimum_volume_zscore: float = 1.0
    minimum_volume_to_market_cap: float = 0.05

    @classmethod
    def from_runtime(cls, runtime_config: object | None) -> "RadarDecisionConfig":
        source = runtime_config or object()
        values: dict[str, Any] = {}
        for field_name, (kind, names) in _RUNTIME_FIELDS.items():
            default = getattr(cls, field_name)
            value = next((getattr(source, name) for name in names if hasattr(source, name)), default)
            values[field_name] = _runtime_bool(value, default) if kind == "bool" else _runtime_float(value, default)
        return cls(**values)


@dataclass(frozen=True)
class RadarDecision:
    decision_model_version: str
    decision_model_enabled: bool
    thesis_origin: str
    directional_bias: str
    catalyst_status: str
    confidence_band: str
    timing_state: str
    tradability_status: str
    radar_route: str
    radar_route_reason: str
    radar_actionable: bool
    actionability_score: float
    evidence_confidence_score: float
    risk_score: float
    actionability_score_components: Mapping[str, float]
    evidence_confidence_components: Mapping[str, float]
    risk_score_components: Mapping[str, float]
    actionability_penalty_components: Mapping[str, float]
    decision_hard_blockers: tuple[str, ...]
    decision_soft_penalties: tuple[str, ...]
    decision_missing_data: tuple[str, ...]
    decision_warnings: tuple[str, ...]
    why_still_worth_reviewing: tuple[str, ...]
    radar_what_confirms: tuple[str, ...]
    radar_what_invalidates: tuple[str, ...]
    actionability_score_cohort: str
    primary_thesis_origin: str = ThesisOrigin.MIXED.value
    thesis_origins: tuple[str, ...] = (ThesisOrigin.MIXED.value,)
    spread_status: str = SpreadStatus.UNAVAILABLE.value
    urgency_score: float = 0.0
    market_phase: str = MarketPhase.ACTIVE.value
    preferred_horizon: str = PreferredHorizon.ONE_TO_THREE_DAYS.value
    expires_at: str | None = None
    chase_risk_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["evidence_confidence_score_components"] = out.pop("evidence_confidence_components")
        for key in (
            "thesis_origins",
            "decision_hard_blockers", "decision_soft_penalties", "decision_missing_data",
            "decision_warnings", "why_still_worth_reviewing", "radar_what_confirms",
            "radar_what_invalidates",
        ):
            out[key] = list(out[key])
        return out


def _runtime_bool(value: object, default: object) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value if value is not None else default).strip().casefold()
    return text in {"1", "true", "yes", "on"}


def _runtime_float(value: object, default: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return float(default)  # type: ignore[arg-type]


def _bounded_score(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        score = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not math.isfinite(score) or not 0.0 <= score <= 100.0:
        return None
    return score


def actionability_score_cohort(value: object) -> str | None:
    """Return the canonical actionability cohort for one bounded v2 score."""

    score = _bounded_score(value)
    if score is None:
        return None
    if score >= 85:
        return "85_100"
    if score >= 70:
        return "70_84"
    if score >= 50:
        return "50_69"
    if score >= 25:
        return "25_49"
    return "0_24"


def evidence_confidence_score_cohort(value: object) -> str | None:
    """Return the canonical evidence-confidence cohort for one v2 score."""

    return _evidence_or_risk_score_cohort(value)


def risk_score_cohort(value: object) -> str | None:
    """Return the canonical risk cohort for one v2 score."""

    return _evidence_or_risk_score_cohort(value)


def decision_score_cohort_values(
    values: Mapping[str, object],
) -> dict[str, str] | None:
    """Project all canonical score cohorts, or fail closed as one unit."""

    projected = {
        "actionability_score_cohort": actionability_score_cohort(
            values.get("actionability_score")
        ),
        "evidence_confidence_score_cohort": evidence_confidence_score_cohort(
            values.get("evidence_confidence_score")
        ),
        "risk_score_cohort": risk_score_cohort(values.get("risk_score")),
    }
    if any(value is None for value in projected.values()):
        return None
    return {key: str(value) for key, value in projected.items()}


def _evidence_or_risk_score_cohort(value: object) -> str | None:
    score = _bounded_score(value)
    if score is None:
        return None
    if score >= 80:
        return "80_100"
    if score >= 65:
        return "65_79"
    if score >= 45:
        return "45_64"
    if score >= 25:
        return "25_44"
    return "0_24"


__all__ = (
    "DECISION_MODEL_VERSION", "CatalystStatus", "ConfidenceBand", "DirectionalBias",
    "MarketPhase", "PreferredHorizon", "RadarDecision", "RadarDecisionConfig",
    "RadarResearchRoute", "SpreadStatus", "ThesisOrigin", "TimingState",
    "TradabilityStatus", "actionability_score_cohort",
    "decision_score_cohort_values", "evidence_confidence_score_cohort",
    "risk_score_cohort",
)
