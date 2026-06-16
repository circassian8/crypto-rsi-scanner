# Event Discovery Design

**Date:** 2026-06-16
**Status:** Phase 1-8 fixture framework with clean CoinGecko universe bridge,
fixture-backed exchange announcement providers, structured calendar/unlock
providers, news/proxy-narrative providers, external catalyst providers, and
Coinalyze-style derivatives plus Tokenomist/Etherscan/Arkham/Dune-style
supply/on-chain enrichment, research-only

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

Current files:

- `event_models.py`: immutable discovery/classification data models
- `event_providers/base.py`: provider protocols
- `event_providers/manual_json.py`: local JSON fixture provider
- `event_providers/coingecko_universe.py`: local CoinGecko market fixture
  provider that reuses shared universe hygiene filters
- `event_providers/binance_announcements.py`: local Binance announcement fixture
  provider for spot/listing-style direct events
- `event_providers/bybit_announcements.py`: local Bybit announcement fixture
  provider for listing/perp-style direct events
- `event_providers/coinmarketcal.py`: local structured calendar fixture provider
  for dated crypto events
- `event_providers/tokenomist.py`: local unlock fixture provider that also
  populates supply-pressure fields
- `event_providers/cryptopanic.py`: local CryptoPanic-style news fixture
  provider for proxy/direct/ambiguous narrative evidence
- `event_providers/gdelt.py`: local GDELT-style news fixture provider for
  external catalyst and attention-event evidence
- `event_providers/project_blog_rss.py`: local project-blog/RSS fixture provider
  for project-sourced narrative evidence
- `event_providers/external_ipo.py`: local IPO-calendar fixture provider for
  external-company catalysts
- `event_providers/sports_fixtures.py`: local sports-fixture provider for
  dated team/match catalysts
- `event_providers/prediction_market_events.py`: local prediction-market
  fixture provider for external attention/catalyst markets
- `derivatives_providers/coinalyze.py`: local derivatives fixture provider that
  maps Coinalyze-style OI/funding/crowding rows to discovery candidates
- `supply_providers/tokenomist.py`: local supply fixture provider for unlock and
  vesting-style pressure snapshots
- `supply_providers/etherscan.py`: local supply fixture provider for token
  transfer / CEX-inflow style snapshots
- `supply_providers/arkham.py`: local supply fixture provider for
  entity-labeled team/MM activity style snapshots
- `supply_providers/dune.py`: local supply fixture provider for custom
  concentration/admin-risk style snapshots
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

## Structured Calendar And Unlock Providers

CoinMarketCal-style fixtures add dated crypto-native events such as mainnet
launches, governance, airdrops, TGEs, and protocol upgrades. Tokenomist-style
fixtures add token unlocks and carry `unlock_amount` plus
`unlock_pct_circulating` into the event-fade candidate's supply snapshot.

These sources are useful for the radar and negative/control sample, but they are
direct token-specific catalysts by default:

- mainnet/protocol/governance calendar events -> direct protocol/token events
- token unlocks -> `direct_unlock`

They must remain `NO_TRADE` under the proxy-fade gate unless a separate source
later proves a true proxy relationship.

## News And Proxy-Narrative Providers

CryptoPanic-, GDELT-, and project-blog/RSS-style providers currently read local
JSON fixtures only. They normalize common article shapes such as `results`,
`features`, and `items` into `RawDiscoveredEvent` rows, preserving explicit
fixture event metadata when provided and otherwise inferring only coarse event
types.

These providers are the first radar layer aimed at VELVET-style narrative
setups:

- proxy exposure news, such as synthetic pre-IPO access to OpenAI/Anthropic
- fan-token or attention-token news around dated sports/political catalysts
- direct-beneficiary crypto news, such as BTC/BTC ETF, as negative controls
- ambiguous momentum/news chatter with no dated catalyst
- post-event articles that must not create pre-event discovery evidence

News evidence can classify an asset as proxy/direct/ambiguous, but it still
feeds the same hard event-fade gate. Articles first seen after the event time
must not create a `SHORT_TRIGGERED` candidate even if the price/technical fields
look strong.

## External Catalyst Providers

External IPO, sports-fixture, and prediction-market providers currently read
local JSON fixtures only. They turn non-crypto catalysts into radar events:

- external IPO/calendar entries
- sports matches or fixtures
- prediction-market questions around dated external events

External catalysts are radar-first. An external event by itself does not resolve
to a crypto asset and therefore cannot produce a fade candidate. A crypto
candidate appears only when the source text also contains asset-link evidence
such as a known token alias plus proxy narrative terms. Date-only catalyst rows
are preserved with lower `event_time_confidence` and should remain validation
sample evidence, not trade triggers.

## Derivatives Enrichment

The Coinalyze-style derivatives provider currently reads local JSON fixtures
only. It produces candidate enrichment keyed by coin id, symbol, base symbol, or
market symbol and fills `EventDerivativesSnapshot` fields used by
`event_fade.py`:

- perp availability
- open interest and 24h OI change
- OI-to-market-cap
- funding rate / percentile
- futures volume
- perp/spot volume ratio
- liquidations, long/short ratio, and basis

Raw event fixture data wins over provider enrichment. This keeps provider rows
from overwriting hand-reviewed event evidence during fixture research.

Derivatives crowding is evidence, not eligibility. A direct exchange listing,
token unlock, or other non-proxy event must remain `NO_TRADE` even when OI,
funding, and perp/spot crowding are extreme.

## Supply And On-Chain Enrichment

Tokenomist-, Etherscan-, Arkham-, and Dune-style supply providers currently read
local JSON fixtures only. They produce candidate enrichment keyed by coin id,
symbol, contract address, or alias and fill `EventSupplyPressureSnapshot` fields
used by `event_fade.py`:

- large-holder / exchange-inflow flags
- CEX inflow amount and percent of supply
- unlock amount and percent of circulating supply
- top-holder concentration
- team or market-maker wallet activity
- admin or mint-risk flags

Raw event fixture data wins over provider enrichment. This keeps provider rows
from overwriting hand-reviewed event evidence during fixture research.

Supply pressure is evidence, not eligibility. A direct exchange listing, token
unlock, or other non-proxy event must remain `NO_TRADE` even when exchange
inflows, unlocks, concentration, and admin-risk flags are severe.

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
- TESTCAL CoinMarketCal-style mainnet-launch fixture
- TESTUNLOCK Tokenomist-style unlock fixture with supply-pressure fields
- TESTAI CryptoPanic-style OpenAI pre-IPO proxy article that can trigger once
  post-event failure is confirmed in the fixed-time test path
- TESTBTC CryptoPanic-style BTC ETF direct-beneficiary article
- TESTFAN GDELT-style fan-token World Cup proxy attention article
- TESTLATE project-blog post-event proxy article that must remain `NO_TRADE`
  because it was first seen after the catalyst
- TESTAMBIG project-blog ambiguous momentum article with no dated catalyst
- SpaceX IPO calendar placeholder with no crypto asset mention, radar-only
- Test FC clean sports fixture with no crypto asset mention, radar-only
- TESTFAN linked sports fixture, proxy watchlist/control only
- TESTPRED prediction-market OpenAI catalyst with token proxy evidence
- election prediction-market catalyst with no crypto asset mention, radar-only
- TESTLIST Coinalyze-style high derivatives crowding fixture that still remains
  `NO_TRADE` because the listing is direct
- TESTPERP Coinalyze-style no-perp snapshot fixture
- TESTVELVET conflicting Coinalyze-style snapshot proving raw event derivatives
  are not overwritten
- TESTPRED Tokenomist-style unlock/supply snapshot that enriches a proxy radar
  candidate without forcing a trade
- TESTLIST Etherscan-style exchange-inflow snapshot that raises supply-pressure
  evidence while the direct listing still remains `NO_TRADE`
- TESTAI Arkham-style team/MM wallet activity snapshot
- TESTFAN Dune-style holder concentration and admin-risk snapshot
- TESTVELVET conflicting Tokenomist-style supply snapshot proving raw event
  supply evidence is not overwritten

`fixtures/coingecko_smoke/top_markets.json` is also used for universe-provider
coverage. BTC/ETH/SOL become discovery assets, while Tether is excluded by the
shared hygiene filter.

## CLI

Run the research report with:

```bash
RSI_EVENT_DISCOVERY_EVENTS_PATH=fixtures/event_discovery/raw_events.json \
RSI_EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH=fixtures/event_discovery/binance_announcements.json \
RSI_EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH=fixtures/event_discovery/bybit_announcements.json \
RSI_EVENT_DISCOVERY_COINMARKETCAL_PATH=fixtures/event_discovery/coinmarketcal_events.json \
RSI_EVENT_DISCOVERY_TOKENOMIST_PATH=fixtures/event_discovery/tokenomist_unlocks.json \
RSI_EVENT_DISCOVERY_CRYPTOPANIC_PATH=fixtures/event_discovery/cryptopanic_news.json \
RSI_EVENT_DISCOVERY_GDELT_PATH=fixtures/event_discovery/gdelt_news.json \
RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH=fixtures/event_discovery/project_blog_rss.json \
RSI_EVENT_DISCOVERY_EXTERNAL_IPO_PATH=fixtures/event_discovery/external_ipo_events.json \
RSI_EVENT_DISCOVERY_SPORTS_FIXTURES_PATH=fixtures/event_discovery/sports_fixtures.json \
RSI_EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH=fixtures/event_discovery/prediction_market_events.json \
RSI_EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH=fixtures/event_discovery/coinalyze_derivatives.json \
RSI_EVENT_DISCOVERY_TOKENOMIST_SUPPLY_PATH=fixtures/event_discovery/tokenomist_supply.json \
RSI_EVENT_DISCOVERY_ETHERSCAN_SUPPLY_PATH=fixtures/event_discovery/etherscan_supply.json \
RSI_EVENT_DISCOVERY_ARKHAM_SUPPLY_PATH=fixtures/event_discovery/arkham_supply.json \
RSI_EVENT_DISCOVERY_DUNE_SUPPLY_PATH=fixtures/event_discovery/dune_supply.json \
RSI_EVENT_DISCOVERY_UNIVERSE_PATH=fixtures/coingecko_smoke/top_markets.json \
  .venv/bin/python main.py --event-discovery-report
```

The report is local and observational. It does not send alerts or write the DB.

## Promotion Requirements

Do not route discovered event-fade candidates to Telegram or paper trading until
a reviewed event sample shows positive edge and acceptable false-positive rates.
First promotion, if approved later, should still be notification-only.
