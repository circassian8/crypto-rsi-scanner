# AGENTS.md — working agreement for AI collaborators (Claude + Codex)

This repo is co-developed by a human owner and two AI coding agents (Anthropic
**Claude**, OpenAI **Codex**). **Read this file first, every session.** It is the
shared source of truth for how we work, the architecture, and what we've learned.

> ✅ **This repo is under git (branch `main`, remote `origin`).** Commit and push
> at the end of every change-making prompt (see "Commit and push every change").
> `DEVLOG.md` remains the human-readable narrative/decision history — keep both
> current.

---

## The one rule: log every change

After any non-trivial change, **prepend an entry to `DEVLOG.md`** using the
template at the top of that file. State *why*, *what files*, and *how you
verified*. No silent changes — the other agent and the human rely on the log to
understand the current state.

Sign your entry with your name (`Claude` / `Codex` / `human`).

## The other rule: commit and push every change

This is a git repo with a GitHub remote. **End any prompt that changed files
with one commit and push it to `origin/main`** capturing that prompt's work, with
a clear message:
- One logical commit per change-making prompt (don't fold in unrelated prompts).
- Run the risk-appropriate verification gate before committing. Do not default
  to full pytest/`make verify` for every small prompt; use the verification
  ladder in "Run / test / deploy" below, and record exactly what ran in
  `DEVLOG.md`.
- Never commit secrets/artifacts: `.env`, `*.db`, logs, `.venv`, and
  `.claude/settings.local.json` are gitignored — keep it that way.
- Commit on `main`, then `git push` after the commit. The human gave standing
  approval on 2026-06-16 to push after every commit. Ask again only before
  changing remotes, force-pushing, or pushing to a different branch.
- After each successful commit + push, also provide a fresh project zip for
  Pro-model review. Include the current source plus local research artifacts
  such as `event_fade_cache/`, but never include secrets or machine-local noise
  (`.env`, DBs, logs, `.venv`, `.git`, IDE files, caches).
- **Do not create one-off timestamped/hash-suffixed review zips.** The human
  wants a single overwrite-in-place review artifact. Use
  `make export-src-with-artifacts`, which writes
  `crypto_rsi_scanner_source_with_artifacts.zip`, and overwrite that same file
  every time.

## Collaboration files

| file | purpose |
|---|---|
| `DEVLOG.md` | Newest-first history of completed non-trivial changes. |
| `ROADMAP.md` | Current pending work, blocked items, and priorities. |
| `DECISIONS.md` | Durable accepted/rejected decisions and revisit conditions. |
| `CLAUDE.md` | Thin Claude Code bridge back to this protocol. |
| `research/` | Checked-in research notes for backtest reviews and non-code conclusions. |
| `fixtures/backtest_smoke/` | Checked-in BTC/ETH/SOL daily klines for offline backtest smoke. |

Current architecture and project-health reports use `ARCHITECTURE_*` and
`PROJECT_HEALTH_*` names. Historical refactor-period reports live only under
`research/archive/refactor_history/` for auditability; do not add new current
tooling, docs, or tests that depend on refactor-era report names.
Event Alpha product work should now align with
`research/EVENT_ALPHA_RADAR_NORTH_STAR.md` / `.json`: the measurable radar
architecture, lane definitions, source activation order, and 30-day no-send
burn-in contract.

Before starting substantial work, read `ROADMAP.md` and `DECISIONS.md` after this
file. When a change completes or changes priority/status, update `ROADMAP.md`.
When a choice should prevent future relitigation, add or update `DECISIONS.md`.

---

## Project in one paragraph

A top-100 crypto multi-timeframe **RSI overextension scanner** plus a
research-only **Crypto Radar** for human trader assistance. Each day it pulls
the top coins from CoinGecko, computes Wilder RSI (daily/4H/weekly) plus context
(z-score, volume, divergence, BTC correlation, trend regime), classifies each
signal into a **setup type** (mean_reversion / dip_buy / trend_continuation /
breakdown_risk), scores conviction, **gates it by the BTC market regime**, and
sends tiered alerts to Telegram. It self-grades past signals, paper-trades them,
and a separate `backtest.py` validates strategy ideas on years of history.
**Deployed live** on the owner's Mac via launchd (daily scan + always-on bot).

---

## Run / test / deploy

### Supported release matrix

| environment | support status | verification status |
|---|---|---|
| macOS normal checkout | supported | verified |
| macOS source-with-artifacts archive | supported | verified |
| Linux normal checkout | supported | verified in CI on Python 3.11 and 3.13 |
| Linux source-with-artifacts archive | optional portability coverage | currently unverified; not release-blocking and not Linux-certified |

The personal production/operator environment is macOS. Do not install a VM or
container runtime, transfer the review archive, or change the host solely to
obtain the optional Linux artifact-bearing observation. Linux source-only CI
remains a required compatibility gate; exact Linux artifact-bearing verification
may be added later when a suitable environment already exists.

- **Python:** `.venv/bin/python` (3.13 default via `.python-version`); supported
  CI/runtime compatibility is Python 3.11 and 3.13. Direct dependency intent is
  in `requirements.in`; `requirements.txt` is the generated universal,
  SHA-256-pinned install set (including `pytest` and `pytest-xdist`). Do not edit
  the lock by hand. Use `make dependency-tools`, `make lock-dependencies`
  (`UPGRADE=1` only for an intentional refresh), and `make dependency-verify`.
  Third-party GitHub Actions must use a full 40-character release commit SHA
  with the human-readable release tag in a comment; weekly Dependabot updates
  the pinned commits. Do not restore mutable major-version action tags.
  `make bootstrap` creates `.venv` from the hash-pinned lock. `make verify` runs
  the full pytest suite via `test-full` and hard-fails if pytest is missing;
  `make verify PYTHON=python3` is acceptable for source-archive review.
  For local iteration, prefer targeted tests over the full pytest package gate:
  run the focused pytest file/package for touched code, `python3 -m compileall -q
  crypto_rsi_scanner tests` for Python changes, and the matching Make smoke or
  doctor target for Event Alpha/provider/notification paths. Docs/report-only
  prompts can use `git diff --check`, JSON validation, and the relevant static
  report target. Use `make verify-fast PYTHON=python3` when a broader local gate
  is warranted but the duplicate standalone runner is not useful. Use
  `make test-pytest-durations PYTHON=python3` to profile slow tests and
  `make test-pytest-parallel PYTHON=python3 PYTEST_WORKERS=4` when xdist is
  installed. `test-full` (and therefore `verify-fast`) records cumulative
  setup/call/teardown time by test file in
  `.pytest_cache/test_file_timing_report.{json,md}` without rerunning tests.
  `make test-artifact-heavy-extracted-checkout PYTHON=python3` is the focused
  cumulative-artifact performance guard: its synthetic extracted checkout must
  stay below `ARTIFACT_HEAVY_TEST_MAX_SECONDS` (5 seconds by default), project
  health may inspect at most 128 namespaces and 128 direct entries per
  namespace, may read only the bounded namespace-status control marker, and must
  never recursively scan research payloads, compact, or delete. Truncating the
  namespace inventory is an explicit blocker, not a false complete report. The
  same-machine extracted source-with-artifacts `verify-fast` review budget is
  360 seconds; it is observational rather than a flaky CI wall-clock gate.
  Investigate a run above 360 seconds or more than 25% slower than the latest
  comparable same-machine baseline before release.
  The standalone compatibility runner behind `make test` always starts one
  disposable artifact/discovery root, strips ambient per-store path overrides,
  disables sends, and removes that root on exit. This preserves namespace-
  relative test behavior while preventing the compatibility pass from appending
  to cumulative operator stores. A release sequence must compare the real
  artifact tree and dashboard pointer before/after when authority neutrality is
  part of the acceptance evidence.
  Run full `make verify` for release-style handoff, risky shared
  code changes, CI/parity checks, before live/provider activation work, after a
  cluster of roughly 5-10 low-risk prompts, or whenever targeted evidence is
  not enough. If you skip full `make verify`, say why and list the targeted gate
  that passed.
- **Clean source export:** `make export-src` writes
  `crypto-rsi-scanner-source.zip` via `git archive` so ignored local artifacts
  such as `.env`, DBs, logs, caches, and `.venv` are not shared.
- **Source + research artifacts export:** `make export-src-with-artifacts`
  overwrites `crypto_rsi_scanner_source_with_artifacts.zip` with current
  committed source plus only the canonical project evidence selected by
  `research/DECISION_RADAR_PROJECT_ARTIFACT_POLICY.json`. The project policy
  retains exact operator controls, current pointer and latest genuine
  live/no-send namespaces, shared campaign/source-contract/calendar state, and
  the separately governed canonical empirical evidence. Superseded, fixture,
  failed, rehearsal, and other noncanonical artifacts remain immutable locally
  and are excluded from the standard ZIP; `make
  export-project-artifact-history` copies their exact disjoint complement into
  one fixed optional ignored archive with an immutable manifest and checksums.
  Neither export deletes, moves, compacts, or rewrites artifacts. Both exclude
  secrets, DBs, logs, virtualenvs, git data, caches, and other zip files. The
  supported exporter is read-only with respect to source and research inputs
  and writes one reproducible, UTC-safe ZIP timestamp for every entry (the ZIP
  epoch by default, or a wall-clock-safe `SOURCE_DATE_EPOCH`). It must retain
  the descriptor-anchored symlink/TOCTOU, bounded-inventory, exact-selection,
  post-write source-drift, and secret-scanning gates; never normalize review
  archives by mutating input mtimes. Missing optional canonical sources are
  reported as partial coverage, never healthy-empty. Tests that do not
  explicitly verify shipped artifacts use isolated temporary artifact bases;
  cumulative root stores are excluded from unrelated fixture tests. In an
  supported macOS extracted source-with-artifacts review checkout, run `make
  test-artifact-heavy-extracted-checkout PYTHON=python3` before `make
  verify-fast PYTHON=python3`; retain both timing-report pairs as release
  evidence. Running the same commands against an exact Linux archive is useful
  optional portability coverage, not a release gate or a Linux certification.
- **Deterministic event research clock:** event fixture/review commands may set
  `RSI_EVENT_RESEARCH_NOW` or pass `--event-now`. Fixture-oriented Make targets
  use `EVENT_FIXTURE_NOW` (default `2026-06-15T16:00:00Z`) so checked-in June
  2026 event fixtures do not age out of lookback windows. Production/profiled
  notification Make targets leave `EVENT_RESEARCH_NOW` blank by default and use
  wall-clock UTC unless the operator explicitly sets it; stale/future fixed
  clocks block actual notification sends unless
  `RSI_EVENT_ALPHA_ALLOW_FIXED_NOW_FOR_NOTIFY=1` is set.
- **Standard verification:** `make verify` (full release gate: standalone
  compatibility runner + pytest package suite + alert render smoke + backtest
  fixture smoke + paper scoreboard). Use it intentionally, not as the default
  loop for every prompt.
- **Targeted tests:** choose the smallest meaningful gate for the files touched:
  focused pytest file/package, `tests/test_indicators.py` for umbrella runner
  changes, compileall for Python import/syntax risk, and matching Event Alpha
  smoke/doctor targets for artifact behavior.
- **Alert render smoke (no sends/network):** `make smoke-alerts`
- **Local Crypto Radar dashboard:** `make radar-dashboard` serves exact-current
  operator artifacts read-only on `127.0.0.1:8765`. Current content requires
  complete v1 file/tree/canonical-run fingerprints plus a fresh immutable run
  and fresh full strict doctor for the exact revision; untrusted current data is
  suppressed, and the smoke fails rather than rendering a false green. `make
  radar-dashboard-readiness ARTIFACT_NAMESPACE=...` is strictly read-only;
  publication is a separate `CONFIRM=1 make radar-dashboard-publish
  ARTIFACT_NAMESPACE=...` boundary that accepts only a receipt-backed Daily
  Operations generation and rejects fixture/legacy namespaces. Inspect with
  `make radar-dashboard-authority-status` and remove only an exact named pointer
  with confirmed `radar-dashboard-invalidate`. Without an explicit command-line
  namespace, the dashboard and readiness command use the pointer and never
  guess the newest directory. Pointer-mode serving is bound to the
  exact run/revision/operator-state hash and fails closed if it drifts. `make
  radar-dashboard-smoke` renders all fixture pages without starting a server,
  calling providers, sending, or writing artifacts. The loopback WSGI serving
  layer handles clients concurrently so one incomplete local connection cannot
  block every later GET/HEAD request. A trusted zero-idea generation still
  renders its exact market-observation scan and per-source coverage state;
  healthy-empty, unconfigured, and degraded layers are never collapsed into the
  same empty message. Shared campaign outcomes are labeled historical and
  non-authoritative rather than mixed into the current namespace's counts. One
  descriptor-anchored namespace is held for the complete load, manifest counts
  are reconciled to the exact snapshot/anomaly rows, and raw anomaly scan
  evidence remains visibly separate from canonical Decision candidates.
- **Phone dashboard access:** keep the dashboard backend on
  `127.0.0.1:8765`. Private access may use Tailscale Serve HTTPS to identities
  permitted by the owner's tailnet policy. The owner also explicitly approved
  an unauthenticated, temporary Cloudflare Quick Tunnel on 2026-07-14 for easier
  public phone access. Use `radar-dashboard-phone-*` for the private route and
  `radar-dashboard-public-*` for the public route; readiness/status are
  observational and every enable/disable/public-guard mutation requires
  `CONFIRM=1`. Tailscale Serve is the recommended persistent mode. The public
  helper may start only an exact owned `cloudflared` process, may expose only the
  loopback dashboard, must pin HTTP/2 plus non-debug logging, and must verify the
  local dashboard identity, edge registration, and public HTTP 200 surface
  before publishing the URL. It must never create an account, named tunnel,
  owner-controlled DNS record, credential, configuration file, startup service,
  or permanent URL. Anyone with its random `trycloudflare.com` link can read the
  dashboard. Its optional trusted-receipt lifetime defaults to 240 minutes;
  expired or locally-unhealthy state suppresses the URL but does not itself
  stop the external process. Status must warn that it may remain public, and
  the confirmed guard may stop only the exact owned process. Keep it off when
  not needed. Never bind the dashboard to a
  LAN/wildcard address, enable Tailscale Funnel, add a credential-bearing URL,
  open a router port, reset unrelated Serve configuration, or kill an unowned
  process. A stale/untrusted dashboard, unsafe private Serve state, unowned
  public-process state, malformed public URL, or failed public probe must fail
  closed.
- **Decision Radar Daily Operations v1.1:** `make radar-daily-ops-readiness` and
  `make radar-daily-ops-status` make no provider call and atomically refresh one
  bounded, credential-free current-status receipt;
  `make radar-daily-ops-cycle` performs at most one already-authorized,
  cadence-eligible CoinGecko no-send observation. Every attempt gets a unique
  namespace and bounded attempted/terminal journal rows. Publication requires
  complete operator state and strict doctor success. It preserves the immutable
  prepublication attempt audit, then writes an immutable final publication
  receipt after exact pointer publication and an immutable operations receipt
  only after the exact owned loopback dashboard restart and terminal success.
  Both final receipts bind the namespace/run/revision, operator-state digest,
  artifact fingerprints, doctor result, and pointer; the publication receipt
  also binds the exact prepublication audit digest. Strict doctor and readiness
  block contradictory phase state. Pointer-started restart may bootstrap after
  the publication receipt, but GET/HEAD remains 503 until the operations
  receipt exists. A bounded HTTP probe then requires trusted 200 content, exact
  namespace/run/revision/operator-digest response headers, and the same positive
  owned PID before and after the request. Pointer publish, rollback,
  invalidation, and reconciliation share one descriptor-anchored mutation
  transaction; replacing the artifact-root pathname cannot redirect its pointer
  reads, writes, or removals. Rollback requires the prior receipt's exact
  pointer mapping and digest. A later failed terminal row for the same cycle
  invalidates the earlier success receipt. Campaign history reports attempt
  audit, publication, operations, and current authority separately. The
  explicit `make radar-daily-ops-reconcile-publication
  PYTHON=.venv/bin/python` command may seal a proven legacy success only
  when one exact terminal cycle already records pointer publication plus owned
  restart; it makes no provider call or process restart, and readiness never
  invokes it automatically. Revalidating the same authority preserves the exact
  pointer bytes; explicit reconciliation may repair only the historical
  `authority_checked_at`-only rewrite produced by the pre-v1.1 readiness path.
  Any publication, restart, probe, receipt, or terminal-state
  failure must restore the prior pointer or invalidate only the failed new
  pointer. Re-read cadence after an actual attempt without crossing the provider
  boundary again. Historical `authorization_at_last_cycle` remains distinct
  from the expiring persisted `current_authorization_status` and
  `current_provider_call_eligibility`; dashboard GET/HEAD never inspects the
  environment. When maintenance is disabled, cadence is eligible, and authority
  is within 90 minutes of expiry, Today and System Health show the remaining
  time, the exact no-provider readiness command, and the separately confirmed
  install/disable commands without running them. The LaunchAgent stays
  prepared/disabled until `CONFIRM=1 make radar-daily-ops-install`; confirmed
  uninstall removes only the exact owned service. Never embed authorization or
  credentials in its plist.
- **Event Alpha evidence-cycle readiness:**
  `make event-alpha-evidence-cycle-readiness PROFILE=notify_llm_quality
  ARTIFACT_NAMESPACE=<namespace>` is read-only, no-network, and no-write. It
  reports deterministic planner hints separately from HTTP fan-out, persisted
  plan truth, current source configuration, explicit authorization, credential
  presence, provider health/backoff, LLM availability, and the next safe
  command. A profile describes capability; it never creates provider or OpenAI
  authorization. Relationship, extractor, and catalyst-frame OpenAI stages
  each require their matching already-present explicit opt-in; readiness's
  request bound covers evidence-acquisition planner fan-out only. Live-style
  dispatch has no fixture/default fallback,
  Coinalyze and sports hints stay unavailable until real adapters exist, and
  fixture/test/mock/replay local paths are rejected. Offline fixture LLM
  evaluation remains allowed because it crosses no provider boundary. The
  writing `event-alpha-evidence-validation-cycle` requires both a passing
  `--require-cycle-ready` guard and `CONFIRM=1`, uses a unique namespace, keeps
  alerts disabled, and never sets authorization. Without a currently eligible
  genuine source, use the reported artifact preview and make no provider call.
- **Source-independence OOS review:** use the
  `event-alpha-source-independence-oos-export`, `...-validate`, and `...-report`
  targets to freeze `development`/`review`/`test` by
  `event_copy_family_id`. Exact source or normalized-content reuse across
  partitions is invalid, pending labels return non-success, and reports remain
  descriptive. Never change the `0.80` Jaccard threshold, 12-token minimum,
  normalization, scores, or routes from this workflow without enough
  independent labels and explicit human approval.
- **Official Decision Radar macro calendar:** use
  `radar-calendar-official-readiness` before the guarded Fed/BLS/BEA producer.
  Live acquisition is off by default and needs the already-present calendar
  authorization; BLS additionally needs an honest contact. It performs at most
  one request per configured source and never follows redirects. Each source is
  independently `observed`, `no_results`, `unavailable`,
  `missing_configuration`, `parse_error`, or `rate_limited`; accepted source
  bytes remain immutable and fingerprinted even when another source fails.
  Snapshot status is `complete`, `partial`, or `unavailable`, and zero rows from
  an unavailable source never means no events. Local import is no-network,
  accepts an explicit subset of genuine operator-downloaded sources, and
  requires a real acquisition time; direct fixture/test/mock/replay paths are
  rejected before writes. Preserve Fed window uncertainty and exact BLS/BEA
  timezones. Latest complete or partial success may be consumed only after
  pointer, receipt, snapshot, source-coverage, and accepted raw-source hash
  attestation; an unavailable attempt never replaces it. Unlinked calendar
  events remain context/risk only and cannot manufacture directional bias.
- **Execution-quality readiness:**
  `make radar-execution-quality-readiness` is static/no-network and reports
  the owner-confirmed Bybit USDT-linear perpetual public-data research surface
  plus feasible inactive alternatives. The concise checked decision package is
  `research/DECISION_RADAR_EXECUTION_VENUE_DECISION_PACKAGE.md`; the structured
  form is available from `radar-execution-quality-readiness-json`. The confirmed
  universe rule intersects the top 30 liquidity-ranked Radar assets with exact
  active `LinearPerpetual`, `Trading`, USDT-quoted, USDT-settled, non-prelisting
  contracts and freezes the resulting IDs only in the Protocol-v2 annex. Run
  `make radar-execution-quality-bybit-smoke` for the offline fixture normalizer;
  it preserves clocks/sequence and computes spread, USDT depth, and
  USDT-notional impact without silent USD conversion. Snapshot schema v2 states
  that the 200-level public REST book excludes RPI orders and labels impact as a
  deterministic visible-book walk, not realized execution or complete venue
  liquidity. The separately gated
  public REST adapter and immutable capture contract are implemented but
  inactive. `make radar-execution-quality-bybit-readiness` binds to the exact
  authoritative Radar generation, and `make
  radar-execution-quality-bybit-status` validates the latest capture; neither
  makes a provider call or write. Capture requires the already-present
  `RSI_DECISION_RADAR_BYBIT_EXECUTION_QUALITY_LIVE=1` plus the exact
  `CONFIRM=1` target, performs at most two fixed-host public GETs per
  provider-query-eligible current asset, follows no redirects, ignores ambient
  proxies, and makes no retries. Non-contract-shaped Radar symbols are excluded
  before the provider boundary; the full ranked universe, exact query subset,
  and reason-coded exclusions remain immutable in the capture. The initial
  Radar-symbol-to-Bybit-base join is an auditable candidate join, not confirmed
  canonical identity; exact IDs stay pending human confirmation in the sealed
  Protocol-v2 annex. If no query candidate resolves to an eligible exact active
  perpetual, collection fails before any order-book request or publication. A
  complete capture immutably stores only the closed exact
  authority/universe, accepted raw responses, request timing, normalized USDT
  observations, fingerprints, manifest, completion receipt, and latest pointer. Validation
  holds one descriptor-anchored namespace for the complete read, rederives all
  projections from the raw bytes, and rejects drift or pointer rollback. The
  exact Radar authority identity and full ranked universe are re-resolved after
  provider collection and before the first immutable capture write; expiry,
  replacement, or universe drift leaves no Bybit capture pointer. The
  standard review archive selects and fully revalidates only the latest complete
  capture. A fresh capture may be Protocol-v2 input-quality eligible, but stays
  `protocol_v2_evidence_eligible=false` and `protocol_v2_annex_bound=false`
  until the sealed annex explicitly binds its immutable capture ID. The
  stdout-only `...-collect` target remains diagnostic. The recorded Bybit 403
  remains an honest reachability blocker; stop on 403/429/region restriction
  and never use a proxy, VPN, alternate host, or region bypass. The
  selection/readiness never creates runtime authorization,
  credential/private-data permission, order permission, or trading permission.
  Unset the authorization flag to disable the collection boundary; no provider
  process or order surface exists.
- **Venue-native Bybit derivatives context:**
  `make radar-derivatives-bybit-smoke` is an offline, no-write contract for the
  selected Bybit USDT-linear perpetual surface. It normalizes supplied public
  ticker, settled-funding, 1h open-interest, and 1h long/short-account-ratio
  responses against the exact execution-quality instrument identity, preserving
  provider clocks, lineage, native USDT/base-asset units, mark/index basis, and
  explicit fraction-to-percent conversions. The bounded plan is four public GETs
  per instrument and at most 120 for the future top-30 intersection. The
  offline normalizer has no HTTP client. The guarded no-write adapter is
  implemented but inactive: `make radar-derivatives-bybit-readiness` requires a
  genuine fresh execution-quality capture for exact current authority plus
  separately present `RSI_DECISION_RADAR_BYBIT_DERIVATIVES_LIVE=1`; readiness
  makes no call or write. Confirmed collection performs the exact request set,
  never retries, retains exact transport responses in memory, and revalidates
  capture/instrument/authority identity afterward. The closed no-I/O capture-
  input contract rederives every normalized context, request timing, lineage,
  unit, and deterministic capture identity from those exact bytes and rejects
  mapping-only diagnostic results. `CONFIRM=1 make
  radar-derivatives-bybit-capture` is the separate immutable write boundary;
  `make radar-derivatives-bybit-status` revalidates the latest capture without a
  call or write. Publication holds one descriptor-anchored namespace, writes
  exact raw responses plus closed projections, manifest, completion receipt,
  and rollback-protected latest pointer, and the standard review archive selects
  only a fully revalidated latest capture. No genuine derivatives capture exists
  in the current artifact store. Every snapshot is context-only, has no directional
  authority or Decision-policy side effect, and remains Protocol-v2-ineligible
  until a separately authorized immutable capture is sealed and annex-bound.
  Coinalyze remains an optional secondary Catalyst-Radar cross-check, not a
  substitute for the selected venue-native execution, funding, OI, or
  positioning surface.
- **Direct Bybit 1h/4h readiness:**
  `make radar-intraday-bybit-smoke` proves the completed trade-price bar
  normalizer offline. `make radar-intraday-bybit-readiness` is no-network and
  no-write; it requires a complete fresh execution-quality capture for the exact
  current Radar authority plus separately present
  `RSI_DECISION_RADAR_BYBIT_INTRADAY_LIVE=1`. `make
  radar-intraday-bybit-status` validates the latest immutable capture without a
  call or write. A confirmed `radar-intraday-bybit-capture` performs exactly one
  `interval=60` and one `interval=240` public GET per eligible native
  instrument, never retries, revalidates the capture/instrument/authority chain
  after the final response, and publishes only a complete exact-response
  bundle. The bundle binds the source execution-quality capture and pointer,
  native instruments, raw bytes, request/provider clocks, normalized bars,
  fingerprints, manifest, completion receipt, and latest pointer. Validation
  holds one descriptor-anchored namespace, rederives every bar from raw bytes,
  and rejects drift, symlinks, races, and pointer rollback. The standard review
  archive selects and fully revalidates only the latest complete capture. A
  fresh bundle may be input-quality eligible but remains campaign-detached,
  `protocol_v2_evidence_eligible=false`, and
  `protocol_v2_annex_bound=false` until the sealed annex names its immutable
  capture ID. The confirmed `...-collect` target remains a stdout-only
  diagnostic and writes nothing. Never infer direct bars from CoinGecko
  snapshots, include an open candle, broaden the execution-quality authorization
  flag, or bypass a 403/region restriction.
- **Empirical Protocol-v2 readiness:**
  `make radar-research-protocol-v2-readiness` renders the frozen/static required
  evidence and annex contract without reading environment, files, credentials,
  providers, or holdout data; `make radar-research-protocol-v2-check` validates
  that exact blocked state. The executable protocol is intentionally not
  frozen or active until an exact human-approved venue/instrument, source,
  partition/untouched-holdout, outcome, cost, universe, route, episode, and
  minimum-sample annex is sealed. Missing 1h/4h, latency, spread/depth,
  catalyst, official-calendar, derivatives, on-chain, or RSI evidence remains
  unavailable and cannot be proxied. No v2 replay, selection, or final-test
  target exists; protocol-v1 final-test evidence is forbidden for tuning.
- **Empirical hardening supplement:**
  `make radar-research-hardening-supplement
  RADAR_RESEARCH_SELECTION_RUN=<exact-selection-run>` creates or identically
  resumes the fixed, separately attested development/validation supplement;
  the matching `...-check` target is the normal verification surface. It binds
  the exact seven immutable v1 reports, selection manifest/artifacts, and
  diagnostics implementation. Selection and report paths use bounded
  descriptor-relative component traversal; a nonselection/final-test manifest
  is rejected before any non-manifest leaf is opened. The supplement schema and
  diagnostic reconciliations are closed. Different existing output bytes fail
  without replacement. Route-conditioned score checks and partition-specific
  market-risk groups are descriptive only; the v1 final-test may appear only
  as an already-sealed display summary and is never read or used for selection
  here. Do not treat mixed-route monotonicity as calibration, auto-retune scores,
  or change production policy from this artifact.
- **Bounded empirical artifact exports:** the checked-in
  `research/DECISION_RADAR_EMPIRICAL_ARTIFACT_POLICY.json` is the only selection
  authority for empirical evidence in `make export-src-with-artifacts`. It binds
  four exact canonical run manifests, the frozen protocol and Protocol-v2
  readiness contract, all seven v1 reports, the separate hardening supplement,
  and bounded optional feedback. The exporter validates the supplement through
  its full closed validator against the same exact seven report byte buffers and
  carries the original verified fingerprints into the archive manifest; it must
  not reselect or silently re-fingerprint changed evidence. Superseded lab files
  remain immutable locally and are excluded from the standard review ZIP. Use
  `make export-empirical-artifact-history` only for the fixed, ignored, optional
  disjoint-complement archive with its own immutable manifest and checksums.
  Neither command deletes, moves, compacts, or rewrites evidence. Missing policy,
  manifest drift, unsafe paths, symlinks, races, invalid feedback, bounds
  violations, report/supplement splices, or secret findings fail closed and
  preserve any prior successful output.
- **Decision Radar Observation Campaign v2:**
  `make radar-market-no-send-readiness` is read-only/no-network and reports the
  already-existing CoinGecko authorization, bounded universe, enforced cadence,
  feature/time-aware warmup, spread limits, artifacts, and next safe command.
  The default minimum observation spacing is 60 minutes; too-close observations
  remain explicit evidence but never enter temporal baselines or advance
  warmup. `make radar-market-no-send` rechecks authorization, cadence, and shared
  provider backoff before the adapter and may reserve/attempt at most one bounded
  live request in one eligible invocation. It never creates authorization. A
  stable base-root cadence receipt and bounded attempt ledger survive campaign
  state-directory replacement, and the exact latest-attempt receipt prevents a
  blocked run from reusing an older complete manifest. Campaign reports use
  root no-send `attempt_id` values as individual terminal-attempt identities;
  an ID-less namespace projection may enrich a receipt only when namespace and
  observation time identify exactly one attempt and every terminal field
  agrees. Ambiguous or contradictory cross-artifact representations block the
  report rather than changing counts. Only canonical live/
  no-send provenance plus a fresh strict doctor may publish. Published
  namespaces are immutable, so later live cycles use a new namespace and seed
  their exact history snapshot from `radar_market_history_cache`; fixture/mock
  history remains isolated. `make radar-market-no-send-smoke` proves mechanics
  offline but never counts in the Decision campaign or replaces dashboard
  authority. `make radar-market-campaign-report` rebuilds the canonical
  Markdown/JSON campaign report from local artifacts without a provider call;
  the live target also refreshes it after every success or failure. Decision
  campaign generations, candidates, routes, feature maturity, and outcomes are
  never aggregated into Event Alpha Catalyst Radar's separate 30-day burn-in.
  Human review timing uses the separate append-only shared campaign ledger
  `radar_market_history_cache/event_decision_radar_review_timing_events.jsonl`.
  `make radar-review-timing-status` is read-only/no-network. Only the explicit
  confirmed `radar-review-timing-view` and `...-complete` commands may record a
  human action for one exact receipt-backed namespace/idea. Dashboard GET/HEAD,
  phone access, probes, and health checks never count as human views. Provable
  idea availability is the immutable owned-dashboard operations-receipt clock;
  every event also binds the canonical Decision projection, candidate/Core
  artifact digests, run/revision/operator identity, and both final receipts.
  Campaign reporting includes the exact point-in-time latency projection, but
  it remains `protocol_v2_evidence_eligible=false` and
  `protocol_v2_annex_bound=false` until the sealed annex fixes clock and
  missing-data rules. Review events never alter routes, scores, outcomes,
  provider authorization, or dashboard authority.
  An optional current calendar snapshot is accepted through the explicit
  `RSI_DECISION_RADAR_CALENDAR_SNAPSHOT_PATH` environment setting or the Daily
  Operations coordinator's hash-attested official-macro latest-success path. Readiness
  inspects it without network or writes; live generations reject fixture/test/
  mock/replay provenance and require the versioned current-source container.
  Container provenance plus event-row `provider`, `source`, and `source_class`
  (including nested provenance) are checked. Only the closed, secret-safe
  allowlisted source-row projection is copied into the exact
  namespace and bound into operator authority; arbitrary provider payload keys
  are never exported. Publication recomputes scheduled, unlock, and unified
  calendar rows from the same read-once hashed buffers, so rewritten artifact
  digests, duplicate keys, or split reads cannot conceal semantic drift. The
  scheduled/unlock JSONL and reports are written as one descriptor-anchored
  no-follow bundle. Absence remains visibly `not_configured`; the
  application never guesses a file, enables a provider, or falls back to a
  fixture for a live generation.
  A same-cycle market-anomaly scan may report healthy-empty only through its
  exact completion receipt with matching run/namespace device and inode, paths,
  content hashes, row semantics/lineage, and snapshot/anomaly/queue counts. Its
  four outputs are likewise one anchored atomic bundle. Generic empty sidecar
  files remain unavailable.
- **Decision Radar outcome-price recovery:**
  `make radar-outcome-price-recovery-readiness` is read-only and makes no
  provider call. It derives only exact overdue outcome windows from the
  canonical campaign report and its read-once market-history snapshot. The
  diagnostic collector requires the existing general CoinGecko authorization,
  the separate `RSI_DECISION_RADAR_OUTCOME_PRICE_RECOVERY_LIVE=1` authorization,
  and `CONFIRM=1`; it may make at most one fixed-host CoinGecko historical-range
  request per exact missing window, with a 20-request total bound and no retry,
  redirect, ambient proxy, or window expansion. A response is either an honest
  `no_results` or the first finite positive USD price inside the original
  window, bound to the exact raw-response hash and separate acquisition and
  historical-market clocks. Prefer the separately confirmed
  `radar-outcome-price-recovery-capture` command when collection is authorized:
  it seals exact request/response/result bytes, campaign pointer, history and
  outcome-ledger digests, target outcome, candidate/Core fingerprints, manifest,
  receipt, and rollback-protected latest pointer. Read-only
  `radar-outcome-price-recovery-status` fully rederives the latest capture; the
  fixed review export selects only that validated pointer target. Neither the
  diagnostic nor capture path applies a response or writes campaign baselines,
  candidates, scores, calibration evidence, or Protocol-v2 evidence. Do not add
  an application step until a separately confirmed ledger-only mutation is
  implemented and shown to leave the temporal baseline byte-identical.
- **Unified calendar no-send preview:** `make radar-calendar-preview` renders
  checked macro/crypto fixture rows without providers, artifact writes, or sends.
  Integrated cycles normalize raw scheduled/fixture rows exactly once and bind
  payload-free rejection/dedupe counters to the canonical run-ledger row; use
  `main.py --event-alpha-runs` to inspect the closed accounting contract.
- **Backtest fixture smoke (no network):** `make backtest-fixture` runs the
  default Binance-style backtest path from checked-in BTC/ETH/SOL kline fixtures.
- **Backtest research smoke:** `make backtest-costs` runs the fixture backtest
  with state slices, cost/slippage modeling, and walk-forward folds.
- **Dry scan (network, no writes/alerts):** `.venv/bin/python main.py --dry-run --top-n 30`
- **Reports:** `main.py --report` (outcome hit-rates plus actionable/control and
  market-alignment cohorts) · `main.py --score` (paper scoreboard) ·
  `main.py --score --json` (structured paper scoreboard) ·
  `main.py --score --cohorts` (state cohort scoreboard) · `main.py --status`
  (scan/listener health) · `main.py --refresh-paper` (close matured paper trades
  without running an alerting scan) · `main.py --event-fade-report` (score local
  event-fade fixtures, alert-only/no sends) · `main.py --event-discovery-report`
  (fixture event radar with optional exchange-announcement, structured calendar,
  unlock, news/proxy-narrative, opt-in live Binance/Bybit/CryptoPanic/GDELT/RSS/Polymarket, external catalyst,
  Coinalyze-style derivatives with opt-in live Coinalyze enrichment,
  supply/on-chain enrichment, and clean CoinGecko
  universe fixtures or opt-in live CoinGecko universe resolver enrichment,
  research-only/no writes) · `main.py --event-alert-report` (rank discovery-fed
  research alert candidates as store-only/radar/watchlist/high-priority/
  triggered-fade; not trade signals, no paper trades, no normal RSI routing;
  optional Telegram digest requires explicit `--event-alert-send` plus
  `RSI_EVENT_ALERTS_ENABLED=1`; `--with-llm` runs LLM relationship analysis and
  only applies tier adjustments when `RSI_EVENT_LLM_MODE=advisory`) ·
  `main.py --event-llm-shadow-report`
  (research-only shadow relationship analysis for event candidates; fixture by
  default, optional OpenAI only when explicitly enabled; no sends, no normal RSI
  routing, no paper trades, no live DB writes) · `main.py
  --event-llm-extract-report` (research-only shadow raw-event extraction for
  catalysts, asset mentions, source-noise terms, and date hints; extracted
  assets are proposals until resolver validation) · `make event-llm-eval`
  (offline golden eval for the LLM analyzer; fails on expected role/action
  drift or quote-validation regressions) · `make event-llm-extract-eval`
  (offline golden eval for the LLM raw-event extractor; fails on catalyst/asset/
  source-noise drift or quote-validation regressions) ·
  `main.py --event-alpha-radar-report` / `make event-alpha-no-key-report`
  (research-only Event Alpha Radar view with opt-in market enrichment and
  market-anomaly rows; Decision Model v2 may surface a catalyst-unknown anomaly
  as actionable research only after strict identity, freshness, liquidity,
  spread, turnover, manipulation, dedupe, and safety gates pass) ·
  `main.py --event-alpha-cycle` / `make event-alpha-cycle`
  / `make event-alpha-cycle-llm` / `make event-alpha-cycle-send` (one unified
  research-only Event Alpha cycle: discovery/anomaly inputs, optional
  quote-checked LLM extraction hints rerun through deterministic
  resolver/classifier validation, optional LLM relationship metadata, alert
  ranking, watchlist refresh, and local router summary; send still requires
  explicit alert enablement and remains a research digest) ·
  `main.py --event-watchlist-refresh` /
  `main.py --event-watchlist-report` and `make event-watchlist-refresh` /
  `make event-watchlist-report` (append/read research-only Event Alpha Radar
  watchlist state; duplicate rows are persisted but only meaningful state
  escalations are alertable metadata) · `main.py --event-alpha-router-report` /
  `make event-alpha-router-report` (route latest watchlist state into
  artifact-only local research output; no sends, paper trades, live DB writes,
  normal RSI routing, or execution) · `main.py --event-feedback-mark` /
  `main.py --event-feedback-report` (append/read lightweight Event Alpha
  feedback labels such as useful/junk/watch/missed as research JSONL artifacts
  only) · `main.py --event-alpha-alerts-report` /
  `main.py --event-alpha-fill-outcomes` and `make event-alpha-alerts-report` /
  `make event-alpha-fill-outcomes` (read/write Event Alpha alert snapshot
  artifacts and fill 1h/4h/24h/72h/7d plus MFE/MAE outcomes from local OHLCV
  fixtures; no live DB/paper/trading writes) · `make event-alpha-eval` (offline Event Alpha route/feedback golden
  eval) · `main.py --event-incidents-report` / `make event-incidents-report`
  (profile-scoped canonical incident rows linking raw source ids/URLs/domains,
  claim history, cause status, hypotheses, watchlist rows, asset roles, market
  reaction vs causal mechanism, and incident confidence; research-only) ·
  `make event-alert-no-key-report` /
  `make event-alert-no-key-llm-report` / `make event-alert-no-key-send`
  (no-key public RSS/GDELT/Polymarket event-alert research surfaces; send still
  requires explicit alert enablement) · `main.py --event-discovery-refresh` (fetch
  configured event-discovery sources and append research-only JSONL cache
  artifacts under `RSI_EVENT_DISCOVERY_CACHE_DIR`; no live DB writes; use
  `make event-discovery-refresh-configured` when you want the Makefile to avoid
  injecting fixture paths) · `main.py --event-discovery-status` (redacted
  source/enrichment readiness report; use before configured-source cycles to
  catch missing provider flags/keys without printing secrets) ·
  `main.py --event-discovery-runs` (recent cache-refresh diagnostics from
  `discovery_runs.jsonl`; use after configured-source cycles to inspect
  zero-row/rate-limit/no-candidate warnings) ·
  `make event-discovery-refresh-public-rss` / `make
  event-fade-public-rss-review-cycle` (opt-in no-key public RSS source bundle
  with a 30-day lookback, targeted proxy-narrative search feed, and optional
  live CoinGecko universe enrichment; research cache/review artifacts only) ·
  `make event-discovery-refresh-gdelt` / `make
  event-fade-gdelt-review-cycle` (opt-in no-key GDELT Article List source with
  configurable proxy-narrative query and optional live CoinGecko universe
  enrichment; research cache/review artifacts only) ·
  `make event-discovery-refresh-polymarket` / `make
  event-fade-polymarket-review-cycle` (opt-in no-key Polymarket Gamma dated
  catalyst source with optional live CoinGecko universe enrichment; research
  cache/review artifacts only) · `make event-fade-no-key-review-cycle` (runs
  public RSS, GDELT, and Polymarket refreshes into the same cache, then writes
  one mixed-source review bundle) ·
  `main.py --event-discovery-binance-listen` (listen to Binance's signed CMS
  WebSocket for the configured window and append raw research cache evidence
  only; no live DB writes) ·
  `main.py --event-fade-auto-report` (grouped
  discovery-fed event-fade sections: watchlist/blowoff/event-passed/armed/
  triggered/rejected/ambiguous, research-only/no writes) ·
  `main.py --event-fade-export-sample PATH` (JSONL/CSV validation-sample export
  from discovery fixtures, with source evidence, features, and blank human/outcome
  fields; research-only/no writes except the requested artifact) ·
  `main.py --event-fade-export-cache-sample PATH` (JSONL/CSV validation-sample
  export from latest cached candidate snapshots under `RSI_EVENT_DISCOVERY_CACHE_DIR`;
  research-only/no writes except the requested artifact) ·
  `main.py --event-fade-review-sample PATH` (read a labeled JSONL/CSV sample and
  print review metrics/cohorts, concrete next-sample work, and promotion
  blockers; research-only/no writes) ·
  `main.py --event-fade-labeling-queue PATH` (prioritize unlabeled rows, missing
  review status/labels, and triggered rows missing required outcomes;
  research-only/no writes) ·
  `main.py --event-fade-review-packet SAMPLE OUT` (write a Markdown packet with
  prioritized rows, source evidence, classifier rationale, signal/outcome
  fields, and human review fields; writes only `OUT`) ·
  `main.py --event-fade-export-review-template SAMPLE OUT` (write compact
  editable review sidecar rows; writes only `OUT`) ·
  `main.py --event-fade-check-review-template SAMPLE TEMPLATE` (dry-check an
  edited sidecar for changed evidence, missing labels/provenance/outcomes, and
  weak valid-proxy event-time evidence; no writes) ·
  `main.py --event-fade-apply-review-template SAMPLE TEMPLATE OUT` (copy
  sidecar human review status/labels/outcomes back into a validation sample and
  print the resulting review report/next work; writes only `OUT`) ·
  `main.py --event-fade-review-bundle SAMPLE OUT_DIR` (write a local manual
  review workspace with copied/optionally prior-review-merged sample, optional
  bundle-local price fixture, optional outcome-filled sample, queue, packet,
  priority sidecar, balanced proxy/control sidecar, review report, manifest, and
  README; writes only under `OUT_DIR`) ·
  `main.py --event-fade-cache-review-bundle OUT_DIR` (same review workspace,
  sourced from latest cached candidate snapshots under
  `RSI_EVENT_DISCOVERY_CACHE_DIR`; writes only under `OUT_DIR`) ·
  `main.py --event-fade-merge-sample FRESH REVIEWED OUT` (copy prior human
  review status/labels/outcomes into a fresh validation export; writes only `OUT`) ·
  `main.py --event-fade-export-outcome-prices SAMPLE OUT` (build a local OHLCV
  price fixture for `SHORT_TRIGGERED` sample rows, optionally from fixture
  klines; `--event-fade-price-interval 1d|1h`, default `1d`; writes only `OUT`) ·
  `main.py --event-fade-fill-outcomes SAMPLE PRICES OUT` (fill
  trigger-time and event-time-baseline `SHORT_TRIGGERED` validation outcome
  fields from local OHLCV fixtures; writes only `OUT`) ·
  bundle wrappers for the human-review handoff:
  `EVENT_FADE_REVIEW_BUNDLE_DIR=/path/to/bundle make event-fade-check-review-bundle`,
  `make event-fade-apply-review-bundle`,
  `make event-fade-review-applied-bundle`, and
  `make event-fade-fill-review-bundle-outcomes` (same research-only behavior,
  using the bundle's balanced sidecar/applied sample/outcome fixture) ·
  `main.py --universe-audit` (latest hygiene audit)
- **DB backup:** `main.py --backup-db` or `make backup-db` (SQLite online backup
  API + integrity check + retention); `main.py --verify-restore` restore-checks
  the newest retained backup. Retained backup `.db` files are immutable,
  standalone snapshots: verification must use read-only immutable SQLite URIs,
  refuse a non-empty backup WAL, and never create `-wal`/`-shm` sidecars.
  Retention removes sidecars paired with pruned snapshots, and `main.py --status`
  reports any sidecar or interrupted-temp debris instead of hiding it.
- **Ops maintenance:** `make status` shows scan, backup, and log health;
  `make maintenance` runs backup + restore drill + log rotation; `make rotate-logs`
  copy-truncates oversized logs; `make install-maintenance-agent` installs the
  daily maintenance LaunchAgent; `make launchd-status` inspects scan/listener/
  maintenance agents; `make restart-listener` restarts the always-on bot listener.
- **Offline dev smoke:** `make dry-run-fixture` runs a small dry scan from
  checked-in CoinGecko fixtures (`fixtures/coingecko_smoke`) without network.
- **Universe hygiene refresh:** `make refresh-universe-audit` fetches only the
  CoinGecko market list, applies shared hygiene filters, persists the audit, and
  prints it without running RSI analysis or sending alerts.
- **Backtest (research):**
  `python -m crypto_rsi_scanner.backtest --top-n 80 --days 1825`
  flags: `--pit` (point-in-time universe via CoinGecko mcap, 365d on demo key) ·
  `--pit-volume` (**preferred for full-cycle research**: point-in-time top-N by
  trailing 30d dollar volume over the whole Binance USDT pool — 5y, free,
  cached) · `--slice <setup>`
  (vol/momentum slice) · `--compare-triggers` (entry-trigger A/B; supports the
  default Binance path and `--pit-volume`) ·
  `--state-slices` (shadow state-conditioned edge table) ·
  `--pit-cache-dir backtest_cache` / `--refresh-pit-cache` (reuse/refetch
  CoinGecko PIT histories) ·
  `--export-priors registry_priors.json` (write reviewable registry calibration) ·
  `--fixture-dir fixtures/backtest_smoke` (offline Binance-path smoke) ·
  `--costs` / `--fee-bps` / `--slippage-bps` / `--max-trades-per-day`
  (cost-aware research) · `--walk-forward` (chronological setup and
  setup×BTC-market stability) ·
  `--min-signals N` (fail if a smoke run produces too few graded observations)
- **Deploy:** the scan agent (`com.nasrenkaraf.rsiscanner`) auto-loads new code on
  its next run (03:10 MSK). The **listener must be restarted** to pick up code:
  `launchctl kickstart -k "gui/$(id -u)/com.nasrenkaraf.rsibot"`.
  The project lives in `~/crypto-rsi-scanner` (NOT `~/Documents`, which is
  TCC-protected — launchd can't exec there).

---

## Architecture (`crypto_rsi_scanner/`)

| module | responsibility |
|---|---|
| `config.py` | env/`.env` config + all tunables; `redact_token` |
| `client.py` | async CoinGecko client (rate-limited, retries) |
| `universe.py` | CoinGecko universe hygiene filters/audit shared by live scan/backtest |
| `state_features.py` | pure market-state features: volatility, breadth, relative strength, beta, liquidity, risk buckets |
| `event_fade.py` | pure alert-only sell-the-news event-fade research sleeve; no storage, alerts, paper trades, or execution |
| `event_core/` | immutable shared event dataclasses and deterministic research-clock helpers used outside Event Alpha too |
| `event_alpha/radar/discovery/` | research-only event radar orchestration: normalize → dedupe → resolve → classify → optional fade scoring, grouped auto reports, and validation sample exports |
| `event_alpha/artifacts/alerts.py` | pure research-alert ranking/tiering for discovery candidates; no labels, paper trades, normal RSI routing, or execution |
| `event_alpha/radar/playbooks.py` | deterministic Event Alpha Radar playbook scoring; labels candidates as proxy fade/attention, listings, unlocks, airdrops/TGEs, fan/sports, political memes, RWA/AI IPO proxies, security/regulatory shocks, infrastructure, market anomalies, source-noise, or ambiguous controls without creating trades or triggers |
| `event_alpha/radar/llm/` / `llm_providers/` | research-only LLM relationship analysis and raw-event extraction; validates source quotes and keeps extracted assets as deterministic resolver hints only |
| `event_alpha/radar/market_enrichment.py` / `event_alpha/radar/anomaly_scanner.py` | research-only Event Alpha Radar market evidence and anomaly discovery; catalyst search enriches confidence but is not a universal prerequisite for v2 research actionability |
| `event_alpha/radar/decision_model.py` / `decision_models.py` | pure Crypto Radar Decision Model v2 scoring and value contracts; separates actionability, evidence confidence, risk, thesis origin, bias, catalyst, timing, and tradability from legacy opportunity routes |
| `event_alpha/radar/rsi_technical_context.py` | pure/read-only adapter from explicitly supplied existing RSI artifacts into bounded Decision v2 context; exact symbol+coin-id match only, no RSI writes/alerts/paper/backtest/provider/send side effects |
| `event_alpha/radar/calendar/` | unified fixture-first macro/crypto scheduled-event model and read-only loaders; reminder windows are display metadata only |
| `event_alpha/dashboard/` | local GET/HEAD-only server-rendered dashboard over one exact operator run/revision; no provider calls, sends, or writes |
| `event_alpha/radar/integrated/pipeline_parts/merge.py` | integrated-family context and final candidate schema-field assembly |
| `event_alpha/radar/integrated/pipeline_parts/merge_policy.py` | pure source normalization, identity selection, opportunity scoring, market/derivatives policy, and merge summaries; exported through the integrated API compatibility wrapper |
| `event_alpha/radar/graph.py` | research-only catalyst clustering by external asset/event type/event-date bucket; used for watchlist identity while preserving rejected/noise asset links |
| `event_alpha/radar/watchlist/` | research-only Event Alpha Radar state cache; tracks raw/radar/watchlist/high-priority/event-passed/armed/triggered/terminal transitions and duplicate suppression without routing alerts or writing live storage |
| `event_alpha/radar/incidents/` | profile-scoped canonical Event Alpha incident JSONL artifacts linking raw sources, claim history, hypotheses, watchlist rows, asset roles, and market/cause context |
| `event_alpha/notifications/router.py` | artifact-only Event Alpha Radar route decisions from watchlist state; local research output only, no sends/trades/live writes |
| `event_alpha/radar/core/` | profile-scoped canonical CoreOpportunity JSONL artifacts; one post-refresh, quality-gated operator row per visible opportunity for daily briefs, near-miss reports, cards, audits, and doctor checks |
| `event_alpha/artifacts/alert_store.py` | research-only Event Alpha alert snapshot/outcome JSONL artifacts; reports cohorts and fills local OHLCV outcomes without live DB, paper, or execution writes |
| `event_alpha/outcomes/feedback.py` / `event_alpha/outcomes/eval.py` | lightweight Event Alpha feedback JSONL artifacts and offline route/feedback golden evals; review metadata only |
| `event_alpha/artifacts/cache.py` | research-only JSONL observational cache for point-in-time event-discovery evidence; no live SQLite/signal/paper writes |
| `event_alpha/radar/validation/` | research-only validation-sample loader/reviewer/labeling-queue/merger for human labels, outcome metrics, and promotion blockers |
| `event_alpha/radar/resolver.py` / `event_alpha/radar/classification.py` | conservative asset matching and deterministic proxy/direct classification |
| `event_providers/` | research event provider interfaces, manual JSON event fixtures, cleaned CoinGecko universe fixture provider plus opt-in live CoinGecko universe resolver enrichment, exchange announcement parsers with captured Binance CMS WebSocket payload support plus opt-in live Binance WebSocket and Bybit HTTP fetches, structured calendar/unlock parsers, CryptoPanic/GDELT/project-blog news parsers with opt-in live CryptoPanic posts, GDELT Article List, and project-blog RSS/Atom fetches, and external IPO/sports/prediction-market catalyst parsers with opt-in live Polymarket Gamma events |
| `derivatives_providers/` | derivatives enrichment adapters for event discovery, starting with Coinalyze-style OI/funding/crowding snapshots and opt-in live Coinalyze REST enrichment |
| `supply_providers/` | fixture-backed supply/on-chain enrichment adapters for event discovery, starting with Tokenomist/Etherscan/Arkham/Dune-style snapshots; no live supply provider enabled yet |
| `signal_registry.py` | canonical setup registry: setup intent, expected direction, market eligibility, edge priors |
| `indicators.py` | **PURE** functions: RSI, regime, setup taxonomy, market gating, conviction. Unit-tested — keep pure, add a test for new logic |
| `scanner.py` | orchestration: scan → analyze → build message → route notifications; CLI |
| `storage.py` | SQLite. **Additive migrations only** (`_migrate`); one-time data migrations gated by a `meta` flag |
| `backups.py` | safe SQLite online backups, restore drills, integrity check, retention |
| `ops.py` | local log rotation and launchd status/restart/maintenance-agent helpers |
| `outcomes.py` | forward-return grading vs each setup's *expected direction* |
| `formatting.py` | channel rendering (Telegram HTML cards, plain text) |
| `notifications.py` | send to Telegram/Discord/email |
| `alert_smoke.py` | offline representative alert-render smoke test |
| `status_report.py` | shared CLI/bot operational health report |
| `telegram.py` | bot listener + commands (`/top /detail /stats /score`) + subscriber mgmt |
| `macro.py` / `heartbeat.py` | digest market-context header / dead-man's-switch |
| `paper.py` | paper-trade scoreboard (virtual P&L) |
| `backtest.py` | offline research; **reuses the pure functions** so it matches live logic |
| `tests/test_indicators.py` | every test (pure, no network) |
| `project_health/` | permanent static architecture/project-health checks, including baseline, size gates, class ownership, naming cleanup, completion, and final architecture reports |

### Event Alpha v1 package boundaries

New Event Alpha implementation code should land in package homes, not in
top-level `event_*.py` shims:

| package | responsibility |
|---|---|
| `event_alpha/providers/` | provider activation, readiness, preflight/rehearsal, provider health, source registry, source packs |
| `event_alpha/radar/` | integrated radar, market state/reaction/anomaly, evidence acquisition, CoreOpportunity rows, source coverage, verdicts, impact hypotheses, incidents |
| `event_alpha/artifacts/` | artifact context, paths, schema v1, run ledger, retention, locks |
| `event_alpha/notifications/` | previews, no-send delivery, send-readiness, go/no-go, inbox, SLO, pack, pause, final check, sender, formatting |
| `event_alpha/outcomes/` | outcomes, calibration, feedback, burn-in, quality, priors, policy simulation |
| `event_alpha/doctor/` | schema-first doctor phases, check registry, plugin checks, reports |
| `event_alpha/namespace/` | namespace status and lifecycle reporting |
| `event_alpha/operations/daily_burn_in.py` | stateful daily no-send burn-in execution, partial/final artifacts, candidate accounting, safety counters, and report rendering |
| `event_alpha/operations/daily_burn_in_plan.py` | pure burn-in step/command planning; keep send-enabling commands out and preserve the orchestrator's public re-exports |
| `cli/` | parser, dispatch, and command-group modules |

No old flat Event Alpha public compatibility shims remain. Deleted old imports
are tombstoned and allowed to fail; their manifest is
`research/EVENT_ALPHA_DELETED_SHIMS.md/json`. New code should import the new
package path, docs should show canonical package paths, and any future public
compatibility bridge must be explicitly documented in
`research/PUBLIC_COMPATIBILITY_ENTRYPOINTS.md/json` and mirrored in
`research/EVENT_ALPHA_PUBLIC_COMPATIBILITY_ENTRYPOINTS.md/json` before it is
retained. `crypto_rsi_scanner.event_alpha.shims` is the tombstone registry, and
artifact doctor warns if a deleted shim file is reintroduced. Run
`make event-alpha-shim-report` to audit shim source and
`make event-alpha-old-import-check` to fail old flat Event Alpha imports outside
documented exceptions and `tests/event_alpha/test_no_old_event_alpha_imports.py`.
CLI parser
construction belongs in `cli/parser.py`, dispatch in `cli/dispatch.py`, and
command groups in `cli/commands_*.py`. New tests belong in
`tests/event_alpha/`, `tests/rsi/`, or `tests/cli/`; `tests/test_indicators.py`
is the compatibility umbrella runner. When splitting a large test module, keep
each extracted module below the 1,500-line warning when a cohesive boundary
allows it, use package `_api_helpers` instead of importing test callables from
the old monolith, register the module in the standalone runner, and prove the
test-name set has neither losses nor duplicates. New artifact fields require schema v1
updates, and new doctor checks require check-registry schema dependencies.
Every new Event Alpha namespace needs lifecycle status, retention policy, and
explicit `safe_for_send_readiness`. Preserve
research-only/no-trading/no-paper/no-send guards in all Event Alpha package
work.

---

## Conventions

- `signal_registry.py` is the source of truth for setup intent, expected
  direction, market eligibility, and backtested conviction priors. It can load
  explicit JSON calibration via `RSI_REGISTRY_PRIORS`; absent that, checked-in
  defaults remain live.
- `universe.py` is the source of truth for CoinGecko market hygiene. Live scans
  and backtest top-N selection must use the same filters. Live scans persist the
  latest audit to SQLite meta and `universe_hygiene_latest.json`; inspect it via
  `main.py --universe-audit`, or refresh only the audit with
  `main.py --refresh-universe-audit`. The 2026-06-09 audit tightened
  stable/pegged detection for fiat, gold, and yield products that were slipping
  into kept candidates. The 2026-07-10 audit added exact-symbol EURC exclusion;
  prefer exact observed fiat-pegged identities over broad currency-name matching
  that could remove legitimate crypto assets.
- `state_features.py` is pure and shadow-first. State features may be tested,
  stored, and reported before they are allowed to affect conviction, routing, or
  gating. The live scanner attaches `state_json` only after the existing decision
  fields are already computed.
- Paper outcomes with extreme returns remain part of the canonical scoreboard.
  Surface them through the robust-mean and outlier-review diagnostics in
  `paper.py` / `paper_risk_research.py`; do not delete, cap, winsorize, or
  auto-apply thresholds retrospectively without a separate evidence-backed
  decision.
- `event_fade.py` is a separate research sleeve for dated proxy-catalyst
  sell-the-news fades. It must stay alert-only and inert by default: no storage,
  notification routing, paper trading, or execution without explicit
  backtest/manual-review evidence and a new decision. Proxy eligibility is a
  hard gate: direct-beneficiary or non-proxy events must remain `NO_TRADE` even
  if pump, crowding, RSI, and post-event failure scores are high.
- Event discovery is radar-first and fixture-backed by default. It may
  normalize, resolve, classify, dedupe, print local reports, and export JSONL/CSV
  validation-sample artifacts, and it may load local exchange announcement,
  structured calendar, unlock, news/proxy-narrative, external catalyst,
  derivatives, supply/on-chain, and clean CoinGecko market fixtures through the
  shared `universe.py` hygiene filters. Opt-in live Bybit announcement,
  CryptoPanic posts, GDELT Article List, project-blog RSS/Atom, and Coinalyze
  derivatives fetching are allowed only for local research
  reports/exports/cache refreshes, not live routing. Event discovery must not
  write live signal/outcome/paper tables or route notifications.
  Ticker-only/ambiguous asset matches must stay below trigger confidence.
  The default manual alias file is `event_discovery_aliases.json`; fixture
  aliases in `fixtures/event_discovery/asset_aliases.json` are for fixture
  targets/tests only and must not pollute real-source review cycles.
  Proxy-style news may infer lower-confidence event times only from explicit
  source-text date phrases such as "by June 20, 2026"; rows without a known or
  inferred event time may enter validation samples as `proxy_attention` review
  evidence, but they must remain `NO_TRADE` because the event-fade hard gate
  still requires a real event time. Inferred event times must keep their
  `event_time_source`/`event_time_confidence` provenance in validation exports,
  and fade-candidate confidence is capped by event-time confidence so
  lower-confidence text dates cannot silently satisfy the event-confidence gate.
  News/proxy providers may infer external assets from a conservative alias list
  plus explicit IPO/exposure/prediction-market/sports-match phrasing; this only
  improves radar/review rows and cannot bypass resolver confidence, proxy/direct
  classification, or event-fade hard gates.
  Validation review reports cohort by event-time source and block promotion if
  reviewed `SHORT_TRIGGERED` rows have event-time confidence below the review
  threshold.
  Asset role classification is part of the proxy gate: only `proxy_instrument`
  and `proxy_venue` rows remain proxy candidates, but `proxy_venue` is
  watchlist/review-only by default and cannot trigger unless
  `RSI_EVENT_FADE_ALLOW_PROXY_VENUE_TRIGGER=1`. Low classifier confidence and
  low event-time confidence explicitly force `NO_TRADE` with review-only reason
  codes before event-fade signal emission. `mentioned_asset`, `infrastructure`,
  and `ticker_word_collision` rows become `proxy_context` controls.
  Dedupe runs exact matching first, then a canonical event-type/external-asset/
  event-date/catalyst-term pass so obvious headline variants merge while all
  raw source timing/evidence is preserved. Fade-candidate enrichment chooses the
  richest point-in-time-safe market/derivatives/supply/RSI/technical payload
  across the deduped raw sources instead of blindly using the first raw event.
  The resolver also guards common identity words observed in public feeds
  (`cash`, `real`, `just`, `humanity`) from becoming high-confidence matches.
  Provider enrichment is evidence, not eligibility; raw reviewed fixture
  evidence takes precedence over provider rows.
- Event LLM analysis is research-only. In `shadow` mode it may build evidence
  packets from discovery/event-alert candidates, call a fixture or explicitly
  enabled OpenAI provider, validate structured output, verify source quotes,
  print local comparison reports, and optionally write a local JSON cache
  artifact. In `advisory` mode, when explicitly requested with `--with-llm`, it
  may adjust discovery-fed research-alert tiers for false-positive quality
  control only. It must not change rule classifications, create
  `TRIGGERED_FADE`, alter `event_fade.py` eligibility, route normal RSI alerts,
  open paper trades, write live signal/outcome/paper tables, or imply execution.
- Event LLM raw-event extraction is research-only. In `shadow` mode it may
  extract external catalysts, crypto asset/project mentions, source-noise terms,
  and event date hints from raw provider evidence, validate structured output,
  verify source quotes, print local reports, and optionally write a local JSON
  cache artifact. The unified Event Alpha cycle may append high-confidence,
  quote-validated extraction hints to raw evidence before deterministic
  normalization/resolution so missed assets can be found. Extracted assets are
  resolver hints only; they do not create candidates, alerts, paper trades, live
  DB rows, or event-fade eligibility unless deterministic resolver/classifier
  gates validate the asset and event through the normal discovery path.
- Event Alpha Radar market enrichment, anomaly scanning, and watchlist state are
  research-only; live provider acquisition remains disabled without its existing
  explicit authorization. Market enrichment may fill candidate
  market snapshots from CoinGecko-style fixture/live rows, but raw reviewed
  event payloads win when both exist. The market anomaly scanner may create
  low-authority raw research events from top movers, volume/mcap spikes, or
  volume z-scores. Under Crypto Radar Decision Model v2, a fresh canonical,
  liquid, adequately traded, non-duplicate market anomaly with meaningful
  relative/structure and volume evidence may enter an explicit research route
  without a known catalyst. Unknown catalyst lowers evidence confidence, raises
  risk, and stays visible; it is not a universal hard block. Legacy opportunity
  lanes and strict alert gates remain unchanged and old artifacts are never
  silently promoted. The watchlist may append JSONL state
  rows under the research cache for `RAW_EVIDENCE`, `RADAR`, `WATCHLIST`,
  `HIGH_PRIORITY`, `EVENT_PASSED`, `ARMED`, `TRIGGERED_FADE`, `INVALIDATED`,
  and `EXPIRED`, and may mark duplicate rows as suppressed unless state
  escalates. Playbook scoring may label candidates as `proxy_fade`,
  `proxy_attention`, `direct_event`, `infrastructure_mention`,
  `market_anomaly`, `source_noise_control`, or `ambiguous_control`; only
  `proxy_fade` may preserve an already-emitted `event_fade.py`
  `SHORT_TRIGGERED` as `TRIGGERED_FADE`. The Event Alpha router may read latest
  watchlist state and produce local route decisions such as store-only,
  duplicate suppression, research digest, high-priority research, or
  triggered-fade research, but this is report metadata only. Feedback labels
  (`useful`, `late`, `manipulation_risk`, `missing_confirmation`, `junk`,
  `watch`, `missed`, `traded_elsewhere`, `ignored`) may be
  appended as JSONL review artifacts and inspected/evaluated offline, but they
  do not mutate watchlist state or alert tiers. None of these paths can create
  proxy eligibility, create `TRIGGERED_FADE`, send Telegram alerts, route normal
  RSI alerts, open paper trades, write live signal/outcome/paper tables, or
  execute orders.
- Event Alpha artifacts must stay profile/run-mode namespaced for burn-in
  safety. Profiled runs should resolve local artifacts under
  `RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR` + `RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE`
  unless a specific path override is intentionally provided. Run-ledger rows and
  alert snapshots should carry `run_id`, `profile`, `run_mode`,
  `artifact_namespace`, and relevant artifact paths. Burn-in/readiness/health
  reports should ignore `test`, `fixture`, and `replay` rows unless
  `--event-alpha-include-test-artifacts` is explicitly passed. Use
  `main.py --event-alpha-artifact-doctor` / `make event-alpha-artifact-doctor`
  to diagnose mixed namespaces, orphan snapshots, missing provider/budget rows,
  and missing snapshot writes before treating burn-in artifacts as evidence.
- Event Alpha promotion and calibrated-send readiness must use the policy-scoped
  30-day North Star operations scorecard as the authoritative contract state.
  Feedback readiness means only that feedback can be collected; operational
  no-send readiness means only that another research burn-in cycle can run.
  Neither may imply contract maturity, and a notification profile with no
  successful matching run is not day-1 ready. Keep all promotion lanes frozen
  while the authoritative scorecard reports `enough_data=false`.
- Event Alpha consolidation is compatibility-first. New Event Alpha code should
  use `crypto_rsi_scanner/event_alpha/` and `crypto_rsi_scanner/cli/`. Old flat
  Event Alpha import paths are tombstoned, not retained; any future public
  bridge needs an explicit decision and entry in
  `research/PUBLIC_COMPATIBILITY_ENTRYPOINTS.md/json`.
  Artifact doctor checks that depend on fields must
  reference `event_alpha/artifacts/schema_v1.py` first, and namespace lifecycle
  status should be inspected with `make event-alpha-namespace-lifecycle-report`
  before using a namespace for send-readiness, burn-in, or calibration.
- Live Coinalyze enrichment may auto-resolve futures symbols. When
  `RSI_EVENT_DISCOVERY_COINALYZE_LIVE=1`, explicit
  `RSI_EVENT_DISCOVERY_COINALYZE_SYMBOLS` still wins; otherwise
  `RSI_EVENT_DISCOVERY_COINALYZE_AUTO_SYMBOLS=1` may query Coinalyze
  `future-markets` and select preferred perp symbols from already-resolved
  discovery assets. This is enrichment only; it cannot create events or bypass
  the event-fade proxy/direct gate.
- Event-discovery cache writes are observational only. `main.py
  --event-discovery-refresh` may append JSONL files under
  `RSI_EVENT_DISCOVERY_CACHE_DIR` for raw events, normalized events, links,
  classifications, candidate snapshots, and run metadata. It must not write the
  live SQLite signal/outcome/paper tables, route alerts, open paper trades, or
  imply promotion. `discovery_runs.jsonl` includes redacted provider readiness
  diagnostics and refresh warnings, such as source-ready runs that collected no
  raw events or raw events that built no candidates. Inspect recent runs with
  `main.py --event-discovery-runs`. `main.py --event-discovery-binance-listen` may append raw
  Binance announcement evidence and run metadata to the same cache; it must not
  normalize into live signals, route alerts, or paper trade. Candidate snapshots
  track research-only transition timestamps (`first_seen_at`,
  `first_watchlisted_at`, `first_armed_at`, `first_triggered_at`,
  `last_seen_at`) by event/asset/relationship identity; these are validation
  evidence fields, not live state.
- Event-fade validation review is research-only. `main.py --event-fade-review-sample`
  may read labeled JSONL/CSV sample artifacts and print coverage, trigger
  precision, trigger latency, point-in-time violations, MFE/MAE, post-event
  returns, event-time short baseline comparison,
  event-type/relationship/asset-role/event-time-source/source-provider/source-origin/BTC-risk
  cohorts, diversity gates, and promotion blockers plus concrete next-sample
  work. Reviewed proxy evidence must not be dominated by one event type or one
  source provider. A row only counts as reviewed evidence when it has
  `review_status=reviewed` and a known `human_label`, and promotion remains
  blocked until reviewed rows also carry `reviewed_by` and `reviewed_at`.
  Source-timing checks use `trigger_observed_at` for reviewed `SHORT_TRIGGERED`
  rows and `event_time` for other reviewed dated rows, including direct or
  ambiguous controls. If a reviewer supplies high-confidence `human_event_time`,
  validation metrics may use it for review-only decision timing, trigger
  latency, source-timing checks, and event-time baseline outcome filling while
  preserving the original machine `event_time`. Reviewed rows with no source
  timing evidence are blocked until timing is added or the row is removed.
  The review command must not automatically promote alerts, write live storage,
  open paper trades, or imply execution.
- Event-fade validation labeling queues are artifact-only. `main.py
  --event-fade-labeling-queue` may prioritize unlabeled proxy/control rows and
  reviewed triggered rows missing required outcomes, source-timing review,
  low-confidence event-time confirmation, or explicit review status/labels. The
  queue surfaces event-time source/confidence plus source-origin/publisher
  context, and ranks higher-confidence
  explicit event times before weaker source-text dates inside the same review
  bucket, but it must not auto-label rows, modify sample files, write storage,
  route alerts, open paper trades, or imply promotion.
- Event-fade validation review packets are artifact-only. `main.py
  --event-fade-review-packet SAMPLE OUT` may write a Markdown packet with source
  URLs, source-origin/publisher context, and row evidence for manual validation
  review, but it must not auto-label rows, modify the source sample, write
  storage, route alerts, open paper trades, or imply promotion.
- Event-fade validation review templates are artifact-only. `main.py
  --event-fade-export-review-template SAMPLE OUT` may write compact editable
  sidecar rows with derived source origins, `main.py
  --event-fade-check-review-template SAMPLE TEMPLATE` may dry-check an edited
  sidecar before apply without writing anything, and `main.py
  --event-fade-apply-review-template SAMPLE TEMPLATE OUT` may copy nonblank
  human labels/notes/outcomes and human event-time confirmations from that
  sidecar into a validation-sample artifact only when the sidecar evidence
  fields still match the sample row. Human event-time confirmation fields must
  stay separate from the machine-extracted `event_time`; they are review
  evidence, not proof that the system knew the event time automatically.
  They must not infer labels, write live storage, route alerts, open paper
  trades, or imply promotion.
- Event-fade validation review bundles are artifact-only. `main.py
  --event-fade-review-bundle SAMPLE OUT_DIR` may copy the sample and write local
  review aids under `OUT_DIR`; with `--event-fade-review-bundle-prices` it may
  also fill outcome fields into a bundle-local sample copy, and with
  `--event-fade-review-bundle-export-prices` it may first export a bundle-local
  OHLCV price fixture for triggered rows using the existing research price
  export path. Makefile price export/review-bundle targets default to that
  Binance daily-kline fetch/cache path; set `EVENT_FADE_PRICE_INTERVAL=1h` for
  hourly outcome export when the sample needs intraday MFE/MAE, and set
  `EVENT_FADE_PRICE_FIXTURE_DIR=fixtures/event_discovery/outcome_klines` only
  for offline fixture smoke. With
  `--event-fade-review-bundle-reviewed` it may first merge prior reviewed
  labels/notes/outcomes that still match the fresh evidence fingerprint. It also
  writes a `manifest.json` for bundle provenance/counts/review-gate metrics/
  price-export/merge status, a priority `review_packet.md` and
  `review_template.csv`, a diversity-first gate-balanced
  `review_packet_balanced.md` and `review_template_balanced.csv` with proxy
  candidates and negative controls, reviewer helper columns including
  `source_search_url` for Google News/feed wrappers, `source_date_hint` for
  date-like source-title cues, and `source_providers` for provider diversity
  review, a `review_guide.md` with
  label taxonomy, review provenance fields, and human event-time rules, and its
  README summarizes the same coverage,
  diversity, timing, and promotion-readiness gates. Empty bundles must warn that
  no validation rows were produced and point back to provider status/source
  refresh, rather than looking like completed review work. It must not infer
  labels, write live storage, route
  alerts, open paper trades, or imply promotion.
- Event-fade validation merges are artifact-only. `main.py --event-fade-merge-sample`
  may copy nonblank human labels/notes/outcomes from a previously reviewed
  JSONL/CSV sample into a fresh export by event/asset/relationship identity only
  when the validation evidence fingerprint is unchanged. Evidence-changed rows
  must remain unreviewed so they return to the labeling queue; merge/apply
  commands should report the affected row and changed evidence fields. The
  command must only write the requested output artifact.
- `indicators.py` stays pure and tested. New signal logic → add a test.
- Alert/formatting changes must keep `make smoke-alerts` passing; it checks
  representative Telegram/plain-text renders without sending anything.
- Notification bookkeeping is delivery-sensitive: only mark instant cooldowns or
  digest timestamps after at least one channel succeeds.
- Run the risk-appropriate verification gate before claiming implementation work
  is complete. Full `make verify` is still required for release/risky/shared
  changes and periodic full sweeps, but ordinary small prompts should use
  targeted tests plus relevant smokes. If you skip full `make verify`, say
  exactly why.
- Verification and runtime commands must not rewrite tracked contracts or
  reports incidentally. `make event-alpha-radar-north-star` and
  `make event-alpha-burn-in-contract` are the explicit Event Alpha contract
  authoring paths; daily burn-in uses `--check-burn-in-contract`. Test real
  subprocess behavior against temporary/fake repository roots and assert
  tracked or sentinel bytes remain unchanged.
- Storage: additive `ALTER` in `_migrate`; bump a `meta` flag for one-time data
  migrations so they run exactly once.
- External calls **fail soft** (log + degrade; never crash the scan).
- Never print/log configured credentials or recipient identifiers — route
  exception and provider text through `config.redact_token`. Runtime logs,
  SQLite files, and backups must remain owner-only (`0600`; directories `0700`).
- Cross-platform path tests must check path semantics or the actual temporary
  root (`Path.is_absolute`, `has_operator_absolute_path`, `str(tmp_path)`) rather
  than assuming Linux `/tmp/` or macOS `/var/` prefixes.
- **Backtest any signal-logic change before shipping it live.** This project has
  burned us with regime-skewed conclusions (see below) — validate first.
- Don't trust short-window or <~1-week live hit-rates; they're one regime.

---

## Strategy state & hard-won findings (context you need)

- **Setups are graded against their own expected direction** (not blanket
  mean-reversion). `setup_for(flag, regime)` → `(setup_type, expected_dir)`.
- **Backtest (5y, Binance klines) verdict: edge is REGIME-CONDITIONAL.**
  - `mean_reversion` → works in CHOP/range; negative in bull.
  - `dip_buy` / `trend_continuation` → work in BULL.
  - `breakdown_risk` (oversold-in-downtrend) → **no edge in any regime.** Shown
    "context only" in alerts; never goes loud.
  - The aggregate edge is **thin** — the live value is the *gating* (firing each
    setup only in its favorable regime), not the raw RSI signal.
- **Market-regime gating is LIVE:** `market_alignment(setup, BTC_regime)` is
  defined in `signal_registry.py` and demotes adverse setups out of INSTANT.
- **Conviction now starts from measured edge:** `signal_registry.py` seeds
  conviction from setup×market-regime priors; `backtest.py --export-priors` can
  generate reviewable numeric overrides, and `RSI_REGISTRY_PRIORS` opts live into
  that artifact. Severity/confluence and matured live outcomes nudge around that
  baseline. First backtest validation landed 2026-06-10: on the 5y volume-PIT
  run conviction is monotonic with edge (low −3 / med +3 / high +9, n=307);
  live paper-scoreboard validation still pending.
- **Paper scoreboard** (`--score`, `/score`) is accruing live; compares an
  "actionable (gated)" book vs a "control (gated-out)" book.
  Use `--score --cohorts` once paper trades close to inspect setup, conviction,
  market-alignment, and stored state-bucket cohorts.
- **Live outcome report** (`--report`) now includes actionable/control and
  setup-market-alignment cohorts. The scanner also fetches extra recent histories
  for pending outcomes/paper trades when a signaled coin leaves today's clean
  top-N universe.
- **State-slice research:** `research/STATE_SLICE_BACKTEST_2026-06-09.md`
  contains the 4-year Binance current-top review; `research/PIT_STATE_SLICE_CONFIRMATION_2026-06-09.md`
  contains the cached 365d PIT review. The PIT run was bear-only, so it does not
  confirm bull/chop state rules.
- **Registry-prior PIT review:** `research/PIT_REGISTRY_PRIORS_REVIEW_2026-06-09.md`
  and `research/registry_priors_pit_2026-06-09.json` capture the cached 365d PIT
  export. It is review-only, not live-loaded: the run was BEAR-only and moved
  broad neutral priors from narrow bear evidence.
- **PIT data depth: SOLVED (2026-06-10)** by `--pit-volume` — membership by
  trailing 30d dollar-volume rank over the Binance USDT pool gives 5y
  point-in-time coverage with no Pro key. `research/VOLUME_PIT_BACKTEST_2026-06-10.md`
  is the first full-cycle survivorship-reduced run (368 coins, 21,334 obs,
  BULL/CHOP/BEAR all covered): the gating map held (mean_reversion CHOP +10
  n=800; breakdown_risk no edge anywhere). Its prior export
  (`research/registry_priors_volpit_2026-06-10.json`) supersedes the bear-only
  one for review; still NOT live-loaded. `research/VOLUME_PIT_WALK_FORWARD_2026-06-17.md`
  confirms the CHOP mean_reversion edge was positive in every eligible
  chronological test fold on the same top-100/1825d volume-PIT configuration
  (+2, +25, +26 edge). `research/PIT_DATA_OPTIONS_2026-06-09.md` is historical
  context. Residual caveats: delisted pairs absent, single venue,
  volume-rank ≠ live mcap universe.
- **Confirmation entry trigger** was A/B'd and **rejected** (no improvement) — do
  not re-add without new evidence.
- **Event fade research sleeve (2026-06-16):** VELVET/SpaceX-style proxy-event
  blowoffs are modeled separately in `event_fade.py`. The thesis is dated
  catalyst + proxy purity + pre-event pump + crowding/liquidity/supply pressure
  + post-event failure. The proxy/direct-beneficiary check is a hard gate, not a
  score nudge. It is not part of the RSI setup registry, does not trade, and
  should not affect live routing until validated on an event sample.
- **Event discovery Phase 1-10 (2026-06-16):** Local fixture radar exists via
  `main.py --event-discovery-report`. It finds raw events, resolves assets with
  aliases, classifies proxy/direct/ambiguous relationships, rejects ticker
  collisions, can merge an optional cleaned CoinGecko market fixture from
  `RSI_EVENT_DISCOVERY_UNIVERSE_PATH`, can opt into live CoinGecko universe
  enrichment with `RSI_EVENT_DISCOVERY_UNIVERSE_LIVE=1`, can parse local Binance/Bybit
  announcement fixtures as direct listing/perp events, can parse captured
  Binance CMS WebSocket `com_announcement_en` DATA payloads, can optionally
  listen briefly to Binance's signed CMS WebSocket when
  `RSI_EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE=1` and API credentials are set,
  can cache raw Binance WebSocket evidence via
  `main.py --event-discovery-binance-listen`,
  can optionally fetch live Bybit `new_crypto` announcements when
  `RSI_EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE=1`, can parse local
  CoinMarketCal-style calendar fixtures and Tokenomist-style unlock fixtures as
  direct events, can parse local CryptoPanic/GDELT/project-blog fixtures as
  proxy/direct/ambiguous news evidence, can optionally fetch live CryptoPanic
  posts when `RSI_EVENT_DISCOVERY_CRYPTOPANIC_LIVE=1` and an API token is set,
  can optionally fetch live GDELT Article List JSON when
  `RSI_EVENT_DISCOVERY_GDELT_LIVE=1`, can optionally fetch live
  RSS/Atom feeds from explicit `RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS` or
  newline URL files when `RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE=1`, can
  infer common external assets such as SpaceX/OpenAI and conservative
  lower-confidence source-text dates in news text, can export event-time source
  provenance for review/merge evidence, can preserve no-event-time proxy-style
  articles as `proxy_attention` review rows that remain `NO_TRADE`,
  can classify linked-asset roles so background mentions,
  infrastructure chains, and ticker-word collisions become `proxy_context`
  controls and proxy venues stay review-only by default, can explicitly force
  `NO_TRADE` on low classifier confidence or low event-time confidence, can
  canonically merge obvious duplicate catalyst headlines while preserving raw
  source evidence, can merge enrichment payloads across deduped raw sources,
  can parse local external IPO,
  sports, and prediction-market catalyst fixtures as radar evidence, can optionally
  fetch no-key live Polymarket Gamma dated catalyst events when
  `RSI_EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE=1`, can attach local
  Coinalyze-style OI/funding/crowding snapshots from
  `RSI_EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH`, can optionally fetch live
  Coinalyze derivatives snapshots from explicit
  `RSI_EVENT_DISCOVERY_COINALYZE_SYMBOLS` or auto-resolved Coinalyze
  `future-markets` symbols from already-resolved discovery assets when
  `RSI_EVENT_DISCOVERY_COINALYZE_LIVE=1`, can attach local
  Tokenomist/Etherscan/Arkham/Dune-style supply and on-chain snapshots from the
  `RSI_EVENT_DISCOVERY_*_SUPPLY_PATH` env vars, and feeds structured candidates
  through `event_fade.py` for flat radar, research-alert ranking, and grouped auto reports.
  `main.py --event-alert-report` ranks discovery candidates into store-only,
  radar digest, watchlist, high-priority watch, or triggered-fade tiers without
  requiring human labels or review status; optional Telegram research digests are
  disabled by default, separate from normal RSI alerts, and explicitly labeled
  "not a trade signal." The grouped
  report is `main.py --event-fade-auto-report` and prints event radar, proxy
  watchlist, blowoff risk, event-passed, armed, triggered, rejected/no-trade,
  and ambiguous sections with evidence/warnings. The validation-sample export is
  `main.py --event-fade-export-sample PATH` and writes JSONL/CSV rows with raw
  source evidence, point-in-time timestamps, link/classifier evidence, fade
  features, asset-role metadata, missing-data fields, raw/min/max source
  timestamps for leakage review, and blank human-review/outcome columns.
  `main.py --event-fade-review-sample PATH` reads labeled sample artifacts and
  reports sample coverage, reviewed trigger count, trigger precision,
  false-positive rate, trigger latency, point-in-time evidence violations,
  post-decision source evidence,
  MFE/MAE, post-event returns, event-time short baseline comparison,
  event-type/relationship/asset-role/event-time-source/BTC-risk cohorts, and
  blockers such as too few reviewed proxy/control/trigger cases, too-narrow
  event/BTC-risk diversity, low-confidence trigger event times, or weak
  edge-quality metrics. It also prints concrete next-sample work so the reviewer
  knows which cases, labels, statuses, source-time confirmations, or outcomes to
  add next.
  `main.py --event-fade-labeling-queue PATH`
  prioritizes the next rows to label, rows missing explicit review status, and
  triggered rows missing required outcome fields.
  `main.py --event-fade-review-packet SAMPLE OUT` writes a
  Markdown packet for the same prioritized rows with source URLs, raw titles,
  classifier evidence, signal/risk fields, trigger/event-time outcomes, and the
  human fields to fill. `main.py --event-fade-export-review-template SAMPLE OUT`
  writes a compact editable sidecar for those rows,
  `main.py --event-fade-check-review-template SAMPLE TEMPLATE` dry-checks the
  edited sidecar, and
  `main.py --event-fade-apply-review-template SAMPLE TEMPLATE OUT` applies
  nonblank sidecar review status/labels/outcomes back into a requested sample
  artifact, then prints the resulting review report and next-sample work.
  `main.py --event-fade-review-bundle SAMPLE OUT_DIR` writes the sample copy,
  queue, packet, template, review report, manifest, README, compact
  sample-quality summary, and optional outcome-filled sample into one local
  review workspace. `main.py
  --event-fade-cache-review-bundle OUT_DIR` builds the same workspace directly
  from latest cached candidate snapshots. The manifest/README summary includes
  event type, relationship, asset role, signal type, source-provider,
  source-origin, proxy, direct, trigger, missing-event-time, per-source provider,
  and per-source origin quality counts.
  Empty bundles warn in CLI output,
  README, and manifest when no validation rows were produced. `make event-fade-review-cycle` runs
  the fixture-backed cache refresh and cache review-bundle export with the same
  `EVENT_DISCOVERY_CACHE_DIR`; `make event-fade-configured-review-cycle` runs
  the same bundle workflow after a refresh that uses only configured
  event-discovery sources from the environment/`.env`. `make
  event-fade-public-rss-review-cycle` is the no-key convenience path for
  public RSS feeds listed in
  `fixtures/event_discovery/public_rss_feeds.txt`, including targeted Google
  News RSS searches for pre-IPO/tokenized-stock/synthetic-exposure, fan-token,
  prediction-market, sports, and political proxy narratives. It defaults to a
  30-day lookback and a broader live CoinGecko resolver universe, and writes
  only research cache/review artifacts.
  `make event-fade-gdelt-review-cycle` is the no-key convenience path for live
  GDELT Article List news. It uses the configured proxy-narrative query, defaults
  to a 30-day lookback plus live CoinGecko universe enrichment, and writes only
  research cache/review artifacts.
  `make event-fade-polymarket-review-cycle` is the no-key convenience path for
  Polymarket Gamma dated catalyst events. It defaults to live CoinGecko universe
  enrichment and writes only research cache/review artifacts.
  `make event-fade-no-key-review-cycle` runs public RSS, GDELT, and Polymarket
  into the same cache before writing a single mixed-source review bundle.
  `main.py --event-fade-merge-sample FRESH REVIEWED OUT`
  preserves prior human review status/labels/outcomes when regenerating a fresh export.
  Cached candidate snapshots track first-seen/watchlisted/armed/triggered and
  last-seen timestamps for research validation; outcome price exports support
  daily or hourly candles and record interval/source in filled samples. Beyond
  the explicit opt-in Binance/Bybit announcements, CryptoPanic, GDELT news,
  RSS/Atom feed fetches, Polymarket Gamma catalyst events, and Coinalyze derivatives enrichment, no network
  event/news/derivatives/supply providers,
  live DB writes, notifications, or paper trades
  are enabled. `main.py --event-discovery-refresh` can write the local
  observational JSONL cache only. `main.py --event-discovery-status` prints
  redacted provider readiness and treats enrichment-only configuration as not
  ready for the configured review cycle. Bybit listings/perp listings are direct events
  and must remain `NO_TRADE` unless separate evidence proves a true proxy
  relationship.
- Caveats: the plain Binance backtest path is survivorship-biased (today's
  top-N). Prefer `--pit-volume` for any conclusion-bearing research; `--pit`
  (CoinGecko mcap) remains for cross-checking but is capped at 365d on the demo
  key.

---

## Open next steps

Use `ROADMAP.md` as the live task list. The current high-leverage items are:

1. Let the paper scoreboard accrue ~1–2 weeks; confirm gating helps live.
2. Validate whether edge-prior conviction buckets outperform the old heuristic.
3. Confirm the 2026-06-09 state-slice candidates via cached PIT/live data before any
   live conviction or routing change.
4. Use `main.py --event-discovery-status` to confirm at least one real event
   source is ready, or use `make event-fade-no-key-review-cycle` as the
   no-key RSS/GDELT/Polymarket starting point. For review bundles, prefer the
   bundle wrappers after the human fills `review_template_balanced.csv`:
   `EVENT_FADE_REVIEW_BUNDLE_DIR=/path/to/bundle make event-fade-check-review-bundle`,
   then `make event-fade-apply-review-bundle`, then
   `make event-fade-review-applied-bundle`. If reviewed trigger rows exist, run
   `make event-fade-fill-review-bundle-outcomes`. Use
   `main.py --event-fade-merge-sample FRESH REVIEWED OUT` when regenerating a
   fresh sample and preserving prior human review status/labels/outcomes. Do not
   promote event-fade output beyond local reports until the reviewed sample
   clears the review gates.
5. Monitor universe hygiene false positives/negatives and tune thresholds.
6. Use `make dry-run-fixture` before network dry-runs when validating scanner
   plumbing that does not need live CoinGecko data.

When in doubt, read the latest `DEVLOG.md` entries, then ask the human.
