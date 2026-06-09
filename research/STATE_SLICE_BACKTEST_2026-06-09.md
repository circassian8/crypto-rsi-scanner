# State-Slice Backtest Review - 2026-06-09

Command:

```bash
.venv/bin/python -m crypto_rsi_scanner.backtest --top-n 80 --days 1460 --state-slices
```

Scope:
- 49 usable Binance USDT histories from the clean current top-80 universe.
- 1460 daily bars, current-top survivorship-biased, single venue, no fees/slippage.
- 7648 graded signal observations.
- State buckets were compared against same coin-regime and same state-bucket base days.

## Setup Baseline

At the 7d primary horizon:

| setup | n | signal conf | base | edge | note |
|---|---:|---:|---:|---:|---|
| `breakdown_risk` | 440 | 48% | 53% | -5 | Still not actionable. |
| `dip_buy` | 155 | 54% | 46% | +7 | Still useful in the right regime. |
| `mean_reversion` | 1017 | 53% | 51% | +2 | Thin aggregate edge; regime matters. |
| `trend_continuation` | 300 | 53% | 46% | +7 | Useful in the right regime. |

Conviction buckets at 7d remain directionally sane:
- low: -4 edge
- medium: +7 edge
- high: +12 edge

## Market Regime Check

The existing registry findings held up:
- `dip_buy` in BTC bull: +8 edge at 7d.
- `trend_continuation` in BTC bull: +8 edge at 7d.
- `mean_reversion` in BTC chop: +12 edge at 7d; in BTC bull: -5.
- `breakdown_risk` remains weak: BEAR +1, BULL -4, CHOP -16 at 7d.

Do not promote `breakdown_risk` to actionable from this run.

## State-Cohort Candidates

These are candidates for PIT/live confirmation, not live rules.

Volatility:
- `dip_buy` looked bad in `low_compressed` volatility (-12 edge, n=37) but good
  in `normal` (+13, n=75) and `high` (+13, n=30).
- `trend_continuation` looked good in `normal` (+11, n=104) and
  `high_expanding` (+13, n=56), but poor in `crisis` (-10, n=60).
- `mean_reversion` looked best in `low_compressed` (+10, n=264) and weak in
  `high` (-8, n=93).

Breadth:
- `risk_on_broad` favored `trend_continuation` (+7, n=169) and hurt
  `mean_reversion` (-9, n=196).
- `washout`/`washout_recovery` cells were small and mixed. Treat them as risk
  context until PIT/live data confirms anything.
- `breakdown_risk` during `washout` showed continuation down (+26, n=24), but
  this is small-sample and should remain context-only/risk warning.

Relative strength:
- `mean_reversion` worked better for high-RS names (+7, n=334).
- `trend_continuation` was better in mid/high RS (+9/+6) than low RS (+1).
- `breakdown_risk` was worse in mid/high RS (-14/-28).

Liquidity:
- No clean promotion-ready rule. `trend_continuation` low-liquidity showed +13
  edge (n=44), but low-liquidity implementation and tradability need caution.
- `dip_buy` was better in mid/high liquidity (+10/+8) than low liquidity (0).

Falling-knife bucket:
- The current falling-knife heuristic did not create a clean actionable split.
- Low/elevated/high buckets should remain reporting-only until live/PIT evidence
  improves the score definition.

## Decision

No live conviction, routing, or gating changes from this run.

The most plausible candidates to validate next are:
- `dip_buy`: avoid or downweight low-compressed-volatility dips if PIT/live data confirms.
- `mean_reversion`: prefer low-compressed-volatility and avoid risk-on-broad if confirmed.
- `trend_continuation`: prefer normal/high-expanding volatility and risk-on-broad if confirmed.
- `breakdown_risk`: keep context-only; maybe use washout/breadth-collapse as a risk warning, not a trade signal.

Next evidence needed:
- Point-in-time state slices with a stronger CoinGecko history source or alternate PIT universe.
- Matured live `state_json` outcomes and paper trades.
