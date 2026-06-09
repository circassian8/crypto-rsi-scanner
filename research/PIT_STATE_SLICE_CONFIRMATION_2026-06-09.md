# PIT State-Slice Confirmation - 2026-06-09

Command:

```bash
.venv/bin/python -m crypto_rsi_scanner.backtest --pit --top-n 80 --pool 150 --days 365 --state-slices
```

Scope:
- CoinGecko point-in-time top-80 membership from a clean 150-coin candidate pool.
- Demo/free CoinGecko path capped history to 365d.
- Cache was empty at start; the run populated 150 raw `market_chart` JSON files
  under local `backtest_cache/`.
- 128/150 candidate histories were usable.
- 1325 graded signal observations.

Critical caveat:
- The PIT window had BTC market-regime coverage only in `BEAR` at the 7d and 1d
  reports. This can check bear-regime behavior, but it cannot confirm bull/chop
  candidates from the 4-year Binance current-top run.

## Setup Baseline

At the 7d primary horizon:

| setup | n | signal conf | base | edge | interpretation |
|---|---:|---:|---:|---:|---|
| `breakdown_risk` | 43 | 51% | 56% | -5 | Still not actionable. |
| `dip_buy` | 5 | 0% | 47% | -47 | Too few samples; bear-regime dip buys looked bad. |
| `mean_reversion` | 229 | 66% | 54% | +12 | Strongest PIT-supported cohort in this window. |
| `trend_continuation` | 35 | 43% | 47% | -4 | Not confirmed in bear window. |

Conviction at 7d:
- low: +5 edge, n=130
- medium: +8 edge, n=180
- high: +3 edge, n=2

The high-conviction bucket is too small in this PIT window.

## State-Slice Read

Because this PIT run is bear-only, treat the state-slice table as bear-regime
confirmation only.

Confirmed or partially supported:
- `mean_reversion` showed positive edge across the main bear-regime state
  cohorts: `normal` volatility (+15, n=120), `low_compressed` volatility (+7,
  n=87), neutral breadth (+11, n=221), low/mid/high relative strength
  (+25/+12/+7), high liquidity (+13, n=198), and low falling-knife bucket (+11,
  n=221).
- `breakdown_risk` again failed as an actionable setup at 7d (-5 aggregate).
  A small `low_compressed` volatility cell was positive (+22, n=13), but this is
  too small and conflicts with the aggregate breakdown-risk finding.
- `trend_continuation` had one positive normal-volatility cell (+16, n=21), but
  aggregate trend continuation in the bear-only PIT window was negative.

Not confirmed:
- Bull-regime `dip_buy` and `trend_continuation` candidates from the Binance run,
  because this PIT window had no bull market-regime coverage.
- Chop-regime `mean_reversion`, because this PIT window had no chop coverage.
- Falling-knife bucket as a routing feature; its current split is still not
  clean enough.

## Decision

No live conviction, routing, or gating changes from this PIT run.

What this run does support:
- Keep `breakdown_risk` context-only.
- Treat `mean_reversion` as the most promising bear-regime setup to monitor with
  live `state_json` outcomes.
- Do not use this 365d PIT window to validate bull/chop state rules.

Next evidence needed:
- Stronger PIT history that includes bull/chop periods, via Pro CoinGecko or
  another historical market-cap source.
- Matured live state cohorts from `signals.state_json` and `paper_trades.state_json`.
