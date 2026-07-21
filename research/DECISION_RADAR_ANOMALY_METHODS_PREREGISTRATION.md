# Decision Radar anomaly-method preregistration

Status: **research-only design record; rank 1 is implemented as an isolated
shadow diagnostic but is not calibrated and is not eligible for routing,
scoring, publication authority, alerts, or Protocol-v2 evidence**.

Contract: `decision_radar.anomaly_methods_preregistration` schema v3.

## Purpose

Decision Radar needs stronger anomaly evidence, but the current live campaign is
too small and too dependent to justify changing production thresholds. This note
records the order in which candidate methods may be studied after genuine
point-in-time inputs and independent episode outcomes exist. It is intentionally
not an executable protocol and does not set thresholds, sample minima, or a
holdout.

## Current engine truth

- Canonical temporal features use strictly earlier, cadence-counted same-asset
  observations and keep the current value out of its own baseline.
- Production return, relative-return, volatility, volume, and turnover features
  currently use transparent mean/population-standard-deviation z-scores.
- Shadow schema v3 preserves the v1 natural-log median/MAD activity comparison
  and v2 direct and BTC/ETH-relative 1h/4h/24h signed-return comparison. It adds
  exact rounded-value distinct counts, tie concentration, current-value tie
  counts, and nominal finite-sample rank floors. Historical v1 and v2 values
  remain readable.
- That shadow value is explicitly barred from routes, priorities, Decision
  scores, thresholds, and automatic application.
- The canonical campaign report now performs a deterministic causal replay of
  that exact shadow evaluator over its one-read retained-history snapshot. It
  exposes per-feature coverage, degeneracy/status counts, exact input
  rejections, per-asset summaries, and source-bound plus causal-value digests.
  This is measurement plumbing only: it does not rewrite history or qualify as
  independent, calibrated, or Protocol-v2 evidence.
- The present campaign has overlapping observations and sparse matured ideas;
  repeated cycles are not independent samples.

## Candidate order

### 1. Robust signed-return and relative-return tails

Implemented originally in shadow schema v2 and preserved unchanged in v3 for
direct 1h, 4h, and 24h signed returns and BTC/ETH-relative returns. Each horizon
and basis remains a separate family.
The implementation rederives percent-point returns only from provider-observed
prices, uses causal at-or-before horizon anchors, keeps BTC/ETH endpoints at or
before the asset clock, and applies median/MAD plus sign-preserving lower,
upper, and two-sided descriptive ranks. Proxy prices, mismatched canonical
benchmark identities, future clocks, and insufficient or degenerate samples
fail closed. The dependent rolling ranks are explicitly not p-values.

Schema v3 also records how much nominal baseline count is repeated or quantized
after the method's existing 12-decimal derived-value normalization. These
variation fields are descriptive only: there is no minimum-distinct threshold,
and they do not change readiness, degeneracy, ranks, robust z-scores, routes,
or scores.

This remains rank 1 because it is a small, explainable extension of an already
closed shadow contract and directly addresses the heavy tails that make
mean/std z-scores fragile. Implementation does not imply empirical acceptance:
it remains unavailable when the scale degenerates and cannot affect production
until the evaluation contract below is completed.

### 2. Point-in-time crypto market-factor residuals

Study whether an asset-specific residual from a crypto market factor separates
idiosyncratic moves from broad risk-on/risk-off moves. Any coefficient, location,
or scale estimate must use prior development data only; current or later
cross-sectional returns cannot leak into the fit. Preserve the raw return and
factor return beside the residual, and report insufficient history instead of
falling back to an unadjusted score.

The motivation is empirical rather than a claim that one factor is sufficient:
published crypto-asset research finds material common market, size, and momentum
structure. Decision Radar should test whether removing a predeclared common
component improves anomaly discrimination, not assume that it does.

### 3. Online changepoint context

Study a separate changepoint flag that estimates whether the recent sequence is
more consistent with a persistent level/regime shift than an isolated outlier.
Bayesian online changepoint detection is a candidate because it maintains a
distribution over current run length using only observations available at each
step. The changepoint result must remain contextual: it cannot manufacture
direction, catalyst evidence, or tradability, and it must not be collapsed into
the magnitude surprise score before validation.

### 4. Extreme-value tail modeling, later

Consider a predeclared peaks-over-threshold/extreme-value experiment only after
the development partition contains enough independent, quality-controlled tail
exceedances per exact feature family. Threshold selection, declustering,
heteroskedastic filtering, parameter stability, and missing-data rules would
need to be frozen before evaluation. The current campaign is not large enough
to estimate these choices honestly.

### 5. Deferred: opaque multivariate detectors

Do not add Isolation Forest, autoencoders, or a broad anomaly ensemble now.
Sparse, overlapping data and heterogeneous missingness would make their scores
hard to interpret and easy to tune opportunistically. Revisit only after the
explainable univariate/residual candidates have a sealed benchmark, sufficient
independent episodes, point-in-time feature matrices, and an explicit
explanation/rollback contract.

## Cross-cutting calibration and alert-volume research

These are not additional detectors and do not alter the candidate order. They
are possible ways to calibrate or govern a future detector after it produces a
causal score.

### Adaptive online thresholds

Compare the unchanged fixed-threshold baseline with a shadow adaptive threshold
only after the development stream has enough point-in-time observations and the
target error event is defined before fitting. Confidence-sequence thresholding
is worth testing because recent work explicitly studies online unsupervised
threshold selection under distribution shift, including warm starts. Its
guarantees must not be imported by analogy: Decision Radar first has to prove
that its score, feedback clock, missingness, and dependence satisfy the chosen
method's data contract. The experiment must report false alerts and misses over
time, not only a pooled accuracy number.

Conformal anomaly scores are another calibration candidate, not an automatic
source of valid p-values. Time-series dependence violates ordinary
exchangeability, so any conformal experiment must freeze a causal rolling or
blocked calibration rule, preserve the exact reference set for every score,
and test coverage drift. A descriptive rank from the current shadow is not a
conformal p-value and must never be relabeled as one.

### Heavy-tail-aware change detection

The changepoint candidate should include one robust comparator designed for
heavy-tailed streams rather than testing only a light-tailed Bayesian model.
Clipped-estimator approaches with finite-sample false-positive analysis are a
useful research candidate. They still require an explicit stream, bounded
feature family, reset rule, missing-observation rule, false-alarm definition,
and detection-delay metric. A changepoint remains context and cannot create
direction, catalyst evidence, tradability, or a Decision route by itself.

### Multiple discoveries over assets, horizons, and time

If a future detector yields valid p-values or e-values, Protocol v2 must freeze
the hypothesis order and family before applying any online false-discovery
procedure. Asset, horizon, and timestamp tests are dependent; repeated rolling
observations and one market-wide move cannot be treated as independent tests.
SAFFRON is a candidate only if its validity assumptions are established for the
sealed stream. E-value-based online methods are worth comparing when valid
e-values can be constructed, but their dependence robustness does not excuse an
invalid score-to-e-value conversion. Until then, report alert burden and every
trial descriptively and make no FDR claim.

The eventual comparison must preserve an append-only trial ledger, count alerts
per operator day and per declustered episode, measure detection delay and
expiry, and report family-level error/coverage by regime and liquidity. No
method may choose its own threshold or stopping point from validation or
holdout outcomes.

## Evaluation contract before any promotion proposal

1. Finish genuine direct 1h/4h, execution-quality, derivatives, catalyst, and
   calendar collection with immutable point-in-time lineage.
2. Group repeated observations into predeclared episodes; never count rolling
   repeats or multiple assets in one market-wide move as independent by default.
3. Freeze exact development, validation, and untouched-holdout partitions before
   fitting or comparing candidates. Protocol-v1 final-test evidence is excluded.
4. Compare each candidate with the unchanged canonical feature on matured
   primary-horizon idea outcomes and matched non-idea controls.
5. Report coverage, missingness, degenerate-scale rate, provider/basis cohorts,
   false-positive burden, precision/recall where labels support them,
   time-indexed calibration, alert burden per operator day and declustered
   episode, detection delay, stability by regime, and uncertainty that respects
   dependence.
6. Predeclare candidate parameters, thresholds, minimum samples, costs, route
   scope, hypothesis family/order, error target, stopping rule, success
   criteria, failure criteria, and rollback rules in the sealed Protocol-v2
   annex. Until then they remain unspecified.
7. A separate reviewed decision is required for any production promotion. A
   null or negative result leaves current policy unchanged.

## Primary research references

- Huber, P. J. (1964), [Robust Estimation of a Location
  Parameter](https://doi.org/10.1214/aoms/1177703732), *The Annals of
  Mathematical Statistics* 35(1), 73-101.
- Adams, R. P. and MacKay, D. J. C. (2007), [Bayesian Online Changepoint
  Detection](https://arxiv.org/abs/0710.3742).
- Liu, Y., Tsyvinski, A., and Wu, X. (2019), [Common Risk Factors in
  Cryptocurrency](https://www.nber.org/papers/w25882), NBER Working Paper
  25882; later published in *The Journal of Finance*.
- McNeil, A. J. and Frey, R. (2000), [Estimation of Tail-Related Risk Measures
  for Heteroscedastic Financial Time Series: an Extreme Value
  Approach](https://doi.org/10.1016/S0927-5398(00)00012-8), *Journal of
  Empirical Finance* 7, 271-300.
- Ishimtsev, V., Bernstein, A., Burnaev, E., and Nazarov, I. (2017), [Conformal
  k-NN Anomaly Detector for Univariate Data
  Streams](https://proceedings.mlr.press/v60/ishimtsev17a.html), PMLR 60.
- Chernozhukov, V., Wuthrich, K., and Zhu, Y. (2018), [Exact and Robust
  Conformal Inference Methods for Predictive Machine Learning with Dependent
  Data](https://proceedings.mlr.press/v75/chernozhukov18a.html), PMLR 75.
- Ramdas, A., Zrnic, T., Wainwright, M., and Jordan, M. (2018), [SAFFRON: an
  Adaptive Algorithm for Online Control of the False Discovery
  Rate](https://proceedings.mlr.press/v80/ramdas18a.html), PMLR 80.
- Sankararaman, A. and Narayanaswamy, B. (2023), [Online Heavy-tailed
  Change-point Detection](https://proceedings.mlr.press/v216/sankararaman23a.html),
  PMLR 216.
- Sun, S. H., Sankararaman, A., and Narayanaswamy, B. M. (2024), [Online
  Adaptive Anomaly Thresholding with Confidence
  Sequences](https://proceedings.mlr.press/v235/sun24h.html), PMLR 235.
- Xu, Z. and Ramdas, A. (2024), [Online Multiple Testing with
  e-values](https://proceedings.mlr.press/v238/xu24a.html), PMLR 238.

These references motivate candidate families; they do not validate their use in
Decision Radar. That requires the sealed point-in-time evaluation above.
