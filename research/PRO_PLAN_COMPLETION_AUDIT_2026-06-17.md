# Pro Plan Completion Audit

**Date:** 2026-06-17  
**Reviewer:** Codex  
**Scope:** ChatGPT Pro stabilization plan for event-discovery/event-fade plus the
remaining validation workflow.

## Current Verdict

The code/tooling portion of the Pro plan is implemented and verified. The plan is
not fully complete because the final validation requirement depends on human
reviewed labels, confirmed event times, trigger outcomes, and more live paper
sample accrual. Those cannot be inferred safely by an agent.

Do not promote event-fade beyond local research reports until the validation
sample has reviewed rows and clears the review gates.

## Completed Requirements

| Requirement | Current evidence |
|---|---|
| Clean source export | `make export-src` writes `crypto-rsi-scanner-source.zip` via `git archive`; `.gitattributes` excludes local artifacts; `.gitignore` ignores the generated archive. |
| Friendlier verification/bootstrap | `Makefile` uses `PYTHON ?= .venv/bin/python`, has `check-python`, and `make bootstrap`. |
| Explicit classifier-confidence gate | `event_discovery.py` forces `NO_TRADE` with `forced_no_trade_reason=low_classifier_confidence`; covered by `test_event_discovery_forces_no_trade_on_low_classifier_confidence`. |
| Explicit event-time-confidence gate | `EventDiscoveryConfig.min_event_time_confidence` forces low-confidence/text-date rows to `NO_TRADE`; covered by `test_event_discovery_explicit_event_time_can_trigger_but_text_date_is_review_only`. |
| Proxy venue watchlist-only default | `RSI_EVENT_FADE_ALLOW_PROXY_VENUE_TRIGGER` defaults false; `proxy_venue_review_only` forces `NO_TRADE`; covered by proxy-venue tests. |
| Better dedupe | Canonical event dedupe merges differently worded catalyst headlines and preserves raw/source evidence; covered by `test_event_discovery_canonical_dedupe_merges_variant_headlines_and_payloads`. |
| Enrichment payload merge | Deduped raw payloads are merged point-in-time-safely instead of using only `raw_ids[0]`; covered by the canonical dedupe/payload test. |
| State transition timestamps | Research cache snapshots preserve `first_seen_at`, `first_watchlisted_at`, `first_armed_at`, `first_triggered_at`, and `last_seen_at`; covered by cache snapshot tests. |
| 1h outcome support | Outcome price export/fill accepts `1h`, records interval/source metadata, and has fixture coverage. |
| External asset extraction hardening | Rule-based extraction handles generic IPO/proxy/sports entities and rejects action-phrase false positives; covered by news and prediction-market tests. |
| Review workflow | Bundles include queue, packets, balanced sidecar, guide, manifest, source provider/origin summaries, event-time helper fields, preflight checks, merge, outcome fill, and promotion blockers. |
| No live promotion | Event-fade remains research-only: no alerts, live DB signal/outcome/paper writes, paper trades, or execution. |

## Latest Validation Artifact

Latest no-key bundle:

`/tmp/event_fade_no_key_review_bundle_20260617_continue`

Counts from `manifest.json`:

- 120 validation rows
- 24 proxy candidates
- 20 proxy-context controls
- 8 direct rows
- 68 ambiguous rows
- 116 missing machine event times
- 0 eligible rows
- 0 `SHORT_TRIGGERED` rows
- 74 rows in `review_template_balanced.csv`
- Source providers: `project_blog_rss` 117 rows, `prediction_market_events` 3 rows
- GDELT was rate-limited with HTTP 429 during the latest refresh

Preflight result:

```text
Status: not ready to apply.
No sidecar row contains nonblank review fields.
```

That is expected for an untouched human-review sidecar.

## Remaining Work

These are not code gaps:

1. Human label the latest balanced sidecar:
   `/tmp/event_fade_no_key_review_bundle_20260617_continue/review_template_balanced.csv`
2. For valid proxy candidates, confirm explicit catalyst times in the
   `human_event_time*` fields when machine event time is missing or low
   confidence.
3. Apply the reviewed sidecar with `main.py --event-fade-apply-review-template`.
4. Run `main.py --event-fade-review-sample` on the applied sample.
5. Fill outcomes only after reviewed trigger rows exist.
6. Keep live paper/outcome cohorts accruing before touching live priors,
   state-conditioned rules, alerts, or paper trading for event fade.

## Promotion Blockers

From the latest review report:

- reviewed proxy candidates `0/25`
- reviewed direct/ambiguous controls `0/50`
- reviewed `SHORT_TRIGGERED` candidates `0/10`

The correct next move is review work, not more provider expansion.

## Verification

Latest full verification before this audit:

```text
make verify
262/262 tests passed
alert render smoke passed
fixture backtest smoke passed
paper scoreboard printed
```

