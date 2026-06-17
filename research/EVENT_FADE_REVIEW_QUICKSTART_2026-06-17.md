# Event-Fade Review Quickstart

**Date:** 2026-06-17  
**Status:** Waiting on human labels; event-fade remains research-only.

This is the handoff for finishing the ChatGPT Pro event-fade validation plan.
The tooling is implemented. The remaining work is to manually review the latest
validation sidecar and then run the existing apply/review commands.

## Latest Bundle

Use this local bundle:

```text
/tmp/event_fade_no_key_review_bundle_20260617_continue
```

Important files:

- `review_guide.md`: label taxonomy and event-time rules
- `review_packet_balanced.md`: source evidence for the balanced sidecar rows
- `review_template_balanced.csv`: editable sidecar to fill
- `validation_sample.jsonl`: source sample
- `review_report.txt`: current blockers and coverage
- `manifest.json`: machine-readable counts/provenance

Current counts:

- 120 validation rows
- 74 balanced sidecar rows to review
- 24 proxy candidates
- 50 direct/ambiguous controls in the balanced sidecar
- 0 reviewed rows
- 0 eligible rows
- 0 `SHORT_TRIGGERED` rows

## What To Fill

Edit only review fields in `review_template_balanced.csv`:

- `review_status`: use `reviewed` once source evidence is checked
- `reviewed_by`: reviewer name/handle
- `reviewed_at`: ISO timestamp, for example `2026-06-17T12:00:00+00:00`
- `human_label`: one of `valid_proxy_fade`, `false_positive`, `direct_event`,
  or `ambiguous`
- `human_notes`: short evidence note
- `human_event_time`, `human_event_time_confidence`, `human_event_time_source`,
  `human_event_time_notes`: fill only when the source proves explicit catalyst
  timing

Use helper columns such as `external_asset`, `primary_source_url`,
`source_search_url`, `source_date_hint`, `source_providers`,
`primary_raw_title`, `review_prompt`, and `event_time_review_hint` only as review
aids. They are not copied back into the validation sample.

## Label Rules

Use `valid_proxy_fade` only when all are true:

- the asset is a real proxy instrument for an external catalyst
- the catalyst is dated or has a clear expiry
- the asset is not the direct beneficiary
- source evidence was knowable before the decision time

Use `direct_event` for token-native catalysts such as ETF approvals for the
same asset, unlocks, listings, airdrops, TGEs, mainnet launches, or protocol
upgrades.

Use `false_positive` when the machine thought the row was proxy-like but manual
review shows the proxy thesis is wrong.

Use `ambiguous` when the source is weak, generic, ticker-only, or cannot prove a
clear proxy/direct relationship.

## Commands After Editing

From the repo root:

```bash
cd /Users/nasrenkaraf/crypto-rsi-scanner

.venv/bin/python main.py --event-fade-check-review-template \
  /tmp/event_fade_no_key_review_bundle_20260617_continue/validation_sample.jsonl \
  /tmp/event_fade_no_key_review_bundle_20260617_continue/review_template_balanced.csv
```

If the check passes, apply the sidecar:

```bash
.venv/bin/python main.py --event-fade-apply-review-template \
  /tmp/event_fade_no_key_review_bundle_20260617_continue/validation_sample.jsonl \
  /tmp/event_fade_no_key_review_bundle_20260617_continue/review_template_balanced.csv \
  /tmp/event_fade_no_key_review_bundle_20260617_continue/validation_sample_reviewed.jsonl
```

Then review promotion blockers:

```bash
.venv/bin/python main.py --event-fade-review-sample \
  /tmp/event_fade_no_key_review_bundle_20260617_continue/validation_sample_reviewed.jsonl
```

If the reviewed sample later has `SHORT_TRIGGERED` rows, fill outcomes from local
prices before considering promotion:

```bash
.venv/bin/python main.py --event-fade-fill-outcomes \
  /tmp/event_fade_no_key_review_bundle_20260617_continue/validation_sample_reviewed.jsonl \
  /tmp/event_fade_no_key_review_bundle_20260617_continue/outcome_prices.json \
  /tmp/event_fade_no_key_review_bundle_20260617_continue/validation_sample_reviewed_with_outcomes.jsonl
```

## Promotion Rule

Do not promote event fade to Telegram, paper tracking, live DB writes, or any
execution path until the review report clears the required proxy/control/trigger
coverage, timing, diversity, and outcome gates.

