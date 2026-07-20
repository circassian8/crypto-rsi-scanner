# Decision Radar anomaly-method preregistration

Status: **research-only design record; rank 1 is implemented as an isolated
shadow diagnostic but is not calibrated and is not eligible for routing,
scoring, publication authority, alerts, or Protocol-v2 evidence**.

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
- Shadow schema v2 preserves the v1 natural-log median/MAD activity comparison
  for eligible `volume_24h` and `turnover_24h`, and implements the preregistered
  rank-1 signed-return comparison for direct and BTC/ETH-relative 1h/4h/24h
  families. Historical v1 values remain readable.
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

Implemented as shadow schema v2 for direct 1h, 4h, and 24h signed returns and
BTC/ETH-relative returns. Each horizon and basis remains a separate family.
The implementation rederives percent-point returns only from provider-observed
prices, uses causal at-or-before horizon anchors, keeps BTC/ETH endpoints at or
before the asset clock, and applies median/MAD plus sign-preserving lower,
upper, and two-sided descriptive ranks. Proxy prices, mismatched canonical
benchmark identities, future clocks, and insufficient or degenerate samples
fail closed. The dependent rolling ranks are explicitly not p-values.

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
   calibration, stability by regime, and uncertainty that respects dependence.
6. Predeclare candidate parameters, thresholds, minimum samples, costs, route
   scope, success criteria, failure criteria, and rollback rules in the sealed
   Protocol-v2 annex. Until then they remain unspecified.
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

These references motivate candidate families; they do not validate their use in
Decision Radar. That requires the sealed point-in-time evaluation above.
