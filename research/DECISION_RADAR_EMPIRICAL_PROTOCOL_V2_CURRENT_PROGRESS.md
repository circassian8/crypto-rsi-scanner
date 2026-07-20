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
  visible-book drag. It preserves side-specific executed-value fees;
- pure decision-price latency arithmetic now compares exact supplied entry and
  exit best-bid/ask decision references with the later matching-engine books,
  preserves provider/acquisition/decision clocks and distinct lineages, and
  decomposes signed midpoint drift from visible-book impact without counting
  spread twice. A decision-reference composite fully rederives latency, book,
  fee, and funding components before accepting one native-USDT identity. No
  actual submission or fill is observed, so the result remains incomplete
  without sealed references and policy, beyond-book slippage, unavailable-cost
  behavior, authoritative fee/funding sources, and annex binding;
- residual-cost sensitivity now fully rederives that decision-reference
  composite and applies an explicit unsealed per-leg basis-point penalty to
  each exact executed USDT value. If the penalty is absent, the all-in cost and
  net remain unavailable rather than silently using zero. Even a supplied zero
  is unobserved sensitivity, not empirical evidence or a sealed policy;
- every new live/no-send row can now retain its exact point-in-time top-liquid
  membership/rank/set-size/limit/policy and a separate outcome-blind control
  liquidity tier. Campaign readiness and empirical projection v4 preserve exact
  coverage into the Research Lab without selecting controls, reading outcomes,
  backfilling old rows, or changing Decision policy;
- a prospective control-only market-regime collector now requires one complete
  same-clock top-liquid set with ready causal `temporal_return_24h` evidence.
  It compares BTC with the universe median, binds the input observations by
  digest, and writes `risk_on`, `risk_off`, or `mixed` only to those retained
  history rows. It does not expose the field to Decision evaluation. The 09:27
  UTC DNS failure and 10:27 UTC timeout were followed by a strict-clean 11:34
  UTC success. Prospective universe/liquidity context now covers 60 counted
  rows, but PUMP and WBT still lack closed causal 24-hour inputs in the latest
  complete universe, so market-regime coverage remains honestly zero;
- the canonical campaign report now derives a digest-bound all-category
  episode coverage frontier from the frozen Decision-v2 episode scorecard and
  copies it into the dashboard without re-evaluation. Current genuine evidence
  is three fixed-start episodes with four dependent repeats: two
  `dashboard_watch`, one `risk_watch`, and only `market_led` as the primary
  origin. The remaining six routes and six primary origins are explicit zero
  rows. This is descriptive only: minimum samples, statistical/cross-asset
  independence, matched controls, annex binding, and Protocol-v2 evidence
  eligibility all remain false;
- forward empirical live projection v5 now preserves that exact closed
  frontier for future empirical bundles and Research Lab rendering. Projection
  schemas v1-v4 remain readable, including full v4 control-context validation;
  an older source report becomes compatibility-unavailable rather than a
  fabricated zero frontier. The currently sealed Protocol-v1 report bundle is
  deliberately unchanged and therefore still carries its historical v1 live
  projection;
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
  slippage source and final policy, funding policy and sources,
  decision-reference source/clock rules, latency-cost policy, and the final
  unavailable-cost rule remain unsealed; the implemented fail-closed
  sensitivity mechanics do not choose those annex values;
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
- six of eight canonical routes and six of seven canonical primary origins
  still have no genuine fixed-start episode. A zero row means missing evidence,
  not strength, weakness, safety, or validation;
- prospective matched-control context remains incomplete: the current campaign
  has no successful post-implementation market-regime row and no sealed
  Protocol-v2 partition, so no complete match row or matched control is
  available. The campaign's exact-authority, manifest-digest-bound diagnostic
  proves the latest top-liquid generation has causal 24-hour regime inputs for
  28 of 30 rows. It identifies PUMP at rank 14 and WBT at rank 28 as missing the
  value, percent-point unit, and closed evidence reference; the collector
  correctly refuses to infer or backfill a regime from that incomplete set.

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
