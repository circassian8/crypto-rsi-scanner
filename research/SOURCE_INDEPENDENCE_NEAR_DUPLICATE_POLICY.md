# Source Independence and Near-Duplicate Evidence Policy

Status: accepted research-only measurement policy

Contract: `event_alpha.source_independence` v1

Reference: Simon Rodier and Dave Carter, [Online Near-Duplicate Detection of News Articles](https://aclanthology.org/2020.lrec-1.156/), LREC 2020, pp. 1242–1249.

## Purpose

Crypto Decision Radar must not treat several copies of one article as several
independent confirmations. News syndication, lightly edited wire stories,
mirrors, and repeated provider rows can inflate apparent evidence without
adding a new observation. The source-independence contract measures that
specific problem before corroboration counts are used in research review.

This contract measures document-content and origin independence only. It does
not decide whether a publisher is authoritative, whether a claim is true,
whether an asset identity or impact path is valid, or whether an article
caused a market move. Those remain separate, closed checks.

## Counting vocabulary

- A **raw document** is one supplied source row. Repeated rows remain visible
  in `raw_document_count`; ingestion volume is not evidence independence.
- A **domain/origin** is the canonical HTTP(S) hostname after lowercasing,
  removing a trailing dot, and removing one leading `www.`. Distinct domains
  describe origin diversity, not truth, ownership independence, or content
  independence.
- A **content cluster** contains one representative document plus exact or
  near-duplicate documents assigned to that representative. One cluster is one
  content unit even when its copies appear on several domains.
- An **independent evidence unit** is a corroboration-eligible content cluster
  selected by the closed v1 origin rule. The first selected unit establishes
  the base evidence; each later unit must introduce at least one canonical
  origin not already represented by selected units.
- An **independent corroboration** is an independent evidence unit after the
  first. Therefore `independent_corroboration_count` is
  `max(0, independent_evidence_count - 1)`.
- An **additional corroboration** is useful content-distinct context that does
  not satisfy the independent-unit rule—for example, another article from an
  already represented origin. It may remain visible, but it must not increment
  the independent-corroboration count.

These are deliberately different quantities. Five raw rows can mean five
documents, one domain, one content cluster, one independent evidence unit, and
zero independent corroborations.

## Closed normalization and similarity rule

The v1 comparison surface is exactly normalized title, a newline, and
normalized body when both are present. Each input is normalized with Unicode
NFKC, Unicode casefolding, replacement of every non-alphanumeric character
with whitespace, whitespace collapse, and trim. The exact-content identity is
SHA-256 of that normalized title/body surface.

For assessable non-exact content, the contract:

1. tokenizes the normalized surface on whitespace;
2. creates the set of consecutive three-word shingles;
3. computes set Jaccard similarity, intersection size divided by union size;
4. marks the document near-duplicate when similarity to an existing canonical
   representative is at least `0.80`.

Documents shorter than 12 normalized tokens are too short for the near-
duplicate comparison and remain unassessable rather than being guessed
independent. The threshold, shingle size, normalization version, ordering, and
bounds are persisted inside the closed contract.

Rodier and Carter demonstrate why shingling is useful for online
near-duplicate news detection and why redundant news copies can bias corpora
and waste analyst effort. This implementation is intentionally stricter than
the paper's general method where operator truth benefits from conservatism: it
uses a fixed high `0.80` full-set Jaccard threshold, requires a canonical origin
and assessable content before corroboration eligibility, retains rejected and
unassessable rows explicitly, and never interprets the result as source
authority or causal truth. These project choices are policy constraints, not
claims that the paper prescribes the same threshold or evidence semantics.

## Representative-only, non-transitive clustering

Documents are processed deterministically by public time, source id, and
document id. A new document is compared only with existing canonical cluster
representatives. It is not compared with every member and cannot enter a
cluster solely through a chain such as A similar to B and B similar to C when C
is below `0.80` against representative A.

This non-transitive rule prevents near-duplicate chaining from gradually
joining materially different stories. If several representatives meet the
threshold, the deterministic best representative is used. Exact normalized
content always joins its exact-content cluster.

## Fail-closed input and bound policy

- At most 128 documents are accepted per assessment.
- Source ids, metadata, URLs, titles, bodies, normalized text, and shingle sets
  have explicit fixed bounds. Exceeding a bound rejects the affected document
  or the assessment; the value is not truncated into apparent evidence.
- Missing or malformed URLs cannot create a canonical origin.
- Missing title/body content, content below the minimum comparison length, or
  missing origin is unassessable and cannot become a corroboration-eligible
  cluster.
- Malformed clocks, unsafe URLs, invalid types, overflow, or shingle-bound
  violations remain explicit rejected evidence.
- Missing source ids receive deterministic derived ids with recorded input
  digests; derivation does not confer source quality.
- Every supplied field's bounded status and digest, every document/cluster
  assignment, count closure, sorted reason codes, and the complete contract
  digest are revalidated. Unknown keys or semantic/digest drift fail closed.

Missing evidence never means evidence of absence. An unassessable document is
not an independent source, and it is not silently discarded from telemetry.

## What this policy does not prove

`distinct_origin_count`, `content_cluster_count`, and
`independent_evidence_count` do not establish any of the following:

- publisher ownership independence or absence of syndication;
- source authority, reliability, accuracy, or firsthand reporting;
- claim agreement, factual truth, or absence of coordinated reporting;
- token identity, candidate role, impact-path validity, or catalyst timing;
- causal attribution between an event and a market anomaly;
- statistical independence of ideas, episodes, assets, or outcomes.

The contract therefore persists `authority_assessed=false` and
`research_only=true`. Source authority and temporal-semantic catalyst
attribution must be evaluated independently. Contradictory independent sources
remain independent documents; independence does not turn contradiction into
confirmation.

## Runtime and safety boundary

This measurement may replace prior raw-row or hostname counts wherever those
counts were already used as evidence-diversity inputs. That replacement can
remove a duplicate-derived bonus or fail a previously inflated corroboration
gate. It cannot add a new kind of positive promotion by itself.

Without a separate versioned policy, this measurement cannot:

- raise catalyst status, confidence, actionability, urgency, or priority beyond
  the existing corroboration semantics it replaces;
- lower a hard blocker or evidence threshold;
- change Decision-v2 or legacy Event Alpha routing;
- authorize a provider call, notification, live trade, paper trade, order, or
  execution venue;
- write normal RSI rows or create Event Alpha `TRIGGERED_FADE`;
- update dashboard publication authority or apply calibration automatically.

Any new positive promotion, threshold change, or calibration effect beyond the
accepted one-for-one replacement of legacy raw-row/hostname diversity inputs
requires a separate versioned decision backed by outcome evidence, frozen
thresholds, false-positive review, dependency-aware uncertainty,
out-of-sample validation, and rollback criteria. The current replacement is
auditable research metadata and may only remove duplicate-derived support from
the existing semantics it replaces.

## Immutable storage and historical compatibility

New contracts are stored once per artifact namespace as immutable canonical
JSON under `event_source_independence_contracts/`. Downstream rows carry a
closed reference with the semantic contract digest, exact blob fingerprint and
size, canonical relative path, validation state, and the bounded count summary.
Readers must verify the complete reference, anchored blob bytes, canonical JSON,
semantic digest, and every summary count before treating it as evidence.

Historical inline contracts remain valid input and are not rewritten merely
because a downstream artifact is normalized or linked to a card. Rewrites
prepare and validate the complete replacement before atomic publication; a
missing, mutated, symlinked, or unsafe store cannot truncate the old artifact.
The read-only storage report is:

```bash
make event-alpha-source-independence-storage-report \
  ARTIFACT_NAMESPACE=<exact-namespace> PYTHON=python3
```

It reports raw bytes, immutable-store growth, bounded resolve performance,
payload-only compatibility estimates, and an exact deterministic in-memory ZIP
comparison for the selected namespace. That ZIP comparison is not described as
the size of the whole project export.

## Frozen out-of-sample review workflow

The labeling contract freezes `development`, `review`, and `test` partitions
by `event_copy_family_id`, not by individual row. Every exact story/copy family
therefore remains indivisible. Validation rejects a family id, exact source
digest, or exact normalized-content digest that appears across partitions.
This prevents a syndicated story seen during development from reappearing as a
nominally out-of-sample test row.

The closed review categories are exact syndicated copy, lightly edited
cross-domain copy, independently reported same-event article, same-domain
original update, contradiction, short headline, and control. Reports separate
precision, recall, false merges, and missed copies across the frozen partitions
and by text length, source type, and provider pair. A structurally valid but
unlabeled review is `pending`; a fully labeled review without sufficient OOS
coverage is `incomplete`; only complete independent coverage is `complete`.
Validation of a structurally sound pending template still exits non-zero so an
unreviewed corpus cannot be mistaken for a finished gate. Persisted metrics
fail closed on boolean schema versions, unknown splits/categories, ratio drift,
or any review/confusion/cohort count mismatch.

```bash
make event-alpha-source-independence-oos-export \
  SOURCE_INDEPENDENCE_OOS_INPUT=<input.jsonl> \
  SOURCE_INDEPENDENCE_OOS_CORPUS=<frozen-corpus.jsonl> \
  SOURCE_INDEPENDENCE_OOS_TEMPLATE=<review-template.jsonl> \
  SOURCE_INDEPENDENCE_OOS_SPLIT_SALT=<operator-kept-frozen-salt>

make event-alpha-source-independence-oos-validate \
  SOURCE_INDEPENDENCE_OOS_CORPUS=<frozen-corpus.jsonl> \
  SOURCE_INDEPENDENCE_OOS_REVIEWS=<reviewed-labels.jsonl>

make event-alpha-source-independence-oos-report \
  SOURCE_INDEPENDENCE_OOS_CORPUS=<frozen-corpus.jsonl> \
  SOURCE_INDEPENDENCE_OOS_REVIEWS=<reviewed-labels.jsonl>
```

These commands make no provider call and do not alter the `0.80` Jaccard
threshold, 12-token minimum, normalization, scores, or routes. A policy change
still requires enough independent labels and explicit human approval.
