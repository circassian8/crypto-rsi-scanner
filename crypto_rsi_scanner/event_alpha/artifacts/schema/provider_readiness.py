"""Provider readiness and preflight schema exports."""

from __future__ import annotations

from .legacy import SCHEMAS

PROVIDER_READINESS_SCHEMA = SCHEMAS["provider_readiness_v1"]
PROVIDER_PREFLIGHT_SCHEMA = SCHEMAS["provider_preflight_v1"]
SCHEMA_IDS = ("provider_readiness_v1", "provider_preflight_v1")
SCHEMA_MAP = {schema_id: SCHEMAS[schema_id] for schema_id in SCHEMA_IDS}

__all__ = (
    "PROVIDER_PREFLIGHT_SCHEMA",
    "PROVIDER_READINESS_SCHEMA",
    "SCHEMA_IDS",
    "SCHEMA_MAP",
)
