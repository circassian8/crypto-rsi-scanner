"""Persistence tests for the rolling live no-send market baseline."""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest

from crypto_rsi_scanner.event_alpha.operations import market_no_send
from crypto_rsi_scanner.event_alpha.operations import market_no_send_campaign_guard
from crypto_rsi_scanner.event_alpha.operations import market_no_send_features
from crypto_rsi_scanner.event_alpha.operations import market_no_send_history_cache
from crypto_rsi_scanner.event_alpha.operations import market_no_send_io


def _normalized_rows(observed_at: datetime):
    rows, _audit = market_no_send.normalize_market_rows(
        market_no_send._smoke_rows(),
        top_n=5,
        observed_at=observed_at,
        provider="coingecko",
        data_mode="live",
        request_cache_artifact=market_no_send.REQUEST_CACHE_FILENAME,
        candidate_source_mode="live_no_send",
        decision_radar_campaign_counted=True,
    )
    return rows


def _control_regime_rows(
    observed_at: datetime,
    *,
    returns: tuple[float, ...] = (2.0, 1.0, 3.0, 0.5, 4.0),
):
    rows = _normalized_rows(observed_at)
    assert len(rows) == len(returns)
    for index, (row, value) in enumerate(zip(rows, returns, strict=True), start=1):
        observation_id = f"control-regime-observation-{index}"
        row["market_history"] = {
            "baseline_counted": True,
            "observation_id": observation_id,
        }
        row["temporal_return_24h"] = value
        row["return_units"] = {"temporal_return_24h": "percent_points"}
        row["market_feature_evidence"] = {
            "temporal_return_24h": {
                "basis": "temporal_baseline",
                "status": "ready",
                "calculation": "price_horizon_return",
                "sample_count": 1,
                "current_observation_id": observation_id,
                "baseline_first_observation_id": f"control-regime-anchor-{index}",
                "baseline_last_observation_id": f"control-regime-anchor-{index}",
                "baseline_input_observation_count": 1,
                "baseline_observation_ids_sha256": hashlib.sha256(
                    json.dumps(
                        [f"control-regime-anchor-{index}"],
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest(),
                "providers": ["coingecko"],
                "data_modes": ["live"],
                "research_only": True,
            }
        }
    return rows


def test_normalization_retains_outcome_blind_point_in_time_universe_context():
    observed_at = datetime(2026, 7, 12, 12, tzinfo=timezone.utc)
    rows = _normalized_rows(observed_at)

    assert [row["point_in_time_volume_rank"] for row in rows] == [1, 2, 3, 4, 5]
    assert all(row["point_in_time_universe_member"] is True for row in rows)
    assert all(row["point_in_time_universe_size"] == 5 for row in rows)
    assert all(row["point_in_time_universe_limit"] == 5 for row in rows)
    assert all(
        row["point_in_time_universe_policy"]
        == market_no_send_features.POINT_IN_TIME_UNIVERSE_POLICY
        for row in rows
    )
    assert all(
        row["control_liquidity_tier"] in {"high", "mid", "low", "unknown"}
        for row in rows
    )
    assert all(
        row["control_liquidity_tier_basis"]
        == market_no_send_features.CONTROL_LIQUIDITY_TIER_BASIS
        for row in rows
    )
    assert all("protocol_partition" not in row for row in rows)
    assert all("market_regime" not in row for row in rows)


def test_control_context_readiness_rejects_rank_and_basis_drift():
    observed_at = datetime(2026, 7, 12, 12, tzinfo=timezone.utc)
    row = {
        **_normalized_rows(observed_at)[0],
        "observed_at": observed_at.isoformat(),
        "baseline_counted": True,
        "point_in_time_volume_rank": 31,
        "point_in_time_universe_size": 30,
        "point_in_time_universe_limit": 30,
        "control_liquidity_tier_basis": "untrusted_reconstruction",
    }

    result = (
        market_no_send_history_cache._point_in_time_control_context_readiness(
            [row],
            cache_status="valid",
        )
    )

    assert result["status"] == "partial"
    assert result["counted_observation_count"] == 1
    assert result["point_in_time_universe_context_row_count"] == 0
    assert result["complete_match_context_row_count"] == 0
    assert result["field_coverage_counts"]["control_liquidity_tier_basis"] == 0


def test_control_context_readiness_cannot_count_bare_partition_claims():
    observed_at = datetime(2026, 7, 12, 12, tzinfo=timezone.utc)
    row = {
        **_normalized_rows(observed_at)[0],
        "observed_at": observed_at.isoformat(),
        "baseline_counted": True,
        "protocol_partition": "untouched_holdout",
        "protocol_partition_basis": "claimed_frozen_protocol_v2",
    }

    result = (
        market_no_send_history_cache._point_in_time_control_context_readiness(
            [row],
            cache_status="valid",
        )
    )

    assert result["status"] == "partial"
    assert result["field_coverage_counts"]["protocol_partition"] == 0
    assert result["field_coverage_counts"]["protocol_partition_basis"] == 0
    assert result["complete_match_context_row_count"] == 0
    assert result["selection_performed"] is False
    assert result["protocol_v2_evidence_eligible"] is False


@pytest.mark.parametrize(
    ("returns", "expected"),
    [
        ((2.0, 1.0, 3.0, 0.5, 4.0), "risk_on"),
        ((-2.0, -1.0, -3.0, -0.5, -4.0), "risk_off"),
        ((2.0, -1.0, -3.0, -0.5, 0.1), "mixed"),
    ],
)
def test_control_market_regime_uses_exact_current_temporal_returns(
    returns,
    expected,
):
    observed_at = datetime(2026, 7, 12, 12, tzinfo=timezone.utc)

    evidence = market_no_send_features.point_in_time_control_market_regime(
        _control_regime_rows(observed_at, returns=returns)
    )

    assert evidence["status"] == "observed"
    assert evidence["regime"] == expected
    assert evidence["universe_input_count"] == 5
    assert len(evidence["input_observation_ids"]) == 5
    assert evidence["btc_canonical_asset_id"] == "bitcoin"
    assert evidence["selection_uses_outcomes"] is False
    assert evidence["routing_eligible"] is False
    assert evidence["decision_policy_eligible"] is False
    assert evidence["protocol_v2_evidence_eligible"] is False
    assert market_no_send_features.control_market_regime_evidence_valid(evidence)


def test_control_market_regime_fails_closed_on_incomplete_or_tampered_evidence():
    observed_at = datetime(2026, 7, 12, 12, tzinfo=timezone.utc)
    rows = _control_regime_rows(observed_at)
    del rows[-1]["temporal_return_24h"]

    unavailable = market_no_send_features.point_in_time_control_market_regime(rows)

    assert unavailable["status"] == "unavailable"
    assert unavailable["reason"] == "temporal_return_24h_incomplete"
    assert unavailable["regime"] is None
    assert market_no_send_features.control_market_regime_evidence_valid(unavailable)

    observed = market_no_send_features.point_in_time_control_market_regime(
        _control_regime_rows(observed_at)
    )
    observed["selection_uses_outcomes"] = True
    assert not market_no_send_features.control_market_regime_evidence_valid(observed)

    observed = market_no_send_features.point_in_time_control_market_regime(
        _control_regime_rows(observed_at)
    )
    observed["input_observation_ids"][1] = observed["input_observation_ids"][0]
    assert not market_no_send_features.control_market_regime_evidence_valid(observed)

    malformed = _control_regime_rows(observed_at)
    malformed[0]["point_in_time_universe_size"] = {"unexpected": "mapping"}
    malformed[1]["point_in_time_volume_rank"] = [2]
    unavailable = market_no_send_features.point_in_time_control_market_regime(
        malformed
    )
    assert unavailable["status"] == "unavailable"
    assert unavailable["reason"] == "current_cycle_context_invalid"

    malformed_identity = _control_regime_rows(observed_at)
    malformed_identity[-1]["canonical_asset_id"] = {"borrowed": "asset"}
    unavailable = market_no_send_features.point_in_time_control_market_regime(
        malformed_identity
    )
    assert unavailable["status"] == "unavailable"
    assert unavailable["reason"] == "current_cycle_context_invalid"

    diagnostic = (
        market_no_send_features.point_in_time_control_market_regime_input_diagnostic(
            malformed_identity
        )
    )
    assert diagnostic["status"] == "unavailable"
    assert diagnostic["missing_input_count"] == 1
    assert diagnostic["missing_inputs"][0]["reasons"] == [
        "canonical_asset_identity_missing"
    ]


def test_control_market_regime_input_diagnostic_names_every_incomplete_row():
    observed_at = datetime(2026, 7, 12, 12, tzinfo=timezone.utc)
    rows = _control_regime_rows(observed_at)
    for row in rows[-2:]:
        row.pop("temporal_return_24h")
        row["return_units"].pop("temporal_return_24h")
        row["market_feature_evidence"].pop("temporal_return_24h")

    diagnostic = (
        market_no_send_features
        .point_in_time_control_market_regime_input_diagnostic(rows)
    )

    assert diagnostic["status"] == "incomplete"
    assert diagnostic["reason"] == "temporal_return_24h_incomplete"
    assert diagnostic["universe_row_count"] == 5
    assert diagnostic["universe_expected_count"] == 5
    assert diagnostic["eligible_input_count"] == 3
    assert diagnostic["missing_input_count"] == 2
    assert [
        row["canonical_asset_id"] for row in diagnostic["missing_inputs"]
    ] == ["market-flow-no-spread", "market-flow-low"]
    assert diagnostic["missing_input_reason_counts"] == {
        "temporal_return_evidence_invalid": 2,
        "temporal_return_unit_invalid": 2,
        "temporal_return_value_missing_or_invalid": 2,
    }
    assert diagnostic["bitcoin_input_ready"] is True
    assert diagnostic["all_inputs_ready"] is False
    assert diagnostic["retained_history_mutated"] is False
    assert diagnostic["historical_context_backfilled"] is False
    assert diagnostic["provider_calls"] == 0
    assert market_no_send_features.control_market_regime_input_diagnostic_valid(
        diagnostic
    )

    diagnostic["missing_inputs"][0]["reasons"] = ["invented_reason"]
    assert not market_no_send_features.control_market_regime_input_diagnostic_valid(
        diagnostic
    )


def test_control_market_regime_input_diagnostic_reports_ready_replay():
    observed_at = datetime(2026, 7, 12, 12, tzinfo=timezone.utc)

    diagnostic = (
        market_no_send_features
        .point_in_time_control_market_regime_input_diagnostic(
            _control_regime_rows(observed_at)
        )
    )

    assert diagnostic["status"] == "ready"
    assert diagnostic["eligible_input_count"] == 5
    assert diagnostic["missing_input_count"] == 0
    assert diagnostic["missing_inputs"] == []
    assert diagnostic["replayed_control_market_regime"]["regime"] == "risk_on"
    assert market_no_send_features.control_market_regime_input_diagnostic_valid(
        diagnostic
    )


@contextmanager
def _provider_reserved_history(base, namespace: str, observed_at: datetime):
    with market_no_send_campaign_guard.acquire_campaign_reservation(
        base,
        artifact_namespace=namespace,
        acquired_at=observed_at,
    ) as reservation:
        market_no_send_campaign_guard.mark_provider_call_reserved(
            reservation,
            attempted_at=observed_at,
            minimum_spacing=timedelta(seconds=1),
        )
        yield reservation


def test_live_history_cache_rolls_across_immutable_generation_namespaces(tmp_path):
    base = tmp_path / "artifacts"
    base.mkdir()
    first_dir = base / "market_generation_1"
    second_dir = base / "market_generation_2"
    market_no_send_io.ensure_safe_namespace_dir(first_dir)
    market_no_send_io.ensure_safe_namespace_dir(second_dir)
    first_at = datetime(2026, 7, 12, 12, tzinfo=timezone.utc)

    with _provider_reserved_history(base, first_dir.name, first_at) as reservation:
        _rows, first_summary, _digest = (
            market_no_send_history_cache.enrich_and_persist_history(
                _normalized_rows(first_at),
                artifact_base_dir=base,
                generation_namespace_dir=first_dir,
                history_filename=market_no_send.HISTORY_FILENAME,
                observed_at=first_at,
                live_no_send=True,
                campaign_reservation=reservation,
            )
        )
    first_snapshot = (first_dir / market_no_send.HISTORY_FILENAME).read_bytes()
    second_at = first_at + timedelta(hours=1)
    with _provider_reserved_history(base, second_dir.name, second_at) as reservation:
        second_rows, second_summary, _digest = (
            market_no_send_history_cache.enrich_and_persist_history(
                _normalized_rows(second_at),
                artifact_base_dir=base,
                generation_namespace_dir=second_dir,
                history_filename=market_no_send.HISTORY_FILENAME,
                observed_at=second_at,
                live_no_send=True,
                campaign_reservation=reservation,
            )
        )

    assert first_summary["shared_seed_rows"] == 0
    assert second_summary["shared_seed_rows"] == 5
    assert all(row["market_history"]["prior_observation_count"] == 1 for row in second_rows)
    retained = market_no_send_io.read_jsonl(
        base / market_no_send_history_cache.LIVE_HISTORY_CACHE_NAMESPACE / market_no_send.HISTORY_FILENAME
    )
    assert all(row["measurement_program"] == "decision_radar_live_observation_campaign_v2" for row in retained)
    assert all(row["decision_radar_campaign_counted"] is True for row in retained)
    assert all(row["burn_in_counted"] is False for row in retained)
    assert sorted(row["point_in_time_volume_rank"] for row in retained) == [
        1, 1, 2, 2, 3, 3, 4, 4, 5, 5,
    ]
    context = market_no_send_history_cache.cache_readiness(
        base,
        history_filename=market_no_send.HISTORY_FILENAME,
        now=second_at,
    )["point_in_time_control_context_readiness"]
    assert context["status"] == "partial"
    assert context["counted_observation_count"] == 10
    assert context["point_in_time_universe_context_row_count"] == 10
    assert context["complete_match_context_row_count"] == 0
    assert context["field_coverage_counts"]["control_liquidity_tier"] == 10
    assert context["field_coverage_counts"]["market_regime"] == 0
    assert context["field_coverage_counts"]["protocol_partition"] == 0
    assert context["selection_uses_outcomes"] is False
    assert context["selection_performed"] is False
    assert context["selection_match_fields"] == [
        "partition", "observation_date", "market_regime", "liquidity_tier",
    ]
    assert context["selection_field_mapping"]["liquidity_tier"] == (
        "control_liquidity_tier"
    )
    assert context["historical_context_backfilled"] is False
    assert context["protocol_v2_evidence_eligible"] is False
    assert context["provider_calls"] == context["writes"] == 0
    assert (first_dir / market_no_send.HISTORY_FILENAME).read_bytes() == first_snapshot


def test_live_history_persists_current_regime_only_after_temporal_evidence_is_ready(
    tmp_path,
):
    base = tmp_path / "artifacts"
    base.mkdir()
    first_dir = base / "market_generation_1"
    second_dir = base / "market_generation_2"
    market_no_send_io.ensure_safe_namespace_dir(first_dir)
    market_no_send_io.ensure_safe_namespace_dir(second_dir)
    first_at = datetime(2026, 7, 12, 12, tzinfo=timezone.utc)
    second_at = first_at + timedelta(hours=24)

    with _provider_reserved_history(base, first_dir.name, first_at) as reservation:
        _first_rows, first_summary, _digest = (
            market_no_send_history_cache.enrich_and_persist_history(
                _normalized_rows(first_at),
                artifact_base_dir=base,
                generation_namespace_dir=first_dir,
                history_filename=market_no_send.HISTORY_FILENAME,
                observed_at=first_at,
                live_no_send=True,
                campaign_reservation=reservation,
            )
        )
    assert first_summary["point_in_time_control_market_regime"]["status"] == (
        "unavailable"
    )

    with _provider_reserved_history(base, second_dir.name, second_at) as reservation:
        second_rows, second_summary, _digest = (
            market_no_send_history_cache.enrich_and_persist_history(
                _normalized_rows(second_at),
                artifact_base_dir=base,
                generation_namespace_dir=second_dir,
                history_filename=market_no_send.HISTORY_FILENAME,
                observed_at=second_at,
                live_no_send=True,
                campaign_reservation=reservation,
            )
        )

    regime = second_summary["point_in_time_control_market_regime"]
    assert regime["status"] == "observed"
    assert regime["regime"] == "mixed"
    assert all("market_regime" not in row for row in second_rows)
    retained = market_no_send_io.read_jsonl(
        base
        / market_no_send_history_cache.LIVE_HISTORY_CACHE_NAMESPACE
        / market_no_send.HISTORY_FILENAME
    )
    old_rows = [row for row in retained if row["observed_at"] == first_at.isoformat()]
    current_rows = [row for row in retained if row["observed_at"] == second_at.isoformat()]
    assert len(old_rows) == len(current_rows) == 5
    assert all("market_regime" not in row for row in old_rows)
    assert all(row["market_regime"] == "mixed" for row in current_rows)
    assert all(row["market_regime_evidence"] == regime for row in current_rows)
    tampered = dict(current_rows[0])
    tampered["point_in_time_volume_rank"] = 2
    assert not market_no_send_history_cache._control_market_regime_valid(tampered)

    rebuilt = market_no_send_history_cache.market_history.enrich_market_rows_with_history(
        [],
        retained,
        now=second_at,
    )
    assert list(rebuilt.retained_history) == retained

    context = market_no_send_history_cache.cache_readiness(
        base,
        history_filename=market_no_send.HISTORY_FILENAME,
        now=second_at,
    )["point_in_time_control_context_readiness"]
    assert context["status"] == "partial"
    assert context["field_coverage_counts"]["market_regime"] == 5
    assert context["field_coverage_counts"]["market_regime_basis"] == 5
    assert context["complete_match_context_row_count"] == 0
    assert context["historical_context_backfilled"] is False


def test_mock_history_cannot_seed_or_mutate_live_cache(tmp_path):
    base = tmp_path / "artifacts"
    base.mkdir()
    live_dir = base / "live_generation"
    mock_dir = base / "mock_generation"
    market_no_send_io.ensure_safe_namespace_dir(live_dir)
    market_no_send_io.ensure_safe_namespace_dir(mock_dir)
    observed = datetime(2026, 7, 12, 12, tzinfo=timezone.utc)
    with _provider_reserved_history(base, live_dir.name, observed) as reservation:
        market_no_send_history_cache.enrich_and_persist_history(
            _normalized_rows(observed),
            artifact_base_dir=base,
            generation_namespace_dir=live_dir,
            history_filename=market_no_send.HISTORY_FILENAME,
            observed_at=observed,
            live_no_send=True,
            campaign_reservation=reservation,
        )
    cache = base / market_no_send_history_cache.LIVE_HISTORY_CACHE_NAMESPACE
    before = (cache / market_no_send.HISTORY_FILENAME).read_bytes()

    _rows, summary, _digest = market_no_send_history_cache.enrich_and_persist_history(
        _normalized_rows(observed + timedelta(hours=1)),
        artifact_base_dir=base,
        generation_namespace_dir=mock_dir,
        history_filename=market_no_send.HISTORY_FILENAME,
        observed_at=observed + timedelta(hours=1),
        live_no_send=False,
    )

    assert summary["cache_scope"] == "generation_local_mock"
    assert summary["shared_seed_rows"] == 0
    assert (cache / market_no_send.HISTORY_FILENAME).read_bytes() == before


def test_generation_cannot_claim_reserved_history_cache_namespace(tmp_path):
    with pytest.raises(market_no_send.MarketNoSendError, match="reserved"):
        market_no_send.build_market_no_send_readiness(
            artifact_namespace=market_no_send_history_cache.LIVE_HISTORY_CACHE_NAMESPACE,
        )


def test_rapid_live_generation_is_retained_as_evidence_without_warming_cache(tmp_path):
    base = tmp_path / "artifacts"
    base.mkdir()
    first_dir = base / "market_generation_1"
    rapid_dir = base / "market_generation_rapid"
    eligible_dir = base / "market_generation_eligible"
    for path in (first_dir, rapid_dir, eligible_dir):
        market_no_send_io.ensure_safe_namespace_dir(path)
    first_at = datetime(2026, 7, 12, 12, tzinfo=timezone.utc)

    with _provider_reserved_history(base, first_dir.name, first_at) as reservation:
        market_no_send_history_cache.enrich_and_persist_history(
            _normalized_rows(first_at),
            artifact_base_dir=base,
            generation_namespace_dir=first_dir,
            history_filename=market_no_send.HISTORY_FILENAME,
            observed_at=first_at,
            live_no_send=True,
            campaign_reservation=reservation,
        )
    rapid_at = first_at + timedelta(minutes=10)
    with _provider_reserved_history(base, rapid_dir.name, rapid_at) as reservation:
        rapid_rows, rapid_summary, _digest = (
            market_no_send_history_cache.enrich_and_persist_history(
                _normalized_rows(rapid_at),
                artifact_base_dir=base,
                generation_namespace_dir=rapid_dir,
                history_filename=market_no_send.HISTORY_FILENAME,
                observed_at=rapid_at,
                live_no_send=True,
                campaign_reservation=reservation,
            )
        )

    assert all(row["market_history_baseline_counted"] is False for row in rapid_rows)
    assert rapid_summary["baseline_counting"]["current"] == {"too_close": 5}
    readiness = market_no_send_history_cache.cache_readiness(
        base,
        history_filename=market_no_send.HISTORY_FILENAME,
        now=rapid_at,
    )
    assert readiness["baseline_observation_count"] == 10
    assert readiness["baseline_counted_observation_count"] == 5
    assert readiness["baseline_too_close_observation_count"] == 5
    assert readiness["cadence_status"] == "waiting"
    assert readiness["next_eligible_observation_at"] == (
        rapid_at + timedelta(hours=1)
    ).isoformat()
    assert set(readiness["baseline_feature_readiness"]) == {
        "volume",
        "turnover",
        "volatility",
        "returns_1h",
        "returns_4h",
        "returns_24h",
        "btc_eth_relative",
    }

    eligible_at = rapid_at + timedelta(hours=1)
    with _provider_reserved_history(base, eligible_dir.name, eligible_at) as reservation:
        eligible_rows, _summary, _digest = (
            market_no_send_history_cache.enrich_and_persist_history(
                _normalized_rows(eligible_at),
                artifact_base_dir=base,
                generation_namespace_dir=eligible_dir,
                history_filename=market_no_send.HISTORY_FILENAME,
                observed_at=eligible_at,
                live_no_send=True,
                campaign_reservation=reservation,
            )
        )
    assert all(row["market_history_baseline_counted"] is True for row in eligible_rows)
    eligible_readiness = market_no_send_history_cache.cache_readiness(
        base,
        history_filename=market_no_send.HISTORY_FILENAME,
        now=eligible_at,
    )
    assert eligible_readiness["baseline_observation_count"] == 15
    assert eligible_readiness["baseline_counted_observation_count"] == 10
    assert eligible_readiness["baseline_too_close_observation_count"] == 5

    current_ids = tuple(
        row["canonical_asset_id"] for row in _normalized_rows(eligible_at)[:2]
    ) + ("missing-current-asset",)
    scoped = market_no_send_history_cache.cache_readiness(
        base,
        history_filename=market_no_send.HISTORY_FILENAME,
        now=eligible_at,
        current_asset_ids=current_ids,
    )["current_universe_maturity"]
    assert scoped["status"] == "incomplete"
    assert scoped["expected_asset_count"] == 3
    assert scoped["observed_asset_count"] == 2
    assert scoped["observed_asset_ids"] == sorted(current_ids[:2])
    assert scoped["missing_asset_count"] == 1
    assert scoped["missing_asset_ids"] == ["missing-current-asset"]
    assert scoped["non_warm_asset_ids"] == sorted(current_ids[:2])
    assert scoped["next_cycle_point_in_time_eligible_at"] == (
        eligible_at + timedelta(hours=1)
    ).isoformat()
    assert scoped["next_cycle_point_in_time_eligible_asset_count"] == 0
    assert scoped["next_cycle_point_in_time_basis"] == (
        "same_asset_retained_history_before_future_observation"
    )
    assert all(
        details["asset_count"] == 2
        for details in scoped["baseline_feature_readiness"].values()
    )
    assert all(
        details["next_cycle_point_in_time_eligible_asset_count"] == 0
        and len(details["deficit_assets"]) == 2
        for details in scoped["baseline_feature_readiness"].values()
    )
    assert all(
        row["canonical_asset_id"] != "missing-current-asset"
        for details in scoped["baseline_feature_readiness"].values()
        for row in details["deficit_assets"]
    )

    all_missing = market_no_send_history_cache.cache_readiness(
        base,
        history_filename=market_no_send.HISTORY_FILENAME,
        now=eligible_at,
        current_asset_ids=("absent-a", "absent-b"),
    )["current_universe_maturity"]
    assert all_missing["status"] == "incomplete"
    assert all_missing["expected_asset_count"] == 2
    assert all_missing["observed_asset_count"] == 0
    assert all_missing["observed_asset_ids"] == []
    assert all_missing["missing_asset_ids"] == ["absent-a", "absent-b"]
    assert all_missing["non_warm_asset_ids"] == []
    assert all_missing["next_cycle_point_in_time_eligible_asset_count"] == 0
    assert all(
        details["asset_count"] == 0
        and details["next_cycle_point_in_time_eligible_asset_count"] == 0
        and details["deficit_assets"] == []
        for details in all_missing["baseline_feature_readiness"].values()
    )


def test_next_cycle_projection_derives_exact_deficits_from_asset_readiness(
    monkeypatch,
):
    assessment = {
        "baseline_status": "warming",
        "baseline_observation_count": 16,
        "baseline_counted_observation_count": 16,
        "baseline_warm_asset_count": 1,
        "baseline_asset_readiness": {
            "asset-a": {
                "status": "warm",
                "feature_readiness": {
                    "volume": {
                        "status": "warm",
                        "sample_count": 8,
                        "required_sample_count": 8,
                        "coverage_seconds": 28_800,
                        "required_coverage_seconds": 25_200,
                    }
                },
            },
            "asset-b": {
                "status": "warming",
                "feature_readiness": {
                    "volume": {
                        "status": "warming",
                        "sample_count": 7,
                        "required_sample_count": 8,
                        "coverage_seconds": 28_800,
                        "required_coverage_seconds": 25_200,
                    }
                },
            },
        },
        "baseline_feature_readiness": {
            "volume": {
                "status_counts": {"warm": 1, "warming": 1},
                "warm_asset_count": 1,
                "warming_asset_count": 1,
                "cold_asset_count": 0,
                "other_asset_count": 0,
                "asset_count": 2,
                "minimum_sample_count": 7,
                "maximum_sample_count": 8,
                "required_sample_count": 8,
                "sample_count_deficit_asset_count": 1,
                "minimum_coverage_seconds": 28_800,
                "maximum_coverage_seconds": 28_800,
                "required_coverage_seconds": 25_200,
                "coverage_deficit_asset_count": 0,
            }
        },
    }
    monkeypatch.setattr(
        market_no_send_history_cache.market_history_readiness,
        "assess_market_history_readiness",
        lambda *_args, **_kwargs: assessment,
    )

    result = market_no_send_history_cache._current_universe_maturity(
        (),
        current_asset_ids=("asset-a", "asset-b", "asset-missing"),
        now="2026-07-19T12:00:00+00:00",
        config=None,
        next_eligible_observation_at="2026-07-19T13:00:00+00:00",
    )

    assert result["observed_asset_ids"] == ["asset-a", "asset-b"]
    assert result["missing_asset_ids"] == ["asset-missing"]
    assert result["non_warm_asset_ids"] == ["asset-b"]
    assert result["baseline_warm_asset_count"] == 1
    assert result["next_cycle_point_in_time_eligible_asset_count"] == 1
    assert result["baseline_feature_readiness"]["volume"]["deficit_assets"] == [
        {
            "canonical_asset_id": "asset-b",
            "status": "warming",
            "sample_count": 7,
            "required_sample_count": 8,
            "sample_deficit": 1,
            "coverage_seconds": 28_800,
            "required_coverage_seconds": 25_200,
            "coverage_deficit_seconds": 0,
        }
    ]


def test_invalid_history_cache_cannot_look_like_honest_missing_evidence(tmp_path):
    base = tmp_path / "artifacts"
    base.mkdir()
    cache_path = base / market_no_send_history_cache.LIVE_HISTORY_CACHE_NAMESPACE
    cache_path.write_text("not a directory", encoding="utf-8")

    readiness = market_no_send_history_cache.cache_readiness(
        base,
        history_filename=market_no_send.HISTORY_FILENAME,
        now="2026-07-19T12:00:00+00:00",
        current_asset_ids=("asset-a", "asset-b"),
    )
    current = readiness["current_universe_maturity"]

    assert readiness["cache_status"] == "invalid"
    assert current["status"] == "unavailable"
    assert current["expected_asset_count"] == 2
    assert current["observed_asset_ids"] == []
    assert current["missing_asset_ids"] == []
    assert current["non_warm_asset_ids"] == []
    assert current["baseline_warm_asset_count"] == 0
    assert current["next_cycle_point_in_time_eligible_asset_count"] == 0
    assert current["next_cycle_point_in_time_eligible_at"] is None
    assert current["baseline_feature_readiness"] == {}


def test_live_history_requires_active_provider_reserved_campaign(tmp_path):
    base = tmp_path / "artifacts"
    base.mkdir()
    generation_dir = base / "live_generation"
    market_no_send_io.ensure_safe_namespace_dir(generation_dir)
    observed = datetime(2026, 7, 12, 12, tzinfo=timezone.utc)
    kwargs = {
        "artifact_base_dir": base,
        "generation_namespace_dir": generation_dir,
        "history_filename": market_no_send.HISTORY_FILENAME,
        "observed_at": observed,
        "live_no_send": True,
    }

    with pytest.raises(
        market_no_send.MarketNoSendError,
        match="active campaign reservation",
    ):
        market_no_send_history_cache.enrich_and_persist_history(
            _normalized_rows(observed),
            **kwargs,
        )

    with market_no_send_campaign_guard.acquire_campaign_reservation(
        base,
        artifact_namespace=generation_dir.name,
        acquired_at=observed,
    ) as reservation:
        with pytest.raises(
            market_no_send.MarketNoSendError,
            match="provider-call reservation",
        ):
            market_no_send_history_cache.enrich_and_persist_history(
                _normalized_rows(observed),
                campaign_reservation=reservation,
                **kwargs,
            )

    with _provider_reserved_history(
        base,
        generation_dir.name,
        observed + timedelta(seconds=1),
    ) as reservation:
        released_reservation = reservation
    with pytest.raises(
        market_no_send.MarketNoSendError,
        match="not active",
    ):
        market_no_send_history_cache.enrich_and_persist_history(
            _normalized_rows(observed),
            campaign_reservation=released_reservation,
            **kwargs,
        )


def test_live_history_rejects_noncanonical_campaign_provenance(tmp_path):
    base = tmp_path / "artifacts"
    base.mkdir()
    generation_dir = base / "live_generation"
    market_no_send_io.ensure_safe_namespace_dir(generation_dir)
    observed = datetime(2026, 7, 12, 12, tzinfo=timezone.utc)
    rows = _normalized_rows(observed)
    rows[0]["decision_radar_campaign_counted"] = False

    with _provider_reserved_history(base, generation_dir.name, observed) as reservation:
        with pytest.raises(
            market_no_send.MarketNoSendError,
            match="canonical campaign provenance",
        ):
            market_no_send_history_cache.enrich_and_persist_history(
                rows,
                artifact_base_dir=base,
                generation_namespace_dir=generation_dir,
                history_filename=market_no_send.HISTORY_FILENAME,
                observed_at=observed,
                live_no_send=True,
                campaign_reservation=reservation,
            )
