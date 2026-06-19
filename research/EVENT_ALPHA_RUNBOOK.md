# Event Alpha Radar Runbook

Event Alpha is a research-only catalyst radar. It can discover evidence,
refresh watchlist rows, route research digests, write review artifacts, and
export proposed eval cases. It must not trade, paper trade, write normal RSI
signal rows, or let LLM/search/watchlist output create `TRIGGERED_FADE`.

## Daily No-Key Operation

Use the no-key profile when you want public RSS/GDELT/Polymarket plus live
CoinGecko-style market rows without OpenAI calls:

```bash
make event-alpha-daily-report PROFILE=no_key_live
```

This prints profile status, runs the cycle, writes alert snapshots and run-ledger
rows, prints router output, and summarizes alert snapshots. If no alerts arrive,
run:

```bash
make event-alpha-explain-last-run PROFILE=no_key_live
make event-alpha-open-items
make event-alpha-daily-brief PROFILE=no_key_live
```

The first command explains where the funnel stopped. The second checks active
watchlist monitoring, missed opportunities, and calibration. The brief writes a
Markdown summary under `RSI_EVENT_ALPHA_DAILY_BRIEF_PATH`, linking any selected
research cards.

For a compact daily burn-in loop that does status, cycle, brief, and last-run
explain without enabling sends:

```bash
make event-alpha-burn-in-no-key
```

For a 7-day operational scorecard across recent run-ledger rows, alert
snapshots, feedback, missed opportunities, provider health, and LLM budget
usage:

```bash
make event-alpha-burn-in-scorecard
python3 main.py --event-alpha-burn-in-scorecard --days 7
```

Before promoting any research-send burn-in, run the checklist. It reports
whether the local artifacts are ready, which blockers remain, and the next
operator actions:

```bash
make event-alpha-burn-in-checklist
python3 main.py --event-alpha-burn-in-checklist --days 7
```

The checklist is advisory only. It does not enable sends, change thresholds,
apply priors, write live signal rows, paper trade, or execute.

For explicit v1 gate flags across scheduled burn-in, research-send readiness,
and full-LLM live readiness:

```bash
make event-alpha-v1-readiness
python3 main.py --event-alpha-v1-readiness --days 7
```

This report is the promotion surface. Treat any `READY_*: no` line as a blocker
until the listed commands and artifacts are reviewed.

For daily freshness and safety checks:

```bash
make event-alpha-health-guard PROFILE=no_key_live
python3 main.py --event-alpha-health-guard
```

The health guard classifies the local research loop as `HEALTHY`, `DEGRADED`,
`STALE`, or `BLOCKED` based on run age, successful-run age, profile mismatch,
provider backoff, missing alert snapshots, LLM budget skips, and stale active
watchlist rows. It reports a next command only; it does not send or mutate state.

## Full LLM No-Send Review

Use the full LLM profile only when `OPENAI_API_KEY` is configured and you want
OpenAI extraction/advisory metadata without sending:

```bash
make event-alpha-daily-llm-report PROFILE=full_llm_live
```

LLM calls are capped by the profile budget defaults and the local budget ledger.
Cache hits are reused. If rows are skipped, the run ledger and explain report
show `llm_skipped_due_budget`.

For an LLM burn-in loop that keeps sends off and adds source reliability:

```bash
make event-alpha-burn-in-llm
```

## Guarded Research Send

Research sends are opt-in. They send only router-approved Event Alpha decisions,
not the broad rule-alert digest:

```bash
RSI_EVENT_ALERTS_ENABLED=1 make event-alpha-daily-send PROFILE=research_send
```

The send path still requires `research_only` alert mode and the normal Telegram
credentials. If no router-approved escalation exists, the cycle records a send
block reason instead of sending a broad digest.

## Feedback Labels

Use lightweight labels after reviewing cards or digests:

```bash
python3 main.py --event-feedback-mark ALERT_KEY --event-feedback-label useful
python3 main.py --event-feedback-mark ALERT_KEY --event-feedback-label junk --event-feedback-notes "publisher noise"
make event-feedback-useful FEEDBACK_TARGET=ALERT_KEY
make event-feedback-junk FEEDBACK_TARGET=ALERT_KEY FEEDBACK_NOTES="publisher noise"
make event-feedback-watch FEEDBACK_TARGET=ALERT_KEY
python3 main.py --event-feedback-report
```

Allowed labels are `useful`, `junk`, `watch`, `missed`, `traded_elsewhere`, and
`ignored`. Feedback is a research artifact only; it does not mutate watchlist
state or alert tiers. Shortcut commands tolerate unmatched keys and record a
manual warning row so review notes are not lost.

## Calibration Workflow

After feedback and outcomes accrue:

```bash
make event-alpha-calibration-report
make event-source-reliability-report
make event-alpha-calibration-export-priors
```

The priors export is reviewable JSON. It is not applied automatically. Treat it
as a proposal for manual threshold or source-prior changes.

If you explicitly want to test bounded priors in research ranking:

```bash
RSI_EVENT_ALPHA_APPLY_PRIORS=1 make event-alpha-cycle PROFILE=no_key_live
make event-alpha-replay
```

Applied priors write `score_before_priors`, `score_after_priors`, prior file,
version, and multipliers into alert snapshots. They cannot create
`TRIGGERED_FADE` or bypass hard source-noise/identity gates.

To compare priors without applying or writing snapshots:

```bash
make event-alpha-priors-shadow-report
```

Weekly review stitches the local review loop together:

```bash
make event-alpha-weekly-review
```

For a compact manual tuning worksheet that proposes changes without applying
them:

```bash
make event-alpha-tuning-worksheet
python3 main.py --event-alpha-tuning-worksheet
```

The worksheet groups repeated junk/useful feedback, repeated missed-opportunity
stages, run failures, and priors-shadow changes into manual review suggestions.
It never edits priors, thresholds, eval fixtures, alert tiers, or watchlist
state.

To hand off a clean burn-in review pack:

```bash
make event-alpha-export-burn-in-pack EVENT_ALPHA_BURN_IN_PACK=/tmp/event_alpha_burn_in_pack.zip
python3 main.py --event-alpha-export-burn-in-pack /tmp/event_alpha_burn_in_pack.zip
```

The pack includes text reports and small JSONL artifact excerpts. It excludes
secrets, `.env`, DB files, logs, caches, virtualenvs, and local ignored
artifacts.

## Research Cards

Print one card:

```bash
make event-research-cards ALERT_KEY=cluster_id\|coin_id\|playbook
```

Write selected cards and an index:

```bash
make event-research-cards-write PROFILE=no_key_live
```

Cards are Markdown artifacts under `RSI_EVENT_RESEARCH_CARDS_DIR` and include
playbook, source evidence, LLM interpretation, market confirmation, warnings,
verification steps, a playbook-specific trade-readiness checklist,
invalidation, and outcome fields.

Router reports now show stable `alert_id` and `card_id` values. Use the
`ea:...` alert ID in feedback commands, and the matching `card_...` ID/filename
when opening generated cards:

```bash
make event-alpha-router-report PROFILE=no_key_live
make event-feedback-useful FEEDBACK_TARGET=ea:cluster_id\|coin_id\|playbook
```

## When No Alerts Arrive

Run:

```bash
make event-alpha-explain-last-run PROFILE=no_key_live
make event-alpha-status PROFILE=no_key_live
make event-alpha-runs-report
```

Common causes:

- no source events or market anomalies entered the cycle
- resolver/classifier gates rejected noisy source rows
- all rows stayed `STORE_ONLY`
- watchlist/router had no escalation after cooldown and duplicate suppression
- send was requested but blocked by missing opt-in or no alertable route
- LLM budget was exhausted and lower-priority rows were skipped

## Provider Health and Replay

Provider health is stored locally under `RSI_EVENT_PROVIDER_HEALTH_PATH`.
Non-fixture event-source, universe, derivatives, catalyst-search, and LLM
providers may be skipped temporarily after repeated failures or DNS-like
errors. Rows are keyed by `provider_service:provider_role`, while legacy
name-only rows are still read for backoff compatibility. Inspect grouped
service/role health with:

```bash
make event-alpha-status PROFILE=no_key_live
```

Replay reads local artifacts only:

```bash
make event-alpha-replay
```

Replay is useful when comparing priors/advisory settings without live providers,
Telegram sends, or watchlist mutations.

Raw-event replay can reconstruct discovery/alerts/watchlist/router decisions
from a local cache/export plus optional local market rows:

```bash
python3 main.py --event-alpha-replay \
  --event-alpha-replay-raw-events event_fade_cache/raw_events.jsonl \
  --event-alpha-replay-market-rows fixtures/coingecko_smoke/top_markets.json \
  --event-alpha-replay-priors
```

This writes no live artifacts and uses a temporary watchlist path.

To compare local replay policies from the same raw event evidence:

```bash
python3 main.py --event-alpha-replay \
  --event-alpha-replay-raw-events event_fade_cache/raw_events.jsonl \
  --event-alpha-replay-market-rows fixtures/coingecko_smoke/top_markets.json \
  --event-alpha-replay-compare baseline,llm_advisory,priors,router_threshold_variant,profile_variant \
  --event-alpha-replay-profile no_key_live \
  --event-alpha-replay-profile-alt research_send
```

Policy comparison reports include candidate-level score, tier, and route diffs.
Use those rows to see which exact assets gained/lost alertability before
touching profile or prior settings.

## Scheduling Templates

Example templates live in:

```bash
research/event_alpha_launchd_template.plist
research/event_alpha_cron_example.txt
make event-alpha-launchd-template
```

They are intentionally disabled/placeholders. Fill in the project directory and
Python path manually, then install them yourself if you want daily local
burn-in. Recommended cadence:

- daily no-key burn-in cycle
- daily health guard after the cycle
- weekly tuning worksheet
- weekly burn-in pack export before external review

Profile-aware daily briefs and explain-last-run reports prefer the latest run
matching `--event-alpha-profile`. If no matching run exists, they show an
explicit requested/selected profile mismatch warning instead of silently
explaining an unrelated profile.

## Retention

Retention pruning is dry-run by default:

```bash
make event-alpha-prune-artifacts
CONFIRM=1 make event-alpha-prune-artifacts
```

It prunes old run-ledger rows, alert snapshots, and research cards according to
`RSI_EVENT_ALPHA_RETENTION_DAYS_*`. Canonical fixtures and proposed eval cases
are retained by default.

## When Alerts Are Noisy

Run:

```bash
make event-source-reliability-report
make event-alpha-calibration-report
make event-alpha-export-eval-cases
```

Then inspect proposed eval cases under
`event_fade_cache/proposed_eval_cases/`. Promote useful proposed cases manually
into the canonical fixture files only after reviewing the evidence and expected
labels.

## Proposed Eval Case Promotion

The exporter writes proposals only. To promote a case:

1. Open the proposed JSON file.
2. Verify the source text, expected label, and asset identity.
3. Copy the case into the appropriate canonical fixture:
   `fixtures/event_discovery/llm_golden_cases.json`,
   `fixtures/event_discovery/llm_extraction_golden_cases.json`, or
   `fixtures/event_discovery/event_alpha_golden_cases.json`.
4. Run:

```bash
make event-llm-eval PYTHON=python3
make event-llm-extract-eval PYTHON=python3
make event-alpha-eval PYTHON=python3
```

## Promotion Boundary

Do not promote Event Alpha beyond local reports/research digests until reviewed
samples show durable usefulness after false positives, missed opportunities,
outcomes, and source reliability are measured. `TRIGGERED_FADE` remains
reserved for deterministic `event_fade.py` output on `proxy_fade` rows.
