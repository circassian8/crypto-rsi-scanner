# DefiLlama protocol-fundamentals interface review

Reviewed: 2026-07-18

Status: **official free-interface shape and exact-universe mapping review
contract closed offline; no live transport or authorization created**.

## Decision

Use four bounded, explicitly typed public responses as the candidate
protocol-fundamentals source contract:

1. `GET https://api.llama.fi/protocols` for protocol identity, current TVL, and
   provider-reported one-day/seven-day TVL changes;
2. `GET https://api.llama.fi/overview/fees?dataType=dailyFees` for user-paid
   top-line fees;
3. the same overview with `dataType=dailyRevenue` for the portion retained by
   the protocol;
4. the same overview with `dataType=dailyHoldersRevenue` for revenue returned
   to token holders.

The overview requests exclude both chart payloads. This keeps a future capture
bounded while retaining the current 24-hour, 7-day-total, 30-day-total, and
one-day-change fields documented by the official SDK types.

The checked fixture contract requires an explicit operator-confirmed mapping
among the Radar canonical asset, CoinGecko asset ID, DefiLlama protocol-list ID,
protocol slug, protocol name, and token symbol. It never assumes that a token
and a protocol are equivalent merely because their names or symbols resemble
one another.

## Semantic rules

- TVL is a USD-valued locked-asset snapshot. Changes can include asset-price
  effects and are not labeled as net deposits or flows.
- Fees, protocol revenue, and holders revenue are separate metrics. They are
  never substituted for one another.
- `change_1d` is retained as percent points. No fraction/percent heuristic is
  applied.
- `total7d` and `total30d` are retained as period totals, not daily averages.
- The free overview response does not provide a metric-value timestamp in the
  reviewed schema. The contract therefore preserves each local request/read
  clock and explicitly marks provider value time unavailable.
- A missing metric remains `unavailable`; it never becomes numeric zero.
- Protocol fundamentals are context-only and have no directional authority by
  themselves.

## Sources reviewed

- [Official free OpenAPI contract](https://raw.githubusercontent.com/DefiLlama/api-docs/master/defillama-openapi-free.json)
- [Official Python SDK fee routes](https://github.com/DefiLlama/python-sdk/blob/master/defillama_sdk/modules/fees.py)
- [Official Python SDK fee data types](https://github.com/DefiLlama/python-sdk/blob/master/defillama_sdk/constants/dimensions.py)
- [Official Python SDK fee response types](https://github.com/DefiLlama/python-sdk/blob/master/defillama_sdk/types/fees.py)
- [DefiLlama metric definitions](https://defillama.com/data-definitions)

The official SDK marks the overview and per-protocol summary methods as free
and marks historical fee-chart methods as authenticated Pro endpoints. This
contract uses only the free overview shape; it does not claim access to or
substitute for Pro historical charts.

## Implemented proof

`crypto_rsi_scanner.event_providers.defillama_fundamentals` is a strict,
offline synthetic-fixture normalizer. It binds:

- the exact four request identities and typed queries;
- request-start, response-read, duration, and capture clocks;
- complete response and request digests;
- explicit protocol/asset mapping;
- USD totals, percent-point changes, units, metric availability, methodology,
  and source lineage;
- no-call, no-authorization, no-authority, no-Protocol-v2, and all existing
  no-side-effect guarantees.

The closed output also flows through the existing DEX/on-chain readiness
surface without losing holders-revenue or metric-semantics fields. Historical
flat DefiLlama-style fixtures retain their prior interpretation.

`crypto_rsi_scanner.event_providers.defillama_mapping_registry` closes the
separate identity-review boundary. It builds a deterministic pending roster
from exact liquidity-ranked market rows and accepts only an exact canonical
registry in which every asset is explicitly either `mapped` or
`not_applicable`. The registry binds its reviewer, review time, exact universe
digest, canonical/CoinGecko identity, symbol, protocol-list ID, slug, name, and
review note. Name or symbol similarity never creates a decision. A changed
universe digest, missing asset, extra asset, symbol/ID conflict, fixture-mode
registry, altered canonical projection, or incomplete decision set keeps live
mapping eligibility false with explicit blockers.

The mapping utility performs no provider call and writes nothing. A fixture
registry can prove the validator but can never satisfy the live boundary; only
a complete `registry_mode=operator` projection for the exact reviewed universe
can close the mapping prerequisite. That still does not authorize DefiLlama,
implement transport, publish evidence, or admit a capture to Protocol v2.

The readiness projection is now explicit: the fixture path sets
`fixture_input_configured=true`, while live `configured=false`,
`live_transport_status=not_implemented`,
`live_authorization_status=not_defined`,
`live_mapping_status=missing_real_registry`, and
`live_rehearsal_eligible=false`. Its current live request budget is zero. The
dashboard labels this state **Fixture only**, and strict doctor blocks any
fixture-scoped artifact that claims live configuration, transport, call
permission, or rehearsal eligibility.

Safe offline checks:

```sh
make radar-fundamentals-defillama-smoke PYTHON=.venv/bin/python
make radar-fundamentals-defillama-mapping-smoke PYTHON=.venv/bin/python
```

Assess any exact market-row artifact without a call or write:

```sh
.venv/bin/python -m crypto_rsi_scanner.event_providers.defillama_mapping_registry \
  <exact-market-rows.json> [--registry <operator-registry.json>]
```

The current revision-12 authority was assessed on 2026-07-18. Its exact
30-asset roster has universe digest
`8002383891e49f7eeea332dc40fc5c181c2a4455907c0c25a3def14f31bb3e52`:
0 mapped, 0 explicitly not applicable, 30 unreviewed, 0 identity conflicts.
The result is correctly live-ineligible and made zero provider calls. This is a
measured review gap, not permission to infer mappings or lower the boundary.

## Still required before genuine evidence

Do not add a live request merely because these endpoints are public. A future
genuine capture still requires:

- a separate explicit DefiLlama authorization flag already present in the
  operator environment;
- a reviewed request/response size and cadence budget;
- immutable exact accepted response bytes, redacted request ledger, health and
  backoff state, freshness policy, strict doctor, and rollback-safe selection;
- a genuine operator-approved protocol/asset mapping registry;
- applicable retention and redistribution review;
- an exact capture ID selected in the sealed Protocol-v2 annex.

Until then, the fixture is parser evidence only. It cannot become campaign,
dashboard, outcome, score-calibration, or Protocol-v2 authority.
