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

## Fixed v1 method

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

- Consecutive `volume_24h` observations overlap heavily and are autocorrelated.
- Crypto activity has intraday/weekly seasonality and provider-regime changes.
- MAD can be zero in short or quantized histories.
- A robust z-score is not calibrated probability and does not establish a
  catalyst or direction.
- An extreme small upper-tail rank can be a data-quality event, wash activity,
  or venue migration.

These limitations are why v1 remains shadow-only.

## Evidence required before promotion is even proposed

- Compare robust and canonical features on matured Decision outcomes and
  matched non-idea controls.
- Evaluate at anomaly-episode level so repeated observations of one move do not
  inflate sample size.
- Report coverage, degenerate-scale rate, provider/basis cohorts, precision,
  recall, false-positive rate, calibration, and confidence intervals.
- Freeze all runtime thresholds until a separate reviewed decision accepts a
  specific, versioned promotion with rollback criteria.
