# Paper-Trade Outlier Review — 2026-07-10

## Scope

Read-only review of the 75 closed RSI paper trades in `rsi_scanner.db`, focused
on rows with absolute signed return of at least 50%. This review does not change
paper trades, signal scoring, conviction, routing, thresholds, stops, or live
execution.

## Result

Seven rows cross the review threshold. They remain canonical observations rather
than being deleted or capped.

| trade | direction | setup | signed return | entry rank | matched 7d directional outcome |
|---|---:|---|---:|---:|---:|
| SIREN / `siren-2` | long | trend_continuation | -95.74% | 73 | -96.16% |
| TAC / `tac` | long | trend_continuation | -92.95% | 131 | -92.82% |
| BDX / `beldex` | short | breakdown_risk | -81.24% | 126 | -77.44% |
| M / `memecore` | long | mean_reversion | +75.53% | 58 | +58.04% |
| VELVET / `velvet` | long | trend_continuation | -62.57% | 91 | -63.57% |
| VELVET / `velvet` | short | mean_reversion | +60.00% | 123 | +62.71% |
| BTW / `bitway` | short | mean_reversion | +54.55% | 136 | +50.68% |

## Evidence checks

- Every stored signed return recomputes exactly from its paper entry/exit prices
  and direction.
- Every row resolves to the same CoinGecko `coin_id`, symbol, and entry price as
  its nearest new OB/OS crossing signal. Signal-to-paper timestamp lag is under
  one minute for four rows, 17 minutes for BDX, 44 minutes for the earlier VELVET
  row, and 79 minutes for the first long-running SIREN scan.
- The independently stored seven-day outcome has the same direction and remains
  extreme for all seven rows. Differences come from the paper snapshot entry
  versus the market-chart as-of entry, not identity drift.
- CoinGecko's market-chart series shows price and market capitalization moving
  together through the major discontinuities. That is inconsistent with a
  simple token split/redenomination artifact. TAC also shows a large volume spike
  during its July 7 collapse.
- Six rows have stored state features and all six entered during `crisis`
  volatility. Five are `high` liquidity by the scanner's cross-sectional bucket;
  MemeCore is `mid`. The older SIREN row predates stored state features.
- CoinGecko's public history independently shows TAC falling about 96% from its
  June 30 high, SIREN trading near five cents after much higher June prices, and
  MemeCore's sharp late-June/early-July repricing:
  [TAC](https://www.coingecko.com/en/coins/tac),
  [SIREN](https://www.coingecko.com/en/coins/siren-2), and
  [MemeCore](https://www.coingecko.com/en/coins/memecore/historical_data).

## Interpretation

The outliers are credible tail-risk observations, not evidence that the paper
database should be rewritten. They do make arithmetic averages and sequential
one-unit equity especially fragile:

| cohort | average | trimmed mean | median |
|---|---:|---:|---:|
| all 75 | -3.78% | -3.61% | -3.12% |
| actionable 32 | -0.29% | +0.37% | +2.44% |
| control 43 | -6.37% | -5.08% | -5.24% |

The actionable/control separation survives the robust check, while
trend-continuation remains materially poor in the observed downtrend regime.
This is still a small, single-regime sample. Stop-loss scenarios remain
research-only and should not be promoted from endpoint-only paper rows.

## Implemented guardrail

`main.py --score` now prints the trimmed-mean cross-check and retained extreme
rows. `make paper-risk-research` writes the same rows as structured diagnostics,
including price recomputation and stored state context. Neither command mutates
the database or changes live behavior.
