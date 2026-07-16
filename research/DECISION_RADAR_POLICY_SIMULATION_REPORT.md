# Decision Radar Policy Simulation Report

- Report bundle: `75d50598fd03a07433caa6ef29c4f7f9f24b17408fbf433dbc34b373c07d89fa`
- Protocol: `decision_radar_empirical_validation_v1` (`efee20ccaa3dda03c8e1172633d92d6a9bf8cb3ae12c926471f2151941d5f158`)
- Selection run: `e906229597af15c6dc3caf3cb37a1846b5d273776c8477bc4637453a78ab7cec`
- Final-test run: `c4361588a7bc6165bf780e7dcd90ba81625be3fb5da711080a0f8c4cbf168933`
- Recommendation seal: `68594ec396be4aeb82f771ff864b24d0058c91ccbed9fc3a91fa9e42224ab87b`
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
