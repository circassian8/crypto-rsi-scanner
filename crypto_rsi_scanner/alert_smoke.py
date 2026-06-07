"""Offline smoke test for alert rendering.

This exercises the notification render paths without network calls. It is meant
to catch the class of regressions that only show up after the scanner assembles a
real alert payload: bad HTML, NaN leaks, oversized messages, missing digest caps,
and formatting crashes in rarely used setup/market combinations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import formatting
from .notifications import _truncate


TELEGRAM_LIMIT = 4096
DISCORD_LIMIT = 2000
_ALLOWED_TAGS = {"a", "b", "code", "i"}
_TAG_RE = re.compile(r"</?([a-zA-Z][a-zA-Z0-9]*)(?:\s+[^>]*)?>")
_BAD_SUBSTRINGS = ("<script", " onclick", " onerror", "javascript:", "nan")
_TS = "2026-06-07 12:00 UTC"
_MACRO = "🌍 F&amp;G 22 (Fear) · BTC ↘️ Downtrend · breadth 9🔴/3🟢"


@dataclass(frozen=True)
class SmokeResult:
    name: str
    chars: int


def _sample_signal(**overrides) -> dict:
    base = {
        "symbol": "BTC",
        "flag": "OB",
        "severity": "WATCH",
        "conviction": 55,
        "tier": "DIGEST",
        "is_new": True,
        "rsi_daily": 72.7,
        "rsi_4h": 74.2,
        "rsi_weekly": 61.4,
        "rsi_z": 2.1,
        "rsi_delta": 8.0,
        "volume_ratio": 1.8,
        "btc_corr": 0.81,
        "divergence": None,
        "regime": "UPTREND",
        "regime_note": "continuation",
        "setup_type": "trend_continuation",
        "expected_dir": "up",
        "market_regime": "UPTREND",
        "market_aligned": "favorable",
        "price": 72000.0,
        "pct_24h": 3.4,
        "pct_7d": 8.9,
        "ath_pct": -6.2,
        "sparkline": [70, 72, 71, 73, 76, 74, 78, 80],
        "track_record": None,
        "conviction_base": None,
        "line": "BTC OB c55",
    }
    base.update(overrides)
    return base


def instant_fixture() -> list[dict]:
    return [
        _sample_signal(
            symbol='A&B<X>"',
            flag="OB",
            severity="EXTREME",
            conviction=91,
            conviction_base=78,
            track_record="7d track: 6/8 favorable, med +3.1%",
            divergence="bearish",
            line='A&B<X>" OB c91',
        ),
        _sample_signal(
            symbol="SOL",
            flag="OS",
            severity="ALERT",
            conviction=72,
            setup_type="dip_buy",
            expected_dir="up",
            regime="UPTREND",
            regime_note="dip?",
            market_regime="UPTREND",
            market_aligned="favorable",
            rsi_daily=18.4,
            rsi_4h=34.0,
            rsi_weekly=39.8,
            rsi_z=-2.8,
            rsi_delta=-12.0,
            volume_ratio=2.4,
            btc_corr=0.72,
            divergence="bullish",
            price=144.25,
            pct_24h=-7.2,
            pct_7d=-12.5,
            ath_pct=-41.0,
            sparkline=[160, 158, 151, 149, 144, 138, 142, 144],
            line="SOL OS c72",
        ),
        _sample_signal(
            symbol="DOGE",
            flag="OS",
            severity="WATCH",
            conviction=31,
            setup_type="breakdown_risk",
            expected_dir="down",
            regime="DOWNTREND",
            regime_note="continuation",
            market_regime="DOWNTREND",
            market_aligned="adverse",
            rsi_daily=28.9,
            rsi_4h=float("nan"),
            rsi_weekly=None,
            rsi_z=-1.6,
            rsi_delta=-4.0,
            volume_ratio=1.1,
            btc_corr=0.42,
            divergence=None,
            price=0.1421,
            pct_24h=-2.0,
            pct_7d=-9.0,
            ath_pct=-78.0,
            track_record=float("nan"),
            conviction_base=float("nan"),
            line="DOGE OS c31",
        ),
    ]


def digest_fixture() -> list[dict]:
    out = []
    for i in range(formatting.DIGEST_GROUP_CAP + 2):
        out.append(_sample_signal(
            symbol=f"OB{i:02d}",
            flag="OB",
            severity="WATCH",
            conviction=45 + i,
            rsi_daily=70.0 + i / 10,
            line=f"OB{i:02d} OB c{45 + i}",
        ))
    for i in range(4):
        out.append(_sample_signal(
            symbol=f"OS{i:02d}",
            flag="OS",
            severity="ALERT",
            conviction=64 - i,
            setup_type="dip_buy",
            expected_dir="up",
            regime="UPTREND",
            regime_note="dip?",
            rsi_daily=22.0 - i,
            pct_24h=-1.5 * i,
            line=f"OS{i:02d} OS c{64 - i}",
        ))
    out.extend([
        _sample_signal(
            symbol="PREOB",
            flag="PRE_OB",
            severity="APPROACHING",
            conviction=33,
            rsi_daily=68.5,
            line="PREOB approaching c33",
        ),
        _sample_signal(
            symbol="PREOS",
            flag="PRE_OS",
            severity="APPROACHING",
            conviction=30,
            setup_type="mean_reversion",
            expected_dir="up",
            regime="RANGE",
            regime_note="range-bottom",
            rsi_daily=32.0,
            line="PREOS approaching c30",
        ),
    ])
    return out


def render_messages() -> dict[str, str]:
    instant = instant_fixture()
    digest = digest_fixture()
    return {
        "telegram_instant": formatting.telegram_html("instant", instant, _TS, macro_line=_MACRO),
        "telegram_digest": formatting.telegram_html("digest", digest, _TS, macro_line=_MACRO),
        "plain_instant": formatting.plain_text("instant", instant, _TS, macro_line=_MACRO),
        "plain_digest": formatting.plain_text("digest", digest, _TS, macro_line=_MACRO),
    }


def _assert_telegram_html(name: str, text: str) -> None:
    if len(text) > TELEGRAM_LIMIT:
        raise AssertionError(f"{name} is {len(text)} chars, exceeds Telegram {TELEGRAM_LIMIT}")
    lowered = text.lower()
    for bad in _BAD_SUBSTRINGS:
        if bad in lowered:
            raise AssertionError(f"{name} contains unsafe/leaked substring: {bad}")
    if name == "telegram_instant" and 'symbol=A&amp;B&lt;X&gt;&quot;USDT' not in text:
        raise AssertionError(f"{name} did not escape a quoted chart-link symbol")

    stack: list[str] = []
    for match in _TAG_RE.finditer(text):
        raw = match.group(0)
        tag = match.group(1).lower()
        if tag not in _ALLOWED_TAGS:
            raise AssertionError(f"{name} contains unsupported HTML tag: {raw}")
        if raw.startswith("</"):
            if not stack or stack[-1] != tag:
                raise AssertionError(f"{name} has unbalanced HTML near: {raw}")
            stack.pop()
        else:
            if tag == "a" and 'href="' not in raw:
                raise AssertionError(f"{name} has <a> without href")
            stack.append(tag)
    if stack:
        raise AssertionError(f"{name} has unclosed HTML tags: {stack}")


def _assert_plain(name: str, text: str) -> None:
    long_candidate = text if len(text) > DISCORD_LIMIT else text + "\n" + ("x" * DISCORD_LIMIT)
    truncated = _truncate(long_candidate, DISCORD_LIMIT)
    if len(truncated) > DISCORD_LIMIT or "\n" not in truncated:
        raise AssertionError(f"{name} does not truncate safely for Discord")
    if "<b>" in text or "</i>" in text:
        raise AssertionError(f"{name} leaked HTML tags into plain fallback")


def run_smoke() -> list[SmokeResult]:
    messages = render_messages()
    results: list[SmokeResult] = []
    for name, text in messages.items():
        if not text.strip():
            raise AssertionError(f"{name} rendered empty output")
        if "telegram" in name:
            _assert_telegram_html(name, text)
        else:
            _assert_plain(name, text)
        if "nan" in text.lower():
            raise AssertionError(f"{name} leaked NaN")
        results.append(SmokeResult(name=name, chars=len(text)))

    digest = messages["telegram_digest"]
    if f"…+2 more" not in digest:
        raise AssertionError("telegram_digest did not enforce the per-group cap")
    return results


def main() -> None:
    for result in run_smoke():
        print(f"PASS {result.name} ({result.chars} chars)")
    print("Alert render smoke passed.")


if __name__ == "__main__":
    main()
