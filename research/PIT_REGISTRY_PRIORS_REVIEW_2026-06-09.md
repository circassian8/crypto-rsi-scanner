# PIT Registry Priors Review - 2026-06-09

## Command

```
.venv/bin/python -m crypto_rsi_scanner.backtest --pit --top-n 80 --pool 150 --days 365 --export-priors research/registry_priors_pit_2026-06-09.json
```

## Run Summary

- Source: CoinGecko daily, point-in-time top-N membership.
- Cache: 150 hits, 0 misses from `backtest_cache`.
- Usable histories: 128/150 candidates.
- Graded observations: 1325.
- Primary horizon: 7d.
- Minimum calibration samples: 8.
- Market-regime coverage: BEAR only.

## Exported Prior Deltas

| setup | prior cell | default | exported | evidence |
|---|---:|---:|---:|---|
| `breakdown_risk` | no change | unchanged | unchanged | 43 BEAR samples, -5.18pp edge; context-only guard prevented promotion |
| `dip_buy` | adverse | 24 | 24 | 5 BEAR samples, -46.81pp edge; below min sample threshold |
| `mean_reversion` | neutral | 42 | 47 | 229 BEAR samples, +11.55pp edge |
| `trend_continuation` | neutral | 42 | 40 | 35 BEAR samples, -3.96pp edge |

The machine-readable artifact is `research/registry_priors_pit_2026-06-09.json`.

## Read

This is useful evidence, but not a live calibration file yet. The export would
move the registry's neutral priors using only BEAR market coverage. That is
conceptually too broad: `neutral` also covers cases outside this exact bear-only
window, so loading this file live would turn one market regime into a global
neutral adjustment.

The constructive finding is narrower:

- BEAR `mean_reversion` again shows positive base-rate-adjusted edge.
- `breakdown_risk` remains non-actionable at 7d.
- BEAR `trend_continuation` did not confirm.
- BEAR `dip_buy` looked poor, but the cell is too small to calibrate.

## Decision

Do not set `RSI_REGISTRY_PRIORS` to this artifact. Keep it as a checked-in
research export and re-run calibration when PIT history includes bull/chop
coverage or live paper outcomes mature enough to validate setup-by-market cells.
