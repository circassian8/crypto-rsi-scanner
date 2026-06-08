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

## Next

| status | item | owner | notes |
|---|---|---|---|
| todo | Improve point-in-time backtest power | open | Pro CoinGecko key or alternate history source would extend PIT universe beyond demo limits. |
| todo | Run stronger PIT calibration and review exported priors | open | Tooling exists via `backtest.py --export-priors`; needs larger PIT history before opting live into a file. |
| todo | Monitor universe hygiene false positives/negatives | open | Initial filters are live; review excluded symbols from logs and tune thresholds if needed. |

## Later

| status | item | owner | notes |
|---|---|---|---|
| todo | Add cached API fixtures for dev | open | Speed dry-run/backtest smoke checks and avoid unnecessary CoinGecko calls. |

## Maintenance Rules

- Update this file when a change completes, changes priority, gets blocked, or is
  intentionally dropped.
- Do not duplicate full history here. Put completed details in `DEVLOG.md`.
- Durable accepted/rejected technical choices belong in `DECISIONS.md`.
