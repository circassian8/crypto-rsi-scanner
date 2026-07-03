# Refactor Release-Candidate Report

- generated_at: `2026-07-03T15:40:39+00:00`
- status: `accepted`
- verdict: Event Alpha refactor v2 accepted: critical behavior, safety, shim, size, scanner-facade, and regression checks passed.
- verification_failed_commands: `0`
- verification_total_commands: `23`

## Verification

| status | command | seconds |
|---|---|---:|
| `pass` | `python3 tests/test_indicators.py` | 19.677 |
| `pass` | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/event_alpha tests/rsi tests/cli tests/test_indicators.py -q` | 20.528 |
| `pass` | `python3 -m compileall -q crypto_rsi_scanner tests` | 0.042 |
| `pass` | `make test-pytest-safe PYTHON=python3` | 20.582 |
| `pass` | `make refactor-size-gates PYTHON=python3` | 1.132 |
| `pass` | `make refactor-class-ownership-report PYTHON=python3` | 1.04 |
| `pass` | `make refactor-final-report PYTHON=python3` | 0.168 |
| `pass` | `make event-alpha-shim-report PYTHON=python3` | 0.056 |
| `pass` | `make event-alpha-integrated-radar-smoke PYTHON=python3` | 1.848 |
| `pass` | `make event-alpha-integrated-radar-doctor PYTHON=python3` | 0.777 |
| `pass` | `make event-alpha-notification-format-smoke PYTHON=python3` | 2.032 |
| `pass` | `make event-alpha-telegram-no-send-final-check-fast PYTHON=python3` | 2.762 |
| `pass` | `make event-alpha-evidence-acquisition-smoke PYTHON=python3` | 4.337 |
| `pass` | `make event-alpha-catalyst-frame-e2e-cycle PYTHON=python3` | 4.123 |
| `pass` | `make event-alpha-coinalyze-preflight-smoke PYTHON=python3` | 0.652 |
| `pass` | `make event-alpha-coinalyze-preflight PYTHON=python3` | 0.631 |
| `pass` | `make event-alpha-coinalyze-no-send-rehearsal PYTHON=python3` | 0.633 |
| `pass` | `make event-alpha-source-coverage-report PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal PYTHON=python3` | 0.644 |
| `pass` | `make event-alpha-daily-brief PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal PYTHON=python3` | 4.426 |
| `pass` | `make event-alpha-notify-preview-from-artifacts PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal PYTHON=python3` | 0.919 |
| `pass` | `make event-alpha-artifact-doctor PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal STRICT=1 PYTHON=python3` | 1.455 |
| `pass` | `make backtest-costs PYTHON=python3` | 0.587 |
| `pass` | `make verify PYTHON=python3` | 21.319 |

## Known Remaining Blockers

- none

## Safety Confirmation

- research_only: `True`
- no_live_provider_calls_by_default: `True`
- no_live_telegram_sends: `True`
- no_trading_paper_or_execution_changes: `True`
- no_event_alpha_normal_rsi_signal_writes: `True`
- no_event_alpha_created_triggered_fade: `True`
- triggered_fade_source: `event_fade.py + proxy_fade only`
- no_secrets_in_artifacts: `True`
