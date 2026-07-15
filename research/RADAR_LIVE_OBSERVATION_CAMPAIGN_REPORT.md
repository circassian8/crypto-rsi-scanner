# Decision Radar live observation campaign v2

Generated at `2026-07-15T04:22:51.647284+00:00` from local artifacts only.
Research and decision support only. This report contains no trade recommendation.

## Campaign measurement

- Status: `in_progress_baseline_warming`
- Counted real/no-send cycles: `7`
- Real market observations: `210`
- Baseline-counting observations: `180`
- Too-close observations: `30`
- Real Decision candidates: `2`
- Current ideas: `0`
- Historical ideas: `2`
- Direct feature evidence: `840`
- Proxy feature evidence: `630`
- Pending outcomes: `1`
- Matured outcomes: `1`
- Provider failures: `0`
- Preflight/blocked attempts: `1`
- Event Alpha catalyst burn-in: `separate_not_aggregated`
- Historical market-provenance v2 fields: `read_only_adapter`

### Decision routes

- `risk_watch`: `2`

## Authority and pointer

- Pointer status: `invalid_or_untrusted`
- Current namespace: `radar_market_no_send_20260714t221551304500z_fcd6de29c447`
- Exact run: `2026-07-14T22:15:51.367228+00:00|no_key_live`
- Revision: `12`
- Exact operator binding: `false`

### Authoritative generations

| Namespace | Observed at | Candidates | Routes | Attempt audit | Publication | Operations | Current |
|---|---|---:|---|---|---|---|---|
| radar_market_no_send_20260713t190728z | 2026-07-13T19:07:29.084694+00:00 | 0 | none | published | published_legacy_audit | legacy_not_recorded | false |
| radar_market_no_send_20260714t002940z | 2026-07-14T00:29:40.814498+00:00 | 1 | risk_watch=1 | published | published_legacy_audit | legacy_not_recorded | false |
| radar_market_no_send_20260714t102122z | 2026-07-14T10:21:23.140944+00:00 | 0 | none | published | published_legacy_audit | legacy_not_recorded | false |
| radar_market_no_send_20260714t163300z | 2026-07-14T16:33:00.405079+00:00 | 0 | none | published | published_legacy_audit | legacy_not_recorded | false |
| radar_market_no_send_20260714t221551304500z_fcd6de29c447 | 2026-07-14T22:15:51.367228+00:00 | 0 | none | not_published | published | dashboard_restarted | false |

### Complete but non-authoritative generations

| Namespace | Observed at | Candidates | Routes | Attempt audit | Publication | Operations | Current |
|---|---|---:|---|---|---|---|---|
| radar_market_no_send | 2026-07-13T15:17:06.228233+00:00 | 0 | none | not_published | not_published | not_recorded | false |
| radar_market_no_send_20260713t152704z | 2026-07-13T15:27:13.330145+00:00 | 1 | risk_watch=1 | published | not_published | not_recorded | false |

## Baseline maturity

- Status: `warming`
- Retained observations: `210`
- Baseline-counted observations: `180`
- Too-close observations: `30`
- Duplicate observations: `0`
- Conflicting duplicate observations: `0`
- Assets: `33`
- Warm assets: `0`
- Minimum spacing seconds: `3600`

### Feature maturity

| Feature group | Warm assets | Warming assets | Status counts |
|---|---:|---:|---|
| btc_eth_relative | 0 | 33 | cold=5, warming=28 |
| returns_1h | 0 | 33 | cold=33 |
| returns_24h | 0 | 33 | cold=5, warming=28 |
| returns_4h | 0 | 33 | cold=33 |
| turnover | 0 | 33 | warming=33 |
| volatility | 0 | 33 | cold=5, warming=28 |
| volume | 0 | 33 | warming=33 |

## Outcomes

- Total canonical outcomes: `2`
- Pending: `1`
- Matured: `1`
- Missing data: `0`
- Source: `campaign_outcome_ledger`
- Refresh/build errors: `0`
- Human labels remain optional preference feedback; no thresholds or routes change automatically.

## Failed and blocked attempts

- No provider failures recorded.

| Namespace | Observed at | Status | Provider attempted | Failure class |
|---|---|---|---|---|
| radar_market_no_send | 2026-07-13T12:40:37.875495+00:00 | blocked | false | none |

## Excluded invalid generations

- None.

## Data-quality limitations

- **execution_quality_spread:** Trusted spread coverage is 0/210. Provider selection is deferred until the operator identifies the intended execution venue.
- **proxy_market_features:** The campaign retains 630 proxy feature observations; proxy evidence remains explicitly quality-capped.
- **temporal_baseline_maturity:** The required feature/time-aware temporal baseline is not globally warm.

## Next observation

- Next eligible time: `2026-07-14T23:15:51.367228+00:00`
- Eligible at report time: `true`
- Exact next safe operator command: `make radar-market-no-send PYTHON=.venv/bin/python`
- Authorization is rechecked at the provider boundary; this report never creates or changes it.

## Campaign-v2 conclusion

Decision Radar campaign v2 has 7 counted real/no-send cycles and 2 canonical ideas; 1 outcome is pending and 1 are matured. There are 0 provider failures and 1 blocked/preflight attempts. Baseline status is warming with 0/33 warm assets. Pointer history contains 5 bound generations and current authority is radar_market_no_send_20260714t221551304500z_fcd6de29c447. Data-quality limitation categories are execution_quality_spread, proxy_market_features, temporal_baseline_maturity; highest-value missing input is execution_quality_spread.

Spread-provider selection remains deferred until the operator identifies the intended execution venue.
No trade is recommended. No automatic threshold or route change is authorized.
