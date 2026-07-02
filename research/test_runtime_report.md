# Test Runtime Report

Research-only timing report. Commands run with no provider live-call or send flags.

- generated_at: `2026-07-02T18:33:39+00:00`
- status: `pass`
- standalone_runner_runtime_seconds: `11.191`
- pytest_runtime_seconds: `11.538`

## Commands

| name | status | seconds | command |
|---|---:|---:|---|
| `standalone_runner` | `pass` | `11.191` | `python3 tests/test_indicators.py` |
| `pytest_safe` | `pass` | `11.538` | `python3 -m pytest tests/event_alpha tests/rsi tests/cli tests/test_indicators.py` |
