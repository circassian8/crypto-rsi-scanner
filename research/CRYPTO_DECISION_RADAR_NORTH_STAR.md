# Crypto Decision Radar North Star

Research-only product contract for trader-facing decision support. Crypto
Decision Radar organizes evidence for a human operator; it never places an
order, creates a live or Event Alpha paper trade, writes a normal RSI signal,
creates `TRIGGERED_FADE`, or sends a real notification by default.

- generated_at: `2026-07-20T08:47:47+00:00`
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

Catalyst freshness is source-clock evidence, not a score hint. A search result
whose `published_at` or `fetched_at` is more than five minutes after the
evaluation clock is rejected before attachment and cannot earn a freshness
bonus, even when an operator lowers the ordinary score threshold. This does not
reject a legitimately future scheduled `event_time`: publication/fetch clocks
describe when evidence existed, while event time describes when the catalyst is
expected to occur. Rejected source-clock evidence remains visible in bounded
search telemetry and never becomes causal confirmation.

Catalyst source authority comes only from the canonical source registry using
an exact provider identity or an exact/child trusted hostname. Article wording,
caller-provided source hints, generic `official` language, and look-alike domain
suffixes cannot establish official exchange, official project, structured, or
market-data authority. Shared Medium and GitHub hosting and the generic
`project_blog_rss` transport remain capped context unless a separate canonical
ownership attestation exists. Evidence-quality scoring reuses this registry
classification, and a source pack may validate an impact path only when the
class appears in that pack's declared validator set. Historical bytes are not
rewritten; current re-evaluation fails closed and records
`source_authority_unverified`.

LLM catalyst frames are proposals until deterministic validation binds them to
exactly one matching raw source. Each accepted quote must be a normalized,
informative contiguous span inside one eligible field—title, body, or
quality-gated enriched text—and carries the raw/provider/URL/publication/fetch
identity, source confidence, original content hash, canonical evidence-surface
and enrichment-provenance hashes, source field, normalized offsets, and exact
analysis and validation digests. Frames use closed keys, enums, primitive
types, finite bounded confidence, and a recomputed canonical id; subjects and
entities must occur in the bound source, while short ticker symbols additionally
require a token boundary plus crypto context or an explicit dollar ticker.
Event summaries, neighbouring raws, cross-field concatenation, and fuzzy term
overlap cannot validate a quote. Application and rehydration fail closed on any
binding drift, while missing, duplicate, or invalid analysis identity remains a
fail-soft unresolved row rather than crashing the cycle. Historical unbound
rows remain immutable audit bytes but are not current catalyst evidence, and
the provider output schema remains unchanged.

Catalyst confirmation also requires a closed temporal-semantic attribution
between one exact source and one exact market anomaly. The source-public clock
is `published_at`, falling back to `fetched_at`; a claimed `event_time` remains
separate and can never backdate when evidence became available. Sources more
than five minutes after an anomaly are retrospective context, not causal
confirmation. Background, historical, reaction, and side-note frames remain
context-only; negated, corrective, denied, or ruled-out evidence remains
disproof. A future scheduled event can be `scheduled_anticipation` only when
its source was already public before or contemporaneous with the anomaly.
Missing or timezone-naive clocks fail closed as unknown.

The immutable `event_alpha.catalyst_attribution` v1 value binds anomaly/source
identities, a digest over the exact anomaly asset/snapshot/state evidence,
public and event clocks, publication lag, one of the eight canonical semantic
roles, candidate role, impact strength, canonical source capabilities, evidence
use, causal eligibility, reason codes, safety flags, and a canonical digest. URL userinfo and
credential-like paths are rejected, while all query and fragment data is
removed before propagation. Catalyst search, discovery, alert evidence,
integrated candidate, CoreOpportunity, canonical Decision projection, and
pending outcome copy the same validated value. Once a current row supplies an
attribution, malformed, foreign, mixed-validity, or exclusively
retrospective/contextual evidence cannot
fall back to the old official-hostname or accepted-count shortcut. Historical
rows without the new value remain readable under the existing compatibility
heuristic and are never rewritten. This timing discipline follows the event-
window and information-availability principles in [MacKinlay's event-study
review (1997)](https://econpapers.repec.org/article/aeajeclit/v_3a35_3ay_3a1997_3ai_3a1_3ap_3a13-39.htm)
and [Miller's event-study design guide
(2023)](https://www.aeaweb.org/articles?id=10.1257/jep.37.2.203); it does not
assert that temporal precedence alone proves causality.

Catalyst corroboration is content-aware rather than a raw row or hostname
count. The closed `event_alpha.source_independence` v1 contract normalizes each
title/body surface, clusters exact and near-duplicate reports with a
representative-only three-word-shingle Jaccard rule, and counts an additional
independent unit only when an assessable content cluster introduces a new
canonical origin. Raw documents, observed domains, content clusters,
independent evidence units, and additional corroborations remain distinct.
Missing, incomplete, over-bound, or invalid assessments are explicitly
`unassessed` or `rejected` and provide zero diversity promotion; legacy rows
remain readable without fabricated values. This contract does not establish
publisher ownership independence, authority, truth, impact, or causality. It
only replaces legacy raw-row/hostname diversity inputs one for one and may
remove duplicate-derived support; any new positive promotion or calibration
requires a separate outcome-backed decision. The method is informed by
[Rodier and Carter's near-duplicate news study
(2020)](https://aclanthology.org/2020.lrec-1.156/), while the fixed `0.80`
threshold and evidence semantics are project policy rather than claims from
the paper.

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
- validated catalyst-attribution values tying every causal-confidence claim to
  an exact source and anomaly;
- the validated source-independence contract, explicit assessed/unassessed/
  rejected status, bounded errors, and exact independent-unit/corroboration/
  content-cluster counts;
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

Live/no-send market generations accept calendar input only from the explicit
`RSI_DECISION_RADAR_CALENDAR_SNAPSHOT_PATH` boundary. Readiness inspects that
bounded local JSON snapshot without a provider call or write and reports
`not_configured`, `healthy_empty`, `healthy_nonempty`, `stale`, `unavailable`,
or `fixture_rejected_live`. An accepted non-fixture snapshot is copied and
fingerprinted inside the exact generation after projecting it to a closed,
allowlisted, secret-safe source-row shape; scheduled/unlock adaptation and
canonical unified-calendar normalization then feed the integrated cycle. Live
operational input requires the versioned container, explicit snapshot time, and explicit
current-source/acquisition provenance; a renamed fixture, bare list, or mtime-
only freshness cannot qualify. Row-level source/provider provenance is checked
as well, and supplied `research_only`, `no_send`, or `no_send_rehearsal` fields
must be exactly true. Unsupported provider fields, secret-like keys, and
credential-bearing URLs fail closed before any copy. Fixture, test, mock, and
replay markers are rejected from container/nested provenance and event-row
`provider`, `source`, and `source_class`.
A missing source is shown as `not_configured`; it is never silently treated
as a quiet calendar and never replaced by fixture/test/mock/replay data in a live
generation.

The official U.S. macro producer begins with Federal Reserve FOMC dates, BLS
CPI/employment releases, and BEA PCE/GDP releases. Live acquisition is off by
default and requires pre-existing explicit authorization; BLS additionally
requires an honest contact. It makes at most one request per configured official
source and does not follow redirects. Every source independently reports
`observed`, `no_results`, `unavailable`, `missing_configuration`, `parse_error`,
or `rate_limited`. Accepted bytes remain immutable and fingerprinted even when
another source fails. A snapshot is `complete`, `partial`, or `unavailable`;
partial coverage names its exact observed and missing sources, and zero rows
from an unavailable source never means that source has no events. Local import
is no-network, accepts an explicit subset of genuine operator-downloaded source
files, and requires their real, explicit acquisition time; direct checked-in
fixture/test/mock/replay paths are rejected before writes. Fed tentative meeting
windows remain windows with no invented decision time, while BLS TZIDs and BEA
offsets survive normalization. Every attempt has a unique directory. A complete
or partial successful pointer is usable only after its closed fields, receipt,
snapshot, coverage digest, and each accepted raw-source digest are re-attested;
Daily Operations consumes that verified latest-success path without guessing a
file. An unavailable acquisition never replaces the prior successful pointer.
Unlinked macro events remain context/risk only and cannot create directional
bias or a directional idea.

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

Operator Experience V1 organizes the dashboard around eight primary pages:
Today, Market Radar, Ideas, Calendar, System Health, Outcomes & Learning, and
Run History, plus the authority-independent Research Lab. Today prioritizes
current attention and constraints; Market
Radar explains the bounded provider-to-decision funnel; Ideas and Idea Detail
render the canonical Decision v2 projection; Calendar preserves certainty and
coverage; System Health separates failures from disabled, unselected,
unconfigured, and warming states; Outcomes separates exact-current placeholders
from historical learning; and Run History shows bounded immutable attempts
without granting them current authority. Research Lab presents closed historical
replay, walk-forward, shadow-policy, and separately fingerprinted live no-send
evidence without granting any result production authority. Historical
compatibility routes remain available but are not primary navigation.

The hierarchy is current-first and route-aware. A sole risk watch is named as a
risk watch rather than a generic actionable idea; active scheduled windows lead
future and past events; observed anomaly moves lead unavailable secondary
strength fields; raw provider IDs, full run identities, expired rows, diagnostic
controls, historical samples, and technical contracts remain available behind
clearly labeled disclosures. Comparison controls appear only when comparison is
possible.

Presentation is render-only. One formatting layer translates timestamps into
operator-local relative and calendar labels while retaining exact UTC in
accessible details, translates internal enums and reason codes, formats units
consistently, and uses `Unavailable` instead of inventing missing values.
Uncertain calendar dates remain windows or date-only labels. Scores are shown as
scores and bands: actionability is not win probability, evidence confidence is
not expected return, and risk is never reversed into a quality score.

Every exact-run relative timestamp uses the generation authority check as its
single read clock. Missing receipt booleans remain tri-state and display as
`Not recorded`; they are never collapsed into `No`. One operator-label
projection names all canonical routes consistently while preserving their
stored route tokens and routing behavior.

Provider authorization at the last cycle is historical evidence, not current
permission. The dashboard labels it separately from the expiring persisted
`current_authorization_status`, `current_authorization_checked_at`, and
`current_provider_call_eligibility` receipt and never inspects environment
variables on GET/HEAD. Calendar coverage likewise lists unavailable and
missing-configuration sources rather than turning absent rows into a healthy
empty claim.

The interface is server-rendered, with its backend loopback-only, responsive
from wide desktop to narrow mobile, keyboard navigable, and usable without
JavaScript. Semantic
states use text and structure as well as color. Tables become contained mobile
comparison cards where appropriate; long identifiers and technical values stay
inside their components. Deep paths, hashes, reason codes, request-ledger data,
and provenance are collapsed by default. The offline
`make radar-dashboard-ux-smoke` target exercises all primary pages, including
Research Lab, and the real browser review covers desktop, laptop, tablet, and
mobile layouts.

Optional phone access preserves that loopback boundary. It may expose the
backend through private Tailscale Serve HTTPS to identities allowed by the
owner's tailnet policy, or through an explicitly confirmed unauthenticated
Cloudflare Quick Tunnel for temporary public access. Both status/readiness paths
are observational and both enable/disable paths require confirmation. The
private helper fails closed on Tailscale/DNS/Funnel/Serve conflicts. The public
helper requires the authoritative local HTTP 200 dashboard identity, a fixed
HTTP/2 non-debug owned process, edge registration, an end-to-end public HTTP 200
identity probe, and one canonical randomized `trycloudflare.com` URL; it creates
no account, named tunnel, owner-controlled DNS record, credential, startup
service, or permanent address.
Neither path binds a wildcard/LAN address, opens a router port, or mutates
dashboard/provider artifacts. Anyone with the public URL can read the dashboard
until the exact owned process stops. Tailscale Serve is the recommended
persistent mode. The Quick Tunnel is off by default, has an optional bounded
trusted-receipt lifetime, and suppresses its URL when expired or when local
authority is unavailable. Receipt expiry does not itself stop `cloudflared`;
status warns that it may remain public, and the confirmed guard terminates only
the exact owned process.

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

A clean zero-idea generation remains informative. The dashboard renders the
exact fingerprint-bound market observations and anomaly artifacts that were
evaluated, reports each source pack as healthy-nonempty, healthy-empty,
unconfigured, or degraded/unavailable, and distinguishes normalization
rejections from a valid empty source. Namespace-local Decision outcomes stay
separate from the shared cumulative campaign outcome ledger, which is labeled
historical and non-authoritative for the current generation.

Market Radar makes the exact layer accounting visible: bounded provider rows,
selected top-liquid universe, fingerprint-bound observations, anomaly evidence,
integrated candidates, and consolidated Core/operator ideas. A reduction after
the exact observation stage is scanner qualification or canonical consolidation
rather than hidden dashboard loss when the stage receipts reconcile. A mixed
integrated generation without a market-only receipt presents independent layer
counts and never implies that catalyst-, technical-, derivatives-, on-chain-,
fundamental-, or macro-led ideas descended from zero market anomalies. Missing
stage receipts are not inferred.

Today and System Health share one canonical seven-layer coverage projection for
market, catalyst, calendar, derivatives, RSI, outcomes, and the exact provider
request ledger. Each layer is healthy-nonempty, healthy-empty, not configured,
not applicable, unavailable, degraded, stale, or rejected. Green requires every
expected layer to be healthy or explicitly not applicable. An empty operator
queue therefore cannot hide a provider, normalization, calendar, derivatives,
RSI, outcome, request-ledger, spread, or baseline limitation.

One descriptor-anchored namespace is held through the entire dashboard load;
directory replacement fails closed, and operator semantic counts must reconcile
with exact market snapshot/anomaly rows. Raw anomaly scanner outputs appear as a
separate scan-evidence table, never as synthetic Decision candidates or routes.
When the server was started from the authoritative pointer, every GET/HEAD
revalidates that the pointer still names the same namespace, run, revision, and
operator-state digest; a changed or missing pointer returns an unavailable
response rather than serving the formerly current generation.
Freshness-only loss is a distinct degraded state: while the same exact pointer
binding still matches, the server returns HTTP 503 with a quarantined diagnostic
shell so System Health, historical Outcomes, and explicitly historical Run
History remain inspectable. All current rows and fields stay suppressed, and
private phone readiness still fails closed. Identity, pointer, fingerprint,
schema, or integrity loss retains the minimal unavailable response rather than
rendering artifact content.
If any authority check fails, all current candidates, observations, anomalies,
calendar rows, exact outcomes, request-ledger fields, source coverage, market
generation fields, and current counts are centrally quarantined on every page.
Historical campaign evidence remains separately labeled. A current artifact
that fails its fingerprint is never reopened or demoted into cumulative history.

External dashboard links accept only absolute HTTP(S) URLs with a hostname and
no embedded username or password. Field-level return-unit metadata overrides a
row-wide unit during rendering, and turnover ratios are converted explicitly to
percent-points for charts; presentation never performs numeric guesswork.

Artifact presence alone is not evidence of healthy-empty acquisition. A
provider/layer may receive that status only from its exact current producer
completion contract with matching lineage and counts; operator publication then
fingerprints the exact artifacts. Otherwise an empty artifact is shown as
unconfigured or unavailable. This prevents an empty unlock or derivatives file
from impersonating successful provider coverage.
A same-cycle zero-anomaly result is healthy-empty only when its completion
receipt reconciles the exact run, namespace device/inode, paths, content hashes,
row semantics/lineage, and snapshot/anomaly/search-queue counts. All four scan
outputs are preflighted and atomically replaced through one held no-follow
namespace bundle. Empty anomaly artifacts without that receipt remain unavailable.

## Empirical Validation and Research Lab

Decision Radar empirical validation is an authority-independent research layer,
not another decision model or production route system. It reuses the canonical
Decision Model v2 projection at historical point-in-time observation clocks,
measures episode-aware forward outcomes, compares predeclared shadow policies,
and publishes recommendations only. Research replay cannot change thresholds,
routes, provider authorization, notifications, execution, or dashboard
authority, and every result carries `research_only=true`, `auto_apply=false`,
and an explicit human-approval boundary.

The frozen protocol is `decision_radar_empirical_validation_v1`, frozen at
`2026-07-16T05:30:00Z` before final-test evaluation with SHA-256
`efee20ccaa3dda03c8e1172633d92d6a9bf8cb3ae12c926471f2151941d5f158`.
Daily observations occur at completed Binance candle close. Point-in-time
universe membership uses the trailing 30-day quote-volume rank calculated at
that close inside the locally retained historical candidate pool. The pool has
an explicit residual delisting-survivorship limitation. Rolling features use
only current and earlier completed bars; the frozen volume z-score uses a
90-day lookback and requires 20 prior observations. Future ranks, future bars,
current metadata fallbacks, retrospective catalyst knowledge, and outcome data
are forbidden inputs. Available daily RSI is observational context only.

Chronological idea and outcome boundaries are fixed:

| Partition | Idea start | Idea end | Outcome end | Policy selection |
|---|---|---|---|---|
| development | `2021-06-12T00:00:00Z` | `2023-01-01T00:00:00Z` | `2023-01-15T00:00:00Z` | allowed |
| validation | `2023-01-15T00:00:00Z` | `2025-01-01T00:00:00Z` | `2025-01-15T00:00:00Z` | allowed |
| final test | `2025-01-15T00:00:00Z` | `2026-06-01T00:00:00Z` | `2026-06-18T00:00:00Z` | forbidden |

Fourteen-day outcome-only embargoes separate the partitions. An outcome is
readable only when its due time is strictly before the applicable outcome
boundary. Walk-forward folds purge primary outcomes whose due time reaches the
fold boundary and omit a final test window shorter than the frozen 180-day
length. Development and validation may nominate a recommendation; final test
may only confirm or reject the exact pre-sealed candidate set and cannot search
for a replacement. An empty sealed set is reported as
`no_candidate_recommendations`, not as final-test validation.

The primary outcome horizon is three days; one-, seven-, and fourteen-day
results are sensitivity evidence. Outcome bars begin after the idea bar.
Return, BTC- and ETH-relative return, MFE, signed MAE, time to MFE/MAE,
invalidation, continuation, reversal, expiry, and post-expiry behavior remain
explicit. Fixed-start 24-hour episodes freeze the first eligible representative
and use an inclusive end, so an observation exactly 24 hours later remains a
dependent repeat. Repeats preserve route, score, phase, catalyst, spread, and
derivatives progression but never inflate the independent sample count or
replace the representative based on outcome maturity.

Matched non-signal controls are chosen by an outcome-blind deterministic hash
within date, regime, and liquidity buckets. Raw-mover, volume, RSI,
relative-strength, BTC/ETH, and late-fade benchmarks are descriptive and do not
support causal claims. Historical bid-ask spread, order-book execution quality,
and intraday high/low ordering are unavailable. Fees, assumed spread, slippage,
adverse selection, review delay, capacity, stop, holding-period, and idea-budget
results are sensitivity scenarios unless an artifact explicitly marks them as
observed. Break-even cost does not convert an assumed scenario into execution
evidence.

The rolling walk-forward contract uses 730-day training and 180-day test
windows across development and validation, requires three outcome-evaluable
folds, and never accesses final test for selection. The shadow simulator
compares the frozen production policy with nine material alternatives under the
predeclared `noninferior_return_failure_selected_day_burden_v1` rule. Candidate
eligibility requires the frozen sample minimum, a material policy change,
non-inferior mean directional return and quick-failure rate, and bounded ideas
per exact selected observation day, including zero-idea days. A `candidate` is
only eligible for sealing; it is not an applied policy.

Historical replay, fixture, live no-send, and artifact replay are distinct
evidence lanes. Fixture results prove mechanics only. Live no-send evidence is
a separately fingerprinted observational lane, never pooled into historical
sample sizes or used to turn an insufficient historical cohort into a policy
candidate. Replay outcomes stay in immutable research-run artifacts and never
enter or rewrite the mutable live campaign outcome ledger.

New live/no-send empirical projections use schema v4 and retain the campaign's
validated causal temporal-surprise coverage, explicit human-review queue and
timing state, and closed point-in-time control-context readiness. They expose
per-feature readiness, exact source/digest lineage, receipt-backed review
counts, whether any completed review-latency sample exists, and exact
prospective coverage for universe, liquidity, market-regime, and sealed
partition fields. Source and campaign counts must reconcile before projection.
Control coverage is outcome-blind and cannot backfill historical rows, select a
matched control, infer absent regime/partition values, or alter routes, scores,
thresholds, publication authority, or Protocol-v2 eligibility. Projections
preserve `statistical_independence_claimed=false`,
`protocol_v2_evidence_eligible=false`, and every zero-side-effect boundary.
Older source context is labeled compatibility-unavailable rather than rendered
as zero. Schema v1, v2, and v3 remain readable. The current sealed seven-file
Protocol-v1 bundle and its separately attested hardening supplement remain
byte-immutable; a future v4-bearing empirical publication must be separately
versioned and reviewed rather than silently refreshing those historical bytes.

Publication is one closed seven-file bundle, in this exact order:

1. `DECISION_RADAR_EMPIRICAL_VALIDATION_REPORT.md`
2. `DECISION_RADAR_EMPIRICAL_VALIDATION_REPORT.json`
3. `DECISION_RADAR_WALK_FORWARD_REPORT.md`
4. `DECISION_RADAR_WALK_FORWARD_REPORT.json`
5. `DECISION_RADAR_POLICY_SIMULATION_REPORT.md`
6. `DECISION_RADAR_POLICY_SIMULATION_REPORT.json`
7. `DECISION_RADAR_RESEARCH_LIMITATIONS.md`

Research Lab acquires all seven bounded files through one descriptor-anchored
read, verifies their whole-bundle identity, source-run bindings, protocol,
recommendation seal, final confirmation, live projection, report digests, and
Markdown/JSON agreement, and only then renders semantic projections. A missing,
unsafe, oversized, tampered, spliced, or digest-drifting member suppresses every
semantic conclusion. The page may show only the bounded file inventory and
failure state; invalid evidence is never rendered as zero evidence.

Research remains inspectable when production authority is stale because it is
explicitly historical and non-authoritative. That visibility never restores a
current idea, relaxes dashboard pointer checks, or implies actionability. The
page leads with bundle status, frozen protocol and run identities, final
verdict, partition/sample counts, route and origin coverage, monotonicity,
signed MFE/MAE, controls, assumed costs, walk-forward purges, operator burden,
shadow-policy status, live/replay separation, limitations, and the unchanged
production boundary.

The current canonical evidence is bound to selection run
`8212b2ddb626805f4312d8986cc1d9f6b3229a169aa49ca75b9b5bbfc1660489`, final-test run `3009e23dd9a9f11418cf97ee07f6e532c451c21196e69bd1ae0cd6ae96c47e72`, report
bundle `267a1c6d30488fcd7088bf20ce6f653df6bf79f82c5e7d401e27fd4b24debbcf`, and recommendation seal
`3f0ea69c2cb3c455bf9d8e13f44f6db6cee6308192c61a090b9f39e0a5442639`. All nine material shadow alternatives are
`not_supported`; the sealed candidate set is empty and final confirmation is
`no_candidate_recommendations`. Production thresholds, routes, notifications,
execution, provider authorization, and dashboard authority remain unchanged.

Historical samples exist only for market-led `dashboard_watch`, `risk_watch`,
and `diagnostic` cohorts. `high_confidence_watch`, `actionable_watch`,
`rapid_market_anomaly`, `fade_exhaustion_review`, and `calendar_risk`, plus
`catalyst_led`, `technical_led`, `derivatives_led`, `onchain_led`,
`fundamental_led`, and `macro_led` primary origins, have no empirical episodes.
Zero samples mean no evidence, not strength, weakness, safety, or validation.
The most important missing evidence is observed spread/order-book quality,
intraday decision-to-review timing, and direct point-in-time catalyst, calendar,
derivatives, and on-chain data across more independent episodes.

The reproducible protocol-check, smoke, medium, full, sealed final-test, report,
byte-check, and optional review-feedback workflow is documented in
[Decision Radar Research Runbook](DECISION_RADAR_RESEARCH_RUNBOOK.md).

## Guarded Real/No-Send Market Generation

The supported operator flow is:

1. `make radar-daily-ops-readiness`
2. `make radar-daily-ops-cycle`
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
Daily Operations v1.1 exclusively owns pointer publication, final receipts,
owned-dashboard restart, exact HTTP probing, terminal state, and report refresh.
`make radar-market-no-send` is a compatibility alias for that coordinator; the
lower-level `market_no_send publish` command is disabled.

When `RSI_DECISION_RADAR_CALENDAR_SNAPSHOT_PATH` is already configured, the
same generation validates and copies that local no-network calendar snapshot,
preserves only the closed secret-safe allowlisted source-row projection, and
separately adapts it to scheduled-catalyst input. Publication deterministically recomputes
the scheduled, unlock, and unified rows from the accepted source copy and
compares their exact canonical forms from the same read-once hashed buffers, so
rewritten digests, duplicate keys, in-place mutation, or split reads cannot
conceal a semantic change. Scheduled/unlock JSONL and report outputs are one
descriptor-anchored no-follow bundle. Snapshot absence or rejection does not block the
market observation, but its coverage status and normalization counters remain
explicit in readiness, manifests, operator state, and the dashboard.

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
closed. Cold/warming status and exact observation ids remain visible. The
canonical market-state snapshot and its nested anomaly copy preserve one
bounded `market_feature_evidence` map plus the matching current history
observation ID, so a computed feature cannot become detached from its exact
baseline fingerprint between collection and classification. Temporal evidence
entries are closed, JSON-safe, deep-copied, and schema-validated. Only fields
explicitly identified as proxy inputs may be replaced by a temporal calculation.
When causal history supplies the canonical BTC/ETH-relative value, its field and
`relative_strength` group basis are `benchmark_derived_temporal_history`; an
observed relative value cannot remain labeled unavailable. An independently
supplied canonical value and stronger basis remain authoritative, with the
temporal calculation retained only under its explicit diagnostic field.

The optional `event_alpha.shadow_temporal_surprise` v6 comparison preserves its
v1 activity contract and keeps historical v1-v5 values readable. Positive finite
provider-observed `volume_24h` and provider-observed or exact provider-ratio
`turnover_24h` use natural log, baseline median, normal-consistent MAD
(`MAD * 1.482602218505602`), and a descriptive add-one upper-tail rank. V2 adds
separate direct, BTC-relative, and ETH-relative 1h/4h/24h signed-return families
in percentage points. Returns are rederived only from provider-observed prices;
each endpoint uses an at-or-before causal horizon anchor within the larger of
300 seconds or 25% of the horizon. A canonical benchmark endpoint must be at or
before the asset clock and within 300 seconds. The identity transform preserves
downside sign, while median/MAD robust z-scores and add-one lower, upper, and
two-sided ranks remain descriptive rather than p-values. Overlapping samples
are explicitly not independent. Proxy basis, identity drift, future/misaligned
clocks, insufficient history, and degenerate MAD fail closed without a fallback.
V3 leaves those calculations unchanged and adds exact rounded-value distinct
counts, maximum/current tie counts, distinct ratios, and nominal one- and
two-sided finite-sample rank floors. These fields expose quantized or repeated
provider baselines but apply no minimum-distinct threshold and change no status,
route, score, or policy.
V4 separately binds feature-specific value-only retained input tuples and
distinguishes source-tuple repetition from distinct tuples collapsing to the
same rounded derived value. V5 adds an observation-identity timing trace for
each return sample: exact endpoint/anchor identity, cross-sample reuse, realized
horizon and anchor-selection error, benchmark endpoint alignment, and exact
maximum references. V6 closes every asset and benchmark return interval as a
half-open anchor-to-endpoint clock range, then measures exact interval reuse,
adjacent overlap seconds, total interval time, unique union clock coverage,
overlap excess, coverage ratio, and exact maximum references. This keeps
repeated numeric inputs, exact interval reuse, and overlapping-but-distinct
rolling windows separate. Neither trace attributes provider fault, estimates
independent sample size, changes sample weights, sets a threshold, or changes
status, route, score, exclusion, publication, or policy.

The value is computed from the exact fingerprinted generation-history snapshot
only after anomaly classification, bucketing, priority, sorting, and truncation,
then attached as top-level snapshot/anomaly diagnostic metadata. The exact
history artifact basename and verified SHA-256 remain inside the closed value,
while bundle enrichment stays bound to the original scan namespace device/inode
and unchanged artifact hashes. It never enters provider source rows, canonical
history, nested market snapshots, integrated candidates, the Decision
projection, routes, priorities, scores, thresholds, cards, or sends. Its
explicit policy remains routing/priority/Decision-score ineligible,
`auto_apply=false`, and research-only until matured episode-level outcome and
matched-control evidence supports a separate sealed out-of-sample decision. The
detailed method and limitations are recorded in
`research/ROBUST_TEMPORAL_SURPRISE_SHADOW.md`.

The canonical campaign report now replays that same closed v6 evaluator over
its one-read exact retained-history snapshot. Only cadence-counted rows enter;
each is evaluated against strictly earlier observations for the same canonical
asset and at-or-before canonical BTC/ETH rows. The report closes excluded,
rejected, and evaluated counts, exposes feature/status/sample coverage and
per-asset summaries, and publishes both a source-bound digest and a causal-value
digest whose older projection values remain stable when only later rows are
appended. Audit status `ready` means every modeled feature has some ready
evidence, not that every projection is ready. The replay rewrites no history,
makes no provider call or write, claims no statistical independence, and is
not eligible for routes, scores, thresholds, publication authority, or
Protocol-v2 evidence.
Campaign-audit v7 preserves historical audit v1-v6 readability and aggregates
both timing and interval-overlap traces per canonical asset and return feature.
It reports exact observation-identity reuse, maximum runs, realized horizon
error, benchmark alignment, exact interval reuse, adjacent overlap, unique
clock coverage, and exact extremes. The campaign report and dashboard show
these separately from value-tuple repetition and retain explicit no-policy,
no-provider-causation, no-effective-sample-size, no-weight-adjustment, and
no-independence semantics. In the current real campaign, all eligible 1-hour
windows have full unique clock coverage, while overlapping 4-hour and 24-hour
rolling windows reach minimum unique-coverage ratios of about 0.456 and 0.126;
no exact asset or benchmark interval reuse was observed. Distinct intervals
therefore must not be mistaken for statistically independent samples.

Repeated campaign observations of one persistent market move are measured with
the closed `event_alpha.shadow_anomaly_episodes` v1 contract. It partitions
each exact canonical asset with a fixed-start, half-open 24-hour primary window
and parallel 12/24/48-hour sensitivity views. The first observation is selected
solely from exact identity and time, independently of outcome availability,
maturity, route, score, or return; a repeat never extends the window and a later
mature observation never replaces the representative. Membership binds exact namespace, run,
candidate, canonical outcome, anomaly, asset, and UTC observation identity.
Raw outcome multiplicity is inspected before the campaign compatibility
deduplication view, so missing, invalid, duplicate, conflicting, and orphan
outcome rows stay explicit. A row claimed by multiple candidates is one
cross-candidate collision component, not one duplicate group per claimant.
Each candidate artifact is captured once and
verified against its manifest or legacy operator binding; one exact mutable
outcome-ledger byte snapshot is reused by headline and episode calculations.
The closed input audit distinguishes `missing`, `observed_empty`, `observed`,
and `unavailable` ledgers and independently reports candidate, outcome, and
overall input readiness. Observation and episode counts remain side by side,
and neither is described as statistically or cross-asset independent. Complete
references are retained within fixed 256-row member and exclusion bounds; a
bound overflow fails closed without a contract. This
measurement is research-only and cannot change routing, priority, Decision
scores, calibration, thresholds, provider activity, publication, or authority;
`auto_apply=false`. The detailed contract and research basis are in
`research/ANOMALY_EPISODE_SHADOW.md`.

The closed `event_alpha.decision_v2_episode_outcome_scorecard` v1 evaluates
only the frozen, chronologically first representative of each primary 24-hour
episode. Outcome availability or maturity never changes that representative,
and a repeat cannot replace it. Only the declared canonical primary horizon
determines `matured`, `not_due`, `due_missing_price`, or
`contract_excluded`; maturity at a secondary horizon cannot promote the
episode. Directional alignment comes from the canonical Decision-v2
`directional_bias`, never from a legacy Event Alpha `opportunity_type`.
Candidate, CoreOpportunity, and campaign-ledger rows are joined by exact
namespace, run, candidate/outcome identity, row digest, equal canonical
Decision projection, and `Core.integrated_candidate_id == candidate_id`.
Every source binding retains its role, namespace, run, basename, SHA-256, byte
size, row count, and binding authority. Score-cohort persistence is explicit as
`canonical_exact`, `legacy_unversioned_exact`,
`legacy_null_derived_from_canonical_scores`, or `invalid`. The narrow
historical-null compatibility derives evidence/risk cohorts only from bounded
canonical scores for this scorecard, records why, and never rewrites history;
partial, mismatched, or unsupported declarations fail closed. Cohort results
remain descriptive with the mandatory conclusion
`insufficient_for_policy_change`: matched non-idea controls,
dependency-aware uncertainty, and out-of-sample validation are still absent.
The scorecard records zero provider calls, writes, routing, priority, Decision
score, calibration, threshold, publication-authority, or automatic policy
changes and inherits every Safety Invariant below.

The closed `decision_radar.protocol_v2_episode_coverage_frontier` v1 expands
that exact scorecard across all eight canonical Decision routes and all seven
canonical primary origins. It names zero-episode categories explicitly and
binds the scorecard schema, contract digest, input-binding digest, and
evaluation clock; campaign reports and the dashboard copy this validated
projection rather than recomputing cohorts. The current genuine campaign has
three fixed-start episodes: two `dashboard_watch`, one `risk_watch`, and only
the `market_led` primary origin. The other six routes and six origins are
therefore visible evidence gaps, not healthy-empty or negative results. This
frontier does not choose minimum samples, claim statistical or cross-asset
independence, provide matched controls, bind the Protocol-v2 annex, or change
routes, scores, thresholds, providers, artifacts, or policy.

Forward empirical live projections use schema v5 to preserve that exact closed
frontier as a separately validated contract. Schemas v1 through v4 remain
readable; v4 still validates its point-in-time control context, while older
source reports expose the frontier as compatibility-unavailable rather than
zero. Research Lab renders a v5 frontier only as the immutable live snapshot
sealed into its empirical bundle and keeps it separate from historical replay.
The current sealed seven-file Protocol-v1 bundle remains byte-identical and is
not silently regenerated to adopt v5.

Prospective live/no-send observations now retain the exact point-in-time
top-liquid universe membership, one-based volume rank, selected-set size,
configured limit, and selection policy needed by a future Bybit intersection
and matched-control pool. They also retain a separate
`control_liquidity_tier`, computed by the existing state-feature liquidity
bucket with its explicit basis. This field is measurement-only and never
replaces the operator-facing `liquidity_tier` used by Decision routing. The
rolling cache copies only context explicitly present on the original row, so
historical observations are not backfilled or reinterpreted. Campaign
history now has a prospective control-only market-regime collector. It requires
the complete same-clock ranked universe, baseline-counted rows, and closed
percent-point `temporal_return_24h` evidence. BTC and the universe median both
positive produce `risk_on`, both negative produce `risk_off`, and disagreement
or a zero produces `mixed`. The exact input observation set is digest-bound and
the result is copied only to those retained-history rows; it is not exposed to
Decision evaluation. The campaign report separately replays the exact current
authority's manifest-bound normalized market-source bytes and reports eligible
versus missing inputs, canonical asset/symbol/rank, and field-level failure
reasons. This replay is diagnostic only: it does not mutate retained history,
backfill an unavailable regime, call a provider, or feed routing or policy.
Campaign readiness reports exact historical coverage but performs no selection,
outcome read, partition assignment, backfill, or policy change. It remains
partial until a successful qualifying cycle has persisted that context and a
pre-holdout Protocol-v2 partition is present.

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

Each completed cycle writes a post-doctor pilot audit before publication. Pilot
audit contract v1 is distinct from market provenance contract v2 and remains
immutable evidence of that prepublication attempt. The audit records
the exact namespace/run/revision, canonical pointer binding, request/source/
history fingerprints, full-universe cold/warming/warm counts and observations
per asset, direct/proxy feature bases, spread coverage, routes/scores/outcomes,
doctor and dashboard status, and zero-side-effect counters. Market-quality
counts are derived from the complete exact snapshot universe, not merely the
subset promoted into candidates. It separately names
`provider_adapter_invoked`, `network_call_attempted`, and
`provider_request_succeeded`; mock adapter invocation is never presented as a
network call. Campaign-level evidence is tracked in
`research/RADAR_LIVE_OBSERVATION_CAMPAIGN_REPORT.md` / `.json` without claiming
a warm baseline before the required prior observations and time coverage exist.
`make radar-market-campaign-report` rebuilds that canonical pair from local
artifacts only, makes no provider call, and reports authoritative and
non-authoritative generations, failed/blocked attempts, attempt-audit status,
final-publication status, dashboard-operations status, current authority, route
counts, feature maturity, next eligible time, data-quality limits, and
pending/mature outcomes. It cannot claim both current authority and an
unpublished final state; legacy `audit_status` is only a compatibility alias for
`publication_status`, not a second authority claim.
Its Decision campaign totals remain explicitly separate from Event Alpha
catalyst burn-in.

Human review latency is a separate explicit-action measurement, never a web
analytics side effect. The shared append-only ledger is
`radar_market_history_cache/event_decision_radar_review_timing_events.jsonl`.
Only confirmed `radar-review-timing-view` and
`radar-review-timing-complete` commands can append one first-view and one later
completion event for an exact namespace/idea; status and queue discovery are
read-only/no-network. The queue selects only campaign-counted ideas with valid
final publication and operations receipts, revalidates the exact source
generation, prints the next confirmed command, and reports legacy/unpublished
ideas only as excluded counts. Its closed v1 generation projection copies only
the canonical complete-generation counting and final-receipt fields required by
that revalidation; it does not rebuild baseline, episode, scorecard, or temporal-
surprise campaign analytics. Equal-clock projection and comprehensive-report
inputs must produce the same queue, and the projection explicitly reports
`full_campaign_report_rebuilt=false`. The normal Make surfaces render a concise
action view; queue schema v3 and its presentation context v2 state the exact
expiry and whether each item is expired. Every row points first to the read-only
`radar-review-timing-inspect` command, which renders the exact stored card only
after descriptor-anchored directory-tree fingerprint verification. Inspection
does not record a view, make a provider call, or write an artifact; the separate
confirmed command remains the only timing boundary.
`RADAR_REVIEW_TIMING_OUTPUT=json` preserves the full machine-
readable payload from the same evaluation. The human summary groups recurring
`idea_id` values to make repeated work visible, but every artifact-
namespace/idea pair remains a separate timing action with its exact confirmed
command; the grouping is never evidence deduplication. Queue schema v2 adds
presentation-only canonical asset/symbol, anomaly type, catalyst/timing state,
and bounded Decision scores. Candidate facts remain bound by the integrated-
candidate digest and Decision values by the projection digest; the added context
never enters timing events or the path-free campaign projection. A receipt-
backed historical generation remains reviewable when ordinary generation/doctor
staleness is its sole authority defect; any structural authority defect still
fails closed.
Dashboard GET/HEAD, phone access, health probes, previews, and notifications
never count as human attention. `idea_observed_at` comes from the canonical
Decision projection. Conservative provable `idea_available_at` is the exact
owned-dashboard operations-receipt time. Every event binds the run, revision,
operator-state digest, canonical Decision projection, candidate/Core artifact
digests, and publication/operations receipt digests. The campaign report
revalidates those sources and derives pipeline, available-to-first-view,
review-duration, and available-to-completion latency through its point-in-time
report cutoff. No event is invented when a review action is absent. The entire
surface is descriptive, makes zero provider calls, has no automatic policy
effect, and remains `protocol_v2_evidence_eligible=false` and
`protocol_v2_annex_bound=false` until preregistration seals clocks, censoring,
missing-action, and latency-cost rules.

## Daily Operations and Execution-Quality Readiness

Daily Operations v1.1 is a local maintenance coordinator, not a trading system.
It is implemented but remains disabled until the operator explicitly confirms
LaunchAgent installation. Readiness/status perform no provider call and refresh
only one bounded credential-free current-status receipt. Their Make surfaces
default to a concise allowlisted operator summary; setting
`RADAR_DAILY_OPS_OUTPUT=json` preserves the full machine-readable compatibility
payload. Neither output mode changes provider eligibility or call behavior. A manual or scheduled
cycle runs readiness before any possible provider call, respects the stable one-hour reservation,
makes at most one bounded already-authorized CoinGecko no-send observation, and
uses a new immutable namespace. It records attempted, skipped, blocked,
successful, and failed cycles plus last readiness, last attempt, last successful
publication, post-attempt next eligibility, authorization at the last cycle,
authorization check time, scheduler health, sanitized launchd last-exit/run
counts, and skip/block reason. A loaded job with a non-zero last exit is
unhealthy rather than green by ownership alone.

A complete operator state and zero-blocker strict doctor precede publication.
The immutable `event_market_no_send_prepublication_audit.json` preserves the
attempt state. After exact pointer publication,
`event_radar_publication_receipt.json` records `published`; after the exact
owned loopback dashboard is running and terminal success is journaled,
`event_radar_dashboard_operations_receipt.json` records
`dashboard_restarted`. These closed receipts bind the namespace, run, revision,
operator-state digest, artifact fingerprints, doctor result, and pointer digest.
The final publication receipt also binds the exact prepublication audit digest.
Strict doctor, readiness, campaign report, operator state, and dashboard history
must agree; a current managed generation missing or contradicting either final
receipt is blocked. Publication, restart, receipt, or terminal-journal failure
restores the previous trusted authority; if restoration is impossible, only the
failed new pointer is descriptor-safely invalidated.

The exact pointer-started dashboard process has one narrow bootstrap phase: a
valid current final-publication receipt may start the process before the
operations receipt exists, but every GET/HEAD remains 503-closed. After terminal
state and the operations receipt are written and revalidated, a bounded
HTTP probe must return trusted dashboard content with the exact namespace, run,
revision, and operator digest while the same positive owned PID remains running
before and after the request. Pointer publication, rollback, invalidation, and
legacy repair share one descriptor-anchored mutation transaction; replacing the
artifact-root pathname cannot redirect its pointer reads, writes, or removals.
Rollback restores only the exact saved bytes whose parsed mapping and SHA-256
match the prior immutable publication receipt. A later failed terminal row for
the same cycle invalidates the earlier success receipt.

Legacy reconciliation is explicit, not automatic:

```sh
make radar-daily-ops-reconcile-publication PYTHON=.venv/bin/python
```

It is allowed only for the exact current pointer plus one unique successful
terminal cycle that already proves pointer publication and owned restart. It
makes no provider call and performs no process restart. Revalidating the same
authority preserves the exact pointer bytes. Explicit reconciliation may
restore only a receipt-bound pointer whose sole drift is the pre-v1.1
`authority_checked_at` readiness refresh; every broader drift remains blocked.
The dashboard reads the bounded receipts without invoking launchd, providers,
writes, or the process
environment. A current-status receipt expires after 15 minutes; stale current
authorization becomes unknown rather than inheriting the last cycle's value.

When the scheduler is disabled, the next observation is eligible, and authority
is within 90 minutes of expiry, Today and System Health show a prominent but
non-alarming recovery action: time remaining, `make radar-daily-ops-readiness
PYTHON=.venv/bin/python`, the separately confirmed install command, and the
confirmed uninstall rollback. Nothing runs automatically. No service
install/uninstall occurs without `CONFIRM=1`, and the service plist never embeds
provider authorization or credentials.

Execution-quality readiness v22 records the owner-confirmed primary research
surface: Bybit USDT-linear perpetuals, public market data only, with current
jurisdiction/account eligibility affirmed for this scope. The eligible-universe
rule is the top 30 liquidity-ranked Decision Radar assets intersected with exact
active `LinearPerpetual`, `Trading`, USDT-quoted, USDT-settled, non-prelisting
contracts. The exact resulting instrument IDs remain unfrozen until the
Protocol-v2 annex is sealed.

The primary Protocol-v2 spread, depth, impact, fee, funding, and P&L cost
currency is sealed as native USDT. The system does not relabel USDT as USD or
assume a 1:1 conversion. Any future cross-venue USD projection requires its own
explicit conversion source, clock, and policy and is outside the selected
Bybit Protocol-v2 cost surface. This closes only the currency-unit decision;
fees, order style, notional sizes, slippage, latency cost, funding treatment,
and the final annex remain unsealed.

The cost-model status is deliberately explicit. Bybit's current public
[fee reference](https://www.bybit.com/en/help-center/article/Trading-Fee-Structure)
states that actual rates vary by region and account tier, so it is not
account- or symbol-authoritative. The official
[account fee-rate endpoint](https://bybit-exchange.github.io/docs/v5/account/fee-rate)
is authenticated and therefore outside the confirmed public-market-data-only
scope; it is not authorized or called. Protocol v2 must separately seal its fee
assumption/source, entry and exit order style, USDT notionals, base-quantity
selection and venue-step rounding, spread and
visible-book impact application, beyond-book slippage, funding treatment,
latency cost, and unavailable-cost policy. Until then
`protocol_v2_cost_model_sealed=false` remains operator truth.

Funding settlement arithmetic is closed for one supplied event, and the pure
interval v1 projection can now require an exact, strictly ordered match between
an operator-supplied expected settlement schedule and the supplied events. It
aggregates their signed cash flows and reconciles the result to visible-book
P&L. Bybit defines a USDT-perpetual funding transfer as base quantity times the
settlement mark price times the settled fractional rate: positive funding is
paid by longs to shorts, while negative funding reverses that transfer. Bybit's
[instrument metadata](https://bybit-exchange.github.io/docs/v5/market/instrument)
exposes the symbol-specific `fundingInterval` in minutes;
the interval projection therefore requires a bounded, causal schedule source
and an effective window covering the modeled position. It rejects missing,
duplicate, reordered, boundary-ambiguous, or extra settlement times as well as
percent/fraction mistakes, unsafe references, and source-round-trip drift.
This exact reconciliation proves only the supplied, unsealed schedule. It does
not obtain a historical schedule, prove schedule authority, obtain required
settlement-time marks or rates, seal any source, call a provider, or make the
row Protocol-v2 evidence. `holding_interval_funding_coverage_complete=false`
therefore remains explicit until genuine schedule, mark, and rate captures and
the final funding holding policy are sealed.

The pure composite cost scenario v1 now prevents a different integration error:
adding a fee projection, funding projection, and visible-book result that do not
belong to the same round trip. It fully rederives the fee and funding interval
from the embedded assumptions and exact source round trip, requires exact value
equality with both supplied component projections, and then reconciles gross
return, side-specific executed-value taker fees, signed funding cash flow, and
visible-book drag into one native-USDT net result. Its modeled component set is
complete only for that declared scope. Latency cost, beyond-book slippage,
unavailable-cost behavior, authoritative schedule/rate/mark/fee sources, final
notional/style policy, and annex binding remain absent, so
`composite_complete_protocol_v2_cost_model=false`.

Decision-price latency arithmetic is now separately closed for supplied
research references. Each entry and exit reference carries exact best bid/ask,
matching-engine observation time, local acquisition time, explicit decision
time, source reference, and lineage. The reference must precede its later
execution book, the exit reference must follow the modeled position open, and
reference lineages cannot reuse each other or either execution lineage. The
projection decomposes decision-reference gross return into signed midpoint
drift and the existing execution-book gross return, then reconciles visible-book
impact without adding spread again. Positive latency cost is adverse and a
negative value is favorable; neither is clamped to zero.

The decision-reference composite fully rederives that latency projection plus
the existing visible-book, taker-fee, and funding components before accepting
one native-USDT identity. This closes supplied-input implementation-shortfall
arithmetic only. No order submission or fill was observed, the decision books
and latency policy are unsealed, and beyond-visible-book slippage and
unavailable-cost behavior remain absent. Therefore the new composite keeps
`complete_protocol_v2_cost_model=false`, `protocol_v2_annex_bound=false`, and
`protocol_v2_evidence_eligible=false`.

Residual-cost sensitivity v1 closes the missing-data behavior without claiming
that the missing evidence has been measured. It fully rederives the exact
decision-reference composite, then either applies explicit non-negative
per-leg basis-point assumptions to each leg's actual executed USDT value or
returns no numeric all-in result when the assumption is absent. Missing
residual cost is never silently treated as zero. Even an explicit zero
sensitivity remains an unobserved research assumption: source authority,
slippage policy, unavailable-cost policy, complete cost-model status, annex
binding, and Protocol-v2 evidence eligibility all remain false.

The selected capability and snapshot projection use the real native fields:
`bid_depth_usdt_by_band`, `ask_depth_usdt_by_band`, and side-specific
`*_price_impact_bps_by_notional_usdt`. The older generic `*_usd_*` interface is
an inactive cross-venue placeholder, not the selected Bybit schema, and no
generic conversion is available. Readiness must keep these scopes separate so
an operator cannot mistake an unperformed USD conversion for observed evidence.

Side-specific visible-book impact is measured from `mid_price`. A marketable
buy therefore already contains the ask-side half-spread and a marketable sell
already contains the bid-side half-spread, plus any additional walked depth.
Consumers must not add `spread_bps` again to the same side impact. A complete
round-trip estimate needs separate entry and exit snapshots and the selected
side at each boundary. The eventual entry/exit snapshot policy remains
unsealed; this closes the primitive math, not the Protocol-v2 cost decision.

The per-snapshot notional curves remain intentionally asymmetric: buy impact
means exact USDT spent, while sell impact means exact USDT proceeds. The same
numeric USDT value therefore does not prove the same base-asset quantity, even
within one book. The offline round-trip primitive now avoids that error: for a
specified quantity aligned to the instrument's `qtyStep`, it walks the entry
and exit sides of two distinct fresh snapshots using the same exact underlying-
token quantity. This follows Bybit's current
[USDT-contract quantity definition](https://www.bybit.com/en/help-center/article/Order-Cost-USDT-Contract),
which denominates USDT/USDC contract quantity in the underlying token. It
reports long or short gross mid-mark return, net visible-book return, and their
USDT drag, normalized to entry mid notional. It never adds `spread_bps`
separately, and it is not realized execution.

The v3 round-trip projection binds a separate instrument-catalog snapshot to
each book leg. Entry constraints must be causal to the entry book; exit
constraints must have a distinct lineage, be refreshed after entry, and remain
causal to the exit book. Both snapshots must identify the exact same native
instrument, while each independently supplies `qtyStep`, `minOrderQty`,
`maxOrderQty`, `maxMktOrderQty`, and `minNotionalValue`. The reconciled quantity
must align to both steps and satisfy each leg's own minimum, maxima, and visible
quote-value minimum. The projection reports market versus marketable-limit
eligibility per leg plus their same-style intersection, but permits the two
legs to have different eligible styles because the primitive does not select
an order style. Bybit's
[instrument contract](https://bybit-exchange.github.io/docs/v5/market/instrument)
states that maximum order quantities change over time, so reusing entry
constraints for an exit is invalid. The Protocol-v2 constraint-freshness policy
remains explicitly unsealed. Size selection, quantity rounding from a USDT
tier, order style, fees, funding, latency, beyond-book liquidity, and
unavailable-cost behavior remain unsealed; therefore
`protocol_v2_cost_model_sealed=false` remains correct.

The offline v1 target-notional projection now closes the arithmetic between a
caller-supplied native-USDT entry-mid reference and the quantity primitive. It
uses the exact entry-book mid, floors the implied underlying-token quantity to
`qtyStep`, never exceeds the supplied mid-notional, and proves that the
shortfall is strictly less than one quantity-step notional. Minimum quantity,
minimum notional, dynamic market/limit maxima, catalog causality, and book
identity remain enforced before the derived quantity is joined through target-
notional composite v2 to the v3 entry/exit walk with separate per-leg
constraint evidence. The target is deliberately not labeled a quote-spend budget:
a marketable buy can spend more, and a marketable sell can receive less,
because spread and walked depth are part of the observed leg. The system has
not chosen the final USDT tier set, adopted the floor rule as Protocol-v2
policy, or selected an order style; those remain annex decisions.

The read-only capture-pair projection now connects that math to immutable
evidence. It accepts two explicitly named capture namespaces—never a guessed
latest pointer—opens the artifact base plus both namespaces together through
held no-follow descriptors, and fully rederives both strict-clean bundles from
their exact raw catalog and order-book responses. Both capture sets must be
fresh at their own completion, distinct, and ordered without overlapping
windows. The selected native instrument must exist exactly once in both, after
which their independent catalog clocks, response hashes, request lineages, and
dynamic constraints feed the target-notional v2 / round-trip v3 model. The
projection is read-only and makes zero provider calls. It remains annex-unbound
and Protocol-v2-ineligible until genuine capture IDs and the complete cost
policy are human-sealed. No genuine Bybit capture pair exists yet.

Use the exact read-only operator surface only after two genuine captures exist:

```bash
make radar-execution-quality-bybit-round-trip \
  BYBIT_ENTRY_EXECUTION_CAPTURE_NAMESPACE=<entry> \
  BYBIT_EXIT_EXECUTION_CAPTURE_NAMESPACE=<exit> \
  BYBIT_EXECUTION_INSTRUMENT_ID=<instrument> \
  BYBIT_EXECUTION_POSITION_SIDE=<long_or_short> \
  BYBIT_EXECUTION_TARGET_NOTIONAL_USDT=<usdt> \
  PYTHON=.venv/bin/python
```

The offline slice validates supplied V5 instrument and order-book payloads,
preserves provider/snapshot clocks and book sequence, and derives spread and
USDT depth/impact. A second checked fixture proves the quantity-reconciled
entry/exit primitive. A
separately gated public REST adapter and immutable capture contract are
implemented but inactive. Readiness and capture status make no provider call or
write. A confirmed capture requires the already-present dedicated authorization
flag. Capture v5 performs one complete
`category=linear&status=Trading&limit=1000` instrument-catalog GET, rejects any
missing or non-empty continuation cursor as incomplete, and then performs one 200-level order-book
GET per exact eligible instrument. Its absolute bound is 31; the current
authority-specific bound is reported by readiness as one catalog request plus
the exact eligible-instrument count. It never retries and has no credential,
private-data, order, trading, or send surface. Every individual book retains
acquisition freshness, while the
closed set is fresh only when every provider observation is still at most 15
seconds old at full-set completion. A complete but aged set remains immutable
evidence and is explicitly Protocol-v2 input-quality-ineligible. Only a complete
run is published: exact accepted response bytes,
request timing, the exact Radar authority and universe, normalized observations,
fingerprints, a completion receipt, and a stable latest pointer are retained.
All guarded Bybit REST collectors reject booleans, strings, non-finite values,
and values outside `0 < timeout <= 30` before provider access. Order-book
normalization is closed to the declared 15-second freshness threshold because
the current immutable projection has no field for a caller-selected policy; a
different threshold requires a versioned end-to-end schema rather than a
runtime override.
Validation holds
one descriptor-anchored namespace for the complete read, rederives every
projection from raw bytes, rejects pointer rollback/drift, and excludes unknown
provider fields from the closed capture summary. The standard review archive
selects and fully revalidates only the latest completed capture.
For exact-response capture v5, each normalized order book uses the corresponding
accepted transport response's read-completion time as `acquired_at`. The
immutable validator requires all requests and responses to remain inside the
declared capture window, preserve sequential timing, and match each book's
acquisition clock exactly; a second injected clock cannot make the evidence
appear fresher.

The venue-native derivatives context contract separately normalizes supplied
Bybit ticker, settled-funding, 1h open-interest, and 1h long/short-account-ratio
responses for the exact selected execution-quality instrument. Run
`make radar-derivatives-bybit-smoke PYTHON=.venv/bin/python` to prove the
offline path. Contract v2 preserves every component provider clock and request
lineage, dates the composite snapshot from its oldest component response,
exposes the newest-response clock and total response span, and therefore cannot
hide one stale input behind another fresh response. It keeps USDT,
base-asset, fraction, percent-point, and basis-point units explicit; rejects the
known 100x fraction/percent failure; and plans no more than four public GETs per
instrument or 120 for the future top-30 intersection. The offline module has no
HTTP client. A guarded no-write adapter now exists but is inactive: no-call
`make radar-derivatives-bybit-readiness PYTHON=.venv/bin/python` requires a
genuine fresh execution-quality capture for exact current authority and the
separate already-present `RSI_DECISION_RADAR_BYBIT_DERIVATIVES_LIVE=1` flag.
The normal target prints a bounded prerequisite summary; use
`RADAR_BYBIT_DERIVATIVES_READINESS_OUTPUT=json` for the full structured packet.
Confirmed collection performs exactly four public GETs per eligible instrument,
never retries, preserves request/provider clocks and exact response bytes in
memory, and revalidates the capture/instrument/authority chain. A closed no-I/O
capture-input contract now rederives every normalized context, unit, request
clock, lineage row, and deterministic capture identity from those exact bytes;
mapping-only diagnostic results cannot enter it. The separately confirmed
capture command publishes one descriptor-anchored immutable namespace with raw
responses, closed projections, manifest, completion receipt, and rollback-
protected latest pointer. Read-only status and the standard review export fully
revalidate the capture from raw bytes. Guarded live/capture v3 preserves both
acquisition freshness and full-set-completion freshness, the exact 15-second
maximum context age, and the oldest-component provider-clock policy through
every immutable publication surface. Exact responses must form one ordered
non-overlapping window. A complete capture that ages during sequential
collection remains exact evidence but is not Protocol-v2 input-quality
eligible. No genuine capture exists in the current store. Output is context-only, non-directional,
policy-neutral, input-quality-ineligible, annex-unbound, and Protocol-v2-
ineligible. Coinalyze is optional secondary Catalyst-Radar corroboration, not a
substitute for the chosen venue-native derivatives or execution surface.

Native liquidation events remain a separate Bybit public-WebSocket surface.
The exact offline `allLiquidation.{instrument_id}` message contract is joined
by a detached, confirmation-gated operator-transcript import. It preserves the
supplied subscribe, acknowledgement, and observed data application payloads,
operator clocks, deterministic normalized events, manifest, and completion
receipt in one immutable namespace. The package claims only
`observed_messages_only` coverage, publishes no latest pointer, and stays
campaign-, dashboard-, policy-, directional-, input-quality-, and Protocol-v2-
detached. In particular, application payloads do not prove TLS, WebSocket frame
bytes, project-owned transport, stream continuity, dropped-message absence, or
liquidation absence during silent intervals. The disposable offline gate is
`make radar-derivatives-bybit-liquidation-capture-smoke
PYTHON=.venv/bin/python`; local validation and confirmed import require an
explicit transcript path, and status requires the exact returned namespace.
This audit boundary does not replace the still-missing separately authorized,
permitted, project-owned bounded listener capture.

Structured unlock context remains a separate evidence surface. Tokenomist v5
response normalization is closed against the current synthetic fixture, and
`make radar-unlock-tokenomist-v5-capture-smoke PYTHON=.venv/bin/python`
proves a five-artifact immutable fixture bundle and strict doctor entirely
inside a disposable root. Exact synthetic source bytes, request identity,
normalized rows, units, clocks, manifest, and completion receipt are rederived;
complete, healthy-empty, and partial-page results remain distinct. The smoke
retains nothing, publishes no pointer, and grants no campaign, dashboard,
directional, source, input-quality, or Protocol-v2 authority. It does not prove
complete multi-page acquisition or genuine provider bytes.

The no-call/no-write readiness surface is
`make radar-unlock-tokenomist-v5-readiness PYTHON=.venv/bin/python`. It reads
only the dedicated boolean `RSI_DECISION_RADAR_TOKENOMIST_V5_LIVE` boundary,
never an API credential, and remains blocked even when the flag is present.
An applicable owner-approved subscription, genuine-byte retention and
redistribution treatment, bounded live transport, health/backoff, immutable
multi-page completion evidence, and later Protocol-v2 annex binding are all
still missing. Tokenomist v4 is deprecated and live-ineligible. The next safe
action is the disposable capture smoke, not a provider call; disable the unused
future boundary by unsetting the dedicated flag.

The direct intraday offline contract likewise validates exact latest-completed
Bybit trade-price candles independently at 1h and 4h. It cuts requests off just
before the current bucket, preserves native instrument identity, OHLC,
base-asset volume, USDT turnover, provider/request/response clocks, and
close-to-acquisition latency, and rejects open/missing/misidentified bars.
Contract v3 marks a bar fresh only when both the completed bar remains inside
its interval recency window and the provider response is no more than 15
seconds old; the two component states and ages remain explicit, and a provider
response cannot predate the completed candle it contains. Guarded live/capture
v4 then re-evaluates every bar-close and provider-response clock when the final
sequential request completes. Acquisition and completion freshness, the maximum
provider-response age, and the minimum remaining bar-recency window stay
explicit; only completion freshness can qualify the set as Protocol-v2 input.
A complete aged set remains immutable evidence but is not input-quality
eligible. Run
`make radar-intraday-bybit-smoke PYTHON=.venv/bin/python` with zero provider
calls or writes. Its guarded live collector is implemented but inactive: zero-
call readiness requires a genuine fresh execution-quality capture for exact
current Radar authority plus separate intraday authorization. Confirmed capture
performs exactly two public GETs per eligible instrument with no retry, then
revalidates the full prerequisite chain before the first write. Only a complete
immutable bundle is published: it binds the source execution-quality capture
and pointer digest, exact native instruments, accepted raw responses,
request/provider clocks, normalized bars, fingerprints, manifest, completion
receipt, and latest pointer. Validation holds one descriptor-anchored namespace
and rederives every bar plus the final-set freshness projection from raw bytes;
request timing must remain one sequential response window, and symlink, race,
drift, and rollback failures close the bundle. Status is no-call/no-write, and the standard review
archive selects and fully revalidates only the latest completed capture. The
stdout-only collect target remains diagnostic and writes nothing. CoinGecko
sparklines, interpolation, derived 4h values, and mark/index bars are not direct
substitutes.

A fresh complete capture may be `protocol_v2_input_quality_eligible`, but it
remains `protocol_v2_evidence_eligible=false` and
`protocol_v2_annex_bound=false`. Promotion occurs only when the sealed
Protocol-v2 annex explicitly references the immutable capture ID; historical
capture bytes are never rewritten to manufacture authority. No genuine capture
exists yet, so live spread remains unavailable. The unfrozen exact set, absent
runtime authorization, and honest reachability after the recorded Bybit 403
remain blockers; 403/429 or regional restrictions stop immediately, and no
proxy, VPN, alternate host, or region bypass is authorized.

The remaining human decisions stay explicit:

- Daily Operations: inspect with `make radar-daily-ops-readiness
  PYTHON=.venv/bin/python` (no provider call); install only with `CONFIRM=1 make
  radar-daily-ops-install PYTHON=.venv/bin/python`; roll back with confirmed
  `radar-daily-ops-uninstall`.
- Official calendar: inspect with `make radar-calendar-official-readiness
  PYTHON=.venv/bin/python` (no provider call or write). Acquisition remains
  blocked without the already-present live authorization; BLS is skipped as
  `missing_configuration` without an honest contact. An authorized acquire may
  call each configured Fed/BLS/BEA source at most once and never creates or
  mutates authorization.
- Execution quality: inspect with `make radar-execution-quality-readiness
  PYTHON=.venv/bin/python` (concise and static/no-network); use the `-full`
  target for the complete static venue/cost catalog or `-json` for the closed
  structured packet. Then run the checked offline
  normalizer with `make radar-execution-quality-bybit-smoke
  PYTHON=.venv/bin/python`. The direct completed-bar fixture gate is `make
  radar-intraday-bybit-smoke PYTHON=.venv/bin/python`; its latest immutable
  capture can be checked with `make radar-intraday-bybit-status
  PYTHON=.venv/bin/python`. The live-boundary readiness command is `make
  radar-execution-quality-bybit-readiness PYTHON=.venv/bin/python`; it remains
  no-call/no-write. Validate the latest capture without a provider call using
  `make radar-execution-quality-bybit-status PYTHON=.venv/bin/python`. Only an
  already-authorized, explicit `CONFIRM=1 make
  radar-execution-quality-bybit-capture PYTHON=.venv/bin/python` may collect and
  seal exact responses. Bybit perpetual is selected and the capture contract
  exists, but live spread remains unavailable while it is inactive and no valid
  capture exists. The offline cost primitive now classifies every immediately
  executing book walk—including an immediately marketable limit—as taker
  liquidity and can apply caller-supplied fractional fee assumptions to each
  leg's exact executed USDT value. It does not select a rate, model maker fills,
  use account data, or seal the fee source/effective window or Protocol-v2
  annex. Collection is disabled by unsetting
  `RSI_DECISION_RADAR_BYBIT_EXECUTION_QUALITY_LIVE`; no provider process or order
  path exists.
- Direct intraday: after one genuine current execution-quality capture exists,
  inspect `make radar-intraday-bybit-readiness PYTHON=.venv/bin/python` without
  a call or write. The normal target prints a bounded prerequisite summary; use
  `RADAR_BYBIT_INTRADAY_READINESS_OUTPUT=json` for the full structured packet.
  Only separately present
  `RSI_DECISION_RADAR_BYBIT_INTRADAY_LIVE=1` plus `CONFIRM=1 make
  radar-intraday-bybit-capture PYTHON=.venv/bin/python` may collect and seal
  exact 1h/4h responses. Disable the boundary by unsetting that flag. A complete
  capture remains campaign-detached and annex-ineligible until preregistration.
- Structured unlocks: inspect `make radar-unlock-tokenomist-v5-readiness
  PYTHON=.venv/bin/python` without a call or write. The response and immutable
  fixture contracts can be checked with `make radar-unlock-tokenomist-v5-smoke
  PYTHON=.venv/bin/python` and `make radar-unlock-tokenomist-v5-capture-smoke
  PYTHON=.venv/bin/python`; both are synthetic, non-authoritative, and offline.
  No live command exists. Genuine acquisition requires a separately approved
  Tokenomist v5 subscription, retention/export decision, bounded transport,
  explicit confirmation, and the already-present dedicated authorization flag.
  Unset `RSI_DECISION_RADAR_TOKENOMIST_V5_LIVE` to disable that future boundary.
- Human review timing: inspect `make radar-review-timing-status
  PYTHON=.venv/bin/python` without a provider call or write, then run `make
  radar-review-timing-queue PYTHON=.venv/bin/python` to discover the exact
  receipt-backed ideas and their next safe commands. Queue discovery uses its
  exact v1 generation projection and does not rebuild unrelated campaign
  analytics. Its summary groups recurring idea IDs for readability while
  retaining every generation-specific action and command, and names the exact
  asset, anomaly type, expiry, expired/current state, and Decision score context
  needed to identify the work. Run the row's `make
  radar-review-timing-inspect RADAR_REVIEW_NAMESPACE=<exact>
  RADAR_REVIEW_IDEA_ID=<exact>` command before recording an action; it verifies
  and renders the exact stored card without a provider call, write, or timing
  event. Use
  `RADAR_REVIEW_TIMING_OUTPUT=json` when the complete binding and digest payload
  is needed. Record only a real human action with `CONFIRM=1 make
  radar-review-timing-view
  RADAR_REVIEW_NAMESPACE=<exact> RADAR_REVIEW_IDEA_ID=<exact>
  RADAR_REVIEWER_ALIAS=<alias>` and later the matching `...-complete` target.
  The application never records a dashboard request as a view, and no missing
  action is synthesized.
- Phone access: private and public readiness/status are non-enabling checks.
  Either route requires its exact `CONFIRM=1 ...-enable` command and is rolled
  back only with the matching confirmed disable command; neither is enabled by
  Daily Operations.

The authoritative pointer uses a stable canonical operator-state digest. A
strict-doctor rerun against an unchanged revision may refresh only the top-level
`updated_at` and nested `doctor.verified_at` clocks without changing pointer
identity. Every substantive doctor value and the complete artifact manifest
remain fingerprinted; any other operator-state or artifact drift invalidates
the exact binding and blocks current authority.

## Artifact-Heavy Verification

Fixture tests use isolated temporary artifact bases unless their purpose is to
verify shipped artifacts. Static project-health checks memoize source/AST work
within the process and never recursively walk cumulative operational roots for
unrelated checks. `test-full` and `verify-fast` write cumulative per-file timing
reports to `.pytest_cache/test_file_timing_report.{json,md}` without rerunning
tests. `make test-artifact-heavy-extracted-checkout PYTHON=python3` runs the
focused isolated cumulative-artifact guard with a default five-second budget
and writes dedicated JSON/Markdown timing reports. In a source-with-artifacts
review checkout it precedes `make verify-fast PYTHON=python3`; both report pairs
are retained as reproducible release evidence. The practical same-machine full
review budget is 360 seconds. This is observational, not a hard CI wall-clock
gate; a run above 360 seconds or more than 25% slower than the latest comparable
same-machine baseline requires investigation before release.

The retention inventory is bounded to 128 namespaces and 128 direct entries per
namespace, reads no research payloads beyond the bounded namespace-status
control marker, and performs no recursive scan. A truncated namespace inventory
is a blocker rather than a false complete result. It may name advisory
compaction candidates, but `retention_policy_authorized`,
`compaction_performed`, and `deletion_performed` remain false. Canonical audit
history cannot be compacted or deleted without a separate explicit retention
policy and operator authorization.

## Outcomes and Learning

Every current canonical Decision idea, including diagnostic controls, receives
a pending outcome placeholder. The shared mutable campaign ledger is
`radar_market_history_cache/event_decision_radar_campaign_outcomes.jsonl`; it is
rebuilt deterministically from immutable generation candidates/Core rows and
locally retained observed prices, while origin namespaces and their pointer
history remain unchanged. Rows stay pending until the declared canonical
primary horizon is due and sufficient observed prices exist, then mature with
exact price lineage; a due primary horizon without sufficient price lineage is
`due_missing_price`. Secondary-horizon maturity never promotes the primary
state. A refresh makes no provider call.

Each outcome's origins, route, directional bias, actionability cohort,
evidence-confidence cohort, risk cohort, catalyst status, timing, and phase are
copied from the canonical projection. Candidate/outcome count mismatch or cohort
drift is a doctor blocker for the trusted publication profile. The explicitly
labeled legacy-null scorecard compatibility derives only missing historical
evidence/risk cohort labels from the unchanged canonical scores and does not
rewrite the row; every other partial, unsupported, or mismatched cohort remains
fail-closed drift.

Outcomes and optional human feedback are measurement evidence only. They do not
automatically alter thresholds, routes, priors, or notification policy. Any
change to decision policy remains an explicit, human-approved, versioned
decision. Immutable empirical replay outcomes remain in their fingerprinted
research-run namespaces and are never appended to, merged into, or used to
rewrite the live campaign outcome ledger. Optional empirical-review labels are
append-only preference metadata and have no automatic scoring or policy effect.

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
- empirical_research_auto_apply: `False`
- empirical_research_production_policy_mutations: `0`
- empirical_research_dashboard_authority_mutations: `0`
