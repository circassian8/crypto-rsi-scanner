"""Outcome-price recovery planning and exact-response safety regressions."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import subprocess

import pytest

from crypto_rsi_scanner.event_alpha.operations import outcome_price_recovery as recovery


_OBSERVED = datetime(2026, 7, 14, 0, 29, 40, 814498, tzinfo=timezone.utc)
_DUE = _OBSERVED + timedelta(days=1)
_LATEST = _DUE + timedelta(days=1)
_CHECKED = datetime(2026, 7, 18, 10, tzinfo=timezone.utc)
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _gap(**updates: object) -> dict[str, object]:
    row: dict[str, object] = {
        "outcome_identity_key": "a" * 64,
        "source_artifact_namespace": "radar_market_no_send_20260714t002940z",
        "candidate_id": "iar:634eae4a52fb",
        "core_opportunity_id": "agg:634eae4a52fb",
        "symbol": "DEXE",
        "coin_id": "dexe",
        "observed_at": _OBSERVED.isoformat(),
        "primary_horizon": "24h",
        "due_at": _DUE.isoformat(),
        "allowed_lag_seconds": 24 * 60 * 60,
        "allowed_latest_price_at": _LATEST.isoformat(),
        "qualifying_price_observation_count": 0,
        "resolution_status": "first_post_due_price_outside_allowed_window",
        "ledger_refresh_can_resolve_from_retained_history": False,
        "historical_point_in_time_evidence_required": True,
        "interpolation_permitted": False,
        "automatic_threshold_change_permitted": False,
        "research_only": True,
    }
    row.update(updates)
    return row


def _outcomes(*, gaps: list[dict[str, object]] | None = None, sha: str = "b" * 64):
    selected = [_gap()] if gaps is None else gaps
    return {
        "due_missing_price": len(selected),
        "due_missing_price_detail_count": len(selected),
        "due_missing_price_details": selected,
        "price_history_snapshot": {
            "status": "observed",
            "artifact": "event_market_history.jsonl",
            "sha256": sha,
            "row_count": 420,
            "binding_source": "campaign_market_history_exact_bytes",
        },
    }


def _report(*, outcomes: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "campaign_status": "in_progress_baseline_warming",
        "generated_at": _CHECKED.isoformat(),
        "pointer": {
            "status": "authoritative",
            "artifact_namespace": "radar_market_no_send_current",
            "run_id": "run:current",
            "revision": 12,
            "operator_state_sha256": "c" * 64,
            "exact_operator_binding": True,
            "secret": "must-not-project",
        },
        "outcomes": _outcomes() if outcomes is None else outcomes,
    }


def _builder(report: dict[str, object]):
    def build(_base, *, evaluated_at):
        assert evaluated_at.tzinfo is not None
        return deepcopy(report)

    return build


def _provider_allowed(_base, *, checked_at):
    assert checked_at.tzinfo is not None
    return {"allowed": True, "reason": None, "disabled_until": None}


def _request() -> recovery.OutcomePriceRecoveryRequest:
    return recovery.build_recovery_requests(_outcomes())[0]


def _captured(
    request: recovery.OutcomePriceRecoveryRequest,
    prices: list[list[float | int]],
    *,
    payload_updates: dict[str, object] | None = None,
) -> recovery.CapturedCoinGeckoResponse:
    payload: dict[str, object] = {
        "prices": prices,
        "market_caps": [],
        "total_volumes": [],
    }
    payload.update(payload_updates or {})
    return recovery.CapturedCoinGeckoResponse(
        request_id=request.request_id,
        provider_base_url=recovery.PUBLIC_API_BASE,
        http_status=200,
        requested_at=_CHECKED,
        received_at=_CHECKED + timedelta(seconds=1),
        body=json.dumps(payload, separators=(",", ":")).encode(),
    )


def _timestamp_ms(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def test_recovery_request_is_exact_deterministic_and_omits_interval():
    first = _request()
    second = _request()

    assert first == second
    assert first.endpoint_path == "/coins/dexe/market_chart/range"
    assert dict(first.query) == {
        "vs_currency": "usd",
        "from": str(math.floor(_DUE.timestamp())),
        "to": str(math.ceil(_LATEST.timestamp())),
        "precision": "full",
    }
    projected = recovery.recovery_request_values(first)
    assert "interval" not in projected["query"]
    assert projected["interval_parameter_omitted"] is True
    assert projected["maximum_provider_requests"] == 1
    assert projected["baseline_eligible"] is False
    assert projected["protocol_v2_evidence_eligible"] is False
    assert projected["source_documentation_url"] == recovery.SOURCE_DOCUMENTATION_URL


@pytest.mark.parametrize(
    ("updates", "reason"),
    [
        ({"coin_id": "../dexe"}, "recovery_coin_id_invalid"),
        ({"qualifying_price_observation_count": 1}, "due_missing_price_detail_contract_invalid"),
        ({"interpolation_permitted": True}, "due_missing_price_detail_contract_invalid"),
        ({"allowed_lag_seconds": 1}, "recovery_allowed_window_mismatch"),
        ({"due_at": (_DUE + timedelta(seconds=1)).isoformat()}, "recovery_due_at_mismatch"),
    ],
)
def test_recovery_request_rejects_identity_window_and_policy_drift(updates, reason):
    with pytest.raises(recovery.OutcomePriceRecoveryError, match=reason):
        recovery.build_recovery_requests(_outcomes(gaps=[_gap(**updates)]))


def test_recovery_request_skips_gap_already_resolvable_from_retained_history():
    requests = recovery.build_recovery_requests(_outcomes(gaps=[_gap(
        resolution_status="qualifying_price_available_ledger_refresh_required",
        ledger_refresh_can_resolve_from_retained_history=True,
        historical_point_in_time_evidence_required=False,
    )]))

    assert requests == ()


def test_exact_response_selects_first_price_inside_original_window():
    request = _request()
    response = _captured(request, [
        [_timestamp_ms(_DUE - timedelta(milliseconds=300)), 40.0],
        [_timestamp_ms(_DUE + timedelta(hours=1)), 41.0],
        [_timestamp_ms(_DUE + timedelta(hours=2)), 42.0],
    ])

    result = recovery.normalize_captured_recovery_response(request, response)

    assert result["status"] == "complete"
    expected_market_time = datetime.fromtimestamp(
        _timestamp_ms(_DUE + timedelta(hours=1)) / 1000,
        tz=timezone.utc,
    )
    assert result["price_observed_at"] == expected_market_time.isoformat().replace(
        "+00:00", "Z"
    )
    assert result["price_usd"] == 41.0
    assert result["price_unit"] == "USD_per_asset"
    assert result["outcome_completion_input_eligible"] is True
    assert result["historical_provider_series"] is True
    assert result["point_in_time_collection_at_market_time"] is False
    assert result["baseline_eligible"] is False
    assert result["baseline_history_written"] is False
    assert result["campaign_observation_counted"] is False
    assert result["calibration_eligible"] is False
    assert result["protocol_v2_evidence_eligible"] is False
    assert result["writes_performed"] is False
    assert len(result["raw_response_sha256"]) == 64


def test_exact_response_can_complete_without_manufacturing_a_result():
    request = _request()
    result = recovery.normalize_captured_recovery_response(
        request,
        _captured(request, [[_timestamp_ms(_DUE - timedelta(milliseconds=300)), 40.0]]),
    )

    assert result["status"] == "no_results"
    assert result["qualifying_price_found"] is False
    assert result["price_observation_id"] is None
    assert result["outcome_completion_input_eligible"] is False


@pytest.mark.parametrize(
    "captured_factory",
    [
        lambda request: _captured(
            request,
            [[_timestamp_ms(_DUE + timedelta(hours=1)), 41.0]],
            payload_updates={"unexpected": []},
        ),
        lambda request: _captured(request, [
            [_timestamp_ms(_DUE + timedelta(hours=1)), 41.0],
            [_timestamp_ms(_DUE + timedelta(hours=1)), 42.0],
        ]),
        lambda request: _captured(
            request,
            [[_timestamp_ms(_LATEST + timedelta(seconds=2)), 41.0]],
        ),
        lambda request: _captured(
            request,
            [[_timestamp_ms(_DUE + timedelta(hours=1)), "41.0"]],
        ),
    ],
)
def test_exact_response_rejects_schema_duplicate_range_and_unit_drift(captured_factory):
    request = _request()
    with pytest.raises(recovery.OutcomePriceRecoveryError):
        recovery.normalize_captured_recovery_response(
            request,
            captured_factory(request),
        )


def test_readiness_is_no_call_and_requires_both_authorizations(tmp_path):
    calls = {"report": 0, "provider": 0}

    def report_builder(*args, **kwargs):
        calls["report"] += 1
        return _report()

    def provider_state(*args, **kwargs):
        calls["provider"] += 1
        return _provider_allowed(*args, **kwargs)

    result = recovery.build_outcome_price_recovery_readiness(
        artifact_base_dir=tmp_path,
        environ={},
        now=_CHECKED,
        fixture_dir=None,
        report_builder=report_builder,
        provider_state_assessor=provider_state,
    )

    assert calls == {"report": 1, "provider": 1}
    assert result["status"] == "blocked"
    assert result["ready"] is False
    assert result["provider_call_attempted"] is False
    assert result["provider_requests_made"] == 0
    assert "general_coingecko_authorization_absent" in result["reasons"]
    assert "outcome_price_recovery_authorization_absent" in result["reasons"]
    assert result["authorization_mutated"] is False
    assert result["writes_performed"] is False
    assert "secret" not in result["campaign_pointer"]


def test_readiness_becomes_ready_without_call_or_write(tmp_path):
    env = {
        recovery.GENERAL_COINGECKO_AUTH_ENV: "1",
        recovery.LIVE_AUTH_ENV: "1",
    }

    first = recovery.build_outcome_price_recovery_readiness(
        artifact_base_dir=tmp_path,
        environ=env,
        now=_CHECKED,
        fixture_dir=None,
        report_builder=_builder(_report()),
        provider_state_assessor=_provider_allowed,
    )
    second = recovery.build_outcome_price_recovery_readiness(
        artifact_base_dir=tmp_path,
        environ=env,
        now=_CHECKED + timedelta(minutes=5),
        fixture_dir=None,
        report_builder=_builder(_report()),
        provider_state_assessor=_provider_allowed,
    )

    assert first["status"] == "ready"
    assert first["ready"] is True
    assert first["historical_recovery_request_count"] == 1
    assert first["provider_call_planned"] is True
    assert first["provider_call_attempted"] is False
    assert first["next_safe_command"] == recovery.COLLECT_COMMAND
    assert first["plan_digest"] == second["plan_digest"]
    assert first["immutable_capture_implemented"] is False
    assert first["calibration_eligible"] is False


def test_readiness_reports_no_work_when_no_gap_exists(tmp_path):
    result = recovery.build_outcome_price_recovery_readiness(
        artifact_base_dir=tmp_path,
        environ={
            recovery.GENERAL_COINGECKO_AUTH_ENV: "1",
            recovery.LIVE_AUTH_ENV: "1",
        },
        now=_CHECKED,
        fixture_dir=None,
        report_builder=_builder(_report(outcomes=_outcomes(gaps=[]))),
        provider_state_assessor=_provider_allowed,
    )

    assert result["status"] == "no_work"
    assert result["historical_recovery_request_count"] == 0
    assert result["provider_call_planned"] is False


def test_collect_requires_confirmation_before_fetch(tmp_path):
    called = False

    def fetch(*_args):
        nonlocal called
        called = True
        raise AssertionError("fetch must not run")

    with pytest.raises(recovery.OutcomePriceRecoveryError, match="explicit_confirmation_required"):
        recovery.collect_outcome_price_recovery(
            artifact_base_dir=tmp_path,
            confirm=False,
            fetch_exact=fetch,
        )
    assert called is False


def test_confirmed_collect_uses_one_exact_request_and_remains_no_write(tmp_path):
    env = {
        recovery.GENERAL_COINGECKO_AUTH_ENV: "1",
        recovery.LIVE_AUTH_ENV: "1",
    }
    fetch_count = 0

    def fetch(request, timeout):
        nonlocal fetch_count
        fetch_count += 1
        assert timeout == recovery.DEFAULT_TIMEOUT_SECONDS
        return _captured(
            request,
            [[_timestamp_ms(_DUE + timedelta(hours=1)), 41.0]],
        )

    clock_values = iter((_CHECKED, _CHECKED + timedelta(seconds=2)))
    result = recovery.collect_outcome_price_recovery(
        artifact_base_dir=tmp_path,
        confirm=True,
        environ=env,
        fixture_dir=None,
        report_builder=_builder(_report()),
        provider_state_assessor=_provider_allowed,
        fetch_exact=fetch,
        clock=lambda: next(clock_values),
    )

    assert fetch_count == 1
    assert result["status"] == "complete"
    assert result["provider_request_count"] == 1
    assert result["provider_retry_count"] == 0
    assert result["qualifying_price_count"] == 1
    assert result["artifact_persisted"] is False
    assert result["baseline_history_mutated"] is False
    assert result["campaign_outcomes_mutated"] is False
    assert result["authorization_mutated"] is False
    assert result["writes_performed"] is False


def test_collect_counts_a_failed_provider_attempt_without_retry(tmp_path):
    env = {
        recovery.GENERAL_COINGECKO_AUTH_ENV: "1",
        recovery.LIVE_AUTH_ENV: "1",
    }
    fetch_count = 0

    def fetch(_request, _timeout):
        nonlocal fetch_count
        fetch_count += 1
        raise recovery.OutcomePriceRecoveryError(
            "provider_http_error",
            http_status=429,
        )

    with pytest.raises(
        recovery.OutcomePriceRecoveryError,
        match="provider_http_error",
    ) as raised:
        recovery.collect_outcome_price_recovery(
            artifact_base_dir=tmp_path,
            confirm=True,
            environ=env,
            fixture_dir=None,
            report_builder=_builder(_report()),
            provider_state_assessor=_provider_allowed,
            fetch_exact=fetch,
            clock=lambda: _CHECKED,
        )

    assert fetch_count == 1
    assert raised.value.http_status == 429
    assert raised.value.request_count == 1


def test_request_projection_type_drift_fails_with_closed_error():
    projected = recovery.recovery_request_values(_request())
    projected["allowed_lag_seconds"] = None

    with pytest.raises(
        recovery.OutcomePriceRecoveryError,
        match="recovery_request_projection_invalid",
    ):
        recovery._request_from_dict(projected)


def test_collect_fails_closed_when_plan_changes_after_response(tmp_path):
    env = {
        recovery.GENERAL_COINGECKO_AUTH_ENV: "1",
        recovery.LIVE_AUTH_ENV: "1",
    }
    reports = iter((
        _report(outcomes=_outcomes(sha="b" * 64)),
        _report(outcomes=_outcomes(sha="d" * 64)),
    ))

    def changing_builder(*_args, **_kwargs):
        return next(reports)

    def fetch(request, _timeout):
        return _captured(
            request,
            [[_timestamp_ms(_DUE + timedelta(hours=1)), 41.0]],
        )

    clock_values = iter((_CHECKED, _CHECKED + timedelta(seconds=2)))
    with pytest.raises(
        recovery.OutcomePriceRecoveryError,
        match="recovery_plan_changed_after_provider_response",
    ) as raised:
        recovery.collect_outcome_price_recovery(
            artifact_base_dir=tmp_path,
            confirm=True,
            environ=env,
            fixture_dir=None,
            report_builder=changing_builder,
            provider_state_assessor=_provider_allowed,
            fetch_exact=fetch,
            clock=lambda: next(clock_values),
        )
    assert raised.value.request_count == 1


def test_make_targets_keep_readiness_separate_from_confirmed_collection():
    def dry_run(target: str, *, confirm: bool = False) -> str:
        command = ["make", "-n", target, "PYTHON=python3"]
        if confirm:
            command.append("CONFIRM=1")
        return subprocess.run(
            command,
            cwd=_REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    readiness = dry_run("radar-outcome-price-recovery-readiness")
    collection = dry_run("radar-outcome-price-recovery-collect")
    confirmed = dry_run("radar-outcome-price-recovery-collect", confirm=True)

    assert "outcome_price_recovery readiness" in readiness
    assert "outcome_price_recovery collect" not in readiness
    assert "outcome_price_recovery collect" in collection
    assert "--confirm" not in collection
    assert confirmed.count("--confirm") == 1
    assert recovery.LIVE_AUTH_ENV not in readiness
    assert f"{recovery.LIVE_AUTH_ENV}=1" not in collection
    assert "place-order" not in (readiness + collection + confirmed).casefold()
