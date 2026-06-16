# DEVLOG — change history

This project now has **local git** for diffs/rollback, while this file remains
the human-readable narrative history. **Newest entries at the top**, just under
this header. Append (prepend) one entry per non-trivial change. Keep it skimmable;
deep reasoning can link to code. See `AGENTS.md` for the working agreement.

### Entry template (copy this)

```
## YYYY-MM-DD — <short title> · <Claude|Codex|human>
**Why:** one or two sentences of motivation.
**Changes:** bullet list, with file references.
**Verify:** what you ran and the result (tests, dry-run, backtest…).
**Notes/risks:** anything the next agent should know. Optional.
```

---

## 2026-06-16 — Require explicit reviewed status for event-fade samples · Codex
**Why:** The validation reviewer counted any row with a `human_label` as
reviewed evidence. That made half-edited sidecars risky: a label without an
explicit review status could accidentally contribute to promotion metrics.
**Changes:**
- Tightened `crypto_rsi_scanner/event_validation.py` so review evidence requires
  both `review_status=reviewed` and a known `human_label`.
- Added review metrics, blockers, queue categories, and next-step text for
  labels missing review status, reviewed rows missing labels, and invalid label
  values.
- Updated queue/report/CLI wording to say status/labels/outcomes rather than
  labels/outcomes only.
- Added regression coverage for invalid labels, missing review status, and
  reviewed rows missing labels.
- Fixed a date-sensitive event-discovery fixture report test by pinning its
  lookback/horizon window.
- Updated `AGENTS.md`, `ROADMAP.md`, and `research/event_discovery_design.md`
  with the stricter reviewed-row definition.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 215/215.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** Older samples still load, but rows with labels and no
`review_status=reviewed` no longer count as reviewed evidence. They now appear
in the labeling queue and promotion blockers.

## 2026-06-16 — Add event-fade validation next-step checklist · Codex
**Why:** The event-fade validation report listed blockers, but the next action
still had to be inferred by a human or the next agent. The remaining Pro-plan
work is sample building, so the report should say exactly which coverage,
outcome, or point-in-time rows need attention next.
**Changes:**
- Added `validation_review_next_steps()` and a `NEXT SAMPLE WORK` section to
  `crypto_rsi_scanner/event_validation.py`, translating review metrics into
  concrete sample-building actions.
- Updated `main.py --event-fade-review-sample` help text to mention next-sample
  work.
- Expanded validation tests to cover blocked/unlabeled samples, promotion-ready
  samples, and mixed post-decision source evidence.
- Fixed the event-discovery design note's labeling-queue priority list to
  include post-decision source review, and updated `AGENTS.md`/`ROADMAP.md`.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 214/214.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** This is reporting-only. It does not auto-label rows, infer
promotion readiness, route alerts, write live storage, open paper trades, or
change event-fade scoring.

## 2026-06-16 — Harden event-fade point-in-time source audits · Codex
**Why:** The validation sample tracked earliest source timestamps, but a
multi-source event could still mix one pre-decision source with another
post-decision source. The Pro plan explicitly requires point-in-time evidence,
so reviewed samples need to expose and block this leakage risk.
**Changes:**
- Extended `crypto_rsi_scanner/event_discovery.py` validation rows with
  `raw_published_at`, `raw_fetched_at`, `published_at_max`, and
  `fetched_at_max` in addition to existing min timestamps.
- Added `post_decision_source_rows` to
  `crypto_rsi_scanner/event_validation.py`; review reports now count/block
  reviewed rows containing any source evidence after the decision time.
- The labeling queue now prioritizes reviewed rows that need post-decision
  source review, and review packets/templates show min/max/raw source timing.
- Added tests for raw timestamp export, clean reviewed samples, all-late
  evidence, and mixed early/late source evidence.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` with the source-leakage guardrail.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 214/214.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** This is an additive validation-sample/schema change under the
same v1 artifact family; older samples without max/raw timestamp fields still
load, but new exports are more auditable.

## 2026-06-16 — Add event-fade review bundle workspace · Codex
**Why:** The validation workflow had all the individual pieces, but building a
human-review workspace still required several commands in the right order. A
single bundle command makes the reviewed event dataset easier to assemble
without changing live behavior.
**Changes:**
- Added `main.py --event-fade-review-bundle SAMPLE OUT_DIR`, which writes a
  local review workspace with `validation_sample.jsonl`, optional
  `validation_sample_with_outcomes.jsonl`, `labeling_queue.txt`,
  `review_packet.md`, `review_template.csv`, `review_report.txt`, and
  `README.md`.
- Added optional `--event-fade-review-bundle-prices PRICES` to fill trigger and
  event-time baseline outcomes into the bundle-local sample copy.
- Added `make event-fade-review-bundle` and top-level usage text.
- Added an offline scanner regression test that verifies the bundle files and
  outcome-filled sample contents.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` with the review-bundle workflow and
  artifact-only guardrails.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 213/213.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard. `.venv/bin/python main.py --help` exposes the new
bundle command.
**Notes/risks:** The bundle does not infer labels, write live storage, route
alerts, open paper trades, or imply event-fade promotion. The actual validation
sample still needs human labels and real local price outcomes.

## 2026-06-16 — Add event-fade review sidecar workflow · Codex
**Why:** Review packets make candidate evidence readable, but a human still had
to edit the full validation export to apply labels. A compact sidecar makes
human labeling safer and easier while preserving the full sample artifact.
**Changes:**
- Added compact event-fade review-template rows in
  `crypto_rsi_scanner/event_validation.py`, with stable event/asset/relationship
  identity, queue context, suggested labels, source URLs, and editable
  review/outcome fields.
- Added `main.py --event-fade-export-review-template SAMPLE OUT` and
  `main.py --event-fade-apply-review-template SAMPLE TEMPLATE OUT`; both are
  artifact-only and never infer labels or touch live storage.
- Added `make event-fade-export-review-template` and
  `make event-fade-apply-review-template`, plus top-level usage text.
- Added offline tests for sidecar export/load/apply and scanner command paths.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` with the sidecar workflow and guardrails.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 212/212.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard. `.venv/bin/python main.py --help` exposes the new
commands.
**Notes/risks:** The actual event-fade sample still needs human labels and real
local price outcomes before any promotion beyond local reports.

## 2026-06-16 — Add event-fade review packet export · Codex
**Why:** The validation sample now has queue/review metrics, but manual labeling
still required jumping between source evidence, classifier rationale, signal
fields, and outcome columns. A Markdown packet makes the reviewed event dataset
easier to build without changing live behavior.
**Changes:**
- Added `event_validation.format_review_packet()` to render prioritized
  validation rows with source URLs, raw titles, classifier evidence,
  signal/risk fields, trigger/event-time outcomes, and explicit human review
  fields.
- Added `main.py --event-fade-review-packet SAMPLE OUT` plus
  `make event-fade-review-packet`; the command writes only the requested
  Markdown artifact or stdout.
- Added offline tests for the pure formatter and scanner write path in
  `tests/test_indicators.py`.
- Updated `AGENTS.md`, `ROADMAP.md`, and `research/event_discovery_design.md`
  to document the packet workflow and artifact-only guardrail.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 210/210.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** This is a human-review workflow artifact only. It does not
auto-label rows, modify samples, write live storage, route alerts, open paper
trades, or imply event-fade promotion.

## 2026-06-16 — Add event-fade validation diversity and latency gates · Codex
**Why:** The event-fade promotion plan requires evidence across more than one
event type and market context, plus trigger-latency visibility. The reviewer
showed cohorts, but it did not block too-narrow samples or report how long
post-event confirmation took.
**Changes:**
- Extended `crypto_rsi_scanner/event_validation.py` with reviewed proxy
  event-type diversity, reviewed trigger BTC-risk-bucket diversity, and
  trigger-latency metrics.
- `--event-fade-review-sample` now reports average/median trigger latency,
  negative trigger-latency rows, proxy event-type coverage, and trigger BTC-risk
  bucket coverage.
- Promotion evidence is now blocked when a fully covered sample is still
  concentrated in too few proxy event types or too few BTC-risk buckets, or when
  reviewed triggers occur before their event time.
- Added regression tests in `tests/test_indicators.py` for the new diversity
  blockers and latency report fields.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` to document latency/diversity review
  gates.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 208/208.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** These are validation gates only. They do not promote
event-fade, write live storage, route alerts, or open paper trades.

## 2026-06-16 — Compare event-fade triggers to event-time shorts · Codex
**Why:** The event-fade plan explicitly requires proving that waiting for
post-event failure beats simply shorting at the event timestamp. The validation
sample could fill trigger outcomes, but it had no event-time baseline to make
that comparison reviewable.
**Changes:**
- Added additive validation-sample fields for event-time baseline entry price,
  MFE/MAE, and 24h/72h/7d post-event returns in
  `crypto_rsi_scanner/event_discovery.py`.
- Extended `crypto_rsi_scanner/event_validation.py` so
  `fill_validation_outcomes()` fills both confirmed-trigger outcomes and the
  event-time short baseline from local OHLCV candles.
- The validation review now reports event-time baseline 72h return,
  trigger-vs-baseline 72h edge, missing baseline fields, and blocks promotion
  evidence when reviewed triggers lack a baseline or fail to beat it.
- Updated validation labeling queues so triggered rows missing the event-time
  baseline stay prioritized for outcome filling.
- Expanded fixture prices and tests in `tests/test_indicators.py` to prove the
  trigger-vs-event-time comparison and scanner price-export path.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` to document the trigger/baseline
  validation workflow.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 207/207.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** This remains artifact-only validation. It does not promote
event-fade alerts, write live storage, open paper trades, or approve routing.

## 2026-06-16 — Add event-fade validation cohort review metrics · Codex
**Why:** The event-fade plan requires proving whether the edge survives by
event type and market context, not just in aggregate. The validation reviewer
only reported top-line trigger/outcome metrics, so it could miss a sample whose
edge is concentrated in one event class or BTC risk bucket.
**Changes:**
- Extended `crypto_rsi_scanner/event_validation.py` with validation cohort
  summaries by event type, relationship type, and BTC risk-on bucket.
- The `--event-fade-review-sample` report now prints cohort rows with reviewed
  counts, proxy/control coverage, reviewed triggers, trigger precision, MFE/MAE,
  and 72h post-event return.
- Added tests in `tests/test_indicators.py` proving cohort calculations and
  formatted report output on the fixture validation sample.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` to document cohort evidence as
  research-only validation review output.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 207/207.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** Cohorts are evidence only. They do not relax promotion
blockers, route alerts, write live storage, open paper trades, or approve
event-fade promotion automatically.

## 2026-06-16 — Auto-resolve live Coinalyze derivatives symbols · Codex
**Why:** Live Coinalyze derivatives enrichment still required hand-written
future-market symbols, which made the event radar harder to run on newly
discovered assets. The safer default is to resolve preferred Coinalyze perp
symbols from assets the discovery pipeline has already linked, while keeping
explicit symbols as the override path.
**Changes:**
- Extended `crypto_rsi_scanner/derivatives_providers/coinalyze.py` with
  `future-markets` symbol resolution. Explicit
  `RSI_EVENT_DISCOVERY_COINALYZE_SYMBOLS` still wins; otherwise the provider can
  select one preferred perp market per requested base asset.
- Moved discovery-asset loading ahead of derivatives enrichment in
  `crypto_rsi_scanner/event_discovery.py` so live Coinalyze can derive base
  symbols from resolved assets and aliases.
- Added `RSI_EVENT_DISCOVERY_COINALYZE_AUTO_SYMBOLS` config and `.env.example`
  documentation, wired through the scanner report path.
- Added offline tests for future-market resolution preference, automatic base
  symbol extraction from discovery assets, exchange-suffix symbols, zero-value
  snapshot preservation, and the live provider fail-soft path.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` to document the auto-symbol path as
  research-only enrichment.
**Verify:** `make verify` passes: 207/207 tests, alert render smoke, backtest
fixture smoke, and paper scoreboard.
**Notes/risks:** Live Coinalyze is still enrichment only. It cannot create
events, route alerts, write live signal/outcome/paper tables, or bypass the
event-fade proxy/direct eligibility gate.

## 2026-06-16 — Add opt-in live Coinalyze derivatives enrichment · Codex
**Why:** The event-fade plan depends on derivatives crowding evidence, but
Coinalyze enrichment was fixture-only. Research radar runs need an opt-in live
path for OI/funding/crowding snapshots without turning derivatives into event
eligibility or live routing.
**Changes:**
- Extended `crypto_rsi_scanner/derivatives_providers/coinalyze.py` with an
  opt-in live REST path using configured Coinalyze symbols and API key. It
  fetches current OI/funding plus OI history, liquidations, long/short ratio,
  and futures volume history over a configurable lookback.
- Preserved legitimate zero values in the derivatives snapshot mapper and fixed
  Coinalyze exchange-suffix symbols such as `TESTUSDT_PERP.A` so they key by
  base asset correctly.
- Added `RSI_EVENT_DISCOVERY_COINALYZE_*` config and `.env.example` settings,
  wired through `event_discovery.py` and `scanner.py`.
- Added offline tests for documented Coinalyze current/history response shapes,
  symbol batching headers/params, missing-config fail-soft behavior, and live
  snapshot field derivation.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` to document live Coinalyze as
  research-only enrichment.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 205/205.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** Live Coinalyze requires explicit symbols such as
`BTCUSDT_PERP.A`; it does not discover events by itself and must not bypass the
proxy/direct event-fade eligibility gate.

## 2026-06-16 — Add raw Binance announcement cache listener · Codex
**Why:** Binance announcements are a push WebSocket feed, so report/refresh
bounded fetches can miss source evidence between runs. The event-discovery plan
needs point-in-time raw event evidence preserved before any classification or
promotion work.
**Changes:**
- Added `main.py --event-discovery-binance-listen`, which uses the configured
  signed Binance CMS WebSocket provider and appends raw announcement evidence to
  the existing research-only JSONL cache.
- Added `make event-discovery-binance-listen` and documented the command in
  `main.py`, `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md`.
- The listener writes only `raw_events.jsonl` and `discovery_runs.jsonl` rows
  via the existing cache writer. It does not normalize events, route alerts,
  write live SQLite signal/outcome/paper tables, or open paper trades.
- Added a scanner-level regression test that stubs the Binance provider and
  verifies raw cache rows plus run metadata are written.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 203/203.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** Continuous collection still needs an ops wrapper such as a
LaunchAgent/KeepAlive job. This command is the safe research capture primitive,
not a trading promotion.

## 2026-06-16 — Add opt-in live Binance announcement discovery · Codex
**Why:** The radar could parse captured Binance CMS announcement payloads, but
it still could not ingest Binance's official signed WebSocket feed during
research refresh/report runs. The Pro-plan exchange-provider phase calls for
automatic discovery from exchange announcements while preserving the proxy gate.
**Changes:**
- Extended `crypto_rsi_scanner/event_providers/binance_announcements.py` with an
  opt-in bounded live WebSocket fetch path for Binance CMS announcements. It
  signs the `com_announcement_en` subscription URL, uses the API key header,
  listens for a configurable short window, and reuses the same CMS DATA parser
  as fixtures.
- Added config and `.env.example` knobs for live Binance announcement research:
  API key/secret, WebSocket URL, topic, recv window, listen seconds, and max
  messages.
- Wired the live Binance source through `event_discovery.py` and `scanner.py`,
  including source-detection for report/refresh commands.
- Added offline WebSocket tests covering signed URL/header construction, control
  frame tolerance, CMS DATA parsing, and missing-credential fail-soft behavior.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` to document the signed, opt-in,
  research-only Binance path and keep always-on caching as future work.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 202/202.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** This is a bounded report/refresh fetch, not an always-on
listener. Binance listing/perp announcements remain direct events and stay
`NO_TRADE` under the event-fade proxy gate unless another source proves a true
proxy relationship.

## 2026-06-16 — Add opt-in live CoinGecko discovery universe · Codex
**Why:** Event discovery had live news/exchange inputs, but asset resolution
still depended on local universe fixtures. Live research passes need the same
clean CoinGecko universe hygiene used by the scanner, without making the
universe itself an event source or promoting event-fade output.
**Changes:**
- Added `RSI_EVENT_DISCOVERY_UNIVERSE_LIVE` and
  `RSI_EVENT_DISCOVERY_UNIVERSE_FETCH_LIMIT` config/env examples, wired through
  `scanner.py` and `event_discovery.run_manual_discovery()`.
- Extended `crypto_rsi_scanner/event_providers/coingecko_universe.py` so it can
  optionally fetch live top markets through the existing `CoinGeckoClient`, apply
  `universe.filter_markets_with_audit`, and fail soft on provider errors.
- Added offline tests with injected fake CoinGecko clients for live fetch,
  hygiene filtering, overfetch limits, and fail-soft behavior.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` to mark live CoinGecko as resolver
  enrichment only: research-only, opt-in, no alert routing, no live DB writes,
  no paper trades.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 200/200.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** Enabling `RSI_EVENT_DISCOVERY_UNIVERSE_LIVE=1` alone does not
create radar events; another event source or fixture must be configured.

## 2026-06-16 — Parse Binance CMS announcement payloads · Codex
**Why:** Binance's official English announcement stream publishes CMS WebSocket
`DATA` messages where the announcement content is a JSON string inside the
`data` field. The existing Binance fixture parser only handled already-flattened
announcement rows, so captured official payloads could not feed the
event-discovery radar.
**Changes:**
- Extended `crypto_rsi_scanner/event_providers/_announcement_common.py` to unwrap
  Binance CMS `DATA` messages, preserve `topic`/`message_type`, parse
  `publishDate` timestamps, and feed the nested announcement through the same
  direct listing/perp classification path as other announcement fixtures.
- Added a regression test using the official `com_announcement_en` payload shape
  with stringified `data`.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` to record captured Binance CMS payload
  support and keep the boundary clear: a true live Binance WebSocket
  listener/cache adapter is still future work.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 198/198.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** This is parser support for official captured payloads, not a
new live listener. It preserves the research-only event-discovery boundary and
does not route alerts, write live signal/outcome/paper tables, or promote
event-fade signals.

## 2026-06-16 — Add opt-in live CryptoPanic discovery · Codex
**Why:** The event-fade validation pipeline needs more real news coverage for
proxy/direct/ambiguous narrative review. CryptoPanic was fixture-only; an
explicit, token-gated live path can feed research reports and cache exports
without changing live alert behavior.
**Changes:**
- Extended `crypto_rsi_scanner/event_providers/cryptopanic.py` from
  fixture-only to optional live posts fetching with API-token config, public/
  filter/currency/region/kind/search parameters, injected opener support, and
  fail-soft behavior.
- Wired `RSI_EVENT_DISCOVERY_CRYPTOPANIC_*` config through `config.py`,
  `event_discovery.py`, and `scanner.py`; scanner no-source messages now refer
  to generic live research providers instead of only Bybit.
- Added `.env.example` entries for the CryptoPanic live path.
- Added offline tests for request parameters, response parsing, missing-token
  behavior, and fetch failure handling.
- Updated `AGENTS.md`, `ROADMAP.md`, and `research/event_discovery_design.md`
  to record CryptoPanic as an opt-in live research source.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 197/197.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** Live CryptoPanic fetching is opt-in and requires
`RSI_EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN`. It feeds local reports/cache/export
paths only; it does not route Telegram alerts, write live signal/outcome/paper
tables, open paper trades, or promote event-fade signals.

## 2026-06-16 — Add opt-in live project-blog RSS discovery · Codex
**Why:** The event-fade validation sample needs broader real narrative coverage,
especially project-sourced posts that may announce synthetic/proxy exposure or
dated catalysts. RSS/Atom feeds are a no-key source that can safely feed the
research-only event radar.
**Changes:**
- Extended `crypto_rsi_scanner/event_providers/project_blog_rss.py` from
  fixture-only to optional live RSS/Atom fetching from explicit feed URLs, with
  injected opener support, deterministic fetched timestamps for tests, and
  fail-soft per-feed behavior.
- Added RSS item and Atom entry parsing into the existing news-row pipeline so
  live feed entries reuse the same event-type inference, point-in-time
  timestamps, and proxy/direct no-trade safety rules as fixtures.
- Added RFC 2822/RSS date parsing in
  `crypto_rsi_scanner/event_providers/_news_common.py`.
- Wired `RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE`,
  `RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS`, and timeout config through
  `config.py`, `event_discovery.py`, and `scanner.py`.
- Updated `.env.example`, `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md`; cleaned inline comments from
  `.env.example` value lines so copying the file cannot create invalid env
  values under the repo's minimal dotenv loader.
- Added offline tests for RSS and Atom parsing, RFC date handling, request
  timeout/headers, and fail-soft feed errors.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 196/196.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** Live RSS is opt-in and research-only. It only feeds local
reports/cache/export paths and does not route Telegram alerts, write live
signal/outcome/paper tables, open paper trades, or promote event-fade signals.

## 2026-06-16 — Add opt-in live GDELT event discovery · Codex
**Why:** The event-fade validation pipeline needs more real narrative/event
coverage, but live discovery sources must remain research-only and fail-soft.
GDELT is a useful no-key news source for proxy-catalyst radar coverage.
**Changes:**
- Extended `crypto_rsi_scanner/event_providers/gdelt.py` from fixture-only to
  optional live GDELT Article List JSON fetching with request-time bounds,
  configurable query/max-records/timeout, injected opener support for tests,
  and fail-soft behavior.
- Added shared news-row conversion and compact `YYYYMMDDHHMMSS` timestamp
  parsing in `crypto_rsi_scanner/event_providers/_news_common.py`.
- Wired `RSI_EVENT_DISCOVERY_GDELT_LIVE`, query, max-record, timeout, and base
  URL settings through `config.py`, `event_discovery.py`, and `scanner.py`.
- Added offline provider regression coverage for GDELT request parameters,
  compact timestamp parsing, empty responses, and fetch failures.
- Updated `.env.example`, `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md`; also moved live-provider comments in
  `.env.example` off value lines so the minimal dotenv loader cannot treat them
  as truthy values.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 195/195.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** GDELT live fetching is opt-in and research-only. It feeds local
reports/cache/export paths only; it does not route Telegram alerts, write live
signal/outcome/paper tables, open paper trades, or promote event-fade signals.

## 2026-06-16 — Export validation price fixtures from sample rows · Codex
**Why:** Outcome filling could consume local price JSON, but building that JSON
still required hand-writing candles. The validation workflow needs a
research-only path from a sample's triggered rows to local OHLCV fixtures before
human review.
**Changes:**
- Added `crypto_rsi_scanner/event_price_history.py` to export local
  `event_fade_outcome_prices_v1` JSON for `SHORT_TRIGGERED` validation rows,
  using either Binance-style fixture CSVs or the existing cached Binance kline
  fetch path.
- Added `main.py --event-fade-export-outcome-prices SAMPLE OUT`, optional
  fixture/price-days/cache-refresh flags, and
  `make event-fade-export-outcome-prices`.
- Extended shared Binance kline DataFrames with `high` and `low`, and taught
  fixture CSV loading to preserve optional `high`, `low`, and `quote_volume`.
- Added checked-in offline kline fixture
  `fixtures/event_discovery/outcome_klines/TESTVELVETUSDT.csv`.
- Added tests for high/low kline preservation, pure price-fixture export,
  scanner CLI export, and export-prices → fill-outcomes integration.
- Updated `AGENTS.md`, `ROADMAP.md`, `main.py`, and
  `research/event_discovery_design.md` with the price-export workflow.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 194/194.
Offline workflow smoke passes:
`make event-fade-export-sample` → `make event-fade-export-outcome-prices` →
`make event-fade-fill-outcomes` → `make event-fade-labeling-queue` →
`make event-fade-review-sample`. Generated price export reports
`assets=1/1` and `price_rows=4`.
**Notes/risks:** The new export command is research-only and artifact-only. It
may fetch Binance daily klines only when run without a fixture directory; it
does not write live scanner storage, route alerts, open paper trades, or imply
event-fade promotion.

## 2026-06-16 — Add validation outcome filling from local prices · Codex
**Why:** Event-fade validation samples had blank outcome fields, and the review
tool correctly blocked reviewed triggered rows without MFE/MAE and 72h
post-event returns. The workflow needed an artifact-only way to fill those
fields from local price histories before human review.
**Changes:**
- Added `event_validation.load_outcome_price_fixture()` and
  `fill_validation_outcomes()` to fill `SHORT_TRIGGERED` sample rows from local
  OHLCV candles while preserving existing fields unless overwrite is requested.
- Added `main.py --event-fade-fill-outcomes SAMPLE PRICES OUT` plus
  `make event-fade-fill-outcomes`.
- Added `fixtures/event_discovery/outcome_prices.json` for offline regression
  coverage of the TESTVELVET short outcome path.
- Added tests for outcome math, skipped-existing behavior, labeling-queue
  interaction, and scanner CLI file output.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` with the outcome-fill workflow.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 192/192.
Offline workflow smoke passes:
`make event-fade-export-sample` → `make event-fade-fill-outcomes` →
`make event-fade-labeling-queue` → `make event-fade-review-sample`. After
filling, the triggered row only needs `human_label`; the review remains blocked
on missing human labels/sample coverage.
**Notes/risks:** This is artifact-only validation tooling. It writes only the
requested output sample and does not write live SQLite signal/outcome/paper
tables, send notifications, open paper trades, or imply promotion.

## 2026-06-16 — Export validation samples from event-discovery cache · Codex
**Why:** The event-fade validation workflow could write point-in-time cache
snapshots, but review artifacts still had to be generated from the current
discovery run. Cached live/refreshed observations need a direct path into the
same human-review sample schema.
**Changes:**
- Added `event_cache.load_cached_validation_sample()` to unwrap
  `candidate_snapshots.jsonl` into normal `event_fade_validation_sample_v1`
  rows and keep only the latest snapshot per event/asset/relationship identity
  by default.
- Added `main.py --event-fade-export-cache-sample PATH` and
  `make event-fade-export-cache-sample` to export cached snapshots as JSONL/CSV
  validation samples.
- Added regression tests for cache snapshot unwrapping, latest-row dedupe, and
  scanner CLI export from a refreshed temp cache.
- Updated `AGENTS.md`, `ROADMAP.md`, `DECISIONS.md`, and
  `research/event_discovery_design.md` with the cached-sample workflow and
  research-only guardrails.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 190/190.
Temp-cache workflow smoke passes:
`make event-discovery-refresh` → `make event-fade-export-cache-sample` →
`make event-fade-review-sample`, with the review correctly blocked because rows
are not human-labeled yet.
**Notes/risks:** This only writes the requested local sample artifact. It does
not write live SQLite signal/outcome/paper tables, send notifications, open
paper trades, or imply event-fade promotion.

## 2026-06-16 — Add event-discovery JSONL cache refresh · Codex
**Why:** Live/refreshed event sources need point-in-time preservation before
they can support manual validation or backtests. `RSI_EVENT_DISCOVERY_CACHE_DIR`
already existed and was gitignored, but nothing wrote the observational cache.
**Changes:**
- Added `crypto_rsi_scanner/event_cache.py`, a research-only JSONL cache writer
  for raw events, normalized events, asset links, classifications, candidate
  snapshots, and discovery-run metadata.
- Added `main.py --event-discovery-refresh` and
  `make event-discovery-refresh`, wired through the existing discovery source
  configuration and `RSI_EVENT_DISCOVERY_CACHE_DIR`.
- Candidate snapshots reuse the validation-sample row builder so cache exports
  and human-review exports stay aligned.
- Added offline tests for cache artifact contents, point-in-time timestamps,
  dedupe of stable evidence rows, candidate snapshot appends, and scanner CLI
  cache refresh output.
- Updated `.env.example`, `AGENTS.md`, `ROADMAP.md`, `DECISIONS.md`, and
  `research/event_discovery_design.md` with the cache workflow and guardrails.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 189/189.
`RSI_EVENT_DISCOVERY_CACHE_DIR=$(mktemp -d)/cache make event-discovery-refresh`
writes the expected research cache summary. `git diff --check` passes.
`make verify` passes.
**Notes/risks:** This is observational research storage only. It writes JSONL
artifacts under the configured cache directory, not live SQLite signal/outcome/
paper tables, notifications, paper trades, or execution paths.

## 2026-06-16 — Add opt-in live Bybit announcement discovery · Codex
**Why:** The Pro plan's event radar should eventually discover exchange events
automatically, but the repo only had fixture-backed announcement parsing. Bybit
has an official unauthenticated announcements endpoint that can be used as a
safe first live source for research-only radar/export runs.
**Changes:**
- Extended the Bybit announcement provider with explicit opt-in live fetching
  from `GET /v5/announcements/index`, while keeping fixture mode as the default.
- Added Bybit live config knobs:
  `RSI_EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE`,
  `RSI_EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_BASE_URL`,
  `RSI_EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LOCALE`,
  `RSI_EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_TYPE`,
  `RSI_EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIMIT`, and
  `RSI_EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_TIMEOUT`.
- Taught the shared announcement parser to understand Bybit's documented
  `dateTimestamp`, `startDateTimestamp`, and `startDataTimestamp` fields.
- Wired the opt-in live provider through discovery reports/exports, updated
  `.env.example`, `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md`.
- Added an offline fake-HTTP regression test for the documented Bybit response
  shape, URL construction, timestamp parsing, listing normalization, and
  fail-soft behavior.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 187/187.
An opt-in live smoke with `RSI_EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE=1`
exits cleanly and prints an empty report after Bybit returns HTTP 403 in this
environment. `git diff --check` passes. `make verify` passes.
**Notes/risks:** Live Bybit fetch is default-off and research-only. Bybit
listings/perp listings are direct exchange events and remain `NO_TRADE` unless
separate evidence proves a true proxy relationship.

## 2026-06-16 — Add event-fade validation labeling queue · Codex
**Why:** The event-fade validation workflow could export, merge, and review
samples, but it did not tell a reviewer which rows to label next or which
triggered rows were missing required outcome fields.
**Changes:**
- Added `event_validation.build_labeling_queue()` and
  `format_labeling_queue()` to prioritize unknown labels, point-in-time issues,
  unlabeled triggered rows, triggered rows missing required outcomes, proxy
  candidates, and direct/ambiguous controls.
- Added `main.py --event-fade-labeling-queue PATH` plus
  `make event-fade-labeling-queue`, controlled by `EVENT_FADE_SAMPLE_IN` and
  `EVENT_FADE_QUEUE_LIMIT`.
- Added offline tests for pure queue priority, reviewed-trigger outcome gaps,
  and scanner CLI output.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` with the queue command and artifact-only
  guardrails.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 186/186.
`make event-fade-export-sample ... && make event-fade-labeling-queue ...`
prints the expected prioritized queue. `git diff --check` passes.
`make verify` passes.
**Notes/risks:** This is a read-only sample review aid. It does not auto-label
rows, write live storage, route alerts, open paper trades, or imply promotion.

## 2026-06-16 — Add event-fade validation sample merge workflow · Codex
**Why:** A reviewed validation sample will need repeated fresh exports as event
fixtures expand, and prior human labels/outcomes should not be lost or manually
retyped.
**Changes:**
- Added `event_validation.merge_review_fields()` to copy nonblank review fields
  from a previously labeled sample into a fresh export by event/asset/
  relationship identity.
- Added `main.py --event-fade-merge-sample FRESH REVIEWED OUT` and
  `make event-fade-merge-sample`, with separate fresh/reviewed/merged path
  variables.
- Added offline tests for direct merge behavior and scanner CLI file output.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` with the export → merge → label → review
  workflow and artifact-only guardrails.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 183/183.
`git diff --check` passes. `make verify` passes.
**Notes/risks:** Merge copies only nonblank human review/outcome fields and only
writes the requested output artifact. It does not write live storage, route
alerts, open paper trades, or imply execution.

## 2026-06-16 — Harden event-fade validation promotion blockers · Codex
**Why:** The review command summarized labels/outcomes, but it could still mark
a tiny or point-in-time-invalid sample as ready if thresholds were lowered. The
Pro plan explicitly requires point-in-time correctness and stronger evidence
before any promotion discussion.
**Changes:**
- Strengthened `event_validation.review_validation_sample()` with default
  blockers for fewer than 10 reviewed `SHORT_TRIGGERED` rows, trigger precision
  below 60%, MFE/MAE below 1.5, and source evidence first seen after the
  decision time.
- The review report now prints reviewed trigger minimums, minimum precision,
  point-in-time violation counts, and minimum MFE/MAE.
- Added a regression test proving a bad labeled trigger is blocked for late
  evidence, false-positive label, weak MFE/MAE, and unfavorable 72h short
  return.
- Updated `AGENTS.md` and `research/event_discovery_design.md` with the stricter
  review criteria.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 181/181.
`git diff --check` passes. `make verify` passes.
**Notes/risks:** This still only affects local validation review. It does not
route alerts, write live storage, open paper trades, or imply execution.

## 2026-06-16 — Add event-fade validation review metrics · Codex
**Why:** The validation exporter produced review artifacts, but the plan also
needs a way to evaluate labeled samples against promotion criteria before any
alert or paper-trading discussion.
**Changes:**
- Added `crypto_rsi_scanner/event_validation.py` to load JSONL/CSV validation
  samples, summarize labels/outcomes, compute trigger precision, false-positive
  rate, MFE/MAE, post-event returns, and emit conservative promotion blockers.
- Added `main.py --event-fade-review-sample PATH` and
  `make event-fade-review-sample`; the Make target reads
  `EVENT_FADE_SAMPLE_IN` so hand-labeled files are not overwritten by export.
- Added offline tests for unlabeled exports, labeled metric summaries, JSONL/CSV
  loading, and scanner CLI plumbing.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` with the export → label → review workflow
  and the non-promotion guardrail.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 180/180.
`make event-fade-export-sample && make event-fade-review-sample` reads the
17-row blank export and correctly prints `BLOCKED` for missing reviewed proxy,
control, and triggered samples. `git diff --check` passes. `make verify` passes.
**Notes/risks:** The reviewer is evidence only. Even a clean report says
`READY FOR HUMAN DECISION`; it does not change routing, storage, paper trading,
or execution behavior.

## 2026-06-16 — Add event-fade validation sample export · Codex
**Why:** Phase 10 needed a concrete review artifact so discovered event-fade
candidates can become a manually labeled validation sample without promoting
the research sleeve into alerts, paper trades, DB writes, or execution.
**Changes:**
- Added a versioned event-fade validation sample schema in
  `crypto_rsi_scanner/event_discovery.py` with JSONL/CSV serializers and a
  writer.
- Export rows now preserve raw source ids/providers/titles/content hashes,
  point-in-time event/source timestamps, source URLs, asset-link evidence,
  proxy/direct classification evidence, fade state/signal, component scores,
  feature fields, missing-data markers, and blank human-review/outcome columns.
- Added `main.py --event-fade-export-sample PATH`; `.csv` writes CSV, other
  suffixes write JSONL, and `-` prints JSONL to stdout.
- Added `make event-fade-export-sample`, defaulting to
  `/tmp/event_fade_validation_sample.jsonl`, using the full offline discovery
  fixture stack.
- Added offline tests for validation rows, JSONL/CSV serialization, file
  writing, and scanner CLI plumbing.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` with Phase 10 status and the remaining
  human-labeling boundary.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 177/177.
`make event-fade-export-sample` writes 17 rows to
`/tmp/event_fade_validation_sample.jsonl`. `git diff --check` passes.
`make verify` passes.
**Notes/risks:** This is still fixture-backed and local-only. The exporter writes
only the requested artifact; it does not write live signal/outcome/paper tables,
send Telegram alerts, open paper trades, or imply execution. The next real step
is expanding the reviewed sample and filling human labels/outcomes.

## 2026-06-16 — Add grouped event-fade auto report · Codex
**Why:** The discovery pipeline had a flat radar/classification report, but the
Phase 9 work order called for a clearer event-fade output grouped by candidate
lifecycle before building the validation sample.
**Changes:**
- Added `event_discovery.format_event_fade_auto_report()` with EVENT RADAR,
  PROXY WATCHLIST, BLOWOFF RISK, EVENT PASSED, ARMED, TRIGGERED,
  REJECTED / NO TRADE, and AMBIGUOUS sections.
- Candidate rows now surface symbol/coin id, event timing, first-seen time,
  link/classifier confidence, relationship type, fade score, state/signal,
  missing data, reason codes, warnings, source URLs, and invalidation when
  available.
- Added `main.py --event-fade-auto-report` and `make event-fade-auto-report`;
  both reuse the existing fixture-only discovery inputs and do not write DB
  rows, send notifications, open paper trades, or imply execution.
- Shared scanner discovery fixture loading between the flat radar report and the
  grouped auto report so provider wiring cannot drift.
- Made Makefile discovery fixture reports deterministic with a 120-hour
  lookback and 2-day horizon.
- Expanded offline tests for grouped section output and scanner CLI plumbing.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` with Phase 9 status and guardrails.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 175/175.
`make event-fade-auto-report` prints the grouped research-only report with
TESTVELVET under TRIGGERED, TESTAI under BLOWOFF RISK, TESTPRED under PROXY
WATCHLIST, direct cases under REJECTED / NO TRADE, and ambiguous cases under
AMBIGUOUS. `git diff --check` passes. `make verify` passes.
**Notes/risks:** Still fixture-backed and local-only. This is a reporting
surface for validation work, not a live routing, paper-trading, storage, or
execution path.

## 2026-06-16 — Add fixture supply/on-chain enrichment for event discovery · Codex
**Why:** The event-fade radar needs local supply and on-chain pressure evidence
before validation-sample work, but those fields must remain research-only
evidence and must not bypass the proxy/direct hard gate.
**Changes:**
- Added fixture-backed Tokenomist-, Etherscan-, Arkham-, and Dune-style supply
  providers under `supply_providers/`.
- Added optional config/report paths:
  `RSI_EVENT_DISCOVERY_TOKENOMIST_SUPPLY_PATH`,
  `RSI_EVENT_DISCOVERY_ETHERSCAN_SUPPLY_PATH`,
  `RSI_EVENT_DISCOVERY_ARKHAM_SUPPLY_PATH`, and
  `RSI_EVENT_DISCOVERY_DUNE_SUPPLY_PATH`.
- Wired supply snapshots into `event_discovery.run_manual_discovery()`,
  `main.py --event-discovery-report`, and `make event-discovery-report`; the
  report now prints `supply=yes/no` alongside derivatives coverage.
- Added fixtures covering unlock pressure, CEX inflow, team/MM wallet activity,
  holder concentration, admin/mint risk, and a conflicting TESTVELVET provider
  row that proves raw event fixture supply evidence wins.
- Expanded offline tests for supply fixture parsing, malformed fixture fail-soft
  behavior, supply enrichment, raw-evidence precedence, scanner report wiring,
  direct/non-proxy safety, and preserving explicit `0` / `False` supply values.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` with Phase 8 status and guardrails.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 173/173.
`make event-discovery-report` prints 20 raw events / 19 normalized events and
shows supply-enriched TESTLIST/TESTUNLOCK/TESTAI/TESTPRED/TESTFAN candidates
while direct listing/unlock cases remain `NO_TRADE`. `git diff --check` passes.
`make verify` passes.
**Notes/risks:** Providers remain fixture-backed only. No live Tokenomist,
Etherscan, Arkham, Dune, cache, DB, notification, paper-trading, or execution
path was added.

## 2026-06-16 — Add fixture external catalyst providers · Codex
**Why:** The event-fade radar needs external catalysts outside crypto, such as
IPO calendars, sports fixtures, and prediction markets, but those sources must
stay radar-first and must not create candidates without crypto asset evidence.
Phase 7 adds that fixture-only layer.
**Changes:**
- Added fixture-backed external IPO, sports-fixture, and prediction-market event
  providers over a shared external-catalyst parser.
- Added optional config/report paths:
  `RSI_EVENT_DISCOVERY_EXTERNAL_IPO_PATH`,
  `RSI_EVENT_DISCOVERY_SPORTS_FIXTURES_PATH`, and
  `RSI_EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH`.
- Added fixtures for a SpaceX IPO date-only radar event, a clean Test FC sports
  fixture, a linked TESTFAN sports proxy fixture, a linked TESTPRED/OpenAI
  prediction-market catalyst, and an election prediction market with no crypto
  asset evidence.
- Expanded aliases for TESTPRED and wired the external fixtures into
  `make event-discovery-report`.
- Added offline tests for provider parsing, malformed fixture fail-soft
  behavior, external-only radar/no-candidate safety, linked proxy candidates,
  date-only event-time confidence, and scanner report wiring.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` with Phase 7 status and guardrails.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 170/170.
`make event-discovery-report` prints external IPO/sports/prediction events while
external-only rows remain radar-only and linked rows stay non-executing local
report candidates. `git diff --check` passes. `make verify` passes.
**Notes/risks:** Providers remain fixture-backed only. No live IPO, sports,
prediction-market, cache, DB, notification, paper-trading, or execution path was
added.

## 2026-06-16 — Add fixture news/proxy narrative discovery · Codex
**Why:** The event-fade radar needs narrative/news sources to discover
VELVET-style proxy setups, not only structured crypto calendars and exchange
announcements. Phase 6 adds offline news fixtures while preserving the
research-only/no-routing boundary.
**Changes:**
- Added fixture-backed CryptoPanic-, GDELT-, and project-blog/RSS-style news
  providers over a shared news parser that accepts common API-like shapes such
  as `results`, `features`, and `items`.
- Added optional config/report paths:
  `RSI_EVENT_DISCOVERY_CRYPTOPANIC_PATH`, `RSI_EVENT_DISCOVERY_GDELT_PATH`, and
  `RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH`.
- Added fixtures for TESTAI/OpenAI proxy exposure, TESTBTC/BTC ETF direct
  beneficiary news, TESTFAN sports/fan-token proxy attention, TESTLATE
  post-event proxy evidence, and TESTAMBIG ambiguous momentum news.
- Expanded aliases for the new news fixture assets.
- Tightened deterministic classification so `etf_approval` and `etf_launch`
  event types classify as direct token events even when article wording is not
  exactly "ETF approval".
- Expanded offline tests for news provider parsing, malformed fixture fail-soft
  behavior, proxy/direct/ambiguous classification, post-event first-seen safety,
  deterministic fixed-time trigger behavior, and scanner report wiring.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` with Phase 6 status and guardrails.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 167/167.
`make event-discovery-report` prints 15 raw events / 14 normalized events with
TESTAI, TESTFAN, TESTLATE, and TESTAMBIG included; direct/ambiguous/late cases
remain `NO_TRADE`. `git diff --check` passes. `make verify` passes.
**Notes/risks:** Providers remain fixture-backed only. No live CryptoPanic,
GDELT, RSS, cache, DB, notification, paper-trading, or execution path was added.

## 2026-06-16 — Add fixture derivatives enrichment for event discovery · Codex
**Why:** Event-fade validation needs crowding evidence, not just dated events.
Phase 5 adds local Coinalyze-style derivatives snapshots so the research radar
can score OI/funding/perp crowding while staying offline and alert-only.
**Changes:**
- Added `derivatives_providers/` with a fixture-backed
  `CoinalyzeDerivativesProvider` for OI, funding, futures volume,
  perp/spot-volume ratio, liquidations, long/short ratio, and basis snapshots.
- Added `RSI_EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH` and wired optional
  derivatives enrichment through `event_discovery.run_manual_discovery()` and
  `main.py --event-discovery-report`.
- Added `fixtures/event_discovery/coinalyze_derivatives.json` covering high
  TESTLIST crowding, TESTPERP no-perp availability, and a conflicting
  TESTVELVET row that proves raw event fixture derivatives take precedence.
- The discovery report now prints candidate fade score and `deriv=yes/no` so
  enrichment is visible from local reports.
- Hardened derivatives symbol normalization so coin symbols ending in `PERP`
  are not over-stripped into false resolver keys.
- Expanded offline tests for derivatives fixture parsing, malformed fixture
  fail-soft behavior, candidate enrichment, raw-snapshot precedence, direct
  listing/no-trade safety under high crowding, and scanner report plumbing.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` with the Phase 5 status and guardrails.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 164/164.
`make event-discovery-report` prints TESTLIST and TESTPERP with `deriv=yes` but
both still `NO_TRADE/DISCOVERED`; TESTVELVET remains the only proxy trigger
fixture. `git diff --check` passes. `make verify` passes.
**Notes/risks:** This is still fixture-backed research tooling only. No live
Coinalyze calls, cache writes, live DB writes, notifications, paper trades, or
execution were added.

## 2026-06-16 — Add fixture structured calendar and unlock providers · Codex
**Why:** The event-fade validation sample needs more dated direct/control
events, including crypto calendar catalysts and supply unlocks, before any proxy
fade result can be trusted. Phase 4 adds those sources as offline fixtures only.
**Changes:**
- Added fixture-backed `CoinMarketCalProvider` for structured dated crypto
  calendar events and `TokenomistProvider` for token unlock events.
- Added `fixtures/event_discovery/coinmarketcal_events.json` and
  `fixtures/event_discovery/tokenomist_unlocks.json`, plus TESTCAL and
  TESTUNLOCK alias rows.
- Wired optional config/report paths:
  `RSI_EVENT_DISCOVERY_COINMARKETCAL_PATH` and
  `RSI_EVENT_DISCOVERY_TOKENOMIST_PATH`.
- Tokenomist unlock fixtures now populate `supply.unlock_amount` and
  `supply.unlock_pct_circulating` on the generated `FadeCandidate`, while still
  classifying as direct unlocks that remain `NO_TRADE`.
- Expanded offline tests for structured provider parsing, malformed fixture
  fail-soft behavior, structured-only scanner reports, direct/no-trade calendar
  behavior, and unlock supply enrichment.
- Updated `AGENTS.md`, `ROADMAP.md`, and `research/event_discovery_design.md`
  with the Phase 4 structured calendar/unlock status and guardrails.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 161/161.
`make event-discovery-report` prints TESTCAL as direct protocol upgrade and
TESTUNLOCK as direct unlock, both `NO_TRADE/DISCOVERED`. `make verify` passes.
**Notes/risks:** Providers remain fixture-backed only. No live API calls, cache
writes, live DB writes, notifications, paper trades, or execution were added.

## 2026-06-16 — Add fixture-backed exchange announcement providers · Codex
**Why:** The event radar needs direct exchange events in the dataset so proxy
fades can be tested against realistic negative/control cases. Phase 3 adds
exchange announcement parsing without enabling live network sources.
**Changes:**
- Added fixture-backed `BinanceAnnouncementProvider` and
  `BybitAnnouncementProvider`, plus shared announcement parsing helpers for
  spot/listing and perpetual/futures listing events.
- Added Binance and Bybit announcement fixtures covering TESTLIST spot listing
  and TESTPERP perp listing, plus alias entries for both assets.
- Event discovery can now combine manual raw-event fixtures, Binance
  announcements, Bybit announcements, and the cleaned CoinGecko universe fixture
  in one research-only report.
- Added optional config paths:
  `RSI_EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH` and
  `RSI_EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH`.
- Added offline tests for fixture parsing, malformed-provider fail-soft
  behavior, exchange-only scanner reports, and direct/no-trade safety for
  listing/perp events.
- Updated `AGENTS.md`, `ROADMAP.md`, and `research/event_discovery_design.md`
  with the Phase 3 exchange-provider status and guardrails.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 158/158.
`make event-discovery-report` prints TESTLIST and TESTPERP as direct
`NO_TRADE/DISCOVERED` candidates while TESTVELVET remains the only proxy trigger
fixture. `make verify` passes.
**Notes/risks:** Providers are fixture-backed only. No live exchange API calls,
DB writes, Telegram routing, paper trades, or execution were added.

## 2026-06-16 — Bridge event discovery to clean CoinGecko universe fixtures · Codex
**Why:** The event radar could resolve only manually aliased assets. The next
step was to let discovery use the same cleaned CoinGecko-style universe fixture
as the live scanner/backtest path, while staying offline and research-only.
**Changes:**
- Added `event_providers/coingecko_universe.py`, which loads local CoinGecko
  market rows, applies shared `universe.py` hygiene filters, and converts kept
  rows into `DiscoveredAsset` objects.
- Added optional `RSI_EVENT_DISCOVERY_UNIVERSE_PATH` and
  `RSI_EVENT_DISCOVERY_UNIVERSE_LIMIT` config, plus orchestration support to
  merge manual aliases with cleaned universe assets.
- Updated `make event-discovery-report` to exercise the checked-in
  `fixtures/coingecko_smoke/top_markets.json` universe fixture with no network
  calls, DB writes, alerts, paper trades, or execution.
- Added offline tests proving BTC/ETH/SOL become discovery assets, Tether is
  filtered out by shared hygiene, and the BTC ETF fixture can resolve to real
  `bitcoin` as a direct-beneficiary no-trade candidate.
- Updated `AGENTS.md`, `ROADMAP.md`, and `research/event_discovery_design.md`
  with the Phase 2 universe bridge status and guardrails.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 155/155.
`make event-discovery-report` prints the research-only radar with cleaned BTC
universe resolution and no writes/sends/trades. `make verify` passes.
**Notes/risks:** The universe bridge is fixture-only. It does not fetch
CoinGecko live data and does not add any live event provider.

## 2026-06-16 — Add fixture-only event discovery radar · Codex
**Why:** Event-fade scoring is structurally solid, but events were still manual
one-off inputs. Phase 1 needed a research-only radar that can normalize event
evidence, resolve assets conservatively, classify proxy vs direct-beneficiary
relationships, and feed structured candidates into `event_fade.py` without live
routing or storage.
**Changes:**
- Added discovery models and pipeline modules: `event_models.py`,
  `event_discovery.py`, `event_resolver.py`, `event_classification.py`, and
  `event_providers/` with a fixture-only manual JSON provider.
- Added `fixtures/event_discovery/raw_events.json` and
  `fixtures/event_discovery/asset_aliases.json` covering TESTVELVET/SpaceX proxy,
  TESTBTC ETF direct beneficiary, TESTTOKEN listing, TESTPUMP ambiguous pump,
  and a COLLIDE ticker collision that must not resolve confidently.
- Added research-only config and CLI/report wiring:
  `main.py --event-discovery-report` / `make event-discovery-report`. The report
  reads local fixtures only and does not write DB rows, send alerts, open paper
  trades, or execute anything.
- Added offline tests for provider loading, normalization/dedupe, alias
  resolution, ticker-collision rejection, proxy/direct/ambiguous classification,
  full pipeline output, event-fade safety, and scanner report plumbing.
- Added `research/event_discovery_design.md`, updated `AGENTS.md` architecture
  notes, and updated `ROADMAP.md` to reflect that the next work is expanding the
  reviewed validation sample.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 153/153.
`RSI_EVENT_DISCOVERY_EVENTS_PATH=fixtures/event_discovery/raw_events.json .venv/bin/python main.py --event-discovery-report`
prints the research-only event radar with TESTVELVET as proxy, TESTBTC/TESTTOKEN
as direct, TESTPUMP as ambiguous, and COLLIDE unresolved. `make verify` passes.
**Notes/risks:** This is still fixture-only. No network providers, JSONL cache
writes, live DB writes, Telegram routing, paper trades, or execution were added.

## 2026-06-16 — Self-score event-fade feature exports · Codex
**Why:** Review noted that `event_fade_feature_vector()` assumed callers had
already populated `component_scores`, which could silently export zeroed scores
from an otherwise valid candidate.
**Changes:**
- `crypto_rsi_scanner/event_fade.py` lets `event_fade_feature_vector()` accept
  optional `now` and automatically calculate fade scores when the candidate has
  not already been scored, without advancing the candidate state.
- `tests/test_indicators.py` adds regression coverage for unscored feature-vector
  export: scores and eligibility populate, while state remains `DISCOVERED`.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 147/147.
`make verify` passes.
**Notes/risks:** Feature export can now mutate scoring metadata on an unscored
candidate, but still does not advance the event-fade state machine.

## 2026-06-16 — Hard-gate event-fade proxy eligibility · Codex
**Why:** External review caught that `is_event_fade_candidate()` had the right
proxy/direct-beneficiary rule, but the state machine treated proxy purity mostly
as a score component. That could let a high-scoring direct-beneficiary event
drift into a generic overextended-event short, which is not the event-fade thesis.
**Changes:**
- `crypto_rsi_scanner/event_fade.py` now enforces proxy eligibility before a
  candidate can advance beyond `DISCOVERED`; ineligible direct-beneficiary or
  non-proxy events emit `NO_TRADE` even if pump, crowding, RSI, and post-event
  failure evidence are strong.
- `event_fade_feature_vector()` now accepts an optional config and uses the same
  eligibility gate when reporting `signal_type`.
- `tests/test_indicators.py` adds regressions for direct-beneficiary and
  manually armed non-proxy events, plus config-sensitive feature-vector output.
- `AGENTS.md` and `DECISIONS.md` record the hard proxy gate as durable event-fade
  design, not just a test detail.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 147/147.
`RSI_EVENT_FADE_EVENTS_PATH=fixtures/event_fade/sample_events.json .venv/bin/python main.py --event-fade-report`
still prints `TESTVELVET SHORT_TRIGGERED`. `make verify` passes.
**Notes/risks:** Valid proxy-event fixtures still trigger; direct-beneficiary and
non-proxy events now stay diagnostic-only.

## 2026-06-16 — Make push-after-commit the collaboration rule · Codex
**Why:** The human wants GitHub to stay current so Claude, Codex, and external
ChatGPT review all see the latest committed project state.
**Changes:**
- `AGENTS.md` changes the core rule from "commit every change" to "commit and
  push every change", with standing approval to push `main` to `origin` after
  each commit.
- `CLAUDE.md` now repeats the three post-change requirements directly for
  Claude: DEVLOG, commit, push.
- `DECISIONS.md` records the durable decision and supersedes the older
  no-push-without-explicit-approval clause.
**Verify:** docs-only; `git diff --check` passes; `make verify` passes.
**Notes/risks:** Agents should still ask before force-pushing, changing remotes,
or pushing a different branch.

## 2026-06-16 — Add alert-only event-fade research sleeve · Codex
**Why:** The VELVET/SpaceX-style idea is not "short every overbought RSI pump";
it is a separate sell-the-news pattern around dated proxy catalysts, crowded
positioning, liquidity/supply fragility, and post-event failure. The system
needed a research-safe engine that can model that thesis without changing live
RSI alerts or implying execution.
**Changes:**
- `crypto_rsi_scanner/event_fade.py` adds a pure event-fade engine: dataclasses,
  component scores, state machine, post-event failure trigger, BTC risk-on block,
  risk sizing helper, feature-vector export, JSON fixture loaders, and an
  alert-only report formatter.
- `crypto_rsi_scanner/config.py`, `crypto_rsi_scanner/scanner.py`, `main.py`, and
  `Makefile` add inert-by-default event-fade tunables and
  `main.py --event-fade-report` / `make event-fade-report` for local fixture
  scoring only.
- `fixtures/event_fade/sample_events.json` adds a TESTVELVET proxy-event fixture
  that reaches `SHORT_TRIGGERED` only after the event and failure evidence.
- `tests/test_indicators.py` covers component scores, negative direct-beneficiary
  cases, no dated catalyst, post-event confirmation, BTC risk-on blocking, risk
  helpers, JSON loading, and passive feature-vector export.
- `research/event_fade.md`, `AGENTS.md`, `ROADMAP.md`, and `DECISIONS.md`
  document the event-fade thesis, constraints, next validation step, and durable
  rule that this remains alert-only until validated.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 145/145.
`RSI_EVENT_FADE_EVENTS_PATH=fixtures/event_fade/sample_events.json .venv/bin/python main.py --event-fade-report`
prints `TESTVELVET SHORT_TRIGGERED` with alert-only/no-order warning.
`git diff --check` passes. `make verify` passes.
**Notes/risks:** Phase 1 uses local/manual JSON inputs only. No live storage,
notification routing, paper trades, exchange execution, or existing RSI signal
behavior changed. Next step is a manually reviewed event-fade validation sample.

## 2026-06-15 — Add safe paper-trade refresh command · Codex
**Why:** Live paper-trade validation was blocked even after several positions
passed their 7-day hold, because paper exits only closed during the daily
non-dry-run scan. Triggering a full scan just to close trades can send alerts, so
the project needed a narrow non-alerting refresh path.
**Changes:**
- `crypto_rsi_scanner/scanner.py` adds `main.py --refresh-paper`, which fetches
  histories only for open paper-trade coins, calls the existing paper close logic
  with no new signals, and prints the refreshed scoreboard. It supports
  `--cohorts` and `--json` like `--score`.
- `main.py` and `AGENTS.md` document the new command.
- `tests/test_indicators.py` covers that the refresh command fetches open paper
  histories, passes an empty signal list, prints the report, and closes storage
  without running scan/alert plumbing.
- `ROADMAP.md` records that the first six paper trades closed but are still too
  small/outlier-dominated for strategy decisions.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 137/137.
`main.py --refresh-paper --cohorts` fetched 19/19 open histories and closed 6
trades. `make verify` passed after the change.
**Notes/risks:** The first closed paper sample is not decision-grade: 6 trades,
including one -95.7% SIREN outlier. Keep waiting for more closed paper trades
before promoting live priors or state cohorts.

## 2026-06-15 — Fix volume-PIT trigger comparison guardrails · Codex
**Why:** Review found that `--compare-triggers --pit-volume` silently used the
default trigger-comparison universe instead of the volume-PIT universe, and bad
research inputs like `--volume-window 0` could produce empty/noisy output instead
of a clear error.
**Changes:**
- `crypto_rsi_scanner/backtest.py` splits volume-PIT into fetch-once and
  walk-under-trigger helpers, adds `run_pit_volume_triggers()`, wires
  `--compare-triggers --pit-volume` through the real volume-ranked universe, and
  rejects invalid CLI values before any network/cache work.
- `build_volume_membership()` now rejects non-positive `top_n`/`window` values.
- The volume-PIT fetch path now closes its `requests.Session` and skips API
  throttling sleeps when a kline file is already cached.
- `tests/test_indicators.py` adds regression coverage for invalid inputs, the
  PIT-volume compare branch, and cache-hit sleep/session behavior.
- `AGENTS.md` documents that `--compare-triggers` supports `--pit-volume`.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 136/136.
`make verify` passes. Real smoke:
`.venv/bin/python -m crypto_rsi_scanner.backtest --compare-triggers --pit-volume --top-n 5 --days 1825 --volume-window 30`
runs on 368 usable volume-PIT histories and prints both trigger books.
**Notes/risks:** Research-tooling only; no live scanner scoring, routing, or
alert behavior changed.

## 2026-06-10 — Sync agent docs to the volume-PIT reality · Claude
**Why:** AGENTS.md still told agents PIT research was bear-only/365d and needed a
Pro key, and conviction was "unvalidated" — all superseded by the volume-PIT run.
Stale shared docs are how settled questions get relitigated.
**Changes:** AGENTS.md (flag list +`--pit-volume`; "PIT data depth: SOLVED";
conviction-validation status; research-path caveats now point to `--pit-volume`);
DECISIONS.md (new: "Volume-rank PIT is the standard full-cycle research universe").
**Verify:** docs-only; `make verify` green.

## 2026-06-10 — Volume-rank PIT universe: 5y survivorship-reduced backtest, no Pro key · Claude
**Why:** Every blocked research item (bull/chop validation, prior recalibration,
state-cohort confirmation) was gated on point-in-time history >365d, which the
mcap PIT path can't get on a demo CoinGecko key. Binance klines are free for ~5y
and carry quote (USDT) volume — so membership can be ranked by trailing dollar
volume instead of market cap.
**Changes:**
- `backtest.py`: `--pit-volume` mode — `binance_usdt_pool()` (exchangeInfo,
  hygiene-filtered; no leveraged-token suffix filter needed since those are all
  delisted, and JUP/SYRUP are real coins), `build_volume_membership()` (top-N by
  trailing `--volume-window`=30d mean quote volume, no lookahead),
  `run_pit_volume()` (walks on USD volume so volume_ratio matches live CoinGecko
  semantics). `fetch_klines` now returns `quote_volume` and caches raw rows under
  `backtest_cache/binance_klines/` (reuses the PIT cache flags; cache hit never
  touches the network).
- Tests: membership rolling-rank, pool hygiene filter, kline row parsing, cache
  roundtrip (132/132).
- `research/VOLUME_PIT_BACKTEST_2026-06-10.md` + prior export
  `research/registry_priors_volpit_2026-06-10.json`; ROADMAP: two "needs Pro
  key" items closed, follow-ups added.
**Verify:** `make verify` green (132/132 + smokes). Full run: 368 coins, 21,334
graded obs, balanced coverage (BULL 60.9k / CHOP 23.8k / BEAR 46.7k base-days).
**Results:** Gating map confirmed on survivorship-reduced full-cycle data —
mean_reversion CHOP **+10 (n=800)** third independent confirmation;
mean_reversion BULL −3; dip_buy/trend_continuation BULL positive but thin
(+6/+4); breakdown_risk no edge anywhere (context-only stays right). **Conviction
monotonic with edge for the first time** (low −3 / med +3 / high +9, n=307) —
first real validation of the registry edge-prior conviction. State-slice
replications: breakdown_risk crisis-vol −19; mean_reversion washout +14,
risk_on_broad −8.
**Notes/risks:** Residual survivorship (delisted pairs absent from exchangeInfo);
single venue; volume-rank ≠ live mcap universe. Prior export is reviewable only —
NOT loaded live (opt-in policy unchanged).

## 2026-06-09 — Fix review reliability gaps · Codex
**Why:** A fresh review found several boundary bugs: failed alert sends could
still advance cooldown/digest state, paper trades opened before matured same-coin
positions closed, live outcome reports could not directly validate gating, and
dry-run/universe-audit behavior had small honesty gaps.
**Changes:**
- `crypto_rsi_scanner/scanner.py` now skips CSV writes in dry-run mode, fetches
  extra recent histories for pending outcome/paper bookkeeping when coins leave
  today's clean universe, and only marks instant/digest notification state after
  a channel succeeds.
- `crypto_rsi_scanner/notifications.py` splits long Telegram messages into
  multiple line-aware chunks instead of truncating later cards.
- `crypto_rsi_scanner/storage.py` adds `signals.market_aligned`, backfills it
  additively, exposes pending signal/open paper coin IDs, and returns market/state
  context from `outcomes_joined()`.
- `crypto_rsi_scanner/outcomes.py` adds actionable/control, market-alignment, and
  state-cohort sections to `main.py --report`.
- `crypto_rsi_scanner/paper.py` closes matured trades before opening new
  crossings and treats missing falling-knife state as unknown, not low risk.
- `crypto_rsi_scanner/universe.py` stores all kept audit rows so suspicious-kept
  checks cover the full requested clean universe.
- `tests/test_indicators.py`, `AGENTS.md`, `ROADMAP.md`, `DECISIONS.md`, and
  `main.py` document and cover the reliability changes.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 128/128.
`main.py --report`, `make dry-run-fixture`, and `make score-cohorts` run
successfully. `make verify` passes tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** This changes live reliability/bookkeeping and reporting, but not
the core RSI setup taxonomy, conviction priors, or market-gating rules. The first
post-change `Storage` open migrates the ignored live DB with `market_aligned`.

## 2026-06-09 — Add cohort, cost, and walk-forward research tools · Codex
**Why:** The remaining improvement tracks needed tooling before any live signal
behavior changes: live cohort reads, cost/slippage-aware backtest output,
chronological stability checks, and a repeatable way to spot universe hygiene
leaks.
**Changes:**
- `crypto_rsi_scanner/paper.py`, `scanner.py`, `main.py`, and `Makefile` add
  `main.py --score --cohorts` / `make score-cohorts`, including state-bucket
  cohort stats from stored `state_json` once paper trades close.
- `crypto_rsi_scanner/backtest.py` adds `--costs`, `--fee-bps`,
  `--slippage-bps`, `--max-trades-per-day`, `--walk-forward`, and timestamped
  signal labels so research can inspect costs, capacity, drawdown, and fold
  stability before promoting calibration.
- `crypto_rsi_scanner/universe.py` adds suspicious-kept leak detection to the
  audit formatter for stable/wrapped/yield-like rows that survive filtering.
- `research/PIT_DATA_OPTIONS_2026-06-09.md` documents the current 365d PIT data
  limit, Pro-key/deeper-history workflow, alternate provider contract, and
  promotion rule.
- `AGENTS.md`, `ROADMAP.md`, and `DECISIONS.md` record the new commands and the
  decision that cost/walk-forward outputs are research-only until a specific
  live rule is proposed.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 124/124.
`make score-cohorts`, `make backtest-costs`, and `make universe-audit` all run
successfully. `make verify` passes tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** No live signal scoring, routing, or gating changed. Broader PIT
history still requires a Pro CoinGecko key or alternate historical market-cap
provider before registry priors should be promoted live.

## 2026-06-09 — Add universe audit refresh command · Codex
**Why:** After tightening hygiene filters, the project still had to wait for a
full scheduled scan to confirm the market-list filter. A lightweight refresh
path gives immediate feedback without running RSI analysis or sending alerts.
**Changes:**
- `crypto_rsi_scanner/scanner.py` adds `fetch_universe_audit()` plus
  `main.py --refresh-universe-audit`, which fetches current CoinGecko market
  rows, applies shared universe hygiene, persists the audit, and prints it.
- `Makefile` adds `make refresh-universe-audit`.
- `crypto_rsi_scanner/universe.py` now directly excludes symbols that start or
  end with `usd`, catching observed BFUSD/apxUSD leaks from the refreshed audit.
- `tests/test_indicators.py` covers the audit refresh helper with a fake
  CoinGecko client and the new USD-prefix/suffix examples.
- `ROADMAP.md`, `DECISIONS.md`, and `AGENTS.md` document the workflow and the
  refreshed audit result.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 122/122.
`make refresh-universe-audit` persisted a fresh audit: 200 fetched, 100 kept, 53
excluded (`stable_like=36`, `low_liquidity=17`). A kept-set regex scan found no
obvious USD/stable/yield leaks. `make verify` passes tests, alert render smoke,
backtest fixture smoke, and paper scoreboard after the documentation update.
**Notes/risks:** The command updates `universe_hygiene_latest.json` and the DB
meta audit, but does not run a full scan, send alerts, or alter signal state.

## 2026-06-09 — Tighten universe stable/pegged filters · Codex
**Why:** The next roadmap item was to review the latest live universe hygiene
audit for false positives/negatives. The 2026-06-09 03:10 MSK audit showed
stable/pegged products surviving into the kept top-100.
**Changes:**
- Reviewed `main.py --universe-audit`: 200 fetched, 100 kept, 41 excluded
  (`stable_like=19`, `low_liquidity=22`).
- `crypto_rsi_scanner/universe.py` now catches observed false negatives:
  USD1, Global Dollar/USDG, USDtb, United Stables, GHO, YLDS, USX, USYC,
  Tether Gold/XAUT, and PAX Gold/PAXG.
- `crypto_rsi_scanner/config.py` mirrors the safe symbol-only exclusions; the
  one-letter United Stables symbol is caught by name instead.
- `tests/test_indicators.py` covers the newly observed stable/pegged examples.
- `ROADMAP.md`, `DECISIONS.md`, and `AGENTS.md` record the audit result and the
  follow-up to re-check the next live audit.
**Verify:** Replayed the known kept false negatives through `exclusion_reason()`;
they now return `stable_like`. `.venv/bin/python tests/test_indicators.py`
passes 121/121. `make verify` passes tests, alert render smoke, backtest fixture
smoke, and paper scoreboard after the documentation update.
**Notes/risks:** Low-liquidity exclusions such as LEO were left unchanged. The
next scheduled scan should confirm these products no longer appear in the kept
universe.

## 2026-06-09 — Add offline backtest fixture smoke · Codex
**Why:** The final ready roadmap item was to make the backtest CLI smoke-testable
without relying on Binance/network availability.
**Changes:**
- `crypto_rsi_scanner/backtest.py` can load Binance-style daily kline CSVs via
  `--fixture-dir`, infer symbols from fixture filenames, and fail smoke runs with
  `--min-signals` when too few graded observations are produced.
- Added checked-in BTC/ETH/SOL 365d fixture snapshots under
  `fixtures/backtest_smoke/klines/` plus a fixture README.
- `Makefile` adds `make backtest-fixture` and includes it in `make verify`.
- `tests/test_indicators.py` covers fixture symbol inference and CSV parsing.
- `ROADMAP.md`, `DECISIONS.md`, and `AGENTS.md` document the completed fixture
  smoke and its verification role.
**Verify:** `make backtest-fixture` produces 3 usable coins and 33 graded
observations. `.venv/bin/python tests/test_indicators.py` passes 121/121.
`make verify` passes tests, alert render smoke, backtest fixture smoke, and paper
scoreboard after the documentation update.
**Notes/risks:** No live scanner logic changed. The fixture is a small smoke
dataset, not strategy evidence.

## 2026-06-09 — Review cached PIT registry priors · Codex
**Why:** The next roadmap research step was to export registry conviction priors
from point-in-time histories and decide whether the artifact is strong enough to
load live.
**Changes:**
- Ran `.venv/bin/python -m crypto_rsi_scanner.backtest --pit --top-n 80 --pool
  150 --days 365 --export-priors research/registry_priors_pit_2026-06-09.json`:
  150 cache hits, 128 usable histories, 1325 graded observations.
- Added `research/registry_priors_pit_2026-06-09.json` and
  `research/PIT_REGISTRY_PRIORS_REVIEW_2026-06-09.md` with the exported deltas
  and review-only decision.
- `ROADMAP.md`, `DECISIONS.md`, and `AGENTS.md` now record that the 365d PIT
  prior export is BEAR-only evidence and should not be loaded with
  `RSI_REGISTRY_PRIORS`.
**Verify:** PIT export completed successfully. `make verify` passes tests
120/120, alert render smoke, and paper scoreboard after the documentation
updates.
**Notes/risks:** No signal logic changed. The export moved
`mean_reversion.neutral` 42 -> 47 and `trend_continuation.neutral` 42 -> 40, but
that is not enough for live adoption because the market coverage was only BEAR.

## 2026-06-09 — Run cached PIT state-slice confirmation · Codex
**Why:** The next roadmap item was to use point-in-time membership to check
whether the current-top Binance state-slice candidates survive a less
survivorship-biased test.
**Changes:**
- Ran `.venv/bin/python -m crypto_rsi_scanner.backtest --pit --top-n 80 --pool
  150 --days 365 --state-slices`: cache started empty, populated 150 raw
  CoinGecko histories, used 128 histories, and produced 1325 graded observations.
- Added `research/PIT_STATE_SLICE_CONFIRMATION_2026-06-09.md` with the command,
  caveats, setup baseline, state-slice read, and no-live-change decision.
- `ROADMAP.md`, `DECISIONS.md`, and `AGENTS.md` record that this PIT result is
  bear-regime evidence only; bull/chop state candidates still need deeper PIT or
  live confirmation.
**Verify:** PIT run completed successfully and populated the local gitignored
cache. `make verify` passes tests 120/120, alert render smoke, and paper
scoreboard after the documentation update.
**Notes/risks:** No signal logic changed. The 365d demo CoinGecko PIT window
only had BTC `BEAR` market-regime coverage, so it supports monitoring
bear-regime `mean_reversion` and keeping `breakdown_risk` context-only, but does
not validate bull/chop rules.

## 2026-06-09 — Add PIT history cache for backtests · Codex
**Why:** PIT state-slice confirmation and registry calibration depend on
CoinGecko market-cap histories, which are rate-limit sensitive and expensive to
refetch. A local raw-history cache improves practical PIT research power even
before a deeper Pro/alternate data source is available.
**Changes:**
- `crypto_rsi_scanner/backtest.py` caches raw CoinGecko `market_chart` JSON for
  PIT histories, reads cached histories before network fetches, and adds
  `--pit-cache-dir`, `--no-pit-cache`, and `--refresh-pit-cache` flags.
- `crypto_rsi_scanner/config.py`, `.env.example`, and `.gitignore` add the
  configurable `RSI_BACKTEST_CACHE_DIR` (`backtest_cache` by default) and keep
  cached research data out of git.
- `tests/test_indicators.py` adds a PIT cache roundtrip test that loads a cached
  synthetic history without network.
- `AGENTS.md`, `ROADMAP.md`, and `DECISIONS.md` document the cache behavior and
  the remaining data-source limit for >365d PIT history.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 120/120.
`.venv/bin/python -m crypto_rsi_scanner.backtest --help | rg
"pit-cache|refresh-pit-cache|no-pit-cache"` confirms the CLI flags. `make
verify` passes tests, alert render smoke, and paper scoreboard.
**Notes/risks:** This improves repeatability/resume behavior and larger-pool PIT
runs, but it does not bypass CoinGecko demo history limits. >365d PIT still needs
a Pro key or alternate historical market-cap source.

## 2026-06-09 — Run first larger state-slice review · Codex
**Why:** The next research step was to use `backtest --state-slices` on a larger
history and decide whether any shadow market-state buckets are ready for live
promotion.
**Changes:**
- Ran `.venv/bin/python -m crypto_rsi_scanner.backtest --top-n 80 --days 1460
  --state-slices`: 49 usable Binance histories, 7648 graded observations.
- Added `research/STATE_SLICE_BACKTEST_2026-06-09.md` with the command, caveats,
  setup baseline, market-regime check, candidate state cohorts, and no-promotion
  decision.
- `crypto_rsi_scanner/backtest.py` widens the state-slice table columns so long
  feature labels do not run into bucket names.
- `ROADMAP.md`, `DECISIONS.md`, and `AGENTS.md` record that these candidates
  need PIT/live confirmation before any live conviction/routing change.
**Verify:** Larger state-slice run completed successfully. Full local
verification was rerun after the docs/formatting update: `make verify` passes
tests 119/119, alert render smoke, and paper scoreboard.
**Notes/risks:** No live signal logic changed. Most plausible candidates are
documented, but the run is current-top survivorship-biased, single-venue, and
costless, so it is not enough to alter live alerts.

## 2026-06-09 — Add state-conditioned backtest slices · Codex
**Why:** Live scanner now stores shadow market-state context, but those labels
need a research path that can test conditional edge before any state bucket is
allowed to affect conviction or routing.
**Changes:**
- `crypto_rsi_scanner/state_features.py` exposes shared bucket/risk helpers for
  relative strength, liquidity, breadth state, and falling-knife risk so live and
  research use the same labels.
- `crypto_rsi_scanner/scanner.py` now consumes those shared helpers instead of
  private copies.
- `crypto_rsi_scanner/backtest.py` adds point-in-time state-frame construction,
  stores state labels on graded events, builds same-regime/same-state base-rate
  tables, and exposes `--state-slices` / `--state-min-samples` for research
  reports.
- `tests/test_indicators.py`, `AGENTS.md`, `ROADMAP.md`, and `DECISIONS.md`
  cover and document the new state-slice benchmark rule.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 119/119.
`.venv/bin/python -m crypto_rsi_scanner.backtest --help | rg
"state-slices|state-min-samples"` confirms the new CLI flags. `make verify`
passes tests, alert render smoke, and paper scoreboard.
**Notes/risks:** The state-slice report is still research-only. A bucket should
not be promoted into live conviction/routing unless it beats the same-regime,
same-state base rate with enough PIT/live observations.

## 2026-06-08 — Wire market-state context into live scanner · Codex
**Why:** The pure state feature layer needs live, reviewable observations before
any state-conditioned edge can be trusted. Scanner rows should therefore carry
volatility, breadth, relative-strength, liquidity, and falling-knife context
without changing current alert decisions.
**Changes:**
- `crypto_rsi_scanner/scanner.py` builds one shadow state context per scan,
  attaches per-coin `state_json`, `vol_state`, `breadth_state`, `rs_bucket`,
  `liquidity_bucket`, and `falling_knife_score` after conviction/tier are
  computed, and adds compact console tokens for meaningful state labels.
- `crypto_rsi_scanner/storage.py` additively migrates `signals` and
  `paper_trades` with nullable `state_json`; `crypto_rsi_scanner/paper.py`
  stores the entry-state snapshot for paper trades.
- `crypto_rsi_scanner/telegram.py` preserves compact state buckets in the latest
  bot snapshot.
- `tests/test_indicators.py`, `ROADMAP.md`, `DECISIONS.md`, and `AGENTS.md`
  document and test the shadow-only state boundary.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 117/117.
`make dry-run-fixture` runs offline and shows state tokens in the scan output.
`make smoke-alerts` passes. `make verify` passes tests, alert render smoke, and
paper scoreboard.
**Notes/risks:** State remains observational only. The next high-leverage work is
state-conditioned backtest/live cohort analysis before allowing any state bucket
to affect conviction or routing.

## 2026-06-08 — Add pure market-state feature layer · Codex
**Why:** The research plan keeps RSI as the event trigger but needs a separate,
auditable market-state layer before testing volatility, breadth, relative
strength, beta, liquidity, and falling-knife hypotheses.
**Changes:**
- New `crypto_rsi_scanner/state_features.py` adds pure helpers for realized
  volatility, trailing percentiles, volatility state labels, percentage returns,
  cross-sectional ranks, single/multi-factor beta, volume z-score, dollar
  volume, turnover, volume/price state, and breadth snapshots.
- `tests/test_indicators.py` adds standalone tests covering flat/changing
  volatility, trailing-only percentiles, volatility state rules, rank monotonicity,
  synthetic beta recovery, volume/liquidity classification, and breadth behavior
  with missing/short histories.
- `AGENTS.md`, `ROADMAP.md`, and `DECISIONS.md` document the shadow-first state
  feature policy and next integration step.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 115/115.
`make verify` passes tests, alert render smoke, and paper scoreboard.
**Notes/risks:** This is intentionally not wired into scanner routing, conviction,
or registry priors. Next step is shadow-only scanner/backtest integration with
`state_json`.

## 2026-06-08 — Add maintenance agent, restore drill, fixtures, and audit outputs · Codex
**Why:** The scanner had backup/log commands, but the remaining system
improvements were still manual or not reviewable: scheduled maintenance,
restore proof, structured paper-score data, universe-hygiene audits, and offline
scanner fixtures.
**Changes:**
- `main.py --maintenance` now runs a safe DB backup, restores that backup into a
  temporary SQLite DB for verification, and rotates configured logs.
- `main.py --verify-restore` restore-checks the newest retained backup by
  default; `backups.py` exposes the reusable restore-drill primitive.
- `make install-maintenance-agent` installs/loads the daily launchd maintenance
  agent (`com.nasrenkaraf.rsimaintenance` by default) to run `--maintenance`.
- `main.py --score --json` emits structured paper-score data, and the text score
  report now includes market-alignment and conviction-bucket breakdowns.
- Live scans persist the latest universe hygiene audit to SQLite meta and
  `universe_hygiene_latest.json`; `main.py --universe-audit` prints it.
- `RSI_FIXTURE_DIR` enables CoinGecko fixture mode, with checked-in
  `fixtures/coingecko_smoke` powering `make dry-run-fixture`.
- `Makefile`, `.env.example`, `.gitignore`, `AGENTS.md`, `CLAUDE.md`,
  `ROADMAP.md`, and `DECISIONS.md` document the new commands and operating
  decisions.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 108/108.
`make verify` passes tests, alert render smoke, and paper scoreboard.
`main.py --verify-restore` passes against the latest backup. `make maintenance`
created and restore-checked `backups/rsi_scanner-20260608T185301Z.db`.
`make dry-run-fixture` runs the scanner offline from fixtures. The maintenance
LaunchAgent was installed at
`~/Library/LaunchAgents/com.nasrenkaraf.rsimaintenance.plist` and points at the
repo venv Python.
**Notes/risks:** `main.py --universe-audit` will show data after the next
non-dry live scan persists the first audit. The fixture smoke validates scanner
plumbing, not live CoinGecko availability.

## 2026-06-08 — Finish ops maintenance status, logs, and launchd helpers · Codex
**Why:** Safe backups existed, but operational health still did not show whether
the latest backup was fresh, logs could grow without a repo-owned rotation
command, and launchd service inspection required memorized shell commands.
**Changes:**
- `main.py --status` now reports newest backup freshness, retained backup count,
  and configured log sizes/rotation thresholds.
- New `crypto_rsi_scanner/ops.py` adds copy-truncate log rotation plus launchd
  scan/listener status parsing and listener restart helpers.
- `main.py`, `Makefile`, `config.py`, `.env.example`, `.gitignore`,
  `AGENTS.md`, `CLAUDE.md`, `ROADMAP.md`, and `DECISIONS.md` document and expose
  `--rotate-logs`, `--launchd-status`, and `--restart-listener`.
- `tests/test_indicators.py` covers backup freshness rendering, log rotation
  retention, and launchd output parsing.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 104/104.
`.venv/bin/python main.py --status` shows the live backup as `OK` and both logs
below rotation threshold. `.venv/bin/python main.py --launchd-status` reports
`com.nasrenkaraf.rsiscanner` loaded/not running with last exit 0 and
`com.nasrenkaraf.rsibot` running. `.venv/bin/python main.py --rotate-logs` keeps
the current small logs without rotating.
**Notes/risks:** This intentionally does not install or mutate launchd schedules;
use the new commands from an explicit scheduled job if/when the owner wants that.

## 2026-06-08 — Add safe SQLite DB backup command · Codex
**Why:** The scanner now has operational health reporting, but the live SQLite
DB still needed a safe recovery path. Because the DB runs in WAL mode and can be
open from the scan and listener, raw file copies are not reliable enough.
**Changes:**
- New `crypto_rsi_scanner/backups.py` uses SQLite's online backup API to create
  consistent snapshots, writes through a temp file, verifies the result with
  `PRAGMA integrity_check`, and prunes older backups by retention count.
- `main.py --backup-db` and `make backup-db` create a verified backup under
  `RSI_BACKUP_DIR` with `RSI_BACKUP_KEEP` retention.
- `config.py`, `.env.example`, `.gitignore`, `AGENTS.md`, `ROADMAP.md`, and
  `DECISIONS.md` document/configure the backup workflow and keep backup artifacts
  out of git.
- `tests/test_indicators.py` adds a temp-DB backup integrity and retention test.
**Verify:** `.venv/bin/python main.py --backup-db` created
`backups/rsi_scanner-20260608T182009Z.db`, size 0.20 MB, `integrity_check: ok`.
`make verify` passes: tests 101/101, alert render smoke, and paper scoreboard.
**Notes/risks:** Backup freshness is not yet shown in `--status`; ROADMAP keeps
that and log rotation as the next ops-hardening work.

## 2026-06-08 — Add scan status and bot health report · Codex
**Why:** The scanner had heartbeat alerts for crashes/degraded fetches, but no
single persisted view of the latest run state. If launchd missed a scan or a run
failed after fetching, the owner and bot had to infer health from logs.
**Changes:**
- `storage.py` now persists scan lifecycle status in SQLite meta: running,
  success, failure, start/finish times, last success/failure, fetch/analyze
  counts, signal counts, routing counts, outcome updates, and paper-trade updates.
- `scanner.py` records live scan start/success/failure status, preserves dry-run
  read-only behavior, returns notification routing counts, and adds
  `main.py --status`.
- New `status_report.py` renders one shared operational report for CLI and bot.
- `telegram.py` adds `/health` and `/status`, updates help text, and has the
  listener check stale successful scans with a one-alert-per-episode watchdog.
- `heartbeat.py`, `config.py`, and `.env.example` expose/tune stale-scan alerts
  via `RSI_STALE_SCAN_HOURS` and `RSI_STALE_CHECK_INTERVAL_SEC`.
- `AGENTS.md`, `ROADMAP.md`, and `DECISIONS.md` document the status path and
  narrow remaining ops hardening to DB backups/log rotation.
- `tests/test_indicators.py` adds status lifecycle/report, bot escaping, stale
  watchdog, and WAL/busy-timeout coverage.
**Verify:** `.venv/bin/python main.py --status` prints current local DB health
(`health: OK`, last success fallback from the existing `scans` table). `make
verify` passes: tests 100/100, alert render smoke, and paper scoreboard.
**Notes/risks:** Existing live runs will show `scan state: unknown` until the next
non-dry scan writes the new status meta; last-success freshness still falls back
to the historical `scans` table.

## 2026-06-08 — SQLite WAL + busy_timeout for scan/listener concurrency · Claude
**Why:** The daily scan (launchd) and the always-on bot listener share one SQLite
file. Default rollback-journal mode makes readers and writers block each other, so
a scan write during a listener read (or vice versa) risks "database is locked".
**Changes:**
- `storage.py` `Storage.__init__`: open with `timeout=30`, `PRAGMA journal_mode=WAL`
  + `PRAGMA busy_timeout=30000`. WAL lets one reader + one writer proceed
  concurrently; busy_timeout backs the rarer writer/writer overlap.
- `.gitignore`: ignore the new `*.db-wal` / `*.db-shm` sidecars.
- `tests/test_indicators.py`: assert Storage opens in WAL with a busy_timeout.
**Verify:** `make verify` green (97/97 + smoke). Live DB confirmed `journal_mode=wal`;
listener restarted on new code (PID 54739); WAL sidecars present and gitignored.
**Notes:** WAL is persistent in the DB header; needs local disk (it's on the Mac's
local FS). No schema change.

## 2026-06-08 — Initialize local git + commit-per-prompt convention · Claude
**Why:** Two agents now edit the same files; git gives real diffs/blame/rollback
that a hand-maintained log can't. Human approved adopting it.
**Changes:**
- `git init` (branch `main`, no remote); initial commit of the full tree.
- `.gitignore`: also ignore `.claude/settings.local.json` (machine-local).
- New convention in `AGENTS.md`/`CLAUDE.md`: end every change-making prompt with one
  commit, `make verify` green, no secrets/artifacts, on `main`, no push without approval.
- `DECISIONS.md`: superseded the two "no git" decisions; added the adoption decision.
  `ROADMAP.md`: dropped the "evaluate git" item.
**Verify:** `make verify` green; `git status` clean post-commit; confirmed `.env`,
`*.db`, logs, `.venv`, `.claude/settings.local.json` are untracked.
**Notes:** local-only; adding a remote/push needs explicit human approval (DECISIONS).

## 2026-06-07 — Fix NaN crash in alert render (DataFrame self-tune) · Claude
**Why:** The registry refactor's `_apply_live_edge_adjustments` creates
`track_record`/`conviction_base` columns via `df.at`, leaving NaN on rows without
a value. Once 7d live outcomes accrue, `_tg_card` joins a NaN float →
`TypeError: expected str, got float` → every alert send would crash silently.
**Changes:**
- `formatting._tg_card`: guard `track_record` + `conviction_base` with `_present`
  (rejects None *and* NaN).
- `scanner._apply_live_edge_adjustments`: pre-create both columns as object/None so
  unset rows stay None, not NaN (also keeps the bot snapshot JSON clean).
- `tests/test_indicators.py`: render-guard + end-to-end (apply→build_message→render)
  regression tests.
**Verify:** reproduced the crash with forced 7d stats, confirmed fixed; suite green.
**Notes:** Codex's later `alert_smoke.py` (DOGE NaN fixture) independently backstops
this at the render layer.

## 2026-06-07 — Add alert render smoke test · Codex
**Why:** Alert rendering has become a critical path with rich Telegram HTML,
plain-text fallbacks, macro headers, digest caps, track-record annotations, and
NaN-prone DataFrame enrichment. A signal-math test can pass while a notification
render still crashes or produces invalid Telegram markup.
**Changes:**
- New `crypto_rsi_scanner/alert_smoke.py` builds representative instant/digest
  payloads and validates Telegram HTML tags, message lengths, digest group caps,
  NaN/unsafe substring leaks, and plain fallback truncation behavior without
  sending network notifications.
- `Makefile` adds `make smoke-alerts` and includes it in `make verify`.
- `formatting.py` now escapes quotes in chart-link `href` attributes.
- `tests/test_indicators.py` adds the smoke suite test and a direct regression
  test for quoted symbols in chart links.
- `AGENTS.md` and `DECISIONS.md` document alert-render smoke as part of standard
  verification.
**Verify:** `.venv/bin/python -m crypto_rsi_scanner.alert_smoke` passes. `.venv/bin/python tests/test_indicators.py`
passes 96/96. `make verify` passes: tests 96/96, alert render smoke, and paper
scoreboard.
**Notes/risks:** The smoke is fixture-based and no-send/no-network; it catches
render regressions but does not validate Telegram API delivery.

## 2026-06-07 — Add backtest-to-registry calibration path · Codex
**Why:** Registry priors were still hand-coded from qualitative backtest findings.
The system needed a repeatable way to turn backtest evidence into reviewable
runtime priors without silently changing live alerts after a noisy smoke run.
**Changes:**
- `crypto_rsi_scanner/backtest.py` adds pure calibration/export helpers plus
  `--export-priors PATH` and `--prior-min-samples`. The export JSON includes run
  metadata, setup priors, default priors, and setup x market-regime evidence.
- Calibration is conservative: it starts from current registry priors, moves only
  sample-backed setup x market cells, clamps swings, and keeps `breakdown_risk`
  context-only even if a short sample shows apparent edge.
- `crypto_rsi_scanner/signal_registry.py` can load explicit JSON overrides from
  `RSI_REGISTRY_PRIORS`, validates schema/values, resolves relative paths against
  the project root, and falls back to checked-in defaults on missing/invalid
  calibration.
- `tests/test_indicators.py` adds deterministic tests for explicit override
  loading and evidence-driven prior calibration.
- `AGENTS.md`, `ROADMAP.md`, `DECISIONS.md`, and `.env.example` document the
  calibration workflow and opt-in policy.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 94/94. `make verify`
passes: tests 94/94 and paper scoreboard runs. Smoke export passes:
`.venv/bin/python -m crypto_rsi_scanner.backtest --top-n 5 --days 365 --export-priors /tmp/rsi_registry_priors_smoke_topn.json`
with 5 usable coins and 63 graded observations; exported JSON reloads through
`signal_registry.load_prior_overrides`.
**Notes/risks:** The smoke artifact is intentionally not enabled live; it is only
a CLI/schema check. Use a stronger PIT or longer-history run before setting
`RSI_REGISTRY_PRIORS` in `.env`.

## 2026-06-07 — Add shared universe hygiene filters · Codex
**Why:** CoinGecko top market-cap lists include stablecoins, wrapped/staked
receipts, stale/suspicious listings, and low-liquidity artifacts that pollute
alerts, outcomes, paper trades, and backtests.
**Changes:**
- New `crypto_rsi_scanner/universe.py` with pure filters for stable-like assets,
  wrapped/staked/synthetic derivatives, invalid market data, low volume/market
  cap, and suspicious 24h moves.
- `scanner.py` now overfetches CoinGecko candidates, applies shared hygiene, logs
  exclusion reason counts, and scans the first clean requested top-N.
- `backtest.py` uses the same hygiene for CoinGecko top-N/PIT candidate
  selection.
- `config.py` adds universe hygiene tunables and removes `stx` from hard symbol
  excludes so Stacks is not accidentally filtered.
- `.env.example`, `AGENTS.md`, `ROADMAP.md`, and `DECISIONS.md` document the new
  shared universe policy.
- Tests added for stable/wrapped/low-liquidity/suspicious exclusions, overfetch
  capping, and the `STX` false-positive case.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 92/92. `make verify`
passes. Backtest smoke check passes:
`.venv/bin/python -m crypto_rsi_scanner.backtest --top-n 5 --days 365`.
Live dry-run passes: `.venv/bin/python main.py --dry-run --top-n 5` fetched 55
candidates, excluded 2 stable-like entries, and scanned 5 clean coins.
**Notes/risks:** Filters are conservative and log reason counts; review live
logs for false positives/negatives before tightening further.

## 2026-06-07 — Backfill NaN-safe live-edge rendering fix · Codex
**Why:** Claude fixed a latent alert-rendering regression after the DataFrame
self-tune refactor, but stopped before logging it. Without the fix, rows without
track-record history could carry `NaN` into Telegram card rendering once live
7-day outcomes accrue.
**Changes:**
- `scanner.py` pre-creates `track_record` and `conviction_base` as object/`None`
  columns before live-edge enrichment, avoiding NaN-filled columns for unmatched
  rows.
- `formatting.py` guards `track_record` and `conviction_base` with `_present()`
  before rendering, so `None`/NaN values do not crash or leak into alerts.
- `tests/test_indicators.py` adds regression tests for direct Telegram card
  rendering and the apply/build/render path.
**Verify:** `make verify` passes: standalone tests 89/89 and paper scoreboard runs.
**Notes/risks:** This is a DEVLOG backfill of Claude's fix, not a new behavioral
change by Codex.

## 2026-06-07 — Add signal registry and edge-prior conviction · Codex
**Why:** Setup intent, market eligibility, and conviction priors were spread
across modules, and conviction still leaned too heavily on fixed severity
weights despite backtest findings.
**Changes:**
- New `crypto_rsi_scanner/signal_registry.py` as the canonical source for setup
  definitions, expected directions, market alignment, and edge-prior conviction
  baselines.
- `indicators.py` now delegates setup/market helpers to the registry and blends
  registry edge priors with severity/confluence in `conviction_score`.
- `scanner.py` uses registry-based conviction directly and applies mature live
  outcome self-tuning before printing, saving CSV/DB rows, snapshots, and alerts.
- `backtest.py`, `outcomes.py`, `paper.py`, `formatting.py`, and `storage.py`
  now consume registry definitions instead of duplicated/private setup maps.
- Tests added for registry coverage, backtest market aliases, and edge-prior
  conviction ordering.
- Updated `AGENTS.md`, `ROADMAP.md`, `DECISIONS.md`, and `config.py` comments to
  reflect the new source of truth.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 87/87. `make verify`
passes: tests 87/87 and paper scoreboard runs. Backtest smoke check passes:
`.venv/bin/python -m crypto_rsi_scanner.backtest --symbols BTC,ETH,SOL --days 365`.
**Notes/risks:** Registry priors encode the current qualitative backtest findings;
`ROADMAP.md` keeps numeric recalibration with stronger PIT/live evidence as a
future task.

## 2026-06-07 — Add roadmap, decisions log, and verify command · Codex
**Why:** The collaboration protocol had a history file, but no single place for
pending work, durable accepted/rejected decisions, or a standard verification
command.
**Changes:**
- New `ROADMAP.md` for live pending work, statuses, and priorities.
- New `DECISIONS.md` for durable technical decisions and revisit conditions.
- New `Makefile` with `make verify`, `make test`, `make score`, `make report`,
  and `make dry-run`.
- Updated `AGENTS.md` and `CLAUDE.md` to point both agents at the new files and
  standard verification path.
**Verify:** `make verify` passes: standalone tests 85/85, paper scoreboard runs.
**Notes/risks:** Did not initialize local git; `DECISIONS.md` records that agents
should wait for explicit human approval before changing the repo workflow.

## 2026-06-07 — Add shared AI-collaboration system (AGENTS.md + DEVLOG.md) · Claude
**Why:** Owner is now co-developing with Codex; we need a shared protocol + change
history (no git repo to lean on).
**Changes:**
- New `AGENTS.md` (shared brain: run/test/deploy, architecture, conventions,
  strategy findings, the "log every change" rule).
- New `DEVLOG.md` (this file) with template + backfilled session history.
- New `CLAUDE.md` (thin pointer so Claude Code follows AGENTS.md/DEVLOG).
**Verify:** docs only; `tests/test_indicators.py` still 85/85.
**Notes:** Codex reads `AGENTS.md` natively; Claude reads `CLAUDE.md` → both land here.

## 2026-06-07 — Confirmation entry trigger: A/B'd, REJECTED (backtest only) · Claude
**Why:** Test whether entering when RSI turns back *out* of the OB/OS zone beats
piercing *into* it (catching the knife).
**Changes:** `backtest.py` — `trigger` param on `walk_coin` (cross_into|confirm via
zone-state), `_fetch_all`/`_walk_all` refactor, `run_triggers`, `--trigger` /
`--compare-triggers`, `format_trigger_comparison`. Test added.
**Verify:** 5y/38-coin A/B: actionable book @7d ~identical (52%/+0.0% vs 51%/−0.0%);
confirm slightly hurts dip_buy & mean_reversion. **Live scanner UNCHANGED.**
**Notes/risks:** Negative result — don't re-add confirmation without new evidence.
Tooling kept for future variant A/Bs. Aggregate live edge is thin & regime-specific.

## 2026-06-07 — Paper-trade scoreboard · Claude
**Why:** Honest live proof of whether the (gated) signals make money.
**Changes:** new `paper.py`; `storage.py` `paper_trades` table + accessors;
`scanner.run` opens/closes trades each scan; `--score` CLI + `/score` bot command;
`config.PAPER_*`. Opens a virtual long/short per new crossing, closes after 7d at
that day's close (reuses fetched prices). Report: **actionable vs control book**,
by setup, by market regime.
**Verify:** 84→ tests pass; live `--score` works; synthetic demo shows the split.
**Notes:** Empty until ~7d of live scans mature trades. 1 unit/trade, horizon exit,
overlap-ignored equity (stated in the report).

## 2026-06-07 — Live market-regime gating · Claude
**Why:** Backtest showed edge is regime-conditional; gate each setup to its
favorable BTC regime.
**Changes:** `indicators.market_alignment` / `market_conviction_adjustment` /
`setup_has_edge` + edge map; `scanner` computes `trend_regime(BTC)` per scan, folds
alignment into conviction (±`MARKET_ALIGN_SWING`=12), `classify_tier` demotes
adverse non-extreme to DIGEST; `formatting` adds 🧭 market line + mutes
breakdown_risk direction; `storage` persists `market_regime`; `RSI_MARKET_GATING`.
**Verify:** 80 tests; dry-run showed BTC=DOWNTREND → adverse setups held to digest,
0 INSTANT.
**Notes:** edge map: mean_reversion→CHOP, dip_buy/trend_continuation→BULL,
breakdown_risk→never.

## 2026-06-07 — Backtester: deeper history + market-regime split · Claude
**Why:** 2y window was one regime (missed the 2022 bear); must separate bull/bear.
**Changes:** `backtest.py` — paginated Binance fetch (5y), `market_regime_series`
(BTC bull/bear/chop), `summarize_market`/`format_market`, default `--days 1460`.
**Verify:** 5y/39-coin run; balanced coverage (BULL 22k / BEAR 15.7k / CHOP 8.7k).
**Notes:** KEY FINDING — blended averages hid regime-conditional edge (see AGENTS.md).

## 2026-06-07 — Backtester: point-in-time universe (survivorship fix) · Claude
**Why:** Using today's top-N over history is survivorship-biased.
**Changes:** `backtest.py` — `--pit`/`--pool`, CoinGecko market-cap history,
`build_pit_membership` (per-date top-N), `walk_coin` `member` mask gates
signals+base.
**Verify:** PIT run (114 coins, 365d). Confirmed breakdown_risk's "bounce" was
survivorship-inflated (~0 under PIT).
**Notes:** demo CoinGecko key caps history at 365d → small samples; pro key extends.

## 2026-06-07 — Backtester: conditional vol/momentum slice · Claude
**Why:** Does oversold-in-downtrend only continue down in high-vol crashes?
**Changes:** `backtest.py` — per-day vol/momentum features, `conditional_table`
(terciles, base conditioned on same bucket), `--slice`.
**Verify:** breakdown_risk bounces MORE in high vol — crash-continuation hypothesis
refuted.

## 2026-06-07 — Backtester: initial build · Claude
**Why:** Validate signal edge over years, not the ~1 week of live data.
**Changes:** new `backtest.py` — replays the pure functions over Binance 1d klines,
grades each setup vs its regime base rate (anti-tautology benchmark). Use
`data-api.binance.vision` (api.binance.com 451s from MSK).
**Verify:** first run overturned the live read — breakdown_risk "98%" was the
tautology trap; real edge in dip_buy/mean_reversion.

## 2026-06-07 — Split signal intent (setup_type) + re-grade history · Claude
**Why:** `favorable` was hardcoded mean-reversion, mislabeling continuation setups.
**Changes:** `indicators.setup_for` + `_SETUP_MAP`; `scanner` stamps
setup_type/expected_dir; `outcomes.favorable(expected_dir,…)` + setup-keyed
reports; `storage` columns + one-time lossless re-grade (meta `setup_regrade_v1`);
`formatting`/`telegram` show the setup hypothesis.
**Verify:** 61→65 tests; re-graded 197 historical outcomes losslessly.

## 2026-06-07 — Ops fixes: bot.log spam, token leak, dead return · Claude
**Why:** Listener spammed ~18k identical DNS errors (with the bot token in the URL);
`telegram.listen()` had an unreachable `return added` (NameError on Ctrl-C).
**Changes:** `telegram.py` — `_Unreachable` for transient net errors, once-per-outage
log + exponential backoff, removed dead `return`; `config.redact_token`;
`notifications.py` scrubs token in logs.
**Verify:** 61 tests; listener restarted clean; truncated the 6.8MB bot.log.
