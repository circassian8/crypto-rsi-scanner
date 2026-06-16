# Event Discovery Design

**Date:** 2026-06-16
**Status:** Phase 1/2/3 fixture framework with clean CoinGecko universe bridge
and fixture-backed exchange announcement providers, research-only

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
- `event_providers/coingecko_universe.py`: local CoinGecko market fixture
  provider that reuses shared universe hygiene filters
- `event_providers/binance_announcements.py`: local Binance announcement fixture
  provider for spot/listing-style direct events
- `event_providers/bybit_announcements.py`: local Bybit announcement fixture
  provider for listing/perp-style direct events
- `event_resolver.py`: alias-aware asset resolver
- `event_classification.py`: deterministic proxy/direct classifier
- `event_discovery.py`: normalizer, deduper, orchestrator, report formatter

## Universe Integration

Manual aliases remain the safest way to resolve one-off proxy tokens and known
test cases. `RSI_EVENT_DISCOVERY_UNIVERSE_PATH` can additionally point to a
CoinGecko-style market fixture, either a `top_markets.json` file or a directory
containing that file. The provider applies `universe.filter_markets_with_audit`
before producing `DiscoveredAsset` rows, so stablecoins, wrapped/staked receipts,
synthetics, bad identity rows, and low-quality market rows are screened by the
same logic used by live scans and backtests.

This is still an offline fixture path. It does not fetch CoinGecko directly.

## Exchange Announcement Providers

Binance and Bybit announcement providers currently read local JSON fixtures only.
They parse spot listing and perpetual/futures listing announcements into
`RawDiscoveredEvent` rows with normalized event metadata. These events are
valuable for the radar and negative/control sample, but they are direct
token-specific catalysts by default:

- exchange listings -> `direct_listing`
- perp/futures listings -> `direct_listing`
- generic/non-listing exchange announcements -> ignored

Direct exchange events must remain `NO_TRADE` under the event-fade proxy gate
unless a separate source later proves a true proxy relationship.

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
- TESTLIST Binance spot-listing announcement fixture
- TESTPERP Bybit perpetual-listing announcement fixture

`fixtures/coingecko_smoke/top_markets.json` is also used for universe-provider
coverage. BTC/ETH/SOL become discovery assets, while Tether is excluded by the
shared hygiene filter.

## CLI

Run the research report with:

```bash
RSI_EVENT_DISCOVERY_EVENTS_PATH=fixtures/event_discovery/raw_events.json \
RSI_EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH=fixtures/event_discovery/binance_announcements.json \
RSI_EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH=fixtures/event_discovery/bybit_announcements.json \
RSI_EVENT_DISCOVERY_UNIVERSE_PATH=fixtures/coingecko_smoke/top_markets.json \
  .venv/bin/python main.py --event-discovery-report
```

The report is local and observational. It does not send alerts or write the DB.

## Promotion Requirements

Do not route discovered event-fade candidates to Telegram or paper trading until
a reviewed event sample shows positive edge and acceptable false-positive rates.
First promotion, if approved later, should still be notification-only.
