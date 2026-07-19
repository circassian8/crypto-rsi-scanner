"""Guarded Bybit direct 1h/4h live-boundary regressions."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest

from crypto_rsi_scanner.event_alpha.operations.bybit_execution_quality import (
    PUBLIC_API_BASE,
    BybitPublicRequest,
    select_bybit_usdt_perpetual_instruments,
)
from crypto_rsi_scanner.event_alpha.operations.bybit_execution_quality_capture import (
    BybitCapturedJSONResponse,
    BybitExecutionQualityCaptureError,
)
from crypto_rsi_scanner.event_alpha.operations.bybit_intraday_capture import (
    POINTER_FILENAME,
)
from crypto_rsi_scanner.event_alpha.operations.bybit_intraday_live import (
    AUTHORIZATION_ACTION,
    CAPTURE_COMMAND,
    COLLECT_COMMAND,
    CONTRACT_VERSION,
    LIVE_AUTH_ENV,
    READINESS_COMMAND,
    BybitIntradayLiveError,
    build_bybit_intraday_live_readiness,
    capture_authoritative_bybit_intraday,
    collect_authoritative_bybit_intraday,
    main,
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


def _capture(capture_id: str = "b" * 64) -> dict[str, object]:
    return {
        "contract_version": "crypto_radar_bybit_execution_quality_capture_v4",
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


def _clock(*, completed_offset_ms: int = 1_000):
    ticks = iter(
        (
            NOW,
            NOW + timedelta(milliseconds=200),
            NOW + timedelta(milliseconds=400),
            NOW + timedelta(milliseconds=600),
            NOW + timedelta(milliseconds=800),
            NOW + timedelta(milliseconds=completed_offset_ms),
        )
    )
    return lambda: next(ticks)


def _fetch(request: object, timeout: float) -> dict[str, object]:
    assert timeout == 10.0
    interval = dict(request.query)["interval"]
    value = _json(INTRADAY_FIXTURES / f"klines_btcusdt_{interval}.json")
    assert isinstance(value, dict)
    return value


def _captured_fetch(
    request: BybitPublicRequest,
    timeout: float,
) -> BybitCapturedJSONResponse:
    payload = _fetch(request, timeout)
    raw = (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")
    interval = dict(request.query)["interval"]
    offset_ms = 100 if interval == "60" else 300
    return BybitCapturedJSONResponse(
        request=request,
        request_started_at=(NOW + timedelta(milliseconds=offset_ms))
        .isoformat()
        .replace("+00:00", "Z"),
        response_received_at=(NOW + timedelta(milliseconds=offset_ms + 25))
        .isoformat()
        .replace("+00:00", "Z"),
        duration_ms=25,
        response_url=f"{PUBLIC_API_BASE}{request.path}?{urlencode(request.query)}",
        http_status=200,
        content_type="application/json",
        raw_bytes=raw,
    )


def test_readiness_without_execution_capture_or_auth_is_zero_call_and_closed() -> None:
    calls = 0

    def missing(_base: object) -> dict[str, object]:
        raise BybitExecutionQualityCaptureError("capture_pointer_missing")

    payload = build_bybit_intraday_live_readiness(
        artifact_base_dir="unused",
        environ={},
        now=NOW,
        capture_loader=missing,
        resolver=_resolver(),
    )

    assert calls == 0
    assert payload["contract_version"] == CONTRACT_VERSION
    assert payload["status"] == "blocked"
    assert payload["reasons"] == [
        "execution_quality_capture_unavailable",
        "runtime_provider_authorization_absent",
    ]
    assert payload["eligible_instrument_count"] == 0
    assert payload["maximum_provider_requests_for_current_capture"] == 0
    assert payload["provider_call_planned"] is False
    assert payload["provider_call_attempted"] is False
    assert payload["writes_performed"] is False
    assert payload["next_safe_command"] == READINESS_COMMAND


def test_current_execution_capture_still_requires_separate_intraday_auth() -> None:
    payload = build_bybit_intraday_live_readiness(
        artifact_base_dir="unused",
        environ={},
        now=NOW,
        capture_loader=lambda _base: _capture(),
        resolver=_resolver(),
    )

    assert payload["status"] == "blocked"
    assert payload["reasons"] == ["runtime_provider_authorization_absent"]
    assert payload["operator_action_required"] == AUTHORIZATION_ACTION
    assert payload["authorization_action_required"] == AUTHORIZATION_ACTION
    assert payload["eligible_instrument_count"] == 1
    assert payload["maximum_provider_requests_for_current_capture"] == 2
    assert payload["expected_provider_activity"] == "none_readiness_only"
    assert payload["authorization_mutated"] is False


def test_authorized_readiness_is_exact_but_still_no_call_or_write() -> None:
    payload = build_bybit_intraday_live_readiness(
        artifact_base_dir="unused",
        environ={LIVE_AUTH_ENV: "1"},
        now=NOW,
        capture_loader=lambda _base: _capture(),
        resolver=_resolver(),
    )

    assert payload["ready"] is True
    assert payload["reasons"] == []
    assert payload["execution_quality_capture_id"] == "b" * 64
    assert payload["next_safe_command"] == CAPTURE_COMMAND
    assert payload["diagnostic_collect_command"] == COLLECT_COMMAND
    assert payload["latest_intraday_capture_status"] == "unavailable"
    assert payload["expected_provider_activity"] == (
        "collect_exactly_2_public_GETs_no_retries"
    )
    assert payload["provider_call_planned"] is False
    assert payload["provider_call_attempted"] is False
    assert payload["artifact_persisted"] is False


def test_stale_or_low_quality_execution_capture_cannot_unlock_intraday() -> None:
    stale = deepcopy(_capture())
    stale["protocol_v2_input_quality_eligible"] = False
    payload = build_bybit_intraday_live_readiness(
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
    payload = build_bybit_intraday_live_readiness(
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

    with pytest.raises(BybitIntradayLiveError, match="authorization_absent"):
        collect_authoritative_bybit_intraday(
            artifact_base_dir="unused",
            environ={},
            now=_clock(),
            capture_loader=lambda _base: _capture(),
            resolver=_resolver(),
            fetch_json=forbidden,
        )

    assert calls == 0


def test_authorized_collection_gets_exact_1h_4h_bars_without_writes() -> None:
    requests: list[object] = []

    def fetch(request: object, timeout: float) -> dict[str, object]:
        requests.append(request)
        return _fetch(request, timeout)

    payload = collect_authoritative_bybit_intraday(
        artifact_base_dir="unused",
        environ={LIVE_AUTH_ENV: "1"},
        now=_clock(),
        capture_loader=lambda _base: _capture(),
        resolver=_resolver(),
        fetch_json=fetch,
    )

    assert [dict(row.query)["interval"] for row in requests] == ["60", "240"]
    assert payload["status"] == "complete"
    assert payload["source_execution_quality_capture_id"] == "b" * 64
    assert payload["eligible_instrument_count"] == 1
    assert payload["bar_count"] == 2
    assert [row["interval"] for row in payload["bars"]] == ["1h", "4h"]
    assert all(row["bar_closed"] is True for row in payload["bars"])
    assert all(row["future_data_used"] is False for row in payload["bars"])
    assert payload["all_bars_fresh"] is True
    assert payload["all_bars_fresh_at_acquisition"] is True
    assert payload["all_bars_fresh_at_completion"] is True
    assert payload["intraday_set_freshness_policy"] == (
        "every_bar_fresh_at_capture_completion"
    )
    assert payload["maximum_provider_response_age_policy_seconds"] == 15.0
    assert payload["provider_request_count"] == payload["provider_request_bound"] == 2
    assert payload["retries"] == payload["redirects_followed"] == 0
    assert payload["artifact_persisted"] is False
    assert payload["campaign_attached"] is False
    assert payload["protocol_v2_evidence_eligible"] is False
    assert payload["writes_performed"] is False
    assert payload["orders_available"] is False
    assert payload["trades_created"] == payload["telegram_sends"] == 0


def test_collection_rechecks_every_bar_at_full_set_completion() -> None:
    payload = collect_authoritative_bybit_intraday(
        artifact_base_dir="unused",
        environ={LIVE_AUTH_ENV: "1"},
        now=_clock(completed_offset_ms=20_000),
        capture_loader=lambda _base: _capture(),
        resolver=_resolver(),
        fetch_json=_fetch,
    )

    assert all(row["freshness_status"] == "fresh" for row in payload["bars"])
    assert payload["all_bars_fresh_at_acquisition"] is True
    assert payload["all_bars_fresh_at_completion"] is False
    assert payload["all_bars_fresh"] is False
    assert payload[
        "maximum_provider_response_age_at_completion_seconds"
    ] == 19.9
    assert payload["minimum_bar_recency_remaining_at_completion_seconds"] > 0


def test_collection_stops_on_first_failure_without_retry() -> None:
    calls = 0

    def fail(_request: object, _timeout: float) -> dict[str, object]:
        nonlocal calls
        calls += 1
        raise BybitIntradayLiveError("provider_unavailable")

    with pytest.raises(BybitIntradayLiveError) as captured:
        collect_authoritative_bybit_intraday(
            artifact_base_dir="unused",
            environ={LIVE_AUTH_ENV: "1"},
            now=_clock(),
            capture_loader=lambda _base: _capture(),
            resolver=_resolver(),
            fetch_json=fail,
        )

    assert captured.value.reason_code == "provider_unavailable"
    assert captured.value.request_count == 1
    assert calls == 1


def test_post_response_capture_drift_fails_closed() -> None:
    captures = iter((_capture("b" * 64), _capture("c" * 64)))

    with pytest.raises(BybitIntradayLiveError, match="prerequisite_drifted"):
        collect_authoritative_bybit_intraday(
            artifact_base_dir="unused",
            environ={LIVE_AUTH_ENV: "1"},
            now=_clock(),
            capture_loader=lambda _base: next(captures),
            resolver=_resolver(),
            fetch_json=_fetch,
        )


def test_confirmed_capture_requires_exact_transport_and_seals_bundle(
    tmp_path: Path,
) -> None:
    result = capture_authoritative_bybit_intraday(
        artifact_base_dir=tmp_path,
        environ={LIVE_AUTH_ENV: "1"},
        now=_clock(),
        capture_loader=lambda _base: _capture(),
        resolver=_resolver(),
        fetch_json=_captured_fetch,
    )

    assert result["status"] == "complete"
    assert result["artifact_namespace"].startswith("radar_bybit_intraday_")
    assert result["request_count"] == result["bar_count"] == 2
    assert result["pointer_validated"] is True
    assert result["protocol_v2_input_quality_eligible"] is True
    assert result["protocol_v2_evidence_eligible"] is False
    assert (tmp_path / POINTER_FILENAME).is_file()

    other = tmp_path / "mapping-only"
    other.mkdir()
    with pytest.raises(
        BybitIntradayLiveError,
        match="exact_provider_response_capture_unavailable",
    ):
        capture_authoritative_bybit_intraday(
            artifact_base_dir=other,
            environ={LIVE_AUTH_ENV: "1"},
            now=_clock(),
            capture_loader=lambda _base: _capture(),
            resolver=_resolver(),
            fetch_json=_fetch,
        )
    assert not (other / POINTER_FILENAME).exists()


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

    readiness = dry_run("radar-intraday-bybit-readiness")
    collection = dry_run("radar-intraday-bybit-collect")
    confirmed = dry_run("radar-intraday-bybit-collect", confirm=True)
    capture = dry_run("radar-intraday-bybit-capture")
    confirmed_capture = dry_run("radar-intraday-bybit-capture", confirm=True)
    status = dry_run("radar-intraday-bybit-status")
    assert "bybit_intraday_live readiness" in readiness
    assert "bybit_intraday_live collect" not in readiness
    assert "bybit_intraday_live collect" in collection
    assert "--confirm" not in collection
    assert confirmed.count("--confirm") == 1
    assert "bybit_intraday_live capture" in capture
    assert "--confirm" not in capture
    assert confirmed_capture.count("--confirm") == 1
    assert "bybit_intraday_live status" in status
    assert LIVE_AUTH_ENV not in readiness
    assert f"{LIVE_AUTH_ENV}=1" not in collection
