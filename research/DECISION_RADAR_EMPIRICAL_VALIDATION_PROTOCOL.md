# Decision Radar empirical-validation protocol v1

- Protocol: `decision_radar_empirical_validation_v1`
- Frozen at: `2026-07-16T05:30:00Z` before final-test evaluation
- SHA-256: `efee20ccaa3dda03c8e1172633d92d6a9bf8cb3ae12c926471f2151941d5f158`
- Validation: `valid`
- Research-only; recommendations never auto-apply to production.

## Chronological partitions

| Partition | Idea start | Idea end | Outcome end | May select policy? |
|---|---|---|---|---|
| development | `2021-06-12T00:00:00Z` | `2023-01-01T00:00:00Z` | `2023-01-15T00:00:00Z` | `true` |
| validation | `2023-01-15T00:00:00Z` | `2025-01-01T00:00:00Z` | `2025-01-15T00:00:00Z` | `true` |
| final_test | `2025-01-15T00:00:00Z` | `2026-06-01T00:00:00Z` | `2026-06-18T00:00:00Z` | `false` |

Fourteen-day outcome-only embargoes separate idea partitions. They permit already-observed ideas to mature through the frozen sensitivity horizon without allowing new ideas into the next partition. The clean final-test idea window begins `2025-01-15T00:00:00Z`; earlier nominal holdout-tail dates are quarantined and are not final-test evidence.

Final-test outcomes may reject a frozen recommendation, but they may not select or tune one. Every final verdict uses the sealed `noninferior_return_failure_selected_day_burden_v1` rule and requires at least 30 matured visible episodes. Its burden check uses the same complete set of selected UTC observation days for production and every shadow scenario, including days with zero ideas; active-idea-day rates remain descriptive only.

## Point-in-time replay

Daily observations are formed at the completed Binance candle close. Universe membership is the trailing 30-day quote-volume rank calculated with data available at that close. Rolling features use current and earlier bars only. The volume z-score uses a frozen 90-day lookback and requires 20 prior observations. Available daily RSI is retained only as read-only historical-OHLCV, point-in-time observational context; it cannot adjust scores, policy, or thesis origin. The locally cached candidate pool retains a documented delisting-survivorship limitation.

Intraday returns, historical spread/order-book quality, market cap, derivatives, calendar, catalyst, and on-chain context remain explicitly unavailable or missing unless an exact time-valid source is supplied. They are never invented or silently proxied.

## Outcomes and episodes

The frozen primary horizon is 3 days; 1, 7, and 14 days are sensitivity horizons. Outcome bars begin after the idea bar. A horizon is readable only when its due time is strictly before the partition's frozen outcome boundary. Return, BTC/ETH-relative return, MFE, MAE, time-to-extremes, invalidation, continuation/reversal, expiry, and post-expiry behavior are measured. Fixed-start 24-hour episodes use an inclusive window end: an observation exactly 24 hours after the representative remains a dependent repeat. The first eligible representative stays frozen and dependent route/score/context progression is retained without inflating sample size; 12-hour and 48-hour grouping counts are reported as sensitivity only.

## Controls, costs, and uncertainty

Matched non-signal controls use date, regime, and liquidity and are selected by an outcome-blind deterministic hash. Simple raw-mover, volume, RSI, relative-strength, BTC/ETH, and late-fade benchmarks remain descriptive. Historical spread is unavailable; fee, spread, slippage, adverse-selection, 0/20/50/100/200 bps round-trip, delay, capacity, daily/simultaneous-budget, stop, and holding-period scenarios are labeled assumptions. Trailing-stop results remain unavailable when daily bars cannot establish intraday high/low order. Episode bootstrap intervals are exploratory, and cohort tables carry multiple-comparison warnings.

## Evidence and approval boundaries

Samples below the frozen minima are reported as `insufficient_sample`, not as positive or negative evidence. Development and validation may nominate a frozen shadow recommendation; final test only confirms or rejects it. Any production change requires a separate versioned human decision and rollback plan.

## Safety

Protocol inspection and replay make zero provider calls and cannot mutate authorization, dashboard authority, production policy, notifications, trades, orders, paper trades, RSI rows, or `TRIGGERED_FADE`.
