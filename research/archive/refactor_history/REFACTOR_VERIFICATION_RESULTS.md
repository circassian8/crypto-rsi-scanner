# Refactor Verification Results

- generated_at: `2026-07-05T10:04:42.182630+00:00`
- status: `passed`
- elapsed_seconds: `817.924`
- failed_commands: `0`

| # | command | status | seconds |
|---:|---|---:|---:|
| 1 | `python3 tests/test_indicators.py` | `pass` | `192.42` |
| 2 | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/event_alpha tests/rsi tests/cli tests/test_indicators.py -q` | `pass` | `197.551` |
| 3 | `python3 -m compileall -q crypto_rsi_scanner tests` | `pass` | `0.058` |
| 4 | `make refactor-transitional-file-check PYTHON=python3` | `pass` | `0.052` |
| 5 | `make refactor-legacy-file-check PYTHON=python3` | `pass` | `0.049` |
| 6 | `make refactor-legacy-terminology-check PYTHON=python3` | `pass` | `0.246` |
| 7 | `make event-alpha-old-import-check PYTHON=python3` | `pass` | `1.459` |
| 8 | `make event-alpha-shim-dependency-report PYTHON=python3` | `pass` | `1.459` |
| 9 | `make refactor-size-gates PYTHON=python3` | `pass` | `1.309` |
| 10 | `make refactor-class-ownership-report PYTHON=python3` | `pass` | `1.12` |
| 11 | `make refactor-final-report PYTHON=python3` | `pass` | `1.626` |
| 12 | `make event-alpha-integrated-radar-smoke PYTHON=python3` | `pass` | `6.049` |
| 13 | `make event-alpha-integrated-radar-doctor PYTHON=python3` | `pass` | `4.95` |
| 14 | `make event-alpha-notification-format-smoke PYTHON=python3` | `pass` | `6.509` |
| 15 | `make event-alpha-telegram-no-send-final-check-fast PYTHON=python3` | `pass` | `7.152` |
| 16 | `make event-alpha-artifact-doctor PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal STRICT=1 PYTHON=python3` | `pass` | `6.273` |
| 17 | `make verify PYTHON=python3` | `pass` | `389.639` |
