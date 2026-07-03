"""Rsi Scan commands from the legacy scanner service."""

from __future__ import annotations

from .runtime import *

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

def status() -> None:
    """Print operational scan/listener health and exit."""
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    storage = Storage(config.DB_PATH)
    try:
        from ...status_report import format_status
        print(format_status(storage))
    finally:
        storage.close()

def backup_db() -> None:
    """Create and verify a safe SQLite backup, then prune old backups."""
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    from ...backups import backup_database, format_backup_result

    result = backup_database(config.DB_PATH, config.BACKUP_DIR, keep=config.BACKUP_KEEP)
    print(format_backup_result(result))

def verify_restore(backup_path: str | None = None) -> None:
    """Restore-check a backup, defaulting to the newest retained DB backup."""
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    from ...backups import format_restore_result, latest_backup_status, verify_restore as _verify_restore

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
    from ...ops import format_log_rotation, rotate_logs as _rotate_logs

    results = _rotate_logs(
        config.LOG_FILES,
        max_bytes=config.LOG_ROTATE_MAX_BYTES,
        keep=config.LOG_ROTATE_KEEP,
    )
    print(format_log_rotation(results))

def maintenance() -> None:
    """Run the daily local maintenance bundle: backup, restore drill, log rotation."""
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    from ...backups import (
        backup_database,
        format_backup_result,
        format_restore_result,
        verify_restore as _verify_restore,
    )
    from ...ops import format_log_rotation, rotate_logs as _rotate_logs

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
    from ...ops import format_launchd_status, launchd_status as _launchd_status

    statuses = _launchd_status((
        config.LAUNCHD_SCAN_LABEL,
        config.LAUNCHD_BOT_LABEL,
        config.MAINTENANCE_LABEL,
    ))
    print(format_launchd_status(statuses))

def restart_listener() -> None:
    """Restart the always-on Telegram bot listener launchd agent."""
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    from ...ops import format_launchd_command, restart_launchd_service

    result = restart_launchd_service(config.LAUNCHD_BOT_LABEL)
    print(format_launchd_command(result))

def install_maintenance_agent() -> None:
    """Install/load the daily launchd maintenance agent for this checkout."""
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    from ...ops import format_maintenance_agent_install, install_maintenance_agent as _install

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

__all__ = (
    '_parse_chart',
    '_severity',
    'classify_tier',
    '_finite_float',
    '_rounded',
    '_json_safe',
    '_build_state_context',
    '_analyze_coin',
    'scan',
    '_is_present',
    '_format_signal',
    'build_message',
    'fetch_universe_audit',
    '_fetch_extra_daily_closes',
    '_outcome_since',
    '_ensure_pending_closes',
    '_write_latest_csv',
    'run',
    '_apply_live_edge_adjustments',
    '_route_notifications',
    'report',
    'score',
    'refresh_paper',
    'event_fade_report',
    'status',
    'backup_db',
    'verify_restore',
    'rotate_logs',
    'maintenance',
    'launchd_status',
    'restart_listener',
    'install_maintenance_agent',
    'universe_audit',
    'refresh_universe_audit',
)
