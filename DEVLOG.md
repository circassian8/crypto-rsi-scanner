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
