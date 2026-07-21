# Robust Temporal Surprise Shadow — Research Contract

Status: shadow-only, research-only, not a trade signal, and not eligible to
change a route, priority, Decision score, threshold, alert, or execution state.

## Why this exists

The current temporal volume and turnover z-scores use an arithmetic mean and
population standard deviation. Those statistics remain the canonical runtime
features, but crypto activity series are positive, strongly skewed, and prone
to isolated extreme observations. A single historical spike can materially
move both the mean and standard deviation and make a later unusual observation
look ordinary.

The shadow metric is a comparison feature, not a replacement. It lets the
outcome loop measure whether a robust view separates useful anomalies from
noise before any threshold or routing proposal is considered.

## Fixed v1 activity method

The eligible feature set is deliberately narrow:

- `volume_24h` with provider-observed basis;
- `turnover_24h` with provider-observed basis or an explicit
  `derived_provider_ratio` based on provider-observed volume and market cap.

An explicit derived-ratio label is not sufficient by itself: turnover must
match `volume_24h / market_cap` within relative tolerance `1e-9` and absolute
tolerance `1e-12`. An independently supplied turnover defaults to
`provider_observed`; only a value actually calculated from provider volume and
market cap defaults to `derived_provider_ratio`.

Proxy and cross-sectional bases are excluded. Current and baseline values must
be finite and strictly positive. The baseline uses only cadence-counted,
strictly earlier observations for the same canonical asset; the current row
never enters its own baseline.

For each feature:

1. Apply the natural logarithm to the current and eligible baseline values.
2. Use the baseline median as location.
3. Use the median absolute deviation around that median as robust scale.
4. Multiply MAD by `1.482602218505602` for the conventional normal-consistency
   scale, then calculate the signed robust z-score.
5. If MAD is at most `1e-12`, return no robust z-score. Do not add epsilon and do
   not fall back to standard deviation.
6. Record the descriptive upper-tail rank
   `(count(baseline_log >= current_log) + 1) / (n + 1)`.

The upper-tail rank is explicitly not a p-value. The observations are a rolling,
overlapping market series rather than exchangeable Monte Carlo draws, so the
value is only a bounded descriptive rank. The add-one form prevents a finite
history from reporting impossible zero tail mass.

The log transformation is a fixed, transparent monotone transform rather than
a fitted distributional claim. Box and Cox describe the broader transformation
family and its variance/modeling motivation: [Box and Cox (1964), *An Analysis
of Transformations*](https://doi.org/10.1111/j.2517-6161.1964.tb00553.x).
Robust median-based scale estimation is grounded in the MAD literature:
[Rousseeuw and Croux (1993), *Alternatives to the Median Absolute
Deviation*](https://doi.org/10.1080/01621459.1993.10476408). The finite-sample
add-one shape is informed by [North, Curtis, and Sham (2002), *A Note on the
Calculation of Empirical P Values from Monte Carlo
Procedures*](https://doi.org/10.1086/341527), while this implementation avoids
calling its non-exchangeable rolling rank a significance test.

## Fixed v2 signed-return extension

Schema v2 keeps the v1 activity fields unchanged and adds nine independent
return families:

- direct `return_1h`, `return_4h`, and `return_24h`;
- `relative_return_vs_btc_{1h,4h,24h}`;
- `relative_return_vs_eth_{1h,4h,24h}`.

Each family is calculated separately. A value cannot cross a horizon,
benchmark, unit, or feature-basis boundary. Historical schema-v1 activity
values remain readable; they are not silently reinterpreted as v2 return
evidence.

The return contract is fixed as follows:

1. Use positive finite prices whose explicit basis is `provider_observed`.
   Proxy, cross-sectional, interpolated, bar-derived, or unknown price bases are
   ineligible.
2. Express each return in percentage points as
   `(endpoint_price / anchor_price - 1) * 100`. Keep the identity transform so
   downside remains negative.
3. For each endpoint, choose the latest observation at or before the exact
   horizon target. It must be within the larger of five minutes or 25% of that
   horizon. Never choose a future anchor.
4. For a relative return, require the canonical BTC identity (`bitcoin` or
   `btc`) or ETH identity (`ethereum` or `eth`). Choose the benchmark endpoint
   at or before the asset endpoint and within five minutes, build its own causal
   horizon return, then subtract benchmark return from asset return. A BTC/ETH
   asset compared with itself is explicitly `not_applicable`.
5. Build the baseline only from strictly earlier, cadence-counted asset
   endpoints. Every baseline return retains its exact endpoint/anchor prices in
   the sample digest; the current sample projects all endpoint/anchor
   observation references.
6. Use the baseline median and median absolute deviation multiplied by
   `1.482602218505602`. MAD at or below `1e-12` produces no robust z-score and
   no fallback.
7. Record add-one lower and upper descriptive ranks and
   `min(1, 2 * min(lower_rank, upper_rank))` as the two-sided descriptive rank.

All three ranks preserve the direction through the signed return and separate
lower/upper fields. They are not p-values. Rolling horizon samples overlap and
are explicitly not claimed to be statistically independent. V2 sets no anomaly
threshold and does not promote any route or score.

## Fixed v3 baseline-variation diagnostics

Schema v3 leaves every v1 activity calculation and v2 signed-return calculation
unchanged. It adds descriptive reference-set diagnostics so a nominal baseline
count cannot be confused with the number of distinct observed values. Historical
v1 and v2 values remain readable and are not silently reinterpreted.

For each activity and return family, v3 records:

- the distinct baseline-value count;
- the largest exact baseline tie count;
- the number of baseline values tied with the current value, when a current
  evaluation value exists;
- the distinct-count-to-sample-count ratio;
- the nominal add-one one-sided rank floor `1 / (n + 1)`; and
- for return families, the nominal two-sided rank floor
  `min(1, 2 / (n + 1))`.

Tie identity uses the feature evaluation value rounded to the existing 12
decimal places: log-transformed activity values and derived percent-point
returns respectively. The robust z-score, MAD, and empirical ranks continue to
use their existing v1/v2 calculations. There is no minimum-distinct threshold,
no effective-sample-size claim, and no status, route, score, threshold, or
publication effect. The nominal rank floor is a finite-sample resolution
description, not a claim that tied values can attain that floor and not a
p-value.

## Fixed v4 retained-input trace

Schema v4 leaves every v1 activity, v2 signed-return, and v3 baseline-variation
calculation unchanged. It adds a value-only trace that distinguishes repetition
already present in exact retained numeric inputs from distinct input tuples
that collapse to the same 12-decimal derived evaluation value. Historical v1,
v2, and v3 values remain readable and are not silently upgraded.

The feature-specific source tuple is deliberately closed:

- volume binds the exact retained provider volume value and basis;
- turnover binds the derived turnover plus its exact retained volume and market-
  cap components and bases;
- a direct return binds the asset endpoint and anchor prices and bases; and
- a relative return additionally binds benchmark endpoint and anchor prices and
  bases.

Observation IDs and clocks remain bound by the existing eligible-sample digest,
but are excluded from this value-only tuple. Otherwise every observation would
look distinct and the diagnostic could not detect repeated inputs. Each feature
records tuple count, distinct tuple count, largest tuple tie, a SHA-256 of the
ordered tuple sequence, source and derived repetition excess, transform-
collision distinct-value loss, and maximum consecutive source/derived runs.
The accounting identities are exact:

- source repetition excess = sample count - distinct source tuples;
- derived repetition excess = sample count - distinct derived values; and
- transform-collision loss = distinct source tuples - distinct derived values.

The closed status is `all_distinct`, `source_tuple_repetition`,
`transform_collision`, `mixed_source_repetition_and_transform_collision`, or
`no_samples`. These labels describe algebra only. They do not attribute a fault
to a provider, estimate effective sample size, classify or exclude an asset, or
change status, robust z-score, rank, threshold, route, score, publication, or
Protocol-v2 evidence eligibility.

## Fixed v5 return-sampling timing trace

Schema v5 preserves every v1 activity, v2 signed-return, v3 variation, and v4
value-only input-trace result byte-for-byte at the feature-calculation level. It
adds a separate observation-identity trace for return sampling. Historical v1
through v4 projections remain readable and are never silently reinterpreted.

For each direct-return sample, the trace binds the exact asset endpoint and the
at-or-before anchor selected for the requested 1h, 4h, or 24h horizon. Relative
returns also bind the exact benchmark endpoint and benchmark anchor. The closed
trace records:

- distinct endpoint and anchor observation counts, reuse excess, maximum reuse,
  and maximum consecutive reuse;
- realized horizon seconds and nonnegative anchor-selection error as
  minimum/median/maximum distributions;
- asset-to-benchmark endpoint-alignment lag for relative returns; and
- exact observation references for maximum reuse, horizon error, and alignment
  lag, plus a digest of the ordered sampling identities.

This identity is deliberately separate from the v4 value-only tuple. Two samples
can reuse one causal anchor while carrying different endpoint prices, and two
different observations can carry an identical numeric price tuple. Reporting
both prevents either condition from being mistaken for the other. A zero error
means the selected anchor landed exactly on the nominal horizon; a positive
error records the realized at-or-before distance already admitted by the fixed
anchor tolerance. No negative/future distance is accepted.

These timing fields are descriptive only. They do not estimate independent
sample size, attribute provider fault, set a reuse or timing threshold, exclude
an asset, or change a status, robust z-score, rank, route, score, publication,
or Protocol-v2 eligibility.

## Fixed v6 return-interval overlap trace

Schema v6 preserves every v1-v5 calculation and sampling-timing field, then
closes the exact time interval implied by each endpoint/anchor pair. Historical
v1 through v5 projections remain readable without manufactured overlap fields.
Each direct asset leg and each separate benchmark leg records:

- ordered half-open `[anchor, endpoint)` interval identity and SHA-256;
- exact interval distinctness, reuse excess, maximum reuse, and consecutive
  reuse;
- adjacent endpoint-ordered pair count, overlapping/nonoverlapping counts, and
  overlap seconds as minimum/median/maximum;
- summed interval seconds, union clock-coverage seconds, overlap-excess seconds,
  and union-to-summed-duration ratio; and
- exact maximum interval-reuse and adjacent-overlap references.

Union coverage measures clock time represented at least once; overlap excess is
the summed interval duration minus that union. Neither is an estimate of
independent information. The trace explicitly records that it is not policy,
does not estimate effective sample size, and does not adjust sample weights.
Direct, BTC-relative, and ETH-relative families stay separate and no return,
status, threshold, route, score, publication, or Protocol-v2 rule changes.

## Campaign-level causal replay

The canonical live campaign report replays this same closed v6 evaluator over
the exact retained market-history snapshot it has already read. It does not
create another model or reinterpret stored rows. Only rows carrying
`baseline_counted=true` enter the replay; rapid non-counted rows are excluded
with an exact count, while malformed identities, clocks, counting flags, and
duplicate observation or asset-time identities are rejected with closed reason
counts.

Every accepted observation is evaluated against strictly earlier observations
for the same canonical asset. BTC and ETH context is restricted to canonical
benchmark rows at or before that observation's clock. The report retains
per-feature ready/status/sample coverage, per-asset summaries, input and
evaluation accounting, and two complementary digests:

- the source-bound digest changes when the exact history snapshot fingerprint
  changes, even if an older projection's causal inputs did not;
- the causal-value digest removes only that whole-snapshot hash, so an older
  projection remains byte-comparable when later observations are appended.

Campaign-audit schema v3 aggregates the closed per-observation variation
diagnostics for each feature. Its distribution population includes projections
whose baseline count meets the model's existing nominal sample minimum,
including degenerate-scale projections; it excludes earlier warm-up rows so a
one-sample reference set cannot dominate the tie-share maximum. The audit
reports distinct-count, distinct-ratio, and largest-tie-ratio distributions,
plus exact observation identities and counts for the least-diverse and
highest-tie-share reference sets.

Campaign-audit schema v4 adds bounded per-asset/per-feature persistence without
changing those distributions. For each evaluated canonical asset, it records
how many sample-eligible projections contain repeated baseline values, the
distinct/tie distribution and latest exact reference set, and retained symbol,
provider, data-mode, and feature-basis counts. Those source fields describe the
rows in the retained context; they do not prove why a value repeated. The
dashboard ranks exact repeated asset-feature pairs only for review, with no
minimum ratio, classification, exclusion, or outcome use. Historical campaign-
audit schemas v1 through v3 remain readable without manufacturing fields they
never recorded.

Campaign-audit schema v5 preserves those v4 distributions and persistence
records, then aggregates the v4 retained-input trace per asset and feature. It
reports how many eligible projections contain source-tuple repetition,
transform collision, or both; source-tuple kinds; maximum repeat/collision
losses; maximum consecutive source/derived runs; and the latest exact trace
reference and digest. Historical campaign-audit schemas v1 through v4 remain
readable without manufacturing trace fields. Dashboard and Markdown views show
the source-repeat and transform counts separately and explicitly make no
provider-causation claim.

Campaign-audit schema v6 preserves the complete v5 input-lineage projection and
adds a per-asset/per-return-feature summary of the v5 sampling trace. It counts
eligible projections with asset-anchor, benchmark-endpoint, or benchmark-anchor
reuse; counts nonzero horizon error and benchmark-alignment lag; retains maximum
reuse/run/error values; and preserves the exact maximum observation references
and source sampling references. Activity features carry an explicit null timing
summary because they do not use horizon anchors. Historical campaign-audit
schemas v1 through v5 remain readable without manufacturing timing evidence.
Dashboard and Markdown views keep numeric value repetition, observation reuse,
and realized timing error visibly separate. The summary is not policy, provider
causation, or an independence claim.

Campaign-audit schema v7 preserves v6 and adds separate asset-leg and benchmark-
leg interval summaries for every sample-eligible return family. It reports how
many reference sets have adjacent overlap or exact interval reuse, distributions
of unique-clock-coverage ratios, maximum adjacent overlap and aggregate overlap
excess, exact extreme observations, and a closed projection digest. Historical
campaign-audit schemas v1 through v6 remain readable without manufacturing
overlap evidence. The dashboard and Markdown report show this as dependence
diagnostics, never as an effective-sample-size estimate or sample weight.

The 59-cycle genuine campaign replay contains 279 sample-eligible asset/return-
feature pairs and 8,262 asset-leg reference sets. Adjacent overlap appears in
185 pairs and 5,214 reference sets, while exact full-interval reuse is zero.
The 184 relative-return benchmark pairs contain 5,442 reference sets; 122 pairs
and 3,434 sets overlap, again with zero exact full-interval reuse. Every eligible
1h set has union coverage ratio `1.0` and zero adjacent overlap. The 4h families
reach a minimum ratio of `0.456072623081`; 24h reaches
`0.126292698333` for `figure-heloc`. The largest observed adjacent overlap is
`101650.31433` seconds and the largest summed overlap excess is
`2691040.565484` seconds, both retained with exact `aave` references. Zero exact
interval reuse therefore does not imply independence: distinct rolling windows
can still share most of their clock span.

These aggregates are reference-set diagnostics, not an effective-sample-size
estimate. They set no minimum-distinct threshold, do not alter feature status,
and are copied into the campaign report and dashboard without re-evaluation.

An audit status of `ready` means each modeled feature has at least one ready
projection. It does not claim that every observation is ready, that rolling
rows are independent, or that the values qualify as Protocol-v2 evidence. The
report remains read-only, performs no provider call, rewrites no historical
row, and cannot change routes, priorities, scores, thresholds, publication, or
authority.

## Isolation and integrity contract

- Compute from the exact fingerprinted generation history snapshot only after
  the market scanner has classified, bucketed, prioritized, sorted, and
  truncated anomalies.
- Verify the history bytes against the generation's expected SHA-256 before
  parsing, and persist the safe artifact basename plus digest inside the closed
  shadow value.
- Bind enrichment reads and the complete scanner-bundle rewrite to the original
  scan namespace device/inode and unchanged input hashes; a directory or leaf
  swap fails before a substituted target can be mutated.
- Attach the result only as top-level diagnostic metadata on the post-scan
  market snapshot and anomaly artifacts.
- Never place it inside `market_state_snapshot`; snapshot-selection code uses
  structural completeness and an extra nested field could alter downstream
  selection.
- Do not write it into the provider source cache or canonical retained history.
- Do not copy it into integrated candidates, the canonical Decision v2
  projection, CoreOpportunity, cards, notifications, or execution surfaces.
- Schema validation rejects the field recursively on every non-market-evidence
  artifact and anywhere below the raw market snapshot/anomaly top level.
- Persist explicit `routing_eligible=false`, `priority_eligible=false`,
  `decision_score_eligible=false`, `score_adjustment_eligible=false`,
  `auto_apply=false`, and `research_only=true` fields.
- Missing, insufficient, unsupported-basis, or degenerate data remains an
  explicit status rather than an inferred zero.

## Known limitations

- Consecutive `volume_24h` observations and rolling return horizons overlap
  heavily and are autocorrelated.
- Crypto activity has intraday/weekly seasonality and provider-regime changes.
- MAD can be zero in short or quantized histories.
- A robust z-score is not calibrated probability and does not establish a
  catalyst or direction.
- An extreme activity upper-tail or return two-sided rank can be a data-quality
  event, wash activity, broad market move, or venue migration.

These limitations are why v6 remains shadow-only.

## Evidence required before promotion is even proposed

- Compare robust and canonical features on matured Decision outcomes and
  matched non-idea controls.
- Evaluate at anomaly-episode level so repeated observations of one move do not
  inflate sample size.
- Report coverage, degenerate-scale rate, provider/basis cohorts, precision,
  recall, false-positive rate, calibration, and confidence intervals.
- Freeze all runtime thresholds until a separate reviewed decision accepts a
  specific, versioned promotion with rollback criteria.
