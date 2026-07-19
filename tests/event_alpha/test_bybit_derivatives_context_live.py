"""Guarded Bybit venue-native derivatives live-boundary regressions."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from typing import Mapping
from urllib.parse import urlencode

import pytest

from crypto_rsi_scanner.event_alpha.operations.bybit_derivatives_context import (
    ACCOUNT_RATIO_PATH,
    FUNDING_HISTORY_PATH,
    OPEN_INTEREST_PATH,
    TICKERS_PATH,
    build_bybit_derivatives_requests,
)
from crypto_rsi_scanner.event_alpha.operations.bybit_derivatives_context_live import (
    AUTHORIZATION_ACTION,
    CAPTURE_COMMAND,
    COLLECT_COMMAND,
    CONTRACT_VERSION,
    LIVE_AUTH_ENV,
    READINESS_COMMAND,
    STATUS_COMMAND,
    BybitDerivativesContextLiveError,
    _collect_authoritative_bybit_derivatives,
    build_bybit_derivatives_live_readiness,
    capture_authoritative_bybit_derivatives,
    collect_authoritative_bybit_derivatives,
    main,
)
from crypto_rsi_scanner.event_alpha.operations.bybit_execution_quality import (
    PUBLIC_API_BASE,
    BybitPublicRequest,
    select_bybit_usdt_perpetual_instruments,
)
from crypto_rsi_scanner.event_alpha.operations.bybit_execution_quality_capture import (
    BybitCapturedJSONResponse,
    BybitExecutionQualityCaptureError,
)
from crypto_rsi_scanner.event_alpha.operations.bybit_execution_quality_live import (
    BybitExecutionQualityLiveError,
    _fetch_public_json,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
EXECUTION_FIXTURES = REPO_ROOT / "fixtures" / "bybit_execution_quality"
DERIVATIVES_FIXTURES = REPO_ROOT / "fixtures" / "bybit_derivatives_context"
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


def _instrument():
    selected = select_bybit_usdt_perpetual_instruments(
        _json(EXECUTION_FIXTURES / "radar_assets.json"),
        _json(EXECUTION_FIXTURES / "instruments_info.json"),
    )
    return next(row for row in selected if row.instrument_id == "BTCUSDT")


def _capture(capture_id: str = "b" * 64) -> dict[str, object]:
    return {
        "contract_version": "crypto_radar_bybit_execution_quality_capture_v3",
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


def _resolver(source: dict[str, object] | None = None):
    authority = AUTHORITY if source is None else source
    snapshot = SimpleNamespace(
        artifact_namespace=authority["artifact_namespace"],
        run_id=authority["run_id"],
        revision=authority["revision"],
        operator_state_sha256=authority["operator_state_sha256"],
        generation_authority_checked_at=authority["authority_checked_at"],
    )

    def resolve(_base: object, *, now: object) -> object:
        assert isinstance(now, datetime)
        return SimpleNamespace(snapshot=snapshot)

    return resolve


def _clock():
    ticks = iter(NOW + timedelta(milliseconds=100 * index) for index in range(40))
    return lambda: next(ticks)


def _fetch(request: BybitPublicRequest, timeout: float) -> dict[str, object]:
    assert timeout == 10.0
    value = _json(DERIVATIVES_FIXTURES / PATH_FIXTURES[request.path])
    assert isinstance(value, dict)
    return value


def _captured_fetch(
    request: BybitPublicRequest,
    timeout: float,
) -> BybitCapturedJSONResponse:
    payload = _fetch(request, timeout)
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


def test_readiness_without_execution_capture_or_auth_is_zero_call_and_closed() -> None:
    def missing(_base: object) -> dict[str, object]:
        raise BybitExecutionQualityCaptureError("capture_pointer_missing")

    payload = build_bybit_derivatives_live_readiness(
        artifact_base_dir="unused",
        environ={},
        now=NOW,
        capture_loader=missing,
        resolver=_resolver(),
    )

    assert payload["contract_version"] == CONTRACT_VERSION
    assert payload["status"] == "blocked"
    assert payload["reasons"] == [
        "execution_quality_capture_unavailable",
        "runtime_provider_authorization_absent",
    ]
    assert payload["maximum_provider_requests_for_current_capture"] == 0
    assert payload["provider_call_attempted"] is False
    assert payload["writes_performed"] is False
    assert payload["next_safe_command"] == READINESS_COMMAND


def test_current_execution_capture_requires_separate_derivatives_auth() -> None:
    payload = build_bybit_derivatives_live_readiness(
        artifact_base_dir="unused",
        environ={},
        now=NOW,
        capture_loader=lambda _base: _capture(),
        resolver=_resolver(),
    )

    assert payload["reasons"] == ["runtime_provider_authorization_absent"]
    assert payload["operator_action_required"] == AUTHORIZATION_ACTION
    assert payload["eligible_instrument_count"] == 1
    assert payload["maximum_provider_requests_for_current_capture"] == 4
    assert payload["composite_freshness_policy"] == (
        "oldest_required_provider_response"
    )
    assert payload["immutable_capture_implemented"] is True
    assert payload["capture_publication_available"] is True
    assert payload["latest_derivatives_capture_status"] == "unavailable"
    assert payload["immutable_capture_command"] == CAPTURE_COMMAND
    assert payload["capture_status_command"] == STATUS_COMMAND
    assert payload["expected_provider_activity"] == "none_readiness_only"


def test_authorized_readiness_is_exact_but_still_no_call_or_write() -> None:
    payload = build_bybit_derivatives_live_readiness(
        artifact_base_dir="unused",
        environ={LIVE_AUTH_ENV: "1"},
        now=NOW,
        capture_loader=lambda _base: _capture(),
        resolver=_resolver(),
    )

    assert payload["ready"] is True
    assert payload["reasons"] == []
    assert payload["source_execution_quality_capture_id"] == "b" * 64
    assert payload["next_safe_command"] == COLLECT_COMMAND
    assert payload["expected_provider_activity"] == (
        "collect_exactly_4_public_GETs_no_retries"
    )
    assert payload["provider_call_planned"] is False
    assert payload["artifact_persisted"] is False
    assert payload["directional_authority"] is False


def test_confirmed_capture_seals_only_exact_transport_responses(
    tmp_path: Path,
) -> None:
    result = capture_authoritative_bybit_derivatives(
        artifact_base_dir=tmp_path,
        environ={LIVE_AUTH_ENV: "1"},
        now=_clock(),
        capture_loader=lambda _base: _capture(),
        resolver=_resolver(),
        fetch_json=_captured_fetch,
    )

    assert result["status"] == "complete"
    assert result["immutable_capture_persisted"] is True
    assert result["request_count"] == 4
    assert result["context_count"] == 1
    assert result["protocol_v2_input_quality_eligible"] is True
    assert result["protocol_v2_evidence_eligible"] is False
    assert result["campaign_attached"] is False
    assert result["pointer_validated"] is True
    assert result["directional_authority"] is False


def test_stale_or_drifted_execution_capture_cannot_unlock_derivatives() -> None:
    stale = deepcopy(_capture())
    stale["protocol_v2_input_quality_eligible"] = False
    payload = build_bybit_derivatives_live_readiness(
        artifact_base_dir="unused",
        environ={LIVE_AUTH_ENV: "1"},
        now=NOW,
        capture_loader=lambda _base: stale,
        resolver=_resolver(),
    )
    assert payload["reasons"] == [
        "execution_quality_capture_not_input_quality_eligible"
    ]

    drifted = dict(AUTHORITY)
    drifted["run_id"] = "different|no_key_live"
    payload = build_bybit_derivatives_live_readiness(
        artifact_base_dir="unused",
        environ={LIVE_AUTH_ENV: "1"},
        now=NOW,
        capture_loader=lambda _base: _capture(),
        resolver=_resolver(drifted),
    )
    assert payload["reasons"] == [
        "execution_quality_capture_not_current_authority"
    ]


def test_collection_without_auth_stops_before_fetch() -> None:
    calls = 0

    def forbidden(_request: object, _timeout: float) -> dict[str, object]:
        nonlocal calls
        calls += 1
        raise AssertionError("provider boundary crossed")

    with pytest.raises(BybitDerivativesContextLiveError, match="authorization_absent"):
        collect_authoritative_bybit_derivatives(
            artifact_base_dir="unused",
            environ={},
            now=_clock(),
            capture_loader=lambda _base: _capture(),
            resolver=_resolver(),
            fetch_json=forbidden,
        )

    assert calls == 0


def test_authorized_collection_gets_exact_context_without_writes_or_policy() -> None:
    requests: list[BybitPublicRequest] = []

    def fetch(request: BybitPublicRequest, timeout: float) -> dict[str, object]:
        requests.append(request)
        return _fetch(request, timeout)

    payload = collect_authoritative_bybit_derivatives(
        artifact_base_dir="unused",
        environ={LIVE_AUTH_ENV: "1"},
        now=_clock(),
        capture_loader=lambda _base: _capture(),
        resolver=_resolver(),
        fetch_json=fetch,
    )

    assert [request.path for request in requests] == list(PATH_FIXTURES)
    assert payload["status"] == "complete"
    assert payload["context_count"] == 1
    assert payload["composite_freshness_policy"] == (
        "oldest_required_provider_response"
    )
    assert payload["provider_request_count"] == payload["provider_request_bound"] == 4
    assert payload["all_context_fresh"] is True
    assert payload["all_context_fresh_at_acquisition"] is True
    assert payload["all_context_fresh_at_completion"] is True
    assert payload["maximum_context_age_at_completion_seconds"] == 0.9
    assert payload["retries"] == payload["redirects_followed"] == 0
    assert len(payload["request_timing"]) == 4
    assert payload["artifact_persisted"] is False
    assert payload["context_only"] is True
    assert payload["directional_authority"] is False
    assert payload["decision_policy_applied"] is False
    assert payload["protocol_v2_input_quality_eligible"] is False
    assert payload["protocol_v2_evidence_eligible"] is False
    assert payload["writes_performed"] is False
    assert payload["orders_available"] is False
    assert payload["trades_created"] == payload["telegram_sends"] == 0


def test_exact_transport_responses_are_retained_in_memory_but_not_persisted() -> None:
    payload, responses = _collect_authoritative_bybit_derivatives(
        artifact_base_dir="unused",
        environ={LIVE_AUTH_ENV: "1"},
        now=_clock(),
        capture_loader=lambda _base: _capture(),
        resolver=_resolver(),
        fetch_json=_captured_fetch,
    )

    assert len(responses) == 4
    assert payload["exact_response_capture_count"] == 4
    assert payload["exact_response_capture_available"] is True
    assert payload["artifact_persisted"] is False
    assert payload["immutable_capture_implemented"] is False


def test_collection_stops_on_first_region_failure_without_retry() -> None:
    calls = 0

    def fail_second(
        request: BybitPublicRequest,
        _timeout: float,
    ) -> dict[str, object]:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise BybitExecutionQualityLiveError(
                "provider_http_error",
                provider_status="region_restricted",
                http_status=403,
            )
        return _fetch(request, 10.0)

    with pytest.raises(BybitDerivativesContextLiveError) as captured:
        collect_authoritative_bybit_derivatives(
            artifact_base_dir="unused",
            environ={LIVE_AUTH_ENV: "1"},
            now=_clock(),
            capture_loader=lambda _base: _capture(),
            resolver=_resolver(),
            fetch_json=fail_second,
        )

    assert captured.value.reason_code == "provider_http_error"
    assert captured.value.provider_status == "region_restricted"
    assert captured.value.http_status == 403
    assert captured.value.request_count == 2
    assert calls == 2


def test_post_response_execution_capture_drift_fails_closed() -> None:
    captures = iter((_capture("b" * 64), _capture("c" * 64)))

    with pytest.raises(BybitDerivativesContextLiveError, match="prerequisite_drifted"):
        collect_authoritative_bybit_derivatives(
            artifact_base_dir="unused",
            environ={LIVE_AUTH_ENV: "1"},
            now=_clock(),
            capture_loader=lambda _base: next(captures),
            resolver=_resolver(),
            fetch_json=_fetch,
        )


class _FakeResponse:
    status = 200
    headers = {"Content-Type": "application/json"}

    def __init__(self, url: str, payload: Mapping[str, object]) -> None:
        self._url = url
        self._raw = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def getcode(self) -> int:
        return 200

    def geturl(self) -> str:
        return self._url

    def read(self, _size: int) -> bytes:
        return self._raw


class _FakeOpener:
    def __init__(self, payload: Mapping[str, object]) -> None:
        self.payload = payload

    def open(self, request: object, *, timeout: float) -> _FakeResponse:
        assert timeout == 10.0
        return _FakeResponse(request.full_url, self.payload)


@pytest.mark.parametrize(
    "public_request", build_bybit_derivatives_requests((_instrument(),))
)
def test_fixed_host_transport_accepts_only_closed_derivatives_requests(
    public_request: BybitPublicRequest,
) -> None:
    payload = _json(DERIVATIVES_FIXTURES / PATH_FIXTURES[public_request.path])
    assert isinstance(payload, dict)

    captured = _fetch_public_json(
        public_request, 10.0, opener=_FakeOpener(payload)
    )

    assert captured.request == public_request
    assert captured.http_status == 200
    assert captured.payload() == payload


def test_fixed_host_transport_rejects_broadened_derivatives_request() -> None:
    invalid = BybitPublicRequest(
        method="GET",
        path=FUNDING_HISTORY_PATH,
        query=(("category", "linear"), ("symbol", "BTCUSDT"), ("limit", "200")),
    )

    with pytest.raises(
        BybitExecutionQualityLiveError, match="public_request_contract_invalid"
    ):
        _fetch_public_json(invalid, 10.0, opener=object())


def test_cli_and_make_targets_keep_readiness_separate_from_confirmed_collection(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(LIVE_AUTH_ENV, "1")
    assert main(["collect", "--artifact-base", str(tmp_path)]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["reason"] == "explicit_collection_confirmation_required"
    assert payload["provider_request_count"] == 0
    assert payload["writes_performed"] is False
    assert main(["capture", "--artifact-base", str(tmp_path)]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["reason"] == "explicit_collection_confirmation_required"
    assert payload["provider_request_count"] == 0
    assert main(["status", "--artifact-base", str(tmp_path)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "unavailable"
    assert payload["provider_call_attempted"] is False

    def dry_run(target: str, *, confirm: bool = False) -> str:
        command = ["make", "-n", target, "PYTHON=python3"]
        if confirm:
            command.append("CONFIRM=1")
        return subprocess.run(
            command,
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    readiness = dry_run("radar-derivatives-bybit-readiness")
    collection = dry_run("radar-derivatives-bybit-collect")
    confirmed = dry_run("radar-derivatives-bybit-collect", confirm=True)
    capture = dry_run("radar-derivatives-bybit-capture")
    confirmed_capture = dry_run("radar-derivatives-bybit-capture", confirm=True)
    status = dry_run("radar-derivatives-bybit-status")
    assert "bybit_derivatives_context_live readiness" in readiness
    assert "bybit_derivatives_context_live collect" not in readiness
    assert "bybit_derivatives_context_live collect" in collection
    assert "--confirm" not in collection
    assert confirmed.count("--confirm") == 1
    assert "bybit_derivatives_context_live capture" in capture
    assert "--confirm" not in capture
    assert confirmed_capture.count("--confirm") == 1
    assert "bybit_derivatives_context_live status" in status
    assert "--confirm" not in status
    assert LIVE_AUTH_ENV not in readiness
    assert f"{LIVE_AUTH_ENV}=1" not in collection
