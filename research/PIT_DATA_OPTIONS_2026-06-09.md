# PIT Data Options - 2026-06-09

The current point-in-time path works, but the local CoinGecko demo/free access is
effectively capped at 365 days. That is enough to reduce survivorship bias in the
recent BEAR window, but not enough to validate BULL/CHOP state cohorts or load a
registry-prior calibration live.

## Current Workflow

Use the cached PIT path for repeatable short-window research:

```
.venv/bin/python -m crypto_rsi_scanner.backtest --pit --top-n 80 --pool 150 --days 365 --state-slices
.venv/bin/python -m crypto_rsi_scanner.backtest --pit --top-n 80 --pool 150 --days 365 --export-priors research/registry_priors_pit_<date>.json
```

The cache lives under `backtest_cache/` by default and is intentionally
gitignored.

## To Extend Beyond 365 Days

Preferred path:

- Set `COINGECKO_API_KEY` to a key that supports deeper `market_chart` history.
- Set `COINGECKO_KEY_TYPE=pro` when using a Pro key.
- Re-run the PIT commands with `--days 1460` or deeper.
- Review market-regime coverage before using any result. A calibration run must
  contain BULL/CHOP/BEAR coverage before it can justify live priors.

Fallback data-source path:

- Use a provider with historical market cap and daily OHLC/volume by asset.
- Keep the same local contract: per asset daily `close`, `mcap`, and `volume`.
- Build PIT membership from historical market-cap rank, not today's top list.
- Reuse `walk_coin()`, `build_pit_membership()`, and the existing base-rate
  reports so live/backtest signal logic stays shared.

## Promotion Rule

Do not set `RSI_REGISTRY_PRIORS` from a PIT artifact unless:

- the run has enough samples by setup and market alignment,
- BULL/CHOP/BEAR regimes are represented,
- cost-aware and walk-forward reports do not contradict the headline edge,
- `make verify` passes after documenting the decision.
