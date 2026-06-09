# AGENTS.md — working agreement for AI collaborators (Claude + Codex)

This repo is co-developed by a human owner and two AI coding agents (Anthropic
**Claude**, OpenAI **Codex**). **Read this file first, every session.** It is the
shared source of truth for how we work, the architecture, and what we've learned.

> ✅ **This repo is under local git (branch `main`).** Commit at the end of every
> change-making prompt (see "Commit every change"). `DEVLOG.md` remains the
> human-readable narrative/decision history — keep both current.

---

## The one rule: log every change

After any non-trivial change, **prepend an entry to `DEVLOG.md`** using the
template at the top of that file. State *why*, *what files*, and *how you
verified*. No silent changes — the other agent and the human rely on the log to
understand the current state.

Sign your entry with your name (`Claude` / `Codex` / `human`).

## The other rule: commit every change

This is a local git repo. **End any prompt that changed files with one commit**
capturing that prompt's work, with a clear message:
- One logical commit per change-making prompt (don't fold in unrelated prompts).
- Run `make verify` first; don't commit a red tree.
- Never commit secrets/artifacts: `.env`, `*.db`, logs, `.venv`, and
  `.claude/settings.local.json` are gitignored — keep it that way.
- Commit on `main` (personal repo, no remote). No `git push` / remote without
  explicit human approval.

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
  (scan/listener health) · `main.py --universe-audit` (latest hygiene audit)
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
  flags: `--pit` (point-in-time universe, survivorship fix) · `--slice <setup>`
  (vol/momentum slice) · `--compare-triggers` (entry-trigger A/B) ·
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
  baseline. This still needs validation from the paper scoreboard.
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
- **PIT data depth:** `research/PIT_DATA_OPTIONS_2026-06-09.md` documents the
  current 365d demo/free limit and the workflow for rerunning deeper PIT research
  with a Pro key or alternate historical market-cap provider.
- **Confirmation entry trigger** was A/B'd and **rejected** (no improvement) — do
  not re-add without new evidence.
- Caveats: the Binance backtest path is survivorship-biased (today's top-N); the
  `--pit` path fixes that but the demo CoinGecko key caps history at 365d (a pro
  key extends it).

---

## Open next steps

Use `ROADMAP.md` as the live task list. The current high-leverage items are:

1. Let the paper scoreboard accrue ~1–2 weeks; confirm gating helps live.
2. Validate whether edge-prior conviction buckets outperform the old heuristic.
3. Confirm the 2026-06-09 state-slice candidates via cached PIT/live data before any
   live conviction or routing change.
4. Improve PIT history depth further with a Pro CoinGecko key or alternate
   historical market-cap source, then re-run registry-prior calibration.
5. Monitor universe hygiene false positives/negatives and tune thresholds.
6. Use `make dry-run-fixture` before network dry-runs when validating scanner
   plumbing that does not need live CoinGecko data.

When in doubt, read the latest `DEVLOG.md` entries, then ask the human.
