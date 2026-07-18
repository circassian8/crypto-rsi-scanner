# crypto-rsi-scanner

Research-oriented crypto RSI scanner and human-decided Event Alpha Crypto Radar.

## Local Crypto Radar dashboard

`make radar-dashboard` serves the current Crypto Decision Radar operator
generation at `http://127.0.0.1:8765/`. The seven-page terminal covers Today,
Market Radar, Ideas, Calendar, System Health, Outcomes & Learning, and Run
History; see the [operator guide](research/CRYPTO_DECISION_RADAR_OPERATOR_GUIDE.md).
It reads the exact run/revision manifest and local
artifacts only. Current research appears only when exact file/tree/run-row
fingerprints, the immutable run age, and a fresh strict doctor for the same
revision all agree. A freshness-only expiry keeps the full diagnostic shell
available under HTTP 503, with every current row suppressed and only Health,
Outcomes, and clearly labeled Run History available; identity, pointer, fingerprint,
schema, or integrity failures remain a minimal unavailable response. It does
not call providers, send notifications, trade, paper
trade, write normal RSI rows, or create `TRIGGERED_FADE`. Run
`make radar-dashboard-smoke` for the deterministic fixture/no-write render gate
and `make radar-dashboard-ux-smoke` for primary-page semantic and responsive
contracts.

Live generations expire after six hours. The campaign's 60-minute observation
spacing remains a provider-safety minimum. Daily Operations v1.1 can maintain
that freshness, but the LaunchAgent is prepared and disabled until explicitly
installed. Readiness/status make no provider call and refresh only a bounded,
credential-free current-status receipt; one manual cycle remains explicit:

```sh
make radar-daily-ops-readiness PYTHON=.venv/bin/python
make radar-daily-ops-status PYTHON=.venv/bin/python
make radar-daily-ops-cycle PYTHON=.venv/bin/python
```

Every cycle runs readiness before a possible call, makes at most one already-
authorized CoinGecko no-send observation when cadence permits, uses a unique
immutable namespace, and strict-doctors before publication. Its immutable
prepublication attempt audit is followed by a final publication receipt only
after exact pointer publication, then an operations receipt only after the
owned dashboard restart and terminal success. Campaign history keeps attempt,
publication, operations, and current authority separate; contradictory phases
fail closed. During restart, the exact pointer-started process may bootstrap
from the publication receipt, but GET/HEAD stays 503 until the operations
receipt exists; a bounded HTTP probe must then return trusted 200 content with
the exact namespace/run/revision/operator digest while the same positive owned
PID remains running before and after the request. Pointer publish, rollback,
invalidation, and reconciliation share one descriptor-anchored mutation
transaction, so an artifact-root pathname replacement cannot redirect pointer
I/O. Rollback restores only prior bytes bound by their immutable receipt, and a
later failed terminal row for the same cycle invalidates the earlier success
receipt. The one-time `reconcile-publication` CLI can seal an already-proven
legacy success only from its exact pointer and unique successful terminal cycle;
it makes no provider call or restart and is never run by readiness:

```sh
make radar-daily-ops-reconcile-publication PYTHON=.venv/bin/python
```

Readiness revalidation preserves the exact publication-pointer bytes. The
explicit reconciliation command can repair only a historical
`authority_checked_at`-only rewrite from the pre-v1.1 readiness behavior; any
other pointer drift remains blocked.

A failed publication/restart/receipt preserves prior authority or invalidates only the
failed new pointer. A loaded LaunchAgent with a non-zero last exit is reported
as unhealthy rather than merely “loaded.”

The dashboard labels authorization at the last cycle as historical and reads
current authorization/call eligibility only from the expiring credential-free
status receipt; GET/HEAD never inspect environment variables. When maintenance
is disabled, cadence is eligible, and authority is within 90 minutes of expiry,
Today and System Health show the remaining time and exact manual readiness,
confirmed installation, and confirmed disable commands without executing them.
Installation remains a separate human action:
`CONFIRM=1 make radar-daily-ops-install PYTHON=.venv/bin/python`; remove only
that owned job with the corresponding confirmed `radar-daily-ops-uninstall`.

### Private phone access

The dashboard can be opened on a phone through private Tailscale Serve without
changing its loopback-only bind or creating a dashboard password/token. Install
the Tailscale app on the phone, sign in to the same tailnet as this Mac, and make
sure the Mac is awake, connected to Tailscale, and running a current dashboard
backend. Then use:

```sh
make radar-dashboard-phone-readiness PYTHON=.venv/bin/python
make radar-dashboard-phone-status PYTHON=.venv/bin/python
CONFIRM=1 make radar-dashboard-phone-enable PYTHON=.venv/bin/python
CONFIRM=1 make radar-dashboard-phone-disable PYTHON=.venv/bin/python
```

The first activation may require one Tailscale admin sign-in and **Enable
HTTPS/Serve** consent in the browser. Approve only that private tailnet feature,
not Funnel, then rerun the confirmed enable command.

Enable prints the private HTTPS URL to open on the phone. Access is governed by
the tailnet's users, devices, and ACL/grant policy, so review that trust boundary
before enabling it on a shared tailnet. This workflow never binds the dashboard
to the LAN, uses Tailscale Funnel, creates a URL token, or exposes it to the
public internet. If the phone is lost, disable the route immediately, revoke the
old phone in Tailscale's device administration, enroll the replacement phone,
then rerun readiness and enable. See the
[operator guide](research/CRYPTO_DECISION_RADAR_OPERATOR_GUIDE.md) for the full
workflow.

### Temporary public phone link

For the simplest no-tailnet option, an explicitly confirmed Cloudflare Quick
Tunnel can publish the unchanged loopback dashboard at a random public HTTPS
address:

```sh
make radar-dashboard-public-readiness PYTHON=.venv/bin/python
CONFIRM=1 make radar-dashboard-public-enable PYTHON=.venv/bin/python
make radar-dashboard-public-status PYTHON=.venv/bin/python
CONFIRM=1 make radar-dashboard-public-disable PYTHON=.venv/bin/python
CONFIRM=1 make radar-dashboard-public-guard PYTHON=.venv/bin/python
```

No Cloudflare account, domain/DNS setup, router port, LAN bind, or Tailscale client is
required. This route is deliberately temporary, unauthenticated, and not
started at login: anyone who has the printed `trycloudflare.com` URL can read
the dashboard until the owned tunnel is stopped or dies. Enable requires a
current authoritative dashboard identity and publishes only after its random
hostname serves that dashboard over HTTP 200. It never calls data providers.
The optional `RSI_RADAR_PUBLIC_MAX_LIFETIME_MINUTES` (default 240) expires the
trusted receipt and suppresses its URL; it does not itself terminate the
external process. Status warns that an expired tunnel may still be public, and
the confirmed guard stops only the exact owned process when expired or
unhealthy. Treat the URL as sensitive, stop it when finished, and use private
Tailscale Serve as the recommended persistent mode.

Official U.S. macro schedules have a separate guarded producer for Fed FOMC,
BLS CPI/employment, and BEA PCE/GDP. Readiness makes no call. Live acquisition
requires the already-present calendar authorization; BLS additionally requires
an honest contact. Each configured source is attempted at most once and reports
`observed`, `no_results`, `unavailable`, `missing_configuration`, `parse_error`,
or `rate_limited`. Accepted raw bytes remain immutable and fingerprinted, so a
valid Fed or BEA result can survive another source's failure. Snapshot status is
`complete`, `partial`, or `unavailable`; the Calendar page names missing sources,
and an unavailable source with zero rows is never presented as “no events.” An
explicit no-network local import accepts any genuine operator-downloaded source
subset with its real acquisition timestamp. Checked-in fixture/test/mock/replay
paths are rejected. Complete and partial successes are hash-attested before
Daily Operations can attach them to a generation:

```sh
make radar-calendar-official-readiness PYTHON=.venv/bin/python
make radar-calendar-official-acquire PYTHON=.venv/bin/python
make radar-calendar-official-import-local \
  FED_FOMC_HTML=/path/to/fomc.html \
  OFFICIAL_MACRO_OBSERVED_AT=2026-07-15T00:00:00Z \
  PYTHON=.venv/bin/python
```

Add `BLS_CALENDAR_ICS=...` and/or `BEA_RELEASE_DATES_JSON=...` when those genuine
exports are available. Unlinked macro rows remain context/risk only and never
manufacture directional bias.

The owner selected Bybit USDT-linear perpetuals as the intended
execution-quality surface, using public market data only. Run
`make radar-execution-quality-readiness PYTHON=.venv/bin/python` for the current
static/no-network truth and `make radar-execution-quality-bybit-smoke
PYTHON=.venv/bin/python` for the offline V5 fixture normalizer. The separately
gated public REST adapter and immutable capture contract are implemented but
inactive. Its read-only preflight is `make
radar-execution-quality-bybit-readiness PYTHON=.venv/bin/python`; `make
radar-execution-quality-bybit-status PYTHON=.venv/bin/python` validates the
latest capture. Both make no provider call or write. Capture remains blocked
unless `RSI_DECISION_RADAR_BYBIT_EXECUTION_QUALITY_LIVE=1` is already present,
and then `CONFIRM=1 make radar-execution-quality-bybit-capture
PYTHON=.venv/bin/python` performs at most two public GETs per current Radar
asset, with no retries, credentials, private data, orders, or sends. A complete
capture immutably stores exact response bytes, request timing, authoritative
universe identity, normalized USDT observations, fingerprints, receipt, and
latest pointer; partial runs are not published. A fresh capture can satisfy the
input-quality contract, but remains ineligible as Protocol-v2 evidence until
the sealed annex explicitly binds its capture ID. The stdout-only `...-collect`
target remains a diagnostic probe. The exact top-30 Radar/active-contract set
is not frozen, no genuine capture exists, and live reachability remains
unverified after the recorded 403;
403/429/region failures stop immediately without proxy, VPN, alternate-host, or
region bypass. Disable the provider boundary by unsetting the authorization
flag.

Venue-native derivatives context is a separate boundary. The offline contract
is `make radar-derivatives-bybit-smoke PYTHON=.venv/bin/python`; no-call
readiness is `make radar-derivatives-bybit-readiness PYTHON=.venv/bin/python`.
It requires one genuine fresh execution-quality capture for the exact current
authority and separately present
`RSI_DECISION_RADAR_BYBIT_DERIVATIVES_LIVE=1`. Only then may `CONFIRM=1 make
radar-derivatives-bybit-collect PYTHON=.venv/bin/python` perform exactly four
public GETs per eligible instrument—ticker, settled funding, 1h open interest,
and 1h account ratio—with no retry. It rechecks capture/instrument/authority
identity after the responses and writes nothing. Exact response bytes stay in
memory for a future immutable capture contract; no genuine derivatives capture
or Protocol-v2 evidence exists yet. Unset the flag to close this boundary.

`make radar-calendar-preview` prints the unified macro/crypto calendar fixture
without provider calls, artifact writes, or sends.
Integrated runs normalize scheduled and fixture rows once and persist only
payload-free accepted/rejected/deduplicated counters in the exact canonical run
row; `main.py --event-alpha-runs` shows that accounting without retaining
rejected titles, URLs, sources, or exception text.

Crypto Radar Decision Model v2 may surface transparent market-led research
ideas without a known catalyst when freshness, identity, liquidity, spread,
turnover, volume, dedupe, and safety gates pass. These are research ideas, not
trade instructions. Legacy Event Alpha routes remain separate.
Each v2 route has its own `RSI_EVENT_ALPHA_DECISION_MODEL_V2_ROUTE_*_ENABLED`
switch; these switches never authorize legacy routing or delivery.

## CI safety

GitHub Actions is configured for safe verification only. Push and pull-request
CI first checks the universal hash-pinned dependency lock and audits it for
known vulnerabilities, then runs the canonical `make verify` on Python 3.11 and
3.13 (standalone compatibility, pytest, alert render, fixture backtest, and
paper scoreboard) with `RSI_EVENT_ALERTS_ENABLED=0`. Static architecture reports
run once on 3.13. The manual Event Alpha smoke workflow runs the fixture/no-call
targets on both supported Python versions. CI does not load `.env`, provider API
keys, Telegram tokens, live-provider allow flags, live-send targets, trading,
paper trading, execution, normal RSI signal writes, or Event Alpha
`TRIGGERED_FADE` creation.

All third-party workflow actions are pinned to immutable full release commit
SHAs with readable version comments. The current checkout/setup actions use
their supported Node 24 releases; weekly Dependabot proposes reviewed SHA
updates instead of silently following mutable major tags.

`requirements.in` records direct dependency intent; `requirements.txt` is the
cross-platform, Python 3.11+-compatible hash-pinned environment used by
bootstrap and CI. Install the pinned dependency tools with
`make dependency-tools`, update the lock with
`make lock-dependencies UPGRADE=1`, and run
`make dependency-verify` before accepting dependency changes.

Artifact-heavy review checkouts use the same gates without recursively walking
cumulative operational stores during unrelated fixture tests. `test-full` and
`verify-fast` write cumulative per-file timing reports to
`.pytest_cache/test_file_timing_report.{json,md}`. The separate
`make test-artifact-heavy-extracted-checkout PYTHON=python3` guard runs its
isolated synthetic project-health case with a 5-second default budget and writes
focused timing reports under `.pytest_cache/artifact_heavy_extracted_checkout_timing.*`.
For reproducible source-with-artifacts review, run that focused guard in the
extracted checkout immediately before `make verify-fast PYTHON=python3` and
retain both timing-report pairs with the release evidence. The practical
same-machine `verify-fast` review budget is 360 seconds. It is an observational
release budget, not a hard CI timeout; investigate a run above 360 seconds or
more than 25% slower than the latest comparable same-machine baseline.
Project-health retention reporting is bounded to 128 namespaces and 128 direct
entries per namespace, reads no research payloads beyond the bounded
namespace-status control marker, and is advisory: it never compacts or deletes
canonical audit history without a separately approved retention policy. A
truncated namespace inventory blocks the report instead of claiming complete
coverage.
