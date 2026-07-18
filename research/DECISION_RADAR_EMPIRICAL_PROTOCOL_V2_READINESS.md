# Decision Radar empirical Protocol-v2 readiness

Status: **required-evidence contract frozen/static; executable protocol blocked
and not frozen; confirmed venue decision recorded separately; holdout unopened**.

- Contract: `decision_radar_empirical_validation_v2_readiness_v1`
- Proposed executable protocol: `decision_radar_empirical_validation_v2`
- Readiness SHA-256:
  `683f03fe74306a80acaebf2556e2652cc67e9c725d97deb6dd083b3b28109603`
- Protocol-v2 replay/selection/final targets: none
- Protocol-v2 holdout defined/accessed: no / no
- Protocol-v1 final-test reuse for tuning: forbidden
- Research only; zero provider calls, credential/environment/file reads, writes,
  sends, trades, orders, paper trades, RSI writes, fade triggers, or pointer
  changes.

## Current decision progress after the frozen contract

The frozen 2026-07-16 requirements object and its SHA-256 remain byte-for-byte
unchanged. It intentionally records the unresolved placeholders that existed at
freeze time. The current readiness view now renders later accepted human
decisions separately so historical contract evidence and present operator truth
are not conflated.

Confirmed:

- venue: Bybit;
- instrument mode: USDT-linear perpetuals;
- quote currency: USDT;
- universe rule: top 30 liquidity-ranked Radar assets intersected with exact
  active `LinearPerpetual`, `Trading`, USDT-quoted, USDT-settled,
  non-prelisting contracts;
- data boundary: public market data only, with no credentials, private account
  data, orders, execution, or trading;
- jurisdiction/account eligibility for this research scope: owner-confirmed on
  2026-07-17.

Still unresolved:

- the exact eligible instrument IDs have not been captured and sealed;
- permitted Bybit public reachability remains unproven after the recorded 403;
- no genuine execution-quality capture exists;
- exact sources, partitions/untouched holdout, outcomes, costs, universe,
  routes, episodes, minimum samples, and final human annex approval remain
  unsealed.

This progress overlay makes zero provider calls, creates no authorization, and
does not freeze or activate Protocol v2.

## Required evidence

An executable protocol must bind genuine point-in-time evidence for:

1. 1h and 4h market observations;
2. exact idea availability, first view, review completion, and latency clocks;
3. observed execution-venue bid/ask, spread, and depth;
4. catalyst publication and observation timing;
5. official calendar events and uncertainty windows;
6. derivatives funding, open interest, and liquidation context;
7. on-chain metric/block-time context;
8. Wilder-RSI context at the closed candle available to the idea.

Every source requires immutable lineage, point-in-time availability, freshness,
timezone, and acquisition-time rules. Missing evidence is `unavailable`.
Invented, current-metadata, retrospective, and proxy substitution is forbidden.

## Annex required before activation

The executable protocol remains blocked until a human-approved, digest-bound
annex fixes all of the following before an untouched holdout is read:

- the confirmed venue, instrument mode, quote, jurisdiction/account, and
  public-data boundary plus the still-unsealed exact eligible instruments;
- exact providers/datasets/endpoints and authorization boundaries;
- development, validation, embargo/purge, outcome-maturity, and untouched
  holdout windows plus a holdout content commitment and access ledger;
- primary/sensitivity outcomes and missing/pending rules;
- fees, observed spread/depth, impact, slippage, and latency costs;
- point-in-time universe and identity/listing rules;
- exact Decision model/route definitions and code/policy digests;
- single-asset and market-wide episode handling and correlated-repeat rules;
- aggregate and route/bias/regime/liquidity/quality minimum samples plus the
  multiple-comparison policy.

The frozen requirements object itself selected no venue. The later accepted
decision selects Bybit only as the intended public research surface; it does
not select exact instrument IDs, create provider authorization, or request
order/trading permission.

## Safe commands

```sh
make radar-research-protocol-v2-readiness PYTHON=.venv/bin/python
make radar-research-protocol-v2-check PYTHON=.venv/bin/python
make radar-execution-quality-readiness PYTHON=.venv/bin/python
```
