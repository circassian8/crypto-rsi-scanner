from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import sys
from collections.abc import Callable, Iterable
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

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
from .notifications import notify_all, send_telegram, send_telegram_structured
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
from . import event_alerts
from . import event_alpha_artifact_doctor
from . import event_alpha_artifacts
from . import event_alpha_alert_store
from . import event_alpha_burn_in
from . import event_alpha_burn_in_readiness
from . import event_alpha_burn_in_pack
from . import event_alpha_calibration
from . import event_alpha_daily_brief
from . import event_alpha_eval_export
from . import event_alpha_explain
from . import event_alpha_feedback_readiness
from . import event_alpha_health_guard
from . import event_alpha_cryptopanic
from . import event_impact_hypothesis_store
from . import event_incident_store
from . import event_alpha_missed
from . import event_alpha_notifications
from . import event_alpha_notification_checklist
from . import event_alpha_notification_delivery
from . import event_alpha_notification_go_no_go
from . import event_alpha_notification_inbox
from . import event_alpha_notification_pack
from . import event_alpha_notification_pause
from . import event_alpha_notification_runs
from . import event_alpha_notification_sender
from . import event_alpha_notification_slo
from . import event_alpha_pipeline
from . import event_alpha_preflight
from . import event_alpha_priors
from . import event_alpha_profiles
from . import event_alpha_replay
from . import event_alpha_retention
from . import event_alpha_run_ledger
from . import event_alpha_run_lock
from . import event_alpha_router
from . import event_alpha_policy_simulator
from . import event_alpha_quality_review
from . import event_alpha_quality_coverage
from . import event_alpha_send_readiness
from . import event_alpha_signal_quality
from . import event_alpha_signal_quality_export
from . import event_alpha_source_coverage
from . import event_alpha_scheduler
from . import event_alpha_telegram_final_check
from . import event_alpha_tuning
from . import event_alpha_telegram_recipient_check
from . import event_alpha_v1_readiness
from . import event_alpha_environment_doctor
from . import event_source_reliability
from . import event_catalyst_search
from . import event_clock
from . import event_core_opportunity_store
from . import event_evidence_acquisition
from . import event_feedback
from . import event_llm_analyzer
from . import event_llm_catalyst_frames
from . import event_llm_extractor
from . import event_near_miss
from . import event_opportunity_audit
from . import event_provider_health
from . import event_provider_status
from . import event_price_history
from . import event_research_cards
from . import event_source_enrichment
from . import event_validation
from . import event_watchlist
from . import event_watchlist_enrichment
from . import event_watchlist_market
from . import event_watchlist_monitor
from .event_models import EventDiscoveryResult, NormalizedEvent, RawDiscoveredEvent
from .event_providers.binance_announcements import BinanceAnnouncementProvider
from .event_providers.bybit_announcements import BybitAnnouncementProvider
from .event_providers.coinmarketcal import CoinMarketCalProvider
from .event_providers.tokenomist import TokenomistProvider
from .llm_providers.fixture import (
    FixtureLLMCatalystFrameProvider,
    FixtureLLMExtractionProvider,
    FixtureLLMRelationshipProvider,
)
from .llm_providers.openai_provider import OpenAILLMExtractionProvider, OpenAILLMRelationshipProvider

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


def event_fade_report(verbose: bool = False, event_now: str | datetime | None = None) -> None:
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
    now = _event_research_now(event_now)
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


def _event_research_now(override: str | datetime | None = None) -> datetime:
    return event_research_now_from_config(override=override)


def event_research_now_from_config(override: str | datetime | None = None) -> datetime:
    """Return the configured event research clock, honoring an explicit override."""
    try:
        return event_clock.event_research_now(config.EVENT_RESEARCH_NOW, override=override)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


def _event_clock_status(override: str | datetime | None = None) -> dict[str, object]:
    try:
        return event_clock.event_clock_status(config.EVENT_RESEARCH_NOW, override=override)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


def _event_alpha_clock_line(status: dict[str, object]) -> str:
    age = status.get("fixed_clock_age_hours")
    age_text = "n/a" if age is None else f"{float(age):.2f}h"
    return (
        "clock: "
        f"mode={status.get('clock_mode') or 'unknown'} "
        f"research_now={status.get('research_now') or 'unknown'} "
        f"wall_clock_now={status.get('wall_clock_now') or 'unknown'} "
        f"fixed_clock_age={age_text}"
    )


def _event_alpha_notify_clock_warnings(status: dict[str, object]) -> tuple[str, ...]:
    if status.get("clock_mode") != "fixed":
        return ()
    warnings = [str(item) for item in status.get("warnings", ()) or () if str(item)]
    warnings.append("fixed research clock active for notification profile")
    return tuple(dict.fromkeys(warnings))


def _event_alpha_notify_fixed_clock_blocker(status: dict[str, object]) -> str | None:
    if bool(getattr(config, "EVENT_ALPHA_ALLOW_FIXED_NOW_FOR_NOTIFY", False)):
        return None
    blocker = event_clock.fixed_clock_notification_blocker(status)
    if not blocker:
        return None
    return f"fixed research clock blocks notification send: {blocker}"


def _event_discovery_result_from_config(
    now: datetime | None = None,
    *,
    raw_event_transform: Callable[[tuple[RawDiscoveredEvent]], Iterable[RawDiscoveredEvent]] | None = None,
) -> event_discovery.EventDiscoveryResult:
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
        project_blog_rss_fail_fast_on_error=(
            config.EVENT_ALPHA_NOTIFY_FAST_FAIL_ON_DNS
            and str(config.EVENT_ALPHA_RUN_MODE or "") == "notification_burn_in"
        ),
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
        market_enrichment_enabled=config.EVENT_MARKET_ENRICHMENT_ENABLED,
        market_enrichment_path=config.EVENT_DISCOVERY_UNIVERSE_PATH,
        market_enrichment_live=config.EVENT_DISCOVERY_UNIVERSE_LIVE,
        market_enrichment_fetch_limit=config.EVENT_DISCOVERY_UNIVERSE_FETCH_LIMIT,
        market_enrichment_fail_soft=_event_alpha_notification_mode(),
        anomaly_scanner_enabled=config.EVENT_ANOMALY_SCANNER_ENABLED,
        anomaly_min_return_24h=config.EVENT_ANOMALY_MIN_RETURN_24H,
        anomaly_min_volume_mcap=config.EVENT_ANOMALY_MIN_VOLUME_MCAP,
        anomaly_min_volume_zscore=config.EVENT_ANOMALY_MIN_VOLUME_ZSCORE,
        anomaly_max_assets=config.EVENT_ANOMALY_MAX_ASSETS,
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
        now=now,
        raw_event_transform=raw_event_transform,
        provider_health_cfg=_event_provider_health_config_from_runtime(),
    )


def _event_alert_config_from_runtime() -> event_alerts.EventAlertConfig:
    return event_alerts.EventAlertConfig(
        enabled=config.EVENT_ALERTS_ENABLED,
        mode=config.EVENT_ALERT_MODE,
        min_digest_score=config.EVENT_ALERT_MIN_DIGEST_SCORE,
        min_watchlist_score=config.EVENT_ALERT_MIN_WATCHLIST_SCORE,
        min_high_priority_score=config.EVENT_ALERT_MIN_HIGH_PRIORITY_SCORE,
        max_digest_items=config.EVENT_ALERT_MAX_DIGEST_ITEMS,
        max_instant_per_day=config.EVENT_ALERT_MAX_INSTANT_PER_DAY,
        cooldown_hours=config.EVENT_ALERT_COOLDOWN_HOURS,
        allow_proxy_venue=config.EVENT_ALERT_ALLOW_PROXY_VENUE,
    )


def _event_alpha_priors_config_from_runtime() -> event_alpha_priors.EventAlphaPriorsConfig:
    return event_alpha_priors.EventAlphaPriorsConfig(
        enabled=config.EVENT_ALPHA_APPLY_PRIORS,
        path=config.EVENT_ALPHA_PRIORS_PATH,
        min_multiplier=config.EVENT_ALPHA_PRIORS_MIN_MULTIPLIER,
        max_multiplier=config.EVENT_ALPHA_PRIORS_MAX_MULTIPLIER,
    )


def _event_provider_health_config_from_runtime() -> event_provider_health.EventProviderHealthConfig:
    notification_mode = _event_alpha_notification_mode()
    return event_provider_health.EventProviderHealthConfig(
        path=config.EVENT_PROVIDER_HEALTH_PATH,
        max_consecutive_failures=(
            config.EVENT_ALPHA_NOTIFY_MAX_PROVIDER_FAILURES_BEFORE_SKIP
            if notification_mode
            else config.EVENT_PROVIDER_MAX_CONSECUTIVE_FAILURES
        ),
        backoff_minutes=config.EVENT_PROVIDER_BACKOFF_MINUTES,
        fail_fast_on_dns=(
            config.EVENT_ALPHA_NOTIFY_FAST_FAIL_ON_DNS
            if notification_mode
            else config.EVENT_PROVIDER_FAIL_FAST_ON_DNS
        ),
        ignore_backoff=bool(config.EVENT_ALPHA_IGNORE_PROVIDER_BACKOFF),
    )


def _event_alpha_notification_mode() -> bool:
    return str(config.EVENT_ALPHA_RUN_MODE or "") == "notification_burn_in"


def _event_alpha_retention_config_from_runtime() -> event_alpha_retention.EventAlphaRetentionConfig:
    return event_alpha_retention.EventAlphaRetentionConfig(
        runs_path=config.EVENT_ALPHA_RUN_LEDGER_PATH,
        alerts_path=config.EVENT_ALPHA_ALERT_STORE_PATH,
        cards_dir=config.EVENT_RESEARCH_CARDS_DIR,
        run_days=config.EVENT_ALPHA_RETENTION_DAYS_RUNS,
        alert_days=config.EVENT_ALPHA_RETENTION_DAYS_ALERTS,
        card_days=config.EVENT_ALPHA_RETENTION_DAYS_CARDS,
        keep_eval_cases=config.EVENT_ALPHA_RETENTION_KEEP_EVAL_CASES,
    )


def _event_llm_config_from_runtime() -> event_llm_analyzer.EventLLMConfig:
    return event_llm_analyzer.EventLLMConfig(
        enabled=config.EVENT_LLM_ENABLED,
        mode=config.EVENT_LLM_MODE,
        provider=config.EVENT_LLM_PROVIDER,
        model=config.EVENT_LLM_MODEL,
        max_candidates_per_run=config.EVENT_LLM_MAX_CANDIDATES_PER_RUN,
        min_prefilter_score=config.EVENT_LLM_MIN_PREFILTER_SCORE,
        require_evidence_quotes=config.EVENT_LLM_REQUIRE_EVIDENCE_QUOTES,
        cache_path=config.EVENT_LLM_CACHE_PATH,
        prompt_version=config.EVENT_LLM_PROMPT_VERSION,
        max_calls_per_run=config.EVENT_LLM_MAX_CALLS_PER_RUN,
        max_calls_per_day=config.EVENT_LLM_MAX_CALLS_PER_DAY,
        max_estimated_cost_usd_per_day=config.EVENT_LLM_MAX_ESTIMATED_COST_USD_PER_DAY,
        max_parallel_calls=config.EVENT_LLM_MAX_PARALLEL_CALLS,
        cache_ttl_hours=config.EVENT_LLM_CACHE_TTL_HOURS,
        budget_ledger_path=config.EVENT_LLM_BUDGET_LEDGER_PATH,
        estimated_cost_per_call_usd=config.EVENT_LLM_ESTIMATED_COST_PER_CALL_USD,
    )


def _event_llm_extractor_config_from_runtime() -> event_llm_extractor.EventLLMExtractorConfig:
    return event_llm_extractor.EventLLMExtractorConfig(
        enabled=config.EVENT_LLM_EXTRACTOR_ENABLED,
        mode=config.EVENT_LLM_EXTRACTOR_MODE,
        provider=config.EVENT_LLM_EXTRACTOR_PROVIDER,
        model=config.EVENT_LLM_EXTRACTOR_MODEL,
        max_events_per_run=config.EVENT_LLM_EXTRACTOR_MAX_EVENTS_PER_RUN,
        require_evidence_quotes=config.EVENT_LLM_EXTRACTOR_REQUIRE_EVIDENCE_QUOTES,
        cache_path=config.EVENT_LLM_EXTRACTOR_CACHE_PATH,
        prompt_version=config.EVENT_LLM_EXTRACTOR_PROMPT_VERSION,
        max_calls_per_run=config.EVENT_LLM_MAX_CALLS_PER_RUN,
        max_calls_per_day=config.EVENT_LLM_MAX_CALLS_PER_DAY,
        max_estimated_cost_usd_per_day=config.EVENT_LLM_MAX_ESTIMATED_COST_USD_PER_DAY,
        max_parallel_calls=config.EVENT_LLM_MAX_PARALLEL_CALLS,
        cache_ttl_hours=config.EVENT_LLM_CACHE_TTL_HOURS,
        budget_ledger_path=config.EVENT_LLM_BUDGET_LEDGER_PATH,
        estimated_cost_per_call_usd=config.EVENT_LLM_ESTIMATED_COST_PER_CALL_USD,
    )


def _event_llm_catalyst_frame_config_from_runtime() -> event_llm_catalyst_frames.EventLLMCatalystFrameConfig:
    return event_llm_catalyst_frames.EventLLMCatalystFrameConfig(
        enabled=config.EVENT_LLM_CATALYST_FRAMES_ENABLED,
        provider=config.EVENT_LLM_CATALYST_FRAMES_PROVIDER,
        model=config.EVENT_LLM_CATALYST_FRAMES_MODEL,
        max_rows_per_run=config.EVENT_LLM_CATALYST_FRAMES_MAX_ROWS_PER_RUN,
        min_source_score=config.EVENT_LLM_CATALYST_FRAMES_MIN_SOURCE_SCORE,
        use_enriched_text=config.EVENT_LLM_CATALYST_FRAMES_USE_ENRICHED_TEXT,
        only_ambiguous=config.EVENT_LLM_CATALYST_FRAMES_ONLY_AMBIGUOUS,
        prompt_version=config.EVENT_LLM_CATALYST_FRAMES_PROMPT_VERSION,
    )


def _event_impact_hypothesis_store_config_from_runtime() -> event_impact_hypothesis_store.EventImpactHypothesisStoreConfig:
    return event_impact_hypothesis_store.EventImpactHypothesisStoreConfig(
        path=config.EVENT_IMPACT_HYPOTHESIS_STORE_PATH,
    )


def _event_incident_store_config_from_runtime() -> event_incident_store.EventIncidentStoreConfig:
    return event_incident_store.EventIncidentStoreConfig(
        path=config.EVENT_INCIDENT_STORE_PATH,
        store_diagnostic=config.EVENT_INCIDENT_STORE_DIAGNOSTIC,
        store_raw_observations=config.EVENT_INCIDENT_STORE_RAW_OBSERVATIONS,
    )


def _event_watchlist_config_from_runtime() -> event_watchlist.EventWatchlistConfig:
    return event_watchlist.EventWatchlistConfig(
        enabled=config.EVENT_WATCHLIST_ENABLED,
        state_path=config.EVENT_WATCHLIST_STATE_PATH,
        expire_hours_after_event=config.EVENT_WATCHLIST_EXPIRE_HOURS_AFTER_EVENT,
    )


def _event_watchlist_monitor_market_rows_from_runtime() -> list[dict[str, Any]]:
    if str(config.EVENT_WATCHLIST_MONITOR_MARKET_SOURCE or "").lower() in {"cycle", "none", "off"}:
        return []
    market_path = config.EVENT_WATCHLIST_MONITOR_MARKET_PATH or config.EVENT_DISCOVERY_UNIVERSE_PATH
    return event_watchlist_market.load_market_rows(market_path)


def _event_watchlist_monitor_derivatives_rows_from_runtime() -> list[dict[str, Any]]:
    source = str(config.EVENT_WATCHLIST_MONITOR_DERIVATIVES_SOURCE or "").strip().lower()
    if source in {"cycle", "none", "off", "disabled"}:
        return []
    return event_watchlist_enrichment.load_enrichment_rows(config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH)


def _event_watchlist_monitor_supply_rows_from_runtime() -> list[dict[str, Any]]:
    source = str(config.EVENT_WATCHLIST_MONITOR_SUPPLY_SOURCE or "").strip().lower()
    if source in {"cycle", "none", "off", "disabled"}:
        return []
    rows: list[dict[str, Any]] = []
    for path in (
        config.EVENT_DISCOVERY_TOKENOMIST_SUPPLY_PATH,
        config.EVENT_DISCOVERY_ETHERSCAN_SUPPLY_PATH,
        config.EVENT_DISCOVERY_ARKHAM_SUPPLY_PATH,
        config.EVENT_DISCOVERY_DUNE_SUPPLY_PATH,
    ):
        rows.extend(event_watchlist_enrichment.load_enrichment_rows(path))
    return rows


def _event_watchlist_market_provider_from_runtime() -> event_watchlist_market.EventWatchlistMarketProvider | None:
    source = str(config.EVENT_WATCHLIST_MONITOR_MARKET_SOURCE or "").strip().lower()
    if source != "coingecko":
        return None
    return event_watchlist_market.CoinGeckoWatchlistMarketProvider(
        live_enabled=bool(config.EVENT_WATCHLIST_MONITOR_TARGETED_LOOKUP and config.EVENT_DISCOVERY_UNIVERSE_LIVE),
        cache_ttl_seconds=config.EVENT_WATCHLIST_MONITOR_MARKET_CACHE_TTL_SECONDS,
        provider_health_cfg=_event_provider_health_config_from_runtime() if _event_alpha_notification_mode() else None,
    )


def _event_watchlist_monitor_result_from_runtime(
    read_result: event_watchlist.EventWatchlistReadResult,
    *,
    now: datetime | None = None,
) -> event_watchlist_monitor.EventWatchlistMonitorResult:
    observed = _event_research_now(now)
    fixture_rows = _event_watchlist_monitor_market_rows_from_runtime()
    market_source = event_watchlist_market.market_rows_for_watchlist(
        read_result,
        source=config.EVENT_WATCHLIST_MONITOR_MARKET_SOURCE,
        fixture_rows=fixture_rows,
        cycle_rows=fixture_rows,
        targeted_lookup=config.EVENT_WATCHLIST_MONITOR_TARGETED_LOOKUP,
        targeted_provider=_event_watchlist_market_provider_from_runtime(),
        max_assets=config.EVENT_WATCHLIST_MONITOR_MAX_ASSETS,
        cache_ttl_seconds=config.EVENT_WATCHLIST_MONITOR_MARKET_CACHE_TTL_SECONDS,
        now=observed,
    )
    enrichment = event_watchlist_enrichment.enrichment_for_watchlist(
        read_result,
        derivatives_source=config.EVENT_WATCHLIST_MONITOR_DERIVATIVES_SOURCE,
        supply_source=config.EVENT_WATCHLIST_MONITOR_SUPPLY_SOURCE,
        derivatives_rows=_event_watchlist_monitor_derivatives_rows_from_runtime(),
        supply_rows=_event_watchlist_monitor_supply_rows_from_runtime(),
        max_assets=config.EVENT_WATCHLIST_MONITOR_ENRICHMENT_MAX_ASSETS,
    )
    return event_watchlist_monitor.monitor_watchlist(
        read_result,
        market_rows=market_source.rows,
        derivatives_by_asset=enrichment.derivatives,
        supply_by_asset=enrichment.supply,
        now=observed,
    )


def _event_alpha_router_config_from_runtime() -> event_alpha_router.EventAlphaRouterConfig:
    return event_alpha_router.EventAlphaRouterConfig(
        enabled=config.EVENT_ALPHA_ROUTER_ENABLED,
        daily_digest_enabled=config.EVENT_ALPHA_ROUTER_DAILY_DIGEST_ENABLED,
        instant_enabled=config.EVENT_ALPHA_ROUTER_INSTANT_ENABLED,
        max_digest_items=config.EVENT_ALPHA_ROUTER_MAX_DIGEST_ITEMS,
        validated_hypothesis_digest_enabled=config.EVENT_ALPHA_VALIDATED_HYPOTHESIS_DIGEST_ENABLED,
        max_validated_hypothesis_digest_items=config.EVENT_ALPHA_VALIDATED_HYPOTHESIS_MAX_ITEMS,
        validated_hypothesis_min_score=config.EVENT_ALPHA_VALIDATED_HYPOTHESIS_DIGEST_MIN_SCORE,
        validated_hypothesis_min_opportunity_score=config.EVENT_ALPHA_VALIDATED_HYPOTHESIS_MIN_OPPORTUNITY_SCORE,
        validated_hypothesis_min_final_score=config.EVENT_ALPHA_VALIDATED_HYPOTHESIS_MIN_FINAL_SCORE,
        validated_hypothesis_require_external_or_direct_event=(
            config.EVENT_ALPHA_VALIDATED_HYPOTHESIS_REQUIRE_EXTERNAL_OR_DIRECT_EVENT
        ),
        validated_hypothesis_require_impact_path=config.EVENT_ALPHA_VALIDATED_HYPOTHESIS_REQUIRE_IMPACT_PATH,
        weak_validated_local_only=config.EVENT_ALPHA_WEAK_VALIDATED_LOCAL_ONLY,
        allow_weak_path_with_market_confirmation=config.EVENT_ALPHA_ALLOW_WEAK_PATH_WITH_MARKET_CONFIRMATION,
        block_generic_cooccurrence_digest=config.EVENT_ALPHA_BLOCK_GENERIC_COOCCURRENCE_DIGEST,
        max_high_priority_per_day=config.EVENT_ALPHA_ROUTER_MAX_HIGH_PRIORITY_PER_DAY,
        per_key_cooldown_hours=config.EVENT_ALPHA_ROUTER_PER_KEY_COOLDOWN_HOURS,
        alert_on_score_jump=config.EVENT_ALPHA_ROUTER_ALERT_ON_SCORE_JUMP,
        score_jump_threshold=config.EVENT_ALPHA_ROUTER_SCORE_JUMP_THRESHOLD,
        alert_on_new_independent_source=config.EVENT_ALPHA_ROUTER_ALERT_ON_NEW_INDEPENDENT_SOURCE,
        alert_on_event_time_upgrade=config.EVENT_ALPHA_ROUTER_ALERT_ON_EVENT_TIME_UPGRADE,
        alert_on_derivatives_crowding_upgrade=config.EVENT_ALPHA_ROUTER_ALERT_ON_DERIVATIVES_CROWDING_UPGRADE,
        alert_on_cluster_confidence_upgrade=config.EVENT_ALPHA_ROUTER_ALERT_ON_CLUSTER_CONFIDENCE_UPGRADE,
    )


def _event_near_miss_config_from_runtime() -> event_near_miss.EventNearMissConfig:
    return event_near_miss.EventNearMissConfig(
        enabled=True,
        near_threshold_points=config.EVENT_ALPHA_NEAR_MISS_THRESHOLD_POINTS,
        digest_threshold=config.EVENT_ALPHA_VALIDATED_HYPOTHESIS_MIN_FINAL_SCORE,
        watchlist_threshold=78.0,
        max_candidates=config.EVENT_ALPHA_NEAR_MISS_MARKET_REFRESH_MAX_ASSETS,
        market_refresh_enabled=config.EVENT_ALPHA_NEAR_MISS_MARKET_REFRESH_ENABLED,
        max_market_refresh_assets=config.EVENT_ALPHA_NEAR_MISS_MARKET_REFRESH_MAX_ASSETS,
        market_refresh_timeout_seconds=config.EVENT_ALPHA_NEAR_MISS_MARKET_REFRESH_TIMEOUT_SECONDS,
    )


def _event_alpha_notification_config_from_runtime(
    profile_name: str | None = None,
) -> event_alpha_notifications.EventAlphaNotificationConfig:
    return event_alpha_notifications.EventAlphaNotificationConfig(
        enabled=config.EVENT_ALERTS_ENABLED,
        mode=config.EVENT_ALERT_MODE,
        notification_scope=config.EVENT_ALPHA_NOTIFY_SCOPE,
        profile_name=profile_name,
        artifact_namespace=config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
        daily_digest_cooldown_hours=config.EVENT_ALPHA_NOTIFY_DAILY_DIGEST_COOLDOWN_HOURS,
        instant_escalation_cooldown_hours=config.EVENT_ALPHA_NOTIFY_INSTANT_COOLDOWN_HOURS,
        max_instant_per_day=config.EVENT_ALPHA_NOTIFY_MAX_INSTANT_PER_DAY,
        health_heartbeat_enabled=config.EVENT_ALPHA_NOTIFY_HEALTH_HEARTBEAT_ENABLED,
        health_heartbeat_cooldown_hours=config.EVENT_ALPHA_NOTIFY_HEALTH_HEARTBEAT_COOLDOWN_HOURS,
        exploratory_digest_enabled=config.EVENT_ALPHA_EXPLORATORY_DIGEST_ENABLED,
        exploratory_digest_max_items=config.EVENT_ALPHA_EXPLORATORY_DIGEST_MAX_ITEMS,
        exploratory_digest_min_score=config.EVENT_ALPHA_EXPLORATORY_DIGEST_MIN_SCORE,
        exploratory_digest_cooldown_hours=config.EVENT_ALPHA_EXPLORATORY_DIGEST_COOLDOWN_HOURS,
        exploratory_digest_include_rejection_reasons=config.EVENT_ALPHA_EXPLORATORY_DIGEST_INCLUDE_REJECTION_REASONS,
        exploratory_digest_include_raw_evidence=config.EVENT_ALPHA_EXPLORATORY_DIGEST_INCLUDE_RAW_EVIDENCE,
        exploratory_digest_include_controls=config.EVENT_ALPHA_EXPLORATORY_DIGEST_INCLUDE_CONTROLS,
        research_review_digest_enabled=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_ENABLED,
        research_review_digest_max_items=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_MAX_ITEMS,
        research_review_digest_min_score=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_MIN_SCORE,
        research_review_digest_cooldown_hours=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_COOLDOWN_HOURS,
        research_review_digest_include_local_only=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_INCLUDE_LOCAL_ONLY,
        research_review_digest_include_sector=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_INCLUDE_SECTOR,
        research_review_digest_send_with_alerts=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_SEND_WITH_ALERTS,
        quality_mode=config.EVENT_ALPHA_NOTIFICATION_QUALITY_MODE,
    )


def _event_catalyst_search_config_from_runtime(
    *,
    enabled_override: bool | None = None,
) -> event_catalyst_search.EventCatalystSearchConfig:
    return event_catalyst_search.EventCatalystSearchConfig(
        enabled=config.EVENT_CATALYST_SEARCH_ENABLED if enabled_override is None else enabled_override,
        provider=config.EVENT_CATALYST_SEARCH_PROVIDER,
        providers=tuple(config.EVENT_CATALYST_SEARCH_PROVIDERS),
        max_anomalies=config.EVENT_CATALYST_SEARCH_MAX_ANOMALIES,
        max_queries_per_anomaly=config.EVENT_CATALYST_SEARCH_MAX_QUERIES_PER_ANOMALY,
        max_results_per_query=config.EVENT_CATALYST_SEARCH_MAX_RESULTS_PER_QUERY,
        min_anomaly_score=config.EVENT_CATALYST_SEARCH_MIN_ANOMALY_SCORE,
        require_live_source=config.EVENT_CATALYST_SEARCH_REQUIRE_LIVE_SOURCE,
        min_result_confidence=config.EVENT_CATALYST_SEARCH_MIN_RESULT_CONFIDENCE,
    )


def _event_impact_hypothesis_search_config_from_runtime(
    *,
    enabled_override: bool | None = None,
) -> event_catalyst_search.EventImpactHypothesisSearchConfig:
    return event_catalyst_search.EventImpactHypothesisSearchConfig(
        enabled=config.EVENT_IMPACT_HYPOTHESIS_SEARCH_ENABLED if enabled_override is None else enabled_override,
        max_hypotheses=config.EVENT_IMPACT_HYPOTHESIS_MAX_HYPOTHESES,
        max_queries_per_hypothesis=config.EVENT_IMPACT_HYPOTHESIS_MAX_QUERIES_PER_HYPOTHESIS,
        max_results_per_query=config.EVENT_CATALYST_SEARCH_MAX_RESULTS_PER_QUERY,
        min_confidence=config.EVENT_IMPACT_HYPOTHESIS_MIN_CONFIDENCE,
        min_result_confidence=config.EVENT_IMPACT_HYPOTHESIS_MIN_RESULT_CONFIDENCE,
        require_validated_identity=config.EVENT_IMPACT_HYPOTHESIS_REQUIRE_VALIDATED_IDENTITY,
        candidate_discovery_enabled=config.EVENT_IMPACT_HYPOTHESIS_CANDIDATE_DISCOVERY_ENABLED,
        max_candidate_discovery_queries=config.EVENT_IMPACT_HYPOTHESIS_MAX_DISCOVERY_QUERIES,
        max_candidate_discovery_results=config.EVENT_IMPACT_HYPOTHESIS_MAX_DISCOVERY_RESULTS,
    )


def _event_evidence_acquisition_config_from_runtime() -> event_evidence_acquisition.EvidenceAcquisitionConfig:
    return event_evidence_acquisition.EvidenceAcquisitionConfig(
        enabled=config.EVENT_ALPHA_EVIDENCE_ACQUISITION_ENABLED,
        max_candidates=config.EVENT_ALPHA_EVIDENCE_ACQUISITION_MAX_CANDIDATES,
        max_queries=config.EVENT_ALPHA_EVIDENCE_ACQUISITION_MAX_QUERIES,
        max_results_per_query=config.EVENT_CATALYST_SEARCH_MAX_RESULTS_PER_QUERY,
        timeout_seconds=config.EVENT_ALPHA_EVIDENCE_ACQUISITION_TIMEOUT_SECONDS,
        fixture_only=config.EVENT_ALPHA_EVIDENCE_ACQUISITION_FIXTURE_ONLY,
        artifact_path=config.EVENT_ALPHA_EVIDENCE_ACQUISITION_PATH,
    )


def _event_source_enrichment_config_from_runtime() -> event_source_enrichment.EventSourceEnrichmentConfig:
    return event_source_enrichment.EventSourceEnrichmentConfig(
        enabled=config.EVENT_SOURCE_ENRICHMENT_ENABLED,
        cache_dir=config.EVENT_SOURCE_ENRICHMENT_CACHE_DIR,
        timeout_seconds=config.EVENT_SOURCE_ENRICHMENT_TIMEOUT_SECONDS,
        max_chars=config.EVENT_SOURCE_ENRICHMENT_MAX_CHARS,
        max_rows_per_run=config.EVENT_SOURCE_ENRICHMENT_MAX_ROWS_PER_RUN,
        min_source_confidence=config.EVENT_SOURCE_ENRICHMENT_MIN_SOURCE_CONFIDENCE,
    )


def _event_feedback_config_from_runtime(path: str | None = None) -> event_feedback.EventFeedbackConfig:
    feedback_path = Path(path).expanduser() if path else config.EVENT_ALPHA_FEEDBACK_PATH
    if not feedback_path.is_absolute():
        feedback_path = config.DATA_DIR / feedback_path
    return event_feedback.EventFeedbackConfig(path=feedback_path)


def _event_alpha_alert_store_config_from_runtime(
    path: str | None = None,
) -> event_alpha_alert_store.EventAlphaAlertStoreConfig:
    alert_path = Path(path).expanduser() if path else config.EVENT_ALPHA_ALERT_STORE_PATH
    if not alert_path.is_absolute():
        alert_path = config.DATA_DIR / alert_path
    return event_alpha_alert_store.EventAlphaAlertStoreConfig(
        path=alert_path,
        snapshot_policy=config.EVENT_ALPHA_SNAPSHOT_POLICY,
        sampled_controls_limit=config.EVENT_ALPHA_SNAPSHOT_SAMPLED_CONTROLS,
    )


def _event_core_opportunity_store_config_from_runtime(
    path: str | None = None,
) -> event_core_opportunity_store.EventCoreOpportunityStoreConfig:
    core_path = Path(path).expanduser() if path else Path(getattr(config, "EVENT_CORE_OPPORTUNITY_STORE_PATH", config.EVENT_DISCOVERY_CACHE_DIR / "event_core_opportunities.jsonl"))
    if not core_path.is_absolute():
        core_path = config.DATA_DIR / core_path
    return event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=core_path)


def _event_alpha_run_ledger_config_from_runtime(path: str | None = None) -> event_alpha_run_ledger.EventAlphaRunLedgerConfig:
    ledger_path = Path(path).expanduser() if path else config.EVENT_ALPHA_RUN_LEDGER_PATH
    if not ledger_path.is_absolute():
        ledger_path = config.DATA_DIR / ledger_path
    return event_alpha_run_ledger.EventAlphaRunLedgerConfig(path=ledger_path)


def _event_alpha_notification_runs_config_from_runtime(
    path: str | None = None,
) -> event_alpha_notification_runs.EventAlphaNotificationRunsConfig:
    summary_path = Path(path).expanduser() if path else config.EVENT_ALPHA_NOTIFICATION_RUNS_PATH
    if not summary_path.is_absolute():
        summary_path = config.DATA_DIR / summary_path
    return event_alpha_notification_runs.EventAlphaNotificationRunsConfig(path=summary_path)


def _event_alpha_run_lock_config_from_runtime() -> event_alpha_run_lock.EventAlphaRunLockConfig:
    return event_alpha_run_lock.EventAlphaRunLockConfig(
        enabled=config.EVENT_ALPHA_NOTIFY_LOCK_ENABLED,
        stale_minutes=config.EVENT_ALPHA_NOTIFY_LOCK_STALE_MINUTES,
        allow_overlap=config.EVENT_ALPHA_NOTIFY_ALLOW_OVERLAP,
    )


def _event_alpha_notify_context_from_runtime(
    profile_name: str | None,
) -> event_alpha_artifacts.EventAlphaArtifactContext:
    """Resolve the artifact context (namespace dir) for lock/delivery paths."""
    return event_alpha_artifacts.context_from_profile(
        profile_name,
        run_mode=config.EVENT_ALPHA_RUN_MODE or None,
        base_dir=config.EVENT_ALPHA_ARTIFACT_BASE_DIR,
        artifact_namespace=config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
    )


def _event_alpha_notification_delivery_config_from_runtime(
    context: event_alpha_artifacts.EventAlphaArtifactContext,
) -> event_alpha_notification_delivery.NotificationDeliveryConfig:
    return event_alpha_notification_delivery.config_for_context(
        context,
        dedupe_by_content=config.EVENT_ALPHA_NOTIFICATION_DEDUPE_BY_CONTENT,
        dedupe_window_hours=config.EVENT_ALPHA_NOTIFICATION_DEDUPE_WINDOW_HOURS,
        in_flight_grace_minutes=config.EVENT_ALPHA_NOTIFICATION_IN_FLIGHT_GRACE_MINUTES,
        partial_marks_cooldown=config.EVENT_ALPHA_NOTIFICATION_PARTIAL_MARKS_COOLDOWN,
    )


def _event_alpha_notification_pause_state(
    context: event_alpha_artifacts.EventAlphaArtifactContext,
) -> event_alpha_notification_pause.EventAlphaNotificationPauseState:
    return event_alpha_notification_pause.read_pause_state(
        context,
        env_paused=config.EVENT_ALPHA_NOTIFICATIONS_PAUSED,
        env_reason=config.EVENT_ALPHA_NOTIFICATIONS_PAUSE_REASON,
    )


def _apply_event_alpha_profile(profile_name: str | None) -> event_alpha_profiles.EventAlphaProfile | None:
    if not profile_name:
        return None
    profile = event_alpha_profiles.get_profile(profile_name)
    for attr, value in profile.config_overrides.items():
        value = _profile_override_value(attr, value)
        setattr(config, attr, value)
    _apply_event_alpha_artifact_context(profile.name)
    _normalize_profile_paths()
    return profile


_PROFILE_LOCAL_BUDGET_OVERRIDES: dict[str, type] = {
    "EVENT_ALPHA_EVIDENCE_ACQUISITION_MAX_CANDIDATES": int,
    "EVENT_ALPHA_EVIDENCE_ACQUISITION_MAX_QUERIES": int,
    "EVENT_ALPHA_EVIDENCE_ACQUISITION_TIMEOUT_SECONDS": float,
    "EVENT_CATALYST_SEARCH_MAX_ANOMALIES": int,
    "EVENT_CATALYST_SEARCH_MAX_QUERIES_PER_ANOMALY": int,
    "EVENT_CATALYST_SEARCH_MAX_RESULTS_PER_QUERY": int,
    "EVENT_DISCOVERY_CRYPTOPANIC_TIMEOUT": float,
    "EVENT_DISCOVERY_GDELT_TIMEOUT": float,
    "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_TIMEOUT": float,
    "EVENT_DISCOVERY_PROJECT_BLOG_RSS_TIMEOUT": float,
    "EVENT_IMPACT_HYPOTHESIS_MAX_DISCOVERY_QUERIES": int,
    "EVENT_IMPACT_HYPOTHESIS_MAX_DISCOVERY_RESULTS": int,
    "EVENT_IMPACT_HYPOTHESIS_MAX_HYPOTHESES": int,
    "EVENT_IMPACT_HYPOTHESIS_MAX_QUERIES_PER_HYPOTHESIS": int,
    "EVENT_LLM_CATALYST_FRAMES_MAX_ROWS_PER_RUN": int,
    "EVENT_LLM_MAX_CANDIDATES_PER_RUN": int,
    "EVENT_LLM_EXTRACTOR_MAX_EVENTS_PER_RUN": int,
    "EVENT_LLM_MAX_CALLS_PER_RUN": int,
    "EVENT_LLM_MAX_CALLS_PER_DAY": int,
    "EVENT_LLM_MAX_ESTIMATED_COST_USD_PER_DAY": float,
    "EVENT_LLM_ESTIMATED_COST_PER_CALL_USD": float,
    "EVENT_LLM_MAX_PARALLEL_CALLS": int,
    "EVENT_LLM_CACHE_TTL_HOURS": float,
    "EVENT_LLM_OPENAI_TIMEOUT": float,
    "EVENT_LLM_EXTRACTOR_OPENAI_TIMEOUT": float,
    "EVENT_SOURCE_ENRICHMENT_MAX_ROWS_PER_RUN": int,
    "EVENT_SOURCE_ENRICHMENT_TIMEOUT_SECONDS": float,
    "EVENT_ALPHA_NOTIFY_MAX_RUNTIME_SECONDS": float,
}


def _profile_override_value(attr: str, profile_value: Any) -> Any:
    """Let explicit runtime env vars intentionally tune profile caps."""
    caster = _PROFILE_LOCAL_BUDGET_OVERRIDES.get(attr)
    if caster is None:
        return profile_value
    raw = os.getenv(f"RSI_{attr}")
    if raw is None or raw == "":
        return profile_value
    try:
        return caster(raw)
    except (TypeError, ValueError):
        log.warning("Ignoring invalid local Event Alpha LLM budget override %s", f"RSI_{attr}")
        return profile_value


def _apply_event_alpha_context_to_config(context: event_alpha_artifacts.EventAlphaArtifactContext) -> None:
    config.EVENT_ALPHA_RUN_MODE = context.run_mode
    config.EVENT_ALPHA_ARTIFACT_NAMESPACE = context.artifact_namespace
    config.EVENT_ALPHA_ARTIFACT_BASE_DIR = context.base_dir
    config.EVENT_ALPHA_RUN_LEDGER_PATH = context.run_ledger_path
    config.EVENT_ALPHA_ALERT_STORE_PATH = context.alert_store_path
    config.EVENT_ALPHA_NOTIFICATION_RUNS_PATH = context.notification_runs_path
    config.EVENT_WATCHLIST_STATE_PATH = context.watchlist_state_path
    config.EVENT_ALPHA_FEEDBACK_PATH = context.feedback_path
    config.EVENT_ALPHA_MISSED_PATH = context.missed_path
    config.EVENT_ALPHA_PRIORS_PATH = context.priors_path
    config.EVENT_PROVIDER_HEALTH_PATH = context.provider_health_path
    config.EVENT_ALPHA_DAILY_BRIEF_PATH = context.daily_brief_path
    config.EVENT_IMPACT_HYPOTHESIS_STORE_PATH = context.impact_hypothesis_store_path
    config.EVENT_CORE_OPPORTUNITY_STORE_PATH = context.core_opportunity_store_path
    config.EVENT_INCIDENT_STORE_PATH = context.incident_store_path
    config.EVENT_ALPHA_EVIDENCE_ACQUISITION_PATH = context.evidence_acquisition_path
    config.EVENT_ALPHA_PROPOSED_EVAL_CASES_DIR = context.proposed_eval_cases_dir
    config.EVENT_RESEARCH_CARDS_DIR = context.research_cards_dir
    config.EVENT_LLM_BUDGET_LEDGER_PATH = context.llm_budget_ledger_path
    config.EVENT_ALPHA_OUTCOMES_PATH = context.outcomes_path


def _apply_event_alpha_artifact_context(profile_name: str | None = None) -> event_alpha_artifacts.EventAlphaArtifactContext:
    context = event_alpha_artifacts.context_from_profile(
        profile_name,
        run_mode=config.EVENT_ALPHA_RUN_MODE or None,
        base_dir=config.EVENT_ALPHA_ARTIFACT_BASE_DIR,
        artifact_namespace=config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
    )
    _apply_event_alpha_context_to_config(context)
    return context


def resolve_event_alpha_artifact_context_for_report(
    profile_name: str | None,
    artifact_namespace: str | None,
    run_mode: str | None = None,
    include_test_artifacts: bool = False,
) -> event_alpha_artifacts.EventAlphaArtifactContext:
    """Resolve and apply the exact artifact context a report should inspect."""
    if not profile_name and not artifact_namespace and not config.EVENT_ALPHA_ARTIFACT_NAMESPACE:
        base_dir = Path(config.EVENT_ALPHA_ARTIFACT_BASE_DIR).expanduser()
        if not base_dir.is_absolute():
            base_dir = config.DATA_DIR / base_dir
        context = event_alpha_artifacts.EventAlphaArtifactContext(
            profile="default",
            run_mode=run_mode or config.EVENT_ALPHA_RUN_MODE or "legacy",
            artifact_namespace="default",
            base_dir=base_dir,
            namespace_dir=base_dir,
            run_ledger_path=Path(config.EVENT_ALPHA_RUN_LEDGER_PATH),
            alert_store_path=Path(config.EVENT_ALPHA_ALERT_STORE_PATH),
            notification_runs_path=Path(config.EVENT_ALPHA_NOTIFICATION_RUNS_PATH),
            watchlist_state_path=Path(config.EVENT_WATCHLIST_STATE_PATH),
            feedback_path=Path(config.EVENT_ALPHA_FEEDBACK_PATH),
            missed_path=Path(config.EVENT_ALPHA_MISSED_PATH),
            priors_path=Path(config.EVENT_ALPHA_PRIORS_PATH),
            provider_health_path=Path(config.EVENT_PROVIDER_HEALTH_PATH),
            daily_brief_path=Path(config.EVENT_ALPHA_DAILY_BRIEF_PATH),
            impact_hypothesis_store_path=Path(config.EVENT_IMPACT_HYPOTHESIS_STORE_PATH),
            core_opportunity_store_path=Path(getattr(config, "EVENT_CORE_OPPORTUNITY_STORE_PATH", base_dir / "event_core_opportunities.jsonl")),
            incident_store_path=Path(config.EVENT_INCIDENT_STORE_PATH),
            evidence_acquisition_path=Path(config.EVENT_ALPHA_EVIDENCE_ACQUISITION_PATH),
            proposed_eval_cases_dir=Path(config.EVENT_ALPHA_PROPOSED_EVAL_CASES_DIR),
            research_cards_dir=Path(config.EVENT_RESEARCH_CARDS_DIR),
            llm_budget_ledger_path=Path(config.EVENT_LLM_BUDGET_LEDGER_PATH),
            outcomes_path=Path(getattr(config, "EVENT_ALPHA_OUTCOMES_PATH", base_dir / "event_alpha_outcomes.jsonl")),
        )
        _apply_event_alpha_context_to_config(context)
        _normalize_profile_paths()
        return context
    profile = _apply_event_alpha_profile(profile_name) if profile_name else None
    selected_profile = profile.name if profile else profile_name
    selected_namespace = artifact_namespace or (None if selected_profile else config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None)
    context = event_alpha_artifacts.context_from_profile(
        selected_profile,
        run_mode=run_mode or config.EVENT_ALPHA_RUN_MODE or None,
        base_dir=config.EVENT_ALPHA_ARTIFACT_BASE_DIR,
        artifact_namespace=selected_namespace,
    )
    _apply_event_alpha_context_to_config(context)
    _normalize_profile_paths()
    return context


def _event_alpha_context_block(context: event_alpha_artifacts.EventAlphaArtifactContext) -> str:
    return "\n".join([
        "artifact context:",
        f"- profile: {context.profile}",
        f"- artifact_namespace: {context.artifact_namespace}",
        f"- run_mode: {context.run_mode}",
        f"- run_ledger_path: {context.run_ledger_path}",
        f"- alert_store_path: {context.alert_store_path}",
        f"- notification_runs_path: {context.notification_runs_path}",
        f"- feedback_path: {context.feedback_path}",
        f"- provider_health_path: {context.provider_health_path}",
        f"- impact_hypothesis_store_path: {context.impact_hypothesis_store_path}",
        f"- core_opportunity_store_path: {context.core_opportunity_store_path}",
        f"- incident_store_path: {context.incident_store_path}",
        f"- evidence_acquisition_path: {context.evidence_acquisition_path}",
        f"- research_cards_dir: {context.research_cards_dir}",
    ])


def _event_alpha_report_path(path: str | None, fallback: Path) -> Path:
    if path:
        resolved = Path(path).expanduser()
        return resolved if resolved.is_absolute() else config.DATA_DIR / resolved
    return fallback


def _event_alpha_report_context(
    profile_name: str | None,
    artifact_namespace: str | None,
) -> event_alpha_artifacts.EventAlphaArtifactContext:
    if profile_name or artifact_namespace:
        return resolve_event_alpha_artifact_context_for_report(profile_name, artifact_namespace)
    base_dir = Path(config.EVENT_ALPHA_ARTIFACT_BASE_DIR).expanduser()
    if not base_dir.is_absolute():
        base_dir = config.DATA_DIR / base_dir
    return event_alpha_artifacts.EventAlphaArtifactContext(
        profile="default",
        run_mode=config.EVENT_ALPHA_RUN_MODE or "legacy",
        artifact_namespace=config.EVENT_ALPHA_ARTIFACT_NAMESPACE or "default",
        base_dir=base_dir,
        namespace_dir=base_dir,
        run_ledger_path=Path(config.EVENT_ALPHA_RUN_LEDGER_PATH),
        alert_store_path=Path(config.EVENT_ALPHA_ALERT_STORE_PATH),
        notification_runs_path=Path(config.EVENT_ALPHA_NOTIFICATION_RUNS_PATH),
        watchlist_state_path=Path(config.EVENT_WATCHLIST_STATE_PATH),
        feedback_path=Path(config.EVENT_ALPHA_FEEDBACK_PATH),
        missed_path=Path(config.EVENT_ALPHA_MISSED_PATH),
        priors_path=Path(config.EVENT_ALPHA_PRIORS_PATH),
        provider_health_path=Path(config.EVENT_PROVIDER_HEALTH_PATH),
        daily_brief_path=Path(config.EVENT_ALPHA_DAILY_BRIEF_PATH),
        impact_hypothesis_store_path=Path(config.EVENT_IMPACT_HYPOTHESIS_STORE_PATH),
        core_opportunity_store_path=Path(getattr(config, "EVENT_CORE_OPPORTUNITY_STORE_PATH", base_dir / "event_core_opportunities.jsonl")),
        incident_store_path=Path(config.EVENT_INCIDENT_STORE_PATH),
        evidence_acquisition_path=Path(config.EVENT_ALPHA_EVIDENCE_ACQUISITION_PATH),
        proposed_eval_cases_dir=Path(config.EVENT_ALPHA_PROPOSED_EVAL_CASES_DIR),
        research_cards_dir=Path(config.EVENT_RESEARCH_CARDS_DIR),
        llm_budget_ledger_path=Path(config.EVENT_LLM_BUDGET_LEDGER_PATH),
        outcomes_path=Path(getattr(config, "EVENT_ALPHA_OUTCOMES_PATH", base_dir / "event_alpha_outcomes.jsonl")),
    )


def _normalize_profile_paths() -> None:
    for attr in (
        "EVENT_DISCOVERY_UNIVERSE_PATH",
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS_PATH",
        "EVENT_CATALYST_SEARCH_FIXTURE_PATH",
        "EVENT_WATCHLIST_STATE_PATH",
        "EVENT_WATCHLIST_MONITOR_MARKET_PATH",
        "EVENT_ALPHA_ALERT_STORE_PATH",
        "EVENT_ALPHA_NOTIFICATION_RUNS_PATH",
        "EVENT_ALPHA_RUN_LEDGER_PATH",
        "EVENT_ALPHA_MISSED_PATH",
        "EVENT_ALPHA_PRIORS_PATH",
        "EVENT_ALPHA_OUTCOMES_PATH",
        "EVENT_PROVIDER_HEALTH_PATH",
        "EVENT_ALPHA_DAILY_BRIEF_PATH",
        "EVENT_IMPACT_HYPOTHESIS_STORE_PATH",
        "EVENT_CORE_OPPORTUNITY_STORE_PATH",
        "EVENT_INCIDENT_STORE_PATH",
        "EVENT_ALPHA_EVIDENCE_ACQUISITION_PATH",
        "EVENT_ALPHA_PROPOSED_EVAL_CASES_DIR",
        "EVENT_RESEARCH_CARDS_DIR",
        "EVENT_LLM_BUDGET_LEDGER_PATH",
    ):
        value = getattr(config, attr, None)
        if isinstance(value, Path):
            resolved = value.expanduser()
            if not resolved.is_absolute():
                resolved = config.DATA_DIR / resolved
            setattr(config, attr, resolved)
    rss_path = getattr(config, "EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS_PATH", None)
    if rss_path and not getattr(config, "EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS", ()):
        try:
            urls = [
                line.strip()
                for line in Path(rss_path).read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
            config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS = tuple(dict.fromkeys(urls))
        except OSError:
            config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS = ()


def _research_card_markdown_paths(cards_dir: str | Path, *, include_index: bool = False) -> list[Path]:
    directory = Path(cards_dir)
    if not directory.exists():
        return []
    return sorted(
        path for path in directory.glob("*.md")
        if include_index or path.name != "index.md"
    )


def _event_alpha_card_lineage_context(
    *,
    run_id: str | None,
    profile: str | None,
    run_mode: str | None,
    artifact_namespace: str | None,
) -> dict[str, str]:
    return {
        "run_id": str(run_id or "manual_card_write"),
        "profile": str(profile or "default"),
        "run_mode": str(run_mode or "legacy"),
        "artifact_namespace": str(artifact_namespace or "default"),
    }


def _latest_event_alpha_run_id(path: str | Path) -> str | None:
    rows = event_alpha_run_ledger.load_run_records(path, limit=1).rows
    if not rows:
        return None
    return str(rows[0].get("run_id") or "") or None


def _latest_event_alpha_profile_from_runs() -> str | None:
    rows = event_alpha_run_ledger.load_run_records(config.EVENT_ALPHA_RUN_LEDGER_PATH, limit=1).rows
    if not rows:
        return None
    profile = str(rows[0].get("profile") or "").strip()
    return profile if profile and profile != "default" else None


def _apply_event_alpha_report_profile(
    profile_name: str | None,
    *,
    infer_latest: bool = False,
) -> tuple[event_alpha_profiles.EventAlphaProfile | None, str | None]:
    selected = profile_name or (_latest_event_alpha_profile_from_runs() if infer_latest else None)
    if not selected:
        return None, None
    try:
        return _apply_event_alpha_profile(selected), None
    except ValueError as exc:
        return None, str(exc)


def _setup_event_discovery_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-5s %(message)s",
        datefmt="%H:%M:%S",
    )


def _event_alpha_inputs_configured() -> bool:
    return bool(
        config.EVENT_ANOMALY_SCANNER_ENABLED
        or config.EVENT_MARKET_ENRICHMENT_ENABLED
        or config.EVENT_CATALYST_SEARCH_ENABLED
        or _event_discovery_paths_configured()
    )


def _event_alerts_from_config(
    with_llm: bool = False,
    *,
    now: datetime | None = None,
) -> list[event_alerts.EventAlertCandidate]:
    cfg = _event_alert_config_from_runtime()
    result = _event_discovery_result_from_config(now=now)
    alerts = event_alerts.build_event_alert_candidates(result, cfg=cfg, now=now)
    if with_llm:
        llm_cfg = _event_llm_config_from_runtime()
        provider = _event_llm_provider(llm_cfg)
        if provider is not None:
            rows = event_llm_analyzer.analyze_event_candidates(result, alerts, provider, cfg=llm_cfg)
            alerts = event_alerts.apply_llm_advisory(alerts, rows, cfg, enabled=llm_cfg.mode == "advisory")
    alerts = event_alpha_priors.apply_priors_to_alerts(
        alerts,
        cfg=_event_alpha_priors_config_from_runtime(),
        alert_cfg=cfg,
    )
    return alerts


def event_discovery_report(verbose: bool = False, event_now: str | datetime | None = None) -> None:
    """Print research-only event-discovery radar from local fixtures."""
    _setup_event_discovery_logging(verbose)
    if not _event_discovery_paths_configured():
        print(
            "No event-discovery sources ready. Set RSI_EVENT_DISCOVERY_EVENTS_PATH, "
            "another event-discovery fixture path, or opt into a live research provider. "
            "Run --event-discovery-status for a redacted readiness report."
        )
        return
    now = _event_research_now(event_now)
    result = _event_discovery_result_from_config(now=now)
    print(event_discovery.format_discovery_report(result))


def event_alert_report(
    verbose: bool = False,
    send: bool = False,
    with_llm: bool = False,
    event_now: str | datetime | None = None,
) -> None:
    """Print or explicitly send research-only event-discovery alert candidates."""
    _setup_event_discovery_logging(verbose)
    if not _event_discovery_paths_configured():
        print(
            "No event-discovery sources ready. Set RSI_EVENT_DISCOVERY_EVENTS_PATH, "
            "another event-discovery fixture path, or opt into a live research provider. "
            "Run --event-discovery-status for a redacted readiness report."
        )
        return
    cfg = _event_alert_config_from_runtime()
    now = _event_research_now(event_now)
    result = _event_discovery_result_from_config(now=now)
    alerts = event_alerts.build_event_alert_candidates(result, cfg=cfg, now=now)
    if with_llm:
        llm_cfg = _event_llm_config_from_runtime()
        provider = _event_llm_provider(llm_cfg)
        if provider is not None:
            llm_rows = event_llm_analyzer.analyze_event_candidates(
                result,
                alerts,
                provider,
                cfg=llm_cfg,
            )
            alerts = event_alerts.apply_llm_advisory(
                alerts,
                llm_rows,
                cfg,
                enabled=llm_cfg.mode == "advisory",
            )
        if llm_cfg.mode not in {"shadow", "advisory"}:
            print(f"Event LLM mode {llm_cfg.mode!r} is not supported; use shadow or advisory.")
    alerts = event_alpha_priors.apply_priors_to_alerts(
        alerts,
        cfg=_event_alpha_priors_config_from_runtime(),
        alert_cfg=cfg,
    )
    print(event_alerts.format_event_alert_report(alerts))
    if send:
        _send_event_alert_digest(alerts, cfg, now=now)


def event_alpha_radar_report(
    verbose: bool = False,
    with_llm: bool = False,
    event_now: str | datetime | None = None,
) -> None:
    """Print the opt-in event alpha radar with market enrichment/anomalies."""
    _setup_event_discovery_logging(verbose)
    if not _event_alpha_inputs_configured():
        print(
            "No event-alpha radar inputs ready. Configure event sources or enable "
            "RSI_EVENT_ANOMALY_SCANNER_ENABLED=1 with a CoinGecko universe fixture/live source."
        )
        return
    now = _event_research_now(event_now)
    alerts = _event_alerts_from_config(with_llm=with_llm, now=now)
    print(event_alerts.format_event_alert_report(alerts))


def _write_event_impact_hypotheses_for_run(
    pipeline_result: event_alpha_pipeline.EventAlphaPipelineResult,
    *,
    now: datetime,
    run_id: str,
    profile: str,
    run_mode: str | None,
    artifact_namespace: str | None,
) -> tuple[event_alpha_pipeline.EventAlphaPipelineResult, event_impact_hypothesis_store.EventImpactHypothesisStoreWriteResult]:
    store_cfg = _event_impact_hypothesis_store_config_from_runtime()
    watchlist_rows = tuple(pipeline_result.watchlist_result.entries) if pipeline_result.watchlist_result else ()
    write_result = event_impact_hypothesis_store.write_impact_hypotheses(
        pipeline_result.impact_hypotheses,
        cfg=store_cfg,
        now=now,
        run_id=run_id,
        profile=profile,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
        watchlist_rows=watchlist_rows,
    )
    updated = replace(
        pipeline_result,
        hypothesis_store_path=str(store_cfg.path),
        hypothesis_write_attempted=write_result.attempted,
        hypothesis_write_success=write_result.success,
        hypothesis_rows_written=write_result.rows_written,
        hypothesis_write_block_reason=write_result.block_reason,
    )
    return updated, write_result


def _write_event_incidents_for_run(
    pipeline_result: event_alpha_pipeline.EventAlphaPipelineResult,
    *,
    now: datetime,
    run_id: str,
    profile: str,
    run_mode: str | None,
    artifact_namespace: str | None,
) -> tuple[event_alpha_pipeline.EventAlphaPipelineResult, event_incident_store.EventIncidentStoreWriteResult]:
    store_cfg = _event_incident_store_config_from_runtime()
    watchlist_rows = tuple(pipeline_result.watchlist_result.entries) if pipeline_result.watchlist_result else ()
    write_result = event_incident_store.write_incidents(
        pipeline_result.discovery_result,
        cfg=store_cfg,
        hypotheses=pipeline_result.impact_hypotheses,
        watchlist_rows=watchlist_rows,
        now=now,
        run_id=run_id,
        profile=profile,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
    )
    updated = replace(
        pipeline_result,
        incident_store_path=str(store_cfg.path),
        incident_write_attempted=write_result.attempted,
        incident_write_success=write_result.success,
        incident_rows_written=write_result.rows_written,
        incident_write_block_reason=write_result.block_reason,
    )
    return updated, write_result


def _write_event_core_opportunities_for_run(
    pipeline_result: event_alpha_pipeline.EventAlphaPipelineResult,
    *,
    now: datetime,
    run_id: str,
    profile: str,
    run_mode: str | None,
    artifact_namespace: str | None,
    card_paths: Iterable[str | Path] = (),
) -> tuple[event_alpha_pipeline.EventAlphaPipelineResult, event_core_opportunity_store.EventCoreOpportunityStoreWriteResult]:
    store_cfg = _event_core_opportunity_store_config_from_runtime()
    watchlist_rows = tuple(pipeline_result.watchlist_result.entries) if pipeline_result.watchlist_result else ()
    route_decisions = tuple(pipeline_result.router_result.decisions) if pipeline_result.router_result else ()
    rows = [*route_decisions, *watchlist_rows, *pipeline_result.impact_hypotheses, *pipeline_result.alerts]
    write_result = event_core_opportunity_store.write_core_opportunities(
        rows,
        cfg=store_cfg,
        now=now,
        run_id=run_id,
        profile=profile,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
        card_paths=card_paths,
    )
    updated = replace(
        pipeline_result,
        core_opportunity_store_path=str(store_cfg.path),
        core_opportunity_write_attempted=write_result.attempted,
        core_opportunity_write_success=write_result.success,
        core_opportunity_rows_written=write_result.rows_written,
        core_opportunity_write_block_reason=write_result.block_reason,
    )
    return updated, write_result


def _cryptopanic_stats_for_pipeline_result(
    pipeline_result: event_alpha_pipeline.EventAlphaPipelineResult,
    *,
    provider_health_path: str | Path,
) -> dict[str, Any]:
    """Summarize CryptoPanic usage without exposing the API token."""
    acquisition = pipeline_result.evidence_acquisition_result
    accepted = 0
    rejected = 0
    results_seen = 0
    attempted = False
    provider_failures = 0
    if acquisition is not None:
        for result in acquisition.results:
            providers = {str(item).casefold() for item in getattr(result, "providers_used", ()) or ()}
            if "cryptopanic" in providers:
                attempted = True
            for query in getattr(result, "query_results", ()) or ():
                query_values = (
                    getattr(query, "provider_hint", ""),
                    getattr(query, "provider_used", ""),
                    getattr(query, "query", ""),
                )
                query_is_cryptopanic = any("cryptopanic" in str(value).casefold() for value in query_values)
                if query_is_cryptopanic:
                    attempted = True
                    results_seen += int(getattr(query, "results_seen", 0) or 0)
                    provider_failures += len(tuple(getattr(query, "provider_failures", ()) or ()))
                accepted += sum(
                    1
                    for item in getattr(query, "accepted_evidence", ()) or ()
                    if _mapping_mentions_cryptopanic(item)
                )
                rejected += sum(
                    1
                    for item in getattr(query, "rejected_evidence", ()) or ()
                    if _mapping_mentions_cryptopanic(item)
                )
            accepted += sum(
                1
                for item in getattr(result, "accepted_evidence", ()) or ()
                if _mapping_mentions_cryptopanic(item)
            )
            rejected += sum(
                1
                for item in getattr(result, "rejected_evidence", ()) or ()
                if _mapping_mentions_cryptopanic(item)
            )
            provider_failures += sum(
                1
                for item in getattr(result, "provider_failures", ()) or ()
                if "cryptopanic" in str(item).casefold()
            )
    rows = event_provider_health.load_provider_health(provider_health_path)
    statuses = [
        event_provider_health.provider_health_status(row)
        for key, row in rows.items()
        if "cryptopanic" in " ".join(
            str(value or "").casefold()
            for value in (
                key,
                row.get("provider"),
                row.get("provider_key"),
                row.get("provider_service"),
            )
        )
    ]
    provider_status = "not_observed"
    if "backoff" in statuses:
        provider_status = "backoff"
    elif "degraded" in statuses:
        provider_status = "degraded"
    elif statuses:
        provider_status = "healthy"
    configured = bool(config.EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN)
    skip_reason = None
    if not configured:
        skip_reason = "missing_api_key"
    elif not config.EVENT_DISCOVERY_CRYPTOPANIC_LIVE and not config.EVENT_DISCOVERY_CRYPTOPANIC_PATH:
        skip_reason = "profile_disabled"
    elif not attempted:
        if provider_status == "backoff":
            skip_reason = "provider_backoff"
        elif provider_failures:
            skip_reason = "provider_error"
        elif acquisition is None or not acquisition.results:
            skip_reason = "no_eligible_candidates"
        else:
            skip_reason = "query_planner_skipped"
    return {
        "cryptopanic_configured": configured,
        "cryptopanic_attempted": attempted,
        "cryptopanic_results": max(results_seen, accepted + rejected),
        "cryptopanic_accepted_evidence": accepted,
        "cryptopanic_rejected_evidence": rejected,
        "cryptopanic_provider_status": provider_status,
        "cryptopanic_skip_reason": skip_reason,
    }


def _mapping_mentions_cryptopanic(item: object) -> bool:
    if not isinstance(item, Mapping):
        return "cryptopanic" in str(item).casefold()
    values = (
        item.get("provider"),
        item.get("provider_hint"),
        item.get("provider_used"),
        item.get("source_class"),
        item.get("source_url"),
        item.get("reason_codes"),
        item.get("currency_tags"),
        item.get("query"),
    )
    return any(
        "cryptopanic" in str(value).casefold()
        or str(value).casefold() == "cryptopanic_tagged"
        for value in values
    )


def event_alpha_cycle(
    verbose: bool = False,
    with_llm: bool = False,
    send: bool = False,
    event_now: str | datetime | None = None,
    profile_name: str | None = None,
) -> None:
    """Run one unified research-only Event Alpha cycle."""
    _setup_event_discovery_logging(verbose)
    profile = _apply_event_alpha_profile(profile_name)
    if profile is not None:
        with_llm = with_llm or profile.with_llm
        send = send or profile.send
    profile_for_run = (profile.name if profile else profile_name) or "default"
    run_mode = config.EVENT_ALPHA_RUN_MODE or "legacy"
    artifact_namespace = config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None
    if not _event_alpha_inputs_configured():
        print(
            "No event-alpha cycle inputs ready. Configure event sources or enable "
            "RSI_EVENT_ANOMALY_SCANNER_ENABLED=1 with a CoinGecko universe fixture/live source."
        )
        return
    clock_status = _event_clock_status(event_now)
    now = _event_research_now(event_now)
    started_at = datetime.now(timezone.utc)
    run_id = event_alpha_run_ledger.run_id_for(started_at, profile_for_run)
    extraction_provider = None
    extraction_cfg = None
    catalyst_frame_provider = None
    catalyst_frame_cfg = None
    relationship_provider = None
    relationship_cfg = None
    if with_llm:
        extraction_cfg = _event_llm_extractor_config_from_runtime()
        extraction_provider = _event_llm_extraction_provider(extraction_cfg)
        catalyst_frame_cfg = _event_llm_catalyst_frame_config_from_runtime()
        catalyst_frame_provider = _event_llm_catalyst_frame_provider(catalyst_frame_cfg)
        relationship_cfg = _event_llm_config_from_runtime()
        relationship_provider = _event_llm_provider(relationship_cfg)
    catalyst_search_cfg = _event_catalyst_search_config_from_runtime()
    catalyst_search_provider = _event_catalyst_search_provider(catalyst_search_cfg)
    hypothesis_search_cfg = _event_impact_hypothesis_search_config_from_runtime()
    evidence_acquisition_cfg = _event_evidence_acquisition_config_from_runtime()
    evidence_acquisition_providers = _event_evidence_acquisition_providers_from_runtime(evidence_acquisition_cfg)
    alert_cfg = _event_alert_config_from_runtime()
    pipeline_result = event_alpha_pipeline.run_event_alpha_operating_cycle(
        load_discovery_result=lambda observed, raw_event_transform: _event_discovery_result_from_config(
            now=observed,
            raw_event_transform=raw_event_transform,
        ),
        alert_cfg=alert_cfg,
        now=now,
        with_llm=with_llm,
        extraction_provider=extraction_provider,
        extraction_cfg=extraction_cfg,
        catalyst_frame_provider=catalyst_frame_provider,
        catalyst_frame_cfg=catalyst_frame_cfg,
        catalyst_search_provider=catalyst_search_provider,
        catalyst_search_cfg=catalyst_search_cfg,
        hypothesis_search_provider=catalyst_search_provider,
        hypothesis_search_cfg=hypothesis_search_cfg,
        source_enrichment_cfg=_event_source_enrichment_config_from_runtime(),
        relationship_provider=relationship_provider,
        relationship_cfg=relationship_cfg,
        watchlist_cfg=_event_watchlist_config_from_runtime(),
        router_cfg=_event_alpha_router_config_from_runtime(),
        priors_cfg=_event_alpha_priors_config_from_runtime(),
        refresh_watchlist=True,
        route=True,
        watchlist_monitor_enabled=config.EVENT_WATCHLIST_MONITOR_ENABLED,
        watchlist_monitor_market_rows=_event_watchlist_monitor_market_rows_from_runtime(),
        watchlist_monitor_market_source=config.EVENT_WATCHLIST_MONITOR_MARKET_SOURCE,
        watchlist_monitor_market_provider=_event_watchlist_market_provider_from_runtime(),
        watchlist_monitor_targeted_lookup=config.EVENT_WATCHLIST_MONITOR_TARGETED_LOOKUP,
        watchlist_monitor_max_assets=config.EVENT_WATCHLIST_MONITOR_MAX_ASSETS,
        watchlist_monitor_market_cache_ttl_seconds=config.EVENT_WATCHLIST_MONITOR_MARKET_CACHE_TTL_SECONDS,
        watchlist_monitor_derivatives_source=config.EVENT_WATCHLIST_MONITOR_DERIVATIVES_SOURCE,
        watchlist_monitor_supply_source=config.EVENT_WATCHLIST_MONITOR_SUPPLY_SOURCE,
        watchlist_monitor_derivatives_rows=_event_watchlist_monitor_derivatives_rows_from_runtime(),
        watchlist_monitor_supply_rows=_event_watchlist_monitor_supply_rows_from_runtime(),
        watchlist_monitor_enrichment_max_assets=config.EVENT_WATCHLIST_MONITOR_ENRICHMENT_MAX_ASSETS,
        watchlist_monitor_route_updates=config.EVENT_WATCHLIST_MONITOR_ROUTE_UPDATES,
        near_miss_cfg=_event_near_miss_config_from_runtime(),
        near_miss_market_rows=_event_watchlist_monitor_market_rows_from_runtime(),
        near_miss_market_provider=_event_watchlist_market_provider_from_runtime()
        if config.EVENT_ALPHA_NEAR_MISS_MARKET_REFRESH_ENABLED
        else None,
        near_miss_derivatives_rows=_event_watchlist_monitor_derivatives_rows_from_runtime(),
        near_miss_supply_rows=_event_watchlist_monitor_supply_rows_from_runtime(),
        evidence_acquisition_cfg=evidence_acquisition_cfg,
        evidence_acquisition_provider=evidence_acquisition_providers.get("default"),
        evidence_acquisition_providers_by_hint=evidence_acquisition_providers,
        evidence_acquisition_context={
            "run_id": run_id,
            "profile": profile_for_run,
            "run_mode": run_mode,
            "artifact_namespace": artifact_namespace or config.EVENT_ALPHA_ARTIFACT_NAMESPACE,
        },
        send=send,
        send_callback=lambda decisions: _send_event_alpha_routed_digest(
            decisions,
            alert_cfg,
            now=now,
            profile=profile_for_run,
            clock_status=clock_status,
        ),
    )
    pipeline_result, hypothesis_store_result = _write_event_impact_hypotheses_for_run(
        pipeline_result,
        now=now,
        run_id=run_id,
        profile=profile_for_run,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
    )
    pipeline_result, incident_store_result = _write_event_incidents_for_run(
        pipeline_result,
        now=now,
        run_id=run_id,
        profile=profile_for_run,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
    )
    pipeline_result, core_store_result = _write_event_core_opportunities_for_run(
        pipeline_result,
        now=now,
        run_id=run_id,
        profile=profile_for_run,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
        card_paths=(),
    )
    latest_core_rows = event_core_opportunity_store.load_core_opportunities(
        _event_core_opportunity_store_config_from_runtime().path,
        latest_run=True,
        run_id=run_id,
    ).rows
    event_evidence_acquisition.reconcile_acquisition_core_ids(
        config.EVENT_ALPHA_EVIDENCE_ACQUISITION_PATH,
        latest_core_rows,
        run_id=run_id,
        profile=profile_for_run,
        artifact_namespace=artifact_namespace,
    )
    if config.EVENT_RESEARCH_CARDS_AUTO_WRITE and pipeline_result.router_result is not None:
        watch_cfg = _event_watchlist_config_from_runtime()
        watchlist = event_watchlist.load_watchlist(watch_cfg.state_path or config.EVENT_WATCHLIST_STATE_PATH)
        card_write = event_research_cards.write_research_cards(
            config.EVENT_RESEARCH_CARDS_DIR,
            watchlist_entries=watchlist.entries,
            alert_rows=latest_core_rows,
            route_decisions=pipeline_result.router_result.decisions,
            selected_tiers=config.EVENT_RESEARCH_CARDS_WRITE_TIERS,
            limit=config.EVENT_RESEARCH_CARDS_WRITE_LIMIT,
            now=now,
            lineage_context=_event_alpha_card_lineage_context(
                run_id=run_id,
                profile=profile_for_run,
                run_mode=run_mode,
                artifact_namespace=artifact_namespace,
            ),
        )
        pipeline_result = replace(pipeline_result, research_card_paths=card_write.card_paths)
        event_core_opportunity_store.update_core_opportunity_card_links(
            _event_core_opportunity_store_config_from_runtime().path,
            card_write.card_paths,
            run_id=run_id,
        )
        latest_core_rows = event_core_opportunity_store.load_core_opportunities(
            _event_core_opportunity_store_config_from_runtime().path,
            latest_run=True,
            run_id=run_id,
        ).rows
        print(event_research_cards.format_card_write_result(card_write))
        print("")
    print(event_alpha_pipeline.format_event_alpha_pipeline_report(pipeline_result))
    store_cfg = _event_alpha_alert_store_config_from_runtime()
    if run_mode in event_alpha_artifacts.NON_OPERATIONAL_RUN_MODES:
        store_result = event_alpha_alert_store.blocked_alert_snapshot_write(
            cfg=store_cfg,
            now=now,
            reason="test_or_fixture_run",
        )
    else:
        store_result = event_alpha_alert_store.write_alert_snapshots(
            pipeline_result.alerts,
            cfg=store_cfg,
            now=now,
            router_result=pipeline_result.router_result,
            run_id=run_id,
            profile=profile_for_run,
            run_mode=run_mode,
            artifact_namespace=artifact_namespace,
            research_card_paths=pipeline_result.research_card_paths,
            core_opportunity_rows=latest_core_rows,
        )
    pipeline_result = replace(
        pipeline_result,
        clock_status=clock_status,
        run_id=run_id,
        profile=profile_for_run,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
        run_ledger_path=str(_event_alpha_run_ledger_config_from_runtime().path),
        alert_store_path=str(store_cfg.path),
        watchlist_state_path=str(config.EVENT_WATCHLIST_STATE_PATH),
        research_cards_dir=str(config.EVENT_RESEARCH_CARDS_DIR),
        snapshot_write_attempted=store_result.attempted,
        snapshot_write_success=store_result.success,
        snapshot_rows_written=store_result.rows_written,
        snapshot_write_block_reason=store_result.block_reason,
    )
    print("")
    print(event_alpha_alert_store.format_alert_store_write_result(store_result))
    print(
        "Event impact hypotheses updated: "
        f"{hypothesis_store_result.path} rows={hypothesis_store_result.rows_written} "
        f"success={str(hypothesis_store_result.success).lower()}"
        + (f" block={hypothesis_store_result.block_reason}" if hypothesis_store_result.block_reason else "")
    )
    print(
        "Event incidents updated: "
        f"{incident_store_result.path} rows={incident_store_result.rows_written} "
        f"success={str(incident_store_result.success).lower()}"
        + (f" block={incident_store_result.block_reason}" if incident_store_result.block_reason else "")
    )
    print(event_core_opportunity_store.format_core_opportunity_store_write_result(core_store_result))
    pipeline_result = replace(
        pipeline_result,
        **_cryptopanic_stats_for_pipeline_result(
            pipeline_result,
            provider_health_path=_event_provider_health_config_from_runtime().path,
        ),
    )
    run_row = event_alpha_run_ledger.append_run_record(
        pipeline_result,
        cfg=_event_alpha_run_ledger_config_from_runtime(),
        profile=profile_for_run,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
        with_llm=with_llm,
        send_requested=send,
        notification_burn_in=bool(profile and profile.notification_burn_in),
        success=True,
    )
    print("")
    print(
        "Event Alpha run ledger updated: "
        f"{config.EVENT_ALPHA_RUN_LEDGER_PATH} run_id={run_row.get('run_id')}"
    )


def event_alpha_profile_report(profile_name: str, verbose: bool = False) -> None:
    """Print one Event Alpha operational profile."""
    _setup_event_discovery_logging(verbose)
    try:
        profile = event_alpha_profiles.get_profile(profile_name)
    except ValueError as exc:
        print(str(exc))
        return
    print(event_alpha_profiles.format_profile_report(profile))


class NotificationRuntimeBudget:
    """Small wall-clock budget helper for day-1 notification cycles."""

    def __init__(self, started_at: datetime, max_seconds: float) -> None:
        self.started_at = started_at.astimezone(timezone.utc) if started_at.tzinfo else started_at.replace(tzinfo=timezone.utc)
        self.max_seconds = float(max_seconds or 0.0)

    def remaining_seconds(self) -> float:
        if self.max_seconds <= 0:
            return 0.0
        elapsed = (datetime.now(timezone.utc) - self.started_at).total_seconds()
        return max(0.0, self.max_seconds - elapsed)

    def exhausted(self) -> bool:
        return self.max_seconds <= 0 or self.remaining_seconds() <= 0

    def warning_if_low(self, stage: str) -> str | None:
        if not self.exhausted():
            return None
        clean_stage = "".join(ch if ch.isalnum() else "_" for ch in str(stage or "stage").strip().lower()).strip("_")
        return f"notification_runtime_budget_exhausted_before_{clean_stage or 'stage'}"


def _notification_runtime_budget(started_at: datetime) -> NotificationRuntimeBudget:
    return NotificationRuntimeBudget(
        started_at,
        float(getattr(config, "EVENT_ALPHA_NOTIFY_MAX_RUNTIME_SECONDS", 120.0) or 0.0),
    )


def _notification_runtime_budget_exhausted(started_at: datetime) -> bool:
    return _notification_runtime_budget(started_at).exhausted()


def _notification_warnings_indicate_partial(warnings: Iterable[str]) -> bool:
    tokens = (
        "notification_cycle_failed_soft",
        "notification_runtime_budget_exhausted",
        "market_enrichment_live_fetch_failed",
        "failed",
        "failure",
        "timeout",
        "dns",
        "backoff",
        "429",
    )
    return any(any(token in str(warning).casefold() for token in tokens) for warning in warnings)


def _empty_notification_pipeline_result(
    *,
    now: datetime,
    warning: str,
    cycle_completed: bool = False,
) -> event_alpha_pipeline.EventAlphaPipelineResult:
    watch_cfg = _event_watchlist_config_from_runtime()
    router_cfg = _event_alpha_router_config_from_runtime()
    watchlist = event_watchlist.load_watchlist(watch_cfg.state_path or config.EVENT_WATCHLIST_STATE_PATH)
    router_result = event_alpha_router.route_watchlist(watchlist, cfg=router_cfg)
    return event_alpha_pipeline.EventAlphaPipelineResult(
        discovery_result=EventDiscoveryResult((), (), (), (), ()),
        alerts=[],
        catalyst_search_result=None,
        hypothesis_search_result=None,
        anomaly_lifecycle_result=None,
        extraction_rows=[],
        catalyst_frame_rows=[],
        relationship_rows=[],
        watchlist_result=None,
        watchlist_monitor_result=None,
        router_result=router_result,
        warnings=(warning,),
        cycle_completed=cycle_completed,
        partial_results=True,
    )


def format_event_alpha_notification_next_steps(
    *,
    profile: str,
    provider_health_rows: Mapping[str, Mapping[str, Any]] | None = None,
    result: Any | None = None,
    notification_row: Mapping[str, Any] | None = None,
) -> str:
    """Render post-run operator commands without mutating state."""
    rows = provider_health_rows or {}
    backoff_keys = tuple(
        str(row.get("provider_key") or key)
        for key, row in rows.items()
        if row.get("disabled_until")
    )
    would_send = _int_value(
        (notification_row or {}).get("would_send_count")
        if notification_row is not None
        else getattr(result, "send_would_send_items", 0)
    )
    cards_written = len(tuple(getattr(result, "research_card_paths", ()) or ()))
    alertable = _int_value(getattr(result, "alertable", 0))
    feedback_target = _first_notification_feedback_target(result)
    lines = [
        "=" * 76,
        "EVENT ALPHA NOTIFICATION NEXT STEPS",
        "=" * 76,
        f"- make event-alpha-notification-runs-report PROFILE={profile}",
        f"- make event-alpha-notification-inbox PROFILE={profile}",
        f"- make event-alpha-daily-brief PROFILE={profile}",
        f"- make event-alpha-artifact-doctor PROFILE={profile} STRICT=1",
        f"- make event-alpha-provider-health-report PROFILE={profile}",
    ]
    if backoff_keys:
        lines.append(
            f"- make event-alpha-provider-health-reset PROFILE={profile} "
            f"PROVIDER_KEY={backoff_keys[0]} CONFIRM=1"
        )
    if would_send > 0 or cards_written > 0 or alertable > 0:
        target = feedback_target or "<alert_id_or_card_id>"
        lines.append(f"- make event-feedback-watch PROFILE={profile} FEEDBACK_TARGET='{target}'")
    else:
        lines.append("- no alert/cards produced; review heartbeat status in the runs report and daily brief")
    lines.append("Research-only follow-up only; these commands do not trade, paper trade, or write normal RSI signals.")
    return "\n".join(lines).rstrip()


def _first_notification_feedback_target(result: Any | None) -> str | None:
    router_result = getattr(result, "router_result", None)
    decisions = tuple(getattr(router_result, "alertable_decisions", ()) or ())
    if not decisions:
        decisions = tuple(getattr(router_result, "decisions", ()) or ())
    for decision in decisions:
        alert_id = str(getattr(decision, "alert_id", "") or "").strip()
        if alert_id:
            return alert_id
        card_id = str(getattr(decision, "card_id", "") or "").strip()
        if card_id:
            return card_id
    for path in tuple(getattr(result, "research_card_paths", ()) or ()):
        stem = Path(path).stem
        if stem and stem != "index":
            return stem
    return None


def _int_value(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def event_alpha_notify_cycle(
    verbose: bool = False,
    with_llm: bool = False,
    send: bool = False,
    event_now: str | datetime | None = None,
    profile_name: str | None = None,
    ignore_provider_backoff: bool = False,
) -> None:
    """Run a day-1 Event Alpha notification cycle, guaranteeing lock release.

    The cycle body acquires the per-profile run lock and stores it in
    ``lock_holder``; this wrapper releases it in a ``finally`` so any exception
    in card writing, sending, snapshot/ledger writes, or report formatting still
    releases the lock (best-effort).
    """
    lock_holder: dict[str, object] = {}
    try:
        _event_alpha_notify_cycle_body(
            verbose=verbose,
            with_llm=with_llm,
            send=send,
            event_now=event_now,
            profile_name=profile_name,
            ignore_provider_backoff=ignore_provider_backoff,
            lock_holder=lock_holder,
        )
    finally:
        run_lock = lock_holder.get("lock")
        if run_lock is not None:
            event_alpha_run_lock.release_run_lock(run_lock)


def _event_alpha_notify_cycle_body(
    *,
    verbose: bool = False,
    with_llm: bool = False,
    send: bool = False,
    event_now: str | datetime | None = None,
    profile_name: str | None = None,
    ignore_provider_backoff: bool = False,
    lock_holder: dict[str, object],
) -> None:
    """Run a day-1 Event Alpha notification burn-in cycle."""
    _setup_event_discovery_logging(verbose)
    selected_profile = profile_name or "notify_no_key"
    profile = _apply_event_alpha_profile(selected_profile)
    previous_ignore_backoff = bool(config.EVENT_ALPHA_IGNORE_PROVIDER_BACKOFF)
    ignore_backoff_for_run = bool(ignore_provider_backoff or config.EVENT_ALPHA_IGNORE_PROVIDER_BACKOFF)
    config.EVENT_ALPHA_IGNORE_PROVIDER_BACKOFF = ignore_backoff_for_run
    try:
        with_llm = with_llm or profile.with_llm
        profile_for_run = profile.name
        run_mode = config.EVENT_ALPHA_RUN_MODE or "notification_burn_in"
        artifact_namespace = config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None
        if not _event_alpha_inputs_configured():
            print(
                "No Event Alpha notification inputs ready. Configure notify_no_key/notify_llm providers "
                "or run --event-alpha-notify-preview for readiness details."
            )
            return
        clock_status = _event_clock_status(event_now)
        now = _event_research_now(event_now)
        started_at = datetime.now(timezone.utc)
        run_id = event_alpha_run_ledger.run_id_for(started_at, profile_for_run)
        lock_context = _event_alpha_notify_context_from_runtime(profile_for_run)
        delivery_cfg = _event_alpha_notification_delivery_config_from_runtime(lock_context)
        pause_state = _event_alpha_notification_pause_state(lock_context)
        run_lock = event_alpha_run_lock.acquire_run_lock(
            lock_context,
            cfg=_event_alpha_run_lock_config_from_runtime(),
            run_id=run_id,
            profile=profile_for_run,
            namespace=artifact_namespace or lock_context.artifact_namespace,
            command="event-alpha-notify-cycle",
            now=started_at,
        )
        lock_holder["lock"] = run_lock
        if run_lock.skipped_due_to_active_lock:
            print(f"Event Alpha notify cycle skipped: {run_lock.status.message}.")
            _record_skipped_notification_run(
                profile_for_run,
                run_id=run_id,
                run_mode=run_mode,
                artifact_namespace=artifact_namespace,
                started_at=started_at,
            )
            return
        if run_lock.stale_recovered:
            print(f"Warning: {event_alpha_run_lock.STALE_LOCK_RECOVERED_WARNING} ({run_lock.status.message}).")
        if pause_state.paused:
            print(f"Event Alpha notifications paused: {pause_state.reason} ({pause_state.source}).")
        budget = _notification_runtime_budget(started_at)
        pre_stage_warnings: list[str] = list(_event_alpha_notify_clock_warnings(clock_status))
        if ignore_backoff_for_run:
            pre_stage_warnings.append("provider_backoff_ignored_for_run")
        extraction_provider = None
        extraction_cfg = None
        catalyst_frame_provider = None
        catalyst_frame_cfg = None
        relationship_provider = None
        relationship_cfg = None
        llm_budget_warning = budget.warning_if_low("llm")
        effective_with_llm = with_llm
        if with_llm and llm_budget_warning:
            effective_with_llm = False
            pre_stage_warnings.append(llm_budget_warning)
        if effective_with_llm:
            llm_deadline_at = (
                started_at + timedelta(seconds=budget.max_seconds)
                if budget.max_seconds > 0
                else None
            )
            extraction_cfg = _event_llm_extractor_config_from_runtime()
            if llm_deadline_at is not None:
                extraction_cfg = replace(extraction_cfg, deadline_at=llm_deadline_at)
            extraction_provider = _event_llm_extraction_provider(extraction_cfg)
            catalyst_frame_cfg = _event_llm_catalyst_frame_config_from_runtime()
            if llm_deadline_at is not None:
                catalyst_frame_cfg = replace(catalyst_frame_cfg, deadline_at=llm_deadline_at)
            catalyst_frame_provider = _event_llm_catalyst_frame_provider(catalyst_frame_cfg)
            relationship_cfg = _event_llm_config_from_runtime()
            if llm_deadline_at is not None:
                relationship_cfg = replace(relationship_cfg, deadline_at=llm_deadline_at)
            relationship_provider = _event_llm_provider(relationship_cfg)
        alert_cfg = _event_alert_config_from_runtime()
        discovery_budget_warning = budget.warning_if_low("discovery")
        if discovery_budget_warning:
            pipeline_result = _empty_notification_pipeline_result(
                now=now,
                warning=discovery_budget_warning,
            )
        else:
            catalyst_budget_warning = budget.warning_if_low("catalyst_search")
            if catalyst_budget_warning:
                pre_stage_warnings.append(catalyst_budget_warning)
            catalyst_search_cfg = _event_catalyst_search_config_from_runtime(
                enabled_override=False if catalyst_budget_warning else None
            )
            catalyst_search_provider = None if catalyst_budget_warning else _event_catalyst_search_provider(catalyst_search_cfg)
            hypothesis_search_cfg = _event_impact_hypothesis_search_config_from_runtime(
                enabled_override=False if catalyst_budget_warning else None
            )
            evidence_acquisition_cfg = _event_evidence_acquisition_config_from_runtime()
            evidence_acquisition_providers = (
                {}
                if catalyst_budget_warning
                else _event_evidence_acquisition_providers_from_runtime(evidence_acquisition_cfg)
            )
            watchlist_budget_warning = budget.warning_if_low("watchlist_refresh")
            if watchlist_budget_warning:
                pre_stage_warnings.append(watchlist_budget_warning)
            try:
                pipeline_result = event_alpha_pipeline.run_event_alpha_operating_cycle(
                    load_discovery_result=lambda observed, raw_event_transform: _event_discovery_result_from_config(
                        now=observed,
                        raw_event_transform=raw_event_transform,
                    ),
                    alert_cfg=alert_cfg,
                    now=now,
                    with_llm=effective_with_llm,
                    extraction_provider=extraction_provider,
                    extraction_cfg=extraction_cfg,
                    catalyst_frame_provider=catalyst_frame_provider,
                    catalyst_frame_cfg=catalyst_frame_cfg,
                    catalyst_search_provider=catalyst_search_provider,
                    catalyst_search_cfg=catalyst_search_cfg,
                    hypothesis_search_provider=catalyst_search_provider,
                    hypothesis_search_cfg=hypothesis_search_cfg,
                    source_enrichment_cfg=_event_source_enrichment_config_from_runtime(),
                    relationship_provider=relationship_provider,
                    relationship_cfg=relationship_cfg,
                    watchlist_cfg=_event_watchlist_config_from_runtime(),
                    router_cfg=_event_alpha_router_config_from_runtime(),
                    priors_cfg=_event_alpha_priors_config_from_runtime(),
                    refresh_watchlist=not bool(watchlist_budget_warning),
                    route=True,
                    watchlist_monitor_enabled=(
                        config.EVENT_WATCHLIST_MONITOR_ENABLED and not bool(watchlist_budget_warning)
                    ),
                    watchlist_monitor_market_rows=_event_watchlist_monitor_market_rows_from_runtime(),
                    watchlist_monitor_market_source=config.EVENT_WATCHLIST_MONITOR_MARKET_SOURCE,
                    watchlist_monitor_market_provider=_event_watchlist_market_provider_from_runtime(),
                    watchlist_monitor_targeted_lookup=config.EVENT_WATCHLIST_MONITOR_TARGETED_LOOKUP,
                    watchlist_monitor_max_assets=config.EVENT_WATCHLIST_MONITOR_MAX_ASSETS,
                    watchlist_monitor_market_cache_ttl_seconds=config.EVENT_WATCHLIST_MONITOR_MARKET_CACHE_TTL_SECONDS,
                    watchlist_monitor_derivatives_source=config.EVENT_WATCHLIST_MONITOR_DERIVATIVES_SOURCE,
                    watchlist_monitor_supply_source=config.EVENT_WATCHLIST_MONITOR_SUPPLY_SOURCE,
                    watchlist_monitor_derivatives_rows=_event_watchlist_monitor_derivatives_rows_from_runtime(),
                    watchlist_monitor_supply_rows=_event_watchlist_monitor_supply_rows_from_runtime(),
                    watchlist_monitor_enrichment_max_assets=config.EVENT_WATCHLIST_MONITOR_ENRICHMENT_MAX_ASSETS,
                    watchlist_monitor_route_updates=config.EVENT_WATCHLIST_MONITOR_ROUTE_UPDATES,
                    near_miss_cfg=_event_near_miss_config_from_runtime(),
                    near_miss_market_rows=_event_watchlist_monitor_market_rows_from_runtime(),
                    near_miss_market_provider=_event_watchlist_market_provider_from_runtime()
                    if config.EVENT_ALPHA_NEAR_MISS_MARKET_REFRESH_ENABLED
                    else None,
                    near_miss_derivatives_rows=_event_watchlist_monitor_derivatives_rows_from_runtime(),
                    near_miss_supply_rows=_event_watchlist_monitor_supply_rows_from_runtime(),
                    evidence_acquisition_cfg=evidence_acquisition_cfg,
                    evidence_acquisition_provider=evidence_acquisition_providers.get("default"),
                    evidence_acquisition_providers_by_hint=evidence_acquisition_providers,
                    evidence_acquisition_context={
                        "run_id": run_id,
                        "profile": profile_for_run,
                        "run_mode": run_mode,
                        "artifact_namespace": artifact_namespace or lock_context.artifact_namespace,
                    },
                    send=False,
                )
            except Exception as exc:  # noqa: BLE001 - notification burn-in must fail soft on provider/runtime errors
                if not config.EVENT_ALPHA_NOTIFY_ALLOW_PARTIAL_RESULTS:
                    raise
                warning = f"notification_cycle_failed_soft: {type(exc).__name__}"
                log.warning("Event Alpha notification cycle failed soft: %s", exc)
                pipeline_result = _empty_notification_pipeline_result(now=now, warning=warning, cycle_completed=False)
            if _notification_runtime_budget_exhausted(started_at):
                pipeline_result = replace(
                    pipeline_result,
                    warnings=tuple(dict.fromkeys((
                        *pipeline_result.warnings,
                        "notification_runtime_budget_exhausted_after_pipeline",
                    ))),
                    partial_results=True,
                )
            if pre_stage_warnings:
                pipeline_result = replace(
                    pipeline_result,
                    warnings=tuple(dict.fromkeys((*pre_stage_warnings, *pipeline_result.warnings))),
                    partial_results=True,
                )
    finally:
        config.EVENT_ALPHA_IGNORE_PROVIDER_BACKOFF = previous_ignore_backoff
    pipeline_result = replace(
        pipeline_result,
        clock_status=clock_status,
        profile=profile_for_run,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
        partial_results=(
            pipeline_result.partial_results
            or _notification_warnings_indicate_partial(pipeline_result.warnings)
        ),
    )
    pipeline_result, hypothesis_store_result = _write_event_impact_hypotheses_for_run(
        pipeline_result,
        now=now,
        run_id=run_id,
        profile=profile_for_run,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
    )
    pipeline_result, incident_store_result = _write_event_incidents_for_run(
        pipeline_result,
        now=now,
        run_id=run_id,
        profile=profile_for_run,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
    )
    pipeline_result, core_store_result = _write_event_core_opportunities_for_run(
        pipeline_result,
        now=now,
        run_id=run_id,
        profile=profile_for_run,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
        card_paths=(),
    )
    latest_core_rows = event_core_opportunity_store.load_core_opportunities(
        _event_core_opportunity_store_config_from_runtime().path,
        latest_run=True,
        run_id=run_id,
    ).rows
    event_evidence_acquisition.reconcile_acquisition_core_ids(
        config.EVENT_ALPHA_EVIDENCE_ACQUISITION_PATH,
        latest_core_rows,
        run_id=run_id,
        profile=profile_for_run,
        artifact_namespace=artifact_namespace,
    )
    card_write = None
    if config.EVENT_RESEARCH_CARDS_AUTO_WRITE and pipeline_result.router_result is not None:
        watch_cfg = _event_watchlist_config_from_runtime()
        watchlist = event_watchlist.load_watchlist(watch_cfg.state_path or config.EVENT_WATCHLIST_STATE_PATH)
        card_write = event_research_cards.write_research_cards(
            config.EVENT_RESEARCH_CARDS_DIR,
            watchlist_entries=watchlist.entries,
            alert_rows=latest_core_rows,
            route_decisions=pipeline_result.router_result.decisions,
            selected_tiers=config.EVENT_RESEARCH_CARDS_WRITE_TIERS,
            limit=config.EVENT_RESEARCH_CARDS_WRITE_LIMIT,
            now=now,
            lineage_context=_event_alpha_card_lineage_context(
                run_id=run_id,
                profile=profile_for_run,
                run_mode=run_mode,
                artifact_namespace=artifact_namespace,
            ),
        )
        pipeline_result = replace(pipeline_result, research_card_paths=card_write.card_paths)
        event_core_opportunity_store.update_core_opportunity_card_links(
            _event_core_opportunity_store_config_from_runtime().path,
            card_write.card_paths,
            run_id=run_id,
        )
        latest_core_rows = event_core_opportunity_store.load_core_opportunities(
            _event_core_opportunity_store_config_from_runtime().path,
            latest_run=True,
            run_id=run_id,
        ).rows
        print(event_research_cards.format_card_write_result(card_write))
        print("")
    storage = Storage(config.DB_PATH)
    try:
        notification_plan = event_alpha_notifications.build_notification_plan(
            pipeline_result.router_result.decisions if pipeline_result.router_result else [],
            storage=storage,
            cfg=_event_alpha_notification_config_from_runtime(profile_for_run),
            now=now,
            include_health_heartbeat=True,
            core_opportunity_rows=latest_core_rows,
        )
    finally:
        storage.close()
    if pipeline_result.router_result is not None and notification_plan.all_decisions:
        pipeline_result = replace(
            pipeline_result,
            router_result=replace(
                pipeline_result.router_result,
                decisions=list(notification_plan.all_decisions),
            ),
        )
    send_result = event_alpha_pipeline.EventAlphaSendResult(
        requested=False,
        lane_items_attempted=notification_plan.lane_counts,
        lane_items_delivered={lane: 0 for lane in event_alpha_notifications.LANES},
        would_send_items=notification_plan.would_send_count,
        heartbeat_due=notification_plan.heartbeat_due,
        cooldown_blocks=dict(notification_plan.blocked_by_lane),
        notification_scope=notification_plan.notification_scope,
        notification_scope_value=notification_plan.scope_value,
        block_reason="send not requested",
        research_review_digest_enabled=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_ENABLED,
        research_review_digest_candidates=len(notification_plan.research_review_items),
        research_review_digest_would_send=notification_plan.lane_counts.get(
            event_alpha_notifications.LANE_RESEARCH_REVIEW_DIGEST,
            0,
        ),
        research_review_digest_sent=0,
        research_review_digest_block_reason=notification_plan.blocked_by_lane.get(
            event_alpha_notifications.LANE_RESEARCH_REVIEW_DIGEST
        ),
    )
    clock_send_blocker = _event_alpha_notify_fixed_clock_blocker(clock_status)
    if send and clock_send_blocker:
        send_result = event_alpha_pipeline.EventAlphaSendResult(
            requested=True,
            attempted=False,
            items_attempted=notification_plan.would_send_count,
            items_delivered=0,
            block_reason=clock_send_blocker,
            lane_items_attempted=notification_plan.lane_counts,
            lane_items_delivered={lane: 0 for lane in event_alpha_notifications.LANES},
            would_send_items=notification_plan.would_send_count,
            heartbeat_due=notification_plan.heartbeat_due,
            cooldown_blocks=dict(notification_plan.blocked_by_lane),
            notification_scope=notification_plan.notification_scope,
            notification_scope_value=notification_plan.scope_value,
            research_review_digest_enabled=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_ENABLED,
            research_review_digest_candidates=len(notification_plan.research_review_items),
            research_review_digest_would_send=notification_plan.lane_counts.get(
                event_alpha_notifications.LANE_RESEARCH_REVIEW_DIGEST,
                0,
            ),
            research_review_digest_sent=0,
            research_review_digest_block_reason=notification_plan.blocked_by_lane.get(
                event_alpha_notifications.LANE_RESEARCH_REVIEW_DIGEST
            ),
        )
        pipeline_result = replace(
            pipeline_result,
            warnings=tuple(dict.fromkeys((*pipeline_result.warnings, clock_send_blocker))),
            partial_results=True,
        )
        print(f"Event Alpha notify cycle send blocked: {clock_send_blocker}.")
    elif send:
        decisions = pipeline_result.router_result.decisions if pipeline_result.router_result else []
        send_result = _send_event_alpha_routed_digest(
            decisions,
            alert_cfg,
            now=now,
            profile=profile_for_run,
            pipeline_result=pipeline_result,
            card_path_by_alert_id=_card_paths_by_alert_id(
                pipeline_result.router_result.decisions if pipeline_result.router_result else [],
                pipeline_result.research_card_paths,
            ),
            include_health_heartbeat=True,
            clock_status=clock_status,
            delivery_cfg=delivery_cfg,
            run_id=run_id,
            namespace=artifact_namespace or lock_context.artifact_namespace,
            pause_state=pause_state,
            core_opportunity_rows=latest_core_rows,
        )
    else:
        print("Event Alpha notify cycle send not requested; pass --event-alert-send for guarded delivery or would-send accounting.")
    pipeline_result = replace(
        pipeline_result,
        send_requested=send_result.requested,
        send_attempted=send_result.attempted,
        send_success=send_result.success,
        send_items_attempted=send_result.items_attempted,
        send_items_delivered=send_result.items_delivered,
        send_block_reason=send_result.block_reason,
        send_lane_items_attempted=dict(send_result.lane_items_attempted),
        send_lane_items_delivered=dict(send_result.lane_items_delivered),
        send_would_send_items=send_result.would_send_items,
        send_heartbeat_due=send_result.heartbeat_due,
        send_heartbeat_sent=send_result.heartbeat_sent,
        send_cooldown_blocks=dict(send_result.cooldown_blocks),
        notification_scope=send_result.notification_scope,
        notification_scope_value=send_result.notification_scope_value,
        research_review_digest_enabled=send_result.research_review_digest_enabled,
        research_review_digest_candidates=send_result.research_review_digest_candidates,
        research_review_digest_would_send=send_result.research_review_digest_would_send,
        research_review_digest_sent=send_result.research_review_digest_sent,
        research_review_digest_block_reason=send_result.research_review_digest_block_reason,
        notification_lock_acquired=run_lock.acquired,
        notification_stale_lock_recovered=run_lock.stale_recovered,
        notification_delivery_records_written=send_result.delivery_records_written,
        notification_deliveries_delivered=send_result.deliveries_delivered,
        notification_deliveries_partial_delivered=send_result.deliveries_partial_delivered,
        notification_deliveries_failed=send_result.deliveries_failed,
        notification_deliveries_skipped_duplicate=send_result.deliveries_skipped_duplicate,
        notification_deliveries_skipped_in_flight=send_result.deliveries_skipped_in_flight,
        notification_deliveries_blocked=send_result.deliveries_blocked,
        notification_burn_in=True,
    )
    print(event_alpha_pipeline.format_event_alpha_pipeline_report(pipeline_result))
    store_cfg = _event_alpha_alert_store_config_from_runtime()
    delivery_rows = event_alpha_notification_delivery.load_delivery_records(delivery_cfg.path)
    store_result = event_alpha_alert_store.write_alert_snapshots(
        pipeline_result.alerts,
        cfg=store_cfg,
        now=now,
        router_result=pipeline_result.router_result,
        run_id=run_id,
        profile=profile_for_run,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
        delivery_rows=delivery_rows,
        research_card_paths=pipeline_result.research_card_paths,
        core_opportunity_rows=latest_core_rows,
    )
    pipeline_result = replace(
        pipeline_result,
        clock_status=clock_status,
        run_id=run_id,
        profile=profile_for_run,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
        run_ledger_path=str(_event_alpha_run_ledger_config_from_runtime().path),
        alert_store_path=str(store_cfg.path),
        watchlist_state_path=str(config.EVENT_WATCHLIST_STATE_PATH),
        research_cards_dir=str(config.EVENT_RESEARCH_CARDS_DIR),
        snapshot_write_attempted=store_result.attempted,
        snapshot_write_success=store_result.success,
        snapshot_rows_written=store_result.rows_written,
        snapshot_write_block_reason=store_result.block_reason,
        notification_burn_in=True,
    )
    print("")
    print(event_alpha_alert_store.format_alert_store_write_result(store_result))
    print(
        "Event impact hypotheses updated: "
        f"{hypothesis_store_result.path} rows={hypothesis_store_result.rows_written} "
        f"success={str(hypothesis_store_result.success).lower()}"
        + (f" block={hypothesis_store_result.block_reason}" if hypothesis_store_result.block_reason else "")
    )
    print(
        "Event incidents updated: "
        f"{incident_store_result.path} rows={incident_store_result.rows_written} "
        f"success={str(incident_store_result.success).lower()}"
        + (f" block={incident_store_result.block_reason}" if incident_store_result.block_reason else "")
    )
    print(event_core_opportunity_store.format_core_opportunity_store_write_result(core_store_result))
    pipeline_result = replace(
        pipeline_result,
        **_cryptopanic_stats_for_pipeline_result(
            pipeline_result,
            provider_health_path=_event_provider_health_config_from_runtime().path,
        ),
    )
    run_row = event_alpha_run_ledger.append_run_record(
        pipeline_result,
        cfg=_event_alpha_run_ledger_config_from_runtime(),
        profile=profile_for_run,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
        with_llm=with_llm,
        send_requested=send,
        notification_burn_in=True,
        success=True,
    )
    notification_row = event_alpha_notification_runs.append_notification_run(
        pipeline_result,
        cfg=_event_alpha_notification_runs_config_from_runtime(),
        profile=profile_for_run,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
        telegram_ready=bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_IDS),
        send_guard_enabled=bool(config.EVENT_ALERTS_ENABLED),
        plan=notification_plan,
        provider_health_rows=event_provider_health.load_provider_health(config.EVENT_PROVIDER_HEALTH_PATH),
    )
    print("")
    print(
        "Event Alpha notification run ledger updated: "
        f"{config.EVENT_ALPHA_RUN_LEDGER_PATH} run_id={run_row.get('run_id')}"
    )
    print(
        "Event Alpha notification summary updated: "
        f"{config.EVENT_ALPHA_NOTIFICATION_RUNS_PATH} run_id={notification_row.get('run_id')}"
    )
    provider_rows = event_provider_health.load_provider_health(config.EVENT_PROVIDER_HEALTH_PATH)
    print("")
    print(format_event_alpha_notification_next_steps(
        profile=profile_for_run,
        provider_health_rows=provider_rows,
        result=pipeline_result,
        notification_row=notification_row,
    ))
    if delivery_cfg is not None and pipeline_result.notification_delivery_records_written:
        print(
            "Event Alpha notification deliveries recorded: "
            f"{pipeline_result.notification_deliveries_delivered} delivered, "
            f"{pipeline_result.notification_deliveries_partial_delivered} partial_delivered, "
            f"{pipeline_result.notification_deliveries_failed} failed, "
            f"{pipeline_result.notification_deliveries_blocked} blocked, "
            f"{pipeline_result.notification_deliveries_skipped_duplicate} skipped_duplicate, "
            f"{pipeline_result.notification_deliveries_skipped_in_flight} skipped_in_flight "
            f"({delivery_cfg.path})."
        )
    # The run lock is released by the event_alpha_notify_cycle wrapper's finally,
    # so any exception above still releases it (best-effort).


def _record_skipped_notification_run(
    profile: str,
    *,
    run_id: str,
    run_mode: str,
    artifact_namespace: str | None,
    started_at: datetime,
) -> dict[str, object]:
    """Record a research-only notification-run row for a cycle skipped by an active lock."""
    skipped = SimpleNamespace(
        run_id=run_id,
        profile=profile,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
        notification_skipped_due_to_active_lock=True,
        notification_lock_acquired=False,
        warnings=("notification_cycle_skipped_active_lock",),
        cycle_completed=False,
    )
    return event_alpha_notification_runs.append_notification_run(
        skipped,
        cfg=_event_alpha_notification_runs_config_from_runtime(),
        profile=profile,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
        telegram_ready=bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_IDS),
        send_guard_enabled=bool(config.EVENT_ALERTS_ENABLED),
    )


def event_alpha_notify_preview(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
) -> None:
    """Preview day-1 notification readiness and lane cooldown state."""
    _setup_event_discovery_logging(verbose)
    selected_profile = profile_name or "notify_no_key"
    try:
        profile = _apply_event_alpha_profile(selected_profile)
    except ValueError as exc:
        print(str(exc))
        return
    provider = event_provider_status.build_event_discovery_provider_status(config)
    watchlist = event_watchlist.load_watchlist(config.EVENT_WATCHLIST_STATE_PATH)
    routed = event_alpha_router.route_watchlist(watchlist, cfg=_event_alpha_router_config_from_runtime())
    clock_status = _event_clock_status()
    now = _event_research_now()
    storage = Storage(config.DB_PATH)
    try:
        plan = event_alpha_notifications.build_notification_plan(
            routed.decisions,
            storage=storage,
            cfg=_event_alpha_notification_config_from_runtime(profile.name),
            now=now,
            include_health_heartbeat=True,
        )
    finally:
        storage.close()
    print(event_alpha_notifications.format_preview(
        profile=profile.name,
        artifact_namespace=config.EVENT_ALPHA_ARTIFACT_NAMESPACE or profile.name,
        telegram_ready=bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_IDS),
        provider_ready_event_sources=provider.ready_event_source_count,
        provider_ready_enrichment_sources=provider.ready_enrichment_count,
        llm_budget_status=_event_alpha_llm_budget_status(),
        plan=plan,
        card_auto_write=bool(config.EVENT_RESEARCH_CARDS_AUTO_WRITE),
        send_guard_enabled=bool(config.EVENT_ALERTS_ENABLED),
        partial_results_allowed=bool(config.EVENT_ALPHA_NOTIFY_ALLOW_PARTIAL_RESULTS),
        max_runtime_seconds=config.EVENT_ALPHA_NOTIFY_MAX_RUNTIME_SECONDS,
        provider_timeout_seconds=config.EVENT_ALPHA_NOTIFY_PROVIDER_TIMEOUT_SECONDS,
        fail_fast_on_dns=bool(config.EVENT_ALPHA_NOTIFY_FAST_FAIL_ON_DNS),
        provider_health_rows=event_provider_health.load_provider_health(config.EVENT_PROVIDER_HEALTH_PATH),
        clock_status=clock_status,
    ))


def event_alpha_notify_go_no_go(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_legacy_artifacts: bool = False,
) -> None:
    """Print a concise day-1 notification go/no-go decision."""
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(
            profile_name or "notify_no_key",
            artifact_namespace,
            include_test_artifacts=include_test_artifacts,
        )
    except ValueError as exc:
        print(str(exc))
        return
    artifact_namespace = artifact_namespace or context.artifact_namespace
    profile_name = profile_name or context.profile
    provider_status = event_provider_status.build_event_discovery_provider_status(config)
    clock_status = _event_clock_status()
    now = _event_research_now()
    storage = Storage(config.DB_PATH)
    try:
        watchlist = event_watchlist.load_watchlist(config.EVENT_WATCHLIST_STATE_PATH)
        routed = event_alpha_router.route_watchlist(watchlist, cfg=_event_alpha_router_config_from_runtime())
        plan = event_alpha_notifications.build_notification_plan(
            routed.decisions,
            storage=storage,
            cfg=_event_alpha_notification_config_from_runtime(profile_name),
            now=now,
            include_health_heartbeat=True,
        )
    finally:
        storage.close()
    artifacts = _event_alpha_local_artifacts(run_limit=250, latest_alerts=False)
    delivery_path = event_alpha_notification_delivery.deliveries_path_for_context(context)
    delivery_rows = event_alpha_notification_delivery.load_delivery_records(delivery_path)
    core_rows = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
        include_legacy=True,
    ).rows
    card_paths = [str(path) for path in _research_card_markdown_paths(context.research_cards_dir, include_index=True)]
    doctor = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=artifacts["runs"].rows,
        alert_rows=artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        outcome_rows=artifacts["outcome_rows"],
        hypothesis_rows=artifacts["hypotheses"].rows,
        core_opportunity_rows=core_rows,
        watchlist_rows=artifacts["watchlist"].entries,
        incident_rows=artifacts["incidents"].rows,
        evidence_acquisition_rows=event_evidence_acquisition.load_acquisition_results(context.evidence_acquisition_path),
        card_paths=card_paths,
        provider_health_rows=artifacts["provider_rows"],
        llm_budget_rows=artifacts["budget_rows"],
        delivery_rows=delivery_rows,
        profile=profile_name,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
        inspected_alert_store_path=context.alert_store_path,
        strict=True,
        delivery_strict_scope="latest_run",
    )
    readiness = event_alpha_send_readiness.build_send_readiness(
        profile=profile_name,
        artifact_namespace=artifact_namespace,
        run_rows=artifacts["runs"].rows,
        core_opportunity_rows=core_rows,
        alert_rows=artifacts["alerts"].rows,
        delivery_rows=delivery_rows,
        artifact_doctor=doctor,
        send_guard_enabled=bool(config.EVENT_ALERTS_ENABLED),
        telegram_ready=bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_IDS),
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    latest_delivery_rows = [
        row for row in event_alpha_notification_delivery.latest_rows_by_delivery(delivery_rows)
        if not readiness.latest_run_id or str(row.get("run_id") or "") == readiness.latest_run_id
    ]
    lock_status = event_alpha_run_lock.inspect_run_lock(
        context,
        stale_minutes=config.EVENT_ALPHA_NOTIFY_LOCK_STALE_MINUTES,
    )
    pause_state = _event_alpha_notification_pause_state(context)
    result = event_alpha_notification_go_no_go.build_go_no_go(
        profile=profile_name,
        artifact_namespace=artifact_namespace,
        telegram_ready=bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_IDS),
        send_guard_enabled=bool(config.EVENT_ALERTS_ENABLED),
        lock_status=lock_status,
        provider_status=provider_status,
        provider_health_rows=event_provider_health.load_provider_health(config.EVENT_PROVIDER_HEALTH_PATH),
        delivery_ledger_path=delivery_path,
        notification_run_ledger_path=context.notification_runs_path,
        research_cards_dir=context.research_cards_dir,
        artifact_doctor_status=doctor.status,
        cooldown_status=plan.cooldown_status,
        llm_budget_status=_event_alpha_llm_budget_status(),
        clock_status=clock_status,
        notifications_paused=pause_state.paused,
        pause_reason=pause_state.reason,
        send_readiness=readiness,
        delivery_rows=latest_delivery_rows,
        delivery_history_rows=delivery_rows,
    )
    print(_event_alpha_context_block(context))
    print(event_alpha_notification_go_no_go.format_go_no_go(result))


def event_alpha_environment_doctor_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
) -> None:
    """Print scheduled notification environment readiness for one profile."""
    _setup_event_discovery_logging(verbose)
    selected_profile = profile_name or "notify_no_key"
    try:
        profile = _apply_event_alpha_profile(selected_profile)
    except ValueError as exc:
        print(str(exc))
        return
    context = event_alpha_artifacts.context_from_profile(
        profile.name,
        run_mode=config.EVENT_ALPHA_RUN_MODE or None,
        base_dir=config.EVENT_ALPHA_ARTIFACT_BASE_DIR,
        artifact_namespace=config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
    )
    result = event_alpha_environment_doctor.build_environment_doctor(
        profile=profile,
        context=context,
        provider_status=event_provider_status.build_event_discovery_provider_status(config),
        provider_health_rows=event_provider_health.load_provider_health(context.provider_health_path),
        lock_path=event_alpha_run_lock.lock_path_for_context(context),
        delivery_ledger_path=event_alpha_notification_delivery.deliveries_path_for_context(context),
        notification_runs_path=context.notification_runs_path,
        research_cards_dir=context.research_cards_dir,
        telegram_token_present=bool(config.TELEGRAM_BOT_TOKEN),
        telegram_chat_ids_present=bool(config.TELEGRAM_CHAT_IDS),
        send_guard_enabled=bool(config.EVENT_ALERTS_ENABLED),
        llm_provider=config.EVENT_LLM_PROVIDER,
        llm_enabled=config.EVENT_LLM_ENABLED,
        llm_extractor_provider=config.EVENT_LLM_EXTRACTOR_PROVIDER,
        llm_extractor_enabled=config.EVENT_LLM_EXTRACTOR_ENABLED,
        openai_key_present=bool(config.OPENAI_API_KEY),
        clock_status=_event_clock_status(),
        cryptopanic_api_token_present=bool(config.EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN),
        python_executable=sys.executable,
        working_directory=str(config.DATA_DIR),
    )
    print(event_alpha_environment_doctor.format_environment_doctor(result))


def event_alpha_pause_notifications(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    reason: str | None = None,
) -> None:
    """Write a namespace-scoped notification pause file."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name or "notify_no_key", None)
    except ValueError as exc:
        print(str(exc))
        return
    state = event_alpha_notification_pause.write_pause_state(
        context,
        reason=reason or "operator pause",
        now=datetime.now(timezone.utc),
    )
    print(event_alpha_notification_pause.format_pause_state(state, action="pause"))


def event_alpha_resume_notifications(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    confirm: bool = False,
) -> None:
    """Clear the namespace-scoped notification pause file when confirmed."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name or "notify_no_key", None)
    except ValueError as exc:
        print(str(exc))
        return
    if not confirm:
        state = _event_alpha_notification_pause_state(context)
        print(event_alpha_notification_pause.format_pause_state(state, action="resume-refused"))
        print("Resume refused: pass --confirm to clear the pause file.")
        return
    state = event_alpha_notification_pause.clear_pause_state(context, confirm=True)
    print(event_alpha_notification_pause.format_pause_state(state, action="resume"))


def _event_alpha_health_guard_status_for_context(
    *,
    context: event_alpha_artifacts.EventAlphaArtifactContext,
    profile_name: str | None,
) -> str:
    artifacts = _event_alpha_local_artifacts(run_limit=100, latest_alerts=True)
    result = event_alpha_health_guard.evaluate_health_guard(
        run_rows=artifacts["runs"].rows,
        alert_rows=artifacts["alerts"].rows,
        watchlist_entries=artifacts["watchlist"].entries,
        provider_health_rows=artifacts["provider_rows"],
        llm_budget_rows=artifacts["budget_rows"],
        cfg=event_alpha_health_guard.EventAlphaHealthGuardConfig(
            max_run_age_hours=config.EVENT_ALPHA_MAX_RUN_AGE_HOURS,
            max_success_age_hours=config.EVENT_ALPHA_MAX_SUCCESS_AGE_HOURS,
            require_profile=profile_name or config.EVENT_ALPHA_HEALTH_REQUIRE_PROFILE,
        ),
        artifact_namespace=context.artifact_namespace,
    )
    return result.status


def event_alpha_scheduler_status_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
) -> None:
    """Print scheduler-facing run freshness, lock, and target status."""
    _setup_event_discovery_logging(verbose)
    selected_profile = profile_name or "notify_no_key"
    try:
        profile = _apply_event_alpha_profile(selected_profile)
    except ValueError as exc:
        print(str(exc))
        return
    context = _event_alpha_report_context(profile.name, None)
    runs = event_alpha_run_ledger.load_run_records(context.run_ledger_path, limit=100)
    delivery_path = event_alpha_notification_delivery.deliveries_path_for_context(context)
    deliveries = event_alpha_notification_delivery.load_delivery_records(delivery_path)
    lock_status = event_alpha_run_lock.inspect_run_lock(
        context,
        stale_minutes=config.EVENT_ALPHA_NOTIFY_LOCK_STALE_MINUTES,
    )
    make_text = (config.DATA_DIR / "Makefile").read_text(encoding="utf-8") if (config.DATA_DIR / "Makefile").exists() else ""
    target_exists = event_alpha_scheduler.scheduled_command(profile.name).split()[-1] + ":" in make_text
    result = event_alpha_scheduler.build_scheduler_status(
        profile=profile.name,
        artifact_namespace=context.artifact_namespace,
        run_rows=runs.rows,
        delivery_rows=deliveries,
        lock_status=lock_status,
        provider_health_rows=event_provider_health.load_provider_health(context.provider_health_path),
        health_guard_status=_event_alpha_health_guard_status_for_context(context=context, profile_name=profile.name),
        scheduled_target_exists=target_exists,
        now=datetime.now(timezone.utc),
    )
    print(_event_alpha_context_block(context))
    print(event_alpha_scheduler.format_scheduler_status(result))


def event_alpha_generate_launchd(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    out: str | None = None,
) -> None:
    """Write a dry-run launchd plist template for scheduled notification runs."""
    _setup_event_discovery_logging(verbose)
    selected_profile = profile_name or "notify_no_key"
    try:
        profile = _apply_event_alpha_profile(selected_profile)
    except ValueError as exc:
        print(str(exc))
        return
    text = event_alpha_scheduler.generate_launchd_plist(
        profile=profile.name,
        repo_path=config.DATA_DIR,
        python_path=sys.executable,
    )
    if out:
        path = Path(out).expanduser()
        if not path.is_absolute():
            path = config.DATA_DIR / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"Event Alpha launchd template written: {path}")
    else:
        print(text.rstrip())


def event_alpha_notification_slo_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_diagnostics: bool = False,
) -> None:
    """Print SLO-style notification freshness and delivery health."""
    _ = include_diagnostics
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name or "notify_no_key", artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    runs = event_alpha_notification_runs.load_notification_runs(context.notification_runs_path, limit=100)
    delivery_path = event_alpha_notification_delivery.deliveries_path_for_context(context)
    deliveries = event_alpha_notification_delivery.load_delivery_records(delivery_path)
    result = event_alpha_notification_slo.build_slo_report(
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        notification_runs=runs.rows,
        delivery_rows=deliveries,
        provider_health_rows=event_provider_health.load_provider_health(context.provider_health_path),
        now=datetime.now(timezone.utc),
    )
    print(_event_alpha_context_block(context))
    print(event_alpha_notification_slo.format_slo_report(result))


def event_alpha_export_notification_pack(
    out: str,
    *,
    verbose: bool = False,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    """Export a redacted zip of notification artifacts and operator reports."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name or "notify_no_key", artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    runs = event_alpha_notification_runs.load_notification_runs(context.notification_runs_path, limit=200)
    delivery_path = event_alpha_notification_delivery.deliveries_path_for_context(context)
    deliveries = event_alpha_notification_delivery.load_delivery_records(delivery_path)
    alerts = event_alpha_alert_store.load_alert_snapshots(context.alert_store_path, latest_only=False)
    provider_rows = event_provider_health.load_provider_health(context.provider_health_path)
    daily_brief = ""
    try:
        daily_brief = context.daily_brief_path.read_text(encoding="utf-8")
    except OSError:
        daily_brief = ""
    provider_status = event_provider_status.build_event_discovery_provider_status(config)
    lock_status = event_alpha_run_lock.inspect_run_lock(context, stale_minutes=config.EVENT_ALPHA_NOTIFY_LOCK_STALE_MINUTES)
    storage = Storage(config.DB_PATH)
    try:
        plan = event_alpha_notifications.build_notification_plan(
            [],
            storage=storage,
            cfg=_event_alpha_notification_config_from_runtime(context.profile),
            now=_event_research_now(),
            include_health_heartbeat=True,
        )
    finally:
        storage.close()
    pause_state = _event_alpha_notification_pause_state(context)
    go_no_go = event_alpha_notification_go_no_go.build_go_no_go(
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        telegram_ready=bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_IDS),
        send_guard_enabled=bool(config.EVENT_ALERTS_ENABLED),
        lock_status=lock_status,
        provider_status=provider_status,
        provider_health_rows=provider_rows,
        delivery_ledger_path=delivery_path,
        notification_run_ledger_path=context.notification_runs_path,
        research_cards_dir=context.research_cards_dir,
        artifact_doctor_status="not_run",
        cooldown_status=plan.cooldown_status,
        llm_budget_status=_event_alpha_llm_budget_status(),
        clock_status=_event_clock_status(),
        notifications_paused=pause_state.paused,
        pause_reason=pause_state.reason,
    )
    doctor = event_alpha_environment_doctor.build_environment_doctor(
        profile=context.profile,
        context=context,
        provider_status=provider_status,
        provider_health_rows=provider_rows,
        lock_path=event_alpha_run_lock.lock_path_for_context(context),
        delivery_ledger_path=delivery_path,
        notification_runs_path=context.notification_runs_path,
        research_cards_dir=context.research_cards_dir,
        telegram_token_present=bool(config.TELEGRAM_BOT_TOKEN),
        telegram_chat_ids_present=bool(config.TELEGRAM_CHAT_IDS),
        send_guard_enabled=bool(config.EVENT_ALERTS_ENABLED),
        llm_provider=config.EVENT_LLM_PROVIDER,
        llm_enabled=config.EVENT_LLM_ENABLED,
        llm_extractor_provider=config.EVENT_LLM_EXTRACTOR_PROVIDER,
        llm_extractor_enabled=config.EVENT_LLM_EXTRACTOR_ENABLED,
        openai_key_present=bool(config.OPENAI_API_KEY),
        clock_status=_event_clock_status(),
        cryptopanic_api_token_present=bool(config.EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN),
        python_executable=sys.executable,
        working_directory=str(config.DATA_DIR),
    )
    slo = event_alpha_notification_slo.build_slo_report(
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        notification_runs=runs.rows,
        delivery_rows=deliveries,
        provider_health_rows=provider_rows,
        now=datetime.now(timezone.utc),
    )
    result = event_alpha_notification_pack.export_notification_pack(
        out_path=out,
        context=context,
        notification_runs=runs.rows,
        delivery_rows=deliveries,
        alert_rows=alerts.rows,
        provider_health_rows=provider_rows,
        go_no_go_text=event_alpha_notification_go_no_go.format_go_no_go(go_no_go),
        environment_doctor_text=event_alpha_environment_doctor.format_environment_doctor(doctor),
        slo_text=event_alpha_notification_slo.format_slo_report(slo),
        daily_brief_text=daily_brief,
        cards_dir=context.research_cards_dir,
    )
    print(event_alpha_notification_pack.format_notification_pack_result(result))


def _event_alpha_llm_budget_status() -> str:
    return (
        f"provider={config.EVENT_LLM_PROVIDER}/{config.EVENT_LLM_EXTRACTOR_PROVIDER} "
        f"max_candidates={config.EVENT_LLM_MAX_CANDIDATES_PER_RUN} "
        f"max_extract_events={config.EVENT_LLM_EXTRACTOR_MAX_EVENTS_PER_RUN} "
        f"max_run={config.EVENT_LLM_MAX_CALLS_PER_RUN} max_day={config.EVENT_LLM_MAX_CALLS_PER_DAY} "
        f"parallel={config.EVENT_LLM_MAX_PARALLEL_CALLS} "
        f"max_cost_day={config.EVENT_LLM_MAX_ESTIMATED_COST_USD_PER_DAY:g} "
        f"cache_ttl_hours={config.EVENT_LLM_CACHE_TTL_HOURS:g}"
    )


def event_alpha_notification_checklist_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
) -> None:
    """Print day-1 notification startup readiness without sending."""
    _setup_event_discovery_logging(verbose)
    selected_profile = profile_name or "notify_no_key"
    try:
        profile = _apply_event_alpha_profile(selected_profile)
    except ValueError as exc:
        print(str(exc))
        return
    context = event_alpha_artifacts.context_from_profile(
        profile.name,
        run_mode=config.EVENT_ALPHA_RUN_MODE or None,
        base_dir=config.EVENT_ALPHA_ARTIFACT_BASE_DIR,
        artifact_namespace=config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
    )
    provider_status = event_provider_status.build_event_discovery_provider_status(config)
    clock_status = _event_clock_status()
    preflight = event_alpha_preflight.run_preflight(
        profile_name=profile.name,
        context=context,
        cfg=config,
        provider_status=provider_status,
        send_requested=True,
        clock_status=clock_status,
    )
    now = _event_research_now()
    storage = Storage(config.DB_PATH)
    try:
        watchlist = event_watchlist.load_watchlist(config.EVENT_WATCHLIST_STATE_PATH)
        routed = event_alpha_router.route_watchlist(watchlist, cfg=_event_alpha_router_config_from_runtime())
        plan = event_alpha_notifications.build_notification_plan(
            routed.decisions,
            storage=storage,
            cfg=_event_alpha_notification_config_from_runtime(profile.name),
            now=now,
            include_health_heartbeat=True,
        )
    finally:
        storage.close()
    artifacts = _event_alpha_local_artifacts(run_limit=250, latest_alerts=False)
    cards_dir = Path(config.EVENT_RESEARCH_CARDS_DIR)
    doctor = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=artifacts["runs"].rows,
        alert_rows=artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        outcome_rows=artifacts["outcome_rows"],
        hypothesis_rows=artifacts["hypotheses"].rows,
        core_opportunity_rows=event_core_opportunity_store.load_core_opportunities(context.core_opportunity_store_path, latest_run=True).rows,
        watchlist_rows=artifacts["watchlist"].entries,
        incident_rows=artifacts["incidents"].rows,
        evidence_acquisition_rows=event_evidence_acquisition.load_acquisition_results(context.evidence_acquisition_path),
        card_paths=[str(path) for path in _research_card_markdown_paths(cards_dir, include_index=True)],
        provider_health_rows=artifacts["provider_rows"],
        source_coverage_report_path=context.namespace_dir / "event_alpha_source_coverage.md",
        llm_budget_rows=artifacts["budget_rows"],
        profile=profile.name,
        artifact_namespace=context.artifact_namespace,
        inspected_alert_store_path=_event_alpha_alert_store_config_from_runtime().path,
        strict=False,
    )
    result = event_alpha_notification_checklist.build_notification_checklist(
        profile=profile.name,
        artifact_namespace=context.artifact_namespace,
        send_guard_enabled=bool(config.EVENT_ALERTS_ENABLED),
        telegram_ready=bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_IDS),
        provider_status=provider_status,
        provider_health_rows=artifacts["provider_rows"],
        plan=plan,
        llm_budget_status=_event_alpha_llm_budget_status(),
        card_auto_write=bool(config.EVENT_RESEARCH_CARDS_AUTO_WRITE),
        artifact_doctor_status=doctor.status,
        clock_status=clock_status,
        preflight_blockers=preflight.blockers,
        preflight_warnings=preflight.warnings,
        cryptopanic_api_token_present=bool(config.EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN),
    )
    print(event_alpha_notification_checklist.format_notification_checklist(result))


def event_alpha_send_test(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    ignore_notification_pause: bool = False,
) -> None:
    """Send one guarded research-only heartbeat without running the radar."""
    _setup_event_discovery_logging(verbose)
    selected_profile = profile_name or "notify_no_key"
    try:
        profile = _apply_event_alpha_profile(selected_profile)
    except ValueError as exc:
        print(str(exc))
        return
    context = event_alpha_artifacts.context_from_profile(
        profile.name,
        run_mode=config.EVENT_ALPHA_RUN_MODE or None,
        base_dir=config.EVENT_ALPHA_ARTIFACT_BASE_DIR,
        artifact_namespace=config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
    )
    pause_state = _event_alpha_notification_pause_state(context)
    if pause_state.paused and not ignore_notification_pause:
        print(f"Refusing Event Alpha test send: notifications paused ({pause_state.reason}).")
        return
    if not config.EVENT_ALERTS_ENABLED:
        print("Refusing Event Alpha test send: set RSI_EVENT_ALERTS_ENABLED=1 to opt in.")
        return
    if config.EVENT_ALERT_MODE != "research_only":
        print("Refusing Event Alpha test send: RSI_EVENT_ALERT_MODE must remain research_only.")
        return
    if not (config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_IDS):
        print("Refusing Event Alpha test send: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_IDS are required.")
        return
    clock_blocker = _event_alpha_notify_fixed_clock_blocker(_event_clock_status())
    if clock_blocker:
        print(f"Refusing Event Alpha test send: {clock_blocker}.")
        return
    sent = send_telegram(
        event_alpha_notifications.format_health_heartbeat(profile=profile.name),
        parse_mode="HTML",
        chat_ids=config.TELEGRAM_CHAT_IDS,
    )
    if sent:
        print("Event Alpha research-only test heartbeat sent.")
    else:
        print("Event Alpha research-only test heartbeat was not delivered.")


def event_alpha_telegram_recipient_check_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
) -> None:
    """Send a guarded one-message diagnostic to each Telegram recipient."""
    _setup_event_discovery_logging(verbose)
    selected_profile = profile_name or "notify_no_key"
    try:
        profile = _apply_event_alpha_profile(selected_profile)
    except ValueError as exc:
        print(str(exc))
        return
    storage = Storage(config.DB_PATH)
    try:
        recipients = storage.active_subscribers() or config.TELEGRAM_CHAT_IDS
    finally:
        storage.close()
    result = event_alpha_telegram_recipient_check.run_recipient_check(
        recipients,
        send_guard_enabled=bool(config.EVENT_ALERTS_ENABLED and config.EVENT_ALERT_MODE == "research_only"),
        telegram_token_present=bool(config.TELEGRAM_BOT_TOKEN),
        profile=profile.name,
        send_one=lambda message, chat_id: send_telegram_structured(
            message,
            parse_mode=None,
            chat_ids=[chat_id],
        ),
    )
    print(event_alpha_telegram_recipient_check.format_recipient_check(result))


def _card_paths_by_alert_id(
    decisions: Iterable[event_alpha_router.EventAlphaRouteDecision],
    card_paths: Iterable[Path],
) -> dict[str, str]:
    by_stem = {Path(path).stem: str(path) for path in card_paths}
    out: dict[str, str] = {}
    for decision in decisions:
        path = by_stem.get(decision.card_id)
        if path is None:
            candidate = Path(config.EVENT_RESEARCH_CARDS_DIR) / f"{decision.card_id}.md"
            path = str(candidate)
        out[decision.alert_id] = path
    return out


class _FixtureNotificationStorage:
    def __init__(self) -> None:
        self.meta: dict[str, str] = {}

    def get_meta(self, key: str) -> str | None:
        return self.meta.get(key)

    def set_meta(self, key: str, value: str) -> None:
        self.meta[key] = value


def _write_fixture_alert_snapshot(
    context: event_alpha_artifacts.EventAlphaArtifactContext,
    *,
    entry: event_watchlist.EventWatchlistEntry,
    decision: event_alpha_router.EventAlphaRouteDecision,
    run_id: str,
    observed_at: datetime,
    core_row: Mapping[str, Any] | None = None,
) -> Path:
    path = context.alert_store_path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    core = dict(core_row or {})
    score_components = dict(entry.latest_score_components)
    core_id = str(core.get("core_opportunity_id") or score_components.get("core_opportunity_id") or "").strip()
    if core_id:
        score_components.setdefault("core_opportunity_id", core_id)
    row = {
        "schema_version": event_alpha_alert_store.ALERT_STORE_SCHEMA_VERSION,
        "row_type": "event_alpha_alert_snapshot",
        "snapshot_id": f"{observed_at.isoformat()}|{entry.key}",
        "alert_key": entry.key,
        "alert_id": decision.alert_id,
        "card_id": decision.card_id,
        "cluster_id": entry.cluster_id,
        "observed_at": observed_at.isoformat(),
        "run_id": run_id,
        "profile": context.profile,
        "run_mode": context.run_mode,
        "artifact_namespace": context.artifact_namespace,
        "event_id": entry.event_id,
        "event_name": entry.latest_event_name,
        "event_type": "fixture_notification_smoke",
        "event_time": entry.event_time,
        "external_asset": entry.external_asset,
        "asset_coin_id": entry.coin_id,
        "asset_symbol": entry.symbol,
        "asset_name": entry.symbol,
        "relationship_type": entry.relationship_type,
        "asset_role": "proxy_instrument",
        "source": entry.latest_source,
        "source_count": entry.source_count,
        "tier": entry.latest_tier,
        "opportunity_score": entry.latest_score,
        "score_components": score_components,
        "playbook_type": entry.latest_playbook_type,
        "rule_playbook_type": entry.latest_rule_playbook_type,
        "effective_playbook_type": entry.latest_effective_playbook_type,
        "playbook_score": entry.latest_playbook_score,
        "playbook_action": entry.latest_playbook_action,
        "expected_direction": "review_only",
        "primary_horizon": "manual",
        "success_metric": "manual_feedback",
        "market_price": entry.latest_market_snapshot.get("price"),
        "return_24h_at_alert": entry.latest_market_snapshot.get("return_24h"),
        "volume_zscore_24h": entry.latest_market_snapshot.get("volume_zscore_24h"),
        "route": decision.route.value,
        "route_alertable": decision.alertable,
        "route_reason": decision.reason,
        "reason": decision.reason,
        "core_opportunity_id": core_id or None,
        "feedback_target": core_id or decision.alert_id,
        "feedback_target_type": "core_opportunity_id" if core_id else "alert_id",
        "final_opportunity_level": core.get("final_opportunity_level") or core.get("opportunity_level") or "high_priority",
        "opportunity_level": core.get("final_opportunity_level") or core.get("opportunity_level") or "high_priority",
        "opportunity_score_final": core.get("opportunity_score_final") or entry.latest_score,
        "final_route_after_quality_gate": core.get("final_route_after_quality_gate") or decision.route.value,
        "final_tier_after_quality_gate": core.get("final_tier_after_quality_gate") or decision.route.value,
        "alertable_after_quality_gate": bool(core.get("alertable_after_quality_gate", decision.alertable)),
        "final_state_after_quality_gate": core.get("final_state_after_quality_gate") or entry.state,
        "impact_path_type": core.get("impact_path_type") or entry.impact_path_type or entry.relationship_type,
        "candidate_role": core.get("candidate_role") or entry.candidate_role or "proxy_venue",
        "impact_path_strength": core.get("impact_path_strength") or entry.impact_path_strength or "strong",
        "source_class": core.get("source_class") or entry.source_class,
        "evidence_specificity": core.get("evidence_specificity") or entry.evidence_specificity,
        "evidence_quality_score": core.get("evidence_quality_score") or entry.evidence_quality_score,
        "market_confirmation_score": core.get("market_confirmation_score") if core.get("market_confirmation_score") is not None else entry.market_confirmation_score,
        "market_confirmation_level": core.get("market_confirmation_level") or entry.market_confirmation_level,
        "market_context_freshness_status": core.get("market_context_freshness_status") or entry.market_context_freshness_status,
        "market_context_age_hours": core.get("market_context_age_hours") if core.get("market_context_age_hours") is not None else 0,
        "market_context_stale": bool(core.get("market_context_stale", False)),
        "market_context_freshness_cap_applied": bool(core.get("market_context_freshness_cap_applied", False)),
        "evidence_acquisition_status": core.get("evidence_acquisition_status"),
        "acquisition_confirmation_status": core.get("acquisition_confirmation_status"),
        "accepted_evidence_count": (
            core.get("accepted_evidence_count")
            if core.get("accepted_evidence_count") is not None
            else core.get("evidence_acquisition_accepted_count")
        ),
        "source_pack": core.get("source_pack"),
        "opportunity_verdict_reasons": core.get("opportunity_verdict_reasons") or core.get("verdict_reason_codes") or ["fixture_notification_smoke"],
        "why_local_only": core.get("why_local_only") or ("not_local_only" if decision.alertable else "rejected_results_only_not_confirmation"),
        "why_not_watchlist": core.get("why_not_watchlist") or ("already_high_priority" if decision.alertable else "accepted_confirmation_missing"),
        "manual_verification_items": core.get("manual_verification_items") or ["review the local fixture card before acting"],
        "upgrade_requirements": core.get("upgrade_requirements") or [],
        "downgrade_warnings": core.get("downgrade_warnings") or ["conflicting_evidence"],
        "verify": ["fixture smoke confirms fake-sender notification plumbing only"],
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True, separators=(",", ":")))
        fh.write("\n")
    return path


def event_alpha_status(profile_name: str | None = None, verbose: bool = False) -> None:
    """Print profile-aware Event Alpha operational status."""
    _setup_event_discovery_logging(verbose)
    try:
        profile = _apply_event_alpha_profile(profile_name)
    except ValueError as exc:
        print(str(exc))
        return
    provider_report = event_provider_status.build_event_discovery_provider_status(config)
    clock_status = _event_clock_status()
    lines = [
        "=" * 76,
        "EVENT ALPHA STATUS (research-only; profile-aware)",
        "=" * 76,
        f"profile: {(profile.name if profile else profile_name) or 'default'}",
        f"artifact_namespace: {config.EVENT_ALPHA_ARTIFACT_NAMESPACE or 'legacy/default'}",
        f"run_mode: {config.EVENT_ALPHA_RUN_MODE or 'legacy'}",
        f"artifact_base_dir: {config.EVENT_ALPHA_ARTIFACT_BASE_DIR}",
        _event_alpha_clock_line(clock_status),
        f"send requested by profile: {str(bool(profile and profile.send)).lower()}",
        f"send enabled env: {str(bool(config.EVENT_ALERTS_ENABLED)).lower()}",
        f"LLM relationship: provider={config.EVENT_LLM_PROVIDER} mode={config.EVENT_LLM_MODE} enabled={str(bool(config.EVENT_LLM_ENABLED)).lower()}",
        (
            "LLM extractor: "
            f"provider={config.EVENT_LLM_EXTRACTOR_PROVIDER} mode={config.EVENT_LLM_EXTRACTOR_MODE} "
            f"enabled={str(bool(config.EVENT_LLM_EXTRACTOR_ENABLED)).lower()}"
        ),
        (
            "LLM catalyst frames: "
            f"provider={config.EVENT_LLM_CATALYST_FRAMES_PROVIDER} "
            f"enabled={str(bool(config.EVENT_LLM_CATALYST_FRAMES_ENABLED)).lower()} "
            f"max_rows={config.EVENT_LLM_CATALYST_FRAMES_MAX_ROWS_PER_RUN} "
            f"only_ambiguous={str(bool(config.EVENT_LLM_CATALYST_FRAMES_ONLY_AMBIGUOUS)).lower()}"
        ),
        (
            "LLM budget: "
            f"max_candidates={config.EVENT_LLM_MAX_CANDIDATES_PER_RUN} "
            f"max_extract_events={config.EVENT_LLM_EXTRACTOR_MAX_EVENTS_PER_RUN} "
            f"max_run={config.EVENT_LLM_MAX_CALLS_PER_RUN} max_day={config.EVENT_LLM_MAX_CALLS_PER_DAY} "
            f"parallel={config.EVENT_LLM_MAX_PARALLEL_CALLS} "
            f"max_cost_day={config.EVENT_LLM_MAX_ESTIMATED_COST_USD_PER_DAY:g} "
            f"timeouts={config.EVENT_LLM_OPENAI_TIMEOUT:g}/{config.EVENT_LLM_EXTRACTOR_OPENAI_TIMEOUT:g}s "
            f"cache_ttl_hours={config.EVENT_LLM_CACHE_TTL_HOURS:g} "
            f"ledger={config.EVENT_LLM_BUDGET_LEDGER_PATH}"
        ),
        f"catalyst providers: {', '.join(config.EVENT_CATALYST_SEARCH_PROVIDERS) or 'none'}",
        (
            "source_enrichment: "
            f"enabled={str(bool(config.EVENT_SOURCE_ENRICHMENT_ENABLED)).lower()} "
            f"max_rows={config.EVENT_SOURCE_ENRICHMENT_MAX_ROWS_PER_RUN} "
            f"timeout={config.EVENT_SOURCE_ENRICHMENT_TIMEOUT_SECONDS:g}s "
            f"cache={config.EVENT_SOURCE_ENRICHMENT_CACHE_DIR}"
        ),
        f"watchlist_state_path: {config.EVENT_WATCHLIST_STATE_PATH}",
        (
            "watchlist_monitor: "
            f"enabled={str(bool(config.EVENT_WATCHLIST_MONITOR_ENABLED)).lower()} "
            f"route_updates={str(bool(config.EVENT_WATCHLIST_MONITOR_ROUTE_UPDATES)).lower()} "
            f"market_source={config.EVENT_WATCHLIST_MONITOR_MARKET_SOURCE} "
            f"derivatives_source={config.EVENT_WATCHLIST_MONITOR_DERIVATIVES_SOURCE} "
            f"supply_source={config.EVENT_WATCHLIST_MONITOR_SUPPLY_SOURCE} "
            f"targeted={str(bool(config.EVENT_WATCHLIST_MONITOR_TARGETED_LOOKUP)).lower()} "
            f"max_assets={config.EVENT_WATCHLIST_MONITOR_MAX_ASSETS} "
            f"enrichment_max_assets={config.EVENT_WATCHLIST_MONITOR_ENRICHMENT_MAX_ASSETS} "
            f"cache_ttl={config.EVENT_WATCHLIST_MONITOR_MARKET_CACHE_TTL_SECONDS}s "
            f"market_path={config.EVENT_WATCHLIST_MONITOR_MARKET_PATH or config.EVENT_DISCOVERY_UNIVERSE_PATH or 'cycle'}"
        ),
        f"alert_store_path: {config.EVENT_ALPHA_ALERT_STORE_PATH}",
        f"run_ledger_path: {config.EVENT_ALPHA_RUN_LEDGER_PATH}",
        f"impact_hypothesis_store_path: {config.EVENT_IMPACT_HYPOTHESIS_STORE_PATH}",
        (
            "health_guard: "
            f"max_run_age_hours={config.EVENT_ALPHA_MAX_RUN_AGE_HOURS:g} "
            f"max_success_age_hours={config.EVENT_ALPHA_MAX_SUCCESS_AGE_HOURS:g} "
            f"require_profile={config.EVENT_ALPHA_HEALTH_REQUIRE_PROFILE or 'none'}"
        ),
        f"missed_path: {config.EVENT_ALPHA_MISSED_PATH}",
        (
            "calibration_priors: "
            f"enabled={str(bool(config.EVENT_ALPHA_APPLY_PRIORS)).lower()} "
            f"path={config.EVENT_ALPHA_PRIORS_PATH} "
            f"bounds={config.EVENT_ALPHA_PRIORS_MIN_MULTIPLIER:g}-{config.EVENT_ALPHA_PRIORS_MAX_MULTIPLIER:g}"
        ),
        (
            "provider_health: "
            f"path={config.EVENT_PROVIDER_HEALTH_PATH} "
            f"max_failures={config.EVENT_PROVIDER_MAX_CONSECUTIVE_FAILURES} "
            f"backoff_minutes={config.EVENT_PROVIDER_BACKOFF_MINUTES:g} "
            f"fail_fast_dns={str(bool(config.EVENT_PROVIDER_FAIL_FAST_ON_DNS)).lower()}"
        ),
        f"daily_brief_path: {config.EVENT_ALPHA_DAILY_BRIEF_PATH}",
    ]
    if profile:
        lines.append("artifact policy:")
        for key, value in event_alpha_profiles.artifact_policy(profile).items():
            lines.append(f"  {key}={value}")
    lines.extend([
        "",
        event_provider_status.format_event_discovery_provider_status(provider_report),
        "",
        event_provider_health.format_provider_health_report(
            event_provider_health.load_provider_health(config.EVENT_PROVIDER_HEALTH_PATH)
        ),
    ])
    print("\n".join(lines))


def event_alpha_preflight_report(
    profile_name: str | None = None,
    *,
    artifact_namespace: str | None = None,
    send_requested: bool = False,
    verbose: bool = False,
) -> None:
    """Print profile-scoped Event Alpha preflight blockers before a run."""
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(profile_name, artifact_namespace)
    except ValueError as exc:
        print(event_alpha_preflight.format_preflight_report(
            event_alpha_preflight.EventAlphaPreflightResult(
                ready=False,
                profile=profile_name or "unknown",
                artifact_namespace=artifact_namespace or "unknown",
                run_mode=config.EVENT_ALPHA_RUN_MODE or "unknown",
                paths={},
                provider_ready_event_sources=0,
                provider_ready_enrichment_sources=0,
                blockers=(str(exc),),
                warnings=(),
                recommended_next_command=f"make event-alpha-status PROFILE={profile_name or 'no_key_live'}",
            )
        ))
        return
    provider_report = event_provider_status.build_event_discovery_provider_status(config)
    clock_status = _event_clock_status()
    result = event_alpha_preflight.run_preflight(
        profile_name=profile_name,
        context=context,
        cfg=config,
        provider_status=provider_report,
        send_requested=send_requested,
        clock_status=clock_status,
    )
    print(event_alpha_preflight.format_preflight_report(result))


def event_alpha_runs_report(
    path: str | None = None,
    limit: int = 20,
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    """Print recent Event Alpha cycle run ledger rows."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    cfg = event_alpha_run_ledger.EventAlphaRunLedgerConfig(
        path=_event_alpha_report_path(path, context.run_ledger_path)
    )
    result = event_alpha_run_ledger.load_run_records(cfg.path, limit=limit)
    print(_event_alpha_context_block(context))
    print(event_alpha_run_ledger.format_run_ledger_report(result))


def event_impact_hypotheses_report(
    path: str | None = None,
    limit: int = 100,
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    latest_run: bool = False,
    run_id: str | None = None,
    since: str | None = None,
    include_legacy: bool = True,
) -> None:
    """Print stored Event Impact Hypothesis rows for a profile/namespace."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    target_path = _event_alpha_report_path(path, context.impact_hypothesis_store_path)
    result = event_impact_hypothesis_store.load_impact_hypotheses(
        target_path,
        limit=limit,
        latest_run=latest_run,
        run_id=run_id,
        since=since,
        include_legacy=include_legacy,
    )
    watchlist = event_watchlist.load_watchlist(context.watchlist_state_path)
    print(_event_alpha_context_block(context))
    stale_warning = _event_alpha_stale_quality_warning(context)
    print(event_impact_hypothesis_store.format_impact_hypotheses_store_report(
        result,
        watchlist_rows=[entry.__dict__ for entry in watchlist.entries],
        stale_quality_warning=stale_warning,
    ))


def event_impact_hypotheses_inbox(
    path: str | None = None,
    limit: int = 100,
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    """Print stored Event Impact Hypothesis rows that need operator review."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    target_path = _event_alpha_report_path(path, context.impact_hypothesis_store_path)
    result = event_impact_hypothesis_store.load_impact_hypotheses(target_path, limit=limit)
    print(_event_alpha_context_block(context))
    print(event_impact_hypothesis_store.format_impact_hypotheses_inbox(result))


def event_incidents_report(
    path: str | None = None,
    limit: int = 100,
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    latest_run: bool = False,
    run_id: str | None = None,
    include_legacy: bool = True,
    include_diagnostic: bool = False,
    include_raw: bool = False,
    include_external_context: bool = False,
) -> None:
    """Print stored canonical incident rows for a profile/namespace."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    target_path = _event_alpha_report_path(path, context.incident_store_path)
    result = event_incident_store.load_incidents(
        target_path,
        limit=limit,
        latest_run=latest_run,
        run_id=run_id,
        include_legacy=include_legacy,
        include_diagnostic=include_diagnostic,
        include_raw=include_raw,
        include_external_context=include_external_context,
    )
    print(_event_alpha_context_block(context))
    print(event_incident_store.format_incidents_report(result))


def event_impact_hypothesis_smoke(verbose: bool = False, event_now: str | datetime | None = None) -> None:
    """Run an offline smoke proving sector hypothesis validation stays RADAR-only."""
    import tempfile

    _setup_event_discovery_logging(verbose)
    now = _event_research_now(event_now) or datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="smoke-spacex-sector",
        provider="fixture_rss",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/spacex-sector",
        title="SpaceX pre-IPO exposure heats up",
        body="Tokenized stock venues may see attention around SpaceX pre-IPO markets.",
        raw_json={
            "event": {
                "event_id": "smoke-spacex-sector",
                "event_name": "SpaceX pre-IPO exposure heats up",
                "event_type": "ipo_proxy",
                "event_time": "2026-06-20T13:30:00Z",
                "event_time_confidence": 0.85,
                "external_asset": "SpaceX",
                "description": "Tokenized stock venues may see attention around SpaceX pre-IPO markets.",
                "confidence": 0.88,
            }
        },
        source_confidence=0.88,
        content_hash="smoke-spacex-sector",
    )
    validation = RawDiscoveredEvent(
        raw_id="smoke-velvet-validation",
        provider="fixture_search",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/velvet-spacex",
        title="VELVET opens SpaceX pre-IPO exposure",
        body="Velvet Capital users can trade tokenized stock style exposure to SpaceX.",
        raw_json={},
        source_confidence=0.92,
        content_hash="smoke-velvet-validation",
    )
    normalized = NormalizedEvent(
        event_id="smoke-spacex-sector",
        raw_ids=(raw.raw_id,),
        event_name=raw.title,
        event_type="ipo_proxy",
        event_time=now,
        event_time_confidence=0.85,
        first_seen_time=now,
        source=raw.provider,
        source_urls=(raw.source_url,),
        external_asset="SpaceX",
        description=raw.body,
        confidence=0.88,
    )
    discovery_result = EventDiscoveryResult(
        raw_events=(raw,),
        normalized_events=(normalized,),
        links=(),
        classifications=(),
        candidates=(),
    )
    provider = event_catalyst_search.FixtureCatalystSearchProvider(
        rows_by_query={"VELVET SpaceX pre-IPO exposure": (validation,)}
    )
    with tempfile.TemporaryDirectory() as tmp:
        pipe = event_alpha_pipeline.run_event_alpha_pipeline(
            discovery_result,
            alert_cfg=event_alerts.EventAlertConfig(),
            now=now,
            hypothesis_search_provider=provider,
            hypothesis_search_cfg=event_catalyst_search.EventImpactHypothesisSearchConfig(
                enabled=True,
                max_hypotheses=5,
                max_queries_per_hypothesis=4,
                min_confidence=0.50,
                min_result_confidence=0.50,
            ),
            watchlist_cfg=event_watchlist.EventWatchlistConfig(
                enabled=True,
                state_path=Path(tmp) / "watchlist.jsonl",
            ),
            router_cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True),
            refresh_watchlist=True,
            route=True,
        )
    entries = tuple(pipe.watchlist_result.entries if pipe.watchlist_result else ())
    velvet_radar = any(entry.symbol == "VELVET" and entry.state == event_watchlist.EventWatchlistState.RADAR.value for entry in entries)
    triggered = any(entry.state == event_watchlist.EventWatchlistState.TRIGGERED_FADE.value for entry in entries)
    print(event_alpha_pipeline.format_event_alpha_pipeline_report(pipe))
    print("")
    print("Event Impact Hypothesis smoke:")
    print(f"- sector_hypotheses={len(pipe.impact_hypotheses)}")
    print(f"- hypothesis_search_results={pipe.hypothesis_search_results}")
    print(f"- velvet_radar={str(velvet_radar).lower()}")
    print(f"- triggered_fade={str(triggered).lower()}")
    print("- research_only=true")
    if not velvet_radar or triggered:
        raise SystemExit(1)


def event_alpha_notification_runs_report(
    path: str | None = None,
    limit: int = 20,
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    """Print recent Event Alpha notification-cycle summary rows."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    cfg = event_alpha_notification_runs.EventAlphaNotificationRunsConfig(
        path=_event_alpha_report_path(path, context.notification_runs_path)
    )
    result = event_alpha_notification_runs.load_notification_runs(cfg.path, limit=limit)
    print(_event_alpha_context_block(context))
    print(event_alpha_notification_runs.format_notification_runs_report(result))


def event_alpha_notification_deliveries_report(
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    verbose: bool = False,
) -> None:
    """Print the research-only notification delivery ledger for one profile/namespace."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    path = event_alpha_notification_delivery.deliveries_path_for_context(context)
    rows = event_alpha_notification_delivery.load_delivery_records(path)
    print(_event_alpha_context_block(context))
    print("")
    print(
        event_alpha_notification_delivery.format_delivery_report(
            rows,
            path=path,
            profile=context.profile,
            namespace=context.artifact_namespace,
        )
    )


def event_alpha_notification_retry_failed(
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    confirm: bool = False,
    verbose: bool = False,
) -> None:
    """List failed notification deliveries; resend is a guarded TODO scaffold.

    The delivery ledger keeps redacted metadata only (no full message body), so
    automated resend is intentionally not wired yet. This stays dry-run unless
    ``--confirm`` is passed, and even then it only points back at the notify
    cycle. It never trades, paper trades, or routes RSI rows.
    """
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    path = event_alpha_notification_delivery.deliveries_path_for_context(context)
    rows = event_alpha_notification_delivery.load_delivery_records(path)
    failed = event_alpha_notification_delivery.failed_deliveries(rows)
    print("=" * 76)
    print("EVENT ALPHA NOTIFICATION RETRY (research-only; dry-run scaffold)")
    print("=" * 76)
    print(f"profile: {context.profile} · namespace: {context.artifact_namespace}")
    print(f"path: {path}")
    print(f"failed deliveries: {len(failed)}")
    for row in failed[:20]:
        print(
            f"- {row.get('attempted_at') or 'unknown'} lane={row.get('lane') or 'unknown'} "
            f"alert_id={row.get('alert_id') or 'n/a'} error={row.get('error_message_safe') or 'unknown'}"
        )
    if not failed:
        print("No failed deliveries to retry.")
        return
    if not confirm:
        print("")
        print("Dry-run only. Re-run with --confirm to proceed (still requires RSI_EVENT_ALERTS_ENABLED=1 to send).")
        return
    print("")
    print(
        "Automated resend is not implemented yet (TODO): the deliveries ledger stores redacted "
        "metadata only, not message bodies. Re-run `make event-alpha-notify-no-key-scheduled` "
        "(or notify_llm) to regenerate and resend due notifications under the run lock."
    )


def event_alpha_provider_health_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    """Print profile-scoped provider health/backoff rows."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    rows = event_provider_health.load_provider_health(context.provider_health_path)
    print(_event_alpha_context_block(context))
    print(f"provider_health_path: {context.provider_health_path}")
    print(event_provider_health.format_provider_health_report(rows))


def event_alpha_cryptopanic_preflight(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    """Print a redacted CryptoPanic readiness report for Event Alpha runs."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name or "notify_llm_deep", artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    provider_report = event_provider_status.build_event_discovery_provider_status(config)
    provider_rows = event_provider_health.load_provider_health(context.provider_health_path)
    report = event_alpha_cryptopanic.build_cryptopanic_preflight(
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        provider_status_report=provider_report,
        provider_health_rows=provider_rows,
        provider_health_path=context.provider_health_path,
        token_configured=bool(config.EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN),
        live_enabled=bool(config.EVENT_DISCOVERY_CRYPTOPANIC_LIVE or config.EVENT_DISCOVERY_CRYPTOPANIC_PATH),
        catalyst_search_providers=tuple(str(item) for item in config.EVENT_CATALYST_SEARCH_PROVIDERS),
        no_send=not bool(config.EVENT_ALERTS_ENABLED),
    )
    print(_event_alpha_context_block(context))
    print(event_alpha_cryptopanic.format_cryptopanic_preflight(report))


def event_alpha_source_coverage_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    """Print source-pack coverage for Event Alpha research artifacts."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name or "no_key_live", artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    provider_report = event_provider_status.build_event_discovery_provider_status(config)
    provider_rows = event_provider_health.load_provider_health(context.provider_health_path)
    acquisition_rows = event_evidence_acquisition.load_acquisition_results(context.evidence_acquisition_path)
    core_rows = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
        include_legacy=True,
    ).rows
    report = event_alpha_source_coverage.build_source_coverage_report(
        provider_status_report=provider_report,
        provider_health_rows=provider_rows,
        evidence_acquisition_rows=acquisition_rows,
        core_opportunity_rows=core_rows,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
    )
    report_text = event_alpha_source_coverage.format_source_coverage_report(report)
    source_coverage_path = context.namespace_dir / "event_alpha_source_coverage.md"
    source_coverage_json_path = context.namespace_dir / "event_alpha_source_coverage.json"
    try:
        context.namespace_dir.mkdir(parents=True, exist_ok=True)
        source_coverage_path.write_text(report_text + "\n", encoding="utf-8")
        source_coverage_json_path.write_text(
            json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        print(f"warning: source coverage artifact write failed: {exc}")
    print(_event_alpha_context_block(context))
    print(f"source_coverage_report_path: {source_coverage_path}")
    print(f"source_coverage_json_path: {source_coverage_json_path}")
    print(report_text)


def event_alpha_provider_health_reset(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    provider_key: str | None = None,
    service: str | None = None,
    role: str | None = None,
    reset_all: bool = False,
    confirm: bool = False,
) -> None:
    """Clear selected provider health backoff state without calling providers."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    if not confirm:
        print("Provider health reset refused: pass --confirm to clear local backoff state.")
        return
    rows = event_provider_health.load_provider_health(context.provider_health_path)
    try:
        updated, result = event_provider_health.reset_provider_health_rows(
            rows,
            provider_key=provider_key,
            service=service,
            role=role,
            reset_all=reset_all,
        )
    except ValueError as exc:
        print(f"Provider health reset failed: {exc}")
        return
    event_provider_health.write_provider_health(context.provider_health_path, updated)
    print(_event_alpha_context_block(context))
    print(event_provider_health.format_provider_health_reset_result(result, path=context.provider_health_path))


def event_catalyst_search_report(
    verbose: bool = False,
    with_llm: bool = False,
    event_now: str | datetime | None = None,
) -> None:
    """Print research-only market-anomaly catalyst-search diagnostics."""
    _setup_event_discovery_logging(verbose)
    if not _event_alpha_inputs_configured():
        print(
            "No event-catalyst-search inputs ready. Enable RSI_EVENT_ANOMALY_SCANNER_ENABLED=1 "
            "with a CoinGecko universe fixture/live source."
        )
        return
    now = _event_research_now(event_now)
    catalyst_search_cfg = _event_catalyst_search_config_from_runtime(enabled_override=True)
    catalyst_search_provider = _event_catalyst_search_provider(catalyst_search_cfg)
    extraction_provider = None
    extraction_cfg = None
    relationship_provider = None
    relationship_cfg = None
    if with_llm:
        extraction_cfg = _event_llm_extractor_config_from_runtime()
        extraction_provider = _event_llm_extraction_provider(extraction_cfg)
        relationship_cfg = _event_llm_config_from_runtime()
        relationship_provider = _event_llm_provider(relationship_cfg)
    result = event_alpha_pipeline.run_event_alpha_operating_cycle(
        load_discovery_result=lambda observed, raw_event_transform: _event_discovery_result_from_config(
            now=observed,
            raw_event_transform=raw_event_transform,
        ),
        alert_cfg=_event_alert_config_from_runtime(),
        now=now,
        with_llm=with_llm,
        extraction_provider=extraction_provider,
        extraction_cfg=extraction_cfg,
        catalyst_search_provider=catalyst_search_provider,
        catalyst_search_cfg=catalyst_search_cfg,
        relationship_provider=relationship_provider,
        relationship_cfg=relationship_cfg,
        watchlist_cfg=_event_watchlist_config_from_runtime(),
        router_cfg=_event_alpha_router_config_from_runtime(),
        priors_cfg=_event_alpha_priors_config_from_runtime(),
        refresh_watchlist=False,
        route=False,
        send=False,
    )
    print(event_catalyst_search.format_catalyst_search_report(result.catalyst_search_result))
    print("")
    print(event_alpha_pipeline.format_event_alpha_pipeline_report(result))


def event_watchlist_refresh(
    verbose: bool = False,
    with_llm: bool = False,
    event_now: str | datetime | None = None,
) -> None:
    """Append research-only Event Alpha Radar watchlist state."""
    _setup_event_discovery_logging(verbose)
    watch_cfg = _event_watchlist_config_from_runtime()
    if not watch_cfg.enabled:
        print("Event watchlist refresh disabled. Set RSI_EVENT_WATCHLIST_ENABLED=1 for this research command.")
        return
    if not _event_alpha_inputs_configured():
        print(
            "No event-watchlist inputs ready. Configure event sources or enable "
            "RSI_EVENT_ANOMALY_SCANNER_ENABLED=1 with a CoinGecko universe fixture/live source."
        )
        return
    now = _event_research_now(event_now)
    alerts = _event_alerts_from_config(with_llm=with_llm, now=now)
    result = event_watchlist.refresh_watchlist(alerts, cfg=watch_cfg, now=now)
    print(event_watchlist.format_watchlist_refresh_result(result))


def event_watchlist_report(verbose: bool = False) -> None:
    """Print latest research-only Event Alpha Radar watchlist state."""
    _setup_event_discovery_logging(verbose)
    watch_cfg = _event_watchlist_config_from_runtime()
    result = event_watchlist.load_watchlist(watch_cfg.state_path or config.EVENT_WATCHLIST_STATE_PATH)
    print(event_watchlist.format_watchlist_report(result))


def event_watchlist_monitor_report(verbose: bool = False, event_now: str | datetime | None = None) -> None:
    """Refresh active watchlist rows from market state without new source evidence."""
    _setup_event_discovery_logging(verbose)
    watch_cfg = _event_watchlist_config_from_runtime()
    read_result = event_watchlist.load_watchlist(watch_cfg.state_path or config.EVENT_WATCHLIST_STATE_PATH)
    fixture_rows = _event_watchlist_monitor_market_rows_from_runtime()
    market_source = event_watchlist_market.market_rows_for_watchlist(
        read_result,
        source=config.EVENT_WATCHLIST_MONITOR_MARKET_SOURCE,
        fixture_rows=fixture_rows,
        cycle_rows=fixture_rows,
        targeted_lookup=config.EVENT_WATCHLIST_MONITOR_TARGETED_LOOKUP,
        targeted_provider=_event_watchlist_market_provider_from_runtime(),
        max_assets=config.EVENT_WATCHLIST_MONITOR_MAX_ASSETS,
        cache_ttl_seconds=config.EVENT_WATCHLIST_MONITOR_MARKET_CACHE_TTL_SECONDS,
        now=_event_research_now(event_now),
    )
    enrichment = event_watchlist_enrichment.enrichment_for_watchlist(
        read_result,
        derivatives_source=config.EVENT_WATCHLIST_MONITOR_DERIVATIVES_SOURCE,
        supply_source=config.EVENT_WATCHLIST_MONITOR_SUPPLY_SOURCE,
        derivatives_rows=_event_watchlist_monitor_derivatives_rows_from_runtime(),
        supply_rows=_event_watchlist_monitor_supply_rows_from_runtime(),
        max_assets=config.EVENT_WATCHLIST_MONITOR_ENRICHMENT_MAX_ASSETS,
    )
    result = event_watchlist_monitor.monitor_watchlist(
        read_result,
        market_rows=market_source.rows,
        derivatives_by_asset=enrichment.derivatives,
        supply_by_asset=enrichment.supply,
        now=_event_research_now(event_now),
    )
    if market_source.warnings:
        print("watchlist market warnings: " + "; ".join(market_source.warnings))
    if enrichment.warnings:
        print("watchlist enrichment warnings: " + "; ".join(enrichment.warnings))
    print(event_watchlist_monitor.format_watchlist_monitor_report(result))


def event_alpha_router_report(verbose: bool = False, profile_name: str | None = None) -> None:
    """Print artifact-only Event Alpha Radar route decisions from watchlist state."""
    _setup_event_discovery_logging(verbose)
    profile, error = _apply_event_alpha_report_profile(profile_name)
    if error:
        print(error)
        return
    watch_cfg = _event_watchlist_config_from_runtime()
    router_cfg = _event_alpha_router_config_from_runtime()
    read_result = event_watchlist.load_watchlist(watch_cfg.state_path or config.EVENT_WATCHLIST_STATE_PATH)
    routed = event_alpha_router.route_watchlist(read_result, cfg=router_cfg)
    report = event_alpha_router.format_router_report(routed)
    if profile:
        report = report + f"\n\nprofile_applied: {profile.name}"
    print(report)


def event_alpha_near_miss_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    event_now: str | datetime | None = None,
) -> None:
    """Print near-promotion Event Alpha candidates from local artifacts."""
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    hypotheses = event_impact_hypothesis_store.load_impact_hypotheses(
        context.impact_hypothesis_store_path,
        limit=500,
        latest_run=True,
        include_legacy=True,
    )
    core_store = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
    )
    watchlist = event_watchlist.load_watchlist(context.watchlist_state_path)
    routed = event_alpha_router.route_watchlist(watchlist, cfg=_event_alpha_router_config_from_runtime())
    cfg = _event_near_miss_config_from_runtime()
    rows: list[Mapping[str, Any]] = []
    if core_store.rows:
        rows.extend(core_store.rows)
    else:
        rows.extend(hypotheses.rows)
        rows.extend(entry.__dict__ for entry in watchlist.entries)
    near = event_near_miss.detect_near_miss_rows(rows, route_decisions=routed.decisions, cfg=cfg)
    if core_store.rows:
        report_items = near
    else:
        refresh_result = event_near_miss.refresh_near_miss_hypotheses(
            _hypothesis_rows_as_objects(hypotheses.rows),
            cfg=cfg,
            market_rows=_event_watchlist_monitor_market_rows_from_runtime(),
            targeted_market_provider=_event_watchlist_market_provider_from_runtime()
            if config.EVENT_ALPHA_NEAR_MISS_MARKET_REFRESH_ENABLED
            else None,
            derivatives_rows=_event_watchlist_monitor_derivatives_rows_from_runtime(),
            supply_rows=_event_watchlist_monitor_supply_rows_from_runtime(),
            now=_event_research_now(event_now),
        )
        route_context = {item.hypothesis_id: item for item in near if item.hypothesis_id}
        report_items = tuple(
            replace(item, final_route_before=route_context[item.hypothesis_id].final_route_before)
            if item.hypothesis_id in route_context and not item.final_route_before
            else item
            for item in refresh_result.near_misses
        ) or near
    print(_event_alpha_context_block(context))
    if core_store.rows:
        print(f"canonical_core_store_rows: {len(core_store.rows)}")
    print(event_near_miss.format_near_miss_report(report_items, profile=context.profile))


def _hypothesis_rows_as_objects(rows: Iterable[Mapping[str, Any]]) -> tuple[SimpleNamespace, ...]:
    return tuple(SimpleNamespace(**dict(row)) for row in rows)


def event_alpha_signal_quality_eval(
    path: str | None = None,
    verbose: bool = False,
) -> None:
    """Run the offline curated Event Alpha signal-quality benchmark."""
    _setup_event_discovery_logging(verbose)
    result = event_alpha_signal_quality.evaluate_signal_quality_cases(
        path or event_alpha_signal_quality.DEFAULT_SIGNAL_QUALITY_CASES_PATH
    )
    print(event_alpha_signal_quality.format_signal_quality_eval(result))
    if result.failed_cases:
        raise SystemExit(1)


def event_opportunity_audit_report(
    target: str,
    *,
    verbose: bool = False,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_diagnostics: bool = False,
) -> None:
    """Print a single-candidate decision audit from local Event Alpha artifacts."""
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    hypotheses = event_impact_hypothesis_store.load_impact_hypotheses(
        context.impact_hypothesis_store_path,
        limit=500,
        include_legacy=True,
    )
    core_store = event_core_opportunity_store.load_core_opportunities(context.core_opportunity_store_path, latest_run=True)
    watchlist = event_watchlist.load_watchlist(context.watchlist_state_path)
    alerts = event_alpha_alert_store.load_alert_snapshots(context.alert_store_path, latest_only=True)
    incidents = event_incident_store.load_incidents(context.incident_store_path, limit=500, include_legacy=True)
    feedback = event_feedback.load_feedback(context.feedback_path)
    routed = event_alpha_router.route_watchlist(watchlist, cfg=_event_alpha_router_config_from_runtime())
    print(_event_alpha_context_block(context))
    print(event_opportunity_audit.format_opportunity_audit(
        target,
        hypotheses=hypotheses.rows,
        core_opportunity_rows=core_store.rows,
        watchlist_entries=watchlist.entries,
        alert_rows=alerts.rows,
        route_decisions=routed.decisions,
        incident_rows=incidents.rows,
        card_paths=_research_card_markdown_paths(context.research_cards_dir),
        feedback_rows=feedback.records,
        profile=context.profile,
        include_diagnostics=include_diagnostics,
    ))


def _event_alpha_quality_artifacts(
    context: event_alpha_artifacts.EventAlphaArtifactContext,
) -> dict[str, Any]:
    hypotheses = event_impact_hypothesis_store.load_impact_hypotheses(
        context.impact_hypothesis_store_path,
        limit=500,
        latest_run=True,
        include_legacy=True,
    )
    watchlist = event_watchlist.load_watchlist(context.watchlist_state_path)
    alerts = event_alpha_alert_store.load_alert_snapshots(context.alert_store_path, latest_only=True)
    core_opportunities = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
        include_legacy=True,
    )
    feedback = event_feedback.load_feedback(context.feedback_path)
    missed = event_alpha_missed.load_missed_rows(context.missed_path)
    routed = event_alpha_router.route_watchlist(watchlist, cfg=_event_alpha_router_config_from_runtime())
    return {
        "hypotheses": hypotheses,
        "watchlist": watchlist,
        "alerts": alerts,
        "core_opportunities": core_opportunities,
        "feedback_rows": [record.__dict__ for record in feedback.records],
        "missed_rows": missed,
        "router": routed,
    }


def _event_alpha_raw_quality_rows(
    context: event_alpha_artifacts.EventAlphaArtifactContext,
) -> dict[str, list[dict[str, Any]]]:
    return {
        "runs": event_alpha_quality_coverage.read_jsonl_rows(
            context.run_ledger_path,
            row_type="event_alpha_run",
        ),
        "hypotheses": event_alpha_quality_coverage.read_jsonl_rows(
            context.impact_hypothesis_store_path,
            row_type="event_impact_hypothesis",
        ),
        "watchlist": event_alpha_quality_coverage.read_jsonl_rows(
            context.watchlist_state_path,
            row_type="event_watchlist_state",
        ),
        "alerts": event_alpha_quality_coverage.read_jsonl_rows(
            context.alert_store_path,
            row_type="event_alpha_alert_snapshot",
        ),
    }


def _event_alpha_reference_quality_rows(
    context: event_alpha_artifacts.EventAlphaArtifactContext,
) -> list[dict[str, Any]]:
    namespace_dir = context.base_dir / "quality_validation"
    reference = event_alpha_artifacts.EventAlphaArtifactContext(
        profile="quality_validation",
        run_mode="test",
        artifact_namespace="quality_validation",
        base_dir=context.base_dir,
        namespace_dir=namespace_dir,
        run_ledger_path=namespace_dir / "event_alpha_runs.jsonl",
        alert_store_path=namespace_dir / "event_alpha_alerts.jsonl",
        notification_runs_path=namespace_dir / "event_alpha_notification_runs.jsonl",
        watchlist_state_path=namespace_dir / "event_watchlist_state.jsonl",
        feedback_path=namespace_dir / "event_alpha_feedback.jsonl",
        missed_path=namespace_dir / "event_alpha_missed.jsonl",
        priors_path=namespace_dir / "event_alpha_priors.json",
        provider_health_path=namespace_dir / "event_provider_health.json",
        daily_brief_path=namespace_dir / "event_alpha_daily_brief.md",
        impact_hypothesis_store_path=namespace_dir / "event_impact_hypotheses.jsonl",
        core_opportunity_store_path=namespace_dir / "event_core_opportunities.jsonl",
        incident_store_path=namespace_dir / "event_incidents.jsonl",
        evidence_acquisition_path=namespace_dir / "event_evidence_acquisition.jsonl",
        proposed_eval_cases_dir=namespace_dir / "proposed_eval_cases",
        research_cards_dir=namespace_dir / "research_cards",
        llm_budget_ledger_path=namespace_dir / "event_llm_budget.json",
        outcomes_path=namespace_dir / "event_alpha_outcomes.jsonl",
    )
    rows = _event_alpha_raw_quality_rows(reference)
    return [*rows["hypotheses"], *rows["watchlist"], *rows["alerts"]]


def _event_alpha_stale_quality_warning(
    context: event_alpha_artifacts.EventAlphaArtifactContext,
) -> str | None:
    rows = _event_alpha_raw_quality_rows(context)
    return event_alpha_quality_coverage.stale_quality_artifact_warning(
        [*rows["hypotheses"], *rows["watchlist"], *rows["alerts"]],
        reference_rows=_event_alpha_reference_quality_rows(context),
    )


def event_alpha_quality_review_report(
    *,
    verbose: bool = False,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    """Print signal-quality distribution and gap review for local artifacts."""
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    artifacts = _event_alpha_quality_artifacts(context)
    result = event_alpha_quality_review.build_quality_review(
        profile=context.profile,
        core_opportunity_rows=event_core_opportunity_store.load_core_opportunities(
            context.core_opportunity_store_path,
            latest_run=True,
        ).rows,
        hypothesis_rows=artifacts["hypotheses"].rows,
        watchlist_entries=artifacts["watchlist"].entries,
        alert_rows=artifacts["alerts"].rows,
        stale_warning=_event_alpha_stale_quality_warning(context),
    )
    print(_event_alpha_context_block(context))
    print(event_alpha_quality_review.format_quality_review(result))


def event_alpha_quality_coverage_report(
    *,
    verbose: bool = False,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_legacy_artifacts: bool = False,
) -> None:
    """Print fresh-run top-level quality-field coverage from raw artifacts."""
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    rows = _event_alpha_raw_quality_rows(context)
    result = event_alpha_quality_coverage.build_latest_run_quality_coverage(
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        run_rows=rows["runs"],
        hypothesis_rows=rows["hypotheses"],
        watchlist_rows=rows["watchlist"],
        alert_rows=rows["alerts"],
        reference_quality_rows=_event_alpha_reference_quality_rows(context),
        include_legacy=include_legacy_artifacts,
    )
    print(_event_alpha_context_block(context))
    print(event_alpha_quality_coverage.format_quality_coverage_report(result))
    if result.status == "BLOCKED":
        raise SystemExit(1)


def event_alpha_policy_simulate_report(
    *,
    verbose: bool = False,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    """Print threshold/policy simulation from local artifacts only."""
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    artifacts = _event_alpha_quality_artifacts(context)
    rows: list[dict[str, Any]] = []
    rows.extend(dict(row) for row in artifacts["hypotheses"].rows)
    rows.extend(_watchlist_entry_dict(entry) for entry in artifacts["watchlist"].entries)
    rows.extend(dict(row) for row in artifacts["alerts"].rows)
    result = event_alpha_policy_simulator.simulate_policy(
        rows,
        profile=context.profile,
        feedback_rows=artifacts["feedback_rows"],
        missed_rows=artifacts["missed_rows"],
    )
    print(_event_alpha_context_block(context))
    print(event_alpha_policy_simulator.format_policy_simulation(result))


def event_alpha_export_signal_quality_cases(
    *,
    verbose: bool = False,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    out_path: str | None = None,
) -> None:
    """Export proposed signal-quality benchmark cases from local artifacts."""
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    artifacts = _event_alpha_quality_artifacts(context)
    target = Path(out_path).expanduser() if out_path else context.namespace_dir / "proposed_signal_quality_cases.json"
    result = event_alpha_signal_quality_export.export_signal_quality_cases(
        target,
        alert_rows=[*artifacts["alerts"].rows, *artifacts["core_opportunities"].rows],
        feedback_rows=artifacts["feedback_rows"],
        missed_rows=artifacts["missed_rows"],
        hypothesis_rows=artifacts["hypotheses"].rows,
    )
    print(_event_alpha_context_block(context))
    print(event_alpha_signal_quality_export.format_signal_quality_export_result(result))


def _watchlist_entry_dict(entry: event_watchlist.EventWatchlistEntry) -> dict[str, Any]:
    row = dict(getattr(entry, "__dict__", {}) or {})
    row["latest_score_components"] = dict(entry.latest_score_components or {})
    return row


def event_feedback_mark(
    target: str,
    label: str | None,
    *,
    notes: str | None = None,
    marked_by: str | None = None,
    path: str | None = None,
    allow_unmatched: bool = False,
    verbose: bool = False,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    """Append one lightweight Event Alpha feedback row."""
    _setup_event_discovery_logging(verbose)
    if not label:
        print(f"Event feedback mark failed: --event-feedback-label is required ({', '.join(event_feedback.valid_labels())})")
        return
    if profile_name or artifact_namespace:
        try:
            context = resolve_event_alpha_artifact_context_for_report(profile_name, artifact_namespace)
        except ValueError as exc:
            print(f"Event feedback mark failed: {exc}")
            return
    else:
        context = None
    watch_cfg = _event_watchlist_config_from_runtime()
    watchlist = event_watchlist.load_watchlist(watch_cfg.state_path or config.EVENT_WATCHLIST_STATE_PATH)
    feedback_cfg = _event_feedback_config_from_runtime(path)
    context_rows: list[dict[str, Any]] = []
    card_paths: tuple[Path, ...] = ()
    if context is not None:
        try:
            alerts = event_alpha_alert_store.load_alert_snapshots(context.alert_store_path).rows
            cores = event_core_opportunity_store.load_core_opportunities(context.core_opportunity_store_path, latest_run=True).rows
            hypotheses = event_impact_hypothesis_store.load_impact_hypotheses(
                context.impact_hypothesis_store_path,
                limit=500,
                latest_run=True,
                include_legacy=True,
            ).rows
            context_rows = [*alerts, *cores, *hypotheses]
            card_paths = tuple(path for path in Path(context.research_cards_dir).glob("*.md") if path.name != "index.md")
        except Exception as exc:  # noqa: BLE001 - feedback marking should still allow manual unmatched rows.
            if verbose:
                print(f"Event feedback context warning: {exc}")
    try:
        record = event_feedback.mark_feedback(
            target,
            label,
            watchlist_entries=watchlist.entries,
            cfg=feedback_cfg,
            marked_by=marked_by or "human",
            notes=notes,
            allow_unmatched=allow_unmatched,
            context_rows=context_rows,
            card_paths=card_paths,
        )
    except ValueError as exc:
        print(f"Event feedback mark failed: {exc}")
        return
    print(event_feedback.format_feedback_record(record, path=feedback_cfg.path))


def event_feedback_shortcut(
    target: str,
    label: str,
    *,
    notes: str | None = None,
    verbose: bool = False,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    """Append quick feedback from a shorthand CLI flag."""
    event_feedback_mark(
        target,
        label,
        notes=notes,
        marked_by="human",
        allow_unmatched=True,
        verbose=verbose,
        profile_name=profile_name,
        artifact_namespace=artifact_namespace,
    )


def event_feedback_report(
    path: str | None = None,
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    """Print lightweight Event Alpha feedback artifact rows."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    feedback_cfg = event_feedback.EventFeedbackConfig(
        path=_event_alpha_report_path(path, context.feedback_path)
    )
    result = event_feedback.load_feedback(feedback_cfg.path)
    print(_event_alpha_context_block(context))
    print(event_feedback.format_feedback_report(result))


def event_alpha_alerts_report(
    path: str | None = None,
    feedback_path: str | None = None,
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    """Print Event Alpha alert snapshot cohorts and outcome fields."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    store_cfg = event_alpha_alert_store.EventAlphaAlertStoreConfig(
        path=_event_alpha_report_path(path, context.alert_store_path),
        snapshot_policy=config.EVENT_ALPHA_SNAPSHOT_POLICY,
        sampled_controls_limit=config.EVENT_ALPHA_SNAPSHOT_SAMPLED_CONTROLS,
    )
    result = event_alpha_alert_store.load_alert_snapshots(store_cfg.path)
    feedback_cfg = event_feedback.EventFeedbackConfig(
        path=_event_alpha_report_path(feedback_path, context.feedback_path)
    )
    feedback = event_feedback.load_feedback(feedback_cfg.path)
    feedback_rows = [record.__dict__ for record in feedback.records]
    print(_event_alpha_context_block(context))
    print(event_alpha_alert_store.format_alert_snapshot_report(result, feedback_rows=feedback_rows))


def event_alpha_notification_inbox_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_diagnostics: bool = False,
    burn_in_review: bool = False,
) -> None:
    """Print unreviewed Event Alpha notification/card follow-up queues."""
    _setup_event_discovery_logging(verbose)
    selected_profile = profile_name or "notify_no_key"
    try:
        context = resolve_event_alpha_artifact_context_for_report(selected_profile, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    notification_runs = event_alpha_notification_runs.load_notification_runs(
        context.notification_runs_path,
        limit=250,
    )
    alerts = event_alpha_alert_store.load_alert_snapshots(context.alert_store_path)
    core_opportunities = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
        include_legacy=True,
    )
    feedback = event_feedback.load_feedback(context.feedback_path)
    delivery_rows = event_alpha_notification_delivery.load_delivery_records(
        event_alpha_notification_delivery.deliveries_path_for_context(context)
    )
    watchlist = event_watchlist.load_watchlist(context.watchlist_state_path)
    result = event_alpha_notification_inbox.build_notification_inbox(
        notification_runs=notification_runs.rows,
        alert_rows=alerts.rows,
        feedback_rows=[record.__dict__ for record in feedback.records],
        notification_delivery_rows=delivery_rows,
        watchlist_entries=watchlist.entries,
        core_opportunity_rows=core_opportunities.rows,
        research_cards_dir=context.research_cards_dir,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        notification_runs_path=context.notification_runs_path,
        alert_store_path=context.alert_store_path,
        feedback_path=context.feedback_path,
        outcomes_path=context.outcomes_path,
        include_diagnostics=include_diagnostics,
    )
    print(event_alpha_notification_inbox.format_notification_inbox(result, burn_in_review=burn_in_review))


def event_alpha_feedback_readiness_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    """Print artifact-only feedback-loop readiness for Event Alpha."""
    _setup_event_discovery_logging(verbose)
    selected_profile = profile_name or "notify_llm_quality"
    try:
        context = resolve_event_alpha_artifact_context_for_report(selected_profile, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    notification_runs = event_alpha_notification_runs.load_notification_runs(
        context.notification_runs_path,
        limit=250,
    )
    alerts = event_alpha_alert_store.load_alert_snapshots(context.alert_store_path)
    core_opportunities = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
        include_legacy=True,
    )
    feedback = event_feedback.load_feedback(context.feedback_path)
    delivery_rows = event_alpha_notification_delivery.load_delivery_records(
        event_alpha_notification_delivery.deliveries_path_for_context(context)
    )
    watchlist = event_watchlist.load_watchlist(context.watchlist_state_path)
    inbox = event_alpha_notification_inbox.build_notification_inbox(
        notification_runs=notification_runs.rows,
        alert_rows=alerts.rows,
        feedback_rows=[record.__dict__ for record in feedback.records],
        notification_delivery_rows=delivery_rows,
        watchlist_entries=watchlist.entries,
        core_opportunity_rows=core_opportunities.rows,
        research_cards_dir=context.research_cards_dir,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        notification_runs_path=context.notification_runs_path,
        alert_store_path=context.alert_store_path,
        feedback_path=context.feedback_path,
        outcomes_path=context.outcomes_path,
    )
    result = event_alpha_feedback_readiness.build_feedback_readiness(
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        card_paths=_research_card_markdown_paths(context.research_cards_dir),
        alert_rows=alerts.rows,
        feedback_rows=[record.__dict__ for record in feedback.records],
        watchlist_entries=watchlist.entries,
        core_opportunity_rows=core_opportunities.rows,
        inbox_result=inbox,
    )
    print(event_alpha_feedback_readiness.format_feedback_readiness(result))


def event_alpha_burn_in_readiness_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    """Print live-style no-send burn-in readiness from profile-scoped artifacts."""
    _setup_event_discovery_logging(verbose)
    selected_profile = profile_name or "live_burn_in_no_send"
    try:
        context = resolve_event_alpha_artifact_context_for_report(selected_profile, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    provider_report = event_provider_status.build_event_discovery_provider_status(config)
    runs = event_alpha_run_ledger.load_run_records(context.run_ledger_path, limit=500)
    alerts = event_alpha_alert_store.load_alert_snapshots(context.alert_store_path, latest_only=False)
    current_alerts = event_alpha_alert_store.load_alert_snapshots(context.alert_store_path)
    core_opportunities = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
        include_legacy=True,
    )
    feedback = event_feedback.load_feedback(context.feedback_path)
    feedback_rows = [record.__dict__ for record in feedback.records]
    delivery_rows = event_alpha_notification_delivery.load_delivery_records(
        event_alpha_notification_delivery.deliveries_path_for_context(context)
    )
    watchlist = event_watchlist.load_watchlist(context.watchlist_state_path)
    notification_runs = event_alpha_notification_runs.load_notification_runs(
        context.notification_runs_path,
        limit=250,
    )
    inbox = event_alpha_notification_inbox.build_notification_inbox(
        notification_runs=notification_runs.rows,
        alert_rows=current_alerts.rows,
        feedback_rows=feedback_rows,
        notification_delivery_rows=delivery_rows,
        watchlist_entries=watchlist.entries,
        research_cards_dir=context.research_cards_dir,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        notification_runs_path=context.notification_runs_path,
        alert_store_path=context.alert_store_path,
        feedback_path=context.feedback_path,
        outcomes_path=context.outcomes_path,
    )
    feedback_readiness = event_alpha_feedback_readiness.build_feedback_readiness(
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        card_paths=_research_card_markdown_paths(context.research_cards_dir),
        alert_rows=current_alerts.rows,
        feedback_rows=feedback_rows,
        watchlist_entries=watchlist.entries,
        core_opportunity_rows=core_opportunities.rows,
        inbox_result=inbox,
    )
    outcome_rows = [
        row for row in alerts.rows if any(
            row.get(field) not in (None, "")
            for field in (
                "primary_horizon_return",
                "return_1h",
                "return_4h",
                "return_24h",
                "return_72h",
                "return_7d",
                "max_favorable_excursion",
                "max_adverse_excursion",
                "mfe_mae_ratio",
                "direction_hit",
                "volatility_hit",
            )
        )
    ]
    doctor = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=runs.rows,
        alert_rows=alerts.rows,
        feedback_rows=feedback_rows,
        outcome_rows=outcome_rows,
        hypothesis_rows=event_impact_hypothesis_store.load_impact_hypotheses(
            context.impact_hypothesis_store_path,
            limit=500,
            latest_run=True,
            include_legacy=True,
        ).rows,
        core_opportunity_rows=core_opportunities.rows,
        watchlist_rows=watchlist.entries,
        incident_rows=event_incident_store.load_incidents(
            context.incident_store_path,
            limit=500,
            latest_run=True,
            include_legacy=True,
        ).rows,
        evidence_acquisition_rows=event_evidence_acquisition.load_acquisition_results(
            context.evidence_acquisition_path
        ),
        card_paths=[str(path) for path in _research_card_markdown_paths(context.research_cards_dir, include_index=True)],
        provider_health_rows=event_provider_health.load_provider_health(context.provider_health_path),
        llm_budget_rows=event_alpha_burn_in.load_llm_budget_rows(context.llm_budget_ledger_path),
        delivery_rows=delivery_rows,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        include_test_artifacts=False,
        include_legacy_artifacts=False,
        inspected_alert_store_path=context.alert_store_path,
        strict=True,
    )
    core_store = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
        include_legacy=True,
    )
    acquisition_rows = event_evidence_acquisition.load_acquisition_results(context.evidence_acquisition_path)
    readiness = event_alpha_burn_in_readiness.build_burn_in_readiness(
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        run_rows=runs.rows,
        provider_status=provider_report,
        artifact_doctor=doctor,
        feedback_readiness=feedback_readiness,
        core_opportunity_rows=core_store.rows,
        evidence_acquisition_rows=acquisition_rows,
        daily_brief_path=context.daily_brief_path,
    )
    print(_event_alpha_context_block(context))
    print(event_provider_status.format_event_discovery_provider_status(provider_report))
    print("")
    print(event_alpha_burn_in_readiness.format_burn_in_readiness(readiness))


def event_alpha_notify_fixture_smoke(
    verbose: bool = False,
    *,
    event_now: str | datetime | None = None,
) -> None:
    """Run a local fake-sender Event Alpha notification smoke."""
    _setup_event_discovery_logging(verbose)
    now = _event_research_now(event_now)
    fixture_profile = str(os.getenv("RSI_EVENT_ALPHA_NOTIFY_FIXTURE_PROFILE", "fixture") or "fixture")
    context = event_alpha_artifacts.context_from_profile(
        fixture_profile,
        run_mode="test",
        base_dir=config.EVENT_ALPHA_ARTIFACT_BASE_DIR,
        artifact_namespace=config.EVENT_ALPHA_ARTIFACT_NAMESPACE or "fixture_notify_smoke",
    )
    if str(context.artifact_namespace or "").endswith("smoke"):
        shutil.rmtree(context.namespace_dir, ignore_errors=True)
    _apply_event_alpha_context_to_config(context)
    _normalize_profile_paths()
    no_send = str(os.getenv("RSI_EVENT_ALPHA_NOTIFY_FIXTURE_NO_SEND", "0")).strip().lower() in {"1", "true", "yes", "on"}
    run_id = event_alpha_run_ledger.run_id_for(now, context.profile)
    entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="fixture-spacex|velvet|proxy_attention",
        cluster_id="fixture-spacex|proxy_attention|2026-06-15",
        event_id="fixture-notify-velvet",
        coin_id="velvet",
        symbol="VELVET",
        relationship_type="venue_value_capture",
        external_asset="SpaceX",
        event_time=now.isoformat(),
        state=event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        previous_state=event_watchlist.EventWatchlistState.WATCHLIST.value,
        first_seen_at=now.isoformat(),
        last_seen_at=now.isoformat(),
        source_count=2,
        highest_score=92,
        latest_score=92,
        latest_tier="HIGH_PRIORITY_WATCH",
        latest_event_name="VELVET offers SpaceX pre-IPO tokenized stock exposure",
        latest_source="CryptoPanic fixture",
        latest_playbook_type="proxy_attention",
        latest_rule_playbook_type="proxy_attention",
        latest_effective_playbook_type="proxy_attention",
        latest_playbook_score=92,
        latest_playbook_action="high_priority_watch",
        latest_market_snapshot={"price": 1.0, "return_24h": 0.42, "volume_zscore_24h": 5.2},
        latest_score_components={
            "core_opportunity_id": "agg:fixture-velvet-spacex",
            "hypothesis_id": "hypothesis:fixture-velvet-spacex",
            "external_catalyst": 92,
            "market_move_volume": 88,
            "impact_path_type": "venue_value_capture",
            "impact_path_strength": "strong",
            "candidate_role": "proxy_venue",
            "source_class": "cryptopanic_tagged",
            "evidence_specificity": "direct_token_mechanism",
            "evidence_quality_score": 91,
            "market_confirmation_score": 88,
            "market_confirmation_level": "strong",
            "market_context_freshness_status": "fresh",
            "opportunity_score_final": 92,
            "opportunity_level": "high_priority",
        },
        incident_id="incident:fixture-spacex",
        hypothesis_id="hypothesis:fixture-velvet-spacex",
        should_alert=True,
        material_change_reasons=("fixture_notification_smoke",),
    )
    decision = event_alpha_router.EventAlphaRouteDecision(
        entry=entry,
        route=event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH,
        alertable=True,
        reason="Fixture high-priority state escalation for notification smoke.",
        lane=event_alpha_router.EventAlphaRouteLane.INSTANT_ESCALATION,
    )
    aave_entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="fixture-aave-kraken|aave|strategic_investment",
        cluster_id="fixture-aave-kraken|strategic_investment|2026-06-15",
        event_id="fixture-notify-aave",
        coin_id="aave",
        symbol="AAVE",
        relationship_type="strategic_investment",
        external_asset="Kraken",
        event_time=None,
        state=event_watchlist.EventWatchlistState.RADAR.value,
        previous_state=None,
        first_seen_at=now.isoformat(),
        last_seen_at=now.isoformat(),
        source_count=2,
        highest_score=78,
        latest_score=78,
        latest_tier="WATCHLIST",
        latest_event_name="Kraken takes strategic stake in Aave ecosystem",
        latest_source="Crypto news fixture",
        latest_playbook_type="strategic_investment_or_valuation",
        latest_rule_playbook_type="strategic_investment_or_valuation",
        latest_effective_playbook_type="strategic_investment_or_valuation",
        latest_playbook_score=78,
        latest_playbook_action="watchlist",
        latest_market_snapshot={},
        latest_score_components={
            "core_opportunity_id": "agg:fixture-aave-kraken",
            "hypothesis_id": "hypothesis:fixture-aave-kraken",
            "impact_path_type": "strategic_investment_or_valuation",
            "impact_path_reason": "strategic_investment",
            "candidate_role": "direct_subject",
            "source_class": "crypto_news",
            "evidence_specificity": "direct_token_mechanism",
            "evidence_acquisition_status": "accepted_evidence_found",
            "accepted_evidence_count": 1,
            "market_confirmation_level": "none",
            "market_context_freshness_status": "missing",
            "opportunity_level": "validated_digest",
            "opportunity_score_final": 78,
        },
        incident_id="incident:fixture-aave-kraken",
        hypothesis_id="hypothesis:fixture-aave-kraken",
        should_alert=True,
        material_change_reasons=("fixture_notification_digest",),
    )
    aave_decision = event_alpha_router.EventAlphaRouteDecision(
        entry=aave_entry,
        route=event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST,
        alertable=True,
        reason="Fixture accepted source evidence for strategic stake digest.",
        lane=event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST,
    )
    core_source_row = {
        "row_type": "event_impact_hypothesis",
        "core_opportunity_id": "agg:fixture-velvet-spacex",
        "key": entry.key,
        "hypothesis_id": entry.hypothesis_id,
        "incident_id": entry.incident_id,
        "event_id": entry.event_id,
        "symbol": entry.symbol,
        "coin_id": entry.coin_id,
        "validated_symbol": entry.symbol,
        "validated_coin_id": entry.coin_id,
        "canonical_incident_name": entry.latest_event_name,
        "candidate_role": "proxy_venue",
        "impact_category": "proxy_attention",
        "impact_path_type": "venue_value_capture",
        "impact_path_strength": "strong",
        "impact_path_reason": "venue_value_capture",
        "relationship_type": "venue_value_capture",
        "opportunity_level": "high_priority",
        "final_opportunity_level": "high_priority",
        "opportunity_score_final": 92,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        "source_class": "cryptopanic_tagged",
        "evidence_specificity": "direct_token_mechanism",
        "evidence_quality_score": 91,
        "market_confirmation_score": 88,
        "market_confirmation_level": "strong",
        "market_context_freshness_status": "fresh",
        "market_context_source": "fixture_market_context",
        "evidence_acquisition_status": "accepted_evidence_found",
        "evidence_acquisition_accepted_count": 1,
        "accepted_evidence_count": 1,
        "acquisition_confirmation_status": "confirms",
        "accepted_evidence_reason_codes": ["cryptopanic_currency_tag_match", "direct_token_mechanism"],
        "accepted_evidence_samples": [
            {
                "title": "VELVET offers SpaceX pre-IPO tokenized stock exposure",
                "provider": "cryptopanic_fixture",
                "source_url": "https://example.invalid/velvet-spacex",
            }
        ],
        "source_pack": "proxy_preipo_rwa_pack",
        "latest_source": "CryptoPanic fixture",
        "latest_source_title": "VELVET offers SpaceX pre-IPO tokenized stock exposure",
        "why_opportunity_visible": "Accepted tagged evidence validates the token/catalyst link.",
        "upgrade_requirements": ["verify accepted source evidence", "confirm market reaction remains organic"],
        "latest_market_snapshot": entry.latest_market_snapshot,
    }
    weak_btc_control = {
        "row_type": "event_impact_hypothesis",
        "core_opportunity_id": "agg:fixture-btc-rejected",
        "key": "fixture-strategy|bitcoin|strategic_context",
        "hypothesis_id": "hypothesis:fixture-btc-rejected",
        "incident_id": "incident:fixture-strategy-valuation",
        "symbol": "BTC",
        "coin_id": "bitcoin",
        "validated_symbol": "BTC",
        "validated_coin_id": "bitcoin",
        "canonical_incident_name": "Strategy valuation article mentions Bitcoin treasury holdings",
        "candidate_role": "treasury_context",
        "impact_category": "strategic_investment_or_valuation",
        "impact_path_type": "strategic_investment_or_valuation",
        "impact_path_strength": "medium",
        "impact_path_reason": "treasury_context",
        "opportunity_level": "local_only",
        "final_opportunity_level": "local_only",
        "opportunity_score_final": 44,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RAW_EVIDENCE.value,
        "source_class": "crypto_news",
        "evidence_specificity": "direct_token_mechanism",
        "evidence_quality_score": 88,
        "market_confirmation_score": 0,
        "market_confirmation_level": "none",
        "market_context_freshness_status": "missing",
        "evidence_acquisition_status": "rejected_results_only",
        "evidence_acquisition_rejected_count": 2,
        "accepted_evidence_count": 0,
        "acquisition_confirmation_status": "does_not_confirm",
        "source_pack": "strategic_investment_pack",
        "latest_source": "Strategy valuation fixture",
        "why_opportunity_visible": "Fixture control: broad treasury valuation context is not direct BTC confirmation.",
    }
    aave_core_source_row = {
        "row_type": "event_impact_hypothesis",
        "core_opportunity_id": "agg:fixture-aave-kraken",
        "key": aave_entry.key,
        "hypothesis_id": aave_entry.hypothesis_id,
        "incident_id": aave_entry.incident_id,
        "event_id": aave_entry.event_id,
        "symbol": aave_entry.symbol,
        "coin_id": aave_entry.coin_id,
        "validated_symbol": aave_entry.symbol,
        "validated_coin_id": aave_entry.coin_id,
        "canonical_incident_name": aave_entry.latest_event_name,
        "candidate_role": "direct_subject",
        "impact_category": "strategic_investment_or_valuation",
        "impact_path_type": "strategic_investment_or_valuation",
        "impact_path_strength": "medium",
        "impact_path_reason": "strategic_investment",
        "relationship_type": "strategic_investment",
        "opportunity_level": "validated_digest",
        "final_opportunity_level": "validated_digest",
        "opportunity_score_final": 78,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
        "source_class": "crypto_news",
        "evidence_specificity": "direct_token_mechanism",
        "evidence_quality_score": 86,
        "market_confirmation_score": 0,
        "market_confirmation_level": "none",
        "market_context_freshness_status": "missing",
        "evidence_acquisition_status": "accepted_evidence_found",
        "evidence_acquisition_accepted_count": 1,
        "accepted_evidence_count": 1,
        "acquisition_confirmation_status": "confirms",
        "accepted_evidence_reason_codes": ["direct_token_mechanism"],
        "accepted_evidence_samples": [
            {
                "title": "Kraken takes strategic stake in Aave ecosystem",
                "provider": "crypto_news_fixture",
                "source_url": "https://example.invalid/aave-kraken",
            }
        ],
        "source_pack": "strategic_investment_pack",
        "latest_source": "Crypto news fixture",
        "latest_source_title": "Kraken takes strategic stake in Aave ecosystem",
        "why_opportunity_visible": "Accepted direct source evidence validates the AAVE/Kraken relationship.",
        "upgrade_requirements": ["verify primary source", "wait for market confirmation"],
    }
    tao_control = {
        "row_type": "event_impact_hypothesis",
        "core_opportunity_id": "agg:fixture-tao-rejected",
        "key": "fixture-tao|bittensor|strategic_context",
        "hypothesis_id": "hypothesis:fixture-tao-rejected",
        "incident_id": "incident:fixture-tao-strategic",
        "symbol": "TAO",
        "coin_id": "bittensor",
        "validated_symbol": "TAO",
        "validated_coin_id": "bittensor",
        "canonical_incident_name": "Broad AI infrastructure article mentions Bittensor without impact evidence",
        "candidate_role": "direct_subject",
        "impact_category": "strategic_investment_or_valuation",
        "impact_path_type": "strategic_investment_or_valuation",
        "impact_path_strength": "weak",
        "impact_path_reason": "weak_cooccurrence_only",
        "opportunity_level": "local_only",
        "final_opportunity_level": "local_only",
        "opportunity_score_final": 38,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RAW_EVIDENCE.value,
        "source_class": "broad_news",
        "evidence_specificity": "weak_cooccurrence",
        "evidence_quality_score": 40,
        "market_confirmation_score": 0,
        "market_confirmation_level": "none",
        "market_context_freshness_status": "missing",
        "evidence_acquisition_status": "rejected_results_only",
        "evidence_acquisition_rejected_count": 1,
        "accepted_evidence_count": 0,
        "acquisition_confirmation_status": "does_not_confirm",
        "source_pack": "strategic_investment_pack",
        "latest_source": "Broad AI fixture",
        "why_opportunity_visible": "Fixture control: broad AI/TAO co-occurrence is not validated impact evidence.",
    }
    doge_near_miss = {
        "row_type": "event_impact_hypothesis",
        "core_opportunity_id": "agg:fixture-doge-near-miss",
        "key": "fixture-doge|dogecoin|exploratory_meme_catalyst",
        "hypothesis_id": "hypothesis:fixture-doge-near-miss",
        "incident_id": "incident:fixture-doge-catalyst",
        "symbol": "DOGE",
        "coin_id": "dogecoin",
        "validated_symbol": "DOGE",
        "validated_coin_id": "dogecoin",
        "canonical_incident_name": "DOGE jumps on unconfirmed meme catalyst chatter",
        "candidate_role": "candidate_asset",
        "impact_category": "meme_attention",
        "impact_path_type": "meme_attention",
        "impact_path_strength": "medium",
        "impact_path_reason": "market_confirmation_without_source_confirmation",
        "relationship_type": "proxy_attention",
        "opportunity_level": "exploratory",
        "final_opportunity_level": "exploratory",
        "opportunity_score_final": 66,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RAW_EVIDENCE.value,
        "source_class": "crypto_news",
        "evidence_specificity": "candidate_context",
        "evidence_quality_score": 58,
        "market_confirmation_score": 72,
        "market_confirmation_level": "moderate",
        "market_context_freshness_status": "fresh",
        "evidence_acquisition_status": "skipped_budget",
        "accepted_evidence_count": 0,
        "acquisition_confirmation_status": "unresolved",
        "source_pack": "meme_attention_pack",
        "latest_source": "Meme catalyst fixture",
        "latest_source_title": "DOGE jumps on unconfirmed meme catalyst chatter",
        "why_opportunity_visible": "Strong fresh move with a possible catalyst clue, but no independent confirmation yet.",
        "why_not_watchlist": "missing independent source confirmation",
        "upgrade_requirements": ["find independent catalyst evidence", "verify liquidity and organic volume"],
    }
    core_write = event_core_opportunity_store.write_core_opportunities(
        [core_source_row, aave_core_source_row, weak_btc_control, tao_control, doge_near_miss],
        cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(context.core_opportunity_store_path),
        now=now,
        run_id=run_id,
        profile=context.profile,
        run_mode=context.run_mode,
        artifact_namespace=context.artifact_namespace,
    )
    core_rows = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
    ).rows
    card_write = event_research_cards.write_research_cards(
        context.research_cards_dir,
        watchlist_entries=[entry, aave_entry],
        alert_rows=core_rows,
        route_decisions=[decision, aave_decision],
        now=now,
        lineage_context=_event_alpha_card_lineage_context(
            run_id=run_id,
            profile=context.profile,
            run_mode=context.run_mode,
            artifact_namespace=context.artifact_namespace,
        ),
    )
    event_core_opportunity_store.update_core_opportunity_card_links(
        context.core_opportunity_store_path,
        card_write.card_paths,
        run_id=run_id,
    )
    core_rows = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
    ).rows
    core_by_id = {str(row.get("core_opportunity_id") or ""): row for row in core_rows}
    canonical_core = core_by_id.get("agg:fixture-velvet-spacex") or (core_rows[0] if core_rows else {})
    btc_core = core_by_id.get("agg:fixture-btc-rejected") or {}
    aave_core = core_by_id.get("agg:fixture-aave-kraken") or {}
    tao_core = core_by_id.get("agg:fixture-tao-rejected") or {}
    doge_core = core_by_id.get("agg:fixture-doge-near-miss") or {}
    snapshot_path = _write_fixture_alert_snapshot(
        context,
        entry=entry,
        decision=decision,
        run_id=run_id,
        observed_at=now,
        core_row=canonical_core,
    )
    _write_fixture_alert_snapshot(
        context,
        entry=aave_entry,
        decision=aave_decision,
        run_id=run_id,
        observed_at=now,
        core_row=aave_core,
    )
    btc_entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="fixture-strategy|bitcoin|strategic_context",
        cluster_id="fixture-strategy|strategic_context|2026-06-15",
        event_id="fixture-btc-rejected",
        coin_id="bitcoin",
        symbol="BTC",
        relationship_type="strategic_investment_or_valuation",
        external_asset="Strategy",
        event_time=None,
        state=event_watchlist.EventWatchlistState.RAW_EVIDENCE.value,
        previous_state=None,
        first_seen_at=now.isoformat(),
        last_seen_at=now.isoformat(),
        source_count=1,
        highest_score=44,
        latest_score=44,
        latest_tier="STORE_ONLY",
        latest_event_name="Strategy valuation article mentions Bitcoin treasury holdings",
        latest_source="Strategy valuation fixture",
        latest_playbook_type="strategic_investment_or_valuation",
        latest_rule_playbook_type="strategic_investment_or_valuation",
        latest_effective_playbook_type="strategic_investment_or_valuation",
        latest_playbook_score=44,
        latest_playbook_action="store_only",
        latest_market_snapshot={},
        latest_score_components={
            "core_opportunity_id": "agg:fixture-btc-rejected",
            "hypothesis_id": "hypothesis:fixture-btc-rejected",
            "impact_path_type": "strategic_investment_or_valuation",
            "impact_path_reason": "treasury_context",
            "candidate_role": "treasury_context",
            "source_class": "crypto_news",
            "evidence_acquisition_status": "rejected_results_only",
            "accepted_evidence_count": 0,
            "market_confirmation_level": "none",
            "market_context_freshness_status": "missing",
            "opportunity_level": "local_only",
            "opportunity_score_final": 44,
        },
        incident_id="incident:fixture-strategy-valuation",
        hypothesis_id="hypothesis:fixture-btc-rejected",
        should_alert=False,
        suppressed_reason="rejected_results_only_not_confirmation",
    )
    btc_decision = event_alpha_router.EventAlphaRouteDecision(
        entry=btc_entry,
        route=event_alpha_router.EventAlphaRoute.STORE_ONLY,
        alertable=False,
        reason="Fixture control: rejected-only strategic broad-asset context is local-only.",
        lane=event_alpha_router.EventAlphaRouteLane.LOCAL_ONLY,
    )
    _write_fixture_alert_snapshot(
        context,
        entry=btc_entry,
        decision=btc_decision,
        run_id=run_id,
        observed_at=now,
        core_row=btc_core,
    )
    tao_entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="fixture-tao|bittensor|strategic_context",
        cluster_id="fixture-tao|strategic_context|2026-06-15",
        event_id="fixture-tao-rejected",
        coin_id="bittensor",
        symbol="TAO",
        relationship_type="strategic_investment_or_valuation",
        external_asset="AI infrastructure",
        event_time=None,
        state=event_watchlist.EventWatchlistState.RAW_EVIDENCE.value,
        previous_state=None,
        first_seen_at=now.isoformat(),
        last_seen_at=now.isoformat(),
        source_count=1,
        highest_score=38,
        latest_score=38,
        latest_tier="STORE_ONLY",
        latest_event_name="Broad AI infrastructure article mentions Bittensor without impact evidence",
        latest_source="Broad AI fixture",
        latest_playbook_type="strategic_investment_or_valuation",
        latest_rule_playbook_type="strategic_investment_or_valuation",
        latest_effective_playbook_type="strategic_investment_or_valuation",
        latest_playbook_score=38,
        latest_playbook_action="store_only",
        latest_market_snapshot={},
        latest_score_components={
            "core_opportunity_id": "agg:fixture-tao-rejected",
            "hypothesis_id": "hypothesis:fixture-tao-rejected",
            "impact_path_type": "strategic_investment_or_valuation",
            "impact_path_reason": "weak_cooccurrence_only",
            "candidate_role": "direct_subject",
            "source_class": "broad_news",
            "evidence_acquisition_status": "rejected_results_only",
            "accepted_evidence_count": 0,
            "market_confirmation_level": "none",
            "market_context_freshness_status": "missing",
            "opportunity_level": "local_only",
            "opportunity_score_final": 38,
        },
        incident_id="incident:fixture-tao-strategic",
        hypothesis_id="hypothesis:fixture-tao-rejected",
        should_alert=False,
        suppressed_reason="rejected_results_only_not_confirmation",
    )
    tao_decision = event_alpha_router.EventAlphaRouteDecision(
        entry=tao_entry,
        route=event_alpha_router.EventAlphaRoute.STORE_ONLY,
        alertable=False,
        reason="Fixture control: rejected-only TAO context is local-only.",
        lane=event_alpha_router.EventAlphaRouteLane.LOCAL_ONLY,
    )
    _write_fixture_alert_snapshot(
        context,
        entry=tao_entry,
        decision=tao_decision,
        run_id=run_id,
        observed_at=now,
        core_row=tao_core,
    )
    doge_entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="fixture-doge|dogecoin|exploratory_meme_catalyst",
        cluster_id="fixture-doge|meme_attention|2026-06-15",
        event_id="fixture-doge-near-miss",
        coin_id="dogecoin",
        symbol="DOGE",
        relationship_type="proxy_attention",
        external_asset="meme catalyst chatter",
        event_time=None,
        state=event_watchlist.EventWatchlistState.RAW_EVIDENCE.value,
        previous_state=None,
        first_seen_at=now.isoformat(),
        last_seen_at=now.isoformat(),
        source_count=1,
        highest_score=66,
        latest_score=66,
        latest_tier="STORE_ONLY",
        latest_event_name="DOGE jumps on unconfirmed meme catalyst chatter",
        latest_source="Meme catalyst fixture",
        latest_playbook_type="meme_attention",
        latest_rule_playbook_type="meme_attention",
        latest_effective_playbook_type="meme_attention",
        latest_playbook_score=66,
        latest_playbook_action="store_only",
        latest_market_snapshot={"return_24h": 0.31, "return_72h": 0.66, "volume_mcap": 0.22},
        latest_score_components={
            "core_opportunity_id": "agg:fixture-doge-near-miss",
            "hypothesis_id": "hypothesis:fixture-doge-near-miss",
            "impact_path_type": "meme_attention",
            "impact_path_reason": "market_confirmation_without_source_confirmation",
            "candidate_role": "candidate_asset",
            "source_class": "crypto_news",
            "evidence_acquisition_status": "skipped_budget",
            "accepted_evidence_count": 0,
            "market_confirmation_score": 72,
            "market_confirmation_level": "moderate",
            "market_context_freshness_status": "fresh",
            "opportunity_level": "exploratory",
            "opportunity_score_final": 66,
            "why_not_watchlist": "missing independent source confirmation",
            "upgrade_requirements": ["find independent catalyst evidence", "verify liquidity and organic volume"],
        },
        incident_id="incident:fixture-doge-catalyst",
        hypothesis_id="hypothesis:fixture-doge-near-miss",
        should_alert=False,
        suppressed_reason="missing independent source confirmation",
    )
    doge_decision = event_alpha_router.EventAlphaRouteDecision(
        entry=doge_entry,
        route=event_alpha_router.EventAlphaRoute.STORE_ONLY,
        alertable=False,
        reason="Fixture near-miss: strong move needs independent catalyst confirmation.",
        lane=event_alpha_router.EventAlphaRouteLane.LOCAL_ONLY,
    )
    _write_fixture_alert_snapshot(
        context,
        entry=doge_entry,
        decision=doge_decision,
        run_id=run_id,
        observed_at=now,
        core_row=doge_core,
    )
    fake_storage = _FixtureNotificationStorage()
    delivered_messages: list[str] = []
    notification_cfg = event_alpha_notifications.EventAlphaNotificationConfig(
        enabled=not no_send,
        mode="research_only",
        notification_scope=event_alpha_notifications.NOTIFICATION_SCOPE_NAMESPACE,
        profile_name=context.profile,
        artifact_namespace=context.artifact_namespace,
        daily_digest_cooldown_hours=0,
        instant_escalation_cooldown_hours=0,
        max_instant_per_day=10,
        health_heartbeat_enabled=False,
        research_review_digest_enabled=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_ENABLED,
        research_review_digest_max_items=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_MAX_ITEMS,
        research_review_digest_min_score=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_MIN_SCORE,
        research_review_digest_cooldown_hours=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_COOLDOWN_HOURS,
        research_review_digest_include_local_only=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_INCLUDE_LOCAL_ONLY,
        research_review_digest_include_sector=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_INCLUDE_SECTOR,
        research_review_digest_send_with_alerts=config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_SEND_WITH_ALERTS,
    )
    delivery_cfg = _event_alpha_notification_delivery_config_from_runtime(context)

    def _fake_sender(message: str) -> event_alpha_notification_sender.NotificationSendAttemptResult:
        delivered_messages.append(message)
        chunks = event_alpha_notification_sender.telegram_chunk_count(message)
        return event_alpha_notification_sender.NotificationSendAttemptResult(
            attempted=True,
            success=True,
            recipient_count=1,
            delivered_count=1,
            failed_count=0,
            chunk_count=chunks,
            delivered_chunks=chunks,
            failed_chunks=0,
            channel_summary={"channel": "fixture", "delivered_count": 1},
        )

    send_result = event_alpha_notifications.send_notifications(
        [decision, aave_decision, doge_decision] if config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_ENABLED else [decision, aave_decision],
        storage=fake_storage,
        cfg=notification_cfg,
        send_fn=_fake_sender,
        now=now,
        profile=context.profile,
        card_path_by_alert_id=_card_paths_by_alert_id([decision], card_write.card_paths),
        core_opportunity_rows=core_rows,
        include_health_heartbeat=False,
        delivery_cfg=delivery_cfg,
        run_id=run_id,
        namespace=context.artifact_namespace,
    )
    snapshot_rows_written = 5
    pipeline_result = SimpleNamespace(
        run_id=run_id,
        profile=context.profile,
        run_mode=context.run_mode,
        artifact_namespace=context.artifact_namespace,
        router_result=event_alpha_router.EventAlphaRouterResult(
            state_path=context.watchlist_state_path,
            rows_read=1,
            decisions=[decision],
            enabled=True,
        ),
        alerts=(),
        warnings=(),
        clock_status=_event_clock_status(event_now),
        cycle_completed=True,
        partial_results=False,
        send_requested=True,
        send_attempted=send_result.attempted,
        send_success=send_result.success,
        send_items_attempted=send_result.items_attempted,
        send_items_delivered=send_result.items_delivered,
        send_block_reason=send_result.block_reason,
        send_lane_items_attempted=send_result.lane_items_attempted,
        send_lane_items_delivered=send_result.lane_items_delivered,
        send_would_send_items=send_result.would_send_items,
        send_heartbeat_due=send_result.heartbeat_due,
        send_heartbeat_sent=send_result.heartbeat_sent,
        send_cooldown_blocks=send_result.cooldown_blocks,
        notification_scope=send_result.notification_scope,
        notification_scope_value=send_result.notification_scope_value,
        research_review_digest_enabled=send_result.research_review_digest_enabled,
        research_review_digest_candidates=send_result.research_review_digest_candidates,
        research_review_digest_would_send=send_result.research_review_digest_would_send,
        research_review_digest_sent=send_result.research_review_digest_sent,
        research_review_digest_block_reason=send_result.research_review_digest_block_reason,
        notification_burn_in=True,
        research_card_paths=card_write.card_paths,
        core_opportunity_store_path=str(context.core_opportunity_store_path),
        core_opportunity_write_attempted=core_write.attempted,
        core_opportunity_write_success=core_write.success,
        core_opportunity_rows_written=core_write.rows_written,
        core_opportunity_write_block_reason=core_write.block_reason,
        run_ledger_path=str(context.run_ledger_path),
        alert_store_path=str(context.alert_store_path),
        watchlist_state_path=str(context.watchlist_state_path),
        research_cards_dir=str(context.research_cards_dir),
        snapshot_write_attempted=True,
        snapshot_write_success=True,
        snapshot_rows_written=snapshot_rows_written,
        snapshot_write_block_reason=None,
        notification_delivery_records_written=send_result.delivery_records_written,
        notification_deliveries_delivered=send_result.deliveries_delivered,
        notification_deliveries_partial_delivered=send_result.deliveries_partial_delivered,
        notification_deliveries_failed=send_result.deliveries_failed,
        notification_deliveries_skipped_duplicate=send_result.deliveries_skipped_duplicate,
        notification_deliveries_skipped_in_flight=send_result.deliveries_skipped_in_flight,
        notification_deliveries_blocked=send_result.deliveries_blocked,
    )
    event_alpha_run_ledger.append_run_record(
        pipeline_result,
        cfg=event_alpha_run_ledger.EventAlphaRunLedgerConfig(context.run_ledger_path),
        profile=context.profile,
        started_at=now,
        finished_at=now,
        with_llm=False,
        send_requested=True,
        notification_burn_in=True,
    )
    notification_row = event_alpha_notification_runs.append_notification_run(
        pipeline_result,
        cfg=event_alpha_notification_runs.EventAlphaNotificationRunsConfig(context.notification_runs_path),
        profile=context.profile,
        started_at=now,
        finished_at=now,
        telegram_ready=False,
        send_guard_enabled=False,
    )
    print(_event_alpha_context_block(context))
    print("\n".join([
        "=" * 76,
        "EVENT ALPHA NOTIFICATION FIXTURE SMOKE (fake sender)",
        "=" * 76,
        f"run_id: {run_id}",
        f"mode: {'no-send guarded preview' if no_send else 'fake sender'}",
        f"fake_sender_delivered: {len(delivered_messages)}",
        f"delivery_path: {delivery_cfg.path}",
        f"delivery_records_written: {send_result.delivery_records_written}",
        f"delivery_delivered: {send_result.deliveries_delivered}",
        f"delivery_partial_delivered: {send_result.deliveries_partial_delivered}",
        f"notification_run_path: {context.notification_runs_path}",
        f"notification_would_send: {notification_row.get('would_send_count')}",
        f"alert_snapshot_path: {snapshot_path}",
        f"core_opportunity_store_path: {context.core_opportunity_store_path}",
        f"core_opportunities_written: {core_write.rows_written}",
        f"research_card_count: {card_write.cards_written}",
        f"research_card_index: {card_write.index_path}",
        "feedback: make event-feedback-useful "
        f"FEEDBACK_TARGET='{canonical_core.get('core_opportunity_id') or decision.alert_id}'",
        "No live providers, Telegram sends, normal RSI alerts, paper trades, live DB rows, or execution were used.",
    ]))


def event_alpha_fill_outcomes(
    price_path: str,
    out_path: str,
    *,
    path: str | None = None,
    verbose: bool = False,
) -> None:
    """Fill Event Alpha alert snapshot outcomes from a local OHLCV price fixture."""
    _setup_event_discovery_logging(verbose)
    store_cfg = _event_alpha_alert_store_config_from_runtime(path)
    snapshots = event_alpha_alert_store.load_alert_snapshots(store_cfg.path)
    result = event_alpha_alert_store.fill_alert_outcomes(
        snapshots.rows,
        price_path,
        out_path,
        source_path=store_cfg.path,
    )
    print(event_alpha_alert_store.format_outcome_fill_result(result))


def event_alpha_missed_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
) -> None:
    """Print missed-opportunity diagnostics from local Event Alpha artifacts."""
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(
            profile_name,
            artifact_namespace,
            include_test_artifacts=include_test_artifacts,
        )
    except ValueError as exc:
        print(str(exc))
        return
    market_rows = event_alpha_missed.load_market_rows(config.EVENT_DISCOVERY_UNIVERSE_PATH)
    store_cfg = _event_alpha_alert_store_config_from_runtime()
    alerts = event_alpha_alert_store.load_alert_snapshots(store_cfg.path)
    watch_cfg = _event_watchlist_config_from_runtime()
    watchlist = event_watchlist.load_watchlist(watch_cfg.state_path or config.EVENT_WATCHLIST_STATE_PATH)
    raw_events: tuple[RawDiscoveredEvent, ...] = ()
    if _event_discovery_paths_configured() or _event_alpha_inputs_configured():
        try:
            raw_events = tuple(_event_discovery_result_from_config().raw_events)
        except Exception as exc:  # noqa: BLE001 - report-only fail-soft guard
            print(f"Missed-opportunity raw event load warning: {exc}")
    result = event_alpha_missed.detect_missed_opportunities(
        market_rows,
        alert_rows=alerts.rows,
        watchlist_entries=watchlist.entries,
        raw_events=raw_events,
    )
    if result.rows:
        event_alpha_missed.write_missed_rows(config.EVENT_ALPHA_MISSED_PATH, result.rows)
    print(_event_alpha_context_block(context))
    print(event_alpha_missed.format_missed_report(result))
    if result.rows:
        print("")
        print(f"Missed-opportunity rows appended: {config.EVENT_ALPHA_MISSED_PATH}")


def event_alpha_calibration_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
) -> None:
    """Print calibration summaries from alert, feedback, outcome, and missed artifacts."""
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(
            profile_name,
            artifact_namespace,
            include_test_artifacts=include_test_artifacts,
        )
    except ValueError as exc:
        print(str(exc))
        return
    store_cfg = _event_alpha_alert_store_config_from_runtime()
    alerts = event_alpha_alert_store.load_alert_snapshots(store_cfg.path)
    feedback_cfg = _event_feedback_config_from_runtime()
    feedback = event_feedback.load_feedback(feedback_cfg.path)
    feedback_rows = [record.__dict__ for record in feedback.records]
    missed_rows = event_alpha_missed.load_missed_rows(config.EVENT_ALPHA_MISSED_PATH)
    print(_event_alpha_context_block(context))
    print(
        event_alpha_calibration.format_calibration_report(
            alerts.rows,
            feedback_rows=feedback_rows,
            missed_rows=missed_rows,
        )
    )


def event_source_reliability_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
) -> None:
    """Print source/provider reliability summaries from local artifacts."""
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(
            profile_name,
            artifact_namespace,
            include_test_artifacts=include_test_artifacts,
        )
    except ValueError as exc:
        print(str(exc))
        return
    alerts = event_alpha_alert_store.load_alert_snapshots(
        _event_alpha_alert_store_config_from_runtime().path,
        latest_only=False,
    )
    feedback = event_feedback.load_feedback(_event_feedback_config_from_runtime().path)
    feedback_rows = [record.__dict__ for record in feedback.records]
    missed_rows = event_alpha_missed.load_missed_rows(config.EVENT_ALPHA_MISSED_PATH)
    runs = event_alpha_run_ledger.load_run_records(config.EVENT_ALPHA_RUN_LEDGER_PATH, limit=50)
    print(_event_alpha_context_block(context))
    print(
        event_source_reliability.format_source_reliability_report(
            alerts.rows,
            feedback_rows=feedback_rows,
            missed_rows=missed_rows,
            run_rows=runs.rows,
        )
    )


def _event_alpha_local_artifacts(*, run_limit: int = 500, latest_alerts: bool = False) -> dict[str, Any]:
    runs = event_alpha_run_ledger.load_run_records(config.EVENT_ALPHA_RUN_LEDGER_PATH, limit=run_limit)
    alerts = event_alpha_alert_store.load_alert_snapshots(
        _event_alpha_alert_store_config_from_runtime().path,
        latest_only=latest_alerts,
    )
    feedback = event_feedback.load_feedback(_event_feedback_config_from_runtime().path)
    missed_rows = event_alpha_missed.load_missed_rows(config.EVENT_ALPHA_MISSED_PATH)
    provider_rows = event_provider_health.load_provider_health(config.EVENT_PROVIDER_HEALTH_PATH)
    budget_rows = event_alpha_burn_in.load_llm_budget_rows(config.EVENT_LLM_BUDGET_LEDGER_PATH)
    watchlist = event_watchlist.load_watchlist(config.EVENT_WATCHLIST_STATE_PATH)
    hypotheses = event_impact_hypothesis_store.load_impact_hypotheses(
        config.EVENT_IMPACT_HYPOTHESIS_STORE_PATH,
        limit=500,
        latest_run=True,
        include_legacy=True,
    )
    core_opportunities = event_core_opportunity_store.load_core_opportunities(
        _event_core_opportunity_store_config_from_runtime().path,
        latest_run=True,
    )
    incidents = event_incident_store.load_incidents(
        config.EVENT_INCIDENT_STORE_PATH,
        limit=500,
        latest_run=True,
        include_legacy=True,
    )
    feedback_rows = [record.__dict__ for record in feedback.records]
    outcome_rows = [row for row in alerts.rows if any(row.get(field) not in (None, "") for field in (
        "primary_horizon_return",
        "return_1h",
        "return_4h",
        "return_24h",
        "return_72h",
        "return_7d",
        "max_favorable_excursion",
        "max_adverse_excursion",
        "mfe_mae_ratio",
        "direction_hit",
        "volatility_hit",
    ))]
    return {
        "runs": runs,
        "alerts": alerts,
        "feedback": feedback,
        "feedback_rows": feedback_rows,
        "missed_rows": missed_rows,
        "provider_rows": provider_rows,
        "budget_rows": budget_rows,
        "watchlist": watchlist,
        "hypotheses": hypotheses,
        "core_opportunities": core_opportunities,
        "incidents": incidents,
        "outcome_rows": outcome_rows,
    }


def event_alpha_burn_in_scorecard(
    days: int = 7,
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_legacy_artifacts: bool = False,
) -> None:
    """Print a multi-artifact burn-in scorecard for Event Alpha."""
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(
            profile_name,
            artifact_namespace,
            include_test_artifacts=include_test_artifacts,
        )
    except ValueError as exc:
        print(str(exc))
        return
    artifact_namespace = artifact_namespace or context.artifact_namespace
    profile_name = profile_name or (context.profile if context.profile != "default" else None)
    runs = event_alpha_run_ledger.load_run_records(config.EVENT_ALPHA_RUN_LEDGER_PATH, limit=500)
    alerts = event_alpha_alert_store.load_alert_snapshots(
        _event_alpha_alert_store_config_from_runtime().path,
        latest_only=False,
    )
    feedback = event_feedback.load_feedback(_event_feedback_config_from_runtime().path)
    missed_rows = event_alpha_missed.load_missed_rows(config.EVENT_ALPHA_MISSED_PATH)
    provider_rows = event_provider_health.load_provider_health(config.EVENT_PROVIDER_HEALTH_PATH)
    budget_rows = event_alpha_burn_in.load_llm_budget_rows(config.EVENT_LLM_BUDGET_LEDGER_PATH)
    scorecard = event_alpha_burn_in.build_burn_in_scorecard(
        run_rows=runs.rows,
        alert_rows=alerts.rows,
        feedback_rows=[record.__dict__ for record in feedback.records],
        missed_rows=missed_rows,
        provider_health_rows=provider_rows,
        llm_budget_rows=budget_rows,
        profile=profile_name,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
        days=days,
    )
    print(_event_alpha_context_block(context))
    print(event_alpha_burn_in.format_burn_in_scorecard(scorecard))


def event_alpha_burn_in_checklist(
    days: int = 7,
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_legacy_artifacts: bool = False,
) -> None:
    """Print the operational burn-in acceptance checklist."""
    _setup_event_discovery_logging(verbose)
    from . import event_alpha_burn_in_checklist as checklist

    try:
        context = resolve_event_alpha_artifact_context_for_report(
            profile_name,
            artifact_namespace,
            include_test_artifacts=include_test_artifacts,
        )
    except ValueError as exc:
        print(str(exc))
        return
    artifact_namespace = artifact_namespace or context.artifact_namespace
    profile_name = profile_name or (context.profile if context.profile != "default" else None)
    runs = event_alpha_run_ledger.load_run_records(config.EVENT_ALPHA_RUN_LEDGER_PATH, limit=500)
    alerts = event_alpha_alert_store.load_alert_snapshots(
        _event_alpha_alert_store_config_from_runtime().path,
        latest_only=False,
    )
    feedback = event_feedback.load_feedback(_event_feedback_config_from_runtime().path)
    missed_rows = event_alpha_missed.load_missed_rows(config.EVENT_ALPHA_MISSED_PATH)
    provider_rows = event_provider_health.load_provider_health(config.EVENT_PROVIDER_HEALTH_PATH)
    budget_rows = event_alpha_burn_in.load_llm_budget_rows(config.EVENT_LLM_BUDGET_LEDGER_PATH)
    scorecard = event_alpha_burn_in.build_burn_in_scorecard(
        run_rows=runs.rows,
        alert_rows=alerts.rows,
        feedback_rows=[record.__dict__ for record in feedback.records],
        missed_rows=missed_rows,
        provider_health_rows=provider_rows,
        llm_budget_rows=budget_rows,
        profile=profile_name,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
        days=days,
    )
    print(_event_alpha_context_block(context))
    print(checklist.format_burn_in_checklist(checklist.build_burn_in_checklist(scorecard)))


def event_alpha_v1_readiness_report(
    days: int = 7,
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_legacy_artifacts: bool = False,
) -> None:
    """Print v1 promotion readiness flags from local research artifacts."""
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(
            profile_name,
            artifact_namespace,
            include_test_artifacts=include_test_artifacts,
        )
    except ValueError as exc:
        print(str(exc))
        return
    artifact_namespace = artifact_namespace or context.artifact_namespace
    artifacts = _event_alpha_local_artifacts(run_limit=500, latest_alerts=False)
    result = event_alpha_v1_readiness.build_v1_readiness(
        run_rows=artifacts["runs"].rows,
        alert_rows=artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        missed_rows=artifacts["missed_rows"],
        provider_health_rows=artifacts["provider_rows"],
        llm_budget_rows=artifacts["budget_rows"],
        outcome_rows=artifacts["outcome_rows"],
        days=days,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
        clock_status=_event_clock_status(),
        generated_at=_event_research_now(),
    )
    print(_event_alpha_context_block(context))
    print(event_alpha_v1_readiness.format_v1_readiness_report(result))


def event_alpha_health_guard_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_legacy_artifacts: bool = False,
) -> None:
    """Print Event Alpha freshness/safety health guard status."""
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(
            profile_name,
            artifact_namespace,
            include_test_artifacts=include_test_artifacts,
        )
    except ValueError as exc:
        print(str(exc))
        return
    artifact_namespace = artifact_namespace or context.artifact_namespace
    if profile_name and not config.EVENT_ALPHA_HEALTH_REQUIRE_PROFILE:
        config.EVENT_ALPHA_HEALTH_REQUIRE_PROFILE = profile_name
    artifacts = _event_alpha_local_artifacts(run_limit=100, latest_alerts=True)
    result = event_alpha_health_guard.evaluate_health_guard(
        run_rows=artifacts["runs"].rows,
        alert_rows=artifacts["alerts"].rows,
        watchlist_entries=artifacts["watchlist"].entries,
        provider_health_rows=artifacts["provider_rows"],
        llm_budget_rows=artifacts["budget_rows"],
        cfg=event_alpha_health_guard.EventAlphaHealthGuardConfig(
            max_run_age_hours=config.EVENT_ALPHA_MAX_RUN_AGE_HOURS,
            max_success_age_hours=config.EVENT_ALPHA_MAX_SUCCESS_AGE_HOURS,
            require_profile=config.EVENT_ALPHA_HEALTH_REQUIRE_PROFILE,
        ),
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    print(_event_alpha_context_block(context))
    print(event_alpha_health_guard.format_health_guard_report(result))


def event_alpha_artifact_doctor_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_legacy_artifacts: bool = False,
    strict: bool = False,
    strict_legacy: bool = False,
    delivery_strict_scope: str | None = None,
) -> None:
    """Print artifact lineage/namespace diagnostics for Event Alpha."""
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(
            profile_name,
            artifact_namespace,
            include_test_artifacts=include_test_artifacts,
        )
    except ValueError as exc:
        print(str(exc))
        return
    artifact_namespace = artifact_namespace or context.artifact_namespace
    profile_name = profile_name or (context.profile if context.profile != "default" else None)
    artifacts = _event_alpha_local_artifacts(run_limit=500, latest_alerts=False)
    cards_dir = Path(config.EVENT_RESEARCH_CARDS_DIR)
    delivery_rows = event_alpha_notification_delivery.load_delivery_records(
        event_alpha_notification_delivery.deliveries_path_for_context(context)
    )
    result = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=artifacts["runs"].rows,
        alert_rows=artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        outcome_rows=artifacts["outcome_rows"],
        hypothesis_rows=artifacts["hypotheses"].rows,
        core_opportunity_rows=event_core_opportunity_store.load_core_opportunities(context.core_opportunity_store_path, latest_run=True).rows,
        watchlist_rows=artifacts["watchlist"].entries,
        incident_rows=artifacts["incidents"].rows,
        evidence_acquisition_rows=event_evidence_acquisition.load_acquisition_results(context.evidence_acquisition_path),
        card_paths=[str(path) for path in _research_card_markdown_paths(cards_dir, include_index=True)],
        provider_health_rows=artifacts["provider_rows"],
        source_coverage_report_path=context.namespace_dir / "event_alpha_source_coverage.md",
        daily_brief_path=context.daily_brief_path,
        llm_budget_rows=artifacts["budget_rows"],
        delivery_rows=delivery_rows,
        profile=profile_name,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
        inspected_alert_store_path=_event_alpha_alert_store_config_from_runtime().path,
        strict=strict or bool(config.EVENT_ALPHA_ARTIFACT_DOCTOR_STRICT),
        strict_legacy=strict_legacy,
        delivery_strict_scope=delivery_strict_scope,
    )
    print(_event_alpha_context_block(context))
    print(event_alpha_artifact_doctor.format_artifact_doctor_report(result))


def event_alpha_send_readiness_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_legacy_artifacts: bool = False,
) -> None:
    """Print final read-only readiness before enabling real Event Alpha sends."""
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(
            profile_name,
            artifact_namespace,
            include_test_artifacts=include_test_artifacts,
        )
    except ValueError as exc:
        print(str(exc))
        return
    artifact_namespace = artifact_namespace or context.artifact_namespace
    profile_name = profile_name or (context.profile if context.profile != "default" else None)
    artifacts = _event_alpha_local_artifacts(run_limit=500, latest_alerts=False)
    delivery_rows = event_alpha_notification_delivery.load_delivery_records(
        event_alpha_notification_delivery.deliveries_path_for_context(context)
    )
    core_rows = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
        include_legacy=True,
    ).rows
    card_paths = [str(path) for path in _research_card_markdown_paths(context.research_cards_dir, include_index=True)]
    doctor = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=artifacts["runs"].rows,
        alert_rows=artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        outcome_rows=artifacts["outcome_rows"],
        hypothesis_rows=artifacts["hypotheses"].rows,
        core_opportunity_rows=core_rows,
        watchlist_rows=artifacts["watchlist"].entries,
        incident_rows=artifacts["incidents"].rows,
        evidence_acquisition_rows=event_evidence_acquisition.load_acquisition_results(context.evidence_acquisition_path),
        card_paths=card_paths,
        provider_health_rows=artifacts["provider_rows"],
        llm_budget_rows=artifacts["budget_rows"],
        delivery_rows=delivery_rows,
        profile=profile_name,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
        inspected_alert_store_path=context.alert_store_path,
        strict=True,
        delivery_strict_scope="latest_run",
    )
    result = event_alpha_send_readiness.build_send_readiness(
        profile=profile_name,
        artifact_namespace=artifact_namespace,
        run_rows=artifacts["runs"].rows,
        core_opportunity_rows=core_rows,
        alert_rows=artifacts["alerts"].rows,
        delivery_rows=delivery_rows,
        artifact_doctor=doctor,
        send_guard_enabled=bool(config.EVENT_ALERTS_ENABLED),
        telegram_ready=bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_IDS),
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    print(_event_alpha_context_block(context))
    print(event_alpha_send_readiness.format_send_readiness(result))


def event_alpha_telegram_final_check_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_legacy_artifacts: bool = False,
) -> None:
    """Print a compact final no-send/send readiness summary for Telegram."""
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(
            profile_name or "notify_llm_deep",
            artifact_namespace,
            include_test_artifacts=include_test_artifacts,
        )
    except ValueError as exc:
        print(str(exc))
        raise SystemExit(1) from exc
    artifact_namespace = artifact_namespace or context.artifact_namespace
    profile_name = profile_name or context.profile
    artifacts = _event_alpha_local_artifacts(run_limit=500, latest_alerts=False)
    delivery_path = event_alpha_notification_delivery.deliveries_path_for_context(context)
    delivery_rows = event_alpha_notification_delivery.load_delivery_records(delivery_path)
    core_rows = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
        include_legacy=True,
    ).rows
    card_paths = [str(path) for path in _research_card_markdown_paths(context.research_cards_dir, include_index=True)]
    doctor = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=artifacts["runs"].rows,
        alert_rows=artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        outcome_rows=artifacts["outcome_rows"],
        hypothesis_rows=artifacts["hypotheses"].rows,
        core_opportunity_rows=core_rows,
        watchlist_rows=artifacts["watchlist"].entries,
        incident_rows=artifacts["incidents"].rows,
        evidence_acquisition_rows=event_evidence_acquisition.load_acquisition_results(context.evidence_acquisition_path),
        card_paths=card_paths,
        provider_health_rows=artifacts["provider_rows"],
        llm_budget_rows=artifacts["budget_rows"],
        delivery_rows=delivery_rows,
        profile=profile_name,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
        inspected_alert_store_path=context.alert_store_path,
        strict=True,
        delivery_strict_scope="latest_run",
    )
    readiness = event_alpha_send_readiness.build_send_readiness(
        profile=profile_name,
        artifact_namespace=artifact_namespace,
        run_rows=artifacts["runs"].rows,
        core_opportunity_rows=core_rows,
        alert_rows=artifacts["alerts"].rows,
        delivery_rows=delivery_rows,
        artifact_doctor=doctor,
        send_guard_enabled=bool(config.EVENT_ALERTS_ENABLED),
        telegram_ready=bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_IDS),
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    latest_delivery_rows = [
        row for row in event_alpha_notification_delivery.latest_rows_by_delivery(delivery_rows)
        if not readiness.latest_run_id or str(row.get("run_id") or "") == readiness.latest_run_id
    ]
    provider_status = event_provider_status.build_event_discovery_provider_status(config)
    lock_status = event_alpha_run_lock.inspect_run_lock(
        context,
        stale_minutes=config.EVENT_ALPHA_NOTIFY_LOCK_STALE_MINUTES,
    )
    pause_state = _event_alpha_notification_pause_state(context)
    go_result = event_alpha_notification_go_no_go.build_go_no_go(
        profile=profile_name,
        artifact_namespace=artifact_namespace,
        telegram_ready=bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_IDS),
        send_guard_enabled=bool(config.EVENT_ALERTS_ENABLED),
        lock_status=lock_status,
        provider_status=provider_status,
        provider_health_rows=event_provider_health.load_provider_health(config.EVENT_PROVIDER_HEALTH_PATH),
        delivery_ledger_path=delivery_path,
        notification_run_ledger_path=context.notification_runs_path,
        research_cards_dir=context.research_cards_dir,
        artifact_doctor_status=doctor.status,
        cooldown_status={},
        llm_budget_status=_event_alpha_llm_budget_status(),
        clock_status=_event_clock_status(),
        notifications_paused=pause_state.paused,
        pause_reason=pause_state.reason,
        send_readiness=readiness,
        delivery_rows=latest_delivery_rows,
        delivery_history_rows=delivery_rows,
    )
    result = event_alpha_telegram_final_check.build_final_check(
        go_no_go_result=go_result,
        doctor_status=doctor.status,
        doctor_blockers=doctor.blockers,
        doctor_warnings=doctor.warnings,
        delivery_rows=delivery_rows,
        core_rows=core_rows,
    )
    print(event_alpha_telegram_final_check.format_final_check(result))
    if result.status == event_alpha_notification_go_no_go.RECOMMEND_NOT_READY:
        raise SystemExit(1)


def event_alpha_tuning_worksheet_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
) -> None:
    """Print weekly tuning recommendations without applying them."""
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(
            profile_name,
            artifact_namespace,
            include_test_artifacts=include_test_artifacts,
        )
    except ValueError as exc:
        print(str(exc))
        return
    artifacts = _event_alpha_local_artifacts(run_limit=500, latest_alerts=False)
    worksheet = event_alpha_tuning.build_tuning_worksheet(
        alert_rows=artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        missed_rows=artifacts["missed_rows"],
        run_rows=artifacts["runs"].rows,
    )
    print(_event_alpha_context_block(context))
    print(event_alpha_tuning.format_tuning_worksheet(worksheet))


def event_alpha_export_burn_in_pack(
    out_path: str,
    days: int = 7,
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_legacy_artifacts: bool = False,
) -> None:
    """Write a clean Event Alpha burn-in review zip."""
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(
            profile_name,
            artifact_namespace,
            include_test_artifacts=include_test_artifacts,
        )
    except ValueError as exc:
        print(str(exc))
        return
    artifact_namespace = artifact_namespace or context.artifact_namespace
    artifacts = _event_alpha_local_artifacts(run_limit=500, latest_alerts=False)
    scorecard = event_alpha_burn_in.build_burn_in_scorecard(
        run_rows=artifacts["runs"].rows,
        alert_rows=artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        missed_rows=artifacts["missed_rows"],
        provider_health_rows=artifacts["provider_rows"],
        llm_budget_rows=artifacts["budget_rows"],
        outcome_rows=artifacts["outcome_rows"],
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
        days=days,
    )
    from . import event_alpha_burn_in_checklist as checklist

    checklist_result = checklist.build_burn_in_checklist(scorecard)
    readiness = event_alpha_v1_readiness.build_v1_readiness(
        run_rows=artifacts["runs"].rows,
        alert_rows=artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        missed_rows=artifacts["missed_rows"],
        provider_health_rows=artifacts["provider_rows"],
        llm_budget_rows=artifacts["budget_rows"],
        outcome_rows=artifacts["outcome_rows"],
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
        days=days,
    )
    health = event_alpha_health_guard.evaluate_health_guard(
        run_rows=artifacts["runs"].rows,
        alert_rows=artifacts["alerts"].rows,
        watchlist_entries=artifacts["watchlist"].entries,
        provider_health_rows=artifacts["provider_rows"],
        llm_budget_rows=artifacts["budget_rows"],
        cfg=event_alpha_health_guard.EventAlphaHealthGuardConfig(
            max_run_age_hours=config.EVENT_ALPHA_MAX_RUN_AGE_HOURS,
            max_success_age_hours=config.EVENT_ALPHA_MAX_SUCCESS_AGE_HOURS,
            require_profile=config.EVENT_ALPHA_HEALTH_REQUIRE_PROFILE,
        ),
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    cards_dir = Path(config.EVENT_RESEARCH_CARDS_DIR)
    doctor = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=artifacts["runs"].rows,
        alert_rows=artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        outcome_rows=artifacts["outcome_rows"],
        hypothesis_rows=artifacts["hypotheses"].rows,
        core_opportunity_rows=event_core_opportunity_store.load_core_opportunities(context.core_opportunity_store_path, latest_run=True).rows,
        watchlist_rows=artifacts["watchlist"].entries,
        incident_rows=artifacts["incidents"].rows,
        evidence_acquisition_rows=event_evidence_acquisition.load_acquisition_results(context.evidence_acquisition_path),
        card_paths=[str(path) for path in _research_card_markdown_paths(cards_dir, include_index=True)],
        provider_health_rows=artifacts["provider_rows"],
        llm_budget_rows=artifacts["budget_rows"],
        profile=config.EVENT_ALPHA_HEALTH_REQUIRE_PROFILE or None,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
        inspected_alert_store_path=_event_alpha_alert_store_config_from_runtime().path,
        strict=bool(config.EVENT_ALPHA_ARTIFACT_DOCTOR_STRICT),
    )
    router_result = event_alpha_router.route_watchlist(
        artifacts["watchlist"],
        cfg=_event_alpha_router_config_from_runtime(),
    )
    daily_brief = event_alpha_daily_brief.build_daily_brief(
        run_rows=artifacts["runs"].rows,
        alert_rows=artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        missed_rows=artifacts["missed_rows"],
        notification_runs=event_alpha_notification_runs.load_notification_runs(config.EVENT_ALPHA_NOTIFICATION_RUNS_PATH).rows,
        hypothesis_rows=event_impact_hypothesis_store.load_impact_hypotheses(config.EVENT_IMPACT_HYPOTHESIS_STORE_PATH, limit=100).rows,
        evidence_acquisition_rows=event_evidence_acquisition.load_acquisition_results(config.EVENT_ALPHA_EVIDENCE_ACQUISITION_PATH),
        watchlist_entries=artifacts["watchlist"].entries,
        router_result=router_result,
        provider_health_rows=artifacts["provider_rows"],
        artifact_namespace=artifact_namespace,
        run_mode=config.EVENT_ALPHA_RUN_MODE,
        run_ledger_path=config.EVENT_ALPHA_RUN_LEDGER_PATH,
        alert_store_path=_event_alpha_alert_store_config_from_runtime().path,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
        clock_status=_event_clock_status(),
        generated_at=_event_research_now(),
    )
    calibration = event_alpha_calibration.format_calibration_report(
        artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        missed_rows=artifacts["missed_rows"],
    )
    source_reliability = event_source_reliability.format_source_reliability_report(
        artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        missed_rows=artifacts["missed_rows"],
        run_rows=artifacts["runs"].rows,
    )
    tuning = event_alpha_tuning.format_tuning_worksheet(event_alpha_tuning.build_tuning_worksheet(
        alert_rows=artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        missed_rows=artifacts["missed_rows"],
        run_rows=artifacts["runs"].rows,
    ))
    result = event_alpha_burn_in_pack.export_burn_in_pack(
        out_path,
        daily_brief=daily_brief,
        burn_in_scorecard=event_alpha_burn_in.format_burn_in_scorecard(scorecard),
        burn_in_checklist=checklist.format_burn_in_checklist(checklist_result),
        v1_readiness=event_alpha_v1_readiness.format_v1_readiness_report(readiness),
        health_guard=event_alpha_health_guard.format_health_guard_report(health),
        artifact_doctor=event_alpha_artifact_doctor.format_artifact_doctor_report(doctor),
        source_reliability=source_reliability,
        calibration=calibration,
        missed="Run --event-alpha-missed-report before exporting if fresh missed rows are required.\n",
        tuning=tuning,
        priors_shadow="Run --event-alpha-priors-shadow-report separately when current provider inputs are configured.\n",
        run_rows=artifacts["runs"].rows,
        alert_rows=artifacts["alerts"].rows,
        feedback_rows=artifacts["feedback_rows"],
        missed_rows=artifacts["missed_rows"],
        outcome_rows=artifacts["outcome_rows"],
        provider_health_rows=artifacts["provider_rows"],
        llm_budget_rows=artifacts["budget_rows"],
        cards_dir=config.EVENT_RESEARCH_CARDS_DIR,
        proposed_eval_dir=config.EVENT_ALPHA_PROPOSED_EVAL_CASES_DIR,
        profile=config.EVENT_ALPHA_HEALTH_REQUIRE_PROFILE or None,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
        date_range=f"{days}d",
    )
    print(event_alpha_burn_in_pack.format_burn_in_pack_result(result))


def event_alpha_calibration_export_priors(out_path: str | None = None, verbose: bool = False) -> None:
    """Write reviewable calibration priors without applying them."""
    _setup_event_discovery_logging(verbose)
    alerts = event_alpha_alert_store.load_alert_snapshots(_event_alpha_alert_store_config_from_runtime().path)
    feedback = event_feedback.load_feedback(_event_feedback_config_from_runtime().path)
    feedback_rows = [record.__dict__ for record in feedback.records]
    path = Path(out_path).expanduser() if out_path else config.EVENT_ALPHA_PRIORS_PATH
    if not path.is_absolute():
        path = config.DATA_DIR / path
    payload = event_alpha_calibration.write_calibration_priors(
        path,
        alerts.rows,
        feedback_rows=feedback_rows,
        generated_at=datetime.now(timezone.utc),
    )
    print(event_alpha_calibration.format_priors_export(path, payload))


def event_alpha_priors_shadow_report(verbose: bool = False) -> None:
    """Print in-memory priors before/after comparison for current Event Alpha alerts."""
    _setup_event_discovery_logging(verbose)
    if not _event_alpha_inputs_configured():
        print(
            "No event-alpha inputs ready for priors shadow report. Configure event sources or enable "
            "RSI_EVENT_ANOMALY_SCANNER_ENABLED=1 with a CoinGecko universe fixture/live source."
        )
        return
    alert_cfg = _event_alert_config_from_runtime()
    result = _event_discovery_result_from_config(now=_event_research_now())
    alerts = event_alerts.build_event_alert_candidates(result, cfg=alert_cfg, now=_event_research_now())
    priors_cfg = _event_alpha_priors_config_from_runtime()
    result_shadow = event_alpha_priors.compare_priors_shadow(alerts, cfg=priors_cfg, alert_cfg=alert_cfg)
    print(event_alpha_priors.format_priors_shadow_report(result_shadow))


def event_alpha_export_eval_cases_from_feedback(out_dir: str | None = None, verbose: bool = False) -> None:
    """Export proposed eval cases from feedback artifacts."""
    _setup_event_discovery_logging(verbose)
    alerts = event_alpha_alert_store.load_alert_snapshots(_event_alpha_alert_store_config_from_runtime().path)
    feedback = event_feedback.load_feedback(_event_feedback_config_from_runtime().path)
    result = event_alpha_eval_export.export_cases_from_feedback(
        alerts.rows,
        [record.__dict__ for record in feedback.records],
        out_dir or config.EVENT_ALPHA_PROPOSED_EVAL_CASES_DIR,
    )
    print(event_alpha_eval_export.format_eval_export_result(result))


def event_alpha_export_eval_cases_from_missed(out_dir: str | None = None, verbose: bool = False) -> None:
    """Export proposed eval cases from missed-opportunity artifacts."""
    _setup_event_discovery_logging(verbose)
    missed_rows = event_alpha_missed.load_missed_rows(config.EVENT_ALPHA_MISSED_PATH)
    result = event_alpha_eval_export.export_cases_from_missed(
        missed_rows,
        out_dir or config.EVENT_ALPHA_PROPOSED_EVAL_CASES_DIR,
    )
    print(event_alpha_eval_export.format_eval_export_result(result))


def event_research_card_report(target: str | None, verbose: bool = False) -> None:
    """Print a Markdown research card for one Event Alpha watchlist/alert key."""
    _setup_event_discovery_logging(verbose)
    watch_cfg = _event_watchlist_config_from_runtime()
    watchlist = event_watchlist.load_watchlist(watch_cfg.state_path or config.EVENT_WATCHLIST_STATE_PATH)
    store_cfg = _event_alpha_alert_store_config_from_runtime()
    alerts = event_alpha_alert_store.load_alert_snapshots(store_cfg.path, latest_only=True)
    core_store = event_core_opportunity_store.load_core_opportunities(
        _event_core_opportunity_store_config_from_runtime().path,
        latest_run=True,
    )
    feedback = event_feedback.load_feedback(_event_feedback_config_from_runtime().path)
    feedback_rows = [record.__dict__ for record in feedback.records]
    outcome_rows = _event_alpha_local_artifacts(run_limit=1, latest_alerts=False)["outcome_rows"]
    routed = event_alpha_router.route_watchlist(watchlist, cfg=_event_alpha_router_config_from_runtime())
    monitor_result = _event_watchlist_monitor_result_from_runtime(watchlist)
    if target:
        result = event_research_cards.render_research_card(
            target,
            watchlist_entries=watchlist.entries,
            alert_rows=[*core_store.rows, *alerts.rows],
            route_decisions=routed.decisions,
            monitor_rows=monitor_result.rows,
            feedback_rows=feedback_rows,
            outcome_rows=outcome_rows,
        )
        print(result.markdown)
        return
    print(
        event_research_cards.render_selected_cards(
            watchlist_entries=watchlist.entries,
            alert_rows=[*core_store.rows, *alerts.rows],
            route_decisions=routed.decisions,
            monitor_rows=monitor_result.rows,
            feedback_rows=feedback_rows,
            outcome_rows=outcome_rows,
        )
    )


def event_research_cards_write(
    verbose: bool = False,
    profile_name: str | None = None,
    *,
    artifact_namespace: str | None = None,
) -> None:
    """Write selected Event Alpha research cards and index markdown files."""
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    watch_cfg = _event_watchlist_config_from_runtime()
    watchlist = event_watchlist.load_watchlist(watch_cfg.state_path or config.EVENT_WATCHLIST_STATE_PATH)
    alerts = event_alpha_alert_store.load_alert_snapshots(
        _event_alpha_alert_store_config_from_runtime().path,
        latest_only=True,
    )
    core_store = event_core_opportunity_store.load_core_opportunities(context.core_opportunity_store_path, latest_run=True)
    feedback = event_feedback.load_feedback(_event_feedback_config_from_runtime().path)
    feedback_rows = [record.__dict__ for record in feedback.records]
    outcome_rows = _event_alpha_local_artifacts(run_limit=1, latest_alerts=False)["outcome_rows"]
    routed = event_alpha_router.route_watchlist(watchlist, cfg=_event_alpha_router_config_from_runtime())
    monitor_result = _event_watchlist_monitor_result_from_runtime(watchlist)
    result = event_research_cards.write_research_cards(
        config.EVENT_RESEARCH_CARDS_DIR,
        watchlist_entries=watchlist.entries,
        alert_rows=[*core_store.rows, *alerts.rows],
        route_decisions=routed.decisions,
        monitor_rows=monitor_result.rows,
        feedback_rows=feedback_rows,
        outcome_rows=outcome_rows,
        selected_tiers=config.EVENT_RESEARCH_CARDS_WRITE_TIERS,
        limit=config.EVENT_RESEARCH_CARDS_WRITE_LIMIT,
        now=datetime.now(timezone.utc),
        lineage_context=_event_alpha_card_lineage_context(
            run_id=_latest_event_alpha_run_id(context.run_ledger_path),
            profile=context.profile,
            run_mode=context.run_mode,
            artifact_namespace=context.artifact_namespace,
        ),
    )
    print(_event_alpha_context_block(context))
    print(event_research_cards.format_card_write_result(result))


def event_alpha_explain_last_run(
    verbose: bool = False,
    profile_name: str | None = None,
    *,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_legacy_artifacts: bool = False,
) -> None:
    """Explain why the latest Event Alpha cycle did or did not alert."""
    _setup_event_discovery_logging(verbose)
    try:
        context = resolve_event_alpha_artifact_context_for_report(
            profile_name,
            artifact_namespace,
            include_test_artifacts=include_test_artifacts,
        )
    except ValueError as exc:
        print(str(exc))
        return
    artifact_namespace = artifact_namespace or context.artifact_namespace
    profile = event_alpha_profiles.get_profile(profile_name) if profile_name else None
    runs = event_alpha_run_ledger.load_run_records(config.EVENT_ALPHA_RUN_LEDGER_PATH, limit=100)
    alerts = event_alpha_alert_store.load_alert_snapshots(
        _event_alpha_alert_store_config_from_runtime().path,
        latest_only=True,
    )
    requested = profile.name if profile else profile_name
    report = event_alpha_explain.format_last_run_explanation(
        runs.rows,
        alert_rows=alerts.rows,
        requested_profile=requested,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    if profile:
        report += (
            f"\nprofile_adjusted_status: profile={profile.name} "
            f"router_enabled={str(bool(config.EVENT_ALPHA_ROUTER_ENABLED)).lower()} "
            f"watchlist_enabled={str(bool(config.EVENT_WATCHLIST_ENABLED)).lower()} "
            f"send_enabled={str(bool(config.EVENT_ALERTS_ENABLED)).lower()}"
        )
    print(_event_alpha_context_block(context))
    print(report)


def event_alpha_daily_brief_report(
    verbose: bool = False,
    profile_name: str | None = None,
    *,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_legacy_artifacts: bool = False,
) -> None:
    """Write and print the daily Event Alpha operating brief."""
    _setup_event_discovery_logging(verbose)
    selected_profile = profile_name
    if not selected_profile:
        selected_profile = _latest_event_alpha_profile_from_runs()
    try:
        context = resolve_event_alpha_artifact_context_for_report(
            selected_profile,
            artifact_namespace,
            include_test_artifacts=include_test_artifacts,
        )
    except ValueError as exc:
        print(str(exc))
        return
    profile = event_alpha_profiles.get_profile(selected_profile) if selected_profile else None
    artifact_namespace = artifact_namespace or context.artifact_namespace
    runs = event_alpha_run_ledger.load_run_records(config.EVENT_ALPHA_RUN_LEDGER_PATH, limit=25)
    alerts = event_alpha_alert_store.load_alert_snapshots(
        _event_alpha_alert_store_config_from_runtime().path,
        latest_only=True,
    )
    core_store = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
    )
    hypotheses = event_impact_hypothesis_store.load_impact_hypotheses(
        context.impact_hypothesis_store_path,
        limit=100,
    )
    feedback = event_feedback.load_feedback(_event_feedback_config_from_runtime().path)
    missed_rows = event_alpha_missed.load_missed_rows(config.EVENT_ALPHA_MISSED_PATH)
    watchlist = event_watchlist.load_watchlist(config.EVENT_WATCHLIST_STATE_PATH)
    router_result = event_alpha_router.route_watchlist(watchlist, cfg=_event_alpha_router_config_from_runtime())
    monitor_result = _event_watchlist_monitor_result_from_runtime(watchlist)
    card_write = event_research_cards.write_research_cards(
        config.EVENT_RESEARCH_CARDS_DIR,
        watchlist_entries=watchlist.entries,
        alert_rows=[*alerts.rows, *hypotheses.rows, *core_store.rows],
        route_decisions=router_result.decisions,
        monitor_rows=monitor_result.rows,
        selected_tiers=config.EVENT_RESEARCH_CARDS_WRITE_TIERS,
        limit=config.EVENT_RESEARCH_CARDS_WRITE_LIMIT,
        now=datetime.now(timezone.utc),
        lineage_context=_event_alpha_card_lineage_context(
            run_id=_latest_event_alpha_run_id(context.run_ledger_path),
            profile=context.profile,
            run_mode=context.run_mode,
            artifact_namespace=artifact_namespace,
        ),
    )
    markdown = event_alpha_daily_brief.build_daily_brief(
        run_rows=runs.rows,
        alert_rows=alerts.rows,
        core_opportunity_rows=core_store.rows,
        feedback_rows=[record.__dict__ for record in feedback.records],
        missed_rows=missed_rows,
        notification_runs=event_alpha_notification_runs.load_notification_runs(context.notification_runs_path).rows,
        hypothesis_rows=hypotheses.rows,
        incident_rows=event_incident_store.load_incidents(context.incident_store_path, limit=100, include_legacy=True).rows,
        evidence_acquisition_rows=event_evidence_acquisition.load_acquisition_results(context.evidence_acquisition_path),
        watchlist_entries=watchlist.entries,
        router_result=router_result,
        provider_health_rows=event_provider_health.load_provider_health(config.EVENT_PROVIDER_HEALTH_PATH),
        card_paths=card_write.card_paths,
        requested_profile=profile.name if profile else profile_name,
        artifact_namespace=artifact_namespace,
        run_mode=context.run_mode,
        run_ledger_path=context.run_ledger_path,
        alert_store_path=context.alert_store_path,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    result = event_alpha_daily_brief.write_daily_brief(
        config.EVENT_ALPHA_DAILY_BRIEF_PATH,
        markdown=markdown,
        card_paths=card_write.card_paths,
    )
    report = _event_alpha_context_block(context) + "\n" + event_alpha_daily_brief.format_daily_brief_result(result)
    if profile:
        report += f"\nprofile_applied: {profile.name}"
    print(report)


def event_alpha_replay_report(
    *,
    priors: bool = False,
    llm_advisory: bool = False,
    raw_events_path: str | None = None,
    market_rows_path: str | None = None,
    compare: str | None = None,
    replay_profile: str | None = None,
    replay_profile_alt: str | None = None,
    verbose: bool = False,
) -> None:
    """Replay Event Alpha local artifacts without provider calls or sends."""
    _setup_event_discovery_logging(verbose)
    if replay_profile:
        _profile, error = _apply_event_alpha_report_profile(replay_profile)
        if error:
            print(error)
            return
    if raw_events_path:
        raw_events = event_alpha_replay.load_raw_events_jsonl(raw_events_path)
        market_rows = event_alpha_replay.load_market_rows(market_rows_path or config.EVENT_DISCOVERY_UNIVERSE_PATH)
        assets = [
            *event_discovery.load_discovery_assets(config.EVENT_DISCOVERY_ALIASES_PATH),
            *event_alpha_replay.assets_from_market_rows(market_rows),
        ]
        llm_cfg = _event_llm_config_from_runtime() if llm_advisory else None
        if compare and any(part.strip().lower() in {"llm", "llm_advisory"} for part in compare.split(",")):
            llm_cfg = _event_llm_config_from_runtime()
        llm_provider = _event_llm_provider(llm_cfg) if llm_cfg and llm_cfg.provider != "openai" else None
        priors_cfg = _event_alpha_priors_config_from_runtime()
        router_cfg = _event_alpha_router_config_from_runtime()
        if compare:
            result = event_alpha_replay.compare_replay_policies(
                raw_events=raw_events,
                assets=assets,
                market_rows=market_rows,
                policies=_replay_policy_names(compare),
                alert_cfg=_event_alert_config_from_runtime(),
                priors_cfg=priors_cfg,
                llm_provider=llm_provider,
                llm_cfg=llm_cfg,
                router_cfg=router_cfg,
                router_threshold_variant=event_alpha_router.EventAlphaRouterConfig(
                    enabled=router_cfg.enabled,
                    include_suppressed=router_cfg.include_suppressed,
                    daily_digest_enabled=router_cfg.daily_digest_enabled,
                    instant_enabled=router_cfg.instant_enabled,
                    max_digest_items=router_cfg.max_digest_items,
                    max_high_priority_per_day=router_cfg.max_high_priority_per_day,
                    per_key_cooldown_hours=0,
                    alert_on_score_jump=True,
                    score_jump_threshold=max(1, router_cfg.score_jump_threshold // 2),
                    alert_on_new_independent_source=router_cfg.alert_on_new_independent_source,
                    alert_on_event_time_upgrade=router_cfg.alert_on_event_time_upgrade,
                    alert_on_derivatives_crowding_upgrade=router_cfg.alert_on_derivatives_crowding_upgrade,
                    alert_on_cluster_confidence_upgrade=router_cfg.alert_on_cluster_confidence_upgrade,
                ),
                profile_variant_router_cfg=_router_config_from_profile(replay_profile_alt),
                now=_event_research_now(),
            )
            print(event_alpha_replay.format_replay_comparison_report(result))
            return
        if priors:
            priors_cfg = event_alpha_priors.EventAlphaPriorsConfig(
                enabled=True,
                path=priors_cfg.path,
                min_multiplier=priors_cfg.min_multiplier,
                max_multiplier=priors_cfg.max_multiplier,
            )
        result = event_alpha_replay.replay_from_raw_events(
            raw_events=raw_events,
            assets=assets,
            market_rows=market_rows,
            alert_cfg=_event_alert_config_from_runtime(),
            priors_cfg=priors_cfg,
            llm_provider=llm_provider,
            llm_cfg=llm_cfg,
            router_cfg=router_cfg,
            now=_event_research_now(),
        )
        print(event_alpha_replay.format_replay_report(result))
        return
    alerts = event_alpha_replay.load_jsonl_rows(config.EVENT_ALPHA_ALERT_STORE_PATH)
    watchlist_rows = event_alpha_replay.load_jsonl_rows(config.EVENT_WATCHLIST_STATE_PATH)
    result = event_alpha_replay.replay_from_artifacts(
        alert_rows=alerts,
        watchlist_rows=watchlist_rows,
        priors_enabled=priors,
        llm_advisory=llm_advisory,
    )
    print(event_alpha_replay.format_replay_report(result))


def _replay_policy_names(value: str) -> tuple[str, ...]:
    aliases = {
        "llm": "llm_advisory",
        "threshold": "router_threshold_variant",
        "router": "router_threshold_variant",
        "profile": "profile_variant",
    }
    out: list[str] = []
    for part in str(value or "").split(","):
        name = part.strip().lower()
        if not name:
            continue
        out.append(aliases.get(name, name))
    return tuple(out or ["baseline"])


def _router_config_from_profile(profile_name: str | None) -> event_alpha_router.EventAlphaRouterConfig | None:
    if not profile_name:
        return None
    try:
        profile = event_alpha_profiles.get_profile(profile_name)
    except ValueError:
        return None
    overrides = dict(profile.config_overrides)
    current = _event_alpha_router_config_from_runtime()
    return event_alpha_router.EventAlphaRouterConfig(
        enabled=bool(overrides.get("EVENT_ALPHA_ROUTER_ENABLED", current.enabled)),
        include_suppressed=current.include_suppressed,
        daily_digest_enabled=bool(overrides.get("EVENT_ALPHA_ROUTER_DAILY_DIGEST_ENABLED", current.daily_digest_enabled)),
        instant_enabled=bool(overrides.get("EVENT_ALPHA_ROUTER_INSTANT_ENABLED", current.instant_enabled)),
        max_digest_items=int(overrides.get("EVENT_ALPHA_ROUTER_MAX_DIGEST_ITEMS", current.max_digest_items)),
        validated_hypothesis_digest_enabled=bool(
            overrides.get(
                "EVENT_ALPHA_VALIDATED_HYPOTHESIS_DIGEST_ENABLED",
                current.validated_hypothesis_digest_enabled,
            )
        ),
        max_validated_hypothesis_digest_items=int(
            overrides.get(
                "EVENT_ALPHA_VALIDATED_HYPOTHESIS_MAX_ITEMS",
                overrides.get(
                    "EVENT_ALPHA_VALIDATED_HYPOTHESIS_DIGEST_MAX_ITEMS",
                    current.max_validated_hypothesis_digest_items,
                ),
            )
        ),
        validated_hypothesis_min_score=float(
            overrides.get(
                "EVENT_ALPHA_VALIDATED_HYPOTHESIS_DIGEST_MIN_SCORE",
                current.validated_hypothesis_min_score,
            )
        ),
        validated_hypothesis_min_opportunity_score=float(
            overrides.get(
                "EVENT_ALPHA_VALIDATED_HYPOTHESIS_MIN_OPPORTUNITY_SCORE",
                current.validated_hypothesis_min_opportunity_score,
            )
        ),
        validated_hypothesis_min_final_score=float(
            overrides.get(
                "EVENT_ALPHA_VALIDATED_HYPOTHESIS_MIN_FINAL_SCORE",
                current.validated_hypothesis_min_final_score,
            )
        ),
        validated_hypothesis_require_external_or_direct_event=bool(
            overrides.get(
                "EVENT_ALPHA_VALIDATED_HYPOTHESIS_REQUIRE_EXTERNAL_OR_DIRECT_EVENT",
                current.validated_hypothesis_require_external_or_direct_event,
            )
        ),
        validated_hypothesis_require_impact_path=bool(
            overrides.get(
                "EVENT_ALPHA_VALIDATED_HYPOTHESIS_REQUIRE_IMPACT_PATH",
                current.validated_hypothesis_require_impact_path,
            )
        ),
        weak_validated_local_only=bool(
            overrides.get(
                "EVENT_ALPHA_WEAK_VALIDATED_LOCAL_ONLY",
                current.weak_validated_local_only,
            )
        ),
        allow_weak_path_with_market_confirmation=bool(
            overrides.get(
                "EVENT_ALPHA_ALLOW_WEAK_PATH_WITH_MARKET_CONFIRMATION",
                current.allow_weak_path_with_market_confirmation,
            )
        ),
        block_generic_cooccurrence_digest=bool(
            overrides.get(
                "EVENT_ALPHA_BLOCK_GENERIC_COOCCURRENCE_DIGEST",
                current.block_generic_cooccurrence_digest,
            )
        ),
        max_high_priority_per_day=int(
            overrides.get("EVENT_ALPHA_ROUTER_MAX_HIGH_PRIORITY_PER_DAY", current.max_high_priority_per_day)
        ),
        per_key_cooldown_hours=float(overrides.get("EVENT_ALPHA_ROUTER_PER_KEY_COOLDOWN_HOURS", current.per_key_cooldown_hours)),
        alert_on_score_jump=bool(overrides.get("EVENT_ALPHA_ROUTER_ALERT_ON_SCORE_JUMP", current.alert_on_score_jump)),
        score_jump_threshold=int(overrides.get("EVENT_ALPHA_ROUTER_SCORE_JUMP_THRESHOLD", current.score_jump_threshold)),
        alert_on_new_independent_source=bool(
            overrides.get("EVENT_ALPHA_ROUTER_ALERT_ON_NEW_INDEPENDENT_SOURCE", current.alert_on_new_independent_source)
        ),
        alert_on_event_time_upgrade=bool(
            overrides.get("EVENT_ALPHA_ROUTER_ALERT_ON_EVENT_TIME_UPGRADE", current.alert_on_event_time_upgrade)
        ),
        alert_on_derivatives_crowding_upgrade=bool(
            overrides.get(
                "EVENT_ALPHA_ROUTER_ALERT_ON_DERIVATIVES_CROWDING_UPGRADE",
                current.alert_on_derivatives_crowding_upgrade,
            )
        ),
        alert_on_cluster_confidence_upgrade=bool(
            overrides.get("EVENT_ALPHA_ROUTER_ALERT_ON_CLUSTER_CONFIDENCE_UPGRADE", current.alert_on_cluster_confidence_upgrade)
        ),
    )


def event_alpha_prune_artifacts(confirm: bool = False, verbose: bool = False) -> None:
    """Dry-run or confirm pruning of old Event Alpha research artifacts."""
    _setup_event_discovery_logging(verbose)
    result = event_alpha_retention.prune_event_alpha_artifacts(
        _event_alpha_retention_config_from_runtime(),
        confirm=confirm,
        now=datetime.now(timezone.utc),
    )
    print(event_alpha_retention.format_retention_report(result))


def event_llm_shadow_report(verbose: bool = False, event_now: str | datetime | None = None) -> None:
    """Print research-only shadow LLM relationship analysis for event candidates."""
    _setup_event_discovery_logging(verbose)
    if not _event_discovery_paths_configured():
        print(
            "No event-discovery sources ready. Set RSI_EVENT_DISCOVERY_EVENTS_PATH, "
            "another event-discovery fixture path, or opt into a live research provider. "
            "Run --event-discovery-status for a redacted readiness report."
        )
        return
    llm_cfg = _event_llm_config_from_runtime()
    if llm_cfg.mode not in {"shadow", "advisory"}:
        print("Event LLM analysis blocked: RSI_EVENT_LLM_MODE must be shadow or advisory.")
        return
    provider = _event_llm_provider(llm_cfg)
    if provider is None:
        return
    alert_cfg = _event_alert_config_from_runtime()
    now = _event_research_now(event_now)
    result = _event_discovery_result_from_config(now=now)
    alerts = event_alerts.build_event_alert_candidates(result, cfg=alert_cfg, now=now)
    rows = event_llm_analyzer.analyze_event_candidates(
        result,
        alerts,
        provider,
        cfg=llm_cfg,
    )
    print(event_llm_analyzer.format_llm_shadow_report(rows))


def event_llm_extract_report(verbose: bool = False, event_now: str | datetime | None = None) -> None:
    """Print research-only LLM raw-event extraction for discovery evidence."""
    _setup_event_discovery_logging(verbose)
    if not _event_discovery_paths_configured():
        print(
            "No event-discovery sources ready. Set RSI_EVENT_DISCOVERY_EVENTS_PATH, "
            "another event-discovery fixture path, or opt into a live research provider. "
            "Run --event-discovery-status for a redacted readiness report."
        )
        return
    extractor_cfg = _event_llm_extractor_config_from_runtime()
    if extractor_cfg.mode not in {"shadow", "advisory"}:
        print("Event LLM extractor blocked: RSI_EVENT_LLM_EXTRACTOR_MODE must be shadow or advisory.")
        return
    provider = _event_llm_extraction_provider(extractor_cfg)
    if provider is None:
        return
    now = _event_research_now(event_now)
    result = _event_discovery_result_from_config(now=now)
    rows = event_llm_extractor.analyze_raw_events(
        result.raw_events,
        provider,
        cfg=extractor_cfg,
    )
    print(event_llm_extractor.format_llm_extract_report(rows))


def _event_llm_provider(llm_cfg: event_llm_analyzer.EventLLMConfig):
    provider_name = llm_cfg.provider.strip().lower()
    if provider_name == "fixture":
        return FixtureLLMRelationshipProvider()
    if provider_name == "openai":
        if not llm_cfg.enabled:
            print("Event LLM OpenAI provider disabled. Set RSI_EVENT_LLM_ENABLED=1 to opt into live LLM calls.")
            return None
        return OpenAILLMRelationshipProvider(
            api_key=config.OPENAI_API_KEY,
            model=llm_cfg.model,
            prompt_version=llm_cfg.prompt_version,
            timeout=config.EVENT_LLM_OPENAI_TIMEOUT,
        )
    print(f"Unknown event LLM provider: {llm_cfg.provider}. Use fixture or openai.")
    return None


def _event_llm_extraction_provider(extractor_cfg: event_llm_extractor.EventLLMExtractorConfig):
    provider_name = extractor_cfg.provider.strip().lower()
    if provider_name == "fixture":
        return FixtureLLMExtractionProvider()
    if provider_name == "openai":
        if not extractor_cfg.enabled:
            print(
                "Event LLM OpenAI extractor disabled. "
                "Set RSI_EVENT_LLM_EXTRACTOR_ENABLED=1 to opt into live LLM calls."
            )
            return None
        return OpenAILLMExtractionProvider(
            api_key=config.OPENAI_API_KEY,
            model=extractor_cfg.model,
            prompt_version=extractor_cfg.prompt_version,
            timeout=config.EVENT_LLM_EXTRACTOR_OPENAI_TIMEOUT,
        )
    print(f"Unknown event LLM extractor provider: {extractor_cfg.provider}. Use fixture or openai.")
    return None


def _event_llm_catalyst_frame_provider(catalyst_frame_cfg: event_llm_catalyst_frames.EventLLMCatalystFrameConfig):
    provider_name = catalyst_frame_cfg.provider.strip().lower()
    if provider_name == "fixture":
        return FixtureLLMCatalystFrameProvider()
    if provider_name == "openai":
        if not catalyst_frame_cfg.enabled:
            print(
                "Event LLM catalyst-frame OpenAI provider disabled. "
                "Set RSI_EVENT_LLM_CATALYST_FRAMES_ENABLED=1 to opt into live LLM calls."
            )
            return None
        return OpenAILLMRelationshipProvider(
            api_key=config.OPENAI_API_KEY,
            model=catalyst_frame_cfg.model,
            prompt_version=catalyst_frame_cfg.prompt_version,
            timeout=config.EVENT_LLM_OPENAI_TIMEOUT,
        )
    print(f"Unknown event LLM catalyst-frame provider: {catalyst_frame_cfg.provider}. Use fixture or openai.")
    return None


def _event_catalyst_search_provider(
    search_cfg: event_catalyst_search.EventCatalystSearchConfig,
):
    provider_names = tuple(
        name.strip().lower()
        for name in (search_cfg.providers or (search_cfg.provider,))
        if name and name.strip()
    )
    providers = []
    warnings: list[str] = []
    for provider_name in provider_names or ("fixture",):
        if provider_name == "fixture":
            providers.append(event_catalyst_search.FixtureCatalystSearchProvider(
                path=config.EVENT_CATALYST_SEARCH_FIXTURE_PATH,
            ))
        elif provider_name == "gdelt":
            providers.append(event_catalyst_search.GdeltCatalystSearchProvider(
                path=config.EVENT_DISCOVERY_GDELT_PATH,
                live_enabled=config.EVENT_DISCOVERY_GDELT_LIVE,
                base_url=config.EVENT_DISCOVERY_GDELT_BASE_URL,
                max_records=config.EVENT_DISCOVERY_GDELT_MAX_RECORDS,
                timeout=config.EVENT_DISCOVERY_GDELT_TIMEOUT,
            ))
        elif provider_name in {"rss", "project_rss", "project_blog_rss"}:
            providers.append(event_catalyst_search.ProjectRssCatalystSearchProvider(
                path=config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH,
                live_enabled=config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE,
                feed_urls=config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS,
                timeout=config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_TIMEOUT,
            ))
        elif provider_name == "cryptopanic":
            providers.append(event_catalyst_search.CryptoPanicCatalystSearchProvider(
                path=config.EVENT_DISCOVERY_CRYPTOPANIC_PATH,
                live_enabled=config.EVENT_DISCOVERY_CRYPTOPANIC_LIVE,
                api_token=config.EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN,
                base_url=config.EVENT_DISCOVERY_CRYPTOPANIC_BASE_URL,
                public=config.EVENT_DISCOVERY_CRYPTOPANIC_PUBLIC,
                filter_name=config.EVENT_DISCOVERY_CRYPTOPANIC_FILTER,
                currencies=config.EVENT_DISCOVERY_CRYPTOPANIC_CURRENCIES,
                regions=config.EVENT_DISCOVERY_CRYPTOPANIC_REGIONS,
                kind=config.EVENT_DISCOVERY_CRYPTOPANIC_KIND,
                timeout=config.EVENT_DISCOVERY_CRYPTOPANIC_TIMEOUT,
            ))
        elif provider_name == "polymarket":
            providers.append(event_catalyst_search.PolymarketCatalystSearchProvider(
                path=config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH,
                live_enabled=config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE,
                base_url=config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_BASE_URL,
                limit=config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIMIT,
                timeout=config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_TIMEOUT,
            ))
        elif provider_name == "coinmarketcal":
            providers.append(event_catalyst_search.EventProviderCatalystSearchProvider(
                lambda query: CoinMarketCalProvider(config.EVENT_DISCOVERY_COINMARKETCAL_PATH),
                name="coinmarketcal",
                filter_by_query=True,
                max_fetches_per_search=1,
            ))
        elif provider_name == "tokenomist":
            providers.append(event_catalyst_search.EventProviderCatalystSearchProvider(
                lambda query: TokenomistProvider(config.EVENT_DISCOVERY_TOKENOMIST_PATH),
                name="tokenomist",
                filter_by_query=True,
                max_fetches_per_search=1,
            ))
        else:
            warnings.append(provider_name)
    if warnings:
        print(
            "Unknown event catalyst-search provider(s): "
            f"{', '.join(warnings)}. Known: fixture, gdelt, rss, cryptopanic, polymarket, coinmarketcal, tokenomist."
        )
    if not providers:
        return None
    health_cfg = _event_provider_health_config_from_runtime()
    providers = [
        provider
        if str(getattr(provider, "name", "")).lower() == "fixture"
        else event_provider_health.HealthCheckedProvider(provider, cfg=health_cfg)
        for provider in providers
    ]
    if len(providers) == 1:
        return providers[0]
    return event_catalyst_search.CompositeCatalystSearchProvider(providers)


def _event_evidence_acquisition_providers_from_runtime(
    cfg: event_evidence_acquisition.EvidenceAcquisitionConfig,
):
    """Return source-pack provider dispatch for evidence acquisition."""
    providers: dict[str, object | None] = {}
    fixture_provider = event_catalyst_search.FixtureCatalystSearchProvider(
        path=config.EVENT_CATALYST_SEARCH_FIXTURE_PATH,
    )
    if cfg.fixture_only:
        for key in (
            "default",
            "fixture",
            "cryptopanic",
            "project_blog_rss",
            "rss",
            "polymarket",
            "official_exchange",
            "binance_announcements",
            "bybit_announcements",
            "coinmarketcal",
            "tokenomist",
            "coinalyze",
            "sports_fixtures",
        ):
            providers[key] = fixture_provider
        return providers

    providers["default"] = fixture_provider
    providers["fixture"] = fixture_provider
    providers["cryptopanic"] = event_catalyst_search.CryptoPanicCatalystSearchProvider(
        path=config.EVENT_DISCOVERY_CRYPTOPANIC_PATH,
        live_enabled=config.EVENT_DISCOVERY_CRYPTOPANIC_LIVE,
        api_token=config.EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN,
        base_url=config.EVENT_DISCOVERY_CRYPTOPANIC_BASE_URL,
        public=config.EVENT_DISCOVERY_CRYPTOPANIC_PUBLIC,
        filter_name=config.EVENT_DISCOVERY_CRYPTOPANIC_FILTER,
        currencies=config.EVENT_DISCOVERY_CRYPTOPANIC_CURRENCIES,
        regions=config.EVENT_DISCOVERY_CRYPTOPANIC_REGIONS,
        kind=config.EVENT_DISCOVERY_CRYPTOPANIC_KIND,
        timeout=min(config.EVENT_DISCOVERY_CRYPTOPANIC_TIMEOUT, cfg.timeout_seconds),
    )
    providers["project_blog_rss"] = event_catalyst_search.ProjectRssCatalystSearchProvider(
        path=config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH,
        live_enabled=config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE,
        feed_urls=config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS,
        timeout=min(config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_TIMEOUT, cfg.timeout_seconds),
    )
    providers["rss"] = providers["project_blog_rss"]
    providers["polymarket"] = event_catalyst_search.PolymarketCatalystSearchProvider(
        path=config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH,
        live_enabled=config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE,
        base_url=config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_BASE_URL,
        limit=config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIMIT,
        timeout=min(config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_TIMEOUT, cfg.timeout_seconds),
    )
    official_exchange = event_catalyst_search.CompositeCatalystSearchProvider((
        event_catalyst_search.EventProviderCatalystSearchProvider(
            lambda query: BinanceAnnouncementProvider(
                config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH,
                live_enabled=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE,
                api_key=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_KEY,
                api_secret=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_SECRET,
                ws_url=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_WS_URL,
                topic=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_TOPIC,
                recv_window_ms=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_RECV_WINDOW_MS,
                listen_seconds=min(config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LISTEN_SECONDS, cfg.timeout_seconds),
                max_messages=config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_MAX_MESSAGES,
            ),
            name="binance_announcements",
            filter_by_query=True,
            max_fetches_per_search=1,
        ),
        event_catalyst_search.EventProviderCatalystSearchProvider(
            lambda query: BybitAnnouncementProvider(
                config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH,
                live_enabled=config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE,
                base_url=config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_BASE_URL,
                locale=config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LOCALE,
                announcement_type=config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_TYPE,
                limit=config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIMIT,
                timeout=min(config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_TIMEOUT, cfg.timeout_seconds),
            ),
            name="bybit_announcements",
            filter_by_query=True,
            max_fetches_per_search=1,
        ),
    ))
    providers["official_exchange"] = official_exchange
    providers["binance_announcements"] = official_exchange
    providers["bybit_announcements"] = official_exchange
    providers["coinmarketcal"] = event_catalyst_search.EventProviderCatalystSearchProvider(
        lambda query: CoinMarketCalProvider(config.EVENT_DISCOVERY_COINMARKETCAL_PATH),
        name="coinmarketcal",
        filter_by_query=True,
        max_fetches_per_search=1,
    )
    providers["tokenomist"] = event_catalyst_search.EventProviderCatalystSearchProvider(
        lambda query: TokenomistProvider(config.EVENT_DISCOVERY_TOKENOMIST_PATH),
        name="tokenomist",
        filter_by_query=True,
        max_fetches_per_search=1,
    )
    providers["coinalyze"] = fixture_provider
    providers["sports_fixtures"] = fixture_provider
    return providers


def _send_event_alert_digest(
    alerts: list[event_alerts.EventAlertCandidate],
    cfg: event_alerts.EventAlertConfig,
    *,
    now: datetime | None = None,
) -> None:
    if not cfg.enabled:
        print("Event research alert sending disabled. Set RSI_EVENT_ALERTS_ENABLED=1 to opt in.")
        return
    if cfg.mode != "research_only":
        print("Event research alert sending blocked: RSI_EVENT_ALERT_MODE must remain research_only.")
        return
    digest = event_alerts.digest_candidates(alerts, cfg=cfg)
    if not digest:
        print("Event research alert sending skipped: no candidates above digest threshold.")
        return
    storage = Storage(config.DB_PATH)
    try:
        now = now or datetime.now(timezone.utc)
        due, reason = _event_alert_digest_due(storage, cfg, now)
        if not due:
            print(f"Event research alert sending held: {reason}.")
            return
        recipients = storage.active_subscribers() or config.TELEGRAM_CHAT_IDS
        sent = send_telegram(
            event_alerts.format_event_alert_telegram_digest(digest),
            parse_mode="HTML",
            chat_ids=recipients,
        )
        if sent:
            _mark_event_alert_digest_sent(storage, len(digest), now)
            print(f"Event research Telegram digest sent with {len(digest)} item(s).")
        else:
            print("Event research Telegram digest not sent: no channel delivered.")
    finally:
        storage.close()


def _send_event_alpha_routed_digest(
    decisions: list[event_alpha_router.EventAlphaRouteDecision],
    cfg: event_alerts.EventAlertConfig,
    *,
    now: datetime | None = None,
    profile: str | None = None,
    pipeline_result: event_alpha_pipeline.EventAlphaPipelineResult | None = None,
    card_path_by_alert_id: dict[str, str | Path] | None = None,
    include_health_heartbeat: bool = False,
    clock_status: dict[str, object] | None = None,
    delivery_cfg: event_alpha_notification_delivery.NotificationDeliveryConfig | None = None,
    run_id: str | None = None,
    namespace: str | None = None,
    pause_state: event_alpha_notification_pause.EventAlphaNotificationPauseState | None = None,
    core_opportunity_rows: Iterable[Mapping[str, object]] = (),
) -> event_alpha_pipeline.EventAlphaSendResult:
    all_decisions = list(decisions)
    alertable = [decision for decision in all_decisions if decision.alertable]
    storage = Storage(config.DB_PATH)
    try:
        now = now or datetime.now(timezone.utc)
        notif_cfg = _event_alpha_notification_config_from_runtime(profile)
        notif_cfg = replace(notif_cfg, enabled=cfg.enabled, mode=cfg.mode)
        if not alertable and not include_health_heartbeat and not notif_cfg.exploratory_digest_enabled:
            print("Event Alpha routed alert sending skipped: no router-approved escalations.")
            return event_alpha_pipeline.EventAlphaSendResult(
                requested=True,
                attempted=False,
                block_reason="no router-approved escalations",
            )
        clock_blocker = _event_alpha_notify_fixed_clock_blocker(clock_status or _event_clock_status())
        if clock_blocker:
            plan = event_alpha_notifications.build_notification_plan(
                all_decisions,
                storage=storage,
                cfg=notif_cfg,
                now=now,
                include_health_heartbeat=include_health_heartbeat,
                core_opportunity_rows=core_opportunity_rows,
            )
            result = event_alpha_pipeline.EventAlphaSendResult(
                requested=True,
                attempted=False,
                items_attempted=plan.would_send_count,
                items_delivered=0,
                block_reason=clock_blocker,
                lane_items_attempted=plan.lane_counts,
                lane_items_delivered={lane: 0 for lane in event_alpha_notifications.LANES},
                would_send_items=plan.would_send_count,
                heartbeat_due=plan.heartbeat_due,
                cooldown_blocks=dict(plan.blocked_by_lane),
                notification_scope=plan.notification_scope,
                notification_scope_value=plan.scope_value,
                research_review_digest_enabled=notif_cfg.research_review_digest_enabled,
                research_review_digest_candidates=len(plan.research_review_items),
                research_review_digest_would_send=plan.lane_counts.get(
                    event_alpha_notifications.LANE_RESEARCH_REVIEW_DIGEST,
                    0,
                ),
                research_review_digest_sent=0,
                research_review_digest_block_reason=plan.blocked_by_lane.get(
                    event_alpha_notifications.LANE_RESEARCH_REVIEW_DIGEST
                ),
            )
            print(f"Event Alpha routed notifications would send {result.would_send_items} item(s); blocked: {clock_blocker}.")
            return result
        recipients = storage.active_subscribers() or config.TELEGRAM_CHAT_IDS
        result = event_alpha_notifications.send_notifications(
            all_decisions,
            storage=storage,
            cfg=notif_cfg,
            now=now,
            profile=profile,
            pipeline_result=pipeline_result,
            card_path_by_alert_id=card_path_by_alert_id,
            core_opportunity_rows=core_opportunity_rows,
            include_health_heartbeat=include_health_heartbeat,
            delivery_cfg=delivery_cfg,
            run_id=run_id,
            namespace=namespace,
            pause_state=pause_state,
            send_fn=lambda message: send_telegram_structured(
                message,
                parse_mode="HTML",
                chat_ids=recipients,
            ),
        )
        if result.attempted and result.success:
            print(
                "Event Alpha routed Telegram notification(s) sent: "
                f"{result.items_delivered}/{result.items_attempted} item(s)."
            )
        elif result.attempted:
            print(
                "Event Alpha routed Telegram notification(s) attempted but not fully delivered: "
                f"{result.block_reason or 'unknown'}."
            )
        elif result.would_send_items:
            print(
                "Event Alpha routed notifications would send "
                f"{result.would_send_items} item(s); blocked: {result.block_reason or 'not due'}."
            )
        elif not alertable and not include_health_heartbeat:
            print("Event Alpha routed alert sending skipped: no router-approved escalations.")
        else:
            print(f"Event Alpha routed alert sending held: {result.block_reason or 'no due notifications'}.")
        return result
    finally:
        storage.close()


def _event_alert_digest_due(
    storage: Storage,
    cfg: event_alerts.EventAlertConfig,
    now: datetime,
) -> tuple[bool, str]:
    last_raw = storage.get_meta("event_alert_last_digest_at")
    if last_raw:
        try:
            last = datetime.fromisoformat(last_raw)
            last = last if last.tzinfo else last.replace(tzinfo=timezone.utc)
        except ValueError:
            last = None
        if last and (now - last.astimezone(timezone.utc)).total_seconds() / 3600.0 < cfg.cooldown_hours:
            return False, f"cooldown active for {cfg.cooldown_hours:g}h"
    day_key = f"event_alert_sent_count_{now.date().isoformat()}"
    try:
        sent_today = int(storage.get_meta(day_key) or "0")
    except ValueError:
        sent_today = 0
    if sent_today >= cfg.max_instant_per_day:
        return False, f"daily send cap reached ({cfg.max_instant_per_day})"
    return True, "due"


def _mark_event_alert_digest_sent(storage: Storage, item_count: int, now: datetime) -> None:
    storage.set_meta("event_alert_last_digest_at", now.isoformat())
    day_key = f"event_alert_sent_count_{now.date().isoformat()}"
    try:
        sent_today = int(storage.get_meta(day_key) or "0")
    except ValueError:
        sent_today = 0
    storage.set_meta(day_key, str(sent_today + 1))
    storage.set_meta("event_alert_last_digest_items", str(item_count))


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


def event_discovery_refresh(verbose: bool = False, event_now: str | datetime | None = None) -> None:
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
    now = _event_research_now(event_now)
    result = _event_discovery_result_from_config(now=now)
    diagnostics = _event_discovery_refresh_diagnostics(result, status_report)
    write = event_cache.write_event_discovery_cache(
        result,
        config.EVENT_DISCOVERY_CACHE_DIR,
        observed_at=now,
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


def event_discovery_binance_listen(verbose: bool = False, event_now: str | datetime | None = None) -> None:
    """Listen briefly to Binance announcements and cache raw research evidence."""
    _setup_event_discovery_logging(verbose)
    if not config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE:
        print(
            "Binance announcement listener disabled. Set "
            "RSI_EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE=1 and API credentials."
        )
        return
    now = _event_research_now(event_now)
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


def event_fade_auto_report(verbose: bool = False, event_now: str | datetime | None = None) -> None:
    """Print grouped research-only event-fade candidates from discovery fixtures."""
    _setup_event_discovery_logging(verbose)
    if not _event_discovery_paths_configured():
        print(
            "No event-discovery sources ready. Set RSI_EVENT_DISCOVERY_EVENTS_PATH, "
            "another event-discovery fixture path, or opt into a live research provider. "
            "Run --event-discovery-status for a redacted readiness report."
        )
        return
    now = _event_research_now(event_now)
    result = _event_discovery_result_from_config(now=now)
    print(event_discovery.format_event_fade_auto_report(result))


def event_fade_export_sample(path: str, verbose: bool = False, event_now: str | datetime | None = None) -> None:
    """Export discovery-fed event-fade validation sample rows."""
    _setup_event_discovery_logging(verbose)
    if not _event_discovery_paths_configured():
        print(
            "No event-discovery sources ready. Set RSI_EVENT_DISCOVERY_EVENTS_PATH, "
            "another event-discovery fixture path, or opt into a live research provider. "
            "Run --event-discovery-status for a redacted readiness report."
        )
        return
    now = _event_research_now(event_now)
    result = _event_discovery_result_from_config(now=now)
    rows = event_discovery.event_fade_validation_sample_rows(result, exported_at=now)
    if path == "-":
        print(event_discovery.format_validation_sample_jsonl(rows))
        return
    out = event_discovery.write_validation_sample(rows, path)
    print(f"Event-fade validation sample: wrote {len(rows)} row(s) to {out}")


def event_fade_export_cache_sample(
    path: str,
    verbose: bool = False,
    event_now: str | datetime | None = None,
) -> None:
    """Export latest cached event-discovery snapshots as validation sample rows."""
    _setup_event_discovery_logging(verbose)
    _event_research_now(event_now)
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


def event_fade_check_review_template(
    sample_path: str,
    template_path: str,
    *,
    verbose: bool = False,
) -> None:
    """Dry-check an edited compact review sidecar before applying it."""
    _setup_event_discovery_logging(verbose)
    sample_rows = event_validation.load_validation_sample(sample_path)
    template_rows = event_validation.load_validation_sample(template_path)
    check = event_validation.check_review_template(sample_rows, template_rows)
    print(event_validation.format_review_template_check(check))
    if not check.ready_to_apply:
        raise SystemExit(1)


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
    event_now: str | datetime | None = None,
) -> None:
    """Write a local event-fade validation review workspace."""
    _setup_event_discovery_logging(verbose)
    source_rows = event_validation.load_validation_sample(sample_path)
    bundle_rows, review_merge = _merge_review_rows_for_bundle(source_rows, reviewed_path)
    generated_at = _event_research_now(event_now)
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
        generated_at=generated_at,
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
    event_now: str | datetime | None = None,
) -> None:
    """Write a local review workspace from latest cached event-discovery snapshots."""
    _setup_event_discovery_logging(verbose)
    read = event_cache.load_cached_validation_sample(config.EVENT_DISCOVERY_CACHE_DIR)
    bundle_rows, review_merge = _merge_review_rows_for_bundle(read.rows, reviewed_path)
    generated_at = _event_research_now(event_now)
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
        generated_at=generated_at,
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
    generated_at: datetime | None = None,
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
    balanced_template_rows = event_validation.build_balanced_review_template_rows(review_rows)
    bundle_warnings = tuple([_empty_review_bundle_message(sample_path)] if not review_rows else [])

    queue_path = bundle_dir / "labeling_queue.txt"
    packet_path = bundle_dir / "review_packet.md"
    balanced_packet_path = bundle_dir / "review_packet_balanced.md"
    template_path = bundle_dir / "review_template.csv"
    balanced_template_path = bundle_dir / "review_template_balanced.csv"
    report_path = bundle_dir / "review_report.txt"
    guide_path = bundle_dir / "review_guide.md"
    manifest_path = bundle_dir / "manifest.json"
    readme_path = bundle_dir / "README.md"

    queue_path.write_text(event_validation.format_labeling_queue(queue) + "\n", encoding="utf-8")
    packet_path.write_text(event_validation.format_review_packet(review_rows, limit=limit) + "\n", encoding="utf-8")
    balanced_packet_path.write_text(
        event_validation.format_balanced_review_packet(review_rows) + "\n",
        encoding="utf-8",
    )
    template_path.write_text(event_validation.format_review_template_csv(template_rows), encoding="utf-8")
    balanced_template_path.write_text(
        event_validation.format_review_template_csv(balanced_template_rows),
        encoding="utf-8",
    )
    report_path.write_text(event_validation.format_validation_review(review) + "\n", encoding="utf-8")
    guide_path.write_text(_event_fade_review_guide(), encoding="utf-8")
    manifest = _event_fade_review_bundle_manifest(
        sample_path=sample_path,
        prices_path=prices_path,
        overwrite_outcomes=overwrite_outcomes,
        copied_sample=copied_sample,
        price_export=price_export_result,
        outcome_sample=outcome_sample,
        queue_path=queue_path,
        packet_path=packet_path,
        balanced_packet_path=balanced_packet_path,
        template_path=template_path,
        balanced_template_path=balanced_template_path,
        balanced_template_rows=len(balanced_template_rows),
        report_path=report_path,
        guide_path=guide_path,
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
        generated_at=generated_at,
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
            balanced_packet_path=balanced_packet_path,
            template_path=template_path,
            balanced_template_path=balanced_template_path,
            report_path=report_path,
            guide_path=guide_path,
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
    balanced_packet_path: Path,
    template_path: Path,
    balanced_template_path: Path,
    balanced_template_rows: int,
    report_path: Path,
    guide_path: Path,
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
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    files = {
        "readme": readme_path.name,
        "validation_sample": copied_sample.name,
        "labeling_queue": queue_path.name,
        "review_packet": packet_path.name,
        "review_packet_balanced": balanced_packet_path.name,
        "review_template": template_path.name,
        "review_template_balanced": balanced_template_path.name,
        "review_report": report_path.name,
        "review_guide": guide_path.name,
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
        "generated_at": (generated_at or datetime.now(timezone.utc)).isoformat(),
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
        "balanced_review_template": {
            "rows": balanced_template_rows,
            "proxy_limit": event_validation.DEFAULT_BALANCED_PROXY_REVIEW_ROWS,
            "control_limit": event_validation.DEFAULT_BALANCED_CONTROL_REVIEW_ROWS,
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
            "missing_review_provenance_rows": review.missing_review_provenance_rows,
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
    balanced_packet_path: Path,
    template_path: Path,
    balanced_template_path: Path,
    report_path: Path,
    guide_path: Path,
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
        f"- `{balanced_packet_path.name}`: human-readable evidence packet matching the balanced sidecar",
        f"- `{template_path.name}`: compact editable CSV sidecar",
        f"- `{balanced_template_path.name}`: gate-balanced editable CSV sidecar with proxy candidates and negative controls",
        f"- `{guide_path.name}`: label taxonomy, review provenance, and event-time review rules",
        f"- `{report_path.name}`: current review metrics and promotion blockers",
        f"- `{manifest_path.name}`: machine-readable bundle provenance and counts",
        "",
        "Suggested workflow:",
        "1. Read `review_guide.md` for label and timing rules.",
        "2. Read `review_packet_balanced.md` for evidence matching `review_template_balanced.csv`; use `review_packet.md` for strict priority rows.",
        "3. For fastest promotion-gate coverage, edit `review_template_balanced.csv`; for strict priority order, edit `review_template.csv`.",
        "4. Fill `review_status`, `reviewed_by`, `reviewed_at`, `human_label`, `human_notes`, any human event-time confirmation, and any missing outcomes. Use `external_asset`, `primary_source_url`, `source_search_url`, `source_date_hint`, `source_providers`, `primary_raw_title`, `review_prompt`, and `event_time_review_hint` as reviewer aids only.",
        "5. Dry-check the edited sidecar with `main.py --event-fade-check-review-template SAMPLE TEMPLATE`.",
        "6. Apply the checked sidecar with `main.py --event-fade-apply-review-template SAMPLE TEMPLATE OUT`.",
        "7. Run `main.py --event-fade-review-sample OUT` to inspect coverage and blockers.",
        "",
    ])


def _event_fade_review_guide() -> str:
    return "\n".join([
        "# Event-Fade Review Guide",
        "",
        "Research-only: this guide is for labeling validation artifacts. It does not promote alerts, paper trades, or execution.",
        "",
        "## Label Rules",
        "",
        "Use exactly one `human_label` value per reviewed row:",
        "",
        "- `valid_proxy_fade`: the crypto asset is a true proxy instrument for a dated external catalyst, not the direct beneficiary, and the evidence would have been knowable before the decision time.",
        "- `false_positive`: the row looked proxy-like to the system but manual review says it is not a valid proxy-fade setup.",
        "- `direct_event`: the catalyst directly changes the asset's own listing, supply, emissions, protocol, utility, or structural demand.",
        "- `ambiguous`: the evidence is too weak, ticker-only, generic market chatter, or cannot be resolved to a clear proxy/direct relationship.",
        "",
        "Set `review_status=reviewed` only after checking the source evidence. Rows with labels but without `review_status=reviewed` do not count as reviewed evidence.",
        "",
        "Fill `reviewed_by` with the reviewer name or handle and `reviewed_at` with an ISO timestamp. These fields make copied labels auditable across refreshed samples, and missing provenance blocks promotion.",
        "",
        "## Proxy Criteria",
        "",
        "A valid proxy-fade candidate should have all of these:",
        "",
        "- a dated external catalyst or expiry",
        "- a crypto asset used as synthetic exposure, attention exposure, fan exposure, or prediction-market-style proxy",
        "- `is_direct_beneficiary=false`",
        "- source evidence available before the decision time",
        "",
        "Examples that should usually be `direct_event`: BTC/BTC ETF, ETH/ETH ETF, token unlocks, exchange listings, airdrops, TGEs, mainnet launches, and protocol upgrades.",
        "",
        "## Event-Time Confirmation",
        "",
        "If the machine `event_time` is blank, weak, or inferred from text, fill the separate human fields instead of editing `event_time`:",
        "",
        "- `human_event_time`: ISO timestamp for the catalyst, preferably UTC with an offset, for example `2026-06-20T13:30:00+00:00`",
        "- `human_event_time_source`: URL or title proving that timestamp",
        "- `human_event_time_confidence`: reviewer confidence from `0.0` to `1.0`; use `0.80` or higher only for explicit source evidence",
        "- `human_event_time_notes`: short note explaining how the timestamp was confirmed",
        "",
        "Validation metrics may use high-confidence `human_event_time` for review-only timing checks and event-time baselines, but it remains separate from the machine-discovered `event_time`.",
        "",
        "## Review Template Helper Columns",
        "",
        "`review_template.csv` and `review_template_balanced.csv` include reviewer-only helper columns:",
        "",
        "- `external_asset`: machine-extracted external catalyst identity; verify it against the source before using `valid_proxy_fade`",
        "- `primary_source_url`: first source URL to open for the row",
        "- `primary_source_origin`: first normalized publisher/origin",
        "- `primary_raw_title`: first raw source title",
        "- `source_search_url`: title/publisher search link for finding the canonical article when the primary source is a feed or Google News wrapper",
        "- `source_date_hint`: date-like phrases found in the source title or event name, such as a date range, event year, `today`, or `tonight`; use it only as a cue to verify explicit source timing",
        "- `source_providers`: discovery provider(s) that supplied the row, such as `project_blog_rss`, `gdelt`, or `prediction_market_events`",
        "- `review_prompt`: compact instruction for the queued review category",
        "- `event_time_review_hint`: whether the event time is missing, inferred/weak, or explicit/high-confidence",
        "",
        "These helper columns are not copied back into validation samples and do not affect evidence matching. The fields that count are still `review_status`, `reviewed_by`, `reviewed_at`, `human_label`, `human_notes`, `human_event_time*`, and required outcome fields.",
        "",
        "`review_template.csv` follows strict labeling-queue priority. `review_template_balanced.csv` is better for building the validation sample because it includes triggered rows, proxy candidates, and direct/ambiguous negative controls in one sidecar.",
        "Run `main.py --event-fade-check-review-template SAMPLE TEMPLATE` before applying an edited sidecar; it catches changed evidence, unmatched rows, missing provenance, unknown labels, missing outcomes, and valid proxy labels without explicit catalyst timing.",
        "",
        "## Outcome Fields",
        "",
        "For reviewed `SHORT_TRIGGERED` rows, fill or verify:",
        "",
        "- `max_adverse_excursion`",
        "- `max_favorable_excursion`",
        "- `post_event_return_72h`",
        "- `event_time_post_event_return_72h`",
        "",
        "Prefer locally filled 1h outcomes when available; daily outcomes are coarse and can hide intraday squeeze risk.",
        "",
        "## Promotion Reminder",
        "",
        "Do not promote event fade beyond local reports until the review report clears the proxy/control/trigger sample-size, source-diversity, timing, and outcome-quality gates.",
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
        f"- Review provenance missing: {review.missing_review_provenance_rows}",
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
        "--event-alert-report",
        action="store_true",
        help="Print ranked research-only event-alert candidates from discovery fixtures.",
    )
    parser.add_argument(
        "--event-alpha-radar-report",
        action="store_true",
        help="Print research-only event alpha radar with opt-in market enrichment/anomaly inputs.",
    )
    parser.add_argument(
        "--event-alpha-cycle",
        action="store_true",
        help="Run one unified research-only Event Alpha cycle (alerts, watchlist, router summary).",
    )
    parser.add_argument(
        "--event-alpha-notify-cycle",
        action="store_true",
        help="Run a day-1 Event Alpha notification burn-in cycle with lane-specific guarded sends.",
    )
    parser.add_argument(
        "--ignore-provider-backoff",
        action="store_true",
        help="With --event-alpha-notify-cycle, attempt providers even if local provider health is in backoff for this run only.",
    )
    parser.add_argument(
        "--event-alpha-notify-preview",
        action="store_true",
        help="Preview Event Alpha notification readiness, would-send counts, and lane cooldowns.",
    )
    parser.add_argument(
        "--event-alpha-notify-go-no-go",
        action="store_true",
        help="Print Event Alpha notification preview/send go-no-go readiness.",
    )
    parser.add_argument(
        "--event-alpha-environment-doctor",
        action="store_true",
        help="Print scheduled Event Alpha notification environment readiness.",
    )
    parser.add_argument(
        "--event-alpha-pause-notifications",
        action="store_true",
        help="Write a namespace-scoped Event Alpha notification pause file.",
    )
    parser.add_argument(
        "--event-alpha-resume-notifications",
        action="store_true",
        help="Clear the namespace-scoped Event Alpha notification pause file. Requires --confirm.",
    )
    parser.add_argument(
        "--event-alpha-scheduler-status",
        action="store_true",
        help="Print Event Alpha scheduled notification run freshness and lock status.",
    )
    parser.add_argument(
        "--event-alpha-generate-launchd",
        action="store_true",
        help="Print or write a launchd plist template for scheduled Event Alpha notifications.",
    )
    parser.add_argument(
        "--event-alpha-notification-slo-report",
        action="store_true",
        help="Print Event Alpha notification SLO/freshness status.",
    )
    parser.add_argument(
        "--event-alpha-export-notification-pack",
        action="store_true",
        help="Write a redacted zip of notification artifacts and operator reports. Use --out OUT.zip.",
    )
    parser.add_argument(
        "--event-alpha-notification-checklist",
        action="store_true",
        help="Print day-1 Event Alpha notification startup checklist.",
    )
    parser.add_argument(
        "--event-alpha-send-readiness",
        action="store_true",
        help="Check latest notification rehearsal artifacts before enabling real Event Alpha Telegram sends.",
    )
    parser.add_argument(
        "--event-alpha-telegram-final-check",
        action="store_true",
        help="Print compact final Event Alpha Telegram no-send/readiness result from existing artifacts.",
    )
    parser.add_argument(
        "--event-alpha-send-test",
        action="store_true",
        help="Send one guarded research-only Event Alpha heartbeat without running providers.",
    )
    parser.add_argument(
        "--event-alpha-telegram-recipient-check",
        action="store_true",
        help="Send a guarded research-only Telegram diagnostic to each configured Event Alpha recipient.",
    )
    parser.add_argument(
        "--ignore-notification-pause",
        action="store_true",
        help="Allow --event-alpha-send-test to bypass the local notification pause file.",
    )
    parser.add_argument(
        "--event-alpha-notification-runs-report",
        action="store_true",
        help="Print recent Event Alpha notification-cycle summary rows.",
    )
    parser.add_argument(
        "--event-alpha-notification-inbox",
        action="store_true",
        help="Print unreviewed Event Alpha notification/card follow-up queues.",
    )
    parser.add_argument(
        "--event-alpha-burn-in-review",
        action="store_true",
        help="Print a compact burn-in notification review inbox instead of the full row-level inbox.",
    )
    parser.add_argument(
        "--event-alpha-notification-deliveries-report",
        action="store_true",
        help="Print the research-only Event Alpha notification delivery ledger for a profile/namespace.",
    )
    parser.add_argument(
        "--event-alpha-notification-retry-failed",
        action="store_true",
        help="List failed Event Alpha notification deliveries (dry-run scaffold; --confirm required to proceed).",
    )
    parser.add_argument(
        "--event-alpha-provider-health-report",
        action="store_true",
        help="Print profile-scoped Event Alpha provider health/backoff rows.",
    )
    parser.add_argument(
        "--event-alpha-cryptopanic-preflight",
        action="store_true",
        help="Print redacted CryptoPanic readiness/backoff/source-pack preflight for Event Alpha.",
    )
    parser.add_argument(
        "--event-alpha-source-coverage-report",
        action="store_true",
        help="Print source-pack provider/evidence coverage for Event Alpha research artifacts.",
    )
    parser.add_argument(
        "--event-alpha-provider-health-reset",
        action="store_true",
        help="Clear selected profile-scoped provider health backoff state. Requires --confirm.",
    )
    parser.add_argument(
        "--event-alpha-notify-fixture-smoke",
        action="store_true",
        help="Run a local fake-sender Event Alpha notification smoke under a fixture namespace.",
    )
    parser.add_argument(
        "--event-alpha-notification-runs-path",
        default=None,
        help="Optional Event Alpha notification summary JSONL path.",
    )
    parser.add_argument(
        "--event-alpha-runs-report",
        action="store_true",
        help="Print recent research-only Event Alpha cycle run ledger rows.",
    )
    parser.add_argument(
        "--event-impact-hypotheses-report",
        action="store_true",
        help="Print stored research-only Event Impact Hypothesis rows for a profile/namespace.",
    )
    parser.add_argument(
        "--event-impact-hypotheses-inbox",
        action="store_true",
        help="Print stored Event Impact Hypothesis rows needing operator review for a profile/namespace.",
    )
    parser.add_argument(
        "--event-incidents-report",
        action="store_true",
        help="Print stored canonical Event Alpha incident rows for a profile/namespace.",
    )
    parser.add_argument(
        "--event-impact-hypothesis-smoke",
        action="store_true",
        help="Run offline Event Impact Hypothesis smoke: SpaceX sector hypothesis validates VELVET RADAR only.",
    )
    parser.add_argument(
        "--event-impact-hypothesis-store-path",
        default=None,
        help="Optional Event Impact Hypothesis JSONL path for --event-impact-hypotheses-report.",
    )
    parser.add_argument(
        "--event-incident-store-path",
        default=None,
        help="Optional canonical incident JSONL path for --event-incidents-report.",
    )
    parser.add_argument(
        "--include-diagnostic-incidents",
        action="store_true",
        help="For --event-incidents-report, include diagnostic/raw/external-context incidents that are hidden by default.",
    )
    parser.add_argument(
        "--include-raw-incidents",
        action="store_true",
        help="For --event-incidents-report, include raw-observation incidents hidden by default.",
    )
    parser.add_argument(
        "--include-external-context-incidents",
        action="store_true",
        help="For --event-incidents-report, include external-context-only incidents hidden by default.",
    )
    parser.add_argument(
        "--latest-run",
        action="store_true",
        help="For impact-hypothesis reports, show only rows from the latest stored run_id. This is the default unless --all-history, --run-id, or --since is used.",
    )
    parser.add_argument(
        "--all-history",
        action="store_true",
        help="For impact-hypothesis reports, include all historical rows instead of defaulting to the latest run.",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="For impact-hypothesis reports, show only rows from this stored run_id.",
    )
    parser.add_argument(
        "--since",
        default=None,
        help="For impact-hypothesis reports, show rows observed at or after this ISO timestamp.",
    )
    parser.add_argument(
        "--include-legacy",
        action="store_true",
        help="For impact-hypothesis reports, include legacy/missing-schema rows in filtered output.",
    )
    parser.add_argument(
        "--event-alpha-run-ledger-path",
        default=None,
        help="Optional Event Alpha run ledger JSONL path for --event-alpha-runs-report.",
    )
    parser.add_argument(
        "--event-alpha-run-limit",
        type=int,
        default=20,
        help="Maximum rows to show for --event-alpha-runs-report.",
    )
    parser.add_argument(
        "--event-alpha-status",
        action="store_true",
        help="Print profile-aware Event Alpha source, artifact, send, and LLM budget status.",
    )
    parser.add_argument(
        "--event-alpha-preflight",
        action="store_true",
        help="Preflight profile-scoped Event Alpha artifact paths, providers, LLM budget, and send guards.",
    )
    parser.add_argument(
        "--event-alpha-feedback-readiness",
        action="store_true",
        help="Check Event Alpha card lineage, inbox feedback targets, and calibration fields without sending or mutating tiers.",
    )
    parser.add_argument(
        "--event-watchlist-refresh",
        action="store_true",
        help="Refresh research-only event alpha watchlist state from current alert candidates.",
    )
    parser.add_argument(
        "--event-watchlist-report",
        action="store_true",
        help="Print latest research-only event alpha watchlist state.",
    )
    parser.add_argument(
        "--event-watchlist-monitor",
        action="store_true",
        help="Monitor active event alpha watchlist rows without requiring new source evidence.",
    )
    parser.add_argument(
        "--event-alpha-router-report",
        action="store_true",
        help="Print research-only Event Alpha Radar route decisions from watchlist state.",
    )
    parser.add_argument(
        "--event-alpha-signal-quality-eval",
        action="store_true",
        help="Run the offline curated Event Alpha signal-quality benchmark.",
    )
    parser.add_argument(
        "--event-alpha-signal-quality-cases-path",
        default=None,
        help="Optional JSON fixture path for --event-alpha-signal-quality-eval.",
    )
    parser.add_argument(
        "--event-opportunity-audit",
        metavar="TARGET",
        help="Explain one Event Alpha opportunity decision path from local artifacts.",
    )
    parser.add_argument(
        "--event-alpha-quality-review",
        action="store_true",
        help="Print latest Event Alpha signal-quality review from local artifacts.",
    )
    parser.add_argument(
        "--event-alpha-quality-coverage-report",
        action="store_true",
        help="Strictly check latest-run Event Alpha artifact rows for top-level signal-quality fields.",
    )
    parser.add_argument(
        "--event-alpha-policy-simulate",
        action="store_true",
        help="Simulate Event Alpha quality threshold policies from local artifacts without writing state.",
    )
    parser.add_argument(
        "--event-alpha-export-signal-quality-cases",
        action="store_true",
        help="Export proposed signal-quality benchmark cases from local artifacts.",
    )
    parser.add_argument(
        "--event-alpha-signal-quality-export-path",
        default=None,
        help="Optional output path for --event-alpha-export-signal-quality-cases.",
    )
    parser.add_argument(
        "--event-alpha-missed-report",
        action="store_true",
        help="Print missed-opportunity diagnostics from market rows and Event Alpha artifacts.",
    )
    parser.add_argument(
        "--event-alpha-near-miss-report",
        action="store_true",
        help="Print near-promotion Event Alpha candidates and targeted refresh diagnostics.",
    )
    parser.add_argument(
        "--event-alpha-calibration-report",
        action="store_true",
        help="Print research-only calibration summaries from alert, feedback, outcome, and missed artifacts.",
    )
    parser.add_argument(
        "--event-source-reliability-report",
        action="store_true",
        help="Print source/provider reliability summaries from Event Alpha artifacts.",
    )
    parser.add_argument(
        "--event-alpha-burn-in-scorecard",
        action="store_true",
        help="Print Event Alpha burn-in scorecard from run/alert/feedback/missed/provider artifacts.",
    )
    parser.add_argument(
        "--event-alpha-burn-in-checklist",
        action="store_true",
        help="Print Event Alpha burn-in acceptance checklist for research-send readiness.",
    )
    parser.add_argument(
        "--event-alpha-burn-in-readiness",
        action="store_true",
        help="Print live-style no-send Event Alpha burn-in readiness from local artifacts.",
    )
    parser.add_argument(
        "--event-alpha-v1-readiness",
        action="store_true",
        help="Print v1 promotion readiness flags for Event Alpha burn-in artifacts.",
    )
    parser.add_argument(
        "--event-alpha-health-guard",
        action="store_true",
        help="Print Event Alpha run freshness/safety guard status.",
    )
    parser.add_argument(
        "--event-alpha-artifact-doctor",
        action="store_true",
        help="Diagnose Event Alpha artifact lineage, namespace, and snapshot consistency.",
    )
    parser.add_argument(
        "--event-alpha-tuning-worksheet",
        action="store_true",
        help="Print weekly Event Alpha tuning suggestions without applying changes.",
    )
    parser.add_argument(
        "--event-alpha-export-burn-in-pack",
        metavar="OUT_ZIP",
        help="Write a clean Event Alpha burn-in review pack zip.",
    )
    parser.add_argument(
        "--event-alpha-burn-in-days",
        "--days",
        type=int,
        default=7,
        dest="event_alpha_burn_in_days",
        help="Lookback window for --event-alpha-burn-in-scorecard.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output path for commands that write one artifact, such as --event-alpha-generate-launchd.",
    )
    parser.add_argument(
        "--event-alpha-calibration-export-priors",
        nargs="?",
        const="",
        metavar="OUT",
        help="Export reviewable Event Alpha calibration priors JSON; defaults to RSI_EVENT_ALPHA_PRIORS_PATH.",
    )
    parser.add_argument(
        "--event-alpha-export-eval-cases-from-feedback",
        nargs="?",
        const="",
        metavar="OUT_DIR",
        help="Export proposed eval cases from feedback artifacts without modifying canonical fixtures.",
    )
    parser.add_argument(
        "--event-alpha-export-eval-cases-from-missed",
        nargs="?",
        const="",
        metavar="OUT_DIR",
        help="Export proposed eval cases from missed-opportunity artifacts.",
    )
    parser.add_argument(
        "--event-alpha-explain-last-run",
        action="store_true",
        help="Explain why the latest Event Alpha cycle did or did not alert.",
    )
    parser.add_argument(
        "--event-alpha-daily-brief",
        action="store_true",
        help="Write and print a daily Event Alpha research brief from local artifacts.",
    )
    parser.add_argument(
        "--event-alpha-replay",
        action="store_true",
        help="Replay Event Alpha local artifacts without provider calls or sends.",
    )
    parser.add_argument(
        "--event-alpha-replay-raw-events",
        default=None,
        help="Optional raw event JSONL/cache path for true local Event Alpha replay.",
    )
    parser.add_argument(
        "--event-alpha-replay-market-rows",
        default=None,
        help="Optional CoinGecko-style market rows path for --event-alpha-replay-raw-events.",
    )
    parser.add_argument(
        "--event-alpha-replay-priors",
        action="store_true",
        help="With --event-alpha-replay, show priors before/after score fields when present.",
    )
    parser.add_argument(
        "--event-alpha-replay-llm-advisory",
        action="store_true",
        help="With --event-alpha-replay, annotate the replay as LLM-advisory comparison mode.",
    )
    parser.add_argument(
        "--event-alpha-replay-compare",
        default=None,
        help="With --event-alpha-replay and raw events, compare policies such as baseline,llm,priors.",
    )
    parser.add_argument(
        "--event-alpha-replay-profile",
        default=None,
        help="Apply a profile before replaying local raw-event evidence.",
    )
    parser.add_argument(
        "--event-alpha-replay-profile-alt",
        default=None,
        help="Profile used for the profile_variant replay comparison row.",
    )
    parser.add_argument(
        "--event-alpha-prune-artifacts",
        action="store_true",
        help="Dry-run retention pruning for old Event Alpha research artifacts.",
    )
    parser.add_argument(
        "--event-alpha-priors-shadow-report",
        action="store_true",
        help="Compare current Event Alpha alert tiers/scores before and after priors without writing artifacts.",
    )
    parser.add_argument(
        "--event-opportunity-audit-include-diagnostics",
        action="store_true",
        help="With --event-opportunity-audit, include hidden diagnostic/source-noise/control rows in core opportunity audits.",
    )
    parser.add_argument(
        "--event-research-card",
        nargs="?",
        const="",
        metavar="ALERT_KEY",
        help="Print a Markdown Event Alpha research card for ALERT_KEY, or selected local cards when omitted.",
    )
    parser.add_argument(
        "--event-research-cards-write",
        action="store_true",
        help="Write selected Event Alpha research cards plus index.md under RSI_EVENT_RESEARCH_CARDS_DIR.",
    )
    parser.add_argument(
        "--event-alpha-alerts-report",
        action="store_true",
        help="Print research-only Event Alpha alert snapshot cohorts and filled outcomes.",
    )
    parser.add_argument(
        "--event-alpha-alert-store-path",
        default=None,
        help="Optional Event Alpha alert snapshot JSONL path for report/outcome commands.",
    )
    parser.add_argument(
        "--event-alpha-fill-outcomes",
        nargs=2,
        metavar=("PRICES", "OUT"),
        help="Fill Event Alpha alert snapshot outcomes from local OHLCV price fixture PRICES and write OUT.",
    )
    parser.add_argument(
        "--event-feedback-mark",
        metavar="TARGET",
        help=(
            "Append lightweight Event Alpha feedback for a watchlist key, event id, symbol, "
            "coin id, or missed opportunity target."
        ),
    )
    parser.add_argument(
        "--event-feedback-label",
        choices=event_feedback.valid_labels(),
        help="Feedback label to use with --event-feedback-mark.",
    )
    parser.add_argument(
        "--event-feedback-notes",
        default=None,
        help="Optional notes to append with --event-feedback-mark.",
    )
    parser.add_argument(
        "--event-feedback-by",
        default="human",
        help="Reviewer name to append with --event-feedback-mark.",
    )
    parser.add_argument(
        "--event-feedback-path",
        default=None,
        help="Optional feedback JSONL artifact path for mark/report commands.",
    )
    parser.add_argument(
        "--event-feedback-report",
        action="store_true",
        help="Print lightweight Event Alpha feedback artifact rows.",
    )
    parser.add_argument("--event-feedback-useful", metavar="TARGET", help="Shortcut: mark TARGET as useful.")
    parser.add_argument("--event-feedback-junk", metavar="TARGET", help="Shortcut: mark TARGET as junk.")
    parser.add_argument("--event-feedback-watch", metavar="TARGET", help="Shortcut: mark TARGET as watch.")
    parser.add_argument("--event-feedback-traded", metavar="TARGET", help="Shortcut: mark TARGET as traded elsewhere.")
    parser.add_argument("--event-feedback-ignore", metavar="TARGET", help="Shortcut: mark TARGET as ignored.")
    parser.add_argument("--event-feedback-missed", metavar="SYMBOL_OR_COIN_ID", help="Shortcut: record a missed opportunity.")
    parser.add_argument(
        "--event-llm-shadow-report",
        action="store_true",
        help="Print research-only shadow LLM relationship analysis for event candidates.",
    )
    parser.add_argument(
        "--event-llm-extract-report",
        action="store_true",
        help="Print research-only shadow LLM raw-event extraction for discovery evidence.",
    )
    parser.add_argument(
        "--event-catalyst-search-report",
        action="store_true",
        help="Print research-only market-anomaly catalyst-search diagnostics.",
    )
    parser.add_argument(
        "--event-alpha-profile",
        default=None,
        help=(
            "Apply an Event Alpha operational research profile "
            f"({', '.join(event_alpha_profiles.profile_names())})."
        ),
    )
    parser.add_argument(
        "--event-alpha-artifact-namespace",
        default=None,
        help="Restrict Event Alpha artifact reports to this namespace/profile artifact directory.",
    )
    parser.add_argument(
        "--provider-key",
        default=None,
        help="Provider health key selector for --event-alpha-provider-health-reset, such as gdelt:event_source.",
    )
    parser.add_argument(
        "--service",
        default=None,
        help="Provider health service selector for --event-alpha-provider-health-reset, such as gdelt.",
    )
    parser.add_argument(
        "--role",
        default=None,
        help="Provider health role selector for --event-alpha-provider-health-reset, such as event_source.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="With --event-alpha-provider-health-reset, clear all provider backoffs in the selected profile namespace.",
    )
    parser.add_argument(
        "--reason",
        default=None,
        help="Operator reason for --event-alpha-pause-notifications.",
    )
    parser.add_argument(
        "--event-alpha-include-test-artifacts",
        action="store_true",
        help="Include Event Alpha rows marked test/fixture/replay in artifact reports.",
    )
    parser.add_argument(
        "--event-alpha-include-legacy-artifacts",
        action="store_true",
        help="Include legacy/default Event Alpha artifact rows in artifact reports for migration review.",
    )
    parser.add_argument(
        "--event-alpha-artifact-doctor-strict",
        action="store_true",
        help="Escalate fresh/current artifact mismatches, mixed namespaces, and unknown IDs to artifact-doctor blockers.",
    )
    parser.add_argument(
        "--event-alpha-artifact-doctor-strict-legacy",
        action="store_true",
        help="With strict artifact doctor, also escalate legacy quality-route conflicts to blockers.",
    )
    parser.add_argument(
        "--event-alpha-artifact-doctor-delivery-scope",
        choices=("latest_run", "all_rows", "legacy_included"),
        default=None,
        help="Scope strict notification-delivery identity checks; default checks the latest run when available.",
    )
    parser.add_argument(
        "--event-alpha-profile-report",
        metavar="PROFILE",
        help="Print an Event Alpha operational profile without running the cycle.",
    )
    parser.add_argument(
        "--event-alert-send",
        action="store_true",
        help=(
            "With --event-alert-report, send an opt-in Telegram research digest. "
            "Requires RSI_EVENT_ALERTS_ENABLED=1."
        ),
    )
    parser.add_argument(
        "--with-llm",
        action="store_true",
        help=(
            "With --event-alert-report, run event LLM analysis. "
            "Advisory tier changes require RSI_EVENT_LLM_MODE=advisory."
        ),
    )
    parser.add_argument(
        "--event-now",
        default=None,
        help=(
            "Override the event research clock for deterministic reports "
            "(ISO-8601, e.g. 2026-06-15T16:00:00Z)."
        ),
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
        "--event-fade-check-review-template",
        nargs=2,
        metavar=("SAMPLE", "TEMPLATE"),
        help="Dry-check edited compact review sidecar rows before applying them.",
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
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm commands that are dry-run by default, such as --event-alpha-prune-artifacts.",
    )
    args = parser.parse_args()
    if args.event_alpha_artifact_namespace:
        config.EVENT_ALPHA_ARTIFACT_NAMESPACE = args.event_alpha_artifact_namespace
        if not args.event_alpha_profile:
            _apply_event_alpha_artifact_context(None)

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
        event_fade_report(verbose=args.verbose, event_now=args.event_now)
        return
    if args.event_discovery_report:
        event_discovery_report(verbose=args.verbose, event_now=args.event_now)
        return
    if args.event_alert_report:
        event_alert_report(
            verbose=args.verbose,
            send=args.event_alert_send,
            with_llm=args.with_llm,
            event_now=args.event_now,
        )
        return
    if args.event_alpha_radar_report:
        event_alpha_radar_report(verbose=args.verbose, with_llm=args.with_llm, event_now=args.event_now)
        return
    if args.event_alpha_cycle:
        event_alpha_cycle(
            verbose=args.verbose,
            with_llm=args.with_llm,
            send=args.event_alert_send,
            event_now=args.event_now,
            profile_name=args.event_alpha_profile,
        )
        return
    if args.event_alpha_notify_cycle:
        event_alpha_notify_cycle(
            verbose=args.verbose,
            with_llm=args.with_llm,
            send=args.event_alert_send,
            event_now=args.event_now,
            profile_name=args.event_alpha_profile,
            ignore_provider_backoff=args.ignore_provider_backoff,
        )
        return
    if args.event_alpha_notify_preview:
        event_alpha_notify_preview(verbose=args.verbose, profile_name=args.event_alpha_profile)
        return
    if args.event_alpha_notify_go_no_go:
        event_alpha_notify_go_no_go(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
            include_legacy_artifacts=args.event_alpha_include_legacy_artifacts,
        )
        return
    if args.event_alpha_environment_doctor:
        event_alpha_environment_doctor_report(verbose=args.verbose, profile_name=args.event_alpha_profile)
        return
    if args.event_alpha_pause_notifications:
        event_alpha_pause_notifications(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            reason=args.reason,
        )
        return
    if args.event_alpha_resume_notifications:
        event_alpha_resume_notifications(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            confirm=args.confirm,
        )
        return
    if args.event_alpha_scheduler_status:
        event_alpha_scheduler_status_report(verbose=args.verbose, profile_name=args.event_alpha_profile)
        return
    if args.event_alpha_generate_launchd:
        event_alpha_generate_launchd(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            out=args.out,
        )
        return
    if args.event_alpha_notification_slo_report:
        event_alpha_notification_slo_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            include_diagnostics=args.event_opportunity_audit_include_diagnostics,
        )
        return
    if args.event_alpha_export_notification_pack:
        if not args.out:
            print("--event-alpha-export-notification-pack requires --out OUT.zip")
            return
        event_alpha_export_notification_pack(
            args.out,
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
        )
        return
    if args.event_alpha_notification_checklist:
        event_alpha_notification_checklist_report(verbose=args.verbose, profile_name=args.event_alpha_profile)
        return
    if args.event_alpha_send_readiness:
        event_alpha_send_readiness_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
            include_legacy_artifacts=args.event_alpha_include_legacy_artifacts,
        )
        return
    if args.event_alpha_telegram_final_check:
        event_alpha_telegram_final_check_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
            include_legacy_artifacts=args.event_alpha_include_legacy_artifacts,
        )
        return
    if args.event_alpha_send_test:
        event_alpha_send_test(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            ignore_notification_pause=args.ignore_notification_pause,
        )
        return
    if args.event_alpha_telegram_recipient_check:
        event_alpha_telegram_recipient_check_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
        )
        return
    if args.event_alpha_notification_runs_report:
        event_alpha_notification_runs_report(
            path=args.event_alpha_notification_runs_path,
            limit=args.event_alpha_run_limit,
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
        )
        return
    if args.event_alpha_notification_inbox:
        event_alpha_notification_inbox_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            include_diagnostics=args.event_opportunity_audit_include_diagnostics,
            burn_in_review=args.event_alpha_burn_in_review,
        )
        return
    if args.event_alpha_notification_deliveries_report:
        event_alpha_notification_deliveries_report(
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            verbose=args.verbose,
        )
        return
    if args.event_alpha_notification_retry_failed:
        event_alpha_notification_retry_failed(
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            confirm=args.confirm,
            verbose=args.verbose,
        )
        return
    if args.event_alpha_provider_health_report:
        event_alpha_provider_health_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
        )
        return
    if args.event_alpha_cryptopanic_preflight:
        event_alpha_cryptopanic_preflight(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
        )
        return
    if args.event_alpha_source_coverage_report:
        event_alpha_source_coverage_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
        )
        return
    if args.event_alpha_provider_health_reset:
        event_alpha_provider_health_reset(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            provider_key=args.provider_key,
            service=args.service,
            role=args.role,
            reset_all=args.all,
            confirm=args.confirm,
        )
        return
    if args.event_alpha_notify_fixture_smoke:
        event_alpha_notify_fixture_smoke(verbose=args.verbose, event_now=args.event_now)
        return
    if args.event_alpha_runs_report:
        event_alpha_runs_report(
            path=args.event_alpha_run_ledger_path,
            limit=args.event_alpha_run_limit,
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
        )
        return
    if args.event_impact_hypotheses_report:
        latest_hypothesis_run = args.latest_run or not (args.all_history or args.run_id or args.since)
        event_impact_hypotheses_report(
            path=args.event_impact_hypothesis_store_path,
            limit=args.event_alpha_run_limit,
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            latest_run=latest_hypothesis_run,
            run_id=args.run_id,
            since=args.since,
            include_legacy=args.include_legacy or args.all_history,
        )
        return
    if args.event_impact_hypotheses_inbox:
        event_impact_hypotheses_inbox(
            path=args.event_impact_hypothesis_store_path,
            limit=args.event_alpha_run_limit,
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
        )
        return
    if args.event_incidents_report:
        latest_incident_run = args.latest_run or not (args.all_history or args.run_id)
        event_incidents_report(
            path=args.event_incident_store_path,
            limit=args.event_alpha_run_limit,
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            latest_run=latest_incident_run,
            run_id=args.run_id,
            include_legacy=args.include_legacy or args.all_history,
            include_diagnostic=args.include_diagnostic_incidents,
            include_raw=args.include_raw_incidents,
            include_external_context=args.include_external_context_incidents,
        )
        return
    if args.event_impact_hypothesis_smoke:
        event_impact_hypothesis_smoke(verbose=args.verbose, event_now=args.event_now)
        return
    if args.event_alpha_status:
        event_alpha_status(profile_name=args.event_alpha_profile, verbose=args.verbose)
        return
    if args.event_alpha_preflight:
        event_alpha_preflight_report(
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            send_requested=args.event_alert_send,
            verbose=args.verbose,
        )
        return
    if args.event_alpha_feedback_readiness:
        event_alpha_feedback_readiness_report(
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            verbose=args.verbose,
        )
        return
    if args.event_alpha_profile_report:
        event_alpha_profile_report(args.event_alpha_profile_report, verbose=args.verbose)
        return
    if args.event_catalyst_search_report:
        event_catalyst_search_report(verbose=args.verbose, with_llm=args.with_llm, event_now=args.event_now)
        return
    if args.event_watchlist_refresh:
        event_watchlist_refresh(verbose=args.verbose, with_llm=args.with_llm, event_now=args.event_now)
        return
    if args.event_watchlist_report:
        event_watchlist_report(verbose=args.verbose)
        return
    if args.event_watchlist_monitor:
        event_watchlist_monitor_report(verbose=args.verbose, event_now=args.event_now)
        return
    if args.event_alpha_router_report:
        event_alpha_router_report(verbose=args.verbose, profile_name=args.event_alpha_profile)
        return
    if args.event_alpha_signal_quality_eval:
        event_alpha_signal_quality_eval(
            path=args.event_alpha_signal_quality_cases_path,
            verbose=args.verbose,
        )
        return
    if args.event_opportunity_audit:
        event_opportunity_audit_report(
            args.event_opportunity_audit,
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
        )
        return
    if args.event_alpha_quality_review:
        event_alpha_quality_review_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
        )
        return
    if args.event_alpha_quality_coverage_report:
        event_alpha_quality_coverage_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            include_legacy_artifacts=args.event_alpha_include_legacy_artifacts,
        )
        return
    if args.event_alpha_policy_simulate:
        event_alpha_policy_simulate_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
        )
        return
    if args.event_alpha_export_signal_quality_cases:
        event_alpha_export_signal_quality_cases(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            out_path=args.event_alpha_signal_quality_export_path,
        )
        return
    if args.event_alpha_missed_report:
        event_alpha_missed_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
        )
        return
    if args.event_alpha_near_miss_report:
        event_alpha_near_miss_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            event_now=args.event_now,
        )
        return
    if args.event_alpha_calibration_report:
        event_alpha_calibration_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
        )
        return
    if args.event_source_reliability_report:
        event_source_reliability_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
        )
        return
    if args.event_alpha_burn_in_scorecard:
        event_alpha_burn_in_scorecard(
            days=args.event_alpha_burn_in_days,
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
            include_legacy_artifacts=args.event_alpha_include_legacy_artifacts,
        )
        return
    if args.event_alpha_burn_in_checklist:
        event_alpha_burn_in_checklist(
            days=args.event_alpha_burn_in_days,
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
            include_legacy_artifacts=args.event_alpha_include_legacy_artifacts,
        )
        return
    if args.event_alpha_burn_in_readiness:
        event_alpha_burn_in_readiness_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
        )
        return
    if args.event_alpha_v1_readiness:
        event_alpha_v1_readiness_report(
            days=args.event_alpha_burn_in_days,
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
            include_legacy_artifacts=args.event_alpha_include_legacy_artifacts,
        )
        return
    if args.event_alpha_health_guard:
        event_alpha_health_guard_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
            include_legacy_artifacts=args.event_alpha_include_legacy_artifacts,
        )
        return
    if args.event_alpha_artifact_doctor:
        event_alpha_artifact_doctor_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
            include_legacy_artifacts=args.event_alpha_include_legacy_artifacts,
            strict=args.event_alpha_artifact_doctor_strict,
            strict_legacy=args.event_alpha_artifact_doctor_strict_legacy,
            delivery_strict_scope=args.event_alpha_artifact_doctor_delivery_scope,
        )
        return
    if args.event_alpha_tuning_worksheet:
        event_alpha_tuning_worksheet_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
        )
        return
    if args.event_alpha_export_burn_in_pack:
        event_alpha_export_burn_in_pack(
            args.event_alpha_export_burn_in_pack,
            days=args.event_alpha_burn_in_days,
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
            include_legacy_artifacts=args.event_alpha_include_legacy_artifacts,
        )
        return
    if args.event_alpha_calibration_export_priors is not None:
        event_alpha_calibration_export_priors(
            args.event_alpha_calibration_export_priors or None,
            verbose=args.verbose,
        )
        return
    if args.event_alpha_priors_shadow_report:
        event_alpha_priors_shadow_report(verbose=args.verbose)
        return
    if args.event_alpha_export_eval_cases_from_feedback is not None:
        event_alpha_export_eval_cases_from_feedback(
            args.event_alpha_export_eval_cases_from_feedback or None,
            verbose=args.verbose,
        )
        return
    if args.event_alpha_export_eval_cases_from_missed is not None:
        event_alpha_export_eval_cases_from_missed(
            args.event_alpha_export_eval_cases_from_missed or None,
            verbose=args.verbose,
        )
        return
    if args.event_alpha_explain_last_run:
        event_alpha_explain_last_run(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
            include_legacy_artifacts=args.event_alpha_include_legacy_artifacts,
        )
        return
    if args.event_alpha_daily_brief:
        event_alpha_daily_brief_report(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or config.EVENT_ALPHA_ARTIFACT_NAMESPACE or None,
            include_test_artifacts=args.event_alpha_include_test_artifacts,
            include_legacy_artifacts=args.event_alpha_include_legacy_artifacts,
        )
        return
    if args.event_alpha_replay:
        event_alpha_replay_report(
            priors=args.event_alpha_replay_priors,
            llm_advisory=args.event_alpha_replay_llm_advisory,
            raw_events_path=args.event_alpha_replay_raw_events,
            market_rows_path=args.event_alpha_replay_market_rows,
            compare=args.event_alpha_replay_compare,
            replay_profile=args.event_alpha_replay_profile,
            replay_profile_alt=args.event_alpha_replay_profile_alt,
            verbose=args.verbose,
        )
        return
    if args.event_alpha_prune_artifacts:
        event_alpha_prune_artifacts(confirm=args.confirm, verbose=args.verbose)
        return
    if args.event_research_card is not None:
        event_research_card_report(args.event_research_card, verbose=args.verbose)
        return
    if args.event_research_cards_write:
        event_research_cards_write(
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
        )
        return
    if args.event_alpha_alerts_report:
        event_alpha_alerts_report(
            path=args.event_alpha_alert_store_path,
            feedback_path=args.event_feedback_path,
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
        )
        return
    if args.event_alpha_fill_outcomes:
        event_alpha_fill_outcomes(
            args.event_alpha_fill_outcomes[0],
            args.event_alpha_fill_outcomes[1],
            path=args.event_alpha_alert_store_path,
            verbose=args.verbose,
        )
        return
    if args.event_feedback_mark:
        event_feedback_mark(
            args.event_feedback_mark,
            args.event_feedback_label,
            notes=args.event_feedback_notes,
            marked_by=args.event_feedback_by,
            path=args.event_feedback_path,
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
        )
        return
    feedback_shortcuts = (
        (args.event_feedback_useful, "useful"),
        (args.event_feedback_junk, "junk"),
        (args.event_feedback_watch, "watch"),
        (args.event_feedback_traded, "traded_elsewhere"),
        (args.event_feedback_ignore, "ignored"),
        (args.event_feedback_missed, "missed"),
    )
    for target, label in feedback_shortcuts:
        if target is not None:
            event_feedback_shortcut(
                target,
                label,
                notes=args.event_feedback_notes,
                verbose=args.verbose,
                profile_name=args.event_alpha_profile,
                artifact_namespace=args.event_alpha_artifact_namespace or None,
            )
            return
    if args.event_feedback_report:
        event_feedback_report(
            path=args.event_feedback_path,
            verbose=args.verbose,
            profile_name=args.event_alpha_profile,
            artifact_namespace=args.event_alpha_artifact_namespace or None,
        )
        return
    if args.event_llm_shadow_report:
        event_llm_shadow_report(verbose=args.verbose, event_now=args.event_now)
        return
    if args.event_llm_extract_report:
        event_llm_extract_report(verbose=args.verbose, event_now=args.event_now)
        return
    if args.event_discovery_refresh:
        event_discovery_refresh(verbose=args.verbose, event_now=args.event_now)
        return
    if args.event_discovery_status:
        event_discovery_status(json_output=args.json)
        return
    if args.event_discovery_runs:
        event_discovery_runs(limit=args.event_discovery_run_limit, json_output=args.json)
        return
    if args.event_discovery_binance_listen:
        event_discovery_binance_listen(verbose=args.verbose, event_now=args.event_now)
        return
    if args.event_fade_auto_report:
        event_fade_auto_report(verbose=args.verbose, event_now=args.event_now)
        return
    if args.event_fade_export_sample:
        event_fade_export_sample(args.event_fade_export_sample, verbose=args.verbose, event_now=args.event_now)
        return
    if args.event_fade_export_cache_sample:
        event_fade_export_cache_sample(
            args.event_fade_export_cache_sample,
            verbose=args.verbose,
            event_now=args.event_now,
        )
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
    if args.event_fade_check_review_template:
        sample_path, template_path = args.event_fade_check_review_template
        event_fade_check_review_template(
            sample_path,
            template_path,
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
            event_now=args.event_now,
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
            event_now=args.event_now,
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
