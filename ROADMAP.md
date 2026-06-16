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
| waiting | Let paper scoreboard accrue live data | system | First 6 paper trades closed via `main.py --refresh-paper` on 2026-06-15, but the sample is too small and outlier-dominated; keep waiting. |
| waiting | Validate edge-prior conviction buckets live | system | `main.py --report` now prints actionable/control, market alignment, and conviction buckets; wait for enough 7d outcomes before drawing conclusions. |
| waiting | Observe live state cohorts | system | `state_json` now lands in scanner CSV/signals/paper trades; `--report` and `--score --cohorts` expose cohorts once enough matured outcomes/trades exist. |
| waiting | Confirm state-slice candidate cohorts | system | Volume-PIT 5y run (`research/VOLUME_PIT_BACKTEST_2026-06-10.md`) replicated several candidates (breakdown_risk crisis-vol −19; mean_reversion washout +14 / risk_on −8); needs live-cohort cross-check before any live rule. |
| todo | Review volume-PIT registry prior export | human | `research/registry_priors_volpit_2026-06-10.json` is the first full-cycle, survivorship-reduced calibration artifact. Review before any `RSI_REGISTRY_PRIORS` opt-in. |
| todo | Build event-fade validation sample | open | Event-fade engine plus fixture event radar, clean CoinGecko-universe bridge, fixture-backed Binance/Bybit announcement parsers, captured official Binance CMS WebSocket payload parsing, opt-in live Binance/Bybit announcement fetches, raw Binance announcement cache listening, research-only JSONL cache refresh, cached-snapshot validation export, structured calendar/unlock parsers, CryptoPanic fixture parser plus opt-in live posts fetch, GDELT fixture parser plus opt-in live Article List fetch, project-blog/RSS fixture parser plus opt-in live RSS/Atom fetch, external IPO/sports/prediction-market catalyst parsers, Coinalyze-style derivatives enrichment plus opt-in live Coinalyze REST snapshots with optional `future-markets` symbol auto-resolution, Tokenomist/Etherscan/Arkham/Dune-style supply/on-chain enrichment, grouped `--event-fade-auto-report`, `--event-fade-export-sample`/`--event-fade-export-cache-sample` JSONL/CSV exports, `--event-fade-merge-sample` label/outcome preservation, `--event-fade-export-outcome-prices` local price-fixture generation, `--event-fade-fill-outcomes` trigger/baseline outcome filling, `--event-fade-labeling-queue` prioritization, `--event-fade-review-packet` Markdown review packets, compact `--event-fade-export-review-template`/`--event-fade-apply-review-template` sidecar label workflow, `--event-fade-review-bundle` local workspace export, and `--event-fade-review-sample` coverage/metrics/cohort/baseline/latency/diversity blocker report exist. Next step is expanding reviewed dated proxy/direct/ambiguous cases and filling human labels/outcomes from real local price histories before any live routing or paper tracking. |
| done | Extend PIT history depth beyond demo limits | — | Solved without a Pro key: `backtest --pit-volume` ranks the full Binance USDT pool by trailing 30d dollar volume per date (5y, point-in-time, cached). Details in `DEVLOG.md` 2026-06-10. |
| done | Confirm bull/chop state cohorts | — | Volume-PIT 5y run covered BULL 60.9k / CHOP 23.8k / BEAR 46.7k base-days: gating-map directions all confirmed (mean_reversion CHOP +10 n=800; dip_buy/trend_continuation BULL positive-thin; breakdown_risk no edge). See `research/VOLUME_PIT_BACKTEST_2026-06-10.md`. |
| todo | Walk-forward check of the CHOP mean_reversion edge | open | Run `--pit-volume --walk-forward` to confirm the +10 CHOP edge isn't one episode. Cached data makes this cheap. |

## Next

| status | item | owner | notes |
|---|---|---|---|
| waiting | Monitor next full-scan universe audit | system | `make refresh-universe-audit` confirmed current hygiene output after the filter tighten: 53 excluded, no obvious USD/stable kept by audit regex. The audit now stores all kept rows for leak detection; re-check after the next scheduled full scan. |

## Later

No ready later items. Current remaining work is waiting on live outcomes, the
event-fade validation sample labels/outcomes, or the next universe hygiene audit.
Tooling now exists for `--score --cohorts`, cost-aware backtests, walk-forward
checks, audit refreshes, event-fade fixture reports, event-discovery fixture/
universe plus opt-in live CoinGecko resolver enrichment/exchange/calendar/news
plus opt-in live Binance, Bybit, CryptoPanic, GDELT, RSS, and Coinalyze
auto-symbol/external-catalyst/derivatives/supply radar
reports, research-only event-discovery JSONL cache refreshes, raw Binance
announcement cache listening, grouped
event-fade auto reports, event-fade validation-sample exports from fixtures or
cached snapshots, event-fade validation merge/price-export/outcome-fill/
labeling-queue/review-packet/review-template/review-bundle/review cohort
reports, and suspicious-kept audit leak detection.

## Maintenance Rules

- Update this file when a change completes, changes priority, gets blocked, or is
  intentionally dropped.
- Do not duplicate full history here. Put completed details in `DEVLOG.md`.
- Durable accepted/rejected technical choices belong in `DECISIONS.md`.
