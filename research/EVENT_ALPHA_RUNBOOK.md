# Event Alpha Radar Runbook

Event Alpha is a research-only catalyst radar. It can discover evidence,
refresh watchlist rows, route research digests, write review artifacts, and
export proposed eval cases. It must not trade, paper trade, write normal RSI
signal rows, or let LLM/search/watchlist output create `TRIGGERED_FADE`.

## Source Coverage And Evidence Plans

Event Alpha now reports source registry and source-pack metadata in near-miss
reports, daily briefs, research cards, and opportunity audits. Use these fields
as an operator checklist:

- `source_class` / `source_mission`: what the source is allowed to prove.
- `source_can_prove` / `source_cannot_prove` / `source_useful_playbooks`: the
  explicit source contract. Broad context, market data, derivatives, and supply
  evidence each prove different things; they should not be treated as generic
  confirmation.
- `provider_coverage_status`: whether absence from the provider is meaningful.
  Degraded, partial, unavailable, or not-configured coverage is a gap, not a
  strong negative signal.
- `source_pack`: the playbook-specific evidence pack, such as listing,
  unlock/supply, proxy pre-IPO/RWA, security shock, sports/fan, political meme,
  or market anomaly.
- `source_pack_sufficient_for_validated_digest`,
  `source_pack_required_for_watchlist`, and
  `source_pack_required_for_high_priority`: pack-specific criteria used to
  explain why evidence is enough for local review, digest, watchlist, or still
  missing required confirmation.
- `evidence_acquisition_plan`: bounded query/checklist metadata for what to
  search next. It is advisory only and does not change routes or watchlist state
  by itself.
- `feed_quality_score`, `feed_source_class`, and feed-level quarantine/cooldown
  fields on live RSS sources: a 403 or parse failure quarantines that feed while
  healthy feeds in the same bundle can continue.

Broad news, RSS recap/SEO, and Polymarket rows are useful context, but they do
not validate token impact by themselves. Official exchange/project,
structured-unlock/calendar, and matching CryptoPanic currency-tag evidence are
stronger source classes when the text also names the token and explains the
impact path. The planner can suggest official searches, denial searches,
market/derivatives/supply refreshes, and validation criteria; deterministic
resolver, quality, router, and `event_fade.py` gates remain authoritative.
Source-pack acquisition rows now persist the attempted plan, execution results,
query execution statuses, provider coverage statuses, accepted/rejected samples,
and source-pack sufficiency booleans. Treat these rows as audit evidence; they
can improve a local research verdict only after deterministic identity,
catalyst-link, impact-path, source-quality, and quality-gate checks pass.

The operator-facing opportunity spine is the canonical CoreOpportunity view.
When `event_core_opportunities.jsonl` exists, cards and audits should read the
stored core row plus its linked support rows, diagnostic/control rows,
evidence-acquisition rows, market-refresh rows, alert snapshots, card path, and
feedback status through the canonical read model. Incident rows and selected
catalyst-frame context are part of that same read model, so audits/cards should
use the joined incident row before falling back to legacy per-row incident
reconstruction. Support/control artifacts are audit evidence attached to the
core opportunity; they should not create a second visible truth for route,
state, tier, incident context, or final opportunity verdict.
Canonical core route fields are part of that contract. A promoted final
opportunity level (`validated_digest`, `watchlist`, or `high_priority`) should
persist a matching research route (`RESEARCH_DIGEST` or
`HIGH_PRIORITY_RESEARCH`) unless a real quality block, quality-capped state,
duplicate suppression, or `TRIGGERED_FADE` route applies. Strict artifact doctor
reports `core_route_conflicts_with_opportunity_level`; treat a nonzero value as
a fresh artifact blocker before reviewing daily briefs, cards, or feedback
queues.
Live-style profiles add one more promotion gate. A canonical core opportunity
may stay `validated_digest`, `watchlist`, or `high_priority` only when at least
one live confirmation source exists: accepted source-pack acquisition evidence,
official/structured evidence, matching CryptoPanic token/catalyst evidence,
strong direct source evidence, or fresh non-generic market confirmation.
`skipped_budget`, `no_results`, `rejected_results_only`,
provider-unavailable/backoff, broad-news context, and prediction-market-only
context do not confirm the candidate by themselves. Sector-only rows such as
`SECTOR/sports_fan_proxy` remain exploratory/local by default unless
`RSI_EVENT_ALPHA_ALLOW_SECTOR_DIGEST=1` is explicitly enabled for a debug or
future reviewed workflow. Daily briefs show these rows under `Live Confirmation
Gated Candidates`, quality review reports `live_confirmation_gates`, and strict
artifact doctor blocks fresh live promoted rows without confirmation.
Source-pack acquisition display follows the same rule: use the canonical
core acquisition view for accepted/rejected counts, reason codes, samples,
source pack, provider failures, and before/after verdicts. If a support row
disagrees with the core row, keep it under diagnostics instead of letting it
change the primary card, audit, quality-review section, market-freshness line,
or upgrade-candidate list.
Cards, audits, and acquisition rows should also show the source contract:
what the source can prove, what it cannot prove, the playbooks it is relevant
for, and whether absence is meaningful under current provider coverage.
CryptoPanic-tagged evidence can strengthen token/catalyst/impact evidence, but
it still cannot prove official confirmation; official project/exchange or
structured sources remain the right evidence for official confirmation.
The same canonical-core rule applies to secondary operator copy. Cards and
audits should derive latest source, source count, impact-path
reason/strength, digest eligibility, market confirmation/freshness, upgrade
requirements, downgrade warnings, and missing-evidence text from the final core
verdict and joined acquisition/market evidence. Filler values such as
`unknown`, `missing`, or `insufficient_data` are placeholders, not stronger
truth than accepted evidence. A promoted `validated_digest`, `watchlist`, or
`high_priority` core should not show generic-cooccurrence, missing direct
mechanism, or missing value-capture blockers in its primary text; those belong
only in diagnostics for stale support/control rows.

## Feedback And Calibration Loop

Every reviewable card/core opportunity should have a stable feedback target.
Use the card command or one of the shortcuts:

```bash
make event-alpha-feedback-readiness PROFILE=catalyst_frame_e2e
make event-feedback-useful PROFILE=catalyst_frame_e2e FEEDBACK_TARGET=<core_or_card_target>
make event-feedback-junk PROFILE=catalyst_frame_e2e FEEDBACK_TARGET=<core_or_card_target>
make event-feedback-watch PROFILE=catalyst_frame_e2e FEEDBACK_TARGET=<core_or_card_target>
make event-alpha-calibration-report PROFILE=catalyst_frame_e2e
make event-alpha-export-signal-quality-cases PROFILE=catalyst_frame_e2e
```

Feedback rows are artifact-only labels. They should preserve the review target,
core id, card path, run/profile/namespace, incident/hypothesis/watchlist ids,
symbol/coin id, impact path, candidate role, opportunity level, final route and
lane, source pack/class/provider/domain, evidence specificity, market
confirmation/freshness, and catalyst-frame status. Calibration reports use
those dimensions to show useful/junk/watch/ignored rates and sample targets;
policy simulation uses them to show which threshold changes would admit known
junk or keep useful candidates; signal-quality export turns useful/junk/watch
and missed rows into proposed eval cases without modifying canonical fixtures.

Missed opportunities can be stored as research rows with symbol/coin id, source
URL or text, why it mattered, approximate time, expected playbook, and notes.
The diagnostic failure stage should explain whether the source was not
ingested, the candidate was not resolved, impact path failed validation, market
confirmation was missing, quality gates were too strict, provider coverage was
down, or the route was suppressed. These rows feed recall-oriented eval-case
exports and source-reliability review only; they do not create alerts.

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

Routed Telegram notifications are core-opportunity-first. When
`event_core_opportunities.jsonl` exists, the notification plan reconciles router
decisions to the canonical `core_opportunity_id` before formatting, dedupe, and
delivery-ledger writes. Lower-level watchlist/hypothesis ids are retained as
`source_alert_ids` for audit, but the delivered item, feedback target, and card
reference should point at the `agg:...` core opportunity. The rendered Telegram
body is intentionally compact: it shows candidate, catalyst, route/level,
impact role, evidence status, market status, and check-next text, while hiding
raw alert ids, card ids, full local paths, and repeated boilerplate. Each
delivery attempt writes the last operator-visible body to
`event_alpha_notification_preview.md`; use:

```bash
make event-alpha-notification-format-smoke PYTHON=python3
make event-alpha-notification-deliveries-report PROFILE=fixture PYTHON=python3
```

Live-style notification profiles also re-check confirmation before digest
delivery. A core row whose evidence acquisition is `rejected_results_only`,
`no_results`, `skipped_budget`, or otherwise non-confirming stays local-only
unless another strong confirmation exists: accepted source-pack evidence,
official/structured/tagged source evidence, or fresh non-generic market
confirmation on a real impact path. Artifact doctor strict mode checks delivery
identity/core-store mismatches, noncanonical alert ids, rejected-only digest
items, missing previews, raw debug dumps, and absolute local paths in previewed
Telegram bodies.

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

Use `make event-alpha-live-burn-in-no-send
PROFILE=live_burn_in_no_send` to prove a real live-style burn-in run without
requesting Telegram delivery. This target clears only
`event_fade_cache/live_burn_in_no_send/`, runs profile-aware status and
preflight, runs the unified Event Alpha cycle without `--event-alert-send`,
writes the daily brief, quality review, feedback-readiness report, strict
artifact doctor, and the final burn-in readiness report:

```bash
make event-alpha-live-burn-in-no-send PROFILE=live_burn_in_no_send
make event-alpha-burn-in-readiness PROFILE=live_burn_in_no_send
make event-alpha-daily-brief PROFILE=live_burn_in_no_send
make event-alpha-artifact-doctor PROFILE=live_burn_in_no_send STRICT=1
```

The readiness report should confirm `no_send_confirmed=true`, a successful
latest run, no delivery rows in the namespace, provider/source-pack coverage,
strict doctor status, card/feedback target readiness, evidence acquisition
attempts, and a visible Market Freshness Readiness section in the daily brief.
Missing provider keys or degraded public sources should be reviewed as coverage
gaps. They do not make evidence absence meaningful by themselves. Do not move
from no-send burn-in to guarded sends unless the operator has reviewed the core
cards, near-miss/local-only sections, provider gaps, source-pack evidence
absence semantics, and feedback targets.

Evidence acquisition failures are expected live-path coverage states, not
runtime failures. `disabled`, `no_candidates`, `provider_unavailable`,
`provider_backoff`, `skipped_budget`, and `failed_soft` runs should appear as
run-ledger/acquisition statuses with safe warnings while the cycle still writes
cards, daily brief, doctor output, and readiness reports. Burn-in readiness is
based on the current visible canonical core review queue: every visible core
needs a card and feedback target, while stale support/inbox rows remain
diagnostics rather than blockers when the canonical core surface is complete.

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
the stale stored final state. Artifact doctor treats rows loaded from a resolved
profile namespace as path-scoped current artifacts even if older watchlist rows
are missing embedded `profile`, `run_mode`, or `artifact_namespace` fields;
missing metadata must not hide active-state quality conflicts.
Lifecycle state caps are not automatically route blockers. A row with
`opportunity_level=watchlist` may be capped from requested `HIGH_PRIORITY` state
to final `WATCHLIST` state and still remain eligible for digest/watchlist
research routing. Only route-quality gates such as local-only verdicts,
insufficient impact/evidence/source, zero final score, source noise, ticker
collision, missing identity, profile policy, or stale-market caps below the
route threshold should force `STORE_ONLY`. Artifact doctor similarly separates
quality-blocked support links that are present for diagnostics from
quality-blocked links that would be the only active incident support.
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
Market confirmation also carries a freshness verdict:
`market_context_freshness_status` is one of `fresh`, `stale`,
`fixture_allowed_stale`, `missing`, `unknown`, and local reports/cards show a
human-readable age. Live-style profiles cap stale, missing, or unknown-timestamp
market context so it cannot by itself promote a candidate to `WATCHLIST` or
`HIGH_PRIORITY`. Fixture/e2e profiles may explicitly allow stale fixture
snapshots, but those rows must say `fixture_allowed_stale`; treat that as an
offline test allowance, not live market confirmation. The freshness policy is
controlled by `RSI_EVENT_MARKET_CONTEXT_MAX_AGE_HOURS`,
`RSI_EVENT_MARKET_CONTEXT_ALLOW_STALE_FIXTURE`, and
`RSI_EVENT_MARKET_CONTEXT_STALE_CAP_LEVEL`.
Incident and hypothesis rows also carry catalyst-frame metadata when source
text contains multiple event claims. `main_frame_type` and
`main_catalyst_frame_id` describe the event the source is primarily about;
`background_frame_ids`, `negated_frame_ids`, `background_context_summary`, and
`rejected_impact_paths` describe context that must not drive promotion by
itself. Example: an AAVE/Kraken strategic-stake article that mentions a prior
KelpDAO exploit should validate as `strategic_investment_or_valuation`, not
`exploit_security_event`, because the exploit is background context and “Aave
itself not being hacked” is a negated/corrective frame.
OpenAI/fixture LLM catalyst-frame analysis is an optional support layer for
this same metadata. It is disabled by default, off for `notify_no_key`, enabled
with bounded caps in OpenAI-backed `notify_llm`/`notify_llm_deep`/`full_llm_live`
profiles, and fixture-backed in `catalyst_frame_validation`. LLM output is never
trusted raw: quotes must appear in the source, external entities cannot be
accepted as crypto assets, generic ticker-word collisions are rejected, and
rule/LLM disagreements are recorded before a validated frame can override a
weaker deterministic frame. Use:

```
make event-alpha-catalyst-frame-validation-cycle PYTHON=python3
make event-alpha-catalyst-frame-e2e-cycle PYTHON=python3
make event-alpha-notify-llm-quality-frame-smoke PYTHON=python3
make event-alpha-frame-quality-loop PROFILE=catalyst_frame_e2e PYTHON=python3
make event-opportunity-audit TARGET=AAVE PROFILE=catalyst_frame_e2e PYTHON=python3
make event-alpha-daily-brief PROFILE=catalyst_frame_e2e PYTHON=python3
```


`catalyst_frame_e2e` is the preferred local proof when reviewing artifact
fidelity. It writes only under `event_fade_cache/catalyst_frame_e2e/`, uses
fixture raw events and fixture LLM catalyst frames, disables live providers and
sends, and proves that AAVE/Kraken remains a strategic investment while KelpDAO
exploit language stays background/corrective context.
Use `make event-alpha-notify-llm-quality-frame-smoke` when the review target is
the live-style `notify_llm_quality` artifact shape rather than the isolated e2e
namespace. It writes under `event_fade_cache/notify_llm_quality_frame/`, uses
fixture catalyst-frame output, keeps sends disabled, and prints the cycle, daily
brief, impact-hypothesis report, incident report, quality review, and strict
artifact doctor. This is the preferred smoke before changing frame counters,
skip reasons, or `notify_llm_quality` report wiring.
Use `make event-alpha-frame-quality-loop PROFILE=catalyst_frame_e2e` for the
full frame-quality review chain: signal-quality eval, regenerated e2e
artifacts, quality review, incident report, impact-hypothesis report, daily
brief, strict artifact doctor, and an AAVE opportunity audit. It is no-send and
fixture-backed by default.

Live-style profiles also record when catalyst-frame analysis was required but
missing or unresolved. Run ledgers and daily briefs expose analyzed, validated,
unresolved, skipped, and skip-reason counts so a provider outage, disabled
profile, missing OpenAI key, budget skip, no-row prefilter miss, or LLM deadline
is visible as a normalized skip reason such as `disabled`, `missing_api_key`,
`budget_exhausted`, `no_rows_selected`, `profile_disabled`, or
`deadline_exceeded`. Rows with ambiguous multi-catalyst/proxy/security-
background language may be capped to local or exploratory research when a
required frame is missing or unresolved. A
deterministic direct-event path can still be sufficient for clear listings,
unlocks, strategic-stake/valuation reports, and confirmed direct exploits, but
generic or ambiguous co-occurrence should not route as validated merely because
the LLM frame layer did not run.

Incident asset roles are provenance-sensitive. Resolver-validated affected
assets can be direct subjects; taxonomy/search suggestions are candidate
suggestions until identity validation confirms them. For example, a THORChain
exploit can validate RUNE as the direct subject while LINK/PYTH taxonomy terms
remain search candidates rather than affected assets. Compatible validated
hypotheses may aggregate by incident, validated asset, role, and impact-path
family, but supporting categories, hypothesis ids, and evidence quotes should
remain visible for audit.
Quality review and daily operator reports may show one core opportunity row for
an aggregated incident/asset/role/path family, for example one VELVET/SpaceX
row with supporting proxy categories. Treat this as presentation de-duplication
only; raw hypotheses, supporting impact paths, and source evidence remain in the
JSONL artifacts and cards for review.

Core opportunities are the default operator contract. A core opportunity is
visible when it appears in high-priority, validated digest, watchlist,
near-miss, upgrade-candidate, or non-diagnostic quality-capped/local sections.
Every fresh visible core opportunity should have a research card, a stable
feedback target, and an audit target keyed by `core_opportunity_id`. Duplicate
or route suppression means "do not send again"; it must not suppress card
creation, feedback readiness, or opportunity audit coverage. Alert snapshots
for visible rows should carry `core_opportunity_id`, `feedback_target`,
`feedback_target_type`, card path, and card group when available, so daily
briefs, inboxes, cards, audits, feedback labels, and Pro-model review bundles
join on the same object.

After a cycle completes, the canonical operator state is persisted in
`event_core_opportunities.jsonl` under the active artifact namespace. This file
contains one post-refresh, quality-gated core row per visible opportunity with
the initial, post-refresh, and final verdict fields plus supporting and
diagnostic row ids. Daily brief, near-miss report, card generation, opportunity
audit, run-ledger, and artifact-doctor paths should prefer this store when it is
present. Raw hypothesis/watchlist/support rows remain useful for diagnostics,
but they should not create separate visible duplicates or downgrade the final
core opportunity.

Research cards and alert snapshots must resolve through the same canonical
store. A Core Opportunity Card should embed a `core_opportunity_id` that exists
in `event_core_opportunities.jsonl` for the selected profile/namespace. If a
source-noise, ticker-collision, or control row is useful for audit, it should be
stored as diagnostic support with `diagnostic_support_for_core_opportunity_id`
and `is_diagnostic_snapshot=true`, not as a new visible core id. The daily brief
uses the research-card index grouping, so card groups and brief groups should
agree by default. If they do not, run the artifact doctor before treating the
bundle as ready for Pro-model review.

Core Opportunity Cards should also render their human-facing quality-gate text
from the final core verdict fields (`final_route_after_quality_gate`,
`final_state_after_quality_gate`, `opportunity_level`, and final verdict
reason/source). Raw support-row gate reasons are useful diagnostics, but they
must not make a final digest/high-priority core card say it is local-only.
Alert snapshots follow the same rule. When a snapshot resolves to a canonical
`core_opportunity_id`, the core row owns final route, tier, opportunity level,
lifecycle state, alertability, live-confirmation fields, evidence-acquisition
fields, and feedback target. Pre-reconciliation snapshot route/level/state may
be kept only as `requested_*_before_core_reconciliation` audit metadata. Daily
briefs, inboxes, feedback readiness, opportunity audits, and artifact doctor
checks should use the reconciled final fields; if the canonical core row is
missing, the snapshot should remain local/store-only until the core store is
repaired.

Diagnostic/support snapshots are the exception to canonical mirroring. They may
link to the canonical core through `diagnostic_support_for_core_opportunity_id`
and may include `support_for_core_summary` with the core route/level/state for
audit, but their own final route, tier, lifecycle state, and alertability must
remain store-only/local-only. If `load_alert_snapshots()` or artifact doctor
shows a diagnostic/support row with an alertable route, treat that as an
artifact bug, not an operator opportunity. The canonical core snapshot is the
only alert snapshot allowed to represent the promoted opportunity.

Card generation is a secondary artifact write. After cards are written, the
cycle should backfill the generated card path, research-card path, and feedback
target fields onto the already-stored core rows instead of appending duplicate
core rows. Source-pack evidence acquisition rows should also be reconciled to
the stored core opportunity id when a temporary acquisition id matches the same
incident, validated asset, role, and impact-path family. Reconciled acquisition
rows keep the original id for audit, but operator-facing cards, audits, daily
briefs, and doctor checks should display the canonical core id first.

Near-miss reporting has two operator buckets. `Near-Miss Candidates` are
currently non-alertable/local candidates close to promotion but missing fixable
evidence. `Upgrade Candidates` are already validated digest or watchlist rows
that are not yet high-priority and are missing market, derivative, source, or
freshness evidence for the next tier. Market-freshness readiness should summarize
the best and worst freshness by core opportunity by default, with row-level
support details left to diagnostics.

The feature is research metadata only. It cannot send notifications, create
paper/live rows, write normal RSI signals, execute trades, or create
`TRIGGERED_FADE`.
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
persisted garbage-subject rows are also quarantined at read/report time. Fresh
incident writes validate the primary subject before persistence, so boilerplate,
publisher/source noise, SEO text, and generic pronouns should never be written
as `incident_subject_quality=valid` with a missing relevance status.
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

Source-pack evidence acquisition is the executable follow-up to the source
registry and evidence planner. Profiles may enable
`RSI_EVENT_ALPHA_EVIDENCE_ACQUISITION_ENABLED=1` to run bounded searches for
selected near-misses and validated hypotheses, capped by
`RSI_EVENT_ALPHA_EVIDENCE_ACQUISITION_MAX_CANDIDATES` and
`RSI_EVENT_ALPHA_EVIDENCE_ACQUISITION_MAX_QUERIES`. Results are written only to
`event_evidence_acquisition.jsonl` under the active artifact namespace and are
shown in the run ledger, daily brief, research cards, and opportunity audits.
Accepted rows must pass deterministic identity, catalyst-link, impact-path, and
source-quality checks; context-only or generic results stay rejected/local. Use
`make event-alpha-evidence-acquisition-smoke PYTHON=python3` for the fixture
proof path: it runs VELVET, RUNE, ZEC, and context/no-result examples with no
Telegram sends, trades, paper rows, normal RSI rows, or event-fade trigger
creation.
Read acquisition rows as a three-step trail, not a single upgrade flag:
`initial_opportunity_*` is the verdict before the search,
`post_refresh_*` is the recomputed evidence/market view after search, and
`final_opportunity_*` is the canonical operator-facing verdict. Accepted
evidence can improve `evidence_quality_score` while `final_upgrade_status`
remains `unchanged` if the final opportunity did not improve. Reports/cards
show `acquisition_evidence_status` separately from `final_upgrade_status`, and
they keep `market_data_freshness` separate from
`market_reaction_confirmation`.
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

Digest routing is quality-gated. Defaults require a validated token identity,
no source-noise/ticker-collision gate, a non-ambiguous playbook, a known
external catalyst or explicit direct token-event evidence,
`opportunity_score_final` >=
`RSI_EVENT_ALPHA_VALIDATED_HYPOTHESIS_MIN_FINAL_SCORE` (65), and
`impact_path_validated` or stronger validation stage. `opportunity_score_final`
and `opportunity_level` are the canonical route inputs; older
`opportunity_score_v2`, `hypothesis_score`, and watchlist/playbook scores are
audit-only once a final verdict exists. When final opportunity metadata is
present, `local_only` and `exploratory` stay local; only
`validated_digest`, `watchlist`, or `high_priority` verdicts can pass the
operator-facing digest gate. The router enforces this verdict after the older
watchlist/playbook route request is built: blocked rows keep
`requested_route_before_quality_gate`, `final_route_after_quality_gate`, and
`quality_gate_block_reason` in route decisions, alert snapshots, daily briefs,
quality review, and research cards so the downgrade is auditable. Route reports
also show `routing_score_source=opportunity_score_final`, the score used, and
the verdict used. Alert
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
source-noise/word-collision failures. It also covers market-context freshness:
fresh market confirmation, stale fixture context allowed only for fixture
profiles, stale live context capped, and missing/unknown market timestamps
capped. It is offline and research-only.

To inspect one candidate from the current artifacts, use:

```bash
make event-opportunity-audit TARGET=SYMBOL PROFILE=notify_llm
make event-opportunity-audit TARGET=incident:<id> PROFILE=notify_llm
make event-alpha-near-miss-report PROFILE=notify_llm_quality
```

`TARGET` can be a symbol, coin id, alert id, card id, event id, route key, or
incident id. The audit report prints the evidence chain, identity status,
canonical incident context, claim history, market reaction vs causal mechanism,
impact path, market confirmation, final opportunity verdict, router decision,
near-miss status, missing evidence, upgrade requirements, downgrade risks, and
a feedback command.
It is diagnostic only and cannot make a candidate alertable or trigger a fade.

The near-miss report identifies validated candidates close to digest/watchlist
promotion, rejects source-noise/ticker-collision/generic co-occurrence rows, and
shows missing evidence plus bounded refresh diagnostics. `notify_llm_quality`,
`notify_llm`, and `notify_llm_deep` profiles enable near-miss market refresh by
profile; the default environment remains off unless a profile opts in. Refresh
may update local hypothesis/watchlist artifacts with market/enrichment
before/after fields and a recomputed final opportunity verdict, but it does not
send notifications, trade, paper trade, write normal RSI rows, or create
`TRIGGERED_FADE`.

For a deterministic proof that stale market context can be refreshed without
live providers or sends, run:

```bash
make event-alpha-market-refresh-smoke
```

This uses the `market_refresh_smoke` profile plus
`fixtures/event_discovery/market_refresh_smoke_markets.json`. It should show the
VELVET/SpaceX validated-digest candidate upgrading to high priority from fresh
fixture market confirmation, while weaker/no-reaction rows remain lower. The
same reports and cards include `market_refresh_attempted`,
`market_refresh_success`, provider/error details, before/after market
confirmation, market data freshness, market reaction confirmation, before/after
opportunity score/level, canonical final opportunity verdict fields, and the refresh upgrade
status.

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
make event-alpha-frame-quality-loop PROFILE=catalyst_frame_e2e
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

Feedback rows are calibration artifacts, not controls. They preserve
`incident_id`, impact path, candidate role, opportunity level, evidence
specificity, market confirmation, source class, and playbook metadata from the
matched watchlist row. Calibration reports group feedback-only rows by those
fields even when no alert snapshot exists, but they only print recommendations;
they do not alter thresholds or routing.

`event-alpha-quality-loop` runs only local reports:

1. `event-alpha-signal-quality-eval`
2. `event-alpha-quality-review`
3. `event-alpha-policy-simulate`
4. `event-alpha-notification-inbox`
5. `event-impact-hypotheses-report`
6. `event-alpha-daily-brief`

It intentionally does not run any send target.
`event-alpha-frame-quality-loop` is the catalyst-frame equivalent for the
AAVE/Kraken/KelpDAO and VELVET/SpaceX fixture spine. It regenerates the
`catalyst_frame_e2e` namespace, then reruns quality review, incident and
hypothesis reports, daily brief, strict artifact doctor, and an AAVE
opportunity audit. It is intended to prove main-catalyst selection, background
frame rejection, asset-role safety, aggregation, route consistency, and report
coherence together.

Default operator reports now present core opportunities rather than every
supporting row. Compatible rows are aggregated by incident, validated asset,
candidate role, and impact-path family. For example, a single VELVET/SpaceX
opportunity may carry tokenized-stock-venue and RWA pre-IPO proxy support while
source-noise/control rows stay hidden under diagnostics. Use
`make event-opportunity-audit TARGET=<core_opportunity_id> INCLUDE_DIAGNOSTICS=1`
when you need to inspect the hidden support/control rows behind a core
opportunity.
The daily brief is intentionally core-first: high-priority, validated digest,
watchlist, near-miss, and local/quality-capped opportunities are mutually
exclusive operator sections, followed by canonical incidents and a short system
health summary. Raw routed decisions, active watchlist dumps, validated routing
details, signal-quality distributions, suppression reasons, research-card
plumbing, and why-alerts-sent details live under the Diagnostics Appendix by
default. Already-promoted opportunities are excluded from exploratory digest
and near-miss sections, and near-miss rows are de-duplicated by incident, asset,
candidate role, and impact path. Near-miss/local-only copy should describe
what is interesting, what evidence is missing, what would upgrade the row, and
what would invalidate it in human terms rather than exposing raw reason-code
strings. Event Alpha uses a shared reason-text helper for daily briefs, quality
reviews, research cards, opportunity audits, and signal-quality eval output so
operator-facing explanations stay consistent across reports. The quality
review's possible-false-positive section is suspicion-only; it requires
explicit source-noise, ticker-collision, generic co-occurrence, identity, or
rejected-candidate evidence. Missing context, weak impact paths, and missing
direct impact paths are local-only blockers, not false-positive labels by
themselves, and should not make strong core opportunities appear suspicious
merely because they have diagnostic support rows. Research-card indexes and
daily-brief card links group cards as core, near-miss, local/quality-capped,
diagnostic/control, or legacy so Pro-model handoffs can inspect the main
opportunities first. New card indexes use the card's watchlist/quality metadata
rather than filename hints when possible; the filename/content fallback exists
only for legacy artifacts.
Validated cards also choose playbook and invalidation copy from the impact path
and catalyst frame: AAVE/Kraken-style strategic investment cards should talk
about stake/valuation risk, VELVET/SpaceX-style proxy cards should talk about
venue/exposure validation, and MemeCore-style unknown market dislocations
should remain local-only until a causal catalyst is found.
Standalone fixture-report targets such as
`make event-alpha-daily-brief PROFILE=catalyst_frame_e2e` pass the fixture/test
artifact include flag automatically, so the generated brief should select the
latest fixture run and show catalyst-frame counters rather than treating the
namespace as empty production history.

Daily briefs include a canonical operator-view note near the top. Treat the
Core Opportunities sections as the default working view. The Diagnostics
Appendix intentionally contains raw/support/control rows and may repeat assets
for debugging; those repeats are not additional operator opportunities.

Daily briefs and quality reviews also include Market Freshness Readiness. Use
that section before trusting watchlist/high-priority rows: fresh market context
supports escalation, stale or unknown-timestamp context is capped according to
profile policy, and missing context explains why an otherwise interesting
candidate may remain local-only. Fixture/e2e profiles may label old fixture
context as `fixture_allowed_stale`; live-style profiles should prefer fresh
provider snapshots.

Market Freshness Readiness is split into core and support fields. Trust
`core_market_freshness_status`, `core_market_context_source`,
`core_market_context_age`, and `core_market_refresh_needed` for the visible
opportunity. `support_rows_stale_or_missing_count` and
`support_rows_needing_refresh_count` are diagnostics; stale support rows should
not make a fresh canonical core look missing or contradictory.

Source Coverage / Evidence Acquisition is also split. `evidence_plans_created`
counts planning work, while `acquisition_requests_executed` and
`provider_queries_executed` count actual execution. A run can execute
acquisition requests even when no new plans were created in that report window,
so use the executed/accepted/no-result/rejected counters instead of assuming a
zero plan count means no provider work happened.

`notify_llm_quality` is the live-style no-send quality profile for catalyst
frame and signal-quality review. `notify_llm_quality_frame` is the fixture/no-send
proof profile that exercises the same artifact shape with deterministic frame
fixtures. Use `make event-alpha-quality-frame-live-smoke` when you need a fresh
`notify_llm_quality`-style no-send run with frame/readiness reports; use
`make event-alpha-notify-llm-quality-frame-smoke` for the offline fixture proof.

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

When `event_core_opportunities.jsonl` exists, the inbox is core-first. It
creates one canonical review item per visible CoreOpportunity, resolves the
research card and feedback target from that core row, and hides source-noise or
diagnostic/support alert snapshots unless diagnostics are explicitly requested.
For example, a VELVET/SpaceX opportunity should use the canonical `agg:...`
feedback target and card path; linked support snapshots are audit context, not
separate review items. Feedback readiness and opportunity audit follow the same
rule so readiness counts match the operator-visible cards.

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
coverage. Research card coverage counts real card Markdown files separately
from `index.md`; `index.md` is required as navigation but cannot satisfy the
card count by itself. Strict mode blocks current cards missing Artifact Lineage
or a stable feedback target. When canonical core-store rows are present, strict
mode also checks Core Opportunity Cards and non-diagnostic snapshots against the
store, warns on diagnostic/source-noise rows with fake core ids, and reports
daily-brief/index card-group mismatches. Fresh alert snapshots must carry
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
The doctor also reports canonical core-store coverage:
`core_opportunity_store_rows`, `visible_core_opportunities_missing_store_rows`,
and duplicate store-row counts. Missing core-store rows block strict
non-legacy/non-test operational checks, while legacy/test migration checks warn
so old artifacts remain inspectable.

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
Current cards also include Artifact Lineage with run/profile/namespace,
incident/hypothesis/watchlist/core-opportunity ids, alert/snapshot/card ids, and
source raw/event ids when available. They also show the local card path, stable
feedback target, feedback target type, and useful/junk/watch helper commands.
Missing lineage is labeled as legacy lineage, not as a current unknown. If a
Pro-model handoff shows a card without lineage or without a feedback target,
regenerate cards from the current profile namespace before relying on the card
as current evidence.

Router reports now show stable `alert_id` and `card_id` values. Use the
`ea:...` alert ID in feedback commands, and the matching `card_...` ID/filename
when opening generated cards:

```bash
make event-alpha-router-report PROFILE=no_key_live
make event-feedback-useful FEEDBACK_TARGET=ea:cluster_id\|coin_id\|playbook
```

Feedback and opportunity audit target lookup accept the same target family where
possible: core opportunity id, hypothesis id, incident id, alert id, snapshot
id, card id, card path, watchlist key, symbol, or coin id. Notification inbox
rows print a `feedback_target` line before the helper command. Opportunity audit
reads the feedback artifact, so after marking useful/junk/watch the audit for
the same core id or card path should show `feedback status: has_feedback`. Run
`make event-alpha-feedback-readiness PROFILE=notify_llm_quality` to check that
cards have current lineage and feedback targets, alert snapshots expose feedback
targets when present, inbox rows are reviewable, and calibration fields are
present before treating a namespace as ready for feedback-loop tuning. No-send
fixture/e2e namespaces may be feedback-ready from current cards even when they
do not have alert snapshots; `no_alert_snapshots_found` is a warning, not a
blocker.

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
