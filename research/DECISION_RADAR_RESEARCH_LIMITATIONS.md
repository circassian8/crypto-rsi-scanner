# Decision Radar Research Limitations

- Report bundle: `75d50598fd03a07433caa6ef29c4f7f9f24b17408fbf433dbc34b373c07d89fa`
- Protocol: `decision_radar_empirical_validation_v1` (`efee20ccaa3dda03c8e1172633d92d6a9bf8cb3ae12c926471f2151941d5f158`)
- Selection run: `e906229597af15c6dc3caf3cb37a1846b5d273776c8477bc4637453a78ab7cec`
- Final-test run: `c4361588a7bc6165bf780e7dcd90ba81625be3fb5da711080a0f8c4cbf168933`
- Recommendation seal: `68594ec396be4aeb82f771ff864b24d0058c91ccbed9fc3a91fa9e42224ab87b`
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
