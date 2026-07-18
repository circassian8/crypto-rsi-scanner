# Decision Radar outcome-price recovery v1

Status: diagnostic exact-response contract and immutable capture implemented;
outcome application is not implemented.

This path exists only to close genuine primary-horizon outcome gaps. It is not
a second market-observation campaign and must never warm temporal baselines,
create Decision candidates, or alter thresholds.

## Current evidence gap

The campaign has one overdue outcome without a qualifying retained price:

- asset: `DEXE` / CoinGecko ID `dexe`
- candidate observed: `2026-07-14T00:29:40.814498Z`
- primary 24h horizon due: `2026-07-15T00:29:40.814498Z`
- latest permitted price time: `2026-07-16T00:29:40.814498Z`
- first retained later price: `2026-07-16T02:08:32.428755Z`
- outside the permitted window by: `5,931.614257` seconds

The later retained price remains invalid for this outcome. No interpolation or
nearest-neighbor substitution is permitted.

## Official source contract

The narrow source is CoinGecko's documented
[`/coins/{id}/market_chart/range`](https://docs.coingecko.com/reference/coins-id-market-chart-range)
endpoint. It returns timestamped price rows for one exact coin ID and time
range. For a historical one-day range, the documented automatic granularity is
hourly; the recovery request intentionally omits `interval`, requests USD with
full precision, and accepts only timestamps inside the original outcome window.

One unresolved outcome plans one fixed-host public GET. The current request is:

```text
GET /coins/dexe/market_chart/range
vs_currency=usd
from=1784075380
to=1784161781
precision=full
```

No retry, redirect, proxy, alternate host, or range expansion is allowed.

## Evidence semantics

A diagnostic response and immutable capture must:

- retain exact response bytes in memory, then persist those exact bytes only
  through the separately confirmed immutable capture command;
- preserve request and response clocks separately from the historical market
  timestamp;
- select the first valid positive USD price at or after `due_at` and at or
  before `allowed_latest_price_at`;
- return `no_results` honestly when no timestamp qualifies;
- fail closed on duplicate keys, unknown response fields, duplicate or
  unordered timestamps, out-of-range timestamps, non-finite/non-positive
  prices, host drift, request drift, or plan drift after the response;
- remain `point_in_time_collection_at_market_time=false` because acquisition
  occurs after the historical market time;
- bind the canonical campaign pointer, exact market-history and outcome-ledger
  snapshots, target outcome row, and immutable candidate/Core generation;
- publish only through a manifest, completion receipt, and rollback-protected
  latest pointer that rederive every result from the exact response;
- remain excluded from baseline history, campaign observation counts,
  calibration, and Protocol-v2 evidence until a sealed annex says otherwise.

## Authorization and commands

Readiness makes no provider call and writes nothing:

```text
make radar-outcome-price-recovery-readiness PYTHON=.venv/bin/python
```

Diagnostic collection and immutable capture require both the existing general
CoinGecko live flag and a separate, already-present recovery authorization:

```text
RSI_EVENT_DISCOVERY_UNIVERSE_LIVE=1
RSI_DECISION_RADAR_OUTCOME_PRICE_RECOVERY_LIVE=1
CONFIRM=1 make radar-outcome-price-recovery-collect PYTHON=.venv/bin/python
CONFIRM=1 make radar-outcome-price-recovery-capture PYTHON=.venv/bin/python
```

The preferred writing command is `radar-outcome-price-recovery-capture`; it
makes the same bounded provider attempt and seals a successful exact response.
Read-only status makes no provider call or write:

```text
make radar-outcome-price-recovery-status PYTHON=.venv/bin/python
```

Codex must never create or mutate either authorization. The diagnostic
collector performs no artifact write. The capture command writes only its
immutable response namespace and latest pointer; neither command performs an
outcome mutation, baseline insertion, send, trade, paper trade, RSI write, or
`TRIGGERED_FADE` creation. The standard review export selects and fully
revalidates only the latest pointed capture.

## Remaining work

Before a recovered price can complete an outcome, add a separate confirmed
application step that revalidates the exact capture and current target, updates
only the campaign outcome ledger, preserves historical-recovery provenance,
and proves the market-history baseline byte-identical before and after.
Protocol-v2 eligibility remains a later annex decision.
