"""Atomic cadence reservation and shared provider-backoff regressions."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone

import pytest

from crypto_rsi_scanner.event_alpha.operations import market_no_send
from crypto_rsi_scanner.event_alpha.operations import market_no_send_campaign_guard
from crypto_rsi_scanner.event_alpha.operations import market_no_send_campaign_provider
from crypto_rsi_scanner.event_alpha.operations import market_no_send_io
from crypto_rsi_scanner.event_alpha.operations import market_no_send_provider
from crypto_rsi_scanner.event_alpha.operations.market_no_send_models import (
    MarketNoSendError,
)


def _clear_context_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR",
        "RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE",
        "RSI_EVENT_ALPHA_RUN_MODE",
    ):
        monkeypatch.delenv(name, raising=False)


def _configure_live_test(monkeypatch: pytest.MonkeyPatch, artifact_base) -> None:
    _clear_context_overrides(monkeypatch)
    monkeypatch.setenv(market_no_send.LIVE_AUTH_ENV, "1")
    monkeypatch.setattr(market_no_send.config, "FIXTURE_DIR", None)
    monkeypatch.setattr(
        market_no_send.config,
        "EVENT_ALPHA_ARTIFACT_BASE_DIR",
        artifact_base,
    )


def test_two_live_namespaces_cannot_call_or_commit_history_concurrently(
    tmp_path,
    monkeypatch,
):
    _configure_live_test(monkeypatch, tmp_path)
    provider_entered = threading.Event()
    release_provider = threading.Event()
    calls: list[int] = []
    first_result: list[object] = []
    first_error: list[BaseException] = []

    def controlled_provider(limit: int):
        calls.append(limit)
        provider_entered.set()
        assert release_provider.wait(timeout=10)
        return market_no_send._smoke_rows()

    monkeypatch.setattr(market_no_send, "_fetch_live_coingecko_rows", controlled_provider)
    observed = datetime.now(timezone.utc).replace(microsecond=0)

    def commit_history_only(**kwargs):
        context = kwargs["context"]
        rows, _audit = market_no_send.normalize_market_rows(
            kwargs["raw_rows"],
            top_n=kwargs["top_n"],
            observed_at=kwargs["observed"],
            provider="coingecko",
            data_mode="live",
            request_cache_artifact=market_no_send.REQUEST_CACHE_FILENAME,
            request_ledger_artifact=market_no_send.REQUEST_LEDGER_FILENAME,
            candidate_source_mode="live_no_send",
            decision_radar_campaign_counted=True,
        )
        market_no_send.market_no_send_history_cache.enrich_and_persist_history(
            rows,
            artifact_base_dir=tmp_path,
            generation_namespace_dir=context.namespace_dir,
            history_filename=market_no_send.HISTORY_FILENAME,
            observed_at=kwargs["observed"],
            live_no_send=True,
            campaign_reservation=kwargs["campaign_reservation"],
        )
        return market_no_send.MarketNoSendGenerationResult(
            status="complete",
            profile=context.profile,
            artifact_namespace=context.artifact_namespace,
            namespace_dir=context.namespace_dir,
            data_mode="live",
            provider="coingecko",
            observed_at=kwargs["observed"].isoformat(),
            live_provider_authorized=True,
            provider_call_attempted=True,
            provider_request_succeeded=True,
        )

    monkeypatch.setattr(
        market_no_send,
        "_build_market_generation_from_rows",
        commit_history_only,
    )

    def run_first() -> None:
        try:
            first_result.append(market_no_send.run_market_no_send_generation(
                artifact_base_dir=tmp_path,
                artifact_namespace="concurrent_first",
                top_n=5,
                observed_at=observed,
                environ={market_no_send.LIVE_AUTH_ENV: "1"},
                fixture_dir=None,
            ))
        except BaseException as exc:  # pragma: no cover - asserted below
            first_error.append(exc)

    thread = threading.Thread(target=run_first, daemon=True)
    thread.start()
    assert provider_entered.wait(timeout=10)
    second = market_no_send.run_market_no_send_generation(
        artifact_base_dir=tmp_path,
        artifact_namespace="concurrent_second",
        top_n=5,
        observed_at=observed,
        environ={market_no_send.LIVE_AUTH_ENV: "1"},
        fixture_dir=None,
    )
    assert second.status == "blocked"
    assert second.failure_class in {"readiness_blocked", "campaign_reservation_busy"}
    assert second.provider_call_attempted is False
    assert len(calls) == 1
    assert not (tmp_path / "concurrent_second").exists()

    release_provider.set()
    thread.join(timeout=20)
    assert not thread.is_alive()
    assert not first_error
    assert first_result and first_result[0].complete is True
    shared_history = market_no_send_io.read_jsonl(
        market_no_send_campaign_guard.campaign_state_dir(tmp_path)
        / market_no_send.HISTORY_FILENAME
    )
    assert len(shared_history) == len(market_no_send._smoke_rows())
    assert {row["observed_at"] for row in shared_history} == {
        first_result[0].observed_at
    }


def test_os_lock_blocks_live_owner_and_safely_reclaims_orphaned_receipt(tmp_path):
    with market_no_send_campaign_guard.acquire_campaign_reservation(
        tmp_path,
        artifact_namespace="first_owner",
    ) as first:
        active = market_no_send_io.read_json_object(
            market_no_send_campaign_guard.campaign_reservation_path(tmp_path)
        )
        assert active["status"] == "active"
        assert active["stale_policy"] == (
            "active_os_lock_never_stolen;orphan_reclaim_after_expiry"
        )
        with pytest.raises(
            market_no_send_campaign_guard.CampaignReservationBusy,
            match="another Decision Radar campaign operation is active",
        ):
            with market_no_send_campaign_guard.acquire_campaign_reservation(
                tmp_path,
                artifact_namespace="contender",
            ):
                raise AssertionError("contender must never acquire the live OS lock")

    reservation_path = market_no_send_campaign_guard.campaign_reservation_path(tmp_path)
    orphan = market_no_send_io.read_json_object(reservation_path)
    now = datetime.now(timezone.utc)
    orphan.update({
        "status": "active",
        "acquired_at": (now - timedelta(minutes=20)).isoformat(),
        "expires_at": (now - timedelta(minutes=5)).isoformat(),
        "next_provider_call_at": None,
        "released_at": None,
    })
    market_no_send_io.write_json_atomic(reservation_path, orphan)
    with market_no_send_campaign_guard.acquire_campaign_reservation(
        tmp_path,
        artifact_namespace="replacement",
    ) as replacement:
        assert replacement.previous_reservation_status == "stale_active_reclaimed"
        replacement.assert_active(tmp_path)


def test_state_directory_replacement_cannot_create_a_second_lock_realm(tmp_path):
    state_dir = market_no_send_campaign_guard.campaign_state_dir(tmp_path)
    displaced_state_dir = tmp_path / "displaced_campaign_state"
    replacement_state_dir = tmp_path / "replacement_campaign_state"
    provider_calls: list[str] = []

    with market_no_send_campaign_guard.acquire_campaign_reservation(
        tmp_path,
        artifact_namespace="anchored_owner",
    ) as reservation:
        state_dir.rename(displaced_state_dir)
        state_dir.mkdir(mode=0o700)
        try:
            with pytest.raises(
                market_no_send_campaign_guard.CampaignReservationBusy,
                match="another Decision Radar campaign operation is active",
            ):
                with market_no_send_campaign_guard.acquire_campaign_reservation(
                    tmp_path,
                    artifact_namespace="replacement_contender",
                ):
                    raise AssertionError("a replacement state directory must not bypass the lock")

            with pytest.raises(
                MarketNoSendError,
                match="campaign state directory identity changed",
            ):
                reservation.assert_active(tmp_path)

            with pytest.raises(
                MarketNoSendError,
                match="campaign state directory identity changed",
            ):
                market_no_send_campaign_guard.mark_provider_call_reserved(
                    reservation,
                    attempted_at=datetime.now(timezone.utc),
                    minimum_spacing=timedelta(hours=1),
                )
                provider_calls.append("provider ingress")
            assert provider_calls == []
        finally:
            state_dir.rename(replacement_state_dir)
            displaced_state_dir.rename(state_dir)
            replacement_state_dir.rmdir()


def test_provider_cadence_survives_state_directory_replacement_after_reservation(
    tmp_path,
):
    state_dir = market_no_send_campaign_guard.campaign_state_dir(tmp_path)
    displaced_state_dir = tmp_path / "displaced_after_provider_reservation"
    attempted = datetime.now(timezone.utc).replace(microsecond=0)

    with pytest.raises(
        MarketNoSendError,
        match="campaign state directory identity changed",
    ):
        with market_no_send_campaign_guard.acquire_campaign_reservation(
            tmp_path,
            artifact_namespace="provider_reserved_owner",
            acquired_at=attempted,
        ) as reservation:
            market_no_send_campaign_guard.mark_provider_call_reserved(
                reservation,
                attempted_at=attempted,
                minimum_spacing=timedelta(hours=1),
            )
            state_dir.rename(displaced_state_dir)
            state_dir.mkdir(mode=0o700)

    stable_receipt = market_no_send_io.read_json_object(
        market_no_send_campaign_guard.campaign_reservation_path(tmp_path)
    )
    assert stable_receipt["artifact_namespace"] == "provider_reserved_owner"
    assert stable_receipt["provider_call_reserved_at"] == attempted.isoformat()
    assert stable_receipt["next_provider_call_at"] == (
        attempted + timedelta(hours=1)
    ).isoformat()
    assessment = market_no_send_campaign_guard.assess_campaign_reservation(
        tmp_path,
        checked_at=attempted + timedelta(minutes=1),
    )
    assert assessment["allowed"] is False
    assert assessment["next_provider_call_at"] == (
        attempted + timedelta(hours=1)
    ).isoformat()
    with pytest.raises(
        market_no_send_campaign_guard.CampaignReservationBusy,
        match="provider call is reserved until",
    ):
        with market_no_send_campaign_guard.acquire_campaign_reservation(
            tmp_path,
            artifact_namespace="immediate_retry",
            acquired_at=attempted + timedelta(minutes=1),
        ):
            raise AssertionError("stable cadence must block an immediate retry")


def test_pre_v2_state_directory_cadence_receipt_remains_readable(tmp_path):
    attempted = datetime.now(timezone.utc).replace(microsecond=0)
    with market_no_send_campaign_guard.acquire_campaign_reservation(
        tmp_path,
        artifact_namespace="legacy_receipt_owner",
        acquired_at=attempted,
    ) as reservation:
        market_no_send_campaign_guard.mark_provider_call_reserved(
            reservation,
            attempted_at=attempted,
            minimum_spacing=timedelta(hours=1),
        )

    stable = market_no_send_campaign_guard.campaign_reservation_path(tmp_path)
    legacy = (
        market_no_send_campaign_guard.campaign_state_dir(tmp_path)
        / market_no_send_campaign_guard.CAMPAIGN_RESERVATION_FILENAME
    )
    stable.rename(legacy)
    assessment = market_no_send_campaign_guard.assess_campaign_reservation(
        tmp_path,
        checked_at=attempted + timedelta(minutes=1),
    )
    assert assessment["allowed"] is False
    assert assessment["next_provider_call_at"] == (
        attempted + timedelta(hours=1)
    ).isoformat()


def test_lock_leaf_replacement_invalidates_the_active_reservation(tmp_path):
    lock_path = tmp_path / market_no_send_campaign_guard.CAMPAIGN_LOCK_FILENAME
    displaced_lock_path = tmp_path / ".displaced_decision_radar_campaign.lock"

    with market_no_send_campaign_guard.acquire_campaign_reservation(
        tmp_path,
        artifact_namespace="lock_identity_owner",
    ) as reservation:
        lock_path.rename(displaced_lock_path)
        lock_path.touch(mode=0o600)
        try:
            with pytest.raises(
                MarketNoSendError,
                match="campaign lock identity changed",
            ):
                reservation.assert_active(tmp_path)
        finally:
            lock_path.unlink()
            displaced_lock_path.rename(lock_path)


def test_rate_limit_backoff_and_latest_failure_are_shared_and_sanitized(
    tmp_path,
    monkeypatch,
):
    _configure_live_test(monkeypatch, tmp_path)
    attempted = datetime.now(timezone.utc).replace(microsecond=0)
    telemetry = {
        "endpoint_path": "/coins/markets?api_key=SECRET_VALUE",
        "request_started_at": attempted.isoformat(),
        "request_ended_at": attempted.isoformat(),
        "duration_ms": 12,
        "http_status": 429,
        "result_count": 0,
        "retry_count": 1,
        "error_class": "rate_limited",
        "cache_behavior": "network",
        "headers": {"Authorization": "SECRET_VALUE"},
        "raw_error": "SECRET_VALUE",
    }
    error = market_no_send_provider.MarketProviderRequestError(
        "rate_limited",
        telemetry,
    )
    with market_no_send_campaign_guard.acquire_campaign_reservation(
        tmp_path,
        artifact_namespace="rate_limited_first",
    ) as reservation:
        market_no_send_campaign_provider.record_shared_provider_failure(
            reservation,
            artifact_namespace="rate_limited_first",
            provider="coingecko",
            run_id="rate-limit-run",
            attempted_at=attempted,
            error=error,
            request_telemetry=telemetry,
        )

    receipt_path = (
        market_no_send_campaign_guard.campaign_state_dir(tmp_path)
        / market_no_send_campaign_provider.LATEST_SHARED_FAILURE_FILENAME
    )
    receipt_text = receipt_path.read_text(encoding="utf-8")
    receipt = json.loads(receipt_text)
    assert "SECRET_VALUE" not in receipt_text
    assert receipt["request"] == {
        "cache_behavior": "network",
        "duration_ms": 12,
        "endpoint_path": "/coins/markets",
        "error_class": "rate_limited",
        "http_status": 429,
        "request_ended_at": attempted.isoformat(),
        "request_started_at": attempted.isoformat(),
        "result_count": 0,
        "retry_count": 1,
    }
    assert receipt["disabled_until"] == (attempted + timedelta(minutes=30)).isoformat()

    readiness = market_no_send.build_market_no_send_readiness(
        artifact_base_dir=tmp_path,
        artifact_namespace="rate_limited_second",
        top_n=5,
        environ={market_no_send.LIVE_AUTH_ENV: "1"},
        fixture_dir=None,
        now=attempted + timedelta(minutes=1),
    )
    assert readiness.ready is False
    assert readiness.will_call_provider is False
    assert any("shared backoff" in reason for reason in readiness.reasons)
    assert readiness.next_safe_command == "make radar-daily-ops-readiness"

    calls = 0

    def forbidden(_limit):
        nonlocal calls
        calls += 1
        raise AssertionError("a new namespace must honor the shared 429 backoff")

    monkeypatch.setattr(market_no_send, "_fetch_live_coingecko_rows", forbidden)
    result = market_no_send.run_market_no_send_generation(
        artifact_base_dir=tmp_path,
        artifact_namespace="rate_limited_second",
        top_n=5,
        observed_at=attempted + timedelta(minutes=1),
        environ={market_no_send.LIVE_AUTH_ENV: "1"},
        fixture_dir=None,
    )
    assert result.status == "blocked"
    assert result.provider_call_attempted is False
    assert calls == 0
    assert not (tmp_path / "rate_limited_second").exists()


def test_invalid_shared_failure_receipt_fails_readiness_closed(tmp_path):
    state_dir = market_no_send_campaign_guard.campaign_state_dir(tmp_path)
    market_no_send_io.ensure_safe_namespace_dir(state_dir)
    market_no_send_io.write_json_atomic(
        state_dir / market_no_send_campaign_provider.LATEST_SHARED_FAILURE_FILENAME,
        {"contract_version": 1, "row_type": "invalid"},
    )
    readiness = market_no_send.build_market_no_send_readiness(
        artifact_base_dir=tmp_path,
        artifact_namespace="invalid_shared_state",
        environ={market_no_send.LIVE_AUTH_ENV: "1"},
        fixture_dir=None,
    )
    assert readiness.ready is False
    assert readiness.will_call_provider is False
    assert "shared provider backoff state is invalid" in readiness.reasons


def test_failed_call_reserves_spacing_before_a_new_namespace_can_retry(
    tmp_path,
    monkeypatch,
):
    _configure_live_test(monkeypatch, tmp_path)
    calls = 0

    def unavailable(_limit):
        nonlocal calls
        calls += 1
        raise TimeoutError("credential text must not escape")

    monkeypatch.setattr(market_no_send, "_fetch_live_coingecko_rows", unavailable)
    observed = datetime.now(timezone.utc).replace(microsecond=0)
    first = market_no_send.run_market_no_send_generation(
        artifact_base_dir=tmp_path,
        artifact_namespace="failed_spacing_first",
        top_n=5,
        observed_at=observed,
        environ={market_no_send.LIVE_AUTH_ENV: "1"},
        fixture_dir=None,
    )
    assert first.status == "provider_unavailable"
    assert calls == 1
    shared_failure = (
        market_no_send_campaign_guard.campaign_state_dir(tmp_path)
        / market_no_send_campaign_provider.LATEST_SHARED_FAILURE_FILENAME
    ).read_text(encoding="utf-8")
    assert "credential text" not in shared_failure

    second = market_no_send.run_market_no_send_generation(
        artifact_base_dir=tmp_path,
        artifact_namespace="failed_spacing_second",
        top_n=5,
        observed_at=observed + timedelta(minutes=1),
        environ={market_no_send.LIVE_AUTH_ENV: "1"},
        fixture_dir=None,
    )
    assert second.status == "blocked"
    assert second.provider_call_attempted is False
    assert calls == 1
    assert not (tmp_path / "failed_spacing_second").exists()
