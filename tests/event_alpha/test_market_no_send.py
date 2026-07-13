"""Guarded market-led no-send generation and pointer publication tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.dashboard.readiness import (
    CURRENT_NAMESPACE_POINTER,
    DashboardReadinessError,
)
from crypto_rsi_scanner.event_alpha.artifacts import schema_v1
from crypto_rsi_scanner.event_alpha.operations import market_no_send
from crypto_rsi_scanner.event_alpha.operations import market_no_send_io


_OBSERVED = "2026-07-12T12:00:00+00:00"


def _clear_context_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR",
        "RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE",
        "RSI_EVENT_ALPHA_RUN_MODE",
    ):
        monkeypatch.delenv(name, raising=False)


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_no_provider_authorization_returns_safe_readiness_and_never_calls_provider(
    tmp_path,
):
    calls = 0

    def forbidden_provider(_limit):
        nonlocal calls
        calls += 1
        raise AssertionError("provider must not be called")

    result = market_no_send.run_market_no_send_generation(
        artifact_base_dir=tmp_path / "artifacts",
        artifact_namespace="blocked_no_auth",
        top_n=5,
        provider=forbidden_provider,
        environ={},
        fixture_dir=None,
        observed_at=_OBSERVED,
    )

    assert result.status == "blocked"
    assert result.live_provider_authorized is False
    assert result.provider_call_attempted is False
    assert result.provider_request_succeeded is False
    assert result.namespace_dir is None
    assert calls == 0
    assert not (tmp_path / "artifacts").exists()


def test_fixture_mode_blocks_live_claim_before_provider_call(tmp_path):
    calls = 0

    def forbidden_provider(_limit):
        nonlocal calls
        calls += 1
        return []

    result = market_no_send.run_market_no_send_generation(
        artifact_base_dir=tmp_path / "artifacts",
        artifact_namespace="blocked_fixture",
        top_n=5,
        provider=forbidden_provider,
        environ={market_no_send.LIVE_AUTH_ENV: "1"},
        fixture_dir=tmp_path / "fixtures",
        observed_at=_OBSERVED,
    )

    assert result.status == "blocked"
    assert result.live_provider_authorized is True
    assert result.provider_call_attempted is False
    assert calls == 0


def test_mocked_fresh_market_data_builds_market_led_ideas_and_blocks_low_liquidity(
    tmp_path,
    monkeypatch,
):
    _clear_context_overrides(monkeypatch)
    result = market_no_send.run_market_no_send_generation(
        artifact_base_dir=tmp_path,
        artifact_namespace="market_mock",
        profile="fixture",
        run_mode="fixture",
        top_n=5,
        provider=lambda _limit: market_no_send._smoke_rows(),
        observed_at=_OBSERVED,
        environ={},
        fixture_dir=None,
        data_mode="mock",
        allow_non_live=True,
    )

    assert result.complete is True
    assert result.market_anomalies == 3
    assert result.candidates == 3
    assert result.core_rows == 2
    namespace_dir = tmp_path / "market_mock"
    rows = _jsonl(namespace_dir / "event_integrated_radar_candidates.jsonl")
    by_symbol = {str(row["symbol"]): row for row in rows}

    spread_verified = by_symbol["MKTFLOW"]
    assert spread_verified["primary_thesis_origin"] == "market_led"
    assert spread_verified["catalyst_status"] == "unknown"
    assert spread_verified["radar_actionable"] is True
    assert spread_verified["radar_route"] in {
        "actionable_watch",
        "high_confidence_watch",
        "rapid_market_anomaly",
    }

    no_spread = by_symbol["MKTNOSPREAD"]
    assert no_spread["primary_thesis_origin"] == "market_led"
    assert no_spread["spread_status"] == "unavailable"
    assert no_spread["radar_route"] == "dashboard_watch"
    assert no_spread["radar_actionable"] is False

    low_liquidity = by_symbol["MKTLOW"]
    assert low_liquidity["radar_route"] == "diagnostic"
    assert low_liquidity["radar_actionable"] is False
    assert low_liquidity["market_snapshot"]["liquidity_usd"] == 18_000.0
    assert low_liquidity["market_snapshot"]["spread_bps"] == 320.0

    manifest = json.loads(
        (namespace_dir / market_no_send.RUN_MANIFEST_FILENAME).read_text(encoding="utf-8")
    )
    request = json.loads(
        (namespace_dir / market_no_send.REQUEST_CACHE_FILENAME).read_text(encoding="utf-8")
    )
    assert manifest["status"] == "complete"
    assert manifest["data_mode"] == "mock"
    assert manifest["provider"] == "mock_coingecko"
    assert manifest["contract_counted_status"] == "counted"
    assert manifest["no_send"] is True
    assert manifest["pointer_published"] is False
    assert request["observed_at"] == _OBSERVED
    assert request["contract_counted_status"] == "counted"
    assert all(request[field] == 0 for field in market_no_send._SAFETY_COUNTERS)
    assert all(
        row["provider_source_artifact"] == market_no_send.REQUEST_CACHE_FILENAME
        for row in request["rows"]
    )
    operator_state = json.loads(
        (namespace_dir / "event_alpha_operator_state.json").read_text(encoding="utf-8")
    )
    provenance = operator_state["market_no_send_provenance"]
    assert provenance["data_mode"] == "mock"
    assert provenance["provider"] == "mock_coingecko"
    assert provenance["observed_at"] == _OBSERVED
    assert provenance["request_cache_artifact"] == market_no_send.REQUEST_CACHE_FILENAME
    assert provenance["contract_counted_status"] == "counted"
    assert provenance["no_send"] is True
    assert schema_v1.validate_row_against_schema(operator_state, "operator_state_v1") == []


def test_provider_failure_is_fail_soft_and_preserves_dashboard_pointer(
    tmp_path,
    monkeypatch,
):
    _clear_context_overrides(monkeypatch)
    tmp_path.mkdir(exist_ok=True)
    pointer = tmp_path / CURRENT_NAMESPACE_POINTER
    pointer.write_bytes(b"trusted-pointer-before-provider-failure\n")

    def unavailable(_limit):
        raise TimeoutError("secret-bearing provider details must not escape")

    result = market_no_send.run_market_no_send_generation(
        artifact_base_dir=tmp_path,
        artifact_namespace="provider_failure",
        top_n=5,
        provider=unavailable,
        environ={market_no_send.LIVE_AUTH_ENV: "1"},
        fixture_dir=None,
        observed_at=_OBSERVED,
    )

    assert result.status == "provider_unavailable"
    assert result.failure_class == "TimeoutError"
    assert result.provider_call_attempted is True
    assert result.provider_request_succeeded is False
    assert pointer.read_bytes() == b"trusted-pointer-before-provider-failure\n"
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["failure_class"] == "TimeoutError"
    assert "secret-bearing" not in result.manifest_path.read_text(encoding="utf-8")


def test_mock_generation_cannot_replace_existing_fixture_pointer(
    tmp_path,
    monkeypatch,
):
    _clear_context_overrides(monkeypatch)
    result = market_no_send.run_market_no_send_generation(
        artifact_base_dir=tmp_path,
        artifact_namespace="mock_pointer_guard",
        profile="fixture",
        run_mode="fixture",
        top_n=5,
        provider=lambda _limit: market_no_send._smoke_rows(),
        observed_at=_OBSERVED,
        environ={},
        fixture_dir=None,
        data_mode="mock",
        allow_non_live=True,
    )
    assert result.complete
    pointer = tmp_path / CURRENT_NAMESPACE_POINTER
    pointer.write_bytes(b"fixture-authority-stays\n")

    with pytest.raises(market_no_send.MarketNoSendError, match="not publishable"):
        market_no_send.publish_market_no_send_generation(
            tmp_path,
            "mock_pointer_guard",
            now=_OBSERVED,
        )

    assert pointer.read_bytes() == b"fixture-authority-stays\n"


def test_live_manifest_without_matching_operator_authority_cannot_replace_pointer(
    tmp_path,
):
    namespace = "live_candidate"
    namespace_dir = tmp_path / namespace
    namespace_dir.mkdir()
    run_id = f"{_OBSERVED}|{market_no_send.DEFAULT_PROFILE}"
    request = {
        "contract_version": market_no_send.CONTRACT_VERSION,
        "artifact_namespace": namespace,
        "run_id": run_id,
        "data_mode": "live",
        "provider": "coingecko",
        "provider_call_attempted": True,
        "provider_request_succeeded": True,
        "contract_counted_status": "counted",
        "no_send_status": "enforced",
        "no_send": True,
        "research_only": True,
        **market_no_send._SAFETY_COUNTERS,
        "rows": [],
    }
    request_path = namespace_dir / market_no_send.REQUEST_CACHE_FILENAME
    request_path.write_text(json.dumps(request, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "contract_version": market_no_send.CONTRACT_VERSION,
        "status": "complete",
        "profile": market_no_send.DEFAULT_PROFILE,
        "artifact_namespace": namespace,
        "run_mode": "burn_in",
        "run_id": run_id,
        "data_mode": "live",
        "provider": "coingecko",
        "observed_at": _OBSERVED,
        "live_provider_authorized": True,
        "fixture_mode": False,
        "provider_call_attempted": True,
        "provider_request_succeeded": True,
        "contract_counted_status": "counted",
        "no_send_status": "enforced",
        "no_send": True,
        "research_only": True,
        "pointer_published": False,
        "request_cache_artifact": market_no_send.REQUEST_CACHE_FILENAME,
        "request_cache_sha256": hashlib.sha256(request_path.read_bytes()).hexdigest(),
        **market_no_send._SAFETY_COUNTERS,
    }
    (namespace_dir / market_no_send.RUN_MANIFEST_FILENAME).write_text(
        json.dumps(manifest, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    pointer = tmp_path / CURRENT_NAMESPACE_POINTER
    pointer.write_bytes(b"previous-fixture-pointer\n")

    with pytest.raises(
        market_no_send.MarketNoSendError,
        match="operator state identity does not match",
    ):
        market_no_send.publish_market_no_send_generation(
            tmp_path,
            namespace,
            now=_OBSERVED,
        )

    assert pointer.read_bytes() == b"previous-fixture-pointer\n"


def test_market_make_targets_do_not_force_live_authorization():
    makefile = Path("Makefile").read_text(encoding="utf-8")
    assert "radar-market-no-send-readiness:" in makefile
    assert "radar-market-no-send:" in makefile
    assert "radar-market-no-send-smoke:" in makefile
    target = makefile.split("radar-market-no-send:\n", 1)[1].split(
        "radar-market-no-send-smoke:", 1
    )[0]
    assert "RSI_EVENT_DISCOVERY_UNIVERSE_LIVE=1" not in target
    assert "--event-alpha-artifact-doctor-strict" in target
    assert "market_no_send publish" in target


def test_market_writer_namespace_parent_symlink_swap_fails_closed(
    tmp_path,
    monkeypatch,
):
    base = tmp_path / "artifacts"
    namespace_dir = base / "market_write_race"
    namespace_dir.mkdir(parents=True)
    target = namespace_dir / market_no_send.RUN_MANIFEST_FILENAME
    target.write_bytes(b'{"status":"safe-before"}\n')
    displaced = base / "market_write_race.checked"
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_target = outside / market_no_send.RUN_MANIFEST_FILENAME
    outside_marker = b'{"status":"outside-unchanged"}\n'
    outside_target.write_bytes(outside_marker)
    original_open = market_no_send_io.os.open
    swapped = False

    def racing_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal swapped
        if path == namespace_dir.name and dir_fd is not None and not swapped:
            namespace_dir.rename(displaced)
            namespace_dir.symlink_to(outside, target_is_directory=True)
            # Identity verification must still fail if no-follow is ineffective.
            flags &= ~market_no_send_io.os.O_NOFOLLOW
            swapped = True
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(market_no_send_io.os, "open", racing_open)
    with pytest.raises(market_no_send.MarketNoSendError, match="write failed"):
        market_no_send._write_json_atomic(target, {"status": "must-not-escape"})

    assert swapped is True
    assert outside_target.read_bytes() == outside_marker
    assert (displaced / target.name).read_bytes() == b'{"status":"safe-before"}\n'
    assert not tuple(outside.glob(".*.tmp"))
    assert not tuple(displaced.glob(".*.tmp"))


def test_market_reader_namespace_parent_symlink_swap_does_not_read_outside(
    tmp_path,
    monkeypatch,
):
    base = tmp_path / "artifacts"
    namespace_dir = base / "market_read_race"
    namespace_dir.mkdir(parents=True)
    target = namespace_dir / market_no_send.RUN_MANIFEST_FILENAME
    target.write_text('{"status":"safe"}\n', encoding="utf-8")
    displaced = base / "market_read_race.checked"
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / target.name).write_text('{"status":"outside"}\n', encoding="utf-8")
    original_open = market_no_send_io.os.open
    swapped = False

    def racing_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal swapped
        if path == namespace_dir.name and dir_fd is not None and not swapped:
            namespace_dir.rename(displaced)
            namespace_dir.symlink_to(outside, target_is_directory=True)
            flags &= ~market_no_send_io.os.O_NOFOLLOW
            swapped = True
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(market_no_send_io.os, "open", racing_open)
    with pytest.raises(
        market_no_send.MarketNoSendError,
        match="missing or unreadable",
    ):
        market_no_send._read_json_object(target)
    assert swapped is True


def test_market_artifact_io_fails_closed_without_descriptor_features(
    tmp_path,
    monkeypatch,
):
    namespace_dir = tmp_path / "market_unsupported"
    namespace_dir.mkdir()
    target = namespace_dir / market_no_send.RUN_MANIFEST_FILENAME
    monkeypatch.setattr(market_no_send_io, "_OPEN_SUPPORTS_DIR_FD", False)

    with pytest.raises(market_no_send.MarketNoSendError, match="unsupported"):
        market_no_send._write_json_atomic(target, {"status": "blocked"})
    with pytest.raises(market_no_send.MarketNoSendError, match="unsupported"):
        market_no_send._read_json_object(target)
    assert not target.exists()
