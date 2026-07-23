# Lean Crypto Radar V1 Product Contract

Status: active product rebuild. The universe/store, market-scan, context-only
calendar, automatic outcomes, bounded system health, and six-page read-only
dashboard are implemented. Telegram preview, dedupe, readiness, and explicitly
guarded delivery are also implemented; default workflow/release closure remains
in progress.

## Product

Lean Crypto Radar is the default personal operator product. It is a practical,
research-only radar for Bybit USDT perpetuals. It answers what is moving,
whether it is actually available on the intended venue, whether the move is
liquid and timely, what confirms or invalidates it, and what data is missing.
The human operator makes every trading decision.

Event Alpha remains available as optional Catalyst Context. Decision Radar and
the Empirical Lab remain research infrastructure. Neither is a required gate
for a market-led Lean Radar idea.

## Fixed V1 choices

- Venue: Bybit.
- Instrument: active, non-prelisting, USDT-quoted and USDT-settled linear
  perpetuals.
- Detection input: CoinGecko/public market data is acceptable.
- Universe: top 200 assets ranked by 24-hour USD volume after shared hygiene,
  intersected with a confirmed Bybit instrument catalog, plus a manual
  watchlist subject to the same instrument check.
- Cadence: operator-configurable from 15 to 30 minutes; default 20 minutes.
- Surfaces: dashboard and Telegram have equal product priority.
- Runtime state: one small ignored SQLite database.
- Urgent alerts: no daily count cap. Visible-family dedupe, unchanged-update
  cooldown, material-change checks, and market-wide grouping prevent spam.
- Shorts: always phrased as exhaustion/fade review, never instructions.
- Catalyst: useful context, never a universal requirement.

## Idea types, routes, and scores

The nine V1 idea types are `market_breakout_long`, `relative_strength_long`,
`pullback_or_mean_reversion`, `rapid_market_anomaly`,
`exhaustion_or_fade_review`, `selloff_or_risk_warning`, `calendar_risk`,
`dashboard_watch`, and `diagnostic`.

The six routes are `urgent_review`, `watchlist`, `daily_digest`,
`dashboard_only`, `risk_calendar`, and `diagnostic_hidden`.

The only main scores are actionability, confidence, risk, and urgency. They are
operator-priority summaries on a 0–100 scale, not win probabilities.

## Implemented scan contract

One scan first proves the local Bybit catalog, source mode, explicit live
authorization, and 15–30-minute cadence. Only then may the live path make one
bounded CoinGecko `/coins/markets` request ordered by `volume_desc`. The request
uses the endpoint's direct 1-hour, 24-hour, and 7-day percentage fields plus its
7-day sparkline. Wilder-14 RSI is explicitly labeled as a calculation over
untimestamped sparkline points. No 4-hour return is derived from array position;
exact 4-hour context remains unavailable until timestamped bars are collected.

The store builds a rolling log-volume baseline after eight prior observations.
Before that baseline is warm, a cross-sectional turnover z-score is labeled as
a cold-start attention proxy. BTC/ETH-relative returns, freshness, minimum
liquidity, spread availability, and chase risk remain separate evidence.

The detector chooses at most one setup per asset. Stale data, missing minimum
return context, suspicious low-liquidity pumps, and known extreme spread become
hidden diagnostics. Valid market-led setups are scored once with the four
operator scores and persisted atomically with the snapshots, four outcome
placeholders per idea, and scan health.
Unknown catalyst remains visible with lower confidence and higher risk. Missing
spread caps confidence and urgency. The initial rules are transparent V1 screens
to be evaluated through outcomes; they are not estimated win probabilities and
must not be tuned against sparse examples.

## Implemented calendar contract

The lean runtime accepts one confirmation-gated genuine local calendar snapshot
with an explicit source name, acquisition time, credential-free HTTPS source
URL when present, and SHA-256 of the exact imported bytes. The strict schema
supports FOMC, CPI, PPI, PCE, employment, GDP, crypto unlock, exchange listing
or delisting, and protocol events. Imported events remain in the same SQLite
database; they do not create a new artifact family.

Macro events can overlay every asset. Crypto-specific events overlay only an
exact affected symbol. An event can raise risk and time-sensitive urgency and
can shorten an existing idea's expiry, but it is always marked context-only and
cannot create directional bias or an idea by itself. Missing or invalid
calendar context remains a visible health limitation while the market scan
continues. No live calendar provider is called by the import or readiness path.

## Implemented outcomes and health contract

Every idea receives pending `1h`, `4h`, `24h`, and `3d` outcome rows in the
same transaction that stores the idea and its exact start snapshot. Outcome
maturation reads only retained point-in-time prices. The endpoint is the first
same-asset observation at or after the horizon target and no more than 45
minutes late. A missing endpoint remains pending until that window closes and
then becomes unresolved; it is never filled from a current quote or a provider
request. BTC/ETH-relative return uses exact matching benchmark start and end
clocks. MFE and MAE use the retained path and the idea's review direction;
neutral ideas keep those directional fields unavailable instead of inventing a
side.

The descriptive result vocabulary is `continued`, `reversed`,
`failed_quickly`, `risk_warning_validated`, and `inconclusive`. The fixed 2
percentage-point movement band and 3 percentage-point one-hour quick-failure
band are reporting definitions, not detector tuning or probability claims.
Outcomes never change setup rules, scores, routes, or thresholds, and human
labels remain optional.

`lean-radar-health` records a small local operator-health projection for the
future dashboard. It separates the last provider attempt and result from the
current authorization check and current call eligibility. It also reports the
last/next scan, data freshness, Bybit catalog, CoinGecko status, calendar,
outcomes, no-send state, Telegram mode, bounded errors, and the next safe
command. The command makes no provider call and no send. A missing runtime
database produces setup guidance without creating one.

## Implemented dashboard contract

The Lean dashboard is a read-only view over the one SQLite runtime. It has
exactly six primary pages: Today, Ideas, Market, Calendar, Outcomes, and System
Health. Today leads with current attention, scan truth, and scheduled risk in
the next 24 hours. Ideas supports bounded search, route/type/horizon filters,
score sorting, and one detail page that keeps price/activity, technical,
calendar, catalyst, and outcome context visibly separate. Market renders the
latest point per venue-confirmed asset, Calendar labels every event as
context-only, Outcomes distinguishes pending, matured, and unresolved evidence,
and System Health separates current authorization from historical provider
results.

Every page shows whether its current scan came from a live no-send request, a
genuine imported snapshot, or fixture data. A fixture can support offline smoke
and visual review but can never masquerade as live state. Browser GET/HEAD
requests neither inspect environment authorization nor write SQLite, call a
provider, send Telegram, or run analysis. Invalid or absent runtime state fails
closed with one safe local health command. The server is concurrent and
loopback-only on `127.0.0.1:8766` during coexistence with the legacy dashboard;
phone/public access is not enabled by this slice.

Current idea cards additionally require the latest scan to be complete, have a
valid aware observation clock and 15–30-minute cadence, and be no older than two
cadences. A later failed/incomplete scan or an aged successful scan leaves the
prior rows intact for market history, idea details, and outcomes, but hides them
from Today and Ideas and labels the retained evidence historical. Calendar
context remains visible because it is independently timed and never directional.

## Implemented Telegram contract

Telegram is a concise projection of the same persisted Lean ideas; it does not
re-score or reclassify them. The four message types are urgent review,
watchlist update, daily digest, and risk/calendar. Each idea block includes its
symbol, human idea/bias wording, four scores, catalyst status, timing/phase, why
now, main risk, confirmation, invalidation, dashboard detail link, and the
research-only human-decision disclaimer. Fade candidates always say fade or
exhaustion review and never give an execution instruction. Upcoming calendar
events are included as context-only risk and create no direction.

The same completed-scan/two-cadence rule used by the dashboard applies before
Telegram dedupe or grouping. Non-current market ideas cannot become messages;
upcoming calendar context remains independently eligible.

`lean-radar-telegram-preview` is read-only, writes no dedupe state, calls no
provider, and sends nothing. `lean-radar-telegram-readiness` exposes only
secret-safe booleans and recipient count; it never prints tokens or recipient
identities. There is no urgent daily cap. Stable visible families, a fixed
eight-point material score delta, route-specific cooldowns, and market-wide
groups of at most four items prevent repeated spam while retaining every
distinct due item across as many messages as needed. State is consumed only
after full mocked/real sender success; failures remain due. One expiring local
SQLite lease prevents overlapping send commands.

Real delivery is a separate command and requires all of: a non-fixture
live-no-send or genuine-imported source, current due messages, existing
Telegram token/recipient configuration, `RSI_EVENT_ALERTS_ENABLED=1`, and
`CONFIRM=1`. The application never sets those values. The command records only
safe delivery counts and material-family state, never token or recipient
values. It calls no market provider and remains research-only.

## Hard gates and soft limitations

Hard gates are unresolved identity, no confirmed Bybit USDT perpetual, stale or
insufficient market data, invalid units, insufficient liquidity, known extreme
spread, control/stable/theme rows, duplicate cooldown, and unsafe provider,
path, or secret state.

Unknown catalyst, missing official/second source, unavailable derivatives,
on-chain, spread, macro, or LLM context are soft limitations. Missing spread
caps confidence and urgency and normally prevents the strongest urgent route;
it does not hide a useful watchlist/dashboard idea.

## Runtime store

The single SQLite database may hold the Bybit catalog, manual watchlist, market
snapshots and baselines, ideas, outcomes, calendar events, notification state,
and health. It contains no orders, positions, portfolio, account data, or paper
trades. The database and WAL/SHM files are ignored from git and review exports.

## Safety

- Research and decision support only.
- No live trading, orders, execution, positions, portfolio, or account data.
- No paper trading from Lean Radar or Event Alpha.
- No normal RSI signal writes from Lean Radar or Event Alpha.
- No Event Alpha-created `TRIGGERED_FADE`; that remains exclusive to
  `event_fade.py` plus `proxy_fade`.
- No Telegram sends by default; sending requires the existing explicit guards.
- No provider call without an already-present explicit authorization flag.
- The application never creates, changes, infers, or persists authorization.
- Missing data remains missing; proxy data is labeled; catalysts, spreads,
  depth, liquidity, anomalies, labels, and outcomes are never fabricated.

## Default workflow

```sh
make lean-radar-readiness PYTHON=.venv/bin/python
make lean-radar-bybit-universe-readiness PYTHON=.venv/bin/python
CONFIRM=1 make lean-radar-bybit-universe-import \
  LEAN_RADAR_BYBIT_CATALOG=/absolute/path/to/instruments-info.json \
  PYTHON=.venv/bin/python
make lean-radar-universe \
  LEAN_RADAR_MARKET_ROWS=/absolute/path/to/coingecko-markets.json \
  PYTHON=.venv/bin/python
make lean-radar-scan PYTHON=.venv/bin/python
make lean-radar-calendar-readiness PYTHON=.venv/bin/python
make lean-radar-outcomes PYTHON=.venv/bin/python
make lean-radar-health PYTHON=.venv/bin/python
make lean-radar-dashboard PYTHON=.venv/bin/python
make lean-radar-telegram-preview PYTHON=.venv/bin/python
make lean-radar-telegram-readiness PYTHON=.venv/bin/python
```

After inspecting preview/readiness, the separate optional real-send boundary is:

```sh
RSI_EVENT_ALERTS_ENABLED=1 CONFIRM=1 \
  make lean-radar-telegram-send PYTHON=.venv/bin/python
```

That command is never invoked by scanning, dashboard reads, preview, readiness,
health, outcomes, or calendar work.

The live scan command respects the already-present CoinGecko authorization and
returns non-success before a provider call when authorization, catalog, or
cadence readiness is absent. For a genuine local calendar and offline market
snapshot:

```sh
CONFIRM=1 make lean-radar-calendar-import \
  LEAN_RADAR_CALENDAR_SNAPSHOT=/absolute/path/to/calendar.json \
  PYTHON=.venv/bin/python

make lean-radar-scan \
  LEAN_RADAR_MARKET_MODE=imported_snapshot \
  LEAN_RADAR_MARKET_ROWS=/absolute/path/to/coingecko-markets.json \
  LEAN_RADAR_MARKET_OBSERVED_AT=2026-07-23T12:00:00Z \
  PYTHON=.venv/bin/python
```

Readiness is observational and makes no provider call or database write.
Outcome maturation and health refresh are local SQLite updates that make no
provider call, send, or model-policy change. The dashboard is a read-only
loopback view; `make lean-radar-dashboard-smoke` renders all six primary pages
against one disposable fixture database without touching operator state. The
catalog import and genuine market-snapshot import reject checked-in fixture,
test, mock, or replay paths. The legacy Decision Radar commands remain
available for research operations but are outside this default path.

## Deliberately not included

There is no execution engine, order manager, portfolio/account integration,
automatic threshold tuning, LLM critical path, universal catalyst gate,
arbitrary urgent-alert cap, or new artifact/provenance framework. Existing
Event Alpha and empirical code remains intact but is outside the default Lean
Radar path.
