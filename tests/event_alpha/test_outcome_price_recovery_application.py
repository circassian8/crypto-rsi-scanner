"""Ledger-only historical outcome-price recovery application regressions."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.operations import market_no_send_io
from crypto_rsi_scanner.event_alpha.operations import market_observation_outcomes
from crypto_rsi_scanner.event_alpha.operations import outcome_price_recovery as recovery
from crypto_rsi_scanner.event_alpha.operations import (
    outcome_price_recovery_application as application,
)
from crypto_rsi_scanner.event_alpha.operations.market_no_send_campaign_guard import (
    CAMPAIGN_LOCK_FILENAME,
)
from crypto_rsi_scanner.event_alpha.operations.market_no_send_history_cache import (
    LIVE_HISTORY_CACHE_NAMESPACE,
)
from crypto_rsi_scanner.event_alpha.outcomes import outcome_eligibility
from crypto_rsi_scanner.event_alpha.radar import decision_model
from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import (
    decision_model_values,
)
from tests.event_alpha.campaign_test_support import write_countable_generation


_OBSERVED = datetime(2026, 7, 14, 12, tzinfo=timezone.utc)
_EVALUATED = _OBSERVED + timedelta(days=2)
_ACQUIRED = _OBSERVED + timedelta(days=4)
_APPLIED = _ACQUIRED + timedelta(hours=1)
_NAMESPACE = "recovery_application_generation"


def _candidate(*, suffix: str, symbol: str, coin_id: str) -> dict[str, object]:
    observed = _OBSERVED.isoformat()
    row: dict[str, object] = {
        "row_type": "event_integrated_radar_candidate",
        "schema_id": "integrated_radar_candidate_v1",
        "schema_version": "event_alpha_schema_v1",
        "run_id": "recovery-application-run",
        "profile": "no_key_live",
        "artifact_namespace": _NAMESPACE,
        "candidate_id": f"candidate-recovery-{suffix}",
        "core_opportunity_id": f"core-recovery-{suffix}",
        "observed_at": observed,
        "symbol": symbol,
        "coin_id": coin_id,
        "canonical_asset_id": coin_id,
        "instrument_resolver_status": "resolved",
        "instrument_resolver_confidence": 0.99,
        "instrument_identity_trusted": True,
        "is_tradable_asset": True,
        "opportunity_type": "DIAGNOSTIC",
        "market_state_class": "confirmed_breakout",
        "market_anomaly_bucket": "high_liquidity_breakout",
        "source_origin": "market_anomaly",
        "source_origins": ["market_anomaly"],
        "source_pack": "market_anomaly_pack",
        "market_snapshot": {
            "market_data_source": "coingecko",
            "observed_at": observed,
            "freshness_status": "fresh",
            "market_snapshot_id": f"market-recovery-{suffix}",
        },
        "market_state_snapshot": {
            "return_unit": "percent_points",
            "return_4h": 12.0,
            "return_24h": 20.0,
            "relative_return_vs_btc_4h": 9.0,
            "volume_zscore_24h": 3.5,
            "volume_to_market_cap": 0.30,
            "liquidity_usd": 12_000_000.0,
            "spread_bps": 22.0,
            "freshness_status": "fresh",
        },
        "research_only": True,
        "sent": False,
        "normal_rsi_signal_written": False,
        "triggered_fade_created": False,
        "paper_trade_created": False,
        "trade_created": False,
    }
    row.update(decision_model.evaluate_radar_decision(row).to_dict())
    row["decision_projection"] = decision_model_values(row)
    return row


def _history_row(*, symbol: str, coin_id: str, price: float) -> dict[str, object]:
    return {
        "schema_id": "event_alpha.market_history_observation",
        "schema_version": 1,
        "canonical_asset_id": coin_id,
        "coin_id": coin_id,
        "symbol": symbol,
        "observed_at": _OBSERVED.isoformat(),
        "observation_id": f"recovery-entry-{coin_id}",
        "price": price,
        "source": "coingecko",
        "provider": "coingecko",
        "research_only": True,
    }


def _fingerprint(raw: bytes) -> dict[str, object]:
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _row_sha256(row: dict[str, object]) -> str:
    raw = json.dumps(
        row,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode()
    return hashlib.sha256(raw).hexdigest()


def _gap(row: dict[str, object]) -> dict[str, object]:
    primary = str(row["primary_horizon"])
    horizon = row["horizon_metadata"][primary]
    due = outcome_eligibility.parse_aware_time(horizon["due_at"])
    assert due is not None
    return {
        "outcome_identity_key": row["outcome_identity_key"],
        "source_artifact_namespace": row["source_artifact_namespace"],
        "candidate_id": row["candidate_id"],
        "core_opportunity_id": row["core_opportunity_id"],
        "symbol": row["symbol"],
        "coin_id": row["coin_id"],
        "observed_at": row["observed_at"],
        "primary_horizon": primary,
        "due_at": horizon["due_at"],
        "allowed_lag_seconds": 24 * 60 * 60,
        "allowed_latest_price_at": (
            due + timedelta(days=1)
        ).isoformat(),
        "qualifying_price_observation_count": 0,
        "resolution_status": "first_post_due_price_outside_allowed_window",
        "ledger_refresh_can_resolve_from_retained_history": False,
        "historical_point_in_time_evidence_required": True,
        "interpolation_permitted": False,
        "automatic_threshold_change_permitted": False,
        "research_only": True,
    }


def _fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    qualifying: bool = True,
) -> dict[str, object]:
    candidates = [
        _candidate(suffix="target", symbol="DEXE", coin_id="dexe"),
        _candidate(suffix="control", symbol="CTRL", coin_id="control-token"),
    ]
    write_countable_generation(
        tmp_path,
        _NAMESPACE,
        _OBSERVED.isoformat(),
        candidates=candidates,
    )
    state_dir = tmp_path / LIVE_HISTORY_CACHE_NAMESPACE
    state_dir.mkdir(parents=True)
    history_path = state_dir / "event_market_history.jsonl"
    market_no_send_io.write_jsonl(history_path, [
        _history_row(symbol="DEXE", coin_id="dexe", price=100.0),
        _history_row(symbol="CTRL", coin_id="control-token", price=200.0),
    ])
    market_observation_outcomes.refresh_campaign_outcomes(
        tmp_path,
        evaluated_at=_EVALUATED,
    )
    ledger_path = (
        state_dir / market_observation_outcomes.CAMPAIGN_OUTCOMES_FILENAME
    )
    ledger_rows = market_no_send_io.read_jsonl(ledger_path)
    target = next(row for row in ledger_rows if row["symbol"] == "DEXE")
    assert target["maturation_state"] == "missing_data"
    request = recovery.build_recovery_requests({
        "due_missing_price_details": [_gap(target)],
    })[0]
    due = outcome_eligibility.parse_aware_time(request.due_at)
    assert due is not None
    payload = {
        "prices": (
            [[int((due + timedelta(hours=1)).timestamp() * 1000), 110.0]]
            if qualifying
            else []
        ),
        "market_caps": [],
        "total_volumes": [],
    }
    response = recovery.CapturedCoinGeckoResponse(
        request_id=request.request_id,
        provider_base_url=recovery.PUBLIC_API_BASE,
        http_status=200,
        requested_at=_ACQUIRED - timedelta(seconds=1),
        received_at=_ACQUIRED,
        body=json.dumps(payload, separators=(",", ":")).encode(),
    )
    result = recovery.normalize_captured_recovery_response(request, response)
    candidate_path = (
        tmp_path / _NAMESPACE / "event_integrated_radar_candidates.jsonl"
    )
    candidate_raw = candidate_path.read_bytes()
    stored_candidates = market_no_send_io.read_jsonl(candidate_path)
    stored_target = next(
        row for row in stored_candidates if row["candidate_id"] == request.candidate_id
    )
    history_raw = history_path.read_bytes()
    source_binding = {
        "schema_id": "decision_radar.outcome_price_recovery_source_binding",
        "schema_version": 1,
        "campaign_pointer": {
            "status": "authoritative",
            "artifact_namespace": _NAMESPACE,
        },
        "price_history_snapshot": {
            "status": "observed",
            "artifact": history_path.name,
            **_fingerprint(history_raw),
            "row_count": len(market_no_send_io.read_jsonl(history_path)),
            "binding_source": "campaign_market_history_exact_bytes",
        },
        "outcome_ledger_snapshot": {
            "artifact": ledger_path.name,
            **_fingerprint(ledger_path.read_bytes()),
            "row_count": len(ledger_rows),
            "binding_source": "campaign_outcome_ledger_exact_bytes",
        },
        "outcome_targets": [{
            "request_id": request.request_id,
            "outcome_identity_key": request.outcome_identity_key,
            "source_artifact_namespace": request.source_artifact_namespace,
            "target_row_sha256": _row_sha256(target),
        }],
        "source_generations": [{
            "request_id": request.request_id,
            "artifact_namespace": request.source_artifact_namespace,
            "candidate_artifact": _fingerprint(candidate_raw),
            "candidate_row_sha256": _row_sha256(stored_target),
        }],
        "baseline_mutated": False,
        "campaign_outcomes_mutated": False,
        "research_only": True,
    }
    capture = {
        "capture_contract_version": "decision_radar_outcome_price_recovery_capture_v1",
        "capture_id": "a" * 64,
        "artifact_namespace": "radar_outcome_price_recovery_fixture",
        "completed_at": _ACQUIRED.isoformat(),
        "request_count": 1,
        "qualifying_price_count": int(qualifying),
        "results": [result],
        "source_binding": source_binding,
        "pointer_sha256": "b" * 64,
        "receipt_sha256": "c" * 64,
        "research_only": True,
    }
    monkeypatch.setattr(
        application,
        "load_latest_outcome_price_recovery_capture",
        lambda _base: deepcopy(capture),
    )
    monkeypatch.setattr(
        application,
        "build_source_binding",
        lambda *_args: deepcopy(source_binding),
    )
    (tmp_path / CAMPAIGN_LOCK_FILENAME).write_bytes(b"")
    return {
        "capture": capture,
        "request": request,
        "result": result,
        "source_binding": source_binding,
        "history_path": history_path,
        "ledger_path": ledger_path,
        "target": target,
    }


def test_confirmed_application_changes_exact_target_and_preserves_baseline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    fixture = _fixture(tmp_path, monkeypatch)
    history_before = fixture["history_path"].read_bytes()
    ledger_before = fixture["ledger_path"].read_bytes()
    rows_before = market_no_send_io.read_jsonl(fixture["ledger_path"])
    control_before = next(row for row in rows_before if row["symbol"] == "CTRL")

    result = application.apply_outcome_price_recovery(
        tmp_path,
        confirm=True,
        applied_at=_APPLIED,
    )

    rows_after = market_no_send_io.read_jsonl(fixture["ledger_path"])
    recovered = next(row for row in rows_after if row["symbol"] == "DEXE")
    control_after = next(row for row in rows_after if row["symbol"] == "CTRL")
    assert result["status"] == "applied"
    assert result["provider_calls"] == 0
    assert result["applied_outcome_count"] == 1
    assert result["baseline_byte_identical"] is True
    assert fixture["history_path"].read_bytes() == history_before
    assert fixture["ledger_path"].read_bytes() != ledger_before
    assert control_after == control_before
    assert recovered["maturation_state"] == "matured"
    assert recovered["primary_horizon_return"] == pytest.approx(0.1)
    assert recovered["historical_price_recovery"] is True
    assert recovered["historical_price_recovery_point_in_time"] is False
    assert recovered["calibration_eligible"] is False
    assert recovered["include_in_performance"] is False
    assert "historical_price_recovery" in recovered[
        "calibration_ineligible_reasons"
    ]
    primary = recovered["primary_horizon"]
    assert recovered["horizon_metadata"][primary]["price_source"] == (
        "coingecko_market_chart_range_historical_recovery"
    )
    assert outcome_eligibility.validate_contract(recovered) == []

    receipt_path = (
        tmp_path / LIVE_HISTORY_CACHE_NAMESPACE / result["application_receipt"]
    )
    receipt_raw = receipt_path.read_bytes()
    receipt = application.validate_application_receipt_bytes(receipt_raw)
    assert receipt["outcome_ledger_before"]["sha256"] == hashlib.sha256(
        ledger_before
    ).hexdigest()
    assert receipt["outcome_ledger_after"]["sha256"] == hashlib.sha256(
        fixture["ledger_path"].read_bytes()
    ).hexdigest()
    assert receipt["baseline_before"] == receipt["baseline_after"]


def test_application_is_idempotent_and_status_is_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    fixture = _fixture(tmp_path, monkeypatch)
    first = application.apply_outcome_price_recovery(
        tmp_path,
        confirm=True,
        applied_at=_APPLIED,
    )
    ledger_after = fixture["ledger_path"].read_bytes()
    tree_before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    second = application.apply_outcome_price_recovery(
        tmp_path,
        confirm=True,
        applied_at=_APPLIED + timedelta(hours=1),
    )
    status = application.outcome_price_recovery_application_status(tmp_path)

    assert second["status"] == "already_applied"
    assert second["writes_performed"] is False
    assert second["application_receipt"] == first["application_receipt"]
    assert status["status"] == "applied"
    assert status["writes_performed"] is False
    assert status["provider_calls"] == 0
    assert fixture["ledger_path"].read_bytes() == ledger_after
    assert sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*")) == tree_before


def test_campaign_refresh_preserves_recovery_firewall(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    fixture = _fixture(tmp_path, monkeypatch)
    application.apply_outcome_price_recovery(
        tmp_path,
        confirm=True,
        applied_at=_APPLIED,
    )

    market_observation_outcomes.refresh_campaign_outcomes(
        tmp_path,
        evaluated_at=_APPLIED + timedelta(days=1),
    )

    recovered = next(
        row
        for row in market_no_send_io.read_jsonl(fixture["ledger_path"])
        if row["symbol"] == "DEXE"
    )
    candidate = next(
        row
        for row in market_no_send_io.read_jsonl(
            tmp_path / _NAMESPACE / "event_integrated_radar_candidates.jsonl"
        )
        if row["candidate_id"] == recovered["candidate_id"]
    )
    assert recovered["historical_price_recovery"] is True
    assert recovered["maturation_state"] == "matured"
    assert recovered["calibration_eligible"] is False
    assert "historical_price_recovery" in recovered[
        "calibration_ineligible_reasons"
    ]
    assert market_observation_outcomes.campaign_ledger_outcome_valid(
        recovered,
        candidate,
        namespace=_NAMESPACE,
    ) is True


@pytest.mark.parametrize("artifact", ("history", "ledger"))
def test_applied_receipt_rejects_current_state_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    artifact: str,
):
    fixture = _fixture(tmp_path, monkeypatch)
    application.apply_outcome_price_recovery(
        tmp_path,
        confirm=True,
        applied_at=_APPLIED,
    )
    if artifact == "history":
        rows = market_no_send_io.read_jsonl(fixture["history_path"])
        rows[0]["price"] = 999.0
        market_no_send_io.write_jsonl(fixture["history_path"], rows)
    else:
        rows = market_no_send_io.read_jsonl(fixture["ledger_path"])
        control = next(row for row in rows if row["symbol"] == "CTRL")
        control["outcome_label"] = "tampered"
        market_no_send_io.write_jsonl(fixture["ledger_path"], rows)

    with pytest.raises(
        recovery.OutcomePriceRecoveryError,
        match="recovery_application_current_state_drift",
    ):
        application.apply_outcome_price_recovery(
            tmp_path,
            confirm=True,
            applied_at=_APPLIED + timedelta(hours=1),
        )
    status = application.outcome_price_recovery_application_status(tmp_path)
    assert status["status"] == "unavailable"
    assert status["reason"] == "recovery_application_current_state_drift"
    assert status["writes_performed"] is False


def test_confirmation_and_no_result_capture_perform_no_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    fixture = _fixture(tmp_path, monkeypatch, qualifying=False)
    before = {
        path: path.read_bytes()
        for path in (fixture["history_path"], fixture["ledger_path"])
    }
    with pytest.raises(
        recovery.OutcomePriceRecoveryError,
        match="recovery_application_explicit_confirmation_required",
    ):
        application.apply_outcome_price_recovery(tmp_path, confirm=False)

    result = application.apply_outcome_price_recovery(
        tmp_path,
        confirm=True,
        applied_at=_APPLIED,
    )

    assert result["status"] == "no_work"
    assert result["writes_performed"] is False
    assert not list(
        (tmp_path / LIVE_HISTORY_CACHE_NAMESPACE).glob(
            f"{application.APPLICATION_RECEIPT_PREFIX}*"
        )
    )
    for path, raw in before.items():
        assert path.read_bytes() == raw


def test_source_drift_and_busy_campaign_fail_before_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    fixture = _fixture(tmp_path, monkeypatch)
    history_before = fixture["history_path"].read_bytes()
    ledger_before = fixture["ledger_path"].read_bytes()
    drifted = deepcopy(fixture["source_binding"])
    drifted["campaign_pointer"] = {
        "status": "authoritative",
        "artifact_namespace": "different-generation",
    }
    monkeypatch.setattr(application, "build_source_binding", lambda *_args: drifted)
    with pytest.raises(
        recovery.OutcomePriceRecoveryError,
        match="recovery_application_source_binding_drift",
    ):
        application.apply_outcome_price_recovery(
            tmp_path,
            confirm=True,
            applied_at=_APPLIED,
        )
    assert fixture["history_path"].read_bytes() == history_before
    assert fixture["ledger_path"].read_bytes() == ledger_before

    monkeypatch.setattr(
        application,
        "build_source_binding",
        lambda *_args: deepcopy(fixture["source_binding"]),
    )
    lock_path = tmp_path / CAMPAIGN_LOCK_FILENAME
    with lock_path.open("r+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(
            recovery.OutcomePriceRecoveryError,
            match="recovery_application_campaign_busy",
        ):
            application.apply_outcome_price_recovery(
                tmp_path,
                confirm=True,
                applied_at=_APPLIED,
            )
    assert fixture["history_path"].read_bytes() == history_before
    assert fixture["ledger_path"].read_bytes() == ledger_before


def test_receipt_failure_restores_exact_ledger_and_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    fixture = _fixture(tmp_path, monkeypatch)
    history_before = fixture["history_path"].read_bytes()
    ledger_before = fixture["ledger_path"].read_bytes()

    def fail_receipt(*_args, **_kwargs):
        raise recovery.OutcomePriceRecoveryError(
            "recovery_application_receipt_write_failed"
        )

    monkeypatch.setattr(
        application,
        "write_application_state_immutable",
        fail_receipt,
    )
    with pytest.raises(
        recovery.OutcomePriceRecoveryError,
        match="recovery_application_receipt_write_failed",
    ):
        application.apply_outcome_price_recovery(
            tmp_path,
            confirm=True,
            applied_at=_APPLIED,
        )

    assert fixture["history_path"].read_bytes() == history_before
    assert fixture["ledger_path"].read_bytes() == ledger_before
    assert not list(
        (tmp_path / LIVE_HISTORY_CACHE_NAMESPACE).glob(
            f"{application.APPLICATION_RECEIPT_PREFIX}*"
        )
    )


def test_state_directory_swap_cannot_redirect_ledger_write_or_rollback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    fixture = _fixture(tmp_path, monkeypatch)
    history_before = fixture["history_path"].read_bytes()
    ledger_before = fixture["ledger_path"].read_bytes()
    state_dir = tmp_path / LIVE_HISTORY_CACHE_NAMESPACE
    detached_dir = tmp_path / "detached_market_history_cache"
    replacement_history = b"replacement-history-must-remain-unchanged\n"
    replacement_ledger = b"replacement-ledger-must-remain-unchanged\n"
    original_write = application.write_application_state_atomic
    swapped = False

    def swap_then_write(self, leaf, data, reason):
        nonlocal swapped
        if not swapped:
            swapped = True
            state_dir.rename(detached_dir)
            state_dir.mkdir()
            (state_dir / "event_market_history.jsonl").write_bytes(
                replacement_history
            )
            (state_dir / "event_decision_radar_campaign_outcomes.jsonl").write_bytes(
                replacement_ledger
            )
        return original_write(self, leaf, data, reason)

    monkeypatch.setattr(
        application,
        "write_application_state_atomic",
        swap_then_write,
    )
    with pytest.raises(
        recovery.OutcomePriceRecoveryError,
        match="recovery_application_state_identity_changed",
    ):
        application.apply_outcome_price_recovery(
            tmp_path,
            confirm=True,
            applied_at=_APPLIED,
        )

    assert (detached_dir / "event_market_history.jsonl").read_bytes() == history_before
    assert (
        detached_dir / "event_decision_radar_campaign_outcomes.jsonl"
    ).read_bytes() == ledger_before
    assert (state_dir / "event_market_history.jsonl").read_bytes() == (
        replacement_history
    )
    assert (
        state_dir / "event_decision_radar_campaign_outcomes.jsonl"
    ).read_bytes() == replacement_ledger
    assert not list(
        detached_dir.glob(f"{application.APPLICATION_RECEIPT_PREFIX}*")
    )
    assert not list(
        state_dir.glob(f"{application.APPLICATION_RECEIPT_PREFIX}*")
    )


def test_path_swap_after_ledger_replace_still_restores_anchored_prior_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    fixture = _fixture(tmp_path, monkeypatch)
    history_before = fixture["history_path"].read_bytes()
    ledger_before = fixture["ledger_path"].read_bytes()
    state_dir = tmp_path / LIVE_HISTORY_CACHE_NAMESPACE
    detached_dir = tmp_path / "detached_after_ledger_replace"
    replacement_history = b"replacement-history-after-ledger-replace\n"
    replacement_ledger = b"replacement-ledger-after-ledger-replace\n"

    def swap_then_fail_receipt(*_args, **_kwargs):
        state_dir.rename(detached_dir)
        state_dir.mkdir()
        (state_dir / "event_market_history.jsonl").write_bytes(
            replacement_history
        )
        (state_dir / "event_decision_radar_campaign_outcomes.jsonl").write_bytes(
            replacement_ledger
        )
        raise recovery.OutcomePriceRecoveryError(
            "recovery_application_receipt_write_failed"
        )

    monkeypatch.setattr(
        application,
        "write_application_state_immutable",
        swap_then_fail_receipt,
    )
    with pytest.raises(
        recovery.OutcomePriceRecoveryError,
        match="recovery_application_state_identity_changed",
    ):
        application.apply_outcome_price_recovery(
            tmp_path,
            confirm=True,
            applied_at=_APPLIED,
        )

    assert (detached_dir / "event_market_history.jsonl").read_bytes() == history_before
    assert (
        detached_dir / "event_decision_radar_campaign_outcomes.jsonl"
    ).read_bytes() == ledger_before
    assert (state_dir / "event_market_history.jsonl").read_bytes() == (
        replacement_history
    )
    assert (
        state_dir / "event_decision_radar_campaign_outcomes.jsonl"
    ).read_bytes() == replacement_ledger
    assert not list(
        detached_dir.glob(f"{application.APPLICATION_RECEIPT_PREFIX}*")
    )


def test_symlinked_mutable_artifact_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    fixture = _fixture(tmp_path, monkeypatch)
    ledger_before = fixture["ledger_path"].read_bytes()
    fixture["history_path"].unlink()
    fixture["history_path"].symlink_to(fixture["ledger_path"].name)

    with pytest.raises(
        recovery.OutcomePriceRecoveryError,
        match="recovery_application_history_unreadable",
    ):
        application.apply_outcome_price_recovery(
            tmp_path,
            confirm=True,
            applied_at=_APPLIED,
        )

    assert fixture["ledger_path"].read_bytes() == ledger_before
    assert not list(
        (tmp_path / LIVE_HISTORY_CACHE_NAMESPACE).glob(
            f"{application.APPLICATION_RECEIPT_PREFIX}*"
        )
    )


def test_application_status_without_capture_is_read_only(tmp_path: Path):
    before = sorted(tmp_path.iterdir())
    status = application.outcome_price_recovery_application_status(tmp_path)

    assert status["status"] == "unavailable"
    assert status["reason"] == "recovery_capture_pointer_missing"
    assert status["provider_calls"] == 0
    assert status["writes_performed"] is False
    assert sorted(tmp_path.iterdir()) == before


def test_application_receipt_validator_rejects_corrupted_target_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    _fixture(tmp_path, monkeypatch)
    result = application.apply_outcome_price_recovery(
        tmp_path,
        confirm=True,
        applied_at=_APPLIED,
    )
    receipt_path = (
        tmp_path / LIVE_HISTORY_CACHE_NAMESPACE / result["application_receipt"]
    )
    receipt = json.loads(receipt_path.read_text())
    receipt["target_changes"][0]["request_id"] = ""

    with pytest.raises(
        recovery.OutcomePriceRecoveryError,
        match="recovery_application_receipt_invalid",
    ):
        application.validate_application_receipt_values(receipt)


def test_application_status_rejects_semantically_rewritten_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    _fixture(tmp_path, monkeypatch)
    result = application.apply_outcome_price_recovery(
        tmp_path,
        confirm=True,
        applied_at=_APPLIED,
    )
    receipt_path = (
        tmp_path / LIVE_HISTORY_CACHE_NAMESPACE / result["application_receipt"]
    )
    receipt = json.loads(receipt_path.read_text())
    receipt["target_changes"][0]["price_usd"] = 111.0
    receipt_path.unlink()
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")

    status = application.outcome_price_recovery_application_status(tmp_path)

    assert status["status"] == "unavailable"
    assert status["reason"] == "recovery_application_receipt_invalid"
    assert status["writes_performed"] is False
