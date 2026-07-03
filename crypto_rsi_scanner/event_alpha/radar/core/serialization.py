"""Core opportunity row serialization helpers."""

from __future__ import annotations

from typing import Any, Mapping

from . import legacy_store as _legacy

IDENTITY_FIELDS = {"core_opportunity_id", "symbol", "coin_id", "canonical_asset_id", "opportunity_type"}
SOURCE_FIELDS = {"source_url", "source_title", "source_origin", "source_pack", "provider", "source_strength"}
MARKET_FIELDS = {"market_state_class", "market_state_snapshot", "market_freshness_status"}
EVIDENCE_FIELDS = {"evidence", "accepted_evidence", "rejected_evidence", "evidence_count"}
NOTIFICATION_FIELDS = {"final_level", "final_route", "alertable", "feedback_target"}
OUTCOME_FIELDS = {"outcome_status", "validation_rate", "return_by_horizon"}
PATH_FIELDS = {"card_path", "research_card_path", "artifact_path", "notification_preview_path"}
SAFETY_FIELDS = {"research_only", "no_send_rehearsal", "trades_created", "paper_trades_created"}


def row_from_core_opportunity(core: Any) -> dict[str, Any]:
    return _legacy._row_from_core_opportunity(core)


def _select(row: Mapping[str, Any], fields: set[str]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key in fields}


def serialize_identity_fields(core: Any) -> dict[str, Any]:
    return _select(row_from_core_opportunity(core), IDENTITY_FIELDS)


def serialize_source_fields(core: Any) -> dict[str, Any]:
    return _select(row_from_core_opportunity(core), SOURCE_FIELDS)


def serialize_market_fields(core: Any) -> dict[str, Any]:
    return _select(row_from_core_opportunity(core), MARKET_FIELDS)


def serialize_evidence_fields(core: Any) -> dict[str, Any]:
    return _select(row_from_core_opportunity(core), EVIDENCE_FIELDS)


def serialize_notification_fields(core: Any) -> dict[str, Any]:
    return _select(row_from_core_opportunity(core), NOTIFICATION_FIELDS)


def serialize_outcome_fields(core: Any) -> dict[str, Any]:
    return _select(row_from_core_opportunity(core), OUTCOME_FIELDS)


def serialize_path_fields(core: Any) -> dict[str, Any]:
    return _select(row_from_core_opportunity(core), PATH_FIELDS)


def serialize_safety_fields(core: Any) -> dict[str, Any]:
    return _select(row_from_core_opportunity(core), SAFETY_FIELDS)


__all__ = (
    "row_from_core_opportunity",
    "serialize_identity_fields",
    "serialize_source_fields",
    "serialize_market_fields",
    "serialize_evidence_fields",
    "serialize_notification_fields",
    "serialize_outcome_fields",
    "serialize_path_fields",
    "serialize_safety_fields",
)
