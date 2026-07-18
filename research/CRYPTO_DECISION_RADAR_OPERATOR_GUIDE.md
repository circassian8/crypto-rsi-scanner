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
make radar-dashboard-authority-status PYTHON=.venv/bin/python
make radar-dashboard-readiness PYTHON=.venv/bin/python
make radar-dashboard-smoke PYTHON=.venv/bin/python
make radar-dashboard-ux-smoke PYTHON=.venv/bin/python
make radar-daily-ops-readiness PYTHON=.venv/bin/python
```

Dashboard readiness validates and never updates the pointer. Publishing is a
separate confirmation-gated action for an explicitly named, receipt-backed
operational namespace; fixture and legacy namespaces are refused:

```sh
CONFIRM=1 make radar-dashboard-publish PYTHON=.venv/bin/python ARTIFACT_NAMESPACE=<namespace>
```

Readiness does not call providers. The live market command may make one bounded
CoinGecko request only when the explicit authorization already exists and the
campaign cadence is eligible; the dashboard never sets that authorization.

### When a generation expires

Current live generations remain authoritative for at most six hours. The
campaign's 60-minute spacing is the minimum interval between eligible
observations. When freshness alone expires, the
browser keeps a quarantined diagnostic shell available under HTTP 503 so System
Health, historical Outcomes, and clearly labeled Run History remain inspectable.
Every current idea, market row, anomaly, calendar row, outcome, provider field,
and current count is suppressed. Phone readiness continues to reject the backend
because it is not authoritative. Pointer, identity, fingerprint, schema, and
integrity failures remain a minimal unavailable response.

Recover without weakening freshness or making an unapproved provider call:

1. Run `make radar-daily-ops-readiness PYTHON=.venv/bin/python`.
2. Only when it reports the already-authorized provider and cadence as eligible,
   run `make radar-daily-ops-cycle PYTHON=.venv/bin/python`. The coordinator may
   make at most one bounded request, strict-doctors the generation, writes the
   closed publication receipts, restarts only the owned dashboard, probes its
   exact identity, and refreshes campaign truth.

`make radar-market-no-send` is a compatibility alias for that same coordinator.
The lower-level collection CLI cannot publish dashboard authority directly, so
there is no separate manual restart step.

Daily Operations v1.1 is the guarded maintainer, but it remains prepared and
disabled until the operator explicitly installs it. Inspect it without writes
or provider calls, or run one manual cycle, with:

```sh
make radar-daily-ops-readiness PYTHON=.venv/bin/python
make radar-daily-ops-status PYTHON=.venv/bin/python
make radar-daily-ops-cycle PYTHON=.venv/bin/python
```

Each cycle journals attempted and terminal states, performs readiness before a
possible provider boundary, observes the one-hour cadence, makes at most one
already-authorized CoinGecko no-send request, and uses a unique namespace.
Strict doctor and complete operator state precede publication. Failure restores
the prior pointer or removes only the failed new pointer; the exact owned
dashboard restarts only after publication. Status treats a loaded LaunchAgent
with a non-zero last exit as unhealthy and keeps its sanitized exit/run counts
in maintenance telemetry. Install only after accepting those recurring calls
and restarts:

```sh
CONFIRM=1 make radar-daily-ops-install PYTHON=.venv/bin/python
```

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

## Temporary public phone access

The easier no-tailnet option is an ephemeral Cloudflare Quick Tunnel. It keeps
the Python dashboard bound to `127.0.0.1:8765` and creates an outbound-only
connection to a randomized public `https://…trycloudflare.com` address. It does
not need a Cloudflare account, domain, DNS change, router port, dashboard token,
or phone app.

Public means unauthenticated: anyone with the URL can read the dashboard. Quick
Tunnels are intended for development/testing, have no uptime guarantee, and the
address changes after a restart. They are suitable for temporary personal phone
access, not a permanent deployment.

Inspect without changing exposure:

```sh
make radar-dashboard-public-readiness PYTHON=.venv/bin/python
make radar-dashboard-public-status PYTHON=.venv/bin/python
```

Readiness requires the local dashboard to return its authoritative HTTP 200
identity and security headers, an
executable `cloudflared`, no conflicting default Cloudflare configuration, and
no stale or unowned public-process state. It does not call providers, write
dashboard artifacts, create a tunnel, or reveal a prior URL.

If readiness reports `cloudflared_binary_missing` on macOS, install the CLI
without starting a background service, then rerun readiness:

```sh
brew install cloudflared
```

Start the temporary public link:

```sh
CONFIRM=1 make radar-dashboard-public-enable PYTHON=.venv/bin/python
```

Open the printed HTTPS URL directly on the phone. The helper launches one fixed
HTTP/2, non-debug `cloudflared` command, waits for edge registration, accepts
only one canonical lowercase `trycloudflare.com` URL, and prints it only after
that address returns the expected dashboard and security headers over HTTP 200.
It stores only bounded machine-local runtime state. It does not install a
startup service, create Cloudflare credentials, or alter Tailscale.

Stop it when finished:

```sh
CONFIRM=1 make radar-dashboard-public-disable PYTHON=.venv/bin/python
CONFIRM=1 make radar-dashboard-public-guard PYTHON=.venv/bin/python
```

Disable terminates only the exact owned process whose PID and complete live argv
still match the runtime state. It refuses argv mismatch or unowned process state.
The link also disappears when the process or Mac stops. The optional
`RSI_RADAR_PUBLIC_MAX_LIFETIME_MINUTES` defaults to 240 minutes; an expired,
stale, or unhealthy link is no longer reported as usable. Receipt expiry does
not itself terminate `cloudflared`; status warns that it may still be public,
and the confirmed guard stops only its exact owned process. Keep public access
off unless actively needed. Tailscale Serve is the recommended persistent phone
route.

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
events. The official producer supports Fed FOMC, BLS CPI/employment, and BEA
PCE/GDP. Readiness is no-call; live acquisition requires the pre-existing
calendar authorization and honest BLS contact. Local import accepts any explicit
non-empty subset of genuine operator-downloaded Fed, BLS, and BEA files plus
their real acquisition timestamp. Omit unavailable source variables rather than
using an empty or fixture path. The resulting snapshot is `partial` and names
the exact observed and missing sources; zero rows from an unavailable source do
not mean that source had no events. For example, a complete three-source import
is:

```sh
make radar-calendar-official-readiness PYTHON=.venv/bin/python
make radar-calendar-official-acquire PYTHON=.venv/bin/python
make radar-calendar-official-import-local \
  FED_FOMC_HTML=/path/to/fomc.html \
  BLS_CALENDAR_ICS=/path/to/bls.ics \
  BEA_RELEASE_DATES_JSON=/path/to/bea.json \
  OFFICIAL_MACRO_OBSERVED_AT=2026-07-15T00:00:00Z \
  PYTHON=.venv/bin/python
```

Every successful pack preserves exact/window semantics and source timezones,
writes immutable source evidence, and is hash-attested before Daily Operations
can use its latest-success snapshot. Complete and partial successes are both
eligible only after the same receipt, pointer, coverage, and raw-source digest
checks. Direct fixture, test, mock, or replay paths are rejected before writes.
Missing, stale, unavailable, unsafe, or rejected calendar evidence remains
explicit and cannot create directional bias alone.

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

### Research Lab

Research Lab presents historical replay, walk-forward, matched-control,
cost-sensitivity, shadow-policy, and separately fingerprinted live no-send
evidence. It is descriptive and authority-independent: a valid research bundle
may remain inspectable when the production generation is stale, but it cannot
restore current actionability, update the dashboard pointer, or change a route,
threshold, provider setting, notification, or execution policy.

The page requires one validated 7/7 report bundle. It reads the exact validation,
walk-forward, and policy Markdown/JSON pairs plus the limitations Markdown
through one descriptor-anchored snapshot. If any member is missing, unsafe,
oversized, tampered, spliced, or inconsistent with the other six, semantic
tables are suppressed. A bounded file inventory and failure state may remain;
the page never translates invalid evidence into a healthy zero-sample result.

Review the page in this order:

1. final empirical verdict and frozen protocol/run identity;
2. development, validation, and final-test idea/episode samples;
3. route and thesis-origin coverage, including explicit no-evidence rows;
4. score monotonicity and any not-evaluable comparisons;
5. MFE, signed MAE, matched controls, missed/false/late classifications, and
   assumed cost sensitivity;
6. walk-forward folds, outcome purges, selected scenarios, and zero-idea days;
7. operator burden and shadow-policy recommendations;
8. live no-send comparison and research limitations.

MAE is signed: a negative value is adverse excursion, not an unsigned magnitude
or a positive quality score. `Historical spread not observed` means fee, spread,
slippage, and adverse-selection results are assumptions, even when a break-even
cost is shown. Live no-send evidence has its own fingerprint and sample warning;
it is never pooled into replay counts.

### Run History

Run History shows bounded immutable attempts, the latest attempt, provider
request result, authorization state, namespace, data mode, route/candidate
counts, baseline progression, doctor/publication state, reservation/cadence,
and the next eligible observation. Historical generations provide context only;
they are never merged into current authority.
The separate Daily Operations ledger shows readiness, provider-attempt,
publication, rollback/invalidation, and owned-dashboard restart state; it is
maintenance telemetry, never authority by itself.

## Historical research workflow

The complete reproducible workflow is in
[Decision Radar Research Runbook](DECISION_RADAR_RESEARCH_RUNBOOK.md). Its safe
order is protocol check, fixture smoke, medium replay, full development/
validation selection, sealed final-test replay, seven-file report publication,
and a byte-for-byte report check. These commands are offline and research-only;
they do not call a provider, inspect or create authorization, publish dashboard
authority, or apply a recommendation.

Interpret research states literally:

- `no_sample`: zero eligible observations; no evidence.
- `insufficient_sample`: below the applicable frozen minimum shown in the
  artifact; neither positive nor negative evidence.
- `descriptive_sample`: enough for a descriptive table, not enough for a policy
  decision.
- `not_supported`: a shadow scenario failed the frozen selection rule or
  produced no material policy change; it is not proof that the scenario is
  harmful.
- `candidate`: development/validation evidence made a scenario eligible to be
  sealed for final-test confirmation; it is not production policy.
- `no_candidate_recommendations`: the sealed candidate set is empty, so final
  test did not search for or confirm an alternative.
- walk-forward `complete`: the required chronological folds and outcome purges
  ran successfully; it is not proof of causal alpha or independent stability.
- `not_evaluable`: the required comparison population is absent, such as fewer
  than two populated score buckets. Never read it as “no violations.”
- `violations_observed`: descriptive monotonicity counterexamples exist; no
  automatic model or threshold change follows.

Optional human review labels are append-only preference metadata. They are not
required for automatic outcome analysis and never tune or apply a policy. Use
the runbook's read-only feedback report before any separately confirmed append.

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

For another manual market observation, always start with:

```sh
make radar-daily-ops-readiness PYTHON=.venv/bin/python
```

Run `make radar-daily-ops-cycle PYTHON=.venv/bin/python` only when readiness says
the already-authorized provider and campaign cadence are eligible. For calendar
coverage, first supply a fresh non-fixture snapshot through the documented local
path, then rerun readiness. Do not lower thresholds, invent spread, substitute
fixtures into a live generation, or enable sends to populate the dashboard.

To compare execution-quality integration choices without selecting a venue or
calling one, run `make radar-execution-quality-readiness
PYTHON=.venv/bin/python`. The concise option matrix and copyable human decision
template are in
[Decision Radar execution-venue decision package](DECISION_RADAR_EXECUTION_VENUE_DECISION_PACKAGE.md).
Multiple-venue research is comparative only and still requires one primary
execution surface before Protocol v2 can seal its cost model. No spread/depth
adapter or order behavior exists until the operator identifies the intended
spot, perpetual, DEX, or comparative research boundary.
