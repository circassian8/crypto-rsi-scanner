# Crypto Decision Radar North Star

Research-only product contract for trader-facing decision support. Crypto
Decision Radar organizes evidence for a human operator; it never places an
order, creates a live or Event Alpha paper trade, writes a normal RSI signal,
creates `TRIGGERED_FADE`, or sends a real notification by default.

- generated_at: `2026-07-12T18:45:07+00:00`
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
- observation ids, source/provider lineage, evaluation timestamp, and explicit
  no-send/no-trade/no-paper/no-RSI-write/no-trigger safety attestations.

Candidate/Core/card/preview/outcome/dashboard disagreement is a doctor blocker.
Numeric comparisons use one documented deterministic rounding tolerance; no
consumer may silently perform a materially new evaluation.

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
verifies spread/tradability. The system never invents spread.

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

Readiness is no-write and no-network. A live CoinGecko request requires the
existing explicit `RSI_EVENT_DISCOVERY_UNIVERSE_LIVE=1` authorization and no
fixture mode. The generation uses a bounded top-liquid universe, records the
request/cache lineage and observation time, computes market anomalies, creates
canonical Decision ideas, then builds cards, preview, outcomes, operator state,
and the dashboard read model. The defaults remain research-only and no-send,
with zero trades, paper trades, normal RSI writes, or `TRIGGERED_FADE` creation.

A fixture or mocked smoke generation can prove mechanics but is permanently
ineligible to become the real dashboard authority. The fixed authoritative
pointer changes only after a real, fresh, complete generation has valid exact
fingerprints, matching counts, a current operator-state binding, and a fresh
full strict doctor with zero blockers. A real clean zero-idea generation may
become honest current authority when those same gates pass; it must not relabel
stale fixture data as live. Until a trusted real run succeeds, the existing
fixture pointer remains explicit fixture evidence.

## Outcomes and Learning

Every current canonical Decision idea, including diagnostic controls, receives
a pending outcome placeholder. Its origins, route, actionability cohort,
evidence-confidence cohort, risk cohort, catalyst status, timing, and phase are
copied from the canonical projection. Cohort drift is a doctor blocker.

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
