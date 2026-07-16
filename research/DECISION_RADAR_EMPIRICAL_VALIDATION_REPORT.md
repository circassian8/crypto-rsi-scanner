# Decision Radar Empirical Validation Report

- Report bundle: `267a1c6d30488fcd7088bf20ce6f653df6bf79f82c5e7d401e27fd4b24debbcf`
- Protocol: `decision_radar_empirical_validation_v1` (`efee20ccaa3dda03c8e1172633d92d6a9bf8cb3ae12c926471f2151941d5f158`)
- Selection run: `8212b2ddb626805f4312d8986cc1d9f6b3229a169aa49ca75b9b5bbfc1660489`
- Final-test run: `3009e23dd9a9f11418cf97ee07f6e532c451c21196e69bd1ae0cd6ae96c47e72`
- Recommendation seal: `3f0ea69c2cb3c455bf9d8e13f44f6db6cee6308192c61a090b9f39e0a5442639`
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
