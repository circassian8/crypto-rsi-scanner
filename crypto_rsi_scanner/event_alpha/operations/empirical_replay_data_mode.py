"""Frozen resource configuration for empirical replay input modes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReplayDataModeConfig:
    """Frozen resource and feature limits for one replay input mode."""

    name: str
    max_symbols: int
    universe_top_n: int
    max_rows_per_symbol: int = 4_096
    max_file_bytes: int = 16 * 1024 * 1024
    membership_window_days: int = 30
    volume_z_window: int = 90
    volume_z_min_observations: int = 20
    final_test_evaluation_enabled: bool = False


__all__ = ("ReplayDataModeConfig",)
