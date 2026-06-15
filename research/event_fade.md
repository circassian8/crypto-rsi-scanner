# Event Fade Engine

**Date:** 2026-06-16
**Status:** Phase 1 research sleeve, alert-only, no execution

## Thesis

The edge is not generic overbought RSI. The target pattern is:

1. A temporary proxy narrative with a dated catalyst.
2. A large pre-event blowoff.
3. Crowded derivatives or leverage.
4. Fragile liquidity and/or supply/distribution pressure.
5. Post-event failure confirmation.

RSI helps identify exhaustion and rollover, but it is not sufficient by itself.
A direct-beneficiary event like BTC around a BTC ETF should not be treated the
same way as a proxy token tied to an external event.

## VELVET Pattern

VELVET acted as a proxy for SpaceX IPO / synthetic pre-IPO access hype. The
important setup was not simply "RSI high." It was a crowded proxy trade into a
dated external catalyst, followed by post-event failure. The Phase 1 engine
models that as a transparent 0-100 score with separate components:

- event clarity
- proxy purity
- pre-event pump
- derivatives crowding
- supply/distribution pressure
- liquidity fragility
- post-event failure
- narrative climax

Narrative climax defaults neutral because the scanner does not yet ingest social
or news data.

## Current Implementation

`crypto_rsi_scanner/event_fade.py` is pure:

- dataclasses for catalyst, market, derivatives, supply, RSI, technical, signal,
  and candidate snapshots
- component score functions
- state-machine transitions
- trigger checks
- risk sizing helper
- JSON fixture loaders
- alert-only report formatter
- feature-vector export for future research

`main.py --event-fade-report` reads `RSI_EVENT_FADE_EVENTS_PATH` and prints a
local report. It does not run a scan, write storage, send notifications, place
orders, or change existing RSI alerts.

Sample:

```bash
RSI_EVENT_FADE_EVENTS_PATH=fixtures/event_fade/sample_events.json \
  .venv/bin/python main.py --event-fade-report
```

## Limitations

- Inputs are manual/local JSON in Phase 1.
- No scraping, no paid API dependencies, no social/news provider.
- Derivatives, supply, and technical fields can be manually supplied and missing
  data degrades gracefully.
- No historical event backtest exists yet.
- No exchange execution exists or should be inferred from this module.

## Data Needed For Real Validation

- event calendar with first-seen timestamps and source confidence
- proxy/direct-beneficiary labels
- spot and perp volumes
- open interest and funding history
- order-book depth/spread snapshots
- unlock and exchange-inflow data
- intraday/post-event technical levels such as event VWAP and lower highs

## Shipping Rule

Do not promote event-fade output into live alert routing or paper trading until
the feature vector is backtested or manually reviewed across a meaningful event
sample. For now it is a separate research/alert sleeve.
