# Event-Fade No-Key Review Cycle - 2026-06-17

**Status:** research-only sample collection. No alerts, paper trades, live DB
writes, or execution.

## Command

```bash
make event-fade-no-key-review-cycle \
  EVENT_FADE_REVIEW_BUNDLE_EXPORT_PRICES=1 \
  EVENT_FADE_PRICE_INTERVAL=1h \
  EVENT_FADE_CACHE_REVIEW_BUNDLE_DIR=/tmp/event_fade_no_key_review_bundle
```

## Result

The cycle completed and wrote a local review bundle:

- Bundle: `/tmp/event_fade_no_key_review_bundle`
- Cache: `event_fade_cache` (gitignored)
- Validation rows: 69
- Rows needing review: 69
- SHORT_TRIGGERED rows: 0
- Outcome price export: enabled, 1h interval, 0 assets because there were no
  triggered rows

Source runs:

- Public RSS / Google News: 149 raw events, 147 normalized events, 66 candidate
  snapshots. Decrypt and The Block feeds returned HTTP 403 but the run still
  produced rows from other feeds.
- GDELT: HTTP 429, 0 raw events.
- Polymarket Gamma: 38 raw events, 36 normalized events, 3 candidate snapshots.

Sample composition:

- Relationships: 60 ambiguous, 4 direct token events, 4 proxy-context controls,
  1 proxy attention.
- Asset roles: 60 ambiguous, 4 direct beneficiaries, 3 ticker-word collisions,
  1 infrastructure, 1 proxy venue.
- Event-time source: 57 missing, 9 text-date, 3 explicit.
- Signal type: all 69 rows are `NO_TRADE`.
- Source providers: 66 `project_blog_rss`, 3 `prediction_market_events`.

## Main Finding

The post-stabilization gates behaved correctly. The only proxy-narrative row was
HYPE/Hyperliquid tied to a SpaceX pre-IPO article, but the classifier marked it
as `proxy_venue`, not `proxy_instrument`, so the new default
`proxy_venue_review_only` gate forced `NO_TRADE`.

That is the intended safety behavior. The cycle produced useful review/control
rows, but it did not produce any validated trigger candidates.

## Review Blockers

The generated review report remains blocked on manual evidence:

- Reviewed proxy candidates: 0/25
- Reviewed direct/ambiguous controls: 0/50
- Reviewed SHORT_TRIGGERED candidates: 0/10
- Trigger outcomes: none, because there are no triggered rows

## Next Work

1. Manually label the 69-row bundle or a refreshed successor bundle using
   `review_packet.md` and `review_template.csv`.
2. Preserve that review work across future refreshes with
   `main.py --event-fade-merge-sample`.
3. Improve collection toward dated proxy-instrument evidence. The current
   no-key sources mostly produce ambiguous RSS/news rows, direct BTC/ETF rows,
   and prediction-market controls.
4. Retry GDELT later or with a narrower query/window; this run was rate-limited.
5. Do not promote event-fade output to Telegram or paper tracking until reviewed
   proxy/control/trigger coverage and outcome metrics clear the existing review
   gates.
