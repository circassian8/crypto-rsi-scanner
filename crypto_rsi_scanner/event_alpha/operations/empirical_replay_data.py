"""Bounded, zero-network market inputs for Decision Radar empirical replay.

This module is deliberately limited to input preparation.  It reads either the
checked daily smoke fixtures or an explicitly supplied Binance-klines cache,
builds point-in-time volume membership and trailing features, and exposes JSON
shaped observations for downstream replay and outcome code.  It never calls a
provider, evaluates a final-test partition, routes an idea, or writes an
artifact.

Public APIs
-----------
``replay_data_mode_config``
    Return one frozen smoke/medium/full resource configuration.
``load_binance_cache_dataset`` / ``load_fixture_dataset``
    Read a descriptor-anchored directory into an immutable ``ReplayDataset``.
``build_replay_catalog``
    Return the content-addressed, secret-free input inventory.
``build_point_in_time_volume_membership``
    Rank only trailing observations available at each daily close.
``iter_point_in_time_observations``
    Yield production-oriented replay inputs with explicit missing-data basis.

The Binance cache is necessarily survivorship-reduced rather than
survivorship-free: its symbol inventory was seeded from currently trading
pairs, so fully delisted assets are absent.  The catalog preserves that caveat
instead of allowing downstream reports to imply a complete historical
universe.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import re
import stat
import statistics
from collections import defaultdict, deque
from collections.abc import Iterator, Mapping, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from ... import config
from ...indicators import wilder_rsi
from .empirical_replay_data_bar import ReplayBar
from .empirical_replay_data_dataset import ReplayDataset
from .empirical_replay_data_error import ReplayDataError
from .empirical_replay_data_mode import ReplayDataModeConfig
from .empirical_replay_data_series import ReplaySeries
from . import empirical_validation_protocol


CATALOG_SCHEMA_ID = "decision_radar.empirical_replay_input_catalog"
CATALOG_SCHEMA_VERSION = 1
DATASET_SCHEMA_ID = "decision_radar.empirical_replay_dataset"
DATASET_SCHEMA_VERSION = 1
OBSERVATION_SCHEMA_ID = "decision_radar.empirical_replay_observation"
OBSERVATION_SCHEMA_VERSION = 1
DAY_MILLISECONDS = 86_400_000
MAX_DIRECTORY_ENTRIES = 8_192
MAX_PARTITIONS = 2
ALLOWED_RESEARCH_PARTITIONS = frozenset({"development", "validation"})
RESIDUAL_SURVIVORSHIP_DISCLOSURE = (
    "Binance cache symbols were seeded from currently trading USDT pairs; "
    "fully delisted assets are absent, so the replay universe is "
    "point-in-time by trailing volume within a residual-survivorship pool."
)

_CACHE_NAME_RE = re.compile(
    r"^(?P<symbol>[A-Z0-9]{1,30}USDT)-(?P<days>[1-9][0-9]{0,4})d\.json$"
)
_FIXTURE_NAME_RE = re.compile(r"^(?P<symbol>[A-Z0-9]{1,30}USDT)\.csv$")
REPLAY_DATA_MODE_CONFIGS: Mapping[str, ReplayDataModeConfig] = {
    "smoke": ReplayDataModeConfig(
        name="smoke",
        max_symbols=3,
        universe_top_n=3,
    ),
    "medium": ReplayDataModeConfig(
        name="medium",
        # Rank the frozen medium top-30 across the complete bounded candidate
        # pool; an alphabetic 30-symbol subsample would not be point-in-time.
        max_symbols=512,
        universe_top_n=30,
    ),
    "full": ReplayDataModeConfig(
        name="full",
        max_symbols=512,
        universe_top_n=100,
    ),
}


def replay_data_mode_config(mode: str) -> ReplayDataModeConfig:
    """Return the frozen smoke/medium/full configuration, failing on aliases."""

    name = str(mode or "").strip().casefold()
    try:
        data_mode = REPLAY_DATA_MODE_CONFIGS[name]
    except KeyError as exc:
        raise ReplayDataError(f"replay_data_mode_invalid:{name or 'missing'}") from exc
    _validate_data_mode_protocol_alignment(data_mode)
    return data_mode


def _validate_data_mode_protocol_alignment(data_mode: ReplayDataModeConfig) -> None:
    warmup = empirical_validation_protocol.protocol_values()["feature_warmup"]
    if (
        data_mode.volume_z_window
        != int(warmup["volume_zscore_lookback_days"])
        or data_mode.volume_z_min_observations
        != int(warmup["volume_zscore_min_observations"])
    ):
        raise ReplayDataError(
            f"replay_data_mode_volume_zscore_protocol_drift:{data_mode.name}"
        )


def load_binance_cache_dataset(
    cache_dir: str | Path,
    *,
    mode: str = "medium",
) -> ReplayDataset:
    """Read a Binance daily-klines cache without importing or calling a provider.

    Exactly one file is selected for each bounded symbol: the greatest declared
    ``-Nd`` horizon wins, followed by the filename as a deterministic tiebreaker.
    Matching symlinks and non-regular files are rejected before content is read.
    """

    cfg = replay_data_mode_config(mode)
    directory_fd = _open_directory(cache_dir)
    try:
        candidates = _matching_regular_files(directory_fd, _CACHE_NAME_RE)
        if not candidates:
            raise ReplayDataError("binance_cache_files_missing")
        grouped: dict[str, list[tuple[int, str]]] = defaultdict(list)
        for name, match in candidates:
            grouped[match.group("symbol")].append((int(match.group("days")), name))
        selected_by_symbol = {
            symbol: sorted(values, key=lambda item: (-item[0], item[1]))[0]
            for symbol, values in grouped.items()
        }
        selected_symbols = sorted(selected_by_symbol)[: cfg.max_symbols]
        series: list[ReplaySeries] = []
        for symbol in selected_symbols:
            declared_days, name = selected_by_symbol[symbol]
            raw, file_stat = _read_regular_file(
                directory_fd,
                name,
                max_bytes=cfg.max_file_bytes,
            )
            bars = _parse_binance_rows(
                raw,
                max_rows=cfg.max_rows_per_symbol,
            )
            series.append(
                ReplaySeries(
                    symbol=symbol,
                    canonical_asset_id=_canonical_asset_id(symbol),
                    relative_path=name,
                    declared_days=declared_days,
                    byte_size=file_stat.st_size,
                    content_sha256=hashlib.sha256(raw).hexdigest(),
                    quote_volume_basis="historical_ohlcv",
                    bars=bars,
                )
            )
    finally:
        os.close(directory_fd)
    return ReplayDataset(
        mode=cfg,
        source_kind="binance_daily_klines_cache",
        candidate_files_discovered=len(candidates),
        candidate_symbols_discovered=len(grouped),
        series=tuple(series),
        residual_survivorship_present=True,
        residual_survivorship_disclosure=RESIDUAL_SURVIVORSHIP_DISCLOSURE,
    )


def load_fixture_dataset(
    fixture_dir: str | Path,
    *,
    mode: str = "smoke",
) -> ReplayDataset:
    """Read checked daily CSV smoke fixtures with explicit proxy-volume basis.

    Fixture CSV contains close and base volume only.  Quote volume is therefore
    derived as ``close * base_volume`` and marked ``cross_sectional_proxy``;
    high, low, open, intraday features, and spread remain explicitly missing.
    """

    cfg = replay_data_mode_config(mode)
    directory_fd = _open_directory(fixture_dir)
    try:
        candidates = _matching_regular_files(directory_fd, _FIXTURE_NAME_RE)
        if not candidates:
            raise ReplayDataError("fixture_files_missing")
        selected = candidates[: cfg.max_symbols]
        series: list[ReplaySeries] = []
        for name, match in selected:
            symbol = match.group("symbol")
            raw, file_stat = _read_regular_file(
                directory_fd,
                name,
                max_bytes=cfg.max_file_bytes,
            )
            bars = _parse_fixture_rows(raw, max_rows=cfg.max_rows_per_symbol)
            series.append(
                ReplaySeries(
                    symbol=symbol,
                    canonical_asset_id=_canonical_asset_id(symbol),
                    relative_path=name,
                    declared_days=None,
                    byte_size=file_stat.st_size,
                    content_sha256=hashlib.sha256(raw).hexdigest(),
                    quote_volume_basis="cross_sectional_proxy",
                    bars=bars,
                )
            )
    finally:
        os.close(directory_fd)
    return ReplayDataset(
        mode=cfg,
        source_kind="checked_daily_smoke_fixture",
        candidate_files_discovered=len(candidates),
        candidate_symbols_discovered=len(candidates),
        series=tuple(sorted(series, key=lambda item: item.symbol)),
        residual_survivorship_present=False,
        residual_survivorship_disclosure=(
            "Fixture symbols are a preselected smoke sample and are not eligible "
            "for empirical universe or strategy claims."
        ),
    )


def build_replay_catalog(dataset: ReplayDataset) -> dict[str, Any]:
    """Return a canonical content-addressed input catalog for ``dataset``."""

    files = []
    first_open = min(item.bars[0].bar_open_at for item in dataset.series)
    last_open = max(item.bars[-1].bar_open_at for item in dataset.series)
    last_observed = max(item.bars[-1].observed_at for item in dataset.series)
    total_rows = 0
    partial_bar_count = 0
    for item in dataset.series:
        row_count = len(item.bars)
        file_partial_count = sum(not bar.full_daily_bar for bar in item.bars)
        total_rows += row_count
        partial_bar_count += file_partial_count
        files.append(
            {
                "symbol": item.symbol,
                "canonical_asset_id": item.canonical_asset_id,
                "relative_path": item.relative_path,
                "declared_days": item.declared_days,
                "byte_size": item.byte_size,
                "content_sha256": item.content_sha256,
                "row_count": row_count,
                "partial_bar_count": file_partial_count,
                "first_bar_open_at": _iso(item.bars[0].bar_open_at),
                "last_bar_open_at": _iso(item.bars[-1].bar_open_at),
                "last_observed_at": _iso(item.bars[-1].observed_at),
                "quote_volume_basis": item.quote_volume_basis,
            }
        )
    values: dict[str, Any] = {
        "schema_id": CATALOG_SCHEMA_ID,
        "schema_version": CATALOG_SCHEMA_VERSION,
        "dataset_schema_id": DATASET_SCHEMA_ID,
        "dataset_schema_version": DATASET_SCHEMA_VERSION,
        "mode": dataset.mode.name,
        "source_kind": dataset.source_kind,
        "selection_policy": "longest_declared_days_then_filename_per_symbol",
        "candidate_files_discovered": dataset.candidate_files_discovered,
        "candidate_symbols_discovered": dataset.candidate_symbols_discovered,
        "selected_file_count": len(dataset.series),
        "selected_symbol_count": len(dataset.series),
        "symbols_truncated_by_mode": (
            dataset.candidate_symbols_discovered > len(dataset.series)
        ),
        "row_count": total_rows,
        "partial_bar_count": partial_bar_count,
        "data_start_at": _iso(first_open),
        "last_bar_open_at": _iso(last_open),
        "data_end_at": _iso(last_observed),
        "files": files,
        "residual_survivorship_present": dataset.residual_survivorship_present,
        "residual_survivorship_disclosure": (
            dataset.residual_survivorship_disclosure
        ),
        "network_access": False,
        "provider_calls": 0,
        "final_test_evaluated": False,
        "research_only": True,
    }
    values["catalog_digest"] = _digest(values)
    return values


def build_point_in_time_volume_membership(
    dataset: ReplayDataset,
    *,
    top_n: int | None = None,
    window_days: int | None = None,
) -> tuple[dict[str, Any], ...]:
    """Return exact per-close volume ranks using only bars available by that close.

    Trailing volume includes the current completed daily bar and the preceding
    ``window_days - 1`` completed bars.  A gap in that calendar window leaves
    membership warming rather than silently treating 30 observations as 30
    consecutive days.  Ties use symbol order for deterministic exact top-N.
    """

    index, limit, window = _point_in_time_membership_index(
        dataset,
        top_n=top_n,
        window_days=window_days,
    )
    values: list[dict[str, Any]] = []
    for (symbol, observed_at), membership in sorted(
        index.items(), key=lambda item: (item[0][1], item[0][0])
    ):
        rank, in_universe, trailing, status = membership
        values.append(
            {
                "symbol": symbol,
                "observed_at": _iso(observed_at),
                "rank": rank,
                "in_universe": in_universe,
                "trailing_quote_volume": trailing,
                "membership_status": status,
                "membership_window_days": window,
                "membership_top_n": limit,
                "feature_basis": "point_in_time_volume_universe",
            }
        )
    return tuple(values)


def _point_in_time_membership_index(
    dataset: ReplayDataset,
    *,
    top_n: int | None,
    window_days: int | None,
) -> tuple[
    dict[tuple[str, datetime], tuple[int | None, bool, float | None, str]],
    int,
    int,
]:
    limit = dataset.mode.universe_top_n if top_n is None else _positive_int(top_n, "top_n")
    window = (
        dataset.mode.membership_window_days
        if window_days is None
        else _positive_int(window_days, "window_days")
    )
    if limit > dataset.mode.max_symbols:
        raise ReplayDataError("membership_top_n_bound_exceeded")
    if window > dataset.mode.max_rows_per_symbol:
        raise ReplayDataError("membership_window_bound_exceeded")
    trailing_by_time: dict[datetime, list[tuple[str, float]]] = defaultdict(list)
    symbols_by_time: dict[datetime, list[str]] = defaultdict(list)
    status_by_key: dict[tuple[str, datetime], str] = {}
    for item in dataset.series:
        rolling: deque[ReplayBar] = deque(maxlen=window)
        for bar in item.bars:
            symbols_by_time[bar.observed_at].append(item.symbol)
            rolling.append(bar)
            key = (item.symbol, bar.observed_at)
            if not _complete_daily_window(rolling, window):
                status_by_key[key] = "warming"
                continue
            trailing = statistics.fmean(value.quote_volume for value in rolling)
            trailing_by_time[bar.observed_at].append((item.symbol, trailing))
            status_by_key[key] = "ready"

    index: dict[
        tuple[str, datetime], tuple[int | None, bool, float | None, str]
    ] = {}
    for observed_at in sorted(symbols_by_time):
        ranked = sorted(
            trailing_by_time.get(observed_at, ()),
            key=lambda item: (-item[1], item[0]),
        )
        rank_by_symbol = {
            symbol: (rank, trailing)
            for rank, (symbol, trailing) in enumerate(ranked, 1)
        }
        symbols_at_time = sorted(symbols_by_time[observed_at])
        for symbol in symbols_at_time:
            rank_value = rank_by_symbol.get(symbol)
            rank = rank_value[0] if rank_value else None
            trailing = rank_value[1] if rank_value else None
            index[(symbol, observed_at)] = (
                rank,
                bool(rank is not None and rank <= limit),
                trailing,
                status_by_key.get((symbol, observed_at), "warming"),
            )
    return index, limit, window


def iter_point_in_time_observations(
    dataset: ReplayDataset,
    *,
    partitions: Mapping[str, Sequence[datetime | str]] | None = None,
    top_n: int | None = None,
    membership_window: int | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield deterministic observations through the private bounded assembler.

    Optional partitions are half-open ``[start, end)`` UTC ranges and may name
    only ``development`` and ``validation``.  ``final_test`` remains rejected,
    and all feature values remain point-in-time.
    """

    from ._empirical_replay_observations import (
        _iter_point_in_time_observations,
    )

    yield from _iter_point_in_time_observations(
        dataset,
        partitions=partitions,
        top_n=top_n,
        membership_window=membership_window,
    )


def _open_directory(path: str | Path) -> int:
    value = Path(path).expanduser()
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(value, flags)
    except OSError as exc:
        raise ReplayDataError("input_directory_unavailable_or_unsafe") from exc
    file_stat = os.fstat(descriptor)
    if not stat.S_ISDIR(file_stat.st_mode):
        os.close(descriptor)
        raise ReplayDataError("input_path_not_directory")
    return descriptor


def _matching_regular_files(
    directory_fd: int,
    pattern: re.Pattern[str],
) -> list[tuple[str, re.Match[str]]]:
    names = sorted(os.listdir(directory_fd))
    if len(names) > MAX_DIRECTORY_ENTRIES:
        raise ReplayDataError("input_directory_entry_bound_exceeded")
    matches: list[tuple[str, re.Match[str]]] = []
    for name in names:
        match = pattern.fullmatch(name)
        if match is None:
            continue
        file_stat = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if not stat.S_ISREG(file_stat.st_mode):
            raise ReplayDataError(f"input_file_not_regular:{name}")
        matches.append((name, match))
    return matches


def _read_regular_file(
    directory_fd: int,
    name: str,
    *,
    max_bytes: int,
) -> tuple[bytes, os.stat_result]:
    if Path(name).name != name or name in {".", ".."}:
        raise ReplayDataError("input_relative_path_invalid")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(name, flags, dir_fd=directory_fd)
    except OSError as exc:
        raise ReplayDataError(f"input_file_open_failed:{name}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ReplayDataError(f"input_file_not_regular:{name}")
        if before.st_size < 1 or before.st_size > max_bytes:
            raise ReplayDataError(f"input_file_size_invalid:{name}")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, max_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > max_bytes:
                raise ReplayDataError(f"input_file_size_invalid:{name}")
        after = os.fstat(descriptor)
        identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        if identity_before != identity_after or total != before.st_size:
            raise ReplayDataError(f"input_file_changed_while_reading:{name}")
        return b"".join(chunks), after
    finally:
        os.close(descriptor)


def _parse_binance_rows(raw: bytes, *, max_rows: int) -> tuple[ReplayBar, ...]:
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReplayDataError("binance_cache_json_invalid") from exc
    if not isinstance(payload, list) or not payload or len(payload) > max_rows:
        raise ReplayDataError("binance_cache_row_bound_or_root_invalid")
    bars: list[ReplayBar] = []
    previous_open_ms: int | None = None
    for index, row in enumerate(payload):
        if not isinstance(row, list) or not 8 <= len(row) <= 16:
            raise ReplayDataError(f"binance_cache_row_schema_invalid:{index}")
        open_ms = _strict_integer(row[0], f"open_time:{index}")
        close_ms = _strict_integer(row[6], f"close_time:{index}")
        duration_ms = close_ms + 1 - open_ms
        if (
            open_ms % DAY_MILLISECONDS
            or duration_ms <= 0
            or duration_ms > DAY_MILLISECONDS
            or duration_ms % 1000
        ):
            raise ReplayDataError(f"binance_cache_daily_clock_invalid:{index}")
        if previous_open_ms is not None and open_ms <= previous_open_ms:
            raise ReplayDataError(f"binance_cache_time_order_invalid:{index}")
        previous_open_ms = open_ms
        open_value = _finite_number(row[1], f"open:{index}", positive=True)
        high = _finite_number(row[2], f"high:{index}", positive=True)
        low = _finite_number(row[3], f"low:{index}", positive=True)
        close = _finite_number(row[4], f"close:{index}", positive=True)
        base_volume = _finite_number(row[5], f"base_volume:{index}", minimum=0.0)
        quote_volume = _finite_number(row[7], f"quote_volume:{index}", minimum=0.0)
        if high < max(open_value, close, low) or low > min(open_value, close, high):
            raise ReplayDataError(f"binance_cache_ohlc_invalid:{index}")
        bars.append(
            ReplayBar(
                bar_open_at=datetime.fromtimestamp(open_ms / 1000, timezone.utc),
                observed_at=datetime.fromtimestamp((close_ms + 1) / 1000, timezone.utc),
                open=open_value,
                high=high,
                low=low,
                close=close,
                base_volume=base_volume,
                quote_volume=quote_volume,
                bar_duration_seconds=duration_ms // 1000,
                full_daily_bar=duration_ms == DAY_MILLISECONDS,
            )
        )
    return tuple(bars)


def _parse_fixture_rows(raw: bytes, *, max_rows: int) -> tuple[ReplayBar, ...]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ReplayDataError("fixture_utf8_invalid") from exc
    if "\x00" in text:
        raise ReplayDataError("fixture_nul_invalid")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames != ["date", "close", "volume"]:
        raise ReplayDataError("fixture_columns_invalid")
    bars: list[ReplayBar] = []
    previous: datetime | None = None
    for index, row in enumerate(reader):
        if index >= max_rows:
            raise ReplayDataError("fixture_row_bound_exceeded")
        opened = _aware_utc(row.get("date"), field=f"date:{index}")
        if opened.hour or opened.minute or opened.second or opened.microsecond:
            raise ReplayDataError(f"fixture_daily_clock_invalid:{index}")
        if previous is not None and opened <= previous:
            raise ReplayDataError(f"fixture_time_order_invalid:{index}")
        previous = opened
        close = _finite_number(row.get("close"), f"close:{index}", positive=True)
        volume = _finite_number(row.get("volume"), f"volume:{index}", minimum=0.0)
        bars.append(
            ReplayBar(
                bar_open_at=opened,
                observed_at=opened + timedelta(days=1),
                open=None,
                high=None,
                low=None,
                close=close,
                base_volume=volume,
                quote_volume=close * volume,
                bar_duration_seconds=DAY_MILLISECONDS // 1000,
                full_daily_bar=True,
            )
        )
    if not bars:
        raise ReplayDataError("fixture_rows_empty")
    return tuple(bars)


def _series_analytics(
    series: ReplaySeries,
    mode: ReplayDataModeConfig,
) -> dict[datetime, dict[str, Any]]:
    rsi_values = _segmented_rsi(series.bars)
    by_open = {bar.bar_open_at: bar for bar in series.bars}
    prior_volumes: deque[float] = deque(maxlen=mode.volume_z_window)
    values: dict[datetime, dict[str, Any]] = {}
    previous_full_open: datetime | None = None
    for bar in series.bars:
        if not bar.full_daily_bar:
            values[bar.bar_open_at] = {
                "return_24h": None,
                "return_72h": None,
                "return_7d": None,
                "volume_zscore_24h": None,
                "volume_baseline_status": "partial_bar",
                "volume_baseline_count": 0,
                "rsi": None,
            }
            prior_volumes.clear()
            previous_full_open = None
            continue
        if (
            previous_full_open is None
            or bar.bar_open_at - previous_full_open != timedelta(days=1)
        ):
            prior_volumes.clear()
        baseline = tuple(prior_volumes)
        if len(baseline) < mode.volume_z_min_observations:
            volume_z = None
            volume_status = "cold" if not baseline else "warming"
        else:
            mean = statistics.fmean(baseline)
            std = statistics.pstdev(baseline)
            volume_z = 0.0 if std <= 1e-12 else (bar.quote_volume - mean) / std
            volume_status = "constant_baseline" if std <= 1e-12 else "warm"
        values[bar.bar_open_at] = {
            "return_24h": _bar_return(by_open, bar, days=1),
            "return_72h": _bar_return(by_open, bar, days=3),
            "return_7d": _bar_return(by_open, bar, days=7),
            "volume_zscore_24h": volume_z,
            "volume_baseline_status": volume_status,
            "volume_baseline_count": len(baseline),
            "rsi": rsi_values.get(bar.bar_open_at),
        }
        prior_volumes.append(bar.quote_volume)
        previous_full_open = bar.bar_open_at
    return values


def _segmented_rsi(bars: Sequence[ReplayBar]) -> dict[datetime, float | None]:
    values = {bar.bar_open_at: None for bar in bars}
    segment: list[ReplayBar] = []

    def finish() -> None:
        if not segment:
            return
        close = pd.Series(
            [bar.close for bar in segment],
            index=pd.DatetimeIndex([bar.bar_open_at for bar in segment]),
            dtype=float,
        )
        calculated = wilder_rsi(close, config.RSI_PERIOD)
        for opened, value in calculated.items():
            values[opened.to_pydatetime()] = _optional_float(value)

    for bar in bars:
        contiguous = (
            segment
            and bar.full_daily_bar
            and bar.bar_open_at - segment[-1].bar_open_at == timedelta(days=1)
        )
        if not bar.full_daily_bar or segment and not contiguous:
            finish()
            segment = []
        if bar.full_daily_bar:
            segment.append(bar)
    finish()
    return values


def _benchmark_return_maps(
    dataset: ReplayDataset,
) -> dict[str, dict[datetime, float | None]]:
    result: dict[str, dict[datetime, float | None]] = {"BTC": {}, "ETH": {}}
    for benchmark in result:
        symbol = f"{benchmark}USDT"
        series = next((item for item in dataset.series if item.symbol == symbol), None)
        if series is None:
            continue
        analytics = _series_analytics(series, dataset.mode)
        result[benchmark] = {
            opened: _optional_float(values.get("return_24h"))
            for opened, values in analytics.items()
        }
    return result


def _btc_market_regime(dataset: ReplayDataset) -> dict[datetime, str | None]:
    btc = next((item for item in dataset.series if item.symbol == "BTCUSDT"), None)
    if btc is None:
        return {}
    values = {bar.bar_open_at: None for bar in btc.bars}
    segment: list[ReplayBar] = []

    def finish() -> None:
        if not segment:
            return
        values.update(_market_regime_segment(segment))

    for bar in btc.bars:
        contiguous = (
            segment
            and bar.full_daily_bar
            and bar.bar_open_at - segment[-1].bar_open_at == timedelta(days=1)
        )
        if not bar.full_daily_bar or segment and not contiguous:
            finish()
            segment = []
        if bar.full_daily_bar:
            segment.append(bar)
    finish()
    return values


def _market_regime_segment(bars: Sequence[ReplayBar]) -> dict[datetime, str | None]:
    close = pd.Series(
        [bar.close for bar in bars],
        index=pd.DatetimeIndex([bar.bar_open_at for bar in bars]),
        dtype=float,
    )
    short = close.rolling(config.REGIME_SHORT_MA).mean()
    long = close.rolling(config.REGIME_LONG_MA).mean()
    slope = long - long.shift(config.REGIME_SLOPE_LOOKBACK)
    values: dict[datetime, str | None] = {}
    for opened in close.index:
        price = close.loc[opened]
        short_value = short.loc[opened]
        long_value = long.loc[opened]
        slope_value = slope.loc[opened]
        if any(pd.isna(value) for value in (short_value, long_value, slope_value)):
            values[opened.to_pydatetime()] = None
        elif price > long_value and short_value > long_value and slope_value >= 0:
            values[opened.to_pydatetime()] = "BULL"
        elif price <= long_value and short_value <= long_value and slope_value <= 0:
            values[opened.to_pydatetime()] = "BEAR"
        else:
            values[opened.to_pydatetime()] = "CHOP"
    return values


def _partition_ranges(
    partitions: Mapping[str, Sequence[datetime | str]] | None,
) -> tuple[tuple[str, datetime, datetime], ...]:
    if not partitions:
        return ()
    if len(partitions) > MAX_PARTITIONS:
        raise ReplayDataError("research_partition_bound_exceeded")
    ranges: list[tuple[str, datetime, datetime]] = []
    for raw_name, boundary in partitions.items():
        name = str(raw_name or "").strip().casefold()
        if name == "final_test":
            raise ReplayDataError("final_test_evaluation_forbidden")
        if name not in ALLOWED_RESEARCH_PARTITIONS:
            raise ReplayDataError(f"research_partition_invalid:{name or 'missing'}")
        if (
            not isinstance(boundary, Sequence)
            or isinstance(boundary, (str, bytes))
            or len(boundary) != 2
        ):
            raise ReplayDataError(f"research_partition_boundary_invalid:{name}")
        start = _aware_utc(boundary[0], field=f"{name}:start")
        end = _aware_utc(boundary[1], field=f"{name}:end")
        if start >= end:
            raise ReplayDataError(f"research_partition_order_invalid:{name}")
        ranges.append((name, start, end))
    ranges.sort(key=lambda item: item[1])
    for previous, current in zip(ranges, ranges[1:]):
        if previous[2] > current[1]:
            raise ReplayDataError("research_partitions_overlap")
    return tuple(ranges)


def _partition_for(
    observed_at: datetime,
    ranges: Sequence[tuple[str, datetime, datetime]],
) -> str | None:
    return next(
        (name for name, start, end in ranges if start <= observed_at < end),
        None,
    )


def _bar_return(
    by_open: Mapping[datetime, ReplayBar],
    bar: ReplayBar,
    *,
    days: int,
) -> float | None:
    prior = by_open.get(bar.bar_open_at - timedelta(days=days))
    window = [
        by_open.get(bar.bar_open_at - timedelta(days=offset))
        for offset in range(days + 1)
    ]
    if (
        prior is None
        or prior.close <= 0
        or not all(value is not None and value.full_daily_bar for value in window)
    ):
        return None
    return (bar.close / prior.close - 1.0) * 100.0


def _relative_return(value: Any, benchmark: Any) -> float | None:
    left = _optional_float(value)
    right = _optional_float(benchmark)
    return None if left is None or right is None else left - right


def _complete_daily_window(values: Sequence[ReplayBar], window: int) -> bool:
    if len(values) != window:
        return False
    return all(value.full_daily_bar for value in values) and all(
        current.bar_open_at - previous.bar_open_at == timedelta(days=1)
        for previous, current in zip(values, list(values)[1:])
    )


def _combined_baseline_status(*, volume_status: str, membership_status: str) -> str:
    if volume_status == "partial_bar":
        return "partial_bar"
    if membership_status == "ready" and volume_status in {"warm", "constant_baseline"}:
        return "warm"
    if membership_status == "warming" and volume_status == "cold":
        return "cold"
    return "warming"


def _strict_integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReplayDataError(f"integer_field_invalid:{field}")
    if value < 0:
        raise ReplayDataError(f"integer_field_invalid:{field}")
    return value


def _finite_number(
    value: Any,
    field: str,
    *,
    positive: bool = False,
    minimum: float | None = None,
) -> float:
    if isinstance(value, bool):
        raise ReplayDataError(f"numeric_field_invalid:{field}")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ReplayDataError(f"numeric_field_invalid:{field}") from exc
    if not math.isfinite(number):
        raise ReplayDataError(f"numeric_field_invalid:{field}")
    if positive and number <= 0:
        raise ReplayDataError(f"numeric_field_invalid:{field}")
    if minimum is not None and number < minimum:
        raise ReplayDataError(f"numeric_field_invalid:{field}")
    return number


def _optional_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _aware_utc(value: Any, *, field: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        text = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ReplayDataError(f"timestamp_invalid:{field}") from exc
    else:
        raise ReplayDataError(f"timestamp_invalid:{field}")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReplayDataError(f"timestamp_not_aware:{field}")
    return parsed.astimezone(timezone.utc)


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ReplayDataError(f"positive_integer_invalid:{field}")
    return value


def _canonical_asset_id(symbol: str) -> str:
    base = symbol.removesuffix("USDT")
    return {
        "BTC": "bitcoin",
        "ETH": "ethereum",
    }.get(base, f"binance-usdt:{base.casefold()}")


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = (
    "CATALOG_SCHEMA_ID",
    "CATALOG_SCHEMA_VERSION",
    "DATASET_SCHEMA_ID",
    "DATASET_SCHEMA_VERSION",
    "OBSERVATION_SCHEMA_ID",
    "OBSERVATION_SCHEMA_VERSION",
    "REPLAY_DATA_MODE_CONFIGS",
    "RESIDUAL_SURVIVORSHIP_DISCLOSURE",
    "ReplayBar",
    "ReplayDataError",
    "ReplayDataModeConfig",
    "ReplayDataset",
    "ReplaySeries",
    "build_point_in_time_volume_membership",
    "build_replay_catalog",
    "iter_point_in_time_observations",
    "load_binance_cache_dataset",
    "load_fixture_dataset",
    "replay_data_mode_config",
)
