# Decision Radar outcome-price recovery v1

Status: diagnostic exact-response contract, immutable capture, and separately
confirmed ledger-only application are implemented. No real capture or
application exists because the separate provider authorization is absent.

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

A qualifying immutable capture may be applied only by the closed local
application boundary. It revalidates the latest capture, exact source binding,
current outcome ledger, immutable candidate, and target identity while holding
the existing root-scoped campaign lock. It then:

- changes exactly one bound outcome row per qualifying recovery result;
- records historical market time, later acquisition time, capture/request/raw
  response IDs, and the explicit historical-recovery price source;
- marks the completed row permanently ineligible for calibration, performance,
  and Protocol-v2 evidence;
- leaves the market-history baseline byte-identical;
- writes the ledger atomically and creates one immutable application receipt
  binding before/after ledger fingerprints and the unchanged baseline;
- restores the exact prior ledger if any pre-receipt step fails;
- is idempotent only while the current ledger and baseline still match the
  immutable receipt; later drift fails closed;
- holds descriptor-anchored base, state-directory, lock, ledger, history, and
  receipt identities so a directory or symlink swap cannot redirect the write
  or rollback.

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

After a qualifying immutable capture exists, application is a distinct local
confirmation. It makes no provider call and does not inspect or create
authorization:

```text
CONFIRM=1 make radar-outcome-price-recovery-apply PYTHON=.venv/bin/python
make radar-outcome-price-recovery-application-status PYTHON=.venv/bin/python
```

Codex must never create or mutate either authorization. The diagnostic
collector performs no artifact write. The capture command writes only its
immutable response namespace and latest pointer; neither command performs an
outcome mutation, baseline insertion, send, trade, paper trade, RSI write, or
`TRIGGERED_FADE` creation. The standard review export selects and fully
revalidates only the latest pointed capture. The application changes only the
mutable campaign outcome ledger and creates its immutable receipt inside the
canonical shared history directory. It never inserts the recovered price into
market history or changes candidates, routes, scores, thresholds, or authority.

## Remaining work

The operator may later supply the already-defined recovery authorization and
run the confirmed capture. Only a successful qualifying capture can make the
separate application command eligible. Until then the real capture pointer and
application receipt remain honestly absent and DEXE remains `due_missing_price`.
Historical recovery remains excluded from Protocol-v2 evidence unless a future
annex is sealed before its holdout is identified or read.
