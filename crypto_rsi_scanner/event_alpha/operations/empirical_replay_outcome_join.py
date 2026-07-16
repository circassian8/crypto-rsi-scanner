"""Bounded path-outcome joins for empirical controls and benchmarks.

The controls layer freezes its point-in-time selections before calling these
helpers.  Outcomes are evaluated in symbol-sized batches with only the selected
asset and the protocol BTC/ETH benchmark frames, preserving the outcome
producer's partition firewall while avoiding repeated scans of unrelated
assets.  This module is pure and performs no I/O or production mutation.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Mapping, Sequence

import pandas as pd

from . import empirical_replay_benchmark_metrics, empirical_replay_outcomes


_DIRECTION_VALUES = {"long", "fade_short_review", "risk", "neutral"}


def outcomes_by_idea_id(
    ideas: Sequence[Mapping[str, Any]],
    *,
    price_frames: Mapping[str, pd.DataFrame],
    evaluated_at: datetime,
) -> dict[str, dict[str, Any]]:
    """Join compact path outcomes in deterministic symbol-sized batches."""

    if not ideas:
        return {}
    by_symbol: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for idea in ideas:
        by_symbol[str(idea.get("symbol") or "").strip().upper()].append(idea)
    frame_entries = [
        (raw_symbol, raw_frame, str(raw_symbol or "").strip().upper())
        for raw_symbol, raw_frame in price_frames.items()
    ]
    output: dict[str, dict[str, Any]] = {}
    for symbol in sorted(by_symbol):
        symbol_frames = _outcome_frames_for_symbol(
            frame_entries,
            symbol=symbol,
        )
        outcome_rows = empirical_replay_outcomes.iter_empirical_path_outcomes(
            by_symbol[symbol],
            symbol_frames,
            evaluated_at=evaluated_at,
        )
        for outcome in outcome_rows:
            idea_id = str(outcome.get("idea_id") or "")
            if not idea_id or idea_id in output:
                raise ValueError("duplicate_or_missing_outcome_idea_id")
            output[idea_id] = (
                empirical_replay_benchmark_metrics.compact_joined_path_outcome(
                    outcome
                )
            )
    return output


def _outcome_frames_for_symbol(
    frame_entries: Sequence[tuple[Any, Any, str]],
    *,
    symbol: str,
) -> dict[Any, Any]:
    """Keep one asset plus the two protocol benchmarks for path scoring.

    The outcome producer previously received every replay frame for every idea.
    Its partition firewall correctly clips every supplied frame before reading
    an outcome, so supplying hundreds of unrelated assets made each outcome
    O(universe size).  Path values depend only on the selected asset, BTC, and
    ETH; retain all case-normalized aliases for those names so invalid/duplicate
    frame behavior remains identical while the firewall work stays bounded.
    """

    required = {symbol, "BTC", "BTCUSDT", "ETH", "ETHUSDT"}
    return {
        raw_symbol: raw_frame
        for raw_symbol, raw_frame, normalized in frame_entries
        if normalized in required
    }


def outcome_idea(
    *,
    idea_id: str,
    observation: Mapping[str, Any],
    direction: str,
    family: str,
) -> dict[str, Any]:
    """Build the closed synthetic idea projection consumed by path scoring."""

    return {
        "idea_id": idea_id,
        "canonical_asset_id": observation["canonical_asset_id"],
        "symbol": observation["symbol"],
        "observed_at": observation["observed_at"],
        "directional_bias": direction if direction in _DIRECTION_VALUES else "neutral",
        "anomaly_family": family,
        "radar_route": "diagnostic",
        "partition": observation.get("partition"),
        "market_regime": observation.get("market_regime"),
        "liquidity_tier": observation.get("liquidity_tier"),
        "liquidity_usd": observation.get("liquidity_usd"),
        "trailing_quote_volume_usd": observation.get(
            "trailing_quote_volume_usd"
        ),
        "data_quality_mode": observation.get("data_quality_mode"),
        "point_in_time_universe_member": observation.get(
            "point_in_time_universe_member"
        ),
        "baseline_status": observation.get("baseline_status"),
        "operator_visible_idea": False,
        "decision_projection": {
            "radar_route": "diagnostic",
            "directional_bias": direction,
            "research_only": True,
        },
    }


__all__ = ["outcome_idea", "outcomes_by_idea_id"]
