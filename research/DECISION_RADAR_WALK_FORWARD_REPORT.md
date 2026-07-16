# Decision Radar Walk-Forward Report

- Report bundle: `75d50598fd03a07433caa6ef29c4f7f9f24b17408fbf433dbc34b373c07d89fa`
- Protocol: `decision_radar_empirical_validation_v1` (`efee20ccaa3dda03c8e1172633d92d6a9bf8cb3ae12c926471f2151941d5f158`)
- Selection run: `e906229597af15c6dc3caf3cb37a1846b5d273776c8477bc4637453a78ab7cec`
- Final-test run: `c4361588a7bc6165bf780e7dcd90ba81625be3fb5da711080a0f8c4cbf168933`
- Recommendation seal: `68594ec396be4aeb82f771ff864b24d0058c91ccbed9fc3a91fa9e42224ab87b`
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
