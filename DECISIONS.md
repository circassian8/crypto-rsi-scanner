# DECISIONS

Durable project decisions live here so agents do not relitigate settled choices.
Use `DEVLOG.md` for chronological change details and this file for the lasting
decision, rationale, and revisit condition.

## Template

```
## YYYY-MM-DD - <decision title>
**Status:** accepted | rejected | superseded
**Decision:** what we will or will not do.
**Why:** concise rationale.
**Revisit when:** concrete condition for reopening. Optional.
```

---

## 2026-06-07 - Use DEVLOG as history while repo has no git
**Status:** superseded 2026-06-08 (see "Adopt local git + commit per change-making prompt")
**Decision:** Every non-trivial change must prepend an entry to `DEVLOG.md`,
signed by `Claude`, `Codex`, or `human`.
**Why:** There is no `.git` directory, so the written log is the shared history
for the human and AI collaborators.
**Revisit when:** The human explicitly initializes a git repo and decides how
commit history and `DEVLOG.md` should coexist.

## 2026-06-08 - Adopt local git + commit per change-making prompt
**Status:** accepted
**Decision:** The repo is a local git repo (branch `main`, no remote). Every prompt
that changes files ends with one commit (clear message, `make verify` green, no
secrets/artifacts). `DEVLOG.md` continues as the narrative/why log; git is the
diff/rollback history. No `git push` / remote without explicit human approval.
**Why:** Two agents edit the same files; git gives real diffs, blame, and rollback
a hand-maintained log can't. Human explicitly approved.

## 2026-06-07 - Do not initialize local git automatically
**Status:** superseded 2026-06-08 (human approved git; see above)
**Decision:** Agents may recommend local git, but must not run `git init` unless
the human explicitly asks for it.
**Why:** The current collaboration protocol is built around "no git"; changing
that workflow affects backups, diffs, and agent expectations.
**Revisit when:** The human asks to adopt local git.

## 2026-06-07 - Use the repo venv and standalone test runner
**Status:** accepted
**Decision:** Primary verification is `.venv/bin/python tests/test_indicators.py`
or `make verify`, not plain `python` or `pytest`.
**Why:** The shell's default Python can stall importing pandas here, and `pytest`
is not installed in the repo venv.
**Revisit when:** Dev dependencies include pytest and the default interpreter is
known-good.

## 2026-06-07 - Grade setups by their expected direction
**Status:** accepted
**Decision:** Outcomes are graded against each setup's `expected_dir`, not a
blanket mean-reversion convention.
**Why:** Overbought/oversold signals mean different things across trend regimes;
continuation setups were previously mislabeled.

## 2026-06-07 - Gate signal loudness by market regime
**Status:** accepted
**Decision:** Use BTC market-regime alignment to adjust conviction and demote
adverse setups out of loud routing.
**Why:** Backtests showed edge is regime-conditional; the useful part is firing
setups only in favorable regimes.

## 2026-06-07 - Keep breakdown_risk context-only
**Status:** accepted
**Decision:** `breakdown_risk` is shown as context but should not go loud or be
treated as an actionable edge.
**Why:** Backtests did not find positive edge for oversold-in-downtrend in any
market regime.
**Revisit when:** A materially better PIT backtest or live paper sample shows
positive edge.

## 2026-06-07 - Reject confirmation entry trigger for now
**Status:** rejected
**Decision:** Do not switch live entries from cross-into-zone to RSI confirmation
out of the zone.
**Why:** A/B backtest did not improve results and slightly hurt key setups.
**Revisit when:** A new trigger variant is specified and backtested against the
current baseline.

## 2026-06-07 - Signal registry is the setup source of truth
**Status:** accepted
**Decision:** `crypto_rsi_scanner/signal_registry.py` owns setup definitions,
expected directions, market eligibility, and backtested conviction priors.
Scanner, backtest, outcomes, paper trading, formatting, and storage migrations
should consume the registry instead of maintaining private setup maps.
**Why:** The same setup logic was spread across modules, making it easy for live
alerts, backtests, and reports to drift.
**Revisit when:** A richer registry schema is needed, but keep one source of
truth.

## 2026-06-07 - Conviction starts from measured edge priors
**Status:** accepted
**Decision:** Live and backtest conviction should start from registry edge priors
by setup and market alignment, with severity/confluence and mature live outcomes
nudging around that baseline.
**Why:** The old fixed severity-first heuristic did not predict edge in backtest.
This makes conviction answer "does this setup have measured edge here?" before
asking how visually stretched the coin is.
**Revisit when:** The paper scoreboard or stronger PIT backtests show the priors
need recalibration.

## 2026-06-07 - Registry calibration is explicit opt-in
**Status:** accepted
**Decision:** Backtest may export calibrated registry priors as JSON, but the
live scanner only loads them when `RSI_REGISTRY_PRIORS` points to that file.
Absent or invalid calibration falls back to checked-in registry defaults.
**Why:** Smoke runs and short-window backtests can produce noisy priors. The
artifact should be reviewable and intentional before affecting live alerts.
**Revisit when:** A routine calibration workflow with enough PIT/live evidence is
trusted enough to automate.

## 2026-06-07 - Keep alert render smoke in verification
**Status:** accepted
**Decision:** Representative alert rendering must be smoke-tested offline via
`make smoke-alerts`, and `make verify` runs that target.
**Why:** Render regressions can block notifications even when signal math passes;
the formatter needs coverage for Telegram HTML, plain fallback, macro headers,
digest caps, NaN handling, and edge-case symbols.
**Revisit when:** Rendering moves to a richer template/parser with equivalent
coverage.

## 2026-06-08 - Persist and expose scan health
**Status:** accepted
**Decision:** Live scans persist their latest operational status in SQLite meta,
and both `main.py --status` and the bot `/health` command render it through the
shared `status_report.py` formatter. The always-on listener also checks stale
successful scans and raises a heartbeat alert once per stale episode.
**Why:** A correct signal engine is not enough if the launchd scan silently stops,
degrades, or fails after fetching. One shared status source gives CLI, bot, and
watchdog paths the same view of scan freshness and last errors.
**Revisit when:** We add richer historical run tables or external monitoring.

## 2026-06-08 - Use SQLite online backup API
**Status:** accepted
**Decision:** DB backups must use SQLite's online backup API, verify the resulting
backup with `PRAGMA integrity_check`, and apply retention. Do not back up by
copying only `rsi_scanner.db`.
**Why:** The live DB runs in WAL mode and can have active scan/listener
connections; raw file copies can miss WAL contents or capture an inconsistent
state.
**Revisit when:** We move state storage away from local SQLite.

## 2026-06-08 - Keep ops maintenance repo-owned but schedule changes explicit
**Status:** superseded 2026-06-08 (human asked to do all suggested changes)
**Decision:** `main.py --status` reports backup freshness and log sizes;
`main.py --rotate-logs` copy-truncates oversized local logs; launchd helpers can
inspect scan/listener status and restart the bot listener by label. Agents should
not install or mutate launchd schedules/plists unless the human explicitly asks.
**Why:** The live Mac needs simple recovery/inspection commands, but changing
service schedules is machine state outside the repo and should remain deliberate.
**Revisit when:** The human wants a checked-in or installed maintenance
LaunchAgent for backups/log rotation.

## 2026-06-08 - Install daily repo-owned maintenance agent
**Status:** accepted
**Decision:** The repo owns `main.py --maintenance`, which creates a safe SQLite
backup, restore-checks it, and rotates logs. `make install-maintenance-agent`
installs/loads a daily launchd agent (`RSI_MAINTENANCE_LABEL`, default
`com.nasrenkaraf.rsimaintenance`) that runs this command.
**Why:** Backups and log rotation are operational controls, not one-off manual
commands. The human explicitly asked to do the scheduled-maintenance item.
**Revisit when:** Maintenance should move to an external scheduler/monitoring
system or the Mac deployment labels change.

## 2026-06-08 - Keep offline scanner fixture smoke checked in
**Status:** accepted
**Decision:** `RSI_FIXTURE_DIR` enables CoinGecko fixture mode, and
`make dry-run-fixture` uses checked-in sanitized fixtures under
`fixtures/coingecko_smoke`.
**Why:** Scanner plumbing can be validated quickly without spending API quota or
waiting on network/rate-limit behavior.
**Revisit when:** The fixture diverges from live API response shape or needs to
cover more signal cases.

## 2026-06-09 - Keep offline backtest fixture smoke in verification
**Status:** accepted
**Decision:** `make backtest-fixture` runs the default Binance-style backtest
path against checked-in BTC/ETH/SOL daily kline CSVs under
`fixtures/backtest_smoke`, and `make verify` includes that target.
**Why:** The backtester had strong unit coverage, but its CLI/default data path
still depended on Binance/network for a smoke run. A small fixture catches
parser, CLI, report, market-regime, and signal-walk regressions locally.
**Revisit when:** The fixture stops producing representative graded observations
or the default research data source changes.

## 2026-06-08 - Add market-state features shadow-first
**Status:** accepted
**Decision:** Keep RSI crossing/approach as the event trigger. New volatility,
breadth, relative-strength, beta, liquidity, and risk-state features must be
computed as pure, backtestable state context before any live conviction, routing,
or hard-gating change.
**Why:** The likely edge is RSI conditioned on market state, not generic indicator
stacking. Shadow-first features avoid silently overfitting live alert behavior.
**Revisit when:** PIT/base-rate-adjusted, cost-aware, walk-forward evidence
supports a specific state feature affecting conviction or routing.

## 2026-06-08 - Store live state snapshots observationally
**Status:** accepted
**Decision:** The live scanner may attach `state_json` and compact state buckets
to rows, alerts, signals, and paper-trade entries, but it must attach them after
`flag`, `setup_type`, `expected_dir`, `market_aligned`, `conviction`, and `tier`
are already computed.
**Why:** We need live/backtestable state labels to measure conditional edge, but
state features are not yet proven enough to affect alert routing or score.
**Revisit when:** State-conditioned PIT/live outcome analysis identifies a
specific feature/cohort with durable incremental edge over the existing registry
baseline.

## 2026-06-09 - Grade state slices against same-state base rates
**Status:** accepted
**Decision:** State-conditioned backtest slices must compare each signal cohort
against base days with the same coin trend regime and the same state bucket.
**Why:** High-volatility, breadth-collapse, or low-RS markets can have strong
base moves on their own. A state bucket only matters if the RSI setup beats what
normally happened in that same state.
**Revisit when:** A better causal/econometric benchmark replaces the current
same-regime, same-state base-rate comparison.

## 2026-06-09 - Do not promote first state-slice candidates live
**Status:** accepted
**Decision:** The 2026-06-09 current-top Binance state-slice review is research
evidence only. Do not alter live conviction, routing, or gating from it alone.
**Why:** The run found plausible cohorts, but it remains survivorship-biased,
single-venue, costless, and some cells are small. State buckets need PIT/live
confirmation before they can affect alerts.
**Revisit when:** Point-in-time state-slice backtests or mature live `state_json`
outcomes confirm a specific cohort with enough samples and positive incremental
edge over the same-regime, same-state base rate.

## 2026-06-09 - Cache raw PIT CoinGecko histories
**Status:** accepted
**Decision:** PIT backtests cache raw CoinGecko `market_chart` JSON under the
configured `RSI_BACKTEST_CACHE_DIR` (`backtest_cache` by default), and research
commands can disable or refresh that cache explicitly.
**Why:** PIT state-slice and calibration runs are rate-limit sensitive and can be
interrupted. Caching raw inputs lets runs resume and keeps derived parsing/report
logic reproducible without checking bulky data into git.
**Revisit when:** A better historical market-cap data source replaces CoinGecko
or the cache needs versioned schema metadata.

## 2026-06-09 - Treat first cached PIT state-slice run as bear-only evidence
**Status:** accepted
**Decision:** The cached 365d PIT state-slice run confirms only bear-regime
conditions. It supports continued monitoring of bear-regime `mean_reversion` and
continued rejection of `breakdown_risk`, but it does not justify live state
routing changes.
**Why:** The run used point-in-time membership and 128 usable histories, but the
available 365d CoinGecko window only produced BTC `BEAR` market-regime coverage.
Bull/chop state candidates from the 4-year Binance run remain unconfirmed.
**Revisit when:** Deeper PIT history includes bull/chop periods or live
`state_json` outcomes mature enough to test those cohorts directly.

## 2026-06-09 - Do not load the first PIT registry-prior export live
**Status:** accepted
**Decision:** `research/registry_priors_pit_2026-06-09.json` is a checked-in
research artifact only. Do not set `RSI_REGISTRY_PRIORS` to it for live scans.
**Why:** The 365d point-in-time run had only BTC `BEAR` market coverage. It moved
`mean_reversion.neutral` from 42 to 47 and `trend_continuation.neutral` from 42
to 40, but those neutral prior cells are broader than this bear-only evidence.
**Revisit when:** PIT history includes bull/chop coverage or mature live paper
outcomes validate setup-by-market prior cells directly.

## 2026-06-07 - Share universe hygiene across live and research
**Status:** accepted
**Decision:** `crypto_rsi_scanner/universe.py` owns CoinGecko market hygiene and
must be used by live scans and backtest top-N selection. Live scans also persist
the latest hygiene audit for review.
**Why:** Stablecoins, wrapped/staked receipts, stale listings, and illiquid
market-cap artifacts pollute alerts, outcomes, paper trades, and backtests.
Using one filter and persisted audit keeps live and research universes aligned
and makes false positives/negatives reviewable.
**Revisit when:** Logs show repeated false positives/negatives, or CoinGecko
metadata support allows a more precise category-based filter.

## 2026-06-09 - Exclude fiat, gold, and yield-pegged products from RSI universe
**Status:** accepted
**Decision:** Treat observed fiat/gold/yield-pegged products such as USD1, USDG,
USDtb, GHO, YLDS, USX, USYC, XAUT, and PAXG as `stable_like` universe
exclusions.
**Why:** The 2026-06-09 live hygiene audit showed these products surviving into
the kept top-100 even though they are not good directional crypto RSI candidates.
They add noise to alerts, paper trades, and backtests.
**Revisit when:** The audit shows a repeated legitimate asset being excluded by
these rules, or CoinGecko exposes reliable categories for stable/commodity/yield
products.

## 2026-06-09 - Refresh universe audits without full scans
**Status:** accepted
**Decision:** `main.py --refresh-universe-audit` and `make refresh-universe-audit`
may fetch the current CoinGecko market list, apply shared hygiene filters,
persist the audit, and print it without running RSI analysis or notifications.
**Why:** Hygiene tuning needs fast feedback. A full scan spends more API calls,
touches scanner bookkeeping, and performs unrelated RSI work when only the
market-list filter changed.
**Revisit when:** CoinGecko rate limits make even market-list-only refreshes too
expensive or audit persistence moves out of local SQLite/files.

## 2026-06-09 - Keep cost and walk-forward outputs research-only
**Status:** accepted
**Decision:** Backtest `--costs` and `--walk-forward` reports are required
research diagnostics before promoting a calibration, but they do not alter live
conviction, routing, or gating by themselves.
**Why:** Costs, slippage, capacity, and temporal stability can invalidate a thin
headline edge. They should be visible in research output without silently
changing live behavior.
**Revisit when:** A specific cost-aware, walk-forward-supported rule is proposed
and documented for live promotion.

## 2026-06-09 - Mark notification state only after delivery
**Status:** accepted
**Decision:** Instant cooldowns and digest timestamps are updated only after at
least one notification channel reports success. Telegram alerts should be split
into multiple messages when needed instead of silently truncating cards.
**Why:** A transient Telegram/API failure should not suppress the next retry, and
large alert batches should not drop later cards while appearing delivered.
**Revisit when:** Delivery moves to an external queue with acknowledgements.

## 2026-06-09 - Keep live outcome maturation independent of today's universe
**Status:** accepted
**Decision:** Recent pending signal outcomes and open paper trades may fetch
extra daily histories for coins that are no longer in today's clean top-N
universe. Live outcome reports include actionable/control and market-alignment
cohorts, deriving alignment for older rows when needed.
**Why:** Gating and conviction cannot be judged honestly if outcomes disappear
when a coin leaves the current universe. The report needs to answer whether
surfaced signals beat the control set directly.
**Revisit when:** Outcome tracking moves to a provider-backed historical data
store or a dedicated run/outcome table with complete lifecycle states.

## 2026-06-07 - Do not exclude STX by symbol
**Status:** accepted
**Decision:** `stx` is not in the hard exclude list.
**Why:** Symbol-only filtering treated Stacks like a staked/wrapped receipt, but
it is a normal asset and should pass unless another hygiene rule excludes it.

## 2026-06-10 - Volume-rank PIT is the standard full-cycle research universe
**Status:** accepted
**Decision:** Conclusion-bearing backtest research uses `backtest --pit-volume`
(per-date top-N by trailing 30d dollar volume over the full Binance USDT pool).
The plain current-top Binance path is for quick smokes only; the CoinGecko mcap
`--pit` path remains as a cross-check (365d on the demo key).
**Why:** It is the only path that is simultaneously full-cycle (~5y, covering
bull/chop/bear) and point-in-time, with free, cacheable data. The 2026-06-10 run
(368 coins, 21,334 obs) confirmed the gating map and first validated conviction
monotonicity. Known residual biases (delisted pairs absent, single venue,
volume-rank ≠ live mcap universe) are documented in
`research/VOLUME_PIT_BACKTEST_2026-06-10.md`.
**Revisit when:** A historical market-cap source (Pro key or alternative) allows
a deep mcap-PIT comparison, or multi-venue data becomes available.
