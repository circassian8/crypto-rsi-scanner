# Architecture Release-Candidate Report

- generated_at: `2026-07-10T06:38:09+00:00`
- status: `accepted`
- verdict: Event Alpha architecture accepted: critical behavior, safety, shim, size, scanner-facade, and regression checks passed.
- verification_failed_commands: `0`
- verification_total_commands: `26`
- accepted_class_exceptions_count: `3`
- remaining_class_ownership_debt_count: `0`

## Verification

| status | command | seconds |
|---|---|---:|
| `pass` | `python3 tests/test_indicators.py` | 177 |
| `pass` | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/event_alpha tests/rsi tests/cli tests/test_indicators.py -q` | 202 |
| `pass` | `python3 -m compileall -q crypto_rsi_scanner tests` | 1 |
| `pass` | `make architecture-naming-check PYTHON=python3` | 1 |
| `pass` | `make architecture-transitional-file-check PYTHON=python3` | 1 |
| `pass` | `make architecture-size-gates PYTHON=python3` | 3 |
| `pass` | `make architecture-class-ownership-report PYTHON=python3` | 2 |
| `pass` | `make architecture-final-report PYTHON=python3` | 6 |
| `pass` | `make architecture-completion-map PYTHON=python3` | 22 |
| `pass` | `make architecture-cleanliness-check PYTHON=python3` | 6 |
| `pass` | `make event-alpha-old-import-check PYTHON=python3` | 2 |
| `pass` | `make event-alpha-shim-dependency-report PYTHON=python3` | 2 |
| `pass` | `make event-alpha-integrated-radar-smoke PYTHON=python3` | 3 |
| `pass` | `make event-alpha-integrated-radar-doctor PYTHON=python3` | 1 |
| `pass` | `make event-alpha-notification-format-smoke PYTHON=python3` | 3 |
| `pass` | `make event-alpha-telegram-no-send-final-check-fast PYTHON=python3` | 4 |
| `pass` | `make event-alpha-evidence-acquisition-smoke PYTHON=python3` | 5 |
| `pass` | `make event-alpha-catalyst-frame-e2e-cycle PYTHON=python3` | 5 |
| `pass` | `make event-alpha-coinalyze-preflight-smoke PYTHON=python3` | 1 |
| `pass` | `make event-alpha-coinalyze-preflight PYTHON=python3` | 1 |
| `pass` | `make event-alpha-coinalyze-no-send-rehearsal PYTHON=python3` | 1 |
| `pass` | `make event-alpha-source-coverage-report PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal PYTHON=python3` | 1 |
| `pass` | `make event-alpha-daily-brief PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal PYTHON=python3` | 5 |
| `pass` | `make event-alpha-notify-preview-from-artifacts PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal PYTHON=python3` | 2 |
| `pass` | `make event-alpha-artifact-doctor PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal STRICT=1 PYTHON=python3` | 3 |
| `pass` | `make verify PYTHON=python3` | 78 |

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
