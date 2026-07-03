"""Market state and anomaly schema exports."""

from __future__ import annotations

from .legacy import SCHEMAS

MARKET_STATE_SNAPSHOT_SCHEMA = SCHEMAS["market_state_snapshot_v1"]
MARKET_ANOMALY_SCHEMA = SCHEMAS["market_anomaly_v1"]
SCHEMA_IDS = ("market_state_snapshot_v1", "market_anomaly_v1")
SCHEMA_MAP = {schema_id: SCHEMAS[schema_id] for schema_id in SCHEMA_IDS}

__all__ = ("MARKET_ANOMALY_SCHEMA", "MARKET_STATE_SNAPSHOT_SCHEMA", "SCHEMA_IDS", "SCHEMA_MAP")
