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
from . import calendar as calendar_specs, decision_model as decision_model_specs
from . import operator_state as operator_state_specs, provider_lineage_specs
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
    "not_due",
    "planned",
    "sending",
    "sent",
    "delivered",
    "partial_delivered",
    "failed",
    "blocked",
    "in_flight",
    "skipped",
    "skipped_duplicate",
    "skipped_in_flight",
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
DECISION_MODEL_V2_FIELDS = decision_model_specs.FIELDS
DECISION_MODEL_V2_TYPES = decision_model_specs.TYPES
DECISION_MODEL_V2_ENUMS = decision_model_specs.ENUMS
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
    allows_guarded_send: bool = False
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
OPERATION_SAFETY = tuple(
    dict.fromkeys(
        (
            "research_only",
            "no_send_rehearsal",
            "strict_alerts_created",
            "telegram_sends",
            "trades_created",
            "paper_trades_created",
            "normal_rsi_signal_rows_written",
            "triggered_fade_created",
            *COMMON_SAFETY,
        )
    )
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
COMMON_TIMESTAMPS = (
    "generated_at",
    "observed_at",
    "created_at",
    "updated_at",
    "published_at",
    "started_at",
    "finished_at",
    "attempted_at",
    "delivered_at",
)
SECRET_FIELD_NAMES = frozenset({
    "api_key",
    "api_secret",
    "auth_token",
    "authorization",
    "bearer_token",
    "client_secret",
    "secret",
    "token",
    "x-api-key",
})
SECRET_FIELD_FRAGMENTS = (
    "api_key",
    "api-secret",
    "api_secret",
    "auth_token",
    "authorization",
    "bearer_token",
    "client_secret",
    "secret_key",
    "private_key",
    "telegram_bot_token",
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
    allows_guarded_send: bool = False,
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
        timestamp_fields=tuple(dict.fromkeys((*timestamps, *COMMON_TIMESTAMPS))),
        safety_fields=tuple(safety),
        lineage_fields=tuple(dict.fromkeys((*lineage, *COMMON_LINEAGE))),
        artifact_relpath_fields=tuple(paths),
        secret_redaction_fields=tuple(sorted(SECRET_FIELD_NAMES)),
        allows_guarded_send=bool(allows_guarded_send),
    )

SCHEMAS: dict[str, ArtifactSchema] = {
    "core_opportunity_v1": _schema(
        "core_opportunity_v1",
        required=("row_type", "core_opportunity_id", "symbol", "opportunity_type"),
        optional=(
            "schema_id", "schema_version", "coin_id", "canonical_asset_id", "candidate_role",
            "incident_id", "source_pack", "source_packs", "source_origin", "latest_source",
            "latest_source_url", "latest_source_title", "market_state_class",
            "crowding_class", "source_strength", "opportunity_score_final",
            "final_level", "route", "state", "why_now", "what_confirms",
            "what_invalidates", "why_not_alertable", "feedback_target",
            "candidate_provenance", "candidate_source_mode", "contract_counted_candidate",
            "provider_generation_id", "provider_request_succeeded", "provider_source_artifact",
            "request_ledger_path", "market_refresh_attempted", "market_refresh_success",
            "market_refresh_status", "market_refresh_provider", "market_refresh_observed_at",
            "market_refresh_artifact", "targeted_market_refresh_id",
            "targeted_market_refresh_ledger_path",
            *DECISION_MODEL_V2_FIELDS,
            *COMMON_SAFETY,
        ),
        types={
            "row_type": "str",
            "core_opportunity_id": "str",
            "symbol": "str",
            "opportunity_type": "str",
            **DECISION_MODEL_V2_TYPES,
        },
        enums={
            "opportunity_type": ALLOWED_OPPORTUNITY_TYPES,
            "final_level": ALLOWED_FINAL_LEVELS,
            **DECISION_MODEL_V2_ENUMS,
        },
        safety=COMMON_SAFETY,
        paths=(
            "card_path", "research_card_path", "canonical_card_path",
            "provider_source_artifact", "request_ledger_path", "market_refresh_artifact",
            "targeted_market_refresh_ledger_path",
        ),
        lineage=COMMON_LINEAGE,
    ),
    "integrated_radar_candidate_v1": _schema(
        "integrated_radar_candidate_v1",
        required=("row_type", "candidate_id", "symbol", "opportunity_type"),
        optional=(
            "schema_id", "schema_version", "candidate_family_id", "coin_id",
            "canonical_asset_id", "core_opportunity_id", "provider", "providers",
            "source_pack", "source_packs", "source_origin", "source_strength",
            "market_state", "market_state_class", "market_state_snapshot",
            "crowding_class", "fade_readiness", "derivatives_state_snapshot",
            "official_exchange_event", "scheduled_catalyst_event", "unlock_event",
            "resolver_confidence", "instrument_resolver_confidence",
            "instrument_resolver_warnings", "opportunity_score_final",
            "why_now", "what_confirms", "what_invalidates", "why_not_alertable",
            "candidate_provenance", "candidate_source_mode", "contract_counted_candidate",
            "provider_generation_id", "provider_request_succeeded", "provider_source_artifact",
            "request_ledger_path", "source_provider", "source_pack_id",
            "market_refresh_attempted", "market_refresh_success", "market_refresh_status",
            "market_refresh_provider", "market_refresh_observed_at", "market_refresh_artifact",
            "targeted_market_refresh_id", "targeted_market_refresh_ledger_path",
            *DECISION_MODEL_V2_FIELDS,
            *COMMON_SAFETY, *OPERATION_SAFETY,
        ),
        types={
            "row_type": "str",
            "candidate_id": "str",
            "symbol": "str",
            "opportunity_type": "str",
            **DECISION_MODEL_V2_TYPES,
        },
        enums={"opportunity_type": ALLOWED_OPPORTUNITY_TYPES, **DECISION_MODEL_V2_ENUMS},
        safety=tuple(dict.fromkeys((*COMMON_SAFETY, *OPERATION_SAFETY))),
        paths=(
            "provider_source_artifact", "request_ledger_path", "card_path", "research_card_path",
            "market_refresh_artifact", "targeted_market_refresh_ledger_path",
        ),
        lineage=COMMON_LINEAGE,
    ),
    "notification_delivery_v1": _schema(
        "notification_delivery_v1",
        required=("row_type", "delivery_id", "status"),
        optional=(
            "schema_id", "schema_version", "delivery_status", "status_detail",
            "delivery_state", "delivery_mode", "sent", "would_send",
            "send_guard_enabled", "no_send_rehearsal", "message_text",
            "message_html", "lane", "route", "card_paths", "canonical_card_path",
            "canonical_card_paths", "notification_preview_path",
            "notification_preview_relpath", "core_opportunity_id",
            "core_opportunity_ids", "canonical_symbols", "content_hash",
            "recipient_count", "delivered_count", "failed_count",
            *COMMON_SAFETY,
        ),
        enums={"status": ALLOWED_DELIVERY_STATUSES, "delivery_status": ALLOWED_DELIVERY_STATUSES},
        safety=COMMON_SAFETY,
        paths=("card_path", "canonical_card_path", "notification_preview_path"),
        timestamps=("attempted_at", "delivered_at"),
        lineage=COMMON_LINEAGE,
        allows_guarded_send=True,
    ),
    "integrated_notification_delivery_v1": _schema(
        "integrated_notification_delivery_v1",
        required=("row_type", "lane", "sent", "no_send_rehearsal"),
        optional=(
            "schema_id", "schema_version", "status", "lane_title", "route",
            "status_detail", "would_send", "send_guard_enabled", "message_text",
            "message_html", "card_paths", "skipped_items", "candidate_ids",
            "core_opportunity_ids", "canonical_symbols", "content_hash",
            "rendered_item_count", "eligible_item_count", "skipped_item_count",
            "preview_path", "preview_kind", "zero_candidate_preview",
            *COMMON_SAFETY,
        ),
        enums={"status": ALLOWED_DELIVERY_STATUSES},
        safety=COMMON_SAFETY,
        paths=("card_path", "notification_preview_path", "preview_path"),
        timestamps=("generated_at",),
        lineage=COMMON_LINEAGE,
    ),
    "event_alpha_daily_burn_in_run_v1": _schema(
        "event_alpha_daily_burn_in_run_v1",
        required=("row_type", "profile", "artifact_namespace", "steps", "research_only", "no_send_rehearsal"),
        optional=(
            "schema_id", "schema_version", "run_id", "generated_at", "started_at", "finished_at", "last_updated_at",
            "namespace_dir", "completed", "smoke", "steps_total", "steps_passed",
            "steps_skipped", "steps_failed", "steps_timeout", "required_failed",
            "steps_interrupted", "status", "final_status_reason", "timeout_seconds", "coinalyze_rehearsal_allowed",
            "candidate_mode", "no_send", "live_provider_calls_allowed",
            "candidate_mode_manifest_path", "provider_activation_status",
            "skipped_missing_config", "skipped_live_calls_disabled",
            "next_steps",
            "required", "skip_reason", "command", "returncode", "stdout_tail",
            "stderr_tail", "duration_seconds", "started_at", "finished_at",
            "step_started_at", "step_finished_at",
            "artifact_paths_written", "candidate_rows_written", "provider_calls_attempted",
            "live_calls_attempted", "safety_side_effects",
            "safe_environment", *OPERATION_SAFETY,
        ),
        types={"row_type": "str", "profile": "str", "artifact_namespace": "str", "completed": "bool"},
        safety=OPERATION_SAFETY,
        paths=("candidate_mode_manifest_path",),
        timestamps=("generated_at", "last_updated_at"),
        lineage=("profile", "artifact_namespace"),
    ),
    "event_alpha_candidate_mode_manifest_v1": _schema(
        "event_alpha_candidate_mode_manifest_v1",
        required=("row_type", "profile", "artifact_namespace", "candidate_mode", "research_only", "no_send_rehearsal"),
        optional=(
            "schema_id", "schema_version", "generated_at", "last_updated_at",
            "namespace_dir", "completed", "status", "no_send", "live_provider_calls_allowed",
            "providers", "skipped_missing_config", "skipped_live_calls_disabled",
            "skipped_request_budget", "skipped_not_required_for_profile",
            "next_steps", "candidate_rows", "real_burn_in_candidate_count",
            "contract_counted_candidate_count", "fixture_candidate_count",
            "preflight_diagnostic_rows", "readiness_rows", "source_coverage_rows",
            "integrated_candidate_rows", "notification_preview_rows",
            "provider_attempts", "provider_skips", "provider_successes",
            "request_ledger_rows", "request_ledgers", "source_artifacts",
            "candidate_artifacts", "review_inbox_path", "scorecard_path",
            "doctor_status", "providers_with_candidates",
            *OPERATION_SAFETY,
        ),
        types={"row_type": "str", "profile": "str", "artifact_namespace": "str", "candidate_mode": "bool"},
        safety=OPERATION_SAFETY,
        timestamps=("generated_at", "last_updated_at"),
        lineage=("profile", "artifact_namespace"),
    ),
    "event_alpha_daily_review_inbox_v1": _schema(
        "event_alpha_daily_review_inbox_v1",
        required=("row_type", "profile", "artifact_namespace", "items", "research_only", "no_send_rehearsal"),
        optional=(
            "schema_id", "schema_version", "generated_at", "namespace_dir",
            "review_time_budget_minutes", "family_grouped", "visible_family_grouped",
            "items_count", "selected_primary_family_count", "collapsed_primary_family_count",
            "second_family_items_count", "rejected_second_family_items_count",
            "family_summaries", "collapsed_family_summary", "stale_path_warnings",
            "blockers", *OPERATION_SAFETY,
        ),
        types={"row_type": "str", "profile": "str", "artifact_namespace": "str"},
        safety=OPERATION_SAFETY,
        timestamps=("generated_at",),
        lineage=("profile", "artifact_namespace"),
    ),
    "event_alpha_burn_in_scorecard_v1": _schema(
        "event_alpha_burn_in_scorecard_v1",
        required=("row_type", "profile", "artifact_namespace", "research_only", "no_send_rehearsal"),
        optional=(
            "schema_id", "schema_version", "generated_at", "namespace_dir",
            "window_days", "evidence_scope", "namespace_scope", "burn_in_contract_scope",
            "count_explicit_namespace_for_burn_in", "include_reason",
            "namespace_policy", "contract", "enough_data",
            "enough_data_reasons", "auto_apply", "auto_apply_thresholds",
            "fixture_candidate_count", "contract_counted_candidate_count",
            "real_burn_in_candidate_count",
            "warnings", *OPERATION_SAFETY,
        ),
        types={"row_type": "str", "profile": "str", "artifact_namespace": "str"},
        safety=OPERATION_SAFETY + ("auto_apply",),
        timestamps=("generated_at",),
        lineage=("profile", "artifact_namespace"),
    ),
    "event_alpha_burn_in_measurement_dashboard_v1": _schema(
        "event_alpha_burn_in_measurement_dashboard_v1",
        required=("row_type", "profile", "artifact_namespace", "evidence_scope", "auto_apply_thresholds", "research_only", "no_send_rehearsal"),
        optional=(
            "schema_id", "schema_version", "generated_at", "namespace_dir",
            "window_days", "namespace_policy", "burn_in_contract_scope",
            "candidate_source_scope", "explicit_scope_warning", "enough_data",
            "enough_data_reasons", "low_sample_warning", "min_sample_warning",
            "source_yield_confidence", *OPERATION_SAFETY,
        ),
        types={"row_type": "str", "profile": "str", "artifact_namespace": "str", "auto_apply_thresholds": "bool"},
        safety=OPERATION_SAFETY + ("auto_apply_thresholds",),
        timestamps=("generated_at",),
        lineage=("profile", "artifact_namespace"),
    ),
    "event_alpha_source_yield_report_v1": _schema(
        "event_alpha_source_yield_report_v1",
        required=("row_type", "profile", "artifact_namespace", "evidence_scope", "auto_apply", "research_only", "no_send_rehearsal"),
        optional=(
            "schema_id", "schema_version", "generated_at", "namespace_dir",
            "window_days", "namespace_policy", "burn_in_contract_scope",
            "candidate_source_scope", "providers", "source_packs",
            "source_yield_confidence", "recommendations_only",
            "auto_apply_thresholds", *OPERATION_SAFETY,
        ),
        types={"row_type": "str", "profile": "str", "artifact_namespace": "str", "auto_apply": "bool"},
        safety=OPERATION_SAFETY + ("auto_apply", "auto_apply_thresholds"),
        timestamps=("generated_at",),
        lineage=("profile", "artifact_namespace"),
    ),
    "event_alpha_burn_in_archive_manifest_v1": _schema(
        "event_alpha_burn_in_archive_manifest_v1",
        required=("row_type", "dry_run", "archive_scope", "research_only", "no_send_rehearsal"),
        optional=(
            "schema_id", "schema_version", "generated_at", "base_dir",
            "archive_path", "manifest_path", "checksums_path",
            "archive_created", "namespace_policy_version", "namespace_policy",
            "included_namespaces", "excluded_namespaces", "enough_data",
            "enough_data_reasons", "secret_hits", "secret_hit_count",
            "secret_scan_summary", "checksum_manifest", *OPERATION_SAFETY,
        ),
        types={"row_type": "str", "dry_run": "bool"},
        safety=OPERATION_SAFETY,
        paths=("archive_path", "manifest_path", "checksums_path"),
        timestamps=("generated_at",),
        lineage=("profile", "artifact_namespace"),
    ),
    "event_alpha_burn_in_namespace_policy_v1": _schema(
        "event_alpha_burn_in_namespace_policy_v1",
        required=("row_type", "profile", "artifact_namespace", "namespace_policy_version", "research_only", "no_send_rehearsal"),
        optional=(
            "schema_id", "schema_version", "generated_at", "namespace_dir",
            "base_dir", "default_include_statuses", "default_exclude_statuses",
            "explicit_inclusion_flags", "explicit_include_namespaces",
            "included_namespaces", "excluded_namespaces", "exclusion_reasons",
            "excluded_reasons", "include_reasons", "namespace_status",
            "latest_doctor_status", "latest_run_id", "artifact_counts",
            "included_without_burn_in_run_count", "fixture_live_mix_blocker",
            *OPERATION_SAFETY,
        ),
        types={"row_type": "str", "profile": "str", "artifact_namespace": "str"},
        safety=OPERATION_SAFETY,
        timestamps=("generated_at",),
        lineage=("profile", "artifact_namespace"),
    ),
    "source_coverage_v1": _schema(
        "source_coverage_v1",
        required=(),
        optional=(
            "schema_id", "schema_version", "row_type", "source", "providers",
            "provider_rows", "categories", "sidecars", "profile",
            "artifact_namespace", "candidate_count", "lane_counts",
            "source_pack_counts", "report_path", "live_provider_readiness_report_path",
            "live_provider_readiness_json_path", "coinalyze_provider_health_status",
            "coinalyze_freshness_status",
        ),
        paths=("report_path", "live_provider_readiness_report_path", "live_provider_readiness_json_path"),
        lineage=COMMON_LINEAGE,
    ),
    **provider_lineage_specs.provider_control_schemas(
        _schema,
        common_safety=COMMON_SAFETY,
        common_lineage=COMMON_LINEAGE,
    ),
    **provider_lineage_specs.provider_market_schemas(
        _schema,
        common_safety=COMMON_SAFETY,
        operation_safety=OPERATION_SAFETY,
        common_lineage=COMMON_LINEAGE,
        allowed_opportunity_types=ALLOWED_OPPORTUNITY_TYPES,
    ),
    "market_anomaly_v1": _schema(
        "market_anomaly_v1",
        required=("row_type", "symbol", "market_state_class"),
        optional=(
            "schema_id", "schema_version", "anomaly_id", "market_anomaly_id",
            "coin_id", "canonical_asset_id", "anomaly_type", "anomaly_bucket",
            "priority", "source_plan", "source_plan_status",
            "suggested_source_packs", "suggested_source_packs_to_search",
            "search_queries", "no_alert_until_evidence",
            "decision_model_v2_catalyst_required", "catalyst_search_role",
            *COMMON_SAFETY,
        ),
        safety=COMMON_SAFETY,
        timestamps=("observed_at", "search_deadline"),
        lineage=COMMON_LINEAGE,
    ),
    "official_exchange_event_v1": _schema(
        "official_exchange_event_v1",
        required=("row_type", "exchange", "title", "source_url", "published_at"),
        optional=(
            "schema_id", "schema_version", "symbol", "symbols", "coin_id",
            "coin_ids", "event_type", "provider", "announcement_id",
            "official_exchange_event_id", "source_pack", "impact_path_type",
            "confidence", "reason_codes", "raw_payload_redacted",
            "provider_generation_id", "provider_request_succeeded",
            "provider_source_artifact", "request_ledger_path", *COMMON_SAFETY,
        ),
        safety=COMMON_SAFETY,
        paths=("provider_source_artifact", "request_ledger_path"),
        timestamps=("published_at", "observed_at"),
        lineage=COMMON_LINEAGE,
    ),
    "scheduled_catalyst_event_v1": _schema(
        "scheduled_catalyst_event_v1",
        required=("row_type", "symbol", "source_url"),
        optional=(
            "schema_id", "schema_version", "coin_id", "canonical_asset_id",
            "event_time", "event_start_time", "event_end_time", "unlock_time",
            "event_type", "title", "source", "source_class",
            "timestamp_confidence", "event_timestamp_confidence",
            "materiality_score", *COMMON_SAFETY,
        ),
        safety=COMMON_SAFETY,
        timestamps=("event_time", "event_start_time", "event_end_time", "unlock_time"),
        lineage=COMMON_LINEAGE,
    ),
    **calendar_specs.schema_specs(
        _schema,
        operation_safety=OPERATION_SAFETY,
        common_lineage=COMMON_LINEAGE,
    ),
    "unlock_event_v1": _schema(
        "unlock_event_v1",
        required=("row_type", "symbol", "source_url"),
        optional=(
            "schema_id", "schema_version", "coin_id", "canonical_asset_id",
            "event_time", "unlock_time", "unlock_pct_circulating",
            "unlock_usd", "unlock_vs_30d_adv", "vesting_category",
            "vesting_type", "cliff_or_linear", "timestamp_confidence",
            "event_timestamp_confidence", *COMMON_SAFETY,
        ),
        safety=COMMON_SAFETY,
        timestamps=("event_time", "unlock_time"),
        lineage=COMMON_LINEAGE,
    ),
    "outcome_row_v1": _schema(
        "outcome_row_v1",
        required=("row_type", "symbol", "opportunity_type"),
        optional=(
            "schema_id", "schema_version", "candidate_id", "core_opportunity_id",
            "outcome_status", "outcome_label", "maturation_state",
            "return_by_horizon", "max_favorable_excursion",
            "max_adverse_excursion", "price_data_status", "market_state_class",
            "crowding_class", *DECISION_MODEL_V2_FIELDS, *COMMON_SAFETY,
        ),
        types={**DECISION_MODEL_V2_TYPES},
        enums={"opportunity_type": ALLOWED_OPPORTUNITY_TYPES, **DECISION_MODEL_V2_ENUMS},
        safety=COMMON_SAFETY,
        timestamps=("observed_at", "matured_at"),
        lineage=COMMON_LINEAGE,
    ),
    "calibration_prior_v1": _schema(
        "calibration_prior_v1",
        required=("auto_apply",),
        optional=(
            "schema_id", "schema_version", "row_type", "recommendation_only",
            "source_pack_prior_suggestions", "provider_prior_suggestions",
            "lane_threshold_suggestions", "opportunity_type_priors",
            "provider_priors", "source_pack_priors", "min_sample_warning",
            "min_sample", "sample_count", "auto_applied", "eligible_for_auto_apply",
        ),
        types={"auto_apply": "bool"},
        safety=("recommendation_only", "auto_apply", "eligible_for_auto_apply", "auto_applied"),
    ),
    "namespace_status_v1": _schema(
        "namespace_status_v1",
        required=("row_type", "namespace", "status", "safe_for_send_readiness"),
        optional=(
            "schema_id", "schema_version", "profile", "reason", "superseded_by",
            "retention_policy", "archive_after_days", "prune_after_days",
            "marker_path", "marked_at", "created_at", "last_updated_at",
            "last_verified_at", "safe_for_burn_in_measurement",
            "safe_for_calibration", "current_doctor_status", "latest_run_id",
            "artifact_counts", "key_artifacts_present", "missing_key_artifacts",
            "readiness_required", "readiness_present", "operator_state_path", "operator_state_run_id",
            "operator_state_revision", "operator_state_status", "doctor_run_id", "doctor_state_revision",
            "counter_schema_version", "raw_events", "candidate_events", "research_candidates",
            "source_alert_snapshots", "current_generation_core_rows",
            "current_generation_visible_core_rows", "cumulative_store_rows",
            "alertable_decisions", "strict_alerts", "preview_rendered_items",
            "burn_in_mode", "send_guard_status", "send_requested", "send_attempted",
            "no_send_rehearsal", "decision_model_version", "decision_model_v2_enabled", "decision_model_v2_row_count",
            "radar_route_counts", "confidence_band_counts", "thesis_origin_counts",
            "directional_bias_counts", "catalyst_status_counts", "timing_state_counts",
            "tradability_status_counts",
            "actionable_research_ideas", "high_confidence_research_ideas",
        ),
        types={
            "safe_for_send_readiness": "bool",
            "safe_for_burn_in_measurement": "bool",
            "safe_for_calibration": "bool",
            "readiness_required": "bool",
            "readiness_present": "bool",
            "operator_state_revision": "int", "doctor_state_revision": "int",
            "raw_events": "int", "candidate_events": "int", "research_candidates": "int",
            "source_alert_snapshots": "int", "current_generation_core_rows": "int",
            "current_generation_visible_core_rows": "int", "cumulative_store_rows": "int",
            "alertable_decisions": "int", "strict_alerts": "int", "preview_rendered_items": "int",
            "send_requested": "bool", "send_attempted": "bool", "no_send_rehearsal": "bool",
            "decision_model_v2_enabled": "bool", "decision_model_v2_row_count": "int", "radar_route_counts": "dict",
            "confidence_band_counts": "dict", "thesis_origin_counts": "dict", "directional_bias_counts": "dict",
            "catalyst_status_counts": "dict", "timing_state_counts": "dict", "tradability_status_counts": "dict",
        },
        enums={"status": ALLOWED_NAMESPACE_STATUSES},
        paths=("marker_path", "operator_state_path"),
        timestamps=("marked_at", "created_at", "last_updated_at", "last_verified_at"),
        safety=("safe_for_send_readiness", "safe_for_burn_in_measurement", "safe_for_calibration"),
        lineage=("profile", "artifact_namespace"),
    ),
    "operator_state_v1": _schema(
        "operator_state_v1",
        required=("row_type", "run_id", "profile", "artifact_namespace", "revision", "manifest_status", "artifacts", "doctor", "research_only", "no_send_rehearsal", "sent", "send_requested", "send_attempted", "send_success", "send_items_delivered", "trades_created", "paper_trades_created", "normal_rsi_signal_rows_written", "triggered_fade_created"),
        optional=(
            "schema_id", "schema_version", "run_mode", "run_started_at", "generated_at", "updated_at",
            "invalidation_reason", "counter_schema_version", "raw_events",
            "candidate_events", "research_candidates", "source_alert_snapshots",
            "current_generation_core_rows", "current_generation_visible_core_rows",
            "cumulative_store_rows", "alertable_decisions", "strict_alerts",
            "preview_rendered_items", "burn_in_mode", "send_guard_status",
            "decision_model_version", "decision_model_v2_enabled", "decision_model_v2_row_count",
            "radar_route_counts", "confidence_band_counts", "thesis_origin_counts",
            "directional_bias_counts", "catalyst_status_counts", "timing_state_counts",
            "tradability_status_counts",
            "actionable_research_ideas", "high_confidence_research_ideas",
        ),
        types={
            "revision": "int", "artifacts": "dict", "doctor": "dict",
            "invalidation_reason": "str", "research_only": "bool",
            "no_send_rehearsal": "bool", "sent": "bool", "send_requested": "bool",
            "send_attempted": "bool", "send_success": "bool", "send_items_delivered": "int",
            "raw_events": "int", "candidate_events": "int", "research_candidates": "int",
            "source_alert_snapshots": "int", "current_generation_core_rows": "int",
            "current_generation_visible_core_rows": "int", "cumulative_store_rows": "int",
            "alertable_decisions": "int", "strict_alerts": "int", "preview_rendered_items": "int",
            "decision_model_v2_enabled": "bool", "decision_model_v2_row_count": "int", "radar_route_counts": "dict",
            "confidence_band_counts": "dict", "thesis_origin_counts": "dict", "directional_bias_counts": "dict",
            "catalyst_status_counts": "dict", "timing_state_counts": "dict", "tradability_status_counts": "dict",
            "actionable_research_ideas": "int", "high_confidence_research_ideas": "int",
            "trades_created": "int", "paper_trades_created": "int", "normal_rsi_signal_rows_written": "int", "triggered_fade_created": "int",
        },
        enums={"manifest_status": ("complete", "partial", "incoherent")},
        safety=("research_only", "no_send_rehearsal", "sent", "trades_created", "paper_trades_created", "normal_rsi_signal_rows_written", "triggered_fade_created"),
        timestamps=("run_started_at", "generated_at", "updated_at"),
        lineage=COMMON_LINEAGE,
        allows_guarded_send=True,
    ),
    "run_ledger_v1": _schema(
        "run_ledger_v1",
        required=("row_type", "run_id", "profile"),
        optional=(
            "schema_id", "schema_version", "run_mode", "artifact_namespace",
            "started_at", "finished_at", "completed_at", "generated_at",
            "success", "failure", "with_llm", "send_requested",
            "strict_alerts_created", "telegram_sends", "integrated_candidates",
            "counter_schema_version", "raw_events", "candidate_events",
            "research_candidates", "source_alert_snapshots",
            "current_generation_core_rows", "current_generation_visible_core_rows",
            "cumulative_store_rows", "alertable_decisions", "strict_alerts",
            "preview_rendered_items", "deprecated_counter_aliases",
            "burn_in_mode", "send_guard_status", "send_attempted", "no_send_rehearsal",
            "integrated_candidates_path", "source_coverage_json_path_rel",
            "source_coverage_md_path_rel", "daily_brief_path", "notification_preview_path",
            "source_coverage_path", "live_provider_readiness_json_path",
            "live_provider_readiness_report_path", "decision_model_version",
            "decision_model_v2_enabled", "decision_model_v2_row_count", "radar_route_counts", "confidence_band_counts",
            "unified_calendar_rows", "unified_calendar_path", "unified_calendar_preview_path",
            "thesis_origin_counts", "directional_bias_counts", "catalyst_status_counts", "timing_state_counts",
            "tradability_status_counts", "actionable_research_ideas",
            "high_confidence_research_ideas", *COMMON_SAFETY,
        ),
        types={
            "decision_model_v2_enabled": "bool", "decision_model_v2_row_count": "int", "unified_calendar_rows": "int",
            "radar_route_counts": "dict", "confidence_band_counts": "dict", "thesis_origin_counts": "dict",
            "directional_bias_counts": "dict", "catalyst_status_counts": "dict", "timing_state_counts": "dict", "tradability_status_counts": "dict",
            "actionable_research_ideas": "int", "high_confidence_research_ideas": "int",
        },
        safety=("strict_alerts_created", "telegram_sends", *COMMON_SAFETY),
        timestamps=("started_at", "finished_at", "completed_at", "generated_at"),
        paths=(
            "integrated_candidates_path", "integrated_report_path", "integrated_input_manifest_path",
            "integrated_source_coverage_json_path", "daily_brief_path", "notification_preview_path",
            "source_coverage_path", "live_provider_readiness_json_path", "live_provider_readiness_report_path", "unified_calendar_path", "unified_calendar_preview_path",
        ),
        lineage=COMMON_LINEAGE,
        allows_guarded_send=True,
    ),
}

ROW_TYPE_TO_SCHEMA_ID = {
    "event_core_opportunity": "core_opportunity_v1",
    "event_integrated_radar_candidate": "integrated_radar_candidate_v1",
    "event_alpha_notification_delivery": "notification_delivery_v1",
    "event_integrated_radar_notification_delivery": "integrated_notification_delivery_v1",
    "event_live_provider_activation_readiness": "provider_readiness_v1",
    "event_official_exchange_activation": "provider_readiness_v1",
    "event_coinalyze_preflight": "provider_preflight_v1",
    "event_coinalyze_rehearsal_report": "provider_preflight_v1",
    "event_bybit_announcements_preflight": "provider_preflight_v1",
    "event_bybit_announcements_rehearsal_report": "provider_preflight_v1",
    "event_unlock_calendar_preflight": "provider_preflight_v1",
    "event_dex_onchain_readiness": "provider_readiness_v1",
    "coinalyze_request_ledger": "coinalyze_request_ledger_v1",
    "derivatives_state_snapshot": "derivatives_state_snapshot_v1",
    "event_derivatives_crowding_candidate": "derivatives_crowding_candidate_v1",
    "event_fade_short_review_candidate": "fade_review_candidate_v1",
    "fade_short_review_candidate": "fade_review_candidate_v1",
    "event_market_state_snapshot": "market_state_snapshot_v1",
    "event_targeted_market_refresh_ledger": "targeted_market_refresh_ledger_v1",
    "event_targeted_market_refresh_report": "targeted_market_refresh_report_v1",
    "event_market_anomaly": "market_anomaly_v1",
    "event_market_anomaly_catalyst_search_queue": "market_anomaly_v1",
    "event_official_exchange_event": "official_exchange_event_v1",
    "official_exchange_event": "official_exchange_event_v1",
    "exchange_announcement": "official_exchange_event_v1",
    "event_scheduled_catalyst": "scheduled_catalyst_event_v1",
    "scheduled_catalyst": "scheduled_catalyst_event_v1",
    "event_unified_calendar_event": "unified_calendar_event_v1",
    "event_unlock_candidate": "unlock_event_v1",
    "unlock_candidate": "unlock_event_v1",
    "event_integrated_radar_outcome": "outcome_row_v1",
    "event_integrated_radar_calibration_priors": "calibration_prior_v1",
    "event_radar_provider_performance": "calibration_prior_v1",
    "event_alpha_namespace_status": "namespace_status_v1",
    "event_alpha_operator_state": "operator_state_v1",
    "event_alpha_run": "run_ledger_v1",
    "event_alpha_daily_burn_in_run": "event_alpha_daily_burn_in_run_v1",
    "event_alpha_candidate_mode_manifest": "event_alpha_candidate_mode_manifest_v1",
    "event_alpha_daily_review_inbox": "event_alpha_daily_review_inbox_v1",
    "event_alpha_burn_in_scorecard": "event_alpha_burn_in_scorecard_v1",
    "event_alpha_burn_in_measurement_dashboard": "event_alpha_burn_in_measurement_dashboard_v1",
    "event_alpha_source_yield_report": "event_alpha_source_yield_report_v1",
    "event_alpha_burn_in_archive_manifest": "event_alpha_burn_in_archive_manifest_v1",
    "event_alpha_burn_in_namespace_policy": "event_alpha_burn_in_namespace_policy_v1",
}

FILENAME_TO_SCHEMA_ID = {
    "event_core_opportunities.jsonl": "core_opportunity_v1",
    "event_integrated_radar_candidates.jsonl": "integrated_radar_candidate_v1",
    "event_alpha_notification_deliveries.jsonl": "notification_delivery_v1",
    "event_integrated_radar_notification_deliveries.jsonl": "integrated_notification_delivery_v1",
    "event_alpha_source_coverage.json": "source_coverage_v1",
    "event_live_provider_readiness.json": "provider_readiness_v1",
    "event_live_provider_activation_readiness.json": "provider_readiness_v1",
    "event_coinalyze_preflight.json": "provider_preflight_v1",
    "event_coinalyze_rehearsal_report.json": "provider_preflight_v1",
    "event_bybit_announcements_preflight.json": "provider_preflight_v1",
    "event_bybit_announcements_rehearsal_report.json": "provider_preflight_v1",
    "event_unlock_calendar_preflight.json": "provider_preflight_v1",
    "event_official_exchange_activation.json": "provider_readiness_v1",
    "event_dex_onchain_readiness.json": "provider_readiness_v1",
    "event_coinalyze_request_ledger.jsonl": "coinalyze_request_ledger_v1",
    "event_bybit_announcements_request_ledger.jsonl": "provider_request_ledger_v1",
    "event_derivatives_state.jsonl": "derivatives_state_snapshot_v1",
    "event_derivatives_crowding_candidates.jsonl": "derivatives_crowding_candidate_v1",
    "event_fade_short_review_candidates.jsonl": "fade_review_candidate_v1",
    "event_market_state_snapshots.jsonl": "market_state_snapshot_v1",
    "event_targeted_market_refresh_ledger.jsonl": "targeted_market_refresh_ledger_v1",
    "event_targeted_market_refresh_report.json": "targeted_market_refresh_report_v1",
    "event_market_anomalies.jsonl": "market_anomaly_v1",
    "event_market_anomaly_catalyst_search_queue.jsonl": "market_anomaly_v1",
    "event_exchange_announcements.jsonl": "official_exchange_event_v1",
    "event_official_exchange_events.jsonl": "official_exchange_event_v1",
    "event_scheduled_catalysts.jsonl": "scheduled_catalyst_event_v1",
    "event_unified_calendar_events.jsonl": "unified_calendar_event_v1",
    "event_unlock_candidates.jsonl": "unlock_event_v1",
    "event_integrated_radar_outcomes.jsonl": "outcome_row_v1",
    "event_integrated_radar_calibration_priors.json": "calibration_prior_v1",
    "event_radar_provider_performance.json": "calibration_prior_v1",
    "event_alpha_namespace_status.json": "namespace_status_v1",
    "event_alpha_operator_state.json": "operator_state_v1",
    "event_alpha_runs.jsonl": "run_ledger_v1",
    "event_alpha_daily_burn_in_run.json": "event_alpha_daily_burn_in_run_v1",
    "event_alpha_candidate_mode_manifest.json": "event_alpha_candidate_mode_manifest_v1",
    "event_alpha_daily_review_inbox.json": "event_alpha_daily_review_inbox_v1",
    "event_alpha_burn_in_scorecard.json": "event_alpha_burn_in_scorecard_v1",
    "event_alpha_burn_in_measurement_dashboard.json": "event_alpha_burn_in_measurement_dashboard_v1",
    "event_alpha_source_yield_report.json": "event_alpha_source_yield_report_v1",
    "event_alpha_burn_in_archive_manifest.json": "event_alpha_burn_in_archive_manifest_v1",
    "event_alpha_burn_in_namespace_policy.json": "event_alpha_burn_in_namespace_policy_v1",
}


def get_schema(schema_id: str) -> ArtifactSchema:
    return SCHEMAS[schema_id]


def infer_schema_id_for_file(path: str | Path) -> str | None:
    """Infer a schema id from a known Event Alpha artifact filename."""
    return FILENAME_TO_SCHEMA_ID.get(Path(path).name)


def schema_for_row(row: Mapping[str, Any], *, fallback_schema_id: str | None = None) -> ArtifactSchema | None:
    schema_id = str(row.get("schema_id") or "").strip()
    if not schema_id and fallback_schema_id:
        schema_id = str(fallback_schema_id).strip()
    if not schema_id:
        schema_id = ROW_TYPE_TO_SCHEMA_ID.get(str(row.get("row_type") or "")) or ""
    return SCHEMAS.get(schema_id)


def validate_row_against_schema(row: Mapping[str, Any], schema: str | ArtifactSchema) -> list[str]:
    schema_obj = get_schema(schema) if isinstance(schema, str) else schema
    errors: list[str] = []
    errors.extend(validate_required_fields(row, schema_obj))
    errors.extend(validate_types(row, schema_obj))
    errors.extend(validate_enums(row, schema_obj))
    errors.extend(validate_path_fields(row, schema_obj))
    errors.extend(validate_safety_fields(row, schema_obj))
    errors.extend(validate_secret_redaction_fields(row, schema_obj))
    if schema_obj.schema_id == "unified_calendar_event_v1":
        errors.extend(calendar_specs.validate_contract(row))
    if schema_obj.schema_id == "operator_state_v1": errors.extend(operator_state_specs.validate_contract(row))
    if row.get("decision_model_version") not in (None, "") and schema_obj.schema_id in {"core_opportunity_v1", "integrated_radar_candidate_v1", "outcome_row_v1"}:
        errors.extend(decision_model_specs.validate_contract(row))
    return errors


def collect_schema_errors(row: Mapping[str, Any], schema: str | ArtifactSchema) -> list[str]:
    return validate_row_against_schema(row, schema)


def validate_required_fields(row: Mapping[str, Any], schema: ArtifactSchema) -> list[str]:
    return [f"missing_required_field:{field}" for field in schema.required_fields if not _required_field_present(row, field)]


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
        if field_name == "sent" and _truthy(value) and not _guarded_send_claim_is_valid(row, schema):
            out.append("unsafe_side_effect_flag:sent")
        if field_name == "research_only" and value is False:
            out.append("unsafe_research_only:false")
        if field_name in {"normal_rsi_signal_written", "triggered_fade_created", "trade_created", "paper_trade_created"} and _truthy(value):
            out.append(f"unsafe_side_effect_flag:{field_name}")
        if field_name in {
            "created_alert",
            "notification_send_enabled",
            "execution_enabled",
            "paper_trading_enabled",
            "normal_rsi_routing_enabled",
        } and _truthy(value):
            out.append(f"unsafe_side_effect_flag:{field_name}")
        if field_name in {
            "trades_created",
            "paper_trades_created",
            "strict_alerts_created",
            "telegram_sends",
            "normal_rsi_signal_rows_written",
            "triggered_fade_created",
        }:
            try:
                if int(value or 0) != 0:
                    out.append(f"unsafe_side_effect_count:{field_name}")
            except (TypeError, ValueError):
                out.append(f"invalid_safety_count:{field_name}")
        if field_name in {"auto_apply", "auto_apply_thresholds"} and _truthy(value):
            out.append("unsafe_auto_apply:true")
    return out


def validate_secret_redaction_fields(row: Mapping[str, Any], schema: ArtifactSchema) -> list[str]:
    out: list[str] = []
    for field_name, value in _iter_secret_like_fields(row, schema):
        if _secret_value_is_safe(value):
            continue
        out.append(f"secret_field_unredacted:{field_name}")
    return out


def stamp_artifact_row(
    row: Mapping[str, Any],
    *,
    schema_id: str | None = None,
    path: str | Path | None = None,
) -> dict[str, Any]:
    """Return a stamped row without overwriting legacy writer-specific versions."""
    out = dict(row)
    resolved_schema_id = (
        str(out.get("schema_id") or "").strip()
        or (schema_id or "")
        or (infer_schema_id_for_file(path) if path is not None else "")
        or ROW_TYPE_TO_SCHEMA_ID.get(str(out.get("row_type") or ""), "")
    )
    if resolved_schema_id and resolved_schema_id in SCHEMAS:
        out.setdefault("schema_id", resolved_schema_id)
        if out.get("schema_version") in (None, "", 1, "1"):
            out["schema_version"] = EVENT_ALPHA_ARTIFACT_SCHEMA_VERSION
        if resolved_schema_id == "coinalyze_request_ledger_v1":
            out.setdefault("row_type", "coinalyze_request_ledger")
        if resolved_schema_id in {"provider_readiness_v1", "provider_preflight_v1"} and "provider" not in out:
            provider_name = out.get("provider_name")
            if provider_name not in (None, ""):
                out["provider"] = provider_name
    return out


def stamp_artifact_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    schema_id: str | None = None,
    path: str | Path | None = None,
) -> list[dict[str, Any]]:
    return [stamp_artifact_row(row, schema_id=schema_id, path=path) for row in rows if isinstance(row, Mapping)]


def stamp_artifact_payload(
    payload: Mapping[str, Any],
    *,
    schema_id: str | None = None,
    path: str | Path | None = None,
) -> dict[str, Any]:
    """Stamp a JSON object artifact and known nested row lists."""
    resolved_schema_id = schema_id or (infer_schema_id_for_file(path) if path is not None else None)
    out = stamp_artifact_row(payload, schema_id=resolved_schema_id, path=path)
    for key in ("providers", "provider_rows", "rows", "categories", "sidecars"):
        nested = out.get(key)
        if isinstance(nested, list):
            out[key] = [
                stamp_artifact_row(item, schema_id=resolved_schema_id, path=path)
                if isinstance(item, Mapping)
                else item
                for item in nested
            ]
    return out


def validate_artifact_file(path: str | Path, schema_id: str | None = None) -> dict[str, Any]:
    file_path = Path(path)
    fallback = schema_id or infer_schema_id_for_file(file_path)
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
        "inferred_schema_id": infer_schema_id_for_file(file_path),
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
    declared.update(
        field
        for field in row
        if field.endswith("_path")
        or field.endswith("_paths")
        or field.endswith("_dir")
        or field.endswith("_dirs")
        or field.endswith("_relpath")
        or field.endswith("_abs_debug")
    )
    return tuple(sorted(declared))


def _required_field_present(row: Mapping[str, Any], field_name: str) -> bool:
    value = row.get(field_name)
    if field_name in {"items", "steps"}:
        return field_name in row and value is not None
    if field_name == "run_id" and str(row.get("row_type") or "") == "daily_burn_in" and value in (None, "", [], {}):
        value = row.get("started_at") or row.get("generated_at")
    if field_name == "provider" and value in (None, "", [], {}):
        value = row.get("provider_name")
    return value not in (None, "", [], {})


def _iter_secret_like_fields(row: Mapping[str, Any], schema: ArtifactSchema) -> Iterable[tuple[str, Any]]:
    declared = {field.casefold() for field in schema.secret_redaction_fields}
    for raw_key, value in row.items():
        key = str(raw_key)
        lower = key.casefold()
        if _secret_field_is_metadata(lower):
            continue
        if lower in declared or lower in SECRET_FIELD_NAMES or any(fragment in lower for fragment in SECRET_FIELD_FRAGMENTS):
            yield key, value


def _secret_field_is_metadata(lower_field_name: str) -> bool:
    if lower_field_name.endswith(("_redacted", "_safe", "_env", "_env_var", "_env_vars", "_required")):
        return True
    return lower_field_name in {
        "required_env_vars",
        "env_vars_required",
        "redacted_headers",
        "raw_payload_redacted",
        "token_redacted",
        "error_message_safe",
    }


def _secret_value_is_safe(value: Any) -> bool:
    if value in (None, "", False):
        return True
    if isinstance(value, Mapping):
        return all(_secret_value_is_safe(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return all(_secret_value_is_safe(item) for item in value)
    text = str(value).strip()
    if not text:
        return True
    lowered = text.casefold()
    if "redacted" in lowered or lowered in {"<hidden>", "<secret>", "<masked>", "****", "***"}:
        return True
    if set(text) <= {"*"}:
        return True
    return False


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


def _guarded_send_claim_is_valid(row: Mapping[str, Any], schema: ArtifactSchema) -> bool:
    """Return whether ``sent=true`` is a consistent guarded-delivery fact."""
    if not schema.allows_guarded_send or _truthy(row.get("no_send_rehearsal")):
        return False
    row_type = str(row.get("row_type") or "").strip()
    if row_type == "event_alpha_notification_delivery":
        status = str(row.get("status") or row.get("delivery_status") or "").strip()
        try:
            delivered = int(row.get("delivered_count") or 0)
        except (TypeError, ValueError):
            delivered = 0
        return (
            str(row.get("delivery_mode") or "").strip() == "live_send"
            and _truthy(row.get("send_guard_enabled"))
            and row.get("no_send_rehearsal") is False
            and status in {"sent", "delivered", "partial_delivered"}
            and delivered > 0
        )
    if row_type in {"event_alpha_run", "event_alpha_operator_state"}:
        try:
            delivered = int(row.get("send_items_delivered") or 0)
        except (TypeError, ValueError):
            delivered = 0
        return (
            _truthy(row.get("send_requested"))
            and _truthy(row.get("send_attempted"))
            and delivered > 0
        )
    return False
