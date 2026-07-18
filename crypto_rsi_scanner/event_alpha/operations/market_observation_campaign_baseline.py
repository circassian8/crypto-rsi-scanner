"""Current-versus-retained baseline projection for campaign reports."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence

from ... import config as project_config
from ..radar import market_history
from . import market_no_send_history_cache, market_observation_campaign_cadence


def build_baseline_maturity(
    base: Path,
    *,
    evaluated: datetime,
    history_filename: str,
    current_asset_ids: object = None,
) -> dict[str, Any]:
    """Build retained and exact-current readiness from one shared cache read."""

    try:
        history_config = market_history.MarketHistoryConfig(
            minimum_observation_spacing=timedelta(
                minutes=int(
                    project_config.DECISION_RADAR_MIN_OBSERVATION_SPACING_MINUTES
                )
            )
        )
    except (TypeError, ValueError):
        history_config = market_history.MarketHistoryConfig()
    try:
        result = market_no_send_history_cache.cache_readiness(
            base,
            history_filename=history_filename,
            now=evaluated,
            config=history_config,
            current_asset_ids=_asset_ids(current_asset_ids),
        )
    except TypeError:  # historical adapter during rolling upgrades
        result = market_no_send_history_cache.cache_readiness(
            base,
            history_filename=history_filename,
        )
    output = dict(result)
    output.setdefault("baseline_feature_readiness", {})
    output.setdefault(
        "current_universe_maturity",
        unavailable_current_universe_maturity(),
    )
    output.setdefault(
        "baseline_counted_observation_count",
        output.get("baseline_observation_count", 0),
    )
    output.setdefault("baseline_too_close_observation_count", 0)
    rejection_counts = _mapping(output.get("baseline_rejection_counts"))
    output.setdefault(
        "baseline_duplicate_observation_count",
        _int(rejection_counts.get("duplicate")),
    )
    output.setdefault(
        "baseline_duplicate_conflict_count",
        _int(rejection_counts.get("duplicate_conflict")),
    )
    output.setdefault(
        "minimum_observation_spacing_seconds",
        int(
            market_history.MarketHistoryConfig()
            .minimum_observation_spacing.total_seconds()
        ),
    )
    next_eligible = market_observation_campaign_cadence.legacy_next_eligible(output)
    output.setdefault("next_eligible_observation_at", next_eligible)
    return output


def unavailable_current_universe_maturity() -> dict[str, Any]:
    """Return the closed no-authority current-universe projection."""

    return {
        "status": "unavailable",
        "scope": "current_authoritative_universe",
        "expected_asset_count": 0,
        "observed_asset_count": 0,
        "missing_asset_count": 0,
        "missing_asset_ids": [],
        "baseline_observation_count": 0,
        "baseline_counted_observation_count": 0,
        "baseline_warm_asset_count": 0,
        "baseline_feature_readiness": {},
        "research_only": True,
    }


def _asset_ids(value: object) -> Sequence[str] | None:
    if not isinstance(value, (list, tuple)):
        return None
    return tuple(str(item) for item in value)


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


__all__ = (
    "build_baseline_maturity",
    "unavailable_current_universe_maturity",
)
