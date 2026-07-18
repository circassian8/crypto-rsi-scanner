"""Read-only latest-status surface for immutable Bybit derivatives captures."""

from __future__ import annotations

from pathlib import Path

from .bybit_derivatives_context_capture import (
    CONTRACT_VERSION,
    POINTER_FILENAME,
    BybitDerivativesContextCaptureError,
    _sha256,
    validate_bybit_derivatives_context_capture,
    validate_bybit_derivatives_context_pointer_bytes,
)
from .market_no_send_io import read_regular_bytes
from .market_no_send_models import MarketNoSendError


def load_latest_bybit_derivatives_context_capture(
    artifact_base_dir: str | Path,
) -> dict[str, object]:
    base = Path(artifact_base_dir).expanduser().absolute()
    try:
        raw = read_regular_bytes(base / POINTER_FILENAME, missing_ok=True)
    except MarketNoSendError as exc:
        raise BybitDerivativesContextCaptureError(
            "capture_pointer_unreadable"
        ) from exc
    if raw is None:
        raise BybitDerivativesContextCaptureError("capture_pointer_missing")
    pointer = validate_bybit_derivatives_context_pointer_bytes(raw)
    validated = validate_bybit_derivatives_context_capture(
        base,
        namespace=str(pointer["artifact_namespace"]),
        pointer=pointer,
    )
    try:
        final_raw = read_regular_bytes(base / POINTER_FILENAME)
    except MarketNoSendError as exc:
        raise BybitDerivativesContextCaptureError(
            "capture_pointer_unreadable"
        ) from exc
    if final_raw != raw:
        raise BybitDerivativesContextCaptureError(
            "capture_pointer_changed_during_read"
        )
    validated["pointer_sha256"] = _sha256(raw)
    return validated


def bybit_derivatives_context_capture_status(
    artifact_base_dir: str | Path,
) -> dict[str, object]:
    try:
        return load_latest_bybit_derivatives_context_capture(artifact_base_dir)
    except BybitDerivativesContextCaptureError as exc:
        return {
            "contract_version": CONTRACT_VERSION,
            "status": "unavailable",
            "reason": str(exc),
            "source_execution_quality_capture": None,
            "eligible_instruments": [],
            "contexts": [],
            "request_count": 0,
            "context_count": 0,
            "protocol_v2_input_quality_eligible": False,
            "protocol_v2_evidence_eligible": False,
            "protocol_v2_annex_bound": False,
            "campaign_attached": False,
            "context_only": True,
            "directional_authority": False,
            "decision_policy_applied": False,
            "provider_call_attempted": False,
            "writes_performed": False,
            "research_only": True,
            "no_send": True,
            "orders": 0,
            "trades": 0,
            "paper_trades": 0,
            "normal_rsi_writes": 0,
            "event_alpha_triggered_fade": 0,
            "pointer_sha256": None,
        }


__all__ = (
    "bybit_derivatives_context_capture_status",
    "load_latest_bybit_derivatives_context_capture",
)
