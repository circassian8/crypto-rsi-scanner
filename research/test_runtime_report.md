# Test Runtime Report

Research-only timing report. Commands run with no provider live-call or send flags.

- generated_at: `2026-07-02T18:02:05+00:00`
- status: `pass`
- standalone_runner_runtime_seconds: `10.761`
- pytest_runtime_seconds: `11.25`

## Commands

| name | status | seconds | command |
|---|---:|---:|---|
| `standalone_runner` | `pass` | `10.761` | `python3 tests/test_indicators.py` |
| `pytest_safe` | `pass` | `11.25` | `python3 -m pytest tests/event_alpha tests/rsi tests/cli tests/test_indicators.py` |
