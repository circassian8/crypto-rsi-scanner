# Event Alpha Radar Runbook

Event Alpha is a research-only catalyst radar. It can discover evidence,
refresh watchlist rows, route research digests, write review artifacts, and
export proposed eval cases. It must not trade, paper trade, write normal RSI
signal rows, or let LLM/search/watchlist output create `TRIGGERED_FADE`.

## Consolidation Surfaces

Event Alpha package shims now live under `crypto_rsi_scanner/event_alpha/`.
Old top-level imports remain supported while future code moves into the
subpackage in small, tested slices. CLI facade code lives under
`crypto_rsi_scanner/cli/`, with the root `main.py` delegating through that
facade.

Package ownership for new code:

- `event_alpha/providers`: provider activation, readiness, source registry,
  source packs, provider health, and provider-specific preflight/rehearsal
  orchestration.
- `event_alpha/radar`: integrated radar, market state/reaction/anomaly,
  evidence acquisition, CoreOpportunity rows, source coverage, opportunity
  verdicts, impact hypotheses, and incidents.
- `event_alpha/artifacts`: artifact context, paths, schema v1, run ledgers,
  retention, and locks.
- `event_alpha/notifications`: preview, no-send delivery, send-readiness,
  go/no-go, inbox, SLO, pack, pause, final check, sender, and formatting.
- `event_alpha/outcomes`: outcomes, calibration, feedback, burn-in, quality,
  priors, and policy simulation.
- `event_alpha/doctor`: schema-first doctor phases, check registry, plugin
  checks, and reports.
- `event_alpha/namespace`: namespace status and lifecycle reporting.
- `cli/`: parser, dispatch, and command-group modules.

No retained old flat Event Alpha import paths remain as compatibility surfaces.
Any future retained entrypoint must be documented in
`research/PUBLIC_COMPATIBILITY_ENTRYPOINTS.md/json` and mirrored in
`research/EVENT_ALPHA_PUBLIC_COMPATIBILITY_ENTRYPOINTS.md/json`; deleted old
imports are tombstoned and are allowed to fail. New code and docs should use
canonical package paths, tombstone tests cover deleted old paths, and old
top-level modules should not receive new implementation logic. Artifact doctor
warns if a deleted old shim path is reintroduced.

CLI rules:

- Parser construction belongs in `crypto_rsi_scanner/cli/parser.py`.
- Dispatch belongs in `crypto_rsi_scanner/cli/dispatch.py`.
- Command groups belong in `crypto_rsi_scanner/cli/commands_*.py`.

Test rules:

- New tests belong in `tests/event_alpha/`, `tests/rsi/`, or `tests/cli/`.
- `tests/test_indicators.py` is the compatibility umbrella runner.

Schema and doctor rules:

- New artifact field => update schema v1.
- New doctor check => register schema dependencies first.
- The artifact doctor is schema-first: namespace lifecycle, schema validation,
  schema safety, legacy checks, consistency checks, report.

Namespace lifecycle rules:

- Every new namespace needs status, retention policy, and explicit
  `safe_for_send_readiness`.
- Stale/archived/quarantine namespaces cannot be send-ready.
- Provider and fixture namespaces remain no-send/no-live by default.

Research-only/no-trading/no-paper/no-send guards remain active for all Event
Alpha operator paths. Nothing in this runbook authorizes live trading, paper
trading, execution, normal RSI signal writes, live Telegram sends in tests,
live provider calls by default, secret printing, or Event Alpha-created
`TRIGGERED_FADE`.

Useful consolidation checks:

- `make test-pytest PYTHON=python3`
- `make test-pytest-durations PYTHON=python3 PYTEST_DURATIONS=50`
- `make test-pytest-parallel PYTHON=python3 PYTEST_WORKERS=4`
- `make verify-fast PYTHON=python3` for local iteration; use full
  `make verify PYTHON=python3` before commit or handoff.
- `make event-alpha-namespace-lifecycle-report PYTHON=python3`
- `make event-alpha-list-active-namespaces PYTHON=python3`
- `make event-alpha-archive-stale-namespaces PYTHON=python3`

When adding an artifact row, update schema v1 first, then the writer, doctor
validation, tests, and docs. When adding a doctor check, register its schema
field dependencies before adding enforcement. When adding a namespace, declare
its lifecycle status, key artifacts, retention policy, and send/burn-in safety.

## Adding New Surfaces

Add a provider:

1. Put activation/preflight/readiness orchestration in `event_alpha/providers`.
2. Keep reusable provider adapters in lower-level provider packages.
3. Start fixture/no-call; add live rehearsal only with explicit allow flag,
   request ledger, redaction, request budget, no-send mode, and provider health.
4. Add source coverage, integrated radar, doctor, and fixture tests.

Add a radar artifact:

1. Declare schema v1 fields first.
2. Write under the namespace with artifact helpers and relative operator paths.
3. Attach canonical identity, source lineage, freshness, safety counters, and
   schema metadata.
4. Add card/brief/source-coverage/doctor surfaces only after schema and tests.

Add a notification lane:

1. Add planning/rendering in `event_alpha/notifications`.
2. Preserve no-send previews, structured skip telemetry, and delivery
   `status`/`status_detail`.
3. Keep real sends behind explicit guard/final-check commands.
4. Keep message copy research-only and not a trade signal.

Add an outcome/calibration field:

1. Update schema v1.
2. Add writer/report fields.
3. Register doctor dependencies where checks use the field.
4. Keep priors recommendation-only with `auto_apply=false` and low-sample
   warnings.

## Integrated Radar Artifact Review

The integrated radar cycle merges sidecar evidence from market anomalies,
official exchange announcements, scheduled/unlock catalysts, derivatives
crowding, and fade-review rows into one portable operator artifact set. It is a
local research surface only: generated delivery rows are no-send previews unless
the explicit Telegram send guard is enabled outside tests.

Useful commands:

- `make event-alpha-integrated-radar-smoke PYTHON=python3`
- `make event-alpha-integrated-radar-outcome-smoke PYTHON=python3`
- `make event-alpha-integrated-radar-outcome-report PYTHON=python3`
- `make event-alpha-integrated-radar-calibration-report PYTHON=python3`
- `make event-alpha-integrated-radar-calibration-export-priors PYTHON=python3`

The cycle writes portable review artifacts under the selected namespace,
including:

- `event_integrated_radar_candidates.jsonl`
- `event_integrated_radar_notification_deliveries.jsonl`
- `event_integrated_radar_notification_preview.md`
- `event_integrated_radar_outcomes.jsonl`
- `event_integrated_radar_outcome_report.md`
- `event_integrated_radar_calibration_report.md`
- `event_integrated_radar_calibration_priors.json`

Rendered Markdown should use artifact-relative labels rather than absolute
machine paths. Structured JSONL rows may keep relative path fields for tooling,
but operator Markdown must not expose `/Users`, `/tmp`, `/mnt/data`, secrets,
database paths, or other machine-local noise. The calibration priors export is
advisory only: it does not update thresholds, send Telegram, create normal RSI
rows, open paper/live trades, execute orders, or create `TRIGGERED_FADE`.

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
CryptoPanic validation is tag-aware: a matching `currency_tags`/`currencies`
entry should be preserved on evidence rows and may add
`cryptopanic_currency_tag_match` only when it matches the validated symbol or
coin id. A CryptoPanic post that is merely hot, bullish, important, or rising is
context only until the source text also supports the catalyst and token impact
path. Official exchange rows should preserve the exchange, normalized event kind
(`exchange_listing`, `perp_listing`, `exchange_delisting`, or
`exchange_product_event`), product type, symbols, pairs/contracts,
announcement time, and source URL so cards and audits can show exactly what the
official source proves.
The official exchange announcement pack writes three local research artifacts:
`event_exchange_announcements.jsonl`, `event_official_exchange_events.jsonl`,
and `event_official_listing_candidates.jsonl`. Use
`make event-alpha-official-exchange-smoke PYTHON=python3` to prove fixture
normalization, source coverage, daily brief output, and strict artifact-doctor
checks without sends. Use `make event-alpha-official-exchange-report
PROFILE=<profile> ARTIFACT_NAMESPACE=<namespace> PYTHON=python3` to inspect a
configured namespace. Official listing/perp/risk packs require
`source_class=official_exchange`; CryptoPanic or broad-news listing rumors are
context only for these packs unless another official/structured source validates
the exchange catalyst. Simple BTC/ETH/stable quote/base pair additions are
diagnostic by default and should not become `EARLY_LONG_RESEARCH` unless
`RSI_EVENT_ALPHA_ALLOW_MAJOR_PAIR_CATALYSTS=1` is set or the announcement is a
material access/product change.

Market return units are explicit. Raw/latest market snapshots keep fractional
returns (`0.012` means `+1.2%`). Event market-state snapshots are persisted in
percentage points with `return_unit=percent_points` and should also carry
`source_return_unit`. Cards, daily briefs, and reports format returns with `%`
signs for humans. A card showing `+148%` when the latest snapshot is `0.0148`
is a unit bug; strict artifact doctor checks for that double-scaling pattern.
Structured calendar and unlock rows have narrower but stronger contracts.
CoinMarketCal-style rows should preserve `event_time_source=structured_calendar`,
`source_class=structured_calendar`, event category/type, event-time confidence,
confirmation/source confidence, source URL/original source URL, and token
identity. They can support direct project-event source packs only when the
calendar item is specific enough to explain a dated catalyst, such as mainnet
launch, hard fork, protocol upgrade, governance, TGE, listing, or delisting;
generic calendar entries such as AMAs remain local/review evidence unless
another stronger source validates the impact path. Tokenomist-style rows should
preserve `event_time_source=structured_unlock`, `source_class=structured_unlock`,
unlock type/category, unlock percentage, materiality, event time, and token
identity. Unlock/supply source packs require material, non-stale supply pressure
before a row can support digest/watchlist promotion; small, missing-size, or
stale unlock rows explain what is missing but should not become confirming
evidence by themselves.
The scheduled catalyst/unlock pack writes these local research artifacts under
the selected Event Alpha namespace:

- `event_scheduled_catalysts.jsonl`
- `event_unlock_candidates.jsonl`
- `event_scheduled_catalyst_report.md`
- `event_unlock_risk_report.md`

Use `make event-alpha-scheduled-catalyst-smoke PYTHON=python3` to prove
fixture normalization, source coverage, daily brief output, and strict artifact
doctor checks for project events and unlock rows. Use
`make event-alpha-unlock-risk-smoke PYTHON=python3` when the focus is unlock
supply risk. Use `make event-alpha-scheduled-catalyst-report PROFILE=<profile>
ARTIFACT_NAMESPACE=<namespace> PYTHON=python3` to inspect a configured
namespace. Media-only CryptoPanic/RSS/GDELT text that merely says a token has an
unlock is not structured unlock proof; strict unlock/supply lanes require
structured/official/supply evidence, event time, source URL, and materiality.
The derivatives crowding pack is a market-risk review lane, not catalyst proof
and not a trigger. It normalizes Coinalyze-style open interest, funding,
liquidation imbalance, long/short ratio, basis, perp/spot volume, exchange,
market, provider, and freshness fields into:

- `event_derivatives_state.jsonl`
- `event_derivatives_crowding_candidates.jsonl`
- `event_fade_short_review_candidates.jsonl`
- `event_derivatives_crowding_report.md`

Use `make event-alpha-derivatives-smoke PYTHON=python3` to prove fixture
normalization, daily-brief/card output, and strict artifact-doctor checks. Use
`make event-alpha-fade-review-smoke PYTHON=python3` when the focus is the
manual fade/short-review lane. A `FADE_SHORT_REVIEW` row requires evidence that
the move already happened plus crowding/exhaustion and liquidity sanity; poor
liquidity stays `RISK_ONLY`. The lane is research-only metadata and cannot
create `TRIGGERED_FADE`, normal RSI rows, Telegram sends, paper trades, live
trades, or execution. `event_derivatives_crowding_candidates.jsonl` keeps every
evaluated derivatives candidate for audit/doctor checks; `event_fade_short_review_candidates.jsonl`
is only the review-ready subset.
Source-pack acquisition rows now persist the attempted plan, execution results,
query execution statuses, provider coverage statuses, accepted/rejected samples,
source-pack sufficiency booleans, and canonical post-policy final fields. If no
evidence was accepted and the status is `rejected_results_only`, `no_results`,
`skipped_budget`, or another unresolved/no-confirmation state, raw acquisition
rows must not retain `final_opportunity_level=validated_digest`; reconciliation
caps those rows to local/exploratory unless the canonical core row has separate
confirming evidence. Treat these rows as audit evidence; they can improve a
local research verdict only after deterministic identity, catalyst-link,
impact-path, source-quality, and quality-gate checks pass.

The integrated radar cycle is the operator-facing artifact orchestrator for
these sidecar packs. It writes:

- `event_integrated_radar_candidates.jsonl`
- `event_integrated_radar_input_manifest.json`
- `event_integrated_radar_report.md`
- `event_alpha_source_coverage.md`
- `event_alpha_source_coverage.json`
- canonical `event_core_opportunities.jsonl`
- research cards, daily brief, run ledger, and no-send notification preview

Use `make event-alpha-integrated-radar-smoke PYTHON=python3` for the
fixture-backed proof cycle and `make event-alpha-integrated-radar-doctor
PYTHON=python3` for the strict consistency check. Runtime cycles support three
input modes: `--event-alpha-integrated-radar-auto`,
`--event-alpha-integrated-radar-run-sidecars`, and
`--event-alpha-integrated-radar-load-existing`. Integrated candidate fields are
canonical when persisted: operator-facing CoreOpportunity rows and cards should
preserve the candidate's opportunity type, market state, route/state, score,
requirements, reason/warning codes, source URL, official exchange event,
scheduled catalyst/unlock evidence, derivatives evidence, and market snapshot.
Diagnostics such as sector-only rows stay in the diagnostics appendix by
default. Strict artifact doctor blocks silent lane upgrades, source/event loss,
missing input manifests/source-coverage JSON, card mismatches, and diagnostics
leaking into default operator sections.

Source enrichment is now quality-gated before LLM extraction or catalyst-frame
analysis can consume fetched article bodies. Enrichment cache rows should carry
`extractor_version`, `cleaner_version`, fetched/final/canonical URLs, redirect
chain, title/byline/source/published metadata when available, `body_char_count`,
`boilerplate_ratio`, `ticker_sidebar_detected`, deterministic `source_triage`,
and `article_quality_status`. Only `good` and `fixture_text_used` bodies replace
the original provider summary in LLM packets. `redirect_placeholder`,
`paywall_or_blocked`, `fetch_failed`, `thin`, `boilerplate_heavy`,
affiliate/SEO, recap, and context-only prediction-market rows should remain
raw observations or diagnostics unless another strict evidence source validates
the token and catalyst. Cards, audits, daily briefs, and source coverage reports
show article-quality status when evidence rows carry enrichment metadata.

Use the source coverage dashboard when a run produces few or no strict
research-alert decisions and you need to see whether the blocker is missing
CryptoPanic/exchange/calendar/unlock/derivatives/market evidence, provider
backoff, budget skipping, or rejected-only acquisition results:

```bash
make event-alpha-cryptopanic-preflight PROFILE=notify_llm_deep PYTHON=python3
make event-alpha-notify-llm-deep-cryptopanic-no-send-rehearsal PYTHON=python3
make event-alpha-source-coverage-report PROFILE=notify_llm_deep_rehearsal PYTHON=python3
make event-alpha-source-coverage-report PROFILE=notify_llm_deep PYTHON=python3
make event-alpha-source-coverage-report PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal PYTHON=python3
make event-alpha-source-coverage-report PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_research_review_smoke PYTHON=python3
make event-alpha-daily-brief PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_research_review_smoke PYTHON=python3
```

The dashboard is read-only and writes
`event_fade_cache/<artifact_namespace>/event_alpha_source_coverage.md` plus a
JSON sidecar for review bundles. `PROFILE` controls the runtime profile;
`ARTIFACT_NAMESPACE` controls which artifact namespace is inspected. The report
shows configured, missing, healthy, unknown/not-observed, and degraded providers
by source pack; accepted/rejected/skipped acquisition outcomes; whether evidence
absence is meaningful; and the provider/source pack most likely to improve the
next run. Each pack also prints recommended actions, such as configuring
CryptoPanic token/news coverage, restoring official exchange announcement
feeds, raising evidence-acquisition query budgets, or fixing feed-level RSS
quarantine/backoff. If same-day CryptoPanic Growth requests succeeded, source
coverage should treat stale CryptoPanic provider-health backoff as reconciled and
should not recommend configuring, restoring, or verifying the token for that
namespace; use the request ledger and the `backoff_reconciled_after_success`
flag for audit. Treat CoinGecko and DefiLlama-style rows as
market/protocol metric evidence only: they can support market confirmation or
source coverage, but they do not prove official confirmation or catalyst
impact-path validation by themselves.

CryptoPanic runs against the current Growth API route by default:
`https://cryptopanic.com/api/growth/v2/posts/`. Configure
`RSI_EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN` in `.env`; the code also accepts the
legacy aliases `RSI_EVENT_DISCOVERY_CRYPTOPANIC_AUTH_TOKEN`,
`CRYPTOPANIC_AUTH_TOKEN`, `CRYPTOPANIC_API_KEY`, and `CRYPTOPANIC_TOKEN`.
Growth Weekly requests send `auth_token` plus only `public`/`following`,
`currencies`, `regions`, `filter`, `kind`, and `page`. Do not expect
Growth Weekly to use `search`, `size`, `last_pull`, `with_content`,
`panic_period`, or `panic_sort`; those remain Enterprise-only and are omitted
unless the configured plan is explicitly `enterprise`.

The Growth Weekly plan is capped at 600 requests per week. Event Alpha records
actual attempted CryptoPanic requests in
`event_fade_cache/<artifact_namespace>/cryptopanic_request_ledger.jsonl` with
redacted URLs, status code, result count, currency batch, page, profile, and
namespace. The default guardrails are conservative:
`RSI_EVENT_DISCOVERY_CRYPTOPANIC_REQUESTS_PER_RUN_LIMIT=10`,
`RSI_EVENT_DISCOVERY_CRYPTOPANIC_REQUESTS_PER_DAY_SOFT_LIMIT=80`,
`RSI_EVENT_DISCOVERY_CRYPTOPANIC_MAX_PAGES_PER_QUERY=1`,
`RSI_EVENT_DISCOVERY_CRYPTOPANIC_MAX_CURRENCIES_PER_REQUEST=10`, and
`RSI_EVENT_DISCOVERY_CRYPTOPANIC_MIN_SECONDS_BETWEEN_REQUESTS=1`. Skipped
quota/budget calls do not consume ledger rows.
CryptoPanic currency requests are planned as validated uppercase tickers only.
CoinGecko slugs, lowercase raw terms, `SECTOR`, empty/global currency batches,
and unvalidated common-word collisions are rejected before request
construction. Repeated normalized request keys within one run are deduped from
the in-memory request cache and surfaced through run-ledger and artifact-doctor
request-planning counters.

If CryptoPanic is configured but unusable, inspect the same ledger rather than
guessing whether the token is missing. Live fetches record `content_type`,
`response_bytes`, `body_excerpt_redacted`, `parse_error_message`,
`provider_health_effect`, `quota_counted`, status code, and a classified
`error_class` such as `json_parse_error`, `empty_response`, `plan_mismatch`,
`plan_or_endpoint_unavailable`,
`rate_limited_or_forbidden`, `auth_failed`, `server_error`, `network_error`,
`provider_backoff`, or `quota_exhausted`. Source coverage reports use
`observed_healthy`, `observed_partial_success`, `observed_no_results`,
`observed_parse_error`, `observed_plan_mismatch`, `observed_rate_limited`,
`observed_backoff_without_success`, `quota_exhausted`,
`configured_not_observed`, and `not_configured` so missing configuration,
successful observation, partial success, and unusable responses are not
collapsed into one status. Artifact doctor strict mode blocks unredacted token
excerpts or HTTP-failure rows missing status codes.

A `plan_mismatch` means the token does not belong to the configured supported
plan route. Do not follow a response hint back to the discontinued Developer
plan. Replace or upgrade the token, set `RSI_EVENT_DISCOVERY_CRYPTOPANIC_PLAN`
to the matching active plan, and rerun the bounded preflight before resetting
provider health.

The CryptoPanic preflight prints only redacted key/config state, endpoint,
plan, quota usage, source packs, provider health/backoff, and the targeted reset
command. The rehearsal target uses the real `notify_llm_deep` path with
`RSI_EVENT_ALERTS_ENABLED=0` and the
`notify_llm_deep_cryptopanic_rehearsal` namespace, so it can prove whether
CryptoPanic was attempted and accepted/rejected evidence without sending
Telegram or mutating trading/live RSI state. If stale missing-key/backoff state
survives after adding the token, run:

```bash
make event-alpha-provider-health-reset PROFILE=notify_llm_deep SERVICE=cryptopanic CONFIRM=1 PYTHON=python3
```

For smoke namespaces such as `notify_llm_deep_research_review_smoke`, the
runtime profile can intentionally remain `notify_llm_deep` while
`ARTIFACT_NAMESPACE` points at the smoke artifact directory. The Make report
targets include test artifacts when the namespace is a known smoke namespace,
so the daily brief should show the selected run profile/namespace, canonical
core count, source coverage path, and research-review lane from that namespace.
Strict artifact doctor blocks a fresh brief that claims no selected run, renders
zero core opportunities while the core store has rows, omits an expected
research-review lane, or loses the source-coverage link.

Advanced market confirmation is split by evidence family. Coinalyze-style
derivatives rows should preserve open-interest change, funding, liquidation
volume, long/short ratio, futures volume, and a freshness status. They are most
useful for perp/listing squeeze and proxy-fade/attention playbooks, but stale
or missing derivatives are a coverage gap, not catalyst proof. GeckoTerminal-
style DEX rows should preserve pool liquidity, DEX volume, pool age, price
impact/spread proxy, new-pool status, and freshness; proxy-attention and
microcap rows need liquidity sanity before high-priority treatment. DefiLlama-
style protocol rows should preserve TVL, TVL change, fees/revenue,
protocol/DEX volume, and freshness; strategic/protocol/security rows can use
these metrics to explain market reaction or TVL outflow. Cards, audits, daily
briefs, and quality review show derivatives, DEX liquidity, and protocol
metric confirmation separately from spot market confirmation. These fields are
research evidence only and cannot bypass source-pack, identity, impact-path,
quality, live-confirmation, router, or `event_fade.py` gates.

Each source-pack row now also prints pack-level `provider_coverage_status`,
role-specific provider health, explicit coverage-gap reasons, and the providers
missing or degraded for confirmation. A provider may be healthy for one role and
degraded for another, for example RSS event intake versus RSS catalyst search.
Interpret `unknown`, `degraded`, `unavailable`, and `not_configured` as unknown
coverage, not as proof that no confirming evidence exists. A configured provider
with no provider-health row is `unknown/not observed`, not healthy. Artifact
doctor flags missing coverage artifacts/metadata, missing provider
recommendations, unobserved-provider coverage warnings, and contradictions where
a degraded/unavailable/not-configured pack is treated as meaningful absence.

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
When reviewing cards or audits, look for compact provider-specific sample
details: CryptoPanic accepted samples should show the matching tag and
`tag_match=true`; official exchange accepted samples should show the exchange,
pair, or contract where available. If those details are missing from a fresh
artifact, rerun the evidence-acquisition smoke before trusting the source-pack
summary.
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
reference should point at the `agg:...` core opportunity. Fresh daily digest and
instant-escalation delivery rows must carry array-backed
`core_opportunity_ids`, `canonical_symbols`, `canonical_coin_ids`,
`canonical_card_paths`, `feedback_targets`, requested/source ids, and identity
reconciliation metadata. Scalar identity fields remain for compatibility and
should point at the first item only, never comma-joined multi-item values.
Rows that cannot satisfy that contract must remain explicit diagnostics/legacy
rows, not delivered core-opportunity notifications. The rendered Telegram
body is intentionally compact: it shows candidate, catalyst, route/level,
impact role, evidence status, market status, and check-next text, while hiding
raw alert ids, card ids, full local paths, and repeated boilerplate. Each
delivery attempt appends its lane section to
`event_alpha_notification_preview.md`, so a run with both high-priority and
daily digest lanes can be reviewed in one file. Use:

```bash
make event-alpha-notification-format-smoke PYTHON=python3
make event-alpha-notify-llm-deep-no-send-smoke PYTHON=python3
make event-alpha-notification-deliveries-report PROFILE=fixture PYTHON=python3
```

Before enabling Telegram delivery for the real deep LLM path, run the
real-profile no-send rehearsal:

```bash
make event-alpha-notify-llm-deep-real-no-send-rehearsal PYTHON=python3
make event-alpha-send-readiness PROFILE=notify_llm_deep_rehearsal PYTHON=python3
make event-alpha-send-go-no-go PROFILE=notify_llm_deep_rehearsal PYTHON=python3
make event-alpha-daily-brief PROFILE=notify_llm_deep_rehearsal PYTHON=python3
make event-alpha-notification-inbox PROFILE=notify_llm_deep_rehearsal PYTHON=python3
make event-alpha-notification-inbox PROFILE=notify_llm_deep_rehearsal BURN_IN_REVIEW=1 PYTHON=python3
make event-alpha-artifact-doctor PROFILE=notify_llm_deep_rehearsal STRICT=1 EVENT_ALPHA_ARTIFACT_DOCTOR_DELIVERY_SCOPE=latest_run PYTHON=python3
```

For a faster first pass through the same real-profile no-send path, use the
capped rehearsal:

```bash
make event-alpha-notify-llm-deep-real-no-send-rehearsal-fast PYTHON=python3
make event-alpha-send-readiness PROFILE=notify_llm_deep_rehearsal PYTHON=python3
make event-alpha-send-go-no-go PROFILE=notify_llm_deep_rehearsal PYTHON=python3
```

When inspecting a smoke/rehearsal namespace with a runtime profile such as
`notify_llm_deep`, pass the namespace explicitly:

```bash
make event-alpha-send-go-no-go PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal PYTHON=python3
```

Daily digest lanes are confirmed and grouped before formatting. Live-style
profiles require accepted source-pack evidence, official/structured evidence,
matching CryptoPanic token/catalyst proof, strong direct source evidence, or
fresh non-generic market confirmation before an item can stay in daily digest.
Narrative packs with higher false-positive risk (`fan_sports_pack`,
`proxy_preipo_rwa_pack`, and `political_meme_pack`) are stricter by default:
a single accepted source-only item without market confirmation, official or
structured confirmation, or a second accepted evidence row is moved to the
research-review/local path. Operators can explicitly allow this class with
`RSI_EVENT_ALPHA_ALLOW_SOURCE_ONLY_NARRATIVE_DIGEST=1`, but the default burn-in
posture is conservative. Unconfirmed support rows are moved to
research-review/local diagnostics. The Telegram digest renders the top
`RSI_EVENT_ALPHA_DAILY_DIGEST_MAX_ITEMS` grouped items and points to the local
brief for overflow.

For a deterministic delivery-plan rehearsal that injects fixture VELVET/AAVE/BTC
core opportunities through the same `notify_llm_deep` notification planning
path, use:

```bash
make event-alpha-notify-llm-deep-real-no-send-rehearsal-with-fixture-candidate PYTHON=python3
make event-alpha-send-readiness PROFILE=notify_llm_deep_fixture_rehearsal PYTHON=python3
make event-alpha-send-go-no-go PROFILE=notify_llm_deep_fixture_rehearsal PYTHON=python3
```

This target uses the actual `notify_llm_deep` profile and passes
`--event-alert-send`, but forces `RSI_EVENT_ALERTS_ENABLED=0`, so the delivery
path writes would-send/blocked ledgers and
`event_alpha_notification_preview.md` without contacting Telegram. Inspect the
preview, send-readiness report, daily brief, inbox, deliveries report, and
strict doctor output before running any `RSI_EVENT_ALERTS_ENABLED=1` command. A
passing send-readiness report requires the latest run to be complete, strict
artifact doctor to have no blockers, preview counts to match the run ledger,
delivery rows to carry canonical core identity and explicit `delivery_mode`,
`delivery_state`, `status_detail`, `send_guard_enabled`, `would_send`, `sent`,
and `failed` fields, `notification_preview_path_source` to resolve through
`relpath` or `namespace_default` when possible, no rejected-only/no-market
candidate to be would-send eligible, and Telegram token/chat id to be present
when the send guard is enabled. The go/no-go report should then show
`READY_FOR_NO_SEND_REVIEW` for a clean rehearsal with the send guard disabled,
or `READY_FOR_SEND` only when both the send guard and Telegram credentials are
enabled. The heartbeat preview should show the same
completed/raw-event/extraction/core-opportunity/LLM call/skip and delivery-lane
due/sent/blocked numbers as the latest run ledger. No-send rehearsal rows
should say `would_send_but_guard_disabled` and should not be counted as provider
delivery failures. Use
`EVENT_ALPHA_ARTIFACT_DOCTOR_DELIVERY_SCOPE=all_rows` only when intentionally
auditing old delivery rows; the default/latest-run scope proves the fresh run
while reporting stale pre-core delivery identity rows as migration diagnostics.

Live-style notification profiles also re-check confirmation before digest
delivery. A core row whose evidence acquisition is `rejected_results_only`,
`no_results`, `skipped_budget`, or otherwise non-confirming stays local-only
unless another strong confirmation exists: accepted source-pack evidence,
official/structured/tagged source evidence, or fresh non-generic market
confirmation on a real impact path. Artifact doctor strict mode checks delivery
identity/core-store mismatches, missing core ids, missing feedback targets,
missing canonical card paths, noncanonical alert ids, rejected-only digest
items, missing previews, raw debug dumps, and absolute local paths in previewed
Telegram bodies.

For broad assets such as BTC, ETH, and SOL, Strategy/MSTR treasury valuation,
public-company discount/premium, ETF/company-equity valuation, and generic
CME/SEC/CFTC market-structure articles are context, not direct token
confirmation. They should render as local/exploratory or near-miss rows unless
accepted source-pack evidence, official/tagged token evidence, a direct
token/project event, or fresh non-generic market confirmation upgrades the
candidate. Artifact doctor reports
`strategic_broad_asset_digest_without_confirmation` if a delivered/promoted
digest violates this rule.

`notify_no_key` uses public RSS, one broad GDELT context fetch, Polymarket,
live CoinGecko universe, market enrichment, anomaly scanning, catalyst search,
watchlist monitoring, router lanes, and auto-written research cards.
`notify_llm` uses the same source
set plus OpenAI extraction/advisory metadata, bounded full-source enrichment for
LLM context, and bounded parallel OpenAI defaults: 100 calls/run, 500 calls/day,
$15/day estimated cap, 3 concurrent LLM calls, 30s LLM HTTP timeouts, 10
enriched source rows/run, a 168-hour cache TTL, and a 600s notification runtime
budget. Like `notify_no_key`, `notify_llm` sends operator-visible output on
every clean scheduled run; cooldown/content dedupe is disabled while the run
lock and in-flight delivery guard remain active. Use `notify_llm_deep` only
when you explicitly want a deeper review cycle: it keeps the same research-only
send guards and per-run delivery behavior but raises the LLM/enrichment caps to
250 calls/run, 1500 calls/day, 3 concurrent LLM calls, and 45s LLM timeouts.
All live OpenAI providers in one cycle share a fail-fast gate. A rate-limit,
quota, authentication, or access response stops unscheduled extraction,
catalyst-frame, and relationship calls and is reported separately from budget
skips. GDELT is intentionally absent from automatic catalyst-search providers
during the upstream DOC API migration; a 429 creates immediate provider
backoff rather than an in-cycle retry.

## Market-State Anomaly Artifacts

Use the standalone anomaly scan when you want a market-first research pass from
cached/fixture market rows before catalyst search:

```bash
make event-alpha-market-anomaly-scan PROFILE=no_key_live
make event-alpha-market-anomaly-smoke PYTHON=python3
```

The scan writes only local research artifacts under the selected Event Alpha
namespace:

- `event_market_state_snapshots.jsonl`
- `event_market_anomalies.jsonl`
- `event_market_anomaly_report.md`

Anomaly rows are catalyst-search seeds. They should show `created_alert=false`,
`needs_catalyst_search=true`, and `suggested_source_packs_to_search`. They are
not alert snapshots, not Telegram notifications, not paper trades, not normal
RSI rows, and not `TRIGGERED_FADE`. Daily briefs display them in “Market
Anomalies Without Confirmed Catalyst”; artifact doctor checks malformed anomaly
rows, including missing snapshots, unsupported confirmed-breakout claims,
suspicious illiquid moves leaking into confirmed lanes, and alert fields leaking
into anomaly rows.

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

Event Alpha also has a stricter `research_review_digest` lane for near-miss
review leads during burn-in. It is separate from daily digest, instant
escalation, triggered fade, exploratory digest, and heartbeat lanes. It is
research-review only: each Telegram body must say the candidates are not
alertable, are missing confirmation, and are not trade signals. Eligibility is
intentionally narrow: exploratory or explicitly allowed local-only level,
validated symbol/coin id, score above
`RSI_EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_MIN_SCORE`, not already alertable, not
sector-only unless configured, and not source-noise/ticker-collision/
generic-cooccurrence/diagnostic/support/control. By default it sends only when
strict alert lanes have no due candidates; set
`RSI_EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_SEND_WITH_ALERTS=1` only when the
operator explicitly wants review leads alongside strict alerts. Smoke it with:

```
make event-alpha-research-review-digest-smoke PYTHON=python3
make event-alpha-notify-llm-deep-research-review-no-send-smoke PYTHON=python3
```

The `notify_llm_deep` smoke uses the real notification profile with fixture
candidates and no-send guard enabled. It should write a blocked
`research_review_digest` delivery row, populate run-ledger fields
`research_review_digest_enabled`, `research_review_digest_candidates`,
`research_review_digest_would_send`, and pass strict artifact doctor. If those
fields show candidates but the delivery ledger has no research-review row, treat
the rehearsal as not ready.
Research-review delivery rows also carry structured skip telemetry:
eligible/rendered/skipped counts, skip-reason counts, skipped-family summaries,
selection policy, max items, ranking policy, and cooldown policy. Telegram
preview copy should show family-level skip summaries before raw skipped samples,
so an operator can see which opportunity families were deduped or capped without
reading every support row.
When a research-review row has a canonical CoreOpportunity, the Telegram body
should display the canonical core card basename and `agg:...` feedback target.
Hypothesis/watchlist ids remain in the local artifacts for audit, but they
should not be the visible feedback target for a canonical opportunity. Strict
artifact doctor checks `notification_body_card_mismatch_canonical`,
`notification_body_feedback_mismatch_canonical`, and
`research_review_body_uses_hypothesis_target_when_core_exists` before send
readiness can pass.

The burn-in inbox starts with a compact ranked review queue. It ranks strict
would-send rows, digest rows, research-review near-misses, upgrade candidates,
and non-diagnostic local learning rows by final score, review value, freshness,
and missing-evidence penalties. This ranking is presentation-only and does not
change routes or tiers. Source-noise, ticker-collision, support/control rows,
and other diagnostics are hidden from the compact queue by default; use the full
inbox, quality review, or diagnostic mode when you need row-level forensic
detail. Card references in compact output should be basenames, not absolute
machine paths.

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
specificity, market confirmation, source class, source domain, source pack,
market freshness, catalyst-frame status, final route, and playbook metadata
from the matched canonical core/card/watchlist row. Those calibration
dimensions should be present as top-level feedback fields; nested source
metadata remains audit context and should not be the only place a report has to
look. Calibration reports group feedback-only rows by those fields even when no
alert snapshot exists, but they only print recommendations; they do not alter
thresholds or routing.

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
total/latest/historical/default availability. Use `ALL_HISTORY=1` for the older
full-history view, `RUN_ID=<id>` for a specific cycle, and `SINCE=<iso-time>` for
a time window.
Add `INCLUDE_HISTORICAL=1` only when intentionally reviewing old/missing-schema
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

For deeper LLM notification burn-in, first run the fast deterministic final
check. It rebuilds the fixture rehearsal namespace, proves VELVET/AAVE
would-send with canonical core identity, excludes weak controls, captures noisy
support-report output, and never calls live providers or Telegram:

```bash
make event-alpha-telegram-no-send-final-check-fast PYTHON=python3
make event-alpha-telegram-send-readiness-final PROFILE=notify_llm_deep_fixture_rehearsal PYTHON=python3
```

Both targets end with the compact `main.py --event-alpha-telegram-final-check`
summary. Inspect the printed
`event_fade_cache/notify_llm_deep_fixture_rehearsal/event_alpha_notification_preview.md`
before trusting the notification copy. If the compact status is `NOT_READY`, do
not enable sends.

If you also want a live-provider rehearsal, run it separately. This path may call
configured live providers, may hit public-provider backoff/403/429 errors, and
may take several minutes:

```bash
make event-alpha-live-provider-readiness PROFILE=notify_llm_deep ARTIFACT_NAMESPACE=notify_llm_deep_rehearsal PYTHON=python3
make event-alpha-notify-llm-deep-real-no-send-rehearsal PYTHON=python3
make event-alpha-telegram-one-cycle-send-preflight PROFILE=notify_llm_deep_rehearsal PYTHON=python3
make event-alpha-send-readiness PROFILE=notify_llm_deep_rehearsal PYTHON=python3
make event-alpha-send-go-no-go PROFILE=notify_llm_deep_rehearsal PYTHON=python3
make event-alpha-notification-inbox PROFILE=notify_llm_deep_rehearsal PYTHON=python3
make event-alpha-notification-inbox PROFILE=notify_llm_deep_rehearsal BURN_IN_REVIEW=1 PYTHON=python3
make event-alpha-daily-brief PROFILE=notify_llm_deep_rehearsal PYTHON=python3
```

The live-provider readiness command is config/fixture inspection only. It writes
`event_live_provider_activation_readiness.json` and
`event_live_provider_activation_readiness.md`, names required env vars without
printing values, and keeps `live_calls_allowed=false` unless a future explicit
activation changes the policy. Use `make event-alpha-live-provider-readiness-smoke
PYTHON=python3` to prove this path without API keys, network calls, or sends.
Source coverage and the daily brief should link the readiness artifact and show
the activation order: Coinalyze derivatives/OI/funding, Bybit/Binance official
announcements, Tokenomist/Messari unlocks, GeckoTerminal/DefiLlama DEX/on-chain,
protocol fundamentals, then context/news.
See `research/EVENT_ALPHA_LIVE_PROVIDER_ACTIVATION_RUNBOOK.md` for the
no-call activation workflow, fixture/smoke proof expectations, and stale
namespace handling.

For Pro-model handoffs, use `make export-src-with-artifacts`. The exporter
overwrites `crypto_rsi_scanner_source_with_artifacts.zip`, excludes secrets and
machine-local noise, and clamps future-dated file mtimes to archive creation
time so extracted review copies do not trigger Makefile clock-skew warnings.

Use `make event-alpha-notify-llm-deep-real-no-send-rehearsal-fast PYTHON=python3`
for a capped preview/readiness smoke before the longer rehearsal. Before any
real send, confirm send-readiness reports a resolvable preview path, a clear
send/no-send guard state, explicit delivery status fields, matching
heartbeat/run-ledger summary numbers, and no rejected-only candidate that would
send. For a compact read-only final checklist over any existing namespace, run:

```bash
make event-alpha-telegram-final-send-checklist PROFILE=notify_llm_deep_rehearsal PYTHON=python3
make event-alpha-telegram-send-readiness-final PROFILE=notify_llm_deep_rehearsal PYTHON=python3
```

The safe one-cycle re-enable workflow is:

```bash
# 1. Deterministic no-send fixture check.
make event-alpha-telegram-no-send-final-check-fast PYTHON=python3

# 2. Inspect the fixture preview first.
sed -n '1,180p' event_fade_cache/notify_llm_deep_fixture_rehearsal/event_alpha_notification_preview.md

# 3. Run a real-profile no-send rehearsal.
make event-alpha-notify-llm-deep-real-no-send-rehearsal-fast PYTHON=python3

# 4. Gate the rehearsal and review inbox output.
make event-alpha-telegram-one-cycle-send-preflight PROFILE=notify_llm_deep_rehearsal PYTHON=python3
make event-alpha-send-go-no-go PROFILE=notify_llm_deep_rehearsal PYTHON=python3
make event-alpha-notification-inbox PROFILE=notify_llm_deep_rehearsal BURN_IN_REVIEW=1 PYTHON=python3

# 5. Inspect the real-profile preview.
sed -n '1,180p' event_fade_cache/notify_llm_deep_rehearsal/event_alpha_notification_preview.md

# 6. Only if the preview is acceptable, send exactly one guarded cycle.
RSI_EVENT_ALERTS_ENABLED=1 CONFIRM=1 make event-alpha-telegram-send-one-cycle PROFILE=notify_llm_deep PYTHON=python3

# 7. Audit immediately after the send.
make event-alpha-telegram-post-send-audit PROFILE=notify_llm_deep PYTHON=python3
```

If anything looks wrong after a send, pause the namespace before the next run:

```bash
make event-alpha-notification-pause PROFILE=notify_llm_deep REASON='operator review after one-cycle send'
```

For the full real-profile one-command no-send final checklist, run:

```bash
make event-alpha-telegram-no-send-final-check PROFILE=notify_llm_deep_rehearsal PYTHON=python3
```

That target runs the capped live-provider no-send rehearsal, strict artifact doctor,
send-readiness, compact final check, compact inbox, and daily brief, and prints
the local `event_alpha_notification_preview.md` path for inspection.

Normal heartbeat previews should use strict/research wording:
`Alertable decisions`, `Strict alerts`, `Research candidates`, and
`Raw source candidates`. If a preview shows legacy `Alertable decisions: 0 ·
Alerts: N` wording, treat the namespace as stale and rerun the preview/rehearsal
before using it for operator review. Research-review previews should also show
rendered candidates, eligible candidates, skipped candidates, and skip reasons
such as `max_items`, `lower_rank`, `duplicate_family`, `quality_blocked`, or
`already_represented`.

If a whole namespace is superseded by a newer rehearsal, mark it explicitly
instead of letting old rows fail current readiness checks:

```bash
make event-alpha-mark-namespace-stale \
  ARTIFACT_NAMESPACE=notify_llm_deep \
  SUPERSEDED_BY=notify_llm_deep_rehearsal \
  REASON='superseded by latest no-send rehearsal'
make event-alpha-prune-or-archive-stale-namespace ARTIFACT_NAMESPACE=notify_llm_deep
```

The prune/archive command is a dry-run plan by default. Strict artifact doctor
skips `stale_deprecated` namespaces unless `--event-alpha-include-stale-artifacts`
is passed for a deliberate legacy audit.

It uses the `notify_llm_deep` profile with bounded run/day LLM budgets, source
enrichment, optional CryptoPanic when the key is present, run locks, and the
same `RSI_EVENT_ALERTS_ENABLED=1` Telegram send guard.

Do not use stale `notify_llm_deep` namespace artifacts for send-readiness if
go/no-go or artifact doctor warns:

```text
This namespace contains pre-canonical notification delivery rows. Do not use it
for send-readiness. Run notify_llm_deep_rehearsal or fixture final check.
```

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
make event-alpha-cryptopanic-preflight PROFILE=notify_llm_deep
make event-alpha-provider-health-reset PROFILE=notify_llm_deep SERVICE=cryptopanic CONFIRM=1
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

For the authoritative policy-scoped 30-day North Star scorecard across daily
no-send runs, real candidates, feedback, labeled near misses, outcomes, and lane
freeze status:

```bash
make event-alpha-burn-in-scorecard
python3 main.py --event-alpha-burn-in-scorecard --days 30
```

Before promoting any research-send burn-in, run the checklist. It reports
whether the local artifacts are ready, which blockers remain, and the next
operator actions:

```bash
make event-alpha-burn-in-checklist
python3 main.py --event-alpha-burn-in-checklist --days 30
```

The checklist consumes the same authoritative scorecard and must remain
`READY_FOR_RESEARCH_SEND: no` while any contract threshold is unmet or a lane is
frozen. `event-alpha-feedback-readiness` answers only whether cards and targets
are ready to collect human feedback; it does not evaluate contract maturity.
`event-alpha-burn-in-readiness` answers whether the latest no-send run is
reviewable and prints the contract progress separately. `event-alpha-v1-readiness`
also prints the authoritative contract gate and cannot report calibrated
research-send readiness while that gate is false.

All readiness/checklist commands are advisory and artifact-only. They do not
enable sends, change thresholds, apply priors, write live signal rows, paper
trade, or execute.

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
conflicts are warnings by default; use `STRICT_HISTORICAL=1` only for a
deliberate historical-artifact audit that should fail on old pre-quality rows.

The doctor also checks watchlist lifecycle consistency. Fresh/current rows with
active `WATCHLIST` / `HIGH_PRIORITY` state that contradict a local-only,
zero-score, or insufficient-data quality verdict must either carry a non-active
`final_state_after_quality_gate` with `state_quality_capped=true`, or strict
doctor blocks the namespace. Properly capped rows are visible in daily brief and
quality review local-only sections, not in active watchlist sections. Legacy
uncapped rows are migration warnings unless `STRICT_HISTORICAL=1` is set. The
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

For historical artifact review only, include historical/default rows explicitly:

```bash
INCLUDE_HISTORICAL=1 make event-alpha-burn-in-scorecard PROFILE=no_key_live
INCLUDE_HISTORICAL=1 make event-alpha-artifact-doctor PROFILE=no_key_live
```

Do not use historical-included reports as promotion evidence. They are for
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
