# Event Alpha Candidate-Mode Burn-In Run Report

Research-only. This run did not authorize live trading, Event Alpha paper
trading, execution/order logic, normal RSI signal writes, Event Alpha-created
`TRIGGERED_FADE`, live Telegram sends, live provider calls by default, or secret
handling changes.

- run_timestamp: `2026-07-09T03:29:47.664370+00:00`
- repo_head: `fc8dc6cb`
- refactor_status: complete; no broad refactor work performed
- latest_candidate_mode_namespace: `live_burn_in_20260709`
- candidate_mode_status: `passed_no_candidates`
- live_provider_calls_allowed: `false`
- real_burn_in_candidate_count: `0`
- contract_counted_candidate_count: `0`
- fixture_candidate_count: `0`
- preflight_diagnostic_rows: `2`
- readiness_rows: `0`
- source_coverage_rows: `1`

## Test Gate

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/event_alpha/test_burn_in_candidate_mode.py -q`: `6 passed`
- `python3 tests/test_indicators.py`: `774/774 passed`
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/event_alpha tests/rsi tests/cli tests/test_indicators.py -q`: `844 passed`
- `python3 -m compileall -q crypto_rsi_scanner tests`: passed
- `make architecture-naming-check PYTHON=python3`: passed
- `make architecture-transitional-file-check PYTHON=python3`: passed
- `make event-alpha-old-import-check PYTHON=python3`: passed
- candidate-mode smoke and strict smoke doctor: passed
- integrated radar smoke and strict doctor: passed
- notification format smoke: passed with existing non-strict schema-safety warnings and no blockers
- Telegram no-send final check fast: passed
- strict CryptoPanic rehearsal doctor: passed with existing warnings and no blockers

## Provider Readiness

| provider | configured | live_call_allowed | result | request ledger |
|---|---:|---:|---|---|
| Coinalyze | false | false | skipped_missing_config: missing `RSI_EVENT_DISCOVERY_COINALYZE_API_KEY` | `event_fade_cache/live_burn_in_20260709/event_coinalyze_request_ledger.jsonl` |
| Bybit announcements | true | false | skipped_live_calls_disabled: set `RSI_EVENT_ALPHA_BYBIT_ANNOUNCEMENTS_ALLOW_LIVE_PREFLIGHT=1` for guarded no-send candidate mode | `event_fade_cache/live_burn_in_20260709/event_bybit_announcements_request_ledger.jsonl` |

No bounded live provider rehearsal was run because the required explicit allow
flags were not present. I did not set allow flags.

## Burn-In Artifacts

- run report: `event_fade_cache/live_burn_in_20260709/event_alpha_daily_burn_in_report.md`
- candidate manifest: `event_fade_cache/live_burn_in_20260709/event_alpha_candidate_mode_manifest.json`
- review inbox: `event_fade_cache/live_burn_in_20260709/event_alpha_daily_review_inbox.md`
- scorecard: `event_fade_cache/live_burn_in_no_send/event_alpha_burn_in_scorecard.md`
- source yield: `event_fade_cache/live_burn_in_no_send/event_alpha_source_yield_report.md`
- archive dry-run manifest: `research/event_alpha_burn_in_archive_manifest.json`
- latest namespace doctor: `event_fade_cache/live_burn_in_20260709/event_alpha_daily_burn_in_doctor_status.json`

Archive dry-run passed with `files_archived=128` and `secret_hit_count=0`.
Latest namespace strict doctor status is `OK` with `blockers=0` and
`warnings=0`. Review inbox has `items=0` and `blockers=0`.

## Safety Counters

- strict_alerts_created: `0`
- telegram_sends: `0`
- trades_created: `0`
- paper_trades_created: `0`
- normal_rsi_signal_rows_written: `0`
- triggered_fade_created: `0`

Key operator JSON/Markdown artifacts checked for `/tmp/`, `/mnt/data/`, and
`/Users/` path leaks had no matches.

## Outcome

Candidate mode ran safely, but no provider-backed `live_no_send` candidates were
produced because provider config/allow flags were missing or disabled. Fixture,
preflight, readiness, and support rows were not counted toward the burn-in
contract.

Current CryptoPanic rehearsal stayed conservative: strict daily digest rows were
`0`, `event_alpha_alerts` rows were `0`, and CHZ/VELVET remained
`UNCONFIRMED_RESEARCH` exploratory/store-only rows.

## Next Safe Operator Commands

Run readiness again:

```bash
make event-alpha-daily-burn-in-readiness PYTHON=python3
```

For Coinalyze, only after configuring `RSI_EVENT_DISCOVERY_COINALYZE_API_KEY`
and explicitly setting `RSI_EVENT_ALPHA_COINALYZE_ALLOW_LIVE_PREFLIGHT=1`:

```bash
make event-alpha-coinalyze-no-send-rehearsal PYTHON=python3
```

For Bybit announcements, only after explicitly setting
`RSI_EVENT_ALPHA_BYBIT_ANNOUNCEMENTS_ALLOW_LIVE_PREFLIGHT=1`:

```bash
make event-alpha-bybit-announcements-no-send-rehearsal PYTHON=python3
```

After any bounded provider rehearsal:

```bash
make event-alpha-daily-live-no-send-burn-in CANDIDATE_MODE=1 PYTHON=python3
```
