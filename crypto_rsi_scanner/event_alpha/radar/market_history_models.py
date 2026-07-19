"""Data contracts for deterministic market-history enrichment."""

from __future__ import annotations

import copy
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping


MARKET_HISTORY_OBSERVATION_SCHEMA = "event_alpha.market_history_observation"
MARKET_HISTORY_ENRICHMENT_SCHEMA = "event_alpha.market_history_enrichment"
MARKET_HISTORY_SUMMARY_SCHEMA = "event_alpha.market_history_summary"
MARKET_HISTORY_SCHEMA_VERSION = 1
TEMPORAL_BASELINE_BASIS = "temporal_baseline"
RETURN_UNIT_PERCENT_POINTS = "percent_points"
BASELINE_COUNTED = "counted"
BASELINE_TOO_CLOSE = "too_close"
BASELINE_DUPLICATE = "duplicate"
FEATURE_READINESS_GROUPS = (
    "volume",
    "turnover",
    "volatility",
    "returns_1h",
    "returns_4h",
    "returns_24h",
    "btc_eth_relative",
)


@dataclass(frozen=True)
class MarketHistoryConfig:
    """Deterministic retention and warm-up policy for market observations."""

    max_history_age: timedelta = timedelta(days=45)
    max_current_age: timedelta = timedelta(hours=6)
    future_tolerance: timedelta = timedelta(minutes=5)
    max_observations_per_asset: int = 256
    min_baseline_observations: int = 8
    minimum_observation_spacing: timedelta = timedelta(hours=1)
    return_horizons_hours: tuple[int, ...] = (1, 4, 24)
    required_feature_groups: tuple[str, ...] = FEATURE_READINESS_GROUPS
    anchor_tolerance_ratio: float = 0.25
    min_anchor_tolerance: timedelta = timedelta(minutes=5)
    benchmark_alignment_tolerance: timedelta = timedelta(minutes=5)
    btc_asset_ids: tuple[str, ...] = ("bitcoin", "btc")
    eth_asset_ids: tuple[str, ...] = ("ethereum", "eth")
    rejection_example_limit: int = 25

    def __post_init__(self) -> None:
        checks = (
            (self.max_history_age > timedelta(0), "max_history_age must be positive"),
            (self.max_current_age > timedelta(0), "max_current_age must be positive"),
            (self.future_tolerance >= timedelta(0), "future_tolerance cannot be negative"),
            (
                self.max_observations_per_asset >= 2,
                "max_observations_per_asset must be at least 2",
            ),
            (
                self.min_baseline_observations >= 2,
                "min_baseline_observations must be at least 2",
            ),
            (
                self.minimum_observation_spacing > timedelta(0),
                "minimum_observation_spacing must be positive",
            ),
            (
                self.return_horizons_hours
                and all(value > 0 for value in self.return_horizons_hours),
                "return_horizons_hours must contain positive values",
            ),
            (
                len(set(self.return_horizons_hours)) == len(self.return_horizons_hours),
                "return_horizons_hours must be unique",
            ),
            (self.anchor_tolerance_ratio >= 0, "anchor_tolerance_ratio cannot be negative"),
            (
                self.min_anchor_tolerance >= timedelta(0),
                "min_anchor_tolerance cannot be negative",
            ),
            (
                self.benchmark_alignment_tolerance >= timedelta(0),
                "benchmark_alignment_tolerance cannot be negative",
            ),
            (self.rejection_example_limit >= 0, "rejection_example_limit cannot be negative"),
            (bool(self.required_feature_groups), "required_feature_groups cannot be empty"),
            (
                len(set(self.required_feature_groups)) == len(self.required_feature_groups),
                "required_feature_groups must be unique",
            ),
            (
                set(self.required_feature_groups).issubset(FEATURE_READINESS_GROUPS),
                "required_feature_groups contains an unknown group",
            ),
        )
        for valid, message in checks:
            if not valid:
                raise ValueError(message)
        if self.max_observations_per_asset <= self.min_baseline_observations:
            raise ValueError(
                "max_observations_per_asset must leave room after min_baseline_observations"
            )


@dataclass(frozen=True)
class _MarketHistoryResult:
    enriched_rows: tuple[dict[str, Any], ...]
    retained_history: tuple[dict[str, Any], ...]
    summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "enriched_rows": copy.deepcopy(list(self.enriched_rows)),
            "retained_history": copy.deepcopy(list(self.retained_history)),
            "summary": copy.deepcopy(self.summary),
        }


@dataclass(frozen=True)
class _PreparedObservation:
    index: int
    observation: dict[str, Any]
    asset_id: str
    observed_at: datetime

    @property
    def key(self) -> tuple[str, datetime]:
        return self.asset_id, self.observed_at


@dataclass(frozen=True)
class _ReturnSample:
    value: float
    endpoint: Mapping[str, Any]
    anchor: Mapping[str, Any]

    @property
    def evidence_rows(self) -> tuple[Mapping[str, Any], ...]:
        return self.endpoint, self.anchor


@dataclass(frozen=True)
class _RelativeReturnSample:
    value: float
    asset_endpoint: Mapping[str, Any]
    asset_anchor: Mapping[str, Any]
    benchmark_endpoint: Mapping[str, Any]
    benchmark_anchor: Mapping[str, Any]

    @property
    def evidence_rows(self) -> tuple[Mapping[str, Any], ...]:
        return (
            self.asset_endpoint,
            self.asset_anchor,
            self.benchmark_endpoint,
            self.benchmark_anchor,
        )


@dataclass
class _Telemetry:
    counts: Counter[str] = field(default_factory=Counter)
    role_counts: Counter[tuple[str, str]] = field(default_factory=Counter)
    examples: list[dict[str, Any]] = field(default_factory=list)
    example_limit: int = 25

    def record(
        self,
        reason: str,
        *,
        role: str,
        index: int,
        asset_id: str = "",
        observed_at: datetime | None = None,
    ) -> None:
        self.counts[reason] += 1
        self.role_counts[(role, reason)] += 1
        if len(self.examples) >= self.example_limit:
            return
        item: dict[str, Any] = {
            "reason": reason,
            "role": role,
            "input_index": index,
        }
        if asset_id:
            item["canonical_asset_id"] = asset_id
        if observed_at is not None:
            item["observed_at"] = observed_at.astimezone(timezone.utc).isoformat()
        self.examples.append(item)


def _config_values(cfg: MarketHistoryConfig) -> dict[str, Any]:
    return {
        "max_history_age_seconds": int(cfg.max_history_age.total_seconds()),
        "max_current_age_seconds": int(cfg.max_current_age.total_seconds()),
        "future_tolerance_seconds": int(cfg.future_tolerance.total_seconds()),
        "max_observations_per_asset": cfg.max_observations_per_asset,
        "min_baseline_observations": cfg.min_baseline_observations,
        "minimum_observation_spacing_seconds": int(
            cfg.minimum_observation_spacing.total_seconds()
        ),
        "return_horizons_hours": list(sorted(cfg.return_horizons_hours)),
        "required_feature_groups": list(cfg.required_feature_groups),
        "anchor_tolerance_ratio": cfg.anchor_tolerance_ratio,
        "min_anchor_tolerance_seconds": int(cfg.min_anchor_tolerance.total_seconds()),
        "benchmark_alignment_tolerance_seconds": int(
            cfg.benchmark_alignment_tolerance.total_seconds()
        ),
        "btc_asset_ids": list(cfg.btc_asset_ids),
        "eth_asset_ids": list(cfg.eth_asset_ids),
    }
