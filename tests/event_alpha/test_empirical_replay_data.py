"""Offline, point-in-time input regressions for the empirical replay lab."""

from __future__ import annotations

import hashlib
import json
import socket
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import crypto_rsi_scanner.event_alpha.operations.empirical_replay_data as replay_data


START = datetime(2025, 1, 1, tzinfo=timezone.utc)
DAY_MS = 86_400_000


def test_mode_universe_sizes_match_frozen_protocol() -> None:
    assert replay_data.replay_data_mode_config("smoke").universe_top_n == 3
    assert replay_data.replay_data_mode_config("medium").universe_top_n == 30
    assert replay_data.replay_data_mode_config("full").universe_top_n == 100


def _kline_rows(
    count: int,
    *,
    quote_volume: float,
    price_start: float = 100.0,
    start: datetime = START,
) -> list[list[object]]:
    rows: list[list[object]] = []
    for offset in range(count):
        opened = start + timedelta(days=offset)
        open_ms = int(opened.timestamp() * 1000)
        close = price_start + offset
        base_volume = quote_volume / close
        rows.append(
            [
                open_ms,
                f"{close:.8f}",
                f"{close * 1.01:.8f}",
                f"{close * 0.99:.8f}",
                f"{close:.8f}",
                f"{base_volume:.8f}",
                open_ms + DAY_MS - 1,
                f"{quote_volume:.8f}",
                100,
                "0",
                "0",
                "0",
            ]
        )
    return rows


def _write_json(path: Path, rows: list[list[object]]) -> None:
    path.write_text(json.dumps(rows, separators=(",", ":")), encoding="utf-8")


def _write_fixture(path: Path, count: int = 40) -> None:
    lines = ["date,close,volume"]
    for offset in range(count):
        opened = START + timedelta(days=offset)
        lines.append(f"{opened.isoformat()},{100 + offset:.8f},{1000 + offset:.8f}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _feature_projection(rows: list[dict], *, through: str) -> list[dict]:
    fields = (
        "symbol",
        "observed_at",
        "in_universe",
        "volume_rank",
        "trailing_quote_volume",
        "membership_status",
        "baseline_status",
        "volume_baseline_status",
        "volume_baseline_count",
        "return_24h",
        "return_72h",
        "return_7d",
        "volume_zscore_24h",
        "rsi",
    )
    return [
        {field: row[field] for field in fields}
        for row in rows
        if row["observed_at"] <= through
    ]


def test_cache_loader_is_zero_network_selects_longest_and_catalogs_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    cache = tmp_path / "binance_klines"
    cache.mkdir()
    short = _kline_rows(31, quote_volume=1_000_000)
    longest = _kline_rows(35, quote_volume=1_500_000)
    btc = _kline_rows(35, quote_volume=20_000_000, price_start=30_000)
    _write_json(cache / "AAAUSDT-30d.json", short)
    _write_json(cache / "AAAUSDT-60d.json", longest)
    _write_json(cache / "BTCUSDT-60d.json", btc)

    def forbidden_network(*_args, **_kwargs):
        raise AssertionError("offline replay loader attempted network access")

    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    dataset = replay_data.load_binance_cache_dataset(cache, mode="medium")

    aaa = next(item for item in dataset.series if item.symbol == "AAAUSDT")
    assert aaa.relative_path == "AAAUSDT-60d.json"
    assert len(aaa.bars) == 35
    assert dataset.frames()["AAAUSDT"][-1]["close"] == pytest.approx(134.0)

    catalog = replay_data.build_replay_catalog(dataset)
    expected = hashlib.sha256((cache / "AAAUSDT-60d.json").read_bytes()).hexdigest()
    aaa_file = next(row for row in catalog["files"] if row["symbol"] == "AAAUSDT")
    assert aaa_file["content_sha256"] == expected
    assert aaa_file["row_count"] == 35
    assert catalog["candidate_files_discovered"] == 3
    assert catalog["candidate_symbols_discovered"] == 2
    assert catalog["selected_file_count"] == 2
    assert catalog["residual_survivorship_present"] is True
    assert "fully delisted assets are absent" in catalog["residual_survivorship_disclosure"]
    assert catalog["provider_calls"] == 0
    assert catalog["network_access"] is False
    assert catalog["final_test_evaluated"] is False
    assert len(catalog["catalog_digest"]) == 64


def test_point_in_time_trailing_volume_rank_is_deterministic(tmp_path: Path):
    cache = tmp_path / "binance_klines"
    cache.mkdir()
    _write_json(cache / "AAAUSDT-60d.json", _kline_rows(31, quote_volume=1_000_000))
    _write_json(cache / "BBBUSDT-60d.json", _kline_rows(31, quote_volume=2_000_000))
    dataset = replay_data.load_binance_cache_dataset(cache, mode="medium")

    membership = replay_data.build_point_in_time_volume_membership(
        dataset,
        top_n=1,
        window_days=30,
    )
    final_time = max(row["observed_at"] for row in membership)
    final = {
        row["symbol"]: row
        for row in membership
        if row["observed_at"] == final_time
    }
    assert final["BBBUSDT"]["rank"] == 1
    assert final["BBBUSDT"]["in_universe"] is True
    assert final["AAAUSDT"]["rank"] == 2
    assert final["AAAUSDT"]["in_universe"] is False
    assert final["BBBUSDT"]["trailing_quote_volume"] == pytest.approx(2_000_000)
    assert final["BBBUSDT"]["feature_basis"] == "point_in_time_volume_universe"


def test_appending_future_rows_cannot_change_earlier_features_or_membership(
    tmp_path: Path,
):
    cache = tmp_path / "binance_klines"
    cache.mkdir()
    a_path = cache / "AAAUSDT-99d.json"
    b_path = cache / "BBBUSDT-99d.json"
    a_rows = _kline_rows(40, quote_volume=1_000_000)
    b_rows = _kline_rows(40, quote_volume=2_000_000)
    _write_json(a_path, a_rows)
    _write_json(b_path, b_rows)

    before_dataset = replay_data.load_binance_cache_dataset(cache, mode="medium")
    before = list(
        replay_data.iter_point_in_time_observations(
            before_dataset,
            top_n=1,
        )
    )
    cutoff = max(row["observed_at"] for row in before)

    a_rows.extend(
        _kline_rows(
            1,
            quote_volume=50_000_000,
            price_start=500,
            start=START + timedelta(days=40),
        )
    )
    b_rows.extend(
        _kline_rows(
            1,
            quote_volume=500_000,
            price_start=50,
            start=START + timedelta(days=40),
        )
    )
    _write_json(a_path, a_rows)
    _write_json(b_path, b_rows)

    after_dataset = replay_data.load_binance_cache_dataset(cache, mode="medium")
    after = list(
        replay_data.iter_point_in_time_observations(
            after_dataset,
            top_n=1,
        )
    )
    assert _feature_projection(before, through=cutoff) == _feature_projection(
        after,
        through=cutoff,
    )


def test_fixture_observations_keep_intraday_spread_and_proxy_basis_explicit(
    tmp_path: Path,
):
    fixtures = tmp_path / "klines"
    fixtures.mkdir()
    _write_fixture(fixtures / "BTCUSDT.csv")
    dataset = replay_data.load_fixture_dataset(fixtures)
    observations = list(replay_data.iter_point_in_time_observations(dataset))
    latest = observations[-1]

    assert latest["canonical_asset_id"] == "bitcoin"
    assert latest["open"] is None
    assert latest["high"] is None
    assert latest["low"] is None
    assert latest["quote_volume"] == pytest.approx(latest["close"] * latest["base_volume"])
    assert latest["point_in_time_universe_member"] == latest["in_universe"]
    assert latest["point_in_time_volume_rank"] == latest["volume_rank"]
    assert latest["data_quality_mode"] == "cross_sectional_proxy"
    assert latest["market_data_source"] == "checked_fixture_historical_ohlcv"
    assert latest["feature_basis"]["quote_volume"] == "cross_sectional_proxy"
    assert latest["feature_basis"]["volume_zscore_24h"] == "cross_sectional_proxy"
    assert latest["feature_basis"]["intraday_returns"] == "missing"
    assert latest["feature_basis"]["spread_bps"] == "unavailable"
    assert latest["market_data_basis"] == "historical_ohlcv"
    assert latest["volume_anomaly_basis"] == "cross_sectional_proxy"
    assert latest["liquidity_basis"] == "cross_sectional_proxy"
    assert latest["spread_bps"] is None
    assert latest["spread_status"] == "unavailable"
    assert latest["intraday_status"] == "missing"
    assert "return_4h" in latest["missing_features"]
    assert "spread_bps" in latest["missing_features"]
    assert latest["provider_calls"] == 0
    assert latest["final_test_evaluated"] is False


def test_volume_zscore_baseline_is_shifted_before_current_bar(tmp_path: Path):
    cache = tmp_path / "binance_klines"
    cache.mkdir()
    rows = _kline_rows(21, quote_volume=1_000_000)
    for index, row in enumerate(rows):
        row[7] = float(index + 1)
    rows[-1][7] = 1_000.0
    _write_json(cache / "AAAUSDT-30d.json", rows)
    dataset = replay_data.load_binance_cache_dataset(cache)

    latest = list(replay_data.iter_point_in_time_observations(dataset))[-1]
    prior = list(range(1, 21))
    expected = (1_000.0 - (sum(prior) / len(prior))) / statistics.pstdev(prior)
    assert latest["volume_baseline_count"] == 20
    assert latest["volume_zscore_24h"] == pytest.approx(expected)
    assert latest["feature_basis"]["volume_zscore_24h"] == "temporal_direct"


def test_partial_daily_bar_is_inventoried_but_never_warms_or_enters_universe(
    tmp_path: Path,
):
    cache = tmp_path / "binance_klines"
    cache.mkdir()
    rows = _kline_rows(35, quote_volume=1_000_000)
    rows[2][6] = int(rows[2][0]) + 3 * 60 * 60 * 1000 - 1
    _write_json(cache / "AAAUSDT-60d.json", rows)
    dataset = replay_data.load_binance_cache_dataset(cache)

    catalog = replay_data.build_replay_catalog(dataset)
    assert catalog["partial_bar_count"] == 1
    assert catalog["files"][0]["partial_bar_count"] == 1
    observations = list(replay_data.iter_point_in_time_observations(dataset))
    partial = next(row for row in observations if row["bar_duration_status"] == "partial_daily")
    assert partial["bar_duration_seconds"] == 3 * 60 * 60
    assert partial["baseline_status"] == "partial_bar"
    assert partial["point_in_time_universe_member"] is False
    assert partial["volume_zscore_24h"] is None
    assert partial["return_24h"] is None
    assert partial["rsi"] is None
    assert "daily_bar_complete" in partial["missing_features"]


def test_malformed_and_symlink_inputs_fail_closed(tmp_path: Path):
    malformed = tmp_path / "malformed"
    malformed.mkdir()
    (malformed / "AAAUSDT-30d.json").write_text(
        json.dumps([["bad"]]),
        encoding="utf-8",
    )
    with pytest.raises(replay_data.ReplayDataError, match="row_schema_invalid"):
        replay_data.load_binance_cache_dataset(malformed)

    outside = tmp_path / "outside.json"
    _write_json(outside, _kline_rows(31, quote_volume=1_000_000))
    linked = tmp_path / "linked"
    linked.mkdir()
    (linked / "AAAUSDT-30d.json").symlink_to(outside)
    with pytest.raises(replay_data.ReplayDataError, match="input_file_not_regular"):
        replay_data.load_binance_cache_dataset(linked)

    root_link = tmp_path / "root-link"
    root_link.symlink_to(linked, target_is_directory=True)
    with pytest.raises(replay_data.ReplayDataError, match="directory_unavailable_or_unsafe"):
        replay_data.load_binance_cache_dataset(root_link)


def test_final_test_partition_is_not_opened_by_input_iterator(tmp_path: Path):
    cache = tmp_path / "binance_klines"
    cache.mkdir()
    _write_json(cache / "BTCUSDT-60d.json", _kline_rows(31, quote_volume=2_000_000))
    dataset = replay_data.load_binance_cache_dataset(cache)

    with pytest.raises(replay_data.ReplayDataError, match="final_test_evaluation_forbidden"):
        list(
            replay_data.iter_point_in_time_observations(
                dataset,
                partitions={
                    "final_test": (
                        "2025-01-01T00:00:00Z",
                        "2025-02-01T00:00:00Z",
                    )
                },
            )
        )
