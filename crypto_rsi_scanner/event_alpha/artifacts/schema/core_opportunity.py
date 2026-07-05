"""Core opportunity schema exports."""

from __future__ import annotations

from .registry import SCHEMAS

CORE_OPPORTUNITY_SCHEMA = SCHEMAS["core_opportunity_v1"]
SCHEMA_IDS = ("core_opportunity_v1",)
SCHEMA_MAP = {schema_id: SCHEMAS[schema_id] for schema_id in SCHEMA_IDS}

__all__ = ("CORE_OPPORTUNITY_SCHEMA", "SCHEMA_IDS", "SCHEMA_MAP")
