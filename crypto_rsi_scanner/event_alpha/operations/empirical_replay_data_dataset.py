"""Closed offline dataset value object for empirical replay inputs."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import pandas as pd

from .empirical_replay_data_error import ReplayDataError
from .empirical_replay_data_mode import ReplayDataModeConfig
from .empirical_replay_data_series import ReplaySeries


@dataclass(frozen=True)
class ReplayDataset:
    """Closed offline dataset selected under one bounded replay mode."""

    mode: ReplayDataModeConfig
    source_kind: str
    candidate_files_discovered: int
    candidate_symbols_discovered: int
    series: tuple[ReplaySeries, ...]
    residual_survivorship_present: bool
    residual_survivorship_disclosure: str

    def __post_init__(self) -> None:
        if not self.series:
            raise ReplayDataError("dataset_series_empty")
        if len(self.series) > self.mode.max_symbols:
            raise ReplayDataError("dataset_symbol_bound_exceeded")
        symbols = [item.symbol for item in self.series]
        if symbols != sorted(symbols) or len(symbols) != len(set(symbols)):
            raise ReplayDataError("dataset_symbol_order_or_identity_invalid")
        if self.mode.final_test_evaluation_enabled:
            raise ReplayDataError("final_test_evaluation_forbidden")

    def frames(self) -> dict[str, tuple[dict[str, Any], ...]]:
        """Return symbol-keyed daily rows for downstream outcome calculations."""

        return {item.symbol: item.frame_rows() for item in self.series}

    def price_frames(
        self,
        symbols: Iterable[str] | None = None,
    ) -> dict[str, pd.DataFrame]:
        """Materialize only requested outcome frames without row-dict copies."""

        selected = (
            None
            if symbols is None
            else {
                str(symbol).strip().upper()
                for symbol in symbols
                if str(symbol).strip()
            }
        )
        frames: dict[str, pd.DataFrame] = {}
        for item in self.series:
            if selected is not None and item.symbol not in selected:
                continue
            frames[item.symbol] = pd.DataFrame(
                {
                    "open": [bar.open for bar in item.bars],
                    "high": [bar.high for bar in item.bars],
                    "low": [bar.low for bar in item.bars],
                    "close": [bar.close for bar in item.bars],
                    "base_volume": [bar.base_volume for bar in item.bars],
                    "quote_volume": [bar.quote_volume for bar in item.bars],
                },
                index=pd.DatetimeIndex([bar.observed_at for bar in item.bars]),
            )
        return frames


__all__ = ("ReplayDataset",)
