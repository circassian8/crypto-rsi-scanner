# Volume-rank PIT backtest — first full-cycle survivorship-reduced run

**Date:** 2026-06-10 · **Author:** Claude
**Command:** `python -m crypto_rsi_scanner.backtest --pit-volume --top-n 100 --days 1825 --state-slices`
**Sample:** 368 usable coins (of 414 currently-trading Binance USDT bases), 21,334
graded observations. Market-regime coverage at 7d: **BULL 60.9k / BEAR 46.7k /
CHOP 23.8k** base-days — the first run that is simultaneously full-cycle (5y,
through the 2022 bear and 2023–25 bull) *and* point-in-time.

## Why this run exists

The mcap-based `--pit` path is capped at 365d by the CoinGecko demo key — a
bear-only window that could not validate bull/chop rules. `--pit-volume` defines
per-date membership as **top-N by trailing 30d dollar (quote) volume** over the
whole Binance USDT pool, from free Binance klines. Membership is fully
point-in-time (a coin needs 30 prior days to enter; decliners drop out as their
volume rank decays), so coins contribute only while they were actually top-100
tradeable.

## Headline results (7d horizon, edge = confirm% − same-regime base%)

### The gating map holds — directions confirmed, magnitudes attenuated

| setup × market | n | edge | prior runs | verdict |
|---|---|---|---|---|
| mean_reversion · CHOP | 800 | **+10** | +10 (biased 5y), +23 (365d PIT) | **confirmed 3rd time — the cornerstone edge** |
| mean_reversion · BULL | 1138 | −3 | −5 | confirmed negative → keep gated out of bull |
| mean_reversion · BEAR | 1043 | 0 | +1 | flat — neutral is right |
| dip_buy · BULL | 251 | +6 | +9 | holds, attenuated |
| trend_continuation · BULL | 517 | +4 (+5 @14d) | +8 | holds, thin |
| breakdown_risk · any | 307–771 | −3 BEAR / +3 BULL / −15 CHOP | ≤0 everywhere | **no reliable edge → context-only stays right** |

Attenuation vs the survivorship-biased run is expected and healthy — biased
samples flatter. The *direction* of every gating decision survives.

### Conviction is monotonic with edge for the first time

| bucket | n | edge |
|---|---|---|
| low (<40) | 2700 | −3 |
| med (40–64) | 2320 | +3 |
| high (65+) | 307 | **+9** |

Every earlier run showed the conviction score failing to rank (and high-bucket
n≤6). Under the registry **edge-prior conviction** (Codex's rework) with a real
sample, higher conviction now means higher edge. First genuine validation of the
score.

### State-slice replications (same-regime + same-state base)

- **breakdown_risk in high/crisis volatility: −14 / −19 edge** (n=130/89) — the
  "violent decline bounces, don't expect continuation" pattern replicates under
  PIT. Reinforces context-only.
- **mean_reversion by breadth: washout +14 (n=45), breadth_collapse +7 (n=777),
  risk_on_broad −8 (n=565)** — buy-the-bounce works when breadth is washed out,
  is an anti-signal when everything already ran. Coherent and now PIT-backed;
  candidate for future gating refinement.
- trend_continuation mid-RS +11 (n=182) and dip_buy high-RS +10 (n=112) —
  suggestive, thinner; keep as candidates.

Per the standing decision, none of these are promoted to live conviction/routing
from a single run; they are now *PIT-confirmed candidates* rather than
biased-sample candidates.

## Caveats

- **Residual survivorship:** exchangeInfo lists only currently-trading pairs, so
  coins Binance fully delisted are absent (less severe than mcap-top-N-today —
  most blowups like LUNC/FTT still trade — but not zero).
- Single venue; USDT pairs only (a coin is invisible before its Binance listing).
- Volume-rank ≠ the live scanner's mcap-rank universe (it's a *tradeable-universe*
  proxy; arguably better, but different).
- No fees/slippage in the headline tables (`--costs` exists for that).

## Follow-ups

1. Registry prior export from this run: `research/registry_priors_volpit_2026-06-10.json`
   (reviewable artifact; **not** loaded live — opt-in via `RSI_REGISTRY_PRIORS`
   only after human review).
2. Cross-check the breadth-state mean_reversion candidates against the live paper
   cohorts once enough trades mature (~2026-06-15).
3. Optional: walk-forward folds (`--walk-forward`) on this universe to check the
   CHOP edge is not concentrated in one episode.
