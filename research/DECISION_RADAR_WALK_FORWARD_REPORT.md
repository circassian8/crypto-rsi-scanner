# Decision Radar Walk-Forward Report

- Report bundle: `267a1c6d30488fcd7088bf20ce6f653df6bf79f82c5e7d401e27fd4b24debbcf`
- Protocol: `decision_radar_empirical_validation_v1` (`efee20ccaa3dda03c8e1172633d92d6a9bf8cb3ae12c926471f2151941d5f158`)
- Selection run: `8212b2ddb626805f4312d8986cc1d9f6b3229a169aa49ca75b9b5bbfc1660489`
- Final-test run: `3009e23dd9a9f11418cf97ee07f6e532c451c21196e69bd1ae0cd6ae96c47e72`
- Recommendation seal: `3f0ea69c2cb3c455bf9d8e13f44f6db6cee6308192c61a090b9f39e0a5442639`
- Live no-send report: `provided_separate_observational_lane`
- Safety: research only; no automatic policy application; no sends, trades, orders, paper trades, RSI writes, provider calls, or authority mutations.

## Result

- Status: `complete`
- Folds / non-empty / outcome-evaluable / required: 3 / 3 / 3 / 3
- Outcome purge rule: `primary_horizon_due_at_lt_fold_boundary`
- Final test accessed for selection: `False`

| Fold | Train end | Test end | Selected scenario | Test episodes |
|---:|---|---|---|---:|
| 1 | 2023-06-12T00:00:00+00:00 | 2023-12-09T00:00:00+00:00 | `production_policy` | 192 |
| 2 | 2023-12-09T00:00:00+00:00 | 2024-06-06T00:00:00+00:00 | `dashboard_watch_40` | 370 |
| 3 | 2024-06-06T00:00:00+00:00 | 2024-12-03T00:00:00+00:00 | `production_policy` | 331 |

Fold estimates are exploratory, not independent causal estimates. No scenario is applied automatically.
