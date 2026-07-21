"""Immutable outcome-price recovery capture and source-binding regressions."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import zipfile

import pytest

from crypto_rsi_scanner.event_alpha.operations import outcome_price_recovery as recovery
from crypto_rsi_scanner.event_alpha.operations import (
    outcome_price_recovery_capture as capture,
)
from crypto_rsi_scanner.event_alpha.operations import (
    outcome_price_recovery_capture_source as source,
)


_OBSERVED = datetime(2026, 7, 14, 0, 29, 40, 814498, tzinfo=timezone.utc)
_DUE = _OBSERVED + timedelta(days=1)
_LATEST = _DUE + timedelta(days=1)
_REQUESTED = datetime(2026, 7, 18, 10, 0, tzinfo=timezone.utc)
_RECEIVED = _REQUESTED + timedelta(seconds=1)
_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_capture_defaults_to_exact_campaign_projection():
    assert (
        inspect.signature(capture.capture_outcome_price_recovery)
        .parameters["report_builder"]
        .default
        is recovery.market_observation_campaign.build_outcome_recovery_projection
    )


def _gap() -> dict[str, object]:
    return {
        "outcome_identity_key": "a" * 64,
        "source_artifact_namespace": "radar_market_no_send_20260714t002940z",
        "candidate_id": "iar:634eae4a52fb",
        "core_opportunity_id": "agg:634eae4a52fb",
        "symbol": "DEXE",
        "coin_id": "dexe",
        "observed_at": _OBSERVED.isoformat(),
        "primary_horizon": "24h",
        "due_at": _DUE.isoformat(),
        "allowed_lag_seconds": 86400,
        "allowed_latest_price_at": _LATEST.isoformat(),
        "qualifying_price_observation_count": 0,
        "resolution_status": "first_post_due_price_outside_allowed_window",
        "ledger_refresh_can_resolve_from_retained_history": False,
        "historical_point_in_time_evidence_required": True,
        "interpolation_permitted": False,
        "automatic_threshold_change_permitted": False,
        "research_only": True,
    }


def _request() -> recovery.OutcomePriceRecoveryRequest:
    return recovery.build_recovery_requests({
        "due_missing_price_details": [_gap()],
    })[0]


def _response(
    request: recovery.OutcomePriceRecoveryRequest,
    *,
    prices: list[list[float | int]] | None = None,
    received_at: datetime = _RECEIVED,
) -> recovery.CapturedCoinGeckoResponse:
    payload = {
        "prices": prices if prices is not None else [[int((_DUE + timedelta(hours=1)).timestamp() * 1000), 41.0]],
        "market_caps": [],
        "total_volumes": [],
    }
    return recovery.CapturedCoinGeckoResponse(
        request_id=request.request_id,
        provider_base_url=recovery.PUBLIC_API_BASE,
        http_status=200,
        requested_at=_REQUESTED,
        received_at=received_at,
        body=json.dumps(payload, separators=(",", ":")).encode(),
    )


def _readiness(request: recovery.OutcomePriceRecoveryRequest) -> dict[str, object]:
    return {
        "ready": True,
        "plan_digest": "b" * 64,
        "campaign_pointer": {
            "status": "authoritative",
            "artifact_namespace": "radar_market_no_send_current",
            "run_id": "run:current",
            "revision": 12,
            "operator_state_sha256": "c" * 64,
            "exact_operator_binding": True,
        },
        "price_history_snapshot": {
            "status": "observed",
            "artifact": "event_market_history.jsonl",
            "sha256": "d" * 64,
            "row_count": 420,
            "binding_source": "campaign_market_history_exact_bytes",
        },
        "historical_recovery_requests": [
            recovery.recovery_request_values(request)
        ],
    }


def _collected(
    *,
    prices: list[list[float | int]] | None = None,
    received_at: datetime = _RECEIVED,
) -> dict[str, object]:
    request = _request()
    response = _response(request, prices=prices, received_at=received_at)
    result = recovery.normalize_captured_recovery_response(request, response)
    return {
        "readiness": _readiness(request),
        "requests": (request,),
        "responses": (response,),
        "results": (result,),
        "provider_request_count": 1,
    }


def _fingerprint(seed: bytes) -> dict[str, object]:
    return {
        "sha256": hashlib.sha256(seed).hexdigest(),
        "size_bytes": len(seed),
    }


def _source_binding(
    request: recovery.OutcomePriceRecoveryRequest | None = None,
) -> dict[str, object]:
    selected = request or _request()
    return {
        "schema_id": "decision_radar.outcome_price_recovery_source_binding",
        "schema_version": 1,
        "campaign_pointer": _readiness(selected)["campaign_pointer"],
        "price_history_snapshot": _readiness(selected)["price_history_snapshot"],
        "outcome_ledger_snapshot": {
            "artifact": "event_decision_radar_campaign_outcomes.jsonl",
            "sha256": "e" * 64,
            "size_bytes": 1234,
            "row_count": 5,
            "binding_source": "campaign_outcome_ledger_exact_bytes",
        },
        "outcome_targets": [{
            "request_id": selected.request_id,
            "outcome_identity_key": selected.outcome_identity_key,
            "source_artifact_namespace": selected.source_artifact_namespace,
            "target_row_sha256": "f" * 64,
        }],
        "source_generations": [{
            "request_id": selected.request_id,
            "artifact_namespace": selected.source_artifact_namespace,
            "manifest": _fingerprint(b"manifest"),
            "candidate_artifact": _fingerprint(b"candidate"),
            "candidate_row_sha256": "1" * 64,
            "core_artifact": _fingerprint(b"core"),
            "core_row_sha256": "2" * 64,
        }],
        "baseline_mutated": False,
        "campaign_outcomes_mutated": False,
        "research_only": True,
    }


def _persist(tmp_path: Path, monkeypatch, **kwargs):
    binding = _source_binding()
    source.validate_source_binding(binding)
    monkeypatch.setattr(capture, "build_source_binding", lambda *_args: binding)
    return capture.persist_outcome_price_recovery_capture(
        tmp_path,
        collected=_collected(**kwargs),
    )


def test_capture_persists_exact_bytes_and_rederives_without_campaign_mutation(
    tmp_path,
    monkeypatch,
):
    collected = _collected()
    raw = collected["responses"][0].body
    result = _persist(tmp_path, monkeypatch)

    assert result["status"] == "complete"
    assert result["request_count"] == 1
    assert result["qualifying_price_count"] == 1
    assert result["results"][0]["price_usd"] == 41.0
    assert result["point_in_time_collection_at_market_time"] is False
    assert result["baseline_eligible"] is False
    assert result["campaign_outcomes_mutated"] is False
    assert result["protocol_v2_evidence_eligible"] is False
    assert result["pointer_validated"] is True
    namespace_dir = tmp_path / result["artifact_namespace"]
    assert (namespace_dir / "response_001.json").read_bytes() == raw
    assert (tmp_path / capture.POINTER_FILENAME).is_file()
    assert not (tmp_path / "radar_market_history_cache").exists()

    manifest = json.loads((namespace_dir / capture.MANIFEST_FILENAME).read_text())
    assert manifest["campaign_outcomes_mutated"] is False
    assert manifest["baseline_eligible"] is False
    assert manifest["writes_performed"] is True
    assert len(manifest["artifacts"]) == 5


def test_capture_status_is_read_only_when_no_pointer_exists(tmp_path):
    before = sorted(tmp_path.iterdir())
    status = capture.outcome_price_recovery_capture_status(tmp_path)

    assert status["status"] == "unavailable"
    assert status["reason"] == "recovery_capture_pointer_missing"
    assert status["provider_call_attempted"] is False
    assert status["writes_performed"] is False
    assert sorted(tmp_path.iterdir()) == before


def test_capture_accepts_honest_no_results_without_manufacturing_price(
    tmp_path,
    monkeypatch,
):
    result = _persist(
        tmp_path,
        monkeypatch,
        prices=[[int((_DUE - timedelta(milliseconds=300)).timestamp() * 1000), 40.0]],
    )

    assert result["qualifying_price_count"] == 0
    assert result["results"][0]["status"] == "no_results"
    assert result["results"][0]["price_usd"] is None


def test_capture_is_idempotent_for_the_same_exact_response(tmp_path, monkeypatch):
    first = _persist(tmp_path, monkeypatch)
    second = _persist(tmp_path, monkeypatch)

    assert second["capture_id"] == first["capture_id"]
    assert second["pointer_sha256"] == first["pointer_sha256"]


def test_capture_rejects_pointer_rollback(tmp_path, monkeypatch):
    later = _persist(
        tmp_path,
        monkeypatch,
        received_at=_RECEIVED + timedelta(hours=1),
    )
    assert later["status"] == "complete"

    with pytest.raises(
        recovery.OutcomePriceRecoveryError,
        match="recovery_capture_pointer_rollback_rejected",
    ):
        _persist(tmp_path, monkeypatch)


def test_capture_rejects_raw_response_tampering(tmp_path, monkeypatch):
    result = _persist(tmp_path, monkeypatch)
    response_path = tmp_path / result["artifact_namespace"] / "response_001.json"
    response_path.write_bytes(b'{"prices":[],"market_caps":[],"total_volumes":[]}')

    with pytest.raises(
        recovery.OutcomePriceRecoveryError,
        match="recovery_capture_descriptor_invalid",
    ):
        capture.load_latest_outcome_price_recovery_capture(tmp_path)


def test_capture_rejects_unmanifested_artifact(tmp_path, monkeypatch):
    result = _persist(tmp_path, monkeypatch)
    namespace_dir = tmp_path / result["artifact_namespace"]
    (namespace_dir / "extra.json").write_text("{}\n")

    with pytest.raises(
        recovery.OutcomePriceRecoveryError,
        match="recovery_capture_inventory_invalid",
    ):
        capture.load_latest_outcome_price_recovery_capture(tmp_path)


def test_capture_rejects_namespace_symlink(tmp_path, monkeypatch):
    result = _persist(tmp_path, monkeypatch)
    namespace = result["artifact_namespace"]
    namespace_dir = tmp_path / namespace
    moved = tmp_path / "moved_capture"
    namespace_dir.rename(moved)
    namespace_dir.symlink_to(moved, target_is_directory=True)

    with pytest.raises(
        recovery.OutcomePriceRecoveryError,
        match="recovery_capture_namespace_unreadable",
    ):
        capture.load_latest_outcome_price_recovery_capture(tmp_path)


def test_capture_rejects_collection_result_drift(tmp_path, monkeypatch):
    binding = _source_binding()
    monkeypatch.setattr(capture, "build_source_binding", lambda *_args: binding)
    collected = _collected()
    collected["results"][0]["price_usd"] = 999.0

    with pytest.raises(
        recovery.OutcomePriceRecoveryError,
        match="recovery_capture_collection_drift",
    ):
        capture.persist_outcome_price_recovery_capture(
            tmp_path,
            collected=collected,
        )
    assert list(tmp_path.iterdir()) == []


def test_source_binding_reconciles_exact_target_and_history(monkeypatch, tmp_path):
    request = _request()
    target = {
        "outcome_identity_key": request.outcome_identity_key,
        "source_artifact_namespace": request.source_artifact_namespace,
        "candidate_id": request.candidate_id,
        "core_opportunity_id": request.core_opportunity_id,
        "symbol": request.symbol,
        "coin_id": request.coin_id,
        "maturation_state": "missing_data",
    }
    monkeypatch.setattr(
        source.market_observation_campaign_snapshots,
        "campaign_market_history_snapshot",
        lambda *_args, **_kwargs: {
            "status": "observed",
            "sha256": "d" * 64,
            "row_count": 420,
        },
    )
    monkeypatch.setattr(
        source.market_observation_campaign_snapshots,
        "campaign_outcome_ledger_snapshot",
        lambda *_args, **_kwargs: {
            "status": "observed",
            "artifact": "event_decision_radar_campaign_outcomes.jsonl",
            "sha256": "e" * 64,
            "size_bytes": 1234,
            "row_count": 1,
            "binding_source": "campaign_outcome_ledger_exact_bytes",
            "rows": (target,),
        },
    )
    monkeypatch.setattr(
        source,
        "_generation_binding",
        lambda *_args: _source_binding(request)["source_generations"][0],
    )

    binding = source.build_source_binding(
        tmp_path,
        _readiness(request),
        (request,),
    )

    assert binding["price_history_snapshot"]["sha256"] == "d" * 64
    assert binding["outcome_ledger_snapshot"]["sha256"] == "e" * 64
    assert binding["outcome_targets"][0]["outcome_identity_key"] == "a" * 64
    assert binding["baseline_mutated"] is False


def test_source_binding_rejects_history_drift_before_capture(monkeypatch, tmp_path):
    request = _request()
    monkeypatch.setattr(
        source.market_observation_campaign_snapshots,
        "campaign_market_history_snapshot",
        lambda *_args, **_kwargs: {
            "status": "observed",
            "sha256": "0" * 64,
            "row_count": 420,
        },
    )

    with pytest.raises(
        recovery.OutcomePriceRecoveryError,
        match="recovery_capture_history_binding_drift",
    ):
        source.build_source_binding(tmp_path, _readiness(request), (request,))


def test_confirmed_capture_uses_one_fetch_and_seals_it(tmp_path, monkeypatch):
    request = _request()
    binding = _source_binding(request)
    monkeypatch.setattr(capture, "build_source_binding", lambda *_args: binding)
    fetch_count = 0

    def fetch(selected, _timeout):
        nonlocal fetch_count
        fetch_count += 1
        assert selected == request
        return _response(selected)

    report = {
        "campaign_status": "in_progress_baseline_warming",
        "generated_at": _REQUESTED.isoformat(),
        "pointer": _readiness(request)["campaign_pointer"],
        "outcomes": {
            "due_missing_price_details": [_gap()],
            "price_history_snapshot": _readiness(request)["price_history_snapshot"],
        },
    }
    clocks = iter((_REQUESTED, _RECEIVED + timedelta(seconds=1)))
    result = capture.capture_outcome_price_recovery(
        artifact_base_dir=tmp_path,
        confirm=True,
        environ={
            recovery.GENERAL_COINGECKO_AUTH_ENV: "1",
            recovery.LIVE_AUTH_ENV: "1",
        },
        fixture_dir=None,
        report_builder=lambda *_args, **_kwargs: deepcopy(report),
        provider_state_assessor=lambda *_args, **_kwargs: {"allowed": True},
        fetch_exact=fetch,
        clock=lambda: next(clocks),
    )

    assert fetch_count == 1
    assert result["status"] == "complete"
    assert result["request_count"] == 1
    assert result["writes_performed"] is False


def test_project_review_export_selects_and_revalidates_latest_capture(
    tmp_path,
    monkeypatch,
):
    root = tmp_path / "tree"
    base = root / "event_fade_cache"
    base.mkdir(parents=True)
    (root / "Makefile").write_text("verify:\n\t@true\n")
    policy_source = (
        _REPO_ROOT / "research/DECISION_RADAR_PROJECT_ARTIFACT_POLICY.json"
    )
    policy_target = (
        root / "research/DECISION_RADAR_PROJECT_ARTIFACT_POLICY.json"
    )
    policy_target.parent.mkdir(parents=True)
    policy_target.write_bytes(policy_source.read_bytes())
    result = _persist(base, monkeypatch)
    spec = importlib.util.spec_from_file_location(
        "outcome_price_recovery_project_export",
        _REPO_ROOT / "scripts/export_source_with_artifacts.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = root / "review.zip"

    assert module.main(root=root, out=output) == 0

    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read(
            "event_fade_cache/PROJECT_ARTIFACT_EXPORT_MANIFEST.json"
        ))
    prefix = f"event_fade_cache/{result['artifact_namespace']}/"
    assert (
        "event_fade_cache/"
        "event_decision_radar_outcome_price_recovery_latest.json"
    ) in names
    assert f"{prefix}{capture.MANIFEST_FILENAME}" in names
    assert f"{prefix}{capture.RECEIPT_FILENAME}" in names
    assert f"{prefix}response_001.json" in names
    selected = {
        row["kind"]: row for row in manifest["selector_results"]
    }["latest_outcome_price_recovery_namespace"]
    assert selected["artifact_namespace"] == result["artifact_namespace"]
    assert selected["capture_id"] == result["capture_id"]
    assert selected["request_count"] == 1
    assert selected["qualifying_price_count"] == 1
    assert selected["protocol_v2_evidence_eligible"] is False
    assert selected["status"] == "selected"
