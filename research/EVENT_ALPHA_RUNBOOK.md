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
LLM context, and bounded parallel OpenAI defaults: 100 calls/run, 500 calls/day,
$15/day estimated cap, 12 concurrent LLM calls, 30s LLM HTTP timeouts, 10
enriched source rows/run, a 168-hour cache TTL, and a 600s notification runtime
budget. Like `notify_no_key`, `notify_llm` sends operator-visible output on
every clean scheduled run; cooldown/content dedupe is disabled while the run
lock and in-flight delivery guard remain active. Use `notify_llm_deep` only
when you explicitly want a deeper review cycle: it keeps the same research-only
send guards and per-run delivery behavior but raises the LLM/enrichment caps to
250 calls/run, 1500 calls/day, 16 concurrent LLM calls, and 45s LLM timeouts.

Use `notify_llm_quality` when the task is to prove current signal-quality
artifact writers rather than deliver Telegram notifications. It uses the
`notify_llm` source/LLM/quality settings, writes under
`event_fade_cache/notify_llm_quality/`, uses wall-clock time, and has a
dedicated scheduled target that does **not** pass `--event-alert-send`:

```bash
make event-alpha-notify-llm-quality-scheduled
make event-alpha-notify-llm-quality-validation-cycle
make event-alpha-quality-live-smoke PROFILE=notify_llm_quality_fresh
make event-alpha-quality-coverage-report PROFILE=notify_llm_quality
make event-alpha-artifact-doctor PROFILE=notify_llm_quality STRICT=1
```

The coverage report reads raw JSONL rows for the latest run and checks that
hypothesis, watchlist, and alert-snapshot artifacts carry the canonical
top-level quality fields. A failing coverage report means the fresh writer path
needs patching; it is not a trading or notification promotion signal.
Use `make event-alpha-notify-llm-quality-validation-cycle` when you need a
fresh rebuild of the regular `notify_llm_quality` namespace without sending
Telegram messages. It clears `event_fade_cache/notify_llm_quality/`, runs the
guarded notify cycle without a send flag, then writes/prints the daily brief,
quality review, incident report, and strict artifact doctor output.

Use `make event-alpha-quality-live-smoke
PROFILE=notify_llm_quality_fresh` when stale `notify_llm_quality` artifacts are
suspected. It mirrors the `notify_llm_quality` source/LLM/quality settings but
writes to `event_fade_cache/notify_llm_quality_fresh/`, clears only that
namespace, uses wall-clock time, does not pass a fixture clock, does not pass
`--event-alert-send`, and then runs daily brief, quality review, incident
report, and strict artifact doctor. Treat this as the clean live-style proof
path for Pro-model review; `quality_validation` remains the isolated offline
fixture proof path.

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
promote to token-level `RADAR` only after identity-safe source evidence
explicitly links a candidate asset to the catalyst. The strongest promoted rows
carry `impact_path_validated`, meaning the evidence explains why the event
affects the token/protocol/venue/sector rather than merely mentioning both.
Validated hypotheses also carry `impact_path_type`, `candidate_role`,
`impact_path_strength`, `evidence_specificity_score`,
`digest_eligible_by_impact_path`, and `opportunity_score_v2`. Newer rows also
carry the final signal-quality layer: `market_confirmation_score` /
`market_confirmation_level`, `evidence_quality_score`, `source_class`,
`evidence_specificity`, `opportunity_score_final`, `opportunity_level`,
`why_local_only`, `why_not_watchlist`, and `manual_verification_items`. These
fields are review/routing metadata only; they do not create trades, paper rows,
normal RSI alerts, or `TRIGGERED_FADE`.
The same quality verdict is authoritative for lifecycle state. Rows with
`local_only`/`exploratory`, zero final score, `impact_path_type=insufficient_data`,
`candidate_role=unknown_with_reason`, `source_class=insufficient_data`, or
`evidence_specificity=insufficient_data` must not appear as active
`WATCHLIST`/`HIGH_PRIORITY` opportunities unless the row also persists an
explicit non-active `final_state_after_quality_gate`, `state_quality_capped=true`,
and `quality_state_block_reason`. Treat `state` as final quality-capped state on
fresh rows; requested pre-quality state is audit-only. Fresh alert/playbook or
market-anomaly rows without explicit quality fields are conservative local-only
evidence. When old rows carry quality fields but stale active final state,
read/report paths recompute the final state from quality rather than trusting
the stale stored final state.
Impact review now also includes claim and incident context. Check
`cause_status`, `claim_polarities`, `claim_history`, `primary_subject`,
`affected_ecosystem`, `candidate_role`, `role_confidence`, and
`role_evidence` before treating an item as validated. A confirmed exploit, an
alleged exploit, a denied/ruled-out exploit, and a no-clear-cause market
dislocation are different research objects. Ruled-out or unknown-cause exploit
language should appear as `market_dislocation_unknown` / local review evidence,
not as a confirmed exploit path. Third-party incidents can affect ecosystem
tokens as `ecosystem_affected_asset` without making the token the direct
incident subject. Market fields also carry `market_context_source`,
`market_context_timestamp`, `market_context_age_seconds`,
`market_context_data_quality`, `market_reaction_observed`,
`market_reaction_confirmed`, and `causal_mechanism_confirmed`; market reaction
is evidence to inspect, not proof that the source explains the causal path.
No-catalyst phrases such as “no dated external catalyst has been validated,”
“no clear trigger,” or “without a known cause” are absence-of-evidence /
unknown-cause metadata. They should never produce `primary_subject=No` or a
confirmed `explains_market_move` claim.
Generic prose fragments such as `Actions`, `Announcements`, `However`, `It`,
`LLM`, `Non`, `Note`, and `Only`, and SEO/source phrases such as
`Best Prediction Market Apps`, `Bitcoin And MSTR Are`, and
`Polymarket Invite Code SBWIRE` are not valid incident subjects. When no
validated external entity, crypto asset, market-anomaly asset, or event entity
is available, the incident row should be diagnostic-only and hidden from default
incident reports rather than shown as a canonical opportunity. Existing
persisted garbage-subject rows are also quarantined at read/report time.
Incident persistence also has a separate crypto-relevance gate. Rows may be
classified as `raw_observation`, `external_context_only`,
`incident_candidate`, `canonical_incident`, `linked_incident`,
`active_incident`, `diagnostic_only`, or `rejected_incident`. Live-style
profiles persist only candidate/canonical/linked/active incident rows by
default. Raw/external-context rows stay hidden and are not written unless
`RSI_EVENT_INCIDENT_STORE_RAW_OBSERVATIONS=1`; diagnostic/rejected rows require
`RSI_EVENT_INCIDENT_STORE_DIAGNOSTIC=1`. Fixture/debug profiles may still write
hidden rows for tests. A broad Polymarket, sports, political, geopolitical, or
macro event without a validated crypto asset, generated hypothesis, active
watchlist row, direct crypto archetype, or market-dislocation evidence is
external context/raw evidence for diagnostics, not an operational canonical
incident.

Incident links are also quality-gated. A hypothesis/watchlist link is
qualified only when it survives the quality gate: non-local opportunity level,
non-blocked final state, non-generic impact path, non-insufficient evidence,
non-unknown candidate role, and a validated asset identity or strong recognized
sector thesis. Weak legacy links such as `UMA:unknown`, `TRUMP:unknown`,
`FET:unknown`, or `SECTOR:unknown_with_reason` are kept as diagnostics with
`weak_link_count`, `unknown_role_link_count`, `quality_blocked_link_count`, and
`link_quality_reasons`; they do not make an incident `active_incident`.
`active_incident` should mean there is at least one qualified hypothesis or
watchlist link, or an explicit material update on a non-blocked row.

Canonical incidents are persisted separately from hypotheses under the active
profile namespace:

```bash
make event-incidents-report PROFILE=notify_llm
make event-incidents-report PROFILE=quality_validation
python3 main.py --event-incidents-report --event-alpha-profile notify_llm_quality --include-diagnostic-incidents
```

The report reads `event_fade_cache/<namespace>/event_incidents.jsonl` unless an
explicit incident-store path override is set. Each row is a compact research
artifact with raw source ids/URLs/domains, claim-history summaries, cause
status, conflicting claims, linked hypothesis ids, linked watchlist keys,
linked assets and roles, market reaction vs causal-mechanism flags, incident
confidence, and warnings. It intentionally does not store full article bodies.
Use this report to verify that duplicate articles about the same incident were
merged, that a second independent source updated the incident rather than
creating duplicate watchlist rows, and that ruled-out/unknown causes stayed
local-only. For market anomalies, verify that canonical names are asset-specific
(`SOL market anomaly`, `USDT market anomaly`) and that the report separates
`reaction_observed` from causal confirmation.
Default incident reports hide diagnostic-only, raw-observation,
external-context-only, and rejected rows but still count them separately, so a
rising diagnostic/raw/external count means the source cleaner/entity/relevance
guard needs review before treating those rows as real incidents. Use
`--include-diagnostic-incidents`, `--include-raw-incidents`, or
`--include-external-context-incidents` only when intentionally auditing
quarantined rows such as `LLM`, referral-code/source-noise subjects, or broad
external events that had no crypto link. Report lines include relevance status,
score, persistence reason, relevance reason codes, and link-quality counts.
Linked/active incidents should have `qualified_link_count > 0` and persistence
reasons such as `qualified_watchlist_link` or `qualified_hypothesis_link`.
Rows with `quality_blocked_link_only`, `unknown_role_link_only`,
`sector_only_unqualified_link`, or `weak_unqualified_watchlist_link` are not
active incidents; review them as candidates or hidden external context.
The linked-asset roles should show the validated anomaly asset from the market
payload as `direct_subject`. Sector rows such as `SECTOR`, source context, or
generic unknown-market text are context only and must not be treated as direct
incident subjects. If a market anomaly lacks validated asset identity, the
incident should carry `market_anomaly_missing_validated_asset`.

Incident id is now the preferred spine for impact-hypothesis state. Fresh
hypothesis rows, hypothesis-derived watchlist rows, route alert snapshots, and
run-ledger/doctor reports should carry top-level incident aliases such as
`incident_canonical_name`, `incident_primary_subject`,
`incident_affected_ecosystem`, `incident_cause_status`,
`incident_market_reaction_observed`, and
`incident_causal_mechanism_confirmed`. Hypothesis watchlist keys use
`incident_id + validated asset/sector identity + candidate_role +
impact_path_type` when an incident exists, so a new independent source updates
the same canonical watchlist row instead of creating a duplicate. Artifact
doctor strict mode blocks fresh hypothesis/watchlist/alert rows that are
missing incident ids unless they are explicitly no-incident evidence with both
`incident_link_status=no_incident` and a non-empty `incident_link_reason`.
Incident-specific material update reasons include `incident_new_independent_source`,
`incident_cause_status_changed`, `incident_claim_confirmed`,
`incident_claim_ruled_out`, `incident_conflicting_claim_added`,
`incident_market_reaction_confirmed`, `incident_causal_mechanism_confirmed`,
and `incident_asset_role_changed`.

Source-enrichment cache rows include the enrichment schema version, cleaner
version, source-content hash, and cleaned-text hash. If the cleaner changes,
old cached cleaned text is intentionally treated as stale and refetched or
recleaned. Set `RSI_EVENT_SOURCE_ENRICHMENT_CLEANER_VERSION` only when
deliberately testing a new cleaner contract.
Candidate-only or identity-only evidence can improve review context but does
not promote a token-level row. Candidate-discovery search hits can suggest new
crypto candidates when the source payload or quote-validated extraction names an
asset, but those suggestions still need deterministic identity/catalyst
validation before they can become token-level `RADAR` rows. Use the report's
`impact_path_reason` and `why_not_promoted` sections to separate real value-
capture paths from discovery-only leads, weak co-occurrence, identity blockers,
catalyst blockers, market blockers, and score blockers.
Validated token-level `RADAR` hypotheses can enter a capped daily research
digest in notification profiles when
`RSI_EVENT_ALPHA_VALIDATED_HYPOTHESIS_DIGEST_ENABLED=1`. The message/card must
still say this is a validated impact hypothesis, not a calibrated strategy or
trade signal. Hypotheses cannot create `WATCHLIST`, `HIGH_PRIORITY`,
paper/live rows, or `TRIGGERED_FADE`; `TRIGGERED_FADE` still comes only from
`event_fade.py` plus the `proxy_fade` playbook.

Digest routing is quality-gated. Defaults require score >=
`RSI_EVENT_ALPHA_VALIDATED_HYPOTHESIS_DIGEST_MIN_SCORE` (65), a validated token
identity, no source-noise/ticker-collision gate, a non-ambiguous playbook, a
known external catalyst or explicit direct token-event evidence,
`opportunity_score_v2` >=
`RSI_EVENT_ALPHA_VALIDATED_HYPOTHESIS_MIN_OPPORTUNITY_SCORE` (65), and
`RSI_EVENT_ALPHA_VALIDATED_HYPOTHESIS_MIN_FINAL_SCORE` (65), and
`impact_path_validated` or stronger validation stage. When final opportunity
metadata is present, `local_only` and `exploratory` stay local; only
`validated_digest`, `watchlist`, or `high_priority` verdicts can pass the
operator-facing digest gate. The router enforces this verdict after the older
watchlist/playbook route request is built: blocked rows keep
`requested_route_before_quality_gate`, `final_route_after_quality_gate`, and
`quality_gate_block_reason` in route decisions, alert snapshots, daily briefs,
quality review, and research cards so the downgrade is auditable. Alert
snapshots, notification plans, routed Telegram copy, and inbox queues use the
final route/lane/tier/alertable flag as authoritative; requested pre-gate fields
are audit-only. Quality-gated local-only rows belong in optional local review
sections, not delivered or would-send digest queues. Strong impact
paths can enter the capped digest if
other gates pass; medium paths need market confirmation; generic co-occurrence
is blocked by default via
`RSI_EVENT_ALPHA_BLOCK_GENERIC_COOCCURRENCE_DIGEST=1`. Weak
`catalyst_link_validated` or policy/macro/technology co-occurrence rows remain
local-only when
`RSI_EVENT_ALPHA_VALIDATED_HYPOTHESIS_REQUIRE_IMPACT_PATH=1` and
`RSI_EVENT_ALPHA_WEAK_VALIDATED_LOCAL_ONLY=1`. Examples that can pass the
impact-path gate include direct token events, venue value-capture events,
fan-token event demand, unlock/supply events, listing/liquidity events, and
security/exploit shocks tied to the token. Generic policy, macro, or broad
technology articles that merely mention a token should stay local-only with
`impact_path_not_digest_eligible:*` or `generic_cooccurrence_only`. Use
`RSI_EVENT_ALPHA_VALIDATED_HYPOTHESIS_REQUIRE_EXTERNAL_OR_DIRECT_EVENT=0` or
`RSI_EVENT_ALPHA_VALIDATED_HYPOTHESIS_REQUIRE_IMPACT_PATH=0` only for deliberate
review experiments. Use `opportunity_level`, `market_confirmation_level`, and
`source_class/evidence_specificity` to decide whether the next manual action is
source validation, market/liquidity verification, or feedback labeling.
Delivered validated-hypothesis digest items are written to
`event_alpha_alerts.jsonl` as research snapshots with `symbol`/`coin_id` plus
validated identity fields so `make event-alpha-notification-inbox
PROFILE=notify_llm` can show them as needing useful/junk feedback.

Lifecycle state is quality-gated too. Watchlist rows carry
`requested_state_before_quality_gate`, `final_state_after_quality_gate`,
`state_quality_capped`, and `quality_state_block_reason`. Daily briefs,
router decisions, active-watchlist monitor output, alert snapshots, inboxes,
research cards, and artifact doctor checks use the final quality-capped state
by default. A row whose final verdict is `local_only`, insufficient-data, or
zero-score cannot remain an active `WATCHLIST` / `HIGH_PRIORITY` candidate; it
appears under `Quality-Capped Watchlist Rows` with the requested/final state and
block reason. Valid `watchlist` / `high_priority` rows can still remain active,
and validated watchlist-quality rows can progress through event lifecycle states
such as `EVENT_PASSED` and `ARMED`. `TRIGGERED_FADE` remains unchanged and can
only come from deterministic `event_fade.py` plus `proxy_fade`. Block reasons
should name the missing evidence or blocker (`needs_strong_market_confirmation`,
`weak_impact_path_despite_market_confirmation`, `missing_direct_impact_path`,
etc.); positive evidence such as strong market confirmation belongs in score
components, not as the reason a row stayed local-only.

Notification visibility is separately controlled by
`RSI_EVENT_ALPHA_NOTIFICATION_QUALITY_MODE`:

- `validated_digest` (default): send validated digest, high-priority, and
  triggered-fade research lanes; keep exploratory-only rows local.
- `high_quality_only`: send only high-priority and triggered-fade research
  lanes.
- `exploratory_only`: enable the exploratory digest lane for deliberate burn-in
  review.

This setting filters operator visibility only. It does not change router
scoring, normal RSI alerts, paper/live writes, trading, or `TRIGGERED_FADE`
eligibility.

Each Event Alpha cycle also appends generated hypotheses to a profile-scoped
research artifact:

```bash
make event-impact-hypotheses-report PROFILE=notify_llm
make event-impact-hypotheses-report PROFILE=notify_llm ALL_HISTORY=1
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

## Signal-Quality Workbench

Run the offline signal-quality benchmark after changing impact-path, market
confirmation, evidence-quality, opportunity-verdict, notification-quality, or
validated-hypothesis routing code:

```bash
make event-alpha-signal-quality-eval
```

The fixture covers positive proxy/direct cases, weak co-occurrence controls,
market anomalies without catalysts, token unlock/listing cases, and known
source-noise/word-collision failures. It is offline and research-only.

To inspect one candidate from the current artifacts, use:

```bash
make event-opportunity-audit TARGET=SYMBOL PROFILE=notify_llm
make event-opportunity-audit TARGET=incident:<id> PROFILE=notify_llm
```

`TARGET` can be a symbol, coin id, alert id, card id, event id, route key, or
incident id. The audit report prints the evidence chain, identity status,
canonical incident context, claim history, market reaction vs causal mechanism,
impact path, market confirmation, final opportunity verdict, router decision,
missing evidence, upgrade requirements, downgrade risks, and a feedback command.
It is diagnostic only and cannot make a candidate alertable or trigger a fade.

### Reproducible quality-validation cycle

To validate the signal-quality layer end-to-end against *fresh* artifacts (rather
than judging stale uploads), run the isolated offline cycle:

```bash
make event-alpha-quality-validation-cycle
```

It uses the `quality_validation` fixture profile (offline, no Telegram sends, no
live providers, fixture clock). The Make target clears only the isolated
`event_fade_cache/quality_validation/` namespace first, then writes the run
ledger, impact hypotheses, watchlist, alert snapshots (if any), research cards,
canonical incidents, and daily brief. It prints the quality review and runs
artifact doctor in strict mode. The doctor checks top-level canonical quality
fields directly with fresh
hypothesis/watchlist/alert counters; nested `score_components` no longer hide
missing top-level verdicts. Hypothesis rows now persist `upgrade_requirements` /
`downgrade_warnings` alongside the other quality fields. Inspect individual rows
with `make event-impact-hypotheses-report PROFILE=quality_validation`,
`make event-incidents-report PROFILE=quality_validation`, or
`make event-opportunity-audit TARGET=<...> PROFILE=quality_validation`. The whole
cycle is research-only: no sends, trades, paper trades, normal RSI rows, or
`TRIGGERED_FADE`.

To validate the same quality/incident invariants against live-style
`notify_llm_quality` inputs without trusting older local rows, use the fresh
namespace smoke:

```bash
make event-alpha-quality-live-smoke PROFILE=notify_llm_quality_fresh
```

That target writes under `event_fade_cache/notify_llm_quality_fresh/`, leaves
Telegram sending off, uses the current wall clock, and runs the daily brief,
quality review, incident report, and strict artifact doctor. If this fresh
namespace is clean but older `notify_llm_quality` rows show active
local-only watchlist rows or garbage incident subjects, treat the older rows as
stale legacy leakage and regenerate before sharing artifacts.

Use the quality-loop targets after live or fixture notification cycles to
inspect real artifacts:

```bash
make event-alpha-quality-review PROFILE=notify_llm
make event-alpha-quality-coverage-report PROFILE=notify_llm_quality
make event-alpha-policy-simulate PROFILE=notify_llm
make event-alpha-export-signal-quality-cases PROFILE=notify_llm
make event-alpha-quality-loop PROFILE=notify_llm
```

`event-alpha-quality-review` groups current artifacts by opportunity level,
impact path, candidate role, evidence specificity, market confirmation,
candidate-discovery funnel conversion, and quality-field source/coverage
(`top_level`, nested legacy components, or recomputed defaults).
It also reports snapshot quality classifications, quality-gate conflicts,
candidate-discovery funnel stages (`raw_terms_extracted`,
`candidate_like_terms`, `resolver_attempted`, resolver accepted/rejected,
context validated, promoted), and a deterministic tuning section with
near-threshold upgrade candidates, repeated weak co-occurrence patterns,
local-only source classes, useful impact paths, common missing evidence, and
next experiments. Treat this as review guidance only; it does not tune live
thresholds. `raw_terms_extracted` is deliberately broad; `candidate_like_terms`
means terms that passed candidate-likeness filters and excludes taxonomy seed
rows, source/publisher/navigation terms, and obvious word-collision rejects
unless a resolver/validator accepted them.
`event-alpha-quality-coverage-report` is stricter: it reads raw artifact rows
from the latest run only and exits non-zero if any fresh row is missing a
canonical top-level quality field. It also warns when a namespace appears to
contain pre-quality-layer artifacts while the isolated `quality_validation`
namespace is clean.
`event-alpha-policy-simulate` compares named policies: current,
lower opportunity threshold, require market confirmation, require impact-path
validation, high-quality-only, and weak-macro-with-strong-market-confirmation.
It uses `final_route_after_quality_gate` by default, excludes legacy quality
conflicts unless explicitly included, and prints gained/lost candidates plus
warnings when weak/generic rows would become alertable.
`event-alpha-export-signal-quality-cases` writes proposed benchmark
cases to the active profile namespace, usually
`event_fade_cache/<profile>/proposed_signal_quality_cases.json`, from delivered
alerts, local-only weak rows, feedback, missed opportunities, and rejected
candidate examples. It does not modify
`fixtures/event_discovery/event_alpha_signal_quality_cases.json`; a human must
review proposed cases before promoting them into the canonical eval.

`event-alpha-quality-loop` runs only local reports:

1. `event-alpha-signal-quality-eval`
2. `event-alpha-quality-review`
3. `event-alpha-policy-simulate`
4. `event-alpha-notification-inbox`
5. `event-impact-hypotheses-report`
6. `event-alpha-daily-brief`

It intentionally does not run any send target.

The report defaults to the latest stored `run_id` while still printing
total/latest/historical/legacy availability. Use `ALL_HISTORY=1` for the older
full-history view, `RUN_ID=<id>` for a specific cycle, and `SINCE=<iso-time>` for
a time window.
Add `INCLUDE_LEGACY=1` only when intentionally reviewing old/missing-schema
rows. Hypothesis reports now separate generated queries from executed queries
and show query counts by `candidate_discovery`, `candidate_validation`, and
`market_confirmation`. `notify_llm` and `notify_llm_deep` can execute a bounded
number of candidate-discovery searches per cycle; `notify_no_key` keeps them
disabled/limited by profile. Rejected validation samples include the query,
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

Notification profiles use bounded runtime and provider behavior: no-key runs
default to a 120 second max runtime, OpenAI-backed notification profiles default
to a 600 second max runtime, live non-LLM provider calls use 5 second provider
timeouts, one provider failure before skip/backoff, DNS fail-fast, and
partial-result continuation. LLM calls have their own relationship/extraction
HTTP timeouts and bounded parallelism (`RSI_EVENT_LLM_MAX_PARALLEL_CALLS`). If
the runtime budget is exhausted, the cycle records
`notification_runtime_budget_exhausted`, preserves partial results, and still
writes heartbeat/run-summary artifacts.
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
alert store path, and incident store path at the top so the reviewed evidence is
auditable.
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
coverage. Fresh alert snapshots must carry
`final_route_after_quality_gate`, `final_tier_after_quality_gate`,
`alertable_after_quality_gate`, and a consistent quality verdict. Strict mode
blocks fresh/current rows whose final route is alertable while the opportunity
verdict is local-only, zero-score, or insufficient-data. Legacy quality-route
conflicts are warnings by default; use `STRICT_LEGACY=1` only for a deliberate
migration audit that should fail on old pre-quality rows.

The doctor also checks watchlist lifecycle consistency. Fresh/current rows with
active `WATCHLIST` / `HIGH_PRIORITY` state that contradict a local-only,
zero-score, or insufficient-data quality verdict must either carry a non-active
`final_state_after_quality_gate` with `state_quality_capped=true`, or strict
doctor blocks the namespace. Properly capped rows are visible in daily brief and
quality review local-only sections, not in active watchlist sections. Legacy
uncapped rows are migration warnings unless `STRICT_LEGACY=1` is set. The
doctor also reports incident relevance health: missing relevance fields,
canonical unlinked incidents, active incidents without qualified links, linked
incidents without qualified links, weak unqualified links, quality-blocked links
that would otherwise promote incidents, raw observations, external context,
rejected incidents, quarantined diagnostic incident rows, and garbage primary
subjects. Diagnostic/raw/rejected rows warn by default and are hidden from
operational incident counts; fresh canonical incident rows missing relevance
fields block strict checks. Fresh active incidents without qualified links block
strict checks. Fresh invalid canonical incident rows still block strict checks.

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
Cache hits are reused. Uncached calls run through a bounded thread pool, so one
slow provider read does not block every lower-priority candidate. If rows are
skipped, the run ledger and explain report show `llm_skipped_due_budget` or
runtime-deadline warnings.

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
RSI_EVENT_LLM_MAX_PARALLEL_CALLS=12
RSI_EVENT_LLM_OPENAI_TIMEOUT=30
RSI_EVENT_LLM_EXTRACTOR_OPENAI_TIMEOUT=30
RSI_EVENT_ALPHA_NOTIFY_MAX_RUNTIME_SECONDS=600
RSI_EVENT_LLM_CACHE_TTL_HOURS=24
```

`main.py --event-alpha-status --event-alpha-profile notify_llm` prints the
effective relationship candidate cap, raw-event extraction cap, run/day call
caps, parallelism, relationship/extraction timeouts, estimated daily cost cap,
cache TTL, and ledger path. These knobs only change how many LLM
relationship/extraction attempts can run and how long they can wait; they do not
change alert scoring, send guards, normal RSI rows, paper/live writes, trading,
or `TRIGGERED_FADE` eligibility.

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
