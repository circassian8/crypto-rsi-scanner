# Decision Radar Empirical Validation Report

- Report bundle: `75d50598fd03a07433caa6ef29c4f7f9f24b17408fbf433dbc34b373c07d89fa`
- Protocol: `decision_radar_empirical_validation_v1` (`efee20ccaa3dda03c8e1172633d92d6a9bf8cb3ae12c926471f2151941d5f158`)
- Selection run: `e906229597af15c6dc3caf3cb37a1846b5d273776c8477bc4637453a78ab7cec`
- Final-test run: `c4361588a7bc6165bf780e7dcd90ba81625be3fb5da711080a0f8c4cbf168933`
- Recommendation seal: `68594ec396be4aeb82f771ff864b24d0058c91ccbed9fc3a91fa9e42224ab87b`
- Live no-send report: `provided_separate_observational_lane`
- Safety: research only; no automatic policy application; no sends, trades, orders, paper trades, RSI writes, provider calls, or authority mutations.

## Verdict

This is a research-only, descriptive replay result. It does not establish causal alpha, recommend a trade, or change production policy.

- Selection ideas / episodes: 3426 / 3127
- Final-test ideas / episodes: 1512 / 1423
- Final confirmation: `no_candidate_recommendations`
- Confirmed / rejected / insufficient: 0 / 0 / 0

## Route evidence

| Route | Development matured | Validation matured | Final-test matured |
|---|---:|---:|---:|
| `high_confidence_watch` | 0 | 0 | 0 |
| `actionable_watch` | 0 | 0 | 0 |
| `rapid_market_anomaly` | 0 | 0 | 0 |
| `dashboard_watch` | 296 | 338 | 229 |
| `fade_exhaustion_review` | 0 | 0 | 0 |
| `risk_watch` | 1453 | 957 | 1149 |
| `calendar_risk` | 0 | 0 | 0 |
| `diagnostic` | 50 | 31 | 45 |

## Origin evidence

| Primary thesis origin | Development matured | Validation matured | Final-test matured |
|---|---:|---:|---:|
| `market_led` | 1799 | 1326 | 1423 |
| `catalyst_led` | 0 | 0 | 0 |
| `technical_led` | 0 | 0 | 0 |
| `derivatives_led` | 0 | 0 | 0 |
| `onchain_led` | 0 | 0 | 0 |
| `fundamental_led` | 0 | 0 | 0 |
| `macro_led` | 0 | 0 | 0 |

Zero samples are reported as no evidence, never as validation.

## Cross-checks

- Walk-forward: `complete`; outcome-evaluable folds 3 / 3 required.
- Score monotonicity: development=`violations_observed`, final_test=`violations_observed`, validation=`violations_observed`
- Live no-send lane: `provided_separate_observational_lane`; evidence pooled with replay: `False`.
- Confirmation verification: canonical persisted scenario reduction is exact-equal; compact reports do not reconstruct stripped raw threshold contexts or re-evaluate Decision v2

## Additional evidence most needed

- observed bid-ask spread and order-book execution-quality snapshots
- intraday bars and exact decision-to-review latency
- direct catalyst, calendar, derivatives, and on-chain evidence with point-in-time lineage
- more independent matured episodes across routes, regimes, and data-quality cohorts

## Evidence boundaries

- Historical replay and live no-send evidence remain separate.
- Missing historical spread is not treated as observed execution quality.
- Matched controls are descriptive and do not support causal inference.
- Every policy recommendation still requires an explicit human decision.
