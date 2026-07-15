# Anomaly Episode Shadow — Research Contract

Status: shadow-only, research-only, descriptive measurement. This contract is
not a trade signal and cannot change a route, priority, Decision score,
threshold, notification, publication authority, or execution state.

## Why an episode unit is needed

The market anomaly scanner can observe the same persistent move in successive
campaign generations. Its canonical detector uses rolling 4-hour and 24-hour
features, while outcome rows are also evaluated over overlapping horizons.
Treating every repeated observation as an independent performance sample would
therefore inflate the apparent evidence base.

The shadow episode is a conservative descriptive unit. It does not rewrite the
canonical candidate or outcome ledgers, and it does not claim that episodes are
statistically independent.

## Fixed v1 method

The source population is limited to exact market-anomaly candidates from
already validated, campaign-counted real/no-send generations. Candidate
authority, canonical asset identity, namespace, run, observation time,
candidate id, market-anomaly id, and canonical outcome identity remain exact.
Symbol fallback and cross-asset grouping are forbidden.

Each generation's candidate JSONL is captured once, checked against its
manifest or legacy operator-state SHA-256, and reused by campaign headline and
episode calculations. The mutable campaign outcome ledger is likewise read
once as exact bytes and reused everywhere. Its state is explicitly `missing`,
`observed_empty`, `observed`, or `unavailable`; absence is never reported as an
observed empty ledger. A separate closed v1 input audit binds candidate
snapshots, ledger SHA-256, all count closures, rejection and join truth, episode
digests, and zero-side-effect constants.

For each canonical asset and each predeclared window:

1. Sort observations by normalized UTC time and immutable exact identity.
2. The earliest unassigned observation becomes the representative and fixes
   the episode start.
3. Add later observations only while
   `member_observed_at < episode_start + window`.
4. A member exactly at the boundary starts a new episode.
5. Repeated members never slide or extend the fixed episode end.
6. Select the first representative solely from exact identity and time,
   independently of outcome availability, maturity, route, score, or return. A
   later matured row can never replace it.

The primary descriptive window is 24 hours because 24 hours is the longest
rolling return horizon in the canonical anomaly classifier. Parallel 12-hour
and 48-hour partitions are sensitivity views. They are recomputed from the
same exact member set and are never summed as additional samples. Parameters
are fixed before looking at outcomes.

Examples for the 24-hour view:

- observations at `0h` and `24h - 1 microsecond` form one episode;
- observations at `0h` and exactly `24h` form two episodes;
- observations at `0h`, `23h`, and `46h` form two episodes because the `23h`
  repeat does not slide the first window.

## Evidence and integrity contract

- Episode membership is formed from structurally valid counted anomaly
  observations before optional outcome evidence is assessed.
- Input readiness (`empty`, `ready`, `partial`, or `unavailable`) remains
  separate from structural episode readiness and outcome-evidence readiness.
- Exact raw outcome multiplicity is inspected before the campaign's legacy
  outcome-deduplication view. Missing, invalid, duplicate, conflicting, or
  colliding outcome evidence remains explicit and cannot select a different
  representative. A raw row claimed by multiple candidates is one explicit
  cross-candidate collision component; it is never multiplied into one fake
  duplicate group per claimant.
- Episode ids and membership digests bind only immutable source identity and
  time. Route, anomaly label, direction, maturity, score, and return changes do
  not alter membership.
- Member and exclusion references are complete within fixed 256-row bounds, so
  the validator recomputes every identity, partition, status count, and digest.
  Exceeding a bound fails closed without producing a contract.
- The 12/24/48-hour episode and repeat counts reconcile to one source member
  set and must remain monotonic as the window grows.
- The value persists `routing_eligible=false`, `priority_eligible=false`,
  `decision_score_eligible=false`, `score_adjustment_eligible=false`,
  `calibration_eligible=false`, `threshold_change_eligible=false`,
  `auto_apply=false`, `statistical_independence_claim=false`,
  `cross_asset_independence_claim=false`, and `research_only=true`.
- No provider is called and no generation, candidate, Core row, outcome,
  pointer, operator state, dashboard authority, or runtime configuration is
  mutated.

## Research basis

Ferro and Segers show that extremes in a time series occur in clusters and that
the declustering scheme can materially affect cluster estimates:
[Ferro and Segers (2003), *Inference for clusters of extreme
values*](https://doi.org/10.1111/1467-9868.00401).

Sueveges and Davison treat the threshold and run parameter as model choices
that require diagnostics. That motivates fixed parameters plus visible
sensitivity views rather than outcome-tuned selection:
[Sueveges and Davison (2010), *Model misspecification in peaks over threshold
analysis*](https://doi.org/10.1214/09-AOAS292).

Hansen and Hodrick address inference when observations are sampled more finely
than the forecast interval. That dependence is directly relevant to repeated
campaign observations paired with rolling features and overlapping outcome
horizons: [Hansen and Hodrick (1980), *Forward Exchange Rates as Optimal
Predictors of Future Spot Rates*](https://doi.org/10.1086/260910).

If the project later reports confidence intervals from a sufficiently large
episode sample, it must use a dependent-data method rather than iid intervals.
One established option is [Politis and Romano (1994), *The Stationary
Bootstrap*](https://doi.org/10.1080/01621459.1994.10476870).

This v1 implementation does not estimate an extremal index, fit a significance
model, or claim its fixed windows recover independent clusters. The literature
supports the need to make dependence and declustering explicit; the exact
24-hour product policy remains a transparent, reviewable engineering choice.

## Remaining evidence required before any promotion

- The Decision-v2 episode outcome scorecard now evaluates canonical outcomes on
  the frozen first representative only, with declared-primary-horizon censoring
  and exact candidate/Core/ledger bindings.
- Keep raw observation counts and episode counts side by side.
- Report missing/duplicate/ambiguous outcome evidence and right-censoring
  separately from directional results.
- Show 12/24/48-hour sensitivity, route/bias transitions, provider cohorts,
  coverage, and confidence intervals appropriate for dependent data.
- Demonstrate out-of-sample value with enough matured episodes and matched
  non-idea controls.
- Require a separate versioned decision, frozen thresholds, and rollback
  criteria before any runtime feature, route, or score consumes episode data.
