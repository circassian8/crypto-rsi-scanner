# Decision Radar execution-venue decision package

Status: **human decision required; no venue, provider, adapter, credential, or
trading permission selected**.

This is the concise operator view of
`crypto_radar_execution_quality_readiness_v3`. Run
`make radar-execution-quality-readiness PYTHON=.venv/bin/python` for the full
static report or add `-json` to the target name for its closed structured form.
Both commands read no environment, credentials, files, providers, or holdout
data and perform no writes or network calls.

## Feasible choices

| Choice | Mode and quote | Public data and credentials | Quality and impact surface | Mapping, limits, and constraints | Protocol-v2 use |
|---|---|---|---|---|---|
| Binance | Spot or perpetual; operator seals exact native quote | Public order book expected without credentials | Bid/ask, spread, depth bands, and notional impact can be derived from observed books | Exact instrument mapping; dynamic exchange request weights; operator confirms current jurisdiction/account eligibility | Strong candidate after exact surface and costs are sealed |
| Bybit | Spot or perpetual; operator seals exact native quote | Public order book expected without credentials, but current project egress has a recorded region-restricted 403 | Bid/ask, spread, depth bands, notional impact, and book sequence | Exact instrument mapping; use a bounded budget far below the documented ceiling; no proxy, VPN, or region bypass | Conditional on honest reachability and eligibility |
| Coinbase Exchange | Spot; operator seals exact native quote | Public order book expected without credentials | Bid/ask, spread, depth bands, sequence, and notional impact | Exact product mapping; documented public REST rate/burst limits; operator confirms eligibility | Suitable for a spot-only protocol |
| Kraken | Spot; operator seals exact native quote | Public pre-trade depth expected without credentials | Bid/ask and spread; depth/impact must be labeled truncated to the available top levels | Exact pair mapping; conservative public request cadence; operator confirms eligibility | Suitable for spot with explicit limited-depth caveat |
| Operator-selected DEX | DEX; chain, token contracts, pool/router, and quote are all required | RPC or quote-provider access and credentials are unknown until selected | Route-specific quote, impact, gas, block, pool/router, and freshness evidence | Exact chain/token/route identity; provider limits and jurisdiction remain unknown | Conditional; cannot be evaluated before the chain and provider decision |
| Multiple-venue research | Comparative read-only mode; every native quote stays explicit | Separate public CEX books expected without credentials; DEX boundary remains provider-specific | Per-venue spread, depth, and impact stay separate and are never blended into false certainty | Exact cross-venue mapping and independent eligibility/request budgets for every venue | Useful for robustness research, but cannot close the primary cost model until one execution surface is sealed |

Public market-data reachability is not trading eligibility. Every option needs a
separate current jurisdiction/account decision. No option requests an API key,
private account data, wallet access, an order endpoint, or permission to trade.

## Human decision template

Copy and complete these six fields exactly:

```text
intended_venue=<binance|bybit|coinbase_exchange|kraken|dex_operator_selected|multiple_venue_research>
instrument_mode=<spot|perpetual|dex|comparative_read_only>
quote_currency=<exact quote asset or explicit per-venue native-quote policy>
eligible_instrument_set=<exact bounded instrument ids>
jurisdiction_and_account_eligibility_confirmation=<confirmed with date and scope>
expected_public_private_data_boundary=<public-only reads|private reads required and separately authorized>
```

If multiple-venue research is chosen, also name the exact included venues and
one primary execution surface or explicitly leave Protocol v2 blocked. Selecting
an option does not activate it. A later, separately reviewed read-only adapter
and provider authorization boundary would still be required.

## Current boundary

- Protocol-v2 executable protocol remains unfrozen and blocked.
- No execution-quality live adapter exists.
- No spread provider is selected.
- No provider call is planned or attempted by readiness.
- No Protocol-v2 holdout is defined, opened, or evaluated.
- No production threshold, route, score, notification, or authority changes.
- Research only; no sends, orders, trades, paper trades, RSI writes, or fade
  triggers.
