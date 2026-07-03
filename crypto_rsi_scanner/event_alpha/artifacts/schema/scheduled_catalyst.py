"""Scheduled catalyst and unlock schema exports."""

from __future__ import annotations

from .legacy import SCHEMAS

SCHEDULED_CATALYST_EVENT_SCHEMA = SCHEMAS["scheduled_catalyst_event_v1"]
UNLOCK_EVENT_SCHEMA = SCHEMAS["unlock_event_v1"]
SCHEMA_IDS = ("scheduled_catalyst_event_v1", "unlock_event_v1")
SCHEMA_MAP = {schema_id: SCHEMAS[schema_id] for schema_id in SCHEMA_IDS}

__all__ = ("SCHEDULED_CATALYST_EVENT_SCHEMA", "SCHEMA_IDS", "SCHEMA_MAP", "UNLOCK_EVENT_SCHEMA")
