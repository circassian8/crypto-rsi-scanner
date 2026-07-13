"""Persistence tests for the rolling live no-send market baseline."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from crypto_rsi_scanner.event_alpha.operations import market_no_send
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
        burn_in_counted=True,
    )
    return rows


def test_live_history_cache_rolls_across_immutable_generation_namespaces(tmp_path):
    base = tmp_path / "artifacts"
    base.mkdir()
    first_dir = base / "market_generation_1"
    second_dir = base / "market_generation_2"
    market_no_send_io.ensure_safe_namespace_dir(first_dir)
    market_no_send_io.ensure_safe_namespace_dir(second_dir)
    first_at = datetime(2026, 7, 12, 12, tzinfo=timezone.utc)

    _rows, first_summary, _digest = market_no_send_history_cache.enrich_and_persist_history(
        _normalized_rows(first_at),
        artifact_base_dir=base,
        generation_namespace_dir=first_dir,
        history_filename=market_no_send.HISTORY_FILENAME,
        observed_at=first_at,
        live_no_send=True,
    )
    first_snapshot = (first_dir / market_no_send.HISTORY_FILENAME).read_bytes()
    second_rows, second_summary, _digest = (
        market_no_send_history_cache.enrich_and_persist_history(
            _normalized_rows(first_at + timedelta(hours=1)),
            artifact_base_dir=base,
            generation_namespace_dir=second_dir,
            history_filename=market_no_send.HISTORY_FILENAME,
            observed_at=first_at + timedelta(hours=1),
            live_no_send=True,
        )
    )

    assert first_summary["shared_seed_rows"] == 0
    assert second_summary["shared_seed_rows"] == 5
    assert all(row["market_history"]["prior_observation_count"] == 1 for row in second_rows)
    assert (first_dir / market_no_send.HISTORY_FILENAME).read_bytes() == first_snapshot


def test_mock_history_cannot_seed_or_mutate_live_cache(tmp_path):
    base = tmp_path / "artifacts"
    base.mkdir()
    live_dir = base / "live_generation"
    mock_dir = base / "mock_generation"
    market_no_send_io.ensure_safe_namespace_dir(live_dir)
    market_no_send_io.ensure_safe_namespace_dir(mock_dir)
    observed = datetime(2026, 7, 12, 12, tzinfo=timezone.utc)
    market_no_send_history_cache.enrich_and_persist_history(
        _normalized_rows(observed),
        artifact_base_dir=base,
        generation_namespace_dir=live_dir,
        history_filename=market_no_send.HISTORY_FILENAME,
        observed_at=observed,
        live_no_send=True,
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
