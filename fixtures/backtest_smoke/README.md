# Backtest Smoke Fixtures

Checked-in Binance-style 1d kline snapshots used by `make backtest-fixture`.

- Symbols: BTCUSDT, ETHUSDT, SOLUSDT.
- Date range: 2025-06-10 through 2026-06-09 UTC.
- Columns: `date`, `close`, `volume`.
- Purpose: smoke-test the default backtest CLI path without network access.

This is not strategy evidence. Refresh only when the smoke stops producing
representative graded observations or the default backtest data path changes.
