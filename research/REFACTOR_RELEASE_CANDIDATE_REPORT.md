# Refactor Release-Candidate Report

- generated_at: `2026-07-05T04:02:53+00:00`
- status: `accepted`
- verdict: Event Alpha refactor v2 accepted: critical behavior, safety, shim, size, scanner-facade, and regression checks passed.
- verification_failed_commands: `0`
- verification_total_commands: `16`
- accepted_class_exceptions_count: `3`
- remaining_class_ownership_debt_count: `0`

## Verification

| status | command | seconds |
|---|---|---:|
| `pass` | `python3 tests/test_indicators.py` | 26.808 |
| `pass` | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/event_alpha tests/rsi tests/cli tests/test_indicators.py -q` | 27.569 |
| `pass` | `python3 -m compileall -q crypto_rsi_scanner tests` | 0.059 |
| `pass` | `make refactor-size-gates PYTHON=python3` | 1.167 |
| `pass` | `make refactor-class-ownership-report PYTHON=python3` | 1.069 |
| `pass` | `make refactor-final-report PYTHON=python3` | 1.282 |
| `pass` | `make event-alpha-shim-report PYTHON=python3` | 0.057 |
| `pass` | `make event-alpha-integrated-radar-smoke PYTHON=python3` | 1.87 |
| `pass` | `make event-alpha-integrated-radar-doctor PYTHON=python3` | 0.822 |
| `pass` | `make event-alpha-notification-format-smoke PYTHON=python3` | 2.182 |
| `pass` | `make event-alpha-telegram-no-send-final-check-fast PYTHON=python3` | 3.006 |
| `pass` | `make event-alpha-coinalyze-preflight-smoke PYTHON=python3` | 0.761 |
| `pass` | `make event-alpha-coinalyze-preflight PYTHON=python3` | 0.678 |
| `pass` | `make event-alpha-coinalyze-no-send-rehearsal PYTHON=python3` | 0.705 |
| `pass` | `make event-alpha-artifact-doctor PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal STRICT=1 PYTHON=python3` | 1.981 |
| `pass` | `make verify PYTHON=python3` | 28.312 |

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
