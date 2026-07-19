"""Persistence tests for the rolling live no-send market baseline."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest

from crypto_rsi_scanner.event_alpha.operations import market_no_send
from crypto_rsi_scanner.event_alpha.operations import market_no_send_campaign_guard
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
    assert (first_dir / market_no_send.HISTORY_FILENAME).read_bytes() == first_snapshot


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
