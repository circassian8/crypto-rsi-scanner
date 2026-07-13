# Crypto Decision Radar North Star

Research-only product contract for trader-facing decision support. Crypto
Decision Radar organizes evidence for a human operator; it never places an
order, creates a live or Event Alpha paper trade, writes a normal RSI signal,
creates `TRIGGERED_FADE`, or sends a real notification by default.

- generated_at: `2026-07-13T17:17:38+00:00`
- schema_version: `crypto_decision_radar_north_star_v1`
- decision_model_version: `crypto_radar_decision_model_v2`
- canonical_projection_version: `crypto_radar_decision_projection_v1`
- primary_surface: local read-only dashboard
- notification_role: route human attention, never execution
- automatic_trading: `False`

## Product Boundary

Crypto Decision Radar is the trader-facing product layer. It combines market,
catalyst, technical, derivatives, on-chain, fundamental, and macro evidence
into one explicit research decision projection.

Event Alpha is the additive Catalyst Radar. It continues to own catalyst
discovery, source-strength classification, strict catalyst routes, and its
historical artifacts. A Decision Radar idea may be visible when the Catalyst
Radar still says `STORE_ONLY` or lacks a strong source. That is not a Catalyst
Radar gate change: the card must describe this precisely as not eligible for a
strict catalyst alert. Unknown catalyst lowers explanatory confidence and can
raise risk, but it is not a universal visibility blocker for a fresh, liquid,
identity-safe market-led idea.

The Decision Radar live observation campaign is its own measurement program,
`decision_radar_live_observation_campaign_v2`. It measures market snapshots,
Decision routes, market-context lineage, and observed outcomes. It is not Event
Alpha's catalyst burn-in, and its generations, candidates, or outcomes must
never be added to Catalyst Radar burn-in thresholds or scorecards. Historical
market-provenance `burn_in_*` fields remain readable compatibility metadata;
they do not silently reclassify or rewrite an older row.

## One Closed Decision Authority

`decision_model_values(raw_row)` returns the canonical, schema-backed Decision
v2 projection. Calling it on that projection is idempotent. The integrated
candidate stores this value once; CoreOpportunity, cards, Decision preview,
dashboard, review inbox, and pending outcome rows copy it. Rendering is a pure
projection and must not re-score an idea from partial context.

The projection carries all data required to validate and render itself:

- model/projection versions and `research_only=true`;
- primary and contributing origins, directional bias, catalyst status,
  confidence band, timing state, market phase, tradability, and spread;
- route, actionable flag, actionability/evidence/risk/urgency/chase-risk scores,
  preferred horizon, and expiry;
- hard blockers, soft penalties, warnings, why-now, supporting facts, missing
  information, main risks, confirmation conditions, and invalidation conditions;
- minimal resolvable calendar evidence and explicit RSI-context references;
- the canonical market-context reference (`source`, `observed_at`,
  `freshness_status`, and `market_snapshot_id`);
- observation ids, source/provider lineage, evaluation timestamp, and explicit
  no-send/no-trade/no-paper/no-RSI-write/no-trigger safety attestations.

Candidate/Core/card/preview/outcome/dashboard disagreement is a doctor blocker.
Numeric comparisons use one documented deterministic rounding tolerance; no
consumer may silently perform a materially new evaluation. The market-context
reference is copied with the projection across all surfaces; missing or changed
source, time, freshness, or snapshot identity is lineage drift and fails closed.

## Canonical Market Provenance v2

Every new market-led candidate carries the closed
`crypto_radar_market_provenance_v2` value (`contract_version=2`). Consumers copy
that value; they do not infer trust from legacy flat fields or accept caller-
asserted validity/counting flags. The contract records acquisition and candidate
source modes, provider call attempted/succeeded state, explicit live-provider
authorization, distinct request-ledger and provider-source artifact paths plus
SHA-256 fingerprints, provider generation id, cache status, feature basis, data
quality, validation errors, the named measurement program, and derived Decision
Radar campaign eligibility/count/reason.

Only a contract-valid `live_provider` / `live_no_send` generation with exact
authorized, attempted, successful provider lineage is eligible and counted for
the Decision Radar observation campaign. A fixture or mock may have a valid
provenance contract so it can prove mechanics, but it always remains
`decision_radar_campaign_eligible=false` and
`decision_radar_campaign_counted=false`. Replay, cache, preflight, malformed,
conflicting, and historical flat rows are never silently reclassified as fresh
real evidence. The legacy `burn_in_eligible`, `burn_in_counted`, and
`burn_in_reason` aliases remain compatibility fields inside market provenance
v2; a new Decision campaign row sets both legacy burn-in booleans to `false`
with `burn_in_reason=not_counted_separate_decision_radar_campaign`. Campaign
generations use `run_mode=operational`. Reporting treats historical burn-in
aliases only through a read-only adapter and never aggregates Decision market
observations into Event Alpha catalyst burn-in.

The request ledger and provider-source artifact are separate fingerprinted evidence
objects. Both paths and both digests must be present for a candidate-bearing
generation, and the provider generation id, feature-basis map, and data-quality
summary must agree across candidate, CoreOpportunity, card, preview, outcome,
operator state, and dashboard.

The request ledger carries only sanitized HTTP telemetry: endpoint path,
request start/end times, duration, HTTP status, result count, retry count, safe
error class, and cache behavior. Query parameters, headers, tokens, raw response
bodies, exception text, and other secret-bearing values are forbidden. The
namespace-local provider-health artifact must reconcile with this ledger.

## Thesis Origins

The allowed primary and contributing origins are:

1. `market_led`
2. `catalyst_led`
3. `technical_led`
4. `derivatives_led`
5. `onchain_led`
6. `fundamental_led`
7. `macro_led`

`primary_thesis_origin` is one origin. `thesis_origins` is an ordered,
deduplicated list whose first item is the primary origin. Legacy
`thesis_origin=mixed` remains readable compatibility metadata; it is not a new
primary-origin value.

## Operator Routes

| route | operator meaning |
|---|---|
| `high_confidence_watch` | Actionable research with the strongest current evidence and execution-quality checks. |
| `actionable_watch` | Actionable research that passes identity, freshness, liquidity, spread, turnover, manipulation, dedupe, and safety gates. |
| `rapid_market_anomaly` | Fresh, liquid, urgent market dislocation that passes the same execution-quality gates; catalyst may remain unknown. |
| `dashboard_watch` | Visible research worth monitoring, including ideas whose spread is unavailable but whose other evidence is sufficient. |
| `fade_exhaustion_review` | Human review of fresh exhaustion/crowding evidence; never an Event Alpha-created `TRIGGERED_FADE`. |
| `risk_watch` | Unscheduled downside or integrity risk without attached scheduled-calendar evidence. |
| `calendar_risk` | Scheduled-event risk backed by actual canonical calendar evidence. Calendar context alone never creates directional bias. |
| `diagnostic` | Hard-blocked, malformed, suspicious, stale, duplicate, control, or otherwise non-promotable evidence retained for audit. |

Every route must be proven end to end through candidate, CoreOpportunity when
eligible, card, Decision preview, outcome placeholder, and dashboard read
model. Diagnostic controls remain visible only in the diagnostic/audit surface.

## Spread, Timing, Urgency, Expiry, and Chase Risk

Spread states are `verified_good`, `verified_acceptable`, `verified_wide`,
`unavailable`, and `stale`. Actionable and rapid routes require
`verified_good` or `verified_acceptable`. Unavailable spread can support only a
non-actionable dashboard watch unless another trusted execution-quality source
verifies spread/tradability. The system never invents spread. Missing or stale
spread caps urgency at 55 even before any stricter market-data-quality cap.

Feature basis is explicit per market field. Proxy-only evidence cannot receive
urgent or actionable routing: actionability is capped at 64, evidence confidence
at 55, risk is floored at 55, and urgency is capped at 45. A cold, warming,
unavailable, or stale temporal baseline caps evidence confidence at 62, floors
risk at 48, and caps urgency at 45. When the affected anomaly basis is still
cross-sectional/proxy, the row remains review-only until the temporal evidence
warms; direct provider evidence is preserved rather than relabeled as a proxy.

Timing, market phase, urgency, preferred horizon, expiry, and chase risk are
first-class decision values, not card-only prose. A scheduled event may raise
risk and shorten expiry. Stale or expired ideas cannot remain actionable.
High urgency cannot override identity, freshness, liquidity, spread,
manipulation, dedupe, unit, path, secret, schema, or safety blockers.

Market return fields carry explicit per-field units. Fractions normalize to
percent points exactly once (`0.10` becomes `10%`); `10.0` declared as a
fraction is invalid and fails closed rather than becoming a silent 100x move.

## Calendar and RSI Context

Calendar evidence preserves event id, category, event time or impact window,
time certainty, importance, timezone, forecast, previous, actual, and surprise
when available. The canonical projection retains enough information to resolve
every reference. `calendar_risk` without real attached evidence is invalid.

RSI is a read-only supporting adapter. Its context and artifact references stay
in the canonical projection and may transparently adjust an existing idea, but
RSI context cannot create a Decision idea by itself and cannot write RSI rows,
send RSI alerts, create paper trades, or change RSI/backtest behavior. A
no-edge setup remains capped.

## Trader-Facing Surfaces

The local read-only dashboard is the primary surface. Decision v2 cards and the
Decision preview lead with operator route, actionability, evidence confidence,
risk, urgency, origins, catalyst status, timing/phase, tradability/spread,
expiry/horizon, why-now, and confirmation/invalidation. Catalyst Radar
classification appears second as explicitly labeled compatibility context.

The primary Decision preview sections are High-Confidence Ideas, Actionable
Ideas, Rapid Market Anomalies, Dashboard Watch, Fade / Exhaustion Review, Risk
Watch, and Calendar / Scheduled Risk. Every rendered item uses the canonical
projection and carries its dashboard pointer plus a research-only, human-
decision-required disclaimer. Legacy Event Alpha lane output stays separate
and diagnostic/compatible.

Dashboard GET/HEAD requests are read-only: no provider call, send, or artifact
write occurs. Route/origin/catalyst/timing filters, score sorting, current/
stale/fixture/live badges, exact run/revision/doctor status, and bounded local
sparklines may use only the already-authorized read model. Stale or untrusted
data is never displayed as currently actionable.

## Guarded Real/No-Send Market Generation

The supported operator flow is:

1. `make radar-market-no-send-readiness`
2. `make radar-market-no-send`
3. `make radar-market-no-send-smoke`
4. `make radar-market-campaign-report`

Readiness is no-write and no-network. A live CoinGecko request requires the
existing explicit `RSI_EVENT_DISCOVERY_UNIVERSE_LIVE=1` authorization and no
fixture mode. The generation uses a bounded top-liquid universe, records the
request-ledger/source-artifact lineage and observation time, computes market
anomalies, creates canonical Decision ideas, then builds cards, preview,
outcomes, operator state, the dashboard read model, and a credential-free JSON
plus Markdown pilot audit. The defaults remain research-only and no-send, with
zero trades, paper trades, normal RSI writes, or `TRIGGERED_FADE` creation.

`radar_market_history_cache/event_market_history.jsonl` is the bounded mutable
live/no-send research cache. Every generation copies an exact fingerprinted
`event_market_history.jsonl` snapshot into its own namespace; fixture and mock
history remains generation-local and can never seed the live cache. A namespace
behind the authoritative dashboard pointer is immutable, so each later live
cycle uses a new generation namespace while retaining the shared bounded
baseline.

The Make target generates a lowercase UTC-suffixed namespace for every live
cycle. Any already-existing generation directory is single-use and blocks
before the provider adapter, even when it was never published. An explicit
`RADAR_MARKET_NO_SEND_NAMESPACE` must likewise be new. Clean zero-idea cycles
still materialize canonical empty CoreOpportunity/card surfaces so missing
artifacts cannot be confused with an exact zero.

The v1 history policy retains at most 45 days and 256 observations per asset,
uses a default one-hour minimum observation spacing, and requires eight strictly
earlier cadence-counted observations plus the required time coverage for a warm
feature baseline. A rapid observation is retained as evidence with
`baseline_counted=false` and `baseline_counting_status=too_close`, but it is
excluded from baselines and cannot advance warmup. Readiness reports the exact
next eligible observation time rather than encouraging rapid duplicate calls.

Warmup is feature- and horizon-aware across volume, turnover, volatility,
1h/4h/24h returns, and BTC/ETH-relative groups. Each group exposes sample count,
required sample count, observed time coverage, and required time coverage; an
asset is not globally warm until all configured required groups are warm.
Returns, volatility, turnover/volume z-scores, and BTC/ETH relative returns are
derived in percent points without using the current observation in its own
baseline. Current rows older than six hours or materially future-dated fail
closed. Cold/warming status and exact observation ids remain visible, and only
fields explicitly identified as proxy inputs may be replaced by a temporal
calculation.

A fixture or mocked smoke generation can prove mechanics but is permanently
ineligible for Decision campaign counting or real dashboard authority. The fixed
authoritative pointer changes only after a real, fresh, complete generation has
canonical v2 provenance, distinct exact lineage fingerprints, matching
candidate/Core/card/preview/outcome counts, a current operator-state binding,
and a fresh full strict doctor with zero blockers. A real clean zero-idea
generation may become honest current authority when those same gates pass; it
must not relabel stale fixture data as live. Until a trusted real run succeeds,
the existing fixture pointer remains explicit fixture evidence.

When authorization is absent, readiness and the generation command return an
explicit safe-blocked result, attempt no provider call, write only the
credential-free pilot audit, and leave the authoritative pointer unchanged.
When cadence is still waiting, the generation also blocks before the adapter.
Authorization is never enabled by the application or inferred from a cache.
Each operator invocation rechecks both existing authorization and cadence; only
an eligible invocation may attempt one bounded live request, and an invocation
never retries by launching a second campaign cycle. The safe next command comes
from readiness or the campaign report.
The CLI also replaces `event_market_no_send_latest_attempt.json` for every live
attempt. Make may run the doctor and publisher only when that receipt matches
the exact complete manifest, so a newly blocked attempt cannot accidentally
reuse an older complete namespace. Provider health is namespace-local,
fingerprinted for live authority, and stores only safe error classes.

Each completed cycle writes one final post-doctor pilot audit. Pilot audit
contract v1 is distinct from market provenance contract v2. The audit records
the exact namespace/run/revision, canonical pointer binding, request/source/
history fingerprints, full-universe cold/warming/warm counts and observations
per asset, direct/proxy feature bases, spread coverage, routes/scores/outcomes,
doctor and dashboard status, and zero-side-effect counters. It separately names
`provider_adapter_invoked`, `network_call_attempted`, and
`provider_request_succeeded`; mock adapter invocation is never presented as a
network call. Campaign-level evidence is tracked in
`research/RADAR_LIVE_OBSERVATION_CAMPAIGN_REPORT.md` / `.json` without claiming
a warm baseline before the required prior observations and time coverage exist.
`make radar-market-campaign-report` rebuilds that canonical pair from local
artifacts only, makes no provider call, and reports authoritative and
non-authoritative generations, failed/blocked attempts, route counts, feature
maturity, next eligible time, data-quality limits, and pending/mature outcomes.
Its Decision campaign totals remain explicitly separate from Event Alpha
catalyst burn-in.

The authoritative pointer uses a stable canonical operator-state digest. A
strict-doctor rerun against an unchanged revision may refresh only the top-level
`updated_at` and nested `doctor.verified_at` clocks without changing pointer
identity. Every substantive doctor value and the complete artifact manifest
remain fingerprinted; any other operator-state or artifact drift invalidates
the exact binding and blocks current authority.

## Outcomes and Learning

Every current canonical Decision idea, including diagnostic controls, receives
a pending outcome placeholder. The shared mutable campaign ledger is
`radar_market_history_cache/event_decision_radar_campaign_outcomes.jsonl`; it is
rebuilt deterministically from immutable generation candidates/Core rows and
locally retained observed prices, while origin namespaces and their pointer
history remain unchanged. Rows stay pending until the configured horizon is due
and sufficient observed prices exist, then mature with exact price lineage; a
refresh makes no provider call.

Each outcome's origins, route, actionability cohort,
evidence-confidence cohort, risk cohort, catalyst status, timing, and phase are
copied from the canonical projection. Candidate/outcome count mismatch or cohort
drift is a doctor blocker for the trusted publication profile.

Outcomes and optional human feedback are measurement evidence only. They do not
automatically alter thresholds, routes, priors, or notification policy. Any
change to decision policy remains an explicit, human-approved, versioned
decision.

## Safety Invariants

- research_only: `True`
- human_decision_required: `True`
- no_live_trading: `True`
- no_event_alpha_paper_trading: `True`
- no_execution_order_logic: `True`
- no_normal_rsi_signal_writes: `True`
- no_event_alpha_triggered_fade: `True`
- triggered_fade_source_boundary: `event_fade.py + proxy_fade only`
- no_real_telegram_sends_by_default: `True`
- no_live_provider_calls_without_existing_explicit_authorization: `True`
- no_credentials_in_artifacts_or_output: `True`
- preserve_historical_artifacts_without_silent_reinterpretation: `True`
