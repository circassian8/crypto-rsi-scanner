"""Immutable Bybit execution-quality capture regressions."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
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
)
from crypto_rsi_scanner.event_alpha.operations.bybit_execution_quality_capture import (
    POINTER_FILENAME,
    BybitCapturedJSONResponse,
    BybitExecutionQualityCaptureError,
    bybit_execution_quality_capture_status,
    load_latest_bybit_execution_quality_capture,
    persist_bybit_execution_quality_capture,
    validate_bybit_execution_quality_capture,
)
from crypto_rsi_scanner.event_alpha.operations.bybit_execution_quality_live import (
    LIVE_AUTH_ENV,
    BybitExecutionQualityLiveError,
    _collect_authoritative_bybit_execution_quality,
    capture_authoritative_bybit_execution_quality,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "fixtures/bybit_execution_quality"
NOW = datetime(2026, 7, 17, 12, 0, 1, tzinfo=timezone.utc)


def _fixture(name: str) -> object:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _observation(
    canonical_asset_id: str,
    symbol: str,
    liquidity_usd: float,
) -> dict[str, object]:
    return {
        "canonical_asset_id": canonical_asset_id,
        "symbol": symbol,
        "liquidity_usd": liquidity_usd,
        "data_mode": "live",
        "candidate_source_mode": "live_no_send",
        "decision_radar_campaign_counted": True,
        "provenance_contract_valid": True,
        "research_only": True,
        "no_send": True,
        "freshness_status": "fresh",
    }


def _resolver(
    observations: tuple[dict[str, object], ...],
    *,
    expected_now: datetime = NOW,
):
    snapshot = SimpleNamespace(
        artifact_namespace="radar_market_no_send_live_exact",
        run_id="2026-07-17T12:00:00Z|no_key_live",
        revision=12,
        operator_state_sha256="a" * 64,
        generation_authority_checked_at="2026-07-17T12:00:00Z",
        current_market_observations=observations,
    )

    def resolve(_base: object, *, now: object) -> object:
        assert now == expected_now
        return SimpleNamespace(snapshot=snapshot)

    return resolve


def _instrument_payload(symbol: str) -> dict[str, object]:
    payload = deepcopy(_fixture("instruments_info.json"))
    payload["result"]["list"] = [
        row for row in payload["result"]["list"] if row["symbol"] == symbol
    ]
    return payload


def _orderbook_payload(symbol: str, price: float) -> dict[str, object]:
    payload = deepcopy(_fixture("orderbook_btcusdt.json"))
    payload["result"]["s"] = symbol
    payload["result"]["b"] = [
        [f"{price:.2f}", "10"],
        [f"{price - 0.05:.2f}", "20"],
        [f"{price - 0.10:.2f}", "50"],
    ]
    payload["result"]["a"] = [
        [f"{price + 0.10:.2f}", "10"],
        [f"{price + 0.15:.2f}", "20"],
        [f"{price + 0.20:.2f}", "50"],
    ]
    return payload


def _captured(
    request: BybitPublicRequest,
    payload: dict[str, object],
) -> BybitCapturedJSONResponse:
    raw = (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")
    return BybitCapturedJSONResponse(
        request=request,
        request_started_at="2026-07-17T12:00:00.900000Z",
        response_received_at="2026-07-17T12:00:00.950000Z",
        duration_ms=50,
        response_url=f"{PUBLIC_API_BASE}{request.path}?{urlencode(request.query)}",
        http_status=200,
        content_type="application/json",
        raw_bytes=raw,
    )


def _fetch(request: BybitPublicRequest, _timeout: float) -> BybitCapturedJSONResponse:
    query = dict(request.query)
    if request.path.endswith("instruments-info"):
        payload = _instrument_payload(query["symbol"])
    else:
        prices = {"BTCUSDT": 100.0, "ETHUSDT": 50.0}
        payload = _orderbook_payload(query["symbol"], prices[query["symbol"]])
    return _captured(request, payload)


def test_capture_seals_exact_raw_responses_and_validates_latest_pointer(
    tmp_path: Path,
) -> None:
    observations = (
        _observation("ethereum", "ETH", 2_000.0),
        _observation("pepe", "PEPE", 1_000.0),
        _observation("bitcoin", "BTC", 3_000.0),
        _observation("figure-heloc", "FIGR_HELOC", 1_500.0),
    )

    result = capture_authoritative_bybit_execution_quality(
        artifact_base_dir=tmp_path,
        environ={LIVE_AUTH_ENV: "1"},
        now=lambda: NOW,
        resolver=_resolver(observations),
        fetch_json=_fetch,
    )

    assert result["status"] == "complete"
    assert result["request_count"] == 5
    assert result["observation_count"] == 2
    assert result["evidence_authority_eligible"] is True
    assert result["protocol_v2_input_quality_eligible"] is True
    assert result["protocol_v2_evidence_eligible"] is False
    assert result["protocol_v2_annex_bound"] is False
    assert result["campaign_attached"] is False
    assert result["pointer_validated"] is True
    assert result["orders"] == result["trades"] == 0
    assert (tmp_path / POINTER_FILENAME).is_file()

    namespace = tmp_path / result["artifact_namespace"]
    raw_paths = sorted(namespace.glob("raw_*.json"))
    assert len(raw_paths) == 5
    assert all(path.stat().st_size > 0 for path in raw_paths)
    assert load_latest_bybit_execution_quality_capture(tmp_path) == result

    universe = json.loads((namespace / "radar_universe.json").read_text())
    assert universe["schema_version"] == 2
    assert universe["asset_count"] == 4
    assert universe["provider_query_asset_count"] == 3
    assert universe["preflight_excluded_asset_count"] == 1
    assert universe["preflight_excluded_assets"] == [{
        "canonical_asset_id": "figure-heloc",
        "symbol": "FIGR_HELOC",
        "liquidity_rank": 3,
        "liquidity_usd": 1_500.0,
        "reason_code": "radar_symbol_not_bybit_base_contract_shape",
    }]
    assert universe["identity_join_basis"] == (
        "exact_radar_symbol_equals_bybit_base_coin_candidate_join"
    )
    assert universe["canonical_identity_status"] == (
        "pending_protocol_v2_annex_human_confirmation"
    )

    manifest = json.loads((namespace / "capture_manifest.json").read_text())
    descriptors = {row["name"]: row for row in manifest["artifacts"]}
    for path in raw_paths:
        assert descriptors[path.name]["sha256"] == hashlib.sha256(
            path.read_bytes()
        ).hexdigest()


def test_capture_rejects_mapping_only_test_transport_before_writes(
    tmp_path: Path,
) -> None:
    observations = (_observation("bitcoin", "BTC", 3_000.0),)

    def mapping_fetch(request: BybitPublicRequest, _timeout: float):
        query = dict(request.query)
        if request.path.endswith("instruments-info"):
            return _instrument_payload(query["symbol"])
        return _orderbook_payload(query["symbol"], 100.0)

    with pytest.raises(
        BybitExecutionQualityLiveError,
        match="exact_provider_response_capture_unavailable",
    ):
        capture_authoritative_bybit_execution_quality(
            artifact_base_dir=tmp_path,
            environ={LIVE_AUTH_ENV: "1"},
            now=lambda: NOW,
            resolver=_resolver(observations),
            fetch_json=mapping_fetch,
        )

    assert not (tmp_path / POINTER_FILENAME).exists()
    assert list(tmp_path.glob("radar_bybit_execution_quality_*")) == []


def test_capture_rejects_unallowlisted_summary_fields_before_writes(
    tmp_path: Path,
) -> None:
    observations = (_observation("bitcoin", "BTC", 3_000.0),)
    summary, responses = _collect_authoritative_bybit_execution_quality(
        artifact_base_dir=tmp_path,
        environ={LIVE_AUTH_ENV: "1"},
        now=lambda: NOW,
        resolver=_resolver(observations),
        fetch_json=_fetch,
    )
    summary["unexpected_provider_payload"] = "must-not-enter-artifacts"

    with pytest.raises(
        BybitExecutionQualityCaptureError,
        match="capture_summary_contract_invalid",
    ):
        persist_bybit_execution_quality_capture(
            tmp_path,
            summary=summary,
            responses=responses,
        )

    assert not (tmp_path / POINTER_FILENAME).exists()
    assert list(tmp_path.glob("radar_bybit_execution_quality_*")) == []


def test_latest_capture_fails_closed_after_raw_response_drift(tmp_path: Path) -> None:
    observations = (_observation("bitcoin", "BTC", 3_000.0),)
    result = capture_authoritative_bybit_execution_quality(
        artifact_base_dir=tmp_path,
        environ={LIVE_AUTH_ENV: "1"},
        now=lambda: NOW,
        resolver=_resolver(observations),
        fetch_json=_fetch,
    )
    namespace = tmp_path / result["artifact_namespace"]
    raw_path = next(namespace.glob("raw_*_orderbook_*.json"))
    raw_path.write_bytes(b'{"retCode":0,"result":{}}\n')

    status = bybit_execution_quality_capture_status(tmp_path)

    assert status["status"] == "unavailable"
    assert status["evidence_authority_eligible"] is False
    assert status["protocol_v2_evidence_eligible"] is False
    assert status["protocol_v2_input_quality_eligible"] is False
    assert status["protocol_v2_annex_bound"] is False
    assert status["provider_call_attempted"] is False


def test_malformed_request_index_fails_closed_with_a_capture_error(
    tmp_path: Path,
) -> None:
    observations = (_observation("bitcoin", "BTC", 3_000.0),)
    result = capture_authoritative_bybit_execution_quality(
        artifact_base_dir=tmp_path,
        environ={LIVE_AUTH_ENV: "1"},
        now=lambda: NOW,
        resolver=_resolver(observations),
        fetch_json=_fetch,
    )
    namespace = tmp_path / result["artifact_namespace"]
    request_path = namespace / "request_index.json"
    manifest_path = namespace / "capture_manifest.json"
    receipt_path = namespace / "capture_completion_receipt.json"
    request_index = json.loads(request_path.read_text())
    request_index["requests"][0]["duration_ms"] = None
    request_path.write_text(
        json.dumps(request_index, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = json.loads(manifest_path.read_text())
    request_raw = request_path.read_bytes()
    descriptor = next(
        row for row in manifest["artifacts"] if row["name"] == request_path.name
    )
    descriptor["sha256"] = hashlib.sha256(request_raw).hexdigest()
    descriptor["size_bytes"] = len(request_raw)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    receipt = json.loads(receipt_path.read_text())
    manifest_raw = manifest_path.read_bytes()
    receipt["manifest"]["sha256"] = hashlib.sha256(manifest_raw).hexdigest()
    receipt["manifest"]["size_bytes"] = len(manifest_raw)
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        BybitExecutionQualityCaptureError,
        match="capture_request_index_invalid",
    ):
        validate_bybit_execution_quality_capture(
            tmp_path,
            namespace=result["artifact_namespace"],
        )


def test_capture_status_without_pointer_is_read_only(tmp_path: Path) -> None:
    before = set(tmp_path.iterdir())

    status = bybit_execution_quality_capture_status(tmp_path)

    assert status["status"] == "unavailable"
    assert status["reason"] == "capture_pointer_missing"
    assert status["provider_call_attempted"] is False
    assert status["writes_performed"] is False
    assert set(tmp_path.iterdir()) == before


def test_capture_pointer_rejects_rollback_to_an_older_complete_capture(
    tmp_path: Path,
) -> None:
    observations = (_observation("bitcoin", "BTC", 3_000.0),)
    later = datetime(2026, 7, 17, 12, 0, 2, tzinfo=timezone.utc)
    first = capture_authoritative_bybit_execution_quality(
        artifact_base_dir=tmp_path,
        environ={LIVE_AUTH_ENV: "1"},
        now=lambda: later,
        resolver=_resolver(observations, expected_now=later),
        fetch_json=_fetch,
    )
    pointer_path = tmp_path / POINTER_FILENAME
    pointer_before = pointer_path.read_bytes()
    namespaces_before = set(tmp_path.glob("radar_bybit_execution_quality_*"))

    with pytest.raises(BybitExecutionQualityLiveError, match="rollback_rejected"):
        capture_authoritative_bybit_execution_quality(
            artifact_base_dir=tmp_path,
            environ={LIVE_AUTH_ENV: "1"},
            now=lambda: NOW,
            resolver=_resolver(observations),
            fetch_json=_fetch,
        )

    assert pointer_path.read_bytes() == pointer_before
    assert set(tmp_path.glob("radar_bybit_execution_quality_*")) == namespaces_before
    assert load_latest_bybit_execution_quality_capture(tmp_path)["capture_id"] == first[
        "capture_id"
    ]


def test_new_capture_refuses_to_replace_a_corrupt_existing_pointer(
    tmp_path: Path,
) -> None:
    observations = (_observation("bitcoin", "BTC", 3_000.0),)
    capture_authoritative_bybit_execution_quality(
        artifact_base_dir=tmp_path,
        environ={LIVE_AUTH_ENV: "1"},
        now=lambda: NOW,
        resolver=_resolver(observations),
        fetch_json=_fetch,
    )
    pointer_path = tmp_path / POINTER_FILENAME
    pointer = json.loads(pointer_path.read_text())
    pointer["unexpected"] = "must-fail-closed"
    pointer_path.write_text(json.dumps(pointer), encoding="utf-8")
    corrupt_bytes = pointer_path.read_bytes()
    later = datetime(2026, 7, 17, 12, 0, 2, tzinfo=timezone.utc)

    with pytest.raises(BybitExecutionQualityLiveError, match="pointer_contract_invalid"):
        capture_authoritative_bybit_execution_quality(
            artifact_base_dir=tmp_path,
            environ={LIVE_AUTH_ENV: "1"},
            now=lambda: later,
            resolver=_resolver(observations, expected_now=later),
            fetch_json=_fetch,
        )

    assert pointer_path.read_bytes() == corrupt_bytes


def test_project_review_export_selects_and_revalidates_latest_capture(
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
    observations = (_observation("bitcoin", "BTC", 3_000.0),)
    capture = capture_authoritative_bybit_execution_quality(
        artifact_base_dir=base,
        environ={LIVE_AUTH_ENV: "1"},
        now=lambda: NOW,
        resolver=_resolver(observations),
        fetch_json=_fetch,
    )
    spec = importlib.util.spec_from_file_location(
        "bybit_capture_project_export",
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
    assert "event_fade_cache/radar_bybit_execution_quality_latest.json" in names
    assert f"{prefix}capture_completion_receipt.json" in names
    assert f"{prefix}capture_manifest.json" in names
    selected = {
        row["kind"]: row for row in manifest["selector_results"]
    }["latest_bybit_execution_quality_namespace"]
    assert selected["artifact_namespace"] == capture["artifact_namespace"]
    assert selected["capture_id"] == capture["capture_id"]
    assert selected["status"] == "selected"
    assert selected["evidence_authority_eligible"] is True
    assert selected["protocol_v2_input_quality_eligible"] is True
    assert selected["protocol_v2_evidence_eligible"] is False
    assert selected["protocol_v2_annex_bound"] is False


@pytest.mark.parametrize("command", ["collect", "capture"])
def test_writing_cli_commands_require_confirmation_before_any_state(
    tmp_path: Path,
    command: str,
) -> None:
    from crypto_rsi_scanner.event_alpha.operations.bybit_execution_quality_live import (
        main,
    )

    before = set(tmp_path.iterdir())
    assert main([command, "--artifact-base", str(tmp_path)]) == 1
    assert set(tmp_path.iterdir()) == before
