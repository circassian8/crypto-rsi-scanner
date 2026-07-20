# Decision Radar empirical Protocol-v2 current progress

Status: **Bybit USDT-linear perpetual research surface selected; evidence
collection and the executable Protocol-v2 annex remain blocked**.

This is the mutable current-progress companion to the immutable 2026-07-16
readiness contract. It does not replace or rewrite
`DECISION_RADAR_EMPIRICAL_PROTOCOL_V2_READINESS.md` or its fingerprinted
implementation. The frozen contract remains byte-identical at readiness
SHA-256 `683f03fe74306a80acaebf2556e2652cc67e9c725d97deb6dd083b3b28109603`.

## Confirmed

- venue: Bybit;
- instrument mode: USDT-linear perpetuals;
- quote currency: USDT;
- primary cost currency: native USDT, with no USD conversion or 1:1 equivalence;
- selected execution-quality fields: native USDT depth and USDT-notional
  side-impact fields; the generic USD projection is inactive and unavailable;
- each side impact is mid-referenced and already includes its crossing
  half-spread, so standalone spread cannot be added to that same side;
- buy size is exact USDT spent and sell size is exact USDT proceeds, so equal
  numeric notionals do not prove equal base quantity; the pure round-trip v3
  model instead carries one exact `qtyStep`-aligned base quantity through two
  distinct books and independently causal entry/exit catalog constraints;
- target-mid-notional sizing can floor one supplied USDT reference to the venue
  quantity step and rederive an exact two-book scenario, while final tiers and
  adoption of that rounding rule remain unsealed;
- the read-only capture-pair contract can fully rederive a modeled round trip
  from two exact immutable capture namespaces without guessing a latest
  pointer; no genuine capture pair or annex binding exists;
- pure taker-fee arithmetic applies separately supplied fractional rates to
  each leg's exact executed USDT value, but fee rates and source authority
  remain unsealed;
- pure funding arithmetic applies exact signed settlement transfers and can
  strictly reconcile and aggregate supplied events against one bounded,
  operator-supplied expected schedule. This proves only that supplied schedule;
  authoritative schedule/rate/mark coverage and holding policy remain unsealed;
- pure composite cost arithmetic fully rederives those fee and funding
  projections from the same exact round trip before combining them with
  visible-book drag. It preserves side-specific executed-value fees and remains
  incomplete without latency, beyond-book slippage, unavailable-cost policy,
  authoritative sources, and annex binding;
- exact-universe rule: top 30 liquidity-ranked Radar assets intersected with
  active `LinearPerpetual`, `Trading`, USDT-quoted, USDT-settled,
  non-prelisting Bybit contracts;
- data boundary: public market data only;
- jurisdiction/account eligibility for this research scope: confirmed by the
  owner on 2026-07-17;
- no credentials, private account data, orders, execution, or trading.

## Still unresolved

- exact eligible native instrument IDs are not captured or sealed;
- permitted Bybit public reachability remains unproven after the recorded 403;
- no genuine execution-quality capture exists;
- no genuine direct 1h/4h capture exists, so its 14-period point-in-time Wilder
  RSI projections are also absent; the v2 offline contract is ready and keeps
  insufficient history explicit rather than inventing a value;
- no genuine Bybit REST funding/open-interest/positioning capture exists;
- the primary currency unit is sealed as native USDT, but the fee schedule,
  order style, notional tiers, final quantity policy, spread/impact application,
  slippage, funding policy and sources, latency-cost, and unavailable-cost rules
  remain unsealed;
- Bybit's public fee table is not treated as account- or symbol-authoritative,
  while its authenticated account fee-rate endpoint remains outside the
  confirmed public-only boundary and is neither authorized nor called;
- Bybit liquidation evidence is a separate public-WebSocket surface. The exact
  `allLiquidation.{instrument_id}` message normalizer is implemented and
  fixture-proven. Detached immutable operator-transcript import is also
  implemented for exact subscribe, acknowledgement, and observed data
  application payloads, but it proves neither project-owned transport nor
  continuous stream coverage. No live listener, runtime authorization, genuine
  capture, or Protocol-v2 binding exists;
- Tokenomist v5 cliff-unlock response normalization and a strict immutable
  synthetic-fixture capture/doctor are implemented. The disposable capture
  proves exact request/source bytes, units, clocks, complete versus
  healthy-empty versus partial-page state, and artifact mechanics, then retains
  nothing. It does not prove a subscription, live transport, multi-page
  acquisition, genuine provider bytes, source authority, or Protocol-v2
  eligibility; v4 remains deprecated and live-ineligible;
- sources, partitions and untouched holdout, outcomes, costs, universe, routes,
  episodes, minimum samples, and final human annex approval remain unsealed.

No Protocol-v2 replay, selection, or final-test target exists. The holdout is
undefined and unopened. Missing evidence remains unavailable and cannot be
proxied.

## Safe commands

```sh
make radar-research-protocol-v2-progress PYTHON=.venv/bin/python
make radar-research-protocol-v2-progress-check PYTHON=.venv/bin/python
make radar-execution-quality-readiness PYTHON=.venv/bin/python
make radar-intraday-bybit-readiness PYTHON=.venv/bin/python
make radar-derivatives-bybit-readiness PYTHON=.venv/bin/python
make radar-derivatives-bybit-liquidation-smoke PYTHON=.venv/bin/python
make radar-derivatives-bybit-liquidation-capture-smoke PYTHON=.venv/bin/python
make radar-unlock-tokenomist-v5-readiness PYTHON=.venv/bin/python
make radar-unlock-tokenomist-v5-capture-smoke PYTHON=.venv/bin/python
```
