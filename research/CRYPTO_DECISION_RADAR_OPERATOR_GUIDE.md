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

### When a generation expires

Current live generations remain authoritative for at most six hours. The
campaign's 60-minute spacing is only the minimum interval between eligible
observations; it does not schedule a refresh. When freshness alone expires, the
browser keeps a quarantined diagnostic shell available under HTTP 503 so System
Health, historical Outcomes, and clearly labeled Run History remain inspectable.
Every current idea, market row, anomaly, calendar row, outcome, provider field,
and current count is suppressed. Phone readiness continues to reject the backend
because it is not authoritative. Pointer, identity, fingerprint, schema, and
integrity failures remain a minimal unavailable response.

Recover without weakening freshness or making an unapproved provider call:

1. Run `make radar-market-no-send-readiness PYTHON=.venv/bin/python`.
2. Only when it reports the already-authorized provider and cadence as eligible,
   run `make radar-market-no-send PYTHON=.venv/bin/python`. The command may make
   at most one bounded request and publishes only after a strict-clean run.
3. Restart the pointer-bound dashboard so it binds the newly published exact
   generation. For the installed local job, use
   `launchctl kickstart -k "gui/$(id -u)/com.nasrenkaraf.crypto-radar-dashboard"`;
   otherwise stop and rerun `make radar-dashboard PYTHON=.venv/bin/python`.

There is no automatic campaign scheduler. Installing a recurring maintainer
would authorize periodic provider calls and process restarts, so it remains a
separate explicit operator decision.

## Private phone access

Phone access uses Tailscale Serve as a private HTTPS proxy to the unchanged
loopback dashboard. It does not bind the Python server to a LAN address, open a
router port, create a dashboard password/token, use Tailscale Funnel, or publish
the dashboard on the public internet. The phone must be connected to the same
tailnet as this Mac. Tailnet ACL/grant policy and device membership are the
access-control boundary; on a shared tailnet, confirm that policy limits access
to the intended user or devices before enabling the route.

Prerequisites:

1. Install the Tailscale app on the phone and sign in to the same tailnet as the
   Mac.
2. Keep the Mac awake, online, and connected to Tailscale.
3. Start the loopback dashboard and ensure its exact generation is current. A
   stale or unavailable backend remains fail-closed and is not made usable by
   phone access.

Inspect the local dashboard and private-access prerequisites without changing
the Serve route:

```sh
make radar-dashboard-phone-readiness PYTHON=.venv/bin/python
make radar-dashboard-phone-status PYTHON=.venv/bin/python
```

Readiness reports whether the loopback dashboard, authoritative generation,
Tailscale connection, private DNS, and route ownership are safe to use. Status
shows the sanitized current state. Neither command enables access, prints raw
Tailscale account data, nor creates a public route.

Enable private HTTPS access with the explicit confirmation gate:

```sh
CONFIRM=1 make radar-dashboard-phone-enable PYTHON=.venv/bin/python
```

On the first activation, Tailscale may require a one-time admin sign-in and
**Enable HTTPS/Serve** consent in the browser. Approve only that private tailnet
feature, never Funnel, then rerun the confirmed enable command. This is a
Tailscale account setting rather than a repository credential.

Open the printed `https://...ts.net/` URL in the phone browser while Tailscale is
connected. The URL contains no dashboard credential; tailnet identity and policy
control who can reach it. Keep it as operator information rather than posting it
publicly.

Disable phone access without stopping the local loopback dashboard:

```sh
CONFIRM=1 make radar-dashboard-phone-disable PYTHON=.venv/bin/python
```

Disable removes only the HTTPS route owned by this dashboard. It does not reset
unrelated Tailscale Serve configuration. Re-run status afterward to confirm that
private phone access is off.

If a phone is lost or replaced:

1. Run the disable command immediately.
2. Revoke or remove the old phone from Tailscale's device administration.
3. Enroll the replacement phone into the intended tailnet and confirm its access
   policy.
4. Run readiness, then enable the private route again.

There is no repository phone-access token to rotate, and the project must not
add a Tailscale API credential merely to automate device revocation. Device
identity rotation and revocation remain explicit Tailscale operator actions.

## Primary pages

### Today

The command center answers what needs attention now and whether the generation
is safe to interpret. It shows the exact trust, data mode, validation state, prioritized
Decision routes, calendar and provider constraints, market observations,
campaign maturity, pending outcomes, and meaningful generation changes.

A sole specialist route is named directly (`1 risk watch`, for example) rather
than being overstated as a generic actionable idea. Compact attention cards lead
with route, symbol, directional posture, actionability/evidence/risk, current
thesis, and research window. Expired and diagnostic rows never inflate the
current queue; they remain in separately labeled disclosures.

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

An anomaly card is scanner evidence, not a Decision route. It leads with the
observed move, keeps missing scanner strength secondary, and links the exact
asset to any separately gated canonical Decision. Wide displays use a compact
comparison table; laptop widths use balanced two-column observation cards where
space permits; phones use one-column cards. Provider coin IDs remain in Context
or More market evidence rather than displacing the operator-facing symbol.

For a mixed integrated generation without a market-only receipt, these are
independent layer counts rather than one arrow chain. Catalyst-, technical-,
derivatives-, on-chain-, fundamental-, and macro-led ideas are not presented as
if they descended from absent market anomalies.

### Ideas and Idea Detail

Ideas can be searched, sorted, and filtered by route, origins, bias, scores,
timing, phase, catalyst, tradability, spread, freshness, horizon, and data mode.
Selected filters remain visible and can be cleared.

The comparison matrix appears only when at least two current ideas exist.
Filters and advanced controls stay collapsed until selected, so a one-idea view
does not lead with an empty comparison affordance.
Expired operator-visible ideas remain labeled historical context. A canonical
diagnostic row stays behind the diagnostics opt-in even after expiry; expiry
never grants it default visibility or direct-detail access.

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
An active risk window is grouped under **Active now**, ahead of future dates;
past events remain collapsed by default. A date-only event remains current
through its known UTC date instead of becoming past at midnight.

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

### Run History

Run History shows bounded immutable attempts, the latest attempt, provider
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

The top trust strip distinguishes current versus untrusted authority, live data
versus fixture/replay/cache modes, no-send state, campaign eligibility, and
validation status. Local human time and relative expiry are primary; exact UTC
and full run identity remain available in accessible or technical details.
Missing values render as `Unavailable`, not as zero, `None`, `null`, or
manufactured precision. Trader-facing surfaces say `Integrity checks` and
`Validation passed`; strict-doctor terms remain in the exact technical contract.
Missing boolean receipts say `Not recorded` instead of implying `No`, and every
relative timestamp is measured from the exact generation's authority-check
clock rather than the workstation wall clock.

Supporting filters, historical samples, compatibility tables, source receipts,
and technical hashes are collapsed by default. At 320px the compact masthead,
2×2 health summary, and readable score cards keep the first operator action in
the initial viewport; at intermediate widths KPI grids rebalance rather than
forcing narrow five-column cards. These layout changes never hide the visible
research-only, human-decision-required, no-execution statement.

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
