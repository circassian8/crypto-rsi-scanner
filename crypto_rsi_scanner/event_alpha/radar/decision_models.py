"""Public value models for Crypto Radar Decision Model v2."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Mapping


DECISION_MODEL_VERSION = "crypto_radar_decision_model_v2"


class ThesisOrigin(str, Enum):
    MARKET_LED = "market_led"
    CATALYST_LED = "catalyst_led"
    TECHNICAL_LED = "technical_led"
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


class RadarResearchRoute(str, Enum):
    ACTIONABLE_WATCH = "actionable_watch"
    HIGH_CONFIDENCE_WATCH = "high_confidence_watch"
    RAPID_MARKET_ANOMALY = "rapid_market_anomaly"
    FADE_EXHAUSTION_REVIEW = "fade_exhaustion_review"
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
    "high_confidence_threshold": (
        "float",
        ("EVENT_ALPHA_DECISION_MODEL_V2_HIGH_CONFIDENCE_THRESHOLD", "EVENT_ALPHA_RADAR_HIGH_CONFIDENCE_THRESHOLD"),
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
    actionability_threshold: float = 70.0
    high_confidence_threshold: float = 85.0
    actionable_watch_route_enabled: bool = True
    high_confidence_route_enabled: bool = True
    rapid_anomaly_route_enabled: bool = True
    fade_exhaustion_route_enabled: bool = True
    calendar_risk_route_enabled: bool = True
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

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["evidence_confidence_score_components"] = out.pop("evidence_confidence_components")
        for key in (
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


def actionability_score_cohort(value: object) -> str | None:
    try:
        score = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
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


__all__ = (
    "DECISION_MODEL_VERSION", "CatalystStatus", "ConfidenceBand", "DirectionalBias",
    "RadarDecision", "RadarDecisionConfig", "RadarResearchRoute", "ThesisOrigin",
    "TimingState", "TradabilityStatus", "actionability_score_cohort",
)
