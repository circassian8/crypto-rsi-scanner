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
