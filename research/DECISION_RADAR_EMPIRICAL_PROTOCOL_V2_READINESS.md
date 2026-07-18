# Decision Radar empirical Protocol-v2 readiness

Status: **required-evidence contract frozen/static; executable protocol blocked
and not frozen; holdout unopened**.

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

- intended venue, instrument mode, quote, exact eligible instruments, and
  jurisdiction/account plus public/private-data boundaries;
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

No venue or provider is selected by this document. No order or trading
permission is requested.

## Safe commands

```sh
make radar-research-protocol-v2-readiness PYTHON=.venv/bin/python
make radar-research-protocol-v2-check PYTHON=.venv/bin/python
make radar-execution-quality-readiness PYTHON=.venv/bin/python
```
