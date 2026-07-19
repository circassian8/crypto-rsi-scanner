"""Closed publication/projection checks for immutable Bybit intraday captures."""

from __future__ import annotations

from typing import Mapping, Sequence

from .bybit_execution_quality_capture import BybitCapturedJSONResponse
from .bybit_intraday_capture import (
    CONTRACT_VERSION,
    MANIFEST_FILENAME,
    MAX_RESPONSES,
    MAX_RESPONSE_BYTES,
    RECEIPT_FILENAME,
    BybitIntradayCaptureError,
    _SHA256_RE,
    _fingerprint,
    _pretty_bytes,
    _validate_common,
    validate_bybit_intraday_pointer_bytes,
)
from .bybit_intraday_set_freshness import (
    common_freshness_matches,
    common_freshness_values,
    freshness_contract_valid,
)


def _validate_publication_objects(
    *,
    namespace: str,
    capture_id: object,
    receipt: Mapping[str, object],
    receipt_raw: bytes,
    manifest: Mapping[str, object],
    manifest_raw: bytes,
    pointer: Mapping[str, object] | None = None,
) -> None:
    common_keys = {
        "all_bars_fresh", "all_bars_fresh_at_acquisition",
        "all_bars_fresh_at_completion", "artifact_namespace", "bar_count",
        "bar_recency_policy", "campaign_attached", "capture_id",
        "completed_at", "contract_version", "intraday_set_freshness_policy",
        "maximum_provider_response_age_at_completion_seconds",
        "maximum_provider_response_age_policy_seconds",
        "minimum_bar_recency_remaining_at_completion_seconds",
        "protocol_v2_annex_bound", "protocol_v2_evidence_eligible",
        "protocol_v2_input_quality_eligible", "request_count", "research_only",
        "source_execution_quality_capture_id",
        "source_execution_quality_pointer_sha256",
    }
    manifest_keys = common_keys | {
        "artifacts", "event_alpha_triggered_fade", "execution_mode", "no_send",
        "normal_rsi_writes", "orders", "paper_trades", "quote_asset",
        "schema_id", "schema_version", "started_at", "trades", "venue_id",
    }
    receipt_keys = common_keys | {
        "manifest", "schema_id", "schema_version", "status",
    }
    if (
        set(manifest) != manifest_keys
        or set(receipt) != receipt_keys
        or not _SHA256_RE.fullmatch(str(capture_id or ""))
        or not _SHA256_RE.fullmatch(
            str(receipt.get("source_execution_quality_capture_id") or "")
        )
        or not _SHA256_RE.fullmatch(
            str(receipt.get("source_execution_quality_pointer_sha256") or "")
        )
        or type(receipt.get("request_count")) is not int
        or not 1 <= receipt["request_count"] <= MAX_RESPONSES
        or receipt.get("bar_count") != receipt.get("request_count")
        or not freshness_contract_valid(receipt)
        or not common_freshness_matches(manifest, receipt)
        or manifest.get("venue_id") != "bybit"
        or manifest.get("execution_mode") != "perpetual"
        or manifest.get("quote_asset") != "USDT"
        or manifest.get("no_send") is not True
        or any(
            manifest.get(field) != 0
            for field in (
                "orders", "trades", "paper_trades", "normal_rsi_writes",
                "event_alpha_triggered_fade",
            )
        )
    ):
        raise BybitIntradayCaptureError("capture_publication_contract_invalid")
    _validate_common(
        namespace,
        receipt,
        schema_id="decision_radar.bybit_intraday_completion_receipt",
        capture_id=capture_id,
    )
    _validate_common(
        namespace,
        manifest,
        schema_id="decision_radar.bybit_intraday_capture_manifest",
        capture_id=capture_id,
    )
    if (
        receipt.get("status") != "complete"
        or receipt.get("manifest")
        != {"name": MANIFEST_FILENAME, **_fingerprint(manifest_raw)}
    ):
        raise BybitIntradayCaptureError("capture_receipt_contract_invalid")
    if pointer is not None:
        validated_pointer = validate_bybit_intraday_pointer_bytes(
            _pretty_bytes(dict(pointer))
        )
        if validated_pointer != pointer:
            raise BybitIntradayCaptureError("capture_pointer_contract_invalid")
        _validate_common(
            namespace,
            pointer,
            schema_id="decision_radar.bybit_intraday_latest_pointer",
            capture_id=capture_id,
        )
        if (
            pointer.get("status") != "complete"
            or pointer.get("receipt")
            != {"name": RECEIPT_FILENAME, **_fingerprint(receipt_raw)}
        ):
            raise BybitIntradayCaptureError("capture_pointer_fingerprint_invalid")


def _validate_projection_objects(
    *,
    capture_id: object,
    artifacts: Mapping[str, bytes],
    responses: Sequence[BybitCapturedJSONResponse],
    source: Mapping[str, object],
    instruments: Mapping[str, object],
    bars: Mapping[str, object],
    prepared: Mapping[str, object],
) -> None:
    if (
        len(artifacts) != len(responses) + 5
        or source.get("capture_id") != capture_id
        or set(source) != {
            "schema_id", "schema_version", "capture_id",
            "source_execution_quality_capture", "research_only",
        }
        or source.get("schema_id")
        != "decision_radar.bybit_intraday_source_execution_capture"
        or source.get("schema_version") != 1
        or source.get("source_execution_quality_capture")
        != prepared["source_execution_quality_capture"]
        or source.get("research_only") is not True
        or set(instruments)
        != {
            "capture_id", "instrument_count", "instruments", "research_only",
            "schema_id", "schema_version",
        }
        or instruments.get("schema_id")
        != "decision_radar.bybit_intraday_instruments"
        or instruments.get("schema_version") != 1
        or instruments.get("capture_id") != capture_id
        or instruments.get("instrument_count") != len(prepared["eligible_instruments"])
        or instruments.get("instruments") != prepared["eligible_instruments"]
        or instruments.get("research_only") is not True
        or set(bars)
        != {
            "all_bars_fresh", "all_bars_fresh_at_acquisition",
            "all_bars_fresh_at_completion", "bar_count",
            "bar_recency_policy", "bars", "capture_id",
            "intraday_set_freshness_policy",
            "maximum_provider_response_age_at_completion_seconds",
            "maximum_provider_response_age_policy_seconds",
            "minimum_bar_recency_remaining_at_completion_seconds",
            "protocol_v2_input_quality_eligible", "research_only",
            "schema_id", "schema_version",
        }
        or bars.get("schema_id") != "decision_radar.bybit_intraday_bars"
        or bars.get("schema_version") != 1
        or bars.get("capture_id") != capture_id
        or bars.get("bar_count") != len(prepared["bars"])
        or bars.get("bars") != prepared["bars"]
        or not common_freshness_matches(bars, prepared)
        or bars.get("research_only") is not True
    ):
        raise BybitIntradayCaptureError("capture_projection_drift")


def _validated_capture_result(
    *,
    namespace: str,
    capture_id: object,
    prepared: Mapping[str, object],
    request_count: int,
    pointer_validated: bool,
) -> dict[str, object]:
    return {
        "contract_version": CONTRACT_VERSION,
        "status": "complete",
        "capture_id": capture_id,
        "artifact_namespace": namespace,
        "completed_at": prepared["completed_at"],
        "source_execution_quality_capture": prepared[
            "source_execution_quality_capture"
        ],
        "eligible_instruments": prepared["eligible_instruments"],
        "bars": prepared["bars"],
        "request_count": request_count,
        "bar_count": len(prepared["bars"]),
        **common_freshness_values(prepared),
        "protocol_v2_evidence_eligible": False,
        "protocol_v2_annex_bound": False,
        "campaign_attached": False,
        "pointer_validated": pointer_validated,
        "research_only": True,
        "no_send": True,
        "orders": 0,
        "trades": 0,
        "paper_trades": 0,
        "normal_rsi_writes": 0,
        "event_alpha_triggered_fade": 0,
    }


__all__ = ()
