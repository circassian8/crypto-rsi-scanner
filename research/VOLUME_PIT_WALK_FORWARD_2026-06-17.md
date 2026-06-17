# Volume-PIT walk-forward check

**Date:** 2026-06-17 · **Author:** Codex

## Why this run exists

`research/VOLUME_PIT_BACKTEST_2026-06-10.md` identified
`mean_reversion` in BTC `CHOP` as the cornerstone regime-conditional edge, but
left one follow-up open: check that the CHOP edge was not concentrated in a
single episode.

This pass adds and uses a setup-by-BTC-market walk-forward table in
`backtest --walk-forward`. The table keeps the existing chronological signal
folds, but reports setup x BTC-market rows with edge against the same
full-period coin-regime x BTC-market base used by `format_market`.

## Command

```bash
.venv/bin/python -m crypto_rsi_scanner.backtest --pit-volume --top-n 100 --days 1825 --walk-forward
```

## Sample

- Universe: 368 usable Binance USDT bases.
- Membership: point-in-time top 100 by trailing 30d dollar volume.
- History: 1,825 daily bars.
- Graded observations: 21,334.
- 7d market-regime base-day coverage: BULL 60,908 · CHOP 23,814 · BEAR 46,676.

## Headline 7d result

The full-period market-regime table replicated the 2026-06-10 result:

| setup x BTC regime | n | edge | median return |
|---|---:|---:|---:|
| `mean_reversion` x `CHOP` | 800 | **+10** | +2.3% |
| `mean_reversion` x `BULL` | 1,138 | -3 | 0.0% |
| `mean_reversion` x `BEAR` | 1,043 | 0 | -2.9% |
| `breakdown_risk` x `CHOP` | 352 | -15 | +3.2% |

## Walk-forward result

The new market-regime walk-forward table answers the specific CHOP question:

| test fold | setup x BTC regime | train n | train edge | test n | test edge | test median directional return |
|---:|---|---:|---:|---:|---:|---:|
| 1 | `mean_reversion` x `CHOP` | 165 | -17 | 226 | **+2** | +0.1% |
| 2 | `mean_reversion` x `CHOP` | 391 | -6 | 262 | **+25** | +6.9% |
| 3 | `mean_reversion` x `CHOP` | 653 | +7 | 147 | **+26** | +7.6% |

Interpretation:

- The CHOP mean-reversion edge is not a one-fold artifact: every eligible test
  fold is positive.
- The first test fold is only marginal (+2), so the edge is real but not
  uniformly strong.
- The stronger later folds (+25, +26) explain much of the aggregate +10 result.
- This supports the existing market-regime gate: `mean_reversion` is still best
  treated as CHOP/range-favorable, not a generic bull-market overbought short.

## Other observations

- Aggregate conviction ordering remained monotonic at 7d:
  low -3, medium +3, high +9.
- `breakdown_risk` stayed weak in the key rows:
  aggregate 7d edge -5, CHOP edge -15, and negative CHOP test-fold edges
  where sample size was large enough. The context-only rule remains correct.
- `dip_buy` x `BULL` stayed positive in aggregate (+6), but the fold table is
  thinner than mean-reversion CHOP and still should be treated as a measured
  but thin edge.

## Caveats

- The walk-forward market table uses the full-period same coin-regime x
  BTC-market base rates for fold edge calculations. That keeps it consistent
  with `format_market`, but it is not a fully time-local base-rate benchmark.
- Data is still single-venue Binance USDT and excludes fully delisted pairs.
- This is research evidence only. It does not change live conviction, routing,
  or gating by itself.

## Conclusion

The open follow-up from the 2026-06-10 volume-PIT note is satisfied:
`mean_reversion` x BTC `CHOP` remains positive across chronological test folds
on the same full-cycle volume-PIT configuration. No live change is needed
because the existing registry/market gate already treats this as the favorable
regime.
