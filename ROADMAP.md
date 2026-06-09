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
| waiting | Re-run registry-prior calibration with broader PIT coverage | human/data | `research/PIT_REGISTRY_PRIORS_REVIEW_2026-06-09.md` reviewed the 365d export; it is BEAR-only and should not be loaded live. |
| waiting | Extend PIT history depth beyond demo limits | human/data | PIT cache now helps reuse CoinGecko histories, but >365d PIT still needs a Pro key or alternate historical market-cap source. |
| waiting | Confirm bull/chop state cohorts | human/data | Cached 365d PIT run only covered BTC `BEAR`; bull/chop confirmation needs deeper PIT history. |

## Next

| status | item | owner | notes |
|---|---|---|---|
| waiting | Re-check universe hygiene after next scan | system | 2026-06-09 audit found stable/pegged false negatives and filters were tightened; review `main.py --universe-audit` after the next scheduled scan confirms live output. |

## Later

No ready later items. Current remaining work is waiting on live outcomes, broader
PIT history, or the next universe hygiene audit.

## Maintenance Rules

- Update this file when a change completes, changes priority, gets blocked, or is
  intentionally dropped.
- Do not duplicate full history here. Put completed details in `DEVLOG.md`.
- Durable accepted/rejected technical choices belong in `DECISIONS.md`.
