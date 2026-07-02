# Refactor Baseline

Static inventory and behavior-freeze contract for the Event Alpha/refactor baseline.

This pass records current behavior and architecture before significant code movement. The generator reads repository files only; it does not invoke scanner/provider/runtime behavior.

## Safety Snapshot

- Static inventory only: `True`
- Behavior-changing code invoked: `False`
- Live provider calls allowed: `False`
- Telegram sends: `0`
- Trades created: `0`
- Paper trades created: `0`
- Normal RSI signal rows written: `0`
- Event Alpha TRIGGERED_FADE created: `0`

## Major File Line Counts

| file | lines |
|---|---:|
| `crypto_rsi_scanner/scanner.py` | 13373 |
| `tests/test_indicators.py` | 42498 |
| `crypto_rsi_scanner/event_alpha_artifact_doctor.py` | 7145 |

## Architecture Inventory

- Top-level `crypto_rsi_scanner/event_*.py` modules: `125`
- `crypto_rsi_scanner/event_alpha/` files: `43`
- `crypto_rsi_scanner/cli/` files: `11`
- `tests/` package files: `19`
- GitHub Actions workflows: `2`
- Event-related Makefile targets: `207`

### Event Alpha Package Files

- `crypto_rsi_scanner/event_alpha/MODULE_MAP.md`
- `crypto_rsi_scanner/event_alpha/__init__.py`
- `crypto_rsi_scanner/event_alpha/artifacts/__init__.py`
- `crypto_rsi_scanner/event_alpha/artifacts/context.py`
- `crypto_rsi_scanner/event_alpha/artifacts/paths.py`
- `crypto_rsi_scanner/event_alpha/artifacts/run_ledger.py`
- `crypto_rsi_scanner/event_alpha/artifacts/schema_v1.py`
- `crypto_rsi_scanner/event_alpha/cli/__init__.py`
- `crypto_rsi_scanner/event_alpha/doctor/__init__.py`
- `crypto_rsi_scanner/event_alpha/doctor/artifact_doctor.py`
- `crypto_rsi_scanner/event_alpha/doctor/check_registry.py`
- `crypto_rsi_scanner/event_alpha/doctor/consistency_doctor.py`
- `crypto_rsi_scanner/event_alpha/doctor/namespace_doctor.py`
- `crypto_rsi_scanner/event_alpha/doctor/report.py`
- `crypto_rsi_scanner/event_alpha/doctor/safety_doctor.py`
- `crypto_rsi_scanner/event_alpha/doctor/schema_doctor.py`
- `crypto_rsi_scanner/event_alpha/namespace/__init__.py`
- `crypto_rsi_scanner/event_alpha/namespace/lifecycle.py`
- `crypto_rsi_scanner/event_alpha/namespace/status.py`
- `crypto_rsi_scanner/event_alpha/notifications/__init__.py`
- `crypto_rsi_scanner/event_alpha/notifications/delivery.py`
- `crypto_rsi_scanner/event_alpha/notifications/pipeline.py`
- `crypto_rsi_scanner/event_alpha/notifications/sender.py`
- `crypto_rsi_scanner/event_alpha/outcomes/__init__.py`
- `crypto_rsi_scanner/event_alpha/outcomes/calibration.py`
- `crypto_rsi_scanner/event_alpha/outcomes/integrated_radar_outcomes.py`
- `crypto_rsi_scanner/event_alpha/providers/__init__.py`
- `crypto_rsi_scanner/event_alpha/providers/coinalyze_preflight.py`
- `crypto_rsi_scanner/event_alpha/providers/cryptopanic.py`
- `crypto_rsi_scanner/event_alpha/providers/live_provider_readiness.py`
- `crypto_rsi_scanner/event_alpha/providers/official_exchange.py`
- `crypto_rsi_scanner/event_alpha/providers/official_exchange_activation.py`
- `crypto_rsi_scanner/event_alpha/providers/source_packs.py`
- `crypto_rsi_scanner/event_alpha/providers/source_registry.py`
- `crypto_rsi_scanner/event_alpha/radar/__init__.py`
- `crypto_rsi_scanner/event_alpha/radar/core_opportunities.py`
- `crypto_rsi_scanner/event_alpha/radar/core_opportunity_store.py`
- `crypto_rsi_scanner/event_alpha/radar/evidence_acquisition.py`
- `crypto_rsi_scanner/event_alpha/radar/integrated_radar.py`
- `crypto_rsi_scanner/event_alpha/radar/market_anomaly_scanner.py`
- `crypto_rsi_scanner/event_alpha/radar/market_reaction.py`
- `crypto_rsi_scanner/event_alpha/radar/market_state.py`
- `crypto_rsi_scanner/event_alpha/radar/source_coverage.py`

### CLI Package Files

- `crypto_rsi_scanner/cli/__init__.py`
- `crypto_rsi_scanner/cli/commands_backtest.py`
- `crypto_rsi_scanner/cli/commands_event_alpha.py`
- `crypto_rsi_scanner/cli/commands_export.py`
- `crypto_rsi_scanner/cli/commands_maintenance.py`
- `crypto_rsi_scanner/cli/commands_paper.py`
- `crypto_rsi_scanner/cli/commands_provider_readiness.py`
- `crypto_rsi_scanner/cli/commands_rsi.py`
- `crypto_rsi_scanner/cli/dispatch.py`
- `crypto_rsi_scanner/cli/main.py`
- `crypto_rsi_scanner/cli/parser.py`

### Tests Package Files

- `tests/__init__.py`
- `tests/cli/__init__.py`
- `tests/cli/test_make_targets.py`
- `tests/cli/test_parser.py`
- `tests/conftest.py`
- `tests/event_alpha/__init__.py`
- `tests/event_alpha/test_artifact_doctor.py`
- `tests/event_alpha/test_artifact_schema.py`
- `tests/event_alpha/test_integrated_radar.py`
- `tests/event_alpha/test_namespace_lifecycle.py`
- `tests/event_alpha/test_notifications.py`
- `tests/event_alpha/test_outcomes.py`
- `tests/event_alpha/test_provider_readiness.py`
- `tests/event_alpha/test_source_coverage.py`
- `tests/rsi/__init__.py`
- `tests/rsi/test_backtest.py`
- `tests/rsi/test_indicators_core.py`
- `tests/rsi/test_paper_risk.py`
- `tests/test_indicators.py`

### GitHub Actions Workflows

- `.github/workflows/event-alpha-smoke.yml`
- `.github/workflows/verify.yml`

### Event-Related Makefile Targets

- `event-alert-no-key-llm-report`
- `event-alert-no-key-report`
- `event-alert-no-key-send`
- `event-alpha-alerts-report`
- `event-alpha-archive-stale-namespaces`
- `event-alpha-artifact-doctor`
- `event-alpha-burn-in-checklist`
- `event-alpha-burn-in-llm`
- `event-alpha-burn-in-no-key`
- `event-alpha-burn-in-readiness`
- `event-alpha-burn-in-scorecard`
- `event-alpha-bybit-announcements-no-send-rehearsal`
- `event-alpha-bybit-announcements-preflight`
- `event-alpha-bybit-announcements-preflight-smoke`
- `event-alpha-calibration-export-priors`
- `event-alpha-calibration-report`
- `event-alpha-catalyst-frame-e2e-cycle`
- `event-alpha-catalyst-frame-validation-cycle`
- `event-alpha-coinalyze-no-send-rehearsal`
- `event-alpha-coinalyze-preflight`
- `event-alpha-coinalyze-preflight-smoke`
- `event-alpha-coinmarketcal-preflight`
- `event-alpha-cryptopanic-preflight`
- `event-alpha-cycle`
- `event-alpha-cycle-llm`
- `event-alpha-cycle-profile`
- `event-alpha-cycle-profile-send`
- `event-alpha-cycle-search`
- `event-alpha-cycle-search-llm`
- `event-alpha-cycle-send`
- `event-alpha-daily-brief`
- `event-alpha-daily-llm-report`
- `event-alpha-daily-report`
- `event-alpha-daily-send`
- `event-alpha-day1-start`
- `event-alpha-day1-start-llm`
- `event-alpha-derivatives-report`
- `event-alpha-derivatives-smoke`
- `event-alpha-dex-onchain-readiness`
- `event-alpha-dex-onchain-readiness-smoke`
- `event-alpha-environment-doctor`
- `event-alpha-eval`
- `event-alpha-evidence-acquisition-smoke`
- `event-alpha-explain-last-run`
- `event-alpha-export-burn-in-pack`
- `event-alpha-export-eval-cases`
- `event-alpha-export-notification-pack`
- `event-alpha-export-signal-quality-cases`
- `event-alpha-fade-review-smoke`
- `event-alpha-feedback-readiness`
- `event-alpha-fill-outcomes`
- `event-alpha-frame-quality-loop`
- `event-alpha-generate-launchd`
- `event-alpha-health`
- `event-alpha-health-guard`
- `event-alpha-integrated-radar-calibration-export-priors`
- `event-alpha-integrated-radar-calibration-report`
- `event-alpha-integrated-radar-cycle`
- `event-alpha-integrated-radar-doctor`
- `event-alpha-integrated-radar-fill-outcomes`
- `event-alpha-integrated-radar-outcome-report`
- `event-alpha-integrated-radar-outcome-smoke`
- `event-alpha-integrated-radar-smoke`
- `event-alpha-launchd-template`
- `event-alpha-list-active-namespaces`
- `event-alpha-live-burn-in-no-send`
- `event-alpha-live-provider-readiness`
- `event-alpha-live-provider-readiness-smoke`
- `event-alpha-mark-known-stale-namespaces`
- `event-alpha-mark-namespace-stale`
- `event-alpha-market-anomaly-scan`
- `event-alpha-market-anomaly-smoke`
- `event-alpha-market-refresh-smoke`
- `event-alpha-messari-unlocks-preflight`
- `event-alpha-missed-report`
- `event-alpha-namespace-lifecycle-report`
- `event-alpha-near-miss-report`
- `event-alpha-no-key-report`
- `event-alpha-notification-checklist`
- `event-alpha-notification-deliveries-report`
- `event-alpha-notification-format-smoke`
- `event-alpha-notification-inbox`
- `event-alpha-notification-pause`
- `event-alpha-notification-retry-failed`
- `event-alpha-notification-runs-report`
- `event-alpha-notification-slo-report`
- `event-alpha-notify-cycle`
- `event-alpha-notify-fixture-smoke`
- `event-alpha-notify-go-no-go`
- `event-alpha-notify-llm`
- `event-alpha-notify-llm-deep-cryptopanic-no-send-rehearsal`
- `event-alpha-notify-llm-deep-fixture-rehearsal-artifacts`
- `event-alpha-notify-llm-deep-no-send-smoke`
- `event-alpha-notify-llm-deep-real-no-send-rehearsal`
- `event-alpha-notify-llm-deep-real-no-send-rehearsal-fast`
- `event-alpha-notify-llm-deep-real-no-send-rehearsal-with-fixture-candidate`
- `event-alpha-notify-llm-deep-rehearsal-with-fixture-candidate`
- `event-alpha-notify-llm-deep-research-review-no-send-smoke`
- `event-alpha-notify-llm-deep-scheduled`
- `event-alpha-notify-llm-quality-frame-smoke`
- `event-alpha-notify-llm-quality-fresh-cycle`
- `event-alpha-notify-llm-quality-scheduled`
- `event-alpha-notify-llm-quality-validation-cycle`
- `event-alpha-notify-llm-scheduled`
- `event-alpha-notify-no-key`
- `event-alpha-notify-no-key-scheduled`
- `event-alpha-notify-preview`
- `event-alpha-notify-preview-from-artifacts`
- `event-alpha-notify-start-llm`
- `event-alpha-notify-start-no-key`
- `event-alpha-official-exchange-report`
- `event-alpha-official-exchange-smoke`
- `event-alpha-open-items`
- `event-alpha-pause-notifications`
- `event-alpha-policy-simulate`
- `event-alpha-preflight`
- `event-alpha-priors-shadow-report`
- `event-alpha-provider-health-report`
- `event-alpha-provider-health-reset`
- `event-alpha-prune-artifacts`
- `event-alpha-prune-or-archive-stale-namespace`
- `event-alpha-quality-coverage-report`
- `event-alpha-quality-frame-live-smoke`
- `event-alpha-quality-live-smoke`
- `event-alpha-quality-loop`
- `event-alpha-quality-loop-llm`
- `event-alpha-quality-review`
- `event-alpha-quality-validation-cycle`
- `event-alpha-replay`
- `event-alpha-research-review-digest-smoke`
- `event-alpha-resume-notifications`
- `event-alpha-router-report`
- `event-alpha-runs-report`
- `event-alpha-scheduled-catalyst-report`
- `event-alpha-scheduled-catalyst-smoke`
- `event-alpha-scheduler-status`
- `event-alpha-send-go-no-go`
- `event-alpha-send-readiness`
- `event-alpha-send-test`
- `event-alpha-signal-quality-eval`
- `event-alpha-source-coverage-report`
- `event-alpha-status`
- `event-alpha-telegram-final-send-checklist`
- `event-alpha-telegram-no-send-final-check`
- `event-alpha-telegram-no-send-final-check-fast`
- `event-alpha-telegram-one-cycle-send-preflight`
- `event-alpha-telegram-post-send-audit`
- `event-alpha-telegram-recipient-check`
- `event-alpha-telegram-send-one-cycle`
- `event-alpha-telegram-send-readiness-final`
- `event-alpha-tokenomist-preflight`
- `event-alpha-tuning-worksheet`
- `event-alpha-unlock-risk-smoke`
- `event-alpha-v1-readiness`
- `event-alpha-weekly-review`
- `event-catalyst-search-fixture-report`
- `event-discovery-binance-listen`
- `event-discovery-refresh`
- `event-discovery-refresh-configured`
- `event-discovery-refresh-gdelt`
- `event-discovery-refresh-polymarket`
- `event-discovery-refresh-public-rss`
- `event-discovery-report`
- `event-discovery-runs`
- `event-discovery-status`
- `event-fade-apply-review-bundle`
- `event-fade-apply-review-template`
- `event-fade-auto-report`
- `event-fade-cache-review-bundle`
- `event-fade-check-review-bundle`
- `event-fade-check-review-template`
- `event-fade-configured-review-cycle`
- `event-fade-export-cache-sample`
- `event-fade-export-outcome-prices`
- `event-fade-export-review-template`
- `event-fade-export-sample`
- `event-fade-fill-outcomes`
- `event-fade-fill-review-bundle-outcomes`
- `event-fade-gdelt-review-cycle`
- `event-fade-labeling-queue`
- `event-fade-merge-sample`
- `event-fade-no-key-review-cycle`
- `event-fade-polymarket-review-cycle`
- `event-fade-public-rss-review-cycle`
- `event-fade-report`
- `event-fade-review-applied-bundle`
- `event-fade-review-bundle`
- `event-fade-review-cycle`
- `event-fade-review-packet`
- `event-fade-review-sample`
- `event-feedback-junk`
- `event-feedback-report`
- `event-feedback-useful`
- `event-feedback-watch`
- `event-impact-hypotheses-inbox`
- `event-impact-hypotheses-report`
- `event-impact-hypothesis-smoke`
- `event-incidents-report`
- `event-llm-eval`
- `event-llm-extract-eval`
- `event-opportunity-audit`
- `event-research-cards`
- `event-research-cards-write`
- `event-source-reliability-report`
- `event-watchlist-monitor`
- `event-watchlist-refresh`
- `event-watchlist-report`

## Namespace Inventory

- Base directory: `event_fade_cache`
- Namespace count: `44`
- Known stale namespaces: `notify_llm_deep`

| status | count |
|---|---:|
| `active_fixture_smoke` | 18 |
| `active_integrated_smoke` | 1 |
| `active_live_rehearsal` | 10 |
| `active_provider_preflight` | 5 |
| `active_provider_rehearsal` | 5 |
| `stale_deprecated` | 1 |
| `unknown` | 4 |

| namespace | status | stale | files | reason |
|---|---|---:|---:|---|
| `bybit_announcements_no_send_rehearsal` | `active_provider_rehearsal` | `False` | 4 | provider no-send rehearsal namespace |
| `bybit_announcements_preflight` | `active_provider_preflight` | `False` | 2 | provider preflight namespace |
| `bybit_announcements_preflight_smoke` | `active_fixture_smoke` | `False` | 2 | fixture smoke namespace |
| `catalyst_frame_e2e` | `unknown` | `False` | 7 | unclassified namespace |
| `catalyst_frame_validation` | `unknown` | `False` | 6 | unclassified namespace |
| `coinalyze_no_send_rehearsal` | `active_provider_rehearsal` | `False` | 4 | provider no-send rehearsal namespace |
| `coinalyze_preflight` | `active_provider_preflight` | `False` | 2 | provider preflight namespace |
| `coinalyze_preflight_smoke` | `active_fixture_smoke` | `False` | 2 | fixture smoke namespace |
| `coinmarketcal_preflight` | `active_provider_preflight` | `False` | 2 | provider preflight namespace |
| `derivatives_crowding_smoke` | `active_fixture_smoke` | `False` | 7 | fixture smoke namespace |
| `dex_onchain_readiness_smoke` | `active_fixture_smoke` | `False` | 9 | fixture smoke namespace |
| `evidence_acquisition_smoke` | `active_fixture_smoke` | `False` | 9 | fixture smoke namespace |
| `fade_review_smoke` | `active_fixture_smoke` | `False` | 7 | fixture smoke namespace |
| `fixture_notify_smoke` | `active_fixture_smoke` | `False` | 4 | fixture smoke namespace |
| `full_llm_live` | `active_live_rehearsal` | `False` | 0 | operator/live-style research namespace |
| `integrated_radar_smoke` | `active_integrated_smoke` | `False` | 36 | current integrated radar smoke namespace |
| `live_burn_in_no_send` | `active_live_rehearsal` | `False` | 10 | operator/live-style research namespace |
| `live_provider_readiness_smoke` | `active_fixture_smoke` | `False` | 2 | fixture smoke namespace |
| `market_anomaly_smoke` | `active_fixture_smoke` | `False` | 12 | fixture smoke namespace |
| `market_refresh_smoke` | `active_fixture_smoke` | `False` | 9 | fixture smoke namespace |
| `messari_unlocks_preflight` | `active_provider_preflight` | `False` | 2 | provider preflight namespace |
| `no_key_live` | `active_live_rehearsal` | `False` | 2 | operator/live-style research namespace |
| `notification_format_smoke` | `active_fixture_smoke` | `False` | 6 | fixture smoke namespace |
| `notify_llm` | `active_live_rehearsal` | `False` | 10 | operator/live-style research namespace |
| `notify_llm_deep` | `stale_deprecated` | `True` | 18 | pre-canonical notify_llm_deep artifacts; superseded by current rehearsal namespaces |
| `notify_llm_deep_cryptopanic_rehearsal` | `active_provider_rehearsal` | `False` | 18 | provider no-send rehearsal namespace |
| `notify_llm_deep_fixture_rehearsal` | `active_provider_rehearsal` | `False` | 7 | provider no-send rehearsal namespace |
| `notify_llm_deep_no_send_smoke` | `active_fixture_smoke` | `False` | 6 | fixture smoke namespace |
| `notify_llm_deep_rehearsal` | `active_provider_rehearsal` | `False` | 14 | provider no-send rehearsal namespace |
| `notify_llm_deep_research_review_smoke` | `active_fixture_smoke` | `False` | 9 | fixture smoke namespace |
| `notify_llm_quality` | `active_live_rehearsal` | `False` | 9 | operator/live-style research namespace |
| `notify_llm_quality_frame` | `active_live_rehearsal` | `False` | 9 | operator/live-style research namespace |
| `notify_llm_quality_frame_live_smoke` | `active_fixture_smoke` | `False` | 8 | fixture smoke namespace |
| `notify_llm_quality_fresh` | `active_live_rehearsal` | `False` | 9 | operator/live-style research namespace |
| `notify_no_key` | `active_live_rehearsal` | `False` | 8 | operator/live-style research namespace |
| `notify_no_key_format_preview` | `active_live_rehearsal` | `False` | 6 | operator/live-style research namespace |
| `official_exchange_smoke` | `active_fixture_smoke` | `False` | 14 | fixture smoke namespace |
| `quality_validation` | `unknown` | `False` | 6 | unclassified namespace |
| `research_review_digest_smoke` | `active_fixture_smoke` | `False` | 6 | fixture smoke namespace |
| `research_send` | `active_live_rehearsal` | `False` | 0 | operator/live-style research namespace |
| `scheduled_catalyst_smoke` | `active_fixture_smoke` | `False` | 11 | fixture smoke namespace |
| `source_enrichment` | `unknown` | `False` | 169 | unclassified namespace |
| `tokenomist_preflight` | `active_provider_preflight` | `False` | 2 | provider preflight namespace |
| `unlock_risk_smoke` | `active_fixture_smoke` | `False` | 9 | fixture smoke namespace |

## Behavior Freeze Contract

- CLI flags must remain compatible.
- Makefile targets must remain compatible.
- Old import paths must remain compatible.
- Artifact schema changes must be additive unless a migration is explicit.
- Doctor strict/WARN semantics must remain compatible.

## Artifact Contract

- Declared schema contract: `event_alpha_schema_v1`
- Schema module: `crypto_rsi_scanner/event_alpha/artifacts/schema_v1.py`
- Doctor check registry module: `crypto_rsi_scanner/event_alpha/doctor/check_registry.py`
- Schema changes: `additive_only_unless_explicit_migration`

## Refactor Success Gates

| gate | target | current | status |
|---|---|---:|---|
| scanner.py reduced below 4000 lines by final phase | `<4000` | 13373 | `baseline_recorded` |
| tests/test_indicators.py becomes umbrella runner below 2000 lines by final phase | `<2000` | 42498 | `baseline_recorded` |
| event_alpha_artifact_doctor.py becomes compatibility wrapper below 1500 lines by final phase | `<1500` | 7145 | `baseline_recorded` |
| pytest-compatible test package exists | `exists` | true | `present` |
| schema v1 is the declared artifact contract | `exists` | true | `present` |
| every doctor check declares schema dependencies | `exists` | true | `present` |
| namespace lifecycle report exists and marks stale namespaces | `exists` | true | `present` |
| GitHub Actions runs make verify safely | `contains make verify PYTHON=python3` | true | `present` |

## GitHub Actions Safety

- `make verify PYTHON=python3` present: `True`
- Forbidden live/secret terms present: `[]`

## Machine-Readable Artifact

- `research/REFACTOR_BASELINE.json` is the machine-readable companion for this report.
