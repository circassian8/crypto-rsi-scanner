"""Market-wide context for the digest header.

A coin oversold while the whole market bleeds is a different signal than one
oversold in isolation. This adds cheap macro context — Fear & Greed, BTC trend,
breadth, dominance — so every alert is read against the backdrop. All fetches
fail soft: a missing piece is omitted, never fatal.
"""

from __future__ import annotations

import logging

import requests

from . import config

log = logging.getLogger(__name__)

_FNG_URL = "https://api.alternative.me/fng/?limit=1"
_CG_GLOBAL = "/global"


def fetch_fear_greed() -> dict | None:
    """Crypto Fear & Greed index (0-100). Free, no key."""
    try:
        r = requests.get(_FNG_URL, timeout=15)
        r.raise_for_status()
        d = r.json()["data"][0]
        return {"value": int(d["value"]), "label": d["value_classification"]}
    except Exception as e:
        log.warning("Fear & Greed fetch failed: %s", e)
        return None


def fetch_global() -> dict | None:
    """BTC dominance + total market-cap 24h change from CoinGecko /global."""
    key = config.COINGECKO_API_KEY
    if key and config.COINGECKO_KEY_TYPE == "pro":
        base, headers = "https://pro-api.coingecko.com/api/v3", {"x-cg-pro-api-key": key}
    elif key:
        base, headers = "https://api.coingecko.com/api/v3", {"x-cg-demo-api-key": key}
    else:
        base, headers = "https://api.coingecko.com/api/v3", {}
    try:
        r = requests.get(f"{base}{_CG_GLOBAL}", headers=headers, timeout=20)
        r.raise_for_status()
        d = r.json()["data"]
        return {
            "btc_dominance": d.get("market_cap_percentage", {}).get("btc"),
            "mcap_change_24h": d.get("market_cap_change_percentage_24h_usd"),
        }
    except Exception as e:
        log.warning("CoinGecko /global fetch failed: %s", e)
        return None


def build_macro(df, n_ob: int, n_os: int, prev_counts: dict | None) -> dict:
    """Assemble the macro snapshot. df is the scan result (for BTC regime)."""
    macro: dict = {"n_ob": n_ob, "n_os": n_os}

    macro["fng"] = fetch_fear_greed()
    macro["glob"] = fetch_global()

    # BTC trend regime, pulled from the scan we already ran (no extra call)
    try:
        if df is not None and not df.empty:
            btc = df[df["symbol"] == "BTC"]
            if not btc.empty:
                macro["btc_regime"] = btc.iloc[0].get("regime")
    except Exception:
        pass

    # breadth direction vs the previous scan
    if prev_counts:
        macro["d_ob"] = n_ob - prev_counts.get("ob", n_ob)
        macro["d_os"] = n_os - prev_counts.get("os", n_os)

    return macro


def _arrow(delta: int | None) -> str:
    if delta is None or delta == 0:
        return ""
    return " ↑" if delta > 0 else " ↓"


def macro_header(macro: dict | None) -> str:
    """One compact HTML line summarizing the market backdrop. '' if nothing."""
    if not macro:
        return ""
    bits = []

    fng = macro.get("fng")
    if fng:
        bits.append(f"😱 F&amp;G {fng['value']} ({fng['label']})")

    btc_regime = macro.get("btc_regime")
    if btc_regime and btc_regime != "UNKNOWN":
        emoji = {"UPTREND": "↗️", "DOWNTREND": "↘️", "RANGE": "↔️"}.get(btc_regime, "")
        bits.append(f"₿ {emoji}{btc_regime.title()}")

    glob = macro.get("glob")
    if glob:
        mc = glob.get("mcap_change_24h")
        if mc is not None:
            bits.append(f"🌐 mcap {mc:+.1f}% 24h")
        dom = glob.get("btc_dominance")
        if dom is not None:
            bits.append(f"BTC.D {dom:.0f}%")

    n_ob, n_os = macro.get("n_ob", 0), macro.get("n_os", 0)
    bits.append(f"breadth {n_ob}🔴{_arrow(macro.get('d_ob'))} / {n_os}🟢{_arrow(macro.get('d_os'))}")

    if not bits:
        return ""
    return "🌍 " + "  ·  ".join(bits)
