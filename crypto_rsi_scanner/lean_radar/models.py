"""Closed, operator-facing values for the lean product."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import math
from typing import Mapping


IDEA_TYPES = (
    "market_breakout_long",
    "relative_strength_long",
    "pullback_or_mean_reversion",
    "rapid_market_anomaly",
    "exhaustion_or_fade_review",
    "selloff_or_risk_warning",
    "calendar_risk",
    "dashboard_watch",
    "diagnostic",
)
ROUTES = (
    "urgent_review",
    "watchlist",
    "daily_digest",
    "dashboard_only",
    "risk_calendar",
    "diagnostic_hidden",
)
SOURCE_MODES = ("live_no_send", "imported_catalog", "fixture")


class _LeanRadarModelError(ValueError):
    """Raised when a lean value would misstate operator truth."""


LeanRadarModelError = _LeanRadarModelError


def _require_text(value: object, label: str, *, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise LeanRadarModelError(f"{label} is invalid")
    return value.strip()


def _require_timestamp(value: object, label: str) -> str:
    text = _require_text(value, label, maximum=64)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LeanRadarModelError(f"{label} is invalid") from exc
    if parsed.tzinfo is None:
        raise LeanRadarModelError(f"{label} must be timezone-aware")
    return text


def _require_score(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LeanRadarModelError(f"{label} is invalid")
    score = float(value)
    if not math.isfinite(score) or not 0 <= score <= 100:
        raise LeanRadarModelError(f"{label} must be between 0 and 100")
    return score


@dataclass(frozen=True)
class BybitInstrument:
    instrument_id: str
    base_coin: str
    quote_coin: str
    settle_coin: str
    contract_type: str
    status: str
    tick_size: str
    quantity_step: str
    minimum_quantity: str
    maximum_limit_quantity: str | None
    maximum_market_quantity: str | None
    minimum_notional_usdt: str | None
    source_observed_at: str
    source_mode: str
    source_sha256: str

    def __post_init__(self) -> None:
        for label in (
            "instrument_id",
            "base_coin",
            "quote_coin",
            "settle_coin",
            "contract_type",
            "status",
            "tick_size",
            "quantity_step",
            "minimum_quantity",
            "source_sha256",
        ):
            _require_text(getattr(self, label), label)
        _require_timestamp(self.source_observed_at, "source_observed_at")
        if self.source_mode not in SOURCE_MODES:
            raise LeanRadarModelError("source_mode is invalid")
        if self.quote_coin != "USDT" or self.settle_coin != "USDT":
            raise LeanRadarModelError("instrument is not USDT quoted and settled")
        if self.contract_type != "LinearPerpetual" or self.status != "Trading":
            raise LeanRadarModelError("instrument is not an active linear perpetual")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class UniverseAsset:
    canonical_asset_id: str
    symbol: str
    name: str
    liquidity_rank: int | None
    total_volume_usd_24h: float | None
    bybit_instrument: str | None
    origins: tuple[str, ...]
    status: str
    reason: str | None
    instrument_source_mode: str | None

    @property
    def active(self) -> bool:
        return self.status == "active"

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["origins"] = list(self.origins)
        payload["active"] = self.active
        return payload


@dataclass(frozen=True)
class LeanIdea:
    idea_id: str
    created_at: str
    expires_at: str
    symbol: str
    canonical_asset_id: str
    bybit_instrument: str
    horizon: str
    idea_type: str
    directional_bias: str
    actionability_score: float
    confidence_score: float
    risk_score: float
    urgency_score: float
    timing_state: str
    market_phase: str
    catalyst_status: str
    liquidity_status: str
    spread_status: str
    data_quality: str
    why_now: tuple[str, ...]
    supporting_facts: tuple[str, ...]
    risks: tuple[str, ...]
    missing_information: tuple[str, ...]
    what_confirms: tuple[str, ...]
    what_invalidates: tuple[str, ...]
    dashboard_route: str
    telegram_route: str
    source_context: Mapping[str, object] = field(default_factory=dict)
    calendar_context: Mapping[str, object] = field(default_factory=dict)
    technical_context: Mapping[str, object] = field(default_factory=dict)
    outcome_status: str = "pending"
    venue: str = "bybit"
    instrument_type: str = "usdt_perpetual"
    research_only: bool = True

    def __post_init__(self) -> None:
        for label in (
            "idea_id",
            "symbol",
            "canonical_asset_id",
            "bybit_instrument",
            "horizon",
            "directional_bias",
            "timing_state",
            "market_phase",
            "catalyst_status",
            "liquidity_status",
            "spread_status",
            "data_quality",
            "outcome_status",
        ):
            _require_text(getattr(self, label), label)
        _require_timestamp(self.created_at, "created_at")
        _require_timestamp(self.expires_at, "expires_at")
        if self.idea_type not in IDEA_TYPES:
            raise LeanRadarModelError("idea_type is invalid")
        if self.dashboard_route not in ROUTES or self.telegram_route not in ROUTES:
            raise LeanRadarModelError("idea route is invalid")
        for label in (
            "actionability_score",
            "confidence_score",
            "risk_score",
            "urgency_score",
        ):
            _require_score(getattr(self, label), label)
        if self.venue != "bybit" or self.instrument_type != "usdt_perpetual":
            raise LeanRadarModelError("idea venue or instrument type is invalid")
        if self.research_only is not True:
            raise LeanRadarModelError("lean ideas must remain research-only")
        if self.idea_type == "exhaustion_or_fade_review" and (
            self.directional_bias not in {"short_review", "neutral"}
        ):
            raise LeanRadarModelError("fade ideas must use review-only bias wording")

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        for key in (
            "why_now",
            "supporting_facts",
            "risks",
            "missing_information",
            "what_confirms",
            "what_invalidates",
        ):
            payload[key] = list(payload[key])
        payload["source_context"] = dict(self.source_context)
        payload["calendar_context"] = dict(self.calendar_context)
        payload["technical_context"] = dict(self.technical_context)
        return payload


__all__ = (
    "IDEA_TYPES",
    "ROUTES",
    "SOURCE_MODES",
    "BybitInstrument",
    "LeanIdea",
    "LeanRadarModelError",
    "UniverseAsset",
)
