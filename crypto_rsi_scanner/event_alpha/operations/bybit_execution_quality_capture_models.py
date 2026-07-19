"""Transport models for immutable Bybit execution-quality captures."""

from __future__ import annotations

from dataclasses import dataclass

from .bybit_execution_quality import BybitPublicRequest
from .bybit_execution_quality_capture_errors import (
    BybitExecutionQualityCaptureError,
)
from .market_no_send_io import parse_json_object_bytes
from .market_no_send_models import MarketNoSendError


TRANSPORT_CONTRACT = "bybit_public_direct_http_v1"
LIVE_SUMMARY_KEYS = frozenset(
    {
        "all_execution_quality_fresh",
        "all_execution_quality_fresh_at_acquisition",
        "all_execution_quality_fresh_at_completion",
        "artifact_persisted", "campaign_attached", "category", "completed_at",
        "contract_version", "credentials_read", "eligible_instrument_count",
        "eligible_instruments", "evidence_authority_eligible", "execution_mode",
        "execution_quality_snapshot_count", "execution_quality_snapshots",
        "execution_quality_set_freshness_policy",
        "instrument_contract", "instrument_status", "no_send",
        "normal_rsi_signal_rows_written", "orders_available", "paper_trades_created",
        "private_data_read", "protocol_v2_evidence_eligible",
        "provider_call_attempted", "provider_call_authorized",
        "preflight_excluded_asset_count", "preflight_excluded_assets",
        "provider_query_asset_count", "provider_query_assets",
        "provider_request_bound", "provider_request_count",
        "provider_request_strategy", "instrument_catalog_request_count",
        "maximum_execution_quality_age_at_completion_seconds",
        "maximum_execution_quality_age_policy_seconds",
        "orderbook_request_count",
        "provider_request_succeeded", "quote_asset", "radar_assets",
        "recorded_403_policy", "redirects_followed", "requested_radar_asset_count",
        "research_only", "retries", "row_type", "source_authority",
        "source_base_url", "started_at", "status", "telegram_sends",
        "trades_created", "triggered_fade_created", "venue_id", "writes_performed",
    }
)
PERSISTED_SUMMARY_EXTRA_KEYS = frozenset(
    {
        "artifact_namespace", "capture_contract_version", "capture_id",
        "protocol_v2_annex_bound", "protocol_v2_input_quality_eligible",
    }
)
REQUEST_ROW_KEYS = frozenset(
    {
        "content_type", "duration_ms", "http_status", "raw_artifact", "request",
        "request_started_at", "request_url", "response_received_at", "sequence",
        "sha256", "size_bytes", "transport_contract",
    }
)


@dataclass(frozen=True)
class BybitCapturedJSONResponse:
    """One exact successful public response and its request timing."""

    request: BybitPublicRequest
    request_started_at: str
    response_received_at: str
    duration_ms: int
    response_url: str
    http_status: int
    content_type: str
    raw_bytes: bytes
    transport_contract: str = TRANSPORT_CONTRACT

    def payload(self) -> dict[str, object]:
        try:
            return parse_json_object_bytes(self.raw_bytes)
        except MarketNoSendError as exc:
            raise BybitExecutionQualityCaptureError(
                "captured_response_json_invalid"
            ) from exc


__all__ = (
    "LIVE_SUMMARY_KEYS",
    "PERSISTED_SUMMARY_EXTRA_KEYS",
    "REQUEST_ROW_KEYS",
    "TRANSPORT_CONTRACT",
    "BybitCapturedJSONResponse",
)
