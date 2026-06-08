"""Pure market-state feature helpers.

These functions are deliberately side-effect free: no network, storage, logging,
or config mutation. They are intended to shadow the existing RSI trigger with
auditable market-state context before any live routing changes are considered.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Mapping

import numpy as np
import pandas as pd


def _finite(value: object) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _clean_series(values: pd.Series) -> pd.Series:
    s = pd.Series(values, dtype="float64").replace([np.inf, -np.inf], np.nan)
    return s.dropna()


def _latest_finite(values: pd.Series, default: float = 0.0) -> float:
    s = pd.Series(values, dtype="float64").replace([np.inf, -np.inf], np.nan).dropna()
    if s.empty:
        return float(default)
    return float(s.iloc[-1])


def _log_returns(close: pd.Series) -> pd.Series:
    prices = _clean_series(close)
    prices = prices[prices > 0]
    if len(prices) < 2:
        return pd.Series(dtype="float64")
    returns = np.log(prices / prices.shift(1))
    return returns.replace([np.inf, -np.inf], np.nan).dropna()


def realized_vol_series(
    close: pd.Series,
    window: int = 20,
    annualization: int = 365,
) -> pd.Series:
    """Rolling annualized realized volatility from log returns."""
    returns = _log_returns(close)
    if window <= 0 or returns.empty:
        return pd.Series(dtype="float64")
    return returns.rolling(window, min_periods=window).std(ddof=0) * math.sqrt(annualization)


def realized_vol(
    close: pd.Series,
    window: int = 20,
    annualization: int = 365,
) -> float:
    """Latest rolling realized volatility; returns 0.0 when unavailable."""
    return _latest_finite(realized_vol_series(close, window, annualization), default=0.0)


def _percentile_of_last(window_values: pd.Series) -> float:
    values = pd.Series(window_values, dtype="float64").replace([np.inf, -np.inf], np.nan).dropna()
    if values.empty:
        return np.nan
    current = float(values.iloc[-1])
    less = float((values < current).sum())
    equal = float((values == current).sum())
    return (less + 0.5 * equal) / float(len(values))


def trailing_percentile_series(series: pd.Series, window: int = 252) -> pd.Series:
    """Rolling percentile rank of the current value using only trailing data."""
    s = pd.Series(series, dtype="float64").replace([np.inf, -np.inf], np.nan)
    if window <= 0:
        return pd.Series(index=s.index, dtype="float64")
    return s.rolling(window, min_periods=window).apply(_percentile_of_last, raw=False)


def trailing_percentile(series: pd.Series, window: int = 252) -> float:
    """Latest trailing percentile rank; returns 0.5 when unavailable."""
    return _latest_finite(trailing_percentile_series(series, window), default=0.5)


def volatility_state(rv_20: float, rv_60: float, rv_pctile_252: float) -> str:
    if not all(_finite(v) for v in (rv_20, rv_60, rv_pctile_252)):
        return "unknown"
    rv_20 = max(0.0, float(rv_20))
    rv_60 = max(0.0, float(rv_60))
    rv_pctile_252 = min(1.0, max(0.0, float(rv_pctile_252)))
    if rv_20 == 0.0 and rv_60 == 0.0:
        ratio = 1.0
    elif rv_60 <= 0:
        ratio = float("inf")
    else:
        ratio = rv_20 / rv_60

    if rv_pctile_252 >= 0.90 and ratio >= 1.25:
        return "crisis"
    if rv_pctile_252 >= 0.75 and ratio >= 1.10:
        return "high_expanding"
    if rv_pctile_252 >= 0.70:
        return "high"
    if rv_pctile_252 <= 0.25 and ratio <= 0.90:
        return "low_compressed"
    return "normal"


def pct_return_series(close: pd.Series, window: int) -> pd.Series:
    prices = pd.Series(close, dtype="float64").replace([np.inf, -np.inf], np.nan)
    if window <= 0:
        return pd.Series(index=prices.index, dtype="float64")
    out = prices / prices.shift(window) - 1.0
    return out.replace([np.inf, -np.inf], np.nan)


def pct_return(close: pd.Series, window: int) -> float:
    return _latest_finite(pct_return_series(close, window), default=0.0)


def cross_sectional_ranks(values: Mapping[str, float]) -> dict[str, float]:
    """Percentile rank 0..1. Higher input value means stronger rank.

    Missing/non-finite values receive neutral rank 0.5 so downstream snapshots
    stay JSON-friendly and do not crash when one coin has short history.
    """
    ranks = {str(k): 0.5 for k in values}
    finite_items = [(str(k), float(v)) for k, v in values.items() if _finite(v)]
    n = len(finite_items)
    if n == 0:
        return ranks
    if n == 1:
        ranks[finite_items[0][0]] = 0.5
        return ranks

    by_value: dict[float, list[str]] = defaultdict(list)
    for key, value in finite_items:
        by_value[value].append(key)

    ordinal = 0
    for value in sorted(by_value):
        keys = by_value[value]
        avg_ordinal = ordinal + (len(keys) - 1) / 2.0
        rank = avg_ordinal / (n - 1)
        for key in keys:
            ranks[key] = float(rank)
        ordinal += len(keys)
    return ranks


def _aligned_return_frame(series_by_name: Mapping[str, pd.Series], window: int) -> pd.DataFrame:
    returns: dict[str, pd.Series] = {}
    for name, series in series_by_name.items():
        returns[name] = pd.Series(series, dtype="float64").pct_change(fill_method=None)
    frame = pd.DataFrame(returns).replace([np.inf, -np.inf], np.nan).dropna()
    if window > 0:
        frame = frame.tail(window)
    return frame


def rolling_beta(asset: pd.Series, benchmark: pd.Series, window: int = 60) -> float:
    frame = _aligned_return_frame({"asset": asset, "benchmark": benchmark}, window)
    if len(frame) < max(5, min(window, 5)):
        return 0.0
    x = frame["benchmark"].to_numpy(dtype=float)
    y = frame["asset"].to_numpy(dtype=float)
    if np.var(x) <= 0:
        return 0.0
    design = np.column_stack([np.ones(len(x)), x])
    try:
        coef, *_ = np.linalg.lstsq(design, y, rcond=None)
    except np.linalg.LinAlgError:
        return 0.0
    return float(coef[1])


def rolling_multi_beta(
    asset: pd.Series,
    factors: Mapping[str, pd.Series],
    window: int = 60,
) -> dict[str, float]:
    names = list(factors.keys())
    out = {f"beta_{name}": 0.0 for name in names}
    out["r2"] = 0.0
    if not names:
        return out

    frame = _aligned_return_frame({"asset": asset, **dict(factors)}, window)
    if len(frame) < max(5, len(names) + 2):
        return out

    y = frame["asset"].to_numpy(dtype=float)
    x = frame[names].to_numpy(dtype=float)
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        return out
    design = np.column_stack([np.ones(len(x)), x])
    try:
        coef, *_ = np.linalg.lstsq(design, y, rcond=None)
    except np.linalg.LinAlgError:
        return out

    fitted = design @ coef
    ss_res = float(np.sum((y - fitted) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    for name, beta in zip(names, coef[1:]):
        out[f"beta_{name}"] = float(beta)
    out["r2"] = 0.0 if ss_tot <= 0 else float(max(0.0, min(1.0, 1.0 - ss_res / ss_tot)))
    return out


def volume_z_score(volume: pd.Series, window: int = 90) -> float:
    vols = _clean_series(volume)
    if window <= 1 or len(vols) < window:
        return 0.0
    sample = vols.tail(window)
    std = float(sample.std(ddof=0))
    if std <= 0:
        return 0.0
    return float((sample.iloc[-1] - sample.mean()) / std)


def dollar_volume_20(
    close: pd.Series,
    volume: pd.Series,
    volume_is_usd: bool,
) -> float:
    if volume_is_usd:
        vols = _clean_series(volume)
        return float(vols.tail(20).mean()) if not vols.empty else 0.0
    frame = pd.DataFrame({
        "close": pd.Series(close, dtype="float64"),
        "volume": pd.Series(volume, dtype="float64"),
    }).replace([np.inf, -np.inf], np.nan).dropna()
    if frame.empty:
        return 0.0
    dollar = frame["close"] * frame["volume"]
    return float(dollar.tail(20).mean())


def turnover_20(dollar_volume: pd.Series, market_cap: pd.Series | None) -> float:
    if market_cap is None:
        return 0.0
    frame = pd.DataFrame({
        "dollar_volume": pd.Series(dollar_volume, dtype="float64"),
        "market_cap": pd.Series(market_cap, dtype="float64"),
    }).replace([np.inf, -np.inf], np.nan).dropna()
    frame = frame[frame["market_cap"] > 0]
    if frame.empty:
        return 0.0
    turnover = frame["dollar_volume"] / frame["market_cap"]
    return float(turnover.tail(20).mean())


def volume_price_state(ret_1d: float, volume_z: float) -> str:
    if not _finite(ret_1d) or not _finite(volume_z):
        return "unknown"
    ret_1d = float(ret_1d)
    volume_z = float(volume_z)
    high_volume = volume_z >= 1.5
    if abs(ret_1d) < 0.005:
        return "spike_flat_price" if high_volume else "quiet"
    if ret_1d > 0:
        return "up_high_volume" if high_volume else "up_normal_volume"
    return "down_high_volume" if high_volume else "down_normal_volume"


def _asof_slice(series: pd.Series, asof: pd.Timestamp | None) -> pd.Series:
    s = pd.Series(series, dtype="float64").replace([np.inf, -np.inf], np.nan).dropna()
    if asof is None or s.empty:
        return s
    if not isinstance(s.index, pd.DatetimeIndex):
        return s
    ts = pd.Timestamp(asof)
    if ts.tzinfo is not None and getattr(s.index, "tz", None) is None:
        ts = ts.tz_convert(None)
    if ts.tzinfo is None and getattr(s.index, "tz", None) is not None:
        ts = ts.tz_localize("UTC")
    return s.loc[s.index <= ts]


def _pct_above_ma(
    closes_by_coin: Mapping[str, pd.Series],
    ma_window: int,
    *,
    asof: pd.Timestamp | None,
    offset: int = 0,
) -> float | None:
    values: list[bool] = []
    for close in closes_by_coin.values():
        s = _asof_slice(close, asof)
        if offset > 0:
            s = s.iloc[:-offset] if len(s) > offset else pd.Series(dtype="float64")
        if len(s) < ma_window:
            continue
        ma = float(s.tail(ma_window).mean())
        values.append(float(s.iloc[-1]) > ma)
    if not values:
        return None
    return float(sum(values) / len(values))


def _breadth_state(
    *,
    median_rsi: float | None,
    pct_rsi_lt_30: float | None,
    pct_rsi_lt_40: float | None,
    pct_rsi_gt_60: float | None,
    pct_above_50dma: float | None,
    pct_above_200dma: float | None,
    pct_above_50dma_chg_5d: float | None,
    pct_above_200dma_chg_5d: float | None,
) -> str:
    if median_rsi is None:
        return "unknown"
    pct_rsi_lt_30 = pct_rsi_lt_30 or 0.0
    pct_rsi_lt_40 = pct_rsi_lt_40 or 0.0
    pct_rsi_gt_60 = pct_rsi_gt_60 or 0.0
    pct_above_50dma = pct_above_50dma if pct_above_50dma is not None else 0.0
    pct_above_200dma = pct_above_200dma if pct_above_200dma is not None else 0.0
    chg_50 = pct_above_50dma_chg_5d or 0.0
    chg_200 = pct_above_200dma_chg_5d or 0.0

    if pct_above_50dma <= 0.25 and (chg_50 <= -0.10 or pct_rsi_lt_40 >= 0.55):
        return "breadth_collapse"
    if pct_rsi_lt_30 >= 0.25 or pct_rsi_lt_40 >= 0.45:
        if chg_50 > 0.05 or chg_200 > 0.03 or median_rsi > 40:
            return "washout_recovery"
        return "washout"
    if pct_above_50dma >= 0.65 and pct_above_200dma >= 0.50 and pct_rsi_gt_60 >= 0.25:
        return "risk_on_broad"
    if pct_rsi_gt_60 >= 0.25 and pct_above_50dma < 0.50:
        return "risk_on_narrow"
    return "neutral"


def breadth_snapshot(
    closes_by_coin: Mapping[str, pd.Series],
    rsi_by_coin: Mapping[str, pd.Series],
    asof: pd.Timestamp | None = None,
) -> dict:
    """Cross-sectional market breadth at an as-of time."""
    rsi_values: list[float] = []
    for key in set(closes_by_coin) | set(rsi_by_coin):
        rsi = _asof_slice(rsi_by_coin.get(key, pd.Series(dtype="float64")), asof)
        if rsi.empty:
            continue
        rsi_values.append(float(rsi.iloc[-1]))

    median_rsi = float(np.median(rsi_values)) if rsi_values else None
    n_rsi = len(rsi_values)
    pct_rsi_lt_30 = float(sum(v < 30 for v in rsi_values) / n_rsi) if n_rsi else None
    pct_rsi_lt_40 = float(sum(v < 40 for v in rsi_values) / n_rsi) if n_rsi else None
    pct_rsi_gt_60 = float(sum(v > 60 for v in rsi_values) / n_rsi) if n_rsi else None
    pct_rsi_gt_70 = float(sum(v > 70 for v in rsi_values) / n_rsi) if n_rsi else None

    pct_50 = _pct_above_ma(closes_by_coin, 50, asof=asof)
    pct_200 = _pct_above_ma(closes_by_coin, 200, asof=asof)
    pct_50_prev = _pct_above_ma(closes_by_coin, 50, asof=asof, offset=5)
    pct_200_prev = _pct_above_ma(closes_by_coin, 200, asof=asof, offset=5)
    pct_50_chg = (pct_50 - pct_50_prev) if pct_50 is not None and pct_50_prev is not None else None
    pct_200_chg = (pct_200 - pct_200_prev) if pct_200 is not None and pct_200_prev is not None else None

    state = _breadth_state(
        median_rsi=median_rsi,
        pct_rsi_lt_30=pct_rsi_lt_30,
        pct_rsi_lt_40=pct_rsi_lt_40,
        pct_rsi_gt_60=pct_rsi_gt_60,
        pct_above_50dma=pct_50,
        pct_above_200dma=pct_200,
        pct_above_50dma_chg_5d=pct_50_chg,
        pct_above_200dma_chg_5d=pct_200_chg,
    )

    return {
        "median_rsi": median_rsi,
        "pct_rsi_lt_30": pct_rsi_lt_30,
        "pct_rsi_lt_40": pct_rsi_lt_40,
        "pct_rsi_gt_60": pct_rsi_gt_60,
        "pct_rsi_gt_70": pct_rsi_gt_70,
        "pct_above_50dma": pct_50,
        "pct_above_200dma": pct_200,
        "pct_above_50dma_chg_5d": pct_50_chg,
        "pct_above_200dma_chg_5d": pct_200_chg,
        "state": state,
    }
