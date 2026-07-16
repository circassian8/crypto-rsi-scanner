# Decision Radar Research Limitations

- Report bundle: `267a1c6d30488fcd7088bf20ce6f653df6bf79f82c5e7d401e27fd4b24debbcf`
- Protocol: `decision_radar_empirical_validation_v1` (`efee20ccaa3dda03c8e1172633d92d6a9bf8cb3ae12c926471f2151941d5f158`)
- Selection run: `8212b2ddb626805f4312d8986cc1d9f6b3229a169aa49ca75b9b5bbfc1660489`
- Final-test run: `3009e23dd9a9f11418cf97ee07f6e532c451c21196e69bd1ae0cd6ae96c47e72`
- Recommendation seal: `3f0ea69c2cb3c455bf9d8e13f44f6db6cee6308192c61a090b9f39e0a5442639`
- Live no-send report: `provided_separate_observational_lane`
- Safety: research only; no automatic policy application; no sends, trades, orders, paper trades, RSI writes, provider calls, or authority mutations.

## Current limitations

1. Historical replay is descriptive and cannot establish causal alpha.
2. Daily historical OHLCV cannot validate intraday execution, exact alert latency, order-book spread, slippage, or adverse selection.
3. Historical spread observed: `False`. Cost results are assumptions unless separately marked observed.
4. Residual survivorship present: `True`.
5. Proxy and direct evidence remain separate cohorts; a proxy-only result must not be generalized to direct live evidence.
6. Matched controls are selected without outcomes but are not a randomized experiment.
7. Walk-forward folds overlap in training history and are not independent trials.
8. Multiple cohort and scenario comparisons increase false-discovery risk.
9. Live no-send evidence is fingerprinted separately and is never pooled into historical replay sample sizes.
10. Human review labels are optional preference data and cannot auto-tune the model.
11. No final-test result can nominate a new policy scenario.
12. No thresholds, routes, sends, trades, execution, paper trades, RSI writes, or dashboard authority changed.

## Explicit no-evidence cohorts

Routes:

`high_confidence_watch`, `actionable_watch`, `rapid_market_anomaly`, `fade_exhaustion_review`, `calendar_risk`

Primary thesis origins:

`catalyst_led`, `technical_led`, `derivatives_led`, `onchain_led`, `fundamental_led`, `macro_led`

A zero-sample route or origin is unvalidated; it is not evidence of safety, weakness, or strength.

## Next human boundary

Review any sealed confirmation alongside sample size, regime coverage, data-quality basis, cost survivability, and operator burden. A separate explicit human decision is required before changing production policy.
