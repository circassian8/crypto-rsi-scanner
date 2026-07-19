"""Guarded Bybit execution-quality live-boundary regressions."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from typing import Mapping
from urllib.error import HTTPError
from urllib.request import ProxyHandler, build_opener

import pytest

from crypto_rsi_scanner.event_alpha.dashboard.readiness import DashboardReadinessError
from crypto_rsi_scanner.event_alpha.operations.bybit_execution_quality import (
    REQUEST_STRATEGY,
    BybitPublicRequest,
    build_bybit_instrument_catalog_request,
)
from crypto_rsi_scanner.event_alpha.operations.bybit_execution_quality_live import (
    AUTHORIZATION_ACTION,
    CAPTURE_COMMAND,
    CONTRACT_VERSION,
    LIVE_AUTH_ENV,
    MAX_PROVIDER_REQUESTS,
    READINESS_COMMAND,
    BybitExecutionQualityLiveError,
    _build_public_opener,
    _fetch_public_json,
    build_bybit_execution_quality_live_readiness,
    collect_authoritative_bybit_execution_quality,
    main,
    partition_bybit_provider_query_assets,
    project_authoritative_radar_assets,
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


def test_authoritative_projection_ranks_liquidity_and_rejects_provenance_drift() -> None:
    rows = (
        _observation("ethereum", "eth", 2_000.0),
        _observation("bitcoin", "btc", 3_000.0),
    )

    projected = project_authoritative_radar_assets(rows)

    assert [row["canonical_asset_id"] for row in projected] == ["bitcoin", "ethereum"]
    assert [row["symbol"] for row in projected] == ["BTC", "ETH"]
    assert [row["liquidity_rank"] for row in projected] == [1, 2]

    invalid = deepcopy(rows[0])
    invalid["data_mode"] = "fixture"
    with pytest.raises(BybitExecutionQualityLiveError, match="provenance_invalid"):
        project_authoritative_radar_assets((invalid,))


def test_readiness_is_no_call_and_requires_exact_authority_plus_explicit_auth() -> None:
    calls: list[str] = []

    def resolve(_base: object, *, now: object) -> object:
        calls.append("resolve")
        return _resolver((_observation("bitcoin", "BTC", 3_000.0),))(
            _base, now=now
        )

    payload = build_bybit_execution_quality_live_readiness(
        artifact_base_dir="unused",
        environ={},
        now=NOW,
        resolver=resolve,
    )

    assert calls == ["resolve"]
    assert payload["contract_version"] == CONTRACT_VERSION
    assert payload["status"] == "blocked"
    assert payload["runtime_provider_authorized"] is False
    assert payload["provider_call_planned"] is False
    assert payload["provider_call_attempted"] is False
    assert payload["evidence_authority_eligible"] is False
    assert payload["capture_publication_available"] is True
    assert payload["latest_capture_status"] == "unavailable"
    assert payload["evidence_publication_status"] == "no_immutable_capture_available"
    assert payload["maximum_provider_requests_for_current_universe"] == 2
    assert payload["provider_request_strategy"] == REQUEST_STRATEGY
    assert payload["instrument_catalog_request_bound"] == 1
    assert payload["orderbook_request_bound"] == 1
    assert payload["execution_quality_set_freshness_policy"] == (
        "every_book_fresh_at_capture_completion"
    )
    assert payload["maximum_execution_quality_age_policy_seconds"] == 15.0
    assert payload["reasons"] == ["runtime_provider_authorization_absent"]
    assert payload["operator_action_required"] == AUTHORIZATION_ACTION
    assert payload["authorization_action_required"] == AUTHORIZATION_ACTION
    assert payload["next_safe_command"] == READINESS_COMMAND
    assert payload["readiness_recheck_command"] == READINESS_COMMAND
    assert payload["authorized_capture_command"] == CAPTURE_COMMAND
    assert payload["authorization_mutated"] is False
    assert payload["capture_confirmation_required"] is True
    assert payload["expected_provider_activity"] == "none_readiness_only"
    assert payload["expected_provider_activity_if_authorized_and_confirmed"] == (
        "collect_at_most_2_public_GETs_no_retries"
    )
    assert payload["credentials_read"] is False
    assert payload["orders_available"] is False
    assert payload["writes_performed"] is False


def test_readiness_fails_closed_when_current_generation_is_not_authoritative() -> None:
    def unavailable(_base: object, *, now: object) -> object:
        raise DashboardReadinessError("generation is stale")

    payload = build_bybit_execution_quality_live_readiness(
        artifact_base_dir="unused",
        environ={LIVE_AUTH_ENV: "1"},
        now=NOW,
        resolver=unavailable,
    )

    assert payload["status"] == "blocked"
    assert payload["runtime_provider_authorized"] is True
    assert payload["current_authority"] is None
    assert payload["radar_assets"] == []
    assert payload["reasons"] == ["authoritative_market_generation_unavailable"]
    assert payload["operator_action_required"] == (
        "resolve_readiness_reasons_then_rerun_readiness"
    )
    assert payload["authorization_action_required"] == "none"
    assert payload["expected_provider_activity"] == "none_readiness_only"


def test_non_contract_symbol_is_excluded_before_provider_without_hiding_authority() -> None:
    observations = (
        _observation("bitcoin", "BTC", 3_000.0),
        _observation("figure-heloc", "FIGR_HELOC", 2_000.0),
    )
    projected = project_authoritative_radar_assets(observations)
    requestable, excluded = partition_bybit_provider_query_assets(projected)

    assert [row["canonical_asset_id"] for row in requestable] == ["bitcoin"]
    assert excluded == ({
        "canonical_asset_id": "figure-heloc",
        "symbol": "FIGR_HELOC",
        "liquidity_rank": 2,
        "liquidity_usd": 2_000.0,
        "reason_code": "radar_symbol_not_bybit_base_contract_shape",
    },)

    readiness = build_bybit_execution_quality_live_readiness(
        artifact_base_dir="unused",
        environ={LIVE_AUTH_ENV: "1"},
        now=NOW,
        resolver=_resolver(observations),
    )
    assert readiness["ready"] is True
    assert readiness["radar_asset_count"] == 2
    assert readiness["provider_query_asset_count"] == 1
    assert readiness["preflight_excluded_asset_count"] == 1
    assert readiness["maximum_provider_requests_for_current_universe"] == 2
    assert readiness["operator_action_required"] == "none"
    assert readiness["authorization_action_required"] == "none"
    assert readiness["next_safe_command"] == CAPTURE_COMMAND
    assert readiness["expected_provider_activity"] == (
        "collect_at_most_2_public_GETs_no_retries"
    )


def test_collection_without_authorization_stops_before_fetch() -> None:
    called = False

    def forbidden_fetch(_request: object, _timeout: float) -> dict[str, object]:
        nonlocal called
        called = True
        raise AssertionError("provider boundary must not be crossed")

    with pytest.raises(BybitExecutionQualityLiveError, match="authorization_absent"):
        collect_authoritative_bybit_execution_quality(
            artifact_base_dir="unused",
            environ={},
            now=lambda: NOW,
            resolver=_resolver((_observation("bitcoin", "BTC", 3_000.0),)),
            fetch_json=forbidden_fetch,
        )

    assert called is False


def test_authorized_collection_with_no_requestable_asset_stops_before_fetch() -> None:
    called = False

    def forbidden_fetch(_request: object, _timeout: float) -> dict[str, object]:
        nonlocal called
        called = True
        raise AssertionError("provider boundary must not be crossed")

    observations = (_observation("figure-heloc", "FIGR_HELOC", 3_000.0),)
    readiness = build_bybit_execution_quality_live_readiness(
        artifact_base_dir="unused",
        environ={LIVE_AUTH_ENV: "1"},
        now=NOW,
        resolver=_resolver(observations),
    )
    assert readiness["ready"] is False
    assert readiness["provider_query_asset_count"] == 0
    assert readiness["preflight_excluded_asset_count"] == 1
    assert readiness["maximum_provider_requests_for_current_universe"] == 0
    assert readiness["reasons"] == ["bybit_provider_query_universe_empty"]

    with pytest.raises(
        BybitExecutionQualityLiveError,
        match="bybit_provider_query_universe_empty",
    ):
        collect_authoritative_bybit_execution_quality(
            artifact_base_dir="unused",
            environ={LIVE_AUTH_ENV: "1"},
            now=lambda: NOW,
            resolver=_resolver(observations),
            fetch_json=forbidden_fetch,
        )

    assert called is False


def test_authorized_mock_collection_selects_exact_active_perps_and_normalizes_books() -> None:
    observations = (
        _observation("ethereum", "ETH", 2_000.0),
        _observation("pepe", "PEPE", 1_000.0),
        _observation("bitcoin", "BTC", 3_000.0),
        _observation("figure-heloc", "FIGR_HELOC", 1_500.0),
    )
    requests: list[BybitPublicRequest] = []

    def fetch(request: BybitPublicRequest, timeout: float) -> Mapping[str, object]:
        assert timeout == 10.0
        requests.append(request)
        query = dict(request.query)
        if request.path.endswith("instruments-info"):
            return deepcopy(_fixture("instruments_info.json"))
        prices = {"BTCUSDT": 100.0, "ETHUSDT": 50.0}
        return _orderbook_payload(query["symbol"], prices[query["symbol"]])

    result = collect_authoritative_bybit_execution_quality(
        artifact_base_dir="unused",
        environ={LIVE_AUTH_ENV: "1"},
        now=lambda: NOW,
        resolver=_resolver(observations),
        fetch_json=fetch,
    )

    assert result["status"] == "complete"
    assert result["source_authority"]["artifact_namespace"] == (
        "radar_market_no_send_live_exact"
    )
    assert result["requested_radar_asset_count"] == 4
    assert result["provider_query_asset_count"] == 3
    assert result["preflight_excluded_asset_count"] == 1
    assert result["preflight_excluded_assets"][0]["canonical_asset_id"] == (
        "figure-heloc"
    )
    assert [row["instrument_id"] for row in result["eligible_instruments"]] == [
        "BTCUSDT",
        "ETHUSDT",
    ]
    assert result["execution_quality_snapshot_count"] == 2
    assert result["provider_request_count"] == 3
    assert result["provider_request_bound"] == 4
    assert result["provider_request_strategy"] == REQUEST_STRATEGY
    assert result["instrument_catalog_request_count"] == 1
    assert result["orderbook_request_count"] == 2
    assert result["provider_request_count"] <= result["provider_request_bound"] <= MAX_PROVIDER_REQUESTS
    assert result["retries"] == 0
    assert result["redirects_followed"] == 0
    assert result["artifact_persisted"] is False
    assert result["campaign_attached"] is False
    assert result["evidence_authority_eligible"] is False
    assert result["protocol_v2_evidence_eligible"] is False
    assert result["execution_quality_set_freshness_policy"] == (
        "every_book_fresh_at_capture_completion"
    )
    assert result["all_execution_quality_fresh_at_acquisition"] is True
    assert result["all_execution_quality_fresh_at_completion"] is True
    assert result["all_execution_quality_fresh"] is True
    assert result["maximum_execution_quality_age_at_completion_seconds"] == 1.0
    assert result["maximum_execution_quality_age_policy_seconds"] == 15.0
    assert all(row["freshness_status"] == "fresh" for row in result["execution_quality_snapshots"])
    assert all(row["notional_currency"] == "USDT" for row in result["execution_quality_snapshots"])
    assert all(row["research_only"] is True for row in result["execution_quality_snapshots"])
    assert result["credentials_read"] is False
    assert result["private_data_read"] is False
    assert result["orders_available"] is False
    assert result["writes_performed"] is False
    assert [request.path for request in requests].count("/v5/market/instruments-info") == 1
    assert [request.path for request in requests].count("/v5/market/orderbook") == 2
    assert all("FIGR_HELOC" not in str(request.query) for request in requests)


def test_sequential_books_can_be_fresh_when_acquired_but_stale_at_set_completion() -> None:
    observations = (
        _observation("bitcoin", "BTC", 3_000.0),
        _observation("ethereum", "ETH", 2_000.0),
    )
    started = datetime(2026, 7, 17, 12, 0, 0, 500_000, tzinfo=timezone.utc)
    clock_values = iter(
        (
            started,
            datetime(2026, 7, 17, 12, 0, 1, tzinfo=timezone.utc),
            datetime(2026, 7, 17, 12, 0, 14, tzinfo=timezone.utc),
            datetime(2026, 7, 17, 12, 0, 16, tzinfo=timezone.utc),
        )
    )

    def fetch(request: BybitPublicRequest, _timeout: float) -> Mapping[str, object]:
        query = dict(request.query)
        if request.path.endswith("instruments-info"):
            return deepcopy(_fixture("instruments_info.json"))
        prices = {"BTCUSDT": 100.0, "ETHUSDT": 50.0}
        return _orderbook_payload(query["symbol"], prices[query["symbol"]])

    result = collect_authoritative_bybit_execution_quality(
        artifact_base_dir="unused",
        environ={LIVE_AUTH_ENV: "1"},
        now=lambda: next(clock_values),
        resolver=_resolver(observations, expected_now=started),
        fetch_json=fetch,
    )

    assert [
        row["freshness_status"] for row in result["execution_quality_snapshots"]
    ] == ["fresh", "fresh"]
    assert result["all_execution_quality_fresh_at_acquisition"] is True
    assert result["all_execution_quality_fresh_at_completion"] is False
    assert result["all_execution_quality_fresh"] is False
    assert result["maximum_execution_quality_age_at_completion_seconds"] == 16.0
    assert result["maximum_execution_quality_age_policy_seconds"] == 15.0


def test_provider_metadata_with_no_eligible_contract_fails_before_orderbook() -> None:
    requests: list[BybitPublicRequest] = []

    def fetch(request: BybitPublicRequest, _timeout: float) -> Mapping[str, object]:
        requests.append(request)
        payload = deepcopy(_fixture("instruments_info.json"))
        payload["result"]["list"] = []
        return payload

    with pytest.raises(BybitExecutionQualityLiveError) as captured:
        collect_authoritative_bybit_execution_quality(
            artifact_base_dir="unused",
            environ={LIVE_AUTH_ENV: "1"},
            now=lambda: NOW,
            resolver=_resolver((_observation("bitcoin", "BTC", 3_000.0),)),
            fetch_json=fetch,
        )

    assert captured.value.reason_code == "eligible_instrument_set_empty"
    assert captured.value.request_count == 1
    assert [request.path for request in requests] == [
        "/v5/market/instruments-info"
    ]


def test_partial_instrument_catalog_fails_before_any_orderbook() -> None:
    requests: list[BybitPublicRequest] = []

    def fetch(request: BybitPublicRequest, _timeout: float) -> Mapping[str, object]:
        requests.append(request)
        payload = deepcopy(_fixture("instruments_info.json"))
        payload["result"]["nextPageCursor"] = "continuation"
        return payload

    with pytest.raises(BybitExecutionQualityLiveError) as captured:
        collect_authoritative_bybit_execution_quality(
            artifact_base_dir="unused",
            environ={LIVE_AUTH_ENV: "1"},
            now=lambda: NOW,
            resolver=_resolver((_observation("bitcoin", "BTC", 3_000.0),)),
            fetch_json=fetch,
        )

    assert captured.value.reason_code == "provider_payload_contract_invalid"
    assert captured.value.request_count == 1
    assert requests == [build_bybit_instrument_catalog_request()]


class _FakeResponse:
    def __init__(self, url: str, payload: Mapping[str, object]) -> None:
        self.status = 200
        self._url = url
        self.headers = {"Content-Type": "application/json"}
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_args: object) -> bool:
        return False

    def getcode(self) -> int:
        return self.status

    def geturl(self) -> str:
        return self._url

    def read(self, _limit: int) -> bytes:
        return self._body


class _FakeOpener:
    def __init__(self, payload: Mapping[str, object]) -> None:
        self.payload = payload
        self.requests: list[object] = []

    def open(self, request: object, *, timeout: float) -> _FakeResponse:
        assert timeout == 10.0
        self.requests.append(request)
        return _FakeResponse(request.full_url, self.payload)


def test_transport_uses_fixed_public_get_without_credentials_or_redirects() -> None:
    payload = deepcopy(_fixture("instruments_info.json"))
    opener = _FakeOpener(payload)
    request = build_bybit_instrument_catalog_request()

    captured = _fetch_public_json(request, 10.0, opener=opener)
    assert captured.payload() == payload
    assert captured.raw_bytes == json.dumps(payload).encode("utf-8")
    assert dict(request.query) == {
        "category": "linear",
        "status": "Trading",
        "limit": "1000",
    }
    sent = opener.requests[0]
    headers = {key.casefold(): value for key, value in sent.header_items()}
    assert sent.get_method() == "GET"
    assert sent.full_url.startswith("https://api.bybit.com/v5/market/instruments-info?")
    assert "authorization" not in headers
    assert "cookie" not in headers
    assert "api-key" not in headers
    assert headers["accept"] == "application/json"
    assert "cdn-request-id" in headers

    symbol_scoped = BybitPublicRequest(
        method="GET",
        path="/v5/market/instruments-info",
        query=(("category", "linear"), ("symbol", "BTCUSDT")),
    )
    with pytest.raises(BybitExecutionQualityLiveError, match="request_contract"):
        _fetch_public_json(symbol_scoped, 10.0, opener=_FakeOpener(payload))


def test_transport_accepts_only_the_closed_direct_kline_query_shape() -> None:
    payload = json.loads(
        (
            REPO_ROOT
            / "fixtures"
            / "bybit_intraday"
            / "klines_btcusdt_60.json"
        ).read_text(encoding="utf-8")
    )
    request = BybitPublicRequest(
        method="GET",
        path="/v5/market/kline",
        query=(
            ("category", "linear"),
            ("symbol", "BTCUSDT"),
            ("interval", "60"),
            ("end", "1784289599999"),
            ("limit", "2"),
        ),
    )

    captured = _fetch_public_json(request, 10.0, opener=_FakeOpener(payload))

    assert captured.payload() == payload
    assert captured.request == request
    assert captured.response_url.startswith(
        "https://api.bybit.com/v5/market/kline?"
    )

    invalid = BybitPublicRequest(
        method="GET",
        path=request.path,
        query=tuple(
            (key, "3" if key == "limit" else value)
            for key, value in request.query
        ),
    )
    with pytest.raises(BybitExecutionQualityLiveError, match="request_contract"):
        _fetch_public_json(invalid, 10.0, opener=_FakeOpener(payload))


def test_default_transport_ignores_ambient_proxy_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid:9999")

    ambient_handlers = [
        handler
        for handler in build_opener().handlers
        if isinstance(handler, ProxyHandler)
    ]
    direct_handlers = [
        handler
        for handler in _build_public_opener().handlers
        if isinstance(handler, ProxyHandler)
    ]

    assert ambient_handlers[0].proxies["https"] == "http://proxy.invalid:9999"
    assert direct_handlers == []


class _ForbiddenOpener:
    def open(self, request: object, *, timeout: float) -> object:
        del timeout
        raise HTTPError(
            request.full_url,
            403,
            "Forbidden",
            {"Content-Type": "application/json"},
            BytesIO(b'{"retCode":10009,"retMsg":"unavailable for your region"}'),
        )


def test_transport_classifies_recorded_403_and_never_retries() -> None:
    request = build_bybit_instrument_catalog_request()

    with pytest.raises(BybitExecutionQualityLiveError) as captured:
        _fetch_public_json(request, 10.0, opener=_ForbiddenOpener())

    assert captured.value.reason_code == "provider_http_error"
    assert captured.value.provider_status == "region_restricted"
    assert captured.value.http_status == 403


def test_transport_classifies_region_restriction_inside_http_200_payload() -> None:
    request = build_bybit_instrument_catalog_request()
    payload = {"retCode": 10009, "retMsg": "unavailable for your region"}

    with pytest.raises(BybitExecutionQualityLiveError) as captured:
        _fetch_public_json(request, 10.0, opener=_FakeOpener(payload))

    assert captured.value.reason_code == "provider_api_error"
    assert captured.value.provider_status == "region_restricted"
    assert captured.value.http_status is None


def test_readiness_cli_on_untrusted_local_pointer_is_safe_and_no_call(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.delenv(LIVE_AUTH_ENV, raising=False)
    monkeypatch.setenv("BYBIT_API_SECRET", "must-not-print")

    assert main(["readiness", "--artifact-base", str(tmp_path)]) == 0
    output = capsys.readouterr()
    payload = json.loads(output.out)

    assert output.err == ""
    assert payload["status"] == "blocked"
    assert payload["provider_call_attempted"] is False
    assert payload["writes_performed"] is False
    assert "must-not-print" not in output.out


def test_collect_cli_requires_explicit_confirmation_before_any_boundary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(LIVE_AUTH_ENV, "1")

    assert main(["collect", "--artifact-base", str(tmp_path)]) == 1
    payload = json.loads(capsys.readouterr().out)

    assert payload["reason"] == "explicit_collection_confirmation_required"
    assert payload["provider_request_count"] == 0
    assert payload["provider_request_succeeded"] is False
    assert payload["writes_performed"] is False


def test_make_targets_keep_readiness_separate_from_authorized_collection() -> None:
    def dry_run(target: str) -> str:
        return subprocess.run(
            ["make", "-n", target, "PYTHON=python3"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    readiness = dry_run("radar-execution-quality-bybit-readiness")
    collection = dry_run("radar-execution-quality-bybit-collect")
    capture = dry_run("radar-execution-quality-bybit-capture")
    status = dry_run("radar-execution-quality-bybit-status")
    confirmed = subprocess.run(
        [
            "make",
            "-n",
            "radar-execution-quality-bybit-collect",
            "PYTHON=python3",
            "CONFIRM=1",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    confirmed_capture = subprocess.run(
        [
            "make",
            "-n",
            "radar-execution-quality-bybit-capture",
            "PYTHON=python3",
            "CONFIRM=1",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    assert "bybit_execution_quality_live readiness" in readiness
    assert "bybit_execution_quality_live collect" not in readiness
    assert "bybit_execution_quality_live collect" in collection
    assert "bybit_execution_quality_live capture" in capture
    assert "bybit_execution_quality_live status" in status
    assert "--confirm" not in collection
    assert "--confirm" not in capture
    assert confirmed.count("--confirm") == 1
    assert confirmed_capture.count("--confirm") == 1
    assert LIVE_AUTH_ENV not in readiness
    assert f"{LIVE_AUTH_ENV}=1" not in collection
    lowered = (
        f"{readiness}\n{collection}\n{capture}\n{status}\n"
        f"{confirmed}\n{confirmed_capture}"
    ).casefold()
    assert "place-order" not in lowered
    assert "execute-order" not in lowered
