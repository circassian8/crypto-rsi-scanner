"""Closed exact-response contract for Bybit derivatives context."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest

from crypto_rsi_scanner.event_alpha.operations.bybit_derivatives_context import (
    ACCOUNT_RATIO_PATH,
    FUNDING_HISTORY_PATH,
    OPEN_INTEREST_PATH,
    TICKERS_PATH,
)
from crypto_rsi_scanner.event_alpha.operations.bybit_derivatives_context_capture import (
    CONTRACT_VERSION,
    BybitDerivativesContextCaptureError,
    prepare_bybit_derivatives_context_capture,
)
from crypto_rsi_scanner.event_alpha.operations.bybit_derivatives_context_live import (
    LIVE_AUTH_ENV,
    _collect_authoritative_bybit_derivatives,
)
from crypto_rsi_scanner.event_alpha.operations.bybit_execution_quality import (
    PUBLIC_API_BASE,
    BybitPublicRequest,
    select_bybit_usdt_perpetual_instruments,
)
from crypto_rsi_scanner.event_alpha.operations.bybit_execution_quality_capture import (
    BybitCapturedJSONResponse,
)


ROOT = Path(__file__).resolve().parents[2]
EXECUTION_FIXTURES = ROOT / "fixtures" / "bybit_execution_quality"
DERIVATIVES_FIXTURES = ROOT / "fixtures" / "bybit_derivatives_context"
NOW = datetime(2026, 7, 18, 7, 44, tzinfo=timezone.utc)
AUTHORITY = {
    "artifact_namespace": "radar_market_no_send_live_exact",
    "run_id": "2026-07-18T07:40:00Z|no_key_live",
    "revision": 12,
    "operator_state_sha256": "a" * 64,
    "authority_checked_at": "2026-07-18T07:40:00Z",
}
PATH_FIXTURES = {
    TICKERS_PATH: "ticker_btcusdt.json",
    FUNDING_HISTORY_PATH: "funding_history_btcusdt.json",
    OPEN_INTEREST_PATH: "open_interest_btcusdt.json",
    ACCOUNT_RATIO_PATH: "account_ratio_btcusdt.json",
}


def _json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _instrument_values() -> list[dict[str, object]]:
    selected = select_bybit_usdt_perpetual_instruments(
        _json(EXECUTION_FIXTURES / "radar_assets.json"),
        _json(EXECUTION_FIXTURES / "instruments_info.json"),
    )
    return [row.to_dict() for row in selected if row.instrument_id == "BTCUSDT"]


def _capture() -> dict[str, object]:
    capture_id = "b" * 64
    return {
        "contract_version": "crypto_radar_bybit_execution_quality_capture_v1",
        "status": "complete",
        "capture_id": capture_id,
        "artifact_namespace": (
            "radar_bybit_execution_quality_20260718t074000000000z_"
            f"{capture_id[:12]}"
        ),
        "completed_at": "2026-07-18T07:40:00Z",
        "pointer_sha256": "c" * 64,
        "source_authority": dict(AUTHORITY),
        "eligible_instruments": _instrument_values(),
        "evidence_authority_eligible": True,
        "protocol_v2_input_quality_eligible": True,
        "protocol_v2_evidence_eligible": False,
        "protocol_v2_annex_bound": False,
        "campaign_attached": False,
        "pointer_validated": True,
        "research_only": True,
        "no_send": True,
        "orders": 0,
        "trades": 0,
        "paper_trades": 0,
        "normal_rsi_writes": 0,
        "event_alpha_triggered_fade": 0,
    }


def _resolver():
    snapshot = SimpleNamespace(
        artifact_namespace=AUTHORITY["artifact_namespace"],
        run_id=AUTHORITY["run_id"],
        revision=AUTHORITY["revision"],
        operator_state_sha256=AUTHORITY["operator_state_sha256"],
        generation_authority_checked_at=AUTHORITY["authority_checked_at"],
    )

    def resolve(_base: object, *, now: object) -> object:
        assert isinstance(now, datetime)
        return SimpleNamespace(snapshot=snapshot)

    return resolve


def _clock():
    ticks = iter(NOW + timedelta(milliseconds=100 * index) for index in range(50))
    return lambda: next(ticks)


def _captured_fetch(
    request: BybitPublicRequest,
    _timeout: float,
) -> BybitCapturedJSONResponse:
    payload = _json(DERIVATIVES_FIXTURES / PATH_FIXTURES[request.path])
    raw = (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")
    return BybitCapturedJSONResponse(
        request=request,
        request_started_at="2026-07-18T07:44:00.100000Z",
        response_received_at="2026-07-18T07:44:00.200000Z",
        duration_ms=100,
        response_url=f"{PUBLIC_API_BASE}{request.path}?{urlencode(request.query)}",
        http_status=200,
        content_type="application/json",
        raw_bytes=raw,
    )


def _evidence():
    return _collect_authoritative_bybit_derivatives(
        artifact_base_dir="unused",
        environ={LIVE_AUTH_ENV: "1"},
        now=_clock(),
        capture_loader=lambda _base: _capture(),
        resolver=_resolver(),
        fetch_json=_captured_fetch,
    )


def test_exact_bytes_rederive_one_closed_capture_without_io() -> None:
    summary, responses = _evidence()

    prepared = prepare_bybit_derivatives_context_capture(summary, responses)

    assert prepared["contract_version"] == CONTRACT_VERSION
    assert prepared["status"] == "prepared"
    assert prepared["request_count"] == 4
    assert prepared["context_count"] == 1
    assert prepared["all_context_fresh"] is True
    assert prepared["protocol_v2_input_quality_eligible"] is True
    assert prepared["protocol_v2_evidence_eligible"] is False
    assert prepared["immutable_capture_persisted"] is False
    assert prepared["provider_call_attempted"] is False
    assert prepared["writes_performed"] is False
    assert prepared["artifact_namespace"].startswith("radar_bybit_derivatives_")
    assert len(prepared["capture_id"]) == 64
    assert len(prepared["raw_artifacts"]) == 4


def test_capture_identity_is_deterministic_for_the_same_exact_evidence() -> None:
    summary, responses = _evidence()

    first = prepare_bybit_derivatives_context_capture(summary, responses)
    second = prepare_bybit_derivatives_context_capture(summary, responses)

    assert first == second


def test_mapping_only_diagnostic_responses_cannot_enter_capture() -> None:
    summary, _responses = _evidence()

    with pytest.raises(
        BybitDerivativesContextCaptureError,
        match="capture_count_contract_invalid",
    ):
        prepare_bybit_derivatives_context_capture(summary, ({},) * 4)  # type: ignore[arg-type]


def test_raw_response_drift_is_rederived_and_rejected() -> None:
    summary, responses = _evidence()
    changed = list(responses)
    payload = changed[0].payload()
    payload["result"]["list"][0]["markPrice"] = "70000"  # type: ignore[index]
    raw = (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")
    changed[0] = BybitCapturedJSONResponse(
        **{**changed[0].__dict__, "raw_bytes": raw}
    )

    with pytest.raises(
        BybitDerivativesContextCaptureError,
        match="derivatives_context_projection_drift",
    ):
        prepare_bybit_derivatives_context_capture(summary, changed)


def test_response_order_drift_is_rejected() -> None:
    summary, responses = _evidence()
    changed = list(responses)
    changed[0], changed[1] = changed[1], changed[0]

    with pytest.raises(
        BybitDerivativesContextCaptureError,
        match="derivatives_request_order_drift",
    ):
        prepare_bybit_derivatives_context_capture(summary, changed)


def test_projected_context_drift_is_rejected() -> None:
    summary, responses = _evidence()
    changed = deepcopy(summary)
    changed["contexts"][0]["open_interest_usdt"] += 1  # type: ignore[index]

    with pytest.raises(
        BybitDerivativesContextCaptureError,
        match="derivatives_context_projection_drift",
    ):
        prepare_bybit_derivatives_context_capture(changed, responses)


def test_request_timing_or_lineage_drift_is_rejected() -> None:
    summary, responses = _evidence()
    changed = deepcopy(summary)
    changed["request_timing"][0]["request_lineage_id"] = "changed"  # type: ignore[index]

    with pytest.raises(
        BybitDerivativesContextCaptureError,
        match="derivatives_context_projection_drift|request_timing_drift",
    ):
        prepare_bybit_derivatives_context_capture(changed, responses)


def test_summary_schema_is_closed() -> None:
    summary, responses = _evidence()
    changed = dict(summary)
    changed["untrusted_extension"] = True

    with pytest.raises(
        BybitDerivativesContextCaptureError,
        match="capture_summary_contract_invalid",
    ):
        prepare_bybit_derivatives_context_capture(changed, responses)


def test_source_capture_must_precede_derivatives_collection() -> None:
    summary, responses = _evidence()
    changed = deepcopy(summary)
    changed["source_execution_quality_capture"]["completed_at"] = (  # type: ignore[index]
        "2026-07-18T07:44:01Z"
    )

    with pytest.raises(
        BybitDerivativesContextCaptureError,
        match="source_execution_capture_after_derivatives_start",
    ):
        prepare_bybit_derivatives_context_capture(changed, responses)


def test_fraction_unit_error_in_raw_ticker_fails_closed() -> None:
    summary, responses = _evidence()
    changed = list(responses)
    payload = changed[0].payload()
    payload["result"]["list"][0]["price24hPcnt"] = "10.0"  # type: ignore[index]
    raw = (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")
    changed[0] = BybitCapturedJSONResponse(
        **{**changed[0].__dict__, "raw_bytes": raw}
    )

    with pytest.raises(
        BybitDerivativesContextCaptureError,
        match="derivatives_response_contract_invalid",
    ):
        prepare_bybit_derivatives_context_capture(summary, changed)
