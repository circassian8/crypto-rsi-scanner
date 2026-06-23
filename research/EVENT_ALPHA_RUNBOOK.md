# Event Alpha Radar Runbook

Event Alpha is a research-only catalyst radar. It can discover evidence,
refresh watchlist rows, route research digests, write review artifacts, and
export proposed eval cases. It must not trade, paper trade, write normal RSI
signal rows, or let LLM/search/watchlist output create `TRIGGERED_FADE`.

## Day-1 Notification Burn-In

Use notification profiles when you want immediate Telegram research
notifications while still treating every message as unvalidated review output.
This is not calibrated research send, not a trade signal, and not paper/live
trading.

Required for actual delivery:

```bash
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_IDS=...
RSI_EVENT_ALERTS_ENABLED=1
```

Then run the no-key startup path:

```bash
make event-alpha-day1-start
make event-alpha-notification-inbox PROFILE=notify_no_key
RSI_EVENT_ALERTS_ENABLED=1 make event-alpha-send-test PROFILE=notify_no_key
RSI_EVENT_ALERTS_ENABLED=1 make event-alpha-notify-no-key
```

`make event-alpha-day1-start` is a no-send operator check. It runs preflight,
the notification checklist, and the notification preview for `notify_no_key`,
then prints the two guarded send commands. Use `make event-alpha-day1-start-llm`
for the same no-send flow against `notify_llm`.

`notify_no_key` uses public RSS, GDELT, Polymarket, live CoinGecko universe,
market enrichment, anomaly scanning, catalyst search, watchlist monitoring,
router lanes, and auto-written research cards. `notify_llm` uses the same source
set plus OpenAI extraction/advisory metadata, bounded full-source enrichment for
LLM context, and conservative defaults: 10 calls/run, 50 calls/day, $1/day
estimated cap, 10 enriched source rows/run, and a 168-hour cache TTL. Use
`notify_llm_deep` only when you explicitly want a deeper review cycle: it keeps
the same research-only send guards but raises the LLM/enrichment caps.

Notification lanes are independent: a daily digest cooldown does not block an
instant escalation, and instant escalation cooldown does not block a
deterministic proxy-fade `TRIGGERED_FADE`. Triggered-fade notifications dedupe
by stable alert id. Health heartbeat delivery is once per day by default and
can report a no-alert run.

For `notify_no_key`, the operator requested visibility on every run. That
profile overrides daily, instant, heartbeat, and exploratory digest cooldowns to
zero and disables stable content dedupe. The run lock and in-flight guard remain
active, so overlapping scheduled cycles are still protected, but a clean new
`notify_no_key` run should deliver Telegram output even if the previous run had
the same health status or digest content.

`notify_no_key` and `notify_llm` also enable a separate
`exploratory_digest` lane during notification burn-in. It surfaces top
suppressed/store-only/raw-evidence rows for operator learning, with explicit
“unvalidated / low-confidence / not a trade signal” copy. It is not an alertable
decision, cannot create `TRIGGERED_FADE`, does not write paper/live/normal RSI
rows, and has its own cooldown/dedupe state. Source-noise and ticker-collision
controls are excluded by default unless
`RSI_EVENT_ALPHA_EXPLORATORY_DIGEST_INCLUDE_CONTROLS=1`.

Event Alpha can also write `HYPOTHESIS` watchlist rows. A hypothesis means the
radar inferred that an external catalyst may affect a crypto sector or seed
asset set, but direct candidate validation is incomplete. External entities
such as SpaceX/OpenAI/Stripe stay in `external_entities`; crypto candidates stay
in `crypto_candidate_assets`; false positives stay in
`rejected_candidate_assets`. Example: a SpaceX pre-IPO article can produce a
tokenized-stock-venue hypothesis with VELVET/HYPE/ASTER validation searches.
These rows are exploratory/store-only by default and are not alertable. They may
promote to `RADAR` only after identity-safe source evidence explicitly links a
candidate asset to the catalyst (`catalyst_link_validated`,
`market_confirmed`, or `promoted_to_radar`). Candidate-only or identity-only
evidence can improve review context but does not promote a token-level row.
Candidate-discovery search hits can suggest new crypto candidates when the
source payload or quote-validated extraction names an asset, but those
suggestions still need deterministic identity/catalyst validation before they
can become token-level `RADAR` rows. Use the report's `why_not_promoted`
section to separate discovery-only leads from identity/catalyst/market/score
blockers.
Hypotheses cannot create `WATCHLIST`, `HIGH_PRIORITY`, paper/live rows, or
`TRIGGERED_FADE`; `TRIGGERED_FADE` still comes only from `event_fade.py` plus
the `proxy_fade` playbook.

Each Event Alpha cycle also appends generated hypotheses to a profile-scoped
research artifact:

```bash
make event-impact-hypotheses-report PROFILE=notify_llm
make event-impact-hypotheses-report PROFILE=notify_llm LATEST=1
make event-impact-hypotheses-inbox PROFILE=notify_llm
make event-impact-hypothesis-smoke
```

The store path defaults to
`event_fade_cache/<profile>/event_impact_hypotheses.jsonl` and can be inspected
with `main.py --event-impact-hypotheses-report --event-alpha-profile PROFILE`
or the review-focused
`main.py --event-impact-hypotheses-inbox --event-alpha-profile PROFILE`.
Rows include candidate provenance (`taxonomy`, `llm_extraction`, and/or
`deterministic_resolver`), suggested assets, validated assets, flattened
`validated_symbol` / `validated_coin_id` fields, promoted watchlist keys,
validation status, search queries, rejection reasons, rejected validation
evidence samples, schema-audit fields, and `why_not_promoted` diagnostics.
Suggested LLM/search assets are metadata only until deterministic
resolver/search evidence validates identity.

Use `LATEST=1` for daily diagnosis so the report focuses on the latest stored
`run_id` while still printing total/latest/historical/legacy availability. Use
`RUN_ID=<id>` for a specific cycle and `SINCE=<iso-time>` for a time window.
Add `INCLUDE_LEGACY=1` only when intentionally reviewing old/missing-schema
rows. Hypothesis reports now separate generated queries from executed queries
and show query counts by `candidate_discovery`, `candidate_validation`, and
`market_confirmation`. Rejected validation samples include the query,
query-type, result title, provider/source, candidate symbol, result score, and
identity/catalyst rejection reason. The entity audit flags suspicious cases
where external catalysts such as OpenAI, Anthropic, SpaceX, Stripe,
Databricks, Anduril, or Figma appear as crypto candidate assets; those are
review diagnostics only, not promotion inputs.

When an Event Alpha cycle has market anomalies but `catalyst_queries=0`, check
the run ledger or daily brief `Catalyst Search Skip Reasons` section before
changing thresholds. Common reasons are `no_anomalies_over_threshold`,
`anomaly_identity_missing`, `provider_backoff`, `provider_unavailable`,
`runtime_budget_exhausted`, and `query_limit_zero`. These are diagnostics only:
they explain missing validation evidence and do not make a row alertable.
Hypothesis validation search has separate skip reasons, including
`no_hypotheses`, `low_confidence`, `no_candidate_assets`,
`provider_unavailable`, `provider_backoff`, `result_identity_rejected`,
`result_catalyst_missing`, and `result_score_below_threshold`.
RSS source intake also distinguishes one-feed `feed_failure` warnings from
provider-level `provider_failure`; a single blocked RSS feed should not imply
the entire public source bundle failed.

Notification delivery state is scoped by profile namespace for `notify_no_key`,
`notify_llm`, and `research_send`. Scoped keys look like
`event_alpha_notify:notify_no_key:last_sent:daily_digest` and
`event_alpha_notify:notify_no_key:sent_count:instant:YYYY-MM-DD`, so a no-key
digest or instant cap cannot block the LLM or research-send profile. Legacy
unscoped keys are left in place for migration review and are still used only by
the explicit `global` notification scope.

Before the first actual send, run the startup checklist:

```bash
make event-alpha-notification-checklist PROFILE=notify_no_key
make event-alpha-notify-go-no-go PROFILE=notify_no_key
make event-alpha-environment-doctor PROFILE=notify_no_key
make event-alpha-scheduler-status PROFILE=notify_no_key
make event-alpha-notification-slo-report PROFILE=notify_no_key
make event-alpha-notification-runs-report PROFILE=notify_no_key
make event-alpha-notification-inbox PROFILE=notify_no_key
make event-alpha-notify-fixture-smoke
RSI_EVENT_ALERTS_ENABLED=1 make event-alpha-telegram-recipient-check PROFILE=notify_no_key
```

For deeper LLM notification burn-in, use the scheduled target only after the
same guarded send checks:

```bash
make event-alpha-notify-llm-deep-scheduled
```

It uses the `notify_llm_deep` profile with bounded run/day LLM budgets, source
enrichment, optional CryptoPanic when the key is present, run locks, and the
same `RSI_EVENT_ALERTS_ENABLED=1` Telegram send guard.

The checklist reports `READY_TO_PREVIEW`, `READY_TO_NOTIFY_NOW`, blockers,
warnings, source readiness, provider backoff, cooldown meta keys, LLM budget,
artifact doctor status, and the next commands. Notification cycles also append
`event_alpha_notification_runs.jsonl` summary rows with due/sent lane counts,
heartbeat state, would-send counts, cooldown blocks, provider fail-fast blocks,
cycle-completed/partial-results flags, runtime-budget status, Telegram
readiness, and send-guard state.

`make event-alpha-notify-go-no-go PROFILE=notify_no_key` is the compact final
send check. It separates preview readiness from send readiness and shows
Telegram/send-guard state, fixed-clock blockers, run-lock state, provider
backoff, delivery/run-ledger writability, research-card path writability,
artifact doctor status, cooldowns, and the next command. It never sends.

`make event-alpha-environment-doctor PROFILE=notify_no_key` is the scheduled-run
environment check. It verifies the active profile, artifact namespace, writable
lock/delivery/run/card paths, Telegram presence (redacted), send guard, provider
source readiness, provider backoff, LLM provider/key readiness, clock mode, and
prints `READY_FOR_SCHEDULED_NOTIFY`.

`make event-alpha-scheduler-status PROFILE=notify_no_key` checks run freshness,
latest successful run age, latest delivery age, run-lock state, provider
backoff, health-guard status, and whether the scheduled Make target exists.
`make event-alpha-notification-slo-report PROFILE=notify_no_key` summarizes
notification SLO state as `OK`, `NO_SEND_CONFIG`, `DEGRADED`, `STALE`, or
`BLOCKED` with the next operator action. Would-send preview rows
(`send_requested=false`) are reported as preview evidence, not delivery
failures. Send-requested rows with the send guard disabled are `NO_SEND_CONFIG`,
not Telegram outages. Only send-requested, guard-enabled rows that fail delivery
become alertable delivery failures.

Use the emergency pause when you want discovery/reporting to continue while
blocking Telegram delivery:

```bash
make event-alpha-pause-notifications PROFILE=notify_no_key REASON="operator pause"
make event-alpha-resume-notifications PROFILE=notify_no_key CONFIRM=1
```

Paused sends write blocked delivery rows with `error_class=notifications_paused`.
The env-level stop switch is `RSI_EVENT_ALPHA_NOTIFICATIONS_PAUSED=1` with an
optional `RSI_EVENT_ALPHA_NOTIFICATIONS_PAUSE_REASON`.

The notification inbox joins notification run rows, alert snapshots, research
cards, and feedback artifacts for one profile namespace. It shows sent
notifications without feedback, would-send items without feedback, would-send
items blocked by send guard, unreviewed high-priority and triggered-fade cards,
exploratory digest items needing review,
heartbeat-only runs, duplicate/in-flight suppressed runs, and provider degraded
runs. Duplicate and in-flight skips are not treated as fresh unreviewed alerts.
Each alert row includes a feedback helper command such as
`make event-feedback-useful PROFILE=notify_no_key FEEDBACK_TARGET='ea:...'`.

Use `make event-alpha-telegram-recipient-check PROFILE=notify_no_key` after
configuring Telegram and the send guard. It sends a tiny research-only
diagnostic to each configured/subscribed recipient, reports delivered/failed
counts, and prints only redacted chat summaries. If one recipient fails, remove
or fix it before relying on scheduled notification burn-in.

Provider health has profile-scoped operator commands:

```bash
make event-alpha-provider-health-report PROFILE=notify_no_key
make event-alpha-provider-health-reset PROFILE=notify_no_key PROVIDER_KEY=gdelt:event_source CONFIRM=1
make event-alpha-provider-health-reset PROFILE=notify_no_key PROVIDER_ALL=1 CONFIRM=1
```

The reset command clears `disabled_until` and `consecutive_failures` only. It
does not call providers, send Telegram messages, trade, paper trade, or write
normal RSI signal rows. If you need a one-off force run without clearing the
health artifact, use:

```bash
make event-alpha-notify-no-key IGNORE_BACKOFF=1
```

That adds `provider_backoff_ignored_for_run` to the run/notification warnings
and still records a fresh provider failure if the provider fails again.

`make event-alpha-notify-fixture-smoke` is the local wiring check. It uses a
fake sender, fixture/test namespace, deterministic clock, and local artifact
writes only. It must not require Telegram env, live providers, paper trading,
normal RSI routing, or execution.

Notification profiles use a conservative runtime budget and provider behavior:
120 seconds max runtime, 5 second provider timeouts, one provider failure before
skip/backoff, DNS fail-fast, and partial-result continuation. If the runtime
budget is exhausted, the cycle records `notification_runtime_budget_exhausted`,
preserves partial results, and still writes heartbeat/run-summary artifacts.
Live CoinGecko market enrichment is fail-soft in notification mode: DNS/network
failures record `market_enrichment_live_fetch_failed`, update
`coingecko:market_enrichment` provider health, continue anomaly/discovery with
empty market rows, and still write run/notification ledgers. Any unexpected
pipeline exception becomes `notification_cycle_failed_soft: <ErrorClass>` and
should still produce a degraded heartbeat would-send when heartbeat is due.

Without `RSI_EVENT_ALERTS_ENABLED=1`, `make event-alpha-notify-no-key` and
`make event-alpha-notify-llm` still run the radar, write research artifacts, and
print a would-send summary. They do not deliver Telegram messages.

Notification targets use the production wall clock by default. The Makefile
only passes `RSI_EVENT_RESEARCH_NOW` into notification/profile/send targets when
you explicitly set `EVENT_RESEARCH_NOW=...`; fixture targets use
`EVENT_FIXTURE_NOW` instead. A fixed notification clock older than 24 hours or
more than 1 hour in the future blocks actual Telegram delivery unless
`RSI_EVENT_ALPHA_ALLOW_FIXED_NOW_FOR_NOTIFY=1` is set. Preview, checklist,
status, daily brief, and run-ledger rows show the active clock mode and fixed
clock age.

### Scheduled day-1 notifications (run lock + delivery ledger)

For unattended/cron-style operation, use the scheduled targets. They add a
per-profile run lock (so overlapping cron firings can't double-send or race lane
cooldown state) and an idempotent delivery ledger (so a retried/overlapping run
cannot re-send identical research content within the dedupe window). They use
real wall-clock time, fail soft on provider errors, and exit 0 on partial
provider failures (nonzero only on config/code errors).

```bash
make event-alpha-day1-start                                  # no-send readiness checks
RSI_EVENT_ALERTS_ENABLED=1 make event-alpha-send-test PROFILE=notify_no_key
RSI_EVENT_ALERTS_ENABLED=1 make event-alpha-notify-no-key-scheduled   # or event-alpha-notify-llm-scheduled
make event-alpha-notification-deliveries-report PROFILE=notify_no_key
make event-alpha-export-notification-pack PROFILE=notify_no_key
```

The run lock lives at `<namespace>/event_alpha_notify.lock`. A fresh lock makes
the next run skip safely (recorded as a skipped notification run with
`skipped_due_to_active_lock`); a stale lock (past
`RSI_EVENT_ALPHA_NOTIFY_LOCK_STALE_MINUTES`, or a dead holder PID on this host)
is recovered with a `stale_notification_lock_recovered` warning. Set
`RSI_EVENT_ALPHA_NOTIFY_ALLOW_OVERLAP=1` only to intentionally run concurrent
cycles.

Each lane send is recorded in
`<namespace>/event_alpha_notification_deliveries.jsonl` as `planned`/`sending`
then `delivered`/`partial_delivered`/`failed`, or
`skipped_duplicate`/`skipped_in_flight`/`blocked`. Deduplication uses stable
lane keys where available: alert lanes use namespace + lane + alert ids,
heartbeats use namespace + lane + day + health-status bucket, and daily digests
and exploratory digests use namespace + lane + day + digest bucket. The exact
message `content_hash` is still stored for audit and for backward compatibility
with older rows.
Recent non-terminal planned/sending rows with the same dedupe key/content hash
are treated as in-flight for
`RSI_EVENT_ALPHA_NOTIFICATION_IN_FLIGHT_GRACE_MINUTES` (default 10 minutes) so
overlapping jobs do not double-send. Failed rows and stale in-flight rows do not
block retry. Structured Telegram send attempts record redacted recipient and
chunk counts; partial delivery is recorded separately. By default
`RSI_EVENT_ALPHA_NOTIFICATION_PARTIAL_MARKS_COOLDOWN=1`, so a partial send marks
lane cooldown to avoid re-sending the same alert to recipients that already got
it. Set it to `0` only if you want partial sends to stay retryable without
cooldown. Cooldown is never marked after a dedupe-skip, in-flight skip, blocked
row, or zero-recipient failed send.
Inspect with `make event-alpha-notification-deliveries-report
PROFILE=notify_no_key`; `make event-alpha-notification-retry-failed
PROFILE=notify_no_key` lists failed deliveries (dry-run; `CONFIRM=1` required,
and automated resend is a documented TODO — re-run the scheduled cycle to
resend). The per-run lock/delivery summary also shows up in
`make event-alpha-notification-runs-report`, the daily brief, and the artifact
doctor (which warns on failed deliveries).

`make event-alpha-notify-go-no-go PROFILE=notify_no_key` also prints the
operator follow-up commands: provider health report, provider reset when any
provider is in backoff, delivery report, and notification inbox. Use the inbox
after every partial delivery because those alerts need both delivery review and
normal useful/junk/watch feedback if any recipient received the message.

## Daily No-Key Operation

Use the no-key profile when you want public RSS/GDELT/Polymarket plus live
CoinGecko-style market rows without OpenAI calls:

```bash
make event-alpha-preflight PROFILE=no_key_live
make event-alpha-daily-report PROFILE=no_key_live
```

Preflight resolves the profile namespace, checks that artifact directories can
be written, verifies provider/LLM/send guard state, and recommends the next
command. The daily report then prints profile status, runs the cycle, writes
alert snapshots and run-ledger rows, prints router output, and summarizes alert
snapshots. If no alerts arrive, run:

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

## Artifact Hygiene

Profile-specific burn-in and readiness reports count only rows with explicit
`run_mode` and `artifact_namespace` metadata. Legacy/default rows from earlier
flat artifact files are ignored by default so a no-key burn-in, LLM burn-in, or
research-send review cannot borrow unrelated evidence.

Report commands that accept `--event-alpha-profile` resolve artifact paths from
that profile before loading rows. For example,
`python3 main.py --event-alpha-artifact-doctor --event-alpha-profile no_key_live`
reads `event_fade_cache/no_key_live/...` unless you intentionally pass
`--event-alpha-artifact-namespace` or an explicit path environment override.
Major reports print their resolved profile, namespace, run mode, run ledger path,
and alert store path at the top so the reviewed evidence is auditable.
For notification operations, prefer profile-aware commands such as
`python3 main.py --event-alpha-notification-runs-report --event-alpha-profile notify_no_key`
and leave `RSI_EVENT_ALPHA_NOTIFICATION_RUNS_PATH` blank unless you are
intentionally inspecting one explicit JSONL file.

Run the artifact doctor before judging a burn-in window:

```bash
make event-alpha-artifact-doctor PROFILE=no_key_live
STRICT=1 make event-alpha-artifact-doctor PROFILE=no_key_live
```

The doctor checks run-ledger to alert-snapshot lineage, missing matching
snapshot rows for alertable runs, external snapshot paths, orphan alerts,
mixed namespaces, provider health, budget rows, feedback/outcome IDs, and card
coverage. Strict mode escalates migration-tolerant warnings such as legacy
snapshot mismatches, mixed namespaces, missing live provider health, and unknown
feedback/outcome IDs into blockers.

For migration review only, include legacy/default rows explicitly:

```bash
INCLUDE_LEGACY=1 make event-alpha-burn-in-scorecard PROFILE=no_key_live
INCLUDE_LEGACY=1 make event-alpha-artifact-doctor PROFILE=no_key_live
```

Do not use legacy-included reports as promotion evidence. They are for
understanding older artifacts while new namespaced burn-in rows accumulate.

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

The OpenAI-backed profiles have bounded defaults, but the owner machine may
raise LLM depth through local `.env` budget overrides without editing profile
code:

```bash
RSI_EVENT_LLM_MAX_CANDIDATES_PER_RUN=200
RSI_EVENT_LLM_EXTRACTOR_MAX_EVENTS_PER_RUN=300
RSI_EVENT_LLM_MAX_CALLS_PER_RUN=200
RSI_EVENT_LLM_MAX_CALLS_PER_DAY=1000
RSI_EVENT_LLM_MAX_ESTIMATED_COST_USD_PER_DAY=25
RSI_EVENT_LLM_ESTIMATED_COST_PER_CALL_USD=0.02
RSI_EVENT_LLM_CACHE_TTL_HOURS=24
```

`main.py --event-alpha-status --event-alpha-profile notify_llm` prints the
effective relationship candidate cap, raw-event extraction cap, run/day call
caps, estimated daily cost cap, cache TTL, and ledger path. These knobs only
change how many LLM relationship/extraction attempts can run; they do not change
alert scoring, send guards, normal RSI rows, paper/live writes, trading, or
`TRIGGERED_FADE` eligibility.

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
