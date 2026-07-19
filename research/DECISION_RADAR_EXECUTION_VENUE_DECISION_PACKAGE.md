# Decision Radar execution-venue decision package

Status: **operator decision confirmed: Bybit USDT-linear perpetuals, public
market data only; the bounded public adapter and immutable exact-response
capture contract are implemented but inactive, no genuine capture exists, and
no credential, private-data access, order path, or trading permission is
active**.

This is the concise operator view of
`crypto_radar_execution_quality_readiness_v10`. Run
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
the exact native instrument IDs. The single-catalog completeness and limit rule
follows Bybit's official
[instruments-info contract](https://bybit-exchange.github.io/docs/v5/market/instrument).

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

The primary Protocol-v2 cost currency is now explicitly sealed as native USDT.
Spread and impact remain basis points; depth, notionals, fees, funding, and P&L
remain USDT where currency-valued. No field is relabeled as USD and no 1:1
equivalence is assumed. A future cross-venue USD view would require a separate
explicit conversion source, observation clock, and policy and would not replace
the native Bybit cost evidence. This unit decision does not seal fee schedules,
order style, notional tiers, slippage, funding treatment, latency cost, or the
final Protocol-v2 annex.

The fee source is not sealed. Bybit's current public
[fee reference](https://www.bybit.com/en/help-center/article/Trading-Fee-Structure)
is useful product documentation, but it explicitly makes actual rates dependent
on region and account tier; the public reference table is not account- or
symbol-authoritative. Bybit's official authenticated
[`/v5/account/fee-rate` endpoint](https://bybit-exchange.github.io/docs/v5/account/fee-rate)
could report an account rate, but it requires credentials and private account
access outside the confirmed public-market-data-only boundary. The project does
not authorize or call it. The operator must later choose and seal either a
fixed, dated research fee assumption or a separately authorized exact fee
source, together with entry/exit order style, USDT notional tiers, spread and
visible-book impact application, beyond-book slippage, funding treatment,
latency cost, and unavailable-cost behavior. No numerical fee is inferred here.

The selected Bybit capability now advertises only the actual native snapshot
fields: USDT depth bands, USDT-notional side-specific price impact, native
notional currency, and exact provider/snapshot/acquisition clocks and book
sequences. Generic `*_usd_*` fields remain an explicitly inactive future cross-
venue interface. They are not required by the selected adapter, and no generic
USD projection is available. This prevents the readiness catalog from implying
that native USDT evidence was converted when it was not.

The visible-book impact primitive is also closed against double counting. Each
buy or sell impact value is measured from `mid_price`, so the market-crossing
half-spread for that side is already included before any extra depth is walked.
Do not add standalone `spread_bps` to the same side impact. A round trip needs
an entry-side impact from the entry snapshot and an exit-side impact from the
exit snapshot. Which snapshots, sizes, and order style Protocol v2 will use
remain unsealed; this rule does not manufacture a round-trip cost.

## Venue-native derivatives context contract

The selected surface now has an offline, fail-closed derivatives-context
normalizer. It consumes already-supplied public Bybit V5 bytes for the exact
execution-quality instrument and produces one point-in-time context snapshot:

- current mark/index price, mark-index basis, 24-hour return, current funding,
  next funding time, turnover, volume, and open interest from the ticker;
- the latest two settled funding observations;
- the latest two 1h open-interest observations and their explicit percentage-
  point change; and
- the latest two 1h long/short account-ratio observations.

The request plan is fixed at four public GETs per instrument and is bounded to
120 requests for the future top-30 intersection. The offline module has no HTTP
client. A guarded no-write adapter is implemented but inactive. Its readiness
requires a genuine fresh execution-quality capture for exact current authority
plus separately present `RSI_DECISION_RADAR_BYBIT_DERIVATIVES_LIVE=1`; confirmed
collection never retries, preserves exact response bytes and request clocks in
memory, and revalidates the capture/instrument/authority chain after the final
response. A closed no-I/O capture-input contract rederives every context, unit,
clock, lineage row, and deterministic identity from those exact bytes and
rejects mapping-only diagnostic responses. Confirmed capture writes one
descriptor-anchored immutable namespace, manifest, completion receipt, and
rollback-protected latest pointer. Read-only status and the standard review
export fully revalidate it from raw bytes. Guarded live/capture v3 preserves
acquisition freshness and re-evaluates every composite context's oldest
provider-response clock at full-set completion. The exact 15-second policy,
maximum completion age, and acquisition/completion states survive every
immutable surface; exact responses must form one ordered non-overlapping
window. A complete aged capture remains evidence but is not Protocol-v2
input-quality eligible. No genuine capture exists in the current store, and
this boundary never creates authorization,
credentials, notifications, orders, or trading capability. It rejects
future/misordered rows, identity/category drift, incomplete lineage,
implausible funding/basis/returns, and the known
`10.0`-as-fraction 100x return-unit error; stale snapshots remain explicitly
stale instead of being promoted. Every normalized row is
explicitly context-only, non-directional, policy-neutral, annex-unbound, and
Protocol-v2-ineligible. Run its zero-call proof with:

```sh
make radar-derivatives-bybit-smoke PYTHON=.venv/bin/python
make radar-derivatives-bybit-readiness PYTHON=.venv/bin/python
make radar-derivatives-bybit-status PYTHON=.venv/bin/python
```

The exact official contracts are [ticker](https://bybit-exchange.github.io/docs/v5/market/tickers),
[funding history](https://bybit-exchange.github.io/docs/v5/market/history-fund-rate),
[open interest](https://bybit-exchange.github.io/docs/v5/market/open-interest),
and [long/short account ratio](https://bybit-exchange.github.io/docs/v5/market/long-short-ratio).
Coinalyze remains useful as an optional secondary Catalyst-Radar cross-check,
but it is not the selected venue and cannot substitute for Bybit-native
execution, funding, OI, positioning, identity, or clocks.

Liquidations are not silently claimed from that REST bundle. Bybit's native
surface is the separate public `allLiquidation.{symbol}` WebSocket topic. An
offline exact-message v1 normalizer now preserves message fingerprints,
instrument identity, message/event/receipt clocks, provider side, documented
liquidated-position semantics, base-asset size, bankruptcy price, and derived
USDT notional. It rejects duplicate JSON keys, non-finite or nonpositive values,
identity/schema drift, and events later than their containing message. It does
not open a socket or create authorization, aggregation, policy, direction, or
Protocol-v2 eligibility. A separate confirmation-gated local-import boundary
can now seal operator-attested subscribe, acknowledgement, and observed data
application payloads into one exact immutable namespace with normalized events,
manifest, and completion receipt. It publishes no latest pointer and explicitly
claims neither TLS/WebSocket framing, project-owned transport, gap-free stream
coverage, silent-interval absence, campaign/dashboard authority, nor Protocol-v2
evidence. A genuine project listener and bounded window capture remain separate
future work and require explicit authorization and a permitted endpoint; until
then, liquidation coverage remains unavailable. The offline proofs are:

```sh
make radar-derivatives-bybit-liquidation-smoke PYTHON=.venv/bin/python
make radar-derivatives-bybit-liquidation-capture-smoke PYTHON=.venv/bin/python
```

An operator-supplied transcript can be checked without writes using:

```sh
make radar-derivatives-bybit-liquidation-validate-local \
  BYBIT_LIQUIDATION_TRANSCRIPT=/absolute/path/to/transcript.json \
  PYTHON=.venv/bin/python
```

Sealing it additionally requires `CONFIRM=1`; status always requires the exact
returned namespace. Neither command infers a latest capture or attaches it to
product evidence.

Official contracts reviewed 2026-07-19:
[All Liquidation](https://bybit-exchange.github.io/docs/v5/websocket/public/all-liquidation)
and [WebSocket Connect](https://bybit-exchange.github.io/docs/v5/ws/connect).

After a genuine current execution-quality capture exists, the exact operator
sequence is: set the separate flag only in the local ignored environment;
rerun the no-call readiness command; run `CONFIRM=1 make
radar-derivatives-bybit-capture PYTHON=.venv/bin/python` once; inspect the
immutable status; then unset the flag. Stop on any 403, 429, region restriction, malformed
response, or prerequisite drift. Do not retry or bypass it. This diagnostic
collection does not publish evidence; only the separately
confirmed capture command may publish the exact response bundle.

## Next point-in-time intraday contract

The intended venue-native 1h/4h source is Bybit V5
`GET /v5/market/kline` on the same exact USDT-linear perpetual instrument IDs.
The offline completed-bar normalizer, guarded live boundary, and immutable
exact-response capture are implemented. They remain inactive until a genuine
execution-quality capture first proves the same current Bybit boundary and
separate intraday authorization plus confirmation exist. A completed intraday
bundle remains detached from the campaign and Protocol-v2 evidence until the
sealed annex explicitly binds its capture ID.

Guarded live/capture v4 treats the native set as one sequential point-in-time
collection. It preserves each bar's acquisition freshness, re-evaluates every
bar-close and provider-response clock when the final request completes, and
uses only that completion state for input-quality eligibility. An early response
that ages past 15 seconds before completion therefore cannot leave the set
eligible; the exact aged bundle may still be retained for audit.

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
- That audit surface is implemented through the shared append-only Decision
  campaign review-timing ledger. Availability is conservatively proven by the
  exact owned-dashboard operations receipt; first view and completion require
  separate confirmed human commands. Dashboard requests never create events.
  The campaign report revalidates every receipt/candidate/Core/projection
  binding and applies a point-in-time cutoff, while all timing rows remain
  Protocol-v2-ineligible until the annex seals clock, censoring, missing-action,
  and latency-cost rules.
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
  explicit `CONFIRM=1` boundary. Capture v4 uses one complete
  `category=linear&status=Trading&limit=1000` catalog request, rejects a
  missing or non-empty continuation cursor as incomplete, and then uses one 200-level
  order-book request per exact eligible instrument. The absolute bound is 31
  GETs; the current 29-candidate universe bound is 30, while the actual count is
  one plus the eligible-instrument count. It makes no retries and stops on the
  first 403, 429, regional restriction, malformed response, or authority
  failure. Non-contract-shaped
  symbols are rejected before the provider boundary rather than consuming a
  request or silently disappearing. Only a complete run publishes an immutable
  bundle containing the closed authority/full-query-excluded universe, exact
  accepted response bytes, request timing, normalized USDT observations,
  fingerprints, manifest, completion receipt, and latest pointer. The bundle is fully
  rederived and validated before pointer publication and review export.
- Treat execution quality as one point-in-time set, not merely a collection of
  individually fresh books. Preserve acquisition freshness for every book, then
  re-evaluate every provider clock when the final book completes. A set may be
  `protocol_v2_input_quality_eligible` only when every book is still within the
  15-second policy at that completion time; valid but aged sets remain immutable
  evidence with input-quality eligibility false.
- Bind exact acquisition to transport truth. For an immutable capture,
  `acquired_at` is the corresponding response-read completion time. Every
  request/response must fit the declared capture window and remain sequential;
  the raw response index and normalized book must carry the identical clock.
- Keep capture quality distinct from Protocol-v2 evidence authority. A fresh
  complete capture may be `protocol_v2_input_quality_eligible`, but it remains
  `protocol_v2_evidence_eligible=false` and `protocol_v2_annex_bound=false`
  until the sealed annex explicitly binds the immutable capture ID. Never
  rewrite a historical capture to promote it.
- Seal point-in-time sources, partitions/untouched holdout, outcomes, fees,
  spread/depth/impact rules, latency, universe, routes, episodes, and minimum
  samples in the Protocol-v2 annex.
- Implement immutable capture/publication for the reviewed closed-candle 1h/4h
  contract only after the first genuine execution-quality capture proves the
  permitted Bybit boundary. The no-write collector already has a separate
  authorization, confirmation, exact two-GETs-per-instrument budget, and
  post-response authority recheck; do not broaden the execution-quality flag
  silently.
- Keep the sealed native-USDT cost-unit policy intact. Do not represent USDT
  depth, notionals, fees, funding, or P&L as USD; any later cross-venue
  conversion needs a separately sealed source, clock, and policy.

The safe implementation smoke is:

```sh
make radar-execution-quality-bybit-smoke PYTHON=.venv/bin/python
make radar-derivatives-bybit-smoke PYTHON=.venv/bin/python
make radar-derivatives-bybit-readiness PYTHON=.venv/bin/python
make radar-intraday-bybit-smoke PYTHON=.venv/bin/python
make radar-intraday-bybit-readiness PYTHON=.venv/bin/python
make radar-intraday-bybit-status PYTHON=.venv/bin/python
make radar-execution-quality-bybit-readiness PYTHON=.venv/bin/python
make radar-execution-quality-bybit-status PYTHON=.venv/bin/python
```

All eight commands perform no network call, read no credential, and have no
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
  claim that all 29 candidate joins are canonically confirmed contracts. The
  exact inactive capture-v2 request bound is 30: one complete instrument
  catalog with an explicit empty continuation cursor plus no more than 29 order books.
- The execution-quality live adapter and immutable capture contract exist but
  are inactive; no genuine capture exists and live spread remains unavailable.
- Venue-native ticker/funding/OI/positioning normalization is fixture-proven and
  context-only; its guarded no-write adapter exists but no immutable genuine
  derivatives capture exists. Current readiness is blocked before the provider
  boundary by the absent execution-quality capture and separate authorization.
- The direct 1h/4h completed-bar offline contract exists and is fixture-proven;
  its separately authorized live boundary and immutable exact-response capture
  exist with full-set completion freshness and exact sequential timing, but are
  inactive behind the missing execution-quality proof and intraday authorization.
- No capture is Protocol-v2 evidence and no capture ID is annex-bound.
- Current Bybit reachability remains unverified after the recorded 403.
- No provider call is planned or attempted by readiness.
- No Protocol-v2 holdout is defined, opened, or evaluated.
- No production threshold, route, score, notification, or authority changes.
- Research only; no sends, orders, trades, paper trades, RSI writes, or fade
  triggers.
