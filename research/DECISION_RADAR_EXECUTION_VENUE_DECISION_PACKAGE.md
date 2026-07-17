# Decision Radar execution-venue decision package

Status: **operator decision confirmed: Bybit USDT-linear perpetuals, public
market data only; no live provider adapter, credential, private-data access,
order path, or trading permission is active**.

This is the concise operator view of
`crypto_radar_execution_quality_readiness_v4`. Run
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
It does not guess multiplier contracts such as `1000TOKENUSDT`.

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

## Remaining engineering and sealing work

- Freeze the exact bounded instrument IDs from one complete point-in-time
  universe intersection; the confirmed rule is not itself an instrument list.
- Prove the official public endpoint is honestly reachable. The recorded 403
  remains a blocker and must not be bypassed with a proxy, VPN, or alternate
  region route chosen by the code.
- Add a separately reviewed, authorization-gated public-read adapter only after
  reachability is established. The current implementation is an offline
  fixture parser and request description only.
- Seal point-in-time sources, partitions/untouched holdout, outcomes, fees,
  spread/depth/impact rules, latency, universe, routes, episodes, and minimum
  samples in the Protocol-v2 annex.
- Resolve the explicit USDT cost-unit policy before any field is represented as
  USD. The offline normalizer reports USDT depth and USDT notionals and does not
  silently assume a 1:1 conversion.

The safe implementation smoke is:

```sh
make radar-execution-quality-bybit-smoke PYTHON=.venv/bin/python
```

It reads checked fixtures, performs no network call, reads no credential, and
has no private-data or order operation. Static current truth remains available
through `make radar-execution-quality-readiness PYTHON=.venv/bin/python`.

## Current boundary

- Protocol-v2 executable protocol remains unfrozen and blocked.
- Bybit USDT-linear perpetuals are selected as the intended primary surface.
- The exact bounded instrument set is not yet frozen.
- No execution-quality live adapter exists; live spread remains unavailable.
- Current Bybit reachability remains unverified after the recorded 403.
- No provider call is planned or attempted by readiness.
- No Protocol-v2 holdout is defined, opened, or evaluated.
- No production threshold, route, score, notification, or authority changes.
- Research only; no sends, orders, trades, paper trades, RSI writes, or fade
  triggers.
