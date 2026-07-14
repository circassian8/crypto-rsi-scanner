# Crypto Decision Radar Operator Guide

Crypto Decision Radar is a local, research-only decision terminal. It ranks and
explains evidence for a human operator. It never places orders, creates live or
Event Alpha paper trades, writes normal RSI signals, creates `TRIGGERED_FADE`,
or sends Telegram messages from dashboard requests.

## Start and verify

Run the dashboard against the fixed authoritative pointer:

```sh
make radar-dashboard PYTHON=.venv/bin/python
```

Open `http://127.0.0.1:8765/`. The server binds to loopback by default. Every
pointer-bound GET/HEAD revalidates the exact namespace, run, revision, and
operator-state fingerprint. If authority changes, the request fails closed
instead of continuing to present an old generation as current.

Useful read-only checks:

```sh
make radar-dashboard-readiness PYTHON=.venv/bin/python
make radar-dashboard-smoke PYTHON=.venv/bin/python
make radar-dashboard-ux-smoke PYTHON=.venv/bin/python
make radar-market-no-send-readiness PYTHON=.venv/bin/python
```

Readiness does not call providers. The live market command may make one bounded
CoinGecko request only when the explicit authorization already exists and the
campaign cadence is eligible; the dashboard never sets that authorization.

## Primary pages

### Today

The command center answers what needs attention now and whether the generation
is safe to interpret. It shows the exact trust/mode/doctor state, prioritized
Decision routes, calendar and provider constraints, market observations,
campaign maturity, pending outcomes, and meaningful generation changes.

Zero current ideas is not automatically a failure. If the page shows evaluated
assets and zero anomaly/idea rows, the assets passed into the exact observation
layer but did not qualify under the current evidence and safety gates. Review
the warning stack and Market Radar funnel before assuming data loss.

### Market Radar

Market Radar shows the bounded universe even when no idea qualifies. The layer
funnel separates:

1. bounded provider rows;
2. selected top-liquid universe;
3. exact fingerprint-bound observations;
4. anomaly evidence;
5. integrated candidate rows;
6. consolidated Core/operator ideas.

A reconciled reduction after the observation stage is qualification. A missing
stage receipt remains explicitly unavailable and is not inferred. Market cap,
turnover, volume, multi-horizon returns, BTC/ETH-relative values, freshness,
baseline maturity, spread, and candidate routes retain their actual basis.
CoinGecko volume or turnover is a proxy, not order-book depth. Missing spread
means unavailable; it may permit a dashboard watch but cannot be invented to
justify an actionable or rapid route.

For a mixed integrated generation without a market-only receipt, these are
independent layer counts rather than one arrow chain. Catalyst-, technical-,
derivatives-, on-chain-, fundamental-, and macro-led ideas are not presented as
if they descended from absent market anomalies.

### Ideas and Idea Detail

Ideas can be searched, sorted, and filtered by route, origins, bias, scores,
timing, phase, catalyst, tradability, spread, freshness, horizon, and data mode.
Selected filters remain visible and can be cleared.

Idea Detail leads with the canonical Decision v2 interpretation: route, bias,
actionability, evidence confidence, risk, urgency, chase risk, origins,
catalyst, timing, phase, tradability, spread, horizon, expiry, why now,
supporting facts, missing information, risks, confirmation, and invalidation.
Calendar, RSI, market quality, charts, outcome, and provenance stay attached to
the same projection. Catalyst Radar classification is secondary; an
operator-visible Decision idea may still be “Not eligible for strict catalyst
alert” without being globally described as not alertable.

### Calendar

Calendar rows are grouped chronologically with importance/category filters,
affected assets, countdowns, forecast/previous/actual/surprise fields, reminder
windows, safe source links, and nearby current ideas. Exact times, date-only
events, tentative dates, and expected windows are presented differently.

An empty live calendar must name its coverage state. `Not configured` means the
generation did not inspect a real calendar source; it does not mean there are no
events. Configure a fresh non-fixture, operator-verified snapshot through
`RSI_DECISION_RADAR_CALENDAR_SNAPSHOT_PATH`, then begin with market readiness.
Fixture, test, mock, replay, stale, unsafe, or rejected calendar rows cannot
silently fill a live authority.

### System Health

Health separates real failures and backoff from intentional disablement,
unselected providers, missing configuration, missing authorization, and warming
data. It exposes the exact run/revision/doctor/pointer contract, bounded request
receipt, provider readiness, source coverage, baseline maturity, freshness,
spread coverage, and direct-versus-proxy limitations. Technical identifiers and
hashes are collapsed by default.

The same canonical coverage matrix is used by Today and Health for market,
catalyst, calendar, derivatives, RSI, outcomes, and the exact provider request
ledger. Green requires every expected layer to be healthy or explicitly not
applicable. A configured layer that is unavailable, degraded, stale, rejected,
or missing cannot disappear behind a clean market scan.

### Outcomes & Learning

Exact current-generation outcomes are separate from shared historical campaign
rows. Pending means the evaluation horizon or required price evidence is not yet
available; it is not a negative result. Matured results are grouped into small,
explicit cohorts with sample-size warnings. Feedback is optional preference
data and never a prerequisite for idea visibility or an automatic threshold
change.

### Campaign History

Campaign History shows bounded immutable attempts, the latest attempt, provider
request result, authorization state, namespace, data mode, route/candidate
counts, baseline progression, doctor/publication state, reservation/cadence,
and the next eligible observation. Historical generations provide context only;
they are never merged into current authority.

## Scores and routes

- Actionability measures how useful and timely the setup is for human review;
  it is not win probability.
- Evidence confidence measures explanatory support; it is not expected return.
- Risk measures uncertainty and downside/integrity concerns; higher is riskier.
- Urgency measures how quickly the evidence may decay.
- Chase risk measures extension and the danger of entering too late.

The operator routes are `high_confidence_watch`, `actionable_watch`,
`rapid_market_anomaly`, `dashboard_watch`, `fade_exhaustion_review`,
`risk_watch`, `calendar_risk`, and `diagnostic`. Primary views translate these
codes into readable labels. Diagnostic rows stay outside normal attention unless
explicitly requested.

Unknown catalyst lowers explanatory confidence and may raise risk, but does not
universally hide a fresh, liquid, identity-safe market-led anomaly. Calendar
context can raise risk or shorten expiry; it cannot create directional bias by
itself.

## Trust and display states

The top trust strip distinguishes current versus untrusted authority, live real
data versus fixture/replay/cache modes, no-send state, campaign eligibility, and
strict-doctor status. Local human time is primary; exact UTC remains available
in accessible details. Missing values render as `Unavailable`, not as zero,
`None`, `null`, or manufactured precision.

The supporting layers use distinct states:

- healthy with rows;
- healthy with no matching rows;
- not configured or not selected;
- unavailable, degraded, rate-limited, or in backoff;
- cold or warming;
- stale, rejected, or fixture-ineligible for live use;
- historical and non-authoritative.

No state is promoted merely to make the terminal look active. The operator may
always inspect exact lineage, but presentation never re-evaluates Decision v2.
If exact authority fails, every current artifact-derived count and row is
quarantined across all pages. A failed current artifact is never relabeled as
historical evidence. Historical campaign rows remain visible only with their
non-authoritative label.

Source links must be absolute HTTP(S), have a hostname, and contain no embedded
username or password. Return fields use their field-level unit metadata; a
10-percentage-point relative return cannot be rendered as 1,000%, and turnover
ratios are labeled as percentages rather than compact currency-like numbers.

## Safe next actions

For another market observation, always start with:

```sh
make radar-market-no-send-readiness PYTHON=.venv/bin/python
```

Run `make radar-market-no-send PYTHON=.venv/bin/python` only when readiness says
the already-authorized provider and campaign cadence are eligible. For calendar
coverage, first supply a fresh non-fixture snapshot through the documented local
path, then rerun readiness. Do not lower thresholds, invent spread, substitute
fixtures into a live generation, or enable sends to populate the dashboard.
