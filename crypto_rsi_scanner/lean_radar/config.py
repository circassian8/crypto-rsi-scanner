"""Small, explicit configuration surface for Lean Crypto Radar."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "lean_radar.db"
TOP_LIQUID_LIMIT = 200
DEFAULT_CADENCE_MINUTES = 20
MIN_CADENCE_MINUTES = 15
MAX_CADENCE_MINUTES = 30


class _LeanRadarConfigError(ValueError):
    """Raised when operator configuration is outside the lean contract."""


LeanRadarConfigError = _LeanRadarConfigError


@dataclass(frozen=True)
class LeanRadarSettings:
    db_path: Path
    cadence_minutes: int
    top_liquid_limit: int = TOP_LIQUID_LIMIT
    venue: str = "bybit"
    instrument_type: str = "usdt_perpetual"
    no_send: bool = True
    research_only: bool = True


def load_settings(env: Mapping[str, str] | None = None) -> LeanRadarSettings:
    values = os.environ if env is None else env
    raw_path = values.get("RSI_LEAN_RADAR_DB_PATH", str(DEFAULT_DB_PATH)).strip()
    if not raw_path:
        raise LeanRadarConfigError("lean radar database path is empty")
    db_path = Path(raw_path).expanduser()
    if not db_path.is_absolute():
        db_path = PROJECT_ROOT / db_path

    raw_cadence = values.get(
        "RSI_LEAN_RADAR_CADENCE_MINUTES", str(DEFAULT_CADENCE_MINUTES)
    ).strip()
    try:
        cadence = int(raw_cadence)
    except ValueError as exc:
        raise LeanRadarConfigError("lean radar cadence must be an integer") from exc
    if not MIN_CADENCE_MINUTES <= cadence <= MAX_CADENCE_MINUTES:
        raise LeanRadarConfigError(
            "lean radar cadence must be between 15 and 30 minutes"
        )
    return LeanRadarSettings(db_path=db_path, cadence_minutes=cadence)


__all__ = (
    "DEFAULT_CADENCE_MINUTES",
    "DEFAULT_DB_PATH",
    "MAX_CADENCE_MINUTES",
    "MIN_CADENCE_MINUTES",
    "PROJECT_ROOT",
    "TOP_LIQUID_LIMIT",
    "LeanRadarConfigError",
    "LeanRadarSettings",
    "load_settings",
)
