"""Source coverage schema exports."""

from __future__ import annotations

from .registry import SCHEMAS

SOURCE_COVERAGE_SCHEMA = SCHEMAS["source_coverage_v1"]
SCHEMA_IDS = ("source_coverage_v1",)
SCHEMA_MAP = {schema_id: SCHEMAS[schema_id] for schema_id in SCHEMA_IDS}

__all__ = ("SOURCE_COVERAGE_SCHEMA", "SCHEMA_IDS", "SCHEMA_MAP")
