"""Provider-lineage and targeted-market schema registrations.

The registry owns the schema model and factory. These helpers keep the
provider-specific declarations cohesive without importing the registry back
into this module or changing registration order.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


SchemaFactory = Callable[..., Any]


def provider_control_schemas(
    schema: SchemaFactory,
    *,
    common_safety: tuple[str, ...],
    common_lineage: tuple[str, ...],
) -> dict[str, Any]:
    """Return provider readiness, preflight, and request-ledger schemas."""
    return {
        "provider_readiness_v1": schema(
            "provider_readiness_v1",
            required=("provider", "configured", "live_call_allowed"),
            optional=(
                "schema_id", "schema_version", "row_type", "mode", "category",
                "provider_health_status", "provider_health_key", "required_env_vars",
                "env_vars_required", "request_ledger_path", "no_send_rehearsal",
                "fixture_parser_status", "source_packs_enabled", "activation_order",
                "configuration_scope", "fixture_input_configured", "fixture_env_vars",
                "live_transport_status", "live_authorization_status",
                "live_mapping_status", "live_rehearsal_eligible",
                "live_rehearsal_blockers",
                "skip_reason", "outputs", "fixture_artifacts", *common_safety,
            ),
            types={
                "provider": "str", "configured": "bool", "live_call_allowed": "bool",
                "fixture_input_configured": "bool", "live_rehearsal_eligible": "bool",
            },
            enums={
                "live_authorization_status": (
                    "absent", "missing_configuration", "not_defined",
                    "not_required", "present",
                ),
            },
            safety=("live_call_allowed", "no_send_rehearsal", *common_safety),
            paths=("request_ledger_path",),
            lineage=common_lineage,
        ),
        "provider_preflight_v1": schema(
            "provider_preflight_v1",
            required=("provider", "configured", "live_call_allowed"),
            optional=(
                "schema_id", "schema_version", "row_type", "category", "mode",
                "preflight_status", "status", "fixture_parser_status",
                "fixture_symbol_mapping_status", "request_ledger_path",
                "provider_health_status", "provider_health_key", "required_env_vars",
                "env_vars_required", "no_send_rehearsal", "supported_params",
                "supported_metrics", "supported_metric_status", "source_packs_enabled",
                "provider_generation_id", "run_id", "warnings", *common_safety,
            ),
            types={"provider": "str", "configured": "bool", "live_call_allowed": "bool"},
            safety=("live_call_allowed", "no_send_rehearsal", *common_safety),
            paths=("request_ledger_path",),
            lineage=common_lineage,
        ),
        "coinalyze_request_ledger_v1": schema(
            "coinalyze_request_ledger_v1",
            required=("provider", "endpoint", "success"),
            optional=(
                "schema_id", "schema_version", "row_type", "status", "status_code",
                "http_status", "sanitized_url", "method", "result_count",
                "error_class", "error_message_safe", "redacted_headers", "request_id",
                "request_budget_before", "request_budget_after", "live_call_allowed",
                "token_redacted", "no_send_rehearsal", "provider_generation_id",
                "run_id", "profile", "artifact_namespace",
            ),
            types={"provider": "str", "endpoint": "str", "success": "bool"},
            safety=("live_call_allowed", "no_send_rehearsal"),
            timestamps=("started_at", "finished_at"),
        ),
        "provider_request_ledger_v1": schema(
            "provider_request_ledger_v1",
            required=("provider", "endpoint", "success"),
            optional=(
                "schema_id", "schema_version", "row_type", "status", "status_code",
                "http_status", "sanitized_url", "method", "result_count", "content_length",
                "error_class", "error_message_safe", "redacted_headers", "request_id",
                "response_headers_safe", "response_body_summary_redacted",
                "response_body_truncated", "response_bytes_captured",
                "request_budget_before", "request_budget_after", "live_call_allowed",
                "token_redacted", "no_send_rehearsal", "supported_query_params",
                "unsupported_query_params", "query_params", "provider_generation_id",
                "run_id", "profile", "artifact_namespace",
            ),
            types={"provider": "str", "endpoint": "str", "success": "bool"},
            safety=("live_call_allowed", "no_send_rehearsal"),
            timestamps=("started_at", "finished_at"),
            lineage=common_lineage,
        ),
    }


def provider_market_schemas(
    schema: SchemaFactory,
    *,
    common_safety: tuple[str, ...],
    operation_safety: tuple[str, ...],
    common_lineage: tuple[str, ...],
    allowed_opportunity_types: tuple[str, ...],
) -> dict[str, Any]:
    """Return derivatives and targeted-market evidence schemas."""
    return {
        "derivatives_state_snapshot_v1": schema(
            "derivatives_state_snapshot_v1",
            required=("row_type", "symbol", "provider"),
            optional=(
                "schema_id", "schema_version", "coin_id", "canonical_asset_id",
                "market", "exchange", "open_interest", "open_interest_delta_1h",
                "open_interest_delta_4h", "open_interest_delta_24h", "funding_rate",
                "predicted_funding", "predicted_funding_rate", "funding_zscore",
                "basis", "basis_rate", "liquidation_imbalance", "long_short_ratio",
                "perp_volume", "spot_volume", "perp_spot_volume_ratio",
                "freshness_status", "derivatives_snapshot_freshness_status",
                "open_interest_freshness", "funding_freshness",
                "liquidation_freshness", "long_short_freshness", "basis_freshness",
                "open_interest_unit", "funding_rate_unit", "basis_unit",
                "liquidation_unit", "volume_unit", "supported_metric_status",
                "provider_generation_id", "provider_request_succeeded",
                "provider_source_artifact", "request_ledger_path",
                *common_safety,
            ),
            types={"row_type": "str", "symbol": "str", "provider": "str"},
            safety=common_safety,
            paths=("provider_source_artifact", "request_ledger_path"),
            timestamps=("observed_at",),
            lineage=common_lineage,
        ),
        "derivatives_crowding_candidate_v1": schema(
            "derivatives_crowding_candidate_v1",
            required=("row_type", "symbol", "crowding_class"),
            optional=(
                "schema_id", "schema_version", "candidate_id",
                "fade_review_candidate_id", "coin_id", "canonical_asset_id",
                "provider", "opportunity_type", "fade_readiness", "evidence",
                "warnings", "derivatives_state_snapshot", "supported_metric_status",
                "open_interest_unit", "funding_rate_unit", "basis_unit",
                "liquidation_unit", "volume_unit", "provider_generation_id",
                "provider_request_succeeded", "provider_source_artifact",
                "request_ledger_path", *common_safety,
            ),
            enums={"opportunity_type": allowed_opportunity_types},
            safety=common_safety,
            paths=("provider_source_artifact", "request_ledger_path"),
            timestamps=("observed_at",),
            lineage=common_lineage,
        ),
        "fade_review_candidate_v1": schema(
            "fade_review_candidate_v1",
            required=("row_type", "symbol", "opportunity_type"),
            optional=(
                "schema_id", "schema_version", "fade_review_candidate_id",
                "coin_id", "canonical_asset_id", "crowding_class", "fade_readiness",
                "evidence", "warnings", "market_state_class",
                "derivatives_state_snapshot", "supported_metric_status",
                "open_interest_unit", "funding_rate_unit", "basis_unit",
                "liquidation_unit", "volume_unit", "provider_generation_id",
                "provider_request_succeeded", "provider_source_artifact",
                "request_ledger_path", *common_safety,
            ),
            enums={"opportunity_type": allowed_opportunity_types},
            safety=common_safety,
            paths=("provider_source_artifact", "request_ledger_path"),
            timestamps=("observed_at",),
            lineage=common_lineage,
        ),
        "market_state_snapshot_v1": schema(
            "market_state_snapshot_v1",
            required=("row_type", "symbol"),
            optional=(
                "schema_id", "schema_version", "coin_id", "canonical_asset_id",
                "market_state_class", "state", "price", "return_24h_pct",
                "return_72h_pct", "volume_zscore_24h", "volume_mcap",
                "liquidity_tier", "relative_return_vs_btc", "relative_return_vs_eth",
                "market_history_observation_id", "market_feature_evidence",
                "shadow_temporal_surprise",
                "targeted_market_refresh_id", "targeted_market_refresh_attempted",
                "targeted_market_refresh_success", "market_refresh_provider",
                "market_refresh_artifact", "targeted_market_refresh_ledger_path",
                *operation_safety,
            ),
            types={
                "market_feature_evidence": "dict",
                "shadow_temporal_surprise": "dict",
            },
            safety=operation_safety,
            paths=("market_refresh_artifact", "targeted_market_refresh_ledger_path"),
            timestamps=("observed_at",),
            lineage=common_lineage,
        ),
        "targeted_market_refresh_ledger_v1": schema(
            "targeted_market_refresh_ledger_v1",
            required=(
                "row_type", "targeted_market_refresh_id", "canonical_asset_id",
                "status", "provider", "attempted", "research_only", "no_send_rehearsal",
            ),
            optional=(
                "schema_id", "schema_version", "refresh_id", "symbol", "coin_id",
                "candidate_family_ids", "priority_bucket", "priority_score", "reason",
                "started_at", "finished_at", "duration_seconds", "timeout_seconds",
                "error_class", "snapshot_id", *operation_safety,
            ),
            safety=operation_safety,
            timestamps=("started_at", "finished_at"),
            lineage=common_lineage,
        ),
        "targeted_market_refresh_report_v1": schema(
            "targeted_market_refresh_report_v1",
            required=(
                "row_type", "refresh_run_id", "provider", "selected_assets",
                "request_count", "research_only", "no_send_rehearsal",
            ),
            optional=(
                "schema_id", "schema_version", "attempted_assets", "refreshed_assets",
                "persisted_snapshot_rows",
                "timeout_seconds", "timed_out", "status_counts", "priority_bucket_counts",
                "ledger_path", "snapshot_path", "warnings", *operation_safety,
            ),
            safety=operation_safety,
            paths=("ledger_path", "snapshot_path"),
            lineage=common_lineage,
        ),
    }
