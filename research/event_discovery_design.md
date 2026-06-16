# Event Discovery Design

**Date:** 2026-06-16
**Status:** Phase 1-10 framework with clean CoinGecko universe bridge,
fixture-backed exchange announcement providers plus opt-in live Bybit
announcement fetch, structured calendar/unlock providers, news/proxy-narrative
providers plus opt-in live CryptoPanic posts, GDELT Article List, and
project-blog RSS/Atom fetches, external catalyst providers, and
Coinalyze-style derivatives plus
Tokenomist/Etherscan/Arkham/Dune-style supply/on-chain enrichment, plus grouped
auto reporting and validation-sample exports, research-only JSONL cache refresh,
validation-sample review metrics, labeling-queue support, research-only merge
support, local outcome-price export, and outcome-fill support.

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
resolve, classify, dedupe, report local fixture data, write local observational
JSONL cache artifacts, export local validation artifacts, and review labeled
local validation artifacts. It must not mutate live scanner state, send Telegram
messages, write live signal/outcome/paper tables, or imply an order.

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
  provider plus opt-in live posts fetch for proxy/direct/ambiguous narrative
  evidence
- `event_providers/gdelt.py`: local GDELT-style news fixture provider plus
  opt-in live GDELT Article List fetch for external catalyst and attention-event
  evidence
- `event_providers/project_blog_rss.py`: local project-blog/RSS fixture provider
  plus opt-in live RSS/Atom fetch for project-sourced narrative evidence
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
- `event_discovery.py`: normalizer, deduper, orchestrator, flat radar report
  formatter, grouped event-fade auto report formatter, and validation-sample
  export helpers
- `event_cache.py`: local JSONL observational cache writer for point-in-time
  discovery evidence
- `event_price_history.py`: local OHLCV price fixture exporter for triggered
  validation rows
- `event_validation.py`: local validation-sample loader/reviewer/labeling
  queue/merger/outcome filler for human labels, outcome metrics, and promotion
  blockers

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

Binance and Bybit announcement providers read local JSON fixtures by default.
Bybit can also fetch the official `GET /v5/announcements/index` endpoint when
`RSI_EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE=1`. The live fetch is still a
research-only source for local reports/exports; it is not live routing. The
Bybit API docs define `locale`, optional `type`, `page`, and `limit` parameters,
and return announcement rows under `result.list` with title, description, type,
tags, URL, and timestamps:
https://bybit-exchange.github.io/docs/v5/announcement

The exchange providers parse spot listing and perpetual/futures listing
announcements into `RawDiscoveredEvent` rows with normalized event metadata.
These events are valuable for the radar and negative/control sample, but they
are direct token-specific catalysts by default:

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

CryptoPanic-, GDELT-, and project-blog/RSS-style providers read local JSON
fixtures by default. CryptoPanic can optionally fetch live posts when an API
token is configured, GDELT can optionally fetch live Article List JSON, and
project-blog/RSS can optionally fetch explicit RSS/Atom feed URLs. All paths
normalize article/feed shapes into `RawDiscoveredEvent` rows, preserving
explicit fixture event metadata when provided and otherwise inferring only
coarse event types.

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

## Auto Report

`main.py --event-fade-auto-report` runs the same fixture-only discovery path as
`--event-discovery-report`, then groups the scored candidates into lifecycle
sections:

- EVENT RADAR
- PROXY WATCHLIST
- BLOWOFF RISK
- EVENT PASSED
- ARMED
- TRIGGERED
- REJECTED / NO TRADE
- AMBIGUOUS

Each candidate row includes symbol, coin id, event name/time, first-seen time,
link/classifier confidence, relationship type, fade score, state/signal,
missing data, reason codes, warnings, source URLs, and invalidation level when
available.

This remains local and observational. It does not send Telegram alerts, write
live signal/outcome/paper tables, open paper trades, or imply execution.

## Observational JSONL Cache

`main.py --event-discovery-refresh` fetches the configured research sources,
runs the discovery pipeline, and appends local JSONL artifacts under
`RSI_EVENT_DISCOVERY_CACHE_DIR` (`event_fade_cache` by default, gitignored).
The cache preserves point-in-time evidence for review and future backtests. It
does not write SQLite, live signal/outcome/paper tables, Telegram, or orders.

Files:

- `raw_events.jsonl`
- `normalized_events.jsonl`
- `event_asset_links.jsonl`
- `classifications.jsonl`
- `candidate_snapshots.jsonl`
- `discovery_runs.jsonl`

Stable evidence files dedupe already-seen rows by source/event identity where
possible. `candidate_snapshots.jsonl` appends every refresh so later analysis
can inspect how scores and missing data looked at each observed time.

`main.py --event-fade-export-cache-sample PATH` turns the latest cached
candidate snapshot for each stable event/asset/relationship identity back into
the normal `event_fade_validation_sample_v1` schema. This is the preferred
review input once live/refreshed sources are running, because it uses the
point-in-time cache instead of only the current fixture run. The command writes
only the requested JSONL/CSV artifact and remains research-only.

## Validation Sample Export

`main.py --event-fade-export-sample PATH` runs the same fixture-only discovery
path and writes a review artifact. A `.csv` suffix writes CSV; any other suffix
writes JSONL; `-` prints JSONL to stdout. The exported rows are designed for
manual labeling and future point-in-time backtests, not for alerts.

Each row includes:

- raw source ids, providers, titles, content hashes, URLs, and raw-source
  timestamps
- normalized event identity, event type, event time/confidence, first-seen time,
  and external asset
- resolved asset identity plus link confidence, match reason, and evidence
- proxy/direct classification, classifier version, confidence, reason, and
  evidence
- fade state, signal type, score, eligibility, reason codes, warnings,
  component scores, feature fields, and missing-data markers
- blank human-review and future outcome columns such as `human_label`,
  `human_notes`, `max_adverse_excursion`, `max_favorable_excursion`, and
  post-event returns

This export may write only the requested local artifact. It must not write live
DB rows, send alerts, open paper trades, or imply execution.

## Validation Sample Merge

`main.py --event-fade-merge-sample FRESH REVIEWED OUT` preserves human work when
the discovery export is regenerated. It reads a fresh JSONL/CSV export and a
previously reviewed JSONL/CSV sample, matches rows by stable event id, asset id,
and relationship type, then copies nonblank review fields into the fresh rows:

- `review_status`
- `human_label`
- `human_notes`
- `max_adverse_excursion`
- `max_favorable_excursion`
- `post_event_return_24h`
- `post_event_return_72h`
- `post_event_return_7d`

The merge writes only the requested `OUT` artifact and reports matched/unmatched
reviewed rows. It does not change live storage, routing, paper trades, or event
state.

## Validation Price Fixture Export

`main.py --event-fade-export-outcome-prices SAMPLE OUT` builds the local OHLCV
price fixture consumed by outcome filling. It reads `SHORT_TRIGGERED` rows from
a validation sample, infers each asset's Binance-style USDT pair from
`asset_symbol`, and writes a JSON artifact with daily candles:

- `asset_coin_id`
- `asset_symbol`
- `timestamp`
- `high`
- `low`
- `close`
- `volume`
- `quote_volume`

By default the command can use the existing Binance daily-kline fetch/cache path
from the research backtester. For deterministic offline runs, pass
`--event-fade-price-fixture-dir DIR`, where `DIR` contains Binance-style CSV
fixtures such as `VELVETUSDT.csv` with `date`, `close`, and optional `high`,
`low`, `volume`, and `quote_volume` columns.

This command writes only the requested price fixture. It does not label samples,
fill outcomes by itself, write live storage, route alerts, open paper trades, or
execute orders.

## Validation Outcome Fill

`main.py --event-fade-fill-outcomes SAMPLE PRICES OUT` fills blank outcome
fields for `SHORT_TRIGGERED` validation rows from a local OHLCV fixture. The
price fixture may be either a flat list of candles or a mapping by `coin_id`/
symbol. Flat rows can use:

- `asset_coin_id` or `coin_id`
- `asset_symbol` or `symbol`
- `timestamp` / `time` / `date`
- `close`, with optional `high` and `low`

The filler uses the row's `trigger_observed_at` as the decision time and
`entry_reference_price` as the entry when present. It computes:

- `post_event_return_24h`
- `post_event_return_72h`
- `post_event_return_7d`
- `max_favorable_excursion`
- `max_adverse_excursion`

For event-fade shorts, negative post-event returns are favorable. MFE/MAE are
positive magnitudes over the 7-day post-trigger window. Existing outcome fields
are preserved unless `--event-fade-overwrite-outcomes` is supplied. The command
writes only `OUT` and remains artifact-only: no live storage, notifications,
paper trades, or execution.

## Validation Sample Labeling Queue

`main.py --event-fade-labeling-queue PATH` reads a JSONL/CSV validation sample
and prints the next rows that need human review. It is a read-only report; it
does not auto-label rows or write the sample.

Queue priority is:

1. unknown `human_label` values
2. reviewed rows with point-in-time evidence violations
3. unlabeled `SHORT_TRIGGERED` rows
4. reviewed `SHORT_TRIGGERED` rows missing required outcome fields:
   `max_adverse_excursion`, `max_favorable_excursion`, and
   `post_event_return_72h`
5. unlabeled proxy candidates
6. unlabeled direct/ambiguous negative controls

The report shows the event, asset, signal type, relationship, event time,
trigger time, missing fields, suggested label category, and source URLs. It is a
workflow aid for building the reviewed validation sample; it is not promotion
evidence by itself.

## Validation Sample Review

`main.py --event-fade-review-sample PATH` reads a labeled JSONL/CSV validation
sample and prints a research-only review report. It is intentionally
conservative: a report can say a sample is ready for a human decision, but it
does not promote event-fade output automatically.

The reviewer currently checks:

- reviewed rows vs unlabeled rows
- reviewed proxy candidate count against the 25-case minimum target
- reviewed direct/ambiguous control count against the 50-case minimum target
- label counts for `valid_proxy_fade`, `false_positive`, `direct_event`, and
  `ambiguous`
- reviewed `SHORT_TRIGGERED` count against the 10-trigger minimum target
- reviewed `SHORT_TRIGGERED` precision against the 60% minimum target and
  false-positive rate
- direct/non-proxy rows that somehow became `SHORT_TRIGGERED`
- point-in-time evidence violations where the source was first seen after the
  decision time
- average MFE, MAE, MFE/MAE ratio, and post-event 24h/72h/7d returns for
  reviewed triggered rows
- missing required outcome fields on reviewed triggered rows
- MFE/MAE ratio against the 1.5 minimum target

The command prints `BLOCKED` until coverage and outcome evidence are strong
enough. Even when it prints `READY FOR HUMAN DECISION`, the repo decision still
requires explicit human approval before any Telegram, paper-trading, storage,
or execution promotion.

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

Run the flat research radar with:

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

Run an opt-in live Bybit announcement radar pass:

```bash
RSI_EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE=1 \
RSI_EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_TYPE=new_crypto \
RSI_EVENT_DISCOVERY_UNIVERSE_PATH=fixtures/coingecko_smoke/top_markets.json \
  .venv/bin/python main.py --event-discovery-report
```

The live Bybit path is research-only and fail-soft. It should only add direct
exchange-listing/perp-listing evidence to the radar unless another source later
proves a proxy relationship.

Run an opt-in live CryptoPanic news radar pass:

```bash
RSI_EVENT_DISCOVERY_CRYPTOPANIC_LIVE=1 \
RSI_EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN=... \
RSI_EVENT_DISCOVERY_CRYPTOPANIC_SEARCH='pre-ipo OR synthetic exposure' \
RSI_EVENT_DISCOVERY_UNIVERSE_PATH=fixtures/coingecko_smoke/top_markets.json \
  .venv/bin/python main.py --event-discovery-report
```

The live CryptoPanic path fetches posts JSON only when a token is configured,
reuses the same news parser as fixtures, and remains research-only/fail-soft.

Run an opt-in live GDELT news radar pass:

```bash
RSI_EVENT_DISCOVERY_GDELT_LIVE=1 \
RSI_EVENT_DISCOVERY_GDELT_QUERY='("pre-ipo" OR "pre ipo" OR "synthetic exposure" OR "tokenized stock" OR "prediction market" OR "fan token")' \
RSI_EVENT_DISCOVERY_UNIVERSE_PATH=fixtures/coingecko_smoke/top_markets.json \
  .venv/bin/python main.py --event-discovery-report
```

The live GDELT path queries Article List JSON, reuses the same news parser as
fixtures, and remains research-only/fail-soft. It should add narrative evidence
for human review or local cache export, not route event-fade signals live.

Run an opt-in live project-blog/RSS radar pass:

```bash
RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE=1 \
RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS=https://example.test/feed.xml,https://example.test/atom.xml \
RSI_EVENT_DISCOVERY_UNIVERSE_PATH=fixtures/coingecko_smoke/top_markets.json \
  .venv/bin/python main.py --event-discovery-report
```

The live RSS path fetches only explicit feed URLs, parses RSS and Atom entries,
reuses the same news parser as fixtures, and remains research-only/fail-soft.

Write the local observational JSONL cache with the fixture set:

```bash
make event-discovery-refresh
```

For live Bybit research cache refreshes:

```bash
RSI_EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE=1 \
RSI_EVENT_DISCOVERY_UNIVERSE_PATH=fixtures/coingecko_smoke/top_markets.json \
  .venv/bin/python main.py --event-discovery-refresh
```

Run the grouped event-fade auto report with the same fixture set:

```bash
make event-fade-auto-report
```

Export the validation-sample rows with the same fixture set:

```bash
make event-fade-export-sample
EVENT_FADE_SAMPLE_OUT=/tmp/event_fade_validation_sample.csv make event-fade-export-sample
```

Export latest cached candidate snapshots into the validation-sample schema:

```bash
make event-fade-export-cache-sample
EVENT_DISCOVERY_CACHE_DIR=/path/to/event_fade_cache \
EVENT_FADE_SAMPLE_OUT=/tmp/event_fade_cached_sample.csv \
  make event-fade-export-cache-sample
```

Build a local price fixture for triggered validation rows:

```bash
make event-fade-export-outcome-prices
EVENT_FADE_SAMPLE_IN=/tmp/event_fade_cached_sample.jsonl \
EVENT_FADE_OUTCOME_PRICES_OUT=/tmp/event_fade_outcome_prices.json \
  make event-fade-export-outcome-prices
```

Fill triggered-row outcomes from local price candles:

```bash
make event-fade-fill-outcomes
EVENT_FADE_SAMPLE_IN=/tmp/event_fade_cached_sample.jsonl \
EVENT_FADE_OUTCOME_PRICES=/path/to/outcome_prices.json \
EVENT_FADE_SAMPLE_OUTCOMES=/tmp/event_fade_with_outcomes.jsonl \
  make event-fade-fill-outcomes
```

Review a labeled sample:

```bash
make event-fade-review-sample
EVENT_FADE_SAMPLE_IN=/path/to/labeled_sample.csv make event-fade-review-sample
```

Print a review queue for missing labels/outcomes:

```bash
make event-fade-labeling-queue
EVENT_FADE_SAMPLE_IN=/path/to/labeled_sample.csv EVENT_FADE_QUEUE_LIMIT=50 \
  make event-fade-labeling-queue
```

Preserve labels/outcomes across a refreshed export:

```bash
make event-fade-merge-sample
EVENT_FADE_SAMPLE_FRESH=/tmp/new_export.jsonl \
EVENT_FADE_SAMPLE_REVIEWED=/path/to/old_labeled_sample.csv \
EVENT_FADE_SAMPLE_MERGED=/tmp/merged_sample.jsonl \
  make event-fade-merge-sample
```

All outputs are local and observational. They do not send alerts or write the
live DB.

## Promotion Requirements

Do not route discovered event-fade candidates to Telegram or paper trading until
a reviewed event sample shows positive edge and acceptable false-positive rates.
The review report is evidence, not approval. First promotion, if approved later,
should still be notification-only.
