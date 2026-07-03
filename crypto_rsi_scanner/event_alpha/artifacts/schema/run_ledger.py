"""Run ledger schema exports."""

from __future__ import annotations

from .legacy import SCHEMAS

RUN_LEDGER_SCHEMA = SCHEMAS["run_ledger_v1"]
SCHEMA_IDS = ("run_ledger_v1",)
SCHEMA_MAP = {schema_id: SCHEMAS[schema_id] for schema_id in SCHEMA_IDS}

__all__ = ("RUN_LEDGER_SCHEMA", "SCHEMA_IDS", "SCHEMA_MAP")
