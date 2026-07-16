# Decision Radar Policy Simulation Report

- Report bundle: `267a1c6d30488fcd7088bf20ce6f653df6bf79f82c5e7d401e27fd4b24debbcf`
- Protocol: `decision_radar_empirical_validation_v1` (`efee20ccaa3dda03c8e1172633d92d6a9bf8cb3ae12c926471f2151941d5f158`)
- Selection run: `8212b2ddb626805f4312d8986cc1d9f6b3229a169aa49ca75b9b5bbfc1660489`
- Final-test run: `3009e23dd9a9f11418cf97ee07f6e532c451c21196e69bd1ae0cd6ae96c47e72`
- Recommendation seal: `3f0ea69c2cb3c455bf9d8e13f44f6db6cee6308192c61a090b9f39e0a5442639`
- Live no-send report: `provided_separate_observational_lane`
- Safety: research only; no automatic policy application; no sends, trades, orders, paper trades, RSI writes, provider calls, or authority mutations.

## Frozen recommendations

| Scenario | Selection status | Evidence | Reason |
|---|---|---|---|
| `dashboard_watch_40` | `not_supported` | `policy_candidate_sample` | frozen_multi_metric_rule_not_met |
| `dashboard_watch_50` | `not_supported` | `policy_candidate_sample` | frozen_multi_metric_rule_not_met |
| `actionable_70` | `not_supported` | `policy_candidate_sample` | scenario_produced_no_observable_policy_change |
| `actionable_evidence_60` | `not_supported` | `policy_candidate_sample` | scenario_produced_no_observable_policy_change |
| `actionable_max_risk_55` | `not_supported` | `policy_candidate_sample` | scenario_produced_no_observable_policy_change |
| `unknown_spread_dashboard_only` | `not_supported` | `policy_candidate_sample` | scenario_produced_no_observable_policy_change |
| `rapid_urgency_78` | `not_supported` | `policy_candidate_sample` | scenario_produced_no_observable_policy_change |
| `expiry_24h` | `not_supported` | `policy_candidate_sample` | scenario_produced_no_observable_policy_change |
| `family_cooldown_48h` | `not_supported` | `policy_candidate_sample` | scenario_produced_no_observable_policy_change |

## Sealed final-test confirmation

- Status: `no_candidate_recommendations`
- Confirmed / rejected / insufficient: 0 / 0 / 0
- Final-test data could confirm or reject only pre-sealed candidates; it could not nominate a new scenario.
- Production thresholds and routes remain unchanged. Human approval is required for any future policy change.
