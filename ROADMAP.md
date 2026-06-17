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
| todo | Build event-fade validation sample | open | Event-fade engine plus fixture event radar, clean CoinGecko-universe bridge, neutral runtime alias default that keeps fixture aliases out of real-source review cycles, fixture-backed Binance/Bybit announcement parsers, captured official Binance CMS WebSocket payload parsing, opt-in live Binance/Bybit announcement fetches, raw Binance announcement cache listening, research-only JSONL cache refresh with redacted run diagnostics and `--event-discovery-runs` reporting, cached-snapshot validation export, redacted `--event-discovery-status` provider readiness checks, structured calendar/unlock parsers, CryptoPanic fixture parser plus opt-in live posts fetch, GDELT fixture parser plus opt-in live Article List fetch, project-blog/RSS fixture parser plus opt-in live RSS/Atom fetch, newline RSS URL-file support, no-key `make event-fade-public-rss-review-cycle` with expanded targeted proxy RSS searches, no-key `make event-fade-gdelt-review-cycle` for GDELT Article List proxy-news rows, no-key `make event-fade-polymarket-review-cycle` for Polymarket Gamma dated catalyst/control rows, no-key `make event-fade-no-key-review-cycle` to aggregate RSS, GDELT, and Polymarket into one source-summarized bundle, conservative source-text date inference with event-time source/confidence provenance for RSS/news rows, 30-day lookback, no-event-time `proxy_attention` review rows, asset-role classification (`proxy_instrument`/`proxy_venue` vs `mentioned_asset`/`infrastructure`/`ticker_word_collision`) with proxy venues review-only by default, explicit low-classifier/low-event-time `NO_TRADE` forcing, canonical catalyst dedupe, merged point-in-time-safe enrichment payloads across deduped raw sources, and generic identity-word resolver guards including the live Polymarket BILL/bill false-positive guard, external IPO/sports/prediction-market catalyst parsers, Coinalyze-style derivatives enrichment plus opt-in live Coinalyze REST snapshots with optional `future-markets` symbol auto-resolution, Tokenomist/Etherscan/Arkham/Dune-style supply/on-chain enrichment, grouped `--event-fade-auto-report`, `--event-fade-export-sample`/`--event-fade-export-cache-sample` JSONL/CSV exports with raw/min/max source timestamps, research-cache transition timestamps, evidence-fingerprint-safe `--event-fade-merge-sample` review-status/label/outcome preservation, `--event-fade-export-outcome-prices` local price-fixture generation with 1d/1h interval support, `--event-fade-fill-outcomes` trigger/baseline outcome filling with price interval/source metadata and review-only human event-time baselines, `--event-fade-labeling-queue` prioritization with event-time source/confidence and source-origin surfacing plus low-confidence trigger time confirmation and proxy event-time confirmation, `--event-fade-review-packet` Markdown review packets with source-origin context, compact evidence-checked `--event-fade-export-review-template`/`--event-fade-apply-review-template` sidecar label workflow with derived source-origin columns and separate review provenance plus human event-time confirmation fields, `--event-fade-review-bundle`/`--event-fade-cache-review-bundle` manifested local workspace exports with sample-quality, review-gate, per-source provider summaries, per-source origin/publisher summaries, bundle-local `review_guide.md` with provenance rules, and optional bundle-local price export/outcome fill, prior-reviewed-sample merging, and empty-cache warnings, fixture-backed `make event-fade-review-cycle`, configured-source `make event-fade-configured-review-cycle`, and `--event-fade-review-sample` coverage/metrics/cohort/baseline/latency/diversity/source-leakage blocker plus asset-role/event-time-source/source-provider/source-origin cohorts, low-confidence trigger event-time blocker, proxy source-provider diversity gate, and next-sample-work report exist. Review evidence now requires both `review_status=reviewed` and a known `human_label`, while promotion remains blocked until reviewed rows also have `reviewed_by` and `reviewed_at`; `proxy_attention` rows without event times are useful sample leads but remain `NO_TRADE`, and `proxy_venue` rows stay watchlist/review-only unless explicitly opted in after evidence. Current local status shows no always-on configured event sources ready. The 2026-06-17 no-key review cycle produced a 69-row mixed bundle (66 RSS/Google News rows, 3 Polymarket rows; GDELT was rate-limited with HTTP 429), with 1 proxy-venue review-only row, 4 direct rows, 4 proxy-context controls, 60 ambiguous rows, 57 missing event times, 0 eligible rows, and 0 triggers. The public RSS starter list now uses multiple Google News searches for pre-IPO/synthetic exposure, tokenized-stock, fan-token, prediction-market, sports, and political proxy narratives; a focused expanded-RSS smoke produced 118 rows, 27 proxy candidates, and 16 proxy-instrument rows, but 117/118 rows still lacked confirmed event times and 0 triggered. The next step is human-labeling those rows, confirming event times in the `human_event_time*` sidecar fields, and checking whether reviewed proxy-instrument candidates justify better automated event-time extraction before filling outcomes or considering any live routing/paper tracking. |
| todo | Label latest event-fade no-key bundle | human | Latest balanced bundle: `/tmp/event_fade_no_key_review_bundle_20260617_032443_template_check`. It has 121 rows: 27 proxy candidates, 19 proxy-context controls, 8 direct rows, 67 ambiguous rows, 0 triggers, and 117 missing machine event times. Start with `review_guide.md`, read `review_packet_balanced.md`, then fill the diversity-first `review_template_balanced.csv` for 75 gate-coverage rows: 25 proxy candidates and 50 controls. Set `review_status`, `reviewed_by`, `reviewed_at`, `human_label`, and any confirmed `human_event_time*` fields; use `primary_source_url`, `source_search_url`, `source_date_hint`, `primary_raw_title`, `review_prompt`, and `event_time_review_hint` only as reviewer aids. Before applying the sidecar, run `main.py --event-fade-check-review-template SAMPLE TEMPLATE` to catch changed evidence, missing provenance/labels/outcomes, and valid proxy labels without explicit catalyst timing. |
| done | Extend PIT history depth beyond demo limits | — | Solved without a Pro key: `backtest --pit-volume` ranks the full Binance USDT pool by trailing 30d dollar volume per date (5y, point-in-time, cached). Details in `DEVLOG.md` 2026-06-10. |
| done | Confirm bull/chop state cohorts | — | Volume-PIT 5y run covered BULL 60.9k / CHOP 23.8k / BEAR 46.7k base-days: gating-map directions all confirmed (mean_reversion CHOP +10 n=800; dip_buy/trend_continuation BULL positive-thin; breakdown_risk no edge). See `research/VOLUME_PIT_BACKTEST_2026-06-10.md`. |
| todo | Walk-forward check of the CHOP mean_reversion edge | open | Run `--pit-volume --walk-forward` to confirm the +10 CHOP edge isn't one episode. Cached data makes this cheap. |

## Next

| status | item | owner | notes |
|---|---|---|---|
| waiting | Monitor next full-scan universe audit | system | `make refresh-universe-audit` confirmed current hygiene output after the filter tighten: 53 excluded, no obvious USD/stable kept by audit regex. The audit now stores all kept rows for leak detection; re-check after the next scheduled full scan. |

## Later

No ready later items. Current remaining work is waiting on live outcomes, the
event-fade validation sample review status/labels/outcomes, or the next universe hygiene audit.
Tooling now exists for `--score --cohorts`, cost-aware backtests, walk-forward
checks, audit refreshes, event-fade fixture reports, event-discovery fixture/
universe plus opt-in live CoinGecko resolver enrichment/exchange/calendar/news
plus opt-in live Binance, Bybit, CryptoPanic, GDELT, RSS/RSS URL files, and Coinalyze
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
