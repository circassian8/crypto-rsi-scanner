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
- Run `make verify` first; don't commit a red tree.
- Never commit secrets/artifacts: `.env`, `*.db`, logs, `.venv`, and
  `.claude/settings.local.json` are gitignored — keep it that way.
- Commit on `main`, then `git push` after the commit. The human gave standing
  approval on 2026-06-16 to push after every commit. Ask again only before
  changing remotes, force-pushing, or pushing to a different branch.

## Collaboration files

| file | purpose |
|---|---|
| `DEVLOG.md` | Newest-first history of completed non-trivial changes. |
| `ROADMAP.md` | Current pending work, blocked items, and priorities. |
| `DECISIONS.md` | Durable accepted/rejected decisions and revisit conditions. |
| `CLAUDE.md` | Thin Claude Code bridge back to this protocol. |
| `research/` | Checked-in research notes for backtest reviews and non-code conclusions. |
| `fixtures/backtest_smoke/` | Checked-in BTC/ETH/SOL daily klines for offline backtest smoke. |

Before starting substantial work, read `ROADMAP.md` and `DECISIONS.md` after this
file. When a change completes or changes priority/status, update `ROADMAP.md`.
When a choice should prevent future relitigation, add or update `DECISIONS.md`.

---

## Project in one paragraph

A top-100 crypto multi-timeframe **RSI overextension scanner**. Each day it pulls
the top coins from CoinGecko, computes Wilder RSI (daily/4H/weekly) plus context
(z-score, volume, divergence, BTC correlation, trend regime), classifies each
signal into a **setup type** (mean_reversion / dip_buy / trend_continuation /
breakdown_risk), scores conviction, **gates it by the BTC market regime**, and
sends tiered alerts to Telegram. It self-grades past signals, paper-trades them,
and a separate `backtest.py` validates strategy ideas on years of history.
**Deployed live** on the owner's Mac via launchd (daily scan + always-on bot).

---

## Run / test / deploy

- **Python:** `.venv/bin/python` (3.13). Deps in `requirements.txt`. (Note: `pytest`
  is NOT installed — use the standalone runner below.)
- **Standard verification:** `make verify` (runs tests + alert render smoke +
  backtest fixture smoke + paper scoreboard).
- **Tests (must all pass before you claim done):**
  `.venv/bin/python tests/test_indicators.py`
- **Alert render smoke (no sends/network):** `make smoke-alerts`
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
  unlock, news/proxy-narrative, opt-in live Binance/Bybit/CryptoPanic/GDELT/RSS, external catalyst,
  Coinalyze-style derivatives with opt-in live Coinalyze enrichment,
  supply/on-chain enrichment, and clean CoinGecko
  universe fixtures or opt-in live CoinGecko universe resolver enrichment,
  research-only/no writes) · `main.py --event-discovery-refresh` (fetch
  configured event-discovery sources and append research-only JSONL cache
  artifacts under `RSI_EVENT_DISCOVERY_CACHE_DIR`; no live DB writes) ·
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
  `main.py --event-fade-apply-review-template SAMPLE TEMPLATE OUT` (copy
  sidecar human review status/labels/outcomes back into a validation sample; writes only
  `OUT`) ·
  `main.py --event-fade-review-bundle SAMPLE OUT_DIR` (write a local manual
  review workspace with copied sample, optional outcome-filled sample, queue,
  packet, sidecar, review report, manifest, and README; writes only under
  `OUT_DIR`) ·
  `main.py --event-fade-cache-review-bundle OUT_DIR` (same review workspace,
  sourced from latest cached candidate snapshots under
  `RSI_EVENT_DISCOVERY_CACHE_DIR`; writes only under `OUT_DIR`) ·
  `main.py --event-fade-merge-sample FRESH REVIEWED OUT` (copy prior human
  review status/labels/outcomes into a fresh validation export; writes only `OUT`) ·
  `main.py --event-fade-export-outcome-prices SAMPLE OUT` (build a local OHLCV
  price fixture for `SHORT_TRIGGERED` sample rows, optionally from fixture
  klines; writes only `OUT`) ·
  `main.py --event-fade-fill-outcomes SAMPLE PRICES OUT` (fill
  trigger-time and event-time-baseline `SHORT_TRIGGERED` validation outcome
  fields from local OHLCV fixtures; writes only `OUT`) ·
  `main.py --universe-audit` (latest hygiene audit)
- **DB backup:** `main.py --backup-db` or `make backup-db` (SQLite online backup
  API + integrity check + retention); `main.py --verify-restore` restore-checks
  the newest retained backup.
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
  (cost-aware research) · `--walk-forward` (chronological setup stability) ·
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
| `event_models.py` | immutable event-discovery dataclasses for raw events, normalized events, links, classifications, and candidates |
| `event_discovery.py` | research-only event radar orchestration: normalize → dedupe → resolve → classify → optional fade scoring, grouped auto reports, and validation sample exports |
| `event_cache.py` | research-only JSONL observational cache for point-in-time event-discovery evidence; no live SQLite/signal/paper writes |
| `event_validation.py` | research-only validation-sample loader/reviewer/labeling-queue/merger for human labels, outcome metrics, and promotion blockers |
| `event_resolver.py` / `event_classification.py` | conservative asset matching and deterministic proxy/direct classification |
| `event_providers/` | research event provider interfaces, manual JSON event fixtures, cleaned CoinGecko universe fixture provider plus opt-in live CoinGecko universe resolver enrichment, exchange announcement parsers with captured Binance CMS WebSocket payload support plus opt-in live Binance WebSocket and Bybit HTTP fetches, structured calendar/unlock parsers, CryptoPanic/GDELT/project-blog news parsers with opt-in live CryptoPanic posts, GDELT Article List, and project-blog RSS/Atom fetches, and external IPO/sports/prediction-market catalyst parsers |
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
  into kept candidates.
- `state_features.py` is pure and shadow-first. State features may be tested,
  stored, and reported before they are allowed to affect conviction, routing, or
  gating. The live scanner attaches `state_json` only after the existing decision
  fields are already computed.
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
  Provider enrichment is evidence, not eligibility; raw reviewed fixture
  evidence takes precedence over provider rows.
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
  imply promotion. `main.py --event-discovery-binance-listen` may append raw
  Binance announcement evidence and run metadata to the same cache; it must not
  normalize into live signals, route alerts, or paper trade.
- Event-fade validation review is research-only. `main.py --event-fade-review-sample`
  may read labeled JSONL/CSV sample artifacts and print coverage, trigger
  precision, trigger latency, point-in-time violations, MFE/MAE, post-event
  returns, event-time short baseline comparison,
  event-type/relationship/BTC-risk cohorts, diversity gates, and promotion
  blockers plus concrete next-sample work. A row only counts as reviewed
  evidence when it has `review_status=reviewed` and a known `human_label`.
  The review command must not automatically promote alerts, write live storage,
  open paper trades, or imply execution.
- Event-fade validation labeling queues are artifact-only. `main.py
  --event-fade-labeling-queue` may prioritize unlabeled proxy/control rows and
  reviewed triggered rows missing required outcomes, source-timing review, or
  explicit review status/labels, but it must not auto-label rows, modify sample
  files, write storage, route alerts, open paper trades, or imply promotion.
- Event-fade validation review packets are artifact-only. `main.py
  --event-fade-review-packet SAMPLE OUT` may write a Markdown packet for manual
  validation review, but it must not auto-label rows, modify the source sample,
  write storage, route alerts, open paper trades, or imply promotion.
- Event-fade validation review templates are artifact-only. `main.py
  --event-fade-export-review-template SAMPLE OUT` may write compact editable
  sidecar rows, and `main.py --event-fade-apply-review-template SAMPLE TEMPLATE
  OUT` may copy nonblank human labels/notes/outcomes from that sidecar into a
  validation-sample artifact. They must not infer labels, write live storage,
  route alerts, open paper trades, or imply promotion.
- Event-fade validation review bundles are artifact-only. `main.py
  --event-fade-review-bundle SAMPLE OUT_DIR` may copy the sample and write local
  review aids under `OUT_DIR`; with `--event-fade-review-bundle-prices` it may
  also fill outcome fields into a bundle-local sample copy. It also writes a
  `manifest.json` for bundle provenance/counts. It must not infer labels, write
  live storage, route alerts, open paper trades, or imply promotion.
- Event-fade validation merges are artifact-only. `main.py --event-fade-merge-sample`
  may copy nonblank human labels/notes/outcomes from a previously reviewed
  JSONL/CSV sample into a fresh export by event/asset/relationship identity, but
  it must only write the requested output artifact.
- `indicators.py` stays pure and tested. New signal logic → add a test.
- Alert/formatting changes must keep `make smoke-alerts` passing; it checks
  representative Telegram/plain-text renders without sending anything.
- Notification bookkeeping is delivery-sensitive: only mark instant cooldowns or
  digest timestamps after at least one channel succeeds.
- Run `make verify` before claiming implementation work is complete. If you skip
  it, say exactly why.
- Storage: additive `ALTER` in `_migrate`; bump a `meta` flag for one-time data
  migrations so they run exactly once.
- External calls **fail soft** (log + degrade; never crash the scan).
- Never print/log secrets — route through `config.redact_token`.
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
  one for review; still NOT live-loaded. `research/PIT_DATA_OPTIONS_2026-06-09.md`
  is historical context. Residual caveats: delisted pairs absent, single venue,
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
  RSS/Atom feeds from explicit `RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS` when
  `RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE=1`, can parse local external IPO,
  sports, and prediction-market catalyst fixtures as radar evidence, can attach local
  Coinalyze-style OI/funding/crowding snapshots from
  `RSI_EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH`, can optionally fetch live
  Coinalyze derivatives snapshots from explicit
  `RSI_EVENT_DISCOVERY_COINALYZE_SYMBOLS` or auto-resolved Coinalyze
  `future-markets` symbols from already-resolved discovery assets when
  `RSI_EVENT_DISCOVERY_COINALYZE_LIVE=1`, can attach local
  Tokenomist/Etherscan/Arkham/Dune-style supply and on-chain snapshots from the
  `RSI_EVENT_DISCOVERY_*_SUPPLY_PATH` env vars, and feeds structured candidates
  through `event_fade.py` for flat radar and grouped auto reports. The grouped
  report is `main.py --event-fade-auto-report` and prints event radar, proxy
  watchlist, blowoff risk, event-passed, armed, triggered, rejected/no-trade,
  and ambiguous sections with evidence/warnings. The validation-sample export is
  `main.py --event-fade-export-sample PATH` and writes JSONL/CSV rows with raw
  source evidence, point-in-time timestamps, link/classifier evidence, fade
  features, missing-data fields, raw/min/max source timestamps for leakage
  review, and blank human-review/outcome columns.
  `main.py --event-fade-review-sample PATH` reads labeled sample artifacts and
  reports sample coverage, reviewed trigger count, trigger precision,
  false-positive rate, trigger latency, point-in-time evidence violations,
  post-decision source evidence,
  MFE/MAE, post-event returns, event-time short baseline comparison,
  event-type/relationship/BTC-risk cohorts, and blockers such as too few
  reviewed proxy/control/trigger cases, too-narrow event/BTC-risk diversity, or
  weak edge-quality metrics. It also prints concrete next-sample work so the
  reviewer knows which cases, labels, statuses, or outcomes to add next.
  `main.py --event-fade-labeling-queue PATH`
  prioritizes the next rows to label, rows missing explicit review status, and
  triggered rows missing required outcome fields.
  `main.py --event-fade-review-packet SAMPLE OUT` writes a
  Markdown packet for the same prioritized rows with source URLs, raw titles,
  classifier evidence, signal/risk fields, trigger/event-time outcomes, and the
  human fields to fill. `main.py --event-fade-export-review-template SAMPLE OUT`
  writes a compact editable sidecar for those rows, and
  `main.py --event-fade-apply-review-template SAMPLE TEMPLATE OUT` applies
  nonblank sidecar review status/labels/outcomes back into a requested sample artifact.
  `main.py --event-fade-review-bundle SAMPLE OUT_DIR` writes the sample copy,
  queue, packet, template, review report, manifest, README, and optional
  outcome-filled sample into one local review workspace. `main.py
  --event-fade-cache-review-bundle OUT_DIR` builds the same workspace directly
  from latest cached candidate snapshots.
  `main.py --event-fade-merge-sample FRESH REVIEWED OUT`
  preserves prior human review status/labels/outcomes when regenerating a fresh export. Beyond
  the explicit opt-in Binance/Bybit announcements, CryptoPanic, GDELT news,
  RSS/Atom feed fetches, and Coinalyze derivatives enrichment, no network
  event/news/derivatives/supply providers,
  live DB writes, notifications, or paper trades
  are enabled. `main.py --event-discovery-refresh` can write the local
  observational JSONL cache only. Bybit listings/perp listings are direct events
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
4. Use `main.py --event-fade-export-sample PATH` to build a manually reviewed
   event-fade sample from discovery fixtures, use
   `main.py --event-fade-merge-sample FRESH REVIEWED OUT` to preserve prior
   review status/labels/outcomes across refreshes, use
   `main.py --event-fade-labeling-queue PATH` to prioritize missing
   review status/labels/outcomes, optionally write a review packet with
   `main.py --event-fade-review-packet SAMPLE OUT`, fill a compact sidecar from
   `main.py --event-fade-export-review-template SAMPLE OUT`, apply it with
   `main.py --event-fade-apply-review-template SAMPLE TEMPLATE OUT`, optionally
   build a review workspace with `main.py --event-fade-review-bundle SAMPLE
   OUT_DIR`, then use
   `main.py --event-fade-review-sample PATH` before promoting event-fade output
   beyond local reports.
5. Monitor universe hygiene false positives/negatives and tune thresholds.
6. Use `make dry-run-fixture` before network dry-runs when validating scanner
   plumbing that does not need live CoinGecko data.

When in doubt, read the latest `DEVLOG.md` entries, then ask the human.
