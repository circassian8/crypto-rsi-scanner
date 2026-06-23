# DECISIONS

Durable project decisions live here so agents do not relitigate settled choices.
Use `DEVLOG.md` for chronological change details and this file for the lasting
decision, rationale, and revisit condition.

## Template

```
## YYYY-MM-DD - <decision title>
**Status:** accepted | rejected | superseded
**Decision:** what we will or will not do.
**Why:** concise rationale.
**Revisit when:** concrete condition for reopening. Optional.
```

---

## 2026-06-23 - Store impact hypotheses as audit artifacts, not alert eligibility
**Status:** accepted
**Decision:** Event Alpha impact hypotheses are persisted as profile-scoped
JSONL research artifacts (`event_impact_hypotheses.jsonl`) with run/profile/
namespace metadata, candidate provenance, validation status, search queries,
validation/rejection reasons, flattened validated symbol/coin-id fields, and
promoted watchlist keys when validation links a hypothesis to a watchlist row.
LLM-extracted assets may populate `suggested_candidate_assets` and drive
validation-search metadata, but only deterministic resolver/search identity
validation may populate token-level validated candidates. `notify_llm` may fetch
bounded full-source text for LLM context; `notify_no_key` stays no-key/no-full-
source enrichment by default.
**Why:** Operators and external reviewers need to inspect why the radar formed
an impact hypothesis and why it did or did not validate without confusing loose
sector intelligence with alertable token evidence.
**Revisit when:** Reviewed burn-in data shows persisted hypothesis provenance is
insufficient for debugging missed opportunities or when a separate validated
promotion policy is approved.

## 2026-06-23 - Keep impact matching exact and sector hypotheses non-token until validation
**Status:** accepted
**Decision:** Event Alpha impact hypotheses must use boundary/phrase-aware
category matching rather than substring matching, and broad sector/venue/
infrastructure hypotheses must remain non-token watchlist rows until separate
source evidence validates a specific asset identity. Candidate symbols may be
stored as metadata and used for validation searches, but unvalidated hypotheses
render as `SECTOR` rows. Validation search can promote a hypothesis to token
scope only after identity-safe evidence links the candidate asset to the
catalyst/sector.
**Why:** Substring matches (`match`/`matched`, `open`/`OpenAI`, generic `hype`,
publisher/source words) and eager sector-to-token rows can make the radar look
more certain than the evidence supports. The system should discover broadly but
promote narrowly.
**Revisit when:** A reviewed validation sample proves that a specific category
can safely create token-level hypotheses without separate validation evidence.

## 2026-06-23 - Treat source/search failures as observability, not eligibility
**Status:** accepted
**Decision:** Event Alpha source-intake and catalyst-search failures should be
recorded with explicit reason codes (`feed_failure`, `provider_failure`,
`provider_unavailable`, `provider_backoff`, `no_anomalies_over_threshold`,
`anomaly_identity_missing`, `runtime_budget_exhausted`, `query_limit_zero`,
`unknown`) and surfaced in reports/briefs. These reason codes explain missing
evidence or zero-query runs, but they do not promote rows, create watchlist
eligibility, create `TRIGGERED_FADE`, write paper/live rows, or alter normal RSI
routing.
**Why:** Operators need to distinguish “nothing interesting found” from “search
was skipped or blocked” without letting provider/error metadata become signal
logic.
**Revisit when:** Catalyst-search reliability data is sufficient to automate
provider failover or budget allocation with a reviewed policy.

## 2026-06-23 - Keep impact hypotheses below alert eligibility until validated
**Status:** accepted
**Decision:** Event Alpha may generate impact hypotheses that infer which
crypto sectors/assets an external catalyst could affect, persist them as
`HYPOTHESIS` watchlist rows, show them in exploratory digests, and generate
targeted validation searches. Unvalidated hypotheses are store-only research
evidence and are not alertable. A hypothesis can promote to `RADAR` only after
identity-safe source evidence explicitly links a candidate asset to the
catalyst/sector. Hypotheses cannot create `WATCHLIST`, `HIGH_PRIORITY`,
`TRIGGERED_FADE`, paper trades, normal RSI signal rows, or execution by
themselves; `TRIGGERED_FADE` remains reserved for `event_fade.py` plus
`proxy_fade`.
**Why:** The radar needs to reason about external catalyst impact before exact
asset validation exists, but promoting loose sector guesses into alerts would
reintroduce false positives.
**Revisit when:** A reviewed sample shows that validated hypotheses reliably
lead to useful RADAR/WATCHLIST candidates and a separate promotion policy is
approved.

## 2026-06-22 - Keep exploratory notification digest separate from alertable lanes
**Status:** accepted
**Decision:** Event Alpha may send a separate `exploratory_digest` during
day-1 notification burn-in for suppressed, store-only, or raw-evidence rows that
are useful for operator learning. The lane has its own cooldown/dedupe state and
must remain separate from `daily_digest`, `instant_escalation`, `triggered_fade`,
and heartbeat lanes. Exploratory rows are not alertable decisions, are not alert
snapshots unless a future explicit artifact policy says otherwise, and cannot
create `TRIGGERED_FADE`, paper trades, live signal rows, or execution. Source
noise and ticker-collision controls stay excluded by default unless the operator
explicitly enables control inclusion.
**Why:** Day-1 operators need to see why the radar is suppressing candidates and
learn from missed/weak rows without promoting them into research alerts or
confusing them with delivery failures.
**Revisit when:** Reviewed feedback shows the exploratory lane is either too
noisy to be useful or mature enough to become a separate sampled-control artifact
with explicit retention and review policy.

## 2026-06-20 - Treat no-send previews separately from delivery failures
**Status:** accepted
**Decision:** Event Alpha notification SLO reports distinguish intentional
would-send previews (`send_requested=false`) and send-guard/config blocks from
actual delivery failures. Preview rows may warn but do not count as alertable
delivery failures. Send-requested rows with `send_guard_enabled=false` classify
as `NO_SEND_CONFIG`, not a Telegram outage. `BLOCKED` is reserved for
send-requested, guard-enabled rows with failed alertable delivery or repeated
sender-side delivery failures.
**Why:** Day-1 operators need to know whether the system found something it
would have sent, versus whether Telegram delivery failed. Treating no-send
previews as outages makes normal dry runs look broken.
**Revisit when:** Notification rows gain recipient-level retry state or a
separate operator dashboard replaces the current SLO text report.

## 2026-06-20 - Scheduled Event Alpha notifications need operator guardrails
**Status:** accepted
**Decision:** Day-1 scheduled Event Alpha notification operations must expose
redacted, profile-aware environment readiness, scheduler freshness, SLO health,
and clean artifact export reports before being treated as unattended research
infrastructure. A namespace-scoped emergency pause file, plus optional
`RSI_EVENT_ALPHA_NOTIFICATIONS_PAUSED=1`, blocks Telegram delivery while still
allowing discovery/report artifacts and blocked delivery rows to be written with
`error_class=notifications_paused`.
**Why:** Once launchd/cron runs notifications daily, failures need to be
operator-visible without forcing a live send or hiding audit evidence. The pause
switch gives the human a safe stop lever without disabling the whole research
pipeline.
**Revisit when:** Event Alpha notifications graduate beyond day-1 research
burn-in, or when recipient-level retry/resend is implemented.

## 2026-06-20 - Guard scheduled Event Alpha notifications with a run lock and delivery ledger
**Status:** accepted
**Decision:** Scheduled day-1 Event Alpha notification cycles use a per-profile
run lock and an idempotent, content-hashed delivery ledger. A fresh lock makes an
overlapping cycle skip safely (recorded as a skipped notification run); a stale
lock (past the stale window, or a dead holder PID on this host) is recovered with
a warning; the lock is released on completion and a crashed run is recovered by
the next run. Each lane send is recorded
(planned/sending/delivered/partial_delivered/failed/skipped_duplicate/
skipped_in_flight/blocked). Delivery records carry a stable lane-specific
`dedupe_key` plus an exact `content_hash`: alert lanes dedupe by namespace/lane/
alert id, heartbeat dedupes by namespace/lane/day/health bucket, and daily digest
dedupes by namespace/lane/day/digest bucket. Existing records without a
`dedupe_key` still fall back to `content_hash`. Identical delivered research
content/key within the dedupe window is skipped, and identical content/key with a
recent non-terminal planned/sending row is treated as in-flight and skipped for
the grace window. Failed rows and stale in-flight rows do not block retry.
Structured send attempts record recipient/chunk delivery counts. Partial
delivery is distinct from failed delivery and marks cooldown by default via
`RSI_EVENT_ALPHA_NOTIFICATION_PARTIAL_MARKS_COOLDOWN=1` so successful recipients
do not receive duplicate alerts; setting it to `0` keeps partial deliveries
retryable without marking cooldown. Cooldown is never marked after a dedupe-skip,
in-flight skip, blocked row, or zero-recipient failed send. Lock/delivery state is
metadata only: it never sends, trades, paper trades, writes normal RSI signal
rows, or creates `TRIGGERED_FADE` (still reserved for `event_fade.py` +
`proxy_fade`). Automated resend of failed deliveries is intentionally a
documented TODO because the ledger stores redacted metadata only.
**Why:** Cron/launchd notify runs can overlap or retry; without a lock and a
delivery ledger they could double-send a research digest or race lane cooldown
state. Idempotent delivery is a prerequisite for trustworthy unattended operation.
**Revisit when:** We want automated retry/resend, multi-host locking, recipient-
level Telegram acknowledgements beyond current best-effort send wrappers, or a
notification surface beyond the per-profile deliveries report and Codex's inbox.

## 2026-06-20 - Keep provider backoff overrides explicit and local
**Status:** accepted
**Decision:** Event Alpha notification provider-health backoff can be inspected
and reset through profile-scoped report/reset commands, and a notification run
may opt into one-shot `IGNORE_BACKOFF` / `--ignore-provider-backoff`. Reset
commands clear only `disabled_until` and `consecutive_failures` in the selected
research artifact namespace. One-shot ignore does not clear the provider-health
file, and successful forced attempts do not mark the provider healthy; fresh
failures are still recorded.
**Why:** Day-1 operations need a practical way to recover from stale public
provider backoff without hiding historical failures or silently promoting
unhealthy sources.
**Revisit when:** Provider reliability history is sufficient to replace manual
backoff reset/force-run with a reviewed automatic recovery policy.

## 2026-06-20 - Keep notification ops profile-aware and review-first
**Status:** accepted
**Decision:** Day-1 Event Alpha notification reports and feedback helpers should
resolve artifacts from the requested profile/namespace by default, while
explicit CLI/env path overrides remain intentional one-file inspections.
Operator inboxes join notification runs, alert snapshots, research cards, and
feedback rows to show unreviewed sent/would-send items and degraded runs. The
fixture notification smoke must use only deterministic fixture/test artifacts
and a fake sender; it must not require Telegram, live providers, paper trades,
normal RSI routing, or execution.
**Why:** Notification burn-in needs fast operational review loops without
mixing profile artifacts or accidentally exercising live delivery/provider
paths during smoke checks.
**Revisit when:** Notification burn-in is promoted and a different reviewed
handoff surface replaces manual feedback/card review.

## 2026-06-20 - Keep Event Alpha notification clocks production-safe
**Status:** accepted
**Decision:** Fixture-oriented Event Alpha and event-fade Make targets use
`EVENT_FIXTURE_NOW` for deterministic checked-in artifacts, while profiled,
burn-in, notification, and send targets leave `EVENT_RESEARCH_NOW` blank by
default and therefore use wall-clock UTC. Operator-facing Event Alpha status,
preflight, notification checklist/preview, daily brief, and run-ledger rows
must disclose clock mode and fixed-clock age. Actual notification sends are
blocked when an explicitly fixed research clock is older than 24 hours or more
than 1 hour in the future unless
`RSI_EVENT_ALPHA_ALLOW_FIXED_NOW_FOR_NOTIFY=1` is set.
**Why:** Day-1 notifications need production-clock cooldowns, daily caps, and
fresh event windows by default. Fixture reproducibility is still useful, but it
must not silently freeze live notification delivery to an old date.
**Revisit when:** Notification burn-in is promoted into a separately approved
research-send workflow with its own scheduling and replay controls.

## 2026-06-20 - Fail soft Event Alpha notification provider/runtime failures
**Status:** accepted
**Decision:** Day-1 Event Alpha notification cycles must treat live provider
and runtime failures as degraded research output, not process-fatal failures.
Live CoinGecko market enrichment in notification mode returns empty rows with
`market_enrichment_live_fetch_failed`, records role-specific provider health,
and lets discovery/anomaly/watchlist reporting continue. Unexpected pipeline
exceptions become `notification_cycle_failed_soft: <ErrorClass>` and still
write run/notification ledgers plus heartbeat would-send/sends when due. The
preview/checklist surfaces provider backoff and separates preview readiness
from send readiness.
**Why:** The owner wants immediate day-1 notifications even when public no-key
sources or CoinGecko are flaky, while preserving a visible degraded state for
review.
**Revisit when:** Notification burn-in has enough clean provider-health and
feedback history to decide whether any provider failures should block specific
lanes instead of only degrading heartbeat/run state.

## 2026-06-19 - Scope Event Alpha notification state by burn-in namespace
**Status:** accepted
**Decision:** Day-1 Event Alpha notification state for `notify_no_key`,
`notify_llm`, and `research_send` is namespace-scoped by default. Lane
cooldowns, daily instant counts, heartbeat cooldowns, and triggered-fade
dedupe use scoped metadata keys, while the explicit `global` scope preserves
legacy unscoped behavior for migration review. Notification cycles may
fail-fast unhealthy providers, preserve partial results, and write compact
notification-run summaries, but they remain research-only and day-1
unvalidated. `TRIGGERED_FADE` still requires deterministic `event_fade.py`
output on `proxy_fade`; LLM output cannot create it.
**Why:** The owner wants immediate notifications from separate burn-in
profiles without one profile suppressing another or unhealthy public sources
stalling the whole cycle.
**Revisit when:** Reviewed notification artifacts justify promoting one
profile into calibrated research send with different delivery rules.

## 2026-06-19 - Allow day-1 Event Alpha notifications without trading trust
**Status:** accepted
**Decision:** Event Alpha may send clearly labeled day-1 research
notifications through `notify_no_key` and `notify_llm` profiles when the
operator explicitly passes the send flag and sets `RSI_EVENT_ALERTS_ENABLED=1`
with Telegram credentials. Notification burn-in is distinct from calibrated
research send and trading readiness: lane-specific cooldown state may deliver
daily digests, instant escalations, deterministic proxy-fade triggered fades,
and health heartbeats, but every message must say it is unvalidated research and
not a trade signal. `TRIGGERED_FADE` remains reserved for deterministic
`event_fade.py` output on `proxy_fade` rows; LLM output may provide advisory
metadata only.
**Why:** The owner wants immediate operational visibility from the radar while
the system continues collecting burn-in evidence before any calibrated trust or
trading workflow.
**Revisit when:** Notification burn-in artifacts, feedback, provider health, and
outcomes are sufficient to decide whether calibrated research send should have
different thresholds or delivery rules.

## 2026-06-19 - Keep Event Alpha artifact namespaces isolated and report-only
**Status:** accepted
**Decision:** Event Alpha profile, run-mode, and namespace metadata are required
for burn-in-safe artifact handling. Profiled runs should write under isolated
artifact namespaces by default, run-ledger rows and alert snapshots should carry
joinable run/profile/namespace lineage, and burn-in/readiness/health reports
should ignore `test`, `fixture`, `replay`, and legacy/default rows unless
explicitly asked to include them for migration review. Alertable run rows that
claim snapshot writes must have matching alert-snapshot rows in the inspected
store, while external snapshot paths are reported safely instead of read
implicitly. The artifact doctor may flag missing snapshots, orphaned rows, mixed
namespaces, missing provider/budget evidence, unknown feedback/outcome IDs, and
card lineage gaps; strict mode may escalate migration-tolerant warnings into
blockers, but it is still a reporting tool only. Profile-aware reports must
resolve artifact paths from the requested profile/namespace before loading rows,
disclose those paths in output, and use preflight only as a blocker/warning
report, never as a promotion or send mechanism.
**Why:** Shared flat artifacts made it too easy for fixture/test rows to pollute
operational burn-in evidence or for alertable runs to lose snapshot lineage.
The radar needs auditable local files before any human can judge readiness.
**Revisit when:** Artifact namespaces and doctor checks have accumulated enough
clean burn-in history to simplify or automate review-pack generation without
weakening the research-only boundary.

## 2026-06-19 - Keep Event Alpha v1 gates report-only
**Status:** accepted
**Decision:** Event Alpha v1 readiness flags, health guard statuses, weekly
tuning worksheets, lifecycle timelines in research cards, clean burn-in export
packs, and schedule templates are operations/reporting tools only. They may
summarize artifacts, recommend next commands, export clean review packets, and
identify stale/degraded burn-in state, but they must not enable sends, change
alert tiers, apply priors, mutate watchlist state, create `TRIGGERED_FADE`,
write normal RSI signal rows, paper trade, or execute.
**Why:** Daily burn-in needs explicit pass/fail gates and handoff artifacts, but
those gates are safer as auditable operator checks rather than hidden promotion
logic.
**Revisit when:** A reviewed burn-in period has enough feedback, outcomes,
missed-opportunity rows, source reliability, and human approval to promote a
specific research-send workflow separately.

## 2026-06-19 - Keep Event Alpha burn-in checklist as a readiness gate only
**Status:** accepted
**Decision:** Event Alpha profile-matched latest-run selection, artifact
coverage diagnostics, replay candidate diff tables, monitor context in research
cards, explicit profile artifact policies, and the burn-in acceptance checklist
are operator-readiness tools only. They may explain whether research-send
burn-in is ready, blocked, or missing artifacts, but they must not enable
sends, change alert tiers, apply priors, mutate watchlist state, write normal
RSI signal rows, paper trade, or execute.
**Why:** Burn-in readiness needs a single, auditable operational surface. That
surface is safer when it reports blockers and next actions without becoming an
authority for alert promotion.
**Revisit when:** A reviewed burn-in period has enough feedback, outcome, missed
opportunity, and source-reliability evidence to justify a separate
human-approved research-send promotion.

## 2026-06-19 - Keep Event Alpha burn-in polish research-only
**Status:** accepted
**Decision:** Event Alpha profile-aware daily reports, service/role provider
health, active watchlist derivative/supply refresh, replay policy comparison,
stable routed `alert_id`/`card_id` references, auto-written research cards, and
burn-in scorecards are operational research tools only. Watchlist enrichment
may mark material update hints such as derivatives heating or supply pressure,
but those hints must route through the existing watchlist/router policy and
must not create `TRIGGERED_FADE`. Replay comparisons and burn-in scorecards
must read local artifacts and report recommendations only; they must not
change thresholds, send alerts, write live signal/paper rows, open paper
trades, or execute.
**Why:** The radar is now mature enough for daily burn-in, but operational
visibility and comparison tooling would be unsafe if it silently became signal
authority.
**Revisit when:** Burn-in artifacts, feedback, missed-opportunity rows, and
outcomes show durable playbook/source value and the human explicitly approves a
separate promotion.

## 2026-06-19 - Keep Event Alpha replay, priors shadow, and provider health advisory-only
**Status:** accepted
**Decision:** Event Alpha may wrap live event-source, catalyst-search,
CoinGecko-universe, and derivatives-enrichment providers with local
health/backoff state; run targeted CoinGecko watchlist market refresh for
active research rows; compare calibration priors in shadow; and replay raw
event evidence through local discovery/alert/watchlist/router stages. These
paths are operations and comparison tools only. Provider backoff must fail soft,
targeted market refresh must be evidence only, priors shadow must not write
snapshots, and replay must not call live providers, send Telegram, write live
DB rows, open paper trades, or execute. `TRIGGERED_FADE` remains reserved for
deterministic `event_fade.py` output on `proxy_fade` rows.
**Why:** Daily operation needs policy-comparable diagnostics and safer provider
behavior, but replay/prior/health tooling would be dangerous if it silently
became alert or trading authority.
**Revisit when:** A reviewed Event Alpha sample and explicit human approval
justify promoting a specific replay/prior/provider signal into a separate
research-digest or paper-tracking workflow.

## 2026-06-19 - Keep Event Alpha daily-ops automation bounded and local
**Status:** accepted
**Decision:** Event Alpha may run targeted active-watchlist market refresh,
provider health circuit breakers, opt-in calibration-prior application, daily
brief generation, shorthand feedback labels, local artifact replay, and
retention pruning. Calibration priors may adjust research alert ranking only
when `RSI_EVENT_ALPHA_APPLY_PRIORS=1`, with bounded multipliers and audit fields.
They must not create `TRIGGERED_FADE`, bypass source-noise/identity gates, write
normal RSI signals, paper trade, or execute. Provider health may skip/back off
live research providers fail-soft, but fixture/eval paths must stay
deterministic. Retention pruning is dry-run unless explicitly confirmed.
**Why:** The radar needs to be usable daily without accumulating stale artifacts
or repeatedly hammering unhealthy providers, but daily operations must not become
hidden trading or signal authority.
**Revisit when:** Reviewed Event Alpha evidence supports a separate
human-approved promotion from local research operations into an alerting or
paper-tracking workflow.

## 2026-06-19 - Keep Event Alpha self-improvement artifacts review-only
**Status:** accepted
**Decision:** Event Alpha may centralize asset-identity matching, refresh active
watchlist rows from already-available market rows, explain the last run, report
source reliability, export calibration priors, export proposed eval cases from
feedback/missed rows, and write Markdown research-card files. These artifacts
are review and operations tools only. Exported priors and proposed eval cases
must not be applied automatically, canonical fixtures must not be modified by
export commands, and watchlist market refreshes must route only through the
existing research router. None of these paths may create `TRIGGERED_FADE`,
normal RSI alerts, paper trades, live signal rows, or execution.
**Why:** The radar needs an operator feedback loop and better diagnostics, but
self-calibration and generated eval proposals are unsafe if they silently become
alert authority.
**Revisit when:** Reviewed Event Alpha artifacts show a source/playbook/prior
change is durable enough for a separate human-approved implementation.

## 2026-06-18 - Route Event Alpha monitor updates through the router only
**Status:** accepted
**Decision:** Active watchlist monitoring may be integrated into
`--event-alpha-cycle` only as an opt-in research update source. Monitor hints
such as `EVENT_TIME_APPROACHING`, `EVENT_PASSED`, `DERIVATIVES_HEATED`,
`MARKET_SCORE_JUMP`, and `POST_EVENT_MONITORING` must be translated into the
existing watchlist/router material-change fields and routed through the same
daily/instant/triggered lanes and send guards as source-derived watchlist rows.
Monitor updates must not create normal event-alert candidates, bypass router
policy, write live signal/paper tables, or create `TRIGGERED_FADE`. Event Alpha
cycle send accounting should distinguish requested, attempted, successful,
delivered, and blocked sends in the run ledger.
**Why:** Daily operation needs to keep watching already-discovered candidates
even when no new article arrives, but repeated market updates are only safe if
they stay inside the existing research router and audit trail.
**Revisit when:** A reviewed Event Alpha sample justifies persisting monitor
state transitions or promoting routed research digests through a separate
human-approved decision.

## 2026-06-18 - Keep Event Alpha operational reports artifact-only
**Status:** accepted
**Decision:** Event Alpha may append a local cycle run ledger, print
profile-aware status, monitor active watchlist rows from market/derivatives
state, detect missed opportunities, summarize calibration by feedback/outcomes,
and render Markdown research cards. These outputs are operational research
artifacts only. They must not write live signal/paper tables, route normal RSI
alerts, open paper trades, execute orders, or create `TRIGGERED_FADE`.
Catalyst-search identity evidence must come from title/body/event text,
contract-address URL paths, or resolver/quote-validated LLM extraction; URL-only
and publisher/source-origin matches are explicit rejection reason codes.
**Why:** The radar needs daily operating visibility and a feedback loop, but
monitoring and calibration data can become dangerous if it silently turns into
alert authority. Keeping these paths artifact-only preserves auditability while
the system builds reviewed evidence.
**Revisit when:** A reviewed Event Alpha sample and human approval justify a
separate promoted research digest, paper-tracking, or threshold-calibration
workflow.

## 2026-06-18 - Require identity proof before catalyst-search attachment
**Status:** accepted
**Decision:** Dynamic catalyst-search results may attach to a market anomaly
only when the source evidence names the anomaly asset through a strong identity
signal: `$SYMBOL`, spot/perp pair format, exact project name or alias, contract
address, token/coin/crypto context, or a quote-validated LLM extraction that
the deterministic resolver validates to the same asset. Catalyst terms alone
must be capped below attachment confidence, and common-word symbols such as
HYPE, PRIME, OPEN, and BEAT must reject generic lowercase word matches.
Router lanes (`DAILY_DIGEST`, `INSTANT_ESCALATION`, `TRIGGERED_FADE`) are
research delivery metadata only; they do not create trading authority.
**Why:** The Event Alpha loop searches noisy public sources around hot assets.
Without identity proof, articles about IPO hype, publisher names, unrelated
listings, or generic market catalysts can attach to the wrong token and pollute
research alerts.
**Revisit when:** A reviewed Event Alpha sample shows the identity caps are too
strict for a specific source/playbook and a narrower, test-backed exception is
approved.

## 2026-06-18 - Treat catalyst-search live providers as scored evidence only
**Status:** accepted
**Decision:** Event Alpha catalyst search may use fixture, GDELT, project RSS,
CryptoPanic, and Polymarket providers, including comma-list composition and
profile presets. Provider rows must be scored and may be rejected before being
attached to anomalies. Accepted rows remain raw research evidence and still
must pass deterministic discovery, resolver, classifier, playbook, watchlist,
and router logic. Search providers and LLM outputs must not create alerts,
paper trades, live signal rows, orders, or `TRIGGERED_FADE`.
**Why:** Hot market anomalies need a practical “find the catalyst” loop, but
search hits are noisy and source/publisher/ticker false positives are common.
Scoring and lifecycle reporting make the loop operational while preserving the
existing safety boundary.
**Revisit when:** Reviewed Event Alpha alert snapshots show a provider/source
or result-score threshold should be promoted, calibrated, or routed differently
through a separate human-approved decision.

## 2026-06-18 - Keep dynamic catalyst search as evidence collection
**Status:** accepted
**Decision:** Event Alpha may run a research-only market-anomaly catalyst-search
loop that generates bounded search queries, collects fixture/provider source
evidence, attaches those source events to the anomaly, and then reruns normal
deterministic discovery, resolver, classifier, playbook, watchlist, and router
logic. Catalyst search results are raw evidence only: they must not create
alerts, paper trades, live signal rows, orders, or `TRIGGERED_FADE` by
themselves. LLM raw extraction budgets should be prioritized by anomaly
severity, source confidence, freshness, catalyst keywords, asset mention
quality, duplicate penalties, and recap/source-noise penalties rather than by
first-seen order.
**Why:** The radar needs to move from passive catalyst feeds toward a loop that
asks “why is this asset moving?” without allowing search hits or LLM text to
bypass identity validation or event-fade hard gates.
**Revisit when:** A live catalyst-search provider is added or reviewed Event
Alpha snapshots justify changing search from local evidence collection into a
promoted research digest input.

## 2026-06-18 - Preserve non-proxy accepted link kinds in event graph
**Status:** accepted
**Decision:** Event graph links should preserve accepted relationship kinds for
`proxy`, `direct`, `supply`, `derivatives`, and `infrastructure` rows. Cluster
confidence may count proxy/direct/supply/derivatives accepted links, but
infrastructure, source-noise, ticker collisions, ambiguous rows, and publisher
noise must not boost alert scoring. Explicit external proxy event types should
take precedence over loose listing keywords; only structured exchange/perp
listing event types should force listing playbooks.
**Why:** Event Alpha is a multi-playbook research radar, so the graph needs to
represent direct/listing/unlock/perp relationships without accidentally turning
context, infrastructure, or source noise into confidence boosts.
**Revisit when:** Reviewed alert snapshots show infrastructure or other
non-boosting link kinds have measurable value that deserves a separate
human-approved tier policy.

## 2026-06-18 - Make Event Alpha tiering playbook-first
**Status:** accepted
**Decision:** Event Alpha research-alert tiers should be resolved from the
deterministic playbook assessment first, with generic opportunity score used
only as a supporting cap/boost. Hard rejection gates still win for source noise,
ticker collisions, low asset-resolution confidence, low classifier confidence,
publisher/source-only evidence, and market recaps. `TRIGGERED_FADE` remains
reserved for `proxy_fade` rows that already have a `SHORT_TRIGGERED` signal
from `event_fade.py`; direct/listing/unlock/perp/security/anomaly playbooks can
produce research alert tiers but cannot trigger event-fade. Catalyst-cluster
confidence may help accepted asset rows, but it must not boost rejected/source
noise rows. Market-anomaly catalyst search remains offline scaffolding that
generates review queries and attaches supplied evidence only; attached evidence
must still pass normal discovery, resolver, classifier, and playbook logic.
Snapshot retention may be tuned with `RSI_EVENT_ALPHA_SNAPSHOT_POLICY` while
remaining artifact-only.
**Why:** The Event Alpha system is now a multi-playbook radar, not a generic
proxy-fade score table. Direct listings, unlocks, and perp listings need their
own evidence thresholds, while false positives and source-noise controls must
stay suppressed and all trigger authority must remain deterministic.
**Revisit when:** Reviewed Event Alpha alert snapshots show a playbook-specific
tier policy should be calibrated from measured outcomes or promoted through a
separate human-approved research digest/paper workflow.

## 2026-06-18 - Route Event Alpha sends through effective playbooks only
**Status:** accepted
**Decision:** `RSI_EVENT_LLM_EXTRACTOR_MODE=shadow` is analysis/report-only and
must not mutate raw event evidence. Only `advisory` mode may append
quote-validated extraction hints before deterministic discovery, and those
hints still require deterministic resolver validation. Event Alpha cycle sends
must use router-approved `alertable_decisions`, not raw event-alert digest
candidates. Alert reports, watchlist state, router decisions, snapshots, and
outcome analytics should use `effective_playbook_type` for operational
grouping while retaining `rule_playbook_type` for audit.
**Why:** The Event Alpha Radar is now an operational research-alert loop, so its
mode semantics, send boundary, and playbook identity need to be unambiguous.
This prevents shadow LLM analysis from changing inputs, prevents broad digest
rows from bypassing the router, and keeps LLM-advisory false-positive handling
auditable.
**Revisit when:** A reviewed Event Alpha sample justifies a human-approved
promotion beyond local/report or opt-in research digest behavior.

## 2026-06-18 - Keep Event Alpha alert snapshots artifact-only
**Status:** accepted
**Decision:** Event Alpha cycles may append research-only alert snapshots to
`event_alpha_alerts.jsonl`, and CLI/Make commands may report those rows or fill
1h/4h/24h/72h/7d plus MFE/MAE outcomes from local price fixtures. These
artifacts must not write live signal/outcome/paper tables, route normal RSI
alerts, open paper trades, execute orders, or affect event-fade eligibility.
**Why:** The radar needs a measurable history of what it surfaced, by playbook,
tier, LLM role, source, market-anomaly score, BTC regime, feedback label, and
outcome. Keeping that history in JSONL artifacts preserves auditability without
promoting the research sleeve into trading infrastructure.
**Revisit when:** Reviewed alert snapshots demonstrate stable value and the
human explicitly approves a separate promoted notification or paper-tracking
path.

## 2026-06-18 - Use catalyst clusters as Event Alpha research identity
**Status:** accepted
**Decision:** Event Alpha may cluster source variants by
`external_asset_slug + event_type + event_date_bucket` and use that cluster id
in watchlist keys. Clusters preserve all raw/source evidence and rejected asset
links, but they do not create candidates, alerts, trades, paper rows, or
event-fade eligibility.
**Why:** Repeated articles often describe the same catalyst in different words.
Stable cluster identity prevents watchlist fragmentation while keeping
source-noise and direct/non-proxy links auditable as controls.
**Revisit when:** Reviewed clusters show obvious over-merging across unrelated
catalysts or under-merging of the same dated event.

## 2026-06-18 - Allow LLM extraction hints upstream of deterministic resolution
**Status:** accepted
**Decision:** The unified Event Alpha cycle may run raw-event LLM extraction
before discovery resolution, append high-confidence quote-validated catalyst and
asset hints to raw evidence, and then rerun the normal deterministic
normalization, resolver, classifier, event-alert, watchlist, and local-router
path. Those hints are not candidates or alerts by themselves: asset links,
classifications, event-fade eligibility, and any `TRIGGERED_FADE` state must
still come from deterministic code and the pure `event_fade.py` engine.
**Why:** Relationship-only LLM analysis could reject false positives but could
not recover missed proxy assets that the deterministic resolver never saw. This
keeps the recall improvement while preserving quote checks and deterministic
identity validation.
**Revisit when:** A reviewed extraction sample shows the hints either add too
much resolver noise or are reliable enough to justify more structured resolver
features beyond appended evidence text.

## 2026-06-18 - Keep the unified Event Alpha cycle research-only
**Status:** accepted
**Decision:** `main.py --event-alpha-cycle` may orchestrate event discovery,
market anomalies, optional LLM relationship/extraction metadata, event-alert
ranking, watchlist refresh, and local router decisions in one command. It may
append research watchlist JSONL rows and, only when `--event-alert-send` plus
`RSI_EVENT_ALERTS_ENABLED=1` are both set, reuse the existing research digest
send path. It must not route normal RSI alerts, write live signal/outcome/paper
rows, open paper trades, execute orders, or let LLM output create
`TRIGGERED_FADE`.
**Why:** Operators need one coherent radar cycle for daily review, but the
system still has not proven Event Alpha edge through reviewed samples. The
cycle should reduce operational friction without silently promoting research
metadata into trading behavior.
**Revisit when:** Reviewed Event Alpha samples justify a human-approved
notification or paper-tracking promotion.

## 2026-06-18 - Allow deterministic clocks for event research commands
**Status:** accepted
**Decision:** Event discovery, event-alert, Event Alpha, LLM event-analysis,
event-fade fixture/export, cache-refresh, and review-bundle commands may use
`RSI_EVENT_RESEARCH_NOW` or CLI `--event-now` to run against a deterministic
UTC research timestamp. Fixture-oriented Make targets should pin that clock so
checked-in June 2026 event fixtures do not age out of lookback windows. Normal
RSI scans and production behavior continue to use wall-clock time unless a
research event command explicitly opts into the override.
**Why:** Event research fixtures, validation exports, and review bundles must be
reproducible across calendar dates. Without an injected clock, tests and
reports can fail or change meaning simply because the real date moved forward.
**Revisit when:** A unified Event Alpha pipeline centralizes all event/review
orchestration and can own a single clock injection point.

## 2026-06-18 - Keep Event Alpha feedback as review metadata
**Status:** accepted
**Decision:** Event Alpha feedback labels (`useful`, `junk`, `watch`, `missed`,
`traded_elsewhere`, `ignored`) may be appended to a local JSONL research
artifact and covered by offline golden evals. Feedback rows may reference latest
watchlist state when a row is known, or record a `missed` item when the radar
failed to capture something. Feedback must not mutate watchlist state, route
alerts, write live signal/outcome/paper rows, open paper trades, execute orders,
or affect event-fade eligibility.
**Why:** Lightweight labels make day-to-day radar quality measurable without
turning subjective review into hidden production logic.
**Revisit when:** A reviewed feedback sample is large enough to justify a
human-approved calibration pass for resolver/classifier/playbook thresholds.

## 2026-06-18 - Keep Event Alpha router local and artifact-only
**Status:** accepted
**Decision:** Event Alpha Radar routing may read latest watchlist JSONL state
and classify rows as store-only, duplicate-suppressed, local-report,
research-digest, high-priority-research, or triggered-fade-research decisions.
Those decisions are local/report metadata only. The router must not send
Telegram alerts, route normal RSI alerts, write live signal/outcome/paper rows,
open paper trades, execute orders, or allow any non-`proxy_fade` playbook to
route a triggered-fade research decision.
**Why:** The watchlist needs a deterministic way to decide what would be
surfaced if promoted, while avoiding a silent promotion from research state into
notifications or trading. Actual event-fade triggers remain owned by
`event_fade.py` and the reviewed-sample promotion gate.
**Revisit when:** A reviewed Event Alpha sample proves route decisions are
useful enough for a human-approved research digest or paper-tracking workflow.

## 2026-06-18 - Keep Event Alpha playbooks deterministic and non-triggering
**Status:** accepted
**Decision:** Event Alpha Radar playbooks may label research candidates as
`proxy_fade`, `proxy_attention`, `listing_volatility`,
`perp_listing_squeeze`, `unlock_supply_pressure`,
`airdrop_tge_sell_pressure`, `fan_sports_event`, `political_meme_event`,
`rwa_preipo_proxy`, `ai_ipo_proxy`, `security_or_regulatory_shock`,
`direct_event`, `infrastructure_mention`, `market_anomaly`,
`market_anomaly_unknown`, `source_noise_control`, or `ambiguous_control`, and
may attach score/action, hypothesis, verification, timing-window, and
invalidation metadata to reports, snapshots, and watchlist state. Playbooks
must not create `TRIGGERED_FADE`; only the `proxy_fade` playbook may preserve a
`SHORT_TRIGGERED` signal that was already emitted by the pure `event_fade.py`
engine. Direct/listing/unlock/sports/political/security playbooks may produce
research alerts, but they cannot become event-fade triggers.
**Why:** Playbooks make the research thesis auditable without giving the
classification layer authority to trade or bypass event-fade hard gates.
**Revisit when:** Reviewed Event Alpha samples show a playbook should be
promoted into a human-approved research digest or paper-tracking workflow.

## 2026-06-18 - Keep Event Alpha watchlist artifact-only
**Status:** accepted
**Decision:** Event Alpha Radar watchlist state may persist local JSONL rows for
research candidates, including first/last seen timestamps, source count, score
history, latest market/LLM context, state transitions, duplicate suppression,
and alertable-escalation metadata. It must remain a research artifact: it must
not route Telegram alerts, write live signal/outcome/paper rows, open paper
trades, execute orders, or allow watchlist state to create `TRIGGERED_FADE`.
**Why:** The radar needs memory so repeated articles/anomalies do not become
repeated prompts, but persistent state is not evidence of edge. Event-fade
triggers still come only from `event_fade.py` hard gates and reviewed validation
remains required before promotion.
**Revisit when:** A reviewed Event Alpha sample proves state escalations are
useful enough for a human-approved research digest or paper-tracking workflow.

## 2026-06-18 - Keep market anomalies evidence-only until catalyst validation
**Status:** accepted
**Decision:** Event Alpha Radar market enrichment may fill research candidate
market snapshots from CoinGecko-style fixture or explicitly enabled live market
rows. The market anomaly scanner may create local research raw events for hot
returns, volume/mcap spikes, or volume z-scores, but anomaly rows without
validated dated external catalyst/source evidence must stay store-only or local
radar evidence. They must not create event-fade proxy eligibility,
`TRIGGERED_FADE`, normal RSI alerts, live signal rows, paper trades, or
execution.
**Why:** Market anomalies can point review toward possible catalyst-driven
moves, but the proxy-fade thesis requires source evidence and deterministic
asset/catalyst validation. Hot coins alone would recreate the false-positive
"short every pump" failure mode.
**Revisit when:** A reviewed Event Alpha Radar sample shows anomaly-first rows
reliably lead to validated catalyst/proxy candidates and the human explicitly
approves a promoted watchlist or alert workflow.

## 2026-06-18 - Keep LLM raw-event extraction as resolver input only
**Status:** accepted
**Decision:** Event LLM raw-event extraction may run in `shadow` mode to propose
external catalysts, crypto asset/project mentions, source-noise terms, and date
hints from raw event evidence. Extracted assets are resolver hints only: they
must not create candidates, research-alert tiers, `TRIGGERED_FADE`, live signal
rows, paper trades, or execution unless deterministic resolver/classifier/event
fade gates validate the asset and event through the existing research path.
**Why:** Upstream extraction helps find missed proxy assets and diagnose source
noise, but LLM output still needs deterministic identity validation and quote
checks before it can influence research artifacts.
**Revisit when:** The extractor has a reviewed sample showing useful recall
improvement without unacceptable false-positive asset links, and the human
approves promotion into the event-alpha radar/watchlist pipeline.

## 2026-06-18 - Keep LLM advisory limited to research-alert tier quality
**Status:** accepted
**Decision:** Event LLM analysis may run in `shadow` mode for diagnosis or
`advisory` mode to adjust discovery-fed research-alert tiers only. Advisory mode
may demote source-noise, ticker-collision, direct-beneficiary, and
infrastructure false positives, and may preserve/raise high-confidence proxy
candidates within research-alert tiers, but it must never create
`TRIGGERED_FADE`, change `event_fade.py` eligibility, route normal RSI alerts,
write live signal/paper rows, open paper trades, or imply execution.
**Why:** The LLM catches semantic false positives that deterministic resolver
rules miss, but event-fade triggers and trading boundaries must remain
deterministic and validated.
**Revisit when:** A reviewed event-alert/event-fade sample shows advisory output
is reliable enough to become part of a promoted notification or paper-tracking
workflow, with explicit human approval.

## 2026-06-17 - Keep weak discovery evidence review-only
**Status:** accepted
**Decision:** Event discovery may keep low-confidence classifier matches,
low-confidence event-time rows, and `proxy_venue` rows in review artifacts, but
they must force `NO_TRADE` by default before event-fade signals can trigger.
`proxy_instrument` remains eligible if every hard gate passes; `proxy_venue`
requires explicit opt-in via `RSI_EVENT_FADE_ALLOW_PROXY_VENUE_TRIGGER=1`.
**Why:** Venue/platform mentions are noisier than true proxy instruments, and
source-text dates or weak classifications can make backtests look tradable when
the system would not have had strong enough evidence in real time.
**Revisit when:** A reviewed event-fade sample proves venue-token fades or
low-confidence timestamp/classification rows have durable edge after timing,
costs, and negative-control checks.

## 2026-06-16 - Classify event-fade asset roles before proxy eligibility
**Status:** accepted
**Decision:** Event discovery must distinguish the linked crypto asset's role
inside a proxy-style article. Only assets classified as the proxy instrument or
proxy venue/platform may remain `is_proxy_narrative=True`; background mentions,
chain/venue infrastructure, and ticker-word collisions become `proxy_context`
negative/control rows and must stay `NO_TRADE`.
**Why:** Public RSS evidence can mention BTC treasuries, chains such as Solana,
or common English words that collide with tickers inside otherwise valid
SpaceX/OpenAI-style proxy narratives. Treating those as proxy candidates would
pollute the validation sample and overstate discovery quality.
**Revisit when:** A reviewed event-fade sample shows the role taxonomy is too
strict or a stronger source-specific entity resolver replaces the deterministic
rules.

## 2026-06-16 - Allow observational event-discovery JSONL cache
**Status:** accepted
**Decision:** Event discovery may write local JSONL cache artifacts under the
configured `RSI_EVENT_DISCOVERY_CACHE_DIR` for raw events, normalized events,
asset links, classifications, candidate snapshots, and discovery-run metadata.
This cache is observational research storage only; it must not write live
signal/outcome/paper tables, route notifications, open paper trades, or imply
execution. Cached candidate snapshots may be exported back into the validation
sample schema for manual review, but only as requested local JSONL/CSV artifacts.
**Why:** The event-fade validation plan requires point-in-time evidence. Live or
refreshed providers are not useful for review/backtesting unless the system
preserves what was known, when it was observed, and which source supplied it.
**Revisit when:** Event-fade promotion is explicitly approved and the cache
needs migration to a reviewed SQLite research schema or a production data store.

## 2026-06-16 - Push after every commit
**Status:** accepted
**Decision:** Every change-making prompt ends with one commit on `main` and a
push to `origin/main`. The human gave standing approval to push after each
commit, superseding the older "no push without explicit approval" clause.
**Why:** GitHub is now the shared handoff point for Claude, Codex, and external
ChatGPT review, so commits should not remain local after a completed prompt.
**Revisit when:** The human revokes standing push approval, asks for PR branches,
or a future change would require force-pushing, changing remotes, or pushing to a
different branch.

## 2026-06-16 - Keep event fades alert-only until validated
**Status:** accepted
**Decision:** The event-fade engine is a separate research sleeve for dated
proxy-catalyst sell-the-news setups. It may score local fixtures and produce
alert-only reports, but it must not write live storage, route notifications,
open paper trades, or imply execution. Proxy eligibility is a hard gate:
direct-beneficiary or non-proxy events must remain `NO_TRADE` even if every
other score and post-event failure check is strong.
**Why:** The thesis is structurally different from the RSI overextension setup
registry and has not been validated across a historical/manual event sample.
The VELVET-style pattern requires catalyst, proxy, crowding, liquidity/supply,
and post-event failure evidence; generic overbought pumps are not enough.
**Revisit when:** A reviewed event dataset or backtest shows durable positive
post-event fade edge and the human explicitly approves live routing/paper
tracking.

## 2026-06-07 - Use DEVLOG as history while repo has no git
**Status:** superseded 2026-06-08 (see "Adopt local git + commit per change-making prompt")
**Decision:** Every non-trivial change must prepend an entry to `DEVLOG.md`,
signed by `Claude`, `Codex`, or `human`.
**Why:** There is no `.git` directory, so the written log is the shared history
for the human and AI collaborators.
**Revisit when:** The human explicitly initializes a git repo and decides how
commit history and `DEVLOG.md` should coexist.

## 2026-06-08 - Adopt local git + commit per change-making prompt
**Status:** accepted
**Decision:** The repo is a local git repo (branch `main`, no remote). Every prompt
that changes files ends with one commit (clear message, `make verify` green, no
secrets/artifacts). `DEVLOG.md` continues as the narrative/why log; git is the
diff/rollback history. No `git push` / remote without explicit human approval.
**Why:** Two agents edit the same files; git gives real diffs, blame, and rollback
a hand-maintained log can't. Human explicitly approved.

## 2026-06-07 - Do not initialize local git automatically
**Status:** superseded 2026-06-08 (human approved git; see above)
**Decision:** Agents may recommend local git, but must not run `git init` unless
the human explicitly asks for it.
**Why:** The current collaboration protocol is built around "no git"; changing
that workflow affects backups, diffs, and agent expectations.
**Revisit when:** The human asks to adopt local git.

## 2026-06-07 - Use the repo venv and standalone test runner
**Status:** accepted
**Decision:** Primary verification is `.venv/bin/python tests/test_indicators.py`
or `make verify`, not plain `python` or `pytest`.
**Why:** The shell's default Python can stall importing pandas here, and `pytest`
is not installed in the repo venv.
**Revisit when:** Dev dependencies include pytest and the default interpreter is
known-good.

## 2026-06-07 - Grade setups by their expected direction
**Status:** accepted
**Decision:** Outcomes are graded against each setup's `expected_dir`, not a
blanket mean-reversion convention.
**Why:** Overbought/oversold signals mean different things across trend regimes;
continuation setups were previously mislabeled.

## 2026-06-07 - Gate signal loudness by market regime
**Status:** accepted
**Decision:** Use BTC market-regime alignment to adjust conviction and demote
adverse setups out of loud routing.
**Why:** Backtests showed edge is regime-conditional; the useful part is firing
setups only in favorable regimes.

## 2026-06-07 - Keep breakdown_risk context-only
**Status:** accepted
**Decision:** `breakdown_risk` is shown as context but should not go loud or be
treated as an actionable edge.
**Why:** Backtests did not find positive edge for oversold-in-downtrend in any
market regime.
**Revisit when:** A materially better PIT backtest or live paper sample shows
positive edge.

## 2026-06-07 - Reject confirmation entry trigger for now
**Status:** rejected
**Decision:** Do not switch live entries from cross-into-zone to RSI confirmation
out of the zone.
**Why:** A/B backtest did not improve results and slightly hurt key setups.
**Revisit when:** A new trigger variant is specified and backtested against the
current baseline.

## 2026-06-07 - Signal registry is the setup source of truth
**Status:** accepted
**Decision:** `crypto_rsi_scanner/signal_registry.py` owns setup definitions,
expected directions, market eligibility, and backtested conviction priors.
Scanner, backtest, outcomes, paper trading, formatting, and storage migrations
should consume the registry instead of maintaining private setup maps.
**Why:** The same setup logic was spread across modules, making it easy for live
alerts, backtests, and reports to drift.
**Revisit when:** A richer registry schema is needed, but keep one source of
truth.

## 2026-06-07 - Conviction starts from measured edge priors
**Status:** accepted
**Decision:** Live and backtest conviction should start from registry edge priors
by setup and market alignment, with severity/confluence and mature live outcomes
nudging around that baseline.
**Why:** The old fixed severity-first heuristic did not predict edge in backtest.
This makes conviction answer "does this setup have measured edge here?" before
asking how visually stretched the coin is.
**Revisit when:** The paper scoreboard or stronger PIT backtests show the priors
need recalibration.

## 2026-06-07 - Registry calibration is explicit opt-in
**Status:** accepted
**Decision:** Backtest may export calibrated registry priors as JSON, but the
live scanner only loads them when `RSI_REGISTRY_PRIORS` points to that file.
Absent or invalid calibration falls back to checked-in registry defaults.
**Why:** Smoke runs and short-window backtests can produce noisy priors. The
artifact should be reviewable and intentional before affecting live alerts.
**Revisit when:** A routine calibration workflow with enough PIT/live evidence is
trusted enough to automate.

## 2026-06-07 - Keep alert render smoke in verification
**Status:** accepted
**Decision:** Representative alert rendering must be smoke-tested offline via
`make smoke-alerts`, and `make verify` runs that target.
**Why:** Render regressions can block notifications even when signal math passes;
the formatter needs coverage for Telegram HTML, plain fallback, macro headers,
digest caps, NaN handling, and edge-case symbols.
**Revisit when:** Rendering moves to a richer template/parser with equivalent
coverage.

## 2026-06-08 - Persist and expose scan health
**Status:** accepted
**Decision:** Live scans persist their latest operational status in SQLite meta,
and both `main.py --status` and the bot `/health` command render it through the
shared `status_report.py` formatter. The always-on listener also checks stale
successful scans and raises a heartbeat alert once per stale episode.
**Why:** A correct signal engine is not enough if the launchd scan silently stops,
degrades, or fails after fetching. One shared status source gives CLI, bot, and
watchdog paths the same view of scan freshness and last errors.
**Revisit when:** We add richer historical run tables or external monitoring.

## 2026-06-08 - Use SQLite online backup API
**Status:** accepted
**Decision:** DB backups must use SQLite's online backup API, verify the resulting
backup with `PRAGMA integrity_check`, and apply retention. Do not back up by
copying only `rsi_scanner.db`.
**Why:** The live DB runs in WAL mode and can have active scan/listener
connections; raw file copies can miss WAL contents or capture an inconsistent
state.
**Revisit when:** We move state storage away from local SQLite.

## 2026-06-08 - Keep ops maintenance repo-owned but schedule changes explicit
**Status:** superseded 2026-06-08 (human asked to do all suggested changes)
**Decision:** `main.py --status` reports backup freshness and log sizes;
`main.py --rotate-logs` copy-truncates oversized local logs; launchd helpers can
inspect scan/listener status and restart the bot listener by label. Agents should
not install or mutate launchd schedules/plists unless the human explicitly asks.
**Why:** The live Mac needs simple recovery/inspection commands, but changing
service schedules is machine state outside the repo and should remain deliberate.
**Revisit when:** The human wants a checked-in or installed maintenance
LaunchAgent for backups/log rotation.

## 2026-06-08 - Install daily repo-owned maintenance agent
**Status:** accepted
**Decision:** The repo owns `main.py --maintenance`, which creates a safe SQLite
backup, restore-checks it, and rotates logs. `make install-maintenance-agent`
installs/loads a daily launchd agent (`RSI_MAINTENANCE_LABEL`, default
`com.nasrenkaraf.rsimaintenance`) that runs this command.
**Why:** Backups and log rotation are operational controls, not one-off manual
commands. The human explicitly asked to do the scheduled-maintenance item.
**Revisit when:** Maintenance should move to an external scheduler/monitoring
system or the Mac deployment labels change.

## 2026-06-08 - Keep offline scanner fixture smoke checked in
**Status:** accepted
**Decision:** `RSI_FIXTURE_DIR` enables CoinGecko fixture mode, and
`make dry-run-fixture` uses checked-in sanitized fixtures under
`fixtures/coingecko_smoke`.
**Why:** Scanner plumbing can be validated quickly without spending API quota or
waiting on network/rate-limit behavior.
**Revisit when:** The fixture diverges from live API response shape or needs to
cover more signal cases.

## 2026-06-09 - Keep offline backtest fixture smoke in verification
**Status:** accepted
**Decision:** `make backtest-fixture` runs the default Binance-style backtest
path against checked-in BTC/ETH/SOL daily kline CSVs under
`fixtures/backtest_smoke`, and `make verify` includes that target.
**Why:** The backtester had strong unit coverage, but its CLI/default data path
still depended on Binance/network for a smoke run. A small fixture catches
parser, CLI, report, market-regime, and signal-walk regressions locally.
**Revisit when:** The fixture stops producing representative graded observations
or the default research data source changes.

## 2026-06-08 - Add market-state features shadow-first
**Status:** accepted
**Decision:** Keep RSI crossing/approach as the event trigger. New volatility,
breadth, relative-strength, beta, liquidity, and risk-state features must be
computed as pure, backtestable state context before any live conviction, routing,
or hard-gating change.
**Why:** The likely edge is RSI conditioned on market state, not generic indicator
stacking. Shadow-first features avoid silently overfitting live alert behavior.
**Revisit when:** PIT/base-rate-adjusted, cost-aware, walk-forward evidence
supports a specific state feature affecting conviction or routing.

## 2026-06-08 - Store live state snapshots observationally
**Status:** accepted
**Decision:** The live scanner may attach `state_json` and compact state buckets
to rows, alerts, signals, and paper-trade entries, but it must attach them after
`flag`, `setup_type`, `expected_dir`, `market_aligned`, `conviction`, and `tier`
are already computed.
**Why:** We need live/backtestable state labels to measure conditional edge, but
state features are not yet proven enough to affect alert routing or score.
**Revisit when:** State-conditioned PIT/live outcome analysis identifies a
specific feature/cohort with durable incremental edge over the existing registry
baseline.

## 2026-06-09 - Grade state slices against same-state base rates
**Status:** accepted
**Decision:** State-conditioned backtest slices must compare each signal cohort
against base days with the same coin trend regime and the same state bucket.
**Why:** High-volatility, breadth-collapse, or low-RS markets can have strong
base moves on their own. A state bucket only matters if the RSI setup beats what
normally happened in that same state.
**Revisit when:** A better causal/econometric benchmark replaces the current
same-regime, same-state base-rate comparison.

## 2026-06-09 - Do not promote first state-slice candidates live
**Status:** accepted
**Decision:** The 2026-06-09 current-top Binance state-slice review is research
evidence only. Do not alter live conviction, routing, or gating from it alone.
**Why:** The run found plausible cohorts, but it remains survivorship-biased,
single-venue, costless, and some cells are small. State buckets need PIT/live
confirmation before they can affect alerts.
**Revisit when:** Point-in-time state-slice backtests or mature live `state_json`
outcomes confirm a specific cohort with enough samples and positive incremental
edge over the same-regime, same-state base rate.

## 2026-06-09 - Cache raw PIT CoinGecko histories
**Status:** accepted
**Decision:** PIT backtests cache raw CoinGecko `market_chart` JSON under the
configured `RSI_BACKTEST_CACHE_DIR` (`backtest_cache` by default), and research
commands can disable or refresh that cache explicitly.
**Why:** PIT state-slice and calibration runs are rate-limit sensitive and can be
interrupted. Caching raw inputs lets runs resume and keeps derived parsing/report
logic reproducible without checking bulky data into git.
**Revisit when:** A better historical market-cap data source replaces CoinGecko
or the cache needs versioned schema metadata.

## 2026-06-09 - Treat first cached PIT state-slice run as bear-only evidence
**Status:** accepted
**Decision:** The cached 365d PIT state-slice run confirms only bear-regime
conditions. It supports continued monitoring of bear-regime `mean_reversion` and
continued rejection of `breakdown_risk`, but it does not justify live state
routing changes.
**Why:** The run used point-in-time membership and 128 usable histories, but the
available 365d CoinGecko window only produced BTC `BEAR` market-regime coverage.
Bull/chop state candidates from the 4-year Binance run remain unconfirmed.
**Revisit when:** Deeper PIT history includes bull/chop periods or live
`state_json` outcomes mature enough to test those cohorts directly.

## 2026-06-09 - Do not load the first PIT registry-prior export live
**Status:** accepted
**Decision:** `research/registry_priors_pit_2026-06-09.json` is a checked-in
research artifact only. Do not set `RSI_REGISTRY_PRIORS` to it for live scans.
**Why:** The 365d point-in-time run had only BTC `BEAR` market coverage. It moved
`mean_reversion.neutral` from 42 to 47 and `trend_continuation.neutral` from 42
to 40, but those neutral prior cells are broader than this bear-only evidence.
**Revisit when:** PIT history includes bull/chop coverage or mature live paper
outcomes validate setup-by-market prior cells directly.

## 2026-06-07 - Share universe hygiene across live and research
**Status:** accepted
**Decision:** `crypto_rsi_scanner/universe.py` owns CoinGecko market hygiene and
must be used by live scans and backtest top-N selection. Live scans also persist
the latest hygiene audit for review.
**Why:** Stablecoins, wrapped/staked receipts, stale listings, and illiquid
market-cap artifacts pollute alerts, outcomes, paper trades, and backtests.
Using one filter and persisted audit keeps live and research universes aligned
and makes false positives/negatives reviewable.
**Revisit when:** Logs show repeated false positives/negatives, or CoinGecko
metadata support allows a more precise category-based filter.

## 2026-06-09 - Exclude fiat, gold, and yield-pegged products from RSI universe
**Status:** accepted
**Decision:** Treat observed fiat/gold/yield-pegged products such as USD1, USDG,
USDtb, GHO, YLDS, USX, USYC, XAUT, and PAXG as `stable_like` universe
exclusions.
**Why:** The 2026-06-09 live hygiene audit showed these products surviving into
the kept top-100 even though they are not good directional crypto RSI candidates.
They add noise to alerts, paper trades, and backtests.
**Revisit when:** The audit shows a repeated legitimate asset being excluded by
these rules, or CoinGecko exposes reliable categories for stable/commodity/yield
products.

## 2026-06-09 - Refresh universe audits without full scans
**Status:** accepted
**Decision:** `main.py --refresh-universe-audit` and `make refresh-universe-audit`
may fetch the current CoinGecko market list, apply shared hygiene filters,
persist the audit, and print it without running RSI analysis or notifications.
**Why:** Hygiene tuning needs fast feedback. A full scan spends more API calls,
touches scanner bookkeeping, and performs unrelated RSI work when only the
market-list filter changed.
**Revisit when:** CoinGecko rate limits make even market-list-only refreshes too
expensive or audit persistence moves out of local SQLite/files.

## 2026-06-09 - Keep cost and walk-forward outputs research-only
**Status:** accepted
**Decision:** Backtest `--costs` and `--walk-forward` reports are required
research diagnostics before promoting a calibration, but they do not alter live
conviction, routing, or gating by themselves.
**Why:** Costs, slippage, capacity, and temporal stability can invalidate a thin
headline edge. They should be visible in research output without silently
changing live behavior.
**Revisit when:** A specific cost-aware, walk-forward-supported rule is proposed
and documented for live promotion.

## 2026-06-09 - Mark notification state only after delivery
**Status:** accepted
**Decision:** Instant cooldowns and digest timestamps are updated only after at
least one notification channel reports success. Telegram alerts should be split
into multiple messages when needed instead of silently truncating cards.
**Why:** A transient Telegram/API failure should not suppress the next retry, and
large alert batches should not drop later cards while appearing delivered.
**Revisit when:** Delivery moves to an external queue with acknowledgements.

## 2026-06-09 - Keep live outcome maturation independent of today's universe
**Status:** accepted
**Decision:** Recent pending signal outcomes and open paper trades may fetch
extra daily histories for coins that are no longer in today's clean top-N
universe. Live outcome reports include actionable/control and market-alignment
cohorts, deriving alignment for older rows when needed.
**Why:** Gating and conviction cannot be judged honestly if outcomes disappear
when a coin leaves the current universe. The report needs to answer whether
surfaced signals beat the control set directly.
**Revisit when:** Outcome tracking moves to a provider-backed historical data
store or a dedicated run/outcome table with complete lifecycle states.

## 2026-06-07 - Do not exclude STX by symbol
**Status:** accepted
**Decision:** `stx` is not in the hard exclude list.
**Why:** Symbol-only filtering treated Stacks like a staked/wrapped receipt, but
it is a normal asset and should pass unless another hygiene rule excludes it.

## 2026-06-10 - Volume-rank PIT is the standard full-cycle research universe
**Status:** accepted
**Decision:** Conclusion-bearing backtest research uses `backtest --pit-volume`
(per-date top-N by trailing 30d dollar volume over the full Binance USDT pool).
The plain current-top Binance path is for quick smokes only; the CoinGecko mcap
`--pit` path remains as a cross-check (365d on the demo key).
**Why:** It is the only path that is simultaneously full-cycle (~5y, covering
bull/chop/bear) and point-in-time, with free, cacheable data. The 2026-06-10 run
(368 coins, 21,334 obs) confirmed the gating map and first validated conviction
monotonicity. Known residual biases (delisted pairs absent, single venue,
volume-rank ≠ live mcap universe) are documented in
`research/VOLUME_PIT_BACKTEST_2026-06-10.md`.
**Revisit when:** A historical market-cap source (Pro key or alternative) allows
a deep mcap-PIT comparison, or multi-venue data becomes available.
