"""Calibration schema exports."""

from __future__ import annotations

from .registry import SCHEMAS

CALIBRATION_PRIOR_SCHEMA = SCHEMAS["calibration_prior_v1"]
SCHEMA_IDS = ("calibration_prior_v1",)
SCHEMA_MAP = {schema_id: SCHEMAS[schema_id] for schema_id in SCHEMA_IDS}

__all__ = ("CALIBRATION_PRIOR_SCHEMA", "SCHEMA_IDS", "SCHEMA_MAP")
