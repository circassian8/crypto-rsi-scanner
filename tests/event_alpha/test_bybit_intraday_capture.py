"""Immutable direct Bybit 1h/4h capture regressions."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode
import zipfile

import pytest

from crypto_rsi_scanner.event_alpha.operations.bybit_execution_quality import (
    PUBLIC_API_BASE,
    BybitPublicRequest,
    select_bybit_usdt_perpetual_instruments,
)
from crypto_rsi_scanner.event_alpha.operations.bybit_execution_quality_capture import (
    BybitCapturedJSONResponse,
)
from crypto_rsi_scanner.event_alpha.operations.bybit_intraday_capture import (
    POINTER_FILENAME,
    BybitIntradayCaptureError,
    bybit_intraday_capture_status,
    load_latest_bybit_intraday_capture,
    persist_bybit_intraday_capture,
    validate_bybit_intraday_capture,
)
from crypto_rsi_scanner.event_alpha.operations.bybit_intraday_live import (
    LIVE_AUTH_ENV,
    collect_authoritative_bybit_intraday,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
EXECUTION_FIXTURES = REPO_ROOT / "fixtures" / "bybit_execution_quality"
INTRADAY_FIXTURES = REPO_ROOT / "fixtures" / "bybit_intraday"
NOW = datetime(2026, 7, 17, 12, 30, tzinfo=timezone.utc)
AUTHORITY = {
    "artifact_namespace": "radar_market_no_send_live_exact",
    "run_id": "2026-07-17T12:00:00Z|no_key_live",
    "revision": 12,
    "operator_state_sha256": "a" * 64,
    "authority_checked_at": "2026-07-17T12:00:00Z",
}


def _json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _instrument_values() -> list[dict[str, object]]:
    selected = select_bybit_usdt_perpetual_instruments(
        _json(EXECUTION_FIXTURES / "radar_assets.json"),
        _json(EXECUTION_FIXTURES / "instruments_info.json"),
    )
    return [
        row.to_dict() for row in selected if row.instrument_id == "BTCUSDT"
    ]


def _execution_capture(capture_id: str = "b" * 64) -> dict[str, object]:
    return {
        "contract_version": "crypto_radar_bybit_execution_quality_capture_v5",
        "status": "complete",
        "capture_id": capture_id,
        "artifact_namespace": (
            "radar_bybit_execution_quality_20260717t120001000000z_"
            f"{capture_id[:12]}"
        ),
        "completed_at": "2026-07-17T12:00:01Z",
        "pointer_sha256": "c" * 64,
        "source_authority": dict(AUTHORITY),
        "eligible_instruments": _instrument_values(),
        "request_count": 2,
        "observation_count": 1,
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


def _clock(*, completed_offset_ms: int = 1_000):
    values = [
        NOW,
        NOW + timedelta(milliseconds=100),
        NOW + timedelta(milliseconds=200),
        NOW + timedelta(milliseconds=300),
        NOW + timedelta(milliseconds=400),
        NOW + timedelta(milliseconds=completed_offset_ms),
    ]
    return lambda: values.pop(0)


def _captured_response(
    request: BybitPublicRequest,
    *,
    sequence: int,
) -> BybitCapturedJSONResponse:
    interval = dict(request.query)["interval"]
    raw = (INTRADAY_FIXTURES / f"klines_btcusdt_{interval}.json").read_bytes()
    started = NOW + timedelta(milliseconds=100 + sequence * 100)
    received = started + timedelta(milliseconds=25)
    return BybitCapturedJSONResponse(
        request=request,
        request_started_at=started.isoformat().replace("+00:00", "Z"),
        response_received_at=received.isoformat().replace("+00:00", "Z"),
        duration_ms=25,
        response_url=(
            f"{PUBLIC_API_BASE}{request.path}?{urlencode(request.query)}"
        ),
        http_status=200,
        content_type="application/json",
        raw_bytes=raw,
    )


def _collected(*, completed_offset_ms: int = 1_000):
    responses: list[BybitCapturedJSONResponse] = []

    def fetch(
        request: BybitPublicRequest,
        _timeout: float,
    ) -> BybitCapturedJSONResponse:
        response = _captured_response(request, sequence=len(responses))
        responses.append(response)
        return response

    summary = collect_authoritative_bybit_intraday(
        artifact_base_dir="unused",
        environ={LIVE_AUTH_ENV: "1"},
        now=_clock(completed_offset_ms=completed_offset_ms),
        capture_loader=lambda _base: _execution_capture(),
        resolver=_resolver(),
        fetch_json=fetch,
    )
    return summary, responses


def test_capture_seals_exact_raw_responses_and_rederives_every_bar(
    tmp_path: Path,
) -> None:
    summary, responses = _collected()

    result = persist_bybit_intraday_capture(
        tmp_path,
        summary=summary,
        responses=responses,
    )

    assert result["status"] == "complete"
    assert result["request_count"] == result["bar_count"] == 2
    assert result["all_bars_fresh"] is True
    assert result["all_bars_fresh_at_acquisition"] is True
    assert result["all_bars_fresh_at_completion"] is True
    assert result["intraday_set_freshness_policy"] == (
        "every_bar_fresh_at_capture_completion"
    )
    assert result["protocol_v2_input_quality_eligible"] is True
    assert result["protocol_v2_evidence_eligible"] is False
    assert result["protocol_v2_annex_bound"] is False
    assert result["campaign_attached"] is False
    assert result["pointer_validated"] is True
    assert result["orders"] == result["trades"] == 0
    assert result["source_execution_quality_capture"]["capture_id"] == "b" * 64
    assert result["source_execution_quality_capture"]["pointer_sha256"] == "c" * 64
    assert load_latest_bybit_intraday_capture(tmp_path) == result

    namespace = tmp_path / str(result["artifact_namespace"])
    raw_paths = sorted(namespace.glob("raw_*.json"))
    assert [path.name for path in raw_paths] == [
        "raw_001_kline_60_BTCUSDT.json",
        "raw_002_kline_240_BTCUSDT.json",
    ]
    manifest = json.loads((namespace / "capture_manifest.json").read_text())
    descriptors = {row["name"]: row for row in manifest["artifacts"]}
    for path in raw_paths:
        assert descriptors[path.name]["sha256"] == hashlib.sha256(
            path.read_bytes()
        ).hexdigest()


def test_summary_or_response_projection_drift_is_rejected_before_writes(
    tmp_path: Path,
) -> None:
    summary, responses = _collected()
    drifted = deepcopy(summary)
    drifted["bars"][0]["close_price"] = 1.0

    with pytest.raises(BybitIntradayCaptureError, match="projection_drift"):
        persist_bybit_intraday_capture(
            tmp_path,
            summary=drifted,
            responses=responses,
        )
    with pytest.raises(BybitIntradayCaptureError, match="request_order_drift"):
        persist_bybit_intraday_capture(
            tmp_path,
            summary=summary,
            responses=list(reversed(responses)),
        )
    freshness_drift = deepcopy(summary)
    freshness_drift[
        "maximum_provider_response_age_at_completion_seconds"
    ] += 1.0
    with pytest.raises(BybitIntradayCaptureError, match="freshness_summary_mismatch"):
        persist_bybit_intraday_capture(
            tmp_path,
            summary=freshness_drift,
            responses=responses,
        )

    assert not (tmp_path / POINTER_FILENAME).exists()
    assert list(tmp_path.glob("radar_bybit_intraday_*")) == []


def test_capture_preserves_aged_set_but_blocks_input_quality(
    tmp_path: Path,
) -> None:
    summary, responses = _collected(completed_offset_ms=20_000)

    result = persist_bybit_intraday_capture(
        tmp_path,
        summary=summary,
        responses=responses,
    )

    assert result["all_bars_fresh_at_acquisition"] is True
    assert result["all_bars_fresh_at_completion"] is False
    assert result["all_bars_fresh"] is False
    assert result["protocol_v2_input_quality_eligible"] is False
    assert result[
        "maximum_provider_response_age_at_completion_seconds"
    ] == 19.9
    assert result["pointer_validated"] is True


def test_source_instrument_and_capture_window_drift_fail_before_writes(
    tmp_path: Path,
) -> None:
    summary, responses = _collected()
    wrong_instruments = deepcopy(summary)
    wrong_instruments["source_execution_quality_capture"][
        "eligible_instruments"
    ] = []
    with pytest.raises(BybitIntradayCaptureError, match="instrument_set_mismatch"):
        persist_bybit_intraday_capture(
            tmp_path,
            summary=wrong_instruments,
            responses=responses,
        )

    future_source = deepcopy(summary)
    future_source["source_execution_quality_capture"]["completed_at"] = (
        "2026-07-17T12:31:00Z"
    )
    with pytest.raises(BybitIntradayCaptureError, match="after_intraday_start"):
        persist_bybit_intraday_capture(
            tmp_path,
            summary=future_source,
            responses=responses,
        )

    short_window = deepcopy(summary)
    short_window["completed_at"] = "2026-07-17T12:30:00.200000Z"
    with pytest.raises(BybitIntradayCaptureError, match="outside_capture_window"):
        persist_bybit_intraday_capture(
            tmp_path,
            summary=short_window,
            responses=responses,
        )

    overlapping_summary = deepcopy(summary)
    overlapping_summary["bars"][1]["request_started_at"] = (
        "2026-07-17T12:30:00.120000Z"
    )
    overlapping_responses = list(responses)
    overlapping_responses[1] = replace(
        overlapping_responses[1],
        request_started_at="2026-07-17T12:30:00.120000Z",
    )
    with pytest.raises(BybitIntradayCaptureError, match="outside_capture_window"):
        persist_bybit_intraday_capture(
            tmp_path,
            summary=overlapping_summary,
            responses=overlapping_responses,
        )

    assert not (tmp_path / POINTER_FILENAME).exists()


def test_latest_capture_fails_closed_after_raw_or_pointer_tamper(
    tmp_path: Path,
) -> None:
    summary, responses = _collected()
    result = persist_bybit_intraday_capture(
        tmp_path,
        summary=summary,
        responses=responses,
    )
    namespace = tmp_path / str(result["artifact_namespace"])
    raw_path = next(namespace.glob("raw_001_*.json"))
    raw_path.write_bytes(b'{"retCode":0,"result":{}}\n')

    status = bybit_intraday_capture_status(tmp_path)
    assert status["status"] == "unavailable"
    assert status["protocol_v2_input_quality_eligible"] is False
    assert status["protocol_v2_evidence_eligible"] is False
    assert status["provider_call_attempted"] is False

    pointer = json.loads((tmp_path / POINTER_FILENAME).read_text())
    pointer["capture_id"] = "d" * 64
    (tmp_path / POINTER_FILENAME).write_text(json.dumps(pointer))
    status = bybit_intraday_capture_status(tmp_path)
    assert status["status"] == "unavailable"
    assert status["pointer_sha256"] is None


def test_capture_rejects_symlinked_artifact_and_pointer_rollback(
    tmp_path: Path,
) -> None:
    summary, responses = _collected(completed_offset_ms=1_000)
    result = persist_bybit_intraday_capture(
        tmp_path,
        summary=summary,
        responses=responses,
    )
    namespace = tmp_path / str(result["artifact_namespace"])
    bars_path = namespace / "intraday_bars.json"
    backup = namespace / "intraday_bars.backup"
    bars_path.rename(backup)
    bars_path.symlink_to(backup.name)

    with pytest.raises(BybitIntradayCaptureError, match="artifact_unreadable"):
        validate_bybit_intraday_capture(
            tmp_path,
            namespace=str(result["artifact_namespace"]),
        )

    bars_path.unlink()
    backup.rename(bars_path)
    earlier, earlier_responses = _collected(completed_offset_ms=500)
    with pytest.raises(BybitIntradayCaptureError, match="rollback_rejected"):
        persist_bybit_intraday_capture(
            tmp_path,
            summary=earlier,
            responses=earlier_responses,
        )


def test_unmanifested_namespace_content_fails_closed(tmp_path: Path) -> None:
    summary, responses = _collected()
    result = persist_bybit_intraday_capture(
        tmp_path,
        summary=summary,
        responses=responses,
    )
    namespace = tmp_path / str(result["artifact_namespace"])
    (namespace / "unmanifested.json").write_text("{}\n", encoding="utf-8")

    status = bybit_intraday_capture_status(tmp_path)

    assert status["status"] == "unavailable"
    assert status["reason"] == "capture_unmanifested_artifact"
    assert status["protocol_v2_evidence_eligible"] is False


def test_status_without_pointer_is_bounded_read_only_and_unavailable(
    tmp_path: Path,
) -> None:
    before = sorted(path.name for path in tmp_path.iterdir())
    status = bybit_intraday_capture_status(tmp_path)
    after = sorted(path.name for path in tmp_path.iterdir())

    assert status["status"] == "unavailable"
    assert status["reason"] == "capture_pointer_missing"
    assert status["provider_call_attempted"] is False
    assert status["writes_performed"] is False
    assert before == after == []


def test_project_review_export_selects_and_revalidates_latest_intraday_capture(
    tmp_path: Path,
) -> None:
    root = tmp_path / "tree"
    base = root / "event_fade_cache"
    base.mkdir(parents=True)
    (root / "Makefile").write_text("verify:\n\t@true\n", encoding="utf-8")
    policy_source = REPO_ROOT / "research/DECISION_RADAR_PROJECT_ARTIFACT_POLICY.json"
    policy_target = root / "research/DECISION_RADAR_PROJECT_ARTIFACT_POLICY.json"
    policy_target.parent.mkdir(parents=True)
    policy_target.write_bytes(policy_source.read_bytes())
    summary, responses = _collected()
    capture = persist_bybit_intraday_capture(
        base,
        summary=summary,
        responses=responses,
    )
    spec = importlib.util.spec_from_file_location(
        "bybit_intraday_project_export",
        REPO_ROOT / "scripts/export_source_with_artifacts.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = root / "review.zip"

    assert module.main(root=root, out=output) == 0

    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        manifest = json.loads(
            archive.read("event_fade_cache/PROJECT_ARTIFACT_EXPORT_MANIFEST.json")
        )
    prefix = f"event_fade_cache/{capture['artifact_namespace']}/"
    assert "event_fade_cache/radar_bybit_intraday_latest.json" in names
    assert f"{prefix}capture_completion_receipt.json" in names
    assert f"{prefix}capture_manifest.json" in names
    assert f"{prefix}raw_001_kline_60_BTCUSDT.json" in names
    selected = {
        row["kind"]: row for row in manifest["selector_results"]
    }["latest_bybit_intraday_namespace"]
    assert selected["artifact_namespace"] == capture["artifact_namespace"]
    assert selected["capture_id"] == capture["capture_id"]
    assert selected["source_execution_quality_capture_id"] == "b" * 64
    assert selected["all_bars_fresh"] is True
    assert selected["all_bars_fresh_at_acquisition"] is True
    assert selected["all_bars_fresh_at_completion"] is True
    assert selected["intraday_set_freshness_policy"] == (
        "every_bar_fresh_at_capture_completion"
    )
    assert selected["protocol_v2_input_quality_eligible"] is True
    assert selected["protocol_v2_evidence_eligible"] is False
    assert selected["protocol_v2_annex_bound"] is False
