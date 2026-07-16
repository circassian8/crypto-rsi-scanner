"""Symbol-series value object for empirical replay inputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .empirical_replay_data_bar import ReplayBar
from .empirical_replay_data_error import ReplayDataError


@dataclass(frozen=True)
class ReplaySeries:
    """One selected symbol file plus its immutable content identity."""

    symbol: str
    canonical_asset_id: str
    relative_path: str
    declared_days: int | None
    byte_size: int
    content_sha256: str
    quote_volume_basis: str
    bars: tuple[ReplayBar, ...]

    def __post_init__(self) -> None:
        if (
            len(self.content_sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.content_sha256)
        ):
            raise ReplayDataError("source_content_sha256_invalid")
        if not self.bars:
            raise ReplayDataError("source_rows_empty")

    def frame_rows(self) -> tuple[dict[str, Any], ...]:
        """Return completed OHLCV rows without any future-derived values."""

        return tuple(bar.to_dict() for bar in self.bars)


__all__ = ("ReplaySeries",)
