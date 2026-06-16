from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import config
from .client import CoinGeckoClient
from .indicators import (
    adaptive_thresholds,
    annualized_vol,
    btc_correlation,
    conviction_adjustment,
    conviction_score,
    decide_flag,
    detect_divergence,
    rsi_rate_of_change,
    rsi_z_score,
    trend_regime,
    volume_ratio,
    wilder_rsi,
)
from .signal_registry import market_alignment, regime_note, setup_for
from .state_features import (
    breadth_snapshot,
    cross_sectional_ranks,
    dollar_volume_20,
    falling_knife_score,
    liquidity_bucket,
    pct_return,
    rank_bucket,
    realized_vol,
    realized_vol_series,
    rolling_beta,
    rolling_multi_beta,
    trailing_percentile,
    volatility_state,
    volume_price_state,
    volume_z_score,
)
from .notifications import notify_all
from .storage import Storage
from .universe import (
    candidate_count,
    filter_markets_with_audit,
    format_audit,
    format_exclusions,
    write_audit,
)
from . import outcomes
from . import telegram
from . import heartbeat
from . import macro
from . import paper
from . import event_fade
from . import event_cache
from . import event_discovery
from . import event_provider_status
from . import event_price_history
from . import event_validation
from .event_models import EventDiscoveryResult
from .event_providers.binance_announcements import BinanceAnnouncementProvider

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_chart(
    data: dict, resample: str | None = None
) -> tuple[pd.Series, pd.Series]:
    prices = data.get("prices", [])
    volumes = data.get("total_volumes", [])
    if not prices:
        return pd.Series(dtype=float), pd.Series(dtype=float)

    pdf = pd.DataFrame(prices, columns=["ts", "price"])
    pdf["dt"] = pd.to_datetime(pdf["ts"], unit="ms", utc=True)
    pdf = pdf.set_index("dt")

    vdf = pd.DataFrame(volumes, columns=["ts", "volume"]) if volumes else pd.DataFrame(columns=["ts", "volume"])
    if not vdf.empty:
        vdf["dt"] = pd.to_datetime(vdf["ts"], unit="ms", utc=True)
        vdf = vdf.set_index("dt")

    if resample:
        price_s = pdf["price"].resample(resample).last().dropna()
        vol_s = vdf["volume"].resample(resample).sum().dropna() if not vdf.empty else pd.Series(dtype=float)
    else:
        pdf["date"] = pdf.index.date
        price_s = pdf.groupby("date")["price"].last()
        price_s.index = pd.to_datetime(price_s.index, utc=True)
        if not vdf.empty:
            vdf["date"] = vdf.index.date
            vol_s = vdf.groupby("date")["volume"].sum()
            vol_s.index = pd.to_datetime(vol_s.index, utc=True)
        else:
            vol_s = pd.Series(dtype=float)

    return price_s, vol_s


def _severity(flag: str, rsi: float) -> str:
    if flag in ("PRE_OB", "PRE_OS"):
        return "APPROACHING"
    if flag not in ("OB", "OS"):
        return ""
    for threshold, level in config.SEVERITY_TIERS[flag]:
        if flag == "OB" and rsi >= threshold:
            return level
        if flag == "OS" and rsi <= threshold:
            return level
    return "WATCH"


def classify_tier(flag: str, severity: str, conviction: int,
                  market_aligned: str = "neutral") -> str:
    """INSTANT (loud, immediate) vs DIGEST (batched watch-list)."""
    if flag in ("PRE_OB", "PRE_OS"):
        return "DIGEST"
    # A setup with no edge in the current market regime shouldn't go loud —
    # hold it to the digest unless the move is an outright extreme.
    if market_aligned == "adverse" and severity != "EXTREME":
        return "DIGEST"
    if severity in config.INSTANT_SEVERITIES or conviction >= config.INSTANT_CONVICTION:
        return "INSTANT"
    return "DIGEST"


def _finite_float(value: object, default: float | None = None) -> float | None:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return v if np.isfinite(v) else default


def _rounded(value: object, ndigits: int = 4, default: float | None = None) -> float | None:
    v = _finite_float(value, default)
    return None if v is None else round(v, ndigits)


def _json_safe(value: object) -> object:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        v = float(value)
        return v if np.isfinite(v) else None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def _build_state_context(
    daily_parsed: dict[str, tuple[pd.Series, pd.Series]],
    coin_map: dict[str, dict],
    btc_closes: pd.Series | None,
    eth_closes: pd.Series | None,
) -> dict:
    """Build shadow market-state snapshots for scanner rows.

    The context is deliberately separate from signal decisions. Callers attach it
    after conviction/tier are already computed so it cannot change live routing.
    """
    closes_by_coin = {cid: cv[0] for cid, cv in daily_parsed.items() if not cv[0].empty}
    rsi_by_coin = {
        cid: wilder_rsi(closes, config.RSI_PERIOD).dropna()
        for cid, closes in closes_by_coin.items()
    }
    breadth = breadth_snapshot(closes_by_coin, rsi_by_coin)

    ret_30d = {cid: pct_return(closes, 30) for cid, closes in closes_by_coin.items()}
    ret_90d = {cid: pct_return(closes, 90) for cid, closes in closes_by_coin.items()}
    rank_30d = cross_sectional_ranks(ret_30d)
    rank_90d = cross_sectional_ranks(ret_90d)
    btc_ret_30d = pct_return(btc_closes, 30) if btc_closes is not None else 0.0
    btc_ret_90d = pct_return(btc_closes, 90) if btc_closes is not None else 0.0
    eth_ret_30d = pct_return(eth_closes, 30) if eth_closes is not None else 0.0
    eth_ret_90d = pct_return(eth_closes, 90) if eth_closes is not None else 0.0

    factors: dict[str, pd.Series] = {}
    if btc_closes is not None and not btc_closes.empty:
        factors["btc"] = btc_closes
    if eth_closes is not None and not eth_closes.empty:
        factors["eth"] = eth_closes

    per_coin: dict[str, dict] = {}
    for coin_id, (closes, volumes) in daily_parsed.items():
        if closes.empty:
            continue
        market = coin_map.get(coin_id, {})

        rv_20 = realized_vol(closes, 20)
        rv_60 = realized_vol(closes, 60)
        rv20_series = realized_vol_series(closes, 20)
        rv_count = len(rv20_series.dropna())
        pct_window = min(252, rv_count) if rv_count >= 20 else 252
        rv_pctile = trailing_percentile(rv20_series, pct_window)
        vol_state = volatility_state(rv_20, rv_60, rv_pctile)

        multi = rolling_multi_beta(closes, factors, 60)
        btc_beta_60 = (
            rolling_beta(closes, btc_closes, 60)
            if btc_closes is not None and not btc_closes.empty else 0.0
        )
        if "beta_btc" in multi:
            btc_beta_60 = multi["beta_btc"]
        eth_beta_60 = multi.get("beta_eth", 0.0)
        beta_r2_60 = multi.get("r2", 0.0)
        resid_30d = ret_30d.get(coin_id, 0.0) - btc_beta_60 * btc_ret_30d - eth_beta_60 * eth_ret_30d
        resid_90d = ret_90d.get(coin_id, 0.0) - btc_beta_60 * btc_ret_90d - eth_beta_60 * eth_ret_90d
        avg_rank = (rank_30d.get(coin_id, 0.5) + rank_90d.get(coin_id, 0.5)) / 2.0
        rs_bucket = rank_bucket(avg_rank)

        dollar_vol = dollar_volume_20(closes, volumes, volume_is_usd=True)
        if dollar_vol <= 0:
            dollar_vol = _finite_float(market.get("total_volume"), 0.0) or 0.0
        market_cap = _finite_float(market.get("market_cap"), 0.0) or 0.0
        turnover = dollar_vol / market_cap if market_cap > 0 else 0.0
        vol_z = volume_z_score(volumes, 90) if not volumes.empty else 0.0
        vp_state = volume_price_state(pct_return(closes, 1), vol_z)
        liq_bucket = liquidity_bucket(dollar_vol, turnover)

        regime = trend_regime(
            closes,
            config.REGIME_SHORT_MA,
            config.REGIME_LONG_MA,
            config.REGIME_SLOPE_LOOKBACK,
        )
        knife = falling_knife_score(
            vol_state=vol_state,
            breadth_state=str(breadth.get("state") or "unknown"),
            rs_bucket=rs_bucket,
            regime=regime,
            volume_state=vp_state,
            ret_30d=ret_30d.get(coin_id, 0.0),
            btc_beta_60=btc_beta_60,
            beta_r2_60=beta_r2_60,
        )

        state = {
            "version": 1,
            "volatility": {
                "rv_20": _rounded(rv_20),
                "rv_60": _rounded(rv_60),
                "rv_pctile_252": _rounded(rv_pctile),
                "state": vol_state,
            },
            "breadth": breadth,
            "relative_strength": {
                "ret_30d": _rounded(ret_30d.get(coin_id)),
                "ret_90d": _rounded(ret_90d.get(coin_id)),
                "ret_30d_ex_btc": _rounded(ret_30d.get(coin_id, 0.0) - btc_ret_30d),
                "ret_90d_ex_btc": _rounded(ret_90d.get(coin_id, 0.0) - btc_ret_90d),
                "resid_ret_30d": _rounded(resid_30d),
                "resid_ret_90d": _rounded(resid_90d),
                "rank_30d": _rounded(rank_30d.get(coin_id)),
                "rank_90d": _rounded(rank_90d.get(coin_id)),
                "bucket": rs_bucket,
            },
            "beta": {
                "btc_beta_60": _rounded(btc_beta_60),
                "eth_beta_60": _rounded(eth_beta_60),
                "r2_btc_eth_60": _rounded(beta_r2_60),
            },
            "liquidity": {
                "dollar_volume_20": _rounded(dollar_vol, 2),
                "turnover_20": _rounded(turnover, 6),
                "volume_z_90": _rounded(vol_z),
                "volume_price_state": vp_state,
                "bucket": liq_bucket,
            },
            "risk": {
                "falling_knife_score": knife,
            },
        }
        per_coin[coin_id] = {
            "state": state,
            "state_json": json.dumps(_json_safe(state), sort_keys=True, separators=(",", ":")),
            "vol_state": vol_state,
            "breadth_state": breadth.get("state") or "unknown",
            "rs_bucket": rs_bucket,
            "liquidity_bucket": liq_bucket,
            "falling_knife_score": knife,
        }

    return {"breadth": breadth, "per_coin": per_coin}


# ---------------------------------------------------------------------------
# Per-coin analysis
# ---------------------------------------------------------------------------

def _analyze_coin(
    closes: pd.Series,
    volumes: pd.Series,
    closes_4h: pd.Series | None,
    btc_closes: pd.Series | None,
    market_info: dict,
    market_regime: str = "UNKNOWN",
    state_context: dict | None = None,
) -> dict | None:
    sym = (market_info.get("symbol") or "").upper()
    coin_id = market_info.get("id", "")

    if len(closes) < config.RSI_PERIOD + config.RSI_Z_WINDOW // 2:
        return None
    if annualized_vol(closes) < config.MIN_ANNUAL_VOL:
        return None

    rsi_series = wilder_rsi(closes, config.RSI_PERIOD).dropna()
    if rsi_series.empty:
        return None
    cur_rsi = float(rsi_series.iloc[-1])

    # Weekly RSI (resample daily -> weekly)
    weekly_closes = closes.resample("W").last().dropna()
    weekly_rsi_s = wilder_rsi(weekly_closes, config.RSI_PERIOD).dropna()
    weekly_rsi = float(weekly_rsi_s.iloc[-1]) if not weekly_rsi_s.empty else None

    # 4H RSI
    rsi_4h = None
    if closes_4h is not None and len(closes_4h) >= config.RSI_PERIOD + 1:
        rsi_4h_s = wilder_rsi(closes_4h, config.RSI_PERIOD).dropna()
        if not rsi_4h_s.empty:
            rsi_4h = float(rsi_4h_s.iloc[-1])

    # Adaptive thresholds. Effective threshold = whichever triggers first, so a
    # coin that never reaches 70 still flags when it's extreme for *itself*.
    adapt_ob, adapt_os = adaptive_thresholds(
        rsi_series, config.ADAPTIVE_OB_PERCENTILE, config.ADAPTIVE_OS_PERCENTILE
    )
    eff_ob = min(config.RSI_OB, adapt_ob)
    eff_os = max(config.RSI_OS, adapt_os)

    z = rsi_z_score(rsi_series, config.RSI_Z_WINDOW)
    delta = rsi_rate_of_change(rsi_series, config.RSI_DELTA_WINDOW)
    vol_r = volume_ratio(volumes, config.VOLUME_AVG_WINDOW) if not volumes.empty else 1.0

    # Flag: crossed (OB/OS) > approaching (PRE_*, within margin AND moving in).
    flag = decide_flag(
        cur_rsi, delta, eff_ob, eff_os, config.APPROACH_MARGIN, config.APPROACH_MIN_DELTA
    )

    btc_corr = 0.0
    if btc_closes is not None and coin_id != "bitcoin":
        btc_corr = btc_correlation(closes, btc_closes, config.BTC_CORR_WINDOW)

    div = detect_divergence(
        closes, rsi_series, config.DIVERGENCE_LOOKBACK, config.DIVERGENCE_ORDER
    )

    regime = trend_regime(
        closes,
        config.REGIME_SHORT_MA,
        config.REGIME_LONG_MA,
        config.REGIME_SLOPE_LOOKBACK,
    )

    result = {
        "symbol": sym,
        "coin_id": coin_id,
        "name": market_info.get("name"),
        "rsi_daily": round(cur_rsi, 1),
        "rsi_4h": round(rsi_4h, 1) if rsi_4h is not None else None,
        "rsi_weekly": round(weekly_rsi, 1) if weekly_rsi is not None else None,
        "rsi_z": round(z, 2),
        "rsi_delta": round(delta, 1),
        "adapt_ob": round(adapt_ob, 1),
        "adapt_os": round(adapt_os, 1),
        "volume_ratio": round(vol_r, 2),
        "btc_corr": round(btc_corr, 2),
        "divergence": div,
        "regime": regime,
        "regime_note": regime_note(flag, regime),
        "price": market_info.get("current_price"),
        "mcap_rank": market_info.get("market_cap_rank"),
        "pct_24h": market_info.get("price_change_percentage_24h_in_currency"),
        "pct_7d": market_info.get("price_change_percentage_7d_in_currency"),
        "ath": market_info.get("ath"),
        "ath_pct": market_info.get("ath_change_percentage"),
        "sparkline": (market_info.get("sparkline_in_7d") or {}).get("price"),
        "flag": flag,
        "severity": _severity(flag, cur_rsi),
    }
    result["setup_type"], result["expected_dir"] = setup_for(flag, regime)
    result["market_regime"] = market_regime
    aligned = (
        market_alignment(result["setup_type"], market_regime)
        if config.MARKET_GATING_ENABLED else "neutral"
    )
    result["market_aligned"] = aligned

    result["conviction"] = conviction_score(result)
    result["tier"] = (
        classify_tier(flag, result["severity"], result["conviction"], aligned)
        if flag else ""
    )
    state_fields = (state_context or {}).get("per_coin", {}).get(coin_id)
    if state_fields:
        result.update(state_fields)
    return result


# ---------------------------------------------------------------------------
# Async scan
# ---------------------------------------------------------------------------

async def scan(top_n: int | None = None) -> tuple[pd.DataFrame, dict, dict]:
    n = top_n or config.TOP_N
    log.info(
        "Starting scan at %s",
        datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    )

    async with CoinGeckoClient() as client:
        fetch_n = candidate_count(n)
        markets = await client.get_top_markets(fetch_n)
        coins, excluded, audit = filter_markets_with_audit(markets, limit=n)
        log.info(
            "Scanning %d clean coins (requested top-%d; fetched %d candidates; excluded: %s)",
            len(coins), n, len(markets), format_exclusions(excluded),
        )
        if len(coins) < n:
            log.warning("Only %d clean coins available for requested top-%d", len(coins), n)

        # --- fetch daily charts for all coins ---
        async def _fetch_daily(coin_id: str) -> tuple[str, dict | None]:
            try:
                data = await client.get_market_chart(coin_id, config.LOOKBACK_DAYS_DAILY)
                return coin_id, data
            except Exception as e:
                log.warning("Daily fetch failed for %s: %s", coin_id, e)
                return coin_id, None

        daily_results = await asyncio.gather(*[_fetch_daily(m["id"]) for m in coins])
        daily_raw: dict[str, dict | None] = dict(daily_results)
        n_ok = sum(1 for v in daily_raw.values() if v)
        log.info("Daily data: %d/%d succeeded", n_ok, len(coins))
        stats = {"requested": len(coins), "fetched": n_ok, "universe_audit": audit}

        # --- parse daily, identify coins near thresholds for 4H fetch ---
        daily_parsed: dict[str, tuple[pd.Series, pd.Series]] = {}
        interesting: set[str] = set()

        for coin_id, raw in daily_raw.items():
            if not raw:
                continue
            closes, volumes = _parse_chart(raw)
            if len(closes) < config.RSI_PERIOD + 1:
                continue
            daily_parsed[coin_id] = (closes, volumes)
            rsi_s = wilder_rsi(closes, config.RSI_PERIOD).dropna()
            if not rsi_s.empty:
                cur = float(rsi_s.iloc[-1])
                if cur >= config.RSI_4H_FETCH_UPPER or cur <= config.RSI_4H_FETCH_LOWER:
                    interesting.add(coin_id)

        log.info("Fetching 4H data for %d coins near thresholds", len(interesting))

        # --- fetch hourly charts for interesting coins, resample to 4H ---
        async def _fetch_4h(coin_id: str) -> tuple[str, dict | None]:
            try:
                data = await client.get_market_chart(coin_id, config.LOOKBACK_DAYS_4H)
                return coin_id, data
            except Exception as e:
                log.warning("4H fetch failed for %s: %s", coin_id, e)
                return coin_id, None

        four_h_parsed: dict[str, pd.Series] = {}
        if interesting:
            four_h_results = await asyncio.gather(
                *[_fetch_4h(cid) for cid in interesting]
            )
            for coin_id, raw in four_h_results:
                if not raw:
                    continue
                closes_4h, _ = _parse_chart(raw, resample="4h")
                if len(closes_4h) >= config.RSI_PERIOD + 1:
                    four_h_parsed[coin_id] = closes_4h

    # --- BTC closes for correlation ---
    btc_closes: pd.Series | None = None
    if "bitcoin" in daily_parsed:
        btc_closes = daily_parsed["bitcoin"][0]
    eth_closes: pd.Series | None = None
    if "ethereum" in daily_parsed:
        eth_closes = daily_parsed["ethereum"][0]

    # --- market regime (BTC trend): the backdrop every setup is gated against ---
    market_regime = "UNKNOWN"
    if btc_closes is not None and len(btc_closes) >= config.REGIME_LONG_MA:
        market_regime = trend_regime(
            btc_closes, config.REGIME_SHORT_MA, config.REGIME_LONG_MA,
            config.REGIME_SLOPE_LOOKBACK,
        )
        log.info("Market regime (BTC): %s", market_regime)

    # --- full analysis ---
    coin_map = {m["id"]: m for m in coins}
    state_context = _build_state_context(daily_parsed, coin_map, btc_closes, eth_closes)
    rows: list[dict] = []
    for coin_id, (closes, volumes) in daily_parsed.items():
        market = coin_map.get(coin_id)
        if not market:
            continue
        result = _analyze_coin(
            closes,
            volumes,
            four_h_parsed.get(coin_id),
            btc_closes,
            market,
            market_regime,
            state_context,
        )
        if result:
            rows.append(result)

    # closes per coin, reused for outcome evaluation (no extra API calls)
    closes_map = {cid: cv[0] for cid, cv in daily_parsed.items()}

    stats["analyzed"] = len(rows)

    df = pd.DataFrame(rows)
    if df.empty:
        return df, closes_map, stats

    df = df.sort_values("rsi_daily", ascending=False).reset_index(drop=True)
    df["xrank"] = df["rsi_daily"].rank(ascending=False, method="min").astype(int)
    return df, closes_map, stats


# ---------------------------------------------------------------------------
# Message builder
# ---------------------------------------------------------------------------

def _is_present(value: object) -> bool:
    return value is not None and not (isinstance(value, float) and np.isnan(value))


def _format_signal(s: dict, is_new: bool) -> str:
    """One aligned line for the console/CSV report (monospace context)."""
    sev = {"EXTREME": "!!", "ALERT": "!", "WATCH": ".", "APPROACHING": "~"}.get(s["severity"], "")
    parts = [f"  {s['symbol']:<7} {sev:<2} c{int(s['conviction']):>3}"]

    rsi_str = f"D:{s['rsi_daily']:>5}"
    if _is_present(s.get("rsi_4h")):
        rsi_str += f"  4H:{s['rsi_4h']:>5}"
    if _is_present(s.get("rsi_weekly")):
        rsi_str += f"  W:{s['rsi_weekly']:>5}"
    parts.append(rsi_str)

    parts.append(f"z{s['rsi_z']:+.1f}")
    parts.append(f"d{s['rsi_delta']:+.0f}")

    if s["volume_ratio"] >= config.VOLUME_SPIKE_THRESHOLD:
        parts.append(f"vol:{s['volume_ratio']:.1f}x")
    if (s.get("btc_corr") or 0) > 0.7:
        parts.append("BTC-beta")
    if s.get("divergence"):
        parts.append(f"{'bull' if s['divergence'] == 'bullish' else 'bear'}-div")

    regime = s.get("regime") or ""
    if regime == "UNKNOWN":
        parts.append("regime?")
    elif regime:
        note = s.get("regime_note") or ""
        parts.append(f"{regime}{'/' + note if note else ''}")

    if is_new:
        parts.append("NEW")

    vol_state = s.get("vol_state")
    if vol_state in ("high_expanding", "crisis", "low_compressed"):
        parts.append(f"vol-state:{vol_state}")

    breadth_state = s.get("breadth_state")
    if breadth_state in ("washout", "washout_recovery", "breadth_collapse", "risk_on_broad"):
        parts.append(f"breadth:{breadth_state}")

    rs_bucket = s.get("rs_bucket")
    if rs_bucket in ("high", "low"):
        parts.append(f"RS:{rs_bucket}")

    if s.get("liquidity_bucket") == "low":
        parts.append("liq:low")

    knife_score = _finite_float(s.get("falling_knife_score"), 0.0) or 0.0
    if knife_score >= 70:
        parts.append(f"knife:{int(knife_score)}")

    return " | ".join(parts)


def build_message(
    df: pd.DataFrame, prev_flags: dict[str, str]
) -> tuple[str, list[dict]]:
    """Full console/CSV report. Returns (text, signals) where signals is one
    dict per currently-flagged coin (OB/OS/PRE_*) with routing metadata."""
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ob = df[df["flag"] == "OB"].sort_values("conviction", ascending=False)
    os_ = df[df["flag"] == "OS"].sort_values("conviction", ascending=False)
    pre = df[df["flag"].isin(["PRE_OB", "PRE_OS"])].sort_values("conviction", ascending=False)
    n = len(df)
    n_ob, n_os, n_pre = len(ob), len(os_), len(pre)

    lines = [f"RSI Scanner  {now_str}"]
    lines.append(f"Universe: {n} | OB: {n_ob} | OS: {n_os} | Approaching: {n_pre}")

    if n and n_ob >= n * 0.4:
        lines.append("!! High OB breadth - broad rally, individual flags are mostly beta")
    if n and n_os >= n * 0.4:
        lines.append("!! High OS breadth - broad flush, likely one macro move")

    signals: list[dict] = []

    def _emit(group, header: str) -> None:
        lines.append(header)
        for rec in group.to_dict("records"):
            is_new = prev_flags.get(rec["symbol"]) != rec["flag"]
            line = _format_signal(rec, is_new)
            lines.append(line)
            rec["conviction"] = int(rec["conviction"])
            rec["is_new"] = is_new
            rec["line"] = line
            signals.append(rec)

    if n_ob:
        _emit(ob, "\n--- OVERBOUGHT (stretched up), by conviction ---")
    if n_os:
        _emit(os_, "\n--- OVERSOLD (stretched down), by conviction ---")
    if n_pre:
        _emit(pre, "\n--- APPROACHING (not crossed yet, moving in), by conviction ---")
    if not (n_ob or n_os or n_pre):
        lines.append("\nNothing stretched or approaching today.")

    lines.append("")
    lines.append("c=conviction 0-100  D=daily  4H=4-hour  W=weekly  z=vs own history  d=3-day delta")
    lines.append("!!=extreme  !=alert  .=watch  ~=approaching  NEW=just crossed")
    lines.append("BTC-beta=correlated  vol=volume spike  bull/bear-div=RSI divergence")
    lines.append("regime vs 200d MA: UPTREND/continuation, DOWNTREND/reversal?, RANGE/range-top|bottom")

    return "\n".join(lines), signals


async def fetch_universe_audit(top_n: int | None = None) -> dict:
    """Fetch only the CoinGecko market list and build a hygiene audit."""
    n = top_n or config.TOP_N
    async with CoinGeckoClient() as client:
        fetch_n = candidate_count(n)
        markets = await client.get_top_markets(fetch_n)
    _, excluded, audit = filter_markets_with_audit(markets, limit=n)
    log.info(
        "Universe audit: requested top-%d; fetched %d candidates; excluded: %s",
        n,
        len(markets),
        format_exclusions(excluded),
    )
    return audit


async def _fetch_extra_daily_closes(coin_ids: list[str]) -> dict[str, pd.Series]:
    """Fetch daily closes for pending outcome/paper coins outside today's universe."""
    if not coin_ids:
        return {}
    async with CoinGeckoClient() as client:
        async def _fetch(coin_id: str) -> tuple[str, pd.Series | None]:
            try:
                raw = await client.get_market_chart(coin_id, config.LOOKBACK_DAYS_DAILY)
                closes, _ = _parse_chart(raw)
                return coin_id, closes if not closes.empty else None
            except Exception as exc:  # noqa: BLE001
                log.warning("Pending-history fetch failed for %s: %s", coin_id, exc)
                return coin_id, None

        results = await asyncio.gather(*[_fetch(cid) for cid in coin_ids])
    return {cid: closes for cid, closes in results if closes is not None}


def _outcome_since(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return (now - timedelta(days=max(config.OUTCOME_HORIZONS) + 5)).isoformat()


def _ensure_pending_closes(storage: Storage, closes_map: dict[str, pd.Series]) -> int:
    """Fill closes_map for recent signals/open paper trades that left today's universe."""
    needed = set(storage.recent_signal_coin_ids(_outcome_since()))
    needed.update(storage.open_paper_coin_ids())
    missing = sorted(cid for cid in needed if cid not in closes_map)
    if not missing:
        return 0
    log.info("Fetching %d extra histories for pending outcome/paper bookkeeping", len(missing))
    extra = asyncio.run(_fetch_extra_daily_closes(missing))
    closes_map.update(extra)
    if len(extra) < len(missing):
        log.warning("Pending-history data: %d/%d succeeded", len(extra), len(missing))
    return len(extra)


def _write_latest_csv(df: pd.DataFrame, *, dry_run: bool) -> bool:
    if dry_run:
        log.info("[dry-run] not writing latest CSV")
        return False
    # sparkline is a long list per row; keep it for alerts but not the CSV
    df.drop(columns=["sparkline", "state"], errors="ignore").to_csv(config.CSV_OUT, index=False)
    log.info("Full table -> %s", config.CSV_OUT)
    return True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(top_n: int | None = None, dry_run: bool = False, verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    config.validate()

    storage = Storage(config.DB_PATH)
    try:
        if not dry_run:
            storage.mark_scan_started(top_n=top_n, dry_run=False)

        # Process bot /start and /stop commands so the recipient list self-manages.
        if not dry_run:
            telegram.seed_subscribers_from_config(storage)
            added = telegram.sync_subscribers(storage)
            if added:
                log.info("Added %d new subscriber(s) via the bot", added)

        df, closes_map, stats = asyncio.run(scan(top_n))
        if not dry_run and stats.get("universe_audit"):
            audit = stats["universe_audit"]
            storage.set_meta("latest_universe_audit", json.dumps(audit, sort_keys=True))
            audit_path = write_audit(audit)
            log.info("Universe hygiene audit -> %s", audit_path)

        health_ok = True
        if not dry_run:
            health_ok = heartbeat.check_health(stats, storage)

        if df.empty:
            log.error("No data - check network / API key / rate limits")
            if not dry_run:
                storage.mark_scan_failure(
                    "No data - check network / API key / rate limits",
                    requested=stats.get("requested", 0),
                    fetched=stats.get("fetched", 0),
                    analyzed=stats.get("analyzed", 0),
                )
            return

        prev_flags = storage.get_prev_flags()
        # Fold matured live history into the table before saving/alerting so CSV,
        # DB, bot snapshots, and notifications agree on final conviction.
        df = _apply_live_edge_adjustments(df, storage)
        msg, signals = build_message(df, prev_flags)

        print("\n" + msg + "\n")

        _write_latest_csv(df, dry_run=dry_run)

        flagged = df[df["flag"] != ""]
        ob_count = int((flagged["flag"] == "OB").sum())
        os_count = int((flagged["flag"] == "OS").sum())

        # macro context (built before saving this scan, so prev counts are prior)
        macro_line = ""
        if config.MACRO_ENABLED:
            prev_counts = storage.last_scan_counts()
            macro_data = macro.build_macro(df, ob_count, os_count, prev_counts)
            macro_line = macro.macro_header(macro_data)

        # persist to database
        if not dry_run:
            scan_id = storage.save_scan(len(df), ob_count, os_count)
            for _, row in flagged.iterrows():
                sig = row.to_dict()
                sig["is_new"] = 1 if prev_flags.get(sig["symbol"]) != sig["flag"] else 0
                storage.save_signal(scan_id, sig)

        # snapshot latest signals so bot commands (/top, /detail) can answer
        # between runs
        if not dry_run:
            telegram.save_latest_snapshot(storage, signals)

        route_stats = _route_notifications(signals, storage, dry_run, macro_line=macro_line)

        # grade past signals whose horizons have matured (uses fetched closes)
        matured = 0
        if not dry_run:
            _ensure_pending_closes(storage, closes_map)
            matured = outcomes.evaluate_all(storage, closes_map)
            if matured:
                log.info("Recorded %d matured signal outcome(s)", matured)

        # paper-trade scoreboard: open new crossings, close matured positions
        opened = closed = 0
        if not dry_run:
            opened, closed = paper.update(storage, signals, closes_map)
            if opened or closed:
                log.info("Paper trades: opened %d, closed %d", opened, closed)

        # update state for next run (skip in dry-run so cron isn't desynced)
        if not dry_run:
            current_flags = {row["symbol"]: row["flag"] for _, row in flagged.iterrows()}
            storage.save_prev_flags(current_flags)
            storage.mark_scan_success(
                top_n=top_n,
                health_ok=health_ok,
                requested=stats.get("requested", 0),
                fetched=stats.get("fetched", 0),
                analyzed=stats.get("analyzed", 0),
                coin_count=len(df),
                flagged_count=len(flagged),
                ob_count=ob_count,
                os_count=os_count,
                instant_count=route_stats["instant_count"],
                digest_count=route_stats["digest_count"],
                instant_sent=route_stats["instant_sent"],
                digest_sent=route_stats["digest_sent"],
                matured_outcomes=matured,
                paper_opened=opened,
                paper_closed=closed,
            )

    except Exception as exc:
        log.exception("Scan failed")
        if not dry_run:
            storage.mark_scan_failure(f"{type(exc).__name__}: {exc}")
            heartbeat.alert_failure(exc, storage)
        raise
    finally:
        storage.close()


def _apply_live_edge_adjustments(df: pd.DataFrame, storage: Storage) -> pd.DataFrame:
    """Use matured live outcomes to annotate signals and nudge conviction.

    Backtested registry priors set the baseline; once the live DB has enough
    setup-specific outcomes, those outcomes can override the baseline gently.
    """
    rows = storage.outcomes_joined()
    if not rows:
        return df
    horizon = config.OUTCOME_PRIMARY_HORIZON
    stats = outcomes.track_records(rows, horizon)
    if not stats:
        return df

    df = df.copy()
    # Pre-create as object/None so unset rows stay None (not NaN) — NaN would
    # crash _tg_card ("expected str, got float") and pollute the bot snapshot.
    for col in ("track_record", "conviction_base"):
        if col not in df.columns:
            df[col] = pd.Series([None] * len(df), dtype=object)
    for idx, row in df[df["flag"] != ""].iterrows():
        setup = row.get("setup_type") or ""
        text = outcomes.track_record_text(setup, stats, horizon)
        if text:
            df.at[idx, "track_record"] = text

        # Live self-tuning: adjust by this setup's own matured hit rate.
        rec = stats.get(setup)
        if config.SELFTUNE_ENABLED and rec and rec["n"] >= config.SELFTUNE_MIN_SAMPLES:
            hit_rate = rec["hit"] / rec["n"]
            old = int(row["conviction"])
            new = conviction_adjustment(
                old, hit_rate, rec["n"],
                min_samples=config.SELFTUNE_MIN_SAMPLES,
                max_swing=config.SELFTUNE_MAX_SWING,
            )
            if new != old:
                df.at[idx, "conviction"] = new
                df.at[idx, "conviction_base"] = old  # keep for transparency
                # conviction can shift the tier (e.g. across the INSTANT line)
                df.at[idx, "tier"] = classify_tier(
                    row["flag"], row["severity"], new, row.get("market_aligned", "neutral")
                )
    return df


def _route_notifications(
    signals: list[dict], storage: Storage, dry_run: bool, macro_line: str = ""
) -> dict:
    """Tiered routing. Nothing worth a look is dropped — tier decides loudness.
      INSTANT: new, important crossings -> sent now (per-coin cooldown).
      DIGEST:  current watch-list snapshot -> batched, once per interval.
    """
    above_floor = lambda s: s["conviction"] >= config.MIN_CONVICTION_ALERT

    # Live recipient list = DB subscribers (auto-grown via /start), falling back
    # to the static .env list if nobody has subscribed yet.
    recipients = storage.active_subscribers() or config.TELEGRAM_CHAT_IDS

    # INSTANT — edge-triggered: only newly-crossed, off cooldown.
    instant = sorted(
        (
            s
            for s in signals
            if s["tier"] == "INSTANT"
            and s["is_new"]
            and above_floor(s)
            and not storage.is_on_cooldown(s["symbol"], s["flag"], config.COOLDOWN_HOURS)
        ),
        key=lambda s: s["conviction"],
        reverse=True,
    )

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    routed = {
        "instant_count": len(instant),
        "digest_count": 0,
        "instant_sent": False,
        "digest_sent": False,
    }

    if instant:
        names = ", ".join(s["symbol"] for s in instant)
        if dry_run:
            log.info("[dry-run] would send INSTANT alert: %s", names)
        else:
            sent = notify_all("instant", instant, ts, chat_ids=recipients, macro_line=macro_line)
            routed["instant_sent"] = bool(sent)
            if sent:
                for s in instant:
                    storage.mark_alerted(s["symbol"], s["flag"])
                log.info("INSTANT alert sent: %s", names)
            else:
                log.warning("INSTANT alert failed on all channels; not marking cooldown: %s", names)
    else:
        log.info("No new INSTANT signals (or on cooldown / below floor)")

    # DIGEST — level-triggered snapshot, rate-limited to once per interval.
    digest = sorted(
        (s for s in signals if s["tier"] == "DIGEST" and above_floor(s)),
        key=lambda s: s["conviction"],
        reverse=True,
    )
    if not digest:
        log.info("Nothing on the digest watch-list")
        return routed
    routed["digest_count"] = len(digest)

    if not storage.digest_due(config.DIGEST_INTERVAL_HOURS):
        log.info("Digest holding %d item(s) until next interval", len(digest))
        return routed

    if dry_run:
        log.info("[dry-run] would send DIGEST with %d item(s)", len(digest))
    else:
        sent = notify_all("digest", digest, ts, chat_ids=recipients, macro_line=macro_line)
        routed["digest_sent"] = bool(sent)
        if sent:
            storage.mark_digest_sent()
            log.info("DIGEST sent with %d item(s)", len(digest))
        else:
            log.warning("DIGEST failed on all channels; not marking digest sent")
    return routed


def report() -> None:
    """Print accumulated signal-outcome statistics and exit."""
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    storage = Storage(config.DB_PATH)
    try:
        rows = storage.outcomes_joined()
        print(outcomes.build_report(rows, config.OUTCOME_PRIMARY_HORIZON))
    finally:
        storage.close()


def score(json_output: bool = False, cohorts: bool = False) -> None:
    """Print the paper-trade scoreboard and exit."""
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    storage = Storage(config.DB_PATH)
    try:
        if json_output:
            print(json.dumps(paper.summary(storage), indent=2, sort_keys=True, default=str))
        else:
            print(paper.report(storage, cohorts=cohorts))
    finally:
        storage.close()


def refresh_paper(verbose: bool = False, json_output: bool = False, cohorts: bool = False) -> None:
    """Close matured paper trades without running a full alerting scan."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-5s %(message)s",
        datefmt="%H:%M:%S",
    )
    storage = Storage(config.DB_PATH)
    try:
        coin_ids = storage.open_paper_coin_ids()
        closes_map = asyncio.run(_fetch_extra_daily_closes(coin_ids))
        _, closed = paper.update(storage, [], closes_map)
        print(f"Paper refresh: fetched {len(closes_map)}/{len(coin_ids)} histories; closed {closed} trade(s).")
        if json_output:
            print(json.dumps(paper.summary(storage), indent=2, sort_keys=True, default=str))
        else:
            print(paper.report(storage, cohorts=cohorts))
    finally:
        storage.close()


def event_fade_report(verbose: bool = False) -> None:
    """Print local event-fade fixture scores without changing live RSI behavior."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-5s %(message)s",
        datefmt="%H:%M:%S",
    )
    cfg = event_fade.runtime_config(config)
    path = config.EVENT_FADE_EVENTS_PATH
    if not path:
        print("No event-fade event file configured. Set RSI_EVENT_FADE_EVENTS_PATH to a local JSON file.")
        return
    try:
        candidates = event_fade.load_event_fade_candidates(path)
    except ValueError as exc:
        log.warning("Event fade fixture load failed: %s", exc)
        print(f"Event fade fixture load failed: {exc}")
        return
    now = datetime.now(timezone.utc)
    print(event_fade.format_fade_report(candidates, cfg, now))


def _event_discovery_paths_configured() -> bool:
    return event_provider_status.build_event_discovery_provider_status(
        config
    ).ready_for_configured_review_cycle


def _event_discovery_refresh_diagnostics(
    result: event_discovery.EventDiscoveryResult,
    status_report: event_provider_status.EventDiscoveryProviderStatus,
) -> dict[str, Any]:
    warnings: list[str] = []
    if not result.raw_events:
        warnings.append(
            "no_raw_events_collected: configured event sources produced zero raw events; "
            "check provider warnings, credentials, rate limits, and query/window settings"
        )
    elif not result.candidates:
        warnings.append(
            "no_validation_candidates_built: raw events were collected but no high-confidence "
            "asset/classification candidates were built"
        )
    return {
        "provider_status": event_provider_status.provider_status_to_dict(status_report),
        "refresh_warnings": warnings,
    }


def _event_discovery_result_from_config() -> event_discovery.EventDiscoveryResult:
    cfg = event_discovery.EventDiscoveryConfig(
        min_link_confidence=config.EVENT_DISCOVERY_MIN_LINK_CONFIDENCE,
        min_classifier_confidence=config.EVENT_DISCOVERY_MIN_CLASSIFIER_CONFIDENCE,
        min_event_time_confidence=config.EVENT_DISCOVERY_MIN_EVENT_TIME_CONFIDENCE,
        allow_proxy_venue_trigger=config.EVENT_FADE_ALLOW_PROXY_VENUE_TRIGGER,
        lookback_hours=config.EVENT_DISCOVERY_LOOKBACK_HOURS,
        horizon_days=config.EVENT_DISCOVERY_HORIZON_DAYS,
    )
    return event_discovery.run_manual_discovery(
        config.EVENT_DISCOVERY_EVENTS_PATH,
        config.EVENT_DISCOVERY_ALIASES_PATH,
        binance_announcements_path=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH,
        binance_announcements_live=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE,
        binance_announcements_api_key=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_KEY,
        binance_announcements_api_secret=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_SECRET,
        binance_announcements_ws_url=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_WS_URL,
        binance_announcements_topic=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_TOPIC,
        binance_announcements_recv_window_ms=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_RECV_WINDOW_MS,
        binance_announcements_listen_seconds=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LISTEN_SECONDS,
        binance_announcements_max_messages=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_MAX_MESSAGES,
        bybit_announcements_path=config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH,
        bybit_announcements_live=config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE,
        bybit_announcements_base_url=config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_BASE_URL,
        bybit_announcements_locale=config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LOCALE,
        bybit_announcements_type=config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_TYPE,
        bybit_announcements_limit=config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIMIT,
        bybit_announcements_timeout=config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_TIMEOUT,
        coinmarketcal_path=config.EVENT_DISCOVERY_COINMARKETCAL_PATH,
        tokenomist_path=config.EVENT_DISCOVERY_TOKENOMIST_PATH,
        cryptopanic_path=config.EVENT_DISCOVERY_CRYPTOPANIC_PATH,
        cryptopanic_live=config.EVENT_DISCOVERY_CRYPTOPANIC_LIVE,
        cryptopanic_api_token=config.EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN,
        cryptopanic_base_url=config.EVENT_DISCOVERY_CRYPTOPANIC_BASE_URL,
        cryptopanic_public=config.EVENT_DISCOVERY_CRYPTOPANIC_PUBLIC,
        cryptopanic_filter=config.EVENT_DISCOVERY_CRYPTOPANIC_FILTER,
        cryptopanic_currencies=config.EVENT_DISCOVERY_CRYPTOPANIC_CURRENCIES,
        cryptopanic_regions=config.EVENT_DISCOVERY_CRYPTOPANIC_REGIONS,
        cryptopanic_kind=config.EVENT_DISCOVERY_CRYPTOPANIC_KIND,
        cryptopanic_search=config.EVENT_DISCOVERY_CRYPTOPANIC_SEARCH,
        cryptopanic_timeout=config.EVENT_DISCOVERY_CRYPTOPANIC_TIMEOUT,
        gdelt_path=config.EVENT_DISCOVERY_GDELT_PATH,
        gdelt_live=config.EVENT_DISCOVERY_GDELT_LIVE,
        gdelt_base_url=config.EVENT_DISCOVERY_GDELT_BASE_URL,
        gdelt_query=config.EVENT_DISCOVERY_GDELT_QUERY,
        gdelt_max_records=config.EVENT_DISCOVERY_GDELT_MAX_RECORDS,
        gdelt_timeout=config.EVENT_DISCOVERY_GDELT_TIMEOUT,
        project_blog_rss_path=config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH,
        project_blog_rss_live=config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE,
        project_blog_rss_urls=config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS,
        project_blog_rss_timeout=config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_TIMEOUT,
        external_ipo_path=config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH,
        sports_fixtures_path=config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH,
        prediction_market_events_path=config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH,
        prediction_market_events_live=config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE,
        prediction_market_events_base_url=config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_BASE_URL,
        prediction_market_events_limit=config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIMIT,
        prediction_market_events_timeout=config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_TIMEOUT,
        coinalyze_derivatives_path=config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH,
        coinalyze_live=config.EVENT_DISCOVERY_COINALYZE_LIVE,
        coinalyze_api_key=config.EVENT_DISCOVERY_COINALYZE_API_KEY,
        coinalyze_symbols=config.EVENT_DISCOVERY_COINALYZE_SYMBOLS,
        coinalyze_auto_symbols=config.EVENT_DISCOVERY_COINALYZE_AUTO_SYMBOLS,
        coinalyze_base_url=config.EVENT_DISCOVERY_COINALYZE_BASE_URL,
        coinalyze_timeout=config.EVENT_DISCOVERY_COINALYZE_TIMEOUT,
        coinalyze_history_interval=config.EVENT_DISCOVERY_COINALYZE_HISTORY_INTERVAL,
        coinalyze_lookback_hours=config.EVENT_DISCOVERY_COINALYZE_LOOKBACK_HOURS,
        coinalyze_convert_to_usd=config.EVENT_DISCOVERY_COINALYZE_CONVERT_TO_USD,
        tokenomist_supply_path=config.EVENT_DISCOVERY_TOKENOMIST_SUPPLY_PATH,
        etherscan_supply_path=config.EVENT_DISCOVERY_ETHERSCAN_SUPPLY_PATH,
        arkham_supply_path=config.EVENT_DISCOVERY_ARKHAM_SUPPLY_PATH,
        dune_supply_path=config.EVENT_DISCOVERY_DUNE_SUPPLY_PATH,
        universe_path=config.EVENT_DISCOVERY_UNIVERSE_PATH,
        universe_limit=config.EVENT_DISCOVERY_UNIVERSE_LIMIT or None,
        universe_live=config.EVENT_DISCOVERY_UNIVERSE_LIVE,
        universe_fetch_limit=config.EVENT_DISCOVERY_UNIVERSE_FETCH_LIMIT or None,
        cfg=cfg,
        fade_cfg=event_fade.runtime_config(config),
    )


def _setup_event_discovery_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-5s %(message)s",
        datefmt="%H:%M:%S",
    )


def event_discovery_report(verbose: bool = False) -> None:
    """Print research-only event-discovery radar from local fixtures."""
    _setup_event_discovery_logging(verbose)
    if not _event_discovery_paths_configured():
        print(
            "No event-discovery sources ready. Set RSI_EVENT_DISCOVERY_EVENTS_PATH, "
            "another event-discovery fixture path, or opt into a live research provider. "
            "Run --event-discovery-status for a redacted readiness report."
        )
        return
    result = _event_discovery_result_from_config()
    print(event_discovery.format_discovery_report(result))


def event_discovery_status(json_output: bool = False) -> None:
    """Print redacted readiness for research-only event-discovery providers."""
    status_report = event_provider_status.build_event_discovery_provider_status(config)
    if json_output:
        print(json.dumps(event_provider_status.provider_status_to_dict(status_report), indent=2, sort_keys=True))
    else:
        print(event_provider_status.format_event_discovery_provider_status(status_report))


def event_discovery_runs(limit: int | None = 10, json_output: bool = False) -> None:
    """Print recent event-discovery cache run diagnostics."""
    read = event_cache.load_discovery_runs(config.EVENT_DISCOVERY_CACHE_DIR, limit=limit)
    if json_output:
        print(json.dumps({
            "cache_dir": str(read.cache_dir),
            "runs_read": read.runs_read,
            "limit": read.limit,
            "rows": read.rows,
        }, indent=2, sort_keys=True))
        return
    print(_format_event_discovery_runs(read))


def _format_event_discovery_runs(read: event_cache.EventDiscoveryRunsReadResult) -> str:
    lines = [
        "EVENT DISCOVERY CACHE RUNS",
        f"Cache dir: {read.cache_dir}",
        f"Runs shown: {len(read.rows)}/{read.runs_read}",
    ]
    if not read.rows:
        lines.extend([
            "",
            "No discovery runs cached.",
            "Run `main.py --event-discovery-status`, then `main.py --event-discovery-refresh` with a working event source.",
        ])
        return "\n".join(lines)
    lines.append("")
    for row in read.rows:
        diagnostics = row.get("diagnostics") if isinstance(row.get("diagnostics"), dict) else {}
        provider_status = diagnostics.get("provider_status") if isinstance(diagnostics.get("provider_status"), dict) else {}
        warnings = diagnostics.get("refresh_warnings") if isinstance(diagnostics.get("refresh_warnings"), list) else []
        ready_sources = provider_status.get("ready_event_source_count", "?")
        ready = provider_status.get("ready_for_configured_review_cycle")
        ready_text = "yes" if ready is True else "no" if ready is False else "unknown"
        lines.append(
            f"- {row.get('observed_at', '?')} run={row.get('run_id', '?')} "
            f"raw={row.get('raw_events', 0)} normalized={row.get('normalized_events', 0)} "
            f"links={row.get('event_asset_links', 0)} classifications={row.get('classifications', 0)} "
            f"snapshots={row.get('candidate_snapshots', 0)} "
            f"ready_sources={ready_sources} ready={ready_text} warnings={len(warnings)}"
        )
        for warning in warnings:
            lines.append(f"  warning: {warning}")
    return "\n".join(lines)


def event_discovery_refresh(verbose: bool = False) -> None:
    """Fetch configured event-discovery sources and write observational cache artifacts."""
    _setup_event_discovery_logging(verbose)
    status_report = event_provider_status.build_event_discovery_provider_status(config)
    if not status_report.ready_for_configured_review_cycle:
        print(
            "No event-discovery sources ready. Set RSI_EVENT_DISCOVERY_EVENTS_PATH, "
            "another event-discovery fixture path, or opt into a live research provider. "
            "Run --event-discovery-status for a redacted readiness report."
        )
        return
    result = _event_discovery_result_from_config()
    diagnostics = _event_discovery_refresh_diagnostics(result, status_report)
    write = event_cache.write_event_discovery_cache(
        result,
        config.EVENT_DISCOVERY_CACHE_DIR,
        diagnostics=diagnostics,
    )
    print(
        "Event-discovery cache refresh: "
        f"raw={write.raw_events_written}, "
        f"normalized={write.normalized_events_written}, "
        f"links={write.event_asset_links_written}, "
        f"classifications={write.classifications_written}, "
        f"candidate_snapshots={write.candidate_snapshots_written}, "
        f"run={write.run_id}, dir={write.cache_dir}"
    )
    for warning in diagnostics["refresh_warnings"]:
        print(f"WARNING: {warning}")


def event_discovery_binance_listen(verbose: bool = False) -> None:
    """Listen briefly to Binance announcements and cache raw research evidence."""
    _setup_event_discovery_logging(verbose)
    if not config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE:
        print(
            "Binance announcement listener disabled. Set "
            "RSI_EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE=1 and API credentials."
        )
        return
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=config.EVENT_DISCOVERY_LOOKBACK_HOURS)
    end = now + timedelta(days=config.EVENT_DISCOVERY_HORIZON_DAYS)
    provider = BinanceAnnouncementProvider(
        None,
        live_enabled=True,
        api_key=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_KEY,
        api_secret=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_SECRET,
        ws_url=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_WS_URL,
        topic=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_TOPIC,
        recv_window_ms=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_RECV_WINDOW_MS,
        listen_seconds=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LISTEN_SECONDS,
        max_messages=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_MAX_MESSAGES,
    )
    raw_events = provider.fetch_events(start, end)
    result = EventDiscoveryResult(
        raw_events=tuple(raw_events),
        normalized_events=(),
        links=(),
        classifications=(),
        candidates=(),
    )
    write = event_cache.write_event_discovery_cache(result, config.EVENT_DISCOVERY_CACHE_DIR, observed_at=now)
    print(
        "Binance announcement cache listen: "
        f"seen={len(raw_events)}, "
        f"raw={write.raw_events_written}, "
        f"run={write.run_id}, dir={write.cache_dir}"
    )


def event_fade_auto_report(verbose: bool = False) -> None:
    """Print grouped research-only event-fade candidates from discovery fixtures."""
    _setup_event_discovery_logging(verbose)
    if not _event_discovery_paths_configured():
        print(
            "No event-discovery sources ready. Set RSI_EVENT_DISCOVERY_EVENTS_PATH, "
            "another event-discovery fixture path, or opt into a live research provider. "
            "Run --event-discovery-status for a redacted readiness report."
        )
        return
    result = _event_discovery_result_from_config()
    print(event_discovery.format_event_fade_auto_report(result))


def event_fade_export_sample(path: str, verbose: bool = False) -> None:
    """Export discovery-fed event-fade validation sample rows."""
    _setup_event_discovery_logging(verbose)
    if not _event_discovery_paths_configured():
        print(
            "No event-discovery sources ready. Set RSI_EVENT_DISCOVERY_EVENTS_PATH, "
            "another event-discovery fixture path, or opt into a live research provider. "
            "Run --event-discovery-status for a redacted readiness report."
        )
        return
    result = _event_discovery_result_from_config()
    rows = event_discovery.event_fade_validation_sample_rows(result)
    if path == "-":
        print(event_discovery.format_validation_sample_jsonl(rows))
        return
    out = event_discovery.write_validation_sample(rows, path)
    print(f"Event-fade validation sample: wrote {len(rows)} row(s) to {out}")


def event_fade_export_cache_sample(path: str, verbose: bool = False) -> None:
    """Export latest cached event-discovery snapshots as validation sample rows."""
    _setup_event_discovery_logging(verbose)
    read = event_cache.load_cached_validation_sample(config.EVENT_DISCOVERY_CACHE_DIR)
    if path == "-":
        print(event_discovery.format_validation_sample_jsonl(read.rows))
        return
    out = event_discovery.write_validation_sample(read.rows, path)
    print(
        "Event-fade cached validation sample: "
        f"read {read.snapshots_read} snapshot(s), "
        f"exported {len(read.rows)} latest row(s) to {out}"
    )


def event_fade_review_sample(path: str, verbose: bool = False) -> None:
    """Review status/labels/outcomes and next sample work for an event-fade validation export."""
    _setup_event_discovery_logging(verbose)
    rows = event_validation.load_validation_sample(path)
    review = event_validation.review_validation_sample(rows)
    print(event_validation.format_validation_review(review))


def event_fade_labeling_queue(path: str, limit: int | None = 20, verbose: bool = False) -> None:
    """Print prioritized rows that still need event-fade validation review."""
    _setup_event_discovery_logging(verbose)
    rows = event_validation.load_validation_sample(path)
    queue = event_validation.build_labeling_queue(rows, limit=limit)
    print(event_validation.format_labeling_queue(queue))


def event_fade_review_packet(
    sample_path: str,
    out_path: str,
    *,
    limit: int | None = 20,
    verbose: bool = False,
) -> None:
    """Write a Markdown packet for manual event-fade validation review."""
    _setup_event_discovery_logging(verbose)
    rows = event_validation.load_validation_sample(sample_path)
    queue = event_validation.build_labeling_queue(rows, limit=limit)
    packet = event_validation.format_review_packet(rows, limit=limit)
    if out_path == "-":
        print(packet)
        return
    out = Path(out_path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(packet + "\n", encoding="utf-8")
    print(
        "Event-fade review packet: "
        f"wrote {queue.shown_rows}/{queue.needed_rows} row(s) needing review to {out}"
    )


def event_fade_export_review_template(
    sample_path: str,
    out_path: str,
    *,
    limit: int | None = 20,
    verbose: bool = False,
) -> None:
    """Export compact editable sidecar rows for event-fade validation review."""
    _setup_event_discovery_logging(verbose)
    rows = event_validation.load_validation_sample(sample_path)
    queue = event_validation.build_labeling_queue(rows, limit=limit)
    if out_path == "-":
        template_rows = event_validation.build_review_template_rows(rows, limit=limit)
        print(event_validation.format_review_template_jsonl(template_rows))
        return
    out = event_validation.write_review_template(rows, out_path, limit=limit)
    print(
        "Event-fade review template: "
        f"wrote {queue.shown_rows}/{queue.needed_rows} row(s) needing review to {out}"
    )


def event_fade_apply_review_template(
    sample_path: str,
    template_path: str,
    out_path: str,
    *,
    verbose: bool = False,
) -> None:
    """Apply edited compact review sidecar rows to a validation sample artifact."""
    _setup_event_discovery_logging(verbose)
    sample_rows = event_validation.load_validation_sample(sample_path)
    template_rows = event_validation.load_validation_sample(template_path)
    result = event_validation.apply_review_template(sample_rows, template_rows)
    out = event_discovery.write_validation_sample(result.rows, out_path)
    review = event_validation.review_validation_sample(result.rows)
    print(
        "Event-fade review template apply: "
        f"{result.matched_rows} matched row(s), "
        f"{result.evidence_changed_rows} evidence-changed row(s), "
        f"{result.unmatched_reviewed_rows} unmatched reviewed row(s), "
        f"{result.copied_fields} copied field(s), wrote {len(result.rows)} row(s) to {out}"
    )
    evidence_changes = event_validation.format_merge_evidence_changes(result)
    if evidence_changes:
        print(evidence_changes)
    print("")
    print(event_validation.format_validation_review(review))


def event_fade_review_bundle(
    sample_path: str,
    out_dir: str,
    *,
    limit: int | None = 20,
    prices_path: str | None = None,
    auto_export_prices: bool = False,
    price_days: int | None = None,
    price_fixture_dir: str | None = None,
    price_interval: str = "1d",
    refresh_price_cache: bool = False,
    reviewed_path: str | None = None,
    overwrite_outcomes: bool = False,
    verbose: bool = False,
) -> None:
    """Write a local event-fade validation review workspace."""
    _setup_event_discovery_logging(verbose)
    source_rows = event_validation.load_validation_sample(sample_path)
    bundle_rows, review_merge = _merge_review_rows_for_bundle(source_rows, reviewed_path)
    result = _write_event_fade_review_bundle(
        source_rows=bundle_rows,
        sample_path=sample_path,
        out_dir=out_dir,
        limit=limit,
        prices_path=prices_path,
        auto_export_prices=auto_export_prices,
        price_days=price_days,
        price_fixture_dir=price_fixture_dir,
        price_interval=price_interval,
        refresh_price_cache=refresh_price_cache,
        reviewed_path=reviewed_path,
        review_merge=review_merge,
        overwrite_outcomes=overwrite_outcomes,
    )
    print(
        "Event-fade review bundle: "
        f"rows={result['rows']}, "
        f"needing_review={result['queue'].needed_rows}, "
        f"showing={result['queue'].shown_rows}, "
        f"dir={result['bundle_dir']}"
    )
    if result["rows"] == 0:
        print(_empty_review_bundle_message(sample_path))
    _print_review_merge_summary(review_merge)
    if result["price_export"] is not None:
        price_export = result["price_export"]
        print(
            "Outcome price fixture: "
            f"assets={price_export.assets_written}/{price_export.assets_requested}, "
            f"price_rows={price_export.price_rows_written}, "
            f"interval={price_export.interval}, source={price_export.source}, wrote {price_export.out_path}"
        )
    if result["outcome_sample"] is not None:
        print(f"Outcome-filled sample: {result['outcome_sample']}")


def event_fade_cache_review_bundle(
    out_dir: str,
    *,
    limit: int | None = 20,
    prices_path: str | None = None,
    auto_export_prices: bool = False,
    price_days: int | None = None,
    price_fixture_dir: str | None = None,
    price_interval: str = "1d",
    refresh_price_cache: bool = False,
    reviewed_path: str | None = None,
    overwrite_outcomes: bool = False,
    verbose: bool = False,
) -> None:
    """Write a local review workspace from latest cached event-discovery snapshots."""
    _setup_event_discovery_logging(verbose)
    read = event_cache.load_cached_validation_sample(config.EVENT_DISCOVERY_CACHE_DIR)
    bundle_rows, review_merge = _merge_review_rows_for_bundle(read.rows, reviewed_path)
    result = _write_event_fade_review_bundle(
        source_rows=bundle_rows,
        sample_path=f"cache:{read.cache_dir}",
        out_dir=out_dir,
        limit=limit,
        prices_path=prices_path,
        auto_export_prices=auto_export_prices,
        price_days=price_days,
        price_fixture_dir=price_fixture_dir,
        price_interval=price_interval,
        refresh_price_cache=refresh_price_cache,
        reviewed_path=reviewed_path,
        review_merge=review_merge,
        overwrite_outcomes=overwrite_outcomes,
    )
    print(
        "Event-fade cached review bundle: "
        f"snapshots_read={read.snapshots_read}, "
        f"rows={result['rows']}, "
        f"needing_review={result['queue'].needed_rows}, "
        f"showing={result['queue'].shown_rows}, "
        f"dir={result['bundle_dir']}"
    )
    if result["rows"] == 0:
        print(_empty_review_bundle_message(f"cache:{read.cache_dir}"))
    _print_review_merge_summary(review_merge)
    if result["price_export"] is not None:
        price_export = result["price_export"]
        print(
            "Outcome price fixture: "
            f"assets={price_export.assets_written}/{price_export.assets_requested}, "
            f"price_rows={price_export.price_rows_written}, "
            f"interval={price_export.interval}, source={price_export.source}, wrote {price_export.out_path}"
        )
    if result["outcome_sample"] is not None:
        print(f"Outcome-filled sample: {result['outcome_sample']}")


def _merge_review_rows_for_bundle(
    source_rows: list[dict[str, Any]],
    reviewed_path: str | None,
) -> tuple[list[dict[str, Any]], event_validation.ValidationSampleMergeResult | None]:
    if not reviewed_path:
        return source_rows, None
    reviewed_rows = event_validation.load_validation_sample(reviewed_path)
    result = event_validation.merge_review_fields(source_rows, reviewed_rows)
    return result.rows, result


def _print_review_merge_summary(
    review_merge: event_validation.ValidationSampleMergeResult | None,
) -> None:
    if review_merge is None:
        return
    print(
        "Review merge: "
        f"{review_merge.matched_rows} matched row(s), "
        f"{review_merge.evidence_changed_rows} evidence-changed row(s), "
        f"{review_merge.unmatched_reviewed_rows} unmatched reviewed row(s), "
        f"{review_merge.copied_fields} copied field(s)"
    )
    evidence_changes = event_validation.format_merge_evidence_changes(review_merge)
    if evidence_changes:
        print(evidence_changes)


def _empty_review_bundle_message(sample_path: str) -> str:
    return (
        "No validation rows were available for this review bundle. "
        f"Source={sample_path}. Run `main.py --event-discovery-status`, check live provider "
        "warnings/rate limits, then refresh event-discovery cache with at least one working event source."
    )


def _write_event_fade_review_bundle(
    *,
    source_rows: list[dict[str, Any]],
    sample_path: str,
    out_dir: str,
    limit: int | None,
    prices_path: str | None,
    auto_export_prices: bool,
    price_days: int | None,
    price_fixture_dir: str | None,
    price_interval: str,
    refresh_price_cache: bool,
    reviewed_path: str | None,
    review_merge: event_validation.ValidationSampleMergeResult | None,
    overwrite_outcomes: bool,
) -> dict[str, Any]:
    bundle_dir = Path(out_dir).expanduser()
    bundle_dir.mkdir(parents=True, exist_ok=True)

    copied_sample = event_discovery.write_validation_sample(
        source_rows,
        bundle_dir / "validation_sample.jsonl",
    )
    review_rows = source_rows
    effective_prices_path = prices_path
    price_export_result: event_price_history.EventFadeOutcomePriceExportResult | None = None
    if auto_export_prices and not effective_prices_path:
        price_export_result = event_price_history.export_outcome_price_fixture(
            source_rows,
            bundle_dir / "outcome_prices.json",
            days=price_days,
            fixture_dir=price_fixture_dir,
            cache_dir=config.BACKTEST_CACHE_DIR,
            refresh_cache=refresh_price_cache,
            interval=price_interval,
        )
        effective_prices_path = str(price_export_result.out_path)

    fill_summary = "No price fixture supplied; outcome fields were not filled."
    fill_result: event_validation.ValidationOutcomeFillResult | None = None
    outcome_sample: Path | None = None
    if effective_prices_path:
        prices = event_validation.load_outcome_price_fixture(effective_prices_path)
        fill_result = event_validation.fill_validation_outcomes(
            source_rows,
            prices,
            overwrite=overwrite_outcomes,
        )
        review_rows = fill_result.rows
        outcome_sample = event_discovery.write_validation_sample(
            review_rows,
            bundle_dir / "validation_sample_with_outcomes.jsonl",
        )
        fill_summary = (
            f"Filled {fill_result.filled_rows}/{fill_result.triggered_rows} triggered row(s); "
            f"missing_history={fill_result.missing_history_rows}, "
            f"insufficient_history={fill_result.insufficient_history_rows}, "
            f"skipped_existing={fill_result.skipped_existing_rows}."
        )

    queue = event_validation.build_labeling_queue(review_rows, limit=limit)
    review = event_validation.review_validation_sample(review_rows)
    sample_summary = _event_fade_review_sample_summary(review_rows)
    template_rows = event_validation.build_review_template_rows(review_rows, limit=limit)
    bundle_warnings = tuple([_empty_review_bundle_message(sample_path)] if not review_rows else [])

    queue_path = bundle_dir / "labeling_queue.txt"
    packet_path = bundle_dir / "review_packet.md"
    template_path = bundle_dir / "review_template.csv"
    report_path = bundle_dir / "review_report.txt"
    manifest_path = bundle_dir / "manifest.json"
    readme_path = bundle_dir / "README.md"

    queue_path.write_text(event_validation.format_labeling_queue(queue) + "\n", encoding="utf-8")
    packet_path.write_text(event_validation.format_review_packet(review_rows, limit=limit) + "\n", encoding="utf-8")
    template_path.write_text(event_validation.format_review_template_csv(template_rows), encoding="utf-8")
    report_path.write_text(event_validation.format_validation_review(review) + "\n", encoding="utf-8")
    manifest = _event_fade_review_bundle_manifest(
        sample_path=sample_path,
        prices_path=prices_path,
        overwrite_outcomes=overwrite_outcomes,
        copied_sample=copied_sample,
        price_export=price_export_result,
        outcome_sample=outcome_sample,
        queue_path=queue_path,
        packet_path=packet_path,
        template_path=template_path,
        report_path=report_path,
        readme_path=readme_path,
        source_rows=len(source_rows),
        review_rows=len(review_rows),
        queue=queue,
        review=review,
        sample_summary=sample_summary,
        limit=limit,
        fill_summary=fill_summary,
        fill_result=fill_result,
        effective_prices_path=effective_prices_path,
        auto_export_prices=auto_export_prices,
        price_days=price_days,
        price_fixture_dir=price_fixture_dir,
        price_interval=price_interval,
        refresh_price_cache=refresh_price_cache,
        reviewed_path=reviewed_path,
        review_merge=review_merge,
        warnings=bundle_warnings,
    )
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    readme_path.write_text(
        _event_fade_review_bundle_readme(
            sample_path=sample_path,
            copied_sample=copied_sample,
            price_export=price_export_result,
            outcome_sample=outcome_sample,
            queue_path=queue_path,
            packet_path=packet_path,
            template_path=template_path,
            report_path=report_path,
            manifest_path=manifest_path,
            rows=len(review_rows),
            queue=queue,
            review=review,
            sample_summary=sample_summary,
            fill_summary=fill_summary,
            auto_export_prices=auto_export_prices,
            reviewed_path=reviewed_path,
            review_merge=review_merge,
            warnings=bundle_warnings,
        ),
        encoding="utf-8",
    )
    return {
        "bundle_dir": bundle_dir,
        "price_export": price_export_result,
        "outcome_sample": outcome_sample,
        "queue": queue,
        "rows": len(review_rows),
    }


def _event_fade_review_bundle_manifest(
    *,
    sample_path: str,
    prices_path: str | None,
    overwrite_outcomes: bool,
    copied_sample: Path,
    price_export: event_price_history.EventFadeOutcomePriceExportResult | None,
    outcome_sample: Path | None,
    queue_path: Path,
    packet_path: Path,
    template_path: Path,
    report_path: Path,
    readme_path: Path,
    source_rows: int,
    review_rows: int,
    queue: event_validation.ValidationLabelingQueue,
    review: event_validation.EventFadeValidationReview,
    sample_summary: dict[str, Any],
    limit: int | None,
    fill_summary: str,
    fill_result: event_validation.ValidationOutcomeFillResult | None,
    effective_prices_path: str | None,
    auto_export_prices: bool,
    price_days: int | None,
    price_fixture_dir: str | None,
    price_interval: str,
    refresh_price_cache: bool,
    reviewed_path: str | None,
    review_merge: event_validation.ValidationSampleMergeResult | None,
    warnings: tuple[str, ...] = (),
) -> dict[str, Any]:
    files = {
        "readme": readme_path.name,
        "validation_sample": copied_sample.name,
        "labeling_queue": queue_path.name,
        "review_packet": packet_path.name,
        "review_template": template_path.name,
        "review_report": report_path.name,
    }
    if price_export is not None:
        files["outcome_prices"] = price_export.out_path.name
    if outcome_sample is not None:
        files["validation_sample_with_outcomes"] = outcome_sample.name
    outcome_fill: dict[str, Any] = {
        "enabled": effective_prices_path is not None,
        "prices_path": effective_prices_path,
        "overwrite_outcomes": overwrite_outcomes,
        "summary": fill_summary,
    }
    if fill_result is not None:
        outcome_fill.update({
            "sample_rows": fill_result.sample_rows,
            "triggered_rows": fill_result.triggered_rows,
            "filled_rows": fill_result.filled_rows,
            "missing_history_rows": fill_result.missing_history_rows,
            "insufficient_history_rows": fill_result.insufficient_history_rows,
            "skipped_existing_rows": fill_result.skipped_existing_rows,
        })

    return {
        "bundle_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "sample_path": sample_path,
            "source_rows": source_rows,
            "review_rows": review_rows,
        },
        "warnings": list(warnings),
        "sample_summary": sample_summary,
        "files": files,
        "queue": {
            "limit": limit,
            "needed_rows": queue.needed_rows,
            "shown_rows": queue.shown_rows,
            "total_rows": queue.total_rows,
        },
        "review": {
            "promotion_ready": review.promotion_ready,
            "promotion_blockers": list(review.promotion_blockers),
            "reviewed_rows": review.reviewed_rows,
            "reviewed_proxy_candidates": review.reviewed_proxy_candidates,
            "reviewed_negative_controls": review.reviewed_negative_controls,
            "reviewed_proxy_event_types": review.reviewed_proxy_event_types,
            "min_proxy_event_types": review.min_proxy_event_types,
            "reviewed_proxy_source_providers": review.reviewed_proxy_source_providers,
            "min_proxy_source_providers": review.min_proxy_source_providers,
            "reviewed_proxy_source_origins": review.reviewed_proxy_source_origins,
            "triggered_reviewed": review.triggered_reviewed,
            "triggered_btc_risk_buckets": review.triggered_btc_risk_buckets,
            "min_trigger_btc_risk_buckets": review.min_trigger_btc_risk_buckets,
            "low_confidence_trigger_event_time_rows": review.low_confidence_trigger_event_time_rows,
            "missing_trigger_outcome_rows": review.missing_trigger_outcome_rows,
            "missing_event_time_baseline_rows": review.missing_event_time_baseline_rows,
            "point_in_time_violation_rows": review.point_in_time_violation_rows,
            "post_decision_source_rows": review.post_decision_source_rows,
            "missing_source_timing_rows": review.missing_source_timing_rows,
            "next_sample_work": list(event_validation.validation_review_next_steps(review)),
        },
        "price_export": _event_fade_review_price_export_manifest(
            auto_export_prices=auto_export_prices,
            explicit_prices_path=prices_path,
            price_days=price_days,
            price_fixture_dir=price_fixture_dir,
            price_interval=price_interval,
            refresh_price_cache=refresh_price_cache,
            result=price_export,
        ),
        "outcome_fill": outcome_fill,
        "review_merge": _event_fade_review_merge_manifest(reviewed_path, review_merge),
    }


def _event_fade_review_price_export_manifest(
    *,
    auto_export_prices: bool,
    explicit_prices_path: str | None,
    price_days: int | None,
    price_fixture_dir: str | None,
    price_interval: str,
    refresh_price_cache: bool,
    result: event_price_history.EventFadeOutcomePriceExportResult | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "enabled": auto_export_prices,
        "exported": result is not None,
        "explicit_prices_path": explicit_prices_path,
        "requested_days": price_days,
        "requested_interval": price_interval,
        "fixture_dir": price_fixture_dir,
        "refresh_cache": refresh_price_cache,
    }
    if result is not None:
        payload.update({
            "out_path": str(result.out_path),
            "assets_requested": result.assets_requested,
            "assets_written": result.assets_written,
            "price_rows_written": result.price_rows_written,
            "missing_assets": list(result.missing_assets),
            "days": result.days,
            "interval": result.interval,
            "source": result.source,
        })
    return payload


def _event_fade_review_merge_manifest(
    reviewed_path: str | None,
    review_merge: event_validation.ValidationSampleMergeResult | None,
) -> dict[str, Any]:
    if review_merge is None:
        return {
            "enabled": False,
            "reviewed_path": reviewed_path,
        }
    return {
        "enabled": True,
        "reviewed_path": reviewed_path,
        "fresh_rows": review_merge.fresh_rows,
        "reviewed_rows": review_merge.reviewed_rows,
        "matched_rows": review_merge.matched_rows,
        "evidence_changed_rows": review_merge.evidence_changed_rows,
        "unmatched_reviewed_rows": review_merge.unmatched_reviewed_rows,
        "copied_fields": review_merge.copied_fields,
        "evidence_changes": [
            {
                "event_id": item.event_id,
                "asset_symbol": item.asset_symbol,
                "asset_coin_id": item.asset_coin_id,
                "relationship_type": item.relationship_type,
                "changed_fields": list(item.changed_fields),
            }
            for item in review_merge.evidence_changes
        ],
    }


def _event_fade_review_sample_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Build compact sample-quality counts for review bundle manifests/READMEs."""
    source_provider_summary = _event_fade_review_source_provider_summary(rows)
    source_origin_summary = _event_fade_review_source_origin_summary(rows)
    return {
        "rows": len(rows),
        "review_status": _count_values(row.get("review_status") or "missing" for row in rows),
        "human_labels": _count_values(row.get("human_label") or "unlabeled" for row in rows),
        "event_types": _count_values(row.get("event_type") or "unknown" for row in rows),
        "relationship_types": _count_values(row.get("relationship_type") or "unknown" for row in rows),
        "asset_roles": _count_values(row.get("asset_role") or "unknown" for row in rows),
        "signal_types": _count_values(row.get("signal_type") or "NO_TRADE" for row in rows),
        "source_providers": _count_values(
            provider
            for row in rows
            for provider in _bundle_list_values(row.get("raw_providers"))
        ),
        "source_origins": _count_values(
            origin
            for row in rows
            for origin in event_validation.source_origin_values(row)
        ),
        "proxy_candidates": sum(1 for row in rows if _bundle_bool(row.get("is_proxy_narrative"))),
        "proxy_context_controls": sum(1 for row in rows if row.get("relationship_type") == "proxy_context"),
        "direct_beneficiaries": sum(1 for row in rows if _bundle_bool(row.get("is_direct_beneficiary"))),
        "eligible_rows": sum(1 for row in rows if _bundle_bool(row.get("eligible"))),
        "short_triggered_rows": sum(1 for row in rows if row.get("signal_type") == "SHORT_TRIGGERED"),
        "missing_event_time_rows": sum(1 for row in rows if not row.get("event_time")),
        "source_provider_summary": source_provider_summary,
        "source_origin_summary": source_origin_summary,
    }


def _event_fade_review_source_provider_summary(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for row in rows:
        providers = _bundle_list_values(row.get("raw_providers")) or _bundle_list_values(row.get("source")) or ["unknown"]
        for provider in providers:
            bucket = summary.setdefault(provider, {
                "rows": 0,
                "proxy_candidates": 0,
                "proxy_context_controls": 0,
                "direct_beneficiaries": 0,
                "eligible_rows": 0,
                "short_triggered_rows": 0,
                "missing_event_time_rows": 0,
            })
            bucket["rows"] += 1
            if _bundle_bool(row.get("is_proxy_narrative")):
                bucket["proxy_candidates"] += 1
            if row.get("relationship_type") == "proxy_context":
                bucket["proxy_context_controls"] += 1
            if _bundle_bool(row.get("is_direct_beneficiary")):
                bucket["direct_beneficiaries"] += 1
            if _bundle_bool(row.get("eligible")):
                bucket["eligible_rows"] += 1
            if row.get("signal_type") == "SHORT_TRIGGERED":
                bucket["short_triggered_rows"] += 1
            if not row.get("event_time"):
                bucket["missing_event_time_rows"] += 1
    return dict(sorted(
        summary.items(),
        key=lambda item: (-item[1]["rows"], item[0]),
    ))


def _event_fade_review_source_origin_summary(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for row in rows:
        origins = event_validation.source_origin_values(row)
        for origin in origins:
            bucket = summary.setdefault(origin, {
                "rows": 0,
                "proxy_candidates": 0,
                "proxy_context_controls": 0,
                "direct_beneficiaries": 0,
                "eligible_rows": 0,
                "short_triggered_rows": 0,
                "missing_event_time_rows": 0,
            })
            bucket["rows"] += 1
            if _bundle_bool(row.get("is_proxy_narrative")):
                bucket["proxy_candidates"] += 1
            if row.get("relationship_type") == "proxy_context":
                bucket["proxy_context_controls"] += 1
            if _bundle_bool(row.get("is_direct_beneficiary")):
                bucket["direct_beneficiaries"] += 1
            if _bundle_bool(row.get("eligible")):
                bucket["eligible_rows"] += 1
            if row.get("signal_type") == "SHORT_TRIGGERED":
                bucket["short_triggered_rows"] += 1
            if not row.get("event_time"):
                bucket["missing_event_time_rows"] += 1
    return dict(sorted(
        summary.items(),
        key=lambda item: (-item[1]["rows"], item[0]),
    ))


def _count_values(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _bundle_list_values(value: object) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item not in (None, "")]
    if isinstance(value, tuple):
        return [str(item) for item in value if item not in (None, "")]
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                return [raw]
            if isinstance(parsed, list):
                return [str(item) for item in parsed if item not in (None, "")]
        return [raw]
    return [str(value)]


def _bundle_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "y"}
    return False


def event_fade_merge_sample(fresh_path: str, reviewed_path: str, out_path: str, verbose: bool = False) -> None:
    """Merge manual review status, labels, and outcomes into a fresh export."""
    _setup_event_discovery_logging(verbose)
    fresh = event_validation.load_validation_sample(fresh_path)
    reviewed = event_validation.load_validation_sample(reviewed_path)
    result = event_validation.merge_review_fields(fresh, reviewed)
    out = event_discovery.write_validation_sample(result.rows, out_path)
    print(
        "Event-fade validation sample merge: "
        f"{result.matched_rows} matched row(s), "
        f"{result.evidence_changed_rows} evidence-changed row(s), "
        f"{result.unmatched_reviewed_rows} unmatched reviewed row(s), "
        f"{result.copied_fields} copied field(s), wrote {len(result.rows)} row(s) to {out}"
    )
    evidence_changes = event_validation.format_merge_evidence_changes(result)
    if evidence_changes:
        print(evidence_changes)


def event_fade_fill_outcomes(
    sample_path: str,
    prices_path: str,
    out_path: str,
    *,
    overwrite: bool = False,
    verbose: bool = False,
) -> None:
    """Fill validation-sample outcome fields from local OHLCV fixtures."""
    _setup_event_discovery_logging(verbose)
    rows = event_validation.load_validation_sample(sample_path)
    prices = event_validation.load_outcome_price_fixture(prices_path)
    result = event_validation.fill_validation_outcomes(rows, prices, overwrite=overwrite)
    out = event_discovery.write_validation_sample(result.rows, out_path)
    print(
        "Event-fade validation outcome fill: "
        f"{result.filled_rows}/{result.triggered_rows} triggered row(s) filled, "
        f"missing_history={result.missing_history_rows}, "
        f"insufficient_history={result.insufficient_history_rows}, "
        f"skipped_existing={result.skipped_existing_rows}, "
        f"wrote {len(result.rows)} row(s) to {out}"
    )


def event_fade_export_outcome_prices(
    sample_path: str,
    out_path: str,
    *,
    days: int | None = None,
    fixture_dir: str | None = None,
    interval: str = "1d",
    refresh_cache: bool = False,
    verbose: bool = False,
) -> None:
    """Export local OHLCV prices for event-fade validation outcome filling."""
    _setup_event_discovery_logging(verbose)
    rows = event_validation.load_validation_sample(sample_path)
    result = event_price_history.export_outcome_price_fixture(
        rows,
        out_path,
        days=days,
        fixture_dir=fixture_dir,
        cache_dir=config.BACKTEST_CACHE_DIR,
        refresh_cache=refresh_cache,
        interval=interval,
    )
    missing = ", ".join(result.missing_assets) if result.missing_assets else "none"
    print(
        "Event-fade outcome price export: "
        f"assets={result.assets_written}/{result.assets_requested}, "
        f"price_rows={result.price_rows_written}, "
        f"days={result.days}, interval={result.interval}, source={result.source}, "
        f"missing={missing}, wrote {result.out_path}"
    )


def _event_fade_review_bundle_readme(
    *,
    sample_path: str,
    copied_sample: Path,
    price_export: event_price_history.EventFadeOutcomePriceExportResult | None,
    outcome_sample: Path | None,
    queue_path: Path,
    packet_path: Path,
    template_path: Path,
    report_path: Path,
    manifest_path: Path,
    rows: int,
    queue: event_validation.ValidationLabelingQueue,
    review: event_validation.EventFadeValidationReview,
    sample_summary: dict[str, Any],
    fill_summary: str,
    auto_export_prices: bool,
    reviewed_path: str | None,
    review_merge: event_validation.ValidationSampleMergeResult | None,
    warnings: tuple[str, ...] = (),
) -> str:
    price_line = (
        f"- `{price_export.out_path.name}`: bundle-local OHLCV price fixture"
        if price_export is not None
        else "- No bundle-local price fixture was exported."
    )
    outcome_line = (
        f"- `{outcome_sample.name}`: sample with locally filled trigger/baseline outcomes"
        if outcome_sample is not None
        else "- No outcome-filled sample was written."
    )
    if review_merge is None:
        merge_line = "- No prior reviewed sample was merged."
    else:
        merge_line = (
            f"- Prior reviewed sample `{reviewed_path}` merged: "
            f"{review_merge.matched_rows} matched, "
            f"{review_merge.evidence_changed_rows} evidence-changed, "
            f"{review_merge.copied_fields} copied field(s)."
        )
    warning_lines = ["Warnings:", *(f"- {warning}" for warning in warnings), ""] if warnings else []
    return "\n".join([
        "# Event-Fade Validation Review Bundle",
        "",
        "Research-only: no alerts, live DB writes, paper trades, or orders.",
        "",
        f"Input sample: `{sample_path}`",
        f"Rows: {rows}",
        f"Rows needing labels/status/outcomes: {queue.needed_rows}",
        f"Rows shown in queue/template/packet: {queue.shown_rows}",
        "",
        "Sample summary:",
        *_event_fade_review_bundle_summary_lines(sample_summary),
        "",
        "Review gates:",
        *_event_fade_review_gate_lines(review),
        *warning_lines,
        f"Auto price export: {'yes' if auto_export_prices else 'no'}",
        f"Outcome fill: {fill_summary}",
        "Review merge:",
        merge_line,
        "",
        "Files:",
        f"- `{copied_sample.name}`: copied source validation sample",
        price_line,
        outcome_line,
        f"- `{queue_path.name}`: prioritized queue for missing labels/status/outcomes",
        f"- `{packet_path.name}`: human-readable evidence packet",
        f"- `{template_path.name}`: compact editable CSV sidecar",
        f"- `{report_path.name}`: current review metrics and promotion blockers",
        f"- `{manifest_path.name}`: machine-readable bundle provenance and counts",
        "",
        "Suggested workflow:",
        "1. Read `review_packet.md` for evidence.",
        "2. Edit `review_template.csv` with `review_status`, `human_label`, `human_notes`, and any missing outcomes.",
        "3. Apply the edited sidecar with `main.py --event-fade-apply-review-template SAMPLE TEMPLATE OUT`.",
        "4. Run `main.py --event-fade-review-sample OUT` to inspect coverage and blockers.",
        "",
    ])


def _event_fade_review_bundle_summary_lines(sample_summary: dict[str, Any]) -> list[str]:
    return [
        f"- Proxy candidates: {sample_summary.get('proxy_candidates', 0)}",
        f"- Proxy-context controls: {sample_summary.get('proxy_context_controls', 0)}",
        f"- Direct beneficiaries: {sample_summary.get('direct_beneficiaries', 0)}",
        f"- SHORT_TRIGGERED rows: {sample_summary.get('short_triggered_rows', 0)}",
        f"- Missing event time rows: {sample_summary.get('missing_event_time_rows', 0)}",
        "- Asset roles: " + _summary_count_line(sample_summary.get("asset_roles")),
        "- Relationships: " + _summary_count_line(sample_summary.get("relationship_types")),
        "- Source providers: " + _summary_count_line(sample_summary.get("source_providers")),
        "- Source provider detail: " + _source_provider_summary_line(sample_summary.get("source_provider_summary")),
        "- Source origins: " + _summary_count_line(sample_summary.get("source_origins")),
        "- Source origin detail: " + _source_provider_summary_line(sample_summary.get("source_origin_summary")),
        "",
    ]


def _event_fade_review_gate_lines(review: event_validation.EventFadeValidationReview) -> list[str]:
    return [
        f"- Promotion ready: {'yes' if review.promotion_ready else 'no'}",
        (
            f"- Reviewed coverage: proxy={review.reviewed_proxy_candidates}/{review.min_proxy_candidates}, "
            f"controls={review.reviewed_negative_controls}/{review.min_negative_controls}, "
            f"triggers={review.triggered_reviewed}/{review.min_triggered_reviewed}"
        ),
        (
            f"- Proxy diversity: event_types={review.reviewed_proxy_event_types}/{review.min_proxy_event_types}, "
            f"source_providers={review.reviewed_proxy_source_providers}/{review.min_proxy_source_providers}, "
            f"source_origins={review.reviewed_proxy_source_origins}"
        ),
        (
            f"- Trigger diversity: btc_risk_buckets={review.triggered_btc_risk_buckets}/"
            f"{review.min_trigger_btc_risk_buckets}"
        ),
        (
            f"- Timing blockers: low_confidence_trigger_times={review.low_confidence_trigger_event_time_rows}, "
            f"missing_source_timing={review.missing_source_timing_rows}, "
            f"point_in_time_violations={review.point_in_time_violation_rows}, "
            f"post_decision_source_rows={review.post_decision_source_rows}"
        ),
        "",
    ]


def _summary_count_line(counts: object, *, limit: int = 6) -> str:
    if not isinstance(counts, dict) or not counts:
        return "none"
    parts = [f"{key}={value}" for key, value in list(counts.items())[:limit]]
    remaining = len(counts) - len(parts)
    if remaining > 0:
        parts.append(f"+{remaining} more")
    return ", ".join(parts)


def _source_provider_summary_line(summary: object, *, limit: int = 4) -> str:
    if not isinstance(summary, dict) or not summary:
        return "none"
    parts: list[str] = []
    for provider, raw_counts in list(summary.items())[:limit]:
        if not isinstance(raw_counts, dict):
            continue
        parts.append(
            f"{provider}: rows={raw_counts.get('rows', 0)}, "
            f"proxy={raw_counts.get('proxy_candidates', 0)}, "
            f"direct={raw_counts.get('direct_beneficiaries', 0)}, "
            f"triggered={raw_counts.get('short_triggered_rows', 0)}, "
            f"missing_time={raw_counts.get('missing_event_time_rows', 0)}"
        )
    remaining = len(summary) - len(parts)
    if remaining > 0:
        parts.append(f"+{remaining} more")
    return "; ".join(parts) if parts else "none"


def status() -> None:
    """Print operational scan/listener health and exit."""
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    storage = Storage(config.DB_PATH)
    try:
        from .status_report import format_status
        print(format_status(storage))
    finally:
        storage.close()


def backup_db() -> None:
    """Create and verify a safe SQLite backup, then prune old backups."""
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    from .backups import backup_database, format_backup_result

    result = backup_database(config.DB_PATH, config.BACKUP_DIR, keep=config.BACKUP_KEEP)
    print(format_backup_result(result))


def verify_restore(backup_path: str | None = None) -> None:
    """Restore-check a backup, defaulting to the newest retained DB backup."""
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    from .backups import format_restore_result, latest_backup_status, verify_restore as _verify_restore

    path = Path(backup_path).expanduser() if backup_path else None
    if path is None:
        latest = latest_backup_status(config.DB_PATH, config.BACKUP_DIR)
        if latest.path is None:
            raise FileNotFoundError(f"no backups found in {config.BACKUP_DIR}")
        path = latest.path
    result = _verify_restore(path, expected_tables=config.RESTORE_EXPECTED_TABLES)
    print(format_restore_result(result))


def rotate_logs() -> None:
    """Rotate oversized local launchd logs."""
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    from .ops import format_log_rotation, rotate_logs as _rotate_logs

    results = _rotate_logs(
        config.LOG_FILES,
        max_bytes=config.LOG_ROTATE_MAX_BYTES,
        keep=config.LOG_ROTATE_KEEP,
    )
    print(format_log_rotation(results))


def maintenance() -> None:
    """Run the daily local maintenance bundle: backup, restore drill, log rotation."""
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    from .backups import (
        backup_database,
        format_backup_result,
        format_restore_result,
        verify_restore as _verify_restore,
    )
    from .ops import format_log_rotation, rotate_logs as _rotate_logs

    backup = backup_database(config.DB_PATH, config.BACKUP_DIR, keep=config.BACKUP_KEEP)
    restore = _verify_restore(backup.path, expected_tables=config.RESTORE_EXPECTED_TABLES)
    rotated = _rotate_logs(
        config.LOG_FILES,
        max_bytes=config.LOG_ROTATE_MAX_BYTES,
        keep=config.LOG_ROTATE_KEEP,
    )
    print(format_backup_result(backup))
    print()
    print(format_restore_result(restore))
    print()
    print(format_log_rotation(rotated))


def launchd_status() -> None:
    """Print launchd status for the scan and bot agents."""
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    from .ops import format_launchd_status, launchd_status as _launchd_status

    statuses = _launchd_status((
        config.LAUNCHD_SCAN_LABEL,
        config.LAUNCHD_BOT_LABEL,
        config.MAINTENANCE_LABEL,
    ))
    print(format_launchd_status(statuses))


def restart_listener() -> None:
    """Restart the always-on Telegram bot listener launchd agent."""
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    from .ops import format_launchd_command, restart_launchd_service

    result = restart_launchd_service(config.LAUNCHD_BOT_LABEL)
    print(format_launchd_command(result))


def install_maintenance_agent() -> None:
    """Install/load the daily launchd maintenance agent for this checkout."""
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    from .ops import format_maintenance_agent_install, install_maintenance_agent as _install

    result = _install(
        label=config.MAINTENANCE_LABEL,
        python_path=Path(sys.executable),
        main_path=config.DATA_DIR / "main.py",
        working_dir=config.DATA_DIR,
        log_path=config.MAINTENANCE_LOG,
        hour=config.MAINTENANCE_HOUR,
        minute=config.MAINTENANCE_MINUTE,
    )
    print(format_maintenance_agent_install(result))


def universe_audit() -> None:
    """Print the most recently persisted universe hygiene audit."""
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    storage = Storage(config.DB_PATH)
    try:
        raw = storage.get_meta("latest_universe_audit")
        audit = json.loads(raw) if raw else {}
        print(format_audit(audit))
    finally:
        storage.close()


def refresh_universe_audit(top_n: int | None = None, verbose: bool = False) -> None:
    """Refresh and persist the universe hygiene audit without a full RSI scan."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    config.validate()
    audit = asyncio.run(fetch_universe_audit(top_n))
    storage = Storage(config.DB_PATH)
    try:
        storage.set_meta("latest_universe_audit", json.dumps(audit, sort_keys=True))
    finally:
        storage.close()
    audit_path = write_audit(audit)
    log.info("Universe hygiene audit -> %s", audit_path)
    print(format_audit(audit))


def cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Top-N crypto multi-timeframe RSI overextension scanner."
    )
    parser.add_argument("--top-n", type=int, default=None, help="Number of coins to scan.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan and print, but send no notifications and don't update state.",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Print signal-outcome stats (hit-rates, forward returns) and exit.",
    )
    parser.add_argument(
        "--score",
        action="store_true",
        help="Print the paper-trade scoreboard (realized P&L by book/setup) and exit.",
    )
    parser.add_argument(
        "--refresh-paper",
        action="store_true",
        help="Fetch open paper-trade histories, close matured positions, and print the scoreboard without alerts.",
    )
    parser.add_argument(
        "--event-fade-report",
        action="store_true",
        help="Score local event-fade JSON fixtures and print an alert-only report.",
    )
    parser.add_argument(
        "--event-discovery-report",
        action="store_true",
        help="Print research-only event radar from local discovery fixtures.",
    )
    parser.add_argument(
        "--event-discovery-refresh",
        action="store_true",
        help="Fetch configured event-discovery sources and append research-only JSONL cache artifacts.",
    )
    parser.add_argument(
        "--event-discovery-status",
        action="store_true",
        help="Print redacted readiness for research-only event-discovery providers.",
    )
    parser.add_argument(
        "--event-discovery-runs",
        action="store_true",
        help="Print recent research-cache event-discovery run diagnostics.",
    )
    parser.add_argument(
        "--event-discovery-run-limit",
        type=int,
        default=10,
        help="Maximum recent run rows to show for --event-discovery-runs.",
    )
    parser.add_argument(
        "--event-discovery-binance-listen",
        action="store_true",
        help="Listen briefly to live Binance announcements and append raw research JSONL cache artifacts.",
    )
    parser.add_argument(
        "--event-fade-auto-report",
        action="store_true",
        help="Print grouped research-only event-fade candidates from discovery fixtures.",
    )
    parser.add_argument(
        "--event-fade-export-sample",
        metavar="PATH",
        help="Export a research-only event-fade validation sample from discovery fixtures (.jsonl/.csv or '-' for JSONL stdout).",
    )
    parser.add_argument(
        "--event-fade-export-cache-sample",
        metavar="PATH",
        help="Export latest research-cache candidate snapshots as a validation sample (.jsonl/.csv or '-' for JSONL stdout).",
    )
    parser.add_argument(
        "--event-fade-review-sample",
        metavar="PATH",
        help="Review status/labels/outcomes and next sample work in a research-only event-fade validation sample export.",
    )
    parser.add_argument(
        "--event-fade-labeling-queue",
        metavar="PATH",
        help="Print prioritized validation sample rows that need human review status, labels, or outcomes.",
    )
    parser.add_argument(
        "--event-fade-review-packet",
        nargs=2,
        metavar=("SAMPLE", "OUT"),
        help="Write a Markdown manual-review packet for prioritized validation rows.",
    )
    parser.add_argument(
        "--event-fade-export-review-template",
        nargs=2,
        metavar=("SAMPLE", "OUT"),
        help="Write compact editable review sidecar rows for prioritized validation rows.",
    )
    parser.add_argument(
        "--event-fade-apply-review-template",
        nargs=3,
        metavar=("SAMPLE", "TEMPLATE", "OUT"),
        help="Apply edited compact review sidecar rows to SAMPLE and write OUT.",
    )
    parser.add_argument(
        "--event-fade-review-bundle",
        nargs=2,
        metavar=("SAMPLE", "OUT_DIR"),
        help="Write a local manual-review workspace for an event-fade validation sample.",
    )
    parser.add_argument(
        "--event-fade-cache-review-bundle",
        metavar="OUT_DIR",
        help="Write a local manual-review workspace from latest cached event-discovery snapshots.",
    )
    parser.add_argument(
        "--event-fade-review-bundle-prices",
        metavar="PRICES",
        help="Optional local OHLCV price fixture for review-bundle outcome filling.",
    )
    parser.add_argument(
        "--event-fade-review-bundle-export-prices",
        action="store_true",
        help=(
            "With review-bundle commands, export a bundle-local outcome price fixture "
            "when --event-fade-review-bundle-prices is not supplied."
        ),
    )
    parser.add_argument(
        "--event-fade-review-bundle-reviewed",
        metavar="REVIEWED_SAMPLE",
        help="Optional prior reviewed sample to merge into review-bundle rows before writing artifacts.",
    )
    parser.add_argument(
        "--event-fade-queue-limit",
        type=int,
        default=20,
        help=(
            "Maximum rows to show for --event-fade-labeling-queue, "
            "--event-fade-review-packet, --event-fade-export-review-template, "
            "or --event-fade-review-bundle."
        ),
    )
    parser.add_argument(
        "--event-fade-merge-sample",
        nargs=3,
        metavar=("FRESH", "REVIEWED", "OUT"),
        help="Merge human review status, labels, and outcomes from REVIEWED into FRESH and write OUT.",
    )
    parser.add_argument(
        "--event-fade-fill-outcomes",
        nargs=3,
        metavar=("SAMPLE", "PRICES", "OUT"),
        help="Fill SHORT_TRIGGERED validation outcome fields from local price fixture PRICES and write OUT.",
    )
    parser.add_argument(
        "--event-fade-overwrite-outcomes",
        action="store_true",
        help="With --event-fade-fill-outcomes, replace existing outcome fields instead of only filling blanks.",
    )
    parser.add_argument(
        "--event-fade-export-outcome-prices",
        nargs=2,
        metavar=("SAMPLE", "OUT"),
        help="Export local OHLCV price fixture for SHORT_TRIGGERED validation sample rows.",
    )
    parser.add_argument(
        "--event-fade-price-days",
        type=int,
        default=None,
        help="Days of daily kline history for --event-fade-export-outcome-prices; auto-sized when omitted.",
    )
    parser.add_argument(
        "--event-fade-price-fixture-dir",
        default=None,
        help="Offline Binance-style kline fixture directory for --event-fade-export-outcome-prices.",
    )
    parser.add_argument(
        "--event-fade-price-interval",
        choices=("1d", "1h"),
        default="1d",
        help="Kline interval for --event-fade-export-outcome-prices.",
    )
    parser.add_argument(
        "--event-fade-refresh-price-cache",
        action="store_true",
        help="Refetch Binance klines for --event-fade-export-outcome-prices instead of using cache.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON for commands that support it.",
    )
    parser.add_argument(
        "--cohorts",
        action="store_true",
        help="For --score, include live paper-trade cohort breakdowns.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print operational scan/listener health and exit.",
    )
    parser.add_argument(
        "--backup-db",
        action="store_true",
        help="Create and verify a safe SQLite backup, then prune old backups.",
    )
    parser.add_argument(
        "--verify-restore",
        nargs="?",
        const="",
        metavar="BACKUP",
        help="Restore-check a backup path, or the newest retained backup when omitted.",
    )
    parser.add_argument(
        "--maintenance",
        action="store_true",
        help="Run DB backup, restore drill, and log rotation.",
    )
    parser.add_argument(
        "--rotate-logs",
        action="store_true",
        help="Rotate oversized local scan/listener logs and prune old rotations.",
    )
    parser.add_argument(
        "--launchd-status",
        action="store_true",
        help="Print launchd status for the scan and bot agents.",
    )
    parser.add_argument(
        "--install-maintenance-agent",
        action="store_true",
        help="Install/load the daily launchd maintenance agent for this checkout.",
    )
    parser.add_argument(
        "--restart-listener",
        action="store_true",
        help="Restart the always-on bot listener launchd agent.",
    )
    parser.add_argument(
        "--universe-audit",
        action="store_true",
        help="Print the most recent universe hygiene audit.",
    )
    parser.add_argument(
        "--refresh-universe-audit",
        action="store_true",
        help="Fetch, persist, and print a fresh universe hygiene audit without a full RSI scan.",
    )
    parser.add_argument(
        "--listen",
        action="store_true",
        help="Run the bot listener loop so commands (/top, /detail, /stats) "
             "are answered in real time. Runs until stopped.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging.")
    args = parser.parse_args()

    if args.report:
        report()
        return
    if args.score:
        score(json_output=args.json, cohorts=args.cohorts)
        return
    if args.refresh_paper:
        refresh_paper(verbose=args.verbose, json_output=args.json, cohorts=args.cohorts)
        return
    if args.event_fade_report:
        event_fade_report(verbose=args.verbose)
        return
    if args.event_discovery_report:
        event_discovery_report(verbose=args.verbose)
        return
    if args.event_discovery_refresh:
        event_discovery_refresh(verbose=args.verbose)
        return
    if args.event_discovery_status:
        event_discovery_status(json_output=args.json)
        return
    if args.event_discovery_runs:
        event_discovery_runs(limit=args.event_discovery_run_limit, json_output=args.json)
        return
    if args.event_discovery_binance_listen:
        event_discovery_binance_listen(verbose=args.verbose)
        return
    if args.event_fade_auto_report:
        event_fade_auto_report(verbose=args.verbose)
        return
    if args.event_fade_export_sample:
        event_fade_export_sample(args.event_fade_export_sample, verbose=args.verbose)
        return
    if args.event_fade_export_cache_sample:
        event_fade_export_cache_sample(args.event_fade_export_cache_sample, verbose=args.verbose)
        return
    if args.event_fade_review_sample:
        event_fade_review_sample(args.event_fade_review_sample, verbose=args.verbose)
        return
    if args.event_fade_labeling_queue:
        event_fade_labeling_queue(
            args.event_fade_labeling_queue,
            limit=args.event_fade_queue_limit,
            verbose=args.verbose,
        )
        return
    if args.event_fade_review_packet:
        sample_path, out_path = args.event_fade_review_packet
        event_fade_review_packet(
            sample_path,
            out_path,
            limit=args.event_fade_queue_limit,
            verbose=args.verbose,
        )
        return
    if args.event_fade_export_review_template:
        sample_path, out_path = args.event_fade_export_review_template
        event_fade_export_review_template(
            sample_path,
            out_path,
            limit=args.event_fade_queue_limit,
            verbose=args.verbose,
        )
        return
    if args.event_fade_apply_review_template:
        sample_path, template_path, out_path = args.event_fade_apply_review_template
        event_fade_apply_review_template(
            sample_path,
            template_path,
            out_path,
            verbose=args.verbose,
        )
        return
    if args.event_fade_review_bundle:
        sample_path, out_dir = args.event_fade_review_bundle
        event_fade_review_bundle(
            sample_path,
            out_dir,
            limit=args.event_fade_queue_limit,
            prices_path=args.event_fade_review_bundle_prices,
            auto_export_prices=args.event_fade_review_bundle_export_prices,
            price_days=args.event_fade_price_days,
            price_fixture_dir=args.event_fade_price_fixture_dir,
            price_interval=args.event_fade_price_interval,
            refresh_price_cache=args.event_fade_refresh_price_cache,
            reviewed_path=args.event_fade_review_bundle_reviewed,
            overwrite_outcomes=args.event_fade_overwrite_outcomes,
            verbose=args.verbose,
        )
        return
    if args.event_fade_cache_review_bundle:
        event_fade_cache_review_bundle(
            args.event_fade_cache_review_bundle,
            limit=args.event_fade_queue_limit,
            prices_path=args.event_fade_review_bundle_prices,
            auto_export_prices=args.event_fade_review_bundle_export_prices,
            price_days=args.event_fade_price_days,
            price_fixture_dir=args.event_fade_price_fixture_dir,
            price_interval=args.event_fade_price_interval,
            refresh_price_cache=args.event_fade_refresh_price_cache,
            reviewed_path=args.event_fade_review_bundle_reviewed,
            overwrite_outcomes=args.event_fade_overwrite_outcomes,
            verbose=args.verbose,
        )
        return
    if args.event_fade_merge_sample:
        fresh_path, reviewed_path, out_path = args.event_fade_merge_sample
        event_fade_merge_sample(fresh_path, reviewed_path, out_path, verbose=args.verbose)
        return
    if args.event_fade_fill_outcomes:
        sample_path, prices_path, out_path = args.event_fade_fill_outcomes
        event_fade_fill_outcomes(
            sample_path,
            prices_path,
            out_path,
            overwrite=args.event_fade_overwrite_outcomes,
            verbose=args.verbose,
        )
        return
    if args.event_fade_export_outcome_prices:
        sample_path, out_path = args.event_fade_export_outcome_prices
        event_fade_export_outcome_prices(
            sample_path,
            out_path,
            days=args.event_fade_price_days,
            fixture_dir=args.event_fade_price_fixture_dir,
            interval=args.event_fade_price_interval,
            refresh_cache=args.event_fade_refresh_price_cache,
            verbose=args.verbose,
        )
        return
    if args.status:
        status()
        return
    if args.backup_db:
        backup_db()
        return
    if args.verify_restore is not None:
        verify_restore(args.verify_restore or None)
        return
    if args.maintenance:
        maintenance()
        return
    if args.rotate_logs:
        rotate_logs()
        return
    if args.launchd_status:
        launchd_status()
        return
    if args.install_maintenance_agent:
        install_maintenance_agent()
        return
    if args.restart_listener:
        restart_listener()
        return
    if args.universe_audit:
        universe_audit()
        return
    if args.refresh_universe_audit:
        refresh_universe_audit(top_n=args.top_n, verbose=args.verbose)
        return
    if args.listen:
        logging.basicConfig(
            level=logging.DEBUG if args.verbose else logging.INFO,
            format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        config.validate()
        telegram.listen()
        return
    run(top_n=args.top_n, dry_run=args.dry_run, verbose=args.verbose)
