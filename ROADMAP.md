# ROADMAP

This file tracks pending work. `DEVLOG.md` records what changed; this file records
what still needs attention. Keep it short, current, and status-oriented.

Status labels:
- `todo`: ready to pick up.
- `waiting`: blocked on time, data, credentials, or a human decision.
- `doing`: actively in progress.
- `done`: completed; move details to `DEVLOG.md`.
- `dropped`: explicitly rejected; record the reason in `DECISIONS.md` if durable.

## Now

| status | item | owner | notes |
|---|---|---|---|
| waiting | Let paper scoreboard accrue live data | system | Needs roughly 1-2 weeks of matured 7d paper trades before drawing conclusions. |
| waiting | Validate edge-prior conviction buckets live | system | Compare high/med/low conviction and actionable/control books after enough paper trades mature. |
| waiting | Observe live state cohorts | system | `state_json` now lands in scanner CSV/signals/paper trades; wait for enough matured outcomes before trusting state-conditioned reads. |
| waiting | Confirm state-slice candidate cohorts | system | First Binance current-top run is documented in `research/STATE_SLICE_BACKTEST_2026-06-09.md`; needs PIT/live confirmation before any live rule. |
| waiting | Extend PIT history depth beyond demo limits | human/data | PIT cache now helps reuse CoinGecko histories, but >365d PIT still needs a Pro key or alternate historical market-cap source. |

## Next

| status | item | owner | notes |
|---|---|---|---|
| todo | Run cached PIT state-slice confirmation | open | Use `backtest --pit --state-slices`; cache raw CoinGecko histories in `backtest_cache` so interrupted/rate-limited runs can resume. |
| todo | Run stronger PIT calibration and review exported priors | open | Tooling exists via `backtest.py --export-priors`; needs larger PIT history before opting live into a file. |
| waiting | Monitor universe hygiene false positives/negatives | system | Latest audit is persisted by live scans; review `main.py --universe-audit` after the next scheduled scan. |

## Later

| status | item | owner | notes |
|---|---|---|---|
| todo | Add historical fixture snapshots for backtest smoke | open | Scanner fixture smoke exists; backtest still depends on network/Binance unless using unit tests. |

## Maintenance Rules

- Update this file when a change completes, changes priority, gets blocked, or is
  intentionally dropped.
- Do not duplicate full history here. Put completed details in `DEVLOG.md`.
- Durable accepted/rejected technical choices belong in `DECISIONS.md`.
