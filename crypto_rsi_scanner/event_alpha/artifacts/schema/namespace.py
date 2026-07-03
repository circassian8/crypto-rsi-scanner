"""Namespace lifecycle schema exports."""

from __future__ import annotations

from .legacy import SCHEMAS

NAMESPACE_STATUS_SCHEMA = SCHEMAS["namespace_status_v1"]
SCHEMA_IDS = ("namespace_status_v1",)
SCHEMA_MAP = {schema_id: SCHEMAS[schema_id] for schema_id in SCHEMA_IDS}

__all__ = ("NAMESPACE_STATUS_SCHEMA", "SCHEMA_IDS", "SCHEMA_MAP")
