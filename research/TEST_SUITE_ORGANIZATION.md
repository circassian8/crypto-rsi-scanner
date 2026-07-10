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
| `tests/event_alpha/test_fade_core.py` | Pure event-fade scoring/state/trigger/risk behavior plus conservative discovery resolver collision/noise handling. |
| `tests/event_alpha/test_event_alert_ranking.py` | Research alert ranking, proxy-venue opt-in, triggered-fade tier eligibility, cluster/noise caps, playbook tiers, and rejection overrides. |
| `tests/event_alpha/test_exchange_universe_providers.py` | Official exchange/package smoke, manual and CoinGecko universe providers, Binance/Bybit adapters, structured calendars, normalization/dedupe, resolution, and direct-no-trade safety. |
| `tests/event_alpha/test_catalyst_frames.py` | Catalyst-frame classification, LLM validation/runtime controls, strategic-frame downstream use, e2e artifacts, missing-provider modes, roles, aggregation, and unresolved-frame caps. |
| `tests/event_alpha/test_claim_semantics.py` | Claim extraction, cause-status transitions, asset roles, incident construction, market context, and doctor/card propagation. |
| `tests/event_alpha/test_incident_relevance.py` | Incident relevance gates, raw/external observation isolation, upgrade paths, audit sections, daily briefs, and research cards. |
| `tests/event_alpha/test_impact_hypotheses.py` | Hypothesis generation, contextual matching, category refinement, identity-safe impact validation, persistence transitions, verdict policy, watchlist identity, and external-entity exclusion. |
| `tests/event_alpha/test_core_opportunities.py` | Core-opportunity storage, watchlist promotion, canonical operator grouping, research cards, and opportunity-audit regressions. |
| `tests/event_alpha/test_core_reconciliation.py` | Canonical-core/snapshot reconciliation, diagnostic isolation, audit reconciliation, and daily-brief evidence accounting. |
| `tests/event_alpha/test_discovery_cache_reports.py` | Point-in-time cache writes, refresh/run diagnostics, Binance raw listen cache, and scanner reports across exchange/derivatives/supply/news/external/calendar fixtures. |
| `tests/event_alpha/test_discovery_pipeline.py` | LLM hint validation, market fail-soft health, catalyst-search adapters/budgets, candidate identity, asset-role/news safety, external catalysts, prediction markets, and event-fade isolation. |
| `tests/event_alpha/test_operator_identity.py` | Asset knowledge, role validation, identity metadata, live-confirmation caps, and stale source-only normalization. |
| `tests/event_alpha/test_operator_presentation.py` | Integrated fixture lane contract, canonical core grouping, daily-brief sections, card-index grouping/collapse, opportunity audit, and lineage markers. |
| `tests/event_alpha/test_operator_workflows.py` | Digest caps/confirmation, status budgets, monitor/scanner updates, identity/market providers, cards/explain output, no-key target, and review dedupe. |
| `tests/event_alpha/test_market_surfaces.py` | Market reaction/state/anomaly, official exchange, scheduled catalyst, derivatives, instrument resolution, and integrated-radar surface regressions. |
| `tests/event_alpha/test_llm_radar.py` | LLM relationship analysis, advisory caps, provider timeout/cache/budget behavior, golden evals, raw-event extraction, and scanner-report integration. |
| `tests/event_alpha/test_market_enrichment.py` | CoinGecko market enrichment, non-overwrite guarantees, store-only anomaly creation, bounded evidence search, and anomaly lifecycle transitions. |
| `tests/event_alpha/test_market_data_providers.py` | Coinalyze preflight/fixtures/live fail-soft/auto-symbols, derivatives non-overwrite enrichment, DEX readiness, and supply-provider hard gates. |
| `tests/event_alpha/test_news_providers.py` | CryptoPanic, GDELT, project RSS, news-derived external assets, explicit/text event-time provenance, classifier-confidence caps, and no-trade safety. |
| `tests/event_alpha/test_playbooks_graph.py` | Deterministic playbook classification and catalyst graph clustering/link rejection across proxy, direct, infrastructure, noise, supply, and derivatives evidence. |
| `tests/event_alpha/test_provider_activation.py` | Provider status/readiness, no-key Make targets, profile-scoped preflight/health, visible-core doctor readiness, backoff/reset/wrappers, v1/tuning/pack reports, daily-brief readiness, and Bybit preflight. |
| `tests/event_alpha/test_radar_pipeline.py` | Radar/scanner reports, watchlist/router pipeline cycles, search validation, hypothesis persistence/briefs, LLM suggestions and skip reasons, extraction ordering, and upstream hints. |
| `tests/event_alpha/test_watchlist_router.py` | Watchlist state/expiry compatibility, router escalation/digest/material-change policy, near-miss market refresh, and router-approved send gating. |
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
1,784 lines immediately before the focused backup-test move. It is now 1,678
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

Ten integrated-radar burn-downs moved all 240 original test identities into
focused modules and retired `tests/event_alpha/test_integrated_radar.py`. Every
step proved exact unique-name preservation, direct pytest execution, and
standalone-adapter compatibility. The largest replacement is 1,450 lines, below
the 1,500-line architecture warning; the final watchlist/router, operator
workflow, and presentation modules are 1,156, 1,006, and 618 lines. The full
Event Alpha package passes 650 cases, and the complete historical standalone
runner passes 786/786.

The provider-readiness burn-down moved all 88 original identities into six
focused modules and retired `tests/event_alpha/test_provider_readiness.py`.
News/event-time, exchange/universe, and Coinalyze/DEX/supply modules are 1,113,
699, and 534 lines; the final activation/readiness, discovery-pipeline, and
cache/scanner-report modules are 1,356, 940, and 817 lines. Exact names, pytest,
and standalone compatibility were preserved at every step.

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
