# Test Runtime Report

Research-only timing report. Commands run with no provider live-call or send flags.

- generated_at: `2026-07-10T07:24:23+00:00`
- status: `pass`
- standalone_runner_runtime_seconds: `191.61`
- pytest_runtime_seconds: `198.114`

## Commands

| name | status | seconds | command |
|---|---:|---:|---|
| `standalone_runner` | `pass` | `191.61` | `.venv/bin/python tests/test_indicators.py` |
| `pytest_safe` | `pass` | `198.114` | `.venv/bin/python -m pytest tests/event_alpha tests/rsi tests/cli tests/test_indicators.py` |
