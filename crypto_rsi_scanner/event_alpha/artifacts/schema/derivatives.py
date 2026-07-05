"""Derivatives schema exports."""

from __future__ import annotations

from .registry import SCHEMAS

COINALYZE_REQUEST_LEDGER_SCHEMA = SCHEMAS["coinalyze_request_ledger_v1"]
DERIVATIVES_STATE_SNAPSHOT_SCHEMA = SCHEMAS["derivatives_state_snapshot_v1"]
DERIVATIVES_CROWDING_CANDIDATE_SCHEMA = SCHEMAS["derivatives_crowding_candidate_v1"]
FADE_REVIEW_CANDIDATE_SCHEMA = SCHEMAS["fade_review_candidate_v1"]
SCHEMA_IDS = (
    "coinalyze_request_ledger_v1",
    "derivatives_state_snapshot_v1",
    "derivatives_crowding_candidate_v1",
    "fade_review_candidate_v1",
)
SCHEMA_MAP = {schema_id: SCHEMAS[schema_id] for schema_id in SCHEMA_IDS}

__all__ = (
    "COINALYZE_REQUEST_LEDGER_SCHEMA",
    "DERIVATIVES_CROWDING_CANDIDATE_SCHEMA",
    "DERIVATIVES_STATE_SNAPSHOT_SCHEMA",
    "FADE_REVIEW_CANDIDATE_SCHEMA",
    "SCHEMA_IDS",
    "SCHEMA_MAP",
)
