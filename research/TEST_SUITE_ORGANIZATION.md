# Test Suite Organization

Date: 2026-07-02

This document records the pytest-compatible split of the historical
`tests/test_indicators.py` standalone runner.

## Current Layout

| path | role |
|---|---|
| `tests/test_indicators.py` | Umbrella compatibility runner plus remaining ops/config/storage tests. Running it directly still executes the split Event Alpha, RSI, and CLI packages. |
| `tests/rsi/test_indicators_core.py` | Pure RSI math, scanner scoring, setup/tier/regime, state features, and universe hygiene tests. |
| `tests/rsi/test_backtest.py` | Backtest edge, state-slice, PIT/volume membership, cache, fixture-loader, and CLI-argument regressions. |
| `tests/rsi/test_paper_risk.py` | Outcome grading, paper scoreboard, refresh-paper, and risk/rendering guard tests. |
| `tests/cli/test_parser.py` | Parser snapshots, command classification, CLI help smoke, and dispatch smoke with patched handlers. |
| `tests/cli/test_make_targets.py` | Makefile, export archive, CI workflow, architecture baseline, and split-target static checks. |
| `tests/event_alpha/` | Event Alpha artifact, radar, notification, provider readiness, source coverage, namespace lifecycle, and outcome tests split into focused package homes. |

## Commands

| command | purpose |
|---|---|
| `python3 tests/test_indicators.py` | Historical standalone runner; no pytest dependency required. |
| `python3 -m pytest tests/rsi tests/cli tests/event_alpha` | Focused pytest-compatible split suite. |
| `make test-rsi PYTHON=python3` | Run `tests/rsi`. |
| `make test-cli PYTHON=python3` | Run `tests/cli`. |
| `make test-event-alpha PYTHON=python3` | Run `tests/event_alpha`. |
| `make test-pytest PYTHON=python3` | Run the full pytest-compatible suite when pytest is installed. |
| `make test-pytest-parallel PYTHON=python3` | Run pytest with xdist when installed; otherwise print a friendly skip message. |

## Size Gate

Before this pass, `tests/test_indicators.py` was 4,987 lines after the Event
Alpha split. It is now 1,770 lines and reports these standalone counts:

| count | value |
|---|---:|
| standalone_tests | 717 |
| event_alpha_tests | 559 |
| rsi_tests | 97 |
| cli_tests | 17 |
| umbrella_tests | 44 |

The architecture baseline final-phase gate for `tests/test_indicators.py` is below
2,000 lines, so the umbrella runner now satisfies that size target.

## Remaining Umbrella Sections

The remaining local tests in `tests/test_indicators.py` are intentionally left
in place for a later, narrower pass:

- Config and dotenv parsing.
- Storage, subscriber, Telegram formatting, bot command, and heartbeat tests.
- Backup, restore drill, status, log rotation, launchd, and maintenance helper tests.
- CoinGecko fixture-client and SQLite WAL/busy-timeout checks.
- Historical helper definitions that are still useful for standalone compatibility
  until the ops/storage packages receive focused pytest homes.

Future splits should move these into `tests/config/`, `tests/storage/`,
`tests/telegram/`, and `tests/ops/` while keeping the direct standalone command
compatible.
