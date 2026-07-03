# Refactor Release-Candidate Report

- generated_at: `2026-07-03T03:16:09+00:00`
- status: `accepted`
- verdict: Event Alpha refactor v2 accepted: critical behavior, safety, shim, size, scanner-facade, and regression checks passed.
- verification_failed_commands: `0`
- verification_total_commands: `27`

## Verification

| status | command | seconds |
|---|---|---:|
| `pass` | `python3 tests/test_indicators.py` | 14.207 |
| `pass` | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/event_alpha tests/rsi tests/cli tests/test_indicators.py -q` | 14.852 |
| `pass` | `python3 -m compileall -q crypto_rsi_scanner tests` | 0.039 |
| `pass` | `make test-pytest-safe PYTHON=python3` | 15.012 |
| `pass` | `make refactor-completion-map PYTHON=python3` | 2.19 |
| `pass` | `make refactor-size-gates PYTHON=python3` | 1.014 |
| `pass` | `make refactor-class-ownership-report PYTHON=python3` | 0.979 |
| `pass` | `make refactor-final-report PYTHON=python3` | 0.101 |
| `pass` | `make event-alpha-shim-report PYTHON=python3` | 0.053 |
| `pass` | `make event-alpha-namespace-lifecycle-report PYTHON=python3` | 0.677 |
| `pass` | `make event-alpha-integrated-radar-smoke PYTHON=python3` | 1.488 |
| `pass` | `make event-alpha-integrated-radar-doctor PYTHON=python3` | 0.692 |
| `pass` | `make event-alpha-live-provider-readiness-smoke PYTHON=python3` | 0.608 |
| `pass` | `make event-alpha-coinalyze-preflight-smoke PYTHON=python3` | 0.613 |
| `pass` | `make event-alpha-coinalyze-preflight PYTHON=python3` | 0.595 |
| `pass` | `make event-alpha-coinalyze-no-send-rehearsal PYTHON=python3` | 0.595 |
| `pass` | `make event-alpha-market-anomaly-smoke PYTHON=python3` | 2.414 |
| `pass` | `make event-alpha-official-exchange-smoke PYTHON=python3` | 2.404 |
| `pass` | `make event-alpha-scheduled-catalyst-smoke PYTHON=python3` | 2.375 |
| `pass` | `make event-alpha-unlock-risk-smoke PYTHON=python3` | 1.796 |
| `pass` | `make event-alpha-derivatives-smoke PYTHON=python3` | 1.804 |
| `pass` | `make event-alpha-fade-review-smoke PYTHON=python3` | 1.89 |
| `pass` | `make event-alpha-source-coverage-report PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal PYTHON=python3` | 0.685 |
| `pass` | `make event-alpha-daily-brief PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal PYTHON=python3` | 3.611 |
| `pass` | `make event-alpha-notify-preview-from-artifacts PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal PYTHON=python3` | 0.742 |
| `pass` | `make event-alpha-artifact-doctor PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal STRICT=1 PYTHON=python3` | 1.239 |
| `pass` | `make verify PYTHON=python3` | 15.657 |

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
