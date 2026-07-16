"""Error contract for bounded empirical replay inputs."""

from __future__ import annotations


class ReplayDataError(ValueError):
    """Raised when an offline replay input fails a bounded safety contract."""


__all__ = ("ReplayDataError",)
