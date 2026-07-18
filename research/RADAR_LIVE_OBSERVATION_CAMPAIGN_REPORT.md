# Decision Radar live observation campaign v2

Generated at `2026-07-18T02:49:46.417202+00:00` from local artifacts only.
Research and decision support only. This report contains no trade recommendation.

## Campaign measurement

- Status: `in_progress_baseline_warming`
- Counted real/no-send cycles: `10`
- Real market observations: `300`
- Baseline-counting observations: `270`
- Too-close observations: `30`
- Real Decision candidates: `3`
- Current ideas: `1`
- Historical ideas: `2`
- Direct feature evidence: `1254`
- Proxy feature evidence: `846`
- Pending outcomes: `1`
- Matured outcomes: `1`
- Provider failures: `2`
- Preflight/blocked attempts: `1`
- Event Alpha catalyst burn-in: `separate_not_aggregated`
- Historical market-provenance v2 fields: `read_only_adapter`

### Decision routes

- `dashboard_watch`: `1`
- `risk_watch`: `2`

## Authority and pointer

- Pointer status: `authoritative`
- Current authority namespace: `radar_market_no_send_20260718t024737179194z_ec091813d359`
- Pointer target namespace: `radar_market_no_send_20260718t024737179194z_ec091813d359`
- Exact run: `2026-07-18T02:47:37.287740+00:00|no_key_live`
- Revision: `12`
- Exact operator binding: `true`

### Authoritative generations

| Namespace | Observed at | Candidates | Routes | Attempt audit | Publication | Operations | Current |
|---|---|---:|---|---|---|---|---|
| radar_market_no_send_20260713t190728z | 2026-07-13T19:07:29.084694+00:00 | 0 | none | published | published_legacy_audit | legacy_not_recorded | false |
| radar_market_no_send_20260714t002940z | 2026-07-14T00:29:40.814498+00:00 | 1 | risk_watch=1 | published | published_legacy_audit | legacy_not_recorded | false |
| radar_market_no_send_20260714t102122z | 2026-07-14T10:21:23.140944+00:00 | 0 | none | published | published_legacy_audit | legacy_not_recorded | false |
| radar_market_no_send_20260714t163300z | 2026-07-14T16:33:00.405079+00:00 | 0 | none | published | published_legacy_audit | legacy_not_recorded | false |
| radar_market_no_send_20260714t221551304500z_fcd6de29c447 | 2026-07-14T22:15:51.367228+00:00 | 0 | none | not_published | published | dashboard_restarted | false |
| radar_market_no_send_20260716t020832349089z_ed303d3217c3 | 2026-07-16T02:08:32.428755+00:00 | 0 | none | not_published | published | dashboard_restarted | false |
| radar_market_no_send_20260718t024737179194z_ec091813d359 | 2026-07-18T02:47:37.287740+00:00 | 1 | dashboard_watch=1 | not_published | published | dashboard_restarted | true |

### Complete but non-authoritative generations

| Namespace | Observed at | Candidates | Routes | Attempt audit | Publication | Operations | Current |
|---|---|---:|---|---|---|---|---|
| radar_market_no_send | 2026-07-13T15:17:06.228233+00:00 | 0 | none | not_published | not_published | not_recorded | false |
| radar_market_no_send_20260713t152704z | 2026-07-13T15:27:13.330145+00:00 | 1 | risk_watch=1 | published | not_published | not_recorded | false |
| radar_market_no_send_20260716t184915z | 2026-07-16T18:49:16.403979+00:00 | 0 | none | not_published | not_published | not_recorded | false |

## Baseline maturity

- Status: `warming`
- Retained observations: `300`
- Baseline-counted observations: `270`
- Too-close observations: `30`
- Duplicate observations: `0`
- Conflicting duplicate observations: `0`
- Assets: `34`
- Warm assets: `0`
- Minimum spacing seconds: `3600`

### Feature maturity

| Feature group | Warm assets | Warming assets | Status counts |
|---|---:|---:|---|
| btc_eth_relative | 0 | 34 | cold=4, warming=30 |
| returns_1h | 0 | 34 | cold=34 |
| returns_24h | 0 | 34 | cold=4, warming=30 |
| returns_4h | 0 | 34 | cold=34 |
| turnover | 27 | 7 | warm=27, warming=7 |
| volatility | 0 | 34 | cold=4, warming=30 |
| volume | 27 | 7 | warm=27, warming=7 |

## Outcomes

- Total canonical outcomes: `3`
- Pending: `1`
- Matured: `1`
- Missing data: `1`
- Source: `campaign_outcome_ledger`
- Refresh/build errors: `0`
- Human labels remain optional preference feedback; no thresholds or routes change automatically.

## Anomaly episodes (shadow)

Repeated observations are grouped into fixed-start descriptive episodes; they are not claimed to be statistically independent.
- Input status: `partial`
- Candidate input status: `ready`
- Outcome input status: `partial`
- Structural membership status: `ready`
- Outcome ledger status: `observed`
- Candidate snapshots: `10`/`10` generations
- Eligible anomaly observations: `3`
- Excluded observations: `0`
- Primary 24h episodes: `2`
- Primary repeats: `1`
- Candidate rows outside market-anomaly scope: `0`
- Missing outcome joins: `0`
- Ambiguous outcome joins: `0`
- Invalid outcome rows: `0`
- Duplicate outcome identities: groups=`0`, rows=`0`
- Cross-candidate outcome collisions: groups=`0`, candidates=`0`, rows=`0`
- Orphan outcome rows: `0`
- Outcome evidence statuses: `available=1, unavailable=2`
- Generation rejections: `0` (`none`)
- Candidate-row rejections: `0` (`none`)
- `12h` sensitivity: episodes=`2`, repeats=`1`
- `24h` sensitivity: episodes=`2`, repeats=`1`
- `48h` sensitivity: episodes=`2`, repeats=`1`
- The first observation is frozen as representative before outcome maturity is inspected.
- Shadow only: no route, score, threshold, provider, publication, or authority change.

## Decision-v2 episode outcomes (shadow)

Only the frozen first member of each primary episode is evaluated; outcome maturity never reselects a representative.
- Status: `ready`
- Episode representatives: `2`
- Matured primary outcomes: `1`
- Scoreable directional outcomes: `1`
- Primary outcome states: `contract_excluded=0, due_missing_price=0, matured=1, not_due=1`
- Direction alignment: `aligned=1, flat=0, non_directional=0, not_evaluated=1, opposed=0`
- Cohort persistence: `canonical_exact=2`
- Exact source artifact bindings: `7`
- Exact outcome validation bindings: `3`
- Policy conclusion: `insufficient_for_policy_change`
- Direction comes from canonical Decision-v2 bias, not a legacy Event Alpha lane; only the declared primary horizon may mature.

| Asset | Route | Bias | State | Alignment | Primary return (fraction) | Score cohorts A/E/R |
|---|---|---|---|---|---:|---|
| dexe | risk_watch | risk | matured | aligned | -0.00949598 | 25_49/45_64/45_64 |
| dexe | dashboard_watch | long | not_due | not_evaluated | n/a | 50_69/45_64/45_64 |
- Descriptive only: no route, score, calibration, threshold, or authority change is eligible.

## Failed and blocked attempts

| Namespace | Observed at | Status | Provider attempted | Failure class |
|---|---|---|---|---|
| radar_market_no_send_20260718t002953190093z_d31fe5583f6d | 2026-07-18T00:29:53.294224+00:00 | provider_unavailable | true | ClientConnectorDNSError |
| radar_market_no_send_20260718t014700z | 2026-07-18T01:47:01.192491+00:00 | provider_unavailable | true | ClientConnectorDNSError |

| Namespace | Observed at | Status | Provider attempted | Failure class |
|---|---|---|---|---|
| radar_market_no_send | 2026-07-13T12:40:37.875495+00:00 | blocked | false | none |

## Excluded invalid generations

- None.

## Data-quality limitations

- **execution_quality_spread:** Trusted spread coverage is 0/300. Bybit USDT-linear perpetuals are the selected execution surface; coverage remains unavailable until a separately authorized immutable public-market capture succeeds and is bound into the campaign.
- **proxy_market_features:** The campaign retains 846 proxy feature observations; proxy evidence remains explicitly quality-capped.
- **temporal_baseline_maturity:** The required feature/time-aware temporal baseline is not globally warm.

## Next observation

- Next eligible time: `2026-07-18T03:47:37.287740+00:00`
- Eligible at report time: `false`
- Exact next safe operator command: `make radar-market-no-send-readiness PYTHON=.venv/bin/python`
- Authorization is rechecked at the provider boundary; this report never creates or changes it.

## Campaign-v2 conclusion

Decision Radar campaign v2 has 10 counted real/no-send cycles and 3 canonical ideas; 1 outcome is pending and 1 are matured. There are 2 provider failures and 1 blocked/preflight attempts. Baseline status is warming with 0/34 warm assets. Pointer history contains 7 bound generations and current authority is radar_market_no_send_20260718t024737179194z_ec091813d359. Data-quality limitation categories are execution_quality_spread, proxy_market_features, temporal_baseline_maturity; highest-value missing input is execution_quality_spread.

Bybit USDT-linear perpetuals are the selected execution surface; no spread or depth evidence is treated as available until a separately authorized immutable capture succeeds.
No trade is recommended. No automatic threshold or route change is authorized.
