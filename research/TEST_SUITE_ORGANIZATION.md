# Test Suite Organization

Date: 2026-07-10

This document records the pytest-compatible split of the historical
`tests/test_indicators.py` standalone runner.

## Current Layout

| path | role |
|---|---|
| `tests/test_indicators.py` | Umbrella compatibility runner plus remaining ops/config/storage tests. Running it directly still executes the split Event Alpha, RSI, and CLI packages. |
| `tests/rsi/test_backups.py` | SQLite online-backup, immutable restore, retention, debris visibility, and backup-status regressions. |
| `tests/rsi/test_indicators_core.py` | Pure RSI math, scanner scoring, setup/tier/regime, state features, and universe hygiene tests. |
| `tests/rsi/test_backtest.py` | Backtest edge, state-slice, PIT/volume membership, cache, fixture-loader, and CLI-argument regressions. |
| `tests/rsi/test_paper_risk.py` | Outcome grading, paper scoreboard, refresh-paper, and risk/rendering guard tests. |
| `tests/cli/test_parser.py` | Parser snapshots, command classification, CLI help smoke, and dispatch smoke with patched handlers. |
| `tests/cli/test_make_targets.py` | Makefile, export archive, CI workflow, architecture baseline, and split-target static checks. |
| `tests/event_alpha/test_fade_validation.py` | Event-fade sample schema, promotion blockers, provenance, diversity, timing, labeling-queue, and human-evidence regressions. |
| `tests/event_alpha/test_fade_review_workflows.py` | Review sidecars, balanced templates, scanner reports, review bundles, cached workspaces, and merge workflows. |
| `tests/event_alpha/test_catalyst_frames.py` | Catalyst-frame classification, LLM validation/runtime controls, strategic-frame downstream use, e2e artifacts, missing-provider modes, roles, aggregation, and unresolved-frame caps. |
| `tests/event_alpha/test_claim_semantics.py` | Claim extraction, cause-status transitions, asset roles, incident construction, market context, and doctor/card propagation. |
| `tests/event_alpha/test_incident_relevance.py` | Incident relevance gates, raw/external observation isolation, upgrade paths, audit sections, daily briefs, and research cards. |
| `tests/event_alpha/test_core_opportunities.py` | Core-opportunity storage, watchlist promotion, canonical operator grouping, research cards, and opportunity-audit regressions. |
| `tests/event_alpha/test_core_reconciliation.py` | Canonical-core/snapshot reconciliation, diagnostic isolation, audit reconciliation, and daily-brief evidence accounting. |
| `tests/event_alpha/test_operator_identity.py` | Asset knowledge, role validation, identity metadata, live-confirmation caps, and stale source-only normalization. |
| `tests/event_alpha/test_market_surfaces.py` | Market reaction/state/anomaly, official exchange, scheduled catalyst, derivatives, instrument resolution, and integrated-radar surface regressions. |
| `tests/event_alpha/test_llm_radar.py` | LLM relationship analysis, advisory caps, provider timeout/cache/budget behavior, golden evals, raw-event extraction, and scanner-report integration. |
| `tests/event_alpha/` | Event Alpha artifact, radar, notification, provider readiness, source coverage, namespace lifecycle, and outcome tests split into focused package homes. |

## Commands

| command | purpose |
|---|---|
| `python3 tests/test_indicators.py` | Historical standalone runner; no pytest dependency required. |
| `python3 -m pytest tests/rsi tests/cli tests/event_alpha` | Focused pytest-compatible split suite. |
| `make verify PYTHON=python3` | Strict pre-commit/release gate: standalone runner, hard pytest, alert smoke, backtest fixture, and score. |
| `make verify-fast PYTHON=python3` | Faster local loop: hard pytest, alert smoke, backtest fixture, and score without the duplicate standalone runner. |
| `make test-rsi PYTHON=python3` | Run `tests/rsi`. |
| `make test-cli PYTHON=python3` | Run `tests/cli`. |
| `make test-event-alpha PYTHON=python3` | Run `tests/event_alpha`. |
| `make test-pytest PYTHON=python3` | Run the full pytest-compatible suite when pytest is installed. |
| `make test-pytest-safe PYTHON=python3` | Run the full pytest-compatible suite with external plugin autoload disabled. |
| `make test-pytest-durations PYTHON=python3 PYTEST_DURATIONS=50` | Print the slowest safe-pytest tests for profiling. |
| `make test-pytest-parallel PYTHON=python3 PYTEST_WORKERS=4` | Run safe pytest with xdist when installed; otherwise print a friendly skip message. |

`PYTEST_PATHS` defaults to `tests/event_alpha tests/rsi tests/cli
tests/test_indicators.py` so the standalone compatibility runner stays covered
inside pytest while full `make verify` still runs it directly as a separate
release guard.

## Size Gate

After the Event Alpha and base-suite splits, `tests/test_indicators.py` was
1,784 lines immediately before the focused backup-test move. It is now 1,665
lines and reports these standalone counts:

| count | value |
|---|---:|
| standalone_tests | 786 |
| event_alpha_tests | 594 |
| rsi_tests | 109 |
| cli_tests | 42 |
| umbrella_tests | 41 |

The architecture baseline final-phase gate for `tests/test_indicators.py` is below
2,000 lines, so the umbrella runner now satisfies that size target.

Five integrated-radar burn-downs moved 159 tests while preserving each source
surface's exact unique names. `tests/event_alpha/test_integrated_radar.py` fell
from 16,234 to 6,421 lines. The first four extracted modules are 1,282, 786, 461,
and 1,450 lines; the validation/review modules are 1,081 and 1,309 lines; and the
LLM radar module is 942 lines. Claim semantics and incident relevance are 867
and 639 lines; catalyst frames are 1,127 lines. No extracted file is above the
1,500-line architecture warning. The full Event Alpha pytest package currently
collects and passes 650 cases; that count includes parametrization and
package-only modules not represented as direct standalone callables.

## Remaining Umbrella Sections

The remaining local tests in `tests/test_indicators.py` are intentionally left
in place for a later, narrower pass:

- Config and dotenv parsing.
- Storage, subscriber, Telegram formatting, bot command, and heartbeat tests.
- Log rotation, launchd, and remaining maintenance helper tests.
- CoinGecko fixture-client and SQLite WAL/busy-timeout checks.
- Historical helper definitions that are still useful for standalone compatibility
  until the ops/storage packages receive focused pytest homes.

Future splits should move these into `tests/config/`, `tests/storage/`,
`tests/telegram/`, and `tests/ops/` while keeping the direct standalone command
compatible.
