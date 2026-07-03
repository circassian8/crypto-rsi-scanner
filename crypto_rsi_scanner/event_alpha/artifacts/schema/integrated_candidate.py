"""Integrated radar candidate schema exports."""

from __future__ import annotations

from .legacy import SCHEMAS

INTEGRATED_RADAR_CANDIDATE_SCHEMA = SCHEMAS["integrated_radar_candidate_v1"]
SCHEMA_IDS = ("integrated_radar_candidate_v1",)
SCHEMA_MAP = {schema_id: SCHEMAS[schema_id] for schema_id in SCHEMA_IDS}

__all__ = ("INTEGRATED_RADAR_CANDIDATE_SCHEMA", "SCHEMA_IDS", "SCHEMA_MAP")
