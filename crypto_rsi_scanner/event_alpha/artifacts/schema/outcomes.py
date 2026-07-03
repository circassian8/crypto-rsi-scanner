"""Outcome schema exports."""

from __future__ import annotations

from .legacy import SCHEMAS

OUTCOME_ROW_SCHEMA = SCHEMAS["outcome_row_v1"]
SCHEMA_IDS = ("outcome_row_v1",)
SCHEMA_MAP = {schema_id: SCHEMAS[schema_id] for schema_id in SCHEMA_IDS}

__all__ = ("OUTCOME_ROW_SCHEMA", "SCHEMA_IDS", "SCHEMA_MAP")
