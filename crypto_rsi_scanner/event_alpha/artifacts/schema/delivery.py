"""Notification delivery schema exports."""

from __future__ import annotations

from .registry import SCHEMAS

NOTIFICATION_DELIVERY_SCHEMA = SCHEMAS["notification_delivery_v1"]
INTEGRATED_NOTIFICATION_DELIVERY_SCHEMA = SCHEMAS["integrated_notification_delivery_v1"]
SCHEMA_IDS = ("notification_delivery_v1", "integrated_notification_delivery_v1")
SCHEMA_MAP = {schema_id: SCHEMAS[schema_id] for schema_id in SCHEMA_IDS}

__all__ = (
    "INTEGRATED_NOTIFICATION_DELIVERY_SCHEMA",
    "NOTIFICATION_DELIVERY_SCHEMA",
    "SCHEMA_IDS",
    "SCHEMA_MAP",
)
