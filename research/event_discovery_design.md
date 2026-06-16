# Event Discovery Design

**Date:** 2026-06-16
**Status:** Phase 1 fixture-only framework, research-only

## Goal

Build a radar that can discover VELVET-style event-fade setups before the pure
`event_fade.py` engine scores them:

1. dated external catalyst
2. crypto asset linked to the event
3. proxy narrative, not direct-beneficiary exposure
4. pre-event pump / crowding / fragility evidence
5. post-event technical failure

The discovery system should collect broadly but trigger narrowly. Phase 1 is not
an alerting, paper-trading, storage, or execution path.

## Boundary

`event_fade.py` remains pure and side-effect free. Discovery code may normalize,
resolve, classify, dedupe, and report local fixture data. It must not mutate
live scanner state, send Telegram messages, write signal/outcome/paper tables,
or imply an order.

Phase 1 files:

- `event_models.py`: immutable discovery/classification data models
- `event_providers/base.py`: provider protocols
- `event_providers/manual_json.py`: local JSON fixture provider
- `event_resolver.py`: alias-aware asset resolver
- `event_classification.py`: deterministic proxy/direct classifier
- `event_discovery.py`: normalizer, deduper, orchestrator, report formatter

## Classification Rules

Proxy candidates need all of:

- external asset or catalyst
- evidence that the crypto asset is being used for synthetic exposure,
  attention, fan/political/prediction-market demand, or similar proxy behavior
- known event time
- the linked crypto asset is not the direct beneficiary

Direct events stay research-only and must not pass the proxy fade gate:

- token unlocks
- exchange/perp listings
- airdrops/TGEs
- mainnet/protocol upgrades
- ETF events for the asset itself

Ambiguous cases stay `NO_TRADE`.

## Asset Resolution

Ticker-only matching is intentionally weak. Confident matches require one of:

- coin id
- contract address
- known alias
- exact name, preferably with ticker context

Symbol collisions are rejected unless another high-confidence identity clue is
present. This is more important than recall because false-positive shorts are
more dangerous than missed setups.

## Fixture Coverage

`fixtures/event_discovery/raw_events.json` and
`fixtures/event_discovery/asset_aliases.json` cover:

- TESTVELVET + SpaceX IPO proxy article
- TESTBTC + BTC ETF direct-beneficiary article
- TESTTOKEN + Binance listing direct event
- TESTPUMP ambiguous pump with no dated catalyst
- COLLIDE ticker collision that must not resolve confidently

## CLI

Run the research report with:

```bash
RSI_EVENT_DISCOVERY_EVENTS_PATH=fixtures/event_discovery/raw_events.json \
  .venv/bin/python main.py --event-discovery-report
```

The report is local and observational. It does not send alerts or write the DB.

## Promotion Requirements

Do not route discovered event-fade candidates to Telegram or paper trading until
a reviewed event sample shows positive edge and acceptable false-positive rates.
First promotion, if approved later, should still be notification-only.
