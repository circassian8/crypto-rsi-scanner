from __future__ import annotations

import numpy as np
import pandas as pd

from .signal_registry import (
    edge_conviction_prior,
    market_alignment,
    market_conviction_adjustment,
    regime_note,
    setup_for,
    setup_has_edge,
)


def _wilder_rma(values: np.ndarray, period: int) -> np.ndarray:
    """Wilder's running moving average with a simple-mean seed — the exact
    smoothing TradingView/Wilder use, correct on any series length (not just
    long ones). `values[0]` is expected to be NaN (from .diff())."""
    out = np.full_like(values, np.nan, dtype=float)
    if len(values) < period + 1:
        return out
    seed = np.mean(values[1 : period + 1])  # first `period` deltas
    out[period] = seed
    for i in range(period + 1, len(values)):
        out[i] = (out[i - 1] * (period - 1) + values[i]) / period
    return out


def wilder_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI with exact SMA seeding. Matches TradingView on any length."""
    delta = close.diff()
    gain = delta.clip(lower=0.0).to_numpy(dtype=float)
    loss = (-delta.clip(upper=0.0)).to_numpy(dtype=float)

    avg_gain = _wilder_rma(gain, period)
    avg_loss = _wilder_rma(loss, period)

    with np.errstate(divide="ignore", invalid="ignore"):
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))

    # avg_loss == 0 -> pure uptrend -> RSI 100; avg_gain == 0 -> RSI 0
    rsi = np.where(avg_loss == 0.0, 100.0, rsi)
    rsi = np.where(avg_gain == 0.0, 0.0, rsi)
    # keep NaN where the average isn't defined yet (warm-up period)
    rsi = np.where(np.isnan(avg_gain) | np.isnan(avg_loss), np.nan, rsi)
    return pd.Series(rsi, index=close.index)


def annualized_vol(close: pd.Series) -> float:
    rets = close.pct_change().dropna()
    if len(rets) < 10:
        return 0.0
    return float(rets.std() * np.sqrt(365))


def rsi_z_score(rsi_series: pd.Series, window: int = 90) -> float:
    if len(rsi_series) < window:
        return 0.0
    baseline = rsi_series.iloc[-window:]
    std = baseline.std()
    if std < 1e-9:
        return 0.0
    return float((rsi_series.iloc[-1] - baseline.mean()) / std)


def rsi_rate_of_change(rsi_series: pd.Series, window: int = 3) -> float:
    if len(rsi_series) < window + 1:
        return 0.0
    return float(rsi_series.iloc[-1] - rsi_series.iloc[-(window + 1)])


def adaptive_thresholds(
    rsi_series: pd.Series, ob_pct: float = 95, os_pct: float = 5
) -> tuple[float, float]:
    clean = rsi_series.dropna()
    if len(clean) < 30:
        return 70.0, 30.0
    return (
        float(np.percentile(clean, ob_pct)),
        float(np.percentile(clean, os_pct)),
    )


def volume_ratio(volumes: pd.Series, window: int = 20) -> float:
    if len(volumes) < window + 1:
        return 1.0
    avg = volumes.iloc[-(window + 1) : -1].mean()
    if avg < 1e-9:
        return 1.0
    return float(volumes.iloc[-1] / avg)


def btc_correlation(
    coin_closes: pd.Series, btc_closes: pd.Series, window: int = 30
) -> float:
    combined = pd.DataFrame({"coin": coin_closes, "btc": btc_closes}).dropna()
    if len(combined) < window:
        return 0.0
    recent = combined.iloc[-window:]
    coin_rets = recent["coin"].pct_change().dropna()
    btc_rets = recent["btc"].pct_change().dropna()
    if len(coin_rets) < 10:
        return 0.0
    corr = coin_rets.corr(btc_rets)
    return 0.0 if np.isnan(corr) else float(corr)


def trend_regime(
    close: pd.Series,
    short: int = 50,
    long: int = 200,
    slope_lookback: int = 20,
) -> str:
    """Classify the macro trend from moving-average structure (close-only):
    UPTREND, DOWNTREND, RANGE, or UNKNOWN (insufficient history for the long MA).
    UPTREND = price above a non-falling long MA with short MA above long MA;
    DOWNTREND = the mirror; everything ambiguous falls to RANGE."""
    n = len(close)
    if n < long:
        return "UNKNOWN"
    c = close.astype(float)
    sma_short = c.rolling(short).mean().iloc[-1]
    sma_long_series = c.rolling(long).mean()
    sma_long = sma_long_series.iloc[-1]
    if np.isnan(sma_short) or np.isnan(sma_long):
        return "UNKNOWN"

    price = c.iloc[-1]
    slope = 0.0
    if n > long + slope_lookback:
        prev = sma_long_series.iloc[-1 - slope_lookback]
        if not np.isnan(prev):
            slope = sma_long - prev

    above_long = price > sma_long
    aligned_up = sma_short > sma_long

    if above_long and aligned_up and slope >= 0:
        return "UPTREND"
    if (not above_long) and (not aligned_up) and slope <= 0:
        return "DOWNTREND"
    return "RANGE"


def decide_flag(
    cur_rsi: float,
    delta: float,
    eff_ob: float,
    eff_os: float,
    margin: float,
    min_delta: float,
) -> str:
    """Classify the current RSI: crossed (OB/OS), approaching (PRE_*), or "".
    PRE_* requires being within `margin` of the threshold AND moving toward it
    by at least `min_delta` over the delta window."""
    if cur_rsi >= eff_ob:
        return "OB"
    if cur_rsi <= eff_os:
        return "OS"
    if (eff_ob - margin) <= cur_rsi < eff_ob and delta >= min_delta:
        return "PRE_OB"
    if eff_os < cur_rsi <= (eff_os + margin) and delta <= -min_delta:
        return "PRE_OS"
    return ""


def conviction_score(sig: dict) -> int:
    """Composite 0-100 conviction for a flagged signal. Higher = more reasons
    to pay attention.

    When setup/market metadata is present, the baseline comes from the signal
    registry's measured-edge prior; severity and confluence then move around
    that baseline. Without setup metadata, this falls back to the legacy
    severity-first heuristic so older tests/callers keep working."""
    flag = sig.get("flag")
    if not flag:
        return 0

    severity = sig.get("severity", "WATCH")
    heuristic = {"APPROACHING": 15, "WATCH": 30, "ALERT": 55, "EXTREME": 75}.get(
        severity, 30
    )
    prior = edge_conviction_prior(sig.get("setup_type"), sig.get("market_aligned", "neutral"))
    score = heuristic if prior is None else round(0.45 * heuristic + 0.55 * prior)

    rsi_4h = sig.get("rsi_4h")
    rsi_w = sig.get("rsi_weekly")
    z = sig.get("rsi_z") or 0.0
    vol = sig.get("volume_ratio") or 1.0
    div = sig.get("divergence")

    if flag in ("OB", "PRE_OB"):
        if rsi_4h is not None and rsi_4h >= 60:
            score += 8
        if rsi_w is not None and rsi_w >= 60:
            score += 10
        if div == "bearish":
            score += 10
    else:  # OS
        if rsi_4h is not None and rsi_4h <= 40:
            score += 8
        if rsi_w is not None and rsi_w <= 40:
            score += 10
        if div == "bullish":
            score += 10

    if vol >= 1.5:
        score += 7
    if abs(z) >= 2.0:
        score += 5

    if severity == "APPROACHING":
        score = min(score, 35)
    if severity == "EXTREME":
        score = max(score, 65)

    return int(max(0, min(100, score)))


def conviction_adjustment(
    base: int,
    hit_rate: float | None,
    n_samples: int,
    min_samples: int = 8,
    max_swing: int = 15,
) -> int:
    """Empirical nudge to the base conviction from this signal-type's own track
    record. Returns an adjusted 0-100 score.

    - hit_rate is the historical favorable fraction (0..1) for this (flag,
      regime) bucket at the primary horizon; None/too-few-samples => no change.
    - The swing is centered at a 50% hit rate and capped at +/- max_swing, and
      it's *scaled by sample size* up to a confidence ceiling, so a 5-sample
      bucket barely moves while a 40-sample bucket gets the full adjustment.

    This is what lets the score learn which setups actually work on *your*
    universe without letting a small, noisy sample whipsaw it."""
    if hit_rate is None or n_samples < min_samples:
        return base
    # confidence ramps from min_samples up to 4x min_samples
    confidence = min(1.0, (n_samples - min_samples) / (3 * min_samples) + 0.34)
    raw = (hit_rate - 0.5) * 2.0  # -1..+1
    delta = int(round(raw * max_swing * confidence))
    return int(max(0, min(100, base + delta)))


def detect_divergence(
    close: pd.Series, rsi: pd.Series, lookback: int = 30, order: int = 5
) -> str | None:
    if len(close) < lookback or len(rsi) < lookback:
        return None

    p = close.iloc[-lookback:].values.astype(float)
    r = rsi.iloc[-lookback:].values.astype(float)

    highs: list[int] = []
    lows: list[int] = []
    for i in range(order, len(p) - order):
        window = p[i - order : i + order + 1]
        if p[i] == np.max(window):
            if not highs or i - highs[-1] >= order:
                highs.append(i)
        if p[i] == np.min(window):
            if not lows or i - lows[-1] >= order:
                lows.append(i)

    if len(highs) >= 2:
        i1, i2 = highs[-2], highs[-1]
        if p[i2] > p[i1] and r[i2] < r[i1]:
            return "bearish"

    if len(lows) >= 2:
        i1, i2 = lows[-2], lows[-1]
        if p[i2] < p[i1] and r[i2] > r[i1]:
            return "bullish"

    return None
