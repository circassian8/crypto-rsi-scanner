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
```
