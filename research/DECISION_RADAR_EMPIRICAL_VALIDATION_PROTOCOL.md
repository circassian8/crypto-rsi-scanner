# Decision Radar empirical-validation protocol v1

- Protocol: `decision_radar_empirical_validation_v1`
- Frozen at: `2026-07-16T06:00:00Z` before final-test evaluation
- SHA-256: `ff1de1a64a54e339f753532f712d0514c0344ddd011fa3783ae6d23750661c24`
- Validation: `valid`
- Research-only; recommendations never auto-apply to production.

## Chronological partitions

| Partition | Start inclusive | End exclusive | May select policy? |
|---|---|---|---|
| development | `2021-06-12T00:00:00Z` | `2023-01-01T00:00:00Z` | `true` |
| validation | `2023-01-01T00:00:00Z` | `2025-01-01T00:00:00Z` | `true` |
| final_test | `2025-01-01T00:00:00Z` | `2026-06-01T00:00:00Z` | `false` |

Final-test outcomes may reject a frozen recommendation, but they may not select or tune one.

## Point-in-time replay

Daily observations are formed at the completed Binance candle close. Universe membership is the trailing 30-day quote-volume rank calculated with data available at that close. Rolling features use current and earlier bars only. The locally cached candidate pool retains a documented delisting-survivorship limitation.

Intraday returns, historical spread/order-book quality, market cap, derivatives, calendar, catalyst, and on-chain context remain explicitly unavailable or missing unless an exact time-valid source is supplied. They are never invented or silently proxied.

## Outcomes and episodes

The frozen primary horizon is 3 days; 1, 7, and 14 days are sensitivity horizons. Outcome bars begin after the idea bar. Return, BTC/ETH-relative return, MFE, MAE, time-to-extremes, invalidation, continuation/reversal, expiry, and post-expiry behavior are measured. Fixed-start 24-hour episodes freeze the first eligible representative and retain dependent route/score/context progression without inflating sample size.

## Controls, costs, and uncertainty

Matched non-signal controls use date, regime, and liquidity and are selected by an outcome-blind deterministic hash. Simple raw-mover, volume, RSI, relative-strength, BTC/ETH, and late-fade benchmarks remain descriptive. Historical spread is unavailable; 0/20/50/100/200 bps round-trip costs are labeled assumptions. Episode bootstrap intervals are exploratory, and cohort tables carry multiple-comparison warnings.

## Evidence and approval boundaries

Samples below the frozen minima are reported as `insufficient_sample`, not as positive or negative evidence. Development and validation may nominate a frozen shadow recommendation; final test only confirms or rejects it. Any production change requires a separate versioned human decision and rollback plan.

## Safety

Protocol inspection and replay make zero provider calls and cannot mutate authorization, dashboard authority, production policy, notifications, trades, orders, paper trades, RSI rows, or `TRIGGERED_FADE`.
