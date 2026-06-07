"""Channel-specific message formatting (pure functions).

Telegram renders in a proportional font, so the console's aligned columns turn
to mush there. These builders produce rich Telegram HTML (bold, emoji, clean
per-coin structure) and a plain-text fallback for Discord/email.
"""

from __future__ import annotations

import html
import math

from .signal_registry import setup_has_edge

DIGEST_GROUP_CAP = 12  # max rows shown per group before "+N more"

_SEV_EMOJI = {"EXTREME": "🔥", "ALERT": "❗", "WATCH": "👀", "APPROACHING": "⏳"}
_REGIME_EMOJI = {"UPTREND": "↗️", "DOWNTREND": "↘️", "RANGE": "↔️"}
_STATE_LABEL = {
    "OB": "Overbought",
    "OS": "Oversold",
    "PRE_OB": "Approaching overbought",
    "PRE_OS": "Approaching oversold",
}


def _present(v: object) -> bool:
    return v is not None and not (isinstance(v, float) and math.isnan(v))


def _esc(s: object) -> str:
    return html.escape(str(s), quote=False)


def _esc_attr(s: object) -> str:
    return html.escape(str(s), quote=True)


def _dir_emoji(flag: str) -> str:
    return "🔴" if flag in ("OB", "PRE_OB") else "🟢"


def _rsi_segment(s: dict) -> str:
    parts = [f"RSI <b>{s['rsi_daily']:.0f}</b>"]
    if _present(s.get("rsi_4h")):
        parts.append(f"4H {s['rsi_4h']:.0f}")
    if _present(s.get("rsi_weekly")):
        parts.append(f"1W {s['rsi_weekly']:.0f}")
    return "  ·  ".join(parts)


def _chart_link(s: dict) -> str:
    """Tap-to-open chart. Links the symbol to TradingView (USDT pair)."""
    sym = str(s.get("symbol", "")).upper()
    if not sym:
        return ""
    url = f"https://www.tradingview.com/chart/?symbol={_esc_attr(sym)}USDT"
    return f'<a href="{url}">📈 chart</a>'


def _context_segment(s: dict) -> str:
    bits = []
    z = s.get("rsi_z")
    if _present(z):
        bits.append(f"z {z:+.1f}")
    d = s.get("rsi_delta")
    if _present(d) and abs(d) >= 1:
        bits.append(f"Δ3d {d:+.0f}")
    return "  ·  ".join(bits)


def _confirm_segment(s: dict) -> str:
    bits = []
    vr = s.get("volume_ratio")
    if _present(vr) and vr >= 1.5:
        bits.append(f"🔊 Vol {vr:.1f}×")
    if s.get("divergence"):
        bits.append(f"⚠️ {'bullish' if s['divergence'] == 'bullish' else 'bearish'} divergence")
    bc = s.get("btc_corr")
    if _present(bc) and bc > 0.7:
        bits.append("🪙 BTC-beta")
    return "  ·  ".join(bits)


_SPARK_CHARS = "▁▂▃▄▅▆▇█"


def sparkline(prices: list | None, width: int = 16) -> str:
    """Unicode sparkline from a price list. Downsamples to `width` buckets."""
    if not prices or len(prices) < 2:
        return ""
    vals = [p for p in prices if isinstance(p, (int, float))]
    if len(vals) < 2:
        return ""
    # downsample to at most `width` points by striding
    if len(vals) > width:
        step = len(vals) / width
        vals = [vals[min(int(i * step), len(vals) - 1)] for i in range(width)]
    lo, hi = min(vals), max(vals)
    rng = hi - lo
    if rng <= 0:
        return _SPARK_CHARS[0] * len(vals)
    out = []
    for v in vals:
        idx = int((v - lo) / rng * (len(_SPARK_CHARS) - 1))
        out.append(_SPARK_CHARS[idx])
    return "".join(out)


def _fmt_price(p: float) -> str:
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return ""
    if p >= 1000:
        return f"${p:,.0f}"
    if p >= 1:
        return f"${p:,.2f}"
    if p >= 0.01:
        return f"${p:.4f}"
    return f"${p:.8f}".rstrip("0")


def _signed(pct: float) -> str:
    return f"{pct:+.1f}%"


def _price_segment(s: dict) -> str:
    """Price, 24h %, 7d % — the 'is it actually moving' line."""
    bits = []
    price = s.get("price")
    if _present(price):
        bits.append(_fmt_price(price))
    p24 = s.get("pct_24h")
    if _present(p24):
        arrow = "🟢" if p24 >= 0 else "🔴"
        bits.append(f"{arrow} {_signed(p24)} 24h")
    p7 = s.get("pct_7d")
    if _present(p7):
        bits.append(f"{_signed(p7)} 7d")
    return "  ·  ".join(bits)


def _ath_segment(s: dict) -> str:
    ath_pct = s.get("ath_pct")
    if not _present(ath_pct):
        return ""
    # ath_change_percentage is negative when below ATH
    return f"📉 {abs(ath_pct):.0f}% below ATH" if ath_pct < -0.5 else "🏔 at/near ATH"


def _regime_segment(s: dict) -> str:
    regime = s.get("regime") or ""
    if not regime or regime == "UNKNOWN":
        return ""
    note = s.get("regime_note") or ""
    label = f"{_REGIME_EMOJI.get(regime, '')} {regime.title()}".strip()
    return f"{label} → <i>{_esc(note)}</i>" if note else label


_SETUP_EMOJI = {
    "trend_continuation": "📈",
    "dip_buy": "🟢",
    "mean_reversion": "↩️",
    "breakdown_risk": "⚠️",
}


def _setup_segment(s: dict) -> str:
    """Headline the trade hypothesis: which setup this is, and which way it
    expects price to go. This is the line that stops someone buying a dip that's
    really a downtrend breakdown."""
    setup = s.get("setup_type")
    if not setup:
        return ""
    label = f"{_SETUP_EMOJI.get(setup, '•')} <b>{_esc(setup.replace('_', ' ').title())}</b>"
    if not setup_has_edge(setup):
        # no historical edge in any market regime -> don't assert a direction
        return label + " — <i>context only, no historical edge</i>"
    exp = s.get("expected_dir")
    if exp == "up":
        label += " — <i>expecting upside ↑</i>"
    elif exp == "down":
        label += " — <i>expecting downside ↓</i>"
    return label


_MARKET_LABEL = {"UPTREND": "Bull", "DOWNTREND": "Bear", "RANGE": "Chop"}


def _market_segment(s: dict) -> str:
    """The BTC market backdrop and whether it favors this setup (per the
    backtested setup × market-regime edge map)."""
    mr = s.get("market_regime")
    if not mr or mr == "UNKNOWN":
        return ""
    label = _MARKET_LABEL.get(mr, str(mr).title())
    aligned = s.get("market_aligned")
    if aligned == "favorable":
        return f"🧭 {label} market · ✅ <i>regime favors this setup</i>"
    if aligned == "adverse":
        return f"🧭 {label} market · ⚠️ <i>little edge in this regime</i>"
    return f"🧭 {label} market"


# --------------------------------------------------------------------------- #
# Telegram (HTML)
# --------------------------------------------------------------------------- #

def _tg_card(s: dict) -> str:
    """Rich multi-line card for an INSTANT alert."""
    head = f"{_dir_emoji(s['flag'])} <b>{_esc(s['symbol'])}</b> · {_STATE_LABEL.get(s['flag'], '')}"
    sev = _SEV_EMOJI.get(s.get("severity", ""), "")
    if sev:
        head += f" {sev}"

    lines = [head]

    setup = _setup_segment(s)
    if setup:
        lines.append(setup)

    mkt = _market_segment(s)
    if mkt:
        lines.append(mkt)

    price = _price_segment(s)
    if price:
        lines.append(price)

    spark = sparkline(s.get("sparkline"))
    if spark:
        lines.append(f"<code>{spark}</code> 7d")

    lines.append(_rsi_segment(s))

    ctx = _context_segment(s)
    if ctx:
        lines.append(ctx)
    reg = _regime_segment(s)
    if reg:
        lines.append(reg)

    track = s.get("track_record")  # filled by hit-rate enrichment (Part B)
    if _present(track) and track:   # _present guards None *and* NaN (from a DataFrame)
        lines.append(str(track))

    conf = _confirm_segment(s)
    if conf:
        lines.append(conf)

    ath = _ath_segment(s)
    conv = int(s["conviction"])
    tail = f"⭐ Conviction <b>{conv}</b>/100"
    base = s.get("conviction_base")
    if _present(base) and int(base) != conv:
        # show that history nudged the score (self-tuning)
        base_i = int(base)
        tail += f" <i>({base_i}{'↑' if conv > base_i else '↓'} by history)</i>"
    if ath:
        tail += f"  ·  {ath}"
    lines.append(tail)

    link = _chart_link(s)
    if link:
        lines.append(link)
    return "\n".join(lines)


def _tg_digest_line(s: dict) -> str:
    """Compact one-liner for the digest watch-list."""
    sev = _SEV_EMOJI.get(s.get("severity", ""), "•")
    chg = ""
    p24 = s.get("pct_24h")
    if _present(p24):
        chg = f" {'🟢' if p24 >= 0 else '🔴'}{p24:+.0f}%"
    tail = ""
    regime = s.get("regime") or ""
    if regime and regime != "UNKNOWN":
        note = s.get("regime_note") or ""
        tail = f"{_REGIME_EMOJI.get(regime, '')} {note}".strip()
    spark = " 🔊" if _present(s.get("volume_ratio")) and s["volume_ratio"] >= 1.5 else ""
    mid = f" · {tail}" if tail else ""
    return (
        f"{sev} <b>{_esc(s['symbol'])}</b> {s['rsi_daily']:.0f}{chg}"
        f"{mid} · c{int(s['conviction'])}{spark}"
    )


def telegram_html(kind: str, signals: list[dict], ts: str, macro_line: str = "") -> str:
    if kind == "instant":
        out = ["⚡ <b>RSI HEADS UP</b>", f"<i>{_esc(ts)}</i>"]
        if macro_line:
            out.append(macro_line)
        for s in signals:
            out.append("")
            out.append(_tg_card(s))
        return "\n".join(out)

    # digest
    out = ["📋 <b>RSI Watch-list</b>", f"<i>{_esc(ts)}</i>"]
    if macro_line:
        out.append(macro_line)
    groups = (
        ("🔴 <b>Overbought</b>", ("OB",)),
        ("🟢 <b>Oversold</b>", ("OS",)),
        ("🟡 <b>Approaching</b>", ("PRE_OB", "PRE_OS")),
    )
    for header, flags in groups:
        items = [s for s in signals if s["flag"] in flags]
        if not items:
            continue
        out.append("")
        out.append(f"{header} · {len(items)}")
        for s in items[:DIGEST_GROUP_CAP]:
            out.append(_tg_digest_line(s))
        if len(items) > DIGEST_GROUP_CAP:
            out.append(f"   …+{len(items) - DIGEST_GROUP_CAP} more")
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# Plain text (Discord / email fallback)
# --------------------------------------------------------------------------- #

def plain_text(kind: str, signals: list[dict], ts: str, macro_line: str = "") -> str:
    title = "RSI HEADS UP" if kind == "instant" else "RSI Watch-list"
    head = f"{title}  {ts}  ({len(signals)})"
    # strip HTML/emoji-light: plain channels just get the text
    macro = ("\n" + _strip_tags(macro_line)) if macro_line else ""
    body = "\n".join(s.get("line", s["symbol"]) for s in signals)
    return f"{head}{macro}\n{body}"


def _strip_tags(s: str) -> str:
    import re
    return re.sub(r"<[^>]+>", "", s).replace("&amp;", "&")
