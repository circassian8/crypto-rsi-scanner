# Decision Radar Protocol-v2 statistical preregistration

Status: **research-only design record; not the Protocol-v2 annex, not
implemented, and not eligible for evaluation, selection, promotion, routing,
scoring, or production policy**.

As of: **2026-07-19**.

## Purpose

Protocol v2 must decide how evidence will be counted and tested before results
can influence those decisions. This record fixes that statistical discipline
without selecting numerical values, partitions, holdout bytes, or a success
threshold. It complements the frozen readiness contract and current progress
projection; it does not modify either one and cannot activate a replay or final
test.

The governing principle is simple: repeated observations, related assets, and
many tried variants must not masquerade as independent confirmation.

## Analysis unit and dependence

- The primary analysis unit is a predeclared, declustered **Decision episode**,
  not an observation row, scan cycle, notification, card, or repeated idea.
- Repeated observations of the same thesis remain one episode until a frozen
  episode-reset rule proves a new opportunity. The exact reset rule is deferred
  to the annex.
- Episodes sharing the same broad market-risk window, common catalyst, or
  mechanically linked asset family remain explicit dependence clusters. A
  larger asset count does not by itself create a larger independent sample.
- Aggregate, route, bias, regime, liquidity, and evidence-quality counts must
  report both rows and distinct episodes. Any independence claim must use the
  latter plus the declared clustering rule.
- Ordinary independent-and-identically-distributed standard errors, random-row
  resampling, and naive row-count sample claims are prohibited unless a future
  sealed diagnostic establishes that the relevant errors are effectively
  uncorrelated. Absence of evidence is not that proof.

## Chronological partition and leakage boundary

1. Freeze chronological `development`, `validation`, and one untouched
   `holdout` partition before candidate comparison.
2. Do not use random row K-fold cross-validation by default. Any repeated
   development resampling must preserve time order and episode/dependence
   groups.
3. Purge and embargo partition boundaries by at least the longest relevant
   feature lookback, outcome horizon, idea lifetime/expiry, and overlapping
   episode window. The exact duration is not chosen here.
4. Fit transformations, missingness rules, nuisance parameters, block lengths,
   thresholds, and model choices on development data only. Validation can
   accept or reject the frozen candidate; it cannot silently retune it.
5. The holdout's dates, source paths, content, digest, and access credentials
   remain undefined and unopened now. The final annex must bind them before the
   first byte is read and keep an immutable access ledger.
6. Protocol-v1 final-test evidence is excluded from tuning, sample planning,
   candidate selection, and Protocol-v2 promotion.

## Dependence-aware uncertainty

- Report descriptive point estimates with episode and cluster counts first.
- For development and validation intervals, use a time-respecting block method,
  such as the stationary bootstrap, rather than an IID row bootstrap.
- Choose the block-length method and its result using development-only
  diagnostics, then freeze it before validation. Do not select the block length
  that produces the most favorable interval.
- Preserve same-episode and market-risk clustering in every resample. When the
  data cannot support that construction, uncertainty is `unavailable`, not an
  IID approximation.
- Cross-sectional and temporal dependence are separate facts. The annex must
  state how both are represented and report sensitivity to the declared
  cluster definition.

## Permanent trial ledger

Every evaluated feature, transformation, model, parameter grid, threshold,
route subset, outcome definition, cost assumption, cohort split, and stopping
choice is one recorded trial or a declared member of a recorded family.

The ledger must:

- include failed, abandoned, and apparently equivalent attempts;
- record proposal time, hypothesis/family, author, code/config/data digests,
  partitions touched, parameters, outputs, and disposition;
- prohibit resetting the count by renaming a method, changing a branch, or
  rebuilding artifacts;
- distinguish planned-but-never-run work from executed trials;
- bind every reported candidate to the complete prior trial history available
  at its decision time; and
- remain immutable and append-only after the annex is sealed.

Exploratory work may continue in development, but it increases the honest trial
count. Validation and holdout access are not exploration surfaces.

## Multiple-testing and overfitting diagnostics

- The annex must choose one family-level multiple-testing procedure before
  validation. White's Reality Check and Hansen's Superior Predictive Ability
  test are candidates; this record does not choose between them or set an error
  rate.
- A Deflated Sharpe Ratio may be reported only as a secondary diagnostic when a
  predeclared, economically meaningful return statistic and honest trial count
  exist. It must never be applied to Decision scores, route scores, confidence
  bands, or arbitrary non-return metrics.
- Combinatorially Symmetric Cross-Validation / Probability of Backtest
  Overfitting may be used only as a development/validation diagnostic over
  leakage-safe temporal blocks. It does not replace the one untouched holdout.
- A favorable unadjusted result with an unfavorable family-level or overfitting
  diagnostic is not evidence for promotion.
- None of these diagnostics repairs bad lineage, missing costs, look-ahead,
  insufficient episodes, or an opened/reused holdout.

## Minimum-sample method, not a number

Before validation, the annex must define:

1. the primary estimand and outcome metric;
2. the smallest effect worth detecting or the maximum tolerable estimation
   error;
3. the confidence/error-control and power policy;
4. the observed cost model and missing-data/attrition policy;
5. development-only estimates of variance, event rate, within-cluster
   correlation, and missingness;
6. dependence and attrition inflation; and
7. exact minimum distinct-episode and distinct-market-window counts.

Minimums must be frozen separately for the aggregate evaluation and every
predeclared route, route-by-bias, regime, liquidity, execution-quality, and
source-quality conclusion. A cohort below its minimum remains unavailable; it
must not be pooled with an incompatible cohort merely to reach a number.
Regime diversity is a separate coverage requirement from episode count.

This record chooses no effect size, power, confidence level, error rate, event
rate, or sample minimum because the necessary genuine point-in-time evidence
does not yet exist.

## Evaluation and promotion sequence

1. Freeze the unchanged canonical control and one candidate specification.
2. Evaluate mature, leakage-safe episode outcomes plus matched non-idea controls
   under observed venue costs and exact point-in-time coverage.
3. Report coverage, missingness, false-positive/operator burden, calibration,
   time-to-detection, and direction-adjusted research outcomes. Do not convert
   this into a trading or PnL product claim.
4. Apply the sealed dependence and multiple-testing contract on development and
   validation only.
5. If the candidate passes the predeclared validation rule, permit one exact
   holdout access under the immutable ledger. Otherwise stop.
6. Publish negative, null, and inconclusive results. A failed holdout cannot be
   tuned against; any new candidate starts a new protocol with a new untouched
   holdout.
7. Production promotion still requires a separate explicit human decision.

## Values intentionally deferred to the final annex

- exact episode-reset and dependence-cluster definitions;
- partition dates, data digests, and untouched-holdout identity;
- purge and embargo duration;
- primary and secondary metrics;
- smallest worthwhile effect and precision target;
- confidence, power, family-wise error, or false-discovery policy;
- block-length selector and frozen block length;
- exact aggregate and cohort sample minimums;
- family-level multiple-testing procedure;
- success, failure, stopping, and promotion thresholds; and
- route scope, cost sensitivity, and rollback rules.

## Current blockers

- genuine Bybit USDT-linear execution-quality, 1h/4h, and derivatives captures;
- exact Protocol-v2 eligible instrument set and observed cost evidence;
- authoritative catalyst, unlock, on-chain/DEX, fundamental, and macro context;
- complete due outcomes and frozen human/OOS labels;
- enough distinct route episodes and market-risk windows to estimate nuisance
  quantities honestly;
- exact chronological partitions and a still-unidentified untouched holdout;
  and
- final human approval of the complete Protocol-v2 annex.

Until those blockers close, this document changes no feature, score, threshold,
route, dashboard authority, provider authorization, or production behavior.

## Primary research references

- Politis, D. N. and Romano, J. P. (1994), [The Stationary
  Bootstrap](https://doi.org/10.1080/01621459.1994.10476870), *Journal of the
  American Statistical Association* 89(428), 1303-1313.
- White, H. (2000), [A Reality Check for Data
  Snooping](https://doi.org/10.1111/1468-0262.00152), *Econometrica* 68(5),
  1097-1126.
- Hansen, P. R. (2005), [A Test for Superior Predictive
  Ability](https://doi.org/10.1198/073500105000000063), *Journal of Business &
  Economic Statistics* 23(4), 365-380.
- Bailey, D. H., Borwein, J. M., López de Prado, M., and Zhu, Q. J. (2014),
  [Pseudo-Mathematics and Financial
  Charlatanism](https://ssrn.com/abstract=2308659), which introduces the
  Deflated Sharpe Ratio framework; see also the authors'
  [Deflated Sharpe Ratio paper](https://ssrn.com/abstract=2460551).
- Bailey, D. H., Borwein, J. M., López de Prado, M., and Zhu, Q. J. (2016),
  [The Probability of Backtest
  Overfitting](https://ssrn.com/abstract=2326253), *Journal of Computational
  Finance* 20(4), 39-69.
- Bergmeir, C., Hyndman, R. J., and Koo, B. (2018), [A Note on the Validity of
  Cross-Validation for Evaluating Autoregressive Time Series
  Prediction](https://doi.org/10.1016/j.csda.2017.11.003), *Computational
  Statistics & Data Analysis* 120, 70-83.
- Harvey, C. R. and Liu, Y. (2014), [Evaluating Trading
  Strategies](https://ssrn.com/abstract=2474755).

These sources motivate the preregistered safeguards. They do not validate any
Decision Radar method, parameter, sample size, or trading result.
