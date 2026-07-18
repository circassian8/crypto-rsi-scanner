# Decision Radar execution-venue decision package

Status: **operator decision confirmed: Bybit USDT-linear perpetuals, public
market data only; the bounded public adapter and immutable exact-response
capture contract are implemented but inactive, no genuine capture exists, and
no credential, private-data access, order path, or trading permission is
active**.

This is the concise operator view of
`crypto_radar_execution_quality_readiness_v6`. Run
`make radar-execution-quality-readiness PYTHON=.venv/bin/python` for the full
static report or add `-json` to the target name for its closed structured form.
Both commands read no environment, credentials, files, providers, or holdout
data and perform no writes or network calls.

## Confirmed primary surface

The owner confirmed the following on 2026-07-17:

```text
intended_venue=bybit
instrument_mode=perpetual
quote_currency=USDT
eligible_instrument_set=top 30 liquidity-ranked Decision Radar assets intersected with active exact Bybit USDT linear-perpetual contracts; freeze the resulting IDs when the Protocol-v2 annex is sealed
jurisdiction_and_account_eligibility_confirmation=confirmed by the owner on 2026-07-17 for this research scope
expected_public_private_data_boundary=public market data only; no credentials or private account data
```

The exact instrument list is intentionally not claimed yet. It must come from a
point-in-time, complete Bybit instrument snapshot and exact canonical-asset
mapping, then be frozen in the Protocol-v2 annex before any holdout is defined
or read. The mapper accepts only `category=linear`, `contractType=LinearPerpetual`,
`status=Trading`, `quoteCoin=USDT`, `settleCoin=USDT`, and non-prelisting rows.
It does not guess multiplier contracts such as `1000TOKENUSDT`. Before any
provider call, symbols that cannot form the closed Bybit base-contract shape
are excluded with a reason code. The immutable capture retains the full ranked
Radar universe, the exact provider-query subset, and every exclusion. The
remaining exact-symbol join is explicitly a candidate join; human confirmation
of canonical asset identity remains pending until the Protocol-v2 annex seals
the exact native instrument IDs.

## Feasibility record

| Choice | Mode and quote | Public data and credentials | Quality and impact surface | Mapping, limits, and constraints | Protocol-v2 use |
|---|---|---|---|---|---|
| Binance | Spot or perpetual; operator seals exact native quote | Public order book expected without credentials | Bid/ask, spread, depth bands, and notional impact can be derived from observed books | Exact instrument mapping; dynamic exchange request weights; operator confirms current jurisdiction/account eligibility | Strong candidate after exact surface and costs are sealed |
| Bybit | **Selected:** USDT-linear perpetual | Public order book expected without credentials, but current project egress has a recorded region-restricted 403 | Bid/ask, spread, USDT depth bands, USDT-notional impact, and book sequence | Exact active-contract mapping; bounded read budget; no proxy, VPN, or region bypass | Primary Protocol-v2 cost surface after exact set, sources, and costs are sealed |
| Coinbase Exchange | Spot; operator seals exact native quote | Public order book expected without credentials | Bid/ask, spread, depth bands, sequence, and notional impact | Exact product mapping; documented public REST rate/burst limits; operator confirms eligibility | Suitable for a spot-only protocol |
| Kraken | Spot; operator seals exact native quote | Public pre-trade depth expected without credentials | Bid/ask and spread; depth/impact must be labeled truncated to the available top levels | Exact pair mapping; conservative public request cadence; operator confirms eligibility | Suitable for spot with explicit limited-depth caveat |
| Operator-selected DEX | DEX; chain, token contracts, pool/router, and quote are all required | RPC or quote-provider access and credentials are unknown until selected | Route-specific quote, impact, gas, block, pool/router, and freshness evidence | Exact chain/token/route identity; provider limits and jurisdiction remain unknown | Conditional; cannot be evaluated before the chain and provider decision |
| Multiple-venue research | Comparative read-only mode; every native quote stays explicit | Separate public CEX books expected without credentials; DEX boundary remains provider-specific | Per-venue spread, depth, and impact stay separate and are never blended into false certainty | Exact cross-venue mapping and independent eligibility/request budgets for every venue | Useful for robustness research, but cannot close the primary cost model until one execution surface is sealed |

Public market-data reachability is not trading eligibility. Every option needs a
separate current jurisdiction/account decision. No option requests an API key,
private account data, wallet access, an order endpoint, or permission to trade.

The Bybit normalized snapshot is deliberately narrower than “venue liquidity.”
It binds the requested 200 visible REST levels, explicitly records that RPI
orders are excluded by the provider, and labels USDT impact as a deterministic
walk of those visible levels rather than realized execution. Buy size means
exact USDT spent; sell size means exact USDT proceeds. These definitions must
remain explicit in any Protocol-v2 cost annex. See the official
[Bybit order-book contract](https://bybit-exchange.github.io/docs/v5/market/orderbook).

## Next point-in-time intraday contract

The intended venue-native 1h/4h source is Bybit V5
`GET /v5/market/kline` on the same exact USDT-linear perpetual instrument IDs.
The offline completed-bar normalizer and fixtures are implemented; the live
adapter and immutable provider capture remain intentionally unimplemented and
unauthorized until a genuine execution-quality capture first proves the same
Bybit boundary.

- Request `category=linear` with exact uppercase `symbol` and explicit
  `interval=60` or `interval=240`. Preserve the exact start/end query, response
  bytes, request/receive clocks, response clock, instrument identity, and one
  immutable lineage ID.
- Persist `startTime`, open, high, low, close, base-coin volume, and USDT
  turnover without silently renaming USDT as USD. The provider returns rows in
  reverse start-time order; canonical storage must order and deduplicate them
  explicitly.
- Exclude every still-open candle. The REST contract says its close is merely
  the last traded price until the candle closes, so a row is eligible only when
  its interval end is no later than the captured provider response clock. A
  partial bar can remain immutable raw evidence but cannot enter a temporal
  baseline, outcome, or Protocol-v2 partition.
- Treat direct 1h and direct 4h bars as separate evidence with their own
  coverage, missingness, and request lineage. Do not relabel CoinGecko
  sparklines, sparse campaign snapshots, locally interpolated prices, or a
  four-hour value inferred from an open one-hour bar as direct provider bars.
- Keep idea availability and human review latency separate from market HTTP
  latency. `idea_observed_at`, `idea_available_at`, first operator view, review
  completion, and their clock sources require their own exact audit evidence.
- Do not attach bars to the campaign or call them Protocol-v2 evidence until a
  separately authorized immutable capture exists and the sealed annex binds
  its exact source, freshness, universe, partition, and missing-data rules.

Official contracts reviewed 2026-07-18:
[Get Kline](https://bybit-exchange.github.io/docs/v5/market/kline),
[Get Bybit Server Time](https://bybit-exchange.github.io/docs/v5/market/time),
and [Rate Limit Rules](https://bybit-exchange.github.io/docs/v5/rate-limit).

## Remaining engineering and sealing work

- Freeze the exact bounded instrument IDs from one complete point-in-time
  universe intersection; the confirmed rule is not itself an instrument list.
- Prove the official public endpoint is honestly reachable. The recorded 403
  remains a blocker and must not be bypassed with a proxy, VPN, or alternate
  region route chosen by the code.
- Keep the implemented public-read adapter inactive until its dedicated runtime
  authorization already exists. Readiness binds to one exact authoritative
  Radar generation, and status validates the latest capture; neither makes a
  provider call or write. A capture attempt may run only through the additional
  explicit `CONFIRM=1` boundary, use at most two public GETs per requestable
  current Radar asset, make no retries, and stop on the first 403, 429, regional
  restriction, malformed response, or authority failure. Non-contract-shaped
  symbols are rejected before the provider boundary rather than consuming a
  request or silently disappearing. Only a complete run publishes an immutable
  bundle containing the closed authority/full-query-excluded universe, exact
  accepted response bytes, request timing, normalized USDT observations,
  fingerprints, manifest, completion receipt, and latest pointer. The bundle is fully
  rederived and validated before pointer publication and review export.
- Keep capture quality distinct from Protocol-v2 evidence authority. A fresh
  complete capture may be `protocol_v2_input_quality_eligible`, but it remains
  `protocol_v2_evidence_eligible=false` and `protocol_v2_annex_bound=false`
  until the sealed annex explicitly binds the immutable capture ID. Never
  rewrite a historical capture to promote it.
- Seal point-in-time sources, partitions/untouched holdout, outcomes, fees,
  spread/depth/impact rules, latency, universe, routes, episodes, and minimum
  samples in the Protocol-v2 annex.
- Implement the live/capture half of the reviewed closed-candle 1h/4h contract
  only after the first genuine execution-quality capture proves the permitted
  Bybit boundary. Give it a separate explicit authorization and request budget;
  do not broaden the execution-quality flag silently. The offline normalizer is
  already available and crosses no provider boundary.
- Resolve the explicit USDT cost-unit policy before any field is represented as
  USD. The offline normalizer reports USDT depth and USDT notionals and does not
  silently assume a 1:1 conversion.

The safe implementation smoke is:

```sh
make radar-execution-quality-bybit-smoke PYTHON=.venv/bin/python
make radar-intraday-bybit-smoke PYTHON=.venv/bin/python
make radar-execution-quality-bybit-readiness PYTHON=.venv/bin/python
make radar-execution-quality-bybit-status PYTHON=.venv/bin/python
```

All three commands perform no network call, read no credential, and have no
private-data or order operation. Static current truth remains available through
`make radar-execution-quality-readiness PYTHON=.venv/bin/python`. Only an
already-present `RSI_DECISION_RADAR_BYBIT_EXECUTION_QUALITY_LIVE=1` permits the
separate `radar-execution-quality-bybit-capture` target to cross the public
provider boundary, and that target additionally requires `CONFIRM=1`; unsetting
the flag disables capture. The `...-collect` target remains a stdout diagnostic
probe and does not publish evidence.

The exact operator sequence is intentionally split:

1. If the owner authorizes this bounded public-data attempt, add
   `RSI_DECISION_RADAR_BYBIT_EXECUTION_QUALITY_LIVE=1` to the local gitignored
   `.env`. The application never writes or changes this flag.
2. Rerun `make radar-execution-quality-bybit-readiness PYTHON=.venv/bin/python`.
   It must report `ready=true`, the exact Radar authority, and the current
   request bound before any call.
3. Run `CONFIRM=1 make radar-execution-quality-bybit-capture
   PYTHON=.venv/bin/python` once. Stop on any failure; do not retry or bypass a
   403/region restriction.
4. Validate the immutable result with
   `make radar-execution-quality-bybit-status PYTHON=.venv/bin/python`, then
   unset the flag to close the provider boundary.

## Current boundary

- Protocol-v2 executable protocol remains unfrozen and blocked.
- Bybit USDT-linear perpetuals are selected as the intended primary surface.
- The exact bounded instrument set is not yet frozen.
- Current no-call readiness projects 30 Radar assets into 29 provider-query
  candidates and one audited preflight exclusion (`FIGR_HELOC`); this is not a
  claim that all 29 candidate joins are canonically confirmed contracts.
- The execution-quality live adapter and immutable capture contract exist but
  are inactive; no genuine capture exists and live spread remains unavailable.
- The direct 1h/4h completed-bar offline contract exists and is fixture-proven;
  its separately authorized live/capture boundary does not yet exist.
- No capture is Protocol-v2 evidence and no capture ID is annex-bound.
- Current Bybit reachability remains unverified after the recorded 403.
- No provider call is planned or attempted by readiness.
- No Protocol-v2 holdout is defined, opened, or evaluated.
- No production threshold, route, score, notification, or authority changes.
- Research only; no sends, orders, trades, paper trades, RSI writes, or fade
  triggers.
