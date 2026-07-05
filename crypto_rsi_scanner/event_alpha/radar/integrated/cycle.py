"""Integrated radar cycle compatibility surface."""

from __future__ import annotations

from typing import Any

from . import api as _api


def run_integrated_radar_cycle(*args: Any, **kwargs: Any) -> Any:
    return _api.run_integrated_radar_cycle(*args, **kwargs)


__all__ = ("run_integrated_radar_cycle",)
