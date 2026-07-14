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
spacing remains a provider-safety minimum. Daily Operations v1 can maintain
that freshness, but the LaunchAgent is prepared and disabled until explicitly
installed. Read-only status and one manual cycle are:

```sh
make radar-daily-ops-readiness PYTHON=.venv/bin/python
make radar-daily-ops-status PYTHON=.venv/bin/python
make radar-daily-ops-cycle PYTHON=.venv/bin/python
```

Every cycle runs readiness before a possible call, makes at most one already-
authorized CoinGecko no-send observation when cadence permits, uses a unique
immutable namespace, strict-doctors before publication, preserves or
invalidates authority on failure, and restarts only the exact owned dashboard
after success. A loaded LaunchAgent with a non-zero last exit is reported as
unhealthy rather than merely “loaded.” Installation remains a separate human action:
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
requires the already-present calendar authorization plus an honest BLS contact;
an explicit local import requires all three operator-downloaded files and their
real acquisition timestamp. Checked-in fixture/test/mock/replay paths are
rejected. Successful packs are immutable and hash-attested before Daily
Operations can attach them to a generation:

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

Execution-quality integration is intentionally venue-neutral. Run
`make radar-execution-quality-readiness PYTHON=.venv/bin/python` to compare
feasible spot, perpetual, and DEX inputs; no adapter is activated until the
operator selects the intended execution venue.

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
