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

## 2026-07-22 - Lead blind-label readiness with the next human action
**Status:** accepted
**Decision:** The normal source-independence OOS readiness Make target is a
bounded stage summary. It shows configured inputs, frozen corpus/template/review
status and counts, descriptive-report coverage, the exact next action, the
blind-label boundary, and zero-I/O/no-policy safety. The complete payload remains
available through `SOURCE_INDEPENDENCE_OOS_READINESS_OUTPUT=json`; direct Python
CLI usage stays JSON by default.
**Why:** The current workflow has one blocker—genuine source-diverse case input
does not exist—but the former full JSON view buried that action among static
contracts. A concise view makes the human evidence task explicit without
revealing cases, partitions, predictions, or fabricating labels.
**Revisit when:** The frozen workflow gains a new genuine stage. Keep the summary
derived from the canonical readiness payload and preserve its full JSON form.

## 2026-07-22 - Lead official-calendar readiness with per-source truth
**Status:** accepted
**Decision:** The normal `radar-calendar-official-readiness` Make surface is a
bounded operator summary. It must show current authorization and BLS contact,
latest attempt/success, each Fed/BEA/BLS source's eligibility and request bound,
partial/local-import support, reasons, exact safe actions, authorization and
rollback boundaries, and zero-call/write safety. The complete payload remains
available through `RADAR_OFFICIAL_MACRO_READINESS_OUTPUT=json`; direct Python
CLI usage stays JSON by default.
**Why:** The prior large JSON payload was correct but obscured the actionable
truth: live acquisition is unauthorized, BLS also lacks contact, all three
sources are individually visible, and a genuine partial local import remains
possible without network access.
**Revisit when:** The source set or authorization boundary changes. Derive the
summary from the canonical readiness object and preserve the full JSON contract.

## 2026-07-22 - Do not substitute snapshot returns for temporal regime evidence
**Status:** accepted
**Decision:** When the exact current-authority regime diagnostic finds an asset
without retained causal `temporal_return_24h`, it may expose a separately valid
current-snapshot `return_24h`, normalized unit, and source basis for diagnosis.
That value remains explicitly ineligible for the temporal regime input and
cannot be promoted, backfilled, or used by routing, scores, thresholds, or
Protocol v2.
**Why:** HBAR and GRAM currently have valid provider-sparkline 24-hour returns,
but neither has a retained point-in-time anchor old enough to prove the causal
24-hour interval. Calling both simply “missing” concealed that distinction;
using the snapshot values would weaken a deliberately stricter evidence
contract.
**Revisit when:** A preregistered Protocol-v2 annex explicitly accepts an exact
provider-return contract as regime evidence and proves its causal clock,
methodology, identity, units, and holdout-safe use.

## 2026-07-22 - Keep regime membership clocks prospective and non-authoritative
**Status:** accepted as operator diagnostic; no anchor or policy authority
**Decision:** Exact-generation regime audit schema v2 records the continuous
membership start and elapsed time for each currently missing causal input only
from complete prospective point-in-time universe envelopes. An asset present in
the first complete envelope has an explicitly unknown start; an observed exit
removes its clock and a later entry starts a new one. Pre-contract rows are not
backfilled into this clock, and membership age must never be interpreted as
proof that a valid temporal-return anchor exists.
**Why:** HBAR entered the prospective top-30 set at 12:12 UTC, exited at 19:08,
and re-entered at 20:09. The current 29/30 result is therefore explained by
only 4.05 hours of continuous prospective membership at cycle 64, while its
older raw observations remain correctly outside the prospective membership
contract. Showing only “recent entry” concealed the reset and invited a false
assumption that a snapshot return or old row could close the causal interval.
**Revisit when:** A preregistered Protocol-v2 annex defines a different causal
membership/anchor contract before holdout access. Never infer anchor eligibility
from membership duration alone.

## 2026-07-22 - Lead outcome recovery readiness with the exact gap
**Status:** accepted
**Decision:** The normal `radar-outcome-price-recovery-readiness` Make surface
is a bounded operator summary. It must show the authoritative namespace, exact
missing outcome request/window, separate general and recovery authorization,
provider-call eligibility, expected activity, reason, next safe command,
authorization boundary, and disable command. The complete unchanged machine
payload remains available through
`RADAR_OUTCOME_RECOVERY_READINESS_OUTPUT=json`; direct Python CLI usage remains
JSON by default for compatibility.
**Why:** One genuine DEXE outcome gap is recoverable, but the former large JSON
view buried the only blocker—the absent dedicated recovery authorization—and
made a read-only readiness check look more complicated than the guarded action.
**Revisit when:** More than the bounded request list can be presented safely in
the summary. Preserve the closed JSON and no-call/no-write readiness boundary.

## 2026-07-22 - Separate exact card inspection from measured review timing
**Status:** accepted
**Decision:** Every human-review queue row states the canonical expiry and its
expired/unexpired status, then offers a read-only exact-card inspection command
before the separate confirmation-gated timing action. Inspection must resolve a
receipt-backed idea/Core pair, retain descriptor-anchored namespace access,
verify the complete current research-card tree against its operator manifest,
and bind card lineage to the exact run/profile/namespace/Core identity. It makes
zero provider calls and writes and never records a first view. Only the explicit
confirmed `radar-review-timing-view` command creates timing evidence.
**Why:** All nine genuine queued ideas were expired, but the prior queue led with
confirmed view commands and no safe exact-card read. Historical inspection is
necessary for informed labeling; silently turning a read into a timing event
would fabricate a clock and violate the explicit-action measurement contract.
**Revisit when:** A sealed Protocol-v2 annex defines an operator-approved UI
interaction as a measured attention event. Version that event boundary
explicitly; do not infer it from CLI inspection, dashboard GET/HEAD, probes, or
previews.

## 2026-07-22 - Bind queue labels to evidence without extending timing events
**Status:** accepted
**Decision:** Human-review queue schema v2 carries a presentation-only operator
context containing canonical asset/symbol, anomaly type, catalyst/timing state,
and bounded Decision scores. Candidate identity fields are covered by the exact
integrated-candidate digest and Decision fields by the canonical projection
digest already present in the timing binding. The append-only timing-event
schema and path-free campaign queue projection deliberately omit this context.
**Why:** Opaque idea IDs made the nine genuine review actions hard to perform:
they actually represent six DEXE observations and three PUMP observations with
different anomaly types and score states. Human-readable identity is necessary
operator context, but it is not a new timing fact and must not silently alter
the immutable ledger contract.
**Revisit when:** A sealed Protocol-v2 annex defines additional human-review
attributes as measurement evidence. Version that event schema explicitly; do
not promote presentation fields implicitly.

## 2026-07-22 - Group recurring review ideas without collapsing timing evidence
**Status:** accepted
**Decision:** The human-readable review queue groups repeated `idea_id` values
to expose recurrence, but the canonical timing identity remains the exact
artifact-namespace/idea pair. Every generation-specific action, ledger event,
and confirmed command remains separate. Grouping is presentation-only and must
not deduplicate evidence, synthesize a human action, or alter the full JSON
queue.
**Why:** The current queue contains nine valid actions but only two recurring
idea IDs across six and three generations. A flat action list hid that repeated
work, while collapsing it would destroy the point-in-time publication and
attention evidence needed for Protocol v2.
**Revisit when:** Protocol-v2 preregistration seals an explicit episode-level
human-review sampling rule. Preserve the immutable generation-specific timing
records even if a later operator surface adds episode-level workflow controls.

## 2026-07-22 - Lead Protocol-v2 progress with decisions and blockers
**Status:** accepted
**Decision:** The normal `radar-research-protocol-v2-progress` target and the
current-progress portion of readiness/check use a concise static summary. It must
show the selected Bybit perpetual surface, protocol/holdout state, genuine-
capture state, all exact activation blockers, canonical changing-campaign path,
priority no-call operator commands, and zero-I/O safety. The complete transcript
and structured packet remain available through explicit `-full` and `-json`
targets; direct Python CLI output remains full-text compatible.
**Why:** The complete static packet is valuable audit detail but buried the
selected venue and actual human/provider boundaries in more than one hundred
lines. The 21-line summary makes the safe next decisions visible without
discarding, re-evaluating, or reading dynamic evidence.
**Revisit when:** A blocker or operator boundary changes. Update the canonical
structured projection first, derive the summary from it, and retain full/JSON
compatibility.

## 2026-07-22 - Cache deterministic shadow primitives, not empirical results
**Status:** accepted
**Decision:** Causal shadow replay may reuse parsed immutable ISO timestamp text
through a bounded process-local cache and may reuse an exact direct-return sample
inside the single projection evaluation that owns its observation tuple and
horizon. It must continue to evaluate every observation, baseline, relative-
return alignment, overlap trace, digest, and closed schema normally; projections
and policy outputs are not cached. Field-specific invalid-timestamp errors must
remain intact, per-projection caches must not survive changed evidence, and
equal-clock campaign output must remain exactly equal to the uncached path.
**Why:** Profiling the 1,800-row campaign found about 56.7 million repeated ISO
timestamp parses inside the same deterministic replay. A 4,096-entry parser
cache removes redundant conversion without changing evidence or hiding stale
input, reducing the measured full-report path from 37.968 to 31.861 seconds.
Reusing each exact direct sample across direct/BTC-relative/ETH-relative feature
construction reduces it again to 30.171 seconds.
**Revisit when:** Observation clocks stop being immutable strings, the unique-
clock working set exceeds the bounded cache materially, or an incremental replay
contract can prove the same closed output more efficiently.

## 2026-07-22 - Keep human-review discovery independent of full campaign analytics
**Status:** accepted
**Decision:** `radar-review-timing-queue` obtains its generation inputs from a
closed v1 projection containing only canonical namespace, campaign-counting,
candidate-count, and final publication/operations receipt truth. The existing
queue builder remains responsible for exact source-generation revalidation and
action construction. At one evaluation clock, projection inputs and the final
queue must equal the comprehensive campaign-report path. The projection must
state `full_campaign_report_rebuilt=false` and must not invoke baseline,
episode, scorecard, or temporal-surprise analytics.
**Why:** Queue discovery needs receipt-backed idea identity, not the entire
empirical campaign analysis. On the current artifact-heavy store, the exact
projection reduced the path from 37.968 seconds to 3.174 seconds while
preserving all nine actions and zero-call/zero-write safety.
**Revisit when:** Queue eligibility or action construction genuinely needs a
new generation field. Extend the canonical projection and prove equal-clock
equivalence; do not restore an implicit comprehensive-report rebuild.

## 2026-07-21 - Keep outcome recovery independent of full campaign analytics
**Status:** accepted
**Decision:** Outcome-price recovery readiness, diagnostic collection, and
immutable capture default to a closed projection built from the exact current
pointer, countable candidate snapshots, campaign outcome ledger, and read-once
market-history snapshot. At an identical evaluation clock, its pointer and
outcome values must equal the comprehensive campaign report. It must identify
its bounded scope, report `full_campaign_report_rebuilt=false`, and never invoke
unrelated baseline, episode, review-queue, or temporal-surprise analytics. The
comprehensive campaign report remains the canonical whole-campaign surface and
is neither replaced nor inferred from this projection.
**Why:** Recovery needs one exact outcome gap and its source bindings, while the
whole-campaign builder also performs expensive empirical analytics. Rebuilding
those unrelated layers made the no-call readiness command take roughly 45
seconds; the exact projection completes in 2.61 seconds without changing its
request plan, pointer, outcome truth, authorization boundary, or safety state.
**Revisit when:** Recovery genuinely requires a new campaign field. Extend the
projection from the same canonical primitive and prove equal-clock equivalence;
do not restore an implicit whole-report rebuild.

## 2026-07-21 - Lead static execution readiness with selected-surface truth
**Status:** accepted
**Decision:** `radar-execution-quality-readiness` prints the bounded selected-
surface summary. `radar-execution-quality-readiness-full` retains the complete
static venue/cost catalog and `radar-execution-quality-readiness-json` retains
the closed structured packet. Direct Python CLI usage keeps full text as its
compatibility default. The summary must explicitly say it does not inspect live
authorization and must route to the separate current-authority Bybit readiness.
**Why:** The 169-line catalog buried the already-confirmed execution choice and
five remaining blockers, and the checked decision package still called its v22
source contract v20. Separate summary/full/JSON views make operator truth
readable without discarding feasibility or cost-model detail.
**Revisit when:** The selected surface changes or another versioned machine view
is required. Preserve the complete catalog and static/no-environment boundary.

## 2026-07-21 - Keep venue-native Bybit derivatives readiness concise
**Status:** accepted
**Decision:** The normal `radar-derivatives-bybit-readiness` Make target prints
a strict bounded summary of its execution-quality dependency, separate runtime
authorization, eligible instruments, exact four-context request plan, request
bounds, capture/freshness state, operator action, and context-only safety. Full
packet JSON remains available through
`RADAR_BYBIT_DERIVATIVES_READINESS_OUTPUT=json`; direct Python CLI usage retains
JSON as its compatibility default.
**Why:** The nested capture, instrument, and context arrays obscured the two
current blockers and safe dependency order. The concise view exposes them while
preserving the complete machine-readable packet and non-directional semantics.
**Revisit when:** A machine consumer needs another structured projection;
preserve JSON compatibility and fail closed on status, reasons, context-field,
instrument, or request-bound drift.

## 2026-07-21 - Keep direct Bybit intraday readiness concise
**Status:** accepted
**Decision:** The normal `radar-intraday-bybit-readiness` Make target prints a
strict bounded summary of its execution-quality dependency, separate runtime
authorization, eligible instruments, request bounds, capture/publication state,
RSI contract, operator action, and research-only safety. Full packet JSON remains
available through `RADAR_BYBIT_INTRADAY_READINESS_OUTPUT=json`; direct Python
CLI usage retains JSON as its compatibility default.
**Why:** The nested capture, instrument, and bar arrays in the compatibility
packet obscured the two current blockers and safe dependency order. The concise
view makes that order readable without changing or hiding the closed packet.
**Revisit when:** A machine consumer needs another structured projection;
preserve JSON compatibility and fail closed on status, reasons, interval,
instrument, or request-bound drift.

## 2026-07-21 - Keep Bybit execution readiness concise and current-authority-bound
**Status:** accepted
**Decision:** The normal `radar-execution-quality-bybit-readiness` Make target
prints a strict bounded summary of exact authority, authorization, eligible and
excluded coverage, current request bound, capture state, fail-closed policy,
operator action, and safety. Full packet JSON remains available through
`RADAR_BYBIT_EXECUTION_READINESS_OUTPUT=json`; direct Python CLI usage retains
JSON as its compatibility default. Static contracts retain the absolute
31-request ceiling but must not copy a volatile “current” universe count; the
readiness result owns that exact current-authority measurement.
**Why:** The prior 448-line packet repeated asset projections and buried the
actual blockers, while its checked-in 29-candidate statement became stale as
the authoritative universe changed. The concise view makes the safe next action
visible without weakening count reconciliation or hiding the full evidence.
**Revisit when:** A machine consumer needs another versioned structured view;
retain JSON compatibility and fail closed on any authority, coverage, or request
count drift.

## 2026-07-21 - Keep DefiLlama mapping review concise and explicit
**Status:** accepted
**Decision:** The normal
`radar-fundamentals-defillama-mapping-review` Make target prints a bounded
summary of exact authority, coverage, blockers, human action, and safety. Full
packet JSON remains available only through
`RADAR_DEFILLAMA_MAPPING_OUTPUT=json`; a separate `template` mode emits exactly
the intentionally invalid operator-registry template. Direct Python CLI usage
retains JSON as its compatibility default. Every mode remains read-only,
no-provider, non-inferential, and non-authoritative.
**Why:** The prior normal command duplicated the complete 30-asset universe in
both review and template sections, burying four blockers and the next action in
thousands of tokens. Separating summary, packet, and template views makes the
human identity-mapping task usable without weakening its exact-universe or
explicit-decision contract.
**Revisit when:** A confirmed operator workflow needs an explicit local template
writer. Any writer must be separately named and confirmation-gated, preserve
the exact universe digest, and never fill or infer a mapping automatically.

## 2026-07-21 - Keep changing campaign truth out of structural progress notes
**Status:** accepted
**Decision:** The Protocol-v2 current-progress projection and its checked-in
note own structural capabilities, accepted decisions, and unresolved activation
boundaries. They must not copy volatile campaign counts, asset identities,
outcome totals, or dashboard authority. Instead, the versioned projection
exposes the canonical campaign JSON/Markdown paths and exact local refresh
command without reading those files. The artifact-derived
`RADAR_LIVE_OBSERVATION_CAMPAIGN_REPORT` remains the single source for changing
measurement truth.
**Why:** Manually copied observations, coverage, episode counts, and missing
assets became stale after later successful cycles even while the canonical
campaign report remained correct. Separating stable structure from dynamic
measurement removes that contradiction and preserves the progress command's
zero-I/O, zero-provider safety contract.
**Revisit when:** A future unified status command reads a fingerprinted campaign
report through an explicit bounded read-only interface; it must still copy the
canonical values rather than re-evaluate or maintain a second counter set.

## 2026-07-21 - Keep strict publication schema-valid and global macro context-only
**Status:** accepted
**Decision:** Serialize each return leg's anchor-error range by applying the
nominal-horizon offset to its already-rounded realized-horizon range. Historical
shadow v5/v6 values produced by independent six-decimal rounding remain readable
when the affine identity differs by at most one microsecond plus a narrowly
defined binary-float epsilon; a two-microsecond difference remains invalid. A
full strict artifact doctor must promote every schema-validation error to a
blocker, exactly as schema-only strict mode and dashboard authority already do.
Non-strict diagnostic doctor runs may continue to report ordinary schema errors
as warnings. Daily Operations status must show the terminal provider-attempt
status and reason separately from the boolean provider-request result. A
calendar event without a specific, non-global token symbol remains in the
unified calendar as context/risk but must not enter the asset-specific scheduled-
catalyst artifact. New generations bind
`scheduled_derivation_scope=asset_linked_events_only` and an exact context-only
count; publication rederives both. Historical manifests without those fields
retain their closed legacy all-rows validation path rather than being silently
reinterpreted.
**Why:** A genuine CoinGecko cycle was retained but correctly rolled back from
publication when independently rounded medians differed by one microsecond.
That representational false negative should not discard valid evidence, while a
strict doctor must never give schema-invalid bytes a zero-blocker publication
stamp or make a successful HTTP request look like a provider failure. Assigning
a fake symbol to an official macro event would turn global risk context into
false asset-specific evidence and could manufacture directional research.
**Revisit when:** A future schema stores timing as integer microseconds or uses
one exact decimal representation end to end; migrate explicitly rather than
widening the tolerance. A separately versioned global scheduled-risk schema may
replace the context-only split only if it preserves non-directional semantics.

## 2026-07-21 - Measure baseline variation and return sampling before policy
**Status:** accepted as descriptive shadow evidence; no policy authority
**Decision:** Shadow temporal surprise v6 records distinct baseline-value count,
maximum and current-value tie counts, distinct-value ratio, and nominal finite-
sample rank floors using the method's existing 12-decimal derived-value
identity. Preserve every v1 activity and v2 signed-return calculation and keep
historical v1-v5 artifacts readable. Its v4 trace also binds exact feature-
specific value-only source tuples and records source-tuple repetition, derived-value
repetition, transform-collision loss, and consecutive source/derived runs.
Observation identity and clocks stay in the causal sample digest but are
excluded from the value-only tuple so distinct timestamps cannot mask repeated
numeric inputs. Do not infer provider fault or effective sample size, impose
a minimum-distinct threshold, or change readiness, degeneracy, ranks, robust
z-scores, routes, scores, or authority from these fields. Campaign-level
distributions may summarize projections meeting the model's existing nominal
sample minimum and retain exact extremes, but must keep historical campaign
schemas readable and must not turn a descriptive ratio into an exclusion rule.
Campaign audit v5 may group those reference-set diagnostics by canonical asset
and retain the observed symbol, provider, data mode, and feature-basis counts.
It may separately count source-tuple repetition and transform collision and
retain the exact latest trace digest/reference. Those fields are mathematical
input lineage only: they do not establish that a provider caused a tie,
distinguish quantization from legitimate low-motion behavior, classify an
asset, or justify exclusion. Keep exact observation references and overlapping-
sample caveats visible wherever the grouping is rendered.
Shadow v5 additionally binds the exact endpoint and anchor observation identity
and clocks for each return sample, including benchmark endpoints/anchors for
relative returns. It may report observation reuse, consecutive reuse, realized
horizon and anchor-selection error, benchmark alignment lag, and exact maximum
references without changing the v2 return values. Campaign audit v6 may
aggregate that timing trace per canonical asset and return feature while keeping
audit v1-v5 readable. Keep numeric source-tuple repetition, observation reuse,
and timing error separate. Do not infer independent sample count, provider
fault, a timing defect, or policy from any of them, and do not set a reuse/error
threshold, exclude an asset, or alter readiness, routes, scores, publication,
or Protocol-v2 eligibility.
Shadow v6 may use those same exact endpoint/anchor identities to describe
half-open return intervals, exact interval reuse, adjacent overlap, summed
duration, union clock coverage, overlap excess, and coverage ratio. Campaign
audit v7 may aggregate asset and benchmark legs separately and retain exact
coverage/overlap extremes while keeping audit v1-v6 readable. These fields do
not estimate effective sample size, change sample weights, create an exclusion,
or change a threshold, score, route, publication, or Protocol-v2 rule. In the
59-cycle replay, 5,214 of 8,262 asset reference sets and 3,434 of 5,442 benchmark
sets overlap adjacently, while exact full-interval reuse is zero; distinct
interval identity therefore must not be interpreted as independence. One-hour
sets have full unique-clock coverage, whereas the minimum observed 4h/24h
coverage ratios are `0.456072623081` and `0.126292698333` respectively.
**Why:** Nominal timestamp count can materially overstate information when a
provider repeats or quantizes activity values, and overlapping derived returns
can also tie. Recording that structure makes later calibration auditable
without opportunistically tuning the sparse live campaign.
**Revisit when:** Protocol v2 has frozen feature families and partitions plus
enough independent development episodes to predeclare and evaluate a
distinctness or effective-information rule without reading the untouched
holdout.

## 2026-07-20 - Make the human-review queue actionable without changing evidence
**Status:** accepted
**Decision:** Keep review-timing CLI status/queue JSON as the compatibility
default. The ordinary Make surfaces select a concise projection that preserves
counts, exact namespace/idea identity, route/bias/clocks, the confirmation-
gated next command, provider/write state, and all safety counters. Full JSON
remains available with `RADAR_REVIEW_TIMING_OUTPUT=json`. Both formats evaluate
the same receipt-backed queue and neither records a human action.
**Why:** The five current actions were hidden inside a large digest-heavy
payload. Human timing evidence is useful only when the operator can identify
and explicitly confirm the exact action without confusing queue inspection for
a view event.
**Revisit when:** The queue schema or human-review workflow is versioned. Any
replacement must keep explicit confirmation and must never infer attention from
dashboard or command reads.

## 2026-07-20 - Treat calibration and discovery control as separate shadow research
**Status:** accepted as research design; no implementation or policy authority
**Decision:** Keep the accepted anomaly-detector order unchanged. Study adaptive
thresholding, conformal score calibration, heavy-tail-aware changepoint
comparators, and online multiple-discovery control only as cross-cutting shadow
research after a causal score stream and its assumptions are closed. A current
descriptive rank is not a p-value. Freeze the hypothesis family/order, error
target, stopping rule, calibration reference sets, feedback clocks, and
dependence treatment before evaluation. Maintain an append-only trial ledger
and report time-indexed calibration, alert burden per operator day and episode,
and detection delay. Make no FDR, conformal-coverage, or confidence-sequence
claim unless the selected method's input and dependence assumptions are proven.
**Why:** A stronger detector can still overwhelm the operator or produce false
confidence when many dependent asset/horizon/time tests are viewed repeatedly.
Separating score construction from calibration and discovery governance makes
those failure modes measurable without tuning the sparse campaign.
**Revisit when:** Genuine point-in-time inputs, independent episodes, complete
outcomes, frozen partitions, and the Protocol-v2 annex are ready to specify and
evaluate exact numerical choices.

## 2026-07-20 - Keep Daily Operations JSON while making operator output concise
**Status:** accepted
**Decision:** Keep the Daily Operations CLI's default readiness/status output as
the full compatibility JSON. The normal Make surfaces select a concise,
allowlisted summary that exposes current authorization, call eligibility,
cadence, explicitly historical baseline warmth, prospective universe/regime/
partition/match coverage, dashboard/scheduler, source availability, latest
invocation, latest actual provider attempt, exact next command, and safety state. Operators
may set `RADAR_DAILY_OPS_OUTPUT=json` to recover the unchanged full payload.
Both modes refresh the same bounded current-status receipt and make zero
provider calls.
**Why:** The complete readiness object contains large per-asset baseline detail
that is valuable for machines but obscures the few facts needed for a safe
manual decision. A separate rendering choice improves operator truth without
forking evaluation or changing authorization.
**Revisit when:** A versioned external consumer requires a different stable
human-readable format or the compatibility JSON contract itself is revised.

## 2026-07-20 - Expose the complete episode taxonomy before choosing sample minimums
**Status:** accepted as descriptive evidence accounting; policy remains unsealed
**Decision:** Derive one closed Protocol-v2 episode coverage frontier from the
validated frozen Decision-v2 episode scorecard. Include every canonical route
and primary origin in canonical order, with explicit zero rows, and bind the
projection to the scorecard schema, contract digest, input-binding digest, and
evaluation time. Campaign reports and the read-only dashboard copy this value
without re-evaluating cohorts and fail closed on source or count drift. Forward
empirical live projections use schema v5 to preserve the same contract for
future Research Lab bundles, while schemas v1-v4 remain readable and the sealed
Protocol-v1 report bundle remains byte-identical. Treat a zero row strictly as
missing episode evidence. Do not infer minimum samples,
sample sufficiency, statistical or cross-asset independence, matched controls,
annex status, policy fitness, or route quality from this frontier, and do not
change routing, scores, thresholds, providers, or authority.
**Why:** Observed-only cohort tables made absent routes and origins easy to
overlook. The current genuine campaign has only three fixed-start episodes in
two routes and one primary origin; explicitly naming the other categories makes
the collection gap actionable without pretending sparse dependent observations
validate the engine.
**Revisit when:** The Protocol-v2 annex has sealed episode definitions,
partitions, untouched holdout, minimum samples, and dependency-aware analysis,
and enough new genuine episodes exist to evaluate the predeclared requirements.

## 2026-07-20 - Replay current regime inputs without rewriting campaign evidence
**Status:** accepted as operator diagnostic; no evidence or policy authority
**Decision:** The campaign report may read the exact normalized market-source
artifact for the one currently authoritative generation, but only after its
bytes, row count, namespace, run, revision, and operator digest reconcile with
the immutable manifest and current pointer. Re-run the closed control-regime
projection read-only and expose eligible/missing input counts plus bounded
canonical asset, symbol, rank, and field-level failure reasons. Keep historical
coverage derived solely from retained history. The replay must not write or
backfill history, call a provider, create a regime when the closed projection is
unavailable, feed Decision routing, select controls, assign a partition, or
grant Protocol-v2 evidence eligibility. Non-current generations do not carry a
current-authority replay.
**Why:** A historical coverage count of zero was correct but insufficiently
actionable: the exact current generation already had 28 of 30 causal 24-hour
inputs, with PUMP and WBT missing the value, unit, and evidence reference. A
source-bound diagnostic explains that concrete gap without silently converting
replay into persisted evidence.
**Revisit when:** The current campaign-report contract is versioned again, or a
sealed Protocol-v2 annex explicitly authorizes a separately validated use of
persisted regime evidence.

## 2026-07-20 - Retain a causal control-only market regime without exposing it to Decision policy
**Status:** accepted as prospective measurement; matched-control policy remains unsealed
**Decision:** After a successful live/no-send history enrichment, derive one
descriptive current-cycle regime only when the exact top-liquid set is complete,
all rows share the same observation clock, every rank is present, every row is
baseline-counted, and every row has closed `temporal_return_24h` evidence in
percent points. Compare the BTC 24-hour return with the full-universe median:
both positive is `risk_on`, both negative is `risk_off`, and every disagreement
or zero case is `mixed`. Bind the inputs by observation IDs and digest, then copy
the result only onto those exact retained-history observations. Do not expose it
to the current Decision rows, backfill older observations, read outcomes, assign
a Protocol-v2 partition, select controls, or change routes, scores, thresholds,
or publication authority. Incomplete input evidence records an unavailable
cycle result rather than inferring a regime.
**Why:** Matched non-idea controls require market context known at the same
observation clock. The causal temporal return is already available independently
of the provider sparkline alias; closing the whole-set regime now prevents future
evidence loss without letting a descriptive research field influence production
policy. The 2026-07-20 09:27 UTC provider failure correctly produced no retained
regime rows.
**Revisit when:** A successful post-implementation live cycle has been observed,
the Protocol-v2 partition rule is sealed before holdout access, and enough
independent complete rows exist for an outcome-blind matched-control review.

## 2026-07-20 - Preserve prospective control context in empirical live projections
**Status:** accepted; current sealed Protocol-v1 bundle remains immutable
**Decision:** New `decision_radar.empirical_live_campaign_projection` values
use schema v4. Copy the campaign's closed point-in-time control-context
readiness into the separate live/no-send observational lane only after exact
source schema, campaign-count reconciliation, per-field coverage, selection
field, and zero-side-effect validation. Preserve universe/liquidity coverage as
observed while leaving absent market-regime and Protocol-v2 partition coverage
at zero. Never backfill historical rows, inspect outcomes, select a matched
control, infer missing context, or grant routing, score, threshold, publication,
policy, or Protocol-v2 authority. Keep schema v1/v2/v3 readable and label a
missing older source field compatibility-unavailable. Do not rewrite the sealed
seven-file Protocol-v1 bundle or its hardening supplement; a v4-bearing bundle
requires a separate versioned publication and review.
**Why:** The campaign now preserves honest prospective top-liquid and
control-liquidity context, but the empirical projection previously stripped it.
Carrying validated coverage into Research Lab closes that truth loss while
showing exactly why matched controls are still unavailable.
**Revisit when:** Genuine point-in-time market-regime context is collected, the
Protocol-v2 partition rule is sealed before holdout access, and an outcome-blind
selector can be reviewed against complete rows without changing Decision policy.

## 2026-07-20 - Retain point-in-time universe context without backfilling history
**Status:** accepted as forward evidence collection; matched-control policy remains unsealed
**Decision:** Every newly normalized no-send market row records its exact
top-liquid membership, one-based volume rank, selected-set size, configured
limit, and selection policy. It also records a separate
`control_liquidity_tier` from the existing state-feature bucket and its basis.
Retained market history copies only explicitly supplied context; it never
derives or backfills these fields onto older immutable observations. Keep the
control bucket separate from the operator-facing `liquidity_tier`, so this
instrumentation cannot change tradability, routing, scores, or thresholds.
Readiness may measure field coverage but must not select controls, inspect
outcomes, assign Protocol-v2 partitions, or grant Protocol-v2 evidence status.
**Why:** Future matched non-idea controls and the exact Bybit instrument
intersection need the universe as it was known at each observation, not a
current ranking reconstructed later. Preserving that context prospectively
closes evidence loss without silently rewriting the existing campaign or
prematurely freezing the Protocol-v2 annex.
**Revisit when:** Genuine market-regime context is collected, the Protocol-v2
partition rule is sealed before holdout access, and an outcome-blind selector
can bind complete point-in-time rows to independent Decision episodes.

## 2026-07-20 - Carry causal coverage and explicit review truth only in forward empirical projections
**Status:** superseded by the 2026-07-20 schema-v4 control-context projection decision
**Decision:** New `decision_radar.empirical_live_campaign_projection` values
use schema v3. When the source campaign report contains the closed causal
temporal-surprise audit and both human-review summaries, copy their bounded
counts, feature coverage, source/digest lineage, and explicit latency-evidence
state into the separate live/no-send observational lane. Revalidate the causal
audit before projection, preserve every no-independence/no-policy/no-authority
flag, and require closed review queue and ledger accounting. Dashboard reads
never become human actions. Missing fields in older source reports become an
explicit compatibility-unavailable state, never a healthy zero. Continue to
read schema v1 and v2 projections. Do not rewrite the already sealed seven-file
Protocol-v1 report bundle or its immutable hardening supplement to adopt v3.
**Why:** The live campaign now measures causal feature readiness and exposes
receipt-backed ideas awaiting explicit review, but the empirical projection
previously stripped both. Copying validated truth closes that loss without
pooling live evidence with replay, manufacturing latency samples, or erasing
the immutable evidence boundary.
**Revisit when:** A separately reviewed, versioned empirical publication is
ready to supersede the current sealed bundle. It must preserve the existing
bundle and supplement bytes, retain backward readability, and bind the exact
campaign snapshot rather than silently refreshing a historical report.

## 2026-07-20 - Replay shadow temporal surprise causally without rewriting history
**Status:** accepted as read-only campaign measurement
**Decision:** Extend the existing canonical campaign report with one closed
`decision_radar.shadow_temporal_surprise_campaign_audit` projection built from
the report's already captured exact history snapshot. Replay only rows whose
canonical contract says `baseline_counted=true`; exclude rapid non-counted rows
and reject malformed or duplicate identities with closed accounting. Evaluate
each accepted row against strictly earlier same-asset history and canonical
BTC/ETH rows at or before its clock. Publish per-feature coverage, per-asset
summaries, a source-bound digest that changes with the exact history snapshot,
and a causal-value digest whose prior values remain stable when only later rows
are appended. For every feature, report deterministic min/p05/median/p95/max
robust-z and family-correct empirical-tail distributions over ready projections,
plus the exact observations at each extreme. Keep upper activity ranks separate
from two-sided signed-return ranks. Never interpret robust-z magnitude as a
calibrated probability, call a rank a p-value, or claim overlapping samples are
independent. Do not rewrite historical rows or grant routing, score, threshold,
publication, or Protocol-v2 authority.
**Why:** The isolated v2 implementation proved mechanics, but it did not show
how much of the genuine retained campaign can actually evaluate each feature or
where insufficient and degenerate histories remain. A deterministic causal
replay exposes that empirical coverage without tuning policy or creating a
second model.
**Revisit when:** A sealed Protocol-v2 annex defines dependence-aware episodes,
matched controls, partitions, sample minima, costs, and promotion criteria, and
genuine matured outcomes are sufficient for an out-of-sample comparison.

## 2026-07-20 - Extend robust temporal surprise with causal signed-return tails
**Status:** accepted as shadow-only research instrumentation
**Decision:** Advance `event_alpha.shadow_temporal_surprise` to schema v2 while
keeping historical v1 values readable. Preserve the existing log-median/MAD
volume and turnover comparison, and add separate direct and BTC/ETH-relative
1h, 4h, and 24h return families. Rederive percent-point returns only from
provider-observed prices with canonical benchmark identity, at-or-before causal
horizon anchors, and a bounded backward tolerance. Preserve sign with the
identity transform; report median/MAD robust z-scores plus add-one lower, upper,
and two-sided descriptive ranks. Treat overlapping observations as dependent,
call no rank a p-value, and fail closed on proxy bases, future or misaligned
clocks, insufficient history, identity drift, or degenerate MAD. Attach v2 only
to top-level post-scan market evidence with every routing, score, threshold,
publication, and automatic-application flag false.
**Why:** Signed crypto returns are heavy-tailed, so the canonical mean/standard-
deviation comparison needs an explainable robust challenger that preserves
direction and exact point-in-time lineage. Implementing the preregistered first
candidate as isolated instrumentation lets the campaign collect comparable
evidence without tuning sparse overlapping observations or changing trader-
facing truth.
**Revisit when:** Matured episode-level Decision outcomes and matched non-idea
controls support a frozen development/validation/untouched-holdout comparison
with dependence-aware uncertainty, coverage and degeneracy reporting, a sealed
Protocol-v2 annex, and a separate reviewed promotion decision.

## 2026-07-20 - Missing residual execution cost cannot become zero
**Status:** accepted as fail-closed offline mechanics; final policy remains unsealed
**Decision:** Fully rederive the exact Bybit decision-reference composite before
projecting any residual execution cost. Without an explicit residual-slippage
assumption, retain the known components but return no numeric all-in cost or net.
An optional sensitivity may supply separate non-negative decimal-text basis
points for entry and exit, applied to each leg's exact executed USDT value under
one causal effective window and distinct research-assumption lineage. Treat even
an explicit zero as unobserved sensitivity. Keep source authority,
beyond-visible-book policy, unavailable-cost policy, complete Protocol-v2 cost
status, annex binding, realized execution, and evidence eligibility false.
**Why:** Silently interpreting an unavailable cost as zero creates optimistic
backtest P&L, while inventing a generic penalty creates unsupported evidence.
The two-state contract lets the project test exact arithmetic and sensitivity
without confusing a research assumption with measured execution quality or
prematurely choosing the final annex rule.
**Revisit when:** Genuine immutable decision/submission/fill evidence supports a
residual-slippage model and the operator is ready to seal its source, estimation
window, missing-data rule, permitted bounds, target tiers, and Protocol-v2 annex.

## 2026-07-20 - Parse Decision Radar policy booleans semantically
**Status:** accepted
**Decision:** Market-anomaly classification, Decision catalyst policy,
integrated route policy, both Event Fade snapshot-construction boundaries,
source enrichment/LLM triage, incident projection/linkage, and persisted
watchlist lifecycle state must parse boolean-like control fields through an
explicit true vocabulary instead of Python object truthiness. Text values such
as `false`, `0`, `no`, and `off`, arbitrary nonzero numbers, and unrecognized
text cannot create a negative/disproven/not-required catalyst, post-event
state/failure, derivatives-availability claim, major-pair cap, completed move,
fade eligibility, confirmed catalyst, catalyst-search request, sector/quote
control, duplicate suppression, real/official/direct-mechanism source claim,
market-reaction/causal confirmation, incident relevance/validated-asset claim,
watchlist alert/material-change state, freshness cap, DEX new-pool claim, or
proxy/supply/RSI/technical fade confirmation. A derivatives representative
must carry a real non-empty mapping snapshot. Booleans are not numeric market
features and cannot become `1.0` confidence, source quality, price, funding,
positioning, liquidation, return, volume, liquidity, pool-age, supply, incident
market score, watchlist score, or RSI-score evidence.
**Why:** Python considers every non-empty string truthy and considers booleans
numeric. Untyped external or compatibility rows could therefore manufacture a
risk/fade classification, crowding state, priority bonus, or source-knownness
claim—or incorrectly cap a valid idea—even when their literal value said false.
**Revisit when:** A versioned upstream schema rejects these malformed types
before every classifier and downstream merge, and every compatibility path is
proven to enforce it.

## 2026-07-20 - Treat latency as signed decision-mid implementation shortfall
**Status:** accepted as offline arithmetic; reference sources and policy remain unsealed
**Decision:** Model one supplied entry and exit decision book from exact best
bid/ask, provider observation, local acquisition, explicit decision timestamp,
bounded source reference, and distinct lineage. Require each decision before
its later matching-engine execution book, require the exit reference after the
modeled position opens, and prohibit decision-reference lineage reuse across
references or execution books. Decompose decision-reference gross return into
signed midpoint drift and execution-book gross return, then join visible-book,
taker-fee, and funding costs only by fully rederiving every component. Latency
cost is positive when adverse and negative when favorable; never clamp it or
add spread a second time. Keep actual order submission/fill observation,
reference authority, latency policy, beyond-book slippage, unavailable-cost
behavior, annex binding, and Protocol-v2 evidence authority false.
**Why:** Measuring all costs from each execution book's own midpoint omits the
price movement between a human/system decision and that later book. Simply
adding the decision-to-execution price difference to the existing gross return
would double count. The closed implementation-shortfall identity makes the
benchmark explicit and preserves favorable as well as adverse movement without
pretending supplied books are realized execution evidence.
**Revisit when:** Genuine decision-time books, exact decision/submission/fill
clocks, and immutable capture pairs exist and the operator is ready to seal the
latency benchmark, allowed window, missing-evidence rule, and full cost annex.

## 2026-07-20 - Composite costs must rederive every supplied component
**Status:** accepted as offline arithmetic; full cost policy remains unsealed
**Decision:** Combine Bybit visible-book drag, taker fees, and holding-interval
funding only when the fee and funding projections can both be fully rederived
from the same exact round trip and compare equal to their supplied values.
Calculate fees from each side's actual executed quote value, not target notional
or a mirrored long/short assumption. Preserve signed funding cash flow and
reconcile one native-USDT gross-to-net identity. Label the modeled component set
complete only for visible-book plus supplied unsealed taker fee plus supplied-
schedule funding. Keep latency, beyond-book slippage, unavailable-cost behavior,
source authority, final cost-model completeness, annex binding, and evidence
eligibility false.
**Why:** Correct component formulas do not prevent integration drift. A fee or
funding projection from a different round trip—or a fee reused across reversed
book sides—can produce a plausible but false all-in return. Full component
rederivation closes that deterministic gap without selecting empirical policy.
**Revisit when:** Genuine capture pairs and authoritative fee/funding evidence
exist and the operator is ready to seal latency, slippage, unavailable-cost,
style, tier, and source rules in the Protocol-v2 annex.

## 2026-07-20 - Reconcile funding over an exact supplied settlement schedule
**Status:** accepted as offline arithmetic; schedule and source authority remain unsealed
**Decision:** A Bybit funding-interval scenario must name one causal bounded
schedule source covering the modeled position and provide the expected funding
timestamps in strict order. The supplied settlement events must match that
sequence exactly; omissions, duplicates, additions, reordering, timestamps at
the entry/exit boundaries, and more than 256 events fail closed. Aggregate each
event using the already accepted signed-settlement formula and reconcile the
total cash flow to visible-book P&L. Label the result complete only relative to
the operator-supplied expected schedule. Keep authoritative holding-interval
coverage, schedule/rate/mark source sealing, realized execution, and
Protocol-v2 eligibility false.
**Why:** Summing independently valid settlement calculations is insufficient if
the expected event set is not explicit. Bybit funding intervals are symbol-
specific, so a missing or duplicated settlement can silently bias modeled P&L.
Exact schedule/event reconciliation closes that arithmetic failure mode without
pretending current instrument metadata proves the historical schedule.
**Revisit when:** Genuine point-in-time instrument schedules, settled rates, and
authoritative settlement marks have immutable capture and the final Protocol-v2
holding-period funding policy is ready for human sealing.

## 2026-07-20 - Relative-return values and feature bases must agree
**Status:** accepted
**Decision:** When causal temporal history supplies a canonical BTC- or
ETH-relative return, label that field and the `relative_strength` feature group
as `benchmark_derived_temporal_history` before market-quality projection. Do
not leave an observed canonical relative value labeled `unavailable`. If an
independently supplied canonical relative return already has a stronger basis,
preserve that value and basis; retain the temporal calculation only as a
separately named diagnostic. Missing or future benchmark evidence remains
unavailable and must not create a direct-feature claim.
**Why:** The temporal layer previously added valid relative-return values after
normalization had already labeled the feature group unavailable. Downstream
quality counts and operator provenance therefore understated direct evidence
despite retaining the exact benchmark inputs.
**Revisit when:** A versioned field-by-field feature graph replaces the current
group basis. The replacement must still forbid value/basis contradictions and
preserve canonical-source precedence.

## 2026-07-20 - Model funding as a signed settlement transfer
**Status:** accepted as offline arithmetic; sources and holding policy remain unsealed
**Decision:** For one supplied Bybit USDT-perpetual funding settlement, compute
position value as exact base quantity times the supplied settlement mark price,
then apply the supplied decimal-text fractional rate. Positive funding transfers
from longs to shorts; negative funding transfers from shorts to longs. Report
position cash flow as positive when received and negative when paid, and
reconcile that signed transfer to the modeled visible-book P&L. Require the
settlement strictly inside the modeled position interval plus bounded separate
rate/mark references, causal source clocks, and lineages. Do not claim complete
holding-interval coverage, an exact settlement mark, genuine source evidence,
realized execution, or Protocol-v2 eligibility.
**Why:** The venue formula and direction are deterministic, but the current
derivatives context has settled rates without the historical mark price needed
for an exact funding fee. Applying a current mark retrospectively—or treating a
one-minute kline close as exact—would create false precision. A pure supplied-
input projection closes arithmetic and sign handling while keeping the missing
evidence visible.
**Revisit when:** A genuine capture preserves every funding event and its
authoritative settlement-time mark over a proposed holding interval, and the
operator is ready to seal interval inclusion, source authority, and funding
treatment in the Protocol-v2 annex.

## 2026-07-20 - Apply immediate-book fees as explicit taker scenarios
**Status:** accepted as offline arithmetic; fee source and Protocol-v2 policy remain unsealed
**Decision:** Treat every complete immediately marketable visible-book walk as
taker liquidity, including a limit order that executes immediately. A research
fee scenario may apply separate caller-supplied decimal-text fractional rates
to the exact executed USDT value of the entry and exit legs. Require a bounded
public-documentation or named research-assumption reference, explicit lineage,
and one effective window covering both provider-observed leg times. Preserve
fee-only, visible-book-only, and combined cost identities; never add spread
again, model a maker fill from an immediate walk, infer an account rate, or
claim realized execution. The projection stays source-unsealed, annex-unbound,
and Protocol-v2-ineligible.
**Why:** Order placement type does not determine maker/taker status: an
immediately executing market or marketable-limit order removes liquidity. The
two-book model already had exact executed quote values but exposed no safe way
to apply fees, inviting either maker/taker confusion or fees calculated from a
target notional instead of the actual modeled legs.
**Revisit when:** The operator seals the final fee source/rates, effective
window, entry/exit execution style, target tiers, and complete Protocol-v2 cost
annex. A maker scenario requires a separate fill-probability and queue-position
contract rather than reuse of the immediate book walk.

## 2026-07-20 - Build round-trip evidence only from two exact immutable captures
**Status:** accepted as a read-only capability; not Protocol-v2 evidence until annex-bound
**Decision:** A capture-backed Bybit round trip must name exact entry and exit
capture namespaces and must never infer either from the latest pointer. Open
one verified artifact-base descriptor and both no-follow namespace descriptors
before reading either bundle, retain them through the full dual read, and
rederive both bundles from exact raw catalog and order-book responses. Require
distinct, non-overlapping capture windows, completion-fresh input-quality sets,
one exact shared native instrument, and independently preserved hashes, clocks,
lineages, constraints, and source authority. The resulting projection remains
read-only, annex-unbound, and Protocol-v2-ineligible.
**Why:** The per-leg arithmetic was closed, but a future operator could still
pair partially validated rows, guess a moving latest pointer, reuse one catalog,
or mix captures across a root/namespace swap. Exact dual-descriptor evidence
turns immutable provider bytes into reproducible round-trip inputs without
claiming execution or empirical authority.
**Revisit when:** Two genuine strict-clean captures exist for a human-confirmed
instrument and the Protocol-v2 annex is ready to bind their IDs, target sizes,
entry/exit styles, fees, funding, latency, slippage, and unavailable-cost rule.

## 2026-07-20 - Revalidate dynamic Bybit constraints at each round-trip leg
**Status:** accepted as an offline correctness contract; Protocol-v2 policy remains unsealed
**Decision:** A quantity-reconciled Bybit round trip must bind separate,
distinct-lineage instrument-catalog snapshots to entry and exit. Entry
constraints must be causal to the entry book. Exit constraints must be
observed after entry, use a different lineage, and remain causal to the exit
book. Both snapshots must identify the same exact native instrument, but their
dynamic values may differ. The common base quantity must align to both
`qtyStep` values and satisfy each leg's own minimum quantity, market/limit
maximums, and visible-quote minimum. Report order-style eligibility per leg and
their same-style intersection without selecting a style or requiring both legs
to use the same style.
**Why:** Bybit explicitly treats order maxima as dynamic. Reusing the entry
catalog for a later exit can falsely claim that a quantity remains admissible,
while forcing one timeless value would discard valid observed changes. Per-leg
evidence preserves causal operator truth without inventing an order policy.
**Revisit when:** The first genuine entry/exit capture exists and the Protocol-
v2 annex is ready to seal catalog freshness, allowed constraint changes,
entry/exit order styles, size tiers, and unavailable-cost behavior.

## 2026-07-20 - Size a supplied Bybit target by conservative venue-step floor
**Status:** accepted as an offline capability; not yet sealed as Protocol-v2 policy
**Decision:** A caller-supplied native-USDT target may be interpreted only as an
entry-mid reference. Derive the exact mid from the causal entry book, floor the
implied underlying-token quantity to the instrument's current `qtyStep`, never
exceed the supplied mid-notional, and require the shortfall to remain below one
step notional. Enforce the same catalog-bound minimum quantity, minimum
notional, dynamic market/limit maxima, clocks, lineage, and identity before
joining the derived quantity to the exact entry/exit book walk. Explicitly
state that the target is not a quote-spend budget because marketable spread and
depth can make an entry buy spend more or an entry sell receive less. Do not
select the final USDT tier set, adopt this floor rule as Protocol-v2 policy, or
choose an order style without the sealed annex.
**Why:** The quantity-reconciled primitive still required a manually supplied
base quantity. A deterministic, conservative target projection closes that
arithmetic gap without inventing final research sizes or confusing mid-
notional normalization with executable quote value.
**Revisit when:** The exact instrument set and genuine books exist and the
operator is ready to approve the final tier set, rounding/admissibility policy,
order style, and complete cost annex.

## 2026-07-20 - Bind Bybit quantity constraints to the exact catalog capture
**Status:** accepted
**Decision:** Every selected Bybit USDT-linear perpetual must preserve
`qtyStep`, `minOrderQty`, `maxOrderQty`, `maxMktOrderQty`, and
`minNotionalValue` from the same complete instrument-catalog response. The
quantity-reconciled visible-book model must reject a quantity below the minimum,
above both market and limit maxima, or below the minimum visible quote value on
either entry or exit. It must report market and marketable-limit quantity
eligibility separately without choosing an order style. Bind the catalog
observation clock and lineage causally before the entry book, and revalidate
the dynamic maxima on every future capture. Keep constraint freshness, USDT-
tier sizing/rounding, and entry/exit order style unsealed until the Protocol-v2
annex is approved.
**Why:** A `qtyStep`-aligned quantity can still be rejected by the venue. Bybit's
official instrument contract exposes the other size/notional limits and warns
that maximum quantities change over time. Preserving the exact catalog values
closes false admissibility while avoiding a fabricated order-style or timeless
limit assumption.
**Revisit when:** The first genuine catalog/book capture exists and the annex is
ready to seal its constraint-freshness window, exact size tiers/rounding, and
market versus marketable-limit policy. No captured maximum may be treated as a
permanent venue constant.

## 2026-07-20 - Reconcile Bybit round trips by exact underlying-token quantity
**Status:** accepted
**Decision:** For the selected Bybit USDT-linear perpetual surface, model a
visible-book round trip only by walking two distinct fresh order-book snapshots
with the same exact positive quantity aligned to the instrument's `qtyStep`.
Bybit's current USDT-contract documentation defines this contract quantity in
the underlying token. Longs buy then sell that quantity; shorts sell then buy
it. Report each leg's mid-referenced impact, gross mid-mark return, net visible-
book return, total USDT drag, and drag in basis points of entry-mid notional.
Never add standalone spread to those side walks. Reject stale, reused,
misordered, identity-mismatched, step-misaligned, or depth-insufficient inputs.
Keep this primitive research-only and explicitly not realized execution.
**Why:** Equal numeric USDT buy and sell lookups can represent different asset
quantities and cannot be summed into an exact round trip. Quantity identity
closes that mathematical defect while retaining native USDT cost accounting and
the exact entry/exit clocks needed for later Protocol-v2 evidence.
**Revisit when:** The Protocol-v2 annex is ready to seal size selection and
rounding from USDT tiers, entry/exit order style, fee source, impact application,
beyond-book slippage, funding, latency, unavailable-cost behavior, and exact
capture IDs. The primitive alone does not seal or activate that cost model.

## 2026-07-19 - Quantitative source-size limits are advisory only
**Status:** accepted; supersedes prior file/function/class line-count blocker
policies
**Decision:** Retain file, function, class, and transitional-core line counts
as static maintenance telemetry, but never block development, architecture
cleanliness, or release because a quantitative threshold was crossed. Do not
split cohesive code solely to satisfy the historical 75/150/1,200/1,500/2,000/
3,000-line references. Continue enforcing non-size module ownership, canonical
imports, naming, paths, schemas, security, and safety boundaries.
**Why:** Mechanical splitting to remain below arbitrary counts was consuming
implementation effort and could make behavior-critical boundaries harder to
follow. Cohesion, correctness, testability, and explicit ownership are better
reasons to split code than a raw line total.
**Revisit when:** Only if measured defects or review failures show that a
specific cohesive boundary needs restructuring. Any future quantitative limit
requires a new explicit owner decision; it must not be inferred from the
retained historical inventory.

## 2026-07-20 - Grow the immutable audit inventory without removing its safety ceiling
**Status:** accepted
**Decision:** Raise the project artifact root and optional history inventory
capacity from 4,096 files / 1.5 GiB to 8,192 files / 3 GiB. Keep the inventory
descriptor-anchored and fail closed when either new ceiling is crossed. Keep
the independent 512-file / 384 MiB standard-review selection and 128 MiB
single-artifact bounds unchanged. Report current inventory count, ceiling, and
headroom on every successful standard export. Never delete or move immutable
audit history merely to make the export pass.
**Why:** The fifty-second live/no-send cycle brought the legitimate immutable
root to 4,109 files, thirteen above the original capacity. The failure was a
retained-audit file-count ceiling, not a source-code line-size rule or an unsafe
selected ZIP. A bounded next tier preserves TOCTOU/resource-exhaustion defense
while providing honest operational headroom.
**Revisit when:** Inventory approaches 8,192 files or 3 GiB, export latency
becomes operationally material, or an explicit retention policy is approved.
Prefer a separately manifested non-destructive history tier; do not silently
remove evidence and do not convert these security/resource bounds into
unbounded scans.

## 2026-07-19 - Do not infer an account fee from Bybit's public table
**Status:** accepted
**Decision:** Treat Bybit's public trading-fee table as product documentation,
not as an account- or symbol-authoritative Protocol-v2 cost input. The
authenticated account fee-rate endpoint is outside the confirmed public-market-
data-only boundary and must not be called without a separate explicit private-
data authorization. Before Protocol v2 is sealed, the owner must choose either
a dated fixed research fee assumption or a separately authorized exact fee
source, then also seal entry/exit order style, USDT notional tiers, spread and
visible-book impact application, beyond-book slippage, funding treatment,
latency cost, and unavailable-cost behavior. Do not invent a numerical fee.
**Why:** Official Bybit documentation says actual rates can depend on region and
account tier, while the exact fee endpoint requires authenticated account
access. Copying a generic table value into the empirical cost model would look
more precise than the evidence and would silently cross the accepted public-
only scope if replaced with account data.
**Revisit when:** The owner explicitly approves the complete Protocol-v2 cost
policy or separately authorizes credentialed fee-rate acquisition. Preserve the
native-USDT values and the exact source/effective clock either way.

## 2026-07-19 - Keep the primary Bybit cost surface native to USDT
**Status:** accepted
**Decision:** Seal native USDT as the currency unit for the primary Bybit
USDT-linear-perpetual Protocol-v2 cost surface. Preserve spread and impact in
basis points and currency-valued depth, notionals, fees, funding, and P&L in
USDT. Do not relabel USDT as USD or assume a 1:1 conversion. Any future
cross-venue USD projection needs a separately sealed conversion source,
observation clock, freshness rule, and policy and cannot replace native Bybit
evidence. The selected Bybit capability and snapshot projection must therefore
use native `*_usdt_*` depth and notional-impact fields; generic `*_usd_*` fields
remain an inactive future interface and are not selected evidence. This unit
boundary also preserves the normalizer's mid-price reference: each side impact
already includes its crossing half-spread, so standalone spread must not be
added to the same side impact. A round trip still requires separate entry and
exit snapshots and a later sealed application policy. Buy size is exact USDT
spent and sell size is exact USDT proceeds, so equal numeric lookups are not
the same base position; quantity reconciliation must remain explicit and
unsealed until implemented. This unit decision does
not seal fees, order style, notional tiers,
slippage, funding treatment, latency cost, unavailable-cost handling, or the
final Protocol-v2 annex.
**Why:** The accepted venue decision and normalizer already preserve USDT and
forbid silent USD equivalence, while static readiness still reported the same
unit policy as unresolved. Keeping that stale blocker made operator truth
contradict its source contract. Native quote accounting is the conservative,
reconstructible choice and removes no missing market or cost evidence.
**Revisit when:** A future protocol deliberately adds a cross-venue reporting
currency. It must retain the original native-USDT values and bind the exact
conversion source and clock rather than rewriting historical evidence.

## 2026-07-19 - Generated North Star owns evidence-cycle authority truth
**Status:** accepted
**Decision:** The Event Alpha North Star generator must own the complete
`evidence_cycle_operator_authority` value and its Markdown rendering. The
checked JSON, Markdown, and burn-in artifacts must be exactly reproducible by
the generator from their recorded generation clock. Do not maintain a manual
operator-authority section that disappears during the explicit
`event-alpha-radar-north-star` authoring target.
**Why:** The checked contract correctly distinguished profile capability from
current authorization and recorded zero-side-effect readiness, but that value
had been inserted only into the generated artifacts. Regeneration therefore
silently removed safety-critical provider-boundary truth while still exiting
successfully. One generator-owned projection plus an exact checked-artifact
regression makes drift visible before it can be committed.
**Revisit when:** A versioned North Star schema replaces this generator. The
replacement must preserve the same exact generated-artifact reproducibility and
must not weaken the explicit-authorization, no-fixture-fallback, no-send, or
zero-call readiness contract.

## 2026-07-19 - Bind Bybit runtime timeouts and book freshness to finite policy
**Status:** accepted
**Decision:** Every guarded Bybit REST collector must reject a timeout unless
it is a finite non-boolean real number greater than zero and no more than 30
seconds, before crossing a provider boundary. The execution-quality order-book
normalizer must use the declared 15-second freshness threshold exactly; it may
not accept an alternate runtime threshold unless a future schema explicitly
persists and validates that policy through live summary, capture, doctor, and
Protocol-v2 binding.
**Why:** Boolean and non-finite values can pass ordinary numeric comparisons,
and an infinite threshold can label arbitrarily old evidence fresh. The current
snapshot projection does not carry a caller-selected threshold, so accepting
one would make freshness impossible to reconstruct from immutable evidence.
One fixed, finite policy keeps the selected Bybit surface deterministic and
fail-closed without changing authorization or making a provider call.
**Revisit when:** A versioned evidence schema deliberately supports multiple
freshness policies and binds the selected finite threshold through every raw,
normalized, capture, status, doctor, annex, and downstream Decision surface.

## 2026-07-19 - Multi-leaf bundles fail closed without pathname rollback
**Status:** accepted
**Decision:** The shared anomaly/scheduled-catalyst bundle publisher must fully
persist every private no-follow stage while retaining its descriptor, then
publish new leaves with native Darwin/Linux atomic no-replace semantics and
replace already-bound regular leaves with descriptor-relative atomic rename.
It may report success only after every final named leaf still matches the exact
staged inode and bytes, guarded leaves remain unchanged, and the namespace path
still names the opened directory. This is a leaf-atomic, generation-fail-closed
contract, not a claim of portable all-or-nothing multi-file transactionality.
After any failure, do not rename, unlink, or roll back mutable pathnames; retain
any partial public prefix and private stages as non-authoritative evidence and
require the caller's completion receipt/strict doctor before trust. Optional
empty calendar-unlock outputs must be omitted from the original bundle rather
than written and subsequently deleted.
**Why:** The former backup/install/rollback sequence could overwrite or delete
a same-user replacement during backup cleanup or rollback, and its closed stage
descriptors allowed a pathname substitution before publication. POSIX does not
offer a portable atomic transaction over several visible leaves. Descriptor-
bound stages plus non-destructive failure handling prevent false success and a
second unsafe mutation; generation receipts and doctors already provide the
correct authority boundary for incomplete bundles.
**Revisit when:** Bundle consumers move to one versioned directory or manifest
pointer that can be switched in a single native operation, with an explicit
retention policy for superseded directories and equivalent macOS support.

## 2026-07-19 - Shared artifact writers fail closed on staging substitution
**Status:** accepted
**Decision:** Shared immutable and replaceable artifact-byte writes must create
one private no-follow stage, keep its descriptor open, read back the exact
bytes, and verify the descriptor-bound inode against the final named leaf after
publication. Immutable leaves use native Darwin/Linux atomic no-replace rename
and fail closed when that primitive is unavailable. Replaceable control-state
leaves use descriptor-relative atomic rename and the same final byte, inode,
snapshot, regular-file, and single-link checks. Never unlink a failed or raced
temporary pathname by name. Retain the observed residue as non-authoritative
and report failure; strict caller fingerprints and doctors remain required
before any resulting artifact can become trusted.
**Why:** Closing a staging descriptor before publication allowed a same-user
pathname substitution to publish different bytes while the writer returned
success. Check-then-unlink cleanup could then delete an unowned replacement.
Holding the descriptor and verifying after rename eliminates false success,
while non-destructive failure handling avoids turning a detected race into a
second unsafe mutation. The contract deliberately does not claim that a
same-user-writable directory cannot be changed after the check.
**Revisit when:** A portable descriptor-native replacement and conditional
unlink primitive can strengthen the boundary without weakening macOS support
or deleting a pathname whose identity changed. Sequential multi-leaf bundle
transactionality remains a separate design problem and is not implied here.

## 2026-07-19 - Keep Tokenomist fixture capture separate from live unlock authority
**Status:** accepted
**Decision:** Tokenomist v5 may have a strict immutable synthetic-fixture
capture and doctor that prove exact response/request preservation,
normalization, units, clocks, coverage, and artifact-chain mechanics. Run that
proof only in a disposable root and publish no latest pointer. A separate
readiness surface may inspect one dedicated boolean authorization flag, but it
must remain blocked even when present until the owner approves an applicable
subscription, retention and redistribution terms, a bounded live transport,
health/backoff, and genuine immutable bytes. Never inspect the API credential
from readiness. Do not place genuine Tokenomist bytes in git or the standard
review archive, and do not treat fixture proof as source, campaign, dashboard,
directional, policy, or Protocol-v2 authority.
**Why:** A closed fixture capture can expose serialization, identity, unit, and
TOCTOU defects without crossing a paid provider boundary. It cannot prove that
the owner may acquire or redistribute genuine bytes, that a project-owned
request succeeded, or that a partial first page covers the requested window.
Keeping those claims separate prevents an offline contract test from
impersonating authoritative structured-unlock coverage.
Interrupted or raced fixture staging is retained under a unique `tmp_`
quarantine name rather than deleted through a mutable pathname; successful
publication uses a native atomic no-replace boundary, and any retained-write
result reports its observed inventory instead of claiming no I/O.
**Revisit when:** The owner explicitly selects and authorizes a suitable
Tokenomist subscription, approves retention/export treatment, and approves a
bounded no-send live transport with immutable request/response evidence and
provider health controls. Full multi-page coverage requires its own closed
request sequence and completion proof.

## 2026-07-19 - Keep operator-imported liquidation transcripts non-authoritative
**Status:** accepted
**Decision:** A local Bybit liquidation transcript may immutably preserve and
rederive exact operator-supplied subscribe, acknowledgement, and observed data
application payloads, but it must publish no latest pointer and claim only
`observed_messages_only` coverage. It cannot claim project-owned transport,
TLS/WebSocket framing, uninterrupted stream continuity, absence of dropped
messages, or absence of liquidations during silence. Keep every such capture
campaign-, dashboard-, policy-, direction-, input-quality-, and Protocol-v2-
detached even when its internal artifact package validates cleanly.
Publish the final namespace only with native Darwin/Linux atomic no-replace
semantics and fail closed when that primitive is unavailable. Never clean up a
failed stage or post-publication identity drift by unlinking, removing, or
renaming a mutable pathname. Retain the exact unique
`tmp_bybit_liquidation_stage_*` tree as quarantine, classify it from the root
without injecting lifecycle files, exclude it from the standard review ZIP,
and preserve it only in the optional history complement.
**Why:** Exact application bytes and deterministic normalization are useful
audit evidence, but an operator-supplied fragment cannot prove the transport or
continuous bounded observation window needed for empirical liquidation rates.
Calling it authoritative would turn unknown collection gaps into false market
evidence. Ordinary directory rename may replace a concurrently created empty
destination, while check-then-delete cleanup can remove an unowned replacement;
native no-replace plus non-destructive quarantine closes both mutation paths.
**Revisit when:** A separately authorized, permitted, project-owned listener can
seal a genuine bounded window with connection, heartbeat, disconnect, and
continuity evidence. It must stop on the recorded Bybit restriction and may not
use a proxy, VPN, alternate regional host, or secondary provider to conceal a
native-source failure.

## 2026-07-19 - Preserve provider-attempt truth across later skipped invocations
**Status:** accepted
**Decision:** Persist the latest terminal Daily Operations invocation and the
latest terminal invocation that crossed the provider boundary as separate
facts. A later cadence skip, authorization block, or readiness block may become
the latest invocation but must not replace the preceding provider attempt's
cycle, namespace, attempted/terminal clocks, terminal status, reason, or request
outcome. Treat the provider-attempt projection as one closed optional group;
partial state fails validation. Historical state may use the bounded immutable
cycle journal as a read-only display fallback and must not be rewritten merely
to improve dashboard wording.
**Why:** “Last cycle” previously changed from a genuine DNS/provider failure to
“cadence waiting” when the operator safely re-entered the command. The campaign
journal remained correct, but the primary health surface obscured the failure
that explains why the cadence reservation exists.
**Revisit when:** A versioned state contract replaces the optional compatibility
group. It must retain the two independent timelines and exact journal binding;
it may remove the legacy fallback only after all supported authority states
carry the closed projection.

## 2026-07-19 - Keep Bybit liquidations as a separate native stream contract
**Status:** accepted
**Decision:** Protocol-v2 liquidation context for the selected Bybit
USDT-linear perpetual surface must come from exact public
`allLiquidation.{instrument_id}` WebSocket messages. Preserve message bytes,
instrument identity, provider event/message/receipt clocks, provider side,
documented liquidated-position semantics, base-asset size, bankruptcy price,
and USDT notional. The existing REST funding/open-interest/positioning bundle
does not imply liquidation coverage, and Coinalyze cannot substitute for native
Protocol-v2 evidence. The offline normalizer alone grants no live-listener,
authorization, aggregation, directional, or evidence authority. Detached
operator-import persistence, when present, remains governed by the separate
non-authoritative transcript decision above.
**Why:** Bybit exposes all-liquidation events through a public WebSocket rather
than the V5 REST market catalog. Collapsing the surfaces would report a required
field as covered when no native liquidation observation was collected.
**Revisit when:** A separately authorized, reachability-proven listener can
seal immutable exact messages into a human-approved window/aggregation annex.
It must remain no-send/no-trade and must not use a proxy, VPN, alternate region,
or secondary provider to conceal a native-source failure.

## 2026-07-19 - Explicit evaluation clocks fail closed
**Status:** accepted
**Decision:** When a caller explicitly supplies the research/evaluation clock
used for candidate timestamps, delivery timestamps, freshness, or context age,
require it to parse as a valid datetime. Do not replace a malformed supplied
clock with wall time. Booleans, non-finite numerics, and out-of-range epochs are
never timestamps. A wall-clock default is permitted only when the optional
clock is genuinely absent.
**Why:** Substituting `now` manufactures point-in-time recency, while Python's
boolean-as-integer behavior can silently create 1970-era provider evidence.
Both make provenance depend on type coercion rather than recorded source truth.
**Revisit when:** A versioned schema makes every evaluation and provider clock
mandatory. Then remove absent-clock defaults and retain the same strict parser.

## 2026-07-19 - Malformed market clocks never become current time
**Status:** accepted
**Decision:** Resolve market observation clocks by ordered presence. A supplied
but invalid higher-authority clock fails closed and cannot borrow a lower alias
or the current wall clock. A timestamp can imply freshness only after it parses
as an actual aware observation time. Wall-clock fallback remains limited to the
legacy case where no optional clock was claimed at all.
**Why:** Replacing malformed evidence with `now` manufactures recency and can
extend a catalyst-search deadline from an unauditable origin.
**Revisit when:** A versioned schema makes every observation clock mandatory.
At that point, remove the missing-clock fallback rather than weakening the
malformed-clock rejection.

## 2026-07-19 - Current crowding routes require fresh derivatives
**Status:** accepted
**Decision:** Treat derivatives crowding as current Decision evidence only when
the highest-authority canonical derivatives snapshot is a mapping and its
ordered freshness status is recognized as fresh. Stale, missing, unknown,
malformed, or alias-hidden snapshots cannot raise derivatives confirmation,
remove the fade confirmation penalty, or select Fade / Exhaustion Review.
**Why:** Open interest, funding, positioning, and liquidation conditions decay
quickly. A historical crowding label is useful context but cannot justify a
current perp-oriented operator route.
**Revisit when:** A versioned provider-clock contract supplies per-component
acquisition age plus full-set completion freshness. It must be at least as
strict as the current recognized-fresh gate and preserve stale context only as
non-routing history.

## 2026-07-19 - Verified spread requires recognized freshness
**Status:** accepted
**Decision:** A numeric spread can be classified as verified only when the
highest-authority supplied spread/order-book/market freshness status is a
recognized fresh state. Missing, unknown, unavailable, malformed, or non-string
freshness makes spread unavailable; stale, expired, invalid, or future status
makes it stale. An invalid higher-authority status cannot fall through to a
lower `fresh` alias.
**Why:** Best bid/ask without a trustworthy acquisition clock is not current
execution-quality evidence. Treating a malformed or absent freshness status as
verified can structurally unlock actionable/rapid routes with an old quote.
**Revisit when:** A versioned execution-quality schema replaces string status
fields with a validated provider-clock contract. That contract must remain
fail-closed and prove acquisition age before spread verification.

## 2026-07-19 - Accepted evidence counts are closed integers
**Status:** accepted
**Decision:** Treat `accepted_evidence_count`, `rejected_evidence_count`, and
equivalent scalar count fields as non-negative finite integers. Reject
booleans, fractional values, numeric strings, negative values, NaN, and
infinity. An invalid count contributes no evidence and cannot improve catalyst
status, source specificity, anomaly priority, integrated scoring, or source
eligibility.
**Why:** Truthiness and permissive float/int conversion let values such as
`true`, `0.5`, `"1"`, and infinity stand in for an accepted evidence row. That
manufactures catalyst confidence without a corresponding immutable source.
**Revisit when:** Never for canonical count fields. A legacy importer may
convert a documented historical representation before canonical evaluation,
but must preserve its original bytes and emit an explicit conversion audit.

## 2026-07-19 - Invalid canonical Decision numerics cannot borrow aliases
**Status:** accepted
**Decision:** For ordered numeric fields and nested market snapshots used by
Decision scoring, timing, tradability, and spread policy, fall through to a
compatibility value only when the higher-authority field is absent or otherwise
does not claim that measurement. An explicitly supplied boolean, non-numeric,
NaN, infinite, or unit-invalid canonical value owns that slot and resolves to
unavailable; normalization and merging must not expose a valid-looking older
value beneath it.
**Why:** A malformed current spread, liquidity measurement, volume statistic,
or return can otherwise be hidden by an older representation and incorrectly
improve a score, freshness interpretation, or operator route.
**Revisit when:** A versioned schema removes every duplicate representation and
rejects malformed canonical rows before Decision evaluation. The fail-closed
rule remains required at that ingestion boundary.

## 2026-07-19 - Bind temporal statistics to their exact input observations
**Status:** accepted
**Decision:** Every temporal scalar, return, volatility, and benchmark-relative
feature must identify the exact usable observations that produced it. Preserve
the current observation separately; bind deduplicated baseline inputs by count,
chronological first/last observation IDs, provider/mode sets, and a deterministic
SHA-256 of the ordered observation-ID list. Derived returns must include their
horizon anchors and historical endpoints; relative returns must additionally
include benchmark endpoints and anchors. Do not fall back to the last N raw
rows. Missing observation identity or conflicting bytes under one identity fail
closed. The canonical market-state snapshot and any anomaly row embedding that
snapshot must carry the same bounded `market_feature_evidence` projection and
its `market_history_observation_id`; downstream classification may not retain a
derived value while discarding its lineage. The projection is deep-copied,
JSON-safe, and schema-validated, while rows that genuinely have no temporal
evidence retain the optional-field compatibility path.
**Why:** Sample count alone does not describe a derived statistic's lineage.
Filtered missing values and multi-hour anchors can make the last N raw rows
materially different from the rows used in calculation, undermining point-in-
time review and future Protocol-v2 reproducibility.
**Revisit when:** A versioned feature store records an equally exact,
independently verifiable input graph. Any replacement must preserve causal
anchors and deterministic reconstruction; it cannot restore approximate range
metadata.

## 2026-07-19 - Keep non-finite market measurements unavailable
**Status:** accepted
**Decision:** Reject NaN and positive/negative infinity at every numeric input
used by canonical market snapshots, anomaly classification, market reaction,
market confirmation, derivatives crowding, and registry liquidity inference.
Non-finite values remain unavailable, cannot derive a liquidity tier, score,
reason, route input, or priority, and must not be copied into canonical JSON
artifacts. A redacted diagnostic payload may preserve only the explicit string
marker `<non_finite>`.
**Why:** Python's permissive numeric and JSON handling can accept `Infinity`.
Treating it as a very large real observation manufactures execution quality,
overstates confidence, and emits non-standard evidence that other readers may
interpret differently.
**Revisit when:** Never for non-finite IEEE values. A provider-specific sentinel
may be supported only by an explicit versioned normalization rule that maps it
to missing data before canonical projection.

## 2026-07-19 - Preserve explicit zero-valued canonical market evidence
**Status:** accepted
**Decision:** Resolve numeric market-field aliases, gate sentinels, and operator
rendering by ordered presence, not truthiness. An explicit finite `0` in the
canonical field is observed evidence and takes precedence over legacy aliases,
source-row fallbacks, and benchmark aliases throughout snapshot normalization,
liquidity/anomaly classification, priority construction, completed-move gates,
and reporting. It must render as zero, not `n/a`. Missing or empty canonical
values may still use the documented fallback order.
**Why:** Truthiness fallback converted genuine zero returns, relative returns,
volume surprise, liquidity, funding, and open-interest change into conflicting
nonzero legacy values. That can manufacture a breakout or crowding state and
corrupt point-in-time Protocol-v2 inputs without any new observation.
**Revisit when:** A versioned schema removes all aliases and rejects duplicate
representations at ingestion. Canonical precedence still remains the migration
rule for historical rows.

## 2026-07-19 - Make relative-return benchmark alignment causal
**Status:** accepted
**Decision:** Align BTC/ETH benchmark observations only from timestamps at or
before the asset observation. Treat the configured alignment tolerance as a
backward lookback, choose the latest eligible row deterministically, and report
missing current context when no causal benchmark row exists. Never use a later
benchmark observation merely because it is closer in wall-clock time.
**Why:** A symmetric nearest-time join can incorporate a benchmark price that
was not yet observable at the asset timestamp. Even a five-minute leak makes
relative-return features invalid point-in-time evidence and can contaminate
future Protocol-v2 partitions.
**Revisit when:** A versioned data source provides a formally synchronized
atomic cross-asset snapshot with one shared provider clock. Such a source may
prove equality, but it still does not justify forward-time matching.

## 2026-07-19 - Keep current KuCoin UTA capture closed before live transport
**Status:** accepted
**Decision:** Treat the current UTA response contract and its immutable fixture
capture/strict doctor as complete offline layers. Keep live transport,
authorization action, health/backoff, retention review, pointer publication,
campaign attachment, dashboard authority, and Protocol-v2 admission unavailable.
The fixture capture must use a UTA-specific namespace, ledger, manifest,
receipt, and raw-byte identity; it may share only the provider-local hardened
descriptor-held file primitives with the historical audit capture.
**Why:** Closing exact persistence and re-derivation before transport removes a
major source-contract ambiguity without turning fixtures or an ambient flag into
genuine catalyst evidence. Separate identities prevent the replaced v1 endpoint
from being silently treated as current UTA proof.
**Revisit when:** The human explicitly authorizes a bounded current-UTA live
transport after health/backoff, retention, confirmation, and exact request-ledger
review. That later decision still cannot attach evidence to policy or Protocol v2
without a genuine strict-clean capture and an explicit annex decision.

## 2026-07-19 - Keep KuCoin UTA parsing separate from historical v1 capture
**Status:** accepted
**Decision:** Implement the current `GET /api/ua/v1/market/announcement`
request/response contract as a separately versioned offline adapter. Preserve
the hashes of exact UTA response bytes and the renamed UTA schema; reuse only
the already-closed common announcement semantics. Do not relabel the historical
v1 immutable doctor as UTA-compatible. Readiness must report the current parser,
current capture/doctor, and live transport as separate implementation states.
**Why:** The two endpoints express the same domain with different request and
response identities. Converting fields for semantic validation is safe only if
the original bytes, schema version, endpoint, query, and lineage remain the
authority; sharing the old capture identity would hide provider-contract drift.
**Revisit when:** A proposed schema change would merge historical and current
capture identity. The current-version UTA doctor now passes offline regressions;
live use still requires a later separate authorization and confirmed bounded
transport decision.

## 2026-07-19 - Retire KuCoin v1 from the live activation path
**Status:** accepted
**Decision:** Keep the implemented `/api/v3/announcements` parser, fixtures, and
immutable doctor as historical audit evidence only. KuCoin's current official
change log says `GET /api/ua/v1/market/announcement` replaces that endpoint, so
readiness must expose no executable v1 plan, permit zero requests, and remain
blocked even when the legacy authorization flag is present. Implement and
review a new versioned UTA request/response/pagination contract and matching
doctor before asking for any provider authorization or building a live command.
**Why:** A public endpoint being reachable or retained in documentation does not
make it the current supported contract. Activating a replaced schema would
create avoidable drift and could turn deprecation or response changes into
false empty or incomplete catalyst evidence.
**Revisit when:** The current UTA contract is fixture-closed and its immutable
doctor passes. That permits consideration of a separate authorization boundary;
it does not authorize a provider call or policy attachment.

## 2026-07-19 - Count episodes, dependence, and every trial before Protocol-v2 evaluation
**Status:** accepted
**Decision:** Make a predeclared declustered Decision episode—not an observation
row, scan, repeated idea, notification, or asset count—the primary Protocol-v2
analysis unit. Freeze chronological development, validation, and one untouched
holdout with leakage-safe purge/embargo; use dependence-aware temporal blocks
rather than IID row resampling by default; and retain an append-only ledger of
every tried feature, parameter, threshold, subset, outcome, cost, and stopping
choice, including failed and abandoned work. Require an annex-selected
family-level multiple-testing method and development-derived sample planning
before validation. Set no numerical values and do not identify or read holdout
bytes from this design record.
**Why:** The current evidence contains overlapping observations, common market
moves, related assets, and many possible research choices. Treating those as
independent or forgetting unsuccessful variants would overstate precision and
make post-hoc selection look like measured edge.
**Revisit when:** The genuine point-in-time inputs, complete outcomes, human
labels, and distinct route episodes are sufficient to estimate nuisance values
from development data and the human is ready to seal the full Protocol-v2
annex. Revisit the exact values then, not the need for honest trial and
dependence accounting.

## 2026-07-19 - Require an explicit empty response to close Bitget coverage
**Status:** accepted
**Decision:** In Bitget announcement contract v2, treat every stopped nonempty
cursor prefix as partial, including a short page. Continue a short nonempty page
with its final `annId` when another supplied response exists, and accept
complete coverage only when the terminal response is explicitly empty. Reject
any supplied page after that empty response. Healthy-empty still requires an
empty first response.
**Why:** Bitget documents the next cursor as the prior response's final
`annId`, but does not document a short-page-is-terminal guarantee or a total
count. Treating a short page as completion could silently hide additional
official announcements.
**Revisit when:** Bitget publishes a stable, versioned terminal or total-count
guarantee and fixtures plus a separately reviewed contract prove it. Never infer
completion merely to reduce requests.

## 2026-07-19 - Make effective provider cadence the readiness headline
**Status:** accepted
**Decision:** Preserve the next time implied by successful observation history
as `history_next_eligible_observation_at`, but make market/no-send readiness's
headline next-eligible time, cadence status, and eligible-now value use the
maximum of history cadence, the durable provider-call reservation, and shared
provider backoff. Reuse the same pure synthesis used by campaign reporting and
combine already-read states so the projection does not introduce a second
state read.
**Why:** Provider-call spacing starts when an attempt crosses the provider
boundary, even if it fails before HTTP or publication. Showing only the older
successful-observation clock beside a reservation blocker was technically
explainable but operator-contradictory and could invite an unsafe retry.
**Revisit when:** The provider campaign adopts a different explicitly reviewed
spacing contract. Never shorten or bypass the effective clock to improve warmup.

## 2026-07-19 - Keep Bitget readiness non-activating
**Status:** accepted
**Decision:** Expose Bitget's future 31-day cursor request plan and the separate
`RSI_DECISION_RADAR_BITGET_ANNOUNCEMENTS_LIVE` state through a no-network,
no-write readiness target. Immutable fixture capture and strict doctor may be
proven only in a disposable root, but readiness stays blocked whether the flag
is absent or present until the live transport and authorized capture command
are implemented. The current next safe action is the capture smoke; no provider
authorization or provider action is requested.
**Why:** A visible authorization and request-budget boundary prevents a public
endpoint or an ambient flag from being mistaken for a complete, authorized,
auditable evidence path. It also preserves source diversity without silently
reprioritizing Bitget ahead of the selected KuCoin path.
**Revisit when:** A separate human decision reprioritizes Bitget and authorizes
a confirmed bounded live transport with health/backoff and retention review.

## 2026-07-19 - Preregister anomaly-method research before implementation
**Status:** accepted
**Decision:** Keep all production anomaly features and the existing volume/
turnover robust-surprise shadow unchanged. Study future candidates, in order,
as (1) separate-horizon robust signed-return and relative-return tails, (2)
strictly point-in-time crypto market-factor residuals, (3) separate online
changepoint context, and (4) extreme-value tails only after enough independent
exceedances exist. Defer Isolation Forest, autoencoders, and broad anomaly
ensembles until an explainable sealed benchmark, sufficient independent
episodes, point-in-time feature matrices, and explanation/rollback rules exist.
Set no parameters, thresholds, minimum samples, costs, route scope, success
criteria, holdout, or executable evaluation target in this decision.
**Why:** The live campaign is sparse, overlapping, and not an independent sample;
implementing or tuning a more complex detector now would invite leakage and
opportunistic threshold selection. A bounded research order lets evidence
collection proceed while preserving the exact Protocol-v2 freeze-before-test
boundary.
**Revisit when:** Genuine intraday/execution/context inputs, matured episode
outcomes, matched controls, frozen development/validation/untouched-holdout
partitions, and a complete Protocol-v2 annex are ready. Any promotion requires
a separate versioned decision and cannot use Protocol-v1 final-test evidence.

## 2026-07-19 - Keep Bitget as an offline source-diverse announcement witness
**Status:** accepted
**Decision:** Implement Bitget's documented public `GET
/api/v2/public/annoucements` response as the second strict synthetic-byte
announcement contract, preserving the provider's exact path spelling,
maximum-10 last-ID cursor pagination, required language, provider/acquisition
clocks, stable string IDs, official type/subtype pairs, deprecated description,
and safe official URLs. Keep it unconfigured, unauthorized, inactive,
campaign-detached, and Protocol-v2-ineligible. Do not collapse its cursor
coverage into KuCoin's total/page-count model or treat `cTime` as event time.
**Why:** A second first-party witness improves future source diversity, while an
offline closed contract prevents public access, deprecated fields, or a full
last page from being mistaken for authorization, complete evidence, or a
directional catalyst.
**Revisit when:** KuCoin has genuine strict-clean evidence or the human
explicitly reprioritizes Bitget and separately authorizes a bounded capture.
Require confirmation, immutable bytes, ledger, health/backoff, doctor,
retention, source-independence, and annex review before any policy use.

## 2026-07-19 - Keep the KuCoin announcement contract closed before activation
**Status:** accepted
**Decision:** Treat the v1 KuCoin announcement implementation as a strict
offline synthetic-byte contract only. Preserve exact request windows, response
digests, local acquisition clocks, stable IDs, official multi-type categories,
language, description-summary status, URLs, and complete-versus-partial page
coverage. Keep provider-returned page size distinct from requested page size.
Never infer event time or direction from `cTime`, and do not attach these
fixtures to discovery, campaign, dashboard, score, route, or Protocol-v2
authority. A live client remains forbidden until a separate no-call readiness,
already-present authorization, explicit confirmation, bounded immutable
capture, ledger, health/backoff, doctor, retention, and annex boundary exists.
**Why:** KuCoin documents a useful public machine contract, but a permissive
generic parser or premature activation would hide pagination gaps, conflate
publication with the actual market event, and make synthetic input look like
genuine catalyst evidence.
**Revisit when:** The offline contract has a strict observational readiness and
immutable capture design, and the human separately authorizes a genuine bounded
acquisition. Any change must retain fail-closed byte, page, clock, identity,
URL, safety, and no-direction guarantees.

## 2026-07-19 - Implement KuCoin's documented announcement contract before Bitget
**Status:** superseded
**Decision:** Select KuCoin's documented public/no-permission `GET
/api/v3/announcements` as the next offline official-announcement contract.
Keep Bitget's documented public `GET /api/v2/public/annoucements` as the second
candidate, preserving the provider's exact path spelling. This chooses
implementation order only: both providers remain unconfigured, unauthorized,
inactive, campaign-detached, and Protocol-v2-ineligible. No live call is
permitted until a separate already-present authorization and confirmed bounded
capture exist.
**Why:** Both official APIs expose stable IDs, categories, publication clocks,
language, source URLs, and bounded pagination. KuCoin's up-to-50-row page plus
explicit total/current-page fields makes coverage easier to close with fewer
requests; Bitget's 10-row cursor contract is valuable as a later source-diverse
official witness.
**Revisit when:** KuCoin's official contract, terms, or reachability no longer
supports a bounded public capture, or the offline normalizer reveals a contract
gap that Bitget closes more safely. Reordering must not create authorization or
weaken immutable-byte, clock, coverage, health, doctor, or annex gates.
**Superseded by:** `Retire KuCoin v1 from the live activation path`; the UTA
replacement condition occurred before any live activation.

## 2026-07-19 - Keep Kraken roadmap context separate from launch evidence
**Status:** accepted
**Decision:** Treat Kraken's official listing roadmap as planned-listing or
scheduled-risk context only. It cannot prove funding, trading launch,
tradability, strict catalyst eligibility, or directional bias. An actual Kraken
launch claim requires an exact official publication acquired through an
approved supported transport; delisting and operational notices remain a
separate regional-risk role. `kraken_announcements` stays planned,
unimplemented, unconfigured, unauthorized, and Protocol-v2-ineligible because
the reviewed official surfaces expose human-readable pages/social channels but
no documented stable announcement REST, WebSocket, RSS, or equivalent machine
contract.
**Why:** Kraken explicitly says roadmap inclusion is not a guaranteed listing
and funding/trading remain unsupported until a separate official announcement.
Collapsing roadmap discovery, launch publication, and regional risk notices
would invent event clocks and overstate catalyst and tradability evidence.
**Revisit when:** The operator selects exact source roles and approves either a
documented machine contract or a bounded first-party page/local-import contract
after access, terms, retention, redistribution, clock, coverage, and regional
semantics are reviewed. Any live acquisition still requires separate explicit
authorization, immutable bytes, strict doctor, and annex selection.

## 2026-07-19 - Preserve derivatives freshness through full-set publication
**Status:** accepted
**Decision:** Bybit derivatives live/capture v3 re-evaluates every composite
context's oldest required provider-response clock when the final sequential
response completes. It preserves acquisition and completion freshness, the
maximum completion age, and the exact 15-second policy through contexts,
manifests, receipts, pointers, status, and review-export selection. Exact
transport responses must form one ordered non-overlapping window. A complete
aged set remains immutable exact-response evidence but sets
`protocol_v2_input_quality_eligible=false`.
**Why:** The offline v2 row already dated each composite context conservatively,
but downstream publication retained only one freshness boolean. That erased
whether the set was fresh when acquired or only became stale while its bounded
sequential request plan was finishing, weakening audit and annex decisions.
**Revisit when:** Bybit offers an atomic multi-instrument derivatives snapshot,
or a preregistered streaming/synchronization annex defines a stronger common
cutoff. Any replacement must retain every component provider clock and must not
let individually fresh composite rows hide an aged completed set.

## 2026-07-19 - Date sequential intraday sets at full capture completion
**Status:** accepted
**Decision:** Bybit intraday live/capture v4 preserves whether every native 1h
and 4h bar was fresh at its own acquisition, then re-evaluates every bar-close
and provider-response clock when the final sequential response completes. The
15-second provider-response policy and interval-specific bar-recency policy both
apply at that full-set boundary. Manifests, receipts, pointers, bar projections,
and review-export selection bind acquisition/completion state, maximum provider
age, minimum remaining bar-recency, and the derived input-quality decision.
Request timing must also prove one ordered non-overlapping response window. A
complete aged set remains immutable exact-response evidence but sets
`protocol_v2_input_quality_eligible=false`.
**Why:** Up to 60 direct-bar requests run sequentially. An early response can be
fresh when received and stale before the collection finishes; preserving only
per-response freshness would overstate the point-in-time set available to
Protocol-v2 research.
**Revisit when:** Bybit offers an atomic multi-instrument completed-bar snapshot,
or a preregistered streaming/synchronization contract defines a stronger common
cutoff. Any replacement must retain exact per-response clocks and must not let
individually fresh arrivals hide an aged set.

## 2026-07-19 - Bind exact book acquisition to response completion
**Status:** accepted
**Decision:** Bybit execution-quality live/capture v4 defines a persisted
order book's `acquired_at` as the corresponding exact transport response's
read-completion time. Immutable validation requires each request and response to
remain inside the declared capture window, preserves sequential request timing,
and requires the normalized acquisition clock to equal its response-index clock.
Mapping-only diagnostic collection may use its injected local clock, but it
cannot enter the immutable exact-response capture boundary.
**Why:** Capturing exact response timing while normalizing against a second clock
left two competing acquisition truths. A drifted or injected second clock could
misstate freshness even though the accepted transport evidence already carried
the correct local availability time.
**Revisit when:** A stronger monotonic/wall-clock binding or signed provider
availability clock is adopted. Any replacement must retain an exact deterministic
join between raw transport timing and every normalized book.

## 2026-07-19 - Date execution-quality sets at full capture completion
**Status:** accepted
**Decision:** Bybit execution-quality live/capture v3 preserves whether every
order book was fresh when acquired, then re-evaluates every provider-observation
clock when the final sequential book completes. The 15-second age policy applies
at that full-set completion boundary. Manifests, receipts, pointers, summaries,
and observation projections bind both freshness states, the maximum completion
age, the policy, and the derived Protocol-v2 input-quality decision. A complete
but aged capture remains immutable and evidence-authority-eligible, but must set
`protocol_v2_input_quality_eligible=false`.
**Why:** With up to 29 sequential order-book requests, an early book can be
fresh on arrival but stale by the time the set is complete. Treating only
per-request acquisition freshness as the set result would overstate the
point-in-time execution evidence available to Protocol v2.
**Revisit when:** A preregistered annex adopts a stricter age limit, the official
provider offers one atomic multi-instrument snapshot, or a bounded streaming
capture defines a stronger synchronization contract. Any replacement must keep
per-book clocks and must not let individually fresh arrivals hide an aged set.

## 2026-07-18 - Require current provider responses for direct intraday bars
**Status:** accepted
**Decision:** Bybit intraday v3 keeps completed-bar recency and provider-response
freshness as separate explicit states. Overall `freshness_status=fresh` requires
both: the exact latest completed 1h/4h candle is still inside its interval window
and the provider response is at most 15 seconds old at acquisition. Persist the
provider-response age and policy, and reject a payload whose provider response
time predates the completed candle it claims to contain. Immutable capture
rederives the same fields from exact response bytes.
**Why:** Exact candle identity alone does not prove a current response. A cached
or replayed payload could satisfy the completed-bucket shape while a stale
provider clock was ignored, overstating the point-in-time evidence available to
Protocol-v2 research.
**Revisit when:** The official provider contract supplies a stronger signed or
stream-sequenced availability clock, or a preregistered annex adopts a stricter
latency limit. Any replacement must preserve separate bar/response truth and
must not let either component hide staleness in the other.

## 2026-07-18 - Date composite derivatives context from its oldest response
**Status:** accepted
**Decision:** Bybit derivatives context v2 preserves all four component provider
response clocks and defines `provider_observed_at` as their minimum. It also
records the newest response, full response-time map, response span, and the
explicit `oldest_component_response` policy. Snapshot age, freshness, live
completion freshness, immutable capture rederivation, and Protocol-v2 input-
quality eligibility all use that conservative clock. One fresh ticker cannot
hide stale funding, open-interest, or positioning response evidence.
**Why:** A derivatives context is a composite observation. The prior maximum-
clock rule described only its newest component and could classify the whole row
fresh when another provider response was already stale. That would overstate the
point-in-time evidence available for empirical work.
**Revisit when:** The source contract provides an atomic multi-metric response
or a preregistered Protocol-v2 annex defines per-component freshness policies.
Any replacement must retain every component clock, expose response skew, and
never make composite freshness more favorable than its stalest required input.

## 2026-07-18 - Require closed unit health on future live generations
**Status:** accepted
**Decision:** Every complete live market generation observed at or after
2026-07-19 00:00:00 UTC must carry snapshot-unit validation contract v1. The
manifest and audit copy exact warning-row, warning-total, warning-category, and
status values derived from the canonical snapshot rows. Strict doctor rederives
the values and exact snapshot cardinality; a missing/invalid contract, drift, or
any unit warning blocks publication. Complete live generations before the
cutoff and fixture mechanics remain readable under their original immutable
contract and are never rewritten.
**Why:** Operator visibility is not sufficient publication evidence. Unit
normalization directly affects anomaly magnitude and Decision actionability, so
future authority must prove both warning-free inputs and agreement between its
summary and exact rows. A forward-only cutoff closes new evidence without
silently reinterpreting or mutating historical artifacts.
**Revisit when:** A versioned manifest migration replaces contract v1 or the
canonical snapshot schema removes `unit_warnings`. Any replacement must retain
exact-row recomputation, immutable historical compatibility, fail-closed strict
publication, and no silent 100x unit conversion.

## 2026-07-18 - Preserve no-independence truth in live empirical projections
**Status:** accepted
**Decision:** New `decision_radar.empirical_live_campaign_projection` values use
schema v2 and copy the source episode contract's explicit
`statistical_independence_claim=false` and
`cross_asset_independence_claim=false`. A source that claims either form of
independence is rejected. The already-sealed schema-v1 empirical report bundle
remains readable as immutable legacy evidence; it is never rewritten or
silently promoted to v2.
**Why:** Fixed-start declustering prevents repeated observations from being
counted as separate episode representatives, but it does not estimate an
independent sample size. Stripping the explicit false claims allowed a consumer
to infer more evidence than the source contract supports.
**Revisit when:** A predeclared Protocol-v2 annex defines and validates an
independent-sample estimator, correlated-market grouping, and minimum-sample
rules from sufficient point-in-time evidence. Do not infer independence from
episode count alone.

## 2026-07-18 - Show campaign work only from exact-pointer safe context
**Status:** accepted
**Decision:** The dashboard may surface campaign-wide human review, missing
outcome-price, and Bybit execution-quality work only from the canonical
`RADAR_LIVE_OBSERVATION_CAMPAIGN_REPORT.json` after a descriptor-anchored,
bounded read; closed schema and zero-side-effect validation; and an exact
namespace/run/revision match to the current dashboard pointer. Project only
bounded identities, counts, symbols, and three allowlisted no-call/no-write
commands. Label the result historical campaign context, never current-generation
authority. A missing, oversized, unsafe, stale-pointer, contradictory, or
command-drifted report suppresses the work panel without weakening or blocking
the exact current dashboard generation. Dashboard GET/HEAD requests never read
environment variables and never count as human review events.
**Why:** A valid zero-idea generation made Today look operationally empty even
though three receipt-backed ideas await explicit review, one DEXE outcome lacks
point-in-time price evidence, and trusted Bybit spread coverage is 0/630. Those
actions already existed in the terminal campaign report; hiding them forced the
operator to reconcile multiple command-line surfaces, while treating the mutable
campaign report as current authority would blur the product's trust boundary.
**Revisit when:** Campaign actions get their own immutable pointer-bound receipt
or the campaign report schema changes. Any replacement must preserve bounded
reads, exact pointer reconciliation, command allowlisting, fail-closed
projection, explicit historical labeling, and the no-call/no-write/no-review-on-
GET contract.

## 2026-07-18 - Derive RSI only from captured closed Bybit candles
**Status:** accepted
**Decision:** Each authorized Bybit intraday request continues to fetch exactly
one `interval=60` or `interval=240` response per eligible native instrument, but
sets the response limit to 200 rather than two. Accept only a reverse-ordered,
contiguous sequence ending at the exact latest completed candle. Derive the
latest 14-period Wilder RSI with the scanner's shared SMA-seeded Wilder
implementation and persist its timeframe, candle-close time, local availability
time, source lineage, input count, unit, and no-future-data state beside the
latest bar. Fewer than 15 closed candles is `insufficient_history` with a null
RSI; never invent or proxy a value. The raw response remains immutable so the
projection can be fully rederived.
**Why:** The prior two-row request could prove the latest 1h/4h OHLCV candle but
could never satisfy Protocol-v2's RSI technical-context requirement. Bybit's
official V5 kline contract supports 1..1000 rows, defaults to 200, and returns
rows in reverse start-time order, so 200 supplies bounded warmup history without
adding a provider request. Closed-contiguous enforcement prevents an open,
missing, or future candle from influencing RSI.
**Revisit when:** The official kline contract or shared Wilder implementation
changes, a genuine response exceeds the bounded payload contract, or the sealed
Protocol-v2 annex selects a different RSI period. Any replacement must preserve
exact native identity, closed-candle availability, immutable raw lineage,
explicit insufficient history, no future data, and the existing request bound.

## 2026-07-18 - Use one complete Bybit catalog before per-instrument books
**Status:** accepted
**Decision:** Execution-quality capture v2 must request one public
`/v5/market/instruments-info` catalog with `category=linear`, `status=Trading`,
and `limit=1000`, then request one 200-level public order book for each exact
eligible USDT-linear perpetual. A missing or non-empty `nextPageCursor` is an
incomplete catalog and fails before every order-book request and publication. The absolute
request bound is 31 for a 30-asset Radar universe; the actual count is one plus
the eligible-instrument count. Preserve the catalog as one immutable raw
response and rederive all candidate joins from it. Do not fall back to one
metadata request per Radar asset, pagination, retries, alternate hosts, proxies,
VPNs, or region bypasses.
**Why:** Bybit's current official V5 contract permits up to 1,000 instruments in
one response and warns that the default 500-row response is incomplete for the
linear catalog. One catalog gives every candidate the same point-in-time
metadata basis, cuts the current worst-case boundary from 58 GETs to 30, and
retains a fail-closed completeness proof while depth still requires one native
book per eligible instrument.
**Revisit when:** The Trading linear catalog exceeds 1,000 rows, the official
endpoint changes its pagination/limit contract, or a sealed Protocol-v2 annex
requires a different point-in-time venue snapshot. Any replacement must retain
complete-catalog evidence, exact identity, bounded calls, raw-byte capture, and
the no-retry/no-bypass policy.

## 2026-07-18 - Type authorization status metadata without weakening secret scans
**Status:** accepted
**Decision:** Treat `live_authorization_status` as a closed metadata field only
when its value is exactly `absent`, `missing_configuration`, `not_defined`,
`not_required`, or `present`. Keep the generic `authorization` secret-name
fragment active. Any other value in the status field must fail both its schema
enum and secret-redaction validation; never exempt all `*_status` or
authorization-named fields from secret scanning.
**Why:** A genuine no-send cycle produced 11 correct readiness rows but strict
doctor mistook their `absent`/`not_defined` status values for credentials. A
blanket field-name exemption would hide a real token accidentally written into
the same field. Closed value typing distinguishes operator state from secret
material without weakening the fail-closed boundary.
**Revisit when:** A new authorization metadata state is required. Add it only
with a documented semantic, an enum update, safe-value validation, and tests
that still reject an arbitrary token in that field.

## 2026-07-18 - Separate current Protocol-v2 progress from its frozen requirements
**Status:** accepted
**Decision:** Keep the canonical 2026-07-16 Protocol-v2 requirements object at
SHA-256
`683f03fe74306a80acaebf2556e2652cc67e9c725d97deb6dd083b3b28109603`,
its checked-in Markdown at
`897b29a85ff38fb19f5c0eda7e8077bf4b3cbc18aa92270e03d3ffe413c8ae4e`,
and its implementation at
`78867805252783d887c4a8ee475e34edb289e9bc86aa8582723ba93bcc975e97`
byte-identical. Render later accepted human decisions only through the separate
`empirical_validation_protocol_v2_progress` static surface and its mutable
current-progress note: Bybit, USDT-linear perpetuals, USDT quote, public market
data only, and owner-confirmed research eligibility are selected. Do not
present the frozen object's freeze-time “venue/instrument/quote not selected”
placeholders as current blockers. Current blockers begin with the exact
unsealed instrument set, unproven permitted reachability after the recorded
403, and absent genuine execution-quality capture. Current-progress v2 must
then enumerate live baseline warmup, genuine intraday/RSI and derivatives
captures, authoritative catalyst/unlock/on-chain/fundamental/official-macro
sources, historical outcome recovery, explicit human timing and blind OOS
labels, holdout, cost, independent episode/sample, and final annex decisions.
Do not collapse those operationally distinct gaps into generic source or
outcome rows. The progress projection reads no environment, files, credentials,
providers, or holdout data and creates no authorization or evaluation target.
**Why:** Rewriting the preregistered requirements would destroy its audit hash,
while continuing to show superseded placeholders as current truth contradicts
the accepted venue decision. Separating immutable historical requirements from
current decision progress preserves both auditability and operator coherence.
**Revisit when:** The exact Protocol-v2 annex is ready to be sealed as a new,
human-approved immutable artifact. Until then, update only genuinely accepted
progress and never imply that selection, evidence, holdout, or activation is
complete.

## 2026-07-18 - Fixture configuration never implies live-provider readiness
**Status:** accepted
**Decision:** A checked-in or operator-selected fixture path may establish only
`fixture_input_configured` and parser coverage. It must not set live
`configured`, authorization, transport, mapping, request budget, rehearsal
eligibility, provider health, or evidence authority. Fixture-only provider rows
must expose `configuration_scope=fixture_input_only`, the explicit live
transport/authorization/mapping states, zero current live request budget, and
closed rehearsal blockers. Operator and dashboard surfaces label this state
“Fixture only,” and strict doctor checks reject a fixture-scoped row that claims
live configuration, call permission, eligibility, or implemented transport.
This applies to the current offline Binance-public parser, structured-calendar
parsers, DEX/on-chain parsers, and DefiLlama fundamentals parser; it does not
change genuine live adapters with their own explicit authorization boundary.
**Why:** File existence proves that deterministic parser mechanics can be
tested. It says nothing about a current provider transport, authorization,
real-world identity mapping, reachability, freshness, or admissible evidence.
Conflating those states makes operator readiness and dashboard coverage look
healthier than the system actually is.
**Revisit when:** A provider gets a bounded live transport, a separate explicit
authorization contract, genuine mapping where required, immutable raw capture,
ledger/health/backoff/freshness controls, and focused doctor coverage. Promote
only that provider's live fields; never infer promotion from its fixture path.

## 2026-07-18 - Keep DefiLlama fundamentals typed, mapped, and fixture-first
**Status:** accepted
**Decision:** The candidate DefiLlama protocol-fundamentals contract uses four
separate official free-interface responses: `/protocols`, then
`/overview/fees` with `dailyFees`, `dailyRevenue`, and
`dailyHoldersRevenue`. Every response keeps its own request/read clock and
digest. A row requires an explicit operator-confirmed mapping among canonical
Radar asset ID, CoinGecko ID, DefiLlama protocol-list ID and slug, protocol
name, and token symbol; name or symbol similarity never creates that mapping.
TVL change stays percent points and is not net flow. User-paid fees, protocol-
retained revenue, and token-holder revenue remain distinct; missing values are
unavailable, not zero, and 7d/30d totals are not daily averages. Because the
reviewed free overview schema exposes no metric-value timestamp, local
acquisition clocks remain explicit while provider value time is unavailable.
The implemented contract is synthetic-fixture-only, context-only, no-call,
non-authoritative, campaign-detached, and Protocol-v2-ineligible. See
`research/DEFILLAMA_PROTOCOL_FUNDAMENTALS_INTERFACE_REVIEW.md` / `.json`.
**Why:** Protocol fundamentals can improve fundamental-led context only if
economic meanings and token/protocol identities remain honest. Collapsing
fees/revenue, treating USD TVL changes as deposits, auto-matching a token to a
protocol, or inventing a provider timestamp would manufacture evidence.
**Revisit when:** The operator approves a genuine mapping registry and a
separate DefiLlama authorization already exists, then after request budgets,
exact immutable bytes, ledger/health/backoff, freshness, retention/export,
strict-doctor, rollback, and Protocol-v2 annex selection are reviewed. Do not
add a client or infer authorization merely because the free endpoints are
public.

## 2026-07-18 - Require an exact reviewed universe for DefiLlama mappings
**Status:** accepted
**Decision:** DefiLlama protocol identity is closed only by a canonical,
operator-reviewed registry bound to one exact liquidity-ranked Radar universe
digest. Every asset must be explicitly `mapped` or `not_applicable`; a mapped
row retains canonical and CoinGecko IDs, symbol, DefiLlama protocol-list ID,
slug, name, reviewer, review time, and note. Name/symbol similarity never
creates or carries a mapping. Missing/extra rows, universe drift, identity
conflicts, altered canonical projections, and incomplete decisions fail closed.
A fixture registry may prove validation mechanics but cannot become live-
mapping eligible. The review and coverage command performs no provider call or
write, and even a complete operator registry grants neither provider
authorization nor evidence/Protocol-v2 authority.
The normal operator review surface must resolve the strict current dashboard
pointer rather than accept a guessed/latest namespace. Its generated template
is deliberately invalid until every placeholder, pending status, note, and
confirmation is replaced by an explicit human decision; a later universe
digest or identity change must return the registry to the review queue.
**Why:** Token and protocol identities are not interchangeable. An apparently
reasonable automatic join can attach TVL, fee, or revenue evidence to the wrong
asset and manufacture a fundamental thesis. Binding the human decision to the
exact reviewed universe makes that ambiguity and later membership drift
observable.
**Revisit when:** A more durable canonical entity registry is independently
designed, human-reviewed, versioned, and proven to preserve the same explicit
mapped/not-applicable decisions across universe changes without inference. Do
not weaken the current exact-universe boundary merely to reduce review work.

## 2026-07-18 - Do not guess an OKX announcement transport or region
**Status:** accepted
**Decision:** Keep `okx_announcements` as a planned, unavailable capability
until the operator selects the applicable official OKX region/domain and
approves a supported acquisition contract. OKX's official Help Center exposes
dated listing, delisting, trading, suspension, and API notices, but the current
official v5 API guide review did not find a documented announcement REST or
WebSocket contract. Do not invent a hidden content endpoint, scrape a guessed
regional page, combine regional catalogs, or promote parsed Help Center HTML
directly into authoritative catalyst or Protocol-v2 evidence. See
`research/OKX_ANNOUNCEMENT_INTERFACE_REVIEW.md` / `.json`.
**Why:** First-party pages can be valuable evidence, but their article sets and
categories differ by region. A registry name or parseable page does not prove
the correct jurisdiction, stable interface, complete pagination, access terms,
retention rights, local observation time, or immutable source chain. Guessing
those fields would turn an authoritative-looking source into unreviewable
evidence.
**Revisit when:** The applicable region and access/retention contract are
explicitly approved. Begin with an offline parser against operator-reviewed
immutable bytes; any live path still requires separate authorization, bounded
no-redirect/no-retry acquisition, raw-byte fingerprints, request ledger,
coverage/freshness/health state, strict doctor, and an explicit Protocol-v2
annex decision. Never use alternate hosts, proxies, VPNs, or region bypasses.

## 2026-07-18 - Separate Coinbase announcement time from observed product state
**Status:** accepted
**Decision:** Keep `coinbase` and `coinbase_announcements` planned and inactive.
Coinbase's current listing guide directs new-asset updates to the official
`@CoinbaseMarkets` X account, but this project has no approved X transport. The
documented public Exchange `GET /products` and WebSocket status/auction
contracts may later prove exact locally observed product identity, restriction,
and auction state. They do not prove a prior listing announcement, approval,
integration start, or first-trading clock. Never scrape X, infer/backdate an
announcement from first product discovery, or use Coinbase as a substitute for
the selected Bybit USDT-linear perpetual execution surface. See
`research/COINBASE_LISTING_INTERFACE_REVIEW.md` / `.json`.
**Why:** Official communication and observed venue state answer different
questions. Collapsing them would create false catalyst timing and look-ahead;
collapsing Coinbase into Bybit would also corrupt venue-native cost and
instrument evidence.
**Revisit when:** The operator explicitly selects the announcement and/or
product-state lane and approves its access/retention contract. Require separate
authorization, a closed offline normalizer, bounded immutable capture, local
read-completion time, complete-catalog/prior-snapshot transition proof,
ledger/health/freshness, strict doctor, and explicit annex selection. Public/no-
key access never creates authorization.

## 2026-07-18 - Preserve official announcement windows without inventing time
**Status:** accepted
**Decision:** Canonical announcement evidence must preserve separately the
provider publication time, explicit activity/effective start, and explicit
activity/effective end. The Bybit adapter accepts both the v5 response-table
`startDataTimestamp`/`endDataTimestamp` names and the official response-example
`startDateTimestamp`/`endDateTimestamp` names. Raw events, official-exchange
events, and candidates copy the resulting window and an explicit status. A
missing endpoint remains missing; an end before its start is
`invalid_end_before_start` plus `invalid_effective_window`, never swapped,
clamped, or silently treated as complete. Calendar or activity windows provide
timing/risk context and cannot create directional bias alone.
**Why:** Dropping the end destroys expiry and episode boundaries, while
repairing malformed source time would manufacture evidence. The provider's own
documentation currently uses two near-identical field spellings, so supporting
both is necessary to remain compatible with its documented contract.
**Revisit when:** Bybit deprecates one spelling in an official versioned
contract. Continue reading historical evidence without rewriting it and retain
publication, start, and end as distinct clocks.

## 2026-07-18 - Do not promote an unverified Binance announcement transport
**Status:** accepted
**Decision:** The legacy signed Binance CMS WebSocket adapter remains disabled,
research-only, and ineligible for Protocol-v2 or authoritative catalyst use.
Preserve its fixture parser and historical code, but do not activate it or add
an authoritative raw-frame publication path until current official Binance
documentation identifies the exact endpoint/stream, topic, authentication and
permission model, payload schema, request/rate limits, supported environment,
and retention/redistribution terms. Credentials and the legacy live flag alone
do not establish that contract. See
`research/BINANCE_ANNOUNCEMENT_INTERFACE_REVIEW.md` / `.json`.
**Why:** Binance's current official developer introduction says undocumented
interfaces should not be relied upon, and its public API catalog does not expose
the repository's `sapi/wss` / `com_announcement_en` contract. Its Developer
Center does advertise an Announcements product, so absence from the public
catalog is not proof the product does not exist; it is proof that this checkout
cannot currently certify the legacy transport as supported evidence.
**Revisit when:** Current official product documentation and applicable terms
are accessible, then after an explicit human review authorizes a bounded
no-send rehearsal with a redacted ledger, immutable accepted frames, and strict
doctor. Never infer authorization from credentials or bypass access controls.

## 2026-07-18 - Accepted official-announcement bytes precede source authority
**Status:** accepted
**Decision:** A successful bounded Bybit official-announcement rehearsal must
persist the exact accepted response body once in its namespace before its
request ledger may record success. The immutable artifact name, SHA-256, size,
request identity, result count, rehearsal report, and normalized official-
exchange rows must reconcile under strict doctor through descriptor-anchored,
no-follow reads. Missing, changed, symlinked, duplicated, secret-like, or
unprojected bytes invalidate the rehearsal. HTTP errors, nonzero provider API
errors, oversized bodies, and other failed requests retain bounded redacted
diagnostics only and must not create an accepted raw-source artifact. Historical
namespaces are never silently rewritten to satisfy the newer contract. This
attestation rule does not create provider authorization or make a rehearsal
campaign, dashboard, or Protocol-v2 authority.
**Why:** Normalized rows and a request ledger alone cannot prove exactly which
provider bytes were accepted. Immutable bytes plus a closed projection chain
make later source review reproducible while avoiding retention of arbitrary
failed responses that may contain unsafe diagnostics.
**Revisit when:** A provider supplies a stronger cryptographic receipt or a
different official source is activated. Preserve the exact-body evidence and
closed source-to-row reconciliation unless the replacement offers equal or
stronger reproducibility and secret safety.

## 2026-07-18 - Live announcement acquisition time is locally observed
**Status:** accepted
**Decision:** For live official-exchange ingestion, canonical `fetched_at` is
the local UTC time immediately after the complete HTTP response body or
WebSocket message is read. Provider publication, update, launch, and event
fields remain source clocks and may not substitute for local acquisition time.
Any provider-supplied fetch claim is preserved separately. Offline fixtures may
retain explicitly recorded fixture clocks, but the live Bybit direct/rehearsal
and Binance paths must stamp this boundary before shared normalization.
**Why:** Publication time proves when a source document says it appeared; it
does not prove when this system observed it. Conflating the clocks destroys
latency measurement and can make post-hoc catalyst evidence look point-in-time.
**Revisit when:** A transport supplies a stronger trusted receipt clock. Even
then, preserve both transport receipt and local read-completion clocks rather
than replacing one with the other.

## 2026-07-18 - Normalize current Tokenomist v5 unlocks without inventing authority
**Status:** accepted
**Decision:** The structured-unlock adapter targets Tokenomist's current v5
cliff-unlock response contract, not deprecated v4. Its first implementation
accepts only one closed synthetic-fixture capture: exact GET host/path/token
identity, filters, pagination, provider query time, acquisition time, response
coverage, token identity, cliff totals, allocation breakdown, reference-price
timing, committed claims, and precision must validate before a row exists.
`valueToMarketCap` is percent points of market capitalization and remains
distinct from circulating- or total-supply percentage. Provider query/update
time is not first-public time; month/week/quarter/year precision is estimated.
Existing flat historical fixtures retain their prior semantics. The fixture
path makes no call, reads no credential or authorization, writes no provider
artifact, and is never campaign, dashboard, or Protocol-v2 authority.
**Why:** The generic loader could see the official top-level `data` array but
could not parse v5's `unlockDate` or nested `cliffUnlocks`, so a genuine-shaped
response would lose timing and size while still appearing structured. A closed
adapter removes that semantic false-positive without activating a provider or
tuning any score. Tokenomist's documentation requires an API key, identifies v5
as current, and limits ordinary plans to personal/non-commercial,
non-redistribution use, so genuine response bytes need their own authorization,
capture, retention, and export policy.
**Revisit when:** The owner has an applicable Tokenomist subscription,
explicitly authorizes a bounded no-send acquisition, and approves its request
ledger, immutable capture, retention, and non-redistribution policy. Do not put
genuine provider bytes into checked-in fixtures or the standard review archive
before that review.

## 2026-07-18 - Keep EVM pool imports exact-named and detached from current authority
**Status:** accepted
**Decision:** A genuine operator-made EVM pool bundle may be validated locally
without writes, then imported only behind explicit confirmation. Import reads
the source once, rejects fixture/test/mock/replay paths and provenance plus
secret-like content, and seals the exact bytes, deterministic normalized
snapshot, manifest, and completion receipt in one digest-derived immutable
namespace. Status must re-read the exact source and fully rederive the snapshot,
identity, artifact set, fingerprints, manifest, and receipt. Imports are
idempotent only when the existing namespace validates byte-for-byte. No latest
pointer is created, no campaign or dashboard authority is advanced, and no
capture becomes Protocol-v2 evidence until its exact ID is human-selected in a
sealed annex. The receipt records that the source is operator-attested and that
transport was not captured by the project. Local import makes no provider call
and creates no provider authorization.
**Why:** Immutable operator-supplied bytes provide a safe bridge for genuine
direct RPC evidence when the application has no selected or authorized live RPC
client. Requiring an exact namespace prevents an imported pool from being
silently treated as the current DEX/on-chain source, while rederivation prevents
post-import projection or metadata drift from masquerading as valid evidence.
**Revisit when:** A specific compliant RPC provider, exact genuine pool/contract
registry, request budget, and independent live authorization are approved for a
project-captured transport. That future capture may add a guarded pointer only
if current-authority semantics and rollback are separately reviewed.

## 2026-07-18 - Start DEX/on-chain evidence with exact finalized EVM pool state
**Status:** accepted
**Decision:** The first chain-native DEX/on-chain input contract covers only one
Uniswap-v2-compatible pair per bundle. It must bind `eth_chainId`, one
node-reported `finalized` block, pair `token0`, `token1`, and `getReserves`
calls, plus both token `decimals` calls. Every state call uses the exact numeric
block returned by the finalized-block query; `latest`, `safe`, `finalized`, or a
different number at the call boundary fails closed. The normalizer cross-checks
chain, pair, token, block, ABI widths, clocks, units, and exact source digest.
It emits token-unit reserve context only: no USD liquidity, price, direction,
actionability, or causal catalyst is inferred. Fixture bundles and unpersisted
operator-local imports cannot become evidence authority, campaign input, or
Protocol-v2 evidence. An operator import may prove only that its input shape is
eligible for a future immutable capture. The implementation has no HTTP client,
provider authorization, credential read, send, trade, order, paper trade, RSI
write, or Event Alpha fade path.
**Why:** The existing GeckoTerminal/CoinGecko DEX/DefiLlama fixture layer has
useful product mechanics but lacks native block identity and exact direct-source
lineage. Ethereum JSON-RPC supports state calls at a specific block, and the
Uniswap v2 pair interface exposes exact token identity and reserves. Binding
those calls to one node-reported finalized block provides honest point-in-time
context without treating an aggregator estimate or reserve ratio as execution
quality, USD liquidity, or directional evidence.
**Revisit when:** A specific compliant EVM RPC source and exact pool/contract
registry are selected for an independently authorized immutable capture, or a
different DEX contract family gets its own reviewed native-state contract. Do
not generalize the v2 ABI to v3/v4 or other pool designs.

## 2026-07-18 - Make Daily Operations the sole live market authority coordinator
**Status:** accepted
**Decision:** A live CoinGecko observation may be collected only through the
existing authorization and cadence gates, but operator authority may advance
only inside the closed Daily Operations v1.1 transition. That transition owns
the strict doctor, immutable prepublication audit, pointer publication, final
publication receipt, exact owned-dashboard restart, terminal journal,
operations receipt, HTTP identity probe, and campaign-report refresh. `make
radar-market-no-send` remains a compatibility alias for `make
radar-daily-ops-cycle`; it is not a second implementation. The lower-level
`market_no_send publish` CLI refuses direct operator publication unless an
internal coordinator supplies the explicit publication transition. Genuine
complete observations remain countable historical campaign evidence even when
they do not become current dashboard authority.
**Why:** A July 18 direct collection completed correctly but briefly advanced
the pointer without final receipts or an owned restart, leaving the old bound
dashboard process fail-closed at HTTP 503. Exact receipt-bound rollback restored
the prior authority while preserving the new observation. One coordinator
prevents evidence collection, audit truth, pointer truth, and served truth from
diverging again.
**Revisit when:** Dashboard authority, process ownership, terminal journaling,
and report publication move together to a different closed transactional
coordinator with equivalent receipts, rollback, probes, and fail-closed tests.

## 2026-07-18 - Keep historical outcome recovery separate from campaign evidence
**Status:** accepted
**Decision:** Historical outcome-price recovery may query only the exact
CoinGecko coin identity and closed missing primary-horizon window already bound
by the canonical campaign report. Readiness is no-call/no-write. Diagnostic
collection requires the existing general CoinGecko authorization, a separate
recovery authorization, and explicit confirmation; it permits one fixed-host
request per unresolved window, no retries, redirects, ambient proxy, range
expansion, interpolation, or alternate source. The first finite positive USD
price inside the original window may become a future outcome-completion input;
`no_results` remains valid evidence. Acquisition time and historical market time
must stay separate. An authorized collection intended for use must be sealed as
one immutable exact-response namespace with its request, raw response, rederived
result, campaign/source bindings, manifest, completion receipt, and rollback-
protected pointer. Status and review export must fully rederive that pointer
target before accepting it. Recovery never enters market-observation history,
temporal warmup, candidate generation, calibration, or Protocol-v2 evidence.
No outcome may be mutated until exact response bytes have an immutable capture.
Application is a separate local/no-provider `CONFIRM=1` boundary that holds the
existing root campaign lock and descriptor-anchored mutable state, revalidates
capture/source/target/current-ledger truth, changes only exact bound outcome
rows, proves market-history bytes unchanged, and writes one immutable receipt.
Any pre-receipt failure restores the exact prior ledger; receipt or exact
recovered-target drift fails closed. The immutable whole-history and
whole-ledger fingerprints
are transaction-time evidence, not a permanent freeze on later unrelated
campaign growth. Pending status must replay the exact apply preconditions under
the campaign lock without writing. After a receipt exists, current status must
reconcile its exact capture provenance and exactly one current recovered target
per bound identity; unrelated history or ledger additions do not invalidate the
receipt, while target mutation, removal, or duplication does. Recovered rows
retain explicit post-hoc lineage and remain permanently excluded from
calibration, performance, and Protocol-v2 evidence.
Campaign episode inputs must therefore mark their returns unavailable with
`historical_price_recovery_not_point_in_time`, and Decision episode scorecards
must contract-exclude those representatives rather than count them as matured
or scoreable evidence.
**Why:** A genuine historical series can close an operational outcome gap, but
post-hoc acquisition is not point-in-time campaign evidence. A distinct
authorization, exact window, immutable provenance, and ledger-only boundary
prevent recovery from manufacturing warmup, routes, or apparent predictive
evidence.
**Revisit when:** A genuine qualifying capture is ready for confirmed local
application, or a sealed Protocol-v2 annex preregisters a different recovery
treatment before its holdout is identified or read.

## 2026-07-18 - Keep overdue outcome price gaps explicit and non-interpolated
**Status:** accepted
**Decision:** A Decision Radar primary-horizon outcome may mature only from a
genuine retained price observed inside its closed post-due lag window. If no
such price exists, campaign JSON and Markdown must retain `due_missing_price`
and bind the exact price-history snapshot, due time, latest permitted time,
nearest retained observations, and resolution status. A later observation
outside the window cannot be substituted, and interpolation, nearest-neighbor
guessing, automatic threshold changes, or silent repair are prohibited. If a
qualifying retained price exists while the ledger is stale, report that an
outcome refresh can resolve it; otherwise require genuine historical
point-in-time evidence through a separately closed provenance path.
**Why:** Using the nearest later price would hide collection gaps and distort
return timing, while a bare missing count does not distinguish unavailable
evidence from a stale local ledger. Exact diagnostics preserve empirical truth
without blocking a future provenance-safe recovery.
**Revisit when:** A sealed Protocol-v2 annex preregisters a different outcome
sampling rule before its holdout is identified or read.

## 2026-07-18 - Prefer venue-native Bybit derivatives context for Decision Radar
**Status:** accepted
**Decision:** For the selected Bybit USDT-linear perpetual research surface,
Decision Radar's primary derivatives context must come from exact native Bybit
instruments: current ticker/mark/index/funding, settled funding history, 1h open
interest, and 1h long/short account ratios. Normalize each field with explicit
USDT, base-asset, fraction, percent-point, basis-point, provider-clock, and
request-lineage semantics. The offline contract may plan at most four public
GETs per instrument and 120 for the future top-30 intersection. The offline
normalizer has no HTTP client. A distinct guarded no-write collector may cross
that public boundary only after a genuine current execution-quality capture,
separately present derivatives authorization, and explicit confirmation; it
never retries and must revalidate the source capture afterward. Exact responses
remain in memory and must pass the closed derivatives-capture input contract,
which rederives every context, unit, clock, lineage row, and deterministic
capture identity from the exact bytes. Confirmed capture then writes one
descriptor-anchored immutable namespace, manifest, completion receipt, and
rollback-protected latest pointer; read-only status rederives the normalized
contexts from the raw bytes while holding the exact namespace. A complete fresh
capture may be input-quality eligible but is never Protocol-v2 evidence until
the sealed annex explicitly binds its capture ID.
Normalized context has no directional authority, cannot create a route or idea,
and remains Protocol-v2-ineligible until an immutable live capture is annex-
bound. Coinalyze
may remain a secondary Catalyst-Radar corroboration source; it must not replace
the chosen venue-native cost, funding, OI, or positioning evidence.
**Why:** Execution quality, direct bars, and derivatives crowding should share
one native instrument identity and clock domain. A third-party aggregate is
useful for cross-checking but cannot prove what was observable on the selected
venue, and silent fraction/percent conversion would reintroduce a known 100x
unit failure mode.
**Revisit when:** The human changes the execution venue/instrument decision, or
a preregistered Protocol-v2 sensitivity annex adds a second independent venue
or aggregator while preserving Bybit-native evidence separately.

## 2026-07-18 - Measure human review latency only from explicit receipt-bound actions
**Status:** accepted
**Decision:** Decision Radar must never infer a human view from dashboard GET,
HEAD, phone access, health probes, or notification rendering. One exact
receipt-backed campaign idea may receive at most one confirmed `first_viewed`
event and one later confirmed `review_completed` event in the append-only shared
review-timing ledger. `idea_observed_at` comes from the canonical Decision
projection; conservative provable `idea_available_at` is the immutable owned-
dashboard operations-receipt time. Events bind namespace, run, revision,
operator digest, candidate/Core artifact fingerprints, canonical projection,
and both final receipts. The campaign report derives point-in-time pipeline,
first-view, review-duration, and available-to-completion latency. These values
are descriptive campaign evidence only and remain Protocol-v2-ineligible until
the sealed annex binds clock, missing-action, censoring, and latency-cost rules.
They never change scores, routes, outcomes, authorization, or authority.
The read-only review queue may discover only campaign-counted ideas whose final
publication and owned-dashboard operations receipts validate. It must reload
the exact source generation and expose legacy/unpublished candidates only as
excluded counts. Historical time expiry alone may not erase a previously
receipt-backed review object, but any non-time authority defect blocks it.
The canonical campaign report must copy a freshly revalidated, path-free queue
summary separately from the event ledger: eligible, not-viewed, in-review,
complete, action-required, and skipped counts plus exact idea identities. It
must not embed machine paths or per-idea confirmed action commands. Therefore
`ledger_event_count=0` cannot be presented as if no review work exists, and a
queue row still does not become a measured view until the explicit confirmed
event is written. The standalone timing-status report remains a ledger-only
projection, but it must explicitly define its recorded-action scope, define
what its idea-record count means, and point to the queue command so
`no_events` cannot be mistaken for `no_eligible_ideas`.
**Why:** Automated requests cannot prove operator attention, while mutable or
unbound timestamps would create look-ahead and attribution ambiguity. Explicit
actions preserve the human/system boundary and exact idea lineage. Separating
queue truth from event truth prevents “not yet measured” from being rendered as
“nothing to review.”
**Revisit when:** The Protocol-v2 annex is ready to seal the human-review clock,
right-censoring/missing-action treatment, and latency-cost rule before any
untouched holdout is identified or read.

## 2026-07-18 - Preserve direct intraday evidence as immutable annex-detached captures
**Status:** accepted
**Decision:** A confirmed direct Bybit 1h/4h capture must retain the exact
accepted public responses, request/provider timing, source execution-quality
capture and pointer digest, eligible native instrument projection, rederived
bars, fingerprints, manifest, completion receipt, and latest pointer in one
immutable namespace. Publish only after exact response count, post-response
prerequisite revalidation, and complete local validation pass. Validation must
hold one descriptor-anchored namespace and rederive every bar from the raw
bytes. A fresh complete capture may be Protocol-v2 input-quality eligible, but
remains detached from the campaign, `protocol_v2_evidence_eligible=false`, and
`protocol_v2_annex_bound=false` until the sealed annex explicitly names its
capture ID. The standard review archive selects and revalidates only the latest
complete capture. Readiness and status are no-call/no-write; capture requires
the separately already-present intraday authorization plus `CONFIRM=1`; the
stdout collection target remains diagnostic.
**Why:** A valid normalized candle is not sufficient empirical provenance.
Without exact provider bytes, a closed source link, immutable publication, and
annex-detached semantics, later validation could neither reproduce the bar nor
prove that it was collected from the same execution surface before outcomes
were known.
**Revisit when:** The Protocol-v2 annex is ready to preregister exact capture
IDs and campaign attachment rules before any holdout is identified or read.

## 2026-07-18 - Gate live intraday collection behind execution-quality proof
**Status:** accepted
**Decision:** A Bybit direct-bar readiness/collection attempt must first load and
fully validate one immutable execution-quality capture whose fresh input-quality
flag is true and whose source namespace, run, revision, and operator digest
still equal current Radar authority. It then requires a separate already-present
`RSI_DECISION_RADAR_BYBIT_INTRADAY_LIVE=1` authorization and `CONFIRM=1`.
Collection performs exactly two public GETs per eligible native instrument—one
1h and one 4h—without retries, then revalidates the same capture, instrument set,
and Radar authority after the final response. The execution-quality flag never
silently authorizes intraday collection.
**Why:** Direct bars are downstream of the chosen venue/instrument mapping. A
standalone ticker query could race authority, collect a different universe, or
bypass the still-unproven Bybit execution-quality boundary. Separate capability,
authorization, and confirmation keep request budgets and operator intent exact.
**Revisit when:** One descriptor-anchored transaction atomically binds execution
quality and intraday responses for the same provider instant. Retain distinct
authorization, request accounting, raw evidence, and failure status even then.

## 2026-07-18 - Use exact completed Bybit trade-price bars for direct 1h/4h evidence
**Status:** accepted
**Decision:** Direct intraday evidence for the selected execution surface uses
Bybit V5 trade-price klines for the exact native USDT-linear perpetual
instrument, with independent `interval=60` and `interval=240` requests. Request
only through the final millisecond before the current bucket and accept only the
exact latest completed bar. Preserve native identity, OHLC, base-asset volume,
USDT turnover, request/response/provider clocks, and signed close-to-acquisition
latency. Never substitute an open candle, CoinGecko sparkline, interpolated
price, derived four-hour value, mark/index bar, or pre-horizon observation.
**Why:** Direct point-in-time bars are needed for temporal anomaly features and
outcomes, but Bybit documents an open REST candle's close as merely the latest
traded price. A deterministic completed-bucket cutoff prevents future or partial
data from entering the baseline, while explicit units avoid silently treating
USDT as USD.
**Revisit when:** Protocol v2 adds a separately preregistered mark/index-price
sensitivity analysis. Keep trade-price evidence and every alternative source
separate; never rewrite historical bar lineage.

## 2026-07-18 - Separate current-universe maturity from retained-history maturity
**Status:** accepted
**Decision:** Report two explicit temporal-baseline scopes. The current-universe
projection is defined by the exact canonical asset IDs in the fingerprint-bound
authoritative dashboard snapshot and is evaluated against the retained campaign
history. The retained-history projection continues to include every valid asset
within policy retention. Missing current IDs are visible and make the current
projection incomplete; departed historical assets never disappear silently.
Within the current-universe projection, preserve the latest exact-generation
row readiness separately from the retained history available before a possible
later observation. The latter may be described as next-cycle point-in-time
eligible only for the same observed canonical asset, at the existing global
history cadence boundary, and only when its complete retained baseline is warm.
It is not a forecast of the future universe, future feature availability,
provider success, or provider-call authorization. Keep observed non-warm IDs,
missing/unassessed IDs, and exact per-feature sample/coverage deficits disjoint
and explicitly reconcilable; an unreadable cache is unavailable rather than
honest-empty.
Do not rewrite or discard historical rows, and do not treat global retained
warmth as a substitute for the per-asset evidence used by current ideas.
**Why:** A rolling top-liquid universe naturally changes. Counting departed
assets in the same unlabeled aggregate can keep the campaign globally warming
after all current assets mature, while dropping them would destroy audit
history. Separate closed projections preserve both operator relevance and
historical truth without changing any signal or threshold.
**Revisit when:** The Protocol-v2 annex freezes an exact universe and maturity
policy. Keep both point-in-time current membership and retained-history lineage
even if their presentation or status names change.

## 2026-07-18 - Revalidate Radar authority before Bybit capture publication
**Status:** accepted
**Decision:** Resolve current trusted Radar authority once before Bybit
collection and again after the final provider response but before the first
immutable capture write. The namespace, run, revision, operator-state digest,
and full ranked Radar universe must still match. Authority expiry,
replacement, unreadability, or universe drift fails closed and publishes no
Bybit capture pointer.
**Why:** A bounded execution-quality run can span many requests. Start-time
authority alone cannot prove that the generation remained current at the
publication boundary, especially near the hourly Daily Operations cycle.
**Revisit when:** Radar pointer publication and execution-quality capture share
one descriptor-anchored transaction lock; retain equivalent exact-generation
proof even if the implementation becomes atomic.

## 2026-07-18 - Treat public Bybit depth as visible-book evidence only
**Status:** accepted
**Decision:** Execution-quality snapshot schema v2 must record the 200-level
REST limit, `rpi_orders_included=false`, and a visible-public-book liquidity
scope. Derived impact is a deterministic book walk, not realized execution. Its
size definition is exact USDT spend for buys and exact USDT proceeds for sells,
with mid-price impact as the reference. Do not describe these values as complete
venue liquidity or silently blend them with another source.
**Why:** Bybit's official order-book contract states that REST is a snapshot and
that Retail Price Improvement orders are excluded. Without explicit scope and
method fields, a mathematically correct normalization could still overstate the
completeness and empirical meaning of its depth/impact evidence.
**Revisit when:** A separately authorized source observes additional executable
liquidity or realized fills. Preserve source-specific values rather than
rewriting historical v2 snapshots or inventing a blended book.

## 2026-07-18 - Partition the Bybit query universe before the provider boundary
**Status:** accepted
**Decision:** Preserve the full liquidity-ranked Radar universe while deriving
one deterministic provider-query subset before any Bybit request. A symbol that
cannot form the closed Bybit base-contract shape is excluded with an immutable
reason code and consumes no provider request. A successful capture stores the
full universe, exact query subset, and exclusions in universe schema v2. Treat
exact Radar symbol equals Bybit base coin only as a candidate identity join;
canonical asset identity remains pending human confirmation when the exact
native instrument set is sealed in the Protocol-v2 annex. If the query subset
is empty, fail before the network boundary. If provider metadata resolves none
of the query candidates to an eligible exact active contract, fail before any
order-book request or publication rather than reporting an empty success.
**Why:** The current authoritative top 30 contains `FIGR_HELOC`, whose underscore
cannot form a valid request under the existing closed Bybit symbol contract.
Discovering that only after entering the request loop would consume or fail a
provider attempt and would obscure whether the asset vanished from the empirical
universe. Explicit partitioning keeps request bounds honest without overstating
ticker equality as canonical identity.
**Revisit when:** The project adopts a separately reviewed canonical
CoinGecko-to-Bybit instrument registry. That registry must preserve point-in-time
lineage and ambiguity/rejection evidence rather than silently widening symbol
guessing.

## 2026-07-18 - Separate selected execution surface from observed execution evidence
**Status:** accepted
**Decision:** Campaign and dashboard-facing reports must state that Bybit
USDT-linear perpetuals are the selected execution surface while independently
reporting trusted spread/depth coverage, current runtime authorization, and
immutable-capture availability. Zero coverage means evidence is unavailable; it
does not mean venue selection is still pending. Artifact-only campaign reports
must not inspect the environment and instead provide the no-network Bybit
readiness command plus the explicit-flag and `CONFIRM=1` boundary.
**Why:** The owner already selected the venue and instrument, but the regenerated
campaign report retained the older “selection deferred” sentence. Conflating a
human decision with provider authorization and observed data makes operator
truth contradictory and obscures the exact remaining action.
**Revisit when:** The selected execution venue changes through an explicit human
decision, or a sealed multi-venue Protocol-v2 annex requires the report to show
more than one independently observed surface.

## 2026-07-18 - Use closed venue-native Bybit bars for future intraday evidence
**Status:** accepted
**Decision:** When the intraday evidence step is implemented, use Bybit V5
linear-perpetual klines for the same exact frozen instruments, with explicit
60-minute and 240-minute intervals. Preserve exact requests/responses, provider
and local clocks, start/end times, OHLC, base-coin volume, USDT turnover, native
instrument identity, and lineage. Exclude the still-open newest candle from
baselines and outcomes. Keep direct 1h and 4h coverage separate; never relabel a
CoinGecko sparkline, sparse observation-to-observation return, interpolation, or
open-bar aggregation as direct venue evidence. Human review latency uses its own
audited clocks and is not inferred from provider HTTP latency. Implementation
requires a separate explicit provider authorization and remains ordered behind
the first genuine execution-quality capture; no bar is Protocol-v2 evidence
until the annex binds its exact immutable source and rules.
**Why:** Bybit documents that REST kline rows carry native OHLC, base volume,
quote turnover, and reverse start-time ordering, while the latest candle's close
is only the last traded price before closure. These semantics prevent lookahead,
partial-bar leakage, unit drift, and the current false shortcut of treating
sparse or sparkline-derived values as direct point-in-time 1h/4h evidence.
**Revisit when:** The first permitted immutable execution-quality capture proves
Bybit reachability and the intraday capture request budget/source annex is ready
to seal before any holdout is identified or read.

## 2026-07-18 - Reconcile campaign attempts by exact receipt identity
**Status:** accepted
**Decision:** Treat each immutable root `attempt_id` as one individual no-send
campaign attempt. A namespace generation/audit projection that has no attempt
ID may enrich that receipt with its exact run ID only when namespace and
observation timestamp identify exactly one receipt and terminal status, provider
result, source mode, and safety fields all agree. Preserve genuinely separate
receipt IDs even when an operator reuses a namespace. Reject ambiguous
projections and contradictory duplicate receipts instead of choosing a
convenient row or altering failure counts.
**Why:** A failed cycle is recorded both at the durable root boundary and inside
its namespace. Counting representations made the two genuine July 18 provider
failures appear as four, while deduplicating by namespace alone would erase
legitimate repeated attempts. Receipt-first reconciliation keeps both audit
surfaces and gives the campaign one coherent terminal count.
**Revisit when:** The run coordinator introduces one stronger immutable cycle ID
that is written atomically into every attempt, generation, and audit artifact;
then migrate through an explicit compatibility contract rather than silently
reinterpreting historical rows.

## 2026-07-18 - Separate immutable capture quality from Protocol-v2 evidence authority
**Status:** accepted
**Decision:** Preserve each successful Bybit public execution-quality run as one
immutable exact-response bundle: closed current Radar authority and universe,
accepted provider bytes, request/response timing, venue-native instrument
identity, normalized USDT spread/depth/impact observations, fingerprints,
manifest, completion receipt, and latest pointer. Publish only complete bundles
and fully rederive their projections from the raw bytes. A fresh complete bundle
may set `protocol_v2_input_quality_eligible=true`, but every capture remains
`protocol_v2_evidence_eligible=false`, `protocol_v2_annex_bound=false`, and
detached from the campaign until the sealed Protocol-v2 annex explicitly binds
its immutable capture ID. Never rewrite a historical capture to promote it.
Readiness and status remain no-call/no-write; capture still requires the
already-present dedicated provider authorization plus `CONFIRM=1`. The existing
403/429/region fail-closed and no-proxy/VPN/alternate-host boundary is unchanged.
**Why:** Exact bytes and clocks solve the evidence-preservation problem, but do
not by themselves preregister the universe, cost model, partitions, outcomes,
minimum samples, or untouched holdout. Keeping input quality separate from
protocol authority prevents a technically valid capture from silently becoming
selection or evaluation evidence after its results are known.
**Revisit when:** The complete Protocol-v2 annex is ready to seal one or more
specific capture IDs before holdout access. Promotion should occur in the annex
and derived protocol index, not by mutating capture artifacts.

## 2026-07-18 - Complete evidence acquisition before any Decision Radar retuning
**Status:** accepted
**Decision:** Advance Protocol v2 in this order: maintain cadence-eligible
authorized no-send market observations and reconcile every terminal campaign
state; collect venue-native Bybit USDT-linear perpetual spread, depth, impact,
clock, and instrument identity; collect direct point-in-time 1h/4h and review
latency; activate authoritative catalyst, unlock, derivatives, DEX/on-chain,
fundamental, and official-macro context; resolve missing outcomes and complete
the frozen source-independence human labels; accumulate independent route
episodes; then seal venue, universe, costs, sources, outcomes, partitions,
minimum samples, and untouched holdout in the Protocol-v2 annex before any v2
evaluation. Do not adjust anomaly thresholds, Decision scores, route policy, or
RSI conviction from the sparse live campaign or Protocol-v1 final-test evidence.
Recurring Daily Operations installation remains a separate explicit human
confirmation. Every provider uses its own already-present authorization; no
authorization, retry bypass, proxy, VPN, or alternate-region route is created.
**Why:** The current campaign has useful turnover/volume history but no warm
1h/4h evidence and no observed spread coverage. Tuning on those gaps would
convert missing evidence into false precision and contaminate the future
holdout. Ordered acquisition makes each later model change measurable and
pre-registered.
**Revisit when:** The exact Protocol-v2 annex is sealed against sufficient
independent, point-in-time evidence and its untouched holdout remains unopened;
then algorithm candidates may be proposed through that protocol rather than
applied directly.

## 2026-07-17 - Select Bybit USDT-linear perpetuals for execution-quality research
**Status:** accepted
**Decision:** Use Bybit USDT-linear perpetuals as Decision Radar's intended
primary execution-quality and Protocol-v2 cost surface. Use public market data
only, with no credentials or private account data. Define the bounded universe
as the top 30 liquidity-ranked Decision Radar assets intersected with exact
active Bybit `LinearPerpetual`, `Trading`, USDT-quoted, USDT-settled,
non-prelisting contracts, and freeze the resulting instrument IDs only when the
Protocol-v2 annex is sealed. Record the owner's 2026-07-17 confirmation of
current jurisdiction/account eligibility for this research scope. The initial
implementation is an offline V5 payload normalizer and non-executable request
description; selection does not create runtime provider authorization, permit a
live call, or authorize credentials, private data, orders, execution, or
trading. Preserve USDT-denominated depth/notionals explicitly rather than
silently claiming USD equivalence. The recorded Bybit 403 fails closed; no
proxy, VPN, or regional bypass is authorized.
**Why:** The primary cost model needs one venue-native surface rather than
generic or blended spread assumptions. Bybit USDT perpetuals match the owner's
intended instrument, while the exact identity, unit, freshness, reachability,
and preregistration boundaries prevent the choice from manufacturing usable
execution evidence before it exists.
**Revisit when:** Bybit eligibility changes, official public access remains
unreachable through the permitted environment, the owner explicitly chooses a
different primary venue/instrument, or the complete Protocol-v2 annex is ready
to freeze the exact instrument set and data/cost rules before holdout access.

## 2026-07-17 - Support macOS operator releases and keep Linux artifact archives optional
**Status:** accepted
**Decision:** Use this release support matrix: macOS normal checkout is
supported and verified; macOS source-with-artifacts archive is supported and
verified; Linux normal checkout is supported and verified in CI on Python 3.11
and 3.13; Linux source-with-artifacts archive is optional portability coverage,
currently unverified, non-release-blocking, and not Linux-certified. Close the
release-hardening goal against that supported matrix and return active priority
to Decision Radar product and empirical work. Do not install a VM/container
runtime, transfer the archive, or change the macOS host solely to obtain the
optional Linux observation. This supersedes only the earlier expectation that
Linux artifact-bearing proof was required; all filesystem security and
fail-closed requirements remain accepted.
**Why:** This personal project's production and operator environment is macOS,
where both ordinary and exact artifact-bearing releases have been verified.
Linux source-only CI already provides the required code-compatibility evidence
on both supported Python versions. Manufacturing a second host solely for an
optional archive observation adds operational risk without strengthening the
supported production boundary.
**Revisit when:** Linux becomes a supported production/operator environment, or
an appropriate Linux environment and approved archive path already exist for a
non-disruptive optional portability run.

## 2026-07-17 - Bound the complete project artifact export without deleting evidence
**Status:** accepted
**Decision:** Select ordinary source-with-artifacts evidence through the closed
`DECISION_RADAR_PROJECT_ARTIFACT_POLICY.json`. Retain exact root operator
controls, the pointer-selected generation, the latest genuine live/no-send
attempt generation, bounded shared campaign/calendar/source-contract state, and
the empirical policy's independent canonical selection. Exclude every other
fixture, rehearsal, failed, intermediate, superseded, and historical artifact
from the standard review ZIP. Preserve all excluded artifacts in place and
offer only their exact disjoint complement through the fixed optional
`make export-project-artifact-history` archive with immutable fingerprints,
manifest, and checksums. Missing optional canonical sources must render as
partial coverage rather than healthy-empty. Both exports remain descriptor-
anchored, bounded, secret-scanned, source-drift checked, no-clobber until clean,
and read-only with respect to every artifact.
**Why:** The prior empirical-only policy left 2,278 noncanonical project files
in the standard review ZIP. That obscured current operator truth, amplified
artifact-heavy verification and review cost, and made retention accidental.
An explicit project-wide canonical/history boundary keeps the routine release
portable while preserving the complete audit record without deletion, moving,
age-based guessing, or reinterpretation.
**Revisit when:** A human approves a versioned policy change for a new canonical
shared store, selector, retention bound, or history boundary. Never infer
canonical status from newest-directory order, modification time, or fixture
availability.

## 2026-07-17 - Keep multiple-venue mode comparative and require one primary v2 cost surface
**Status:** accepted
**Decision:** Include multiple-venue research as an explicit operator option,
but preserve each venue's native quote, identity, spread, depth, impact,
eligibility, and request budget independently. Comparative evidence may test
robustness; it cannot close Protocol-v2's primary execution-cost model until the
operator seals one exact primary execution surface. The readiness package
selected nothing when this decision was accepted; the later 2026-07-17 Bybit
USDT-perpetual decision supersedes only that no-selection state. The
comparative-mode boundary still requests no credential, private data, wallet,
order, or trading permission.
**Why:** Cross-venue evidence can reveal venue sensitivity, but blending books
or leaving the executable venue undefined would manufacture cost precision and
make a preregistration changeable after results are visible.
**Revisit when:** The operator completes the exact venue/instrument/quote/set,
jurisdiction/account, and public/private-data decision template before any
Protocol-v2 holdout is defined or opened.

## 2026-07-16 - Bound the standard empirical export without deleting history
**Status:** accepted
**Decision:** Select empirical evidence for the normal source-with-artifacts ZIP
only through one checked-in, closed policy that binds the exact canonical
fixture, medium, selection, and final-test manifests; frozen protocol artifacts;
seven v1 reports; the separate hardening supplement; and bounded optional human
feedback. Preserve every superseded local artifact in place. Its exact disjoint
complement may be copied only to one fixed optional research-history ZIP with an
immutable manifest and checksums. Both exports are descriptor-anchored,
bounded, secret-scanned, no-clobber until validation succeeds, and read-only
with respect to evidence. The standard exporter must validate the supplement
against the same exact seven report bytes and reuse the fingerprints from that
semantic pass rather than silently accepting later bytes.
**Why:** The lab held 439 files and 972,516,087 logical bytes, most of them
superseded immutable runs. Shipping every run in every review ZIP made the
release gate slow and obscured the canonical evidence, while deletion or moving
would destroy audit history. The explicit selection plus optional complement
keeps ordinary review bounded without weakening reproducibility or retention.
**Revisit when:** A human approves a new canonical run set or a different
retention limit through a reviewed policy revision; never infer it from file age
or newest-directory order.

## 2026-07-16 - Publish empirical hardening only as a separate closed supplement
**Status:** accepted
**Decision:** Keep the seven Protocol-v1 reports and their bundle identifier
immutable. Publish route-conditioned calibration, development/validation
market-risk grouping, and the operator-first negative conclusion only in one
separately attested supplement bound to the exact selection run, exact seven
report bytes, and a deterministic diagnostics-code contract. The supplement
must reject nonselection/final-test inputs before opening any non-manifest run
leaf, use bounded descriptor-walk I/O, validate a closed schema, and resume only
identical existing bytes; a different fixed output fails without clobbering.
Raw Protocol-v1 final-test data remains unopened by this workflow. Already
sealed v1 final summaries may be copied for clearly labeled display only and
may not select a scenario. Diagnostics remain descriptive, outcome-blind where
specified, `policy_eligible=false`, and never auto-apply.
**Why:** The requested calibration and operator-readability improvements are
useful, but rewriting the sealed v1 evidence or letting a self-attested/open
extension read the holdout would invalidate the empirical firewall. A closed,
separate, immutable supplement adds reproducible diagnostics while preserving
the measured negative result and production policy.
**Revisit when:** A human approves a fully sealed new protocol with genuinely
new evidence and an untouched holdout, or the supplement itself needs a new
explicitly versioned revision rather than an in-place rewrite.

## 2026-07-16 - Freeze Protocol-v2 evidence requirements before its executable protocol
**Status:** accepted
**Decision:** Freeze the static Protocol-v2 required-evidence and annex contract
at SHA-256 `683f03fe74306a80acaebf2556e2652cc67e9c725d97deb6dd083b3b28109603`,
while keeping the executable protocol explicitly unfrozen and blocked. No v2
replay, selection, or final-test target may exist until a human-approved exact
annex binds venue/instruments, genuine point-in-time sources, partitions and an
untouched holdout, outcomes, costs, universe, existing route definitions,
episode rules, and minimum samples. Protocol-v1 final-test evidence is forbidden
for v2 tuning. Missing required evidence stays unavailable and cannot be
invented or proxied.
**Why:** Calling v2 frozen before the execution venue and exact data sources are
known would create a changeable protocol disguised as a preregistration. The
static contract closes what must be decided while preserving a verifiable zero-
access firewall around a future holdout.
**Revisit when:** The owner supplies the execution-quality decision template and
all remaining acquisition/statistical annex sections can be sealed before any
holdout content is identified or read.

## 2026-07-16 - Require descriptor-walk security for empirical filesystem inputs
**Status:** accepted
**Decision:** Replay input directories, their regular-file leaves, and optional
feedback-ledger parents/leaves must be reached by descriptor-relative traversal
from the filesystem root. Every component is no-follow stated, type-checked,
opened relative to the verified parent descriptor, fstat-checked, and compared
by device/inode; leaves additionally bind size and modification snapshots across
reads. Missing feedback ledgers use exclusive creation. A supported runtime
without the required descriptor-relative/no-follow facilities fails closed and
must not skip the regression.
**Why:** A no-follow flag on one full pathname does not protect symlinked parent
components, and non-exclusive create leaves a check/create substitution window.
Empirical evidence and human preference data cannot be trustworthy if either
path may be redirected outside the operator-selected tree.
**Revisit when:** The project adopts an equally strict shared secure-path API
whose behavior and component/leaf replacement regressions are proven across
the supported release matrix. Linux artifact-bearing coverage remains optional
unless Linux becomes a supported production/operator environment.

## 2026-07-16 - Treat the empirical lab as bounded research debt, not a generation namespace
**Status:** accepted
**Decision:** Keep the 1,200-line production target and 1,500-line blocker
unchanged. The six frozen empirical implementation modules and the shared
dashboard renderer that currently fall between those limits are documented
target-gap exceptions with path-specific reasons and mandatory split
conditions. The exact `decision_radar_research_lab` artifact root is an
immutable, non-authoritative research store with `manual_review` retention; it
is not an Event Alpha operator generation and cannot become authority.
**Why:** Release verification correctly exposed that the new research modules
had not been reconciled with the existing architecture contract and that the
artifact inventory mistook the lab's run store for an unknown generation.
Splitting frozen replay logic after opening the sealed holdout would change its
behavior-bearing code digest and force a new protocol evidence chain. Explicit
bounded exceptions preserve the measured evidence while keeping every file
below the unchanged hard blocker and every function below its blocker.
**Revisit when:** Any accepted file grows further, crosses 1,500 lines, adds a
new behavior or schema family, or gains digest-stable extraction fixtures; then
split it before the feature lands. Revisit the artifact-root classification
only if the lab is intentionally redesigned as an operator generation, which
would require a separate authority contract.

## 2026-07-16 - Keep Decision Radar production policy unchanged after protocol-v1 validation
**Status:** accepted
**Decision:** Apply none of the nine frozen shadow-policy changes evaluated by
Decision Radar empirical-validation protocol v1. The full top-100 development
and validation selection found every material scenario `not_supported`; the
pre-frozen final-test candidate set was therefore empty. The final-test lane may
only report `no_candidate_recommendations`, not perform a post-hoc policy
search. An initial selection/holdout pair with a trace-histogram aggregation
defect is retained but superseded; its results cannot tune the unchanged
replacement run. The replacement evidence is selection
`8212b2ddb626805f4312d8986cc1d9f6b3229a169aa49ca75b9b5bbfc1660489`,
final test
`3009e23dd9a9f11418cf97ee07f6e532c451c21196e69bd1ae0cd6ae96c47e72`,
and closed seven-file report bundle
`267a1c6d30488fcd7088bf20ce6f653df6bf79f82c5e7d401e27fd4b24debbcf`.
The preceding valid `e906229...` / `c436158...` / `75d505...` evidence remains
immutable but is superseded for current-code reproducibility because correcting
locked-pandas microsecond timestamp normalization changed the behavior-bearing
code fingerprint. Its conclusions were not used to tune the unchanged rerun.
Thresholds, routes, dashboard authority, notifications, execution, and provider
authorization remain unchanged.
**Why:** The complete selection run produced useful descriptive evidence for
market-led `dashboard_watch`, `risk_watch`, and `diagnostic` ideas, but no frozen
policy scenario satisfied the multi-metric selection rule. Five routes and six
primary origins still have zero empirical episodes, historical spread and
intraday execution are unavailable, and live no-send evidence remains an
insufficient-sample observational lane. A policy change would exceed the
evidence and violate the frozen holdout contract.
**Revisit when:** A new protocol version is frozen before accessing its holdout
and adds genuinely independent evidence, especially observed execution quality,
intraday timing, and point-in-time catalyst/calendar/derivatives/on-chain data.
Any later change still requires a separate explicit human decision.

## 2026-07-16 - Quarantine partition tails before opening the empirical holdout
**Status:** accepted
**Decision:** Treat each partition's maximum 14-day outcome tail as an
outcome-only embargo in which no new ideas may be evaluated. Development ideas
end on 2023-01-01 and may mature only through 2023-01-15; validation ideas begin
on 2023-01-15, end on 2025-01-01, and may mature only through 2025-01-15; the
clean final-test idea window begins on 2025-01-15. The nominal 2025-01-01 through
2025-01-14 tail is quarantined from final evidence because an early validation
sensitivity pass indirectly read those prices before the firewall audit, even
though no per-idea final-test result was inspected.

Every outcome horizon must be due strictly before its partition outcome
boundary. Walk-forward training and test sets purge primary outcomes whose due
time reaches the fold boundary, and omit a final fold shorter than the frozen
180-day test length. Recommendation seals bind one deterministic
`noninferior_return_failure_selected_day_burden_v1` selection rule over the
exact selected UTC-day denominator, including zero-idea days. The final test may
only confirm, reject, or report insufficient sample for those sealed candidates.
All earlier medium runs remain immutable but are superseded for selection.
**Why:** A nominal date label is not an effective holdout when validation
sensitivity outcomes can read its prices. Explicit embargoes and outcome-time
purges restore a testable no-lookahead boundary without concealing the discovered
contamination or silently discarding historical audit evidence.
**Revisit when:** A new protocol version freezes different idea/outcome
boundaries before accessing any of its own confirmation data. Protocol v1 must
retain this quarantine permanently.

## 2026-07-16 - Bind empirical holdout access to one complete selection run
**Status:** accepted
**Decision:** An empirical final-test run may load a recommendation seal only
from a complete immutable `full` top-100 development/validation run. The seal
must bind that run's fingerprint, input, code, configuration, protocol, exact
frozen scenario definitions, simulation bytes, and complete artifact manifest.
The final-test loader reads and verifies the whole run through one no-follow
bundle contract before it reads the seal, and then requires the final input and
behavior-bearing code digests to match. A medium run, loose copied seal,
mutated simulation, behaviorally identical scenario, or partial bundle cannot
authorize holdout access.

Fixed-start daily episodes include an observation exactly 24 hours after the
first representative; only a later timestamp starts a new episode. The frozen
volume-z feature has a 90-day lookback with 20 prior observations required.
Daily RSI and point-in-time volume rank are retained as observational context,
not score or route inputs. Historical runs produced under the earlier exclusive
boundary remain immutable audit artifacts but are superseded for selection.

Persisted replay evidence uses bounded plaintext shards with one canonical
Decision projection per idea and digest-bound episode references. Targeted
review is descriptive; optional human labels live in a separate confirmed,
append-only, exact-queue ledger and never auto-apply to scoring or policy.
**Why:** Holdout credibility depends on independent episodes and on proving that
the evaluated recommendation is exactly the one selected before final-test
inspection. Compact, inspectable persistence keeps the same evidence viable at
top-100 scale without weakening path, secret, or immutability checks.
**Revisit when:** A new protocol version freezes a different cadence, episode
boundary, feature warm-up, selection partition, or holdout before accessing its
own final test. Historical protocol-v1 evidence must never be rewritten.

## 2026-07-16 - Keep empirical Research Lab evidence outside production authority
**Status:** accepted
**Decision:** Render empirical validation, walk-forward, shadow-policy, and live
no-send evidence inside the existing Decision Radar dashboard, but read it from
the exact seven fixed filenames in the closed report contract: validation,
walk-forward, and policy-simulation Markdown/JSON pairs plus the limitations
Markdown. One descriptor-anchored read must acquire the bounded bytes, and the
whole bundle must validate before any semantic projection is rendered. It is an
authority-independent research projection. Research can remain inspectable when
a production generation is stale, provided it is labeled descriptive/historical
and never restores or implies current actionability. Missing, invalid, unsafe,
oversized, spliced, or digest-drifting reports suppress the complete semantic
bundle; they never become zero evidence. GET/HEAD cannot write, inspect provider
authorization, change a threshold/route, or mutate dashboard authority, and
shadow recommendations do not auto-apply.
**Why:** Operators need one coherent product surface for empirical evidence,
including negative and insufficient results, without allowing research files or
stale production data to bypass exact-generation publication safeguards.
**Revisit when:** Research evidence is moved to another immutable store with
equivalent fixed-source, byte-bound, schema, no-follow, read-only, and
authority-separation guarantees.

## 2026-07-16 - Freeze Decision Radar empirical-validation protocol v1 before final-test evaluation
**Status:** accepted
**Decision:** Use `decision_radar_empirical_validation_v1` as the immutable
research protocol for the first Decision-v2 historical replay. It fixes the
daily completed-candle observation clock, trailing 30-day point-in-time quote-
volume universe, 2021-06-12 through 2026-06-01 idea window, embargo-separated
development/validation/final-test partitions, 3-day primary outcome, 1/7/14-day
sensitivity outcomes, fixed-start 24-hour episodes, outcome-blind matched
controls, predeclared missed/false/late rules, deterministic episode bootstrap,
cost scenarios, minimum samples, operator-burden budgets, and the complete
shadow scenario set. Development and validation may nominate a recommendation;
the final test may only confirm or reject its already-hashed bytes.

The locally cached Binance universe is point-in-time by trailing volume only
inside the retained candidate pool and must carry its residual delisting-
survivorship limitation. Daily OHLCV cannot be presented as intraday timing or
observed spread. Missing catalyst, calendar, derivatives, on-chain, market-cap,
and order-book evidence stays missing or unavailable. A partial/early-close
daily bar is inventory evidence only: it resets contiguous feature warm-up and
cannot enter point-in-time membership, a warm baseline, or an idea. Fixture route coverage is
mechanical evidence only. The lab is research-only, `auto_apply=false`, and
cannot mutate production thresholds, routes, policy, authorization, dashboard
authority, sends, trades, paper trades, RSI rows, or `TRIGGERED_FADE`.
**Why:** Choosing partitions, outcomes, missed-move thresholds, or scenarios
after viewing final-test Decision results would make the apparent validation
non-reproducible and outcome-leaking. Freezing the limitations as well as the
parameters prevents unavailable data from being silently converted into a
stronger claim.
**Revisit when:** A new protocol version is proposed before its own untouched
holdout is evaluated. Historical v1 results and bytes remain immutable; any
production policy change still needs independent human approval, a versioned
decision, and rollback criteria.

## 2026-07-16 - Treat Event Alpha profiles as capability, never authorization
**Status:** accepted
**Decision:** A profile may describe which live source or OpenAI stage it can
use, but a true profile override is not current authorization. Every live
provider factory must additionally observe its already-present explicit
environment/`.env` opt-in at execution time. Readiness must display profile
capability, current explicit authorization, required credential presence,
persisted provider health/backoff, and current call eligibility separately,
without exposing credential values or inspecting Telegram configuration.

Live-style evidence dispatch has no fixture/default fallback. Fixture,
test, mock, and replay local paths are invalid for live-style evidence;
Coinalyze and sports planner hints remain unavailable until a real adapter is
implemented. Eligible providers reuse the existing `event_source` health
circuit breaker. Relationship analysis, extraction, and catalyst-frame OpenAI
stages each require their own already-present explicit opt-in; a credential or
profile capability cannot authorize another stage. Offline fixture LLM
evaluation does not need live authorization because it crosses no provider
boundary. The observational readiness command never writes or calls a
provider. Its HTTP bound covers evidence-acquisition planner fan-out only and
explicitly excludes discovery, market, enrichment, and LLM work. A writing evidence cycle
requires a passing bounded readiness guard, at least one currently eligible
genuine source, a unique namespace, alerts disabled, and explicit `CONFIRM=1`;
it never creates authorization and unavailable hints fail soft without a call.
**Why:** Notification-quality profiles previously enabled source flags as a
convenience, so operator output could describe GDELT/RSS/Polymarket as live
authorized even when the current environment had granted no such authority.
That blurred capability with consent and left fixture-backed dispatch paths in
a supposedly live evidence cycle.
**Revisit when:** A versioned authorization service replaces environment flags
with equivalent explicit operator consent, bounded call ledgers, rollback, and
runtime/readiness parity. Fixture evidence must remain structurally unable to
become real authority.

## 2026-07-16 - Freeze source-independence OOS partitions by event-copy family
**Status:** accepted
**Decision:** Source-independence review corpus split v3 assigns the complete
`event_copy_family_id` to one deterministic `development`, `review`, or `test`
partition. Validation rejects family IDs, exact source digests, or exact
normalized-content digests reused across partitions. Review categories are
exact syndicated copy, lightly edited cross-domain copy, independently
reported same-event article, same-domain original update, contradiction, short
headline, and control. Pending labels can be structurally valid but return
non-success; a report is complete
only after independent OOS coverage is complete. Metrics remain descriptive
and cannot auto-apply policy. Persisted reports use strict non-boolean schema
integers, closed splits/categories, bounded ratios, and count-closure checks.
The readiness surface may summarize proposed case structure and frozen-stage
completeness, but it must not show per-case split assignments or algorithm
predictions, write a file, create a human label, or treat a fixture as genuine
evidence. Human review uses only a separate operator-owned copy of the immutable
blind template; the frozen corpus is not a labeling surface.
**Why:** Splitting individual article pairs can leak the same syndicated story
family into development and test, overstating precision and recall. Family-
indivisible partitions preserve the intended out-of-sample claim.
**Revisit when:** Enough independently reviewed development/review/test labels
exist to evaluate the frozen normalization, 12-token minimum, and `0.80`
Jaccard threshold. Any score, route, threshold, or normalization change still
requires explicit human approval and a separate rollback-backed decision.

## 2026-07-16 - Store new source-independence contracts by immutable reference
**Status:** accepted
**Decision:** Persist each new validated `event_alpha.source_independence` value
once in the exact artifact namespace under
`event_source_independence_contracts/<semantic-digest>.<blob-sha256>.json` and
copy only the closed `event_alpha.source_independence_reference` v1 value into
new downstream rows. A reference must carry the schema/version, canonical
store directory and relative path, semantic digest, exact file fingerprint and
byte size, validation state, research-only flag, and the raw/cluster/
independent/corroboration/origin/copy count summary. Resolve it only after
descriptor-anchored no-follow reading, complete reference validation, exact
fingerprint/canonical-byte verification, semantic digest verification, and
summary equality. Bind the canonical store directory and fingerprint into
operator state and strict doctor whenever references exist; alternate store
paths, missing objects, symlinks, mutation, or ambiguous summaries are
blockers. Cache only references whose complete canonical reference bytes are
identical.

Keep validated historical inline contracts readable and idempotent, and never
silently migrate their representation during an unrelated artifact rewrite.
Prepare all externalization/serialization before atomically replacing a row
artifact so a store failure cannot truncate prior evidence. Full contract and
technical digests remain available in technical details; primary cards and
dashboard surfaces lead with the bounded evidence-count summary. This storage
decision changes neither the source-independence algorithm nor any score,
threshold, route, publication, provider, or safety policy.
**Why:** One self-validating evidence object was copied across many canonical
surfaces, increasing artifact/export size and read work while creating a new
failure point for historical rewrites. Content-addressed namespace-local
storage preserves exact evidence reality and cross-artifact consistency with a
smaller operator footprint, while explicit inline compatibility protects audit
history.
**Revisit when:** A versioned store migration has independent corruption,
performance, export, and rollback evidence and an explicit policy for
historical representation changes. Garbage collection or deletion requires a
separate retention decision and must never infer that an old inline/reference
contract is disposable from current routes alone.

## 2026-07-15 - Count independent catalyst evidence by origin-aware content units
**Status:** accepted
**Decision:** Measure source independence with the closed
`event_alpha.source_independence` v1 contract before describing catalyst
corroboration. Preserve raw-document count, canonical-domain count, content
cluster count, independent evidence units, and additional independent
corroborations as distinct quantities. Normalize the exact title/newline/body
surface with Unicode NFKC, casefolding, alphanumeric-whitespace projection,
whitespace collapse, and trim; exact duplicates share that surface digest.
Compare assessable non-exact documents as sets of consecutive three-word
shingles and treat Jaccard similarity at or above `0.80` as near-duplicate.
Assign a document only against canonical representatives in deterministic
public-time/source-id order; do not use transitive member-to-member chaining.
An independent evidence unit must be a corroboration-eligible content cluster,
and every selected unit after the first must introduce a canonical origin not
already represented. Content-distinct rows from an already represented origin
may remain additional context but cannot increment independent corroboration.
Missing origin or assessable content stays unassessable; malformed or
overflowing inputs stay rejected; fixed document, text, URL, metadata, and
shingle bounds fail closed without truncating evidence into apparent support.
Persist full input statuses/digests, assignments, reasons, count closure, and a
closed contract digest. The result explicitly does not assess source authority,
ownership independence, claim truth, impact validity, causal attribution, or
statistical independence. It is research-only and cannot weaken a blocker or
threshold, apply calibration, publish authority, send, trade, paper trade,
execute, write normal RSI rows, or create Event Alpha `TRIGGERED_FADE`. The
contract may replace raw-row or hostname counts in existing diversity bonuses
and gates, so duplicate-derived scores, priority, or routes can fail closed; it
cannot introduce a new positive promotion mechanism.
**Why:** News syndication and lightly edited copies can turn one underlying
story into many provider rows or domains, inflating apparent corroboration.
Rodier and Carter's LREC 2020 work supports shingle-based online near-duplicate
detection; the project deliberately adds a fixed conservative threshold,
origin eligibility, non-transitive representative assignment, complete
rejection telemetry, and no-authority/no-causality semantics for operator
truth. See `research/SOURCE_INDEPENDENCE_NEAR_DUPLICATE_POLICY.md`.
**Revisit when:** A labeled, source-diverse corpus supports a predeclared
precision/recall study of the normalization, minimum length, and `0.80`
threshold, including syndicated cross-domain articles and same-domain original
reporting. Any new positive promotion, threshold change, or calibration effect
beyond the accepted one-for-one replacement of legacy raw-row/hostname
diversity inputs requires a separate outcome-backed, out-of-sample,
human-approved policy with frozen thresholds and rollback criteria.

## 2026-07-15 - Require temporal-semantic attribution for current catalyst confirmation
**Status:** accepted
**Decision:** Bind each current catalyst-confidence claim to one exact source
and one exact market anomaly with the closed
`event_alpha.catalyst_attribution` v1 value. Use `published_at`, falling back to
`fetched_at`, as the source-public clock and keep claimed `event_time` separate.
Bind the anomaly id and clock to a digest of its provider/content identity,
canonical asset, snapshot identity, market state, anomaly bucket, and exact
market snapshot. Reject foreign bindings and mixed valid/invalid supplied sets
as a whole while retaining explicit rejection telemetry.
Treat a source more than five minutes after the anomaly as retrospective
context; background, historical, market-reaction, and side-note roles as
context-only; and negated, corrective, denied, or ruled-out evidence as
disproof. A future scheduled event may be anticipation evidence only if its
source was already public. Missing or timezone-naive clocks are unknown and
noncausal. Causal eligibility additionally requires direct official evidence or
a validated direct beneficiary with a strong impact path. Copy the same
digest-bound attribution through discovery, alert evidence, integrated
candidate, CoreOpportunity, canonical Decision projection, and outcomes. Once a
current row supplies attribution, malformed or exclusively noncausal evidence
cannot fall back to official-hostname, source-class, or accepted-count
confirmation. Preserve historical rows without attribution under the prior v2
compatibility heuristic and never rewrite their bytes. Attribution remains
research-only, `auto_apply=false`, and neither precedence nor an official source
alone proves causality.
**Why:** The prior merge could label an official article published after a
market move—even one explicitly marked background context—as a confirmed
catalyst and promote the idea to `high_confidence_watch`. Separating information
availability from claimed event time removes look-ahead attribution while
retaining useful retrospective context and scheduled-event evidence.
**Revisit when:** A versioned outcome study with frozen anomaly/source windows,
matched non-idea controls, dependency-aware uncertainty, and out-of-sample
evidence supports a different contemporaneous window or causal eligibility
rule. Any routing or threshold change requires a separate human-approved
decision.

## 2026-07-15 - Score frozen anomaly representatives with canonical Decision-v2 outcomes
**Status:** accepted
**Decision:** Evaluate only the chronologically first representative frozen by
each fixed-start 24-hour anomaly episode. Repeats never replace that row based
on outcome availability. Use only the declared canonical primary horizon for
`matured`, `not_due`, `due_missing_price`, or `contract_excluded`; secondary
maturity cannot promote it. Grade alignment from canonical Decision-v2
`directional_bias`, never a legacy Event Alpha lane. Bind the exact candidate,
CoreOpportunity, and campaign outcome through namespace, run, identity, row and
artifact digests, equal Decision projection, and exact
`Core.integrated_candidate_id`. Preserve score cohorts exactly; the sole
historical compatibility is an explicitly labeled derivation of missing
evidence/risk cohort labels from unchanged bounded canonical scores, without
rewriting history. Every other partial, unsupported, or mismatched cohort fails
closed. The scorecard is descriptive and always concludes
`insufficient_for_policy_change` while matched non-idea controls,
dependency-aware uncertainty, or out-of-sample validation are absent. It cannot
call providers, write source evidence, trade, send, create paper/RSI/fade rows,
or change routes, priority, Decision scores, calibration, thresholds,
publication authority, or policy automatically.
**Why:** Frozen representative selection avoids outcome-conditioned survivorship
bias, primary-horizon censoring avoids promoting an idea from a convenient
secondary result, and exact Decision/Core/ledger bindings make cohort evidence
auditable without silently reinterpreting historical rows.
**Revisit when:** Enough primary representatives have matured to support
predeclared matched controls, dependency-aware uncertainty estimates, and a
genuine out-of-sample comparison. Any runtime use requires a separate versioned
human decision with frozen thresholds and rollback criteria.

## 2026-07-15 - Measure repeated anomalies as fixed-start shadow episodes
**Status:** accepted
**Decision:** Partition validated market-anomaly candidates from campaign-counted
real/no-send generations by exact canonical asset into fixed-start, half-open
episodes. The primary window is 24 hours, with 12/24/48-hour sensitivity views
computed from the same member population. The first exact observation is
selected solely from identity and time, independently of outcome availability,
maturity, route, score, or return; repeats never slide the boundary and later
mature rows never replace it. Membership binds namespace, run, candidate,
canonical outcome, market-anomaly, asset, and UTC observation identity. Inspect
raw campaign-outcome multiplicity before the compatibility deduplication view,
and keep missing, invalid, duplicate, conflicting, colliding, and orphan rows
explicit. One row claimed by several candidates is one cross-candidate
collision component, never one duplicate group per claimant. Episode counts are
descriptive: they do not claim statistical or cross-asset independence and are
ineligible for routing, priority, Decision scoring, calibration, threshold
changes, publication authority, or automatic application. All member and
exclusion references remain complete within fixed 256-row bounds; exceeding
either bound fails closed without a contract.
The campaign captures each manifest-bound candidate artifact and the mutable
outcome ledger once, reuses those exact snapshots across headline and episode
surfaces, and persists a closed input audit with count closures, snapshot and
episode digests, explicit ledger/input statuses, and zero-side-effect constants.
**Why:** Successive campaign cycles can observe one persistent move through
overlapping rolling features and outcome horizons. Counting every observation
as an independent result would inflate the apparent evidence base, while
outcome-aware representative selection would introduce survivorship bias.
Fixed-start episodes make dependence visible without changing runtime behavior.
**Revisit when:** A sufficiently large set of matured primary-horizon episode
outcomes and matched non-idea controls supports predeclared cohort analysis,
dependent-data uncertainty estimates, and out-of-sample comparison. Any runtime
promotion requires a separate versioned decision with frozen thresholds and
rollback criteria.

## 2026-07-15 - Keep robust temporal surprise shadow-only until measured
**Status:** accepted
**Decision:** Compare provider-observed 24-hour volume and provider-observed or
explicit provider-ratio turnover with a versioned, log-median/MAD temporal
surprise value over same-asset, strictly earlier, cadence-counted observations.
Derived turnover is eligible only when it matches provider volume divided by
provider market cap within fixed `1e-9` relative and `1e-12` absolute
tolerances; an independently supplied turnover defaults to provider-observed.
MAD at or below `1e-12` yields no robust z-score, and the add-one upper-tail
rank is descriptive rather than a p-value. The calculation reads one exact
fingerprinted generation-history buffer after anomaly classification, records
its safe basename and SHA-256 in the closed value, and rewrites the complete
scanner bundle only while the original namespace device/inode and input hashes
still match. It attaches only top-level snapshot/anomaly diagnostic metadata.
It never mutates
provider source or retained history, enters a nested market snapshot, copies to
Decision candidates/outcomes, changes a route/priority/score/threshold, or
applies automatically. Missing, ineligible-basis, invalid, insufficient, and
degenerate samples remain explicit. Non-unique current observation identity,
canonical-asset drift, source duplication, or history fingerprint drift fails
closed.
**Why:** The canonical mean/standard-deviation temporal features are sensitive
to the skew and isolated extremes common in crypto activity series, but there
is not yet episode-level outcome/control evidence that a robust alternative
improves decisions. A closed shadow comparison creates measurable evidence
without changing trader-facing truth prematurely.
**Revisit when:** Matured Decision outcomes and matched non-idea controls are
evaluated at anomaly-episode level with coverage, degeneracy, provider/basis,
false-positive, calibration, and confidence-interval reporting. Any promotion
requires a separate versioned decision, frozen thresholds, rollback criteria,
and proof that the new feature adds out-of-sample value.

## 2026-07-15 - Bind LLM catalyst frames to exact immutable source evidence
**Status:** accepted
**Decision:** An LLM catalyst-frame analysis is eligible for deterministic
validation only when its `raw_id` resolves to exactly one supplied raw row.
Every accepted quote must match one normalized contiguous span inside that
row's title, body, or quality-gated enriched text; event summaries, adjacent
rows, cross-field concatenation, and fuzzy term overlap are ineligible. Current
validation persists the raw/provider/URL/publication identity, original content
hash, fetch clock, source confidence, canonical evidence-surface and controlled
enrichment-provenance hashes, source field, normalized offsets, and exact
analysis/validation payload digests on the closed validation and frame. Closed
keys, enums, primitive types, finite bounded confidence, canonical frame ids,
source-evidenced subjects/entities, and boundary-safe short ticker identity are
revalidated before use. Application and rehydration fail closed if any binding
drifts. Invalid or ambiguous analysis identity remains fail-soft unresolved
instead of crashing the cycle. Legacy unbound validation remains unchanged
historical data but does not rehydrate as current LLM evidence. Provider output
remains a semantic proposal schema and does not self-attest these deterministic
bindings.
**Why:** The previous validator merged all raw and normalized-event text,
ignored the analysis `raw_id`, accepted an 80-percent bag-of-words overlap, and
stamped valid frames with the first raw. A quote from one article could
therefore be laundered into another article's provenance and remain trusted
after source mutation.
**Revisit when:** A versioned evidence format can prove byte offsets directly
against immutable provider bytes. It must retain single-source resolution,
quality gating, deterministic binding, and fail-closed revalidation.

## 2026-07-15 - Derive catalyst source authority from canonical identity only
**Status:** accepted
**Decision:** Official exchange, official project, structured, derivatives,
supply, market-data, prediction-market, and named-news source classes are
derived by the canonical source registry from exact provider ids or exact/child
trusted hostnames. Article text, `source_origin`, caller-provided class hints,
generic `official` language, shared Medium/GitHub hosting, and suffix look-alike
domains cannot establish authority. `project_blog_rss` is a transport rather
than automatic official-project attestation. Evidence-quality scoring reuses
the registry's authority and confidence cap. A source pack validates an impact
path only when the registry class is in that pack's declared validator set;
`can_validate_impact_path` is not a fallback bypass. Unverified claims remain
capped context with `source_authority_unverified`. Existing historical bytes
are preserved rather than silently reclassified in place.
**Why:** Content mentioning an exchange could previously classify an unrelated
GDELT article as an official exchange source, and arbitrary Medium/GitHub pages
could become official project evidence. Those labels minted official proof
tokens and could satisfy deterministic source-pack gates.
**Revisit when:** A versioned project-domain ownership registry or signed source
attestation is implemented. Shared-host ownership must be proven explicitly;
it must never be inferred from article wording or a generic hosting domain.

## 2026-07-15 - Reject impossible catalyst source clocks before attachment
**Status:** accepted
**Decision:** Catalyst-search evidence whose `published_at` or `fetched_at` is
more than five minutes after the explicit evaluation clock receives score zero,
is rejected before attachment, and records `source_timestamp_in_future` plus the
offending field. This is a hard validity rule even if the ordinary result-score
threshold is configured to zero. A future structured `event_time` remains
valid when the article publication/fetch clock is current because scheduled
event time and evidence-availability time are separate facts.
**Why:** Clamping a negative source age to zero converted impossible chronology
into the strongest freshness bucket and could promote evidence that did not yet
exist. The five-minute tolerance matches the existing bounded market-clock skew
policy without weakening identity, provenance, or score gates.
**Revisit when:** Provider-specific signed timestamps justify a different
bounded skew tolerance through an explicit source contract; never infer a wider
tolerance from content or score.

## 2026-07-15 - Close Daily Operations publication with phase-specific receipts
**Status:** accepted
**Decision:** Daily Operations v1.1 preserves the immutable prepublication
attempt audit, writes an immutable `published` receipt only after strict-clean
exact pointer publication, and writes an immutable `dashboard_restarted`
operations receipt only after the owned dashboard is running and terminal
success is journaled. All receipts bind namespace/run/revision, operator-state
digest, artifact fingerprints, doctor result, and pointer digest. Campaign and
dashboard history must show attempt, publication, operations, and current
authority as separate facts; a managed current generation with missing or
contradictory final evidence is blocked. Legacy reconciliation is an explicit
no-provider/no-restart command limited to one exact prior successful terminal
cycle and is never automatic from readiness. Revalidating an unchanged
authority is byte-idempotent for the pointer. Reconciliation may restore an
older receipt-bound pointer only when every authority field is unchanged and
the sole drift is the pre-v1.1 readiness refresh of `authority_checked_at`;
broader pointer drift remains blocked.

The owned dashboard may bootstrap from an exact current pointer after the
final publication receipt exists but before the operations receipt exists;
every GET/HEAD remains 503-closed during that narrow transition. Daily
Operations writes and validates the operations receipt, then requires a
successful HTTP probe bound to exact namespace/run/revision/operator headers and
the same positive owned PID before reporting terminal success. Pointer publish,
rollback, invalidation, and reconciliation share one descriptor-anchored
mutation transaction, so an artifact-root pathname replacement cannot redirect
pointer I/O. Rollback restores only the exact saved bytes whose mapping and
digest match the prior immutable publication receipt. Any later failed terminal
row for the same cycle invalidates the earlier success receipt.

Authorization at the last cycle is historical. Current authorization and
provider-call eligibility come only from a bounded credential-free readiness
receipt that expires after 15 minutes; dashboard GET/HEAD never inspect the
environment. Readiness/status may refresh only that receipt and make no provider
call. Expiry guidance appears only when maintenance is disabled, cadence is
eligible, and authority is within 90 minutes of expiry; it prints the exact safe
readiness and confirmation-gated install/disable commands but executes nothing.
The LaunchAgent remains prepared/disabled until `CONFIRM=1 make
radar-daily-ops-install`; the application never creates authorization or embeds
credentials in the service.
**Why:** A prepublication audit cannot truthfully prove later publication or
restart, and historical authorization cannot safely stand in for current
permission. Separating these clocks and phases removes contradictory operator
truth without weakening rollback, provider, or installation boundaries.
**Revisit when:** Pointer publication is replaced by a transactional external
store, the authorization receipt source changes, or dashboard ownership moves
outside the exact local service contract.

## 2026-07-16 - Keep validation and fixtures outside dashboard authority
**Status:** accepted
**Decision:** Dashboard readiness and namespace validation are observational:
they may read and revalidate an explicit namespace or current pointer, but they
never write, refresh, select, or remove authority. Fixture rendering, integrated
radar smoke, outcome smoke, market no-send smoke, `verify-fast`, and `verify`
must preserve current-pointer bytes exactly and must not invoke a publication
command even to prove that fixture publication would fail. Pointer publication
is an explicitly named, `CONFIRM=1` operator command that requires a namespace
with the existing closed Daily Operations publication and owned-restart
receipts; fixture and legacy namespaces are refused. Manual invalidation is a
separate `CONFIRM=1` command that removes only the exact expected current
namespace under the shared descriptor-anchored mutation lock and fails closed
on absence or mismatch. A stale trusted real generation remains historical;
it is not republished merely to keep the dashboard nonempty. If no fresh trusted
generation exists, no current authority is the correct state.
**Why:** A fixture smoke silently replaced the real pointer and later made the
dashboard unavailable when that fixture aged out. A command named readiness
must not carry publication authority, and a negative fixture-publication test
must not aim a writer at the shared production store.
**Revisit when:** Dashboard authority moves to an external transactional store
with an equivalent explicit validation/publication split, receipt binding,
fixture exclusion, exact compare-and-remove invalidation, and byte-preservation
tests for every non-publication gate.

## 2026-07-15 - Accept attested partial official macro coverage
**Status:** accepted
**Decision:** Fed, BLS, and BEA acquisition are independent. Each source reports
`observed`, `no_results`, `unavailable`, `missing_configuration`, `parse_error`,
or `rate_limited`; accepted bytes are immutable and fingerprinted. A snapshot is
`complete`, `partial`, or `unavailable`, and a complete or partial snapshot may
be latest success after pointer/receipt/snapshot/coverage/raw-source
re-attestation. Local no-network import may supply any genuine source subset
with its real acquisition time. Unavailable zero-row coverage is never called
“no events,” an unavailable attempt never replaces prior success, and unlinked
macro events remain context/risk only without directional bias.
**Why:** Discarding valid official rows because one independent publisher is
unavailable creates less truthful calendar coverage than preserving an exact,
visible partial snapshot.
**Revisit when:** A source becomes transactionally coupled to another source or
partial coverage cannot be represented without ambiguous event identity.

## 2026-07-15 - Bound artifact-heavy verification without deleting history
**Status:** accepted
**Decision:** Unrelated fixture tests use isolated temporary artifact bases;
an explicit call-site `base_dir` takes precedence over the suite-wide isolation
environment so deliberate fixture/shipped-artifact tests stay exact;
project-health source/AST work is process-memoized; cumulative operational roots
are not recursively scanned. `test-full`/`verify-fast` emit cumulative per-file
timings, and the focused extracted-checkout project-health guard has a five-
second default budget. The full same-machine extracted-checkout `verify-fast`
review budget is an observational 360 seconds rather than a hard CI timeout; a
run beyond that or more than 25% over the latest comparable baseline requires
investigation. Retention reporting is metadata-only and bounded to 128
namespaces plus 128 direct entries per namespace, with no research payload reads
beyond the bounded namespace-status control marker and no compaction or
deletion. A truncated namespace inventory is a blocker. Candidates are advisory
until a separate retention policy and explicit operator authorization exist.
**Why:** Release verification must stay reproducible when research artifacts
grow, but performance is not permission to weaken integrity gates or erase
canonical audit history.
**Revisit when:** A versioned retention policy is approved, operational history
moves to an indexed store, or supported reference hardware cannot meet the
focused guard for a demonstrated non-regression reason.

## 2026-07-15 - Keep Daily Operations prepared but explicitly opt-in
**Status:** accepted
**Decision:** Daily Operations v1.1 is the only supported recurring Decision
Radar freshness maintainer. Every possible market call is preceded by readiness,
uses the enforced campaign reservation, and is limited to one already-authorized
CoinGecko no-send attempt in a unique namespace. Complete operator state and a
zero-blocker strict doctor precede pointer publication; the exact owned dashboard
restarts only afterward. Failure restores the previous pointer or invalidates
only the failed new pointer, and post-attempt cadence plus every terminal state
is persisted. Restart exceptions use the same containment path, and a loaded
LaunchAgent with a non-zero last exit is unhealthy rather than green. The
LaunchAgent remains uninstalled until `CONFIRM=1 make
radar-daily-ops-install`; its plist never creates or embeds authorization.
**Why:** The dashboard can remain current during the day without converting a
provider allow flag into an implicit recurring service or weakening freshness,
pointer, no-send, or research-only boundaries.
**Revisit when:** The provider cadence, dashboard service identity, or campaign
publication contract changes; re-review the coordinator before reinstalling.

## 2026-07-15 - Trust official macro calendars only through attested source packs
**Status:** superseded
**Decision:** The first official live calendar producer covers Federal Reserve
FOMC dates, BLS CPI/employment releases, and BEA PCE/GDP releases. Live calls are
off by default and require existing explicit authorization plus an honest BLS
contact. Local import requires all three operator-downloaded files and their real
acquisition time; checked-in fixture/test/mock/replay paths are rejected. FOMC
uncertainty, BLS TZIDs, and BEA offsets are preserved. Daily Operations may use
latest success only after closed-pointer, receipt, snapshot, and raw-source hash
attestation. Missing acquisition remains `not_configured`, never `no events`.
**Why:** Calendar context is useful only when its authority, timing, freshness,
and provenance survive into the exact generation without fixture laundering or
invented directional meaning.
**Revisit when:** A crypto unlock, exchange, or protocol calendar has an equally
authoritative, bounded, provenance-preserving source contract.
**Superseded by:** `Accept attested partial official macro coverage` above; the
source authenticity and timing requirements remain, but all-required packing no
longer discards independently valid official evidence.

## 2026-07-15 - Keep execution quality venue-neutral and private phone access preferred
**Status:** accepted
**Decision:** Execution-quality work stops at a static interface/readiness
contract until the owner selects the intended spot, perpetual, or DEX venue; no
live adapter, order, or execution behavior is activated. For ongoing phone use,
private Tailscale Serve remains recommended. Cloudflare Quick Tunnel stays
public, unauthenticated, temporary, off by default, confirmation-gated, and
given an optional 240-minute default trusted-receipt lifetime. Expiry suppresses
the URL and reports that the external process may still be public; it is not an
automatic process stop. The confirmation-gated guard removes only the exact
owned process after expiry or local authority loss.
**Why:** Venue data must match the operator's actual execution surface, while
persistent dashboard access should retain identity-based access control.
**Revisit when:** The operator names the execution venue/instrument mode or
requests a separately authenticated permanent dashboard deployment.

## 2026-07-14 - Allow an explicit temporary public dashboard link
**Status:** accepted
**Decision:** In addition to private Tailscale Serve, the owner may expose the
loopback-only Decision Radar through an unauthenticated Cloudflare Quick Tunnel.
Public enable and disable require explicit confirmation. Enable must require an
authoritative local HTTP 200 dashboard with its expected identity, an executable `cloudflared`, no
conflicting default configuration, and no stale or unowned runtime state. The
helper owns one fixed HTTP/2, non-debug process and accepts only one canonical
lowercase `https://<random>.trycloudflare.com` URL. It publishes that URL only
after edge registration and an end-to-end HTTP 200 identity probe. Disable may
terminate only the exact owned PID whose full command still matches.

The helper must not bind the dashboard to LAN/wildcard interfaces, open a router
port, use Tailscale Funnel, create Cloudflare credentials/accounts/named tunnels,
change owner-controlled DNS, install a startup service, persist a permanent public URL, print raw
logs, or mutate provider/Decision artifacts. Anyone with the URL can read the
dashboard; the operator should stop it when not in use. The existing private
Tailscale route remains the access-controlled alternative.
**Why:** The owner explicitly prefers a simpler phone workflow and accepts
public reachability. A temporary outbound Quick Tunnel provides a one-command
HTTPS link without weakening the loopback bind or silently creating permanent
infrastructure.
**Revisit when:** The dashboard needs durable uptime, a stable hostname,
multiple users, or access control; replace the Quick Tunnel with a separately
reviewed authenticated deployment rather than extending this temporary path.

## 2026-07-14 - Keep freshness expiry inspectable but non-authoritative
**Status:** accepted
**Decision:** A pointer-bound dashboard whose exact identity still matches but
whose only authority loss is `generation:stale` and/or `doctor:stale` returns a
full quarantined diagnostic shell with HTTP 503. System Health, historical
Outcomes, and explicitly historical Run History remain inspectable, while every
current artifact-derived row, field, count, detail route, and actionability
claim stays centrally suppressed. HTTP 503 keeps private phone readiness
fail-closed. Pointer, identity, fingerprint, schema, or integrity loss continues
to return the minimal unavailable response. The six-hour current-generation
limit is not raised.

The one-hour campaign cadence is a minimum provider-safety interval, not a
refresh scheduler. Recurring provider calls and dashboard restarts must not be
installed without a separate explicit operator decision.
**Why:** Freshness expiry is expected operational degradation, not evidence
corruption. Keeping safe health and historical context visible makes recovery
possible without presenting stale research as current or weakening the private
access gate. A scheduler would materially broaden provider activity and must
remain opt-in.
**Revisit when:** The dashboard gains a separately reviewed dynamic-generation
rebinding contract, or the owner explicitly authorizes a guarded recurring
no-send maintainer.

## 2026-07-14 - Use private tailnet HTTPS when access control is required
**Status:** accepted
**Decision:** The Crypto Radar HTTP backend remains bound to loopback. Optional
private phone access uses Tailscale Serve on HTTPS 443 and is available only to
identities permitted by the owner's tailnet policy. Readiness and status are
observational; enable and disable require explicit confirmation. Enablement
must fail closed unless the dashboard returns authoritative HTTP 200, the local
Tailscale node is running and online with a `.ts.net` DNS name, Funnel is
disabled, and the HTTPS Serve configuration is empty or exactly owned by this
dashboard. Disable removes only that exact route and never resets unrelated
Serve configuration. Do not add a dashboard token, LAN/wildcard binding,
router forwarding, or Funnel fallback. The separately governed temporary public
Quick Tunnel is not a private-access substitute.
**Why:** This gives the owner authenticated phone access at home or away without
expanding the dashboard's loopback trust boundary, handling a second secret, or
making research artifacts public. Exact configuration checks protect future
unrelated Serve handlers and make exposure drift visible.
**Revisit when:** Tailscale is no longer available, multiple trusted dashboard
users require application-level authorization, or a separately threat-modeled
deployment replaces the local operator surface.

## 2026-07-14 - Keep operator hierarchy current-first, route-aware, and density-adaptive
**Status:** accepted
**Decision:** Dashboard presentation must lead with the smallest truthful answer
to the operator's current question, then disclose supporting evidence on demand.
Today names a sole specialist route such as `risk_watch` instead of overstating
every visible row as a generic actionable idea. Current attention, active
scheduled risk, actionability constraints, and exact coverage precede expired,
historical, diagnostic, compatibility, and technical material.

Market anomaly evidence and canonical Decision routes remain distinct but are
visibly connected by exact asset identity. The observed move leads; unavailable
scanner strength is secondary metadata, never the dominant claim. Raw provider
slugs and full run identities remain available in context/provenance disclosures
instead of competing with symbols and current-run labels. A one-row idea set
does not offer a comparison matrix. Active calendar windows lead upcoming dates;
past events remain collapsed. Trader-facing status uses `Integrity checks` and
`Validation passed`; strict-doctor terminology remains in exact technical
contracts.

Responsive density is part of the product contract: wide screens use compact
comparison tables; common laptop widths use balanced cards or two-column market
rows; phone layouts preserve readable score labels, touch targets, no horizontal
overflow, and a compact masthead without hiding the research-only, human-decision,
no-execution statement. Missing, unavailable, suppressed, not configured, stale,
and healthy-empty states remain visually distinct and are never converted to
zero merely for layout convenience. Missing boolean receipt fields render as
`Not recorded`, never as an inferred `No`. Every relative time on an exact-run
page is computed from `generation_authority_checked_at`, so fixture, replay, and
live surfaces share one deterministic read clock. All visible route names come
from one operator-label projection; the canonical route tokens remain unchanged.
**Why:** Repeated desktop and mobile renders showed that correct data could still
feel illogical when generic counts, internal jargon, unavailable metrics, raw
identifiers, or secondary history dominated the first viewport. This hierarchy
makes the exact same canonical evidence faster to interpret without changing any
Decision v2 score, route, safety gate, provider policy, or artifact authority.
**Revisit when:** Measured operator research shows a different hierarchy is
faster while preserving the same exact-generation, presentation-only,
fail-closed, accessible, no-send/no-trade contracts.

## 2026-07-14 - Treat the dashboard as a seven-page decision terminal
**Status:** accepted
**Decision:** The primary Crypto Decision Radar interface is a server-rendered,
loopback-only seven-page operator terminal: Today, Market Radar, Ideas,
Calendar, System Health, Outcomes & Learning, and Run History. These pages
organize human attention rather than mirror artifact filenames. Historical
compatibility routes remain available but do not compete in primary navigation.

All human formatting is a pure presentation projection over the exact canonical
Decision v2 and supporting read models. It may translate time, units, enums,
scores, and reason codes, but it may not re-score, reinterpret, fill, or repair
canonical evidence. Exact-current ideas/outcomes/provider evidence remain
visually and semantically separate from bounded historical campaign context.
Actionability is not a win probability, evidence confidence is not expected
return, and unavailable spread, liquidity, baseline, or calendar coverage is
never invented.

A sparse generation must expose its full layer funnel—bounded provider rows,
selected universe, exact observations, anomaly evidence, integrated candidates,
and consolidated Core/operator ideas—plus the state of supporting layers. A
mixed integrated generation without a market-only receipt uses independent
counts rather than a false causal arrow. Zero rows are meaningful only when labeled
as verified qualification, healthy empty, unconfigured, unavailable/degraded,
stale/rejected, or historical-only. Rendering remains GET/HEAD-only, no-provider,
no-write, no-JavaScript, responsive, keyboard usable, and loopback-only. A
pointer-started server revalidates the exact namespace/run/revision/operator
digest on every request and fails closed if current authority changes.

Today and Health use one canonical layer projection for market, catalyst,
calendar, derivatives, RSI, outcomes, and provider request ledger. A green state
requires every expected layer healthy or explicitly not applicable. If
generation authority fails, every current artifact-derived count and row is
centrally quarantined across all routes; a failed current artifact may not be
reopened or demoted into historical context. Dashboard source links reject URL
userinfo, and presentation uses field-level return units plus explicit turnover
ratio conversion rather than shared-unit assumptions.
**Why:** A strict-clean zero-idea run looked broken because useful market rows,
campaign progress, and source limitations were distributed across artifacts or
hidden entirely. A consistent operator workflow makes the product useful during
both active and quiet markets without lowering thresholds or fabricating data.
**Revisit when:** A replacement interface preserves the same exact-generation,
read-only, fail-closed, accessibility, responsive, presentation-only, and
cross-layer truth contracts with materially better measured operator usability.

## 2026-07-14 - Distinguish an empty decision set from missing product coverage
**Status:** accepted
**Decision:** A trusted zero-idea Decision Radar generation must still expose
the exact fingerprint-bound market observations and anomaly rows it evaluated.
Every supporting layer must distinguish healthy non-empty, healthy empty,
unconfigured, degraded/unavailable, and normalization-rejected states; strict
doctor coherence alone does not imply that every product source was covered.
Dashboard current counts remain namespace-local, while the shared Decision
campaign outcome ledger is shown separately as cumulative historical evidence.
An empty artifact without an exact producer completion contract, lineage,
counts, and digests is unavailable—not healthy empty. In particular, empty
unlock or derivatives outputs cannot imply that their providers were observed.
A same-cycle anomaly scanner completion receipt must bind the exact run,
namespace device/inode, paths, content hashes, row semantics/lineage, and
snapshot/anomaly/search-queue counts before a zero-anomaly result becomes
healthy empty; a generic empty anomaly file remains unavailable. All scanner
outputs must be preflighted and written through one held descriptor-anchored
bundle so leaf or namespace replacement cannot split or redirect the generation.

The dashboard holds one descriptor-anchored namespace for its entire load and
fails closed if the configured namespace is replaced. Operator semantic counts
must match exact snapshot and anomaly artifacts, not only their byte digests.
Raw anomaly scanner outputs are rendered as observed scan evidence, separately
from canonical Decision candidates; they are never assigned an invented route
or made actionable by the dashboard.

Live/no-send calendar input is allowed only through the already-configured
`RSI_DECISION_RADAR_CALENDAR_SNAPSHOT_PATH`. Readiness performs a bounded,
descriptor-anchored, no-network/no-write inspection. Live generations reject
fixture, test, mock, and replay provenance; copy and fingerprint accepted source rows in
the exact namespace only after projecting them into a closed, allowlisted,
secret-safe source-row shape; preserve supported unified-calendar values; and adapt a
separate scheduled-catalyst view without loss. Publication must recompute and
exactly compare scheduled, unlock, and unified rows from that accepted copy;
counts and rewritten digests alone are not semantic authority. Live input
requires a versioned container with explicit observed time and current-source/
acquisition provenance. Unknown provider payload fields do not enter artifacts,
and secret-like keys or credential-bearing URLs fail closed. Missing or rejected
calendar input remains explicit coverage telemetry and never triggers a guessed
path, fixture fallback, provider call, authorization change, or fabricated event.
Container and nested provenance plus row-level `provider`, `source`, and
`source_class` must also be non-fixture/test/mock/replay, and any supplied
`research_only`, `no_send`, or `no_send_rehearsal` value must be exactly true.
Publication hashes and parses one unchanged buffer per calendar artifact,
rejects duplicate keys and in-place mutation, and writes the complete scheduled/
unlock JSONL-plus-report set through one held no-follow namespace bundle.
Market-quality audit counts likewise use the complete exact snapshot universe,
not only promoted candidates.
**Why:** The first clean real zero-idea authority was internally coherent but
looked broken because thirty evaluated market rows, source-pack status, and one
historical campaign outcome were hidden, while an unconfigured calendar looked
like a genuinely quiet one. The closed layer contract makes sparse evidence
useful without weakening freshness, provenance, publication, or safety gates.
**Revisit when:** A versioned, explicitly authorized calendar provider replaces
the local snapshot boundary with equal or stronger no-send, provenance,
freshness, identity, normalization, fingerprint, and coverage guarantees.

## 2026-07-13 - Measure live market evidence in a separate Decision Radar campaign
**Status:** accepted
**Decision:** `decision_radar_live_observation_campaign_v2` is the sole
measurement program for the live/no-send Decision Radar market pilot. Its
generations, candidates, feature maturity, routes, and outcomes remain separate
from Event Alpha Catalyst Radar burn-in and must not enter Event Alpha burn-in
thresholds or scorecards. Historical market-provenance v2 `burn_in_*` fields
remain readable through a read-only compatibility adapter; new rows also carry
explicit `decision_radar_campaign_*` fields, set the legacy burn-in booleans to
false with `not_counted_separate_decision_radar_campaign`, and use the
`operational` run mode. Historical rows are neither rewritten nor silently
reclassified.

The default campaign cadence is at least one hour between observations. A
too-close observation remains retained evidence with an explicit status, but it
does not enter the temporal baseline or advance warmup. Warmup is feature- and
time-aware for volume, turnover, volatility, 1h/4h/24h returns, and BTC/ETH-
relative groups. Eight samples alone are insufficient when the relevant
horizon-plus-cadence coverage is still short; every configured required group
must be warm before the asset is globally warm.

Aggregate operator and campaign projections must preserve, per feature group,
the minimum and maximum observed sample counts, required sample count, assets
below that requirement, minimum and maximum elapsed coverage, required elapsed
coverage, and assets below that requirement. A single `warming` label or total
observation count is not an adequate progress report. These fields describe
retained evidence only; they must not forecast a warm time or count hypothetical
future cycles.

Readiness remains no-network. The live command rechecks the already-existing
CoinGecko authorization and cadence before the provider adapter, never sets
authorization itself, and may attempt at most one bounded live request per
eligible invocation. Missing authorization or a waiting cadence attempts no
provider call. The provider-call reservation is persisted in a stable artifact-
base receipt before the network boundary, so replacing the mutable campaign
state directory cannot reset spacing or permit another call; the bounded attempt
ledger and exact latest-attempt receipt preserve the same fail-closed boundary.
Request ledgers persist only the allowlisted endpoint path, start/end times,
duration, HTTP status, result count, retry count, safe error class, cache
behavior, authorization boolean, and no-send state. Parameters, headers, tokens,
raw bodies, raw exception text, and recipient identifiers are forbidden, and
provider-health telemetry must reconcile.

Each Decision projection carries one canonical market-context reference with
source, observed time, freshness status, and market-snapshot id. Candidate,
CoreOpportunity, card, preview, outcome, daily brief, and dashboard copy it;
lineage drift is a strict-doctor blocker. Dashboard authority uses the canonical
operator digest that excludes only the mutable top-level `updated_at` and nested
`doctor.verified_at` verification clocks. Re-running an unchanged strict doctor
therefore preserves pointer identity, while every substantive doctor value and
artifact-manifest change remains bound and fail-closed. Pilot audits retain
monotonic `ever_authoritative` and `first_authoritative_at` history separately
from current exact-pointer readiness, so later re-audits cannot erase that a
generation was previously authoritative or present it as current after drift.

Campaign outcomes live in the shared mutable
`radar_market_history_cache/event_decision_radar_campaign_outcomes.jsonl` ledger.
It is rebuilt without providers from immutable generation candidate/Core rows
and retained observed prices, preserving origin namespaces and pointer history;
rows remain pending until due with sufficient price lineage and then mature
deterministically. `make radar-market-campaign-report` rebuilds the canonical
Markdown/JSON campaign report from local artifacts only, including authority,
attempts, cadence, feature maturity, routes, outcomes, limitations, and the next
safe command. The supported source-with-artifacts review export writes one
reproducible UTC-safe ZIP timestamp for every entry without mutating source or
research mtimes, while preserving descriptor-anchored symlink/TOCTOU checks and
secret scanning.
**Why:** Rapid duplicate snapshots are not independent temporal evidence, and
calling a market observation "burn-in" made it too easy to mix Decision product
measurement with Catalyst Radar readiness. Explicit cadence, closed lineage,
stable authority, sanitized telemetry, and a separate outcome/reporting loop
make the campaign auditable without creating provider, notification, trading,
paper, RSI, or `TRIGGERED_FADE` side effects. This decision supersedes only the
Decision-market measurement terminology/counting portions of the earlier
2026-07-13 market-pilot decision; its provenance, quality-cap, and guarded-
publication rules remain in force.
**Revisit when:** A versioned campaign v3 provides equivalent or stronger
cadence, lineage, telemetry, outcome, and exact-authority guarantees, or reviewed
longitudinal evidence supports a human-approved change to spacing or required
feature coverage without combining it with Event Alpha catalyst burn-in.

## 2026-07-13 - Treat every live market generation as single-use, including exact zeroes
**Status:** accepted
**Decision:** Every real Decision Radar market cycle uses a new lowercase
UTC-suffixed namespace. Any existing generation directory blocks before the
provider adapter, regardless of whether that generation published. A successful
zero-idea generation must still materialize canonical empty CoreOpportunity and
card-index artifacts so operator fingerprints distinguish an exact zero from a
missing or failed surface. Make runs one full strict doctor, publishes only when
its exact revision is authoritative with zero blockers, and then always writes
the final pilot audit. Pilot audit v1 uses the same canonical operator-state
digest as dashboard pointer v1 and explicitly separates adapter invocation,
network-call attempt, and provider success from market provenance v2.
**Why:** The first authorized cold-baseline run legitimately produced no ideas,
but the absent empty CoreOpportunity file made the operator manifest incoherent
and prevented doctor attestation. A later successful pointer publication also
exposed that the pilot audit compared raw file bytes while the dashboard pointer
uses canonical JSON. Single-use namespaces, materialized zeroes, and one digest
definition preserve fail-closed behavior without rejecting honest zero-idea
market observations.
**Revisit when:** A versioned generation registry replaces directory existence
as the immutable-attempt boundary, or pointer/audit contracts deliberately move
to a new shared fingerprint version.

## 2026-07-13 - The local dashboard must tolerate stalled loopback clients
**Status:** accepted
**Decision:** The Crypto Radar dashboard remains loopback-only, GET/HEAD-only,
read-only, and bound to one exact authoritative generation, but its WSGI serving
layer must handle client connections concurrently. One local client that opens
a socket without completing an HTTP request may occupy only its daemon request
thread and must not prevent another complete request from receiving the current
dashboard. A real-socket regression must park the incomplete request before
proving the second request succeeds and must verify dashboard fixture bytes are
unchanged.
**Why:** The stdlib reference server's single-threaded default blocked inside
`rfile.readline()` when the in-app browser left an incomplete connection open,
making the healthy dashboard appear offline to every later request. Concurrency
fixes availability without weakening freshness, pointer, schema, path, provider,
write, send, or trading guards.
**Revisit when:** The local dashboard moves to another loopback HTTP server with
equivalent or stronger stalled-client isolation and the same read-only and exact-
authority contracts.

## 2026-07-13 - Count market-pilot truth only from canonical provenance and bounded temporal evidence
**Status:** accepted
**Decision:** This entry's original Event Alpha `burn_in_*` terminology and
count-only warmup wording are superseded by the Campaign v2 decision above; the
provenance, evidence-quality caps, and guarded-publication rules remain accepted.
New Decision Radar market-led generations use the closed
`crypto_radar_market_provenance_v2` value (`contract_version=2`) as the only
authority for acquisition mode, provider lineage, validity, and Decision Radar
campaign counting. Consumers copy that value and its feature-basis/data-quality
evidence; they do not trust caller-asserted `decision_radar_campaign_*`, legacy
`burn_in_*`, or contract-valid flags and do not silently reinterpret historical
flat rows. A candidate-bearing generation must retain distinct request-ledger
and provider-source artifacts with valid SHA-256 fingerprints, a provider
generation id, cache status, explicit provider-call attempted/succeeded state,
and explicit live authorization. Only a valid `live_provider` / `live_no_send`
generation is eligible and counted in the Decision campaign. Mock/fixture
generations may validate the pipeline but remain excluded from that campaign and
real dashboard authority; replay, cache, preflight, malformed, or conflicting
provenance also remains excluded. Decision campaign rows never count toward
Event Alpha Catalyst Radar burn-in.

Market anomaly evidence uses a bounded per-asset temporal history rather than
presenting a one-snapshot cross-section as a mature time-series signal. The v1
history policy retains at most 45 days and 256 observations per asset, requires
at least one hour between baseline-counting observations, and retains too-close
rows as explicit non-counting evidence. Volume, turnover, volatility, 1h/4h/24h
return, and BTC/ETH-relative groups each require eight strictly earlier counted
observations plus horizon-aware elapsed coverage; every configured required
group must be warm before the asset is globally warm. Derived returns,
volatility, turnover/volume z-scores, and BTC/ETH relative returns use percent
points and never include the current observation in its own baseline. Current
rows older than six hours or beyond the five-minute future tolerance fail
closed. Direct provider fields remain direct; only fields explicitly marked as
proxy inputs may be replaced by a temporal derivation.

Decision Model v2 makes evidence limitations operational. Missing/stale spread
caps urgency at 55 and cannot support actionable/rapid routing. Proxy-only
market evidence caps actionability at 64 and evidence confidence at 55, floors
risk at 55, caps urgency at 45, and cannot be actionable or rapid. A cold,
warming, unavailable, or stale temporal baseline caps evidence confidence at
62, floors risk at 48, and caps urgency at 45; a still-proxy anomaly basis stays
review-only until it warms. These are transparent Decision Radar caps, not
changes to Event Alpha's strict Catalyst Radar lanes.

The live pilot remains no-send and research-only. Missing
`RSI_EVENT_DISCOVERY_UNIVERSE_LIVE=1` authorization returns an explicit safe-
blocked result, performs no provider call, writes only bounded local no-send
attempt/audit/campaign-report evidence, and leaves the fixed dashboard pointer
unchanged. Publication requires a
real fresh complete generation, canonical v2 lineage, exact request/source/
history/product fingerprints, matching candidate/Core/card/preview/pending-
outcome counts, current operator-state binding, and a fresh full strict doctor
with zero blockers. Every canonical Decision candidate gets one pending outcome
placeholder; outcome cohorts remain copied measurement evidence and never
auto-apply a threshold. No path may send, trade, paper trade, write normal RSI
rows, execute orders, or let Event Alpha create `TRIGGERED_FADE`.
**Why:** A provider name or mock snapshot is not evidence that a real market
observation occurred, and a cross-sectional proxy is not a temporal baseline.
Closed lineage, explicit warmup, and visible quality caps keep the pilot useful
without overstating freshness, execution quality, or campaign maturity. Guarded
publication prevents a blocked, partial, fixture, or drifted attempt from
becoming current operator truth.
**Revisit when:** A versioned provenance or history contract provides equivalent
or stronger immutable lineage and time-series evidence, or reviewed real
no-send outcomes justify a separately human-approved change to warmup, quality
caps, routes, or publication policy without weakening the safety boundaries.

## 2026-07-12 - Use one closed Decision v2 projection as trader-facing authority
**Status:** accepted
**Decision:** `crypto_radar_decision_projection_v1`, returned by
`decision_model_values`, is the single Decision Model v2 authority for one idea
generation. It is stored on the integrated candidate, is idempotent, contains
everything required to validate and render itself, and is copied—not rebuilt—
to CoreOpportunity, cards, the Decision preview, review inbox, pending outcome,
and dashboard. Operator state carries exact aggregates and artifact fingerprints
derived from those canonical projections rather than duplicating every idea.
Candidate/Core route or deterministic-score drift and card/preview/outcome/
dashboard projection drift are doctor blockers. Rendering may not perform a
materially new evaluation from partial context.

Crypto Decision Radar is the trader-facing product layer; Event Alpha remains
the additive Catalyst Radar with unchanged strict catalyst lanes and historical
artifacts. Decision Radar primary and contributing origins are `market_led`,
`catalyst_led`, `technical_led`, `derivatives_led`, `onchain_led`,
`fundamental_led`, and `macro_led`. Legacy `thesis_origin=mixed` remains
readable compatibility metadata only. The eight operator routes are
`dashboard_watch`, `actionable_watch`, `high_confidence_watch`,
`rapid_market_anomaly`, `fade_exhaustion_review`, `risk_watch`,
`calendar_risk`, and `diagnostic`. Unknown catalyst lowers explanatory
confidence and may raise risk but is not a universal visibility blocker.

The configurable initial route floors remain dashboard watch 45, actionable
65, rapid anomaly 68 with urgency 72, and high confidence 80 with evidence
confidence 75. Actionable/rapid routes require verified good or acceptable
spread. Unavailable spread may support dashboard watch only; spread is never
invented. Timing, phase, urgency, horizon, expiry, and chase risk are canonical
values. Stale/expired ideas cannot remain actionable, and urgency never bypasses
identity, freshness, liquidity, spread, turnover, manipulation, unit, dedupe,
schema, path, secret, or safety gates. Per-field return units normalize exactly
once; implausible fractions and incompatible mixed units fail closed.

The dashboard is the primary read-only surface and notifications route human
attention, never execution. The Decision-first preview is
`event_decision_v2_notification_preview.md`; the legacy Event Alpha preview
stays separate compatibility/diagnostic output. Cards lead with Crypto Decision
Radar and retain Catalyst Radar Classification as a secondary section. Calendar
evidence and read-only RSI context remain inside the canonical projection.
Calendar evidence may adjust risk/expiry but cannot create direction;
`calendar_risk` without actual attached evidence is invalid. RSI cannot create
an idea or touch RSI storage, alerts, backtests, paper, sends, or execution.

The first real/no-send market-led generation uses
`radar-market-no-send-readiness`, `radar-market-no-send`, and
`radar-market-no-send-smoke`. Readiness performs no write or network call; live
CoinGecko data requires the existing explicit
`RSI_EVENT_DISCOVERY_UNIVERSE_LIVE=1` authorization. Fixture/mock generations
are never real dashboard authority. The fixed pointer updates only for a real,
fresh, complete generation with exact fingerprints, matching canonical counts,
current run/revision/operator-state binding, and a fresh full strict doctor with
zero blockers. A real clean zero-idea generation may become honest current
authority when those same gates pass. Blocked, failed, stale, fixture, or mock
runs must remain explicit and cannot make stale fixture data look live.

The rolling temporal baseline uses the dedicated bounded research cache
`radar_market_history_cache/event_market_history.jsonl`. Each live generation
copies an exact fingerprinted snapshot into its own namespace; fixture/mock
history is isolated and never warms live evidence. Published namespaces are
immutable, so subsequent live cycles use a new namespace while seeding from the
shared cache. `event_market_no_send_latest_attempt.json` binds Make orchestration
to the just-completed CLI attempt; doctor/publication cannot reuse an older
complete manifest after a blocked attempt. Live authority also requires the
fingerprinted namespace-local provider-health artifact, which persists only
safe error classes.

Every current canonical Decision idea, including diagnostic controls, receives
a pending outcome placeholder whose origin/route/actionability/evidence/risk/
catalyst/timing/phase cohorts match the projection exactly. Outcomes and
optional preference feedback remain measurement only; threshold, route, and
prior changes require explicit human approval. All paths remain research-only,
no-send by default, and incapable of trading, Event Alpha paper trading, normal
RSI writes, execution, or Event Alpha-created `TRIGGERED_FADE`.
**Why:** A closed, copy-only authority prevents context loss and downstream
semantic drift, makes a liquid unknown-catalyst move visible without weakening
execution-quality or safety gates, and separates trader-facing judgment from
strict catalyst eligibility. Guarded pointer publication prevents stale,
fixture, or partially inspected data from becoming current operator truth.
**Revisit when:** Exact observed outcomes and reviewed preference cohorts are
large enough to justify a human-approved threshold experiment, or a versioned
Decision Model v3 deliberately replaces these fields while preserving legacy
readability, fail-closed authority, and all research-only boundaries.

## 2026-07-12 - Use one closed evidence clock for burn-in measurement
**Status:** accepted
**Decision:** Event Alpha burn-in measurement, scorecard, source-yield, evidence
semantics, namespace-policy output, and feedback-progress reports must capture
one timezone-aware UTC evaluation clock and reuse it throughout the report.
Window membership is the inclusive relation `cutoff <= timestamp <=
evaluated_at`. The first present registered timestamp is authoritative;
missing, malformed, timezone-naive, stale, future, or invalid-first timestamps
fail closed and cannot borrow a later field or the current wall clock. JSON
documents such as daily runs, candidate manifests, source coverage, readiness,
and provider health obey the same rule. Feedback today/week counts use only the
exact eligible raw label's aware `marked_at`. Source-coverage producers stamp
that captured clock directly; provider-health measurement reads the real nested
store and uses the current state's exact success/failure timestamp without mtime
or secondary-field fallback. Measurement, scorecard, and source-yield share all
five North Star count thresholds: live no-send cycles, real candidates, human
labels, labeled near misses, and outcomes. No partial threshold subset may claim
that evidence is sufficient.

Near-miss and quality-cap measurement cohorts use the latest canonical Core
Opportunity revision for each exact run/profile/namespace/Core identity. The
same Core id in another run is a distinct observation; linked candidate or
alert representations do not add another count. Near misses use the
deterministic Core classifier, while quality caps require explicit final
quality state. Arbitrary prose, provider names, URLs, requested states, and
support-row counts are never cohort predicates. Current dashboards expose a
closed schema-validated window summary; old interpretation fields are
deprecated, and feedback progress has its own typed denominator/safety schema.
Core authority parts must be exact canonical strings and are encoded as a tuple,
not delimiter-joined text; whitespace/coercion ambiguity fails closed. Distinct
revisions at the same authoritative timestamp exclude that Core observation
until a strictly later revision resolves the conflict. Near-miss classification
uses the same captured report clock.

Archived pre-fix dashboards remain immutable historical evidence rather than
being rewritten. Burn-in report writers refuse lifecycle-frozen namespaces and
daily namespaces already sealed by the local archive checksum ledger before
writing any policy/report file. Historical inputs may be inspected only by
writing a new explicit diagnostic namespace.
**Why:** Implicit-now fallbacks, per-row clock reads, future rows, and substring
matches made mutually contradictory reports possible and inflated local
quality counts from 6 to 76. One closed clock plus canonical Core authority
makes denominators reproducible without converting missing or historical data
into apparent current evidence.
**Revisit when:** A versioned research database provides immutable temporal
queries and typed cohort identities with equivalent fail-closed bounds, or a
reviewed schema version deliberately replaces the timestamp precedence or
cohort classifier without weakening exact authority.

## 2026-07-12 - Keep observed-outcome ingestion preview-first and noncanonical
**Status:** accepted
**Decision:** Building an Event Alpha observed outcome requires explicit local
candidate, Core Opportunity, and versioned close-set files; literal candidate
and Core ids; and an explicit aware evaluation clock that is not in the future.
The default command prints a research-only preview and writes nothing. Optional
staging requires both an absolute noncanonical `.jsonl` path and `--confirm`,
creates exactly one mode-0600 file without append/replace, and refuses existing
targets, symlinks, input aliases, canonical artifact names/paths, and configured
Event Alpha roots. Profile and namespace flags are identity assertions only.
The checked-in close fixture is always `synthetic_fixture`, inconclusive, and
calibration-ineligible; only the strict observed-close contract may claim
observed market prices. Neither mode writes canonical stores, run ledgers,
cards, notifications, trades, paper rows, normal RSI rows, or triggers.
**Why:** A convenient append/upsert path or caller-asserted fixture could poison
the exact evidence loop before price lineage is reviewed. Preview-first,
create-only isolation makes provenance and identity inspectable without granting
the operator authority over live research history.
**Revisit when:** A human-approved provider ingestion design supplies immutable
price attestations, bounded acquisition ledgers, replay/rollback semantics, and
an exact canonical merge policy with holdout evidence; do not weaken the
synthetic-fixture exclusion or Event Alpha safety boundaries.

## 2026-07-12 - Keep feedback calibration priors shadow-only
**Status:** accepted
**Decision:** Exact Core-authorized feedback may produce reviewable calibration
prior artifacts and in-memory before/after comparisons, but runtime Event Alpha
paths must not apply those priors to alert scores or tiers. Canonical artifacts
carry `recommendation_only=true` and `auto_apply=false`; the retained
`RSI_EVENT_ALPHA_APPLY_PRIORS` setting is compatibility-only and grants no
mutation authority. Local replay and the priors-shadow report may calculate
hypothetical bounded adjustments without writing alert snapshots or changing
routing.
**Why:** The July North Star and research-truth decisions supersede the older
opt-in application path. An environment flag and self-asserted artifact cannot
replace the separately approved policy decision, burn-in review, holdout
evidence, and tier-specific safety analysis required for automatic promotion.
Generic score thresholds could also bypass richer playbook timing, derivatives,
supply, proxy, and maximum-tier caps.
**Revisit when:** A separate human-approved decision names the exact prior
contract, minimum reviewed samples, holdout evidence, freshness window,
playbook/tier caps, rollback path, and bounded no-send activation procedure.

## 2026-07-12 - Count only exact observed evidence as outcome and feedback truth
**Status:** accepted
**Decision:** Event Alpha calibration may count an outcome only when contract v1
joins one exact run/profile/namespace/candidate/Core/observation identity to one
canonical integrated-candidate row and one canonical Core Opportunity row. The
primary horizon must be mature under an external current UTC clock. Every
mature horizon must carry a due time, bounded-lag observation time, positive
exit price, canonical source, and unique observation id; its return must
recompute from the observed entry and exit prices within the contract tolerance.
Future evaluations, duplicate or malformed JSON keys, partial/legacy rows,
synthetic fixtures, missing prices, reused observations, ambiguous identities,
and unsafe send/execution/trade/paper/normal-RSI/trigger fields remain readable
diagnostics but cannot enter denominators. Validation is derived from the
canonical lane and signed primary return, never from a persisted positive label.
Burn-in and readiness surfaces must use the same exact joined partition and
must not promote legacy alert-return aliases as outcome evidence.

Manual feedback follows the parallel exact contract: one run/profile/namespace/
Core identity, one canonical Core authority, an unambiguous latest human label
after Core creation and not in the future, safe scalar attribution owned by the
Core row, and no side effects or secret-bearing notes. Duplicate, malformed,
future, pre-Core, legacy, or unmatched feedback is calibration-ineligible.
Consumers remain fail-closed until they explicitly adopt this partition; the
presence of a legacy label alone is never evidence authority.
**Why:** A return or label is not research truth merely because a JSON field
claims it. Exact authority, independently recomputable prices, deterministic
directional grading, and closed safety/clock rules prevent synthetic,
future-dated, duplicated, poisoned, or broadly matched rows from manufacturing
sample size or priors.
**Revisit when:** A versioned outcome contract replaces local price lineage with
equivalent immutable market-data attestations, or measured reviewed samples
justify a new directional grading contract without weakening exact identity,
maturity, provenance, and research-only safety.

## 2026-07-12 - Count calendar normalization without retaining rejected payloads
**Status:** accepted
**Decision:** The integrated unified calendar must merge raw scheduled and raw
fixture rows before exactly one normalization pass. Normalization contract v1
uses `last_valid_row_wins` and records only nine closed fields: contract version,
dedupe policy, input/accepted/output/duplicate-overwrite/non-mapping/rejected
counts, and sorted counts from the registered payload-free rejection enum. It
must satisfy `input = accepted + non_mapping + rejected`, `accepted = output +
duplicate_overwrite`, and `rejected = sum(reason_counts)`. Invalid duplicates
cannot replace a prior valid row. No rejected title, id, URL, source, field name,
sample, exception, traceback, hash, or raw value may enter telemetry. Duplicate
JSON keys and nonempty unknown fixture containers fail closed before a false
zero-row result. New integrated runs snapshot and validate the exact nested
mapping before writing it to the canonical run ledger, reject extra/missing or
malformed fields before persistence, and require its output count to equal both
the calendar artifact and outer run-row count. Legacy rows may omit the mapping;
they do not gain inferred telemetry.
**Why:** An output-only count hides whether upstream data was absent, rejected,
or overwritten, while storing rejected samples would create privacy, secret,
and operator-noise risks. Closed aggregate accounting makes source quality and
normalizer regressions observable without turning bad payloads into durable
artifacts or changing any research route.
**Revisit when:** A versioned immutable raw-event quarantine with explicit
retention/redaction policy is approved, or a telemetry schema v2 adds a new
aggregate dimension with the same payload-free and exact-accounting guarantees.

## 2026-07-12 - Require exact evidence for current dashboard authority
**Status:** accepted
**Decision:** A current Event Alpha operator artifact from a new generation must
carry fingerprint contract v1: exact bytes for files, a framed sorted exact-byte
tree for directories, or one canonical persisted row for the cumulative run
ledger. Run-ledger authority binds exactly one non-whitespace string identity
of run id, profile, and artifact namespace; unrelated later appends are allowed,
but edits, duplicate identities/JSON keys, partial/deprecated metadata, symlinks,
non-regular files, concurrent mutation, and path fallbacks are not. The dashboard
parses the same verified byte buffer and grants current-generation authority
only when the known-artifact manifest is structurally complete, the immutable
run time and exact strict-doctor stamp are fresh, the doctor inspected the same
revision, its exact typed status is `OK` or `WARN`, and it has zero blockers.
Failed current artifacts are never parsed or displayed. Legacy fingerprintless
or valid SHA-only states may remain readable only through a stale,
non-authoritative in-memory view; they are never rewritten or upgraded by
inference. When current authority fails, only system Health and explicitly
cumulative/non-authoritative feedback, outcomes, and provider health remain
visible; current ideas, diagnostics, calendar rows, candidate details, and
counts stay suppressed. The dashboard smoke must fail when authority is absent.
**Why:** Run ids, paths, counts, and revision labels prove lineage but not
content. Exact verified evidence plus independent immutable-run and doctor
freshness prevents a locally coherent-looking mix of stale, replaced, aliased,
or uninspected artifacts from becoming trader-facing research authority.
**Revisit when:** Artifact schema v2 stores immutable per-run directories behind
an atomic content-addressed pointer and provides equivalent exact-row,
freshness, no-follow, and fail-closed display guarantees.

## 2026-07-12 - Treat one valid v2 authority and strict doctor as fail-closed contracts
**Status:** accepted
**Decision:** A projected Decision Model v2 row must come from one individually
schema-valid authority; consumers may not assemble a stronger-looking row by
borrowing fields from different candidate/core/card records, and explicit empty
required containers must survive projection. Promotion requires the exact
affirmative `research_only is True` contract. Boolean-only provider safety
attestations survive every reevaluation and downstream projection, must match a
hard blocker plus diagnostic route, and are derived before unsafe source paths
are reduced to portable labels; secret values and absolute paths do not persist.
The first explicit v2 marker is authoritative, so disabled or malformed data
cannot fall through to nested/later actionable data. Later correction/disproof
evidence on either the candidate or source rows outranks an earlier derived
catalyst confirmation. Performance reporting joins exact candidate and core
aliases into one observation and defines diagnostic cohorts only from
actual lane/opportunity/route semantics, not unrelated values containing the
word `diagnostic`. A full strict artifact-doctor CLI run must exit nonzero when
its context cannot resolve, its lock is skipped, its result is `BLOCKED`, any
blocker remains, or its exact operator revision cannot be stamped; non-strict,
schema-only, and API-skipped reports remain observational rather than readiness
authority.
**Why:** Research-only does not make misleading operator evidence harmless.
Single-row authority, durable safety facts, exact denominators, and meaningful
process exit codes prevent partial artifacts and automation from presenting a
false green state without changing notification or execution policy.
**Revisit when:** Immutable per-run artifacts make projection precedence
unambiguous by construction, or a versioned schema deliberately replaces these
contracts with equally fail-closed lineage and safety guarantees.

## 2026-07-12 - Separate Crypto Radar actionability from catalyst confirmation
**Status:** accepted
**Decision:** Event Alpha's additive Crypto Radar Decision Model v2 may present
an explicit research-only market-led idea without a known catalyst. Actionability,
evidence confidence, risk, thesis origin, directional bias, catalyst status,
timing, and tradability are independent fields. Market-led promotion requires a
canonical asset, proven-fresh snapshot, adequate liquidity, observed acceptable
spread, meaningful turnover/volume anomaly, strong relative move or classified
breakout/stealth structure, and no duplicate/control/suspicious/safety blocker.
Unknown catalyst is a disclosed soft penalty; missing official source/article
or derivatives evidence is also soft unless a specific lane inherently requires
it. The lowercase v2 radar routes are separately configurable presentation and
operator metadata. They do not replace `opportunity_type`, legacy strict-alert
gates, or notification routing, and old/unversioned artifacts are never inferred
as v2. Event Alpha still cannot trade, paper trade, execute, write normal RSI
signals, send Telegram by default, or create `TRIGGERED_FADE`; actual
`TRIGGERED_FADE` remains exclusive to `event_fade.py` plus `proxy_fade`.
**Why:** Price/volume structure, squeezes, positioning, liquidity shifts, and
unexplained momentum can be useful to a human operator before a discoverable
event exists. Treating catalyst discovery as confidence enrichment preserves
that information while explicit tradability and safety gates contain
manipulation risk.
**Revisit when:** Measured outcomes by thesis origin, catalyst status,
actionability cohort, and anomaly type justify changing thresholds or when a
separate reviewed decision authorizes any notification policy beyond no-send
preview.

## 2026-07-12 - Treat provider access failures as bounded operational state
**Status:** accepted
**Decision:** Live research providers must identify themselves honestly, retain
only bounded/redacted diagnostics, classify access failures precisely, and stop
spending request budgets when the upstream service says to stop. RSS uses the
project user agent and at most one retry for transient network/408/429/5xx
failures, never an ordinary 403 retry. GDELT remains one broad context fetch but
is excluded from automatic catalyst search while its DOC API migration is
rate-limited; the first 429 enters backoff. Bybit region/compliance blocks are
reported as `region_restricted` and are never bypassed through proxy rotation or
browser impersonation. CryptoPanic uses the current official plan slug and
reports token/plan mismatch instead of `network_error`. OpenAI 429/auth/access
failures trip a shared per-cycle gate, stop unscheduled batch work, and record
attempt/success/failure/provider-backoff counts; live OpenAI profiles use at most
three concurrent calls. None of these policies enables sends, trades, paper
trades, normal RSI writes, or LLM-created `TRIGGERED_FADE`.
**Why:** The full live run amplified upstream failures: RSS publishers rejected
Python's default user agent, GDELT was called in two roles, Bybit's public 403
lost the CloudFront country-block evidence, CryptoPanic used a retired route,
and 150 OpenAI attempts continued after quota 429s. Bounded, explicit provider
state preserves useful partial results without hiding configuration, billing,
regional, or upstream-capacity blockers.
**Revisit when:** GDELT's replacement feed is stable enough for a tested adapter,
Bybit is available through a permitted owner-approved egress, CryptoPanic/OpenAI
credentials are restored, or measured successful throughput justifies changing
the three-call OpenAI concurrency cap.

## 2026-07-11 - Count provider burn-in evidence only from an exact guarded attempt
**Status:** accepted
**Decision:** Event Alpha provider-backed burn-in candidates count only when the
current rehearsal report, provider generation id, provider run id, profile,
artifact namespace, successful no-send request-ledger row, namespace-local
source artifact, and provider-specific provenance all agree. Every provider
attempt gets a unique generation even under a fixed research clock; a later
failed retry cannot reuse an earlier success, and current lineage may update
only matching current core rows. Provider live authority must already exist in
the provider-specific environment gate; a CLI boolean cannot grant it.
Readiness may proceed with any one ready priority provider, while still
reporting whether all priority providers are ready and preserving the separate
strategic activation order. Targeted market refresh is one bounded,
canonical-asset-deduplicated batch (default maximum 20) and cannot promote a
source-less anomaly; market confirmation still requires strong source evidence.
Operator artifacts use canonical raw/candidate/research/snapshot/current-core/
visible-current/cumulative/alertable/strict/preview counters and explicitly
named freshness scopes rather than legacy `alerts` or unlabeled populations.
**Why:** Reused fixed-clock identities, legacy counter aliases, and environment-
local configuration checks could overstate observed evidence or let individually
reasonable reports contradict the exact run. Exact attempt lineage and scoped
operator language keep research burn-in measurable without weakening no-send,
no-trading, no-paper, no-RSI, or no-trigger safety.
**Revisit when:** Immutable per-attempt artifact directories make the current
generation/report/ledger joins redundant, or reviewed burn-in evidence justifies
a deliberate provider-activation or market-confirmation policy change.

## 2026-07-11 - Treat one exact operator generation as the readiness authority
**Status:** accepted
**Decision:** Active Event Alpha namespaces must maintain one atomic operator
state keyed by exact run id, profile, and artifact namespace. Every artifact is
current, skipped, failed, or stale with an explicit reason. Only a full strict
doctor (`schema_only=false`, API checks enabled) for that exact state revision
is authoritative. Runs, reports/cards/previews, and confirmed retention share a
canonical namespace mutation lock, including strict doctor, lifecycle, and
provider-preflight writers. A custom ledger path never changes that lock/state
identity. Retention also holds the notification lock and uses fingerprint
revalidation plus expected-run/revision invalidation before writes. Missing,
corrupt, schema-invalid, or unknown state/marker data, custom-ledger ambiguity,
copied marker identity, and unowned fixed-path writes fail closed for
send-readiness. A failed attempted live delivery is not a no-send rehearsal even
when zero items were delivered, impossible send-accounting combinations are
invalid, and only `OK`, `WARN`, or `BLOCKED` can be authoritative doctor results.
**Why:** Individually valid artifacts were able to describe different runs, and
retention could otherwise replace files after another writer advanced the
namespace. Exact identity, revision CAS, and shared exclusion make lifecycle,
doctor, report, and retention claims auditable without weakening no-send safety.
**Revisit when:** Artifact schema v2 replaces fixed namespace paths with an
immutable per-run directory and atomic `latest` pointer that provides equivalent
cross-process ownership and retention guarantees.

## 2026-07-11 - Activate lane-critical providers in North Star order
**Status:** accepted
**Decision:** The next live-data activation is Coinalyze derivatives/OI/funding,
followed by official exchange announcements (Bybit public no-send first within
that category, then Binance public/fixture). Every activation starts with a
bounded request-ledger-backed no-send rehearsal. Context/news providers do not
move ahead of lane-critical sources, and no activation enables Telegram sends.
All Markdown and structured runbooks must derive the full seven-rank order from
the canonical source-coverage priority tuple, including separate CryptoPanic
context and lower-priority RSS/GDELT context-only categories.
**Why:** Derivatives evidence unlocks fade/crowding review and confirmed-long
warnings, while exchange announcements supply high-authority listing/risk
identity. Broad news is useful context but cannot be the primary alpha engine.
**Revisit when:** Measured no-send burn-in evidence shows a different provider
category produces more contract-counted, reviewable candidates per request and
the North Star contract is deliberately updated.

## 2026-07-10 - Scope artifact-doctor semantics to explicit contracts
**Status:** accepted
**Decision:** Event Alpha doctor checks must interpret rows using their declared
schema, delivery mode, guard state, return unit, namespace measurement
eligibility, and artifact generation. Guarded historical sends are valid only
for the notification-delivery and run-ledger schemas when live-send mode,
guards, status, and accounting agree; no-send and integrated-delivery rows stay
strict. Notification rehearsal status alone does not make a namespace daily
burn-in evidence. Market-unit compatibility may infer only from the horizons
being reconciled, and legacy normalization must use a narrow, identifiable
signature while preserving the original evidence. Any existing-ledger rewrite
must use a same-directory atomic replacement after flushing durable bytes.
**Why:** Generic truthiness and whole-row heuristics produced false blockers for
valid historical sends, extreme unrelated market horizons, and a rehearsal
namespace that explicitly opted out of burn-in measurement. Narrow migrations
also clear pre-schema paths and incident rows without relabeling modern malformed
evidence or weakening research-only/no-send safety.
**Revisit when:** Artifact schema v2 replaces these contracts, delivery ledgers
gain a different guarded-send accounting model, market snapshots adopt a single
mandatory unit with no legacy rows, or the pre-incident watchlist generation is
fully retired from retained artifacts.

## 2026-07-10 - Separate notification runtime helpers from config assembly
**Status:** accepted
**Decision:** Notification wall-clock budgets, partial-warning detection,
operator next-step rendering, feedback-target selection, and integer coercion
belong in `notification_runtime_helpers.py`. Runtime configuration builders and
the empty pipeline-result constructor remain in `config_reports.py`; the latter
depends on watchlist/router configuration and is not a pure runtime helper.
**Why:** The 1,392-line config service mixed provider/profile assembly with 126
lines of notification runtime/report helpers. A broad regression test caught
and corrected the attempted movement of the config-coupled constructor before
acceptance. The final split yields 1,295- and 126-line modules with all seven
moved ASTs unchanged.
**Revisit when:** Notification configuration gains a dedicated dependency-
injected factory that can own empty-result construction without circular imports.

## 2026-07-10 - Separate verdict value and evidence-semantics helpers
**Status:** accepted
**Decision:** Generic mapping, score, count, and normalized-value helpers belong
in `opportunity_verdict_values.py`; narrative/proxy, official/structured,
fresh-market, strategic-context, and sector predicates belong in
`opportunity_verdict_evidence.py`. `opportunity_verdict.py` owns scoring,
thresholds, caps, final levels, live-confirmation policy, and explanation text,
and re-exports all moved private names.
**Why:** The 1,395-line verdict module mixed final policy decisions with 396
lines of reusable normalization and evidence classification. The split yields
1,056-, 132-, and 264-line modules with all 15 moved ASTs unchanged.
**Revisit when:** Verdict schema v2 changes score/confirmation semantics or
evidence predicates become a shared cross-product policy service.

## 2026-07-10 - Separate opportunity-audit matching and value normalization
**Status:** accepted
**Decision:** Opportunity-audit scalar normalization, quality-field access, row
conversion, and incident value helpers belong in `opportunity_audit_values.py`;
card, feedback, and target matching belong in `opportunity_audit_matching.py`.
`opportunity_audit.py` owns decision-path assembly and re-exports the existing
private helper names for compatibility.
**Why:** The 1,404-line audit module mixed operator report assembly with 312
lines of reusable normalization and identity matching. The split yields 1,145-,
182-, and 130-line modules with all 19 moved function ASTs unchanged.
**Revisit when:** Opportunity-audit schema v2 replaces the current row contract
or matching is centralized across all operator artifacts.

## 2026-07-10 - Keep shim report formatting pure and separate from audits
**Status:** accepted
**Decision:** Markdown rendering for shim registry, dependency, old-import,
final-status, and removal-candidate reports belongs in
`event_alpha/shim_formatting.py`. `event_alpha/shims.py` owns registry/audit,
scanning, counters, persistence, and CLI behavior and re-exports all established
formatter names plus `LEGACY_IMPORT_COMPATIBILITY_TEST`.
**Why:** The safety-critical tombstone registry was 1,431 lines and mixed pure
presentation with filesystem/import auditing. The split yields 1,169- and
286-line modules while all five rendered reports remain byte-for-byte identical.
**Revisit when:** A structured report schema replaces Markdown or the deleted
shim tombstone system is explicitly retired.

## 2026-07-10 - Separate architecture-report contract data from report logic
**Status:** accepted
**Decision:** Static final-report schema names, output names, major target
metadata, tracked paths, split-path inventory, and historical migrated-module
inventory belong in `project_health/architecture_report_contract.py`.
`architecture_report.py` continues to re-export every established name and owns
measurement, report construction, formatting, writing, and CLI behavior.
**Why:** The report generator was 1,472 lines, only 28 below the production file
blocker. Moving 93 lines of immutable contract data created headroom without
altering generated fields, public names, safety gates, or runtime behavior.
**Revisit when:** The architecture report schema is deliberately versioned or
the historical migrated-module inventory is retired.

## 2026-07-10 - Keep split-test helper ownership out of the umbrella runner
**Status:** accepted
**Decision:** Event Alpha fixtures and compatibility globals used by split test
modules belong only in `tests/event_alpha/_api_helpers.py`. The standalone
umbrella owns its 41 residual tests, module registries, adapter, and runner; it
must not retain a second copy of package helper graphs that none of its local
tests consumes.
**Why:** After all oversized Event Alpha tests moved to focused modules, 747
lines of old helper definitions remained duplicated in `test_indicators.py`.
Removing the unreferenced graph reduced the umbrella from 1,698 to 913 lines
while preserving all 41 local identities and the complete 786-test standalone
execution path.
**Revisit when:** A residual umbrella test genuinely needs a shared Event Alpha
fixture and cannot be moved to its focused package home.

## 2026-07-10 - Separate integrated-radar merge policy from row assembly
**Status:** accepted
**Decision:** Pure integrated-radar normalization, family selection, opportunity
policy, market/derivatives interpretation, source ranking, and summary helpers
belong in `pipeline_parts/merge_policy.py`. `pipeline_parts/merge.py` owns the
merged-family context and schema-field assembly. Private compatibility names
remain exported through the existing API wrapper synchronization, and changes
to either side must preserve fixed semantic hashes spanning identity, source,
market, derivatives, diagnostics, and research-only safety fields.
**Why:** The former 1,498-line module sat two lines below the production blocker
threshold and mixed policy decisions with mechanical row construction. The
split yields 551- and 1,016-line modules without changing any candidate field or
weakening monkeypatch compatibility.
**Revisit when:** Integrated candidate schema v2 intentionally replaces the
current row contract, or the private compatibility API is explicitly retired.

## 2026-07-10 - Keep burn-in command planning pure and execution stateful
**Status:** accepted
**Decision:** Daily Event Alpha burn-in command construction belongs in
`event_alpha/operations/daily_burn_in_plan.py`; subprocess execution, partial
artifact writes, candidate accounting, safety counters, and final rendering stay
in `daily_burn_in.py`. The orchestrator continues to re-export `BurnInStep`,
`build_steps`, and `default_namespace` for compatibility. Planning regressions
must prove both exact sequence and absence of send-enabling commands.
**Why:** The previous 1,499-line module mixed pure plan creation with stateful
execution. Separating that boundary reduced the orchestrator below the 1,200-line
architecture threshold without changing any generated command, plan rendering,
provider gate, required-step status, or research-only safety behavior.
**Revisit when:** Burn-in artifact schema v2 deliberately changes the plan model,
or callers are migrated through a separately reviewed public API change.

## 2026-07-10 - Split oversized tests into focused sub-threshold modules
**Status:** accepted
**Decision:** Oversized package test modules must be reduced through cohesive
behavioral slices, with extracted files kept below the architecture warning of
1,500 lines whenever the boundary permits. Shared setup comes from the package's
`_api_helpers` module rather than importing test functions from the source
monolith. Every new module must be registered with the direct standalone runner,
and the split must prove unique test-name preservation plus both pytest and
standalone execution before acceptance.
**Why:** `tests/event_alpha/test_integrated_radar.py` had reached 16,234 lines
and mixed core-store, reconciliation, operator-identity, provider, and market
surface regressions. A naive move into another multi-thousand-line file would
only relocate the warning; four focused modules reduced the monolith by 3,923
lines without creating another over-1,500 file or weakening the compatibility
runner. A second validation/review split applied the same rule to 45 tests,
reducing the monolith again from 12,311 to 9,953 lines while producing 1,081-
and 1,309-line modules and preserving all 240 integrated-radar test identities.
A third 27-test split isolated LLM relationship analysis, advisory behavior,
provider timeout/budget/cache handling, and raw extraction in a 942-line module;
the source monolith fell again from 9,953 to 9,018 lines while preserving the
exact 125-name remaining surface across source plus extraction.
A fourth split separated the final four incident/claim/context regressions into
867- and 639-line modules; the source monolith fell from 9,018 to 7,536 lines
with the exact 98-name surface preserved.
A fifth split isolated 13 catalyst-frame and downstream role/aggregation tests
in a 1,127-line module; the source monolith fell from 7,536 to 6,421 lines with
the exact 94-name surface preserved.
A sixth split moved 15 fade/resolver tests and 6 alert-ranking/trigger-guard
tests into 435- and 377-line modules; the source monolith fell from 6,421 to
5,634 lines with the exact 81-name surface preserved.
A seventh split moved 5 market enrichment/anomaly lifecycle tests and 3
deterministic playbook/graph tests into 387- and 531-line modules; the source
monolith fell from 5,634 to 4,740 lines with the exact 60-name surface preserved.
An eighth split isolated 9 impact-hypothesis generation/matching/validation,
persistence, verdict, watchlist-identity, and external-entity tests in a
920-line module; the source monolith fell from 4,740 to 3,832 lines with the
exact 52-name surface preserved.
A ninth split isolated 12 operating-pipeline/scanner, search validation,
hypothesis store/brief, LLM suggestion/skip, extraction-order, and upstream-hint
tests in a 1,088-line module; the source monolith fell from 3,832 to 2,756 lines
with the exact 43-name surface preserved.
A tenth and final split partitioned the residual 31 tests into 1,156-line
watchlist/router, 1,006-line operator-workflow, and 618-line presentation
modules, then deleted the source monolith. All original 240 integrated-radar
test identities are now housed in focused modules no larger than 1,450 lines.
The same rule now applies beyond the retired integrated-radar file: the first
provider-readiness split moved 14 CryptoPanic/GDELT/RSS/news timing and safety
tests into a 1,113-line module while preserving the exact 88-name source surface.
A second provider split moved 16 exchange/universe/calendar normalization tests
and 10 Coinalyze/DEX/supply tests into 699- and 534-line modules; provider
readiness fell from 4,277 to 3,079 lines with the exact 74-name surface preserved.
A third and final provider split partitioned the residual 48 tests into
1,356-line activation/readiness/health, 940-line discovery-pipeline, and
817-line cache/scanner-report modules, then deleted the source monolith. All 88
original provider-readiness identities now live in focused sub-threshold homes.
The 5,002-line notification test file was likewise partitioned into seven
planning, routing, readiness, delivery, lane, operations, and inbox/rehearsal
modules ranging from 393 to 1,019 lines; all 66 identities were preserved and
the source monolith was deleted.
The 4,082-line outcomes test file was partitioned into five evidence/quality,
alert-outcome, feedback/calibration, burn-in/replay, and quality-feedback modules
ranging from 588 to 1,023 lines; all 49 identities were preserved and the source
monolith was deleted.
The 4,052-line artifact-doctor test file was partitioned into five core/schema,
notification, quality, reconciliation, and provider-conflict/integrated-safety
modules ranging from 623 to 1,082 lines; all 47 identities were preserved and
the source monolith was deleted.
The 2,991-line source-coverage test file was partitioned into four report,
catalyst-search, source-registry/pack, and evidence-acquisition modules ranging
from 405 to 1,214 lines; all 35 identities were preserved and the source
monolith was deleted.
The 1,826-line namespace-lifecycle test file was partitioned into four profile,
ledger/lock, scheduled-catalyst/unlock, and cross-namespace integration modules
ranging from 242 to 683 lines; all 30 identities were preserved and the source
monolith was deleted.
**Revisit when:** The standalone runner is intentionally retired, the project
adopts a different test-size threshold, or shared fixtures replace the current
API-helper compatibility layer.

## 2026-07-10 - Treat retained SQLite backups as immutable standalone snapshots
**Status:** accepted
**Decision:** Backup creation still uses SQLite's online backup API, but every
retained backup must be verified and restored through a read-only immutable URI
that cannot create WAL/SHM sidecars. A non-empty backup WAL blocks verification
rather than being ignored. Retention deletes sidecars paired with a pruned
snapshot, and operational status reports all matching sidecar and interrupted
temporary files as backup debris. Do not delete retained backup databases or
performance/research caches merely because they are ignored runtime state.
**Why:** The live directory contained exactly 14 valid retained databases but
also 34 WAL/SHM pairs. Restore checks had created one pair per WAL-mode snapshot,
and retention removed old `.db` files without their sidecars, leaving 20 orphan
pairs. All WALs were empty and all retained databases independently passed
integrity checks, so the debris was harmless but invisible to the previous
healthy status report.
**Revisit when:** Backups become writable by design, move to managed/encrypted
storage, or concurrent restore consumers require a different immutable snapshot
protocol.

## 2026-07-10 - Pin every third-party GitHub Action to a release commit
**Status:** accepted
**Decision:** Workflow `uses:` references for third-party actions must use the
full 40-character commit SHA of a reviewed upstream release and retain the
human-readable release tag in a comment. The current baseline is
`actions/checkout` v7.0.0 and `actions/setup-python` v6.3.0, both on Node 24.
Weekly GitHub Actions Dependabot updates may propose new release commits, but
they still require release-note review and the normal CI gate; mutable major,
branch, and floating tags are not accepted.
**Why:** The prior v4/v5 actions targeted deprecated Node 20 and GitHub was
forcibly substituting Node 24 at runtime. Moving to supported manifests removes
that compatibility ambiguity, while full commit pins prevent an upstream tag
move from changing executed CI code without a repository diff.
**Revisit when:** GitHub changes immutable-action policy, a pinned release is
withdrawn or compromised, or a new supported runtime requires another reviewed
release upgrade.

## 2026-07-10 - Hash-lock dependencies and verify Python 3.11/3.13 equally
**Status:** accepted
**Decision:** `requirements.in` is the human-edited direct dependency source;
the generated `requirements.txt` is the universal Python 3.11+ installation
lock and every resolved distribution must be exact-versioned and SHA-256
hashed. Bootstrap and CI must install it with `--require-hashes`; dependency
changes must pass deterministic uv regeneration plus pip-audit. Push/PR CI runs
the canonical `make verify` on both Python 3.11 and 3.13, while the repository
defaults locally to 3.13. Dependabot reviews pip and GitHub Actions updates
weekly, but no update is accepted unless the lock and both-version gates pass.
**Why:** Lower bounds alone produced different environments over time, CI only
covered 3.11 while the deployed development venv used 3.13, and the project had
no repeatable vulnerability gate. A universal lock retains the one necessary
NumPy version fork while making every installed artifact reviewable and
integrity-checked.
**Revisit when:** Python 3.11 support is intentionally retired, Python 3.14 is
adopted, the project moves to a standardized `pylock.toml` workflow supported by
all deployment tooling, or a lock/audit incident requires a different resolver.

## 2026-07-10 - Tracked contracts and reports require explicit authoring commands
**Status:** accepted
**Decision:** Tests, verification gates, daily burn-in, and other runtime paths
must not regenerate tracked research contracts or reports as a side effect. The
Event Alpha North Star and burn-in contract may be rewritten only through their
explicit authoring targets. Daily burn-in must use the read-only contract check,
and subprocess regressions for this boundary must run against temporary or fake
repository roots with byte-preservation assertions.
**Why:** The candidate-mode fixture smoke was green while its contract step
rewrote `research/event_alpha_burn_in_contract.json` and `.md` solely to refresh
`generated_at`. That made verification non-hermetic, dirtied developer and CI
checkouts, and blurred the boundary between an authored policy contract and
runtime evidence.
**Revisit when:** Tracked reports move to a deterministic generated-source
system with an explicit freshness gate, or the burn-in contract is replaced by
a versioned immutable contract store.

## 2026-07-10 - Retain extreme paper outcomes and expose robust diagnostics
**Status:** accepted
**Decision:** Closed paper trades with extreme returns remain in canonical
scoreboard aggregates. The human-readable scoreboard must show a trimmed-mean
cross-check and explicit retained outlier rows, while the research report carries
structured price-recomputation and state diagnostics. Do not cap, winsorize,
delete, or automatically exclude these rows, and do not apply stop scenarios or
state thresholds to live behavior from this review.
**Why:** Seven of 75 closed rows have absolute returns of at least 50%, but their
stored prices recompute exactly, matched signals and independent 7-day outcomes
agree, and provider price/market-cap histories support real high-volatility moves
rather than an identity, database, or redenomination error. Removing them would
hide genuine tail risk; presenting only averages lets them obscure the typical
trade.
**Revisit when:** Cross-provider evidence contradicts CoinGecko history, an
identity/corporate-action mismatch is proven, or a separately reviewed
path-aware stop/risk policy has enough live evidence for promotion.

## 2026-07-10 - Exclude observed fiat-pegged assets by exact identity
**Status:** accepted
**Decision:** EURC is a `stable_like` universe exclusion in both shared
CoinGecko hygiene and exchange-based backtest pools. Prefer exact observed
symbols or identities for non-USD fiat-pegged products instead of broad terms
such as `euro` that could remove unrelated crypto assets.
**Why:** The latest persisted audit kept EURC at rank 111 even though stablecoins
are unsuitable for the scanner's directional RSI, outcome, paper, and backtest
universes. Exact identity closes the observed leak while limiting false-positive
risk.
**Revisit when:** CoinGecko supplies reliable asset categories, another
fiat-pegged product leaks through, or an exact identity is reused by a legitimate
non-pegged asset.

## 2026-07-10 - One authoritative Event Alpha burn-in maturity gate
**Status:** accepted
**Decision:** The policy-scoped 30-day North Star operations scorecard is the
sole source of truth for Event Alpha promotion and calibrated research-send
maturity. Feedback readiness reports only whether review labels can be
collected, while operational burn-in readiness reports only whether another
no-send research cycle can run. Neither status may imply contract maturity.
V1/day-1 readiness also requires a successful matching run, and all promotion
lanes remain frozen while the authoritative scorecard reports
`enough_data=false`.
**Why:** The prior commands mixed three different meanings of readiness, used a
legacy seven-day view, and could report feedback or day-1 readiness while the
North Star minimums were unmet. Two command paths also crashed before showing
any result, making operator output both contradictory and unreliable.
**Revisit when:** The 30-day minimums are met and reviewed, or the North Star
contract is explicitly superseded by a new accepted operating contract.

## 2026-07-09 - Runtime credentials and recipient identifiers stay private by default
**Status:** accepted
**Decision:** All configured credentials and recipient/account identifiers must
pass through `config.redact_token` before entering logs or operator error text.
Runtime credential, log, SQLite, and backup files use owner-only permissions
(`0600` files and `0700` sensitive directories), launchd templates use a `077`
umask, and source-with-artifacts exports scan exact locally configured sensitive
values in a temporary ZIP before atomically replacing the review artifact.
Tracked examples must use explicit placeholders rather than real recipient IDs.
**Why:** A historical Telegram request exception placed the bot token and chat
identifier in an ignored log, while permissive file modes and path-only ZIP
validation left avoidable disclosure paths. Privacy controls should be enforced
by code and export gates, not depend on each caller remembering to scrub output.
**Revisit when:** Runtime storage moves off the local Mac, a new credential or
notification channel is added, or export artifacts need an approved encrypted
secret-bearing format.

## 2026-07-09 - Risk-based verification replaces full pytest on every prompt
**Status:** accepted
**Decision:** Do not run the full pytest package gate or `make verify` by
default on every small prompt. Ordinary changes should use the smallest
meaningful gate: targeted pytest file/package for touched code, compileall for
Python import/syntax risk, matching Event Alpha/provider/notification smoke or
doctor targets for artifact behavior, and static/JSON/Markdown checks for
docs/report-only changes. Full `make verify` remains the release/risky/shared
code gate and should run before live/provider activation work, CI-parity
handoff, broad shared-module changes, or after a cluster of roughly 5-10
low-risk prompts. If full `make verify` is skipped, the handoff must say why and
list the targeted gate that passed. CI should invoke the canonical full
`make verify` once, not run standalone and pytest separately before repeating
them inside the same release gate.
**Why:** The full pytest package suite currently adds about 3.5 minutes and
`make verify` also duplicates the standalone compatibility runner. That is too
slow for normal iteration and encourages waiting instead of making focused,
verified changes. Keeping full verify as a deliberate release/risk gate preserves
coverage without taxing every small prompt.
**Revisit when:** Targeted gates miss a regression that full verify would have
caught, CI timing changes materially, or the pytest suite is split so the full
gate becomes fast enough for every prompt again.

## 2026-07-05 - Test optimization keeps strict verify intact
**Status:** superseded by `2026-07-09 - Risk-based verification replaces full pytest on every prompt`
**Decision:** `make verify` remains the strict pre-commit/release gate and still
runs both the standalone compatibility runner and the hard pytest suite. Faster
developer loops are explicit: `make verify-fast` skips only the duplicate
standalone pass while keeping hard pytest plus runtime smokes,
`make test-pytest-durations` profiles slow tests, and
`make test-pytest-parallel` uses xdist with external pytest plugin autoload
disabled.
**Why:** The duplicated standalone-plus-pytest gate is intentionally conservative
after the prior CLI ops regression, but it is too slow for every local edit.
Separate fast/timing/parallel targets improve iteration without weakening the
release gate or changing product behavior.
**Revisit when:** pytest owns equivalent standalone-runner compatibility
coverage, xdist proves unsafe for shared artifact tests, or the project adopts a
different mandatory test runner.

## 2026-07-05 - Event Alpha Radar North Star governs post-refactor development
**Status:** accepted
**Decision:** Future Event Alpha development should align to
`research/EVENT_ALPHA_RADAR_NORTH_STAR.md` and
`research/EVENT_ALPHA_RADAR_NORTH_STAR.json`. The North Star defines the radar
architecture, six opportunity lanes, bounded human-labeling role, 30-day
no-send burn-in contract, and source activation order. Suggestions and priors
remain recommendations-only with `auto_apply_thresholds=false`; any automatic
threshold application would require a separate explicit decision.
**Why:** The refactor is complete, so the next durable constraint is product
focus: a measurable crypto market radar with burn-in evidence, not more
scaffolding. The contract preserves research-only, no-trading, no-paper,
no-execution, no-send-by-default, no-live-provider-by-default, and
no-Event-Alpha-created `TRIGGERED_FADE` boundaries.
**Revisit when:** the 30-day burn-in minimums are met and reviewed, a lane needs
schema-changing semantics, or a future activation pass proposes auto-applied
thresholds.

## 2026-07-05 - Architecture health tooling uses permanent project_health names
**Status:** accepted
**Decision:** Refactor-era static tooling is no longer a top-level implementation
surface. Permanent architecture/project-health tooling lives under
`crypto_rsi_scanner.project_health.*`, canonical operator targets use
`make architecture-*`, and canonical checked-in reports use `ARCHITECTURE_*` or
`PROJECT_HEALTH_*` names. Old `make refactor-*` targets are retired. Historical
`REFACTOR_*` report files live only under
`research/archive/refactor_history/` as archived history and are not regenerated
by current tooling.
**Why:** The Event Alpha refactor is accepted, so current source and runbooks
should no longer make the project look like it is in a temporary migration
state. Permanent naming makes future maintenance ownership clearer while
retiring local automation aliases from current runbooks.
**Revisit when:** a future cleanup removes the archived historical reports or
artifact schema v2 removes old historical field aliases.

## 2026-07-05 - Final refactor terminology uses historical/transitional wording
**Status:** superseded by `2026-07-05 - Architecture health tooling uses
permanent project_health names`
**Decision:** The historical/transitional wording policy remains, but the
canonical static checker is now `make architecture-transitional-file-check`.
Old `make refactor-*` targets are retired. Canonical CLI flags continue to
include historical-artifact aliases while old `legacy` flags and report fields
remain supported for backwards compatibility and historical artifact row
semantics.
**Why:** Refactor v3 is accepted with old flat Event Alpha shims retired, so
continuing to call current modules “legacy” makes future ownership ambiguous.
The terminology report makes remaining `legacy` occurrences explicit and gates
stale source wording without breaking existing CLI/scripts/artifact schemas.
**Revisit when:** artifact schema v2 removes legacy-named compatibility fields,
or a future CLI-breaking release retires the old parser aliases.

## 2026-07-05 - Final Event Alpha refactor accepted: no legacy files, no old flat Event Alpha imports, canonical module architecture only
**Status:** accepted
**Decision:** The final Event Alpha refactor is accepted. No internal
`legacy.py`, `legacy_*.py`, `*_legacy.py`, `compat.py`, or `compatibility.py`
migration files remain; old flat Event Alpha import paths are retired; no
nonessential public shims remain; and new code must use canonical
`crypto_rsi_scanner.event_alpha.*` package paths. `scanner.py` remains only the
CLI entrypoint wrapper, and `event_fade.py` remains intentionally outside Event
Alpha as the safety boundary for `TRIGGERED_FADE`.
**Why:** The final retirement and refactor reports show
`legacy_named_files_remaining=0`, `legacy_named_files_with_implementation=0`,
`compatibility_named_files_remaining=0`, `old_path_internal_imports=0`,
`old_path_test_imports=0`, `old_path_docs_references=0`,
`nonessential_shims_remaining=0`, `retained_public_entrypoints=0`,
`production_files_over_1500_lines=0`, `functions_over_150_lines=0`, and
`legacy_unregistered=0`. The integrated radar doctor and full safe verification
passed without live provider calls, live sends, trading, paper trading, normal
RSI writes, or Event Alpha-created `TRIGGERED_FADE`.
**Revisit when:** an explicit public compatibility requirement is accepted, a
new legacy/compat file is proposed, a deleted old flat import path needs to be
restored, or a future package-boundary refactor changes Event Alpha ownership.

## 2026-07-05 - Flat Event Alpha shims are fully retired
**Status:** accepted
**Decision:** No old flat Event Alpha public compatibility shims remain. Deleted
old imports are allowed to fail and are covered by
`tests/event_alpha/test_no_old_event_alpha_imports.py`; new code and docs must
use canonical `crypto_rsi_scanner.event_alpha.*` package paths. `scanner.py`
remains the historical CLI entrypoint, and `event_fade.py` remains
intentionally outside Event Alpha.
**Why:** The final shim/old-import/legacy-retirement reports now show
`active_shims=0`, `retained_public_shims_count=0`,
`nonessential_shims_remaining=0`, `old_path_internal_imports=0`,
`old_path_test_imports=0`, `old_path_docs_references=0`, and
`old_path_import_allowed_exceptions=0`. Keeping empty public compatibility
surface documentation avoids future agents reintroducing old shim paths.
**Revisit when:** a compatibility-breaking release explicitly accepts a new
temporary public bridge, or an external consumer requirement proves a deleted
old path must be restored.

## 2026-07-05 - Accepted refactor v3 exceptions are not blockers
**Status:** accepted
**Decision:** Refactor v3 reports use four statuses: `pass`,
`accepted_with_documented_exceptions`, `pending`, and `blocked`. The current
v3 state is `accepted_with_documented_exceptions`: hard blockers are zero,
`acceptance_status=accepted`, `critical_gate_status=pass`, and the remaining
over-1,200-line production files plus storage mixin class exceptions are
documented accepted exceptions, not pending work.
**Why:** The release-candidate report already accepted the refactor with those
documented warnings, but the final/size/class reports still surfaced the same
warnings as auto-accept blockers. Treating accepted warnings as pending created
contradictory operator status without identifying real refactor work.
**Revisit when:** a new production file crosses 1,200 lines without an accepted
exception, any production file crosses 1,500 lines, a new oversized class lacks
an accepted owner note, or the project intentionally changes the v3
zero-exception auto-accept definition.

## 2026-07-05 - Full pytest suite is a hard verification gate
**Status:** superseded by `2026-07-09 - Risk-based verification replaces full pytest on every prompt`
**Decision:** `make verify` must run the full pytest-compatible suite through
`make test-full`, with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, and fail if pytest
is unavailable. `pytest` is a declared dependency in `requirements.txt`.
**Why:** The CLI refactor introduced wrong-depth function-local imports that
broke production ops commands such as `--status`, `--backup-db`,
`--verify-restore`, and `--maintenance` while the previous verification path
still passed. The package pytest suite now contains direct ops command smokes
and a static relative-import integrity guard, so skipping pytest would recreate
that blind spot.
**Revisit when:** the standalone runner fully owns equivalent CLI dispatch and
import-integrity coverage, or the project adopts a different mandatory test
runner with the same ops-command guarantees.

## 2026-07-05 - Shim dependency scans are source-scoped by default
**Status:** accepted
**Decision:** Event Alpha shim dependency and old-import scans inspect source,
tests, scripts, top-level docs, Makefile, research Markdown, and selected
checked-in JSON by default. Runtime artifact directories such as
`event_fade_cache/` are excluded unless an operator explicitly passes
`--include-runtime-artifacts`; scans keep file-size limits, scan accounting, and
cache/freshness metadata in the generated reports.
**Why:** Shim-retirement and old-import gates are source-compatibility checks.
Parsing large runtime artifacts by default makes refactor reports slow and can
produce irrelevant old-path references from historical research output.
**Revisit when:** runtime artifact content becomes a required compatibility
contract, or a future artifact-retention policy needs a separate explicit
runtime-artifact audit.

## 2026-07-05 - Event Alpha refactor v3 accepted
**Status:** accepted
**Decision:** Event Alpha refactor v3 is accepted as the current package,
shim, doctor, namespace, size, and test baseline. The only top-level
implementation event module is `event_fade.py`, which remains intentionally
outside Event Alpha. No old flat Event Alpha public compatibility shims remain;
deleted old imports are tombstoned, and new code must use canonical package
paths.
**Why:** The full v3 release-candidate gauntlet passed (`26/26` commands), the
critical RC gates passed, and `research/REFACTOR_V3_RELEASE_CANDIDATE_REPORT.md`
records zero nonessential shims, zero old-path internal/test/docs references,
zero production files over 1,500 lines, zero functions over 150 lines, zero
unresolved over-1,200-line production files, zero unresolved multi-class
modules, zero unknown namespaces, and zero doctor registry legacy-unregistered
checks. Remaining over-1,200 files and storage mixin classes are accepted
warnings with owner notes and revisit conditions.
**Revisit when:** a public compatibility bridge is proposed for restoration, a production
file crosses a blocker threshold, a new class/model-bundle exception is needed,
or a future provider activation pass changes Event Alpha package boundaries.

## 2026-07-05 - Retained Event Alpha shims are public entrypoints only
**Status:** superseded
**Decision:** Superseded by “Flat Event Alpha shims are fully retired.” The
retained public shim set is now empty.
**Why:** A later pass removed the remaining public compatibility shims after
canonical imports, tests, docs, and reports stopped depending on them.
**Revisit when:** an external consumer requirement proves a deleted old path
must be restored as an explicitly documented bridge.

## 2026-07-05 - Refactor v3 production size warning threshold is 1,200 lines
**Status:** accepted
**Decision:** Production source files over 1,200 lines are v3 maintainability
warnings that must be split when low risk or explicitly documented as accepted
exceptions with owner notes and revisit conditions. Production source files over
1,500 lines remain blockers unless an exception is explicitly accepted in the
refactor reports. Production functions over 150 lines remain blockers unless
accepted, and class ownership gates continue to publish accepted model bundles
and class exceptions separately from unresolved debt.
**Why:** The v2/v3 refactor already eliminated production files over 1,500
lines. The next useful pressure is keeping near-threshold modules visible
without forcing risky behavior changes in stable provider, notification, radar,
or CLI paths.
**Revisit when:** any accepted over-1,200-line file is touched for non-trivial
behavior changes, a safe package split can preserve imports and artifacts, or a
new production file would cross 1,200 lines.

## 2026-07-04 - Multi-class production modules require model-bundle registration
**Status:** accepted
**Decision:** Production modules may contain multiple public classes only when
they are explicitly registered as accepted model bundles or documented module
exceptions. The class ownership report must publish
`multi_public_class_modules`, `accepted_model_bundles`, and
`unresolved_multi_class_modules`; refactor gates treat unresolved modules as
blockers while keeping accepted bundles visible for review.
**Why:** A raw count mixed small dataclasses/enums/protocol DTOs with
behaviorful modules, making the gate noisy. Explicit registration preserves old
imports and behavior while making future unregistered multi-class modules fail
the refactor gate.
**Revisit when:** a registered bundle gains behaviorful public classes,
contains a class over the advisory line limit, or a package split can preserve
imports with low risk.

## 2026-07-04 - Storage mixins remain the only oversized class exceptions
**Status:** accepted
**Decision:** After the provider, LLM, CoinGecko, and canonical asset class
ownership cleanup, the only accepted classes over the 75-line advisory limit are
`SignalsMixin`, `WatchlistMixin`, and `MigrationsMixin` under
`crypto_rsi_scanner.storage_parts`. Provider shells, LLM providers, and
`CanonicalAsset` should stay in their focused module homes, with compatibility
exports preserved where public imports already exist.
**Why:** The remaining oversized classes are DB persistence mixins where a split
could affect SQLite schema, signal writes, watchlist behavior, or migration
ordering. This pass is behavior-preserving, so the reports document those mixins
as accepted exceptions instead of changing persistence internals.
**Revisit when:** storage schema v2, a repository-layer split, or an explicit
migration-tested DB refactor is planned with backup/restore and roundtrip
coverage.

## 2026-07-04 - Second non-public Event Alpha shim wave retired
**Status:** accepted
**Decision:** Remaining non-public old flat Event Alpha shims may be deleted
after Makefile module entrypoints, docs, and compatibility tests are moved to
canonical package paths. The only retained old shim modules are explicitly
public compatibility wrappers listed in
`crypto_rsi_scanner/event_alpha/MODULE_MAP.md`; `scanner.py` remains the CLI
entrypoint wrapper, and `event_fade.py` remains the safety boundary outside
Event Alpha. Deleted old paths are tracked in
`research/EVENT_ALPHA_DELETED_SHIMS.md/json` and final retained/deleted status
is tracked in `research/EVENT_ALPHA_FINAL_SHIM_STATUS.md/json`.
**Why:** The old import check reports zero internal old-path imports, so
retaining non-public shims only preserves obsolete surfaces. Moving Makefile
targets to canonical packages preserves target names while allowing the old
module files to fail import intentionally.
**Revisit when:** a retained public compatibility wrapper has an accepted
deprecation/removal plan or a third-party/public entrypoint requirement is
identified.

## 2026-07-04 - First non-public Event Alpha shims retired
**Status:** accepted
**Decision:** The first refactor v3 deletion batch may remove old flat Event
Alpha shims that are not public compatibility entrypoints, are not
`scanner.py`, are not `event_fade.py`, have zero internal, Makefile, script,
dynamic, and artifact-documentation references, and were referenced only by the
dedicated legacy import compatibility test. Deleted paths are recorded in
`research/EVENT_ALPHA_DELETED_SHIMS.md/json`; retained old paths remain in
`crypto_rsi_scanner/event_alpha/MODULE_MAP.md` and
`crypto_rsi_scanner/event_alpha/SHIM_REGISTRY.json`.
**Why:** Canonical imports are already enforced, so keeping unused non-public
shims only preserves obsolete import surfaces. Removing the proven-unused batch
reduces refactor v3 shim debt while preserving public wrappers, Makefile module
entrypoints, `scanner.py`, and the `event_fade.py` safety boundary.
**Revisit when:** another retained shim has zero dependency-report references
or is explicitly accepted as a permanent public compatibility entrypoint.

## 2026-07-04 - Event Alpha old flat imports are compatibility-only
**Status:** accepted
**Decision:** Superseded by “Flat Event Alpha shims are fully retired.” Internal
project code and ordinary tests must import canonical
Event Alpha package paths under `crypto_rsi_scanner.event_alpha.*` or other new
canonical packages. Old flat Event Alpha paths are now deleted/tombstoned, and
failure coverage lives in `tests/event_alpha/test_no_old_event_alpha_imports.py`.
`make event-alpha-old-import-check` is the lint-style gate for this boundary and
its counters are surfaced in shim, doctor, and refactor reports.
**Why:** The refactor v3 phase should retire internal dependence on old flat
modules without deleting public compatibility shims prematurely. A focused
allowlist protects CLI/Make/import compatibility while preventing new code from
drifting back to old paths.
**Revisit when:** a future accepted shim-removal phase deletes old paths or
declares a specific old module a permanent public compatibility entrypoint.

## 2026-07-04 - Event Alpha refactor v3 finalization contract
**Status:** accepted
**Decision:** Refactor v3 is the finalization phase after accepted v2
compatibility. Old top-level Event Alpha shim paths are temporary and should be
removed unless explicitly retained as public compatibility entrypoints.
`scanner.py` remains a public CLI entrypoint compatibility wrapper, and
`event_fade.py` remains intentionally outside Event Alpha because
`TRIGGERED_FADE` ownership belongs only to `event_fade.py` plus `proxy_fade`.
New code must import new package paths only. V3 reports must expose stricter
gates for nonessential shims, old-path internal imports, public compatibility
shims, shim removal blockers, production files over 1,200 and 1,500 lines,
public classes not in their own modules, accepted class exceptions, functions
over 150 lines, and old-path documentation references.
**Why:** Refactor v2 accepted the compatibility shim state, but fully finishing
the refactor requires a measurable removal contract before deleting old paths or
relitigating safety-sensitive boundaries. Keeping v3 as a pending gate report
lets future passes remove or explicitly retain shims without changing runtime
behavior in this setup pass.
**Revisit when:** `research/REFACTOR_FINAL_REPORT.md/json` reports
`v3_auto_accept_ready=true`, especially `nonessential_shims_remaining=0`,
`old_path_internal_imports=0`, and no unaccepted v3 size/class ownership gaps.

## 2026-07-04 - Event Alpha shim retirement requires dependency proof
**Status:** accepted
**Decision:** Old Event Alpha top-level shims remain available until the shim
dependency report proves zero internal references and a dedicated removal phase
is declared. New implementation code must import new package paths, and the
artifact doctor warns on internal imports from old shim paths. `event_fade.py`
remains intentionally outside Event Alpha and is not a shim-removal candidate.
**Why:** The project still has compatibility tests, Makefile module entrypoints,
and docs that deliberately exercise or document old imports. Removing shims
without an explicit dependency inventory would risk old CLI/Make/import
behavior and could blur the `TRIGGERED_FADE` ownership boundary.
**Revisit when:** `research/EVENT_ALPHA_SHIM_DEPENDENCY_REPORT.md/json` shows a
shim has no internal, test, Makefile, docs, script, dynamic, or artifact
references, and a later accepted refactor release declares that old import
compatibility may be retired.

## 2026-07-04 - Final class ownership exceptions are documented
**Status:** accepted
**Decision:** The remaining 14 oversized classes are accepted refactor v2
exceptions with explicit owner notes and revisit conditions in
`research/REFACTOR_CLASS_OWNERSHIP_REPORT.md/json`. They are advisory class
ownership debt only, not product behavior blockers, while reports must continue
to expose `accepted_class_exceptions`, `remaining_class_ownership_debt`,
`provider_class_split_status`, `storage_mixin_exception_status`, and
`near_threshold_file_status`.
**Why:** Splitting these provider adapters, LLM providers, storage mixins, and
field-rich data models in a final cleanup pass would risk request contracts,
redaction, no-call defaults, SQLite behavior, or schema identity semantics
without adding user-visible value. The safer baseline is to document them
precisely and keep progressive size gates blocking new violations.
**Revisit when:** one of the recorded per-class revisit conditions triggers,
such as a new provider mode, storage schema migration, shared provider
transport, or schema v2 identity split.

## 2026-07-04 - Production size gates are separate from test and ownership debt
**Status:** accepted
**Decision:** Refactor acceptance distinguishes production file-size gates from
test-file size and advisory class/function ownership. A production Python file
over 1,500 lines is a warning, over 2,000 lines is a blocker, and over 3,000
lines is a hard blocker. Test file size remains tracked separately, and
classes/functions over the advisory limits are reported as the next ownership
burn-down target rather than blocking the accepted production-size milestone.
**Why:** The remaining large production files were split into focused packages
with old import compatibility preserved, and the safe 23-command regression
stack passed. Keeping production/test/ownership counters separate prevents
test-suite compatibility debt or known large functions from masking the fact
that production file-size blockers are now gone.
**Revisit when:** the class/function ownership inventory has been reduced
enough to make those advisory thresholds blocking, or when a future v2/v3
compatibility break retires old import paths and compatibility binders.

## 2026-07-03 - Split binders accepted for Event Alpha legacy cores
**Status:** accepted
**Decision:** Large Event Alpha radar legacy cores may be decomposed into
focused implementation modules while the old `legacy.py`/`legacy_*` files remain
small compatibility binders that re-export public names and share legacy globals
into the split modules for old monkeypatch/import behavior. Size-gate aliases
must be updated when a known legacy violation moves so the progressive gate
blocks new sprawl rather than behavior-preserving relocation.
**Why:** This approach reduced the impact hypotheses, validation, core store,
evidence acquisition, discovery, watchlist, and near-miss legacy blockers
without changing CLI behavior, artifact schemas, provider readiness, route
gates, no-send notification behavior, or research-only safety invariants.
**Revisit when:** old import paths are formally deprecated in a future v2/v3
compatibility break, or when the remaining split modules can be reduced further
without requiring shared legacy globals.

## 2026-07-03 - Legacy implementation size gates define refactor completion
**Status:** accepted
**Decision:** Small public wrappers and compatibility aggregators are not enough
to mark the refactor complete. `*_api.py` and `legacy_*` implementation cores
are transitional only: files over 1,500 lines are warnings, and files over
3,000 lines block the refactor final/completion reports until they are split or
an explicit baseline decision is made.
**Why:** The earlier refactor hid behavior-compatible monoliths behind small
facades. Legacy-aware gates keep the migration honest while preserving CLI,
Makefile, import, artifact, provider-readiness, and notification behavior.
**Revisit when:** no legacy implementation file remains over 3,000 lines, or a
specific large compatibility core is deliberately accepted with documented
blockers, next split target, and parity tests.

## 2026-07-03 - Event Alpha refactor v2 accepted
**Status:** accepted
**Decision:** Event Alpha refactor v2 is accepted as the behavior-preserving
baseline for resuming provider activation work. `crypto_rsi_scanner/scanner.py`
is now a compatibility facade over `crypto_rsi_scanner.cli`, Event Alpha command
dispatch and services live under `crypto_rsi_scanner/cli/`, top-level
Event Alpha modules are active shims except the intentionally separate
`event_fade.py`, artifact doctor is schema/plugin-backed at the public surface,
and `research/REFACTOR_RELEASE_CANDIDATE_REPORT.md/json` is the canonical
acceptance artifact.
**Why:** The full safe regression gauntlet passed with no live provider calls by
default, no live Telegram sends, no trading/paper/execution changes, no Event
Alpha normal RSI signal writes, no Event Alpha-created `TRIGGERED_FADE`, and no
secret leakage. Compatibility paths remain available while the remaining large
legacy cores are tracked by size gates and completion maps.
**Revisit when:** a future v2/v3 compatibility break proposes warnings or
removal for old import paths, or a focused pass moves command families out of
`cli/services/scanner_api.py` and replaces the remaining service refresh
helpers with direct imports under parity tests.

## 2026-07-03 - Shared storage, backtest, and schema modules use facades plus parts
**Status:** accepted
**Decision:** Shared RSI/backtest/storage refactors should keep public facades
stable while moving implementation ownership into focused package parts.
`crypto_rsi_scanner.storage.Storage` remains the storage import contract over
`storage_parts/`; `python -m crypto_rsi_scanner.backtest` and historical
`crypto_rsi_scanner.backtest` helper imports remain compatible over
`backtest_parts/`; `event_alpha/artifacts/schema_v1.py` remains the schema v1
compatibility aggregator over `event_alpha/artifacts/schema/`.
**Why:** These modules touch SQLite writes, paper-book reporting, PIT backtest
research, and schema-backed doctor validation. Facades plus explicit parts let
future work reduce large compatibility cores without changing DB schema,
backtest output semantics, paper behavior, Event Alpha route gates,
notification behavior, or no-live/no-send safety.
**Revisit when:** a smaller helper family can be moved out of a compatibility
core with fixture-backed parity tests, or a later v2 compatibility break
explicitly retires old import paths.

## 2026-07-03 - Progressive refactor size gates are baseline-relative
**Status:** accepted
**Decision:** `make refactor-size-gates` is the progressive size guard for this
refactor track. Existing file/function/class/module ownership violations are
warnings when recorded in `research/REFACTOR_SIZE_BASELINE.json`; newly
introduced violations are blockers unless the baseline is explicitly refreshed
with `make refactor-size-baseline-update`.
**Why:** The repository still has known large compatibility cores. A
baseline-relative gate prevents new sprawl while allowing conservative,
behavior-preserving migrations to continue.
**Revisit when:** the remaining compatibility cores are small enough to make
the absolute thresholds blocking for all violations rather than only new ones.

## 2026-07-03 - Medium radar and provider modules use package ownership
**Status:** accepted
**Decision:** Medium Event Alpha radar and reusable provider adapters should use
focused package homes with compatibility cores. Validation, discovery,
watchlist, near-miss, CryptoPanic, Coinalyze, Bybit announcements, Binance
announcements, and provider-health wrappers now expose package-level old import
compatibility while new implementation work belongs in focused modules such as
`models.py`, `provider.py`, `client.py`, `parser.py`, `loader.py`,
`entries.py`, `review.py`, and `report.py`.
**Why:** This continues the behavior-preserving refactor without changing
provider request contracts, source parsing, artifact schemas, Event Alpha route
gates, no-call defaults, no-send behavior, or research-only safety boundaries.
It also keeps CryptoPanic and Coinalyze reusable adapters outside Event Alpha
provider-readiness orchestration.
**Revisit when:** a focused helper family can be moved out of a legacy core
with fixture-backed parity tests, or an old import path can be retired through
an explicit v2 compatibility break.

## 2026-07-03 - Large Event Alpha internals use wrapper plus legacy-core split
**Status:** accepted
**Decision:** The largest Event Alpha internals now expose small public wrappers
or packages while preserving behavior in legacy cores. New implementation logic
belongs in the focused module homes under `notifications/`,
`artifacts/research_cards/`, `artifacts/daily_brief/`, `radar/integrated/`,
`radar/impact_hypotheses/`, `radar/core/`, and `radar/evidence/`. The
compatibility cores remain only to preserve current behavior while individual
models, renderers, writers, selectors, and sections are migrated behind tests.
**Why:** This makes the package ownership measurable without changing
notification gates, delivery ledger schema, card copy, daily-brief grouping,
integrated radar lane policy, provider guards, source coverage, route gates, or
research-only safety invariants.
**Revisit when:** a focused migration can move one section/helper family out of
the legacy core with byte/semantic artifact comparisons or fixture tests.

## 2026-07-03 - Artifact doctor public orchestrator accepted with legacy core
**Status:** accepted
**Decision:** `crypto_rsi_scanner.event_alpha.doctor.artifact_doctor` is the
small public artifact-doctor orchestrator/export surface. New doctor logic must
land in focused modules such as `execution.py`, `context.py`, `discovery.py`,
`aggregation.py`, `result.py`, `counters.py`, `issues.py`, `status.py`,
`report_sections/`, and `checks/`. The behavior-compatible core remains in
`crypto_rsi_scanner.event_alpha.doctor.artifact_doctor_core` until individual
checks are migrated behind regression fixtures.
**Why:** This meets the public size and registry gates while preserving doctor
output semantics, counter names, stale namespace behavior, schema counters,
strict/WARN handling, old imports, and old result constructor patterns.
**Revisit when:** a focused migration can move one legacy check family into a
plugin without changing `format_artifact_doctor_report()` output or strict mode
status for existing fixture namespaces.

## 2026-07-03 - Event Alpha module migration finished with neutral event_core
**Status:** accepted
**Decision:** Remaining Event Alpha-specific top-level implementation modules
have package homes with active shims. Shared event infrastructure now lives in
`crypto_rsi_scanner.event_core`: `event_core.clock` for deterministic research
clock helpers and `event_core.models` for shared event dataclasses. The old
`crypto_rsi_scanner.event_clock` and `crypto_rsi_scanner.event_models` import
paths were later retired by the second v3 shim deletion pass after internal
imports moved to canonical `crypto_rsi_scanner.event_core.*` paths.
`event_fade.py` stays intentionally outside Event Alpha and remains the only
top-level `event_*.py` implementation excluded from shim ownership.
**Why:** This clears the Event Alpha module-migration backlog without burying
shared provider/radar infrastructure under Event Alpha, preserves old imports,
and keeps the `TRIGGERED_FADE` safety boundary unchanged: Event Alpha may write
`FADE_SHORT_REVIEW` research artifacts, but `TRIGGERED_FADE` remains owned only
by `event_fade.py` plus proxy-fade eligibility.
**Revisit when:** a future v2 migration explicitly deprecates old import paths
in development mode, or a dedicated behavior-freeze pass splits `event_fade.py`
without moving TRIGGERED_FADE ownership into Event Alpha.

## 2026-07-03 - CLI parser split and Event Alpha command registry accepted
**Status:** accepted
**Decision:** The CLI parser may now be maintained through category extension
modules and a generated flag snapshot, while `commands_event_alpha.handle()`
stays as a small registry bridge. The command registry is metadata-first and
keeps no-live-provider and no-send defaults explicit for Event Alpha commands.
Scanner-owned command bodies remain behind compatibility wrappers until they
can be moved safely with focused tests.
**Why:** This reduces `build_parser()` to a small orchestrator and
`commands_event_alpha.handle()` to a registry call without changing any CLI
flags, defaults, Make targets, provider-readiness behavior, notification gates,
or Event Alpha route gates. The remaining scanner and service-bind targets are
measured blockers rather than reasons to move broad command bodies in one risky
batch.
**Revisit when:** a scanner-body extraction can move a narrow command family
into service modules with old-name wrappers, no recursion, and command-specific
dispatch tests proving behavior parity.

## 2026-07-02 - Event Alpha service split and 25-module migration accepted with bind-site blockers
**Status:** accepted
**Decision:** The current behavior-preserving refactor continuation is accepted:
`crypto_rsi_scanner/cli/services/event_alpha.py` is now a compatibility
aggregator over focused Event Alpha service modules, 25 additional top-level
Event Alpha modules have package homes with active shims, and
`event_fade.py` remains explicitly outside Event Alpha. `event_clock.py` and
`event_models.py` were later moved to neutral `event_core` package paths and
their old flat shims were retired in the second v3 shim deletion pass.
**Why:** The split reduces the Event Alpha CLI service file to 46 lines and
raises the active-shim count to 120 with zero active-shim implementation
violations, while preserving old import paths and research-only/no-send/no-live
guards. The final refactor gate remains pending only for measured blockers:
`scanner.py` is still 7,744 lines against the <6,500 target, Event Alpha
service modules still have 26 `bind_scanner_globals(...)` call sites, and the
doctor registry still reports `legacy_unregistered=15` against the <=5 target.
**Revisit when:** the next CLI pass can replace scanner-global binding with
explicit imports under command dispatch tests, the scanner drops below 6,500
lines, or the remaining doctor sites can be migrated without changing
strict/WARN semantics.

## 2026-07-02 - Event Alpha module migration accepted with final gates pending
**Status:** accepted
**Decision:** The 28-module Event Alpha migration batch is accepted as a
behavior-preserving refactor continuation: old top-level imports remain active
shims, `event_fade.py` remains explicitly outside Event Alpha, the remaining
implementation modules are classified, and no research-only safety gates were
changed. The final refactor gate remains pending for the documented scanner,
CLI-service, and doctor-plugin blockers rather than forcing risky movement in
this pass.
**Why:** Verification passed across the standalone runner, safe pytest,
compileall, shim report, refactor final report, namespace lifecycle, integrated
radar smoke/doctor, provider readiness, Coinalyze preflight/rehearsal, market
anomaly, official exchange, scheduled catalyst, unlock risk, derivatives,
fade-review, source coverage, daily brief, no-send preview, strict CryptoPanic
rehearsal doctor, and `make verify`. Current measured state: active shims 95,
partial shims 0, unmigrated modules 30, active-shim logic violations 0,
`scanner.py` 7,744 lines, `cli/services/event_alpha.py` 3,938 lines with 26
service bind sites, and `legacy_unregistered=15`.
**Revisit when:** `scanner.py` drops below 6,500 lines, Event Alpha CLI service
modules are split below the requested target with explicit-import dispatch
tests, `legacy_unregistered` drops to <=5, or any old/new import compatibility
or safety invariant regresses.

## 2026-07-02 - Event Alpha refactor blocker burn-down accepted with doctor-plugin follow-up
**Status:** accepted
**Decision:** The current refactor continuation is accepted for the
compatibility baseline: `scanner.py` is below the interim 8k gate, the
top-level artifact doctor is an active compatibility shim, the migrated module
batch is active-shim guarded, safe pytest is the default CI/test mode, namespace
unknowns are classified, and export timestamp hardening is in place. Provider
activation work may continue behind the existing research-only behavior freeze.
The final refactor report remains `blocked` only for the documented
doctor-plugin target because `legacy_unregistered=15` still exceeds the
requested <=5 threshold.
**Why:** Verification passed across standalone tests, safe pytest, compileall,
Event Alpha shim/report/namespace/integrated/provider/Coinalyze/source-coverage/
daily-brief/notification/doctor/scheduled/unlock/derivatives/fade-review/
official-exchange/export smokes, and `make verify`. Current measured state:
`scanner.py` 7,744 lines, top-level `event_alpha_artifact_doctor.py` 19 lines,
package doctor implementation 6,363 lines, `tests/test_indicators.py` 1,771
lines, active shims 67, partial shims 0, unmigrated modules 58, unknown
namespaces 0, and active-shim logic violations 0.
**Revisit when:** the remaining 15 unregistered legacy doctor append sites are
migrated or a doctor strict/WARN counter regresses; future scanner extraction
changes CLI defaults, Make targets, provider guardrails, or research-only
side-effect gates; or a shim is retired.

## 2026-07-02 - Event Alpha refactor v1 accepted
**Status:** accepted
**Decision:** Event Alpha refactor v1 is accepted for resuming provider
activation work. The compatibility-first package split, schema-first doctor,
namespace lifecycle, shim registry, pytest-compatible test split, and safe CI
workflow configuration are now the baseline architecture contract.
**Why:** The post-refactor release-candidate gauntlet passed all critical local
checks: standalone runner, full pytest, compileall, `make test-pytest`, Event
Alpha integrated radar/outcome/readiness/provider/scheduled/unlock/derivatives/
fade-review/source-coverage/daily-brief/notify-preview/strict-doctor/namespace
lifecycle smokes, and `make verify`. Doctor schema validation covered 328 row
checks with zero schema errors, the doctor registry remained stable at 53
registered checks and 15 legacy-unregistered checks, active shim logic
violations are zero, and safety invariants remained no-live/no-send/no-trading/
no-paper/no-RSI/no-Event-Alpha-created-TRIGGERED_FADE. Prior GitHub Actions
runs exposed Python 3.11 f-string parsing and fixed-clock test-isolation
failures; this RC includes both compatibility fixes, `/usr/bin/python3`
compileall now passes, and the full gauntlet passes with the workflow fixed
research clock set.
**Revisit when:** a critical smoke/doctor/verify command regresses, GitHub
Actions exposes a new incompatibility on the RC commit, an old import shim is
removed, or provider activation work needs to change the schema/doctor/namespace
contract.

## 2026-07-02 - Active Event Alpha shims are compatibility-only
**Status:** accepted
**Decision:** Old top-level Event Alpha modules that have migrated package homes
must be tracked by `crypto_rsi_scanner.event_alpha.shims` and marked as
`active_shim`, `partial_shim`, or `not_migrated`. `active_shim` modules may only
contain docstrings, imports, `globals().update(...)`, `__all__`, comments, and
minimal compatibility glue; new implementation logic belongs in the new package
path. `partial_shim` is reserved for explicit migration bridges; the artifact
doctor bridge has now been promoted to `active_shim` after moving the real
implementation into `crypto_rsi_scanner.event_alpha.doctor.artifact_doctor`.
`make event-alpha-shim-report` writes the audit artifacts, and artifact doctor
warns if active shims accumulate logic.
**Why:** Compatibility wrappers keep old import paths stable during the v1
migration, but leaving them unguarded would let new behavior drift back into the
old top-level sprawl.
**Revisit when:** v1 compatibility shims are retired through an explicit
breaking migration, or a module is promoted from `partial_shim` to `active_shim`
after its implementation is fully moved.

## 2026-07-02 - Event Alpha v1 architecture rules prevent renewed sprawl
**Status:** accepted
**Decision:** Event Alpha v1 uses the package map documented in
`research/EVENT_ALPHA_ARCHITECTURE_V1.md`: providers, radar, artifacts,
notifications, outcomes, doctor, namespace, and CLI command modules each own
their respective implementation surfaces. Old top-level import modules remain
compatibility shims during v1 migration, but new implementation logic should go
to the new package paths. CLI parser/dispatch changes belong under `cli/`,
new tests belong in `tests/event_alpha`, `tests/rsi`, or `tests/cli`, new
artifact fields require schema v1 updates, new doctor checks require
check-registry schema dependencies, and every new namespace requires lifecycle
status, retention, and explicit `safe_for_send_readiness`.
**Why:** Event Alpha has enough providers, artifacts, doctor checks,
notifications, outcomes, and CLI paths that undocumented placement choices
would recreate the old monolith/sprawl. The package map plus schema-first and
namespace-lifecycle rules keep future refactors behavior-preserving and
research-only.
**Revisit when:** v1 shims are intentionally retired through an explicit
compatibility-breaking migration with old/new import audits, CLI snapshots,
schema migration notes, doctor registry updates, and full verification.

## 2026-07-02 - Event Alpha consolidation is compatibility-first
**Status:** accepted
**Decision:** Event Alpha moves toward `crypto_rsi_scanner/event_alpha/` and
`crypto_rsi_scanner/cli/` through wrappers, schema declarations, and focused
tests before any broad physical module moves. Old import paths and commands
remain supported until a later tested migration explicitly removes a shim.
Artifact doctor checks that depend on fields must reference schema v1, and
namespace lifecycle status must be explicit before a namespace is used for
send-readiness, burn-in, or calibration.
**Why:** Event Alpha has many mature provider, radar, notification, outcome,
and doctor paths. A big-bang move would risk behavior drift in research-only
safety gates, while wrappers and schema-first validation give future moves a
stable map.
**Revisit when:** The high-traffic Event Alpha modules have been migrated in
small slices with old/new import tests, CLI snapshot tests, schema validation,
and unchanged smoke/doctor results.

## 2026-07-02 - Radar performance learning is recommendation-only
**Status:** accepted
**Decision:** Cross-run Event Alpha radar performance artifacts may summarize
provider, source-pack, lane, market-state, crowding, and source-strength
research outcomes and may write prior/threshold suggestions, but every
suggestion must be recommendation-only with `auto_apply=false`, low-sample
warnings, and no automatic threshold mutation.
**Why:** Cross-run no-send rehearsal outcomes are useful for learning which
providers and lanes deserve attention, but small samples and fixture/live-cache
mixing make automatic tuning unsafe.
**Revisit when:** A human-reviewed, larger cross-run sample has enough mature
rows per provider/lane and a separate explicit threshold-change workflow is
approved.

## 2026-07-02 - DEX/on-chain and protocol fundamentals activation is fixture-first
**Status:** accepted
**Decision:** GeckoTerminal, CoinGecko DEX, and DefiLlama TVL/fees/revenue
activation starts with fixture/parser readiness artifacts only. The scaffold may
write DEX pool state, DEX anomaly, and protocol fundamentals rows for integrated
radar research, but `live_call_allowed` remains false by default and no live
fetcher is claimed until a bounded provider-specific request path, request
ledger, and explicit operator approval exist. Low-liquidity DEX pumps are
diagnostic, protocol metrics require source/time provenance, and protocol
fundamentals may support early/confirmed research only with market/liquidity
sanity.
**Why:** DEX-native moves and protocol fundamentals can explain catalysts that
centralized exchange/news feeds miss, but pool-liquidity manipulation and stale
fundamental metrics are high false-positive risks.
**Revisit when:** A specific DEX/protocol provider has a reviewed bounded
no-send live rehearsal with redacted request ledger rows, freshness checks, and
human approval for a live preflight flag.

## 2026-07-02 - Structured unlock/calendar activation is fixture-first
**Status:** accepted
**Decision:** Tokenomist, Messari unlocks, and CoinMarketCal activation starts
with fixture/parser preflight rows and provider-specific no-send stubs. Rows may
list required env var names, request-ledger paths, request budgets, supported
event types, source packs, and fixture status, but `live_call_allowed` remains
false by default and no live fetcher is claimed until a bounded provider-specific
request path is implemented and explicitly enabled. Unlock promotion requires a
structured source, event time, and materiality fields such as circulating
percentage, USD size, ADV comparison, vesting category, cliff/linear distinction,
and timestamp confidence.
**Why:** Unlock/calendar feeds are useful source evidence, but missing event
time or size can turn ordinary calendar rows into misleading risk/fade
research. Fixture-first activation proves parser/readiness contracts without
network or credential risk.
**Revisit when:** A specific provider has a reviewed bounded live rehearsal with
redacted request ledger rows, no-send artifacts, and human approval to enable an
explicit live preflight flag.

## 2026-07-02 - Market anomalies are catalyst-search queue inputs until sourced
**Status:** accepted
**Decision:** Broad market anomaly scanning may rank cached/fixture market rows,
attach canonical asset identity, bucket anomalies, and write catalyst-search
queue artifacts, but a market anomaly alone remains `UNCONFIRMED_RESEARCH`.
Official or structured source evidence plus a valid market anomaly can confirm
research rows; anomaly plus fresh Coinalyze crowding can support
`FADE_SHORT_REVIEW` only when the move is completed/exhausted. Low-liquidity
suspicious moves remain diagnostic/risk review and cannot be promoted to
confirmed long research. These artifacts must not create Telegram sends, trades,
paper trades, normal RSI rows, execution, or Event Alpha-created
`TRIGGERED_FADE`.
**Why:** Market-first scanning is useful for finding unknown catalysts, but
price/volume alone is not catalyst evidence and thin-liquidity spikes are too
fragile for operator opportunity lanes.
**Revisit when:** A reviewed broad-market live/cache sample shows reliable
source-confirmation coverage and a separate human-approved promotion path is
defined.

## 2026-07-02 - Event Alpha uses canonical asset identity as research metadata
**Status:** accepted
**Decision:** Event Alpha provider artifacts should resolve crypto/provider
identifiers through a canonical asset/instrument registry before cross-provider
merges. The resolver may attach `canonical_asset_id`, venue/instrument metadata,
confidence, and warnings to research artifacts, but it must not create alerts,
sends, trades, paper trades, normal RSI rows, execution, or Event Alpha-created
`TRIGGERED_FADE`. Quote assets such as USDT/USDC/FDUSD are diagnostics unless
explicitly targeted, SECTOR/theme rows are non-tradable diagnostics, BTC/ETH
simple pair announcements are capped unless materially new, and proxy assets
must be labeled proxy rather than direct beneficiaries.
**Why:** CryptoPanic tickers, CoinGecko IDs, official exchange pairs, Coinalyze
futures symbols, future DEX contracts, calendar symbols, and theme rows need a
shared identity layer so integrated radar does not merge by fragile provider
strings or promote non-opportunity assets by accident.
**Revisit when:** contract-address/DEX pool resolution is added for live DEX
artifacts or when a reviewed operator workflow explicitly targets quote/base
assets as first-class research subjects.

## 2026-07-02 - Official exchange activation uses provider-specific modes under one schema
**Status:** accepted
**Decision:** Official exchange activation artifacts use one shared schema with
separate provider rows for `bybit_announcements_public`,
`binance_announcements_public_or_fixture`, and
`binance_announcements_signed_listener`. Bybit public and Binance
public/fixture rows may be fixture/parser-ready without API keys; the Binance
signed listener remains blocked unless explicit live-listener env vars are
configured and reviewed. Any live-call-allowed row requires a request ledger,
and activation artifacts must not claim sends, trades, paper trades, normal RSI
rows, or Event Alpha `TRIGGERED_FADE`.
**Why:** Bybit and Binance official announcement paths share downstream source
packs and artifact doctor checks, but their credential and request models
differ. One activation schema avoids drift while keeping public/fixture parsing
distinct from the signed listener.
**Revisit when:** Binance has a reviewed bounded signed-listener no-send
rehearsal with redacted ledger/artifacts and human approval to promote it beyond
blocked readiness.

## 2026-07-02 - Coinalyze live rehearsal is bounded no-send only
**Status:** accepted
**Decision:** Coinalyze may run a live-capable no-send rehearsal only inside a
clean activation namespace and only when a key is configured, an explicit
operator allow flag is set, no-send mode is preserved, the request ledger is
writable, and a tiny request budget is enforced. Missing key reports
`missing_config`; key without allow reports `live_call_blocked_by_default`.
Successful rehearsals must write redacted request-ledger rows plus local
derivatives state/candidate artifacts and provider-health telemetry. Stale
namespaces must block preflight or rehearsal writes unless the operator sets an
explicit stale-namespace override.
**Why:** A bounded live data check is useful for parser, quota, and provider
health validation, but it must not turn into notification routing or trading by
accident.
**Revisit when:** A reviewed no-send Coinalyze sample has stable quota behavior,
source coverage, and useful operator rows, and the human approves promotion to a
regular research profile.

## 2026-07-02 - Coinalyze activation starts with a no-call preflight
**Status:** accepted
**Decision:** Coinalyze derivatives/OI/funding activation must start with a
provider-specific no-call preflight artifact. The preflight may report whether
`RSI_EVENT_DISCOVERY_COINALYZE_API_KEY` is configured, parser/mapping readiness,
provider-health key, request-ledger path, timeout/cache/budget policy,
supported metrics, and the research lanes/source packs enabled if healthy. It
must not print API key values, call Coinalyze, send Telegram messages, write
normal RSI rows, trade, paper trade, execute orders, or create
`TRIGGERED_FADE`. A no-send rehearsal remains blocked by default even when a key
exists unless a future explicitly bounded live-preflight flag is supplied.
**Why:** Derivatives evidence is high-value but quota- and side-effect-sensitive.
Operators need a repeatable way to prove local configuration and fixture parser
readiness before any live provider request is considered.
**Revisit when:** Coinalyze has a reviewed bounded request ledger, quota policy,
provider-health integration, no-send burn-in output, and human approval for a
specific live rehearsal.

## 2026-07-02 - Stale Event Alpha namespaces are explicit markers, not silent failures
**Status:** accepted
**Decision:** Superseded Event Alpha artifact namespaces may be marked with an
`event_alpha_namespace_status.json` stale marker that records the namespace,
reason, timestamp, and replacement namespace. Artifact doctor should
short-circuit stale namespaces by default and report the marker instead of
blocking on known legacy rows. Operators must opt into legacy inspection with
`--event-alpha-include-stale-artifacts`; prune/archive commands are dry-run
plans unless a future explicit destructive workflow is approved.
**Why:** Old `notify_llm_deep` artifacts can preserve pre-policy routes,
preview wording, or delivery rows that should not be used for current
send-readiness. An explicit marker preserves auditability while preventing stale
data from masquerading as current blockers.
**Revisit when:** Namespace retention moves to a managed artifact database with
typed lifecycle states and reviewed archive/delete controls.

## 2026-07-01 - Live-provider activation readiness is no-call and no-send by default
**Status:** accepted
**Decision:** Event Alpha live-provider activation readiness artifacts may
inspect configuration, provider health, request-ledger paths, source-pack
coverage, quota policy, and required environment variable names, but they must
not call live providers, send Telegram messages, write normal RSI signal rows,
trade, paper trade, execute orders, print secret values, or claim Telegram send
readiness. Source coverage and daily briefs may link these readiness artifacts
and recommend an activation order, but enabling any provider still requires an
explicit guarded profile/config change and a no-send rehearsal.
**Why:** The next useful operational step is knowing which high-value providers
are safe to turn on and what credentials/quotas are missing, without letting a
readiness report silently become a live data or notification path.
**Revisit when:** A specific provider has a reviewed no-send burn-in sample,
bounded request ledger, quota policy, source-pack tests, and explicit human
approval to promote it into a live-style research profile.

## 2026-07-01 - Integrated radar preview and outcome artifacts are research truth only
**Status:** accepted
**Decision:** Integrated Event Alpha radar operator output should use portable
artifact-relative paths in rendered Markdown and a structured
`event_integrated_radar_notification_deliveries.jsonl` ledger as the preview
delivery source of truth. Integrated radar outcomes and calibration priors may
be written as local research artifacts, but they are recommendation-only and
must not mutate thresholds, alert tiers, normal RSI signal rows, paper/live
state, Telegram sends, execution, or `TRIGGERED_FADE`.
**Why:** Pro-model review and operator audits need portable, reproducible
artifacts that explain what would have rendered, why items were skipped, and
how fixture outcomes cohort by lane/source without relying on machine-specific
paths or live side effects.
**Revisit when:** Integrated radar has a reviewed live burn-in sample large
enough to justify a human-approved promotion from local research artifacts to a
separate notification or paper-tracking workflow.

## 2026-07-01 - Canonical integrated lane truth wins operator presentation
**Status:** accepted
**Decision:** For integrated Event Alpha radar artifacts, canonical integrated
candidate/CoreOpportunity fields are the source of truth for research cards,
card indexes, daily briefs, and artifact-doctor validation. Generic recomputed
market-reaction or score-component fallback may fill missing fields only; it
must not upgrade or rewrite a canonical lane, why-now explanation, market
state, derivatives crowding/fade metadata, source URL, warning, or reason code.
Lane-first card groups are authoritative for integrated radar cards.
**Why:** Operator output must not tell a different story from the canonical
row. In particular, simple BTC/ETH/stable major-pair announcements stay
unconfirmed/diagnostic by default, and fade/confirmed research rows must show
their actual market/derivatives context rather than generic `n/a` or
source-only fallback text.
**Revisit when:** Integrated radar moves to a typed artifact schema that can
enforce canonical presentation fields at serialization time.

## 2026-07-01 - Integrated Event Alpha radar cycle is an artifact orchestrator
**Status:** accepted
**Decision:** Event Alpha may run an integrated research cycle that collects
configured sidecar artifacts, merges market anomalies, official exchange
events, scheduled/unlock catalysts, and derivatives/fade-review evidence into
canonical integrated candidates and CoreOpportunity rows, then writes cards,
source coverage, daily brief, run ledger, and a no-send notification preview.
The integrated cycle must remain artifact-only and research-only: no normal RSI
signal rows, paper trades, live trades, execution, Telegram sends in tests, or
Event Alpha-created `TRIGGERED_FADE`. Integrated candidate truth is
authoritative at rest: the canonical CoreOpportunity/card/report layer must not
silently upgrade lanes or drop source URLs, reason codes, official exchange
events, scheduled catalyst/unlock evidence, derivatives evidence, market-state
snapshots, route/state fields, or requirement flags. Diagnostic rows may be
stored and shown in diagnostics appendices, but they should not create visible
operator opportunities unless a later deterministic quality gate explicitly
promotes them.
**Why:** Operators need one coherent radar view instead of separate sidecar
reports, but the sidecar evidence types are still validation inputs rather than
trade decisions. Strict artifact-doctor checks must enforce lane/source/market
requirements and keep price-only, source-only, CryptoPanic-only, and simple
major-pair rows out of confirmed lanes.
**Revisit when:** A reviewed validation sample proves a specific integrated
lane should be promoted beyond local/no-send research artifacts and the human
approves that promotion explicitly.

## 2026-07-01 - Event Alpha market-state returns use explicit units
**Status:** accepted
**Decision:** Raw/latest market snapshots use fractional returns by default
(`0.012` means `+1.2%`). Persisted Event Alpha market-state snapshots use
percentage points with explicit `return_unit=percent_points`,
`source_return_unit`, and unit warnings when needed. Reports and research cards
must format returns with `%` signs, and artifact doctor should block obvious
double-scaled market-state snapshots relative to the raw/latest source. Raw
source-pack evidence acquisition rows must not retain promoted final levels when
no evidence was accepted and acquisition was skipped, rejected, or unresolved.
Official exchange simple BTC/ETH/stable pair additions are capped to
unconfirmed/diagnostic by default unless explicitly enabled.
**Why:** Mixed fractional and percentage-point values made CHZ/VELVET cards
show impossible 1h/4h moves and could corrupt market-state classification,
opportunity lanes, and fade-review diagnostics. Stale acquisition and simple
major-pair artifacts can likewise make non-confirming evidence look promoted.
**Revisit when:** Event Alpha market and evidence artifacts move to a typed
schema that enforces units/final fields at serialization boundaries.

## 2026-07-01 - Derivatives crowding is fade-review evidence, not a trigger
**Status:** accepted
**Decision:** Event Alpha may normalize derivatives crowding evidence such as
open-interest change, funding, liquidation imbalance, long/short ratio, basis,
and perp/spot volume into profile-scoped research artifacts, daily-brief
sections, cards, notification copy, run ledgers, and artifact-doctor checks.
`FADE_SHORT_REVIEW` rows are manual research review metadata only. They must
not create Telegram sends, normal RSI signal rows, paper trades, live trades,
execution, or Event Alpha-created `TRIGGERED_FADE`; only deterministic
`event_fade.py` plus `proxy_fade` can produce a fade trigger.
**Why:** Derivatives crowding is useful for spotting post-move exhaustion and
risk, but it is not source evidence for a catalyst and is not enough to justify
an automated short signal.
**Revisit when:** A reviewed validation sample proves a derivatives-crowding
fade-review lane has reliable edge and the human approves a separate
notification or paper-tracking promotion.

## 2026-07-01 - Scheduled catalyst and unlock rows are research artifacts only
**Status:** accepted
**Decision:** Event Alpha may normalize scheduled project events and
Tokenomist-style unlocks into profile-scoped research artifacts, daily-brief
sections, source-coverage rows, cards, audits, and artifact-doctor checks. These
rows must not create Telegram sends, normal RSI signal rows, paper trades, live
trades, execution, or Event Alpha-created `TRIGGERED_FADE`. Unlock/supply
strict lanes require structured/official/supply evidence, known event time,
source URL, and materiality; media-only CryptoPanic/RSS/GDELT text that merely
mentions an unlock is context only and cannot satisfy structured unlock proof.
**Why:** Scheduled catalysts and supply events are useful for early research
and risk review, but false unlock proof from broad media would make the radar
look more certain than the evidence supports.
**Revisit when:** A reviewed validation sample proves a scheduled/unlock lane
deserves notification or paper-tracking promotion and the human approves a
separate promotion path.

## 2026-07-01 - Official exchange announcements are first-class research evidence only
**Status:** accepted
**Decision:** Event Alpha may normalize official exchange announcements into
profile-scoped research artifacts and use explicit official source packs for
listing, perp-listing, and exchange-risk evidence. These rows can support local
reports, source coverage, cards, audits, and artifact-doctor checks, but they
must not create Telegram sends, normal RSI signal rows, paper trades, live
trades, execution, or Event Alpha-created `TRIGGERED_FADE`.
**Why:** Official exchange announcements are high-quality identity/catalyst
evidence for listing and tradability events, but promotion still requires the
deterministic Event Alpha quality/router gates and market/source confirmation
rules.
**Revisit when:** A reviewed validation sample proves an official-exchange
event lane should move beyond research artifacts, and the human approves a
separate notification or paper-tracking promotion.

## 2026-07-01 - Market anomaly artifacts are catalyst-search seeds only
**Status:** accepted
**Decision:** Event Alpha may write profile-scoped market-state snapshots and
broad market anomaly rows for abnormal price/volume/liquidity behavior. These
rows can seed catalyst search, daily-brief diagnostics, source-pack follow-up,
and artifact-doctor checks, but they must not create alert snapshots, Telegram
sends, normal RSI signal rows, paper trades, live trades, or
Event Alpha-created `TRIGGERED_FADE`.
**Why:** Market anomalies are useful for recall and for finding missed
catalysts, but price/volume movement alone is not evidence of an actionable
research alert. Keeping anomaly rows as search seeds prevents the radar from
turning “coin moved” into a false alert lane.
**Revisit when:** A reviewed sample proves a specific anomaly class has
reliable catalyst-confirmation behavior and the human approves a separate
promotion path.

## 2026-07-01 - Event Alpha opportunity lanes are research metadata only
**Status:** accepted
**Decision:** Event Alpha may classify canonical CoreOpportunity rows into
research opportunity lanes (`EARLY_LONG_RESEARCH`,
`CONFIRMED_LONG_RESEARCH`, `FADE_SHORT_REVIEW`, `RISK_ONLY`,
`UNCONFIRMED_RESEARCH`, and `DIAGNOSTIC`) using a pure market-reaction snapshot
and source-pack requirements. Weak/missing-confirmation rows should become
`UNCONFIRMED_RESEARCH`, and sector/control/source-noise rows should become
`DIAGNOSTIC`; `RISK_ONLY` is reserved for credible negative/risk catalysts such
as exploits, delistings, structured unlock/supply risk, legal/regulatory shock,
chain halt, bridge compromise, or severe liquidity risk. These lanes can improve
cards, previews, doctor checks, and review artifacts, but they cannot write
normal RSI signal rows, paper trades, live trades, or create `TRIGGERED_FADE`.
`FADE_SHORT_REVIEW` is not a trigger; only `event_fade.py` plus `proxy_fade` can
produce a fade trigger. CryptoPanic-only narratives are not sufficient for
early or confirmed lanes unless separate official/structured evidence or
deterministic market/source requirements explicitly validate the row.
**Why:** The radar needs to distinguish early catalyst research, confirmed
market reaction, crowded fade review, and risk-only rows without turning source
evidence or market movement into automated trading authority.
**Revisit when:** A reviewed validation sample proves a specific lane has
positive edge and the human explicitly approves a separate notification or
paper-tracking promotion.

## 2026-07-01 - CoreOpportunity final fields are post-policy truth
**Status:** accepted
**Decision:** Raw `event_core_opportunities.jsonl` rows must persist final
opportunity level, route, state, score, and live-confirmation fields after all
live-confirmation and quality-policy caps have been applied. If a pre-policy or
support-row value is useful for audit, it must live in an explicitly named
requested/pre-policy/raw-support field. `SUPPRESS_DUPLICATE` is not allowed to
mask an invalid `final_opportunity_level`.
**Why:** Operator views, artifact doctor, notification readiness, and Pro-model
review zips all inspect raw artifacts. A raw row that says
`final_opportunity_level=validated_digest` while the canonical rendered view is
exploratory makes the artifact set internally contradictory and can make
source-only narrative evidence look alertable.
**Revisit when:** CoreOpportunity artifacts move to a typed versioned schema
with separate immutable requested/verdict/final sections and all readers are
schema-aware.

## 2026-07-01 - CryptoPanic success reconciles stale backoff and narrative digest stays strict
**Status:** accepted
**Decision:** A successful same-day CryptoPanic Growth request is operational
evidence that the provider is usable for the inspected namespace, even if an
older profile-scoped provider-health row still says `provider_backoff`. Source
coverage should report `observed_healthy` or `observed_partial_success`, keep a
backoff-reconciled flag for audit, and avoid telling the operator to configure,
restore, or verify the token after successful requests were observed. Live-style
narrative source packs such as fan/sports, proxy/pre-IPO RWA, and political meme
packs still need stronger daily-digest confirmation than a single source-only
row: official/structured evidence, multiple accepted evidence rows, matching
CryptoPanic tag evidence plus market confirmation, or an explicit operator opt-in
via `RSI_EVENT_ALPHA_ALLOW_SOURCE_ONLY_NARRATIVE_DIGEST=1`. Narrative/proxy
semantics from supporting categories, impact paths, roles, and source/incident
text override stale lower-level source-pack labels, so a fan/proxy row cannot
escape as a direct unlock/listing-style digest just because a support row is
mispacked. Operator-facing research-card indexes, evidence-acquisition summaries,
and artifact-doctor card checks should use the normalized canonical
CoreOpportunity verdict and source-coverage JSON rather than stale lower-level
support-row metadata.
**Why:** The first successful Growth Weekly rehearsal proved CryptoPanic was
working, but stale backoff diagnostics and source-only narrative digest rows made
operator-facing artifacts look both broken and too permissive.
**Revisit when:** Burn-in labels show that a specific single-source narrative
class is useful enough to promote without market, official, structured, or
multi-source confirmation.

## 2026-06-30 - CryptoPanic live diagnostics must be body-aware and redacted
**Status:** accepted
**Decision:** CryptoPanic live fetches must read response bodies while the HTTP
response is open, decode them safely, and classify empty, malformed JSON, auth,
rate-limit/forbidden, server, network, provider-backoff, and quota-exhausted
failures without leaking `auth_token` values. Request ledger rows should keep
redacted URLs plus content type, redacted body excerpt, parse error, response
byte count, quota-counted flag, and provider-health effect. Source coverage and
artifact doctor must distinguish missing configuration from configured-but-
unusable parse/rate-limit/backoff states.
**Why:** A configured provider that returns HTML, an empty body, or a 403 is a
different operator problem from a missing token. Without body-aware diagnostics
the system can look silently unconfigured or unusable while hiding the actual
repair path.
**Revisit when:** CryptoPanic moves to a typed SDK/client layer that exposes
the same diagnostics without direct urllib response handling.

## 2026-06-30 - Research-review Telegram copy uses canonical core identity
**Status:** accepted
**Decision:** When a research-review digest item resolves to a canonical
CoreOpportunity, Telegram copy must show the canonical card basename and
`agg:...` feedback target, while lower-level hypothesis/watchlist ids remain
artifact metadata only. Artifact doctor strict mode must block fresh
research-review delivery rows whose preview body points at stale hypothesis
cards/feedback targets when canonical core identity is available.
**Why:** Research-review digests are the operator feedback loop. Showing
support-row or hypothesis targets for a canonical opportunity makes feedback
hard to apply and can make duplicated support rows look like separate review
items.
**Revisit when:** Notification bodies are generated directly from typed
CoreOpportunity card objects and no longer accept lower-level route decisions.

## 2026-06-30 - Event Alpha daily digest requires confirmation and grouping
**Status:** accepted
**Decision:** Live-style Event Alpha daily digest lanes must contain grouped,
confirmed core opportunities only. A daily digest item needs accepted
source-pack evidence, official/structured evidence, matching CryptoPanic
token+catalyst proof, or fresh market confirmation with a non-generic impact
path. Unconfirmed/not-executed/no-market candidates, sector-only rows, generic
cooccurrence, broad strategic/macro context without token proof, and duplicate
support rows must stay in research-review, near-miss, local-only, or diagnostic
artifacts. Multi-item delivery rows must use structured identity arrays while
retaining scalar compatibility fields.
**Why:** The first Growth Weekly rehearsal proved CryptoPanic evidence works,
but it also showed that unconfirmed support rows can make daily digest output
too noisy and artifact identities fragile.
**Revisit when:** Reviewed burn-in labels show that a specific lower-confidence
class should be promoted into daily digest with a deterministic source/market
proof rule.

## 2026-06-30 - CryptoPanic Growth Weekly uses a conservative request contract
**Status:** accepted
**Decision:** CryptoPanic live Event Alpha access defaults to the Growth Weekly
API contract: `https://cryptopanic.com/api/growth_weekly/v2/posts/` with
`auth_token` plus only Growth-supported query parameters (`public` or
`following`, `currencies`, `regions`, `filter`, `kind`, and `page`). The
canonical token env var is `RSI_EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN`; legacy
aliases are accepted for operator convenience. Growth profiles must not send
`search`, `size`, `last_pull`, `with_content`, `panic_period`, or
`panic_sort`. Requests are quota-ledgered with redacted URLs and bounded by
weekly, per-run, daily-soft, page, currency-batch, and minimum-interval limits.
CryptoPanic currency planning is ticker-only: CoinGecko slugs, `SECTOR`, empty
currency requests, lowercase/raw terms, and unvalidated common-word collisions
must be rejected before live request construction. Repeated normalized request
keys within a run must be deduped/cached. Artifact doctor blocks unredacted
tokens, Growth-unsupported params, invalid or duplicate currency requests,
quota overruns, and rejected-only promoted CryptoPanic evidence.
**Why:** The user’s current subscription is a 600-request/week Growth Weekly
plan. The previous integration could hit the wrong endpoint or unsupported
params, causing 403s and stale backoff while burning operator trust.
**Revisit when:** The user explicitly upgrades to an Enterprise plan and wants
Enterprise-only fields such as search to participate in research evidence
collection.

## 2026-06-30 - CryptoPanic live proof remains no-send and redacted
**Status:** accepted
**Decision:** CryptoPanic operational checks must use a redacted preflight and
no-send rehearsal path before any notification promotion. The preflight may
report whether the token is configured, provider health/backoff status, source
packs that depend on CryptoPanic, and a targeted `SERVICE=cryptopanic`
provider-health reset command, but it must not print the token. The
`notify_llm_deep_cryptopanic_rehearsal` target runs with Telegram sends
guarded off and records CryptoPanic configured/attempted/result/accepted/
rejected/status/skip counters in the run ledger.
**Why:** CryptoPanic is useful high-specificity evidence only when token-tagged
and catalyst-specific, but it uses a secret token and can fail/backoff like any
live provider. Operators and Pro-model reviews need proof that it was exercised
without risking a secret leak or accidental send.
**Revisit when:** CryptoPanic evidence is promoted into a scheduled live-send
profile with reviewed burn-in metrics and a separate human-approved send plan.

## 2026-06-30 - Daily brief selection is artifact-namespace authoritative
**Status:** accepted
**Decision:** Event Alpha operator reports must treat an explicit
`ARTIFACT_NAMESPACE` as the artifact scope even when the runtime `PROFILE`
differs. Smoke/test namespaces must pass `--event-alpha-include-test-artifacts`
based on either profile or namespace, and strict artifact doctor must block
fresh daily briefs that miss the selected run, mismatch selected
profile/namespace, show a canonical core count inconsistent with the current
core store, omit an expected research-review lane, or fail to link an existing
source coverage report.
**Why:** Research-review rehearsals commonly use a production-like runtime
profile such as `notify_llm_deep` with a smoke namespace. Filtering only by
profile can silently hide valid test-mode run/core rows and produce a brief
that says there are zero opportunities while cards and delivery artifacts
exist.
**Revisit when:** Event Alpha artifact selection moves to a typed run-index
store that records an explicit immutable selected run id for every generated
operator report.

## 2026-06-30 - Unobserved providers are not healthy source coverage
**Status:** accepted
**Decision:** Event Alpha source coverage must distinguish runtime profile from
artifact namespace and must persist source-coverage reports under the inspected
namespace. A configured source provider with no provider-health observation is
`unknown/not observed`, not healthy, and evidence absence from that pack is not
meaningful unless a high-specificity healthy provider actually observed the
source path. Artifact doctor may warn on missing source-coverage reports or
unknown provider coverage and must block impossible contradictions where the
same provider is both healthy and unobserved.
**Why:** Live and no-send research-review runs can otherwise overstate source
coverage and make missing evidence look like a reliable negative signal.
Separating profile and namespace also prevents operator reports from inspecting
the wrong artifact directory.
**Revisit when:** Provider-health storage moves to a typed schema with explicit
per-role observation records and source-pack coverage SLAs.

## 2026-06-30 - CryptoPanic and exchange evidence require asset-specific proof
**Status:** accepted
**Decision:** CryptoPanic rows may serve as stronger Event Alpha source-pack
evidence only when their currency tags match the validated symbol or coin id
and the article text supports the catalyst/impact path. Narrative heat,
sentiment, hot/bullish flags, or unrelated tags are not confirmation. Official
exchange announcements may validate listing/perp/direct exchange-event
evidence only when parsed symbol, pair, or contract metadata matches the
candidate identity; an official exchange domain alone is not enough. Both
families remain research-only evidence sources and cannot bypass market,
derivatives, quality, or event-fade gates.
**Why:** These sources are high-value but easy to misuse. Token tags and
exchange metadata provide auditable identity proof; generic source authority or
sentiment does not.
**Revisit when:** Reviewed live burn-in data shows a separate deterministic
rule is needed for untagged CryptoPanic posts or exchange product events that
do not expose normalized symbol/pair metadata.

## 2026-06-30 - Feedback rows expose top-level calibration dimensions
**Status:** accepted
**Decision:** Event Alpha feedback rows are calibration artifacts and must carry
the dimensions needed for grouping and eval-case export as top-level fields:
core opportunity id, card path, run/profile/namespace, incident/hypothesis
identity, symbol/coin id, impact path, candidate role, opportunity level, final
route, evidence specificity, source class/domain/pack, market confirmation,
market freshness, and catalyst-frame status where available. Nested source or
score metadata remains useful audit context, but calibration reports and
feedback-to-eval exports should not depend on nested-only fields.
**Why:** Useful/junk/watch labels only become learnable if they preserve the
operator-facing source, quality, market, and route dimensions in a stable shape
across alert, card, watchlist, and core-opportunity targets.
**Revisit when:** Feedback storage moves to a typed database schema with an
explicit migration path for historical JSONL artifacts.

## 2026-06-30 - LLM analyst tools are advisory planning surfaces
**Status:** accepted
**Decision:** Event Alpha may use LLM-backed or fixture-backed analyst tools
for source triage, evidence query planning, denial/correction planning, manual
verification checklists, and concise analyst summaries. These outputs must be
quote-checked where they cite evidence and constrained by deterministic source
triage, source-pack contracts, asset identity validation, opportunity quality
gates, and live confirmation policy. They may explain or prioritize what to
verify next, but they cannot decide final route/state, send Telegram, paper
trade, live trade, write normal RSI rows, bypass source-pack gates, or create
`TRIGGERED_FADE`.
**Why:** LLMs are useful for reducing operator workload around messy source
quality and follow-up planning, but letting them act as final promotion logic
would weaken the research-only safety model and make artifacts harder to audit.
**Revisit when:** Reviewed burn-in data shows enough analyst-tool precision and
calibration to promote a specific advisory field into a deterministic rule.

## 2026-06-30 - Asset role validation is deterministic before promotion
**Status:** accepted
**Decision:** Event Alpha candidate promotion must validate the asset role
against deterministic asset knowledge before treating a token as the affected
asset, proxy instrument, proxy venue, infrastructure provider, ecosystem asset,
or broad macro context. Rows should persist asset kind, role capabilities,
identity confidence, identity evidence, role source, matched identity field,
collision risk, and role-validation failures/warnings where available.
Taxonomy candidates, LLM suggestions, source-context mentions, and common-word
tickers are proposals only until source text directly ties the asset identity
to the relevant mechanism. Broad macro assets such as BTC/ETH/SOL can remain
market context unless the source directly explains the asset-specific impact.
This validation may cap or demote candidates, but it cannot send Telegram,
paper trade, live trade, write normal RSI rows, bypass source-pack gates, or
create `TRIGGERED_FADE`.
**Why:** Source expansion makes false positives more likely: LINK can be a
taxonomy candidate in a THORChain exploit, HYPE can be a common word or a venue
token depending on context, and BTC can appear as broad market context without
being the actual affected asset.
**Revisit when:** The asset knowledge graph is replaced by a reviewed external
asset registry with audited entity/role mappings and false-positive metrics.

## 2026-06-30 - Article enrichment quality gates LLM source text
**Status:** accepted
**Decision:** Event Alpha source enrichment must persist auditable article
extraction metadata before downstream LLM extraction or catalyst-frame analysis
uses fetched article bodies. Enriched source rows should record extractor and
cleaner versions, fetched/final/canonical URLs, redirect chain, title/byline/
source/published metadata when available, body text, body length, boilerplate
ratio, ticker-sidebar detection, deterministic source triage, and an
`article_quality_status` such as `good`, `thin`, `boilerplate_heavy`,
`redirect_placeholder`, `paywall_or_blocked`, `fetch_failed`, or
`fixture_text_used`. Only good or fixture text can replace the raw source
summary in LLM packets; placeholders, blocked pages, boilerplate-heavy pages,
affiliate/SEO pages, market recaps, and context-only prediction-market pages
remain raw observations or diagnostics unless another strict source path
confirms them. Optional LLM source-quality judging is advisory and constrained
by deterministic triage; it cannot override hard deterministic quality caps.
**Why:** Bad fetched text, especially Google News placeholders, ticker sidebars,
and referral/SEO pages, can poison LLM extraction, catalyst frames, evidence
scoring, and operator notifications if treated as reliable article evidence.
**Revisit when:** The source-enrichment layer moves to a typed extraction
service with domain-specific cleaners and reviewed precision/recall metrics.

## 2026-06-30 - Derivatives, DEX liquidity, and protocol metrics are market evidence only
**Status:** accepted
**Decision:** Event Alpha may use Coinalyze-style derivatives snapshots,
GeckoTerminal-style DEX liquidity/pool-volume snapshots, and DefiLlama-style
protocol TVL/fees/volume snapshots as first-class market-confirmation evidence
with explicit freshness status. These signals may support playbook-specific
confirmation: listings/perps can use open-interest, funding, futures volume,
and liquidations; proxy-attention rows can use DEX liquidity sanity and DEX
volume; strategic/protocol/security rows can use TVL, fees, protocol volume, or
TVL outflow. Stale, missing, unknown, or provider-unavailable rows remain
coverage gaps and cannot validate the catalyst. These sources cannot prove
asset identity, official confirmation, impact-path validation, `TRIGGERED_FADE`,
Telegram sends, paper trades, normal RSI signal rows, or execution by
themselves.
**Why:** Price-only confirmation is too thin for Event Alpha. Derivatives,
liquidity, and protocol metrics make operator review more useful, but treating
them as catalyst proof would weaken strict source/identity/impact gates.
**Revisit when:** Reviewed live burn-in outcomes show reliable playbook-specific
thresholds for OI/funding, DEX liquidity, TVL/fees, or protocol-volume changes.

## 2026-06-30 - Structured calendar and unlock evidence has pack-specific proof obligations
**Status:** accepted
**Decision:** Event Alpha may treat CoinMarketCal-style structured calendar
events and Tokenomist-style structured unlock rows as first-class source-pack
evidence only when they preserve explicit token identity, event-time provenance,
source class/mission, source confidence, and playbook-specific structured
metadata. Structured calendar rows can prove dated project/direct-token catalyst
evidence when the event type is specific enough, such as mainnet launch or
protocol upgrade; low-authority calendar items such as generic AMAs stay
local/review-only unless other stronger evidence exists. Structured unlock rows
can prove supply/unlock evidence only when unlock size/materiality is known and
the unlock is not stale; small, missing-materiality, or stale unlock rows cannot
by themselves satisfy validated digest/watchlist/high-priority source-pack
requirements. These sources still route through deterministic resolver,
identity, catalyst-link, impact-path, source-quality, live-confirmation, router,
and `event_fade.py` gates, and cannot send Telegram, write normal RSI rows,
paper trade, live trade, or create `TRIGGERED_FADE`.
**Why:** Structured calendars and unlock feeds are higher authority than broad
news for dated catalysts and supply pressure, but over-promoting generic
calendar posts or unquantified unlocks would make live burn-in too noisy.
**Revisit when:** Reviewed outcomes show specific calendar categories or unlock
materiality thresholds need playbook-specific calibration.

## 2026-06-30 - CryptoPanic tags and exchange announcements are first-class evidence
**Status:** accepted
**Decision:** Event Alpha may treat matching CryptoPanic currency-tag evidence
and official exchange announcements as first-class source-pack evidence when
they pass deterministic identity, catalyst-link, impact-path, and source-quality
checks. CryptoPanic evidence must preserve currency tags and only gets the
`cryptopanic_currency_tag_match` reason when the tag matches the validated
symbol or coin; sentiment, hot, rising, important, or bullish context alone is
not confirmation. Official exchange announcements should preserve exchange,
normalized event kind, product type, symbol, pair/contract, announcement time,
and URL metadata for cards, audits, and daily briefs. These sources can support
validated digest/watchlist decisions only through existing source-pack and live
confirmation gates; they cannot create `TRIGGERED_FADE`, bypass resolver or
impact-path gates, send Telegram by themselves, write normal RSI rows, paper
trade, or imply execution.
**Why:** CryptoPanic token-tagged news and official Binance/Bybit-style listing
announcements are high-signal confirmation sources, but treating them as generic
news made cards and audits less useful and made tag-mismatched/hot-only rows too
ambiguous for operator review.
**Revisit when:** The source registry moves to typed provider events or a
reviewed burn-in sample proves that tag-matched CryptoPanic or official
exchange evidence needs playbook-specific weighting changes.

## 2026-06-29 - Source coverage reports diagnose gaps, not eligibility
**Status:** accepted
**Decision:** Event Alpha source coverage reports may combine provider
readiness, provider health, source-pack definitions, evidence-acquisition
outcomes, and canonical core rows to show which source pack or provider is
missing, degraded, budget-skipped, rejected-only, or otherwise not confirming.
Coverage diagnostics must separate source-pack status from provider role health:
one provider can be healthy for event intake while degraded for catalyst search,
and a pack can be `complete`, `partial`, `degraded`, `unavailable`, or
`not_configured` without changing eligibility by itself. Rows should carry
explicit gap reasons and list providers missing or degraded for confirmation so
operators know what to fix next. Degraded, unavailable, or not-configured
coverage means absence is a coverage gap, not negative proof; strict artifact
doctor may block fresh artifacts that mark such absence as meaningful without an
accepted alternative source.
These reports and daily-brief recommendations are operator diagnostics only.
They cannot validate a candidate, promote an opportunity, loosen live
confirmation requirements, create `TRIGGERED_FADE`, send Telegram, write normal
RSI rows, paper trade, or imply execution. Market/protocol metric sources such
as CoinGecko and DefiLlama may support market confirmation or source-pack
coverage vocabulary, but they do not by themselves prove catalyst impact-path
validation or official confirmation.
**Why:** Live burn-in needs to explain why useful-looking rows remain local or
near-miss, and which source would most improve the next run. That explanation
must not become an implicit bypass around strict source, identity, impact-path,
market, and route gates.
**Revisit when:** Source coverage moves from JSONL/report artifacts into a
typed provider job system with reviewed source-reliability priors and explicit
promotion rules.

## 2026-06-29 - Keep research-review notifications separate from alert lanes
**Status:** accepted
**Decision:** Event Alpha may send a separate `research_review_digest` lane for
operator review of near-miss/exploratory candidates during burn-in, but this
lane is not a strict alert lane and does not count as alertable. It must be
disabled by default for normal profiles unless explicitly enabled, carry its own
cooldown/dedupe state, and clearly label messages as research review only,
not alertable, missing confirmation, and not a trade signal. It may include
non-alertable exploratory/local rows only after identity, score, and hard-gate
filters pass; source-noise, ticker collisions, generic co-occurrence,
sector-only rows by default, diagnostics/support rows, and already alertable
rows must stay out. It cannot create `TRIGGERED_FADE`, loosen quality gates,
route normal RSI alerts, write paper/live rows, or imply execution. Real-profile
rehearsals must write run-ledger counters and delivery rows for the
`research_review_digest` lane when candidates are due; missing lane rows are an
artifact-health failure, not a reason to relax alert gates.
**Why:** Burn-in needs useful operator feedback even when strict routes have no
alertable decisions. Mixing near-misses into daily digest/high-priority lanes
would blur the meaning of alertable Event Alpha decisions.
**Revisit when:** A reviewed feedback/outcome sample proves the review lane is
too noisy or too restrictive, or when Event Alpha notification promotion rules
are redesigned around a new validated quality policy.

## 2026-06-30 - Ranked burn-in review queues are presentation-only
**Status:** accepted
**Decision:** Event Alpha burn-in inboxes may rank and group operator review
items across strict would-send, digest would-send, research-review near-miss,
upgrade, local-only learning, and diagnostic categories. This queue is a
display layer only: it must not mutate watchlist/core state, route decisions,
alert tiers, notification eligibility, feedback rows, quality gates, or event
fade eligibility. Source-noise, ticker-collision, support/control diagnostics,
and other low-value controls stay hidden by default in the compact queue and
must remain available only through explicit diagnostic/full review surfaces.
**Why:** Operators need a short phone-friendly queue during burn-in, but making
diagnostics prominent or letting queue order feed back into alerting would blur
strict alert semantics.
**Revisit when:** The feedback loop has enough useful/junk labels to justify a
new reviewed prioritization policy with explicit tests and promotion rules.

## 2026-06-29 - Real Event Alpha sends require ledger-backed rehearsal readiness
**Status:** accepted
**Decision:** Before enabling real Telegram delivery for `notify_llm_deep`, the
operator should first run the deterministic fixture final check
`make event-alpha-telegram-no-send-final-check-fast`. It must use the
`notify_llm_deep_fixture_rehearsal` namespace, avoid live providers, avoid
Telegram sends, and prove canonical delivery identity with VELVET/AAVE would-send
fixture rows plus rejected weak controls. The fast target must not call
recursive Make; it should rebuild fixture artifacts directly, capture noisy
support-report output, and print the compact
`main.py --event-alpha-telegram-final-check` result only. The optional full
live-provider rehearsal remains separate under `notify_llm_deep_rehearsal`; it
may call live providers, take several minutes, and should pass
`make event-alpha-send-readiness PROFILE=notify_llm_deep_rehearsal` plus a
compact final check before real sends.
`make event-alpha-telegram-send-readiness-final PROFILE=<namespace>` and
`make event-alpha-telegram-final-send-checklist PROFILE=<namespace>` are
read-only trust targets for existing artifacts: they print the compact final
status, resolved preview path, strict doctor status, would-send lanes, core ids,
send count, provider summary, and next commands, then fail on `NOT_READY`.
The approved first real-send path is one cycle only:
`RSI_EVENT_ALERTS_ENABLED=1 CONFIRM=1 make event-alpha-telegram-send-one-cycle PROFILE=notify_llm_deep`.
That target must refuse before reaching the sender unless the send guard is
enabled, Telegram token/chat config is present, and either a fresh
`event-alpha-telegram-one-cycle-send-preflight` marker exists or `CONFIRM=1` is
passed. It must rerun the compact final check against the rehearsal namespace
immediately before sending and print the preview path plus the fact that it will
send Telegram messages. After any real one-cycle send, operators should run
`make event-alpha-telegram-post-send-audit PROFILE=notify_llm_deep`; if anything
looks wrong, pause with `make event-alpha-notification-pause PROFILE=notify_llm_deep REASON='...'`.
Notification heartbeat/no-digest previews must summarize the latest run ledger
and canonical core store rather than independent defaults, including completed
status, raw events, extraction rows, core opportunities, alertable final routes,
provider issues, LLM calls/skips, artifact-doctor status, and explicit
no-send/send-guard state. Strict artifact doctor blocks fresh previews whose
summary contradicts the latest run, lacks send-guard status, or uses unclear
no-send wording. Delivery rows must store a portable
`notification_preview_relpath` when a preview exists. Delivery rows for fresh
rehearsals/sends must also persist explicit `delivery_mode`, `delivery_state`,
`status_detail`, `send_guard_enabled`, `would_send`, `sent`, and `failed` fields
so no-send rehearsals, quality/cooldown blocks, provider failures, and successful
sends are machine-checkable without report-only inference. Send-readiness,
artifact doctor, inbox/audit-style consumers, and operator reports should resolve
previews by relpath first, namespace default path second, and legacy absolute path
only as a fallback; stale machine-specific `/Users/...` paths must not block
another checkout when the namespace preview exists. Namespaces with
pre-canonical delivery rows must warn operators not to use that namespace for
send-readiness and to rerun `notify_llm_deep_rehearsal` or the fixture final
check instead.
**Why:** A rehearsal that writes real artifacts but previews `Raw events=0`,
`Core opportunities=0`, or `Completed=no` makes a safe run look broken and can
hide stale artifacts. Explicit delivery status fields prevent ambiguous
blocked/would-send rows from being mistaken for real failures or successful
sends. Separate send-readiness and go/no-go gates give the operator one
deterministic final check and an explicit recommendation:
`READY_FOR_NO_SEND_REVIEW`, `READY_FOR_SEND`, or `NOT_READY`, before flipping
`RSI_EVENT_ALERTS_ENABLED=1`.
**Revisit when:** Event Alpha notifications move to a typed operational UI that
renders previews/readiness directly from a single delivery-run record.

## 2026-06-28 - Evidence acquisition failures are artifact status, not crashes
**Status:** accepted
**Decision:** Event Alpha evidence acquisition must return a complete
`EventEvidenceAcquisitionRunResult` for disabled, no-candidate, provider
unavailable/backoff, skipped-budget, failed-soft, and artifact-write-warning
paths. Live/no-send burn-in should record acquisition status and safe warnings
in run ledgers/reports, then continue writing review artifacts. Provider
failures or non-confirming statuses do not validate a candidate for digest or
send promotion.
**Why:** Live providers routinely 429, 403, timeout, or lack optional keys.
Those conditions are expected research coverage gaps, not reasons to crash the
cycle or silently promote weak rows.
**Revisit when:** Evidence acquisition moves into a typed job table with retry
state and operator-controlled provider retry workflows.

## 2026-06-28 - Telegram notifications use canonical core identity
**Status:** accepted
**Decision:** Event Alpha routed Telegram notifications must reconcile candidate
items through canonical CoreOpportunity rows before delivery when the core store
is available. Delivery ledger `alert_id` / dedupe item identity should use the
canonical `core_opportunity_id`; lower-level router/watchlist/hypothesis ids
must be preserved only as `source_alert_ids` / requested identity metadata.
Daily digest and instant-escalation delivery rows must also persist
`core_opportunity_id`, `canonical_symbol`, `canonical_coin_id`,
`canonical_card_path`, `feedback_target`, requested/source ids, and
identity-reconciliation metadata unless they are explicitly legacy/external
diagnostics. Artifact doctor strict mode blocks fresh core-required delivery
rows that miss those fields or keep a lower-level `ea:...` alert id.
Telegram digest bodies should be compact operator summaries, not raw router
debug dumps, and should omit full local paths and pipe-delimited internal ids.
The local notification preview is multi-lane, so preview/review artifacts must
show every planned/sent/blocked lane from the run, not just the last message.
No-send rehearsals must still write an operator preview even when there are no
digest candidates, so a missing `event_alpha_notification_preview.md` is treated
as an artifact gap rather than a normal quiet run.
Live/send digest rows with non-confirming acquisition statuses such as
`rejected_results_only`, `no_results`, or `skipped_budget` must remain
local-only unless accepted evidence, a strong official/tagged source, or fresh
non-generic market confirmation independently supports the opportunity.
Artifact doctor strict delivery checks should evaluate the latest run by
default when a latest run exists, while labeling older missing-core delivery
rows as stale/legacy diagnostics. Operators can still request all-row strict
delivery checks for migration sweeps.
**Why:** Operators and Pro-model reviewers need delivery artifacts, daily
briefs, cards, inbox items, and feedback targets to point at the same durable
opportunity. Sending a lower-level row while the canonical core says a different
asset or local-only verdict makes the Telegram output misleading and can promote
weak evidence despite quality gates. Latest-run scoping lets a fresh rehearsal
prove current safety without hiding old unsafe rows from explicit migration
review.
**Revisit when:** Notifications are backed by a typed core-opportunity delivery
table with schema-enforced source/support/core relationships.

## 2026-06-28 - Broad-asset treasury context is not direct confirmation
**Status:** accepted
**Decision:** BTC/ETH/SOL live-style strategic investment or valuation rows
about public-company treasury holdings, Strategy/MSTR valuation, ETF/company
equity valuation, CME/SEC/CFTC market-structure commentary, or similar broad
context do not satisfy `strong_direct_original_source_evidence` by themselves.
They must stay local/exploratory unless the source directly affects the asset
or token itself, accepted source-pack evidence exists, official/tagged source
evidence validates the token/catalyst/impact path, or fresh non-generic market
confirmation supports the opportunity.
**Why:** A company-valuation or treasury article may mention Bitcoin or other
major assets without creating a token-level catalyst. Treating that as a direct
BTC/ETH/SOL digest confirmation made live-style Telegram output over-permissive
and could promote broad context rows despite rejected-only or missing evidence.
**Revisit when:** Reviewed burn-in feedback shows a specific, bounded treasury
context playbook has useful recall and a separate confirmation rule is approved.

## 2026-06-28 - Operator review surfaces are canonical core-first
**Status:** accepted
**Decision:** Event Alpha notification inbox, feedback readiness, opportunity
audit, and artifact doctor must treat canonical CoreOpportunity rows as the
primary review surface when `event_core_opportunities.jsonl` is available.
Canonical cards and core feedback targets are the review target. Alert
snapshots, source-noise controls, and support rows are diagnostic attachments
by default and should only appear when a diagnostics/legacy review mode is
explicitly requested.
**Why:** Operators and Pro-model reviewers need one stable item per opportunity
to label, audit, and discuss. Letting support snapshots compete with canonical
core rows makes VELVET-style opportunities appear as both high-priority and
local/diagnostic, breaks feedback readiness counts, and can point feedback
commands at ephemeral alert ids instead of durable `agg:...` core targets.
**Revisit when:** The review UI moves to a typed relational view that can expose
core opportunities and diagnostics as separate first-class entities.

## 2026-06-28 - Diagnostic support snapshots cannot inherit core alertability
**Status:** accepted
**Decision:** Event Alpha diagnostic/support alert snapshots may carry
`core_opportunity_id` and `diagnostic_support_for_core_opportunity_id` so they
remain traceable to a canonical CoreOpportunity, but they must stay
non-alertable `STORE_ONLY` / local-only artifacts. Only canonical-core
snapshots may mirror a core row's alertable route, tier, lifecycle state, and
opportunity level. Support rows may store the canonical route/level/state only
inside `support_for_core_summary` for audit.
**Why:** Source-noise, ticker-collision, and other support/control rows are
evidence diagnostics, not operator-visible opportunities. Letting them inherit
the core route makes the same opportunity appear both high-priority and
insufficient-data/local-only, which breaks daily brief, inbox, quality-review,
artifact-doctor, and Pro-model handoff semantics.
**Revisit when:** Diagnostic/support rows are represented in a separate typed
artifact/table that cannot be loaded through the alert snapshot path.

## 2026-06-28 - Alert snapshots defer to canonical core final state
**Status:** accepted
**Decision:** When an Event Alpha alert snapshot resolves to a canonical
`core_opportunity_id`, the canonical CoreOpportunity row is authoritative for
final operator-facing route, tier, opportunity level, lifecycle state,
alertability, live-confirmation status, evidence-acquisition status, and
feedback target. Snapshot fields that existed before reconciliation may be
preserved as `requested_*_before_core_reconciliation` audit metadata, but daily
briefs, inbox queues, feedback readiness, audits, and artifact doctor checks
must use the reconciled final fields by default. Missing canonical core rows
force snapshots to non-alertable local/store-only output until the core store is
present or repaired.
**Why:** Alert snapshots are downstream artifacts. If a live confirmation gate
caps a core opportunity after snapshot-like support rows were created, stale
snapshot fields can make local-only candidates look like digest/watchlist
items. The canonical core store is the single operator contract for current
Event Alpha opportunity state.
**Revisit when:** Alert snapshots and core opportunities move into a typed
relational store where the final route/state/level relationship can be enforced
by schema and generated views.

## 2026-06-28 - Live-style digest promotion requires confirmation
**Status:** accepted
**Decision:** In live/no-send/research-send Event Alpha profiles,
`validated_digest`, `watchlist`, and `high_priority` core opportunities require
real confirmation beyond the score: accepted source-pack evidence,
official/structured source evidence, matching CryptoPanic token/catalyst
evidence, strong direct source evidence, or fresh non-generic market
confirmation. `skipped_budget`, `no_results`, `rejected_results_only`, provider
backoff/unavailable, and broad/prediction-market context do not confirm a
candidate by themselves. Sector-only rows stay exploratory/local by default
unless `RSI_EVENT_ALPHA_ALLOW_SECTOR_DIGEST=1` is explicitly set.
**Why:** Live burn-in artifacts should not promote weak article/co-occurrence
rows simply because the score model reached digest threshold while acquisition
coverage was missing or negative. Digest promotion should mean the candidate
has some source, acquisition, or market evidence that actually confirms the
token/catalyst/impact path.
**Revisit when:** A reviewed burn-in sample shows that specific source packs or
sector-only briefs are useful enough to promote under a documented, separate
policy.

## 2026-06-28 - Canonical core route follows final opportunity verdict
**Status:** accepted
**Decision:** Canonical CoreOpportunity rows must persist final route/tier fields
that agree with the final opportunity verdict. If a core opportunity is
`validated_digest`, `watchlist`, or `high_priority`, its
`final_route_after_quality_gate` should be `RESEARCH_DIGEST` or
`HIGH_PRIORITY_RESEARCH` unless a real quality block, quality-capped state,
duplicate suppression, or `TRIGGERED_FADE` route applies. Strict artifact doctor
must block fresh core rows that violate this route/verdict contract.
**Why:** Operator-facing artifacts use the canonical core store as the shared
truth. A digest-worthy core row with `STORE_ONLY` route text makes daily briefs,
cards, feedback readiness, and Pro-model review disagree about whether an
opportunity is local-only or digest-ready.
**Revisit when:** Core opportunities move from JSONL artifacts into a typed
store with schema-enforced final route/state/verdict columns.

## 2026-06-28 - Live-style burn-in requires an explicit no-send readiness gate
**Status:** accepted
**Decision:** Event Alpha live-style burn-in should have a dedicated no-send
profile and readiness report before operators treat artifacts as meaningful or
consider notification promotion. The readiness gate must verify a successful
fresh run, no send request/delivery, provider/source-pack coverage, strict
artifact-doctor status, feedback/card readiness, evidence acquisition, and
market-freshness visibility. Provider gaps should be visible as coverage gaps;
missing or degraded broad sources are not automatically strong negative
evidence.
**Why:** The radar can be safe and still misleading if a no-op run is mistaken
for a clean absence of opportunities. A profile-scoped no-send burn-in gate
separates safe execution, provider readiness, artifact completeness, and
manual review readiness without adding Telegram sends, paper/live rows, or
trading paths.
**Revisit when:** A reviewed burn-in dataset and operator feedback justify a
separate human-approved notification promotion workflow.

## 2026-06-28 - Source contracts must be explicit in operator artifacts
**Status:** accepted
**Decision:** Event Alpha source-quality artifacts should expose a compact
source contract: what the source can prove, what it cannot prove, which
playbooks it is useful for, and whether absence of evidence is meaningful.
Non-official sources must explicitly mark `official_confirmation` as not
provable, even when they can validate token identity, catalyst context, or
impact path through other evidence.
**Why:** Source packs combine official, structured, news, prediction-market,
market, derivatives, and supply evidence. Operators need to see why a
CryptoPanic-tagged item can strengthen token/catalyst evidence but still does
not replace an official project/exchange confirmation.
**Revisit when:** Source registry and evidence acquisition move into a typed
store with enforced source-contract columns and richer provider-specific
schemas.

## 2026-06-28 - Canonical core view owns incident context
**Status:** accepted
**Decision:** `CanonicalCoreOpportunityView` should include linked canonical
incident rows and select the best incident row for operator-facing rendering.
Cards, opportunity audits, daily briefs, and doctor checks should consume
incident/catalyst-frame context through this joined core view when a canonical
core opportunity exists. Legacy per-row incident reconstruction is fallback
only for old artifacts without core rows.
**Why:** Incident rows carry the main catalyst frame, subject/actor/object,
claim context, and relevance status. Reconstructing that context separately
from the canonical opportunity can make cards or audits disagree with the
core row even when route/state/evidence are already canonical.
**Revisit when:** Event Alpha incidents and core opportunities move into a
typed store with explicit relational joins.

## 2026-06-28 - Canonical core verdict fields own secondary operator copy
**Status:** accepted
**Decision:** When a canonical CoreOpportunity row exists, research cards,
opportunity audits, quality review, and artifact-doctor checks must render both
primary and secondary source/impact/market/upgrade/downgrade copy from the
canonical final core fields and joined canonical acquisition/market evidence.
Fallback/support-row blockers such as generic co-occurrence, missing direct
mechanism, or missing value capture may appear only in diagnostic/support
sections when the final core has already passed those gates. Filler values such
as `unknown`, `missing`, `none`, or `insufficient_data` should not override
accepted evidence samples or derived canonical market/impact fields.
**Why:** Operators and Pro-model reviews inspect cards and audits first. A
high-priority core opportunity that shows stale support-row blockers or
`Latest source: unknown` in secondary sections looks contradictory even when
the stored final route/state are correct.
**Revisit when:** Core opportunities, source acquisition, market refresh,
cards, audits, and support diagnostics move into a typed store that can enforce
final-vs-support presentation contracts by schema.

## 2026-06-28 - Canonical core acquisition view owns source-evidence display
**Status:** accepted
**Decision:** Operator-facing cards, audits, quality review, and artifact
doctor checks must display source-pack acquisition evidence through the
canonical core opportunity view when `event_core_opportunities.jsonl` is
available. Accepted/rejected evidence counts, reason codes, samples, source
pack, provider failures, and before/after verdict metadata should be attached
to the stored core row or joined through `CoreEvidenceAcquisitionView`.
Support/control acquisition rows may remain available as diagnostics, but they
must not override the primary core card, audit, quality-review section, market
freshness summary, or upgrade-candidate list.
**Why:** Source acquisition runs after multiple lower-level rows have been
created. Reading those rows directly can make one promoted opportunity look
accepted in JSONL, rejected in the card, weak in quality review, and upgradable
in another section. The canonical core view is the operator contract.
**Revisit when:** Event Alpha artifacts move from JSONL joins into a typed
store with schema-enforced source-acquisition relations.

## 2026-06-28 - Core research cards use final quality-gated verdict copy
**Status:** accepted
**Decision:** Canonical Core Opportunity Cards must render their operator-facing
quality-gate and promotion/local-only copy from the stored final core fields:
`final_route_after_quality_gate`, `final_state_after_quality_gate`,
`opportunity_level`, `opportunity_score_final`, and final verdict reason/source.
They must not rerun raw validated-hypothesis digest eligibility against a
synthetic card row when a canonical `core_opportunity_id` is present. Raw
support/control row gate reasons may still appear as diagnostics, but they
cannot override the final core verdict copy.
**Why:** Core cards are the human review object. Re-evaluating a merged core as
a raw hypothesis can make a digest/high-priority opportunity show stale
`local-only` text from an old support row, creating operator confusion even when
the route/state artifacts are correct.
**Revisit when:** Core opportunities, support rows, cards, and alert snapshots
move into a typed store that can enforce final-vs-support presentation fields
by schema.

## 2026-06-28 - Feedback labels are calibration artifacts, not mutations
**Status:** accepted
**Decision:** Event Alpha feedback labels should be stored as enriched
research artifacts tied to the best available review object: canonical core
opportunity, research card, alert snapshot, or watchlist row. A label must
preserve enough signal context to calibrate later: source pack/class/domain,
impact path, candidate role, opportunity level, final route/lane, market
confirmation/freshness, catalyst-frame status, provider metadata, and linked
incident/hypothesis/watchlist identifiers. Useful/junk/watch/missed labels may
feed calibration reports, proposed priors, policy simulations, and proposed
signal-quality eval cases, but they must not directly change thresholds,
routes, watchlist state, alerts, paper/live rows, normal RSI rows, or
`TRIGGERED_FADE`.
**Why:** Manual review is the only practical way to learn which Event Alpha
signals are useful or junk, but mutating routing directly from sparse feedback
would overfit and weaken safety boundaries. Enriched labels make learning
auditable while keeping promotion decisions explicit.
**Revisit when:** There is enough reviewed feedback/outcome data to propose a
versioned, human-approved calibration prior or threshold change with holdout
eval coverage.

## 2026-06-28 - Evidence absence is source-pack and coverage scoped
**Status:** accepted
**Decision:** Event Alpha source evidence must carry an explicit source
contract (`source_can_prove`, `source_cannot_prove`, useful playbooks, mission,
confidence cap, and coverage status) plus playbook-specific source-pack
sufficiency fields. Official exchange/project, structured calendar/unlock,
matching CryptoPanic tags, market data, derivatives, and supply sources each
prove different things. Broad GDELT/RSS/Polymarket context, SEO/recap feeds, or
degraded/unavailable providers must not make “no source found” look like strong
negative evidence. Source-pack acquisition may execute bounded provider queries
and persist plans/results/coverage gaps, but accepted evidence is still only
research metadata until deterministic identity, catalyst-link, impact-path,
quality, router, and `event_fade.py` gates validate it.
**Why:** Event Alpha’s semantic layer is only as good as the source layer. A
clean source contract prevents broad/noisy feeds from over-validating token
impact while making true official/CryptoPanic/structured evidence auditable.
**Revisit when:** Source/provider coverage moves from JSONL artifacts into a
typed store with provider-level SLAs, reviewed precision/recall, and automated
source-quality calibration.

## 2026-06-28 - Canonical CoreOpportunity view is the operator read model
**Status:** accepted
**Decision:** Operator-facing Event Alpha artifacts should read one joined
canonical view for a core opportunity: the stored core row, supporting rows,
diagnostic/control rows, evidence acquisition, market refresh evidence, card
path, alert snapshots, and feedback status. New card and audit code should use
`load_canonical_core_opportunity_view(...)` or its row-based equivalent when a
canonical core store is available, falling back to legacy aggregation only for
older artifacts without core rows.
**Why:** Canonical core ids solved most duplicate/opportunity drift, but callers
could still reassemble different partial views from the same artifacts. A
single read model makes the stored final route/state/verdict the operator
contract while preserving all supporting evidence for audit.
**Revisit when:** Event Alpha artifacts move into a typed store with schema
enforced joins and the JSONL read model can be replaced by database queries.

## 2026-06-28 - CoreOpportunity store rows win after secondary artifact writes
**Status:** accepted
**Decision:** Event Alpha cycles may create secondary artifacts after the
canonical core store is first written, such as research cards and source-pack
evidence acquisition rows. Those secondary artifacts must be reconciled back to
the canonical `event_core_opportunities.jsonl` rows before operator-facing
reports are considered ready. Research-card paths and feedback targets should
be written back onto the stored core rows, and evidence-acquisition rows whose
temporary core ids resolve to a compatible stored core should carry the
canonical `core_opportunity_id` plus diagnostic support metadata. Cards,
audits, daily briefs, and artifact-doctor checks should read the reconciled
canonical row first, with support/control rows used only as diagnostics.
**Why:** Post-cycle artifacts can otherwise make a high-quality core opportunity
look downgraded or fragmented: for example a VELVET core can be stored as
high-priority while a support row/card still displays `STORE_ONLY`, or a source
acquisition result can point at an orphan core id. Reconciliation keeps the
operator view and Pro-model review bundle centered on one truthful object.
**Revisit when:** Core opportunities, cards, evidence acquisition, and feedback
targets are written transactionally in a single typed store.

## 2026-06-28 - Canonical core ids govern visible Event Alpha artifacts
**Status:** accepted
**Decision:** Visible Event Alpha research cards, daily-brief card groups, alert
snapshots, opportunity audits, and artifact-doctor coverage must resolve through
canonical `event_core_opportunities.jsonl` rows when those rows exist. A visible
core opportunity id is valid only when it is present in the canonical store or
resolves to a compatible stored incident/asset/role/path family. Source-noise,
ticker-collision, control, and other diagnostic rows may link to a canonical
core through `diagnostic_support_for_core_opportunity_id`, but they must not
invent separate visible core ids or appear in Core Opportunity Cards.
**Why:** Operator-facing artifacts need one stable review object per real
opportunity. Fake card/snapshot core ids made Pro-model review and feedback
grouping ambiguous, and daily briefs could disagree with card indexes or market
freshness summaries.
**Revisit when:** The JSONL artifact store is replaced by a typed relational or
document store that enforces core/card/snapshot/support relationships by schema.

## 2026-06-28 - Persisted CoreOpportunity rows are authoritative for operators
**Status:** accepted
**Decision:** After an Event Alpha cycle writes canonical
`event_core_opportunities.jsonl` rows, operator-facing reports should prefer
those rows over recomputing visible opportunities from mixed hypotheses,
watchlist entries, alert snapshots, and support/control rows. The store records
one final post-refresh, quality-gated core opportunity per visible
incident/asset/role/path family, plus support and diagnostic row ids. Daily
briefs, near-miss reports, cards, audits, run ledgers, and artifact doctor
checks should treat the stored final route/state/opportunity verdict as the
operator contract when present. Raw/support rows remain available for
diagnostics, but they must not downgrade or duplicate the visible final
opportunity.
**Why:** Recomputing from heterogeneous artifacts made reports disagree after
targeted market refresh and evidence acquisition. A promoted VELVET opportunity
could also appear as a near-miss, and stale RUNE support rows could make a
watchlist core look downgraded. Persisting the final core state gives operators
and Pro-model reviews one stable object to inspect.
**Revisit when:** Core opportunities move from JSONL artifacts into a typed
database with schema-enforced relationships to hypotheses, cards, snapshots,
feedback, and outcomes.

## 2026-06-28 - Evidence acquisition reports final verdicts, not evidence wins
**Status:** accepted
**Decision:** Event Alpha source-pack evidence acquisition must distinguish
evidence-quality improvement from final opportunity upgrades. Accepted evidence
may improve source quality, impact-path support, or review context, but
`final_upgrade_status` and operator-facing route/state fields must be based on
the canonical final opportunity verdict. Artifacts should preserve
`initial_*`, `post_refresh_*`, and `final_opportunity_*` fields so operators can
audit what changed. If a prior market-refresh verdict is stronger and the new
evidence collection does not produce a better final opportunity, the stronger
final verdict may be preserved with an explicit source/reason. Market data
freshness and market reaction confirmation must remain separate fields.
**Why:** A source row can prove better evidence without making the trade/research
opportunity better, and a later evidence pass can otherwise make reports look
upgraded or downgraded for the wrong reason. The final verdict is the only field
that should drive operator-facing promotion.
**Revisit when:** Evidence acquisition moves into a typed store and the
initial/post-refresh/final verdict relationship can be enforced by schema.

## 2026-06-28 - Source-pack acquisition executes evidence, not alerts
**Status:** accepted
**Decision:** Event Alpha may execute bounded source-pack evidence plans for
selected near-misses and validated hypotheses, using fixture or configured
providers to collect candidate evidence. Every result must still pass
deterministic identity, catalyst-link, impact-path, source-mission, and
source-quality checks before it can improve a research verdict. Acquisition
artifacts may record accepted/rejected evidence, before/after quality, provider
failures, and upgrade/no-upgrade reasons, and feedback/calibration may group by
source pack and accepted evidence reason codes. Acquisition must not send
Telegram messages, trade, paper trade, write normal RSI rows, or create
`TRIGGERED_FADE`; only `event_fade.py` plus `proxy_fade` can do that.
**Why:** The source registry and planner were useful but too passive when they
only described what to search next. Executing the plans makes near-miss review
actionable while preserving the safety boundary between evidence collection and
alert/trade creation.
**Revisit when:** Reviewed acquisition artifacts show stable precision/recall
by source pack, provider, and accepted reason code, and the human explicitly
approves any promotion beyond local research artifacts.

## 2026-06-28 - Event Alpha source evidence is mission-scoped
**Status:** accepted
**Decision:** Event Alpha source evidence must be interpreted through source
class, source mission, provider coverage, and playbook source-pack context.
Official exchange/project and structured event/unlock sources can validate
token identity, catalyst timing, and direct impact when their evidence is
specific. CryptoPanic currency-tag matches are stronger narrative/catalyst
evidence than untagged news. Broad news, RSS recaps, SEO/affiliate posts, and
prediction-market rows are context/diagnostic evidence by default; Polymarket
or GDELT absence is not a strong negative when provider coverage is degraded,
partial, unavailable, or not configured. A constrained evidence planner may
produce source-pack query/checklist metadata for near-miss or upgrade
candidates, but it must not create alerts, routes, watchlist state, paper/live
rows, normal RSI writes, or `TRIGGERED_FADE`.
**Why:** Event Alpha was collecting useful context from broad providers, but
operators need to know whether a source actually proves asset identity and
impact path or merely suggests where to look next. Source-pack semantics reduce
false confidence while making near-miss evidence acquisition more actionable.
**Revisit when:** Event Alpha stores source health, source pack fulfillment,
and evidence acquisition attempts in a typed database with provider-level SLAs
and reviewed precision/recall metrics.

## 2026-06-28 - CoreOpportunity is the operator-visible artifact contract
**Status:** accepted
**Decision:** Event Alpha operator-facing output should be keyed by
`core_opportunity_id` whenever a row is visible in high-priority, validated
digest, watchlist, near-miss, upgrade-candidate, or non-diagnostic local/capped
sections. Visible core opportunities must keep a research card, stable feedback
target, and audit target even when route or duplicate suppression prevents a
send. Alert snapshots written from core opportunities should carry
`core_opportunity_id`, `feedback_target`, `feedback_target_type`, card path, and
card group when available. Artifact doctor and feedback readiness should treat
missing coverage for fresh visible core opportunities as a blocker. Near-miss
reports should separate local near-misses from already-valid upgrade candidates,
and market-freshness readiness should summarize by core opportunity by default.
**Why:** Operators and Pro-model reviews need one visible object per real
opportunity, with supporting rows preserved as diagnostics. Suppressing duplicate
sends must not remove the review card or feedback handle for a RUNE/THORChain-
style watchlist opportunity, and row-level market/readiness output was too noisy
to use safely.
**Revisit when:** Event Alpha artifacts move into a typed store where core
opportunities, cards, snapshots, feedback labels, and market-refresh attempts
are enforced by schema-level relationships.

## 2026-06-27 - Event Alpha lifecycle caps are not route blockers
**Status:** accepted
**Decision:** Event Alpha must keep lifecycle state caps and route quality gates
separate. Lifecycle caps decide the final watchlist state
(`QUALITY_BLOCKED`, `RADAR`, `WATCHLIST`, `HIGH_PRIORITY`, etc.). Route gates
decide operator routing (`STORE_ONLY`, local report, digest, high-priority
research, triggered-fade research). A hard quality block such as local-only,
insufficient impact/evidence/source, zero final score, source noise, or ticker
collision may force `STORE_ONLY`. A soft lifecycle cap such as
`opportunity_level_caps_state:watchlist` or
`opportunity_level_caps_state:validated_digest` must not by itself force
`STORE_ONLY`; the row continues through normal route eligibility and route caps.
Incident artifact health follows the same distinction: quality-blocked support
links are diagnostic warnings when a qualified link exists, and blockers only
when blocked links would otherwise be the sole active incident support.
**Why:** The operator view needs to show a valid RUNE/THORChain-style watchlist
opportunity as digest/watchlist research even when requested high-priority
lifecycle state is capped to watchlist. Treating all state caps as route blocks
hid real validated opportunities and produced misleading block reasons.
**Revisit when:** Event Alpha moves to a typed lifecycle/router database with
explicit foreign keys and a UI that can show requested state, final state,
requested route, final route, and diagnostic support links as separate fields.

## 2026-06-27 - Targeted market refresh is bounded and validation-first
**Status:** accepted
**Decision:** Event Alpha may run targeted market-context refresh for
already-validated candidates whose promotion is blocked by stale, missing, or
unknown market context. The queue must be auditable by refresh id, validated
symbol/coin id, incident/hypothesis/core opportunity ids, reason, current market
source/age, and priority score. Refresh may use current-cycle rows, fresh
fixture rows in explicit proof profiles, active-watchlist market snapshots, or
configured fail-soft providers, and must persist attempted/success/provider/error
metadata plus before/after market confirmation and opportunity verdict fields.
It must not run for source-noise, ticker-collision, generic co-occurrence, or
unvalidated assets, and it must not reprocess already-promoted watchlist/high
priority candidates with fresh market context.
**Why:** Strong candidates such as VELVET/SpaceX can be semantically correct but
stuck below watchlist/high-priority because market evidence is stale. A bounded
validation-first refresh lets the radar use fresh market context without turning
market anomalies or provider/LLM output into trades or triggers.
**Revisit when:** Event Alpha has durable point-in-time market snapshots with
provider SLAs and reviewed outcome evidence for refresh-driven promotions.

## 2026-06-27 - Event Alpha operator artifacts need joinable lineage
**Status:** accepted
**Decision:** Operator-facing Event Alpha artifacts must preserve enough
lineage to move between daily brief, research card, opportunity audit,
notification inbox, and feedback commands without guessing. Current research
cards should show run id, profile, artifact namespace, incident id, hypothesis
id, watchlist key, core opportunity id, alert/snapshot/card ids, and source raw
or event ids when available. Legacy rows may remain readable, but missing
lineage must be labeled as legacy/missing rather than rendered as a current
unknown. Current cards must also show card path, stable feedback target,
feedback target type, and ready-to-copy feedback commands. Card indexes are
navigation artifacts, not research cards: readiness and artifact doctor counts
must count real card files separately from `index.md` and should block current
cards missing lineage or feedback targets. Feedback and audit target lookup
should accept the same family of ids where practical, including card paths, and
opportunity audit should read feedback artifacts so already-marked review status
is visible for the same target. Live-style frame profiles should also expose
whether catalyst frame analysis ran or was intentionally skipped, and daily
operator views should separate the canonical core-opportunity sections from
diagnostics.
**Why:** Pro-model review and daily operations depend on being able to trace one
visible opportunity back to its source evidence, support rows, card, and
feedback target. Unlabeled lineage gaps and inconsistent target lookup make
good artifacts hard to review and make legacy rows look current.
**Revisit when:** Event Alpha artifacts move from JSONL/Markdown files into a
typed review database with enforced foreign keys and a UI for card/audit/feedback
navigation.

## 2026-06-27 - Stale market context cannot promote Event Alpha candidates
**Status:** accepted
**Decision:** Event Alpha market confirmation must carry source, observed-at
timestamp, age, and freshness status through hypotheses, watchlist rows, alert
snapshots, cards, audits, daily briefs, and signal-quality eval output. Live or
notify-style profiles treat stale, missing, or unknown-timestamp market context
as capped evidence: it may support local review, radar, or validated digest
context when other evidence is strong, but it must not by itself promote a
candidate to `WATCHLIST` or `HIGH_PRIORITY`. Fixture/e2e profiles may opt in to
stale fixture market context only when it is explicitly configured and clearly
labeled `fixture_allowed_stale`. Source enrichment must also treat fixture or
example URLs as local fixture text and must not fetch those URLs over the
network.
**Why:** Event Alpha's operator view depends on market confirmation being
current enough to justify escalation. Reusing old market snapshots or fetching
fixture URLs made offline artifacts look more live than they were and could
overstate stale evidence in Pro-model review packages.
**Revisit when:** Market enrichment stores point-in-time snapshots in a typed
database with enforced source timestamps and provider freshness SLAs.

## 2026-06-27 - Event Alpha default operator views are core-first
**Status:** accepted
**Decision:** Daily briefs, notification inboxes, research-card indexes, and
quality reviews should present promoted Event Alpha opportunities through a
single core-opportunity view by default. Already-promoted opportunities must not
also appear as exploratory digest rows or near-misses. Near-miss rows should be
deduplicated by incident, asset, candidate role, and impact path. The daily
brief's default top-level sections are for operator decisions; raw watchlist,
validated-routing, signal-quality, suppression, and other row-level dumps belong
under a Diagnostics Appendix unless explicitly requested. Possible
false-positive lists should require explicit suspicion reason codes such as
source noise, ticker collision, generic co-occurrence, low-confidence identity,
source-origin-only identity, common-word collision, invalid subjects,
diagnostic-only rows, or rejected candidate asset evidence. Missing context,
weak impact paths, and missing direct impact paths are local-only blockers by
themselves, not false-positive suspicion labels unless paired with explicit
noise/collision/co-occurrence evidence. Research-card grouping should use stored
watchlist/quality metadata when available, and daily-brief card links should use
the same core, near-miss, local/quality-capped, diagnostic/control, and legacy
groups as card indexes. Content/filename fallback exists only for legacy
artifacts. Card and near-miss copy should be verdict-aware: validated strategic
investment, proxy venue/exposure, and unknown market-dislocation rows should not
fall back to stale generic source-identity failure language or expose raw
internal reason codes as the main operator explanation.
**Why:** Operators need to review actual opportunities, not every support row
and diagnostic/control artifact as if it were a separate lead. Mixing promoted
VELVET/AAVE/RUNE/ZEC rows with near-miss, exploratory, or suspicion sections
creates false workload and obscures which candidates are actionable research
items versus local learning evidence.
**Revisit when:** Event Alpha has a typed UI that can render expandable support,
diagnostic, and control rows under each primary opportunity.

## 2026-06-27 - Operator reports show core opportunities, not duplicate support rows
**Status:** accepted
**Decision:** Event Alpha operator-facing reports should aggregate compatible
rows by incident, validated asset, candidate role, and impact-path family into a
single core opportunity. Supporting hypotheses, quality-capped rows, duplicate
raw observations, source-noise controls, and ticker-collision controls should
remain available as audit diagnostics, but they should not create separate
default daily-brief/card/near-miss entries for the same opportunity.
**Why:** The same VELVET/SpaceX opportunity can legitimately produce several
supporting rows: venue value capture, RWA pre-IPO proxy, quality-capped support,
and source-noise controls. Showing each row as a separate operator opportunity
overstates the number of real leads and makes promoted opportunities look like
near-misses or junk at the same time.
**Revisit when:** Event Alpha moves to a typed UI/database that can render a
primary opportunity with expandable support/control evidence natively.

## 2026-06-27 - Event Alpha feedback preserves incident context
**Status:** accepted
**Decision:** Manual Event Alpha feedback rows should preserve the same
artifact context needed for later calibration: `incident_id`, impact path,
candidate role, opportunity level, evidence specificity, market confirmation,
and source class. Calibration reports should group feedback-only rows by those
fields even when no matching alert snapshot exists.
**Why:** Feedback is useful only if it can be mapped back to the incident spine
and quality verdict that produced the candidate. Otherwise useful/junk labels
can tune broad playbook counts while losing the specific incident/source class
that caused the outcome.
**Revisit when:** Feedback moves from JSONL artifacts into a typed review
database with foreign keys to incident, watchlist, alert, and card rows.

## 2026-06-27 - Sector placeholders are not qualified incident asset links
**Status:** accepted
**Decision:** Event Alpha incident relevance must treat taxonomy/sector
identities such as `SECTOR`, `sports_fan_proxy`, `political_meme_proxy`,
`ai_ipo_proxy`, `rwa_preipo_proxy`, `tokenized_stock_venue`, and
`prediction_market_infra` as sector placeholders, not validated affected crypto
assets. They may keep broad incidents visible as research candidates, but they
must not qualify an active/linked incident unless a deterministic resolver or
validated asset row supplies a concrete token/project identity.
**Why:** Broad external events can mention fan-token, proxy, or venue sectors
without naming a tradable asset. Treating those taxonomy placeholders as
qualified crypto links made broad incidents look more actionable than the
evidence supported.
**Revisit when:** A typed incident graph distinguishes sector taxonomy nodes
from validated asset nodes at schema level and reports them separately.

## 2026-06-27 - Catalyst-frame coverage must be operator-auditable
**Status:** accepted
**Decision:** Live-style Event Alpha profiles that depend on catalyst-frame
quality control must expose frame coverage as first-class artifact metadata.
Run ledgers, daily briefs, quality review, cards, opportunity audits, and
artifact doctor reports should show analyzed/validated/unresolved/skipped frame
counts, selected artifact namespace, and normalized skip reasons such as
`disabled`, `missing_api_key`, `budget_exhausted`, `no_rows_selected`,
`profile_disabled`, and `deadline_exceeded`. Operator-facing opportunity
sections may aggregate duplicate supporting hypotheses into one core
opportunity row, but they must preserve supporting categories, impact paths,
hypothesis ids, and evidence in audit fields. The fixture-backed
`notify_llm_quality_frame` profile is the no-send proof path for this live-style
artifact shape.
**Why:** A profile can appear healthy while silently missing catalyst-frame
coverage because of provider configuration, missing credentials, budget/deadline
limits, or prefilter behavior. Operators and Pro-model reviewers need clear
coverage and skip-reason artifacts without reading raw JSONL internals or
mistaking duplicate supporting rows for separate opportunities.
**Revisit when:** Catalyst-frame artifacts move to a typed research database
with enforced coverage columns and a dedicated UI for frame status, duplicate
support, and skip reasons.

## 2026-06-27 - Required catalyst frames cap ambiguous research routes
**Status:** accepted
**Decision:** Event Alpha rows that contain ambiguous, multi-catalyst, proxy,
investment/valuation, or background/security language should record whether
catalyst-frame analysis was required, performed, validated, unresolved, skipped,
or missing. If a required frame is missing or unresolved, validated hypotheses
must stay local/exploratory unless deterministic evidence is independently
sufficient for the direct event path. Missing/unresolved frame reasons such as
`catalyst_frame_required`, `catalyst_frame_missing`,
`catalyst_frame_unresolved`, and `catalyst_frame_conflict_caps_route` are route
quality-control metadata only; they cannot create candidates or triggers.
Incident asset roles must also distinguish validated affected assets from
taxonomy/search suggestions: unvalidated LINK/PYTH-style taxonomy suggestions
in a THORChain/RUNE exploit article are candidate suggestions, not direct
incident subjects. Compatible validated hypotheses may aggregate by incident,
validated asset, role, and impact-path family, but supporting categories and
quotes must remain auditable.
**Why:** A live-style run can have the catalyst-frame feature configured but
fail to receive validated LLM output because of provider availability, budget,
prefiltering, or unresolved analysis. Treating those rows as if no frame was
needed would overstate ambiguous evidence. Separately, taxonomy expansion is
useful for search, but it must not turn infrastructure-adjacent tokens into
directly affected assets.
**Revisit when:** A reviewed incident/hypothesis dataset proves that specific
missing-frame categories can be safely promoted without LLM support, or when a
typed research database enforces frame status and asset-role provenance at
schema level.

## 2026-06-27 - LLM catalyst frames are validated research metadata only
**Status:** accepted
**Decision:** Event Alpha may use a constrained LLM catalyst-frame analyzer to
propose the source's main catalyst, background/historical context, negated or
corrective claims, rejected impact paths, and manual verification items, but
only after deterministic validation. Valid frames require quote support in the
source text, acceptable crypto-asset identity evidence, no external-entity-as-
crypto misuse, and no generic ticker-word collision. A validated LLM main frame
may override a weaker deterministic rule frame only when those gates pass and
the disagreement is recorded. Once accepted, the transformed raw rows are the
authoritative source for downstream incident and impact-hypothesis artifacts,
so incident, hypothesis, watchlist, card, audit, daily-brief, and run-ledger
rows should preserve selected-main-frame, background/corrective, rejected-path,
and rule-vs-LLM resolution metadata. Hard deterministic safety gates still win:
validated LLM frames cannot create `TRIGGERED_FADE`, send notifications, open
paper/live trades, write normal RSI signal rows, or bypass resolver, quality,
proxy/direct, or event-fade eligibility checks.
**Why:** Some articles contain the actionable catalyst in the headline while
using exploit/policy/background language elsewhere. The AAVE/Kraken/KelpDAO
case needs semantic framing to preserve the Kraken strategic-stake catalyst and
reject the KelpDAO exploit mention as background without letting an LLM invent
assets or routes.
**Revisit when:** A reviewed artifact dataset shows either systematic LLM
frame mistakes that require stricter gating, or enough validated cases to move
frame analysis from ambiguous-only support into a broader configured review
surface.

## 2026-06-27 - Main catalyst frames drive incident and impact classification
**Status:** accepted
**Decision:** Event Alpha source interpretation must separate the article's
main catalyst from background, historical, corrective, negated, side-note, and
market-reaction context before incident, impact-path, hypothesis, and
opportunity verdict logic run. Fresh rows should carry frame metadata such as
`main_catalyst_frame_id`, `main_frame_type`, `background_frame_ids`,
`negated_frame_ids`, `frame_summary`, `background_context_summary`, and
`rejected_impact_paths` when relevant. Only the selected main catalyst frame may
drive direct impact classification. Background/historical exploit mentions and
negated/corrective claims may be persisted for audit, but they must not promote
the event into an exploit/security playbook or make a token the affected subject
when the main catalyst is a strategic stake, valuation, listing, proxy, or
other non-security event.
**Why:** Source articles often include unrelated incident history or corrective
language. Treating those context phrases as the main event produced false
security paths, such as reading an AAVE/Kraken strategic-stake article as an
AAVE exploit because the body referenced a prior KelpDAO exploit and said Aave
itself was not hacked.
**Revisit when:** A reviewed incident dataset supports a richer multi-catalyst
model with explicit simultaneous main events and audited precedence rules.

## 2026-06-26 - Final opportunity verdict is the Event Alpha routing source
**Status:** accepted
**Decision:** Event Alpha validated-hypothesis routing and lifecycle quality
checks must use `opportunity_score_final` and `opportunity_level` as the
canonical active verdict. Older/intermediate fields such as
`opportunity_score_v2`, `hypothesis_score`, and playbook/watchlist score remain
audit and diagnostic inputs only; they must not block or promote a route when a
final opportunity verdict is present. Route decisions should record
`routing_score_used`, `routing_score_source=opportunity_score_final`, and
`routing_verdict_used` so the operator can see which verdict drove routing.
Near-miss refresh may fetch bounded market/enrichment/evidence context for
already-validated near-promotion candidates and recompute the final verdict,
but it is research-only and cannot send notifications by itself, create paper
or live rows, write normal RSI signals, execute trades, or create
`TRIGGERED_FADE`.
**Why:** A stale intermediate score can contradict the final signal-quality
verdict and hide useful validated candidates. Near-miss refresh should acquire
missing evidence before final routing without weakening deterministic safety
gates.
**Revisit when:** The opportunity verdict model is replaced by a versioned
research database/schema with explicit migration and backtest-reviewed
thresholds.

## 2026-06-26 - Canonical incidents require crypto relevance
**Status:** accepted
**Decision:** Event Alpha incident artifacts must distinguish raw source
observations from crypto-relevant canonical incidents. Fresh incident rows carry
`incident_relevance_status`, `incident_relevance_score`,
`incident_relevance_reasons`, `incident_relevance_warnings`, and
`canonical_persistence_reason`. Broad external context without a crypto link
uses `external_context_only`, while generic unstructured unlinked rows use
`raw_observation`. Live-style profiles persist
`incident_candidate`, `canonical_incident`, `linked_incident`, and
`active_incident` rows by default; `raw_observation`,
`external_context_only`, `diagnostic_only`, and `rejected_incident` rows are
hidden/not persisted unless `RSI_EVENT_INCIDENT_STORE_RAW_OBSERVATIONS=1`,
`RSI_EVENT_INCIDENT_STORE_DIAGNOSTIC=1`, or fixture/debug mode is intentionally
active. A broad external event without a validated crypto asset, generated
hypothesis, watchlist linkage, direct crypto archetype, or market-dislocation
evidence is external context/raw evidence, not an operational canonical
incident.
`active_incident` and `linked_incident` status require quality-qualified crypto
links, not merely any legacy hypothesis/watchlist id. A link qualifies only when
the linked row is not quality-capped/local-only, has a non-generic impact path,
has non-insufficient evidence, has a concrete validated asset or strong sector
thesis, and avoids unknown/generic/source-noise roles. Weak sector-only,
unknown-role, or quality-blocked links are recorded as link-quality diagnostics
and may leave an event as `incident_candidate`/`external_context_only`, but they
do not make the incident active.
**Why:** Broad political, sports, prediction-market, and news rows are useful
for source diagnostics and future search, but showing them beside linked crypto
incidents overstates actionability and creates noise in daily briefs, doctor
checks, and Pro-model reviews.
**Revisit when:** A reviewed incident dataset shows that currently hidden raw
external observations reliably become useful crypto hypotheses, or when a typed
research database can store separate raw-observation and canonical-incident
tables with explicit UI filtering.

## 2026-06-26 - Fresh live-style quality proof uses an isolated namespace
**Status:** accepted
**Decision:** When proving Event Alpha quality/incident fixes against live-style
inputs, use the isolated `notify_llm_quality_fresh` artifact namespace and
`make event-alpha-quality-live-smoke PROFILE=notify_llm_quality_fresh` rather
than interpreting older `notify_llm_quality` rows as fresh evidence. The fresh
proof path mirrors `notify_llm_quality` quality gates and sources, uses the
wall clock, does not pass `--event-alert-send`, clears only its own namespace,
and then runs the daily brief, quality review, incident report, and strict
artifact doctor.
**Why:** Stale JSONL artifacts can predate quality lifecycle caps or incident
subject validation. A clean namespace separates current writer behavior from
historical leakage without rewriting old artifacts.
**Revisit when:** Event Alpha artifacts move to a versioned research database
with explicit migrations and current-vs-legacy row scoping.

## 2026-06-26 - Event Alpha quality verdicts cap lifecycle state
**Status:** accepted
**Decision:** Event Alpha watchlist lifecycle state must obey the final quality
verdict, not only router/notification gates. Fresh rows with
`opportunity_level=local_only` or `exploratory`, `opportunity_score_final <= 0`,
`impact_path_type=insufficient_data`, `candidate_role=unknown_with_reason`,
`source_class=insufficient_data`, or `evidence_specificity=insufficient_data`
must not persist as active `WATCHLIST`, `HIGH_PRIORITY`, `EVENT_PASSED`, or
`ARMED` unless they explicitly persist a non-active
`final_state_after_quality_gate` plus `state_quality_capped=true`. Missing
quality on fresh alert/playbook/market-anomaly rows is conservative local-only
evidence, and stale persisted final states must be recomputed from quality
fields when those fields are present. The lifecycle cap is a persistence rule
for every fresh watchlist row, including non-hypothesis event-alert/playbook
rows; requested pre-quality state is audit metadata only. Artifact doctor must
inspect path-scoped watchlist rows even when older rows lack embedded
profile/namespace fields.
Generic prose, source, and SEO fragments are not valid canonical incident
subjects; invalid incident rows are diagnostic-only unless linked to real
hypothesis/watchlist context. Existing persisted garbage subjects such as
`LLM`, `Best Prediction Market Apps`, or `Polymarket Invite Code SBWIRE` must be
quarantined at read/report time and hidden from default incident reports unless
diagnostics are explicitly requested. Fresh incident store writes must validate
primary subjects before persistence so garbage subjects are rejected,
diagnostic-only, external/raw context, or replaced by validated fallback
context rather than stored as canonical valid incidents. These rules are
artifact truth and operator-UX rules only, and
cannot create candidates, normal RSI alerts, paper rows, trades, or
`TRIGGERED_FADE`.
**Why:** Operator reports should not show local-only or insufficient-data
evidence as active opportunities merely because an older playbook/watchlist path
requested a stronger state. Likewise, incident reports need real entities, not
capitalized boilerplate fragments.
**Revisit when:** A typed research database replaces JSONL artifacts and enforces
equivalent final-state and incident-subject constraints at schema/write time.

## 2026-06-26 - Canonical incident id is the Event Alpha spine
**Status:** accepted
**Decision:** For Event Alpha impact-hypothesis artifacts, the canonical
incident id is the primary research identity spine. Hypotheses, hypothesis-store
rows, hypothesis-derived watchlist rows, route alert snapshots, incident
reports, run-ledger rows, opportunity audits, daily briefs, cards, and artifact
doctor checks should carry incident linkage when the source evidence belongs to
an incident. Hypothesis watchlist identity should prefer
`incident_id + validated asset/sector identity + candidate_role +
impact_path_type`, not only symbol/title/source text. Missing incident ids on
fresh hypothesis/watchlist/alert rows are artifact-health problems unless the
row explicitly represents no-incident evidence. Incident identity and linked
counts are audit/provenance metadata only; they do not create candidates,
routes, paper rows, normal RSI rows, trades, or `TRIGGERED_FADE`.
Explicit no-incident evidence must carry both `incident_link_status=no_incident`
and an `incident_link_reason`; otherwise strict artifact-health checks should
treat a missing incident id as a fresh linkage failure. Market-anomaly incidents
may mark a crypto asset as `direct_subject` only when the validated asset
identity comes from the market/anomaly payload or equivalent resolver-validated
evidence. `SECTOR` and generic unknown-market context are sector/context roles,
not direct incident subjects.
**Why:** Event Alpha increasingly reasons over follow-up source updates,
disputed/confirmed claims, and market reaction for the same underlying event.
Without a stable incident spine, duplicate articles can fragment watchlist
state, hide independent-source confirmation, and make artifact reports disagree
about what happened.
**Revisit when:** Incident storage is migrated to a reviewed research database
with an explicit schema version and equivalent point-in-time incident linkage
guarantees.

## 2026-06-26 - No-catalyst statements are absence evidence, not incident subjects
**Status:** accepted
**Decision:** Event Alpha claim semantics must treat phrases such as “no dated
external catalyst has been validated,” “no clear trigger,” “no known catalyst,”
and “without a known cause” as absence-of-validated-catalyst / unknown-cause
metadata. They must not create a `subject=No`, a confirmed
`explains_market_move` causal claim, or a generic incident that merges unrelated
market anomalies. Generic words such as `No`, `None`, `Unknown`, `Unclear`,
`Market`, `Catalyst`, `Event`, `Token`, and `Coin` cannot be canonical incident
subjects unless a resolver/entity context proves they are real named entities.
Market-anomaly incidents must key by asset identity, date bucket, and anomaly
type, and incident artifacts must distinguish observed market reaction from
confirmed causal mechanism.
**Why:** Absence-of-evidence language is common in anomaly copy. Treating “No”
as a subject or “no catalyst” as a confirmed cause makes artifacts misleading
and can merge unrelated anomalies into one false canonical incident.
**Revisit when:** A reviewed incident dataset supports a richer unknown-cause
taxonomy with separate but equally explicit absence-of-evidence fields.

## 2026-06-26 - Canonical incidents are first-class research artifacts
**Status:** accepted
**Decision:** Event Alpha canonical incidents must be persisted as
profile-scoped research artifacts (`event_incidents.jsonl`) and treated as the
shared context linking raw source evidence, claim history, cause status,
hypotheses, watchlist rows, alert snapshots, daily briefs, research cards, and
opportunity audits. Incident ids and incident confidence are audit metadata and
quality inputs; they do not create candidates, routes, paper rows, normal RSI
rows, trades, or `TRIGGERED_FADE`. Follow-up sources should update the same
incident when the subject/archetype/ecosystem/date match, and material changes
should be recorded as review reasons such as independent-source confirmation,
cause confirmed/ruled out, incident-confidence change, or affected-asset role
change. Market reaction must stay separate from causal mechanism confirmation.
**Why:** Without a durable incident layer, duplicate articles can fragment
source confidence, and a market move can be mistaken for proof of the claimed
cause. Operators need one auditable object that shows what happened, what was
claimed, what changed, and which assets are linked by role.
**Revisit when:** A later schema migration moves incident storage from JSONL
into a reviewed research database with equivalent point-in-time provenance.

## 2026-06-26 - Event Alpha claim semantics and incident roles are authoritative context
**Status:** accepted
**Decision:** Event Alpha impact validation must preserve event claim polarity,
cause status, canonical incident identity, and candidate role before treating a
source as an impact path. Confirmed causes, alleged/suspected causes,
negated/ruled-out causes, disputed/denied claims, and unknown-cause market
moves must remain distinguishable in artifacts and reports. A ruled-out or
unknown-cause exploit narrative must not be promoted as a confirmed
`exploit_security_event`; it should be stored as `market_dislocation_unknown`
or local review evidence unless later source evidence confirms the cause.
Third-party ecosystem incidents may classify a token as
`ecosystem_affected_asset`, but that must not be collapsed into
`direct_subject` unless the token/protocol itself is the incident subject.
Market reaction confirmation is useful evidence, but it does not by itself
prove causal mechanism confirmation.
**Why:** Public event sources often blend rumor, denial, publisher/source noise,
ecosystem exposure, and price movement. Without claim polarity and candidate
role, the radar can make a local-only market move look like a validated token
impact path.
**Revisit when:** A reviewed Event Alpha dataset proves a narrower or broader
role/claim policy has better precision for a specific playbook.

## 2026-06-25 - Event Alpha block reasons must name missing evidence
**Status:** accepted
**Decision:** Event Alpha `why_local_only`, `why_not_watchlist`,
`quality_gate_block_reason`, and `quality_state_block_reason` fields should
name the blocker or missing evidence, not positive evidence that happened to be
present. For example, strong market confirmation must remain positive score
context; it must not appear as the reason a row is local-only. Weak or
local-only rows should instead use reasons such as
`needs_strong_market_confirmation`, `weak_impact_path_despite_market_confirmation`,
`missing_direct_impact_path`, or `impact_path_not_strong_enough`. Legacy
artifacts with positive-sounding reasons may be normalized at read/report time
without rewriting the JSONL artifact.
**Why:** Operators and Pro-model reviews need to see what is missing before a
candidate can upgrade. Reusing positive evidence as a block reason makes the
quality gate look contradictory and obscures the manual verification path.
**Revisit when:** The artifact schema is migrated and old local-only reason
fields are retired.

## 2026-06-25 - Event Alpha quality verdicts must cap lifecycle state
**Status:** accepted
**Decision:** Event Alpha final signal-quality / opportunity verdicts are
authoritative over watchlist lifecycle state, not only notification routes.
Rows with final `local_only`, insufficient-data, source-noise/ticker-collision,
or zero-score verdicts must not remain active `WATCHLIST` or `HIGH_PRIORITY`
rows. They may be persisted as `QUALITY_BLOCKED` or other local/review-only
state with `requested_state_before_quality_gate`,
`final_state_after_quality_gate`, `state_quality_capped`, and
`quality_state_block_reason` for audit. Active watchlist reports, monitor
updates, router decisions, alert snapshots, daily briefs, research cards,
quality review, notification inbox, and artifact doctor checks must use the
final quality-capped state by default. Valid `watchlist` and `high_priority`
verdicts may still use active lifecycle states, and validated watchlist-quality
rows may continue through post-event monitoring states such as `EVENT_PASSED`
and `ARMED`. Deterministic `TRIGGERED_FADE` from `event_fade.py` plus
`proxy_fade` is preserved and remains the only trigger source.
**Why:** A row can have stale pre-quality watchlist state even after the final
quality verdict proves it is local-only or insufficient-data. Operator-facing
daily briefs and monitor/router paths must not promote stale lifecycle state
above the canonical quality verdict.
**Revisit when:** A reviewed Event Alpha dataset justifies a separately
approved lifecycle policy for a specific quality cohort.

## 2026-06-25 - Event Alpha routes must obey final quality verdicts
**Status:** accepted
**Decision:** Event Alpha routing must apply the final signal-quality /
opportunity verdict before any operator-facing route. Rows with final
`local_only`, `exploratory`, insufficient-data/source-noise/ticker-collision,
or zero-score verdicts stay in local/store-only or exploratory review output
even if the older watchlist/playbook path requested digest, watchlist,
high-priority, or instant routing. Alert snapshots, notification plans, routed
Telegram copy, inbox queues, and artifact doctors must treat the final route as
authoritative; requested pre-gate route/tier fields are audit metadata only.
Alert snapshots must persist both requested route/tier and final route/tier
after quality gate, plus alertable-after-quality-gate, block reason, and a
snapshot quality classification. Reports use final route/tier by default.
Quality-gated local/store-only rows may appear in explicit local-only review
sections, and legacy conflicts may appear in migration-review sections, but
they must not be counted as delivered or would-send digest items by default.
Fresh/current rows with alertable final routes that contradict `local_only`,
zero-score, or insufficient-data quality fields are artifact-doctor blockers.
The only exception is an already-deterministic `TRIGGERED_FADE_RESEARCH` route
from `event_fade.py` plus the `proxy_fade` playbook; LLMs, providers,
hypotheses, and quality metadata still cannot create `TRIGGERED_FADE`.
**Why:** Impact/watchlist state can be stale, broad, or pre-quality-layer. The
final opportunity verdict is the row-level safety contract that combines
impact path, evidence/source quality, market confirmation, and hard identity
guards. Operator-facing research messages must not outrank that verdict.
**Revisit when:** A reviewed Event Alpha dataset proves a specific lower-tier
opportunity class should have a separately approved exploratory or digest
route policy.

## 2026-06-25 - Fresh quality validation needs raw artifact coverage
**Status:** accepted
**Decision:** Live-style Event Alpha quality validation should use an isolated
`notify_llm_quality` profile/namespace and a raw-artifact coverage report that
checks the latest run's hypothesis, watchlist, and alert snapshot rows for
canonical top-level quality fields. Compatibility loaders may still fill missing
fields for backward-compatible reads, but they do not prove that fresh rows on
disk are complete. Namespaces with missing quality fields while
`quality_validation` is clean should warn that they may contain pre-quality-layer
artifacts and should be rerun.
**Why:** Operator review and Pro-model handoff need to distinguish stale
artifact gaps from current writer behavior. A loader-repaired report can make
old rows look healthy and hide the exact integration regressions this quality
layer is supposed to prevent.
**Revisit when:** All pre-quality-layer namespaces have been retired or the
artifact schema is versioned with an explicit migration marker.

## 2026-06-25 - Event Alpha quality fields must be canonical at top level
**Status:** accepted
**Decision:** Fresh Event Alpha hypothesis, watchlist, and alert snapshot rows
must carry the canonical signal-quality fields at the artifact row's top level:
impact path, candidate role, evidence quality, source class, market
confirmation, final opportunity score/level, verdict reasons,
local-only/watchlist blockers, manual verification items, and
upgrade/downgrade diagnostics. Nested `score_components` may preserve raw
inputs, but they must not be the only place fresh rows store quality verdicts.
If context is missing, writers must store conservative explicit
`insufficient_data` / `local_only` defaults and explain what needs validation.
Artifact doctor strict mode blocks fresh rows missing top-level quality fields;
legacy gaps are review warnings unless a future strict-legacy policy is added.
**Why:** Operator review, Pro-model analysis, artifact doctor, policy
simulation, and opportunity audits need one stable field contract. Letting
nested components mask top-level `None` values made quality artifacts appear
healthy while row-level consumers saw blank verdicts.
**Revisit when:** The artifact schema is versioned to a new canonical contract
and all readers/writers migrate together.

## 2026-06-25 - Event Alpha quality loops are artifact review, not promotion
**Status:** accepted
**Decision:** The Event Alpha quality review, policy simulation, artifact
doctor quality checks, proposed signal-quality case export, and
`event-alpha-quality-loop` Make targets are review tooling only. They may
enforce artifact completeness, explain missing evidence, simulate thresholds,
and export proposed fixture cases, but they must not mutate canonical
signal-quality fixtures automatically, send Telegram notifications, alter
router scoring, write normal RSI signal rows, open paper/live trades, or create
`TRIGGERED_FADE`.
**Why:** The owner needs a daily operational workbench for real artifacts while
the system is still in research burn-in. Review and simulation are useful only
if they cannot silently become production signal changes.
**Revisit when:** A human-reviewed dataset and outcomes justify a separate
approved change to promote a specific policy from simulation into routing.

## 2026-06-25 - Event Alpha signal quality is diagnostic and visibility-scoped
**Status:** accepted
**Decision:** Event Alpha signal-quality evaluation, opportunity audits,
upgrade/downgrade explanations, and
`RSI_EVENT_ALPHA_NOTIFICATION_QUALITY_MODE` are research workbench features.
They may explain candidates, group feedback/calibration cohorts, promote
validated hypothesis watchlist state for review metadata, and filter which
research notification lanes are visible to the operator. They must not alter
normal RSI alerts, write live signal/paper rows, open trades, or create
`TRIGGERED_FADE`; deterministic `event_fade.py` plus `proxy_fade` remains the
only `TRIGGERED_FADE` source.
**Why:** The radar needs a practical way to suppress low-quality exploratory
noise and audit candidate evidence without turning diagnostic scores into
execution or calibrated signal authority.
**Revisit when:** A reviewed Event Alpha sample plus outcomes show a
signal-quality cohort has stable enough edge to justify a separately approved
promotion path.

## 2026-06-25 - Event Alpha digests require final opportunity verdicts
**Status:** accepted
**Decision:** Validated Event Alpha hypotheses must carry a final opportunity
verdict before operator-facing digest promotion when that metadata is
available. The verdict combines impact-path strength, market confirmation,
source/evidence quality, timing, liquidity/tradability, and resolver/LLM
confidence. `local_only` and `exploratory` verdicts stay local even if a
catalyst link exists. `validated_digest` and `watchlist` verdicts may enter the
capped research digest, and `high_priority` verdicts may use the research
escalation lane. This verdict cannot create `TRIGGERED_FADE`, paper trades,
normal RSI signal rows, live DB writes, or execution.
**Why:** Impact-path validation answers “could this catalyst affect this
asset?” but not “is this worth operator attention today?” Market confirmation
and source quality need to be first-class gates so broad co-occurrence and weak
evidence stay local.
**Revisit when:** Reviewed Event Alpha feedback/outcomes show the final
verdict weights are too conservative or too permissive for a specific playbook.

## 2026-06-25 - Validated hypothesis digests require an explained impact path and v2 score
**Status:** accepted
**Decision:** Event Impact Hypothesis validation must classify the source's
impact path before a validated token-level `RADAR` hypothesis can enter the
capped daily research digest. The validator stores `impact_path_type`,
`candidate_role`, `impact_path_strength`, evidence specificity,
`digest_eligible_by_impact_path`, and `opportunity_score_v2`. Digest routing
requires validated token identity, catalyst-link validation or stronger, no
source-noise/ticker collision, a non-ambiguous playbook, old minimum score,
`RSI_EVENT_ALPHA_VALIDATED_HYPOTHESIS_MIN_OPPORTUNITY_SCORE`, and a strong
impact path or medium path with market confirmation. Generic co-occurrence is
blocked by default with `RSI_EVENT_ALPHA_BLOCK_GENERIC_COOCCURRENCE_DIGEST=1`.
Weak policy, macro, and broad technology rows remain local-only unless a future
reviewed sample justifies a different gate.
**Why:** “Token and catalyst appear in the same article” is not enough signal
quality for operator-facing research digests. The system must distinguish a
real value/liquidity/supply/security/proxy path from broad market commentary
before asking for feedback on a digest candidate.
**Revisit when:** Reviewed Event Alpha outcomes show that a currently weak
path class has repeatable usefulness after source quality, identity, and market
confirmation controls.

## 2026-06-24 - Validated impact hypotheses may enter capped daily research digest
**Status:** accepted
**Decision:** Token-level Event Impact Hypothesis rows must use validated asset
identity, not candidate order, when writing watchlist rows or digest context.
If validation lacks a concrete token identity, the row falls back to `SECTOR`
with a warning. A validated token-level `RADAR` hypothesis may enter a capped
daily research digest in notification profiles when
`RSI_EVENT_ALPHA_VALIDATED_HYPOTHESIS_DIGEST_ENABLED=1`, but only after the
validated-hypothesis digest quality gate passes: validated token identity,
`impact_path_validated` or stronger stage by default, no
source-noise/ticker-collision gate, score at least
`RSI_EVENT_ALPHA_VALIDATED_HYPOTHESIS_DIGEST_MIN_SCORE`, non-ambiguous playbook,
and either a known external catalyst or explicit direct token-event evidence.
Weak `catalyst_link_validated` rows that only show catalyst/token co-occurrence
remain local-only when
`RSI_EVENT_ALPHA_VALIDATED_HYPOTHESIS_REQUIRE_IMPACT_PATH=1` and
`RSI_EVENT_ALPHA_WEAK_VALIDATED_LOCAL_ONLY=1`. Bounded
`candidate_discovery` searches may suggest missing crypto candidates, but those
suggestions still require deterministic identity/catalyst validation and cannot
create alertability or `TRIGGERED_FADE`.
The message/card must label it as a research-only validated impact hypothesis,
not a trade signal or calibrated strategy. Delivered digest decisions are
persisted as Event Alpha alert snapshots so the notification inbox can request
useful/junk feedback without treating them as live signals; snapshots should
persist `symbol`/`coin_id` from validated identity when the route item does not
already have plain asset fields.
**Why:** Validated hypotheses are useful operator intelligence only if they
name the asset that was actually validated. Making them visible in the daily
research digest helps review them without promoting loose sector hypotheses or
turning them into trading signals.
**Revisit when:** A reviewed sample proves a specific impact-hypothesis
category deserves `WATCHLIST`/`HIGH_PRIORITY` escalation or calibrated outcome
tracking.

## 2026-06-24 - Send OpenAI-backed notification profiles on every clean run
**Status:** accepted
**Decision:** `notify_llm` and `notify_llm_deep` should use the same
operator-visible per-run delivery policy as `notify_no_key`: heartbeat,
exploratory, daily digest, and instant lane cooldowns are zero, and scheduled
content dedupe is disabled. The run lock, overlap guard, in-flight delivery
guard, Telegram send guard, and research-only copy remain active.
**Why:** The owner wants a Telegram notification every time the system runs.
The LLM profiles are operational notification profiles, so a successful run
should not be hidden by a prior exploratory digest cooldown.
**Revisit when:** Telegram volume becomes too noisy or a separate schedule
requires digest throttling for OpenAI-backed runs.

## 2026-06-24 - Use bounded parallel LLM calls inside notification deadlines
**Status:** accepted
**Decision:** OpenAI-backed Event Alpha raw-event extraction and relationship
analysis may run uncached provider calls concurrently through a bounded thread
pool, controlled by `RSI_EVENT_LLM_MAX_PARALLEL_CALLS`. Per-request HTTP
timeouts still apply, and the notification runtime deadline remains the outer
wall-clock guard; cache hits remain local/free, and uncached calls are skipped
once budget or runtime deadline is exhausted.
**Why:** Sequential LLM requests let one slow socket/read timeout stall all
later candidates. Bounded parallelism improves candidate coverage during daily
notification runs without removing cost caps, daily call caps, runtime limits,
or research-only safety boundaries.
**Revisit when:** The project moves LLM work into an async/background queue with
retryable job state, per-model token accounting, or adaptive provider failover.

## 2026-06-23 - Bound live LLM calls by notification runtime deadlines
**Status:** accepted
**Decision:** OpenAI-backed Event Alpha notification runs must pass the cycle's
runtime deadline into raw-event extraction and relationship analysis. LLM cache
hits may still be used after the deadline because they are local, but uncached
provider calls must skip with explicit runtime-deadline warnings once the
deadline is exhausted.
**Why:** Per-run/day/cost budgets control spend, not wall-clock delivery
reliability. A slow provider can otherwise keep a notification cycle inside the
LLM loop after the outer runtime budget has expired, delaying or preventing
heartbeat/exploratory delivery.
**Revisit when:** LLM calls move to an asynchronous queue with resumable
background processing and notification sends no longer wait on live model calls.

## 2026-06-23 - Let local LLM budget env vars override Event Alpha profile caps
**Status:** accepted
**Decision:** Event Alpha profiles still provide bounded defaults for OpenAI
relationship analysis and raw-event extraction, but local
`RSI_EVENT_LLM_*` budget variables for candidate/event selection, per-run calls,
per-day calls, estimated cost/day, estimated cost/call, and cache TTL may
override those profile budget caps at runtime.
**Why:** Operational LLM depth needs to be adjustable without code edits or
profile rewrites. The owner explicitly wants substantially higher LLM budgets
for daily notification runs, while preserving profile behavior for non-budget
settings.
**Revisit when:** Budget control moves to a dedicated operator config file or
the project adds model-specific token/cost accounting instead of per-call
estimates.

## 2026-06-23 - Treat impact-hypothesis reports as run-scoped diagnostics
**Status:** accepted
**Decision:** Event Impact Hypothesis artifacts may contain historical and
legacy rows, so operator reports must expose latest-run, run-id, since, and
legacy-aware filters, plus schema gaps, generated/executed query type counts,
rejected evidence samples, why-not-promoted diagnostics, and entity/candidate
audits. These fields are observability only. They explain why hypotheses did or
did not validate/promote, but they cannot promote rows, change routing, write
normal RSI signal rows, open paper/live trades, or create `TRIGGERED_FADE`.
**Why:** Without run-scoped diagnostics, old rows with missing fields can make
fresh `notify_llm` runs look broken and hide provider/search failure modes.
**Revisit when:** Hypothesis storage migrates to a versioned DB/table with
native run indexes and automatic retention.

## 2026-06-23 - Send notify_no_key research notifications on every clean run
**Status:** accepted
**Decision:** The `notify_no_key` Event Alpha notification profile should send
operator-facing research notifications on every clean run. Its notification
lane cooldowns are zero and content dedupe is disabled for that profile, while
the per-profile run lock and in-flight delivery guard remain active. This only
changes delivery frequency for day-1 research notifications; it does not alter
alert scoring, watchlist routing, normal RSI alerts, paper/live writes, trading,
or the rule that `TRIGGERED_FADE` only comes from deterministic `event_fade.py`
plus `proxy_fade`.
**Why:** The owner wants direct Telegram visibility whenever the Event Alpha
system runs, including no-alert/degraded heartbeat runs and exploratory digest
rows for manual review.
**Revisit when:** Notification volume becomes noisy enough to require
per-lane cooldowns again, or when `notify_no_key` is replaced by a calibrated
research-send profile.

## 2026-06-23 - Separate external catalysts from crypto candidate assets in impact hypotheses
**Status:** accepted
**Decision:** Event Alpha impact hypotheses must store external entities,
crypto candidate assets, and rejected candidate assets separately. External
companies or events such as OpenAI, Anthropic, SpaceX, Stripe, Databricks,
Figma, elections, or sports fixtures are catalyst context, not crypto
`candidate_symbols`. Sector-level hypotheses may generate
`candidate_discovery` queries even without named assets, but token-level
watchlist promotion requires catalyst-linked candidate validation
(`catalyst_link_validated`, `market_confirmed`, or `promoted_to_radar`).
Candidate-discovery results may suggest crypto candidates for later validation,
but those suggestions stay below promotion until deterministic identity evidence
and catalyst linkage validate the candidate. Reports should expose
`why_not_promoted` reasons so discovery-only evidence is auditable.
Candidate-only evidence can reach `source_mentions_candidate`; identity-only
evidence can reach `identity_validated`; catalyst-only evidence is rejection/no
candidate validation. Reports may persist capped rejected validation samples for
audit, but those samples cannot create alerts or triggers.
**Why:** External catalyst intelligence is useful, but mixing external
companies with crypto candidates makes the radar appear more certain than the
evidence supports and can reintroduce false positives.
**Revisit when:** A reviewed burn-in sample proves a category-specific policy
can safely promote named assets before explicit catalyst-linked validation.

## 2026-06-23 - Store impact hypotheses as audit artifacts, not alert eligibility
**Status:** accepted
**Decision:** Event Alpha impact hypotheses are persisted as profile-scoped
JSONL research artifacts (`event_impact_hypotheses.jsonl`) with run/profile/
namespace metadata, candidate provenance, validation status, search queries,
validation/rejection reasons, flattened validated symbol/coin-id fields, and
promoted watchlist keys when validation links a hypothesis to a watchlist row.
Rows also carry schema-auditable fields (`validation_stage`,
`hypothesis_score`, `external_entities`, `crypto_candidate_assets`) plus
diagnostic `why_not_promoted` reason codes so legacy/missing fields and blocked
promotion causes are visible in reports/briefs.
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
routing. Multi-feed RSS `feed_failure` rows are soft provider-health warnings
when at least one configured feed still returns usable rows; provider-level
failures and upstream rate limits such as GDELT `429` remain eligible for
circuit-breaker backoff.
**Why:** Operators need to distinguish “nothing interesting found” from “search
was skipped or blocked” without letting provider/error metadata become signal
logic. A single public feed returning 403 should not disable the rest of an RSS
bundle, but true provider/rate-limit failures should still protect daily runs
from repeated stalls.
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
**Status:** superseded
**Superseded by:** `2026-07-12 - Keep feedback calibration priors shadow-only`.
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
