"""Declarative Event Alpha artifact schema v1.

This module intentionally uses lightweight Python objects instead of a
jsonschema dependency. It is the field registry that future artifact writers
and doctor checks should reference before adding new validation behavior.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping


EVENT_ALPHA_ARTIFACT_SCHEMA_VERSION = "event_alpha_schema_v1"

ALLOWED_OPPORTUNITY_TYPES = (
    "EARLY_LONG_RESEARCH",
    "CONFIRMED_LONG_RESEARCH",
    "FADE_SHORT_REVIEW",
    "RISK_ONLY",
    "UNCONFIRMED_RESEARCH",
    "DIAGNOSTIC",
)
ALLOWED_FINAL_LEVELS = (
    "strict_alert",
    "high_priority",
    "watchlist",
    "radar",
    "local_only",
    "store_only",
    "diagnostic",
    "rejected",
    "unknown",
)
ALLOWED_DELIVERY_STATUSES = (
    "planned",
    "sending",
    "delivered",
    "partial_delivered",
    "failed",
    "blocked",
    "skipped_duplicate",
    "would_send_but_guard_disabled",
    "no_send_preview",
    "preview_only",
)
ALLOWED_NAMESPACE_STATUSES = (
    "active",
    "active_live_rehearsal",
    "active_fixture_smoke",
    "active_provider_preflight",
    "active_provider_rehearsal",
    "active_integrated_smoke",
    "stale_deprecated",
    "archived",
    "quarantine",
    "unknown",
)


@dataclass(frozen=True)
class ArtifactSchema:
    schema_id: str
    schema_version: str = EVENT_ALPHA_ARTIFACT_SCHEMA_VERSION
    required_fields: tuple[str, ...] = ()
    optional_fields: tuple[str, ...] = ()
    deprecated_fields: tuple[str, ...] = ()
    field_types: Mapping[str, str] = field(default_factory=dict)
    enum_fields: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    path_fields: tuple[str, ...] = ()
    debug_abs_path_fields: tuple[str, ...] = ()
    timestamp_fields: tuple[str, ...] = ()
    safety_fields: tuple[str, ...] = ()
    lineage_fields: tuple[str, ...] = ()
    artifact_relpath_fields: tuple[str, ...] = ()
    secret_redaction_fields: tuple[str, ...] = ()
    allowed_opportunity_types: tuple[str, ...] = ALLOWED_OPPORTUNITY_TYPES
    allowed_final_levels: tuple[str, ...] = ALLOWED_FINAL_LEVELS
    allowed_delivery_statuses: tuple[str, ...] = ALLOWED_DELIVERY_STATUSES
    allowed_namespace_statuses: tuple[str, ...] = ALLOWED_NAMESPACE_STATUSES

    @property
    def declared_fields(self) -> frozenset[str]:
        fields = set(self.required_fields)
        fields.update(self.optional_fields)
        fields.update(self.deprecated_fields)
        fields.update(self.field_types)
        fields.update(self.enum_fields)
        fields.update(self.path_fields)
        fields.update(self.debug_abs_path_fields)
        fields.update(self.timestamp_fields)
        fields.update(self.safety_fields)
        fields.update(self.lineage_fields)
        fields.update(self.artifact_relpath_fields)
        fields.update(self.secret_redaction_fields)
        fields.update(COMMON_PATHS)
        return frozenset(fields)


COMMON_LINEAGE = (
    "run_id",
    "profile",
    "run_mode",
    "artifact_namespace",
    "candidate_id",
    "core_opportunity_id",
)
COMMON_SAFETY = (
    "research_only",
    "no_send_rehearsal",
    "sent",
    "normal_rsi_signal_written",
    "triggered_fade_created",
    "trades_created",
    "paper_trades_created",
    "trade_created",
    "paper_trade_created",
)
COMMON_PATHS = (
    "path",
    "artifact_path",
    "request_ledger_path",
    "source_coverage_path",
    "daily_brief_path",
    "card_path",
    "research_card_path",
    "notification_preview_path",
    "marker_path",
)


def _schema(
    schema_id: str,
    *,
    required: Iterable[str],
    optional: Iterable[str] = (),
    deprecated: Iterable[str] = (),
    types: Mapping[str, str] | None = None,
    enums: Mapping[str, Iterable[str]] | None = None,
    safety: Iterable[str] = (),
    paths: Iterable[str] = (),
    timestamps: Iterable[str] = (),
    lineage: Iterable[str] = (),
) -> ArtifactSchema:
    enum_values = {key: tuple(value) for key, value in (enums or {}).items()}
    return ArtifactSchema(
        schema_id=schema_id,
        required_fields=tuple(required),
        optional_fields=tuple(optional),
        deprecated_fields=tuple(deprecated),
        field_types=dict(types or {}),
        enum_fields=enum_values,
        path_fields=tuple(dict.fromkeys((*paths,))),
        debug_abs_path_fields=tuple(field for field in (*paths, *COMMON_PATHS) if field.endswith("_abs_debug")),
        timestamp_fields=tuple(timestamps),
        safety_fields=tuple(safety),
        lineage_fields=tuple(dict.fromkeys((*lineage, *COMMON_LINEAGE))),
        artifact_relpath_fields=tuple(paths),
        secret_redaction_fields=("api_key", "token", "authorization", "auth_token", "x-api-key"),
    )


SCHEMAS: dict[str, ArtifactSchema] = {
    "core_opportunity_v1": _schema(
        "core_opportunity_v1",
        required=("row_type", "core_opportunity_id", "symbol", "opportunity_type"),
        optional=("coin_id", "source_pack", "source_origin", "market_state_class", "source_strength", "final_level", *COMMON_SAFETY),
        types={"row_type": "str", "core_opportunity_id": "str", "symbol": "str", "opportunity_type": "str"},
        enums={"opportunity_type": ALLOWED_OPPORTUNITY_TYPES, "final_level": ALLOWED_FINAL_LEVELS},
        safety=COMMON_SAFETY,
        paths=("card_path", "research_card_path"),
    ),
    "integrated_radar_candidate_v1": _schema(
        "integrated_radar_candidate_v1",
        required=("row_type", "candidate_id", "symbol", "opportunity_type"),
        optional=("coin_id", "core_opportunity_id", "provider", "source_pack", "source_origin", "market_state_class", "crowding_class", *COMMON_SAFETY),
        types={"row_type": "str", "candidate_id": "str", "symbol": "str", "opportunity_type": "str"},
        enums={"opportunity_type": ALLOWED_OPPORTUNITY_TYPES},
        safety=COMMON_SAFETY,
    ),
    "notification_delivery_v1": _schema(
        "notification_delivery_v1",
        required=("row_type", "delivery_id", "status"),
        optional=("delivery_status", "sent", "would_send", "no_send_rehearsal", "message_text", "lane", "card_paths", *COMMON_SAFETY),
        enums={"status": ALLOWED_DELIVERY_STATUSES, "delivery_status": ALLOWED_DELIVERY_STATUSES},
        safety=COMMON_SAFETY,
        paths=("card_path", "notification_preview_path"),
    ),
    "integrated_notification_delivery_v1": _schema(
        "integrated_notification_delivery_v1",
        required=("row_type", "lane", "sent", "no_send_rehearsal"),
        optional=("lane_title", "message_text", "card_paths", "skipped_items", *COMMON_SAFETY),
        safety=COMMON_SAFETY,
        paths=("card_path", "notification_preview_path"),
    ),
    "source_coverage_v1": _schema(
        "source_coverage_v1",
        required=(),
        optional=("providers", "categories", "profile", "artifact_namespace", "report_path"),
        paths=("report_path",),
    ),
    "provider_readiness_v1": _schema(
        "provider_readiness_v1",
        required=("row_type", "provider", "configured", "live_call_allowed"),
        optional=("provider_health_status", "required_env_vars", "request_ledger_path", "no_send_rehearsal", *COMMON_SAFETY),
        safety=("live_call_allowed", "no_send_rehearsal", *COMMON_SAFETY),
        paths=("request_ledger_path",),
    ),
    "provider_preflight_v1": _schema(
        "provider_preflight_v1",
        required=("row_type", "provider", "configured", "live_call_allowed"),
        optional=("fixture_parser_status", "request_ledger_path", "provider_health_status", "required_env_vars", "no_send_rehearsal", *COMMON_SAFETY),
        safety=("live_call_allowed", "no_send_rehearsal", *COMMON_SAFETY),
        paths=("request_ledger_path",),
    ),
    "coinalyze_request_ledger_v1": _schema(
        "coinalyze_request_ledger_v1",
        required=("row_type", "provider", "endpoint", "status"),
        optional=("http_status", "success", "error_class", "redacted_headers", "request_id"),
        types={"provider": "str", "endpoint": "str"},
    ),
    "derivatives_state_snapshot_v1": _schema(
        "derivatives_state_snapshot_v1",
        required=("row_type", "symbol", "provider"),
        optional=("open_interest", "funding_rate", "predicted_funding", "basis", "freshness_status", "derivatives_snapshot_freshness_status", *COMMON_SAFETY),
        safety=COMMON_SAFETY,
    ),
    "derivatives_crowding_candidate_v1": _schema(
        "derivatives_crowding_candidate_v1",
        required=("row_type", "symbol", "crowding_class"),
        optional=("provider", "evidence", "opportunity_type", *COMMON_SAFETY),
        enums={"opportunity_type": ALLOWED_OPPORTUNITY_TYPES},
        safety=COMMON_SAFETY,
    ),
    "fade_review_candidate_v1": _schema(
        "fade_review_candidate_v1",
        required=("row_type", "symbol", "opportunity_type"),
        optional=("crowding_class", "fade_readiness", "evidence", *COMMON_SAFETY),
        enums={"opportunity_type": ALLOWED_OPPORTUNITY_TYPES},
        safety=COMMON_SAFETY,
    ),
    "market_state_snapshot_v1": _schema(
        "market_state_snapshot_v1",
        required=("row_type", "symbol"),
        optional=("coin_id", "market_state_class", "price", "observed_at"),
        timestamps=("observed_at",),
    ),
    "market_anomaly_v1": _schema(
        "market_anomaly_v1",
        required=("row_type", "symbol", "market_state_class"),
        optional=("anomaly_id", "canonical_asset_id", "priority", "source_plan"),
    ),
    "official_exchange_event_v1": _schema(
        "official_exchange_event_v1",
        required=("row_type", "exchange", "title", "source_url", "published_at"),
        optional=("symbol", "coin_id", "event_type", "provider"),
        timestamps=("published_at",),
    ),
    "scheduled_catalyst_event_v1": _schema(
        "scheduled_catalyst_event_v1",
        required=("row_type", "symbol", "source_url"),
        optional=("event_time", "event_start_time", "event_end_time", "unlock_time", "event_type", "title", "timestamp_confidence", "event_timestamp_confidence"),
        timestamps=("event_time", "event_start_time", "event_end_time", "unlock_time"),
    ),
    "unlock_event_v1": _schema(
        "unlock_event_v1",
        required=("row_type", "symbol", "source_url"),
        optional=("event_time", "unlock_time", "unlock_pct_circulating", "unlock_usd", "unlock_vs_30d_adv", "vesting_category"),
        timestamps=("event_time", "unlock_time"),
    ),
    "outcome_row_v1": _schema(
        "outcome_row_v1",
        required=("row_type", "candidate_id", "symbol", "opportunity_type", "outcome_status"),
        optional=("outcome_label", "return_by_horizon", "maturation_state", *COMMON_SAFETY),
        enums={"opportunity_type": ALLOWED_OPPORTUNITY_TYPES},
        safety=COMMON_SAFETY,
    ),
    "calibration_prior_v1": _schema(
        "calibration_prior_v1",
        required=("row_type", "recommendation_only", "auto_apply"),
        optional=("opportunity_type_priors", "provider_prior_suggestions", "source_pack_prior_suggestions"),
        safety=("recommendation_only", "auto_apply", "eligible_for_auto_apply"),
    ),
    "namespace_status_v1": _schema(
        "namespace_status_v1",
        required=("row_type", "namespace", "status", "safe_for_send_readiness"),
        optional=("profile", "reason", "superseded_by", "retention_policy", "archive_after_days", "prune_after_days", "marker_path"),
        enums={"status": ALLOWED_NAMESPACE_STATUSES},
        paths=("marker_path",),
    ),
    "run_ledger_v1": _schema(
        "run_ledger_v1",
        required=("row_type", "run_id", "profile", "run_mode", "artifact_namespace"),
        optional=("started_at", "completed_at", "strict_alerts_created", "telegram_sends", *COMMON_SAFETY),
        safety=("strict_alerts_created", "telegram_sends", *COMMON_SAFETY),
        timestamps=("started_at", "completed_at"),
    ),
}

ROW_TYPE_TO_SCHEMA_ID = {
    "event_core_opportunity": "core_opportunity_v1",
    "event_integrated_radar_candidate": "integrated_radar_candidate_v1",
    "event_alpha_notification_delivery": "notification_delivery_v1",
    "event_integrated_radar_notification_delivery": "integrated_notification_delivery_v1",
    "derivatives_state_snapshot": "derivatives_state_snapshot_v1",
    "event_derivatives_crowding_candidate": "derivatives_crowding_candidate_v1",
    "event_fade_short_review_candidate": "fade_review_candidate_v1",
    "event_market_state_snapshot": "market_state_snapshot_v1",
    "event_market_anomaly": "market_anomaly_v1",
    "event_official_exchange_event": "official_exchange_event_v1",
    "event_scheduled_catalyst": "scheduled_catalyst_event_v1",
    "event_unlock_candidate": "unlock_event_v1",
    "event_integrated_radar_outcome": "outcome_row_v1",
    "event_integrated_radar_calibration_priors": "calibration_prior_v1",
    "event_radar_provider_performance": "calibration_prior_v1",
    "event_alpha_namespace_status": "namespace_status_v1",
    "event_alpha_run": "run_ledger_v1",
}

FILENAME_TO_SCHEMA_ID = {
    "event_core_opportunities.jsonl": "core_opportunity_v1",
    "event_integrated_radar_candidates.jsonl": "integrated_radar_candidate_v1",
    "event_alpha_notification_deliveries.jsonl": "notification_delivery_v1",
    "event_integrated_radar_notification_deliveries.jsonl": "integrated_notification_delivery_v1",
    "event_alpha_source_coverage.json": "source_coverage_v1",
    "event_live_provider_readiness.json": "provider_readiness_v1",
    "event_coinalyze_preflight.json": "provider_preflight_v1",
    "event_coinalyze_request_ledger.jsonl": "coinalyze_request_ledger_v1",
    "event_derivatives_state.jsonl": "derivatives_state_snapshot_v1",
    "event_derivatives_crowding_candidates.jsonl": "derivatives_crowding_candidate_v1",
    "event_fade_short_review_candidates.jsonl": "fade_review_candidate_v1",
    "event_market_state_snapshots.jsonl": "market_state_snapshot_v1",
    "event_market_anomalies.jsonl": "market_anomaly_v1",
    "event_official_exchange_events.jsonl": "official_exchange_event_v1",
    "event_scheduled_catalysts.jsonl": "scheduled_catalyst_event_v1",
    "event_unlock_candidates.jsonl": "unlock_event_v1",
    "event_integrated_radar_outcomes.jsonl": "outcome_row_v1",
    "event_integrated_radar_calibration_priors.json": "calibration_prior_v1",
    "event_radar_provider_performance.json": "calibration_prior_v1",
    "event_alpha_namespace_status.json": "namespace_status_v1",
    "event_alpha_runs.jsonl": "run_ledger_v1",
}


def get_schema(schema_id: str) -> ArtifactSchema:
    return SCHEMAS[schema_id]


def schema_for_row(row: Mapping[str, Any], *, fallback_schema_id: str | None = None) -> ArtifactSchema | None:
    schema_id = str(row.get("schema_id") or "").strip() or ROW_TYPE_TO_SCHEMA_ID.get(str(row.get("row_type") or ""))
    if not schema_id:
        schema_id = fallback_schema_id or ""
    return SCHEMAS.get(schema_id)


def validate_row_against_schema(row: Mapping[str, Any], schema: str | ArtifactSchema) -> list[str]:
    schema_obj = get_schema(schema) if isinstance(schema, str) else schema
    errors: list[str] = []
    errors.extend(validate_required_fields(row, schema_obj))
    errors.extend(validate_types(row, schema_obj))
    errors.extend(validate_enums(row, schema_obj))
    errors.extend(validate_path_fields(row, schema_obj))
    errors.extend(validate_safety_fields(row, schema_obj))
    return errors


def collect_schema_errors(row: Mapping[str, Any], schema: str | ArtifactSchema) -> list[str]:
    return validate_row_against_schema(row, schema)


def validate_required_fields(row: Mapping[str, Any], schema: ArtifactSchema) -> list[str]:
    return [f"missing_required_field:{field}" for field in schema.required_fields if row.get(field) in (None, "", [], {})]


def validate_types(row: Mapping[str, Any], schema: ArtifactSchema) -> list[str]:
    out: list[str] = []
    for field_name, type_name in schema.field_types.items():
        if field_name not in row or row.get(field_name) is None:
            continue
        if not _matches_type(row.get(field_name), type_name):
            out.append(f"invalid_type:{field_name}:{type_name}")
    return out


def validate_enums(row: Mapping[str, Any], schema: ArtifactSchema) -> list[str]:
    out: list[str] = []
    for field_name, allowed in schema.enum_fields.items():
        value = row.get(field_name)
        if value in (None, ""):
            continue
        if str(value) not in {str(item) for item in allowed}:
            out.append(f"invalid_enum:{field_name}:{value}")
    return out


def validate_path_fields(row: Mapping[str, Any], schema: ArtifactSchema) -> list[str]:
    out: list[str] = []
    for field_name in _candidate_path_fields(row, schema):
        value = row.get(field_name)
        if value in (None, ""):
            continue
        values = value if isinstance(value, (list, tuple, set)) else (value,)
        for item in values:
            text = str(item)
            if not text:
                continue
            if Path(text).is_absolute() and not field_name.endswith("_abs_debug"):
                out.append(f"absolute_non_debug_path:{field_name}")
    return out


def validate_safety_fields(row: Mapping[str, Any], schema: ArtifactSchema) -> list[str]:
    out: list[str] = []
    for field_name in schema.safety_fields:
        if field_name not in row:
            continue
        value = row.get(field_name)
        if field_name == "sent" and _truthy(value):
            out.append("unsafe_side_effect_flag:sent")
        if field_name == "research_only" and value is False:
            out.append("unsafe_research_only:false")
        if field_name in {"normal_rsi_signal_written", "triggered_fade_created", "trade_created", "paper_trade_created"} and _truthy(value):
            out.append(f"unsafe_side_effect_flag:{field_name}")
        if field_name in {"trades_created", "paper_trades_created", "strict_alerts_created", "telegram_sends"}:
            try:
                if int(value or 0) != 0:
                    out.append(f"unsafe_side_effect_count:{field_name}")
            except (TypeError, ValueError):
                out.append(f"invalid_safety_count:{field_name}")
        if field_name == "auto_apply" and _truthy(value):
            out.append("unsafe_auto_apply:true")
    return out


def validate_artifact_file(path: str | Path, schema_id: str | None = None) -> dict[str, Any]:
    file_path = Path(path)
    fallback = schema_id or FILENAME_TO_SCHEMA_ID.get(file_path.name)
    rows = _load_artifact_rows(file_path)
    errors: list[dict[str, Any]] = []
    rows_validated = 0
    deprecated_field_usage = 0
    for index, row in enumerate(rows):
        schema = schema_for_row(row, fallback_schema_id=fallback)
        if schema is None:
            continue
        rows_validated += 1
        deprecated_field_usage += sum(
            1
            for field_name in schema.deprecated_fields
            if field_name in row and row.get(field_name) not in (None, "", [], {})
        )
        row_errors = validate_row_against_schema(row, schema)
        for error in row_errors:
            errors.append({"row_index": index, "schema_id": schema.schema_id, "error": error})
    return {
        "path": str(file_path),
        "schema_id": fallback,
        "rows_read": len(rows),
        "rows_validated": rows_validated,
        "deprecated_field_usage": deprecated_field_usage,
        "errors": errors,
    }


def all_schema_fields() -> frozenset[str]:
    fields: set[str] = set()
    for schema in SCHEMAS.values():
        fields.update(schema.declared_fields)
    return frozenset(fields)


def _load_artifact_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    if path.suffix == ".jsonl":
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, Mapping):
                rows.append(dict(value))
        return rows
    try:
        value = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(value, Mapping):
        rows = _extract_known_rows(value)
        return rows if rows else [dict(value)]
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def _extract_known_rows(value: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in ("providers", "provider_rows", "rows", "categories", "sidecars"):
        nested = value.get(key)
        if isinstance(nested, list):
            rows.extend(dict(item) for item in nested if isinstance(item, Mapping))
    return rows


def _candidate_path_fields(row: Mapping[str, Any], schema: ArtifactSchema) -> tuple[str, ...]:
    declared = set(schema.path_fields)
    declared.update(schema.artifact_relpath_fields)
    declared.update(field for field in row if field.endswith("_path") or field.endswith("_paths"))
    return tuple(sorted(declared))


def _matches_type(value: Any, type_name: str) -> bool:
    if type_name == "str":
        return isinstance(value, str)
    if type_name == "bool":
        return isinstance(value, bool)
    if type_name == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if type_name == "float":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if type_name == "list":
        return isinstance(value, list)
    if type_name == "dict":
        return isinstance(value, Mapping)
    return True


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().casefold() in {"1", "true", "yes", "y", "on"}
