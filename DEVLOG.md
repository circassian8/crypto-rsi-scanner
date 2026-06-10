# DEVLOG — change history

This project now has **local git** for diffs/rollback, while this file remains
the human-readable narrative history. **Newest entries at the top**, just under
this header. Append (prepend) one entry per non-trivial change. Keep it skimmable;
deep reasoning can link to code. See `AGENTS.md` for the working agreement.

### Entry template (copy this)

```
## YYYY-MM-DD — <short title> · <Claude|Codex|human>
**Why:** one or two sentences of motivation.
**Changes:** bullet list, with file references.
**Verify:** what you ran and the result (tests, dry-run, backtest…).
**Notes/risks:** anything the next agent should know. Optional.
```

---

## 2026-06-10 — Volume-rank PIT universe: 5y survivorship-reduced backtest, no Pro key · Claude
**Why:** Every blocked research item (bull/chop validation, prior recalibration,
state-cohort confirmation) was gated on point-in-time history >365d, which the
mcap PIT path can't get on a demo CoinGecko key. Binance klines are free for ~5y
and carry quote (USDT) volume — so membership can be ranked by trailing dollar
volume instead of market cap.
**Changes:**
- `backtest.py`: `--pit-volume` mode — `binance_usdt_pool()` (exchangeInfo,
  hygiene-filtered; no leveraged-token suffix filter needed since those are all
  delisted, and JUP/SYRUP are real coins), `build_volume_membership()` (top-N by
  trailing `--volume-window`=30d mean quote volume, no lookahead),
  `run_pit_volume()` (walks on USD volume so volume_ratio matches live CoinGecko
  semantics). `fetch_klines` now returns `quote_volume` and caches raw rows under
  `backtest_cache/binance_klines/` (reuses the PIT cache flags; cache hit never
  touches the network).
- Tests: membership rolling-rank, pool hygiene filter, kline row parsing, cache
  roundtrip (132/132).
- `research/VOLUME_PIT_BACKTEST_2026-06-10.md` + prior export
  `research/registry_priors_volpit_2026-06-10.json`; ROADMAP: two "needs Pro
  key" items closed, follow-ups added.
**Verify:** `make verify` green (132/132 + smokes). Full run: 368 coins, 21,334
graded obs, balanced coverage (BULL 60.9k / CHOP 23.8k / BEAR 46.7k base-days).
**Results:** Gating map confirmed on survivorship-reduced full-cycle data —
mean_reversion CHOP **+10 (n=800)** third independent confirmation;
mean_reversion BULL −3; dip_buy/trend_continuation BULL positive but thin
(+6/+4); breakdown_risk no edge anywhere (context-only stays right). **Conviction
monotonic with edge for the first time** (low −3 / med +3 / high +9, n=307) —
first real validation of the registry edge-prior conviction. State-slice
replications: breakdown_risk crisis-vol −19; mean_reversion washout +14,
risk_on_broad −8.
**Notes/risks:** Residual survivorship (delisted pairs absent from exchangeInfo);
single venue; volume-rank ≠ live mcap universe. Prior export is reviewable only —
NOT loaded live (opt-in policy unchanged).

## 2026-06-09 — Fix review reliability gaps · Codex
**Why:** A fresh review found several boundary bugs: failed alert sends could
still advance cooldown/digest state, paper trades opened before matured same-coin
positions closed, live outcome reports could not directly validate gating, and
dry-run/universe-audit behavior had small honesty gaps.
**Changes:**
- `crypto_rsi_scanner/scanner.py` now skips CSV writes in dry-run mode, fetches
  extra recent histories for pending outcome/paper bookkeeping when coins leave
  today's clean universe, and only marks instant/digest notification state after
  a channel succeeds.
- `crypto_rsi_scanner/notifications.py` splits long Telegram messages into
  multiple line-aware chunks instead of truncating later cards.
- `crypto_rsi_scanner/storage.py` adds `signals.market_aligned`, backfills it
  additively, exposes pending signal/open paper coin IDs, and returns market/state
  context from `outcomes_joined()`.
- `crypto_rsi_scanner/outcomes.py` adds actionable/control, market-alignment, and
  state-cohort sections to `main.py --report`.
- `crypto_rsi_scanner/paper.py` closes matured trades before opening new
  crossings and treats missing falling-knife state as unknown, not low risk.
- `crypto_rsi_scanner/universe.py` stores all kept audit rows so suspicious-kept
  checks cover the full requested clean universe.
- `tests/test_indicators.py`, `AGENTS.md`, `ROADMAP.md`, `DECISIONS.md`, and
  `main.py` document and cover the reliability changes.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 128/128.
`main.py --report`, `make dry-run-fixture`, and `make score-cohorts` run
successfully. `make verify` passes tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** This changes live reliability/bookkeeping and reporting, but not
the core RSI setup taxonomy, conviction priors, or market-gating rules. The first
post-change `Storage` open migrates the ignored live DB with `market_aligned`.

## 2026-06-09 — Add cohort, cost, and walk-forward research tools · Codex
**Why:** The remaining improvement tracks needed tooling before any live signal
behavior changes: live cohort reads, cost/slippage-aware backtest output,
chronological stability checks, and a repeatable way to spot universe hygiene
leaks.
**Changes:**
- `crypto_rsi_scanner/paper.py`, `scanner.py`, `main.py`, and `Makefile` add
  `main.py --score --cohorts` / `make score-cohorts`, including state-bucket
  cohort stats from stored `state_json` once paper trades close.
- `crypto_rsi_scanner/backtest.py` adds `--costs`, `--fee-bps`,
  `--slippage-bps`, `--max-trades-per-day`, `--walk-forward`, and timestamped
  signal labels so research can inspect costs, capacity, drawdown, and fold
  stability before promoting calibration.
- `crypto_rsi_scanner/universe.py` adds suspicious-kept leak detection to the
  audit formatter for stable/wrapped/yield-like rows that survive filtering.
- `research/PIT_DATA_OPTIONS_2026-06-09.md` documents the current 365d PIT data
  limit, Pro-key/deeper-history workflow, alternate provider contract, and
  promotion rule.
- `AGENTS.md`, `ROADMAP.md`, and `DECISIONS.md` record the new commands and the
  decision that cost/walk-forward outputs are research-only until a specific
  live rule is proposed.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 124/124.
`make score-cohorts`, `make backtest-costs`, and `make universe-audit` all run
successfully. `make verify` passes tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** No live signal scoring, routing, or gating changed. Broader PIT
history still requires a Pro CoinGecko key or alternate historical market-cap
provider before registry priors should be promoted live.

## 2026-06-09 — Add universe audit refresh command · Codex
**Why:** After tightening hygiene filters, the project still had to wait for a
full scheduled scan to confirm the market-list filter. A lightweight refresh
path gives immediate feedback without running RSI analysis or sending alerts.
**Changes:**
- `crypto_rsi_scanner/scanner.py` adds `fetch_universe_audit()` plus
  `main.py --refresh-universe-audit`, which fetches current CoinGecko market
  rows, applies shared universe hygiene, persists the audit, and prints it.
- `Makefile` adds `make refresh-universe-audit`.
- `crypto_rsi_scanner/universe.py` now directly excludes symbols that start or
  end with `usd`, catching observed BFUSD/apxUSD leaks from the refreshed audit.
- `tests/test_indicators.py` covers the audit refresh helper with a fake
  CoinGecko client and the new USD-prefix/suffix examples.
- `ROADMAP.md`, `DECISIONS.md`, and `AGENTS.md` document the workflow and the
  refreshed audit result.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 122/122.
`make refresh-universe-audit` persisted a fresh audit: 200 fetched, 100 kept, 53
excluded (`stable_like=36`, `low_liquidity=17`). A kept-set regex scan found no
obvious USD/stable/yield leaks. `make verify` passes tests, alert render smoke,
backtest fixture smoke, and paper scoreboard after the documentation update.
**Notes/risks:** The command updates `universe_hygiene_latest.json` and the DB
meta audit, but does not run a full scan, send alerts, or alter signal state.

## 2026-06-09 — Tighten universe stable/pegged filters · Codex
**Why:** The next roadmap item was to review the latest live universe hygiene
audit for false positives/negatives. The 2026-06-09 03:10 MSK audit showed
stable/pegged products surviving into the kept top-100.
**Changes:**
- Reviewed `main.py --universe-audit`: 200 fetched, 100 kept, 41 excluded
  (`stable_like=19`, `low_liquidity=22`).
- `crypto_rsi_scanner/universe.py` now catches observed false negatives:
  USD1, Global Dollar/USDG, USDtb, United Stables, GHO, YLDS, USX, USYC,
  Tether Gold/XAUT, and PAX Gold/PAXG.
- `crypto_rsi_scanner/config.py` mirrors the safe symbol-only exclusions; the
  one-letter United Stables symbol is caught by name instead.
- `tests/test_indicators.py` covers the newly observed stable/pegged examples.
- `ROADMAP.md`, `DECISIONS.md`, and `AGENTS.md` record the audit result and the
  follow-up to re-check the next live audit.
**Verify:** Replayed the known kept false negatives through `exclusion_reason()`;
they now return `stable_like`. `.venv/bin/python tests/test_indicators.py`
passes 121/121. `make verify` passes tests, alert render smoke, backtest fixture
smoke, and paper scoreboard after the documentation update.
**Notes/risks:** Low-liquidity exclusions such as LEO were left unchanged. The
next scheduled scan should confirm these products no longer appear in the kept
universe.

## 2026-06-09 — Add offline backtest fixture smoke · Codex
**Why:** The final ready roadmap item was to make the backtest CLI smoke-testable
without relying on Binance/network availability.
**Changes:**
- `crypto_rsi_scanner/backtest.py` can load Binance-style daily kline CSVs via
  `--fixture-dir`, infer symbols from fixture filenames, and fail smoke runs with
  `--min-signals` when too few graded observations are produced.
- Added checked-in BTC/ETH/SOL 365d fixture snapshots under
  `fixtures/backtest_smoke/klines/` plus a fixture README.
- `Makefile` adds `make backtest-fixture` and includes it in `make verify`.
- `tests/test_indicators.py` covers fixture symbol inference and CSV parsing.
- `ROADMAP.md`, `DECISIONS.md`, and `AGENTS.md` document the completed fixture
  smoke and its verification role.
**Verify:** `make backtest-fixture` produces 3 usable coins and 33 graded
observations. `.venv/bin/python tests/test_indicators.py` passes 121/121.
`make verify` passes tests, alert render smoke, backtest fixture smoke, and paper
scoreboard after the documentation update.
**Notes/risks:** No live scanner logic changed. The fixture is a small smoke
dataset, not strategy evidence.

## 2026-06-09 — Review cached PIT registry priors · Codex
**Why:** The next roadmap research step was to export registry conviction priors
from point-in-time histories and decide whether the artifact is strong enough to
load live.
**Changes:**
- Ran `.venv/bin/python -m crypto_rsi_scanner.backtest --pit --top-n 80 --pool
  150 --days 365 --export-priors research/registry_priors_pit_2026-06-09.json`:
  150 cache hits, 128 usable histories, 1325 graded observations.
- Added `research/registry_priors_pit_2026-06-09.json` and
  `research/PIT_REGISTRY_PRIORS_REVIEW_2026-06-09.md` with the exported deltas
  and review-only decision.
- `ROADMAP.md`, `DECISIONS.md`, and `AGENTS.md` now record that the 365d PIT
  prior export is BEAR-only evidence and should not be loaded with
  `RSI_REGISTRY_PRIORS`.
**Verify:** PIT export completed successfully. `make verify` passes tests
120/120, alert render smoke, and paper scoreboard after the documentation
updates.
**Notes/risks:** No signal logic changed. The export moved
`mean_reversion.neutral` 42 -> 47 and `trend_continuation.neutral` 42 -> 40, but
that is not enough for live adoption because the market coverage was only BEAR.

## 2026-06-09 — Run cached PIT state-slice confirmation · Codex
**Why:** The next roadmap item was to use point-in-time membership to check
whether the current-top Binance state-slice candidates survive a less
survivorship-biased test.
**Changes:**
- Ran `.venv/bin/python -m crypto_rsi_scanner.backtest --pit --top-n 80 --pool
  150 --days 365 --state-slices`: cache started empty, populated 150 raw
  CoinGecko histories, used 128 histories, and produced 1325 graded observations.
- Added `research/PIT_STATE_SLICE_CONFIRMATION_2026-06-09.md` with the command,
  caveats, setup baseline, state-slice read, and no-live-change decision.
- `ROADMAP.md`, `DECISIONS.md`, and `AGENTS.md` record that this PIT result is
  bear-regime evidence only; bull/chop state candidates still need deeper PIT or
  live confirmation.
**Verify:** PIT run completed successfully and populated the local gitignored
cache. `make verify` passes tests 120/120, alert render smoke, and paper
scoreboard after the documentation update.
**Notes/risks:** No signal logic changed. The 365d demo CoinGecko PIT window
only had BTC `BEAR` market-regime coverage, so it supports monitoring
bear-regime `mean_reversion` and keeping `breakdown_risk` context-only, but does
not validate bull/chop rules.

## 2026-06-09 — Add PIT history cache for backtests · Codex
**Why:** PIT state-slice confirmation and registry calibration depend on
CoinGecko market-cap histories, which are rate-limit sensitive and expensive to
refetch. A local raw-history cache improves practical PIT research power even
before a deeper Pro/alternate data source is available.
**Changes:**
- `crypto_rsi_scanner/backtest.py` caches raw CoinGecko `market_chart` JSON for
  PIT histories, reads cached histories before network fetches, and adds
  `--pit-cache-dir`, `--no-pit-cache`, and `--refresh-pit-cache` flags.
- `crypto_rsi_scanner/config.py`, `.env.example`, and `.gitignore` add the
  configurable `RSI_BACKTEST_CACHE_DIR` (`backtest_cache` by default) and keep
  cached research data out of git.
- `tests/test_indicators.py` adds a PIT cache roundtrip test that loads a cached
  synthetic history without network.
- `AGENTS.md`, `ROADMAP.md`, and `DECISIONS.md` document the cache behavior and
  the remaining data-source limit for >365d PIT history.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 120/120.
`.venv/bin/python -m crypto_rsi_scanner.backtest --help | rg
"pit-cache|refresh-pit-cache|no-pit-cache"` confirms the CLI flags. `make
verify` passes tests, alert render smoke, and paper scoreboard.
**Notes/risks:** This improves repeatability/resume behavior and larger-pool PIT
runs, but it does not bypass CoinGecko demo history limits. >365d PIT still needs
a Pro key or alternate historical market-cap source.

## 2026-06-09 — Run first larger state-slice review · Codex
**Why:** The next research step was to use `backtest --state-slices` on a larger
history and decide whether any shadow market-state buckets are ready for live
promotion.
**Changes:**
- Ran `.venv/bin/python -m crypto_rsi_scanner.backtest --top-n 80 --days 1460
  --state-slices`: 49 usable Binance histories, 7648 graded observations.
- Added `research/STATE_SLICE_BACKTEST_2026-06-09.md` with the command, caveats,
  setup baseline, market-regime check, candidate state cohorts, and no-promotion
  decision.
- `crypto_rsi_scanner/backtest.py` widens the state-slice table columns so long
  feature labels do not run into bucket names.
- `ROADMAP.md`, `DECISIONS.md`, and `AGENTS.md` record that these candidates
  need PIT/live confirmation before any live conviction/routing change.
**Verify:** Larger state-slice run completed successfully. Full local
verification was rerun after the docs/formatting update: `make verify` passes
tests 119/119, alert render smoke, and paper scoreboard.
**Notes/risks:** No live signal logic changed. Most plausible candidates are
documented, but the run is current-top survivorship-biased, single-venue, and
costless, so it is not enough to alter live alerts.

## 2026-06-09 — Add state-conditioned backtest slices · Codex
**Why:** Live scanner now stores shadow market-state context, but those labels
need a research path that can test conditional edge before any state bucket is
allowed to affect conviction or routing.
**Changes:**
- `crypto_rsi_scanner/state_features.py` exposes shared bucket/risk helpers for
  relative strength, liquidity, breadth state, and falling-knife risk so live and
  research use the same labels.
- `crypto_rsi_scanner/scanner.py` now consumes those shared helpers instead of
  private copies.
- `crypto_rsi_scanner/backtest.py` adds point-in-time state-frame construction,
  stores state labels on graded events, builds same-regime/same-state base-rate
  tables, and exposes `--state-slices` / `--state-min-samples` for research
  reports.
- `tests/test_indicators.py`, `AGENTS.md`, `ROADMAP.md`, and `DECISIONS.md`
  cover and document the new state-slice benchmark rule.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 119/119.
`.venv/bin/python -m crypto_rsi_scanner.backtest --help | rg
"state-slices|state-min-samples"` confirms the new CLI flags. `make verify`
passes tests, alert render smoke, and paper scoreboard.
**Notes/risks:** The state-slice report is still research-only. A bucket should
not be promoted into live conviction/routing unless it beats the same-regime,
same-state base rate with enough PIT/live observations.

## 2026-06-08 — Wire market-state context into live scanner · Codex
**Why:** The pure state feature layer needs live, reviewable observations before
any state-conditioned edge can be trusted. Scanner rows should therefore carry
volatility, breadth, relative-strength, liquidity, and falling-knife context
without changing current alert decisions.
**Changes:**
- `crypto_rsi_scanner/scanner.py` builds one shadow state context per scan,
  attaches per-coin `state_json`, `vol_state`, `breadth_state`, `rs_bucket`,
  `liquidity_bucket`, and `falling_knife_score` after conviction/tier are
  computed, and adds compact console tokens for meaningful state labels.
- `crypto_rsi_scanner/storage.py` additively migrates `signals` and
  `paper_trades` with nullable `state_json`; `crypto_rsi_scanner/paper.py`
  stores the entry-state snapshot for paper trades.
- `crypto_rsi_scanner/telegram.py` preserves compact state buckets in the latest
  bot snapshot.
- `tests/test_indicators.py`, `ROADMAP.md`, `DECISIONS.md`, and `AGENTS.md`
  document and test the shadow-only state boundary.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 117/117.
`make dry-run-fixture` runs offline and shows state tokens in the scan output.
`make smoke-alerts` passes. `make verify` passes tests, alert render smoke, and
paper scoreboard.
**Notes/risks:** State remains observational only. The next high-leverage work is
state-conditioned backtest/live cohort analysis before allowing any state bucket
to affect conviction or routing.

## 2026-06-08 — Add pure market-state feature layer · Codex
**Why:** The research plan keeps RSI as the event trigger but needs a separate,
auditable market-state layer before testing volatility, breadth, relative
strength, beta, liquidity, and falling-knife hypotheses.
**Changes:**
- New `crypto_rsi_scanner/state_features.py` adds pure helpers for realized
  volatility, trailing percentiles, volatility state labels, percentage returns,
  cross-sectional ranks, single/multi-factor beta, volume z-score, dollar
  volume, turnover, volume/price state, and breadth snapshots.
- `tests/test_indicators.py` adds standalone tests covering flat/changing
  volatility, trailing-only percentiles, volatility state rules, rank monotonicity,
  synthetic beta recovery, volume/liquidity classification, and breadth behavior
  with missing/short histories.
- `AGENTS.md`, `ROADMAP.md`, and `DECISIONS.md` document the shadow-first state
  feature policy and next integration step.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 115/115.
`make verify` passes tests, alert render smoke, and paper scoreboard.
**Notes/risks:** This is intentionally not wired into scanner routing, conviction,
or registry priors. Next step is shadow-only scanner/backtest integration with
`state_json`.

## 2026-06-08 — Add maintenance agent, restore drill, fixtures, and audit outputs · Codex
**Why:** The scanner had backup/log commands, but the remaining system
improvements were still manual or not reviewable: scheduled maintenance,
restore proof, structured paper-score data, universe-hygiene audits, and offline
scanner fixtures.
**Changes:**
- `main.py --maintenance` now runs a safe DB backup, restores that backup into a
  temporary SQLite DB for verification, and rotates configured logs.
- `main.py --verify-restore` restore-checks the newest retained backup by
  default; `backups.py` exposes the reusable restore-drill primitive.
- `make install-maintenance-agent` installs/loads the daily launchd maintenance
  agent (`com.nasrenkaraf.rsimaintenance` by default) to run `--maintenance`.
- `main.py --score --json` emits structured paper-score data, and the text score
  report now includes market-alignment and conviction-bucket breakdowns.
- Live scans persist the latest universe hygiene audit to SQLite meta and
  `universe_hygiene_latest.json`; `main.py --universe-audit` prints it.
- `RSI_FIXTURE_DIR` enables CoinGecko fixture mode, with checked-in
  `fixtures/coingecko_smoke` powering `make dry-run-fixture`.
- `Makefile`, `.env.example`, `.gitignore`, `AGENTS.md`, `CLAUDE.md`,
  `ROADMAP.md`, and `DECISIONS.md` document the new commands and operating
  decisions.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 108/108.
`make verify` passes tests, alert render smoke, and paper scoreboard.
`main.py --verify-restore` passes against the latest backup. `make maintenance`
created and restore-checked `backups/rsi_scanner-20260608T185301Z.db`.
`make dry-run-fixture` runs the scanner offline from fixtures. The maintenance
LaunchAgent was installed at
`~/Library/LaunchAgents/com.nasrenkaraf.rsimaintenance.plist` and points at the
repo venv Python.
**Notes/risks:** `main.py --universe-audit` will show data after the next
non-dry live scan persists the first audit. The fixture smoke validates scanner
plumbing, not live CoinGecko availability.

## 2026-06-08 — Finish ops maintenance status, logs, and launchd helpers · Codex
**Why:** Safe backups existed, but operational health still did not show whether
the latest backup was fresh, logs could grow without a repo-owned rotation
command, and launchd service inspection required memorized shell commands.
**Changes:**
- `main.py --status` now reports newest backup freshness, retained backup count,
  and configured log sizes/rotation thresholds.
- New `crypto_rsi_scanner/ops.py` adds copy-truncate log rotation plus launchd
  scan/listener status parsing and listener restart helpers.
- `main.py`, `Makefile`, `config.py`, `.env.example`, `.gitignore`,
  `AGENTS.md`, `CLAUDE.md`, `ROADMAP.md`, and `DECISIONS.md` document and expose
  `--rotate-logs`, `--launchd-status`, and `--restart-listener`.
- `tests/test_indicators.py` covers backup freshness rendering, log rotation
  retention, and launchd output parsing.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 104/104.
`.venv/bin/python main.py --status` shows the live backup as `OK` and both logs
below rotation threshold. `.venv/bin/python main.py --launchd-status` reports
`com.nasrenkaraf.rsiscanner` loaded/not running with last exit 0 and
`com.nasrenkaraf.rsibot` running. `.venv/bin/python main.py --rotate-logs` keeps
the current small logs without rotating.
**Notes/risks:** This intentionally does not install or mutate launchd schedules;
use the new commands from an explicit scheduled job if/when the owner wants that.

## 2026-06-08 — Add safe SQLite DB backup command · Codex
**Why:** The scanner now has operational health reporting, but the live SQLite
DB still needed a safe recovery path. Because the DB runs in WAL mode and can be
open from the scan and listener, raw file copies are not reliable enough.
**Changes:**
- New `crypto_rsi_scanner/backups.py` uses SQLite's online backup API to create
  consistent snapshots, writes through a temp file, verifies the result with
  `PRAGMA integrity_check`, and prunes older backups by retention count.
- `main.py --backup-db` and `make backup-db` create a verified backup under
  `RSI_BACKUP_DIR` with `RSI_BACKUP_KEEP` retention.
- `config.py`, `.env.example`, `.gitignore`, `AGENTS.md`, `ROADMAP.md`, and
  `DECISIONS.md` document/configure the backup workflow and keep backup artifacts
  out of git.
- `tests/test_indicators.py` adds a temp-DB backup integrity and retention test.
**Verify:** `.venv/bin/python main.py --backup-db` created
`backups/rsi_scanner-20260608T182009Z.db`, size 0.20 MB, `integrity_check: ok`.
`make verify` passes: tests 101/101, alert render smoke, and paper scoreboard.
**Notes/risks:** Backup freshness is not yet shown in `--status`; ROADMAP keeps
that and log rotation as the next ops-hardening work.

## 2026-06-08 — Add scan status and bot health report · Codex
**Why:** The scanner had heartbeat alerts for crashes/degraded fetches, but no
single persisted view of the latest run state. If launchd missed a scan or a run
failed after fetching, the owner and bot had to infer health from logs.
**Changes:**
- `storage.py` now persists scan lifecycle status in SQLite meta: running,
  success, failure, start/finish times, last success/failure, fetch/analyze
  counts, signal counts, routing counts, outcome updates, and paper-trade updates.
- `scanner.py` records live scan start/success/failure status, preserves dry-run
  read-only behavior, returns notification routing counts, and adds
  `main.py --status`.
- New `status_report.py` renders one shared operational report for CLI and bot.
- `telegram.py` adds `/health` and `/status`, updates help text, and has the
  listener check stale successful scans with a one-alert-per-episode watchdog.
- `heartbeat.py`, `config.py`, and `.env.example` expose/tune stale-scan alerts
  via `RSI_STALE_SCAN_HOURS` and `RSI_STALE_CHECK_INTERVAL_SEC`.
- `AGENTS.md`, `ROADMAP.md`, and `DECISIONS.md` document the status path and
  narrow remaining ops hardening to DB backups/log rotation.
- `tests/test_indicators.py` adds status lifecycle/report, bot escaping, stale
  watchdog, and WAL/busy-timeout coverage.
**Verify:** `.venv/bin/python main.py --status` prints current local DB health
(`health: OK`, last success fallback from the existing `scans` table). `make
verify` passes: tests 100/100, alert render smoke, and paper scoreboard.
**Notes/risks:** Existing live runs will show `scan state: unknown` until the next
non-dry scan writes the new status meta; last-success freshness still falls back
to the historical `scans` table.

## 2026-06-08 — SQLite WAL + busy_timeout for scan/listener concurrency · Claude
**Why:** The daily scan (launchd) and the always-on bot listener share one SQLite
file. Default rollback-journal mode makes readers and writers block each other, so
a scan write during a listener read (or vice versa) risks "database is locked".
**Changes:**
- `storage.py` `Storage.__init__`: open with `timeout=30`, `PRAGMA journal_mode=WAL`
  + `PRAGMA busy_timeout=30000`. WAL lets one reader + one writer proceed
  concurrently; busy_timeout backs the rarer writer/writer overlap.
- `.gitignore`: ignore the new `*.db-wal` / `*.db-shm` sidecars.
- `tests/test_indicators.py`: assert Storage opens in WAL with a busy_timeout.
**Verify:** `make verify` green (97/97 + smoke). Live DB confirmed `journal_mode=wal`;
listener restarted on new code (PID 54739); WAL sidecars present and gitignored.
**Notes:** WAL is persistent in the DB header; needs local disk (it's on the Mac's
local FS). No schema change.

## 2026-06-08 — Initialize local git + commit-per-prompt convention · Claude
**Why:** Two agents now edit the same files; git gives real diffs/blame/rollback
that a hand-maintained log can't. Human approved adopting it.
**Changes:**
- `git init` (branch `main`, no remote); initial commit of the full tree.
- `.gitignore`: also ignore `.claude/settings.local.json` (machine-local).
- New convention in `AGENTS.md`/`CLAUDE.md`: end every change-making prompt with one
  commit, `make verify` green, no secrets/artifacts, on `main`, no push without approval.
- `DECISIONS.md`: superseded the two "no git" decisions; added the adoption decision.
  `ROADMAP.md`: dropped the "evaluate git" item.
**Verify:** `make verify` green; `git status` clean post-commit; confirmed `.env`,
`*.db`, logs, `.venv`, `.claude/settings.local.json` are untracked.
**Notes:** local-only; adding a remote/push needs explicit human approval (DECISIONS).

## 2026-06-07 — Fix NaN crash in alert render (DataFrame self-tune) · Claude
**Why:** The registry refactor's `_apply_live_edge_adjustments` creates
`track_record`/`conviction_base` columns via `df.at`, leaving NaN on rows without
a value. Once 7d live outcomes accrue, `_tg_card` joins a NaN float →
`TypeError: expected str, got float` → every alert send would crash silently.
**Changes:**
- `formatting._tg_card`: guard `track_record` + `conviction_base` with `_present`
  (rejects None *and* NaN).
- `scanner._apply_live_edge_adjustments`: pre-create both columns as object/None so
  unset rows stay None, not NaN (also keeps the bot snapshot JSON clean).
- `tests/test_indicators.py`: render-guard + end-to-end (apply→build_message→render)
  regression tests.
**Verify:** reproduced the crash with forced 7d stats, confirmed fixed; suite green.
**Notes:** Codex's later `alert_smoke.py` (DOGE NaN fixture) independently backstops
this at the render layer.

## 2026-06-07 — Add alert render smoke test · Codex
**Why:** Alert rendering has become a critical path with rich Telegram HTML,
plain-text fallbacks, macro headers, digest caps, track-record annotations, and
NaN-prone DataFrame enrichment. A signal-math test can pass while a notification
render still crashes or produces invalid Telegram markup.
**Changes:**
- New `crypto_rsi_scanner/alert_smoke.py` builds representative instant/digest
  payloads and validates Telegram HTML tags, message lengths, digest group caps,
  NaN/unsafe substring leaks, and plain fallback truncation behavior without
  sending network notifications.
- `Makefile` adds `make smoke-alerts` and includes it in `make verify`.
- `formatting.py` now escapes quotes in chart-link `href` attributes.
- `tests/test_indicators.py` adds the smoke suite test and a direct regression
  test for quoted symbols in chart links.
- `AGENTS.md` and `DECISIONS.md` document alert-render smoke as part of standard
  verification.
**Verify:** `.venv/bin/python -m crypto_rsi_scanner.alert_smoke` passes. `.venv/bin/python tests/test_indicators.py`
passes 96/96. `make verify` passes: tests 96/96, alert render smoke, and paper
scoreboard.
**Notes/risks:** The smoke is fixture-based and no-send/no-network; it catches
render regressions but does not validate Telegram API delivery.

## 2026-06-07 — Add backtest-to-registry calibration path · Codex
**Why:** Registry priors were still hand-coded from qualitative backtest findings.
The system needed a repeatable way to turn backtest evidence into reviewable
runtime priors without silently changing live alerts after a noisy smoke run.
**Changes:**
- `crypto_rsi_scanner/backtest.py` adds pure calibration/export helpers plus
  `--export-priors PATH` and `--prior-min-samples`. The export JSON includes run
  metadata, setup priors, default priors, and setup x market-regime evidence.
- Calibration is conservative: it starts from current registry priors, moves only
  sample-backed setup x market cells, clamps swings, and keeps `breakdown_risk`
  context-only even if a short sample shows apparent edge.
- `crypto_rsi_scanner/signal_registry.py` can load explicit JSON overrides from
  `RSI_REGISTRY_PRIORS`, validates schema/values, resolves relative paths against
  the project root, and falls back to checked-in defaults on missing/invalid
  calibration.
- `tests/test_indicators.py` adds deterministic tests for explicit override
  loading and evidence-driven prior calibration.
- `AGENTS.md`, `ROADMAP.md`, `DECISIONS.md`, and `.env.example` document the
  calibration workflow and opt-in policy.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 94/94. `make verify`
passes: tests 94/94 and paper scoreboard runs. Smoke export passes:
`.venv/bin/python -m crypto_rsi_scanner.backtest --top-n 5 --days 365 --export-priors /tmp/rsi_registry_priors_smoke_topn.json`
with 5 usable coins and 63 graded observations; exported JSON reloads through
`signal_registry.load_prior_overrides`.
**Notes/risks:** The smoke artifact is intentionally not enabled live; it is only
a CLI/schema check. Use a stronger PIT or longer-history run before setting
`RSI_REGISTRY_PRIORS` in `.env`.

## 2026-06-07 — Add shared universe hygiene filters · Codex
**Why:** CoinGecko top market-cap lists include stablecoins, wrapped/staked
receipts, stale/suspicious listings, and low-liquidity artifacts that pollute
alerts, outcomes, paper trades, and backtests.
**Changes:**
- New `crypto_rsi_scanner/universe.py` with pure filters for stable-like assets,
  wrapped/staked/synthetic derivatives, invalid market data, low volume/market
  cap, and suspicious 24h moves.
- `scanner.py` now overfetches CoinGecko candidates, applies shared hygiene, logs
  exclusion reason counts, and scans the first clean requested top-N.
- `backtest.py` uses the same hygiene for CoinGecko top-N/PIT candidate
  selection.
- `config.py` adds universe hygiene tunables and removes `stx` from hard symbol
  excludes so Stacks is not accidentally filtered.
- `.env.example`, `AGENTS.md`, `ROADMAP.md`, and `DECISIONS.md` document the new
  shared universe policy.
- Tests added for stable/wrapped/low-liquidity/suspicious exclusions, overfetch
  capping, and the `STX` false-positive case.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 92/92. `make verify`
passes. Backtest smoke check passes:
`.venv/bin/python -m crypto_rsi_scanner.backtest --top-n 5 --days 365`.
Live dry-run passes: `.venv/bin/python main.py --dry-run --top-n 5` fetched 55
candidates, excluded 2 stable-like entries, and scanned 5 clean coins.
**Notes/risks:** Filters are conservative and log reason counts; review live
logs for false positives/negatives before tightening further.

## 2026-06-07 — Backfill NaN-safe live-edge rendering fix · Codex
**Why:** Claude fixed a latent alert-rendering regression after the DataFrame
self-tune refactor, but stopped before logging it. Without the fix, rows without
track-record history could carry `NaN` into Telegram card rendering once live
7-day outcomes accrue.
**Changes:**
- `scanner.py` pre-creates `track_record` and `conviction_base` as object/`None`
  columns before live-edge enrichment, avoiding NaN-filled columns for unmatched
  rows.
- `formatting.py` guards `track_record` and `conviction_base` with `_present()`
  before rendering, so `None`/NaN values do not crash or leak into alerts.
- `tests/test_indicators.py` adds regression tests for direct Telegram card
  rendering and the apply/build/render path.
**Verify:** `make verify` passes: standalone tests 89/89 and paper scoreboard runs.
**Notes/risks:** This is a DEVLOG backfill of Claude's fix, not a new behavioral
change by Codex.

## 2026-06-07 — Add signal registry and edge-prior conviction · Codex
**Why:** Setup intent, market eligibility, and conviction priors were spread
across modules, and conviction still leaned too heavily on fixed severity
weights despite backtest findings.
**Changes:**
- New `crypto_rsi_scanner/signal_registry.py` as the canonical source for setup
  definitions, expected directions, market alignment, and edge-prior conviction
  baselines.
- `indicators.py` now delegates setup/market helpers to the registry and blends
  registry edge priors with severity/confluence in `conviction_score`.
- `scanner.py` uses registry-based conviction directly and applies mature live
  outcome self-tuning before printing, saving CSV/DB rows, snapshots, and alerts.
- `backtest.py`, `outcomes.py`, `paper.py`, `formatting.py`, and `storage.py`
  now consume registry definitions instead of duplicated/private setup maps.
- Tests added for registry coverage, backtest market aliases, and edge-prior
  conviction ordering.
- Updated `AGENTS.md`, `ROADMAP.md`, `DECISIONS.md`, and `config.py` comments to
  reflect the new source of truth.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 87/87. `make verify`
passes: tests 87/87 and paper scoreboard runs. Backtest smoke check passes:
`.venv/bin/python -m crypto_rsi_scanner.backtest --symbols BTC,ETH,SOL --days 365`.
**Notes/risks:** Registry priors encode the current qualitative backtest findings;
`ROADMAP.md` keeps numeric recalibration with stronger PIT/live evidence as a
future task.

## 2026-06-07 — Add roadmap, decisions log, and verify command · Codex
**Why:** The collaboration protocol had a history file, but no single place for
pending work, durable accepted/rejected decisions, or a standard verification
command.
**Changes:**
- New `ROADMAP.md` for live pending work, statuses, and priorities.
- New `DECISIONS.md` for durable technical decisions and revisit conditions.
- New `Makefile` with `make verify`, `make test`, `make score`, `make report`,
  and `make dry-run`.
- Updated `AGENTS.md` and `CLAUDE.md` to point both agents at the new files and
  standard verification path.
**Verify:** `make verify` passes: standalone tests 85/85, paper scoreboard runs.
**Notes/risks:** Did not initialize local git; `DECISIONS.md` records that agents
should wait for explicit human approval before changing the repo workflow.

## 2026-06-07 — Add shared AI-collaboration system (AGENTS.md + DEVLOG.md) · Claude
**Why:** Owner is now co-developing with Codex; we need a shared protocol + change
history (no git repo to lean on).
**Changes:**
- New `AGENTS.md` (shared brain: run/test/deploy, architecture, conventions,
  strategy findings, the "log every change" rule).
- New `DEVLOG.md` (this file) with template + backfilled session history.
- New `CLAUDE.md` (thin pointer so Claude Code follows AGENTS.md/DEVLOG).
**Verify:** docs only; `tests/test_indicators.py` still 85/85.
**Notes:** Codex reads `AGENTS.md` natively; Claude reads `CLAUDE.md` → both land here.

## 2026-06-07 — Confirmation entry trigger: A/B'd, REJECTED (backtest only) · Claude
**Why:** Test whether entering when RSI turns back *out* of the OB/OS zone beats
piercing *into* it (catching the knife).
**Changes:** `backtest.py` — `trigger` param on `walk_coin` (cross_into|confirm via
zone-state), `_fetch_all`/`_walk_all` refactor, `run_triggers`, `--trigger` /
`--compare-triggers`, `format_trigger_comparison`. Test added.
**Verify:** 5y/38-coin A/B: actionable book @7d ~identical (52%/+0.0% vs 51%/−0.0%);
confirm slightly hurts dip_buy & mean_reversion. **Live scanner UNCHANGED.**
**Notes/risks:** Negative result — don't re-add confirmation without new evidence.
Tooling kept for future variant A/Bs. Aggregate live edge is thin & regime-specific.

## 2026-06-07 — Paper-trade scoreboard · Claude
**Why:** Honest live proof of whether the (gated) signals make money.
**Changes:** new `paper.py`; `storage.py` `paper_trades` table + accessors;
`scanner.run` opens/closes trades each scan; `--score` CLI + `/score` bot command;
`config.PAPER_*`. Opens a virtual long/short per new crossing, closes after 7d at
that day's close (reuses fetched prices). Report: **actionable vs control book**,
by setup, by market regime.
**Verify:** 84→ tests pass; live `--score` works; synthetic demo shows the split.
**Notes:** Empty until ~7d of live scans mature trades. 1 unit/trade, horizon exit,
overlap-ignored equity (stated in the report).

## 2026-06-07 — Live market-regime gating · Claude
**Why:** Backtest showed edge is regime-conditional; gate each setup to its
favorable BTC regime.
**Changes:** `indicators.market_alignment` / `market_conviction_adjustment` /
`setup_has_edge` + edge map; `scanner` computes `trend_regime(BTC)` per scan, folds
alignment into conviction (±`MARKET_ALIGN_SWING`=12), `classify_tier` demotes
adverse non-extreme to DIGEST; `formatting` adds 🧭 market line + mutes
breakdown_risk direction; `storage` persists `market_regime`; `RSI_MARKET_GATING`.
**Verify:** 80 tests; dry-run showed BTC=DOWNTREND → adverse setups held to digest,
0 INSTANT.
**Notes:** edge map: mean_reversion→CHOP, dip_buy/trend_continuation→BULL,
breakdown_risk→never.

## 2026-06-07 — Backtester: deeper history + market-regime split · Claude
**Why:** 2y window was one regime (missed the 2022 bear); must separate bull/bear.
**Changes:** `backtest.py` — paginated Binance fetch (5y), `market_regime_series`
(BTC bull/bear/chop), `summarize_market`/`format_market`, default `--days 1460`.
**Verify:** 5y/39-coin run; balanced coverage (BULL 22k / BEAR 15.7k / CHOP 8.7k).
**Notes:** KEY FINDING — blended averages hid regime-conditional edge (see AGENTS.md).

## 2026-06-07 — Backtester: point-in-time universe (survivorship fix) · Claude
**Why:** Using today's top-N over history is survivorship-biased.
**Changes:** `backtest.py` — `--pit`/`--pool`, CoinGecko market-cap history,
`build_pit_membership` (per-date top-N), `walk_coin` `member` mask gates
signals+base.
**Verify:** PIT run (114 coins, 365d). Confirmed breakdown_risk's "bounce" was
survivorship-inflated (~0 under PIT).
**Notes:** demo CoinGecko key caps history at 365d → small samples; pro key extends.

## 2026-06-07 — Backtester: conditional vol/momentum slice · Claude
**Why:** Does oversold-in-downtrend only continue down in high-vol crashes?
**Changes:** `backtest.py` — per-day vol/momentum features, `conditional_table`
(terciles, base conditioned on same bucket), `--slice`.
**Verify:** breakdown_risk bounces MORE in high vol — crash-continuation hypothesis
refuted.

## 2026-06-07 — Backtester: initial build · Claude
**Why:** Validate signal edge over years, not the ~1 week of live data.
**Changes:** new `backtest.py` — replays the pure functions over Binance 1d klines,
grades each setup vs its regime base rate (anti-tautology benchmark). Use
`data-api.binance.vision` (api.binance.com 451s from MSK).
**Verify:** first run overturned the live read — breakdown_risk "98%" was the
tautology trap; real edge in dip_buy/mean_reversion.

## 2026-06-07 — Split signal intent (setup_type) + re-grade history · Claude
**Why:** `favorable` was hardcoded mean-reversion, mislabeling continuation setups.
**Changes:** `indicators.setup_for` + `_SETUP_MAP`; `scanner` stamps
setup_type/expected_dir; `outcomes.favorable(expected_dir,…)` + setup-keyed
reports; `storage` columns + one-time lossless re-grade (meta `setup_regrade_v1`);
`formatting`/`telegram` show the setup hypothesis.
**Verify:** 61→65 tests; re-graded 197 historical outcomes losslessly.

## 2026-06-07 — Ops fixes: bot.log spam, token leak, dead return · Claude
**Why:** Listener spammed ~18k identical DNS errors (with the bot token in the URL);
`telegram.listen()` had an unreachable `return added` (NameError on Ctrl-C).
**Changes:** `telegram.py` — `_Unreachable` for transient net errors, once-per-outage
log + exponential backoff, removed dead `return`; `config.redact_token`;
`notifications.py` scrubs token in logs.
**Verify:** 61 tests; listener restarted clean; truncated the 6.8MB bot.log.
