# Event Discovery Design

**Date:** 2026-06-16
**Status:** Phase 1-10 framework with clean CoinGecko universe bridge,
fixture-backed exchange announcement providers plus opt-in live Bybit
announcement fetch, structured calendar/unlock providers, news/proxy-narrative
providers plus opt-in live CryptoPanic posts, GDELT Article List, and
project-blog RSS/Atom fetches, external catalyst providers, and
Coinalyze-style derivatives plus opt-in live Coinalyze REST enrichment with
optional `future-markets` symbol auto-resolution,
Tokenomist/Etherscan/Arkham/Dune-style supply/on-chain enrichment, plus grouped
auto reporting and validation-sample exports, research-only JSONL cache refresh,
validation-sample review metrics, labeling-queue support, research-only merge
support, local outcome-price export, and outcome-fill support. Stabilization
rules now explicitly force `NO_TRADE` for weak classifier confidence, weak
event-time confidence, and proxy-venue rows by default, merge obvious duplicate
catalyst headlines, preserve transition timestamps in cached snapshots, and
record outcome price interval/source metadata.

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
- `event_providers/coingecko_universe.py`: CoinGecko market provider that
  reuses shared universe hygiene filters for local fixtures or opt-in live
  resolver enrichment
- `event_providers/binance_announcements.py`: local Binance announcement fixture
  provider for spot/listing-style direct events, including captured official CMS
  WebSocket `com_announcement_en` payloads and opt-in bounded live WebSocket
  fetches
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
  fixture provider plus opt-in live Polymarket Gamma event fetch for dated
  external attention/catalyst markets
- `derivatives_providers/coinalyze.py`: derivatives provider that maps
  Coinalyze-style OI/funding/crowding fixture rows or opt-in live Coinalyze REST
  snapshots to discovery candidates
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
project aliases, but they are high-confidence resolver evidence and must be
curated carefully. The runtime default alias file is
`event_discovery_aliases.json`, which starts empty. Fixture aliases live in
`fixtures/event_discovery/asset_aliases.json` and are explicitly injected by
fixture Make targets only; do not use them for real-source review cycles or they
will create fake `TEST*` candidates. `RSI_EVENT_DISCOVERY_UNIVERSE_PATH` can
additionally point to a CoinGecko-style market fixture, either a
`top_markets.json` file or a directory containing that file. The provider
applies `universe.filter_markets_with_audit` before producing `DiscoveredAsset`
rows, so stablecoins, wrapped/staked receipts,
synthetics, bad identity rows, and low-quality market rows are screened by the
same logic used by live scans and backtests.

For live research passes, `RSI_EVENT_DISCOVERY_UNIVERSE_LIVE=1` fetches a clean
CoinGecko universe through the existing rate-limited `CoinGeckoClient`, applies
the same hygiene filter, and uses the result only for asset resolution. It is not
an event source by itself, does not route alerts, and does not write live signal,
paper, or outcome tables. `RSI_EVENT_DISCOVERY_UNIVERSE_FETCH_LIMIT` can
override the overfetch count when a broader resolver universe is needed.

## Exchange Announcement Providers

Binance and Bybit announcement providers read local JSON fixtures by default.
Binance fixtures may be normalized listing-style rows or captured official CMS
WebSocket `DATA` messages from topic `com_announcement_en`; the latter stores
the announcement JSON string inside the `data` field with `catalogName`,
`publishDate`, `title`, and `body`.

Binance can also listen briefly to the official signed CMS WebSocket when
`RSI_EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE=1` and
`RSI_EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_KEY` /
`RSI_EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_SECRET` are set. The default
topic is `com_announcement_en`, the default URL is
`wss://api.binance.com/sapi/wss`, and
`RSI_EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LISTEN_SECONDS` controls the bounded
listen window used by report/refresh commands and by
`main.py --event-discovery-binance-listen`. The dedicated listen command writes
raw Binance announcement evidence to the observational JSONL cache. It is still
research-only; wrapping it in launchd/KeepAlive for continuous collection remains
an ops task, not a trading promotion.

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

When a proxy-style article has strong narrative evidence but no precise
`event_time`, it may remain in the validation sample as a `proxy_attention` row.
That is review evidence only: the pure event-fade engine still requires a known
event time before a candidate can become eligible or leave `NO_TRADE`. The news
parser infers only a small set of common external assets such as SpaceX, OpenAI,
Anthropic, Tesla, Nvidia, World Cup, Champions League, Iran, and US election.
The resolver also rejects common identity words observed in public feeds
(`cash`, `real`, `just`, `humanity`) so they do not become high-confidence
asset matches from normal prose.

After an article resolves to an asset, the classifier assigns an asset role:

- `proxy_instrument`: the token/instrument is explicitly framed as the proxy
  exposure asset.
- `proxy_venue`: the venue/platform token is explicitly tied to the proxy
  market narrative.
- `direct_beneficiary`: the event directly affects the token itself.
- `mentioned_asset`: the asset is background market/treasury context.
- `infrastructure`: the asset is the chain, network, or plumbing used by the
  proxy market.
- `ticker_word_collision`: a short ticker alias matched normal prose rather
  than the crypto ticker.

Only `proxy_instrument` and `proxy_venue` can remain `is_proxy_narrative=True`,
but they are not equal for trigger eligibility. `proxy_instrument` can trigger
only if all hard event-fade gates pass. `proxy_venue` is watchlist/review-only
by default and must force `NO_TRADE` unless
`RSI_EVENT_FADE_ALLOW_PROXY_VENUE_TRIGGER=1` is explicitly enabled after sample
review. `mentioned_asset`, `infrastructure`, and `ticker_word_collision` rows
are kept as `proxy_context` controls for review, but they cannot pass
event-fade eligibility.

The discovery orchestrator also applies explicit review-only gates before
emitting the event-fade signal:

- `classification.confidence < min_classifier_confidence`
- `event_time_confidence < min_event_time_confidence`
- `asset_role == proxy_venue` while venue triggers are disabled

Rows blocked this way still appear in reports and validation samples with a
`forced_no_trade_reason` in `data_quality`, but their signal is `NO_TRADE`.

## External Catalyst Providers

External IPO and sports-fixture providers currently read local JSON fixtures
only. The prediction-market provider can read local fixtures or, when explicitly
opted in, fetch no-key live Polymarket Gamma events. They turn non-crypto
catalysts into radar events:

- external IPO/calendar entries
- sports matches or fixtures
- prediction-market questions around dated external events

Run an opt-in live Polymarket catalyst pass:

```bash
RSI_EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE=1 \
RSI_EVENT_DISCOVERY_UNIVERSE_LIVE=1 \
RSI_EVENT_DISCOVERY_UNIVERSE_FETCH_LIMIT=250 \
  .venv/bin/python main.py --event-discovery-refresh
```

Or use the no-key Make convenience target:

```bash
make event-fade-polymarket-review-cycle
```

The live Polymarket path fetches Gamma events ordered by 24h volume, preserves
event end dates as `event_time`, and remains research-only/fail-soft. It is a
dated external-catalyst source, not a proxy classifier by itself.

External catalysts are radar-first. An external event by itself does not resolve
to a crypto asset and therefore cannot produce a fade candidate. A crypto
candidate appears only when the source text also contains asset-link evidence
such as a known token alias plus proxy narrative terms. Date-only catalyst rows
are preserved with lower `event_time_confidence` and should remain validation
sample evidence, not trade triggers.

## Derivatives Enrichment

The Coinalyze-style derivatives provider reads local JSON fixtures by default.
It can also fetch live Coinalyze REST snapshots when
`RSI_EVENT_DISCOVERY_COINALYZE_LIVE=1` and
`RSI_EVENT_DISCOVERY_COINALYZE_API_KEY` is set. Explicit
`RSI_EVENT_DISCOVERY_COINALYZE_SYMBOLS` such as `BTCUSDT_PERP.A` are used first.
If explicit symbols are omitted and
`RSI_EVENT_DISCOVERY_COINALYZE_AUTO_SYMBOLS=1`, the provider queries Coinalyze
`future-markets` and selects one preferred perp symbol for each already-resolved
discovery asset base. Live derivatives are enrichment only; enabling them
without an event source does not create discovery events.

The provider produces candidate enrichment keyed by coin id, symbol, base
symbol, or market symbol and fills `EventDerivativesSnapshot` fields used by
`event_fade.py`:

- perp availability
- open interest and 24h OI change
- OI-to-market-cap
- funding rate / percentile
- futures volume
- perp/spot volume ratio
- liquidations, long/short ratio, and basis

The live path uses Coinalyze's documented `future-markets`, `open-interest`,
`funding-rate`, `open-interest-history`, `liquidation-history`,
`long-short-ratio-history`, and `ohlcv-history` endpoints. Current OI/funding
fill the latest snapshot; 24h OI change, liquidations, long/short ratio, and
futures volume are derived from the configured historical lookback.

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

## Dedupe And Enrichment Selection

Discovery first merges exact duplicates by clean event name, event type, exact
event time, and external asset. It then applies a conservative canonical merge
for obvious headline variants using event type, external-asset slug, event-date
bucket, and normalized catalyst terms such as IPO, listing, unlock, ETF,
sports, political, or product launch. All raw ids, URLs, published/fetched
timestamps, titles, and content hashes stay attached for point-in-time review.

When a deduped event has several raw sources, candidate construction does not
blindly use the first payload. It selects the richest point-in-time-safe
market, derivatives, supply, RSI, and technical section for the resolved asset
across all raw ids. Raw evidence published or fetched after the decision time is
ignored for trigger-time enrichment so later articles cannot backfill a
pre-event signal.

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
`main.py --event-discovery-status` prints a redacted readiness report for event
sources and enrichment providers. Use it before a configured-source refresh; an
enrichment-only setup is not enough to build validation rows.
`make event-discovery-refresh` is fixture-backed for deterministic local smoke
work; `make event-discovery-refresh-configured` avoids Makefile fixture
injection and uses only sources configured through the environment/`.env`.
`main.py --event-discovery-binance-listen` appends raw Binance announcement rows
and a run row to the same cache without normalization, classification, alerts,
or paper trades.

Files:

- `raw_events.jsonl`
- `normalized_events.jsonl`
- `event_asset_links.jsonl`
- `classifications.jsonl`
- `candidate_snapshots.jsonl`
- `discovery_runs.jsonl`

Stable evidence files dedupe already-seen rows by source/event identity where
possible. `candidate_snapshots.jsonl` appends every refresh so later analysis
can inspect how scores and missing data looked at each observed time. Snapshot
rows also carry research-only transition timestamps by stable event/asset/
relationship identity: `first_seen_at`, `first_watchlisted_at`,
`first_armed_at`, `first_triggered_at`, and `last_seen_at`. These fields help
separate scan observation time from first trigger time in validation samples;
they are not live state and do not promote routing or paper trades.
`discovery_runs.jsonl` stores redacted provider-readiness diagnostics and
refresh warnings. Use those warnings to distinguish a healthy zero-result run
from a provider problem, rate limit, bad credential, too-narrow query/window, or
resolution/classification failure. `main.py --event-discovery-runs` prints the
recent run rows in a compact form, and `--json` returns the cached run payloads
for external review tooling.

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
  timestamps, including raw published/fetched arrays plus min/max timestamp
  summaries for point-in-time leakage review
- normalized event identity, event type, event time/confidence, first-seen time,
  and external asset
- resolved asset identity plus link confidence, match reason, and evidence
- proxy/direct classification, classifier version, confidence, reason, and
  evidence
- fade state, signal type, score, eligibility, reason codes, warnings,
  component scores, feature fields, and missing-data markers
- research cache transition fields such as `first_seen_at`,
  `first_watchlisted_at`, `first_armed_at`, `first_triggered_at`, and
  `last_seen_at` when exported from cache
- outcome price metadata fields `outcome_price_interval` and
  `outcome_price_source` after outcome filling
- blank human-review and future outcome columns such as `human_label`,
  `human_notes`, `max_adverse_excursion`, `max_favorable_excursion`, and
  trigger-time plus event-time-baseline post-event returns

This export may write only the requested local artifact. It must not write live
DB rows, send alerts, open paper trades, or imply execution.

## Validation Sample Merge

`main.py --event-fade-merge-sample FRESH REVIEWED OUT` preserves human work when
the discovery export is regenerated. It reads a fresh JSONL/CSV export and a
previously reviewed JSONL/CSV sample, matches rows by stable event id, asset id,
and relationship type, then copies nonblank review fields into the fresh rows
only when the validation evidence fingerprint is unchanged:

- `review_status`
- `human_label`
- `human_notes`
- `max_adverse_excursion`
- `max_favorable_excursion`
- `post_event_return_24h`
- `post_event_return_72h`
- `post_event_return_7d`

The merge writes only the requested `OUT` artifact and reports matched/unmatched
reviewed rows, evidence-changed matched rows, copied fields, and the affected
asset/event/relationship plus changed evidence field names. Evidence-changed rows
intentionally remain unreviewed so they return to the labeling queue instead of
carrying stale human labels or outcomes. The compact review-template apply path
performs the same check against the evidence fields present in the sidecar.
Neither command changes live storage, routing, paper trades, or event state.

## Validation Price Fixture Export

`main.py --event-fade-export-outcome-prices SAMPLE OUT` builds the local OHLCV
price fixture consumed by outcome filling. It reads `SHORT_TRIGGERED` rows from
a validation sample, infers each asset's Binance-style USDT pair from
`asset_symbol`, and writes a JSON artifact with candles:

- `asset_coin_id`
- `asset_symbol`
- `timestamp`
- `high`
- `low`
- `close`
- `volume`
- `quote_volume`
- `interval`

By default the command uses the existing Binance daily-kline fetch/cache path
from the research backtester (`--event-fade-price-interval 1d`). For intraday
review, use `--event-fade-price-interval 1h`; this uses Binance hourly klines
or a local fixture and records the selected interval/source in the price
artifact. For deterministic offline runs, pass
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

The filler uses the row's `trigger_observed_at` as the confirmed decision time
and `entry_reference_price` as the trigger entry when present. It also computes
an event-time short baseline from the row's `event_time` and the closest local
close at or before the event timestamp. When the price fixture includes source
metadata, the filler copies `outcome_price_interval` and `outcome_price_source`
into filled rows so review reports can distinguish coarse daily outcomes from
hourly/intraday validation. It computes:

- `post_event_return_24h`
- `post_event_return_72h`
- `post_event_return_7d`
- `max_favorable_excursion`
- `max_adverse_excursion`
- `event_time_entry_price`
- `event_time_post_event_return_24h`
- `event_time_post_event_return_72h`
- `event_time_post_event_return_7d`
- `event_time_max_favorable_excursion`
- `event_time_max_adverse_excursion`

For event-fade shorts, negative post-event returns are favorable. MFE/MAE are
positive magnitudes over the 7-day post-trigger or post-event baseline window.
Existing outcome fields are preserved unless `--event-fade-overwrite-outcomes`
is supplied. The command writes only `OUT` and remains artifact-only: no live
storage, notifications, paper trades, or execution.

## Validation Sample Labeling Queue

`main.py --event-fade-labeling-queue PATH` reads a JSONL/CSV validation sample
and prints the next rows that need human review status, labels, or outcomes. It
is a read-only report; it does not auto-label rows or write the sample.

Queue priority is:

1. unknown `human_label` values
2. rows marked `review_status=reviewed` but missing `human_label`
3. labeled rows missing `review_status=reviewed`
4. reviewed rows with point-in-time evidence violations
5. reviewed rows with any source evidence after the decision time
6. reviewed rows missing source timing evidence
7. unlabeled `SHORT_TRIGGERED` rows
8. reviewed `SHORT_TRIGGERED` rows missing required outcome fields:
   `max_adverse_excursion`, `max_favorable_excursion`, and
   `post_event_return_72h`
9. unlabeled proxy candidates
10. unlabeled direct/ambiguous negative controls

The report shows the event, asset, signal type, relationship, event time,
trigger time, missing fields, suggested label category, and source URLs. It is a
workflow aid for building the reviewed validation sample; it is not promotion
evidence by itself.

## Validation Review Packet

`main.py --event-fade-review-packet SAMPLE OUT` reads the same JSONL/CSV
validation sample as the queue and writes a Markdown packet for manual review.
It uses the queue priority order, then expands each selected row with:

- event, asset, relationship, proxy/direct classification, and timestamps
- source URLs, raw titles, classifier evidence, reason codes, warnings, and
  missing-data markers
- signal state, fade score, eligibility, trigger time, entry reference, and
  invalidation level
- trigger-time outcomes, event-time baseline outcome, and trigger-vs-baseline
  72h edge when those fields are already filled
- explicit `review_status`, `human_label`, and `human_notes` fields to fill in

The packet is a human workflow artifact only. It does not auto-label rows,
modify the source sample, write live storage, route alerts, open paper trades,
or imply promotion. After review status, labels, and outcomes are filled in the sample, use
`main.py --event-fade-review-sample PATH` to measure coverage, trigger quality,
and promotion blockers.

## Validation Review Template

`main.py --event-fade-export-review-template SAMPLE OUT` writes a compact
editable sidecar for the same prioritized rows used by the labeling queue and
review packet. A `.csv` suffix writes CSV; any other suffix writes JSONL. The
sidecar keeps stable identity/context fields plus editable review fields:

- `event_id`, `asset_coin_id`, `asset_symbol`, and `relationship_type`
- event/signal context, queue category, suggested label, missing fields, and
  source URLs
- raw/min/max source timestamps for point-in-time review
- `review_status`, `human_label`, `human_notes`
- `human_event_time`, `human_event_time_source`,
  `human_event_time_confidence`, and `human_event_time_notes` when the system
  missed or weakly inferred a catalyst time
- trigger-time and event-time-baseline outcome fields when they need manual
  override or preservation

After a human edits the sidecar, `main.py --event-fade-apply-review-template
SAMPLE TEMPLATE OUT` copies nonblank review fields back into a full validation
sample artifact and immediately prints the resulting review report and
next-sample work. Human event-time confirmation is stored separately from the
machine-extracted `event_time` so later analysis can distinguish what the system
knew from what the reviewer confirmed. When `human_event_time_confidence` meets
the review threshold, validation metrics may use `human_event_time` for
review-only decision timing, trigger latency, source-timing checks, and
event-time baseline outcome filling; it still does not prove the discovery
pipeline knew that event time automatically. A row only counts as reviewed
evidence when it has both
`review_status=reviewed` and a known `human_label`. The apply command uses stable
event/asset/relationship identity and writes only `OUT`; it does not infer
labels, alter the source sample, write live storage, route alerts, open paper
trades, or imply promotion.

## Validation Review Bundle

`main.py --event-fade-review-bundle SAMPLE OUT_DIR` writes a local manual-review
workspace for a validation sample. The bundle contains:

- `validation_sample.jsonl`: copied source sample
- `validation_sample_with_outcomes.jsonl`: optional outcome-filled sample when
  `--event-fade-review-bundle-prices PRICES` is supplied
- `outcome_prices.json`: optional bundle-local OHLCV fixture when
  `--event-fade-review-bundle-export-prices` is supplied and no explicit
  `--event-fade-review-bundle-prices` file is supplied
- `labeling_queue.txt`: prioritized rows needing review status, labels, or
  outcomes
- `review_packet.md`: human-readable evidence packet
- `review_template.csv`: compact editable sidecar
- `review_report.txt`: current metrics and promotion blockers
- `manifest.json`: machine-readable bundle provenance, file map, review counts,
  diversity/timing gate metrics, blockers, next-sample work, and optional
  outcome-fill stats
- `review_guide.md`: label taxonomy, proxy/direct criteria, review provenance,
  human event-time confirmation rules, outcome fields, and promotion reminder
- `README.md`: suggested manual workflow

The bundle is a convenience wrapper around existing artifact-only commands. It
does not infer labels, alter the source sample, write live storage, route
alerts, open paper trades, or imply promotion. If a local price fixture is
supplied, outcome filling is applied only to the bundle-local sample copy.
If `--event-fade-review-bundle-export-prices` is supplied without an explicit
price fixture, the bundle writes `outcome_prices.json` under `OUT_DIR` using the
same research-only Binance/fixture kline path as
`--event-fade-export-outcome-prices`, then fills outcomes from that local file.
If `--event-fade-review-bundle-reviewed REVIEWED_SAMPLE` is supplied, the
bundle first merges matching prior review fields into the bundle-local
`validation_sample.jsonl` using the same evidence-fingerprint guard as
`--event-fade-merge-sample`. The manifest records matched rows, copied fields,
evidence-changed rows, any skipped evidence-change details, review-gate metrics
such as proxy source-provider diversity and low-confidence trigger event times,
price-export counts, and outcome-fill counts. The README mirrors the core
coverage/diversity/timing gates so a local bundle is inspectable without opening
the full review report first.

`main.py --event-fade-cache-review-bundle OUT_DIR` writes the same workspace
directly from latest cached candidate snapshots under
`RSI_EVENT_DISCOVERY_CACHE_DIR`. This is the preferred review handoff after
running `main.py --event-discovery-refresh`, because it avoids the extra
export-sample step and keeps the review bundle tied to the point-in-time cache.
It writes only under `OUT_DIR`. If the cache has no candidate snapshots, the
CLI output, README, and manifest warn that no validation rows were produced and
point the operator back to provider readiness, live-source warnings/rate limits,
and a refreshed event source.

`make event-fade-review-cycle` runs the fixture-backed cache refresh and then
writes the cache-backed review bundle using the same `EVENT_DISCOVERY_CACHE_DIR`.
Set `EVENT_FADE_REVIEW_BUNDLE_REVIEWED=/path/to/previous_reviewed_sample.jsonl`
to preserve valid prior human review work during the refresh.

`make event-fade-configured-review-cycle` runs the same cache-backed review
bundle workflow, but starts with `make event-discovery-refresh-configured`. Use
it when the goal is to collect review candidates from the research sources
enabled in `.env` or the shell, such as opt-in live announcement/news/RSS/
derivatives providers. It still writes only the observational cache and review
bundle artifacts.

## Validation Sample Review

`main.py --event-fade-review-sample PATH` reads a labeled JSONL/CSV validation
sample and prints a research-only review report. It is intentionally
conservative: a report can say a sample is ready for a human decision, but it
does not promote event-fade output automatically.

The reviewer currently checks:

- reviewed rows vs unreviewed/incomplete rows
- labeled rows missing `review_status=reviewed`, and rows marked reviewed but
  missing `human_label`
- reviewed proxy candidate count against the 25-case minimum target
- reviewed direct/ambiguous control count against the 50-case minimum target
- label counts for `valid_proxy_fade`, `false_positive`, `direct_event`, and
  `ambiguous`
- reviewed `SHORT_TRIGGERED` count against the 10-trigger minimum target
- reviewed `SHORT_TRIGGERED` precision against the 60% minimum target and
  false-positive rate
- reviewed proxy event-type diversity against the two-event-type minimum target
- reviewed proxy source-provider diversity against the two-provider minimum
  target, so a sample dominated by one RSS/feed/API source cannot look
  promotion-ready by itself
- reviewed proxy source-origin diversity as reporting context, derived from
  source URL domains and Google News publisher suffixes, so reviewers can see
  whether an RSS batch has one publisher or several independent publishers
- reviewed trigger BTC risk-bucket diversity against the two-bucket minimum
  target
- direct/non-proxy rows that somehow became `SHORT_TRIGGERED`
- point-in-time evidence violations where the source was first seen after the
  decision time
- reviewed rows with any source evidence published/fetched after the decision
  time, even if another source for the same event was available earlier
- decision time is `trigger_observed_at` for reviewed `SHORT_TRIGGERED` rows and
  `event_time` for other reviewed dated rows, including direct/ambiguous controls
- reviewed rows with no source timing evidence, which must be removed or given
  auditable timing before they count toward promotion evidence
- trigger latency from event time to `SHORT_TRIGGERED`, including negative
  latencies that imply invalid state progression
- average MFE, MAE, MFE/MAE ratio, and post-event 24h/72h/7d returns for
  reviewed triggered rows
- event-time short baseline 72h return and trigger-vs-baseline 72h edge
- missing required outcome fields on reviewed triggered rows
- missing event-time baseline fields on reviewed triggered rows
- MFE/MAE ratio against the 1.5 minimum target
- cohort summaries by event type, relationship type, asset role, event-time
  source, source provider, source origin, and BTC risk-on bucket so the reviewed
  sample can expose where the edge is concentrated or absent

The report also prints a `NEXT SAMPLE WORK` section that translates blockers
into concrete work: how many more proxy candidates, direct/ambiguous controls,
and reviewed `SHORT_TRIGGERED` rows are needed, which rows still need explicit
review status or labels, which unsafe or missing point-in-time rows need
review/removal, and which triggered rows still need trigger or event-time
baseline outcomes, stronger event-time confirmation, or proxy examples from
additional source providers.

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
`fixtures/event_discovery/asset_aliases.json` cover deterministic test assets
only:

- TESTVELVET + SpaceX IPO proxy article
- TESTBTC + BTC ETF direct-beneficiary article
- TESTTOKEN + Binance listing direct event
- TESTPUMP ambiguous pump with no dated catalyst
- COLLIDE ticker collision that must not resolve confidently
- TESTLIST Binance spot-listing announcement fixture
- TESTLIVE captured Binance CMS WebSocket announcement payload fixture shape
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

Run an opt-in live Binance/Bybit announcement radar pass:

```bash
RSI_EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE=1 \
RSI_EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_KEY=... \
RSI_EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_SECRET=... \
RSI_EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LISTEN_SECONDS=10 \
RSI_EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE=1 \
RSI_EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_TYPE=new_crypto \
RSI_EVENT_DISCOVERY_UNIVERSE_LIVE=1 \
  .venv/bin/python main.py --event-discovery-report
```

The live Binance, Bybit, and CoinGecko universe paths are research-only and
fail-soft. They should only add direct exchange-listing/perp-listing evidence
and resolver coverage to the radar unless another source later
proves a proxy relationship.

Listen for raw Binance WebSocket announcements and cache source evidence:

```bash
RSI_EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE=1 \
RSI_EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_KEY=... \
RSI_EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_SECRET=... \
RSI_EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LISTEN_SECONDS=300 \
  .venv/bin/python main.py --event-discovery-binance-listen
```

This command writes only `raw_events.jsonl` and `discovery_runs.jsonl` rows. Use
`--event-discovery-refresh` or validation-sample exports for normalized
candidate snapshots.

Add opt-in live Coinalyze derivatives enrichment to a radar pass with explicit
symbols:

```bash
RSI_EVENT_DISCOVERY_EVENTS_PATH=fixtures/event_discovery/raw_events.json \
RSI_EVENT_DISCOVERY_COINALYZE_LIVE=1 \
RSI_EVENT_DISCOVERY_COINALYZE_API_KEY=... \
RSI_EVENT_DISCOVERY_COINALYZE_SYMBOLS=BTCUSDT_PERP.A,ETHUSDT_PERP.A \
  .venv/bin/python main.py --event-discovery-report
```

Live Coinalyze is enrichment only. It cannot create events by itself and must
not bypass proxy/direct eligibility.

Or let the provider resolve preferred Coinalyze perp symbols from already-linked
discovery assets:

```bash
RSI_EVENT_DISCOVERY_EVENTS_PATH=fixtures/event_discovery/raw_events.json \
RSI_EVENT_DISCOVERY_COINALYZE_LIVE=1 \
RSI_EVENT_DISCOVERY_COINALYZE_API_KEY=... \
RSI_EVENT_DISCOVERY_COINALYZE_AUTO_SYMBOLS=1 \
  .venv/bin/python main.py --event-discovery-report
```

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

Use the no-key Make convenience target when building a cache-backed review
workspace from GDELT:

```bash
EVENT_DISCOVERY_CACHE_DIR=event_fade_cache \
EVENT_FADE_CACHE_REVIEW_BUNDLE_DIR=/tmp/event_fade_gdelt_bundle \
EVENT_FADE_REVIEW_BUNDLE_EXPORT_PRICES=1 \
EVENT_FADE_QUEUE_LIMIT=50 \
  make event-fade-gdelt-review-cycle
```

This target enables `RSI_EVENT_DISCOVERY_GDELT_LIVE=1`, uses the configured
proxy-narrative query, sets a 30-day lookback, and enables broader live
CoinGecko universe enrichment by default. GDELT rows remain source evidence for
manual review; they cannot bypass asset-resolution, proxy/direct, event-time, or
post-event failure gates.

Run an opt-in live project-blog/RSS radar pass:

```bash
RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE=1 \
RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS=https://example.test/feed.xml,https://example.test/atom.xml \
RSI_EVENT_DISCOVERY_UNIVERSE_PATH=fixtures/coingecko_smoke/top_markets.json \
  .venv/bin/python main.py --event-discovery-report
```

The live RSS path fetches only explicit feed URLs, parses RSS and Atom entries,
reuses the same news parser as fixtures, and remains research-only/fail-soft.
The shared news parser may infer a lower-confidence `event_time` only from
explicit source-text date phrases such as "by June 20, 2026" or "on
2026-06-20"; it must not use publication time as the catalyst time. Rows without
that explicit date evidence remain `proxy_attention` and `NO_TRADE`. Inferred
dates are exported with `event_time_source=text_date` and reduced
`event_time_confidence`; fade-candidate confidence is capped by that
event-time confidence so low-confidence text dates cannot satisfy the
event-fade confidence gate by themselves. Validation review reports cohort rows
by `event_time_source` and block promotion if reviewed `SHORT_TRIGGERED` rows
have event-time confidence below the review threshold; text-date rows are leads
until a stronger source confirms the catalyst time.
For a newline-separated URL list, set
`RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS_PATH`. The checked-in no-key starter
list is `fixtures/event_discovery/public_rss_feeds.txt`; it includes broad
crypto publisher feeds plus targeted Google News RSS searches for pre-IPO,
tokenized-stock, synthetic-exposure, fan-token, prediction-market, sports, and
political proxy narratives. The searches intentionally bias toward dated
proxy-instrument leads because broad feeds mostly produce generic BTC controls.
Use it for local research cache collection, then inspect and label the resulting
bundle before any conclusion-bearing review.

Refresh the no-key public RSS source bundle and write a cache-backed review
workspace in one step:

```bash
make event-fade-public-rss-review-cycle
EVENT_DISCOVERY_CACHE_DIR=event_fade_cache \
EVENT_FADE_CACHE_REVIEW_BUNDLE_DIR=/tmp/event_fade_public_rss_bundle \
EVENT_FADE_REVIEW_BUNDLE_EXPORT_PRICES=1 \
EVENT_FADE_QUEUE_LIMIT=50 \
  make event-fade-public-rss-review-cycle
```

This target enables `RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE=1`, points
`RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS_PATH` at the checked-in public feed
list, sets a 30-day lookback, and enables broader live CoinGecko universe
enrichment by default so real article mentions can resolve beyond the fixture
aliases. Public RSS rows now include asset-role metadata, conservative
source-text date inference, and event-time source/confidence provenance in
validation exports and review packets so reviewers can separate actual dated
proxy instruments/venues from lower-confidence text-date rows, undated
attention, background mentions, infrastructure rows, and ticker-word collisions.
Provider/network failures remain warnings in `discovery_runs.jsonl`.

The live Polymarket cycle is complementary to public RSS and GDELT: it can
produce dated external-catalyst/control rows even when news rows are undated, but
current public Polymarket data may still resolve mostly ambiguous controls.
Treat that as useful negative-control evidence, not proof of a proxy-fade edge.

For a mixed no-key review bundle, run public RSS, GDELT, and Polymarket into the
same cache and write one review workspace:

```bash
EVENT_DISCOVERY_CACHE_DIR=event_fade_cache \
EVENT_FADE_CACHE_REVIEW_BUNDLE_DIR=/tmp/event_fade_no_key_bundle \
EVENT_FADE_REVIEW_BUNDLE_EXPORT_PRICES=1 \
EVENT_FADE_QUEUE_LIMIT=50 \
  make event-fade-no-key-review-cycle
```

This is the preferred no-key sample-expansion command because the resulting
bundle can contain RSS/GDELT proxy-attention or source-text-dated proxy rows
plus Polymarket dated external-catalyst controls.

Validation review reports include asset-role, source-provider, and source-origin
cohorts alongside event-type, relationship, event-time-source, and BTC-risk
cohorts. Use the asset-role section to verify that reviewed proxy rows are not
dominated by `mentioned_asset`, `infrastructure`, or `ticker_word_collision`
controls, use the source-provider section to verify that proxy evidence is not
all from one feed/API family, use the source-origin section to inspect actual
publisher/domain concentration inside RSS and Google News rows, and use the
event-time-source section to verify that triggered evidence is not dominated by
lower-confidence `text_date` rows before treating the sample as promotion
evidence.

Labeling queues, review packets, and review templates surface the same
event-time source/confidence and derived source-origin/publisher context.
Reviewed `SHORT_TRIGGERED` rows with low event-time confidence return to the
queue as `confirm_trigger_event_time` even if labels and outcomes are already
filled, and same-priority review rows are ordered so explicit, high-confidence
event times come before weaker source-text dates or missing times.

Review bundles also write a compact sample summary into `manifest.json` and
`README.md`: event types, relationship types, asset roles, signal types, source
providers, source origins, proxy candidate count, proxy-context control count,
direct beneficiary count, SHORT_TRIGGERED count, missing-event-time count,
per-source provider quality counts, and per-source origin quality counts. This
is the fastest way to sanity-check a fresh RSS/GDELT/Polymarket bundle before
filling the sidecar labels.
The bundle-level `review_guide.md` makes the manual review artifact
self-contained: it defines the four accepted labels, proxy/direct criteria,
review provenance fields (`reviewed_by` and `reviewed_at`), human event-time
confirmation fields, required trigger outcomes, and the promotion reminder.

Inspect configured provider readiness without printing secrets:

```bash
make event-discovery-status
.venv/bin/python main.py --event-discovery-status --json
make event-discovery-runs
.venv/bin/python main.py --event-discovery-runs --json
make event-discovery-refresh-public-rss
```

The status report separates event sources from enrichment. At least one event
source must be ready before `make event-fade-configured-review-cycle` can
produce review rows; universe, derivatives, or supply enrichment alone cannot
create events. The runs report is the post-refresh view: use it to inspect
whether recent configured runs produced candidates or only warnings.

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

By default this uses the research Binance daily-kline fetch/cache path. For
hourly outcome fixtures, add `EVENT_FADE_PRICE_INTERVAL=1h`. For
offline smoke work, set
`EVENT_FADE_PRICE_FIXTURE_DIR=fixtures/event_discovery/outcome_klines`.

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

Print a review queue for missing review status, labels, or outcomes:

```bash
make event-fade-labeling-queue
EVENT_FADE_SAMPLE_IN=/path/to/labeled_sample.csv EVENT_FADE_QUEUE_LIMIT=50 \
  make event-fade-labeling-queue
```

Write a Markdown packet for manual review:

```bash
make event-fade-review-packet
EVENT_FADE_SAMPLE_IN=/path/to/labeled_sample.csv \
EVENT_FADE_REVIEW_PACKET_OUT=/tmp/event_fade_review_packet.md \
EVENT_FADE_QUEUE_LIMIT=50 \
  make event-fade-review-packet
```

Write and apply a compact editable review sidecar:

```bash
make event-fade-export-review-template
EVENT_FADE_SAMPLE_IN=/path/to/sample.jsonl \
EVENT_FADE_REVIEW_TEMPLATE_OUT=/tmp/event_fade_review_template.csv \
EVENT_FADE_QUEUE_LIMIT=50 \
  make event-fade-export-review-template

make event-fade-apply-review-template
EVENT_FADE_SAMPLE_IN=/path/to/sample.jsonl \
EVENT_FADE_REVIEW_TEMPLATE=/tmp/event_fade_review_template.csv \
EVENT_FADE_SAMPLE_REVIEW_APPLIED=/tmp/event_fade_reviewed.jsonl \
  make event-fade-apply-review-template
```

Write a local review workspace:

```bash
make event-fade-review-bundle
EVENT_FADE_SAMPLE_IN=/path/to/sample.jsonl \
EVENT_FADE_REVIEW_BUNDLE_DIR=/tmp/event_fade_review_bundle \
EVENT_FADE_REVIEW_BUNDLE_EXPORT_PRICES=1 \
EVENT_FADE_QUEUE_LIMIT=50 \
  make event-fade-review-bundle
```

For an offline bundle smoke, add
`EVENT_FADE_PRICE_FIXTURE_DIR=fixtures/event_discovery/outcome_klines`; otherwise
auto-exported bundle prices use the research Binance daily-kline fetch/cache
path. Add `EVENT_FADE_PRICE_INTERVAL=1h` when a review bundle should export
hourly candles for intraday MFE/MAE checks.

Write a local review workspace from the latest research cache:

```bash
make event-fade-cache-review-bundle
EVENT_DISCOVERY_CACHE_DIR=event_fade_cache \
EVENT_FADE_CACHE_REVIEW_BUNDLE_DIR=/tmp/event_fade_cache_review_bundle \
EVENT_FADE_REVIEW_BUNDLE_EXPORT_PRICES=1 \
EVENT_FADE_QUEUE_LIMIT=50 \
  make event-fade-cache-review-bundle
```

Refresh the fixture-backed research cache and write the review bundle in one
step:

```bash
make event-fade-review-cycle
EVENT_DISCOVERY_CACHE_DIR=event_fade_cache \
EVENT_FADE_CACHE_REVIEW_BUNDLE_DIR=/tmp/event_fade_cache_review_bundle \
EVENT_FADE_REVIEW_BUNDLE_EXPORT_PRICES=1 \
EVENT_FADE_REVIEW_BUNDLE_REVIEWED=/path/to/previous_reviewed_sample.jsonl \
EVENT_FADE_QUEUE_LIMIT=50 \
  make event-fade-review-cycle
```

Refresh configured research sources and write the review bundle in one step:

```bash
make event-fade-configured-review-cycle
EVENT_DISCOVERY_CACHE_DIR=event_fade_cache \
EVENT_FADE_CACHE_REVIEW_BUNDLE_DIR=/tmp/event_fade_cache_review_bundle \
EVENT_FADE_REVIEW_BUNDLE_EXPORT_PRICES=1 \
EVENT_FADE_REVIEW_BUNDLE_REVIEWED=/path/to/previous_reviewed_sample.jsonl \
EVENT_FADE_QUEUE_LIMIT=50 \
  make event-fade-configured-review-cycle
```

This target intentionally does not set fixture paths. Configure providers with
`RSI_EVENT_DISCOVERY_*` environment variables or `.env` first.

Preserve review status/labels/outcomes across a refreshed export:

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
