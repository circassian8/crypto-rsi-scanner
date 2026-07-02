# CLI Command Inventory

Generated inventory for the scanner CLI dispatch split. Runtime parser construction now lives in `crypto_rsi_scanner.cli.parser`; command routing lives in `crypto_rsi_scanner.cli.dispatch` and command-group modules.

## Size Gate

- Baseline `crypto_rsi_scanner/scanner.py` lines: `13373`
- Current `crypto_rsi_scanner/scanner.py` lines: `11262`
- Reduction this pass: `2111` lines
- Scanner remains a compatibility wrapper for `cli()` / `main()` plus historical helper exports.

## Dispatch Modules

| command group | handler module | role |
|---|---|---|
| `rsi` | `crypto_rsi_scanner.cli.commands_rsi` | report and default scan routing |
| `paper` | `crypto_rsi_scanner.cli.commands_paper` | score and refresh-paper routing |
| `maintenance` | `crypto_rsi_scanner.cli.commands_maintenance` | status, backup, launchd, logs, listener, universe audit |
| `export` | `crypto_rsi_scanner.cli.commands_export` | source export and source-with-artifacts export |
| `backtest` | `crypto_rsi_scanner.cli.commands_backtest` | module/Make command group marker for `python -m crypto_rsi_scanner.backtest` |
| `event_alpha*` | `crypto_rsi_scanner.cli.commands_event_alpha` | Event Alpha, integrated radar, doctor, notification, event-fade, event-discovery, feedback, LLM, and research-card routing |
| `event_alpha_provider_readiness` / `event_alpha_coinalyze` / `event_alpha_official_exchange` | `crypto_rsi_scanner.cli.commands_provider_readiness` | provider health, readiness, preflight, no-send rehearsal, Coinalyze, Bybit, DEX/on-chain, unlock/calendar routing |

## Classified Flags

| command group | flag | dispatch key | handler module |
|---|---|---|---|
| `event_alpha` | `--event-alpha-integrated-radar-smoke` | `event_alpha_integrated_radar_smoke` | `crypto_rsi_scanner.cli.commands_event_alpha` |
| `event_alpha` | `--event-alpha-namespace-lifecycle-report` | `event_alpha_namespace_lifecycle_report` | `crypto_rsi_scanner.cli.commands_event_alpha` |
| `event_alpha_artifact_doctor` | `--event-alpha-artifact-doctor` | `event_alpha_artifact_doctor` | `crypto_rsi_scanner.cli.commands_event_alpha` |
| `event_alpha_artifact_doctor` | `--event-alpha-integrated-radar-doctor` | `event_alpha_integrated_radar_doctor` | `crypto_rsi_scanner.cli.commands_event_alpha` |
| `event_alpha_coinalyze` | `--event-alpha-coinalyze-no-send-rehearsal` | `event_alpha_coinalyze_no_send_rehearsal` | `crypto_rsi_scanner.cli.commands_provider_readiness` |
| `event_alpha_coinalyze` | `--event-alpha-coinalyze-preflight` | `event_alpha_coinalyze_preflight` | `crypto_rsi_scanner.cli.commands_provider_readiness` |
| `event_alpha_coinalyze` | `--event-alpha-coinalyze-preflight-smoke` | `event_alpha_coinalyze_preflight_smoke` | `crypto_rsi_scanner.cli.commands_provider_readiness` |
| `event_alpha_integrated_radar` | `--event-alpha-integrated-radar-calibration-report` | `event_alpha_integrated_radar_calibration_report` | `crypto_rsi_scanner.cli.commands_event_alpha` |
| `event_alpha_integrated_radar` | `--event-alpha-integrated-radar-cycle` | `event_alpha_integrated_radar_cycle` | `crypto_rsi_scanner.cli.commands_event_alpha` |
| `event_alpha_integrated_radar` | `--event-alpha-integrated-radar-fill-outcomes` | `event_alpha_integrated_radar_fill_outcomes` | `crypto_rsi_scanner.cli.commands_event_alpha` |
| `event_alpha_integrated_radar` | `--event-alpha-integrated-radar-outcome-report` | `event_alpha_integrated_radar_outcome_report` | `crypto_rsi_scanner.cli.commands_event_alpha` |
| `event_alpha_notification` | `--event-alpha-notify-go-no-go` | `event_alpha_notify_go_no_go` | `crypto_rsi_scanner.cli.commands_event_alpha` |
| `event_alpha_notification` | `--event-alpha-notify-preview` | `event_alpha_notify_preview` | `crypto_rsi_scanner.cli.commands_event_alpha` |
| `event_alpha_notification` | `--event-alpha-notify-preview-from-artifacts` | `event_alpha_notify_preview_from_artifacts` | `crypto_rsi_scanner.cli.commands_event_alpha` |
| `event_alpha_official_exchange` | `--event-alpha-bybit-announcements-no-send-rehearsal` | `event_alpha_bybit_announcements_no_send_rehearsal` | `crypto_rsi_scanner.cli.commands_provider_readiness` |
| `event_alpha_official_exchange` | `--event-alpha-bybit-announcements-preflight` | `event_alpha_bybit_announcements_preflight` | `crypto_rsi_scanner.cli.commands_provider_readiness` |
| `event_alpha_official_exchange` | `--event-alpha-bybit-announcements-preflight-smoke` | `event_alpha_bybit_announcements_preflight_smoke` | `crypto_rsi_scanner.cli.commands_provider_readiness` |
| `event_alpha_official_exchange` | `--event-alpha-official-exchange-report` | `event_alpha_official_exchange_report` | `crypto_rsi_scanner.cli.commands_provider_readiness` |
| `event_alpha_provider_readiness` | `--event-alpha-live-provider-readiness` | `event_alpha_live_provider_readiness` | `crypto_rsi_scanner.cli.commands_provider_readiness` |
| `event_alpha_provider_readiness` | `--event-alpha-live-provider-readiness-smoke` | `event_alpha_live_provider_readiness_smoke` | `crypto_rsi_scanner.cli.commands_provider_readiness` |
| `export` | `--export-src` | `export_src` | `crypto_rsi_scanner.cli.commands_export` |
| `export` | `--export-src-with-artifacts` | `export_src_with_artifacts` | `crypto_rsi_scanner.cli.commands_export` |
| `maintenance` | `--backup-db` | `backup_db` | `crypto_rsi_scanner.cli.commands_maintenance` |
| `maintenance` | `--maintenance` | `maintenance` | `crypto_rsi_scanner.cli.commands_maintenance` |
| `maintenance` | `--status` | `status` | `crypto_rsi_scanner.cli.commands_maintenance` |
| `paper` | `--refresh-paper` | `refresh_paper` | `crypto_rsi_scanner.cli.commands_paper` |
| `paper` | `--score` | `score` | `crypto_rsi_scanner.cli.commands_paper` |
| `rsi` | `--dry-run` | `dry_run` | `crypto_rsi_scanner.cli.commands_rsi` |
| `rsi` | `--report` | `report` | `crypto_rsi_scanner.cli.commands_rsi` |

## Compatibility Notes

- `scanner.py` keeps `cli()` and `main()` as compatibility wrappers.
- Existing command bodies remain in `scanner.py` until later command-body extraction slices.
- CLI schema changes in this pass are additive: `--export-src` and `--export-src-with-artifacts` expose existing Make/export behavior through the CLI facade.
- No live provider calls, sends, trades, paper trades, normal RSI rows, or Event Alpha-created `TRIGGERED_FADE` are enabled by this inventory.
